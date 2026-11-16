"""pygame으로 경기 화면을 그린다. 학습에는 쓰지 않고, 사람 플레이·관전·영상 녹화에만 쓴다.

캐릭터는 알바트로스를 단순한 도형으로 직접 그린 것이다. 공식 로고나 이미지는 쓰지 않는다.
효과음도 파일 없이 코드로 합성한다.

게임 로직(game.py)은 이 파일을 모른다. 게임이 남긴 events 목록만 읽어서
날갯짓, 먼지, 불꽃, 화면 흔들림, 효과음을 붙인다. 그래서 모션을 바꿔도 학습 결과에는 영향이 없다.
"""
import math
import random
from collections import deque

import numpy as np
import pygame

from .game import (B_R, BALL_MAX_SPEED, COURT_H, COURT_W, JUMP_V, NET_H, NET_HALF_W,
                   NET_X, P_R, SWING_FRAMES)

SCALE = 52                      # 1 단위 = 52픽셀
WIDTH, HEIGHT = int(COURT_W * SCALE), int(COURT_H * SCALE)
GROUND_PX = 64                  # 바닥 아래 모래 두께

SKY_TOP, SKY_BOTTOM = (96, 170, 232), (214, 236, 250)
SEA, SEA_DARK = (72, 150, 200), (58, 130, 185)
SAND, SAND_DARK = (236, 212, 164), (214, 188, 138)
CRIMSON = (176, 28, 46)         # 서강 진홍색 계열
NAVY = (30, 60, 120)
WHITE, DARK, BEAK = (250, 250, 250), (58, 60, 72), (245, 170, 60)
BELLY, WING, WING_LIGHT = (232, 234, 240), (70, 74, 90), (120, 126, 146)


def to_px(x, y):
    return int(x * SCALE), int(HEIGHT - y * SCALE)


# ----------------------------------------------------------------------
# 효과음: 짧은 파형을 직접 만들어서 쓴다
# ----------------------------------------------------------------------
class Sounds:
    RATE = 44100

    def __init__(self):
        self.ok = False
        try:
            pygame.mixer.init(self.RATE, -16, 1, 512)
            self.channels = pygame.mixer.get_init()[2]
            self.bank = {
                "hit": self._tone(520, 0.07, 0.35, slide=-120),
                "dig": self._tone(330, 0.10, 0.35, slide=140),
                "spike": self._mix(self._noise(0.12, 0.45), self._tone(160, 0.14, 0.6, slide=-90)),
                "swing": self._noise(0.07, 0.12),
                "net": self._tone(140, 0.10, 0.4, slide=-40),
                "wall": self._tone(240, 0.06, 0.25, slide=-60),
                "jump": self._tone(360, 0.09, 0.12, slide=320),
                "land": self._noise(0.05, 0.10),
                "dive": self._noise(0.16, 0.22),
                "point": self._mix(self._tone(880, 0.32, 0.3), self._tone(1320, 0.32, 0.2, delay=0.10)),
            }
            self.ok = True
        except (pygame.error, NotImplementedError, ImportError):
            pass                 # 소리 장치가 없으면 조용히 넘어간다

    def _env(self, n):
        t = np.linspace(0.0, 1.0, n)
        return np.minimum(t * 40.0, 1.0) * np.exp(-4.0 * t)

    def _tone(self, freq, sec, volume, slide=0.0, delay=0.0):
        n = int(self.RATE * sec)
        t = np.arange(n) / self.RATE
        phase = 2 * np.pi * (freq * t + 0.5 * slide / sec * t * t)
        wave = np.sin(phase) * self._env(n) * volume
        return np.concatenate([np.zeros(int(self.RATE * delay)), wave])

    def _noise(self, sec, volume):
        n = int(self.RATE * sec)
        rng = np.random.default_rng(0)
        wave = np.convolve(rng.uniform(-1, 1, n), np.ones(6) / 6, mode="same")
        return wave * self._env(n) * volume

    @staticmethod
    def _mix(a, b):
        out = np.zeros(max(len(a), len(b)))
        out[:len(a)] += a
        out[:len(b)] += b
        return out

    def _sound(self, wave):
        data = (np.clip(wave, -1, 1) * 32767).astype(np.int16)
        if self.channels > 1:
            data = np.repeat(data[:, None], self.channels, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(data))

    def play(self, name):
        if not self.ok or name not in self.bank:
            return
        if not isinstance(self.bank[name], pygame.mixer.Sound):
            self.bank[name] = self._sound(self.bank[name])
        self.bank[name].play()


