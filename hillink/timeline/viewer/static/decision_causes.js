// HILLINK decision-cause analyzer: reads the M4 decision records of any /api/visit result and explains,
// per customer decision, why each competing option was not chosen. It never changes weights, never
// creates scores for options that were not candidates, and separates "blocked" from "out-scored".
// Levers are classified only from the runtime capability contract and recorded engine limits.
(function (root) {
'use strict';

// ---- score terms: engine factor name -> cause category (unknown names stay UNCLASSIFIED) ----
const TERM = {
  '1인 지불액': 'PRICE', '점수 계산 가격(경쟁 호텔 저녁 최저가 · 가상 비교 기준)': 'PRICE', '가격 미확인 · 비용 비교 미평가': 'PRICE_UNKNOWN', '구매 전 가치 비교(내용 대비 가격 초과)': 'VALUE_CHECK',
  '할인 반응(개인 근거)': 'VALUE_CHECK', '패키지에 포함(추가 지불 없음)': 'INCLUSION', '포함 혜택 활용(개인 근거)': 'INCLUSION',
  '시작까지 기다림': 'TIME', '저녁을 미룸': 'TIME',
  '음식 경험': 'MENU', '간식 · 디저트': 'MENU', '구체적 메뉴 기호 일치': 'MENU',
  '야경 · 공간 경험': 'SPACE', '정원 · 산책 경험': 'SPACE', '온수 · 족욕 휴식': 'SPACE',
  '저녁 끼니 해결': 'MEAL_NEED', '휴식 · 회복': 'STATE',
  '익숙한 곳 · 실제 이용 경험': 'HISTORY', '이미 경험한 곳(새로움 낮음)': 'HISTORY', '명시적 재방문 거부(같은 업장)': 'HISTORY', '이용 후 가격 가치 유보(같은 업장)': 'HISTORY',
  '실용적 식사 대안(객실에서 먹기)': 'TRAIT', '수영 비선호': 'TRAIT', '수영장에 가도 수영은 안 함': 'TRAIT'
};
// ---- block reasons: catalog exclusion codes and world block phrases -> category ----
const BLOCK = [
  [/^(RECENT_MEAL|SAME_VENUE_RECENT_MEAL)$/, 'MEAL_STATE'],
  [/^SERVICE_NOT_OPEN_YET$/, 'TIME'], [/^(SERVICE_CLOSED_OR_INSUFFICIENT_TIME|SOURCE_LAST_ORDER_PASSED|SERVICE_OR_COMPLETION_WINDOW|MEAL_PERIOD|RESEARCH_ACTUAL_ARRIVAL_EXCEEDS_EXISTING_TIME_LIMIT)$/, 'TIME'],
  [/운영하지 않음|운영 종료|하루 종료 시각/, 'TIME'],
  [/^RESERVATION_NOT_CONFIRMED_OR_VIRTUALLY_DECLARED$/, 'RESERVATION'],
  [/^(DATE_OR_SALE_DAY|NATIVE_SOURCE_MEAL_CONTRACT_PERIOD|PACKAGE_REDEMPTION_WINDOW|PACKAGE_EVENT_WEATHER_VARIANT_MISMATCH)$/, 'SALE_PERIOD'],
  [/^(CHILDREN_NOT_ELIGIBLE|POOL_BUILDING|ALCOHOL_PARTY_QUALIFICATION_UNKNOWN|KIDSCLUB_AGE_BAND_REQUIRED|SELECTED_CURRENT_GUEST_PACKAGE_REQUIRED)$/, 'ELIGIBILITY'],
  [/^(FIXED_SET_PARTY_SIZE|MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY)$/, 'ORDER_UNIT'],
  [/^(PAID_IRD_BREAKFAST_REQUIRES_EXPLICIT_OPT_IN|FREE_SKYARD_COVERAGE_NOT_PRESENT|USE_INCLUDED_SKYARD_NOT_PAID_SKU)$/, 'INCLUSION'],
  [/^OPERATING_REOPENING_UNKNOWN_EXPLICIT_VIRTUAL_OVERRIDE_REQUIRED$/, 'OPERATING'],
  [/^(DRINK_OR_SNACK_NOT_A_MAIN_MEAL|DINNER_MAIN_SERVICE_NOT_EXPLICIT)$/, 'PRODUCT_ROLE'],
  [/오늘 저녁을 이미 먹음|오늘 이미 이용/, 'ALREADY_DONE'],
  [/^DELIVERY_EXCLUDED_NO_HOTEL_DINNER_PRICE_REFERENCE$/, 'NO_PRICE_REFERENCE']
];
const LABEL = {
  MEAL_STATE: '최근 식사·같은 장소 재식사 제한', PRICE: '1인 가격', PRICE_UNKNOWN: '가격 미확인', VALUE_CHECK: '가격 대비 가치 판단', INCLUSION: '포함 혜택', TIME: '시간 (영업·대기·마감)',
  MENU: '메뉴·음식 취향', SPACE: '공간·분위기', MEAL_NEED: '끼니 필요', STATE: '휴식·상태', HISTORY: '이용 이력', TRAIT: '개인 성향',
  PLAN: '다음 일정 (내다보기)', RESERVATION: '예약', SALE_PERIOD: '판매 기간', ELIGIBILITY: '이용 자격', ORDER_UNIT: '주문 단위',
  OPERATING: '운영 재개 미확인', PRODUCT_ROLE: '상품 성격', ALREADY_DONE: '이미 이용·식사함', NO_PRICE_REFERENCE: '엔진 비교 기준 부재(외부 배달)', CONTEXT: '상황 보정', UNCLASSIFIED: '분류 규칙 없음'
};
const STATUS = { COMPUTABLE: '현재 엔진으로 계산 가능', NEEDS_ENGINE: '일부 엔진 보완 후 계산 가능', NEEDS_DATA: '운영·상품 자료 확인 필요', NOT_STRATEGIZABLE: '현재 근거로 전략화 불가' };

// Lever per category. The status of the price lever is read from /api/runtime/capabilities; the rest
// cite the request contract or a recorded engine run (T1/T2) as their basis.
function levers(cap) {
  const sup = new Set((cap && cap.supported) || []), lim = new Set((cap && cap.limited) || []);
  const price = sup.has('catalog_discount_percent') || sup.has('catalog_price_overrides');
  const booking = lim.has('no_actual_booking') ? 'capabilities.limited: no_actual_booking' : '실제 예약 이행 미검증';
  return {
    PRICE: { lever: '기존 SKU 가격·할인', status: price ? 'COMPUTABLE' : 'NEEDS_ENGINE', basis: price ? 'capabilities.supported: catalog_discount_percent · catalog_price_overrides' : '가격 입력 미지원' },
    VALUE_CHECK: { lever: '기존 SKU 가격·할인 (개인 가치 판단 항은 재실행으로 확인)', status: price ? 'COMPUTABLE' : 'NEEDS_ENGINE', basis: '가격 입력은 지원 · 이 항이 가격에 따라 바뀌는지는 재실행 결과로만 판단' },
    PRICE_UNKNOWN: { lever: '확인된 판매가 입력', status: 'NEEDS_DATA', basis: '가격 미확인 상품' },
    INCLUSION: { lever: '패키지 포함 혜택', status: 'NEEDS_DATA', basis: '포함 상품·이용 조건 자료 필요 (요청 계약에 패키지 혜택 편집 없음)' },
    TIME: { lever: '영업 시각 · 행사 회차 · 식사 예약 시각', status: 'NEEDS_ENGINE', basis: `영업시간 변경 입력 없음 · ${booking} · 산타 회차 변경 T1·T2 실행에서 체크인·퇴실 일과가 예약보다 먼저 처리됨` },
    RESERVATION: { lever: '식사·시설 예약', status: 'NEEDS_ENGINE', basis: `카탈로그에 가상 예약 입력은 있으나 ${booking} · 일정 이행 미검증` },
    PLAN: { lever: '행사·시설 연계 동선', status: 'NEEDS_ENGINE', basis: '연계 상품·동선 입력 없음' },
    MENU: { lever: '실제 메뉴·상품 구성', status: 'NEEDS_DATA', basis: '개인 취향은 변경 불가 · 실제 판매 가능한 메뉴 구성 자료 필요' },
    SPACE: { lever: '실제 좌석·서비스 조건', status: 'NEEDS_DATA', basis: '공간 점수는 업장 속성 · 실제 제공 가능한 좌석·서비스가 확인될 때만 가설' },
    ELIGIBILITY: { lever: '이용 자격·연령 조건', status: 'NEEDS_DATA', basis: lim.has('unconfirmed_child_age_requires_declared_model_or_age') ? 'capabilities.limited: unconfirmed_child_age_requires_declared_model_or_age' : '이용 규정 자료 필요' },
    ORDER_UNIT: { lever: '판매 단위·최소 주문', status: 'NEEDS_DATA', basis: '실제 판매 단위 자료 필요' },
    SALE_PERIOD: { lever: '판매 기간', status: 'NEEDS_DATA', basis: '판매 기간·행사 일정 자료 필요' },
    OPERATING: { lever: '운영 재개', status: 'NEEDS_DATA', basis: '운영 재개 확인 필요' },
    MEAL_STATE: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '공통 식사 종료·장소 재방문 제약 · 할인이나 영업시간으로 해제하지 않음' },
    MEAL_NEED: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '고객 상태' }, STATE: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '고객 상태' },
    HISTORY: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '고객 이력' }, TRAIT: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '개인 성향' },
    ALREADY_DONE: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '이미 이용·식사함' }, PRODUCT_ROLE: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '상품 성격' },
    NO_PRICE_REFERENCE: { lever: '외부 배달 비교 기준', status: 'NEEDS_DATA', basis: '같은 시각 비교할 호텔 저녁이 없어 배달 후보를 만들지 않음 · 실제 배달 가격 자료 필요' },
    CONTEXT: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '상황 보정' }, UNCLASSIFIED: { lever: '—', status: 'NOT_STRATEGIZABLE', basis: '분류 규칙 없음 · 원 코드 그대로 표시' }
  };
}

