"""학습이 도는 동안 승률 곡선을 실시간으로 보여준다. 10초마다 새로 그린다.

예)
  python -m analysis.monitor runs/e1
  python -m analysis.monitor runs/e1 runs/e2 --metric wr_easy
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

COLORS = {"ppo": "#b01c2e", "dqn": "#1f6fb4", "sac": "#2a9d55"}


def read(path, metric):
    try:
        with open(path, encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get(metric)]
        return [int(r["step"]) for r in rows], [float(r[metric]) for r in rows]
    except (OSError, ValueError, KeyError):
        return [], []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--metric", default="wr_hard",
                    help="wr_hard | wr_easy | wr_random | spikes | dives | rally_sec")
    ap.add_argument("--interval", type=float, default=10.0)
    args = ap.parse_args()

    fig, ax = plt.subplots(figsize=(10, 6))
    while plt.fignum_exists(fig.number):
        ax.clear()
        n_running = n_done = 0
        for d in args.dirs:
            for mfile in sorted(Path(d).glob("**/metrics.csv")):
                steps, values = read(mfile, args.metric)
                if not steps:
                    continue
                run = mfile.parent
                done = (run / "model.pt").exists()
                n_done += done
                n_running += not done
                algo = run.name.split("_")[0]
                ax.plot(steps, values, color=COLORS.get(algo, "#555555"), lw=1.3,
                        alpha=0.9 if done else 0.55, ls="-" if done else "--")
                ax.annotate(run.name, (steps[-1], values[-1]), fontsize=7,
                            xytext=(3, 0), textcoords="offset points")
        if args.metric.startswith("wr_"):
            ax.set_ylim(0, 1.02)
            ax.axhline(0.5, color="gray", lw=0.8, ls=":")
        ax.set_xlabel("Environment steps")
        ax.set_ylabel(args.metric)
        ax.set_title(f"{args.metric}   running: {n_running} (dashed)   finished: {n_done} (solid)")
        ax.grid(alpha=0.3)
        plt.pause(args.interval)


if __name__ == "__main__":
    main()
