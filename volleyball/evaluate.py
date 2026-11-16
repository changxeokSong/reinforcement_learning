"""두 선수를 붙여서 승률과 플레이 통계를 잰다. 학습 중 평가와 리그전에서 함께 쓴다."""
import numpy as np

from .vec_env import VecVolley


def play_points(player, opponent, n_points=200, seed=12345, n_envs=20):
    """player(왼쪽)와 opponent(오른쪽)가 n_points 점을 겨룬다.

    환경마다 같은 수의 점을 치르게 해서, 짧은 랠리만 먼저 집계되는 편향을 막는다.
    같은 seed면 서브가 같으므로 서로 다른 선수를 같은 조건에서 비교할 수 있다.

    승률 = (승 + 0.5 × 무승부) / 전체. 무승부는 랠리 시간 제한에 걸린 경우다.
    """
    quota = int(np.ceil(n_points / n_envs))
    vec = VecVolley(n_envs, seed=seed)
    obs, obs_opp = vec.reset()
    count = np.zeros(n_envs, dtype=int)
    wins = losses = draws = 0
    frames = 0
    spikes, dives, touches = [0, 0], [0, 0], [0, 0]
    while count.min() < quota:
        out = vec.step(player.act(obs), opponent.act(obs_opp))
        obs, obs_opp = out["obs"], out["obs_opp"]
        for i, winner, s in out["stats"]:
            if count[i] >= quota:
                continue
            count[i] += 1
            wins += winner == 1
            losses += winner == -1
            draws += winner == 0
            frames += s["frames"]
            for k in (0, 1):
                spikes[k] += s["spikes"][k]
                dives[k] += s["dives"][k]
                touches[k] += s["touches"][k]
    n = wins + losses + draws
    return {
        "points": n, "wins": int(wins), "losses": int(losses), "draws": int(draws),
        "win_rate": (wins + 0.5 * draws) / n,
        "rally_sec": frames / 60.0 / n,
        "spikes": spikes[0] / n, "dives": dives[0] / n, "touches": touches[0] / n,
        "opp_spikes": spikes[1] / n, "opp_dives": dives[1] / n, "opp_touches": touches[1] / n,
    }
