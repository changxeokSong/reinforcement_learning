"""빔 탐색으로 찾은 통과 경로(시범, laser/data/campaign_demos.csv. Unity 메뉴 없이 LaserDemoProbe.Run으로 다시 만든다)를 Python 환경에서 재생해 (관측, 행동) 쌍을 만든다.

학습 전용 빌드의 training_layout 옵션으로 배치를 고정한다. 배치의 기하는 평가 빌드와 같다.
"""
import csv
from pathlib import Path

import numpy as np

from laser.env import FORWARD_ACTION, TIME_INDEX, LaserEnv

DEMOS = Path("laser/data/campaign_demos.csv")
LAYOUT_BUILD = "tmp/laser_layout_build/LaserMission.exe"


def load_demos(path=DEMOS):
    with open(path, encoding="utf-8") as f:
        return {(int(r["stage"]), int(r["layout"])): [int(a) for a in r["actions"].split()] for r in csv.DictReader(f)}


def replay(common, level, layout, actions, worker, seed=0):
    """시간 0에서 시작한 판에 시범 행동을 그대로 넣는다. (관측 목록, 결과, 첫 관측)을 돌려준다."""
    env = LaserEnv(n_areas=1, seed=seed, worker_id=worker, level=level, campaign_layouts=True, build=LAYOUT_BUILD,
                   obs_mode=common["obs_mode"], shaping=common["shaping"], time_penalty=common["time_penalty"],
                   time_scale=common["time_scale"])
    try:
        env.set_param("training_layout", layout)
        env.set_param("training_layout_prob", 1.0)
        env.set_level(level)
        obs = env.reset()
        while obs[0, TIME_INDEX] != 0:                 # 강제 리셋 직후의 준비 판을 끝까지 보낸다
            r = env.step(np.array([FORWARD_ACTION]))
            obs = r["obs"]
        states, outcome = [], None
        for a in actions:
            states.append(obs[0].copy())
            r = env.step(np.array([a]))
            obs = r["obs"]
            if r["results"]:
                outcome = r["results"][0][1]
                break
        return np.array(states), outcome, states[0]
    finally:
        env.close()
