"""학습 실행 스크립트. 세 알고리즘이 같은 학습 루프, 같은 상대, 같은 평가를 쓴다.

예)
  python train.py --algo ppo --seed 0
  python train.py --algo sac --seed 1 --set action_set=basic total_steps=1000000
  python train.py --algo ppo --seed 0 --set ent_coef=0.03 --out runs/e3/ppo_ent0.03_seed0

결과는 runs/<이름>/ 에 저장된다.
  config.json   설정, seed, 코드 버전
  metrics.csv   평가 시점별 승률과 학습 통계
  model.pt      최종 정책
"""
import argparse
import csv
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

from algos import ALGOS, save_policy
from volleyball import ACTION_SETS, OBS_DIM, VecVolley
from volleyball.bots import make_bot
from volleyball.evaluate import play_points

# 모든 알고리즘에 똑같이 적용되는 설정
COMMON = {
    "total_steps": 3_000_000,
    "n_envs": 16,
    "action_set": "full",        # "full"(18개) 또는 "basic"(6개)
    "shaping": 0.0,              # 공을 넘길 때 주는 보조 보상
    # 학습 상대 비율: 과거의 자기 자신(self-play)과 봇을 섞는다
    "opp_self": 0.6,
    "opp_easy": 0.2,
    "opp_random": 0.2,
    "opp_hard": 0.0,             # 어려움 봇은 평가 전용 기준이라 학습에는 쓰지 않는다
    "snapshot_interval": 100_000,
    "pool_size": 20,
    "eval_interval": 100_000,
    "eval_points": 200,
    "checkpoint_interval": 500_000,
    "latest_interval": 20_000,   # latest.pt 갱신 주기. watch.py가 학습 중인 모델을 읽어 간다
}
EVAL_OPPONENTS = ("random", "easy", "hard")


