// 판단 근거 · 모델 설정 (10/14 메뉴 재구성) — 운영 요약의 숫자가 어디서 나왔고 얼마나 믿을 수 있는지를 한 화면에 모은다.
// 원칙은 운영 요약과 같다: 계산 결과(day JSON · 시드 묶음)와 장부(입력 출처표 · 가설표 · 근거 사슬)에서만 문장을 만든다.

const EV = { holdout: null, busy: false, go: 0, open: new Set() };
function goWeak() { evOpen(7); }
// 10/16 판단 근거 바로가기 — 다른 화면 · 어시스턴트에서 n번 근거로 들어올 때 그 칸을 펼치고 그 자리로
function evOpen(n) {
  if (MODE !== "evidence") { EV.go = n; EV.view = "detail"; setMode("evidence"); return; }
  if (EV.view !== "detail" && typeof x19SetView === "function") x19SetView("detail");
  const sec = document.getElementById("ev-" + n); if (!sec) return;
  sec.open = true; EV.open.add(n);
  setTimeout(() => sec.scrollIntoView({ behavior: "smooth", block: "start" }), 30);
}
const EV_SECS = [[1, "숫자 정의"], [2, "참조 모델 비교"], [3, "입력 출처"], [4, "성향 적용"], [5, "가설 실험"], [6, "근거 사슬"], [7, "약한 고리"]];
// ① 화면 숫자의 세는 법 — 판단 근거 표와 어시스턴트가 같은 정의를 쓴다
const EV_DEFS = [
    ["공급 제한을 겪은 팀", "점수가 더 높았던 후보가 만석 · 대기로 빠져 다른 곳을 고른 일이 한 번 이상 있는 고유 팀. 막힌 팀의 일행 수(초과 수요 · 팀마다 업장별 한 번)와 단위가 다름"],
    ["건 · 팀", "건 = 손님이 후보를 고를 때마다 센 횟수(같은 팀이 여러 번 셀 수 있음), 팀 = 고유 팀"],
    ["최종 식사 선택", "식사 이용이 제한됐을 때 같은 식사 시간대에 결국 무엇을 먹었는지 (고객팀 · 날짜 · 식사 시간대마다 한 번). 객실로 돌아간 것을 식사 포기로 보지 않음"],
    ["빠진 후보", "고른 곳보다 점수가 높았지만 공급 제한으로 빠진 곳. 자리가 있었으면 반드시 갔다는 뜻은 아님"],
    ["체류 매출", "그날 들어온 손님이 머무는 동안 쓴 돈 (연박 객실 · 다음 날 지출 포함). 온톨로지와 비교하는 값"],
    ["그날 지출", "그날 날짜로 잡힌 결제만 (객실은 1박분). 호텔의 하루 운영 매출은 여러 날을 이어 돌려야 나옴"],
    ["업장 구성 (목적 · 투숙)", "업장을 이용한 고유 팀 기준. 상품을 여러 개 산 팀을 한 번만 셈"],
    ["시드 범위 · 95% 구간", "손님 생성 · 확률 선택의 우연만 바꿔 여러 번 돌린 범위. 구간은 t값 (시드 3개 4.30 · 5개 2.78 · 10개 2.26)"],
    ["시드 반복에서 방향 일관 (굵은 표시)", "같은 시드끼리 짝지은 차이의 95% 구간이 0을 넘지 않고, 거의 매번 같은 방향. 정한 모델과 가정 안에서 반복 실행한 결과이며, 실제 호텔에서 효과가 검증됐다는 뜻은 아님"],
    ["95% 구간의 뜻", "지금 가정과 모델을 고정했을 때 우연(손님 생성 · 확률 선택)만 바꿔 생기는 반복 변동성. 실제 워커힐 매출 예측의 신뢰구간이 아님"],
    ["같은 시드 비교", "같은 시드면 손님 생성이 같아 기준과 변동 상황에 같은 손님이 들어감 (휴업 · 휴장 · 바이럴 · 외국인 · 가격은 기준 손님 1,087팀이 그대로이고 늘어난 손님만 덧붙음). 비 오는 주말은 손님 구성 자체가 바뀌어 짝이 약 3분의 2만 맞음. 손님마다 확률 선택 난수가 독립인지는 근거사슬 7-8절"],
    ["모델 · 입력 버전", "코드와 입력 표의 해시. 버전이 다른 결과는 '예전 계산' 으로 표시하고 서로 비교하지 않음"],
];
const EV_ONTO_NOTE = "온톨로지 기반 참조 모델과의 비교이며, 실제 워커힐 영업 실적에 대한 예측 정확도를 의미하지 않습니다.";
// 섹션 한 칸: 번호 · 제목 · 한 줄 결론은 늘 보이고, 설명 문단과 표는 펼쳤을 때만
// 10/16 LLM 행동 선택 파일럿 (근거사슬 7-21) — 기본은 한 줄, 펼치면 A/A2/B/C · 표본 선정 편향 · 정답 정의에 따른 차이 · 비용. static/llm_pilot.json 만 읽는다
function llmPilotBlock(LP) {
  const A = LP.agg || {}, N = { A: "A 규칙 엔진 v4.1", A2: "A2 규칙 엔진 · 난수만 바꿈 (잡음 기준)", B: "B 모든 결정을 LLM", C: "C 자유 식사 결정만 LLM" };
  const f4 = v => (v == null ? "-" : (+v).toFixed(4)), sg = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(4);
  const rows = Object.keys(N).filter(k => A[k]).map(k => { const x = A[k];
    return `<tr><td>${N[k]}</td><td class="n">${(+x.recall).toFixed(1)}%</td><td class="n">${(+x.precision).toFixed(1)}%</td><td class="n">${f4(x.brier)}</td><td class="n">${x.d_brier == null ? "" : `${sg(x.d_brier)} ± ${(+x.se_brier).toFixed(4)}`}</td><td class="n">${x.better == null ? "" : `${x.better} / ${x.worse}`}</td></tr>`; }).join("");
  const T = LP.gold_tiers, s1 = LP.stage1;
  const tier = T ? `<h5>정답 정의에 따라 결론이 바뀐다 · 가지 않은 곳과 후기에 적히지 않은 곳</h5><p class="hint">후기 체류의 '미방문' ${Object.entries(T.counts).map(([k, v]) => `${k} ${v}`).join(" · ")}. 지금 Brier 는 적히지 않은 곳도 미방문으로 셉니다.</p>
    <table class="t"><tr><th>미방문으로 세는 범위</th>${["A", "A2", "B", "C"].map(k => `<th class="n">${k}</th>`).join("")}</tr>${Object.entries(T.brier).map(([lab, r]) => `<tr><td>${esc(lab)}</td>${["A", "A2", "B", "C"].map(k => `<td class="n">${f4(r[k].brier)}${r[k].d != null ? `<br><span class="hint">${sg(r[k].d)} ± ${r[k].se.toFixed(4)}</span>` : ""}</td>`).join("")}</tr>`).join("")}
    <tr><td>순위 판별 AUC · 간 곳 vs 명시 미방문 (높을수록 좋음)</td>${["A", "A2", "B", "C"].map(k => `<td class="n">${(T.auc["명시 미방문 (◎)"][k] || [])[0] ?? "-"}</td>`).join("")}</tr></table>
    <p class="hint">${esc(T.note)} 명시 미방문만으로 매기면 B 가 나아 보이고, 적히지 않은 곳까지 세면 B 가 나빠 보입니다. 순위 판별은 난수만 바꾼 A2 의 흔들림 안에 있습니다. 지금 정답으로는 어느 쪽도 확정하지 않습니다.</p>` : "";
  const st = s1 ? `<h5>표본 선정 편향 · 1차 결정 사례 ${s1.n}건</h5><p class="hint">후기에 식당 이름이 나온 결정만 골랐더니 1순위 적중이 규칙 ${s1.top1_rule} → LLM ${s1.top1_llm} 로 보였지만, 식당 후보를 균등하게 고르는 단순 기준선(로그 점수 ${s1.logscore_rest_uniform})이 규칙(${s1.logscore_rule}) · LLM(${s1.logscore_llm}) 을 모두 이겼습니다. '식당에 갔다' 가 사례 고르기에서 이미 정해졌기 때문입니다. 식당이 둘 이상인 자유 선택은 ${s1.n_place}건뿐이었습니다.</p>` : "";
  const u = LP.usage || {};
  return `<details class="llmp"><summary><b>LLM 행동 선택 파일럿</b> · LLM 적용 시 재현율은 올랐으나 전체 예측 오차 개선은 확인되지 않아 확대 보류 <span class="hint">· 근거사슬 7-21</span></summary>
    <p class="hint">${esc(LP.model || "")} · 엔진이 운영 시간 · 좌석 · 예약 규칙으로 거른 후보 중 하나만 LLM 이 고릅니다. 후기 원문 · 정답 · 모델 점수 · 성향 값은 주지 않았습니다. 후기 ${LP.n} 체류 · 같은 손님 · 같은 시드 ${LP.k}번 (반복 횟수는 표본 수가 아님).</p>
    <table class="t"><tr><th>조건</th><th class="n">재현율</th><th class="n">정밀도</th><th class="n">Brier</th><th class="n">A 대비 ± 표준오차</th><th class="n">좋아짐 / 나빠짐</th></tr>${rows}</table>
    <p class="hint">B 는 결정이 더 많고 더 많은 곳을 들러, 간 곳을 더 맞히지만(재현율) 가지 않은 곳에도 확률을 더 줍니다(Brier 악화). 성향 점수를 넣었을 때와 같은 모양입니다. 차이는 표준오차와 비슷한 크기라 '규칙 엔진이 더 낫다' 고 확정하지 않습니다.</p>
    ${st}${tier}
    <p class="hint">비용: 59 체류 실행의 Decisions API 입력 약 ${Math.round((u.in || 0) / 1e4).toLocaleString()}만 토큰 (출력 과금 없음 · 1달러 미만). LLM 입력에서 성향 값을 뺐으므로, 자연어 페르소나를 풍부하게 준 경우의 효과는 따로 남은 가설입니다.</p></details>`;
}
// 10/16 데이터 기여도 · 추가 데이터 가치 (근거사슬 7-23 · docs/데이터_가치_분석_1016.md) — static/data_value.json 만 읽는다
function dataValueBlock(DV) {
  const S1 = DV.stage1, S2 = DV.stage2, S3 = DV.stage3; if (!S1) return "";
  const sg = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(4);
  const rc = r => r === "악화" ? "bad" : r === "개선" ? "good" : "flat";
  const G = S1.gold;
  const t1 = `<table class="t dv"><tr><th>바꾼 것</th>${S1.tiers.map(t => `<th class="n">${esc(t.name)}</th>`).join("")}<th>읽기</th></tr>` +
    S1.rows.map(r => `<tr><td>${esc(r.name)} <span class="hint">${esc(r.source)}</span></td>${S1.tiers.map(t => { const x = r[t.id]; return `<td class="n"><span class="dv-r ${rc(x.read)}">${esc(x.read)}</span><br><span class="hint">${sg(x.d)} ± ${x.se.toFixed(4)}</span></td>`; }).join("")}<td><b>${esc(r.robust)}</b></td></tr>`).join("") + `</table>`;
  const mx = `<table class="t dv"><tr><th>고객 행동</th><th>지금 자료로 확인한 것</th><th>지금 구분 못 하는 것</th><th>추가되면 쓸 자료</th><th>검증할 가설 · 지표</th></tr>` +
    S3.matrix.map(m => `<tr><td><b>${esc(m.behavior)}</b><br><span class="hint">${esc(m.level)}</span></td><td>${esc(m.now)}</td><td>${esc(m.gap)}</td><td>${esc(m.data)}</td><td>${esc(m.hypo)}<br><span class="hint">${esc(m.metric)}</span></td></tr>`).join("") + `</table>`;
  const rm = `<table class="t dv"><tr><th>순위 · 자료</th><th>단위 · 기간</th><th>검증할 것</th><th>왜 이 순서</th></tr>` +
    S3.roadmap.map(x => `<tr><td><b>${x.rank}. ${esc(x.item)}</b></td><td>${esc(x.unit)}<br><span class="hint">${esc(x.period)} · ${esc(x.link)}</span></td><td>${esc(x.verify)}<br><span class="hint">활용: ${esc(x.use)}</span></td><td class="hint">${esc(x.why)}</td></tr>`).join("") + `</table>`;
  const s2 = S2 ? `<h5>2단계 · 추가 데이터의 잠재적 가치 — 피자힐 대기 (모델 안의 민감도)</h5><p class="hint">${esc(S2.sample)}</p><ul class="dv-list">${(S2.finding || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul><p><b>${esc(S2.implication || "")}</b></p><p class="hint">${esc(S2.caveat)}</p>` : "";
  return `<details class="llmp dvb"><summary><b>데이터 기여도 · 추가 데이터 가치</b> · 지금 견고하게 확인된 것은 예약 정보 하나 · 정답(Gold)의 '관측되지 않음' 이 결론을 좌우 <span class="hint">· 근거사슬 7-23</span></summary>
    <h5>관측 상태 네 가지 · 평가용 정답 정의 세 가지</h5><p class="hint">관측 상태: 방문 확인 ${G["간 곳"]}곳(후기 원문 전체${G["간 곳 · 평가 후보 안"] != null ? ` · 그중 Brier · AUC 평가 후보 안 ${G["간 곳 · 평가 후보 안"]}곳 · 후보 밖 ${G["간 곳"] - G["간 곳 · 평가 후보 안"]}곳(로비 · 발렛처럼 행동 후보가 아닌 곳)` : ""}) · 안 갔다고 적힌 곳(명시 미방문 ◎) ${G["명시 미방문 (◎)"]} · 간접 단서(○ · 추천 · 안내 · 대안 언급 · 미방문 확인 아님) ${G["간접 (○)"]} · 언급 없음 ${G["언급 없음"]}. 평가용 정답 정의: A 언급 없음까지 미방문(지금 Brier) · B 언급 없음 제외(명시 미방문 + 간접 단서) · C 명시 미방문만. A 처럼 언급 없음을 미방문으로 다루면 방문 장소를 넓게 예측하는 모델이 구조적으로 불리합니다.</p>
    <h5>1단계 · 이미 검증한 데이터 기여도 (기본 모델 대비 Brier · 체류별 짝 차이 ± 표준오차)</h5>${t1}<p class="hint">${esc(S1.rule)} 대기 회피 역추정(7-20)은 '조건부 대기 회피 가설의 추가 설명력 · 확인되지 않음'.</p>
    ${S1.pref ? `<h5>하루 손님 · '가고 싶은 식당' 입력 (${esc(S1.pref.date.slice(5).replace("-", "/"))} · 시드 ${S1.pref.seeds.length}개 짝 · 온톨로지 식당 6곳 구성비와의 차이)</h5><table class="t dv"><tr><th>조건</th><th class="n">구성비 차이</th><th class="n">A 대비 (시드 범위)</th><th class="n">90~110% 안</th><th>업장별 모델 ÷ 온톨로지</th></tr>` +
      S1.pref.rows.map(r => `<tr><td>${esc(r.name)}</td><td class="n">${r.comp_gap_pp}%p</td><td class="n">${r.d ? `${r.d.mean > 0 ? "+" : ""}${r.d.mean}%p<br><span class="hint">${r.d.min} ~ ${r.d.max}</span>` : ""}</td><td class="n">${r.within} / 6</td><td class="hint">${Object.entries(r.ratio).map(([k, v]) => `${esc(k)} ${v}%`).join(" · ")}</td></tr>`).join("") +
      `</table><p class="hint">${esc(S1.pref.read)}</p>` : ""}
    ${s2}
    <h5>행동별 관측 가능 정보와 추가 데이터 가치</h5>${mx}
    <h5>3단계 · 기업 데이터 확보 · 검증 순서 (제안)</h5>${rm}<ul class="dv-list">${S3.rules.map(x => `<li>${esc(x)}</li>`).join("")}</ul></details>`;
}
// 10/16 근거 완전성 검사 (작업배정 1016 항목 5 · 근거사슬 7-25) — static/evidence_check.json 만 읽는다
function evidenceCheckBlock(EC) {
  const K = EC.kinds_links || EC.kinds || {}, KU = EC.kinds_unique || null, C = EC.cats || {};
  const order = ["외부 근거", "참조 모델 값", "맞춤값", "가정", "근거 없음", "가설표에만"];
  const kc = { "외부 근거": "ok", "참조 모델 값": "ref", "맞춤값": "fit", "가정": "asm", "근거 없음": "none", "가설표에만": "none" };
  const kcls = k => kc[k] || (k.startsWith("혼합") ? "mix" : "etc");
  const sum = o => Object.values(o).reduce((a, b) => a + b, 0);
  // 10/16 집계 기준 두 가지 — 고유 입력 기준(합 = 입력 수) · 근거 연결 기준(혼합 입력은 줄마다)
  const chipRow = o => [...order.filter(k => o[k]), ...Object.keys(o).filter(k => !order.includes(k)).sort((a, b) => o[b] - o[a])]
    .map(k => `<span class="ec-k ${kcls(k)}">${esc(k)} ${o[k]}</span>`).join("");
  const chips = KU ? `<div class="ec-row"><b>고유 입력 기준</b> <span class="hint">입력 하나에 종류 하나 · 합 ${sum(KU)}</span></div><div class="ec-chips">${chipRow(KU)}</div>
    <div class="ec-row"><b>근거 연결 기준</b> <span class="hint">출처표 줄마다 셈 · 혼합 입력은 두 번, 꺼진 계수는 묶음 줄의 종류로 · 합 ${sum(K)}</span></div><div class="ec-chips">${chipRow(K)}</div>`
    : `<div class="ec-chips">${chipRow(K)}</div>`;
  const filled = (EC.filled || []).length ? `<p class="hint"><b>10/16 출처표 보완 ${EC.filled.length}개</b> · 누락이 해소됐다는 뜻이고 근거 수준이 올라간 것은 아닙니다. 보완한 입력의 근거 종류: ${esc(Object.entries((EC.inventory || []).filter(it => it.filled).reduce((a, it) => (a[it.kind] = (a[it.kind] || 0) + 1, a), {})).map(([k, n]) => `${k} ${n}`).join(" · "))}</p>` : "";
  const cats = ["누락", "누락 (부분)", "참조 오류", "버전 불일치", "근거 혼용", "표기 차이", "보류 · 다음 입력 버전", "버전 불일치 (정보)"];
  const iss = cats.filter(c => (EC.issues || []).some(i => i.cat === c)).map(c => `<tr><td colspan="3" class="ec-cat"><b>${esc(c)}</b> ${(EC.issues || []).filter(i => i.cat === c).length}</td></tr>` +
    EC.issues.filter(i => i.cat === c).map(i => `<tr><td>${esc(i.target)}</td><td>${esc(i.detail)}</td><td class="hint">${esc(i.fix)}</td></tr>`).join("")).join("");
  const inv = (EC.inventory || []).map(it => `<tr><td>${esc(it.id)}</td><td class="n">${it.value == null ? "" : esc(String(it.value).slice(0, 24))}</td><td><span class="ec-k ${kcls(it.kind)}">${esc(it.kind)}</span>${it.filled ? ` <span class="ec-new">10/16 보완</span>` : ""}</td><td>${esc((it.provenance || []).join(" · ") || "-")}${(it.hypotheses || []).length ? ` <span class="hint">· 가설 ${esc(it.hypotheses.join(", "))}</span>` : ""}${it.value_ok === false ? ` <b class="ec-bad">값 다름</b>` : ""}</td></tr>`).join("");
  return `<details class="llmp ecb"><summary><b>근거 완전성 검사</b> · 지금 기본 모델이 쓰는 입력 ${(EC.inventory || []).length}개 · 누락 ${(C["누락"] || 0) + (C["누락 (부분)"] || 0)} · 참조 오류 ${C["참조 오류"] || 0} · 근거 혼용 ${C["근거 혼용"] || 0} · 표기 차이 ${C["표기 차이"] || 0}${C["보류 · 다음 입력 버전"] ? ` · 보류 ${C["보류 · 다음 입력 버전"]}` : ""} <span class="hint">· 근거사슬 7-25 · ${esc(EC.built)}</span></summary>
    <p class="hint">조정값 · 행동 점수 계수 · 손님 생성 상수 · 운영 조건 표 · 입력 표를 입력 출처표 · 가설표 · 근거 사슬표와 이어 보고, 근거 종류를 나눴습니다. ${esc(EC.rule)}</p>
    ${chips}${filled}
    <h5>찾은 문제</h5><table class="t dv"><tr><th>대상</th><th>내용</th><th>고칠 방법</th></tr>${iss}</table>
    <details><summary>입력 ${(EC.inventory || []).length}개 전체 · 근거 종류</summary><table class="t dv"><tr><th>입력</th><th class="n">지금 값</th><th>근거 종류</th><th>출처표 줄 · 가설</th></tr>${inv}</table></details>
    <p class="hint">결과 파일 버전: ${(EC.files || []).map(f => `${esc(f.file)} ${f.ok ? "지금 버전" : "다름"}`).join(" · ")} · ${esc(EC.where || "")}</p></details>`;
}
function esect(n, title, one, body, detail) {
  return `<details class="esec" id="ev-${n}" data-n="${n}" ${EV.open.has(n) ? "open" : ""}><summary><span class="rnum">${n}</span><span class="eh"><b>${title}</b><span class="eone">${one}</span></span><span class="echev" aria-hidden="true"></span></summary>` +
    `<div class="ebody"><div class="rtext">${body}</div>${detail ? `<div class="edet">${detail}</div>` : ""}</div></details>`;
}

