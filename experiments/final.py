"""모든 실험을 돌리고 결과를 한 번에 정리한다. 중간에 끊겨도 다시 실행하면 이어서 한다.

실행: python -m experiments.final [--parallel 14] [--seeds 0 1 2 3 4]

결과 (runs/results/)
  league/                 전체 리그전 (모든 모델 + 봇)
  e1_algorithms/          E1 알고리즘 비교
  e2_action_space/        E1 + E2 행동 공간 비교
  e3_entropy/             E1 PPO + E3 entropy 계수 비교
  e4_shaping/             E1 PPO + E4 보조 보상
  e5_same_time/           E1 + E5 같은 시간 비교
  e6_sac_entropy/         E1 + E6 SAC 목표 엔트로피
  e7_dqn_epsilon/         E1 + E7 DQN 탐험 기간
  e8_opponents/           E1 + E8 학습 상대 구성
  e9_e10_same_time/       E1 + E5 + E9 + E10 같은 시간 비교 (약 35분, 1시간, 2시간)
  e11_learning_rate/      E1 + E11 학습률
  dashboard.html          전체 대시보드
"""
import argparse
import subprocess
import sys
import time

COMPARISONS = {
    "e1_algorithms": ["runs/e1"],
    "e2_action_space": ["runs/e1", "runs/e2"],
    "e3_entropy": ["runs/e1", "runs/e3"],
    "e4_shaping": ["runs/e1", "runs/e4"],
    "e5_same_time": ["runs/e1", "runs/e5"],
    "e6_sac_entropy": ["runs/e1", "runs/e6"],
    "e7_dqn_epsilon": ["runs/e1", "runs/e7"],
    "e8_opponents": ["runs/e1", "runs/e8"],
    "e9_e10_same_time": ["runs/e1", "runs/e5", "runs/e9", "runs/e10"],
    "e11_learning_rate": ["runs/e1", "runs/e11"],
}
EXPERIMENTS = ["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "e10", "e11"]
# 결과가 애매했던 실험은 seed를 10개로 늘린다
EXTRA_SEEDS = ["e1@5-9", "e8@5-9"]


def run(args):
    print("\n$ " + " ".join(args), flush=True)
    return subprocess.call([sys.executable, *args])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--parallel", type=int, default=14)
    ap.add_argument("--seeds", nargs="*", default=["0", "1", "2", "3", "4"])
    ap.add_argument("--league-points", default="200")
    args = ap.parse_args()

    start = time.time()
    code = run(["-m", "experiments.run", *EXPERIMENTS, *EXTRA_SEEDS,
                "--seeds", *args.seeds, "--parallel", str(args.parallel)])
    if code != 0:
        print("일부 학습이 실패했습니다. 성공한 것만으로 정리합니다.", flush=True)
    print(f"\n학습 단계 끝 ({(time.time() - start) / 60:.0f}분)", flush=True)

    all_dirs = [f"runs/{e}" for e in EXPERIMENTS]
    league_path = "runs/results/league/league.json"
    league_code = run(["-m", "analysis.league", *all_dirs, "--points", args.league_points,
                       "--workers", str(args.parallel), "--out", "runs/results/league"])
    for name, dirs in COMPARISONS.items():
        run(["-m", "analysis.report", *dirs, "--out", f"runs/results/{name}",
             "--league", league_path])
    dashboard_options = ["--league", league_path] if league_code == 0 else []
    run(["-m", "analysis.dashboard", *all_dirs, "--out", "runs/results/dashboard.html", *dashboard_options])
    print(f"\n전체 끝 ({(time.time() - start) / 60:.0f}분)", flush=True)


if __name__ == "__main__":
    main()
