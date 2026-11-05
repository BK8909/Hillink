// 10/16 상황 비교 개편 — ① 상황 선택 → ② 호텔 전체 변화 → ③ 업장 선택 → ④ 업장의 변화 · 시간 · 고객 · 검토 → ⑤ 파급 · 상세 A/B
// 저장된 시드 묶음을 우선 사용하고, 없는 상황은 선택한 날짜·조건으로 시드 0의 A/B를 계산한다.
// 업장을 바꿔도 다시 돌리지 않는다. 오른쪽은 운영 요약과 같은 '힐링크 운영 어시스턴트' (assist.js) 를 이 화면의 맥락으로 쓴다.
const ASK = { scn: null, venue: null, open: false, cur: null, render: 0, job: null, error: null };
const VEN_M = {
  THE_BUFFET: [["더뷔페 이용 (명)", "중식 · 석식 · 다음날 중식 이용", " 인 · 회"], ["더뷔페 다음날 조식 이용 (명)", "다음날 조식 이용", " 인 · 회"], ["더뷔페 초과 수요 (명)", "초과 수요 (막힌 팀의 일행 수)", "명"], ["더뷔페 비투숙 팀 (팀)", "비투숙 팀", "팀"]],
  PIZZA_HILL: [["피자힐 홀 이용 (명)", "홀 이용", " 인 · 회"], ["피자힐 홀 초과 수요 (명)", "홀 초과 수요 (막힌 팀의 일행 수)", "명"], ["피자힐 포장 (판)", "포장", "판"], ["피자힐 비투숙 팀 (팀)", "비투숙 팀", "팀"]],
  GEUMRYONG: [["금룡 이용 (명)", "이용", " 인 · 회"], ["금룡 초과 수요 (명)", "초과 수요 (막힌 팀의 일행 수)", "명"]],
  MYONGWOLGWAN: [["명월관 이용 (명)", "이용", " 인 · 회"], ["명월관 초과 수요 (명)", "초과 수요 (막힌 팀의 일행 수)", "명"]],
  ONDAL: [["온달 이용 (명)", "이용", " 인 · 회"], ["온달 초과 수요 (명)", "초과 수요 (막힌 팀의 일행 수)", "명"]],
  MOEGI: [["모에기 이용 (명)", "이용", " 인 · 회"], ["모에기 초과 수요 (명)", "초과 수요 (막힌 팀의 일행 수)", "명"]],
  LUX_BAR: [["럭스바 (잔)", "판매", "잔"]],
  LE_PASSAGE: [["르파사쥬 (건)", "구매", "건"]],   // 첫 칸은 짝 비교 지표 키(서버 이름)라 그대로 둔다
};
const QUICK_V = ["THE_BUFFET", "PIZZA_HILL", "MYONGWOLGWAN", "GEUMRYONG", "ONDAL", "MOEGI", "THE_PAVILION", "LE_PASSAGE", "LUX_BAR"];
const VEN_NEED = {
  THE_BUFFET: "회차별 실제 입장 · 대기 · 포기 기록",   // 10/19 소연 ③-13 — 테라스 문구는 좌석 338석 상황에서만 (venNeed)
  PIZZA_HILL: "시간대별 포장 처리 능력, 홀 대기 · 이탈 기록",
  GEUMRYONG: "별실 · 단체 예약 비중 (모델이 별실을 따로 다루지 않음)",
  MYONGWOLGWAN: "별실 · 단체 예약 비중 (모델이 별실을 따로 다루지 않음)",
  ONDAL: "회차별 이용 인원 · 예약 비중",
  MOEGI: "식사별 예약 · 좌석 구성",
};
// 10/19 소연 ③-13 — 필요한 현장 자료는 고른 상황을 따른다. 테라스 사용 여부는 더뷔페 좌석을 늘린 상황에서만 묻는다
const venNeed = (loc, sc) => (VEN_NEED[loc] || "회차 · 시간대별 실제 이용 인원") + (sc && sc.kind === "seat" && loc === "THE_BUFFET" ? ", 테라스를 식사에 쓸 수 있는지(연회 · 인력 · 동선)" : "");
// 10/17 QA Q4 — 반올림해서 0 이 되면 '−0' 이 아니라 '0' 으로
const fmtD = (v, d = 0) => { let s = (+v).toFixed(d); if (/^-0(\.0+)?$/.test(s)) s = s.slice(1); return `${+s > 0 ? "+" : ""}${s}`.replace(/^-/, "−"); };   // 10/17 · 화면 표기는 진짜 빼기 기호
const shortName = loc => locName(loc).split(" (")[0];

// 계산과 비교 조회에서 같은 조건을 쓴다. 0도 기본값과 다르면 의미 있는 입력이다.
function askThetaSig(date, theta) {
  const wk = isWeekday(date), defaults = LIB.knobs || {};
  return JSON.stringify(Object.entries(theta || {}).filter(([k, v]) =>
    !(k === "seed" && !v) && !(!wk && WEEKDAY_ONLY.includes(k)) && v != null &&
    (!defaults[k] || v !== defaults[k].default)).sort(([a], [b]) => a.localeCompare(b)));
}
function askPairSpec(D, sc) {
  const base = Object.assign({}, D.theta || {});
  delete base.seed; delete base.anomaly; delete base.anomaly_k;
  const comp = Object.assign({}, base);
  if (sc.kind === "seat") comp.buffet_seats = 338;
  if (sc.kind === "anom") {
    comp.anomaly = +sc.a.ID;
    const strength = (D.theta || {}).anomaly_k;
    if (strength != null && strength !== 1) comp.anomaly_k = strength;
  }
  const cfg = (theta, scenario) => ({ date: D.date, scenario, scale: D.scale, theta });
  return { base: cfg(base, sc.kind === "fair" ? "none" : D.scenario), comp: cfg(comp, sc.kind === "fair" ? "winefair" : D.scenario) };
}
function askSameConfig(row, cfg) {
  return row.date === cfg.date && row.scenario === cfg.scenario && +row.scale === +cfg.scale &&
    row.model_ver === LIB.model_ver && row.input_ver === LIB.input_ver &&
    askThetaSig(row.date, row.theta) === askThetaSig(cfg.date, cfg.theta);
}
async function askScenarios(D) {
  let bands = [];
  try { bands = (await api("/api/bands")).filter(b => b.compare).sort((a, b) => b.seeds - a.seeds); } catch (e) {}
  const out = [{ id: "bs", kind: "seat", label: "더뷔페 좌석 338석", sub: "현재 조건에서 더뷔페 좌석만 338석으로 변경 · 가정 실험" }];
  for (const a of LIB.anomalies || []) out.push({ id: "an" + a.ID, kind: "anom", label: a.이름,
    sub: anomLead(a), a, popDiff: +a.ID === 3 });
  if ((LIB.dates || []).find(x => x.date === D.date && x.fair)) out.push({ id: "wf", kind: "fair", label: "와인페어 진행",
    sub: "같은 날 행사 없음과 비교 · 손님 구성이 달라 짝 비교 아님", popDiff: true });
  const L = refreshDays.list || [];
  for (const sc of out) {
    const spec = askPairSpec(D, sc);
    const A = L.find(d => askSameConfig(d, spec.base)), B = L.find(d => askSameConfig(d, spec.comp));
    // /api/bands의 요약에는 규모가 없으므로 전체 조건을 확인한 하루 키로 연결한다.
    const band = A && B && bands.find(b => b.base_key === A.key && b.compare_key === B.key &&
      b.model_ver === LIB.model_ver && b.input_ver === LIB.input_ver &&
      askThetaSig(D.date, b.theta) === askThetaSig(D.date, spec.base.theta) &&
      askThetaSig(D.date, b.compare) === askThetaSig(D.date, spec.comp.theta));
    Object.assign(sc, band ? { band, aKey: band.base_key, bKey: band.compare_key, ok: true }
      : A && B ? { aKey: A.key, bKey: B.key, ok: true, seed0: true } : { ok: false });
  }
  return out;
}

let ASK_EVIDENCE;
function askLoadEvidence() {
  if (!ASK_EVIDENCE) ASK_EVIDENCE = api("/static/anomaly_evidence.json").catch(() => null);
  return ASK_EVIDENCE;
}
function askEvidencePanel(C) {
  if (!C.sc || C.sc.kind !== "anom") return "";
  const used = (C.B || {}).anomaly || {}, e = (C.evidence || {})[String(C.sc.a.ID)];
  const applied = (used.applied || []).join(" · ") || "적용 상세 기록 없음";
  let h = `<details class="cmp-evidence pane" open><summary><b>이번 계산에 쓴 값과 근거</b></summary><p><b>이번 계산에 적용:</b> ${esc(applied)}</p>` +
    `<p><b>계산 기록의 출처:</b> ${esc(used.src || "출처 기록 없음")} · ${esc(used.grade || "등급 기록 없음")}</p>`;
  if (e) {
    const f = v => Number.isInteger(v) ? String(v) : (+v).toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    // 10/16 외부 자료는 참고 표시일 뿐 위 적용값을 산출한 근거가 아니다(세 자료 모두 계산에 자동 적용하지 않음) — 제목에서 구분
    const kind = { 3: "강수 관측", 4: "검색 관심", 5: "방한객 통계" }[C.sc.a.ID] || "외부";
    h += `<div class="cmp-observed"><p class="cmp-obs-h"><b>${kind} 참고자료 · 현재 시나리오 배율의 산출값 아님</b></p>` +
      `<p><b>${esc(e.source_id)}:</b> ${esc(e.source_name)} · ${esc(e.grade)}</p>` +
      `<p><b>관측 범위:</b> ${e.observations.map(x => `${esc(x.level)} ${f(x.value)} ${esc(x.unit)}`).join(" / ")}</p>` +
      `<p><b>분모:</b> ${esc(e.denominator)}</p><p>${esc(e.coverage)}</p>` +
      `<p><b>가정:</b> ${esc(e.assumption)}</p><p class="hint">${esc(e.status)}</p></div>`;
  }
  return h + `</details>`;
}

async function renderAsk() {
  const el = $("#askView"), D = DAY, render = ++ASK.render;
  if (!D) { el.innerHTML = `<div class="callout info">먼저 왼쪽에서 하루를 돌리거나 계산해 둔 날을 고르세요.</div>`; return; }
  el.innerHTML = `<div class="cmp-wrap"><div class="hint">비교할 결과를 읽는 중…</div></div>`;
  const S = await askScenarios(D);
  if (render !== ASK.render || !DAY || DAY.key !== D.key) return;
  if (!S.find(x => x.id === ASK.scn)) ASK.scn = (S.find(x => x.ok) || {}).id || null;
  const selected = S.find(x => x.id === ASK.scn), sc = selected && selected.ok ? selected : null;
  let A = null, B = null, FA = null, FB = null, evidence = null;
  if (sc) {
    [A, B] = await Promise.all([ensureDay(sc.aKey), ensureDay(sc.bKey)]);
    try { [FA, FB] = await Promise.all([flowOf(sc.aKey), flowOf(sc.bKey)]); } catch (e) {}
    if (sc.kind === "anom") evidence = await askLoadEvidence();
    if (render !== ASK.render || !DAY || DAY.key !== D.key) return;
  }
  ASK.cur = { D, S, sc, A, B, evidence, FA: FA && !FA.error ? FA : null, FB: FB && !FB.error ? FB : null };
  if (sc && (!ASK.venue || !askVenues(A, B).includes(ASK.venue))) ASK.venue = askTopVenue(ASK.cur) || "THE_BUFFET";
  drawAsk();
}