# ----------------------------------------------------------------------
class Renderer:
    def __init__(self, title="알바트로스 배구", headless=False, sound=True):
        pygame.init()
        self.headless = headless
        size = (WIDTH, HEIGHT + GROUND_PX)
        if headless:
            self.screen = pygame.Surface(size)
        else:
            self.screen = pygame.display.set_mode(size)
            pygame.display.set_caption(title)
        self.scene = pygame.Surface(size)
        self.fx = pygame.Surface(size, pygame.SRCALPHA)
        self.font = pygame.font.SysFont("malgungothic,arial", 30, bold=True)
        self.big = pygame.font.SysFont("arialblack,arial", 44, bold=True)
        self.small = pygame.font.SysFont("malgungothic,arial", 18)
        self.tiny = pygame.font.SysFont("consolas,arial", 14)
        self.mono = pygame.font.SysFont("consolas,couriernew,malgungothic", 17)
        self.sounds = Sounds() if (sound and not headless) else None
        self.rng = random.Random(0)
        self.background = self._make_background()
        self.clouds = [[self.rng.uniform(0, WIDTH), self.rng.uniform(30, 190),
                        self.rng.uniform(0.6, 1.3), self.rng.uniform(0.15, 0.45)] for _ in range(5)]
        self.tick = 0
        self.particles = []          # [x, y, vx, vy, life, max_life, color, size, gravity]
        self.texts = []              # [x, y, text, color, life]
        self.trail = deque(maxlen=12)
        self.ball_angle = 0.0
        self.shake = 0
        self.squash = [0, 0]         # 착지할 때 몸이 눌리는 남은 프레임
        self.flash = 0
        self.last_key = None

    # ------------------------------------------------------------------
    def _make_background(self):
        bg = pygame.Surface((WIDTH, HEIGHT + GROUND_PX))
        for y in range(HEIGHT):
            k = y / HEIGHT
            color = [int(a + (b - a) * k) for a, b in zip(SKY_TOP, SKY_BOTTOM)]
            pygame.draw.line(bg, color, (0, y), (WIDTH, y))
        # 해
        pygame.draw.circle(bg, (255, 244, 200), (WIDTH - 150, 110), 62)
        pygame.draw.circle(bg, (255, 250, 228), (WIDTH - 150, 110), 46)
        # 먼 바다와 수평선
        sea_top = HEIGHT - 90
        pygame.draw.rect(bg, SEA, (0, sea_top, WIDTH, 90))
        for i in range(6):
            y = sea_top + 10 + i * 14
            for x in range((i * 37) % 60, WIDTH, 120):
                pygame.draw.line(bg, SEA_DARK, (x, y), (x + 46, y), 2)
        # 모래
        pygame.draw.rect(bg, SAND, (0, HEIGHT, WIDTH, GROUND_PX))
        pygame.draw.line(bg, SAND_DARK, (0, HEIGHT), (WIDTH, HEIGHT), 3)
        for _ in range(260):
            x, y = self.rng.randrange(WIDTH), HEIGHT + self.rng.randrange(6, GROUND_PX)
            pygame.draw.circle(bg, SAND_DARK, (x, y), 1)
        # 코트 경계선
        for x in (6, WIDTH - 6):
            pygame.draw.line(bg, WHITE, (x, HEIGHT + 4), (x, HEIGHT + 22), 4)
        return bg

    def _draw_clouds(self, s):
        for c in self.clouds:
            c[0] = (c[0] + c[3]) % (WIDTH + 260)
            x, y, k = c[0] - 130, c[1], c[2]
            for dx, dy, r in ((0, 0, 30), (34, -10, 38), (72, 0, 30), (36, 12, 34)):
                pygame.draw.circle(s, (255, 255, 255), (int(x + dx * k), int(y + dy * k)), int(r * k))

    def _draw_net(self, s):
        left, top = to_px(NET_X - NET_HALF_W, NET_H)
        w, h = int(2 * NET_HALF_W * SCALE), int(NET_H * SCALE)
        pygame.draw.rect(s, (92, 70, 52), (left, top, w, h))                 # 기둥
        pygame.draw.rect(s, WHITE, (left - 3, top - 4, w + 6, 10), border_radius=3)   # 위쪽 띠
        for y in range(top + 16, HEIGHT, 14):
            pygame.draw.line(s, (240, 240, 240), (left, y), (left + w, y), 1)

    # ------------------------------------------------------------------
    def _burst(self, x, y, n, colors, speed, life=18, size=4, gravity=0.25, up=0.0, spread=math.pi):
        px, py = to_px(x, y)
        for _ in range(n):
            a = -math.pi / 2 + self.rng.uniform(-spread, spread)
            v = self.rng.uniform(0.3, 1.0) * speed
            self.particles.append([px, py, math.cos(a) * v, math.sin(a) * v - up,
                                   life, life, self.rng.choice(colors), size, gravity])

    def _handle_events(self, game):
        """게임에서 일어난 일을 이펙트와 효과음으로 바꾼다. 같은 스텝을 두 번 처리하지 않는다."""
        key = (id(game), game.frames, game.score[0], game.score[1])
        if key == self.last_key:
            return
        self.last_key = key
        for name, side, x, y in game.events:
            if self.sounds:
                self.sounds.play(name)
            if name == "spike":
                self._burst(x, y, 22, [(255, 220, 90), (255, 150, 50), (255, 255, 255)], 7.0, life=16)
                self.shake, self.flash = 7, 5
                self.texts.append([*to_px(x, y + 0.9), "SPIKE!", (220, 90, 30), 26])
            elif name == "hit":
                self._burst(x, y, 7, [(255, 255, 255), (255, 240, 180)], 3.0, life=10, size=3)
            elif name == "dig":
                self._burst(x, y, 10, [(255, 255, 255), (170, 220, 255)], 4.0, life=14)
                self.texts.append([*to_px(x, y + 0.9), "DIG!", (40, 120, 190), 22])
            elif name in ("land", "jump"):
                self._burst(x, 0.05, 6, [SAND_DARK, SAND], 2.4, life=12, size=3, gravity=0.12,
                            spread=1.3)
                if name == "land" and side >= 0:
                    self.squash[side] = 7
            elif name == "dive":
                self._burst(x, 0.05, 14, [SAND_DARK, SAND], 4.0, life=18, size=4, gravity=0.12,
                            spread=1.2)
            elif name in ("net", "wall"):
                self._burst(x, y, 4, [(255, 255, 255)], 2.0, life=8, size=2)
            elif name == "point":
                colors = [CRIMSON, (255, 200, 60), WHITE] if side == 0 else [NAVY, (120, 190, 255), WHITE]
                self._burst(x, 0.1, 40, colors, 8.0, life=34, size=5, gravity=0.3, up=4.0, spread=1.1)
                self._burst(x, 0.05, 12, [SAND_DARK, SAND], 4.0, life=16, size=4, gravity=0.15, spread=1.3)
                self.shake = max(self.shake, 4)
                self.texts.append([WIDTH // 4 if side == 0 else 3 * WIDTH // 4, HEIGHT // 2,
                                   "POINT!", CRIMSON if side == 0 else NAVY, 34])

    # ------------------------------------------------------------------
    def _draw_bird(self, s, p, side, color):
        facing = 1.0 if side == 0 else -1.0
        back = -facing
        t = self.tick
        cx, cy = to_px(p.x, p.y)
        r = P_R * SCALE

        # 그림자: 높이 뜰수록 작고 옅어진다
        k = max(0.35, 1.0 - (p.y - P_R) / 7.0)
        shadow = pygame.Rect(0, 0, int(2.0 * r * k), int(14 * k))
        shadow.center = (cx, HEIGHT + 9)
        pygame.draw.ellipse(s, SAND_DARK, shadow)

        # 몸의 늘어남과 눌림
        sx = sy = 1.0
        if p.dive > 0:
            sx, sy = 1.28, 0.78
        elif self.squash[side] > 0:
            q = self.squash[side] / 7.0
            sx, sy = 1.0 + 0.22 * q, 1.0 - 0.22 * q
        elif not p.grounded:
            q = min(abs(p.vy) / JUMP_V, 1.0) * 0.14
            sx, sy = 1.0 - q, 1.0 + q
        walking = p.grounded and abs(p.vx) > 0.1 and p.dive == 0
        bob = abs(math.sin(t * 0.45)) * 5 if walking else 0.0
        cy = cy + r * (1.0 - sy) - bob          # 발이 땅에서 뜨지 않게 아래쪽을 고정한다
        rx, ry = r * sx, r * sy

        # 발
        if p.grounded and p.dive == 0:
            step = math.sin(t * 0.45) * 7 if walking else 0.0
            for off in (-0.35, 0.35):
                fx = cx + off * r + (step if off < 0 else -step)
                pygame.draw.ellipse(s, BEAK, (fx - 9, HEIGHT - 7, 20, 9))

        # 꼬리 깃
        pygame.draw.polygon(s, WING, [(cx + back * rx * 0.75, cy + ry * 0.15),
                                      (cx + back * rx * 1.35, cy + ry * 0.0),
                                      (cx + back * rx * 0.8, cy + ry * 0.55)])
        # 몸통
        body = pygame.Rect(cx - rx, cy - ry, 2 * rx, 2 * ry)
        pygame.draw.ellipse(s, WHITE, body)
        belly = pygame.Rect(0, 0, rx * 1.3, ry * 1.0)
        belly.center = (cx + facing * rx * 0.12, cy + ry * 0.35)
        pygame.draw.ellipse(s, BELLY, belly)
        pygame.draw.ellipse(s, DARK, body, 2)

        # 목도리 (팀 색) + 바람에 날리는 끝자락
        pygame.draw.arc(s, color, (cx - rx, cy - ry * 0.25, 2 * rx, ry * 1.2), math.pi, 2 * math.pi, 8)
        flutter = math.sin(t * 0.5 + side) * 5
        pygame.draw.polygon(s, color, [(cx + back * rx * 0.85, cy + ry * 0.25),
                                       (cx + back * rx * 1.5, cy + ry * 0.2 + flutter),
                                       (cx + back * rx * 1.25, cy + ry * 0.55 + flutter)])

        # 날개: 접힘 / 날갯짓 / 스윙
        length = r * 1.75
        if p.swing > 0:
            q = 1.0 - p.swing / SWING_FRAMES
            angle = math.radians(95 + 120 * q)          # 머리 위에서 앞쪽 아래로 휘두른다
            length = r * 2.0
        elif p.dive > 0:
            angle = math.radians(12)                    # 뒤로 쭉 편다
        elif not p.grounded:
            angle = math.radians(28 + 34 * math.sin(t * 0.9 + side))
        else:
            angle = math.radians(-38)
            length = r * 1.05
        shoulder = (cx + back * rx * 0.1, cy - ry * 0.25)
        tip = (shoulder[0] + back * length * math.cos(angle), shoulder[1] - length * math.sin(angle))
        mid = (shoulder[0] + back * length * 0.45 * math.cos(angle - 0.55),
               shoulder[1] - length * 0.45 * math.sin(angle - 0.55) + ry * 0.3)
        pygame.draw.polygon(s, WING, [shoulder, tip, mid])
        pygame.draw.line(s, WING_LIGHT, shoulder, tip, 3)
        if p.swing > 0:
            # 스윙 궤적
            arc = pygame.Rect(0, 0, length * 2, length * 2)
            arc.center = (int(shoulder[0]), int(shoulder[1]))
            a0, a1 = sorted((math.radians(95), angle))
            if facing > 0:
                a0, a1 = math.pi - a1, math.pi - a0
            pygame.draw.arc(self.fx, (255, 255, 255, 170), arc, a0, a1, 5)

        # 머리: 부리와 눈
        lean = 0.3 if p.dive > 0 else 0.0
        hx = cx + facing * rx * (0.55 + lean)
        hy = cy - ry * 0.38
        pygame.draw.polygon(s, BEAK, [(hx, hy - 8), (hx + facing * r * 0.8, hy + 3), (hx, hy + 10)])
        pygame.draw.line(s, (200, 120, 40), (hx, hy + 2), (hx + facing * r * 0.7, hy + 3), 1)
        ex, ey = int(hx - facing * r * 0.22), int(hy - 9)
        if p.recover > 0:
            # 경직: 눈이 X가 되고 머리 위에 별이 돈다
            for dx, dy in ((-4, -4), (-4, 4)):
                pygame.draw.line(s, DARK, (ex + dx, ey + dy), (ex - dx, ey - dy), 2)
            for i in range(3):
                a = t * 0.3 + i * 2.094
                star = (int(cx + math.cos(a) * r * 0.7), int(cy - ry - 14 + math.sin(a) * 5))
                pygame.draw.circle(s, (255, 205, 40), star, 5)
                pygame.draw.circle(s, (255, 245, 180), star, 2)
        elif (t + side * 47) % 110 < 5:
            pygame.draw.line(s, DARK, (ex - 5, ey), (ex + 5, ey), 2)          # 깜빡임
        else:
            pygame.draw.circle(s, DARK, (ex, ey), 5)
            pygame.draw.circle(s, WHITE, (ex + int(facing), ey - 2), 2)

    def _draw_ball(self, s, game):
        bx, by = to_px(game.bx, game.by)
        r = int(B_R * SCALE)
        speed = math.hypot(game.bvx, game.bvy)
        fast = speed > 0.72 * BALL_MAX_SPEED
        # 궤적
        self.trail.append((bx, by, fast))
        n = len(self.trail)
        for i, (tx, ty, tf) in enumerate(self.trail):
            k = (i + 1) / n
            color = (255, 150, 50, int(150 * k)) if tf else (255, 255, 255, int(90 * k))
            pygame.draw.circle(self.fx, color, (tx, ty), max(2, int(r * k * (0.95 if tf else 0.7))))
        if fast and self.tick % 2 == 0:
            self.particles.append([bx, by, self.rng.uniform(-1, 1), self.rng.uniform(-1, 1),
                                   10, 10, (255, 170, 60), 4, 0.0])
        # 그림자
        k = max(0.3, 1.0 - game.by / COURT_H)
        shadow = pygame.Rect(0, 0, int(2.2 * r * k), int(12 * k))
        shadow.center = (bx, HEIGHT + 11)
        pygame.draw.ellipse(s, SAND_DARK, shadow)
        # 공: 굴러가는 방향으로 무늬가 돈다
        self.ball_angle += game.bvx * 0.03
        pygame.draw.circle(s, (255, 236, 130), (bx, by), r)
        pygame.draw.circle(s, (255, 250, 205), (bx - r // 3, by - r // 3), r // 3)
        for i in range(3):
            a = self.ball_angle + i * 2.094
            pygame.draw.line(s, (214, 170, 60), (bx, by),
                             (bx + math.cos(a) * r * 0.92, by + math.sin(a) * r * 0.92), 2)
        pygame.draw.circle(s, DARK, (bx, by), r, 2)

    def _draw_panel(self, s, side, probs, color):
        """AI가 지금 어떤 행동을 선호하는지 막대로 보여준다.

        18개 행동을 조작 단위로 묶는다: 뒤/정지/앞 이동, 위(점프·로브), 아래 조준, 타격.
        """
        p = probs.reshape(3, 3, 2)          # [이동, 위아래, 타격]
        bars = [("BACK", p[0].sum()), ("STAY", p[1].sum()), ("FWD", p[2].sum()),
                ("UP", p[:, 1].sum()), ("DOWN", p[:, 2].sum()), ("HIT", p[:, :, 1].sum())]
        x0 = 20 if side == 0 else WIDTH - 20 - 170
        y0 = 50
        box = pygame.Surface((170, 20 * len(bars) + 12), pygame.SRCALPHA)
        box.fill((255, 255, 255, 150))
        s.blit(box, (x0, y0))
        for i, (name, value) in enumerate(bars):
            y = y0 + 8 + i * 20
            s.blit(self.tiny.render(name, True, DARK), (x0 + 8, y))
            pygame.draw.rect(s, (210, 210, 210), (x0 + 60, y + 2, 100, 12))
            pygame.draw.rect(s, color, (x0 + 60, y + 2, int(100 * float(value)), 12))

    # ------------------------------------------------------------------
    def draw(self, game, names=("LEFT", "RIGHT"), message=None, panels=None, caption=None):
        self.tick += 1
        self._handle_events(game)
        s = self.scene
        self.fx.fill((0, 0, 0, 0))
        s.blit(self.background, (0, 0))
        self._draw_clouds(s)
        self._draw_net(s)
        self._draw_bird(s, game.players[0], 0, CRIMSON)
        self._draw_bird(s, game.players[1], 1, NAVY)
        self._draw_ball(s, game)
        for side in (0, 1):
            if self.squash[side] > 0:
                self.squash[side] -= 1

        # 입자
        alive = []
        for q in self.particles:
            q[0] += q[2]
            q[1] += q[3]
            q[3] += q[8]
            q[4] -= 1
            if q[4] > 0:
                k = q[4] / q[5]
                pygame.draw.circle(self.fx, (*q[6], int(255 * k)), (int(q[0]), int(q[1])),
                                   max(1, int(q[7] * (0.4 + 0.6 * k))))
                alive.append(q)
        self.particles = alive
        s.blit(self.fx, (0, 0))
        if self.flash > 0:
            # 스파이크 순간 화면이 살짝 밝아진다
            glow = 14 * self.flash
            s.fill((glow, glow, glow), special_flags=pygame.BLEND_RGB_ADD)
            self.flash -= 1

        # 떠오르는 글자 (SPIKE!, POINT! 등)
        kept = []
        for item in self.texts:
            item[1] -= 1.6
            item[4] -= 1
            if item[4] > 0:
                font = self.big if item[2] == "POINT!" else self.font
                img = font.render(item[2], True, item[3])
                outline = font.render(item[2], True, WHITE)
                rect = img.get_rect(center=(int(item[0]), int(item[1])))
                for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                    s.blit(outline, rect.move(dx, dy))
                s.blit(img, rect)
                kept.append(item)
        self.texts = kept

        # 화면 흔들림을 적용해서 내보낸다. 점수와 패널은 흔들리지 않게 그 위에 그린다
        ox = oy = 0
        if self.shake > 0:
            ox, oy = self.rng.randint(-self.shake, self.shake), self.rng.randint(-self.shake, self.shake)
            self.shake -= 1
        out = self.screen
        out.fill(SAND)
        out.blit(s, (ox, oy))

        score = self.font.render(f"{game.score[0]}  :  {game.score[1]}", True, DARK)
        out.blit(score, score.get_rect(center=(WIDTH // 2, 30)))
        left = self.small.render(names[0], True, CRIMSON)
        right = self.small.render(names[1], True, NAVY)
        out.blit(left, (20, 18))
        out.blit(right, right.get_rect(topright=(WIDTH - 20, 18)))
        for side, probs in (panels or {}).items():
            self._draw_panel(out, side, probs, CRIMSON if side == 0 else NAVY)
        lines = [caption] if isinstance(caption, str) else (caption or [])
        for i, line in enumerate(lines):
            cap = self.mono.render(line, True, DARK)
            out.blit(cap, cap.get_rect(center=(WIDTH // 2, 62 + 22 * i)))
        if message:
            msg = self.font.render(message, True, DARK)
            out.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT // 3)))
        if not self.headless:
            pygame.display.flip()

    def frame_rgb(self):
        """현재 화면을 (H, W, 3) 배열로 돌려준다. 영상 녹화용."""
        return pygame.surfarray.array3d(self.screen).swapaxes(0, 1)

    def close(self):
        pygame.quit()
