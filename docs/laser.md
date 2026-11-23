# 레이저 미션 (Unity 3D 환경)

배구에 이은 두 번째 환경이다. 알바트로스가 움직이는 레이저를 피해 금고까지 가는 1인 미션이다. Unity로 3D 화면을 만들고, ML-Agents로 Python과 연결해서 배구와 같은 PPO·DQN·SAC 구현으로 학습한다.

- 배구: 둘이 겨루는 **대결형**. 상대도 학습하므로 목표가 계속 바뀐다
- 레이저: 혼자 푸는 **미션형**. 목표는 고정이지만 실패가 바로 끝으로 이어지고, 보상이 드물다

## 구성

| 부분 | 파일 | 내용 |
|---|---|---|
| 게임 규칙 | `unity/LaserMission/Assets/Scripts/Room.cs` | 이동·점프·슬라이딩, 레이저 충돌, 관측, 레벨 생성 |
| 레이저 | `Laser.cs` | 레이저 4종의 움직임 (시간 t의 식으로 계산) |
| ML-Agents 연결 | `LaserAgent.cs` | 보상, 에피소드 종료, 키보드 조작 |
| 화면 | `Bootstrap.cs`, `Effects.cs` | 방 배치, 카메라, HUD, 효과음, 파티클 |
| 빌드 | `Assets/Editor/LaserBuild.cs` | 장면·재질·캐릭터 조립·후처리·실행 파일 빌드를 명령줄로 |
| Python | `laser/env.py`, `train.py`, `experiments.py`, `report.py`, `watch.py`, `record.py` | 벡터 환경, 학습, 실험, 분석, 관전, 녹화 |

물리 엔진(Rigidbody, Collider)은 쓰지 않는다. 위치를 직접 계산하고, 충돌은 "에이전트 캡슐과 레이저 선분 사이의 최소 거리"로 판정한다. 그래서 같은 seed면 결과가 같고, 한 프로세스에 방 16개를 넣어도 초당 약 1만 5천 스텝이 나온다.

## MDP

| | 내용 |
|---|---|
| State | 연속값 66개. 자신 11개(위치, 속도, 슬라이딩 남은 비율, 착지 여부, 경과 시간, 레벨, 금고까지 거리) + 레이저 5개 × 11개(종류 4, 가장 가까운 지점의 상대 x·높이·상대 z, 그 지점의 속도 x·z, 켜짐, 깜빡임 전환까지 남은 시간) |
| Action | 이산 27개: 좌우(3) × 앞뒤(3) × (없음 / 점프 / 슬라이딩)(3) |
| Reward | 금고 도착 +1, 레이저 -1, 시간 초과(20초) -1, 매 0.1초 -0.01, 금고 쪽으로 다가간 거리 × 0.5 (출발선부터 금고까지 합이 0.5) |
| Episode | 성공, 레이저 접촉, 시간 초과 중 하나로 끝난다. 결정 한 번 = 0.1초 |

| 레벨 | 레이저 |
|---|---|
| 0 | 없음 |
| 1 | 고정된 가로 막대 2개 (낮으면 점프, 높으면 슬라이딩) |
| 2 | 가로 막대, 좌우로 쓸고 가는 세로 막대, 앞뒤로 움직이는 가로 막대 |
| 3 | 4종(가로 막대, 세로 막대, 회전 막대, 깜빡이는 막대)을 섞은 순서로 하나씩 |
| 4 | 무작위 종류 5개, 속도 1.3배 |
| 5 | 6개 구간을 무작위 순서로: **겹친 레이저** 2곳(가로 막대 + 같은 자리를 쓸고 가는 세로 막대. 점프·슬라이딩과 좌우 회피를 동시에), **레이저 벽** 2곳(바닥부터 머리 위까지 막고, 좌우로 움직이는 폭 1.6m 통로 하나만 열림. 점프·슬라이딩으로 못 넘는다), 회전 막대, 깜빡이는 막대 (속도 1.4배). 레이저 10개 |
| 6 | 통로가 반대 위상으로 움직이는 이중 벽, 폭 1.1m 통로가 있는 벽, 잠깐 꺼지는 전폭 벽, 움직이는 겹친 레이저 2곳, 빠른 회전 막대. 레이저 12개 |
| 7 | 좁게 움직이는 통로 3곳과 회전 막대, 좌우로 쓸고 가는 레이저 |
| 8 | 방 전체를 차단했다가 열리는 점멸 벽 3곳. 벽마다 열리는 시간이 다름 |
| 9 | 서로 반대로 움직이는 통로 두 쌍, 이동 막대, 점멸 벽 |
| 10 | 움직이는 이중 통로와 좁은 통로, 회전·좌우 이동 레이저, 시작과 끝의 점멸 벽 |

