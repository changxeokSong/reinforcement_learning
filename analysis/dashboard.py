"""학습 상황을 웹 페이지 한 장으로 보여준다. 알고리즘별 승률 곡선과 실행별 현재 값.

예)
  python -m analysis.dashboard runs/e1                  # runs/e1/dashboard.html 생성
  python -m analysis.dashboard runs/e1 --watch          # 15초마다 다시 만들고, 브라우저도 자동 새로고침
  python -m analysis.dashboard runs/live runs/e1 --out dash.html

생성된 html 파일을 브라우저로 열면 된다. 굵은 선은 알고리즘별 평균(seed 평균), 가는 선은 seed 하나하나다.
학습이 끝나지 않은 실행도 지금까지의 기록으로 그린다.
"""
import argparse
import csv
import json
import time
from pathlib import Path

METRICS = ["wr_hard", "wr_easy", "wr_random", "spikes", "dives", "rally_sec"]


def collect(dirs):
    runs = []
    for d in dirs:
        for mfile in sorted(Path(d).glob("**/metrics.csv")):
            run = mfile.parent
            try:
                cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
                with open(mfile, encoding="utf-8") as f:
                    rows = [r for r in csv.DictReader(f) if r.get("wr_hard")]
            except (OSError, ValueError):
                continue
            if not rows:
                continue
            group = run.name.rsplit("_seed", 1)[0]
            runs.append({
                "name": f"{Path(d).name}/{run.name}", "group": f"{Path(d).name}/{group}",
                "algo": cfg["algo"], "seed": cfg["seed"],
                "total": cfg["common"]["total_steps"], "done": (run / "model.pt").exists(),
                "step": [int(r["step"]) for r in rows],
                "min": [round(float(r["wall_sec"]) / 60, 2) for r in rows],
                **{m: [float(r[m]) for r in rows] for m in METRICS},
            })
    return runs


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">__REFRESH__
<title>알바트로스 배구 학습 현황</title>
<style>
.viz { font-family: var(--font-sans, "Malgun Gothic", system-ui, sans-serif); color: var(--foreground, #0b0b0b);
  --ink2: var(--muted-foreground, #52514e); --grid: var(--border, #dddcd6);
  --s-ppo: #2a78d6; --s-dqn: #eb6834; --s-sac: #1baf7a; --s-other: #6250d6; }
@media (prefers-color-scheme: dark) { .viz { --s-ppo: #3987e5; --s-dqn: #d95926; --s-sac: #199e70; --s-other: #9085e9; } }
.viz h2 { font-size: 15px; margin: 0 0 2px; font-weight: 600; }
.viz .sub { font-size: 12px; color: var(--ink2); margin-bottom: 10px; }
.viz .row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; font-size: 12px; }
.viz button { font: inherit; padding: 3px 9px; border: 1px solid var(--grid); border-radius: 6px;
  background: transparent; color: inherit; cursor: pointer; }
.viz button[aria-pressed="true"] { background: var(--secondary, #ecebe6); font-weight: 600; }
.viz .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; margin: 4px 0 6px; }
.viz .key { display: inline-block; width: 16px; height: 0; border-top: 3px solid; vertical-align: middle; margin-right: 5px; }
.viz svg { display: block; width: 100%; height: 320px; overflow: visible; }
.viz svg text { fill: var(--ink2); font-size: 11px; }
.viz .tip { position: absolute; pointer-events: none; font-size: 12px; padding: 7px 9px; border-radius: 6px;
  background: var(--popover, #fff); color: var(--popover-foreground, inherit); border: 1px solid var(--grid);
  box-shadow: 0 2px 8px rgba(0,0,0,.15); white-space: nowrap; display: none; }
.viz .wrap { position: relative; }
.viz table { border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 14px; }
.viz th, .viz td { text-align: right; padding: 4px 8px; border-bottom: 1px solid var(--grid); }
.viz th:first-child, .viz td:first-child { text-align: left; }
.viz th { color: var(--ink2); font-weight: 500; }
.viz .bar { height: 4px; border-radius: 2px; background: var(--grid); min-width: 60px; }
.viz .bar i { display: block; height: 4px; border-radius: 2px; }
</style></head><body>
<div class="viz" id="viz">
  <h2 id="title"></h2>
  <div class="sub" id="sub"></div>
  <div class="row" id="metricRow"></div>
  <div class="row" id="xRow"></div>
  <div class="legend" id="legend"></div>
  <div class="wrap"><svg id="chart" role="img"></svg><div class="tip" id="tip"></div></div>
  <table id="table"></table>
</div>
<script>
const RUNS = __DATA__;
const STAMP = "__STAMP__";
const LABEL = {wr_hard: "어려움 봇 상대 승률", wr_easy: "쉬움 봇 상대 승률", wr_random: "무작위 봇 상대 승률",
               spikes: "점당 스파이크 횟수", dives: "점당 다이빙 횟수", rally_sec: "랠리 길이(초)"};
const COLOR = a => `var(--s-${["ppo","dqn","sac"].includes(a) ? a : "other"})`;
let metric = "wr_hard", xKey = "step";
const $ = id => document.getElementById(id);
const el = (tag, attrs = {}, text) => {
  const svg = ["svg","g","path","line","text","circle","rect"].includes(tag);
  const e = svg ? document.createElementNS("http://www.w3.org/2000/svg", tag) : document.createElement(tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text !== undefined) e.textContent = text;
  return e;
};
const fmt = v => metric.startsWith("wr_") ? (v * 100).toFixed(0) + "%" : v.toFixed(2);
const fmtX = v => xKey === "step" ? (v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : Math.round(v / 1e3) + "k") : v.toFixed(0) + "분";

function groups() {
  // 같은 설정의 seed들을 묶어 평균 곡선을 만든다 (모든 seed가 도달한 구간까지만)
  const by = {};
  for (const r of RUNS) (by[r.group] ||= []).push(r);
  return Object.entries(by).map(([name, rs]) => {
    const n = Math.min(...rs.map(r => r.step.length));
    const x = [], y = [];
    for (let i = 0; i < n; i++) {
      x.push(rs.reduce((s, r) => s + r[xKey][i], 0) / rs.length);
      y.push(rs.reduce((s, r) => s + r[metric][i], 0) / rs.length);
    }
    return {name, algo: rs[0].algo, runs: rs, x, y};
  });
}

function buttons(row, items, current, set) {
  row.replaceChildren(...items.map(([key, label]) => {
    const b = el("button", {"aria-pressed": key === current}, label);
    b.onclick = () => { set(key); draw(); };
    return b;
  }));
}

function draw() {
  const G = groups();
  $("title").textContent = LABEL[metric] + " (학습 스텝에 따른 변화)";
  const running = RUNS.filter(r => !r.done).length;
  $("sub").textContent = `실행 ${RUNS.length}개 · 학습 중 ${running}개 · 완료 ${RUNS.length - running}개 · 갱신 ${STAMP}`;
  buttons($("metricRow"), Object.entries(LABEL), metric, k => metric = k);
  buttons($("xRow"), [["step", "가로축: 학습 스텝"], ["min", "가로축: 실제 시간(분)"]], xKey, k => xKey = k);
  $("legend").replaceChildren(...G.map(g => {
    const s = el("span");
    const key = el("span", {class: "key", style: `border-color:${COLOR(g.algo)}`});
    s.append(key, document.createTextNode(`${g.name} (seed ${g.runs.length}개 평균)`));
    return s;
  }));

  const svg = $("chart");
  const W = svg.clientWidth, H = 320, m = {l: 44, r: 96, t: 10, b: 28};
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.replaceChildren();
  const xMax = Math.max(1, ...RUNS.map(r => r[xKey][r[xKey].length - 1]));
  const isRate = metric.startsWith("wr_");
  const yMax = isRate ? 1 : Math.max(0.1, ...RUNS.flatMap(r => r[metric])) * 1.1;
  const X = v => m.l + v / xMax * (W - m.l - m.r), Y = v => H - m.b - v / yMax * (H - m.t - m.b);
  for (let i = 0; i <= 4; i++) {
    const v = yMax * i / 4;
    svg.append(el("line", {x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: "var(--grid)", "stroke-width": 1}));
    svg.append(el("text", {x: m.l - 6, y: Y(v) + 4, "text-anchor": "end"}, fmt(v)));
  }
  for (let i = 0; i <= 4; i++) {
    const v = xMax * i / 4;
    svg.append(el("text", {x: X(v), y: H - 8, "text-anchor": "middle"}, fmtX(v)));
  }
  const path = (xs, ys) => xs.map((x, i) => (i ? "L" : "M") + X(x).toFixed(1) + " " + Y(ys[i]).toFixed(1)).join("");
  for (const g of G) for (const r of g.runs)
    svg.append(el("path", {d: path(r[xKey], r[metric]), fill: "none", stroke: COLOR(g.algo), "stroke-width": 1, opacity: 0.3}));
  const ends = [];
  for (const g of G) {
    svg.append(el("path", {d: path(g.x, g.y), fill: "none", stroke: COLOR(g.algo), "stroke-width": 2,
                           "stroke-linejoin": "round", "stroke-linecap": "round"}));
    const i = g.x.length - 1;
    svg.append(el("circle", {cx: X(g.x[i]), cy: Y(g.y[i]), r: 4, fill: COLOR(g.algo), stroke: "var(--background, #fff)", "stroke-width": 2}));
    ends.push({g, x: X(g.x[i]), y: Y(g.y[i]), v: g.y[i]});
  }
  // 끝점 이름표: 겹치지 않게 위아래로 밀어낸다
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
  if (ends.length <= 4) for (const e of ends)
    svg.append(el("text", {x: e.x + 9, y: e.y + 4}, `${e.g.name.split("/").pop()} ${fmt(e.v)}`));

  // 십자선과 툴팁: 가장 가까운 평가 시점의 모든 계열 값을 보여준다
  const hair = el("line", {y1: m.t, y2: H - m.b, stroke: "var(--ink2)", "stroke-width": 1, visibility: "hidden"});
  svg.append(hair);
  const tip = $("tip");
  svg.onpointermove = ev => {
    const box = svg.getBoundingClientRect();
    const xv = (ev.clientX - box.left - m.l) / (W - m.l - m.r) * xMax;
    if (xv < 0 || xv > xMax || !G.length) return svg.onpointerleave();
    const rows = G.map(g => {
      let best = 0;
      g.x.forEach((x, i) => { if (Math.abs(x - xv) < Math.abs(g.x[best] - xv)) best = i; });
      return {g, x: g.x[best], y: g.y[best]};
    });
    const xs = rows[0].x;
    hair.setAttribute("x1", X(xs)); hair.setAttribute("x2", X(xs)); hair.setAttribute("visibility", "visible");
    tip.replaceChildren(el("div", {style: "color:var(--ink2);margin-bottom:3px"}, fmtX(xs)), ...rows.map(r => {
      const d = el("div");
      d.append(el("span", {class: "key", style: `border-color:${COLOR(r.g.algo)}`}), el("b", {}, fmt(r.y)),
               document.createTextNode("  " + r.g.name));
      return d;
    }));
    tip.style.display = "block";
    const left = Math.min(ev.clientX - box.left + 14, W - tip.offsetWidth - 4);
    tip.style.left = left + "px"; tip.style.top = (ev.clientY - box.top + 12) + "px";
  };
  svg.onpointerleave = () => { hair.setAttribute("visibility", "hidden"); tip.style.display = "none"; };

  // 표: 실행별 현재 값
  const t = $("table");
  const head = el("tr");
  ["실행", "진행", "스텝", "시간(분)", "vs 무작위", "vs 쉬움", "vs 어려움", "스파이크", "다이빙"].forEach(h => head.append(el("th", {}, h)));
  t.replaceChildren(head, ...RUNS.map(r => {
    const i = r.step.length - 1, tr = el("tr"), pct = Math.min(100, r.step[i] / r.total * 100);
    const name = el("td");
    name.append(el("span", {class: "key", style: `border-color:${COLOR(r.algo)}`}), document.createTextNode(r.name));
    const prog = el("td"), bar = el("div", {class: "bar"});
    bar.append(el("i", {style: `width:${pct}%;background:${COLOR(r.algo)}`}));
    prog.append(bar);
    tr.append(name, prog);
    const pc = v => (v * 100).toFixed(0) + "%";
    [r.done ? "완료" : (r.step[i] / 1e6).toFixed(1) + "M", r.min[i].toFixed(0), pc(r.wr_random[i]), pc(r.wr_easy[i]),
     pc(r.wr_hard[i]), r.spikes[i].toFixed(2), r.dives[i].toFixed(2)].forEach(v => tr.append(el("td", {}, v)));
    return tr;
  }));
}
draw();
addEventListener("resize", draw);
</script></body></html>
"""


def build(dirs, out, refresh=0):
    runs = collect(dirs)
    page = (PAGE.replace("__DATA__", json.dumps(runs, ensure_ascii=False))
            .replace("__STAMP__", time.strftime("%H:%M:%S"))
            .replace("__REFRESH__", f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""))
    Path(out).write_text(page, encoding="utf-8")
    return len(runs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--watch", action="store_true", help="15초마다 다시 만든다 (Ctrl+C로 종료)")
    args = ap.parse_args()
    out = args.out or str(Path(args.dirs[0]) / "dashboard.html")
    if not args.watch:
        print(f"실행 {build(args.dirs, out)}개 → {out}")
        return
    print(f"{out} 을 브라우저로 여세요. 15초마다 갱신합니다. (Ctrl+C로 종료)")
    while True:
        build(args.dirs, out, refresh=15)
        time.sleep(15)


if __name__ == "__main__":
    main()