// 10/15 P1-C 약한 고리 목록 — 순서: 근거가 약하고 · 운영 요약 숫자를 크게 움직이고 · 확보할 수 있는 것 (근거사슬_가설실험_1014 7-11)
const WEAK = [
  { name: "조식 기상 시각 분포", grade: "△",
    line: "더뷔페 조식 2부(08:30) 쏠림은 30분 단위 기상 시각 임시값과 회차 경계가 만든 모양일 수 있습니다. 회차별 실제 입장 인원이 있으면 바로 가려집니다.",
    ev: "임시값 06:30~09:00 30분 단위 6칸(가중 1 · 2 · 3 · 3 · 2 · 1). 근거 없음. 조식 1부로 당긴 후기 5편은 2부 혼잡이 실재함을 시사",
    sens: "10/16 측정(10/10 · v4 · 시드 3 · 같은 조건): 기상 시각을 30분 앞당기면 조식 2부 초과 수요 443 → 198명 · 1부 착석 257 → 288명, 30분 늦추면 546명 · 1부 63명. 조식 제약 팀은 230~276. '어느 회차에 몰리나' 는 거의 이 가정에 달려 있음. 198~546명은 신뢰구간이 아니라 검토한 가정 범위(근거사슬 7-16)",
    need: "더뷔페 조식 회차별 입장 인원 · 2부 대기 시간 · 체크인 때 회차 안내 여부", ease: "중간 (집계값이면 공개 가능할 수 있음)",
    where: "기상 시각 분포 · 회차 선택", fix: "현장 자료" },
  { name: "식사 대체 선택지 구성", grade: "△",
    line: "이용이 제한된 식사의 약 73%(10/10 · 306/421건)가 '호텔 밖 · 객실' 로 갑니다. 여기에는 두 가지 문제가 겹쳐 있습니다. 모델 구조 쪽은 객실 식사(자격 필요)와 호텔 밖 식사(비투숙도 가능)를 한 선택지로 묶어 투숙객만 고르게 한 것이고, 자료 쪽은 막힌 뒤 실제 행선지를 보여 주는 후기가 2편뿐이라는 것입니다. 필요한 자료는 만석 때 안내 문구와 안내받은 손님의 행선지 · 룸서비스 식사 시간대별 건수입니다.",
    ev: "규칙: 식당 외 식사는 객실 키가 있어야 고름(비투숙 없음) · 계수 0.33 은 후기 46편에 맞춘 값(교차검증 · 독립 근거 아님 △). 막혀 포기한 후기 2편(라운지 · 같은 업장 포장). 다른 유료 식당 전환 후기 0편은 반례가 아니라 표본 부족",
    sens: "10/16 측정(10/10 · v4 · 시드 3 · 같은 조건): 식당 밖 식사 계수 0.33 → 1.0 이면 공급 제한 팀 430 → 353, 더뷔페 조식 제약 팀 228 → 129, 이용이 제한된 식사 중 다른 호텔 식당 8 → 13%. 선택지 분리(비투숙 호텔 밖 식사 · 막혔을 때만)는 일요일 더뷔페 158 → 140% · 144 → 127%, 10/10 정합 거의 그대로(근거사슬 7-14 · 7-16)",
    need: "만석 때 안내 문구와 안내받은 손님의 행선지(다른 업장 · 포장 · 룸서비스 · 이탈), 룸서비스 식사 시간대별 건수", ease: "중간 (운영 기록 · 집계값)",
    where: "식당 외 식사 계수 · 대안 안내 조건", fix: "둘 다", fixNote: "모델: '객실 식사'(자격 필요)와 '호텔 밖 식사'(비투숙도 가능)를 나눠야 함 · 현장: 행선지 자료" },
  { name: "평일 비투숙 손님 규모 (H4b 0.5)", grade: "○/△",
    line: "",
    ev: "방향은 통계 2 · 호텔 동향 1 · 비투숙 후기 7편이 받침, 크기(0.4~0.7)는 못 좁힘",
    sens: "지금 구조(v4.1 · 좌석 회전 검증 뒤 · 근거사슬 7-13): 배율 0.4~0.7 에서 업장 평균 차이 10/7 19.9 ~ 22.0%p · 10/14 17.1 ~ 19.5%p 로 거의 변하지 않아 '정합 개선'은 확인되지 않음 → 0.5 는 가정 △ 로 유지. (예전 구조의 10/7 19.5 → 8.2%p · 10/14 22.2 → 10.5%p 는 이전 좌석 구조에서의 관측이라 지금 결론으로 쓰지 않음)",
    need: "네이버 플레이스 방문 요일 건수 · 평일 신호 총량 vs 구성", ease: "진행 중",
    where: "평일 비투숙 배율 (값은 그대로 두고 근거만 보강)", fix: "공개 자료" },
  { name: "비투숙 목적 구성 · 도착 시각", grade: "△",
    line: "",
    ev: "목적은 후기 39편(비투숙 후기 거의 없음), 도착 시각 11시 40% · 17시 60% 는 임시값",
    sens: "도착 시각은 피자힐 저녁 집중의 원인이 아니었음(10/13). 미식 손님 ×2(H2) → 피자힐 미식 1.7 → 3.6%(흔들림 대비 1.9)",
    need: "플레이스 시간대 통계 · SNS 목적 분류", ease: "중간",
    where: "비투숙 목적 섞기 · 도착 시각", fix: "공개 자료" },
  { name: "가고 싶은 식당 · 가고 싶음 비율", grade: "△",
    line: "",
    ev: "후기 39편 '식당=' 건수 + 온톨로지 구성비 · 비율 0.7 · 0.9 는 역산 1회",
    sens: "10/16 측정(10/10 · v4.1 · 시드 3 짝 · pref_eval.py): 가고 싶은 식당을 모두 지우면 더뷔페 이용이 온톨로지의 89 → 67%, 체류 매출 6.10 → 5.78억, 식당 6곳 구성비가 온톨로지에서 4.1%p 멀어짐(3개 시드 모두 같은 방향). 목적별로 다른 식당 비중만 지우면(선호 확률은 그대로) 차이 −0.1%p 로 거의 없음. 즉 효과는 '목적별 구성' 이 아니라 투숙 0.7 · 비투숙 0.9 라는 선호 확률(역산 · 가정)에서 옴",
    need: "SNS 집계형(플레이스 태그) 업장별 목적 비중", ease: "진행 중",
    where: "목적별 선호표 · 선호 비율", fix: "공개 자료" },
  { name: "회차 안 줄 서기 상한 30분 (포함 조식 손님 포함)", grade: "△",
    line: "줄 30분 상한은 후기 1편(blog43)에서 왔지만, 예약 대기가 켜진 지금 규칙에서는 15~60분으로 바꿔도 결과가 같습니다. 근거는 약하되 지금 결과를 움직이지 않는 가정이고, 손님이 다음 회차 예약을 받아들이는 비율이 대신 확인 대상입니다.",
    ev: "후기 1편(blog43 · 50분 넘는 줄 포기). 반례: 같은 장소에서 기다린 후기 6편(10/7 후기 집계)",
    sens: "10/16 측정(10/10 · v4 · 시드 3): 상한 15 · 45 · 60분으로 바꿔도 결과가 같음. 예약 대기가 켜진 지금 규칙에서는 줄이 상한을 넘으면 포기가 아니라 다음 회차 예약으로 가기 때문. 예약 대기를 끈 조건에서는 다를 수 있음(10/13 v4 이전 설정: 30 → 60분이면 명월관 175 → 347명). 실제 손님이 다음 회차 예약을 얼마나 받아들이는지가 새 확인 대상(근거사슬 7-16)",
    need: "조식 포함 손님의 평균 대기 · 포기 비율, 회차 안 대기 한도 운영 방식", ease: "중간 (2순위와 같은 기록)",
    where: "줄 서기 상한 · 식사 포함 혜택 손님의 대기 감수", fix: "현장 자료" },
  { name: "혼잡 시 체류 단축 (v4.1 에서는 조식에만 남음)", grade: "△",
    line: "좌석이 절반 넘게 차면 최소 체류(조식 40분)만 앉는다는 가정은 근거가 부족합니다. v4.1 에서 중식 · 석식은 껐고, 조식은 끄면 평일 조식 이용이 25% 줄어 그대로 두었습니다. 조식 회차별 평균 체류가 있으면 가려집니다.",
    ev: "후기 근거 체류: 조식은 객실 출발부터 90분 미만 경과 1편(착석 시각이 없어 85분으로 확정 못 함) · 석식 약 120분 자기 진술 1편 (10/16 원문 검수 15/39편). 혼잡 때문에 빨리 먹었다는 직접 근거는 아직 못 찾음. 붐빌 때 최소 체류는 v3-E 창 맞춤용 임시값",
    sens: "10/16 측정(시드 3 · 같은 손님): 조식까지 끄면 평일 다음날 조식 560 → 418명 · 585 → 432명, 초과 수요 259 → 400명. 중식 · 석식만 끄면 일요일 석식 704 → 576명(288석 × 2회전 공급 상한), 평일 조식 그대로, A/B 338석 결론 유지(근거사슬 7-19)",
    need: "더뷔페 조식 · 석식 회차별 평균 체류 시간, 붐비는 날과 한산한 날의 체류 차이", ease: "중간 (POS 입 · 퇴장 시각이면 집계 가능)",
    where: "조식 혼잡 시 최소 체류 (no_busy_dwell)", fix: "현장 자료" },
  { name: "금룡 별실 · 접대 손님 (H5)", grade: "△",
    line: "",
    ev: "비즈니스 · 접대 후기 0편 · 금룡 별실 112명 설명 못 함",
    sens: "켜도 명월관 +4~38명, 평균 차이 변화는 시드 편차 안 (보류)",
    need: "공식 별실 조건(쉬움) · 평일 단체 예약 비중(어려움)", ease: "나눠서",
    where: "일행 크기 · 이용 자격 (기본은 그대로)", fix: "현장 자료" },
  { name: "뷔페 품목 소비량", grade: "없음",
    line: "",
    ev: "모델에 없음 · 제공 확인은 후기 1편씩(달걀 요리 · 우유)",
    sens: "모델 결과에는 영향 없음 (준비량 계산 예시의 입력만)",
    need: "메뉴별 선택률 · 1인 소비량 · 재고 · 입고", ease: "어려움 (내부 자료)",
    where: "준비량 예시 카드의 빈칸만 · 발주량은 보류", fix: "현장 자료" },
];

// 10/18 UX 19차b · 판단 근거 세 화면(핵심 발견 / 행동 역추적 / 상세 검증) — 보조 내비는 탭 안에서만 · 기존 상단 탭과 겹치지 않음
//   세 화면을 한 번에 그리고 보이기만 바꾼다(기존 계산 · 바인딩 · id 를 그대로 두기 위해). 숫자는 research_index.json · factor_eval.json 등 기존 결과 파일에서만 읽는다.
const X19_VIEWS = [["find", "핵심 발견"], ["bench", "행동 역추적"], ["detail", "상세 검증"]];
EV.view = EV.view || "find";
function x19SetView(v, opt) {
  if (!X19_VIEWS.some(([k]) => k === v)) v = "find";
  EV.view = v;
  const root = document.querySelector("#evidenceView .x19"); if (!root) return;
  root.querySelectorAll(".x19-view").forEach(s => { s.hidden = s.dataset.v !== v; });
  root.querySelectorAll(".x19-sub [data-v]").forEach(b => { const on = b.dataset.v === v; b.classList.toggle("on", on); b.setAttribute("aria-current", on ? "page" : "false"); });
  if (!(opt && opt.keepHash) && !(v === "find" && EV_ACTION.cur)) { try { history.replaceState(null, "", `#evidence/${v}`); } catch (e) {} }
  if (!(opt && opt.keepScroll)) { const m = document.querySelector("main"); if (m) m.scrollTop = 0; }
}
function x19Subnav() {
  return `<nav class="x19-sub" aria-label="판단 근거 안 화면"><div class="in"><span class="t">판단 근거</span>` +
    X19_VIEWS.map(([k, t]) => `<button type="button" data-v="${k}" class="${EV.view === k ? "on" : ""}">${t}</button>`).join("") +
    `<span class="x19-sp"></span><span class="ver">모델 <code>${esc(LIB.model_ver || "-")}</code> 입력 <code>${esc(LIB.input_ver || "-")}</code> <span class="vs">· 개발 자료 59 체류 · 독립 검증 전</span></span></div></nav>`;
}