독립 실행은 1단계부터 10단계까지 순서대로 진행한다. 각 단계는 기존 장애물 조합을 기준으로 출발 위치, 레이저 위치, 움직임 속도와 점멸 타이밍이 달라지는 배치 4개를 사용한다. 실패 후 재도전하거나 `R`로 다시 시작하면 같은 단계에서 직전과 다른 배치가 나온다. 10단계에 성공하면 게임 진행이 멈추고 클리어 화면이 표시된다. 여기서 새 캠페인을 시작하면 전 단계가 직전과 다른 배치를 뽑는다. X11의 Python 학습도 동일한 네 가지 배치와 재도전 규칙을 사용한다. 학습은 레벨별 에피소드 단위로 진행한다.

단계별 배치 4개를 모두 대상으로 경로 탐색을 수행했다. 40개 경로를 실제 게임 행동으로 재생해 각 단계의 제한 시간 안에 도착함을 확인했다. 실패 후에는 단계 번호를 유지하면서 출발 위치와 레이저 배치가 바뀌는지도 검증했다.

레이저 위치·높이·위상은 에피소드마다 무작위로 바뀐다. 같은 배치를 외워서는 풀 수 없다.

## 설계를 고친 과정

처음 설계로는 학습이 되지 않았다. 원인을 하나씩 찾아서 고쳤고, 각 단계에서 무엇을 확인했는지 남긴다. 레벨 1은 "레이저가 낮으면 점프, 높으면 숙이기"라는 단순한 규칙 정책으로 100% 통과할 수 있어서, 학습 실패가 환경 탓인지 학습 탓인지 가릴 기준으로 썼다.

| 단계 | 증상 | 원인 | 고친 것 | 결과 (PPO, 레벨 1) |
|---|---|---|---|---|
| 1 | 성공률 0 | 시간 초과가 0점이라 레이저 앞에서 멈추는 것이 가장 안전 | 시간 초과를 -1로 | 여전히 0 |
| 2 | 성공률 0, 대부분 시간 초과 | 할인율 0.99에서는 25초 뒤의 -1이 지금 거의 0으로 보인다 | 매 0.1초 -0.01 시간 벌점, 제한 시간 20초 | 약 10% |
| 3 | 10%에서 정체 | 레이저 높이와 상관없이 항상 점프. 숙이기는 4번 연속 눌러야 해서 탐험으로 찾기 어려움 | 숙이기를 한 번 누르면 0.6초 지속되는 슬라이딩으로 | 약 25% |
| 4 | 25%에서 정체 | 관측에서 낮은/높은 레이저의 차이가 ±0.1 정도로 작다 | 레이저 종류, 가장 가까운 지점의 실제 높이, 앞쪽부터 정렬 | **약 90%** |
| 5 | 깜빡이는 레이저에서 실패 | 언제 꺼질지 알 수 없다 | 깜빡임 전환까지 남은 시간 추가 | (본 실험에 반영) |

배운 점
- **보상 설계는 할인율과 같이 봐야 한다.** 에피소드 끝의 벌점만으로는 "버티기"를 막지 못했다. 매 순간의 작은 벌점이 필요했다.
- **행동 설계가 탐험 난이도를 정한다.** 같은 "숙이기"라도 여러 번 연속 눌러야 하면 무작위 탐험으로 거의 발견되지 않는다.
- **한 번의 개선 효과는 반복 실험으로 다시 확인해야 한다.** 4단계에서 관측을 바꾸자 성공률이 25%에서 90%로 올랐지만, 같은 시기에 다른 수정도 함께 들어갔다. 400만 스텝, seed 3개로 다시 비교한 X3에서는 원래 관측과 개선한 관측의 차이가 거의 없었다. 관측 형태만의 효과는 생각보다 작았다.

## 실험

| 실험 | 비교 | 학습 횟수 |
|---|---|---|
| X1 | PPO vs DQN vs SAC (커리큘럼 학습) | 9 |
| X2 | 학습 방식: 커리큘럼 / 커리큘럼 + 복습(절반은 낮은 레벨) / 레벨 무작위 / 처음부터 레벨 4 (PPO) | 9 |
| X3 | 관측: 설계한 특징 / 원시 선분 좌표 (PPO) | 3 |
| X4 | 보상: 시간 벌점 없음 / 보조 보상 없음 (PPO) | 6 |
| X5 | 학습량: PPO 레벨 무작위 2000만 스텝 | 3 |
| X6·X7 | SAC 안정화: 기울기 노름 상한 / + Bellman 목표값 범위 제한 | 6 |
| X8 | 레벨 5 추가: SAC(X7 설정, 커리큘럼 0→5) / PPO(레벨 1~5 무작위, 2000만 스텝) | 6 |
| X9 | X8의 SAC 설정에서 레벨 5에 도달한 뒤, 에피소드의 25%를 레벨 4로 배정 | 3 |
| X10 | 하나의 SAC 정책으로 레벨 1~6을 학습. 레벨 2부터 에피소드의 50%를 이전 레벨 1~현재 레벨−1에 균등하게 배정 | 3 |
| X11 | 최신 랜덤 캠페인 레벨 1~10의 실제 배치로 SAC를 처음부터 학습. 레벨 2부터 50% 이전 단계 복습, 늦어도 720만 스텝에 레벨 10 배정 시작 | 3 |

