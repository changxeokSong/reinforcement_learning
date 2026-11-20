"""직접 구현한 알고리즘이 맞게 동작하는지 CartPole-v1로 확인한다.

배구에서 학습이 안 될 때 "알고리즘 버그인지, 환경이 어려운 건지"를 가르기 위한 검증이다.
세 알고리즘 모두 평균 리턴 195 이상(최대 500)에 도달하면 통과로 본다.

실행: python -m tests.check_algos [--algo ppo dqn sac] [--steps 100000]
"""
import argparse
import json
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch

from algos import ALGOS

# CartPole은 배구보다 훨씬 짧은 문제라서 탐험·워밍업 관련 값만 줄인다
OVERRIDES = {
    "ppo": {"n_steps": 128, "hidden": 64},
    "dqn": {"learning_starts": 1000, "eps_fraction": 0.2, "train_freq": 1, "hidden": 64,
            "buffer_size": 50_000, "batch_size": 128},
    "sac": {"learning_starts": 1000, "train_freq": 1, "hidden": 64,
            "buffer_size": 50_000, "batch_size": 128},
}


def check_ppo_diagnostics():
    # 균등 정책을 고정하면 확률비 1, KL 추정치 0, clip fraction 0이어야 한다.
    agent = ALGOS["ppo"](4, 2, 2, 8, {"n_steps": 4, "lr": 0, "hidden": 8})
    with torch.no_grad():
        for param in agent.params:
            param.zero_()
    obs = np.zeros((2, 4), dtype=np.float32)
    reward = np.ones(2, dtype=np.float32)
    done = np.zeros(2, dtype=bool)
    for _ in range(4):
        action = agent.act_train(obs)
        diagnostics = agent.observe(obs, action, reward, obs, obs, done, done)
    np.testing.assert_allclose(diagnostics["entropy"], np.log(2), atol=1e-6)
    np.testing.assert_allclose(diagnostics["approx_kl"], 0, atol=1e-6)
    assert diagnostics["clip_fraction"] == 0
    assert np.isfinite(diagnostics["v_loss"]) and diagnostics["v_loss"] > 0
    print("PPO 고정 균등 정책: entropy=log(2), KL=0, clip fraction=0")


def run(algo, total_steps, seed=0, n_envs=8, diagnostics=None):
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    envs = gym.vector.SyncVectorEnv([lambda: gym.make("CartPole-v1") for _ in range(n_envs)],
                                    autoreset_mode=gym.vector.AutoresetMode.SAME_STEP)
    obs, _ = envs.reset(seed=seed)
    obs = obs.astype(np.float32)
    agent = ALGOS[algo](4, 2, n_envs, total_steps, OVERRIDES[algo], seed=seed)
    returns, ep_ret, best = [], np.zeros(n_envs), 0.0
    start = time.time()
    for step in range(0, total_steps, n_envs):
        act = agent.act_train(obs)
        next_obs, rew, term, trunc, info = envs.step(act)
        next_obs = next_obs.astype(np.float32)
        final_obs = next_obs.copy()
        for i in np.nonzero(term | trunc)[0]:
            final_obs[i] = info["final_obs"][i]
        # 보상을 0.01배로 줄여 배구(±1)와 비슷한 크기로 맞춘다
        stats = agent.observe(obs, act, (rew * 0.01).astype(np.float32), next_obs, final_obs, term, trunc)
        if diagnostics is not None and algo == "ppo" and stats:
            diagnostics.append({"algo": algo, "seed": seed, "step": step + n_envs, **stats})
        obs = next_obs
        ep_ret += rew
        for i in np.nonzero(term | trunc)[0]:
            returns.append(ep_ret[i])
            ep_ret[i] = 0.0
        if len(returns) >= 20:
            best = max(best, float(np.mean(returns[-20:])))
    last = float(np.mean(returns[-20:]))
    envs.close()
    if diagnostics is not None:
        diagnostics.append({"algo": algo, "seed": seed, "steps": total_steps,
                            "last_20_return": last, "best_20_return": best, "passed": best >= 195})
    print(f"{algo} seed {seed}: 최근 20판 평균 {last:6.1f}, 학습 중 최고 {best:6.1f}  "
          f"({time.time() - start:.0f}초)  {'통과' if best >= 195 else '실패'}")
    return best >= 195


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--algo", nargs="*", default=["ppo", "dqn", "sac"])
    ap.add_argument("--steps", type=int, default=100_000)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--diagnostics-out", type=Path, help="PPO 갱신 로그와 각 실행의 최종 검증 요약을 JSON으로 저장")
    args = ap.parse_args()
    diagnostics = [] if args.diagnostics_out is not None else None
    if "ppo" in args.algo:
        check_ppo_diagnostics()
    ok = [run(a, args.steps, seed=seed, diagnostics=diagnostics) for seed in args.seeds for a in args.algo]
    if args.diagnostics_out is not None:
        args.diagnostics_out.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostics_out.write_text(json.dumps(diagnostics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    raise SystemExit(0 if all(ok) else 1)
