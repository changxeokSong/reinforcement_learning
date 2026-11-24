// 레이저 미션 발표 자료: 단계별 개선 과정
// 실행: npm install pptxgenjs@3.12.0 → node tools/build_presentation.js (APPLY_THEME에 apply_theme.js 경로)
const pptxgen = require("pptxgenjs");
const path = require("path");
// 테마 색 적용: pptx 스킬의 apply_theme.js (없으면 주석 처리해도 색 이름만 Office 기본으로 남는다)
const { applyTheme } = require(process.env.APPLY_THEME || "./apply_theme.js");

const REPO = path.resolve(__dirname, "..");
const FIG = REPO + "/docs/figures/";
const HERE = __dirname;
const OUT = REPO + "/docs/LaserMission_presentation.pptx";

const THEME = {
  name: "Laser Mission",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "1B1B2A", lt1: "FFFFFF", dk2: "0D1B2A", lt2: "EEF1F5",
    accent1: "E5383B", accent2: "1FA99B", accent3: "4361EE", accent4: "F4A261",
    accent5: "8D99AE", accent6: "7B2CBF", hlink: "4361EE", folHlink: "7B2CBF",
  },
};
const HEX = { red: "E5383B", teal: "1FA99B", blue: "4361EE", orange: "F4A261", gray: "8D99AE", purple: "7B2CBF",
              navy: "0D1B2A", ink: "1B1B2A", light: "EEF1F5", grid: "D9DEE5" };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";               // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "레이저 미션: 강화학습에서 모방 학습까지";
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28, w: 9.0, h: 0.62, fontSize: 26, bold: true,
                                 color: C.text2, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "레이저 미션 · 강화학습 팀 프로젝트", options: { x: 0.5, y: 5.22, w: 5, h: 0.25, fontSize: 9, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.4, h: 0.28, fontSize: 9, color: C.accent5, align: "right" },
});
pres.defineSlideMaster({
  title: "DARK",
  background: { color: HEX.navy },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.35, w: 9.0, h: 0.7, fontSize: 28, bold: true,
                                 color: C.background1, valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.4, h: 0.28, fontSize: 9, color: C.accent5, align: "right" },
});

let n = 0;
function content(title, section, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  s.addNotes(notes);
  return s;
}
function txt(s, text, o) { s.addText(text, { isTextBox: true, margin: 0, fontSize: 14, color: C.text1, valign: "top", ...o }); }
function card(s, x, y, w, h, fill, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill }, objectName: name });
}
function stepBadge(s, label, x, y, color) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color }, objectName: "badge " + label });
  s.addText(label, { isTextBox: true, x, y, w: 0.42, h: 0.42, align: "center", valign: "middle", fontSize: 14, bold: true, color: C.background1, margin: 0 });
}
// 제출 전에 팀원 학번·이름을 채운다.
const TEAM = [["학번 확인 중", "팀원 1"], ["학번 확인 중", "팀원 2"], ["학번 확인 중", "팀원 3"]];
const GITHUB = "https://github.com/changxeokSong/reinforcement_learning";
// 순수 강화학습 정책 하나의 최고 기록 (처음 보는 배치, 1~10단계 평균)
const PURE_RL = "79%";
function table(s, rows, o, fontSize = 11) {
  const head = rows[0].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.navy }, fontSize, align: "center" } }));
  const body = rows.slice(1).map((r) => r.map((t, i) => ({ text: t, options: { fontSize, color: C.text1, fill: { color: HEX.light }, align: i === 0 ? "left" : (o.alignBody || "center"), bold: i === 0 } })));
  s.addTable([head, ...body], { border: { type: "solid", pt: 1.5, color: "FFFFFF" }, margin: 0.05, valign: "middle", ...o });
}
function bullets(s, lines, o) {
  s.addText(lines.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < lines.length - 1 } })),
    { isTextBox: true, fontSize: 12, color: C.text1, paraSpaceAfter: 6, valign: "top", margin: 0, ...o });
}
const LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"];
const chartBase = (title) => ({
  showTitle: false, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  catAxisLabelColor: "555B66", valAxisLabelColor: "555B66", catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  valAxisMaxVal: 100, valAxisMinVal: 0, valAxisMajorUnit: 25, valAxisLabelFormatCode: "0\"%\"",
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" },
  showLegend: true, legendPos: "t", legendFontSize: 10, barGapWidthPct: 40,
});

// ---------------------------------------------------------------- 1. 표지
pres.addSection({ title: "시작" });
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "시작" });
  s.addImage({ path: FIG + "laser_title.jpg", x: 0, y: 0, w: 10, h: 5.625, objectName: "game screenshot" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 5.625, fill: { color: HEX.navy, transparency: 35 }, line: { color: HEX.navy, transparency: 100 }, objectName: "overlay" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.45, y: 1.35, w: 6.4, h: 2.75, rectRadius: 0.1, fill: { color: HEX.navy, transparency: 15 }, line: { color: HEX.navy, transparency: 100 }, objectName: "title card" });
  txt(s, "레이저 미션", { x: 0.8, y: 1.6, w: 5.8, h: 0.8, fontSize: 40, bold: true, color: C.background1 });
  txt(s, "강화학습과 모방 학습으로\n정책 하나가 10단계를 완주하기까지", { x: 0.8, y: 2.45, w: 5.8, h: 0.95, fontSize: 18, color: C.background1 });
  txt(s, "Unity 3D 환경 직접 제작 · PPO / DQN / SAC · Behavior Cloning / DAgger", { x: 0.8, y: 3.55, w: 5.8, h: 0.35, fontSize: 11, color: "CADCFC" });
  txt(s, TEAM.map(([id, name]) => `${id} ${name}`).join("   ·   "), { x: 0.5, y: 4.45, w: 9.0, h: 0.3, fontSize: 13, bold: true, color: C.background1 });
  txt(s, GITHUB, { x: 0.5, y: 4.8, w: 9.0, h: 0.28, fontSize: 11, color: "CADCFC", hyperlink: { url: GITHUB } });
  s.addNotes("알바트로스가 움직이는 레이저를 피해 금고까지 가는 3D 미션을 Unity로 직접 만들고, 강화학습과 모방 학습으로 풀었다. 오늘은 처음 실패부터 최종 완주까지 단계별로 무엇을 확인하고 무엇을 고쳤는지 순서대로 설명한다.");
}

// ---------------------------------------------------------------- 2. 한 장 요약
{
  const s = content("한 장 요약: 0번 완주에서 1,200번 완주까지", "시작",
    "결론부터 말하면, 강화학습 정책 하나로는 고정 배치 10단계를 한 번도 완주하지 못했고, 원인을 하나씩 찾아 고쳐서 마지막에는 정책 하나가 단계당 한 번의 시도만으로 1,200번 모두 완주했다(위 다섯 단계). 아래 세 줄은 그 뒤에 한 일이다. 하이퍼파라미터를 탐색하고 새 seed로 확인해 알고리즘 순위와 순수 강화학습 성능을 다시 쟀고, 처음 보는 배치에서 학습된 정책과 실행 시 충돌 예측의 기여를 나눠 보고했다.");
  const steps = [
    ["1", "강화학습\n정책 하나", "0 / 600", "10단계 완주", HEX.red],
    ["2", "한 단계만\n학습한 PPO", "100%", "그 단계만 · 나머지는 망각", HEX.orange],
    ["3", "모방 학습\n(BC · DAgger)", "361 / 600", "10단계 완주", HEX.blue],
    ["4", "약한 단계\n선생님 재학습", "600 / 600", "단계당 3번 시도", HEX.purple],
    ["5", "통과 경로\n시범 추가", "1,200 / 1,200", "단계당 1번 시도", HEX.teal],
  ];
  const w = 1.66, gap = 0.17;
  steps.forEach(([k, name, big, small, color], i) => {
    const x = 0.5 + i * (w + gap);
    card(s, x, 1.05, w, 2.7, HEX.light, "step card " + k);
    stepBadge(s, k, x + 0.15, 1.17, color);
    txt(s, name, { x: x + 0.15, y: 1.65, w: w - 0.3, h: 0.7, fontSize: 13, bold: true, color: C.text2 });
    txt(s, big, { x: x + 0.1, y: 2.4, w: w - 0.2, h: 0.55, fontSize: big.length > 9 ? 15 : 20, bold: true, color, align: "center", valign: "middle" });
    txt(s, small, { x: x + 0.1, y: 2.98, w: w - 0.2, h: 0.7, fontSize: 10.5, color: "555B66", align: "center" });
  });
  const facts = [
    ["알고리즘 비교 (seed 5개)", "기본값: PPO ≈ SAC > DQN\n튜닝 후: SAC 33% > PPO 18% > DQN 5%", HEX.blue],
    ["순수 강화학습 정책 하나", "하이퍼파라미터 탐색 · 긴 학습\n13% → " + PURE_RL + " (처음 보는 배치 평균)", HEX.purple],
    ["처음 보는 배치 10단계 완주", "학습만: PPO 하나 44% · 모방 학습 60%\n+ 0.2초 충돌 예측: 100% · 99.8%", HEX.teal],
  ];
  facts.forEach(([h, b, color], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 3.9, 2.9, 1.05, "FFFFFF", "fact " + i);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.9, w: 0.07, h: 1.05, fill: { color }, line: { color } });
    txt(s, h, { x: x + 0.18, y: 3.95, w: 2.65, h: 0.3, fontSize: 11.5, bold: true, color });
    txt(s, b, { x: x + 0.18, y: 4.27, w: 2.65, h: 0.65, fontSize: 10 });
  });
}

// ---------------------------------------------------------------- 2-1. 주제와 목표
{
  const s = content("주제와 목표", "시작",
    "기존 벤치마크 대신 3D 미션 게임을 직접 만들었다. 대결형인 배구와 달리 혼자 푸는 미션형이고, 실패하면 바로 끝나며 보상이 드물다. 단계를 10개로 늘리면서 생긴 문제(망각, 희소 보상, 배치 암기)를 하나씩 확인하고, 강화학습과 모방 학습으로 풀었다. 아래 네 질문에 실험으로 답한다.");
  card(s, 0.5, 1.1, 4.3, 3.85, HEX.light, "goal card");
  txt(s, "문제", { x: 0.7, y: 1.22, w: 3.9, h: 0.35, fontSize: 15, bold: true, color: C.accent1 });
  bullets(s, [
    "알바트로스가 움직이는 레이저를 피해 금고까지 간다",
    "1~10단계 캠페인. 단계가 오를수록 레이저 벽·회전 막대·점멸 벽이 늘어난다",
    "목표: 정책 하나로 1~10단계를 순서대로 완주",
    "환경은 Unity 6 + ML-Agents로 직접 제작. 알고리즘은 PyTorch로 직접 구현",
  ], { x: 0.7, y: 1.65, w: 3.95, h: 3.2, fontSize: 12 });
  const qs = [
    ["Q1", "같은 조건에서 PPO · Double DQN · 이산 SAC 중 무엇이 잘 배우는가? 비교 기준(스텝, 시간)에 따라 달라지는가?"],
    ["Q2", "레벨 구성 방식(커리큘럼, 복습, 무작위)과 관측·보상 설계가 성공률을 바꾸는가?"],
    ["Q3", "정책 하나로 10단계를 못 깨는 원인은 무엇이고, 모방 학습(BC · DAgger)으로 해결되는가?"],
    ["Q4", "처음 보는 배치에서도 통하는가? 일반화를 막는 것은 무엇인가?"],
  ];
  qs.forEach(([k, q], i) => {
    const y = 1.1 + i * 0.97;
    stepBadge(s, k, 5.05, y + 0.18, [HEX.blue, HEX.teal, HEX.purple, HEX.orange][i]);
    txt(s, q, { x: 5.6, y, w: 3.9, h: 0.85, fontSize: 12, valign: "middle" });
  });
}

