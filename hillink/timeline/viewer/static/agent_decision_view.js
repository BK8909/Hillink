// Recorded pre-choice decisions only. Scores are never reconstructed as LLM reasons.
(function(root){
'use strict';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>Number.isFinite(n)?n.toLocaleString('ko-KR')+'원':'금액 미기록';
const hm=n=>Number.isFinite(n)?`${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`:'시각 미기록';
const list=xs=>xs?.length?`<ul>${xs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
// Policy versions are exact: a stored V16 answer is never relabeled as a V17 (day-end reviewed) judgment.
const VERSION={LLM_AUTONOMOUS_CUSTOMER_V16:'과거 판단 기준(V16) · 조기 종료 검증 이전',LLM_AUTONOMOUS_CUSTOMER_V17:'현재 판단 기준(V17) · 조기 종료 검증 적용'};
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
 const stateLine=fs?`<p><b>판단 시점 상태</b> 피로 ${esc(fs.value)} · 휴식 한도 ${esc(fs.rest_limit)}의 ${esc(fs.ratio_percent)}% (${esc(fs.level)})${tr?` · 저녁 ${tr.dinner_resolved?'해결':'미해결'} · 남은 식사 후보 ${esc(tr.open_meal_options)}개 · 활동 후보 ${esc(tr.open_activity_options)}개 · 방문 종료 ${esc(tr.day_end)}`:''} <small>엔진 상태 모델 · 실측 아님</small></p>`
  :Number.isFinite(sb.fatigue)?`<p><b>판단 시점 상태</b> 피로 ${Number(sb.fatigue).toFixed(2)} · 허기 참고 ${esc(sb.hunger)} <small>V16 기록 · 당시 모델에는 휴식 한도 척도가 전달되지 않음</small></p>`:'';
 const activities=(c.activity_experiences||[]).filter(x=>x.action!=='move');
 const activityHTML=activities.length?`<details><summary>이번 방문에서 이미 실행한 활동 · ${activities.length}건</summary><p>전날부터 이어진 가상 실행 기록입니다. 이용했다는 사실만으로 만족·선호를 확인한 것은 아닙니다.</p><ul>${activities.map(x=>`<li>${esc(x.date)} ${esc(x.start_time||hm(x.start))}–${esc(x.end_time||hm(x.end))} · ${esc(x.label||x.action)}</li>`).join('')}</ul></details>`:'';
 const citations=new Set([...(d.selected_plan?.supporting_fact_ids||[]),...(d.selected_plan?.counterevidence_fact_ids||[])]),facts=(c.facts||[]).filter(f=>f.fact_ids.some(id=>citations.has(id)));
 return `<p><b>${esc(purposeText)}</b> · ${esc(partyText)}</p>${eligibility}<p>${esc(v.date||'날짜 미기록')} ${esc(s.time||hm(d.minute))} · 방문 종료 ${esc(s.day_end||'미기록')}${v.checked_out?' · 체크아웃 이후':''}</p>${stateLine}${prior?`<p><b>이전 식사</b> ${esc(order||prior.venue)} · 종료 후 ${prior.minutes_since_end==null?'경과 시간 미기록':esc(prior.minutes_since_end)+'분'}. 주문 기록이며 실제 섭취량은 미관측입니다.</p>`:'<p>연결된 이전 가상 식사 기록 없음 · 도착 전 식사를 하지 않았다는 뜻은 아닙니다.</p>'}${activityHTML}${v.breakfast?`<p>조식 권리: 포함 성인 ${esc(v.breakfast.covered_adults??'미확인')}명 · ${v.breakfast.whole_party_covered?'현재 동행 전체 포함':'동행 전체 포함 여부·추가 요금 계약 확인'}</p>`:''}${facts.length?`<ul>${facts.map(f=>`<li>${f.fact_ids.filter(id=>citations.has(id)).map(id=>`<button class="cf-link" data-bh-fact="${esc(id)}">${esc(id)}</button>`).join(' · ')} — ${esc(f.summary)} <small>(${f.source_scope==='other'?'다른 장소의 경험 · ':''}원문 의미 검수 미완료${f.independent_observation_count==null?' · 독립 반복 횟수 미확정':''})</small></li>`).join('')}</ul>`:'<p>이 계획에 직접 연결한 개인 Fact 요약이 없습니다. 상황 판단과 개인 선호를 구분합니다.</p>'}`;
}
function reviewHTML(scene,d){
 const r=scene.recorded_review,review=r?.review?.review,findings=review?.findings||[];
 return `<section data-agent-review><p>${r?'저장된 V16 방문 재생 · 현재 실호출 0회 · 원 실행 모델 '+esc(r.model):'현재 판단 기록'}</p><p>원문 의미·행동 품질: 사람 승인 미완료. 유효한 Fact ID만으로 근거의 의미나 누락 없는 연결을 승인하지 않습니다.</p>${review?`<p>독립 모델 평가: ${esc(review.review_status)} · 사람 승인과 별도</p>${findings.map(f=>`<details><summary>${esc(f.dimension)} · ${esc(f.severity)}</summary><p>${esc(f.observation)}</p><p>원 판단 참조: ${esc((f.decision_refs||[]).join(', '))}</p><p>${esc(f.follow_up)}</p></details>`).join('')}`:''}<p>판단 경계: ${esc(d.date)} ${hm(d.minute)} · ${esc(d.selected_plan?.action_id)}. 연속 휴식이 합쳐진 장면과 개별 판단의 일대일 대응은 별도 검수 대상입니다.</p>${scene.basis?.continued_autonomous_decisions?.length?`<p>이 장면 안에 이어진 판단 ${scene.basis.continued_autonomous_decisions.length}건. 각 판단은 저장 방문의 원 판단 목록에서 확인합니다.</p>`:''}</section>`;
}
function contractHTML(scene,d,action){
 const p=d.selected_plan||{},contracts=action.item_contracts||[],assessment=p.meal_assessment;
 return `<section data-agent-contract>${contracts.length?`<h4>선택 전 상품·이용권 계약</h4>${contracts.map(c=>`<p>${esc(c.label||c.sku_id)} × ${esc(c.quantity)} · ${c.semantics==='PERSON_ACCESS_ENTITLEMENT'?'인원별 이용·과금 권리 · 개별 음식 주문이나 아동 전용 음식이 아님':esc(c.semantics||'음식 구성 계약 확인')}</p>`).join('')}<p>당시 후보 금액 ${money(action.order_total_krw)} · 원 선택 금액 ${money(p.order_total_krw)}</p>`:''}${assessment?`<p>모델의 식사 의도: ${esc(assessment.kind)} · ${esc(assessment.intake_assumption)}</p>`:''}<p>회계·서비스 시간대: ${esc(scene.meal||'미기록')} · 식사 의도와 별도. ${esc(p.meal_period_basis||d.input_context?.state?.meal_context?.meal_period_basis||d.input_context?.state?.meal_period_basis||'시간대는 기존 운영 시각 계약')}</p>${action.wait?`<p>판단 전 대기 계약: ${esc(JSON.stringify(action.wait))}</p>`:''}${action.consequences?`<p>당시 실행 결과 조건: ${esc(action.consequences)}</p>`:''}</section>`;
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
 const validation=d.execution_state==='EXECUTED'?'등록 후보·시간·주문 계약 검증을 통과한 계획으로 실행했습니다. 고객 선호나 실제 효과가 입증됐다는 뜻은 아닙니다.':d.execution_state==='VALIDATED'?'운영 계약 검증 통과 · 실행 완료는 아직 확인되지 않았습니다.':d.execution_state==='RULE_FALLBACK'?'LLM 계획을 실행하지 못해 규칙 정책으로 폴백했습니다.':'유효한 최종 실행을 확인하지 못했습니다.';
 const breakfast=d.breakfast_outcome?.startsWith('CONTRACT_UNAVAILABLE')?'조식 이용 조건을 충족한 음식 후보가 없어 보류했습니다. 조식 비선호·절약 성향으로 해석하지 않습니다.':d.breakfast_outcome?.startsWith('VOLUNTARY_NONUSE')?'이용 가능한 조식 후보 중 이번에는 미이용을 선택했습니다. 고정적인 조식 비선호로 해석하지 않습니다.':'';
 return `<section class="frp-section" data-agent-decision><h3>선택 전 LLM 판단·운영 검증</h3><div class="frp-chips"><span>${esc(v.mode)}</span><span>${esc(d.policy)}</span><span>${esc(version(d.policy))}</span></div><p>${esc(v.choice_scope)}</p>${reviewHTML(scene,d)}<h4>1. 고객 근거와 당시 방문 상황</h4>${contextHTML(d)}<h4>2. LLM이 선택한 이유</h4><p><strong>${esc(v.summary)}</strong></p>${p.current_need_assessment?`<p>현재 식사·휴식 필요 판단: ${esc(p.current_need_assessment.reason)} <small>모델 판단 · 실측 상태 아님</small></p>`:''}${items(p)?`<p><b>계획한 주문</b> ${esc(items(p))} · ${money(p.order_total_krw)}</p>`:''}${p.sharing_plan?`<p>나눠 먹는 방식: ${esc(p.sharing_plan)}</p>`:''}${p.meal_assessment?`<p>식사량 판단: ${esc(p.meal_assessment.quantity_reason)} · 실제 섭취는 미관측입니다.</p>`:''}<p>${esc(p.schedule_impact||'이후 일정 영향 미기록')}</p>${contractHTML(scene,d,action)}<h4>3. 비교한 대안</h4>${alternatives.length?alternatives.map(x=>`<details><summary>${esc(name(x.action_id))}${items(x)?' · '+esc(items(x)):''}</summary><p>${esc(x.decision_summary)}</p><p>${esc(x.schedule_impact||'')}</p></details>`).join(''):'<p>응답에 기록된 다른 계획이 없습니다. 대안 비교를 수행했다고 해석하지 않습니다.</p>'}${p.why_not_other_plans?`<p><b>선택과 비교한 판단</b> ${esc(p.why_not_other_plans)}</p>`:''}<h4>4. 운영 규칙의 검증과 실행</h4><p>${validation}</p>${timingHTML}${breakfast?`<p>${breakfast}</p>`:''}${rejections.length?`<p>재계획 요청 ${rejections.length}회</p>${list(rejections)}`:'<p>기록된 재계획 거절 없음</p>'}${d.day_end_review?`<p><b>조기 종료 검토</b> ${d.day_end_review.first_choice_rejected?'첫 선택은 거절됐고 재계획에서 남은 후보를 비교한 뒤 종료를 재확인':'첫 선택에서 검토 조건을 충족해 통과'} · 피로 ${esc(d.day_end_review.fatigue?.ratio_percent)}% (${esc(d.day_end_review.fatigue?.level)})</p>`:''}<p>${d.price_score_rerank===false?'최종 LLM 의도를 기존 가격 점수로 재정렬하지 않았습니다.':'가격 점수 재정렬 여부 미기록'}</p>${list(p.assumptions)}<details><summary>반례·다음 의도·후보 제외 및 기술 기록</summary><p>반례 Fact: ${esc((p.counterevidence_fact_ids||[]).join(', ')||'직접 인용 없음')}</p>${list(p.pending_intentions)}<p>다음 의도는 아직 실행되지 않은 계획입니다. Fact 의미 적합성과 행동 품질은 별도 검수 대상입니다.</p><pre>${esc(JSON.stringify({excluded:d.excluded||[],state_before:d.state_before,state_after:d.state_after,input_sha256:d.input_sha256,implementation_sha256:d.implementation_sha256},null,2))}</pre></details></section>`;
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
 const altHTML=alternatives.length?`<ul class="frp-brief-alts">${alternatives.map(x=>`<li><b>${esc(name(x.action_id))}${items(x)?' · '+esc(items(x)):''}</b><span>${esc(clip(x.decision_summary,120))}</span></li>`).join('')}</ul>${p.why_not_other_plans?`<p class="frp-note">${esc(clip(p.why_not_other_plans,220))}</p>`:''}`:'<p class="frp-note">응답에 기록된 다른 계획이 없습니다.</p>';
 return `<section class="frp-section frp-brief-decision" data-frp-section="decision-brief" data-agent-decision-brief><div class="frp-section-heading"><h3>함께 저울질한 선택</h3></div><p class="frp-brief-origin">${esc(origin)} · ${esc(version(d.policy))}${replans?` · 운영 검증으로 ${replans}회 다시 계획`:''}</p>${altHTML}</section>`;
}
root.HLAgentDecisionView={record,resolve,view,panel,brief,version};if(typeof module!=='undefined')module.exports={record,resolve,view,panel,brief,version};
})(typeof window!=='undefined'?window:globalThis);
