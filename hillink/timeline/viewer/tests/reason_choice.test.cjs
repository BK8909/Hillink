const test=require('node:test'),assert=require('node:assert/strict'),R=require('../static/reason_choice.js');
function x(){return {scene:{act:'turn_dinner',meal:'dinner',label:'마르게리타 피자 S',loc:'PIZZA_HILL'},selectedId:'s',decision:{packet:{packet_sha256:'p',context_factors:{}}},rawCands:[{candidate_id:'s',service_contract:{venue_id:'PIZZA_HILL'},world_allowed:true,terms:[{factor:'음식 경험',value:1.2,kind:'profile_and_offer',facet:'food',fact_ids:[]},{factor:'저녁 끼니 해결',value:3}],score_contribution:{terms:[]}}],facts:[]};}
test('first page explains meal need, not invented food preference or review quote',()=>{const a=x(),before=structuredClone(a),r=R.compose(a);assert.match(r.sentences[0],/저녁 시간이 되어 끼니를 채우는.*피자힐/);assert.doesNotMatch(r.sentences.join(' '),/좋아|마르게리타.*선호|후기에서 추출|통계/);assert.deepEqual(a,before)});
test('measured space contribution is a cause; common food baseline is not',()=>{const a=x(),r=a.rawCands[0];r.terms.push({factor:'야경 · 공간 경험',facet:'space',kind:'profile',value:1.08,fact_ids:['F2']});r.score_contribution.terms.push({factor:'야경 · 공간 경험',evidence_delta:.63});const b=R.compose(a);assert.match(b.sentences[0],/공간.*중요하게 여겨.*피자힐/);assert.deepEqual(b.audit.fact_ids,['F2']);assert.equal(b.audit.contributions[0].value,.63);assert.doesNotMatch(b.sentences.join(' '),/친구|콰트로|마르게리타/)});
test('linked fact without measured contribution does not establish a preference',()=>{const a=x();a.rawCands[0].terms[0].fact_ids=['F1'];a.rawCands[0].score_contribution.terms.push({factor:'음식 경험',evidence_delta:0});assert.equal(R.compose(a).audit.reason_kind,'COMMON_MEAL_AND_ELIGIBILITY')});
test('unobserved planner bars alone are not review evidence',()=>{const a=x();a.sampling='NATIVE';a.rawCands[0].terms=[];a.rawCands[0].profile_feature_marginals={'bars.food':{weight_delta_at_fixed_state:1}};assert.equal(R.compose(a).audit.reason_kind,'ELIGIBLE_WEIGHTED_SELECTION')});
test('planner observed marginal is qualified as a contribution to sampling',()=>{const a=x();a.sampling='NATIVE';a.decision.packet.context_factors.food_observation={indirect_fact_ids:{space:['F2']}};a.rawCands[0].profile_feature_marginals={'bars.space':{weight_delta_at_fixed_state:.3}};const r=R.compose(a);assert.match(r.sentences[0],/고려한 선택지 중/);assert.deepEqual(r.audit.fact_ids,['F2'])});
test('movement stays with the accepted movement formatter',()=>{assert.equal(R.compose({scene:{act:'move'}}),null)});
test('an adopted review cannot borrow a rejected rule winner trait',()=>{const a=x();a.review={decided_by:'LLM_ADOPTED',reasons:[],rule_choice:'s',final:'other'};a.rawCands[0].terms.push({factor:'공간',facet:'space',kind:'profile',value:1,fact_ids:['F1']});const r=R.compose(a);assert.equal(r.audit.review,true);assert.deepEqual(r.audit.fact_ids,[]);assert.doesNotMatch(r.sentences.join(' '),/전망|선호/)});
test('unapplied general research remains absent',()=>{const a=x();a.rawCands[0].general_food_evidence={applied:false,delta:-.2,stage:'BEFORE_SELECTION',prior_event_ids:['e']};assert.notEqual(R.compose(a).audit.reason_kind,'APPLIED_GENERAL_EVIDENCE')});
test('missing decision is explained without fabricating a source',()=>{const r=R.compose({scene:{act:'theatre',label:'입장권'}});assert.match(r.sentences[0],/판단 기록이 남아 있지/);assert.deepEqual(r.audit.fact_ids,[])});