기본 예산은 설정당 400만 스텝이며 X5와 X8의 PPO는 2000만 스텝, X10 SAC는 800만 스텝이다. 각 설정의 학습 seed는 0, 1, 2다. 커리큘럼은 레벨 0에서 시작해서, 최근 300판 성공률이 0.8을 넘으면 다음 레벨로 올린다. X10에서는 실제 현재 레벨에서 끝난 판만 승급에 사용한다. 최종 평가는 학습에 쓰지 않은 seed로 레벨마다 200판을 돌리고, 정책이 가장 높은 점수를 준 행동을 사용한다. X10의 주요 지표는 레벨 1~6 평균과 가장 낮은 레벨의 성공률이다. 레이저가 없는 레벨 0도 작동 확인용으로 평가한다.

X11의 예산은 시드당 1200만 스텝이다. 평가 시드는 학습과 분리하며, 배치 집합은 실제 캠페인과 공유한다. 레벨 1~10 성공률과 평균·최저 성공률을 기록한다. 이전 로컬 모델은 휴지통으로 옮겼고, 이 결과는 새 가중치로 시작한 X11에서만 산출한다.

별도 데이터셋 없이 Unity가 생성한 관측·행동·보상·종료 기록으로 학습한다. 위치와 속도는 방 크기와 이동 속도 등으로 정규화하고, 레이저 종류는 원-핫 벡터로 표현한다. 실험 실행기는 실행 파일과 Unity 데이터 전체의 SHA-256 지문으로 빌드 복사본을 식별한다. 평가는 매 배치의 리셋 직후 관측에서 실제 레벨을 검사한다.

```powershell
.venv-unity\Scripts\python -m laser.experiments x1 x2 x3 x4 x5 x6 x7 x8 --parallel 8   # 학습
python -m laser.report                                                       # 표·그래프 → runs/results/laser/
```

결과는 [실험 결과](results.md)의 레이저 미션 절에 정리한다.

## 프로젝트 체크리스트

### 문제 정식화 연습

#### 로봇 청소기

예제는 벽이 없는 4×4 격자, 모서리에서 시작, 충전 없이 배터리 40단위로 가정한다. 한 동작에 배터리 1단위를 쓰며, 방 전체를 청소하는 것이 목표다.

| 항목 | 정의 |
|---|---|
| 상태 `s` | 로봇의 칸, 칸마다 청소 여부를 담은 마스크, 남은 배터리. 지도나 장애물이 에피소드마다 바뀌면 그 배치도 포함한다. |
| 행동 `a` | 상·하·좌·우 이동 또는 현재 칸 청소. 경계를 벗어나는 이동은 제자리에 남고 배터리 1단위를 쓴다. 이동과 청소는 별도 동작이다. |
| 보상 `r` | 마지막 칸을 청소하면 +1, 미완료 상태로 배터리가 소진되면 −1. 행동당 −0.005와 처음 청소한 칸당 `+0.2/16`을 추가하는 dense reward를 예로 든다. |
| `terminated` | 전 칸 청소 또는 미완료 상태에서 배터리 소진. 마지막 배터리로 마지막 칸을 청소하면 성공이다. |
| `truncated` | 평가기가 별도 스텝 한도에 도달해, 배터리가 남고 과제가 진행 중인 에피소드를 끊는 경우다. |
| 할인율 `γ` | 0.98을 초기값으로 둔다. 지그재그로 방문하면 이동 15번과 청소 16번, 총 31번에 완료할 수 있다. 첫 행동 보상의 가중치를 1로 두면 31번째 행동의 보상 가중치는 `0.98³⁰ ≈ 0.55`이고, 배터리 한도인 40번째 행동은 `0.98³⁹ ≈ 0.45`다. |

지도·청소 마스크·배터리·위치를 알면 다음 상태와 보상이 현재 상태와 행동으로 결정된다. 배터리나 마스크를 빼면 동일한 위치에서도 종료 조건과 첫 청소 보상이 달라진다. 매번 청소할 때 보너스를 주면 한 칸을 반복해서 청소할 수 있으므로, 보너스는 마스크가 더러움에서 깨끗함으로 바뀔 때만 지급한다. 쉬운 칸만 청소하고 실패하는 정책에 대비해 평가에서 전체 청소 성공률과 남은 칸 수를 따로 기록한다.

