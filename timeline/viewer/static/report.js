// 운영 요약 (10/14 · 처음 이름 '요약 리포트') — 경영 · 운영 쪽이 처음 보는 화면.
// 원칙: 모든 문장은 이 날의 계산 결과(day JSON) · 시드 묶음(band) · 장부(가설표 · 입력 출처표)에서만 만든다. 지어낸 숫자 없음.
// 문단마다 '근거 · 수치 보기' 를 펼치면 그 문장을 만든 숫자 · 출처 · 등급이 나오고, 링크를 누르면 '고객 흐름' 의 지도 · 손님 화면으로 내려간다.

const RPT = { key: null, view: "day", guest: null, busy: false };
const GRADE_TXT = { "◎": "공식 · 확인", "○": "간접 근거 (표마다 뜻이 다름 · 범례 참고)", "△": "가정 · 근거 약함" };
// 10/17 QA Q2 — ◎ · △ 는 표와 상관없이 같은 뜻이지만 ○ 는 출처표마다 정의가 다르다(데이터 쪽 정의 차이 · 통일은 팀 결정).
// 그래서 범례는 늘 어느 표의 등급인지와 함께 쓴다.
const GRADE_LEGEND = {
  prov: "입력 출처표 등급: ◎ 공식 자료 · ○ 참조 모델(온톨로지) 값 또는 후기로 맞춘 값 · △ 가정 · 임시값",
  place: "가정표(운영 조건) 등급: ◎ 공식 자료 · ○ 공식 자료에서 계산 · 간접 확인 · △ 가정 · 후기 근거",
  menu: "상품표 등급: ◎ 공식 가격 · ○ 공식 자료에서 계산 · 간접 확인 · △ 추정",
};

