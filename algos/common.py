"""세 알고리즘이 함께 쓰는 부품: 신경망, 리플레이 버퍼, 저장된 정책 불러오기."""
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


def mlp(in_dim, out_dim, hidden=256, layers=2, act=nn.ReLU):
    mods, d = [], in_dim
    for _ in range(layers):
        mods += [nn.Linear(d, hidden), act()]
        d = hidden
    mods.append(nn.Linear(d, out_dim))
    return nn.Sequential(*mods)


class ReplayBuffer:
    """off-policy 알고리즘(DQN, SAC)용 원형 버퍼."""

    def __init__(self, capacity, obs_dim):
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.next_obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.act = np.zeros(capacity, dtype=np.int64)
        self.rew = np.zeros(capacity, dtype=np.float32)
        self.done = np.zeros(capacity, dtype=np.float32)
        self.pos = 0
        self.size = 0

    def add_batch(self, obs, act, rew, next_obs, done):
        n = len(obs)
        idx = (self.pos + np.arange(n)) % self.capacity
        self.obs[idx], self.act[idx], self.rew[idx] = obs, act, rew
        self.next_obs[idx], self.done[idx] = next_obs, done
        self.pos = (self.pos + n) % self.capacity
        self.size = min(self.size + n, self.capacity)

    def sample(self, batch_size, rng):
        idx = rng.integers(0, self.size, size=batch_size)
        t = torch.as_tensor
        return (t(self.obs[idx]), t(self.act[idx]), t(self.rew[idx]),
                t(self.next_obs[idx]), t(self.done[idx]))


class FrozenPolicy:
    """학습이 멈춘 정책. self-play 상대, 평가, 리그전에서 "선수"로 쓴다.

    net의 출력은 행동별 점수다 (PPO·SAC는 logits, DQN은 Q값).
    act()는 게임 행동 번호를 돌려준다 (action_table로 변환).
    """

    def __init__(self, net, kind, action_table, name="policy", greedy=False, seed=0):
        self.net = net
        self.kind = kind              # "ppo" | "dqn" | "sac"
        self.table = np.asarray(action_table)
        self.name = name
        self.greedy = greedy
        self.rng = np.random.default_rng(seed)

    @torch.no_grad()
    def act(self, obs, *, action_mask=None):
        out = self.net(torch.as_tensor(obs, dtype=torch.float32))
        if action_mask is not None:
            unavailable = action_mask[:, self.table]
            if unavailable.all(axis=1).any():
                raise ValueError("Every observation needs an available action in the policy's action table")
            out = out.masked_fill(torch.as_tensor(unavailable), -torch.inf)
        if self.greedy:
            a = out.argmax(-1).numpy()
        elif self.kind == "dqn":
            # 상대로 쓸 때는 완전히 결정적이지 않게 약간의 무작위 행동을 섞는다
            a = out.argmax(-1).numpy()
            explore = self.rng.random(len(a)) < 0.05
            if action_mask is None:
                a[explore] = self.rng.integers(0, out.shape[-1], size=int(explore.sum()))
            else:
                for slot in np.flatnonzero(explore):
                    a[slot] = self.rng.choice(np.flatnonzero(~unavailable[slot]))
        else:
            a = torch.distributions.Categorical(logits=out).sample().numpy()
        return self.table[a]


    @torch.no_grad()
    def action_probs(self, obs):
        """게임 행동 18개에 대한 선호도 (합이 1). 화면에 정책을 보여줄 때 쓴다.

        PPO·SAC는 행동 확률 그대로다. DQN은 확률이 없으므로 Q값에 softmax를 씌워
        "어떤 행동의 Q가 상대적으로 높은지"를 보여준다.
        """
        out = self.net(torch.as_tensor(obs, dtype=torch.float32))
        if self.kind == "dqn":
            out = (out - out.max(-1, keepdim=True).values) / (out.std(-1, keepdim=True) + 1e-6) * 2.0
        p = torch.softmax(out, dim=-1).numpy()
        full = np.zeros((len(p), 18), dtype=np.float32)
        full[:, self.table] = p
        return full


def save_policy(path, agent, action_set, config, steps=None):
    """정책을 저장한다. 임시 파일에 쓴 뒤 이름을 바꾸므로, 다른 프로그램이 읽는 중에도 안전하다."""
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    torch.save({
        "steps": steps,
        "kind": agent.kind,
        "state_dict": agent.policy_net().state_dict(),
        "obs_dim": agent.obs_dim,
        "action_set": list(action_set),
        "hidden": agent.hidden,
        "config": config,
    }, tmp)
    os.replace(tmp, path)


def load_policy(path, greedy=True, name=None, seed=0):
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    act_fn = nn.Tanh if ckpt["kind"] == "ppo" else nn.ReLU
    net = mlp(ckpt["obs_dim"], len(ckpt["action_set"]), ckpt["hidden"], act=act_fn)
    net.load_state_dict(ckpt["state_dict"])
    net.eval()
    policy = FrozenPolicy(net, ckpt["kind"], ckpt["action_set"], name or str(path), greedy, seed)
    policy.steps = ckpt.get("steps")     # 몇 스텝 학습한 모델인지
    return policy
