const test=require('node:test'),assert=require('node:assert/strict');
const P=require('../static/strategy_personal.js'),S=require('../static/strategy_current.js');
const bundle={facts:[{id:'F1',summary:'여러 음식 비교',features:['buffet_food_exploration'],anchors:[]},{id:'F2',summary:'가격 대비 아쉬움',polarity:'negative',features:[],anchors:[]}],patterns:{food_exploration:{contributions:[{fact_ids:['F1','MISSING'],post_ids:['post1'],experience_group:'one'},{fact_ids:['F1'],post_ids:['post1'],experience_group:'one'}]}}};
test('recommendations use actual authorized facts and explicit provenance counts, not scores or guessed repetition',()=>{
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:bundle},catalog:{},decisions:[]});
 const i=r.proposals[0].ideas[0];assert.equal(i.evidence.support.length,1);assert.equal(i.evidence.posts.length,1);assert.equal(i.evidence.experiences.length,1);assert.equal(i.evidence.qualifications.length,0);assert.equal(i.status,'UNTESTED_HYPOTHESIS');assert.equal(i.basis,'PROFILE_ONLY');assert.equal(i.evidence.strength,'추출 요약 · 원문 의미 검수 필요');assert.equal(r.proposals[0].ideas.length,1);assert.equal(i.expected_revenue,undefined);
});
test('operator assumptions remain hypothetical even with a real visit and supported discount',()=>{
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C'],basis:'OPERATOR_ASSUMPTION',assumed_origin:'EXTERNAL_DELIVERY'},bundles:{C:bundle},catalog:{},decisions:[{customer_id:'C',chosen:{label:'실제 피자'}}],executable:[{sku:'S',venue:'THE_BUFFET',customers:['C']}]});
 assert.equal(r.basis,'OPERATOR_ASSUMPTION');for(const i of r.proposals[0].ideas){assert.equal(i.basis,'OPERATOR_ASSUMPTION');assert.deepEqual(i.ab_options,[]);assert.equal(i.assumed_origin,'EXTERNAL_DELIVERY');assert.doesNotMatch(i.content,/현재 선택 실제 피자/);}
});
test('laboratory scopes select only runnable registered customers',()=>{
 const people=[{id:'a',type:'가족'},{id:'b',type:'커플'},{id:'c',type:'가족'}];
 assert.equal(P.selectCustomers(people,{scope:'all'}).length,3);
 assert.deepEqual(P.selectCustomers(people,{scope:'selected',ids:['a','private-unknown']}).map(p=>p.id),['a']);
 assert.deepEqual(P.selectCustomers(people,{scope:'type',type:'가족'}).map(p=>p.id),['a','c']);
 assert.deepEqual(P.selectCustomers(people,{scope:'one',ids:['b']}).map(p=>p.id),['b']);
});
test('actual consumption links the event to its scene and all basket receipt lines without a same-time unrelated order',()=>{
 const scene={t0:1039,act:'turn_dinner',loc:'PIZZA_HILL',visit_date:'2026-09-10',basis:{m4:{event_id:'evt'}}};
 const event={event_id:'evt',date:'2026-09-10',start:'17:19',action_id:'HC_BASKET',meal_slot:'dinner',venue_id:'PIZZA_HILL'};
 const plan={scenes:[scene],m4:{decisions:[{execution_status:'EXECUTED',actual_next_event_id:'evt',selected_action:'HC_BASKET',packet:{packet_sha256:'packet',context_factors:{time:1023},candidates:[]}}],activity_history:[event]}};
 const row={visit_date:event.date,time:event.start,act:scene.act,t0:scene.t0,loc:scene.loc,venue_id:scene.loc};
 const flow={plans:{C:plan},ledger:{receipts:{C:{rows:[{...row,product:'피자',paid_krw:69000},{...row,product:'파스타',paid_krw:48000},{...row,act:'other',paid_krw:999999}]}}}};
 const d=P.actualDecisions(flow)[0];assert.equal(d.chosen.total_krw,117000);assert.equal(d.chosen.label,'피자 + 파스타');assert.equal(d.time,'17:03');assert.equal(d.actual_time,'17:19');
 plan.scenes=[];assert.equal(P.actualDecisions(flow)[0].chosen.total_krw,null);
});
test('same-venue spend conclusion cannot claim hotel-wide gains as target success',()=>{
 const v=S.verdict({objective:'spend',intent:'increase',target:'PIZZA_HILL'},{eligible_customers:['C'],paid_delta:84000,cohort_target_delta:-1000});assert.equal(v.status,'MAINTAIN');assert.match(v.text,/他|다른 업장/);
});

