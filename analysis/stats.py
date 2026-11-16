"""통계 도구: 신뢰구간과 Elo."""
import math

import numpy as np

# 95% 양측 t 분포 임계값 (자유도 1~30). scipy 없이 쓰기 위해 표로 둔다.
T_95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def mean_ci(values, axis=0):
    """평균과 95% t 신뢰구간의 반폭. 표본 단위는 학습 seed다.

    seed가 n개면 자유도 n-1의 t 분포를 쓴다. n이 작으면 구간이 넓어지는 게 정상이다.
    """
    x = np.asarray(values, dtype=float)
    n = x.shape[axis]
    mean = x.mean(axis=axis)
    if n < 2:
        return mean, np.zeros_like(mean)
    t = T_95[n - 2] if n - 2 < len(T_95) else 1.96
    half = t * x.std(axis=axis, ddof=1) / math.sqrt(n)
    return mean, half


def elo_from_wins(wins, anchor=None, anchor_rating=1000.0, iters=2000):
    """승수 행렬로 Elo를 추정한다 (Bradley-Terry 모델, MM 알고리즘).

    wins[i][j] = i가 j를 이긴 횟수 (무승부는 양쪽에 0.5씩 넣어서 준다).
    한 번도 못 이기거나 한 번도 안 진 선수 때문에 발산하지 않도록 작은 사전값을 더한다.
    anchor: 기준으로 삼을 선수 번호. 그 선수의 점수를 anchor_rating으로 맞춘다.
    """
    w = np.asarray(wins, dtype=float) + 0.5
    np.fill_diagonal(w, 0.0)
    n = len(w)
    games = w + w.T
    strength = np.ones(n)
    for _ in range(iters):
        denom = (games / (strength[:, None] + strength[None, :])).sum(axis=1)
        new = w.sum(axis=1) / denom
        new /= np.exp(np.log(new).mean())
        if np.abs(new - strength).max() < 1e-10:
            strength = new
            break
        strength = new
    rating = 400.0 * np.log10(strength)
    rating += anchor_rating - (rating[anchor] if anchor is not None else rating.mean())
    return rating