#### 레이저 미션

| 항목 | 정의 |
|---|---|
| 상태와 관측 | 전체 상태에는 캐릭터 위치·속도·접지·슬라이딩 타이머, 경과 시간, 에피소드당 레이저 배치와 운동 파라미터가 들어간다. 이 정보로 에피소드 안의 다음 상태를 계산한다. 정책은 에이전트 특징 11개와 우선순위가 높은 레이저 5개의 특징 55개를 받아 부분 관측을 한다. |
| 행동 | 좌우 3가지 × 앞뒤 3가지 × 자세 3가지(기본·점프·슬라이딩), 총 27개. 한 번의 결정은 시뮬레이션 0.1초다. |
| 보상 | 도착 +1, 충돌·게임 시간 제한 −1. 매 결정 −0.01과 `0.5 × (z′−z)/(8.6−(−8.5))`을 더하는 dense reward로 기존 비교 실험을 수행했다. |
| `terminated` | 금고 도착, 레이저 충돌, 게임 규칙인 20초 경과다. |
| `truncated` | 과제가 진행 중인데 외부 평가 한도 등으로 중단되고 ML-Agents가 이를 `interrupted`로 전달한 경우다. |
| 할인율 `γ` | 실제 실험 설정은 0.99다. 0.1초 결정 기준으로 5초 뒤 보상의 가중치는 약 0.605, 10초 뒤에는 0.366, 20초 뒤에는 0.134다. 가중치가 절반이 되는 시간은 약 6.9초다. |

레이저 벽은 통로가 열리는 위치와 시간을 맞춰야 한다. 성공 장면에는 약 5~6초가 걸렸고, `γ=0.99`는 그 정도 앞의 금고 도착 보상에 절반 넘는 가중치를 남긴다. 할인율별 성능 비교는 이번 정식화의 검증 범위에 포함하지 않았다.

보상만 보면 금고에 못 가도 전진 보상을 일부 얻을 수 있다. 앞뒤로 같은 거리를 왕복하는 경우 할인 때문에 먼저 받은 전진 보상이 조금 더 크게 남지만, 최대 직진 이동량 0.4m로 계산해도 두 결정의 시간 벌점을 포함한 왕복 보상은 약 −0.0198이다. 장애물 앞에 오래 대기하거나 초반 전진 후 충돌하는 행동은 리턴과 함께 금고 도착률, 충돌률, 시간 초과 비율, 플레이 영상으로 점검한다. `potential_shaping=true`의 할인된 보조 보상은 종료 잠재값을 0으로 두었을 때 출발 상태에서 결정되는 상수로 합쳐진다.

### Formulation

- **관측과 행동.** PPO·Double DQN·이산 SAC는 위 표의 66차원 관측을 받아 이산 행동 27개 중 하나를 선택한다. 적용한 할인율은 `γ = 0.99`다.
- **Markov 여부.** 시뮬레이터는 캐릭터의 위치·속도·접지·슬라이딩 상태, 시간, 각 레이저의 위치·종류·운동 파라미터를 보존한다. 한 에피소드 안에서 이 전체 상태와 행동으로 다음 상태가 결정된다. 정책은 우선순위가 높은 레이저 5개와 일부 운동 특징만 보므로, 같은 관측이라도 누락된 레이저나 위상에 따라 다음 결과가 달라질 수 있다. 따라서 정책 입력은 부분 관측이다.
- **종료와 중단.** 금고 도착, 레이저 충돌, 게임 규칙인 20초 경과는 `terminated=True`다. 20초 경과에는 실패 보상 −1을 준다. 별도 외부 중단이 ML-Agents의 `interrupted`로 전달되면 `truncated=True`다. Python은 실패한 에피소드의 마지막 시뮬레이션 시간을 사용해 20초 경과를 판별한다. 이전 로그에서는 Python 스텝 수를 사용해 실제 시간 초과를 충돌로 센 경우가 생길 수 있었다. 성공률 계산과 종료 플래그는 이 구분에 영향을 받지 않는다.

### Reward

- **기존 실험 보상.** 도착 +1, 충돌 또는 시간 초과 −1에 매 결정 −0.01과 전진 거리 변화 `0.5 × (z′−z)/(goalZ−startZ)`를 더한다. 매 결정 보상이 있는 dense reward다.
- **Potential-based 보상.** 기존 전진 보상은 `γ=0.99`에서 `γΦ(s′)−Φ(s)` 형태와 일반적으로 같지 않다. 이 형태를 시험할 때는 `potential_shaping=true`를 사용한다. 비종료 상태에서 `Φ(s)=0.5 × (z−goalZ)/(goalZ−startZ)`, 모든 종료 상태에서 `Φ(s)=0`으로 두고, 알고리즘 설정의 할인율을 전달한다. 성공·충돌·시간 초과 경로에서 한 스텝 보상과 할인된 보조 보상 누적값이 계산식과 일치함을 확인했다. X1~X9의 비교는 기존 보상 설정을 사용한다.
- **행동 점검.** 설계 초기에 에이전트가 레이저 앞에서 멈췄고, 시간 초과 보상과 시간 벌점을 조정했다. 같은 SAC 정책의 [성공](figures/laser_sac_level5_success.gif)과 [충돌](figures/laser_sac_level5_hit.gif) 장면을 검토했다. 시간 초과 집계를 수정한 뒤 X8 모델 6개를 별도 환경 시드 2777에서 레벨 5로 200판씩 평가했다. 1,200판에서 시간 초과가 관찰된 경우는 없었다.

