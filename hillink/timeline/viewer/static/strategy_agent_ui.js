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

 return `<section class="st-agent-pair st-decision-outcome"><h4>조건 변경 후 두 실행에서 관측한 차이</h4>${target}<p>호텔 전체 ${won(pair.comparison.before_krw)} → ${won(pair.comparison.after_krw)} (차이 ${won(pair.comparison.delta_krw)})</p><p><b>전체 방문의 업장별 소비·이용</b> · 포함 조식과 다른 날짜 이용 포함</p>${pair.comparison.venues.map(v=>`<p>${esc(v.name)} · ${won(v.before_krw)} → ${won(v.after_krw)} · 이용 ${v.before_teams} → ${v.after_teams}팀</p>`).join('')}<p>${pair.readiness?.execution_kind==='AUTONOMOUS_REINFERENCE'?'동일 자율 정책으로 행동을 다시 판단했습니다.':'규칙 정책으로 방문을 다시 계산했습니다.'} 같은 고객·시드·행사에서 가격 입력만 바꾼 관찰값이며, LLM 응답 변동과 할인만의 인과 효과는 분리 검증되지 않았습니다.</p>${p?`<details><summary>선택을 고정한 가격 재계산과 비교</summary><p>${p.delta_krw===null?'가격·수량 계약 검수 보류':`기존 주문을 그대로 유지했을 때의 가격 차이 ${won(p.delta_krw)}`}. 이 계산은 행동 전환 실험이나 새 구매가 아닙니다. 포함 혜택은 그대로 유지합니다.</p></details>`:''}<button class="cf-btn" data-agent-ledger="before">A 행동·원장</button> <button class="cf-btn" data-agent-ledger="after">B 행동·원장</button></section>`;
}
function groupHTML(c,result){
 const r=result.group_review;if(!r)return '';
 return `<section class="st-agent-group"><h4>함께 검토할 수 있는 운영 개입</h4><p>${esc(r.conclusion||r.note||'집단 적용 범위 검토 보류')}</p>${(r.groups||[]).map(g=>`<article><h4>${esc(g.title)}</h4><p>${g.customer_count}명 · ${g.customer_ids.map(c.name).map(esc).join(' · ')}</p><p>${esc(g.common_reason)}</p><p><strong>운영 조치</strong> ${esc(g.operator_action)}</p><details><summary>적용 제외 조건·개인 근거</summary><p>${esc(g.exclusions.join(' · '))}</p><p>${esc(g.uncertainties.join(' · '))}</p>${Object.entries(g.fact_ids).map(([pid,ids])=>`<p>${esc(c.name(pid))}: ${ids.map(esc).join(', ')}</p>`).join('')}</details><small>개별 가격 실험 연결 ${g.individually_executable_customers.length}명 · 집단 효과 미검증</small></article>`).join('')}</section>`;
}
// LLM analysis in the rule strategy template (strategy_story.js render/conclusion DOM and classes): ① 고객 → ② 이번 선택
// → ③ 바꾸려는 선택 → ④ 전략 카드 → ⑤ 최종 제안. The model's own sentences are shown as written; only codes become words.
const KIND={experience:'✧ 미식 경험',food:'◇ 메뉴 구성',benefit:'＋ 혜택',space:'◈ 공간',convenience:'◷ 예약·편의',value:'↗ 가치 비교'};
const BASIS={RECORDED_COMPARISON:'이번 방문의 비교 기록으로 확인',HYPOTHESIS:'AI 가설 · 기록으로 확인되지 않음',NO_EVIDENCE:'미선택 이유 기록 없음'};
const ORIGIN={LIVE_RESPONSES:'실시간 AI 분석',CACHE_REPLAY:'저장된 AI 분석 재생'};
const HOLD_TEXT={REPLAY_MISS:'저장된 AI 분석 기록이 없어 실행하지 못했습니다. 실시간 AI 호출이 가능한 서버에서 다시 실행해 주세요.',CALL_LIMIT:'승인된 호출 한도에 도달해 실행하지 못했습니다.',USD_LIMIT:'승인된 비용 한도에 도달해 실행하지 못했습니다.',LIVE_APPROVAL_REQUIRED:'이 서버는 실시간 AI 호출 승인 없이 시작되어 실행하지 못했습니다.',STRATEGY_ANALYSIS_HOLD:'AI 분석을 완료하지 못했습니다.'};
const VENUE_KO={PIZZA_HILL:'피자힐',GEUMRYONG:'금룡',MYONGWOLGWAN:'명월관',ONDAL:'온달',MOEGI:'모에기',THE_BUFFET:'더뷔페',THE_PAVILION:'더 파빌리온',ROOM_MEAL:'룸서비스',IRD:'룸서비스',LE_PASSAGE:'르 파사쥬',DELVINO:'델비노',EXTERNAL_DELIVERY:'외부 배달',DOUGLAS_LOUNGE:'더글라스 라운지'};
const plain=t=>(HOLD_TEXT[String(t??'').trim()]||String(t??'')).replace(/\b(?:meal:)?([A-Z][A-Z_]{3,})\b/g,(m,k)=>VENUE_KO[k]||m).replace(/\bE\d{2}(?:\s*[·,]\s*E\d{2})*\b(?:에서|의)?/g,m=>/에서$/.test(m)?'후기 경험에서':/의$/.test(m)?'후기 경험의':'후기 경험').replace(/\b[A-Z][A-Z0-9_]{4,}\b\s*[:：]\s*/g,'').replace(/\s*\((?:[A-Z][A-Z0-9_]{4,})\)/g,'').replace(/(?:상품\s*)?\bHC-[A-Z]+-\d+\b/g,'해당 상품').replace(/\b(?:A|N)\d\d-F\d+[a-z]?\b(?:\s*[,·]\s*(?:A|N)\d\d-F\d+[a-z]?\b)*/g,'후기').trim();
function factItems(c,pid,ids){const fs=c.evidence?.[pid]?.facts||[];return ids.map(id=>fs.find(f=>f.id===id)).filter(Boolean).map(f=>`<li><p>${esc(f.summary)}</p><small>${f.source==='WALKERHILL'?'워커힐 후기':f.source==='SAME_AUTHOR_OTHER'?'같은 작성자의 다른 경험':'후기'}</small></li>`).join('');}
function customerHTML(c,r,locked,many){
 const pid=r.customer_id,src=scenes(c,pid)[state.selected[pid]||0],strategies=r.strategies||[],origin=[...new Set((r.provider||[]).map(p=>ORIGIN[p.provider?.execution]).filter(Boolean))].join(' · ')||'AI 분석';
 const cards=strategies.map((i,n)=>{const support=factItems(c,pid,i.supporting_fact_ids||[]),counter=factItems(c,pid,i.counterevidence_fact_ids||[]);
  return `<article class="st-idea ${n===0?'st-idea-primary':''}" data-personal-idea data-agent-idea="${esc(i.id)}" data-strategy-kind="${esc(i.kind)}"><header><span class="st-idea-type">${KIND[i.kind]||'운영 개입'}</span><small>${n===0?'우선 추천 · ':''}운영 가설 · AI 제안</small></header><h3>${esc(plain(i.title))}</h3><p class="st-personal-why"><span class="st-copy-label">이 고객에게 맞는 이유</span>${esc(plain(i.problem))}</p><p class="st-action-copy"><b class="st-copy-label">운영자가 바꿀 조건</b> ${esc(plain(i.proposed_intervention))}</p><p class="st-mechanism"><span class="st-copy-label">기대하는 행동 변화</span>${esc(plain(i.expected_behavior_hypothesis))}</p><details><summary>추천 근거 · 관련 후기 확인</summary><ul class="st-source-list">${support||'<li>직접 연결한 후기가 없습니다. 현재 방문 상황에 근거한 제안입니다.</li>'}</ul>${counter?`<h5>함께 고려한 반대·조건부 경험</h5><ul class="st-source-list">${counter}</ul>`:''}${(i.supporting_fact_ids||[]).length?`<button class="cf-btn" data-story-profile="${esc(pid)}" data-story-facts="${esc(i.supporting_fact_ids.join(','))}">프로필에서 근거 확인</button>`:''}</details><details><summary>적용 전 확인</summary><ul>${(i.required_conditions||[]).map(x=>`<li>${esc(plain(x))}</li>`).join('')}</ul>${(i.uncertainties||[]).length?`<h5>아직 모르는 점</h5><ul>${i.uncertainties.map(x=>`<li>${esc(plain(x))}</li>`).join('')}</ul>`:''}</details>${i.experiment_supported?`<div class="st-idea-test"><p>현재 가능한 검증: 등록 상품 가격 A/B. 위 운영 가설 전체의 효과와 구분합니다.</p><div class="st-form"><label>할인<select data-agent-percent${locked}>${[10,15,20].map(p=>`<option value="${p}"${p===state.pct?' selected':''}>${p}%</option>`).join('')}</select></label><button class="cf-btn cf-primary" data-agent-pair="${esc(i.id)}" data-agent-customer="${esc(pid)}"${locked}>이 전략의 가격 조건 시험하기</button></div></div>`:'<p class="st-idea-test"><small class="st-status-pill">운영 가설 · 실험 미지원</small></p>'}</article>`;}).join('');
 const holds=[...(r.hold_reasons||[]).map(plain),...((r.experiment_holds||[]).includes('TIME_COMPATIBILITY_REVIEW_BEFORE_PRICE')?['선택한 식사 시각에는 목표 업장 이용이 맞지 않습니다. 할인 전에 영업시간·예약·행사 일정을 먼저 검토해야 합니다.']:[])].filter(Boolean);
 const lead=strategies[0];
 const verdict=`<section class="st-card st-operator-decision" data-agent-verdict><span class="st-eyebrow">05 / 운영 전략 최종 제안</span><h2>${lead?'가장 추천하는 운영 전략':'운영 전략 보류'}</h2><article class="st-conclusion-customer"><p class="st-conclusion-context">${esc(plain(r.current_choice_analysis))}</p><p class="st-conclusion-lead">${lead?`<strong>${esc(plain(lead.title))}</strong> — `:''}${esc(plain(r.operator_recommendation||(lead?'':'근거가 충분한 제안이 없어 보류합니다.')))}</p><div class="st-conclusion-evidence"><span><b>고객 관측 근거</b>${lead?`후기 ${(lead.supporting_fact_ids||[]).length}건${(lead.counterevidence_fact_ids||[]).length?` · 반대·조건부 ${(lead.counterevidence_fact_ids||[]).length}건`:''}`:'연결 근거 없음'}</span><span><b>실제 선택</b>${src?`${esc(src.label)} · ${won(src.basis?.charge?.krw)}`:'연결된 방문 없음'}</span></div><small class="st-status-pill">${esc(statusLabel(r.status))} · ${esc(origin)}</small></article>${state.pair?pairHTML(state.pair):''}</section>`;
 const body=`<header class="st-story-hero"><small>① AI가 분석한 고객과 방문</small><h2>${esc(c.name(pid))} 고객 맞춤 운영 전략</h2><p>${esc(c.context)}</p><small class="st-status-pill">${esc(origin)} · ${esc(statusLabel(r.status))}</small></header>
 <div class="st-story-context"><section class="st-story-choice"><small>② 이번 방문의 선택</small><h3>${src?esc(src.label)+' · '+won(src.basis?.charge?.krw):'현재 방문 연결 없음'}</h3><p>${esc(plain(r.current_choice_analysis))}</p>${src?`<span>${esc(src.visit_date)}</span>`:''}</section><section class="st-story-goal"><small>③ 바꾸려는 선택 · 선택하지 않은 이유</small><h3>${esc(c.targetLabel||'목표 업장')}</h3><p>${esc(plain(r.nonselection_analysis))}</p><b>${esc(BASIS[r.nonselection_basis]||'근거 확인 필요')}</b></section></div>
 <h3 class="st-story-step">④ 이 고객에게 적용해볼 만한 운영 전략</h3><div class="st-ideas">${cards||`<p class="st-story-empty">${esc(holds[0]||'근거가 충분한 제안이 없어 보류했습니다.')}</p>`}</div>${holds.length&&cards?`<p class="st-graph-note">${holds.map(esc).join(' · ')}</p>`:''}${verdict}`;
 return `<article data-personal-customer="${esc(pid)}" data-agent-customer-result>${many?`<details${many===1?' open':''}><summary>${esc(c.name(pid))} · ${strategies.length}개 제안 · ${esc(statusLabel(r.status))}</summary>${body}</details>`:body}</article>`;
}
function resultHTML(c,result,locked){
 const many=result.customers.length>1,gen=result.customers.filter(r=>(r.strategies||[]).length).length;
 const kpi=many?`<section class="st-card st-cohort-overview" data-agent-cohort><span class="st-eyebrow">고객별 AI 분석을 종합한 운영 기회</span><h2>전체 분석 결과</h2><div class="st-cohort-kpis"><div><small>분석 대상</small><strong>${result.analysis_count}명</strong></div><div><small>추천 생성</small><strong>${gen}명</strong></div><div><small>보류</small><strong>${result.analysis_count-gen}명</strong></div></div>${groupHTML(c,result)}</section>`:'';
 return `<section class="st-card st-story" data-personal-proposal data-agent-result-summary>${kpi}${result.customers.map((r,i)=>customerHTML(c,r,locked,many?(i===0?1:2):0)).join('')}</section>`;
}
function render(c){
 refresh(c);if(!c.enabled)return '';
 const locked=state.busy?' disabled':'';
 const actual=c.basis==='ACTUAL_RUN';
 const choices=actual?c.ids.map(pid=>`<label>${esc(c.name(pid))}의 실제 소비 결정<select data-agent-source="${esc(pid)}"${locked}>${scenes(c,pid).map((s,i)=>`<option value="${i}"${i===(state.selected[pid]||0)?' selected':''}>${esc(s.visit_date)} · ${esc(s.label)} · ${won(s.basis?.charge?.krw)}</option>`).join('')}</select></label>`).join(''):'';
 const missing=actual&&c.ids.some(pid=>!scenes(c,pid).length);
 const status=state.busy?(state.progress==='QUEUED'?'앞선 방문·분석 작업이 끝나면 시작합니다. 요청은 대기 중이며 다시 누를 필요가 없습니다.':'LLM 분석·엔진 검증 중입니다. 다른 화면 기능은 계속 사용할 수 있습니다.'):'실행하면 실시간 AI가 분석합니다(고객 1명당 약 1~2회 호출 · 승인 한도 안). 제안은 미검증 운영 가설이며, 실제 A/B 실행과 구분합니다.';
 return `<section class="st-card st-agent-lab" data-agent-lab><h3>LLM으로 운영 개입 검토</h3><p>${esc(c.context)} · ${actual?'서버에 보존된 실제 가상 방문':c.basis==='OPERATOR_ASSUMPTION'?'운영자 출발 행동 가정':'프로필 기반 가설'}</p><div class="st-form">${choices}</div>
 <p role="status">${status}</p>${missing?'<p>선택 고객 모두의 실제 소비가 연결되지 않았습니다. 새 방문을 실행하거나 프로필 가설로 분석해 주세요.</p>':''}
 <button class="cf-btn cf-primary" data-agent-analyze${locked}${missing?' disabled':''}>${state.busy?'실행 중…':'LLM 전략 분석 실행'}</button>
 ${state.error?`<p role="alert">${esc(state.error)}</p>`:''}
 ${state.result?resultHTML(c,state.result,locked):''}
</section>`;
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
