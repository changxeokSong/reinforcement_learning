# 알바트로스 배구: 강화학습 알고리즘 대결

서강대 마스코트 알바트로스를 모티브로 한 2D 1:1 배구 게임을 직접 만들고, 직접 구현한 PPO·DQN·SAC 에이전트를 같은 조건에서 학습시킨 뒤 리그전으로 비교하는 강화학습 기말 프로젝트다.

- 환경: 외부 물리 엔진 없이 직접 구현한 배구 게임 (이동, 점프, 스파이크, 다이빙)
- 알고리즘: PPO, Double DQN, 이산 SAC를 PyTorch로 직접 구현
- 비교: 같은 학습 스텝, 같은 상대, 같은 평가. seed 5개와 95% 신뢰구간

> 현재 상태: 본 실험(8개 실험, 학습 80회) 완료. 결과는 [실험 결과](docs/results.md)에 있다.

## 설치

Python 3.10 이상. 가상환경을 만들어서 쓴다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

이후 명령은 모두 가상환경을 켠 상태에서 실행한다. PowerShell에서 스크립트 실행이 막혀 있으면 `Set-ExecutionPolicy -Scope Process RemoteSigned`를 먼저 실행하거나, `.venv\Scripts\python`으로 직접 실행한다.

GPU는 필요 없다. 신경망이 작아서 CPU로 학습한다.

## 게임 해 보기

```powershell
python play.py                              # 사람(왼쪽) vs 어려움 봇
python play.py --left human --right human   # 사람 vs 사람
python play.py --left runs/e1/ppo_seed0/model.pt --right hard   # 학습된 AI vs 봇
python play.py --left a.pt --right b.pt --record match.gif      # AI끼리 붙여서 GIF 저장
```

| | 왼쪽 선수 | 오른쪽 선수 |
|---|---|---|
| 이동 | A / D | ← / → |
| 점프 | W | ↑ |
| 타격 | F | / 또는 오른쪽 Shift |
| 조준 (공중) | W 위, S 아래 | ↑ 위, ↓ 아래 |

- 공중에서 타격 = **스파이크**. 한 번 점프에 한 번만 휘두를 수 있다.
- 땅에서 이동 + 타격 = **다이빙**. 멀리 있는 공을 받지만 착지 후 잠깐 못 움직인다.
- R 다시 시작, ESC 종료

## 학습

```powershell
python train.py --algo ppo --seed 0
python train.py --algo sac --seed 0 --set total_steps=1000000 action_set=basic
```

결과는 `runs/<이름>/`에 저장된다: `config.json`(설정·seed·코드 버전), `metrics.csv`(평가 기록), `model.pt`(최종 정책).

## 실험 재현

```powershell
python -m tests.test_game          # 게임·통계 코드 검증
python -m tests.check_algos        # 알고리즘 구현 검증 (CartPole)

python -m experiments.final       # 모든 실험 + 리그전 + 그래프·표 (약 5시간 30분)
```

`experiments.final`은 아래를 차례로 실행한다. 하나씩 돌릴 수도 있다.

```powershell
python -m experiments.run e1 e2 e3 e4 e5 e6 e7 e8 --parallel 14   # 학습 (seed 5개씩, 총 80회)
python -m analysis.league runs/e1 runs/e2 runs/e3 runs/e4 runs/e5 runs/e6 runs/e7 runs/e8 --out runs/results/league
python -m analysis.report runs/e1 runs/e2 --out runs/results/e2_action_space   # 실험별 그래프와 표
python -m analysis.dashboard runs/e1 runs/e2 runs/e3 runs/e4 runs/e5 runs/e6 runs/e7 runs/e8   # 대시보드 (html)
```

## 눈으로 확인하기

```powershell
python watch.py                                    # PPO·DQN·SAC를 학습시키면서 서로 붙는 모습을 실시간으로 본다
python -m analysis.monitor runs/e1                 # 학습 중 승률 곡선을 실시간으로 본다
python -m analysis.progress runs/e1/ppo_seed0      # 학습 과정 영상(GIF): 체크포인트별 실력 변화
python play.py --left runs/e1/dqn_seed0/model.pt --right runs/e1/ppo_seed0/model.pt   # AI 대결 관전
```

경기 화면에서 AI 선수 옆의 막대는 그 순간 정책이 선호하는 행동이다(뒤·정지·앞·위·아래·타격). 관전 중 SPACE로 일시정지, 1~4 키로 속도를 바꾼다.