// ---------------------------------------------------------------- 3. 환경
pres.addSection({ title: "환경" });
{
  const s = content("직접 만든 3D 환경: 레이저를 피해 금고까지", "환경",
    "Unity로 직접 만들었고 ML-Agents로 파이썬과 연결했다. 물리 엔진 없이 위치와 충돌을 직접 계산해서, 같은 seed면 결과가 같고 한 프로세스에 방 16개를 넣어 초당 약 1만 5천 스텝을 낸다. 1~10단계마다 배치가 4개씩 있고, 실패하면 같은 단계의 다른 배치로 재도전한다.");
  s.addImage({ path: FIG + "laser_top_view.jpg", x: 0.75, y: 1.1, w: 3.4, h: 2.85, objectName: "top view" });
  txt(s, "5단계 위에서 본 모습: 통로가 움직이는 레이저 벽, 겹친 레이저, 회전 막대", { x: 0.75, y: 4.05, w: 3.4, h: 0.5, fontSize: 10, color: "555B66" });
  const rows = [
    ["상태", "연속값 66개: 자신 11개 + 가까운 레이저 5개 × 11개 (종류, 가장 가까운 지점, 속도, 깜빡임 남은 시간)"],
    ["행동", "이산 27개: 좌우 3 × 앞뒤 3 × (없음 / 점프 / 슬라이딩)"],
    ["보상", "금고 +1, 레이저 −1, 시간 초과 −1, 매 0.1초 −0.01, 금고 쪽 이동 × 0.5"],
    ["종료", "성공 · 레이저 접촉 · 20초 초과 (결정 한 번 = 0.1초)"],
    ["단계", "1~10단계, 단계마다 배치 4개. 10단계 연속 통과가 목표"],
  ];
  s.addTable(rows.map(([a, b]) => [
    { text: a, options: { bold: true, color: C.background1, fill: { color: HEX.navy }, fontSize: 12, valign: "middle", align: "center" } },
    { text: b, options: { color: C.text1, fill: { color: HEX.light }, fontSize: 11, valign: "middle" } },
  ]), { x: 4.7, y: 1.1, w: 4.8, colW: [0.75, 4.05], rowH: 0.62, border: { type: "solid", pt: 1.5, color: "FFFFFF" }, margin: 0.06 });
}

// ---------------------------------------------------------------- 3-1. 단계 구성
{
  const s = content("1~10단계 구성: 장애물이 하나씩 늘어난다", "환경",
    "단계마다 장애물 조합이 다르다. 캠페인에서는 단계마다 출발 위치, 레이저 위치, 속도, 점멸 타이밍이 다른 배치 4개 중 하나가 나온다. 무작위 배치 모드에서는 판마다 수치를 새로 뽑는다. 모든 단계가 풀 수 있는지 빔 탐색으로 통과 경로를 찾아 실제 게임 행동으로 재생해 확인했다(고정 배치 40/40, 무작위 배치 299/300).");
  table(s, [
    ["단계", "레이저 구성", "핵심 기술"],
    ["1", "고정된 가로 막대 2개", "낮으면 점프, 높으면 슬라이딩"],
    ["2", "가로 막대 + 좌우로 쓸고 가는 세로 막대 + 앞뒤 이동 막대", "좌우 회피"],
    ["3", "가로 · 세로 · 회전 · 깜빡이는 막대를 하나씩", "타이밍"],
    ["4", "무작위 종류 5개, 속도 1.3배", "조합"],
    ["5", "겹친 레이저 2곳 + 통로가 움직이는 레이저 벽 2곳 + 회전 · 깜빡임", "통로 찾기"],
    ["6", "반대 위상 이중 벽, 좁은 통로 벽, 잠깐 꺼지는 전폭 벽, 빠른 회전", "정밀한 대기"],
    ["7", "좁게 움직이는 통로 3곳 + 회전 막대 + 좌우 레이저", "통로 추적"],
    ["8", "방 전체를 막았다가 열리는 점멸 벽 3곳 (열리는 시간이 다름)", "기다리기"],
    ["9", "반대로 움직이는 통로 두 쌍 + 이동 막대 + 점멸 벽", "통로 전환"],
    ["10", "이중 통로, 좁은 통로, 회전 · 좌우 레이저, 시작과 끝의 점멸 벽", "전부"],
  ], { x: 0.5, y: 1.05, w: 9.0, colW: [0.7, 6.0, 2.3], rowH: 0.36, alignBody: "left" }, 10.5);
}

// ---------------------------------------------------------------- 3-2. State · 전처리
{
  const s = content("State 설계와 전처리: 66개 연속값", "환경",
    "별도 데이터셋 없이 Unity가 만든 전이로 학습한다. 관측은 방 크기와 이동 속도로 정규화해 대부분 −1~1 범위에 둔다. 레이저는 종류를 원-핫으로 넣고, 선분 전체 대신 에이전트에게 가장 가까운 지점과 그 지점의 속도를 준다. 레이저 수가 단계마다 달라서 가까운 순서(앞쪽 우선)로 5개만 고정 길이로 넣는다. 깜빡이는 레이저는 언제 바뀌는지 모르면 Markov가 아니므로 전환까지 남은 시간을 넣었다. 정책이 레이저 5개만 보므로 엄밀히는 부분 관측이다.");
  table(s, [
    ["구분", "값", "개수"],
    ["자신", "위치 x·z, 속도 x·y·z, 높이, 슬라이딩 남은 비율, 착지 여부, 경과 시간, 레벨, 금고까지 거리", "11"],
    ["레이저 (× 5)", "종류 원-핫 4, 가장 가까운 지점의 상대 x·높이·상대 z, 그 지점의 속도 x·z, 켜짐, 깜빡임 전환까지 남은 시간", "11 × 5 = 55"],
  ], { x: 0.5, y: 1.05, w: 9.0, colW: [1.4, 6.3, 1.3], rowH: 0.62, alignBody: "left" }, 11);
  const pre = [
    ["정규화", "위치는 방 크기, 속도는 최대 속도로 나눔"],
    ["고정 길이", "가까운 순서로 레이저 5개. 부족하면 0으로 채움"],
    ["Markov 보완", "깜빡임 전환까지 남은 시간, 경과 시간 추가"],
    ["검증", "관측 설계 vs 원시 선분 좌표 비교 (X3)"],
  ];
  pre.forEach(([h, b], i) => {
    const x = 0.5 + i * 2.27;
    card(s, x, 3.2, 2.12, 1.7, HEX.light, "pre " + h);
    txt(s, h, { x: x + 0.12, y: 3.3, w: 1.9, h: 0.35, fontSize: 13, bold: true, color: C.accent3 });
    txt(s, b, { x: x + 0.12, y: 3.7, w: 1.9, h: 1.1, fontSize: 11 });
  });
}

// ---------------------------------------------------------------- 3-3. Action · Reward
{
  const s = content("Action · Reward · 종료 조건", "환경",
    "행동은 이산 27개로 세 알고리즘이 같은 행동 공간을 쓴다. 보상은 도착 +1, 실패 −1이 핵심이고, 매 결정 −0.01 시간 벌점과 금고 쪽으로 다가간 거리 보상(출발부터 도착까지 합 0.5)을 더했다. 할인율 0.99에서 반감 시간은 약 6.9초이고, 성공 경로는 5~12초라서 도착 보상이 충분히 앞까지 전달된다. 20초 시간 초과는 게임 규칙이라 terminated로 처리하고 −1을 준다. 외부 중단만 truncated다.");
  card(s, 0.5, 1.1, 4.35, 1.75, HEX.light, "action card");
  txt(s, "Action: 이산 27개", { x: 0.7, y: 1.2, w: 4.0, h: 0.35, fontSize: 14, bold: true, color: C.accent3 });
  txt(s, "좌우 3 × 앞뒤 3 × (없음 / 점프 / 슬라이딩) 3\n결정 한 번 = 시뮬레이션 0.1초\n슬라이딩은 한 번 누르면 0.6초 지속 (탐험으로 찾기 쉽게)", { x: 0.7, y: 1.6, w: 4.0, h: 1.2, fontSize: 11 });
  card(s, 0.5, 3.05, 4.35, 1.9, HEX.light, "done card");
  txt(s, "종료", { x: 0.7, y: 3.15, w: 4.0, h: 0.35, fontSize: 14, bold: true, color: C.accent3 });
  txt(s, "terminated: 금고 도착 · 레이저 접촉 · 20초 경과\ntruncated: 외부 평가 한도로 중단 (ML-Agents interrupted)\nγ = 0.99 → 5초 뒤 0.61, 10초 뒤 0.37", { x: 0.7, y: 3.55, w: 4.0, h: 1.3, fontSize: 11 });
  table(s, [
    ["보상 항목", "값", "이유"],
    ["금고 도착", "+1", "목표"],
    ["레이저 접촉", "−1", "실패"],
    ["시간 초과 (20초)", "−1", "0점이면 레이저 앞에서 버티는 게 안전해진다"],
    ["매 결정", "−0.01", "먼 −1은 할인으로 거의 0이라 버티기를 막지 못했다"],
    ["다가간 거리", "합 0.5", "출발 직후 학습 신호 (X4에서 제거해도 비슷)"],
  ], { x: 5.1, y: 1.1, w: 4.4, colW: [1.25, 0.7, 2.45], rowH: 0.6, alignBody: "left" }, 10.5);
}

// ---------------------------------------------------------------- 4. 학습이 되게 만들기
{
  const s = content("처음에는 성공률 0: 원인을 하나씩 찾아 고쳤다", "환경",
    "처음 설계로는 학습이 전혀 되지 않았다. 레벨 1은 '낮으면 점프, 높으면 슬라이딩' 규칙으로 100% 통과할 수 있어서, 실패가 환경 탓인지 학습 탓인지 가리는 기준으로 썼다. 다만 나중에 seed 3개로 다시 비교하니 관측·보상 수정의 효과는 대부분 신뢰구간 안이었다. 짧은 학습과 seed 1개로 판단했기 때문이고, 10장의 '한 seed로 결론 내지 않기'를 직접 겪은 사례다.");
  const head = ["증상", "원인", "고친 것", "레벨 1"].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.navy }, fontSize: 12, align: "center" } }));
  const rows = [
    ["레이저 앞에서 멈춤", "시간 초과가 0점 → 버티는 게 안전", "시간 초과 −1", "0%"],
    ["여전히 버팀", "할인율 0.99에서 먼 −1은 거의 0", "매 0.1초 −0.01 시간 벌점", "약 10%"],
    ["무조건 점프만", "숙이기를 4번 연속 눌러야 함", "한 번 누르면 0.6초 슬라이딩", "약 25%"],
    ["25%에서 정체", "낮은/높은 레이저 차이가 관측에서 작음", "레이저 종류·실제 높이를 관측에", "약 90%"],
    ["깜빡이 레이저 실패", "언제 꺼질지 알 수 없음 (Markov 아님)", "전환까지 남은 시간 추가", "반영"],
  ].map((r) => r.map((t, i) => ({ text: t, options: { fontSize: 11, color: C.text1, fill: { color: HEX.light }, align: i === 3 ? "center" : "left", bold: i === 3 } })));
  s.addTable([head, ...rows], { x: 0.5, y: 1.1, w: 9.0, colW: [1.7, 3.0, 3.1, 1.2], rowH: 0.5, border: { type: "solid", pt: 1.5, color: "FFFFFF" }, margin: 0.07, valign: "middle" });
  card(s, 0.5, 4.3, 9.0, 0.72, "FCE8E8", "lesson card");
  txt(s, "seed 3개로 다시 비교하니 관측·보상 수정 효과는 대부분 신뢰구간 안이었다. 개선은 반드시 여러 seed로 다시 확인한다 (10장).", { x: 0.7, y: 4.4, w: 8.6, h: 0.55, fontSize: 12, color: C.text1, valign: "middle" });
}

