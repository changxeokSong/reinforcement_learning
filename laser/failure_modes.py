"""실패 방식 분해(성공·충돌·시간 초과)와 DQN의 Q값 추이를 그린다.

  python -m laser.failure_modes   → docs/figures/laser_failure_modes.png, runs/results/laser/failure_modes.json
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
ROOT = Path("runs/laser")
GROUPS = [
    ("PPO", "refactor_curriculum/ppo"),
    ("SAC", "refactor_curriculum/sac"),
    ("SAC 갱신 4배", "hp_sac/sac_train_freq4"),
    ("DQN", "refactor_curriculum/dqn"),
    ("DQN 조합", "hp_dqn/dqn_combo"),
    ("PPO γ=0.95", "hp_ppo/ppo_gamma0.95"),
    ("SAC γ=0.95", "hp_sac/sac_gamma0.95"),
]
LEVELS = range(1, 11)
Q_MAX = 1.0 + 0.5  # 도착 보상 + 전진 보조 보상 합. 시간 벌점을 빼면 실제 최대 리턴은 이보다 작다


def modes(group):
    out = []
    for seed in range(3):
        d = json.loads((ROOT / f"{group}_seed{seed}" / "final.json").read_text(encoding="utf-8"))
        out.append([np.mean([d[f"{k}_l{i}"] for i in LEVELS]) for k in ("success", "hit", "timeout")])
    return np.mean(out, axis=0)


def main():
    table = {name: modes(group).tolist() for name, group in GROUPS}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.3, 1]})
    names = list(table)
    vals = np.array([table[n] for n in names]) * 100
    left = np.zeros(len(names))
    for j, (label, color) in enumerate([("성공", "#2a9d8f"), ("충돌", "#e76f51"), ("시간 초과", "#8d99ae")]):
        ax1.barh(names, vals[:, j], left=left, color=color, label=label)
        for i, v in enumerate(vals[:, j]):
            if v >= 6:
                ax1.text(left[i] + v / 2, i, f"{v:.0f}", ha="center", va="center", color="white", fontsize=9)
        left += vals[:, j]
    ax1.invert_yaxis()
    ax1.set_xlim(0, 100)
    ax1.set_xlabel("1~10단계 평균 비율 (%, 학습 seed 0~2)")
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False)

    for name, color in [("dqn_base", "#e76f51"), ("dqn_combo", "#2a9d8f")]:
        for seed in range(3):
            rows = list(csv.DictReader(open(ROOT / "dqn_diag" / f"{name}_seed{seed}" / "metrics.csv", encoding="utf-8")))
            rows = [r for r in rows if r["q_mean"]]
            ax2.plot([int(r["step"]) / 1e6 for r in rows], [float(r["q_mean"]) for r in rows], color=color, alpha=0.8,
                     label=("기존 DQN" if name == "dqn_base" else "조합: 갱신 4배 + ε 기간 2배 + 목표값 ±3") if seed == 0 else None)
    ax2.axhline(Q_MAX, color="#495057", ls="--", lw=1)
    ax2.text(0.02, Q_MAX + 0.05, "가능한 최대 리턴 1.5", fontsize=9, color="#495057")
    ax2.set_xlabel("환경 스텝 (백만)")
    ax2.set_ylabel("학습 배치의 평균 Q값")
    ax2.legend(loc="upper left", fontsize=9, frameon=False)
    fig.tight_layout()
    out = Path("docs/figures/laser_failure_modes.png")
    fig.savefig(out, dpi=150)
    Path("runs/results/laser/failure_modes.json").write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    for n in names:
        print(n, " ".join(f"{100 * v:.1f}" for v in table[n]))
    print("→", out)


if __name__ == "__main__":
    main()
