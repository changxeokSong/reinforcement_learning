"""레이저 미션 학습. 배구와 같은 PPO·DQN·SAC 구현을 그대로 쓴다.

예)
  .venv-unity\\Scripts\\python -m laser.train --algo ppo --seed 0 --set level=1 total_steps=1000000
  .venv-unity\\Scripts\\python -m laser.train --algo ppo --seed 0 --set level=curriculum

level
  0~4         그 레벨만 학습
  random      에피소드마다 1~4 중 무작위
  curriculum  레벨 0부터 시작해서, 최근 성공률이 기준을 넘으면 다음 레벨로 올린다

결과 (runs/laser/<이름>/)
  config.json, metrics.csv (레벨별 성공률), model.pt
"""
import argparse
import csv
import json
import platform
import time
from pathlib import Path

import numpy as np
import torch

from algos import ALGOS, load_policy, save_policy
from laser.env import LEVEL_INDEX, N_ACTIONS, OBS_DIM, LaserEnv

COMMON = {
    "total_steps": 4_000_000,
    "n_areas": 16,
    "level": "curriculum",
    "shaping": 0.5,             # 금고 쪽으로 다가간 거리에 주는 보조 보상 (출발→금고 전체 합)
    "potential_shaping": False, # γΦ(s')−Φ(s), 종료 상태의 Φ는 0
    "campaign_layouts": False,  # 실제 10단계 캠페인의 배치와 재도전 규칙을 사용한다.
    "time_penalty": 0.01,       # 매 결정(0.1초)마다 빼는 시간 벌점
    "level_mix": 0.0,
    "level_mix_from": 2,
    "level_mix_target": 0,     # 0이면 현재 레벨보다 낮은 레벨 중 무작위
    "max_level": 4,             # 커리큘럼의 마지막 레벨, 레벨 무작위의 최대 레벨 (레벨 5를 넣으려면 5)           # 커리큘럼 복습: 이 확률로 지금보다 낮은 레벨을 낸다
    "obs_mode": 1,              # 1: 설계한 레이저 특징, 0: 원시 선분 좌표
    "build": None,              # Unity 실행 파일 (기본: unity/LaserMission/Build)
    "training_build": None,     # 학습 전용 빌드를 쓸 때 평가 빌드는 build로 지정
    "gap_bonus": 0.0,
    "gap_bonus_steps": 0,
    "curriculum_threshold": 0.8,
    "curriculum_window": 300,
    "curriculum_track_actual_level": False,
    "curriculum_deadlines": [],  # 누적 스텝 상한. 난이도별 승급이 지연돼도 마지막 레벨을 학습한다.
    "eval_interval": 100_000,
    "eval_levels": [1, 2, 3, 4],
    "eval_rounds": 4,           # 학습 중 평가: 레벨마다 (방 수 × rounds)판
    "final_rounds": 20,         # 학습 후 최종 평가: 레벨마다 200판 → final.json
    "eval_areas": 10,
    "time_scale": 100.0,
    "latest_interval": 20_000,  # latest.pt 갱신 주기. laser.watch가 학습 중인 모델을 읽어 간다
    "checkpoint_interval": 500_000,
}
ACTION_TABLE = np.arange(N_ACTIONS)


def parse_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def evaluate(env, policy, levels, rounds):
    """레벨마다 모든 방을 새로 시작해서 각 방의 첫 에피소드 결과만 센다 (짧은 에피소드 편향 방지)."""
    out = {}
    for lv in levels:
        counts = {"success": 0, "hit": 0, "timeout": 0}
        lengths = []
        returns = []
        for _ in range(rounds):
            obs, warmup = env.evaluation_reset(lv)
            done = np.zeros(env.n, dtype=bool)
            episode_return = np.zeros(env.n, dtype=np.float64)
            while not done.all():
                active = ~done & ~warmup
                r = env.evaluation_step(policy.act(obs), warmup)
                episode_return[active] += r["reward"][active]
                for i, kind, length in r["results"]:
                    if not done[i]:
                        done[i] = True
                        counts[kind] += 1
                        returns.append(episode_return[i])
                        if kind == "success":
                            lengths.append(length)
                obs = r["obs"]
        n = sum(counts.values())
        out[f"success_l{lv}"] = counts["success"] / n
        out[f"hit_l{lv}"] = counts["hit"] / n
        out[f"timeout_l{lv}"] = counts["timeout"] / n
        out[f"return_l{lv}"] = float(np.mean(returns))
        out[f"time_l{lv}"] = float(np.mean(lengths)) / 10 if lengths else float("nan")
    return out


