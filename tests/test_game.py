"""게임과 통계 코드의 기본 검증. 실행: python -m tests.test_game"""
import numpy as np

from analysis.stats import elo_from_wins, mean_ci
from volleyball import BASIC_ACTIONS, N_ACTIONS, OBS_DIM, Game, VecVolley, encode_action
from volleyball.bots import make_bot
from volleyball.evaluate import play_points
from volleyball.game import B_R, COURT_W, NET_X, P_R


def test_deterministic():
    """같은 seed와 같은 행동이면 결과가 완전히 같아야 한다 (재현성)."""
    def run():
        g, rng, trace = Game(seed=7, points_to_win=3), np.random.default_rng(0), []
        while not g.match_over:
            g.step(int(rng.integers(N_ACTIONS)), int(rng.integers(N_ACTIONS)))
            trace.append((g.bx, g.by, g.players[0].x, g.players[1].y))
        return trace, tuple(g.score)
    assert run() == run()


def test_mirror_symmetry():
    """좌우를 바꿔도 공평해야 한다.

    공의 초기 상태를 좌우로 뒤집고 두 선수의 행동을 맞바꾸면, 경기도 정확히 좌우 대칭으로
    진행되어야 한다. 한쪽 코트가 유리하면 self-play와 리그전 결과를 믿을 수 없다.
    """
    rng = np.random.default_rng(3)
    for trial in range(20):
        a, b = Game(seed=trial), Game(seed=trial)
        b.bx, b.bvx = COURT_W - a.bx, -a.bvx
        for _ in range(400):
            x, y = int(rng.integers(N_ACTIONS)), int(rng.integers(N_ACTIONS))
            wa, _ = a.step(x, y)
            wb, _ = b.step(y, x)
            assert wa == -wb
            if a.match_over:
                break
            assert abs(a.bx - (COURT_W - b.bx)) < 1e-9 and abs(a.by - b.by) < 1e-9
            assert np.allclose(a.observe(0), b.observe(1), atol=1e-9)
            assert np.allclose(a.observe(1), b.observe(0), atol=1e-9)


def test_bounds_and_scoring():
    """선수는 자기 코트를 벗어나지 않고, 공은 코트 안에 있으며, 관측값 범위가 정상이어야 한다."""
    rng = np.random.default_rng(1)
    g = Game(seed=1, points_to_win=10 ** 9)
    points = 0
    for _ in range(20000):
        winner, _ = g.step(int(rng.integers(N_ACTIONS)), int(rng.integers(N_ACTIONS)))
        points += winner != 0
        left, right = g.players
        assert P_R - 1e-9 <= left.x < NET_X < right.x <= COURT_W - P_R + 1e-9
        assert left.y >= P_R - 1e-9 and right.y >= P_R - 1e-9
        assert B_R - 1e-6 <= g.bx <= COURT_W - B_R + 1e-6
        obs = np.array(g.observe(0))
        assert obs.shape == (OBS_DIM,) and np.all(np.abs(obs) <= 1.5)
    assert points > 50 and sum(g.score) == points


def test_dive_and_spike_rules():
    g = Game(seed=0)
    # 땅에서 이동 + 타격 = 다이빙, 그 뒤 경직
    g.step(encode_action(1, 0, 1), encode_action(0, 0, 0))
    assert g.players[0].dive > 0 and g.dives[0] == 1
    x_before = g.players[0].x
    for _ in range(13):
        g.step(encode_action(-1, 1, 0), encode_action(0, 0, 0))   # 다이빙·경직 중엔 조작 불가
    assert g.players[0].grounded and g.players[0].x > x_before
    g.step(encode_action(0, 1, 0), encode_action(0, 0, 0))        # 경직이 끝나면 다시 점프 가능
    g.step(encode_action(0, 1, 0), encode_action(0, 0, 0))
    assert not g.players[0].grounded
    # 공중에서 타격 = 스윙, 한 번 점프에 한 번만
    g = Game(seed=0)
    g.step(encode_action(0, 1, 0), encode_action(0, 0, 0))
    g.step(encode_action(0, 2, 1), encode_action(0, 0, 0))
    p = g.players[0]
    assert not p.grounded and p.swing_used and p.swing_aim == 2
    # 기본 행동 공간에는 타격이 없다
    assert all(a % 2 == 0 for a in BASIC_ACTIONS) and len(BASIC_ACTIONS) == 6


def test_vec_env_and_bots():
    vec = VecVolley(8, seed=0)
    obs, obs_opp = vec.reset()
    assert obs.shape == obs_opp.shape == (8, OBS_DIM)
    bot = make_bot("hard")
    for _ in range(300):
        out = vec.step(bot.act(obs), bot.act(obs_opp))
        obs, obs_opp = out["obs"], out["obs_opp"]
        done = out["terminated"] | out["truncated"]
        assert np.all((out["reward"] != 0) == out["terminated"])
        assert len(out["stats"]) == done.sum()
    # 봇 실력 순서: 어려움 > 쉬움 > 무작위
    assert play_points(make_bot("hard", 1), make_bot("random", 2), 200)["win_rate"] > 0.9
    assert play_points(make_bot("easy", 1), make_bot("random", 2), 200)["win_rate"] > 0.8
    assert play_points(make_bot("hard", 1), make_bot("easy", 2), 200)["win_rate"] > 0.6


def test_stats():
    mean, half = mean_ci([1.0, 2.0, 3.0, 4.0, 5.0])
    assert abs(mean - 3.0) < 1e-12 and abs(half - 2.776 * np.std([1, 2, 3, 4, 5], ddof=1) / 5 ** 0.5) < 1e-9
    # 강한 순서대로 Elo가 나와야 하고, 기준 선수는 1000이어야 한다
    elo = elo_from_wins([[0, 70, 90], [30, 0, 70], [10, 30, 0]], anchor=1)
    assert elo[0] > elo[1] > elo[2] and abs(elo[1] - 1000) < 1e-6
    # 승률 70%면 Elo 차이는 약 147점
    assert 120 < elo[0] - elo[1] < 190


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"통과  {t.__name__}")
    print(f"\n{len(tests)}개 테스트 모두 통과")
