function runtimeCandidatePriceText(ledger){
 if(!ledger||!['live_engine','stored_demo'].includes(ledger.source)||!ledger.run_id)return null;
 const current=(ledger.source==='stored_demo'?'저장 시연 ':'현재 실행 ')+ledger.run_id.slice(0,8);
 const classes=ledger.price_class_aggregates&&ledger.price_class_aggregates.classes;
 if(!classes)return current+' · 가격 등급별 분리 기록 없음 · 해당 원장의 기존 가격 유지';
 const labels={OFFICIAL:'공식 가격',EXISTING_REFERENCE:'기존 참고',COMPARABLE_ESTIMATE:'비교 추정',SIMULATION_ASSUMPTION:'시뮬레이션 가정',LEGACY_OR_INCLUDED:'포함·기존 분류'};
 return current+' · 전체 가상금액 '+Number(ledger.totals.paid_krw).toLocaleString('ko-KR')+'원 · '+Object.entries(classes).map(([k,v])=>(labels[k]||k)+' '+Number(v.amount_krw||0).toLocaleString('ko-KR')+'원').join(' / ')+' · 실제 확정 매출 아님';
}
// Explicit local candidate mode; saved demonstrations and default requests are preserved.
(function(){
'use strict';
const originalFetch=window.fetch.bind(window);let enabled=false,cap=null;
const panel=document.createElement('section');panel.id='hlRuntimeCandidate';panel.style.cssText='position:relative;flex:none;font:12px/1.5 system-ui;color:#243b31';
panel.innerHTML='<label><input id="hlCandidateEnabled" type="checkbox" disabled> 통합 상품·선택 검토 사용</label><p id="hlCandidateStatus" role="status">지원 조건 확인 중</p>';
const tools=document.createElement('section');tools.id='hlRuntimeTools';tools.appendChild(panel);
const status=panel.querySelector('#hlCandidateStatus');
const prices=document.createElement('fieldset');prices.hidden=true;
prices.innerHTML='<legend>새 시나리오 상품 가격·할인</legend><label>상품 <select data-sku aria-label="가격 변경 상품"></select></label><label>단가(원) <input data-price aria-label="시나리오 단가" type="number" min="1" step="1" placeholder="기준 가격 유지"></label><label>할인율(%) <input data-discount aria-label="상품 할인율" type="number" min="0" max="100" step="0.1" value="0"></label><button type="button" class="cf-btn cf-sm" data-set>적용</button><button type="button" class="cf-btn cf-sm" data-clear>전체 해제</button><p data-note role="status">다음 새 계산에 적용 · 실제 확정 가격 아님</p>';
const drawer=document.createElement('details');drawer.id='hlPriceEditor';drawer.innerHTML='<summary>SKU 가격·할인</summary>';drawer.appendChild(prices);tools.appendChild(drawer);prices.querySelectorAll('label').forEach(e=>e.style.cssText='display:block;margin:8px 0');prices.querySelectorAll('input,select').forEach(e=>e.style.cssText='width:100%;box-sizing:border-box');
const edits={price_overrides:{},discount_percent:{}};
originalFetch('/static/sku_scenario_options.json').then(r=>r.json()).then(data=>{const select=prices.querySelector('[data-sku]');for(const p of [...data.products,...(data.scenario_products||[])]){const option=document.createElement('option');option.value=p.sku_id;const unconfirmed=p.price_confirmed===false;option.textContent=p.sku_id+' · '+p.label+' · '+(unconfirmed?'미확인 참고값 '+Number(p.unit_price_krw).toLocaleString()+'원 · 비적용(가격 미정, 청구 안 함)':p.unit_price_krw.toLocaleString()+'원/'+p.billing_unit);if(unconfirmed){option.disabled=true;option.dataset.priceStatus='UNCONFIRMED_REFERENCE_NOT_APPLIED';}select.append(option);}prices.hidden=false;});
prices.querySelector('[data-set]').onclick=()=>{const sku=prices.querySelector('[data-sku]').value,raw=prices.querySelector('[data-price]').value,percent=Number(prices.querySelector('[data-discount]').value);if(!sku||raw!==''&&(!Number.isSafeInteger(Number(raw))||Number(raw)<=0)||!Number.isFinite(percent)||percent<0||percent>100){prices.querySelector('[data-note]').textContent='단가·할인율을 확인해주세요.';return;}if(raw==='')delete edits.price_overrides[sku];else edits.price_overrides[sku]=Number(raw);edits.discount_percent[sku]=percent;prices.querySelector('[data-note]').textContent=Object.keys(edits.discount_percent).length+'개 상품 설정 · 통합 상품·선택 검토 사용 시 다음 생성에 적용';};
function clearPrices(){edits.price_overrides={};edits.discount_percent={};prices.querySelector('[data-price]').value='';prices.querySelector('[data-discount]').value='0';prices.querySelector('[data-note]').textContent='상품 가격 설정 해제';}
prices.querySelector('[data-clear]').onclick=clearPrices;document.addEventListener('click',e=>{if(e.target.closest('#agReset'))clearPrices();});

originalFetch('/api/runtime/capabilities').then(r=>r.json()).then(c=>{cap=c;panel.hidden=!c.common_candidate;panel.querySelector('input').disabled=!c.common_candidate;status.textContent=c.common_candidate?'통합 상품 카탈로그 · 선택적 검토 '+c.hybrid_mode+' · 기본값 유지':'기본 엔진 · 통합 후보는 이 환경에서 꺼져 있습니다.';}).catch(()=>{status.textContent='기본 엔진 · 후보 설정을 확인하지 못했습니다.';});
const originalSituationRender=situationRender;
situationRender=function(...args){tools.remove();const result=originalSituationRender.apply(this,args);const operations=document.querySelector('.st-operations');if(operations){operations.appendChild(tools);}return result;};
document.addEventListener('keydown',e=>{if(e.key==='Escape')drawer.open=false;});
const observer=new MutationObserver(()=>{if(!document.querySelector('.st-operations')||!document.querySelector('main.library'))drawer.open=false;});observer.observe(document.querySelector('main'),{attributes:true,attributeFilter:['class'],childList:true,subtree:false});
panel.querySelector('input').addEventListener('change',e=>{enabled=e.target.checked;});
function showPrice(ledger){const text=runtimeCandidatePriceText(ledger);if(text){status.textContent=text;status.dataset.ledgerRunId=ledger.run_id;}}
const remember=revRememberFlow;
revRememberFlow=function(flow,...rest){const result=remember.call(this,flow,...rest);if(flow)showPrice(flow.ledger);return result;};
const render=revRender;
revRender=function(...args){const result=render.apply(this,args);showPrice(REV.ledger);return result;};
const originalApi=api;
api=async function(path,body,...rest){
 if(enabled&&cap&&path==='/api/visit'&&body){
  body.behavior_engine='m4_c01';body.catalog_policy=cap.catalog_policy;
  body.catalog_options=structuredClone(body.catalog_options||{});for(const key of ['price_overrides','discount_percent'])body.catalog_options[key]={...(body.catalog_options[key]||{}),...edits[key]};
  if(cap.native_hybrid)body.hybrid_policy=cap.hybrid_policy;
 }
 return originalApi.call(this,path,body,...rest);
};
})();
