"""레이저 미션 실험 일괄 실행. 설정 × seed 조합을 여러 프로세스로 동시에 돌린다.

예)
  .venv-unity\Scripts\python -m laser.experiments x1 x2 x3 x4 --parallel 8

이미 끝난 실행(model.pt가 있는 폴더)은 건너뛴다. 학습은 Build를 복사한 runs/laser_bin/으로 돌리므로,
학습 중에도 Unity 프로젝트를 고치고 다시 빌드할 수 있다.
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from laser.env import DEFAULT_BUILD

SEEDS = [0, 1, 2]
EXPERIMENTS = {
    # X1 알고리즘 비교: 커리큘럼 학습
    "x1": [(a, a, {}) for a in ["ppo", "dqn", "sac"]],
    # X2 학습 방식: 레벨 무작위 / 처음부터 레벨 4 (커리큘럼은 X1의 ppo와 공유)
    "x2": [("ppo_random", "ppo", {"level": "random"}),
           ("ppo_level4", "ppo", {"level": 4})],
    # X3 관측 설계: 원시 선분 좌표 (설계한 특징은 X1의 ppo와 공유)
    "x3": [("ppo_rawobs", "ppo", {"obs_mode": 0})],
    # X4 보상 설계: 시간 벌점 없음 / 보조 보상 없음
    "x4": [("ppo_notimepen", "ppo", {"time_penalty": 0.0}),
           ("ppo_noshaping", "ppo", {"shaping": 0.0})],
}
COST = {"ppo": 1, "dqn": 3, "sac": 5}


def prepare_build(root):
    """학습용으로 실행 파일을 복사한다 (Build보다 오래됐으면 다시 복사)."""
    src = DEFAULT_BUILD.parent
    dst = Path(root) / "laser_bin"
    stamp = dst / "LaserMission.exe"
    if not stamp.exists() or stamp.stat().st_mtime < DEFAULT_BUILD.stat().st_mtime:
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*DoNotShip*"))
        shutil.copystat(DEFAULT_BUILD, stamp)
    return stamp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("experiments", nargs="+", choices=sorted(EXPERIMENTS))
    ap.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--root", default="runs")
    args = ap.parse_args()

    build = prepare_build(args.root)
    jobs = []
    for exp in args.experiments:
        for name, algo, overrides in EXPERIMENTS[exp]:
            for seed in args.seeds:
                out = Path(args.root) / "laser" / exp / f"{name}_seed{seed}"
                if (out / "model.pt").exists():
                    print(f"건너뜀 (완료됨): {out}")
                    continue
                settings = {"build": str(build), **overrides}
                if args.steps:
                    settings["total_steps"] = args.steps
                jobs.append((COST[algo], out, algo, seed, settings))
    jobs.sort(key=lambda j: -j[0])
    print(f"학습 {len(jobs)}개를 최대 {args.parallel}개씩 동시에 실행합니다.", flush=True)

    running, failed, start, slot = [], [], time.time(), 0
    free_workers = list(range(200, 200 + 4 * args.parallel, 4))
    while jobs or running:
        while jobs and len(running) < args.parallel:
            _, out, algo, seed, settings = jobs.pop(0)
            worker = free_workers.pop(0)
            out.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-u", "-m", "laser.train", "--algo", algo, "--seed", str(seed),
                   "--out", str(out), "--worker", str(worker),
                   "--set"] + [f"{k}={v}" for k, v in settings.items()]
            log = open(out / "log.txt", "w", encoding="utf-8")
            running.append((out, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT), log, worker))
            print(f"시작: {out}", flush=True)
        time.sleep(3)
        for item in running[:]:
            out, proc, log, worker = item
            if proc.poll() is None:
                continue
            running.remove(item)
            log.close()
            free_workers.append(worker)
            minutes = (time.time() - start) / 60
            if proc.returncode == 0:
                print(f"완료: {out}  (경과 {minutes:.0f}분, 대기 {len(jobs)}개)", flush=True)
            else:
                failed.append(out)
                print(f"실패: {out}  → {out / 'log.txt'}", flush=True)
    print(f"\n전체 종료. 경과 {(time.time() - start) / 60:.0f}분, 실패 {len(failed)}개", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
