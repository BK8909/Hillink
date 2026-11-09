const {test}=require('node:test'),assert=require('node:assert/strict');
const V=require('../static/visit_execution.js');
test('ordinary Replay request binds the actual V16 and C01 engine contract',()=>{
 const input={personas:['A01','A07'],duration:'stay_1',environment:{weather:'rain'}};
 const q=V.request(input,'replay');
 assert.equal(q.hybrid_policy,'LLM_AUTONOMOUS_CUSTOMER_V16');assert.equal(q.behavior_engine,'m4_c01');
 assert.equal(q.catalog_policy,'C01_HOTEL_CATALOG_V1');assert.equal(q.simulation_mode,'independent');
 assert.deepEqual(q.environment,input.environment);assert.equal(input.judgment_mode,undefined);
});
test('explicit rules remove a prior autonomous selection and cannot claim LLM',()=>{
 const q=V.request({hybrid_policy:V.POLICY},'rules');assert.equal(q.hybrid_policy,undefined);
 assert.match(V.label({judgment:{actual:'rules'}}),/^규칙 계산 · AI 판단 없음$/);
 assert.match(V.label({judgment:{actual:'replay'}}),/^저장된 판단 재현 · 새 호출 0회/);
 assert.match(V.label({judgment:{actual:'BLOCKED'}}),/규칙 계산으로 대체하지 않음/);
});

test('policy versions: replay keeps the stored run policy, live uses the current one, labels name the version', () => {
  const api = require('../static/visit_execution.js');
  assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, api.LIVE_POLICY);
  assert.equal(api.request({ seed: 1, hybrid_policy: api.POLICY }, 'replay').hybrid_policy, api.POLICY);
  assert.equal(api.request({ seed: 1 }, 'replay').hybrid_policy, api.POLICY);
  assert.equal(api.request({ seed: 1 }, 'replay', api.LIVE_POLICY).hybrid_policy, api.LIVE_POLICY);
  assert.equal(api.request({ seed: 1, hybrid_policy: api.POLICY }, 'live').hybrid_policy, api.LIVE_POLICY);
  assert.equal('hybrid_policy' in api.request({ seed: 1, hybrid_policy: api.POLICY }, 'rules'), false);
  assert.match(api.label({ judgment: { actual: 'replay', policy: api.POLICY } }), /^저장된 판단 재현 · 새 호출 0회 · 과거 판단 기준$/);
  assert.match(api.label({ judgment: { actual: 'live', policy: api.LIVE_POLICY } }), /^실시간 AI 판단$/, 'the current LIVE policy needs no version name');
  assert.match(api.label({ judgment: { actual: 'live', policy: api.PREVIOUS_LIVE_POLICY } }), /^실시간 AI 판단 · V17 기준$/);
  assert.doesNotMatch(api.options('live'), /LLM/);
  assert.match(api.version(api.POLICY), /조기 종료 검증 이전/);
});

test('V18 experiment policies: live stays on the current policy unless the page names ?policy=V18; replay of a V18 run keeps V18', () => {
  const api = require('../static/visit_execution.js');
  const V18 = 'LLM_AUTONOMOUS_CUSTOMER_V18';
  assert.deepEqual(api.EXPERIMENT_POLICIES, [V18, V18 + 'B', V18 + 'BM', V18 + 'BD']);
  assert.equal(api.request({ seed: 1 }, 'live', V18).hybrid_policy, api.LIVE_POLICY, 'a stored/saved policy never switches LIVE to the experiment');
  assert.equal(api.request({ seed: 1, hybrid_policy: V18 }, 'replay').hybrid_policy, V18);
  globalThis.location = { search: '?policy=' + V18 };
  try { assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, V18); } finally { delete globalThis.location; }
  assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, api.LIVE_POLICY);
  assert.match(api.label({ judgment: { actual: 'live', policy: V18 } }), /^실시간 AI 판단 · V18 실험 기준$/);
  assert.match(api.version(V18), /규칙 선별 후 LLM 선택/);
});

