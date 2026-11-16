"""여러 경기를 한꺼번에 진행하는 벡터 환경.

양쪽 선수의 행동을 모두 밖에서 받는다. 그래서 학습 중인 에이전트(왼쪽)와
상대(오른쪽)를 자유롭게 조합할 수 있고, self-play와 리그전에 같은 코드를 쓴다.

한 에피소드 = 한 점. 득점하면 끝나고(terminated), 랠리 시간 제한에 걸리면
무승부로 끝난다(truncated). 끝난 경기는 자동으로 다시 시작한다.
"""
import numpy as np

from .game import OBS_DIM, Game


class VecVolley:
    def __init__(self, n_envs, seed=0, shaping=0.0):
        """shaping: 공을 상대 코트로 넘길 때마다 주는 보조 보상 (0이면 사용 안 함)"""
        self.n = n_envs
        self.shaping = shaping
        self.games = [Game(seed=seed * 100003 + i) for i in range(n_envs)]

    def _obs(self, side):
        return np.array([g.observe(side) for g in self.games], dtype=np.float32)

    def reset(self):
        for g in self.games:
            g.reset()
        return self._obs(0), self._obs(1)

    def step(self, actions_left, actions_right):
        """행동은 게임 행동 번호(0~17) 배열.

        반환 dict
          obs, obs_opp : 다음 관측 (끝난 경기는 새 랠리의 첫 관측)
          final_obs    : 자동 재시작 전의 실제 마지막 관측 (끝난 경기에서만 의미 있음)
          reward       : 왼쪽 선수 기준 보상 (득점 +1, 실점 -1)
          terminated, truncated
          stats        : 끝난 경기의 (환경 번호, 승자, 랠리 통계) 목록
        """
        n = self.n
        reward = np.zeros(n, dtype=np.float32)
        terminated = np.zeros(n, dtype=bool)
        truncated = np.zeros(n, dtype=bool)
        final_obs = np.zeros((n, OBS_DIM), dtype=np.float32)
        stats = []
        for i, g in enumerate(self.games):
            winner, timeout = g.step(int(actions_left[i]), int(actions_right[i]))
            reward[i] = winner + self.shaping * g.last_crossed[0]
            if winner != 0 or timeout:
                terminated[i] = winner != 0
                truncated[i] = timeout
                final_obs[i] = g.observe(0)
                stats.append((i, winner, g.last_stats))
                g.reset()
        return {
            "obs": self._obs(0), "obs_opp": self._obs(1), "final_obs": final_obs,
            "reward": reward, "terminated": terminated, "truncated": truncated,
            "stats": stats,
        }
