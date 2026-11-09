// Reader views of an LLM decision and an LLM strategy: the rule page layout, no raw records, codes or repeated lines.
const test=require('node:test'),assert=require('node:assert/strict');
const V=require('../static/agent_decision_view.js');
const scene=()=>({label:'명월관 저녁',basis:{autonomous_decision:{policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS_INT4',execution_state:'EXECUTED',date:'2026-11-05',minute:1071,candidate_count:22,
 input_sha256:'a'.repeat(64),implementation_sha256:'b'.repeat(64),state_before:{fatigue:.1},state_after:{fatigue:.7},
 attempts:[{provider:{execution:'LIVE_RESPONSES',input_sha256:'c'.repeat(64)},answer:{selected_index:0,plans:[
  {action_id:'meal:MYONGWOLGWAN',decision_summary:'기념일 저녁으로 명월관을 고릅니다.',items:[{sku_id:'S1',quantity:1}],order_total_krw:86000},
  {action_id:'meal:ROOM_MEAL',decision_summary:'객실에서 편하게 먹는 선택도 가능하지만, 피로가 낮아 명월관을 선택했습니다.'}]}}],
 selected_plan:{action_id:'meal:MYONGWOLGWAN',decision_summary:'기념일 저녁으로 명월관을 고릅니다.',items:[{sku_id:'S1',quantity:1}],order_total_krw:86000,
  supporting_fact_ids:['A07-F10a'],counterevidence_fact_ids:['A07-F10a'],why_not_other_plans:'meal:ROOM_MEAL: 객실에서 편하게 먹는 선택도 가능하지만, 피로가 낮아 명월관을 선택했습니다.',
  meal_assessment:{kind:'FULL_MEAL',intake_assumption:'V18_SELECTION_NO_SEPARATE_INTAKE_STATEMENT',quantity_reason:'2인분 구성입니다.'}},
 input_context:{visit:{date:'2026-11-05',party_size:2,purpose:{value:'anniversary'},checked_in:true,breakfast:{covered_adults:2,whole_party_covered:true}},
  state:{time:'17:51',location:'SKYARD',meals:{dinner:true},fatigue_scale:{level:'여유',ratio_percent:4},modeled_need:{minutes_since_last_meal:52,engine_estimate:{modeled_satiety:'FULL_LIKELY'}},today_remaining:{dinner_resolved:false,open_meal_options:8,day_end:'23:00'}},
  meal_experiences:[],activity_experiences:[],
  facts:[{fact_ids:['A07-F10a'],summary:'명월관 한우 정식을 호평했다.',source_scope:'wh'},{fact_ids:['A07-F99'],summary:'참고 후기',source_scope:'other'}],
  actions:[{action_id:'meal:MYONGWOLGWAN',label:'명월관',item_contracts:[{sku_id:'S1',label:'한우 모둠 주물럭'}]},{action_id:'meal:ROOM_MEAL',label:'객실 룸서비스'}]}}}});
test('evidence story: rule-page sections, recorded text, no raw codes or hashes',()=>{
 const s=V.story(scene()),html=[s.summary,s.personal,s.state,s.comparison,...s.result.flat(),...s.metrics.flat()].join(' ').replace(/<[^>]+>/g,' ');
 assert.match(s.summary,/기념일 저녁/);assert.match(s.personal,/장단점 함께 고려/);assert.match(s.personal,/참고로 전달/);
 assert.match(s.state,/오늘 저녁 완료 · 마지막 식사 52분 전/);assert.doesNotMatch(s.state,/기록된 식사 없음/);
 assert.match(s.comparison,/객실 룸서비스/);assert.match(s.comparison,/2인분 구성/);
 for(const bad of [/aaaaaaaa|bbbbbbbb|cccccccc/,/FULL_MEAL|V18_SELECTION|LLM_AUTONOMOUS|LIVE_RESPONSES|meal:ROOM_MEAL|A07-F10a|<pre/])assert.doesNotMatch(html,bad);
 // the comparison sentence that only repeats the alternative's own summary is shown once
 assert.equal((s.comparison.match(/피로가 낮아 명월관을 선택했습니다/g)||[]).length,1);
 assert.deepEqual(s.metrics.map(m=>m[0]),['판단 방식','핵심 비교','개인 후기','주문']);assert.match(s.metrics[0][1],/실시간 AI 판단 · 개선형/);
});
test('LLM strategy result uses the rule strategy template and shows no codes',()=>{
 globalThis.HLAgentLab=undefined;const L=require('../static/strategy_agent_ui.js');
 const st=globalThis.HLAgentLab;const result={analysis_count:1,generated_count:1,customers:[{customer_id:'A01',status:'GENERATED_UNTESTED',current_choice_analysis:'객실에서 클럽 샌드위치를 선택했습니다.',nonselection_analysis:'피자힐은 서비스 시간 제약이 있었습니다.',nonselection_basis:'RECORDED_COMPARISON',hold_reasons:['SEMANTIC_HOLD: 사람 의미 검수가 남아 있습니다.'],
  strategies:[{id:'s1',kind:'convenience',title:'늦은 저녁 운영 점검',problem:'시간 제약이 있었습니다.',proposed_intervention:'상품 HC-MENU-086을 안내합니다.',expected_behavior_hypothesis:'피자힐을 고를 수 있습니다.',supporting_fact_ids:['A01-F01'],counterevidence_fact_ids:[],required_conditions:['마감 확인'],uncertainties:[],experiment_supported:false}],
  operator_recommendation:'HC-MENU-086의 판매 조건을 점검하세요.',provider:[{provider:{execution:'LIVE_RESPONSES'}}]}]};
 let html='';const ctx={enabled:true,ids:['A01'],target:'PIZZA_HILL',targetLabel:'피자힐',basis:'ACTUAL_RUN',run:{plans:{A01:{scenes:[{consume:true,label:'클럽 샌드위치',visit_date:'2026-10-24',basis:{charge:{krw:116000}}}]}},ledger:{run_id:'r'}},evidence:{A01:{facts:[{id:'A01-F01',summary:'객실 식사를 좋게 평가',source:'WALKERHILL'}]}},context:'행사 없음',name:()=>'No.0001',draw:()=>{},call:async()=>({job_id:'j',status:'DONE',result})};
 assert.ok(st&&st.render);void L;
 // render the result section directly through the same path the UI uses after a finished job
 const el={querySelectorAll:()=>[],querySelector:()=>null};st.render(ctx);
 return (async()=>{let clicked;const btn={addEventListener:(t,f)=>clicked=f};st.wire({querySelectorAll:()=>[],querySelector:s=>s==='[data-agent-analyze]'?btn:null},ctx);await clicked();await new Promise(r=>setTimeout(r,10));html=st.render(ctx);
  for(const cls of ['st-story-hero','st-story-choice','st-story-goal','st-idea st-idea-primary','st-operator-decision','05 / 운영 전략 최종 제안'])assert.ok(html.includes(cls),cls);
  assert.match(html,/해당 상품/);assert.match(html,/이번 방문의 비교 기록으로 확인/);assert.match(html,/운영 가설 · 실험 미지원/);
  assert.doesNotMatch(html.replace(/<[^>]+>/g,' '),/HC-MENU-086|SEMANTIC_HOLD|RECORDED_COMPARISON|LIVE_RESPONSES|A01-F01/);void el;})();
});