test('V19LS is the product LIVE default; V17 stays selectable only by name; Replay keeps the recorded policy', () => {
  const api = require('../static/visit_execution.js');
  const V19 = 'LLM_AUTONOMOUS_CUSTOMER_V19LS', V17 = 'LLM_AUTONOMOUS_CUSTOMER_V17';
  assert.equal(api.LIVE_POLICY, V19);
  assert.equal(api.PREVIOUS_LIVE_POLICY, V17);
  assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, V19);
  assert.equal(api.request({ seed: 1, hybrid_policy: V17 }, 'live').hybrid_policy, V19, 'a saved V17 run never switches LIVE back');
  assert.equal(api.request({ seed: 1, hybrid_policy: V17 }, 'replay').hybrid_policy, V17, 'a V17 run replays under V17');
  assert.equal(api.request({ seed: 1 }, 'replay').hybrid_policy, 'LLM_AUTONOMOUS_CUSTOMER_V16', 'stored V16 runs are not relabeled');
  globalThis.location = { search: '?policy=' + V17 };
  try { assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, V17); } finally { delete globalThis.location; }
  globalThis.location = { search: '?policy=UNKNOWN' };
  try { assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, V19); } finally { delete globalThis.location; }
  assert.match(api.version(V19), /현재 판단 기준\(V19-LS\)/);
  assert.match(api.version(V17), /이전 판단 기준\(V17\)/);
});

test('improved policy is one more entry of the same list and sets the engine policy, not a label', () => {
  const V = require('../static/visit_execution.js');
  const opts = V.options('live_improved');
  assert.equal((opts.match(/<option /g) || []).length, 4, 'one list, one more entry');
  assert.match(opts, /value="live_improved" selected/);
  assert.doesNotMatch(opts, /INT4|DAY_FLOW|LEAN2|HILLINK_RESEARCH/, 'no internal ids or switch names on screen');
  const r = V.request({ personas: ['A05'] }, 'live_improved');
  assert.equal(r.judgment_mode, 'live');
  assert.equal(r.hybrid_policy, V.IMPROVED_POLICY);
  assert.equal(V.request({ personas: ['A05'] }, 'live').hybrid_policy, V.LIVE_POLICY, 'the default LIVE policy is unchanged');
  assert.equal(V.modeOf(r), 'live_improved', 'a rerun keeps the improved policy');
  assert.equal(V.modeOf(V.request({}, 'live')), 'live');
  assert.equal(V.request({}, 'replay', V.IMPROVED_POLICY).hybrid_policy, V.IMPROVED_POLICY, 'a recorded improved run replays under its own policy');
  assert.equal(V.label({ judgment: { actual: 'replay', policy: V.IMPROVED_POLICY } }), '저장된 판단 재현 · 새 호출 0회 · 개선형 기준');
  assert.equal(V.label({ judgment: { actual: 'live', policy: V.IMPROVED_POLICY } }), '실시간 AI 판단 · 개선형 기준');
  assert.ok(V.isLive('live_improved') && V.isLive('live') && !V.isLive('replay'));
});

test('2026-11-09 final A/B: the improved mode runs INT5M; INT4 saved visits still replay and read as 개선형', () => {
  assert.equal(V.IMPROVED_POLICY, 'LLM_AUTONOMOUS_CUSTOMER_V19LS_INT5M');
  assert.equal(V.request({}, 'live_improved').hybrid_policy, V.IMPROVED_POLICY);
  assert.ok(V.POLICIES.includes(V.PREVIOUS_IMPROVED_POLICY) && !V.RESEARCH_POLICIES.includes(V.IMPROVED_POLICY));
  assert.equal(V.request({}, 'replay', V.PREVIOUS_IMPROVED_POLICY).hybrid_policy, V.PREVIOUS_IMPROVED_POLICY, 'a saved INT4 visit replays under INT4');
  assert.equal(V.modeOf({ judgment_mode: 'live', hybrid_policy: V.PREVIOUS_IMPROVED_POLICY }), 'live_improved');
  assert.ok(V.isImproved(V.PREVIOUS_IMPROVED_POLICY) && V.isImproved(V.IMPROVED_POLICY) && !V.isImproved(V.LIVE_POLICY));
  assert.equal(V.label({ judgment: { actual: 'replay', policy: V.PREVIOUS_IMPROVED_POLICY } }), '저장된 판단 재현 · 새 호출 0회 · 개선형 기준');
});
