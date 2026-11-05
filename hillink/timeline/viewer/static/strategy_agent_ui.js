// Explicit local LLM jobs. Editing inputs never issues a paid request.
(function(root){
'use strict';
const state={key:null,selected:{},busy:false,progress:null,job:null,result:null,error:null,pair:null,pct:20};
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const won=x=>new Intl.NumberFormat('ko-KR').format(x||0)+'원';
const statusLabel=s=>({GENERATED_UNTESTED:'운영 가설 · 효과 미검증',RECOMMENDATION_HOLD:'개인화 전략 검토 보류',EVIDENCE_HOLD:'개인 근거 검수 보류',VALIDATION_HOLD:'제안 계약 검수 보류',PROVIDER_UNAVAILABLE:'LLM 실행 불가'}[s]||s);
function key(c){return JSON.stringify([c.ids,c.target,c.intent,c.basis,c.assumption,c.run?.ledger?.run_id,c.context]);}
function refresh(c){const k=key(c);if(state.key!==k)Object.assign(state,{key:k,selected:{},busy:false,progress:null,job:null,result:null,error:null,pair:null});}
function scenes(c,pid){return (c.run?.plans?.[pid]?.scenes||[]).filter(s=>s.consume||s.meal);}
function pairHTML(pair){
 if(!pair)return '';
 if(!pair.comparison||pair.readiness?.comparable===false)return `<section class="st-agent-pair"><h4>A/B 실행 검수 보류</h4><p>두 방문의 완료·동일 조건을 확인하지 못해 전환이나 소비 효과를 집계하지 않았습니다.</p><p>${esc((pair.readiness?.reasons||[]).join(' · '))}</p><p>실행 제한을 확인한 뒤 같은 조건으로 다시 실행해 주세요.</p></section>`;
 const p=pair.fixed_choice_repricing,t=pair.target_meal_comparison;
 const target=t?.status==='OBSERVED_SIMULATED_MEAL_PERIOD'?`<p><strong>${esc(t.scope.date)} ${t.scope.meal==='dinner'?'저녁':'점심'} 목표 업장 선택</strong> ${t.before.selected_teams} → ${t.after.selected_teams}팀 · 새로 선택 ${t.entering_customers.length}팀</p><p>해당 끼니의 목표 업장 소비 ${won(t.before.paid_krw)} → ${won(t.after.paid_krw)}. 포함 조식·다른 날짜 이용은 이 유입 수에 넣지 않습니다.</p>`:'<p>이전 실험 계약에는 날짜·끼니별 유입 범위가 기록되지 않았습니다. 아래 업장 전체 방문 수를 목표 식사 전환으로 해석하지 않습니다.</p>';

 return `<section class="st-agent-pair"><h4>조건 변경 후 두 실행에서 관측한 차이</h4>${target}<p>호텔 전체 ${won(pair.comparison.before_krw)} → ${won(pair.comparison.after_krw)} (차이 ${won(pair.comparison.delta_krw)})</p><p><b>전체 방문의 업장별 소비·이용</b> · 포함 조식과 다른 날짜 이용 포함</p>${pair.comparison.venues.map(v=>`<p>${esc(v.name)} · ${won(v.before_krw)} → ${won(v.after_krw)} · 이용 ${v.before_teams} → ${v.after_teams}팀</p>`).join('')}<p>${pair.readiness?.execution_kind==='AUTONOMOUS_REINFERENCE'?'동일 자율 정책으로 행동을 다시 판단했습니다.':'규칙 정책으로 방문을 다시 계산했습니다.'} 같은 고객·시드·행사에서 가격 입력만 바꾼 관찰값이며, LLM 응답 변동과 할인만의 인과 효과는 분리 검증되지 않았습니다.</p>${p?`<details><summary>선택을 고정한 가격 재계산과 비교</summary><p>${p.delta_krw===null?'가격·수량 계약 검수 보류':`기존 주문을 그대로 유지했을 때의 가격 차이 ${won(p.delta_krw)}`}. 이 계산은 행동 전환 실험이나 새 구매가 아닙니다. 포함 혜택은 그대로 유지합니다.</p></details>`:''}<button class="cf-btn" data-agent-ledger="before">A 행동·원장</button> <button class="cf-btn" data-agent-ledger="after">B 행동·원장</button></section>`;
}
function groupHTML(c,result){
 const r=result.group_review;if(!r)return '';
 return `<section class="st-agent-group"><h4>함께 검토할 수 있는 운영 개입</h4><p>${esc(r.conclusion||r.note||'집단 적용 범위 검토 보류')}</p>${(r.groups||[]).map(g=>`<article><h4>${esc(g.title)}</h4><p>${g.customer_count}명 · ${g.customer_ids.map(c.name).map(esc).join(' · ')}</p><p>${esc(g.common_reason)}</p><p><strong>운영 조치</strong> ${esc(g.operator_action)}</p><details><summary>적용 제외 조건·개인 근거</summary><p>${esc(g.exclusions.join(' · '))}</p><p>${esc(g.uncertainties.join(' · '))}</p>${Object.entries(g.fact_ids).map(([pid,ids])=>`<p>${esc(c.name(pid))}: ${ids.map(esc).join(', ')}</p>`).join('')}</details><small>개별 가격 실험 연결 ${g.individually_executable_customers.length}명 · 집단 효과 미검증</small></article>`).join('')}</section>`;
}
function render(c){
 refresh(c);if(!c.enabled)return '';
 const locked=state.busy?' disabled':'';
 const actual=c.basis==='ACTUAL_RUN';
 const choices=actual?c.ids.map(pid=>`<label>${esc(c.name(pid))}의 실제 소비 결정<select data-agent-source="${esc(pid)}"${locked}>${scenes(c,pid).map((s,i)=>`<option value="${i}"${i===(state.selected[pid]||0)?' selected':''}>${esc(s.visit_date)} · ${esc(s.label)} · ${won(s.basis?.charge?.krw)}</option>`).join('')}</select></label>`).join(''):'';
 const missing=actual&&c.ids.some(pid=>!scenes(c,pid).length);
 const status=state.busy?(state.progress==='QUEUED'?'앞선 방문·분석 작업이 끝나면 시작합니다. 요청은 대기 중이며 다시 누를 필요가 없습니다.':'LLM 분석·엔진 검증 중입니다. 다른 화면 기능은 계속 사용할 수 있습니다.'):'제안은 미검증 운영 가설이며, 실제 A/B 실행과 구분합니다.';
 return `<section class="st-card st-agent-lab" data-agent-lab><h3>LLM으로 운영 개입 검토</h3><p>${esc(c.context)} · ${actual?'서버에 보존된 실제 가상 방문':c.basis==='OPERATOR_ASSUMPTION'?'운영자 출발 행동 가정':'프로필 기반 가설'}</p><div class="st-form">${choices}</div>
 <p role="status">${status}</p>${missing?'<p>선택 고객 모두의 실제 소비가 연결되지 않았습니다. 새 방문을 실행하거나 프로필 가설로 분석해 주세요.</p>':''}
 <button class="cf-btn cf-primary" data-agent-analyze${locked}${missing?' disabled':''}>${state.busy?'실행 중…':'LLM 전략 분석 실행'}</button>
 ${state.error?`<p role="alert">${esc(state.error)}</p>`:''}
 ${state.result?`<p data-agent-result-summary>${state.result.analysis_count}명 분석 · ${state.result.generated_count}명 제안 생성 · 사람 의미 검수 대기</p>${groupHTML(c,state.result)}${state.result.customers.map(r=>`<details${state.result.analysis_count===1?' open':''}><summary>${esc(c.name(r.customer_id))} · ${esc(statusLabel(r.status))}</summary>
 <p>${esc(r.current_choice_analysis)}</p><p>미선택 이유: ${esc(r.nonselection_analysis)} (${esc(r.nonselection_basis)})</p>
 ${(r.experiment_holds||[]).includes('TIME_COMPATIBILITY_REVIEW_BEFORE_PRICE')?'<p>선택한 식사 시각에는 목표 업장 이용이 맞지 않습니다. 할인 전에 영업시간·예약·행사 일정을 검토해야 합니다.</p>':''}
 ${(r.hold_reasons||[]).map(h=>`<p>${esc(h)}</p>`).join('')}
 ${(r.strategies||[]).map(i=>`<article class="st-agent-idea"><h4>${esc(i.title)}</h4><p>${esc(i.problem)}</p><p><strong>운영 개입</strong> ${esc(i.proposed_intervention)}</p><p><strong>기대 행동 가설</strong> ${esc(i.expected_behavior_hypothesis)}</p>
 <details><summary>개인 Fact·반례·적용 조건</summary>${[...i.supporting_fact_ids,...i.counterevidence_fact_ids].map(fid=>`<p>${esc(fid)} · ${esc(c.evidence?.[r.customer_id]?.facts?.find(f=>f.id===fid)?.summary||'해당 프로필에서 근거 확인')}</p>`).join('')}<p>${esc(i.required_conditions.join(' · '))}</p><p>${esc(i.uncertainties.join(' · '))}</p><button class="cf-link" data-story-profile="${esc(r.customer_id)}" data-story-facts="${esc(i.supporting_fact_ids.join(','))}">프로필 원문 근거 보기</button></details>
 <small>${i.experiment_supported?'등록 가격 개입 실행 가능 · 아직 미실험':'미검증 제안 · 엔진 연결 필요'}</small>
 ${i.experiment_supported?`<div class="st-form"><label>할인 조건<select data-agent-percent${locked}>${[10,15,20].map(p=>`<option${p===state.pct?' selected':''}>${p}</option>`).join('')}</select></label><button class="cf-btn" data-agent-pair="${esc(i.id)}" data-agent-customer="${esc(r.customer_id)}"${locked}>동일 방문 가격 A/B 실행</button></div>`:''}</article>`).join('')}
 <p><strong>운영자 판단</strong> ${esc(r.operator_recommendation)}</p><small>${esc((r.provider||[]).map(p=>p.provider?.execution).filter(Boolean).join(' · '))}</small></details>`).join('')}`:''}
 ${pairHTML(state.pair)}</section>`;
}
async function poll(c,job,k){
 while(['QUEUED','RUNNING'].includes(job.status)){
  if(k!==state.key)return null;
  if(state.progress!==job.status){state.progress=job.status;c.draw();}
  await new Promise(r=>setTimeout(r,2000));
  job=await c.call('/api/agent/jobs?id='+encodeURIComponent(job.job_id));
  if(k!==state.key)return null;
 }
 if(job.status!=='DONE')throw Error(job.error||'실행 상태 확인 필요');
 return job;
}
async function execute(c,path,body,assign){
 if(state.busy)return;
 const k=state.key;state.busy=true;state.progress='SUBMITTING';state.error=null;c.draw();
 try{const job=await poll(c,await c.call(path,body),k);if(job&&k===state.key)assign(job);}
 catch(err){if(k===state.key)state.error=err.message;}
 finally{if(k===state.key){state.busy=false;c.draw();}}
}
function wire(el,c){
 el.querySelectorAll('[data-agent-source]').forEach(x=>x.onchange=()=>{state.selected[x.dataset.agentSource]=Number(x.value);state.result=null;state.pair=null;c.draw();});
 el.querySelector('[data-agent-analyze]')?.addEventListener('click',()=>{
  const sources={};if(c.basis==='ACTUAL_RUN')for(const pid of c.ids){const s=scenes(c,pid)[state.selected[pid]||0];if(!s)return;sources[pid]={date:s.visit_date,start:s.t0,venue:s.loc};}
  const body={customers:c.ids,run_id:c.basis==='ACTUAL_RUN'?c.run?.ledger?.run_id:null,
   goal:{target_venue:c.target,intent:c.intent,basis:c.basis,assumed_origin:c.assumption,scenario_context:c.context},source_actions:sources};
  execute(c,'/api/strategy/agent',body,j=>{state.job=j.job_id;state.result=j.result;state.pair=null;});
 });
 el.querySelectorAll('[data-agent-percent]').forEach(x=>x.onchange=()=>{state.pct=Number(x.value);state.pair=null;c.draw();});
 el.querySelectorAll('[data-agent-pair]').forEach(x=>x.onclick=()=>execute(c,'/api/strategy/agent/experiment',{
  analysis_job_id:state.job,run_id:c.run.ledger.run_id,customer:x.dataset.agentCustomer,strategy_id:x.dataset.agentPair,percent:state.pct},j=>{state.pair=j.result;}));
 el.querySelectorAll('[data-agent-ledger]').forEach(x=>x.onclick=()=>c.openLedger(state.pair[x.dataset.agentLedger]));
}
root.HLAgentLab={render,wire};if(typeof module!=='undefined')module.exports={key,scenes,pairHTML};
})(typeof window!=='undefined'?window:globalThis);
