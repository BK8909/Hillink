// UXIA01: evidence reads one immutable product run. Navigation never starts an engine.
const BH = { pid:'blog41',e:0,turn:'dinner',tab:'case',step:0,type:null,q:'',open:false,flow:null,data:{},context:null,snapshots:new Map(),storageWarning:'',routeToken:0 };
const BH_TURN={breakfast:'아침',lunch:'점심',event:'행사 시간',dinner:'저녁'};
function bhKey(pid,e){return JSON.stringify({event:!!e,intervention:'none',mode:'one',observe:'day',personas:[pid],product_levers:{},seed:0,visit_override:null});}
function bhDB(){return new Promise((resolve,reject)=>{const q=indexedDB.open('hillink-local-runs-v1',1);q.onupgradeneeded=()=>{if(!q.result.objectStoreNames.contains('runs'))q.result.createObjectStore('runs');};q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);});}
async function bhRemember(snapshot){
  const run=snapshot.flow.ledger.run_id;BH.snapshots.set(run,snapshot);
  try{const db=await bhDB();await new Promise((resolve,reject)=>{const tx=db.transaction('runs','readwrite');tx.objectStore('runs').put(snapshot,run);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});db.close();BH.storageWarning='';}
  catch(e){BH.storageWarning='현재 탭에서는 탐색할 수 있지만 이 실행의 새로고침 복원은 저장하지 못했습니다.';}
}
async function bhRecall(run){
  if(typeof hlReasonPrepare==='function')try{await hlReasonPrepare(run);}catch(e){BH.storageWarning=e.message;return null;}
  if(BH.snapshots.has(run))return BH.snapshots.get(run);
  try{const db=await bhDB();const value=await new Promise((resolve,reject)=>{const q=db.transaction('runs').objectStore('runs').get(run);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);});db.close();if(value)BH.snapshots.set(run,value);return value||(typeof hlReasonSnapshot==='function'?hlReasonSnapshot(run):null);}catch(e){return typeof hlReasonSnapshot==='function'?hlReasonSnapshot(run):null;}
}
async function bhRun_(pid,e){
  const snapshot=BH.context&&await bhRecall(BH.context.run_id);if(snapshot&&snapshot.flow.result.plans[pid])return snapshot.flow.result;
  const cached=BH.data[pid+'|'+e];if(cached)return cached;
  if(typeof DS!=='undefined'&&DS.on&&DS.step&&DS.fx&&DS.fx.entries){const stored=DS.fx.entries[bhKey(pid,e)];if(stored)return structuredClone(stored);}
  throw new Error('연결된 실행 기록이 없습니다. 고객 흐름에서 실제 방문을 실행하고 행동을 선택해 주세요.');
}
// Ledger scene_index is day-local; the evidence scene_index is visit-global.
// Never use either index alone to join transactions across a multi-day visit.
function bhRowsForScene(receipt,raw){
  return (receipt.rows||[]).filter(r=>(r.visit_day||1)===(raw.visit_day||1)&&r.act===raw.act&&r.time===agHM(raw.t0)&&(!r.selection_id||!raw.basis?.selection_id||r.selection_id===raw.basis.selection_id));
}
function bhContextFor(snapshot,pid,index,options={}){
  const flow=snapshot.flow,L=flow.ledger,plan=flow.result.plans[pid],raw=plan&&plan.scenes[index];if(!raw)return null;
  const receipt=L.receipts[pid],day=raw.visit_day||1,time=agHM(raw.t0);
  const action=(receipt.actions||[]).find(a=>(a.visit_day||1)===day&&a.time===time&&a.action===raw.act);
  const rows=bhRowsForScene(receipt,raw);
  if(options.ledger_tx_id&&!rows.some(r=>r.row_id===options.ledger_tx_id))return null;
  const ids=raw.basis&&raw.basis.m4&&raw.basis.m4.decision_packet_ids||[];
  const d=window.HLStory?.decisionOf(plan,raw)||(plan.m4&&(plan.m4.decisions||[]).find(d=>d.execution_status==='EXECUTED'&&ids.includes(d.packet.packet_sha256)));
  return {customer_id:pid,run_id:L.run_id,visit_id:L.visit&&L.visit.visit_id||flow.result.visit_id||null,stay_id:receipt.stay_id||null,visit_day:day,visit_date:raw.visit_date||null,scene_index:index,action_id:action&&action.action_id||null,action_code:raw.act,decision_id:d?d.packet.packet_sha256:raw.decision_id||null,ledger_tx_id:options.ledger_tx_id&&rows.some(r=>r.row_id===options.ledger_tx_id)?options.ledger_tx_id:rows.length===1?rows[0].row_id:null,returnTo:options.returnTo||'flow'};
}
function bhContextURL(c){const p=new URLSearchParams();for(const k of ['customer_id','visit_id','stay_id','visit_day','visit_date','scene_index','action_id','action_code','decision_id','ledger_tx_id','returnTo'])if(c[k]!=null)p.set(k,String(c[k]));return '#evidence/run/'+encodeURIComponent(c.run_id)+'?'+p.toString();}
function bhActivate(snapshot,context,push=true){
  if(window.HLNav?.active())return HLNav.activate(snapshot,context);
  BH.context=context;BH.pid=context.customer_id;BH.e=snapshot.flow.ledger.context.event?1:0;BH.tab='case';BH.flow={pid:BH.pid,turn:BH.turn,e:BH.e,many:snapshot.flow.ledger.team_count>1};
  BH.snapshots.set(context.run_id,snapshot);if(push)history.pushState({hillinkEvidence:context},'',bhContextURL(context));closeDrawer();setMode('evidence');
}
function bhFromScene(pid,si,options={}){
  if(window.HLNav?.active())return HLNav.openScene(pid,si,options);
  if(!AG.flow||!AG.flow.ledger||!AG.flow.result)return false;
  const scene=agScenes(pid).find(s=>s.si===si);if(!scene||scene.k==='move')return false;
  const snapshot={flow:structuredClone(AG.flow),returnState:{mode:AG.mode,one:AG.one,sel:AG.sel,day:AG.visitDay||1,cond:structuredClone(AG.cond),duration:AG.duration,dialogue:window.HLDialogue?.capture?.(),manyTime:AG.manyT,fraction:AG.f,nowMin:AG.nowMin,panelScroll:document.querySelector('#panel')?.scrollTop||0,panelDetails:[...document.querySelectorAll('#panel details')].map(d=>({key:d.dataset.frpDetailKey||d.className+'|'+(d.querySelector('summary')?.textContent||''),open:d.open})),stripScroll:document.querySelector('#strip')?.scrollLeft||0,scene:{t0:scene.t0,t1:scene.t1,act:scene.act,loc:scene.loc,k:scene.k,turn:AG.runs[scene.ti]&&AG.runs[scene.ti].turn}}};
  const plan=snapshot.flow.result.plans[pid],index=plan&&plan.scenes.findIndex(s=>(s.visit_day||1)===(scene.visit_day||AG.visitDay||1)&&s.t0===scene.t0&&s.t1===scene.t1&&(s.act===scene.act||scene.k==='turn'&&s.turn===AG.runs[scene.ti].turn));
  if(index==null||index<0)return false;const context=bhContextFor(snapshot,pid,index,options);if(!context)return false;
  agPause();
  // Browser Back owns the same immutable run, not the generic /live route initializer.
  const query=bhContextURL(context).split('?')[1];
  history.replaceState(null,'',`#flow/${encodeURIComponent(pid)}/${snapshot.flow.ledger.context.event?1:0}/run/${encodeURIComponent(context.run_id)}?${query}`);
  BH.persisting=bhRemember(snapshot);if(options.reviewOnly){BH.context=context;const x=window.HLStory.input(snapshot.flow.result,pid,index);libOpen(pid,x.facts.map(f=>f.id),bhContextURL(context),'reviews');}else bhActivate(snapshot,context);return true;
}
function bhFromFlow(pid,ti){
  const scene=agScenes(pid).find(s=>s.k==='turn'&&s.ti===ti);if(scene)return bhFromScene(pid,scene.si);
  return false;
}
async function bhFromStoredDemo(pid,e,turn){
  if(typeof DS==='undefined'||!DS.on||!DS.step||!DS.fx||!DS.fx.entries)return false;
  const key=bhKey(pid,e),stored=DS.fx.entries[key];if(!stored)return false;
  const L=await api('/api/ledger/demo',{key});if(!L||L.source!=='stored_demo'||!L.receipts[pid])return false;
  const r={...structuredClone(stored),ledger:L},index=r.plans[pid].scenes.findIndex(s=>s.turn===turn);if(index<0)return false;
  const snapshot={flow:{result:r,ledger:L,request:JSON.parse(key),engine:r.engine,stories:r.stories||null},returnState:{mode:'agent',day:1,cond:structuredClone((r.runs.find(x=>x.turn===turn)||{}).conditions||AG.cond),duration:'day_visit'}};
  const context=bhContextFor(snapshot,pid,index);if(!context)return false;BH.persisting=bhRemember(snapshot);bhActivate(snapshot,context,false);return true;
}
async function bhRestore(snapshot,c){
  const navigation=BH.navToken||0;
  BH.restoring=true;try{
  const source=structuredClone(snapshot.flow);REV.flow={...structuredClone(source.result),ledger:source.ledger};revRememberFlow(REV.flow,source.request);await revShowCustomer(c.customer_id);if(navigation!==(BH.navToken||0))return false;
  const mode=snapshot.returnState.mode==='agents'&&source.ledger.team_count>1?'agents':'agent';AG.one=c.customer_id;AG.sel=c.customer_id;AG.duration=source.request.duration||snapshot.returnState.duration;AG.cond=structuredClone(snapshot.returnState.cond);AG.visitData=source.ledger.visit?structuredClone(source.result):null;
  AG.keep[mode]={runs:AG.runs,sel:c.customer_id,plans:AG.plans,visits:AG.visits,flow:source};await setMode(mode);if(source.ledger.visit)agVisitDaySelect(c.visit_day||1);
  AG.flow=source;if(AG.keep[mode])AG.keep[mode].flow=source;
  const raw=source.result.plans[c.customer_id].scenes[c.scene_index],scene=agScenes(c.customer_id).find(s=>s.k!=='move'&&(s.visit_day||1)===(c.visit_day||1)&&s.t0===raw.t0&&s.t1===raw.t1&&(s.act===raw.act||s.k==='turn'&&AG.runs[s.ti].turn===raw.turn));
  if(scene){
    const saved=snapshot.returnState, same=(saved.sel||saved.one)===c.customer_id&&saved.day===(c.visit_day||1)&&saved.scene?.t0===raw.t0&&saved.scene?.t1===raw.t1&&saved.scene?.act===raw.act;
    if(mode==='agents'&&typeof agManyJump==='function'){AG.si=scene.si;agManyJump(same&&saved.manyTime!=null?saved.manyTime:scene.t0);AG.paused=true;}else {
    agSetScene(scene.si,same?saved.fraction:0);
    if(same&&saved.nowMin!=null){AG.nowMin=saved.nowMin;agClock();agStripMark();}
    agPause();
    if(same){window.HLDialogue?.restore?.(saved.dialogue);const recorded=(saved.panelDetails||[]).slice();for(const d of document.querySelectorAll('#panel details')){const key=d.dataset.frpDetailKey||d.className+'|'+(d.querySelector('summary')?.textContent||'');const i=recorded.findIndex(v=>v.key===key);if(i>=0){d.open=recorded[i].open;recorded.splice(i,1);}}document.querySelector('#panel').scrollTop=saved.panelScroll||0;document.querySelector('#strip').scrollLeft=saved.stripScroll||0;}
  }}return !!scene;
  }finally{BH.restoring=false;}
}
async function bhReturnFlow(){if(window.HLNav?.active())return HLNav.go("flow",{context:BH.context});const c=BH.context,snapshot=c&&await bhRecall(c.run_id);if(!snapshot)return;if(!await bhRestore(snapshot,c))return;const p=new URLSearchParams(bhContextURL(c).split('?')[1]);history.pushState(null,'',`#flow/${encodeURIComponent(c.customer_id)}/${snapshot.flow.ledger.context.event?1:0}/run/${encodeURIComponent(c.run_id)}?${p}`);}
async function bhReturnRevenue(push=true){if(window.HLNav?.active())return HLNav.go("revenue",{run:BH.context.run_id});const navigation=BH.navToken||0;const c=BH.context,snapshot=c&&await bhRecall(c.run_id);if(!snapshot)return;await bhRestore(snapshot,c);if(navigation!==(BH.navToken||0))return;REV.flow={...structuredClone(snapshot.flow.result),ledger:structuredClone(snapshot.flow.ledger)};revRememberFlow(REV.flow,snapshot.flow.request);REV.ledger=REV.flow.ledger;REV.scope='recent';setMode('opx');if(push)history.pushState(null,'','#revenue/run/'+encodeURIComponent(c.run_id)+'?'+bhContextURL(c).split('?')[1]);}
function bhModel(snapshot,c){
  const flow=snapshot.flow,L=flow.ledger,plan=flow.result.plans[c.customer_id],raw=plan&&plan.scenes[c.scene_index];if(!raw)return null;
  const expected=bhContextFor(snapshot,c.customer_id,c.scene_index,{ledger_tx_id:c.ledger_tx_id,returnTo:c.returnTo});
  if(!expected||expected.run_id!==c.run_id||expected.visit_day!==c.visit_day||(c.visit_date&&expected.visit_date!==c.visit_date)||(c.action_code&&expected.action_code!==c.action_code)||(c.action_id&&c.action_id!==expected.action_id)||(c.decision_id&&c.decision_id!==expected.decision_id)||(c.ledger_tx_id&&c.ledger_tx_id!==expected.ledger_tx_id))return null;
  const ids=raw.basis&&raw.basis.m4&&raw.basis.m4.decision_packet_ids||[],decision=window.HLStory?.decisionOf(plan,raw)||(plan.m4&&(plan.m4.decisions||[]).find(d=>d.execution_status==='EXECUTED'&&ids.includes(d.packet.packet_sha256)));
  const run=(flow.result.runs||[]).find(r=>(r.visit_day||1)===(raw.visit_day||1)&&r.turn===raw.turn&&r.customers.some(x=>x.persona_id===c.customer_id));
  const customer=run&&run.customers.find(x=>x.persona_id===c.customer_id),row=decision&&decision.packet.candidates.find(x=>x.candidate_id===decision.selected_action);
  const rows=bhRowsForScene(L.receipts[c.customer_id],raw);
  return {flow,L,plan,raw:window.HLAgentDecisionView?.resolve(raw,plan)||raw,decision,row,run,customer,rows};
}
async function renderBehavior(){
  if(!bhRouteMatch()&&!(typeof DS!=='undefined'&&DS.step)&&AG.flow&&AG.res){const pid=AG.mode==='agent'?AG.one:AG.sel;if(pid){const sc=agScenes(pid).find(s=>s.si===AG.si);if(sc&&sc.k!=='move'&&bhFromScene(pid,sc.si))return;}}
  const el=$('#evidenceView');if(typeof libLoad==='function')try{await libLoad();}catch(e){}
  if(BH.context&&libEng(BH.context.customer_id)?.isolated_qa)await HillinkPrivateIntake.load(BH.context.customer_id);
  const ids=((AG.meta||{}).personas||[]).map(p=>p.id);
  el.innerHTML=`<div class="bv ux-evidence"><div class="bv-head"><div><h2>행동근거</h2><p>선택 당시의 후보·상태·계산 기록을 확인합니다.</p></div><div class="bv-tabs" role="tablist"><button role="tab" data-tab="case" class="${BH.tab==='case'?'on':''}">선택의 판단 근거</button><button role="tab" data-tab="engine" class="${BH.tab==='engine'?'on':''}">엔진 재현 방법</button></div></div><div id="bvBody"></div></div>`;
  el.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{BH.tab=b.dataset.tab;renderBehavior();});if(BH.tab==='engine')return bvEngine(ids);return bvCase(ids);
}
async function bvCase(ids){
  const mount=$('#bvBody'),c=BH.context,snapshot=c&&await bhRecall(c.run_id),model=snapshot&&bhModel(snapshot,c);if(!mount)return;
  if(!model){mount.innerHTML=`<div class="ux-evidence-empty"><h3>${c?'해당 선택의 실행 기록을 확인할 수 없습니다':'분석할 행동을 선택하세요'}</h3><p>고객 흐름의 행동 또는 매출 집계의 거래에서 ‘자세한 판단 근거’를 열어 주세요. 이 화면은 별도 실행을 만들지 않습니다.</p><button class="cf-btn" id="bhUseCurrent">현재 고객 흐름의 선택 보기</button>${c?'<p class="hint">다른 run의 기록으로 대체하지 않습니다. 해당 실행을 보관한 브라우저에서 다시 열어 주세요.</p>':''}</div>`;mount.querySelector('#bhUseCurrent').onclick=()=>{if(AG.flow&&AG.res)bhFromFlow(AG.one||AG.sel||BH.pid,AG.ti);else setMode('agent');};return;}
  mount.innerHTML=bhEvidenceHTML(model,c);bhWireEvidence(snapshot,c,model);
}
function bvTypeOf(id){const p=typeof libP==='function'&&LIBV.data?libP(id):null;return p&&libTypeOf(p)||'유형 미확인';}
function bhSigned(v){return v==null?'미기록':(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(3);}
function bhNumber(v){return v==null?'미기록':Number(v).toFixed(3);}
function bhMealBasketHTML(row,rows){
  const b=row?.scoring_input_contract?.meal_basket;if(!b)return '';
  const quantity=r=>r.billing_quantity??r.quantity;
  return `<section class="ux-evidence-meal-basket"><h3>이 식사의 주문 구성과 식사량</h3><p>${rows.map(r=>`${esc(r.product)}${quantity(r)!=null?' × '+esc(quantity(r)):''} · ${r.paid_krw==null?'금액 미확인':rcMoney(r.paid_krw)}`).join(' / ')}</p><p>${esc(b.party_size)}인 · 한 끼 충족량 모델 ${Math.round(b.meal_fraction*100)}%. ${b.menu_diversity?'서로 다른 메뉴 구성의 음식 경험을 기존 개인 성향과 비교했습니다.':'단품·세트의 판매 단위에 따른 식사량입니다.'}</p><p class="ux-evidence-muted">식사량과 포만감은 실측이 아닌 공통 모델 추정입니다. ${b.excess_capacity>0?'주문 구성의 추정량이 한 끼 기준을 넘지만 섭취량을 추가로 높이지 않았습니다. 남긴 음식 여부는 알 수 없습니다. ':''}${b.limitation?'정확한 분량 자료가 없어 기존 한 끼 가정을 유지합니다. ':''}음료나 세트를 필수 구매로 추가하지 않습니다.</p></section>`;
}
function bhEvidenceHTML(m,c){
  if(window.HLAgentDecisionView?.record(m.raw)||m.plan?.trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_'))return bhAgentEvidenceHTML(m,c);
  const {L,plan,raw,decision:d,row,customer}=m,legacy=customer,packet=d&&d.packet,ctx=packet&&packet.context_factors||{},sampling=d&&d.sampling, research=typeof hlReasonView==='function'?hlReasonView(m.flow,c.customer_id,c.scene_index):null;
  const score=x=>x&&(x.final_with_lookahead??x.final_score),candidates=packet?packet.candidates:legacy?[legacy.choice,...(legacy.not_chosen||[])]:[];
  const selectedScore=row?score(row):legacy&&legacy.choice.score,others=candidates.filter(x=>packet?x.candidate_id!==d.selected_action&&x.world_allowed&&score(x)!=null:x.product_id!==legacy.choice.product_id&&x.feasible&&x.score!=null).slice().sort((a,b)=>(packet?score(b)-score(a):b.score-a.score)),alt=others[0];
  const terms=legacy?(legacy.reasons||[]).flatMap(t=>['review','common','assumption','transfer','out_of_scope'].filter(k=>Math.abs((t.parts||{})[k]||0)>1e-8).map(k=>({...t,amount:t.parts[k],group:k==='review'?'profile':k==='common'?'common':'assumption'}))):row?(row.terms||[]).map(t=>({...t,amount:t.value,group:t.kind==='profile'?'profile':t.kind==='context'?'state':/profile_and/.test(t.kind||'')?'mixed':'common'})):[];
  const major=terms.filter(t=>t.amount).slice().sort((a,b)=>Math.abs(b.amount)-Math.abs(a.amount)).slice(0,3),factIds=research?research.fact_ids:[...new Set(terms.filter(t=>t.amount).flatMap(t=>t.fact_ids||[]))],P=libP(c.customer_id)||{},Fx=P.engine&&P.engine.facts||{};
  const shownRows=c.ledger_tx_id?m.rows.filter(r=>r.row_id===c.ledger_tx_id):m.rows,known=shownRows.length&&shownRows.every(r=>r.status!=='금액 미확인'),paid=known?shownRows.reduce((n,r)=>n+r.paid_krw,0):null;
  const action=(L.receipts[c.customer_id].actions||[]).find(a=>a.action_id===c.action_id);
  const payment=!shownRows.length&&action&&action.purchase_status==='NO_PURCHASE'?'거래 없음':paid==null?'금액 미확인':paid>0?rcMoney(paid):shownRows.some(r=>r.purchase_status==='PACKAGE_INCLUDED'||r.status==='포함')?'포함 혜택':shownRows.every(r=>r.purchase_status==='FREE_USE'||r.status==='무료')?'무료 이용':'추가 결제 없음';
  const name=x=>packet?agU06ActionName(x.candidate_id):(x.venue_label||x.venue_id||'후보')+' · '+(x.product_label||'');
  const termList=group=>{const list=terms.filter(t=>t.group===group);return list.length?`<ul class="ux-evidence-terms">${list.map(t=>`<li><span>${esc(t.factor||t.kind||'계산 항')}</span><b class="${t.amount<0?'negative':'positive'}">${bhSigned(t.amount)}</b></li>`).join('')}</ul>`:'<p class="ux-evidence-muted">연결된 기여 항이 없습니다.</p>';};
  return `<div class="bv-case ux-exact-case"><div class="ux-evidence-nav"><label>현재 run의 고객<select id="bhRunCustomer">${Object.keys(m.flow.result.plans).map(id=>`<option value="${esc(id)}"${id===c.customer_id?' selected':''}>${esc(dno(id))} · ${esc(bvTypeOf(id))}</option>`).join('')}</select></label><label class="ux-evidence-action-select">방문 행동<select id="bhRunAction">${plan.scenes.map((s,i)=>`<option value="${i}"${i===c.scene_index?' selected':''}>${s.visit_day||1}일차 ${agHM(s.t0)} · ${esc(s.label)}</option>`).join('')}</select></label><button class="cf-btn" id="bhReturnFlow">같은 방문의 행동으로 돌아가기</button><button class="cf-btn" id="bhReturnRevenue">같은 실행 매출 집계</button></div>
  <section class="ux-evidence-hero"><div><small>${research?(research.live_execution?'새 방문 계산':'연구 저장 실행'):L.source==='stored_demo'?'저장 시연':'제품 실행 기록'} · ${esc(dno(c.customer_id))} · ${esc(raw.visit_date||'날짜 미기록')} ${agHM(raw.t0)} · ${c.visit_day}일차</small><h3>${esc(raw.label)}</h3>${shownRows[0]&&shownRows[0].product!==raw.label?`<p>${esc(shownRows[0].product)}</p>`:''}<span>${research?esc(research.method_label):sampling?'후보 가중치 추첨 · 최고 점수 선택으로 해석하지 않음':d?'후속 활동 포함 점수 비교':legacy?'기록된 선택 전 점수 비교':'정밀 결정 패킷 연결 미확인'}</span></div><div class="ux-evidence-metrics"><div><small>${research&&research.live_execution&&research.actual_final_method==='SHARED_TRANSITION_FINAL_CONTRACT'?'계획 평가값':research&&research.actual_final_method==='VALIDATED_LOCAL_PLAN_FINAL_ACTION_NO_REDRAW'?'후보 적합도 · 최종 계획 판단과 별도':packet&&packet.kind==='PLANNER'?'추첨 전 가중치':'선택 전 점수'}</small><b>${bhNumber(selectedScore)}</b></div><div><small>비교 대안</small><b>${alt?bhNumber(packet?score(alt):alt.score):'없음'}</b><em>${alt?esc(name(alt)):''}</em></div><div class="ux-evidence-money"><small>같은 원장의 가상 이용·결제</small><b>${payment}</b></div></div></section>
  ${research?hlReasonEvidenceHTML(research):''}
  ${bhMealBasketHTML(row,m.rows)}
  ${research&&research.actual_final_method==='VALIDATED_LOCAL_PLAN_FINAL_ACTION_NO_REDRAW'?'<p class="ux-evidence-muted">아래 점수·기여는 정량 후보의 적합도 계산입니다. 최종 LLM 계획 판단의 개인 인과 설명과 구분합니다.</p>':''}
  <div class="ux-evidence-major">${major.map(t=>`<article><small>${({profile:'후기 기반 프로파일 해석',state:'현재 환경·상태',common:'공통 행동 규칙',assumption:'모델 가정·출처 범위',mixed:'프로파일·공통 조건 혼합항'})[t.group]}</small><b>${esc(t.factor)}</b><strong>${bhSigned(t.amount)}</strong></article>`).join('')}</div>
  <div class="ux-evidence-grid"><section><h3>${research&&research.actual_final_method==='VALIDATED_LOCAL_PLAN_FINAL_ACTION_NO_REDRAW'?'계획 비교에 참조된 후기':'후기에 기록된 사실'}</h3><p class="ux-evidence-muted">${research&&research.actual_final_method==='VALIDATED_LOCAL_PLAN_FINAL_ACTION_NO_REDRAW'?'각 Fact가 이 순서를 선호하게 한 정도는 미확인입니다.':'과거 후기의 요지 · 이번 가상 행동의 직접 관측이 아님'}</p><div class="ux-evidence-facts">${factIds.length?factIds.map(id=>{const f=research&&research.personal_evidence&&research.personal_evidence[id]?{...(Fx[id]||{}),gist:research.personal_evidence[id].gist}:Fx[id],ok=f&&!f.hidden&&f.gist&&!(typeof LIB_SENS!=='undefined'&&LIB_SENS.test(f.gist));return `<article><p>${ok?esc(f.gist):'공개 가능한 Fact 요지 연결 미확인'}</p><small>${esc(id)}</small>${ok?`<button class="cf-link" data-bh-fact="${esc(id)}">프로필의 해당 사실 →</button>${libA(libUrl(f.post),'원문 ↗','sm')||'<em>원문 연결 미확인</em>'}`:''}</article>`;}).join(''):'<p>이번 선택 항에 연결된 Fact ID가 없습니다.</p>'}</div></section><section><h3>${research&&research.actual_final_method==='VALIDATED_LOCAL_PLAN_FINAL_ACTION_NO_REDRAW'?'정량 후보의 프로필 기여':'개인 프로파일 추론'}</h3>${termList('profile')}<details><summary>고정 상태 민감도 · 합산 인과효과 아님</summary><pre>${esc(JSON.stringify(row&&row.profile_feature_marginals||{},null,2))}</pre></details></section><section><h3>일반 행동 기저·공통 규칙</h3>${termList('common')}${terms.some(t=>t.group==='mixed')?`<h4>프로파일·공통 조건 혼합항</h4><p class="ux-evidence-muted">개인 기여와 공통 기여가 분리되지 않은 원본 항입니다.</p>${termList('mixed')}`:''}${terms.some(t=>t.group==='assumption')?`<h4>별도 모델 가정·출처 범위</h4>${termList('assumption')}`:''}</section><section><h3>당시 환경·이전 행동</h3>${termList('state')}<dl class="ux-state"><div><dt>판단 시각</dt><dd>${ctx.time!=null?agHM(ctx.time):'미기록'}</dd></div><div><dt>직전 식사</dt><dd>${ctx.last_meal?esc(ctx.last_meal.date+' '+ctx.last_meal.end):'정밀 기록 없음'}</dd></div><div><dt>완료한 이전 활동</dt><dd>${Array.isArray(ctx.activities)?ctx.activities.length+'건':'정밀 기록 없음'}</dd></div><div><dt>현재 목표·의도</dt><dd>${ctx.goal||ctx.intention?esc(JSON.stringify(ctx.goal||ctx.intention)):'별도 명시 기록 없음'}</dd></div></dl><details><summary>이전 행동·식사·행사 상태 전체</summary><pre>${esc(JSON.stringify(ctx,null,2))}</pre></details></section></div>
  <section class="ux-evidence-candidates"><div class="ux-evidence-section-title"><h3>실제로 열거한 후보 전체</h3><span>${candidates.length}개 · 점수와 확률은 별도 단위</span></div><div class="ux-evidence-table-scroll"><table><thead><tr><th>후보</th>${packet?(packet.kind==='PLANNER'?'<th>기본 가중치</th><th>맥락 가감</th><th>최종 가중치</th><th>추첨 확률</th>':'<th>기본 점수</th><th>맥락 가감</th><th>자체 점수</th><th>후속 포함</th><th>추첨 확률</th>'):'<th>선택 전 점수</th>'}<th>당시 이용 조건</th></tr></thead><tbody>${candidates.map(x=>{const selected=packet?x.candidate_id===d.selected_action:x.product_id===legacy.choice.product_id;return `<tr class="${selected?'selected':''}"><th>${esc(name(x))}${packet?`<code>${esc(x.candidate_id)}</code>`:''}${selected?' <small>실제 선택</small>':''}</th>${packet?`<td>${bhNumber(x.base_score)}</td><td>${bhSigned(x.context_adjustment)}</td><td>${bhNumber(x.final_score)}</td>${packet.kind==='PLANNER'?'':`<td>${bhNumber(x.final_with_lookahead)}</td>`}<td>${sampling&&sampling.probabilities&&sampling.probabilities[x.candidate_id]!=null?(100*sampling.probabilities[x.candidate_id]).toFixed(2)+'%':'해당 없음'}</td>`:`<td>${bhNumber(x.score)}</td>`}<td>${packet?x.world_allowed?'허용':esc(agU06BlockLabel(x.block_reason)):x.feasible===false?esc(agU06BlockLabel((x.blocked||[]).join(' · '))):'비교 후보'}</td></tr>`;}).join('')}</tbody></table></div></section>
  <details class="ux-evidence-raw"><summary>실행 식별자·정밀 계수·원본 trace·가격 출처</summary><h4>동일 실행 연결</h4><pre>${esc(JSON.stringify(c,null,2))}</pre><h4>${research?'후보 계산 엔진 기록 · 최종 판단 방식은 위 연구 기록 참조':'실제 엔진·호출 기록'}</h4><pre>${esc(JSON.stringify({engine:m.flow.engine,provider_calls:plan.m4&&plan.m4.provider_calls},null,2))}</pre><h4>선택 전 원본</h4><pre>${esc(JSON.stringify({decision:d||null,compatibility_customer:legacy||null,compatibility_excluded:m.run&&m.run.excluded||[],scene_basis:raw.basis||null},null,2))}</pre><h4>연결된 L5 거래</h4><pre>${esc(JSON.stringify(shownRows,null,2))}</pre></details><p class="ux-evidence-muted">연결된 제품 실행 기록만 표시합니다. 제품 trace에 없는 연구 계수·의도·원문 연결을 보충하지 않습니다.${BH.storageWarning?' '+esc(BH.storageWarning):''}</p></div>`;
}
function bhAgentEvidenceHTML(m,c){
  // Same page as the rule engine's evidence: summary → 개인 후기 → 당시 상황 → 비교 → 실행·소비. Reader text only.
  const rows=c.ledger_tx_id?m.rows.filter(r=>r.row_id===c.ledger_tx_id):m.rows,S=HLAgentDecisionView.story(m.raw);
  const nav=`<div class="ux-evidence-nav"><label>현재 run의 고객<select id="bhRunCustomer">${Object.keys(m.flow.result.plans).map(id=>`<option value="${esc(id)}"${id===c.customer_id?' selected':''}>${esc(dno(id))}</option>`).join('')}</select></label><label>방문 행동<select id="bhRunAction">${m.plan.scenes.map((s,i)=>`<option value="${i}"${i===c.scene_index?' selected':''}>${s.visit_day||1}일차 ${agHM(s.t0)} · ${esc(s.label)}</option>`).join('')}</select></label><button class="cf-btn" id="bhReturnFlow">같은 방문의 행동으로 돌아가기</button><button class="cf-btn" id="bhReturnRevenue">같은 실행 매출 집계</button></div>`;
  const paid=rows.reduce((n,r)=>n+(Number(r.paid_krw)||0),0);
  const receipt=rows.length?`<ul>${rows.map(r=>`<li>${esc(r.product)} · ${r.unit_price_krw==null?'단가 미기록':Number(r.unit_price_krw).toLocaleString()+'원'} × ${esc(r.billing_quantity??r.quantity??'수량 미기록')} · ${r.status==='금액 미확인'?'금액 미확인':rcMoney(r.paid_krw||0)} <small>${esc(typeof revTypeLabel==='function'?revTypeLabel(r):r.status||'')}</small></li>`).join('')}</ul><b>이 행동의 원장 합계 ${paid.toLocaleString()}원</b>`:'<p>이 행동에 연결된 구매가 없습니다.</p>';
  const step=(i,t,b)=>`<section class="dc-step" data-decision-step="${i}" id="decision-step-${i}"><h3>${t}</h3>${b}</section>`;
  const when=`${esc(dno(c.customer_id))} · ${c.visit_day||1}일차 · ${esc(m.raw.visit_date)} ${agHM(m.raw.t0)}`;
  if(!S)return `<div class="dc-page bv-case ux-exact-case">${nav}<div class="dc-head"><small>${when} · 자동 일정</small><h3>${esc(m.raw.label)}</h3><p>도착·이동·체크인·체크아웃처럼 방문 일정에 따라 진행된 장면입니다. 별도의 선택 판단이 없습니다.</p></div>${step('⑥','실행 결과와 소비',receipt)}</div>`;
  const metrics=`<div class="ev-decision-metrics">${S.metrics.map(([k,x])=>`<div><span>${esc(k)}</span><b>${esc(x)}</b></div>`).join('')}</div>`;
  const head=`<div class="dc-head" data-agent-story><small>${when} · ${esc(typeof agPlaceName==='function'?agPlaceName(m.raw.loc):'')}</small><h3>${esc(m.raw.label)}</h3><p>${esc(S.summary)}</p>${metrics}</div>`;
  const stages=[['②','개인 후기'],['③','당시 상황'],['④','비교와 선택'],['⑥','실행·소비']];
  const stageNav=`<nav class="ev-decision-stages" aria-label="판단 흐름">${stages.map(([id,label])=>`<button data-decision-scroll="${id}">${label}</button>`).join('<span aria-hidden="true">→</span>')}</nav>`;
  const result=`<dl class="dc-state">${S.result.map(([k,x])=>`<div><dt>${esc(k)}</dt><dd>${esc(x)}</dd></div>`).join('')}<div><dt>행동 시간</dt><dd>${esc(m.raw.visit_date)} ${agHM(m.raw.t0)}–${agHM(m.raw.t1)}</dd></div></dl>${receipt}`;
  return `<div class="dc-page bv-case ux-exact-case ev-llm-page">${nav}${head}${stageNav}${step('②','어떤 개인 후기를 참고했나',S.personal)}${step('③','당시 상황',S.state)}${step('④','무엇을 비교했고 왜 골랐나',S.comparison)}${step('⑥','실행 결과와 소비',result)}</div>`;
}

function bhWireEvidence(snapshot,c,m){
  const root=$('#bvBody');root.querySelector('#bhReturnFlow').onclick=bhReturnFlow;root.querySelector('#bhReturnRevenue').onclick=bhReturnRevenue;
  root.querySelector('#bhRunAction').onchange=e=>{const next=bhContextFor(snapshot,c.customer_id,+e.target.value,{returnTo:c.returnTo});bhActivate(snapshot,next);};
  root.querySelector('#bhRunCustomer').onchange=e=>{const next=bhContextFor(snapshot,e.target.value,0,{returnTo:c.returnTo});bhActivate(snapshot,next);};
  root.querySelectorAll('[data-bh-fact]').forEach(b=>b.onclick=()=>libOpen(c.customer_id,b.dataset.bhFact.split(','),bhContextURL(c),'reviews'));
}
function bhRouteMatch(){return /^#evidence\/run\//.test(location.hash)||/^#revenue\/run\//.test(location.hash)||/^#flow\/[^/]+\/[01]\/run\//.test(location.hash);}
async function bhApplyRoute(){
  if(window.HLNav&&history.state?.hillinkNav){HLNav.restoreHistory();return true;}
  if(!bhRouteMatch())return false;const token=++BH.routeToken,h=location.hash,run=decodeURIComponent(h.match(/\/run\/([^?]+)/)[1]),p=new URLSearchParams(h.split('?')[1]||''),snapshot=await bhRecall(run);if(token!==BH.routeToken||location.hash!==h)return true;
  if(!snapshot){BH.context={run_id:run,customer_id:p.get('customer_id')};setMode('evidence');return true;}
  const c={run_id:run};for(const k of ['customer_id','visit_id','stay_id','visit_date','action_id','action_code','decision_id','ledger_tx_id','returnTo'])c[k]=p.get(k);c.scene_index=Number(p.get('scene_index'));c.visit_day=Number(p.get('visit_day')||1);
  if(h.startsWith('#revenue/run/')){if(!bhModel(snapshot,c)){BH.context=c;setMode('evidence');return true;}BH.context=c;await bhReturnRevenue(false);return true;}
  if(!bhModel(snapshot,c)){BH.context=c;setMode('evidence');return true;}
  if(h.startsWith('#flow/')){BH.context=c;await bhRestore(snapshot,c);}else bhActivate(snapshot,c,false);return true;
}
window.addEventListener('popstate',()=>{if(bhRouteMatch())bhApplyRoute();});
window.addEventListener('hashchange',()=>{if(bhRouteMatch())bhApplyRoute();});
(async()=>{await HILLINK_APP_READY;if(typeof DS!=='undefined')await DS.ready;if(bhRouteMatch())await bhApplyRoute();})();

const bvJosa = w => { const ch = String(w || "").replace(/[^가-힣]+$/, "").slice(-1), c = ch.charCodeAt(0); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? "을" : "를"; };   // 받침 있으면 '을'
const bvN = v => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2);
function bvCaseBody(pid, R, c, FL) {
  const P = (LIBV.data ? libP(pid) : null) || {}, Fx = (P.engine && P.engine.facts) || {};
  const T = c.reason_totals || {}, ch = c.choice, o = c.best_other_venue, ru = c.runner_up;
  const reasons = [...c.reasons], revR = reasons.filter(r => Math.abs(r.parts.review || 0) > 0.005).sort((a, b) => Math.abs(b.parts.review) - Math.abs(a.parts.review));
  const used = [...new Set(revR.flatMap(r => r.fact_ids || []))];
  const fOk = f => Fx[f] && !Fx[f].hidden && Fx[f].gist && !(typeof LIB_SENS !== "undefined" && LIB_SENS.test(Fx[f].gist));
  const llm = /llm/i.test(String(c.decision_engine || "") + String(R.engine || ""));
  const vName = R.turn === "event" && ch.venue_id === "FOREST" ? "와인페어" : agShort(ch.product_label);
  // 스냅샷
  const close = o && o.margin < 0.15;
  const snap = `<section class="bv-snap"><div class="bv-sn-l"><div class="bv-kick">${esc(dno(pid))} · ${esc(BH_TURN[R.turn] || R.turn)} ${esc(R.time || "")} · ${esc(ch.venue_label)}</div>
      <h3>${esc(vName)}${bvJosa(vName)} 고른 이유</h3>
      <div class="bv-chips"><span class="bv-chip">${BH.e ? "와인페어가 열린 날" : "행사 없는 날"}</span><span class="bv-chip ${Math.abs(T.review) > 0.000005 ? "rv" : ""}">${Math.abs(T.review) > 0.000005 ? `후기 근거 ${bvN(T.review)}` : "공통 규칙에 따른 결정"}</span></div></div>
    <div class="bv-sn-r"><table class="bv-cmp"><tr class="on"><th>선택</th><td>${esc(agShort(ch.product_label))}</td><td class="n">${ch.score.toFixed(2)}</td></tr>${ru ? `<tr><th>다음 대안</th><td>${esc(agShort(ru.product_label))}</td><td class="n">${ru.score.toFixed(2)}</td></tr>` : ""}</table>
      <div class="bv-gap">${o ? `<div>다른 업장 최고 대안과 점수 차 <b>${o.margin.toFixed(2)}</b>${close ? " · 근소" : ""}</div>` : ""}<span>점수는 효용 차이 · 확률 아님</span></div></div></section>`;
  // ① 근거 글 — 이번 결정에 쓰인 사실이 나온 글(같은 작성자) → 나머지는 관찰된 배경
  const posts = {}; used.forEach(f => { const pp = Fx[f] && Fx[f].post; const k = pp || "_none"; (posts[k] = posts[k] || []).push(f); });
  const evByPost = {}; [...(P.wh_events || []), ...(P.other_events || [])].forEach(ev => (ev.posts || []).forEach(pp => { (evByPost[pp] = evByPost[pp] || []).push(ev); }));
  const startU = typeof libStartUrl === "function" ? libStartUrl(P) : null;
  const postRows = Object.entries(posts).filter(([k]) => k !== "_none").map(([pp, fs]) => { const u = typeof libUrl === "function" ? libUrl(pp) : null, ev = (evByPost[pp] || [])[0], wh = fs.some(f => Fx[f].wh);
    return `<tr><td><span class="bv-src ${wh ? "wh" : ""}">${wh ? "워커힐 후기" : "같은 작성자 · 다른 글"}</span></td><td>${esc(libShort ? libShort((ev && ev.detail) || Fx[fs[0]].gist, 70) : (ev && ev.detail) || "")}</td><td class="n">${fs.filter(fOk).length}</td><td>${u ? libA(u, "원문 보기 ↗", "sm") : `<em class="bv-mute">원문 연결 확인 중</em>`}</td></tr>`; });
  const loose = (posts._none || []).filter(fOk);
  const s1 = `<section class="bv-sec"><div class="bv-sh"><i>1</i><h4>근거 글</h4><span>이번 결정에 쓰인 후기 사실 ${used.length}개가 나온 글 · 같은 작성자 기준</span></div>
    <div class="bv-src-top">${startU ? libA(startU, "대표 후기 원문 보기 ↗", "lb-srcbtn") : `<span class="lb-srcbtn off">원문 연결 확인 중</span>`}<span class="bv-mute">원문은 외부 블로그 · 아래 문장은 후기에서 추출 · 검수한 요약(원문 인용 아님)</span></div>
    ${postRows.length ? `<table class="bv-tbl"><thead><tr><th>글</th><th>확인된 행동 요지</th><th class="n">쓰인 사실</th><th>원문</th></tr></thead><tbody>${postRows.slice(0, 5).join("")}</tbody></table>${postRows.length > 5 ? `<details class="bv-more bv-pmore"><summary>근거 글 ${postRows.length - 5}편 더 보기 <span>모두 ${postRows.length}편 · 같은 작성자</span></summary><table class="bv-tbl"><tbody>${postRows.slice(5).join("")}</tbody></table></details>` : ""}` : ""}
    ${loose.length ? `<div class="bv-facts"><div class="bv-lab">${postRows.length ? "글 연결이 없는 사실" : "대표 후기에서 추출한 사실(글별 연결은 이 고객 자료에 없음)"}</div><ul>${loose.slice(0, 2).map(f => `<li><code>${esc(f)}</code>${esc(Fx[f].gist)}</li>`).join("")}</ul>${loose.length > 2 ? `<details class="bv-more"><summary>사실 ${loose.length - 2}개 더 보기</summary><ul>${loose.slice(2).map(f => `<li><code>${esc(f)}</code>${esc(Fx[f].gist)}</li>`).join("")}</ul></details>` : ""}</div>` : ""}
    ${!used.length ? `<p class="bv-empty">이 결정에는 후기 사실이 점수에 연결되지 않았습니다 — 공통 규칙에 따른 결정입니다.</p>` : ""}</section>`;
  // ② 성향 해석 — 관측 사실 | 프로파일 해석 | 반례 · 한계 | 이번 기여
  const bars = (c.persona && c.persona.bars) || [];
  const traits = P.traits || [];
  const rowT = r => { const b = bars.find(x => x.key === r.facet), fs = (r.fact_ids || []).filter(fOk), tr = traits.find(t => (t.support || []).length && (r.factor || "").split(/[ ·(]/).some(w => w.length > 1 && (t.trait || "").includes(w)));
    return `<tr><td><b>${escP(r.factor)}</b>${r.note ? `<div class="bv-mute">${esc(r.note)}</div>` : ""}</td><td>${fs.length ? `${esc(libShort(Fx[fs[0]].gist, 46))}${fs.length > 1 ? ` <span class="bv-mute">외 ${fs.length - 1}건</span>` : ""}` : `<span class="bv-mute">사실 문장 비공개 · 연결 없음</span>`}</td>
      <td>${b ? `<div class="bv-bar"><i style="width:${Math.round(b.level * 100)}%"></i></div><span class="bv-mute">${esc(b.label)} · 근거 ${b.evidence_count}건</span>` : `<span class="bv-mute">성향 막대 밖 — 후기 사실이 이 항에 직접 연결</span>`}</td>
      <td>${tr && (tr.counter || [])[0] ? esc(libShort(tr.counter[0], 40)) : `<span class="bv-mute">${traits.length ? "반례 기록 없음" : "반례 분석 전"}</span>`}</td><td class="n rv">${bvN(r.parts.review)}</td></tr>`; };
  const s2 = `<section class="bv-sec"><div class="bv-sh"><i>2</i><h4>어떻게 성향으로 읽었나</h4><span>관측 사실과 프로파일 해석을 나눠 봅니다</span></div>
    ${revR.length ? `<table class="bv-tbl bv-mx"><thead><tr><th>성향 · 제약 항목</th><th>관측 사실(후기 요약)</th><th>프로파일 해석(엔진 입력)</th><th>반례 · 한계</th><th class="n">이번 기여</th></tr></thead><tbody>${revR.map(rowT).join("")}</tbody></table>` : `<p class="bv-empty">이번 결정에 후기 성향이 더해진 항이 없습니다.</p>`}</section>`;
  // ③ 계산 기여 — 항별 분해 막대 + 후보 비교
  const rs = reasons.slice().sort((a, b) => Math.abs(b.value) - Math.abs(a.value)), mx = Math.max(0.01, ...rs.map(r => Math.abs(r.value)));
  const seg = r => ["common", "review", "assumption"].filter(k => Math.abs(r.parts[k] || 0) > 1e-6).map(k => `<i class="s-${k}${r.parts[k] < 0 ? " neg" : ""}" style="width:${(Math.abs(r.parts[k]) / mx * 100).toFixed(1)}%" title="${({ common: "공통 규칙", review: "후기 근거", assumption: "설계값" })[k]} ${r.parts[k].toFixed(2)}"></i>`).join("");
  const cands = [ch, ...(c.not_chosen || [])].filter(x => x && x.score != null).slice(0, 5);
  const s3 = `<section class="bv-sec"><div class="bv-sh"><i>3</i><h4>계산에 실제로 더해진 값</h4><span>엔진 기록(reasons · reason_totals) 그대로 · 원문 인용만으로는 점수에 넣지 않음</span></div>
    <div class="bv-tot"><div><b class="rv">${bvN(T.review || 0)}</b><span>후기 근거(개인)</span></div><div><b>${bvN(T.common || 0)}</b><span>공통 규칙(가격 · 끼니 · 이동 · 다음 일정)</span></div>${(T.assumption || 0) > 0.005 ? `<div><b class="as">${bvN(T.assumption)}</b><span>설계값</span></div>` : ""}<div><b>${ch.score.toFixed(2)}</b><span>선택 점수</span></div></div>
    <div class="bv-calc">${rs.map(r => `<div class="bv-cr"><span class="bv-cf">${escP(r.factor)}${r.facet ? `<code>${esc(r.facet)}</code>` : ""}</span><span class="bv-cb">${seg(r)}</span><b class="n">${bvN(r.value)}</b></div>`).join("")}</div>
    <div class="ag-skey"><span><i class="s-review"></i>후기 근거</span><span><i class="s-common"></i>공통 규칙</span><span><i class="s-assumption"></i>설계값</span></div>
    <details class="bv-more"><summary>후보 비교 · 결정 엔진</summary><table class="bv-tbl"><thead><tr><th>후보</th><th>업장</th><th class="n">점수</th></tr></thead><tbody>${cands.map((x, i) => `<tr class="${i === 0 ? "on" : ""}"><td>${esc(agShort(x.product_label))}</td><td>${esc(x.venue_label)}</td><td class="n">${x.score.toFixed(2)}</td></tr>`).join("")}</tbody></table>
      <p class="bv-mute">결정 엔진: ${esc(c.decision_engine || "-")} · 하루 엔진: ${esc(R.engine || FL.engine || "-")}</p></details></section>`;
  // ④ 근거 상태 — 실측 · 정성 추론 · 미사용 · 연구 중
  const notUsed = bars.filter(b => b.status === "observed" && !revR.some(r => r.facet === b.key)).map(b => b.label);
  const sc = ((FL.plans || {})[pid] || {}).scenes || [], nGen = sc.filter(s => s.layer === "generated").length, nRev = sc.filter(s => s.layer === "review").length, nEng = sc.filter(s => s.layer === "engine").length;
  const s4 = `<section class="bv-sec"><div class="bv-sh"><i>4</i><h4>부족한 근거는 어떻게 채웠나</h4><span>실측 · 추론 · 미사용 · 연구 중을 나눕니다</span></div>
    <div class="bv-4"><div class="k ok"><b>실측 사실</b><p>이번 점수에 연결된 후기 사실 <strong>${used.length}개</strong></p></div>
      <div class="k inf"><b>정성 추론</b><p>${traits.length ? `반복 취향 ${traits.length}개 · 조건부 규칙 ${(P.rules || []).length}개(분석 해석 — 이번 점수에 직접 쓰이지 않음)` : "반복 취향 분석 전 — 엔진 성향 수준만 사용"}</p></div>
      <div class="k no"><b>사용되지 않음</b><p>${notUsed.length ? `측정됐지만 이번 결정에 쓰이지 않은 성향: ${notUsed.map(esc).join(" · ")}` : "측정된 성향은 모두 이번 결정에 관여"}</p></div>
      <div class="k rs"><b>연구 중</b><p>${llm ? "LLM 보완 실행됨" : "이번 결과는 LLM 추론을 사용하지 않았습니다"} · 후기에 없는 하루 장면은 규칙 기반 계획기가 채움(이 하루: 엔진 결정 ${nEng} · 후기 장면 ${nRev} · 생성 장면 ${nGen} [시뮬레이션 가정])</p></div></div></section>`;
  // ⑤ 그래서 이번 행동
  const bg = [...(P.wh_events || [])].filter(ev => !(ev.facts || []).some(f => used.includes(f)) && !(typeof LIB_SENS !== "undefined" && LIB_SENS.test(ev.detail || ""))).slice(0, 3);
  const s5 = `<section class="bv-sec bv-fin"><div class="bv-sh"><i>5</i><h4>그래서 이번 행동</h4></div>
    <p class="bv-con"><b>${esc(agShort(ch.product_label))}</b> — ${esc((c.why || "").replace(/\s+/g, " "))}</p>
    ${revR.length ? `<div class="bv-why"><span class="bv-lab">이번 선택의 이유(실제 기여)</span>${revR.slice(0, 3).map(r => `<span class="bv-chip rv">${escP(r.factor)} ${bvN(r.parts.review)}</span>`).join("")}</div>` : `<div class="bv-why"><span class="bv-lab">이번 선택의 이유</span><span class="bv-chip">공통 규칙에 따른 결정 · 실제 개인화 점수 기여 0</span></div>`}
    ${bg.length ? `<div class="bv-bg"><span class="bv-lab">관찰된 배경(결정 기여 미확인)</span><ul>${bg.map(ev => `<li>${esc(libShort(ev.detail, 70))}</li>`).join("")}</ul></div>` : ""}
    <div class="bv-act"><button type="button" class="cf-btn" id="bvProf">고객 프로필 보기</button>${used.length ? `<button type="button" class="cf-btn" data-ff="${esc(used.join(","))}">프로필에서 이 사실들 보기</button>` : ""}</div></section>`;
  return `<div class="bv-case">${snap}${s1}${s2}${s3}${s4}${s5}</div>`;
}

// ---------------------------------------------------------------- B. 엔진 재현 방법
const BV_STEPS = [
  { t: "후기 · 연관 글 확보", st: "현재 사용 중", s: "ok", what: "같은 작성자의 워커힐 후기를 먼저, 이어서 연관 호텔 · 다이닝 · 여행 글을 모읍니다. 광고성 글과 같은 체류를 여러 번 쓴 글은 따로 표시합니다.", fields: "audit.walkerhill · audit.unique_posts · wh_events[].posts", plan: "계획: 최근 최대 50개 글까지(고객마다 확보량이 다름 — 실제 확보량은 고객별 판단 근거의 근거 글 표)" },
  { t: "사실 · 행동 · 시점 추출", st: "현재 사용 중", s: "ok", what: "글에서 실제 한 일(이용 · 주문 · 참여 · 구매)과 시점을 사실 ID 단위로 뽑고, 같은 방문인지 연결 상태(확인 · 추정 · 미확인)를 붙입니다.", fields: "engine.facts{id: gist · post · wh} · wh_events[].stage · link", plan: "사실은 요약 문장이며 원문 인용이 아님 · 아동 · 건강 문장은 화면에서 제외" },
  { t: "다층 프로파일", st: "현재 사용 중", s: "ok", what: "여러 경험에서 반복된 선호 · 제약을 성향 수준(0~1)과 근거 건수로 정리하고, 반례와 확인 안 된 성향은 따로 둡니다.", fields: "persona.bars[key · level · evidence_count · status] · traits[support · counter]", plan: "신뢰도 · 근거 강도 · 효용 가중치를 한 숫자로 합치지 않음 — 계수화 v0 개선은 설계 중" },
  { t: "월드 · 행사 조건 · 후보", st: "현재 사용 중", s: "ok", what: "날짜 · 시각 · 투숙 여부 · 행사 운영 · 가격 · 이용 자격으로 그때 고를 수 있는 후보만 남깁니다. 자격이 안 되면 점수 비교에서 빠집니다.", fields: "runs[].conditions · not_chosen[].feasible · blocked · price", plan: "와인페어는 2026 가을 운영 기간(10/25 종료) 기준 저장 시나리오" },
  { t: "행동 계산 · 보완", st: "규칙 사용 중 · LLM 연구 중", s: "mix", what: "실제 기록에 따라 점수 비교 또는 후보 가중치 추첨으로 선택합니다. 공통 규칙과 후기 기여, 선택 확률은 서로 다른 값입니다. 후기에 없는 장면은 규칙 기반 계획기가 채웁니다. LLM 보완은 근거 제한 · 후보 제약 · 출력 검증을 거치는 연구 단계이며, 저장된 시연 결과에는 쓰이지 않았습니다.", fields: "reasons[factor · facet · parts{common · review · assumption} · fact_ids] · reason_totals · decision_engine", plan: "llm_backend: rules(LLM 호출 0) — 저장된 시연 결과는 규칙 계산이며 LLM 혼합 결과가 아님" },
  { t: "결정 기록 · 검증", st: "현재 사용 중(재현성) · 개인화 유효성 별도", s: "mix", what: "선택 · 비선택 대안 · 항별 기여 · 사실 ID 를 결정 기록으로 남겨 되짚습니다. 같은 입력이면 같은 결과인지(재현성)와, 후기 성향이 실제로 선택을 바꾸는지(개인화 유효성)는 따로 검증합니다.", fields: "runner_up · best_other_venue · score_basis · 저장본 entry_sha", plan: "" },
];
async function bvEngine(ids) {
  const i=BH.step,S=BV_STEPS[i],exTxt="";
  $("#bvBody").innerHTML = `<div class="bv-eng">
    <ol class="bv-flow">${BV_STEPS.map((x, k) => `<li class="${k === i ? "on" : ""} ${x.s}"><button type="button" data-st="${k}"><i>${k + 1}</i><b>${esc(x.t)}</b><em>${esc(x.st)}</em></button></li>`).join("")}</ol>
    <section class="bv-stp"><div class="bv-stp-h"><span class="bv-stn">${i + 1} / 6</span><h3>${esc(S.t)}</h3><span class="bv-stt ${S.s}">${esc(S.st)}</span></div>
      <p class="bv-stw">${esc(S.what)}</p>
      <dl class="bv-kv">${exTxt ? `<div><dt>지금 고른 고객에서</dt><dd>${esc(exTxt)}</dd></div>` : ""}${S.plan ? `<div><dt>범위</dt><dd>${esc(S.plan.replace(/llm_backend: rules\(LLM 호출 0\) — /, ""))}</dd></div>` : ""}</dl>
      <details class="bv-more"><summary>기술 상세 · 실제 사용된 데이터 항목</summary><p class="bv-mute"><code>${esc(S.fields)}</code></p></details></section>
    <section class="bv-sec"><div class="bv-sh"><h4>재현성과 개인화 유효성은 다른 검증입니다</h4></div>
      <table class="bv-tbl"><thead><tr><th>질문</th><th>방법</th><th>현재 상태</th></tr></thead><tbody>
        <tr><td>같은 입력이면 같은 결정인가(재현성)</td><td>기존 11명 × 결정 264개를 다시 계산해 기록과 대조 · 저장본 26개 바이트 대조</td><td>과거 저장 시연의 검증 기록 · 현재 선택의 증명과 별도</td></tr>
        <tr><td>후기 성향이 실제로 선택을 바꾸는가(개인화 유효성)</td><td>후기 근거를 뺀 대조군(no-sidecar)과 비교 · 결정 시점에 허용된 정보만 사용 · 정답지 누출 방지</td><td><b class="rs">별도 게이트 · 검증 중</b></td></tr>
        <tr><td>후기에 없는 행동을 LLM 으로 보완하면 나아지는가</td><td>근거 제한 · 후보 제약 · 출력 검증 뒤 규칙 결과와 비교</td><td><b class="rs">연구 중</b> · 시연 결과에는 쓰지 않음</td></tr></tbody></table></section></div>`;
  $$("#bvBody .bv-flow [data-st]").forEach(b => b.onclick = () => { BH.step = +b.dataset.st; bvEngine(ids); });
}

// A new user navigation owns the screen; late run restoration must not reclaim it.
if(typeof document!=='undefined')document.addEventListener('click',event=>{
 const nav=event.target.closest('header [data-mode],#libBack,#sitHome');if(!nav)return;
 BH.navToken=(BH.navToken||0)+1;BH.routeToken++;
 // The header previously called agEnter directly, resetting to arrival even
 // though the evidence return button and history route restored the same run.
 if(nav.matches('header [data-mode="day"]')&&BH.context&&(MODE==='evidence'||(MODE==='library'&&new URLSearchParams(location.hash.split('?')[1]||'').has('evidence_ref')))){
  event.preventDefault();event.stopImmediatePropagation();bhReturnFlow();
 }
},true);

// Keep evidence detail panels open across review → browser back (UI state only; no data or route change).
(function(){
 if(typeof document==='undefined'||typeof document.addEventListener!=='function'||typeof MutationObserver==='undefined')return;
 const KEY='hl:evidence-open',root=()=>document.querySelector('#evidenceView');
 const read=()=>{try{return JSON.parse(sessionStorage.getItem(KEY)||'{}');}catch(_){return {};}};
 const write=v=>{try{sessionStorage.setItem(KEY,JSON.stringify(v));}catch(_){}};
 const route=()=>(location.hash.match(/^#evidence\/[^?]*/)||[''])[0];
 const label=d=>{const s=d.querySelector(':scope > summary');return s?s.textContent.replace(/\s+/g,' ').trim().slice(0,80):null;};
 document.addEventListener('toggle',e=>{const d=e.target,r=root();if(!r||!(d instanceof HTMLDetailsElement)||!r.contains(d)||!route())return;const k=label(d);if(!k)return;const all=read(),m=all[route()]||{};if(d.open)m[k]=1;else delete m[k];all[route()]=m;const keys=Object.keys(all);if(keys.length>40)delete all[keys[0]];write(all);},true);
 let pending=0;const restore=()=>{pending=0;const r=root(),m=read()[route()];if(!r||!m)return;r.querySelectorAll('details').forEach(d=>{const k=label(d);if(k&&m[k]&&!d.open)d.open=true;});};
 const start=()=>{const r=root();if(!r)return;new MutationObserver(()=>{if(!pending)pending=requestAnimationFrame(restore);}).observe(r,{childList:true,subtree:true});};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
