const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const calls = [], flows = new Map();
  const ctx = { structuredClone, document: { querySelector: () => null, addEventListener() {} }, dno: id => ({A01:'No.0001',A02:'No.0002',A07:'No.0006'})[id] || id,
    rcMoney: n => n == null ? '금액 미확인' : `${n}원`, rcDelta: n => `${n > 0 ? '+' : ''}${n}원`, rcVenueName: n => n, rcContext: c => [c.building === 'GRAND' ? '그랜드' : '', c.party_size ? `${c.party_size}인` : ''].filter(Boolean).join(' · '), esc: s => String(s ?? ''),
    api: async (route, body) => {
      calls.push({route, body: structuredClone(body)});
      if (route === '/api/ledger/compare') return { comparable: true, baseline_id: body.baseline_id, scenario_id: body.scenario_id, venues: [] };
      if (route === '/api/visit') { const flow = sample(body.personas, body.event_mode === 'wine' ? 'wine' : 'none'); flows.set(flow.ledger.run_id, flow); return flow; }
      throw new Error(route);
    }};
  vm.createContext(ctx);
  // Load the real shared picker; the unit still owns no browser DOM or profile store.
  ctx.AG={meta:{personas:[]}};ctx.agLibP=()=>null;ctx.agTypeFull=()=>'';
  const agent=fs.readFileSync(path.join(__dirname,'../static/agent.js'),'utf8');
  vm.runInContext(agent.slice(agent.indexOf('function hlCustomerPickerHTML('),agent.indexOf('function hlCustomerPickerWire(')),ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/revenue.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/revenue_analysis.js'), 'utf8'), ctx);
  return {ctx, calls, flows, state: vm.runInContext('REV',ctx)};
}
function sample(ids, suffix='recent') {
  return { plans: Object.fromEntries(ids.map(id=>[id,{scenes:[]}])) ,
    ledger: {source:'live_engine', run_id:ids.join('|')+'-'+suffix, context:{event:suffix==='wine'}, customer_types:['가족'], venues:[], receipts:Object.fromEntries(ids.map(id=>[id,{customer_id:id}]))} };
}
test('latest execution is copied and unknown receipt sources are rejected', () => {
  const {ctx,state}=setup(), flow=sample(['A01']), request={personas:['A01'],seed:3,event:false};
  ctx.revRememberFlow(flow,request);
  flow.plans.A01.scenes.push('later UI mutation'); request.seed=9;
  assert.equal(state.latest.request.seed,3);
  assert.equal(state.latest.flow.plans.A01.scenes.length,0);
  ctx.revRememberFlow({...sample(['A02']),ledger:{source:'unknown'}},{personas:['A02']});
  assert.deepEqual(Array.from(Object.keys(state.latest.flow.plans)),['A01']);
});
test('entering revenue reuses the exact latest run without invoking the engine', async () => {
  const {ctx,state,calls,flows}=setup(), flow=sample(['A01']);
  flows.set(flow.ledger.run_id,flow); ctx.revRememberFlow(flow,{personas:['A01'],seed:0,event:false});
  await ctx.revEnter();
  assert.equal(state.flow.ledger.run_id,flow.ledger.run_id);
  assert.equal(state.ledger.run_id,flow.ledger.run_id);
  assert.equal(calls.filter(x=>x.route==='/api/flow').length,0);
});
test('recent visit preserves duration and event mode without recalculation', async () => {
  const {ctx,state,calls}=setup(), flow=sample(['A01'],'wine');
  flow.ledger.visit={duration:'stay_2',day_count:3};
  ctx.revRememberFlow(flow,{personas:['A01'],seed:7,event_mode:'wine',duration:'stay_2'});
  state.duration='day_visit';
  await ctx.revUseRecent();
  assert.equal(state.duration,'stay_2');
  assert.equal(state.scenario,'wine');
  assert.equal(state.flow.ledger.run_id,flow.ledger.run_id);
  assert.equal(calls.filter(x=>x.route==='/api/visit').length,0);
});
test('recent package scenario retains its package context; new customer scope does not inherit it', () => {
  const {ctx,state}=setup(), flow=sample(['A01']);
  ctx.revRememberFlow(flow,{personas:['A01'],seed:7,event_mode:'none',duration:'stay_2',package_id:'GRAND_SUNGSU_V2_2N'});
  state.scope='recent'; state.duration='stay_2';
  assert.equal(ctx.revRequest('none').package_id,'GRAND_SUNGSU_V2_2N');
  state.scope='selected'; state.allIds=['A01']; state.selected=new Set(['A01']);
  assert.equal('package_id' in ctx.revRequest('none'),false);
});
test('direct selection keeps exact customer IDs and sends one visit duration without copying manual profile overrides', () => {
  const {ctx,state}=setup(); state.allIds=['A01','A02','A07']; state.scope='selected'; state.selected=new Set(['A02','A01','INVALID']);
  const override={stay:true,building:'VISTA',phase:'checkout',party_size:2};
  ctx.revRememberFlow(sample(['A01']),{personas:['A01'],seed:4,event:false,visit_override:{A01:override}});
  const request=ctx.revRequest('wine');
  assert.deepEqual(Array.from(request.personas),['A01','A02']);
  assert.equal(request.seed,4); assert.equal(request.event_mode,'wine');
  assert.equal(request.duration,'day_visit'); assert.equal(request.start_date,'2026-10-24');
  assert.equal(request.include_ledger,true);
  assert.equal('visit_override' in request,false);
});
test('pre-run controls separate last result from customer scope and expose event only', () => {
  const {ctx,state}=setup(); state.allIds=['A01','A02']; state.scope='selected'; state.selected=new Set(['A01']);
  const html=ctx.revHTML();
  assert.match(html,/data-rev-recent>최근 실행/);
  assert.match(html,/고객 선택/);
  assert.match(html,/전체 2팀 선택/);
  assert.match(html,/data-picker-id="A01" checked/);
  assert.doesNotMatch(html,/data-picker-id="A02" checked/);
  assert.match(html,/숙박 일정/); assert.match(html,/당일 방문 \(0박\)/);
  assert.match(html,/1박 2일/); assert.match(html,/2박 3일/); assert.match(html,/3박 4일/);
  assert.match(html,/행사 없음/); assert.match(html,/와인페어 있음/);
  assert.match(html,/placeholder="번호 · 유형 · 핵심 특징"/);
  assert.equal((html.match(/id="revScenario"/g)||[]).length,1);
  assert.equal((html.match(/id="revRun"/g)||[]).length,1);
  assert.doesNotMatch(html,/고객 유형<select|투숙 여부<select|data-rev-scope="all"/);
});
test('recent action restores the exact read-only run; only explicit new setup opens calculation controls', async () => {
  const {ctx,state,calls}=setup(),flow=sample(['A01']);
  flow.ledger.context.duration='stay_1';flow.ledger.totals={paid_krw:0};
  state.allIds=['A01','A02'];ctx.revRememberFlow(flow,{personas:['A01'],event:false,duration:'stay_1'});
  await ctx.revUseRecent();
  const previous=structuredClone(state.latest),ledger=structuredClone(state.ledger);
  assert.equal(state.scope,'recent');assert.equal(state.setupOpen,false);
  assert.equal(state.ledger.run_id,flow.ledger.run_id);
  assert.equal(state.duration,'stay_1');assert.equal(calls.length,0);
  ctx.revNewSetup();
  assert.equal(state.scope,'selected');assert.equal(state.setupOpen,true);
  assert.deepEqual(Array.from(state.selected),['A01']);
  assert.deepEqual(structuredClone(state.latest),previous);
  assert.deepEqual(structuredClone(state.ledger),ledger);
  assert.equal(calls.length,0,'loading a recent run or opening its draft must not calculate');
  const draft=ctx.revSetupPanelHTML();
  assert.equal((draft.match(/id="revRun"/g)||[]).length,1);
  assert.match(draft,/배경은 이전 결과/);
});
test('day visit is an explicit duration and does not change profile party size', () => {
  const {ctx,state}=setup(); state.allIds=['A01','A02']; state.selected=new Set(['A01','A02']); state.scope='selected'; state.duration='day_visit';
  const request=ctx.revRequest('wine');
  assert.equal(request.duration,'day_visit');
  assert.equal('visit_override' in request,false);
  assert.equal('party_size' in request,false);
});
test('multi-day duration reaches visit API as a real scenario', async () => {
  const {ctx,state,calls}=setup(); state.allIds=['A01']; state.selected=new Set(['A01']); state.scope='selected'; state.duration='stay_1';
  await ctx.revRun();
  const visitCalls=calls.filter(x=>x.route==='/api/visit');
  assert.equal(visitCalls.length,1);
  assert.equal(visitCalls[0].body.duration,'stay_1');
  assert.equal(visitCalls[0].body.include_ledger,true);
  assert.equal(state.err,null);
});
test('resolved visit profile assumptions are displayed as assumptions', () => {
  const {ctx}=setup();
  const text=ctx.revProfileContext({stay:true,building:'GRAND',phase:'mid',party_size:4,nights:2}, {event:false});
  assert.match(text,/그랜드/); assert.match(text,/4인/); assert.match(text,/2박/);
  assert.doesNotMatch(ctx.revProfileContext({stay:false,building:null,phase:'visit',party_size:4,nights:2},{event:false}),/2박/);
});
test('all-customer scenario comparison calculates the same cohort twice', async () => {
  const {ctx,state,calls}=setup(); state.allIds=['A01','A02','A07']; state.scope='all'; state.scenario='wine';
  await ctx.revRun();
  const engineCalls=calls.filter(x=>x.route==='/api/visit');
  assert.equal(engineCalls.length,2);
  assert.deepEqual(engineCalls[0].body.personas,engineCalls[1].body.personas);
  assert.equal(engineCalls[0].body.event_mode,'wine'); assert.equal(engineCalls[1].body.event_mode,'none');
  assert.equal(engineCalls[0].body.duration,engineCalls[1].body.duration);
  assert.equal(engineCalls[0].body.start_date,engineCalls[1].body.start_date);
  assert.notEqual(state.baseline.ledger.run_id,state.flow.ledger.run_id);
  assert.equal(state.ledger.run_id,state.flow.ledger.run_id);
});
test('facility amount and event delta charts are derived from ledger comparison rows', () => {
  const {ctx,state}=setup(); state.department='F&B';
  const ledger={venues:[{key:['F&B','피자힐'],name:'피자힐',department:'F&B',paid_krw:120000,team_count:2,unknown_count:0}]};
  const amount=ctx.revVenueAmountChart(ledger);
  assert.match(amount,/120000원/); assert.match(amount,/data-rev-venue/);
  const delta=ctx.revEventDeltaChart({venues:[{key:['F&B','피자힐'],name:'피자힐',department:'F&B',before_krw:100000,after_krw:120000,delta_krw:20000},{key:['ROOM','객실'],name:'객실',department:'ROOM',before_krw:5000,after_krw:1000,delta_krw:-4000}]});
  assert.match(delta,/\+20000원/); assert.match(delta,/행사 전후 업장별 소비/);
  assert.doesNotMatch(delta,/객실/);
  const off={source:'live_engine',run_id:'off',context:{event:false}}, on={source:'live_engine',run_id:'on',context:{event:true}};
  const comparison={comparable:true,baseline_id:'off',scenario_id:'on',venues:[]};
  ctx.revRememberAB(off,on,comparison); state.scope='recent';
  assert.equal(ctx.revEventComparison({run_id:'on'}).scenario_id,'on');
  assert.equal(ctx.revEventComparison({run_id:'unrelated'}),null);
});
test('recent remains read-only even if its execute handler is called', async () => {
  const {ctx,state,calls,flows}=setup(), flow=sample(['A01']); flows.set(flow.ledger.run_id,flow);
  ctx.revRememberFlow(flow,{personas:['A01'],seed:0,event:false}); await ctx.revEnter();
  state.scenario='wine'; await ctx.revRun();
  assert.equal(calls.filter(x=>x.route==='/api/visit').length,0);
  assert.equal(state.scenario,'none');
  assert.equal(state.flow.ledger.run_id,flow.ledger.run_id);
});
test('changing a draft clears old totals without changing the last customer-flow result', () => {
  const {ctx,state}=setup(),flow=sample(['A01']);ctx.revRememberFlow(flow,{personas:['A01']});
  state.flow=flow;state.ledger=flow.ledger;state.scope='selected';ctx.revInvalidate();
  assert.equal(state.ledger,null);assert.equal(state.flow,null);
  assert.equal(state.latest.flow.ledger.run_id,flow.ledger.run_id);
});
test('stored replay keeps its own receipt and is never relabeled as live', async () => {
  const {ctx,state}=setup(), flow=sample(['A01']);flow.ledger.source='stored_demo';
  ctx.revRememberFlow(flow,{personas:['A01'],event:false});await ctx.revEnter();
  assert.equal(state.ledger.source,'stored_demo');assert.equal(state.ledger.run_id,flow.ledger.run_id);
});