// ---------------------------------------------------------------- 4-1. 알고리즘
pres.addSection({ title: "알고리즘 · 실험 설계" });
{
  const s = content("직접 구현한 세 알고리즘", "알고리즘 · 실험 설계",
    "세 알고리즘 모두 라이브러리 없이 PyTorch로 직접 구현했다(algos/ppo.py, dqn.py, sac.py). 배구와 레이저가 같은 코드를 쓴다. 정책 기반 on-policy(PPO), 가치 기반 off-policy(DQN), 최대 엔트로피 off-policy(SAC)로 성격이 다른 세 가지를 골랐다. SAC는 원래 연속 행동용이라, 행동이 27개뿐인 점을 이용해 정책 기댓값을 샘플 대신 정확한 합으로 계산하는 이산 버전을 썼다. 레이저에서는 Q값 발산 때문에 기울기 상한과 Bellman 목표값 범위 제한(±3)을 옵션으로 추가했다.");
  const cols = [
    ["PPO", "on-policy · 정책 경사", HEX.blue, ["clipped surrogate (ε = 0.2)", "GAE (λ = 0.95)로 advantage 추정", "16개 방에서 256스텝씩 모아 4 epoch 갱신", "엔트로피 보너스 0.01, 학습률 선형 감소"]],
    ["Double DQN", "off-policy · 가치 기반", HEX.gray, ["온라인 망이 행동 선택, 타깃 망이 평가 (과대추정 완화)", "재생 버퍼 50만, soft target τ = 0.005", "Huber 손실", "ε-greedy 1.0 → 0.05 (전체의 30%)"]],
    ["이산 SAC", "off-policy · 최대 엔트로피", HEX.teal, ["Q 두 개 중 작은 값 사용 (twin Q)", "정책 기댓값을 27개 행동에 대해 정확히 합산", "목표 엔트로피 = 0.3 × ln 27, α 자동 조절", "레이저 전용: 기울기 상한 10, 목표값 ±3"]],
  ];
  cols.forEach(([h, sub, color, lines], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.1, 2.9, 3.85, HEX.light, h + " card");
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.1, w: 2.9, h: 0.08, fill: { color }, line: { color }, objectName: h + " bar" });
    txt(s, h, { x: x + 0.18, y: 1.3, w: 2.6, h: 0.4, fontSize: 17, bold: true, color });
    txt(s, sub, { x: x + 0.18, y: 1.72, w: 2.6, h: 0.3, fontSize: 11, color: "555B66" });
    bullets(s, lines, { x: x + 0.18, y: 2.15, w: 2.6, h: 2.7, fontSize: 11.5 });
  });
}

// ---------------------------------------------------------------- 4-2. 하이퍼파라미터
{
  const s = content("하이퍼파라미터: 공통 값은 같게", "알고리즘 · 실험 설계",
    "비교의 공정성을 위해 할인율, 학습률, 신경망 크기, 환경 설정, 학습 스텝, 평가 방법을 세 알고리즘에 똑같이 맞췄다. 알고리즘 고유 설정은 각 논문의 기본값에 가깝게 두었다. 모든 값은 실행마다 config.json에 저장된다. 레이저 전용으로 바꾼 것은 SAC의 기울기 상한과 목표값 범위뿐이고, 이것도 X6·X7에서 따로 비교했다.");
  table(s, [
    ["공통", "값"],
    ["할인율 γ", "0.99"],
    ["학습률", "3 × 10⁻⁴ (Adam)"],
    ["신경망", "66 → 256 → 256 → 27"],
    ["병렬 방", "16개 (한 Unity 프로세스)"],
    ["학습 스텝", "1~4단계 400만, 10단계 1,200만"],
    ["커리큘럼", "최근 300판 성공률 0.8 이상이면 승급, 레벨 2부터 50% 복습"],
    ["최종 빌드 비교", "은닉 128 · DQN · SAC 16스텝마다 갱신 · 105만 스텝. 튜닝 후 PPO 학습률 1e-3, SAC 4스텝마다"],
  ], { x: 0.5, y: 1.05, w: 4.3, colW: [1.3, 3.0], rowH: 0.47, alignBody: "left" }, 10.5);
  table(s, [
    ["알고리즘", "고유 설정"],
    ["PPO", "n_steps 256 · epoch 4 · minibatch 4 · clip 0.2 · GAE λ 0.95 · 엔트로피 0.01 · value 0.5 · grad norm 0.5"],
    ["Double DQN", "버퍼 50만 · batch 256 · 4스텝마다 갱신 · τ 0.005 · ε 1.0→0.05 (30%) · 시작 1만 스텝"],
    ["이산 SAC", "버퍼 50만 · batch 256 · 4스텝마다 갱신 · τ 0.005 · 목표 엔트로피 0.3·ln27 · 초기 α 0.2 · 기울기 상한 10 · 목표값 ±3"],
  ], { x: 5.0, y: 1.05, w: 4.5, colW: [1.15, 3.35], rowH: 0.8, alignBody: "left" }, 10.5);
}

// ---------------------------------------------------------------- 4-3. 구현 검증
{
  const s = content("구현 검증: 알고리즘과 환경을 따로 확인", "알고리즘 · 실험 설계",
    "학습이 안 될 때 알고리즘 버그인지 환경 문제인지 가르기 위해 둘을 따로 검증했다. 알고리즘은 CartPole-v1에서 세 개 모두 평균 리턴 195 이상을 확인했다. 환경은 규칙 정책 기준선, 통과 경로 탐색, 빌드 회귀 검사로 확인했다. 실험 실행기는 Unity 빌드 전체의 SHA-256 지문으로 빌드를 식별하고, 평가 때 Unity가 돌려준 실제 레벨을 검사한다. 이 검사 덕분에 레벨 5 요청이 레벨 4로 실행되던 X8 초기 오류를 찾아 결과에서 뺐다.");
  const items = [
    ["알고리즘", HEX.blue, ["CartPole-v1: PPO · DQN · SAC 모두 평균 리턴 195 이상 (tests/check_algos.py)", "무작위 행동 기준선: 모든 단계 0%"]],
    ["환경", HEX.teal, ["1단계 규칙 정책(낮으면 점프, 높으면 슬라이딩) 100% 통과", "빔 탐색으로 단계마다 통과 경로 확인: 고정 배치 40/40, 무작위 배치 299/300", "잠재함수 보상 · 종료 플래그 계산 확인 (tests/check_laser.py)"]],
    ["빌드 · 재현", HEX.purple, ["코드 정리 전후 28,160개 전이에서 관측 · 보상 · 종료가 일치", "빌드 내용 지문(SHA-256)으로 실험마다 빌드 기록", "평가 시 실제 레벨 확인 → X8 초기 레벨 오류 발견 · 제외"]],
  ];
  items.forEach(([h, color, lines], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.1, 2.9, 3.85, HEX.light, h + " card");
    txt(s, h, { x: x + 0.18, y: 1.25, w: 2.6, h: 0.4, fontSize: 16, bold: true, color });
    bullets(s, lines, { x: x + 0.18, y: 1.8, w: 2.6, h: 3.05, fontSize: 11.5 });
  });
}

// ---------------------------------------------------------------- 4-4. 실험 셋업 · 평가 지표
{
  const s = content("실험 셋업과 평가 지표", "알고리즘 · 실험 설계",
    "통계 단위는 학습 seed다. 한 모델의 200판은 그 seed의 성공률 하나를 정확히 재는 데 쓰고, 신뢰구간은 seed n개의 값으로 t 분포를 써서 계산한다. 그래서 200판을 표본 200개로 세지 않는다. 평가 환경 seed는 학습과 검증(선생님 고르기)에 쓰지 않은 값이다. 학습 시간은 같은 PC에서 여러 실행을 동시에 돌린 기준이라, 절대값보다 상대 비교로 본다.");
  table(s, [
    ["항목", "설정"],
    ["PC", "Intel i7-13700KF · RAM 64GB · GTX 1660 (학습은 CPU)"],
    ["소프트웨어", "Unity 6000.0 · ML-Agents · Python 3.10 · PyTorch 2"],
    ["학습 seed", "기본 0 · 1 · 2, 최종 비교 0~4, 확인 실험 3~7"],
    ["평가 seed", "학습 · 검증과 분리 (예: 검증 77000, 평가 123456)"],
    ["평가 판 수", "레벨마다 200판, 가장 점수 높은 행동"],
    ["동시 실행", "실험 6~8개를 동시에"],
  ], { x: 0.5, y: 1.05, w: 4.6, colW: [1.25, 3.35], rowH: 0.47, alignBody: "left" }, 10.5);
  table(s, [
    ["지표", "정의"],
    ["단계별 성공률", "금고 도착 판 / 200판"],
    ["1~10단계 평균", "단계별 성공률의 평균"],
    ["10단계 완주율", "순차 캠페인 200회 중 완주. 단계당 최대 3번 (또는 1번) 시도"],
    ["실패 유형", "충돌 · 시간 초과 비율"],
    ["95% 신뢰구간", "seed별 값의 평균 ± t(0.975, n−1) · s/√n"],
  ], { x: 5.3, y: 1.05, w: 4.2, colW: [1.35, 2.85], rowH: 0.55, alignBody: "left" }, 10.5);
}

// ---------------------------------------------------------------- 4-5. 실험 목록
{
  const s = content("실험 목록", "알고리즘 · 실험 설계",
    "실험은 질문 순서대로 진행했다. X1~X7은 1~4단계에서 알고리즘과 설계를 비교했고, X8~X13은 단계를 10개로 늘리며 생긴 문제를 다뤘다. 이후 모방 학습, 일반화, 6단계 설계 수정과 충돌 예측을 실험했다. 기본은 seed 3개이고, 최종 비교와 확인 실험은 seed 5개다. 명령 한 줄로 다시 돌릴 수 있고(laser.experiments), 결과 표와 그래프는 laser.report가 만든다.");
  table(s, [
    ["실험", "비교", "질문"],
    ["X1", "PPO vs Double DQN vs SAC (1~4단계, 400만 스텝)", "Q1"],
    ["X2", "커리큘럼 / 커리큘럼 + 복습 / 레벨 무작위 / 처음부터 레벨 4", "Q2"],
    ["X3 · X4", "관측: 설계한 특징 vs 원시 좌표 · 보상: 시간 벌점, 다가가기 보상 제거", "Q2"],
    ["X5", "PPO 학습량 400만 vs 2,000만 스텝 (같은 시간 비교)", "Q1"],
    ["X6 · X7", "SAC 안정화: 기울기 상한 · Bellman 목표값 범위", "Q1"],
    ["X8 ~ X12", "레벨 5 · 6 · 10단계로 확장, 세 알고리즘 1,200만 스텝", "Q3"],
    ["X13", "PPO 정책 하나에 모방 학습과 같은 예산 5,250만 스텝", "Q3"],
    ["모방 학습", "BC vs DAgger · 학생 크기 64 / 256 / 512 · 선생님 PPO vs SAC · 시범", "Q3"],
    ["일반화", "고정 배치 4개 vs 판마다 새 배치", "Q4"],
    ["새 빌드", "세 알고리즘 재비교 (무작위 vs 커리큘럼, seed 5개) · 6단계 설계 수정 · 충돌 예측", "Q1 · Q4"],
    ["H · C", "하이퍼파라미터 32개 설정 × seed 3 탐색 → 새 seed 5개로 확인 · 같은 시간 비교", "Q1 · Q2"],
  ], { x: 0.5, y: 1.05, w: 9.0, colW: [1.3, 6.7, 1.0], rowH: 0.33, alignBody: "left" }, 10.5);
}