async function askRunDay(cfg, job, label) {
  const r = await api("/api/day", cfg);
  if (!["done", "running"].includes(r.status)) throw new Error(r.error || "계산을 시작하지 못했습니다");
  if (r.status !== "done") for (;;) {
    const s = await api("/api/day/status?key=" + encodeURIComponent(r.key));
    if (s.status === "done") break;
    if (["error", "lost", "none"].includes(s.status)) throw new Error(s.error || "계산이 끊겼습니다. 상황을 다시 선택해 주세요");
    job.message = `${label} · ${s.total ? `${(s.done || 0).toLocaleString()}/${s.total.toLocaleString()}팀` : "손님 만드는 중"}`;
    job.percent = s.total ? 100 * (s.done || 0) / s.total : 0;
    if (MODE === "ask" && ASK.cur) drawAsk();
    await new Promise(res => setTimeout(res, 1000));
  }
  delete DAYCACHE[r.key]; delete FLOWCACHE[r.key];
  return r.key;
}
async function askRunScenario(D, sc) {
  if (ASK.job) return;
  const job = { dayKey: D.key, date: D.date, label: sc.label, message: "계산 준비 중", percent: 0 };
  ASK.job = job; ASK.error = null; ASK.scn = sc.id; ASK.venue = null; ASK.venueSet = false;
  if (ASK.cur) { ASK.cur.sc = null; ASK.cur.A = null; ASK.cur.B = null; drawAsk(); }
  try {
    const spec = askPairSpec(D, sc);
    await askRunDay(spec.base, job, "A 평상시 확인");
    await askRunDay(spec.comp, job, "B 선택한 상황 계산");
    await refreshDays();
  } catch (e) { ASK.error = { dayKey: D.key, message: e.message }; }
  finally {
    ASK.job = null;
    if (MODE === "ask") await renderAsk();
  }
}

function askVenues(A, B) {
  const s = new Set([...Object.keys((A && A.venue_detail) || {}), ...Object.keys((B && B.venue_detail) || {})]);
  for (const X of [A, B]) for (const l of Object.keys((X && X.present) || {})) if (!/ROOM|LOBBY|DESK|STN|ICN|GATE/.test(l)) s.add(l);
  return [...s];
}
// 변화가 큰 업장 — 짝 비교에서 흔들림과 구분되는 이용 변화가 가장 큰 곳 (없으면 시드 0 이용 인원 차이)
function askTopVenue(C) {
  const { sc, A, B } = C;
  if (sc.band) {
    const E = sc.band.effect || {};
    let best = null;
    for (const [loc, ms] of Object.entries(VEN_M)) for (const [k] of ms.filter(m => / 이용 \(명\)$/.test(m[0]))) {
      const e = E[k]; if (e && sureEffect(e, sc.band.seeds) && (!best || Math.abs(e.diff) > best[1])) best = [loc, Math.abs(e.diff), "짝 비교 평균"];
    }
    if (best) { C.topWhy = best[2]; return best[0]; }
  }
  const va = A.venue_detail || {}, vb = B.venue_detail || {};
  const r = Object.keys({ ...va, ...vb }).map(l => [l, Math.abs(((vb[l] || {}).persons_day || 0) - ((va[l] || {}).persons_day || 0))]).sort((x, y) => y[1] - x[1])[0];
  C.topWhy = "시드 0 한 번";
  return r ? r[0] : null;
}

