"""Train matched PPO policies for the level 6 redesign and evaluate on new procedural layouts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import subprocess
import sys

import torch

from algos.common import load_policy
from laser.baseline import RandomPolicy
from laser.env import LaserEnv
from laser.train import evaluate


CONDITIONS = {"legacy": (0, 1), "geometry": (2, 1), "geometry_and_observation": (2, 2)}
SEEDS = (0, 1, 2)


def train_one(run, design, observation, seed, steps, build, worker, initial):
    if (run / "model.pt").is_file():
        config = json.loads((run / "config.json").read_text(encoding="utf-8"))
        common = config["common"]
        if (config.get("finished") and config["seed"] == seed and common["total_steps"] == steps
                and common["level6_design"] == design and common["obs_mode"] == observation
                and Path(common["build"]).resolve() == build
                and config.get("init_policy", {}).get("path") == initial):
            return
        raise ValueError(f"Existing model does not match this experiment: {run}")
    run.mkdir(parents=True, exist_ok=True)
    with (run / "log.txt").open("w", encoding="utf-8") as log:
        init_args = ["--init-policy", initial] if initial else []
        subprocess.run(
            [sys.executable, "-u", "-m", "laser.train", "--algo", "ppo", "--seed", str(seed),
             "--out", str(run), "--worker", str(worker), *init_args, "--set", f"build={json.dumps(str(build))}",
             "level=6", "max_level=6", "eval_levels=[6]", f"total_steps={steps}",
             f"level6_design={design}", f"obs_mode={observation}",
             "eval_interval=100000", "final_rounds=4"],
            stdout=log, stderr=subprocess.STDOUT, check=True,
        )
    print(f"Trained {run.name}", flush=True)


def score(build, design, observation, seed, worker, policy):
    env = LaserEnv(n_areas=10, seed=91_000 + seed, worker_id=worker, level=6,
                   build=build, level6_design=design, obs_mode=observation)
    try:
        return {key.removesuffix("_l6"): value if math.isfinite(value) else None
                for key, value in evaluate(env, policy, [6], 20).items()}
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--root", default=Path("runs/laser/level6_redesign"), type=Path)
    parser.add_argument("--out", default=Path("runs/results/laser/level6_redesign.json"), type=Path)
    parser.add_argument("--steps", default=1_500_000, type=int)
    parser.add_argument("--parallel", default=6, type=int)
    parser.add_argument("--worker", default=2600, type=int)
    parser.add_argument("--init-policy", type=Path)
    parser.add_argument("--speed-comparison", action="store_true",
                        help="compare designs 2 and 3 with the same observation")
    args = parser.parse_args()
    if args.steps <= 0 or args.steps % 16:
        parser.error("--steps must be a positive multiple of 16")
    if args.parallel <= 0:
        parser.error("--parallel must be positive")
    build = args.build.resolve(strict=True)
    initial = str(args.init_policy.resolve(strict=True)) if args.init_policy else None
    torch.set_num_threads(1)
    conditions = {"geometry": (2, 1), "speed_limit": (3, 1)} if args.speed_comparison else CONDITIONS
    jobs = [(name, design, observation, seed) for seed in SEEDS
            for name, (design, observation) in conditions.items()]
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(train_one, args.root / f"{name}_seed{seed}", design, observation, seed,
                               args.steps, build, args.worker + i * 4, initial)
                   for i, (name, design, observation, seed) in enumerate(jobs)]
        for future in futures:
            future.result()
    results = []
    worker = args.worker + len(jobs) * 4
    for name, design, observation, seed in jobs:
        model = args.root / f"{name}_seed{seed}" / "model.pt"
        policy = load_policy(model)
        if policy.kind != "ppo" or policy.steps != args.steps:
            raise ValueError(f"Unexpected policy or step budget: {model}")
        scores = score(build, design, observation, seed, worker, policy)
        print(name, seed, scores, flush=True)
        results.append({"condition": name, "seed": seed, "eval_seed": 91_000 + seed,
                        "design": design, "obs_mode": observation, "model": str(model), **scores})
    if not initial and not args.speed_comparison:
        for seed in SEEDS:
            for design in (0, 2):
                scores = score(build, design, 1, seed, worker, RandomPolicy(92_000 + seed))
                results.append({"condition": f"random_design_{design}", "seed": seed,
                                "eval_seed": 91_000 + seed, "design": design, "obs_mode": 1, **scores})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(".tmp")
    temp.write_text(json.dumps({"steps": args.steps, "episodes_per_seed": 200,
                                "build": str(build), "initial_policy": initial, "runs": results}, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    temp.replace(args.out)


if __name__ == "__main__":
    main()