test('a lab group cannot label profile-only people as observed visitors',()=>{
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['A','B']},bundles:{A:bundle,B:bundle},catalog:{},decisions:[{customer_id:'A',chosen:{label:'meal'}}]});assert.equal(r.basis,'MIXED');assert.equal(r.observed_customers,1);assert.equal(r.profile_only_customers,1);assert.equal(r.proposals[1].basis,'PROFILE_ONLY');
});

test('ranking follows relevant evidence rather than rule order or duplicate fact volume',()=>{
 const facts=[{id:'E',summary:'메뉴 탐색',features:['limited_menu'],posts:['p1'],experiences:[]},{id:'S',summary:'더뷔페 창가 경험',features:['window'],posts:['p2'],experiences:[]}];
 const run=fs=>P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:{facts:fs}},catalog:{}}).proposals[0];
 const a=run(facts);assert.equal(a.ideas[0].kind,'space');assert.equal(a.ranking_trace.find(x=>x.kind==='space').criteria.target_evidence,1);
 const duplicated=[...facts,...Array.from({length:20},(_,i)=>({...facts[0],id:'D'+i}))];const b=run(duplicated);assert.equal(b.ideas[0].kind,'space');assert.equal(b.ranking_trace.find(x=>x.kind==='experience').criteria.observation_groups,1);
 assert.equal(P.observationUnits([{posts:['one'],experiences:['x']},{posts:['two'],experiences:['x']},{posts:['two'],experiences:['y']},{posts:[],experiences:[]}]),1);
 const reversed=run([...facts].reverse());assert.deepEqual(reversed.ideas.map(i=>i.kind),a.ideas.map(i=>i.kind));
});
test('counterexamples must relate to the particular recommendation',()=>{
 const facts=[{id:'E',summary:'메뉴 탐색',features:['limited_menu'],posts:['p']},{id:'V',summary:'가격 상한',features:['price_cap'],polarity:'negative',posts:['q']},{id:'N',summary:'무관한 경험',features:['weather_failure'],polarity:'negative',posts:['r']}];
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:{facts}},catalog:{}}).proposals[0];
 assert.equal(r.ideas.find(i=>i.kind==='experience').evidence.qualifications.length,0);assert.deepEqual(r.ideas.find(i=>i.kind==='value').evidence.qualifications.map(f=>f.id),['V']);assert.doesNotMatch(r.ideas.find(i=>i.kind==='value').content,/할인 후에도 만족/);
});
test('paid cafe decisions retain actual quantities and distinguish planner from scored evidence',()=>{
 const event={event_id:'cafe',date:'2026-09-11',start:'10:56',meal_slot:'snack',venue_id:'THE_PAVILION'};
 const scene={visit_date:event.date,t0:656,act:'cafe',loc:event.venue_id,basis:{m4:{event_id:'cafe'}}};
 const row={visit_date:event.date,time:event.start,t0:656,act:'cafe',loc:event.venue_id,venue_id:event.venue_id,quantity:2};
 const flow={plans:{C:{scenes:[scene],m4:{activity_history:[event],decisions:[{execution_status:'EXECUTED',actual_next_event_id:'cafe',selected_action:'CAFE',packet:{kind:'PLANNER',packet_sha256:'c',context_factors:{time:653},candidates:[]}}]}}},ledger:{receipts:{C:{rows:[{...row,product:'브런치',paid_krw:56000},{...row,product:'주스',paid_krw:44000}]}}}};
 const d=P.actualDecisions(flow)[0];assert.equal(d.status,'NO_TERM_DECOMPOSITION');assert.equal(d.chosen.total_krw,100000);assert.deepEqual(d.orders.map(r=>r.quantity),[2,2]);assert.deepEqual(d.chosen.facts,[]);
});

