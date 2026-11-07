const test=require('node:test'),assert=require('node:assert/strict');
const V=require('../static/agent_decision_view.js');
test('autonomous explanation uses recorded plan, not compatibility score',()=>{
 const s={basis:{choice:{score:999},autonomous_decision:{policy:'LLM_AUTONOMOUS_CUSTOMER_V5',execution_state:'EXECUTED',candidate_count:1,price_score_rerank:false,selected_plan:{decision_summary:'쉬기로 선택',supporting_fact_ids:['F1','F1'],counterevidence_fact_ids:['F2']},attempts:[{provider:{execution:'LIVE_RESPONSES'},answer:{plans:[]}}]}}};
 const before=JSON.stringify(s),v=V.view(s);assert.equal(v.summary,'쉬기로 선택');assert.deepEqual(v.fact_ids,['F1','F2']);assert.match(v.choice_scope,/개인화 성공의 근거로 평가하지 않음/);assert.match(v.mode,/LIVE/);assert.doesNotMatch(V.panel(s),/999/);assert.equal(JSON.stringify(s),before);
 s.basis.autonomous_decision.attempts[0].provider.execution='CACHE_REPLAY';assert.match(V.view(s).mode,/캐시 재생/);
 s.basis.autonomous_decision.execution_state='RULE_FALLBACK';assert.equal(V.view(s).mode,'규칙 폴백');
 s.basis.autonomous_decision.execution_state='EXECUTION_HOLD';assert.match(V.view(s).mode,/실행 보류/);assert.doesNotMatch(V.view(s).mode,/LIVE/);
});
test('rule scenes stay unchanged; recorded text is escaped',()=>{
 assert.equal(V.view({basis:{}}),null);assert.equal(V.panel({basis:{}}),'');
 assert.doesNotMatch(V.panel({basis:{autonomous_decision:{selected_plan:{decision_summary:'<script>bad</script>'}}}}),/<script>/);
});
test('recorded context, menu alternatives and contract-unavailable breakfast stay separate',()=>{
 const scene={basis:{autonomous_decision:{policy:'V7',execution_state:'EXECUTED',price_score_rerank:false,candidate_count:2,
  input_context:{visit:{date:'2026-11-04',party_size:2,purpose:{status:'UNCONFIRMED'}},state:{time:'08:00'},facts:[{fact_ids:['F1'],summary:'다른 장소에서 메뉴 비교',source_scope:'other'}],products:[{sku_id:'SKU',label:'검증 메뉴'}],actions:[]},
  breakfast_outcome:'CONTRACT_UNAVAILABLE_DEFERRED_NOT_CUSTOMER_PREFERENCE',selected_plan:{decision_summary:'현재 이용 자격 확인 필요',supporting_fact_ids:['F1'],items:[]},
  attempts:[{provider:{execution:'LIVE_RESPONSES'},answer:{selected_index:0,plans:[{action_id:'SKIP'}, {action_id:'MEAL',items:[{sku_id:'SKU',quantity:2}],decision_summary:'대안 검토'}]}}]}}};
 const html=V.panel(scene);for(const text of ['방문 목적 미확인','다른 장소에서 메뉴 비교','검증 메뉴 × 2','조식 비선호·절약 성향으로 해석하지','최종 LLM 의도를 기존 가격 점수로 재정렬하지'])assert.ok(html.includes(text),text);
 assert.match(V.panel({basis:{}},{expected:true}),/LLM 판단 기록 없음/);
 delete scene.basis.autonomous_decision.input_context;assert.match(V.panel(scene),/현재 프로필로 당시 입력을 재구성하지/);
});