// ---------------------------------------------------------------- 5. 알고리즘 비교 (1~4단계)
pres.addSection({ title: "강화학습" });
{
  const s = content("1~4단계: 같은 스텝이면 SAC, 같은 시간이면 PPO", "강화학습",
    "레벨 1~4 평균 성공률, seed 3개. 기본 SAC는 seed 하나가 Q값 발산으로 0이 되었다. 로그에서 Q 손실이 44,000까지 치솟는 것을 보고 원인을 찾았고, 기울기 상한만으로는 부족했으며 보상이 유계라는 점을 이용해 Bellman 목표값을 ±3으로 자르자 세 seed 모두 안정되었다. PPO는 스텝을 늘리면 따라오지만 시간은 훨씬 짧다.");
  const data = [{ name: "평균 성공률", labels: ["SAC 안정화\n(400만, 180분)", "PPO\n(2000만, 57분)", "PPO\n(400만, 17분)", "SAC 기본\n(400만)", "DQN\n(400만)"], values: [93, 87, 66, 62, 40] }];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.05, w: 5.6, h: 3.9, barDir: "col", showLegend: false,
    chartColors: [HEX.teal, HEX.blue, "8FA3F5", "A7E3DC", HEX.gray], varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0\"%\"", dataLabelFontSize: 11, dataLabelColor: "1B1B2A", dataLabelFontFace: "+mn-lt", catAxisLabelFontSize: 9 });
  card(s, 6.35, 1.1, 3.15, 1.75, HEX.light, "sac card");
  txt(s, "SAC가 무너진 원인", { x: 6.55, y: 1.22, w: 2.8, h: 0.3, fontSize: 13, bold: true, color: C.accent1 });
  txt(s, "레벨이 오를 때 Q값 발산 (Q 손실 0.03 → 44,000). 목표값을 보상 범위(±3)로 잘라 0.62 → 0.93", { x: 6.55, y: 1.55, w: 2.8, h: 1.2, fontSize: 11 });
  card(s, 6.35, 3.05, 3.15, 1.85, HEX.light, "fair card");
  txt(s, "비교 기준이 결론을 바꾼다", { x: 6.55, y: 3.17, w: 2.8, h: 0.3, fontSize: 13, bold: true, color: C.accent3 });
  txt(s, "같은 스텝: SAC가 높다\n같은 시간: PPO가 효율적이다\n배구 실험(2인 대결)과 같은 결론", { x: 6.55, y: 3.5, w: 2.8, h: 1.3, fontSize: 11 });
}

// ---------------------------------------------------------------- 5-1. X2~X4
{
  const s = content("X2~X4: 학습 방식 · 관측 · 보상", "강화학습",
    "PPO, 400만 스텝, seed 3개, 레벨 1~4 평균 성공률 ± 95% 신뢰구간. 커리큘럼은 레벨 3을 오래 연습하는 동안 레벨 1을 잊었다(0.71). 레벨을 무작위로 섞으면 0.66으로 가장 좋았고, 처음부터 레벨 4만 하면 성공 경험이 드물어 0.42였다. 관측과 보상 수정은 설계할 때 큰 효과로 보였지만 seed 3개로 다시 재면 차이가 신뢰구간 안이었다.");
  s.addImage({ path: FIG + "laser_x2_training.png", x: 0.5, y: 1.05, w: 5.6, h: 1.94, objectName: "x2 figure" });
  table(s, [
    ["설정 (PPO)", "1~4단계 평균"],
    ["레벨 무작위", "0.66 ± 0.31"],
    ["커리큘럼 + 복습", "0.57 ± 0.02"],
    ["커리큘럼 (기본)", "0.53 ± 0.06"],
    ["처음부터 레벨 4", "0.42 ± 0.17"],
    ["원시 좌표 관측 (X3)", "0.57 ± 0.20"],
    ["시간 벌점 없음 (X4)", "0.59 ± 0.34"],
    ["다가가기 보상 없음 (X4)", "0.66 ± 0.23"],
  ], { x: 6.35, y: 1.05, w: 3.15, colW: [1.85, 1.3], rowH: 0.42 }, 10.5);
  card(s, 0.5, 3.2, 5.6, 1.75, HEX.light, "x2 lesson");
  bullets(s, [
    "커리큘럼의 망각: 레벨 3을 연습하는 동안 레벨 1이 0.71로 떨어짐. 복습을 넣으면 회복하지만 어려운 레벨 연습이 줄어 평균은 비슷",
    "처음부터 어려운 레벨: 성공 경험이 드물어 학습 신호가 약함 (희소 보상)",
    "관측 · 보상 수정 효과는 신뢰구간 안. 20초 시간 초과 −1만으로도 버티기가 막힘",
  ], { x: 0.7, y: 3.3, w: 5.2, h: 1.6, fontSize: 11 });
}

// ---------------------------------------------------------------- 6. Step 1: 10단계, 정책 하나
{
  const s = content("1단계: 정책 하나로는 10단계 완주 0번", "강화학습",
    "게임을 10단계 캠페인으로 늘리고 SAC, PPO, Double DQN을 같은 설정으로 1,200만 스텝씩 처음부터 학습했다. 레벨 2부터 절반은 이전 단계를 복습하게 했다. 1~4단계는 대부분 통과했지만 6·9단계는 거의 0%이고, 단계마다 무너지는 곳이 seed마다 달랐다. 세 알고리즘 모두 10단계 완주는 600번 중 0번이었다.");
  const data = [
    { name: "SAC", labels: LEVELS, values: [100, 91, 94, 94, 61, 0, 77, 40, 0, 18] },
    { name: "PPO", labels: LEVELS, values: [100, 100, 100, 100, 63, 11, 0, 33, 0, 9] },
    { name: "DQN", labels: LEVELS, values: [8, 25, 8, 8, 0, 0, 0, 0, 0, 0] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.05, w: 6.4, h: 3.95, barDir: "col", chartColors: [HEX.teal, HEX.blue, HEX.gray] });
  card(s, 7.15, 1.25, 2.35, 2.0, "FCE8E8", "zero card");
  txt(s, "0 / 600", { x: 7.25, y: 1.45, w: 2.15, h: 0.75, fontSize: 32, bold: true, color: C.accent1, align: "center", valign: "middle" });
  txt(s, "10단계 완주\n(세 알고리즘 모두)", { x: 7.25, y: 2.25, w: 2.15, h: 0.7, fontSize: 12, align: "center" });
  txt(s, "단계별 성공률, seed 3개 평균.\n1,200만 스텝, 레벨당 200판 평가", { x: 7.15, y: 3.45, w: 2.35, h: 0.8, fontSize: 10, color: "555B66" });
  txt(s, "학습 시간 (1,200만 스텝): PPO 50분 · DQN 4.3시간 · SAC 10.7시간", { x: 7.15, y: 4.25, w: 2.35, h: 0.7, fontSize: 10, bold: true, color: C.text2 });
}

