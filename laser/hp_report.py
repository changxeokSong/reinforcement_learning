"""하이퍼파라미터 탐색(hp_ppo, hp_dqn, hp_sac)과 학습량(long) 결과를 정리한다.

기준은 새 빌드 커리큘럼 비교(refactor_curriculum)의 같은 학습 seed다. 모든 값은 학습이 끝난 뒤
학습에 쓰지 않은 환경 seed(학습 seed + 1000)에서 1~10단계 각 100판을 돌린 final.json의 평균 성공률이다.
값 하나만 바꿨으므로 같은 seed끼리의 차이로 효과를 본다. 신뢰구간은 학습 seed를 표본으로 한 95% t 구간이다.

  .venv-unity\\Scripts\\python -m laser.hp_report
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


ROOT = Path("runs/laser")
OUT = Path("runs/results/laser")
LEVELS = range(1, 11)
STUDIES = ["hp_ppo", "hp_dqn", "hp_sac", "long"]


def score(run):
    path = run / "final.json"
    if not path.is_file():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    return float(np.mean([d[f"success_l{i}"] for i in LEVELS]))


def ci(values):
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return float("nan")
    return float(stats.t.ppf(0.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values)))


def seeds_of(folder, name):
    out = {}
    for run in sorted(folder.glob(f"{name}_seed*")):
        s = score(run)
        if s is not None:
            out[int(run.name.rsplit("seed", 1)[1])] = s
    return out


def main():
    rows = []
    base = {algo: seeds_of(ROOT / "refactor_curriculum", algo) for algo in ("ppo", "dqn", "sac")}
    for algo, by_seed in base.items():
        vals = [by_seed[s] for s in sorted(by_seed) if s < 3]
        rows.append({"study": "base", "algo": algo, "name": f"{algo} 기준", "n": len(vals),
                     "mean": np.mean(vals), "ci": ci(vals), "diff": 0.0, "diff_ci": 0.0, "seeds": vals})
    for study in STUDIES:
        names = sorted({run.name.rsplit("_seed", 1)[0] for run in (ROOT / study).glob("*_seed*")})
        for name in names:
            algo = name.split("_", 1)[0]
            by_seed = seeds_of(ROOT / study, name)
            common = [s for s in sorted(by_seed) if s in base[algo] and s < 3]
            if not common:
                continue
            vals = [by_seed[s] for s in common]
            diffs = [by_seed[s] - base[algo][s] for s in common]
            rows.append({"study": study, "algo": algo, "name": name, "n": len(vals),
                         "mean": np.mean(vals), "ci": ci(vals), "diff": np.mean(diffs),
                         "diff_ci": ci(diffs), "seeds": vals})

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "hp_sweep.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["study", "algo", "name", "n", "mean_pct", "ci_pct", "diff_pct", "diff_ci_pct", "seeds_pct"])
        for r in rows:
            w.writerow([r["study"], r["algo"], r["name"], r["n"], f"{100 * r['mean']:.2f}", f"{100 * r['ci']:.2f}",
                        f"{100 * r['diff']:.2f}", f"{100 * r['diff_ci']:.2f}",
                        " ".join(f"{100 * v:.1f}" for v in r["seeds"])])
    for r in rows:
        lo, hi = r["diff"] - r["diff_ci"], r["diff"] + r["diff_ci"]
        flag = " *" if r["n"] >= 3 and (lo > 0 or hi < 0) else ""
        print(f"{r['study']:7s} {r['name']:34s} n={r['n']} {100 * r['mean']:6.2f}% ± {100 * r['ci']:5.2f}"
              f" | 기준 대비 {100 * r['diff']:+6.2f}%p [{100 * lo:+6.2f}, {100 * hi:+6.2f}]{flag}")

    # 그림: 알고리즘별, 기준 대비 차이와 95% CI
    fig, axes = plt.subplots(1, 3, figsize=(15, 6), sharex=False)
    for ax, algo in zip(axes, ("ppo", "sac", "dqn")):
        sub = [r for r in rows if r["algo"] == algo and r["study"].startswith("hp")]
        sub.sort(key=lambda r: r["diff"])
        y = np.arange(len(sub))
        d = np.array([100 * r["diff"] for r in sub])
        e = np.array([100 * r["diff_ci"] for r in sub])
        colors = ["#2a9d8f" if lo > 0 else "#e76f51" if hi < 0 else "#8d99ae"
                  for lo, hi in zip(d - e, d + e)]
        ax.errorbar(d, y, xerr=e, fmt="none", ecolor="#adb5bd", capsize=3)
        ax.scatter(d, y, c=colors, zorder=3)
        ax.axvline(0, color="#495057", lw=1)
        ax.set_yticks(y, [r["name"].split("_", 1)[1] for r in sub])
        b = [r for r in rows if r["study"] == "base" and r["algo"] == algo][0]
        ax.set_title(f"{algo.upper()} (기준 {100 * b['mean']:.1f}%)")
        ax.set_xlabel("기준 대비 성공률 차이 (%p, 95% CI)")
    plt.rcParams["font.family"] = "Malgun Gothic"
    for ax in axes:
        for label in ax.get_yticklabels() + [ax.title, ax.xaxis.label]:
            label.set_fontfamily("Malgun Gothic")
    fig.tight_layout()
    fig.savefig(OUT / "hp_sweep.png", dpi=150)
    print(f"→ {OUT / 'hp_sweep.csv'}, {OUT / 'hp_sweep.png'}")


if __name__ == "__main__":
    main()
