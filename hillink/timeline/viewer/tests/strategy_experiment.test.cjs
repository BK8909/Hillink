const test=require('node:test'),assert=require('node:assert/strict'),{preview,latestRunner}=require('../static/strategy_experiment.js');
function fixture(unit=198000,qty=2,old=0){
 const candidate={kind:'discount',sku:'S',customers:['P'],decisions:[{key:'P|2026-09-10|17:03'}]};
 const product={sku_id:'S',unit_price_krw:unit,label:'석식',source_unit:'1인'};
 const actual=Math.round(unit*(100-old)/100),raw={product_quote:{total_krw:actual*qty,components:[{sku_id:'S',billing_quantity:qty,unit_price_krw:actual}]},scoring_input_contract:{participant_count:qty}};
 const packet={packet_sha256:'packet',context_factors:{date:'2026-09-10',time:1023},candidates:[raw]};
 const flow={visit:{hotel_price_snapshot:{products:[product]}},request:{catalog_options:{discount_percent:{S:old}}},ledger:{receipts:{P:{display_id:'No.0001'}}},plans:{P:{m4:{decisions:[{execution_status:'EXECUTED',packet}]}}}};
 return {flow,candidate,product,raw,packet};
}
test('actual two-person quote previews 10/15/20%, without booking or ledger changes',()=>{
 const {flow,candidate}=fixture(),before=JSON.stringify(flow);
 for(const [pct,total] of [[10,356400],[15,336600],[20,316800]]){const q=preview(flow,candidate,pct);assert.equal(q.ok,true);assert.equal(q.rows[0].before,396000);assert.equal(q.rows[0].after,total);assert.equal(q.rows[0].quantity,2);assert.equal(q.rows[0].difference,396000-total);}
 assert.equal(JSON.stringify(flow),before);
});
test('existing discount is replaced, not compounded; per-unit KRW rounding precedes quantity',()=>{
 let f=fixture(198000,2,10),q=preview(f.flow,f.candidate,20);assert.equal(q.rows[0].before,356400);assert.equal(q.rows[0].after,316800);assert.equal(q.rows[0].difference,39600);assert.equal(preview(f.flow,f.candidate,10).unchanged,true);
 f=fixture(198000,2,20);q=preview(f.flow,f.candidate,10);assert.equal(q.rows[0].difference,-39600);assert.equal(q.rows[0].after,356400);
 f=fixture(105,3);q=preview(f.flow,f.candidate,10);assert.equal(q.rows[0].after,285); // 94.5 rounds to 95 per person
});
test('unknown price, included entitlement, unsupported contract and quantity mismatch refuse quote',()=>{
 for(const mutate of [f=>f.product.price_confirmed=false,f=>f.product.unit_price_krw=null,f=>f.raw.product_quote.included=true,f=>f.raw.scoring_input_contract.included=true,f=>f.product.discount_policy='NO_DISCOUNT_OR_POINTS',f=>f.product.discount_policy='NO_ADDITIONAL_DISCOUNT',f=>f.product.pricing_parent_sku_id='parent',f=>f.flow.request.catalog_options.price_overrides={S:100},f=>f.raw.product_quote.components[0].billing_quantity=3,f=>f.raw.product_quote.components.push({sku_id:'child'}),f=>f.packet.context_factors.date='2026-09-11']){const f=fixture();mutate(f);assert.equal(preview(f.flow,f.candidate,20).ok,false);}
});
test('accumulated day snapshots do not repeat the same actual quote',()=>{
 const f=fixture();f.flow.visit_days=[{flow:{plans:f.flow.plans}},{flow:{plans:f.flow.plans}}];assert.equal(preview(f.flow,f.candidate,20).rows.length,1);
});
const tick=()=>new Promise(r=>setImmediate(r));
test('serial runner coalesces pending rates, rejects stale success, ignores duplicate clicks',async()=>{
 const calls=[],events=[],finish=[];let active=0,max=0;
 const r=latestRunner(async v=>{calls.push(v.pct);max=Math.max(max,++active);await new Promise(resolve=>finish.push(resolve));active--;return v.pct;},e=>events.push(e));
 const req=pct=>r.request({pct,identity:['same-goal','S',pct]});req(10);req(10);req(15);req(20);assert.deepEqual(calls,[10]);finish.shift()();await tick();assert.deepEqual(calls,[10,20]);assert.equal(events.filter(e=>e.status==='done').length,0);finish.shift()();await tick();assert.equal(max,1);assert.deepEqual(events.filter(e=>e.status==='done').map(e=>e.result),[20]);req(20);assert.deepEqual(calls,[10,20]);
});
test('goal invalidation suppresses old result and error; actual error allows retry',async()=>{
 let done;const events=[],r=latestRunner(()=>new Promise((resolve,reject)=>done={resolve,reject}),e=>events.push(e));
 r.request({identity:['old']});r.invalidate();done.reject(Error('old failure'));await tick();assert.equal(events.filter(e=>e.status==='error').length,0);
 r.request({identity:['new']});done.reject(Error('real failure'));await tick();assert.equal(events.at(-1).status,'error');r.request({identity:['new']});done.resolve(0);await tick();assert.equal(events.at(-1).result,0);
});