### Debugging

- **무작위 기준선.** 27개 행동을 균등하게 고르는 정책은 레벨 1~5에서 레벨당 600판을 평가해 매 레벨 성공 0판이었다. X1의 PPO·DQN·SAC는 레벨 1~4 평균에서 이 기준선을 넘었다. 무작위 평가의 환경 및 행동 난수 시드는 1000·1001·1002다.
- **PPO 로그.** `entropy`, `approx_kl`, `v_loss`는 기존 로그에도 있다. 새 실행은 `clip_fraction`도 기록한다. 이는 PPO 갱신의 모든 미니배치에서 확률비 `r`이 `|r−1| > ε`를 만족한 샘플 비율이다. 시작 시점에는 갱신 전이라 학습 진단 칸이 비어 있다. 이전 실행에서 기록하지 않은 clip fraction은 소급할 수 없다.

#### 디버깅 체크리스트 7개

| 항목 | 검증 내용 |
|---|---|
| 풀 수 있는 환경에서 시작 | 레이저가 없는 레벨 0에서 전진 정책이 44번의 결정으로 도착했다. CartPole-v1에서도 PPO를 10만 스텝씩 학습해 시드 3개를 확인했다. |
| 무작위 정책 비교 | 레벨 1~5에서 균등 무작위 정책을 레벨당 600판 평가했다. 레벨 1~4의 동일 예산 비교(X1)에서 세 학습 정책 모두 이 기준선을 넘었다. |
| 리턴과 학습 지표 기록 | 새 평가는 레벨별 무할인 에피소드 리턴 평균, 성공·충돌·시간 초과 비율을 기록한다. PPO는 엔트로피·KL 추정치·clip fraction·value loss를 기록한다. |
| 지표의 정상 동작 확인 | 두 행동의 균등 정책을 고정한 검사에서 엔트로피는 `ln(2)`, KL 추정치는 0, clip fraction은 0이었고 양의 목표값에 대해 value loss가 양수였다. |
| 에이전트 관찰 | 레벨 5 환경 시드 0·1·11에서 같은 SAC 모델의 3개 에피소드를 렌더링하고 플레이를 확인했다. 성공 2판과 충돌 1판에서 이동 및 통로 통과를 확인했고, 별도의 X8 재평가 1,200판에서 시간 초과는 0판이었다. |
| 한 번에 변수 하나 | X3는 관측만, X4의 각 실험은 시간 벌점 또는 전진 보상만, X6→X7은 Bellman 목표값 제한만 바꿨다. X5와 X1→X6은 Unity 빌드도 달랐으므로 단일 변수의 효과를 확정하는 근거에서 제외한다. |
| 여러 시드에서 검증 | 본 실험은 시드 0·1·2를 사용하고 시드별 값과 95% t 신뢰구간을 보고한다. 데모 한 판과 단일 시드의 실패는 관찰 사례로 기록한다. |

엔트로피는 행동 분포의 퍼짐을 보여 준다. 27개 행동에서는 이론적 상한이 `ln(27) ≈ 3.296`이다. `approx_kl`은 기존 로그에서 마지막 미니배치의 표본 추정치라 작은 음수가 나올 수 있다. clip fraction은 0~1이고 value loss는 유한한 0 이상의 값이어야 한다. 학습 중 지표는 갱신 강도와 보상 스케일에 따라 움직이므로, 단일 수치와 함께 성공률 및 플레이를 본다.

CartPole PPO의 마지막 20판 평균 리턴은 학습 시드 0·1·2에서 각각 487.25, 490.50, 430.85였다. 시드마다 PPO 갱신 97회에서 네 진단 지표가 유한했고, 엔트로피와 clip fraction, value loss가 각각의 수학적 범위 안에 있었다. 이 수치는 CartPole 학습 검증용이며 레이저 미션의 진단 임계값으로 사용하지 않는다.

### Experiments

