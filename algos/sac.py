"""SAC (Soft Actor-Critic), 이산 행동용.

Haarnoja et al., 2018 / Christodoulou, 2019 (SAC-Discrete).
연속 행동용 SAC와 다른 점
- actor가 행동별 확률을 직접 출력하므로, 기대값을 샘플링 없이 정확히 계산한다
- Q 네트워크는 상태를 받아 모든 행동의 Q값을 한 번에 출력한다
- 온도 alpha는 정책 엔트로피가 목표값에 가까워지도록 자동 조절한다
"""
import copy
import math

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
    "train_freq": 4,
    "tau": 0.005,
    "target_entropy_ratio": 0.3,   # 목표 엔트로피 = ratio × log(행동 수)
    "init_alpha": 0.2,
    "hidden": 256,
}


class SAC:
    kind = "sac"

    def __init__(self, obs_dim, n_actions, n_envs, total_steps, cfg, seed=0):
        self.cfg = c = {**DEFAULTS, **cfg}
        self.obs_dim, self.n_actions, self.n_envs = obs_dim, n_actions, n_envs
        self.hidden = c["hidden"]
        self.actor = mlp(obs_dim, n_actions, c["hidden"])
        self.q1 = mlp(obs_dim, n_actions, c["hidden"])
        self.q2 = mlp(obs_dim, n_actions, c["hidden"])
        self.q1_target = copy.deepcopy(self.q1).requires_grad_(False)
        self.q2_target = copy.deepcopy(self.q2).requires_grad_(False)
        self.log_alpha = torch.tensor(math.log(c["init_alpha"]), requires_grad=True)
        self.target_entropy = c["target_entropy_ratio"] * math.log(n_actions)
        self.actor_opt = torch.optim.Adam(self.actor.parameters(), lr=c["lr"])
        self.q_opt = torch.optim.Adam(
            list(self.q1.parameters()) + list(self.q2.parameters()), lr=c["lr"])
        self.alpha_opt = torch.optim.Adam([self.log_alpha], lr=c["lr"])
        self.buffer = ReplayBuffer(c["buffer_size"], obs_dim)
        self.rng = np.random.default_rng(seed)
        self.steps = 0
        self.grad_debt = 0.0

    @torch.no_grad()
    def act_train(self, obs):
        if self.steps < self.cfg["learning_starts"]:
            return self.rng.integers(0, self.n_actions, size=len(obs))
        logits = self.actor(torch.as_tensor(obs, dtype=torch.float32))
        return torch.distributions.Categorical(logits=logits).sample().numpy()

    def observe(self, obs, act, rew, next_obs, final_obs, terminated, truncated):
        c = self.cfg
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
        alpha = self.log_alpha.exp().detach()

        # ---- critic: soft Bellman target ----
        with torch.no_grad():
            next_logp = F.log_softmax(self.actor(next_obs), dim=-1)
            next_p = next_logp.exp()
            next_q = torch.min(self.q1_target(next_obs), self.q2_target(next_obs))
            next_v = (next_p * (next_q - alpha * next_logp)).sum(-1)
            target = rew + c["gamma"] * (1.0 - done) * next_v
        q1 = self.q1(obs).gather(1, act.unsqueeze(1)).squeeze(1)
        q2 = self.q2(obs).gather(1, act.unsqueeze(1)).squeeze(1)
        q_loss = F.mse_loss(q1, target) + F.mse_loss(q2, target)
        self.q_opt.zero_grad()
        q_loss.backward()
        self.q_opt.step()

        # ---- actor: 행동 확률로 기대값을 정확히 계산 ----
        logp = F.log_softmax(self.actor(obs), dim=-1)
        p = logp.exp()
        with torch.no_grad():
            q_min = torch.min(self.q1(obs), self.q2(obs))
        actor_loss = (p * (alpha * logp - q_min)).sum(-1).mean()
        self.actor_opt.zero_grad()
        actor_loss.backward()
        self.actor_opt.step()

        # ---- alpha: 엔트로피가 목표보다 낮으면 alpha를 키운다 ----
        entropy = -(p * logp).sum(-1).mean().detach()
        alpha_loss = self.log_alpha * (entropy - self.target_entropy)
        self.alpha_opt.zero_grad()
        alpha_loss.backward()
        self.alpha_opt.step()

        with torch.no_grad():
            for net, tgt in ((self.q1, self.q1_target), (self.q2, self.q2_target)):
                for p_, pt in zip(net.parameters(), tgt.parameters()):
                    pt.lerp_(p_, c["tau"])
        return {"q_loss": q_loss.item(), "actor_loss": actor_loss.item(),
                "entropy": entropy.item(), "alpha": alpha.item()}

    def policy_net(self):
        return self.actor

    def snapshot(self, action_table, name="snapshot", greedy=False):
        net = copy.deepcopy(self.actor).eval()
        return FrozenPolicy(net, self.kind, action_table, name, greedy,
                            seed=int(self.rng.integers(1 << 30)))
