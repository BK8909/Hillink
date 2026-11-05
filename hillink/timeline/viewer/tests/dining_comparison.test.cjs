const test=require('node:test'),assert=require('node:assert/strict'),S=require('../static/reason_story.js');
test('dining comparison groups actual candidates, retains components and labels uncertainty',()=>{
 const r=(id,v,n)=>({candidate_id:id,candidate_label:id,service_contract:{venue_id:v},world_allowed:true,final_score:n,final_with_lookahead:n+1,terms:[{factor:'음식 경험',value:1.2,kind:'profile_and_offer',fact_ids:[]}]});
 const x={rawCands:[r('first','PIZZA_HILL',3),r('other','PIZZA_HILL',2),r('course','MOEGI',2.9),{...r('blocked','GEUMRYONG',10),world_allowed:false}],selectedId:'first',name:s=>s,decision:{packet:{catalog_excluded_candidates:[{venue_id:'MOEGI',reasons:['MINIMUM_ORDER']}]}}};
 const html=S.diningComparison(x);assert.match(html,/최종 선택/);assert.match(html,/직접 Fact 없음/);assert.match(html,/MINIMUM_ORDER/);assert.doesNotMatch(html,/>other<|>blocked</);assert.match(html,/3.000/);assert.match(html,/4.000/);
});
test('no ranked dining evidence creates no invented comparison',()=>assert.equal(S.diningComparison({rawCands:[]}),''));
