"""레벨별 PPO 검증 후 모델을 하나씩 선택해 10단계 캠페인을 평가한다."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.campaign_eval import EVAL_SEED, LEVELS, ROUNDS, evaluate_campaign, evaluate_model, evaluation_env
from laser.env import LEVEL_INDEX, LaserEnv
from laser.experiments import SEEDS

EXTENDED_ATTEMPTS = 10


class StagePolicy:
    def __init__(self, models):
        self.policies = {int(level): load_policy(path, greedy=True) for level, path in models.items()}
        if set(self.policies) != set(LEVELS) or any(p.kind != "ppo" for p in self.policies.values()):
            raise ValueError("Expected one PPO model for each stage")

    def act(self, obs):
        levels = np.rint(4 * obs[:, LEVEL_INDEX]).astype(int)
        actions = np.empty(len(obs), dtype=np.int64)
        for level in np.unique(levels):
            slots = levels == level
            actions[slots] = self.policies[level].act(obs[slots])
        return actions


def measure_layouts(env, policy, level):
    scores = defaultdict(lambda: [0, 0])
    for _ in range(10):
        obs, warmup = env.evaluation_reset(level)
        spawn = obs[:, 0].copy()
        done = np.zeros(env.n, dtype=bool)
        while not done.all():
            previous_warmup = warmup.copy()
            result = env.evaluation_step(policy.act(obs), warmup)
            obs = result["obs"]
            fresh = previous_warmup & ~warmup
            spawn[fresh] = obs[fresh, 0]
            for slot, outcome, _ in result["results"]:
                if not done[slot]:
                    tally = scores[float(spawn[slot])]
                    tally[0] += int(outcome == "success")
                    tally[1] += 1
                    done[slot] = True
    if len(scores) != 4:
        raise RuntimeError(f"Expected four layouts on stage {level}; saw {len(scores)}")
    return {str(x): wins / attempts for x, (wins, attempts) in sorted(scores.items())}


def select_models(root, build, worker):
    candidate_levels = {
        root / f"x12/ppo_random_campaign_seed{seed}/model.pt": LEVELS for seed in SEEDS
    }
    for level in LEVELS:
        for path in sorted((root / "pilots").glob(f"ppo_level{level}_seed*/model.pt")):
            cfg = json.loads(path.with_name("config.json").read_text(encoding="utf-8"))
            if Path(cfg["common"]["build"]).resolve() != build or cfg["common"]["level"] != level:
                raise ValueError(f"Unexpected pilot environment: {path}")
            candidate_levels[path] = [level]
            for checkpoint in sorted(path.parent.glob("ckpt_*.pt")):
                if checkpoint.stem != "ckpt_000000000":
                    candidate_levels[checkpoint] = [level]
    validation = defaultdict(list)
    for path, levels in candidate_levels.items():
        policy = load_policy(path)
        env = LaserEnv(n_areas=10, seed=22_000, worker_id=worker, level=1, build=build, campaign_layouts=True)
        try:
            for level in levels:
                rates = measure_layouts(env, policy, level)
                score = float(np.mean(list(rates.values())))
                validation[level].append({"model": str(path), "validation_rate": score, "layouts": rates})
                print(f"L{level}: {score:.0%} by layout ({path.parent.name}/{path.name})", flush=True)
        finally:
            env.close()
    chosen = {level: max(validation[level], key=lambda row: row["validation_rate"])["model"] for level in LEVELS}
    return chosen, validation


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("runs/laser"))
    ap.add_argument("--out", type=Path, default=Path("runs/results/laser/ppo_specialists.json"))
    ap.add_argument("--worker", type=int, default=1076)
    args = ap.parse_args()
    torch.set_num_threads(1)
    config = args.root / "x12/ppo_random_campaign_seed0/config.json"
    common = json.loads(config.read_text(encoding="utf-8"))["common"]
    models, validation = select_models(args.root, Path(common["build"]).resolve(), args.worker)
    policy = StagePolicy(models)
    runs = []
    for seed in SEEDS:
        env_seed = EVAL_SEED + seed
        results = evaluate_model(policy, common, env_seed, args.worker)
        campaign = results["campaign"]
        print(f"Eval seed {env_seed} (3 attempts): {campaign['completed']}/{campaign['campaigns']} full clears", flush=True)
        env = evaluation_env(common, env_seed + len(SEEDS), args.worker)
        try:
            extended = evaluate_campaign(env, policy, LEVELS, ROUNDS, EXTENDED_ATTEMPTS)
        finally:
            env.close()
        print(f"Eval seed {env_seed} ({EXTENDED_ATTEMPTS} attempts): "
              f"{extended['completed']}/{extended['campaigns']} full clears", flush=True)
        runs.append({"seed": env_seed, **results, "extended_campaign": extended})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    artifact = {"build": common["build"], "models": models, "validation": validation,
                "extended_attempts": EXTENDED_ATTEMPTS, "runs": runs}
    temp = args.out.with_suffix(".tmp")
    temp.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(args.out)


if __name__ == "__main__":
    main()
