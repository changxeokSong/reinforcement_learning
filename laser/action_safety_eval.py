"""Compare collision prediction and PPO fine-tuning on unseen procedural campaigns."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.campaign_eval import AREAS, EPISODE_ATTEMPTS, LEVELS, ROUNDS, evaluate_campaign
from laser.env import OBS_DIM, TIME_INDEX, LaserEnv
from laser.level6_integration import StageSixPolicy


CONDITIONS = {
    "baseline": (0, (), "level6_speed_warm"),
    "stage6_safety": (2, (6,), "level6_speed_warm"),
    "several_stages_safety": (2, (4, 5, 6, 9, 10), "level6_speed_warm"),
    "refined_ppo": (0, (), "level6_refine"),
    "refined_ppo_safety": (2, (4, 5, 6, 9, 10), "level6_refine"),
    "distilled_safety": (0, (), "level6_distilled_safety"),
    "include_stage7": (2, (4, 5, 6, 7, 9, 10), "level6_speed_warm"),
}
DEFAULT_CONDITIONS = tuple(name for name in CONDITIONS if name not in ("distilled_safety", "include_stage7"))
SEEDS = (0, 1, 2)


def evaluate_stage_six(env, policy, rounds, horizon):
    return evaluate_fresh_episodes(env, policy, 6, rounds, require_mask=bool(horizon))


def evaluate_fresh_episodes(env, policy, level, rounds, *, require_mask=False, classify_start=None,
                            diagnose_failures=False):
    """Score the first consecutive fresh episodes in each room on identical layouts."""
    obs, warmup = env.evaluation_reset(level)
    counts = np.zeros(env.n, dtype=int)
    starts = np.empty((rounds, env.n, OBS_DIM), dtype=np.float32)
    starts[0, ~warmup] = obs[~warmup]
    outcomes = {"success": 0, "hit": 0, "timeout": 0}
    cohorts = {}
    masked_decisions = 0
    failures = []
    previous_masked = np.zeros(env.n, dtype=int)
    while (counts < rounds).any():
        active = counts < rounds
        preparing = warmup.copy()
        mask = env.action_mask
        if diagnose_failures:
            blocked = np.zeros(env.n, dtype=int) if mask is None else mask.sum(axis=1)
        if mask is not None:
            masked_decisions += int(mask[active & ~warmup].any(axis=1).sum())
        actions = policy.act(obs) if mask is None else policy.act(obs, action_mask=mask)
        result = env.evaluation_step(actions, warmup)
        obs = result["obs"]
        fresh = preparing & ~warmup
        starts[0, fresh] = obs[fresh]
        for slot, outcome, length in result["results"]:
            if active[slot]:
                outcomes[outcome] += 1
                if diagnose_failures and outcome != "success":
                    final = result["final_obs"][slot]
                    failures.append({"episode_in_room": int(counts[slot]), "room": int(slot),
                                     "outcome": outcome, "decision": length,
                                     "action": int(actions[slot]), "blocked_actions": int(blocked[slot]),
                                     "previous_blocked_actions": int(previous_masked[slot]),
                                     "start_x": float(starts[counts[slot], slot, 0] * 4),
                                     "x": float(final[0] * 4), "z": float(final[1] * 10),
                                     "seconds": float(final[TIME_INDEX] * 20)})
                if classify_start is not None:
                    cohort = classify_start(starts[counts[slot], slot])
                    tally = cohorts.setdefault(cohort, dict.fromkeys(outcomes, 0))
                    tally[outcome] += 1
                counts[slot] += 1
                if counts[slot] < rounds:
                    starts[counts[slot], slot] = obs[slot]
        if diagnose_failures:
            previous_masked = blocked
            previous_masked[obs[:, TIME_INDEX] == 0] = 0
    if require_mask and not masked_decisions:
        raise RuntimeError(f"Unity did not provide collision masks for stage {level}")
    score = {**outcomes, "episodes": rounds * env.n, "masked_decisions": masked_decisions,
             "start_observations_sha256": hashlib.sha256(starts.tobytes()).hexdigest()}
    if classify_start is not None:
        score["cohorts"] = cohorts
    if diagnose_failures:
        score["failures"] = failures
    return score


def run(args, condition, seed, worker):
    horizon, stages, specialist_group = CONDITIONS[condition]
    run_name = f"geometry_seed{seed}" if specialist_group == "level6_speed_warm" else f"seed{seed}"
    specialist_path = args.root / specialist_group / run_name / "model.pt"
    student_path = args.root / "imitation" / f"dagger_rand_h512_long_seed{seed}" / "model.pt"
    specialist = load_policy(specialist_path)
    generalist = load_policy(student_path)
    env_options = dict(n_areas=AREAS, worker_id=worker, build=args.build, level6_design=2,
                       level6_safety_steps=horizon, safety_levels=stages)
    eval_seed = args.eval_seed + seed
    env = LaserEnv(seed=eval_seed, level=6, **env_options)
    try:
        stage_six = evaluate_stage_six(env, specialist, args.rounds, horizon)
    finally:
        env.close()

    campaign_seed = eval_seed + len(SEEDS)
    env = LaserEnv(seed=campaign_seed, level=1, **env_options)
    try:
        policy = StageSixPolicy(generalist, specialist)
        campaign = evaluate_campaign(env, policy, LEVELS, args.rounds, EPISODE_ATTEMPTS)
    finally:
        env.close()
    print(f"{condition} seed {seed}: L6 {stage_six['success']}/{stage_six['episodes']}; "
          f"campaign {campaign['completed']}/{campaign['campaigns']}", flush=True)
    return {"condition": condition, "train_seed": seed, "stage_six_seed": eval_seed,
            "campaign_seed": campaign_seed, "horizon_steps": horizon, "safety_stages": stages,
            "specialist": str(specialist_path), "student": str(student_path),
            "stage_six": stage_six, "campaign": campaign}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("runs/action_safety_release/LaserMission.exe"))
    parser.add_argument("--root", type=Path, default=Path("runs/laser"))
    parser.add_argument("--out", type=Path, default=Path("runs/results/laser/action_safety.json"))
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS,
                        default=DEFAULT_CONDITIONS)
    parser.add_argument("--eval-seed", type=int, default=98_000)
    parser.add_argument("--rounds", type=int, default=ROUNDS)
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--worker", type=int, default=3200)
    args = parser.parse_args()
    if args.rounds < 1 or args.parallel < 1:
        parser.error("--rounds and --parallel must be positive")
    args.build = args.build.resolve(strict=True)
    torch.set_num_threads(1)
    jobs = [(condition, seed) for condition in args.conditions for seed in SEEDS]
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        tasks = [pool.submit(run, args, condition, seed, args.worker + index)
                 for index, (condition, seed) in enumerate(jobs)]
        results = [task.result() for task in tasks]
    for seed in SEEDS:
        signatures = {result["stage_six"]["start_observations_sha256"] for result in results
                      if result["train_seed"] == seed}
        if len(signatures) != 1:
            raise RuntimeError(f"Stage 6 initial observations differ across conditions for seed {seed}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(".tmp")
    temporary.write_text(json.dumps({"build": str(args.build), "level6_design": 2, "levels": LEVELS,
                                     "attempts_per_stage": EPISODE_ATTEMPTS, "runs": results}, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(args.out)


if __name__ == "__main__":
    main()
