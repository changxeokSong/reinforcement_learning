"""레이저 미션 실험 일괄 실행. 설정 × seed 조합을 여러 프로세스로 동시에 돌린다.

예)
  .venv-unity\Scripts\python -m laser.experiments x1 x2 x3 x4 --parallel 8

이미 끝난 실행(model.pt가 있는 폴더)은 건너뛴다. 학습은 Build를 복사한 runs/laser_bin_*/에서 돌리므로,
학습 중에도 Unity 프로젝트를 고치고 다시 빌드할 수 있다.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from laser.env import DEFAULT_BUILD

SEEDS = [0, 1, 2]
RANDOM_CAMPAIGN = {
    "max_level": 10,
    "total_steps": 12_000_000,
    "eval_levels": list(range(1, 11)),
    "campaign_layouts": True,
    "level_mix": 0.5,
    "curriculum_track_actual_level": True,
    "curriculum_deadlines": [150_000, 400_000, 800_000, 1_250_000, 1_950_000,
                             3_200_000, 4_300_000, 5_300_000, 6_250_000, 7_200_000],
}
REFACTOR_CAMPAIGN = {
    "total_steps": 1_048_576,
    "level": "random",
    "max_level": 10,
    "eval_levels": list(range(1, 11)),
    "campaign_layouts": False,
    "level6_design": 2,
    "eval_interval": 262_144,
    "eval_rounds": 2,
    "final_rounds": 10,
}
REFACTOR_STUDIES = {
    "refactor": REFACTOR_CAMPAIGN,
    "refactor_curriculum": {
        **REFACTOR_CAMPAIGN,
        "level": "curriculum",
        "level_mix": 0.5,
        "curriculum_track_actual_level": True,
        "curriculum_promote_on_success": False,
        "curriculum_deadlines": [32_768, 147_456, 262_144, 376_832, 491_520,
                                 606_208, 720_896, 802_816, 884_736, 966_656],
    },
}
REFACTOR_ALGOS = {
    "ppo": {"hidden": 128},
    "dqn": {"hidden": 128, "batch_size": 128, "train_freq": 16},
    "sac": {"hidden": 128, "batch_size": 128, "train_freq": 16, "grad_clip": 10.0, "target_clip": 3.0},
}
EXPERIMENTS = {
    **{name: [(algo, algo, {**common, **settings}) for algo, settings in REFACTOR_ALGOS.items()]
       for name, common in REFACTOR_STUDIES.items()},
    # X1 알고리즘 비교: 커리큘럼 학습
    "x1": [(a, a, {}) for a in ["ppo", "dqn", "sac"]],
    # X2 학습 방식: 레벨 무작위 / 처음부터 레벨 4 (커리큘럼은 X1의 ppo와 공유)
    "x2": [("ppo_random", "ppo", {"level": "random"}),
           ("ppo_level4", "ppo", {"level": 4}),
           ("ppo_curmix", "ppo", {"level_mix": 0.5})],
    # X3 관측 설계: 원시 선분 좌표 (설계한 특징은 X1의 ppo와 공유)
    "x3": [("ppo_rawobs", "ppo", {"obs_mode": 0})],
    # X4 보상 설계: 시간 벌점 없음 / 보조 보상 없음
    "x4": [("ppo_notimepen", "ppo", {"time_penalty": 0.0}),
           ("ppo_noshaping", "ppo", {"shaping": 0.0})],
    # X5 학습량: PPO가 400만 스텝에서 멈춘 것이 학습량 부족 때문인지 (SAC는 400만에서 0.9 이상)
    "x5": [("ppo_random_20m", "ppo", {"level": "random", "total_steps": 20_000_000})],
    # X6 SAC 안정화: X1에서 seed 1의 Q값이 발산했다 → 기울기 노름 상한
    "x6": [("sac_clip", "sac", {"grad_clip": 10.0})],
    # X7 X6에서도 레벨이 오를 때 발산 → 목표값도 실제 가능한 범위(보상 합 |G| < 3)로 자른다
    "x7": [("sac_clip2", "sac", {"grad_clip": 10.0, "target_clip": 3.0})],
    # X8 레벨 5 (겹친 레이저, 움직이는 통로가 있는 레이저 벽, 레이저 10개): 가장 좋았던 두 설정
    "x8": [("sac_l5", "sac", {"grad_clip": 10.0, "target_clip": 3.0, "max_level": 5,
                              "eval_levels": [1, 2, 3, 4, 5]}),
           ("ppo_l5", "ppo", {"level": "random", "max_level": 5, "total_steps": 20_000_000,
                              "eval_levels": [1, 2, 3, 4, 5]})],
    "x9": [("sac_l5_review", "sac", {"grad_clip": 10.0, "target_clip": 3.0, "max_level": 5,
                                     "eval_levels": [1, 2, 3, 4, 5],
                                     "level_mix": 0.25, "level_mix_from": 5, "level_mix_target": 4})],
    "x10": [("sac_all_levels", "sac", {"grad_clip": 10.0, "target_clip": 3.0, "max_level": 6,
                                        "total_steps": 8_000_000, "eval_levels": [1, 2, 3, 4, 5, 6],
                                        "level_mix": 0.5, "curriculum_track_actual_level": True,
                                        "curriculum_deadlines": [160_000, 450_000, 850_000, 1_250_000,
                                                                 2_000_000, 4_500_000]})],
    "x11": [("sac_random_campaign", "sac", {**RANDOM_CAMPAIGN, "grad_clip": 10.0, "target_clip": 3.0})],
    "x12": [(f"{algo}_random_campaign", algo, RANDOM_CAMPAIGN) for algo in ("ppo", "dqn")],
    # X13 같은 예산 비교: 최종 학생의 선생님들에 쓰인 강화학습 합계(5,250만 스텝)를 정책 하나에 모두 준다
    "x13": [("ppo_random_campaign_52m", "ppo", {**RANDOM_CAMPAIGN, "total_steps": 52_500_000, "eval_interval": 500_000})],
}
COST = {"ppo": 1, "dqn": 3, "sac": 5}


def build_digest(folder):
    """Unity 실행 파일, 관리 어셈블리 및 장면 데이터를 함께 식별한다."""
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if not path.is_file() or any("DoNotShip" in part for part in relative.parts):
            continue
        # ML-Agents rewrites these diagnostics on shutdown. Hash packaged files only.
        if path.suffix == ".log" or ("ML-Agents" in relative.parts and "Timers" in relative.parts):
            continue
        file_digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                file_digest.update(chunk)
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update(file_digest.digest())
    return digest.hexdigest()


def prepare_build(root):
    """내용이 같은 빌드만 재사용하고 실행 중인 복사본을 덮어쓰지 않는다."""
    if not DEFAULT_BUILD.is_file():
        raise FileNotFoundError(DEFAULT_BUILD)
    src = DEFAULT_BUILD.parent
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    digest = build_digest(src)
    dst = root / f"laser_bin_{digest}"
    if not dst.exists():
        with tempfile.TemporaryDirectory(dir=root) as temp:
            copied = Path(temp) / "build"
            shutil.copytree(src, copied, ignore=shutil.ignore_patterns("*DoNotShip*"))
            if build_digest(copied) != digest:
                raise RuntimeError("Unity 빌드가 복사 중에 바뀌었습니다. 빌드가 끝난 후 다시 실행하세요.")
            try:
                copied.rename(dst)
            except OSError:
                if not dst.is_dir():
                    raise
                # 다른 실험 프로세스가 같은 빌드의 복사본을 먼저 공개했다.
    return dst / DEFAULT_BUILD.name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("experiments", nargs="+", choices=sorted(EXPERIMENTS))
    ap.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--sac-device", choices=["cpu", "cuda"], help="SAC 신경망을 학습할 장치")
    ap.add_argument("--build", type=Path, help="이미 보존된 Unity 실행 파일을 사용")
    ap.add_argument("--root", default="runs")
    ap.add_argument("--worker-base", type=int, default=200, help="다른 실험과 동시에 돌릴 때 겹치지 않게")
    args = ap.parse_args()

    build = args.build.resolve() if args.build else prepare_build(args.root)
    if not build.is_file():
        ap.error(f"Unity 실행 파일이 없습니다: {build}")
    jobs = []
    for exp in args.experiments:
        for name, algo, overrides in EXPERIMENTS[exp]:
            for seed in args.seeds:
                out = Path(args.root) / "laser" / exp / f"{name}_seed{seed}"
                if (out / "model.pt").exists():
                    if exp in REFACTOR_STUDIES:
                        config = json.loads((out / "config.json").read_text(encoding="utf-8"))
                        expected = {**REFACTOR_STUDIES[exp], "build": str(build)}
                        if args.steps:
                            expected["total_steps"] = args.steps
                        if (not config.get("finished") or config["algo"] != algo or config["seed"] != seed
                            or any(config["common"][key] != value for key, value in expected.items())):
                            raise SystemExit(f"Existing model does not match this build or study: {out}")
                    if exp in ("x8", "x9", "x10", "x11", "x12", "x13"):
                        config = json.loads((out / "config.json").read_text(encoding="utf-8"))
                        expected_level = overrides["max_level"]
                        if expected_level not in config.get("verified_eval_levels", []):
                            raise SystemExit(
                                f"레벨 {expected_level} 미검증 결과가 있습니다: {out}. "
                                "--root로 새 결과 폴더를 지정하세요."
                            )
                    print(f"건너뜀 (완료됨): {out}")
                    continue
                settings = {"build": str(build), **overrides}
                if algo == "sac" and args.sac_device:
                    settings["device"] = args.sac_device
                if args.steps:
                    settings["total_steps"] = args.steps
                jobs.append((COST[algo], out, algo, seed, settings))
    jobs.sort(key=lambda j: -j[0])
    print(f"학습 {len(jobs)}개를 최대 {args.parallel}개씩 동시에 실행합니다.", flush=True)

    running, failed, start, slot = [], [], time.time(), 0
    free_workers = list(range(args.worker_base, args.worker_base + 4 * args.parallel, 4))
    while jobs or running:
        while jobs and len(running) < args.parallel:
            _, out, algo, seed, settings = jobs.pop(0)
            worker = free_workers.pop(0)
            out.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-u", "-m", "laser.train", "--algo", algo, "--seed", str(seed),
                   "--out", str(out), "--worker", str(worker),
                   "--set"] + [f"{k}={json.dumps(v)}" for k, v in settings.items()]
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