- **주 비교는 X1.** 같은 커리큘럼 규칙과 400만 환경 스텝으로 PPO·DQN·SAC를 비교했다. 각 방법의 학습 시드는 0·1·2이며, 시드마다 학습과 다른 평가 시드에서 레벨당 200판을 평가했다. 보고서의 평균과 양측 95% t 신뢰구간은 학습 시드별 성공률을 사용한다.
- **별도 실험.** X5는 PPO의 스텝 예산을 바꾼 실험이다. X8의 SAC(400만 스텝·커리큘럼)와 PPO(2,000만 스텝·레벨 무작위)는 각각의 학습 설정 결과로 해석한다. X9는 X8 SAC와 같은 스텝·학습 시드에서 레벨 4 복습 효과를 비교한다.
- **기록.** 시드별 `config.json`, `metrics.csv`, `final.json`과 모델을 저장한다. 초기 X8의 레벨 5 빌드 오류, 기존 SAC의 발산, 수정 후 재평가를 [실험 결과](results.md)에 기록했다.

```powershell
.venv-unity\Scripts\python -m laser.baseline
.venv-unity\Scripts\python -m tests.check_laser
.venv-unity\Scripts\python -m laser.train --algo ppo --seed 0 --set potential_shaping=true
.venv\Scripts\python -m tests.check_algos --algo ppo --seeds 0 1 2 --diagnostics-out runs/results/laser/cartpole_ppo_diagnostics.json
```

### 6단계 설계 재검증

Unity의 `LaserSolvabilityProbe.RunLevel6Audit`를 `-level6-audit-output <절대 경로>`와 함께 실행하면
동일한 생성 시드 60개와 캠페인 배치 4개에서 설계 0~2의 통과 경로와 조작 오차 허용 정도를 검사한다.
`level6_design=0`은 기존 배치다. 1은 이중벽의 공칭 간격을 1.10m에서 1.44m로 넓힌다.
2는 좁은 통로의 물리적 폭도 1.10m에서 1.36m로 넓힌다. 3은 좁은 통로의 좌우 이동 속도 제한을 추가한 비교 후보다.
`obs_mode=2`는 6단계에서 움직이는 통로 하나를 관측 한 칸으로 나타내고 진입 중심, 충돌 여유, 좌우 속도를 제공한다.
깜빡이는 전폭 벽도 별도 유형으로 표시한다.

당시 Unity 실행 파일을 직접 플레이하면 설계 3이 적용됐다. 최신 게임은 아래 리팩토링 빌드의 설정을 사용한다. 정책 학습과 실험에서는 설계 0~3을 지정할 수 있다.

```powershell
# 수정 소스로 별도 빌드를 만든 뒤 실행
.venv-unity\Scripts\python -m tests.check_level6 --candidate runs/level6_parallel_build/LaserMission.exe
.venv-unity\Scripts\python -m laser.level6_eval --build runs/level6_parallel_build/LaserMission.exe
.venv-unity\Scripts\python -m laser.level6_eval --build runs/level6_parallel_build/LaserMission.exe --root runs/laser/level6_redesign_warm --out runs/results/laser/level6_redesign_warm.json --init-policy runs/laser/specialists_rand2/ppo_level6_seed0/model.pt
.venv\Scripts\python -m laser.level6_report
# Unity에서 6단계만 직접 플레이
& runs/level6_release/LaserMission.exe -level 6
# 새 무작위 배치에서 DAgger 학생 관전
.venv-unity\Scripts\python -m laser.watch runs/laser/imitation/dagger_rand_h512_long_seed0/model.pt --campaign --procedural --build runs/level6_release/LaserMission.exe --level6-design 3 --view chase
```

표와 그래프는 `runs/results/laser/level6_redesign.md`, `level6_redesign.png`에 저장된다.

속도 제한만 바꾼 PPO 추가 학습을 비교하려면 `laser.level6_eval --speed-comparison`을 실행한다.
과거 결과에 덮어쓰지 않도록 `--root runs/laser/level6_speed_warm` 및
`--out runs/results/laser/level6_speed_warm.json`을 지정한다. 6단계에 PPO 전문 정책을 연결하는
후속 검증은 `python -m laser.level6_integration`으로 재현한다. 아래 관전 명령은 간격·폭을 바꾼 설계에서
6단계에만 PPO를 사용한다.

```powershell
.venv-unity\Scripts\python -m laser.watch runs/laser/imitation/dagger_rand_h512_long_seed0/model.pt --campaign --procedural --build runs/level6_release/LaserMission.exe --level6-design 2 --level6-policy runs/laser/level6_speed_warm/geometry_seed0/model.pt --view chase
```

### 충돌 예측을 쓰는 캠페인

Unity는 현재 레이저 배치에서 27개 후보 행동을 실제 이동·충돌 계산으로 시험하고, 다음 결정까지 충돌 없이 이어갈 수 있는 행동을 표시한다. 0.2초까지 안전한 행동이 없으면 0.1초 조건으로 좁히고, 그때도 선택지가 없으면 정책의 원래 행동 점수를 사용한다. 예측 도중 위치·속도·시간을 복원하며, 보상이나 충돌 횟수도 기록하지 않는다.

