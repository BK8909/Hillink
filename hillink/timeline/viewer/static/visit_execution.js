/* Bind existing visit controls to the product engine; no new navigation. */
(function(root){
'use strict';
const POLICY='LLM_AUTONOMOUS_CUSTOMER_V16';        // stored runs: exact replay under the policy they were recorded with
const LIVE_POLICY='LLM_AUTONOMOUS_CUSTOMER_V19LS'; // product LIVE default (2026-11-07): evidence stance, day-end review, selection diagnostics
const PREVIOUS_LIVE_POLICY='LLM_AUTONOMOUS_CUSTOMER_V17';   // kept: only when the page names it (?policy=LLM_AUTONOMOUS_CUSTOMER_V17)
const EXPERIMENT_POLICIES=['LLM_AUTONOMOUS_CUSTOMER_V18','LLM_AUTONOMOUS_CUSTOMER_V18B','LLM_AUTONOMOUS_CUSTOMER_V18BM','LLM_AUTONOMOUS_CUSTOMER_V18BD'];   // M4 shortlist experiments: only when a request names it (?policy=…)
const RESEARCH_POLICIES=['LLM_AUTONOMOUS_CUSTOMER_V19LS_P2'];   // research on V19LS: only when a request names it
const SELECTABLE=[PREVIOUS_LIVE_POLICY,...EXPERIMENT_POLICIES,...RESEARCH_POLICIES];
const POLICIES=[POLICY,LIVE_POLICY,...SELECTABLE];
const VERSION_NOTE={[POLICY]:'과거 판단 기준(V16) · 조기 종료 검증 이전',[LIVE_POLICY]:'현재 판단 기준(V19-LS) · 근거 성격 표시 · 하루 종료 재검토',[PREVIOUS_LIVE_POLICY]:'이전 판단 기준(V17)',
 LLM_AUTONOMOUS_CUSTOMER_V18:'실험 기준(V18) · 규칙 선별 후 LLM 선택',LLM_AUTONOMOUS_CUSTOMER_V18B:'실험 기준(V18-B) · 후보 관련 근거만',LLM_AUTONOMOUS_CUSTOMER_V18BM:'실험 기준(V18-C) · B 입력 · reasoning medium',LLM_AUTONOMOUS_CUSTOMER_V18BD:'실험 기준(V18-D) · B 입력 · 최소 출력',LLM_AUTONOMOUS_CUSTOMER_V19LS_P2:'연구 기준(V19-LS P2) · 일부 인원 조식 후보 · 식사량 1회 재검토'};
const SHORT={[POLICY]:'V16',[LIVE_POLICY]:'V19-LS',[PREVIOUS_LIVE_POLICY]:'V17',LLM_AUTONOMOUS_CUSTOMER_V18:'V18 실험',LLM_AUTONOMOUS_CUSTOMER_V18B:'V18-B 실험',LLM_AUTONOMOUS_CUSTOMER_V18BM:'V18-C 실험',LLM_AUTONOMOUS_CUSTOMER_V18BD:'V18-D 실험',LLM_AUTONOMOUS_CUSTOMER_V19LS_P2:'V19-LS P2 연구'};
function experimentPolicy(){try{const p=new URLSearchParams(root.location?.search||'').get('policy');return SELECTABLE.includes(p)?p:null;}catch(e){return null;}}
function request(value,mode='replay',policy){
 if(!['rules','replay','live'].includes(mode))throw Error('판단 모드를 선택해 주세요.');
 const out={...value,judgment_mode:mode};
 if(mode==='rules'){delete out.hybrid_policy;return out;}
 // Replay keeps the policy the stored run names (default V16); a new LIVE judgment uses the current policy.
 const chosen=mode==='live'?(experimentPolicy()||LIVE_POLICY):(POLICIES.includes(policy)?policy:POLICIES.includes(out.hybrid_policy)?out.hybrid_policy:POLICY);
 Object.assign(out,{behavior_engine:'m4_c01',catalog_policy:'C01_HOTEL_CATALOG_V1',hybrid_policy:chosen,simulation_mode:out.simulation_mode||'independent'});
 return out;
}
function version(policy){return VERSION_NOTE[policy]||(policy?String(policy):'판단 기준 미기록');}
function options(mode){return [['replay','저장된 판단 재현 (무과금)'],['live','실시간 AI 판단 (API 호출)'],['rules','규칙 계산 (AI 없음)']].map(([v,t])=>`<option value="${v}"${v===mode?' selected':''}>${t}</option>`).join('');}
function label(result){const j=result?.judgment;if(!j)return '판단 출처는 개별 실행 기록에서 확인';
 const old=j.policy===LIVE_POLICY?'':` · ${SHORT[j.policy]||'기준 미기록'} 기준`;
 return ({rules:'규칙 계산 · AI 판단 없음',replay:`저장된 판단 재현 · 새 호출 0회${j.policy===POLICY?' · 과거 판단 기준':old}`,live:`실시간 AI 판단${old}`,BLOCKED:'판단 미완료 · 규칙 계산으로 대체하지 않음'})[j.actual]||'판단 출처 미확인';}
// Read-only availability notice; execution and budget checks remain server-owned.
function bindAvailability(select,notice){
 let revision=0;
 async function refresh(){
  const current=++revision;
  notice.hidden=true;notice.textContent='';
  if(select.value!=='live')return;
  try{
   const response=await root.fetch('/api/runtime/capabilities');
   if(!response.ok)throw Error('capabilities unavailable');
   const status=await response.json();
   if(current!==revision)return;
   if(status.judgment_modes?.live===false)notice.textContent='지금 서버에서는 실시간 AI 판단(API 호출)을 사용할 수 없습니다. 저장된 판단 재현이나 규칙 계산을 선택해 주세요.';
   else if(status.judgment_modes?.live!==true)throw Error('live status unknown');
  }catch(error){
   if(current!==revision)return;
   notice.textContent='서버의 실시간 AI 판단 사용 가능 여부를 확인하지 못했습니다.';
  }
  notice.hidden=!notice.textContent;
 }
 select.addEventListener('change',refresh);refresh();
}
const api={request,options,label,version,bindAvailability,POLICY,LIVE_POLICY,PREVIOUS_LIVE_POLICY,POLICIES,EXPERIMENT_POLICIES,RESEARCH_POLICIES,SELECTABLE};root.HLVisitExecution=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
