"""PPO (Proximal Policy Optimization), 이산 행동용.

Schulman et al., 2017. clipped surrogate objective + GAE.
- actor와 critic은 따로 둔 MLP
- 병렬 환경 N개에서 n_steps씩 모은 뒤, 미니배치로 여러 epoch 업데이트
"""
import copy

import numpy as np
import torch
import torch.nn as nn

from .common import FrozenPolicy, mlp

DEFAULTS = {
    "lr": 3e-4,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip": 0.2,
    "ent_coef": 0.01,
    "vf_coef": 0.5,
    "n_steps": 256,          # 환경 하나당 rollout 길이
    "epochs": 4,
    "minibatches": 4,
    "max_grad_norm": 0.5,
    "anneal_lr": True,
    "hidden": 256,
}


class PPO:
    kind = "ppo"

    def __init__(self, obs_dim, n_actions, n_envs, total_steps, cfg, seed=0):
        self.cfg = c = {**DEFAULTS, **cfg}
        self.obs_dim, self.n_actions, self.n_envs = obs_dim, n_actions, n_envs
        self.hidden = c["hidden"]
        self.actor = mlp(obs_dim, n_actions, c["hidden"], act=nn.Tanh)
        self.critic = mlp(obs_dim, 1, c["hidden"], act=nn.Tanh)
        self.params = list(self.actor.parameters()) + list(self.critic.parameters())
        self.opt = torch.optim.Adam(self.params, lr=c["lr"], eps=1e-5)
        self.rng = np.random.default_rng(seed)

        T, N = c["n_steps"], n_envs
        self.total_updates = max(total_steps // (T * N), 1)
        self.updates = 0
        self.t = 0
        self.b_obs = torch.zeros(T, N, obs_dim)
        self.b_act = torch.zeros(T, N, dtype=torch.long)
        self.b_logp = torch.zeros(T, N)
        self.b_val = torch.zeros(T, N)
        self.b_rew = torch.zeros(T, N)
        self.b_done = torch.zeros(T, N)

    # ------------------------------------------------------------------
    @torch.no_grad()
    def act_train(self, obs):
        o = torch.as_tensor(obs, dtype=torch.float32)
        dist = torch.distributions.Categorical(logits=self.actor(o))
        a = dist.sample()
        t = self.t
        self.b_obs[t], self.b_act[t] = o, a
        self.b_logp[t] = dist.log_prob(a)
        self.b_val[t] = self.critic(o).squeeze(-1)
        return a.numpy()

    @torch.no_grad()
    def observe(self, obs, act, rew, next_obs, final_obs, terminated, truncated):
        """한 스텝 결과를 저장한다. rollout이 다 차면 업데이트하고 학습 통계를 돌려준다."""
        c = self.cfg
        rew = torch.as_tensor(rew, dtype=torch.float32).clone()
        if truncated.any():
            # 시간 제한으로 끊긴 경우는 "끝"이 아니므로 마지막 상태의 가치를 더해 준다
            idx = np.nonzero(truncated)[0]
            v = self.critic(torch.as_tensor(final_obs[idx])).squeeze(-1)
            rew[idx] += c["gamma"] * v
        self.b_rew[self.t] = rew
        self.b_done[self.t] = torch.as_tensor(terminated | truncated, dtype=torch.float32)
        self.t += 1
        if self.t < c["n_steps"]:
            return None

        # ---- GAE로 advantage 계산 ----
        last_val = self.critic(torch.as_tensor(next_obs, dtype=torch.float32)).squeeze(-1)
        adv = torch.zeros_like(self.b_rew)
        gae = torch.zeros(self.n_envs)
        for t in reversed(range(c["n_steps"])):
            next_val = last_val if t == c["n_steps"] - 1 else self.b_val[t + 1]
            not_done = 1.0 - self.b_done[t]
            delta = self.b_rew[t] + c["gamma"] * next_val * not_done - self.b_val[t]
            gae = delta + c["gamma"] * c["gae_lambda"] * not_done * gae
            adv[t] = gae
        ret = adv + self.b_val
        self.t = 0
        with torch.enable_grad():
            return self._update(adv, ret)

    # ------------------------------------------------------------------
    def _update(self, adv, ret):
        c = self.cfg
        if c["anneal_lr"]:
            frac = 1.0 - self.updates / self.total_updates
            for g in self.opt.param_groups:
                g["lr"] = c["lr"] * max(frac, 0.0)
        self.updates += 1

        obs = self.b_obs.reshape(-1, self.obs_dim)
        act, logp_old = self.b_act.reshape(-1), self.b_logp.reshape(-1)
        adv, ret = adv.reshape(-1), ret.reshape(-1)
        n = len(obs)
        mb_size = n // c["minibatches"]
        stats = {}
        for _ in range(c["epochs"]):
            perm = torch.as_tensor(self.rng.permutation(n))
            for start in range(0, n, mb_size):
                mb = perm[start:start + mb_size]
                dist = torch.distributions.Categorical(logits=self.actor(obs[mb]))
                logp = dist.log_prob(act[mb])
                ratio = (logp - logp_old[mb]).exp()
                a = adv[mb]
                a = (a - a.mean()) / (a.std() + 1e-8)
                # clipped surrogate objective
                pg_loss = -torch.min(ratio * a,
                                     ratio.clamp(1 - c["clip"], 1 + c["clip"]) * a).mean()
                v_loss = 0.5 * (self.critic(obs[mb]).squeeze(-1) - ret[mb]).pow(2).mean()
                entropy = dist.entropy().mean()
                loss = pg_loss + c["vf_coef"] * v_loss - c["ent_coef"] * entropy
                self.opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.params, c["max_grad_norm"])
                self.opt.step()
        with torch.no_grad():
            stats = {
                "pg_loss": pg_loss.item(), "v_loss": v_loss.item(),
                "entropy": entropy.item(),
                "approx_kl": (logp_old[mb] - logp).mean().item(),
            }
        return stats

    # ------------------------------------------------------------------
    def policy_net(self):
        return self.actor

    def snapshot(self, action_table, name="snapshot", greedy=False):
        net = copy.deepcopy(self.actor).eval()
        return FrozenPolicy(net, self.kind, action_table, name, greedy,
                            seed=int(self.rng.integers(1 << 30)))
