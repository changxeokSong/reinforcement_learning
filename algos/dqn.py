"""DQN (Deep Q-Network), Double DQN 방식.

Mnih et al., 2015 / van Hasselt et al., 2016.
- replay buffer + target network
- epsilon-greedy 탐험 (선형 감소)
- 행동 선택은 online 네트워크, 가치 평가는 target 네트워크 (Double DQN)
"""
import copy

import numpy as np
import torch
import torch.nn.functional as F

from .common import FrozenPolicy, ReplayBuffer, mlp

DEFAULTS = {
    "lr": 3e-4,
    "gamma": 0.99,
    "buffer_size": 500_000,
    "batch_size": 256,
    "learning_starts": 10_000,
    "train_freq": 4,             # 환경 스텝 4번마다 gradient step 1번
    "tau": 0.005,                # target network soft update
    "eps_start": 1.0,
    "eps_end": 0.05,
    "eps_fraction": 0.3,         # 전체 학습의 앞 30% 동안 epsilon을 줄인다
    "max_grad_norm": 10.0,
    "hidden": 256,
    "target_clip": None,         # Bellman 목표값을 [-x, x]로 자른다 (SAC와 같은 안정화)
}


class DQN:
    kind = "dqn"

    def __init__(self, obs_dim, n_actions, n_envs, total_steps, cfg, seed=0):
        self.cfg = c = {**DEFAULTS, **cfg}
        self.obs_dim, self.n_actions, self.n_envs = obs_dim, n_actions, n_envs
        self.hidden = c["hidden"]
        self.total_steps = total_steps
        self.q = mlp(obs_dim, n_actions, c["hidden"])
        self.q_target = copy.deepcopy(self.q).requires_grad_(False)
        self.opt = torch.optim.Adam(self.q.parameters(), lr=c["lr"])
        self.buffer = ReplayBuffer(c["buffer_size"], obs_dim)
        self.rng = np.random.default_rng(seed)
        self.steps = 0
        self.grad_debt = 0.0

    def epsilon(self):
        c = self.cfg
        frac = min(self.steps / (c["eps_fraction"] * self.total_steps), 1.0)
        return c["eps_start"] + frac * (c["eps_end"] - c["eps_start"])

    @torch.no_grad()
    def act_train(self, obs):
        a = self.q(torch.as_tensor(obs, dtype=torch.float32)).argmax(-1).numpy()
        explore = self.rng.random(len(a)) < self.epsilon()
        a[explore] = self.rng.integers(0, self.n_actions, size=int(explore.sum()))
        return a

    def observe(self, obs, act, rew, next_obs, final_obs, terminated, truncated):
        c = self.cfg
        # 끝난 에피소드는 자동 재시작 전의 실제 마지막 관측을 다음 상태로 저장한다.
        # 시간 제한(truncated)은 done으로 치지 않는다 (bootstrap 유지).
        done = terminated | truncated
        real_next = np.where(done[:, None], final_obs, next_obs)
        self.buffer.add_batch(obs, act, rew, real_next, terminated.astype(np.float32))
        self.steps += self.n_envs
        if self.steps < c["learning_starts"]:
            return None
        self.grad_debt += self.n_envs / c["train_freq"]
        stats = None
        while self.grad_debt >= 1.0:
            self.grad_debt -= 1.0
            stats = self._update()
        return stats

    def _update(self):
        c = self.cfg
        obs, act, rew, next_obs, done = self.buffer.sample(c["batch_size"], self.rng)
        with torch.no_grad():
            next_a = self.q(next_obs).argmax(-1, keepdim=True)
            next_q = self.q_target(next_obs).gather(1, next_a).squeeze(1)
            target = rew + c["gamma"] * (1.0 - done) * next_q
            if c.get("target_clip"):
                target = target.clamp(-c["target_clip"], c["target_clip"])
        q = self.q(obs).gather(1, act.unsqueeze(1)).squeeze(1)
        loss = F.smooth_l1_loss(q, target)
        self.opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q.parameters(), c["max_grad_norm"])
        self.opt.step()
        with torch.no_grad():
            for p, pt in zip(self.q.parameters(), self.q_target.parameters()):
                pt.lerp_(p, c["tau"])
        return {"q_loss": loss.item(), "q_mean": q.mean().item(), "epsilon": self.epsilon()}

    def policy_net(self):
        return self.q

    def snapshot(self, action_table, name="snapshot", greedy=False):
        net = copy.deepcopy(self.q).eval()
        return FrozenPolicy(net, self.kind, action_table, name, greedy,
                            seed=int(self.rng.integers(1 << 30)))
