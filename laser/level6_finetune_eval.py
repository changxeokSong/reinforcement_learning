"""Evaluate level-6 PPO fine-tuning on held-out procedural layouts."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import torch

from algos.common import load_policy
from laser.campaign_eval import EPISODE_ATTEMPTS, LEVELS, ROUNDS, evaluate_campaign
from laser.level6_integration import StageSixPolicy
from laser.pure_rl_safety import SEEDS, env_for
from laser.train import evaluate


def score(seed, group, model, build, worker, eval_seed_base, generalist=None):
    policy = load_policy(model, greedy=True)
    eval_seed = eval_seed_base + 10 * seed
    env = env_for(build, eval_seed, worker, safety=False)
    try:
        level6 = evaluate(env, policy, [6], ROUNDS)
    finally:
        env.close()

    env = env_for(build, eval_seed + 1, worker, safety=False)
    try:
        campaign_policy = StageSixPolicy(load_policy(generalist, greedy=True), policy) if generalist else policy
        campaign = evaluate_campaign(env, campaign_policy, LEVELS, ROUNDS, EPISODE_ATTEMPTS)
    finally:
        env.close()
    result = {
        "seed": seed,
        "group": group,
        "steps": policy.steps,
        "level6_eval_seed": eval_seed,
        "campaign_eval_seed": eval_seed + 1,
        "level6": {key: level6[f"{key}_l6"] for key in ("success", "hit", "timeout")},
        "campaign": campaign,
    }
    print(f"{group} seed {seed}: L6 {result['level6']['success']:.1%}, "
          f"campaign {campaign['completed']}/{campaign['campaigns']}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("runs/laser_refactor_release/LaserMission.exe"))
    parser.add_argument("--root", type=Path, default=Path("runs/laser"))
    parser.add_argument("--finetuned-dir", type=Path, default=Path("l6_ppo48_finetune"))
    parser.add_argument("--eval-seed-base", type=int, default=141_000)
    parser.add_argument("--stage6-only", action="store_true",
                        help="use the fine-tuned checkpoint only in level 6")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--parallel", type=int, default=5)
    parser.add_argument("--worker", type=int, default=260)
    args = parser.parse_args()
    filename = "level6_finetune_stage6_only.json" if args.stage6_only else "level6_finetune.json"
    out = args.out or Path("runs/results/laser") / filename
    build = str(args.build.resolve(strict=True))
    torch.set_num_threads(1)

    jobs = []
    for seed in SEEDS:
        baseline = (args.root / "long2" / f"ppo_tuned_48m_seed{seed}" / "model.pt").resolve(strict=True)
        finetuned = (args.root / args.finetuned_dir / f"seed{seed}" / "model.pt").resolve(strict=True)
        if args.stage6_only:
            jobs.append((seed, "stage6_only", finetuned, build, args.worker + 4 * len(jobs),
                         args.eval_seed_base, baseline))
        else:
            jobs.append((seed, "baseline", baseline, build, args.worker + 4 * len(jobs), args.eval_seed_base))
            jobs.append((seed, "finetuned", finetuned, build, args.worker + 4 * len(jobs), args.eval_seed_base))
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(score, *job) for job in jobs]
        results = [future.result() for future in futures]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"build": build, "runs": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