// ---------------------------------------------------------------------------
// 10/17 UX 10차 · 상황 비교를 '요약 → 원인 → 상세' 로 — ① 무엇을 바꿨나 ② 무엇이 달라졌나 ③ 왜 달라졌나 ④ 어떤 조건에서 유효한가 ⑤ 자세히 분석
//   새 계산은 없다. 이미 있는 A/B 하루 · 시드 묶음(band) · 정산 흐름에서만 고르고 줄여 보여 준다
// ---------------------------------------------------------------------------
const askUnc = e => !e || e.lo95 == null || (e.lo95 <= 0 && e.hi95 >= 0);
// ① 무엇을 바꿨나 — 기준 운영(A) → 변경 운영(B) 의 조건 차이
function askCond(C) {
  const { sc, A, B, D } = C;
  if (sc.kind === "seat") {
    const ca = ((A.venue_detail || {}).THE_BUFFET || {}).cap, cb = ((B.venue_detail || {}).THE_BUFFET || {}).cap;
    return { what: "더뷔페 좌석", a: ca ? `${ca}석` : "기본", b: cb ? `${cb}석` : "변경", d: ca && cb ? `${cb - ca > 0 ? "+" : "−"}${Math.abs(cb - ca)}석` : "",
      short: ca && cb ? `더뷔페 좌석을 ${Math.abs(cb - ca)}석 ${cb > ca ? "늘린" : "줄인"} 조건` : "더뷔페 좌석을 바꾼 조건", tag: "좌석 수만 바꾼 가정 실험 · 다른 조건과 손님은 같음", lines: [] };
  }
  if (sc.kind === "anom" && sc.a) {
    const used = B && B.anomaly && +B.anomaly.id === +sc.a.ID ? B.anomaly : null, k = used && used.k != null ? +used.k : +(((D || {}).theta || {}).anomaly_k || 1);
    const L = anomLines(sc.a, k), price = /가격|인상/.test(sc.label);
    return { what: sc.a.이름, a: "추가 변동 없음", b: sc.a.이름, d: "", short: `'${sc.a.이름}' 조건`, lines: L,
      tag: price ? "단가는 정한 값 · 가격에 대한 손님 반응은 가정 △" : "상황의 크기는 가정 △" + (k !== 1 ? ` · 크기 ×${k}` : "") };
  }
  return { what: "와인페어", a: "행사 없음", b: "와인페어 진행", d: "", short: "와인페어를 연 날", lines: [], tag: "행사 손님이 더해져 손님 구성이 다름 · 같은 손님끼리 짝 비교 아님" };
}
// ② 무엇이 달라졌나 — 대표 수치 셋 (각자 계산 기준을 붙인다)
function askKpis(C) {
  const { sc, A, B } = C, E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const r = E && E["순매출 (억)"], t = E && E["공급 제한 겪은 팀 (팀)"];
  const rev = r ? { v: r.diff, unc: askUnc(r), basis: `시드 ${n}쌍 평균 · 95% ${v2Sign(+r.lo95, 2)} ~ ${v2Sign(+r.hi95, 2)}억` } : { v: (B.total - A.total) / 1.1 / 1e8, unc: null, basis: "시드 0 한 번 · 반복 범위 없음" };
  const c = X => (X.guests || []).filter(g => g.n_switch > 0).length;
  const con = t ? { v: t.diff, unc: askUnc(t), basis: `시드 ${n}쌍 평균 · 95% ${v2Sign(t.lo95, 0)} ~ ${v2Sign(t.hi95, 0)}팀` } : { v: c(B) - c(A), unc: null, basis: "시드 0 한 번" };
  let beh = null;
  if (!sc.popDiff) {
    const ga = Object.fromEntries((A.guests || []).map(g => [g.id, (g.acts || []).join("|")]));
    beh = { v: (B.guests || []).filter(g => g.id in ga && ga[g.id] !== (g.acts || []).join("|")).length, of: Object.keys(ga).length };
  }
  return { rev, con, beh, n };
}
// ③ 왜 달라졌나 — 업장 이용 변화가 큰 순서로 (짝 비교에서 방향이 일관된 것 우선, 없으면 시드 0 이용 인원)
//   10/17 UX 11차 · 같은 업장의 식사 지표(더뷔페 중식 · 석식 · 다음날 중식 + 다음날 조식)는 한 줄(업장 합계)로 묶고 그 아래 내역으로 — 별개 원인 셋처럼 읽히지 않게.
//   막대는 같은 단위(인 · 회)끼리만 길이를 비교하고, 판 · 잔 · 건은 막대 없이 숫자만 둔다 (단위가 달라 길이 비교가 뜻이 없음)
function askDrivers(C) {
  const { sc, A, B } = C, E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const out = [];
  if (E) for (const [loc, ms] of Object.entries(VEN_M)) {
    const subs = [];
    for (const [k, lab, u] of ms) {
      if (!E[k] || !/ 이용 \(명\)$| \(판\)$| \(잔\)$| \(건\)$/.test(k)) continue;
      const e = E[k]; subs.push({ loc, k, lab: `${shortName(loc)} ${lab}`, sub: lab, a: sc.band.base[k].mean, b: sc.band.comp[k].mean, d: e.diff, u, sure: sureEffect(e, n), basis: `시드 ${n}쌍 평균` });
    }
    if (!subs.length) continue;
    const meals = subs.filter(x => x.u === " 인 · 회"), rest = subs.filter(x => x.u !== " 인 · 회");
    if (meals.length > 1) {
      // 업장 합계 (겹치지 않는 식사 지표의 합) — 방향이 모두 일관되면 합계도 일관, 하나라도 불확실이면 '내역 보기' 로 둔다
      const d = meals.reduce((s, x) => s + x.d, 0), a = meals.reduce((s, x) => s + x.a, 0), b = meals.reduce((s, x) => s + x.b, 0);
      const sure = meals.every(x => x.sure) ? true : meals.some(x => x.sure === false) ? false : null;
      out.push({ loc, k: loc + ":sum", lab: `${shortName(loc)} 이용 합계`, a, b, d, u: " 인 · 회", sure, basis: `시드 ${n}쌍 평균`, subs: meals });
    } else if (meals.length === 1) out.push(meals[0]);
    out.push(...rest);
  }
  if (!out.length) {
    const va = A.venue_detail || {}, vb = B.venue_detail || {};
    for (const loc of new Set([...Object.keys(va), ...Object.keys(vb)])) {
      const a = (va[loc] || {}).persons_day || 0, b = (vb[loc] || {}).persons_day || 0;
      if (a !== b) out.push({ loc, k: loc, lab: `${shortName(loc)} 이용`, a, b, d: b - a, u: " 인 · 회", sure: null, basis: "시드 0 한 번" });
    }
  }
  out.sort((x, y) => (y.sure === true) - (x.sure === true) || Math.abs(y.d) - Math.abs(x.d));
  // 단위별로 고른다: 인 · 회(식사 이용)에서 최대 셋, 다른 단위에서는 방향이 일관된 것만 최대 둘
  const mAll = out.filter(x => x.u === " 인 · 회"), mSure = mAll.filter(x => x.sure !== false);
  const meals = (mSure.length ? mSure : mAll).slice(0, 3), others = out.filter(x => x.u !== " 인 · 회" && x.sure !== false).slice(0, 2);
  return [...meals, ...others];
}
// 운영자가 읽을 한 문장 — 모두 위 수치에서만 만든다
function askReading(C, cond, K, drv) {
  const p = [];
  if (K.con.unc) p.push("공급 제약 팀 변화는 시드 흔들림과 구분되지 않고");
  else if (K.con.v) p.push(`공급 제약을 겪은 팀이 ${Math.abs(Math.round(K.con.v))}팀 ${K.con.v < 0 ? "줄고" : "늘고"}`);
  const top = drv.find(x => x.sure !== false);
  if (top) p.push(`${josa(top.lab, "이/가")} ${Math.abs(Math.round(top.d)).toLocaleString()}${top.u.trim()} ${top.d > 0 ? "늘어" : "줄어"}`);
  if (K.rev.unc) p.push("체류 매출 변화는 시드 흔들림과 구분되지 않습니다");
  else p.push(`체류 매출이 ${Math.abs(K.rev.v).toFixed(2)}억 ${K.rev.v >= 0 ? "늘었습니다" : "줄었습니다"}`);
  return `${cond.short}에서 ${p.join(", ")}. 실제 호텔에서 확인된 효과가 아니라 모델 안에서의 결과입니다.`;
}
// 10/17 UX 12차 · 대표 띠 — 숫자 셋을 나열하지 않고 '무엇이 좋아졌나 · 나빠졌나' 가 먼저 읽히게:
//   제목(실험 이름) → 한 문장 판정 → 네 칸(조건 · 공급 제약 팀 · 체류 매출 · 달라진 손님) 각 칸에 방향 표식(개선 · 악화 · 불확실 · 참고) → 한 줄 주의
// 10/19 UX 22차 — 손님 수요(목적 · 비투숙 · 가고 싶음 배율)나 손님 구성이 함께 바뀌는 상황. 이때 '공급 제약 팀 감소' 는
// 찾아온 손님이 줄어서일 수 있으므로 개선 · 악화로 읽지 않고 중립 변화량으로 보여 준다 (계산 · 수치는 그대로)
function askDemandMix(sc) {
  if (!sc) return false;
  if (sc.kind === "fair" || sc.popDiff) return true;
  if (sc.kind !== "anom" || !sc.a) return false;
  return ["목적 배율", "비투숙 배율", "가고 싶음 배율"].some(k => String(sc.a[k] || "").trim() !== "");
}
function askVerdict(C, cond, K) {
  const good = [], bad = [], unc = [];
  const con = K.con, rev = K.rev;
  if (con.unc) unc.push("공급 제약 팀"); else if (con.v < 0) good.push(`공급 제약 팀 ${Math.abs(Math.round(con.v))}팀 감소`); else if (con.v > 0) bad.push(`공급 제약 팀 ${Math.round(con.v)}팀 증가`);
  if (rev.unc) unc.push("체류 매출"); else if (rev.v > 0) good.push(`체류 매출 ${rev.v.toFixed(2)}억 증가`); else if (rev.v < 0) bad.push(`체류 매출 ${Math.abs(rev.v).toFixed(2)}억 감소`);
  let t;
  if (!good.length && !bad.length) t = unc.length ? `${unc.join(" · ")} 변화는 시드 흔들림과 구분되지 않습니다` : "뚜렷한 변화가 없습니다";
  else t = [good.length ? `${good.join(", ")}` : "", bad.length ? `${bad.join(", ")}` : ""].filter(Boolean).join(" / ") + (unc.length ? ` · ${unc.join(" · ")}은 불확실` : "");
  let tone = good.length && !bad.length ? "good" : bad.length && !good.length ? "bad" : good.length || bad.length ? "mixed" : "unc";
  if (askDemandMix(C && C.sc) && tone !== "unc") tone = "neu";   // 수요가 함께 바뀐 상황 — 색으로 좋고 나쁨을 말하지 않음
  return { t, tone };
}
function askTop(C, cond, K) {
  const mix = askDemandMix(C.sc);
  const dir = (x, lowerBetter) => x.unc ? ["unc", "불확실"] : x.v === 0 ? ["flat", "변화 없음"] : mix ? ["mix", x.v < 0 ? "감소" : "증가"] : ((x.v < 0) === lowerBetter ? ["good", "개선"] : ["bad", "악화"]);
  const tile = (lab, v, u, [cls, tag], sub) => `<div class="kt ${cls}"><small>${lab}</small><b class="num">${v}${u ? `<u>${u}</u>` : ""}</b><em class="dir">${tag}</em><span>${sub}</span></div>`;
  const vd = askVerdict(C, cond, K);
  const con = dir(K.con, true), rev = dir(K.rev, false);
  const condTile = `<div class="kt cond"><small>${esc(cond.what)}</small><b class="num">${cond.a && cond.b && /석$/.test(cond.a) ? `<i class="ca">${esc(cond.a)}</i><i class="car">→</i>${esc(cond.b)}` : esc(cond.b)}</b><em class="dir chg">${esc(cond.d || "조건 변경")}</em><span>${esc(cond.a && !/석$/.test(cond.a) ? `기준 ${cond.a}` : "기준 운영 A → 변경 운영 B")}</span></div>`;
  return `<section class="v2hero chero c10 c12"><div class="ttl"><div class="ov">① 무엇을 바꿨나 → ② 무엇이 달라졌나 (B − A)</div><h2 class="vd ${vd.tone}">${esc(cond.short)}에서 ${esc(vd.t)}</h2>` +
    (cond.lines.length ? `<ul class="clines">${cond.lines.map(([x, y]) => `<li><span>${esc(x)}</span><b>${esc(y)}</b></li>`).join("")}</ul>` : "") + `</div>` +
    `<div class="ktiles">` + condTile +
    tile("공급 제약 팀", K.con.unc ? `<i class="dimv">${fmtD(K.con.v)}</i>` : fmtD(K.con.v), "팀", con, K.con.basis) +
    tile("체류 매출", K.rev.unc ? `<i class="dimv">${v2Sign(K.rev.v, 2)}</i>` : v2Sign(K.rev.v, 2), "억", rev, K.rev.basis) +
    (K.beh ? tile("행동이 달라진 손님", K.beh.v.toLocaleString(), "팀", ["info", "참고"], `같은 손님 ${K.beh.of.toLocaleString()}팀 중 · 시드 0`) : tile("행동이 달라진 손님", "—", "", ["info", "짝 비교 아님"], "손님 구성이 달라 짝 비교 없음")) +
    `</div>` + (mix ? `<div class="kmix"><b>손님 수요도 함께 바뀐 상황</b> · 위 증감은 '찾아온 손님 변화 + 운영 조건 변화' 를 합친 결과라, 공급 제약 팀이 줄어도 운영이 나아졌다는 뜻은 아닙니다</div>` : "") + `<div class="kfoot"><span class="chip">${esc(cond.tag)}</span><span class="mtag">모델 안의 변화 · 실제 호텔 효과로 검증된 값은 아님</span></div></section>`;
}
function askWhy(C, drv) {
  if (!drv.length) return `<section class="v2s c10s"><div class="sh"><h2>③ 왜 달라졌나</h2></div><div class="pane hint">업장 이용 변화가 기록되지 않았습니다.</div></section>`;
  const meals = drv.filter(x => x.u === " 인 · 회"), others = drv.filter(x => x.u !== " 인 · 회");
  const mx = Math.max(...meals.map(x => Math.abs(x.d))) || 1;
  const val = x => x.sure === false ? `<b class="unc-t" title="95% 구간이 0 포함">불확실</b>` : `${fmtD(x.d)}<small>${esc(x.u.trim())}</small>`;
  const ab = x => `${Math.round(x.a).toLocaleString()} → ${Math.round(x.b).toLocaleString()}`;
  // 식사 이용 (인 · 회) — 막대로 길이 비교. 업장 합계 줄 아래에 겹치지 않는 내역 (합계 = 내역의 합)
  const rows = meals.map((x, i) => `<button class="cdrv ${x.loc === ASK.venue ? "on" : ""} ${x.d < 0 ? "negrow" : ""}" data-sv="${x.loc}" aria-pressed="${x.loc === ASK.venue}"><span class="rk">${i + 1}</span><span class="nm">${vdot(x.loc)}${esc(x.lab)}</span>` +
    `<span class="bar"><i class="${x.sure === false ? "unc" : x.d >= 0 ? "pos" : "neg"}" style="width:${Math.max(2, Math.abs(x.d) / mx * 100).toFixed(1)}%"></i></span>` +
    `<span class="v num">${val(x)}</span><span class="ab num">${ab(x)}</span></button>` +
    (x.subs ? `<div class="cdrv-subs" role="list" aria-label="${esc(x.lab)} 내역">` + x.subs.map(s => `<div class="cdrv sub" role="listitem"><span class="rk tree" aria-hidden="true">└</span><span class="nm">${esc(s.sub)}</span>` +
      `<span class="bar"><i class="${s.sure === false ? "unc" : s.d >= 0 ? "pos" : "neg"}" style="width:${Math.max(2, Math.abs(s.d) / mx * 100).toFixed(1)}%"></i></span><span class="v num">${val(s)}</span><span class="ab num">${ab(s)}</span></div>`).join("") +
      `<div class="cdrv-note">내역의 합 = 합계 · 서로 겹치지 않음</div></div>` : "")).join("");
  // 다른 단위 (판 · 잔 · 건) — 막대 없이 숫자만. 인 · 회와 길이를 견주지 않는다
  const orows = others.length ? `<div class="cdrv-other"><div class="cdrv-oh">단위가 다른 변화 <span class="hint">· 위 막대와 크기를 견주지 않음</span></div>` +
    others.map(x => `<button class="cdrv other ${x.loc === ASK.venue ? "on" : ""} ${x.d < 0 ? "negrow" : ""}" data-sv="${x.loc}" aria-pressed="${x.loc === ASK.venue}"><span class="rk dot" aria-hidden="true">·</span><span class="nm">${vdot(x.loc)}${esc(x.lab)}</span><span class="bar none" aria-hidden="true"></span><span class="v num">${val(x)}</span><span class="ab num">${ab(x)}</span></button>`).join("") + `</div>` : "";
  // 10/17 UX 12차 · 중요한 변화 1~2개를 먼저 한 문장으로, 막대는 그 근거로
  const lead = (() => { const m1 = meals.find(x => x.sure !== false), o1 = others[0]; const p = [];
    if (m1) p.push(`${josa(m1.lab, "이/가")} ${Math.abs(Math.round(m1.d)).toLocaleString()}인 · 회 ${m1.d > 0 ? "늘어난" : "줄어든"} 것이 가장 큰 변화${m1.subs ? ` (${m1.subs.map(x => `${x.sub} ${fmtD(x.d)}`).join(", ")})` : ""}`);
    if (o1) p.push(`${o1.lab}는 ${Math.abs(Math.round(o1.d))}${o1.u.trim()} ${o1.d > 0 ? "증가" : "감소"}`);
    if (!p.length) p.push("시드 흔들림과 구분되는 업장 이용 변화는 없습니다");
    return p.join(" · ") + "."; })();
  return `<section class="v2s c10s"><div class="sh"><h2>③ 왜 달라졌나</h2><span class="s">${esc(drv[0].basis)} · 줄을 누르면 아래 업장이 바뀝니다</span></div>` +
    `<div class="pane cdrvs"><p class="clead">${esc(lead)}</p><div class="cgh">근거 · 업장별 이용 변화</div>${rows}${orows}${capN("막대는 인 · 회끼리만 비교 · 모델 안의 변화", "막대 길이는 식사 이용(인 · 회) 사이의 변화 크기 비교입니다. 인 · 회 = 식사 이용을 사람 수로 센 값(같은 손님이 두 끼 먹으면 2). 불확실 = 95% 구간이 0을 포함해 시드 흔들림과 구분되지 않는 변화. 모두 모델 안의 변화이며 실제 호텔에서 확인된 효과가 아닙니다.")}</div>` +
    `<div id="cmpFocus">${askFocus(C, ASK.venue)}</div></section>`;
}
// 가장 영향받은 업장 — 전후 비교 차트 하나만 기본으로, 표 · 고객 · 검토는 '이 업장 자세히' 안에
function askFocus(C, loc) {
  if (!C || !loc) return "";
  const { A, B } = C, va = (A.venue_detail || {})[loc], vb = (B.venue_detail || {})[loc];
  const nm = shortName(loc);
  let chart = "", cap = "";
  if (va || vb) {
    const ws = [...new Set([...((va || {}).windows || []), ...((vb || {}).windows || [])].filter(w => w.persons || w.over_persons).map(w => w.name))];
    const wf = (v, x) => ((v || {}).windows || []).find(w => w.name === x) || {};
    const mx = Math.max(100, ...ws.map(x => Math.max(wf(va, x).peak_pct || 0, wf(vb, x).peak_pct || 0)));
    chart = ws.length ? ws.map(x => { const a = wf(va, x), b = wf(vb, x);
      return `<div class="fw"><span class="fn">${esc(x.replace(" (익일)", " (다음날)"))}</span><span class="fb"><i class="fa" style="width:${((a.peak_pct || 0) / mx * 100).toFixed(1)}%"></i><i class="fbb" style="width:${((b.peak_pct || 0) / mx * 100).toFixed(1)}%"></i><em class="f100" style="left:${(100 / mx * 100).toFixed(1)}%"></em></span>` +
        `<span class="fv num">A ${a.peak_pct || 0}% · B ${b.peak_pct || 0}%</span><span class="fo num ${b.over_persons ? "bad" : ""}" title="자리가 없어 다른 선택을 한 팀의 일행 수">${a.over_persons || b.over_persons ? `막힘 ${a.over_persons || 0} → ${b.over_persons || 0}명` : ""}</span></div>`; }).join("") : `<div class="hint">이 날 이 업장의 회차 기록이 없습니다.</div>`;
    cap = capN("회차별 가장 붐빈 때 좌석 점유율 · 시드 0", "세로선 = 좌석 100%. 막힘 = 자리가 없어 다른 선택을 한 팀의 일행 수이고, 그 회차에서 처음 막힌 팀만 셉니다. 시드 0 한 번 계산입니다.");
  } else {
    const hr = X => { const a = ((X.present || {})[loc]) || []; const o = {}; a.forEach((v, i) => { const hh = 10 + Math.floor(i / 6); o[hh] = Math.max(o[hh] || 0, v); }); return o; };
    const ha = hr(A), hb = hr(B), hs = [...new Set([...Object.keys(ha), ...Object.keys(hb)])].filter(k => ha[k] || hb[k]).sort((x, y) => x - y);
    const mx = Math.max(1, ...hs.map(k => Math.max(ha[k] || 0, hb[k] || 0)));
    chart = hs.length ? hs.map(k => `<div class="fw"><span class="fn">${String(k % 24).padStart(2, "0")}시${k >= 24 ? " (다음날)" : ""}</span><span class="fb"><i class="fa" style="width:${((ha[k] || 0) / mx * 100).toFixed(1)}%"></i><i class="fbb" style="width:${((hb[k] || 0) / mx * 100).toFixed(1)}%"></i></span><span class="fv num">A ${ha[k] || 0} · B ${hb[k] || 0}명</span><span class="fo"></span></div>`).join("") : `<div class="hint">이 시설의 시간대 기록이 없습니다.</div>`;
    cap = capN("시간대별 최대 머문 인원 · 시드 0", "같은 시각에 머문 인원의 시간대 최댓값입니다. 이 시설은 좌석 · 매출을 업장 단위로 집계하지 않아 머문 인원만 보입니다.");
  }
  const all = askVenues(A, B), quick = QUICK_V.filter(l => all.includes(l)), rest = all.filter(l => !quick.includes(l)).sort((x, y) => locName(x).localeCompare(locName(y)));
  return `<div class="pane cfocus"><div class="cfh"><h3>${vdot(loc)}${esc(nm)} <span class="hint">전후 비교</span></h3><span class="lg"><i class="fa"></i>A 기준 운영<i class="fbb"></i>B 변경 운영</span>` +
    `<select class="cmp-vsel" aria-label="다른 업장 보기"><option value="">다른 업장 보기…</option>${[...quick, ...rest].map(l => `<option value="${l}" ${l === loc ? "selected" : ""}>${esc(locName(l))}</option>`).join("")}</select></div>` +
    `<div class="fchart">${chart}</div>${cap}` +
    `<details class="cmore" id="cmpVenMore"><summary>${esc(nm)} 자세히 · 짝 비교 표 · 누가 영향을 받나 · 막힌 식사는 어디로 · 현장 검토</summary><div id="cmpVen">${askVenueDetail(C, loc)}</div></details></div>`;
}
// ④ 실험 범위와 한계 (10차 '어떤 조건에서 유효한가')
function askValid(C, cond, K) {
  const { sc } = C, E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const pri = k => /순매출/.test(k) ? 0 : /공급 제한/.test(k) ? 1 : / 이용 \(명\)$/.test(k) ? 2 : /^L\d|비중/.test(k) ? 9 : 5;
  const U = E ? Object.entries(E).filter(([, e]) => askUnc(e)).sort((a, b) => pri(a[0]) - pri(b[0])).map(([k]) => askMetric(k).replace(/ \(%\)$/, " 비중")) : [];
  const S = E ? Object.entries(E).filter(([, e]) => sureEffect(e, n)).length : 0;
  const rep = E ? `같은 손님 · 시드 ${n}쌍으로 반복했습니다. 지표 ${Object.keys(E).length}개 중 ${S}개는 시드 반복에서 방향이 일관됐고, ${U.length}개는 95% 구간이 0을 포함합니다.` : "시드 0 한 번 계산이라 반복 범위가 없습니다. 차이에 손님 생성의 우연이 섞여 있습니다.";
  const asm = cond.tag + (sc.kind === "seat" ? ". 테라스 50석을 식사에 쓸 수 있는지는 확인되지 않았습니다." : sc.kind === "anom" ? `. ${ANOM_NOTE[sc.a.ID] || "실제 관측값이 아니라 시나리오에 적용한 가정값입니다."}` : ".");
  const unc = E ? (U.length ? `${U.slice(0, 4).join(", ")}${U.length > 4 ? ` 외 ${U.length - 4}개` : ""}` : "없음") : "모든 수치 (반복 범위 없음)";
  const loc = ASK.venue, ob = (((C.B.venue_detail || {})[loc]) || {}).over_persons || 0, prop = [];
  if (sc.kind === "seat") prop.push("테라스 50석 식사 사용 가능 여부(연회 · 인력 · 동선)", "좌석을 늘려도 2부에 몰리는 손님이 남으므로 1부 안내 검토");
  else if (sc.kind === "anom") prop.push("다른 업장에서 넘어올 손님을 받을 회차 · 좌석 여력");
  if (ob > 0 && sc.kind !== "seat") prop.push("B 에서도 막힘이 남는 회차의 예약 분산 안내");
  const cell = (t, b) => `<div class="cv"><b>${t}</b><p>${b}</p></div>`;
  // 10/17 UX 11차 · 제목 '어떤 조건에서 유효한가' → '실험 범위와 한계' (실제 효과가 검증된 것처럼 읽히지 않게)
  return `<section class="v2s c10s"><div class="sh"><h2>④ 실험 범위와 한계</h2><span class="s">모델 안의 결과 · 실제 호텔 실적이 아님</span></div><div class="pane cvalid">` +
    cell("시드 반복", esc(rep)) + cell("넣은 가정", esc(asm)) + cell("불확실한 수치", esc(unc)) +
    cell("현장에서 확인할 것 (미검증)", `${esc(prop.join(" · ") || "이 상황에서 따로 제안할 조치가 없습니다")}<br><span class="hint">필요한 현장 자료: ${esc(venNeed(loc, sc))}</span>`) + `</div></section>`;
}