| 실험 | 비교 내용 | 학습 횟수 |
|---|---|---|
| e1 | PPO vs DQN vs SAC (확장 행동 18개) | 15 |
| e2 | 같은 알고리즘, 기본 행동 6개 (이동·점프만) | 15 |
| e3 | PPO entropy 계수 0 / 0.03 (0.01은 e1과 공유) | 10 |
| e4 | PPO 보조 보상 (공을 넘기면 +0.1) | 5 |
| e5 | PPO 1200만 스텝 (같은 시간 비교) | 5 |
| e6 | SAC 목표 엔트로피 비율 0.1 / 0.5 (0.3은 e1과 공유) | 10 |
| e7 | DQN epsilon 감소 구간 0.1 / 0.5 (0.3은 e1과 공유) | 10 |
| e8 | PPO 학습 상대 중 self-play 비율 0.3 / 0.9 (0.6은 e1과 공유) | 10 |

학습 1회(300만 스텝)에 걸리는 시간은 i7-13700KF에서 14개를 동시에 돌릴 때 PPO 약 10분, DQN 약 56분, SAC 약 2시간이다. 중간에 끊겨도 같은 명령을 다시 실행하면 끝난 것은 건너뛴다.

## 환경 요약

| | 내용 |
|---|---|
| State | 연속값 20개: 나·상대의 위치·속도·상태, 공의 위치·속도, 공과 나의 상대 위치 |
| Action | 이산 18개: 이동(뒤/정지/앞) × 위아래(없음/위/아래) × 타격(안 함/함) |
| Reward | 득점 +1, 실점 -1 |
| Episode | 한 점. 랠리가 30초를 넘으면 무승부로 끊는다 |
| 학습 상대 | 과거의 자기 자신 60%, 쉬움 봇 20%, 무작위 봇 20% |
| 평가 | 무작위·쉬움·어려움 봇 상대 승률, 에이전트끼리의 리그전(Elo) |

오른쪽 선수의 관측은 좌우를 뒤집어서 주기 때문에, 하나의 정책이 어느 코트에서든 똑같이 플레이한다. 어려움 봇은 학습에 쓰지 않는 평가 전용 기준이다. 자세한 설계는 [프로젝트 계획](docs/project_plan.md)에 있다.

## 폴더 구조

```
volleyball/   게임
  game.py       물리와 규칙
  vec_env.py    여러 경기를 동시에 진행하는 환경
  bots.py       무작위 봇, 규칙 기반 봇
  evaluate.py   두 선수의 승률 측정
  render.py     화면 그리기 (pygame)
algos/        알고리즘
  ppo.py  dqn.py  sac.py  common.py
train.py      학습 실행 (세 알고리즘 공통 루프)
play.py       사람 플레이, 관전, GIF 녹화
watch.py      학습하면서 알고리즘끼리 붙는 모습을 실시간으로 본다
experiments/  실험 일괄 실행
analysis/     리그전, Elo, 신뢰구간, 그래프, 실시간 모니터, 학습 과정 영상
tests/        게임 검증, 알고리즘 검증
docs/         계획, 보고서 구성, 실험 결과, 그래프
```

## 실험 결과

seed 5개의 평균 ± 95% 신뢰구간이다. 자세한 표와 해석은 [실험 결과](docs/results.md)에 있다.

| 설정 | 어려움 봇 상대 승률 | 리그전 Elo | 학습 시간(분) |
|---|---|---|---|
| PPO 300만 스텝 | 0.26 ± 0.09 | 886 ± 22 | 10 |
| DQN 300만 스텝 | **0.67 ± 0.07** | 1107 ± 38 | 56 |
| SAC 300만 스텝 | 0.55 ± 0.04 | 1025 ± 51 | 128 |
| PPO 1200만 스텝 | 0.63 ± 0.10 | **1245 ± 35** | 35 |
| SAC 기본 행동 (스파이크·다이빙 없음) | **0.88 ± 0.10** | 1129 ± 64 | 138 |

- 같은 스텝에서는 DQN > SAC > PPO. 같은 시간을 주면 PPO가 가장 강하다.
- SAC는 스파이크·다이빙을 빼자 오히려 훨씬 강해졌고, DQN은 그 기술이 있어야 학습된 상대를 이겼다.
- 탐험 하이퍼파라미터(PPO entropy, SAC 목표 엔트로피, DQN epsilon 구간)와 보조 보상은 신뢰구간 안의 차이만 만들었다. 탐험이 부족하면 seed 하나가 무너지는 일이 생겼다.
- PPO는 self-play 비율을 0.9로 올리면 봇 상대 승률은 같지만 리그전에서 더 강해졌다.

