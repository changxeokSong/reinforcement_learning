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
    "x5_steps": ["x2/ppo_random", "x5/ppo_random_20m"],
    "x6_sac_stability": ["x1/sac", "x6/sac_clip", "x7/sac_clip2"],
    "x8_level5": ["x8/sac_l5", "x8/ppo_l5"],
    "x9_level4_review": ["x8/sac_l5", "x9/sac_l5_review"],
    "x10_all_levels": ["x10/sac_all_levels"],
    "x11_random_campaign": ["x11/sac_random_campaign"],
}
LABELS = {
    "x1/ppo": "PPO (curriculum)", "x1/dqn": "DQN (curriculum)", "x1/sac": "SAC (curriculum)",
    "x2/ppo_random": "PPO random level", "x2/ppo_curmix": "PPO curriculum + review", "x2/ppo_level4": "PPO level 4 only",
    "x3/ppo_rawobs": "PPO raw observation",
    "x4/ppo_notimepen": "PPO no time penalty", "x4/ppo_noshaping": "PPO no shaping",
    "x5/ppo_random_20m": "PPO random level 20M",
    "x6/sac_clip": "SAC + grad clip", "x7/sac_clip2": "SAC + grad clip + target clip",
    "x8/sac_l5": "SAC level 1-5 (curriculum)", "x8/ppo_l5": "PPO level 1-5 random 20M",
    "x9/sac_l5_review": "SAC + 25% level 4 review at level 5",
    "x10/sac_all_levels": "SAC all levels + 50% review",
    "x11/sac_random_campaign": "SAC randomized campaign",
    "x12/ppo_random_campaign": "PPO randomized campaign",
    "x12/dqn_random_campaign": "DQN randomized campaign",
}
LINESTYLES = ["-", "--", ":", "-."]


def load(root):
    groups = defaultdict(list)
    for final in sorted(Path(root).glob("x*/*_seed*/final.json")):
        run = final.parent
        group = f"{run.parent.name}/{run.name.rsplit('_seed', 1)[0]}"
        cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
        expected_level = {"x8": 5, "x9": 5, "x10": 6, "x11": 10, "x12": 10}.get(run.parent.name)
        if expected_level is not None and expected_level not in cfg.get("verified_eval_levels", []):
            print(f"제외 (레벨 {expected_level} 실행 미검증): {run}")
            continue
        with (run / "metrics.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        groups[group].append({
            "final": json.loads(final.read_text(encoding="utf-8")),
            "metrics": rows,
            "minutes": cfg.get("wall_sec", float("nan")) / 60,
            "algo": cfg["algo"],
            "seed": cfg["seed"],
        })
    return groups


def curve(runs, key, levels=LEVELS):
    steps = np.array([int(r["step"]) for r in runs[0]["metrics"]])
    n = min(len(r["metrics"]) for r in runs)
    vals = np.array([[_mean_success(row, levels) if key == "mean" else float(row[key]) for row in r["metrics"][:n]]
                     for r in runs])
    return steps[:n], vals


def _mean_success(row, levels=LEVELS):
    return float(np.mean([float(row[f"success_l{lv}"]) for lv in levels]))


def levels_of(groups, names):
    """모든 실행에 공통으로 기록된 평가 레벨을 선택한다."""
    return LEVELS + [level for level in range(5, 11)
                     if all(f"success_l{level}" in r["final"] for g in names for r in groups[g])]


def fmt(values, precision=2):
    m, h = mean_ci(values)
    return f"{m:.{precision}f} ± {h:.{precision}f}"