Python은 이 표시를 받아 정책 점수가 가장 높은 허용 행동을 선택한다. 신경망 입력은 기존 관측 66개다. 충돌 예측은 그 관측에 포함되지 않은 Unity 내부 상태도 사용하므로 순수 강화학습과 별도의 결과로 기록한다.

```powershell
# 4·5·6·7·9·10단계 예측을 켜고 관전
.venv-unity\Scripts\python -m laser.watch runs/laser/imitation/dagger_rand_h512_long_seed0/model.pt --campaign --procedural --build runs/action_safety_release/LaserMission.exe --level6-design 2 --level6-policy runs/laser/level6_speed_warm/geometry_seed0/model.pt --safety-horizon 2 --safety-levels 4 5 6 7 9 10 --view chase

# 동일 빌드와 시드에서 대조군 및 추가 학습 모델 평가
.venv-unity\Scripts\python -m laser.action_safety_eval --parallel 6
.venv-unity\Scripts\python -m laser.action_safety_eval --conditions several_stages_safety --eval-seed 99000 --out runs/results/laser/action_safety_confirmation.json
.venv-unity\Scripts\python -m laser.action_safety_eval --conditions include_stage7 --eval-seed 99000 --out runs/results/laser/action_safety_stage7.json

# 실제 행동과 예측 결과의 일치 검사
.venv-unity\Scripts\python -m tests.check_level6 --reference runs/level6_release/LaserMission.exe --candidate runs/action_safety_release/LaserMission.exe --check-safety
```

`--safety-horizon 0`은 기본 정책, `1`은 결정 한 번(0.1초), `2`는 두 번(0.2초)을 시험한다. `--safety-levels`로 적용할 단계를 지정한다. 캠페인 평가에서는 단계당 3회까지만 허용한다. 관전 모드에서는 단계 통과까지 새 배치에 계속 재도전한다.

### 회전 레이저의 벽 쪽 우회 수정

폭 8m인 방에서 캐릭터 중심은 중심선에서 좌우 3.7m까지 움직인다. 기존 회전 레이저의 반지름은 3.2m라서 캐릭터가 벽에 붙으면 빔의 충돌 거리 0.34m 밖에 있었다. 새 레이저는 방을 가로지를 때 양쪽 벽에 닿고, 회전 각도에 따라 빔 길이를 조정해 앞뒤 최대 범위는 중심 기준 3.2m로 제한한다. 화면, 충돌, 정책 관측, 충돌 예측 모두 같은 선분을 사용한다.

```powershell
# 수정판에서 직접 플레이
& .\runs\rotor_rebalance\LaserMission.exe -level 3

# 수정판의 AI 관전
.venv-unity\Scripts\python -m laser.watch runs/laser/imitation/dagger_rand_h512_long_seed0/model.pt --campaign --procedural --build runs/rotor_rebalance/LaserMission.exe --level6-design 2 --level6-policy runs/laser/level6_speed_warm/geometry_seed0/model.pt --safety-horizon 2 --safety-levels 4 5 6 7 9 10 --view chase

# 이전 실험과 동일한 조건으로 수정판 평가
.venv-unity\Scripts\python -m laser.action_safety_eval --conditions include_stage7 --build runs/rotor_rebalance/LaserMission.exe --eval-seed 99000 --out runs/results/laser/rotor_campaign_eval.json
```

Unity 에디터의 배치 실행에서 `LaserSolvabilityProbe.RunRotorAudit`를 `-rotor-audit-output <절대 CSV 경로>`와 함께 호출하면 가장자리 충돌, 점프·슬라이딩, 통과 경로 재생을 검사한다. `LaserSolvabilityProbe.RunLaserBoundsAudit`는 모든 단계의 레이저 끝점과 벽 통로 범위를 검사한다.

수정판 실행 파일을 다시 만들려면 같은 Unity 버전에서 `LaserBuild.BuildWindows`를 실행하고 `-laser-build-path`에 출력 실행 파일의 절대 경로를 지정한다.

### 리팩토링 빌드와 전체 재학습

`Room.cs`에는 이동·충돌과 에피소드 진행을 두고, 배치 생성·관측·화면은 `Room.Layouts.cs`, `Room.Observations.cs`, `Room.Visuals.cs`로 분리했다. 충돌 예측은 방의 운동 상태 복사본에서 계산한다. 학습용 배치 모드는 화면 오브젝트를 생성하지 않고, 관측 생성은 정렬용 리스트를 재사용한다.

