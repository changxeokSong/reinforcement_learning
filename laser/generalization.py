"""처음 보는 배치에서의 일반화 평가.

캠페인 배치(단계마다 고정된 4개)를 끄면 Unity가 판마다 레이저 위치·속도·위상을 무작위로 만든다.
학습에 쓴 4개 배치와 같은 장애물 종류이지만 수치가 다른 새 배치에서 레벨당 200판을 평가한다.

  .venv-unity\Scripts\python -m laser.generalization
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from algos.common import load_policy
from laser.campaign_eval import LEVELS
from laser.env import LaserEnv
from laser.imitation import load_common
from laser.ppo_specialists import StagePolicy
from laser.train import evaluate

OUT = Path("runs/results/laser/generalization.json")
POLICIES = {
    "PPO 정책 하나 (1,200만)": [f"runs/laser/x12/ppo_random_campaign_seed{s}/model.pt" for s in range(3)],
    "단계별 PPO 선생님 v2": ["teachers:runs/results/laser/ppo_specialists_v2.json"],
    "학생 v2 + 시범 (BC)": [f"runs/laser/imitation/bc_v2_demo_seed{s}/model.pt" for s in range(3)],
    "학생 v2 + 시범 (DAgger)": [f"runs/laser/imitation/dagger_v2_demo_seed{s}/model.pt" for s in range(3)],
}


def load(spec):
    if spec.startswith("teachers:"):
        return StagePolicy(json.loads(Path(spec.split(":", 1)[1]).read_text(encoding="utf-8"))["models"])
    return load_policy(spec, greedy=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--worker", type=int, default=2300)
    ap.add_argument("--rounds", type=int, default=20)
    args = ap.parse_args()
    torch.set_num_threads(2)
    common = load_common()
    env = LaserEnv(n_areas=10, seed=123_456, worker_id=args.worker, level=1, campaign_layouts=False,
                   build=common["build"], obs_mode=common["obs_mode"], shaping=common["shaping"],
                   time_penalty=common["time_penalty"], time_scale=common["time_scale"])
    env.set_param("max_level", 10)
    out = {}
    try:
        for name, specs in POLICIES.items():
            rows = []
            for spec in specs:
                r = evaluate(env, load(spec), LEVELS, args.rounds)
                rows.append({"model": spec, **{f"success_l{l}": r[f"success_l{l}"] for l in LEVELS}})
                print(name, spec[-40:], " ".join(f"{r[f'success_l{l}']:.2f}" for l in LEVELS), flush=True)
            out[name] = rows
    finally:
        env.close()
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, rows in out.items():
        m = np.mean([[r[f"success_l{l}"] for l in LEVELS] for r in rows], axis=0)
        print(f"{name}: " + " ".join(f"L{l} {v:.2f}" for l, v in zip(LEVELS, m)) + f" | 평균 {m.mean():.3f}")


if __name__ == "__main__":
    main()