// ---------------------------------------------------------------- 6-1. 새 빌드 재비교
{
  const s = content("최종 빌드에서 세 알고리즘 재비교 (seed 5개)", "강화학습",
    "코드를 정리한 최종 빌드에서 세 알고리즘을 처음부터 다시 학습했다. 시드당 105만 스텝, 은닉층 128, 판마다 새 배치. 무작위 레벨과, 모든 알고리즘이 같은 스텝에서 레벨을 여는 고정 커리큘럼(레벨 2부터 50% 복습)을 비교했다. 처음 seed 3개로는 신뢰구간이 넓어 seed를 5개로 늘렸다. PPO와 SAC가 DQN보다 낫다는 것은 두 조건 모두 유의했고(p ≤ 0.008), 커리큘럼은 PPO를 5.8%p 올렸다(p = 0.03). SAC와 PPO는 기본 설정에서는 구분되지 않았다(p = 0.88). 1단계 낮은 빔에서 PPO는 80%의 결정에서 슬라이딩을 눌러 실패했고, SAC는 점프를 75% 골랐다.");
  const data = [
    { name: "무작위 레벨", labels: ["PPO", "SAC", "Double DQN", "무작위 행동"], values: [7.32, 9.17, 1.70, 0] },
    { name: "커리큘럼", labels: ["PPO", "SAC", "Double DQN", "무작위 행동"], values: [13.15, 13.64, 1.28, 0] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), valAxisMaxVal: 25, valAxisMajorUnit: 5, x: 0.5, y: 1.05, w: 5.3, h: 3.9, barDir: "col", chartColors: [HEX.gray, HEX.teal],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", dataLabelFontSize: 10, dataLabelColor: "1B1B2A", dataLabelFontFace: "+mn-lt" });
  card(s, 6.05, 1.1, 3.45, 1.15, HEX.light, "rank card");
  txt(s, "1~10단계 평균 (seed 5개, 커리큘럼)", { x: 6.2, y: 1.18, w: 3.2, h: 0.3, fontSize: 12, bold: true, color: C.accent3 });
  txt(s, "SAC 13.6 ± 5.4 · PPO 13.2 ± 5.4 · DQN 1.3 ± 1.9 (%). PPO·SAC > DQN 유의, SAC vs PPO는 구분 불가", { x: 6.2, y: 1.5, w: 3.2, h: 0.7, fontSize: 10.5 });
  card(s, 6.05, 2.4, 3.45, 1.2, HEX.light, "curriculum card");
  txt(s, "커리큘럼 효과 (같은 seed끼리)", { x: 6.2, y: 2.48, w: 3.2, h: 0.3, fontSize: 12, bold: true, color: C.accent2 });
  txt(s, "PPO +5.8 ± 5.0%p (p = 0.03) · SAC +4.5 ± 7.9%p (p = 0.19) · DQN −0.4%p. 개선은 1~4단계에서", { x: 6.2, y: 2.8, w: 3.2, h: 0.75, fontSize: 10.5 });
  card(s, 6.05, 3.75, 3.45, 1.2, "FCE8E8", "behavior card");
  txt(s, "차이는 1단계 낮은 빔에서", { x: 6.2, y: 3.83, w: 3.2, h: 0.3, fontSize: 12, bold: true, color: C.accent1 });
  txt(s, "낮은 빔은 점프가 정답. PPO 슬라이딩 80.6% → 36/222 통과, SAC 점프 75.5% → 100/222", { x: 6.2, y: 4.15, w: 3.2, h: 0.75, fontSize: 10.5 });
}

// ---------------------------------------------------------------- 6-2. 하이퍼파라미터 탐색
{
  const s = content("하이퍼파라미터 탐색: 32개 설정 × seed 3", "강화학습",
    "위 비교의 커리큘럼 설정을 기준으로 값을 하나씩만 바꿔 102개 모델을 학습했다(시드당 105만 스텝). 같은 seed끼리 기준과의 차이를 구하고 95% 신뢰구간을 그렸다. 초록은 구간 전체가 0보다 위, 빨강은 아래다. SAC는 갱신 빈도를 16스텝에서 4스텝마다로 바꾸자 15.5%에서 34.1%가 됐다. 환경 데이터를 4배 모은 학습(420만 스텝, 갱신 횟수가 같음)도 35.2%로 같았고 걸린 시간도 비슷했다. 즉 SAC는 데이터가 아니라 갱신 횟수가 부족했다. PPO는 학습률 1e-3이 좋았고, γ = 0.95는 둘 다 0%로 무너졌다. DQN은 값 하나만 바꿔서는 아무것도 유의하지 않았다. 주의: seed 3개로 32개를 검정했으므로 Holm 다중 비교 보정을 하면 유의한 것이 하나도 남지 않는다(가장 작은 보정 p = 0.28). 그래서 여기서는 후보만 고르고, 다음 장에서 새 seed로 다시 확인했다.");
  s.addImage({ path: FIG + "laser_hp_sweep.png", x: 0.5, y: 1.0, w: 9.0, h: 3.6, objectName: "hp sweep figure" });
  txt(s, "후보: SAC 갱신 4배 +18.6%p · PPO 학습률 1e-3 +6.0%p · γ 0.95 −12.7 / −15.5%p (32개 다중 비교 보정 전)",
    { x: 0.5, y: 4.68, w: 9.0, h: 0.35, fontSize: 11.5, bold: true, color: C.text2, align: "center", valign: "middle" });
}

// ---------------------------------------------------------------- 6-3. 실패 방식
{
  const s = content("실패 방식으로 본 원인: 할인율과 DQN", "강화학습",
    "성공률만 보면 왜 실패했는지 모른다. 그래서 실패를 충돌과 시간 초과로 나눴다. γ = 0.95에서는 실패의 90% 이상이 시간 초과였고, 모델 6개 중 5개는 레이저가 없는 0단계도 깨지 못했다. 20초 뒤 시간 초과 −1은 0.95의 200제곱 ≈ 0으로 할인돼 거의 보이지 않으니, 충돌 위험을 피해 출발선 근처에 머무는 정책이 된다. 환경을 처음 설계할 때 겪은 '버티기' 문제가 그대로 재현됐고, 0.99를 쓴 이유를 실험으로 확인했다. DQN도 실패의 41%가 시간 초과다. Q값은 대체로 가능한 범위 안이었지만 한 seed는 마지막에 2.17로 최대 리턴 1.5를 넘었다(과대추정). 갱신 4배, ε 기간 2배, 목표값 ±3을 함께 쓰면 탐색 seed에서 13.4%까지 올랐지만, 다음 장처럼 새 seed에서는 재현되지 않았다.");
  s.addImage({ path: FIG + "laser_failure_modes.png", x: 0.5, y: 1.0, w: 9.0, h: 3.33, objectName: "failure modes figure" });
  txt(s, "γ 0.95: 시간 초과 89~93% → γ 0.99 선택 근거  ·  DQN: 시간 초과 41%, Q값 2.17 > 최대 리턴 1.5",
    { x: 0.5, y: 4.45, w: 9.0, h: 0.5, fontSize: 11.5, bold: true, color: C.text2, align: "center", valign: "middle" });
}

// ---------------------------------------------------------------- 6-4. 새 seed로 확인
{
  const s = content("새 seed 5개로 확인: 튜닝하면 순위가 바뀐다", "강화학습",
    "탐색에서 가장 좋아 보인 설정은 우연히 뽑혔을 수 있다(선택 편향). 그래서 탐색에 쓰지 않은 seed 3~7로 기준과 고른 설정을 다시 학습했다. PPO 학습률 1e-3과 SAC 갱신 4배는 새 seed에서도 그대로 재현됐다. DQN 조합은 탐색 seed에서 +12.3%p였지만 새 seed에서는 +2.8%p로 유의하지 않았다. 같은 105만 스텝에서 각 알고리즘을 튜닝하자 SAC 33.3%, PPO 18.3%, DQN 4.9%로 순위가 갈렸고 모든 쌍의 차이가 유의했다. 기본값 비교에서 'PPO와 SAC는 같다'였던 결론이 튜닝 후에는 달라진 것이다. 확인 실험은 미리 고른 3개만 검정했으므로 Holm 보정 후에도 PPO(p = 0.031)와 SAC(p = 0.0009)는 유의하다.");
  table(s, [
    ["고른 설정 (기준 대비)", "탐색 seed 0~2", "새 seed 3~7", "재현"],
    ["PPO 학습률 3e-4 → 1e-3", "+6.0%p", "+7.6 ± 5.2%p (p = 0.016)", "O"],
    ["SAC 갱신 16 → 4스텝마다", "+18.6%p", "+22.3 ± 5.3%p (p<0.001)", "O"],
    ["DQN 조합 (갱신 · ε · 목표값)", "+12.3%p", "+2.8 ± 5.3%p (p = 0.22)", "X"],
  ], { x: 0.5, y: 1.05, w: 5.6, colW: [2.3, 0.95, 1.85, 0.5], rowH: 0.45 }, 10);
  const data = [
    { name: "기본 설정", labels: ["PPO", "SAC", "Double DQN"], values: [10.7, 11.0, 2.1] },
    { name: "튜닝", labels: ["PPO", "SAC", "Double DQN"], values: [18.3, 33.3, 4.9] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), valAxisMaxVal: 40, valAxisMajorUnit: 10, x: 6.3, y: 1.0, w: 3.2, h: 3.95, barDir: "col", chartColors: [HEX.gray, HEX.teal],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", dataLabelFontSize: 9, dataLabelColor: "1B1B2A", dataLabelFontFace: "+mn-lt" });
  card(s, 0.5, 3.25, 5.6, 1.7, HEX.light, "tuned rank card");
  txt(s, "튜닝 후 1~10단계 평균 (새 seed 5개, 같은 105만 스텝)", { x: 0.7, y: 3.35, w: 5.2, h: 0.3, fontSize: 12, bold: true, color: C.accent3 });
  bullets(s, [
    "SAC 33.3% > PPO 18.3% > DQN 4.9%, 모든 쌍 p ≤ 0.001",
    "SAC 1~3단계 83~100%, 4단계 51%. 5단계부터는 모두 거의 0",
    "DQN 조합은 탐색 seed에서만 좋았다 → 새 seed로 재확인 필요",
  ], { x: 0.7, y: 3.72, w: 5.2, h: 1.2, fontSize: 10.5 });
}

// ---------------------------------------------------------------- 6-4b. 학습 곡선
{
  const s = content("학습 곡선: 같은 스텝과 같은 시간", "강화학습",
    "새 seed 3~7의 학습 중 평가(단계마다 20판)다. 띠는 seed 5개의 95% 신뢰구간이다. 105만 스텝까지는 튜닝한 SAC의 성공률이 가장 높았다. 기본 설정의 DQN은 거의 오르지 않았다. 시간 축에서 약 130분의 성공률은 SAC 39%, PPO 42%였다. SAC는 약 130분에 학습을 마쳤고, PPO는 230분까지 학습해 79%에 도달했다. 시간은 같은 PC에서 여러 실행을 동시에 돌린 기록이다.");
  s.addImage({ path: FIG + "laser_tuned_curves.png", x: 0.5, y: 1.0, w: 9.0, h: 3.33, objectName: "tuned curves" });
  txt(s, "105만 스텝에서는 SAC 우세. 약 130분에서는 두 정책이 비슷했고 PPO는 230분에 79% 도달",
    { x: 0.5, y: 4.45, w: 9.0, h: 0.5, fontSize: 12, bold: true, color: C.text2, align: "center", valign: "middle" });
}

// ---------------------------------------------------------------- 6-5. 학습 시간
{
  const s = content("더 오래 학습하면: PPO 4,800만 스텝 79%", "강화학습",
    "튜닝한 설정을 더 길게 학습했다(새 seed 3~7). SAC는 4스텝마다 갱신해 420만 스텝(시드당 약 130분)을 학습했다. PPO는 학습률 1e-3에서 1,600만 스텝(약 40분)과 4,800만 스텝(약 230분)을 학습했다. SAC는 105만 스텝 33.3%에서 420만 스텝 40.4%로 올랐다(p = 0.058). PPO는 47.7%에서 78.9 ± 8.9%로 올랐다. 두 최종 체크포인트의 차이는 38.5%p였다(p < 0.001). 6단계의 단독 성공률이 16.2%로 가장 낮았다.");
  const lv = LEVELS;
  const data = [
    { name: "SAC 튜닝 420만 (약 130분)", labels: lv, values: [100, 98.8, 82.6, 59.6, 4.4, 0.4, 0.2, 57.8, 0, 0] },
    { name: "PPO 튜닝 1,600만 (약 40분)", labels: lv, values: [99.2, 98.8, 77.4, 54.0, 15.4, 0.8, 21.8, 78.0, 18.8, 12.4] },
    { name: "PPO 튜닝 4,800만 (약 230분)", labels: lv, values: [100, 99.8, 93.6, 73.4, 60.4, 16.2, 81.4, 100, 96.6, 67.6] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.0, w: 6.1, h: 3.95, barDir: "col", chartColors: [HEX.orange, HEX.blue, HEX.teal] });
  [["78.9 ± 8.9%", "PPO 4,800만 스텝, 1~10단계 평균\n(새 seed 5개)", "E3F6F4", C.accent2],
   ["13% → " + PURE_RL, "순수 강화학습 정책 하나\n기본 → 튜닝 + 긴 학습", HEX.light, C.accent3],
   ["6단계 16.2%", "가장 낮은 단계. SAC 420만은\n6 · 7 · 9 · 10단계 거의 0", "FCE8E8", C.accent1]].forEach(([big, small, fill, color], i) => {
    const y = 1.05 + i * 1.32;
    card(s, 6.85, y, 2.65, 1.2, fill, "time card " + i);
    txt(s, big, { x: 6.95, y: y + 0.08, w: 2.45, h: 0.45, fontSize: 18, bold: true, color, align: "center", valign: "middle" });
    txt(s, small, { x: 6.95, y: y + 0.55, w: 2.45, h: 0.6, fontSize: 10, align: "center" });
  });
}

// ---------------------------------------------------------------- 7. Step 2: 망각
{
  const s = content("2단계: 한 단계만 배우면 나머지를 잊는다", "강화학습",
    "약한 단계마다 PPO를 따로 600만 스텝 학습했더니 자기 단계는 100%가 되었다. 그런데 다른 단계는 거의 0%로 떨어졌다. 정책 하나로 여러 단계를 동시에 학습하기 어려운 이유가 이 망각과 간섭이라는 것을 직접 확인했다. 그래서 단계마다 잘하는 정책을 따로 두고, 그것들을 하나로 합치는 방법이 필요했다.");
  const data = [
    { name: "5단계 전용 PPO", labels: LEVELS, values: [0, 76, 0, 0, 100, 0, 0, 0, 0, 0] },
    { name: "6단계 전용 PPO", labels: LEVELS, values: [74, 26, 0, 0, 0, 100, 0, 0, 0, 0] },
    { name: "7단계 전용 PPO", labels: LEVELS, values: [0, 28, 76, 30, 0, 0, 100, 0, 0, 0] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.05, w: 6.4, h: 3.95, barDir: "col", chartColors: [HEX.orange, HEX.red, HEX.purple] });
  card(s, 7.15, 1.25, 2.35, 3.0, HEX.light, "forgetting card");
  txt(s, "망각", { x: 7.35, y: 1.4, w: 2.0, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
  txt(s, "새 단계를 배우면 앞에서 배운 행동을 덮어쓴다.\n\n→ 단계별 전문가를 두고 하나로 합치자", { x: 7.35, y: 1.85, w: 2.0, h: 2.3, fontSize: 12 });
}

// ---------------------------------------------------------------- 8. Step 3: 모방 학습
pres.addSection({ title: "모방 학습" });
{
  const s = content("3단계: 모방 학습으로 정책 하나에 합치기", "모방 학습",
    "11장의 behavior cloning과 DAgger를 그대로 썼다. 선생님은 단계마다 고른 PPO 정책이고, 학생은 PPO와 같은 크기의 신경망 하나다. 손실은 선생님 행동을 정답으로 한 cross-entropy다. BC는 선생님이 플레이한 상태만, DAgger는 학생이 플레이한 상태에 선생님이 정답을 붙인다. 데이터 양과 학습 횟수는 같게 맞췄다.");
  card(s, 0.5, 1.15, 2.6, 2.6, HEX.light, "teacher card");
  txt(s, "선생님", { x: 0.7, y: 1.28, w: 2.2, h: 0.35, fontSize: 15, bold: true, color: C.accent3 });
  txt(s, "단계마다 가장 잘하는 PPO 정책 (10개 단계)", { x: 0.7, y: 1.68, w: 2.2, h: 0.9, fontSize: 12 });
  ["L1", "L5", "L6", "L10"].forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7 + i * 0.53, y: 2.75, w: 0.45, h: 0.42, rectRadius: 0.05, fill: { color: HEX.blue }, line: { color: HEX.blue }, objectName: "teacher " + t });
    s.addText(t, { isTextBox: true, x: 0.7 + i * 0.53, y: 2.75, w: 0.45, h: 0.42, fontSize: 10, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
  });
  s.addShape(pres.shapes.RIGHT_ARROW, { x: 3.25, y: 2.15, w: 0.7, h: 0.5, fill: { color: HEX.gray }, line: { color: HEX.gray }, objectName: "arrow" });
  card(s, 4.1, 1.15, 2.6, 2.6, "E3F6F4", "student card");
  txt(s, "학생 (정책 하나)", { x: 4.3, y: 1.28, w: 2.2, h: 0.35, fontSize: 15, bold: true, color: C.accent2 });
  txt(s, "66 → 256 → 256 → 27\n선생님 행동을 정답으로 cross-entropy 학습", { x: 4.3, y: 1.68, w: 2.2, h: 1.2, fontSize: 12 });
  const rows = [["BC", "선생님이 플레이한 상태만 모은다"], ["DAgger", "학생이 플레이한 상태에 선생님이 정답"]];
  s.addTable(rows.map(([a, b]) => [
    { text: a, options: { bold: true, fontSize: 12, color: C.background1, fill: { color: HEX.navy }, align: "center" } },
    { text: b, options: { fontSize: 11, color: C.text1, fill: { color: HEX.light } } },
  ]), { x: 0.5, y: 3.95, w: 6.2, colW: [1.1, 5.1], rowH: 0.42, border: { type: "solid", pt: 1.5, color: "FFFFFF" }, margin: 0.06, valign: "middle" });
  card(s, 6.95, 1.15, 2.55, 3.65, "FDF1E6", "result card");
  txt(s, "361 / 600", { x: 7.05, y: 1.35, w: 2.35, h: 0.65, fontSize: 28, bold: true, color: C.accent3, align: "center", valign: "middle" });
  txt(s, "10단계 완주 (단계당 3번)\n강화학습만 쓴 정책은 0", { x: 7.05, y: 2.0, w: 2.35, h: 0.6, fontSize: 11, align: "center" });
  txt(s, "BC = DAgger\n학생이 직접 간 상태에서도 선생님과 99.99% 같은 행동\n→ ε≈0이라 오차 누적(εT²)이 없음", { x: 7.15, y: 2.85, w: 2.15, h: 1.85, fontSize: 11 });
}

// ---------------------------------------------------------------- 9. Step 4: 선생님 개선
{
  const s = content("4단계: 약한 단계 선생님을 다시 학습", "모방 학습",
    "학생은 선생님을 거의 그대로 따라 하므로, 실패도 그대로 물려받는다. 그래서 약한 단계(5·6·7·10)의 PPO 선생님을 기존 정책에서 이어서 600만 스텝 다시 학습했다. 6·10단계는 처음에 레이저 벽 통로를 넓혀 주고 점점 원래 폭으로 줄였다. 선생님은 최종 평가와 겹치지 않는 검증용 seed에서 골랐다. 다시 증류한 학생은 1~9단계 100%, 10단계 71%였다.");
  const head = ["단계", "이전 선생님", "새 PPO 선생님"].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.navy }, fontSize: 12, align: "center" } }));
  const rows = [["5단계", "71%", "100%"], ["6단계", "49.5%", "100%"], ["7단계", "79%", "100%"], ["10단계", "22.5%", "74%"]]
    .map((r) => r.map((t, i) => ({ text: t, options: { fontSize: 13, align: "center", bold: i === 2, color: i === 2 ? C.accent2 : C.text1, fill: { color: HEX.light } } })));
  s.addTable([head, ...rows], { x: 0.5, y: 1.15, w: 4.6, colW: [1.3, 1.6, 1.7], rowH: 0.5, border: { type: "solid", pt: 1.5, color: "FFFFFF" }, margin: 0.05, valign: "middle" });
  txt(s, "검증용 seed(77000)에서 단계당 200판", { x: 0.5, y: 3.8, w: 4.6, h: 0.3, fontSize: 10, color: "555B66" });
  [["97.1%", "1~10단계 평균 성공률", HEX.purple, 1.15], ["600 / 600", "10단계 완주 (단계당 3번)", HEX.purple, 2.4], ["446 / 600", "단계당 1번만 시도하면", HEX.red, 3.65]].forEach(([big, small, color, y]) => {
    card(s, 5.45, y, 4.05, 1.05, HEX.light, "stat " + small);
    txt(s, big, { x: 5.6, y: y + 0.1, w: 1.9, h: 0.85, fontSize: 26, bold: true, color, valign: "middle" });
    txt(s, small, { x: 7.5, y: y + 0.1, w: 1.9, h: 0.85, fontSize: 12, valign: "middle" });
  });
}

