"""개선 과정을 단계별로 보여주는 GIF를 만든다 (발표·README용).

  steps : 같은 배치(10단계 배치 3)를 단계마다의 정책이 차례로 플레이한다 → docs/figures/laser_steps.gif
  full  : 최종 학생 정책 하나가 1~10단계를 연속으로 통과한다 → docs/figures/laser_campaign.gif

  .venv-unity\\Scripts\\python -m laser.record_steps steps
  .venv-unity\\Scripts\\python -m laser.record_steps full

Unity 창이 잠깐 뜨고, 매 프레임을 PNG로 저장한 뒤 글자를 얹어 GIF로 묶는다.
강제 리셋 직후의 준비 판(시간 0에서 시작하지 않은 판)은 잘라낸다.
"""
import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from algos.common import load_policy
from laser.demos import LAYOUT_BUILD
from laser.env import FORWARD_ACTION, TIME_INDEX, LaserEnv

FONT = "C:/Windows/Fonts/malgunbd.ttf"
STEPS = [
    ("1단계 · 강화학습 정책 하나 (PPO)", "runs/laser/x12/ppo_random_campaign_seed0/model.pt"),
    ("2단계 · 10단계만 집중 학습한 PPO", "runs/laser/specialists_v3/ppo_level10_layout3_seed0/model.pt"),
    ("3단계 · 모방 학습 학생 (정책 하나)", "runs/laser/imitation/bc_v2_seed0/model.pt"),
    ("4단계 · 학생 + 통과 경로 시범", "runs/laser/imitation/bc_v2_demo_seed0/model.pt"),
]
FINAL = "runs/laser/imitation/bc_v2_demo_seed0/model.pt"


def open_env(frames, worker, level, layout=None):
    env = LaserEnv(n_areas=1, seed=7, worker_id=worker, level=level, time_scale=1.0, graphics=True,
                   campaign_layouts=True, build=LAYOUT_BUILD,
                   extra_args=["-record", str(frames), "-mute", "-view", "1",
                               "-screen-width", "1280", "-screen-height", "720"])
    env.set_param("hud_algo", 0)
    if layout is not None:
        env.set_param("training_layout", layout)
        env.set_param("training_layout_prob", 1.0)
    return env


def frame_count(frames):
    return len(list(Path(frames).glob("frame_*.png")))


def run_one(env, policy, frames, tail=12):
    """시간 0에서 시작하는 판을 한 번 플레이한다. (시작 프레임, 끝 프레임, 결과)를 돌려준다."""
    obs = env.reset()
    while obs[0, TIME_INDEX] != 0:
        obs = env.step(np.array([FORWARD_ACTION]))["obs"]
    start = frame_count(frames)
    outcome = None
    while outcome is None:
        r = env.step(policy.act(obs))
        obs = r["obs"]
        if r["results"]:
            outcome = r["results"][0][1]
    for _ in range(tail):                      # 결과(성공/충돌) 연출이 보이도록 조금 더 찍는다
        env.step(np.array([0]))
    return start, frame_count(frames), outcome


def caption(im, text, sub, color):
    draw = ImageDraw.Draw(im)
    w = im.width
    draw.rectangle([0, 0, w, 56], fill=(10, 10, 20))
    draw.text((14, 6), text, font=ImageFont.truetype(FONT, 20), fill=(255, 255, 255))
    draw.text((14, 32), sub, font=ImageFont.truetype(FONT, 15), fill=color)
    return im


def collect(frames, start, end, skip, width, text, sub, color, hold=20):
    files = sorted(Path(frames).glob("frame_*.png"))[start:end:skip]
    out = []
    for f in files:
        im = Image.open(f).convert("RGB")
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        out.append(caption(im, text, sub, color))
    return out + [out[-1]] * hold               # 마지막 장면에서 잠깐 멈춘다


def save_gif(frames, out, skip):
    pal = [f.quantize(colors=64, method=Image.Quantize.MEDIANCUT) for f in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=int(1000 / 30 * skip), loop=0, optimize=True)
    print(f"저장: {out} ({len(pal)}프레임, {Path(out).stat().st_size / 1e6:.1f}MB)")


def steps_gif(args):
    all_frames = []
    for k, (title, model) in enumerate(STEPS):
        with tempfile.TemporaryDirectory(prefix="laser_steps_") as d:
            env = open_env(d, args.worker + 4 * k, 10, layout=3)
            try:
                start, end, outcome = run_one(env, load_policy(model, greedy=True), d)
            finally:
                env.close()
            ok = outcome == "success"
            sub = "결과: 통과" if ok else "결과: 레이저에 닿아 실패" if outcome == "hit" else f"결과: {outcome}"
            print(title, outcome)
            all_frames += collect(d, start, end, args.skip, args.width, title, "10단계 · 배치 3   " + sub,
                                  (120, 255, 140) if ok else (255, 120, 110))
    save_gif(all_frames, args.out or "docs/figures/laser_steps.gif", args.skip)


def full_gif(args):
    """최종 학생 하나가 1~10단계를 이어서 통과한다. 단계마다 배치는 무작위다."""
    policy = load_policy(FINAL, greedy=True)
    all_frames, rng = [], np.random.default_rng(args.seed)
    for level in range(1, 11):
        with tempfile.TemporaryDirectory(prefix="laser_full_") as d:
            env = open_env(d, args.worker + 4 * level, level, layout=int(rng.integers(4)))
            try:
                env.set_level(level)
                start, end, outcome = run_one(env, policy, d, tail=8)
            finally:
                env.close()
            print(f"{level}단계", outcome)
            if outcome != "success":
                raise SystemExit(f"{level}단계에서 {outcome}")
            all_frames += collect(d, start, end, args.skip, args.width, f"정책 하나로 1~10단계 · {level}단계",
                                  "모방 학습 학생   결과: 통과", (120, 255, 140), hold=6)
    save_gif(all_frames, args.out or "docs/figures/laser_campaign.gif", args.skip)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("what", choices=["steps", "full"])
    ap.add_argument("--out")
    ap.add_argument("--width", type=int, default=560)
    ap.add_argument("--skip", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--worker", type=int, default=1900)
    args = ap.parse_args()
    steps_gif(args) if args.what == "steps" else full_gif(args)


if __name__ == "__main__":
    main()
