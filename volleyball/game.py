"""알바트로스 배구: 물리와 규칙.

외부 라이브러리 없이 순수 파이썬으로 구현한다. 화면 출력은 render.py가 맡는다.

좌표계
- x: 0(왼쪽 벽) ~ COURT_W(오른쪽 벽), 네트는 NET_X
- y: 0(바닥) ~ COURT_H(천장)

행동은 "자기 기준(ego)"으로 준다. move의 +1은 항상 네트 쪽(앞)이다.
그래서 같은 정책이 왼쪽·오른쪽 어느 코트에서든 똑같이 플레이할 수 있다.
"""
import math
import random

# ---- 코트 ----
COURT_W = 24.0
COURT_H = 11.0
NET_X = 12.0
NET_H = 3.0
NET_HALF_W = 0.12

# ---- 시간 ----
DT = 1.0 / 60.0          # 물리 1프레임
FRAME_SKIP = 2           # 에이전트는 2프레임마다 한 번 행동 (30Hz)
MAX_RALLY_FRAMES = 60 * 30   # 랠리 하나의 시간 제한 (30초)

# ---- 선수 ----
P_R = 0.9                # 선수 반지름 (원형 충돌)
MOVE_SPEED = 6.5
JUMP_V = 13.0
P_GRAVITY = 32.0
HOME_X = NET_X / 2       # 랠리 시작 위치 (자기 기준)

# ---- 다이빙 ----
DIVE_SPEED = 13.0
DIVE_FRAMES = 12         # 몸을 던지는 시간
RECOVER_FRAMES = 18      # 착지 후 경직
DIG_VX = 2.0             # 다이빙으로 받은 공의 속도 (앞으로 살짝, 위로 높이)
DIG_VY = 12.0

# ---- 스파이크 ----
SWING_FRAMES = 8         # 타격 버튼을 누른 뒤 스윙이 유효한 시간
SPIKE_REACH = 0.35       # 스윙 중 늘어나는 타격 범위
# 조준: 0=정면, 1=위(로브), 2=아래(내리꽂기). (앞 방향 성분, 위 방향 성분, 속력)
SPIKE_AIMS = (
    (0.98, 0.17, 17.0),
    (0.70, 0.71, 13.0),
    (0.77, -0.64, 18.0),
)

# ---- 공 ----
B_R = 0.45
B_GRAVITY = 16.0
BALL_MAX_SPEED = 20.0
MIN_BOUNCE = 7.0         # 선수에게 맞고 튀는 최소 속도
NET_BOUNCE = 0.8
WALL_BOUNCE = 0.9

# ---- 행동 ----
# 행동 번호 a = move_i * 6 + vert_i * 2 + hit
#   move_i: 0=뒤, 1=정지, 2=앞   vert_i: 0=없음, 1=위, 2=아래   hit: 0/1
N_ACTIONS = 18
FULL_ACTIONS = tuple(range(N_ACTIONS))
# 기본 행동 공간: 이동 3 × 점프 여부 2 = 6개 (타격 없음)
BASIC_ACTIONS = tuple(m * 6 + v * 2 for m in range(3) for v in (0, 1))
ACTION_SETS = {"full": FULL_ACTIONS, "basic": BASIC_ACTIONS}

OBS_DIM = 20


def encode_action(move, vert, hit):
    """move: -1/0/+1, vert: 0 없음/1 위/2 아래, hit: 0/1 → 행동 번호"""
    return (move + 1) * 6 + vert * 2 + hit


class Player:
    __slots__ = ("x", "y", "vx", "vy", "grounded", "dive", "dive_dir",
                 "recover", "swing", "swing_used", "swing_aim", "touch_cd")

    def reset(self, x):
        self.x, self.y = x, P_R
        self.vx = self.vy = 0.0
        self.grounded = True
        self.dive = 0          # 남은 다이빙 프레임
        self.dive_dir = 0.0
        self.recover = 0       # 남은 경직 프레임
        self.swing = 0         # 남은 스윙 프레임
        self.swing_used = False  # 한 번 점프에 스윙은 한 번
        self.swing_aim = 0
        self.touch_cd = 0      # 터치 횟수를 중복으로 세지 않기 위한 쿨다운


