"""모방 학습(11장)으로 단계별 PPO 정책들을 하나의 정책으로 합친다: Behavior Cloning vs DAgger.

선생님(expert): 단계마다 고른 PPO 정책 (runs/results/laser/ppo_specialists.json, 1~10단계 평균 82.4%)
학생(learner): PPO actor와 같은 크기의 신경망 하나 (66 → 256 → 256 → 27, tanh). 모든 단계를 혼자 푼다.

  BC     : 선생님이 플레이한 상태만 모은다. 학생은 실수로 벗어난 상태를 배운 적이 없다 (분포 이동).
  DAgger : 1회차는 선생님이, 2회차부터는 학생이 플레이하고 선생님이 그 상태에 정답을 붙인다.
           데이터를 계속 합쳐서(aggregate) 다시 학습한다.

두 방식은 회차 수, 회차당 상태 수, 학습 횟수가 모두 같다. 다른 것은 "누가 플레이한 상태를 모으느냐"뿐이다.

  .venv-unity\\Scripts\\python -m laser.imitation --mode dagger --seed 0
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from algos.common import mlp
from laser.campaign_eval import EVAL_SEED, LEVELS, evaluate_model, evaluation_env
from laser.env import N_ACTIONS, OBS_DIM
from laser.ppo_specialists import StagePolicy
from laser.train import evaluate

SPECIALISTS = Path("runs/results/laser/ppo_specialists.json")   # --teachers로 바꿀 수 있다
REFERENCE_RUN = Path("runs/laser/x12/ppo_random_campaign_seed0")


class Student:
    """FrozenPolicy와 같은 인터페이스(act)를 가진 학생 정책."""
    kind = "ppo"

    def __init__(self, hidden, seed):
        torch.manual_seed(seed)
        self.hidden = hidden
        self.net = mlp(OBS_DIM, N_ACTIONS, hidden, act=nn.Tanh)
        self.steps = 0

    @torch.no_grad()
    def act(self, obs):
        return self.net(torch.as_tensor(obs, dtype=torch.float32)).argmax(-1).numpy()

    def save(self, path, config):
        torch.save({"steps": self.steps, "kind": "ppo", "state_dict": self.net.state_dict(), "obs_dim": OBS_DIM,
                    "action_set": list(range(N_ACTIONS)), "hidden": self.hidden, "config": config}, path)


def load_common():
    cfg = json.loads((REFERENCE_RUN / "config.json").read_text(encoding="utf-8"))
    common = dict(cfg["common"])
    for key in ("campaign_layouts", "curriculum_track_actual_level"):
        if common.get(key) == "True":
            common[key] = True
    common["build"] = json.loads(SPECIALISTS.read_text(encoding="utf-8"))["build"]
    return common


def collect(env, teacher, student, level, steps, beta, rng):
    """한 단계에서 steps번 결정하며 (상태, 선생님 행동)을 모은다.
    방마다 이번 에피소드를 선생님이 플레이할 확률이 beta다 (BC는 항상 1, DAgger는 1회차만 1)."""
    env.set_level(level)
    obs = env.reset()
    by_teacher = rng.random(env.n) < beta
    states, labels, finished = [], [], 0
    for _ in range(steps):
        expert = teacher.act(obs)
        states.append(obs.copy())
        labels.append(expert)
        actions = np.where(by_teacher, expert, student.act(obs))
        result = env.step(actions)
        obs = result["obs"]
        for slot, _, _ in result["results"]:
            finished += 1
            by_teacher[slot] = rng.random() < beta
    return np.concatenate(states), np.concatenate(labels), finished


def train_student(student, opt, states, labels, epochs, batch, rng):
    x = torch.as_tensor(states, dtype=torch.float32)
    y = torch.as_tensor(labels, dtype=torch.long)
    losses, accs = [], []
    for _ in range(epochs):
        order = torch.as_tensor(rng.permutation(len(x)))
        for start in range(0, len(x), batch):
            idx = order[start:start + batch]
            logits = student.net(x[idx])
            loss = F.cross_entropy(logits, y[idx])     # 11장: 이산 행동의 behavior cloning = cross-entropy
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(loss.item())
            accs.append((logits.argmax(-1) == y[idx]).float().mean().item())
    return float(np.mean(losses[-50:])), float(np.mean(accs[-50:]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--mode", choices=["bc", "dagger"], required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iterations", type=int, default=8)
    ap.add_argument("--steps-per-level", type=int, default=400, help="회차·단계마다 결정 횟수 (× 방 16개)")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--worker", type=int, default=700)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--teachers", type=Path, default=SPECIALISTS, help="단계별 선생님 목록 (select_teachers 결과)")
    args = ap.parse_args()

    tag = "" if args.teachers == SPECIALISTS else "_" + args.teachers.stem.replace("ppo_specialists_", "")
    out = args.out or Path("runs/laser/imitation") / f"{args.mode}{tag}_seed{args.seed}"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    torch.set_num_threads(2)
    common = load_common()
    teacher = StagePolicy(json.loads(args.teachers.read_text(encoding="utf-8"))["models"])
    student = Student(args.hidden, args.seed)
    opt = torch.optim.Adam(student.net.parameters(), lr=1e-3)
    config = {**vars(args), "out": str(out), "teachers": str(args.teachers), "common": common}
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    env = evaluation_env(common, 30_000 + args.seed, args.worker, areas=16)
    check = evaluation_env(common, 40_000 + args.seed, args.worker + 1, areas=10)
    data_x, data_y, log, start = [], [], [], time.time()
    try:
        for it in range(args.iterations):
            beta = 1.0 if (args.mode == "bc" or it == 0) else 0.0
            episodes = 0
            for level in LEVELS:
                x, y, n = collect(env, teacher, student, level, args.steps_per_level, beta, rng)
                data_x.append(x)
                data_y.append(y)
                episodes += n
            states, labels = np.concatenate(data_x), np.concatenate(data_y)
            loss, acc = train_student(student, opt, states, labels, args.epochs, 2048, rng)
            student.steps = len(states)
            scores = evaluate(check, student, LEVELS, 2)
            row = {"iteration": it + 1, "samples": len(states), "episodes_collected": episodes, "loss": loss,
                   "train_accuracy": acc, "minutes": (time.time() - start) / 60,
                   **{f"success_l{lv}": scores[f"success_l{lv}"] for lv in LEVELS}}
            row["success_mean"] = float(np.mean([row[f"success_l{lv}"] for lv in LEVELS]))
            log.append(row)
            print(f"[{args.mode} seed{args.seed}] 회차 {it + 1}: 데이터 {len(states):,} | 일치율 {acc:.2f} | "
                  + " ".join(f"L{lv} {row[f'success_l{lv}']:.2f}" for lv in LEVELS)
                  + f" | 평균 {row['success_mean']:.2f}", flush=True)
            (out / "log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
            student.save(out / "model.pt", config)
    finally:
        env.close()
        check.close()

    final = evaluate_model(student, common, EVAL_SEED + 100 + args.seed, args.worker + 2)
    (out / "final.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    b = final["by_level"]
    print("최종: " + " ".join(f"L{lv} {b[f'success_l{lv}']:.2f}" for lv in LEVELS)
          + f" | 10단계 완주 {final['campaign']['completed']}/{final['campaign']['campaigns']}", flush=True)


if __name__ == "__main__":
    main()