test('card explanation prioritizes the actual evidence that supports its concrete intervention',()=>{
 const fs=[{id:'A',summary:'체크인 전 이용',features:['before_checkin'],posts:['p']},{id:'Z',summary:'식당 사전예약 경험',features:['restaurant_prebook_offpeak'],posts:['q']},{id:'ZZ',summary:'예약 대기열 활용',features:['split_queue_couple'],posts:['r']}];
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:{facts:fs}},catalog:{}}).proposals[0].ideas.find(i=>i.kind==='convenience');
 assert.match(r.personal_reason,/^식당 사전예약 경험/);assert.deepEqual(r.intervention_fact_ids,['Z','ZZ']);
});

test('price-driven alternatives do not invent a scheduling preference or repeated evidence',()=>{
 const fact={id:'P',summary:'비싼 음식 대신 다른 지출 선택',features:[],posts:['p']};
 const bundle={facts:[fact,{...fact,id:'Q'}],patterns:{practical_alternative:{contributions:[{fact_ids:['P','Q'],post_ids:['p']}]}}};
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:bundle},catalog:{}}).proposals[0];assert.deepEqual(r.ideas.map(i=>i.kind),['value']);assert.equal(r.ideas[0].personal_reason,fact.summary);assert.equal(r.ideas[0].evidence.observation_units,1);
});

test('an activity tag alone does not prove a convenience motivation',()=>{
 const facts=[{id:'R',summary:'룸서비스를 구매하지 않음',features:['roomservice'],posts:['one']}];
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:{facts}},catalog:{}}).proposals[0];assert.equal(r.ideas.length,0);assert.match(r.conclusion,/근거가 부족/);
});

test('opaque event features use exact facet ancestry, never novelty or excluded/weak/hidden links',()=>{
 const facts=[{id:'F',summary:'registered food preference',features:['event_1'],posts:['one']},{id:'G',summary:'same post',features:['event_2'],posts:['one']},{id:'X',summary:'excluded',features:['event_x']},{id:'W',summary:'weak',features:['event_w']}];
 const bundle={facts,facet_evidence:{food_specific:{present:true,evidence:[{fact_id:'F',feature:'event_1',grade:'rep'},{fact_id:'G',feature:'event_2',grade:'rep'},{fact_id:'X',feature:'event_x',grade:'exclude'},{fact_id:'W',feature:'event_w',grade:'weak'},{fact_id:'HIDDEN',feature:'event_h',grade:'rep'}]},novelty:{present:true,evidence:[{fact_id:'F',feature:'event_1',grade:'rep'}]}}};
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:bundle},catalog:{}}).proposals[0];
 assert.deepEqual(r.ideas.map(i=>i.kind),['food']);assert.deepEqual(r.ideas[0].evidence.support.map(f=>f.id),['F','G']);assert.equal(r.ideas[0].evidence.observation_units,1);assert.equal(r.ideas[0].status,'UNTESTED_HYPOTHESIS');assert.equal(r.ideas[0].evidence.facet_links[0].semantic_status,'SEMANTIC_HOLD');
});
test('facet fallback does not change recommendations with existing semantic feature support',()=>{
 const bundle={facts:[{id:'F',summary:'menu',features:['limited_menu']}],facet_evidence:{space:{present:true,evidence:[{fact_id:'F',feature:'limited_menu',grade:'rep'}]}}};
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:bundle},catalog:{}}).proposals[0];assert.deepEqual(r.ideas.map(i=>i.kind),['experience']);
});
test('restored companion, future or unknown evidence does not become personal observed preference',()=>{
 const facts=['other','unknown'].map((actor,i)=>({id:'A'+i,summary:'companion preference',actor,features:['pasta_preference']})).concat([{id:'F',summary:'future coupon',time_scope:'future',features:['coupon']}]);
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:{facts}},catalog:{}}).proposals[0];assert.equal(r.ideas.length,0);assert.equal(r.evidence_coverage.fact_count,3);
});
test('an excluded facet cannot be resurrected by a matching restored feature tag',()=>{
 const bundle={facts:[{id:'F',summary:'discount not applicable',features:['coupon']}],facet_evidence:{benefit:{present:false,evidence:[{fact_id:'F',feature:'coupon',grade:'exclude'}]}}};
 const r=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['C']},bundles:{C:bundle},catalog:{}}).proposals[0];assert.equal(r.ideas.length,0);
});

