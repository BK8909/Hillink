// Recorded pre-choice decisions only. Scores are never reconstructed as LLM reasons.
(function(root){
'use strict';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>Number.isFinite(n)?n.toLocaleString('ko-KR')+'원':'금액 미기록';
const hm=n=>Number.isFinite(n)?`${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`:'시각 미기록';
const list=xs=>xs?.length?`<ul>${xs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
// Policy versions are exact: a stored V16 answer is never relabeled as a V17 (day-end reviewed) judgment.
const VERSION={LLM_AUTONOMOUS_CUSTOMER_V19LS_HP1B:'연구 기준(V19-LS HP1b) · 외부 배달 대안 · 통계 유무만 다른 통제 비교 · 합성값은 가상 호텔 조건',LLM_AUTONOMOUS_CUSTOMER_V19LS_MEM1:'연구 기준(V19-LS MEM1) · 앞선 날 실제 행동 기억 전달',LLM_AUTONOMOUS_CUSTOMER_V19LS_HP1:'연구 기준(V19-LS HP1) · 외부 배달 저녁 대안 · 호텔 배달 통계 일반 참고',LLM_AUTONOMOUS_CUSTOMER_V19LS_P2:'연구 기준(V19-LS P2) · 일부 인원 조식 후보 · 식사량 1회 재검토',LLM_AUTONOMOUS_CUSTOMER_V16:'과거 판단 기준(V16) · 조기 종료 검증 이전',LLM_AUTONOMOUS_CUSTOMER_V17:'이전 판단 기준(V17) · 조기 종료 검증 적용',LLM_AUTONOMOUS_CUSTOMER_V18:'실험 기준(V18) · 규칙 선별 후 LLM 선택',LLM_AUTONOMOUS_CUSTOMER_V18B:'실험 기준(V18-B) · 후보 관련 근거만',LLM_AUTONOMOUS_CUSTOMER_V18BM:'실험 기준(V18-C) · B 입력 · reasoning medium',LLM_AUTONOMOUS_CUSTOMER_V18BD:'실험 기준(V18-D) · B 입력 · 최소 출력',LLM_AUTONOMOUS_CUSTOMER_V19LS:'현재 판단 기준(V19-LS) · 근거 성격 표시 · 하루 종료 재검토 · 선택 진단 기록'};
const version=p=>VERSION[p]||(p?String(p):'판단 기준 미기록');
function record(scene){return scene?.basis?.autonomous_decision||null;}
// Join only the immutable decision in this customer's same stored plan. A scene
// contains the pre-execution snapshot; completion belongs to the decision log.
function resolve(scene,plan){
 if(scene&&plan?.recorded_review)scene={...scene,recorded_review:plan.recorded_review};
 const d=record(scene);if(!d?.input_sha256)return scene;
 const matches=(plan?.autonomous_decisions||[]).filter(x=>x.input_sha256===d.input_sha256&&
  ['customer_id','date','minute','policy','contract_sha256'].every(k=>x[k]===d[k]));
 if(matches.length!==1||JSON.stringify(matches[0].selected_plan)!==JSON.stringify(d.selected_plan))return scene;
 const executed=matches[0];
 return {...scene,basis:{...scene.basis,autonomous_decision:{...d,execution_state:executed.execution_state,
  state_after:executed.state_after,execution_link:'SAME_RUN_CUSTOMER_DECISION_ID'}}};
}
function view(scene){
 const d=record(scene);if(!d)return null;
 const executions=(d.attempts||[]).map(a=>a.provider?.execution).filter(Boolean);
 const mode=d.execution_state==='EXECUTION_HOLD'?'실행 보류 · 유효한 자율 계획 미확정':d.execution_state==='RULE_FALLBACK'?'규칙 폴백':executions.includes('LIVE_RESPONSES')?'LIVE LLM · 실제 API 판단':executions.includes('CACHE_REPLAY')?'캐시 재생 · 저장된 LLM 판단':'실행 출처 확인 필요';
 const displayMode=scene.recorded_review?'저장 방문 재생 · 원 실행 출처: '+mode:mode;
 return {decision:d,mode:displayMode,summary:d.selected_plan?.decision_summary||d.fallback_reason||'최종 판단 미기록',
  fact_ids:[...new Set([...(d.selected_plan?.supporting_fact_ids||[]),...(d.selected_plan?.counterevidence_fact_ids||[])])],
  alternatives:d.attempts?.at(-1)?.answer?.plans||[],
  choice_scope:d.candidate_count===1?'유효 후보 1개 · 개인화 성공의 근거로 평가하지 않음':`운영 계약을 통과한 후보 ${d.candidate_count??'미기록'}개`};
}
function contextHTML(d){
 const c=d.input_context;if(!c)return '<p>이 실행에는 당시 입력한 Fact 요약·방문 맥락의 화면용 기록이 없습니다. 아래 판단 문장과 인용 ID는 보존된 LLM 응답이며, 현재 프로필로 당시 입력을 재구성하지 않습니다.</p>';
 const v=c.visit||{},s=c.state||{},purpose={anniversary:'기념일',dining:'식사 경험',rest:'휴식',family_time:'가족 시간',event:'행사',business:'출장',wellness:'웰니스'};
 const purposeText=v.purpose?.status==='OPERATOR_SCENARIO_NOT_REVIEW_FACT'?`${purpose[v.purpose.value]||v.purpose.value} · 운영자 시나리오`:'이번 방문 목적 미확인';
 const party=v.party,children=party?.children||[];
 const eligibility=v.contract_party_assumption?.source==='LEGACY_ALL_ADULT_PRICE_REFERENCE'?'<p>전원 성인 요금은 계산 참고 가정입니다. 실제 동행 구성·연령·운영 이용 자격은 확인이 필요합니다 (REVIEW_REQUIRED).</p>':'';
 const partyText=party?`성인 ${party.adult_count}명${children.length?' · 어린이 '+children.map(x=>x.age_months==null?'연령 미확인':x.age_months+'개월').join(', '):''} · 운영자 시나리오`:`${v.party_size??'미확인'}인 · 관계·연령 미확인`;
 const prior=(c.meal_experiences||[]).at(-1),order=prior?.order?.map(x=>`${x.label||x.sku_id} × ${x.quantity}`).join(' + ');
 const fs=s.fatigue_scale,tr=s.today_remaining,sb=d.state_before||{};
 // The recorded context keeps only some fields (e.g. a breakfast record has the fatigue level and percent but no
 // value / rest limit and an empty today_remaining): show what was recorded, never blanks.
 const has=v=>v!==undefined&&v!==null&&v!=='';
 const fatigueText=fs&&[has(fs.value)?`피로 ${esc(fs.value)}`:'',has(fs.ratio_percent)?(has(fs.rest_limit)?`휴식 한도 ${esc(fs.rest_limit)}의 ${esc(fs.ratio_percent)}%`:`휴식 한도의 ${esc(fs.ratio_percent)}%`)+(fs.level?` (${esc(fs.level)})`:''):fs.level?`피로 ${esc(fs.level)}`:''].filter(Boolean).join(' · ');
 const todayText=tr&&[has(tr.dinner_resolved)?`저녁 ${tr.dinner_resolved?'해결':'미해결'}`:'',has(tr.open_meal_options)?`남은 식사 후보 ${esc(tr.open_meal_options)}개`:'',has(tr.open_activity_options)?`활동 후보 ${esc(tr.open_activity_options)}개`:'',has(tr.day_end)?`방문 종료 ${esc(tr.day_end)}`:''].filter(Boolean).join(' · ');
 const stateLine=fs&&(fatigueText||todayText)?`<p><b>판단 시점 상태</b> ${[fatigueText,todayText].filter(Boolean).join(' · ')} <small>엔진 상태 모델 · 실측 아님</small></p>`
  :Number.isFinite(sb.fatigue)?`<p><b>판단 시점 상태</b> 피로 ${Number(sb.fatigue).toFixed(2)} · 허기 참고 ${esc(sb.hunger)} <small>V16 기록 · 당시 모델에는 휴식 한도 척도가 전달되지 않음</small></p>`:'';
 const activities=(c.activity_experiences||[]).filter(x=>x.action!=='move');
 const activityHTML=activities.length?`<details><summary>이번 방문에서 이미 실행한 활동 · ${activities.length}건</summary><p>전날부터 이어진 가상 실행 기록입니다. 이용했다는 사실만으로 만족·선호를 확인한 것은 아닙니다.</p><ul>${activities.map(x=>`<li>${esc(x.date)} ${esc(x.start_time||hm(x.start))}–${esc(x.end_time||hm(x.end))} · ${esc(x.label||x.action)}</li>`).join('')}</ul></details>`:'';
 const citations=new Set([...(d.selected_plan?.supporting_fact_ids||[]),...(d.selected_plan?.counterevidence_fact_ids||[])]),facts=(c.facts||[]).filter(f=>f.fact_ids.some(id=>citations.has(id)));
 return `<p><b>${esc(purposeText)}</b> · ${esc(partyText)}</p>${eligibility}<p>${esc(v.date||'날짜 미기록')} ${esc(s.time||hm(d.minute))} · 방문 종료 ${esc(s.day_end||'미기록')}${v.checked_out?' · 체크아웃 이후':''}</p>${stateLine}${prior?`<p><b>이전 식사</b> ${esc(order||prior.venue)} · 종료 후 ${prior.minutes_since_end==null?'경과 시간 미기록':esc(prior.minutes_since_end)+'분'}. 주문 기록이며 실제 섭취량은 미관측입니다.</p>`:'<p>연결된 이전 가상 식사 기록 없음 · 도착 전 식사를 하지 않았다는 뜻은 아닙니다.</p>'}${activityHTML}${v.breakfast?`<p>조식 권리: 포함 성인 ${esc(v.breakfast.covered_adults??'미확인')}명 · ${v.breakfast.whole_party_covered?'현재 동행 전체 포함':'동행 전체 포함 여부·추가 요금 계약 확인'}</p>`:''}${facts.length?`<ul>${facts.map(f=>`<li>${f.fact_ids.filter(id=>citations.has(id)).map(id=>`<button class="cf-link" data-bh-fact="${esc(id)}">${esc(id)}</button>`).join(' · ')} — ${esc(f.summary)} <small>(${f.source_scope==='other'?'다른 장소의 경험 · ':''}원문 의미 검수 미완료${f.independent_observation_count==null?' · 독립 반복 횟수 미확정':''})</small></li>`).join('')}</ul>`:'<p>이 계획에 직접 연결한 개인 Fact 요약이 없습니다. 상황 판단과 개인 선호를 구분합니다.</p>'}`;
}
// Model answers may name a candidate by its internal action id (e.g. "end_day_in_room: ..."). Shown text uses the
// candidate's own label from the same input; the stored answer is not changed.
function actionLabels(d){const acts=((d&&d.input_context&&d.input_context.actions)||[]).filter(a=>a.action_id&&a.label),byId=new Map(acts.map(a=>[a.action_id,a.label]));if(!acts.length)return text=>String(text??'');
 // whole ids only, longest first (room_rest must not match inside room_rest_long)
 const ids=[...byId.keys()].sort((x,y)=>y.length-x.length).map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')),re=new RegExp('(?<![A-Za-z0-9_:])('+ids.join('|')+')(?![A-Za-z0-9_])','g');
 return text=>String(text??'').replace(re,m=>byId.get(m));}
function reviewHTML(scene,d){
 const r=scene.recorded_review,review=r?.review?.review,findings=review?.findings||[];
 return `<section data-agent-review><p>${r?'저장된 V16 방문 재생 · 현재 실호출 0회 · 원 실행 모델 '+esc(r.model):'현재 판단 기록'}</p><p>원문 의미·행동 품질: 사람 승인 미완료. 유효한 Fact ID만으로 근거의 의미나 누락 없는 연결을 승인하지 않습니다.</p>${review?`<p>독립 모델 평가: ${esc(review.review_status)} · 사람 승인과 별도</p>${findings.map(f=>`<details><summary>${esc(f.dimension)} · ${esc(f.severity)}</summary><p>${esc(f.observation)}</p><p>원 판단 참조: ${esc((f.decision_refs||[]).join(', '))}</p><p>${esc(f.follow_up)}</p></details>`).join('')}`:''}<p>판단 경계: ${esc(d.date)} ${hm(d.minute)} · ${esc(actionLabels(d)(d.selected_plan?.action_id))}. 연속 휴식이 합쳐진 장면과 개별 판단의 일대일 대응은 별도 검수 대상입니다.</p>${scene.basis?.continued_autonomous_decisions?.length?`<p>이 장면 안에 이어진 판단 ${scene.basis.continued_autonomous_decisions.length}건. 각 판단은 저장 방문의 원 판단 목록에서 확인합니다.</p>`:''}</section>`;
}
// V19LS marks each breakfast line as covered by the room contract or paid extra (price_basis). Shown as recorded;
// the engine total is not recomputed here.
const BF_INCLUDED='객실 조식 포함(추가 비용 없음)',BF_PAID='추가 결제';
function inclusionHTML(action,contracts,party){
 const qty=list=>list.reduce((n,c)=>n+(Number(c.quantity)||0),0),inc=contracts.filter(c=>c.price_basis===BF_INCLUDED),paid=contracts.filter(c=>c.price_basis===BF_PAID);
 if(!inc.length)return '';
 const diners=qty(inc)+qty(paid),absent=Number.isInteger(party)&&party>diners?party-diners:0;
 return `<p data-agent-breakfast-inclusion><b>조식 포함 구분</b> 객실 조식 포함 ${qty(inc)}명 · 추가 비용 없음${paid.length?` · 추가 결제 ${qty(paid)}명 · 추가 비용 ${money(action.order_total_krw)}`:''}${absent?` · ${absent}명은 조식을 먹지 않음`:paid.length?'':' · 동행 전원 포함'} <small>객실 계약 기준 · 엔진 금액 그대로</small></p>`;
}
function contractHTML(scene,d,action){
 const p=d.selected_plan||{},contracts=action.item_contracts||[],assessment=p.meal_assessment;
 return `<section data-agent-contract>${contracts.length?`<h4>선택 전 상품·이용권 계약</h4>${inclusionHTML(action,contracts,d.input_context?.visit?.party_size)}${contracts.map(c=>`<p>${esc(c.label||c.sku_id)} × ${esc(c.quantity)} · ${c.semantics==='PERSON_ACCESS_ENTITLEMENT'?'인원별 이용·과금 권리 · 개별 음식 주문이나 아동 전용 음식이 아님':esc(c.semantics||'음식 구성 계약 확인')}${c.price_basis?` · ${esc(c.price_basis)}`:''}</p>`).join('')}<p>당시 후보 금액 ${money(action.order_total_krw)} · 원 선택 금액 ${money(p.order_total_krw)}</p>`:''}${assessment?(String(p.output_contract||'').startsWith('V18D')?`<p>식사 구분: ${esc(assessment.kind)} <small>엔진 기본 가정 · 모델 진술 아님</small></p>`:`<p>모델의 식사 의도: ${esc(assessment.kind)} · ${esc(assessment.intake_assumption)}</p>`):''}<p>회계·서비스 시간대: ${esc(scene.meal||'미기록')} · 식사 의도와 별도. ${esc(p.meal_period_basis||d.input_context?.state?.meal_context?.meal_period_basis||d.input_context?.state?.meal_period_basis||'시간대는 기존 운영 시각 계약')}</p>${action.wait?`<p>판단 전 대기 계약: ${esc(JSON.stringify(action.wait))}</p>`:''}${action.consequences?`<p>당시 실행 결과 조건: ${esc(action.consequences)}</p>`:''}</section>`;
}
function panel(scene,options={}){
 const v=view(scene);if(!v)return options.expected?'<section class="frp-section" data-agent-decision-missing><h3>이 장면의 LLM 판단 기록 없음</h3><p>도착·이동·체크아웃 같은 실행 절차이거나 판단 기록이 누락된 장면입니다. 규칙 점수를 LLM 선택 이유로 표시하지 않습니다.</p></section>':'';
 const d=v.decision,p=d.selected_plan||{},c=d.input_context||{},actions=c.actions||[],products=c.products||[];
 const name=id=>actions.find(a=>a.action_id===id)?.label||id;
 // Breakfast input may carry fixed SKU IDs without a menu list. Labels may
 // come from this scene's immutable executed contract, never today's catalog.
 const executedProducts=scene.basis?.charge?.sku_contract?.components||[];
 const items=plan=>(plan.items||[]).map(i=>`${actions.find(a=>a.action_id===plan.action_id)?.item_contracts?.find(x=>x.sku_id===i.sku_id)?.label||products.find(x=>x.sku_id===i.sku_id)?.label||executedProducts.find(x=>x.sku_id===i.sku_id)?.label||i.sku_id} × ${i.quantity}`).join(' + ');
 const alternatives=v.alternatives.filter((x,i)=>i!==d.attempts?.at(-1)?.answer?.selected_index);
 const rejections=(d.attempts||[]).filter(a=>a.validation_rejection).map(a=>a.validation_rejection);
 const action=actions.find(a=>a.action_id===p.action_id)||{},timing=action.schedule;
 const timingHTML=timing?`<p><b>엔진이 제공한 실행 일정</b> 판단 ${esc(timing.decision_time)} · 출발 ${esc(timing.departure_time)} · 최종 이동 출발 ${esc(timing.final_leg_departure_time)} · 도착 ${esc(timing.arrival_time)} · 이용 ${esc(timing.start_time)}–${esc(timing.end_time)} · 이동 ${esc(timing.travel_minutes)}분 · 대기 ${esc(timing.wait_minutes)}분 <small>운영 모델 계산 · 실제 예약 확정 아님</small></p>`:'';
 const FAIL={MALFORMED_OR_INCOMPLETE_RESPONSE:'모델 응답 형식 오류 · 한 번 다시 요청한 뒤에도 실패',RATE_LIMITED:'호출 한도 초과(429) · 자동으로 다시 보내지 않음',PROVIDER_SERVER_ERROR:'모델 제공자 서버 오류',DELIVERY_UNCERTAIN:'전송 여부 불확실(시간 초과·연결 끊김) · 중복 호출을 막기 위해 다시 보내지 않음',BUDGET_OR_CALL_LIMIT:'비용·호출 상한 도달',NOT_AUTHORIZED:'실시간 호출 미승인 또는 키 없음',REPLAY_MISMATCH:'저장 응답과 입력이 일치하지 않음',PROVIDER_ERROR:'호출 실패'};
 const failure=d.failure_class?`<p data-agent-failure>판단 보류 원인: ${esc(FAIL[d.failure_class]||d.failure_class)} · 규칙 결과로 대체하지 않았습니다.</p>`:(d.hold_reason==='REPLAN_VALIDATION_EXHAUSTED'?'<p data-agent-failure>판단 보류 원인: 운영 검증 실패(재계획 후에도) · 규칙 결과로 대체하지 않았습니다.</p>':'');
 const DIAG={NEGATIVE_RECORD_ON_SELECTED_UNEXPLAINED:'부정·재방문 거부 기록이 있는 곳을 현재 조건 설명 없이 선택',NEGATIVE_RECORD_ON_SELECTED_EXPLAINED:'부정 기록이 있는 곳을 현재 조건으로 설명하고 선택',MIXED_RECORD_ONE_SIDED:'혼합 평가(좋은 점·아쉬운 점)를 한쪽만 이유로 사용',QUANTITY_ABOVE_PARTY_DESPITE_LEFTOVER:'과거에 음식을 남긴 기록이 있는데 인원보다 많은 양을 선택',REPEATED_WAIT_AFTER_SIGNAL:'같은 이유의 대기를 반복',CITED_NOT_SENT:'보내지 않은 근거를 인용',QUANTITY_AT_OR_BELOW_PARTY_DESPITE_SHORTFALL_RECORD:'과거 양 부족 기록이 있는데 인원과 같거나 적은 양을 선택',QUANTITY_BELOW_PARTY:'일반 환산 기준으로 인원보다 적은 양을 선택',COUNTEREVIDENCE_FOR_UNNAMED_ALTERNATIVE:'다른 후보에 관한 반대 근거를 인용했지만 이유에서 그 후보를 다루지 않음'};
 const DAYEND={STRUCTURED_ALTERNATIVE:'비교한 남은 후보를 대안 항목에 명시',ID:'남은 후보를 이름(ID)으로 비교',LABEL:'남은 후보를 이름으로 비교',DISTINCTIVE_WORD_IN_COMPARISON:'남은 후보를 비교 문장으로 언급',OTHER_RULE:'기존 종료 기준(동행 아동 취침·포만 근거)'};
 const mq=d.meal_quantity_review?.final,mealReview=mq?`<p data-agent-meal-review>식사량 재검토: 과거 양 부족 기록과 맞지 않는 첫 선택을 한 번 돌려보냈고, 재판단에서 일반 환산 ${esc(mq.equivalents??'미확인')}인분(${esc(mq.party??'?')}명)을 선택했습니다${(mq.cited||[]).length?' · 인용 '+esc(mq.cited.join(', ')):''}. 더 많이 주문하라고 강제하지 않습니다.</p>`:'';
 const dayend=d.day_end_match?`<p data-agent-dayend>하루 종료 재검토: 첫 종료 선택은 남은 후보와 비교하도록 한 번 돌려보냈고, 재계획에서 ${esc(DAYEND[d.day_end_match.accepted_by]||d.day_end_match.accepted_by)}해 종료를 실행했습니다.</p>`:'';
 const diag=(d.selection_diagnostics||[]).length?`<p data-agent-diagnostics><b>선택 진단(검수용 · 실행을 막지 않음)</b></p>${list(d.selection_diagnostics.map(x=>DIAG[x.code]||x.code))}`:(d.stability_policy?'<p data-agent-diagnostics>선택 진단: 기록된 충돌 없음</p>':'');
 const validation=d.execution_state==='EXECUTED'?'등록 후보·시간·주문 계약 검증을 통과한 계획으로 실행했습니다. 고객 선호나 실제 효과가 입증됐다는 뜻은 아닙니다.':d.execution_state==='VALIDATED'?'운영 계약 검증 통과 · 실행 완료는 아직 확인되지 않았습니다.':d.execution_state==='RULE_FALLBACK'?'LLM 계획을 실행하지 못해 규칙 정책으로 폴백했습니다.':'유효한 최종 실행을 확인하지 못했습니다.';
 const breakfast=d.breakfast_outcome?.startsWith('CONTRACT_UNAVAILABLE')?'조식 이용 조건을 충족한 음식 후보가 없어 보류했습니다. 조식 비선호·절약 성향으로 해석하지 않습니다.':d.breakfast_outcome?.startsWith('VOLUNTARY_NONUSE')?'이용 가능한 조식 후보 중 이번에는 미이용을 선택했습니다. 고정적인 조식 비선호로 해석하지 않습니다.':'';
 return `<section class="frp-section" data-agent-decision><h3>선택 전 LLM 판단·운영 검증</h3><div class="frp-chips"><span>${esc(v.mode)}</span>${typeof HLVisitExecution!=='undefined'&&HLVisitExecution.isImproved(d.policy)?'<span>개선형 판단 기준</span>':`<span>${esc(d.policy)}</span><span>${esc(version(d.policy))}</span>`}</div><p>${esc(v.choice_scope)}</p>${reviewHTML(scene,d)}<h4>1. 고객 근거와 당시 방문 상황</h4>${contextHTML(d)}<h4>2. LLM이 선택한 이유</h4><p><strong>${esc(v.summary)}</strong></p>${dayend}${mealReview}${p.tradeoff_note?`<p data-agent-tradeoff><b>상충 근거 대비 판단</b> ${esc(p.tradeoff_note)}</p>`:''}${(()=>{const dflt=String(p.output_contract||'').startsWith('V18D'),tag=dflt?' <small>엔진 기본 가정 · 모델 진술 아님</small>':'';
 const need=p.current_need_assessment?(dflt?`<p>현재 식사 필요 상태: ${esc(p.current_need_assessment.state)} <small>모델은 상태만 답함 · 이유는 요청하지 않음</small></p>`:`<p>현재 식사·휴식 필요 판단: ${esc(p.current_need_assessment.reason)} <small>모델 판단 · 실측 상태 아님</small></p>`):'';
 return need+(items(p)?`<p><b>계획한 주문</b> ${esc(items(p))} · ${money(p.order_total_krw)}</p>`:'')+(p.sharing_plan?`<p>나눠 먹는 방식: ${esc(p.sharing_plan)}${tag}</p>`:'')+(p.meal_assessment?`<p>식사량 판단: ${esc(p.meal_assessment.quantity_reason)} · 실제 섭취는 미관측입니다.${tag}</p>`:'');})()}<p>${esc(p.schedule_impact||'이후 일정 영향 미기록')}</p>${contractHTML(scene,d,action)}<h4>3. 비교한 대안</h4>${alternatives.length?alternatives.map(x=>`<details><summary>${esc(name(x.action_id))}${items(x)?' · '+esc(items(x)):''}</summary><p>${esc(x.decision_summary)}</p><p>${esc(x.schedule_impact||'')}</p></details>`).join(''):'<p>응답에 기록된 다른 계획이 없습니다. 대안 비교를 수행했다고 해석하지 않습니다.</p>'}${p.why_not_other_plans?`<p><b>선택과 비교한 판단</b> ${esc(actionLabels(d)(p.why_not_other_plans))}</p>`:''}<h4>4. 운영 규칙의 검증과 실행</h4><p>${validation}</p>${failure}${diag}${timingHTML}${breakfast?`<p>${breakfast}</p>`:''}${rejections.length?`<p>재계획 요청 ${rejections.length}회</p>${list(rejections)}`:'<p>기록된 재계획 거절 없음</p>'}${d.day_end_review?`<p><b>조기 종료 검토</b> ${d.day_end_review.first_choice_rejected?'첫 선택은 거절됐고 재계획에서 남은 후보를 비교한 뒤 종료를 재확인':'첫 선택에서 검토 조건을 충족해 통과'} · 피로 ${esc(d.day_end_review.fatigue?.ratio_percent)}% (${esc(d.day_end_review.fatigue?.level)})</p>`:''}<p>${d.price_score_rerank===false?'최종 LLM 의도를 기존 가격 점수로 재정렬하지 않았습니다.':'가격 점수 재정렬 여부 미기록'}</p>${list(p.assumptions)}<details><summary>반례·다음 의도·후보 제외 및 기술 기록</summary><p>반례 Fact: ${esc((p.counterevidence_fact_ids||[]).join(', ')||'직접 인용 없음')}</p>${list(p.pending_intentions)}<p>다음 의도는 아직 실행되지 않은 계획입니다. Fact 의미 적합성과 행동 품질은 별도 검수 대상입니다.</p><pre>${esc(JSON.stringify({excluded:d.excluded||[],state_before:d.state_before,state_after:d.state_after,input_sha256:d.input_sha256,implementation_sha256:d.implementation_sha256},null,2))}</pre></details></section>`;
}
// Evidence page in the rule page's layout (최종 선택 → 개인 후기 → 당시 상황 → 비교 → 실행·소비). Reader text only:
// no JSON, hashes, internal ids or policy codes; panel() keeps the full record for tests/review tools.
function story(scene){
 const v=view(scene);if(!v)return null;
 const d=v.decision,p=d.selected_plan||{},c=d.input_context||{},actions=c.actions||[],products=c.products||[],lab=actionLabels(d);
 const code=x=>/^[A-Z0-9_:#.\-]{6,}$/.test(String(x||''));   // never show bare internal codes
 const name=id=>{const l=actions.find(a=>a.action_id===id)?.label;if(l&&!/^[A-Z0-9_:]+$/.test(l))return l;const v=String(l||id||'').replace(/^meal:/,'');const n=typeof root.agPlaceName==='function'?root.agPlaceName(v):'';return n&&!/^[A-Z0-9_:]+$/.test(n)?n:(code(id)||/[a-z]_[a-z]/.test(String(id))?'기록된 다른 후보':lab(id));};
 const executedProducts=scene.basis?.charge?.sku_contract?.components||[];
 const items=plan=>(plan.items||[]).map(i=>`${actions.find(a=>a.action_id===plan.action_id)?.item_contracts?.find(x=>x.sku_id===i.sku_id)?.label||products.find(x=>x.sku_id===i.sku_id)?.label||executedProducts.find(x=>x.sku_id===i.sku_id)?.label||String(actions.find(a=>a.action_id===plan.action_id)?.label||'상품').split(' · ')[0]} × ${i.quantity}`).join(' + ');
 const last=d.attempts?.at(-1),plans=last?.answer?.plans||[],selIdx=last?.answer?.selected_index;
 const alternatives=plans.filter((x,i)=>i!==selIdx);
 const executions=(d.attempts||[]).map(a=>a.provider?.execution);
 const origin=d.execution_state==='EXECUTION_HOLD'?'판단 보류':scene.recorded_review||executions.includes('CACHE_REPLAY')&&!executions.includes('LIVE_RESPONSES')?'저장된 AI 판단 재생':executions.includes('LIVE_RESPONSES')?'실시간 AI 판단':'출처 확인 필요';
 const policy=/_INT4$/.test(String(d.policy||''))?'개선형':(version(d.policy).match(/\(([^)]+)\)/)?.[1]||'기록된 기준');
 const row=(k,val,tag)=>`<div><dt>${esc(k)}${tag?` <i class="ev-src ev-src-${tag[0]}">${esc(tag[1])}</i>`:''}</dt><dd>${esc(val)}</dd></div>`;
 const OBS=['obs','실행 기록'],EST=['est','엔진 추정'],OPS=['ops','운영자 설정'];
 // ② 개인 후기 — cited facts first (direct), the rest of the facts sent with this decision as reference
 const sup=new Set(p.supporting_fact_ids||[]),ctr=new Set(p.counterevidence_fact_ids||[]),cited=new Set([...sup,...ctr]);
 const all=c.facts||[],direct=all.filter(f=>f.fact_ids.some(id=>cited.has(id))),reference=all.filter(f=>!f.fact_ids.some(id=>cited.has(id)));
 const role=ids=>{const a=ids.some(id=>sup.has(id)),b=ids.some(id=>ctr.has(id));return a&&b?['mix','장단점 함께 고려']:b?['neg','반대 근거로 검토']:['pos','선택을 뒷받침'];};
 const factCard=(f,r)=>{const ids=f.fact_ids.filter(id=>!r||cited.has(id)),[k,t]=r?role(ids):['ref','참고로 전달'];return `<li class="ev-fact ev-fact-${k}"><span class="ev-fact-role">${t}</span><p>${esc(f.summary)}</p><small>${f.source_scope==='other'?'다른 장소의 경험':'워커힐 후기'}${ids.length?` · <button class="cf-link" data-bh-fact="${esc(ids.join(','))}">후기 원문 보기 ↗</button>`:''}</small></li>`;};
 const personal=(direct.length?`<ul class="ev-facts">${direct.map(f=>factCard(f,true)).join('')}</ul>`:cited.size?`<p>이 판단이 인용한 후기 ${cited.size}건 · <button class="cf-link" data-bh-fact="${esc([...cited].join(','))}">후기 원문 보기 ↗</button></p>`:'<p class="ev-empty">이 판단은 개인 후기를 직접 인용하지 않았습니다. 지금의 상황(시각·허기·피로·남은 일정)에 따른 판단입니다.</p>')
  +(reference.length?`<details class="ev-ref"><summary>판단에 함께 전달된 다른 후기 ${reference.length}건</summary><ul class="ev-facts">${reference.map(f=>factCard(f,false)).join('')}</ul></details>`:'');
 // ③ 당시 상황
 const vi=c.visit||{},s=c.state||{},purpose={anniversary:'기념일',dining:'식사 경험',rest:'휴식',family_time:'가족 시간',event:'행사',business:'출장',wellness:'웰니스'};
 const party=vi.party,children=party?.children||[];
 const partyText=party?`성인 ${party.adult_count}명${children.length?' · 어린이 '+children.length+'명':''}`:`${vi.party_size??'미확인'}명`;
 const fs=s.fatigue_scale,tr=s.today_remaining,has=x=>x!==undefined&&x!==null&&x!=='';
 const fatigue=fs?[fs.level?`피로 ${fs.level}`:'',has(fs.ratio_percent)?`(휴식 한도의 ${fs.ratio_percent}%)`:''].filter(Boolean).join(' '):(Number.isFinite(d.state_before?.fatigue)?`피로 ${Number(d.state_before.fatigue).toFixed(2)}`:'');
 const SAT={FULL_LIKELY:'포만 가능성 높음',PARTIAL:'약간 허기',HUNGRY_LIKELY:'허기 가능성 높음'},sat=s.modeled_need?.engine_estimate?.modeled_satiety;
 const today=tr?[has(tr.dinner_resolved)?`저녁 ${tr.dinner_resolved?'해결':'미해결'}`:'',has(tr.open_meal_options)?`식사 후보 ${tr.open_meal_options}개`:'',has(tr.open_activity_options)?`활동 후보 ${tr.open_activity_options}개`:'',tr.day_end||s.day_end?`일과 종료 ${tr.day_end||s.day_end}`:''].filter(Boolean).join(' · '):'';
 // the lighter improved input may carry only today's meal flags and minutes since the last meal: show those, never "없음" by omission
 const prior=(c.meal_experiences||[]).at(-1),done=Object.entries(s.meals||{}).filter(([,v])=>v).map(([k])=>({breakfast:'조식',lunch:'점심',dinner:'저녁'})[k]).filter(Boolean),since=s.modeled_need?.minutes_since_last_meal;
 const priorText=prior?`${(prior.order||[]).map(x=>`${x.label||'상품'} × ${x.quantity}`).join(' + ')||'식사'} · ${prior.minutes_since_end==null?'경과 시간 미기록':prior.minutes_since_end+'분 전 종료'}`:done.length||Number.isFinite(since)?[done.length?`오늘 ${done.join('·')} 완료`:'',Number.isFinite(since)?`마지막 식사 ${since}분 전`:''].filter(Boolean).join(' · '):'오늘 기록된 식사 없음';
 const place=id=>{try{const n=typeof root.agPlaceName==='function'?root.agPlaceName(id):'';return n&&!/^[A-Z0-9_]+$/.test(n)?n:'';}catch(e){return '';}};
 const acts=(c.activity_experiences||[]).filter(x=>x.action!=='move');
 const action=actions.find(a=>a.action_id===p.action_id)||{},timing=action.schedule;
 const state=`<dl class="dc-state">${row('동행·방문 목적',`${partyText} · ${vi.purpose?.value?(purpose[vi.purpose.value]||vi.purpose.value):'목적 미확인'}`,OPS)}${row('판단 시각',`${vi.date||d.date||''} ${s.time||hm(d.minute)} · ${vi.checked_out?'체크아웃 이후':vi.checked_in?'투숙 중':'체크인 전'}`,OBS)}${row('직전 식사',priorText,OBS)}${acts.length?row('앞서 한 활동',acts.slice(-3).map(x=>x.label||'활동').join(' · ')+(acts.length>3?` 외 ${acts.length-3}건`:''),OBS):s.location&&place(s.location)?row('판단 위치',place(s.location),OBS):''}${fatigue||sat?row('허기·피로',[sat?SAT[sat]||'':'',fatigue].filter(Boolean).join(' · '),EST):''}${today?row('남은 일정',today,EST):''}${timing?row('이동·대기',`${timing.start_time}–${timing.end_time} 이용 · 이동 ${timing.travel_minutes}분 · 대기 ${timing.wait_minutes}분`,EST):''}${vi.breakfast?row('조식 포함',`성인 ${vi.breakfast.covered_adults??'?'}명 · ${vi.breakfast.whole_party_covered?'동행 전원 포함':'일부 인원만 포함'}`,OPS):''}</dl>`;
 // ④ 비교한 선택과 이유
 const altTime=plan=>{const a=actions.find(x=>x.action_id===plan.action_id)?.schedule;return a?`${a.start_time}–${a.end_time}${a.wait_minutes?` · 대기 ${a.wait_minutes}분`:''}`:'';};
 const shown=[{plan:plans[selIdx]||p,chosen:true},...alternatives.slice(0,3).map(x=>({plan:x}))];
 const withTime=shown.some(({plan})=>altTime(plan));
 const table=`<div class="dc-table ev-choice-table"><table><thead><tr><th>선택지</th><th>주문·금액</th>${withTime?'<th>시간</th>':''}<th>판단 요지</th></tr></thead><tbody>${shown.map(({plan,chosen})=>`<tr${chosen?' class="selected"':''}><th>${esc(name(plan.action_id))}${chosen?' · 선택':''}</th><td>${esc(items(plan)||'—')}${plan.order_total_krw?' · '+money(plan.order_total_krw):''}</td>${withTime?`<td>${esc(altTime(plan)||'—')}</td>`:''}<td>${chosen?'이번에 고른 선택 · 이유는 위 요약':esc(lab(plan.decision_summary||''))}</td></tr>`).join('')}</tbody></table></div>`;
 // the same sentence is shown once: a "why not" that only repeats an alternative's own summary is dropped
 const altText=alternatives.map(x=>lab(x.decision_summary||'')).filter(Boolean),whyNot=lab(p.why_not_other_plans||'');
 const repeats=whyNot&&altText.some(t=>whyNot.includes(t)||t.includes(whyNot.replace(/^[^:]{1,40}:\s*/,'')));
 const why=[p.tradeoff_note?['고민한 점',p.tradeoff_note]:null,whyNot&&!(plans.length>1&&repeats)?['다른 선택을 고르지 않은 이유',whyNot]:null,p.meal_assessment?.quantity_reason?['주문 양',p.meal_assessment.quantity_reason]:null,p.schedule_impact?['이후 일정',p.schedule_impact]:null].filter(Boolean);
 const comparison=(plans.length>1?table:'<p class="ev-empty">이 판단에는 다른 선택지가 함께 기록되지 않았습니다.</p>')+(why.length?`<dl class="dc-state ev-llm-reason">${why.map(([k,x])=>row(k,lab(x))).join('')}</dl>`:'');
 // ⑤ 실행 결과
 const replans=(d.attempts||[]).filter(a=>a.validation_rejection).length;
 const executed=d.execution_state==='EXECUTED'?'실행됨 · 영업시간·이동·주문 조건 확인 후 실행':d.execution_state==='VALIDATED'?'조건 확인 완료 · 실행 대기':d.execution_state==='RULE_FALLBACK'?'AI 계획을 실행하지 못해 규칙 정책으로 실행':'실행되지 않음';
 const result=[['실행',executed+(replans?` · 조건에 맞게 ${replans}회 다시 계획`:'')]];
 const alt0=alternatives[0];
 const lead=lab(v.summary);
 const metrics=[['판단 방식',`${origin} · ${policy}`],['핵심 비교',alt0?name(alt0.action_id):'다른 선택지 기록 없음'],['개인 후기',direct.length||cited.size?`${direct.length||cited.size}건 인용`:'인용 없음 · 상황 판단'],['주문',items(p)?money(p.order_total_krw):'주문 없음']];
 return {origin,policy,summary:lead,metrics,personal,state,comparison,result,direct:direct.length,cited:[...cited]};
}
// Reader-facing card for the flow panel: what else was weighed, in plain words.
// Cited review facts are shown by the panel's own evidence section; policy names,
// review codes, SHA and raw JSON stay in panel() for the evidence page. Nothing is
// reconstructed from scores.
function brief(scene){
 const v=view(scene);if(!v)return '';
 const d=v.decision,p=d.selected_plan||{},c=d.input_context||{},actions=c.actions||[],products=c.products||[];
 const name=id=>actions.find(a=>a.action_id===id)?.label||id;
 const items=plan=>(plan.items||[]).map(i=>`${actions.find(a=>a.action_id===plan.action_id)?.item_contracts?.find(x=>x.sku_id===i.sku_id)?.label||products.find(x=>x.sku_id===i.sku_id)?.label||i.sku_id} × ${i.quantity}`).join(' + ');
 const clip=(s,n)=>{s=String(s??'').trim();return s.length>n?s.slice(0,n-1)+'…':s;};
 const last=d.attempts?.at(-1),alternatives=(last?.answer?.plans||[]).filter((x,i)=>i!==last?.answer?.selected_index).slice(0,3);
 const executions=(d.attempts||[]).map(a=>a.provider?.execution);
 const origin=d.execution_state==='EXECUTION_HOLD'?'판단 보류 · 유효한 계획을 확정하지 못함':scene.recorded_review||executions.includes('CACHE_REPLAY')&&!executions.includes('LIVE_RESPONSES')?'저장된 LLM 판단 재생 · 유료 호출 없음':executions.includes('LIVE_RESPONSES')?'새로운 LLM 판단 · 실제 호출':'판단 출처 확인 필요';
 const replans=(d.attempts||[]).filter(a=>a.validation_rejection).length;
 const altHTML=alternatives.length?`<ul class="frp-brief-alts">${alternatives.map(x=>`<li><b>${esc(name(x.action_id))}${items(x)?' · '+esc(items(x)):''}</b><span>${esc(clip(x.decision_summary,120))}</span></li>`).join('')}</ul>${p.why_not_other_plans?`<p class="frp-note">${esc(clip(actionLabels(d)(p.why_not_other_plans),220))}</p>`:''}`:'<p class="frp-note">응답에 기록된 다른 계획이 없습니다.</p>';
 return `<section class="frp-section frp-brief-decision" data-frp-section="decision-brief" data-agent-decision-brief><div class="frp-section-heading"><h3>함께 저울질한 선택</h3></div><p class="frp-brief-origin">${esc(origin)} · ${esc(version(d.policy))}${replans?` · 운영 검증으로 ${replans}회 다시 계획`:''}</p>${altHTML}</section>`;
}
root.HLAgentDecisionView={record,resolve,view,panel,brief,story,version};if(typeof module!=='undefined')module.exports={record,resolve,view,panel,brief,story,version};
})(typeof window!=='undefined'?window:globalThis);
