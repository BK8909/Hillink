const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),S=require('../static/strategy_current.js');
const row={customer_id:'P',status:'ANALYZED',slot:'dinner',date:'2026-10-24',chosen:{venue:'IRD'},competitors:[],blocked:[]};
const flow={request:{personas:['P'],duration:'stay_1'},visit:{hotel_price_snapshot:{products:[]},catalog_policy:'catalog'},ledger:{run_id:'A',source:'live_engine',receipts:{P:{display_id:'No.0001',rows:[]}}}};
function outcome(rows,origin='EXTERNAL_DELIVERY',cs=[],code='ABSENT') {const g=S.strategyGoal({goal:'restaurant',origin,target:'MYONGWOLGWAN'},flow),analysis={rows},opp=S.opportunity(flow,analysis,g);return S.analysisOutcome(flow,analysis,g,opp,cs,{code,message:'기록된 제약'});}
test('no target, no evidence, no executable lever and analyzed are distinct results',()=>{
 const zero=outcome([row]);assert.equal(zero.status,'NO_TARGET_CUSTOMERS');assert.match(zero.diagnosis,/룸서비스.*외부 배달.*0명/);assert.match(zero.conclusion,/실험해 효과가 없었다는 뜻은 아닙니다/);
 assert.equal(outcome([]).status,'NO_EVIDENCE');assert.equal(outcome([row],'ANY').status,'NO_EVIDENCE');
 assert.equal(outcome([row],'ANY',[],'CONSTRAINED').status,'NO_EXECUTABLE_STRATEGY');
 assert.equal(outcome([row],'ANY',[{kind:'discount'}],'READY').status,'ANALYZED');
 assert.match(outcome([row],'ANY',[{kind:'opening'}],'READY').conclusion,/영업시간/);
});
test('saved run restores authoritative outer ledger, original request and visit together',()=>{
 const f=S.restoreRun({result:{plans:{},visit:{duration:'stay_2'}},ledger:flow.ledger,request:flow.request});assert.strictEqual(f.ledger,flow.ledger);assert.strictEqual(f.request,flow.request);assert.equal(f.visit.duration,'stay_2');
 assert.throws(()=>S.restoreRun({result:{ledger:{run_id:'B'}},ledger:flow.ledger,request:flow.request}),/일치/);
});
function setup(catalog=true){
 const f=structuredClone(flow);if(!catalog)delete f.visit.hotel_price_snapshot;
 const state={goal:'restaurant',origin:'ANY',target:'MYONGWOLGWAN'};let analyses=0,calls=0;
 const ctx={structuredClone,setTimeout,window:{HLNav:{state:{runs:new Map()}}},REV:{flow:f},ST:{cap:{},venueCatalog:{products:[{venue_id:'MYONGWOLGWAN',category:'F&B',role:'MAIN'}]},live:{},events:{}},HLStrategy:S,HLStrategyExperiment:require('../static/strategy_experiment.js'),HLStrategyStory:require('../static/strategy_story.js'),HLPersonalStrategy:require('../static/strategy_personal.js'),HLCauses:{analyze:()=>{analyses++;return {rows:[row]};}},e:String,VN:x=>x,runLine:()=>({teams:1}),DUR:{},fx:String,delta:String,money:String,liveHTML:()=>'',document:{querySelector:()=>null},draw:()=>{},call:async(path)=>{calls++;assert.match(path,/^\/api\/strategy\/evidence\?/);return {facts:[],patterns:{}};}};
 const src=fs.readFileSync(require('node:path').join(__dirname,'../static/strategy_ab.js'),'utf8');vm.createContext(ctx);vm.runInContext(src.slice(src.indexOf('const CURRENT='),src.indexOf('function panelHTML()')),ctx);vm.runInContext("currentContext=()=>'';currentStale=()=>null;CURRENT.target='MYONGWOLGWAN';",ctx);
 return {ctx,get:()=>vm.runInContext('CURRENT',ctx),analyses:()=>analyses,calls:()=>calls};
}
test('render and edited goal do not analyze; only explicit action produces diagnosis',async()=>{
 const h=setup();let html=h.ctx.currentHTML();assert.match(html,/이 목표로 고객 분석 실행/);assert.doesNotMatch(html,/data-current-scope|data-current-cohort|data-current-origin|data-current-multi/);assert.doesNotMatch(html,/data-personal-proposal|data-current-result|data-goal-verdict/);assert.equal(h.analyses(),0);
 const promise=h.ctx.currentAnalyze();assert.equal(h.get().status,'ANALYZING');await promise;assert.equal(h.analyses(),1);assert.equal(h.get().status,'NO_EVIDENCE');assert.match(h.ctx.currentHTML(),/data-personal-proposal/);
 h.ctx.currentReset('조건 변경');assert.equal(h.get().status,'NOT_STARTED');assert.doesNotMatch(h.ctx.currentHTML(),/data-personal-proposal/);assert.equal(h.analyses(),1);
});
test('legacy visit asks for explicit preparation and cannot run A/B before analysis',async()=>{
 const h=setup(false);await h.ctx.currentAnalyze();assert.equal(h.get().status,'NO_EXECUTABLE_STRATEGY');assert.match(h.ctx.currentHTML(),/data-current-prepare/);assert.equal(h.calls(),1);assert.equal(h.analyses(),1);await h.ctx.currentRun('sku');assert.equal(h.calls(),1);
 h.ctx.currentReset();assert.equal(h.get().status,'NOT_STARTED');
});
test('analysis errors are explicit and a changed goal cannot receive stale results',async()=>{
 const h=setup();h.ctx.currentHTML();h.ctx.HLCauses.analyze=()=>{throw Error('decision record unavailable');};await h.ctx.currentAnalyze();assert.equal(h.get().status,'ERROR');assert.match(h.ctx.currentHTML(),/decision record unavailable/);assert.equal(h.get().result,null);
 const next=setup();next.ctx.currentHTML();const pending=next.ctx.currentAnalyze();next.get().target='PIZZA_HILL';await pending;assert.equal(next.get().status,'ERROR');assert.equal(next.get().analysis,null);assert.match(next.get().err,/목표 또는 방문/);
});