const hm = t => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
const score = c => (c.final_with_lookahead != null ? c.final_with_lookahead : c.final_score);
// Catalog candidates carry a service contract; plain world offers (non-catalog runs) are identified by their offer id.
const rawVenueOf = c => (c.service_contract && c.service_contract.venue_id) || (c.sku_contract && c.sku_contract.venue_id) || (c.candidate_id && !/^HC_/.test(c.candidate_id) ? c.candidate_id : null);
const venueOf = c => {const v=rawVenueOf(c);return ['@room','ROOM_MEAL','ROOM_SERVICE'].includes(v)?'IRD':v;};
const skuOf = c => { const q = c.product_quote; return q && q.components && q.components.length === 1 ? q.components[0].sku_id : null; };
const totalOf = c => (c.product_quote ? c.product_quote.total_krw : null);
const partyOf = c => ((c.scoring_input_contract || {}).participant_count) || null;
function blockCats(text) {
  return String(text || '').split(' · ').filter(Boolean).map(code => { const hit = BLOCK.find(([re]) => re.test(code)); return { code, category: hit ? hit[1] : 'UNCLASSIFIED' }; });
}
function termMap(c) { const m = {}; for (const t of c.terms || []) m[t.factor] = { value: t.value, fact_ids: t.fact_ids || [] }; return m; }
function days(flow) { return flow.visit_days ? flow.visit_days.map(d => d.flow) : [flow.result || flow]; }

