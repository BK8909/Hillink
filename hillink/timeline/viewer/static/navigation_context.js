/* One navigation owner. Run payloads stay in memory/the existing run store;
 * history contains opaque entry/run identifiers only, never reviews or profiles. */
(function(root){'use strict';
function historyMarker(e){return {hillinkNav:{id:e.id,run:e.run,view:e.view}};}
function sameAction(s,c,r){return !!(s&&r&&s.run_id===c.run_id&&(s.sel||s.one)===c.customer_id&&s.day===(c.visit_day||1)&&s.scene?.t0===r.t0&&s.scene?.t1===r.t1&&s.scene?.act===r.act);}
function sceneMatches(x,s){return !!s&&x.t0===s.t0&&x.t1===s.t1&&x.act===s.act&&(s.k==null||x.k===s.k);}
// History owns mutable UI state, not another copy of the immutable engine payload.
function copyEntry(e){if(!e)return e;return {...e,ui:structuredClone(e.ui||{}),flow:e.flow?structuredClone(e.flow):e.flow,context:e.context?structuredClone(e.context):e.context,profile:e.profile?structuredClone(e.profile):e.profile,revenue:e.revenue?{...e.revenue,fields:structuredClone(e.revenue.fields),request:structuredClone(e.revenue.request)}:e.revenue};}
// Native visit records need not contain the legacy screen's editable lever map.
// Copy before adding UI defaults: the saved request, conditions and ledger stay immutable.
function flowControls(conditions){const c=structuredClone(conditions||{});c.product_levers=c.product_levers??{};return c;}
function initialAction(result){const ids=Object.keys(result.plans||{}),pid=ids.find(id=>(result.plans[id].scenes||[]).length);if(!pid)return null;const scene=result.plans[pid].scenes[0];return {customer_id:pid,scene_index:0,visit_day:scene.visit_day||1,many:ids.length>1};}

function revenueRequest(rev){return structuredClone(rev.latest?.flow?.ledger?.run_id===rev.ledger?.run_id?rev.latest.request:rev.flow?.request||rev.ledger?.context||{});}
if(typeof module!=='undefined'&&module.exports){module.exports={historyMarker,sameAction,sceneMatches,copyEntry,flowControls,initialAction,revenueRequest};return;}
const clone=v=>v==null?v:structuredClone(v);
const REV_KEYS=['scope','ids','selected','duration','scenario','completedKey','completedScenario','department','venue','product','customer','analysisContext','analysisCustomer','analysisExpanded','transactions','opsDate','opsHour','hourFilter','rollRow','rollSelection','rollView','flowExpanded','detailPanel','setupOpen','pickerOpen','amountBars','search','personaSearch','uxActivityOpen'];
const S={entries:new Map(),runs:new Map(),last:new Map(),current:null,activeRun:null,busy:false,serial:0,queue:Promise.resolve(),error:null};
const raw={mode:setMode,open:libOpen,activate:bhActivate};
const rootFor=v=>({flow:'main',revenue:'#opxView',evidence:'#evidenceView',reviews:'#libraryView'})[v];
function path(el,base){const parts=[];while(el&&el!==base){const p=el.parentElement;if(!p)return null;parts.unshift(el.tagName.toLowerCase()+':nth-child('+([...p.children].indexOf(el)+1)+')');el=p;}return parts.join(' > ');}
function ui(v){const b=document.querySelector(rootFor(v));if(!b)return {};return {scroll:[b,...b.querySelectorAll('*')].filter(e=>e.getClientRects().length&&(e.scrollTop||e.scrollLeft)).map(e=>[e===b?'':path(e,b),e.scrollTop,e.scrollLeft]),details:[...b.querySelectorAll('details')].filter(e=>(v!=='flow'||e.closest('#panel'))&&(v!=='revenue'||!e.matches('[data-analysis-group]'))).map(e=>[path(e,b),e.open]),controls:v==='reviews'?[...b.querySelectorAll('.ev-review-library input,.ev-review-library select')].map(e=>[path(e,b),e.value]):[],topic:v==='reviews'?b.querySelector('[data-review-topic][aria-pressed="true"]')?.dataset.reviewTopic:null};}
function applyUI(v,u={}){const b=document.querySelector(rootFor(v));if(!b)return;const find=p=>p?b.querySelector(':scope > '+p):b;
 if(v==='reviews'){
  if(u.topic!=null)[...b.querySelectorAll('[data-review-topic]')].find(e=>e.dataset.reviewTopic===u.topic)?.click();
  for(const [p,value] of u.controls||[]){const e=find(p);if(e){e.value=value;e.dispatchEvent(new Event(e.tagName==='INPUT'?'input':'change',{bubbles:true}));}}
 }
 for(const [p,open] of u.details||[]){const e=find(p);if(e?.tagName==='DETAILS')e.open=open;}
 for(const [p,top,left] of u.scroll||[]){const e=find(p);if(e){e.scrollTop=top;e.scrollLeft=left;}}
}
function remember(flow){if(!flow?.ledger?.run_id||!flow.result?.plans)return null;const id=flow.ledger.run_id;if(!S.runs.has(id))S.runs.set(id,{...flow,result:{...flow.result},request:clone(flow.request)});return id;}
function currentScene(pid=AG.mode==='agent'?AG.one:AG.sel){
 if(!pid)return null;
 if(AG.mode==='agents'){const p=agManyPos(pid,AG.manyT??AG.nowMin);return p&&!p.away&&!p.moving?p.sc:null;}
 return agScenes(pid).find(s=>s.si===AG.si)||null;
}
function flowState(){const sc=currentScene();return {run_id:AG.flow.ledger.run_id,mode:AG.mode,one:AG.one,sel:AG.sel,many:[...AG.many],day:AG.visitDay||1,duration:AG.duration,cond:clone(AG.cond),fix:AG.fix,seed:AG.seed,engine:AG.engine,visitRequest:clone(AG.visitRequest),si:AG.si,fraction:AG.f,nowMin:AG.nowMin,manyTime:AG.manyT,dialogue:root.HLDialogue?.capture?.(),scene:sc?{si:sc.si,t0:sc.t0,t1:sc.t1,act:sc.act,k:sc.k,loc:sc.loc,day:sc.visit_day||AG.visitDay||1}:null};}
function revenueState(){REV.analysisExpanded=new Set([...document.querySelectorAll('#opxView [data-analysis-group][open]')].map(e=>e.dataset.analysisGroup));const fields={};for(const k of REV_KEYS)fields[k]=clone(REV[k]);return {fields,ledger:REV.ledger,flow:REV.flow,baseline:REV.baseline,comparison:REV.comparison,request:revenueRequest(REV)};}
function view(){return MODE==='agent'||MODE==='agents'?'flow':MODE==='opx'?'revenue':MODE==='evidence'?'evidence':MODE==='library'&&LIBV.open?'reviews':null;}
function stamp(e,replace=false){S.entries.set(e.id,e);S.current=e.id;S.activeRun=e.run;S.last.set(e.run+'|'+e.view,e.id);const state=historyMarker(e);history[replace?'replaceState':'pushState'](state,'',e.url);}
function capture(write=true){const v=view();if(!v)return null;let run,entry={view:v,url:location.hash,ui:ui(v)};
 if(v==='flow'){run=remember(AG.flow);if(!run)return null;agPause();entry.flow=flowState();}
 if(v==='revenue'){if(!REV.ledger||!REV.flow)return null;run=remember({result:REV.flow,ledger:REV.ledger,request:revenueRequest(REV),engine:REV.flow.engine});entry.revenue=revenueState();}
 if(v==='evidence'){run=BH.context?.run_id;entry.context=clone(BH.context);}
 if(v==='reviews'){run=S.activeRun||BH.context?.run_id;entry.profile={id:LIBV.open,facts:[...LIBV.hl],ref:new URLSearchParams(location.hash.split('?')[1]||'').get('evidence_ref'),tab:new URLSearchParams(location.hash.split('?')[1]||'').get('tab')};}
 if(!run)return null;entry.run=run;const prior=S.entries.get(S.current);entry.id=prior?.view===v&&prior.run===run?prior.id:'nav-'+(++S.serial);
 if(!write&&prior)entry.url=prior.url;
 S.entries.set(entry.id,entry);S.current=entry.id;S.activeRun=run;S.last.set(run+'|'+v,entry.id);
 if(write)history.replaceState(historyMarker(entry),'',entry.url);return entry;
}
const last=(run,v)=>S.entries.get(S.last.get(run+'|'+v));
function error(message){S.error=message;document.getElementById('hlNavError')?.remove();const el=document.createElement('div');el.id='hlNavError';el.setAttribute('role','alert');el.style.cssText='position:fixed;top:76px;left:15%;right:15%;z-index:10000;background:#fff8ee;border:1px solid #bd6755;padding:18px;border-radius:12px;color:#54352d';el.textContent=message+' ';const b=document.createElement('button');b.textContent='닫기';b.onclick=()=>el.remove();el.append(b);document.body.append(el);}
async function source(run){if(S.runs.has(run))return S.runs.get(run);const saved=await bhRecall(run);if(saved?.flow){remember(saved.flow);return S.runs.get(run);}throw Error('해당 실행 기록이 이 탭에 없습니다. 기존 실행을 보관한 화면에서 다시 열어 주세요. 새 계산은 시작하지 않았습니다.');}
function compatible(state,c,flow){return sameAction(state,c,flow.result.plans[c.customer_id]?.scenes[c.scene_index]);}
function actionState(run,c,flow){const saved=last(run,'flow')?.flow;if(compatible(saved,c,flow))return clone(saved);const r=flow.result.plans[c.customer_id]?.scenes[c.scene_index];if(!r)throw Error('이 실행에서 요청한 행동을 찾을 수 없습니다. 다른 실행으로 대체하지 않았습니다.');return {...clone(saved||{}),run_id:run,mode:saved?.mode||'agent',one:c.customer_id,sel:c.customer_id,many:saved?.many||Object.keys(flow.result.plans),day:c.visit_day||1,duration:flow.request.duration||flow.ledger.context.duration,cond:clone(saved?.cond||flow.result.runs.find(x=>x.visit_day===(c.visit_day||1))?.conditions||{}),si:null,fraction:0,nowMin:r.t0,manyTime:r.t0,dialogue:null,scene:{t0:r.t0,t1:r.t1,act:r.act,k:r.k,loc:r.loc,day:c.visit_day||1}};}
async function restoreFlow(e,flow){const s=e.flow;if(!s)throw Error('고객 흐름의 재생 위치를 복원할 기록이 없습니다.');const mode=s.mode==='agents'?'agents':'agent',r=flow.result,day=s.day||1,v=flow.ledger.visit?agVisitDayView(r,day):r;
 AG.autorun=false;AG.flow={...flow,request:clone(flow.request)};AG.visitData=flow.ledger.visit?r:null;AG.one=s.one;AG.sel=s.sel;AG.many=new Set(s.many||Object.keys(r.plans));AG.duration=s.duration;AG.cond=flowControls({...v.runs[0]?.conditions,...s.cond});AG.fix=s.fix??false;AG.seed=s.seed??flow.request.seed;AG.engine=s.engine||'autonomy';AG.visitRequest=clone(s.visitRequest);AG.visitDay=day;
 AG.keep[mode]={runs:v.runs,sel:s.sel,plans:v.plans,visits:v.visits,flow:AG.flow};await raw.mode(mode);
 if(flow.ledger.visit)agVisitDaySelect(day);AG.flow={...flow,request:clone(flow.request)};AG.one=s.one;AG.sel=s.sel;AG.many=new Set(s.many||Object.keys(r.plans));AG.visitRequest=clone(s.visitRequest);agLeft();
 if(mode==='agents'){if(s.sel)agSelect(s.sel);agManyJump(s.manyTime??s.nowMin);AG.si=s.si??currentScene(s.sel)?.si??AG.si;}
 else {const scenes=agScenes(s.one),sc=scenes.find(x=>sceneMatches(x,s.scene))||scenes[s.si];if(!sc)throw Error('저장된 장면 위치를 찾지 못했습니다. 초기 장면으로 바꾸지 않았습니다.');agSetScene(sc.si,s.fraction||0);}
 if(s.nowMin!=null){AG.nowMin=s.nowMin;agClock();agStripMark();}agPause();root.HLDialogue?.restore?.(s.dialogue);applyUI('flow',e.ui);
}
async function restoreRevenue(e,flow){let r=e.revenue;if(!r){Object.assign(REV,{analysisContext:null,analysisCustomer:'',analysisExpanded:new Set(),transactions:null,opsDate:null,opsHour:null,hourFilter:false,rollRow:null,rollSelection:null,rollView:'venues',flowExpanded:false,detailPanel:null,setupOpen:false,pickerOpen:false,amountBars:false});revRememberFlow({...flow.result,ledger:flow.ledger},clone(flow.request));await revUseRecent();r=revenueState();e.revenue=r;}
 if(r.ledger.run_id!==e.run)throw Error('집계와 실행 ID가 일치하지 않습니다.');REV.latest={flow:{...flow.result,ledger:flow.ledger},request:clone(flow.request)};REV.enteredLatest=e.run;
 const assign=()=>{Object.assign(REV,clone(r.fields));REV.flow=r.flow;REV.ledger=r.ledger;REV.baseline=r.baseline;REV.comparison=r.comparison;REV.busy=false;REV.err=null;};assign();REV.transitionDispatch=true;try{await raw.mode('opx');}finally{REV.transitionDispatch=false;}assign();revRender();applyUI('revenue',e.ui);
}
async function show(e){const flow=await source(e.run);if(e.view==='flow')await restoreFlow(e,flow);
 if(e.view==='revenue')await restoreRevenue(e,flow);
 if(e.view==='evidence'){const snap={flow,returnState:last(e.run,'flow')?.flow||{}};if(!bhModel(snap,e.context))throw Error('행동·거래와 실행의 연결이 일치하지 않습니다.');BH.context=clone(e.context);BH.pid=e.context.customer_id;BH.tab='case';BH.snapshots.set(e.run,snap);await raw.mode('evidence');applyUI('evidence',e.ui);}
 if(e.view==='reviews'){await raw.mode('library');LIBV.open=e.profile.id;LIBV.hl=new Set(e.profile.facts||[]);await libDetail(e.profile.id);applyUI('reviews',e.ui);}
 S.current=e.id;S.activeRun=e.run;S.last.set(e.run+'|'+e.view,e.id);S.error=null;
}
function enqueue(fn){const job=async()=>{S.busy=true;BH.restoring=true;BH.navToken=(BH.navToken||0)+1;BH.routeToken++;try{return await fn();}catch(e){error(e.message);return false;}finally{S.busy=false;BH.restoring=false;}};S.queue=S.queue.then(job,job);return S.queue;}
async function go(v,options={}){const origin=view();if(!S.busy)capture();return enqueue(async()=>{const run=options.run||options.context?.run_id||S.activeRun,flow=await source(run);let e=copyEntry(last(run,v)||{view:v,run,ui:{}});e.id='nav-'+(++S.serial);
 if(v==='flow'&&options.context){e.flow=actionState(run,options.context,flow);if(!compatible(last(run,'flow')?.flow,options.context,flow))e.ui={};}
 // A visit opened directly in revenue has no playback history yet. Start its recorded visit,
 // only for the generic Flow tab; exact action links and existing playback are never replaced.
 if(v==='flow'&&!options.context&&!e.flow){const first=initialAction(flow.result);if(!first)throw Error('이 실행에 표시할 행동 기록이 없습니다.');e.flow=actionState(run,first,flow);e.flow.mode=first.many?'agents':'agent';e.ui={};}
 if(v==='evidence'){e.context=clone(options.context||BH.context);e.url=bhContextURL(e.context);}
 else if(v==='flow')e.url='#flow/'+encodeURIComponent(e.flow?.one||e.flow?.sel||Object.keys(flow.result.plans)[0])+'/'+(flow.ledger.context.event?1:0)+'/run/'+encodeURIComponent(run);
 else if(v==='revenue')e.url='#revenue/run/'+encodeURIComponent(run);
 else if(v==='reviews'){e.profile=options.profile;const q=new URLSearchParams({tab:e.profile.tab||'reviews'});if(e.profile.ref)q.set('evidence_ref',e.profile.ref);if(e.profile.facts?.length)q.set('facts',e.profile.facts.join(','));e.url='#lib/profile/'+encodeURIComponent(e.profile.id)+'?'+q;}
 stamp(e);await show(e);document.dispatchEvent(new CustomEvent('hillink:navigation',{detail:{view:v,fresh:v==='revenue'&&!['evidence','reviews','revenue'].includes(origin)}}));return true;});}
function openScene(pid,si,options={}){if(!AG.flow)return false;capture();const flow=S.runs.get(AG.flow.ledger.run_id),sc=agScenes(pid).find(s=>s.si===si);if(!sc||sc.k==='move')return false;const index=flow.result.plans[pid].scenes.findIndex(s=>(s.visit_day||1)===(sc.visit_day||AG.visitDay||1)&&s.t0===sc.t0&&s.t1===sc.t1&&(s.act===sc.act||sc.k==='turn'&&s.turn===AG.runs[sc.ti]?.turn)),snapshot={flow,returnState:last(flow.ledger.run_id,'flow')?.flow};const c=bhContextFor(snapshot,pid,index,options);if(!c)return false;BH.context=c;
 return options.reviewOnly?go('reviews',{run:c.run_id,profile:{id:pid,facts:root.HLStory.input(flow.result,pid,index).facts.map(f=>f.id),ref:bhContextURL(c),tab:'reviews'}}):go('evidence',{context:c});}
function fromTransaction(rowId,target="evidence"){capture();return enqueue(async()=>{const L=REV.ledger,row=Object.values(L.receipts).flatMap(r=>r.rows).find(r=>r.row_id===rowId);if(!row)throw Error('현재 실행에 해당 거래가 없습니다.');const flow=await source(L.run_id),index=flow.result.plans[row.customer_id].scenes.findIndex(s=>(s.visit_day||1)===(row.visit_day||1)&&s.act===row.act&&agHM(s.t0)===row.time&&(!row.selection_id||!s.basis?.selection_id||row.selection_id===s.basis.selection_id));const c=bhContextFor({flow},row.customer_id,index,{ledger_tx_id:rowId,returnTo:'revenue'});if(!c)throw Error('거래의 행동 연결을 확인하지 못했습니다.');const e=target==='flow'?{id:'nav-'+(++S.serial),run:L.run_id,view:'flow',flow:actionState(L.run_id,c,flow),ui:compatible(last(L.run_id,'flow')?.flow,c,flow)?clone(last(L.run_id,'flow').ui):{},url:'#flow/'+encodeURIComponent(c.customer_id)+'/0/run/'+encodeURIComponent(L.run_id)}:{id:'nav-'+(++S.serial),run:L.run_id,view:'evidence',context:c,ui:{},url:bhContextURL(c)};stamp(e);await show(e);return true;});}
function routeMode(m){if(S.busy||!S.activeRun&&!AG.flow?.ledger&&!(view()==='revenue'&&REV.ledger&&REV.flow))return null;const v=['day','agent','agents','guest','report'].includes(m)?'flow':m==='opx'?'revenue':m==='evidence'?'evidence':null;if(!v)return null;
 if(MODE==='library'&&LIBV.situation||AG.busy||AG.autorun)return null;if(view()==='flow'&&v==='flow')return null;
 if(v==='evidence'){if(view()==='flow'){const pid=AG.mode==='agent'?AG.one:AG.sel;return pid?{handled:openScene(pid,currentScene(pid)?.si??AG.si)}:null;}const c=last(S.activeRun,'evidence')?.context||BH.context;return c?{handled:go(v,{context:c})}:null;}
 const context=v==='flow'&&view()==='evidence'?BH.context:null;return {handled:go(v,{context})};}
function evidenceURL(url){const match=url.match(/^#evidence\/run\/([^?]+)/);if(!match){error('행동근거 실행 주소를 확인할 수 없습니다.');return false;}const q=new URLSearchParams(url.split('?')[1]),c={run_id:decodeURIComponent(match[1])};for(const k of ['customer_id','visit_id','stay_id','visit_date','action_id','action_code','decision_id','ledger_tx_id','returnTo'])c[k]=q.get(k);c.scene_index=Number(q.get('scene_index'));c.visit_day=Number(q.get('visit_day')||1);return go('evidence',{context:c});}
function openRun(flow,pid,index){const run=remember(flow);if(!run)return Promise.resolve(false);const context=bhContextFor({flow},pid,index,{returnTo:'revenue'});if(!context){error('선택한 실행의 고객 행동을 찾지 못했습니다.');return Promise.resolve(false);}return go('flow',{run,context});}
root.HLNav={openRunLedger:flow=>{const run=remember(flow);return run?go('revenue',{run}):Promise.resolve(false);},openRun,evidenceURL,restoreHistory:()=>historyRoute(),state:S,capture,go,openScene,fromTransaction,routeMode,active:()=>!S.busy,activate:(snapshot,c)=>{remember(snapshot.flow);return go('evidence',{context:c});},review:(id,facts,ref,tab)=>{capture();return go('reviews',{profile:{id,facts:facts||[],ref,tab}});}};
function historyRoute(event){const mark=history.state?.hillinkNav;if(!mark)return;if(event){event.stopImmediatePropagation();event.preventDefault();}
 // popstate already moved the URL: save the screen without rewriting that entry.
 if(!S.busy)capture(false);const e=S.entries.get(mark.id);enqueue(async()=>{if(!e)throw Error('이 페이지의 화면 상태가 현재 탭에 없습니다. 실행을 보관한 탭에서 다시 열어 주세요. 초기화하거나 재계산하지 않았습니다.');await show(e);});}
window.addEventListener('popstate',historyRoute,true);window.addEventListener('hashchange',e=>{if(history.state?.hillinkNav)e.stopImmediatePropagation();},true);
window.addEventListener('click',e=>{const b=e.target.closest('header [data-mode]');if(!b)return;if(S.busy){e.preventDefault();e.stopImmediatePropagation();const v={day:'flow',opx:'revenue',evidence:'evidence'}[b.dataset.mode];if(v)go(v,{context:v==='evidence'?BH.context:null});return;}if(b.dataset.mode==='library'){capture();return;}const route=routeMode(b.dataset.mode);if(route){e.preventDefault();e.stopImmediatePropagation();}},true);
})(typeof window!=='undefined'?window:globalThis);
