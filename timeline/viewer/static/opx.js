// 운영 실험 (CL-1024-17 · CL-1024-18 보완) — 운영자가 상품 조건을 바꾸고, 동결 정량 엔진(Codex CD-1024-15 실행 인터페이스)이 다시 계산한 고객별 선택을 본다.
//   무엇을 바꿨나 → 누가 선택을 바꿨나 → 어느 업장으로 옮겼나(지도 영향 레이어) → 왜 달라졌나
//   · 실행할 때마다 서버(/api/opx/run → opx_run.py)가 엔진을 기준선 · 시나리오 두 번 실제로 계산한다. 화면 · 지도는 저장된 결과를 고르지 않고 숫자를 따로 세지 않는다.
//   · 지도는 '운영 실험 영향 표시'다 — 실제 이동 궤적 · 방문객 수 · 혼잡도가 아니며, 기존 고객흐름 지도(#map) · 아바타 · 하루 일정은 건드리지 않는다(별도 SVG).
//   · 가상 고객 11명의 조건부 결과 — 호텔 전체 수요 · 매출 · 선택 확률이 아니다.
const OPX = { meta: null, form: null, last: null, lastForm: null, sel: null, busy: false, runs: [], err: null, lastAt: null };
const OPX_VENUE = { GEUMRYONG: "금룡", THE_BUFFET: "더뷔페", PIZZA_HILL: "피자힐", ROOM_MEAL: "룸서비스", MYONGWOLGWAN: "명월관", ONDAL: "온달", MOEGI: "모에기", LE_PASSAGE: "르파사쥬" };
const OPX_REASON = {
  outside_validity_window: "상품 판매 기간 밖", outside_or_exceeds_session: "이 시각 · 이용 시간이 확인된 판매 회차와 맞지 않음",
  reservation_not_assumed_available: "예약 조건 충족을 가정하지 않음", seat_type_mismatch: "좌석 조건과 맞지 않음",
  child_price_or_adult_child_composition_unverified: "아동 요금 자료 미확인", offer_data_partial: "상품 자료 일부만 확인",
  price_or_basis_missing: "가격 · 가격 기준 자료 없음", source_provenance_missing: "공식 출처 확인 전", stay_required: "투숙객 대상 상품",
  party_below_minimum: "최소 인원 미만", party_above_maximum: "최대 인원 초과", day_of_week_mismatch: "요일 조건과 맞지 않음",
  public_holiday_excluded: "공휴일 제외 상품", no_matching_session_rule: "이 요일의 회차 자료 없음", meal_period_mismatch: "저녁 상품 아님",
  scenario_not_enabled: "가상 상품(이번 실험에서 끔)", unknown_verification_status: "검증 상태 미상",
};
const OPX_ELIG = { ELIGIBLE: "점수 비교", INELIGIBLE: "조건 불충족", INSUFFICIENT_DATA: "자료 부족" };
const OPX_STATUS = { COMPLETED: "엔진 재계산 완료", NO_ELIGIBLE_OFFERS: "선택 계산 불가 — 이 조건에서 적격 후보가 없습니다", INVALID_REQUEST: "입력을 확인해 주세요",
  ENGINE_SHA_MISMATCH: "엔진 파일이 CD-15 기준과 달라 계산하지 않았습니다", LOCAL_INPUT_UNAVAILABLE: "로컬 전용 프로필 입력이 없어 계산할 수 없습니다",
  OUTPUT_PRIVACY_BLOCKED: "결과에 비공개 문자열이 있어 표시하지 않았습니다", BLOCKED_ENGINE_RUN: "엔진 실행이 차단됐습니다", BLOCKED_ENGINE_MAPPING: "상품 ↔ 엔진 연결 누락" };
const OPX_KIND = { profile: "후기 근거", profile_and_offer: "후기 근거 × 상품", context: "공통(가격 · 끼니)", assumption: "설계 가정" };
const opxW = n => (n == null ? "-" : Math.round(n).toLocaleString("ko-KR"));
const opxV = id => OPX_VENUE[id] || id;
const opxF = (x, d = 3) => (x == null ? "-" : (+x).toFixed(d));
const opxSgn = (x, d = 2) => (x == null ? "-" : (x > 0 ? "+" : x < 0 ? "−" : "±") + Math.abs(x).toFixed(d));
const OPX_NAR = `<i class="ox-nar" title="1 · 2위 점수 차 0.01 이하 · 경계 사례">근소</i>`;

async function opxEnter() {
  const v = $("#opxView");
  try { await revInit(); await revEnter(); } catch(e) { REV.err = e.message; }
  if (!OPX.meta) {
    v.innerHTML = `<div class="ox-load">운영 실험 준비 중…</div>`;
    try { OPX.meta = await api("/api/opx/meta"); }
    catch (e) { v.innerHTML = `<div class="ox-load">운영 실험을 열 수 없습니다 — ${esc(String(e.message || e))}</div>`; return; }
    OPX.form = { ...OPX.meta.default };
    try { if (typeof libLoad === "function") await libLoad(); } catch (e) {}
    if (typeof AG !== "undefined" && !AG.avm) { try { const r = await fetch("/static/avatars/manifest.json", { cache: "no-cache" }); AG.avm = r.ok ? await r.json() : {}; } catch (e) { AG.avm = {}; } }
  }
  opxRender();
}