const S=require('../static/reason_story.js');
test('legacy decision join requires exact date, action, time, location and unique executed event',()=>{
 const scene={visit_date:'2026-10-24',t0:600,loc:'POOL',act:'sku'},e={date:scene.visit_date,start:'10:00',location_id:'POOL',action_id:'sku',event_id:'e'};
 const d={selected_action:'sku',execution_status:'EXECUTED',actual_next_event_id:'e',packet:{context_factors:{date:scene.visit_date}}},p={m4:{activity_history:[e],decisions:[d]}};
 assert.equal(S.decisionOf(p,scene),d);for(const [k,v] of Object.entries({visit_date:'2026-10-25',t0:601,loc:'ROOM',act:'other'}))assert.equal(S.decisionOf(p,{...scene,[k]:v}),null);
 p.m4.decisions.push(structuredClone(d));assert.equal(S.decisionOf(p,scene),null);
});
test('stored review reasons use their actual llm payload and do not become a new call',()=>{const a=x();a.review={decided_by:'LLM_REVIEW_ADOPTED',llm:{reasons:[{type:'업장 정보',text:'일행의 식사 비용을 낮추는 선택이다.',fact_ids:[]}]}};const r=R.compose(a);assert.equal(r.audit.reason_kind,'ADOPTED_REVIEW_COST');assert.match(r.sentences[0],/식사 비용.*피자힐/);assert.doesNotMatch(r.sentences[0],/호출|새로.*검토/)});

test('explicit negative alternative is a reason only when its recorded effect could alter ranking',()=>{const a=x();a.rawCands[0].final_score=5;a.rawCands.push({candidate_id:'bad',world_allowed:true,final_score:4.5,service_contract:{venue_id:'MOEGI'},terms:[{factor:'명시적 재방문 거부(같은 업장)',value:-1,fact_ids:['NEG']}]});let r=R.compose(a);assert.equal(r.audit.reason_kind,'EXPLICIT_NEGATIVE_ALTERNATIVE');assert.match(r.sentences[0],/다시 가고 싶지/);assert.deepEqual(r.audit.fact_ids,['NEG']);a.rawCands[1].final_score=1;assert.notEqual(R.compose(a).audit.reason_kind,'EXPLICIT_NEGATIVE_ALTERNATIVE')});
test('an unsupported satisfaction or regret is never inferred from an ordinary venue memory',()=>{const a=x();a.rawCands[0].terms.push({factor:'익숙한 곳 · 실제 이용 경험',facet:'routine',kind:'profile',value:.2,fact_ids:['V']});const r=R.compose(a);assert.doesNotMatch(r.sentences.join(' '),/맛있|행복|만족|불만|후회/)});

test('breakfast reuses its native score parts without claiming a new M4 calculation',()=>{const a=x();a.rawCands=[];a.selectedId=null;a.scene={act:'turn_breakfast',meal:'breakfast',loc:'THE_BUFFET',label:'호텔 조식'};a.turnDecision={choice:{product_id:'BREAKFAST_BUFFET',venue_id:'THE_BUFFET',score:4,feasible:true},reasons:[{factor:'음식 경험',facet:'food',value:1.5,fact_ids:['B1'],parts:{review:.3,common:1.2}}]};const r=R.compose(a);assert.match(r.sentences[0],/아침.*음식 경험.*더뷔페/);assert.equal(r.audit.source_kind,'NATIVE_TURN_SCORE');assert.equal(r.audit.contributions[0].value,.3)});


test('generic recovery scores do not turn swimming or golf into a need to rest',()=>{for(const act of ['pool','hc_golf']){const a=x();a.scene={act,label:act==='pool'?'수영':'골프',loc:'FACILITY'};a.rawCands[0].terms=[{factor:'피로 회복',value:1}];a.decision.packet.context_factors.fatigue_proxy=.9;assert.doesNotMatch(R.compose(a).sentences[0],/쉴 필요/);}});
test('activity grammar separates resting, reading and ordering beverages',()=>{for(const [act,label,loc,expected] of [['ROOM_REST','객실에서 쉬기','ROOM',/객실에서 잠시 쉬기로/],['library','책 · 음악','LIBRARY',/책과 음악을 즐기기로/],['hc_drink','칵테일','LUX_BAR',/럭스바에서 주문하기로/]]){const a=x();a.scene={act,label,loc,consume:true};a.rawCands[0].service_contract={venue_id:loc};a.rawCands[0].terms=[];const t=R.compose(a).sentences[0];assert.match(t,expected);assert.doesNotMatch(t,/쉬기를|음악을 하기로|칵테일.*먹기로/);}});
test('scheduled checkin is not described as a sampled personal choice',()=>{const a=x();a.scene={act:'checkin',label:'체크인'};a.sampling='NATIVE';assert.equal(R.compose(a).audit.reason_kind,'SCHEDULE')});