// 상황 비교의 어시스턴트 열림 (main.as-on) — 시험용 가짜 DOM 에서도 안전하게
const askAsOn = () => { const m = typeof document !== "undefined" && document.querySelector ? document.querySelector("main") : null; return !!(m && m.classList && m.classList.contains("as-on")); };
function drawAsk() {
  const el = $("#askView"), C = ASK.cur; if (!C) return;
  const { D, S, sc, A, B } = C;
  const dl = `${D.date.slice(5).replace("-", "/")} (${"일월화수목금토"[new Date(D.date + "T12:00:00").getDay()]})`;
  // 10/17 v2 — 운영 요약과 같은 규칙: 제목 줄 · 짙은 대표 띠(체류 매출 B − A) · 회색 바탕 칸(pane) · 표 오른쪽 정렬 · 상세는 펼침/패널
  let h = `<div class="rv2 cv2"><div class="v2top"><div><h1>${dl} 상황 비교</h1><div class="sub">시뮬레이션 결과입니다 · <em>실제 호텔 실적이 아님</em> · 기준 운영(A)과 변경 운영(B)을 같은 손님으로 비교합니다 · 비교의 기준 하루는 왼쪽 '기준 하루 설정'</div></div><div class="v2top-r"><button class="v2asst" id="cmpAsst" aria-pressed="${askAsOn()}" title="이 비교 결과 기준으로 묻고 답하기"><i>?</i>어시스턴트</button></div></div>`;
  const chip = x => `<button class="cmp-chip ${x.id === ASK.scn ? "on" : ""} ${x.ok ? "" : "needs"}" data-scn="${x.id}" ${ASK.job ? "disabled" : ""} title="${esc(x.ok ? (x.sub || "계산한 결과 보기") : "선택하면 이 날짜·조건으로 비교를 계산합니다")}">${esc(x.label)}${x.ok ? "" : ` <small>계산해서 보기</small>`}</button>`;
  const opS = S.filter(x => x.kind === "seat" || (x.kind === "anom" && /가격|인상/.test(x.label))), evS = S.filter(x => !opS.includes(x));
  h += `<div class="cscn"><div class="cscn-h">비교할 실험 고르기</div><div class="cg"><span class="cgl">운영 조건을 바꾸면</span><div class="cgc">${opS.map(chip).join("")}</div></div><div class="cg"><span class="cgl">이런 일이 생기면 <i>크기는 가정 △</i></span><div class="cgc">${evS.map(chip).join("")}</div></div></div>` + askStaleNote(C);
  if (ASK.job) {
    const j = ASK.job;
    h += `<div class="callout info cmp-progress" role="status" aria-live="polite"><b>${esc(j.date.slice(5).replace("-", "/"))} · ${esc(j.label)} 계산 중</b><div>${esc(j.message)}</div><progress max="100" value="${j.percent}"></progress><div class="hint">처음에는 시간이 걸립니다. 다른 상황은 이 계산이 끝나면 선택할 수 있습니다.</div></div>` + askPreview(C);
  }
  if (ASK.error && ASK.error.dayKey === D.key) h += `<div class="callout" role="alert">비교를 완료하지 못했습니다: ${esc(ASK.error.message)}. 상황을 다시 선택해 주세요.</div>`;
  if (!sc) {
    const pv = !ASK.job && ASK.scn ? askPreview(C) : "";
    if (pv) h += pv;
    else if (!ASK.job) h += `<div class="callout info">위에서 비교할 상황을 선택하세요. ${esc(dl)}의 현재 행사·규모·모델 설정을 유지해 A 기준 운영과 B 선택한 상황을 계산합니다. 처음 계산은 시드 0 한 번이며 반복 범위는 없습니다.</div>`;
    el.innerHTML = h + `</div>`; askBindScenarios(C); askBindRun(C); askAssist(); return;
  }
  // 10/17 UX 10차 · ① 무엇을 바꿨나 + ② 무엇이 달라졌나 (짙은 띠) → 한 문장 해석 → ③ 왜 달라졌나 (업장 셋 · 전후 차트 하나) → ④ 유효 조건 → ⑤ 자세히 분석 (접힘)
  const cond = askCond(C), K = askKpis(C), drv = askDrivers(C);
  if (!ASK.venueSet && drv.length && drv[0].loc !== ASK.venue && (VEN_M[drv[0].loc] || C.A.venue_detail[drv[0].loc])) ASK.venue = drv[0].loc;
  h += askTop(C, cond, K);   // 12차 · '읽는 법' 상자는 대표 띠의 판정 문장과 ③ 해석 문장으로 흡수
  h += askWhy(C, drv);
  h += askValid(C, cond, K);
  const an = askAnomNote(C), ev = askEvidencePanel(C);
  // 10/17 UX 11차 · ⑤ 는 표를 한 번에 길게 펼치지 않고 '업장별 / 고객별 / 시간대별 / 전체 지표' 네 묶음으로. 계산 · 정보는 그대로, 묶음마다 따로 연다
  const DS = ASK.deepSec || {};
  const sec = (id, lab, hint, body) => `<details class="cmp-ab pane cdsec" data-dsec="${id}" ${DS[id] ? "open" : ""}><summary><b>${lab}</b> <span class="hint">${hint}</span></summary><div class="cdsec-in">${body}</div></details>`;
  h += `<section class="v2s c10s"><details class="cmp-ab pane cdeep" id="cmpDeep" ${ASK.deep ? "open" : ""}><summary><b>⑤ 자세히 분석</b> <span class="hint">업장별 · 고객별 · 시간대별 · 전체 지표 — 묶음마다 따로 엽니다</span></summary>` +
    sec("venue", "업장별", "다른 업장으로의 파급 · 줄을 누르면 위 업장이 바뀝니다", askSpill(C) || `<div class="hint">업장별 짝 비교 지표가 없습니다.</div>`) +
    sec("guest", "고객별", "투숙 · 비투숙 · 방문 목적별 이용 팀 변화", askByGuest(C)) +
    sec("hour", "시간대별", "식당 안 인원 A · B 시간대 비교", askByHour(C)) +
    sec("all", "전체 지표", "모든 지표의 시드 반복 범위 · 넣은 가정 원문 · A/B 하루 열기",
      (an || ev ? `<section class="v2s"><div class="sh"><h2>이 상황에 넣은 가정</h2><span class="s">실제 관측값이 아니라 시나리오에 적용한 값</span></div><div class="${an && ev ? "grid2" : ""}">${an}${ev}</div></section>` : "") +
      `<section class="v2s"><details class="cmp-ab pane" id="cmpAb" ${ASK.open ? "open" : ""}><summary><b>상세 A/B 비교</b> <span class="hint">모든 지표의 시드 반복 범위 · A/B 하루 열기 · 예전 비교 카드</span></summary><div id="cmpLegacy"><div class="hint">읽는 중…</div></div></details></section>`) +
    `</details></section>`;
  h += `<div class="rfoot hint">시뮬레이션 결과 · 실제 호텔 실적이 아님${noteI("95% 구간은 같은 손님으로 모델을 반복해 돌린 변동 범위이지 실제 매출 예측 구간이 아닙니다.")}</div></div>`;
  el.innerHTML = h;
  askBindScenarios(C);
  askBindRun(C);
  askWireFocus();
  $$("#askView [data-sv]").forEach(b => b.onclick = () => askSelectVenue(b.dataset.sv));
  $$("#askView [data-open]").forEach(b => b.onclick = () => askOpen(b.dataset.open));
  const ab0 = $("#cmpAsst"); if (ab0) ab0.onclick = () => { const on = !askAsOn(); $("main").classList.toggle("as-on", on); ab0.setAttribute("aria-pressed", on ? "true" : "false"); if (on) askAssist(); };
  const dp = $("#cmpDeep"); if (dp) dp.addEventListener("toggle", () => { ASK.deep = dp.open; });
  $$("#askView .cdsec").forEach(d => d.addEventListener("toggle", () => { ASK.deepSec = ASK.deepSec || {}; ASK.deepSec[d.dataset.dsec] = d.open; }));
  const ab = $("#cmpAb");
  ab.addEventListener("toggle", () => { ASK.open = ab.open; if (ab.open) askLegacy(); });
  if (ab.open) askLegacy();
  askAssist();
}

