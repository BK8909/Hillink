/* Native replay/dry has no model answer; preserve the sealed v3 renderer bytes. */
(function(root){
'use strict';
function repair(html,review){
 if(!review)return html;
 const skipped=review.call&&review.call.skipped,mode=review.review_execution;
 const missing=['CACHE_MISS','REVIEW_NOT_RUN','REVIEW_ERROR'].includes(mode)||['replay_miss','dry'].includes(skipped);
 if(missing&&!review.llm){
  const causes={replay_miss:'응답 캐시 미일치',cache_policy_mismatch:'캐시 정책 불일치',cache_content_mismatch:'캐시 입력 불일치',dry:'질문 생성 전용 모드',authorization:'호출 승인 없음',budget:'호출 예산 제한'};
  const cause=causes[skipped]||'사용 가능한 검토 응답 없음',network=review.provider_call_performed||(review.call&&review.call.network_attempted);
  return html.replaceAll('LLM 검토 뒤 규칙 선택 유지','LLM 응답 없음 · 규칙 선택 유지')
   .replaceAll('LLM 검토 뒤 유지','LLM 응답 없이 규칙 선택 유지').replaceAll('LLM 검토 있음',cause+' · LLM 응답 없음')
   +'<p class="frp-note" data-native-review-unavailable="'+(skipped||mode)+'">실행 기록: '+cause+'. '+(network?'호출 시도 후 사용할 수 있는 응답을 받지 못해':'새 외부 모델 호출 없이')+' 규칙 선택을 유지했습니다. 최종 상품·원장 기록은 보존합니다.</p>';
 }
 if(mode==='SYNTHETIC_TEST')return html.replaceAll('LLM 검토','합성 시험 검토')+'<p class="frp-note" data-native-review-status="SYNTHETIC_TEST">합성 시험 응답입니다. 실제 외부 LLM 검토·품질 검증이 아닙니다.</p>';
 if(mode==='CACHE_REPLAY')return html+'<p class="frp-note" data-native-review-status="CACHE_REPLAY">저장된 LLM 판단 재생 · 새 외부 호출 없음'+(review.review_succeeded?'':' · 판단 검증 거부, 규칙 선택 유지')+'</p>';
 if(mode==='LIVE_REVIEW')return html+'<p class="frp-note" data-native-review-status="LIVE_REVIEW">실제 외부 검토 응답'+(review.review_succeeded?'':' · 판단 검증 거부')+'</p>';
 return html;
}
if(typeof module!=='undefined'&&module.exports)module.exports={repair};
if(typeof root.bhEvidenceHTML==='function'){
 const original=root.bhEvidenceHTML;
 root.bhEvidenceHTML=function(model,...rest){return repair(original.call(this,model,...rest),model&&model.raw&&model.raw.basis&&model.raw.basis.review);};
}
})(typeof window!=='undefined'?window:globalThis);