async function renderEvidence() {
  const el = $("#evidenceView");
  await loadRidx();
  const PV = LIB.provenance || [], HY = LIB.hypotheses || [], CH = LIB.chain || [];
  const g = s => gradeOf(s["등급"]);
  const nG = k => PV.filter(r => g(r) === k).length;
  const D = typeof DAY !== "undefined" && DAY ? DAY : null;
  const run = D ? `<div class="evrun"><small>현재 실행 정보</small><div><b>${D.date.slice(5).replace("-", "/")} (${"일월화수목금토"[new Date(D.date + "T12:00:00").getDay()]})</b> · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${esc(D.knobs ? knobSummary(D) : "기본 모델")}</div><div class="hint">모델 ${esc(LIB.model_ver || "-")} · 입력 ${esc(LIB.input_ver || "-")}</div></div>`
    : `<div class="evrun"><small>현재 실행 정보</small><div class="hint">열린 하루가 없습니다 · 모델 ${esc(LIB.model_ver || "-")} · 입력 ${esc(LIB.input_ver || "-")}</div></div>`;

  // ── 상세 검증: 전문 분석 ①~⑦ (내용 그대로 · 처음엔 접힘) ──
  let secs = "";
  const p1 = `같은 '전환' 이라도 선택할 때마다 센 횟수와 고유 팀 수는 다르고, '매출' 도 손님이 머무는 동안 쓴 돈과 그날 일어난 지출이 다릅니다. 화면의 숫자는 아래 정의를 따릅니다.`;
  const d1 = `<table class="t rt"><tr><th>화면의 말</th><th>세는 방법</th></tr>` + EV_DEFS.map(([a, b]) => `<tr><td><b>${a}</b></td><td>${b}</td></tr>`).join("") + `</table>`;
  secs += esect(1, "숫자를 세는 방법", `화면 숫자 ${EV_DEFS.length}가지의 세는 법입니다. 팀은 고유 팀, 건은 선택 횟수, 체류 매출은 손님이 머무는 동안 쓴 돈입니다.`, p1, d1);
  const p2 = `기준일 10/10 (토)에 제공해 주신 온톨로지 모델과의 정합을 맞춘 뒤, 같은 설정을 다른 날짜에도 적용했습니다. ` +
    `평일 두 날(10/7 · 10/14)은 평일 비투숙 손님 배율(가설 H4b)을 정할 때 참고했으므로 엄밀한 독립 검증이 아니어서 '기준일 외 날짜' 로 부릅니다. 독립 검증에는 모델 수정에 쓰지 않은 새 날짜가 필요합니다. ` +
    `표의 칸은 시드 여러 개의 평균이고, 괄호는 시드별 최소~최대입니다. 주말 · 공휴일과 평일 사이에 정합도 차이가 있고, 일부 날짜와 업장에서는 편차가 남아 있습니다. ` +
    `후기 재현은 후기 46편으로 계수를 교차검증한 결과입니다. 계수 기본값으로 가장 점수가 높은 행동만 고르면 후기가 간 곳의 76%를 모델도 가고(재현), 모델이 간 곳의 46%가 후기에 있습니다(정밀). 하루 시뮬레이션처럼 확률로 고르게 해 12번 평균을 내면 재현 67% · 정밀 52%입니다.`;
  secs += esect(2, "참조 모델과 얼마나 일치하나", EV_ONTO_NOTE, p2, `<div id="evHold" class="ewide"><div class="hint">날짜별 · 시드별 결과를 모으는 중입니다…</div></div>`);
  const p3 = `모델에 들어가는 입력 ${PV.length}개를 출처와 함께 관리합니다. 공식 자료나 확인을 거친 것(◎)이 ${nG("◎")}개, 근거가 있는 것(○)이 ${nG("○")}개, 아직 가정이거나 근거가 약한 것(△)이 ${nG("△")}개입니다. ` +
    `운영 수치(좌석 · 회차 · 객실 수)는 호텔 쪽 확인이 오면 그대로 바꿉니다.`;
  const order = { "△": 0, "○": 1, "◎": 2 };
  const d3 = `<table class="t rt"><tr><th>입력</th><th>지금 값</th><th>등급</th><th>출처 · 메모</th></tr>${PV.slice().sort((a, b) => (order[g(a)] ?? 3) - (order[g(b)] ?? 3)).map(provRow).join("")}</table><div class="hint">${GRADE_LEGEND.prov}</div>`;
  secs += esect(3, "무엇을 근거로 움직이나 · 입력 출처표", `입력 ${PV.length}개의 출처와 등급입니다 (◎ ${nG("◎")} · ○ ${nG("○")} · △ ${nG("△")}). 근거가 약한 △부터 보입니다.`, p3, d3);
  const TM = LIB.trait_model || {};
  const nPart = Object.keys(TM.always_on || {}).length;
  const d4 = `<table class="t rt"><tr><th>성향</th><th>지금 모델에서</th></tr>${(TM.traits || []).map(k => `<tr><td>${esc(k)}</td><td>${(TM.always_on || {})[k] ? `<span class="tstate part">일부만 반영</span> <span class="hint">${esc(TM.always_on[k])}</span>` : TM.lam_trait > 0 ? `<span class="tstate on">반영</span>` : `<span class="tstate off">점수에 안 들어감</span>`}</td></tr>`).join("")}</table>`;
  const one4 = TM.lam_trait > 0 ? `후기에서 뽑은 성향이 강도 ${TM.lam_trait}로 행동 선택 점수에 들어갑니다.`
    : `후기에서 뽑은 성향 점수는 지금 행동 선택 점수에 반영되지 않습니다 (강도 0${nPart ? ` · 일부만 쓰이는 것 ${nPart}개` : ""}).`;
  secs += esect(4, "손님 성향은 지금 어떻게 쓰이나", one4, traitNote(), d4);
  const byOp = o => HY.filter(x => hOp(x) === o);
  const OPS = ["모델 기본값 반영", "영향 미미", "외부 근거 보강 필요", "현장 확인 필요"];
  const p5 = OPS.map(o => byOp(o).length ? `${o} ${byOp(o).map(hLabel).join(" · ")}` : "").filter(Boolean).join(", ") + ".";
  const d5 = `<table class="t rt"><tr><th>가설</th><th>운영 표시</th><th>근거</th><th>다음 확인</th></tr>${HY.map(x => `<tr><td><b>${hLabel(x)}</b> ${esc(hName(x))}</td><td><span class="hstate ${HSTATE_CLS[hOp(x)] || ""}">${esc(hOp(x))}</span></td><td class="hint">${esc((x.근거 || "").slice(0, 260))}</td><td class="hint">${esc(x["다음 확인"] || "")}</td></tr>`).join("")}</table>`;
  const d5f = `<div class="hint">후기 59 체류에서 성향을 켜고 끄거나 예약 · 식사 포함 혜택 정보를 빼 본 결과는 '행동 역추적' 화면에서 조건을 골라 볼 수 있습니다.</div>`;
  let LP = null; try { LP = await (await fetch("/static/llm_pilot.json")).json(); } catch (e) {}
  const d5l = LP ? llmPilotBlock(LP) : "";
  secs += esect(5, "가설과 실험 · 행동 결정 요인", `가설 ${HY.length}개(${OPS.map(o => `${o} ${byOp(o).length}`).join(" · ")})와, 후기 59 체류에서 어떤 정보가 행동을 설명하는지 가른 결과입니다: 성향을 켜면 Brier 0.120 → 0.131, 예약 정보를 빼면 0.136.`,
    `가설은 같은 손님으로 조정값 하나만 바꿔 시드 3~10개를 짝지어 비교하고, 결과를 운영 표시로 나눕니다. ${p5} 아래 '행동 결정 요인 분석' 은 후기 손님 59 체류를 같은 난수로 돌리며 성향을 켜고 끄거나 직접 정보(예약 · 식사 포함 혜택)를 빼 본 결과입니다.` +
    (LP ? ` LLM 행동 선택 파일럿: LLM 적용 시 재현율은 올랐으나 전체 예측 오차 개선은 확인되지 않아 확대를 보류했습니다.` : ""), d5 + d5f + d5l);
  const p6 = `손님 근거(후기 · SNS · 현장) → 행동 근거 → 모델 결과 → 교차 근거 → 예측 문장을 한 줄로 묶은 기록이 ${CH.length}개 있습니다. 확실성과 한계, 다음 확인을 같이 적습니다.`;
  const d6 = `<div class="ecards">${CH.map(c => `<div class="ecard"><div class="eid">${esc(c["근거ID"] || "")} · ${gradeChip(c["확실성"])} ${esc(String(c["확실성"] || "").replace(/^[◎○△]\s*/, ""))}</div><div class="ep">${esc(c["예측문장"] || "")}</div><dl>` +
    [["손님", "고객근거"], ["행동", "행동근거"], ["모델", "모델결과"], ["교차", "교차근거"], ["한계", "반대사례_한계"], ["다음", "다음확인"]].map(([a, k]) => c[k] ? `<dt>${a}</dt><dd>${esc(String(c[k]).slice(0, 220))}</dd>` : "").join("") + `</dl></div>`).join("")}</div>`;
  secs += esect(6, "근거 사슬", `외부 자료 → 행동 근거 → 모델 결과 → 교차 근거 → 예측 문장으로 이은 기록 ${CH.length}개입니다.`, p6, d6);
  const top = WEAK.slice(0, 3);
  const p7 = `근거가 약하면서 운영 요약의 숫자를 크게 움직이고, 현장에서 받을 수 있는 것부터 순서를 매겼습니다. ` +
    top.map((w, i) => `${i + 1}순위 <b>${w.name}</b>: ${w.line}`).join(" ") +
    ` 1순위는 더뷔페 조식 회차별 입장 · 대기 기록으로, 2순위는 만석 때 안내와 손님 행선지 기록으로 확인할 수 있습니다. ` +
    `10/16부터 순위는 같은 손님 · 같은 시드에서 가정 하나씩 바꿔 잰 영향(근거사슬 7-16)을 따릅니다. 표의 범위는 신뢰구간이 아니라 검토한 가정에서 나온 결과 범위이고, 예측이 좋아졌다는 뜻이 아니라 결과가 그 가정에 얼마나 민감한지를 뜻합니다.`;
  const d7 = `<table class="t rt"><tr><th>순위 · 약한 고리</th><th>근거 · 표본 · 반례</th><th>결과에 미치는 영향 (같은 조건 비교)</th><th>필요한 자료 · 확보 난이도</th><th>모델에서 바뀌는 자리</th><th>고칠 방법</th></tr>` +
    WEAK.map((w, i) => `<tr><td><b>${i + 1}. ${w.name}</b> <span class="g ${gradeCls(w.grade)}">${w.grade}</span></td><td>${w.ev}</td><td>${w.sens}</td><td>${w.need} <span class="hint">· ${w.ease}</span></td><td class="hint">${w.where}</td><td><b>${w.fix || ""}</b>${w.fixNote ? `<div class="hint">${w.fixNote}</div>` : ""}</td></tr>`).join("") +
    `</table><div class="hint">고칠 방법: '현장 · 공개 자료' 는 자료가 오면 값을 바꾸는 것, '모델 선택지 분리' 는 자료와 별개로 가능한 행동을 다시 정의해야 하는 것. 체크인 날 하나만 계산해 2박째 손님이 빠지는 것은 근거가 아니라 계산 범위 문제라 목록에서 뺐습니다. 10/15 기준 · 자세한 표는 근거사슬_가설실험_1014 7-11절. '결과에 미치는 영향' 에서 날짜가 붙은 예전 실험은 v4 이전 설정이라 방향만 참고합니다. 근거가 없으면 '없음' 으로 적었습니다.</div>`;
  let DV = null; try { DV = await (await fetch("/static/data_value.json")).json(); } catch (e) {}
  let EC = null; try { EC = await (await fetch("/static/evidence_check.json")).json(); } catch (e) {}
  secs += esect(7, "약한 고리와 다음에 확보할 자료", `추가 검증이 필요한 가정 ${WEAK.length}개와, 그 가정을 바꿨을 때 결과가 얼마나 움직이는지입니다. 1순위는 ${WEAK[0].name}입니다 (조식 2부 초과 수요 198~546명 · 가정 범위).` +
    (DV ? ` 아래 '데이터 기여도 · 추가 데이터 가치' 는 어떤 정보가 행동 예측에 실제로 기여했고, 어떤 자료가 더해지면 무엇을 검증할 수 있는지 정리한 것입니다.` : ""), p7, d7 + (DV ? dataValueBlock(DV) : "") + (EC ? evidenceCheckBlock(EC) : ""));
  const xtra = (id, t, s, body) => `<details class="x19-xtra" id="${id}"><summary><span class="rnum">+</span><span class="eh"><b>${t}</b><span class="eone">${s}</span></span><span class="echev" aria-hidden="true"></span></summary><div class="x19-xbody">${body}</div></details>`;

  const viewFind = `<section class="x19-view" data-v="find"${EV.view === "find" ? "" : " hidden"}>${rxActionPanel()}${rxFind()}</section>`;
  const viewBench = `<section class="x19-view" data-v="bench"${EV.view === "bench" ? "" : " hidden"}>` +
    `<div class="x19-sechead"><h2>행동 역추적</h2><span class="d">관측된 행동에서 출발해, 어떤 정보가 그 선택을 설명하는지 <b>저장된 실험 결과</b>로 비교합니다 · 개발 자료 안의 탐색이며 실제 고객 행동의 인과 검증이 아닙니다</span></div>` +
    `<div id="labMain" class="x19-benchwrap"><div class="hint">실험 결과를 읽는 중입니다…</div></div>` +
    `<section class="x19-card2 x19-stay" id="labStay"></section></section>`;
  const viewDetail = `<section class="x19-view" data-v="detail"${EV.view === "detail" ? "" : " hidden"}>` +
    `<div class="x19-sechead"><h2>상세 검증 · 연구 근거</h2><span class="d">필요할 때 펼쳐 보는 전문 분석 ①~⑦ 과 보조 기능 · 내용은 그대로이며 처음에는 접혀 있습니다</span><span class="x19-sp"></span><button type="button" class="x19-btn sm evall">모두 펼치기</button></div>` +
    `<div class="x19-acc" id="evDetail">${secs}` +
    xtra("evPayBox", "후기의 실제 추가 결제", "확보한 후기의 결제 기록만 합산 · 호텔 월 매출이나 시뮬레이션 매출이 아님", `<div class="ev-pay"><div class="pane" id="evPay"></div></div>`) +
    xtra("evAssistBox", "운영 어시스턴트 질문", "판단 근거에 관한 질문을 골라 답과 근거 위치를 봅니다", `<aside class="rassist inpage" id="eAssist"></aside>`) +
    xtra("evFindBox", "이전 요약 · 이번 분석에서 드러난 점", "행동 역추적 결과를 세 카드로 요약했던 기존 화면 (내용 동일)", `<section class="lab-card lab-find" id="labFind"></section>`) +
    `</div><div class="x19-runinfo">${run}</div></section>`;

  el.innerHTML = `<div class="x19 ev2">${x19Subnav()}<div class="x19-page">${viewFind}${viewBench}${viewDetail}</div></div>`;
  el.querySelectorAll(".x19-sub [data-v]").forEach(b => b.onclick = () => x19SetView(b.dataset.v));
  rxBind(el);
  x19BindFind(el);
  renderObservedPayments(el.querySelector("#evPay") || el);
  const secEls = [...el.querySelectorAll(".esec")];
  const allBtn = el.querySelector(".evall");
  const syncAll = () => { allBtn.textContent = secEls.every(x => x.open) ? "모두 접기" : "모두 펼치기"; };
  secEls.forEach(x => x.addEventListener("toggle", () => { const n = +x.dataset.n; x.open ? EV.open.add(n) : EV.open.delete(n); syncAll(); }));
  allBtn.onclick = () => { const to = !secEls.every(x => x.open); secEls.forEach(x => x.open = to); syncAll(); };
  syncAll();
  assistSet({ page: "evidence", D }, "eAssist");
  drawLab();
  x19SetView(EV.view, { keepHash: true, keepScroll: true });
  if (EV_ACTION.cur && EV.view === "find") { const m = document.querySelector("main"); if (m) m.scrollTop = 0; }
  if (EV.go) { const n = EV.go; EV.go = 0; evOpen(n); }   // 운영 요약 카드 · 어시스턴트 '관련 근거' 에서 들어온 경우
  fillHoldout();
}

