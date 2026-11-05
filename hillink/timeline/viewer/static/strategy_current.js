// Current-run strategy planning. No stored run IDs, scenario presets or invented products.
(function(root){
'use strict';
const GOALS={restaurant:'특정 업장 방문 유치',spend:'호텔 전체 가상 소비 증대',recapture:'호텔 밖 소비의 내부 전환'};
const stable=x=>JSON.stringify(normalize(x));
function normalize(x){if(Array.isArray(x))return x.map(normalize);if(x&&typeof x==='object')return Object.fromEntries(Object.keys(x).sort().filter(k=>x[k]!==undefined).map(k=>[k,normalize(x[k])]));return x;}
const isRestaurant=v=>['PIZZA_HILL','GEUMRYONG','MOEGI','ONDAL','MYONGWOLGWAN','THE_BUFFET','DELVINO','LE_PASSAGE'].includes(v);
function candidates(analysis,goal,cap,catalog,target){
 const groups=new Map();
 if(!(cap?.supported||[]).includes('catalog_discount_percent'))return [];
 for(const r of analysis.rows||[]){
  if(r.status!=='ANALYZED'||!['lunch','dinner'].includes(r.slot))continue;
  if(goal==='recapture'&&r.chosen.venue!=='EXTERNAL_DELIVERY')continue;
  if(goal==='restaurant'&&(target?r.chosen.venue===target:isRestaurant(r.chosen.venue)))continue;
  for(const c of r.competitors||[]){
   if(target&&c.venue!==target)continue;
   const product=catalog?.products?.find(p=>p.sku_id===c.sku);
   if(catalog&&(!product||['NO_DISCOUNT_OR_POINTS','NO_ADDITIONAL_DISCOUNT'].includes(product.discount_policy)||product.price_confirmed===false))continue;
   if(!c.sku||!(c.total_krw>0)||!(c.price_part>0)||!isRestaurant(c.venue))continue;
   if(goal==='restaurant'&&c.same_venue)continue;
   if(goal==='spend'&&!(c.total_krw>(r.chosen.total_krw||0)))continue;
   let g=groups.get(c.sku);if(!g){g={kind:'discount',sku:c.sku,label:c.label,venue:c.venue,customers:[],decisions:[],gap:c.gap,space_sensitive:false};groups.set(c.sku,g);}
   if(!g.customers.includes(r.customer_id))g.customers.push(r.customer_id);
   g.decisions.push({key:r.decision_key,from:r.chosen.venue,to:c.venue,price_part:c.price_part,gap:c.gap});
   g.gap=Math.min(g.gap,c.gap);g.space_sensitive ||= (c.causes||[]).some(x=>x.category==='SPACE'&&x.delta!==0);
  }
 }
 if(target&&(cap?.supported||[]).includes('catalog_service_open_overrides')){
  const baseline=cap.service_open_venues?.[target];
  const blocked=(analysis.rows||[]).filter(r=>r.slot==='dinner'&&r.time<baseline&&r.time>='16:30'&&(r.blocked||[]).some(b=>b.venue===target&&(b.reasons||[]).some(x=>x.category==='TIME'&&!/CLOSURE|DATE_OR_SALE|RESERVATION/.test(x.code))));
  if(baseline&&blocked.length)groups.set('TIME:'+target,{kind:'opening',sku:'TIME:'+target,label:'저녁 영업 시작 앞당기기',venue:target,open_time:'17:00',baseline_open:baseline,customers:[...new Set(blocked.map(r=>r.customer_id))],decisions:blocked.map(r=>({key:r.decision_key,from:r.chosen.venue,to:target,reason:'실행 당시 영업시간으로 후보 제외'})),gap:0,space_sensitive:false});
 }
 return [...groups.values()].sort((a,b)=>b.customers.length-a.customers.length||a.gap-b.gap||a.sku.localeCompare(b.sku)).slice(0,3);
}
function prepareRequest(request,flow,cap){
 if(!request||!flow?.ledger||!cap?.catalog_policy)throw Error('원래 방문 조건과 상품 계산 정책을 확인하지 못했습니다.');
 const q=structuredClone(request);q.include_ledger=true;q.behavior_engine='m4_c01';q.catalog_policy=cap.catalog_policy;
 for(const k of ['simulation_mode','breakfast_policy'])if(flow.visit?.[k])q[k]=flow.visit[k];
 return q;
}
function readiness(flow,analysis,target,cs){
 if(!flow?.visit?.catalog_policy||!flow?.visit?.hotel_price_snapshot)return {code:'PREPARE',message:'현재 방문은 상품별 가격 비교를 사용하지 않았습니다. 같은 방문 조건으로 전략 분석용 방문을 먼저 생성해 주세요.'};
 if(cs.length)return {code:'READY',message:'실제 선택·후보 기록에서 실험 가능한 운영 조건을 찾았습니다.'};
 const t=targetSummary(analysis,target);
 if(!t.decisions&&(analysis.rows||[]).some(r=>r.chosen?.choice_source==='RECORDED_SCENE_ORDER'))return {code:'NO_SCORE_RECORD',message:'실제 식사·주문 기록은 있지만 후보별 비교 점수가 없습니다. 이 기록만으로 비선택 이유나 할인 전략을 추정하지 않습니다. 다른 식사 결정이나 실행을 선택해 주세요.'};
 if(!t.decisions)return {code:'NO_DECISIONS',message:'이 방문에는 분석 가능한 점심·저녁 결정 기록이 없습니다. 방문 시간이나 기간을 바꾸어 새 방문을 생성해 주세요.'};
 if(t.blocked)return {code:'CONSTRAINED',message:'이 업장은 후보에서 제외된 기록이 있습니다. 자격·판매 기간·예약 제약은 할인으로 해제하지 않습니다. 현재 지원되는 시간 변경으로도 실험 후보를 만들 수 없는 조건입니다.'};
 if(t.absent===t.decisions)return {code:'ABSENT',message:'이 방문의 식사 결정에 해당 업장 후보가 기록되지 않았습니다. 비선택 이유나 효과를 추정하지 않습니다. 다른 업장을 선택하거나 방문 조건을 확인해 주세요.'};
 return {code:'NO_CANDIDATE',message:'분석은 완료됐지만 이 목표에 맞는 가격·시간 개입 후보가 없습니다. 다른 업장이나 운영 목표를 선택해 비교할 수 있습니다. 효과가 없다는 실험 결과를 뜻하지는 않습니다.'};
}
function pair(request,flow,candidate,pct){
 if(!request||!flow?.ledger||!candidate?.sku)throw new Error('현재 실행의 요청과 상품 근거가 필요합니다.');
 if(!Number.isFinite(pct)||pct<=0||pct>30)throw new Error('할인율은 0 초과 30 이하로 선택해 주세요.');
 const A=structuredClone(request);A.include_ledger=true;
 // Pin the actual resolved execution policies. Never change engine/catalog just to make an experiment runnable.
 for(const k of ['behavior_engine','simulation_mode','breakfast_policy'])if(flow.visit?.[k])A[k]=flow.visit[k];
 const B=structuredClone(A);B.catalog_options=B.catalog_options||{};
 if(B.catalog_options.price_overrides?.[candidate.sku]!=null)throw new Error('같은 상품의 직접 가격 변경을 먼저 해제해 주세요.');
 if(candidate.kind==='opening')B.catalog_options.service_open_overrides={...(B.catalog_options.service_open_overrides||{}),[candidate.venue]:candidate.open_time};
 else B.catalog_options.discount_percent={...(B.catalog_options.discount_percent||{}),[candidate.sku]:pct};
 if(stable(A)===stable(B))throw new Error('현재 할인과 같은 조건입니다. 다른 할인율을 선택해 주세요.');
 return {A,B};
}
function comparableDecision(r){return r.status==='ANALYZED'||r.status==='NO_TERM_DECOMPOSITION'&&r.chosen?.choice_source==='RECORDED_SCENE_ORDER';}
function metrics(a,b,analyze,sku,target){
 const ar=analyze(a).rows.filter(comparableDecision),br=analyze(b).rows.filter(comparableDecision);
 // Align by customer, service date, meal slot and occurrence, never by changing decision timestamp.
 function keyed(rows){const n={},out={};for(const r of rows){const base=[r.customer_id,r.date,r.slot].join('|'),k=base+'|'+(n[base]=(n[base]||0)+1);out[k]={...r,occurrence:n[base]};}return out;}
 const am=keyed(ar),bm=keyed(br),moves=[];let unmatched=0;
 for(const k of new Set([...Object.keys(am),...Object.keys(bm)])){
  const x=am[k],y=bm[k];if(!x||!y){unmatched++;continue;}
  const paidInternal=(b.ledger.receipts?.[y.customer_id]?.rows||[]).some(r=>r.visit_date===y.date&&(r.meal===y.slot||r.turn===y.slot)&&r.paid_krw>0&&((r.sku_id||r.product_sku_id||r.product_id)===y.chosen.sku||r.decision_id===`${y.customer_id}|${y.slot}|${y.time}`));
  if(x.chosen.venue!==y.chosen.venue||x.chosen.sku!==y.chosen.sku||x.chosen.product_signature!==y.chosen.product_signature)moves.push({pid:x.customer_id,date:x.date,slot:x.slot,occurrence:x.occurrence,A:decisionTarget(a,x),B:decisionTarget(b,y),from:x.chosen.venue,to:y.chosen.venue,from_product:x.chosen.label,to_product:y.chosen.label,recaptured:x.chosen.venue==='EXTERNAL_DELIVERY'&&(isRestaurant(y.chosen.venue)||y.chosen.venue==='IRD')&&paidInternal});
 }
 const rows=f=>Object.values(f.ledger.receipts||{}).flatMap(r=>r.rows||[]);
 const rowSKU=r=>r.sku_id||r.product_sku_id||r.product_id||r.sku_contract?.sku_id;
 const visits=rr=>rr.filter(r=>['lunch','dinner'].includes(r.slot)&&isRestaurant(r.chosen.venue)).length;
 // Existing buyer discount loss: same customer/date/product buys again; unmatched amounts are not claimed as causal loss.
 let retainedPriceDelta=0;for(const [pid,receipt] of Object.entries(a.ledger.receipts||{})){
  const before=(receipt.rows||[]).filter(r=>rowSKU(r)===sku),after=(b.ledger.receipts[pid]?.rows||[]).filter(r=>rowSKU(r)===sku);
  for(const r of before){const i=after.findIndex(t=>t.visit_date===r.visit_date&&t.quantity===r.quantity);if(i>=0){const t=after.splice(i,1)[0];retainedPriceDelta+=(t.paid_krw||0)-(r.paid_krw||0);}}
 }
 const targetVisits=rr=>rr.filter(r=>['lunch','dinner'].includes(r.slot)&&r.chosen.venue===target).length;
 const targetPaid=f=>rows(f).filter(r=>r.department==='F&B'&&(r.sku_contract?.venue_id===target||r.venue_id===target)).reduce((sum,r)=>sum+(r.paid_krw||0),0);
 return {target_before:targetVisits(ar),target_after:targetVisits(br),target_delta:targetVisits(br)-targetVisits(ar),target_fnb_delta:targetPaid(b)-targetPaid(a),target_arrivals:moves.filter(m=>m.to===target&&m.from!==target).length,target_departures:moves.filter(m=>m.from===target&&m.to!==target).length,paid_delta:b.ledger.totals.paid_krw-a.ledger.totals.paid_krw,restaurant_delta:visits(br)-visits(ar),recaptured:moves.filter(m=>m.recaptured).length,
 changed_customers:new Set(moves.map(m=>m.pid)).size,moves,unmatched,retained_price_delta:retainedPriceDelta,
 discount_burden:rows(b).filter(r=>rowSKU(r)===sku).reduce((n,r)=>n+(r.discount_krw||0),0)};
}
function decisionTarget(flow,row){
 return {run_id:flow.ledger?.run_id,customer_id:row.customer_id,date:row.date,slot:row.slot,
  occurrence:row.occurrence,decision_id:row.packet_sha256||null,event_id:row.event_id||null,time:row.time};
}
function resolveDecisionScene(flow,target){
 if(!target||flow.ledger?.run_id!==target.run_id)throw Error('선택한 행동의 실행 ID가 현재 결과와 일치하지 않습니다.');
 const scenes=flow.plans?.[target.customer_id]?.scenes;
 if(!scenes)throw Error('해당 실행에 선택한 고객의 행동 기록이 없습니다.');
 if(!target.date||!target.slot)throw Error('변경된 결정의 날짜·식사 구분이 없어 행동을 열 수 없습니다.');
 // Cafe/snack scenes may omit meal/turn. Resolve their slot from the recorded
 // activity occurrence, never from the venue or the first meal of that day.
 const activities=(flow.visit_days?.map(d=>d.flow)||[flow]).flatMap(d=>d.plans?.[target.customer_id]?.m4?.activity_history||[]);
 const slotOf=s=>s.meal||s.turn||activities.find(a=>a.event_id===s.basis?.m4?.event_id&&a.date===s.visit_date&&a.start_minute===s.t0)?.meal_slot;
 const matches=scenes.map((scene,index)=>({scene,index})).filter(({scene:s})=>s.visit_date===target.date&&slotOf(s)===target.slot);
 let exact=matches;
 if(target.decision_id)exact=exact.filter(({scene:s})=>(s.basis?.m4?.decision_packet_ids||[]).includes(target.decision_id)||s.decision_id===target.decision_id);
 if(target.event_id)exact=exact.filter(({scene:s})=>s.basis?.m4?.event_id===target.event_id);
 if(!target.decision_id&&!target.event_id)throw Error('변경된 결정의 발생 식별자가 없어 다른 활동으로 대체하지 않았습니다.');
 if(exact.length!==1)throw Error(exact.length?'같은 결정에 여러 행동이 연결되어 정확한 발생 건을 확인해야 합니다.':'해당 날짜·식사·결정에 연결된 실제 행동을 찾지 못했습니다. 다른 장면으로 대체하지 않았습니다.');
 return {index:exact[0].index,scene:exact[0].scene,target};
}
function policyKey(flow){
 return stable({breakfast:flow.visit?.breakfast_policy,catalog:flow.visit?.hotel_catalog_sha256,
  engine:flow.visit?.behavior_engine,mode:flow.visit?.simulation_mode,source:flow.visit?.m4_configuration?.source_sha256,
  room:flow.ledger?.context?.room_price_source_sha256});
}
function conditionKey(request){
 const keys=['personas','duration','event_mode','seed','start_date','environment','visit_conditions','package_id','scenario','behavior_engine','simulation_mode','catalog_policy','catalog_options','breakfast_policy','hybrid_policy'];
 return stable(Object.fromEntries(keys.filter(k=>request[k]!==undefined).map(k=>[k,request[k]])));
}
function eventLabel(registry,visit,request){
 const id=visit?.scenario_snapshot?.event_card_id||request?.scenario?.event_card_id;
 if(id&&id!=='NONE')return registry?.events?.find(x=>x.event_card_id===id)?.label||id;
 const mode=request?.event_mode||visit?.event_mode;
 if(mode==='wine')return registry?.events?.find(x=>x.id==='wine')?.label||'와인페어';
 return '행사 없음';
}
function replayMatches(original,replay){
 const proof=f=>({run:f.ledger?.run_id,policy:f.visit?.breakfast_policy,catalog:f.visit?.hotel_catalog_sha256,
  engine:f.visit?.m4_configuration?.source_sha256,room:f.ledger?.context?.room_price_source_sha256,
  receipts:f.ledger?.receipts});
 return !!original?.ledger?.run_id&&stable(proof(original))===stable(proof(replay));
}

function venues(catalog){return [...new Set((catalog?.products||[]).filter(p=>p.category==='F&B'&&['MAIN','BREAKFAST','SNACK'].includes(p.role)&&!['ROOM_MEAL','WINE_FAIR'].includes(p.venue_id)&&p.automatic_choice!==false).map(p=>p.venue_id))].sort();}
function targetSummary(analysis,target){
 const rr=(analysis.rows||[]).filter(r=>r.status==='ANALYZED'&&['lunch','dinner'].includes(r.slot)),chosen=rr.filter(r=>r.chosen.venue===target),competed=rr.filter(r=>r.chosen.venue!==target&&(r.competitors||[]).some(c=>c.venue===target)),blocked=rr.filter(r=>(r.blocked||[]).some(c=>c.venue===target));
 const reasons={};for(const r of competed)for(const t of r.competitors.filter(c=>c.venue===target))for(const c of t.causes||[])if(c.delta>0){(reasons[c.category]??=new Set()).add(r.customer_id);}
 return {decisions:rr.length,selected:chosen.length,customers:[...new Set(chosen.map(r=>r.customer_id))],competed:competed.length,blocked:blocked.length,time_blocked:blocked.filter(r=>r.blocked.some(b=>b.venue===target&&b.reasons.some(x=>x.category==='TIME'))).length,absent:rr.filter(r=>r.chosen.venue!==target&&!r.competitors?.some(c=>c.venue===target)&&!r.blocked?.some(c=>c.venue===target)).length,reasons:Object.fromEntries(Object.entries(reasons).map(([k,v])=>[k,v.size]))};
}

// Goal contract: run identity and filters travel together through diagnosis, experiments and verdicts.
function strategyGoal(input,flow){
 const objective=Object.hasOwn(GOALS,input.goal)?input.goal:'restaurant';
 return {version:'STRATEGY_GOAL_V31',basis:input.basis||'OBSERVED_VISIT',assumed_origin:input.basis==='OPERATOR_ASSUMPTION'?input.assumedOrigin:null,decision:input.decision||null,intent:input.intent||'switch',objective,origin:objective==='recapture'?'EXTERNAL_DELIVERY':input.origin||'ANY',target:objective==='spend'&&input.intent!=='increase'?null:input.target||null,cohort:input.cohort==='family'?'family':'all',run_id:flow.ledger.run_id,environment:conditionKey(flow.request||{})};
}
function familyEvidence(flow,pid){
 const c=flow.visit?.resolved_conditions?.[pid]||{},type=flow.ledger.receipts?.[pid]?.customer_type||'';
 if(c.party_composition?.children?.length)return {family:true,basis:'이번 방문의 아동 동행 입력',party_size:c.party_size};
 if(/가족/.test(type))return {family:true,basis:'실행에 기록된 가족 프로필 분류 · 실제 나이 미확인',party_size:c.party_size};
 return {family:null,basis:'가족 동행 여부 미확인 · 인원수로 추정하지 않음',party_size:c.party_size};
}
function opportunity(flow,analysis,goal){
 if(goal.run_id!==flow.ledger.run_id)throw Error('운영 목표와 분석 실행이 다릅니다.');
 const meals=(analysis.rows||[]).filter(r=>comparableDecision(r)&&(goal.decision||['lunch','dinner'].includes(r.slot)));
 const family=Object.fromEntries(Object.keys(flow.ledger.receipts||{}).map(p=>[p,familyEvidence(flow,p)]));
 const rows=meals.filter(r=>(!goal.decision||JSON.stringify([r.customer_id,r.date,r.slot,r.packet_sha256||null,r.event_id||null,r.time])===goal.decision)&&(goal.cohort!=='family'||family[r.customer_id]?.family===true)&&(goal.origin==='ANY'||(goal.origin==='OTHER_RESTAURANT'?isRestaurant(r.chosen.venue)&&r.chosen.venue!==goal.target:r.chosen.venue===goal.origin)));
 const customers=[...new Set(rows.map(r=>r.customer_id))];
 const details=rows.map(r=>{const c=goal.target?r.competitors?.find(c=>c.venue===goal.target):r.competitors?.find(c=>isRestaurant(c.venue)&&c.price_part>0),b=goal.target?r.blocked?.find(c=>c.venue===goal.target):r.blocked?.find(c=>isRestaurant(c.venue));return {row:r,status:r.chosen.venue===goal.target?'CHOSEN':c?'COMPETED':b?'BLOCKED':'ABSENT',competitor:c,blocked:b,family:family[r.customer_id]};});
 const counts=Object.fromEntries(['CHOSEN','COMPETED','BLOCKED','ABSENT'].map(s=>[s,details.filter(d=>d.status===s).length]));
 return {goal,customers,rows,details,counts,analysis:{...analysis,rows},all_customers:Object.keys(flow.ledger.receipts||{}).length,family_unknown:Object.values(family).filter(x=>x.family!==true).length,
  diagnosis:!customers.length?'이 목표에 해당하는 실제 식사 결정이 없습니다. 다른 실제 실행이나 고객군을 선택하세요.':!goal.target?`${customers.length}팀의 ${rows.length}건에서 다른 호텔 식당의 가격·시간 대안을 분석합니다. 업장 간 소비 대체와 할인 비용을 함께 비교합니다.`:`${customers.length}팀의 ${rows.length}건을 분석했습니다. 목표 업장과 비교 후 미선택 ${counts.COMPETED}건, 조건으로 제외 ${counts.BLOCKED}건, 후보 기록 없음 ${counts.ABSENT}건입니다.`};
}
function goalCandidates(opp,cap,catalog){
 if(!opp.customers.length)return [];
 // Every lever, including opening-time changes, is restricted to the same origin/cohort.
 return candidates(opp.analysis,opp.goal.objective,cap,catalog,opp.goal.target);
}
function hypotheses(opp,catalog){
 if(!opp.customers.length||!opp.goal.target)return [];
 const products=(catalog?.menu_references||catalog?.products||[]).filter(p=>p.venue_id===opp.goal.target&&p.role==='MAIN'&&p.sku_id&&p.automatic_choice!==false);
 const periods=new Set(opp.rows.map(r=>r.slot)),date=opp.rows[0]?.date;
 const menus=products.filter(p=>(!p.service_periods?.length||p.service_periods.some(x=>periods.has(x)))&&(!p.valid_from||p.valid_from<=date)&&(!p.valid_until||p.valid_until>=date)).slice(0,3);
 if(!menus.length)return [];
 const causes=[...new Set(opp.details.flatMap(d=>(d.competitor?.causes||[]).filter(c=>c.delta>0).map(c=>c.category)))];
 const family=opp.details.some(d=>d.family.family===true);
 const questions=[];
 if(causes.some(c=>['PRICE','VALUE_CHECK'].includes(c)))questions.push('등록 메뉴의 인원별 구성으로 가격 부담을 낮출 수 있는지');
 if(causes.includes('MENU'))questions.push('기록된 메뉴 취향에 맞는 기존 상품 조합이 있는지');
 if(causes.includes('SPACE'))questions.push('실제로 제공 가능한 좌석·공간 조건으로 비교 열세를 줄일 수 있는지');
 if(opp.details.some(d=>d.blocked?.reasons?.some(r=>r.category==='TIME')))questions.push('식사 시점과 영업시간을 맞출 수 있는지');
 if(!questions.length)questions.push('후보 생성·이용 자격·식사 구성을 먼저 확인할 필요가 있는지');
 return [{status:'UNTESTED',title:family?'동행 인원에 맞춘 가족 식사 구성 검토':'기존 메뉴의 식사 구성·접근 조건 검토',customers:opp.customers,menus,causes,question:questions.join(' · '),
  observation:`${opp.customers.length}팀의 실제 선택에서 출발한 운영 가설입니다. ${opp.counts.ABSENT?'목표 업장 후보가 없는 결정은 비선택 원인을 확정할 수 없습니다.':''}`,
  price_basis:'등록 단품의 모델 참고가만 제시합니다. 적정 세트 가격과 지불 의향은 확인되지 않아 산정하지 않았습니다.',
  requirements:'실제 제공 가능한 구성·판매 단위·인원별 수량·아동 조건·예약·운영시간을 확인해야 합니다.',
  engine_inputs:'가상 구성 계약, 인원별 수량, 판매 기간과 자격을 후보 생성·선택·주문·원장에 연결해야 합니다. 현재 세트 효과는 계산하지 않았습니다.'}];
}
function goalMetrics(a,b,analysis,sku,goal){
 const m=metrics(a,b,analysis,sku,goal.target),opp=opportunity(a,analysis(a),goal),ids=new Set(opp.customers),decisions=new Set(opp.rows.map(r=>r.packet_sha256));
 const paidOccurrence=x=>{
  if(!b.plans)return false; // A paid occurrence must resolve to this execution's actual scene.
  try{const {scene}=resolveDecisionScene(b,x.B),time=String(Math.floor(scene.t0/60)).padStart(2,'0')+':'+String(scene.t0%60).padStart(2,'0');
   return (b.ledger.receipts[x.pid]?.rows||[]).some(r=>r.visit_date===x.date&&r.time===time&&(r.meal||r.turn)===x.slot&&r.paid_krw>0&&(r.venue_id===goal.target||r.sku_contract?.venue_id===goal.target));
  }catch{return false;}
 };
 const arrivals=m.moves.filter(x=>ids.has(x.pid)&&decisions.has(x.A.decision_id)&&x.to===goal.target&&x.from!==goal.target&&(goal.objective!=='recapture'||x.recaptured&&paidOccurrence(x)));
 const spend=(f,predicate)=>Object.entries(f.ledger.receipts||{}).filter(([id])=>ids.has(id)).flatMap(([,r])=>r.rows||[]).filter(predicate).reduce((n,r)=>n+(r.paid_krw||0),0);
 const atTarget=r=>r.department==='F&B'&&(r.venue_id===goal.target||r.sku_contract?.venue_id===goal.target);
 const venueTotals=f=>{const out={};for(const r of Object.values(f.ledger.receipts||{}).flatMap(r=>r.rows||[])){const v=r.venue_id||r.sku_contract?.venue_id;if(v)out[v]=(out[v]||0)+(r.paid_krw||0);}return out;};
 const av=venueTotals(a),bv=venueTotals(b);
 const afterAnalysis=analysis(b),matchedB=new Set(m.moves.filter(x=>decisions.has(x.A.decision_id)).map(x=>x.B.decision_id));
 const afterRows=goal.decision?afterAnalysis.rows.filter(r=>matchedB.has(r.packet_sha256)||opp.rows.some(a=>a.customer_id===r.customer_id&&a.date===r.date&&a.slot===r.slot&&a.time===r.time)):afterAnalysis.rows;
 const afterOpportunity=opportunity(b,{...afterAnalysis,rows:afterRows},{...goal,decision:null,run_id:b.ledger.run_id,origin:'ANY'});
 const remaining=afterOpportunity.details.filter(d=>ids.has(d.row.customer_id)&&d.status!=='CHOSEN');
 const remainingCauses=[...new Set(remaining.flatMap(d=>(d.competitor?.causes||[]).filter(c=>c.delta>0).map(c=>c.category)))];
 return {...m,goal,remaining_causes:remainingCauses,remaining_blocked:remaining.filter(d=>d.status==='BLOCKED').length,eligible_customers:opp.customers,goal_arrivals:arrivals.length,goal_customers:[...new Set(arrivals.map(x=>x.pid))],goal_moves:arrivals,
 cohort_paid_delta:spend(b,()=>true)-spend(a,()=>true),cohort_target_delta:spend(b,atTarget)-spend(a,atTarget),
 other_venue_decreases:Object.keys(av).filter(v=>v!==goal.target&&(bv[v]||0)<av[v]).map(v=>({venue:v,delta:(bv[v]||0)-av[v]}))};
}
function verdict(goal,m){
 if(!m)return {status:'UNTESTED',text:'전략을 실행한 뒤 판단합니다. 아직 실행하지 않은 가설에는 효과를 부여하지 않습니다.'};
 if(!m.eligible_customers.length)return {status:'NO_POPULATION',text:'분석 대상 고객이 없습니다. 효과가 0이라는 결과가 아닙니다.'};
 if(goal.intent==='increase'&&goal.target)return {status:m.cohort_target_delta>0?'REVIEW':'MAINTAIN',text:m.cohort_target_delta>0?'목표 업장의 가상 소비가 늘었습니다. 같은 고객의 전체 방문 합계이며, 식사 구성 변화와 호텔 전체 소비·할인 비용을 함께 검토하세요.':'현재 업장을 유지한 소비 확대는 확인되지 않았습니다. 다른 업장 소비 증가를 이 목표의 성공으로 해석하지 않습니다.'};
 if(goal.objective==='spend')return {status:m.paid_delta>0?'REVIEW':'MAINTAIN',text:m.paid_delta>0?'이 실행에서는 호텔 전체 가상 소비가 늘었습니다. 할인 비용과 업장 간 감소를 함께 검토하세요.':'이 실행에서는 호텔 전체 가상 소비 증가가 확인되지 않았습니다. 현재 전략을 채택할 근거가 부족합니다.'};
 if(m.goal_arrivals>0)return {status:'REVIEW',text:m.paid_delta<0?'목표 고객의 유치 효과는 있었으나 호텔 전체 가상 소비가 감소했습니다. 다른 업장 감소와 할인 비용을 고려해 시행 여부를 검토하세요.':'목표 고객의 업장 이동이 관찰됐습니다. 단일 시드 가상 결과이므로 실제 시행 전 운영 가능성과 반복 결과를 확인하세요.'};
 return {status:'MAINTAIN',text:'현재 고객 조건에서는 이 전략이 목표 고객을 해당 업장으로 이동시키지 못했습니다. 관측된 시간·상품·선호 제약을 검토하고, 미실험 가설과 구분하세요.'};
}

// A saved navigation wrapper may carry the authoritative ledger outside result.
function restoreRun(saved){
 if(!saved?.result||!saved.ledger||!saved.request)return null;
 if(saved.result.ledger?.run_id&&saved.result.ledger.run_id!==saved.ledger.run_id)throw Error('저장 실행의 원장 식별자가 일치하지 않습니다.');
 return {...saved.result,ledger:saved.ledger,request:saved.request,visit:saved.result.visit||saved.visit};
}
function analysisOutcome(flow,analysis,goal,opp,cs,ready){
 const meals=(analysis.rows||[]).filter(r=>comparableDecision(r)&&(goal.decision||['lunch','dinner'].includes(r.slot)));
 const observedOrigins=[...new Set(meals.map(r=>r.chosen.venue))];
 const names={IRD:'룸서비스',EXTERNAL_DELIVERY:'외부 배달',MYONGWOLGWAN:'명월관',PIZZA_HILL:'피자힐',GEUMRYONG:'금룡',MOEGI:'모에기',ONDAL:'온달',THE_BUFFET:'더뷔페',DELVINO:'델비노'};
 let status='ANALYZED',diagnosis=opp.diagnosis,conclusion='추천 전략 중 하나로 A/B를 실행해 실제 선택이 달라지는지 확인하세요. 아직 효과를 계산하지 않았습니다.';
 if(!meals.length){status='NO_EVIDENCE';diagnosis='이번 방문에는 식사 선택을 판단할 기록이 부족합니다. 외부 배달을 이용하지 않았다고 단정할 수 없습니다.';conclusion='식사 결정 기록이 있는 실제 실행을 선택하거나 다른 방문 조건을 실행해 주세요.';}
 else if(!opp.customers.length){status='NO_TARGET_CUSTOMERS';const selected=observedOrigins.map(v=>names[v]||'다른 활동').join(' · ');
  diagnosis=goal.origin!=='ANY'&&!observedOrigins.includes(goal.origin)&&goal.origin!=='OTHER_RESTAURANT'?`이번 방문의 기록된 식사 선택은 ${selected}입니다. ${names[goal.origin]||'설정한 소비 경로'} 선택 기록이 없어 목표에 해당하는 고객은 0명입니다.`:goal.cohort==='family'?'선택한 소비 경로와 가족 분류가 함께 확인된 고객이 없습니다. 가족 여부 미확인을 실제 비가족으로 판정하지 않았습니다.':'설정한 소비 경로에 해당하는 고객이 없습니다.';
  conclusion='대상 고객이 없다는 분석 결과입니다. 전략을 실험해 효과가 없었다는 뜻은 아닙니다. 실제 선택 경로 또는 이미 실행한 다른 고객군으로 분석 조건을 바꾸세요.';
 }else if(['ABSENT','NO_SCORE_RECORD','NO_DECISIONS'].includes(ready.code)){status='NO_EVIDENCE';conclusion=ready.message;}
 else if(!cs.length){status='NO_EXECUTABLE_STRATEGY';conclusion=ready.message;}
 else if(cs.some(c=>c.kind==='opening'))conclusion='영업시간 때문에 후보에서 제외된 결정이 기록되어 있습니다. 지원되는 영업 시작 시각 변경을 먼저 비교할 수 있습니다. 다른 제약도 있으므로 할인만으로 해결된다고 단정하지 않습니다.';
 return {status,diagnosis,conclusion,observedOrigins};
}

const API={restoreRun,analysisOutcome,strategyGoal,familyEvidence,opportunity,goalCandidates,hypotheses,goalMetrics,verdict,prepareRequest,readiness,decisionTarget,resolveDecisionScene,venues,targetSummary,GOALS,stable,candidates,pair,metrics,isRestaurant,replayMatches,eventLabel,conditionKey,policyKey};
if(typeof module!=='undefined'&&module.exports)module.exports=API;
root.HLStrategy=API;
})(typeof window!=='undefined'?window:globalThis);
