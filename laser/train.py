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

from algos import ALGOS, save_policy
from laser.env import N_ACTIONS, OBS_DIM, LaserEnv

COMMON = {
    "total_steps": 4_000_000,
    "n_areas": 16,
    "level": "curriculum",
    "shaping": 0.5,             # 금고 쪽으로 다가간 거리에 주는 보조 보상 (출발→금고 전체 합)
    "time_penalty": 0.01,       # 매 결정(0.1초)마다 빼는 시간 벌점
    "obs_mode": 1,              # 1: 설계한 레이저 특징, 0: 원시 선분 좌표
    "build": None,              # Unity 실행 파일 (기본: unity/LaserMission/Build)
    "curriculum_threshold": 0.8,
    "curriculum_window": 300,
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
        env.set_level(lv)
        counts = {"success": 0, "hit": 0, "timeout": 0}
        lengths = []
        for _ in range(rounds):
            obs = env.reset()
            done = np.zeros(env.n, dtype=bool)
            while not done.all():
                r = env.step(policy.act(obs))
                for i, kind, length in r["results"]:
                    if not done[i]:
                        done[i] = True
                        counts[kind] += 1
                        if kind == "success":
                            lengths.append(length)
                obs = r["obs"]
        n = sum(counts.values())
        out[f"success_l{lv}"] = counts["success"] / n
        out[f"hit_l{lv}"] = counts["hit"] / n
        out[f"time_l{lv}"] = float(np.mean(lengths)) / 10 if lengths else float("nan")
    return out


def train(algo, seed, overrides, out_dir, worker_id=0):
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    np.random.seed(seed)
    common = {**COMMON, **{k: v for k, v in overrides.items() if k in COMMON}}
    algo_cfg = {k: v for k, v in overrides.items() if k not in COMMON}
    n, total = common["n_areas"], common["total_steps"]
    agent = ALGOS[algo](OBS_DIM, N_ACTIONS, n, total, algo_cfg, seed=seed)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"algo": algo, "seed": seed, "env": "laser", "common": common, "algo_config": agent.cfg,
              "python": platform.python_version(), "torch": torch.__version__,
              "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    mode = common["level"]
    level = 0 if mode == "curriculum" else (-1 if mode == "random" else int(mode))
    env_kw = dict(shaping=common["shaping"], time_penalty=common["time_penalty"],
                  obs_mode=common["obs_mode"], time_scale=common["time_scale"])
    if common["build"]:
        env_kw["build"] = common["build"]
    env = LaserEnv(n_areas=n, seed=seed, worker_id=worker_id, level=level, **env_kw)
    eval_env = LaserEnv(n_areas=common["eval_areas"], seed=seed + 1000, worker_id=worker_id + 1,
                        level=1, **env_kw)

    metrics = open(out_dir / "metrics.csv", "w", newline="", encoding="utf-8")
    writer = None
    obs = env.reset()
    steps, start, next_eval, next_latest, next_ckpt = 0, time.time(), 0, 0, 0
    recent = []                     # (레벨, 결과)
    last_stats = {}

    def log():
        nonlocal writer
        row = {"step": steps, "wall_sec": round(time.time() - start, 1), "train_level": level}
        lv_recent = [k for lv, k in recent[-common["curriculum_window"]:]]
        row["train_success"] = round(lv_recent.count("success") / len(lv_recent), 4) if lv_recent else 0.0
        row.update({k: round(v, 4) for k, v in evaluate(eval_env, agent.snapshot(ACTION_TABLE, greedy=True),
                                                        common["eval_levels"], common["eval_rounds"]).items()})
        row.update({k: round(v, 5) for k, v in last_stats.items()})
        if writer is None:
            stat_keys = {"ppo": ["pg_loss", "v_loss", "entropy", "approx_kl"],
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
        while steps < total:
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
            for _, kind, _ in out["results"]:
                recent.append((level, kind))
            if len(recent) > 5000:
                del recent[:2500]
            if mode == "curriculum" and level < 4:
                window = [k for lv, k in recent if lv == level][-common["curriculum_window"]:]
                if len(window) >= common["curriculum_window"] and \
                        window.count("success") / len(window) >= common["curriculum_threshold"]:
                    level += 1
                    env.set_level(level)
                    print(f"  → 레벨 {level}로 올림 (step {steps:,})", flush=True)
        log()
        final = evaluate(eval_env, agent.snapshot(ACTION_TABLE, greedy=True),
                         [0, 1, 2, 3, 4], common["final_rounds"])
        final["success_mean"] = float(np.mean([final[f"success_l{lv}"] for lv in [1, 2, 3, 4]]))
        (out_dir / "final.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
        print("최종 평가: " + " ".join(f"L{lv} {final[f'success_l{lv}']:.2f}" for lv in range(5)), flush=True)
    finally:
        metrics.close()
        env.close()
        eval_env.close()
    save_policy(out_dir / "model.pt", agent, ACTION_TABLE, config, steps)
    save_policy(out_dir / "latest.pt", agent, ACTION_TABLE, config, steps)
    config["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    config["wall_sec"] = round(time.time() - start, 1)
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--algo", required=True, choices=sorted(ALGOS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--worker", type=int, default=0, help="Unity 통신 포트 번호 (동시에 돌릴 때 서로 다르게, 2씩 띄워서)")
    ap.add_argument("--set", nargs="*", default=[], metavar="KEY=VALUE")
    args = ap.parse_args()
    overrides = {}
    for item in args.set:
        k, _, v = item.partition("=")
        overrides[k] = parse_value(v)
    train(args.algo, args.seed, overrides, args.out or f"runs/laser/{args.algo}_seed{args.seed}", args.worker)


if __name__ == "__main__":
    main()