// One competitor against the chosen option, from the same decision packet only.
function compare(ch, c) {
  const a = termMap(ch), b = termMap(c), causes = [];
  for (const f of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const d = (a[f] ? a[f].value : 0) - (b[f] ? b[f].value : 0);
    if (Math.abs(d) < 1e-9) continue;
    const ids = [...new Set([...(a[f] ? a[f].fact_ids : []), ...(b[f] ? b[f].fact_ids : [])])];
    causes.push({ factor: f, category: TERM[f] || 'UNCLASSIFIED', delta: +d.toFixed(4), evidence: ids.length ? 'PERSONAL_FACT' : 'COMMON_RULE', fact_ids: ids });
  }
  const ctx = (ch.context_adjustment || 0) - (c.context_adjustment || 0);
  if (Math.abs(ctx) > 1e-9) causes.push({ factor: '상황 보정', category: 'CONTEXT', delta: +ctx.toFixed(4), evidence: 'COMMON_RULE', fact_ids: [] });
  const look = (score(ch) - ch.final_score) - (score(c) - c.final_score);
  if (Math.abs(look) > 1e-9) causes.push({ factor: '다음 일정 (내다보기)', category: 'PLAN', delta: +look.toFixed(4), evidence: 'COMMON_RULE', fact_ids: [] });
  causes.sort((x, y) => y.delta - x.delta);
  const gap = score(ch) - score(c), price = causes.filter(x => x.category === 'PRICE').reduce((n, x) => n + x.delta, 0);
  const out = { ...(c.price_reference ? { price_reference: c.price_reference } : {}), status: 'COMPETED', id: c.candidate_id, label: c.candidate_label, venue: venueOf(c), sku: skuOf(c), total_krw: totalOf(c), score: +score(c).toFixed(4), gap: +gap.toFixed(4), price_part: +price.toFixed(4), nonprice_part: +(gap - price).toFixed(4), causes };
  // First-order price approximation, derived from this candidate's own price term (no constant assumed).
  const pt = (b['1인 지불액'] || {}).value, n = partyOf(c), tot = totalOf(c);
  if (pt != null && pt < 0 && n && tot) {
    const k = -pt / (tot / n), pp = tot / n, cut = gap / k;           // KRW per person the price would have to drop
    out.approx = { method: 'PRICE_TERM_ONLY_FIRST_ORDER', per_person_krw: Math.round(pp), break_even_discount_pct: +(100 * cut / pp).toFixed(1),
      spend_at_break_even_krw: Math.round(Math.max(0, pp - cut) * n), spend_delta_vs_chosen_krw: totalOf(ch) != null ? Math.round(Math.max(0, pp - cut) * n) - totalOf(ch) : null };
  }
  return out;
}

