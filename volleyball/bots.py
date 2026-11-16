"""학습하지 않는 상대: 무작위 봇과 규칙 기반 봇.

모든 "선수"는 act(obs_batch) -> 게임 행동 번호 배열 이라는 같은 인터페이스를 쓴다.
규칙 기반 봇은 학습된 에이전트의 실력을 재는 고정 기준이다.
"""
import math

import numpy as np

from .game import (B_GRAVITY, B_R, BALL_MAX_SPEED, COURT_H, HOME_X, N_ACTIONS, NET_X,
                   P_R, encode_action)


class RandomBot:
    name = "random"

    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)

    def act(self, obs):
        return self.rng.integers(0, N_ACTIONS, size=len(obs))


class RuleBot:
    """공이 떨어질 곳을 예측해서 움직이는 봇.

    level="easy": 이동과 점프만 하고, 가끔 엉뚱하게 움직인다.
    level="hard": 스파이크와 다이빙도 쓴다.
    """

    def __init__(self, level="hard", seed=0):
        assert level in ("easy", "hard")
        self.level = level
        self.name = f"bot_{level}"
        self.rng = np.random.default_rng(seed)

    def act(self, obs):
        return np.array([self._act_one(o) for o in obs])

    def _act_one(self, o):
        # 정규화된 관측을 원래 단위로 되돌린다 (자기 기준: 나는 x<8, 네트는 x=8)
        sx, sy = o[0] * NET_X + NET_X, o[1] * COURT_H
        grounded, busy, can_swing = o[4] > 0.5, o[5] > 0.0, o[6] > 0.5
        bx, by = o[14] * NET_X + NET_X, o[15] * COURT_H
        bvx, bvy = o[16] * BALL_MAX_SPEED, o[17] * BALL_MAX_SPEED

        if self.level == "easy" and self.rng.random() < 0.25:
            return encode_action(int(self.rng.integers(-1, 2)), 0, 0)
        if busy:
            return encode_action(0, 0, 0)

        # 공이 내 몸 높이(y=1.6)까지 내려오는 시간과 위치를 예측한다
        target_y = 1.6
        disc = bvy * bvy + 2.0 * B_GRAVITY * max(by - target_y, 0.0)
        t = (bvy + math.sqrt(disc)) / B_GRAVITY
        land_x = bx + bvx * t
        if land_x < B_R:                  # 뒷벽에 맞고 튀는 경우
            land_x = 2 * B_R - land_x
        coming = land_x < NET_X

        # 공보다 살짝 뒤에 서야 공이 앞으로 튄다
        goal_x = land_x - 0.4 if coming else HOME_X
        diff = goal_x - sx
        move = 0 if abs(diff) < 0.15 else (1 if diff > 0 else -1)

        dist = math.hypot(bx - sx, by - sy)
        if not grounded:
            if self.level == "hard" and can_swing and dist < P_R + B_R + 0.5:
                # 네트 가까이에서 공이 높으면 내리꽂고, 낮으면 띄워서 넘긴다
                if sx > NET_X - 2.2 and by > 3.9:
                    aim = 2
                elif by > 3.0:
                    aim = 0
                else:
                    aim = 1
                return encode_action(move, aim, 1)
            return encode_action(move, 0, 0)

        if coming:
            # 공이 머리 위 적당한 높이로 오면 점프
            if abs(bx - sx) < 1.3 and 2.6 < by < 4.8 and bvy < 2.0:
                return encode_action(move, 1, 0)
            # 걸어서는 늦을 때 다이빙
            if self.level == "hard" and move != 0 and t < 0.35 and abs(diff) > 1.2:
                return encode_action(move, 0, 1)
        return encode_action(move, 0, 0)


def make_bot(name, seed=0):
    if name == "random":
        return RandomBot(seed)
    if name in ("easy", "bot_easy"):
        return RuleBot("easy", seed)
    if name in ("hard", "bot_hard"):
        return RuleBot("hard", seed)
    raise ValueError(f"알 수 없는 봇: {name}")