function opxTarget(id) { return ((OPX.meta && OPX.meta.target_offers) || []).find(o => o.offer_id === id) || {}; }
function opxType(pid) {
  try { const p = LIBV.data.personas.find(x => x.id === pid); const f = LIB_TYPE_FIX[pid]; return (f && f.label) || (p && libTypeOf(p)) || ""; } catch (e) { return ""; }
}
function opxAv(pid, size = 30) { try { return agAvatarIcon(pid, 2, size); } catch (e) { return ""; } }
function opxChanged() {   // 마지막 실행과 다른 입력 필드
  if (!OPX.lastForm) return [];
  return Object.keys(OPX.form).filter(k => OPX.form[k] !== OPX.lastForm[k]);
}
function opxCalc(f) {
  const party = (f.adults || 0) + (f.children || 0), t = opxTarget(f.target_offer), pp = f.discount_unit === "per_party" ? f.discount_amount / Math.max(party, 1) : f.discount_amount;
  return { party, pp, team: pp * party, price: t.price_amount, after: t.price_amount != null ? t.price_amount - pp : null };
}
// CL-18 §1 — 적격 후보 수로 결과의 성격을 나눈다: 2개 이상 = 경쟁 선택 · 1개 = 단일 후보(경쟁 선택 아님) · 0개 = 계산 불가
function opxMode(R) {
  if (!R || !R.experiment) return null;
  const el = (R.eligibility || []).filter(x => x.eligibility_status === "ELIGIBLE");
  const n = R.experiment.run_status === "COMPLETED" ? (R.experiment.selected_offer_ids || el.map(x => x.offer_id)).length : (R.experiment.run_status === "NO_ELIGIBLE_OFFERS" ? 0 : null);
  return { n, kind: n == null ? "error" : n >= 2 ? "compete" : n === 1 ? "single" : "none", eligible: el };
}
function opxStatus() {   // 실행 버튼 옆 상태 — 실행 전 · 조건 변경 · 계산 중 · 완료 · 단일 후보 · 계산 불가 · 오류
  const ch = opxChanged().length, R = OPX.last, m = opxMode(R);
  if (OPX.busy) return { k: "busy", t: "엔진 계산 중 — 기준선 · 시나리오 계산" };
  if (OPX.err) return { k: "err", t: "실행 실패" };
  if (!R) return { k: "idle", t: "아직 실행 전" };
  if (ch) return { k: "chg", t: `조건 ${ch}개 변경 · 아직 실행 전 — 화면은 이전 결과` };
  const at = OPX.lastAt ? ` · ${OPX.lastAt}` : "";
  if (R.experiment.run_status !== "COMPLETED") return { k: m && m.kind === "none" ? "none" : "err", t: (m && m.kind === "none" ? "계산 불가 · 적격 후보 0개" : OPX_STATUS[R.experiment.run_status] || R.experiment.run_status) + at };
  if (m.kind === "single") return { k: "single", t: `계산 완료 · 단일 후보(제한적 결과)${at}` };
  return { k: "ok", t: `계산 완료 · 경쟁 후보 ${m.n}개${at}` };
}

function opxRender() {
  const v = $("#opxView"); if (!v) return;
  const sc = (document.getElementById("oxLs") || {}).scrollTop || 0, cc = (document.getElementById("oxC") || {}).scrollTop || 0;
  v.innerHTML = `<div id="revenueContent">${revHTML()}</div><details class="rev-product" id="revProduct"${OPX.productOpen ? " open" : ""}><summary>상품 조건 실험 · 금룡·더뷔페 선택 비교 <small>(하루 매출과 별도 계산)</small></summary>${opxGuide()}<div class="ox"><aside class="ox-l">${opxLeft()}</aside><section class="ox-c" id="oxC">${opxCenter()}</section><aside class="ox-r" id="oxR">${opxRight()}</aside></div></details>`;
  const ls = document.getElementById("oxLs"); if (ls) ls.scrollTop = sc; const c = document.getElementById("oxC"); if (c) c.scrollTop = cc;
  opxWire(); revWire();
  const product = document.getElementById("revProduct");
  if (product) product.ontoggle = () => { OPX.productOpen = product.open; if (product.open && !OPX.last && !OPX.busy) opxRun(); };
}