// 10/19 · 계산 전에도 무엇을 바꾸는 실험인지 먼저 보여 준다 (계산 중 · 아직 계산 안 한 상황)
function askPreview(C) {
  const x = (C.S || []).find(y => y.id === ASK.scn); if (!x) return "";
  let body = `<p>${esc(x.sub || "")}</p>`;
  if (x.kind === "seat") {
    // 10/19 UX 22차 — 계산 전부터 지금 기준 좌석(기준 하루 → 없으면 가정표 · 공식 홀 288석)을 보여 준다. 338석은 테라스 50석을 더한 검토용 가정
    const sv = (LIB.seats || {}).THE_BUFFET || {};
    const base = (C.D.theta || {}).buffet_seats || ((C.D.venue_detail || {}).THE_BUFFET || {}).cap || sv.n;
    body = `<ul><li><span>더뷔페 좌석</span><b>${base ? `지금 ${base}석` : "기본 좌석"} → 338석${base ? ` <span class="hint">(+${338 - base}석)</span>` : ""}</b></li></ul>` +
      `<p class="hint">338석은 실제 운영 확정값이 아니라 검토용 가정입니다(테라스 50석을 식사에 쓴다고 본 값 · 사용 가능 여부 미확인). 좌석 수만 바꾸고 다른 조건과 손님은 같습니다.</p>`;
  } else if (x.kind === "anom" && x.a) {
    const k = +((C.D.theta || {}).anomaly_k || 1), L = anomLines(x.a, k);
    body = `<p>${esc(anomLead(x.a))}</p>` + (L.length ? `<ul>${L.map(([p, q]) => `<li><span>${esc(p)}</span><b>${esc(q)}</b></li>`).join("")}</ul>` : "") +
      `<p class="hint">${esc(ANOM_NOTE[x.a.ID] || "실제 관측값이 아니라 시나리오에 적용한 가정값입니다.")}</p>`;
  }
  const run = !x.ok && !ASK.job ? `<a class="rlink" data-run="${esc(x.id)}">이 조건으로 계산해서 보기 →</a>` : "";
  return `<div class="cmp-anom pane"><div class="fhd"><b>${esc(x.label)}</b><span>${ASK.job ? "계산 중 · 넣는 조건 미리보기" : x.ok ? "" : "아직 계산 안 함 · 넣을 조건"}</span></div>${body}${run}</div>`;
}
// 10/19 · 왼쪽 기준 하루가 예전 버전이면 — 비교는 지금 버전으로 계산되고 운영 요약은 기준 하루를 그대로 보여 준다는 것을 알린다
function askStaleNote(C) {
  if (typeof isStale !== "function" || !isStale(C.D)) return "";
  const open = C.sc && C.sc.aKey ? ` <a class="rlink" data-open="day:${esc(C.sc.aKey)}">지금 버전 A 하루를 기준으로 열기 →</a>` : "";
  return `<div class="callout info">왼쪽 기준 하루는 예전 버전 결과입니다. 이 비교는 지금 버전으로 계산하고, 운영 요약 · 고객 흐름은 왼쪽 기준 하루를 그대로 보여 줍니다.${open}</div>`;
}
function askBindRun(C) {
  $$("#askView [data-run]").forEach(b => b.onclick = e => {
    e.preventDefault(); if (ASK.job) return;
    const sc = C.S.find(x => x.id === b.dataset.run); if (sc) askRunScenario(C.D, sc);
  });
  $$("#askView [data-open]").forEach(b => b.onclick = e => { e.preventDefault(); askOpen(b.dataset.open); });
}
function askBindScenarios(C) {
  $$("#askView .cmp-chip[data-scn]").forEach(b => b.onclick = () => {
    if (ASK.job) return;
    const sc = C.S.find(x => x.id === b.dataset.scn); if (!sc) return;
    ASK.scn = sc.id; ASK.venue = null; ASK.venueSet = false; ASK.error = null; askHist();
    if (sc.ok) renderAsk(); else askRunScenario(C.D, sc);
  });
}

function askWireFocus() {
  const sel = $("#askView .cmp-vsel"); if (sel) sel.onchange = () => sel.value && askSelectVenue(sel.value);
  const mo = $("#cmpVenMore"); if (mo) { mo.open = !!ASK.venMore; mo.addEventListener("toggle", () => { ASK.venMore = mo.open; }); }
  $$("#cmpFocus [data-open]").forEach(b => b.onclick = () => askOpen(b.dataset.open));
}
function askSelectVenue(loc) {
  ASK.venue = loc; ASK.venueSet = true; askHist();
  $("#cmpFocus").innerHTML = askFocus(ASK.cur, loc);
  askWireFocus();
  $$("#askView [data-sv]").forEach(x => { x.classList.toggle("on", x.dataset.sv === loc); if (x.classList.contains("cdrv")) x.setAttribute("aria-pressed", x.dataset.sv === loc ? "true" : "false"); });
  $("#cmpFocus").scrollIntoView({ behavior: "smooth", block: "nearest" });
  askAssist();
}
async function askLegacy() {
  const box = $("#cmpLegacy"); if (!box || box.dataset.done) return;
  box.dataset.done = 1;
  const C = ASK.cur;
  let h = "";
  if (C.sc.band) h += `<div class="cmp-abtbl">${askBandTable(C.sc)}</div>`;
  h += `<div class="cmp-abdays"><a class="rlink" data-open="day:${esc(C.sc.aKey)}">A 하루 열기 →</a> <a class="rlink" data-open="day:${esc(C.sc.bKey)}">B 하루 열기 →</a></div><div id="cmpLegacyIn"></div>`;
  box.innerHTML = h;
  $$("#cmpLegacy [data-open]").forEach(b => b.onclick = () => askOpen(b.dataset.open));
  await renderAskLegacy($("#cmpLegacyIn"));
}
function askBandTable(sc) {
  const b = sc.band, E = b.effect || {};
  const names = Object.keys(E).sort((x, y) => (sureEffect(E[y], b.seeds) - sureEffect(E[x], b.seeds)) || ((E[y].ratio || 0) - (E[x].ratio || 0)));
  const f = v => Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : (+v).toFixed(Math.abs(v) < 10 ? 2 : 1);
  return `<table class="t"><tr><th>지표 (시드 ${b.seeds}쌍)</th><th class="n">A 평균</th><th class="n">B 평균</th><th class="n">B − A</th><th class="n">95% 구간</th></tr>` +
    names.map(n => { const e = E[n], s = sureEffect(e, b.seeds); return `<tr class="${s ? "sure" : ""}"><td>${esc(n)}</td><td class="n">${b.base[n] ? f(b.base[n].mean) : "-"}</td><td class="n">${b.comp[n] ? f(b.comp[n].mean) : "-"}</td><td class="n"><b>${e.diff > 0 ? "+" : ""}${f(e.diff)}</b></td><td class="n hint">${f(e.lo95)} ~ ${f(e.hi95)}</td></tr>`; }).join("") +
    `</table><div class="hint">굵은 줄 = 시드 반복에서 방향 일관${noteI("굵은 줄은 95% 구간이 0을 넘지 않고 거의 매번 같은 방향인 변화입니다. 범위는 모델을 반복해 돌린 변동성이지 실제 매출 예측 구간이 아닙니다.")}</div>`;
}

// 호텔 전체 요약 — 실제로 계산된 값만
// 10/16 변칙 시나리오 설명 — 표의 배율 칸 × 크기 조정값을 '기준 대비' 로 적고, B 계산에 실제 들어간 값(applied)을 함께 보여 준다.
// 설명 문구만 바꾼다. anomaly_scenarios.csv 는 입력 버전 계산 대상이라 고치지 않는다(문구만 고쳐도 입력 버전 · 캐시가 바뀜).
const ANOM_LEAD = { 4: "SNS 화제로 피자힐 방문 수요와 선호도가 함께 높아지는 상황을 가정합니다." };
const ANOM_NOTE = {
  4: "실제 방문객 증가율이 아니라 시나리오에 적용한 가정값입니다. 선호 가중치 +50%는 피자힐 방문 인원 +50%가 아닙니다. 다른 식당과 나눠 갖는 선택 비중이 바뀌고, 좌석 · 회차가 차면 이용으로 이어지지 않을 수 있습니다.",
};
const anomKv = s => String(s || "").split(";").filter(p => p.includes(":")).map(p => { const i = p.indexOf(":"); return [p.slice(0, i).trim(), +p.slice(i + 1)]; });
const anomPct = m => { const p = Math.round((m - 1) * 1000) / 10; return `기준 대비 ${p > 0 ? "+" : p < 0 ? "−" : "±"}${Math.abs(p)}%`; };
function anomLead(a) { return ANOM_LEAD[a.ID] || String(a.설명 || "").split(/ — |\. /)[0]; }
function anomLines(a, k) {
  const sc = m => 1 + (m - 1) * k, out = [];
  for (const c of String(a.닫음 || "").split(";").filter(Boolean)) out.push([`${shortName(c)} 운영`, "그날 닫음"]);
  for (const [p, m] of anomKv(a["목적 배율"])) out.push([`'${p}' 목적 손님 수`, anomPct(sc(m))]);
  if (a["비투숙 배율"]) out.push(["비투숙 방문 수요", anomPct(sc(+a["비투숙 배율"]))]);
  for (const [v, m] of anomKv(a["가고 싶음 배율"])) {
    const j = v.lastIndexOf("|"), pp = j >= 0 ? v.slice(0, j) : "", vv = j >= 0 ? v.slice(j + 1) : v;
    out.push([`${pp ? pp + " 손님의 " : ""}${shortName(vv)} 선택 선호 가중치`, anomPct(sc(m))]);
  }
  for (const [v, m] of anomKv(a["가격 배율"])) out.push([`${shortName(v)} 상품 단가`, anomPct(sc(m))]);
  return out;
}
// 상황 비교에 붙는 설명 칸 — B 결과에 기록된 크기 조정값(k)을 우선 쓴다
function askAnomNote(C) {
  const { sc, D, B } = C;
  if (!sc || sc.kind !== "anom" || !sc.a) return "";
  const a = sc.a, used = B && B.anomaly && +B.anomaly.id === +a.ID ? B.anomaly : null;
  const k = used && used.k != null ? +used.k : +(((D || {}).theta || {}).anomaly_k || 1);
  const L = anomLines(a, k);
  const note = ANOM_NOTE[a.ID] || "실제 관측값이 아니라 시나리오에 적용한 가정값입니다.";
  return `<div class="cmp-anom pane"><div class="fhd"><b>${esc(a.이름)}</b><span>적용한 가정 ${esc(gradeOf(a.등급) || "△")}${k !== 1 ? ` · 크기 조정 ×${k}` : ""}</span></div>` +
    `<p>${esc(anomLead(a))}</p>` +
    (L.length ? `<ul>${L.map(([x, y]) => `<li><span>${esc(x)}</span><b>${esc(y)}</b></li>`).join("")}</ul>` : "") +
    `<div class="hint">${esc(note)}</div></div>`;
}

