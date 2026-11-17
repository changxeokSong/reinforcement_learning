"""레이저 미션 실험 결과 정리: 표(최종 성공률 ± 95% 신뢰구간)와 학습 곡선.

배구 쪽 분석 도구와 같은 방식이다 (표본 단위는 학습 seed). matplotlib이 있는 .venv로 실행한다.
  python -m laser.report                      # runs/laser 전체 → runs/results/laser/
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.report import COLORS
from analysis.stats import mean_ci

LEVELS = [1, 2, 3, 4]
# 비교 묶음: 이름 → 그룹 목록 (실험/설정)
COMPARISONS = {
    "x1_algorithms": ["x1/ppo", "x1/dqn", "x1/sac"],
    "x2_training": ["x1/ppo", "x2/ppo_curmix", "x2/ppo_random", "x2/ppo_level4"],
    "x3_observation": ["x1/ppo", "x3/ppo_rawobs"],
    "x4_reward": ["x1/ppo", "x4/ppo_notimepen", "x4/ppo_noshaping"],
}
LABELS = {
    "x1/ppo": "PPO (curriculum)", "x1/dqn": "DQN (curriculum)", "x1/sac": "SAC (curriculum)",
    "x2/ppo_random": "PPO random level", "x2/ppo_curmix": "PPO curriculum + review", "x2/ppo_level4": "PPO level 4 only",
    "x3/ppo_rawobs": "PPO raw observation",
    "x4/ppo_notimepen": "PPO no time penalty", "x4/ppo_noshaping": "PPO no shaping",
}
LINESTYLES = ["-", "--", ":", "-."]


def load(root):
    groups = defaultdict(list)
    for final in sorted(Path(root).glob("x*/*_seed*/final.json")):
        run = final.parent
        group = f"{run.parent.name}/{run.name.rsplit('_seed', 1)[0]}"
        rows = list(csv.DictReader(open(run / "metrics.csv", encoding="utf-8")))
        cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
        groups[group].append({
            "final": json.loads(final.read_text(encoding="utf-8")),
            "metrics": rows,
            "minutes": cfg.get("wall_sec", float("nan")) / 60,
            "algo": cfg["algo"],
        })
    return groups


def curve(runs, key):
    steps = np.array([int(r["step"]) for r in runs[0]["metrics"]])
    n = min(len(r["metrics"]) for r in runs)
    vals = np.array([[_mean_success(row) if key == "mean" else float(row[key]) for row in r["metrics"][:n]]
                     for r in runs])
    return steps[:n], vals


def _mean_success(row):
    return float(np.mean([float(row[f"success_l{lv}"]) for lv in LEVELS]))


def fmt(values):
    m, h = mean_ci(values)
    return f"{m:.2f} ± {h:.2f}"


def write_summary(groups, out):
    lines = ["# 레이저 미션 결과", "",
             "학습 후 최종 평가(레벨마다 200판, 가장 좋은 행동)의 성공률. 평균 ± 95% 신뢰구간, 표본 단위는 학습 seed.", "",
             "| 설정 | seed 수 | 레벨 1 | 레벨 2 | 레벨 3 | 레벨 4 | 평균 (1~4) | 학습 시간(분) |",
             "|---|---|---|---|---|---|---|---|"]
    for g, runs in sorted(groups.items(), key=lambda kv: -np.mean([r["final"]["success_mean"] for r in kv[1]])):
        cells = [fmt([r["final"][f"success_l{lv}"] for r in runs]) for lv in LEVELS]
        lines.append(f"| {LABELS.get(g, g)} | {len(runs)} | " + " | ".join(cells) +
                     f" | **{fmt([r['final']['success_mean'] for r in runs])}** | "
                     f"{np.mean([r['minutes'] for r in runs]):.0f} |")
    lines += ["", "## seed별 평균 성공률 (레벨 1~4)", "", "| 설정 | 값 |", "|---|---|"]
    for g, runs in sorted(groups.items()):
        lines.append(f"| {LABELS.get(g, g)} | " + " ".join(f"{r['final']['success_mean']:.2f}" for r in runs) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot_comparison(groups, names, title, path):
    names = [n for n in names if n in groups]
    if not names:
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    used = defaultdict(int)
    for g in names:
        runs = groups[g]
        algo = runs[0]["algo"]
        color, ls = COLORS.get(algo, "#333"), LINESTYLES[used[algo] % 4]
        used[algo] += 1
        steps, vals = curve(runs, "mean")
        m, h = mean_ci(vals)
        axes[0].plot(steps / 1e6, m, color=color, ls=ls, lw=2, label=f"{LABELS.get(g, g)} (n={len(runs)})")
        axes[0].fill_between(steps / 1e6, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=color, alpha=0.15)
    axes[0].set_xlabel("training steps (M)")
    axes[0].set_ylabel("success rate (mean of level 1-4)")
    axes[0].set_ylim(0, 1)
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    axes[0].set_title(title)

    width = 0.8 / len(names)
    used = defaultdict(int)
    for k, g in enumerate(names):
        runs = groups[g]
        algo = runs[0]["algo"]
        vals = np.array([[r["final"][f"success_l{lv}"] for lv in LEVELS] for r in runs])
        m, h = mean_ci(vals)
        x = np.arange(len(LEVELS)) + (k - (len(names) - 1) / 2) * width
        axes[1].bar(x, m, width, yerr=h, capsize=3, color=COLORS.get(algo, "#333"),
                    alpha=0.9 - 0.25 * used[algo], edgecolor="black", lw=0.5, label=LABELS.get(g, g))
        used[algo] += 1
        for j in range(len(LEVELS)):
            axes[1].scatter(np.full(len(runs), x[j]), vals[:, j], color="black", s=8, zorder=3)
    axes[1].set_xticks(range(len(LEVELS)), [f"level {lv}" for lv in LEVELS])
    axes[1].set_ylabel("final success rate")
    axes[1].set_ylim(0, 1.05)
    axes[1].grid(alpha=0.3, axis="y")
    axes[1].legend(fontsize=8)
    axes[1].set_title("final evaluation (200 episodes per level)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_curriculum(groups, path):
    """커리큘럼 학습에서 학습 레벨이 언제 올라갔는지."""
    fig, ax = plt.subplots(figsize=(7, 4))
    for g in ["x1/ppo", "x1/dqn", "x1/sac"]:
        for i, r in enumerate(groups.get(g, [])):
            steps = [int(row["step"]) / 1e6 for row in r["metrics"]]
            lv = [int(float(row["train_level"])) for row in r["metrics"]]
            ax.step(steps, lv, where="post", color=COLORS[r["algo"]], alpha=0.7,
                    label=LABELS[g] if i == 0 else None)
    ax.set_xlabel("training steps (M)")
    ax.set_ylabel("training level")
    ax.set_yticks(range(5))
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title("curriculum progress")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default="runs/laser")
    ap.add_argument("--out", default="runs/results/laser")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    groups = load(args.root)
    if not groups:
        raise SystemExit("끝난 실행이 없습니다 (final.json)")
    write_summary(groups, out)
    for name, names in COMPARISONS.items():
        plot_comparison(groups, names, name, out / f"{name}.png")
    plot_curriculum(groups, out / "curriculum.png")
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
