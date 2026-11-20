"""학습된 AI의 플레이를 GIF로 녹화한다 (보고서·README용).

예)
  .venv-unity\\Scripts\\python -m laser.record runs/laser/x1/ppo_seed0/model.pt --level 4 --episodes 3 --out docs/figures/laser_ppo.gif
  # 학습 과정: 체크포인트마다 한 판씩 (왼쪽 위에 학습량이 표시된다)
  .venv-unity\\Scripts\\python -m laser.record runs/laser/x1/ppo_seed0 --progress --level 2 --out docs/figures/laser_progress.gif

Unity 창이 잠깐 뜨고, 매 프레임(30fps)을 PNG로 저장한 뒤 GIF로 묶는다.
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from PIL import Image

from algos.common import load_policy
from laser.env import LaserEnv
from laser.watch import ALGO_CODE


def run_episodes(env, policy, level, episodes, want_success):
    """want_success면 성공한 판이 나올 때까지(최대 episodes×5판) 돌린다."""
    env.set_level(level)
    obs = env.reset(expected_level=level)
    kept, tries = 0, 0
    outcomes = []
    while kept < episodes and tries < episodes * 5:
        done = False
        while not done:
            r = env.step(policy.act(obs))
            obs = r["obs"]
            for _, kind, length in r["results"]:
                done = True
                tries += 1
                outcomes.append(kind)
                print(f"  {kind} ({length / 10:.1f}초)", flush=True)
                if kind == "success" or not want_success:
                    kept += 1
    return outcomes


def to_gif(frames_dir, out, width, skip):
    files = sorted(Path(frames_dir).glob("frame_*.png"))[::skip]
    if not files:
        raise SystemExit("녹화된 프레임이 없습니다")
    frames = []
    for f in files:
        im = Image.open(f).convert("RGB")
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        frames.append(im.quantize(colors=96, method=Image.Quantize.MEDIANCUT))
    if not any(frame.convert("RGB").getbbox() for frame in frames):
        raise SystemExit("녹화된 화면이 모두 검은색입니다")
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=int(1000 / 30 * skip),
                   loop=0, optimize=True)
    print(f"저장: {out} ({len(frames)}프레임, {out.stat().st_size / 1e6:.1f}MB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("model", help=".pt 파일, 또는 --progress일 때 학습 폴더")
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--episodes", type=int, default=2)
    ap.add_argument("--progress", action="store_true", help="체크포인트(ckpt_*.pt)마다 한 판씩")
    ap.add_argument("--success-only", action="store_true", help="성공한 판만 남긴다 (실패한 판도 녹화는 된다)")
    ap.add_argument("--view", type=int, default=0, help="카메라: 0 위, 1 뒤, 2 옆, 3 정면")
    ap.add_argument("--width", type=int, default=560)
    ap.add_argument("--skip", type=int, default=3, help="몇 프레임마다 하나씩 쓸지 (용량 줄이기)")
    ap.add_argument("--worker", type=int, default=95)
    ap.add_argument("--seed", type=int, help="재현할 환경 시드")
    ap.add_argument("--build", type=Path, help="녹화에 사용할 Unity 빌드")
    ap.add_argument("--expect", choices=["success", "hit", "timeout"], help="한 판의 예상 결과")
    ap.add_argument("--offscreen", action="store_true", help="카메라 영상을 창과 별도로 녹화한다")
    args = ap.parse_args()
    if args.expect and (args.episodes != 1 or args.progress or args.success_only):
        ap.error("--expect는 --episodes 1과 함께 사용하세요")

    path = Path(args.model)
    models = sorted(path.glob("ckpt_*.pt")) + [path / "model.pt"] if args.progress else [path]
    run_dir = path if path.is_dir() else path.parent
    with tempfile.TemporaryDirectory(prefix="laser_rec_") as directory:
        record(args, models, run_dir, Path(directory))


def record(args, models, run_dir, frames):
    build_arg = {"build": args.build} if args.build else {}
    seed = args.seed if args.seed is not None else int(time.time()) % 10000
    capture_args = ["-record-offscreen"] if args.offscreen else []
    env = LaserEnv(n_areas=1, seed=seed, worker_id=args.worker, level=args.level,
                   time_scale=1.0, graphics=True,
                   extra_args=["-record", str(frames), "-mute", "-view", str(args.view),
                               "-screen-width", "1280", "-screen-height", "720"] + capture_args, **build_arg)
    try:
        cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        env.set_param("hud_algo", ALGO_CODE.get(cfg.get("algo"), 0))
    except (OSError, ValueError):
        pass
    try:
        for m in models:
            policy = load_policy(m, greedy=True)
            env.set_param("hud_step", policy.steps or 0)
            print(f"{m.name}: {policy.steps or 0:,} 스텝")
            outcomes = run_episodes(env, policy, args.level, 1 if args.progress else args.episodes, args.success_only)
            if args.expect and outcomes != [args.expect]:
                raise SystemExit(f"예상 결과 {args.expect}, 실제 결과 {outcomes}")
        if args.expect:
            for _ in range(4):
                env.step([4])  # 종료 직후 HUD가 보이는 프레임을 남긴다.
    finally:
        env.close()
    to_gif(frames, Path(args.out), args.width, args.skip)


if __name__ == "__main__":
    main()