def write_summary(groups, out):
    lines = ["# 레이저 미션 결과", "",
             "학습 후 최종 평가(레벨마다 200판, 가장 좋은 행동)의 성공률. 평균 ± 95% 신뢰구간, 표본 단위는 학습 seed.", "",
             "| 설정 | seed 수 | 레벨 1 | 레벨 2 | 레벨 3 | 레벨 4 | 평균 (1~4) | 레벨 5 | 학습 시간(분) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for g, runs in sorted(groups.items(), key=lambda kv: -np.mean([r["final"]["success_mean"] for r in kv[1]])):
        cells = [fmt([r["final"][f"success_l{lv}"] for r in runs]) for lv in LEVELS]
        lines.append(f"| {LABELS.get(g, g)} | {len(runs)} | " + " | ".join(cells) +
                     f" | **{fmt([r['final']['success_mean'] for r in runs])}** | "
                     + (fmt([r["final"]["success_l5"] for r in runs], precision=3) if all("success_l5" in r["final"] for r in runs)
                        else "-") + " | "
                     f"{np.mean([r['minutes'] for r in runs]):.0f} |")
    lines += ["", "## seed별 평균 성공률 (레벨 1~4)", "", "| 설정 | 값 |", "|---|---|"]
    for g, runs in sorted(groups.items()):
        lines.append(f"| {LABELS.get(g, g)} | " + " ".join(f"{r['final']['success_mean']:.2f}" for r in runs) + " |")
    baseline = {r["seed"]: r["final"] for r in groups.get("x8/sac_l5", [])}
    review = {r["seed"]: r["final"] for r in groups.get("x9/sac_l5_review", [])}
    if set(baseline) == set(review) == {0, 1, 2}:
        lines += ["", "## X9 레벨 4 복습", "",
                  "시드별 성공률 차이(복습 − 기본)의 평균 ± 95% t 신뢰구간 반폭 (%p).", "",
                  "| 레벨 | 평균 변화 | seed 0 | seed 1 | seed 2 |", "|---|---:|---:|---:|---:|"]
        for level in (4, 5):
            key = f"success_l{level}"
            delta = [100 * (review[seed][key] - baseline[seed][key]) for seed in range(3)]
            lines.append(f"| {level} | {fmt(delta, precision=1)} | "
                         + " | ".join(f"{value:+.1f}" for value in delta) + " |")
    for name, group, max_level in (("X10", "x10/sac_all_levels", 6), ("X11", "x11/sac_random_campaign", 10)):
        all_levels = groups.get(group, [])
        if {r["seed"] for r in all_levels} != {0, 1, 2}:
            continue
        level_names = [f"레벨 {lv}" for lv in range(1, max_level + 1)]
        lines += ["", f"## {name} 전체 레벨 성공률", "",
                  "| " + " | ".join(["seed", *level_names, "평균", "최저"]) + " |",
                  "|---|" + "---:|" * (max_level + 2)]
        keys = [f"success_l{lv}" for lv in range(1, max_level + 1)] + ["success_mean_all", "success_worst_all"]
        for run in sorted(all_levels, key=lambda r: r["seed"]):
            values = [f"{run['final'][key]:.1%}" for key in keys]
            lines.append(f"| {run['seed']} | " + " | ".join(values) + " |")
        lines.append("| 평균 ± 95% CI 반폭 (%p) | "
                     + " | ".join(fmt([100 * r["final"][key] for r in all_levels], precision=1)
                                  for key in keys)
                     + " |")
        best = max(all_levels, key=lambda r: (r["final"]["success_worst_all"], r["final"]["success_mean_all"]))
        mode = "--campaign" if max_level == 10 else "--levels 1 2 3 4 5 6"
        lines += ["", f"최저 성공률을 우선한 {name} 관전 후보는 seed {best['seed']}이다.",
                  f"`python -m laser.watch runs/laser/{group}_seed{best['seed']}/model.pt {mode} --view chase`"]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot_comparison(groups, names, title, path):
    names = [n for n in names if n in groups]
    if not names:
        return
    levels = levels_of(groups, names)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    used = defaultdict(int)
    for g in names:
        runs = groups[g]
        algo = runs[0]["algo"]
        color, ls = COLORS.get(algo, "#333"), LINESTYLES[used[algo] % 4]
        used[algo] += 1
        steps, vals = curve(runs, "mean", levels)
        m, h = mean_ci(vals)
        axes[0].plot(steps / 1e6, m, color=color, ls=ls, lw=2, label=f"{LABELS.get(g, g)} (n={len(runs)})")
        axes[0].fill_between(steps / 1e6, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=color, alpha=0.15)
    axes[0].set_xlabel("training steps (M)")
    axes[0].set_ylabel(f"success rate (mean of level 1-{levels[-1]})")
    axes[0].set_ylim(0, 1)
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    axes[0].set_title(title)

    width = 0.8 / len(names)
    used = defaultdict(int)
    for k, g in enumerate(names):
        runs = groups[g]
        algo = runs[0]["algo"]
        vals = np.array([[r["final"][f"success_l{lv}"] for lv in levels] for r in runs])
        m, h = mean_ci(vals)
        x = np.arange(len(levels)) + (k - (len(names) - 1) / 2) * width
        axes[1].bar(x, m, width, yerr=h, capsize=3, color=COLORS.get(algo, "#333"),
                    alpha=0.9 - 0.25 * used[algo], edgecolor="black", lw=0.5, label=LABELS.get(g, g))
        used[algo] += 1
        for j in range(len(levels)):
            axes[1].scatter(np.full(len(runs), x[j]), vals[:, j], color="black", s=8, zorder=3)
    axes[1].set_xticks(range(len(levels)), [f"L{lv}" for lv in levels])
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
    max_level = 0
    for g in ["x1/ppo", "x1/dqn", "x1/sac", "x8/sac_l5", "x11/sac_random_campaign"]:
        for i, r in enumerate(groups.get(g, [])):
            steps = [int(row["step"]) / 1e6 for row in r["metrics"]]
            lv = [int(float(row["train_level"])) for row in r["metrics"]]
            max_level = max(max_level, max(lv, default=0))
            ax.step(steps, lv, where="post", color=COLORS[r["algo"]], alpha=0.7,
                    label=LABELS[g] if i == 0 else None)
    ax.set_xlabel("training steps (M)")
    ax.set_ylabel("training level")
    ax.set_yticks(range(max_level + 1))
    ax.grid(alpha=0.3)
    if ax.lines:
        ax.legend(fontsize=8)
    ax.set_title("curriculum progress")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_campaign_report(root, out):
    data = json.loads((out / "campaign_comparison.json").read_text(encoding="utf-8"))
    training = load(root)
    groups = defaultdict(list)
    for run in data["runs"]:
        model = Path(run["model"])
        group = f"{model.parent.parent.name}/{model.parent.name.rsplit('_seed', 1)[0]}"
        saved = next(r for r in training[group] if r["seed"] == run["seed"])
        groups[group].append({**saved, "final": run["by_level"], "campaign": run["campaign"]})
    levels = data["levels"]
    counts = data["episodes_per_level"]
    attempts = data["attempts_per_level"]
    lines = ["# 레이저 미션 알고리즘 비교", "",
             f"각 알고리즘은 같은 Unity 빌드에서 시드 0·1·2로 {data['total_steps']:,} 환경 스텝을 학습했다. "
             "최종 체크포인트에 가장 높은 점수의 행동을 적용했다.", "",
             f"레벨별 성공률은 모델당 각 레벨 {counts}판으로 측정했다. "
             f"순차 캠페인은 모델당 {counts}회 진행했고, 단계당 최대 {attempts}번 시도했다. "
             "성공하면 다음 단계로 이동하고 시도 횟수를 소진하면 해당 캠페인을 종료했다. "
             "같은 학습 시드에 속한 모델은 같은 평가 환경 시드로 시작했다. "
             "최종 평가는 게임 시간이 0인 출발 상태에서 시작한 판을 집계했다. "
             "학습 중 기록한 곡선에는 초기 이동이 포함된 종전 평가가 사용됐다.", "",
             "모든 성공률은 %이며 ± 뒤는 학습 시드 3개에 대한 95% t 신뢰구간의 반폭(%p)이다.", "",
             "| 알고리즘 | " + " | ".join(f"L{lv}" for lv in levels) + " | 레벨 평균 | 캠페인 완주 |",
             "|---|" + "---:|" * (len(levels) + 2)]
    for runs in groups.values():
        values = [[100 * r["final"][f"success_l{lv}"] for r in runs] for lv in levels]
        values += [[100 * _mean_success(r["final"], levels) for r in runs],
                   [100 * r["campaign"]["completion_rate"] for r in runs]]
        lines.append(f"| {runs[0]['algo'].upper()} | " + " | ".join(fmt(v, 1) for v in values) + " |")
    lines += ["", "## 시드별 완주 횟수", "", "| 알고리즘 | 시드 | 성공 / 전체 |",
              "|---|---:|---:|"]
    for runs in groups.values():
        for run in runs:
            result = run["campaign"]
            lines.append(f"| {run['algo'].upper()} | {run['seed']} | {result['completed']}/{result['campaigns']} |")
    (out / "campaign_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot_comparison(groups, list(groups), "Randomized campaign · SAC vs PPO vs DQN", out / "campaign_comparison.png")

    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    for runs in groups.values():
        algo = runs[0]["algo"]
        rates = [np.asarray(r["campaign"]["cleared"]) / r["campaign"]["campaigns"] for r in runs]
        mean, half = mean_ci(rates)
        ax.plot(levels, mean, marker="o", color=COLORS[algo], label=algo.upper())
        ax.fill_between(levels, np.clip(mean - half, 0, 1), np.clip(mean + half, 0, 1),
                        color=COLORS[algo], alpha=0.15)
    ax.set(title=f"Sequential campaign · up to {attempts} attempts per stage", xlabel="Stage",
           ylabel="Fraction clearing this stage", xticks=levels, ylim=(0, 1.04))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.savefig(out / "campaign_completion.png", dpi=150)
    plt.close(fig)


def write_specialists_report(out):
    special_path = out / "ppo_specialists.json"
    specialists = json.loads(special_path.read_text(encoding="utf-8"))
    baseline_path = out / "ppo_fresh_start_evaluation.json"
    series = {"Stage-specific PPO": specialists["runs"]}
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        series = {"Single-policy PPO": baseline["runs"], **series}
    levels = range(1, 11)
    lines = ["# 레이저 미션 단계별 PPO 후속 실험", "",
             "단계별 모델은 네 배치의 검증 성공률을 동일 비중으로 계산해 선택했다. "
             "선택 후 다른 환경 시드에서 단계당 최대 3회 시도하는 순차 캠페인을 평가했다. "
             "평가에 사용한 배치의 종류는 학습과 같다.", "",
             "기본 PPO는 독립적으로 학습한 세 모델을 사용했다. 단계별 PPO는 추가 학습 결과에서 고른 "
             "정책을 같은 방식으로 세 환경 시드에 평가했다. 표는 추가 학습의 기술통계 비교다.", "",
             "| 정책 | 1~10단계 평균 성공률 | 10단계 순차 완주율 | 완주 / 시도 |",
             "|---|---:|---:|---:|"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), layout="constrained")
    for index, (label, runs) in enumerate(series.items()):
        by_level = [np.mean([r["by_level"][f"success_l{lv}"] for r in runs]) for lv in levels]
        total = sum(r["campaign"]["campaigns"] for r in runs)
        cleared = np.sum([r["campaign"]["cleared"] for r in runs], axis=0)
        lines.append(f"| {label} | {np.mean(by_level):.1%} | {cleared[-1] / total:.1%} | {cleared[-1]}/{total} |")
        color = ["#445d78", COLORS["ppo"]][index] if len(series) == 2 else COLORS["ppo"]
        axes[0].plot(list(levels), by_level, marker="o", color=color, label=label)
        axes[1].plot(list(levels), cleared / total, marker="o", color=color, label=label)
    if "extended_attempts" in specialists:
        extended = [r["extended_campaign"] for r in specialists["runs"]]
        total = sum(r["campaigns"] for r in extended)
        cleared = sum(r["completed"] for r in extended)
        lines += ["", f"단계당 최대 {specialists['extended_attempts']}회 시도한 평가에서는 "
                      f"{cleared}/{total}회({cleared / total:.1%}) 완주했다."]
    axes[0].set(title="Level success from a fresh start", ylabel="Success fraction")
    axes[1].set(title="Sequential campaign (3 attempts per stage)", ylabel="Fraction clearing the stage")
    for ax in axes:
        ax.set(xlabel="Stage", xticks=list(levels), ylim=(0, 1.04))
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.savefig(out / "ppo_specialists.png", dpi=150)
    plt.close(fig)

    lines += ["", "## 선택된 모델", "", "| 단계 | 검증 성공률 | 체크포인트 |", "|---:|---:|---|"]
    for lv in levels:
        key = str(lv)
        path = specialists["models"][key]
        score = next(r["validation_rate"] for r in specialists["validation"][key] if r["model"] == path)
        lines.append(f"| {lv} | {score:.0%} | `{path}` |")
    (out / "ppo_specialists.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_progress(root, path):
    """완료 파일을 기다리지 않고 X11 평가 로그와 최신 체크포인트를 그린다."""
    from algos.common import load_policy

    roots = sorted(Path(root).glob("x11/sac_random_campaign_seed*/metrics.csv"))
    runs = []
    for metrics in roots:
        content = metrics.read_text(encoding="utf-8")
        lines = content.splitlines()
        rows = list(csv.DictReader(lines if content.endswith("\n") else lines[:-1]))
        if not rows:
            continue
        cfg = json.loads((metrics.parent / "config.json").read_text(encoding="utf-8"))
        steps = int(rows[-1]["step"])
        try:
            steps = max(steps, load_policy(metrics.parent / "latest.pt").steps or 0)
        except OSError:
            pass
        runs.append((cfg["seed"], cfg["common"]["total_steps"], steps, rows))
    if not runs:
        raise SystemExit("X11 평가 기록이 아직 없습니다")

    levels = list(range(1, 11))
    common_steps = set.intersection(*(set(int(row["step"]) for row in rows) for _, _, _, rows in runs))
    eval_step = max(common_steps)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), layout="constrained")
    width = 0.8 / len(runs)
    for i, (seed, total, steps, rows) in enumerate(runs):
        color = f"C{i}"
        axes[0].barh(i, total / 1e6, color="#e4eaf0")
        axes[0].barh(i, steps / 1e6, color=color)
        axes[0].text(total / 1e6 + 0.4, i, f"{steps:,}", va="center")
        axes[1].plot([int(row["step"]) / 1e6 for row in rows],
                     [100 * _mean_success(row, levels) for row in rows],
                     marker=".", color=color, label=f"Seed {seed}")
        snapshot = next(row for row in rows if int(row["step"]) == eval_step)
        x = np.arange(1, 11) + (i - (len(runs) - 1) / 2) * width
        axes[2].bar(x, [100 * float(snapshot[f"success_l{lv}"]) for lv in levels], width, color=color)
    axes[0].set_yticks(range(len(runs)), [f"Seed {seed}" for seed, _, _, _ in runs])
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, max(run[1] for run in runs) / 1e6 * 1.25)
    axes[0].set_xlabel("Steps (millions)")
    axes[0].set_title("Latest saved checkpoints")
    axes[1].set_title("Mean success across L1–L10")
    axes[1].set_xlabel("Evaluated steps (millions)")
    axes[1].set_xlim(left=0)
    axes[1].legend(loc="upper left")
    axes[2].set_title(f"Success by level at {eval_step:,} steps")
    axes[2].set_xticks(levels)
    axes[2].set_xlabel("Level")
    for ax in axes[1:]:
        ax.set_ylim(0, 100)
        ax.set_ylabel("Success (%)")
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
    fig.suptitle("X11 · Randomized campaign training progress", fontsize=14, fontweight="bold")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default="runs/laser")
    ap.add_argument("--out", default="runs/results/laser")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--progress", action="store_true", help="학습 중인 X11 진행 그래프를 만든다")
    mode.add_argument("--campaign", action="store_true", help="X11/X12 최종 캠페인 비교 표와 그래프를 만든다")
    mode.add_argument("--specialists", action="store_true", help="단계별 PPO의 순차 캠페인 평가를 정리한다")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.specialists:
        write_specialists_report(out)
        print(f"저장: {out / 'ppo_specialists.md'}")
        return
    if args.campaign:
        write_campaign_report(args.root, out)
        print(f"저장: {out / 'campaign_comparison.md'}")
        return
    if args.progress:
        path = out / "x11_progress.png"
        plot_progress(args.root, path)
        print(f"저장: {path}")
        return
    groups = load(args.root)
    if not groups:
        raise SystemExit("끝난 실행이 없습니다 (final.json)")
    write_summary(groups, out)
    for name, names in COMPARISONS.items():
        if name in ("x9_level4_review", "x10_all_levels", "x11_random_campaign") and not all(
            {r["seed"] for r in groups.get(group, [])} == {0, 1, 2} for group in names
        ):
            continue
        plot_comparison(groups, names, name, out / f"{name}.png")
    plot_curriculum(groups, out / "curriculum.png")
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
