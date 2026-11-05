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