// ---------------------------------------------------------------- 10. 진단 지표
{
  const s = content("PPO 선생님의 학습 진단 지표는 정상 범위", "모방 학습",
    "10장 슬라이드 24에서 본 네 가지 지표를 함께 기록했다. 엔트로피는 천천히 줄었지만 0으로 무너지지 않았고, 업데이트당 KL과 clip fraction은 작게 유지되다가 학습률이 줄어드는 후반에 0에 가까워졌다. value loss도 줄어드는 추세다. 그래서 학습 코드 자체에는 문제가 없고, 남은 실패는 다른 원인에서 찾아야 한다고 판단했다.");
  s.addImage({ path: FIG + "laser_teacher_diagnostics.png", x: 0.5, y: 1.15, w: 9.0, h: 1.71, objectName: "diagnostics figure" });
  const checks = [["엔트로피", "0.35~1.0 (최대 ln27≈3.3). 0으로 무너지지 않음"], ["KL · clip fraction", "0.03 · 0.12 이하. 후반에는 0에 가까워짐"], ["value loss", "줄어드는 추세"]];
  checks.forEach(([a, b], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 3.2, 2.9, 1.15, HEX.light, "check " + a);
    txt(s, "✓ " + a, { x: x + 0.15, y: 3.32, w: 2.6, h: 0.35, fontSize: 13, bold: true, color: C.accent2 });
    txt(s, b, { x: x + 0.15, y: 3.72, w: 2.6, h: 0.55, fontSize: 11 });
  });
}

// ---------------------------------------------------------------- 11. Step 5: 마지막 배치
{
  const s = content("5단계: 강화학습이 못 푼 배치 하나는 시범으로 해결", "모방 학습",
    "10단계 배치 4개 중 3개는 100%, 배치 3 하나만 늘 0%였다. 학습 판의 절반을 그 배치로 고정해 600만 스텝 PPO를 학습해도 0%였다. 통과 경로가 11.7초로 가장 길고 기다리는 타이밍이 정확해야 해서, 무작위 탐험으로 성공을 한 번도 보지 못했기 때문이다. 10장의 희소 보상 문제다. 그래서 빔 탐색으로 찾은 통과 경로를 시범으로 학생 데이터에 넣었다. 그 배치에서는 선생님 정답을 빼서, 같은 상태에 정답이 두 개 붙는 문제(11장 슬라이드 16)를 피했다.");
  card(s, 0.5, 1.15, 4.35, 2.15, "FCE8E8", "ppo fail card");
  txt(s, "PPO 집중 학습 600만 스텝", { x: 0.7, y: 1.27, w: 4.0, h: 0.35, fontSize: 14, bold: true, color: C.accent1 });
  txt(s, "배치 3 성공률 0% (seed 2개 모두)", { x: 0.7, y: 1.68, w: 4.0, h: 0.35, fontSize: 13, bold: true });
  txt(s, "성공을 한 번도 못 보면 학습 신호가 없다\n= 희소 보상 (10장, MountainCar 0/1000과 같은 상황)", { x: 0.7, y: 2.1, w: 4.0, h: 1.1, fontSize: 11 });
  card(s, 5.15, 1.15, 4.35, 2.15, "E3F6F4", "demo card");
  txt(s, "통과 경로 시범 117개 행동", { x: 5.35, y: 1.27, w: 4.0, h: 0.35, fontSize: 14, bold: true, color: C.accent2 });
  txt(s, "배치 3 성공률 100%", { x: 5.35, y: 1.68, w: 4.0, h: 0.35, fontSize: 13, bold: true });
  txt(s, "빔 탐색으로 찾은 경로를 시범으로 추가 (11장).\n그 배치의 선생님 정답은 빼서 정답이 섞이지 않게 함", { x: 5.35, y: 2.1, w: 4.0, h: 1.1, fontSize: 11 });
  card(s, 0.5, 3.5, 9.0, 1.4, HEX.light, "final stat");
  txt(s, "1,200 / 1,200", { x: 0.75, y: 3.6, w: 3.6, h: 1.2, fontSize: 36, bold: true, color: C.accent2, valign: "middle" });
  txt(s, "정책 하나가 1~10단계를 단계당 한 번의 시도로 모두 완주\n(학생 6개 = BC·DAgger × seed 3개, 새 환경 seed에서 각 200회)", { x: 4.4, y: 3.6, w: 4.9, h: 1.2, fontSize: 13, valign: "middle" });
}

// ---------------------------------------------------------------- 12. 같은 배치를 단계별로
{
  const s = content("같은 배치(10단계 배치 3)를 단계마다의 정책이 플레이", "모방 학습",
    "같은 배치를 1단계부터 4단계까지의 정책이 차례로 플레이하는 영상이다. 앞의 세 정책은 같은 지점에서 레이저에 닿고, 시범을 넣은 학생만 기다렸다가 통로를 지나 금고에 도착한다. 발표 화면에서 GIF가 재생된다.");
  s.addImage({ path: FIG + "laser_steps.gif", x: 1.6, y: 1.05, w: 6.8, h: 3.825, objectName: "step by step gif" });
  txt(s, "1단계 PPO 정책 하나 → 2단계 10단계 전용 PPO → 3단계 모방 학습 학생 → 4단계 학생 + 시범", { x: 0.5, y: 4.95, w: 9.0, h: 0.25, fontSize: 10, color: "555B66", align: "center" });
}

// ---------------------------------------------------------------- 13. 최종 비교
{
  const s = content("최종 비교: 정책 하나로 1~10단계", "모방 학습",
    "왼쪽은 단계별 성공률(seed 3개 평균 ± 95% 신뢰구간, 레벨당 200판), 오른쪽은 10단계 완주율이다. 채운 막대는 단계당 3번, 빗금은 단계당 1번 시도다. 강화학습만 쓴 정책(당시 기본 설정, 1,200만 스텝)은 0, 모방 학습 학생은 선생님 개선과 시범으로 100%가 되었다. 이후 튜닝과 긴 학습으로 강화학습 정책 하나도 새 배치 완주 44%까지 올랐다(정리 절).");
  s.addImage({ path: FIG + "laser_imitation.png", x: 0.5, y: 1.05, w: 9.0, h: 2.957, objectName: "final comparison figure" });
  const rows = [["정책", "1~10단계 평균", "완주 (3번)", "완주 (1번)"], ["SAC · PPO (강화학습만, 1,200만)", "57.5% · 51.6%", "0 / 600", "–"], ["학생 v2 (선생님 개선)", "97.1%", "600 / 600", "446 / 600"], ["학생 v2 + 시범", "100%", "600 / 600", "600 / 600"]];
  s.addTable(rows.map((r, j) => r.map((t, i) => ({ text: t, options: { fontSize: 11, bold: j === 0 || j === 3, align: i === 0 ? "left" : "center",
    color: j === 0 ? C.background1 : (j === 3 ? C.accent2 : C.text1), fill: { color: j === 0 ? HEX.navy : HEX.light } } }))),
    { x: 0.5, y: 4.08, w: 9.0, colW: [3.0, 2.0, 2.0, 2.0], rowH: 0.27, border: { type: "solid", pt: 1, color: "FFFFFF" }, margin: 0.04, valign: "middle" });
}

