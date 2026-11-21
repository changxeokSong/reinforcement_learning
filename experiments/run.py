"""실험 일괄 실행. 설정 × seed 조합을 여러 프로세스로 동시에 돌린다.

예)
  python -m experiments.run e1                 # 알고리즘 비교 (15회 학습)
  python -m experiments.run e1 e2 --parallel 12
  python -m experiments.run e1 --seeds 0 1 --steps 300000   # 빠른 시험 실행
  python -m experiments.run e1 e8@5-9           # e8만 seed 5~9로 (실험@seed 범위)

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
    # E5 같은 시간 비교: PPO에 4배 스텝(1200만)을 준다. 실제 학습 시간이 DQN과 비슷해진다
    "e5": [("ppo_12m", "ppo", {"total_steps": 12_000_000})],
    # E6 SAC 목표 엔트로피 비율. 기본값 0.3은 E1의 sac와 같다
    "e6": [("sac_ent0.1", "sac", {"target_entropy_ratio": 0.1}),
           ("sac_ent0.5", "sac", {"target_entropy_ratio": 0.5})],
    # E7 DQN 탐험 기간(epsilon을 줄이는 구간). 기본값 0.3은 E1의 dqn과 같다
    "e7": [("dqn_eps0.1", "dqn", {"eps_fraction": 0.1}),
           ("dqn_eps0.5", "dqn", {"eps_fraction": 0.5})],
    # E8 학습 상대 구성(PPO): self-play 비율 0.3 / 0.9. 나머지는 쉬움·무작위 봇이 반씩. 기본값 0.6은 E1과 같다
    "e8": [("ppo_self0.3", "ppo", {"opp_self": 0.3, "opp_easy": 0.35, "opp_random": 0.35}),
           ("ppo_self0.9", "ppo", {"opp_self": 0.9, "opp_easy": 0.05, "opp_random": 0.05})],
    # E9 같은 시간 약 1시간: PPO 1800만, SAC 140만 스텝 (DQN 300만은 E1, 약 56분)
    "e9": [("ppo_18m", "ppo", {"total_steps": 18_000_000}),
           ("sac_1.4m", "sac", {"total_steps": 1_400_000})],
    # E10 같은 시간 약 2시간: PPO 3600만, DQN 600만 스텝 (SAC 300만은 E1, 약 2시간)
    "e10": [("ppo_36m", "ppo", {"total_steps": 36_000_000}),
            ("dqn_6m", "dqn", {"total_steps": 6_000_000})],
    # E11 학습률: 세 알고리즘 모두 1e-4 / 1e-3. 기본값 3e-4는 E1과 같다
    "e11": [(f"{a}_lr{lr}", a, {"lr": lr}) for a in ALGOS for lr in ("1e-4", "1e-3")],
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
    ap.add_argument("experiments", nargs="+", help=f"실험 이름 또는 실험@seed범위 (예: e1@5-9). 실험: {', '.join(EXPERIMENTS)}")
    ap.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    ap.add_argument("--parallel", type=int, default=12, help="동시에 돌릴 학습 수")
    ap.add_argument("--steps", type=int, default=None, help="total_steps 덮어쓰기 (시험용)")
    ap.add_argument("--root", default="runs")
    args = ap.parse_args()

    jobs = []
    for spec in args.experiments:
        exp, _, seed_range = spec.partition("@")
        if exp not in EXPERIMENTS:
            ap.error(f"모르는 실험: {exp}")
        seeds = args.seeds
        if seed_range:
            lo, _, hi = seed_range.partition("-")
            seeds = list(range(int(lo), int(hi or lo) + 1))
        for name, algo, overrides in EXPERIMENTS[exp]:
            for seed in seeds:
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
                # 대략적인 소요 시간 (PPO 300만 스텝 = 1). 오래 걸리는 것부터 시작해야 전체가 빨리 끝난다
                cost = {"sac": 12, "dqn": 5, "ppo": 1}[algo] * settings.get("total_steps", 3_000_000) / 3_000_000
                jobs.append((cost, out, cmd))

    jobs = [(out, cmd) for _, out, cmd in sorted(jobs, key=lambda j: -j[0])]
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
