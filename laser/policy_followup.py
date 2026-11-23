"""Evaluate policy and collision prediction changes on fresh layouts."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from time import perf_counter

import torch

from algos.common import load_policy
from laser.action_safety_eval import evaluate_fresh_episodes
from laser.campaign_eval import AREAS, EPISODE_ATTEMPTS, LEVELS, ROUNDS, evaluate_campaign
from laser.env import LaserEnv
from laser.level6_integration import StageSixPolicy
from laser.retrain_campaign import SAFETY_STAGES, models


def classify_level_one(obs):
    # Height fields for the first and second bar, normalized by 1.5.
    return "low_beam" if min(obs[16], obs[27]) < 0.5 else "two_high_beams"


def evaluate_entropy(args, seed, worker):
    previous = args.root / "refactor_curriculum" / f"ppo_seed{seed}" / "model.pt"
    paths = [("original", previous)]
    control_settings = None
    for variant, coefficient in (("control", 0.01), ("more_entropy", 0.04)):
        run = args.root / "level1_entropy" / f"{variant}_seed{seed}"
        config = json.loads((run / "config.json").read_text(encoding="utf-8"))
        common = config["common"]
        algorithm = dict(config["algo_config"])
        entropy = algorithm.pop("ent_coef")
        if (not config.get("finished") or config["seed"] != seed or config["algo"] != "ppo"
            or common["level"] != 1 or common["total_steps"] != 262_144
            or entropy != coefficient
            or Path(config["init_policy"]["path"]).resolve() != previous.resolve()
            or Path(common["build"]).resolve() != args.build):
            raise ValueError(f"Training run differs from the entropy ablation settings: {run}")
        settings = (common, algorithm)
        if control_settings is None:
            control_settings = settings
        elif settings != control_settings:
            raise ValueError(f"Entropy must be the only training setting that differs: {run}")
        paths.append((variant, run / "model.pt"))
    reports = []
    for condition, path in paths:
        env = LaserEnv(n_areas=AREAS, level=1, seed=115_000 + seed, worker_id=worker, build=args.build)
        try:
            result = evaluate_fresh_episodes(env, load_policy(path), 1, args.rounds,
                                             classify_start=classify_level_one)
        finally:
            env.close()
        print(condition, seed, result["success"], result["episodes"], flush=True)
        reports.append({"condition": condition, "seed": seed, "model": str(path), "stage": result})
    return reports


def evaluate_horizon(args, seed, worker):
    conditions = [(horizon, SAFETY_STAGES, horizon) for horizon in (2, 3)]
    return evaluate_safety(args, seed, worker, 6, 115_100, conditions)


def evaluate_stage3(args, seed, worker):
    conditions = [("baseline", SAFETY_STAGES, None),
                  ("predict_stage3", (3, *SAFETY_STAGES), None)]
    return evaluate_safety(args, seed, worker, 3, 116_000, conditions)


def evaluate_safety(args, seed, worker, level, seed_base, conditions):
    student_path, specialist_path = models(args.root, seed, "both_retrained")
    student, specialist = load_policy(student_path), load_policy(specialist_path)
    campaign_policy = StageSixPolicy(student, specialist)
    stage_policy = specialist if level == 6 else student
    reports = []
    for condition, safety_stages, stage6_horizon in conditions:
        options = dict(n_areas=AREAS, worker_id=worker, build=args.build, level6_design=2,
                       level6_safety_steps=2, safety_levels=safety_stages, stage6_safety_horizon=stage6_horizon)
        env = LaserEnv(level=level, seed=seed_base + seed, **options)
        started = perf_counter()
        try:
            result = evaluate_fresh_episodes(env, stage_policy, level, args.rounds, require_mask=level in safety_stages)
        finally:
            env.close()
        seconds = perf_counter() - started
        env = LaserEnv(level=1, seed=seed_base + 100 + seed, **options)
        try:
            campaign = evaluate_campaign(env, campaign_policy, LEVELS, args.rounds, args.campaign_attempts)
        finally:
            env.close()
        print(f"{condition} seed {seed}: L{level} {result['success']}/{result['episodes']}; "
              f"campaign {campaign['completed']}/{campaign['campaigns']}", flush=True)
        reports.append({"condition": condition, "seed": seed, "stage_number": level,
                        "stage": result, "stage_seconds": seconds,
                        "campaign": campaign})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    studies = {"entropy": evaluate_entropy, "horizon": evaluate_horizon, "stage3": evaluate_stage3}
    parser.add_argument("study", choices=studies)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path("runs/laser"))
    parser.add_argument("--worker", type=int, default=4000)
    parser.add_argument("--rounds", type=int, default=ROUNDS)
    parser.add_argument("--campaign-attempts", type=int, choices=range(1, EPISODE_ATTEMPTS + 1))
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    if args.campaign_attempts is not None and args.study == "entropy":
        parser.error("--campaign-attempts applies to campaign studies")
    args.campaign_attempts = args.campaign_attempts or EPISODE_ATTEMPTS
    args.build = args.build.resolve(strict=True)
    torch.set_num_threads(1)
    evaluate = studies[args.study]
    runs = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(evaluate, args, seed, args.worker + seed) for seed in range(3)]
        for future in futures:
            scores = future.result()
            if len({row["stage"]["start_observations_sha256"] for row in scores}) != 1:
                raise RuntimeError("Evaluation layouts differed between conditions")
            runs.extend(scores)
    suffix = "" if args.campaign_attempts == EPISODE_ATTEMPTS else f"_attempts{args.campaign_attempts}"
    out = Path("runs/results/laser") / f"policy_followup_{args.study}{suffix}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(".tmp")
    report = {"build": str(args.build), "study": args.study, "runs": runs}
    if args.study != "entropy":
        report["campaign_attempts_per_stage"] = args.campaign_attempts
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(out)


if __name__ == "__main__":
    main()