test('consumption summary and paged table retain free/included rows and explicit event attribution', () => {
  const {ctx,state}=setup();const rows=[
    {row_id:'paid',customer_id:'A01',venue:'Restaurant',product:'Dinner',paid_krw:100,quantity:2,unit_basis:'person',price_tier:'SIMULATION_ASSUMPTION'},
    {row_id:'event',customer_id:'A02',venue:'Fair',product:'Ticket',product_id:'C01-EVENT-X',paid_krw:50,quantity:1},
    {row_id:'free',customer_id:'A01',venue:'Park',product:'Walk',paid_krw:0,purchase_status:'FREE_USE'},
    {row_id:'included',customer_id:'A01',venue:'Restaurant',product:'Breakfast',paid_krw:0,purchase_status:'PACKAGE_INCLUDED'}];
  const l={run_id:'x',receipts:{A01:{rows:rows.filter(r=>r.customer_id==='A01')},A02:{rows:rows.filter(r=>r.customer_id==='A02')}}};
  assert.equal(ctx.revPriceClass({price_status:'VIRTUAL_MODEL_UNIT_PRICE'}),'가정 단가');
  assert.equal(ctx.revPriceClass({price_status:'COMPOSED_ORDER_FROM_EXISTING_MENU_REFERENCES'}),'과거 참고');
  let html=ctx.revOperatorSummaryHTML(l);assert.match(html,/전체 가상 소비/);assert.match(html,/참여 고객 1명[\s\S]*?50원/);assert.match(html,/포함 1건 · 무료 1건/);
  state.analysisCustomer='A01';html=ctx.revOperatorSummaryHTML(l);assert.match(html,/고객 일행 가상 소비/);assert.match(html,/100원/);assert.match(html,/참여 0건[\s\S]*?0원/);
  html=ctx.revTransactionsTableHTML(l);assert.match(html,/전체 4건 · 유료 2건 · 무료 1건 · 포함 혜택 1건/);assert.match(html,/<table/);assert.match(html,/가정 단가/);assert.match(html,/data-rev-table-filter="customer"/);
  state.transactions.type='FREE';html=ctx.revTransactionsTableHTML(l);assert.match(html,/필터 1건 \/ 원장 4건/);assert.equal(l.receipts.A01.rows.length,3);
});
test('transaction evidence lookup uses customer day action time, not a day-local array index', () => {
 const {ctx,state}=setup();state.flow={plans:{A01:{scenes:[{visit_day:1,act:'meal',t0:600},{visit_day:2,act:'meal',t0:720}]}}};
 ctx.agHM=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;ctx.revReasonFor=(l,pid,index)=>({pid,index});
 assert.equal(ctx.revRowReason({}, {customer_id:'A01',visit_day:2,scene_index:0,act:'meal',time:'12:00'}).index,1);
});