// 기준일 · 기준일 외 날짜 — v4 · 행사 없음 · 전체 규모로 계산해 둔 날을 날짜별로 모아 업장별 온톨로지 대비의 시드 평균 · 범위
const HOLD_USED = { "2026-10-10": "기준일 (정합 조정)", "2026-10-07": "평일 배율 조정에 참고", "2026-10-14": "평일 배율 확인에 참고" };
function sameV4(th, ds) { const a = Object.assign({}, th || {}); delete a.seed; const b = v4For(ds); const ka = Object.keys(a).filter(k => a[k] != null && a[k] !== 0 && a[k] !== false).sort(), kb = Object.keys(b).sort(); return ka.length === kb.length && ka.every((k, i) => k === kb[i] && a[k] === b[k]); }
async function fillHoldout() {
  const box = document.getElementById("evHold");
  if (!box || EV.busy) return;
  EV.busy = true;
  try {
    if (!EV.holdout) {
      const list = await api("/api/day/list");
      const keys = list.filter(d => d.scenario === "none" && +d.scale === 1 && d.theta && sameV4(d.theta, d.date) && d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver);
      const byDate = {};
      for (const d of keys) {
        const D = await ensureDay(d.key);
        const VO = venueOnto(D);
        const x = (byDate[D.date] = byDate[D.date] || { date: D.date, seeds: 0, net: [], ven: {} });
        x.seeds++; x.net.push(D.total / 1.1);
        for (const [loc, r] of Object.entries(VO)) if (r.onto) (x.ven[loc] = x.ven[loc] || []).push(r.model / r.onto * 100);
        if (!(D.theta || {}).seed) { x.s0 = {}; for (const [loc, r] of Object.entries(VO)) if (r.onto) x.s0[loc] = r.model / r.onto * 100; }   // 10/19 UX 22차 — 운영 요약이 보여 주는 '선택한 실행(시드 0)'
      }
      EV.holdout = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
    }
    const R = EV.holdout;
    if (!R.length) { box.innerHTML = `<div class="hint">지금 버전으로 계산해 둔 ${V4N} 날이 없습니다. '고객 흐름' 에서 하루를 돌리면 여기에 모입니다.</div>`; return; }
    const dl = ds => `${ds.slice(5).replace("-", "/")} (${"일월화수목금토"[new Date(ds + "T12:00:00").getDay()]})`;
    const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
    const locs = [...new Set(R.flatMap(x => Object.keys(x.ven)))];
    const cell = (arr, l) => { if (!arr || !arr.length) return `<td class="n">-</td>`; const m = mean(arr), tbd = UNIT_TBD.has(l), off = !tbd && !inBand9011(m), far = !tbd && (m < 80 || m > 120);   // 10/19 원값 기준 (마지막 칸 개수 · 운영 요약과 같게)
      return `<td class="n${off ? " neg" : ""}${tbd ? " hint" : ""}" style="${far ? "font-weight:700" : ""}">${pctBand(m)}${tbd ? " △" : ""}${arr.length > 1 ? `<div class="hint">${Math.round(Math.min(...arr))}~${Math.round(Math.max(...arr))}</div>` : ""}</td>`; };
    box.innerHTML = `<div style="overflow-x:auto"><table class="t rt"><tr><th>날</th><th class="n">시드</th><th class="n">체류 매출</th>${locs.map(l => `<th class="n">${esc(locName(l))}</th>`).join("")}<th class="n">90~110% 안<div class="hint">반복 평균</div></th></tr>` +
      R.map(x => { const ms = locs.filter(l => !UNIT_TBD.has(l)).map(l => x.ven[l] ? mean(x.ven[l]) : null).filter(v => v != null), inb = ms.filter(inBand9011).length;
        const s0 = x.seeds > 1 && x.s0 ? locs.filter(l => !UNIT_TBD.has(l) && x.s0[l] != null).map(l => x.s0[l]) : null;
        return `<tr><td>${dl(x.date)}<div class="hint">${HOLD_USED[x.date] || (isWeekday(x.date) ? "평일" : "주말 · 공휴일")}</div></td><td class="n">${x.seeds}</td>` +
          `<td class="n">${eok(mean(x.net))}${x.net.length > 1 ? `<div class="hint">${(Math.min(...x.net) / 1e8).toFixed(2)}~${(Math.max(...x.net) / 1e8).toFixed(2)}억</div>` : ""}</td>` +
          locs.map(l => cell(x.ven[l], l)).join("") + `<td class="n"><b>${inb}/${ms.length}</b>${s0 && s0.length ? `<div class="hint" title="운영 요약 · 고객 흐름이 보여 주는 선택한 실행 하나(시드 0)의 같은 판정">시드 0 한 번: ${s0.filter(inBand9011).length}/${s0.length}</div>` : ""}</td></tr>`; }).join("") + `</table></div>` +
      `<div class="hint">칸 = 업장별 모델 이용 ÷ 온톨로지 이용의 시드 평균 (풀 단위를 맞춰 합침), 아래 숫자 = 시드별 최소~최대. 빨강은 평균이 90~110% 밖, 굵게는 80~120% 밖. ${UNIT_TBD_NOTE} (마지막 칸은 나머지 업장만 셈 · 굵은 숫자는 시드 여러 개의 <b>반복 평균</b>, 그 아래는 운영 요약이 보여 주는 <b>선택한 실행(시드 0 한 번)</b> — 판정 규칙은 같고 집계 대상만 다릅니다). 평일은 비투숙 손님 배율 0.5(H4b)가 들어간 값입니다. ` +
      `시드 범위는 지금 가정과 모델을 고정했을 때 우연만 바꿔 생기는 변동이지, 실제 매출 예측의 신뢰구간이 아닙니다.</div>`;
  } catch (e) { box.innerHTML = `<div class="hint">불러오지 못했습니다: ${esc(e.message)}</div>`; }
  finally { EV.busy = false; }
}

function renderSettings() {
  const th = knobCfg(), ds = $("#dDate").value;
  const K = LIB.knobs || {};
  const v4 = v4For(ds);
  const TM = LIB.trait_model || {};
  $("#settingsHead").innerHTML = `<div class="rhead"><div><div class="rtitle">모델 설정</div>` +
    `<div class="rsub">지금 설정: ${esc(knobSummary({ theta: th, date: ds }))} · 모델 ${esc(LIB.model_ver || "-")} · 입력 ${esc(LIB.input_ver || "-")}</div></div></div>` +
    `<div class="rlead">운영 판단에는 기본 모델(${V4_LABEL()})을 씁니다. 여기서 조정값을 바꾸면 '고객 흐름' 의 하루 돌리기에 그대로 반영되고, 결과 화면에는 어떤 설정으로 돌렸는지가 함께 표시됩니다. 조정값을 바꾼 결과는 같은 설정끼리만 비교합니다.</div>`;
  $("#settingsInfo").innerHTML = `<div class="setbox"><h4 style="margin:0 0 6px">${V4N} 기본에 들어 있는 것 <span class="hint">(${isWeekday(ds) ? "평일" : "주말 · 공휴일"} 기준)</span></h4>` +
    `<table class="t rt"><tr><th>조정값</th><th class="n">${V4N} 값</th><th class="n">지금</th></tr>${Object.keys(v4).map(k => `<tr><td>${esc(nmDisp((K[k] || {}).name || k))}</td><td class="n">${v4[k]}</td><td class="n${th[k] !== v4[k] ? " neg" : ""}">${th[k] ?? "끔"}</td></tr>`).join("")}</table>` +
    `<div class="hint" style="margin-top:8px">행동 점수 계수는 후기 46편 교차검증으로 정한 값(에이전트 v4)을 그대로 쓰고, 성향 강도는 ${TM.lam_trait ?? "-"}입니다. 계수 자체는 화면에서 바꾸지 않습니다.</div></div>`;
}

// ── 운영 조건 비교 (A/B · 10/14) ─────────────────────────────────────────────
// 같은 날 · 같은 손님(같은 시드)에서 운영 조건 하나만 바꾼 결과를 나란히. 시뮬레이션은 이미 돌려 둔 시드 묶음(band)을 쓰고,
// '어떤 고객이 바뀌었나' 는 시드 0 의 두 하루를 고객 이동 정산(check_flow)으로 맞대 본다
let AB_LAST = null;     // 오른쪽 패널(풀린 팀 목록)에 쓰려고 마지막 A/B 결과를 둔다
const AB_TXT = { buffet_seats: v => `더뷔페 좌석 288석 → ${v}석${+v === 338 ? " (테라스 50석을 식사에 쓰는 경우)" : ""}` };
async function abCard(D) {
  const wk = isWeekday(D.date);
  const sig = t => JSON.stringify(Object.entries(t || {}).filter(([k, v]) => !["anomaly", "anomaly_k", "seed", "buffet_seats"].includes(k) && !(!wk && WEEKDAY_ONLY.includes(k)) && v != null && v !== 0 && v !== false).sort());
  const ALL = (await api("/api/bands")).filter(b => b.compare && b.compare.buffet_seats && !b.compare.anomaly && b.date === D.date && b.model_ver === LIB.model_ver && b.input_ver === LIB.input_ver && sig(b.theta) === sig(D.theta));
  const b = ALL[0];
  if (!b) return null;
  const E = b.effect || {}, n = b.seeds;
  const f1 = (e, u, d = 0) => e ? `<b style="${sureEffect(e, n) ? "" : "font-weight:400;color:var(--ink2)"}">${e.diff > 0 ? "+" : ""}${(+e.diff).toFixed(d)}${u}</b><div class="hint">95% 구간 ${(+e.lo95).toFixed(d)} ~ ${(+e.hi95).toFixed(d)}${sureEffect(e, n) ? "" : " · 흔들림과 구분 안 됨"}</div>` : "-";
  const row = (name, key, u, d) => `<tr><td>${name}</td><td class="n">${b.base[key] ? (+b.base[key].mean).toFixed(d) + u : "-"}</td><td class="n">${f1(E[key], u, d)}</td></tr>`;
  const others = Object.entries(E).filter(([k, e]) => / 이용 \(명\)$/.test(k) && !/더뷔페/.test(k) && sureEffect(e, n));
  // 어떤 고객이 바뀌었나 — 시드 0 두 하루의 정산 기록
  let who = "", why2 = "";
  try {
    const [FA, FB, DB, DA] = await Promise.all([flowOf(b.base_key), flowOf(b.compare_key), ensureDay(b.compare_key), ensureDay(b.base_key)]);
    // 회차별 모양 — 조식은 1부 여유 · 2부 몰림인지 (10/14 08:30 집중 점검)
    const bw = X => ((X.venue_detail || {}).THE_BUFFET || {}).windows || [];
    const brk = X => bw(X).filter(w => w.kind === "조식" && (w.persons || w.over_persons));
    const wTxt = X => brk(X).map(w => `${w.name.replace(" (익일)", "").replace("조식 ", "")} ${w.persons}명${w.over_persons ? ` · 초과 ${w.over_persons}명` : " · 여유"}`).join(", ");
    if (brk(DA).length > 1) why2 = ` 조식은 회차별로 보면(시드 0) A ${wTxt(DA)} → B ${wTxt(DB)}입니다. 1부에 자리가 남고 2부에 몰리는 구조라서, 같은 손님을 1부로 나눠 안내하는 방법도 비슷한 효과를 낼 수 있습니다(실험하지 않음). 2부 시작(08:30)에 제약이 몰려 보이는 것은 회차 경계와 30분 단위 기상 시각 가정(△)의 영향이 큽니다.`;
    if (!FA.error && !FB.error) {
      const isBuf = e => /더뷔페/.test(e.from) && e.meal;
      const A = {}, B = {};
      (FA.events || []).filter(isBuf).forEach(e => { A[e.id] = A[e.id] || e; });
      (FB.events || []).filter(isBuf).forEach(e => { B[e.id] = B[e.id] || e; });
      const freed = Object.values(A).filter(e => !B[e.id]), added = Object.values(B).filter(e => !A[e.id]);
      const gB = Object.fromEntries((DB.guests || []).map(g => [g.id, g]));
      const ate = freed.filter(e => ((gB[e.id] || {}).acts || []).some(a => a === e.from || a.startsWith("더뷔페")));
      const byMeal = {}; freed.forEach(e => { byMeal[e.meal] = (byMeal[e.meal] || 0) + 1; });
      const gA = Object.fromEntries((DA.guests || []).map((g, i) => [g.id, Object.assign({ _i: i }, g)]));
      AB_LAST = { date: D.date, b, freed: freed.map(e => ({ e, g: gA[e.id] || {}, ate: ate.includes(e), gb: gB[e.id] || {} })), added: added.map(e => ({ e, g: gB[e.id] || {} })), nA: Object.keys(A).length, nB: Object.keys(B).length };
      const inc = freed.filter(e => e.included).length;
      const stay = freed.filter(e => (gB[e.id] || {}).is_guest).length;
      who = `<h5>어떤 고객이 바뀌었나 <span class="hint">· 시드 0 의 두 하루 · 고객 이동 정산 기록</span></h5>` +
        `<div style="font-size:12.5px;line-height:1.7">더뷔페에서 좌석 제약을 겪은 팀이 ${Object.keys(A).length}팀 → ${Object.keys(B).length}팀이 됐습니다. ` +
        `제약이 풀린 ${freed.length}팀은 ${Object.entries(byMeal).map(([m, c]) => `${m} ${c}팀`).join(" · ")}이고, 그중 ${ate.length}팀이 실제로 더뷔페에서 먹었습니다. ` +
        `풀린 팀의 ${pct(stay, freed.length)}%가 투숙객, ${pct(inc, freed.length)}%가 그 식사를 객실 상품에 포함한 팀입니다.` +
        (added.length ? ` 반대로 ${added.length}팀은 좌석이 늘어난 조건에서 새로 제약을 겪었습니다(다른 손님이 먼저 자리를 잡아 차례가 밀린 경우).` : "") + `</div>`;
    }
  } catch (e) { who = ""; }
  const h = `<h5>운영 조건을 바꾸면? <span class="hint">(같은 날 · 같은 손님 · 시드 ${n}쌍 짝 비교)</span></h5>` +
    `<div style="font-size:14px;font-weight:700;margin:2px 0 4px">A 지금 운영 vs B ${esc(AB_TXT.buffet_seats(b.compare.buffet_seats))}</div>` +
    `<div class="abnote">가상 실험 · 좌석 수(공급량)만 바꿨고 인력 · 서비스 속도는 그대로, 좌석을 늘리는 비용은 넣지 않았습니다. 아래 범위는 같은 조건을 반복 실행했을 때의 95% 구간이며, 실제 도입 효과의 예측 구간이 아닙니다.</div>` +
    `<table class="t"><tr><th>지표</th><th class="n">A (시드 평균)</th><th class="n">B − A <span class="hint">(95% 구간)</span></th></tr>` +
    row("더뷔페 이용 · 중식 · 석식 · 다음날 중식", "더뷔페 이용 (명)", " 인 · 회", 0) + (E["더뷔페 다음날 조식 이용 (명)"] ? row("더뷔페 이용 · 다음날 조식", "더뷔페 다음날 조식 이용 (명)", " 인 · 회", 0) : "") + row("더뷔페 초과 수요 (막힌 팀의 일행 수)", "더뷔페 초과 수요 (명)", "명", 0) +
    row("공급 제한을 겪은 팀 (호텔 전체)", "공급 제한 겪은 팀 (팀)", "팀", 0) + row("더뷔페 비투숙 팀", "더뷔페 비투숙 팀 (팀)", "팀", 0) +
    row("체류 매출", "순매출 (억)", "억", 2) + row("그날 지출", "그날 지출 (억)", "억", 2) + `</table>` +
    `<div class="hint">다른 업장 이용 변화: ${others.length ? others.map(([k, e]) => `${k.replace(" 이용 (명)", "")} ${e.diff > 0 ? "+" : ""}${Math.round(e.diff)}명`).join(" · ") : "흔들림과 구분되는 변화 없음"}${E["르파사쥬 (건)"] && sureEffect(E["르파사쥬 (건)"], n) ? ` · 르파사쥬 ${Math.round(E["르파사쥬 (건)"].diff)}건` : ""}. 굵은 숫자는 짝지은 차이의 95% 구간이 0을 넘지 않는 변화(모델 반복 변동성 기준, 예측 구간 아님). A 는 시드 ${n}개 평균이라 운영 요약 · 고객 흐름 화면의 숫자(시드 0 한 번)와 조금 다릅니다. 중식 · 석식 인원은 온톨로지 날짜 대조와 같은 정의(그 날 중식 · 석식 + 다음날 중식)이고, 이 날 체크인 손님의 다음날 조식은 따로 셉니다.</div>` +
    who +
    `<h5>왜 이런 결과가 나왔나</h5><div style="font-size:12.5px;line-height:1.7">좌석이 늘어난 만큼 가장 붐비는 회차(조식 2부 · 석식 1부)에 들어갈 수 있는 팀이 늘었습니다. 늘어난 50석이 중식 · 석식에서 ${E["더뷔페 이용 (명)"] ? Math.round(E["더뷔페 이용 (명)"].diff) : "-"}명${E["더뷔페 다음날 조식 이용 (명)"] ? `, 다음날 조식에서 ${Math.round(E["더뷔페 다음날 조식 이용 (명)"].diff)}명` : ""}을 더 받는 것은 회차제 좌석을 회차 끝까지 잡는 가정(조정값 '회차제 좌석 회차 끝까지')과 회차 수에서 나옵니다. 그래도 제약을 겪는 팀이 대부분 남는 것은 좌석 총량보다 특정 회차에 수요가 몰리기 때문입니다.${why2}</div>` +
    `<h5>도입 전에 확인할 자료</h5><div style="font-size:12.5px;line-height:1.7">테라스 50석을 조식 · 석식에 쓸 수 있는지(연회 일정 · 인력 · 동선), 실제 더뷔페 회차별 대기와 포기 기록, 조식 포함 손님이 실제로 얼마나 기다리는지(모델은 회차 안 줄 서기 30분 가정). 좌석 늘리기의 비용은 모델에 없습니다.</div>` +
    `<div class="row" style="gap:8px;margin-top:8px"><button class="ghost" data-abday="${esc(b.base_key)}">A 하루 열기</button><button class="ghost" data-abday="${esc(b.compare_key)}">B 하루 열기</button></div>`;
  return { id: "ab", loc: "THE_BUFFET", wide: true, h };
}

// 상황 비교 오른쪽 — A/B 에서 제약이 풀린 팀 · 새로 막힌 팀. 누르면 B 하루에서 그 손님이 왜 그렇게 골랐는지
function abPanel() {
  const X = AB_LAST; if (!X) return;
  const row = (r, tag) => { const g = r.g || {};
    return `<tr class="click" data-i="${g._i ?? ""}" data-id="${esc(r.e.id)}"><td>${g.is_guest ? (PROPS[g.property] || "") + " " + g.nights + "박" : "비투숙"} · ${g.party || "-"}인${g.kids ? " · 아이" : ""}<br><span class="hint">${esc(g.purpose || "")}${r.e.included ? " · 식사 포함 혜택" : ""}</span></td><td style="font-size:11.5px">${esc(r.e.from)}<br><span class="hint">A: ${esc(r.e.final_at || r.e.final || altName(r.e.to))}</span></td><td style="font-size:11.5px">${tag}</td></tr>`; };
  let h = `<div class="card"><h4 style="font-size:15px">좌석을 늘리면 누가 달라지나</h4><div class="hint">시드 0 의 A · B 하루를 고객 이동 정산 기록으로 맞댄 결과입니다. 더뷔페에서 좌석 제약을 겪은 팀 ${X.nA}팀 → ${X.nB}팀.</div></div>`;
  h += `<div class="card"><h4>제약이 풀린 ${X.freed.length}팀 <span class="hint">· 누르면 B 하루의 그 손님</span></h4><table class="t"><tr><th>손님</th><th>A에서 막힌 곳 · 결과</th><th>B 더뷔페</th></tr>` +
    X.freed.map(r => row(r, r.ate ? `<b style="color:var(--pos)">이용</b>` : "다른 선택")).join("") + `</table></div>`;
  if (X.added.length) h += `<div class="card"><h4>B에서 새로 막힌 ${X.added.length}팀</h4><table class="t">${X.added.map(r => row(r, "새로 제약")).join("")}</table><div class="hint">다른 손님이 먼저 자리를 잡아 차례가 밀린 경우입니다.</div></div>`;
  $("#panel").innerHTML = h;
  $$("#panel tr.click[data-i]").forEach(tr => tr.onclick = async () => { const i = tr.dataset.i; if (i === "") return; setMode("day"); await loadDay(X.b.compare_key); openDayGuest(+i, () => { setMode("ask"); }); });
}