// 받침에 따라 조사 고르기 (은/는 · 이/가 · 과/와 · 으로/로 · 을/를)
function josa(w, pair) {
  const [a, b] = pair.split("/"); const c = String(w).replace(/\s*\([^)]*\)\s*$/, "").trim().slice(-1); const code = c.charCodeAt(0);   // 끝 괄호는 건너뛰고 받침을 본다
  if (code < 0xac00 || code > 0xd7a3) return w + (/[0-9LMNRlmnr]$/.test(c) ? a : b);
  const jong = (code - 0xac00) % 28;
  if (a === "으로") return w + (jong === 0 || jong === 8 ? "로" : "으로");
  return w + (jong ? a : b);
}
function pctS(a, b) { return b ? Math.round(a / b * 100) : 0; }
function topN(obj, n) { return Object.entries(obj || {}).sort((a, b) => b[1] - a[1]).slice(0, n); }
function gradeOf(s) { const m = String(s || "").match(/[◎○△]/); return m ? m[0] : ""; }
function gradeChip(s) { const g = gradeOf(s); return g ? `<span class="gchip g${"◎○△".indexOf(g)}" title="${esc(GRADE_TXT[g] || "")}">${g}</span>` : ""; }
function prov(name) { return (LIB.provenance || []).find(r => (r["입력"] || "").startsWith(name)); }
function provRow(r) {
  if (!r) return "";
  return `<tr><td>${esc(r["입력"])}</td><td>${esc(r["지금 값"])}</td><td class="c">${gradeChip(r["등급"])}</td><td>${esc(r["출처"])}<div class="hint">${esc((r["비고"] || "").slice(0, 160))}</div></td></tr>`;
}
function provTable(names) {
  const rows = names.map(prov).filter(Boolean);
  if (!rows.length) return "";
  return `<table class="t rt"><tr><th>입력</th><th>지금 값</th><th>등급</th><th>출처 · 메모</th></tr>${rows.map(provRow).join("")}</table>`;
}
// ── 10/16 근거 표시 (리뷰 P1) — 번호만 붙이면 모두 검증된 사실처럼 보이므로 근거의 성격을 함께 적는다.
//   확인된 운영 조건 + 출처 / 모델 계산 결과 + 조건 · 버전 / 모델 가정 + 근거 번호 / 참조 모델 값 / 미검증 검토안 + 관련 실험
//   출처표 줄은 근거 완전성 검사(static/evidence_check.json)에서 연결이 확인된 입력에만 붙인다. 연결이 없으면 '근거 연결 없음 · 검증 필요'.
let ECI = null;
async function ecLoad() { if (!ECI) { try { ECI = await api("/static/evidence_check.json"); } catch (e) { ECI = { inventory: [] }; } } return ECI; }
function ecItem(id) { return ((ECI || {}).inventory || []).find(it => it.id === id) || null; }
const EVK = { op: ["확인된 운영 조건", "ok"], calc: ["모델 계산 결과", "calc"], asm: ["모델 가정", "asm"], ref: ["참조 모델 값", "ref"], prop: ["미검증 검토안", "need"] };
function evRef(id, extra) {
  if (!ECI) return extra || "";
  const it = ecItem(id);
  if (!it || !(it.provenance || []).length) return `근거 연결 없음 · 검증 필요${extra ? " · " + extra : ""}`;
  const P = it.provenance, g = P.length > 1 ? "" : /[~\/]/.test(it.grade || "") ? it.grade : gradeOf(it.grade);   // '◎~△' 처럼 범위인 등급은 그대로 (앞 글자만 쓰면 과장)
  return `출처표 ${P.map(n => `'${n}'`).join(" · ")} · ${it.kind}${g ? " " + g : ""}${(it.hypotheses || []).length ? " · " + it.hypotheses.map(x => /^가설/.test(x) ? x : "가설 " + x).join(", ") : ""}${extra ? " · " + extra : ""}`;
}
function calcRef(D, extra) {
  return `${D.date.slice(5).replace("-", "/")} · ${D.knobs ? (typeof knobSummary === "function" ? knobSummary(D) : "조정값 있음") : "기본 모델"} · 모델 ${D.model_ver || "-"} · 입력 ${D.input_ver || "-"}${extra ? " · " + extra : ""}`;
}
function evTag(k, label, ref) { const [n, c] = EVK[k]; return `<li><span class="evk ${c}">${n}</span><span class="evt">${esc(label)}</span>${ref ? `<span class="evr">${esc(ref)}</span>` : ""}</li>`; }
function evList(tags, title) { return tags && tags.length ? `<div class="evl">${title ? `<span class="rdet-l">${title}</span>` : ""}<ul>${tags.join("")}</ul></div>` : ""; }
function hLabel(h) { const m = String(h.이름 || "").match(/\((H\d+[a-z]?)\)/); return m ? m[1] : "H" + h.ID; }
function hName(h) { return String(h.이름 || "").replace(/\s*\(H\d+[a-z]?\)\s*$/, ""); }
function hState(h) { const s = h.상태 || ""; return /채택/.test(s) ? "채택" : /기각/.test(s) ? "기각" : /보류/.test(s) ? "보류" : /방향은 맞/.test(s) ? "부분" : "진행"; }
// 10/14 운영 표시 — 실험 판정(채택 · 기각 …)을 운영자가 읽는 말로: 모델 기본값 반영 / 영향 미미 / 외부 근거 보강 필요 / 현장 확인 필요
function hOp(h) { return h["운영 표시"] || ({ 채택: "모델 기본값 반영", 기각: "영향 미미", 부분: "외부 근거 보강 필요", 보류: "외부 근거 보강 필요" })[hState(h)] || "진행 중"; }
// ── 운영 요약 · 오늘 판단할 것 (10/14 메뉴 재구성 · 10/14 리뷰 2차 반영) ─────────────────────
// 카드마다 같은 세 문장 구조: 어떤 현상이 나타났나(시뮬레이션 결과) → 어떤 운영 조치를 검토할 수 있나(효과는 아직 실험 안 함) → 어떤 근거 · 가정을 확인해야 하나.
// 링크는 둘: 숫자 설명(근거 문단)과 숫자를 만든 실제 손님 기록(정산 check_flow.py → 팀 목록 → 손님 한 팀의 선택 이유)
// 이용이 제한된 식사의 회차별 모양 — 같은 식사 시간대 회차 중 초과 수요가 있는 회차와 없는 회차 (10/14 · 08:30 집중 점검)
function windowSplit(D, nm) {
  const w0 = String(nm).split(" ")[0], kind = (String(nm).match(/조식|중식|석식/) || [])[0];
  if (!kind) return null;      // 10/16 식사 시간대가 정해지지 않은 업장(파빌리온 등)은 식사 시간대가 다른 회차를 섞어 '남고 몰린다' 고 쓰지 않는다
  const loc = Object.keys(D.venue_detail || {}).find(l => locNames(l).some(n => n.split(" ")[0] === w0)); if (!loc) return null;
  const ws = (D.venue_detail[loc].windows || []).filter(w => (!kind || w.kind === kind) && (w.persons || w.over_persons));
  if (ws.length < 2) return null;
  const full = ws.filter(w => w.over_persons > 0), free = ws.filter(w => !w.over_persons);
  if (!full.length || !free.length) return null;
  const nmW = w => w.name.replace(" (익일)", "").replace(kind || "", "").trim();
  return `${free.map(nmW).join(" · ")}에는 자리가 남고 ${full.map(nmW).join(" · ")}에 몰립니다`;
}
// 10/17 · 더뷔페 조식 2부(익일 포함) 초과 수요 — 지금 하루 결과에서 바로 (막힌 팀의 일행 수 · 팀마다 이 업장에서 처음 막힌 회차에 한 번)
function bfSecondOver(D) {
  const bf = D && D.venue_detail && D.venue_detail.THE_BUFFET; if (!bf || !bf.windows) return null;
  const w = bf.windows.filter(x => x.kind === "조식" && /2부/.test(x.name || ""));
  return w.length ? w.reduce((a, x) => a + (x.over_persons || 0), 0) : null;
}
function opsIssueItems(D, G, VO, ANOM, FL) {
  const SW = D.switch || {}, MO = SW.meal_outcome || null, out = [];
  const okF = FL && !FL.error;
  const top = (SW.by_from || [])[0];
  if (top) {
    const nm = top.from, fl = okF ? (FL.flow || {})[nm] : null;
    const isMeal = !!fl;
    const sameV = fl ? Object.entries(fl).filter(([w]) => w.split(" ")[0] === nm.split(" ")[0]).reduce((a, [, n]) => a + n, 0) : null;
    const finTxt = fl ? ` 이 팀들이 그 식사를 결국 해결한 곳은 ${Object.entries(fl).slice(0, 3).map(([w, n]) => `${w} ${n}팀`).join(", ")}이고, 기다렸다가 같은 업장을 이용한 팀은 ${sameV ? sameV + "팀" : "없었습니다"}${sameV ? "입니다" : ""}.` : "";
    const act = /조식/.test(nm) ? "조식 이용 시간 분산 안내(체크인 때 시간대 배정)를 검토할 수 있습니다"
      : /파빌리온|라운지|바|BAR/.test(nm) ? "붐비는 시간대의 좌석 이용 시간 안내와 가까운 대체 공간 안내를 검토할 수 있습니다"
      : "붐비는 회차의 예약을 앞뒤 회차로 나누는 안내를 검토할 수 있습니다";
    const evs = okF ? (FL.events || []).filter(e => e.from === nm && e.meal && !e.repeat) : [];
    const incN = evs.filter(e => e.included).length;
    const incTxt = evs.length && incN ? ` 이 팀 중 ${incN}팀(${pctS(incN, evs.length)}%)은 그 식사가 객실 상품에 포함된 손님인데, 모델은 이들도 회차 안 줄 서기 30분을 넘기면 다른 방식으로 해결하게 둡니다. 실제로는 기다리거나 늦은 회차로 갈 가능성이 있어 이 수는 많게 잡혔을 수 있습니다.` : "";
    const asm = /더뷔페/.test(nm) ? `더뷔페 좌석 · 회차(조식 2부제 · 석식 3부제)와 회차 안 줄 서기 상한 30분은 가정표 값(${gradeOf((prov("더뷔페 예약") || {})["등급"]) || "△"})이라 실제 회차 운영을 확인해야 합니다.`
      : `좌석 · 회차 · 대기 상한은 가정표 값이라 실제 운영 수치로 확인해야 합니다.`;
    // 10/17 · 2부 초과 수요는 지금 계산(시드 0)에서 바로 읽고, 198~546명은 10/16 민감도 실험(이전 모델 v4 · 시드 3개 · 별도 계산 · 근거사슬 7-16)의 값으로 구분해 적는다
    const bf2 = bfSecondOver(D);
    const wakeTxt = /조식/.test(nm) ? ` 2부(08:30)에 몰리는 모양에는 손님 기상 시각을 30분 단위로 만든 임시값(△)과 회차 경계의 영향이 큽니다.${bf2 != null ? ` 지금 계산(시드 0)에서 2부에서 처음 자리를 못 잡은 팀의 일행은 ${bf2.toLocaleString()}명입니다.` : ""} 참고로 10/16 민감도 실험(이전 모델 v4 · 시드 3개 · 지금 결과와 별도 계산)에서는 기상 시각 분포만 30분 옮기자 2부 초과 수요가 198~546명으로 달라졌습니다(그 실험의 기준 443명 · 신뢰구간이 아니라 검토한 가정 범위). '1부는 남고 2부에 몰린다' 는 말할 수 있지만, 08:30 이라는 시각 자체는 실제 회차별 입장 기록으로 확인해야 합니다.` : "";
    const asm2 = asm + wakeTxt + incTxt;
    const split = windowSplit(D, nm);
    const s0 = /조식/.test(nm) ? "조식 시간대 분산 안내 검토" : /파빌리온|라운지|바|BAR/.test(nm) ? "붐비는 시간대 이용 안내 검토" : "붐비는 회차 예약 분산 검토";
    out.push({ cls: "risk", k: "자리를 못 잡은 팀이 가장 많은 곳", t: `${nm}에 이용 수요 집중`,
      big: `${top.teams}팀`, bl: `좌석 제약을 겪은 고유 팀 · 하루 손님의 ${pctS(top.teams, G.length)}%`,
      one: (split ? split + ". " : "") + (fl ? `기다렸다가 같은 업장을 이용한 팀은 ${sameV ? sameV + "팀" : "없습니다"}.` : ""),
      n: `시뮬레이션에서 ${top.teams}팀이 ${nm}에서 좌석 제약을 경험했습니다(한 번 이상 제약을 겪은 고유 팀 · 하루 손님의 ${pctS(top.teams, G.length)}% · 선택 기준 ${top.events}건).${finTxt}`,
      a: act + ". 이 조치의 효과는 아직 시뮬레이션으로 실험하지 않았습니다." + (/더뷔페/.test(nm) ? " 좌석을 늘리는 조건은 '상황 비교' 에서 비교해 볼 수 있습니다." : ""), c: asm2, sec: 3,
      drill: { t: `이 ${top.teams}팀 보기`, fn: "constrained", arg: nm }, drill2: /더뷔페/.test(nm) ? { t: "좌석을 늘리면? (상황 비교)", fn: "ask", arg: "bs" } : null, weak: true,
      s: s0,
      cue: /조식/.test(nm) ? "기상 시각 분포 가정(△)에 민감 · 10/16 민감도 실험(이전 모델): 30분 이동 시 2부 초과 수요 198~546명 (가정 범위)" : "좌석 · 회차 · 대기 상한은 가정표 값", ask: /더뷔페 조식/.test(nm) ? "bf" : "busy",
      ev: [evTag("calc", `${nm}에서 좌석 제약을 겪은 ${top.teams}팀`, calcRef(D, "시드 0 한 번")),
        evTag("op", "업장 좌석 · 회차 · 운영 창", evRef("prices.SEATS", "업장마다 등급이 다름")),
        evTag("asm", "회차 안 줄 서기 상한 30분", evRef("조정값 queue_max")),
        /조식/.test(nm) ? evTag("asm", "손님 기상 시각 분포 (30분 단위 임시값)", evRef("generate.WAKE_SPREAD", "영향 범위 근거사슬 7-16")) : "",
        evTag("prop", s0, /더뷔페/.test(nm) ? "관련 실험: 상황 비교 더뷔페 338석 (좌석 늘리기만 · 안내 효과는 실험 안 함)" : "관련 실험 없음 · 효과 미실험")].filter(Boolean) });
  }
  if (MO && SW.meal_cases) {
    const outN = MO["호텔 밖 · 객실 식사"] || 0, noRec = MO["같은 식사 시간대 이용 기록 없음"] || 0;
    const inN = SW.meal_cases - outN - noRec;
    out.push({ cls: "flow", k: "이용이 제한된 식사의 행방", t: "호텔 내 대체 이용 전환이 제한적",
      big: `${pctS(inN, SW.meal_cases)}%`, bl: `이용이 제한된 식사 ${SW.meal_cases}건(다음 날 식사 포함) 중 호텔 안 다른 선택 ${inN}건 = 다른 식당 ${MO["다른 호텔 식당"] || 0} · 포장 ${MO["포장"] || 0} · 포함 라운지 ${MO["클럽 라운지 (포함)"] || 0}건 · 나머지 ${outN + noRec}건(호텔 밖 · 객실 ${outN} · 기록 없음 ${noRec})은 '자세히' 와 '막힌 곳 → 최종 흐름'에서`,
      one: `나머지는 호텔 밖 · 객실 식사 ${pctS(outN, SW.meal_cases)}%, 기록 없음 ${pctS(noRec, SW.meal_cases)}%입니다. 투숙 · 비투숙의 차이는 선호가 아니라 모델 선택지 차이입니다(아래).`,
      n: `공급 제약이 발생한 식사 ${SW.meal_cases}건(고객팀 · 날짜 · 식사 시간대마다 한 번${okF ? ` · 같은 식사 시간대에 다시 막힌 시도까지 세면 ${FL.attempts}건` : ""}) 중 호텔 안 다른 선택(다른 식당 · 같은 업장 다른 회차 · 포장 · 라운지)으로 이어진 비율은 ${pctS(inN, SW.meal_cases)}%입니다. ${pctS(outN, SW.meal_cases)}%는 호텔 밖 · 객실 식사, ${pctS(noRec, SW.meal_cases)}%는 그 식사 식사 기록이 없습니다.`,
      a: "만석일 때 같은 식사 시간대의 호텔 안 대안(다른 식당 빈 회차 · 포장 · 룸서비스)을 안내하는 조치의 효과를 검토할 필요가 있습니다. 대안 안내를 넣은 조건은 아직 실험하지 않았습니다.",
      c: (() => { const S = okF ? flowByStay(FL, D) : null; const o = (k, x) => S && S.n[k] ? pctS(S.out[k][x] || 0, S.n[k]) : "-";
        return (S && S.n.비투숙 ? `<b>모델 구조의 한계</b>: 투숙 ${S.n.투숙}건은 다른 호텔 식당 ${o("투숙", "다른 호텔 식당")}% · 호텔 밖 · 객실 ${o("투숙", "호텔 밖 · 객실 식사")}%, 비투숙 ${S.n.비투숙}건은 다른 호텔 식당 ${o("비투숙", "다른 호텔 식당")}% · 기록 없음 ${o("비투숙", "같은 식사 시간대 이용 기록 없음")}%로 크게 다릅니다. ${STAY_NOTE} ` : "") +
          "또 모델은 '호텔 밖' 과 '객실 식사' 를 한 선택지로 묶고 있어, 이 몫이 실제로 호텔 밖으로 나간 수요인지는 확인되지 않았습니다(룸서비스 이용 자료가 있으면 나눌 수 있음). 후기에서 막혀서 다른 유료 식당으로 간 사례 0건은 실제로 막혀 포기한 후기가 2편뿐이라 '전환하지 않는다'는 증거가 아니라 표본 부족입니다."; })(), sec: 3,
      drill: { t: "막힌 곳 → 최종 흐름 보기", fn: "flow" }, weak: true,
      s: "만석 때 호텔 안 대안 안내 검토", cue: "투숙 · 비투숙 차이는 모델 선택지 구조 때문", ask: "flow",
      ev: [evTag("calc", `이용이 제한된 식사 ${SW.meal_cases}건의 최종 행방`, calcRef(D, "시드 0 한 번")),
        evTag("asm", "식당 외 식사 선택지 (객실 키 필요 · 호텔 밖과 객실 식사를 한 선택지로 묶음)", evRef("계수 meal_other")),
        evTag("prop", "만석 때 호텔 안 대안 안내 검토", "관련 실험: 선택지 분리 비교 (근거사슬 7-14 · 7-17 · 모델 구조 비교이며 안내 효과 실험은 아님)")] });
  }
  const risk = (ANOM || []).map(b => ({ b, a: (LIB.anomalies || []).find(x => String(x.ID) === String(b.compare.anomaly)) || {}, r: (b.effect || {})["순매출 (억)"] }))
    .filter(x => x.r && sureEffect(x.r, x.b.seeds) && x.r.diff < 0).sort((x, y) => x.r.diff - y.r.diff)[0];
  if (risk) {
    const E = risk.b.effect || {};
    const gain = Object.entries(E).filter(([n, e]) => / 이용 \(명\)$/.test(n) && e.diff > 0 && sureEffect(e, risk.b.seeds)).sort((x, y) => y[1].diff - x[1].diff)[0];
    const nm = String(risk.a.이름 || "").replace(/\s*하루\s*/, " ").trim();
    out.push({ cls: "what", k: "가장 큰 위험 상황", t: `${nm} 시 대체 수용에 한계`,
      big: `−${Math.abs(risk.r.diff).toFixed(2)}억`, bl: "체류 매출 변화 · 모델 추정 (예측 구간 아님)",
      one: gain ? `대신 받아 주는 곳은 ${gain[0].replace(" 이용 (명)", "")} 약 ${Math.round(gain[1].diff)}명 정도입니다.` : "다른 업장이 받아 주는 몫이 뚜렷하지 않습니다.",
      n: `${risk.a.이름} 시나리오에서 체류 매출이 기준 대비 ${Math.abs(risk.r.diff).toFixed(2)}억 감소했고(같은 손님 · 같은 시드 ${risk.b.seeds}쌍 비교, 95% 구간 ${(-risk.r.hi95).toFixed(2)}~${(-risk.r.lo95).toFixed(2)}억)${gain ? `, ${gain[0].replace(" 이용 (명)", "")}이 약 ${Math.round(gain[1].diff)}명을 추가 수용했습니다` : ""}.`,
      a: "다른 업장의 대체 수용 여력(회차 · 좌석을 늘릴 수 있는지)을 확인할 필요가 있습니다.",
      c: `모델 가정과 기준 시나리오에 따른 추정치이며, 실제 휴업 손실을 확정하는 값이 아닙니다. 상황의 크기는 가정(${gradeOf(risk.a.등급) || "△"})이고, 범위는 모델을 반복해 돌린 변동성이지 매출 예측 구간이 아닙니다.`, sec: 6,
      drill: { t: "이 상황의 하루 열어 보기", fn: "day", arg: risk.b.compare_key },
      s: "다른 업장의 대체 수용 여력 확인", cue: `상황 크기는 가정(${gradeOf(risk.a.등급) || "△"})`, ask: +risk.b.compare.anomaly === 1 ? "closed" : null,
      ev: [evTag("calc", `${nm} 상황의 체류 매출 변화`, calcRef(D, `같은 손님 · 같은 시드 ${risk.b.seeds}쌍 짝 비교`)),
        evTag("asm", "상황의 크기와 손님 반응", `변칙 상황표 등급 ${gradeOf(risk.a.등급) || "△"} · ${evRef("anomaly_scenarios.csv")}`),
        evTag("prop", "다른 업장의 대체 수용 여력 확인", "관련 실험 없음 · 효과 미실험")] });
  }
  {
    const off = Object.entries(VO).map(([loc, r]) => [loc, r.onto ? r.model / r.onto * 100 : null]).filter(r => r[1] != null && !UNIT_TBD.has(r[0]) && !inBand9011(r[1])).sort((a, b) => Math.abs(b[1] - 100) - Math.abs(a[1] - 100))[0];
    if (off) out.push({ cls: "model", k: "모델 확인 사항", t: `${locName(off[0])} 이용이 온톨로지의 ${pctBand(off[1])}`, s: "운영 위험이 아닌 모델 정합 확인 항목", cue: "판단 전에 좌석 · 회차 · 이용 인원을 현장 수치로 확인",
      big: `${off[1]}%`, bl: "온톨로지 대비 이용 인원", one: "이 업장 숫자는 범위로만 읽습니다.",
      n: `이 날 ${locName(off[0])}의 모델 이용 인원이 온톨로지 모델과 ${Math.abs(off[1] - 100)}%p 차이 납니다.`, a: "이 업장의 숫자는 범위로만 읽고, 판단에 쓰기 전에 좌석 · 회차 · 이용 인원을 현장 수치로 확인할 필요가 있습니다.",
      c: "기준일(10/10) 외 날짜이거나 근거가 약한 입력이 걸린 곳일 수 있습니다.", sec: 7, drill: { t: "이 업장 보기", fn: "venue", arg: off[0] },
      ev: [evTag("calc", `${locName(off[0])} 모델 이용 인원`, calcRef(D, "시드 0 한 번")),
        evTag("ref", "온톨로지 이용 인원 (비교 기준)", "제공해 주신 온톨로지 모델의 값 · 실측 아님")] });
  }
  RV2.risk = risk ? risk.b : null;
  return out;
}
// 10/16 카드형 렌더 (v2 이전) — 지금 화면에서는 쓰지 않지만 같은 항목을 그대로 그릴 수 있게 남겨 둔다
function opsIssues(D, G, VO, ANOM, FL) {
  const out = opsIssueItems(D, G, VO, ANOM, FL);
  if (!out.length) return "";
  const card = (x, i) => `<div class="rissue ${x.cls}"><div class="ik">${x.k}</div><div class="it">${esc(x.t)}</div>` +
    (x.big ? `<div class="ibig">${x.big}<span>${esc(x.bl || "")}</span></div>` : "") +
    (x.s ? `<div class="irow"><b title="미검증 검토안 · 효과 미실험">검토안</b>${esc(x.s)}</div>` : "") + (x.cue ? `<div class="irow cue"><b>단서</b>${esc(x.cue)}</div>` : "") +
    `<button class="idet-btn" data-det="${i}" aria-expanded="false">자세히 · 현상 · 조치 · 가정 · 기록 <span aria-hidden="true">▾</span></button>` +
    (x.ask ? `<a class="rlink iask" data-ask="${x.ask}">어시스턴트에게 묻기 →</a>` : "") + `</div>`;
  // 10/16 UX P0-3 · 자세히는 카드 안이 아니라 카드 줄 아래 넓은 상세 칸 하나에 연다 (한 번에 하나 · 다른 카드 높이 그대로)
  const det = (x, i) => `<div class="rdet-body" data-det="${i}" hidden><div class="rdet-h"><span class="rdet-k">${x.k}</span><b>${esc(x.t)}</b>${x.big ? `<span class="rdet-big">${x.big} <small>${esc(x.bl || "")}</small></span>` : ""}<button class="rdet-x" data-close="1" aria-label="상세 닫기">닫기 ✕</button></div>` +
    `<div class="rdet-grid"><div class="rdet-c"><span class="rdet-l">① 모델 계산 결과 · 나타난 현상 <em>모델 산출</em></span>${x.one ? `<p class="ione">${x.one}</p>` : ""}<p>${x.n}</p></div>` +
    `<div class="rdet-c act"><span class="rdet-l">② 미검증 검토안 <em class="need">확인 전 · 효과 미실험</em></span><p>${x.a}</p></div>` +
    `<div class="rdet-c"><span class="rdet-l">③ 확인된 운영 조건 · 적용 가정 <em class="asm">가정 포함</em></span><p>${x.c}</p></div></div>` +
    evList(x.ev, "근거 성격 · 출처 <em>번호가 있어도 검증된 사실이라는 뜻은 아닙니다</em>") +
    `<div class="rdet-links"><span class="rdet-l">④ 계산 근거</span><a class="rlink" data-sec="${x.sec}">숫자 설명 (${x.sec}번 문단) ↓</a>${x.weak ? `<a class="rlink" data-weak="1">적용된 가정 · 확인할 자료 (판단 근거 ⑦) →</a>` : ""}` +
    `${x.drill || x.drill2 ? `<span class="rdet-l">⑤ 관련 화면</span>` : ""}${x.drill ? `<a class="rlink" data-drill="${i}">${esc(x.drill.t)} →</a>` : ""}${x.drill2 ? `<a class="rlink" data-drill="${i}b">${esc(x.drill2.t)} →</a>` : ""}</div></div>`;
  const ops = out.map((x, i) => [x, i]).filter(([x]) => x.cls !== "model"), mdl = out.map((x, i) => [x, i]).filter(([x]) => x.cls === "model");
  return `<h4 class="rissues-h">오늘 확인할 운영 이슈 <span class="hint">· 모델 결과 기준 · 조치는 효과를 실험하지 않은 검토 제안</span></h4><div class="rissues n${ops.length}">${ops.map(([x, i]) => card(x, i)).join("")}</div>` +
    `<div class="rdet">${ops.map(([x, i]) => det(x, i)).join("")}</div>` +
    (mdl.length ? `<h4 class="rissues-h">모델 확인 사항 <span class="hint">· 운영 이슈가 아니라 모델과 참조 모델(온톨로지)의 차이</span></h4><div class="rissues rmodel">${mdl.map(([x, i]) => card(x, i)).join("")}</div><div class="rdet">${mdl.map(([x, i]) => det(x, i)).join("")}</div>` : "") +
    `<script type="application/json" id="issueDrill">${JSON.stringify(Object.assign({}, ...out.map((x, i) => ({ [i]: x.drill || null, [i + "b"]: x.drill2 || null })))).replace(/</g, "\\u003c")}</script>`;
}
// 이슈 카드 '자세히' — 같은 줄의 상세 칸 하나에 연다. 같은 버튼을 다시 누르거나 닫기를 누르면 접히고 그 카드로 돌아간다
function issueDetailWire(el) {
  const close = (box, back) => { box.querySelectorAll(".rdet-body").forEach(b => b.hidden = true); box.classList.remove("open");
    el.querySelectorAll(".idet-btn").forEach(b => { if (box.contains(el.querySelector(`.rdet-body[data-det="${b.dataset.det}"]`))) { b.setAttribute("aria-expanded", "false"); b.closest(".rissue").classList.remove("sel"); } });
    if (back) back.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
  el.querySelectorAll(".idet-btn").forEach(b => b.onclick = () => {
    const body = el.querySelector(`.rdet-body[data-det="${b.dataset.det}"]`); if (!body) return;
    const box = body.closest(".rdet"), was = !body.hidden;
    close(box);
    if (was) return;
    body.hidden = false; box.classList.add("open"); b.setAttribute("aria-expanded", "true"); b.closest(".rissue").classList.add("sel");
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  el.querySelectorAll(".rdet-x").forEach(x => x.onclick = () => { const box = x.closest(".rdet"), i = x.closest(".rdet-body").dataset.det; close(box, el.querySelector(`.idet-btn[data-det="${i}"]`)); });
}
function S0net(D) { return D.total / 1.1 / 1e8; }

function sect(n, title, body, detail, more) {
  RV2.secs[n] = { n, title, body, detail, more };   // 10/17 v2 — 본문 대신 상세 패널에서 연다
  return `<section class="rsec"><div class="rnum">${n}</div><div class="rbody"><h3>${title}</h3><div class="rtext">${body}</div>` +
    (detail ? `<details class="rdet"><summary>근거 · 수치 보기</summary><div class="rdin">${detail}</div></details>` : "") +
    (more ? `<div class="rmore">${more}</div>` : "") + `</div></section>`;
}
function venueOnto(D) {
  // 업장별 모델 ÷ 온톨로지 (풀 단위를 맞춘 poolModel 을 업장마다 합친다 — 지도 화면 '온톨로지 대조' 카드와 같은 셈)
  const R = ontoRef(D); const out = {};
  if (!R.pools) return out;
  const weekday = R.pools.some(q => /-week$/.test(q.id) && q.cap > 0);
  const vd = D.venue_detail || {};
  for (const p of R.pools) {
    if (!(p.cap > 0) || /^room-|breakfast|pizza-addon|pizza-takeout|pavilion/.test(p.id)) continue;
    const loc = L3LOC[p.venue]; if (!loc || !vd[loc]) continue;
    const [m] = poolModel(p, vd[loc], weekday); if (m == null) continue;
    out[loc] = out[loc] || { model: 0, onto: 0, geum: false };
    // 금룡 풀(주중 홀 · PDR · 휴일)은 모델이 홀과 PDR 을 가르지 않아 poolModel 이 풀마다 하루 전체를 돌려준다 — 한 번만 더한다
    if (/^geum/.test(p.id)) { if (!out[loc].geum) { out[loc].model += m; out[loc].geum = true; } } else out[loc].model += m;
    out[loc].onto += p.used || 0;
  }
  return out;
}

// 10/19 소연 ③-3 — 90~110% 판정은 반올림 전 원값으로 한다(운영 요약 · 판단 근거 같은 기준). 반올림하면 경계를 넘는 값(예: 110.3 → 110)은
// 소수 한 자리로 보여 '110% 인데 범위 밖' 처럼 읽히지 않게 한다
const inBand9011 = x => x != null && x >= 90 && x <= 110;
const pctBand = x => { if (x == null || isNaN(x)) return "-"; const r = Math.round(x); return (r === 90 || r === 110) && !inBand9011(x) ? `${(+x).toFixed(1)}%` : `${r}%`; };
// 10/16 QA · PR #47 — 온톨로지 비교값과 모델 값의 단위 대응이 확정되지 않은 업장. 비율은 △ 로 표시하고 90~110% 판정 · 개수에서 뺀다
//   피자힐 홀 · 명월관 저녁: 온톨로지 '세트' ↔ 모델 착석 인원(1세트 = 1인인지 미확인) · 럭스바: 온톨로지 '잔' ↔ 모델 결제 음료 수량(잔 + 병)
const UNIT_TBD = new Set(["PIZZA_HILL", "MYONGWOLGWAN", "LUX_BAR"]);
const UNIT_TBD_NOTE = "△ 단위 미확정 — 피자힐 홀 · 명월관 저녁은 온톨로지 '세트' ↔ 모델 인원, 럭스바는 '잔' ↔ 잔 + 병. 90~110% 판정 · 개수에서 뺍니다";
// 10/16 QA · 연박 집계(stay_day.json)는 v4.1 기본 조건 전용 — 같은 조건의 하루 계산(키가 base_keys 에 있음)일 때만 붙인다
function stayMatch(D) {
  const S = (typeof STAYDAY !== "undefined" && STAYDAY) || {};
  return !!(D && S.base_keys && S.base_keys.includes(D.key) && S.model_ver === D.model_ver && S.input_ver === D.input_ver);
}
// 10/16 연박 집계 — 같은 날을 두 기준으로 (체크인 고객 기준 = 이 화면 · 달력일 운영 기준 = viewer/stay_summary.py). 실험 결과가 있을 때만
const SB_VEN = { THE_BUFFET: "더뷔페", PIZZA_HILL: "피자힐 홀", MYONGWOLGWAN: "명월관", GEUMRYONG: "금룡", ONDAL: "온달", MOEGI: "모에기", LUX_BAR: "LUX BAR (음료 수량 · 잔 · 병)", LE_PASSAGE: "르 파사쥬 (건)" };
function stayBasis(D) {
  const S = (((typeof STAYDAY !== "undefined" && STAYDAY) || {}).summary || {})[D.date];
  if (!S) return null;
  if (!stayMatch(D)) return { p: `<span class="hint">그 날 운영 기준(연박 손님 포함) 값은 ${esc(STAYDAY.condition || "v4.1 기본 조건")}에서만 계산했습니다. 이 결과는 조건(행사 · 규모 · 좌석 · 변칙 · 조정값 · 버전)이 달라 직접 비교할 수 없어 붙이지 않습니다.</span>`, d: "" };
  const R = S.revenue || {}, G = R.operating_by_group || {};
  const f2 = x => x ? (+x.mean).toFixed(2) + "억" : "-";
  const rg = x => x && x.n > 1 ? ` <span class="hint">(${(+x.lo).toFixed(2)}~${(+x.hi).toFixed(2)})</span>` : "";
  const prevG = ["전날 체크인", "그 전날 체크인"].reduce((a, g) => a + (G[g] ? +G[g].mean : 0), 0);
  const p = `<b>그 날 운영 기준</b>으로 다시 세면(연박 집계 · 실험 · 시드 ${S.seeds.length}개) 시뮬레이션에서 이 달력일에 발생한 매출은 ${f2(R.operating_day)}이고, 그중 전날 · 그 전날 체크인한 연박 손님 몫이 ${prevG.toFixed(2)}억, 비투숙 손님 몫이 ${f2(G["비투숙"])}입니다. ` +
    `같은 계산에서 이 날 체크인한 손님의 체류 전체 매출은 ${f2(R.stay_checkin_T)}이고, 같은 시드의 체크인 고객 기준 ${f2(R.screen_stay)}보다 작습니다. 객실 ${S.rooms.inhouse.mean}실 가운데 평균 ${S.rooms.carried.mean}실을 연박 손님이 쓰고 있어 새 체크인이 그만큼 줄기 때문입니다. ` +
    `<b>손님 여정과 체류 가치</b>는 체크인 고객 기준, <b>조식 준비량 · 업장 혼잡 · 일별 운영</b>은 그 날 운영 기준으로 읽습니다.`;
  const V = Object.entries(S.venues || {}).filter(([, v]) => v.onto);
  const pc = pctBand;
  const inb = inBand9011;
  const pcU = (loc, x) => UNIT_TBD.has(loc) ? `<span class="hint">${pc(x)} △</span>` : pc(x);
  const d = `<h5>두 집계 기준 (같은 날 · 같은 v4.1 · 시드 ${S.seeds.join(", ")})</h5>` +
    `<table class="t rt"><tr><th>기준</th><th>누구를 세나</th><th class="n">매출 (순매출)</th><th>읽는 곳</th></tr>` +
    `<tr><td>체크인 고객</td><td>이 날 도착한 손님 · 머무는 동안 전체</td><td class="n">${f2(R.screen_stay)}${rg(R.screen_stay)}</td><td>고객 여정 · 체류 가치</td></tr>` +
    `<tr><td>그 날 운영</td><td>이 날 호텔에 있던 모든 손님 · 이 날 일어난 것만</td><td class="n">${f2(R.operating_day)}${rg(R.operating_day)}</td><td>조식 준비량 · 업장 혼잡 · 일별 운영</td></tr></table>` +
    `<table class="t rt"><tr><th>그 날 운영 매출의 구성</th><th class="n">순매출</th></tr>${["그날 체크인", "전날 체크인", "그 전날 체크인", "비투숙"].filter(g => G[g]).map(g => `<tr><td>${g}</td><td class="n">${f2(G[g])}${rg(G[g])}</td></tr>`).join("")}</table>` +
    (V.length ? `<table class="t rt"><tr><th>업장 (조식 제외)</th><th class="n">온톨로지</th><th class="n">체크인 고객 기준</th><th class="n">그 날 운영 기준</th></tr>${V.map(([loc, v]) => `<tr><td>${esc(SB_VEN[loc] || loc)}</td><td class="n">${v.onto}</td><td class="n${UNIT_TBD.has(loc) || inb(v.screen_pct) ? "" : " hint"}">${pcU(loc, v.screen_pct)}</td><td class="n${UNIT_TBD.has(loc) || inb(v.operating_pct) ? "" : " hint"}">${pcU(loc, v.operating_pct)}</td></tr>`).join("")}</table>` +
      `<div class="hint">${UNIT_TBD_NOTE}.</div>` +
      `<div class="hint">모델 ÷ 온톨로지 실이용(인 · 회, 잔, 건). 체크인 고객 기준은 당일 중 · 석식 + 다음 날 중식(전날 손님의 오늘 중식 대리), 그 날 운영 기준은 이 날 시작한 식사만 셉니다. 럭스바 · 르파사쥬는 두 기준 모두 결제 수량만 셉니다(착석 단계와 결제 수량을 함께 더하면 같은 손님을 두 번 셉니다).</div>` : "") +
    `<div class="hint">점검: 같은 손님 번호 중복 ${S.checks.duplicate_ids}건 · 최대 ${S.checks.max_nights}박 ≤ 워밍업 ${S.warm.join("/")}일 · 투숙 객실 ${S.rooms.inhouse.mean}실 ≤ ${S.rooms.total}실 · 업장 좌석 동시 점유 ≤ 좌석 수 ${S.checks.seats_ok ? "통과" : "초과 있음"}. 워밍업 첫날 이월은 0으로 시작하므로 실제 호텔 장부를 복원한 값은 아닙니다.</div>`;
  return { p, d };
}

// ───────────────────────────────────────────────────────────────────────────
// 10/17 운영 요약 v2 — 세로 카드 나열 대신 한 화면 위계:
//   ① 대표 결과(공급 제약을 겪은 고유 팀) ② 어디에서 막혔나(순위 · 회차 좌석) ③ 상황 실험 · 더 볼 곳.
//   긴 문단 · 표 · 근거는 넓은 상세 패널(openDrawer)로 연다. 숫자는 모두 이 하루 결과 · 시드 묶음 · 정산 기록에서 읽는다.
//   단위 원칙: 팀 = 고유 팀(중복 없음) · 건 = 팀 · 식사마다 한 번 · 초과 수요 = 막힌 팀의 일행 수(명). 서로 직접 비교하지 않는다.
//   10/17 확인(engine.day seen_over): 초과 수요는 팀마다 '이 업장에서 처음 막힌 회차' 에 한 번만 더한다 — 회차마다 다시 세지 않으며 중복이 없다.
// ───────────────────────────────────────────────────────────────────────────
const RV2 = { items: [], secs: {}, lead: "", D: null, G: [], FL: null, exp: [], rows: [], focus: 0, risk: null };
const v2Num = n => Math.round(n).toLocaleString();
const v2Win = n => String(n || "").replace(" (익일)", "").trim();
const v2Sign = (x, d) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d);
// 막힌 곳 이름('더뷔페 조식' · '피자힐' · '더 파빌리온') → 업장 · 그 식사의 회차
function v2Windows(D, nm) {
  const vd = D.venue_detail || {}, kind = (String(nm).match(/조식|중식|석식/) || [])[0];
  const L = Object.keys(vd);
  const loc = L.find(l => locNames(l).some(n => nm === n || String(nm).startsWith(n + " "))) || L.find(l => locNames(l).some(n => n.split(" ")[0] === String(nm).split(" ")[0]));
  if (!loc) return null;
  const v = vd[loc], ws = (v.windows || []).filter(w => (!kind || w.kind === kind) && (w.persons || w.over_persons));
  return { loc, v, kind, ws, cap: v.cap || 0, oneSeat: ws.length > 0 && ws.every(w => (w.persons || 0) <= (v.cap || 0)) };
}
function v2WinLabel(W, w) { const s = v2Win(w.name); const t = (W.kind ? s.replace(W.kind, "").trim() : s) || s;
  return /익일/.test(w.name) && W.ws.some(x => !/익일/.test(x.name)) ? "다음날 " + t : t; }   // 같은 이름의 오늘 · 다음날 회차가 함께 있으면 구분
function v2Why(D, nm) {
  const W = v2Windows(D, nm); if (!W) return "";
  const over = W.ws.filter(w => w.over_persons > 0), sum = over.reduce((a, w) => a + w.over_persons, 0), tm = over.reduce((a, w) => a + (w.over_parties || 0), 0);
  if (!over.length) return `최고 점유 ${W.v.peak_day ?? "-"}%`;
  // 10/17 8차 · '초과 수요 430명' 은 부족한 좌석 수로 읽히기 쉬워 정의를 그대로 쓴다: 그 회차에서 처음 막힌 팀 · 그 일행 수
  return `${over.map(w => v2WinLabel(W, w)).join("·")} · 처음 막힌 ${v2Num(tm)}팀 · ${v2Num(sum)}명`;
}
// 회차별 좌석 — 회차 안에서 자리를 한 번만 쓰는 업장(더뷔페 2부제 등)은 좌석 · 이용 · 초과 수요를 한 축(명)에 놓는다.
// 회차 안에서 여러 번 앉는 업장(파빌리온 등)은 이용 인원이 좌석보다 커서 같은 축에 놓으면 뜻이 섞이므로 최고 점유율만 막대로 그린다.
function v2Focus(D, i) {
  const row = RV2.rows[i]; if (!row) return `<div class="hint">공급 제약이 생긴 곳이 없습니다.</div>`;
  const W = v2Windows(D, row.from), next = W && W.ws.length && W.ws.every(w => /익일/.test(w.name));
  let h = `<div class="fhd"><b>${i + 1}위 ${esc(nmDisp(row.from))} · 회차별 좌석</b><span>${W ? `${next ? "다음날 아침 · " : ""}${v2Num(W.cap)}석` : ""}</span></div>`;
  if (!W || !W.ws.length) return h + `<div class="hint">이 곳의 회차 기록이 없습니다.</div>`;
  const tm = w => `${String(w.t0 || "").slice(-5)}–${w.t1 || ""}`;
  const cls = p => p >= 100 ? "full" : p >= 85 ? "hi" : "";
  if (W.oneSeat) {
    const mx = Math.max(W.cap, ...W.ws.map(w => (w.persons || 0) + (w.over_persons || 0)));
    const P = x => (x / mx * 100).toFixed(2) + "%";
    h += W.ws.map(w => { const p = w.persons || 0, o = w.over_persons || 0;
      return `<div class="slot"><div class="lb"><b>${esc(v2WinLabel(W, w))} <span class="tm">${esc(tm(w))}</span></b><span class="num">${v2Num(p)} / ${v2Num(W.cap)}석 · ${o ? `<em>처음 막힌 ${v2Num(w.over_parties || 0)}팀 · ${v2Num(o)}명</em>${v2Info("over")}` : `${Math.round(p / W.cap * 100)}%`}</span></div>` +
        `<div class="seat"><i class="trk" style="width:${P(W.cap)}"></i><i class="fill ${cls(Math.round(p / W.cap * 100))}" style="width:${P(Math.min(p, W.cap))}"></i>${o ? `<i class="over" style="left:${P(W.cap)};width:${P(o)}"></i>` : ""}<i class="capl" style="left:${P(W.cap)}"></i></div></div>`; }).join("") +
      `<div class="axis"><span style="left:0;transform:none">0</span><span style="left:${P(W.cap)}">좌석 ${v2Num(W.cap)}</span>${mx > W.cap * 1.3 ? `<span style="left:100%;transform:translateX(-100%)">${v2Num(mx)}명</span>` : ""}</div>`;
    const free = W.ws.filter(w => !w.over_persons && (w.persons || 0) < W.cap), full = W.ws.filter(w => w.over_persons > 0);
    const fr = free.map(w => `${josa(v2WinLabel(W, w), "은/는")} <b class="num">${v2Num(W.cap - (w.persons || 0))}석</b>이 남`), fu = full.map(w => `${josa(v2WinLabel(W, w), "은/는")} 만석이고 이 회차에서 처음 자리를 못 잡은 <b class="num">${v2Num(w.over_parties || 0)}팀(${v2Num(w.over_persons)}명)</b>이 다른 선택을 했습니다`);
    const s = fu.length ? [...fr.map(x => x + "고"), ...fu].join(", ") : fr.length ? fr.join(", ") + "았습니다" : "";
    if (s) h += `<div class="fnote">${s}.</div>`;
  } else {
    h += W.ws.map(w => `<div class="slot"><div class="lb"><b>${esc(v2WinLabel(W, w))} <span class="tm">${esc(tm(w))}</span></b><span class="num">최고 점유 ${w.peak_pct}% · 이용 ${v2Num(w.persons || 0)}명${w.over_persons ? ` · <em>처음 막힌 ${v2Num(w.over_parties || 0)}팀 · ${v2Num(w.over_persons)}명</em>` : ""}</span></div>` +
      `<div class="seat pk"><i class="trk" style="width:100%"></i><i class="fill ${cls(w.peak_pct)}" style="width:${Math.min(100, w.peak_pct || 0)}%"></i></div></div>`).join("") +
      `<div class="axis"><span style="left:0;transform:none">0%</span><span style="left:100%;transform:translateX(-100%)">좌석 ${v2Num(W.cap)}석이 다 찬 상태 = 100%</span></div>` +
      `<div class="fnote sm">이 곳은 한 회차 안에서 자리가 여러 번 돌아 이용 인원이 좌석 수보다 많습니다. 그래서 막대는 가장 붐빈 순간의 점유율만 보여 줍니다.</div>`;
  }
  // 단위 주석 — 늘 차트 옆에 (팀 수와 초과 수요를 비교하지 않도록)
  if (W.ws.some(w => w.over_persons > 0)) {
    // 이 줄의 고유 팀 중 같은 업장의 다른 식사(예: 전날 석식)에서 먼저 막혀 그 회차에 세어진 팀 — 정산 기록(FL)이 있을 때만
    const F = RV2.FL && !RV2.FL.error ? RV2.FL : null; let early = null;
    if (F) { const vn = locKey(W.loc).split(" ")[0], ev = (F.events || []).filter(e => String(e.from).split(" ")[0] === vn).sort((a, b) => a.t < b.t ? -1 : 1), first = {};
      ev.forEach(e => { if (!(e.idx in first)) first[e.idx] = e; });
      early = [...new Set(ev.filter(e => e.from === row.from).map(e => e.idx))].filter(i => first[i].from !== row.from).length; }
    const ow = W.ws.filter(w => w.over_persons > 0);
    // 10/17 UX 10차 · 기본은 한 줄, 자세한 범위 설명은 펼쳐서
    h += `<details class="unit"><summary><b>단위</b> 빗금 = 그 회차에서 <u>처음</u> 자리를 못 잡은 팀의 일행 수 · 부족한 좌석 수 아님</summary>빗금은 그 회차에서 <u>처음</u> 자리를 못 잡아 다른 선택을 한 팀의 일행 수입니다(${ow.map(w => `${esc(v2WinLabel(W, w))} ${v2Num(w.over_parties)}팀 · ${v2Num(w.over_persons)}명`).join(" · ")}). 한 팀은 이 업장에서 한 번만 세어 중복이 없고, 부족한 좌석 수를 뜻하지는 않습니다. ` +
      `위 ${v2Num(row.teams)}팀은 ${esc(nmDisp(row.from))}에서 한 번이라도 막힌 고유 팀이라 범위가 다릅니다${early ? `(그중 ${early}팀은 같은 업장의 다른 식사에서 먼저 막혀 그 회차에 셉니다)` : ""}.</details>`;
  }
  const x = i === 0 ? RV2.items.find(t => t.cls === "risk") : null;
  if (x) h += `<div class="frow"><span class="fk">검토안</span><span>${esc(x.s)} <span class="hint">· 효과는 아직 실험하지 않음</span></span></div>` +
    `<button class="flag" data-issue="${RV2.items.indexOf(x)}">${esc(/조식/.test(row.from) ? "기상 시각 분포 가정(△)에 민감" : "좌석 · 회차 · 대기 상한은 가정표 값(△)")} · 근거 보기</button>`;
  else h += `<button class="flag" data-weak="1">좌석 · 회차 · 대기 상한은 가정표 값(△) · 판단 근거에서 확인</button>`;
  h += `<div class="gorow"><a class="go" data-cons="${esc(row.from)}" data-ckey="${esc(D.key)}">이 ${v2Num(row.teams)}팀의 하루 따라가 보기 → 고객 흐름</a>${W ? `<a class="go sub" data-venue="${esc(W.loc)}">${esc(locName(W.loc))} 회차별 점유율</a>` : ""}</div>`;
  return h;
}
// 상황 실험 — 지금 하루와 같은 조건 · 같은 모델 · 입력 버전에서 상황만 넣어 시드 쌍으로 따로 돌린 결과
function v2ExpRows(D, ANOM, AB) {
  const AN = Object.fromEntries((LIB.anomalies || []).map(a => [String(a.ID), a]));
  const rows = [];
  if (AB) rows.push({ grp: "op", nm: `더뷔페 좌석 ${AB.compare.buffet_seats}석`, b: AB, a: { 이름: `더뷔페 좌석 ${AB.compare.buffet_seats}석 (지금 ${((D.venue_detail || {}).THE_BUFFET || {}).cap || "-"}석)`, 등급: "", 설명: "더뷔페 좌석만 늘리고 나머지 조건은 그대로 둔 비교" } });
  ANOM.slice().sort((a, b) => a.compare.anomaly - b.compare.anomaly).forEach(b => { const a = AN[String(b.compare.anomaly)] || {};
    const price = /가격|인상/.test(a.이름 || ""); rows.push({ grp: price ? "op" : "ev", price, nm: String(a.이름 || "").replace(/\s*\(비 오는 주말\)/, ""), b, a }); });
  rows.forEach(x => { x.r = (x.b.effect || {})["순매출 (억)"] || null; x.t = (x.b.effect || {})["공급 제한 겪은 팀 (팀)"] || null;
    x.unc = !x.r || x.r.lo95 == null || (x.r.lo95 <= 0 && x.r.hi95 >= 0); x.weak = !x.unc && !sureEffect(x.r, x.b.seeds);
    x.tunc = !x.t || x.t.lo95 == null || (x.t.lo95 <= 0 && x.t.hi95 >= 0); });
  return rows.filter(x => x.r);
}
function v2ExpHtml(rows) {
  if (!rows.length) return `<div class="hint">이 날 · 이 조건으로 따로 돌려 둔 상황 실험이 없습니다. '상황 비교'에서 조건을 바꿔 돌려 볼 수 있습니다.</div>`;
  const lo = Math.min(0, ...rows.map(x => x.r.lo95)), hi = Math.max(0, ...rows.map(x => x.r.hi95)), pad = (hi - lo) * .04;
  const X = v => ((v - (lo - pad)) / (hi - lo + 2 * pad) * 100);
  const z = X(0);
  const row = (x, i) => { const d = x.r.diff, a = Math.min(X(d), z), w = Math.max(.6, Math.abs(X(d) - z));
    const col = x.unc ? "unc" : d > 0 ? "pos" : "neg";
    const cur = RV2.D && (RV2.D.theta || {}).anomaly && String(x.b.compare.anomaly) === String(RV2.D.theta.anomaly);
    return `<button class="xrow${cur ? " cur" : ""}" data-exp="${i}" title="자세히 · 시드 쌍 · 95% 구간 · 가정 · 비교 가능 여부"><span class="nm">${esc(x.nm)}${x.price ? ` <i class="asm" title="가격에 대한 손님 반응은 모델 가정">△</i>` : ""}</span>` +
      `<span class="dv"><i class="z" style="left:${z.toFixed(2)}%"></i><i class="b ${col}" style="left:${a.toFixed(2)}%;width:${w.toFixed(2)}%"></i><i class="ci" style="left:${X(x.r.lo95).toFixed(2)}%;width:${Math.max(.4, X(x.r.hi95) - X(x.r.lo95)).toFixed(2)}%"></i></span>` +
      `<span class="v num">${x.unc ? `<b class="unc-t">불확실</b>` : `${v2Sign(d, 2)}억`}</span>` +
      `<span class="ci95 num">${v2Sign(+x.r.lo95, 2)} ~ ${v2Sign(+x.r.hi95, 2)}</span>` +
      `<span class="tm num">${!x.t ? "-" : x.tunc ? `<b class="unc-t" title="${v2Sign(x.t.diff, 0)}팀 · 95% ${Math.round(x.t.lo95)}~${Math.round(x.t.hi95)}">불확실</b>` : `${v2Sign(x.t.diff, 0)}팀`}</span></button>`; };
  const op = rows.map((x, i) => [x, i]).filter(([x]) => x.grp === "op"), ev = rows.map((x, i) => [x, i]).filter(([x]) => x.grp === "ev");
  const seeds = [...new Set(rows.map(x => x.b.seeds))].join("·");
  return `<div class="xhdr"><span>조건</span><span>체류 매출 변화 · 막대 = 평균 · 선 = 95% 구간</span><span>평균</span><span>95% 구간 (억)</span><span>제약 팀</span></div>` +
    (op.length ? `<div class="xgrp">운영 조건을 바꾸면 <span>· 조건은 정한 값${op.some(([x]) => x.price) ? " · 가격에 대한 손님 반응은 가정 △" : ""}</span></div>${op.map(([x, i]) => row(x, i)).join("")}` : "") +
    (ev.length ? `<div class="xgrp">이런 일이 생기면 <span>· 상황의 크기는 가정 △</span></div>${ev.map(([x, i]) => row(x, i)).join("")}` : "") +
    `${capN(`같은 손님 · 시드 ${seeds}쌍 평균 · <b class="unc-t">불확실</b> = 95% 구간이 0 포함 · 줄을 누르면 근거`, `${(RV2.D.theta || {}).anomaly ? "음영 줄이 지금 보고 있는 상황입니다. 기준은 추가 변동 없는 같은 날이고, " : "모두 지금 하루와 같은 조건 · "}모델 ${RV2.D.model_ver || "-"} · 입력 ${RV2.D.input_ver || "-"}에서 상황만 넣어 같은 손님 · 같은 시드 ${seeds}쌍을 짝지어 비교한 평균입니다. 불확실 = 95% 구간이 0을 포함해 방향을 말할 수 없음. 제약 팀 = 공급 제약을 겪은 고유 팀 수의 변화.`)}`;
}
function v2ExpDetail(x) {
  const D = RV2.D, b = x.b, r = x.r, t = x.t, n = b.seeds;
  const sameV = b.model_ver === D.model_ver && b.input_ver === D.input_ver, sameBase = b.base_key === D.key;
  const mv = Object.entries(b.effect || {}).filter(([k]) => / 이용 \(명\)$/.test(k)).sort((p, q) => Math.abs(q[1].diff) - Math.abs(p[1].diff)).slice(0, 5);
  const judge = e => e.lo95 <= 0 && e.hi95 >= 0 ? `<b class="unc-t">불확실</b> 95% 구간이 0을 포함` : sureEffect(e, n) ? "시드 반복에서 방향 일관 · 실제 효과 검증은 아님" : "구간은 0을 넘지 않지만 같은 방향 쌍이 적음";
  const src = String(x.a["크기 출처 (signal_stats · 문서)"] || "").split(" — ")[0].replace(/한호님 · /g, "");
  let h = `<dl class="kv">` +
    `<dt>무엇을 바꿨나</dt><dd>${esc(x.a.이름 || x.nm)}${x.a.설명 ? `<div class="hint">${esc(String(x.a.설명).slice(0, 220))}</div>` : ""}</dd>` +
    `<dt>계산 방법</dt><dd>같은 손님 · 같은 시드로 상황만 넣은 하루와 넣지 않은 하루를 <b>${n}쌍</b> 짝지어 돌리고, 쌍마다 차이를 구해 평균을 냈습니다. 오늘 화면의 하루(시드 0 한 번)와는 별도 계산입니다.</dd>` +
    `<dt>체류 매출 변화</dt><dd><b>${v2Sign(r.diff, 3)}억</b> (평균) · 95% 구간 ${v2Sign(+r.lo95, 3)} ~ ${v2Sign(+r.hi95, 3)}억 · ${n}쌍 중 ${r.same_sign ?? "-"}쌍이 같은 방향<div>${judge(r)}</div></dd>` +
    (t ? `<dt>공급 제약 팀 변화</dt><dd><b>${v2Sign(t.diff, 1)}팀</b> · 95% 구간 ${v2Sign(t.lo95, 0)} ~ ${v2Sign(t.hi95, 0)}팀 · ${n}쌍 중 ${t.same_sign ?? "-"}쌍 같은 방향<div>${judge(t)}</div></dd>` : "") +
    (mv.length ? `<dt>이용이 바뀐 곳</dt><dd><table class="t rt"><tr><th>곳</th><th class="n">평균 변화</th><th class="n">95% 구간</th><th>판정</th></tr>${mv.map(([k, e]) => `<tr><td>${esc(k.replace(" 이용 (명)", ""))}</td><td class="n">${v2Sign(e.diff, 0)}명</td><td class="n hint">${v2Sign(e.lo95, 0)} ~ ${v2Sign(e.hi95, 0)}</td><td>${e.lo95 <= 0 && e.hi95 >= 0 ? `<b class="unc-t">불확실</b>` : sureEffect(e, n) ? "확실" : "약함"}</td></tr>`).join("")}</table></dd>` : "") +
    `<dt>가정</dt><dd>${x.price ? `<b>실험 조건</b>: ${esc(String(x.a.설명 || "").split(" · ")[0] || x.nm)} (정한 값). <b>손님 반응</b>: 가격이 오를 때 손님이 덜 오거나 다른 곳을 고르는 정도는 모델에 넣은 가격 민감도 가정입니다 ${gradeChip(x.a.등급 || "△")} — ${esc(String(x.a.설명 || "").split(" · ").slice(1).join(" · "))}. 매출 · 이용 변화는 이 가정에 따라 달라집니다.${x.a.한계 ? `<div class="hint">한계: ${esc(x.a.한계)}</div>` : ""}${src ? `<div class="hint">근거: ${esc(src.slice(0, 120))}</div>` : ""}` : x.grp === "op" && !x.a.등급 ? "좌석 수는 비교용으로 정한 값이고, 늘린 좌석에서 손님이 어떻게 고르는지는 지금 모델의 선택 점수를 그대로 씁니다." : `상황의 크기와 손님 반응은 가정입니다 ${gradeChip(x.a.등급 || "△")}${src ? ` <span class="hint">크기 근거: ${esc(src.slice(0, 120))}</span>` : ""}`}</dd>` +
    `<dt>지금 결과와 비교</dt><dd>${sameV ? `같은 모델 ${esc(b.model_ver)} · 입력 ${esc(b.input_ver)} · 같은 조정값` : `<b>비교 불가</b> · 실험 모델 ${esc(b.model_ver || "-")} · 입력 ${esc(b.input_ver || "-")}`}${sameBase ? " · 기준 하루가 지금 보는 하루와 같은 조건" : " · 기준 하루는 추가 변동 없는 같은 날 (지금 보는 결과와 조건이 다름)"}</dd></dl>` +
    `<div class="callout info">95% 구간은 같은 손님으로 모델을 반복해 돌린 변동성이지 실제 매출 예측 구간이 아닙니다. 상황의 크기가 가정(△)이라 금액보다 방향과 손님이 옮겨 가는 곳을 중심으로 읽습니다.</div>` +
    `<div class="rdet-links"><a class="rlink" data-key="${esc(b.compare_key)}">이 상황의 하루 열어 보기 →</a><a class="rlink" data-go="ask">상황 비교에서 조건 바꿔 보기 →</a><a class="rlink" data-sec="6">상황 실험 전체 표 (6번 문단) →</a></div>`;
  const risk = RV2.items.find(it => it.cls === "what");
  if (risk && x.b === RV2.risk) h += `<h4 class="dr-h">운영 이슈로 본 이 상황</h4>` + issueBody(risk, RV2.items.indexOf(risk));
  return h;
}
// 이슈 상세 — 기존 ①②③ + 근거 성격 + ④⑤ 링크를 상세 패널에 그대로 (계산 · 문장은 opsIssueItems 그대로)
function issueBody(x, i) {
  return `<div class="rdet-grid"><div class="rdet-c"><span class="rdet-l">① 모델 계산 결과 · 나타난 현상 <em>모델 산출</em></span>${x.one ? `<p class="ione">${x.one}</p>` : ""}<p>${x.n}</p></div>` +
    `<div class="rdet-c act"><span class="rdet-l">② 미검증 검토안 <em class="need">확인 전 · 효과 미실험</em></span><p>${x.a}</p></div>` +
    `<div class="rdet-c"><span class="rdet-l">③ 확인된 운영 조건 · 적용 가정 <em class="asm">가정 포함</em></span><p>${x.c}</p></div></div>` +
    evList(x.ev, "근거 성격 · 출처 <em>번호가 있어도 검증된 사실이라는 뜻은 아닙니다</em>") +
    `<div class="rdet-links"><span class="rdet-l">④ 계산 근거</span><a class="rlink" data-sec="${x.sec}">숫자 설명 (${x.sec}번 문단) →</a>${x.weak ? `<a class="rlink" data-weak="1">적용된 가정 · 확인할 자료 (판단 근거 ⑦) →</a>` : ""}` +
    `${x.drill || x.drill2 ? `<span class="rdet-l">⑤ 관련 화면</span>` : ""}${x.drill ? `<a class="rlink" data-drill="${i}">${esc(x.drill.t)} →</a>` : ""}${x.drill2 ? `<a class="rlink" data-drill="${i}b">${esc(x.drill2.t)} →</a>` : ""}</div>`;
}
// 막힌 식사의 행방 — 모델은 '호텔 밖' 과 '객실 식사' 를 한 선택지로 묶는다. 나눌 수 없으므로 이름에 묶음을 드러낸다
const V2_OUT = { "호텔 밖 · 객실 식사": "호텔 밖 또는 객실 식사 (모델에서 한 선택지)", "같은 식사 시간대 이용 기록 없음": "기록 없음", "다른 호텔 식당": "다른 호텔 식당", "포장": "포장", "클럽 라운지 (포함)": "클럽 라운지 (객실 포함)" };
const V2_IN = new Set(["다른 호텔 식당", "포장", "클럽 라운지 (포함)"]);
function v2Flow(D) {
  const SW = D.switch || {}, MO = SW.meal_outcome || null, N = SW.meal_cases || 0;
  if (!MO || !N) return "";
  const inN = Object.entries(MO).filter(([k]) => V2_IN.has(k)).reduce((a, [, n]) => a + n, 0);
  const order = ["다른 호텔 식당", "포장", "클럽 라운지 (포함)", "호텔 밖 · 객실 식사", "같은 식사 시간대 이용 기록 없음"].filter(k => MO[k] != null).concat(Object.keys(MO).filter(k => !V2_OUT[k]));
  const col = { "다른 호텔 식당": "in1", "포장": "in2", "클럽 라운지 (포함)": "in3", "호텔 밖 · 객실 식사": "out", "같은 식사 시간대 이용 기록 없음": "none" };
  return `<div class="flow"><div class="ft"><span>막힌 식사 <b class="num">${v2Num(N)}건</b>${v2Info("meals")}은 어디로 갔나</span><span>호텔 안 다른 선택 <b class="num">${pctS(inN, N)}%</b> <span class="hint">${inN}건</span></span></div>` +
    `<div class="stack">${order.map(k => `<i class="${col[k] || "none"}" style="flex:${MO[k]}" title="${esc(V2_OUT[k] || k)} ${MO[k]}건"></i>`).join("")}</div>` +
    `<div class="leg">${order.map(k => `<span><i class="${col[k] || "none"}"></i>${esc(V2_OUT[k] || outName(k))} <b class="num">${MO[k]}</b></span>`).join("")}</div>` +
    `<a class="go sub" data-open="flow">${pctS(inN, N)}%에 무엇이 들어가나 · 투숙 · 비투숙 차이 →</a></div>`;
}
function v2FlowDetail() {
  const D = RV2.D, FL = RV2.FL, SW = D.switch || {}, MO = SW.meal_outcome || {}, N = SW.meal_cases || 0;
  const inN = Object.entries(MO).filter(([k]) => V2_IN.has(k)).reduce((a, [, n]) => a + n, 0);
  let h = `<p>공급 제한으로 식사 후보가 빠진 경우를 <b>고객팀 · 날짜 · 식사 시간대마다 한 번</b> 세었습니다${FL && !FL.error ? ` (같은 식사 시간대에 다시 막힌 시도까지 세면 ${FL.attempts}건)` : ""}. 최종 상태는 같은 식사 시간대에 결국 먹은 곳입니다.</p>` +
    `<table class="t rt"><tr><th>최종 상태</th><th class="n">건</th><th class="n">비율</th><th>호텔 안 다른 선택에 포함</th></tr>${Object.entries(MO).map(([k, n]) => `<tr><td>${esc(V2_OUT[k] || outName(k))}</td><td class="n">${n}</td><td class="n">${pctS(n, N)}%</td><td>${V2_IN.has(k) ? "포함" : `<span class="hint">빠짐</span>`}</td></tr>`).join("")}<tr><td><b>합계</b></td><td class="n"><b>${N}</b></td><td class="n">100%</td><td><b>${inN}건 · ${pctS(inN, N)}%</b></td></tr></table>`;
  if (FL && !FL.error && FL.flow) {
    const agg = {}; Object.values(FL.flow).forEach(c => Object.entries(c).forEach(([w, n]) => { if (/호텔 밖|기록 없음/.test(w)) return; agg[w] = (agg[w] || 0) + n; }));
    const tot = Object.values(agg).reduce((a, b) => a + b, 0);
    h += `<h5>호텔 안 다른 선택 ${inN}건은 실제로 어디였나 <span class="hint">· 정산 기록 합계 ${tot}건</span></h5><table class="t rt"><tr><th>최종으로 먹은 곳</th><th class="n">건</th><th>막혔던 곳</th></tr>` +
      Object.entries(agg).sort((a, b) => b[1] - a[1]).map(([w, n]) => `<tr><td>${esc(outName(w))}</td><td class="n">${n}</td><td class="hint">${Object.entries(FL.flow).filter(([, c]) => c[w]).map(([o, c]) => `${esc(o)} ${c[w]}`).join(" · ")}</td></tr>`).join("") + `</table>`;
    const S = flowByStay(FL, D), o = (k, x) => S.n[k] ? pctS(S.out[k][x] || 0, S.n[k]) + "%" : "-";
    h += `<h5>투숙 · 비투숙으로 나누면</h5><table class="t rt"><tr><th>최종 상태</th><th class="n">투숙 ${S.n.투숙}건</th><th class="n">비투숙 ${S.n.비투숙}건</th></tr>${Object.keys(MO).map(k => `<tr><td>${esc(V2_OUT[k] || outName(k))}</td><td class="n">${o("투숙", k)}</td><td class="n">${k === "호텔 밖 · 객실 식사" ? `<span class="hint">선택지 없음</span>` : o("비투숙", k)}</td></tr>`).join("")}</table>`;
  }
  h += `<div class="callout warn"><b>집계의 한계</b> · 모델은 '호텔 밖에서 먹기' 와 '객실에서 먹기' 를 <b>식당 외 식사</b> 한 선택지로 묶습니다. 그래서 ${MO["호텔 밖 · 객실 식사"] || 0}건 중 실제로 호텔 밖으로 나간 수요가 얼마인지는 이 결과로 나눌 수 없습니다(룸서비스 이용 자료가 있으면 나눌 수 있음). ${STAY_NOTE}</div>`;
  const x = RV2.items.find(t => t.cls === "flow");
  if (x) h += `<h4 class="dr-h">운영 이슈로 본 막힌 식사</h4>` + issueBody(x, RV2.items.indexOf(x));
  return h;
}
function v2TeamsDetail() {
  const D = RV2.D, G = RV2.G, T = G.filter(g => (g.n_switch || 0) > 0), n = T.length;
  const gs = T.filter(g => g.is_guest).length, kids = T.filter(g => g.kids).length;
  const by = {}; T.forEach(g => by[g.purpose || "-"] = (by[g.purpose || "-"] || 0) + 1);
  const times = { "1번": 0, "2번": 0, "3번 이상": 0 }; T.forEach(g => times[g.n_switch >= 3 ? "3번 이상" : g.n_switch + "번"]++);
  const allGuest = G.filter(g => g.is_guest).length;
  return `<p>점수가 더 높았던 곳이 만석 · 대기로 빠져 한 번 이상 다른 선택을 한 <b>고유 팀 ${v2Num(n)}팀</b>(방문 ${v2Num(G.length)}팀 중 ${pctS(n, G.length)}%)입니다. 자리가 있었으면 반드시 그곳에 갔다는 뜻은 아닙니다.</p>` +
    `<div class="rgrid2"><div><h5>누구인가</h5><table class="t rt"><tr><th>구분</th><th class="n">팀</th><th class="n">그 구분의 몇 %</th></tr><tr><td>투숙</td><td class="n">${gs}</td><td class="n">${pctS(gs, allGuest)}%</td></tr><tr><td>비투숙</td><td class="n">${n - gs}</td><td class="n">${pctS(n - gs, G.length - allGuest)}%</td></tr><tr><td>아이 동반</td><td class="n">${kids}</td><td class="n">${pctS(kids, G.filter(g => g.kids).length)}%</td></tr></table>` +
    `<h5>몇 번 막혔나</h5><table class="t rt">${Object.entries(times).map(([k, v]) => `<tr><td>${k}</td><td class="n">${v}팀</td></tr>`).join("")}</table></div>` +
    `<div><h5>방문 목적</h5>${miniBars(by, n)}</div></div>` +
    `<h5>막힌 곳별 <span class="hint">· 한 팀이 여러 곳에서 막히면 곳마다 한 번씩 셉니다 (합계가 ${v2Num(n)}팀보다 큼)</span></h5><table class="t rt"><tr><th>막힌 곳</th><th class="n">고유 팀</th><th class="n">선택 기준 건</th><th></th></tr>${((D.switch || {}).by_from || []).map(r => `<tr><td>${esc(nmDisp(r.from))}</td><td class="n">${r.teams}</td><td class="n hint">${r.events}</td><td><a class="rlink" data-cons="${esc(r.from)}">팀 목록 → 고객 흐름</a></td></tr>`).join("")}</table>`;
}
function v2SecDetail(n) {
  const s = RV2.secs[n]; if (!s) return "";
  return `<div class="v2sec"><div class="rtext">${s.body}</div>${s.detail ? `<div class="rdin">${s.detail}</div>` : ""}${s.more ? `<div class="rmore">${s.more}</div>` : ""}</div>`;
}
function v2Open(k) {
  const [t, a] = String(k).split(":");
  if (t === "sec") { const s = RV2.secs[+a]; if (s) openDrawer(s.title, `근거 · 수치 · ${+a}번 문단`, v2SecDetail(+a), v2Wire, { wide: true }); return; }
  if (t === "issue") { const x = RV2.items[+a]; if (x) openDrawer(x.t, x.k + " · 모델 결과 기준 · 조치는 효과 미실험", (x.big ? `<div class="dr-big"><b>${x.big}</b> <span class="hint">${esc(x.bl || "")}</span></div>` : "") + issueBody(x, +a), v2Wire, { wide: true }); return; }
  if (t === "exp") { const x = RV2.exp[+a]; if (x) openDrawer(x.nm, "상황 실험 · 오늘 결과와 별도 계산", v2ExpDetail(x), v2Wire, { wide: true }); return; }
  if (t === "flow") { openDrawer("막힌 식사의 행방", "고객팀 · 날짜 · 식사마다 한 번 · 시드 0", v2FlowDetail(), v2Wire, { wide: true }); return; }
  if (t === "teams") { openDrawer("공급 제약을 겪은 팀의 구성", "고유 팀 · 시드 0", v2TeamsDetail(), v2Wire, { wide: true }); return; }
  if (t === "issues") { const L = RV2.items.map((x, i) => [x, i]).filter(([x]) => x.cls !== "model");
    openDrawer("오늘 확인할 운영 이슈", "모델 결과 기준 · 조치는 효과를 실험하지 않은 검토 제안", L.map(([x, i]) => `<section class="dr-issue"><div class="dr-ik">${esc(x.k)}</div><h4 class="dr-h">${esc(x.t)}${x.big ? ` <span class="dr-bigs">${x.big}</span>` : ""}</h4><div class="hint">${esc(x.bl || "")}</div>${issueBody(x, i)}</section>`).join(""), v2Wire, { wide: true }); return; }
  if (t === "lead") { openDrawer("이 날 전체를 문장으로", "계산 결과에서 자동으로 만든 문장", `<div class="rlead">${RV2.lead}</div>`, v2Wire, { wide: true }); return; }
}
// 10/17 리뷰 4 — 숫자 옆 정보 버튼: 435팀 · 421건 · 221팀 · 430명의 세는 법(정의 · 중복 처리)을 그 자리에서 보여 준다
function v2Info(k, tone) { return `<button class="nfo${tone ? " " + tone : ""}" data-info="${k}" aria-label="이 숫자를 세는 법" title="이 숫자를 세는 법">i</button>`; }
function v2Defs() {
  const D = RV2.D, G = RV2.G, SW = D.switch || {}, row = RV2.rows[RV2.focus] || {}, F = RV2.FL && !RV2.FL.error ? RV2.FL : null;
  const sw = G.filter(g => (g.n_switch || 0) > 0).length, basis = `기준: ${D.date.slice(5).replace("-", "/")} · 시드 0 한 번 · 모델 ${esc(D.model_ver || "-")} · 입력 ${esc(D.input_ver || "-")}`;
  let mt = null, m2 = null;
  if (F) { const c = {}; (F.events || []).filter(e => e.meal && !e.repeat).forEach(e => c[e.idx] = (c[e.idx] || 0) + 1); mt = Object.keys(c).length; m2 = Object.values(c).filter(n => n > 1).length; }
  const W = row.from ? v2Windows(D, row.from) : null, ow = W ? W.ws.filter(w => w.over_persons > 0) : [];
  return {
    teams: [`공급 제약을 겪은 팀 ${v2Num(sw)}팀`, `점수가 더 높았던 곳이 만석 · 대기로 빠져 하루 동안 한 번 이상 다른 선택을 한 <b>고유 팀</b>입니다. 한 팀이 여러 번 막혀도 1팀으로 셉니다. 분모는 그 날 방문한 ${v2Num(G.length)}팀입니다.`, basis],
    meals: [`막힌 식사 ${v2Num(SW.meal_cases || 0)}건`, `식사 후보가 공급 제약으로 빠진 경우를 <b>팀 · 날짜 · 식사 시간대마다 한 번</b> 셉니다. 같은 식사에서 여러 번 막혀도 1건이고, 한 팀이 저녁과 다음날 아침에 각각 막히면 2건입니다${mt != null ? `(${v2Num(mt)}팀 · 그중 ${v2Num(m2)}팀이 2건 이상)` : ""}.${F ? ` 같은 식사에서 다시 막힌 시도까지 세면 ${v2Num(F.attempts)}건입니다.` : ""} 식사 업장이 아닌 곳(더 파빌리온 · 바 · 라운지 해피아워)에서 막힌 경우는 빠집니다.`, basis],
    rowteams: [row.from ? `${esc(nmDisp(row.from))} ${v2Num(row.teams)}팀` : "고유 팀", row.from ? `${esc(nmDisp(row.from))}이 만석 · 대기로 후보에서 빠진 적이 한 번 이상 있는 <b>고유 팀</b>입니다(선택 기준 ${v2Num(row.events)}건 = 후보를 고를 때마다 센 횟수). 한 팀이 여러 곳에서 막히면 곳마다 다시 세므로 순위의 합은 ${v2Num(sw)}팀보다 큽니다.` : "", basis],
    over: ["처음 막힌 팀 · 일행 수 (화면 이전 이름: 초과 수요)", `그 회차에서 처음 자리를 못 잡아 다른 선택을 한 팀과 그 <b>일행 수 합</b>입니다. 부족한 좌석 수가 아닙니다. 한 팀은 이 업장에서 <b>처음 막힌 회차에 한 번만</b> 더하므로 중복이 없습니다${ow.length ? `(${ow.map(w => `${esc(v2WinLabel(W, w))} ${v2Num(w.over_persons)}명 = ${v2Num(w.over_parties)}팀`).join(" · ")})` : ""}. 고유 팀 수와 단위가 달라 직접 비교하지 않습니다.`, basis],
  };
}
function v2InfoClose() { document.querySelectorAll(".nfo-pop").forEach(x => x.remove()); document.querySelectorAll(".nfo[aria-expanded='true']").forEach(b => b.setAttribute("aria-expanded", "false")); }
function v2InfoOpen(btn) {
  const was = btn.getAttribute("aria-expanded") === "true"; v2InfoClose(); if (was) return;
  const d = v2Defs()[btn.dataset.info]; if (!d) return;
  const pop = document.createElement("div"); pop.className = "nfo-pop"; pop.setAttribute("role", "dialog");
  pop.innerHTML = `<b>${d[0]}</b><p>${d[1]}</p><small>${d[2]}</small>`; document.body.appendChild(pop);
  const r = btn.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  let x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), innerWidth - w - 8), y = r.bottom + 8;
  if (y + h > innerHeight - 8) y = Math.max(64, r.top - h - 8);
  pop.style.left = x + "px"; pop.style.top = y + "px"; btn.setAttribute("aria-expanded", "true");
  if (!v2InfoOpen.wired) { v2InfoOpen.wired = true;
    document.addEventListener("mousedown", e => { if (!e.target.closest(".nfo-pop, .nfo")) v2InfoClose(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") v2InfoClose(); });
    document.addEventListener("scroll", v2InfoClose, true); }
}
function v2Drill(id) {
  const x = RV2.items[parseInt(id, 10)], d = x && (String(id).endsWith("b") ? x.drill2 : x.drill); if (!d) return;
  closeDrawer();
  if (d.fn === "constrained") { setMode("day"); showConstrained(d.arg); }
  else if (d.fn === "flow") { setMode("day"); showFlow(); }
  else if (d.fn === "day") { setMode("day"); loadDay(d.arg); }
  else if (d.fn === "venue") { setMode("day"); placePanel(d.arg); }
  else if (d.fn === "ask") {
    // 10/19 · 링크가 가리키는 상황(예: 더뷔페 338석)을 지정해서 연다 — 직전에 보던 다른 상황이 남지 않게
    if (d.arg && typeof ASK !== "undefined") Object.assign(ASK, { scn: d.arg, venue: null, venueSet: false, error: null });
    setMode("ask");
  }
}
function v2Assist(open) { const L = document.querySelector(".rlayout"); if (!L) return; const on = open == null ? L.classList.contains("as-closed") : open; L.classList.toggle("as-closed", !on); L.classList.toggle("as-show", on); const b = document.getElementById("v2Asst"); if (b) b.setAttribute("aria-pressed", on ? "true" : "false"); }
// 본문과 상세 패널이 같은 연결을 쓴다
function v2Wire(root) {
  const on = (sel, f) => root.querySelectorAll(sel).forEach(a => a.onclick = e => { e.preventDefault(); f(a); });
  on("[data-open]", a => v2Open(a.dataset.open));
  on("[data-issue]", a => v2Open("issue:" + a.dataset.issue));
  on("[data-exp]", a => v2Open("exp:" + a.dataset.exp));
  on("[data-sec]", a => v2Open("sec:" + a.dataset.sec));
  on("[data-go]", a => { closeDrawer(); setMode(a.dataset.go); });
  on("[data-weak]", () => { closeDrawer(); goWeak(); });
  on("[data-drill]", a => v2Drill(a.dataset.drill));
  on("[data-cons]", a => { closeDrawer(); setMode("day"); showConstrained(a.dataset.cons, a.dataset.ckey || (RV2.D && RV2.D.key)); });
  on("[data-venue]", a => { closeDrawer(); setMode("day"); placePanel(a.dataset.venue); });
  on("[data-key]", a => { closeDrawer(); RPT.view = "day"; loadDay(a.dataset.key); });
  on("[data-view]", a => { closeDrawer(); RPT.view = a.dataset.view; syncReportLeft(); renderReport(); });
  on("[data-ask]", a => { closeDrawer(); v2Assist(true); assistAsk(a.dataset.ask); });
  on("[data-rk]", a => { const i = +a.dataset.rk; RV2.focus = i; root.querySelectorAll("[data-rk]").forEach(r => { r.classList.toggle("sel", +r.dataset.rk === i); r.setAttribute("aria-pressed", +r.dataset.rk === i ? "true" : "false"); });
    if (a.dataset.alert) { const f = root.querySelector("#v2Focus"); if (f && f.scrollIntoView) f.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
    const f = root.querySelector("#v2Focus"); if (f) { f.innerHTML = v2Focus(RV2.D, i); v2Wire(f); f.classList.remove("flash"); void f.offsetWidth; f.classList.add("flash"); } });
  on("[data-info]", a => v2InfoOpen(a));
}

async function renderReport() {
  reportShell();
  const el = $("#reportView .rmain");
  if (RPT.view === "guest") { assistSet(null, "rAssist"); return renderGuestSummary(el); }
  if (!DAY) { el.innerHTML = `<div class="rwrap"><div class="empty">계산해 둔 날을 불러오는 중입니다…</div></div>`; return; }
  syncReportLeft();
  await ecLoad();
  if (typeof stayLoad === "function") await stayLoad();
  const D = DAY, th = D.theta || {};
  RPT.key = D.key;
  const G = D.guests || [];
  const guests = G.filter(g => g.is_guest), day = G.filter(g => !g.is_guest);
  const persons = D.persons || 0;
  const vd = D.venue_detail || {};
  const V = Object.entries(vd).filter(([, v]) => v.cap && v.persons_day > 0).map(([loc, v]) => ({ loc, v }));
  const overAll = V.reduce((a, x) => a + (x.v.over_persons || 0), 0);
  // 원하던 곳이 차거나 대기가 길어 한 번이라도 다른 곳으로 바꾼 팀 (팀 단위 · 중복 없음)
  const swTeams = G.filter(g => (g.n_switch || 0) > 0).length, swPct = pctS(swTeams, G.length);
  const full = V.filter(x => (x.v.peak_day || 0) >= 95).sort((a, b) => (b.v.over_persons || 0) - (a.v.over_persons || 0));
  const VO = venueOnto(D);
  const weekday = isWeekday(D.date);
  const dlabel = `${D.date.slice(5).replace("-", "/")} (${"일월화수목금토"[new Date(D.date + "T12:00:00").getDay()]})`;

  // 시드 묶음 · 변칙 묶음
  let B = null, ANOM = [];
  try { B = await api("/api/day/band?key=" + encodeURIComponent(D.key)); if (B && B.model_ver !== D.model_ver) B = null; } catch (e) {}
  try {
    const wk = isWeekday(D.date);
    const sig = t => JSON.stringify(Object.entries(t || {}).filter(([k, v]) => !["anomaly", "anomaly_k", "seed"].includes(k) && !(!wk && WEEKDAY_ONLY.includes(k)) && v != null && v !== 0 && v !== false).sort());
    const want = sig(th);
    ANOM = (await api("/api/bands")).filter(b => b.compare && b.compare.anomaly && b.date === D.date && sig(b.theta) === want && b.model_ver === LIB.model_ver && b.input_ver === LIB.input_ver);
  } catch (e) {}
  const S = B && (B.compare_key === D.key ? B.comp : B.base);
  const netR = S && S["순매출 (억)"];
  const swR = S && S["공급 제한 겪은 팀 (팀)"];

  // 손님 구성
  const cnt = arr => { const o = {}; arr.forEach(g => o[g.purpose] = (o[g.purpose] || 0) + 1); return o; };
  const pg = cnt(guests), pd = cnt(day);
  const kids = guests.filter(g => g.kids).length;
  const purpList = (o, tot) => topN(o, 3).map(([k, n]) => `${k} ${pctS(n, tot)}%`).join(", ");
  const anomaly = th.anomaly ? (LIB.anomalies || []).find(a => String(a.ID) === String(th.anomaly)) : null;

  // ── 10/17 v2 — 본문은 대표 결과 · 막힌 곳 · 상황 실험 · 더 볼 곳만 그린다. 근거 문단 1~7 은 sect() 가 RV2.secs 에 모아 두고 상세 패널로 연다
  const topFrom = ((D.switch || {}).by_from || [])[0];
  RV2.secs = {}; RV2.D = D; RV2.G = G;
  let h = "";
  // ── 0. 한 문단 결론 ('이 날 전체를 문장으로' 상세 패널)
  const topVen = V.slice().sort((a, b) => (b.v.krw || 0) - (a.v.krw || 0)).slice(0, 2).map(x => locName(x.loc));
  const fullNames = full.slice(0, 3).map(x => locName(x.loc));
  const ratios = Object.entries(VO).map(([loc, r]) => [loc, r.onto ? r.model / r.onto * 100 : null]).filter(r => r[1] != null && !UNIT_TBD.has(r[0]));
  const inBand = ratios.filter(r => inBand9011(r[1])).length;   // 10/19 원값 기준 (판단 근거와 같게)
  let lead = `이 날은 투숙 ${guests.length}팀과 비투숙 ${day.length}팀이 호텔을 찾은 것으로 계산했습니다. `;
  lead += topVen.length ? `매출이 가장 큰 업장은 ${topVen.length > 1 ? josa(topVen[0], "과/와") + " " + topVen[1] : topVen[0]}이고, ` : "";
  lead += fullNames.length ? `${full.length > fullNames.length ? `${fullNames.join(" · ")} 등 ${josa(full.length + "곳", "은/는")}` : josa(fullNames.join(" · "), "은/는")} 가장 붐비는 회차에 자리가 다 찼습니다. 그래서 전체 ${G.length.toLocaleString()}팀 중 ${swTeams.toLocaleString()}팀(${swPct}%)이 한 번 이상 점수가 더 높았던 곳을 공급 제한으로 못 가고 다른 곳을 골랐습니다. ` : `만석이 된 업장은 없었습니다. `;
  // 10/19 UX 22차 — '선택한 실행' 과 '반복 평균' 을 숫자 바로 옆에서 구분 (같은 판정 규칙 · 다른 집계 대상)
  const nRep = (refreshDays.list || []).filter(d => d.date === D.date && d.scenario === "none" && +d.scale === 1 && d.theta && typeof sameV4 === "function" && sameV4(d.theta, d.date) && d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver).length;
  if (ratios.length) lead += `<b>선택한 실행(시드 ${(D.theta || {}).seed || 0} 한 번)</b>으로 보면 온톨로지 모델 대비 단위 대응이 확인된 식당 ${ratios.length}곳 중 ${inBand}곳이 90~110% 안에 있습니다(피자힐 홀 · 명월관 · 럭스바는 단위 미확정이라 뺌). ` +
    (nRep > 1 ? `같은 날 시드 ${nRep}개의 <b>반복 평균</b>은 판단 근거 ② 에 있고, 판정 규칙은 같지만 집계 대상이 달라 개수가 다를 수 있습니다. ` : `시드 여러 개의 반복 평균은 판단 근거 ② 에 모입니다(판정 규칙은 같고 집계 대상이 다름). `);
  if (anomaly) lead += `<b>이 날은 '${esc(anomaly.이름)}' 상황을 넣어 돌린 결과입니다.</b> `;
  RV2.lead = lead;
  let FL = null; try { FL = await flowOf(D.key); } catch (e) {}
  RV2.FL = FL;
  RV2.items = opsIssueItems(D, G, VO, ANOM, FL);

  // ── 1. 누가 왔나
  const p1 = `투숙 손님은 ${purpList(pg, guests.length)} 순으로 많고, 아이와 함께 온 팀이 ${pctS(kids, guests.length)}%입니다. 비투숙 손님은 ${purpList(pd, day.length)} 순입니다. ` +
    `객실 수는 건물마다 그날 채울 객실을 먼저 정하는 방식이라, 손님 구성을 바꿔도 객실 판매는 흔들리지 않습니다.` +
    (weekday ? ` 평일이라 비투숙 손님은 주말 기준의 절반으로 두었습니다(가설 H4b · 외부 근거로 유지하는 모델 가정 · 범위 0.4~0.7 · ${esc(evRef("조정값 wd_day"))}).` : "");
  const d1 = `<div class="rgrid2"><div><h5>투숙 손님 목적</h5>${miniBars(pg, guests.length)}</div><div><h5>비투숙 손님 목적</h5>${miniBars(pd, day.length)}</div></div>` +
    `<h5>이 숫자를 만든 입력</h5>` + provTable(["객실 가동률", "객실 수", "목적 섞기", "연령 섞기", "비투숙 팀 수", "날짜 배율"]);
  h += sect(1, "누가 왔나", p1, d1, `<a class="rlink" data-view="guest">왼쪽에서 손님 한 팀을 골라 따라가 보기 →</a>`);

  // ── 2. 무엇을 원했나 (성향)
  const DIN = LIB.dining || {};
  const prefOf = p => (DIN[p] || []).slice().sort((a, b) => b[1] - a[1]);
  const mainP = topN(Object.fromEntries(Object.entries(pg).map(([k, n]) => [k, n + (pd[k] || 0)])), 3).map(([k]) => k);
  const p2 = mainP.map(p => {
    const t = prefOf(p).slice(0, 2); if (!t.length) return "";
    const a = `${locName(t[0][0])}(${Math.round(t[0][1] * 100)}%)`, b = t[1] ? `${locName(t[1][0])}(${Math.round(t[1][1] * 100)}%)` : "";
    return `${p} 손님이 가장 가고 싶어 하는 곳은 ${b ? josa(a, "과/와") + " " + b : a}입니다`;
  }).filter(Boolean).join(". ") + ". " +
    `이 선호는 후기 페르소나에서 뽑은 목적별 식당 비중입니다. 실제로 어디에 갈지는 대기 시간 · 이동 거리 · 식사 시간 · 식사 포함 혜택 · 예약 · 아이 동반 같은 조건과 함께 점수로 정해집니다. ` +
    `다만 후기에서 뽑은 성향(대기 회피 · 조망 중시 같은 일곱 가지)은 대기 회피가 포장 선택에 쓰이는 것 말고는 지금 모델의 점수에 들어가지 않습니다. 교차검증에서 성향을 넣지 않는 쪽이 새 후기를 더 잘 맞혔고, 하루 손님에게는 성향 값이 아예 없습니다.`;
  const sns = (LIB.sns || {}).PIZZA_HILL;
  const d2 = `<table class="t rt"><tr><th>목적</th><th>가고 싶은 식당 (비중)</th></tr>` +
    mainP.map(p => `<tr><td>${esc(p)}</td><td>${prefOf(p).slice(0, 4).map(([v, w]) => `${esc(locName(v))} ${Math.round(w * 100)}%`).join(" · ")}</td></tr>`).join("") + `</table>` +
    (sns ? `<div class="hint">SNS 대조 (피자힐): 문장형 게시물 ${sns.n}건의 목적 구성은 화면의 피자힐 카드에서 모델 · 온톨로지와 나란히 볼 수 있습니다.</div>` : "") +
    `<h5>지금 선택에 작용하는 것과 작용하지 않는 것</h5><table class="t rt"><tr><th>구분</th><th>무엇</th></tr>` +
    `<tr><td><span class="tstate on">작용함</span></td><td>대기 시간 · 이동 거리 · 식사 시간 · 객실 상품의 식사 포함 혜택 · 예약 · 아이 동반 · 목적별 가고 싶은 식당 · 객실에서 쉬기 · 좌석 · 회차 (공급 제한)</td></tr>` +
    `<tr><td><span class="tstate part">일부만</span></td><td>대기 회피 — 후기 손님이 피자힐 · 르파사쥬 포장을 고를 때만 (하루 손님은 값이 없어 작용 안 함)</td></tr>` +
    `<tr><td><span class="tstate off">작용 안 함</span></td><td>이동 최소화 · 격식 선호 · 조망 중시 · 새로움 추구 · 함께 먹기 선호 · 조용함 선호 (후기 페르소나에서 추출했지만 성향 강도 0)</td></tr></table>` +
    `<div class="hint">${traitNote()}</div>` +
    `<h5>이 숫자를 만든 입력</h5>` + provTable(["가고 싶은 식당", "식당 가고 싶음 비율", "AI 유형 섞기", "행동 점수 계수"]);
  h += sect(2, "무엇을 원했나 · 선호와 선택 조건", p2, d2);

  // ── 3. 어디로 갔나 (막힘 · 대체 행동)
  const SW = D.switch || null;
  const sw = (SW ? SW.by_from : []).slice(0, 3);
  const swTxt = sw.map((x, i) => `${nmDisp(x.from)}에서 ${x.teams}팀(${x.events}건)`).join(", ");
  const MO = SW && SW.meal_outcome ? SW.meal_outcome : null;
  const moTxt = MO && SW.meal_cases ? `식사 이용이 제한된 ${SW.meal_cases}건(팀 · 날짜 · 식사 기준)의 최종 결과는 ${Object.entries(MO).map(([k, n]) => `${k} ${pctS(n, SW.meal_cases)}%`).join(", ")}입니다. ` : "";
  const byWin = {}; full.slice(0, 4).forEach(x => (byWin[x.v.peak_window || "가장 붐비는 회차"] = byWin[x.v.peak_window || "가장 붐비는 회차"] || []).push(locName(x.loc)));
  const fullTxt = Object.entries(byWin).map(([w, ns]) => `${josa(ns.join(" · "), "은/는")} ${w}에`).join(", ");
  const p3 = (full.length ? `${fullTxt} 자리가 다 찼습니다${full.length > 4 ? `(만석이 된 곳은 모두 ${full.length}곳)` : ""}. ` : "") +
    `자리가 없거나 대기가 길면 손님은 기다리거나, 다른 곳으로 가거나, 그 식사를 다른 방식으로 해결합니다. ` +
    (sw.length ? `점수가 더 높았지만 공급 제한으로 빠진 곳이 많았던 순서로 보면 ${swTxt}입니다. ` : "") + moTxt +
    `객실로 돌아갔다고 식사를 포기한 것은 아니어서, 같은 식사 시간대에 결국 무엇을 먹었는지까지 따라가 셉니다.`;
  const rows3 = V.slice().sort((a, b) => (b.v.persons_day || 0) - (a.v.persons_day || 0)).slice(0, 9);
  const d3 = `<table class="t rt"><tr><th>업장</th><th class="n">이용 인원</th><th class="n">최고 점유율</th><th class="n">빠진 팀</th><th class="n">온톨로지 대비<div class="hint">선택한 실행 · 시드 1회</div></th></tr>` +
    rows3.map(x => { const r = VO[x.loc]; const rr = r && r.onto ? r.model / r.onto * 100 : null;
      return `<tr><td>${esc(locName(x.loc))}</td><td class="n">${(x.v.persons_day || 0).toLocaleString()}명</td><td class="n${(x.v.peak_day || 0) >= 95 ? " neg" : ""}">${x.v.peak_day ?? "-"}%</td><td class="n">${x.v.over_parties || ""}</td><td class="n${rr != null && !inBand9011(rr) ? " neg" : ""}">${pctBand(rr)}</td></tr>`; }).join("") + `</table>` +
    (MO ? `<h5>식사 이용이 제한된 경우 최종 결과 (고객팀 · 날짜 · 식사 시간대마다 한 번)</h5><table class="t rt"><tr><th>최종 결과</th><th class="n">건</th><th class="n">비율</th></tr>${Object.entries(MO).map(([k, n]) => `<tr><td>${esc(outName(k))}</td><td class="n">${n}</td><td class="n">${pctS(n, SW.meal_cases)}%</td></tr>`).join("")}</table>` : "") +
    `<h5>공급 제한으로 빠진 후보와 대신 고른 곳</h5><table class="t rt"><tr><th>빠진 후보 (점수가 더 높았던 곳)</th><th>대신 고른 곳</th><th class="n">건</th><th class="n">팀</th></tr>${(D.switches || []).slice(0, 8).map(s => `<tr><td>${esc(s.from)}</td><td>${esc(altName(s.to))}</td><td class="n">${s.events ?? s.n}</td><td class="n">${s.teams ?? "-"}</td></tr>`).join("")}</table>` +
    `<div class="hint">건 = 손님이 후보를 고를 때마다 센 횟수(같은 팀이 여러 번 셀 수 있음), 팀 = 고유 팀. '빠진 후보' 는 고른 곳보다 점수가 높았지만 만석 · 대기로 빠진 곳이고, 자리가 있었으면 반드시 그곳에 갔다는 뜻은 아닙니다.</div>` +
    `<h5>이 숫자를 만든 입력</h5>` + provTable(["좌석 · 회차", "파인다이닝 식사시간", "더뷔페 예약", "피자힐 포장", "손님 처리 순서"]);
  h += sect(3, "어디로 갔나 · 막힌 곳과 대체 행동", p3, d3, `<a class="rlink" data-go="day">지도에서 시간대별로 보기 →</a>`);

  // ── 4. 매출
  const NOT_IN_ONTO = ["와인페어", "와인페어 푸드트럭", "빛의 시어터"];
  const B2 = D.by_l2 || {};
  const l2 = { ROOM: (B2.ROOM || 0) - (D.room_extra_nights || 0), "F&B": B2["F&B"] || 0, LEISURE: (B2["레저"] || 0) - NOT_IN_ONTO.filter(k => l3of(D, k) === "레저").reduce((a, k) => a + ((D.by_l3 || {})[k] || 0), 0) };
  const tot2 = Object.values(l2).reduce((a, b) => a + b, 0) || 1;
  const O = ontoRef(D); const oTot = O && O.l2 ? Object.values(O.l2).reduce((a, b) => a + b, 0) || 1 : 0;
  const l3top = topN(D.by_l3 || {}, 5);
  const p4 = `그날 들어온 손님이 머무는 동안 쓴 돈(순매출)은 ${eok(D.total / 1.1)}${netR ? `이고, 손님 생성의 우연만 바꿔 ${B.seeds}번 돌리면 ${netR.min.toFixed(2)}~${netR.max.toFixed(2)}억 사이에서 움직입니다` : "입니다"}. ` +
    (D.total_day != null ? `이 가운데 그날 일어난 지출은 ${eok(D.total_day / 1.1)}입니다. 전날 들어와 오늘 머무는 손님의 지출은 빠져 있어서, 호텔의 하루 운영 매출과는 다릅니다. ` : "") +
    `객실 : 식음 : 레저 비중은 ${pctS(l2.ROOM, tot2)} : ${pctS(l2["F&B"], tot2)} : ${pctS(l2.LEISURE, tot2)}` + (oTot ? `이고, 온톨로지는 ${pctS(O.l2.ROOM || 0, oTot)} : ${pctS(O.l2["F&B"] || 0, oTot)} : ${pctS(O.l2.LEISURE || 0, oTot)}입니다. ` : "입니다. ") +
    `매출이 큰 곳은 ${l3top.slice(0, 3).map(([n, v]) => `${l3Disp(n)}(${eok(v / 1.1)})`).join(", ")}입니다.`;
  const d4 = `<table class="t rt"><tr><th>L3</th><th class="n">순매출</th><th class="n">비중</th></tr>${topN(D.by_l3 || {}, 10).map(([n, v]) => `<tr><td>${esc(l3Disp(n))}</td><td class="n">${eok(v / 1.1)}</td><td class="n">${pctS(v, D.total)}%</td></tr>`).join("")}</table>` +
    `<div class="hint">매출은 이용 건마다 목적 · 인원 · 아동 동반에 맞는 상품을 메뉴판 정가로 정해 L5 → L1 로 합산합니다. 패키지 포함 식사는 객실 매출입니다.</div>` +
    (S ? `<h5>시드 ${B.seeds}개 범위</h5><table class="t rt"><tr><th>지표</th><th class="n">평균</th><th class="n">범위</th></tr>${Object.entries(S).filter(([n]) => /순매출|이용 \(명\)/.test(n)).slice(0, 8).map(([n, s]) => `<tr><td>${esc(n)}</td><td class="n">${(+s.mean).toFixed(n.includes("억") ? 2 : 0)}</td><td class="n hint">${(+s.min).toFixed(n.includes("억") ? 2 : 0)} ~ ${(+s.max).toFixed(n.includes("억") ? 2 : 0)}</td></tr>`).join("")}</table>` : "");
  const SBR = stayBasis(D);
  h += sect(4, "매출은 어떻게 나왔나", p4 + (SBR ? `<p style="margin-top:8px">${SBR.p}</p>` : ""), d4 + (SBR ? SBR.d : ""), `<a class="rlink" data-go="day">업장별 L4 · L5 내려가 보기 →</a>`);

  // ── 5. 적용된 가설
  const HY = LIB.hypotheses || [];
  const by = s => HY.filter(x => hState(x) === s);
  const byOp = o => HY.filter(x => hOp(x) === o);
  const nm = xs => xs.map(x => `${hLabel(x)} '${esc(hName(x))}'`).join(", ");
  const p5 = (byOp("모델 기본값 반영").length ? `모델 기본값에 반영된 가설은 ${nm(byOp("모델 기본값 반영"))}입니다. ` : "") +
    (byOp("영향 미미").length ? `${byOp("영향 미미").map(hLabel).join(" · ")} 가설은 실험해 보니 결과를 바꾸는 힘이 작아 넣지 않았습니다. ` : "") +
    (byOp("외부 근거 보강 필요").length ? `${byOp("외부 근거 보강 필요").map(hLabel).join(" · ")} 가설은 방향은 보이지만 크기를 정할 공개 근거가 더 필요하고, ` : "") +
    (byOp("현장 확인 필요").length ? `${byOp("현장 확인 필요").map(hLabel).join(" · ")} 가설은 호텔 쪽 운영 조건을 확인해야 판단할 수 있습니다.` : "");
  const d5 = `<table class="t rt"><tr><th>가설</th><th>운영 표시</th><th>다음 확인</th><th>실험 결과</th></tr>${HY.map(x => `<tr><td><b>${hLabel(x)}</b> ${esc(hName(x))}</td><td><span class="hstate ${HSTATE_CLS[hOp(x)] || ""}">${esc(hOp(x))}</span></td><td class="hint">${esc(x["다음 확인"] || "")}</td><td class="hint">${esc((x.상태 || "").slice(0, 200))}</td></tr>`).join("")}</table>` +
    `<div class="hint">실험 결과는 같은 손님으로 조정값만 바꿔 시드 3~10개를 짝지어 비교한 것입니다. 시드만 바꿔도 생기는 흔들림보다 작은 차이는 효과로 보지 않습니다. 근거 문장은 가설표(hypotheses.csv)에 있습니다.</div>`;
  h += sect(5, "어떤 가설이 적용됐나", p5, d5);

  // ── 6. 이런 일이 생기면
  const AN = Object.fromEntries((LIB.anomalies || []).map(a => [String(a.ID), a]));
  const anRows = ANOM.slice().sort((a, b) => a.compare.anomaly - b.compare.anomaly).map(b => {
    const a = AN[String(b.compare.anomaly)] || {}; const E = b.effect || {}; const r = E["순매출 (억)"] || {};
    const mv = Object.entries(E).filter(([n]) => / 이용 \(명\)$/.test(n)).sort((x, y) => Math.abs(y[1].diff) - Math.abs(x[1].diff)).slice(0, 2);
    return { a, b, r, mv, sure: sureEffect(r, b.seeds) };
  });
  const signed = x => `${x > 0 ? "+" : "−"}${Math.abs(Math.round(x))}명`;
  const anLine = x => {
    const d = +x.r.diff, amt = `${Math.abs(d).toFixed(2)}억`;
    const money = !x.sure ? "체류 매출은 우연과 구분될 만큼 바뀌지 않고" : d < 0 ? `체류 매출이 ${amt} 줄고` : `체류 매출이 ${amt} 늘고`;
    // 10/14 — 확실한 이동만 문장에 쓴다 (작은 흔들림을 이동처럼 읽지 않도록)
    const mvS = x.mv.filter(([, e]) => sureEffect(e, x.b.seeds));
    const moves = mvS.length ? `손님은 ${mvS.map(([n, e]) => `${n.replace(" 이용 (명)", "")} ${signed(e.diff)}`).join(", ")}으로 바뀝니다` : "손님이 옮겨 가는 곳은 뚜렷하지 않습니다";
    const t = (x.b.effect || {})["공급 제한 겪은 팀 (팀)"];
    const tm = t && sureEffect(t, x.b.seeds) ? ` 공급 제한을 겪는 팀은 ${t.diff > 0 ? `${Math.round(t.diff)}팀 늘어납니다` : `${Math.round(-t.diff)}팀 줄어듭니다`}.` : "";
    return `<li><b>${esc(x.a.이름 || "")}</b>: ${money}, ${moves}.${tm}</li>`;
  };
  const p6 = anRows.length ? `<ul class="rlist">${anRows.map(anLine).join("")}</ul>` +
    `수요를 늘리는 상황은 저녁 좌석과 회차가 이미 차 있어 매출로 잘 이어지지 않고, 공급을 줄이는 상황은 다른 업장이 다 받아 주지 못해 손실로 남습니다.`
    : `이 날 기준으로 돌려 둔 변칙 상황이 없습니다. 10/10 (토) 기준 예측표는 '상황 비교' 화면에 있습니다.`;
  const d6 = anRows.length ? `<table class="t rt"><tr><th>상황</th><th class="n">체류 매출 (95% 구간)</th><th class="n">공급 제한 겪은 팀</th><th>크기 근거</th><th></th></tr>${anRows.map(x => `<tr><td>${esc(x.a.이름 || "")}</td><td class="n${x.sure ? " b" : ""}">${x.r.diff > 0 ? "+" : ""}${(+x.r.diff).toFixed(2)}억<div class="hint">${(+x.r.lo95).toFixed(2)} ~ ${(+x.r.hi95).toFixed(2)}</div></td><td class="n">${(() => { const t = (x.b.effect || {})["공급 제한 겪은 팀 (팀)"]; return t ? `<span class="${sureEffect(t, x.b.seeds) ? "b" : ""}">${t.diff > 0 ? "+" : ""}${Math.round(t.diff)}팀</span><div class="hint">${Math.round(t.lo95)} ~ ${Math.round(t.hi95)}</div>` : "-"; })()}</td><td>${gradeChip(x.a.등급 || "△")} <span class="hint">${esc(String(x.a["크기 출처 (signal_stats · 문서)"] || "").split(" — ")[0].replace(/한호님 · /g, "").slice(0, 80))}</span></td><td><a class="rlink" data-key="${esc(x.b.compare_key)}">이 상황의 하루 →</a></td></tr>`).join("")}</table>` +
    `<div class="hint">같은 손님 · 같은 시드로 상황만 넣어 ${anRows[0].b.seeds}번씩 짝지어 비교했습니다. 굵은 숫자는 95% 구간이 0을 넘지 않고 거의 매번 같은 방향인 효과입니다. 변화의 크기는 아직 가정(△)이라 방향과 손님이 옮겨 가는 곳을 중심으로 읽습니다.</div>` : "";
  h += sect(6, "이런 일이 생기면", p6, d6, `<a class="rlink" data-go="ask">변칙 상황 더 보기 →</a>`);

  // ── 7. 아직 약한 고리
  const PV = LIB.provenance || [];
  const weak = PV.filter(r => gradeOf(r["등급"]) === "△");
  const W3 = (typeof WEAK !== "undefined" ? WEAK : []).slice(0, 3);
  const p7 = `모델에 들어가는 입력 ${PV.length}개 중 ${weak.length}개는 아직 가정이거나 근거가 약합니다(△). ` +
    (W3.length ? `그중 결과를 가장 크게 움직이는 것은 ${W3.map((w, i) => `${i + 1}) ${w.name}`).join(", ")}입니다. 조식 회차 혼잡은 기상 시각 분포 가정에 민감해서(10/16 민감도 실험 · 이전 모델 v4 · 2부 초과 수요 198~546명 · 검토한 가정 범위), 1순위는 더뷔페 조식 회차별 입장 · 대기 기록으로, 2순위는 만석 때 안내와 손님 행선지 기록으로 확인합니다. ` : "") +
    `숫자를 읽을 때 이 등급을 함께 봐야 합니다.`;
  const d7 = `<table class="t rt"><tr><th>입력</th><th>지금 값</th><th>등급</th><th>출처 · 다음 할 일</th></tr>${weak.map(provRow).join("")}</table>` +
    `<div class="hint">${GRADE_LEGEND.prov}. 운영 수치(좌석 · 회차 · 객실 수)는 호텔 쪽 확인이 오면 그대로 바꿉니다.</div>`;
  h += sect(7, "아직 근거가 약한 곳", p7, d7, `<a class="rlink" data-go="evidence">약한 고리 순위와 필요한 자료 (판단 근거 ⑦) →</a>`);

  // ── 10/17 v2 본문
  let AB = null;
  try {
    const wk = isWeekday(D.date);
    const sig = t => JSON.stringify(Object.entries(t || {}).filter(([k, v]) => !["anomaly", "anomaly_k", "seed", "buffet_seats"].includes(k) && !(!wk && WEEKDAY_ONLY.includes(k)) && v != null && v !== 0 && v !== false).sort());
    AB = (await api("/api/bands")).find(b => b.compare && b.compare.buffet_seats && !b.compare.anomaly && b.date === D.date && b.model_ver === LIB.model_ver && b.input_ver === LIB.input_ver && sig(b.theta) === sig(th)) || null;
  } catch (e) {}
  if (RPT.key !== D.key) return;     // 그 사이 다른 날을 열었으면 그리지 않는다
  const built = esc(String(D.built || "").replace("T", " ").slice(5, 16).replace("-", "/"));
  const kv = (lab, v, u, sub, tip) => `<div class="k"${tip ? ` title="${esc(tip)}"` : ""}><small>${lab}</small><b class="num">${v}<u>${u}</u></b><span>${esc(sub)}</span></div>`;
  let m = `<div class="rv2">${staleNote(D)}<div class="v2top"><div><h1>${dlabel} 운영 요약</h1><div class="sub">시뮬레이션 결과입니다 · <em>실제 호텔 실적이 아님</em> · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${anomaly ? `변동 상황 '${esc(anomaly.이름)}'` : "추가 변동 없음"} · ${weekday ? "평일" : "주말 · 공휴일"}</div></div>` +
    `<div class="v2top-r"><span class="when">계산 ${built}</span><button class="v2asst" id="v2Asst" aria-pressed="false" title="이 결과 기준으로 묻고 답하기"><i>?</i>어시스턴트</button></div></div>`;
  // ① 대표 결과 — 진행 막대는 숫자를 되풀이할 뿐이라 뺐다 (10/17 리뷰 1)
  m += `<section class="v2hero"><div class="hl"><div class="ov">오늘 가장 중요한 결과 · 공급 제약을 겪은 팀</div>` +
    `<div class="line"><span class="big num">${v2Num(swTeams)}<small>팀</small></span>${v2Info("teams", "dark")}<span class="pct num">${swPct}%<small>방문 ${v2Num(G.length)}팀 중</small></span></div>` +
    `<div class="desc">점수가 더 높았던 곳이 만석 · 대기로 빠져 한 번 이상 다른 선택을 한 고유 팀입니다.</div>` +
    `<div class="chips"><span class="chip">시뮬레이션 · 시드 0 한 번</span>${swR ? `<span class="chip">시드 ${B.seeds}개 범위 ${Math.round(swR.min)}~${Math.round(swR.max)}팀</span>` : ""}<button class="chip lnk" data-open="teams">어떤 팀인가 →</button></div></div>` +
    `<div class="kpis">` +
    kv("체류 매출", (D.total / 1.1 / 1e8).toFixed(2), "억", netR ? `VAT 제외 · 시드 ${B.seeds}개 ${netR.min.toFixed(2)}~${netR.max.toFixed(2)}억` : "VAT 제외 · 모델 추정", `그날 들어온 손님이 머무는 동안 쓴 돈 (VAT 제외). VAT 포함 총액 ${(D.total / 1e8).toFixed(2)}억${D.total_day != null ? ` · 그중 그날 지출 ${eok(D.total_day / 1.1)}` : ""}`) +
    kv("방문", v2Num(D.n || G.length), "팀", `${v2Num(persons)}명 · 비투숙 ${v2Num(day.length)}팀`) +
    kv("투숙", v2Num(D.n_guest || guests.length), "팀", "그 날 체크인 · 한 팀 한 객실 가정") +
    kv("좌석 95% 이상", full.length, "곳", "가장 붐빈 회차 기준") + `</div></section>`;
  // 10/17 UX 12차 · 대표 숫자 바로 아래 '오늘 주의할 회차' — 운영자가 아래 표까지 내려가지 않아도 어느 업장 · 몇 시인지 보이게 (누르면 그 업장의 회차별 좌석으로)
  RV2.rows = ((D.switch || {}).by_from || []).slice(0, 5); RV2.focus = 0;
  const alerts = RV2.rows.map((r, i) => { const W = v2Windows(D, r.from); if (!W) return null; const over = W.ws.filter(w => w.over_persons > 0); if (!over.length) return null;
    const w = over.reduce((a, b) => (b.over_persons > a.over_persons ? b : a)); return { i, from: r.from, win: v2WinLabel(W, w), t0: String(w.t0 || "").slice(-5), parties: w.over_parties || 0, persons: w.over_persons || 0, next: /익일/.test(w.name) }; }).filter(Boolean).slice(0, 3);
  if (alerts.length) m += `<section class="v2alert" aria-label="오늘 주의할 회차"><div class="ah"><b>오늘 주의할 회차</b><span class="hint">처음 자리를 못 잡은 팀이 가장 많은 회차 · 누르면 회차별 좌석</span></div><div class="al">` +
    alerts.map(a => `<button class="ai" data-rk="${a.i}" data-alert="1"><span class="r">${a.i + 1}</span><span class="t"><b>${vdot(a.from)}${esc(nmDisp(a.from))}</b><span>${a.next ? "다음날 " : ""}${esc(a.win)} ${esc(a.t0)}</span></span><span class="v"><b class="num">${v2Num(a.parties)}팀</b><span>${v2Num(a.persons)}명 · 처음 막힘</span></span></button>`).join("") + `</div></section>`;
  // ② 어디에서 막혔나 — 순위(고유 팀) + 막힌 식사의 행방(건) | 고른 곳의 회차별 좌석(명 · 회차마다)
  const mxT = Math.max(1, ...RV2.rows.map(r => r.teams));
  m += `<section class="v2s"><div class="sh"><h2>어디에서 제약이 생겼나</h2><span class="s">고유 팀이 많은 순 · 시드 0 · 줄을 누르면 오른쪽 회차가 바뀝니다</span><a class="act" data-sec="3">업장 · 시간대 혼잡 자세히</a></div>` +
    `<div class="grid2"><div class="pane">` + (RV2.rows.length ?
      `<div class="rkh"><span></span><span>막힌 곳</span><span></span><span class="n">고유 팀 ${v2Info("rowteams")}</span><span>처음 막힌 회차 · 팀 · 명 ${v2Info("over")}</span></div>` +
      RV2.rows.map((r, i) => `<button class="rk${i === 0 ? " lead sel" : ""}" data-rk="${i}" aria-pressed="${i === 0}"><span class="r">${i + 1}</span><span class="nm">${vdot(r.from)}${esc(nmDisp(r.from))}</span><span class="tr"><i style="width:${(r.teams / mxT * 100).toFixed(1)}%"></i></span><span class="v num">${v2Num(r.teams)}팀</span><span class="why">${esc(v2Why(D, r.from))}</span></button>`).join("") +
      capN("고유 팀 · 한 팀이 여러 곳에 셀 수 있음", `팀 = 그곳에서 한 번 이상 자리를 못 잡은 고유 팀. 한 팀이 여러 곳에 셀 수 있어 합이 ${v2Num(swTeams)}팀보다 큽니다. 오른쪽 칸은 그 회차에서 처음 막힌 팀과 그 일행 수라 왼쪽 고유 팀 수와 범위가 다릅니다.`)
      : `<div class="hint">공급 제약이 생긴 곳이 없습니다.</div>`) +
    v2Flow(D) + `</div><div class="pane focus" id="v2Focus">${v2Focus(D, 0)}</div></div></section>`;
  // ③ 상황 실험 | 더 볼 곳
  RV2.exp = v2ExpRows(D, ANOM, AB);
  const ops = RV2.items.filter(x => x.cls !== "model"), mdl = RV2.items.find(x => x.cls === "model");
  const nav = (k, t, s) => `<a data-open="${k}">${t}<span>${esc(s)}</span></a>`;
  const q = id => { const x = (typeof AQ !== "undefined" ? AQ : []).find(y => y.id === id && (y.page === "report" || y.page === "*")); return x ? `<a data-ask="${id}">${esc(typeof x.q === "function" ? x.q("") : x.q)}</a>` : ""; };
  m += `<section class="v2s"><div class="grid2 gx"><div><div class="sh"><h2>상황 실험</h2><span class="s">오늘 결과와 별도 계산 · 시드 쌍 평균</span><a class="act" data-go="ask">상황 비교에서 조건 바꿔 보기</a></div><div class="pane exp">${v2ExpHtml(RV2.exp)}</div></div>` +
    `<div><div class="sh"><h2>더 볼 곳</h2><span class="s">누르면 넓은 상세 패널</span></div><div class="pane"><div class="nav">` +
    `<div class="ng"><h4>고객</h4>${nav("sec:1", "누가 왔나", "목적 · 아이 동반 · 투숙")}${nav("teams", "제약을 겪은 팀의 구성", `${v2Num(swTeams)}팀`)}${nav("sec:2", "무엇을 원했나", "선호 · 선택 조건")}</div>` +
    `<div class="ng"><h4>시설 · 혼잡</h4>${nav("sec:3", "업장별 이용 · 대체 행동", `${V.length}곳`)}${nav("flow", "막힌 식사의 행방", `${v2Num((D.switch || {}).meal_cases || 0)}건`)}<a data-go="day">지도에서 시간대별로 보기<span>고객 흐름</span></a></div>` +
    `<div class="ng"><h4>매출</h4>${nav("sec:4", "매출 구성 · 시드 범위", eok(D.total / 1.1))}${nav("lead", "이 날 전체를 문장으로", "요약 문단")}</div>` +
    `<div class="ng"><h4>근거 · 가정</h4>${ops.length ? nav("issues", "오늘 확인할 운영 이슈", `${ops.length}건 · 검토안`) : ""}${nav("sec:7", "결과를 크게 움직이는 가정", `△ ${weak.length}개`)}${nav("sec:5", "적용된 가설", `${HY.length}개`)}${mdl ? nav("issue:" + RV2.items.indexOf(mdl), "모델 확인 사항", mdl.t.replace(/ 이용이 온톨로지의 /, " ")) : ""}</div>` +
    `</div><div class="ask"><h4>어시스턴트에게 묻기 · 이 결과 기준</h4>${q(topFrom && /더뷔페 조식/.test(topFrom.from) ? "bf" : "busy")}${q("flow")}${q(AB ? "ab" : "closed")}</div></div></div></div></section>`;
  m += `<div class="rfoot hint">시뮬레이션 결과 · 실제 호텔 실적이 아님${noteI("이 화면의 숫자는 시뮬레이션 계산 결과와 장부(가설표 · 입력 출처표)에서 자동으로 만든 것이며 실제 호텔 실적이 아닙니다.")}</div></div>`;
  el.innerHTML = m;
  if (RV2._k !== D.key) { const mr = document.querySelector("main.report"); if (mr) mr.scrollTop = 0; RV2._k = D.key; }
  v2Wire(el);
  $("#v2Asst").onclick = () => v2Assist();
  const bs = $("#rBasis"); if (bs) bs.innerHTML = `<b>지금 보고 있는 결과</b><span>시드 0 한 번 계산</span><span>${esc(knobSummary(D))}</span><span>모델 ${esc(D.model_ver || "-")} · 입력 ${esc(D.input_ver || "-")}</span><span>계산 ${built}</span>`;
  if (RPT.key === D.key) assistSet({ page: "report", D, FL, ANOM, AB }, "rAssist");
}

function kpi(label, big, sub, tip, cls) { return `<div class="rkpi ${cls || ""}"${tip ? ` title="${esc(tip)}"` : ""}><small>${label}</small><span class="big">${big}</span><span class="sub">${esc(sub)}</span></div>`; }
function miniBars(o, tot) {
  return topN(o, 6).map(([k, n]) => `<div class="mbar"><span>${esc(k)}</span><i><b style="width:${pctS(n, tot)}%"></b></i><em>${pctS(n, tot)}%</em></div>`).join("");
}
function reportDayOptions(D) {
  // 요약에서 고를 수 있는 날 — v4(지금 기본) 날과 이 날의 변칙 상황, 그리고 지금 보는 날
  const L = (refreshDays.list || []).filter(d => d.scale === 1 && !(d.theta || {}).seed && d.scenario === "none");
  const v4 = L.filter(d => { const t = Object.assign({}, d.theta || {}); delete t.anomaly; return isV4Theta(t, d.date) && Object.keys(t).every(k => k in PRE.full); });
  const seen = new Set(); const opts = [];
  for (const d of [D, ...v4.sort((a, b) => a.date.localeCompare(b.date) || ((a.theta || {}).anomaly || 0) - ((b.theta || {}).anomaly || 0))]) {
    if (!d || seen.has(d.key)) continue; seen.add(d.key);
    opts.push(`<option value="${esc(d.key)}"${d.key === D.key ? " selected" : ""}>${esc(dayLabel(d.key))}</option>`);
  }
  return opts.join("");
}

// ───────────────────────────────────────────────────────────────────────────
// 왼쪽 — 무엇을 돌려 볼지 고르는 자리 (하루 전체 / 손님 한 팀 · 날짜 · 변동 상황 · 손님 설정)
// 기본 모델은 '온톨로지 정합 v4'. 다른 조정값은 '모델 설정' 에서
// ───────────────────────────────────────────────────────────────────────────
function reportShell() {
  const root = $("#reportView");
  if (root.querySelector(".rlayout")) return;
  const opt = (v, t, sel) => `<option value="${esc(v)}"${sel ? " selected" : ""}>${esc(t)}</option>`;
  const dates = (LIB.dates || []).map(d => opt(d.date, `${d.date.slice(5).replace("-", "/")} (${d.dow})${d.fair ? " · 와인페어 기간" : ""}`, d.date === "2026-10-10")).join("");
  const anoms = opt("", "추가 변동 없음", true) + (LIB.anomalies || []).map(a => opt(a.ID, a.이름)).join("");
  const purposes = (LIB.purposes || []).map(p => opt(p, p, p === "가족·친족")).join("");
  const ages = (LIB.ages || []).map(a => opt(a, a, /30/.test(a))).join("");
  const reviews = opt("", "직접 설정") + (LIB.review_list || []).map((r, i) => opt(i, `${r.blog}${r.alt ? " (둘째 체류)" : ""} · ${r.is_guest ? `투숙 ${r.nights}박` : "비투숙"} · ${r.party}인${r.kids ? " · 아이" : ""} · ${r.purpose || ""}`)).join("");
  // 10/17 v2 — 어시스턴트는 기본으로 접어 두고 제목 줄 버튼으로 연다. 왼쪽은 날짜 · 행사 · 변동 상황 · 실행 · 지금 보는 결과만
  root.innerHTML = `<div class="rlayout as-closed"><aside class="rleft">
    <div class="rseg" id="rView"><button data-v="day" class="on">하루 전체</button><button data-v="guest">손님 한 팀</button></div>
    <div class="rl-h">계산할 하루</div>
    <label>날짜<select id="rDate">${dates}</select></label>
    <label class="rl-scen">행사<select id="rScen">${opt("none", "행사 없음", true)}${opt("winefair", "와인페어 있음 (외부 손님 · 입장권 · 푸드트럭)")}</select></label>
    <label>변동 상황<select id="rAnom">${anoms}</select></label>
    <div id="rAnomDesc" class="hint"></div>
    <div class="rl-day">
      <button id="rRunDay" class="rbtn">이 조건으로 계산</button>
    </div>
    <div class="rl-guest hidden">
      <label>후기에서 온 손님<select id="rReview">${reviews}</select></label>
      <div class="rseg small" id="rGuestType"><button data-v="1" class="on">투숙</button><button data-v="0">비투숙</button></div>
      <label>방문 목적<select id="rPurpose">${purposes}</select></label>
      <div class="rrow"><label>연령<select id="rAge">${ages}</select></label><label>인원<select id="rParty">${[1, 2, 3, 4, 5, 6].map(n => opt(n, n + "명", n === 3)).join("")}</select></label></div>
      <label class="check"><input type="checkbox" id="rKids" checked> 13세 미만 아이와 함께</label>
      <div class="rrow r-stay"><label>건물<select id="rProp">${opt("GRAND", "그랜드", true)}${opt("VISTA", "비스타")}${opt("DOUGLAS", "더글라스")}</select></label><label>박 수<select id="rNights">${opt(1, "1박", true)}${opt(2, "2박")}</select></label></div>
      <label>도착 시각<select id="rArrive">${opt("11:00", "11:00")}${opt("15:00", "15:00", true)}${opt("17:00", "17:00")}</select></label>
      <label class="check"><input type="checkbox" id="rCrowd" checked> 그날 다른 손님들과 함께 (자리 경쟁 반영)</label>
      <button id="rRunGuest" class="rbtn">이 손님 따라가 보기</button>
    </div>
    <div id="rStatus" class="hint"></div>
    <div class="rbasis rl-day" id="rBasis"></div>
    <div class="hint rnote">기본 모델은 '${V4_LABEL()}'입니다. 다른 조정값 · 가설 실험은 '모델 설정'에서 바꿔 볼 수 있습니다.</div>
  </aside><div class="rmain"></div><aside class="rassist" id="rAssist"></aside><button class="as-open" id="asOpen">운영 어시스턴트</button></div>`;
  $("#asOpen").onclick = () => { const L = $(".rlayout"); L.classList.remove("as-closed"); L.classList.add("as-show"); };
  $$("#rView button").forEach(b => b.onclick = () => { RPT.view = b.dataset.v; syncReportLeft(); renderReport(); });
  $$("#rGuestType button").forEach(b => b.onclick = () => { $$("#rGuestType button").forEach(x => x.classList.toggle("on", x === b)); syncReportLeft(); });
  $("#rAnom").onchange = syncReportLeft;
  $("#rReview").onchange = fillFromReview;
  $("#rRunDay").onclick = runReportDay;
  $("#rRunGuest").onclick = runReportGuest;
}
function syncReportLeft() {
  if (!$("#rView")) return;
  $$("#rView button").forEach(b => b.classList.toggle("on", b.dataset.v === RPT.view));
  $$(".rl-day, .rl-scen").forEach(e => e.classList.toggle("hidden", RPT.view !== "day"));
  $(".rl-guest").classList.toggle("hidden", RPT.view !== "guest");
  const stay = $("#rGuestType .on").dataset.v === "1";
  $(".r-stay").classList.toggle("hidden", !stay);
  const a = (LIB.anomalies || []).find(x => String(x.ID) === $("#rAnom").value);
  $("#rAnomDesc").innerHTML = a ? `${esc(String(a.설명 || "").split(/ — |\. /)[0])} <span class="gchip g2" title="크기는 가정">${esc(gradeOf(a.등급) || "△")}</span>` : "추가 변동 없이 계산한 하루입니다.";
  if (RPT.view === "day" && DAY && !RPT._synced) {    // 처음 한 번 — 지금 보는 날을 왼쪽에 맞춘다
    $("#rDate").value = DAY.date; $("#rAnom").value = (DAY.theta || {}).anomaly ? String(DAY.theta.anomaly) : ""; $("#rScen").value = DAY.scenario || "none";
    RPT._synced = true; syncReportLeft();
  }
}
function fillFromReview() {
  const r = (LIB.review_list || [])[+$("#rReview").value];
  if (!r) return;
  $$("#rGuestType button").forEach(x => x.classList.toggle("on", x.dataset.v === (r.is_guest ? "1" : "0")));
  if (r.purpose && [...$("#rPurpose").options].some(o => o.value === r.purpose)) $("#rPurpose").value = r.purpose;
  $("#rParty").value = String(Math.min(6, Math.max(1, r.party || 2)));
  $("#rKids").checked = !!r.kids;
  if (r.property) $("#rProp").value = r.property;
  if (r.nights) $("#rNights").value = String(Math.min(2, r.nights));
  syncReportLeft();
}
function reportTheta() {
  const date = $("#rDate").value, th = v4For(date), a = $("#rAnom").value;
  if (a) th.anomaly = +a;
  return th;
}
async function ensureReportDay(onProgress) {
  // 고른 날짜 · 행사 · 변동 상황의 v4 하루를 찾고, 없으면 돌린다 (40초 안팎)
  const cfg = { date: $("#rDate").value, scenario: RPT.view === "day" ? $("#rScen").value : "none", scale: 1, theta: reportTheta() };
  const r = await api("/api/day", cfg);
  if (r.status === "done") return r.key;
  const t0 = Date.now(); let none = 0;
  for (;;) {
    await new Promise(res => setTimeout(res, 1000));
    const s = await api("/api/day/status?key=" + encodeURIComponent(r.key));
    if (s.status === "done") { await refreshDays(); return r.key; }
    if (s.status === "error") throw new Error((s.error && s.error !== "계산 실패" ? s.error : "계산이 결과 파일을 남기지 못했습니다") + " · 화면 서버(app.py)를 껐다 켠 뒤 다시 눌러 주세요");
    if (s.status === "lost") throw new Error("계산 중에 화면 서버가 다시 켜져 끊겼습니다. 다시 눌러 주세요");
    if (s.status === "none" && ++none > 8) throw new Error("계산이 시작되지 않았습니다. 화면 서버(app.py)를 껐다 켠 뒤 다시 눌러 주세요");
    s.elapsed = Math.round((Date.now() - t0) / 1000);
    onProgress && onProgress(s);
  }
}
async function runReportDay() {
  if (RPT.busy) return; RPT.busy = true;
  const st = $("#rStatus"); st.textContent = "계산해 둔 결과를 찾는 중…";
  try {
    const key = await ensureReportDay(s => st.textContent = `하루를 돌리는 중… ${s.total ? (s.done >= s.total ? "결과 정리 중" : `${s.done}/${s.total}팀`) : "손님 만드는 중"} · ${s.elapsed}초 지남 (보통 3~5분)`);
    st.textContent = ""; RPT.view = "day"; await loadDay(key);
  } catch (e) { st.textContent = "실패: " + e.message; }
  RPT.busy = false;
}
async function runReportGuest() {
  if (RPT.busy) return; RPT.busy = true;
  const st = $("#rStatus");
  try {
    let crowd = "";
    if ($("#rCrowd").checked) {
      st.textContent = "그날 다른 손님들의 결과를 찾는 중…";
      crowd = await ensureReportDay(s => st.textContent = `그날 하루를 먼저 돌리는 중… ${s.total ? `${s.done}/${s.total}팀` : ""}`);
    }
    st.textContent = "이 손님을 돌리는 중…";
    const stay = $("#rGuestType .on").dataset.v === "1";
    const cfg = { date: $("#rDate").value, scenario: "none", crowd, anomaly: $("#rAnom").value || null,
      is_guest: stay, property: $("#rProp").value, nights: stay ? +$("#rNights").value : 0, party: +$("#rParty").value,
      kids: $("#rKids").checked && +$("#rParty").value >= 2, sex: (LIB.sexes || ["여성"])[0], age: $("#rAge").value, purpose: $("#rPurpose").value,
      package: "auto", prefers: "auto", wf_go: false, arrive: $("#rArrive").value, depart: "22:00", wake: "07:30", arrival: "", seed: 7 };
    const res = await api("/api/guest", cfg);
    res._cfg = cfg; res._crowd = crowd;
    if (crowd) await ensureDay(crowd);
    RPT.guest = res; RPT.view = "guest"; st.textContent = "";
    renderReport();
  } catch (e) { st.textContent = "실패: " + e.message; }
  RPT.busy = false;
}

// ───────────────────────────────────────────────────────────────────────────
// 손님 한 팀 요약 — 이 손님이 누구이고, 무엇을 원했고, 어디가 막혀 어떻게 바꿨는지. 점수와 이유는 에이전트가 실제로 계산한 값
// ───────────────────────────────────────────────────────────────────────────
const hm = t => String(t || "").slice(11, 16);
const dayOf = (t, t0) => (String(t).slice(0, 10) !== String(t0).slice(0, 10) ? "다음날 " : "");
function renderGuestSummary(el) {
  const R = RPT.guest;
  if (!R) { el.innerHTML = `<div class="rwrap"><div class="empty">왼쪽에서 손님을 고르고 <b>이 손님 따라가 보기</b>를 누르세요.<br>후기에서 온 손님을 불러오거나, 목적 · 인원 · 아이 동반을 직접 정할 수 있습니다.</div></div>`; return; }
  const P = R.persona || {}, S = R.steps || [], cfg = R._cfg || {};
  const t0 = S.length ? S[0].t_in : P.start;
  const pref = (P.prefers || []).map(locName);
  const who = `${P.is_guest ? `${P.prop_name || locName(P.property)}에 ${P.nights}박하는` : "투숙하지 않고 하루 들른"} ${P.age || ""} ${P.purpose || ""} 손님 ${P.party}명${P.kids ? "(아이 동반)" : ""}`;
  const key = S.filter(s => ["meal", "facility", "event"].includes(s.kind) || (s.switch && s.switch.원래) || /식사/.test(s.label));
  const sws = S.filter(s => s.switch && s.switch.원래);
  const meals = S.filter(s => s.kind === "meal" || /식사/.test(s.label));
  const an = R.anomaly;
  const lastT = S.length ? S[S.length - 1].t_out : t0;
  const hours = Math.round((new Date(lastT) - new Date(t0)) / 36e5);

  let h = `<div class="rwrap"><div class="rhead"><div><div class="rtitle">손님 한 팀 따라가 보기</div><div class="rsub">${esc(cfg.date ? cfg.date.slice(5).replace("-", "/") : "")} · ${an ? `변동 상황: ${esc(an.name)}` : "추가 변동 없음"} · ${R._crowd ? "그날 다른 손님들과 함께" : "이 손님 혼자 (자리 경쟁 없음)"} · 온톨로지 정합 v4</div></div></div>`;
  h += `<div class="rkpis">` + kpi("머문 시간", `${hours}시간`, `${hm(t0)} 도착 · ${dayOf(lastT, t0)}${hm(lastT)} 마지막 행동`) +
    kpi("들른 곳", `${key.length}곳`, `식사 ${meals.length}번`) +
    kpi("공급 제한으로 빠진 후보", `${sws.length}번`, sws.length ? sws.map(s => s.switch.사유).filter((v, i, a) => a.indexOf(v) === i).join(" · ") : "없음") +
    kpi("쓴 돈", `${Math.round((R.spend_total || 0) / 1e4).toLocaleString()}만 원`, `객실 ${Math.round((R.spend_by_l2 || {}).ROOM / 1e4 || 0)}만 · 식음 ${Math.round((R.spend_by_l2 || {})["F&B"] / 1e4 || 0)}만 원`) + `</div>`;

  // 결론 문단
  let lead = `${esc(who)}입니다. ` + (pref.length ? `이 손님이 가장 가고 싶어 한 식당은 ${pref.map(esc).join(" · ")}입니다. ` : "") +
    (P.package ? `객실 상품은 '${esc(P.package)}'${(P.included || []).length ? `이고 식사 포함 혜택이 있습니다` : "입니다"}. ` : "");
  const closed = an ? (an.applied || []).filter(x => /닫음$/.test(x)).map(x => x.replace(/\s*닫음$/, "")) : [];
  const hitClosed = pref.filter(p => closed.some(c => p.startsWith(c) || c.startsWith(p)));
  if (hitClosed.length) {
    const dinner = meals.find(m => +hm(m.t_in).slice(0, 2) >= 17 && !dayOf(m.t_in, t0));
    lead += `가장 가고 싶어 한 ${josa(esc(hitClosed[0]), "이/가")} 이날 문을 닫아 다른 곳에서 식사했습니다${dinner ? `(저녁: ${esc(dinner.label)})` : ""}. `;
  }
  if (sws.length) {
    const f = sws.slice().sort((a, b) => (+b.switch.원래_점수) - (+a.switch.원래_점수))[0].switch;   // 가장 원했던(점수가 높았던) 곳이 막힌 경우부터
    lead += `${dayOf(f.시각, t0)}${hm(f.시각)}에는 점수가 가장 높았던 ${josa(esc(f.원래), "이/가")} ${f.사유 === "만석" ? "만석이라" : esc(f.사유) + "라"} 빠지고 ${josa(esc(altName(f.대체)), "을/를")} 골랐습니다. `;
    if (sws.length > 1) lead += `이렇게 공급 제한으로 더 높은 점수의 후보가 빠진 일이 하루에 ${sws.length}번 있었습니다. `;
  } else lead += `공급 제한으로 빠진 후보 없이, 점수에 따라 고른 곳에 모두 들어갔습니다. `;
  if (an) lead += `<b>'${esc(an.name)}' 상황</b>(${esc((an.applied || []).join(" · "))})을 넣어 돌린 결과입니다.`;
  h += `<div class="rlead">${lead}</div>`;

  // 1. 동선
  const line = s => {
    const sw = s.switch && s.switch.원래 ? ` <span class="rsw">${esc(s.switch.원래)} ${esc(josa(s.switch.사유 || "", "으로/로"))} 빠짐 → </span>` : "";
    return `<li><span class="rt">${dayOf(s.t_in, t0)}${hm(s.t_in)}</span>${sw} <b>${esc(s.label)}</b>${s.wait > 0 ? ` <span class="hint">대기 ${Math.round(s.wait)}분</span>` : ""}</li>`;
  };
  const p1 = `<ul class="rtimeline">${key.map(line).join("")}</ul>`;
  const d1 = `<table class="t rt"><tr><th>시각</th><th>행동</th><th>고른 이유 (점수)</th><th>다른 후보</th></tr>${S.map(s => `<tr><td class="n">${dayOf(s.t_in, t0)}${hm(s.t_in)}</td><td>${esc(s.label)}</td><td>${(s.why || []).map(esc).join("<br>")}<div class="hint">합계 ${(+s.pts).toFixed(2)} · 후보 ${s.feasible}곳 중 ${s.rank}위</div></td><td class="hint">${(s.alts || []).filter(a => a.label !== s.label).slice(0, 3).map(a => `${esc(a.label)} ${(+a.pts).toFixed(1)}`).join("<br>")}</td></tr>`).join("")}</table>`;
  h += sect(1, "하루 동선", p1, d1, `<a class="rlink" id="rToMap">지도에서 이 손님 움직임 보기 →</a>`);

  // 2. 왜 그렇게 움직였나
  const p2 = sws.length ? sws.map(s => {
    const f = s.switch;
    return `${dayOf(f.시각, t0)}${hm(f.시각)}, 점수가 더 높았던 ${josa(esc(f.원래), "이/가")} ${f.사유 === "만석" ? "만석이라" : esc(f.사유) + "라"} 빠지고 ${josa(esc(altName(f.대체)), "을/를")} 골랐습니다(점수 ${(+f.원래_점수).toFixed(1)} → ${(+f.대체_점수).toFixed(1)}). 대신 고른 곳의 점수에 작용한 요인은 '${(s.why || []).map(w => esc(w.replace(/\s[+-−]?[\d.]+$/, ""))).join("', '")}'입니다.`;
  }).join(" ") : `원하던 곳이 막힌 일이 없었습니다.`;
  const FS = factorSummary(S).filter(x => !/정해진 일정/.test(x[0]));
  const TR = traitRows(R.persona), trOn = TR.filter(t => t.cls === "part" || t.cls === "on"), trOff = TR.filter(t => t.cls === "off");
  const p2b = (FS.length ? ` 하루 전체로 보면 선택에 가장 크게 작용한 요인은 ${FS.slice(0, 3).map(x => `${esc(x[0])}(${x[1] > 0 ? "+" : ""}${x[1].toFixed(1)})`).join(", ")}입니다.` : "") +
    (trOff.length ? ` 후기에서 뽑은 이 손님의 성향 ${trOff.map(t => `'${esc(t.k)}'`).join(", ")}는 지금 모델의 점수에 들어가지 않습니다${trOn.length ? `('${esc(trOn[0].k)}'만 포장을 고를 때 작용)` : ""}.` :
      (TR.every(t => t.cls === "none") ? ` 이 손님은 성향 값이 없어 조건과 목적별 선호만으로 움직였습니다.` : ""));
  const rej = {};
  S.forEach(s => (s.rejected || []).forEach(x => { const [n, why] = String(x).split(": "); if (/만석|닫|휴업|운영/.test(why || "")) rej[n] = why; }));
  const d2 = `<h5>이 손님이 고려했지만 갈 수 없었던 곳</h5><table class="t rt"><tr><th>곳</th><th>이유</th></tr>${Object.entries(rej).slice(0, 12).map(([n, w]) => `<tr><td>${esc(n)}</td><td>${esc(w)}</td></tr>`).join("")}</table>` +
    `<div class="hint">점수는 후기 46편으로 교차검증해 정한 계수(에이전트 v4)로 계산합니다. 같은 조건이면 점수가 높은 쪽을 고를 확률이 높고, 반드시 1위를 고르지는 않습니다.</div>` +
    `<h5>이 손님의 성향을 만든 입력</h5>` + provTable(["가고 싶은 식당", "식당 가고 싶음 비율", "AI 유형 섞기", "행동 점수 계수"]);
  h += sect(2, "왜 그렇게 움직였나", p2 + p2b, `<h5>선택에 작용한 요인 (고른 행동의 점수 사유를 요인별로 더함)</h5>${factorTable(S)}<h5>성향 (후기에서 추출)</h5>${traitTable(R.persona)}<div class="hint">${traitNote()}</div>` + d2);

  // 3. 쓴 돈
  const L = R.spend_by_l2 || {};
  const p3 = `이 손님이 쓴 돈은 모두 ${Math.round((R.spend_total || 0) / 1e4).toLocaleString()}만 원(${R.n_lines || 0}건)이고, 객실 ${Math.round((L.ROOM || 0) / 1e4)}만 원 · 식음 ${Math.round((L["F&B"] || 0) / 1e4)}만 원 · 레저 ${Math.round((L["레저"] || 0) / 1e4)}만 원입니다. 상품은 목적 · 인원 · 아이 동반에 맞춰 메뉴판 정가로 정했습니다.`;
  const sp = S.flatMap(s => (Array.isArray(s.spend) ? s.spend : []).filter(x => x.krw > 0).map(x => ({ s, x })));
  const d3 = sp.length ? `<table class="t rt"><tr><th>시각</th><th>곳</th><th>상품</th><th class="n">금액</th><th>등급</th></tr>${sp.map(({ s, x }) => `<tr><td>${dayOf(s.t_in, t0)}${hm(s.t_in)}</td><td>${esc(x.l3 || s.label)}</td><td>${esc(x.product)}${x.qty > 1 ? ` × ${x.qty}` : ""}${x.note ? `<div class="hint">${esc(x.note)}</div>` : ""}</td><td class="n">${Math.round(x.krw).toLocaleString()}원</td><td class="c">${gradeChip(x.grade)}</td></tr>`).join("")}</table>` : "";
  h += sect(3, "얼마를 썼나", p3, d3);

  // 4. 그날 상황
  const p4 = (R._crowd ? `이 손님은 그날 다른 손님들이 이미 잡은 좌석 위에 들어가서, 붐비는 회차에는 자리를 못 잡을 수 있습니다. ` : `이 손님 혼자 돌렸기 때문에 자리 경쟁은 없습니다. `) +
    (an ? `변동 상황 '${esc(an.name)}'을 넣었습니다(설정: ${esc(String(an.desc || "").split(/ — |\. /)[0].replace(/다\.?$/, "다"))}). 이 상황의 크기는 아직 ${esc(String(an.src || "가정").split(" — ")[0])}이라 등급 ${esc(an.grade || "△")}입니다.` : `추가 변동 없이 계산한 하루입니다.`);
  h += sect(4, "그날 상황", p4, "", R._crowd ? `<a class="rlink" id="rToDay">이 날 하루 전체 요약 보기 →</a>` : "");
  h += `<div class="rfoot hint">이 요약은 에이전트가 실제로 계산한 점수와 선택 기록에서 만든 문장입니다.</div></div>`;
  el.innerHTML = h;
  const m = $("#rToMap"); if (m) m.onclick = () => { setMode("guest"); showGuest(R); };
  const dd = $("#rToDay"); if (dd) dd.onclick = () => { RPT.view = "day"; loadDay(R._crowd); };
  el.querySelectorAll(".rlink[data-go]").forEach(a => a.onclick = () => setMode(a.dataset.go));
}