test('transaction table pages all immutable rows instead of shortening the ledger', () => {
 const {ctx,state}=setup();const rows=Array.from({length:61},(_,i)=>({row_id:'tx-'+i,customer_id:'A01',venue:'v',product:'product-'+i,paid_krw:i+1,quantity:1}));const L={run_id:'large',receipts:{A01:{rows}}};
 let html=ctx.revTransactionsTableHTML(L);assert.match(html,/전체 61건/);assert.equal((html.match(/<tr data-rev-row=/g)||[]).length,25);state.transactions.page=2;html=ctx.revTransactionsTableHTML(L);assert.equal((html.match(/<tr data-rev-row=/g)||[]).length,11);assert.match(html,/3 \/ 3쪽/);assert.equal(rows.length,61);
});

test('scene spending reads only matching customer, day, time and selection L5 rows',()=>{
 const {ctx}=setup();const row={customer_id:'A01',visit_day:2,time:'12:00',act:'lunch_cafe',selection_id:'pick',product:'브런치',paid_krw:112000,unit_price_krw:28000,billing_quantity:4,purchase_status:'SIMULATED_CHARGE'};
 const f={result:{visits:{A01:{party_size:4}}},ledger:{run_id:'run',receipts:{A01:{rows:[row,{...row,visit_day:1},{...row,selection_id:'other'}]},A02:{rows:[row]}}}};
 const sc={visit_day:2,t0:720,act:'lunch_cafe',basis:{selection_id:'pick'}};
 assert.equal(ctx.revSceneConsumptionRows(f,'A01',sc).length,1);const html=ctx.revSceneConsumptionHTML(f,'A01',sc);assert.match(html,/일행 4명 전체/);assert.match(html,/112,000원/);assert.match(html,/28,000원 × 4/);assert.equal(ctx.revSceneConsumptionHTML(f,'A01',{...sc,t0:730}),'');
});