// 10/16 행동 역추적 — static/factor_eval.json(실제 실험 결과)만 읽는다. 새로 계산하거나 측정하지 않은 조합의 숫자를 만들지 않는다
let FACTOR = null;
async function loadFactor() {
  if (FACTOR) return FACTOR;
  const r = await fetch("/static/factor_eval.json"); FACTOR = deName(await r.json()); return FACTOR;
}
EV.lab = EV.lab || { group: "all", book: 1, incl: 1, trait: "0", stay: null, place: null };
const LAB_SHORT = { A: "기본 모델", A0: "성향 완전 제외", B1: "성향 강도 1", B2: "성향 강도 2", C1: "예약 정보 제외", C2: "식사 포함 혜택 제외", C3: "예약 · 혜택 모두 제외" };
const LAB_TRAIT = [["off", "제외"], ["0", "기본 (0)"], ["1", "강도 1"], ["2", "강도 2"]];
function labCond(F) {     // 지금 고른 요인 조합이 측정한 조건 중 하나인가
  const L = EV.lab;
  return F.cond.find(c => c.sel.book === L.book && c.sel.incl === L.incl && c.sel.trait === L.trait) || null;
}
// Brier 변화 판정 — Brier 는 낮을수록 좋으므로 올라가면 확률 예측 성능 악화
function labVerdict(d) {
  if (d == null) return { cls: "", t: "" };
  if (d > 0.01) return { cls: "bad2", t: "확률 예측 성능 크게 악화" };
  if (d > 0.003) return { cls: "bad", t: "확률 예측 성능 악화" };
  if (d < -0.003) return { cls: "good", t: "확률 예측 성능 개선" };
  return { cls: "flat", t: "차이 거의 없음" };
}
const labD = (v, dig) => { const a = Math.abs(v).toFixed(dig); return `${+a === 0 ? "±" : v > 0 ? "+" : "−"}${a}`; };
const pct1 = v => (+v).toFixed(1);
// 조건마다 '무엇을 바꿨나' 를 문장으로 (결과 해석 문구에 쓴다)
const LAB_ACT = { A0: "후기 성향을 완전히 빼자", B1: "후기 성향을 강도 1로 넣자", B2: "후기 성향을 강도 2로 넣자",
  C1: "후기에 기록된 예약 정보를 제거하자", C2: "식사 포함 혜택 정보를 제거하자", C3: "예약 정보와 식사 포함 혜택을 모두 제거하자" };
function labRead(cid, base, r) {
  const dR = r.recall - base.recall, dB = r.brier - base.brier;
  const dir = dR <= -0.5 ? "감소했습니다" : dR >= 0.5 ? (dR < 2 ? "소폭 증가했습니다" : "증가했습니다") : "거의 같았습니다";
  let t = `${LAB_ACT[cid] || "조건을 바꾸자"} 재현율은 ${pct1(base.recall)}%에서 ${pct1(r.recall)}%로 ${dir}.`;
  if ((dR >= 0.5 && dB > 0.003) || (dR <= -0.5 && dB < -0.003))
    t += ` 재현율과 Brier 가 다른 방향으로 움직였습니다. 재현율은 간 곳을 맞혔는지만 보고, Brier 는 장소마다 갈 확률 전체를 봅니다.`;
  return t;
}

// 전체 59 체류에서 이 조건의 Brier 차이가 체류별 짝 차이의 2 표준오차를 넘는가 (넘으면 true · 안 넘으면 false · 판단 못 하면 null)
function labSig(F, G, cid) {
  if (!G || G.id !== "all" || cid === "A" || !F.stays) return null;
  const dd = F.stays.filter(x => x.res && x.res.A && x.res[cid]).map(x => x.res[cid].brier - x.res.A.brier);
  if (dd.length < 3) return null;
  const mu = dd.reduce((a, b) => a + b, 0) / dd.length, se = Math.sqrt(dd.reduce((a, b) => a + (b - mu) ** 2, 0) / (dd.length - 1) / dd.length);
  return se > 0 ? Math.abs(mu) >= 2 * se : null;
}
// 10/16 UX P0-4 · ③ 맨 위 결론 한 문장 — 고른 조건의 실제 비교 결과로만 만든다 (바꾸지 않은 요인에 대한 결론은 쓰지 않음)
const LAB_IF = { A0: "후기 성향을 완전히 빼면", B1: "후기 성향을 강도 1로 넣으면", B2: "후기 성향을 강도 2로 넣으면",
  C1: "예약 정보를 빼면", C2: "식사 포함 혜택 정보를 빼면", C3: "예약 정보와 식사 포함 혜택을 모두 빼면" };
function labConcl(cid, base, r) {
  const v = labVerdict(r.brier - base.brier).cls, dR = r.recall - base.recall;
  const b = { bad2: "확률 예측이 크게 나빠지고", bad: "확률 예측이 나빠지고", good: "확률 예측이 좋아지고", flat: "확률 예측은 거의 같고" }[v] || "";
  const rc = dR <= -0.5 ? "줄어듭니다" : dR >= 0.5 ? "늘어납니다" : "거의 같습니다";
  return `${LAB_IF[cid] || "이 조건에서는"} ${b}, 후기에서 간 곳을 맞히는 비율(재현율)은 ${rc}.`;
}
const LAB_HELP = { brier: "장소마다 '갈 확률' 과 실제로 갔는지(1 · 0)의 차이를 제곱해 평균한 값. 낮을수록 실제 선택에 가깝습니다.",
  recall: "후기에서 실제로 간 곳 중 모델 손님도 간 곳의 비율", precision: "모델 손님이 간 곳 중 후기에서도 간 곳의 비율" };
const labQ = k => `<span class="lab-help" tabindex="0" title="${esc(LAB_HELP[k])}" aria-label="${esc(LAB_HELP[k])}">?</span>`;
function x19Bench(steps, colA, colB, colC) {
  return `<div class="x19-bench"><div class="bh">${steps.map(([t, v], i) => `<div class="stp ${i === 3 ? "on" : "done"}"><i>${i + 1}</i><span><b>${t}</b><small>${esc(v || "")}</small></span></div>`).join("")}</div>` +
    `<div class="bb"><div class="col ca">${colA}</div><div class="col cb">${colB}</div><div class="col cc"><h4>4 · 결과 해석</h4>${colC}</div></div>` +
    `<div class="bf"><span>저장된 실험 결과(<code>factor_eval.json</code> · Eval-K12 · 59 체류 · 12회)를 읽어 보여 줍니다 · 화면에서 다시 계산하지 않으며, 측정하지 않은 조합은 숫자를 만들지 않습니다</span></div></div>`;
}
async function drawLab() {
  const box = document.getElementById("labMain"); if (!box) return;
  let F;
  try { F = await loadFactor(); } catch (e) { box.innerHTML = `<div class="callout">실험 결과 파일을 읽지 못했습니다: ${esc(e.message)}</div>`; return; }
  const WI = await loadWait();
  const L = EV.lab, waitMode = L.group === "wait_inv" && !!WI;
  const G = F.groups.find(g => g.id === L.group) || F.groups[0], C = labCond(F);
  const base = G.res.A, r = C ? G.res[C.id] : null;

  // ① 분석 대상 — 관측 행동과 고객군을 나눠서
  const opt = g => `<button class="lab-opt ${!waitMode && g.id === G.id ? "on" : ""}" data-g="${g.id}"><b>${esc(g.name)}</b><small>${esc(g.sub)}</small><i class="lab-radio"></i></button>`;
  const plan = WI ? `<button class="lab-opt ${waitMode ? "on" : ""}" data-g="wait_inv"><b>대기 후 선택한 행동</b><small>후기 ${WI.cases.length} 체류 · 대기 회피 성향 역추정 · ${esc(WI.doc)}</small><i class="lab-radio"></i></button>` : (F.planned || []).filter(p => p.id === "wait_inv").map(p => `<div class="lab-opt off" title="${esc(p.note)}"><b>대기 후 선택한 행동</b><small>${p.n ? p.n + " 체류 · " : ""}${esc(p.name)} · 결과가 나오면 연결합니다</small><span class="lab-tag">${esc(p.status)}</span></div>`).join("");
  const s1 = `<section class="lab-card lab-s1"><h2><span class="lnum">1</span>분석 대상 선택</h2><p class="lab-hint">후기에서 관찰된 방문을 전체로 보거나, 손님 조건으로 나눈 고객군만 볼 수 있습니다.</p>
    <div class="lab-sub-h">관측 행동</div><div class="lab-opts">${F.groups.filter(g => g.kind === "behavior").map(opt).join("")}${plan}</div>
    <details class="x19-grp"${!waitMode && G.kind !== "behavior" ? " open" : ""}><summary class="lab-sub-h">고객군 ${F.groups.filter(g => g.kind !== "behavior").length}개${!waitMode && G.kind !== "behavior" ? ` · ${esc(G.name)}` : " 펼치기"}</summary><div class="lab-opts">${F.groups.filter(g => g.kind !== "behavior").map(opt).join("")}</div></details></section>`;
  if (waitMode) {
    box.innerHTML = x19Bench([["분석 대상", "대기 후 선택한 행동 · " + WI.cases.length + " 체류"], ["설명 요인", "대기 회피 값 " + wiV(WI).toFixed(1)], ["조건별 결과 비교", "관찰 선택 비율"], ["결과 해석", WI.verdict]],
      s1 + labWaitS2(WI), labWaitS3(WI), `<div class="x19-read"><b>지금 선택의 뜻</b><p>${esc(WI.verdict)}</p><p class="hint">후기 ${WI.cases.length} 체류의 탐색 결과이며 개인의 실제 성향이 아닙니다.</p></div><div class="x19-tags">${x19Tag("개발 자료 내 확인")}${x19Tag("미확정")}</div>`);
    box.querySelectorAll(".lab-opt[data-g]").forEach(b => b.onclick = () => { L.group = b.dataset.g; drawLab(); });
    box.querySelectorAll("[data-wv]").forEach(b => b.onclick = () => { L.wv = +b.dataset.wv; drawLab(); });
    box.querySelectorAll("[data-ww]").forEach(b => b.onclick = () => { L.ww = +b.dataset.ww; drawLab(); });
    drawLabFind(F); drawLabWaitCases(WI);
    return;
  }

  // ② 설명 요인 후보
  const chk = (k, name, sub) => `<label class="lab-fac ${L[k] ? "on" : ""}"><input type="checkbox" data-f="${k}" ${L[k] ? "checked" : ""}><span><b>${name}</b><small>${sub}</small></span></label>`;
  const s2 = `<section class="lab-card lab-s2"><h2><span class="lnum">2</span>설명 요인 후보 선택</h2><p class="lab-hint">모델에 넣을 정보를 고르세요. 빼 보면 그 정보가 행동을 얼마나 설명했는지 드러납니다.</p>
    <div class="lab-facs">${chk("book", "예약 정보", "후기에 적힌 방문 전 예약 사실")}${chk("incl", "식사 포함 혜택", "객실 상품에 포함된 식사")}
      <div class="lab-fac trait ${L.trait !== "0" && L.trait !== "off" ? "on" : ""}"><span><b>후기에서 뽑은 성향 7개</b><small>대기 회피 · 조망 · 조용함 · 격식 · 이동 · 새로움 · 함께 먹기</small></span>
        <div class="lab-seg">${LAB_TRAIT.map(([v, t]) => `<button data-t="${v}" class="${L.trait === v ? "on" : ""}">${t}</button>`).join("")}</div></div>
      <div class="lab-fac fixed"><span><b>방문 목적 · 아동 동반 · 공급 제약</b><small>모든 조건에 늘 들어 있는 기본 정보 · 빼 본 실험 없음</small></span><span class="lab-tag">항상 포함</span></div>
      ${(F.planned || []).filter(p => p.id !== "wait_inv").map(p => `<div class="lab-fac off" title="${esc(p.note)}"><span><b>${esc(p.name)}</b><small>${esc(p.note)}</small></span><span class="lab-tag">${esc(p.status)}</span></div>`).join("")}
    </div>
    <div class="lab-pick">${C ? `선택한 조합 = <b>${esc(C.name)}</b> <span class="hint">(측정한 조건)</span>` : `<b>측정하지 않은 조합입니다.</b> <span class="hint">정보를 하나씩 바꾼 조건만 실험했습니다. 숫자를 만들지 않습니다.</span>`}</div></section>`;

  // ③ 검증 결과 — 기본 모델과 바꾼 조건을 나란히, 무엇이 얼마나 달라졌나를 먼저
  const reps = ((F.sample || "").match(/(\d+)번/) || [])[1];
  let s3 = `<section class="lab-card lab-s3"><h2><span class="lnum">3</span>검증 결과 확인</h2><p class="lab-hint">${esc(G.name)} · ${G.n} 체류 · 같은 손님 · 같은 난수${reps ? `로 ${reps}번 반복해` : "로"} 기본 모델과 비교 <span class="lab-scope">반복 횟수는 표본 수가 아닙니다 · 표본은 후기 ${G.n} 체류</span></p>`;
  if (!r) {
    s3 += `<div class="lab-concl none">이 조합은 실험하지 않아 결론이 없습니다.</div><div class="lab-none">정보를 하나씩 바꾼 조건만 실험했습니다. 아래 목록에서 측정한 조건을 고르세요.</div>`;
  } else if (C.id === "A") {
    s3 += `<div class="lab-concl">기본 모델은 후기에서 간 곳의 ${pct1(base.recall)}%를 맞히고, 확률 오차(Brier)는 ${base.brier.toFixed(3)} 입니다. ② 에서 조건을 바꾸면 이 값과 비교합니다.</div>
      <div class="lab-vs one"><div class="lab-vs-c"><small>기본 모델 Brier ${labQ("brier")}</small><b>${base.brier.toFixed(3)}</b><span class="lab-dir">낮을수록 실제 선택에 가까움</span></div></div>
      <div class="lab-kv"><span>재현율 ${labQ("recall")} <b>${pct1(base.recall)}%</b></span><span>정밀도 ${labQ("precision")} <b>${pct1(base.precision)}%</b></span></div>`;
  } else {
    let dB = r.brier - base.brier, v = labVerdict(dB);
    // 10/16 · 전체 59 체류일 때는 체류별 짝 차이의 표준오차로 흔들림과 구분되는지 본다 (data_value.py 1단계와 같은 잣대 · 2 표준오차)
    let seNote = "";
    if (G.id === "all" && F.stays && F.stays.length > 2) {
      const dd = F.stays.filter(x => x.res && x.res.A && x.res[C.id]).map(x => x.res[C.id].brier - x.res.A.brier);
      const mu = dd.reduce((a, b) => a + b, 0) / dd.length, se = Math.sqrt(dd.reduce((a, b) => a + (b - mu) ** 2, 0) / (dd.length - 1) / dd.length);
      if (se > 0 && Math.abs(mu) < 2 * se) { v = { cls: "flat", t: "흔들림과 구분되지 않음" }; seNote = ` 체류별 차이의 표준오차 ±${se.toFixed(4)} 안이라 방향을 말하지 않습니다.`; }
      else if (se > 0) seNote = ` 체류별 차이의 표준오차 ±${se.toFixed(4)} (2배를 넘음).`;
    }
    const dR = r.recall - base.recall, split = (dR >= 0.5 && dB > 0.003) || (dR <= -0.5 && dB < -0.003);
    s3 += `<div class="lab-concl ${v.cls}">${v.cls === "flat" && seNote ? `${LAB_IF[C.id] || "이 조건에서는"} 확률 예측의 차이가 흔들림과 구분되지 않습니다.` : labConcl(C.id, base, r)}${seNote ? `<span class="lab-dir" style="display:block;font-weight:500;margin-top:4px">${seNote.trim()}</span>` : ""}</div>
      <div class="lab-vs"><div class="lab-vs-c"><small>기본 모델 Brier ${labQ("brier")}</small><b>${base.brier.toFixed(3)}</b></div><div class="lab-vs-ar" aria-hidden="true">→</div><div class="lab-vs-c ${v.cls}"><small>${esc(C.name)}</small><b>${r.brier.toFixed(3)}</b></div></div>
      <div class="lab-delta ${v.cls}"><span class="dl-arrow" aria-hidden="true">${dB > 0.0005 ? "▲" : dB < -0.0005 ? "▼" : "＝"}</span>Brier ${labD(dB, 4)} · ${v.t} <span class="lab-dir">${dB > 0.0005 ? "오차가 늘었음 = 예측이 나빠짐 (Brier 는 낮을수록 좋음)" : dB < -0.0005 ? "오차가 줄었음 = 예측이 좋아짐" : "Brier 는 낮을수록 좋음"}</span></div>
      ${split ? `<p class="lab-read">재현율과 Brier 가 다른 방향으로 움직였습니다. 재현율은 간 곳을 맞혔는지만 보고, Brier 는 장소마다 갈 확률 전체를 봅니다.</p>` : ""}
      <div class="lab-kv"><span>재현율 ${labQ("recall")} <b>${pct1(base.recall)}% → ${pct1(r.recall)}%</b></span><span>정밀도 ${labQ("precision")} <b>${pct1(base.precision)}% → ${pct1(r.precision)}%</b></span></div>
      <div class="lab-cnt"><span class="good">나아진 체류 <b>${r.cmp.better}</b></span><span>같은 체류 <b>${r.cmp.same}</b></span><span class="bad">나빠진 체류 <b>${r.cmp.worse}</b></span><small>체류 하나의 Brier 차이 ${F.same_th} 이내는 같음${r.moved != null ? ` · 장소 확률이 0.25 넘게 움직인 체류 ${r.moved} / ${G.n}` : ""}</small></div>`;
  }
  const order = F.cond.map(c => ({ c, x: G.res[c.id] })).filter(o => o.x).map(o => Object.assign(o, { d: o.x.brier - base.brier })).sort((a, b) => a.d - b.d);
  const mx = Math.max(0.005, ...order.map(o => Math.abs(o.d)));
  // 기본 모델 · 변화가 큰 3개 · 지금 고른 조건만 먼저, 나머지는 펼치기 (순서는 Brier 변화 순 그대로)
  const big3 = new Set(order.filter(o => o.c.id !== "A").sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 3).map(o => o.c.id));
  const shown = o => o.c.id === "A" || big3.has(o.c.id) || (C && C.id === o.c.id);
  const rk = o => {
    const w = Math.abs(o.d) / mx * 50, cls = labSig(F, G, o.c.id) === false ? "flat" : labVerdict(o.d).cls;
    return `<button class="lab-rk ${C && C.id === o.c.id ? "on" : ""} ${o.c.id === "A" ? "base" : ""}" data-c="${o.c.id}"><span class="rk-n" title="${esc(o.c.name)}">${esc(LAB_SHORT[o.c.id] || o.c.name)}</span><span class="rk-bar"><i class="${cls} ${o.d < 0 ? "neg" : ""}" style="width:${w.toFixed(1)}%;${o.d < 0 ? `right:50%` : `left:50%`}"></i></span><span class="rk-v ${cls}">${o.c.id === "A" ? o.x.brier.toFixed(3) : labD(o.d, 4)}</span></button>`;
  };
  const rest = order.filter(o => !shown(o));
  s3 += `<div class="lab-rank"><div class="lab-rk-h">기본 모델 대비 Brier 변화 · 누르면 그 조합을 고릅니다</div><div class="lab-rk-axis"><span></span><span class="ax"><em>← 개선</em><em>악화 →</em></span><span></span></div>${order.filter(shown).map(rk).join("")}` +
    (rest.length ? `<details class="lab-rk-more"${EV.labRankOpen ? " open" : ""}><summary>나머지 ${rest.length}개 조건 보기 (측정한 조건 전체 ${order.length}개)</summary>${rest.map(rk).join("")}</details>` : "") + `</div></section>`;

  const vv = r && C.id !== "A" ? labVerdict(r.brier - base.brier) : null;
  const sig = r && C.id !== "A" ? labSig(F, G, C.id) : null;
  const readTxt = !r ? `<p><b>측정하지 않은 조합입니다.</b> 정보를 하나씩 바꾼 조건만 실험했습니다. 숫자를 만들지 않습니다.</p>`
    : C.id === "A" ? `<p>기본 모델은 후기에서 간 곳의 <b>${pct1(base.recall)}%</b>를 맞히고, 확률 오차(Brier)는 <b>${base.brier.toFixed(4)}</b> 입니다. 왼쪽에서 정보를 빼거나 성향을 켜면 이 값과 비교합니다.</p><p class="hint">같은 59 체류 · 같은 후보에서 인기도만 쓴 기준선은 0.1085 로, 기본 모델이 더 좋지 않습니다(핵심 발견 ①).</p>`
    : `<p>${sig === false ? `${LAB_IF[C.id] || "이 조건에서는"} 확률 예측의 차이가 흔들림과 구분되지 않습니다.` : esc(labConcl(C.id, base, r))}</p><p>${esc(labRead(C.id, base, r))}</p>` +
      (C.id === "C1" ? `<p class="hint">예약은 후기에서 사후에 복원한 사실이고 계수는 같은 46편에 맞춘 값입니다. 운영에서도 유지되는지는 호텔 사전 예약 기록으로 확인해야 합니다.</p>` : "") +
      (/^B/.test(C.id) ? `<p class="hint">성향이 무의미하다는 결론이 아니라, 지금 입력 · 규칙에서 추가 설명력이 확인되지 않았다는 뜻입니다.</p>` : "");
  const tags = !r ? x19Tag("미검증") : C.id === "A" ? x19Tag("개발 자료 내 확인") : x19Tag(sig === false ? "미확정" : "개발 자료 내 확인") + `<span class="x19-ev warn">운영 자료로 재확인 전</span>`;
  box.innerHTML = x19Bench([["분석 대상", `${G.name} · ${G.n} 체류`], ["설명 요인", C ? C.name : "측정하지 않은 조합"], ["조건별 결과 비교", r ? (C.id === "A" ? `Brier ${base.brier.toFixed(4)}` : `Brier ${labD(r.brier - base.brier, 4)}`) : "숫자 없음"], ["결과 해석", vv ? (sig === false ? "흔들림과 구분 안 됨" : vv.t) : (C && C.id === "A" ? "기준" : "-")]],
    s1 + s2, s3, `<div class="x19-read"><b>지금 선택의 뜻</b>${readTxt}</div><div class="x19-tags">${tags}</div>`);
  box.querySelectorAll(".lab-opt[data-g]").forEach(b => b.onclick = () => { L.group = b.dataset.g; drawLab(); });
  box.querySelectorAll(".lab-fac input[data-f]").forEach(i => i.onchange = () => { L[i.dataset.f] = i.checked ? 1 : 0; drawLab(); });
  box.querySelectorAll(".lab-seg button").forEach(b => b.onclick = () => { L.trait = b.dataset.t; drawLab(); });
  { const dm = box.querySelector(".lab-rk-more"); if (dm) dm.ontoggle = () => { EV.labRankOpen = dm.open; }; }
  box.querySelectorAll(".lab-rk[data-c]").forEach(b => b.onclick = () => { const c = F.cond.find(x => x.id === b.dataset.c); Object.assign(L, { book: c.sel.book, incl: c.sel.incl, trait: c.sel.trait }); drawLab(); });
  drawLabFind(F); drawLabStay(F);
}

