"""실험 일괄 실행. 설정 × seed 조합을 여러 프로세스로 동시에 돌린다.

예)
  python -m experiments.run e1                 # 알고리즘 비교 (15회 학습)
  python -m experiments.run e1 e2 --parallel 12
  python -m experiments.run e1 --seeds 0 1 --steps 300000   # 빠른 시험 실행

이미 끝난 실행(model.pt가 있는 폴더)은 건너뛰므로, 중간에 끊겨도 다시 실행하면 이어진다.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

SEEDS = [0, 1, 2, 3, 4]
ALGOS = ["ppo", "dqn", "sac"]

# 실험 이름 -> [(실행 이름, 알고리즘, 덮어쓸 설정)]
EXPERIMENTS = {
    # E1 알고리즘 비교: 확장 행동(18개), 기본 하이퍼파라미터
    "e1": [(a, a, {}) for a in ALGOS],
    # E2 행동 공간: 기본 행동(6개: 이동·점프만). E1과 비교한다
    "e2": [(f"{a}_basic", a, {"action_set": "basic"}) for a in ALGOS],
    # E3 하이퍼파라미터: PPO entropy 계수. 기본값 0.01은 E1의 ppo와 같다
    "e3": [("ppo_ent0", "ppo", {"ent_coef": 0.0}),
           ("ppo_ent0.03", "ppo", {"ent_coef": 0.03})],
    # E4 보조 보상: 공을 넘길 때마다 +0.1
    "e4": [("ppo_shaping", "ppo", {"shaping": 0.1})],
    # P1 예비 실험: 본 실험 전에 PPO 설정을 점검한다 (seed 0, 1만 사용)
    "p1": [("ppo_base", "ppo", {}),
           ("ppo_noanneal", "ppo", {"anneal_lr": "false"}),
           ("ppo_lr1e-3", "ppo", {"lr": 1e-3}),
           ("ppo_nsteps128", "ppo", {"n_steps": 128}),
           ("ppo_epochs10", "ppo", {"epochs": 10}),
           ("ppo_mb8", "ppo", {"minibatches": 8}),
           ("ppo_gamma0.995", "ppo", {"gamma": 0.995}),
           ("ppo_hidden128", "ppo", {"hidden": 128})],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("experiments", nargs="+", choices=sorted(EXPERIMENTS))
    ap.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    ap.add_argument("--parallel", type=int, default=12, help="동시에 돌릴 학습 수")
    ap.add_argument("--steps", type=int, default=None, help="total_steps 덮어쓰기 (시험용)")
    ap.add_argument("--root", default="runs")
    args = ap.parse_args()

    jobs = []
    for exp in args.experiments:
        for name, algo, overrides in EXPERIMENTS[exp]:
            for seed in args.seeds:
                out = Path(args.root) / exp / f"{name}_seed{seed}"
                if (out / "model.pt").exists():
                    print(f"건너뜀 (완료됨): {out}")
                    continue
                settings = dict(overrides)
                if args.steps:
                    settings["total_steps"] = args.steps
                cmd = [sys.executable, "train.py", "--algo", algo, "--seed", str(seed),
                       "--out", str(out)]
                if settings:
                    cmd += ["--set"] + [f"{k}={v}" for k, v in settings.items()]
                jobs.append((out, cmd))

    print(f"학습 {len(jobs)}개를 최대 {args.parallel}개씩 동시에 실행합니다.")
    running, failed, start = [], [], time.time()
    while jobs or running:
        while jobs and len(running) < args.parallel:
            out, cmd = jobs.pop(0)
            out.mkdir(parents=True, exist_ok=True)
            log = open(out / "log.txt", "w", encoding="utf-8")
            running.append((out, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT), log))
            print(f"시작: {out}", flush=True)
        time.sleep(2)
        for item in running[:]:
            out, proc, log = item
            if proc.poll() is None:
                continue
            running.remove(item)
            log.close()
            minutes = (time.time() - start) / 60
            if proc.returncode == 0:
                print(f"완료: {out}  (경과 {minutes:.0f}분, 남은 대기 {len(jobs)}개)", flush=True)
            else:
                failed.append(out)
                print(f"실패: {out}  → {out / 'log.txt'} 확인", flush=True)
    print(f"\n전체 종료. 경과 {(time.time() - start) / 60:.0f}분, 실패 {len(failed)}개")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