// CL-1025-37 P2 — 첫 화면 안내: 누구를 대상으로 · 어떤 조건을 · 결과를 어디서 보나 + 운영 레버 지원 등급(코드 확인 기준)
const OPX_LEVERS = [
  ["저녁 가상 할인 · 금룡 / 더뷔페(1인 · 팀)", "지원", "이 화면 — 동결 정량 엔진이 기준선 · 시나리오를 매번 실제 계산"],
  ["와인페어 있음 / 없음", "지원 · 저장본 있음", "고객 흐름 — 한 명 11명 × 있음/없음 · 여러 명 5명 / 11명 저장된 실행"],
  ["와인페어 투숙객 할인 · 안주 + 무알코올", "지원(근거 계산)", "행동근거 — 턴 엔진 비교 계산 · 하루 지도 저장본 없음"],
  ["수용량 · 대기 · 만석 · 포장", "연구 중", "이번 엔진에 반영하지 않음 — 결과를 만들지 않음"],
];
function opxGuide() {
  const n = ((OPX.meta && OPX.meta.personas) || []).length;
  return `<div class="ox-guide"><div class="oxg-3"><div><i>1</i><b>누구를 대상으로</b><span>실행 검증 고객 ${n}명(같은 조건 · 각자 판단)</span></div><div><i>2</i><b>어떤 조건을</b><span>업장 · 할인 금액 · 날짜 · 인원 · 투숙</span></div><div><i>3</i><b>결과는 어디서</b><span>선택이 바뀐 고객 · 업장별 지도 · 고객별 이유</span></div></div>
    <details class="oxg-lv"><summary>운영 레버 지원 범위</summary><table><tbody>${OPX_LEVERS.map(([a, b, c]) => `<tr><td>${esc(a)}</td><td><em class="lv-${b.startsWith("지원") ? "ok" : "rs"}">${esc(b)}</em></td><td>${esc(c)}</td></tr>`).join("")}</tbody></table></details></div>`;
}
function opxLeft() {
  const f = OPX.form, ch = new Set(opxChanged()), c = opxCalc(f), t = opxTarget(f.target_offer), m = OPX.meta, st = opxStatus();
  const cls = k => ch.has(k) ? " ox-chg" : "";
  const seg = (k, opts) => `<div class="cf-seg${cls(k)}" data-k="${k}">${opts.map(([val, lab]) => `<button type="button" data-v="${val}" class="${String(f[k]) === String(val) ? "on" : ""}">${lab}</button>`).join("")}</div>`;
  const step = (k, lab, min, max) => `<div class="ox-step${cls(k)}"><span>${lab}</span><button type="button" data-k="${k}" data-d="-1" ${f[k] <= min ? "disabled" : ""}>−</button><b>${f[k]}</b><button type="button" data-k="${k}" data-d="1" ${f[k] >= max ? "disabled" : ""}>+</button></div>`;
  const ok = (m.integrity || {}).ok;
  // CL-18 §1 — 조건 목록만 스크롤하고, 실행 버튼 · 상태는 패널 아래에 고정(1440 × 900 첫 화면에서 보임)
  return `<div class="ox-ls" id="oxLs"><div class="ox-h"><h2>운영 조건</h2><p>저녁 · 실행 검증 고객 ${m.personas.length}명${document.body.classList.contains("devmode") ? ` · 동결 엔진 ${esc((m.integrity.engine_head || "").slice(0, 7))}` : ""}${ok ? "" : " · <b class='ox-bad'>엔진 SHA 불일치</b>"}</p></div>
    <div class="ox-grp ox-disc"><div class="ox-lab">가상 할인 <span class="ox-vtag">가상 · 실제 혜택 아님</span></div>
      <div class="ox-mini">조절할 상품</div>${seg("target_offer", m.target_offers.map(o => [o.offer_id, opxV(o.venue_id)]))}
      <div class="ox-amt${cls("discount_amount")}"><input type="range" id="oxRng" min="0" max="${Math.min(100000, t.price_amount || 100000)}" step="1000" value="${Math.min(f.discount_amount, 100000)}" aria-label="할인 금액"><div class="ox-amtin"><input class="cf-input" type="number" id="oxAmt" min="0" step="1000" value="${f.discount_amount}" aria-label="할인 금액(원)"><span>원</span></div></div>
      <div class="ox-mini">할인 단위</div>${seg("discount_unit", [["per_person", "1인"], ["per_party", "팀 전체"]])}
      <div class="ox-calc">${f.discount_amount ? `1인 ${opxW(c.pp)}원 · ${c.party}명 팀 ${opxW(c.team)}원 반영<br>${esc(opxV(t.venue_id))} ${opxW(c.price)} → <b>${opxW(c.after)}원/인</b>` : `${esc(opxV(t.venue_id))} 기준 가격 ${opxW(c.price)}원/인 · 할인 없음`}</div></div>
    <div class="ox-grp"><div class="ox-lab">날짜 · 시간</div>
      <input class="cf-input${cls("date")}" type="date" id="oxDate" value="${esc(f.date)}" aria-label="날짜">
      <div class="ox-row2"><input class="cf-input${cls("start_time")}" type="time" id="oxTime" value="${esc(f.start_time)}" step="300" aria-label="시작 시각"><select class="cf-input${cls("duration_minutes")}" id="oxDur" aria-label="이용 시간">${[60, 90, 120].map(x => `<option value="${x}" ${f.duration_minutes === x ? "selected" : ""}>${x}분 이용</option>`).join("")}</select></div>
      <label class="cf-switch${cls("holiday")}"><input type="checkbox" id="oxHol" ${f.holiday ? "checked" : ""}>공휴일</label></div>
    <div class="ox-grp"><div class="ox-lab">인원 · 투숙</div>${step("adults", "성인", 0, 8)}${step("children", "아동", 0, 8)}
      ${seg("stay_status", [["staying", "투숙"], ["non_staying", "비투숙"], ["unknown", "미정"]])}</div>
    <div class="ox-grp"><div class="ox-lab">좌석 · 예약</div>${seg("seat_type", [["hall", "Hall"], ["private_room", "별실"]])}
      <label class="cf-switch${cls("reservation")}"><input type="checkbox" id="oxRes" ${f.reservation ? "checked" : ""}>예약 조건 충족 가정</label>
      <div class="ox-note">실시간 좌석 · 예약 조회가 아닌 운영자 가정입니다.</div></div>
    ${OPX.runs.length ? `<div class="ox-grp"><div class="ox-lab">실행 기록</div><ol class="ox-hist">${OPX.runs.slice(-6).reverse().map(r => `<li>${esc(r.label)}<span>${esc(r.counts)}</span></li>`).join("")}</ol></div>` : ""}</div>
    <div class="ox-run"><div class="ox-st ox-st-${st.k}" id="oxSt" role="status">${esc(st.t)}</div>
      <button type="button" class="cf-btn cf-primary" id="oxRun" ${OPX.busy ? "disabled" : ""}>${OPX.busy ? "엔진 계산 중…" : ch.size ? "변경 조건으로 실행" : "시나리오 실행"}</button>
      <button type="button" class="cf-link" id="oxReset">기본 조건으로</button></div>`;
}

function opxDiscLabel(req) {
  const ov = req && req.offer_overrides ? Object.entries(req.offer_overrides)[0] : null;
  if (!ov) return "할인 없음(기준선과 같은 조건)";
  const [oid, o] = ov, t = opxTarget(oid), party = req.party_size, pp = o.discount_unit === "per_party" ? o.discount_amount / party : o.discount_amount;
  return `${opxV(t.venue_id || oid)} ${o.discount_unit === "per_party" ? `팀 전체 ${opxW(o.discount_amount)}원(1인 ${opxW(pp)}원)` : `1인 ${opxW(o.discount_amount)}원`} 가상 할인`;
}
function opxFormLabel(f) {
  if (!f.discount_amount) return `할인 없음${f.seat_type !== "hall" ? " · 별실" : ""} · ${f.date.slice(5)} ${f.start_time}`;
  return `${opxV(opxTarget(f.target_offer).venue_id || f.target_offer)} ${f.discount_unit === "per_party" ? "팀" : "1인"} ${opxW(f.discount_amount)}원${f.adults !== 2 || f.children ? ` · ${f.adults + f.children}명` : ""}${f.seat_type !== "hall" ? " · 별실" : ""}${f.date !== OPX.meta.default.date || f.start_time !== OPX.meta.default.start_time ? ` · ${f.date.slice(5)} ${f.start_time}` : ""}`;
}
function opxCondLine(req) {
  return `${esc(req.simulation_date)} ${esc(req.start_time)} · ${req.duration_minutes}분 · ${req.party_composition.adults ? `성인 ${req.party_composition.adults}` : ""}${req.party_composition.children ? ` · 아동 ${req.party_composition.children}` : ""} · ${{ staying: "투숙", non_staying: "비투숙", unknown: "투숙 미정" }[req.stay_status]} · ${req.seat_type === "hall" ? "Hall" : "별실"} · ${req.reservation_assumption ? "예약 조건 충족 가정" : "예약 가정 없음"}`;
}
// 조절 대상 두 상품(금룡 · 더뷔페)의 적격성 사유 — 단일 후보 · 후보 없음 설명에 쓴다
function opxTargetsElig(R) {
  return ((OPX.meta && OPX.meta.target_offers) || []).map(t => { const e = (R.eligibility || []).find(x => x.offer_id === t.offer_id) || {}; return { id: t.offer_id, venue: t.venue_id, st: e.eligibility_status, why: (e.reasons || []).map(r => OPX_REASON[r] || r).join(" · ") }; });
}