test('assumed origin appears only in assumption mode and cannot execute real A/B',async()=>{
 const h=setup();h.ctx.currentHTML();assert.doesNotMatch(h.ctx.currentHTML(),/data-current-assumed-origin/);
 h.get().basis='OPERATOR_ASSUMPTION';const html=h.ctx.currentHTML();assert.match(html,/data-current-assumed-origin/);assert.doesNotMatch(html,/data-current-cohort|data-current-scope|data-current-multi/);
 await h.ctx.currentAnalyze();const calls=h.calls();await h.ctx.currentRun('S');assert.equal(h.calls(),calls);assert.equal(h.get().result,null);
});

test('completed run analysis is independent of another customer draft or pending visit edits',()=>{
 const h=setup();const source=h.ctx.currentSource();const src=fs.readFileSync(require('node:path').join(__dirname,'../static/strategy_ab.js'),'utf8');
 vm.runInContext(src.slice(src.indexOf('function currentStale(source){'),src.indexOf('function currentContext(source){')),h.ctx);
 h.ctx.AG={pendingConditions:true,flow:source.flow};h.ctx.SIT={draftPid:'OTHER',pid:'OTHER',forms:new Map([['OTHER',{}]]),options:{}};
 assert.equal(h.ctx.currentStale(source),null);assert.match(h.ctx.currentDraftDifference(source),/변경/);
 assert.match(h.ctx.currentStale({...source,request:null}),/원래 방문 조건/);assert.match(h.ctx.currentStale({...source,request:{personas:['OTHER']}}),/일치하지/);
 h.get().selectedRun='MISSING_RUN';assert.equal(h.ctx.currentSource(),null);
});
test('busy is cleared after evidence error and a retry can analyze the same immutable run',async()=>{
 const h=setup();h.ctx.currentHTML();const call=h.ctx.call;h.ctx.call=async()=>{throw Error('evidence unavailable')};await h.ctx.currentAnalyze();assert.equal(h.get().busy,false);assert.equal(h.get().status,'ERROR');h.ctx.call=call;await h.ctx.currentAnalyze();assert.equal(h.get().busy,false);assert.notEqual(h.get().status,'ERROR');
});

test('autonomous current run uses actual scene strategy contract without a legacy score decision',()=>{
 const h=setup();h.ctx.ST.cap.llm_strategy=true;
 h.ctx.ST.venueCatalog.products[0].role='MAIN';h.ctx.REV.flow.plans={P:{autonomous_decisions:[{execution_state:'EXECUTED'}],scenes:[{consume:true,meal:'dinner',visit_date:'2026-11-05',t0:1167,loc:'ONDAL',label:'실제 등록 식사',basis:{charge:{krw:120000}}}]}};
 require('../static/strategy_agent_ui.js');h.ctx.HLAgentLab=globalThis.HLAgentLab;
 const html=h.ctx.currentHTML();assert.match(html,/data-agent-source="P"/);assert.match(html,/실제 등록 식사/);assert.match(html,/data-agent-analyze/);
 assert.doesNotMatch(html,/연결된 식사·카페 소비 결정 없음|data-current-analyze|점수와 근거 상세/);assert.equal(h.calls(),0);assert.equal(h.analyses(),0);
 const c=h.ctx.currentAgentContext();assert.equal(c.run.ledger.run_id,'A');assert.equal(c.basis,'ACTUAL_RUN');assert.deepEqual(Array.from(c.ids),['P']);
});
