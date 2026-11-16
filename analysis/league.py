"""리그전: 학습된 모든 에이전트와 봇이 서로 한 번씩 붙는다.

예)
  python -m analysis.league runs/e1 --points 200
  python -m analysis.league runs/e1 runs/e2 --out results/league_e1_e2

출력 (기본: 첫 번째 폴더 아래 league/)
  league.json   선수 목록, 승률 행렬, Elo, 플레이 통계
  winrate.csv   승률 행렬 (행이 열을 이긴 비율)
"""
import argparse
import csv
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

BOTS = ("random", "easy", "hard")


def _load(spec, seed):
    from algos import load_policy
    from volleyball.bots import make_bot
    if spec in BOTS:
        return make_bot(spec, seed)
    return load_policy(spec, greedy=True, seed=seed)


def _play_pair(job):
    import torch
    from volleyball.evaluate import play_points
    torch.set_num_threads(1)
    i, j, spec_i, spec_j, points, seed = job
    result = play_points(_load(spec_i, seed), _load(spec_j, seed + 1), points, seed=seed)
    return i, j, result


def find_runs(dirs):
    """model.pt가 있는 실행 폴더를 찾는다. 이름은 '<실험>/<실행>' 형태."""
    runs = []
    for d in dirs:
        for model in sorted(Path(d).glob("**/model.pt")):
            cfg = json.loads((model.parent / "config.json").read_text(encoding="utf-8"))
            name = model.parent.name
            group = name.rsplit("_seed", 1)[0]
            runs.append({
                "name": f"{Path(d).name}/{name}", "group": f"{Path(d).name}/{group}",
                "algo": cfg["algo"], "seed": cfg["seed"], "path": str(model),
            })
    return runs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--points", type=int, default=200, help="한 쌍이 겨루는 점수")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from analysis.stats import elo_from_wins

    runs = find_runs(args.dirs)
    if not runs:
        raise SystemExit("model.pt를 찾지 못했어요.")
    players = [{"name": b, "group": b, "algo": "bot", "seed": None, "path": b} for b in BOTS] + runs
    n = len(players)
    jobs = [(i, j, players[i]["path"], players[j]["path"], args.points, 1000 + i * n + j)
            for i in range(n) for j in range(i + 1, n)]
    print(f"선수 {n}명, 대진 {len(jobs)}개, 대진당 {args.points}점")

    wins = np.zeros((n, n))
    style = [dict(spikes=0.0, dives=0.0, touches=0.0, rally_sec=0.0, games=0) for _ in range(n)]
    start = time.time()
    with ProcessPoolExecutor(args.workers) as pool:
        for done, (i, j, r) in enumerate(pool.map(_play_pair, jobs, chunksize=4), 1):
            wins[i, j] = r["wins"] + 0.5 * r["draws"]
            wins[j, i] = r["losses"] + 0.5 * r["draws"]
            for idx, prefix in ((i, ""), (j, "opp_")):
                for key in ("spikes", "dives", "touches"):
                    style[idx][key] += r[prefix + key]
                style[idx]["rally_sec"] += r["rally_sec"]
                style[idx]["games"] += 1
            if done % 50 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}  ({time.time() - start:.0f}초)", flush=True)

    total = wins + wins.T
    winrate = np.divide(wins, total, out=np.full((n, n), np.nan), where=total > 0)
    elo = elo_from_wins(wins, anchor=BOTS.index("hard"))
    for p, e, s in zip(players, elo, style):
        p["elo"] = round(float(e), 1)
        g = max(s.pop("games"), 1)
        p["style"] = {k: round(v / g, 3) for k, v in s.items()}
        p["mean_winrate"] = round(float(np.nanmean(winrate[players.index(p)])), 4)

    out = Path(args.out or Path(args.dirs[0]) / "league")
    out.mkdir(parents=True, exist_ok=True)
    (out / "league.json").write_text(json.dumps({
        "points_per_pair": args.points, "players": players,
        "wins": wins.tolist(), "winrate": np.where(np.isnan(winrate), None, winrate).tolist(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "winrate.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([""] + [p["name"] for p in players])
        for p, row in zip(players, winrate):
            w.writerow([p["name"]] + ["" if np.isnan(v) else f"{v:.3f}" for v in row])

    print("\nElo 순위 (어려움 봇 = 1000)")
    for p in sorted(players, key=lambda p: -p["elo"]):
        print(f"  {p['elo']:7.1f}  {p['name']}")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
