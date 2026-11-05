const test=require('node:test'),assert=require('node:assert/strict');
const V=require('../static/strategy_agent_ui.js');
test('partial pair has no success amounts or broken null comparison',()=>{
 const html=V.pairHTML({comparison:null,readiness:{comparable:false,reasons:['EXECUTION_HOLD']}});
 assert.match(html,/검수 보류/);assert.doesNotMatch(html,/호텔 전체|0원|A 행동/);
});
test('fixed selection arithmetic is separate from autonomous re-inference',()=>{
 const html=V.pairHTML({comparison:{before_krw:100,after_krw:100,delta_krw:0,venues:[]},
 readiness:{comparable:true,execution_kind:'AUTONOMOUS_REINFERENCE'},fixed_choice_repricing:{delta_krw:0}});
 assert.match(html,/행동을 다시 판단/);assert.match(html,/기존 주문을 그대로/);assert.match(html,/새 구매가 아닙니다/);
});

test('included breakfast is not labeled dinner conversion',()=>{
 const html=V.pairHTML({comparison:{before_krw:100,after_krw:100,delta_krw:0,venues:[]},readiness:{comparable:true},
 target_meal_comparison:{status:'OBSERVED_SIMULATED_MEAL_PERIOD',scope:{date:'2026-11-05',meal:'dinner'},before:{selected_teams:0,paid_krw:0},after:{selected_teams:0,paid_krw:0},entering_customers:[]}});
 assert.match(html,/저녁 목표 업장 선택/);assert.match(html,/새로 선택 0팀/);assert.match(html,/포함 조식·다른 날짜 이용은 이 유입 수에 넣지/);
});
