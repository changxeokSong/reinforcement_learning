"""Adapt the campaign policies on the refactored Unity build and compare deployments."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.action_safety_eval import evaluate_stage_six
from laser.campaign_eval import AREAS, EPISODE_ATTEMPTS, LEVELS, ROUNDS, evaluate_campaign
from laser.env import LaserEnv
from laser.experiments import SEEDS, build_digest
from laser.imitation import Student, collect, train_student
from laser.level6_eval import train_one
from laser.level6_integration import StageSixPolicy
from laser.ppo_specialists import StagePolicy


SAFETY_STAGES = (4, 5, 6, 7, 9, 10)
PPO_STEPS = 524_288
DAGGER_STEPS = 400
DAGGER_BETAS = (1.0, 0.5, 0.25, 0.0)
CONDITIONS = {
    "previous": (False, False),
    "new_ppo": (False, True),
    "new_dagger": (True, False),
    "both_retrained": (True, True),
}


def models(root, seed, condition):
    new_dagger, new_ppo = CONDITIONS[condition]
    student_dir = (root / "retrained_campaign" / f"dagger_seed{seed}" if new_dagger
                   else root / "imitation" / f"dagger_rand_h512_long_seed{seed}")
    expert_dir = (root / "retrained_campaign" / f"ppo_seed{seed}" if new_ppo
                  else root / "level6_speed_warm" / f"geometry_seed{seed}")
    return student_dir / "model.pt", expert_dir / "model.pt"


def train_pair(args, seed, worker):
    initial_student, initial_ppo = models(args.root, seed, "previous")
    student_path, ppo_path = models(args.root, seed, "both_retrained")
    train_one(ppo_path.parent, 2, 1, seed, PPO_STEPS, args.build, worker, str(initial_ppo.resolve(strict=True)))

    config = {"build": str(args.build), "build_sha256": args.build_sha256, "level6_design": 2, "seed": seed,
              "initial_student": str(initial_student), "teachers": str(args.teachers), "stage6_teacher": str(ppo_path),
              "decisions_per_stage": DAGGER_STEPS, "teacher_probabilities": DAGGER_BETAS,
              "lr": 1e-4, "epochs": 2, "batch_size": 1024, "safety_stages": SAFETY_STAGES}
    history_path = student_path.with_name("history.json")
    if student_path.is_file():
        saved = json.loads(history_path.read_text(encoding="utf-8"))
        if saved["config"] != json.loads(json.dumps(config)):
            raise ValueError(f"Existing DAgger model belongs to different settings: {student_path}")
        return

    expert_paths = json.loads(args.teachers.read_text(encoding="utf-8"))["models"]
    teacher = StagePolicy({**expert_paths, "6": str(ppo_path)})
    student = Student(512, seed)
    student.net.load_state_dict(load_policy(initial_student).net.state_dict())
    optimizer = torch.optim.Adam(student.net.parameters(), lr=config["lr"])
    rng = np.random.default_rng(seed)
    history, states, labels = [], [], []
    env = LaserEnv(n_areas=16, seed=111_000 + seed, worker_id=worker, level=1, build=args.build,
                   level6_design=2, level6_safety_steps=2, safety_levels=SAFETY_STAGES)
    try:
        for iteration, beta in enumerate(DAGGER_BETAS, start=1):
            for level in LEVELS:
                x, y, _ = collect(env, teacher, student, level, DAGGER_STEPS, beta, rng)
                states.append(x)
                labels.append(y)
                student.steps += len(x)
            loss, accuracy = train_student(student, optimizer, np.concatenate(states), np.concatenate(labels),
                                           epochs=config["epochs"], batch=config["batch_size"], rng=rng)
            history.append({"iteration": iteration, "samples": student.steps, "loss": loss, "agreement": accuracy})
            print(f"DAgger seed {seed}, iteration {iteration}: {student.steps} examples, agreement {accuracy:.1%}",
                  flush=True)
    finally:
        env.close()
    student_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps({"config": config, "iterations": history}, indent=2) + "\n", encoding="utf-8")
    temporary = student_path.with_suffix(".tmp")
    student.save(temporary, config)
    temporary.replace(student_path)


def evaluate_seed(args, seed, worker, conditions, seed_base, rounds):
    scores = []
    options = dict(n_areas=AREAS, worker_id=worker, build=args.build, level6_design=2,
                   level6_safety_steps=2, safety_levels=SAFETY_STAGES)
    for condition in conditions:
        student_path, ppo_path = models(args.root, seed, condition)
        student, expert = load_policy(student_path), load_policy(ppo_path)
        env = LaserEnv(seed=seed_base + seed, level=6, **options)
        try:
            isolated = evaluate_stage_six(env, expert, rounds, 2)
        finally:
            env.close()
        env = LaserEnv(seed=seed_base + seed + len(SEEDS), level=1, **options)
        try:
            campaign = evaluate_campaign(env, StageSixPolicy(student, expert), LEVELS, rounds, EPISODE_ATTEMPTS)
        finally:
            env.close()
        scores.append({"condition": condition, "seed": seed, "student": str(student_path),
                       "stage6_policy": str(ppo_path), "stage_six": isolated, "campaign": campaign})
        print(f"{seed_base} {condition} seed {seed}: {campaign['completed']}/{campaign['campaigns']}",
              flush=True)
    return scores


def evaluate_conditions(pool, args, conditions, base, rounds):
    futures = [pool.submit(evaluate_seed, args, seed, args.worker + seed * 4, conditions, base, rounds)
               for seed in SEEDS]
    return [score for future in futures for score in future.result()]


def select_configuration(validation):
    def validation_score(condition):
        rows = [row for row in validation if row["condition"] == condition]
        return (sum(row["campaign"]["completed"] for row in rows),
                sum(row["stage_six"]["success"] for row in rows),
                sum(CONDITIONS[condition]))

    return max(CONDITIONS, key=validation_score)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("runs/laser_refactor_release/LaserMission.exe"))
    parser.add_argument("--root", type=Path, default=Path("runs/laser"))
    parser.add_argument("--teachers", type=Path, default=Path("runs/results/laser/ppo_specialists_rand.json"))
    parser.add_argument("--out", type=Path, default=Path("runs/results/laser/refactor_campaign_retraining.json"))
    parser.add_argument("--worker", type=int, default=3550)
    args = parser.parse_args()
    args.build = args.build.resolve(strict=True)
    args.build_sha256 = build_digest(args.build.parent)
    torch.set_num_threads(1)

    with ThreadPoolExecutor(max_workers=len(SEEDS)) as pool:
        training = [pool.submit(train_pair, args, seed, args.worker + seed * 4) for seed in SEEDS]
        for future in training:
            future.result()
        validation = evaluate_conditions(pool, args, tuple(CONDITIONS), 112_000, 6)
        selected = select_configuration(validation)
        print(f"Validation selected {selected}", flush=True)
        holdout_conditions = tuple(dict.fromkeys(("previous", "new_ppo", "both_retrained", selected)))
        holdout = evaluate_conditions(pool, args, holdout_conditions, 113_000, ROUNDS)

    results = {"build": str(args.build), "build_sha256": args.build_sha256,
               "ppo_additional_steps": PPO_STEPS, "safety_stages": SAFETY_STAGES,
               "attempts_per_stage": EPISODE_ATTEMPTS, "selected": selected,
               "validation_seed_base": 112_000, "holdout_seed_base": 113_000,
               "validation": validation, "holdout": holdout}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(".tmp")
    temporary.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.out)


if __name__ == "__main__":
    main()