test('analysis groups preserve independent expansion and reset with customer or run',()=>{
 const {ctx,state}=setup(),L={run_id:'one',receipts:{A01:{rows:[]},A02:{rows:[]}}};let html=ctx.revOperatorSummaryHTML(L);
 assert.equal((html.match(/data-analysis-group=/g)||[]).length,5);assert.doesNotMatch(html,/data-analysis-group="[^"]+" open/);
 state.analysisExpanded.add('venue');state.analysisExpanded.add('event');html=ctx.revOperatorSummaryHTML(L);assert.equal((html.match(/data-analysis-group="[^"]+" open/g)||[]).length,2);
 state.analysisCustomer='A01';html=ctx.revOperatorSummaryHTML(L);assert.doesNotMatch(html,/data-analysis-group="[^"]+" open/);assert.match(html,/가장 많이 소비한 업장/);assert.doesNotMatch(html,/매출 1위 업장/);
});
test('unresolved receipt is never displayed as a free zero and extra lines remain accessible',()=>{
 const {ctx}=setup(),sc={si:3,visit_day:1,t0:720,act:'meal'},rows=Array.from({length:3},(_,i)=>({visit_day:1,time:'12:00',act:'meal',product:'item'+i,amount_status:'UNKNOWN',paid_krw:0}));
 const f={result:{visits:{A01:{party_size:1}}},ledger:{run_id:'immutable',receipts:{A01:{rows}}}},original=structuredClone(f);const html=ctx.revSceneConsumptionHTML(f,'A01',sc);
 assert.match(html,/<strong>금액 미산정<\/strong>/);assert.doesNotMatch(html,/<strong>0원| · 무료 이용<\/small>/);assert.match(html,/나머지 1개 항목 펼침/);assert.doesNotMatch(html,/data-ux-scene|거래 상세 보기/);assert.deepEqual(f,original);
});

test('review presentation distinguishes extracted gist, verbatim quote and contextual evidence',()=>{
 const {ctx}=setup(),src=fs.readFileSync(path.join(__dirname,'../static/agent.js'),'utf8');ctx.AG={visitDay:1};ctx.agReadingKey=()=> 'key';ctx.libUrl=()=>null;
 vm.runInContext('const AG_READING=new Map();let agReadingSerial=0;'+src.slice(src.indexOf('function agReadableHTML('),src.indexOf('function agReadableMount('))+src.slice(src.indexOf('function agBRFactTag('),src.indexOf('function agBRFacts('))+src.slice(src.indexOf('function agBRFactCards('),src.indexOf('function agBREvidence(')),ctx);
 const html=ctx.agBRFactCards('A01',[{id:'F1',text:'식사 경험의 추출 요약',direct:false,scope:'워커힐 후기'}],3);
 assert.match(html,/후기에서 추출한 요약/);assert.match(html,/개인 성향의 참고 경험/);assert.doesNotMatch(html,/원문 보기|원문 URL 없음|<blockquote|원문 발췌/);assert.match(html,/--reading-lines:4/);assert.match(html,/data-frp-fact="F1"/);assert.match(html,/이어서 보기/);
 const quoted=ctx.agBRFactCards('A01',[{id:'F2',text:'요약',source_quote:'실제 제공된 원문 문장',direct:true,scope:'워커힐 후기'}],3);assert.match(quoted,/원문 발췌/);assert.match(quoted,/실제 제공된 원문 문장/);assert.match(quoted,/선택 기록에 인용된 근거/);assert.match(quoted,/인과 기여 미검증/);
});


test('receipt detail expands exact L5 values without routing to decision evidence',()=>{
 const {ctx}=setup(),sc={si:6,visit_day:1,t0:1102,act:'turn_dinner'},row={row_id:'tx-actual',visit_day:1,visit_date:'2026-10-24',time:'18:22',act:'turn_dinner',product:'룸서비스 세트',unit_price_krw:87000,billing_quantity:1,quantity:1,paid_krw:87000,discount_krw:0,purchase_status:'SIMULATED_CHARGE'};
 const f={result:{visits:{A02:{party_size:3}}},ledger:{run_id:'same-run',receipts:{A02:{rows:[row]}}}},before=structuredClone(f),html=ctx.revSceneConsumptionHTML(f,'A02',sc);
 assert.match(html,/<details class="frp-transaction-detail">/);assert.match(html,/data-l5-row="tx-actual"/);assert.match(html,/87,000원 × 1/);assert.match(html,/일행 3명 전체/);assert.match(html,/2026-10-24 18:22/);assert.doesNotMatch(html,/data-ux-scene|data-bh/);assert.deepEqual(f,before);
});

test('transaction evidence reuses the paused same-run snapshot without resetting its clock', async () => {
  const {ctx,state}=setup();
  const row={row_id:'tx',customer_id:'A02',visit_day:1,act:'turn_dinner',time:'18:22',selection_id:'choice'};
  state.ledger={run_id:'saved-run',receipts:{A02:{rows:[row]}}};
  const saved={flow:{result:{plans:{A02:{scenes:[{visit_day:1,act:'turn_dinner',t0:1102,basis:{selection_id:'choice'}}]}}}},returnState:{nowMin:1117,fraction:.25}};
  let activated;
  ctx.bhRecall=async run=>{assert.equal(run,'saved-run');return saved;};
  ctx.agHM=()=> '18:22';
  ctx.bhContextFor=(s,pid,index,options)=>{assert.equal(s,saved);assert.equal(pid,'A02');assert.equal(index,0);return {...options,run_id:'saved-run'};};
  ctx.bhActivate=(s,c)=>{activated={s,c};};
  ctx.revShowCustomer=()=>{throw Error('must not reset a saved flow for a ledger lookup');};
  await ctx.revUXOpenEvidence('tx');
  assert.equal(activated.s,saved);assert.equal(activated.s.returnState.nowMin,1117);assert.equal(activated.s.returnState.fraction,.25);assert.equal(activated.c.ledger_tx_id,'tx');
});

test('transaction without a snapshot initializes its own scene before capturing a return position', async () => {
  const {ctx,state}=setup(),order=[];
  state.ledger={run_id:'new-run',receipts:{A02:{rows:[{row_id:'tx',customer_id:'A02',act:'turn_dinner',time:'18:22'}]}}};
  ctx.bhRecall=async()=>null;ctx.revShowCustomer=async()=>order.push('load');ctx.agHM=()=> '18:22';
  ctx.agScenes=()=>[{si:11,k:'turn',act:'turn_dinner',t0:1102}];
  ctx.agSetScene=(si,f)=>{assert.equal(si,11);assert.equal(f,0);order.push('position');};ctx.agPause=()=>order.push('pause');ctx.bhFromScene=()=>order.push('snapshot');
  await ctx.revUXOpenEvidence('tx');assert.deepEqual(order,['load','position','pause','snapshot']);
});

test('ROOM supporting summary retains amounts and uncertainty in one text span',()=>{
 const {ctx}=setup();const room={paid_krw:373000,status:'가상 결제'},ird={paid_krw:138000,status:'가상 결제'};
 assert.equal(ctx.revRoomSummary([room],[]),'객실 1박 · 373000원');
 assert.equal(ctx.revRoomSummary([room],[ird]),'객실 373000원 · 룸서비스 138000원');
 assert.equal(ctx.revRoomSummary([{paid_krw:null,status:'금액 미확인'}],[]),'객실 1박 · 금액 미확인');
 assert.match(ctx.revRoomSummary([room,{paid_krw:null,purchase_status:'UNKNOWN_AMOUNT'}],[ird]),/373000원 · 1건 미확인 · 룸서비스 138000원/);
 assert.doesNotMatch(ctx.revRoomSummary([room],[]),/룸서비스 없음/);
});
test('operator aggregate panel labels references by source class and keeps included breakfast out of revenue', () => {
  const {ctx}=setup();
  assert.equal(ctx.revOperatingHTML(null),'');
  const html=ctx.revOperatingHTML({teams:1,persons:3,team_mornings:2,breakfast:{entitled:4,entitlement_unknown_mornings:0,diners:6,included_used:4,paid_diners:2,diners_split_unknown:0,unused_entitlement:0,paid_revenue_krw:170000,skipped_team_mornings:0,skip_reasons:{}},
    comparison:[{metric_id:'breakfast.use_share_when_included',name_ko:'조식 포함 투숙객의 이용 비율',simulated:1,status:'SAMPLE_TOO_SMALL',reference:{low:.55,high:.7,source_ko:'외부 연구(워커힐 실측 아님)',url:'https://example.org/x'}},
                {metric_id:'breakfast.included_room_share',name_ko:'조식 포함 객실 비율',simulated:null,status:'CONTEXT_ONLY',reference:null}]});
  assert.match(html,/data-rev-operating/);
  assert.match(html,/포함 혜택 4 \+ 추가 결제 2/);
  assert.match(html,/170000원/);
  assert.match(html,/별도 매출로 더하지 않음/);
  assert.match(html,/외부 연구\(워커힐 실측 아님\)/);
  assert.match(html,/표본이 작아 비교하지 않음/);
  assert.match(html,/55%~70%/);
  assert.doesNotMatch(html,/조식 포함 객실 비율/);   // no simulated value and no reference: not listed
  assert.doesNotMatch(html,/구분 미확인/);
});
