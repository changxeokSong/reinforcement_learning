"""학습을 눈으로 본다. 알고리즘들이 학습하는 동안, 그 시점의 모델끼리 계속 경기를 시킨다.

예)
  python watch.py                         # PPO·DQN·SAC 학습을 시작하고 서로 붙는 모습을 본다
  python watch.py --algos ppo sac --steps 1000000
  python watch.py --runs runs/e1/ppo_seed0 runs/e1/dqn_seed0   # 이미 돌고 있는(또는 끝난) 학습을 본다
  python watch.py --bot hard              # 어려움 봇도 대진에 넣는다

학습은 화면과 별개의 프로세스에서 돌고, 2만 스텝마다 최신 모델(latest.pt)을 저장한다.
한 대진은 5점 내기다(--points로 변경). 경기가 끝날 때마다 최신 모델을 다시 불러와서 다음 대진을
시작한다. 그래서 시간이 지날수록 실력이 느는 게 보인다.

조작: SPACE 일시정지, 1~4 속도(1배/2배/4배/8배), N 다음 대진, ESC 종료
창을 닫으면 여기서 시작한 학습도 함께 멈춘다 (--keep을 주면 계속 돈다).
"""
import argparse
import itertools
import subprocess
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pygame

from algos import load_policy
from volleyball import Game
from volleyball.bots import make_bot
from volleyball.game import FRAME_SKIP
from volleyball.render import Renderer


class Contestant:
    """대진에 참가하는 선수. 학습 중인 모델이면 파일이 바뀔 때마다 다시 불러온다."""

    def __init__(self, name, path=None, bot=None):
        self.name, self.path, self.policy = name, path, bot
        self.mtime = 0.0
        self.recent = deque(maxlen=10)      # 최근 10경기의 승패 (1 승, 0 패)

    def refresh(self):
        if self.path is None:
            return True
        try:
            mtime = self.path.stat().st_mtime
            if mtime != self.mtime:
                # 학습 때와 같은 방식으로 행동한다 (PPO·SAC는 확률적으로 고른다)
                self.policy = load_policy(self.path, greedy=False, name=self.name)
                self.mtime = mtime
        except (OSError, RuntimeError, EOFError):
            pass                            # 아직 파일이 없거나 쓰는 중이면 다음에 다시 시도
        return self.policy is not None

    def status(self):
        steps = getattr(self.policy, "steps", None)
        steps_text = "bot" if self.path is None else (f"{steps:>9,} steps" if steps is not None else "loading")
        record = f"{sum(self.recent):2d}/{len(self.recent):2d}" if self.recent else " -"
        return f"{self.name:<10s} {steps_text:>15s}   recent matches won {record}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--algos", nargs="+", default=["ppo", "dqn", "sac"])
    ap.add_argument("--runs", nargs="+", default=None, help="이미 있는 학습 폴더를 본다 (새로 학습하지 않음)")
    ap.add_argument("--bot", nargs="*", default=[], help="대진에 넣을 봇: random easy hard")
    ap.add_argument("--points", type=int, default=5, help="한 대진을 몇 점 내기로 할지")
    ap.add_argument("--steps", type=int, default=3_000_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="runs/live")
    ap.add_argument("--keep", action="store_true", help="창을 닫아도 학습을 계속한다")
    ap.add_argument("--mute", action="store_true", help="효과음 끄기")
    args = ap.parse_args()

    procs, contestants = [], []
    if args.runs:
        for d in args.runs:
            contestants.append(Contestant(Path(d).name, Path(d) / "latest.pt"))
    else:
        for algo in args.algos:
            out = Path(args.out) / algo
            out.mkdir(parents=True, exist_ok=True)
            (out / "latest.pt").unlink(missing_ok=True)
            log = open(out / "log.txt", "w", encoding="utf-8")
            procs.append(subprocess.Popen(
                [sys.executable, "train.py", "--algo", algo, "--seed", str(args.seed),
                 "--out", str(out), "--set", f"total_steps={args.steps}"],
                stdout=log, stderr=subprocess.STDOUT))
            contestants.append(Contestant(algo, out / "latest.pt"))
    for i, b in enumerate(args.bot):
        contestants.append(Contestant(f"bot_{b}", bot=make_bot(b, seed=i)))
    if len(contestants) == 1:
        contestants.append(Contestant("bot_hard", bot=make_bot("hard")))

    renderer = Renderer(title="알바트로스 배구 - 학습 관전", sound=not args.mute)
    clock = pygame.time.Clock()
    pairs = itertools.cycle(itertools.permutations(range(len(contestants)), 2))
    speed, paused, running, match_no = 2.0, False, True, 0
    game = Game(seed=args.seed, points_to_win=args.points)
    left = right = None
    result_frames, counted = 0, False   # 경기가 끝난 뒤 결과를 보여주는 남은 프레임

    while running:
        # 새 대진: 경기가 끝났거나 아직 시작 전이면 다음 두 선수를 고르고 최신 모델을 불러온다
        if left is not None and game.match_over and result_frames == 0 and not counted:
            counted = True
            if game.score[0] != game.score[1]:
                left.recent.append(int(game.score[0] > game.score[1]))
                right.recent.append(int(game.score[1] > game.score[0]))
            result_frames = 45
        if left is None or (game.match_over and result_frames == 0):
            ready = all([c.refresh() for c in contestants])
            if ready:
                i, j = next(pairs)
                left, right = contestants[i], contestants[j]
                match_no += 1
                game = Game(seed=args.seed * 7919 + match_no, points_to_win=args.points)
                counted = False
            else:
                left = None

        skip = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_n:
                    skip = True
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    speed = {pygame.K_1: 1.0, pygame.K_2: 2.0, pygame.K_3: 4.0, pygame.K_4: 8.0}[event.key]

        status = [c.status() for c in contestants]
        if left is None:
            renderer.draw(game, ("", ""), "학습을 시작하는 중...", None, status)
            clock.tick(5)
            continue
        if skip:
            game.match_over, counted, result_frames = True, True, 0
            continue
        if game.match_over:
            # 경기 결과를 잠깐 보여준다
            result_frames -= 1
            if game.score[0] == game.score[1]:
                message = "DRAW"
            else:
                message = f"{left.name if game.score[0] > game.score[1] else right.name} WINS"
            renderer.draw(game, (left.name, right.name), message, None, status)
            clock.tick(30)
            continue

        panels = {}
        if not paused:
            obs_l = np.array([game.observe(0)], dtype=np.float32)
            obs_r = np.array([game.observe(1)], dtype=np.float32)
            for side, c, obs in ((0, left, obs_l), (1, right, obs_r)):
                if hasattr(c.policy, "action_probs"):
                    panels[side] = c.policy.action_probs(obs)[0]
            game.step(int(left.policy.act(obs_l)[0]), int(right.policy.act(obs_r)[0]))
        if all(p.poll() is not None for p in procs) and procs:
            status.append("training finished")
        if paused:
            status.append("PAUSED")
        renderer.draw(game, (left.name, right.name), None, panels, status)
        clock.tick(int(60 // FRAME_SKIP * speed))

    renderer.close()
    if not args.keep:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
