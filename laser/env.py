"""Unity 레이저 미션 환경을 우리 알고리즘이 쓰는 형태(VecVolley와 비슷한 벡터 환경)로 감싼다.

Unity 실행 파일 하나 안에 방 n개가 있고, 방마다 에이전트가 하나씩 있다.
모든 에이전트는 매 스텝 함께 결정을 내리므로(DecisionPeriod=1) 일반 벡터 환경처럼 쓸 수 있다.

step()이 돌려주는 값
  obs         다음 관측 (끝난 방은 이미 새 에피소드의 첫 관측)
  final_obs   끝난 방의 마지막 관측 (나머지는 obs와 같음)
  reward, terminated(성공·충돌·게임 시간 제한), truncated(Unity에서 전달된 외부 중단)
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
TIME_INDEX = 8              # Room.Observe의 time / TimeLimit
LEVEL_INDEX = 9             # Room.Observe의 level / 4f
N_ACTIONS = 27
FORWARD_ACTION = 7


class LaserEnv:
    def __init__(self, n_areas=16, seed=0, worker_id=0, level=0, shaping=0.5, time_penalty=0.01, obs_mode=1, extra_args=(),
                 time_scale=100.0, graphics=False, build=DEFAULT_BUILD, *, potential_shaping=False, shaping_gamma=0.99,
                 campaign_layouts=False):
        self.n = n_areas
        self.engine = EngineConfigurationChannel()
        self.params = EnvironmentParametersChannel()
        self.env = UnityEnvironment(
            file_name=str(build), worker_id=worker_id, seed=seed, no_graphics=not graphics,
            side_channels=[self.engine, self.params],
            additional_args=["-areas", str(n_areas), "-envseed", str(seed)] +
                            ([] if graphics else ["-batchmode"]) + list(extra_args),
            timeout_wait=120,
        )
        self.engine.set_configuration_parameters(time_scale=time_scale, target_frame_rate=-1,
                                                 width=960, height=540, quality_level=0)
        self.set_level(level)
        if campaign_layouts:
            self.set_param("campaign_layouts", 1)
        self.set_param("shaping", shaping)
        if potential_shaping:
            self.set_param("potential_shaping", 1)
            self.set_param("shaping_gamma", shaping_gamma)
        self.set_param("time_penalty", time_penalty)
        self.set_param("obs_mode", obs_mode)
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

    def reset(self, *, expected_level=None):
        """모든 방을 새 에피소드로 시작한다 (평가할 때 쓴다)."""
        self.env.reset()
        dec, _ = self.env.get_steps(self.behavior)
        self.obs = self._gather(dec)
        self.ep_len[:] = 0
        if expected_level is not None:
            actual = self.obs[:, LEVEL_INDEX] * 4
            if not np.allclose(actual, expected_level):
                raise RuntimeError(
                    f"레벨 {expected_level}을 요청했지만 Unity가 레벨 "
                    f"{np.unique(actual).tolist()}을 반환했습니다. Unity 빌드를 확인하세요."
                )
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
                else:   # 시간 초과도 실패(-1)로 끝난다. 종료 관측의 시뮬레이션 시간을 사용한다.
                    kind = "timeout" if final_obs[i, TIME_INDEX] >= 1.0 else "hit"
            results.append((i, kind, int(self.ep_len[i])))
            self.ep_len[i] = 0
        self.obs = obs
        return {"obs": obs, "final_obs": final_obs, "reward": reward,
                "terminated": terminated, "truncated": truncated, "results": results}

    def evaluation_reset(self, level):
        """평가를 시작하고, 아직 시간 0에서 출발하지 않은 방을 표시한다."""
        self.set_level(level)
        obs = self.reset(expected_level=level)
        return obs, obs[:, TIME_INDEX] > 0

    def evaluation_step(self, actions, warmup):
        """준비 판의 결과는 제외하고 자동 재시작한 방의 warmup 플래그를 해제한다."""
        # Academy의 강제 리셋 직후에는 기본 행동이 이미 한 번 실행돼 있을 수 있다.
        # 방마다 자동 재시작 후 시간 0인 관측에서 시작한 에피소드부터 집계한다.
        result = self.step(np.where(warmup, FORWARD_ACTION, actions))
        scored = []
        for episode in result["results"]:
            slot = episode[0]
            if warmup[slot]:
                if result["obs"][slot, TIME_INDEX] != 0:
                    raise RuntimeError("Evaluation did not receive a fresh automatic restart")
                warmup[slot] = False
            else:
                scored.append(episode)
        result["results"] = scored
        return result

    def close(self):
        self.env.close()
