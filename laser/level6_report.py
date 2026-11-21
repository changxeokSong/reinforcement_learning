"""Report the paired Unity audit and held-out level 6 PPO experiment."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.stats import mean_ci


DESIGNS = {0: "기존 설계", 1: "이중벽 간격 확대", 2: "이중벽 간격·통로 폭 확대"}
CONDITIONS = {
    "legacy": "기존 PPO",
    "geometry": "간격·폭 수정 PPO",
    "geometry_and_observation": "간격·폭 및 통로 관측 PPO",
    "random_design_0": "기존 설계 무작위 정책",
    "random_design_2": "수정 설계 무작위 정책",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("runs/results/laser"))
    args = parser.parse_args()
    root = args.root
    with (root / "level6_audit.csv").open(encoding="utf-8", newline="") as stream:
        audit = list(csv.DictReader(stream))
    data = json.loads((root / "level6_redesign.json").read_text(encoding="utf-8"))
    procedural = [[r for r in audit if int(r["design"]) == design and r["layout"] == "procedural"]
                  for design in DESIGNS]
    campaign = [[r for r in audit if int(r["design"]) == design and r["layout"] == "campaign"]
                for design in DESIGNS]
    if {len(rows) for rows in procedural} != {60} or {len(rows) for rows in campaign} != {4}:
        raise ValueError("The paired Unity audit did not finish")
    lines = [
        "# 6단계 Unity 설계 점검", "",
        "움직이는 이중벽 사이는 에이전트 중심이 머물 수 있는 깊이로 계산했다. "
        "두 벽 간 거리에서 충돌 반경 0.36m의 두 배를 뺀 값이다. "
        "통로 유효 폭은 실제 개구부에서 같은 반경의 두 배를 뺀 값이다.", "",
        "각 설계에서 같은 시드의 생성 배치 60개와 캠페인 배치 4개를 Unity에서 탐색했다. "
        "경로가 발견된 경우 출발점 좌우 0.1m 변화 2종, 경로 중간에 0.1초 정지 3종을 따로 검사했다. "
        "탐색에서 경로를 못 찾은 경우는 주어진 탐색 예산 내 미발견으로 집계했다.", "",
        "| 설계 | 새 배치 경로 발견 | 캠페인 경로 발견 | 캠페인 최소 대기 깊이 | 좁은 통로 유효 폭 | 좌우 이동 후 통과 | 정지 후 통과 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    robust = []
    for name, rows, fixed in zip(DESIGNS.values(), procedural, campaign):
        found = sum(int(r["found"]) for r in rows)
        fixed_found = sum(int(r["found"]) for r in fixed)
        depth = min(float(r["wait_margin_m"]) for r in fixed)
        width = float(rows[0]["narrow_clearance_m"])
        spawn = sum(int(r["spawn_survived"]) for r in rows)
        pause = sum(int(r["pause_survived"]) for r in rows)
        lines.append(f"| {name} | {found}/60 | {fixed_found}/4 | {depth:.3f}m | {width:.2f}m | "
                     f"{spawn}/{2 * found} | {pause}/{3 * found} |")
        robust.append((spawn / (2 * found), pause / (3 * found)))
    lines += [
        "", "## 처음 보는 무작위 배치에서 PPO 평가", "",
        f"설정마다 시드 3개를 각각 {data['steps']:,} 환경 스텝으로 처음부터 학습했다. "
        f"마지막 체크포인트를 학습에 쓰지 않은 환경 시드에서 각각 {data['episodes_per_seed']}판 평가했다. "
        "학습 곡선과 별도로 이 표를 계산했다. 신뢰구간의 표본 단위는 학습 시드 3개다.", "",
        "| 설정 | 성공률 ± 95% 신뢰구간 반폭 | 시드별 성공률 | 충돌률 | 시간 초과율 |",
        "|---|---:|---|---:|---:|",
    ]
    warm_path = root / "level6_redesign_warm.json"
    columns = 3 if warm_path.is_file() else 2
    fig, axes = plt.subplots(1, columns, figsize=(5.5 * columns, 4.5), layout="constrained")
    x = np.arange(3)
    axes[0].bar(x - .18, [v[0] for v in robust], width=.36, label="Spawn shifted ±0.1 m")
    axes[0].bar(x + .18, [v[1] for v in robust], width=.36, label="One 0.1 s pause")
    axes[0].set(xticks=x, xticklabels=["Original", "Spacing", "Spacing + gate"], title="Search-path robustness")
    axes[0].legend()
    rates = {}
    for name, label in CONDITIONS.items():
        runs = [r for r in data["runs"] if r["condition"] == name]
        if {r["seed"] for r in runs} != {0, 1, 2}:
            raise ValueError(f"Expected three seeds: {name}")
        rates[name] = [r["success"] for r in sorted(runs, key=lambda r: r["seed"])]
        mean, half = mean_ci(rates[name])
        seeds = ", ".join(f"{v:.1%}" for v in rates[name])
        hit = np.mean([r["hit"] for r in runs])
        timeout = np.mean([r["timeout"] for r in runs])
        lines.append(f"| {label} | {mean:.1%} ± {100 * half:.1f}%p | {seeds} | {hit:.1%} | {timeout:.1%} |")
    for before, after in (("legacy", "geometry"), ("geometry", "geometry_and_observation")):
        delta, half = mean_ci(np.asarray(rates[after]) - rates[before])
        lines.append(f"\n- {CONDITIONS[before]} → {CONDITIONS[after]} 성공률 변화 "
                     f"{100 * delta:+.1f}%p (시드별 차이의 95% 신뢰구간 반폭 {100 * half:.1f}%p).")
    for index, name in enumerate(("legacy", "geometry", "geometry_and_observation")):
        mean, half = mean_ci(rates[name])
        err = [[min(half, mean)], [min(half, 1 - mean)]]
        axes[1].bar(index, mean, yerr=err, capsize=4)
        axes[1].scatter([index] * 3, rates[name], color="black", zorder=3)
    axes[1].set(xticks=x, xticklabels=["Original", "Geometry", "Geometry + obs."],
                title="PPO on unseen layouts (3 seeds)")
    transfer_path = root / "level6_transfer_check.json"
    if transfer_path.is_file():
        transfer = json.loads(transfer_path.read_text(encoding="utf-8"))
        lines += ["", "## 기존 PPO의 전이 확인", "",
                  "기존 6단계 PPO의 가중치를 유지하고 관측 방식도 동일하게 유지한 상태로, "
                  "환경 기하 변경에 따른 성공률을 확인했다. 행 하나는 학습 정책 하나의 평가다.", "",
                  "| 기존 학습 스텝 | 환경 시드 수 | 기존 설계 | 수정 설계 |",
                  "|---:|---:|---:|---:|"]
        for model in dict.fromkeys(r["model"] for r in transfer):
            runs = [r for r in transfer if r["model"] == model]
            left, right = ([r for r in runs if r["design"] == design] for design in (0, 2))
            lines.append(f"| {left[0]['steps']:,} | {len(left)} | {np.mean([r['success'] for r in left]):.1%} | "
                         f"{np.mean([r['success'] for r in right]):.1%} |")
    speed_path = root / "level6_speed_transfer.json"
    if speed_path.is_file():
        speed = json.loads(speed_path.read_text(encoding="utf-8"))
        lines += ["", "## 움직이는 좁은 통로의 속도 제한", "",
                  "같은 PPO 가중치와 평가 시드에서 간격·폭 수정 조건에 좁은 통로의 "
                  "최대 좌우 이동 속도 2.10m/s 제한을 추가했다. 캠페인의 배치별 속도 배율은 이 상한 적용 후 곱해진다.", "",
                  "| 기존 학습 스텝 | 간격·폭 수정 | 속도 제한 추가 |", "|---:|---:|---:|"]
        for model in dict.fromkeys(r["model"] for r in speed):
            runs = [r for r in speed if r["model"] == model]
            before, after = (np.mean([r[f"design_{design}"]["success"] for r in runs]) for design in (2, 3))
            lines.append(f"| {runs[0]['steps']:,} | {before:.1%} | {after:.1%} |")
    speed_audit = root / "level6_speed_audit.csv"
    if speed_audit.is_file():
        with speed_audit.open(encoding="utf-8", newline="") as stream:
            capped = list(csv.DictReader(stream))
        samples = [[r for r in procedural[design] if int(r["seed"]) < 24] for design in (0, 2)]
        samples.append([r for r in capped if r["layout"] == "procedural"])
        if any(len(rows) != 24 for rows in samples):
            raise ValueError("Missing paired speed audit layouts")
        lines += ["", "동일한 생성 시드 24개에서 속도 제한까지 포함해 다시 비교했다.", "",
                  "| 설계 | 경로 발견 | 좌우 이동 후 통과 | 정지 후 통과 |", "|---|---:|---:|---:|"]
        for label, rows in zip(("기존", "간격·폭 확대", "간격·폭 확대 + 속도 제한"), samples):
            found = sum(int(r["found"]) for r in rows)
            spawn = sum(int(r["spawn_survived"]) for r in rows)
            pause = sum(int(r["pause_survived"]) for r in rows)
            lines.append(f"| {label} | {found}/24 | {spawn}/{2 * found} | {pause}/{3 * found} |")
        fixed_found = sum(int(r["found"]) for r in capped if r["layout"] == "campaign")
        lines += ["", f"속도 제한을 넣은 캠페인 배치는 4개 중 {fixed_found}개에서 경로를 찾았다."]
    dagger_path = root / "level6_dagger_transfer.json"
    if dagger_path.is_file():
        students = json.loads(dagger_path.read_text(encoding="utf-8"))
        lines += ["", "## 기존 DAgger 학생의 전체 캠페인 검증", "",
                  "학생 가중치는 고정하고 6단계 설계만 바꿨다. 단계마다 새 무작위 배치를 생성하고 "
                  "최대 3회 시도하는 조건으로 3개 모델을 각각 200회 평가했다.", "",
                  "| 설계 | 6단계 별도 평가 성공률 | 무작위 10단계 캠페인 완주 |",
                  "|---|---:|---:|"]
        for design, label in ((0, "기존"), (2, "간격·폭 확대"), (3, "간격·폭 확대 + 속도 제한")):
            runs = sorted((r for r in students if r["design"] == design), key=lambda r: r["seed"])
            if {r["seed"] for r in runs} != {0, 1, 2}:
                raise ValueError(f"Expected three DAgger seeds: {design}")
            mean, half = mean_ci([r["level6"]["success"] for r in runs])
            wins = sum(r["campaign"]["completed"] for r in runs)
            total = sum(r["campaign"]["campaigns"] for r in runs)
            lines.append(f"| {label} | {mean:.1%} ± {100 * half:.1f}%p | {wins}/{total} ({wins / total:.1%}) |")
    if columns == 3:
        warm = json.loads(warm_path.read_text(encoding="utf-8"))
        lines += ["", "## 동일한 PPO actor에서 추가 학습", "",
                  f"기존 6단계 PPO actor 하나에서 세 설정을 각각 {warm['steps']:,} 스텝 추가 학습했다. "
                  "critic과 옵티마이저는 새로 초기화했다. 동일한 초기 actor를 사용한 후속 실험이다.", "",
                  "| 설정 | 성공률 ± 95% 신뢰구간 반폭 | 시드별 성공률 |",
                  "|---|---:|---|"]
        for index, name in enumerate(("legacy", "geometry", "geometry_and_observation")):
            runs = sorted((r for r in warm["runs"] if r["condition"] == name), key=lambda r: r["seed"])
            if {r["seed"] for r in runs} != {0, 1, 2}:
                raise ValueError(f"Expected three fine-tuning seeds: {name}")
            values = [r["success"] for r in runs]
            mean, half = mean_ci(values)
            seeds = ", ".join(f"{v:.1%}" for v in values)
            lines.append(f"| {CONDITIONS[name]} | {mean:.1%} ± {100 * half:.1f}%p | {seeds} |")
            axes[2].bar(index, mean, yerr=[[min(half, mean)], [min(half, 1 - mean)]], capsize=4)
            axes[2].scatter([index] * 3, values, color="black", zorder=3)
        axes[2].set(xticks=x, xticklabels=["Original", "Geometry", "Geometry + obs."],
                    title="PPO after fine-tuning (3 seeds)")
    for ax in axes:
        ax.set(ylim=(0, 1.05), ylabel="Success fraction")
        ax.grid(axis="y", alpha=.25)
    fig.savefig(root / "level6_redesign.png", dpi=150)
    plt.close(fig)
    (root / "level6_redesign.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