function askSummary(C) {
  const { sc, A, B } = C;
  const E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const kv = (lab, v, u, sub, cls) => `<div class="k ${cls || ""}"><small>${lab}</small><b class="num">${v}${u ? `<u>${u}</u>` : ""}</b><span>${sub}</span></div>`;
  const unc = e => !e || e.lo95 == null || (e.lo95 <= 0 && e.hi95 >= 0);
  const r = E && E["순매출 (억)"], price = sc.kind === "anom" && /가격|인상/.test(sc.label);
  const big = r ? r.diff : (B.total - A.total) / 1.1 / 1e8;
  let h = `<section class="v2hero chero"><div class="hl"><div class="ov">선택한 상황의 체류 매출 변화 (B − A)</div>` +
    `<div class="line"><span class="big num${r && unc(r) ? " dim" : ""}">${v2Sign(big, 2)}<small>억</small></span>${r ? (unc(r) ? `<span class="unc-t">불확실 · 95% 구간이 0 포함</span>` : `<span class="pct num"><small>시드 ${n}쌍 평균 · 시드 반복에서 방향 일관</small></span>`) : `<span class="pct num"><small>시드 0 한 번</small></span>`}</div>` +
    `<div class="desc">${r ? `95% 구간 ${v2Sign(+r.lo95, 2)} ~ ${v2Sign(+r.hi95, 2)}억 · 같은 손님으로 반복 실행한 모델 변동 범위이며, 실제 효과의 확인이나 매출 예측 구간이 아닙니다` : "시드 0 한 번 계산이라 95% 구간이 없습니다. 이 차이에는 손님 생성의 우연이 섞여 있습니다."}</div>` +
    `<div class="chips"><span class="chip">A 기준 운영 · 지금 조건</span><span class="chip">B ${esc(sc.label)}</span>${sc.kind === "anom" ? `<span class="chip">${price ? "단가는 정한 값 · 손님 반응은 가정 △" : "상황의 크기는 가정 △"}</span>` : sc.kind === "seat" ? `<span class="chip">좌석만 바꾼 가정 실험</span>` : `<span class="chip">손님 구성이 달라 짝 비교 아님</span>`}</div></div><div class="kpis">`;
  const t = E && E["공급 제한 겪은 팀 (팀)"];
  if (t) h += kv("공급 제약 팀", unc(t) ? `<span class="unc-t">불확실</span>` : fmtD(t.diff).replace("-", "−"), unc(t) ? "" : "팀", `95% ${v2Sign(t.lo95, 0)} ~ ${v2Sign(t.hi95, 0)}팀 · 줄수록 좋음`);
  else { const c = X => (X.guests || []).filter(g => g.n_switch > 0).length; h += kv("공급 제약 팀", fmtD(c(B) - c(A)).replace("-", "−"), "팀", "시드 0 한 번"); }
  const top = askTopVenue({ ...C });
  if (top) {
    const m = (VEN_M[top] || []).find(x => / 이용 \(명\)$/.test(x[0]));
    const e = E && m ? E[m[0]] : null;
    // 10/17 QA Q4 — 업장을 짝 비교로 골랐을 때만 짝 비교 숫자를, 시드 0 으로 골랐으면 시드 0 숫자를 쓴다
    const d0 = ((B.venue_detail[top] || {}).persons_day || 0) - ((A.venue_detail[top] || {}).persons_day || 0);
    if (e && C.topWhy === "짝 비교 평균") h += kv("이용 변화가 가장 큰 업장", esc(shortName(top)), "", `${m[1]} ${fmtD(e.diff)}${m[2]} · 짝 비교 평균`);
    else if (Math.abs(d0) < 1) h += kv("이용 변화가 가장 큰 업장", "뚜렷한 변화 없음", "", "업장별 차이가 95% 구간 안");
    else h += kv("이용 변화가 가장 큰 업장", esc(shortName(top)), "", `이용 ${fmtD(d0)} 인 · 회 · 시드 0 한 번`);
  }
  if (!sc.popDiff) {
    const ga = Object.fromEntries((A.guests || []).map(g => [g.id, (g.acts || []).join("|")]));
    const diff = (B.guests || []).filter(g => g.id in ga && ga[g.id] !== (g.acts || []).join("|")).length;
    h += kv("행동이 달라진 팀", diff.toLocaleString(), "팀", `같은 손님 ${Object.keys(ga).length.toLocaleString()}팀 중 · 시드 0`);
  } else h += kv("영향 고객", "짝 비교 아님", "", sc.kind === "fair" ? "행사 날은 외부 손님이 더해져 구성이 다름" : "비 오는 날은 같은 손님이 약 3분의 2");
  return h + `</div></section>`;
}