def train(algo, seed, overrides, out_dir, worker_id=0, init_policy=None):
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    np.random.seed(seed)
    common = {**COMMON, **{k: v for k, v in overrides.items() if k in COMMON}}
    algo_cfg = {k: v for k, v in overrides.items() if k not in COMMON}
    n, total = common["n_areas"], common["total_steps"]
    deadlines = common["curriculum_deadlines"]
    if deadlines and (common["level"] != "curriculum" or len(deadlines) != common["max_level"]
                      or any(a >= b for a, b in zip([0, *deadlines], [*deadlines, total]))):
        raise ValueError("curriculum_deadlines must increase from 0 to below total_steps, one per promotion")
    gap_bonus, gap_steps = common["gap_bonus"], common["gap_bonus_steps"]
    if gap_bonus and (not common["campaign_layouts"] or not common["training_build"]
                      or not 0 < gap_bonus <= 0.5 or not 0 < gap_steps < total):
        raise ValueError("A gap curriculum needs campaign layouts, a training build and a valid decay budget")
    agent = ALGOS[algo](OBS_DIM, N_ACTIONS, n, total, algo_cfg, seed=seed)
    if init_policy is not None:
        if algo != "ppo":
            raise ValueError("--init-policy is available for PPO actor fine-tuning")
        source = load_policy(init_policy)
        if source.kind != algo or not np.array_equal(source.table, ACTION_TABLE):
            raise ValueError("Initial policy must be a PPO checkpoint with the same action table")
        agent.policy_net().load_state_dict(source.net.state_dict())

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"algo": algo, "seed": seed, "env": "laser", "common": common, "algo_config": agent.cfg,
              "python": platform.python_version(), "torch": torch.__version__,
              "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    if init_policy is not None:
        config["init_policy"] = {"path": str(Path(init_policy).resolve()), "steps": source.steps}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    mode = common["level"]
    level = 0 if mode == "curriculum" else (-1 if mode == "random" else int(mode))
    env_kw = dict(shaping=common["shaping"], time_penalty=common["time_penalty"],
                  obs_mode=common["obs_mode"], time_scale=common["time_scale"],
                  potential_shaping=common["potential_shaping"], shaping_gamma=agent.cfg["gamma"],
                  campaign_layouts=common["campaign_layouts"])
    if common["build"]:
        env_kw["build"] = common["build"]
    train_kw = {**env_kw, "build": common["training_build"]} if common["training_build"] else env_kw
    env = LaserEnv(n_areas=n, seed=seed, worker_id=worker_id, level=level, **train_kw)
    if gap_bonus:
        env.set_param("training_gap_bonus", gap_bonus)
    env.set_param("level_mix", common["level_mix"])
    env.set_param("level_mix_from", common["level_mix_from"])
    env.set_param("level_mix_target", common["level_mix_target"])
    env.set_param("max_level", common["max_level"])
    eval_env = LaserEnv(n_areas=common["eval_areas"], seed=seed + 1000, worker_id=worker_id + 1,
                        level=1, **env_kw)

    metrics = open(out_dir / "metrics.csv", "w", newline="", encoding="utf-8")
    writer = None
    obs = env.reset()
    steps, start, next_eval, next_latest, next_ckpt = 0, time.time(), 0, 0, 0
    next_gap_update = min(gap_steps, 20_000) if gap_bonus else float("inf")
    recent = []                     # (레벨, 결과)
    last_stats = {}

    def log():
        nonlocal writer
        row = {"step": steps, "wall_sec": round(time.time() - start, 1), "train_level": level}
        lv_recent = [k for lv, k in recent if not common["curriculum_track_actual_level"] or lv == level]
        lv_recent = lv_recent[-common["curriculum_window"]:]
        row["train_success"] = round(lv_recent.count("success") / len(lv_recent), 4) if lv_recent else 0.0
        row.update({k: round(v, 4) for k, v in evaluate(eval_env, agent.snapshot(ACTION_TABLE, greedy=True),
                                                        common["eval_levels"], common["eval_rounds"]).items()})
        row.update({k: round(v, 5) for k, v in last_stats.items()})
        if writer is None:
            stat_keys = {"ppo": ["pg_loss", "v_loss", "entropy", "approx_kl", "clip_fraction"],
                         "dqn": ["q_loss", "q_mean", "epsilon"],
                         "sac": ["q_loss", "actor_loss", "entropy", "alpha"]}[algo]
            writer = csv.DictWriter(metrics, fieldnames=list(row) + [k for k in stat_keys if k not in row],
                                    restval="", extrasaction="ignore")
            writer.writeheader()
        writer.writerow(row)
        metrics.flush()
        sps = steps / max(time.time() - start, 1e-9)
        succ = " ".join(f"L{lv} {row[f'success_l{lv}']:.2f}" for lv in common["eval_levels"])
        print(f"[{algo} seed{seed}] step {steps:>9,} | train L{level} {row['train_success']:.2f} | "
              f"eval {succ} | {sps:,.0f} steps/s", flush=True)

    try:
        max_requested_level = max(level, common["max_level"], *common["eval_levels"])
        eval_env.set_level(max_requested_level)
        previous = eval_env.reset(expected_level=max_requested_level)
        if common["campaign_layouts"]:
            spawns = set(previous[:, 0])
            for _ in range(32):
                current = eval_env.reset(expected_level=max_requested_level)
                if np.any(current[:, 0] == previous[:, 0]):
                    raise RuntimeError("Campaign retry repeated the same spawn")
                spawns.update(current[:, 0])
                previous = current
            if len(spawns) != 4:
                raise RuntimeError(f"Expected four campaign spawn positions, found {len(spawns)}")
        while steps < total:
            if steps >= next_gap_update:
                remaining = max(0.0, 1.0 - steps / gap_steps)
                env.set_param("training_gap_bonus", gap_bonus * remaining)
                next_gap_update = min(gap_steps, steps + 20_000) if remaining else float("inf")
            if steps >= next_eval:
                log()
                next_eval += common["eval_interval"]
            if steps >= next_latest:
                save_policy(out_dir / "latest.pt", agent, ACTION_TABLE, config, steps)
                next_latest += common["latest_interval"]
            if steps >= next_ckpt:
                save_policy(out_dir / f"ckpt_{steps:09d}.pt", agent, ACTION_TABLE, config, steps)
                next_ckpt += common["checkpoint_interval"]
            act = agent.act_train(obs)
            out = env.step(act)
            stats = agent.observe(obs, act, out["reward"], out["obs"], out["final_obs"],
                                  out["terminated"], out["truncated"])
            if stats:
                last_stats = stats
            obs = out["obs"]
            steps += n
            for slot, kind, _ in out["results"]:
                episode_level = level
                if common["curriculum_track_actual_level"]:
                    episode_level = round(float(out["final_obs"][slot, LEVEL_INDEX]) * 4)
                recent.append((episode_level, kind))
            if len(recent) > 5000:
                del recent[:2500]
            if mode == "curriculum" and level < common["max_level"]:
                window = [k for lv, k in recent if lv == level][-common["curriculum_window"]:]
                qualified = len(window) >= common["curriculum_window"] and (
                    window.count("success") / len(window) >= common["curriculum_threshold"]
                )
                deadline_reached = bool(deadlines) and steps >= deadlines[level]
                if qualified or deadline_reached:
                    level += 1
                    env.set_level(level)
                    reason = ", 단계별 스텝 한도" if not qualified else ""
                    print(f"  → 레벨 {level}로 올림 (step {steps:,}{reason})", flush=True)
        log()
        final = evaluate(eval_env, agent.snapshot(ACTION_TABLE, greedy=True),
                         list(range(common["max_level"] + 1)), common["final_rounds"])
        final["success_mean"] = float(np.mean([final[f"success_l{lv}"] for lv in [1, 2, 3, 4]]))
        final["success_mean_all"] = float(np.mean([final[f"success_l{lv}"]
                                                   for lv in range(1, common["max_level"] + 1)]))
        final["success_worst_all"] = min(final[f"success_l{lv}"] for lv in range(1, common["max_level"] + 1))
        (out_dir / "final.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
        print("최종 평가: " + " ".join(f"L{lv} {final[f'success_l{lv}']:.2f}" for lv in range(common["max_level"] + 1)), flush=True)
    finally:
        metrics.close()
        env.close()
        eval_env.close()
    save_policy(out_dir / "model.pt", agent, ACTION_TABLE, config, steps)
    save_policy(out_dir / "latest.pt", agent, ACTION_TABLE, config, steps)
    config["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    config["wall_sec"] = round(time.time() - start, 1)
    config["verified_eval_levels"] = list(range(common["max_level"] + 1))
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--algo", required=True, choices=sorted(ALGOS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--worker", type=int, default=0, help="Unity 통신 포트 번호 (동시에 돌릴 때 서로 다르게, 2씩 띄워서)")
    ap.add_argument("--init-policy", type=Path, help="PPO actor의 초기 가중치로 읽을 체크포인트")
    ap.add_argument("--set", nargs="*", default=[], metavar="KEY=VALUE")
    args = ap.parse_args()
    overrides = {}
    for item in args.set:
        k, _, v = item.partition("=")
        overrides[k] = parse_value(v)
    train(args.algo, args.seed, overrides, args.out or f"runs/laser/{args.algo}_seed{args.seed}",
          args.worker, init_policy=args.init_policy)


if __name__ == "__main__":
    main()
