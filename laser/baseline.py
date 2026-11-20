"""27개 이산 행동의 균등 무작위 정책을 레벨별로 평가한다."""
import argparse
import json
from pathlib import Path

import numpy as np

from laser.env import DEFAULT_BUILD, N_ACTIONS, LaserEnv
from laser.train import evaluate


class RandomPolicy:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)

    def act(self, obs):
        return self.rng.integers(N_ACTIONS, size=len(obs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", default=DEFAULT_BUILD, type=Path)
    parser.add_argument("--out", default=Path("runs/results/laser/random_baseline.json"), type=Path)
    parser.add_argument("--worker", default=990, type=int)
    args = parser.parse_args()

    levels = [1, 2, 3, 4, 5]
    areas, rounds = 10, 20
    runs = []
    for seed in (1000, 1001, 1002):
        env = LaserEnv(n_areas=areas, seed=seed, worker_id=args.worker, level=1, build=args.build)
        try:
            metrics = evaluate(env, RandomPolicy(seed), levels, rounds)
            runs.append({"seed": seed, **{key: value if np.isfinite(value) else None
                                         for key, value in metrics.items()}})
        finally:
            env.close()

    result = {"build": str(args.build), "episodes_per_level_per_seed": areas * rounds, "runs": runs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