![리그전 Elo](docs/figures/league_elo.png)

![어려움 봇 상대 승률 학습 곡선](docs/figures/e1_curves_wr_hard.png)

## 두 번째 환경: 레이저 미션 (Unity 3D)

알바트로스가 움직이는 레이저를 피해 금고까지 가는 1인 미션이다. Unity 6 + ML-Agents로 만들었고, 배구와 같은 PPO·DQN·SAC 구현으로 학습한다. 환경 설계와 학습이 안 되던 원인을 하나씩 고친 과정은 [레이저 미션 문서](docs/laser.md)에 있다.

준비 (Unity 6000.0 LTS, Python 3.10)

```powershell
py -3.10 -m venv .venv-unity
.venv-unity\Scripts\python -m pip install -r requirements-unity.txt --extra-index-url https://download.pytorch.org/whl/cpu
# 실행 파일 빌드 (에디터를 열지 않고 명령줄로)
& "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -quit -projectPath unity/LaserMission -executeMethod LaserBuild.All
```

실행

```powershell
unity\LaserMission\Build\LaserMission.exe                                 # 1~10단계 캠페인 (WASD, Space 점프, C 슬라이딩)
.venv-unity\Scripts\python -m laser.experiments x11 --parallel 3           # 최신 랜덤 캠페인 1~10단계 새 학습
.venv-unity\Scripts\python -m laser.watch runs/laser/x11/sac_random_campaign_seed0 --view chase
.venv\Scripts\python -m laser.report --progress                             # X11 진행 그래프 갱신
python -m laser.report                                                      # 표·그래프
.venv-unity\Scripts\python -m laser.record <model.pt> --level 3 --out play.gif   # GIF 녹화
```

![SAC가 레벨 4를 통과하는 장면](docs/figures/laser_sac_level4.gif)

*학습된 SAC가 레벨 4(무작위 레이저 5개, 1.3배 속도)를 통과하는 장면. 높은 레이저는 슬라이딩, 낮은 레이저는 점프로 피한다.*

실행 파일을 바로 열면 **1~10단계 캠페인**이 시작된다. 각 단계는 고유한 장애물 조합을 바탕으로 출발 위치, 레이저 위치와 움직임이 다른 배치 4개 중 하나를 뽑는다. 성공 후 **Enter**로 다음 단계에 진입한다. 실패 후 **Enter**를 누르거나 **R**로 재도전하면 단계 번호는 그대로이고 직전과 다른 배치가 나온다. 10단계를 완료하면 **MISSION COMPLETE**가 표시되며, **Enter**로 전 단계의 배치를 다시 뽑아 시작한다. **P**로 연습 모드를 전환하며, 연습 모드에서는 **0~9**와 **=**(레벨 10)로 바로 이동한다. 캠페인 진행은 실행 중에 유지된다.

직접 플레이하거나 AI를 관전할 때 **V**로 시점을 순환하고, **F1~F4**로 전체·뒤따르기·측면·정면을 바로 선택한다. **우클릭 드래그**로 회전하고 **휠**로 확대·축소한다. **Home**은 현재 시점의 각도와 확대를 초기화한다. `laser.watch --view chase`처럼 시작 시점을 지정하고, `--levels 1 2 3 4 5 6`으로 에피소드마다 레벨을 순환할 수 있다. 정책의 순차 클리어를 관전하려면 `--campaign`을 사용한다. 이 모드는 성공할 때만 승급한다.

X11은 실제 캠페인과 같은 단계별 네 가지 배치에서 새 SAC 정책을 학습한다. 학습 중에는 `runs/results/laser/x11_progress.png`에서 저장된 스텝과 중간 평가 결과를 볼 수 있다. 명령을 다시 실행하면 그래프가 갱신된다. 학습이 모두 끝나면 같은 폴더에 `x11_random_campaign.png`와 `summary.md`가 생성된다. 이전 학습의 로컬 체크포인트는 휴지통으로 옮겼다. 실험 문서에 남은 이전 숫자와 영상은 당시 환경에서의 기록이다.