// ---------------------------------------------------------------- 13-1. 일반화
{
  const s = content("6단계: 처음 보는 배치에서는 외운 것이었다", "모방 학습",
    "캠페인 배치를 끄면 판마다 레이저 위치·속도·위상이 새로 정해진다. 그 새 배치에서 평가하자 고정 배치에서 100%였던 학생이 21%였다. 단계마다 고정된 배치 4개를 외운 것이다. 경로 탐색으로 확인하니 무작위 배치 300개 중 299개에 통과 경로가 있었으므로, 낮은 성공률은 학습 문제다. 판마다 새 배치로 선생님을 다시 학습하고(4·5단계는 SAC 후보 포함) 학생을 다시 증류하자 처음 보는 배치에서 80%가 되었다. 같은 예산 5,250만 스텝을 준 PPO 정책 하나는 약 28%였다.");
  const data = [{ name: "처음 보는 배치 평균", labels: ["PPO 정책 하나\n(1,200만)", "PPO 정책 하나\n(5,250만, 같은 예산)", "고정 배치 학생", "무작위 배치\n선생님", "무작위 배치 학생\n(DAgger 512)"], values: [16.8, 27.6, 21.3, 84.0, 80.0] }];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.05, w: 5.9, h: 3.95, barDir: "col", showLegend: false,
    chartColors: [HEX.gray, HEX.orange, "A7E3DC", HEX.blue, HEX.teal], varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", dataLabelFontSize: 11, dataLabelColor: "1B1B2A", dataLabelFontFace: "+mn-lt", catAxisLabelFontSize: 9 });
  card(s, 6.65, 1.1, 2.85, 1.7, "FCE8E8", "memorize card");
  txt(s, "외운 배치 100% → 새 배치 21%", { x: 6.8, y: 1.22, w: 2.6, h: 0.35, fontSize: 12, bold: true, color: C.accent1 });
  txt(s, "단계마다 배치 4개로만 배우면 배치를 외운다", { x: 6.8, y: 1.6, w: 2.6, h: 1.1, fontSize: 11 });
  card(s, 6.65, 3.0, 2.85, 1.95, "E3F6F4", "solvable card");
  txt(s, "299 / 300 통과 가능", { x: 6.8, y: 3.12, w: 2.6, h: 0.35, fontSize: 13, bold: true, color: C.accent2 });
  txt(s, "무작위 배치를 경로 탐색으로 확인. 판마다 새 배치로 다시 학습하자 학생 21% → 80%", { x: 6.8, y: 3.5, w: 2.6, h: 1.35, fontSize: 11 });
}

// ---------------------------------------------------------------- 13-2. DAgger vs BC
{
  const s = content("7단계: DAgger가 BC보다 나은 조건", "모방 학습",
    "고정 배치에서는 학생이 선생님을 99.99% 따라 해서 BC와 DAgger가 같았다. 새 배치에서는 학생이 실수하고, 작은 학생일수록 실수가 많다. 이때 학생이 실제로 간 상태에서 정답을 모으는 DAgger가 BC보다 낫다. 작은 학생에서 11.5%p 차이이고 신뢰구간이 겹치지 않는다. 또 5단계 선생님을 더 강한 SAC(95%)로 바꾸자 학생은 오히려 78%에서 63%로 떨어졌다. SAC 선생님 단계의 행동 일치율이 71~93%로 PPO 선생님(93~99%)보다 낮았다. 최대 엔트로피 학습이라 여러 행동의 점수가 비슷해 정답이 흔들리기 때문으로 본다.");
  const data = [
    { name: "BC", labels: ["학생 64", "학생 256"], values: [48.9, 68.5] },
    { name: "DAgger", labels: ["학생 64", "학생 256"], values: [60.4, 71.2] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.05, w: 4.6, h: 3.95, barDir: "col", chartColors: [HEX.gray, HEX.blue],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", dataLabelFontSize: 11, dataLabelColor: "1B1B2A", dataLabelFontFace: "+mn-lt" });
  card(s, 5.35, 1.1, 4.15, 1.75, HEX.light, "dagger card");
  txt(s, "학생이 실수할 때 DAgger가 효과", { x: 5.55, y: 1.22, w: 3.8, h: 0.35, fontSize: 13, bold: true, color: C.accent3 });
  txt(s, "작은 학생: BC 48.9% → DAgger 60.4% (신뢰구간 겹치지 않음). 고정 배치(ε≈0)에서는 차이 없음", { x: 5.55, y: 1.6, w: 3.8, h: 1.15, fontSize: 11 });
  card(s, 5.35, 3.05, 4.15, 1.9, "FDF1E6", "imitability card");
  txt(s, "선생님은 따라 하기 쉬워야 한다", { x: 5.55, y: 3.17, w: 3.8, h: 0.35, fontSize: 13, bold: true, color: C.accent4 });
  txt(s, "5단계 선생님 PPO 80% → SAC 95%로 바꾸자 학생 5단계 78% → 63%. 행동 일치율: PPO 단계 93~99%, SAC 단계 71~93%", { x: 5.55, y: 3.55, w: 3.8, h: 1.3, fontSize: 11 });
}

// ---------------------------------------------------------------- 13-3. 6단계 설계 수정
pres.addSection({ title: "6단계" });
{
  const s = content("게임 6단계: 병목 측정과 설계 수정", "6단계",
    "새 배치에서 학생의 6단계는 약 20%로 남았다. 측정해 보니 폭 1.10m 통로에서 에이전트 반경과 벽 두께를 빼면 중심이 지나갈 범위가 0.38m뿐이었고, 반대 위상 이중벽 사이의 대기 공간은 가장 좁은 배치에서 0.228m였다. 이중벽 간격을 1.44m로, 좁은 통로의 유효 폭을 0.64m로 넓혔다. 수정 전후 모두 통과 경로는 생성 배치 60개 중 59개에서 찾았다. 학생 가중치는 고정하고 같은 평가 seed로 비교했다. 환경을 바꾼 것이므로 기존 결과와는 별도 조건으로 기록했다.");
  table(s, [
    ["평가 환경 (DAgger 학생, 가중치 고정)", "새 배치 6단계", "새 배치 10단계 완주"],
    ["기존 설계", "17.5% ± 3.7%p", "253 / 600 (42.2%)"],
    ["간격 · 폭 확대", "29.0% ± 7.8%p", "352 / 600 (58.7%)"],
    ["+ 좁은 통로 속도 제한", "31.2% ± 7.1%p", "386 / 600 (64.3%)"],
  ], { x: 0.5, y: 1.1, w: 9.0, colW: [4.0, 2.3, 2.7], rowH: 0.5 }, 12);
  [["0.38m → 0.64m", "좁은 통로에서 중심이 지나갈 수 있는 폭"], ["0.228m → 0.568m", "이중벽 사이 가장 좁은 대기 깊이"], ["59 / 60", "수정 전후 모두 통과 경로가 있는 배치"]].forEach(([big, small], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 3.35, 2.9, 1.55, HEX.light, "stat6 " + i);
    txt(s, big, { x: x + 0.1, y: 3.45, w: 2.7, h: 0.6, fontSize: 20, bold: true, color: C.accent3, align: "center", valign: "middle" });
    txt(s, small, { x: x + 0.1, y: 4.1, w: 2.7, h: 0.7, fontSize: 11, align: "center" });
  });
}

// ---------------------------------------------------------------- 13-4. 충돌 예측
{
  const s = content("0.2초 충돌 예측으로 완주 99.8%", "6단계",
    "남은 실패 427회는 모두 충돌이었다. 그래서 행동을 고를 때 Unity가 방 상태를 복사해 각 행동을 0.2초 앞까지 시뮬레이션하고, 충돌하는 행동을 후보에서 뺐다(행동 마스크). 학습된 정책은 그대로 두고 실행할 때만 적용한다. 6단계만 쓰면 6단계 단독 89.8%, 4·5·6·9·10단계에 쓰면 완주 99.5%, 7단계까지 넣으면 99.8%였다. 반대로 충돌 예측을 쓰는 선생님을 학생이 따라 하게 하면 28.2%에 그쳤다. 관측만으로는 미래 충돌을 알기 어렵다는 뜻이다. 이 방법은 시뮬레이터를 미리 돌려 볼 수 있다는 가정이 필요하므로, 순수 강화학습 결과와 따로 보고한다.");
  const data = [
    { name: "6단계 한 번 시도", labels: ["기존", "6단계만 예측", "4·5·6·9·10 예측", "PPO 추가 학습만", "예측 교사 모방"], values: [28.8, 89.8, 89.8, 34.2, 28.2] },
    { name: "10단계 완주", labels: ["기존", "6단계만 예측", "4·5·6·9·10 예측", "PPO 추가 학습만", "예측 교사 모방"], values: [59.7, 95.2, 99.5, 67.0, 62.3] },
  ];
  s.addChart(pres.charts.BAR, data, { ...chartBase(), x: 0.5, y: 1.05, w: 5.9, h: 3.9, barDir: "col", chartColors: [HEX.orange, HEX.teal],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"", dataLabelFontSize: 9, dataLabelColor: "1B1B2A", dataLabelFontFace: "+mn-lt", catAxisLabelFontSize: 9 });
  card(s, 6.65, 1.1, 2.85, 1.55, "E3F6F4", "final campaign card");
  txt(s, "599 / 600", { x: 6.75, y: 1.18, w: 2.65, h: 0.6, fontSize: 28, bold: true, color: C.accent2, align: "center", valign: "middle" });
  txt(s, "최종 빌드, 새 배치 10단계 완주\n(4·5·6·7·9·10단계 예측, 단계당 3번)", { x: 6.75, y: 1.8, w: 2.65, h: 0.8, fontSize: 10.5, align: "center" });
  card(s, 6.65, 2.8, 2.85, 2.15, HEX.light, "safety check card");
  txt(s, "검증", { x: 6.8, y: 2.88, w: 2.6, h: 0.3, fontSize: 12, bold: true, color: C.accent3 });
  bullets(s, [
    "예측이 방 상태를 바꾸지 않음: 7,680개 전이 일치",
    "허용한 행동 2,065개 중 즉시 충돌 0회",
    "평균 ± 는 seed 3개 기준 95% t 신뢰구간",
  ], { x: 6.8, y: 3.22, w: 2.6, h: 1.7, fontSize: 10.5 });
}

// ---------------------------------------------------------------- 14. 배운 점
pres.addSection({ title: "정리" });
{
  const s = content("PPO 순차 완주율 44%와 충돌 예측 적용 시 100%", "정리",
    "최종 숫자가 무엇 덕분인지 2 × 2로 나눴다. 모두 처음 보는 배치에서 1~10단계를 순서대로, 단계당 최대 3번 시도한 완주율이다. 학습만 쓴 경우 튜닝한 PPO 정책 하나(4,800만 스텝)가 44.0%, 단계별 선생님을 DAgger로 합친 모방 학습이 59.7%였다. 여기에 실행할 때 Unity가 0.2초 앞을 시뮬레이션해 충돌하는 행동을 빼면 PPO 하나가 1,000 / 1,000, 모방 학습이 599 / 600이 됐다. 같은 예측을 약한 정책에 붙이면 SAC 420만 13.5%, PPO 1,600만 39.6%에 그쳤다. 예측은 0.2초 앞의 충돌만 막아 줄 뿐 어디로 가야 하는지는 알려주지 않으므로, 잘 학습된 정책이 있어야 효과가 난다. 예측 층은 시뮬레이터를 미리 돌려 볼 수 있다는 가정에 기대므로 학습 성과와 따로 본다. PPO 행은 seed 5개, 모방 학습 행은 seed 3개다.");
  table(s, [
    ["정책 (처음 보는 배치, 10단계 순차 완주)", "학습만", "+ 0.2초 충돌 예측"],
    ["SAC 튜닝 420만 스텝 (강화학습, seed 5)", "0 / 1,000 (0%)", "135 / 1,000 (13.5%)"],
    ["PPO 튜닝 1,600만 스텝 (강화학습, seed 5)", "6 / 1,000 (0.6%)", "396 / 1,000 (39.6%)"],
    ["PPO 튜닝 4,800만 스텝 (강화학습, seed 5)", "440 / 1,000 (44.0%)", "1,000 / 1,000 (100%)"],
    ["단계별 선생님 → DAgger (모방 학습, seed 3)", "358 / 600 (59.7%)", "599 / 600 (99.8%)"],
  ], { x: 0.5, y: 1.05, w: 9.0, colW: [4.4, 2.2, 2.4], rowH: 0.46 }, 11);
  [["6단계 단독 성공률 16.2%", "PPO 4,800만 스텝의 최저 성공률. 처음 보는 배치에서 한 번만 시도", "FCE8E8", C.accent1],
   ["PPO 순차 완주 1,000 / 1,000", "0.2초 충돌 예측 적용 후 학습 seed 5개 모두 200회 완주", "E3F6F4", C.accent2],
   ["정책에 따라 다른 완주율", "같은 충돌 예측을 적용한 SAC 420만은 13.5%, PPO 1,600만은 39.6%", HEX.light, C.accent3]].forEach(([h, b, fill, color], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 3.5, 2.9, 1.45, fill, "takeaway " + i);
    txt(s, h, { x: x + 0.15, y: 3.6, w: 2.6, h: 0.35, fontSize: 12, bold: true, color });
    txt(s, b, { x: x + 0.15, y: 4.0, w: 2.6, h: 0.85, fontSize: 10.5 });
  });
}

