"""X11/X12 최종 모델을 같은 조건에서 레벨별·순차 캠페인으로 평가한다."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.env import LaserEnv
from laser.experiments import RANDOM_CAMPAIGN, SEEDS
from laser.train import evaluate

GROUPS = {
    "sac": "x11/sac_random_campaign",
    "ppo": "x12/ppo_random_campaign",
    "dqn": "x12/dqn_random_campaign",
}
LEVELS = RANDOM_CAMPAIGN["eval_levels"]
EPISODE_ATTEMPTS = 3
AREAS = 10
ROUNDS = 20
EVAL_SEED = 20_000


def evaluate_campaign(env, policy, levels, rounds, max_attempts):
    """방마다 독립적으로 성공한 경우에만 다음 단계의 결과를 계산한다."""
    reached = np.zeros(len(levels), dtype=int)
    cleared = np.zeros(len(levels), dtype=int)
    for _ in range(rounds):
        alive = np.ones(env.n, dtype=bool)
        for index, level in enumerate(levels):
            reached[index] += alive.sum()
            obs, warmup = env.evaluation_reset(level)
            attempts_left = alive.astype(int) * max_attempts
            passed = np.zeros(env.n, dtype=bool)
            while attempts_left.any():
                step = env.evaluation_step(policy.act(obs), warmup)
                obs = step["obs"]
                for slot, outcome, _ in step["results"]:
                    if attempts_left[slot] > 0:
                        attempts_left[slot] -= 1
                        if outcome == "success":
                            passed[slot] = True
                            attempts_left[slot] = 0
            cleared[index] += passed.sum()
            alive = passed
            if not alive.any():
                break
    return {"reached": reached.tolist(), "cleared": cleared.tolist(),
            "completed": int(cleared[-1]), "campaigns": rounds * env.n,
            "completion_rate": float(cleared[-1] / (rounds * env.n))}


def evaluation_env(common, seed, worker, areas=AREAS):
    return LaserEnv(seed=seed, n_areas=areas, level=1, worker_id=worker, campaign_layouts=True,
                    build=common["build"], obs_mode=common["obs_mode"], shaping=common["shaping"],
                    time_penalty=common["time_penalty"], potential_shaping=common["potential_shaping"],
                    shaping_gamma=0.99, time_scale=common["time_scale"])


def evaluate_model(policy, common, eval_seed, worker, *, areas=AREAS, rounds=ROUNDS):
    env = evaluation_env(common, eval_seed, worker, areas)
    try:
        by_level = evaluate(env, policy, LEVELS, rounds)
    finally:
        env.close()
    env = evaluation_env(common, eval_seed + len(SEEDS), worker, areas)
    try:
        campaign = evaluate_campaign(env, policy, LEVELS, rounds, EPISODE_ATTEMPTS)
    finally:
        env.close()
    for key, value in by_level.items():
        if not np.isfinite(value):
            by_level[key] = None
    return {"by_level": by_level, "campaign": campaign}


def finished_models(root):
    reference = None
    for algo, group in GROUPS.items():
        for seed in SEEDS:
            run = root / f"{group}_seed{seed}"
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            model = run / "model.pt"
            common = dict(cfg["common"])
            for key in ("campaign_layouts", "curriculum_track_actual_level"):
                if common[key] == "True":  # X11에서 문자열로 저장된 불리언
                    common[key] = True
            common["build"] = str(Path(common["build"]).resolve())
            if not cfg.get("finished") or not model.is_file() or max(LEVELS) not in cfg.get("verified_eval_levels", []):
                raise ValueError(f"Final campaign model is missing or unfinished: {run}")
            if cfg["algo"] != algo or cfg["seed"] != seed or not all(
                common[key] == value for key, value in RANDOM_CAMPAIGN.items()
            ) or cfg["algo_config"]["gamma"] != 0.99:
                raise ValueError(f"Unexpected campaign training configuration: {run}")
            if reference is None:
                reference = common
            elif common != reference:
                raise ValueError(f"Campaign models must use the same environment and step budget: {run}")
            yield algo, seed, model, common


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("runs/laser"))
    ap.add_argument("--out", type=Path, default=Path("runs/results/laser/campaign_comparison.json"))
    ap.add_argument("--worker", type=int, default=1026)
    args = ap.parse_args()
    torch.set_num_threads(1)
    models = list(finished_models(args.root))
    results = []
    for algo, seed, model, common in models:
        policy = load_policy(model, greedy=True)
        if policy.kind != algo or policy.steps != common["total_steps"]:
            raise ValueError(f"Checkpoint does not match the final training budget: {model}")
        seed_for_eval = EVAL_SEED + seed
        scores = evaluate_model(policy, common, seed_for_eval, args.worker)
        results.append({"algo": algo, "seed": seed, "env_seed": seed_for_eval,
                        "campaign_seed": seed_for_eval + len(SEEDS), "model": str(model), **scores})
        campaign = scores["campaign"]
        print(f"{algo.upper()} seed {seed}: {campaign['completed']}/{campaign['campaigns']} full clears", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(".tmp")
    temp.write_text(json.dumps({"total_steps": RANDOM_CAMPAIGN["total_steps"], "levels": LEVELS,
                                "episodes_per_level": AREAS * ROUNDS, "attempts_per_level": EPISODE_ATTEMPTS,
                                "starts_at_time_zero": True, "build": models[0][3]["build"], "runs": results},
                               indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(args.out)


if __name__ == "__main__":
    main()
