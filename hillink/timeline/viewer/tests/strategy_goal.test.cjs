const test=require('node:test'),assert=require('node:assert/strict'),S=require('../static/strategy_current.js');
const target='MYONGWOLGWAN',sku='REAL-MENU';
const row=(pid,venue,packet)=>({customer_id:pid,date:'2026-10-24',time:'17:00',slot:'dinner',packet_sha256:packet,status:'ANALYZED',decision_key:pid+'|2026-10-24|17:00',chosen:{venue,sku:venue==='EXTERNAL_DELIVERY'?'EXT':sku,total_krw:100,label:venue},competitors:[{sku,venue:target,label:'등록 메뉴',price_part:1,total_krw:200,gap:1}],blocked:[]});
function flow(id,rows,paid=0){return {request:{personas:['P','Q'],seed:0,duration:'stay_1'},rows,visit:{resolved_conditions:{P:{party_size:3},Q:{party_size:3,party_composition:{adult_count:2,children:[{}]}}}},ledger:{run_id:id,totals:{paid_krw:paid},receipts:{P:{customer_type:'유형 확인 중',rows:[]},Q:{customer_type:'유형 확인 중',rows:[]}}}};}
const analyze=f=>({rows:f.rows}),cap={supported:['catalog_discount_percent','catalog_service_open_overrides'],service_open_venues:{MYONGWOLGWAN:'17:30'}};
test('external-to-destination goal survives diagnosis and all candidate types without including other origins',()=>{
 const f=flow('A',[row('P','EXTERNAL_DELIVERY','a'),row('Q','IRD','b')]);
 const g=S.strategyGoal({goal:'recapture',target,origin:'ANY'},f),o=S.opportunity(f,analyze(f),g);
 assert.equal(g.target,target);assert.equal(g.origin,'EXTERNAL_DELIVERY');assert.deepEqual(o.customers,['P']);
 const cs=S.goalCandidates(o,cap);assert.equal(cs.length,1);assert.deepEqual(cs[0].customers,['P']);assert.equal(cs[0].venue,target);
 f.rows[0].competitors=[];f.rows[1].blocked=[{venue:target,reasons:[{category:'TIME',code:'SERVICE_NOT_OPEN_YET'}]}];
 assert.deepEqual(S.goalCandidates(S.opportunity(f,analyze(f),g),cap),[]);
});
test('family population requires recorded composition or family classification, never just party size',()=>{
 const f=flow('A',[row('P','EXTERNAL_DELIVERY','a'),row('Q','IRD','b')]),g=S.strategyGoal({goal:'recapture',target,cohort:'family'},f),o=S.opportunity(f,analyze(f),g);
 assert.equal(o.customers.length,0);assert.deepEqual(S.hypotheses(o,{products:[]}),[]);assert.equal(S.familyEvidence(f,'P').family,null);
 f.ledger.receipts.P.customer_type='가족 · 부모 동반';assert.deepEqual(S.opportunity(f,analyze(f),g).customers,['P']);
});
test('missing candidate is distinguished from blocked and competed; another run is rejected',()=>{
 const f=flow('A',[{...row('P','EXTERNAL_DELIVERY','a'),competitors:[]},row('Q','IRD','b')]),g=S.strategyGoal({goal:'restaurant',target},f),o=S.opportunity(f,analyze(f),g);
 assert.equal(o.counts.ABSENT,1);assert.equal(o.counts.COMPETED,1);assert.throws(()=>S.opportunity(f,analyze(f),{...g,run_id:'B'}));
});
test('hypothesis uses real registered menus with no invented set price or effect and respects date/meal',()=>{
 const f=flow('A',[row('P','EXTERNAL_DELIVERY','a')]),o=S.opportunity(f,analyze(f),S.strategyGoal({goal:'recapture',target},f));
 const menus=[{sku_id:sku,venue_id:target,role:'MAIN',unit_price_krw:78000},{sku_id:'lunch',venue_id:target,role:'MAIN',service_periods:['lunch']},{sku_id:'old',venue_id:target,role:'MAIN',valid_until:'2025-12-31'}];
 const h=S.hypotheses(o,{menu_references:menus})[0];assert.equal(h.status,'UNTESTED');assert.deepEqual(h.menus,[menus[0]]);assert.equal(h.expected_revenue,undefined);assert.match(h.price_basis,/산정하지/);
});
test('goal success counts only source cohort, destination and actual internal payment; other movements remain costs',()=>{
 const a=flow('A',[row('P','EXTERNAL_DELIVERY','a'),row('Q','IRD','b')]),b=flow('B',[row('P',target,'c'),row('Q',target,'d')],160);
 b.plans=Object.fromEntries(b.rows.map(r=>[r.customer_id,{scenes:[{t0:1020,visit_date:r.date,meal:'dinner',basis:{m4:{decision_packet_ids:[r.packet_sha256]}}}]}]));
 for(const pid of ['P','Q'])b.ledger.receipts[pid].rows=[{sku_id:sku,visit_date:'2026-10-24',time:'17:00',meal:'dinner',department:'F&B',venue_id:target,paid_krw:80}];
 const g=S.strategyGoal({goal:'recapture',target},a),m=S.goalMetrics(a,b,analyze,sku,g);
 assert.equal(m.goal_arrivals,1);assert.deepEqual(m.goal_customers,['P']);assert.equal(m.target_arrivals,2);assert.equal(m.cohort_target_delta,80);assert.equal(m.paid_delta,160);assert.equal(S.verdict(g,m).status,'REVIEW');
 b.rows[0].chosen.venue='PIZZA_HILL';const wrong=S.goalMetrics(a,b,analyze,sku,g);assert.equal(wrong.goal_arrivals,0);assert.equal(S.verdict(g,wrong).status,'MAINTAIN');
 b.rows[0].chosen.venue=target;b.ledger.receipts.P.rows[0].time='18:00';assert.equal(S.goalMetrics(a,b,analyze,sku,g).goal_arrivals,0);b.ledger.receipts.P.rows=[];assert.equal(S.goalMetrics(a,b,analyze,sku,g).goal_arrivals,0);
});
test('verdict distinguishes untested, no population, no movement and attraction with total loss',()=>{
 const g={objective:'recapture'};assert.equal(S.verdict(g).status,'UNTESTED');assert.equal(S.verdict(g,{eligible_customers:[]}).status,'NO_POPULATION');assert.match(S.verdict(g,{eligible_customers:['P'],goal_arrivals:1,paid_delta:-10}).text,/감소/);
});
const C=require('../static/decision_causes.js');
function plannerFlow(run,product,price){
 const r={customer_id:'P',visit_date:'2026-10-25',time:'12:42',act:'lunch_myongwol',meal:'lunch',venue_id:target,department:'F&B',sku_id:product,product,paid_krw:price};
 const packet={kind:'PLANNER',packet_sha256:run+'-packet',context_factors:{date:r.visit_date,time:750},candidates:[{candidate_id:r.act,final_score:0.5}]};
 return {request:{personas:['P']},ledger:{run_id:run,totals:{paid_krw:price},receipts:{P:{rows:[r]}}},plans:{P:{m4:{activity_history:[{event_id:run+'-event',meal_slot:'lunch'}],decisions:[{execution_status:'EXECUTED',actual_next_event_id:run+'-event',selected_action:r.act,packet}]},scenes:[{visit_date:r.visit_date,meal:'lunch',act:r.act,t0:762,basis:{m4:{event_id:run+'-event',decision_packet_ids:[packet.packet_sha256]}}}]}}};
}
test('planner lunch menu changes count as real choices without fabricating competitive scores',()=>{
 const a=plannerFlow('A','SOUP',78000),b=plannerFlow('B','BEEF',120000),analyze=f=>C.analyze(f,['P']);
 const r=analyze(a).rows[0];assert.equal(r.status,'NO_TERM_DECOMPOSITION');assert.equal(r.chosen.venue,target);assert.equal(r.chosen.sku,'SOUP');assert.equal(r.competitors,undefined);
 const m=S.goalMetrics(a,b,analyze,'BEEF',S.strategyGoal({goal:'restaurant',target},a));assert.equal(m.changed_customers,1);assert.equal(m.target_before,1);assert.equal(m.target_after,1);assert.equal(m.goal_arrivals,0);assert.equal(m.target_fnb_delta,42000);
 assert.equal(S.resolveDecisionScene(b,m.moves[0].B).scene.act,'lunch_myongwol');assert.deepEqual(S.goalCandidates(S.opportunity(a,analyze(a),S.strategyGoal({goal:'restaurant',target},a)),cap),[]);
});
test('planner order mapping fails closed when the scene occurrence or order date does not match',()=>{
 const a=plannerFlow('A','SOUP',78000);a.ledger.receipts.P.rows[0].visit_date='2026-10-24';assert.equal(C.analyze(a,['P']).rows[0].chosen.choice_source,undefined);
 a.ledger.receipts.P.rows[0].visit_date='2026-10-25';a.plans.P.scenes.push(structuredClone(a.plans.P.scenes[0]));assert.equal(C.analyze(a,['P']).rows[0].chosen.choice_source,undefined);
});