// 이번 분석에서 드러난 점 — 전체 59 체류 결과와 민감도 기록에서 문장을 만든다 (비교한 정보 안에서만 말한다)
function drawLabFind(F) {
  const el = document.getElementById("labFind"); if (!el) return;
  const A = F.groups[0].res, b = A.A.brier, S = (F.sensitivity || {}).rows || [];
  const card = (n, t, body, chips) => `<div class="lf"><h3><span class="lnum s">${n}</span>${t}</h3><p>${body}</p><div class="lf-chips">${chips}</div></div>`;
  const chip = (txt, cls) => `<span class="lf-chip ${cls || ""}">${txt}</span>`;
  const one = ["C1", "C2"].sort((x, y) => A[y].brier - A[x].brier)[0], oneName = one === "C1" ? "예약 정보" : "식사 포함 혜택 정보";
  const v1 = labVerdict(A[one].brier - b), v2 = labVerdict(A.B1.brier - b), W = F.groups.find(g => g.id === "wait");
  const BK = F.groups.find(g => g.id === "book"), wk = S[0];
  el.innerHTML = `<h2><span class="lab-ico s" aria-hidden="true">▤</span>이번 분석에서 드러난 점</h2><p class="lab-hint">${esc(F.sample)}</p><div class="lf-row">` +
    card(1, `${oneName} 제거의 하락 폭이 가장 큼`, `이번에 비교한 정보 중 ${oneName} 제거의 성능 하락 폭이 가장 컸습니다. 재현율 ${pct1(A.A.recall)}% → ${pct1(A[one].recall)}%, Brier ${b.toFixed(3)} → ${A[one].brier.toFixed(3)}.${one === "C1" && BK ? ` 예약한 곳이 있는 손님만 보면 Brier ${BK.res.A.brier.toFixed(3)} → ${BK.res.C1.brier.toFixed(3)}.` : ""} 방문 목적 등 다른 정보의 독립적인 설명력은 아직 비교하지 않았습니다.`,
      chip(`Brier ${labD(A[one].brier - b, 4)}`) + chip(v1.t, v1.cls)) +
    card(2, "성향은 선택 확률을 바꾸지만 Brier 는 악화", `성향 점수를 추가하면 일부 행동의 선택 확률은 달라지지만(${A.B1.moved}개 체류에서 장소 확률이 0.25 넘게 움직임), 전체 확률 예측의 Brier 점수는 ${b.toFixed(3)} → ${A.B1.brier.toFixed(3)} 로 악화됐습니다. 재현율은 ${pct1(A.A.recall)}% → ${pct1(A.B1.recall)}% 로 소폭 올랐습니다.${W ? ` 대기 회피 성향이 높은 손님은 Brier 변화가 ${labD(W.res.B1.brier - W.res.A.brier, 3)} 에 그쳤습니다.` : ""}`,
      chip(`Brier ${labD(A.B1.brier - b, 4)}`) + chip(v2.t, v2.cls)) +
    (wk ? card(3, "조식 혼잡은 기상 시각 가정에 민감", `${esc(wk.metric)}가 기본 ${wk.base_v} 에서 ${wk.alt.map((a, i) => `${esc(a)} ${wk.alt_v[i]}`).join(" · ")} 로 달라집니다. 신뢰구간이 아니라 검토한 가정 범위입니다(${esc(F.sensitivity.doc)}).`,
      chip(`${Math.min(...wk.alt_v)}~${Math.max(...wk.alt_v)}명`) + chip("가정 확인 필요", "warn")) : "") +
    `</div><p class="lab-cav">${esc(F.caveat)}</p>`;
}

// 개별 행동 역추적 — 한 체류에서 후기가 실제로 간 곳(관찰)과 모델이 갈 확률(시뮬레이션)을 나란히.
// 장소를 누르면 정보를 하나씩 바꾼 7개 조건에서 그 장소의 확률이 어떻게 달라졌는지 (측정값만 · 원인 단정 아님)
function drawLabStay(F) {
  const el = document.getElementById("labStay"); if (!el) return;
  const L = EV.lab, list = F.stays;
  if (!L.stay || !list.find(s => s.stay === L.stay)) L.stay = (list.find(s => s.booked.length && s.traits["대기 회피"] != null) || list[0]).stay;
  const S = list.find(s => s.stay === L.stay), P = S.prob || {};
  const nm = c => locName(c);
  const pr = (c, p) => (P[c] || {})[p];
  const places = [...new Set([...S.truth, ...Object.keys(P.A || {}), ...Object.keys(P.B1 || {})])]
    .filter(p => S.truth.includes(p) || F.cond.some(c => (pr(c.id, p) || 0) > 0.05))
    .sort((a, b) => (S.truth.includes(b) - S.truth.includes(a)) || (pr("A", b) || 0) - (pr("A", a) || 0));
  if (!L.place || !places.includes(L.place)) L.place = places[0];
  const pc = v => v == null ? "-" : `${Math.round(v * 100)}%`;
  const bar = v => `<span class="ls-bar"><i style="width:${Math.round((v || 0) * 100)}%"></i></span>`;
  const tr = Object.entries(S.traits).map(([k, v]) => `${esc(k)} ${v}`).join(" · ") || "없음";
  const hitA = places.filter(p => S.truth.includes(p)), pl = L.place, obs = S.truth.includes(pl);
  const isBook = S.booked.includes(pl), isIncl = S.incl.includes(pl);
  const det = pl ? `<div class="ls-det"><h3>${esc(nm(pl))} <span class="ls-obs ${obs ? "hit" : ""}">${obs ? "후기에서 방문함" : "후기에 방문 기록 없음"}</span></h3>
      <div class="ls-facts">${isBook ? `<span class="lf-chip">후기에 적힌 예약 장소</span>` : ""}${isIncl ? `<span class="lf-chip">패키지 포함 식사 장소</span>` : ""}${!isBook && !isIncl ? `<span class="hint">이 체류의 예약 · 포함 식사와 직접 연결된 장소는 아닙니다</span>` : ""}</div>
      <table class="t ls-ct"><tr><th>조건</th><th>이 장소에 갈 확률</th><th class="n">기본 대비</th></tr>${F.cond.map(c => { const v = pr(c.id, pl), d = v != null && pr("A", pl) != null ? v - pr("A", pl) : null;
        return `<tr class="${c.id === "A" ? "base" : ""}"><td>${esc(c.id === "A" ? "기본 모델" : c.name)}</td><td>${bar(v)} ${pc(v)}</td><td class="n ${d == null || Math.abs(d) < 0.09 ? "" : (d > 0) === obs ? "good" : "bad"}">${d == null ? "-" : c.id === "A" ? "" : `${d > 0 ? "+" : d < 0 ? "−" : "±"}${Math.round(Math.abs(d) * 100)}%p`}</td></tr>`; }).join("")}</table>
      <p class="lab-cav">조건마다 같은 손님을 12번 돌려 이 장소에 간 비율입니다. 정보를 하나씩 바꿨을 때 확률이 어떻게 움직였는지는 측정값이지만, 요인별 기여도를 나눠 계산한 것은 아니며 이 손님이 왜 갔는지를 단정하지 않습니다. 초록은 관찰 쪽으로, 빨강은 관찰과 반대쪽으로 9%p 넘게 움직인 것입니다.</p></div>` : "";
  el.innerHTML = `<h2><span class="lab-ico s" aria-hidden="true">◎</span>개별 행동 역추적 <span class="hint">· 후기 한 체류를 골라, 실제로 간 곳과 모델이 갈 확률을 나란히 보고 장소를 누르면 정보마다 확률이 어떻게 바뀌는지 봅니다</span></h2>
    <div class="ls-top"><label>체류 <select id="labStaySel">${list.map(s => `<option value="${s.stay}" ${s.stay === S.stay ? "selected" : ""}>${s.stay}${s.booked.length ? " · 예약 " + s.booked.length : ""}${s.incl.length ? " · 포함 식사 " + s.incl.length : ""}</option>`).join("")}</select></label>
      <span class="hint">예약 ${S.booked.length ? S.booked.map(nm).join(" · ") : "없음"} · 패키지 포함 식사 ${S.incl.length ? [...new Set(S.incl)].map(nm).join(" · ") : "없음"} · 후기 성향 ${tr} · 후기 방문 ${hitA.length}곳</span></div>
    <div class="ls-grid"><div><table class="t ls-t"><tr><th>장소</th><th>관찰 (후기)</th><th>기본 모델</th><th>성향 강도 1</th></tr>${places.map(p => `<tr class="click ${S.truth.includes(p) ? "hit" : ""} ${p === pl ? "on" : ""}" data-p="${p}"><td>${esc(nm(p))}</td><td>${S.truth.includes(p) ? "<b>방문함</b>" : "<span class='hint'>기록 없음</span>"}</td><td>${bar(pr("A", p))} ${pc(pr("A", p))}</td><td>${bar(pr("B1", p))} ${pc(pr("B1", p))}</td></tr>`).join("")}</table>
      <div class="ls-conds"><span class="hint">이 체류의 조건별 Brier (낮을수록 좋음):</span> ${F.cond.map(c => `<span class="ls-c">${esc(c.id === "A" ? "기본 모델" : c.name)} <b>${S.res[c.id].brier.toFixed(3)}</b></span>`).join("")}</div></div>${det}</div>`;
  el.querySelector("#labStaySel").onchange = e => { L.stay = e.target.value; L.place = null; drawLabStay(F); };
  el.querySelectorAll("tr[data-p]").forEach(t => t.onclick = () => { L.place = t.dataset.p; drawLabStay(F); });
}

