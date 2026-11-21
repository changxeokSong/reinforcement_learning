"""Evaluate a stage 6 specialist and the original DAgger controller on new campaigns."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.campaign_eval import EPISODE_ATTEMPTS, LEVELS, ROUNDS, evaluate_campaign
from laser.env import LEVEL_INDEX, LaserEnv


class StageSixPolicy:
    def __init__(self, generalist, specialist):
        self.generalist = generalist
        self.specialist = specialist

    def act(self, obs, *, action_mask=None):
        stage_six = np.rint(obs[:, LEVEL_INDEX] * 4) == 6
        if stage_six.all():
            return self.specialist.act(obs, action_mask=action_mask)
        actions = self.generalist.act(obs, action_mask=action_mask)
        if stage_six.any():
            mask = None if action_mask is None else action_mask[stage_six]
            actions[stage_six] = self.specialist.act(obs[stage_six], action_mask=mask)
        return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("runs/level6_release/LaserMission.exe"))
    parser.add_argument("--root", type=Path, default=Path("runs/laser"))
    parser.add_argument("--out", type=Path, default=Path("runs/results/laser/level6_policy_integration.json"))
    parser.add_argument("--worker", type=int, default=2830)
    args = parser.parse_args()
    torch.set_num_threads(1)
    records = []
    build = args.build.resolve(strict=True)
    for seed in range(3):
        teacher_path = args.root / "level6_speed_warm" / f"geometry_seed{seed}" / "model.pt"
        student_path = args.root / "imitation" / f"dagger_rand_h512_long_seed{seed}" / "model.pt"
        generalist = load_policy(student_path)
        specialist = load_policy(teacher_path)
        for name, design, policy in (
            ("dagger", 2, generalist),
            ("stage6_ppo", 2, StageSixPolicy(generalist, specialist)),
            ("dagger_speed", 3, generalist),
        ):
            eval_seed = 93_500 + seed
            env = LaserEnv(n_areas=10, seed=eval_seed, worker_id=args.worker, level=1, build=build,
                           obs_mode=1, level6_design=design)
            try:
                score = evaluate_campaign(env, policy, LEVELS, ROUNDS, EPISODE_ATTEMPTS)
            finally:
                env.close()
            records.append({"policy": name, "design": design, "seed": seed, "eval_seed": eval_seed,
                            "student": str(student_path),
                            "specialist": str(teacher_path) if name == "stage6_ppo" else None, **score})
            print(name, seed, score["completed"], score["campaigns"], flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(".tmp")
    temp.write_text(json.dumps({"attempts_per_stage": EPISODE_ATTEMPTS, "runs": records}, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(args.out)


if __name__ == "__main__":
    main()
