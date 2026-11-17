"""학습 중인 AI가 레이저 방을 통과하는 모습을 게임 창으로 본다.

학습(laser.train)이 20,000 스텝마다 latest.pt를 저장하고, 이 창은 한 판이 끝날 때마다
최신 모델을 다시 읽는다. 그래서 학습이 진행될수록 AI가 점점 잘하는 모습이 보인다.

예)
  .venv-unity\\Scripts\\python -m laser.watch runs/laser_test/ppo_curr
  .venv-unity\\Scripts\\python -m laser.watch runs/laser_test/ppo_curr --level 3 --speed 2
  .venv-unity\\Scripts\\python -m laser.watch runs/laser/ppo_seed0/model.pt      # 학습이 끝난 모델

창에서 V로 카메라를 바꿀 수 있다. 창을 닫거나 Ctrl+C로 끝낸다.
"""
import argparse
import json
import time
from pathlib import Path

from algos.common import load_policy
from laser.env import LaserEnv

ALGO_CODE = {"ppo": 1, "dqn": 2, "sac": 3}


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
    ap.add_argument("run", help="학습 폴더 또는 .pt 파일")
    ap.add_argument("--level", type=int, default=None, help="보여 줄 레벨 (기본: 학습 중인 레벨, 없으면 3)")
    ap.add_argument("--speed", type=float, default=1.0, help="재생 배속")
    ap.add_argument("--sample", action="store_true", help="가장 좋은 행동 대신 확률대로 고른다")
    ap.add_argument("--worker", type=int, default=90)
    args = ap.parse_args()

    run = Path(args.run)
    run_dir = run if run.is_dir() else run.parent
    print("모델을 기다리는 중..." if find_model(run) is None else f"모델: {find_model(run)}")
    while find_model(run) is None:
        time.sleep(2)

    env = LaserEnv(n_areas=1, seed=int(time.time()) % 10000, worker_id=args.worker, level=3,
                   time_scale=args.speed, graphics=True)
    try:
        cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        env.set_param("hud_algo", ALGO_CODE.get(cfg.get("algo"), 0))
    except (OSError, ValueError):
        pass
    policy, loaded_at = None, None
    obs = env.reset()
    try:
        while True:
            path = find_model(run)
            mtime = path.stat().st_mtime
            if policy is None or mtime != loaded_at:
                try:
                    policy = load_policy(path, greedy=not args.sample)
                    loaded_at = mtime
                    env.set_param("hud_step", policy.steps or 0)
                except Exception:       # 학습 쪽이 저장하는 중이면 다음에 다시 읽는다
                    pass
            level = args.level if args.level is not None else (current_level(run_dir) or 3)
            env.set_level(level)
            done = False
            while not done:
                r = env.step(policy.act(obs))
                obs = r["obs"]
                for _, kind, length in r["results"]:
                    done = True
                    print(f"레벨 {level}  {policy.steps or 0:>10,} 스텝 모델  →  {kind} ({length / 10:.1f}초)", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        env.close()


if __name__ == "__main__":
    main()
