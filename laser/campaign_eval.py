"""X11/X12 최종 모델을 같은 조건에서 레벨별·순차 캠페인으로 평가한다."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.baseline import RandomPolicy
from laser.env import LaserEnv
from laser.experiments import RANDOM_CAMPAIGN, REFACTOR_ALGOS, REFACTOR_STUDIES, SEEDS, build_digest
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
                mask = env.action_mask
                actions = policy.act(obs) if mask is None else policy.act(obs, action_mask=mask)
                step = env.evaluation_step(actions, warmup)
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


def evaluation_env(common, seed, worker, areas=AREAS, *, campaign_layouts=True):
    return LaserEnv(seed=seed, n_areas=areas, level=1, worker_id=worker, campaign_layouts=campaign_layouts,
                    build=common["build"], obs_mode=common["obs_mode"], shaping=common["shaping"],
                    time_penalty=common["time_penalty"], potential_shaping=common["potential_shaping"],
                    shaping_gamma=0.99, time_scale=common["time_scale"], level6_design=common.get("level6_design", 0))


def evaluate_model(policy, common, eval_seed, worker, *, areas=AREAS, rounds=ROUNDS, campaign_layouts=True):
    env = evaluation_env(common, eval_seed, worker, areas, campaign_layouts=campaign_layouts)
    try:
        by_level = evaluate(env, policy, LEVELS, rounds)
    finally:
        env.close()
    env = evaluation_env(common, eval_seed + len(SEEDS), worker, areas, campaign_layouts=campaign_layouts)
    try:
        campaign = evaluate_campaign(env, policy, LEVELS, rounds, EPISODE_ATTEMPTS)
    finally:
        env.close()
    for key, value in by_level.items():
        if not np.isfinite(value):
            by_level[key] = None
    return {"by_level": by_level, "campaign": campaign}


def finished_models(root, study=None):
    reference = None
    groups = {algo: f"{study}/{algo}" for algo in REFACTOR_ALGOS} if study else GROUPS
    expected = REFACTOR_STUDIES[study] if study else RANDOM_CAMPAIGN
    for algo, group in groups.items():
        for seed in SEEDS:
            run = root / f"{group}_seed{seed}"
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            model = run / "model.pt"
            common = dict(cfg["common"])
            common.setdefault("curriculum_promote_on_success", True)
            for key in ("campaign_layouts", "curriculum_track_actual_level"):
                if common[key] == "True":  # X11에서 문자열로 저장된 불리언
                    common[key] = True
            common["build"] = str(Path(common["build"]).resolve())
            if not cfg.get("finished") or not model.is_file() or max(LEVELS) not in cfg.get("verified_eval_levels", []):
                raise ValueError(f"Final campaign model is missing or unfinished: {run}")
            if cfg["algo"] != algo or cfg["seed"] != seed or not all(
                common[key] == value for key, value in expected.items()
            ) or cfg["algo_config"]["gamma"] != 0.99:
                raise ValueError(f"Unexpected campaign training configuration: {run}")
            if study and (cfg.get("init_policy") or any(
                cfg["algo_config"][key] != value for key, value in REFACTOR_ALGOS[algo].items()
            )):
                raise ValueError(f"Expected a fresh model with the recorded algorithm settings: {run}")
            if reference is None:
                reference = common
            elif common != reference:
                raise ValueError(f"Campaign models must use the same environment and step budget: {run}")
            yield algo, seed, model, common


def score_run(algo, seed, model, common, worker, refactor):
    policy = load_policy(model, greedy=True) if model is not None else RandomPolicy(seed)
    if model is not None and (policy.kind != algo or policy.steps != common["total_steps"]):
        raise ValueError(f"Checkpoint does not match the final training budget: {model}")
    seed_for_eval = (110_000 if refactor else EVAL_SEED) + seed
    scores = evaluate_model(policy, common, seed_for_eval, worker, campaign_layouts=not refactor)
    campaign = scores["campaign"]
    print(f"{algo.upper()} seed {seed}: {campaign['completed']}/{campaign['campaigns']} full clears", flush=True)
    return {"algo": algo, "seed": seed, "env_seed": seed_for_eval,
            "campaign_seed": seed_for_eval + len(SEEDS), "model": str(model) if model else None, **scores}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("runs/laser"))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--worker", type=int, default=1026)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--study", choices=REFACTOR_STUDIES, help="evaluate the fresh models on procedural layouts")
    args = ap.parse_args()
    if args.parallel < 1:
        ap.error("--parallel must be positive")
    if args.out is None:
        filename = f"{args.study}_results.json" if args.study else "campaign_comparison.json"
        args.out = Path("runs/results/laser") / filename
    torch.set_num_threads(1)
    models = list(finished_models(args.root, study=args.study))
    common = models[0][3]
    if args.study:
        models.extend(("random", seed, None, common) for seed in SEEDS)
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        tasks = [pool.submit(score_run, *job, args.worker + index, bool(args.study))
                 for index, job in enumerate(models)]
        results = [task.result() for task in tasks]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(".tmp")
    temp.write_text(json.dumps({"total_steps": common["total_steps"], "levels": LEVELS,
                                "episodes_per_level": AREAS * ROUNDS, "attempts_per_level": EPISODE_ATTEMPTS,
                                "starts_at_time_zero": True, "build": common["build"],
                                "build_sha256": build_digest(Path(common["build"]).parent),
                                "procedural": bool(args.study), "study": args.study, "runs": results},
                               indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(args.out)


if __name__ == "__main__":
    main()
