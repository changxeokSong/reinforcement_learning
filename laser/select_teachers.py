"""단계마다 후보 PPO 정책을 같은 검증 조건(검증용 환경 seed, 레벨당 200판)으로 평가해 선생님을 고른다.

  .venv-unity\Scripts\python -m laser.select_teachers --base runs/results/laser/ppo_specialists.json \
      --candidates runs/laser/specialists_v2 --out runs/results/laser/ppo_specialists_v2.json
최종 평가 seed(campaign_eval.EVAL_SEED 계열)와 겹치지 않는 seed로 고른다.
"""
import argparse
import json
import re
from pathlib import Path

import torch

from algos.common import load_policy
from laser.campaign_eval import evaluation_env
from laser.imitation import load_common
from laser.train import evaluate

VALIDATION_SEED = 77_000


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--worker", type=int, default=900)
    args = ap.parse_args()
    torch.set_num_threads(2)
    base = json.loads(args.base.read_text(encoding="utf-8"))
    models = {int(k): v for k, v in base["models"].items()}
    cands = {}
    for run in sorted(args.candidates.glob("ppo_level*_seed*")):
        if (run / "model.pt").exists():
            lv = int(re.search(r"level(\d+)", run.name).group(1))
            cands.setdefault(lv, []).append(str(run / "model.pt"))
    common = load_common()
    env = evaluation_env(common, VALIDATION_SEED, args.worker, areas=10)
    validation = {}
    try:
        for lv, paths in sorted(cands.items()):
            rows = []
            for path in [models[lv]] + paths:
                rate = evaluate(env, load_policy(path), [lv], 20)[f"success_l{lv}"]
                rows.append({"model": path, "validation_rate": rate})
                print(f"L{lv} {rate:.3f} {path}", flush=True)
            best = max(rows, key=lambda r: r["validation_rate"])
            models[lv] = best["model"]
            validation[str(lv)] = rows
    finally:
        env.close()
    out = {"build": base["build"], "models": {str(k): models[k] for k in sorted(models)},
           "validation": validation, "validation_seed": VALIDATION_SEED, "base": str(args.base)}
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["models"], indent=1))


if __name__ == "__main__":
    main()
