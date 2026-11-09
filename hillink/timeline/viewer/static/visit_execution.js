/* Bind existing visit controls to the product engine; no new navigation. */
(function(root){
'use strict';
const POLICY='LLM_AUTONOMOUS_CUSTOMER_V16';        // stored runs: exact replay under the policy they were recorded with
const LIVE_POLICY='LLM_AUTONOMOUS_CUSTOMER_V19LS'; // product LIVE default (2026-11-07): evidence stance, day-end review, selection diagnostics
const PREVIOUS_LIVE_POLICY='LLM_AUTONOMOUS_CUSTOMER_V17';   // kept: only when the page names it (?policy=LLM_AUTONOMOUS_CUSTOMER_V17)
const IMPROVED_POLICY='LLM_AUTONOMOUS_CUSTOMER_V19LS_INT5M';  // improved selectable policy (2026-11-09 final A/B: INT4 + meal context); V19LS stays the default
const PREVIOUS_IMPROVED_POLICY='LLM_AUTONOMOUS_CUSTOMER_V19LS_INT4';  // 2026-11-08 improved policy: its saved visits replay under it
const IMPROVED_POLICIES=[IMPROVED_POLICY,PREVIOUS_IMPROVED_POLICY];
const EXPERIMENT_POLICIES=['LLM_AUTONOMOUS_CUSTOMER_V18','LLM_AUTONOMOUS_CUSTOMER_V18B','LLM_AUTONOMOUS_CUSTOMER_V18BM','LLM_AUTONOMOUS_CUSTOMER_V18BD'];   // M4 shortlist experiments: only when a request names it (?policy=…)
const RESEARCH_POLICIES=['LLM_AUTONOMOUS_CUSTOMER_V19LS_P2','LLM_AUTONOMOUS_CUSTOMER_V19LS_HP1','LLM_AUTONOMOUS_CUSTOMER_V19LS_HP1B','LLM_AUTONOMOUS_CUSTOMER_V19LS_MEM1'];   // research on V19LS: only when a request names it
const SELECTABLE=[PREVIOUS_LIVE_POLICY,IMPROVED_POLICY,PREVIOUS_IMPROVED_POLICY,...EXPERIMENT_POLICIES,...RESEARCH_POLICIES];
const POLICIES=[POLICY,LIVE_POLICY,...SELECTABLE];
const VERSION_NOTE={[POLICY]:'과거 판단 기준(V16) · 조기 종료 검증 이전',[LIVE_POLICY]:'현재 판단 기준(V19-LS) · 근거 성격 표시 · 하루 종료 재검토',[PREVIOUS_LIVE_POLICY]:'이전 판단 기준(V17)',
 [IMPROVED_POLICY]:'개선형 판단 기준 · 앞선 날 기억 · 저녁 객실 체류와 취침 구분 · 식사 후보 개선 · 경량 입력',[PREVIOUS_IMPROVED_POLICY]:'이전 개선형 판단 기준(11/08) · 저장된 개선형 방문의 기준',
 LLM_AUTONOMOUS_CUSTOMER_V18:'실험 기준(V18) · 규칙 선별 후 LLM 선택',LLM_AUTONOMOUS_CUSTOMER_V18B:'실험 기준(V18-B) · 후보 관련 근거만',LLM_AUTONOMOUS_CUSTOMER_V18BM:'실험 기준(V18-C) · B 입력 · reasoning medium',LLM_AUTONOMOUS_CUSTOMER_V18BD:'실험 기준(V18-D) · B 입력 · 최소 출력',LLM_AUTONOMOUS_CUSTOMER_V19LS_P2:'연구 기준(V19-LS P2) · 일부 인원 조식 후보 · 식사량 1회 재검토'};
const SHORT={[IMPROVED_POLICY]:'개선형',[PREVIOUS_IMPROVED_POLICY]:'개선형',LLM_AUTONOMOUS_CUSTOMER_V19LS_HP1:'V19-LS HP1 연구',LLM_AUTONOMOUS_CUSTOMER_V19LS_HP1B:'V19-LS HP1b 연구',LLM_AUTONOMOUS_CUSTOMER_V19LS_MEM1:'V19-LS MEM1 연구',[POLICY]:'V16',[LIVE_POLICY]:'V19-LS',[PREVIOUS_LIVE_POLICY]:'V17',LLM_AUTONOMOUS_CUSTOMER_V18:'V18 실험',LLM_AUTONOMOUS_CUSTOMER_V18B:'V18-B 실험',LLM_AUTONOMOUS_CUSTOMER_V18BM:'V18-C 실험',LLM_AUTONOMOUS_CUSTOMER_V18BD:'V18-D 실험',LLM_AUTONOMOUS_CUSTOMER_V19LS_P2:'V19-LS P2 연구'};
function experimentPolicy(){try{const p=new URLSearchParams(root.location?.search||'').get('policy');return SELECTABLE.includes(p)?p:null;}catch(e){return null;}}
// '개선형' is one more entry of the same 행동 판단 list: a new LIVE judgment with the improved policy's engine settings.
function isLive(mode){return mode==='live'||mode==='live_improved';}
function isImproved(policy){return IMPROVED_POLICIES.includes(policy);}
function modeOf(request){return request?.judgment_mode==='live'&&isImproved(request?.hybrid_policy)?'live_improved':(request?.judgment_mode||null);}
function request(value,mode='replay',policy){
 if(!['rules','replay','live','live_improved'].includes(mode))throw Error('판단 모드를 선택해 주세요.');
 const out={...value,judgment_mode:mode==='live_improved'?'live':mode};
 if(mode==='rules'){delete out.hybrid_policy;return out;}
 // Replay keeps the policy the stored run names (default V16; ?policy= may name a selectable one for a recorded run);
 // a new LIVE judgment uses the current policy, or the improved one when that entry was chosen.
 const chosen=mode==='live_improved'?IMPROVED_POLICY:mode==='live'?(experimentPolicy()||LIVE_POLICY):(POLICIES.includes(policy)?policy:POLICIES.includes(out.hybrid_policy)?out.hybrid_policy:(experimentPolicy()||POLICY));
 Object.assign(out,{behavior_engine:'m4_c01',catalog_policy:'C01_HOTEL_CATALOG_V1',hybrid_policy:chosen,simulation_mode:out.simulation_mode||'independent'});
 return out;
}
// The request fields that decide an execution. A stored judgment can be replayed only for exactly these values.
const RUN_KEYS=['personas','duration','event_mode','seed','start_date','environment','visit_conditions','package_id','scenario','behavior_engine','catalog_policy','catalog_options','hybrid_policy','simulation_mode'];
const RUN_KEY_LABEL={personas:'고객',duration:'방문 기간',event_mode:'행사',seed:'시드',start_date:'방문일',environment:'도착 시각·날씨',visit_conditions:'건물·인원·주문',package_id:'객실 상품',scenario:'행사 조건',behavior_engine:'행동 엔진',catalog_policy:'상품 계산',catalog_options:'상품 설정',hybrid_policy:'판단 기준',simulation_mode:'실행 방식'};
function canon(v){if(v===undefined||v===null||v==='')return undefined;if(Array.isArray(v))return v.map(canon);if(typeof v==='object'){const o={};for(const k of Object.keys(v).sort()){const c=canon(v[k]);if(c!==undefined&&!(c&&typeof c==='object'&&!Array.isArray(c)&&!Object.keys(c).length))o[k]=c;}return o;}return v;}
function runFields(r){const o={};for(const k of RUN_KEYS){let v=r?.[k];if(k==='simulation_mode'&&v==null)v='independent';if(k==='personas'&&Array.isArray(v))v=[...v].sort();const c=canon(v);if(c!==undefined&&!(c&&typeof c==='object'&&!Array.isArray(c)&&!Object.keys(c).length))o[k]=c;}return o;}
// Differences between two requests as readable field names; [] = the same execution conditions.
function runDiff(a,b){const x=runFields(a),y=runFields(b);return RUN_KEYS.filter(k=>JSON.stringify(x[k])!==JSON.stringify(y[k])).map(k=>RUN_KEY_LABEL[k]||k);}
const REPLAY_NEEDS_SAVED='저장된 판단 재현은 저장된 실행 조건을 불러와 그 조건 그대로 실행할 때만 가능합니다. 새 조건은 ‘규칙 계산 (AI 없음)’ 또는 실시간 AI 판단을 선택해 주세요.';
function replayChanged(diff){return `불러온 저장 조건에서 ${diff.join(' · ')}이(가) 바뀌어 저장된 판단을 재생할 수 없습니다. 저장 조건으로 되돌리거나 다른 판단 방식을 선택해 주세요.`;}
const LIVE_REASON={LIVE_APPROVAL_REQUIRED:'서버가 실시간 호출 승인 없이 시작됨(저장 재생·규칙 전용 검수 서버)',EXTERNAL_CALL_NOT_AUTHORIZED:'외부 API 호출이 꺼져 있음',EXISTING_SHARED_BUDGET_REQUIRED:'비용 원장이 연결되지 않음',APPROVED_LIMIT_REQUIRED:'승인된 호출·비용 상한이 설정되지 않음',EXISTING_JOURNAL_CALL_EXTENSION_APPROVAL_REQUIRED:'호출 상한 증액 승인 기록이 없음',CALL_LIMIT:'승인된 호출 상한에 도달함',USD_LIMIT:'승인된 비용 상한에 도달함',INVALID_EXISTING_BUDGET:'비용 원장을 읽지 못함',API_CREDENTIAL_MISSING:'서버에 API 인증 정보가 없음',LOCAL_REVIEW_ONLY:'로컬 검수 환경에서만 사용 가능'};
// One server capability read per page; live availability is decided by the server, never assumed.
let capability=null;
function capabilities(){if(!capability)capability=root.fetch('/api/runtime/capabilities').then(r=>{if(!r.ok)throw Error('capabilities unavailable');return r.json();}).catch(e=>{capability=null;throw e;});return capability;}
function version(policy){return VERSION_NOTE[policy]||(policy?String(policy):'판단 기준 미기록');}
function options(mode){return [['replay','저장된 판단 재현 (무과금)'],['live','실시간 AI 판단 (API 호출)'],['live_improved','실시간 AI 판단 · 개선형 (API 호출)'],['rules','규칙 계산 (AI 없음)']].map(([v,t])=>`<option value="${v}"${v===mode?' selected':''}>${t}</option>`).join('');}
function label(result){const j=result?.judgment;if(!j)return '판단 출처는 개별 실행 기록에서 확인';
 const old=j.policy===LIVE_POLICY?'':` · ${SHORT[j.policy]||'기준 미기록'} 기준`;
 return ({rules:'규칙 계산 · AI 판단 없음',replay:`저장된 판단 재현 · 새 호출 0회${j.policy===POLICY?' · 과거 판단 기준':old}`,live:`실시간 AI 판단${old}`,BLOCKED:'판단 미완료 · 규칙 계산으로 대체하지 않음'})[j.actual]||'판단 출처 미확인';}
// Availability notice and run guard. `check` (optional) returns a message that blocks the run before any request is
// sent (e.g. a replay without matching saved conditions); live availability comes from the server.
function bindAvailability(select,notice,button,check){
 let revision=0;
 async function refresh(){
  const current=++revision;
  let message=check?check(select.value):null,block=!!message;
  if(!message&&isLive(select.value)){
   try{
    const status=await capabilities();
    if(current!==revision)return;
    if(status.judgment_modes?.live===false){message=`이 서버에서는 실시간 AI 판단(API 호출)을 사용할 수 없습니다 — ${LIVE_REASON[status.live_reason]||'호출 권한·예산 미설정'}. 유료 호출 없이 차단했습니다. 규칙 계산이나 저장된 판단 재현을 선택해 주세요.`;block=true;}
    else if(status.judgment_modes?.live!==true)throw Error('live status unknown');
   }catch(error){
    if(current!==revision)return;
    message='서버의 실시간 AI 판단 사용 가능 여부를 확인하지 못해 실행을 막았습니다.';block=true;
   }
  }
  if(current!==revision)return;
  notice.textContent=message||'';notice.hidden=!message;
  if(button){button.dataset.modeBlocked=block?'1':'';button.disabled=block||button.dataset.busy==='1';}
 }
 select.addEventListener('change',refresh);refresh();
 return refresh;
}
const api={request,options,label,version,bindAvailability,isLive,modeOf,runDiff,runFields,capabilities,REPLAY_NEEDS_SAVED,replayChanged,POLICY,LIVE_POLICY,PREVIOUS_LIVE_POLICY,IMPROVED_POLICY,PREVIOUS_IMPROVED_POLICY,IMPROVED_POLICIES,isImproved,POLICIES,EXPERIMENT_POLICIES,RESEARCH_POLICIES,SELECTABLE};root.HLVisitExecution=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