function opxCenter() {
  const R = OPX.last;
  if (OPX.err) return `<div class="ox-empty ox-bad">${esc(OPX.err)}</div>`;
  if (!R) return `<div class="ox-empty">${OPX.busy ? "엔진이 기준선과 시나리오를 계산하고 있습니다…" : "조건을 정하고 '시나리오 실행'을 누르세요."}</div>`;
  const st = R.experiment.run_status, req = (R.adapter && R.adapter.normalized_request) || (OPX.lastForm ? null : null);
  const elig = R.eligibility || [], md = opxMode(R);
  const eligTbl = `<details class="ox-det"><summary>상품 적격성 — 점수 비교 ${elig.filter(x => x.eligibility_status === "ELIGIBLE").length}개 · 제외 ${elig.filter(x => x.eligibility_status !== "ELIGIBLE").length}개</summary>
    <table class="ox-tbl"><thead><tr><th>업장 · 상품</th><th>상태</th><th>사유</th></tr></thead><tbody>${elig.map(x => `<tr><td><b>${esc(opxV(x.venue_id))}</b> <span class="ox-sub">${esc(x.offer_name)}</span></td><td class="ox-e-${x.eligibility_status}">${OPX_ELIG[x.eligibility_status] || x.eligibility_status}</td><td>${x.reasons.length ? x.reasons.map(r => esc(OPX_REASON[r] || r)).join(" · ") : `${x.price_amount != null ? `${opxW(x.price_amount)}원 · ` : ""}가격 · 조건 확인됨`}</td></tr>`).join("")}</tbody></table>
    <p class="ox-foot">자료 부족 · 조건 불충족 상품은 이번 시나리오의 가격 · 회차 · 체류 조건으로 적격성을 입증하지 못했다는 뜻이며, 업장이 영업하지 않는다거나 실제 예약이 불가능하다는 뜻이 아닙니다.</p></details>`;
  if (st !== "COMPLETED") {
    const te = opxTargetsElig(R);
    return `<div class="ox-what"><div class="ox-k">실행 결과</div><h3>${esc(OPX_STATUS[st] || st)}</h3>${R.error ? `<p>${esc(R.error)}</p>` : ""}${md && md.kind === "none" && OPX.lastForm ? `<p>${esc(opxFormLabel(OPX.lastForm))}</p>` : ""}</div>
      ${md && md.kind === "none" ? `<div class="ox-mode ox-mode-none"><b>적격 후보 0개 — 선택을 계산하지 않았습니다</b><ul>${te.map(x => `<li><b>${esc(opxV(x.venue))}</b> ${esc(OPX_ELIG[x.st] || "-")}${x.why ? ` · ${esc(x.why)}` : ""}</li>`).join("")}</ul></div>
        <div class="ox-sec"><div class="ox-sh"><h4>지도 · 운영 실험 영향</h4></div>${opxMap(R, md)}</div>` : ""}
      ${elig.length ? `<div class="ox-low">${eligTbl}${opxDiag(R)}</div>` : ""}`;
  }
  const agg = R.venue_aggregates.filter(a => a.baseline_selected_count || a.scenario_selected_count || elig.some(x => x.venue_id === a.venue_id && x.eligibility_status === "ELIGIBLE"));
  const N = R.customers.length, cs = R.customers;
  const moved = cs.filter(c => c.choice_changed), scoreOnly = cs.filter(c => c.score_changed_without_choice_change), narrow = cs.filter(c => c.scenario_margin_diagnostic === "NARROW_MARGIN");
  const ov = Object.entries(req.offer_overrides || {})[0], c = opxCalc({ ...OPX.lastForm });
  const what = `<div class="ox-what"><div class="ox-k">무엇을 바꿨나</div><h3>${esc(opxDiscLabel(req))}${ov ? ` <span class="ox-price">${opxW(c.price)} → ${opxW(c.after)}원/인</span>` : ""}</h3><p>${opxCondLine(req)}</p></div>`;
  const te = opxTargetsElig(R), only = md.eligible[0];
  const mode = md.kind === "single"
    ? `<div class="ox-mode ox-mode-single"><b>단일 적격 후보(${esc(opxV(only && only.venue_id))})에 따른 제한적 결과 — 경쟁 선택 실험이 아닙니다</b><p>다른 상품이 이 조건을 통과하지 못해 ${N}명 모두 같은 상품으로 계산됐습니다. 고객 선호나 업장 경쟁력으로 해석하지 마세요.</p><ul>${te.filter(x => x.st !== "ELIGIBLE").map(x => `<li><b>${esc(opxV(x.venue))}</b> 제외 · ${esc(x.why || OPX_ELIG[x.st] || "")}</li>`).join("")}</ul></div>`
    : `<div class="ox-mode ox-mode-compete">경쟁 선택 실험 · 적격 후보 ${md.n}개(${md.eligible.map(x => esc(opxV(x.venue_id))).join(" · ")}) · 기준선과 시나리오를 같은 조건에서 각각 계산</div>`;
  const pills = xs => xs.map(x => `<button type="button" class="ox-pill${OPX.sel === x.persona_id ? " on" : ""}" data-pid="${esc(x.persona_id)}">${opxAv(x.persona_id, 20)}${esc(dno(x.persona_id))}${x.scenario_margin_diagnostic === "NARROW_MARGIN" ? OPX_NAR : ""}</button>`).join("");
  const flow = md.kind === "single" ? `<p class="ox-none">단일 후보라 고객 간 선택 비교가 없습니다.</p>`
    : moved.length ? `<div class="ox-moves">${Object.entries(moved.reduce((m, x) => { const k = `${x.baseline_choice.venue_id}>${x.scenario_choice.venue_id}`; (m[k] = m[k] || []).push(x); return m; }, {})).map(([k, xs]) => { const [a, b] = k.split(">"); return `<div class="ox-mv"><span class="ox-mvv">${esc(opxV(a))}</span><span class="ox-arrow">→</span><span class="ox-mvv on">${esc(opxV(b))}</span><span class="ox-mvp">${pills(xs)}</span></div>`; }).join("")}</div>`
    : `<p class="ox-none">선택을 바꾼 고객이 없습니다${scoreOnly.length ? ` — ${scoreOnly.length}명은 선택은 같지만 점수 차가 바뀌었습니다` : ""}.</p>`;
  const bars = `<div class="ox-bars">${agg.map(a => `<div class="ox-bar"><div class="ox-bn">${esc(opxV(a.venue_id))}</div>
      <div class="ox-bt"><div class="ox-bl${a.baseline_selected_count ? "" : " z"}"><i style="width:${a.baseline_selected_count / N * 100}%"></i><em>기준선 ${a.baseline_selected_count}</em></div><div class="ox-bl ox-bs${a.scenario_selected_count ? "" : " z"}"><i style="width:${a.scenario_selected_count / N * 100}%"></i><em>변경 후 ${a.scenario_selected_count}</em></div></div>
      <div class="ox-bd ${a.delta > 0 ? "up" : a.delta < 0 ? "dn" : ""}" data-venue="${esc(a.venue_id)}">${a.delta > 0 ? "+" : ""}${a.delta || "±0"}</div></div>`).join("")}</div>`;
  const order = [...cs].sort((a, b) => (b.choice_changed - a.choice_changed) || ((b.scenario_margin_diagnostic === "NARROW_MARGIN") - (a.scenario_margin_diagnostic === "NARROW_MARGIN")) || ((a.scenario_margin ?? 9) - (b.scenario_margin ?? 9)));
  const tbl = `<table class="ox-tbl ox-cust"><thead><tr><th>고객</th><th>기준선</th><th>변경 후</th><th class="num">1 · 2위 점수 차</th><th>상태</th></tr></thead><tbody>${order.map(x => {
    const tag = md.kind === "single" ? `<span class="ox-sub">단일 후보</span>` : x.choice_changed ? `<b class="ox-t-mv">선택 변경</b>` : x.score_changed_without_choice_change ? `<span class="ox-t-sc">점수 차만 변화</span>` : `<span class="ox-sub">변화 없음</span>`;
    return `<tr class="${OPX.sel === x.persona_id ? "on" : ""}${x.choice_changed ? " mv" : ""}" data-pid="${esc(x.persona_id)}"><td><span class="ox-who">${opxAv(x.persona_id, 24)}<b>${esc(dno(x.persona_id))}</b><span class="ox-sub">${esc(opxType(x.persona_id))}</span></span></td>
      <td>${esc(opxV(x.baseline_choice && x.baseline_choice.venue_id))}</td><td>${x.choice_changed ? `<b>${esc(opxV(x.scenario_choice.venue_id))}</b>` : esc(opxV(x.scenario_choice && x.scenario_choice.venue_id))}</td>
      <td class="num">${md.kind === "single" ? "비교 없음" : `${opxF(x.baseline_margin)} → <b>${opxF(x.scenario_margin)}</b>${x.scenario_margin_diagnostic === "NARROW_MARGIN" ? ` ${OPX_NAR}` : ""}`}</td><td>${tag}</td></tr>`; }).join("")}</tbody></table>`;
  return `<div class="ox-top">${what}${mode}
    <div class="ox-sec"><div class="ox-sh"><h4>누가 선택을 바꿨나</h4><span>${md.kind === "single" ? "단일 후보 · 비교 없음" : `이동 ${moved.length}명 · 점수 차만 변화 ${scoreOnly.length}명 · 근소(경계 사례) ${narrow.length}명`}</span></div>${flow}</div>
    <div class="ox-sec"><div class="ox-sh"><h4>업장별 선택 수 · 지도</h4><span>규칙 엔진이 고른 가상 고객 ${N}명의 선택${md.kind === "single" ? " · 단일 후보 · 선호 비교 아님" : ""} · 실제 수요 · 매출 예측 아님</span></div>
      <div class="ox-impact">${opxMap(R, md)}${bars}</div></div></div>
    <div class="ox-low"><div class="ox-lowh">상세 — 고객별 전후 · 적격성 · 계산 정보</div>
      <div class="ox-sec"><div class="ox-sh"><h4>고객별 결과 · 전후 비교</h4><span>변하지 않은 고객 포함 ${N}명 · 행을 누르면 오른쪽에 선택 근거</span></div>${tbl}
        <p class="ox-foot">'근소'는 1 · 2위 모델 점수 차가 0.01 이하인 경계 사례라는 뜻입니다. 선택 확률이나 신뢰구간이 아니며, 조건이 조금만 달라도 순위가 바뀔 수 있습니다.</p></div>
      ${eligTbl}${opxDiag(R)}</div>`;
}