// 10/16 대기 회피 역추정 (근거사슬 7-20) — static/wait_inv.json(wait_inv.py 실행 결과)만 읽는다. 숫자를 새로 만들지 않는다
let WAITINV = undefined;
async function loadWait() {
  if (WAITINV !== undefined) return WAITINV;
  try { const r = await fetch("/static/wait_inv.json"); WAITINV = r.ok ? await r.json() : null; } catch (e) { WAITINV = null; }
  return WAITINV;
}
const wiPct = v => v == null ? "-" : `${Math.round(v * 100)}%`;
function wiV(W) { const L = EV.lab; if (L.wv == null || !W.grid.includes(L.wv)) L.wv = 0; if (L.ww == null) L.ww = 1; return L.wv; }
function labWaitS2(W) {
  const v = wiV(W), L = EV.lab;
  const mk = (x, t) => `<button data-wv="${x}" class="${v === x ? "on" : ""}">${t}</button>`;
  return `<section class="lab-card lab-s2"><h2><span class="lnum">2</span>설명 요인 후보 선택</h2><p class="lab-hint">가설: 줄 앞에서는 대기 회피가 선택을 바꾼다. 후기 손님마다 관찰된 업장에만 줄을 세우고, 대기 회피 값을 바꿔 가며 관찰된 선택을 몇 번 하는지 봅니다.</p>
    <div class="lab-facs"><div class="lab-fac trait on"><span><b>대기 회피 값 (성향 강도 1)</b><small>0 = 줄을 신경 쓰지 않음 · 1 = 줄을 가장 싫어함 · 다른 성향은 비움</small></span>
      <div class="lab-seg wv">${W.grid.map(x => mk(x, x.toFixed(1))).join("")}</div>
      <div class="wi-marks"><span>이 사례들을 가장 잘 맞힌 값 <b>${W.v_all.toFixed(1)}</b> (줄 짧게 ${W.v_all_wait_lo.toFixed(1)} · 길게 ${W.v_all_wait_hi.toFixed(1)}) · 개인의 실제 성향이 아님</span></div></div>
      <div class="lab-fac trait"><span><b>줄 길이</b><small>후기에 숫자가 있으면 그 범위, 없으면 가정 범위</small></span>
        <div class="lab-seg">${["짧게", "기준", "길게"].map((t, i) => `<button data-ww="${i}" class="${L.ww === i ? "on" : ""}">${t}</button>`).join("")}</div></div>
      <div class="lab-fac fixed"><span><b>그 밖의 조건</b><small>v4 맞춘 계수 · 다른 손님 없음 · 같은 난수 줄 · 사례마다 ${W.k}번. 식당 앞 줄을 대기로 세는 것은 이 실험의 조건입니다(지금 규칙은 객실에서 출발하면 줄도 대기로 세지 않음)</small></span><span class="lab-tag">실험 조건</span></div>
    </div>
    <div class="lab-pick">대기 회피 값 = <b>${v.toFixed(1)}</b> <span class="hint">· 지금 기본 모델은 성향 강도 0이라 이 값은 포장 가점에만 씁니다</span></div></section>`;
}
function wiCurve(g, v, grid) {
  const W = 132, H = 40, mx = Math.max(0.2, ...g);
  const xs = i => 4 + i * (W - 8) / (grid.length - 1), ys = p => H - 4 - p / mx * (H - 10);
  const i = grid.indexOf(v);
  return `<svg class="wi-curve" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true"><line x1="4" y1="${H - 4}" x2="${W - 4}" y2="${H - 4}" class="ax"/><polyline points="${g.map((p, k) => `${xs(k).toFixed(1)},${ys(p).toFixed(1)}`).join(" ")}"/>${i >= 0 ? `<circle cx="${xs(i).toFixed(1)}" cy="${ys(g[i]).toFixed(1)}" r="3.5"/>` : ""}</svg>`;
}
function labWaitS3(W) {
  const v = wiV(W), L = EV.lab, iv = W.grid.indexOf(v);
  const M = W.cases.filter(c => c.kind === "model");
  const rows = M.map(c => {
    const w = String(c.wait[L.ww]), g = c.grid[w], p = g[iv], cur = c.current[w];
    if (!c.informative) return `<div class="wi-row dim"><div class="wi-h"><b>${esc(c.blog)}</b> · ${esc(c.seen)} → <em>${esc(c.obs)}</em></div><div class="hint">줄이 없어도 모델이 이 식사를 이 업장에서 하는 비율이 ${wiPct(c.no_line)}라 대기 회피 값을 가릴 수 없습니다.${c.note ? " " + esc(c.note) : ""}</div></div>`;
    return `<div class="wi-row"><div class="wi-h"><b>${esc(c.blog)}</b> · ${esc(c.seen)} → <em>${esc(c.obs)}</em> <span class="hint">· 줄 ${w}분 (${esc(c.wait_src)})</span></div>
      <div class="wi-b"><div class="wi-p"><small>관찰된 선택을 고른 비율</small><b>${wiPct(p)}</b><span class="hint">지금 기본 모델 ${wiPct(cur)} · 후기 추출 값 ${c.trait_review ?? "-"}</span></div>${wiCurve(g, v, W.grid)}
      <div class="wi-e ${c.effect_clear ? "clear" : ""}">값 0 → 1: ${c.effect > 0 ? "+" : c.effect < 0 ? "−" : "±"}${Math.round(Math.abs(c.effect) * 100)}%p <span class="hint">(±${Math.round(c.effect_se * 200)}%p 안이면 흔들림)</span></div></div></div>`;
  }).join("");
  const loo = W.loo.map(x => `<li><b>${esc(x.blog)}</b> · 다른 사례로 고른 값 ${x.v_others.toFixed(1)} → 관찰 선택 ${wiPct(x.p_others)} <span class="hint">(지금 기본 ${wiPct(x.p_current)})</span></li>`).join("");
  const good = W.verdict.includes("보임");
  return `<section class="lab-card lab-s3"><h2><span class="lnum">3</span>검증 결과 확인</h2><p class="lab-hint">${esc(W.sample)}</p>
    <div class="lab-delta ${good ? "good" : "flat"}">${esc(W.verdict)} · 다른 사례로 옮겨 맞힌 사례 ${W.loo_better} / ${W.loo.length}</div>
    <div class="wi-rows">${rows}</div>
    <div class="wi-loo"><div class="lab-sub-h">하나씩 빼기 · 다른 고객에게도 맞나</div><ul>${loo}</ul></div>
    <p class="lab-read">${good ? "다른 사례로 고른 값이 뺀 사례도 지금 기본 모델보다 잘 맞혔습니다(제한된 사례의 탐색 결과)." : "한 사례에서 맞는 값이 다른 사례에서는 지금 기본 모델보다 못하거나 같았습니다. 제한된 사례에서는 '줄 앞에서 대기 회피가 선택을 바꾼다' 는 조건부 가설의 추가 설명력이 확인되지 않았습니다."}</p>
    <p class="lab-cav">${esc(W.caveat)}</p></section>`;
}
const WI_KIND_ORDER = ["model", "rule", "inside", "plan"];
function drawLabWaitCases(W) {
  const el = document.getElementById("labStay"); if (!el) return;
  const cnt = k => W.cases.filter(c => c.kind === k).length;
  const name = { model: "모델의 선택으로 표현됨", rule: "규칙으로 정해짐 (포함 식사)", inside: "업장 안의 줄 (모델에 없음)", plan: "미리 피함 (시각 · 예약)" };
  const v41 = W.cases.filter(c => c.kind === "model" && c.informative).map(c => `${esc(c.blog)} ${Object.values(c.v41_effect)[1] > 0 ? "+" : ""}${Math.round(Object.values(c.v41_effect)[1] * 100)}%p`).join(" · ");
  el.innerHTML = `<h2><span class="lab-ico s" aria-hidden="true">◎</span>관찰된 대기 행동 ${W.cases.length}건 · 지금 모델이 표현할 수 있나 <span class="hint">· 후기 요약이며 원문이 아닙니다</span></h2>
    <div class="wi-kinds">${WI_KIND_ORDER.map(k => `<span class="lf-chip ${k === "model" ? "good" : ""}">${name[k]} ${cnt(k)}</span>`).join("")}</div>
    <table class="t ls-t wi-t"><tr><th>체류</th><th>후기에서 본 상황</th><th>그다음 행동</th><th>모델에서</th></tr>${WI_KIND_ORDER.flatMap(k => W.cases.filter(c => c.kind === k)).map(c => `<tr class="${c.kind === "model" ? "hit" : ""}"><td><b>${esc(c.blog)}</b></td><td>${esc(c.seen)}</td><td>${esc(c.did)}</td><td><b>${esc(c.kind_name)}</b>${c.why ? `<br><span class="hint">${esc(c.why)}</span>` : c.informative === false ? `<br><span class="hint">줄이 없어도 이 식사를 이 업장에서 거의 하지 않음 (${wiPct(c.no_line)})${c.note ? " · " + esc(c.note) : ""}</span>` : ""}</td></tr>`).join("")}</table>
    <p class="lab-read">지금 v4.1 규칙으로 같은 줄을 세우면 줄 길이는 선택을 바꾸지 않습니다. 객실에서 출발하면 기다림을 객실 시간으로 보고(대기 벌점 없음), 줄이 30분을 넘으면 다음 회차 예약으로 바뀌기 때문입니다. 대기 회피 값이 움직이는 것은 포장 가점뿐입니다(값 0 → 1: ${v41}).</p>
    <p class="lab-cav">대기를 겪은 후기 대부분은 줄을 서서 같은 업장을 이용했거나 미리 시각 · 예약으로 피했습니다. 이런 행동은 '줄 대신 다른 곳' 을 고르는 선택이 아니라서, 대기 회피 성향보다 '업장을 지키고 시각 · 형태를 바꾸는 행동' 으로 읽는 편이 후기와 맞습니다(근거사슬 7-10).</p>`;
}

// ---------------------------------------------------------------------------
// 10/18 UX 18차(연구 연결) · 판단 근거 첫 화면 — 한 줄 결론 + 네 질문 카드 + 두 가지 설명 한계 (판단근거_핵심발견_증거연결_1018.md v5)
//   숫자 · 문장은 static/research_index.json(표시 · 연결 전용 색인)에서만 읽는다. 화면은 아무것도 다시 계산하지 않는다.
//   claim 은 value · denominator · gold · condition · evidence · source 여섯 칸이 비면 숫자를 그리지 않고 '모름 / 미측정' 으로 둔다.
// ---------------------------------------------------------------------------
let RIDX = undefined;
async function loadRidx() { if (RIDX !== undefined) return RIDX; try { RIDX = await (await fetch("/static/research_index.json")).json(); } catch (e) { RIDX = null; } return RIDX; }
const EV_ACTION = { cur: null };     // 손님 한 팀에서 넘어온 행동 (stay · run · step · key)
const rxLab = k => `<span class="rx-lab" title="${esc((RIDX && RIDX.labels && RIDX.labels[k]) || "")}">${esc(k)}</span>`;
function rxClaimOk(c) { return !!(c && c.value != null && c.denominator && c.gold && c.condition && c.evidence && c.source && c.source.file); }
function rxClaimRow(id) {
  const c = RIDX.claims[id]; if (!c) return "";
  if (!rxClaimOk(c)) return `<li class="rx-claim"><b>${esc(id)}</b> <span class="hint">모름 / 미측정 (색인에 출처 · 분모 · 조건이 없음)</span></li>`;
  return `<li class="rx-claim"><b>${esc(c.text)}</b> ${rxLab(c.evidence)}<div class="hint">분모 ${esc(c.denominator)} · 정답 ${esc(c.gold)} · 조건 ${esc(c.condition)}</div><div class="hint">출처 ${esc(c.source.file)} › ${esc(c.source.path || "")} · ${esc(c.source.report || "")}${c.not_claim ? ` · <i>주장하지 않음: ${esc(c.not_claim)}</i>` : ""}</div></li>`;
}
function rxWhyFor(stay, key) {
  const cs = (RIDX.cases || []).find(x => x.id === stay && x.link && x.link.key === key) || (RIDX.cases || []).find(x => x.id === stay);
  const n = cs && cs.why_unknown; const W = n && RIDX.why_unknown[n];
  return { cs, n, W };
}
// ── 19차b 핵심 발견 · 증거 종류 색 (관측 · 모델 · 미검증 · 코딩) — 색은 증거 종류에만, 늘 글자와 함께 ──
const x19Kind = lab => (RIDX && RIDX.label_kind && RIDX.label_kind[lab]) || "code";
const x19Tag = lab => `<span class="x19-ev ${x19Kind(lab)}" title="${esc((RIDX && RIDX.labels && RIDX.labels[lab]) || "")}">${esc(lab)}</span>`;
const x19Claim = id => (RIDX && RIDX.claims && RIDX.claims[id]) || null;
function x19Num(id) {
  const c = x19Claim(id); if (!rxClaimOk(c)) return null;
  const v = c.value;
  if (id === "recall_dev") return `${(+v).toFixed(1)}<small>%</small>`;
  if (id === "booked_removed" || id === "included_removed") return `+${(+v).toFixed(4)}`;
  if (id === "moegi_paths") return v.map(x => Math.round(x * 100)).join(" · ") + "<small>%</small>";
  if (typeof v === "number" && v < 1 && v > 0) return (+v).toFixed(4);
  return esc(String(v));
}
const X19_NUMCLS = { brier_dev: "model", baseline_pop: "ref", baseline_mix: "ref" };
function x19Card(card, i) {
  const kind = x19Kind((card.labels || [])[0]);
  let mid = "";
  if (card.mini) {
    const vals = card.mini.claims.map(id => { const c = x19Claim(id); return rxClaimOk(c) ? +c.value : null; });
    if (vals.every(v => v != null)) {
      const mx = Math.max(...vals);
      mid = `<div class="x19-mini"><div class="mh">확률 오차(Brier) · 짧을수록 좋음</div>` + vals.map((v, j) => `<div class="r"><span>${esc(card.mini.names[j])}</span><span class="bar ${j ? "ref" : ""}"><i style="width:${(v / mx * 100).toFixed(0)}%"></i></span><span class="v">${v.toFixed(4)}</span></div>`).join("") +
        `<div class="cap">${esc(card.mini.cap)}</div></div>`;
    }
  } else if (card.stat) {
    mid = `<div class="x19-stat">${card.stat.map(s => `<span><b>${esc(s.v)}</b>${esc(s.l)}</span>`).join("")}</div>`;
  }
  return `<article class="x19-qcard k-${kind}" id="rx-${card.id}" data-card="${card.id}" tabindex="0" role="button" aria-expanded="false" aria-controls="x19Drawer">` +
    `<div class="q"><i>${i + 1}</i>${esc(card.q19 || card.q)}</div><div class="big ${card.kpi ? "x19-kpi" : ""}">${esc(card.head || card.big)}</div><div class="one">${esc(card.one || card.line1 || "")}</div>${mid}` +
    `<div class="foot">${(card.labels || []).map(x19Tag).join("")}<span class="more">자세히 <span aria-hidden="true">↓</span></span></div></article>`;
}
const X19_DTABS = [["concl", "결론"], ["cond", "측정 조건"], ["cases", "대표 사례"], ["next", "다음 검증"]];
function x19Drawer(id, tab) {
  const card = (RIDX.cards || []).find(c => c.id === id); if (!card) return "";
  const d = card.detail || {}, n = (RIDX.cards || []).indexOf(card) + 1;
  tab = tab || "concl";
  let body = "";
  if (tab === "concl") {
    const nums = (card.claims || []).map(cid => { const v = x19Num(cid), c = x19Claim(cid); return v ? `<div class="num ${X19_NUMCLS[cid] || ""}"><div class="l">${esc(c.short || cid)}</div><div class="n">${v}</div></div>` : ""; }).join("");
    body = `<div class="dgrid"><div>${d.lead ? `<p class="lead">${esc(d.lead)}</p>` : ""}${nums ? `<div class="numrow">${nums}</div>` : ""}</div>` +
      `<div class="side"><h4>연구 결과 요약</h4><p>${esc(d.result || "")}</p></div></div>`;
  } else if (tab === "cond") {
    const rows = (card.claims || []).map(cid => { const c = x19Claim(cid); if (!rxClaimOk(c)) return `<tr><td><b>${esc(cid)}</b></td><td colspan="3" class="hint">모름 / 미측정 (색인에 출처 · 분모 · 조건이 없음)</td></tr>`;
      return `<tr><td><b>${esc(c.short || cid)}</b><div>${x19Tag(c.evidence)}</div></td><td>${esc(c.denominator)}<div class="hint">정답 ${esc(c.gold)}</div></td><td>${esc(c.condition)}</td><td class="hint">${esc(c.source.file)}${c.source.path ? " › " + esc(c.source.path) : ""}<br>${esc(c.source.report || "")}${c.not_claim ? `<br><i>주장하지 않음: ${esc(c.not_claim)}</i>` : ""}</td></tr>`; }).join("");
    body = rows ? `<table class="t x19-ct"><tr><th>항목 · 증거</th><th>분모 · 정답</th><th>조건</th><th>출처</th></tr>${rows}</table>` : `<p class="hint">이 질문은 수치 claim 없이 연구 통합 문서의 원인 구분을 요약합니다. 출처: P1_연구통합_1018.md 5절</p>`;
  } else if (tab === "cases") {
    body = `<ul class="x19-cases">${(d.cases || []).map(c => { const cs = (RIDX.cases || []).find(x => x.id === c.ref);
      const go = cs && cs.link ? `<button type="button" class="x19-go rx-go" data-stay="${esc(cs.link.stay)}" data-run="${cs.link.run}" data-key="${esc(cs.link.key)}" title="손님 한 팀 · 실행 run ${cs.link.run} 에서 이 행동으로">${esc(cs.link.stay)} 동선 보기 ›</button>` : `<span class="x19-nogo">연결 없음</span>`;
      return `<li>${go}<span>${esc(c.text)}${cs ? ` <span class="hint">· ${esc(cs.kind)}</span>` : ""}</span></li>`; }).join("")}</ul>`;
  } else {
    body = `<div class="dgrid"><div><h4>부족한 근거</h4><p>${esc(d.gap || "")}</p></div><div><h4>다음 검증</h4><p>${esc(d.next || "")}</p></div></div>`;
  }
  return `<div class="dh">${(card.labels || []).slice(0, 1).map(x19Tag).join("")}<h3><span class="dn">${n}</span>${esc(card.q19 || card.q)} <span class="ds">— ${esc(card.head || card.big)}</span></h3><button type="button" class="x19-btn sm x19-dx">닫기 ✕</button></div>` +
    `<div class="dtabs" role="tablist">${X19_DTABS.map(([k, t]) => `<button type="button" role="tab" data-t="${k}" aria-selected="${k === tab}" class="${k === tab ? "on" : ""}">${t}</button>`).join("")}</div><div class="dbody">${body}</div>`;
}
function x19Pair() {
  const P = RIDX.limits_pair; if (!P) return "";
  const cs = id => (RIDX.cases || []).find(x => x.id === id) || {};
  const L = cs(P.left.case), R = cs(P.right.case);
  const bars = (L.values || []).map(([k, v]) => `<div class="r"><span>${esc(k)}</span><span class="bar"><i style="width:${Math.max(1, Math.round(v * 100))}%"></i></span><span class="v">${Math.round(v * 100)}%</span></div>`).join("");
  const flow = (R.flow || []).map(([h, t, k], j) => `${j ? `<span class="ar" aria-hidden="true">→</span>` : ""}<div class="st ${k}"><b>${esc(h)}</b>${esc(t)}</div>`).join("");
  return `<section class="x19-blk"><div class="x19-sechead"><h2>연구에서 드러난 두 가지 한계</h2><span class="d">같은 결과가 다른 이유로 나올 수 있고, 이유가 있어도 모델이 못 볼 수 있습니다</span></div><div class="x19-pair">` +
    `<div class="x19-find"><div class="k">${x19Tag("모델 내부 실험")}<span class="hint">P1-D</span></div><h3>${esc(P.left.head)}</h3><div class="s">모에기를 고른 비율 — 각기 다른 세 조건에서 20회씩 실행</div><div class="x19-bars">${bars}</div>` +
    `<div class="cap">${esc(L.denominator || "")} · 조건별 선택 비율이며 이유의 비중이 아님</div><div class="take">${esc(P.left.foot)}</div></div>` +
    `<div class="x19-find"><div class="k">${x19Tag("후기 사례 코딩")}<span class="hint">P1-A</span></div><h3>${esc(P.right.head)}</h3><div class="s">${esc(R.title || "")}</div>${flow ? `<div class="x19-flow">${flow}</div>` : `<p>${esc(R.note || "")}</p>`}` +
    `<div class="take">${esc(P.right.foot)} — 자료 요청이 아니라 모델 개선 항목${R.link ? `<button type="button" class="x19-go rx-go" data-stay="${esc(R.link.stay)}" data-run="${R.link.run}" data-key="${esc(R.link.key)}">${esc(R.link.stay)} 동선 보기 ›</button>` : ""}</div></div>` +
    `<div class="note">${esc(P.caption)}</div></div></section>`;
}
function rxFind() {
  if (!RIDX) return `<div class="hint">연구 색인(research_index.json)을 읽지 못해 핵심 발견을 그리지 않습니다.</div>`;
  const H = RIDX.headline || {}, K = RIDX.label_kind || {};
  const why = Object.entries(RIDX.why_unknown || {}).map(([n, w]) => `<div class="w"><i>${esc(n)}</i><div><b>${esc(w.text)}</b><span>${esc(w.when)} → ${esc(w.action)}</span></div></div>`).join("");
  return `<section class="x19-hero"><div><h1>${esc(H.title19 || H.title || "")}</h1><p class="msg">${esc(H.line19_a || "")}<b>${esc(H.line19_b || "")}</b>${esc(H.line19_c || "")}</p><div class="scope">${esc(H.scope19 || H.sub || "")}</div></div>` +
    `<div class="x19-key"><b>색은 증거의 종류만 뜻합니다</b><div class="row"><span class="sw obs"></span>후기에서 관측 · 개발 자료 안에서 확인</div><div class="row"><span class="sw model"></span>모델 안에서만 본 결과 (실제 고객 아님)</div><div class="row"><span class="sw warn"></span>미검증 · 미확정 · 운영 자료 없음</div><div class="row"><span class="sw code"></span>연구자 코딩 · 질적 사례</div></div></section>` +
    `<div class="x19-cards">${(RIDX.cards || []).map(x19Card).join("")}</div>` +
    `<div class="x19-drawer" id="x19Drawer" hidden></div>` +
    `<div class="x19-why" aria-label="왜 알 수 없는가">${why}</div>` +
    x19Pair() +
    `<div class="x19-foot">${esc(H.foot || "")} · 색인 ${esc(RIDX.version || "")} · 모델 ${esc(RIDX.model_ver || "")}</div>`;
}
function x19BindFind(root) {
  const dr = root.querySelector("#x19Drawer"); if (!dr) return;
  const open = (id, tab) => {
    root.querySelectorAll(".x19-qcard").forEach(c => { const on = c.dataset.card === id; c.classList.toggle("open", on); c.setAttribute("aria-expanded", on); });
    if (!id) { dr.hidden = true; dr.innerHTML = ""; EV.card = null; return; }
    EV.card = id; dr.innerHTML = x19Drawer(id, tab); dr.hidden = false;
    dr.querySelector(".x19-dx").onclick = () => open(null);
    dr.querySelectorAll(".dtabs [data-t]").forEach(b => b.onclick = () => open(id, b.dataset.t));
    dr.querySelectorAll(".rx-go").forEach(b => b.onclick = () => goGuestAction(b.dataset.stay, +b.dataset.run, b.dataset.key));
  };
  root.querySelectorAll(".x19-qcard").forEach(c => {
    const go = () => open(c.classList.contains("open") ? null : c.dataset.card);
    c.onclick = go; c.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } };
  });
}

