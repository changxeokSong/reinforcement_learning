"""최종 빌드 학습 곡선: 기본 설정과 튜닝 설정, 스텝 기준과 학습 시간 기준 (학습 seed 3~7).

학습 중 평가(단계마다 20판)의 1~10단계 평균 성공률이다. 띠는 seed 5개의 95% t 신뢰구간이다.
학습 시간은 같은 PC에서 9~13개를 동시에 돌린 기록이라 상대 비교로 본다.

  python -m laser.tuned_curves   → docs/figures/laser_tuned_curves.png
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
ROOT = Path("runs/laser")
SEEDS = [3, 4, 5, 6, 7]
GROUPS = [
    ("DQN 기본", "refactor_curriculum/dqn", "#e76f51", "--"),
    ("PPO 기본", "refactor_curriculum/ppo", "#4361ee", "--"),
    ("SAC 기본", "refactor_curriculum/sac", "#1fa99b", "--"),
    ("PPO 튜닝", "confirm/ppo_tuned", "#4361ee", "-"),
    ("SAC 튜닝", "confirm/sac_tuned", "#1fa99b", "-"),
    ("PPO 튜닝 1,600만", "confirm/ppo_tuned_16m", "#7b2cbf", "-"),
]
EXTRA = [("PPO 튜닝 4,800만", "long2/ppo_tuned_48m", "#e5383b", "-"),
         ("SAC 튜닝 420만", "long2/sac_tuned_4m", "#f4a261", "-")]


def load(group):
    runs = []
    for seed in SEEDS:
        path = ROOT / f"{group}_seed{seed}" / "metrics.csv"
        if not (path.parent / "model.pt").is_file():
            return None
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        runs.append([(int(r["step"]), float(r["wall_sec"]) / 60,
                      np.mean([float(r[f"success_l{i}"]) for i in range(1, 11)]) * 100) for r in rows])
    n = min(len(r) for r in runs)
    arr = np.array([r[:n] for r in runs])  # seed × 시점 × (스텝, 분, 성공률)
    return arr


def band(ax, x, y, color, ls, label):
    m = y.mean(0)
    h = stats.t.ppf(0.975, len(y) - 1) * y.std(0, ddof=1) / np.sqrt(len(y))
    ax.plot(x, m, color=color, ls=ls, lw=2, label=label)
    ax.fill_between(x, m - h, m + h, color=color, alpha=0.12)


def main():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    for name, group, color, ls in GROUPS + EXTRA:
        arr = load(group)
        if arr is None:
            continue
        steps, minutes, success = arr[..., 0].mean(0) / 1e6, arr[..., 1].mean(0), arr[..., 2]
        if steps[-1] <= 1.1:
            band(a1, steps, success, color, ls, name)
        band(a2, minutes, success, color, ls, name)
    a1.set_xlabel("환경 스텝 (백만)")
    a1.set_title("같은 스텝 (105만)")
    a2.set_xlabel("학습 시간 (분, 동시 실행 기준)")
    a2.set_title("같은 시간")
    for ax in (a1, a2):
        ax.set_ylabel("1~10단계 평균 성공률 (%)")
        ax.set_ylim(0, 70)
        ax.grid(alpha=0.3)
    a1.legend(fontsize=9, loc="upper left", frameon=False)
    a2.legend(fontsize=9, loc="upper left", frameon=False)
    fig.tight_layout()
    out = Path("docs/figures/laser_tuned_curves.png")
    fig.savefig(out, dpi=150)
    print("→", out)


if __name__ == "__main__":
    main()
