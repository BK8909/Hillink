/* Display actual decision provenance; never infer missing scores or mutate a run. */
(function(root){'use strict';
const n=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
function classify(x){
 if(['EXECUTED','INFO_CHECK_NOT_ATTENDANCE'].includes(x.decision?.execution_status)||x.turnDecision||x.review)return 'CHOICE';
 if(x.linkedDecisions?.some(d=>d.execution_status==='EXECUTED'))return 'MISSING';
 const a=x.scene?.act||'';
 if(a==='wait'||x.executionEvent?.kind==='wait')return 'CONDITIONAL';
 if(x.scene?.source==='obligation'&&['arrive','wake','unpack','pack','checkin','checkout','leave','sleep'].includes(a))return 'SCHEDULE';
 if(x.decision||x.scene?.basis?.m4?.decision_packet_ids?.length)return 'MISSING';
 if(['arrive','wake','unpack','pack','checkin','checkout','leave','sleep','move'].includes(a)&&!x.scene.consume)return 'SCHEDULE';
 return 'MISSING';
}
function split(r,planner=false){
 const g=n(r.general_food_evidence?.delta)||0,ctx=n(r.context_adjustment)||0,actual=n(r.final_score??r.score),total=n(r.final_with_lookahead)??actual,sc=r.score_contribution;
 const base=sc?n(sc.common):n(r.base_score),personal=sc?n(sc.evidence_delta):null;
 const sum=base==null?null:base+(personal||0)+ctx+g;
 return {base,personal,context:ctx,general:g,self:actual,lookahead:total==null||actual==null?null:total-actual,total,reconciled:sum!=null&&actual!=null&&Math.abs(sum-actual)<.0011,residual:sum==null||actual==null?null:actual-sum,planner};
}
function selection(x){
 const adopted=/ADOPTED/.test(x.review?.decided_by||'');
 const final=adopted?(x.review.actual_candidate_id||x.review.final):x.selectedId;
 return {adopted,final:final||null,rule:x.review?.rule_choice||x.selectedId};
}
const API={classify,split,selection};if(typeof module!=='undefined'&&module.exports)module.exports=API;root.HLDecisionExplain=API;
if(!root.document)return;
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>v==null?'분리 미기록':Number(v).toFixed(4);
const section=(i,title,body)=>`<section class="dc-step" data-decision-step="${i}" id="decision-step-${i}"><h3>${title}</h3>${body}</section>`;
const old=root.bhEvidenceHTML;
root.bhEvidenceHTML=function(m,c){
 // A recorded autonomous plan is the decision, not a missing legacy score packet.
 if(root.HLAgentDecisionView?.record(m.raw)||m.plan?.trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_'))return old(m,c);
 const html=old(m,c),tmp=document.createElement('div');tmp.innerHTML=html;
 const nav=tmp.querySelector('.ux-evidence-nav');if(!nav)return html;
 const actionSelect=nav.querySelector('#bhRunAction');
 if(actionSelect)for(const opt of [...actionSelect.options]){
  const v=root.HLStory.input(m.flow.result,c.customer_id,Number(opt.value));
  if(classify(v)==='SCHEDULE'){
   if(Number(opt.value)===c.scene_index){opt.disabled=true;opt.textContent+=' (자동 일정)';}else opt.remove();
  }
 }
 const navHTML=nav.outerHTML;nav.remove();
 const x=root.HLStory.input(m.flow.result,c.customer_id,c.scene_index),kind=classify(x),ctx=x.decision?.packet?.context_factors||{},reason=root.HLChoiceReason?.compose(x),raw=m.raw;
 const label={CHOICE:'선택 판단',CONDITIONAL:'조건부 행동',SCHEDULE:'자동 일정',MISSING:'판단 연결 확인 필요'}[kind];
 const head=`<div class="dc-head"><small>${e(dno(c.customer_id))} · ${e(raw.visit_date)} ${e(agHM(raw.t0))} · ${e(label)}</small><h3>${e(raw.label)}</h3><p>${e(reason?.sentences?.join(' ')||'기록된 실행을 확인합니다.')}</p></div>`;
 const audit=`<details class="dc-audit"><summary>전체 Fact·기여 항·후보·LLM·원장 원본</summary>${tmp.innerHTML}</details>`;
 if(kind==='SCHEDULE'||kind==='CONDITIONAL')return `<div class="dc-page">${navHTML}${head}<p>${kind==='SCHEDULE'?'별도 후보 평가 없이 방문 일정에 배치된 행동입니다.':'기록된 조건: '+e(raw.why||'시간 제약에 따른 대기')+' · '+e(agHM(raw.t0))+'–'+e(agHM(raw.t1))+'. 개인 취향 점수와 구분합니다.'}</p>${audit}</div>`;
 const chosen=selection(x),prev=x.prev,next=x.nexts?.[0],party=m.L.receipts[c.customer_id]?.party_size;
 const state=`<dl class="dc-state"><div><dt>동행·위치</dt><dd>일행 ${e(party??'미기록')}명 · ${e(typeof agPlaceName==='function'?agPlaceName(ctx.location_id||raw.loc):raw.loc)}</dd></div><div><dt>직전 행동</dt><dd>${e(prev?.label||'이전 행동 기록 없음')}</dd></div><div><dt>직전 식사</dt><dd>${e(ctx.last_meal?ctx.last_meal.date+' '+ctx.last_meal.end+' · '+(ctx.minutes_since_meal_end??'?')+'분 경과':'별도 식사 상태 미기록')}</dd></div><div><dt>현재 상태</dt><dd>허기 지표 ${e(ctx.meal_state?.current_meal_target_proxy??'미기록')} · 피로 지표 ${ctx.fatigue_proxy==null?'미기록':num(ctx.fatigue_proxy)} (시뮬레이션 상태)</dd></div><div><dt>실행상 다음 행동 (사후 연결)</dt><dd>${e(next?agHM(next.t0)+' '+next.label:'다음 일정 없음')}</dd></div><div><dt>판단 당시 일정 한계</dt><dd>${e(ctx.next_known_deadline??'별도 기록 없음')}</dd></div><div><dt>행사·날씨</dt><dd>${e(m.L.context.event_label||'행사 정보 미기록')} · ${e(m.flow.request?.environment?.weather||'입력 원본 확인')}</dd></div></dl>`;
 const selected=x.rawCands.find(r=>r.candidate_id===chosen.final),parts=selected?.score_contribution?.terms||[];
 const personal=parts.filter(t=>Math.abs(t.evidence_delta)>1e-6&&(t.fact_ids||[]).length).sort((a,b)=>Math.abs(b.evidence_delta)-Math.abs(a.evidence_delta));
 const P=libP(c.customer_id)||{},facts=P.engine?.facts||{};
 const maxPersonal=Math.max(...personal.map(t=>Math.abs(t.evidence_delta)),.001);
 const frow=t=>{
  const direct=/명시적.*거부/.test(t.factor);
  return `<li class="ev-contribution"><div><b>${e(t.factor)}</b><strong>${t.evidence_delta>0?'+':''}${num(t.evidence_delta)}</strong></div><div class="ev-contribution-track"><span class="${t.evidence_delta<0?'negative':''}" style="width:${Math.abs(t.evidence_delta)/maxPersonal*100}%"></span></div><small>${direct?'후기 직접 관측':'후기 기반 성향 추론'} · 같은 상태에서 개인 근거를 제거한 차이</small><details><summary>연결 Fact ${t.fact_ids.length}개 확인</summary>${t.fact_ids.map(id=>`<button class="cf-link" data-bh-fact="${e(id)}">${e(id)} 후기 확인 ↗</button>`).join(' · ')}</details></li>`;
 };
 let personalHTML=personal.length?`<ul class="dc-personal">${personal.slice(0,2).map(frow).join('')}</ul>${personal.length>2?`<details><summary>나머지 기여 ${personal.length-2}개</summary><ul>${personal.slice(2).map(frow).join('')}</ul></details>`:''}`:x.turnDecision?`<p>별도 식사 판단의 후기 기여 ${num(x.turnDecision.reason_totals?.review)}. 세부 항과 원문 연결은 아래 전체 기록에서 확인합니다.</p>`:`<p>${x.decision?.packet?.kind==='PLANNER'?'이 경로의 개인 성향 민감도는 합산 가능한 점수 분해가 아닙니다. 전체 기록의 민감도와 연결 Fact를 참고합니다.':selected?.score_contribution?'이 후보의 기록된 개인 기여는 '+num(selected.score_contribution.evidence_delta)+'입니다. 개인 취향이 선택을 이끌었다고 단정하지 않습니다.':'이번 선택의 직접 개인 기여값을 확인할 수 없습니다. 개인 취향으로 단정하지 않습니다.'}</p>`;
 const rejectedDirect=x.rawCands.filter(r=>r.world_allowed!==false&&r.candidate_id!==chosen.final).flatMap(r=>(r.terms||[]).filter(t=>t.value<0&&t.fact_ids?.length&&/명시적.*거부/.test(t.factor||'')).map(t=>({r,t})));
 if(rejectedDirect.length)personalHTML+=`<details><summary>비교 후보에서 작용한 직접 부정 근거 ${rejectedDirect.length}건</summary><ul>${rejectedDirect.map(({r,t})=>`<li>${e(r.candidate_label||x.name(r.candidate_id))} · ${e(t.factor)} ${num(t.value)}<small>이 감점만으로 최종 선택이 바뀌었다는 뜻은 아닙니다.</small>${t.fact_ids.map(id=>`<button class="cf-link" data-bh-fact="${e(id)}">${e(id)} 후기 근거</button>`).join('')}</li>`).join('')}</ul></details>`;
 const obs=ctx.food_observation,observationLabel={LINKED_PREFERENCE:'기존 음식 선호·비선호 연결 있음',UNOBSERVED_IN_ACCEPTED_INPUT:'특정 음식 취향 미관측 — 간접 성향과 상황은 별도로 사용',FOOD_EVIDENCE_UNMAPPED:'음식 관련 근거가 있으나 메뉴 연결 미확정'}[obs?.status];
 const g=selected?.general_food_evidence;
 const gLabel={MEAL_TIME_HEDONIC_INTERACTION:'기존 공통 음식 항 × 식사 시간대 보완',REPEATED_VENUE_EXPERIMENT:'같은 업장 반복 보완',REPEATED_FOOD_CATEGORY_EXPERIMENT:'음식 범주 중복 보완'};
 const gReason={PERSONAL_FOOD_LINK_OR_UNRESOLVED_EVIDENCE_PROTECTED:'개인 음식 근거 또는 연결 미확정 근거 보호',SOURCE_LINKED_NEGATIVE_EVIDENCE_PROTECTED:'후기에 연결된 부정 기여 우선',NOT_A_FULL_MEAL:'주 식사가 아님',NO_NON_DUPLICATED_APPLICABLE_TERM:'중복 없이 적용할 보완 항 없음'};
 const general=g?.applied?`<p><b>실험 정책 ${e(g.policy)} · ${num(g.delta)}</b> — 선택 전에 적용. 수치는 논문의 추정계수가 아닌 HILLINK 실험 가정입니다.</p><ul>${g.components.map(z=>`<li>${e(gLabel[z.factor]||z.factor)}: ${num(z.delta)}${z.limitation?`<small>${e(z.limitation)}</small>`:''}</li>`).join('')}</ul>${(g.sources||[]).map(s=>`<p><a href="${e(s.url)}" target="_blank" rel="noopener">${e(s.title)}</a> · 일반 행동 연구<br><small>${e(s.sample_or_unit)} · ${e(s.not_applicable)}</small></p>`).join('')}`:`<p>${g?'실험 정책 '+e(g.policy)+' — 적용하지 않음: '+e(gReason[g.reason]||g.reason):'이 실행에는 일반 행동·산업 통계 보완값이 기록되지 않았습니다.'}</p>`;
 const candidates=x.rawCands.slice().sort((a,b)=>(b.final_with_lookahead??b.final_score??-Infinity)-(a.final_with_lookahead??a.final_score??-Infinity));
 const venueSeen=new Set(),top=candidates.filter(r=>{if(r.world_allowed===false)return false;const v=r.service_contract?.venue_id||r.candidate_id;if(venueSeen.has(v))return false;venueSeen.add(v);return true;}).slice(0,3);
 const alternative=candidates.find(r=>r.world_allowed!==false&&r.candidate_id!==chosen.final);
 const primary=new Set([chosen.final,chosen.rule,alternative?.candidate_id,...top.map(r=>r.candidate_id)]);
 const rowHTML=r=>{const z=split(r,x.decision?.packet?.kind==='PLANNER'),name=r.candidate_label||x.name(r.candidate_id);return `<tr${(r._menuSelected||r.candidate_id===chosen.final)?' class="selected"':''}><th>${e(name)}${(r._menuSelected||r.candidate_id===chosen.final)?' · 최종 채택':r.candidate_id===chosen.rule?' · 규칙 선택':''}</th><td>${num(z.base)}</td><td>${num(z.personal)}</td><td>${num(z.context)}</td><td>${num(z.general)}</td><td>${num(z.lookahead)}</td><td>${num(z.total)}</td><td>${r.world_allowed===false?'제외: '+e(String(r.block_reason||'이용 조건 미충족').replace(/RESEARCH_ACTUAL_ARRIVAL_EXCEEDS_EXISTING_TIME_LIMIT/g,'도착·이용 시간 제한').replace(/\b[A-Z][A-Z0-9_]{5,}\b/g,'상세 이용 조건').replace(/(\s*·\s*상세 이용 조건)+/g,' · 상세 이용 조건')):z.reconciled?'합계 일치':`분해 확인 필요${z.residual==null?'':' · 차이 '+num(z.residual)}`}</td></tr>`;};
 const table=rs=>`<div class="dc-table"><table><thead><tr><th>후보</th><th>기본·공통</th><th>개인</th><th>상황 가감</th><th>일반 보완</th><th>후속 가치</th><th>최종</th><th>검사·조건</th></tr></thead><tbody>${rs.map(rowHTML).join('')}</tbody></table></div>`;
 const compactTable=rs=>`<div class="dc-table ev-candidate-summary"><table><thead><tr><th>후보</th><th>개인 기여</th><th>상황 가감</th><th>최종 점수</th></tr></thead><tbody>${rs.map(r=>{const z=split(r);return `<tr class="${r.candidate_id===chosen.final?'selected':''}"><th>${e(r.candidate_label||x.name(r.candidate_id))}${r.candidate_id===chosen.final?' · 채택':''}</th><td>${num(z.personal)}</td><td>${num(z.context)}</td><td><b>${num(z.total)}</b></td></tr>`;}).join('')}</tbody></table></div><p class="dc-note">개인·상황은 전체 점수의 일부입니다. 기본·공통, 일반 보완, 후속 가치를 포함한 전체 분해는 아래에서 확인합니다.</p>`;
 const dlv=candidates.find(r=>r.price_reference||r.candidate_id==='EXTERNAL_DELIVERY'),dlvOut=((x.decision&&x.decision.packet&&x.decision.packet.catalog_excluded_candidates)||[]).some(z=>z.venue_id==='EXTERNAL_DELIVERY');
 const deliveryNote=dlv?`<p class="dc-note"><b>외부 배달</b> — 실제 배달 가격: 미확인 · 점수 계산 가격: ${dlv.price_reference?`경쟁 가능한 호텔 저녁의 최저가(1인 ${Number(dlv.price_reference.per_person_krw).toLocaleString('ko-KR')}원 · ${e(dlv.price_reference.reference_label)})를 사용한 가상 비교 기준`:'기록 없음'} · 고객 외부 지출: 금액 미상 · 호텔 L5~L1 매출: 0원</p>`:dlvOut?'<p class="dc-note"><b>외부 배달</b> — 같은 시각 비교할 호텔 저녁이 없어 후보에서 제외(엔진 비교 기준 부재)</p>':'';
 const candidateHTML=candidates.length?compactTable(candidates.filter(r=>primary.has(r.candidate_id)))+`<details><summary>전체 ${candidates.length}개 후보·제외 사유</summary>${table(candidates)}</details><p class="dc-note">업장별 상위 후보와 최종·규칙 선택을 먼저 표시합니다. 표시는 소수점 반올림이며 합계 검사는 원본 수치를 사용합니다. 기본·공통에는 기존 시간·가격 등의 공통 항도 포함됩니다. 개인 값은 동일 상태 근거 제거 차이이며 인과효과 추정이 아닙니다. 추첨 경로의 개인 민감도는 합산하지 않습니다.</p>`:x.turnDecision?`<p>식사 전용 엔진: 선택 ${e(x.turnDecision.choice.product_label)} · ${num(x.turnDecision.choice.score)}. 전체 기록에서 실제 대안과 점수를 확인합니다.</p>`:`<p class="dc-defect">실제 선택에 대응하는 후보 기록 연결이 누락됐습니다. 자동 일정으로 분류하지 않습니다.</p>`;
 const review=x.review,mode=review?`검토 상태 ${e(review.decided_by||review.outcome)} · ${e(review.review_execution||review.execution_mode||'실행 출처는 원본 trace 확인')}`:x.sampling?'기존 가중치 추첨으로 채택. 최고 점수 후보를 반드시 고르는 정책이 아닙니다.':'기록된 후보 점수와 후속 가치를 비교한 선택입니다.';
 const best=candidates.find(r=>r.world_allowed!==false),gap=best&&candidates.find(r=>r.world_allowed!==false&&r.candidate_id!==best.candidate_id);
 const comparison=best&&!x.sampling?`규칙 비교 1위: ${e(best.candidate_label||x.name(best.candidate_id))}${gap?' · 다음 후보와 총점 차이 '+num((best.final_with_lookahead??best.final_score)-(gap.final_with_lookahead??gap.final_score)):''}`:'';
 const final=`<p><b>${e(raw.label)}</b></p><p>${comparison}</p>${chosen.adopted?`<p>저장된 검토의 규칙 선택 ${e(x.name(chosen.rule))} → 최종 ${e(x.name(chosen.final))}. 규칙 점수를 최종 채택 이유로 대체하지 않습니다.</p>`:''}<p>${mode}</p>${reason?.audit?.contributions?.length?`<p>RPG 설명에 사용한 항: ${reason.audit.contributions.map(t=>e(t.factor)).join(' · ')}</p>`:''}`;
 const selectedScore=selected?split(selected):null;
 const altScore=alternative?split(alternative):null,margin=selectedScore?.total!=null&&altScore?.total!=null?selectedScore.total-altScore.total:null;
 const reviewState=String(review?.decided_by||review?.outcome||'');
 const execution=String(review?.review_execution||review?.execution_mode||'');
 const method=/CACHE_MISS|NOT_RUN|SKIP|UNAVAILABLE/.test(reviewState+' '+execution)?'규칙 선택 · 검토 미실행':chosen.adopted?(/REPLAY|CACHE/i.test(execution)?'저장 검토 채택':'검토 채택 · 출처 상세 확인'):x.sampling?'기존 가중 선택':'규칙·후속 가치';
 const metrics=`<div class="ev-decision-metrics"><div><span>최종 점수</span><strong>${num(selectedScore?.total)}</strong></div><div><span>주요 비교 후보</span><b>${e(alternative?.candidate_label||'별도 기록 없음')}</b></div><div><span>비교 후보와 차이</span><strong>${margin==null?'비교 미기록':(margin>0?'+':'')+num(margin)}</strong></div><div><span>판단 방식</span><b>${method}</b></div></div>`;
 const differences=selectedScore?.reconciled&&altScore?.reconciled?`<p class="ev-score-difference">선택 후보 − 비교 후보: ${[['기본·공통','base'],['개인','personal'],['상황','context'],['일반 보완','general'],['후속 가치','lookahead']].map(([label,k])=>`${label} ${num(selectedScore[k]-altScore[k])}`).join(' · ')}. 표시값은 반올림이며 전체 차이는 원본 점수를 따릅니다.</p>`:'';
 const stages=[['②','당시 상황'],['③','개인 성향'],...(g?.applied?[['④','보완 근거']]:[]),['⑤','후보 비교'],['⑥','최종 선택']];
 const stageNav=`<nav class="ev-decision-stages" aria-label="판단 흐름">${stages.map(([id,label])=>`<button data-decision-scroll="${id}">${label}</button>`).join('<span aria-hidden="true">→</span>')}</nav>`;
 const summaryHead=head.replace('</div>',metrics+'</div>');
 const menu=x.scene?.basis?.menu_decision;
 const menuHTML=menu?.candidates?.length?`<details><summary>업장 선택 이후 실제 메뉴 비교 ${menu.candidates.length}개</summary><p>업장 선택과 별도로 기록된 주문 전 메뉴 결정입니다.</p>${table(menu.candidates.map(c=>({...c,_menuSelected:c.candidate_id===menu.selected,candidate_label:c.sku_contract?.label||c.candidate_id,final_score:c.score,service_contract:c.sku_contract})))}</details>`:'';
 const rows=m.rows||[],paid=rows.reduce((s,r)=>s+(Number(r.paid_krw)||0),0),receipt=rows.length?`<ul>${rows.map(r=>`<li>${e(r.product)} · ${r.unit_price_krw==null?'단가 미기록':Number(r.unit_price_krw).toLocaleString()+'원'} × ${e(r.quantity??'수량 미기록')} · ${Number(r.paid_krw||0).toLocaleString()}원 <small>${e(typeof revTypeLabel==='function'?revTypeLabel(r)+' · 시뮬레이션 원장':r.purchase_status||'거래 구분 미기록')}</small></li>`).join('')}</ul><small>할인·포함 혜택·구성품은 원장 값으로 표시합니다. 자세한 가격·수량·거래 ID는 아래 원본 기록에서 확인합니다.</small><b>이 행동의 원장 합계 ${paid.toLocaleString()}원</b>`:'<p>이 행동에 연결된 구매 거래가 없습니다.</p>';
 return `<div class="dc-page">${navHTML}${summaryHead}${stageNav}${kind==='MISSING'?'<p class="dc-defect">판단 연결 결함: 이유를 임의로 보완하지 않습니다.</p>':''}${section('②','고객의 당시 상황',state)}${section('③','개인 후기와 성향',(observationLabel?'<p>'+e(observationLabel)+'</p>':'')+personalHTML)}${g?.applied?section('④','실제 적용된 일반 행동·통계 보완',general):''}${section('⑤','후보 비교',candidateHTML+deliveryNote+differences+final)}${section('⑥','최종 선택과 소비',receipt+(root.bhMealBasketHTML?root.bhMealBasketHTML(selected,m.rows||[]):'')+menuHTML)}${audit}</div>`;
};
root.hlProfileEvidenceTabs=function(id){
 const host=document.querySelector('.pv3-profile'),hero=host?.querySelector('.lb-hero');if(!hero||host.querySelector('[data-review-tabs]'))return;
 const p=libP(id),fx=p?.engine?.facts||{},related=[...LIBV.hl],rows=Object.entries(fx).filter(([,f])=>!f.hidden&&f.gist&&!(typeof LIB_SENS!=='undefined'&&LIB_SENS.test(f.gist))).sort(([a],[b])=>related.includes(b)-related.includes(a));
 const tab=document.createElement('nav');tab.dataset.reviewTabs='1';tab.setAttribute('role','tablist');tab.innerHTML='<button class="cf-btn" data-profile-view="profile" role="tab">고객 프로필</button><button class="cf-btn" data-profile-view="reviews" role="tab">후기 근거</button>';hero.after(tab);
 const review=document.createElement('section');review.className='dc-reviews';review.innerHTML=`<h3>후기 근거</h3><p>현재 장면 연결 Fact ${related.length}개를 먼저 표시합니다. 아래 추출 요약은 원문 그대로의 인용과 구분하며, 성향 해석은 프로필 탭에서 확인합니다.</p><label>후기 검색 <input data-review-search placeholder="후기 요약 또는 Fact ID"></label><p>${rows.length}개 전체 후기 Fact</p><ul>${rows.map(([key,f])=>`<li data-review-fact="${e(key)}"><small>${related.includes(key)?'현재 장면 연결 · ':''}후기 추출 요약</small><p>${e(f.gist)}</p>${libA(libUrl(f.post),'원문 보기 ↗','sm')||'<small>연결 가능한 원문 URL 미확인</small>'}</li>`).join('')}</ul>`;tab.after(review);
 const overview=[...host.children].filter(el=>![hero,tab,review].includes(el)&&!el.classList.contains('lb-crumb'));
 const apply=t=>{review.hidden=t!=='reviews';overview.forEach(el=>el.hidden=t==='reviews');tab.querySelectorAll('button').forEach(b=>{b.setAttribute('aria-selected',String(b.dataset.profileView===t));});};
 tab.querySelectorAll('button').forEach(b=>b.onclick=()=>{const q=new URLSearchParams(location.hash.split('?')[1]||'');q.set('tab',b.dataset.profileView);history.replaceState(null,'',location.hash.split('?')[0]+'?'+q);apply(b.dataset.profileView);});
 review.querySelector('input').oninput=ev=>{const q=ev.target.value.toLowerCase();review.querySelectorAll('li').forEach(li=>li.hidden=!(li.textContent+' '+li.dataset.reviewFact).toLowerCase().includes(q));};
 apply(new URLSearchParams(location.hash.split('?')[1]||'').get('tab')==='reviews'?'reviews':'profile');
};
document.addEventListener('click',ev=>{const stage=ev.target.closest?.('[data-decision-scroll]');if(stage){document.getElementById('decision-step-'+stage.dataset.decisionScroll)?.scrollIntoView({block:'start',behavior:'smooth'});return;}const b=ev.target.closest?.('[data-review-all]');if(!b)return;ev.preventDefault();bhFromScene(b.dataset.reviewAll,Number(b.dataset.reviewScene),{reviewOnly:true});});
})(typeof window!=='undefined'?window:globalThis);
