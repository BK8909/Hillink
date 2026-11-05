const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/runtime_candidate.js'),'utf8'),ctx={};
vm.runInNewContext(source.slice(0,source.indexOf('(function(){')),ctx);
const price=(id,amount)=>({source:'live_engine',run_id:id,totals:{paid_krw:amount},price_class_aggregates:{classes:{OFFICIAL:{amount_krw:amount}}}});
test('price caption follows the displayed run instead of retaining the latest calculated amount',()=>{
 const first=price('run-AAAAAA',20000),second=price('run-BBBBBB',30000),before=structuredClone(first);
 assert.match(ctx.runtimeCandidatePriceText(first),/run-AAAA.*20,000/);
 assert.match(ctx.runtimeCandidatePriceText(second),/run-BBBB.*30,000/);
 const restored=ctx.runtimeCandidatePriceText(first);assert.match(restored,/20,000/);assert.doesNotMatch(restored,/30,000|run-BBBB/);assert.deepEqual(first,before);
});
test('stored legacy price remains separate and unsupported sources cannot impersonate a run',()=>{
 const saved=ctx.runtimeCandidatePriceText({source:'stored_demo',run_id:'saved-AAA'});assert.match(saved,/저장 시연 saved-AA/);assert.match(saved,/분리 기록 없음/);assert.doesNotMatch(saved,/공식 가격/);
 assert.equal(ctx.runtimeCandidatePriceText({source:'unknown',run_id:'bad'}),null);
});