X12는 X11과 같은 빌드·환경 설정에서 PPO와 Double DQN을 각각 시드 0·1·2, 1,200만 환경 스텝으로 학습한다. 최종 체크포인트 9개를 같은 평가 조건에서 비교한다. 모델마다 각 레벨 200판의 성공률과 200회의 순차 캠페인 완주율을 구한다. 순차 캠페인은 성공할 때만 다음 단계로 이동하며, 단계마다 시도 3번을 허용한다. 결과 표와 그래프는 `runs/results/laser/campaign_comparison.md`, `campaign_comparison.png`, `campaign_completion.png`에 저장된다.

최종 평가에서는 Unity의 강제 리셋 중 기본 행동이 실행된 판을 준비 판으로 처리하고, 방마다 게임 시간 0에 시작한 다음 판부터 집계한다. X11과 X12의 학습 로그에 저장된 중간 평가는 종전 리셋 동작을 포함한다.

```powershell
# 새로 X12를 시작할 때 X11에서 사용한 Unity 빌드를 지정한다.
$build = (Get-Content -Raw runs/laser/x11/sac_random_campaign_seed0/config.json | ConvertFrom-Json).common.build
.venv-unity\Scripts\python -m laser.experiments x12 --parallel 6 --worker-base 1000 --build $build
# X11과 X12의 학습이 끝난 뒤 최종 모델 평가와 그래프를 생성한다.
.venv-unity\Scripts\python -m laser.campaign_eval
.venv\Scripts\python -m laser.report --campaign
```

후속 실험에서는 순차 캠페인에서 막힌 단계에 PPO actor를 추가 학습한다. 레벨별 검증에서는 네 배치의 성공률을 같은 비중으로 집계해 각 단계에 사용할 정책을 고른다. 선택이 끝나면 단계당 최대 3회와 10회 시도 조건에서 순차 캠페인을 각각 600회 평가한다. 평가 환경 시드는 검증용과 다르고, 사용할 수 있는 배치는 게임과 같은 네 가지다. 단계별 정책을 골라 쓰는 이 방식은 단일 정책의 X11/X12 비교와 별도 결과다.

```powershell
.venv-unity\Scripts\python -m laser.ppo_specialists
.venv\Scripts\python -m laser.report --specialists
.venv-unity\Scripts\python -m laser.watch runs/results/laser/ppo_specialists.json --campaign --view chase
```

CUDA가 지원되는 PyTorch를 설치한 환경에서는 아래처럼 SAC 학습에 GPU를 선택할 수 있다. Unity 시뮬레이션과 체크포인트 평가는 CPU에서 실행된다. `--root`와 `--worker-base`를 별도로 지정하면 진행 중인 X11 실행과 결과 폴더 및 통신 포트가 겹치지 않는다.

```powershell
# CUDA PyTorch를 설치한 가상환경을 활성화한 뒤 실행
python -m laser.experiments x11 --sac-device cuda --seeds 0 --parallel 1 --root runs/gpu --worker-base 980
```

레벨 5에서는 같은 SAC 정책으로 두 배치의 [성공 장면(5.3초)](docs/figures/laser_sac_level5_success.gif)과 [충돌 장면(5.1초)](docs/figures/laser_sac_level5_hit.gif)을 녹화했다. 학습 시드는 1이고, 녹화 환경 시드는 각각 0과 11이다.

