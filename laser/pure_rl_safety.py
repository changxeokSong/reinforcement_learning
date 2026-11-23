"""순수 강화학습 정책 하나에 실행 시 충돌 예측을 붙이면 얼마나 오르는가.

모방 학습 정책(59.7% → 99.8%)과 같은 조건으로, 튜닝한 PPO·SAC 정책 하나를 평가한다.
- 단계별 성공률: 단계마다 200판, 한 번 시도
- 순차 캠페인: 1~10단계, 단계당 최대 3번 시도, 200회
충돌 예측은 0.2초(2결정), 적용 단계는 최종 캠페인과 같은 4·5·6·7·9·10단계, 6단계는 통로 설계 2.

  .venv-unity\\Scripts\\python -m laser.pure_rl_safety --parallel 6
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.campaign_eval import AREAS, EPISODE_ATTEMPTS, LEVELS, ROUNDS, evaluate_campaign
from laser.env import LaserEnv
from laser.train import evaluate

SAFETY_STAGES = (4, 5, 6, 7, 9, 10)
GROUPS = {"ppo_48m": "long2/ppo_tuned_48m", "sac_4m": "long2/sac_tuned_4m", "ppo_16m": "confirm/ppo_tuned_16m"}
SEEDS = [3, 4, 5, 6, 7]
EVAL_SEED = 130_000


def env_for(build, seed, worker, safety):
    return LaserEnv(n_areas=AREAS, seed=seed, worker_id=worker, level=1, build=build, level6_design=2,
                    level6_safety_steps=2 if safety else 0, safety_levels=SAFETY_STAGES if safety else (6,))


def score(group, seed, root, build, worker, safety):
    policy = load_policy(root / f"{GROUPS[group]}_seed{seed}" / "model.pt", greedy=True)
    env_seed = EVAL_SEED + 10 * seed
    env = env_for(build, env_seed, worker, safety)
    try:
        by_level = evaluate(env, policy, LEVELS, ROUNDS)
    finally:
        env.close()
    env = env_for(build, env_seed + 1, worker, safety)
    try:
        campaign = evaluate_campaign(env, policy, LEVELS, ROUNDS, EPISODE_ATTEMPTS)
    finally:
        env.close()
    by_level = {k: (v if np.isfinite(v) else None) for k, v in by_level.items()}
    mean = float(np.mean([by_level[f"success_l{i}"] for i in LEVELS]))
    print(f"{group} seed {seed} safety={safety}: 평균 {100 * mean:.1f}%, 완주 {campaign['completed']}/{campaign['campaigns']}",
          flush=True)
    return {"group": group, "seed": seed, "safety": safety, "env_seed": env_seed, "mean": mean,
            "by_level": by_level, "campaign": campaign}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("runs/laser"))
    ap.add_argument("--build", type=Path, default=Path("runs/laser_refactor_release/LaserMission.exe"))
    ap.add_argument("--groups", nargs="+", default=list(GROUPS), choices=list(GROUPS))
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--worker", type=int, default=1500)
    ap.add_argument("--out", type=Path, default=Path("runs/results/laser/pure_rl_safety.json"))
    args = ap.parse_args()
    torch.set_num_threads(1)
    build = str(args.build.resolve())
    jobs = [(g, s, safety) for g in args.groups for s in SEEDS for safety in (False, True)]
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(score, g, s, args.root, build, args.worker + 4 * i, safety)
                   for i, (g, s, safety) in enumerate(jobs)]
        results = [f.result() for f in futures]
    old = json.loads(args.out.read_text(encoding="utf-8"))["runs"] if args.out.is_file() else []
    keep = [r for r in old if r["group"] not in args.groups]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"build": build, "safety_stages": SAFETY_STAGES, "horizon_steps": 2,
                                    "episodes_per_level": AREAS * ROUNDS, "attempts_per_level": EPISODE_ATTEMPTS,
                                    "runs": keep + results}, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