// 10/17 8차 · 대표 띠 아래 세 줄 — 무엇이 바뀌었나 · 왜(넣은 조건) · 어느 수치가 불확실한가. 모두 이 비교의 계산값에서만
const askMetric = k => String(k).replace("공급 제한 겪은 팀 (팀)", "공급 제약 팀").replace("순매출 (억)", "체류 매출").replace(/ \((명|팀|억|판|잔|건|회)\)$/, "");
function askBrief(C) {
  const { sc, A, B } = C, E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const unc = e => !e || e.lo95 == null || (e.lo95 <= 0 && e.hi95 >= 0);
  const u = k => /억/.test(k) ? "억" : /\(팀\)/.test(k) ? "팀" : /이용 \(명\)/.test(k) ? " 인 · 회" : /\(판\)/.test(k) ? "판" : /\(잔\)/.test(k) ? "잔" : /\(건\)/.test(k) ? "건" : "명";
  let what, why, doubt;
  if (E) {
    const r = E["순매출 (억)"], t = E["공급 제한 겪은 팀 (팀)"];
    const mv = Object.entries(E).filter(([k, e]) => / 이용 \(명\)$/.test(k) && sureEffect(e, n)).sort((a, b) => Math.abs(b[1].diff) - Math.abs(a[1].diff)).slice(0, 3);
    what = `체류 매출 ${r ? (unc(r) ? "변화는 불확실" : `${v2Sign(r.diff, 2)}억`) : "-"} · 공급 제약 팀 ${t ? (unc(t) ? "변화는 불확실" : `${v2Sign(t.diff, 0)}팀`) : "-"}` +
      (mv.length ? ` · 시드 반복에서 방향이 일관된 이용 변화: ${mv.map(([k, e]) => `${askMetric(k)} ${v2Sign(e.diff, 0)}`).join(", ")} (인 · 회)` : " · 시드 흔들림보다 크게 이용이 바뀐 업장은 없습니다");
    const pri = k => /순매출/.test(k) ? 0 : /공급 제한/.test(k) ? 1 : / 이용 \(명\)$/.test(k) ? 2 : /^L\d|비중/.test(k) ? 9 : 5;
    const U = Object.entries(E).filter(([, e]) => unc(e)).sort((a, b) => pri(a[0]) - pri(b[0])).map(([k]) => askMetric(k).replace(/ \(%\)$/, " 비중"));
    doubt = U.length ? `95% 구간이 0을 포함해 방향을 말할 수 없는 지표 ${U.length}개: ${U.slice(0, 4).join(", ")}${U.length > 4 ? ` 외 ${U.length - 4}개` : ""}.` : `지표 ${Object.keys(E).length}개 모두 95% 구간이 0을 넘지 않습니다 (시드 반복에서 방향 일관).`;
    doubt += ` 시드 ${n}쌍 반복의 모델 변동 범위이며, 방향이 일관돼도 실제 호텔에서 검증된 효과는 아닙니다${sc.kind === "anom" ? " · 상황의 크기는 가정 △" : ""}.`;
  } else {
    what = `체류 매출 ${v2Sign((B.total - A.total) / 1.1 / 1e8, 2)}억 (시드 0 한 번)`;
    doubt = "시드 0 한 번 계산이라 모든 수치에 반복 범위가 없고, 손님 생성의 우연이 섞여 있습니다.";
  }
  if (sc.kind === "seat") { const ca = ((A.venue_detail || {}).THE_BUFFET || {}).cap, cb = ((B.venue_detail || {}).THE_BUFFET || {}).cap;
    why = `더뷔페 좌석만 ${ca || "-"}석 → ${cb || "-"}석으로 바꾼 가정 실험입니다. 다른 조건과 손님은 같고, 위 차이는 이 좌석 변화만으로 생긴 모델 결과입니다.`; }
  else if (sc.kind === "anom" && sc.a) { const used = B && B.anomaly && +B.anomaly.id === +sc.a.ID ? B.anomaly : null, k = used && used.k != null ? +used.k : 1;
    const L = anomLines(sc.a, k); why = `B에 넣은 조건: ${L.length ? L.slice(0, 3).map(([x, y]) => `${x} ${y}`).join(" · ") : anomLead(sc.a)}${L.length > 3 ? " 외" : ""}. 같은 손님으로 이 조건만 넣은 하루와 비교한 차이입니다.`; }
  else why = "B 하루에는 와인페어 손님이 더해져 손님 구성이 달라, 같은 손님끼리의 짝 비교가 아닙니다.";
  const row = (k, v) => `<div class="cb"><b>${k}</b><span>${v}</span></div>`;
  return `<section class="cbrief" aria-label="비교 요약">${row("무엇이 바뀌었나", esc(what))}${row("왜 바뀌었나", esc(why))}${row("불확실한 수치", esc(doubt))}</section>`;
}
// 줄어들어야 좋은 지표 (초과 수요 · 제한) — 색은 부호가 아니라 지표의 뜻으로 (10/16 UX 3-3)
const lowerBetter = lab => /초과|제한|대기/.test(lab);
const dirCls = (lab, d) => !d ? "" : ((d > 0) !== lowerBetter(lab) ? "up" : "down");
// 업장 상세 — 어떻게 달라졌나 · 언제 집중되나 · 누가 영향을 받나 · 현장에서 검토할 것
function askVenueDetail(C, loc) {
  if (!C || !loc) return "";
  const { sc, A, B, FA, FB } = C;
  const va = (A.venue_detail || {})[loc], vb = (B.venue_detail || {})[loc];
  const E = sc.band ? sc.band.effect || {} : {}, n = sc.band ? sc.band.seeds : 1;
  const nm = locName(loc);
  let h = `<div class="cmp-ven"><div class="cmp-vhead"><b>${esc(nm)}</b><span class="hint">${va || vb ? `좌석 ${va && vb && va.cap !== vb.cap ? `A ${va.cap}석 → B ${vb.cap}석` : `${(vb || va).cap}석`} (가정표)` : "좌석 · 회차를 모델이 추적하지 않는 시설"}</span><a class="go sub" data-open="venue:${loc}">업장 정보 · L4 상품 →</a></div><div class="cmp-grid">`;
  // ① 어떻게 달라졌나
  let t1 = "";
  const ms = (VEN_M[loc] || []).filter(([k]) => E[k]);
  if (ms.length) t1 += `<table class="t"><tr><th>짝 비교 (시드 ${n}쌍 평균)</th><th class="n">A</th><th class="n">B</th><th class="n">차이</th></tr>` + ms.map(([k, lab, u]) => {
    const e = E[k], s = sureEffect(e, n);
    return `<tr><td>${esc(lab)}</td><td class="n">${Math.round(sc.band.base[k].mean).toLocaleString()}${u}</td><td class="n">${Math.round(sc.band.comp[k].mean).toLocaleString()}${u}</td><td class="n ${s ? dirCls(lab, e.diff) : "flat"}">${s ? `${fmtD(e.diff)}${u}` : `<span title="95% 구간 ${Math.round(e.lo95)} ~ ${Math.round(e.hi95)}">뚜렷한 변화 확인 안 됨</span>`}</td></tr>`;
  }).join("") + `</table>`;
  if (va || vb) {
    const g = (v, k) => (v || {})[k] || 0;
    const row = (lab, a, b, u, f = x => Math.round(x).toLocaleString()) => `<tr><td>${lab}</td><td class="n">${f(a)}${u}</td><td class="n">${f(b)}${u}</td><td class="n ${dirCls(lab, b - a)}">${b === a ? "0" : (b > a ? "+" : "−") + f(Math.abs(b - a))}${u}</td></tr>`;
    t1 += `<table class="t"><tr><th>시드 0 한 번</th><th class="n">A</th><th class="n">B</th><th class="n">차이</th></tr>` +
      row("이용 팀", g(va, "parties"), g(vb, "parties"), "팀") + row("이용 (그 날 + 다음날 낮까지)", g(va, "persons_day"), g(vb, "persons_day"), " 인 · 회") +
      (g(va, "takeout_day") || g(vb, "takeout_day") ? row("포장", g(va, "takeout_day"), g(vb, "takeout_day"), "판") : "") +
      row("매출 (VAT 제외)", g(va, "krw") / 1.1 / 1e4, g(vb, "krw") / 1.1 / 1e4, "만원") + row("초과 수요 (막힌 팀의 일행 수)", g(va, "over_persons"), g(vb, "over_persons"), "명") +
      `<tr><td>가장 붐빈 회차</td><td class="n">${esc((va || {}).peak_window || "-")} ${g(va, "peak_day")}%</td><td class="n">${esc((vb || {}).peak_window || "-")} ${g(vb, "peak_day")}%</td><td></td></tr></table>`;
  } else {
    const pk = X => Math.max(0, ...(((X.present || {})[loc]) || [0]));
    t1 += `<table class="t"><tr><th>시드 0 한 번</th><th class="n">A</th><th class="n">B</th></tr><tr><td>같은 시각 최대 머문 인원</td><td class="n">${pk(A)}명</td><td class="n">${pk(B)}명</td></tr></table><div class="hint">이 시설은 좌석 · 매출을 업장 단위로 집계하지 않아 머문 인원만 보입니다.</div>`;
  }
  if (va || vb || ms.length) t1 += `<div class="hint">단위${noteI("인 · 회 = 식사 이용을 사람 수로 센 값(같은 손님이 두 번 먹으면 2). 팀 = 일행 단위. 둘 다 고유 손님 수가 아닙니다.")}</div>`;
  h += `<section class="pane"><h5>어떻게 달라졌나</h5>${t1}</section>`;
  // ② 언제 집중되나
  let t2;
  if (va || vb) {
    const ws = [...new Set([...((va || {}).windows || []), ...((vb || {}).windows || [])].filter(w => w.persons || w.over_persons).map(w => w.name))];
    const wf = (v, nmw) => ((v || {}).windows || []).find(w => w.name === nmw) || {};
    t2 = ws.length ? `<table class="t"><tr><th>회차</th><th class="n">A 착석 · 점유</th><th class="n">B 착석 · 점유</th><th class="n">B 초과 수요</th></tr>` + ws.map(x => { const a = wf(va, x), b = wf(vb, x);
      return `<tr><td>${esc(x.replace(" (익일)", " (다음날)"))}</td><td class="n">${a.persons || 0}명 · ${a.peak_pct || 0}%</td><td class="n">${b.persons || 0}명 · ${b.peak_pct || 0}%</td><td class="n ${b.over_persons ? "down" : ""}">${b.over_persons ? b.over_persons + "명" : "여유"}</td></tr>`; }).join("") + `</table><div class="hint">초과 수요 = 처음 막힌 회차에서 한 번${noteI("회차는 운영 창 기준이고, 한 창으로 여는 업장은 창 하나로 보입니다. 초과 수요는 자리가 없어 다른 선택을 한 팀의 일행 수이고, 팀마다 이 업장에서 처음 막힌 회차에 한 번만 셉니다.")}</div>`
      : `<div class="hint">이 날 이 업장의 회차 기록이 없습니다.</div>`;
  } else {
    const hr = X => { const a = ((X.present || {})[loc]) || []; const o = {}; a.forEach((v, i) => { const hh = 10 + Math.floor(i / 6); o[hh] = Math.max(o[hh] || 0, v); }); return o; };
    const ha = hr(A), hb = hr(B), hs = [...new Set([...Object.keys(ha), ...Object.keys(hb)])].filter(k => ha[k] || hb[k]).sort((x, y) => x - y);
    t2 = hs.length ? `<table class="t"><tr><th>시각</th><th class="n">A 최대 인원</th><th class="n">B 최대 인원</th></tr>${hs.map(k => `<tr><td>${String(k % 24).padStart(2, "0")}시${k >= 24 ? " (다음날)" : ""}</td><td class="n">${ha[k] || 0}</td><td class="n">${hb[k] || 0}</td></tr>`).join("")}</table>` : `<div class="hint">이 시설의 시간대 기록이 없습니다.</div>`;
  }
  h += `<section class="pane"><h5>언제 집중되나 <span class="hint">시드 0 한 번 · 짝 비교(시드 ${n}쌍 평균)와 기준이 다름</span></h5>${t2}</section>`;
  // ③ 누가 영향을 받나
  let t3 = "";
  if (va || vb) {
    const dif = k => { const a = (va || {})[k] || {}, b = (vb || {})[k] || {}; return [...new Set([...Object.keys(a), ...Object.keys(b)])].map(x => [x, a[x] || 0, b[x] || 0]).filter(r => r[1] !== r[2]).sort((x, y) => Math.abs(y[2] - y[1]) - Math.abs(x[2] - x[1])); };
    const rows = [...dif("by_guest"), ...dif("by_purpose").slice(0, 4)];
    t3 += rows.length ? `<table class="t"><tr><th>이용 팀 (시드 0)</th><th class="n">A</th><th class="n">B</th><th class="n">차이</th></tr>${rows.map(([k, a, b]) => `<tr><td>${esc(k)}</td><td class="n">${a}팀</td><td class="n">${b}팀</td><td class="n ${b > a ? "up" : "down"}">${b > a ? "+" : "−"}${Math.abs(b - a)}팀</td></tr>`).join("")}</table>` : `<div class="hint">투숙 여부 · 목적별 이용 팀 수가 같습니다.</div>`;
  }
  const w0 = locKey(loc).split(" ")[0];   // 10/19 서버 이름과 맞춤
  const hit = F => { const o = {}; for (const e of (F && F.events) || []) if (e.from && e.from.split(" ")[0] === w0) o[e.id] = o[e.id] || e; return o; };
  if (FA && FB && !sc.popDiff) {
    const a = hit(FA), b = hit(FB);
    const freed = Object.values(a).filter(e => !b[e.id]), added = Object.values(b).filter(e => !a[e.id]);
    // 10/16 UX P0-1 · 팀 번호에 이름표 (예전엔 숫자만 이어져 무엇인지 알 수 없었음)
    const lst = (L, key, lab) => L.length ? `<div class="cmp-gl"><div><b>${lab}</b> <span class="cnt">${L.length}팀</span></div><div class="tids"><span class="hint">팀 번호${L.length > 8 ? ` (앞 8팀)` : ""}</span>${L.slice(0, 8).map(e => `<a class="rlink tid" data-open="guest:${esc(key)}:${e.idx}" title="B 하루의 이 손님 보기">팀 #${esc(e.id.split("#")[1] || e.id)}</a>`).join("")}${L.length > 8 ? `<span class="hint">외 ${L.length - 8}팀</span>` : ""}</div></div>` : "";
    t3 += lst(freed, sc.bKey, "A에서 이 업장 좌석 제약을 겪었는데 B에서는 겪지 않은 팀") + lst(added, sc.bKey, "B에서 새로 이 업장 좌석 제약을 겪은 팀") ||
      `<div class="hint">이 업장에서 좌석 제약을 겪은 팀이 A · B 에서 같습니다.</div>`;
    t3 += `<div class="hint">팀 번호를 누르면 B 하루의 그 손님(선택 근거 포함)으로 갑니다. 브라우저 뒤로 가기로 이 화면에 돌아옵니다.</div>`;
  } else if (sc.popDiff) t3 += `<div class="hint">이 상황은 손님 구성이 달라 같은 손님끼리 짝지어 영향 고객을 고르지 않습니다.</div>`;
  h += `<section class="pane"><h5>누가 영향을 받나</h5>${t3}</section>`;
  // ④ 현장에서 검토할 것 — 확인된 조건 · 모델 결과 · 미검증 검토안을 나눠서
  const pv = prov("좌석 · 회차 · 운영 창") || {};
  const ob = (vb || {}).over_persons || 0;
  const wins = va || vb ? [...new Set(((vb || va).windows || []).filter(w => w.persons || w.over_persons).map(w => `${w.name.replace(" (익일)", "")} ${w.t0.slice(-5)}~${w.t1}`))] : [];
  const lay1 = va || vb ? `좌석 ${(va || vb).cap}석 · ${wins.slice(0, 6).join(", ")} <span class="gtxt">${esc(pv["등급"] || "△")}</span> <span class="hint">업장마다 공식 홈페이지 ◎ · 현장 · 추정 △ 이 섞여 있어 입력 출처표에서 확인</span>` : `좌석 · 회차 자료 없음`;
  const lay2 = ms.length ? ms.filter(([k]) => sureEffect(E[k], n)).map(([k, lab, u]) => `${lab} ${fmtD(E[k].diff)}${u}`).join(" · ") || "흔들림과 구분되는 변화 없음" : "짝 비교 지표 없음 (시드 0 표만)";
  const prop = [];
  if (sc.kind === "seat" && loc === "THE_BUFFET") prop.push("테라스 50석을 식사에 쓸 수 있는지(연회 · 인력 · 동선)를 먼저 확인", "좌석을 늘려도 2부에 몰리는 손님이 남으므로 1부 안내도 함께 검토");
  if (sc.kind === "anom" && sc.a && String(sc.a.이름).includes(shortName(loc))) prop.push("휴업 · 변경 공지와 대체 업장 안내 문구 준비");
  else if (sc.kind === "anom") prop.push("다른 업장에서 넘어올 손님을 받을 회차 · 좌석 여력 확인");
  if (ob > 0) prop.push("B 에서도 초과 수요가 남는 회차의 예약 분산 안내");
  if (sc.kind === "fair" && loc === "FOREST_PARK") prop.push("행사 시간대 입장 · 동선 안내 확인");
  const unsup = /GEUMRYONG|MYONGWOLGWAN/.test(loc) ? "별실 · 단체 수요는 모델이 따로 다루지 않습니다(모델 미지원)." : "";
  h += `<section class="cmp-check pane"><h5>현장에서 검토할 것</h5>
    <div class="lay"><span class="lt ok">확인된 운영 조건</span>${lay1}</div>
    <div class="lay"><span class="lt model">모델 계산 결과</span>${esc(lay2)}</div>
    <div class="lay"><span class="lt prop">미검증 검토안</span>${prop.length ? prop.map(esc).join(" · ") : "이 상황에서 이 업장에 대해 따로 제안할 조치가 없습니다"} <span class="hint">· 효과 미실험 · 현장 확인 필요</span></div>
    <div class="lay"><span class="lt need">필요한 현장 자료</span>${esc(venNeed(loc, sc))}${unsup ? ` <span class="hint">${esc(unsup)}</span>` : ""}</div>
    </section>`;
  h += `</div>` + askFlowNote(C, loc) + `</div>`;
  return h;
}
// 막힌 뒤 어디로 — 이 업장에서 이용이 제한된 식사의 최종 상태 (정산 기록)
function askFlowNote(C, loc) {
  const { FA, FB } = C; if (!FA || !FB) return "";
  const w0 = locKey(loc).split(" ")[0];   // 10/19 서버 이름과 맞춤
  const pick = F => { const o = {}; for (const [k, v] of Object.entries(F.flow || {})) if (k.split(" ")[0] === w0) for (const [x, n] of Object.entries(v)) o[x] = (o[x] || 0) + n; return o; };
  const a = pick(FA), b = pick(FB), ks = [...new Set([...Object.keys(a), ...Object.keys(b)])];
  if (!ks.length) return "";
  const ta = Object.values(a).reduce((x, y) => x + y, 0), tb = Object.values(b).reduce((x, y) => x + y, 0);
  const IN = k => !/호텔 밖|기록 없음/.test(k), inK = ks.filter(IN), col = k => /호텔 밖/.test(k) ? "out" : /기록 없음/.test(k) ? "none" : ["in1", "in2", "in3"][Math.min(2, inK.indexOf(k))];
  const order = [...inK, ...ks.filter(k => !IN(k))];
  const bar = (o, tot, lab) => `<div class="abar"><span class="abl">${lab} <b class="num">${tot}건</b></span><div class="stack">${order.filter(k => o[k]).map(k => `<i class="${col(k)}" style="flex:${o[k]}" title="${esc(outName(k))} ${o[k]}건"></i>`).join("")}</div><span class="abv num">호텔 안 ${pctS(inK.reduce((x, k) => x + (o[k] || 0), 0), tot)}%</span></div>`;
  return `<div class="cmp-flow pane"><h5>이 업장에서 막힌 식사는 어디로 갔나 <span class="hint">· 팀 · 식사마다 한 번 셈</span></h5>${bar(a, ta, "A")}${bar(b, tb, "B")}` +
    `<div class="leg">${order.map(k => `<span><i class="${col(k)}"></i>${esc(/호텔 밖/.test(k) ? "호텔 밖 또는 객실 식사 (모델에서 한 선택지)" : outName(k))}</span>`).join("")}</div><table class="t"><tr><th>최종</th><th class="n">A</th><th class="n">B</th></tr>${ks.map(k => `<tr><td>${esc(outName(k))}</td><td class="n">${a[k] || 0}건 · ${pctS(a[k] || 0, ta)}%</td><td class="n">${b[k] || 0}건 · ${pctS(b[k] || 0, tb)}%</td></tr>`).join("")}</table>` +
    `<div class="hint">'호텔 밖 또는 객실 식사' 는 모델에서 한 선택지${noteI("지금 모델은 '객실 식사' 와 '호텔 밖 식사' 를 한 선택지로 묶고 객실 키가 있는 투숙객만 고르게 합니다. 비투숙 손님에게 이 선택지가 없는 것은 모델 구조의 한계이지, 실제로 호텔 밖에 갈 수 없다는 뜻이 아닙니다.")}</div><a class="go sub" data-open="flow:${esc(C.sc.bKey)}">B 하루의 막힌 곳 → 최종 흐름 (고객 흐름) →</a></div>`;
}
// 10/17 UX 11차 · ⑤ 고객별 — 투숙 · 비투숙 · 방문 목적별 이용 팀 (업장별 venue_detail · 시드 0) + 짝 비교의 비투숙 팀 지표
function askByGuest(C) {
  const { sc, A, B } = C, E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const va = A.venue_detail || {}, vb = B.venue_detail || {};
  let h = "";
  if (E) {
    const ks = Object.keys(E).filter(k => !/^L\d/.test(k) && / 비투숙 팀 \(팀\)$| \(%\)$/.test(k));
    if (ks.length) h += `<table class="t"><tr><th>짝 비교 (시드 ${n}쌍 평균)</th><th class="n">A</th><th class="n">B</th><th class="n">B − A</th></tr>` + ks.map(k => { const e = E[k], s = sureEffect(e, n), pct = / \(%\)$/.test(k), f = v => pct ? (+v).toFixed(1) + "%" : Math.round(v).toLocaleString() + "팀";
      return `<tr><td>${esc(k.replace(/ \(팀\)$/, "").replace(/ \(%\)$/, " 비중"))}</td><td class="n">${f(sc.band.base[k].mean)}</td><td class="n">${f(sc.band.comp[k].mean)}</td><td class="n ${s ? (e.diff > 0 ? "up" : "down") : "flat"}">${s ? (pct ? v2Sign(e.diff, 1) + "%p" : fmtD(e.diff) + "팀") : `<span title="95% 구간 ${(+e.lo95).toFixed(1)} ~ ${(+e.hi95).toFixed(1)}">뚜렷한 변화 확인 안 됨</span>`}</td></tr>`; }).join("") + `</table>`;
  }
  // 업장 × 고객군 (투숙 · 비투숙 · 목적) 이용 팀 차이 — 시드 0 한 번, 차이가 큰 순 12줄
  const rows = [];
  for (const loc of new Set([...Object.keys(va), ...Object.keys(vb)])) for (const key of ["by_guest", "by_purpose"]) {
    const a = (va[loc] || {})[key] || {}, b = (vb[loc] || {})[key] || {};
    for (const g of new Set([...Object.keys(a), ...Object.keys(b)])) if ((a[g] || 0) !== (b[g] || 0)) rows.push([shortName(loc), g, a[g] || 0, b[g] || 0]);
  }
  rows.sort((x, y) => Math.abs(y[3] - y[2]) - Math.abs(x[3] - x[2]));
  h += rows.length ? `<table class="t"><tr><th>업장 · 고객군 (시드 0 한 번)</th><th class="n">A</th><th class="n">B</th><th class="n">B − A</th></tr>` +
    rows.slice(0, 12).map(([l, g, a, b]) => `<tr><td>${esc(l)} · ${esc(g)}</td><td class="n">${a}팀</td><td class="n">${b}팀</td><td class="n ${b > a ? "up" : "down"}">${fmtD(b - a)}팀</td></tr>`).join("") + `</table>` +
    (rows.length > 12 ? `<div class="hint">차이가 큰 12줄만 보입니다 (전체 ${rows.length}줄).</div>` : "") : `<div class="hint">투숙 여부 · 목적별 이용 팀 수가 A · B 에서 같습니다.</div>`;
  h += `<div class="hint">시드 0 한 번 · 반복 범위 없음${noteI(`팀 = 그 업장을 이용한 일행 단위. 시드 0 한 번 계산이라 반복 범위가 없습니다. 같은 손님끼리의 비교${sc.popDiff ? "가 아닙니다 (손님 구성이 다름)" : "입니다"}.`)}</div>`;
  return h;
}
// 10/17 UX 11차 · ⑤ 시간대별 — 식당(좌석을 추적하는 업장) 안 인원의 시각별 합 A · B (10분 격자 중 그 시간대 최대)
function askByHour(C) {
  const { A, B } = C, locs = Object.keys(VEN_M);
  const hr = X => { const o = {}; for (const loc of locs) { const a = ((X.present || {})[loc]) || []; a.forEach((v, i) => { const hh = 10 + Math.floor(i / 6); o[hh] = (o[hh] || 0) + v; }); } return o; };
  // 10분 격자 6칸의 합을 시간대 합으로 쓰면 여섯 배가 되므로, 칸별 합의 최대를 쓴다
  const hrMax = X => { const o = {}; for (const loc of locs) { const a = ((X.present || {})[loc]) || []; a.forEach((v, i) => { const hh = 10 + Math.floor(i / 6), j = i % 6; o[hh] = o[hh] || [0, 0, 0, 0, 0, 0]; o[hh][j] += v; }); } return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Math.max(...v)])); };
  const ha = hrMax(A), hb = hrMax(B), hs = [...new Set([...Object.keys(ha), ...Object.keys(hb)])].filter(k => ha[k] || hb[k]).sort((x, y) => x - y);
  if (!hs.length) return `<div class="hint">시간대 기록이 없습니다.</div>`;
  const mx = Math.max(1, ...hs.map(k => Math.max(ha[k] || 0, hb[k] || 0)));
  const chart = hs.map(k => `<div class="fw"><span class="fn">${String(k % 24).padStart(2, "0")}시${k >= 24 ? " (다음날)" : ""}</span><span class="fb"><i class="fa" style="width:${((ha[k] || 0) / mx * 100).toFixed(1)}%"></i><i class="fbb" style="width:${((hb[k] || 0) / mx * 100).toFixed(1)}%"></i></span><span class="fv num">A ${(ha[k] || 0).toLocaleString()} · B ${(hb[k] || 0).toLocaleString()}명</span><span class="fo num ${(hb[k] || 0) - (ha[k] || 0) ? ((hb[k] || 0) > (ha[k] || 0) ? "" : "") : ""}">${(hb[k] || 0) - (ha[k] || 0) ? fmtD((hb[k] || 0) - (ha[k] || 0)) + "명" : ""}</span></div>`).join("");
  return `<div class="cfocus"><span class="lg"><i class="fa"></i>A 기준 운영<i class="fbb"></i>B 변경 운영</span><div class="fchart">${chart}</div>${capN("식당 안 인원의 합 · 시간대 최대 · 시드 0", `${locs.map(l => (VEN_M[l][0] || [""])[0].split(" ")[0]).join(" · ")} 안에 같은 시각 머문 인원의 합이고, 그 시간대의 최댓값입니다. 시드 0 한 번 계산이며 식당이 아닌 시설(수영장 · 라운지 등)은 포함하지 않습니다.`)}</div>`;
}
// 다른 업장으로의 파급 — 짝 비교의 업장별 이용 변화
function askSpill(C) {
  const { sc, A, B } = C;
  const E = sc.band ? sc.band.effect || {} : null, n = sc.band ? sc.band.seeds : 1;
  const items = [];
  for (const [loc, ms] of Object.entries(VEN_M)) {
    const m = ms[0]; if (!m) continue;
    if (E && E[m[0]]) items.push({ loc, d: E[m[0]].diff, a: sc.band.base[m[0]].mean, b: sc.band.comp[m[0]].mean, u: m[2], sure: sureEffect(E[m[0]], n), lab: m[1] });
    else if (!E) { const pa = ((A.venue_detail || {})[loc] || {}).persons_day || 0, pb = ((B.venue_detail || {})[loc] || {}).persons_day || 0; if (pa || pb) items.push({ loc, d: pb - pa, a: pa, b: pb, u: "명", sure: null, lab: "이용 인원 (시드 0)" }); }
  }
  if (!items.length) return "";
  // 단위가 업장마다 달라(인 · 회 · 판 · 잔 · 건) 막대는 A 대비 변화율로 그린다. 값은 그 업장 단위의 차이
  const rel = x => x.a ? x.d / x.a * 100 : 0, mx = Math.max(5, ...items.map(x => Math.abs(rel(x))));
  return `<section class="v2s cmp-spill"><div class="sh"><h2>다른 업장으로의 파급</h2><span class="s">${E ? `짝 비교 시드 ${n}쌍 평균` : "시드 0 한 번 · 반복 범위 없음"} · 막대 = A 대비 변화율 · 줄을 누르면 위 업장이 바뀝니다</span></div><div class="pane">` +
    `<div class="sph"><span>업장</span><span>A 대비 변화율</span><span>차이</span><span>A → B</span></div>` +
    items.map(x => { const p = rel(x), w = Math.abs(p) / mx * 50;
      return `<button class="sprow ${x.loc === ASK.venue ? "on" : ""} ${x.sure === false ? "weak" : ""}" data-sv="${x.loc}" title="${esc(x.lab)}"><span class="nm">${vdot(x.loc)}${esc(shortName(x.loc))}</span>` +
        `<span class="dv"><i class="z" style="left:50%"></i><i class="b ${x.sure === false ? "unc" : x.d >= 0 ? "pos" : "neg"}" style="left:${(p >= 0 ? 50 : 50 - w).toFixed(2)}%;width:${Math.max(.6, w).toFixed(2)}%"></i></span>` +
        `<span class="v num">${x.sure === false ? `<b class="unc-t" title="95% 구간이 0 포함">불확실</b>` : `${fmtD(x.d).replace("-", "−")}${x.u}`}</span><span class="ab num">${Math.round(x.a).toLocaleString()} → ${Math.round(x.b).toLocaleString()}${x.u}</span></button>`; }).join("") +
    `${capN("불확실 = 95% 구간이 0 포함 · 단위는 업장마다 다름", "불확실 = 95% 구간이 0을 포함해 시드 흔들림과 구분되지 않는 변화. 숫자로 보이는 변화는 시드 반복에서 방향이 일관됐다는 뜻이며 실제 효과 검증은 아닙니다. 단위는 업장마다 다릅니다(인 · 회 · 판 · 잔 · 건).")}</div></section>`;
}

