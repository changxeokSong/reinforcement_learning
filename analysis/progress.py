"""학습 과정을 영상으로 만든다. 체크포인트마다 같은 상대와 몇 점씩 겨루는 장면을 이어 붙인다.

예)
  python -m analysis.progress runs/e1/ppo_seed0                      # 어려움 봇 상대
  python -m analysis.progress runs/e1/sac_seed0 --opponent easy --points 2 --out sac.gif

같은 seed를 쓰므로 모든 체크포인트가 같은 서브를 받는다. 실력 변화만 비교할 수 있다.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from algos import load_policy
from volleyball import Game
from volleyball.bots import make_bot
from volleyball.render import Renderer


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--opponent", default="hard", help="random | easy | hard | <model.pt>")
    ap.add_argument("--points", type=int, default=2, help="체크포인트당 점수")
    ap.add_argument("--max-sec", type=float, default=8.0, help="한 점에서 보여줄 최대 시간")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run = Path(args.run_dir)
    ckpts = sorted(run.glob("ckpt_*.pt"))
    if (run / "model.pt").exists():
        ckpts.append(run / "model.pt")
    if not ckpts:
        raise SystemExit("체크포인트가 없어요.")

    renderer = Renderer(headless=True)
    frames = []
    for ckpt in ckpts:
        policy = load_policy(ckpt, greedy=True)
        if args.opponent in ("random", "easy", "hard"):
            opponent = make_bot(args.opponent, seed=0)
        else:
            opponent = load_policy(args.opponent, greedy=True)
        if ckpt.name == "model.pt":
            steps = "final"
        else:
            steps = f"{int(ckpt.stem.split('_')[1]):,} steps"
        game = Game(seed=args.seed, points_to_win=args.points)
        rally_frames = 0
        while not game.match_over:
            obs = np.array([game.observe(0)], dtype=np.float32)
            obs_opp = np.array([game.observe(1)], dtype=np.float32)
            panel = {0: policy.action_probs(obs)[0]}
            before = sum(game.score)
            game.step(int(policy.act(obs)[0]), int(opponent.act(obs_opp)[0]))
            rally_frames = 0 if sum(game.score) != before else rally_frames + 1
            if rally_frames <= args.max_sec * 30:
                renderer.draw(game, (run.name, args.opponent), None, panel, f"training: {steps}")
                frames.append(Image.fromarray(renderer.frame_rgb()[::2, ::2]))
        frames.extend([frames[-1]] * 15)
        print(f"{steps:>16s}  {game.score[0]} : {game.score[1]}")
    renderer.close()

    out = args.out or str(run / "progress.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=33, loop=0)
    print(f"저장: {out} ({len(frames)} 프레임)")


if __name__ == "__main__":
    main()