test('scene completion joins only the same customer, policy, input and plan without mutation',()=>{
 const d={input_sha256:'hash',contract_sha256:'contract',policy:'V7',customer_id:'A07',date:'2026-11-04',minute:900,execution_state:'VALIDATED',selected_plan:{decision_summary:'저장된 판단'}};
 const scene={basis:{autonomous_decision:d}},complete={...d,execution_state:'EXECUTED',state_after:{time:960}};
 const before=JSON.stringify(scene),plan={autonomous_decisions:[complete]};
 assert.match(V.panel(V.resolve(scene,plan)),/계획으로 실행했습니다/);
 assert.equal(JSON.stringify(scene),before);
 for(const field of ['input_sha256','contract_sha256','policy','customer_id','date','minute']){
  assert.equal(V.resolve(scene,{autonomous_decisions:[{...complete,[field]:'other'}]}),scene);
 }
 assert.equal(V.resolve(scene,{autonomous_decisions:[complete,complete]}),scene);
 assert.equal(V.resolve(scene,{autonomous_decisions:[{...complete,selected_plan:{decision_summary:'다른 판단'}}]}),scene);
 assert.match(V.panel(V.resolve(scene,{autonomous_decisions:[]})),/완료는 아직 확인되지/);
});

test('cross-day executed memory is shown as simulation, never inferred satisfaction',()=>{
 const scene={basis:{autonomous_decision:{input_context:{activity_experiences:[{date:'2026-11-04',start:1140,end:1180,action:'footbath',label:'족욕 <test>'}],facts:[]},selected_plan:{}}}};
 const before=JSON.stringify(scene),html=V.panel(scene);
 assert.match(html,/2026-11-04 19:00–19:40/);assert.match(html,/족욕 &lt;test&gt;/);
 assert.match(html,/만족·선호를 확인한 것은 아닙니다/);assert.equal(JSON.stringify(scene),before);
});

 test('recorded engine schedule is separate from the actual model explanation',()=>{
 const scene={basis:{autonomous_decision:{execution_state:'EXECUTED',selected_plan:{action_id:'MEAL',decision_summary:'이전 식사와 다음 일정을 비교'},input_context:{actions:[{action_id:'MEAL',schedule:{start_time:'08:30',end_time:'09:30',travel_minutes:14,wait_minutes:0}}]}}}};
 const before=JSON.stringify(scene),html=V.panel(scene);
 assert.match(html,/이전 식사와 다음 일정을 비교/);assert.match(html,/08:30–09:30 · 이동 14분 · 대기 0분/);
 assert.match(html,/실제 예약 확정 아님/);assert.equal(JSON.stringify(scene),before);
 delete scene.basis.autonomous_decision.input_context.actions[0].schedule;
 assert.doesNotMatch(V.panel(scene),/엔진이 제공한 실행 일정/);
 });

test('fixed breakfast SKU labels use only the same recorded order contract',()=>{
 const s={basis:{charge:{sku_contract:{components:[{sku_id:'BF',label:'포함 조식 성인'}]}},autonomous_decision:{selected_plan:{items:[{sku_id:'BF',quantity:2}],decision_summary:'저장된 실제 판단'},input_context:{products:[]}}}};
 const before=JSON.stringify(s);assert.match(V.panel(s),/포함 조식 성인 × 2/);assert.equal(JSON.stringify(s),before);
 delete s.basis.charge;assert.match(V.panel(s),/BF × 2/);assert.doesNotMatch(V.panel(s),/포함 조식 성인/);
});

test('V16 access rights, meal intent, clocks and original independent findings remain distinct',()=>{
 const d={date:'2026-11-05',minute:490,input_sha256:'input',customer_id:'A',policy:'LLM_AUTONOMOUS_CUSTOMER_V16',contract_sha256:'contract',execution_state:'EXECUTED',selected_plan:{action_id:'BF',order_total_krw:0,items:[{sku_id:'RIGHT',quantity:1}],meal_assessment:{kind:'LIGHT_MEAL',intake_assumption:'모델 가정'}},input_context:{actions:[{action_id:'BF',item_contracts:[{sku_id:'RIGHT',label:'포함 아동 이용권',quantity:1,semantics:'PERSON_ACCESS_ENTITLEMENT'}],order_total_krw:0,wait:{minutes:14},schedule:{departure_time:'08:10',arrival_time:'08:16',start_time:'08:30',end_time:'09:30',wait_minutes:14,travel_minutes:6}}]}};
 const scene={meal:'breakfast',basis:{autonomous_decision:d}},plan={autonomous_decisions:[d],recorded_review:{model:'saved-model',source_head:'source',review:{review:{review_status:'ISSUES_FOUND',findings:[{dimension:'TRACE',observation:'개인 근거 연결 누락',decision_refs:['input']}]}}}};
 const before=JSON.stringify(scene),html=V.panel(V.resolve(scene,plan));
 for(const text of ['현재 실호출 0회','개인 근거 연결 누락','인원별 이용·과금 권리','아동 전용 음식이 아님','LIGHT_MEAL','출발 08:10','도착 08:16','대기 14분','사람 승인 미완료','일대일 대응은 별도 검수'])assert.ok(html.includes(text),text);
 assert.equal(JSON.stringify(scene),before);
});

