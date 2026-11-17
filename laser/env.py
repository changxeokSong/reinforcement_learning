"""Unity 레이저 미션 환경을 우리 알고리즘이 쓰는 형태(VecVolley와 비슷한 벡터 환경)로 감싼다.

Unity 실행 파일 하나 안에 방 n개가 있고, 방마다 에이전트가 하나씩 있다.
모든 에이전트는 매 스텝 함께 결정을 내리므로(DecisionPeriod=1) 일반 벡터 환경처럼 쓸 수 있다.

step()이 돌려주는 값
  obs         다음 관측 (끝난 방은 이미 새 에피소드의 첫 관측)
  final_obs   끝난 방의 마지막 관측 (나머지는 obs와 같음)
  reward, terminated(성공·실패·시간 초과), truncated(쓰지 않음)
  results     이번 스텝에 끝난 에피소드 [(방 번호, "success"|"hit"|"timeout", 길이)]
"""
from pathlib import Path

import numpy as np
from mlagents_envs.base_env import ActionTuple
from mlagents_envs.environment import UnityEnvironment
from mlagents_envs.side_channel.engine_configuration_channel import EngineConfigurationChannel
from mlagents_envs.side_channel.environment_parameters_channel import EnvironmentParametersChannel

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUILD = ROOT / "unity" / "LaserMission" / "Build" / "LaserMission.exe"
OBS_DIM = 66
N_ACTIONS = 27
EPISODE_STEPS = 200          # 20초 = 결정 200번


class LaserEnv:
    def __init__(self, n_areas=16, seed=0, worker_id=0, level=0, shaping=0.5, time_penalty=0.01,
                 time_scale=100.0, graphics=False, build=DEFAULT_BUILD):
        self.n = n_areas
        self.engine = EngineConfigurationChannel()
        self.params = EnvironmentParametersChannel()
        self.env = UnityEnvironment(
            file_name=str(build), worker_id=worker_id, seed=seed, no_graphics=not graphics,
            side_channels=[self.engine, self.params],
            additional_args=["-areas", str(n_areas), "-envseed", str(seed)] +
                            ([] if graphics else ["-batchmode"]),
            timeout_wait=120,
        )
        self.engine.set_configuration_parameters(time_scale=time_scale, target_frame_rate=-1,
                                                 width=960, height=540, quality_level=0)
        self.set_level(level)
        self.set_param("shaping", shaping)
        self.set_param("time_penalty", time_penalty)
        self.env.reset()
        self.behavior = list(self.env.behavior_specs)[0]
        dec, _ = self.env.get_steps(self.behavior)
        assert len(dec) == n_areas, f"에이전트 {len(dec)}개 (방 {n_areas}개 예상)"
        self.ids = np.sort(dec.agent_id)
        self.slot = {a: i for i, a in enumerate(self.ids)}
        self.obs = self._gather(dec)
        self.ep_len = np.zeros(n_areas, dtype=np.int64)

    def set_param(self, key, value):
        self.params.set_float_parameter(key, float(value))

    def set_level(self, level):
        """다음 에피소드부터 적용된다. -1이면 에피소드마다 1~4 중 무작위."""
        self.level = level
        self.set_param("level", level)

    def _gather(self, steps):
        out = np.zeros((self.n, OBS_DIM), dtype=np.float32)
        for k, a in enumerate(steps.agent_id):
            out[self.slot[a]] = steps.obs[0][k]
        return out

    def reset(self):
        """모든 방을 새 에피소드로 시작한다 (평가할 때 쓴다)."""
        self.env.reset()
        dec, _ = self.env.get_steps(self.behavior)
        self.obs = self._gather(dec)
        self.ep_len[:] = 0
        return self.obs

    def step(self, actions):
        dec, _ = self.env.get_steps(self.behavior)
        order = np.array([self.slot[a] for a in dec.agent_id])
        self.env.set_actions(self.behavior, ActionTuple(discrete=np.asarray(actions)[order].reshape(-1, 1).astype(np.int32)))
        self.env.step()
        dec, term = self.env.get_steps(self.behavior)
        if len(dec) != self.n:
            raise RuntimeError(f"결정 요청이 {len(dec)}개뿐이다 (방 {self.n}개). 에이전트 동기화가 깨졌다")

        reward = np.zeros(self.n, dtype=np.float32)
        for k, a in enumerate(dec.agent_id):
            reward[self.slot[a]] = dec.reward[k]
        obs = self._gather(dec)
        final_obs = obs.copy()
        terminated = np.zeros(self.n, dtype=bool)
        truncated = np.zeros(self.n, dtype=bool)
        self.ep_len += 1
        results = []
        for k, a in enumerate(term.agent_id):
            i = self.slot[a]
            reward[i] = term.reward[k]
            final_obs[i] = term.obs[0][k]
            if term.interrupted[k]:
                truncated[i] = True
                kind = "timeout"
            else:
                terminated[i] = True
                if term.reward[k] > 0:
                    kind = "success"
                else:   # 시간 초과도 실패(-1)로 끝난다. 길이로 구분한다
                    kind = "timeout" if self.ep_len[i] >= EPISODE_STEPS else "hit"
            results.append((i, kind, int(self.ep_len[i])))
            self.ep_len[i] = 0
        self.obs = obs
        return {"obs": obs, "final_obs": final_obs, "reward": reward,
                "terminated": terminated, "truncated": truncated, "results": results}

    def close(self):
        self.env.close()