// 이동 — 다른 화면으로 갈 때는 기록을 남겨 브라우저 뒤로 가기로 이 상태에 돌아오게
function askHist() { try { history.replaceState({ mode: "ask", ask: { scn: ASK.scn, venue: ASK.venue, open: ASK.open } }, ""); } catch (e) {} }
function askPush() { try { history.pushState({ mode: MODE, ask: { scn: ASK.scn, venue: ASK.venue, open: ASK.open } }, ""); } catch (e) {} }
async function askOpen(go) {
  const [fn, ...r] = go.split(":"), arg = r.join(":");
  askHist(); askPush();
  if (fn === "venue") return placePanel(arg);
  if (fn === "day") { setMode("day"); return loadDay(arg); }
  if (fn === "flow") { setMode("day"); await loadDay(arg); return showFlow(); }
  if (fn === "guest") { const [key, idx] = [r.slice(0, -1).join(":"), +r[r.length - 1]]; setMode("day"); await loadDay(key); return openDayGuest(idx, null); }
}
window.addEventListener("popstate", e => {
  const s = e.state; if (!s || !s.mode) return;
  if (s.ask) Object.assign(ASK, s.ask);
  if (s.mode === "ask") { if (ASK.cur && ASK.cur.D) DAY = ASK.cur.D; setMode("ask"); }
  else if (s.mode !== MODE) setMode(s.mode);
});

function askAssist() {
  const C = ASK.cur; if (!C || MODE !== "ask") return;
  $("#panel").innerHTML = `<div class="as-panel" id="askAssist"></div>`;
  if (!C.sc || !C.A || !C.B) {
    assistSet(null, "askAssist");
    $("#askAssist").innerHTML = `<div class="as-head"><b>힐링크 운영 어시스턴트</b></div><div class="as-ctx"><small>지금 보고 있는 날짜</small><div>${esc(C.D.date.slice(5).replace("-", "/"))} · 상황 비교</div></div><p class="hint">상황을 선택하고 계산을 마치면 이 날짜의 비교 결과에 대해 질문할 수 있습니다.</p>`;
    return;
  }
  assistSet({ page: "ask", D: C.D, sc: C.sc, A: C.A, B: C.B, FA: C.FA, FB: C.FB, venue: ASK.venue, AB: C.sc && C.sc.kind === "seat" ? C.sc.band : null, ANOM: [] }, "askAssist");
}