// 손님 한 팀 → 판단 근거: '이 행동의 판단 근거' 패널 (체류 ID + 실행 ID + 행동 순번 + 행동 키 기준 · 시각은 보조 표시)
//   19차b — 머리 판정 3칸 + 세 단계 + 펼침(다섯 상자). 확률은 원래 선택 집합 전체의 가중치가 색인(action_probs)에 있을 때만 그린다.
//   '모델 대기값' = 도착(이동 계산)부터 그 행동을 시작할 수 있을 때(개점 · 회차 · 착석)까지의 분. 업장 앞 실제 줄이 아니다(후기 재현 실행은 좌석 경쟁 없음)
function rxActionPanel() {
  const A = EV_ACTION.cur; if (!A || !RIDX) return "";
  const s = A.step || {}; const { cs, W } = rxWhyFor(A.stay, A.key);
  const alts = (s.alts || []).slice(0, 6);
  const why = (s.why || []);
  const chosenName = s.label || A.key;
  const place = s.venue || s.location;
  const obs = A.review ? (A.review.visited || []).find(v => v.loc === place) : null;
  const topAlt = alts.length ? alts.reduce((m, a) => (+a.pts > +m.pts ? a : m), alts[0]) : null;
  const notTop = topAlt && topAlt.key !== A.key;
  const PR = A.review && A.review.blog === A.stay ? (RIDX.action_probs || []).find(x => x.stay === A.stay && x.run === A.run && x.step === A.stepIdx && x.key === A.key) : null;   // 후기 대조 실행(후기 날짜 · 좌석 경쟁 없음)일 때만 — ② 날짜로 돌린 실행에는 붙이지 않음
  const waitNote = "모델 대기값 = 도착(이동 계산)부터 이 행동을 시작할 수 있을 때(개점 · 회차 · 착석)까지의 분. 업장 앞 실제 줄이 아닙니다 (이 실행은 좌석 경쟁 없음)";
  const caseHit = cs && cs.link && cs.link.key === A.key;
  // 머리 판정 3칸
  const v1 = !A.review ? [A.stay !== "custom" ? "대조 실행 아님" : "후기 손님 아님", "code"] : obs ? [caseHit ? "같은 행동 기록 있음" : "같은 장소 기록 있음", "obs"] : ["언급 없음 · 미관측", "warn"];
  const v2 = !A.review ? ["대조 없음", "code"] : W ? ["미확인 · 이유 후보 여러 개", "warn"] : cs ? ["코딩 결과 참고", "code"] : ["코딩 대상 아님", "code"];
  const v3 = (cs && cs.sens) ? ["연결됨", "model"] : ["연결된 것 없음", "code"];
  const vb = (l, [t, k]) => `<div class="x19-vb"><div class="l">${l}</div><div class="v ${k}">${esc(t)}</div></div>`;
  const sub = !A.review ? (A.stay !== "custom" ? `② 에서 고른 날짜 · 상황으로 돌린 실행입니다 · 후기 대조는 '후기 방문 기록과 모델 대조' 실행에서만 합니다` : "직접 만든 손님 · 후기 대조 없음") : obs ? `후기에도 ${esc(obs.name || place)} 기록이 있습니다 · 결과가 같다는 것이지 이유가 같다는 뜻은 아닙니다` : "후기에 이 장소의 언급이 없습니다 — 미관측이며 '안 갔다'로 확정하지 않습니다";
  // 1단계 — 선택지 · 점수 · 확률
  let altHtml;
  if (PR) {
    const cands = PR.cands.slice().sort((a, b) => b.p - a.p), shown = cands.slice(0, 6), rest = cands.slice(6);
    const topP = Math.max(...PR.cands.map(c => c.pts)), mxp = Math.max(...cands.map(c => c.p));
    altHtml = `<ul class="x19-alts">${shown.map(c => `<li class="${c.key === A.key ? "sel" : ""} ${c.pts === topP ? "top" : ""}"><span class="nm">${esc(c.label)}${c.pts === topP ? ` <em class="tg">최고 점수</em>` : ""}${c.key === A.key ? ` <em class="tg sel">이 실행의 선택</em>` : ""}</span><span class="pt">${c.pts.toFixed(2)}</span><span class="pp">${(c.p * 100).toFixed(1)}%</span><span class="pb"><i style="width:${(c.p / mxp * 100).toFixed(1)}%"></i></span></li>`).join("")}</ul>` +
      (rest.length ? `<div class="x19-rest">나머지 ${rest.length}개 후보 합 ${(rest.reduce((a, c) => a + c.p, 0) * 100).toFixed(1)}%</div>` : "") +
      `<div class="x19-den">확률 분모 = ${esc(PR.denominator)} · 점수 · 확률은 이 실행에서 모델이 계산한 값</div>`;
  } else {
    altHtml = alts.length ? `<ul class="x19-alts noprob">${alts.map(a => `<li class="${a.key === A.key ? "sel" : ""} ${topAlt && a.key === topAlt.key ? "top" : ""}"><span class="nm">${esc(a.label)}${topAlt && a.key === topAlt.key ? ` <em class="tg">최고 점수</em>` : ""}${a.key === A.key ? ` <em class="tg sel">이 실행의 선택</em>` : ""}</span><span class="pt">${(+a.pts).toFixed(2)}</span><span class="hint">이동 ${a.travel}분 · 모델 대기값 ${a.wait}분</span></li>`).join("")}</ul>` +
      `<div class="x19-den">점수 상위 ${alts.length}개만 저장돼 있어${s.feasible ? `(원래 선택 집합 ${s.feasible}개)` : ""} 선택 확률은 표시하지 않습니다</div>` : `<div class="hint">기록 없음</div>`;
  }
  const step1 = `<div class="st"><div class="sh"><i>1</i><b>어떤 선택지와 점수였나</b>${x19Tag("모델 생성")}</div>${altHtml}` +
    `<div class="x19-note"><b>가장 높은 점수의 행동이 반드시 선택되는 것은 아닙니다.</b> ${notTop ? `이번 실행에서 뽑힌 것은 최고 점수(${esc(topAlt.label)} ${(+topAlt.pts).toFixed(2)})가 아니라 '${esc(chosenName)}'입니다. ` : ""}모델은 점수를 확률(τ ${s.tau ?? 0.5})로 바꿔 뽑습니다.</div>` +
    (why.length ? `<div class="x19-terms">${why.map(w => `<span>${esc(w)}</span>`).join("")}<span class="wt" title="${esc(waitNote)}">모델 대기값 ${s.wait ?? "-"}분 ⓘ</span></div><div class="x19-cap">점수 항목은 모델이 쓴 계산 항이며 실제 손님의 이유가 아닙니다 · 모델 대기값은 행동을 시작할 수 있는 시각까지의 시간(업장 앞 줄 아님)</div>` : "") + `</div>`;
  const step2 = `<div class="st"><div class="sh"><i>2</i><b>후기에서 확인되는가</b>${x19Tag("실측 · 후기 보고")}</div>` +
    (obs ? `<div class="x19-obs"><b>후기에 적힌 행동</b>${esc(String(obs.why).replace(/^[◎○△]\s*/, ""))}${obs.p != null ? `<span class="x19-p">같은 조건 화면 난수 12회 중 ${Math.round(obs.p * 12)}회 이 장소에 감 (모델 생성)</span>` : ""}</div>` : `<div class="x19-obs none"><b>후기</b>${A.review ? "이 장소의 언급 없음 (미관측)" : "후기 손님이 아님 · 실측 없음"}</div>`) +
    (W ? `<div class="x19-whyrow"><i>${esc(String(RIDX && Object.keys(RIDX.why_unknown || {}).find(k => RIDX.why_unknown[k] === W) || ""))}</i><div><b class="rx-why-t">${esc(W.text)}</b><span>${esc(cs && cs.reason_note ? cs.reason_note : W.when)}</span></div></div>` : `<div class="x19-whyrow none"><div><b>선택 이유 코딩 없음</b><span>이 행동은 사례 코딩 대상이 아닙니다</span></div></div>`) +
    `<div class="x19-note">후기에 같은 행동이 있다는 것은 <b>결과의 일치</b>입니다. 모델이 그 손님과 같은 이유로 골랐다는 증거가 아닙니다. 후기 보고 ≠ 운영 측정 — 호텔 대기 등록 · 결제 기록으로 확인된 것이 아닙니다.</div></div>`;
  const step3 = `<div class="st"><div class="sh"><i>3</i><b>조건을 바꾸면</b>${x19Tag(cs && cs.sens ? "모델 내부 민감도" : "미검증")}</div>` +
    ((cs && cs.sens) ? `<p>${esc(cs.sens)}</p>` : `<div class="x19-empty"><b>이 행동에 연결된 조건 실험이 아직 없습니다</b>이 실행(run 0)과 같은 조건으로 다시 돌린 결과만 여기에 연결합니다.</div>`) +
    `<button type="button" class="x19-btn wide" id="rxToBench">행동 역추적에서 ${esc(A.stay)} 체류 보기 ›</button>` +
    `<div class="x19-cap">행동 역추적의 체류별 표는 저장된 실험(Eval-K12 · 다른 난수 줄 · 12회)의 장소 단위 확률입니다. P1-C 같은 격리 실험의 조건부 결과는 조건이 달라 이 행동과 섞지 않습니다.</div></div>`;
  const obsTxt = !A.review ? "후기 손님이 아님 · 실측 없음" : obs ? `실측(후기 보고) — ${esc(obs.why)}${obs.p != null ? ` · 화면 난수 12회 중 ${Math.round(obs.p * 100)}% 에서 이 장소에 감` : ""}` : "후기에 이 장소의 언급 없음 (미관측)";
  const detail = `<details class="rx-act-det"><summary>전문 분석 — 다섯 단계 펼치기 (당시 선택지 전체 · 점수 항 · 후기 확인 · 왜 알 수 없는가 · 다시 실행 시 변화)</summary><div class="rx-act-grid">` +
    `<div class="rx-box"><h5>1 당시 선택지 <span class="hint">모델 생성 · 점수 상위 6</span></h5>${alts.length ? `<ol>${alts.map(a => `<li class="${a.key === A.key ? "me" : ""}">${esc(a.label)} <span class="hint">${(+a.pts).toFixed(2)} · 이동 ${a.travel}분 · 모델 대기값 ${a.wait}분</span></li>`).join("")}</ol>` : `<div class="hint">기록 없음</div>`}</div>` +
    `<div class="rx-box"><h5>2 선택에 쓰인 점수 항 <span class="hint">모델 생성</span></h5>${why.length ? `<ul>${why.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : `<div class="hint">기록 없음</div>`}</div>` +
    `<div class="rx-box"><h5>3 후기의 확인 / 미관측 <span class="hint">실측(후기 보고)</span></h5><p>${obsTxt}</p></div>` +
    `<div class="rx-box rx-why"><h5>4 왜 알 수 없는가 <span class="hint">${cs ? esc(cs.kind) : "분류 없음"}</span></h5>${W ? `<p>${esc(W.text)}</p><div class="hint">${esc(W.when)} → ${esc(W.action)}</div>` : `<p class="hint">분류 없음</p>`}${cs && cs.note ? `<div class="hint">${esc(cs.note)}</div>` : ""}</div>` +
    `<div class="rx-box"><h5>5 다시 실행 시 변화 <span class="hint">모델 내부 조건 비교</span></h5><p class="hint">${(cs && cs.sens) ? esc(cs.sens) : "연결된 조건 실험 없음"}</p></div>` +
    `</div></details>`;
  return `<section class="x19-act" id="rxAct">` +
    `<div class="x19-ret"><span>손님 한 팀에서 왔습니다</span><span class="ids"><code>${esc(A.stay)}</code><code>run ${A.run}</code><code>행동 ${A.stepIdx}</code><code>${esc(A.key)}</code></span><button type="button" class="x19-btn" id="rxBack">← 동선으로 돌아가기</button></div>` +
    `<div class="x19-panel"><div class="ph"><div><h2>${esc(A.t || "")} · ${esc(chosenName)} <span class="q">— 모델은 왜 이 행동을 골랐나</span></h2><div class="m">${sub}</div></div>` +
    `<div class="x19-verdict">${vb("후기 관측", v1)}${vb("이유 확인", v2)}${vb("조건 실험", v3)}</div></div>` +
    `<div class="x19-steps">${step1}${step2}${step3}</div>` +
    `<div class="pf">${detail}<div class="pfm"><span>식별자 ${esc(A.stay)} · run ${A.run} · 행동 ${A.stepIdx} · ${esc(A.key)}</span><span>${esc(RIDX.run_note || "")}</span></div></div></div></section>`;
}
function rxBlock() { return rxFind(); }   // 이전 이름 호환
function rxBind(root) {
  root.querySelectorAll(".x19-view .rx-go").forEach(b => b.onclick = () => goGuestAction(b.dataset.stay, +b.dataset.run, b.dataset.key));
  const bk = root.querySelector("#rxBack"); if (bk) bk.onclick = () => { const A = EV_ACTION.cur; if (typeof backToGuestStep === "function") backToGuestStep(A); };
  const tb = root.querySelector("#rxToBench"); if (tb) tb.onclick = () => { const A = EV_ACTION.cur; if (A && FACTOR && FACTOR.stays && FACTOR.stays.some(x => x.stay === A.stay)) { EV.lab.stay = A.stay; EV.lab.place = A.step && (A.step.venue || A.step.location) || null; if (typeof drawLabStay === "function") drawLabStay(FACTOR); } x19SetView("bench"); const st = document.getElementById("labStay"); if (st) setTimeout(() => st.scrollIntoView({ behavior: "smooth", block: "start" }), 40); };
}

// 판단 근거 → 손님 한 팀: 후기 손님(stay)을 화면 기본 실행(run 0)으로 돌려 그 행동 키가 처음 나오는 순번으로. 없으면 "이 실행에서는 선택되지 않음"
async function goGuestAction(stay, run, key) {
  if (typeof openReviewStay !== "function") return;
  location.hash = `oneteam?stay=${encodeURIComponent(stay)}&run=${run}&key=${encodeURIComponent(key)}`;
  await openReviewStay(stay, run, key);
}
