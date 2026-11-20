"""모방 학습 결과 그림: (1) 단계별 성공률 비교 (2) 선생님 PPO 학습 진단 지표 (10장 슬라이드 24).

  python -m laser.imitation_report     → docs/figures/laser_imitation.png, laser_teacher_diagnostics.png
"""
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.stats import mean_ci

LEVELS = list(range(1, 11))
FIG = Path("docs/figures")


def single_rl(algo):
    d = json.load(open(f"runs/results/laser/{algo}_fresh_start_evaluation.json"))
    S = np.array([[r["by_level"][f"success_l{l}"] for l in LEVELS] for r in d["runs"]])
    comp = sum(r["campaign"]["completed"] for r in d["runs"]) / sum(r["campaign"]["campaigns"] for r in d["runs"])
    return S, comp


def student(tag):
    F = [json.load(open(f"runs/laser/imitation/{tag}_seed{s}/final.json")) for s in range(3)]
    S = np.array([[f["by_level"][f"success_l{l}"] for l in LEVELS] for f in F])
    comp = sum(f["campaign"]["completed"] for f in F) / sum(f["campaign"]["campaigns"] for f in F)
    return S, comp


def plot_success():
    groups = [("SAC (single RL policy)", *single_rl("sac"), "#2ca02c"),
              ("PPO (single RL policy)", *single_rl("ppo"), "#d62728"),
              ("student, teachers v1 (BC)", *student("bc"), "#9467bd"),
              ("student, teachers v2 (BC)", *student("bc_v2"), "#1f77b4"),
              ("student, v2 + stage-10 demo (BC)", *student("bc_v2_demo"), "#17becf")]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={"width_ratios": [3, 1]})
    w = 0.8 / len(groups)
    for k, (name, S, comp, c) in enumerate(groups):
        m, h = mean_ci(S)
        x = np.arange(len(LEVELS)) + (k - (len(groups) - 1) / 2) * w
        ax.bar(x, m, w, yerr=h, capsize=2, color=c, edgecolor="black", lw=0.4, label=name)
        bx.bar(k - (0.15 if k >= 3 else 0), comp, 0.35 if k >= 3 else 0.7, color=c, edgecolor="black", lw=0.4)
        bx.text(k - (0.15 if k >= 3 else 0), comp + 0.02, f"{comp:.0%}", ha="center", fontsize=8)
    ax.set_xticks(range(len(LEVELS)), [f"L{l}" for l in LEVELS])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("success rate (200 episodes per level, mean ± 95% CI over 3 seeds)")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(alpha=0.3, axis="y")
    ax.set_title("one policy for all 10 stages")
    one_try = json.load(open("runs/results/laser/imitation_one_try_campaign.json"))
    for k, tag in [(3, "bc_v2"), (4, "bc_v2_demo")]:
        runs = [one_try[f"{tag}_seed{s}"] for s in range(3)]
        rate = sum(r["completed"] for r in runs) / sum(r["campaigns"] for r in runs)
        bx.bar(k + 0.2, rate, 0.35, color="white", edgecolor="black", hatch="//", lw=0.6,
               label="1 try per stage" if k == 3 else None)
        bx.text(k + 0.2, rate + 0.02, f"{rate:.0%}", ha="center", fontsize=8)
    bx.legend(fontsize=7, loc="upper left")
    bx.set_xticks(range(len(groups)), ["SAC", "PPO", "v1", "v2", "v2+demo"], fontsize=9)
    bx.set_ylim(0, 1.15)
    bx.set_title("10-stage campaign completed\n(solid: 3 tries per stage, hatched: 1 try)", fontsize=10)
    bx.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "laser_imitation.png", dpi=150)
    plt.close(fig)


