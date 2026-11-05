const test=require('node:test'),assert=require('node:assert/strict');
const {repair}=require('../static/native_review_display.js');
const html='<section data-selection="final-1"><h3>LLM 검토 뒤 규칙 선택 유지</h3><p>LLM 검토 있음</p><p>LLM 검토 뒤 유지</p><code>tx-1</code></section>';
test('replay miss is not promoted to a completed LLM review; selection and transaction remain',()=>{
 const review={call:{skipped:'replay_miss'},llm:null,final:'final-1'},before=structuredClone(review),out=repair(html,review);
 assert.doesNotMatch(out,/LLM 검토 있음|LLM 검토 뒤/);assert.match(out,/응답 캐시 미일치/);assert.match(out,/외부 모델 호출 없이/);
 assert.match(out,/data-selection="final-1"/);assert.match(out,/<code>tx-1<\/code>/);assert.deepEqual(review,before);
});
test('dry is labeled as question generation; real cached or live judgments stay intact',()=>{
 assert.match(repair(html,{call:{skipped:'dry'},llm:null}),/질문 생성 전용 모드/);
 assert.equal(repair(html,{call:{cache_hit:true},llm:{choice:'final-1'}}),html);
 assert.equal(repair(html,{call:{cache_hit:false},llm:{choice:'final-1'}}),html);
 assert.equal(repair(html,null),html);
});

test('B boundary cache misses, stored responses and synthetic tests keep separate provenance',()=>{
 assert.match(repair(html,{review_execution:'CACHE_MISS',call:{skipped:'cache_policy_mismatch'},llm:null}),/캐시 정책 불일치/);
 const cached=repair(html,{review_execution:'CACHE_REPLAY',review_succeeded:true,call:{cache_hit:true},llm:{choice:'final-1'}});
 assert.match(cached,/저장된 LLM 판단 재생/);assert.match(cached,/새 외부 호출 없음/);
 const synthetic=repair(html,{review_execution:'SYNTHETIC_TEST',call:{fixture:true},llm:{choice:'final-1'}});
 assert.match(synthetic,/합성 시험/);assert.doesNotMatch(synthetic,/LLM 검토 있음/);
 const error=repair(html,{review_execution:'REVIEW_ERROR',provider_call_performed:true,call:{error:'TransportError'},llm:null});
 assert.match(error,/호출 시도 후/);assert.doesNotMatch(error,/새 외부 모델 호출 없이/);
});