// Decisions of one customer. A decision is the QUANTITATIVE packet that was executed; its slot comes
// from the activity it produced. PLANNER packets have no term decomposition and are reported as such.
function analyzeCustomer(flow, pid, opts = {}) {
  const runId = (flow.ledger && flow.ledger.run_id) || null, rows = [];
  for (const day of days(flow)) {
    const m = (((day.plans || {})[pid] || {}).m4) || {}, ev = {};
    for (const a of m.activity_history || []) ev[a.event_id] = a;
    for (const dc of m.decisions || []) {
      if (dc.execution_status !== 'EXECUTED') continue;
      const pk = dc.packet, act = ev[dc.actual_next_event_id] || {}, slot = act.meal_slot || null;
      if (opts.slot && slot !== opts.slot) continue;
      const cs = pk.candidates || [], sid = (dc.selected_action && dc.selected_action.candidate_id) || dc.selected_action;
      const ch = cs.find(c => c.candidate_id === sid);
      const base = { run_id: runId, customer_id: pid, date: pk.context_factors.date, time: hm(pk.context_factors.time), packet_sha256: pk.packet_sha256, event_id: dc.actual_next_event_id || null, kind: pk.kind, slot,
        observed_context: {fatigue_proxy:pk.context_factors.fatigue_proxy,prior_meals_count:pk.context_factors.prior_meals?.length,companions:pk.context_factors.companions,appetite_proxy:pk.context_factors.meal_state?.appetite_proxy},
        decision_key: `${pid}|${pk.context_factors.date}|${hm(pk.context_factors.time)}` };
      if (!ch) { rows.push({ ...base, status: 'CHOSEN_NOT_IN_PACKET' }); continue; }
      const chosen = { ...(ch.price_reference ? { price_reference: ch.price_reference } : {}), id: ch.candidate_id, label: ch.candidate_label, venue: venueOf(ch), sku: skuOf(ch), total_krw: totalOf(ch), score: +score(ch).toFixed(4),
        facts: [...new Set((ch.terms || []).flatMap(t => t.fact_ids || []))] };
      if (pk.kind !== 'QUANTITATIVE') {
        // Planner choices have real scenes/orders even when there is no score decomposition.
        // Resolve that occurrence; never infer a venue from an action-name substring.
        const scenes=(flow.plans?.[pid]?.scenes||[]).filter(s=>s.visit_date===base.date&&(s.meal||s.turn)===slot&&
          s.basis?.m4?.event_id===base.event_id&&(s.basis?.m4?.decision_packet_ids||[]).includes(base.packet_sha256));
        if(slot&&scenes.length===1){
          const scene=scenes[0],order=(flow.ledger?.receipts?.[pid]?.rows||[]).filter(r=>r.visit_date===base.date&&r.time===hm(scene.t0)&&(r.meal||r.turn)===slot&&r.act===scene.act),venues=[...new Set(order.map(r=>r.venue_id||r.sku_contract?.venue_id).filter(Boolean))];
          if(venues.length===1&&order.length){
            chosen.venue=venues[0];chosen.label=order.map(r=>r.product||r.sku_contract?.label).filter(Boolean).join(' + ');
            const skus=[...new Set(order.map(r=>r.sku_id||r.product_sku_id||r.product_id).filter(Boolean))].sort();
            chosen.sku=skus.length===1?skus[0]:null;chosen.product_signature=skus.join('|');
            chosen.total_krw=order.reduce((n,r)=>n+(r.paid_krw||0),0);chosen.choice_source='RECORDED_SCENE_ORDER';
          }
        }
        rows.push({ ...base, chosen, status: 'NO_TERM_DECOMPOSITION' }); continue;
      }
      const best = {}, blocked = {};
      for (const c of cs) {
        if (c === ch) continue;
        const v = venueOf(c) || c.candidate_id;
        if (c.world_allowed && c.final_score != null) { if (!best[v] || score(c) > score(best[v])) best[v] = c; }
        else if (c.block_reason) (blocked[v] = blocked[v] || { status: 'BLOCKED', venue: venueOf(c), label: c.candidate_label, reasons: blockCats(c.block_reason) });
      }
      for (const x of pk.catalog_excluded_candidates || []) if (x.venue_id && !best[x.venue_id]) blocked[x.venue_id] = { status: 'BLOCKED', venue: x.venue_id, label: x.venue_id, reasons: (x.reasons || []).flatMap(blockCats) };
      const competitors = Object.values(best).map(c => Object.assign(compare(ch, c), { same_venue: venueOf(c) === chosen.venue })).sort((a, b) => a.gap - b.gap);
      const rival = competitors.find(c => !c.same_venue) || null;      // closest option at another venue
      const blockedList = Object.values(blocked).filter(b => !best[b.venue]);
      let target = null;
      if (opts.target_venue) {
        const t = competitors.find(c => c.venue === opts.target_venue);
        if (chosen.venue === opts.target_venue) target = { status: 'CHOSEN' };
        else if (t) target = t;
        else if (blocked[opts.target_venue]) target = blocked[opts.target_venue];
        else target = { status: 'ABSENT', venue: opts.target_venue };        // not a candidate: no score is invented
      }
      // Options the customer liked more on non-price terms but lost on price (where a discount could raise spend).
      const priceLost = competitors.filter(c => c.nonprice_part < 0 && c.price_part > 0 && c.total_krw != null && chosen.total_krw != null && c.total_krw > chosen.total_krw);
      rows.push({ ...base, status: 'ANALYZED', chosen, competitors, rival, blocked: blockedList, target, price_lost_upsell: priceLost.map(c => ({ label: c.label, venue: c.venue, total_krw: c.total_krw, approx: c.approx || null })) });
    }
  }
  return rows;
}