def plot_diagnostics():
    keys = [("eval", "success on its stage"), ("entropy", "entropy (max ln27≈3.30)"),
            ("approx_kl", "KL(old‖new) per update"), ("clip_fraction", "clip fraction"), ("v_loss", "value loss")]
    fig, axes = plt.subplots(1, len(keys), figsize=(19, 3.6))
    colors = {5: "#1f77b4", 6: "#ff7f0e", 7: "#2ca02c", 10: "#d62728"}
    for run in sorted(Path("runs/laser/specialists_v2").glob("ppo_level*_seed*")):
        lv = int(run.name.split("level")[1].split("_")[0])
        rows = list(csv.DictReader(open(run / "metrics.csv", encoding="utf-8")))[1:]
        steps = np.array([int(r["step"]) for r in rows]) / 1e6
        for ax, (key, title) in zip(axes, keys):
            col = f"success_l{lv}" if key == "eval" else key
            ax.plot(steps, [float(r[col]) for r in rows], color=colors[lv], alpha=0.8,
                    ls="-" if run.name.endswith("seed0") else "--",
                    label=f"stage {lv} seed {run.name[-1]}")
            ax.set_title(title, fontsize=10)
            ax.set_xlabel("training steps (M)")
            ax.grid(alpha=0.3)
    axes[3].set_ylim(bottom=0)
    axes[4].set_yscale("log")
    axes[0].legend(fontsize=7)
    fig.suptitle("PPO teachers for weak stages: diagnostics (Ch.10 slide 24)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "laser_teacher_diagnostics.png", dpi=140)
    plt.close(fig)




def plot_campaign_curves():
    """(왼쪽) 1~10단계 강화학습 학습 곡선과 무작위 기준선 (오른쪽) 모방 학습 회차별 성공률."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={"width_ratios": [3, 2]})
    groups = [("SAC", "x11/sac_random_campaign", "#2ca02c"), ("PPO", "x12/ppo_random_campaign", "#d62728"),
              ("DQN", "x12/dqn_random_campaign", "#7f7f7f"), ("PPO 52.5M (same budget)", "x13/ppo_random_campaign_52m", "#ff7f0e")]
    for name, group, color in groups:
        runs = [Path(f"runs/laser/{group}_seed{s}/metrics.csv") for s in range(3)]
        runs = [r for r in runs if r.exists()]
        if not runs:
            continue
        tables = [list(csv.DictReader(open(r, encoding="utf-8")))[1:] for r in runs]
        n = min(len(t) for t in tables)
        steps = np.array([int(r["step"]) for r in tables[0][:n]]) / 1e6
        vals = np.array([[np.mean([float(row[f"success_l{l}"]) for l in LEVELS]) for row in t[:n]] for t in tables])
        m, h = mean_ci(vals) if len(vals) > 1 else (vals[0], np.zeros(n))
        ax.plot(steps, m, color=color, lw=2, label=f"{name} (n={len(vals)})")
        ax.fill_between(steps, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=color, alpha=0.15)
    base = json.load(open("runs/results/laser/random_campaign_baseline.json"))
    rnd = np.mean([[r["by_level"][f"success_l{l}"] for l in LEVELS] for r in base["runs"]])
    ax.axhline(rnd, color="black", ls=":", lw=1.5, label=f"uniform random policy ({rnd:.0%})")
    ax.axhline(1.0, color="#17becf", ls="--", lw=1.5, label="imitation student, final (100%)")
    ax.set_xlabel("environment steps (M)")
    ax.set_ylabel("success rate, mean of stages 1-10")
    ax.set_ylim(-0.02, 1.05)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="center right")
    ax.set_title("single RL policy on stages 1-10 (mid-training eval, 40 episodes per stage)", fontsize=10)

    for tag, label, color, ls in [("bc", "BC, teachers v1", "#9467bd", "-"), ("dagger", "DAgger, teachers v1", "#9467bd", "--"),
                                  ("bc_v2", "BC, teachers v2", "#1f77b4", "-"), ("dagger_v2", "DAgger, teachers v2", "#1f77b4", "--"),
                                  ("bc_v2_demo", "BC, v2 + demo", "#17becf", "-"), ("dagger_v2_demo", "DAgger, v2 + demo", "#17becf", "--")]:
        logs = [json.load(open(f"runs/laser/imitation/{tag}_seed{s}/log.json")) for s in range(3)]
        it = [r["iteration"] for r in logs[0]]
        vals = np.array([[r["success_mean"] for r in lg] for lg in logs])
        m, h = mean_ci(vals)
        bx.plot(it, m, color=color, ls=ls, lw=2, marker="o", ms=3, label=label)
        bx.fill_between(it, np.clip(m - h, 0, 1), np.clip(m + h, 0, 1), color=color, alpha=0.1)
    bx.set_xlabel("DAgger / BC iteration (64k states added per iteration)")
    bx.set_ylabel("success rate, mean of stages 1-10")
    bx.set_ylim(0, 1.05)
    bx.grid(alpha=0.3)
    bx.legend(fontsize=7, loc="lower right")
    bx.set_title("imitation learning progress (3 seeds, 20 episodes per stage)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "laser_campaign_curves.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    plot_success()
    plot_diagnostics()
    plot_campaign_curves()
    print("저장:", FIG / "laser_imitation.png", FIG / "laser_teacher_diagnostics.png", FIG / "laser_campaign_curves.png")
