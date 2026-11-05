const test=require('node:test'),assert=require('node:assert/strict'),S=require('../static/reason_story.js');
const x=(status,terms=[])=>({decision:{packet:{context_factors:{food_observation:{status,menu_links:[]}}}},selectedId:'A',rawCands:[{candidate_id:'A',terms,score_contribution:{common:4,evidence_delta:.5,actual:4.5}}]});
test('unobserved is not dislike and common decision is explicit',()=>{const h=S.foodObservation(x('UNOBSERVED_IN_ACCEPTED_INPUT'));assert.match(h,/미관측/);assert.match(h,/비선호가 아닙니다/);assert.match(h,/공통 규칙/);assert.match(h,/4.500/)});
test('indirect evidence cannot become firm food taste',()=>{const h=S.foodObservation(x('UNOBSERVED_IN_ACCEPTED_INPUT',[{facet:'space',value:.4,fact_ids:['F1']}])) ;assert.match(h,/간접 기여/);assert.match(h,/확고한 취향으로 해석하지 않습니다/)});
test('missing metadata remains unknown for old runs',()=>assert.equal(S.foodObservation({}),''));
test('unmapped food evidence has its own status',()=>assert.match(S.foodObservation(x('FOOD_EVIDENCE_UNMAPPED')),/연결은 미확정/));

test('planner indirect evidence is not presented as no personalization',()=>{const a=x('UNOBSERVED_IN_ACCEPTED_INPUT');a.decision.packet.context_factors.food_observation.indirect_fact_ids={value_check:['F1']};a.rawCands[0].profile_feature_marginals={'bars.value_check':{weight_delta_at_fixed_state:.2}};assert.match(S.foodObservation(a),/점심 선택 가중치/)});
