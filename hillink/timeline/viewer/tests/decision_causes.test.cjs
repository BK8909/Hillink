const test = require('node:test'), assert = require('node:assert/strict');
const DC = require('../static/decision_causes.js');

// Synthetic flow in the /api/visit shape: one customer, one executed dinner decision, one planner decision.
const term = (factor, value, fact_ids = []) => ({ factor, value, fact_ids });
const cand = (id, label, venue, final, look, terms, total, extra = {}) => ({ candidate_id: id, candidate_label: label, final_score: final, final_with_lookahead: final + look, world_allowed: true,
  context_adjustment: 0, terms, service_contract: { venue_id: venue }, scoring_input_contract: total ? { participant_count: 2 } : null,
  product_quote: total ? { total_krw: total, components: [{ sku_id: `SKU-${id}`, billing_quantity: 1, unit_price_krw: total }] } : undefined, ...extra });
const chosen = cand('P', '피자', 'PIZZA', 4.0, 2.0, [term('저녁 끼니 해결', 3), term('야경 · 공간 경험', 1.2, ['X-F1']), term('1인 지불액', -0.4)], 40000);
const rival = cand('G', '자장면', 'GEUM', 3.5, 2.0, [term('저녁 끼니 해결', 3), term('1인 지불액', -0.5), term('새 항목', 1.0)], 50000);
const pricey = cand('S', '세트', 'SET', 3.0, 2.0, [term('저녁 끼니 해결', 3), term('야경 · 공간 경험', 2.0), term('1인 지불액', -2.0)], 200000);
const blocked = { candidate_id: 'W', candidate_label: '행사', world_allowed: false, final_score: null, final_with_lookahead: null, block_reason: '운영하지 않음 · 오늘 이미 이용', service_contract: { venue_id: 'FOREST' }, terms: [] };
const pk = (kind, time, cs, extra = {}) => ({ kind, packet_sha256: `sha-${kind}-${time}`, context_factors: { date: '2025-12-19', time }, candidates: cs, ...extra });
const flow = { ledger: { run_id: 'run-x' }, visit_days: [{ flow: { plans: { C1: { m4: {
  activity_history: [{ event_id: 'e1', meal_slot: 'dinner' }, { event_id: 'e0', meal_slot: null }],
  decisions: [
    { execution_status: 'EXECUTED', actual_next_event_id: 'e0', selected_action: 'P', packet: pk('PLANNER', 700, [chosen]) },
    { execution_status: 'PROPOSAL_REPLACED_OR_NOT_EXECUTED', actual_next_event_id: 'e1', selected_action: 'G', packet: pk('QUANTITATIVE', 1020, [chosen, rival]) },
    { execution_status: 'EXECUTED', actual_next_event_id: 'e1', selected_action: 'P', packet: pk('QUANTITATIVE', 1030, [chosen, rival, pricey, blocked],
      { catalog_excluded_candidates: [{ venue_id: 'ONDAL', reasons: ['SERVICE_NOT_OPEN_YET'] }, { sku_id: 'X', reasons: ['DRINK_OR_SNACK_NOT_A_MAIN_MEAL'] }] }) }
  ] } } } } }] };

test('only executed decisions are analyzed and planner packets are reported without decomposition', () => {
  const rows = DC.analyzeCustomer(flow, 'C1');
  assert.deepEqual(rows.map(r => [r.time, r.status]), [['11:40', 'NO_TERM_DECOMPOSITION'], ['17:10', 'ANALYZED']]);
  assert.equal(DC.analyzeCustomer(flow, 'C1', { slot: 'dinner' }).length, 1);
});

test('competitor gap is decomposed term by term with evidence level; unknown terms stay unclassified', () => {
  const r = DC.analyzeCustomer(flow, 'C1', { slot: 'dinner' })[0], g = r.competitors.find(c => c.venue === 'GEUM');
  assert.equal(g.gap, 0.5);
  const by = Object.fromEntries(g.causes.map(c => [c.factor, c]));
  assert.equal(by['야경 · 공간 경험'].category, 'SPACE'); assert.equal(by['야경 · 공간 경험'].evidence, 'PERSONAL_FACT'); assert.deepEqual(by['야경 · 공간 경험'].fact_ids, ['X-F1']);
  assert.equal(by['1인 지불액'].evidence, 'COMMON_RULE'); assert.equal(by['새 항목'].category, 'UNCLASSIFIED');
  assert.equal(g.price_part, 0.1); assert.equal(g.nonprice_part, 0.4);
});

test('price approximation uses the candidate own price term and is labelled first-order', () => {
  const g = DC.analyzeCustomer(flow, 'C1', { slot: 'dinner' })[0].competitors.find(c => c.venue === 'GEUM');
  assert.equal(g.approx.method, 'PRICE_TERM_ONLY_FIRST_ORDER');
  assert.equal(g.approx.break_even_discount_pct, 100);        // 0.5 gap / (0.5 / 25,000 KRW) = 25,000 KRW = all of it
});

test('blocked options carry reasons, never a score gap or a discount', () => {
  const r = DC.analyzeCustomer(flow, 'C1', { slot: 'dinner', target_venue: 'ONDAL' })[0];
  assert.equal(r.target.status, 'BLOCKED'); assert.deepEqual(r.target.reasons.map(x => x.category), ['TIME']);
  assert.equal(r.target.gap, undefined); assert.equal(r.target.approx, undefined);
  const forest = r.blocked.find(b => b.venue === 'FOREST'); assert.deepEqual(forest.reasons.map(x => x.category), ['TIME', 'ALREADY_DONE']);
});

test('an option that was not a candidate is ABSENT, not scored', () => {
  const r = DC.analyzeCustomer(flow, 'C1', { slot: 'dinner', target_venue: 'NOWHERE' })[0];
  assert.deepEqual(r.target, { status: 'ABSENT', venue: 'NOWHERE' });
});

test('a pricier option liked more on non-price terms is listed as a price-lost upsell', () => {
  const r = DC.analyzeCustomer(flow, 'C1', { slot: 'dinner' })[0];
  assert.deepEqual(r.price_lost_upsell.map(x => x.label), ['세트']);
});

test('lever status follows the capability contract', () => {
  assert.equal(DC.levers({ supported: ['catalog_discount_percent'] }).PRICE.status, 'COMPUTABLE');
  assert.equal(DC.levers({ supported: [] }).PRICE.status, 'NEEDS_ENGINE');
  assert.equal(DC.levers({ supported: ['catalog_discount_percent'] }).TIME.status, 'NEEDS_ENGINE');
  assert.equal(DC.levers({}).SPACE.status, 'NEEDS_DATA');
  assert.equal(DC.levers({}).TRAIT.status, 'NOT_STRATEGIZABLE');
});

test('summary counts blocked vs competed and maps causes to levers', () => {
  const A = DC.analyze(flow, ['C1'], { slot: 'dinner', target_venue: 'GEUM' }), S = DC.summarize(A.rows, { supported: ['catalog_discount_percent'] });
  assert.equal(S.counts.competed, 1); assert.equal(S.counts.blocked, 0);
  assert.equal(S.table[0].category, 'SPACE'); assert.equal(S.table[0].status, 'NEEDS_DATA');
  const B = DC.analyze(flow, ['C1'], { slot: 'dinner', target_venue: 'ONDAL' }), T = DC.summarize(B.rows, {});
  assert.equal(T.counts.blocked, 1); assert.equal(T.table[0].category, 'TIME'); assert.equal(T.table[0].status, 'NEEDS_ENGINE');
});
