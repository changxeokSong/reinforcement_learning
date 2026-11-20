"""학습 중인 AI가 레이저 방을 통과하는 모습을 게임 창으로 본다.

학습(laser.train)이 20,000 스텝마다 latest.pt를 저장하고, 이 창은 한 판이 끝날 때마다
최신 모델을 다시 읽는다. 그래서 학습이 진행될수록 AI가 점점 잘하는 모습이 보인다.

예)
  .venv-unity\\Scripts\\python -m laser.watch runs/laser_test/ppo_curr
  .venv-unity\\Scripts\\python -m laser.watch runs/laser_test/ppo_curr --level 3 --speed 2
  .venv-unity\\Scripts\\python -m laser.watch runs/laser/ppo_seed0/model.pt      # 학습이 끝난 모델

창에서 V 또는 F1~F4로 시점을 바꾼다. 우클릭 드래그로 회전, 휠로 확대·축소,
Home으로 현재 시점의 각도와 확대를 초기화한다. 창을 닫거나 Ctrl+C로 끝낸다.
"""
import argparse
import json
import time
from pathlib import Path

from algos.common import load_policy
from laser.env import LaserEnv

ALGO_CODE = {"ppo": 1, "dqn": 2, "sac": 3}
CAMERA_VIEWS = ("overview", "chase", "side", "front")


def find_model(path):
    path = Path(path)
    if path.is_file():
        return path
    for name in ("latest.pt", "model.pt"):
        if (path / name).exists():
            return path / name
    return None


def current_level(run_dir):
    """학습 중인 레벨 (커리큘럼이면 metrics.csv의 마지막 기록)."""
    try:
        lines = (Path(run_dir) / "metrics.csv").read_text(encoding="utf-8").strip().splitlines()
        header, last = lines[0].split(","), lines[-1].split(",")
        lv = int(float(last[header.index("train_level")]))
        return lv if lv >= 0 else None
    except (OSError, ValueError, IndexError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("run", help="학습 폴더, .pt 파일 또는 캠페인 레벨별 모델 .json")
    level_args = ap.add_mutually_exclusive_group()
    level_args.add_argument("--level", type=int, choices=range(11), help="고정 레벨 (기본: 학습 중인 레벨, 없으면 3)")
    level_args.add_argument("--levels", type=int, choices=range(11), nargs="+", help="에피소드마다 순서대로 관전할 레벨")
    level_args.add_argument("--campaign", action="store_true", help="성공해야 다음 레벨로 진행하고 레벨 10 성공 후 종료")
    ap.add_argument("--speed", type=float, default=1.0, help="재생 배속")
    ap.add_argument("--view", choices=CAMERA_VIEWS, default="overview", help="시작 카메라 시점")
    ap.add_argument("--sample", action="store_true", help="가장 좋은 행동 대신 확률대로 고른다")
    ap.add_argument("--worker", type=int, default=90)
    args = ap.parse_args()

    run = Path(args.run)
    run_dir = run if run.is_dir() else run.parent
    manifest = None
    policy = None
    if run.suffix == ".json":
        if not args.campaign or args.sample:
            ap.error("레벨별 PPO 모델은 --campaign에서 사용할 수 있습니다")
        from laser.ppo_specialists import StagePolicy

        manifest = json.loads(run.read_text(encoding="utf-8"))
        policy = StagePolicy(manifest["models"])
        print(f"레벨별 모델: {run}")
    else:
        print("모델을 기다리는 중..." if find_model(run) is None else f"모델: {find_model(run)}")
        while find_model(run) is None:
            time.sleep(2)

    levels = list(range(1, 11)) if args.campaign else args.levels or (
        [args.level] if args.level is not None else []
    )
    level = levels[0] if levels else current_level(run_dir)
    level = 3 if level is None else level
    try:
        cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    build = manifest["build"] if manifest else cfg.get("common", {}).get("build")
    build_args = {"build": build} if build else {}
    env = LaserEnv(n_areas=1, seed=int(time.time()) % 10000, worker_id=args.worker, level=level,
                   time_scale=args.speed, graphics=True, extra_args=["-view", str(CAMERA_VIEWS.index(args.view))],
                   campaign_layouts=args.campaign or cfg.get("common", {}).get("campaign_layouts", False),
                   **build_args)
    env.set_param("hud_algo", ALGO_CODE.get("ppo" if manifest else cfg.get("algo"), 0))
    loaded_at = None
    episode = 0
    try:
        if args.campaign:
            obs, warmup = env.evaluation_reset(level)
        else:
            obs = env.reset(expected_level=level)
        while True:
            if manifest is None:
                path = find_model(run)
                mtime = path.stat().st_mtime
                if policy is None or mtime != loaded_at:
                    try:
                        policy = load_policy(path, greedy=not args.sample)
                        loaded_at = mtime
                        env.set_param("hud_step", policy.steps or 0)
                    except Exception:       # 학습 쪽이 저장하는 중이면 다음에 다시 읽는다
                        pass
            next_level = levels[episode % len(levels)] if levels else current_level(run_dir)
            next_level = 3 if next_level is None else next_level
            if next_level != level:
                level = next_level
                if args.campaign:
                    obs, warmup = env.evaluation_reset(level)
                else:
                    env.set_level(level)
                    obs = env.reset(expected_level=level)
            steps = policy.policies[level].steps if manifest else policy.steps
            if manifest:
                env.set_param("hud_step", steps or 0)
            done = False
            while not done:
                actions = policy.act(obs)
                r = env.evaluation_step(actions, warmup) if args.campaign else env.step(actions)
                obs = r["obs"]
                for _, kind, length in r["results"]:
                    done = True
                    print(f"레벨 {level}  {steps or 0:>10,} 스텝 모델  →  {kind} ({length / 10:.1f}초)", flush=True)
            if not args.campaign or kind == "success":
                episode += 1
            if args.campaign and episode == len(levels):
                print("MISSION COMPLETE — all 10 stages cleared.", flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        env.close()


if __name__ == "__main__":
    main()