`runs/laser_game_release/LaserMission.exe`를 실행하면 1단계에서 시작해 매번 새 배치를 생성한다. 사망 후 R로 재도전하고, 클리어 후 Enter로 다음 단계에 진입한다. 10단계에서 캠페인이 끝난다. 6단계 통로는 직접 플레이와 새 학습에서 설계 2를 사용한다. 같은 재도전 순서를 재현하려면 `-envseed 716`을, 예전 고정 배치 4종을 직접 비교하려면 `-fixed-campaign`을 사용한다.

```powershell
& .\runs\laser_game_release\LaserMission.exe

# 동일한 게임 규칙으로 만든 학습용 빌드에서 비교 실험 실행
.venv-unity\Scripts\python -m laser.experiments refactor refactor_curriculum --parallel 7 --build runs/laser_refactor_release/LaserMission.exe
.venv-unity\Scripts\python -m laser.campaign_eval --study refactor --parallel 6 --out runs/results/laser/refactor_results.json
.venv-unity\Scripts\python -m laser.campaign_eval --study refactor_curriculum --parallel 6 --out runs/results/laser/refactor_curriculum_results.json

# 완주용 6단계 PPO와 DAgger 재학습 및 홀드아웃 평가
.venv-unity\Scripts\python -m laser.retrain_campaign

# 검증 시드에서 선택한 완주용 구성 관전
.venv-unity\Scripts\python -m laser.watch runs/laser/retrained_campaign/dagger_seed0/model.pt --campaign --procedural --level6-design 2 --level6-policy runs/laser/retrained_campaign/ppo_seed0/model.pt --safety-horizon 2 --safety-levels 4 5 6 7 9 10 --view chase

# 관측·보상·종료 플래그의 회귀검사
.venv-unity\Scripts\python -m tests.check_level6 --all-stages --check-safety --reference runs/rotor_rebalance/LaserMission.exe --candidate runs/laser_refactor_release/LaserMission.exe
```

두 비교 실험은 PPO·SAC·Double DQN을 초기 가중치에서 시드당 1,048,576 환경 스텝씩 학습한다. 첫 조건은 레벨을 균등 추출하고, 둘째는 알고리즘마다 동일한 스텝 경계에서 레벨을 높이고 이전 단계를 복습한다. 두 조건 모두 학습과 평가에서 절차 생성 배치를 사용하고, 순차 평가에서는 단계당 3회 시도한다. 완주용 구성은 이전 체크포인트에서 출발해 추가 학습하며 실행 시 충돌 예측을 사용한다.

### 정책 후속 실험

1단계에서는 커리큘럼 PPO 가중치를 시드별로 불러와 엔트로피 계수 0.01과 0.04에서 각각 262,144스텝을 추가 학습했다. 개선된 1단계 정책은 개별 관전 명령으로 볼 수 있다. 6단계 예측 길이 실험은 별도 빌드에서 같은 PPO·DAgger 가중치에 0.2초와 0.3초 예측을 적용한다.

```powershell
.venv-unity\Scripts\python -m laser.watch runs/laser/level1_entropy/control_seed0/model.pt --level 1 --procedural --build runs/laser_game_release/LaserMission.exe --view chase
.venv-unity\Scripts\python -m laser.policy_followup entropy --build runs/laser_game_release/LaserMission.exe
.venv-unity\Scripts\python -m laser.policy_followup horizon --build runs/laser_horizon_trial/LaserMission.exe
.venv-unity\Scripts\python -m laser.policy_followup horizon --build runs/laser_horizon_trial/LaserMission.exe --campaign-attempts 1
```

6단계에서 0.3초 예측으로 관전하려면 아래 명령을 실행한다. 실험 빌드가 자동으로 선택된다. 캠페인 관전의 기본 예측은 0.2초다.

```powershell
.venv-unity\Scripts\python -m laser.watch runs/laser/retrained_campaign/ppo_seed0/model.pt --level 6 --procedural --level6-design 2 --safety-horizon 2 --stage6-safety-horizon 3 --view chase
```

3단계에도 0.2초 예측을 켜면 첫 시도 성능이 개선됐다. 아래 캠페인 관전 설정은 그 조합을 사용한다. 평가 명령은 단계당 한 번과 최대 세 번의 시도 결과를 별도 JSON에 저장한다.

```powershell
.venv-unity\Scripts\python -m laser.watch runs/laser/retrained_campaign/dagger_seed0/model.pt --campaign --procedural --level6-design 2 --level6-policy runs/laser/retrained_campaign/ppo_seed0/model.pt --safety-horizon 2 --safety-levels 3 4 5 6 7 9 10 --view chase
.venv-unity\Scripts\python -m laser.policy_followup stage3 --build runs/laser_game_release/LaserMission.exe --campaign-attempts 1
.venv-unity\Scripts\python -m laser.policy_followup stage3 --build runs/laser_game_release/LaserMission.exe
```
