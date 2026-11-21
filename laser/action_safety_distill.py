"""Teach a stage 6 policy from collision-checked PPO actions and deploy it without the mask."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.action_safety_eval import evaluate_stage_six
from laser.env import LaserEnv
from laser.imitation import Student, collect, train_student


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=range(3), required=True)
    parser.add_argument("--worker", type=int, required=True)
    parser.add_argument("--build", type=Path, default=Path("runs/action_safety_release/LaserMission.exe"))
    parser.add_argument("--root", type=Path, default=Path("runs/laser"))
    args = parser.parse_args()
    seed = args.seed
    build = args.build.resolve(strict=True)
    teacher_path = args.root / "level6_speed_warm" / f"geometry_seed{seed}" / "model.pt"
    initial = args.root / "imitation" / f"dagger_rand_h512_long_seed{seed}" / "model.pt"
    out = args.root / "level6_distilled_safety" / f"seed{seed}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "model.pt").exists():
        raise FileExistsError(f"Move the previous trained policy before rerunning {out}")

    torch.set_num_threads(1)
    rng = np.random.default_rng(seed)
    teacher = load_policy(teacher_path)
    student = Student(512, seed)
    student.net.load_state_dict(load_policy(initial).net.state_dict())
    optimiser = torch.optim.Adam(student.net.parameters(), lr=3e-4)
    config = {"mode": "dagger", "seed": seed, "level": 6, "teacher": str(teacher_path),
              "initial": str(initial), "common": {"build": str(build), "level6_design": 2},
              "collection_seed": 97_000 + seed, "validation_seed": 97_100 + seed,
              "steps_per_iteration": 600, "iterations": 10}
    histories, states, labels = [], [], []
    best_successes = -1
    env = LaserEnv(n_areas=16, seed=config["collection_seed"], worker_id=args.worker, level=6,
                   build=build, level6_design=2, level6_safety_steps=2)
    try:
        for iteration in range(config["iterations"]):
            x, y, _ = collect(env, teacher, student, 6, config["steps_per_iteration"], 0.6 ** iteration, rng)
            states.append(x)
            labels.append(y)
            loss, accuracy = train_student(student, optimiser, np.concatenate(states), np.concatenate(labels),
                                           epochs=4, batch=1024, rng=rng)
            validation = LaserEnv(n_areas=10, seed=config["validation_seed"], worker_id=args.worker + 1, level=6,
                                  build=build, level6_design=2)
            try:
                score = evaluate_stage_six(validation, student, 10, 0)
            finally:
                validation.close()
            student.steps += len(x)
            histories.append({"iteration": iteration + 1, "samples": student.steps, "loss": loss,
                              "accuracy": accuracy, "validation": score})
            print(f"seed {seed}, iteration {iteration + 1}: {score['success']}/{score['episodes']} "
                  f"unassisted clears, action agreement {accuracy:.1%}", flush=True)
            if score["success"] > best_successes:
                best_successes = score["success"]
                student.save(out / "best.pt", {**config, "selected_iteration": iteration + 1})
    finally:
        env.close()
    (out / "history.json").write_text(json.dumps(histories, indent=2) + "\n", encoding="utf-8")
    (out / "best.pt").replace(out / "model.pt")


if __name__ == "__main__":
    main()
