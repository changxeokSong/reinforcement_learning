"""실험 결과를 보고서용 그래프와 표로 정리한다.

예)
  python -m analysis.report runs/e1
  python -m analysis.report runs/e1 runs/e2 --out results/e1_e2

같은 설정의 seed들을 한 그룹으로 묶어서 평균과 95% 신뢰구간을 낸다.
(폴더 이름이 '<그룹>_seed<번호>' 형태여야 한다.)

출력
  curves_<지표>.png   학습 곡선 (평균 ± 95% 신뢰구간)
  final_winrate.png   최종 승률 막대그래프
  summary.md / summary.csv   최종 결과 표 (seed별 값 포함)
  league_heatmap.png, league_elo.png   리그전 결과 (league.json이 있을 때)
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

from analysis.stats import mean_ci

OPPONENTS = ("random", "easy", "hard")
COLORS = {"ppo": "#b01c2e", "dqn": "#1f6fb4", "sac": "#2a9d55", "bot": "#777777"}
LINESTYLES = ["-", "--", ":", "-."]


def load_runs(dirs):
    """그룹 이름 -> [(seed, config, metrics 열 dict)]"""
    groups = defaultdict(list)
    for d in dirs:
        for mfile in sorted(Path(d).glob("**/metrics.csv")):
            run = mfile.parent
            if "_seed" not in run.name or not (run / "model.pt").exists():
                continue
            cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
            with open(mfile, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            cols = {k: np.array([float(r[k]) if r[k] != "" else np.nan for r in rows])
                    for k in rows[0]}
            group = f"{Path(d).name}/{run.name.rsplit('_seed', 1)[0]}"
            groups[group].append((cfg["seed"], cfg, cols))
    return dict(groups)


def style_for(groups):
    """그룹마다 색(알고리즘)과 선 모양(같은 알고리즘 안에서 구분)을 정한다."""
    seen, styles = defaultdict(int), {}
    for g, runs in groups.items():
        algo = runs[0][1]["algo"]
        styles[g] = (COLORS.get(algo, "#333333"), LINESTYLES[seen[algo] % len(LINESTYLES)])
        seen[algo] += 1
    return styles


def plot_curves(groups, metric, ylabel, out):
    styles = style_for(groups)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for g, runs in groups.items():
        n = min(len(c[metric]) for _, _, c in runs)
        steps = runs[0][2]["step"][:n]
        mean, half = mean_ci(np.stack([c[metric][:n] for _, _, c in runs]))
        color, ls = styles[g]
        ax.plot(steps, mean, color=color, ls=ls, lw=2, label=f"{g} (n={len(runs)})")
        lo, hi = mean - half, mean + half
        if metric.startswith("wr_"):
            lo, hi = np.clip(lo, 0, 1), np.clip(hi, 0, 1)   # 승률은 0~1 범위만 그린다
        ax.fill_between(steps, lo, hi, color=color, alpha=0.15)
    ax.set_xlabel("Environment steps")
    ax.set_ylabel(ylabel)
    if metric.startswith("wr_"):
        ax.set_ylim(0, 1.02)
        ax.axhline(0.5, color="gray", lw=0.8, ls=":")
    ax.set_title(f"{ylabel} (mean ± 95% CI over seeds)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def summarize(groups, out_dir):
    """마지막 평가 시점의 값으로 표를 만든다."""
    keys = [f"wr_{o}" for o in OPPONENTS] + ["spikes", "dives", "rally_sec"]
    rows = []
    for g, runs in groups.items():
        runs = sorted(runs, key=lambda r: r[0])
        row = {"group": g, "algo": runs[0][1]["algo"], "n_seeds": len(runs),
               "steps": int(runs[0][2]["step"][-1]),
               "wall_min": round(float(np.mean([r[1].get("wall_sec", 0) for r in runs])) / 60, 1)}
        for k in keys:
            vals = np.array([c[k][-1] for _, _, c in runs])
            mean, half = mean_ci(vals)
            row[k] = float(mean)
            row[k + "_ci"] = float(half)
            row[k + "_seeds"] = " ".join(f"{v:.2f}" for v in vals)
        rows.append(row)

    with open(out_dir / "summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    lines = ["# 실험 결과 요약", "",
             "값은 마지막 평가 시점의 평균 ± 95% 신뢰구간(t 분포, 표본 단위는 학습 seed)이다.", "",
             "| 그룹 | seed 수 | vs random | vs easy | vs hard | 스파이크/점 | 다이빙/점 | 학습 시간(분) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        cell = lambda k, fmt=".2f": f"{r[k]:{fmt}} ± {r[k + '_ci']:{fmt}}"
        lines.append(f"| {r['group']} | {r['n_seeds']} | {cell('wr_random')} | {cell('wr_easy')} | "
                     f"{cell('wr_hard')} | {cell('spikes')} | {cell('dives')} | {r['wall_min']} |")
    lines += ["", "## seed별 어려움 봇 상대 승률", "", "| 그룹 | seed별 값 |", "|---|---|"]
    lines += [f"| {r['group']} | {r['wr_hard_seeds']} |" for r in rows]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 최종 승률 막대그래프
    styles = style_for(groups)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.8 / len(rows)
    for i, r in enumerate(rows):
        x = np.arange(len(OPPONENTS)) + i * width
        ax.bar(x, [r[f"wr_{o}"] for o in OPPONENTS], width,
               yerr=[r[f"wr_{o}_ci"] for o in OPPONENTS], capsize=3,
               color=styles[r["group"]][0], alpha=0.55 + 0.45 * (i % 2 == 0),
               edgecolor="black", lw=0.5, label=r["group"])
    ax.set_xticks(np.arange(len(OPPONENTS)) + 0.4 - width / 2)
    ax.set_xticklabels([f"vs {o} bot" for o in OPPONENTS])
    ax.set_ylabel("Win rate")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.5, color="gray", lw=0.8, ls=":")
    ax.set_title("Final win rate vs fixed bots (mean ± 95% CI)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "final_winrate.png", dpi=150)
    plt.close(fig)
    return rows


def plot_league(league_file, out_dir):
    data = json.loads(Path(league_file).read_text(encoding="utf-8"))
    players = data["players"]
    wins = np.array(data["wins"])
    group_names = list(dict.fromkeys(p["group"] for p in players))
    members = {g: [i for i, p in enumerate(players) if p["group"] == g] for g in group_names}

    # 그룹 대 그룹 승률: 그룹에 속한 선수들의 승수를 합쳐서 계산한다
    n = len(group_names)
    mat = np.full((n, n), np.nan)
    for a, ga in enumerate(group_names):
        for b, gb in enumerate(group_names):
            w = sum(wins[i, j] for i in members[ga] for j in members[gb] if i != j)
            l = sum(wins[j, i] for i in members[ga] for j in members[gb] if i != j)
            if w + l > 0:
                mat[a, b] = w / (w + l)

    fig, ax = plt.subplots(figsize=(1.1 * n + 3, 0.9 * n + 2.5))
    im = ax.imshow(mat, cmap="RdBu", vmin=0, vmax=1)
    ax.set_xticks(range(n))
    ax.set_xticklabels(group_names, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(group_names)
    for a in range(n):
        for b in range(n):
            if not np.isnan(mat[a, b]):
                ax.text(b, a, f"{mat[a, b]:.2f}", ha="center", va="center", fontsize=9,
                        color="white" if abs(mat[a, b] - 0.5) > 0.3 else "black")
    ax.set_title("League: win rate of row vs column")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(out_dir / "league_heatmap.png", dpi=150)
    plt.close(fig)

    # 그룹별 Elo (seed 간 평균 ± 95% 신뢰구간)
    order = sorted(group_names, key=lambda g: -np.mean([players[i]["elo"] for i in members[g]]))
    fig, ax = plt.subplots(figsize=(8, 0.5 * n + 2))
    for k, g in enumerate(order):
        elos = np.array([players[i]["elo"] for i in members[g]])
        mean, half = mean_ci(elos)
        algo = players[members[g][0]]["algo"]
        ax.barh(k, mean, xerr=half, capsize=3, color=COLORS.get(algo, "#333333"), alpha=0.8)
        ax.scatter(elos, np.full(len(elos), k), color="black", s=12, zorder=3)
    ax.set_yticks(range(n))
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    ax.set_xlabel("Elo (hard bot = 1000)")
    ax.set_title("League Elo (bar: mean ± 95% CI, dots: seeds)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "league_elo.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--league", default=None, help="league.json 경로 (기본: <첫 폴더>/league/league.json)")
    args = ap.parse_args()

    groups = load_runs(args.dirs)
    if not groups:
        raise SystemExit("완료된 실행을 찾지 못했어요 (model.pt와 metrics.csv 필요).")
    out_dir = Path(args.out or Path(args.dirs[0]) / "report")
    out_dir.mkdir(parents=True, exist_ok=True)

    for metric, label in (("wr_hard", "Win rate vs hard bot"), ("wr_easy", "Win rate vs easy bot"),
                          ("wr_random", "Win rate vs random bot"),
                          ("spikes", "Spikes per point"), ("dives", "Dives per point")):
        plot_curves(groups, metric, label, out_dir / f"curves_{metric}.png")
    rows = summarize(groups, out_dir)

    league = Path(args.league or Path(args.dirs[0]) / "league" / "league.json")
    if league.exists():
        plot_league(league, out_dir)
    else:
        print(f"리그전 결과가 없어 리그 그래프는 건너뜁니다: {league}")

    for r in rows:
        print(f"{r['group']:28s} n={r['n_seeds']}  vs hard {r['wr_hard']:.2f} ± {r['wr_hard_ci']:.2f}")
    print(f"저장: {out_dir}")


if __name__ == "__main__":
    main()