test('cross-category fallback suppression is diagnosed without approving excluded or weak evidence',()=>{
 const facts=[{id:'coupon-event',summary:'booking evidence needs review',features:['coupon'],actor:'author',time_scope:'source_experience'}, {id:'rep-event',summary:'existing facet requires transfer review',features:['opaque-event']},{id:'weak-event',summary:'weak evidence',features:['opaque-weak']}];
 const b={facts,facet_evidence:{benefit:{present:false,evidence:[{fact_id:'coupon-event',feature:'coupon',grade:'exclude'}]},value_check:{present:true,evidence:[{fact_id:'rep-event',feature:'opaque-event',grade:'rep'},{fact_id:'weak-event',feature:'opaque-weak',grade:'weak'}]}}};
 const audit=P.facetAudit(b);assert.deepEqual(audit.triggers,[{kind:'benefit',fact_id:'coupon-event',path:'FEATURE',excluded:true}]);assert.deepEqual(audit.suppressed_rep_links.map(e=>e.fact_id),['rep-event']);
 const value=P.RULES.find(r=>r.id==='value');assert.deepEqual(P.facetLinks(b,value),[]);
 // Independent counterfactual isolates the customer-wide guard; never changes the real Fact.
 const withoutTrigger={...b,facts:facts.filter(f=>f.id!=='coupon-event')};assert.deepEqual(P.facetLinks(withoutTrigger,value).map(e=>e.fact_id),['rep-event']);
 const before=JSON.stringify(b),p=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['synthetic']},bundles:{synthetic:b},catalog:{}}).proposals[0];
 assert.equal(p.ideas.length,0);assert.equal(p.evidence_coverage.hold_reason,'FACET_GRADE_REVIEW');assert.match(p.evidence_coverage.hold_message,/개인화 전략 근거 검수 보류/);assert.doesNotMatch(p.evidence_coverage.hold_message,/coupon-event|rep-event/);assert.equal(JSON.stringify(b),before);
});
test('candidate generation is neither human semantic approval nor a completed experiment',()=>{
 const m=P.recommend({goal:{target:'THE_BUFFET',customer_ids:['one','two']},bundles:{one:bundle,two:{facts:[{id:'U',features:[],summary:'unmapped'}]}},catalog:{}});
 const s=P.summarizeCohort(m);assert.equal(s.review.generated,1);assert.equal(s.review.semantic_approved,0);assert.equal(s.review.semantic_pending,2);assert.equal(s.review.ab_status,'NOT_ATTACHED');assert.equal(s.review.hypothesis_count,1);
 m.proposals[0].semantic_status='SEMANTIC_APPROVED';const approved=P.summarizeCohort(m);assert.equal(approved.review.semantic_approved,1);assert.equal(approved.review.semantic_pending,1);assert.equal(approved.effect_status,'NOT_TESTED');
});