class OpponentPool:
    """학습 상대를 관리한다. 환경마다 상대가 다를 수 있고, 에피소드가 끝날 때 다시 뽑는다."""

    def __init__(self, cfg, n_envs, seed):
        self.rng = np.random.default_rng(seed)
        self.kinds = ["self", "easy", "random", "hard"]
        w = np.array([cfg[f"opp_{k}"] for k in self.kinds], dtype=float)
        self.probs = w / w.sum()
        self.bots = {k: make_bot(k, seed + i) for i, k in enumerate(("easy", "random", "hard"))}
        self.snapshots = []
        self.pool_size = cfg["pool_size"]
        self.assigned = [None] * n_envs

    def add_snapshot(self, policy):
        self.snapshots.append(policy)
        if len(self.snapshots) > self.pool_size:
            # 가장 오래된 것 하나는 남겨 두고(초기 실력 유지), 그다음 오래된 것을 버린다
            self.snapshots.pop(1)

    def sample(self):
        kind = self.kinds[self.rng.choice(len(self.kinds), p=self.probs)]
        if kind != "self":
            return self.bots[kind]
        # 절반은 최신 버전, 절반은 과거 버전 중 무작위
        if self.rng.random() < 0.5:
            return self.snapshots[-1]
        return self.snapshots[self.rng.integers(len(self.snapshots))]

    def assign_all(self):
        self.assigned = [self.sample() for _ in self.assigned]

    def act(self, obs_opp):
        """상대별로 환경을 묶어서 한 번에 행동을 계산한다."""
        actions = np.zeros(len(obs_opp), dtype=np.int64)
        groups = {}
        for i, opp in enumerate(self.assigned):
            groups.setdefault(id(opp), (opp, []))[1].append(i)
        for opp, idx in groups.values():
            actions[idx] = opp.act(obs_opp[idx])
        return actions


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def parse_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def train(algo, seed, overrides, out_dir, quiet=False):
    torch.set_num_threads(1)     # seed 여러 개를 동시에 돌릴 때 서로 CPU를 뺏지 않게 한다
    torch.manual_seed(seed)
    np.random.seed(seed)

    common = {**COMMON, **{k: v for k, v in overrides.items() if k in COMMON}}
    algo_cfg = {k: v for k, v in overrides.items() if k not in COMMON}
    unknown = set(algo_cfg) - set(_algo_defaults(algo))
    if unknown:
        raise SystemExit(f"알 수 없는 설정: {sorted(unknown)}")

    action_table = np.array(ACTION_SETS[common["action_set"]])
    n_envs, total = common["n_envs"], common["total_steps"]
    agent = ALGOS[algo](OBS_DIM, len(action_table), n_envs, total, algo_cfg, seed=seed)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "algo": algo, "seed": seed, "common": common, "algo_config": agent.cfg,
        "git_commit": git_commit(), "python": platform.python_version(),
        "torch": torch.__version__, "cpu": platform.processor(),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False),
                                         encoding="utf-8")

    vec = VecVolley(n_envs, seed=seed, shaping=common["shaping"])
    pool = OpponentPool(common, n_envs, seed)
    pool.add_snapshot(agent.snapshot(action_table))
    pool.assign_all()
    eval_bots = {k: make_bot(k, seed=999) for k in EVAL_OPPONENTS}

    metrics_file = open(out_dir / "metrics.csv", "w", newline="", encoding="utf-8")
    writer = None
    obs, obs_opp = vec.reset()
    steps, start = 0, time.time()
    next_eval = next_snap = next_ckpt = next_latest = 0
    recent_results = []          # 최근 학습 에피소드 결과 (+1/0/-1)
    last_stats = {}

    def evaluate_and_log():
        nonlocal writer
        player = agent.snapshot(action_table, greedy=True)
        row = {"step": steps, "wall_sec": round(time.time() - start, 1)}
        for name, bot in eval_bots.items():
            r = play_points(player, bot, common["eval_points"])
            row[f"wr_{name}"] = round(r["win_rate"], 4)
            if name == "hard":
                row.update(rally_sec=round(r["rally_sec"], 2), spikes=round(r["spikes"], 3),
                           dives=round(r["dives"], 3), touches=round(r["touches"], 3))
        row["train_result"] = round(float(np.mean(recent_results[-500:])), 4) if recent_results else 0.0
        row.update({k: round(v, 5) for k, v in last_stats.items()})
        if writer is None:
            fields = list(row) + [k for k in _stat_keys(algo) if k not in row]
            writer = csv.DictWriter(metrics_file, fieldnames=fields, restval="")
            writer.writeheader()
        writer.writerow(row)
        metrics_file.flush()
        if not quiet:
            sps = steps / max(time.time() - start, 1e-9)
            print(f"[{algo} seed{seed}] step {steps:>9,} | random {row['wr_random']:.2f} "
                  f"easy {row['wr_easy']:.2f} hard {row['wr_hard']:.2f} | "
                  f"spikes {row['spikes']:.2f} dives {row['dives']:.2f} | {sps:,.0f} steps/s",
                  flush=True)

    while steps < total:
        if steps >= next_eval:
            evaluate_and_log()
            next_eval += common["eval_interval"]
        if steps >= next_snap and steps > 0:
            pool.add_snapshot(agent.snapshot(action_table))
            next_snap += common["snapshot_interval"]
        elif steps == 0:
            next_snap = common["snapshot_interval"]
        if steps >= next_ckpt:
            # 학습 전(0 스텝) 모델도 저장해 둔다. 학습 과정 영상에 쓴다
            save_policy(out_dir / f"ckpt_{steps:09d}.pt", agent, action_table, config, steps)
            next_ckpt += common["checkpoint_interval"]
        if steps >= next_latest:
            save_policy(out_dir / "latest.pt", agent, action_table, config, steps)
            next_latest += common["latest_interval"]

        act = agent.act_train(obs)
        out = vec.step(action_table[act], pool.act(obs_opp))
        stats = agent.observe(obs, act, out["reward"], out["obs"], out["final_obs"],
                              out["terminated"], out["truncated"])
        if stats:
            last_stats = stats
        obs, obs_opp = out["obs"], out["obs_opp"]
        steps += n_envs
        for i, winner, _ in out["stats"]:
            recent_results.append(winner)
            pool.assigned[i] = pool.sample()
        if len(recent_results) > 5000:
            del recent_results[:2500]

    evaluate_and_log()
    metrics_file.close()
    save_policy(out_dir / "model.pt", agent, action_table, config, steps)
    save_policy(out_dir / "latest.pt", agent, action_table, config, steps)
    config["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    config["wall_sec"] = round(time.time() - start, 1)
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    return out_dir


def _algo_defaults(algo):
    import importlib
    return importlib.import_module(f"algos.{algo}").DEFAULTS


def _stat_keys(algo):
    return {"ppo": ["pg_loss", "v_loss", "entropy", "approx_kl", "clip_fraction"],
            "dqn": ["q_loss", "q_mean", "epsilon"],
            "sac": ["q_loss", "actor_loss", "entropy", "alpha"]}[algo]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--algo", required=True, choices=sorted(ALGOS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="결과 폴더 (기본: runs/<algo>_seed<seed>)")
    ap.add_argument("--set", nargs="*", default=[], metavar="KEY=VALUE",
                    help="설정 덮어쓰기. 예: --set total_steps=1000000 lr=1e-4")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        overrides[key] = parse_value(value)
    out = args.out or f"runs/{args.algo}_seed{args.seed}"
    train(args.algo, args.seed, overrides, out, args.quiet)


if __name__ == "__main__":
    main()
