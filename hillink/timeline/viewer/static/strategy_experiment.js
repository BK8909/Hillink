// Display-only quote preview and serial, latest-request-wins execution. No order writes.
(function(root){'use strict';
function preview(flow,candidate,pct){
 const fail=reason=>({ok:false,reason,rows:[]});
 if(candidate.kind==='opening')return {ok:true,kind:'opening',rows:[]};
 if(![10,15,20].includes(pct))return fail('지원되는 할인율을 선택해 주세요.');
 const p=flow.visit?.hotel_price_snapshot?.products?.find(p=>p.sku_id===candidate.sku),opts=flow.request?.catalog_options||{};
 if(!p||!Number.isFinite(p.unit_price_krw)||p.unit_price_krw<=0||p.price_confirmed===false)return fail('이 실행에서 확인된 상품 가격이 없습니다.');
 const key=p.pricing_parent_sku_id||p.sku_id;
 if(key!==candidate.sku||opts.price_overrides?.[key]!=null)return fail('별도 가격 변경 또는 상위 가격 계약이 있어 이 할인 실험을 적용할 수 없습니다.');
 if(['NO_DISCOUNT_OR_POINTS','NO_ADDITIONAL_DISCOUNT'].includes(p.discount_policy))return fail('할인이 허용되지 않는 상품입니다.');
 let before=p.price_trace?.scenario_unit_price_before_discount_krw??p.unit_price_krw;
 if(!p.price_trace&&['COMPARABLE_ESTIMATE','SIMULATION_ASSUMPTION'].includes(p.price_tier)){
  const v=before*(opts.price_sensitivity_factor??1),i=Math.floor(v);before=v-i===.5?(i%2?i+1:i):Math.round(v); // existing Python model rounding
 }
 const oldPct=opts.discount_percent?.[key]||0,unit=Math.round(before*(100-pct)/100),oldUnit=Math.round(before*(100-oldPct)/100),rows=[],seen=new Set();
 for(const day of flow.visit_days?.map(d=>d.flow)||[flow])for(const [pid,plan] of Object.entries(day.plans||{}))for(const d of plan.m4?.decisions||[]){
  if(d.execution_status!=='EXECUTED'||!candidate.customers.includes(pid))continue;
  const packet=d.packet,decisionKey=pid+'|'+packet?.context_factors?.date+'|'+String(Math.floor(packet?.context_factors?.time/60)).padStart(2,'0')+':'+String(packet?.context_factors?.time%60).padStart(2,'0');
  if(!candidate.decisions.some(x=>x.key===decisionKey))continue;
  const raw=packet?.candidates?.find(c=>c.product_quote?.components?.length===1&&c.product_quote.components[0].sku_id===candidate.sku);if(!raw)continue;
  const id=pid+'|'+packet.packet_sha256;if(seen.has(id))continue;seen.add(id);
  const quote=raw.product_quote,line=quote.components[0],qty=line.billing_quantity;
  if(quote.included||raw.scoring_input_contract?.included)return fail('포함 혜택 계약이므로 유료 할인으로 다시 계산하지 않습니다.');
  if(!Number.isInteger(qty)||qty<=0||line.unit_price_krw!==oldUnit||quote.total_krw!==oldUnit*qty)return fail('원래 후보의 수량·단가·계약을 단순 할인 계산과 대조할 수 없습니다.');
  rows.push({customer:flow.ledger.receipts[pid]?.display_id||'고객',quantity:qty,party:raw.scoring_input_contract?.participant_count||null,unit:oldUnit,before:quote.total_krw,after:unit*qty,difference:quote.total_krw-unit*qty,oldPercent:oldPct,date:packet.context_factors.date});
 }
 return rows.length?{ok:true,sku:candidate.sku,label:p.label,unitLabel:p.source_unit||p.billing_unit,priceStatus:p.price_status,priceTier:p.price_tier,rows,pct,unchanged:oldPct===pct}:fail('선택 전 상품 후보의 정확한 주문 수량과 가격을 찾지 못했습니다.');
}
function latestRunner(execute,notify){
 let revision=0,pending=null,running=false,lastKey=null;
 async function drain(){
  if(running)return;running=true;
  while(pending){const job=pending;pending=null;const current=()=>job.revision===revision;
   try{const result=await execute(job.value,current);if(current())notify({status:'done',value:job.value,result});}
   catch(error){if(current()){lastKey=null;notify({status:'error',value:job.value,error});}}
  }running=false;
 }
 return {request(value){const key=JSON.stringify(value.identity);if(key===lastKey)return;lastKey=key;pending={value,revision:++revision};notify({status:'running',value});void drain();},invalidate(){revision++;pending=null;lastKey=null;},get running(){return running;}};
}
const api={preview,latestRunner};root.HLStrategyExperiment=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
