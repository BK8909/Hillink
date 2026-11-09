// Operator strategy A/B on the revenue screen: same customers and visit, one product condition changed.
// Reuses /api/visit, /api/ledger/compare, the revenue panels and the customer-flow handoff. No new engine.
(function () {
'use strict';
const ST = { open: false, busy: false, err: null, preset: null, ex: null, view: 'live', promoId: null, live: { src: 'rev', who: 'all', slot: 'dinner', target: '' }, cap: null, ids: null, pct: null, A: null, B: null, cmp: null, sel: null, ranPct: null };
const SANTA_SKU_PREFIX = 'C01-EVENT-SANTA';

async function call(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  const raw = await r.json().catch(() => ({}));
  const data = typeof HLWireJSON!=='undefined' ? HLWireJSON.unpack(raw) : raw;
  if (!r.ok) throw new Error(data.error || `요청 실패 (${r.status})`);
  // Match the existing visit UI's display-only normalization; keep server records intact.
  return typeof deName === 'function' ? deName(data) : data;
}
function promo() { return ST.preset.promotions.find(p => p.id === ST.promoId) || ST.preset.promotions[0]; }
async function ensure() {
  if(!ST.cap)ST.cap=await call('/api/runtime/capabilities');
  if(!ST.venueCatalog)ST.venueCatalog=await call('/api/strategy/options');
  if(!ST.events)ST.events=await call('/static/event_scenario_options.json');
  if(!ST.rooms)ST.rooms=await call('/api/room/options');
  if(!ST.customers){await libLoad();const meta=await call('/api/turn/meta');ST.customers=meta.personas.map(p=>({id:p.id,label:typeof dno==='function'?dno(p.id):p.id,type:libTypeOf(libP(p.id)||{})||'유형 미확인'}));}

}
function request(pct) {
  const P = ST.preset, F = P.fixed, vc = {}, booked = {};
  for (const f of P.booked_families) {
    vc[f.id] = { party_size: 3, party_composition: { adult_count: 2, children: [{}] } };
    if (f.building) vc[f.id].building = f.building;
    booked[f.id] = { date: F.start_date, start: F.booked_start };
  }
  return {
    personas: ST.ids, duration: F.duration, seed: F.seed, start_date: F.start_date, include_ledger: true, behavior_engine: F.behavior_engine,
    scenario: { event_card_id: 'SANTA_KIDS_VILLAGE_2025', assumptions: { ...structuredClone(F.scenario_assumptions), booked_sessions: booked }, arrival_time: F.arrival_time },
    visit_conditions: vc, catalog_policy: ST.cap.catalog_policy || 'C01_HOTEL_CATALOG_V1',
    catalog_options: pct ? { discount_percent: { [promo().sku_id]: pct } } : {}
  };
}
async function runAB() {
  if (ST.busy) return;
  ST.busy = true; ST.err = null; ST.sel = null; draw();
  try {
    await ensure();
    const pct = ST.pct;
    const [A, B] = await Promise.all([call('/api/visit', request(0)), call('/api/visit', request(pct))]);
    if (A.ledger.source !== 'live_engine' || B.ledger.source !== 'live_engine') throw new Error('실제 엔진 계산 결과가 아닙니다. 다시 실행해 주세요.');
    const cmp = await call('/api/ledger/compare', { baseline_id: A.ledger.run_id, scenario_id: B.ledger.run_id, event_only: false });
    if (!cmp.comparable) throw new Error(cmp.message || '두 실행을 비교할 수 없습니다.');
    Object.assign(ST, { A, B, cmp, ranPct: pct });
  } catch (e) { ST.err = e.message; }
  finally { ST.busy = false; draw(); }
}

// ---- derived facts (all from the two ledgers and their decision traces) ----
const scoreOf = c => (c.final_with_lookahead != null ? c.final_with_lookahead : c.final_score);
function rowsOf(flow, pid) { return ((flow.ledger.receipts[pid] || {}).rows) || []; }
function buyers(flow) { const sku = promo().sku_id; return Object.keys(flow.ledger.receipts).filter(pid => rowsOf(flow, pid).some(r => r.sku_id === sku)); }
function santaTeams(flow) { return Object.keys(flow.ledger.receipts).filter(pid => rowsOf(flow, pid).some(r => String(r.sku_id || '').startsWith(SANTA_SKU_PREFIX))); }
function promoDiscount(flow) { const sku = promo().sku_id; return Object.values(flow.ledger.receipts).flatMap(r => r.rows).filter(r => r.sku_id === sku).reduce((n, r) => n + (r.discount_krw || 0), 0); }
function famFnbDelta() { return ST.preset.booked_families.reduce((n, f) => n + ((ST.cmp.customers[f.id] || {}).departments || []).filter(d => d.name === 'F&B').reduce((m, d) => m + d.delta_krw, 0), 0); }
function deptDelta(name) { return Object.values(ST.cmp.customers).flatMap(c => c.departments).filter(d => d.name === name).reduce((n, d) => n + d.delta_krw, 0); }
// One definition for every place that counts customers.
function groups() {
  const switched = [], priceOnly = [], knockOn = [];
  for (const [pid, c] of Object.entries(ST.cmp.customers)) {
    if (!c.changed) continue;
    if ((c.transitions || []).length) switched.push(pid);
    else if ((c.decomposition || {}).price_condition) priceOnly.push(pid);
    else knockOn.push(pid);
  }
  const booked = ST.preset.booked_families.map(f => f.id);
  const menuOnly = switched.filter(pid => ST.cmp.customers[pid].transitions.every(t => t.before_venue === t.after_venue));
  return { switched, priceOnly, knockOn, menuOnly, venueSwitched: switched.filter(p => !menuOnly.includes(p)), affected: [...switched, ...priceOnly, ...knockOn], booked, bookedSwitched: switched.filter(p => booked.includes(p)) };
}
function kindOf(pid) { const g = groups(); return g.menuOnly.includes(pid) ? '같은 식당 메뉴 변경' : g.switched.includes(pid) ? '식당 선택 변경' : g.priceOnly.includes(pid) ? '기존 선택 유지 · 할인만' : '후속 일정만 변경'; }
function isBooked(pid) { return ST.preset.booked_families.some(f => f.id === pid); }
function label(pid) { const r = ST.B.ledger.receipts[pid] || ST.A.ledger.receipts[pid] || {}; return `${r.display_id || pid}`; }
function typeOf(pid) { const r = ST.B.ledger.receipts[pid] || {}; return isBooked(pid) ? '산타 예약 가족' : (r.customer_type || '일반 방문'); }
function decisions(flow, pid) {
  const days = flow.visit_days ? flow.visit_days.map(d => d.flow) : [flow];
  return days.flatMap(d => (((d.plans || {})[pid] || {}).m4 || {}).decisions || []);
}
// The dinner decision in which the promoted product was a real candidate.
// Prefer the decision that actually chose a meal; otherwise the first one where the product competed.
function promoDecision(flow, pid) {
  const sku = promo().sku_id, found = [];
  for (const dec of decisions(flow, pid)) {
    const cs = dec.packet.candidates;
    const promo = cs.find(c => c.product_quote && c.product_quote.components && c.product_quote.components[0].sku_id === sku);
    if (!promo) continue;
    const sid = dec.selected_action && dec.selected_action.candidate_id || dec.selected_action;
    const win = cs.find(c => c.candidate_id === sid) || null;
    found.push({ promo, win });
  }
  return found.find(d => d.win && (d.win.meal_fraction || 0) >= 0.8) || found[0] || null;
}
function terms(c) { return ((c && c.score_contribution && c.score_contribution.terms) || []); }
function termValue(c, factor) { const t = terms(c).find(x => x.factor === factor); return t ? t.actual : null; }
function pp(c) { const s = c.scoring_input_contract || {}; return s.participant_count ? Math.round((s.order_net_krw || 0) / s.participant_count) : null; }

// ---- rendering ----
const money = n => (typeof rcMoney === 'function' ? rcMoney(n) : `${Number(n).toLocaleString('ko-KR')}원`);
const delta = n => (typeof rcDelta === 'function' ? rcDelta(n) : `${n > 0 ? '+' : ''}${n}`);
const e = s => (typeof esc === 'function' ? esc(String(s)) : String(s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]));
const fx = n => (n == null ? '—' : Number(n).toFixed(3));

function inputsHTML() {
  const P = ST.preset, F = P.fixed;
  const opts = promo().options_percent.map(p => `<option value="${p}"${p === ST.pct ? ' selected' : ''}>${p}% 할인</option>`).join('');
  return `<section class="rev-console-panel st-ab-inputs"><div class="rev-console-heading"><h3>운영자 입력</h3><span class="cf-sub">A와 B는 아래 조건이 모두 같고, 상품 조건 하나만 다릅니다</span></div>
  <div class="st-ab-cols"><div><h4>고정 조건 (A·B 동일)</h4><ul class="st-ab-list">
    <li>2025 산타 키즈빌리지 · ${e(F.start_date)} · 1박 2일 · 시드 ${F.seed}</li>
    <li>실행 가능 고객 ${ST.ids ? ST.ids.length : 28}팀 · 도착 ${e(F.arrival_time)}</li>
    <li>산타 ${e(F.booked_start)} 회차(2025 공식 회차) 사전 예약 가족 ${P.booked_families.length}팀 <small>(운영자 가정)</small></li>
  </ul><details><summary>예약 가족 설정 근거 ${P.booked_families.length}팀 · 시나리오 설정용(선택 점수 미사용)</summary><ul class="st-ab-list">${P.booked_families.map(f => `<li><b>${e(f.id)}</b> ${e(f.basis)} · ${e(f.note)}</li>`).join('')}</ul><p class="rc-note">${e(P.basis_role_note || '')}</p></details></div>
  <div><h4>변경 조건 (B만)</h4><p><select data-st-promo aria-label="전략"${ST.busy ? ' disabled' : ''}>${P.promotions.map(x => `<option value="${e(x.id)}"${x.id === promo().id ? ' selected' : ''}>${e(x.id)} · ${e(x.label)}</option>`).join('')}</select></p>
    <p><b>${e(promo().label)}</b> 기존 ${money(promo().base_price_krw)}/${e(promo().price_unit || '인')} · <select data-st-pct aria-label="할인율"${ST.busy ? ' disabled' : ''}>${opts}</select></p>
    <p class="rc-note">운영자 가상 프로모션 · 공식 가격 아님. 대상 상품은 ${e(promo().target_rule)}</p>
    <button type="button" class="cf-btn cf-primary" data-st-run${ST.busy ? ' disabled' : ''}>${ST.busy ? 'A·B 계산 중…' : ST.A ? '다시 실행' : 'A·B 실행'}</button></div></div></section>`;
}
function summaryHTML() {
  const { A, B, cmp } = ST, g = groups();
  const bA = buyers(A), bB = buyers(B), sA = santaTeams(A), sB = santaTeams(B);
  const card = (cls, k, v, sub) => `<article class="${cls}"><div><small>${k}</small><strong>${v}</strong><span>${sub}</span></div></article>`;
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>1 · 전략 요약</h3><span class="cf-sub">A ${e(A.ledger.run_id.slice(0, 8))} · B ${e(B.ledger.run_id.slice(0, 8))} · ${ST.ranPct}% 할인</span></div>
  <div class="rev-command-kpis st-ab-kpis">
    ${card('kpi-room', '목표 지표 · 예약 가족 F&B 가상 결제', delta(famFnbDelta()), `산타 예약 가족 선택 변화 ${g.bookedSwitched.length} / ${g.booked.length}팀 · 산타 참가 A ${sA.length} · B ${sB.length}팀`)}
    ${card('kpi-total', '보호 지표 · 호텔 전체 가상 결제', delta(cmp.delta_krw), `${money(cmp.before_krw)} → ${money(cmp.after_krw)}`)}
    ${g.menuOnly.length ? card('kpi-leisure', '설명 · 선택이 바뀐 고객', `${g.switched.length}팀`, `식당 변경 ${g.venueSwitched.length}팀 · 같은 식당 메뉴 변경 ${g.menuOnly.length}팀 · 할인만 ${g.priceOnly.length}팀${g.knockOn.length ? ` · 후속 일정만 ${g.knockOn.length}팀` : ''} · 영향 총 ${g.affected.length}팀 / ${Object.keys(cmp.customers).length}팀`)
      : card('kpi-leisure', '설명 · 식당 선택이 바뀐 고객', `${g.switched.length}팀`, `할인만 받은 고객 ${g.priceOnly.length}팀${g.knockOn.length ? ` · 후속 일정만 ${g.knockOn.length}팀` : ''} · 영향 총 ${g.affected.length}팀 / ${Object.keys(cmp.customers).length}팀`)}
    ${card('kpi-fnb', '설명 · F&B 전체 가상 결제', delta(deptDelta('F&B')), `할인 부담 ${money(promoDiscount(B))} 포함 · 프로모션 상품 선택 ${bA.length} → ${bB.length}팀`)}
  </div></section>`;
}
function customersHTML() {
  const { cmp } = ST, rows = [];
  for (const [pid, c] of Object.entries(cmp.customers)) {
    if (!c.changed) continue;
    const tr = (c.transitions || []).map(t => `${e(t.before_venue)} · ${e(t.before_product)} <span aria-hidden="true">→</span> <b>${e(t.after_venue)} · ${e(t.after_product)}</b> <small>${e((t.before_decision_id || '').split('|').pop())}→${e((t.after_decision_id || '').split('|').pop())}</small>`).join('<br>');
    const other = (c.activity_changes || []).filter(a => a.slot !== 'dinner').map(a => `${e((a.before || {}).label || '없음')} → ${e((a.after || {}).label || '없음')}`).slice(0, 3).join(' · ');
    const d = c.decomposition || {};
    rows.push(`<tr class="${ST.sel === pid ? 'on' : ''}"><th><button type="button" class="cf-link" data-st-sel="${e(pid)}">${e(label(pid))}</button><small>${e(typeOf(pid))} · ${e(kindOf(pid))}</small></th>
      <td>${tr || '같은 업장 · 가격 조건만 변경'}${other ? `<br><small>연쇄 변화: ${other}</small>` : ''}</td>
      <td class="num">${delta(c.delta_krw)}<small>이동 ${delta(d.selection || 0)} · 가격 ${delta(d.price_condition || 0)} · 연쇄 ${delta(d.interaction || 0)}</small></td>
      <td><button type="button" class="cf-link" data-st-flow="${e(pid)}" data-run="A">A 흐름</button> · <button type="button" class="cf-link" data-st-flow="${e(pid)}" data-run="B">B 흐름</button></td></tr>`);
  }
  const kept = ST.preset.booked_families.map(f => f.id).filter(pid => cmp.customers[pid] && !cmp.customers[pid].changed).map(pid => {
    const d = promoDecision(ST.B, pid);
    const gap = d && d.win ? scoreOf(d.win) - scoreOf(d.promo) : null;
    return `<li><button type="button" class="cf-link" data-st-sel="${e(pid)}">${e(label(pid))}</button> ${d && d.win ? `${e(d.win.candidate_label)} 유지 · 할인 후에도 ${e(promo().label)}보다 ${fx(gap)}점 높음` : '저녁을 고를 때 프로모션 상품이 후보에 없었음(영업 시간 전 결정 등)'}</li>`;
  }).join('');
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>2 · 고객별 선택 변화</h3><span class="cf-sub">${groups().menuOnly.length ? `식당 변경 ${groups().venueSwitched.length} · 같은 식당 메뉴 변경 ${groups().menuOnly.length}` : `식당 선택 변경 ${groups().switched.length}`} · 할인만 ${groups().priceOnly.length} · 영향 총 ${groups().affected.length}팀 · A 선택 → B 선택</span></div>
  ${rows.length ? `<table class="rev-table st-ab-table"><thead><tr><th>고객</th><th>바뀐 결정</th><th>가상 결제 변화</th><th>지도·장면</th></tr></thead><tbody>${rows.join('')}</tbody></table>` : '<p class="rc-note">두 실행에서 행동이 바뀐 고객이 없습니다.</p>'}
  ${kept ? `<h4>선택을 유지한 산타 예약 가족</h4><ul class="st-ab-list">${kept}</ul>` : ''}</section>`;
}
function venuesHTML() {
  const { cmp } = ST, list = cmp.venues.filter(v => v.delta_krw || v.before_teams !== v.after_teams).sort((a, b) => a.delta_krw - b.delta_krw);
  const max = Math.max(1, ...list.map(v => Math.abs(v.delta_krw)));
  const parts = Object.values(cmp.customers).reduce((s, c) => { for (const k of ['selection', 'price_condition', 'time_rule', 'interaction']) s[k] += (c.decomposition || {})[k] || 0; return s; }, { selection: 0, price_condition: 0, time_rule: 0, interaction: 0 });
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>3 · 업장별 가상 결제 변화</h3><span class="cf-sub">감소 · 이동 · 추가를 같은 원장에서 분리</span></div>
  <ol class="rev-chart rev-delta-chart st-ab-delta" aria-label="업장별 가상 결제 변화">${list.map(v => { const w = Math.min(50, 50 * Math.abs(v.delta_krw) / max), left = v.delta_krw < 0 ? 50 - w : 50; return `<li><span class="st-ab-name">${e(typeof rcVenueName === 'function' ? rcVenueName(v.name) : v.name)}<small>${v.before_teams} → ${v.after_teams}팀</small></span><span class="st-ab-bar"><i class="${v.delta_krw < 0 ? 'neg' : 'pos'}" style="left:${left}%;width:${w}%"></i></span><b>${delta(v.delta_krw)}</b></li>`; }).join('')}</ol>
  <table class="rev-table st-ab-parts"><tbody>
    <tr><th>선택 이동</th><td>다른 업장·상품으로 바꾼 결정의 차액</td><td class="num">${delta(parts.selection)}</td></tr>
    <tr><th>가격 조건</th><td>같은 상품을 그대로 사고 할인만 받은 차액</td><td class="num">${delta(parts.price_condition)}</td></tr>
    <tr><th>연쇄 변화</th><td>저녁 시각이 바뀌며 뒤 일정(바·휴식 등)이 달라진 차액</td><td class="num">${delta(parts.interaction + parts.time_rule)}</td></tr>
    <tr><th>합계</th><td>호텔 전체 가상 결제 L5 = L1</td><td class="num"><b>${delta(cmp.delta_krw)}</b></td></tr>
  </tbody></table></section>`;
}
function hotelHTML() {
  const { A, B } = ST;
  const L2 = f => Object.fromEntries((f.ledger.levels.L2 || []).map(g => [g.key[0], g.paid_krw]));
  const a = L2(A), b = L2(B), depts = [...new Set(['ROOM', 'F&B', '레저', ...Object.keys(a), ...Object.keys(b)])];   // every L2 row, so the rows add up to L1
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>4 · 호텔 전체 가상 결제 (L5 → L1)</h3><span class="cf-sub">할인으로 줄어든 단가까지 반영한 실제 결제액 차이</span></div>
  <table class="rev-table"><thead><tr><th>구분</th><th>A 기준</th><th>B 전략</th><th>차이</th></tr></thead><tbody>
  ${depts.filter(k => (a[k] || 0) !== 0 || (b[k] || 0) !== 0 || ['ROOM', 'F&B', '레저'].includes(k)).map(k => `<tr><th>${e(k)}${k === 'ROOM' ? '<small>객실 1박 + 룸서비스(IRD)</small>' : k === 'F&B' ? '<small>업장 식음 · 룸서비스 제외</small>' : ''}</th><td class="num">${money(a[k] || 0)}</td><td class="num">${money(b[k] || 0)}</td><td class="num">${delta((b[k] || 0) - (a[k] || 0))}</td></tr>`).join('')}
  <tr><th>L1 호텔</th><td class="num">${money(A.ledger.totals.paid_krw)}</td><td class="num">${money(B.ledger.totals.paid_krw)}</td><td class="num"><b>${delta(B.ledger.totals.paid_krw - A.ledger.totals.paid_krw)}</b></td></tr>
  </tbody></table><p class="rc-note">시뮬레이션 표본 28팀의 가상 결제액입니다. 회계상 순매출이나 워커힐 실제 매출·매출 예측이 아닙니다. 원가·좌석 수용·실제 방문객 수가 없어 이익은 계산하지 않습니다.</p></section>`;
}
function detailHTML() {
  const pid = ST.sel; if (!pid) return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>5 · 행동근거 상세</h3></div><p class="rc-note">고객을 선택하면 저녁 결정의 후보 점수와 근거를 A·B로 나란히 봅니다.</p></section>`;
  const side = (flow, tag) => {
    const d = promoDecision(flow, pid);
    if (!d) return `<div><h4>${tag}</h4><p class="rc-note">프로모션 상품이 후보에 없던 방문입니다.</p></div>`;
    const facts = c => [...new Set(terms(c).flatMap(t => t.fact_ids || []))];
    const row = (name, c) => c ? `<tr><th>${e(name)}</th><td>${e(c.candidate_label)}</td><td class="num">${fx(scoreOf(c))}</td><td class="num">${pp(c) != null ? money(pp(c)) : '—'}</td><td class="num">${fx(termValue(c, '1인 지불액'))}</td><td>${facts(c).map(e).join(', ') || '공통 규칙만'}</td></tr>` : '';
    const same = d.win && d.win.candidate_id === d.promo.candidate_id;
    return `<div><h4>${tag} · 선택: ${e(d.win ? d.win.candidate_label : '미기록')}</h4><table class="rev-table st-ab-score"><thead><tr><th></th><th>후보</th><th>최종 점수</th><th>1인 지불</th><th>가격 항</th><th>개인 Fact</th></tr></thead><tbody>${same ? row('선택 = 프로모션', d.promo) : row('선택', d.win) + row('프로모션 상품', d.promo)}</tbody></table></div>`;
  };
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>5 · 행동근거 상세 · ${e(label(pid))}</h3><span class="cf-sub">${e(typeOf(pid))} · 같은 상태에서 가격 조건만 다름</span></div>
  <div class="st-ab-cols">${side(ST.A, 'A 기준')}${side(ST.B, 'B 전략')}</div>
  <p class="rc-note">할인은 선택 전 후보 점수의 '1인 지불액' 항으로 들어갑니다. 결정 시각이 같으면 다른 항은 그대로이고, 시각이 달라지면 기다림·상태 항도 함께 달라질 수 있어 표의 값을 그대로 비교합니다. 선택은 같은 엔진의 점수 비교로 정해지며 구매를 강제하지 않습니다.</p>
  <p><button type="button" class="cf-btn" data-st-flow="${e(pid)}" data-run="B">B 흐름에서 이 고객 보기</button> <button type="button" class="cf-btn" data-st-flow="${e(pid)}" data-run="A">A 흐름에서 보기</button></p></section>`;
}
function proposalHTML() {
  const { cmp } = ST, g = groups(), fam = g.bookedSwitched;
  const lines = [];
  lines.push(`${ST.ranPct}% 할인에서 식당 선택이 바뀐 고객은 ${g.switched.length}팀, 기존 선택을 유지하고 할인만 받은 고객은 ${g.priceOnly.length}팀으로 영향을 받은 고객은 총 ${g.affected.length}팀입니다. 산타 예약 가족의 선택 변화는 ${fam.length}/${g.booked.length}팀입니다.`);
  const pairs = {};
  for (const pid of g.switched) for (const t of cmp.customers[pid].transitions || []) { const k = t.before_venue === t.after_venue ? `${t.after_venue} 안에서 ${t.after_product}(으)로 메뉴 변경` : `${t.before_venue} → ${t.after_venue} 이동`; pairs[k] = (pairs[k] || 0) + 1; }
  const top = Object.entries(pairs).sort((a, b) => b[1] - a[1])[0];
  const famFnb = g.booked.reduce((n, pid) => n + ((cmp.customers[pid] || {}).departments || []).filter(d => d.name === 'F&B').reduce((m, d) => m + d.delta_krw, 0), 0);
  lines.push(`${promo().label} ${ST.ranPct}% 할인${top ? `에서 가장 많은 변화는 ${top[0]}(${top[1]}팀)이고` : '은 식당 선택을 바꾸지 않았고'}, 호텔 전체 가상 결제액은 ${cmp.delta_krw < 0 ? '감소했습니다' : cmp.delta_krw > 0 ? '늘었습니다' : '변하지 않았습니다'}(${delta(cmp.delta_krw)}). 산타 예약 가족의 F&B 가상 결제 변화는 ${delta(famFnb)}입니다.`);
  const rec = promo().recorded;
  if (promo().interpretation && rec && rec.percent === ST.ranPct && rec.delta_krw === cmp.delta_krw && ST.A.ledger.totals.paid_krw === rec.baseline_paid_krw) lines.push(`해석: ${promo().interpretation}`);
  if (!fam.length) {
    const gaps = [], lift = [];
    for (const f of ST.preset.booked_families) {
      const a = promoDecision(ST.A, f.id), b = promoDecision(ST.B, f.id);
      if (b && b.win && b.win.candidate_id !== b.promo.candidate_id) gaps.push(scoreOf(b.win) - scoreOf(b.promo));
      if (a && b) { const x = termValue(a.promo, '1인 지불액'), y = termValue(b.promo, '1인 지불액'); if (x != null && y != null) lift.push(y - x); }
    }
    const lo = gaps.length ? Math.min(...gaps) : null, hi = gaps.length ? Math.max(...gaps) : null, up = lift.length ? Math.max(...lift) : null;
    lines.push(`근거: 할인 뒤에도 예약 가족의 남은 점수 차는 ${gaps.length ? `${fx(lo)}~${fx(hi)}점` : '측정 불가'}이고, 할인이 만든 가격 항 변화는 최대 +${fx(up)}점입니다. 아동 메뉴처럼 가족 구성에 맞는 조건은 아직 검증하지 않은 다음 가설입니다.`);
  }
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>운영 제안 · 근거와 한계</h3></div><ul class="st-ab-list">${lines.map(l => `<li>${e(l)}</li>`).join('')}</ul>
  <details><summary>이 실험의 가정</summary><ul class="st-ab-list">${ST.preset.notes.map(n => `<li>${e(n)}</li>`).join('')}</ul></details></section>`;
}

// ---- strategy exploration (goal → opportunity → candidates → same-customer comparison → verdict) ----
// Reads the recorded exploration (strategy_santa_explore.json, built from real engine runs). Computed
// strategies can be recomputed live in the A/B tab; numbers there come from the engine, not from this file.
const VERDICT = { NOT_RECOMMENDED: ['비권장', 'neg'], HOLD: ['보류', 'hold'], RECOMMENDED: ['권장', 'pos'] };
const STATUS = { COMPUTED: '엔진 계산 완료', ENGINE_LIMIT: '실행했으나 엔진 제약 · 판단 제외', NOT_COMPUTABLE: '현재 엔진으로 계산 불가' };
function badge(v) { const [t, c] = VERDICT[v] || [v, 'hold']; return `<span class="st-ex-badge ${c}">${e(t)}</span>`; }
function exploreHTML(archive) {
  const X = ST.ex; if (!X) return '<p class="rc-note">전략 분석 기록을 불러오는 중…</p>';
  const G = X.goal, O = X.opportunity, S = O.summary, L = X.screen.levels, gaps = O.rows.filter(r => r.gap != null).map(r => r.gap);
  const fam = O.rows.map(r => `<tr><th>${e(r.customer_id)}<small>${e(r.chosen_venue === 'PIZZA_HILL' ? '피자힐' : r.chosen_venue === 'ROOM_MEAL' ? '룸서비스' : r.chosen_venue)} · ${e(r.chosen)}</small></th>
    <td class="num">${e(r.decision_time)}</td><td>${e(r.barrier_text)}</td>
    <td class="num">${r.gap != null ? fx(r.gap) : '—'}</td><td class="num">${r.price_part != null ? fx(r.price_part) : '—'}</td>
    <td>${r.largest_nonprice ? `${e(r.largest_nonprice)} ${fx(r.largest_nonprice_value)}` : '—'}</td>
    <td class="num">${r.break_even_discount_pct != null ? (r.break_even_discount_pct > 100 ? '100% 넘음' : `${r.break_even_discount_pct}%`) : '후보 아님'}</td></tr>`).join('');
  const lv = ['10', '20', '30'].map(k => `<li>${k}% 할인: 가족을 움직이는 상품 <b>${L[k].skus_moving_family}개</b> · 그중 가족 결제가 늘어나는 상품 <b>${L[k].skus_family_spend_up}개</b></li>`).join('');
  const cards = X.strategies.map(s => `<article class="st-ex-card"><header><b>${e(s.id)} · ${e(s.title)}</b>${badge(s.verdict)}</header>
    <p><small>${e(s.lever)} · ${e(STATUS[s.status] || s.status)}</small></p><p>근거: ${e(s.why)}</p><p class="rc-note">${e(s.note)}</p>
    ${s.status === 'COMPUTED' ? `<button type="button" class="cf-btn" data-st-rerun="${e(s.id)}"${ST.busy ? ' disabled' : ''}>같은 조건으로 A/B 다시 계산</button>` : ''}</article>`).join('');
  const comp = X.strategies.filter(s => s.metrics).map(s => { const m = s.metrics, off = s.status !== 'COMPUTED';
    return `<tr class="${off ? 'st-ex-off' : ''}"><th>${e(s.id)}<small>${e(s.title)}</small></th>
    <td class="num">${off ? '—' : `<b>${delta(m.fam_fnb)}</b>`}</td><td class="num">${off ? `<s>${delta(m.total)}</s>` : delta(m.total)}</td><td class="num">${off ? '—' : delta(m.dept['F&B'] || 0)}</td><td class="num">${off ? '—' : `${m.fam_changed.length} / 6`}</td><td class="num">${off ? '—' : `${m.other_changed.length}팀`}</td>
    <td class="num">${m.santa.length} / 6</td><td><code>${e(m.run.slice(0, 8))}</code></td><td>${badge(s.verdict)}</td></tr>`; }).join('');
  const s2 = X.strategies.find(s => s.id === 'S2'), R = X.recommendation;
  return `<section class="rev-console-panel"><div class="rev-console-heading"><h3>① 운영 목표</h3><span class="cf-sub">${e(G.event)}</span></div>
    <p><b>${e(G.text)}</b></p><ul class="st-ab-list"><li>대상: ${e(G.target)}</li><li>지표: ${e(G.metric)}</li><li>제약: ${G.constraints.map(e).join(' · ')}</li></ul>
    <p class="rc-note">기준 실행 <code>${e(X.baseline.run_id.slice(0, 8))}</code> · 호텔 전체 ${money(X.baseline.paid_krw)}</p></section>
  <section class="rev-console-panel"><div class="rev-console-heading"><h3>② 현재 행동에서 찾은 기회</h3><span class="cf-sub">기준 실행의 가족 6팀 저녁 결정 기록 · 금룡 삼선 자장면(저녁)과 비교</span></div>
    <div class="rev-command-kpis st-ab-kpis">
      <article class="kpi-total"><div><small>시간이 막은 가족</small><strong>${S.time_barrier} / ${S.families}팀</strong><span>18:00 전 결정 ${S.decision_before_1800}팀 · 영업 종료 무렵 ${S.time_barrier - S.decision_before_1800 > 0 ? S.time_barrier - S.decision_before_1800 : 0}팀 포함</span></div></article>
      <article class="kpi-fnb"><div><small>20% 할인이 만드는 점수</small><strong>+${fx(S.twenty_pct_gain)}</strong><span>남은 점수 차 ${fx(Math.min(...gaps))} ~ ${fx(Math.max(...gaps))}</span></div></article>
      <article class="kpi-leisure"><div><small>선택을 뒤집는 할인율 (1차 추정)</small><strong>${Math.round(S.break_even_min)}% 이상</strong><span>가격 항만 바뀐다고 본 근사 · 확정 손익분기 아님 · 가족 ${gaps.length}팀 · 최대 ${S.break_even_max > 100 ? '100% 초과' : S.break_even_max + '%'}</span></div></article>
      <article class="kpi-room"><div><small>가장 큰 비가격 항목</small><strong>공간·분위기</strong><span>피자힐이 금룡보다 높은 가족 ${S.space_barrier}팀</span></div></article></div>
    <table class="rev-table st-ab-table st-ex-opp"><thead><tr><th>가족 · 실제 선택</th><th>결정 시각</th><th>금룡을 고르지 않은 이유</th><th>점수 차</th><th>가격 항 차</th><th>가장 큰 비가격 항</th><th>필요 할인율</th></tr></thead><tbody>${fam}</tbody></table>
    <h4>가격 후보 사전 선별 · 기존 단품 ${L['20'].skus}개</h4><ul class="st-ab-list">${lv}</ul>
    <p class="rc-note">${e(X.screen.rule)}. ${e(X.screen.caveat)}</p></section>
  <section class="rev-console-panel"><div class="rev-console-heading"><h3>③ 전략 후보</h3><span class="cf-sub">계산한 전략과 계산할 수 없는 가설을 구분</span></div><div class="st-ex-cards">${cards}</div></section>
  <section class="rev-console-panel"><div class="rev-console-heading"><h3>④ 같은 고객 · 같은 조건 비교</h3><span class="cf-sub">기준(A) 대비 · 28팀 · 시드 0 · 가중치 고정</span></div>
    <table class="rev-table st-ab-table"><thead><tr><th>전략</th><th>예약 가족 F&amp;B<small>목표 지표</small></th><th>호텔 전체<small>보호 지표</small></th><th>F&amp;B</th><th>가족 선택 변화</th><th>일반 고객 변화</th><th>산타 참가</th><th>실행 ID</th><th>판정</th></tr></thead><tbody>${comp}</tbody></table>
    ${s2 && s2.prediction ? `<p class="rc-note">사전 계산과 본실행의 일관성: S2는 실행 전 가족 ${s2.prediction.families}팀 · ${delta(s2.prediction.family_delta)}로 계산했고, 엔진 실행 결과는 가족 ${s2.metrics.fam_changed.length}팀 · ${delta(s2.metrics.fam_fnb)}입니다. 같은 점수식·같은 고객을 쓴 계산이므로 독립적인 예측 정확도 검증은 아닙니다.</p>` : ''}
    <p class="rc-note">T1·T2는 산타 참가가 0/6이 되어 전략 효과가 아니라 엔진 제약이 결과를 좌우했습니다. 금액은 취소선으로 표시하고 판단에서 제외합니다.</p></section>
  ${X.official && !archive ? `<section class="rev-console-panel"><div class="rev-console-heading"><h3>공식 회차 재검증 · PR #126</h3><span class="cf-sub">${e(X.session_basis.official.sessions.join(' · '))} · 예약 ${e(X.session_basis.official.booked)} · 기준 <code>${e(X.official.baseline.run_id.slice(0, 8))}</code> ${money(X.official.baseline.paid_krw)}</span></div>
    <p class="rc-note">${e(X.official.baseline.check)}. 위 ①~④의 S1·S2·T1·T2 기록은 모델 가정 회차(${e(X.session_basis.model.sessions.join(' · '))}, 예약 ${e(X.session_basis.model.booked)})이며 덮어쓰지 않았습니다.</p>
    <table class="rev-table st-ab-table"><thead><tr><th>전략</th><th>예약 가족 F&amp;B<small>목표 지표</small></th><th>호텔 전체<small>보호 지표</small></th><th>가족 선택 변화</th><th>일반 고객 변화</th><th>산타 참가</th><th>실행 ID</th></tr></thead><tbody>
    ${X.official.runs.map(r => `<tr><th>${e(r.id)}<small>${e(r.title)}</small></th><td class="num"><b>${delta(r.metrics.fam_fnb)}</b></td><td class="num">${delta(r.metrics.total)}</td><td class="num">${r.metrics.fam_changed.length} / 6</td><td class="num">${r.metrics.other_changed.length}팀</td><td class="num">${r.metrics.santa.length} / 6</td><td><code>${e(r.metrics.run.slice(0, 8))}</code></td></tr>`).join('')}</tbody></table>
    <p class="rc-note">${e(X.official.note)} B3는 3인 예약 가족이 고정 2인 세트 대상이 아니어서 '3인 가족 조건에서 실행 가능한 대상 없음'입니다(전략 효과 0으로 일반화하지 않음).</p>
    ${X.official.reconciliation ? (() => { const R = X.official.reconciliation, A = R.A; return `<details><summary>정합성 대조 · 현재 정책(외부 배달 기본) 재실행</summary>
      <table class="rev-table st-ab-table st-ex-opp"><tbody>
      <tr><th>공통 조건</th><td>${e(A.customers.length)}팀 · 시드 ${e(A.seed)} · ${e(A.date)} · ${e(A.duration)} · 도착 ${e(A.arrival)} · 회차 ${e(A.sessions.map(x => x[0]).join(' · '))} · 예약 가족 ${e(Object.keys(A.booked).length)}팀(${e(Object.values(A.booked)[0].start)}) · 동행 성인 2·아동 1</td></tr>
      <tr><th>기준 A</th><td><code>${e(A.run_id.slice(0, 12))}</code> · ${money(A.paid_krw)} · 산타 참가 ${A.santa.length}/6 · 외부 배달 ${A.external_spend.count || 0}건</td></tr>
      ${['S1', 'S2'].map(k => { const r = R[k], fam = r.changed_customers.filter(c => c.booked); return `<tr><th>${k}</th><td><code>${e(r.run_id.slice(0, 12))}</code> · ${money(r.paid_krw)} · 입력 차이 ${r.input_diff_vs_A.map(d => `${e(d.path)} = ${e(JSON.stringify(d.B))}`).join(', ')} · 고객 목록 동일 ${r.same_customers ? '예' : '아니오'} · 변화 고객 ${r.changed_customers.length}팀(산타 가족 ${fam.length}팀 · 가족 F&amp;B ${delta(fam.reduce((n, c) => n + c.fnb_delta_krw, 0))}) · 원장 L2 ${Object.entries(r.L2_delta).filter(([, v]) => v).map(([g, v]) => `${e(g)} ${delta(v)}`).join(' · ') || '변화 없음'} · 비교 ${delta(r.compare.delta)}</td></tr>`; }).join('')}
      </tbody></table><p class="rc-note">14:00 모델 가정 회차 결과와는 다른 실험입니다.</p></details>`; })() : ''}
    ${X.official.delivery_recheck ? `<p class="rc-note">외부 배달 기본 정책 재실행 · 기준 <code>${e(X.official.delivery_recheck.baseline.run_id.slice(0, 8))}</code> ${money(X.official.delivery_recheck.baseline.paid_krw)} · ${X.official.delivery_recheck.runs.map(r => `${e(r.id)} ${delta(r.metrics.total)} (가족 F&amp;B ${delta(r.metrics.fam_fnb)})`).join(' · ')} · ${e(X.official.delivery_recheck.note)}</p>` : ''}
    <h4>PR #126 전략별 상태</h4><table class="rev-table st-ab-table st-ex-opp"><thead><tr><th>항목</th><th>상태</th><th>근거</th></tr></thead><tbody>
    ${X.pr126.items.map(i => `<tr><th>${e(i.id)}<small>${e(i.title)}</small></th><td><span class="st-ex-badge ${i.status === '실행 완료' ? 'pos' : 'hold'}">${e(i.status)}</span></td><td>${e(i.basis)}</td></tr>`).join('')}</tbody></table>
    <p class="rc-note">${e(X.pr126.source)}</p></section>` : ''}
  <section class="rev-console-panel"><div class="rev-console-heading"><h3>⑤ 판정과 운영 제안</h3></div>
    <p><b>${e(R.headline)}</b></p><h4>실험에서 배운 것</h4><ul class="st-ab-list">${R.learned.map(x => `<li>${e(x)}</li>`).join('')}</ul>
    <h4>다음으로 검증할 전략 <small>(실험 전 후보 · 효과가 검증된 추천안 아님)</small></h4><ul class="st-ab-list">${R.next.map(x => `<li>${e(x)}</li>`).join('')}</ul>
    <h4>현장 검증 방법</h4><ul class="st-ab-list">${R.field.map(x => `<li>${e(x)}</li>`).join('')}</ul>
    <details><summary>한계</summary><ul class="st-ab-list">${R.limits.map(x => `<li>${e(x)}</li>`).join('')}</ul></details></section>`;
}

// ---- live decision-cause analysis of a run that exists now (never the stored Santa numbers) ----
const VN = v => ({DOUGLAS_LOUNGE:'더글라스 라운지',CLUB_LOUNGE:'클럽 라운지',LE_PASSAGE:'르 파사쥬',THE_PAVILION:'더 파빌리온',IRD:'룸서비스',DELVINO:'델비노',GEUMRYONG:'금룡',PIZZA_HILL:'피자힐',MOEGI:'모에기',ONDAL:'온달',MYONGWOLGWAN:'명월관',THE_BUFFET:'더뷔페',EXTERNAL_DELIVERY:'외부 배달'}[v] || (v === '@room' ? '객실' : v === 'ROOM_MEAL' ? '룸서비스' : typeof agPlaceName === 'function' ? agPlaceName(v) : v));
const STC = { COMPUTABLE: 'pos', NEEDS_ENGINE: 'hold', NEEDS_DATA: 'hold', NOT_STRATEGIZABLE: 'neg' };
function liveFlow(){return currentSource()?.flow||null;}
function liveSrc(flow) { return flow && ST.A && flow.ledger.run_id === ST.A.ledger.run_id ? 'A' : 'rev'; }
function bookedIds(flow) { return Object.keys(((((flow.visit || {}).scenario_snapshot || {}).assumptions || {}).booked_sessions) || {}); }
function liveAnalysis(flow) {
  const all = Object.keys(flow.ledger.receipts || {}), booked = bookedIds(flow).filter(p => all.includes(p));
  const ids = ST.live.who === 'booked' && booked.length ? booked : all;
  let A = HLCauses.analyze(flow, ids, { slot: ST.live.slot, target_venue: ST.live.target || undefined });
  if(ST.view==='live')A=HLStrategy.opportunity(flow,A,HLStrategy.strategyGoal(CURRENT,flow)).analysis;
  return { A, S: HLCauses.summarize(A.rows, ST.cap), ids, all, booked };
}
// Tab 1 · '왜 이런 선택을 했을까?' — the run selected now (revenue run or A/B baseline), one customer at a time.
const EVL = c => (c.evidence === 'PERSONAL_FACT' ? '후기 근거' : '공통 규칙');
const DUR = { day_visit: '당일 방문', stay_1: '1박 2일', stay_2: '2박 3일', stay_3: '3박 4일' };
function runLine(flow) {
  const L = flow.ledger, ctx = L.context || {}, rc = Object.values(L.receipts || {});
  const names = rc.slice(0, 3).map(r => r.display_id).join(' · ') + (rc.length > 3 ? ` 외 ${rc.length - 3}팀` : '');
  const days = L.visit && L.visit.days ? L.visit.days.map(d => d.date) : [ctx.start_date].filter(Boolean);
  return { names, span: days.length > 1 ? `${days[0]} ~ ${days[days.length - 1]}` : (days[0] || '날짜 미기록'), dur: DUR[ctx.duration] || ctx.duration || '', event: (ST.events?.events.find(x=>x.event_card_id===flow.visit?.scenario_snapshot?.event_card_id)?.label)||ctx.event_label||(ctx.event?'와인페어':'행사 없음'), run: L.run_id, teams: rc.length };
}
// Plain-language size of a final score gap; the number itself stays in the details.
function gapWord(g) { return g == null ? '점수 차 정보 없음' : g < 0.1 ? '두 선택지의 점수가 거의 비슷했습니다' : g < 0.5 ? '선택한 쪽이 조금 앞섰습니다' : '선택한 쪽이 뚜렷하게 앞섰습니다'; }
function sumLine(c) { const pos = c.causes.filter(x => x.delta > 0).reduce((n, x) => n + x.delta, 0), neg = c.causes.filter(x => x.delta < 0).reduce((n, x) => n + x.delta, 0); return `+${fx(pos)} ${neg < 0 ? '− ' + fx(-neg) : ''}<small>= ${fx(c.gap)}${Math.abs(pos + neg - c.gap) > 0.002 ? ' · 상황 보정 포함' : ''}</small>`; }
// Amount of the meal this decision produced, read from the same run's ledger (first paid F&B/ROOM row at or after the decision).
function ledgerPaid(L, pid, r) {
  const row = (((L.receipts || {})[pid] || {}).rows || []).filter(x => x.visit_date === r.date && x.time && x.time >= r.time && x.act !== 'room_night' && (x.venue_id === r.chosen.venue || ((x.sku_contract || {}).venue_id) === r.chosen.venue)).sort((a, b) => a.time < b.time ? -1 : 1)[0];
  return row ? row.paid_krw : null;
}
function liveHTML() {
  if (typeof HLCauses === 'undefined') return '<p class="rc-note">분석 모듈을 불러오지 못했습니다.</p>';
  const flow = liveFlow();
  if (!flow) return `<section class="st-card st-empty"><h3>분석할 실행이 없습니다</h3><p>매출 집계에서 방문을 실행하거나 '직접 전략 비교하기'에서 A/B를 실행하면, 그 실행의 실제 결정 기록을 여기서 분석합니다.</p></section>`;
  const { A, S, ids, all, booked } = liveAnalysis(flow), L = flow.ledger, dn = pid => (L.receipts[pid] || {}).display_id || pid, R = runLine(flow);
  const by = {}; for (const r of A.rows) if (r.status === 'ANALYZED') (by[r.customer_id] = by[r.customer_id] || []).push(r);
  const cust = ids.filter(p => by[p]);
  if (!cust.includes(ST.live.pid)) { ST.live.pid = cust[0] || null; ST.live.ri = 0; }
  const pid = ST.live.pid, rs = by[pid] || [], r = rs[Math.min(ST.live.ri || 0, Math.max(0, rs.length - 1))];
  const srcOpt = [`<option value="rev"${liveSrc(flow) === 'rev' ? ' selected' : ''}${typeof REV !== 'undefined' && REV.flow ? '' : ' disabled'}>매출 화면에서 실행한 방문</option>`,
    `<option value="A"${liveSrc(flow) === 'A' ? ' selected' : ''}${ST.A ? '' : ' disabled'}>직접 비교의 기준 실행(A)${ST.A ? '' : ' · 미실행'}</option>`].join('');
  const sel = (k, opts) => `<select data-st-live="${k}">${opts.map(([v, t]) => `<option value="${e(v)}"${ST.live[k] === v ? ' selected' : ''}>${e(t)}</option>`).join('')}</select>`;
  const head = `<section class="st-card st-run"><div class="st-run-main"><small>이번 실행</small><b>${e(R.names)}</b><span>${e(R.span)} · ${e(R.dur)} · ${e(R.event)} · ${R.teams}팀</span></div>
    <div class="st-run-ctl"><label>분석 대상 ${`<select data-st-live="src">${srcOpt}</select>`}</label><label>식사 ${sel('slot', [['dinner', '저녁'], ['lunch', '점심']])}</label>${booked.length ? `<label>고객 ${sel('who', [['all', `전체 ${all.length}팀`], ['booked', `예약 고객 ${booked.length}팀`]])}</label>` : ''}</div>
    </section>`;
  if (!r) return head + `<section class="st-card st-empty"><p>이 실행에는 선택한 식사(${ST.live.slot === 'lunch' ? '점심' : '저녁'})의 점수 비교 기록이 없습니다.</p></section>`;
  const pick = cust.length > 1 ? `<section class="st-card st-pick"><h4>고객 선택 <small>${cust.length}팀 · 한 명씩 확인합니다</small></h4><div class="st-pick-list">${cust.map(p => { const x = by[p][0]; return `<button type="button" class="st-chip${p === pid ? ' on' : ''}" data-st-pid="${e(p)}"><b>${e(dn(p))}</b><span>${e(VN(x.chosen.venue))}</span></button>`; }).join('')}</div></section>` : '';
  const dpick = rs.length > 1 ? `<div class="st-dpick">${rs.map((x, i) => `<button type="button" class="st-chip sm${x === r ? ' on' : ''}" data-st-ri="${i}">${e(x.date.slice(5))} ${e(x.time)}</button>`).join('')}</div>` : '';
  const t = r.target || r.rival, near = r.competitors[0], Lv = HLCauses.levers(ST.cap);
  let altHTML = '<p class="st-muted">같은 시각에 고를 수 있었던 다른 업장 후보가 없습니다.</p>', why = [], cats = [], offset = '';
  if (t && t.status === 'BLOCKED') { altHTML = `<b>${e(VN(t.venue))}</b><span>후보에서 제외됨</span>`; why = t.reasons.map(x => `<li><b>${e(HLCauses.LABEL[x.category] || x.category)}</b><span>결정 시각에 이 업장을 고를 수 없었습니다</span></li>`); cats = [...new Set(t.reasons.map(x => x.category))]; }
  else if (t && t.status === 'CHOSEN') altHTML = '<p class="st-muted">비교 대상 업장을 선택했습니다.</p>';
  else if (t && t.status === 'ABSENT') altHTML = `<b>${e(VN(t.venue))}</b><span>이 결정의 후보가 아니었습니다(점수 없음)</span>`;
  else if (t) {
    altHTML = `<b>${e(VN(t.venue))} · ${e(t.label)}</b><span>${t.total_krw != null ? money(t.total_krw) + ' · ' : ''}${e(gapWord(t.gap))}</span>`;
    const top = t.causes.filter(c => c.delta > 0).slice(0, 2), against = t.causes.filter(c => c.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, 2);
    why = top.map(c => `<li><b>${e(HLCauses.LABEL[c.category] || c.factor)}</b><span>선택한 쪽이 더 높았던 항목 · ${e(EVL(c))}</span></li>`); cats = top.map(c => c.category);
    offset = against.length ? `<p class="st-muted">반대로 ${against.map(c => e(HLCauses.LABEL[c.category] || c.factor)).join('·')}은(는) 대안 쪽이 더 높았습니다. 항목끼리 상쇄된 결과 최종 차이는 '${e(gapWord(t.gap).replace(/습니다$/, '음'))}'이며, 위 항목 하나가 단독으로 선택을 결정했다는 뜻은 아닙니다.</p>` : `<p class="st-muted">위 항목은 점수에서 선택한 쪽이 더 높았던 부분입니다. 단독으로 선택을 결정했다는 뜻은 아닙니다.</p>`;
  }
  const lev = [...new Set(cats)].map(k => { const x = Lv[k] || Lv.UNCLASSIFIED; return `<li><span>${e(x.lever === '—' ? '운영으로 바꿀 수 없는 고객 요인' : x.lever)}</span><span class="st-ex-badge ${STC[x.status]}">${e(HLCauses.STATUS[x.status])}</span></li>`; }).join('');
  const sameNote = near && near.same_venue && HLStrategy.isRestaurant(near.venue) ? `<p class="st-muted">점수가 가장 가까운 대안은 같은 식당의 다른 메뉴(${e(near.label)})였습니다.</p>` : '';
  const setFacts = []; // Stored scenario setup evidence never enters current-run analysis.
  const detail = `<details class="st-more"><summary>점수 · 근거 Fact · 제외 코드 상세</summary>
    <table class="rev-table st-ab-table st-ex-opp"><thead><tr><th>후보</th><th>업장</th><th>최종 점수 차</th><th>항목별 차이 (근거)</th><th>합산</th></tr></thead><tbody>
    <tr><th>실제 선택<small>${e(r.chosen.label)}</small></th><td>${e(VN(r.chosen.venue))}</td><td class="num">—</td><td>${r.chosen.facts.length ? `근거 Fact ${e(r.chosen.facts.join(', '))}` : '공통 규칙만'}</td><td>—</td></tr>
    ${r.competitors.slice(0, 4).map(c => `<tr><th>${e(c.label)}<small>${HLStrategy.isRestaurant(c.venue)?(c.same_venue?'같은 식당':'다른 식당'):'같은 시각의 다른 활동'}</small></th><td>${e(VN(c.venue))}</td><td class="num">${fx(c.gap)}</td><td>${c.causes.filter(x => x.delta > 0).slice(0, 3).map(x => `${e(HLCauses.LABEL[x.category] || x.factor)} +${fx(x.delta)}${x.fact_ids.length ? ` <small>${e(x.fact_ids.join(', '))}</small>` : ' <small>공통 규칙</small>'}`).join('<br>') || '—'}</td><td class="num">${sumLine(c)}</td></tr>`).join('')}
    ${r.blocked.map(b => `<tr><th>${e(b.label)}<small>후보 제외</small></th><td>${e(VN(b.venue))}</td><td class="num">—</td><td>${b.reasons.map(x => `${e(HLCauses.LABEL[x.category] || x.category)} <small>${e(x.code)}</small>`).join('<br>')}</td><td>—</td></tr>`).join('')}
    </tbody></table><p class="rc-note">최종 점수 차는 선택한 쪽이 높은 항목(+)과 대안이 높은 항목(−)을 모두 더한 값입니다. 개별 항목의 크기는 그 항목이 단독으로 만든 효과가 아니며, 점수 계산은 바꾸지 않았습니다.</p>
    ${t && t.approx ? `<p class="rc-note">가격만 바꿔 이 대안을 고르게 하려면 1차 근사로 ${t.approx.break_even_discount_pct > 100 ? '100% 넘는' : t.approx.break_even_discount_pct + '%'} 할인이 필요합니다(그 후보의 가격 항만 본 근사 · 확정 손익분기 아님).</p>` : ''}
    ${setFacts.length ? `<p class="rc-note">산타 예약 가족 설정 근거 ${e(setFacts.join(', '))}는 시나리오 설정에만 썼고 이 선택 점수에는 쓰이지 않았습니다.</p>` : ''}
    ${(r.chosen.price_reference || r.competitors.some(c => c.price_reference)) ? '<p class="rc-note">외부 배달 — 실제 배달 가격: 미확인 · 점수 계산 가격: 경쟁 가능한 호텔 저녁의 최저가를 사용한 가상 비교 기준 · 고객 외부 지출: 금액 미상 · 호텔 L5~L1 매출: 0원</p>' : ''}</details>`;
  const C = S.counts;
  const all_ = `<details class="st-more"><summary>전체 고객 원인 집계 · ${ids.length}팀</summary>
    <p class="st-ex-counts">분석한 결정 ${C.analyzed} · 후보 차단 ${C.blocked} · 점수 경쟁 ${C.competed} · 가장 가까운 대안이 같은 식당 메뉴 ${C.same_venue_runner_up}</p>
    <table class="rev-table st-ab-table st-ex-opp"><thead><tr><th>원인</th><th>고객</th><th>운영 변수(실험 가능한 후보)</th><th>계산 가능 여부</th></tr></thead><tbody>${S.table.map(x => `<tr><th>${e(x.label)}</th><td class="num">${x.count}팀</td><td>${e(x.lever)}</td><td><span class="st-ex-badge ${STC[x.status]}">${e(x.status_label)}</span><small class="st-ex-basis">${e(x.basis)}</small></td></tr>`).join('') || '<tr><td colspan="4">원인 없음</td></tr>'}</tbody></table></details>`;
  return `${head}${pick}<section class="st-card st-why"><header class="st-why-head"><div><small>${e(dn(pid))} · ${e(r.date)} ${e(r.time)} 결정</small><h3>왜 ${e(VN(r.chosen.venue))}을(를) 골랐을까?</h3></div>${dpick}</header>
    <div class="st-pair"><div class="st-pair-cell chosen"><small>실제 선택</small><b>${e(VN(r.chosen.venue))} · ${e(r.chosen.label)}</b><span>${r.chosen.total_krw != null ? money(r.chosen.total_krw) : ledgerPaid(L, pid, r) != null ? `원장 가상 결제 ${money(ledgerPaid(L, pid, r))}` : ''}</span></div>
      <div class="st-pair-cell alt"><small>${t?.status==='CHOSEN'?'선택한 목표 업장':t&&HLStrategy.isRestaurant(t.venue)?'비교한 식당 후보':t?'같은 시각의 다른 활동':'비교 후보'}</small>${altHTML}</div></div>${sameNote}
    <div class="st-two"><div><h4>대안을 고르지 않은 핵심 이유</h4><ul class="st-reasons">${why.join('') || '<li><span>비교할 대안이 없습니다</span></li>'}</ul>${offset}</div>
      <div><h4>운영자가 바꿀 수 있는 조건</h4><ul class="st-levers">${lev || '<li><span>해당 없음</span></li>'}</ul><p class="st-muted">실험 가능한 후보입니다. A/B로 검증하기 전에는 효과가 입증된 전략이 아닙니다.</p></div></div>
    <div class="st-actions"><button type="button" class="cf-btn" data-st-dec="${e(r.decision_key)}" data-packet="${e(r.packet_sha256||'')}" data-ev="0">결정 장면 보기</button><button type="button" class="cf-btn" data-st-dec="${e(r.decision_key)}" data-packet="${e(r.packet_sha256||'')}" data-ev="1">행동근거 보기</button></div>
    ${detail}</section>${all_}`;
}
async function openDecision(key, evidence, packet){
 const flow=liveFlow();if(!flow)return;
 try{
  const pid=key.split('|')[0],rows=HLCauses.analyzeCustomer(flow,pid).filter(r=>r.decision_key===key&&r.packet_sha256===packet);
  if(rows.length!==1)throw Error('선택한 결정의 발생 건을 정확히 구분하지 못했습니다. 다른 활동으로 대체하지 않았습니다.');
  const {index}=HLStrategy.resolveDecisionScene(flow,HLStrategy.decisionTarget(flow,rows[0]));
  const wrapped={result:flow,ledger:flow.ledger,request:flow.request,engine:flow.engine};
  const saved={result:CURRENT.result,key:CURRENT.key,goal:CURRENT.goal,target:CURRENT.target,origin:CURRENT.origin,cohort:CURRENT.cohort,selectedRun:CURRENT.selectedRun,decision:CURRENT.decision,intent:CURRENT.intent,basis:CURRENT.basis,assumedOrigin:CURRENT.assumedOrigin,pct:CURRENT.pct,status:CURRENT.status,analysis:CURRENT.analysis,notice:CURRENT.notice,err:null,returnRun:flow.ledger.run_id,returnView:ST.view};
  const context=evidence?bhContextFor({flow:wrapped},pid,index,{returnTo:'revenue'}):null;
  if(evidence&&!context)throw Error('해당 행동의 정밀 근거 연결을 확인하지 못했습니다.');
  ST.open=false;draw();
  const opened=evidence?await HLNav.activate({flow:wrapped},context):await HLNav.openRun(wrapped,pid,index);
  if(opened)strategyReturnButton(saved);
 }catch(err){CURRENT.err=err.message;ST.open=true;draw();}
}
// Tab 2 · '산타 사례 · 무엇을 실험했나?' — stored official-session record first; the 14:00 model-session record is kept folded.
// Next-experiment candidates come from the diagnosed causes (not from price search); none is engine-verified.
function nextCands(D) {
  const has = k => D.table.some(x => x.category === k), out = [];
  if (has('TIME')) out.push({ lever: '식사 시간 연계 — 산타 회차 종료와 금룡 저녁 영업(18:00)·식사 예약 시각 맞추기', cause: '저녁 결정 시각·영업 전·대기', status: '엔진 연결 필요(예약 시각 이행 보완 후 T1·T2 재계산)' });
  if (has('SPACE')) out.push({ lever: '가족 대상 혜택·좌석 조건 — 산타 예약 가족 한정 식사 혜택, 가족 좌석', cause: '업장 공간·분위기 점수 차', status: '대상 한정 가격·실제 좌석 자료 필요' });
  if (has('MENU')) out.push({ lever: '아동 메뉴를 포함한 가족 식사 구성', cause: '메뉴·음식 취향', status: '실제 판매 메뉴 구성·아이 나이 입력 필요' });
  return out;
}
const OK = v => (v === true ? '통과' : v === false ? '위반' : '—');
function santaHTML() {
  const X = ST.ex; if (!X || !X.official) return '<p class="rc-note">산타 사례 기록을 불러오는 중…</p>';
  // Final ledger policy record first (room valuation v3); older-policy records stay folded and are never mixed into these numbers.
  const O = X.official, V = X.official_current || X.official_v3 || null, D = V ? V.diagnosis : O.diagnosis, runs = Object.fromEntries((V ? V.runs : O.runs).map(r => [r.id, r])), base = V ? V.baseline : O.baseline;
  const lf = liveFlow(), same = lf && lf.ledger.run_id === base.run_id;
  const meta = `<p class="st-record">공식 회차 저장 기록 · 2025-12-19 · 1박 2일 · 28팀 · 산타 2부 14:10 사전 예약 가족 6팀(운영자 가정) · 시드 0 — ${same ? '현재 분석 중인 실행과 같은 기준입니다.' : '현재 실행의 결과가 아닙니다.'}${V ? (base.room_nights_unpriced ? ` 기준 호텔 전체 ${money(base.paid_krw)}은 2025 객실박 ${base.room_nights_unpriced}박의 객실료가 빠진 합계입니다(객실료 미확인).` : ` 기준 호텔 전체 ${money(base.paid_krw)}에는 객실 ${base.room_nights}박이 가상 객실 모델 단가로 들어 있습니다(실제 판매가 아님 · 산타 객실 패키지는 자동 적용하지 않음).`) : ''}</p>`;
  const fam = D.families, blocked = fam.filter(f => f.vs_geumryong === 'BLOCKED').length, comp = fam.filter(f => f.vs_geumryong === 'COMPETED').length;
  const main = D.table.find(x => x.kinds.includes('MAIN_SCORE_GAP')) || D.table[0];
  const chosen = [...new Set(fam.map(f => VN(f.chosen_venue)))].join('·');
  const card = (id, verdict) => { const r = runs[id], m = r.metrics, fc = m.fam_changed.length;
    const famLine = fc ? `${fc}/6팀 선택 변경 · ${id === 'S2' ? '같은 식당 안에서 할인된 메뉴로만 바꿈' : '식당 선택 변경'}` : `0/6팀 · 가족 선택 변화 없음${m.other_changed.length ? ` (일반 고객 ${m.other_changed.length}팀만 이동)` : ''}`;
    return `<article class="st-strat"><header><span class="st-strat-id">${e(id)}</span><h4>${e(r.title)}</h4></header>
      <dl><div class="goal"><dt>산타 가족 F&amp;B 변화 <small>목표</small></dt><dd>${delta(m.fam_fnb)}</dd></div><div class="guard"><dt>호텔 전체 가상 결제 <small>보호</small></dt><dd>${delta(m.total)}</dd></div></dl>
      <p class="st-strat-fam">${e(famLine)}</p><p class="st-strat-verdict">${e(verdict)}</p></article>`; };
  const v1 = '가족 F&B는 그대로이고 호텔 전체가 줄었습니다 → 채택하지 않음';
  const v2 = '가족 선택은 바뀌었지만 더 낮은 가격의 메뉴로 옮겨 가족 F&B와 호텔 전체가 모두 줄었습니다 → 채택하지 않음';
  const S = Object.fromEntries(X.strategies.map(s => [s.id, s])), P = Object.fromEntries(X.pr126.items.map(i => [i.id, i]));
  const more = [
    ['B1', P.B1.title, P.B1.status, 'PR #126 · ' + P.B1.basis], ['B2', P.B2.title, P.B2.status, 'PR #126 · ' + P.B2.basis],
    ['B3', P.B3.title, P.B3.status, '전략 효과가 0이라는 뜻이 아니라, 이번 3인 가족 구성에서는 고정 2인 세트를 주문할 수 있는 대상이 없었다는 뜻입니다. ' + P.B3.basis],
    ['T1', S.T1.title, P.T1 ? P.T1.status : '엔진 연결 필요', (P.T1 ? P.T1.basis + ' ' : '') + '14:00 모델 회차 실행에서는 산타 참가가 0/6이 되어 판단에서 제외했습니다.'],
    ['T2', S.T2.title, '엔진 연결 필요', S.T2.note || S.T2.why],
    ...['H1', 'H2', 'H3', 'H4'].map(k => [k, S[k].title, '현재 엔진으로 계산 불가 · 가설', S[k].note || S[k].why])];
  const moreHTML = `<details class="st-fold"><summary>추가로 검토한 전략 · ${more.length}건 <small>실행하지 않았거나 보류한 가설 · 효과가 검증된 추천안 아님</small></summary>
    <ul class="st-more-list">${more.map(([id, title, st, why]) => `<li><div><b>${e(id)} · ${e(title)}</b><span class="st-ex-badge hold">${e(st)}</span></div><p>${e(why)}</p></li>`).join('')}</ul></details>`;
  const LC = O.ledger_checks, rec = O.reconciliation;
  const evid = `<details class="st-fold"><summary>근거와 검증 <small>운영 조건·상품 가격·행동 근거가 쓰인 곳 · PR #126·#127·#128</small></summary>
    <ul class="st-evidence">
      <li><b>운영 조건 (PR #126)</b><span>2025 공식 회차 11:00·14:10·15:20·16:30을 이 실험의 회차로 사용했습니다. 2026 조건(3·4부 패키지 전용 등)과 섞지 않습니다. 이전 14:00 실험은 모델 가정 회차로 따로 보존합니다.</span></li>
      <li><b>상품 가격 (PR #127)</b><span>S1·S2는 현재 카탈로그의 기존 단품(금룡 삼선 자장면, 피자힐 콤비네이션 피자 L)에 가상 할인율만 적용했습니다. 포장 SKU는 이미 20% 할인가이고 자동 후보가 아니어서 B1·B2는 계산하지 않았습니다. 할인은 SKU 단위로 전원에게 적용되므로 '산타 가족 한정' 혜택은 표현하지 못합니다.</span></li>
      <li><b>행동 근거 (PR #128)</b><span>예약 가족 6팀을 고른 근거 Fact는 시나리오 설정에만 썼고 선택 점수에는 쓰이지 않았습니다. 선택 점수의 개인 근거 항이 결과에 어떻게 작용했는지는 점수 항목으로만 보여주며, 개별 Fact의 인과 효과는 검증하지 않았습니다.</span></li>
      <li><b>해석 주의</b><span>아이 나이는 입력되지 않았습니다. 2025 산타 날짜에는 더뷔페 조식 SKU가 없어 조식 소비가 빠집니다(A·S1·S2 공통). 룸서비스는 ROOM 부문에 집계되며, 이 실험의 산타 가족 룸서비스는 0원입니다.</span></li>
      <li><b>원장 검증 (PR #127 검사 항목 선별 적용 · 최종 정책 실행)</b><span>${V ? [['discount_only_on_target', '할인 행은 대상 상품에만'], ['target_rows_all_discounted', '대상 상품 결제 행 모두 할인'], ['non_target_unit_prices_unchanged', '대상 밖 단가 변화 없음'], ['included_or_free_rows_paid_zero', '포함·무료 행 0원(혜택 중복 과금 없음)'], ['same_engine_and_mode', '같은 엔진·실행 방식'], ['l5_equals_l1', 'L5 = L1'], ['room_nights_same', '객실박 행 A와 동일']].map(([k, t]) => `${t} S1 ${OK(V.checks.S1[k])} · S2 ${OK(V.checks.S2[k])}`).join(' / ') + ` · 할인 행 S1 ${V.checks.S1.discount_rows}건 · S2 ${V.checks.S2.discount_rows}건` : LC.items.map(i => `${e(i.label)} S1 ${OK(i.S1)} · S2 ${OK(i.S2)}`).join(' / ')}</span></li>
      <li><b>객실가 정책</b><span>${V ? (V.baseline.room_nights_unpriced ? `이 기록은 객실가 정책 v3로 실행했습니다. 2025 객실박은 금액 미확인이라 호텔 전체 합계에 객실료가 없습니다. 객실박은 A·S1·S2에서 같아 전략 차이에는 영향이 없습니다.` : `이 기록은 객실가 정책 v4(가상 객실 모델 단가를 모든 날짜에 적용 · 산타 패키지는 명시 선택 시에만)로 실행했습니다. 28팀 모두 패키지를 선택하지 않았고, 객실박은 A·S1·S2에서 같아 전략 차이에는 영향이 없습니다.`) : e(O.room_policy_note || '')}</span></li>
    </ul>
    ${rec ? `<details class="st-more"><summary>A·S1·S2 정합성 대조 · 객실가 v2 · 외부 배달 기본 실행</summary><p class="rc-note">세 실행은 고객 28팀·시드·날짜·인원·회차가 같고 입력 차이는 할인율 하나뿐입니다(${['S1', 'S2'].map(k => `${k}: ${rec[k].input_diff_vs_A.map(d => `${e(d.path)}=${e(JSON.stringify(d.B))}`).join(', ')}`).join(' · ')}). 원장 변화는 F&amp;B뿐입니다(${['S1', 'S2'].map(k => `${k} ${Object.entries(rec[k].L2_delta).filter(([, v]) => v).map(([g, v]) => `${e(g)} ${delta(v)}`).join(' · ')}`).join(' / ')}).</p></details>` : ''}
    <p class="rc-note">기준 실행 ${money(base.paid_krw)}${base.room_nights_unpriced ? '(객실료 미포함)' : '(객실 가상 모델 단가 포함)'} · 실행 ID ${e(base.run_id.slice(0, 12))} · S1 ${e(runs.S1.metrics.run.slice(0, 12))} ${money(runs.S1.metrics.paid_krw)} · S2 ${e(runs.S2.metrics.run.slice(0, 12))} ${money(runs.S2.metrics.paid_krw)}</p>
    ${V ? `<details class="st-more"><summary>이전 정책 기록 · 외부 배달 이전 실행</summary><p class="rc-note">기준 ${money(O.baseline.paid_krw)} (${e(O.baseline.run_id.slice(0, 12))}) · ${O.runs.map(r => `${e(r.id)} ${delta(r.metrics.total)} · 가족 F&amp;B ${delta(r.metrics.fam_fnb)}`).join(' · ')}. 위 최신 기록과 금액 기준이 달라 합치거나 비교하지 않습니다(전략 차이는 같음).</p>${X.official_v3 && V !== X.official_v3 ? `<p class="rc-note">객실가 v3 기록(2025 객실박 금액 미확인): 기준 ${money(X.official_v3.baseline.paid_krw)}(객실료 제외 · ${e(X.official_v3.baseline.run_id.slice(0, 12))}) · ${X.official_v3.runs.filter(r => r.id !== 'B3').map(r => `${e(r.id)} ${delta(r.metrics.total)}`).join(' · ')}</p>` : ''}</details>` : ''}</details>`;
  const archive = `<details class="st-fold"><summary>이전 기록 · 14:00 모델 회차 전체 분석 <small>공식 회차와 다른 실험 · 덮어쓰지 않고 보존</small></summary>
    <p class="st-record">모델 가정 회차(10:00·12:00·14:00·16:00, 예약 14:00) 기록입니다. 기준 실행 ${e(X.baseline.run_id.slice(0, 8))} · ${money(X.baseline.paid_krw)}.</p>${exploreHTML(true)}</details>`;
  return `<section class="st-card st-question"><small>운영 질문</small><h3>${e(O.question)}</h3>${meta}</section>
  <section class="st-card"><div class="st-step"><span>1</span><h4>운영 목표</h4></div><p class="st-lead">산타 예약 가족의 호텔 F&amp;B 가상 결제를 늘리되, 호텔 전체 가상 결제가 줄지 않아야 합니다.</p></section>
  <section class="st-card"><div class="st-step"><span>2</span><h4>고객 행동에서 발견한 원인</h4></div>
    <p class="st-lead">예약 가족 6팀은 모두 저녁으로 ${e(chosen)}을(를) 골랐습니다. 금룡과 비교하면 ${blocked}팀은 결정 시각에 금룡이 아직 영업 전이었고, ${comp}팀은 점수 경쟁에서 졌습니다. 점수 항목 중 가장 크게 벌어진 것은 ${e(main ? main.label : '—')}(${main ? main.count : 0}팀)입니다. 다른 항목과 상쇄된 뒤의 결과이며, 이 항목 하나가 단독 원인이라는 뜻은 아닙니다.</p>
    <div class="st-stats"><div><strong>${blocked}팀</strong><span>시간 때문에 후보 제외</span></div><div><strong>${comp}팀</strong><span>점수 경쟁에서 짐</span></div><div><strong>${e(main ? main.label : '—')}</strong><span>가장 크게 벌어진 점수 항목</span></div></div>
    <details class="st-more"><summary>가족별 결정 보기</summary><table class="rev-table st-ab-table st-ex-opp"><thead><tr><th>가족</th><th>결정 시각</th><th>선택</th><th>금룡 대비</th></tr></thead><tbody>${fam.map(f => `<tr><th>${e(f.customer_id)}</th><td class="num">${e(f.time)}</td><td>${e(VN(f.chosen_venue))} · ${e(f.chosen)}</td><td>${f.vs_geumryong === 'BLOCKED' ? '후보 제외 · ' + f.reasons.map(x => e(HLCauses.LABEL[x] || x)).join(', ') : `점수 차 ${fx(f.gap)} · ${f.top_causes.map(c => `${e(HLCauses.LABEL[c.category] || c.category)} +${fx(c.delta)}`).join(', ')}`}</td></tr>`).join('')}</tbody></table>
    <p class="rc-note">공식 회차 기준 실행(${e(base.run_id.slice(0, 12))})의 결정 기록을 '왜 이런 선택을 했을까?'와 같은 분석기로 계산한 값입니다. 점수 차는 항목별 차이를 모두 더한 값이고, 표시한 항목은 그중 선택한 쪽이 더 높았던 것입니다.</p></details></section>
  <section class="st-card"><div class="st-step"><span>3</span><h4>실제로 실행한 전략</h4></div><div class="st-strats">${card('S1', v1)}${card('S2', v2)}</div>${moreHTML}</section>
  <section class="st-card st-conclusion"><div class="st-step"><span>4</span><h4>결과와 판단</h4></div><p class="st-lead"><b>${e(O.conclusion)}</b></p>
    <div class="st-verdict-split"><div class="tested"><h5>엔진으로 검증한 것 <span class="st-ex-badge pos">같은 조건 A/B</span></h5><ul>${['S1', 'S2'].map(k => { const m = runs[k].metrics; return `<li><b>${e(k)} · ${e(runs[k].title)}</b><span>가족 선택 변화 ${m.fam_changed.length}/6 · 가족 F&amp;B ${delta(m.fam_fnb)} · 호텔 전체 ${delta(m.total)}</span></li>`; }).join('')}<li><b>판단</b><span>할인은 메뉴 선택을 바꿀 수 있었지만 산타 가족 F&amp;B와 호텔 전체 가상 결제를 늘리지 못했습니다.</span></li></ul></div>
      <div class="next"><h5>다음 실험 후보 <span class="st-ex-badge hold">효과 미검증</span></h5><ul>${nextCands(D).map(c => `<li><b>${e(c.lever)}</b><span>원인: ${e(c.cause)} · ${e(c.status)}</span></li>`).join('')}</ul></div></div>
    <p class="st-muted">추천의 핵심은 할인율을 더 찾는 것이 아니라, 고객이 선택하지 않은 이유를 운영자가 바꿀 수 있는 조건과 연결하는 것입니다. 오른쪽 후보는 원인에서 나온 다음 실험 후보이며 현재 엔진이 효과를 검증한 전략이 아닙니다.</p></section>
  ${evid}${archive}`;
}
// Tab 3 · '직접 전략 비교하기' — conditions → one lever → run → goal/guard → who changed and why. Nothing stored is shown as a result here.
function abHTML() {
  if (!ST.preset) return '<p class="rc-note">실험 조건을 불러오는 중…</p>';
  const P = ST.preset, F = P.fixed, has = ST.A && ST.B && ST.cmp && !ST.busy;
  const opts = promo().options_percent.map(p => `<option value="${p}"${p === ST.pct ? ' selected' : ''}>${p}% 할인</option>`).join('');
  const s1 = `<section class="st-card"><div class="st-step"><span>1</span><h4>같은 고객 · 같은 방문 조건</h4></div>
    <ul class="st-facts"><li>2025 산타 키즈빌리지 · ${e(F.start_date)} · 1박 2일</li><li>고객 ${ST.ids ? ST.ids.length : 28}팀 · 도착 ${e(F.arrival_time)} · 시드 ${F.seed}</li><li>산타 ${e(F.booked_start)} 회차(2025 공식) 사전 예약 가족 ${P.booked_families.length}팀 · 운영자 가정</li></ul>
    <details class="st-more"><summary>예약 가족 설정 근거 · 시나리오 설정용(선택 점수 미사용)</summary><ul class="st-ab-list">${P.booked_families.map(f => `<li><b>${e(f.id)}</b> ${e(f.basis)} · ${e(f.note)}</li>`).join('')}</ul><p class="rc-note">${e(P.basis_role_note || '')}</p></details></section>`;
  const s2 = `<section class="st-card"><div class="st-step"><span>2</span><h4>바꿀 운영 조건 하나</h4></div>
    <div class="st-form"><label>상품<select data-st-promo aria-label="전략"${ST.busy ? ' disabled' : ''}>${P.promotions.map(x => `<option value="${e(x.id)}"${x.id === promo().id ? ' selected' : ''}>${e(x.label)}</option>`).join('')}</select></label>
    <label>할인<select data-st-pct aria-label="할인율"${ST.busy ? ' disabled' : ''}>${opts}</select></label><span class="st-muted">현재 ${money(promo().base_price_krw)}/${e(promo().price_unit || '인')} · 운영자 가상 프로모션(공식 가격 아님)</span></div></section>`;
  const s3 = `<section class="st-card"><div class="st-step"><span>3</span><h4>A/B 실행</h4></div>
    <p class="st-muted">A는 지금 조건, B는 위 조건 하나만 바꾼 실행입니다. 두 실행을 새로 계산합니다(28팀 · 약 1분).</p>
    <div class="st-actions"><button type="button" class="cf-btn cf-primary" data-st-run${ST.busy ? ' disabled' : ''}>${ST.busy ? 'A·B 계산 중…' : has ? '다시 실행' : 'A·B 실행'}</button></div>
    ${ST.err ? `<p class="rc-note" role="alert">${e(ST.err)}</p>` : ''}${ST.busy ? '<p class="rev-status" role="status">같은 조건으로 A(기준)와 B(조건 변경)를 계산하고 있습니다.</p>' : ''}</section>`;
  if (!has) return s1 + s2 + s3 + `<section class="st-card st-empty"><h4>아직 결과가 없습니다</h4><p>실행하면 목표 지표(산타 가족 F&amp;B)와 호텔 전체 변화, 바뀐 고객이 여기에 나타납니다. 저장된 산타 사례 수치는 이 화면에 표시하지 않습니다.</p></section>`;
  const g = groups(), cmp = ST.cmp;
  const famF = famFnbDelta(), verdict = famF > 0 && cmp.delta_krw >= 0 ? '가족 F&B가 늘고 호텔 전체도 줄지 않았습니다 · 반복 실행으로 확인이 필요합니다' : famF > 0 ? '가족 F&B는 늘었지만 호텔 전체가 줄었습니다' : '가족 F&B가 늘지 않았습니다';
  const s4 = `<section class="st-card"><div class="st-step"><span>4</span><h4>결과 요약</h4><small class="st-muted">${ST.ranPct}% 할인 · 같은 28팀</small></div>
    <div class="st-kpis"><article class="goal"><small>목표 · 산타 가족 F&amp;B</small><strong>${delta(famF)}</strong><span>가족 선택 변화 ${g.bookedSwitched.length}/${g.booked.length}팀</span></article>
      <article class="guard"><small>보호 · 호텔 전체 가상 결제</small><strong>${delta(cmp.delta_krw)}</strong><span>${money(cmp.before_krw)} → ${money(cmp.after_krw)}${unpricedNights(ST.A) ? ` · 객실료 미포함 합계(객실박 ${unpricedNights(ST.A)}박 금액 미확인)` : ''}</span></article>
      <article class="explain"><small>설명 · 선택이 바뀐 고객</small><strong>${g.switched.length}팀</strong><span>할인만 받은 고객 ${g.priceOnly.length}팀 · 할인 부담 ${money(promoDiscount(ST.B))}</span></article></div>
    <p class="st-lead">${e(verdict)}</p></section>`;
  const s5 = `<section class="st-card"><div class="st-step"><span>5</span><h4>어떤 고객이 왜 바뀌었나</h4></div>${customersHTML().replace(/^<section class="rev-console-panel">/, '<div>').replace(/<\/section>$/, '</div>').replace('<h3>2 · 고객별 선택 변화</h3>', '')}
    <details class="st-more"><summary>업장별 변화 · 호텔 전체 원장 · 점수 비교 상세</summary>${(venuesHTML() + hotelHTML() + detailHTML() + proposalHTML()).replace(/<h3>\d · /g, '<h3>')}</details>
    <details class="st-more"><summary>실행 ID</summary><p class="rc-note">A ${e(ST.A.ledger.run_id)} · B ${e(ST.B.ledger.run_id)}</p></details></section>`;
  return s1 + s2 + s3 + s4 + s5;
}
function unpricedNights(flow) { return Object.values(flow.ledger.receipts || {}).flatMap(r => r.rows || []).filter(x => x.act === 'room_night' && x.status === '금액 미확인').length; }
const TABS = [['live', '현재 실행 분석 · A/B'], ['lab', '맞춤 전략 실험실']];
// Retired research states/links never hydrate old experiments into a current run.
const strategyView = view => view === 'lab' ? 'lab' : 'live';
// Current execution and historical cases have independent state and requests.
const CURRENT={goal:'restaurant',target:'',origin:'ANY',cohort:'all',selectedRun:null,decision:null,intent:'switch',basis:'OBSERVED_VISIT',assumedOrigin:'EXTERNAL_DELIVERY',pct:20,experiments:{},activeExperiment:null,busy:false,err:null,key:null,result:null,status:'NOT_STARTED',analysis:null,notice:null};
let currentAnalysisRevision=0;
function currentSource(){
 const selected=CURRENT.selectedRun&&window.HLNav?.state.runs.get(CURRENT.selectedRun);
 if(CURRENT.selectedRun&&!selected)return null;
 const flow=selected?HLStrategy.restoreRun(selected):typeof REV!=='undefined'?REV.flow:null;
 const request=flow?.request||(flow?.ledger&&typeof REV!=='undefined'&&REV.latest?.flow?.ledger?.run_id===flow.ledger.run_id?REV.latest.request:null);   // no run yet: empty state, not a TypeError
 return flow?.ledger?{flow:{...flow,request},request}:null;
}
function currentStale(source){
 // Analysis belongs to an immutable completed run, never to the mutable visit editor.
 if(source?.flow?.ledger?.source!=='live_engine')return '저장된 시연 기록입니다. 새 방문을 생성한 뒤 운영 조건을 비교해 주세요.';
 if(!source?.flow?.ledger?.run_id||!source?.request?.personas?.length)return '이 실행의 원래 방문 조건을 확인하지 못했습니다. 방문 조건에서 다시 실행해 주세요.';
 const ids=Object.keys(source.flow.ledger.receipts||{});
 if(ids.length!==new Set(source.request.personas).size||ids.some(id=>!source.request.personas.includes(id)))return '실행 고객과 원장의 고객이 일치하지 않습니다. 원래 방문을 다시 열거나 새 방문을 실행해 주세요.';
 return null;
}
function currentDraftDifference(source){
 if(source?.flow?.ledger?.source!=='live_engine')return '저장된 시연 기록입니다. 새 방문을 생성한 뒤 운영 조건을 비교해 주세요.';
 if(!source?.request)return '이 실행의 원래 방문 조건이 없습니다. 방문 조건에서 다시 실행해 주세요.';
 if(CURRENT.selectedRun)return null; // Explicitly selected immutable run, independent of the visit draft.
 if(typeof AG!=='undefined'&&AG.pendingConditions&&AG.flow?.ledger?.run_id===source.flow.ledger.run_id)return '방문 조건이 변경되었습니다. 새 조건으로 실행하면 운영 전략을 분석할 수 있습니다.';
 if(typeof SIT!=='undefined'&&SIT.draftPid&&(source.request.personas.length!==1||!source.request.personas.includes(SIT.draftPid)))return '선택한 고객이 변경되었습니다. 새 고객 조건으로 실행해 주세요.';
 if(typeof SIT!=='undefined'&&SIT.pid&&SIT.options&&SIT.forms.has(SIT.pid)){
  try{const draft=situationRequest(SIT.pid,SIT.forms.get(SIT.pid),SIT.options);
   if(source.request.personas.length===1&&source.request.personas[0]===SIT.pid){
    if(HLStrategy.conditionKey(draft)!==HLStrategy.conditionKey(CURRENT.prepared?.to===source.flow.ledger.run_id?CURRENT.prepared.originalRequest:source.request))return '방문 조건이 변경되었습니다. 새 조건으로 실행하면 운영 전략을 분석할 수 있습니다.';
   }
  }catch(err){return '변경한 방문 조건을 확인하고 다시 실행해 주세요.';}
 }
 return null;
}
function currentContext(source){
 const {flow,request}=source,R=runLine(flow),v=flow.visit||{},conditions=v.resolved_conditions||{};
 const label=HLStrategy.eventLabel(ST.events,v,request),env=request?.environment||{};
 const rooms=Object.entries(conditions).map(([p,c])=>`${flow.ledger.receipts?.[p]?.display_id||'고객'} · ${({GRAND:'그랜드',VISTA:'비스타',DOUGLAS:'더글라스'})[c.building]||'비투숙'} · ${!c.stay?'당일 방문':c.building==='DOUGLAS'?'라운지 라이트 조식 포함':c.breakfast_plan==='room_only'?'조식 별도':c.breakfast_plan==='breakfast_included'?'조식 포함':'객실 포함 계약 적용'}`);
 const arrival=env.arrival_time||request?.scenario?.arrival_time||v.scenario_snapshot?.arrival_time;
 return `<section class="st-card st-run" data-strategy-run="${e(flow.ledger.run_id||'')}"><div class="st-run-main"><small>${CURRENT.selectedRun?'선택한 실제 실행 분석':'현재 실행 분석'} · 실행 ${e(String(flow.ledger.run_id||'미기록').slice(0,8))}</small><b>${e(R.names||R.teams+'팀')} · ${e(label)}</b><span>${e(v.start_date||request?.start_date||R.span)} · ${e(DUR[v.duration||request?.duration]||R.dur)} · ${R.teams}팀</span><span>${e(({rain:'비',clear:'맑음',snow:'눈',hot:'더움',cold:'추움'})[env.weather]||'기본 날씨')} · ${arrival?'도착 '+e(arrival):'고객별 기본 도착 시각'}</span></div><details class="st-more"><summary>객실·방문 조건과 가상 소비 계산 기준</summary>${rooms.map(t=>`<p>${e(t)}</p>`).join('')}<p>${v.catalog_policy?'등록 상품별 가격과 포함 계약을 반영한 가상 소비입니다.':'기본 방문 가격 정책으로 계산한 가상 소비입니다. 상품별 전략 실험은 별도 분석용 방문에서 수행합니다.'} 실제 호텔 결제나 매출 예측이 아닙니다.</p></details>${CURRENT.prepared?.to===flow.ledger.run_id?`<p class="st-muted" role="status">같은 방문 조건에서 상품별 가격 계산을 적용해 새로 생성한 분석용 방문입니다. 이전 방문과 정책이 달라 가상 소비가 달라질 수 있습니다. 전략 효과는 이 방문을 기준으로 새 A/B를 실행해 비교합니다. ${e(CURRENT.prepared?.decision_note||'')}</p>`:''}</section>`;
}
function currentAnalysis(flow){const a=HLCauses.analyze(flow,Object.keys(flow.ledger.receipts||{})),actual=HLPersonalStrategy.actualDecisions(flow);return {...a,rows:a.rows.map(r=>{const d=actual.find(d=>d.customer_id===r.customer_id&&d.packet_sha256===r.packet_sha256&&d.event_id===r.event_id);return d?{...r,...d,chosen:{...r.chosen,...d.chosen},competitors:r.competitors||[],blocked:r.blocked||[]}:r;})};}
function currentDecisions(source){
 const key=source.flow.ledger.run_id;
 if(ST.decisionRun!==key){ST.decisionRun=key;ST.decisionRows=HLPersonalStrategy.actualDecisions(source.flow);}
 return ST.decisionRows||[];
}
async function personalEvidence(ids){
 ST.evidence=ST.evidence||{};
 await Promise.all(ids.map(async pid=>{if(!ST.evidence[pid])ST.evidence[pid]=await call('/api/strategy/evidence?customer='+encodeURIComponent(pid));}));
 return ST.evidence;
}
function personalHTML(model){return HLStrategyStory.render(model,{e,money,VN,name:pid=>typeof dno==='function'?dno(pid):'고객',conclusion:ST.view==='lab'});}
const LAB={mode:'EXISTING',event:'none',date:'2026-12-18',duration:'stay_1',weather:'clear',arrival:'09:00',seed:0,package:'',session:'',bookingDate:'',earlybird:false,partyAssumption:false,source:null,originalRun:null,scope:'one',ids:[],type:'',basis:'PROFILE_ONLY',origin:'EXTERNAL_DELIVERY',target:'THE_BUFFET',intent:'switch',busy:false,result:null,error:null,filter:'all',initialized:false};
function labCustomers(){return HLPersonalStrategy.selectCustomers(ST.customers||[],LAB);}
function agentLabContext(){
 const source=LAB.mode==='SIMULATE'?LAB.source:LAB.mode==='EXISTING'?currentSource():null;
 return {enabled:ST.cap?.llm_strategy,ids:labCustomers().map(p=>p.id),target:LAB.target,intent:LAB.intent,
  basis:LAB.basis==='OPERATOR_ASSUMPTION'?'OPERATOR_ASSUMPTION':source?'ACTUAL_RUN':'PROFILE_HYPOTHESIS',
  assumption:LAB.basis==='OPERATOR_ASSUMPTION'?LAB.origin:null,run:source?.flow,evidence:ST.evidence,
  targetLabel:VN(LAB.target),context:HLStrategyEventLab.summary(LAB,source,ST.events),name:pid=>ST.customers.find(p=>p.id===pid)?.label||pid,
  call,draw,openLedger:async flow=>{const saved={...CURRENT,returnView:'lab',returnRun:source?.flow.ledger.run_id};ST.open=false;draw();await HLNav.openRunLedger({result:flow,ledger:flow.ledger,request:flow.request,engine:flow.engine});strategyReturnButton(saved);}};
}
function autonomousSource(source){return Object.values(source?.flow?.plans||{}).some(p=>p.autonomous_decisions?.length);}
function currentAgentContext(){
 const source=currentSource();
 return {enabled:ST.cap?.llm_strategy,ids:source?.request?.personas||[],target:CURRENT.target,
  intent:CURRENT.agentIntent||'switch',basis:'ACTUAL_RUN',run:source?.flow,evidence:ST.evidence,
  targetLabel:VN(CURRENT.target),context:`${HLStrategy.eventLabel(ST.events,source?.flow?.visit,source?.request)} · 보존된 현재 실행`,
  name:pid=>source?.flow?.ledger?.receipts?.[pid]?.display_id||pid,call,draw,
  openLedger:async flow=>{const saved={...CURRENT,returnView:'live',returnRun:source?.flow.ledger.run_id};ST.open=false;draw();await HLNav.openRunLedger({result:flow,ledger:flow.ledger,request:flow.request,engine:flow.engine});strategyReturnButton(saved);}};
}
function currentAgentHTML(source,venues){
 const stale=currentStale(source),ctx=currentAgentContext();
 return currentContext(source)+`<section class="st-card st-goal-input"><h4>현재 LLM 방문의 운영 전략</h4><p>실제 선택한 식당·메뉴와 비교 대안을 바탕으로 개입을 검토합니다.</p><div class="st-form"><label>목표 업장<select data-current-target>${venues.map(v=>`<option value="${e(v)}"${v===CURRENT.target?' selected':''}>${e(VN(v))}</option>`).join('')}</select></label><label>운영 목표<select data-current-agent-intent><option value="switch"${ctx.intent==='switch'?' selected':''}>목표 업장 유치</option><option value="increase"${ctx.intent==='increase'?' selected':''}>목표 업장 소비 확대</option></select></label></div></section>`+
  (stale?`<p class="st-card" role="status">${e(stale)}</p>`:typeof HLAgentLab==='undefined'||!ctx.enabled?'<p class="st-card" role="status">이 환경에서는 LLM 전략 분석을 사용할 수 없습니다. 실행 설정을 확인해 주세요.</p>':HLAgentLab.render(ctx));
}
async function agentVisit(request){
 let job=await call('/api/visit/jobs',request);
 while(['QUEUED','RUNNING'].includes(job.status)){
  await new Promise(r=>setTimeout(r,2000));job=await call('/api/agent/jobs?id='+encodeURIComponent(job.job_id));
 }
 if(job.status!=='DONE')throw Error(job.error||'방문 계산 상태 확인 필요');
 return job.result;
}
function labHTML(){
 if(!ST.events||!ST.rooms||!ST.customers)return '<section class="st-card" role="status">행사·상품·고객 조건을 불러오고 있습니다.</section>';
 if(LAB.mode==='EXISTING'&&LAB.result?.source_run_id&&LAB.result.source_run_id!==currentSource()?.flow.ledger.run_id){LAB.result=null;LAB.error='연결 방문이 바뀌었습니다. 현재 조건으로 다시 분석해 주세요.';}
 const people=ST.customers||[],types=[...new Set(people.map(p=>p.type))];
 if(!LAB.initialized&&people.length){LAB.ids=[currentSource()?.request?.personas?.[0]||people[0].id];LAB.initialized=true;}
 if(!LAB.type&&types.length)LAB.type=types[0];
 const opt=(v,t,cur)=>`<option value="${e(v)}"${v===cur?' selected':''}>${e(t)}</option>`;
 const ids=labCustomers().map(p=>p.id),locked=LAB.busy?' disabled':'';
 const step=(n,title,body)=>`<section class="st-lab-step" data-lab-step="${n}"><div class="st-lab-step-heading"><span>STEP ${n}</span><h4>${title}</h4></div>${body}</section>`;
 return `<section class="st-card st-lab-workspace"><h3>맞춤 전략 실험실</h3><p class="st-lab-intro">고객과 방문 상황을 정한 뒤 운영 목표를 분석합니다. 설정을 바꾸어도 계산은 자동 실행되지 않습니다.</p>
 ${step(1,'누구를 분석할까요?',` <div class="st-form"><label>분석 대상 <select data-lab-scope${locked}>${[['one','고객 1명'],['selected','선택한 여러 고객'],['type','프로파일 유형별'],['all','실행 가능 고객 전체']].map(([v,t])=>opt(v,t,LAB.scope)).join('')}</select></label>
 ${LAB.scope==='one'?`<label>고객 <select data-lab-person${locked}>${people.map(p=>opt(p.id,p.label,LAB.ids[0])).join('')}</select></label>`:LAB.scope==='type'?`<label>유형 <select data-lab-type${locked}>${types.map(t=>opt(t,t,LAB.type)).join('')}</select></label>`:''}
 </div>  ${LAB.scope==='selected'?`<fieldset><legend>실제 등록 고객 선택</legend>${people.map(p=>`<label style="display:inline-block;margin:8px"><input type="checkbox" data-lab-pick="${e(p.id)}"${LAB.ids.includes(p.id)?' checked':''}${locked}> ${e(p.label)}</label>`).join('')}</fieldset>`:''}`)}
 ${step(2,'어떤 방문을 분석할까요?',`<div class="st-form"> <label>분석 방식 <select data-lab-env="mode"${locked}>${[['EXISTING','보존된 현재 방문 그대로 분석'],['PROFILE','프로필 기반 행사 가설 · 방문 미실행'],['SIMULATE','새 행사 조건으로 가상 방문 계산']].map(([v,t])=>opt(v,t,LAB.mode)).join('')}</select></label>
${LAB.mode==='SIMULATE'&&ST.cap?.autonomous_agent?`<label>행동 판단 정책<select data-lab-env="visitPolicy"${locked}>${opt('RULE','규칙 전용 · 대조군',LAB.visitPolicy||'RULE')}${opt('AUTONOMOUS','LLM 자율 판단 · '+ST.cap.agent_mode,LAB.visitPolicy)}</select></label>`:''}</div>${LAB.mode==='EXISTING'?'<p class="st-muted">현재 실행의 날짜·행사·패키지를 그대로 사용합니다. 새 조건은 새 가상 방문 계산에서 설정하세요.</p>':LAB.mode==='PROFILE'?'<p class="st-muted">방문 환경은 가설의 맥락입니다. 행동과 소비를 계산하지 않습니다.</p>':''}`)}
 ${LAB.mode!=='EXISTING'?step(3,'행사·기간·환경을 정하세요',`<div class="st-form"><label>행사 <select data-lab-env="event"${locked}>${HLStrategyEventLab.events(ST.events).map(v=>`<option value="${e(v.id)}"${v.id===LAB.event?' selected':''}${!v.enabled?' disabled':''}>${e(v.label)}${v.id!=='none'&&v.id!=='SANTA_KIDS_VILLAGE_2026'?' · 과거 행사 재현':''}${!v.enabled?' · HOLD/실행 준비 중':''}</option>`).join('')}</select></label>
 <label>방문 시작일 <input type="date" data-lab-env="date" value="${e(LAB.date)}"${locked}></label>
 <label>체류 <select data-lab-env="duration"${locked}>${[['day_visit','당일'],['stay_1','1박 2일'],['stay_2','2박 3일'],['stay_3','3박 4일']].map(([v,t])=>opt(v,t,LAB.duration)).join('')}</select></label>
 <label>날씨 <select data-lab-env="weather"${locked}>${opt('clear','맑음',LAB.weather)}${opt('rain','비',LAB.weather)}</select></label>
 <label>도착 <input type="time" data-lab-env="arrival" value="${e(LAB.arrival)}" min="07:00" max="20:00"${locked}></label>
</div><details class="st-lab-advanced"><summary>계산 재현 설정</summary><label>시드 <input type="number" min="0" data-lab-env="seed" value="${LAB.seed}"${locked}></label></details>`):''}
 ${LAB.mode!=='EXISTING'&&['SANTA_KIDS_VILLAGE_2026','SAVORING_SUMMER_NIGHT_2026'].includes(LAB.event)?step(4,'행사 상세 조건을 확인하세요',`<div class="st-form"> ${LAB.event==='SANTA_KIDS_VILLAGE_2026'?`<label>산타 객실 패키지 <select data-lab-env="package"${locked}>${opt('','미선택 · 패키지 회차 입장 불가',LAB.package)}${ST.rooms.packages.filter(p=>p.event_card_id===LAB.event&&p.runnable).map(p=>opt(p.id,p.label+' · '+money(p.price_krw)+'부터',LAB.package)).join('')}</select></label>
 ${LAB.package?`<label>예약 회차 <select data-lab-env="session"${locked}>${opt('','회차 예약 없음 · 혜택만 보유',LAB.session)}${opt('15:20','3부 15:20–16:30 · 예약 가정',LAB.session)}${opt('16:40','4부 16:40–17:50 · 예약 가정',LAB.session)}</select></label><label>예약일 <input type="date" data-lab-env="bookingDate" value="${e(LAB.bookingDate)}"${locked}></label><label><input type="checkbox" data-lab-env="earlybird"${LAB.earlybird?' checked':''}${locked}>11/2~11/8 예약 조건의 얼리버드 8% 적용</label>`:''}`:''}
 ${(LAB.event==='SANTA_KIDS_VILLAGE_2026'&&LAB.package)||LAB.event==='SAVORING_SUMMER_NIGHT_2026'?`<label><input type="checkbox" data-lab-env="partyAssumption"${LAB.partyAssumption?' checked':''}${locked}>${LAB.event==='SANTA_KIDS_VILLAGE_2026'?'성인 2인·어린이 1인':'성인 2인·비스타 패키지'}을 이번 방문의 운영자 조건으로 적용</label>`:''}
</div>${LAB.event==='SANTA_KIDS_VILLAGE_2026'?'<p class="st-muted">패키지는 공식 시작가를 사용한 가상 계산입니다. 예약·입장·참가는 별개이며, 추가 인원 요금은 미확인입니다. 패키지별 권리와 연령 제한을 유지합니다. 식음 10% 할인은 적용 상품·중복 할인 검수 후 연결합니다.</p>':''}`):''}
 ${step(5,'무엇을 바꿔보고 싶나요?',`<div class="st-form"> <label>목표 업장 <select data-lab-target${locked}>${HLStrategy.venues(ST.venueCatalog).map(v=>opt(v,VN(v),LAB.target)).join('')}</select></label>
 <label>운영 목표 <select data-lab-intent${locked}>${opt('switch','목표 업장으로 식사 전환',LAB.intent)}${opt('increase','현재 업장 유지 · 식사 소비 확대',LAB.intent)}</select></label>
 <label>행동 기준 <select data-lab-basis${locked}>${opt('PROFILE_ONLY','후기 프로필 + 연결된 실제 방문만',LAB.basis)}${opt('OPERATOR_ASSUMPTION','운영자가 출발 행동을 가정',LAB.basis)}</select></label>
 ${LAB.basis==='OPERATOR_ASSUMPTION'?`<label>가정한 출발 행동 <select data-lab-origin${locked}>${['EXTERNAL_DELIVERY','IRD',...HLStrategy.venues(ST.venueCatalog)].map(v=>opt(v,VN(v),LAB.origin)).join('')}</select></label>`:''}</div>`)}
 ${step(6,'설정을 확인하고 실행하세요',`<div class="st-lab-run-summary">${e(HLStrategyEventLab.summary(LAB,LAB.mode==='EXISTING'?currentSource():null,ST.events))} · 목표 ${e(VN(LAB.target))}</div> <p>${ids.length}명 선택 · ${LAB.basis==='OPERATOR_ASSUMPTION'?'운영자 가정은 원래 방문 행동·원장을 변경하지 않습니다.':LAB.mode==='SIMULATE'?'선택 고객의 새 가상 방문을 계산하고 그 행동·원장에 연결합니다.':LAB.mode==='PROFILE'?'후기 근거만 분석하며 방문 행동과 소비는 생성하지 않습니다.':'현재 화면의 실제 실행과 연결되지 않은 고객은 프로필 근거만 분석합니다.'}</p><button class="cf-btn cf-primary" data-lab-analyze${locked}${!ids.length?' disabled':''}>${LAB.busy?'방문·개인별 근거 계산 중…':LAB.mode==='SIMULATE'?'이 행사 조건으로 방문 계산·전략 분석':'선택한 고객의 맞춤 전략 분석'}</button>`)}
 </section>
 ${LAB.error?`<section class="st-card" role="alert">${e(LAB.error)}</section>`:''}
 ${LAB.result?`<section class="st-card" data-lab-scenario-result><strong>${e(LAB.result.scenario_context)}</strong><p>가상 방문과 원문 Fact는 별도 근거입니다. 행사 참여나 전환 효과는 실제 실행 결과에서만 확인합니다.</p>${LAB.originalRun?`<button class="cf-btn" data-lab-original>원래 방문으로 돌아가기</button>`:''}${LAB.source?`<button class="cf-btn" data-lab-ledger>새 방문의 행동·원장 열기</button> <button class="cf-btn" data-lab-current="${e(LAB.result.proposals.find(p=>p.decisions.length)?.customer_id||'')}">같은 행사 조건으로 가격 A/B 검토</button>`:''}</section>`:''}
 ${typeof HLAgentLab!=='undefined'?HLAgentLab.render(agentLabContext()):''}
 ${LAB.result?(LAB.result.proposals.length>1?HLStrategyStory.renderCohort(LAB.result,HLPersonalStrategy.summarizeCohort(LAB.result),{e,money,VN,name:pid=>typeof dno==='function'?dno(pid):'고객',people:ST.customers},LAB.filter):personalHTML(LAB.result)):''}`;
}
async function labAnalyze(){
 if(LAB.busy)return;LAB.busy=true;LAB.result=null;LAB.error=null;LAB.filter='all';draw();
 const ids=labCustomers().map(p=>p.id),goal={target:LAB.target,intent:LAB.intent,basis:LAB.basis,assumed_origin:LAB.basis==='OPERATOR_ASSUMPTION'?LAB.origin:null,customer_ids:ids};
 try{
  let source=LAB.mode==='EXISTING'?currentSource():null;
  if(LAB.mode==='SIMULATE'){
   const request=HLStrategyEventLab.request(LAB,ids,ST.events,ST.rooms,ST.cap);
   if(LAB.visitPolicy==='AUTONOMOUS')request.hybrid_policy=ST.cap.autonomous_policy;
   const flow=await (LAB.visitPolicy==='AUTONOMOUS'?agentVisit(request):call('/api/visit',request));flow.request=request;
   if(!flow.ledger?.checks?.receipts_equal_L4_L3_L2_L1)throw Error('새 방문 원장 합계 확인에 실패했습니다.');
   LAB.originalRun=LAB.originalRun||currentSource()?.flow.ledger.run_id;
   LAB.source={flow,request};source=LAB.source;
   HLNav.state.runs.set(flow.ledger.run_id,{result:flow,ledger:flow.ledger,request,engine:flow.engine});
  }else LAB.source=null;
  const bundles=await personalEvidence(ids);
  const decisions=source?currentDecisions(source).filter(r=>ids.includes(r.customer_id)):[];
  let executable=[];
  if(source&&goal.basis!=='OPERATOR_ASSUMPTION'){
   const g=HLStrategy.strategyGoal({goal:goal.intent==='increase'?'spend':'restaurant',target:goal.target,origin:'ANY'},source.flow),a=currentAnalysis(source.flow),op=HLStrategy.opportunity(source.flow,a,g);
   executable=HLStrategy.goalCandidates(op,ST.cap,source.flow.visit?.hotel_price_snapshot);
  }
  if(LAB.mode==='EXISTING'&&(source?.flow.ledger.run_id||null)!==(currentSource()?.flow.ledger.run_id||null))throw Error('분석 중 연결 방문이 바뀌었습니다. 현재 방문으로 다시 분석해 주세요.');
  LAB.result={...HLPersonalStrategy.recommend({goal,bundles,catalog:ST.venueCatalog,decisions,executable}),source_run_id:source?.flow.ledger.run_id||null,scenario_context:HLStrategyEventLab.summary(LAB,source,ST.events),scenario_request:source?.request||null};
 }catch(err){LAB.error=err.message;}finally{LAB.busy=false;draw();(document.querySelector('[data-cohort-summary]')||document.querySelector('[data-personal-proposal]'))?.scrollIntoView({block:'start'});}
}
function wireLab(ov){
 if(typeof HLAgentLab!=='undefined'&&(ST.view==='lab'||autonomousSource(currentSource())))HLAgentLab.wire(ov,ST.view==='lab'?agentLabContext():currentAgentContext());
 ov.querySelector('[data-lab-original]')?.addEventListener('click',async()=>{if(!LAB.originalRun)return;CURRENT.selectedRun=LAB.originalRun;ST.open=false;draw();await HLNav.go('revenue',{run:LAB.originalRun});});
 ov.querySelectorAll('[data-lab-env]').forEach(el=>el.onchange=()=>{const key=el.dataset.labEnv;LAB[key]=el.type==='checkbox'?el.checked:el.value;if(key==='event'){const ev=ST.events.events.find(v=>v.id===el.value);LAB.date=ev?.start_date||'2026-12-18';LAB.package='';LAB.session='';LAB.partyAssumption=false;LAB.earlybird=false;}LAB.result=null;LAB.source=null;LAB.error=null;draw();});
 ov.querySelector('[data-lab-ledger]')?.addEventListener('click',async()=>{if(!LAB.source)return;const saved={...CURRENT,returnView:'lab',returnRun:LAB.source.flow.ledger.run_id};ST.open=false;draw();await HLNav.openRunLedger({result:LAB.source.flow,ledger:LAB.source.flow.ledger,request:LAB.source.request});strategyReturnButton(saved);});
 ov.querySelectorAll('[data-cohort-filter]').forEach(b=>b.onclick=()=>{LAB.filter=b.dataset.cohortFilter;draw();document.querySelector('.st-cohort-list')?.scrollIntoView({block:'start'});});
 ov.querySelectorAll('[data-lab-scope],[data-lab-type],[data-lab-target],[data-lab-intent],[data-lab-basis],[data-lab-origin],[data-lab-person]').forEach(el=>el.onchange=()=>{const key=Object.keys(el.dataset).find(k=>k.startsWith('lab')).slice(3).toLowerCase();if(key==='person')LAB.ids=[el.value];else LAB[key]=el.value;LAB.result=null;LAB.error=null;draw();});
 ov.querySelectorAll('[data-lab-pick]').forEach(el=>el.onchange=()=>{LAB.ids=el.checked?[...new Set([...LAB.ids,el.dataset.labPick])]:LAB.ids.filter(x=>x!==el.dataset.labPick);LAB.result=null;draw();});
 ov.querySelector('[data-lab-analyze]')?.addEventListener('click',labAnalyze);
 ov.querySelectorAll('[data-lab-current]').forEach(b=>b.addEventListener('click',ev=>labOpenCurrent(ev.currentTarget.dataset.labCurrent)));
}

async function labOpenCurrent(pid,sku){
 const source=LAB.source||currentSource();if(!source||LAB.result?.source_run_id!==source.flow.ledger.run_id){LAB.error='연결된 실제 방문을 확인할 수 없습니다. 다시 분석해 주세요.';draw();return;}
 const p=LAB.result.proposals.find(p=>(!pid||p.customer_id===pid)&&p.decisions.length);if(!p){LAB.error='이 방문에는 연결할 식사 결정이 없습니다. 현재 추천은 프로필 가설이며 가격 A/B로 대체하지 않습니다.';draw();return;}
 let decision=p.decisions[0];
 if(sku){const a=currentAnalysis(source.flow),g=HLStrategy.strategyGoal({goal:LAB.intent==='increase'?'spend':'restaurant',target:LAB.target,origin:'ANY'},source.flow),op=HLStrategy.opportunity(source.flow,a,g),candidate=HLStrategy.goalCandidates(op,ST.cap,source.flow.visit?.hotel_price_snapshot).find(c=>c.sku===sku);decision=a.rows.find(r=>r.customer_id===p.customer_id&&candidate?.decisions.some(d=>d.key===r.decision_key));if(!decision){LAB.error='이 고객의 해당 가격 후보에 연결된 결정을 찾지 못했습니다. 다른 고객의 실험으로 대체하지 않습니다.';draw();return;}}
 if(LAB.basis==='OPERATOR_ASSUMPTION'){LAB.error='가정한 출발 행동은 자유 선택 A/B 성과로 집계하지 않습니다. 실제 방문 기준으로 다시 분석하세요.';draw();return;}
 CURRENT.selectedRun=source.flow.ledger.run_id;
 CURRENT.basis='OBSERVED_VISIT';CURRENT.decision=HLPersonalStrategy.decisionId(decision);CURRENT.allDecisions=false;CURRENT.intent=LAB.intent;CURRENT.goal=LAB.intent==='increase'?'spend':'restaurant';CURRENT.target=LAB.target;CURRENT.origin='ANY';CURRENT.cohort='all';currentReset();ST.view='live';draw();await currentAnalyze();
 if(sku)document.querySelector('[data-experiment="'+window.CSS.escape(sku)+'"]')?.scrollIntoView({block:'start'});
}

function currentHTML(){
 const source=currentSource();
 if(!source)return `<section class="st-card st-empty"><h3>먼저 고객의 가상 방문을 생성해 주세요</h3><p>현재 실행의 고객 행동과 원장을 분석해 실험 후보를 찾습니다.</p><button class="cf-btn cf-primary" data-current-visit>방문 조건으로 이동</button></section>`;
 const key=source.flow.ledger.run_id;if(CURRENT.key!==key){CURRENT.key=key;currentReset();}
 const venueOptions=HLStrategy.venues(ST.venueCatalog);
 if(!venueOptions.includes(CURRENT.target))CURRENT.target=venueOptions.includes('PIZZA_HILL')?'PIZZA_HILL':venueOptions[0]||'';
 if(autonomousSource(source))return currentAgentHTML(source,venueOptions);
 const decisionRows=currentDecisions(source);
 if(CURRENT.decision&&!decisionRows.some(r=>HLPersonalStrategy.decisionId(r)===CURRENT.decision))CURRENT.decision=null;
 if(!CURRENT.decision&&decisionRows.length)CURRENT.decision=HLPersonalStrategy.decisionId(decisionRows[0]);
 CURRENT.goal=CURRENT.intent==='increase'?'spend':'restaurant';CURRENT.origin='ANY';CURRENT.cohort='all';
 if(CURRENT.intent==='increase'){const d=decisionRows.find(r=>HLPersonalStrategy.decisionId(r)===CURRENT.decision);CURRENT.target=CURRENT.basis==='OPERATOR_ASSUMPTION'?CURRENT.assumedOrigin:d?.chosen.venue||CURRENT.target;if(CURRENT.target==='EXTERNAL_DELIVERY'){CURRENT.intent='switch';CURRENT.goal='restaurant';CURRENT.target=venueOptions[0]||'';}}
 const goal=HLStrategy.strategyGoal(CURRENT,source.flow),target=goal.target;
 const stale=currentStale(source),draft=currentDraftDifference(source);
 ST.live.target=target||'';
 const option=(value,label,current)=>`<option value="${e(value)}"${value===current?' selected':''}>${e(label)}</option>`;
 const disabled=CURRENT.busy?' disabled':'';
 const runs=[...(window.HLNav?.state.runs||new Map())].filter(([,w])=>w.ledger?.source==='live_engine'&&w.request);
 const goalDecision=decisionRows.find(r=>HLPersonalStrategy.decisionId(r)===CURRENT.decision),assumed=CURRENT.basis==='OPERATOR_ASSUMPTION';
 const goals=`<section class="st-card st-goal-input" data-strategy-run="${e(source.flow.ledger.run_id||'')}"><h4>① 어떤 고객 행동을 바꿔볼까요?</h4><div class="st-current-summary"><span>${e(source.flow.ledger.receipts[goalDecision?.customer_id]?.display_id||runLine(source.flow).names||Object.keys(source.flow.ledger.receipts).length+'팀')}</span>${Object.keys(source.flow.ledger.receipts).length>1?`<span>${Object.keys(source.flow.ledger.receipts).length}팀 실행 중 선택 고객 분석</span>`:''}<span>${e(DUR[source.request.duration]||source.request.duration)}</span><span>${e(HLStrategy.eventLabel(ST.events,source.flow.visit,source.request))}</span></div>
 <label class="st-decision-control">분석 기준 <select data-current-basis${disabled}>${option('OBSERVED_VISIT','현재 선택된 행동에서 출발',CURRENT.basis||'OBSERVED_VISIT')}${option('OPERATOR_ASSUMPTION','다른 행동을 가정하기',CURRENT.basis)}</select></label>
 <label class="st-decision-control">${assumed?'참고할 원래 방문 결정':'현재 소비 결정'} <select data-current-decision${disabled}>${decisionRows.map(r=>option(HLPersonalStrategy.decisionId(r),`${source.flow.ledger.receipts[r.customer_id]?.display_id||'고객'} · ${r.date} ${r.actual_time||r.time} · ${VN(r.chosen.venue)} · ${r.chosen.label} · ${r.chosen.total_krw==null?'결제액 미확인':money(r.chosen.total_krw)}`,CURRENT.decision)).join('')||'<option value="">연결된 식사·카페 소비 결정 없음</option>'}</select></label>
 <div class="st-form">${assumed?`<label>가정한 출발 소비 경로 <select data-current-assumed-origin${disabled}>${['EXTERNAL_DELIVERY','IRD',...venueOptions].map(v=>option(v,VN(v),CURRENT.assumedOrigin||'EXTERNAL_DELIVERY')).join('')}</select></label>`:''}<label>유도할 변화 <select data-current-intent${disabled}>${option('switch','다른 업장으로 전환',CURRENT.intent)}${option('increase','현재 업장 소비 확대',CURRENT.intent)}</select></label>
 ${CURRENT.intent==='increase'?`<b>소비 확대 업장 · ${e(VN(CURRENT.target))}</b>`:`<label>유치할 업장 <select data-current-target${disabled}>${venueOptions.map(v=>option(v,VN(v),CURRENT.target)).join('')}</select></label>`}</div>
 <div class="st-actions st-analysis-actions"><button class="cf-btn cf-primary" data-current-analyze${CURRENT.busy||stale?' disabled':''}>${CURRENT.status==='ANALYZING'?'고객 근거 분석 중…':'이 목표로 고객 분석 실행'}</button><button class="st-scope-link" data-current-lab>다른 고객·집단 분석은 맞춤 전략 실험실에서</button></div><p class="st-run-note" data-current-run-note>${draft?'방문 조건 초안이 별도로 있습니다. 아래 분석은 초안을 적용하지 않고, 표시된 기존 방문 기록을 사용합니다. 새 조건은 방문 실행 후 반영됩니다.':'보존된 방문의 고객·행동·원장을 기준으로 분석합니다.'}</p><p class="st-common-note">후기 기반 프로필과 가상 방문을 활용한 운영 제안입니다. 실제 방문·결제 및 전환 효과를 보증하지 않습니다.</p></section>`;
 const status= currentStatusHTML(source,goal);
 const prepared=CURRENT.prepared?.to===key?'<p class="st-card st-muted">같은 방문 조건에 상품별 계산을 적용한 새 기준 방문입니다. 기존 방문은 보존되며, 정책 변경에 따른 금액 차이는 전략 효과에 포함하지 않습니다.</p>':'';
 const header=goals+prepared+status;
 if(!CURRENT.analysis||['NOT_STARTED','ANALYZING','NEEDS_PREPARATION'].includes(CURRENT.status))return header;
 const {analysis,opp,cs,hs,ready}=CURRENT.analysis;

 const result=experimentResultHTML();
 return header+personalHTML(CURRENT.analysis.personal)+(opp.customers.length&&CURRENT.basis!=='OPERATOR_ASSUMPTION'?experimentPanels(source,cs,ready,result):'')+operatorConclusion(goal)+`<details class="st-fold st-score-details"><summary>고객 행동의 점수와 근거 상세</summary>${liveHTML()}</details>`;
}
function experimentPanels(source,cs,ready,result){
 return `<section class="st-card st-experiment-section" data-experiments><div class="st-section-heading"><span>04 / 가상 실험</span><h3>가격을 바꾸면 선택도 바뀔까요?</h3><p>상품 가격 미리보기와 실제 고객 선택 결과를 나눠 확인합니다.</p></div>${cs.map(c=>{
 const settings=CURRENT.experiments[c.sku]||{pct:20,started:false},pct=settings.pct,quote=HLStrategyExperiment.preview(source.flow,c,pct),active=CURRENT.activeExperiment===c.sku,testing=active&&CURRENT.status==='TESTING',completed=CURRENT.result?.candidate.sku===c.sku&&CURRENT.result.pct===pct;
 return `<article class="st-experiment" data-experiment="${e(c.sku)}"><div class="st-experiment-heading"><div><small>${e(VN(c.venue))} · ${c.kind==='opening'?'운영시간 실험':'상품 가격 실험'}</small><h4>${e(c.label)}</h4></div><span class="st-status-pill">${testing?'계산 중':CURRENT.result?.candidate.sku===c.sku?'실험 완료':settings.started?'조건 변경':'실험 전'}</span></div>
 <p class="st-muted">${c.customers.length}팀의 실제 후보 비교에서 찾은 ${c.kind==='opening'?'영업시간 제약':'가격 조건'}입니다.</p>
 <div class="st-experiment-setup">${c.kind==='opening'?`<p>${e(c.baseline_open)} → ${e(c.open_time)} 영업 시작</p>`:`<div class="st-discount-controls" role="group" aria-label="${e(VN(c.venue))} 가상 할인율">${[10,15,20].map(n=>`<button type="button" data-experiment-pct="${n}" data-experiment-sku="${e(c.sku)}" aria-pressed="${n===pct}">${n}%<span>할인</span></button>`).join('')}</div>
 <div class="st-price-preview" data-price-preview>${quote.ok?quote.rows.map(q=>`<div class="st-price-line"><span>${e(q.customer)} · ${q.party?'동행 '+q.party+'인 · ':''}요금 ${q.quantity}${quote.unitLabel==='1인'?'인':'개'}${q.oldPercent?' · 기존 '+q.oldPercent+'% 할인':''}</span><div><s>${money(q.before)}</s><i>→</i><strong>${money(q.after)}</strong><b class="${q.difference<0?'st-price-rise':''}">가격 차이 ${delta(-q.difference)}</b></div></div>`).join(''):`<p>${e(quote.reason)}</p>`}<small>미리보기 · 구매·매출 변화가 아닙니다. 기존 할인은 선택한 할인율로 대체합니다.</small></div><details class="st-tech"><summary>상품·가격 계약</summary><p>${e(quote.label||c.label)} · ${e(c.sku)}</p><p>${quote.rows.map(q=>'단가 '+money(q.unit)+' × '+q.quantity).join(' · ')}</p><p>${quote.priceStatus==='OFFICIAL_OTHER_PERIOD_REFERENCE'?'다른 기간에 확인한 요금을 적용한 가상 모델 참고가입니다. ':''}선택 전 후보의 수량·단가·포함 여부와 현재 실행 가격 정책을 대조했습니다.</p></details>`}
 <div class="st-experiment-action"><button class="cf-btn cf-primary" data-current-run="${e(c.sku)}"${!quote.ok||quote.unchanged||testing||completed?' disabled':''}>${testing?'고객 선택 계산 중…':completed?'실험 완료 · 할인율을 바꿔 비교':settings.started?'이 조건으로 다시 실험':'이 조건으로 고객 선택 실험'}</button><small>${settings.started?'할인율을 바꾸면 자동으로 다시 계산합니다. 마지막 선택의 결과만 표시합니다.':'시작 전에는 가격만 미리 보여줍니다.'}</small></div>
 </div>${!testing&&CURRENT.result?.candidate.sku!==c.sku?'<div class="st-experiment-idle"><span>선택 결과는 실험 후 확인합니다</span><h4>가격 변화에서<br>고객의 선택 변화로</h4><p>할인율을 고른 뒤 고객 선택 실험을 시작하세요.</p></div>':''}
 ${testing?`<div class="st-experiment-progress" role="status"><span class="st-spinner"></span><b>${c.kind==='opening'?'영업시간':pct+'% 할인'} 조건에서 고객의 선택을 계산하고 있습니다.</b><p>계산 중 변경한 할인율은 순서대로 처리하며, 중간 선택은 마지막 조건으로 합칩니다.</p></div>`:''}
 ${active&&CURRENT.status==='ERROR'?`<p role="alert">${e(CURRENT.err)}</p>`:''}
 ${CURRENT.result?.candidate.sku===c.sku?result:''}</article>`;
 }).join('')||`<div class="st-empty-experiment"><h4>지금 실행할 수 있는 가격·시간 실험이 없습니다</h4><p>${e(ready.message)}</p><p>개인화 제안의 운영 조건을 확인하거나 다른 실제 소비 결정을 선택하세요.</p>${ready.code==='PREPARE'?'<button class="cf-btn cf-primary" data-current-prepare>같은 조건으로 분석용 방문 생성</button>':''}</div>`}</section>`;
}
function experimentVerdict(r){
 const m=r.metrics,chosen=CURRENT.analysis?.opp.rows[0]?.chosen;
 if(r.candidate.kind!=='opening'&&!m.goal_customers.length&&m.changed_customers===0){
  return `${r.pct}% 할인 후에도 ${VN(chosen?.venue)} 선택이 유지됐습니다. 이번 조건에서는 할인만으로 목표 업장 유입 효과가 확인되지 않았습니다.`;
 }
 return HLStrategy.verdict(r.strategyGoal,m).text;
}
function experimentResultHTML(){
 const r=CURRENT.result;if(!r)return '';const {metrics:m,candidate:c,pct,strategyGoal:goal,A,B}=r,preview=HLStrategyExperiment.preview(A,c,pct);
 const changed=m.goal_moves||[],unchanged=!m.goal_customers.length,choice=CURRENT.analysis?.opp.rows[0]?.chosen;
 return `<div class="st-experiment-result" data-current-result tabindex="-1"><div class="st-result-heading"><small>실제 엔진 계산 완료</small><h4>${e(VN(c.venue))} ${c.kind==='opening'?'영업시간 변경':pct+'% 할인'}</h4></div>
 ${preview.ok&&preview.rows.length?`<p class="st-result-price">비교한 상품 가격 ${preview.rows.map(q=>money(q.before)+' → '+money(q.after)).join(' · ')}</p>`:''}
 <div class="st-result-metrics"><article><span>목표 업장 유입</span><strong>${m.goal_customers.length}<small>팀</small></strong></article><article><span>목표 고객의 업장 소비</span><strong>${delta(m.cohort_target_delta)}</strong></article><article><span>호텔 전체 소비</span><strong>${delta(m.paid_delta)}</strong></article></div>
 <p class="st-result-decision">${e(experimentVerdict(r))}</p><p>${unchanged&&m.changed_customers===0?`${e(VN(choice?.venue))} · ${e(choice?.label||'기존 선택')} 유지`:changed.map(x=>e(VN(x.from))+' → '+e(VN(x.to))).join(' · ')||'목표 업장 신규 유입은 없으며 다른 선택 변화가 있습니다.'}</p>
 <ul class="st-facts">${m.moves.map((x,i)=>`<li>${e(B.ledger.receipts?.[x.pid]?.display_id||'고객')} · ${e(x.date)} · ${e(VN(x.from))} → ${e(VN(x.to))}<small>${e(x.from_product)} → ${e(x.to_product)}</small><button class="cf-btn" data-current-customer="${e(x.pid)}" data-current-move="${i}" data-current-side="A">A 행동·근거</button> <button class="cf-btn" data-current-customer="${e(x.pid)}" data-current-move="${i}" data-current-side="B">B 행동·근거</button></li>`).join('')}</ul>
 <details><summary>영수증 · 상품별 가상 결제 상세</summary><p>업장 전체 소비 ${delta(m.target_fnb_delta)} · 기존 구매자 가격 차이 ${delta(m.retained_price_delta)} · 할인 부담 ${money(m.discount_burden)}</p><p>다른 업장 감소: ${m.other_venue_decreases.map(x=>e(VN(x.venue))+' '+delta(x.delta)).join(' · ')||'없음'}</p><button class="cf-btn" data-current-flow="A">A 원장 열기</button> <button class="cf-btn" data-current-flow="B">B 원장 열기</button></details><small>같은 고객·환경·시드의 가격 또는 시간 실험입니다. 개인화 행사·메뉴 가설의 효과와 구분합니다.${m.unmatched?' 구조가 달라 대조하지 못한 결정 '+m.unmatched+'건은 유입 성과에서 제외했습니다.':''}</small></div>`;
}
function operatorConclusion(goal){
 return HLStrategyStory.conclusion(CURRENT.analysis?.personal||{goal,proposals:[]},{e,money,VN,name:pid=>typeof dno==='function'?dno(pid):'고객'},CURRENT.result);
}

function strategyReturnButton(saved){
 document.querySelector('[data-strategy-return]')?.remove();
 const button=document.createElement('button');button.className='cf-btn cf-primary';button.dataset.strategyReturn='';button.textContent=saved.result?'원래 A/B 결과로 돌아가기':'운영 전략으로 돌아가기';
 button.style.cssText='position:fixed;right:24px;bottom:24px;z-index:9500;box-shadow:0 3px 18px #0002';
 button.onclick=async()=>{
  const run=saved.returnRun||saved.result?.A?.ledger.run_id;
  const ok=run?await HLNav.go('revenue',{run}):(await setMode('revenue'),true);
  if(ok){
  const latest=saved.busy&&CURRENT.key===saved.key?{busy:CURRENT.busy,status:CURRENT.status,result:CURRENT.result,analysis:CURRENT.analysis,err:CURRENT.err}:null;
  Object.assign(CURRENT,saved,latest||{busy:false});if(!CURRENT.busy&&['ANALYZING','TESTING'].includes(CURRENT.status)){CURRENT.status=CURRENT.analysis?'ANALYZED':'NOT_STARTED';CURRENT.notice='진행 중이던 계산 상태를 복원하지 않았습니다. 필요한 분석·실험을 다시 실행하세요.';}ST.open=true;ST.view=strategyView(saved.returnView);draw();button.remove();}
 };
 document.body.append(button);
}
async function currentOpenFlow(f,target){
 try{
  const {index}=HLStrategy.resolveDecisionScene(f,target);
  if(!window.HLNav?.openRun)throw Error('행동 화면 이동 기능이 아직 준비되지 않았습니다.');
  const saved={result:CURRENT.result,key:CURRENT.key,goal:CURRENT.goal,target:CURRENT.target,origin:CURRENT.origin,cohort:CURRENT.cohort,selectedRun:CURRENT.selectedRun,decision:CURRENT.decision,intent:CURRENT.intent,basis:CURRENT.basis,assumedOrigin:CURRENT.assumedOrigin,pct:CURRENT.pct,status:CURRENT.status,analysis:CURRENT.analysis,notice:CURRENT.notice,err:null};
  ST.open=false;draw();
  if(await HLNav.openRun({result:f,ledger:f.ledger,request:f.request,engine:f.engine},target.customer_id,index))strategyReturnButton(saved);
 }catch(err){CURRENT.err=err.message;ST.open=true;draw();}
}
async function currentOpenLedger(side){
 const f=CURRENT.result?.[side];if(!f)return;
 const saved={result:CURRENT.result,key:CURRENT.key,goal:CURRENT.goal,target:CURRENT.target,origin:CURRENT.origin,cohort:CURRENT.cohort,selectedRun:CURRENT.selectedRun,decision:CURRENT.decision,intent:CURRENT.intent,basis:CURRENT.basis,assumedOrigin:CURRENT.assumedOrigin,pct:CURRENT.pct,status:CURRENT.status,analysis:CURRENT.analysis,notice:CURRENT.notice,err:null};
 ST.open=false;draw();
 if(await HLNav.openRunLedger({result:f,ledger:f.ledger,request:f.request,engine:f.engine}))strategyReturnButton(saved);
}
function currentReset(message){currentAnalysisRevision++;EXPERIMENT_RUNNER.invalidate();experimentBaseline=null;CURRENT.experiments={};CURRENT.activeExperiment=null;CURRENT.busy=false;CURRENT.result=null;CURRENT.analysis=null;CURRENT.status='NOT_STARTED';CURRENT.err=null;CURRENT.notice=message||null;CURRENT.prepareConfirm=false;}
function currentStatusHTML(source,goal){
 const stale=currentStale(source),status=CURRENT.status,target=goal.target?VN(goal.target):'호텔 전체';
 const labels={NOT_STARTED:'분석 대기',ANALYZING:'고객 행동 분석 중',ANALYZED:'고객 분석 완료',NEEDS_PREPARATION:'분석용 방문 준비 필요',NO_TARGET_CUSTOMERS:'목표에 해당하는 고객 없음',NO_EVIDENCE:'비선택 근거 부족',NO_EXECUTABLE_STRATEGY:'실행 가능한 개입 없음',TESTING:'전략 A/B 계산 중',TESTED:'전략 실험 완료',ERROR:'분석·실험 오류'};
 let text=stale||CURRENT.err||CURRENT.notice||'';
 if(status==='NOT_STARTED'&&!text)text='목표와 대상을 설정한 뒤 고객 분석 실행을 눌러 주세요. 아직 고객 분석이나 전략 실험을 실행하지 않았습니다.';
 if(status==='ANALYZING')text=`이 고객의 후기 근거와 실제 소비를 ${target} ${goal.intent==='increase'?'소비 확대':'유치'} 목표에 맞춰 분석하고 있습니다.`;
 if(status==='TESTING')text='같은 고객·방문 조건에서 A와 B를 계산하고 있습니다. 목표 고객 이동과 전체 소비를 구분해 비교합니다.';
 let actions=stale?'<button class="cf-btn" data-current-visit>방문 조건 확인</button>':'';
 if(status==='NEEDS_PREPARATION'){text='같은 고객·방문 조건에 상품별 선택·가격 계산을 적용한 새 방문이 필요합니다. 행동과 총액이 달라질 수 있으며, 기존 방문은 보존합니다. 이 차이는 전략 효과로 계산하지 않습니다.';actions=`<button class="cf-btn cf-primary" data-current-prepare${CURRENT.busy?' disabled':''}>${CURRENT.busy?'분석용 방문 생성 중…':'새 기준 방문 생성 후 분석 계속'}</button> <button class="cf-btn" data-current-prepare-cancel${CURRENT.busy?' disabled':''}>취소</button>`;}
 if(status==='NO_TARGET_CUSTOMERS'){
  text=CURRENT.analysis?.diagnosis||text;
  const origins=CURRENT.analysis?.observedOrigins||[];
  actions=origins.includes('IRD')?'<button class="cf-btn" data-current-alternative="IRD">룸서비스 → 목표 업장으로 조건 변경</button>':'';
  actions+='<p>분석 범위에서 이미 실행한 다른 고객 방문을 선택하거나, 실제 대상이 있는 방문 조건을 새로 실행할 수 있습니다.</p><button class="cf-btn" data-current-alternative="ANY">같은 고객의 모든 식사 선택 분석으로 조건 변경</button> <button class="cf-btn" data-current-visit>다른 방문 조건 설정</button>';
 }
 return `<section class="st-card st-analysis-status" data-analysis-status="${status}" role="${status==='ERROR'?'alert':'status'}" aria-live="polite"><b>${e(labels[status]||status)}</b>${text?`<p>${e(text)}</p>`:''}${actions}</section>`;
}
async function currentAnalyze(){
 if(CURRENT.busy)return;const source=currentSource();if(!source)return;
 if(currentStale(source)){CURRENT.err=currentStale(source);CURRENT.status='ERROR';draw();return;}
 const revision=++currentAnalysisRevision;
 CURRENT.key=source.flow.ledger.run_id;CURRENT.result=null;CURRENT.analysis=null;CURRENT.err=null;CURRENT.notice=null;
 CURRENT.origin='ANY';CURRENT.cohort='all';CURRENT.goal=CURRENT.intent==='increase'?'spend':'restaurant';const goal=HLStrategy.strategyGoal(CURRENT,source.flow),key=source.flow.ledger.run_id;
 CURRENT.status='ANALYZING';CURRENT.busy=true;draw();
 // Give the progress state a paint before synchronous analysis of existing evidence.
 await new Promise(resolve=>setTimeout(resolve,250));
 try{
  if(revision!==currentAnalysisRevision)return;
  const analysis=currentAnalysis(source.flow),opp=HLStrategy.opportunity(source.flow,analysis,goal),cs=goal.basis==='OPERATOR_ASSUMPTION'?[]:HLStrategy.goalCandidates(opp,ST.cap,source.flow.visit?.hotel_price_snapshot),hs=[],ready=HLStrategy.readiness(source.flow,opp.analysis,goal.target,cs);
  if(currentSource()?.flow.ledger.run_id!==key||HLStrategy.stable(goal)!==HLStrategy.stable(HLStrategy.strategyGoal(CURRENT,source.flow)))throw Error('분석 중 목표 또는 방문이 바뀌었습니다. 현재 조건으로 다시 분석해 주세요.');
  const summary=HLStrategy.analysisOutcome(source.flow,analysis,goal,opp,cs,ready);
  const bundles=await personalEvidence(opp.customers),personal=HLPersonalStrategy.recommend({goal:{...goal,customer_ids:opp.customers},bundles,catalog:ST.venueCatalog,decisions:opp.rows,executable:cs});
  if(revision!==currentAnalysisRevision)return;
  if(currentSource()?.flow.ledger.run_id!==key||HLStrategy.stable(goal)!==HLStrategy.stable(HLStrategy.strategyGoal(CURRENT,source.flow)))throw Error('분석 중 목표 또는 방문이 바뀌었습니다.');
  if(personal.idea_count){summary.status='ANALYZED';summary.conclusion=personal.conclusion;}
  CURRENT.analysis={analysis,opp,cs,hs,ready,goal,personal,...summary};CURRENT.status=summary.status;
 }catch(err){if(revision===currentAnalysisRevision){CURRENT.err=err.message;CURRENT.status='ERROR';}}
 finally{if(revision===currentAnalysisRevision){CURRENT.busy=false;draw();const el=document.querySelector('[data-personal-proposal]')||document.querySelector('[data-analysis-status]');el?.scrollIntoView({block:'start'});el?.focus({preventScroll:true});}}
}
async function currentPrepare(){
 const source=currentSource();if(CURRENT.busy||!source||currentStale(source))return;
 const key=source.flow.ledger.run_id,originalDecision=currentDecisions(source).find(r=>HLPersonalStrategy.decisionId(r)===CURRENT.decision);CURRENT.busy=true;CURRENT.err=null;CURRENT.status='NEEDS_PREPARATION';draw();
 try{
  const request=HLStrategy.prepareRequest(source.request,source.flow,ST.cap),flow=await call('/api/visit',request);flow.request=request;
  if(!flow.visit?.hotel_price_snapshot||!flow.ledger?.checks?.receipts_equal_L4_L3_L2_L1)throw Error('상품별 가격과 원장 정합성을 확인하지 못했습니다. 기존 방문을 유지합니다.');
  if(currentSource()?.flow.ledger.run_id!==key||currentStale(source))throw Error('계산 중 방문 조건이 변경되었습니다. 새 결과로 대체하지 않았습니다.');
  // Navigation owns both immutable runs. Do not rewrite the original request or its receipts.
  const prepared={from:key,to:flow.ledger.run_id,originalRequest:structuredClone(source.request)};
  if(!await HLNav.openRunLedger({result:flow,ledger:flow.ledger,request,engine:flow.engine}))throw Error('새 방문을 열지 못했습니다.');
  CURRENT.selectedRun=flow.ledger.run_id;CURRENT.prepared=prepared;
  if(originalDecision){const oldRows=currentDecisions(source).filter(r=>r.customer_id===originalDecision.customer_id&&r.date===originalDecision.date&&r.slot===originalDecision.slot),index=oldRows.indexOf(originalDecision),next=HLPersonalStrategy.actualDecisions(flow).filter(r=>r.customer_id===originalDecision.customer_id&&r.date===originalDecision.date&&r.slot===originalDecision.slot)[index];CURRENT.decision=next?HLPersonalStrategy.decisionId(next):null;CURRENT.allDecisions=!next;prepared.decision_note=next?'새 계산 정책의 같은 날짜·끼니 발생 순서에 연결했습니다. 이전 결정과 동일한 행동이라는 뜻은 아닙니다.':'새 기준 방문에서 원래 끼니 발생을 찾지 못했습니다. 모든 식사 기록으로 전환했습니다. 출발 결정을 다시 확인하세요.';}
  CURRENT.key=flow.ledger.run_id;CURRENT.result=null;CURRENT.analysis=null;CURRENT.status='NOT_STARTED';CURRENT.prepareConfirm=false;ST.open=true;
 }catch(err){CURRENT.err=err.message;CURRENT.status='ERROR';ST.open=true;}finally{CURRENT.busy=false;draw();}
 if(CURRENT.status!=='ERROR')await currentAnalyze();
}
let experimentBaseline=null;
const EXPERIMENT_RUNNER=HLStrategyExperiment.latestRunner(async(job,isLatest)=>{
 const {source,candidate,pct,strategyGoal,goal,key}=job,requests=HLStrategy.pair(source.request,source.flow,candidate,pct),cacheKey=HLStrategy.stable(requests.A);
 const A=experimentBaseline?.key===cacheKey?experimentBaseline.flow:await call('/api/visit',requests.A);A.request=requests.A;
 if(!HLStrategy.replayMatches(source.flow,A))throw Error('기준 실행 재현값이 달라졌습니다. 현재 코드로 방문을 다시 생성해 주세요.');
 if(isLatest())experimentBaseline={key:cacheKey,flow:A};else return;
 const B=await call('/api/visit',requests.B);B.request=requests.B;
 for(const f of [A,B]){if(f.ledger?.source!=='live_engine')throw Error('실제 엔진 원장을 확인하지 못했습니다.');const total=Object.values(f.ledger.receipts||{}).flatMap(r=>r.rows||[]).reduce((n,r)=>n+(r.paid_krw||0),0);if(total!==f.ledger.totals.paid_krw)throw Error('L5와 호텔 합계가 달라 비교를 중단했습니다.');}
 if(HLStrategy.policyKey(A)!==HLStrategy.policyKey(B))throw Error('실행 정책이 달라 비교를 중단했습니다.');
 if(currentSource()?.flow.ledger.run_id!==key||HLStrategy.stable(strategyGoal)!==HLStrategy.stable(HLStrategy.strategyGoal(CURRENT,source.flow))||currentStale(source))throw Error('분석 대상이 변경되어 결과를 현재 실행에 붙이지 않았습니다.');
 return {A,B,requests,candidate,goal,pct,target:strategyGoal.target,strategyGoal,metrics:HLStrategy.goalMetrics(A,B,currentAnalysis,candidate.sku,strategyGoal)};
},event=>{
 CURRENT.result=event.status==='done'?event.result:null;CURRENT.err=event.status==='error'?event.error.message:null;
 CURRENT.busy=event.status==='running';CURRENT.status=event.status==='running'?'TESTING':event.status==='error'?'ERROR':'TESTED';draw();
});
async function currentRun(sku){
 if((CURRENT.busy&&CURRENT.status!=='TESTING')||!CURRENT.analysis||CURRENT.basis==='OPERATOR_ASSUMPTION')return;const source=currentSource();if(!source||currentStale(source))return;
 if(!source.flow.visit?.hotel_price_snapshot||HLStrategy.stable(CURRENT.analysis.goal)!==HLStrategy.stable(HLStrategy.strategyGoal(CURRENT,source.flow)))return;
 const strategyGoal=HLStrategy.strategyGoal(CURRENT,source.flow),candidate=CURRENT.analysis.cs.find(c=>c.sku===sku);if(!candidate)return;
 const settings=CURRENT.experiments[sku]||{pct:20,started:false},pct=settings.pct,preview=HLStrategyExperiment.preview(source.flow,candidate,pct);
 if(!preview.ok||preview.unchanged){EXPERIMENT_RUNNER.invalidate();CURRENT.busy=false;CURRENT.result=null;CURRENT.err=preview.reason||'현재 기준 방문과 같은 할인율입니다. 다른 할인율을 선택하세요.';CURRENT.status='ERROR';draw();return;}
 settings.started=true;CURRENT.experiments[sku]=settings;CURRENT.activeExperiment=sku;CURRENT.pct=pct;
 const key=source.flow.ledger.run_id,goal=CURRENT.goal;EXPERIMENT_RUNNER.request({source,candidate,pct,strategyGoal,goal,key,identity:[key,strategyGoal,sku,pct]});
}

function panelHTML() {
  ST.view = strategyView(ST.view);
  const tab = ([v, t]) => `<button type="button" role="tab" class="st-tab${ST.view === v ? ' on' : ''}" aria-selected="${ST.view === v}" data-st-view="${v}">${t}</button>`;
  const body = ST.view === 'lab' ? labHTML() : currentHTML();
  return `<div class="rev-overlay st-ab-overlay" role="dialog" aria-modal="true" aria-label="운영 전략"><section class="rev-expanded-panel st-ab">
  <div class="st-sticky"><div class="st-title"><h3>운영 전략</h3><button type="button" class="cf-btn" data-st-close>닫기 ×</button></div><div class="st-tabs" role="tablist">${TABS.map(tab).join('')}</div></div>
  <div class="st-body">${body}</div></section></div>`;
}
const CSS = `.st-ab{max-width:1120px;width:min(1120px,calc(100vw - 48px));padding:0 0 28px!important;font-size:14.5px;line-height:1.6}
.st-analysis-actions{margin-top:20px;display:flex;gap:12px;flex-wrap:wrap}.st-analysis-actions>[data-current-analyze]{font-size:16px;padding:13px 24px}.st-analysis-status{border-left:4px solid #c9463f}.st-sticky{position:static;background:#fffdf9;border-radius:20px 20px 0 0;padding:20px 28px 0;border-bottom:1px solid #efe6dc}
.st-title{display:flex;justify-content:space-between;align-items:center;gap:12px}.st-title h3{margin:0;font-size:21px;letter-spacing:-.3px}
.st-tabs{display:flex;gap:4px;margin-top:14px;overflow-x:auto}
.st-tab{appearance:none;border:0;background:none;padding:10px 16px 12px;font:inherit;font-size:14.5px;font-weight:650;color:#7a716a;border-bottom:3px solid transparent;cursor:pointer;white-space:nowrap}
.st-tab.on{color:#b93332;border-bottom-color:#cc4544}.st-tab:hover{color:#353839}
.st-ab{min-width:0}.st-ab pre{white-space:pre-wrap;overflow-wrap:anywhere}.st-body{min-width:0;padding:20px 28px 0;display:flex;flex-direction:column;gap:18px}
.st-card{background:#fff;border:1px solid #f0e8df;border-radius:16px;padding:22px 24px;box-shadow:inset 0 1px #fff,0 6px 16px #674e3a0a;overflow-wrap:anywhere}
.st-card h3{margin:4px 0 0;font-size:20px;letter-spacing:-.3px;line-height:1.4}.st-card h4{margin:0;font-size:16px}.st-card h5{margin:0 0 8px;font-size:14.5px}
.st-card small{color:#7b726a}.st-muted{color:#6f6862;font-size:13.5px;margin:10px 0 0}.st-lead{font-size:15px;margin:12px 0 0;color:#2c3036}
.st-empty{text-align:left;background:#fbf8f4}.st-empty p{margin:8px 0 0;color:#5d5751}
.st-run{display:grid;grid-template-columns:1fr;gap:12px;align-items:center}
.st-run-main{display:flex;flex-direction:column;gap:2px}.st-run-main b{font-size:17px}.st-run-main span{color:#5d5751}
.st-run-ctl{display:flex;flex-wrap:wrap;gap:10px 20px;justify-content:flex-start;padding-top:12px;border-top:1px solid #f3ece4}.st-run-ctl label,.st-form label{display:flex;gap:8px;align-items:center;font-size:13.5px;color:#5d5751;white-space:nowrap}.st-run-ctl label,.st-form label{flex:0 0 auto}.st-run-ctl select,.st-form select{flex:0 0 auto;width:auto!important;min-width:0;max-width:280px}
.st-run .st-more{grid-column:1/-1}
.st-pick h4 small{font-weight:500;margin-left:6px}.st-pick-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;max-height:168px;overflow:auto}
.st-chip{display:flex;flex-direction:column;align-items:flex-start;gap:1px;border:1px solid #e9dfd5;background:#fdfaf6;border-radius:12px;padding:8px 12px;font:inherit;cursor:pointer;min-width:110px}
.st-chip b{font-size:13.5px}.st-chip span{font-size:12px;color:#7b726a}.st-chip.on{border-color:#cc4544;background:#cc45440d}.st-chip.sm{min-width:0;padding:5px 10px;font-size:12.5px}
.st-ab header.st-why-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;background:none!important;border:0!important;padding:0!important;margin:0!important;box-shadow:none!important}.st-why-head h3{color:#2c3036}.st-dpick{display:flex;gap:6px;flex-wrap:wrap}
.st-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}
.st-pair-cell{border-radius:14px;padding:16px 18px;display:flex;flex-direction:column;gap:4px;background:#faf6f1}
.st-pair-cell.chosen{background:#de86270f;border:1px solid #de862733}.st-pair-cell.alt{background:#517fc50d;border:1px solid #517fc52b}
.st-pair-cell b{font-size:16px}.st-pair-cell span,.st-pair-cell p{color:#5d5751;margin:0}
.st-two{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:20px}
.st-reasons,.st-levers,.st-facts,.st-evidence,.st-more-list,.st-verdict-split ul{list-style:none;padding:0;margin:10px 0 0;display:flex;flex-direction:column;gap:10px}
.st-reasons li,.st-levers li,.st-evidence li,.st-verdict-split li{display:flex;flex-direction:column;gap:2px;padding:10px 14px;border-radius:12px;background:#faf7f3}
.st-levers li{flex-direction:row;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.st-reasons span,.st-evidence span,.st-verdict-split span{color:#5d5751;font-size:13.5px}
.st-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.st-more{margin-top:16px;border-top:1px dashed #eadfd4;padding-top:12px}.st-more>summary,.st-fold>summary{cursor:pointer;font-weight:650;color:#4b4f55}
.st-fold{background:#fff;border:1px solid #f0e8df;border-radius:16px;padding:18px 24px}.st-fold>summary small{font-weight:500;margin-left:8px;color:#7b726a}.st-fold[open]>summary{margin-bottom:12px}
.st-question{background:linear-gradient(135deg,#fff,#fff7f2)}.st-question h3{font-size:22px}
.st-record{font-size:13px;padding:10px 14px;border-radius:10px;background:#7a6a2a12;color:#5a4f2a;margin:12px 0 0}
.st-step{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.st-step>span{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#cc45441a;color:#b93332;font-weight:750;font-size:13px}
.st-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}.st-stats div{background:#faf7f3;border-radius:12px;padding:14px 16px;display:flex;flex-direction:column}.st-stats strong{font-size:20px}.st-stats span{color:#6f6862;font-size:13px}
.st-strats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:16px}
.st-strat{border:1px solid #efe5da;border-radius:16px;padding:20px 22px;background:#fffdfa}
.st-ab .st-strat header{display:flex;gap:10px;align-items:center;background:none!important;border:0!important;padding:0!important;margin:0!important}.st-strat-id{font-weight:800;color:#b93332;background:#cc454414;border-radius:8px;padding:2px 8px}
.st-strat dl{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0 0}.st-strat dl div{background:#faf7f3;border-radius:12px;padding:12px 14px}
.st-strat dt{font-size:12.5px;color:#6f6862}.st-strat dd{margin:4px 0 0;font-size:22px;font-weight:750;letter-spacing:-.4px}
.st-strat .goal dd{color:#b57929}.st-strat .guard dd{color:#b93332}.st-strat-fam{margin:14px 0 0;color:#2c3036}.st-strat-verdict{margin:8px 0 0;padding-top:10px;border-top:1px solid #f0e8df;font-weight:650;color:#4b4f55}
.st-more-list li{padding:12px 14px;border-radius:12px;background:#faf7f3}.st-more-list li div{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center}.st-more-list p{margin:6px 0 0;color:#5d5751;font-size:13.5px}
.st-verdict-split{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:16px;align-items:start}.st-verdict-split>div{border-radius:14px;padding:16px 18px}.st-verdict-split .tested{background:#3b947e0d;border:1px solid #3b947e2b}.st-verdict-split .next{background:#7a6a2a0d;border:1px solid #7a6a2a2b}
.st-verdict-split li{background:#ffffffb3}
.st-facts li{padding:8px 12px;border-radius:10px;background:#faf7f3}
.st-form{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center;margin-top:12px}.st-form label{display:flex;gap:8px;align-items:center}.st-form select{font-size:14px;padding:6px 8px}
.st-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:16px}.st-kpis article{background:#faf7f3;border-radius:14px;padding:16px 18px;display:flex;flex-direction:column;gap:4px}
.st-kpis strong{font-size:24px;letter-spacing:-.5px}.st-kpis .goal strong{color:#b57929}.st-kpis .guard strong{color:#b93332}.st-kpis .explain strong{color:#3b947e}.st-kpis span{font-size:13px;color:#6f6862}
.st-body .rev-console-panel{margin-top:14px}.st-body .st-ab-table td:not(.num),.st-body .st-ab-table th{text-align:left}.st-body .st-ab-table td{vertical-align:top}
@media (max-width:900px){.st-pair,.st-two,.st-strats,.st-verdict-split{grid-template-columns:1fr}.st-run{grid-template-columns:1fr}.st-run-ctl{justify-content:flex-start}.st-kpis,.st-stats{grid-template-columns:1fr}.st-body,.st-sticky{padding-left:16px;padding-right:16px}.st-card{padding:18px}}
.st-ab-host .st-ab-overlay{z-index:160}
.st-ex-tabs{display:flex;gap:8px;margin-top:10px}
.st-ex-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
.st-ex-card{border:1px solid #efe5da;border-radius:14px;padding:18px 20px;background:#fffdfa;line-height:1.6}
.st-ab .st-ex-card header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;background:none!important;border:0!important;border-bottom:1px solid #f0e8df!important;box-shadow:none!important;padding:0 0 12px!important;margin:0 0 10px!important;min-height:0!important;line-height:1.45}
.st-ex-card header b{font-size:15px}
.st-ex-card p{margin:8px 0}
.st-ex-badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;white-space:nowrap;border:1px solid currentColor}
.st-ex-badge.neg{color:#b5552c}.st-ex-badge.hold{color:#7a6a2a}.st-ex-badge.pos{color:#2f8f83}
.st-ex-off td,.st-ex-off th{opacity:.6}
.st-ex-opp td:not(.num),.st-ex-opp th{text-align:left}
.st-ex-controls{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0}
.st-ex-controls label{display:flex;gap:6px;align-items:center;font-size:13px}
.st-ex-counts{font-size:13px;line-height:1.7}
.st-ex-basis{display:block;opacity:.72;font-size:11px;margin-top:3px}
.st-ex-ev{display:inline-block;font-size:10px;padding:0 5px;border-radius:6px;border:1px solid currentColor;margin-left:2px}
.st-ex-ev.p{color:#2f6f8f}.st-ex-ev.c{color:#7a7a7a}
.st-ex-record{font-size:12px;padding:8px 10px;border-radius:8px;background:rgba(122,106,42,.08);margin-top:10px}
.st-ex-opp small{display:block;opacity:.7;font-size:11px}
.st-ab>section,.st-ab .rev-console-panel{margin-top:14px}
.st-ab-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
.st-ab-list{margin:6px 0;padding-left:18px;line-height:1.7}
.st-ab-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.st-ab-table td small,.st-ab-table th small,.st-ab-table td.num small{display:block;opacity:.72;font-size:11px}
.st-ab .num{text-align:right;white-space:nowrap}
.st-ab-delta{list-style:none;padding:0;margin:8px 0}
.st-ab-delta li{display:grid;grid-template-columns:150px 1fr 110px;align-items:center;gap:10px;padding:5px 0}
.st-ab-name small{display:block;opacity:.7;font-size:11px}
.st-ab-bar{position:relative;height:12px;border-radius:6px;background:rgba(0,0,0,.05)}
.st-ab-bar::after{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:rgba(0,0,0,.25)}
.st-ab-bar i{position:absolute;top:0;bottom:0;border-radius:6px}
.st-ab-bar i.pos{background:#2f8f83}.st-ab-bar i.neg{background:#c0643a}
.st-ab-delta b{text-align:right}
@media (max-width:760px){.st-ab-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.st-ab-delta li{grid-template-columns:110px 1fr 90px}}`;

function rootEl() { return document.querySelector('#revenueContent .rev-root') || document.querySelector('#revenueContent'); }
function ensureButton() {
  const root = rootEl(); if (!root) return;
  if (!document.getElementById('stAbStyle')) { const s = document.createElement('style'); s.id = 'stAbStyle'; s.textContent = CSS; document.head.appendChild(s); }
  const tools = root.querySelector('.rev-command-tools') || root.querySelector('.rev-command-head') || root.querySelector('.rev-title') || root;
  if (tools && !tools.querySelector('[data-st-open]')) {
    tools.insertAdjacentHTML('beforeend', '<button type="button" class="cf-btn" data-st-open>운영 전략</button>');
    tools.querySelector('[data-st-open]').onclick = async () => { const run=typeof REV!=='undefined'?REV.ledger?.run_id:null;if(CURRENT.openedRevenueRun!==run){CURRENT.selectedRun=null;CURRENT.decision=null;CURRENT.allDecisions=false;CURRENT.key=null;currentReset();CURRENT.openedRevenueRun=run;}ST.open = true; draw(); try { await ensure(); } catch (err) { ST.err = err.message; } draw(); };
  }
}
// The overlay lives beside the revenue board (not inside its glass layer, which would clip a fixed dialog).
function hostEl() { return document.querySelector('#opxView') || document.body; }
function ensureOverlay() { if (ST.open && rootEl() && !document.querySelector('.st-ab-overlay')) mountOverlay(); }
function mountOverlay() {
  hostEl().insertAdjacentHTML('beforeend', `<div class="rev-harmonized rev-compact st-ab-host">${panelHTML()}</div>`);
  const ov = document.querySelector('.st-ab-overlay');
  wireLab(ov);
  ov.querySelectorAll('[data-open-experiment]').forEach(x=>x.onclick=()=>{if(ST.view==='lab'){void labOpenCurrent(x.dataset.experimentCustomer,x.dataset.openExperiment);return;}const panel=[...ov.querySelectorAll('[data-experiment]')].find(p=>p.dataset.experiment===x.dataset.openExperiment);panel?.scrollIntoView({block:'start'});panel?.querySelector('[data-experiment-pct]')?.focus({preventScroll:true});});
  ov.querySelectorAll('[data-current-analyze]').forEach(x=>x.onclick=currentAnalyze);
  ov.querySelector('[data-current-lab]')?.addEventListener('click',()=>{ST.view='lab';draw();});
  ov.querySelectorAll('[data-current-basis],[data-current-assumed-origin]').forEach(x=>x.onchange=()=>{if(x.hasAttribute('data-current-basis'))CURRENT.basis=x.value;else CURRENT.assumedOrigin=x.value;CURRENT.origin='ANY';CURRENT.cohort='all';currentReset('분석 조건'+'이 변경되었습니다. 분석을 다시 실행해 주세요.');draw();});
  ov.querySelectorAll('[data-story-profile]').forEach(x=>x.onclick=async()=>{const saved={...CURRENT,returnView:ST.view,returnRun:currentSource()?.flow.ledger.run_id};ST.open=false;draw();await setMode('library');libOpen(x.dataset.storyProfile,(x.dataset.storyFacts||'').split(',').filter(Boolean));strategyReturnButton(saved);});

  ov.querySelectorAll('[data-current-decision],[data-current-intent]').forEach(x=>x.onchange=()=>{if(x.hasAttribute('data-current-decision')){CURRENT.decision=x.value||null;CURRENT.allDecisions=!x.value;}else {CURRENT.intent=x.value;if(x.value==='switch')CURRENT.goal='restaurant';}if(CURRENT.intent==='increase'){CURRENT.goal='spend';const r=currentDecisions(currentSource()).find(r=>HLPersonalStrategy.decisionId(r)===CURRENT.decision);if(CURRENT.basis==='OPERATOR_ASSUMPTION'&&HLStrategy.isRestaurant(CURRENT.assumedOrigin))CURRENT.target=CURRENT.assumedOrigin;else if(r)CURRENT.target=r.chosen.venue;}currentReset('출발 결정과 목표가 변경되었습니다. 고객 분석을 실행해 주세요.');draw();});

  ov.querySelectorAll('[data-current-alternative]').forEach(x=>x.onclick=()=>{CURRENT.goal='restaurant';CURRENT.origin=x.dataset.currentAlternative;currentReset('출발 소비 경로가 변경되었습니다. 고객 분석 실행을 눌러 주세요.');draw();document.querySelector('[data-current-analyze]')?.scrollIntoView({block:'center'});});
  ov.querySelectorAll('[data-current-catalog]').forEach(x=>x.onclick=()=>{CURRENT.prepareConfirm=true;draw();});
  ov.querySelectorAll('[data-current-origin],[data-current-cohort],[data-current-scope]').forEach(x=>x.onchange=()=>{if(x.hasAttribute('data-current-origin'))CURRENT.origin=x.value;if(x.hasAttribute('data-current-cohort'))CURRENT.cohort=x.value;if(x.hasAttribute('data-current-scope')){CURRENT.selectedRun=x.value||null;CURRENT.decision=null;CURRENT.allDecisions=false;}currentReset('분석 조건이 변경되었습니다. 이 목표로 고객 분석 실행을 눌러 주세요.');draw();});
  ov.querySelectorAll('[data-current-multi]').forEach(x=>x.onclick=async()=>{CURRENT.selectedRun=null;CURRENT.result=null;ST.open=false;draw();await setMode('agents');if(MODE!=='agents')await setMode('agents');const picker=document.querySelector('.hl-customer-picker[data-picker=flow]');if(picker){picker.open=true;picker.scrollIntoView({block:'center'});}});
  ov.querySelectorAll('[data-current-prepare]').forEach(x=>x.onclick=currentPrepare);
  ov.querySelectorAll('[data-current-prepare-cancel]').forEach(x=>x.onclick=()=>{currentReset('새 기준 방문 생성을 취소했습니다. 기존 방문은 유지됩니다.');draw();});
  ov.querySelectorAll('[data-current-goal]').forEach(x=>x.onchange=()=>{CURRENT.goal=x.value;if(x.value!=='spend')CURRENT.intent='switch';currentReset('운영 목표가 변경되었습니다. 고객 분석을 다시 실행해 주세요.');draw();});
  ov.querySelectorAll('[data-current-target]').forEach(x=>x.onchange=()=>{CURRENT.target=x.value;if(CURRENT.intent==='increase'){CURRENT.intent='switch';CURRENT.goal='restaurant';}currentReset('목표 업장이 변경되었습니다. 고객 분석을 다시 실행해 주세요.');draw();});
  ov.querySelectorAll('[data-current-agent-intent]').forEach(x=>x.onchange=()=>{CURRENT.agentIntent=x.value;draw();});
  ov.querySelectorAll('[data-current-customer]').forEach(x=>x.onclick=async()=>{const side=x.dataset.currentSide,move=CURRENT.result?.metrics.moves[Number(x.dataset.currentMove)],f=CURRENT.result?.[side];if(!f||!move)return;await currentOpenFlow(f,move[side]);});
  ov.querySelectorAll('[data-experiment-pct]').forEach(x=>x.onclick=()=>{const sku=x.dataset.experimentSku,pct=Number(x.dataset.experimentPct),settings=CURRENT.experiments[sku]||{pct:20,started:false};if(settings.pct===pct)return;settings.pct=pct;CURRENT.experiments[sku]=settings;if(settings.started){void currentRun(sku);}else draw();});
  ov.querySelectorAll('[data-current-run]').forEach(x=>x.onclick=()=>currentRun(x.dataset.currentRun));
  ov.querySelectorAll('[data-current-visit]').forEach(x=>x.onclick=()=>{ST.open=false;draw();const pid=typeof SIT!=='undefined'&&SIT.pid||currentSource()?.request?.personas?.[0];if(pid)situationOpen(pid);else setMode('library');});
  ov.querySelectorAll('[data-current-flow]').forEach(x=>x.onclick=async()=>{await currentOpenLedger(x.dataset.currentFlow);});
  ov.onclick = ev => { if (ev.target === ov) { ST.open = false; draw(); } };
  ov.querySelectorAll('[data-st-close]').forEach(b => b.onclick = () => { ST.open = false; draw(); });
  ov.querySelectorAll('[data-st-view]').forEach(b => b.onclick = async () => { ST.view=strategyView(b.dataset.stView);draw();try{await ensure();}catch(err){ST.err=err.message;}draw(); });
  ov.querySelectorAll('[data-st-pid]').forEach(b => b.onclick = () => { ST.live.pid = b.dataset.stPid; ST.live.ri = 0; draw(); });
  ov.querySelectorAll('[data-st-ri]').forEach(b => b.onclick = () => { ST.live.ri = Number(b.dataset.stRi); draw(); });
  ov.querySelectorAll('[data-st-live]').forEach(x => x.onchange = () => { const k = x.dataset.stLive; ST.live[k] = x.value; if (k === 'src') ST.live.target = ''; draw(); });
  ov.querySelectorAll('[data-st-dec]').forEach(b => b.onclick = () => openDecision(b.dataset.stDec, b.dataset.ev === '1', b.dataset.packet));
}
// Explicit redraw after a state change; the observer below only fills in what is missing.
function draw() {
  const root = rootEl(); if (!root) return;
  ensureButton();
  const old = document.querySelector('.st-ab-host'), ov0 = old && old.querySelector('.st-ab-overlay'), scroll = ov0 && ST.drawnView === ST.view ? ov0.scrollTop : 0;   // a new tab always opens at its top
  const panelScroll=ov0?.querySelector('.st-ab')?.scrollTop||0,focused=document.activeElement;
  const control=['data-current-goal','data-current-target','data-current-origin','data-current-cohort','data-current-scope'].find(a=>focused?.hasAttribute(a));
  const opened=[...(ov0?.querySelectorAll('details[open]')||[])].map(d=>d.getAttribute('data-story-signal')||d.getAttribute('data-idea-id')||null).filter(Boolean),rateFocus=focused?.dataset.experimentPct,skuFocus=focused?.dataset.experimentSku;
  ST.drawnView = ST.view;
  if (old) old.remove();
  if (!ST.open) return;
  mountOverlay();
  const ov = document.querySelector('.st-ab-overlay');
  if(ov){ov.scrollTop=scroll;const panel=ov.querySelector('.st-ab');if(panel)panel.scrollTop=panelScroll;if(control)ov.querySelector('['+control+']')?.focus({preventScroll:true});for(const d of ov.querySelectorAll('[data-story-signal]'))if(opened.includes(d.dataset.storySignal))d.open=true;if(rateFocus)[...ov.querySelectorAll('[data-experiment-pct]')].find(x=>x.dataset.experimentPct===rateFocus&&x.dataset.experimentSku===skuFocus)?.focus({preventScroll:true});}
}
async function showFlow(pid, which) {
  if (typeof revShowCustomer !== 'function') return;
  const flow = which === 'A' ? ST.A : ST.B, other = which === 'A' ? ST.B : ST.A;
  const tr = ((ST.cmp.customers[pid] || {}).transitions || [])[0];
  const promoRow = rowsOf(flow, pid).find(r => r.sku_id === promo().sku_id);
  const id = tr ? (which === 'A' ? tr.before_decision_id : tr.after_decision_id) : promoRow ? `|${promoRow.time}` : null;
  REV.flow = flow; REV.baseline = other; REV.comparison = ST.cmp; REV.ledger = flow.ledger;
  ST.open = false;
  await revShowCustomer(pid);
  const req = request(which === 'A' ? 0 : ST.ranPct);
  if (typeof AG !== 'undefined') {
    AG.scenarioSelection = { personas: [...req.personas], scenario: structuredClone(req.scenario), request: structuredClone(req), label: (flow.visit && flow.visit.scenario_snapshot && flow.visit.scenario_snapshot.sources[0].record['행사 · 상품명']) || '2025 산타 키즈 빌리지' };
    if (AG.flow) AG.flow.request = structuredClone(req);
    if (AG.keep && AG.keep.agents) AG.keep.agents.flow = AG.flow;
    if (typeof agLeft === 'function') agLeft();
  }
  const hm = id && id.split('|').pop();
  if (hm && typeof agManyJump === 'function') { const [h, m] = hm.split(':').map(Number); agManyJump(h * 60 + m + 1); }   // inside the decided scene (the scene before ends exactly at the decision time)
}
const original = revRender;
revRender = function (...args) { const out = original.apply(this, args); ensureButton(); ensureOverlay(); return out; };
function observe() {
  const mount = document.querySelector('#revenueContent'); if (!mount) { setTimeout(observe, 500); return; }
  new MutationObserver(() => { ensureButton(); ensureOverlay(); }).observe(document.body, { childList: true, subtree: true });
  ensureButton();
}
observe();
})();