test('V19LS decision panel: trade-off note, non-blocking diagnostics and failure class are shown in plain words', () => {
 const V=require('../static/agent_decision_view.js');
 const d={policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS',execution_state:'EXECUTED',stability_policy:'LS_STABILITY_V1',
  selected_plan:{decision_summary:'피자힐에서 늦은 점심',tradeoff_note:'다른 식당은 135분 대기라 지금 가능한 곳을 고름'},
  selection_diagnostics:[{code:'MIXED_RECORD_ONE_SIDED',detail:['F17']}]};
 const html=V.panel({basis:{autonomous_decision:d}});
 assert.match(html,/상충 근거 대비 판단/);assert.match(html,/135분 대기/);assert.match(html,/혼합 평가\(좋은 점·아쉬운 점\)를 한쪽만/);assert.match(html,/실행을 막지 않음/);
 assert.match(html,/현재 판단 기준\(V19-LS\)/);
 const de=V.panel({basis:{autonomous_decision:{...d,day_end_match:{first_rejection:'EARLY_DAY_END_WITH_REMAINING_OPTIONS_REVIEW',accepted_by:'STRUCTURED_ALTERNATIVE'},selection_diagnostics:[{code:'QUANTITY_AT_OR_BELOW_PARTY_DESPITE_SHORTFALL_RECORD',detail:{}}]}}});
 assert.match(de,/하루 종료 재검토.*대안 항목에 명시/);assert.match(de,/과거 양 부족 기록/);
 const clean=V.panel({basis:{autonomous_decision:{...d,selection_diagnostics:[]}}});assert.match(clean,/기록된 충돌 없음/);
 const held=V.panel({basis:{autonomous_decision:{policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS',execution_state:'EXECUTION_HOLD',failure_class:'DELIVERY_UNCERTAIN',selected_plan:{}}}});
 assert.match(held,/전송 여부 불확실/);assert.match(held,/규칙 결과로 대체하지 않았습니다/);
 const v17=V.panel({basis:{autonomous_decision:{policy:'LLM_AUTONOMOUS_CUSTOMER_V17',execution_state:'EXECUTED',selected_plan:{decision_summary:'x'}}}});
 assert.doesNotMatch(v17,/선택 진단|상충 근거/,'V17 records show nothing new');
});
test('V19LS breakfast: room-contract coverage and extra cost are shown per line and in one summary; V16 lines unchanged', () => {
 const V=require('../static/agent_decision_view.js');
 const line=(q,b)=>({sku_id:'S',label:'조식 성인',quantity:q,semantics:'PERSON_ACCESS_ENTITLEMENT',...(b?{price_basis:b}:{})});
 const dec=lines=>({policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS',execution_state:'EXECUTED',date:'2026-10-25',minute:450,
  input_context:{visit:{date:'2026-10-25',party_size:3,breakfast:{covered_adults:2,whole_party_covered:false}},state:{time:'07:30'},actions:[{action_id:'BF',label:'조식',order_total_krw:59000,item_contracts:lines}]},
  selected_plan:{action_id:'BF',decision_summary:'조식',order_total_krw:59000,items:[]}});
 const partial=V.panel({basis:{autonomous_decision:dec([line(2,'객실 조식 포함(추가 비용 없음)'),line(1,'추가 결제')])}});
 assert.match(partial,/객실 조식 포함 2명 · 추가 비용 없음 · 추가 결제 1명 · 추가 비용 59,000원/);
 assert.match(partial,/조식 성인 × 1 · 인원별 이용·과금 권리 · 개별 음식 주문이나 아동 전용 음식이 아님 · 추가 결제/);
 const all=V.panel({basis:{autonomous_decision:dec([line(3,'객실 조식 포함(추가 비용 없음)')])}});
 assert.match(all,/객실 조식 포함 3명 · 추가 비용 없음 · 동행 전원 포함/);
 const old=V.panel({basis:{autonomous_decision:dec([line(3)])}});
 assert.doesNotMatch(old,/data-agent-breakfast-inclusion|객실 조식 포함/);
});
test('V19LS party-subset breakfast: diners who do not eat are named, never shown as the whole party covered', () => {
 const V=require('../static/agent_decision_view.js');
 const line=(q,b)=>({sku_id:'S',label:'조식 성인',quantity:q,semantics:'PERSON_ACCESS_ENTITLEMENT',price_basis:b});
 const d={policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS',execution_state:'EXECUTED',date:'2026-11-10',minute:490,
  input_context:{visit:{date:'2026-11-10',party_size:3},state:{time:'08:10'},actions:[{action_id:'BREAKFAST_BUFFET#D2',label:'더뷔페 조식 · 2명 이용',order_total_krw:0,item_contracts:[line(2,'객실 조식 포함(추가 비용 없음)')]}]},
  selected_plan:{action_id:'BREAKFAST_BUFFET#D2',decision_summary:'두 명만',order_total_krw:0,items:[]}};
 const html=V.panel({basis:{autonomous_decision:d}});
 assert.match(html,/객실 조식 포함 2명 · 추가 비용 없음 · 1명은 조식을 먹지 않음/);
 assert.doesNotMatch(html,/동행 전원 포함/);
});
test('V19LS meal quantity review is shown with the final quantity and no claim of forced upsizing', () => {
 const V=require('../static/agent_decision_view.js');
 const d={policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS',execution_state:'EXECUTED',date:'2026-11-07',minute:1071,stability_policy:true,
  meal_quantity_review:{first_rejection:'MEAL_QUANTITY_REVIEW_SHORTFALL_RECORD',final:{equivalents:4,party:3,cited:['A05-F25'],quantity_reason:'지난번 부족'}},
  input_context:{visit:{date:'2026-11-07',party_size:3},state:{time:'17:51'},actions:[]},selected_plan:{action_id:'meal:PIZZA_HILL',decision_summary:'피자와 파스타',items:[]}};
 const html=V.panel({basis:{autonomous_decision:d}});
 assert.match(html,/식사량 재검토: .*일반 환산 4인분\(3명\)을 선택했습니다 · 인용 A05-F25\. 더 많이 주문하라고 강제하지 않습니다/);
});

test('a breakfast record with partial state shows only the recorded fields (no blanks)',()=>{
 const scene={basis:{autonomous_decision:{policy:'LLM_AUTONOMOUS_CUSTOMER_V19LS_P2',execution_state:'EXECUTED',candidate_count:4,price_score_rerank:false,
  input_context:{visit:{party_size:3},state:{time:'08:10',fatigue_scale:{level:'여유',ratio_percent:0},today_remaining:{}}},selected_plan:{decision_summary:'포함 2명 이용'},attempts:[{provider:{execution:'LIVE_RESPONSES'}}]}}};
 const text=V.panel(scene).replace(/<[^>]+>/g,' ').replace(/\s+/g,' ');
 assert.match(text,/판단 시점 상태 휴식 한도의 0% \(여유\)/);
 assert.doesNotMatch(text,/휴식 한도 의|후보 개|저녁 미해결|방문 종료 엔진/);
 const full={...scene.basis.autonomous_decision,input_context:{visit:{party_size:3},state:{fatigue_scale:{value:0.4,rest_limit:2,ratio_percent:20,level:'여유'},today_remaining:{dinner_resolved:false,open_meal_options:8,open_activity_options:6,day_end:'23:00'}}}};
 assert.match(V.panel({basis:{autonomous_decision:full}}).replace(/<[^>]+>/g,' ').replace(/\s+/g,' '),/피로 0.4 · 휴식 한도 2의 20% \(여유\) · 저녁 미해결 · 남은 식사 후보 8개 · 활동 후보 6개 · 방문 종료 23:00/);
});
