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
 assert.match(V.label({judgment:{actual:'rules'}}),/LLM 판단 없음/);
 assert.match(V.label({judgment:{actual:'replay'}}),/Replay.*0회/);
 assert.match(V.label({judgment:{actual:'BLOCKED'}}),/규칙 대체 없음/);
});

test('policy versions: replay keeps the stored run policy, live uses the current one, labels name the version', () => {
  const api = require('../static/visit_execution.js');
  assert.equal(api.request({ seed: 1 }, 'live').hybrid_policy, api.LIVE_POLICY);
  assert.equal(api.request({ seed: 1, hybrid_policy: api.POLICY }, 'replay').hybrid_policy, api.POLICY);
  assert.equal(api.request({ seed: 1 }, 'replay').hybrid_policy, api.POLICY);
  assert.equal(api.request({ seed: 1 }, 'replay', api.LIVE_POLICY).hybrid_policy, api.LIVE_POLICY);
  assert.equal(api.request({ seed: 1, hybrid_policy: api.POLICY }, 'live').hybrid_policy, api.LIVE_POLICY);
  assert.equal('hybrid_policy' in api.request({ seed: 1, hybrid_policy: api.POLICY }, 'rules'), false);
  assert.match(api.label({ judgment: { actual: 'replay', policy: api.POLICY } }), /V16.*과거 판단 기준/);
  assert.match(api.label({ judgment: { actual: 'live', policy: api.LIVE_POLICY } }), /^V17 · 새로운 LLM 판단$/);
  assert.match(api.version(api.POLICY), /조기 종료 검증 이전/);
});
