"""경기를 직접 하거나 구경한다.

선수 지정: human | random | easy | hard | <model.pt 경로>

예)
  python play.py                         # 사람(왼쪽) vs 어려움 봇
  python play.py --left human --right human
  python play.py --left runs/e1/ppo_seed0/model.pt --right hard
  python play.py --left a.pt --right b.pt --record match.gif --points 3

조작
  왼쪽 선수: A/D 이동, W 점프(공중에서는 위 조준), S 아래 조준, F 타격
  오른쪽 선수: ←/→ 이동, ↑ 점프, ↓ 아래 조준, / 또는 오른쪽 Shift 타격
  땅에서 이동 + 타격 = 다이빙, 공중에서 타격 = 스파이크
  R 다시 시작, ESC 종료, SPACE 일시정지, 1~4 속도 (0.5배 / 1배 / 2배 / 4배)

AI 선수 옆에는 지금 어떤 행동을 선호하는지 막대로 표시된다 (--no-overlay로 끔).
"""
import argparse

import numpy as np
import pygame

from algos import load_policy
from volleyball import Game, encode_action
from volleyball.bots import make_bot
from volleyball.game import FRAME_SKIP
from volleyball.render import Renderer

KEYS = {
    0: dict(left=pygame.K_a, right=pygame.K_d, up=pygame.K_w, down=pygame.K_s,
            hit=(pygame.K_f,)),
    1: dict(left=pygame.K_LEFT, right=pygame.K_RIGHT, up=pygame.K_UP, down=pygame.K_DOWN,
            hit=(pygame.K_SLASH, pygame.K_RSHIFT)),
}


def human_action(side, pressed):
    k = KEYS[side]
    x = int(pressed[k["right"]]) - int(pressed[k["left"]])
    move = x if side == 0 else -x          # 자기 기준: +1이 네트 쪽
    vert = 1 if pressed[k["up"]] else (2 if pressed[k["down"]] else 0)
    hit = int(any(pressed[h] for h in k["hit"]))
    return encode_action(move, vert, hit)


def make_player(spec, seed):
    if spec == "human":
        return None
    if spec in ("random", "easy", "hard"):
        return make_bot(spec, seed)
    return load_policy(spec, greedy=True, seed=seed)


def label(spec):
    if spec in ("human", "random", "easy", "hard"):
        return spec
    parts = spec.replace("\\", "/").split("/")
    return parts[-2] if len(parts) >= 2 else parts[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--left", default="human")
    ap.add_argument("--right", default="hard")
    ap.add_argument("--points", type=int, default=5, help="몇 점 내기")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--record", default=None, help="GIF로 저장할 경로 (화면 없이 녹화)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--no-overlay", action="store_true", help="AI 행동 선호도 표시 끄기")
    ap.add_argument("--mute", action="store_true", help="효과음 끄기")
    args = ap.parse_args()

    players = [make_player(args.left, args.seed), make_player(args.right, args.seed + 1)]
    names = (label(args.left), label(args.right))
    if args.record and None in players:
        raise SystemExit("녹화는 사람 없이 봇이나 모델끼리만 할 수 있어요.")

    game = Game(seed=args.seed, points_to_win=args.points)
    renderer = Renderer(headless=bool(args.record), sound=not args.mute)
    clock = pygame.time.Clock()
    frames = []
    running = True
    paused, speed = False, 1.0
    panels = {}
    while running:
        pressed = None
        if not args.record:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        game.reset()
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                        speed = {pygame.K_1: 0.5, pygame.K_2: 1.0, pygame.K_3: 2.0,
                                 pygame.K_4: 4.0}[event.key]
            pressed = pygame.key.get_pressed()

        if not game.match_over and not paused:
            actions = []
            for side in (0, 1):
                if players[side] is None:
                    actions.append(human_action(side, pressed))
                else:
                    obs = np.array([game.observe(side)], dtype=np.float32)
                    actions.append(int(players[side].act(obs)[0]))
                    if not args.no_overlay and hasattr(players[side], "action_probs"):
                        panels[side] = players[side].action_probs(obs)[0]
            game.step(actions[0], actions[1])

        message = None
        if game.match_over:
            if game.score[0] == game.score[1]:
                message = "무승부  (R: 다시 시작)"
            else:
                message = f"{names[game.score[1] > game.score[0]]} 승리!  (R: 다시 시작)"
        caption = "PAUSED" if paused else (f"x{speed:g}" if speed != 1.0 else None)
        renderer.draw(game, names, message, panels, caption)

        if args.record:
            frames.append(renderer.frame_rgb())
            if game.match_over:
                frames.extend([frames[-1]] * args.fps)   # 마지막 화면을 1초간 보여준다
                running = False
        else:
            clock.tick(int(60 // FRAME_SKIP * speed))

    if args.record:
        from PIL import Image
        images = [Image.fromarray(f[::2, ::2]) for f in frames]     # 절반 크기로 저장
        images[0].save(args.record, save_all=True, append_images=images[1:],
                       duration=1000 // args.fps, loop=0)
        print(f"저장: {args.record} ({len(images)} 프레임)")
    renderer.close()


if __name__ == "__main__":
    main()
