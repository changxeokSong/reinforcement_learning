"""Unity 빌드에서 잠재함수 보상과 종료 플래그를 확인한다."""
import numpy as np

from laser.env import TIME_INDEX, LaserEnv


def potential(obs):
    # 관측 10번은 금고까지의 거리 / 방 길이(20m)다.
    return -0.5 * float(obs[0, 10]) * 20 / 17.1


def check_episode(env, level, action, expected, gamma):
    env.set_level(level)
    obs = env.reset(expected_level=level)
    start_potential = potential(obs)
    discounted_shaping = 0.0
    for step in range(230):
        result = env.step([action])
        episode = result["results"]
        base_reward = -0.01
        if episode:
            base_reward += 1 if episode[0][1] == "success" else -1
        next_potential = 0.0 if episode else potential(result["obs"])
        measured = result["reward"][0] - base_reward
        np.testing.assert_allclose(measured, gamma * next_potential - potential(obs), atol=2e-6)
        discounted_shaping += gamma**step * measured
        obs = result["obs"]
        if episode:
            assert episode[0][1] == expected, episode
            assert result["terminated"][0] and not result["truncated"][0]
            np.testing.assert_allclose(discounted_shaping, -start_potential, atol=2e-6)
            print(f"{expected}: {step + 1} decisions", flush=True)
            return
    raise AssertionError(f"No terminal outcome: {expected}")


def check_evaluation_start(env):
    obs, warmup = env.evaluation_reset(0)
    if warmup[0]:
        for _ in range(230):
            result = env.evaluation_step([4], warmup)
            assert not result["results"], "A warmup outcome was counted"
            if not warmup[0]:
                obs = result["obs"]
                break
    assert not warmup[0]
    np.testing.assert_array_equal(obs[0, [3, 4, 5, TIME_INDEX]], np.zeros(4))
    for _ in range(230):
        result = env.evaluation_step([7], warmup)
        if result["results"]:
            assert result["results"][0][1] == "success"
            print("Evaluation starts at game time zero", flush=True)
            return
    raise AssertionError("The first scored episode did not finish")


if __name__ == "__main__":
    gamma = 0.97  # 학습기에서 할인율을 넘기는지 확인하기 위해 기본값과 다르게 둔다.
    env = LaserEnv(n_areas=1, seed=1000, worker_id=991, potential_shaping=True, shaping_gamma=gamma)
    try:
        check_episode(env, level=0, action=7, expected="success", gamma=gamma)
        check_episode(env, level=1, action=7, expected="hit", gamma=gamma)
        check_episode(env, level=0, action=4, expected="timeout", gamma=gamma)
        check_evaluation_start(env)
    finally:
        env.close()
