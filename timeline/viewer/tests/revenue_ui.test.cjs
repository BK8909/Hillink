const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const calls = [], flows = new Map();
  const ctx = { structuredClone, document: { querySelector: () => null }, dno: id => ({A01:'No.0001',A02:'No.0002',A07:'No.0006'})[id] || id,
    api: async (route, body) => {
      calls.push({route, body: structuredClone(body)});
      if (route === '/api/ledger/filter') return flows.get(body.run_id).ledger;
      if (route === '/api/ledger/compare') return { comparable: true, baseline_id: body.baseline_id, scenario_id: body.scenario_id, venues: [] };
      if (route === '/api/flow') { const flow = sample(body.personas, body.event ? 'wine' : 'none'); flows.set(flow.ledger.run_id, flow); return flow; }
      throw new Error(route);
    }};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/revenue.js'), 'utf8'), ctx);
  return {ctx, calls, flows, state: vm.runInContext('REV',ctx)};
}
function sample(ids, suffix='recent') {
  return { plans: Object.fromEntries(ids.map(id=>[id,{scenes:[]}])) ,
    ledger: {source:'live_engine', run_id:ids.join('|')+'-'+suffix, customer_types:['가족'], venues:[], receipts:Object.fromEntries(ids.map(id=>[id,{customer_id:id}]))} };
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
test('direct selection retains supported visit conditions and exact customer IDs', () => {
  const {ctx,state}=setup(); state.allIds=['A01','A02','A07']; state.scope='selected'; state.selected=new Set(['A02','A01','INVALID']);
  const override={stay:true,building:'VISTA',phase:'checkout',party_size:2};
  ctx.revRememberFlow(sample(['A01']),{personas:['A01'],seed:4,event:false,visit_override:{A01:override}});
  const request=ctx.revRequest('wine');
  assert.deepEqual(Array.from(request.personas),['A01','A02']);
  assert.equal(request.seed,4); assert.equal(request.event,true);
  assert.deepEqual(JSON.parse(JSON.stringify(request.visit_override)),{A01:override,A02:override});
});
test('all-customer scenario comparison calculates the same cohort twice', async () => {
  const {ctx,state,calls}=setup(); state.allIds=['A01','A02','A07']; state.scope='all'; state.scenario='wine';
  await ctx.revRun();
  const engineCalls=calls.filter(x=>x.route==='/api/flow');
  assert.equal(engineCalls.length,2);
  assert.deepEqual(engineCalls[0].body.personas,engineCalls[1].body.personas);
  assert.equal(engineCalls[0].body.event,false); assert.equal(engineCalls[1].body.event,true);
  assert.notEqual(state.baseline.ledger.run_id,state.flow.ledger.run_id);
  assert.equal(state.ledger.run_id,state.flow.ledger.run_id);
});
test('recent remains read-only even if its execute handler is called', async () => {
  const {ctx,state,calls,flows}=setup(), flow=sample(['A01']); flows.set(flow.ledger.run_id,flow);
  ctx.revRememberFlow(flow,{personas:['A01'],seed:0,event:false}); await ctx.revEnter();
  state.scenario='wine'; await ctx.revRun();
  assert.equal(calls.filter(x=>x.route==='/api/flow').length,0);
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
