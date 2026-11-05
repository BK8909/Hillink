/* Bind existing visit controls to the product engine; no new navigation. */
(function(root){
'use strict';
const POLICY='LLM_AUTONOMOUS_CUSTOMER_V16';
function request(value,mode='replay'){
 if(!['rules','replay','live'].includes(mode))throw Error('판단 모드를 선택해 주세요.');
 const out={...value,judgment_mode:mode};
 if(mode==='rules')delete out.hybrid_policy;
 else Object.assign(out,{behavior_engine:'m4_c01',catalog_policy:'C01_HOTEL_CATALOG_V1',hybrid_policy:POLICY,simulation_mode:out.simulation_mode||'independent'});
 return out;
}
function options(mode){return [['replay','저장된 LLM 판단 (무과금)'],['live','새로운 LLM 판단 (API 호출)'],['rules','규칙 계산 (LLM 없음)']].map(([v,t])=>`<option value="${v}"${v===mode?' selected':''}>${t}</option>`).join('');}
function label(result){const j=result?.judgment;return j?({rules:'규칙 계산 · LLM 판단 없음',replay:'V16 · 저장 응답 Replay · 현재 유료 호출 0회',live:'V16 · 새로운 LLM 판단',BLOCKED:'판단 미완료 · 규칙 대체 없음'})[j.actual]||'판단 출처 미확인':'판단 출처는 개별 실행 기록에서 확인';}
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
   if(status.judgment_modes?.live===false)notice.textContent='현재 서버에서 LLM 실호출을 사용할 수 없습니다.';
   else if(status.judgment_modes?.live!==true)throw Error('live status unknown');
  }catch(error){
   if(current!==revision)return;
   notice.textContent='현재 서버의 LLM 실호출 상태를 확인하지 못했습니다.';
  }
  notice.hidden=!notice.textContent;
 }
 select.addEventListener('change',refresh);refresh();
}
const api={request,options,label,bindAvailability,POLICY};root.HLVisitExecution=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