1~10단계 캠페인 결과 (seed 3개, 단계당 최대 3번 시도. 자세한 내용은 [실험 결과](docs/results.md#모방-학습-단계별-ppo를-정책-하나로-합치기-11장))

| 정책 하나로 1~10단계 | 1~10단계 평균 성공률 | 10단계 완주 |
|---|---:|---:|
| SAC (강화학습만, 1,200만 스텝) | 57.5% | 0 / 600 |
| PPO (강화학습만, 1,200만 스텝) | 51.6% | 0 / 600 |
| 모방 학습 학생 (단계별 PPO 선생님 → BC/DAgger) | 97.1% | 600 / 600 (단계당 1번이면 446 / 600) |
| 모방 학습 학생 + 10단계 배치 1개 시범 | **100%** | **600 / 600 (단계당 1번도 600 / 600)** |

정책 하나로 강화학습을 하면 단계가 늘어날수록 앞 단계를 잊었다. 단계마다 PPO 선생님을 따로 학습한 뒤, 모방 학습(behavior cloning, DAgger)으로 학생 정책 하나에 합쳐 전 단계를 완주했다. PPO가 무작위 탐험으로 한 번도 성공하지 못한 10단계 배치 하나는 탐색으로 찾은 통과 경로를 시범으로 넣어 해결했다.

![imitation](docs/figures/laser_imitation.png)

| 같은 배치(10단계 배치 3)를 단계별 정책이 차례로 플레이 | 최종 학생 정책 하나가 1~10단계를 연속 통과 |
|---|---|
| ![단계별](docs/figures/laser_steps.gif) | ![10단계 완주](docs/figures/laser_campaign.gif) |

GIF는 `python -m laser.record_steps steps` / `full`로 다시 만든다.

1~4단계 초기 실험 결과 (seed 3개, 레벨 1~4 평균 성공률. 자세한 내용은 [실험 결과](docs/results.md#레이저-미션-결과))

| 설정 | 성공률 | 학습 시간 | 비고 |
|---|---|---|---|
| SAC + 기울기 상한 + 목표값 범위 (400만 스텝) | **0.93** | 180분 | 기본 SAC는 seed 하나가 Q값 발산으로 0. 원인을 찾아 고친 결과 |
| PPO 레벨 무작위 (2000만 스텝) | 0.87 | 57분 | SAC 설정보다 짧게 학습했고 최종 평균 성공률은 낮았음 |
| PPO 레벨 무작위 (400만 스텝) | 0.66 | 17분 | 커리큘럼(0.53)보다 좋음. 커리큘럼은 앞 레벨을 잊는다 |
| DQN (400만 스텝) | 0.40 | 105분 | 가장 불안정 |

![laser sac](docs/figures/laser_x6_sac_stability.png)

캐릭터는 그림 생성 AI로 직접 디자인한 알바트로스를 3D 생성 AI로 모델링하고, 원본 그림을 투영해서 색을 입힌 뒤 날개·다리를 잘라 움직이게 했다 (`tools/split_bird.py`). 학교 공식 캐릭터가 아니다.

## 학습된 모델

[Releases v1.0](https://github.com/changxeokSong/reinforcement_learning/releases/tag/v1.0)에 있다.

- `models_seed0.zip`: 설정 16개의 seed 0 모델. 풀어서 `python play.py --left models/e5_ppo_12m_seed0/model.pt --right hard`처럼 쓴다.
- `models_all.zip`: 학습 80회 전체와 리그전 결과. 저장소 폴더에 풀면 `runs/` 아래 원래 경로로 들어가서, 학습 없이 `analysis.report`·`analysis.dashboard`로 그래프를 다시 만들 수 있다.

레이저 미션은 [Releases v2.0](https://github.com/changxeokSong/reinforcement_learning/releases/tag/v2.0)에 있다.

- `LaserMission_windows.zip`: 레벨 0~4를 해 볼 수 있는 Windows 실행 파일. 레벨 5·6은 위의 Unity 빌드 방법을 사용한다.
- `laser_models.zip`: 학습 33회 전체(`runs/laser/`). 가장 좋은 모델은 `runs/laser/x7/sac_clip2_seed1/model.pt`

## 보고서

레이저 미션 발표 자료는 [docs/LaserMission_presentation.pptx](docs/LaserMission_presentation.pptx)다. 15장으로, 처음 실패부터 정책 하나로 10단계를 완주하기까지를 단계별로 구성했다(`tools/build_presentation.js`로 다시 만든다). 제출 전에 표지와 기여 항목에 팀원 이름·학번과 담당 작업을 넣는다. 배구 쪽 발표 순서는 [보고서 구성안](docs/report_outline.md)을 참고한다.

## 팀

| 이름 | 학번 | 담당 |
|---|---|---|
| | | A: 환경 |
| | | B: PPO, self-play |
| | | C: DQN, SAC, 평가·분석 |

## 참고

- Schulman et al., *Proximal Policy Optimization Algorithms*, 2017
- Mnih et al., *Human-level control through deep reinforcement learning*, 2015
- van Hasselt et al., *Deep Reinforcement Learning with Double Q-learning*, 2016
- Haarnoja et al., *Soft Actor-Critic*, 2018 / Christodoulou, *Soft Actor-Critic for Discrete Action Settings*, 2019
- 코드 작성에 AI 코딩 도구(Claude Code)의 도움을 받았고, 팀원이 직접 읽고 검증했다.
