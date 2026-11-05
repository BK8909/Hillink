/* Display only. Reasons come from the selected candidate before execution.
 * No profile inference from prose, no scoring, no LLM calls, no plan writes.
 */
(function(root){
'use strict';
const VERSION='choice-reason-v2-action-phase';
const VENUE={PIZZA_HILL:'피자힐',THE_BUFFET:'더뷔페',MOEGI:'모에기',GEUMRYONG:'금룡',MYONGWOLGWAN:'명월관',ONDAL:'온달',THE_PAVILION:'더 파빌리온',LE_PASSAGE:'르 파사쥬',ROOM_MEAL:'룸서비스',LUX_BAR:'럭스바'};
const ACT={theatre:'빛의 시어터 관람',footbath:'족욕',night_footbath:'족욕',pool:'수영',sauna:'사우나',night_walk:'야경 산책',forest_walk:'산책',garden_walk:'산책',ROOM_REST:'객실 휴식',library:'독서와 음악 감상',room_rest:'객실 휴식',room_nap:'낮잠',room_bath:'객실 욕조에서 휴식',room_night:'객실 휴식',sleep:'취침',lunch_skip:'점심 건너뛰기'};
const PERSONAL={space:'전망과 공간을 즐기는 성향',food:'음식 경험을 중요하게 여기는 성향',food_specific:'후기에서 확인된 메뉴 기호',routine:'전에 이용한 곳이라는 점',warm_rest:'따뜻하게 쉬는 활동을 선호하는 성향',rest_need:'쉬는 시간을 중요하게 여기는 성향',value_check:'비용을 따져 보는 성향',benefit:'혜택을 살피는 성향',novelty:'새로운 경험에 관심을 두는 성향',active:'몸을 움직이는 활동을 즐기는 성향',premium:'특별한 경험을 중시하는 성향',breakfast_priority:'아침 식사를 챙기는 성향',practical_alt:'간편한 대안을 찾는 성향',promo:'행사에 관심을 두는 성향'};
const INTERNAL=/\b[A-Z]{2,}[_-][A-Z0-9_-]+\b|\b[a-z]+_[a-z0-9_]+\b/;
function clean(s){return String(s||'').replace(/\s*·?\s*(객실포함|객실 포함|패키지 포함|포함 혜택|무료 대상 투숙객|규격 미정|이용료 가정|기존 메뉴 기준 가상 계산)/g,'').trim();}
function compose(x){
 const s=x.scene||{},turn=x.turnDecision;
 const row=(x.rawCands||[]).find(r=>r.candidate_id===x.selectedId)||(turn?{candidate_id:turn.choice.product_id,world_allowed:turn.choice.feasible,final_score:turn.choice.score,service_contract:{venue_id:turn.choice.venue_id},terms:turn.reasons||[],score_contribution:{terms:(turn.reasons||[]).map(t=>({factor:t.factor,evidence_delta:t.parts?.review||0}))}}:null);
 const terms=row?.terms||[],cf=x.decision?.packet?.context_factors||{};
 if(s.act==='move')return null;
 const venue=VENUE[s.loc]||VENUE[row?.service_contract?.venue_id]||VENUE[x.charge?.sku_contract?.venue_id]||VENUE[row?.candidate_id],meal=({breakfast:'아침',lunch:'점심',dinner:'저녁'})[s.meal]||(/lunch/.test(s.act||'')?'점심':/dinner/.test(s.act||'')?'저녁':/breakfast/.test(s.act||'')?'아침':null);
 let action=ACT[s.act]||({SKYARD:'족욕',GRAND_POOL:'실내 수영',VISTA_POOL:'실내 수영',THEATRE_OF_LIGHT:'빛의 시어터 관람'})[s.loc]||clean(s.label)||'이 활동';if(INTERNAL.test(action))action='이 활동';
 if(venue&&meal&&s.act!=='lunch_skip')action=venue+'에서 '+meal+' 식사';
 else if(venue&&s.consume)action=venue+' 이용';
 const last=action.charCodeAt(action.length-1),object=last>=0xac00&&last<=0xd7a3&&(last-0xac00)%28?'을':'를';
 const skipBreakfast=turn?.choice?.product_id==='SKIP_BREAKFAST';
 const rest=/^(ROOM_REST|room_rest|room_nap|room_bath|room_night)$/.test(s.act||'');
 const activity=s.act==='turn_event'?`${action}에 참여하기로 했어요`:/^[A-Z_]+:check$/.test(s.act||'')?`${action.replace(/\s*·\s*안내 확인$/, '')} 안내를 확인하기로 했어요`:rest?(s.act==='room_bath'?'객실 욕조에서 잠시 쉬기로 했어요':s.act==='room_nap'?'객실에서 낮잠을 자기로 했어요':'객실에서 잠시 쉬기로 했어요'):s.act==='library'?'라이브러리에서 책과 음악을 즐기기로 했어요':`${action}${object} 하기로 했어요`;
 let choose=s.act==='lunch_skip'?'점심은 건너뛰기로 했어요':skipBreakfast?'아침 식사는 건너뛰고 객실에서 쉬기로 했어요':venue==='룸서비스'&&meal?`객실에서 룸서비스로 ${meal}을 해결하기로 했어요`:venue&&!meal&&s.consume?`${venue}에서 주문하기로 했어요`:venue&&meal?`${venue}에서 ${meal}을 먹기로 했어요`:activity;
 // Narration phase is taken from the recorded scene/order, never a new plan.
 const executed=['EXECUTED','INFO_CHECK_NOT_ATTENDANCE'].includes(x.decision?.execution_status)||!!turn||!!s.basis?.decision;
 const confirmed=s.consume&&(x.charge?.sku_contract||s.basis?.menu_decision?.status==='SELECTED');
 const phase=s.decision_phase==='PLANNED'?'PLANNED':s.decision_phase==='ORDER_CONFIRMED'?'ORDER_CONFIRMED':executed||confirmed?'EXECUTED':'UNVERIFIED';
 if(venue&&meal&&s.act!=='lunch_skip'&&!skipBreakfast){
  const where=venue==='룸서비스'?'객실에서 룸서비스로':venue+'에서';
  if(phase==='PLANNED')choose=`${where} ${meal}을 먹는 쪽으로 생각하고 있어요`;
  else if(phase==='ORDER_CONFIRMED'&&clean(x.charge?.sku_contract?.label)&&!INTERNAL.test(x.charge.sku_contract.label)){
   const label=clean(x.charge.sku_contract.label),c=label.charCodeAt(label.length-1),obj=c>=0xac00&&c<=0xd7a3&&(c-0xac00)%28?'을':'를';choose=`${label}${obj} 주문했어요`;
  }else if(phase==='EXECUTED'){
   const form=Array.from(String(x.pid||'')+String(s.act||'')).reduce((n,c)=>n+c.charCodeAt(0),0)%3;
   choose=[`${where} ${meal}을 먹어요`,`${meal}은 ${where} 해결해요`,`${where} ${meal} 식사를 해요`][form];
  }
 }else if(venue&&s.consume&&phase==='EXECUTED')choose=`${venue}에서 주문을 마쳤어요`;
 if(!meal&&phase==='EXECUTED'){
  const present={theatre:'빛의 시어터를 관람해요',pool:'수영을 해요',sauna:'사우나를 이용해요',footbath:'족욕으로 쉬어요',night_footbath:'족욕으로 쉬어요',night_walk:'야경을 보며 걸어요',forest_walk:'숲길을 걸어요',garden_walk:'정원을 산책해요',room_nap:'객실에서 낮잠을 자요'};
  if(present[s.act])choose=present[s.act];
  if(/^[A-Z_]+:check$/.test(s.act||''))choose=activity.replace('확인하기로 했어요','확인해요');
 }
 if(!meal&&phase==='EXECUTED')choose=choose.replace('참여하기로 했어요','참여해요').replace('쉬기로 했어요','쉬어요').replace('즐기기로 했어요','즐겨요');
 const audit={version:VERSION,action_phase:phase,selected_id:x.selectedId||turn?.choice?.product_id||null,scene_action:s.act,source_packet:x.decision?.packet?.packet_sha256||null,source_kind:turn?'NATIVE_TURN_SCORE':x.decision?'M4_PACKET':'NOT_RECORDED',reason_kind:null,contributions:[],fact_ids:[],comparison_ids:[],review:false,not_a_but_for_causal_claim:true};
 const done=(sentences,kind)=>({sentences:sentences.filter(Boolean).slice(0,2),audit:{...audit,reason_kind:kind}});
 const rv=x.review,adopted=rv&&/ADOPTED/.test(rv.decided_by||rv.outcome||'');
 if(adopted){
  // Use only recorded review reasons; never borrow the former rule winner's traits.
  audit.review=true;audit.selected_id=rv.actual_candidate_id||rv.final||audit.selected_id;audit.source_kind='ADOPTED_REVIEW';
  const reasons=rv.reasons||rv.llm?.reasons||[],valid=reasons.filter(r=>r.text&&!(r.fact_ids||[]).some(id=>(rv.cited_fact_ids_not_in_profile||[]).includes(id)));
  const repeat=valid.find(r=>/반복|전날|어제|같은 (?:메뉴|업장)/.test(r.text));
  const old=VENUE[(x.rawCands||[]).find(r=>r.candidate_id===rv.rule_choice)?.service_contract?.venue_id]||Object.values(VENUE).find(v=>String(rv.rule_label||'').includes(v));
  const history=(x.mealHistory||[]).find(m=>old&&m.venue===old);
  if(repeat&&history){audit.fact_ids=repeat.fact_ids||[];return done([`이미 ${old}에서 식사한 점을 다시 고려해, 이번에는 ${choose}.`],'ADOPTED_REVIEW_WITH_RECORDED_MEAL');}
  const cost=valid.find(r=>/비용을 낮추|비용.*(?:고려|따지|비교)|가격.*(?:부담|망설)|비싸/.test(r.text));
  if(cost){audit.fact_ids=cost.fact_ids||[];audit.contributions=[{factor:'ADOPTED_REVIEW_COST_REASON',source:'STORED_ADOPTED_REVIEW'}];return done([`식사 비용과 이용할 구성을 다시 따져, 이번에는 ${choose}.`],'ADOPTED_REVIEW_COST');}
  const repeatOnly=repeat&&(rv.triggers||[]).some(t=>/REPEAT/.test(t));
  if(repeatOnly){audit.contributions=[{factor:'ADOPTED_REVIEW_REPEAT_REASON',source:'STORED_ADOPTED_REVIEW_NOT_INDEPENDENT_HISTORY_VERIFICATION'}];return done([`같은 음식을 반복할지도 다시 살펴본 뒤, 이번에는 ${choose}.`],'ADOPTED_REVIEW_REPEAT_CONSIDERATION');}
  return done([`가능한 선택지를 다시 검토해 ${choose}. 개별 변경 이유는 이 기록만으로는 더 자세히 확인하기 어려워요.`],'ADOPTED_REVIEW_REASON_UNAVAILABLE');
 }
 const duty={wait:'다음 일정으로 넘어가기 전 대기하는 구간이에요. 개인 선호를 새로 판단하는 장면은 아니에요.',idle:'다음 일정 전의 빈 시간이어서 잠시 머물러요.',arrive:'정해 둔 방문 일정에 맞춰 호텔에 도착했어요.',checkin:'이제 객실을 이용할 시간이라 체크인을 해요.',unpack:'숙박 일정을 시작하기 위해 객실에서 짐을 정리해요.',wake:'오늘 방문 일정을 시작할 시간이에요.',pack:'퇴실을 준비하려고 짐을 챙겨요.',checkout:'숙박 일정이 끝나 체크아웃을 해요.',leave:'예정된 방문을 마쳐 돌아갈 시간이에요.',sleep:'하루 일정을 마쳐 객실에서 잠을 청해요.'};
 if(duty[s.act])return done([duty[s.act]],'SCHEDULE');
 if(!row)return done([`${action} 장면이에요. 이 장면에는 개별 선택 이유를 확인할 판단 기록이 남아 있지 않아요.`],'REASON_UNAVAILABLE');
 const alternatives=(x.rawCands||[]).filter(r=>r.world_allowed!==false&&r.candidate_id!==row.candidate_id&&(!venue||r.service_contract?.venue_id!==row.service_contract?.venue_id)).sort((a,b)=>(b.final_with_lookahead??b.final_score??0)-(a.final_with_lookahead??a.final_score??0));
 const alt=alternatives[0],base=row.score_contribution?.terms;
 const deltas=r=>new Map((r?.score_contribution?.terms||[]).map(t=>[t.factor,t.evidence_delta]));
 const theirs=deltas(alt),ours=deltas(row),con=[];
 for(const t of terms){
  if(!(t.fact_ids||[]).length||!PERSONAL[t.facet])continue;
  // A profile+offer baseline is not personal evidence. Measured ablation is preferred.
  const value=ours.has(t.factor)?ours.get(t.factor):t.kind==='profile'?t.value:0;
  if(!(value>1e-6))continue;
  con.push({facet:t.facet,factor:t.factor,value,contrast:base&&alt?.score_contribution?value-(theirs.get(t.factor)||0):null,fact_ids:t.fact_ids,method:ours.has(t.factor)?'SAME_STATE_EVIDENCE_DELTA':'RECORDED_PROFILE_TERM'});
 }
 const obs=cf.food_observation||{};
 for(const [key,m] of Object.entries(row.profile_feature_marginals||{})){
  const facet=key.split('.').pop(),ids=obs.indirect_fact_ids?.[facet]||[];
  if(m.weight_delta_at_fixed_state>1e-6&&ids.length&&PERSONAL[facet])con.push({facet,factor:key,value:m.weight_delta_at_fixed_state,contrast:null,fact_ids:ids,method:'SINGLE_FEATURE_ABLATION_NOT_ADDITIVE'});
 }
 // Prefer a distinguishing measured contribution, not the largest mixed common term.
 con.sort((a,b)=>(b.contrast>1e-6)-(a.contrast>1e-6)||(b.contrast||0)-(a.contrast||0)||b.value-a.value);
 const negative=alternatives.map(r=>({row:r,term:(r.terms||[]).find(t=>t.value<0&&(t.fact_ids||[]).length&&/명시적 재방문 거부/.test(t.factor||''))})).find(v=>v.term&&(VENUE[v.row.service_contract?.venue_id]||VENUE[v.row.candidate_id])&&(v.row.final_with_lookahead??v.row.final_score)-v.term.value>(row.final_with_lookahead??row.final_score));
 if(negative&&!x.sampling){
  const v=VENUE[negative.row.service_contract?.venue_id]||VENUE[negative.row.candidate_id],t=negative.term;
  audit.contributions=[{factor:t.factor,value:t.value,fact_ids:t.fact_ids,candidate_id:negative.row.candidate_id,role:'REJECTED_ALTERNATIVE_NEGATIVE_EVIDENCE'}];audit.fact_ids=t.fact_ids;audit.comparison_ids=[negative.row.candidate_id];
  return done([`${v}에 다시 가고 싶지 않다는 이전 평가도 고려해, 이번에는 ${choose}.`],'EXPLICIT_NEGATIVE_ALTERNATIVE');
 }
 const p=con[0];
 if(p){
  audit.contributions=[p];audit.fact_ids=p.fact_ids;if(p.contrast>1e-6&&alt)audit.comparison_ids=[alt.candidate_id];
  const sampled=!!x.sampling;
  const intro=meal&&!skipBreakfast&&s.act!=='lunch_skip'?`${meal}을 먹을 때가 됐고, `:'';
  const reason=PERSONAL[p.facet];
  const cause={space:'전망과 공간을 즐기는 경험을 중요하게 여겨',food:'음식 경험을 중요하게 여겨',routine:'전에 이용해 본 곳이라는 점을 고려해',value_check:'비용을 꼼꼼히 따져',rest_need:'쉬는 시간을 중요하게 여겨'}[p.facet]||`${reason}을 고려해`;
  const first=sampled?`${reason}도 고려한 선택지 중, 이번에는 ${choose}.`:`${intro}${cause} ${choose}.`;
  const extra=con.find(t=>t.facet==='routine'&&p.facet!=='routine'&&t.value>1e-6);
  if(extra){audit.contributions.push(extra);audit.fact_ids=[...new Set([...audit.fact_ids,...extra.fact_ids])];}
  return done([first,extra?'전에 이용해 본 곳이라는 점도 이번 선택에 보탬이 됐어요.':null],sampled?'PERSONAL_CONTRIBUTION_TO_SAMPLING':'PERSONAL_SCORE_CONTRIBUTION');
 }
 // No generic research text unless an applied, pre-selection term is recorded.
 const g=row.general_food_evidence;
 if(g?.applied&&g.delta&&g.stage==='BEFORE_SELECTION'&&g.prior_event_ids?.length){audit.contributions=[{factor:'general_food_evidence',value:g.delta,source_ids:g.source_ids}];return done([`앞서 먹은 식사와 겹치는지도 함께 고려해, 이번에는 ${choose}.`],'APPLIED_GENERAL_EVIDENCE');}
 const positive=re=>terms.some(t=>re.test(t.factor||'')&&t.value>0);
 if(meal&&venue==='룸서비스'&&positive(/휴식.*회복/)&&Number(cf.fatigue_proxy)>=.75)return done([`앞선 활동으로 피로가 쌓였고 ${meal}도 먹을 때라, ${choose}.`],'RECORDED_ROOM_MEAL_RECOVERY');
 if(meal&&positive(/끼니|식사 필요/))return done([`${meal} 시간이 되어 끼니를 채우는 쪽에 무게를 두고, ${choose}.`],'COMMON_MEAL_AND_ELIGIBILITY');
 if(rest&&positive(/휴식|회복/)&&Number(cf.fatigue_proxy)>=.75)return done([`앞선 활동으로 쉴 필요가 커져, ${choose}.`],'RECORDED_RECOVERY_SCORE');
 if(x.sampling)return done([`뚜렷한 개인 선호가 이 선택을 이끌었다는 기록은 없어요. 가능한 선택지 중 이번에는 ${choose}.`],'ELIGIBLE_WEIGHTED_SELECTION');
 if(row.world_allowed!==false)return done([`이번 선택의 개인적인 이유는 기록에서 확인되지 않아요. ${choose}.`],'COMMON_RULES_NO_PERSONAL_CAUSE');
 return done(['최종 행동의 자세한 선택 이유는 남아 있는 기록만으로 확인하기 어려워요.'],'REASON_UNAVAILABLE');
}
const API={version:VERSION,compose};if(typeof module!=='undefined'&&module.exports)module.exports=API;root.HLChoiceReason=API;
})(typeof window!=='undefined'?window:globalThis);