class Game:
    """1:1 배구 한 경기. side 0 = 왼쪽, side 1 = 오른쪽."""

    def __init__(self, seed=None, points_to_win=1):
        self.rng = random.Random(seed)
        self.points_to_win = points_to_win
        self.players = (Player(), Player())
        self.reset()

    # ------------------------------------------------------------------
    def reset(self):
        self.score = [0, 0]
        self.match_over = False
        self._reset_rally()

    def _reset_rally(self):
        self.players[0].reset(HOME_X)
        self.players[1].reset(COURT_W - HOME_X)
        # 공은 네트 위에서 무작위 방향으로 떨어진다 (양쪽에 공평)
        self.bx, self.by = NET_X, 7.0
        self.bvx = self.rng.uniform(2.5, 7.0) * self.rng.choice((-1.0, 1.0))
        self.bvy = self.rng.uniform(0.0, 4.0)
        self.frames = 0
        # 랠리 통계: [왼쪽, 오른쪽]
        self.spikes = [0, 0]
        self.dives = [0, 0]
        self.touches = [0, 0]
        self.crossings = [0, 0]   # 공을 상대 코트로 넘긴 횟수
        self.events = []          # 이번 스텝에 일어난 일 (이름, 선수, x, y). 화면·효과음용

    # ------------------------------------------------------------------
    def step(self, action_left, action_right):
        """두 선수의 행동(자기 기준 행동 번호)을 받아 FRAME_SKIP 프레임 진행한다.

        반환: (winner, timeout)
          winner: +1 왼쪽 득점, -1 오른쪽 득점, 0 진행 중
          timeout: 랠리 시간 제한으로 무승부 처리됐으면 True
        """
        crossed_before = (self.crossings[0], self.crossings[1])
        self.events = []
        winner, timeout = 0, False
        for _ in range(FRAME_SKIP):
            winner = self._frame(action_left, action_right)
            if winner != 0:
                break
            if self.frames >= MAX_RALLY_FRAMES:
                timeout = True
                break
        self.last_crossed = (self.crossings[0] - crossed_before[0],
                             self.crossings[1] - crossed_before[1])
        self.last_stats = None
        if winner != 0 or timeout:
            self.last_stats = {
                "frames": self.frames, "spikes": tuple(self.spikes),
                "dives": tuple(self.dives), "touches": tuple(self.touches),
            }
            if winner != 0:
                self.events.append(("point", 0 if winner == 1 else 1, self.bx, self.by))
            if winner == 1:
                self.score[0] += 1
            elif winner == -1:
                self.score[1] += 1
            if timeout or max(self.score) >= self.points_to_win:
                self.match_over = True
            else:
                self._reset_rally()
        return winner, timeout

    # ------------------------------------------------------------------
    def _frame(self, action_left, action_right):
        self.frames += 1
        self._move_player(0, action_left)
        self._move_player(1, action_right)

        # 공 이동
        prev_bx = self.bx
        self.bvy -= B_GRAVITY * DT
        self.bx += self.bvx * DT
        self.by += self.bvy * DT

        # 벽과 천장
        if self.bx < B_R:
            self.bx, self.bvx = B_R, abs(self.bvx) * WALL_BOUNCE
            self.events.append(("wall", -1, self.bx, self.by))
        elif self.bx > COURT_W - B_R:
            self.bx, self.bvx = COURT_W - B_R, -abs(self.bvx) * WALL_BOUNCE
            self.events.append(("wall", -1, self.bx, self.by))
        if self.by > COURT_H - B_R:
            self.by, self.bvy = COURT_H - B_R, -abs(self.bvy) * WALL_BOUNCE
            self.events.append(("wall", -1, self.bx, self.by))

        self._collide_net(prev_bx)
        self._collide_player(0)
        self._collide_player(1)

        # 속력 제한
        speed = math.hypot(self.bvx, self.bvy)
        if speed > BALL_MAX_SPEED:
            k = BALL_MAX_SPEED / speed
            self.bvx *= k
            self.bvy *= k

        # 네트를 넘어갔는지 기록
        if prev_bx < NET_X <= self.bx:
            self.crossings[0] += 1
        elif prev_bx > NET_X >= self.bx:
            self.crossings[1] += 1

        # 바닥에 닿으면 득점
        if self.by <= B_R:
            return 1 if self.bx > NET_X else -1
        return 0

    # ------------------------------------------------------------------
    def _move_player(self, side, action):
        p = self.players[side]
        facing = 1.0 if side == 0 else -1.0   # 네트 방향
        move = action // 6 - 1
        vert = (action % 6) // 2
        hit = action % 2

        if p.touch_cd > 0:
            p.touch_cd -= 1
        if p.swing > 0:
            p.swing -= 1

        if p.recover > 0:
            # 경직: 아무것도 못 한다
            p.recover -= 1
            p.vx = 0.0
        elif p.dive > 0:
            # 다이빙 중: 방향을 바꿀 수 없다
            p.dive -= 1
            p.vx = p.dive_dir * DIVE_SPEED
            if p.dive == 0:
                p.recover = RECOVER_FRAMES
        else:
            p.vx = move * facing * MOVE_SPEED
            if p.grounded:
                if vert == 1:
                    p.vy = JUMP_V
                    p.grounded = False
                    self.events.append(("jump", side, p.x, p.y))
                elif hit and move != 0:
                    p.dive = DIVE_FRAMES
                    p.dive_dir = move * facing
                    p.vx = p.dive_dir * DIVE_SPEED
                    self.dives[side] += 1
                    self.events.append(("dive", side, p.x, p.y))
            elif hit and not p.swing_used:
                p.swing = SWING_FRAMES
                p.swing_used = True
                self.events.append(("swing", side, p.x, p.y))
                p.swing_aim = vert

        if not p.grounded:
            p.vy -= P_GRAVITY * DT
            p.y += p.vy * DT
            if p.y <= P_R:
                p.y, p.vy = P_R, 0.0
                p.grounded = True
                p.swing = 0
                p.swing_used = False
                self.events.append(("land", side, p.x, p.y))

        # 자기 코트 밖으로 못 나간다
        p.x += p.vx * DT
        if side == 0:
            lo, hi = P_R, NET_X - NET_HALF_W - P_R
        else:
            lo, hi = NET_X + NET_HALF_W + P_R, COURT_W - P_R
        if p.x < lo:
            p.x = lo
        elif p.x > hi:
            p.x = hi

    # ------------------------------------------------------------------
    def _collide_net(self, prev_bx):
        # 원과 직사각형(네트)의 충돌
        cx = min(max(self.bx, NET_X - NET_HALF_W), NET_X + NET_HALF_W)
        cy = min(max(self.by, 0.0), NET_H)
        dx, dy = self.bx - cx, self.by - cy
        d2 = dx * dx + dy * dy
        if d2 >= B_R * B_R:
            return
        if d2 < 1e-12:
            # 공 중심이 네트 안에 들어간 경우: 들어온 쪽으로 밀어낸다
            nx, ny = (-1.0, 0.0) if prev_bx < NET_X else (1.0, 0.0)
            cx = NET_X
            push = NET_HALF_W + B_R
        else:
            d = math.sqrt(d2)
            nx, ny = dx / d, dy / d
            push = B_R
        self.bx, self.by = cx + nx * push, cy + ny * push
        vn = self.bvx * nx + self.bvy * ny
        if vn < 0.0:
            self.bvx -= (1.0 + NET_BOUNCE) * vn * nx
            self.bvy -= (1.0 + NET_BOUNCE) * vn * ny
            self.events.append(("net", -1, self.bx, self.by))

    def _collide_player(self, side):
        p = self.players[side]
        facing = 1.0 if side == 0 else -1.0
        dx, dy = self.bx - p.x, self.by - p.y
        reach = P_R + B_R + (SPIKE_REACH if p.swing > 0 else 0.0)
        d2 = dx * dx + dy * dy
        if d2 >= reach * reach:
            return
        d = math.sqrt(d2) or 1e-6
        nx, ny = dx / d, dy / d

        if p.swing > 0:
            # 스파이크: 조준 방향으로 강하게 날린다
            ux, uy, speed = SPIKE_AIMS[p.swing_aim]
            self.bvx, self.bvy = facing * ux * speed, uy * speed
            p.swing = 0
            self.spikes[side] += 1
            self.events.append(("spike", side, self.bx, self.by))
        elif p.dive > 0:
            # 다이빙 리시브: 공을 위로 띄운다
            self.bvx, self.bvy = facing * DIG_VX, DIG_VY
            if p.touch_cd == 0:
                self.events.append(("dig", side, self.bx, self.by))
        else:
            # 일반 충돌: 선수 기준 상대속도를 반사시킨다
            rvx, rvy = self.bvx - p.vx, self.bvy - p.vy
            vn = rvx * nx + rvy * ny
            if vn < 0.0:
                rvx -= 2.0 * vn * nx
                rvy -= 2.0 * vn * ny
                vn = -vn
            if vn < MIN_BOUNCE:
                rvx += (MIN_BOUNCE - vn) * nx
                rvy += (MIN_BOUNCE - vn) * ny
            self.bvx, self.bvy = rvx + p.vx, rvy + p.vy
            if p.touch_cd == 0:
                self.events.append(("hit", side, self.bx, self.by))

        if d < P_R + B_R:
            self.bx = p.x + nx * (P_R + B_R)
            self.by = p.y + ny * (P_R + B_R)
        if p.touch_cd == 0:
            self.touches[side] += 1
        p.touch_cd = 10

    # ------------------------------------------------------------------
    def observe(self, side):
        """side 선수 기준의 관측 20개. 값은 대략 [-1, 1] 범위로 정규화한다.

        오른쪽 선수는 좌우를 뒤집어서, 항상 "나는 왼쪽, 네트는 오른쪽"으로 보이게 한다.
        """
        me, opp = self.players[side], self.players[1 - side]
        if side == 0:
            mx, mvx, ox, ovx = me.x, me.vx, opp.x, opp.vx
            bx, bvx = self.bx, self.bvx
        else:
            mx, mvx, ox, ovx = COURT_W - me.x, -me.vx, COURT_W - opp.x, -opp.vx
            bx, bvx = COURT_W - self.bx, -self.bvx
        busy_total = DIVE_FRAMES + RECOVER_FRAMES
        return (
            (mx - NET_X) / NET_X, me.y / COURT_H, mvx / BALL_MAX_SPEED, me.vy / BALL_MAX_SPEED,
            1.0 if me.grounded else 0.0,
            (me.dive + me.recover) / busy_total,
            0.0 if me.swing_used else 1.0,
            (ox - NET_X) / NET_X, opp.y / COURT_H, ovx / BALL_MAX_SPEED, opp.vy / BALL_MAX_SPEED,
            1.0 if opp.grounded else 0.0,
            (opp.dive + opp.recover) / busy_total,
            0.0 if opp.swing_used else 1.0,
            (bx - NET_X) / NET_X, self.by / COURT_H, bvx / BALL_MAX_SPEED, self.bvy / BALL_MAX_SPEED,
            (bx - mx) / COURT_W, (self.by - me.y) / COURT_H,
        )