function opxDiag(R) {   // 계산 SHA · 버전 · 진단 — 접힌 상세
  if (!document.body.classList.contains("devmode")) return "";   // P5 — 계산 SHA · 버전은 개발 정보에서만
  const e = R.experiment || {}, a = R.adapter || {}, im = (OPX.meta || {}).integrity || {};
  const rows = [["실행 상태", e.run_status], ["엔진 호출", a.engine_called ? `예 · ${(a.arms_computed || []).join(" · ")}` : "-"], ["시나리오 입력 SHA256", e.scenario_input_sha256], ["프로필 입력 SHA256", e.profile_input_sha256],
    ["카탈로그", e.catalog_version], ["동결 엔진", e.engine_version], ["어댑터", a.version], ["CD-15 원본 · 엔진 파일 대조", im.ok ? `${(im.cd15_source || []).length} · ${(im.engine || []).length}개 일치` : "불일치"],
    ["실시간 좌석", e.live_seat_inventory || "NOT_CHECKED"], ["지도 매핑표", ((OPX.meta || {}).venue_map || {}).ok ? "map.js · 카탈로그 SHA 일치" : "불일치 — 지도 표시 안 함"]].filter(r => r[1]);
  return `<details class="ox-det"><summary>계산 정보 · 진단</summary><table class="ox-tbl ox-kv"><tbody>${rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td><code>${esc(String(v))}</code></td></tr>`).join("")}</tbody></table>
    <p class="ox-foot">${esc(a.interpretation || "동결 규칙 엔진의 조건부 시나리오")}</p></details>`;
}

// ---------------------------------------------------------------- CL-18 §2 · §3 지도 운영 영향 레이어
//   확인된 매핑(서버 opx_venue_map.json · use_on_map)만, 그리고 map.js LOC 와 표의 좌표가 같을 때만 그린다. 숫자 · 고객 ID 는 같은 실행 결과(venue_aggregates)에서만.
function opxMapRows() {
  const vm = (OPX.meta || {}).venue_map || {};
  if (!vm.ok) return [];
  return (vm.rows || []).filter(r => r.use_on_map && typeof LOC !== "undefined" && LOC[r.map_loc_id] && r.coord_display && LOC[r.map_loc_id][0] === r.coord_display[0] && LOC[r.map_loc_id][1] === r.coord_display[1]);
}
function opxMap(R, md) {
  const rows = opxMapRows();
  if (!rows.length) return `<div class="ox-map ox-map-off">지도 매핑이 확인되지 않아 지도에 표시하지 않습니다.</div>`;
  const aggBy = Object.fromEntries((R.venue_aggregates || []).map(a => [a.venue_id, a]));
  const eligBy = Object.fromEntries((R.eligibility || []).map(e => [e.venue_id + "|" + e.offer_id, e]));
  const pts = rows.map(r => ({ r, x: r.coord_display[0], y: r.coord_display[1], a: aggBy[r.venue_id], e: eligBy[r.venue_id + "|" + r.offer_id] }));
  const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length, cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
  const W = 470, H = 236, vx = Math.round(cx - W / 2), vy = Math.round(cy - H / 2 - 6);
  const ov = Object.entries(((R.adapter || {}).normalized_request || {}).offer_overrides || {})[0];
  const discVenue = ov ? (opxTarget(ov[0]).venue_id || ov[0]) : null;
  const card = p => {
    const right = p.x >= cx, w = 150, h = p.a ? 58 : 46, x = right ? p.x + 16 : p.x - 16 - w, y = p.y - h / 2;
    const name = opxV(p.r.venue_id), elig = p.e && p.e.eligibility_status === "ELIGIBLE";
    const d = p.a ? p.a.delta : 0, cls = !elig ? "off" : d > 0 ? "up" : d < 0 ? "dn" : "eq";
    const l2 = !elig ? `${OPX_ELIG[p.e && p.e.eligibility_status] || "후보 아님"}` : md.kind === "single" ? "단일 후보 · 비교 없음" : `기준선 ${p.a ? p.a.baseline_selected_count : 0} → 변경 후 ${p.a ? p.a.scenario_selected_count : 0}`;
    const l3 = !elig ? ((p.e && p.e.reasons) || []).map(r => OPX_REASON[r] || r).join(" · ").slice(0, 26) : discVenue === p.r.venue_id ? "가상 할인 적용 업장" : "";
    return `<g class="ox-mc ox-mc-${cls}" data-venue="${esc(p.r.venue_id)}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="7"/>
      <text x="${x + 10}" y="${y + 17}" class="n">${esc(name)}</text>${elig && md.kind !== "single" ? `<text x="${x + w - 10}" y="${y + 18}" class="d" text-anchor="end">${d > 0 ? "+" : ""}${d || "±0"}</text>` : ""}
      <text x="${x + 10}" y="${y + 33}" class="s">${esc(l2)}</text>${l3 ? `<text x="${x + 10}" y="${y + 48}" class="t${discVenue === p.r.venue_id && elig ? " v" : ""}">${esc(l3)}</text>` : ""}</g>`;
  };
  const pin = p => { const elig = p.e && p.e.eligibility_status === "ELIGIBLE", n = p.a ? p.a.scenario_selected_count : 0;
    return `<g class="ox-pin${elig ? "" : " off"}${discVenue === p.r.venue_id ? " disc" : ""}" data-venue="${esc(p.r.venue_id)}"><circle cx="${p.x}" cy="${p.y}" r="11"/><text x="${p.x}" y="${p.y + 4}" text-anchor="middle">${elig ? n : "–"}</text><title>${esc(opxV(p.r.venue_id))} · ${esc(p.r.coord_note || "")}</title></g>`; };
  // 선택 변화 화살표(기준선 업장 → 변경 후 업장) — 이동 궤적이 아니라 '선택이 바뀐 방향'
  const moves = {}; (R.customers || []).filter(c => c.choice_changed).forEach(c => { const k = c.baseline_choice.venue_id + ">" + c.scenario_choice.venue_id; (moves[k] = moves[k] || []).push(c.persona_id); });
  const P = Object.fromEntries(pts.map(p => [p.r.venue_id, p]));
  const arrows = Object.entries(moves).map(([k, ids]) => { const [a, b] = k.split(">"), A = P[a], B = P[b]; if (!A || !B) return "";
    const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2, dx = B.x - A.x, dy = B.y - A.y, L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, k2 = 26;
    const qx = mx + nx * k2, qy = my + ny * k2, ux = (B.x - qx), uy = (B.y - qy), ul = Math.hypot(ux, uy) || 1, ex = B.x - ux / ul * 14, ey = B.y - uy / ul * 14, sx = A.x + (qx - A.x) / Math.hypot(qx - A.x, qy - A.y) * 14, sy = A.y + (qy - A.y) / Math.hypot(qx - A.x, qy - A.y) * 14;
    return `<g class="ox-arr"><path d="M${sx.toFixed(1)},${sy.toFixed(1)} Q${qx.toFixed(1)},${qy.toFixed(1)} ${ex.toFixed(1)},${ey.toFixed(1)}" marker-end="url(#oxArrH)"/><text x="${(qx + nx * 4).toFixed(1)}" y="${(qy + ny * 4 + 4).toFixed(1)}" text-anchor="middle">${ids.length}명 선택 변경</text></g>`; }).join("");
  const svg = `<svg class="ox-msvg" viewBox="${vx} ${vy} ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="운영 실험 영향 지도">
    <defs><marker id="oxArrH" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="ox-arrh"/></marker></defs>
    <image href="${typeof MAP_IMG !== "undefined" ? MAP_IMG : "/static/map_base.png"}" x="0" y="0" width="1000" height="643" preserveAspectRatio="none" opacity=".55"/>
    ${md.kind === "single" || md.kind === "none" ? "" : arrows}${pts.map(pin).join("")}${pts.map(card).join("")}
    ${md.kind === "single" ? `<text class="ox-mban" x="${vx + 10}" y="${vy + 18}">단일 적격 후보 · 경쟁 선택 아님</text>` : md.kind === "none" ? `<text class="ox-mban" x="${vx + 10}" y="${vy + 18}">적격 후보 0개 · 선택 계산 불가</text>` : ""}</svg>`;
  const ids = Object.entries(moves).map(([k, xs]) => { const [a, b] = k.split(">"); return `<span class="ox-mlg"><b>${esc(opxV(a))} → ${esc(opxV(b))}</b>${xs.map(id => `<button type="button" class="ox-pill ox-pill-s${OPX.sel === id ? " on" : ""}" data-pid="${esc(id)}">${esc(dno(id))}</button>`).join("")}</span>`; }).join("");
  return `<figure class="ox-map">${svg}<figcaption>${md.kind === "compete" && ids ? `<div class="ox-mids">선택이 바뀐 고객 ${ids}</div>` : ""}<div class="ox-foot">운영 실험 영향 표시 — 선택이 바뀐 방향이며 실제 이동 궤적 · 방문객 수 · 혼잡도 · 수용 능력이 아닙니다. 위치는 지도 그림의 건물 안 업장 대표점(매핑 확인 ${rows.length}개 업장 · 그 밖의 상품은 이번 조건에서 점수 비교 밖이라 표시 안 함). 고객 ID 를 누르면 오른쪽에 전후 선택 근거가 열립니다.</div></figcaption></figure>`;
}

function opxCand(arm, pid) { const p = ((OPX.last[arm] || {}).customers || []).find(x => x.persona_id === pid); return p ? p.candidates || [] : []; }
function opxWhy(x) {   // 선택이 달라진(또는 유지된) 이유 — 같은 엔진의 기준선 · 시나리오 항목 차이에서 만든다
  const pid = x.persona_id, b = opxCand("baseline", pid), s = opxCand("scenario", pid);
  const offs = [...new Set([x.baseline_choice && x.baseline_choice.offer_id, x.scenario_choice && x.scenario_choice.offer_id, ...s.slice(0, 2).map(c => c.offer_id)].filter(Boolean))];
  return offs.map(oid => {
    const cb = b.find(c => c.offer_id === oid), cs = s.find(c => c.offer_id === oid);
    const fb = Object.fromEntries((cb ? cb.terms : []).map(t => [t.factor, t.value])), fs = Object.fromEntries((cs ? cs.terms : []).map(t => [t.factor, t.value]));
    const diffs = [...new Set([...Object.keys(fb), ...Object.keys(fs)])].map(k => ({ k, d: (fs[k] || 0) - (fb[k] || 0) })).filter(d => Math.abs(d.d) >= 0.0005);
    return { oid, venue: (cs || cb || {}).venue_id, before: cb ? cb.score : null, after: cs ? cs.score : null, diffs };
  });
}

function opxRight() {
  const R = OPX.last;
  if (!R || R.experiment.run_status !== "COMPLETED") return `<div class="ox-empty">고객을 고르면 선택 근거가 여기에 나옵니다.</div>`;
  const x = R.customers.find(c => c.persona_id === OPX.sel) || R.customers.find(c => c.choice_changed) || R.customers[0];
  if (!x) return "";
  const md = opxMode(R), pid = x.persona_id, sc = x.scenario_choice, bc = x.baseline_choice, rows = opxWhy(x);
  const s = opxCand("scenario", pid), top = s[0], run = s[1];
  const parts = top ? [["공통(가격 · 끼니)", top.common_contribution, "c"], ["후기 근거", top.personal_contribution, "p"], ["설계 가정", top.assumption_contribution, "a"]] : [];
  const mx = Math.max(0.01, ...parts.map(p => Math.abs(p[1] || 0)));
  const diag = x.scenario_margin_diagnostic === "NARROW_MARGIN" ? "경계 사례 — 1 · 2위 점수 차가 0.01 이하로 근소합니다. 조건이 조금만 달라도 순위가 바뀔 수 있다는 진단이며, 선택 확률이 아닙니다."
    : x.scenario_margin_diagnostic === "LOW_MARGIN" ? "점수 차가 0.2 이하로 작은 편입니다(진단 · 확률 아님)." : x.scenario_margin_diagnostic === "NO_ALTERNATIVE" ? "비교할 다른 상품이 없습니다(단일 적격 후보)." : "점수 차가 작지 않습니다.";
  const why = md.kind === "single" ? `이 조건에서 점수 비교에 들어간 상품이 ${opxV(sc.venue_id)} 하나뿐이라 그대로 선택됐습니다. 선호를 비교한 결과가 아닙니다.`
    : x.choice_changed ? `${opxV(bc.venue_id)} ${opxF(rows.find(r => r.oid === bc.offer_id)?.before, 3)} → ${opxF(rows.find(r => r.oid === bc.offer_id)?.after, 3)} · ${opxV(sc.venue_id)} ${opxF(rows.find(r => r.oid === sc.offer_id)?.before, 3)} → ${opxF(rows.find(r => r.oid === sc.offer_id)?.after, 3)} — 가상 할인으로 ${opxV(sc.venue_id)} 점수가 올라 1위가 바뀌었습니다.`
    : x.score_changed_without_choice_change ? `${opxV(sc.venue_id)}가 계속 1위입니다. 다른 상품 점수는 바뀌었지만 순위를 뒤집지 못했습니다(점수 차 ${opxF(x.baseline_margin)} → ${opxF(x.scenario_margin)}).` : "이번 변경은 이 고객의 후보 점수를 바꾸지 않았습니다.";
  const termTbl = cands => `<table class="ox-tbl ox-terms"><thead><tr><th>상품</th><th>항목</th><th>구분</th><th class="num">값</th></tr></thead><tbody>${cands.map(cd => cd.terms.map((t, i) => `<tr>${i ? "<td></td>" : `<td><b>${esc(opxV(cd.venue_id))}</b> ${opxF(cd.score)}</td>`}<td>${esc(t.factor)}</td><td class="ox-sub">${esc(OPX_KIND[t.kind] || t.kind || "")}</td><td class="num">${opxSgn(t.value, 3)}</td></tr>`).join("")).join("")}</tbody></table>`;
  return `<div class="ox-rh">${opxAv(pid, 44)}<div><b>${esc(dno(pid))}</b><span>${esc(opxType(pid))}</span></div></div>
    <div class="ox-ch"><div><span class="ox-k">원래 선택</span><b>${esc(opxV(bc.venue_id))}</b><span class="ox-sub">${esc(bc.offer_name)}</span></div><span class="ox-arrow">→</span><div class="${x.choice_changed ? "on" : ""}"><span class="ox-k">변경 후 선택</span><b>${esc(opxV(sc.venue_id))}</b><span class="ox-sub">${esc(sc.offer_name)}</span></div></div>
    <div class="ox-blk"><h5>선택이 ${x.choice_changed ? "달라진" : "유지된"} 이유</h5><p>${esc(why)}</p>
      ${md.kind === "single" ? "" : `<ul class="ox-diffs">${rows.filter(r => r.diffs.length).map(r => `<li><b>${esc(opxV(r.venue))}</b> ${r.diffs.map(d => `${esc(d.k)} ${opxSgn(d.d, 3)}`).join(" · ")}</li>`).join("") || "<li class='ox-sub'>점수 항목 변화 없음</li>"}</ul>`}</div>
    <div class="ox-blk"><h5>1 · 2위 점수 차</h5><p class="ox-mg"><b>${opxF(x.scenario_margin)}</b> ${run ? `(${esc(opxV(top.venue_id))} ${opxF(top.score)} vs ${esc(opxV(run.venue_id))} ${opxF(run.score)})` : ""}${x.scenario_margin_diagnostic === "NARROW_MARGIN" ? ` ${OPX_NAR}` : ""}</p><p class="ox-sub">${esc(diag)}</p></div>
    <p class="ox-rnote">지도 · 이 패널은 운영 실험의 전후 선택이며, 고객흐름의 실제 하루 동선과 별개입니다.</p>
    <details class="ox-det"><summary>점수 분해 · 근거</summary>
      <div class="ox-blk"><h5>1위 점수 구성 · ${esc(opxV(top && top.venue_id))}</h5>${parts.map(([l, v, k]) => `<div class="ox-part"><span>${l}</span><div class="ox-pb ox-pb-${k}"><i style="width:${Math.abs(v || 0) / mx * 100}%"></i></div><b>${opxSgn(v, 2)}</b></div>`).join("")}
        <p class="ox-foot">후기 근거 = 이 고객의 후기에서 추출한 사실(익명 ID ${top ? top.fact_ids.length : 0}개)에 기반한 항목 · 공통 = 모든 고객에게 같은 가격 · 끼니 항목 · 설계 가정 = 근거 없이 둔 모델 가정.</p></div>
      <div class="ox-sub ox-pad">후보별 점수 항목 · 시나리오</div>${termTbl(s)}<div class="ox-sub ox-pad">기준선</div>${termTbl(opxCand("baseline", pid))}
      <p class="ox-foot dev">근거 사실 ID: ${esc((top ? top.fact_ids : []).join(", ") || "-")}<br>잠금 결정 ID ${esc(((x.locked_decision || {}).decision_id || "").slice(0, 16))} · 플래너 변경 불가 · 기존 고객흐름 결정과 별개(자동 교체 안 함)</p></details>`;
}

function opxWire() {
  const f = OPX.form, re = () => opxRender();
  $$("#opxView .cf-seg[data-k] button").forEach(b => b.onclick = () => { const k = b.parentElement.dataset.k; f[k] = b.dataset.v; if (k === "target_offer") f.discount_amount = Math.min(f.discount_amount, opxTarget(f.target_offer).price_amount || f.discount_amount); re(); });
  $$("#opxView .ox-step button").forEach(b => b.onclick = () => { const k = b.dataset.k; f[k] = Math.max(0, Math.min(8, f[k] + +b.dataset.d)); if (f.adults + f.children < 1) f[k] = 1; re(); });
  const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e[ev] = fn; };
  on("oxDate", "onchange", e => { f.date = e.target.value; re(); });
  on("oxTime", "onchange", e => { f.start_time = e.target.value; re(); });
  on("oxDur", "onchange", e => { f.duration_minutes = +e.target.value; re(); });
  on("oxHol", "onchange", e => { f.holiday = e.target.checked; re(); });
  on("oxRes", "onchange", e => { f.reservation = e.target.checked; re(); });
  // 할인 금액은 입력 중 화면 전체를 다시 그리지 않는다(포커스 · 실행 버튼 클릭 유지) — 계산 줄 · 상태 · 버튼 글자만 갱신
  on("oxRng", "oninput", e => { f.discount_amount = +e.target.value; const a = document.getElementById("oxAmt"); if (a) a.value = f.discount_amount; opxSoft(); });
  on("oxAmt", "oninput", e => { const n = Math.round(+e.target.value || 0); f.discount_amount = Math.max(0, n); const r = document.getElementById("oxRng"); if (r) r.value = Math.min(f.discount_amount, +r.max); opxSoft(); });
  on("oxRun", "onclick", () => opxRun());
  on("oxReset", "onclick", () => { OPX.form = { ...OPX.meta.default }; re(); });
  $$("#opxView [data-pid]").forEach(el => el.onclick = () => { OPX.sel = el.dataset.pid; $("#oxR").innerHTML = opxRight(); $$("#opxView [data-pid]").forEach(z => z.classList.toggle("on", z.dataset.pid === OPX.sel)); });
}

function opxSoft() {   // 금액 입력 중 부분 갱신
  const f = OPX.form, c = opxCalc(f), t = opxTarget(f.target_offer), st = opxStatus(), ch = opxChanged();
  const calc = document.querySelector("#opxView .ox-calc"); if (calc) calc.innerHTML = f.discount_amount ? `1인 ${opxW(c.pp)}원 · ${c.party}명 팀 ${opxW(c.team)}원 반영<br>${esc(opxV(t.venue_id))} ${opxW(c.price)} → <b>${opxW(c.after)}원/인</b>` : `${esc(opxV(t.venue_id))} 기준 가격 ${opxW(c.price)}원/인 · 할인 없음`;
  const se = document.getElementById("oxSt"); if (se) { se.textContent = st.t; se.className = `ox-st ox-st-${st.k}`; }
  const rb = document.getElementById("oxRun"); if (rb && !OPX.busy) rb.textContent = ch.length ? "변경 조건으로 실행" : "시나리오 실행";
  const am = document.querySelector("#opxView .ox-amt"); if (am) am.classList.toggle("ox-chg", ch.includes("discount_amount"));
}

async function opxRun() {
  if (OPX.busy) return;
  OPX.busy = true; OPX.err = null; opxRender();
  const sent = { ...OPX.form };
  try {
    const r = await fetch("/api/opx/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sent) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
    OPX.last = j; OPX.lastForm = sent; OPX.lastAt = new Date().toTimeString().slice(0, 8);
    const md = opxMode(j);
    if (j.experiment.run_status === "COMPLETED") {
      const cnt = j.venue_aggregates.filter(a => a.scenario_selected_count).map(a => `${opxV(a.venue_id)} ${a.scenario_selected_count}`).join(" · ") + (md.kind === "single" ? " (단일 후보)" : "");
      OPX.runs.push({ label: opxFormLabel(sent), counts: cnt });
      if (OPX.sel && !j.customers.some(c => c.persona_id === OPX.sel)) OPX.sel = null;
    } else OPX.runs.push({ label: opxFormLabel(sent), counts: md && md.kind === "none" ? "적격 후보 0 · 계산 불가" : (OPX_STATUS[j.experiment.run_status] || j.experiment.run_status) });
  } catch (e) { OPX.err = "실행 실패 — " + (e.message || e); }
  OPX.busy = false; opxRender();
}