// Goal-level summary: what blocks or out-scores the target, and which levers could address it.
function summarize(rows, cap) {
  const L = levers(cap), cat = {}, add = (k, pid, ev) => { const x = cat[k] = cat[k] || { category: k, label: LABEL[k] || k, customers: new Set(), personal: 0, common: 0, kind: new Set() }; x.customers.add(pid); if (ev === 'PERSONAL_FACT') x.personal++; else if (ev === 'COMMON_RULE') x.common++; return x; };
  const counts = { analyzed: 0, blocked: 0, competed: 0, absent: 0, chosen: 0, no_decomposition: 0, same_venue_runner_up: 0 };
  for (const r of rows) {
    if (r.status !== 'ANALYZED') { if (r.status === 'NO_TERM_DECOMPOSITION') counts.no_decomposition++; continue; }
    counts.analyzed++;
    if (r.competitors[0] && r.competitors[0].same_venue) counts.same_venue_runner_up++;
    const t = r.target || r.rival;
    if (!t) continue;
    if (t.status === 'CHOSEN') { counts.chosen++; continue; }
    if (t.status === 'ABSENT') { counts.absent++; continue; }
    if (t.status === 'BLOCKED') { counts.blocked++; for (const b of t.reasons) add(b.category, r.customer_id).kind.add('BLOCKED'); continue; }
    counts.competed++;
    const top = t.causes.filter(c => c.delta > 0);
    if (!top.length) continue;
    const main = top[0]; add(main.category, r.customer_id, main.evidence).kind.add('MAIN_SCORE_GAP');
    // Other terms that alone cover at least a fifth of the gap also count as contributing causes.
    for (const c of top.slice(1)) if (c.delta >= Math.max(0.1, 0.2 * t.gap)) add(c.category, r.customer_id, c.evidence).kind.add('CONTRIBUTING');
  }
  const table = Object.values(cat).map(x => ({ category: x.category, label: x.label, customers: [...x.customers], count: x.customers.size, kinds: [...x.kind], evidence: { personal: x.personal, common: x.common },
    lever: (L[x.category] || L.UNCLASSIFIED).lever, status: (L[x.category] || L.UNCLASSIFIED).status, status_label: STATUS[(L[x.category] || L.UNCLASSIFIED).status], basis: (L[x.category] || L.UNCLASSIFIED).basis }))
    .sort((a, b) => b.count - a.count);
  return { counts, table };
}

const API = { analyzeCustomer, summarize, levers, TERM, LABEL, STATUS, blockCats,
  analyze(flow, customers, opts = {}) { const rows = customers.flatMap(pid => analyzeCustomer(flow, pid, opts)); return { run_id: (flow.ledger && flow.ledger.run_id) || null, opts, rows }; } };
if (typeof module !== 'undefined' && module.exports) module.exports = API; else root.HLCauses = API;
})(typeof window !== 'undefined' ? window : globalThis);
