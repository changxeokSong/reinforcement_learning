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
  s.addNotes("알바트로스가 움직이는 레이저를 피해 금고까지 가는 3D 미션을 Unity로 직접 만들고, 강화학습과 모방 학습으로 풀었다. 오늘은 처음 실패부터 최종 완주까지 단계별로 무엇을 확인하고 무엇을 고쳤는지 순서대로 설명한다.");
}

// ---------------------------------------------------------------- 2. 한 장 요약
{
  const s = content("한 장 요약: 0번 완주에서 1,200번 완주까지", "시작",
    "결론부터 말하면, 강화학습 정책 하나로는 10단계를 한 번도 완주하지 못했고, 원인을 하나씩 찾아 고쳐서 마지막에는 정책 하나가 단계당 한 번의 시도만으로 1,200번 모두 완주했다. 이후 슬라이드는 이 다섯 단계를 차례로 설명한다.");
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
    card(s, x, 1.25, w, 3.45, HEX.light, "step card " + k);
    stepBadge(s, k, x + 0.15, 1.42, color);
    txt(s, name, { x: x + 0.15, y: 1.98, w: w - 0.3, h: 0.75, fontSize: 14, bold: true, color: C.text2 });
    txt(s, big, { x: x + 0.1, y: 3.0, w: w - 0.2, h: 0.6, fontSize: big.length > 9 ? 15 : 20, bold: true, color, align: "center", valign: "middle" });
    txt(s, small, { x: x + 0.1, y: 3.65, w: w - 0.2, h: 0.75, fontSize: 11, color: "555B66", align: "center" });
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
    "왼쪽은 단계별 성공률(seed 3개 평균 ± 95% 신뢰구간, 레벨당 200판), 오른쪽은 10단계 완주율이다. 채운 막대는 단계당 3번, 빗금은 단계당 1번 시도다. 강화학습만 쓴 정책은 0, 모방 학습 학생은 선생님 개선과 시범으로 100%가 되었다.");
  s.addImage({ path: FIG + "laser_imitation.png", x: 0.5, y: 1.05, w: 9.0, h: 2.957, objectName: "final comparison figure" });
  const rows = [["정책", "1~10단계 평균", "완주 (3번)", "완주 (1번)"], ["SAC · PPO (강화학습만)", "57.5% · 51.6%", "0 / 600", "–"], ["학생 v2 (선생님 개선)", "97.1%", "600 / 600", "446 / 600"], ["학생 v2 + 시범", "100%", "600 / 600", "600 / 600"]];
  s.addTable(rows.map((r, j) => r.map((t, i) => ({ text: t, options: { fontSize: 11, bold: j === 0 || j === 3, align: i === 0 ? "left" : "center",
    color: j === 0 ? C.background1 : (j === 3 ? C.accent2 : C.text1), fill: { color: j === 0 ? HEX.navy : HEX.light } } }))),
    { x: 0.5, y: 4.08, w: 9.0, colW: [3.0, 2.0, 2.0, 2.0], rowH: 0.27, border: { type: "solid", pt: 1, color: "FFFFFF" }, margin: 0.04, valign: "middle" });
}

// ---------------------------------------------------------------- 14. 배운 점
pres.addSection({ title: "정리" });
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "정리" });
  s.addText("배운 점", { placeholder: "title" });
  s.addNotes("네 가지를 정리한다. 비교 기준, 망각, 희소 보상, 그리고 여러 seed로 다시 확인하기. 모두 수업에서 배운 개념을 우리 환경에서 직접 확인한 것이다.");
  const items = [
    ["비교 기준이 결론을 바꾼다", "같은 스텝이면 SAC, 같은 시간이면 PPO. 예산을 맞춰 비교하고 기준을 밝힌다 (10장)", HEX.blue],
    ["정책 하나는 여러 단계를 잊는다", "단계별 PPO 전문가를 모방 학습으로 하나에 합쳐 망각을 피했다 (11장)", HEX.purple],
    ["성공을 못 보면 배울 수 없다", "희소 보상으로 PPO가 0%인 배치는 시범 하나로 100%가 됐다 (10·11장)", HEX.teal],
    ["한 번의 개선은 다시 확인한다", "seed 1개로 본 개선은 seed 3개에서 대부분 사라졌다. 신뢰구간으로 판단 (10장)", HEX.orange],
  ];
  items.forEach(([h, b, color], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.35 + Math.floor(i / 2) * 1.85;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.4, h: 1.65, rectRadius: 0.08, fill: { color: "1B2B40" }, line: { color: "1B2B40" }, objectName: "lesson " + (i + 1) });
    stepBadge(s, String(i + 1), x + 0.2, y + 0.2, color);
    txt(s, h, { x: x + 0.78, y: y + 0.2, w: 3.45, h: 0.45, fontSize: 15, bold: true, color: C.background1, valign: "middle" });
    txt(s, b, { x: x + 0.2, y: y + 0.78, w: 4.0, h: 0.8, fontSize: 12, color: "CADCFC" });
  });
}

// ---------------------------------------------------------------- 15. 한계
{
  const s = content("한계와 다음 단계", "정리",
    "시범은 시뮬레이터의 모든 상태를 아는 탐색으로 만들었기 때문에, 되감을 수 없는 실제 환경에서는 사람의 시범이 필요하다. 단계마다 배치가 4개뿐이라 처음 보는 배치에 대한 일반화는 확인하지 않았다. 다음 단계로는 배치를 무작위로 많이 만들어 일반화를 평가하고, 학생을 강화학습으로 다시 미세 조정하는 것을 생각할 수 있다.");
  const cols = [
    ["한계", HEX.red, ["시범은 시뮬레이터 상태를 모두 아는 탐색으로 만듦. 실제 환경이라면 사람 시범이 필요", "단계마다 배치 4개뿐. 처음 보는 배치에서의 일반화는 미확인", "BC와 DAgger 차이가 드러나지 않음 (ε≈0)"]],
    ["다음 단계", HEX.teal, ["배치를 무작위로 많이 만들어 일반화 평가", "관측을 줄여(시야 제한) 분포 이동이 생기는 조건에서 BC vs DAgger 비교", "학생을 PPO로 미세 조정해 시범 없는 배치도 풀기"]],
  ];
  cols.forEach(([h, color, lines], i) => {
    const x = 0.5 + i * 4.6;
    card(s, x, 1.15, 4.4, 3.0, HEX.light, h + " card");
    txt(s, h, { x: x + 0.25, y: 1.3, w: 3.9, h: 0.4, fontSize: 17, bold: true, color });
    s.addText(lines.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < lines.length - 1 } })),
      { isTextBox: true, x: x + 0.25, y: 1.85, w: 3.95, h: 2.15, fontSize: 13, color: C.text1, paraSpaceAfter: 10, valign: "top", margin: 0 });
  });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("saved", OUT);
})();