test('native turn joins through an exact executed event without borrowing another date or customer',()=>{
 const e={event_id:'e',date:'2026-10-25',start:'09:10',location_id:'GRAND_ROOM',action_id:'SKIP_BREAKFAST'},s={visit_date:e.date,visit_day:2,t0:550,t1:610,loc:e.location_id,act:'turn_breakfast',turn:'breakfast',meal:'breakfast',basis:{m4:{event_id:'e'}}};
 const c={persona_id:'p',decided_at:e.start,choice:{product_id:e.action_id,map_loc:e.location_id,feasible:true},reasons:[{factor:'휴식',facet:'rest_need',fact_ids:['F'],parts:{review:.72}}]};
 const f={plans:{p:{scenes:[s],m4:{activity_history:[e]}}},runs:[{visit_date:e.date,visit_day:2,turn:'breakfast',customers:[c]}]};
 const x=S.input(f,'p',0);assert.equal(x.turnDecision,c);assert.match(R.compose(x).sentences[0],/쉬는 시간.*아침 식사는 건너뛰고/);assert.doesNotMatch(R.compose(x).sentences[0],/먹을 때/);
 c.persona_id='other';assert.equal(S.input(f,'p',0).turnDecision,null);c.persona_id='p';e.date='2026-10-26';assert.equal(S.input(f,'p',0).turnDecision,null);
});

test('skipping lunch at a cafe location cannot become a meal purchase in narration',()=>{const a=x();a.scene={act:'lunch_skip',loc:'THE_PAVILION',label:'점심 건너뜀',meal:'lunch',consume:false};a.sampling='NATIVE';a.rawCands[0].terms=[];const r=R.compose(a);assert.match(r.sentences[0],/점심은 건너뛰기로/);assert.doesNotMatch(r.sentences[0],/파빌리온에서 점심을 먹/)});

test('event information check is distinct from recorded event entry',()=>{const a=x();a.rawCands[0].service_contract={venue_id:'FOREST_PARK'};a.rawCands[0].terms=[];a.scene={act:'WINE_FAIR:check',loc:'FOREST_PARK',label:'와인페어 · 안내 확인',consume:false};let r=R.compose(a);assert.match(r.sentences[0],/안내를 확인하기로/);assert.doesNotMatch(r.sentences[0],/참여하기로/);a.scene.act='turn_event';a.scene.label='와인페어';r=R.compose(a);assert.match(r.sentences[0],/와인페어에 참여하기로/)});

test('executed room service uses actual venue and fatigue, not product-as-activity or future planning',()=>{
 const a=x();a.pid='p';a.scene={act:'turn_dinner',meal:'dinner',loc:'VISTA_ROOM',consume:true,label:'룸서비스 세트'};a.selectedId='ROOM_MEAL';a.rawCands[0].candidate_id='ROOM_MEAL';delete a.rawCands[0].service_contract;a.rawCands[0].terms.push({factor:'휴식 · 회복',value:.24});a.decision.execution_status='EXECUTED';a.decision.packet.context_factors.fatigue_proxy=1.2;a.charge={sku_contract:{venue_id:'ROOM_MEAL',label:'룸서비스 세트'}};
 const r=R.compose(a);assert.match(r.sentences[0],/피로.*객실에서 룸서비스/);assert.doesNotMatch(r.sentences.join(' '),/세트를 하|하기로|먹기로|좋아|선호/);assert.equal(r.audit.action_phase,'EXECUTED');assert.equal(r.audit.reason_kind,'RECORDED_ROOM_MEAL_RECOVERY');
 a.scene.decision_phase='PLANNED';assert.match(R.compose(a).sentences[0],/생각하고/);
 a.scene.decision_phase='ORDER_CONFIRMED';assert.match(R.compose(a).sentences[0],/룸서비스 세트를 주문했어요/);
});