{
  const s = content("연구 질문에 대한 답", "정리",
    "처음에 던진 네 질문에 실험 결과로 답한다. 숫자는 모두 해당 슬라이드의 seed 단위 95% 신뢰구간과 같은 조건에서 나왔다.");
  const qa = [
    ["Q1", "알고리즘 · 비교 기준", "기본값이면 PPO ≈ SAC > DQN (seed 5개). 튜닝하면 같은 스텝에서 SAC 33% > PPO 18% > DQN 5%. 같은 시간이면 PPO가 따라잡고 더 길게 학습해 " + PURE_RL + ". 비교 기준과 튜닝 여부가 순위를 바꾼다", HEX.blue],
    ["Q2", "레벨 구성 · 설계", "1~4단계에서는 레벨 무작위, 10단계에서는 커리큘럼 + 복습이 유리 (PPO +5.8%p). γ 0.95는 버티기로 0%, 관측 · 보상 세부 수정은 신뢰구간 안", HEX.teal],
    ["Q3", "10단계 실패 원인", "망각과 희소 보상. 단계별 선생님 → DAgger + 시범으로 고정 배치 1,200 / 1,200. 다만 튜닝한 PPO를 4,800만 스텝 학습하면 정책 하나로도 새 배치 완주 44%", HEX.purple],
    ["Q4", "처음 보는 배치", "고정 배치 학생은 21% (암기). 판마다 새 배치로 학습해 80%. 6단계 병목은 설계 수정 + 충돌 예측으로 해결: PPO 하나 100%, 모방 학습 99.8%", HEX.orange],
  ];
  qa.forEach(([k, h, body, color], i) => {
    const y = 1.05 + i * 0.98;
    card(s, 0.5, y, 9.0, 0.88, HEX.light, "answer " + k);
    stepBadge(s, k, 0.65, y + 0.23, color);
    txt(s, h, { x: 1.2, y: y + 0.1, w: 1.9, h: 0.68, fontSize: 12.5, bold: true, color, valign: "middle" });
    txt(s, body, { x: 3.1, y: y + 0.08, w: 6.25, h: 0.72, fontSize: 11, valign: "middle" });
  });
}

{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "정리" });
  s.addText("배운 점", { placeholder: "title" });
  s.addNotes("여섯 가지를 정리한다. 비교 기준(튜닝 여부, 같은 스텝·같은 시간), 망각, 희소 보상, 고정 배치 암기와 일반화, DAgger가 필요한 조건, 새 seed로 다시 확인하기. 모두 수업에서 배운 개념을 우리 환경에서 직접 확인한 것이다.");
  const items = [
    ["비교 기준이 결론을 바꾼다", "기본값이면 PPO ≈ SAC, 튜닝하면 같은 스텝에서 SAC 33% > PPO 18%. 시간을 더 주면 PPO가 79%까지", HEX.blue],
    ["정책 하나는 여러 단계를 잊는다", "단계별 전문가를 모방 학습으로 하나에 합쳐 망각을 피했다 (11장)", HEX.purple],
    ["성공을 못 보면 배울 수 없다", "희소 보상으로 PPO 0%인 배치를 시범 하나로 100% (10·11장)", HEX.teal],
    ["고정 배치로만 배우면 외운다", "처음 보는 배치에서 21%. 판마다 새 배치로 학습해 80% (평가 분리)", HEX.red],
    ["DAgger는 학생이 실수할 때 필요", "작은 학생에서 DAgger가 BC보다 11.5%p 높음. ε≈0이면 차이 없음 (11장)", HEX.orange],
    ["한 번의 개선은 다시 확인한다", "탐색 seed에서 +12%p였던 DQN 조합이 새 seed에서는 +2.8%p(유의하지 않음)", "8D99AE"],
  ];
  items.forEach(([h, b, color], i) => {
    const x = 0.5 + (i % 3) * 3.05, y = 1.25 + Math.floor(i / 3) * 1.95;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.9, h: 1.8, rectRadius: 0.08, fill: { color: "1B2B40" }, line: { color: "1B2B40" }, objectName: "lesson " + (i + 1) });
    stepBadge(s, String(i + 1), x + 0.15, y + 0.15, color);
    txt(s, h, { x: x + 0.7, y: y + 0.12, w: 2.1, h: 0.5, fontSize: 13, bold: true, color: C.background1, valign: "middle" });
    txt(s, b, { x: x + 0.15, y: y + 0.75, w: 2.6, h: 1.0, fontSize: 11, color: "CADCFC" });
  });
}

// ---------------------------------------------------------------- 15. 한계
{
  const s = content("한계와 다음 단계", "정리",
    "PPO를 6단계에서 210만 스텝 더 학습했다. 새 평가 배치에서 충돌 예측을 끈 6단계 단독 성공률은 17.5%에서 26.8%로 올랐고, 10단계 순차 완주는 410회에서 516회로 늘었다(각 1,000회 평가). 두 학습 예산과 두 지표에 Holm 보정을 적용한 결과, 6단계 단독 성공률 개선의 보정 p는 0.0083, 순차 완주율 개선의 보정 p는 0.105였다. 추가 학습 정책을 6단계에서만 쓴 탐색 평가에서는 539회를 완주했다. 충돌 예측과 시범 생성에는 Unity 상태가 필요하다. 모방 학습은 학습 seed 3개로 비교했다.");
  const cols = [
    ["한계", HEX.red, ["100% 완주에는 실행 시 충돌 예측을 사용", "충돌 예측과 시범 생성에는 Unity 상태가 필요", "모방 학습 비교는 학습 seed 3개", "학습 시간에는 동시 실행 부하가 포함됨"]],
    ["6단계 후속 실험", HEX.teal, ["PPO를 6단계에서 210만 스텝 추가 학습", "6단계 성공률 17.5% → 26.8% (보정 p = 0.0083)", "1,000회 중 순차 완주 410회 → 516회", "순차 완주율 차이의 보정 p = 0.105"]],
  ];
  cols.forEach(([h, color, lines], i) => {
    const x = 0.5 + i * 4.6;
    card(s, x, 1.1, 4.4, 3.85, HEX.light, h + " card");
    txt(s, h, { x: x + 0.25, y: 1.3, w: 3.9, h: 0.4, fontSize: 17, bold: true, color });
    s.addText(lines.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < lines.length - 1 } })),
      { isTextBox: true, x: x + 0.25, y: 1.8, w: 3.95, h: 3.05, fontSize: 12, color: C.text1, paraSpaceAfter: 10, valign: "top", margin: 0 });
  });
}

// ---------------------------------------------------------------- 16. 기여
{
  const s = content("프로젝트 구현 범위와 팀원 기여 확인 현황", "정리",
    "세 영역은 저장소에서 확인할 수 있는 작업이다. 개인별 담당은 팀원 확인 후 표기한다.");
  const roles = [
    ["A · 환경", HEX.blue, "Unity 레이저 미션 (Room.cs, LaserAgent.cs), MDP 설계, 단계 설계와 통과 경로 검증, 6단계 설계 수정"],
    ["B · PPO · 모방 학습", HEX.purple, "PPO 구현, 커리큘럼 · 복습, 단계별 선생님, BC · DAgger 증류, 시범"],
    ["C · DQN · SAC · 평가", HEX.teal, "Double DQN · 이산 SAC 구현과 안정화, 평가 · 통계(신뢰구간), 충돌 예측 평가, 보고서"],
  ];
  roles.forEach(([h, color, body], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.1, 2.9, 3.85, HEX.light, h + " card");
    txt(s, "담당자 확인 중", { x: x + 0.18, y: 1.25, w: 2.6, h: 0.35, fontSize: 13, bold: true, color: C.text2 });
    txt(s, h, { x: x + 0.18, y: 1.65, w: 2.6, h: 0.35, fontSize: 14, bold: true, color });
    txt(s, body, { x: x + 0.18, y: 2.1, w: 2.6, h: 2.7, fontSize: 11.5 });
  });
}

// ---------------------------------------------------------------- 17. 참고 자료
{
  const s = content("참고 자료와 사용 도구", "정리",
    "알고리즘은 논문을 보고 직접 구현했고 강화학습 라이브러리 코드는 쓰지 않았다. Unity ML-Agents는 Unity와 Python 사이 통신에만 썼다. 코드 작성과 문서 정리에 AI 코딩 도구를 사용했다.");
  bullets(s, [
    "Schulman et al., Proximal Policy Optimization Algorithms, 2017",
    "Schulman et al., High-Dimensional Continuous Control Using Generalized Advantage Estimation, 2016",
    "van Hasselt et al., Deep Reinforcement Learning with Double Q-learning, AAAI 2016",
    "Haarnoja et al., Soft Actor-Critic Algorithms and Applications, 2018",
    "Christodoulou, Soft Actor-Critic for Discrete Action Settings, 2019",
    "Ross, Gordon, Bagnell, A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning (DAgger), AISTATS 2011",
    "Bengio et al., Curriculum Learning, ICML 2009",
    "Juliani et al., Unity: A General Platform for Intelligent Agents (ML-Agents), 2018",
  ], { x: 0.5, y: 1.1, w: 9.0, h: 2.9, fontSize: 11.5 });
  card(s, 0.5, 4.1, 9.0, 0.85, HEX.light, "tools card");
  txt(s, "사용 도구: Unity 6000.0 LTS · ML-Agents · Python 3.10 · PyTorch · NumPy · Matplotlib · AI 코딩 도구 (Claude Code, Codex). 코드: " + GITHUB,
    { x: 0.7, y: 4.18, w: 8.6, h: 0.7, fontSize: 11, valign: "middle" });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("saved", OUT);
})();
