const test=require('node:test'),assert=require('node:assert/strict'),D=require('../static/decision_explain.js'),S=require('../static/reason_story.js');
test('actual linked execution wins over a discarded proposal without nearest-time guessing',()=>{
 const scene={act:'library',visit_date:'2026-10-24',basis:{m4:{event_id:'e',decision_packet_ids:['old','actual']}}};
 const old={execution_status:'PROPOSAL_REPLACED_OR_NOT_EXECUTED',selected_action:'ROOM_REST',packet:{packet_sha256:'old'}},actual={execution_status:'EXECUTED',actual_next_event_id:'e',selected_action:'library',packet:{packet_sha256:'actual',context_factors:{date:scene.visit_date}}};
 const plan={m4:{decisions:[old,actual]}},before=structuredClone(plan);assert.equal(S.decisionOf(plan,scene),actual);assert.deepEqual(plan,before);
 actual.packet.context_factors.date='2026-10-25';assert.equal(S.decisionOf(plan,scene),null);actual.packet.context_factors.date=scene.visit_date;plan.m4.decisions.push(structuredClone(actual));assert.equal(S.decisionOf(plan,scene),null);
});
test('automatic or waiting activity never claims a discarded proposal was selected',()=>{
 const linkedDecisions=[{execution_status:'PROPOSAL_REPLACED_OR_NOT_EXECUTED'}],basis={m4:{decision_packet_ids:['old']}};
 assert.equal(D.classify({scene:{act:'checkin',source:'obligation',basis},linkedDecisions}),'SCHEDULE');
 assert.equal(D.classify({scene:{act:'idle',basis},executionEvent:{kind:'wait'},linkedDecisions}),'CONDITIONAL');
 assert.equal(D.classify({scene:{act:'library',basis},linkedDecisions}),'MISSING');
 assert.equal(D.classify({scene:{act:'checkin',source:'obligation',basis},linkedDecisions:[{execution_status:'EXECUTED'}]}),'MISSING');
});
test('native meal decisions and executed choices stay decisions',()=>{
 assert.equal(D.classify({scene:{act:'turn_breakfast'},turnDecision:{choice:{}}}),'CHOICE');
 assert.equal(D.classify({scene:{act:'wait'},decision:{execution_status:'EXECUTED'}}),'CHOICE');
 assert.equal(D.classify({scene:{act:'idle'}}),'MISSING');
});
test('score decomposition uses recorded terms, with no invented planner personal delta',()=>{
 const r={score_contribution:{common:2,evidence_delta:.4},context_adjustment:-.2,general_food_evidence:{delta:.05},final_score:2.25,final_with_lookahead:3.5},before=structuredClone(r),z=D.split(r);
 assert.equal(z.reconciled,true);assert.equal(z.lookahead,1.25);assert.deepEqual(r,before);
 assert.equal(D.split({...r,final_score:5}).reconciled,false);
 const planner=D.split({base_score:.8,context_adjustment:-.2,final_score:.6},true);assert.equal(planner.personal,null);assert.equal(planner.reconciled,true);
});
test('adopted review retains final choice distinct from rule winner',()=>{
 assert.deepEqual(D.selection({selectedId:'rule',review:{decided_by:'LLM_REVIEW_ADOPTED',rule_choice:'rule',final:'final'}}),{adopted:true,final:'final',rule:'rule'});
 assert.deepEqual(D.selection({selectedId:'rule',review:{decided_by:'RULE_ENGINE',review_execution:'CACHE_MISS'}}),{adopted:false,final:'rule',rule:'rule'});
});
