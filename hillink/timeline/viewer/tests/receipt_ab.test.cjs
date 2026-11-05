const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = fs.readFileSync(path.join(__dirname, '../static/receipts.js'), 'utf8');
const fn = src.slice(src.indexOf('async function rcRunAB('), src.indexOf('function rcComparisonHTML('));

async function main() {
  const calls = [];
  const current = { run_id: 'base', source: 'live_engine', receipts: { A01: { paid_krw: 10 } }, context: { event: false } };
  const other = { run_id: 'event', source: 'live_engine', receipts: { A01: { paid_krw: 20 } }, context: { event: true } };
  const ctx = {
    AG: { flow: { ledger: current, request: { personas: ['A01'], mode: 'one', event: false, seed: 3,
      visit_override: { A01: { stay: true, building: 'GRAND', phase: 'mid', party_size: 2 } }, intervention: 'none', product_levers: {} } } },
    RC: { ab: new Map(), abPending: new Set() },
    api: async (url, body) => { calls.push([url, body]); return url === '/api/flow' ? { ledger: other } : { comparable: true, customers: { A01: { row_changes: [] } } }; },
    rcMountPanel() {},
  };
  vm.createContext(ctx); vm.runInContext(fn, ctx);
  await ctx.rcRunAB('base');
  assert.equal(calls.length, 2);
  assert.equal(calls[0][0], '/api/flow');
  const request = calls[0][1];
  assert.equal(request.event, true);
  assert.equal(request.seed, 3);
  assert.equal(request.personas[0], 'A01');
  assert.deepEqual(JSON.parse(JSON.stringify(request.visit_override)), { A01: { stay: true, building: 'GRAND', phase: 'mid', party_size: 2 } });
  assert.equal(request.include_ledger, true);
  assert.equal(JSON.stringify(calls[1][1]), JSON.stringify({ baseline_id: 'base', scenario_id: 'event', event_only: true }));
  assert.equal(ctx.RC.ab.get('base').current, current);
  assert.equal(ctx.AG.flow.ledger, current, 'comparison must not replace the displayed run');

  const reverseCalls = [];
  const reverse = {
    AG: { flow: { ledger: other, request: { personas: ['A01'], mode: 'one', event: true, seed: 3,
      visit_override: { A01: { stay: true, building: 'GRAND', phase: 'mid', party_size: 2 } }, intervention: 'none', product_levers: {} } } },
    RC: { ab: new Map(), abPending: new Set() },
    api: async (url, body) => { reverseCalls.push([url, body]); return url === '/api/flow' ? { ledger: current } : { comparable: true, customers: { A01: { row_changes: [] } } }; },
    rcMountPanel() {},
  };
  vm.createContext(reverse); vm.runInContext(fn, reverse);
  await reverse.rcRunAB('event');
  assert.equal(reverseCalls[1][1].baseline_id, 'base', 'comparison orientation is always event OFF → ON');
  assert.equal(reverseCalls[1][1].scenario_id, 'event');
  assert.equal(reverse.RC.ab.get('event').current_event, true);

  const visitCalls = [];
  const visitOff = { run_id: 'visit-off', source: 'live_engine', visit: { nights: 2 }, receipts: { A01: { paid_krw: 100 } }, context: { event: false } };
  const visitOn = { run_id: 'visit-on', source: 'live_engine', visit: { nights: 2 }, receipts: { A01: { paid_krw: 120 } }, context: { event: true } };
  const visit = {
    AG: { flow: { ledger: visitOff, request: { personas: ['A01'], mode: 'one', event: false, duration: 'stay_2', start_date: '2026-10-24', seed: 7, package_id: 'GRAND_SUNGSU_V2_2N', intervention: 'none' } } },
    RC: { ab: new Map(), abPending: new Set() },
    api: async (url, body) => { visitCalls.push([url, body]); return url === '/api/visit' ? { ledger: visitOn } : { comparable: true, customers: { A01: { row_changes: [] } } }; },
    rcMountPanel() {},
  };
  vm.createContext(visit); vm.runInContext(fn, visit);
  await visit.rcRunAB('visit-off');
  assert.equal(visitCalls[0][0], '/api/visit');
  assert.deepEqual(JSON.parse(JSON.stringify(visitCalls[0][1])), { personas: ['A01'], duration: 'stay_2', start_date: '2026-10-24', seed: 7, event_mode: 'wine', include_ledger: true, package_id: 'GRAND_SUNGSU_V2_2N' });
  assert.deepEqual(JSON.parse(JSON.stringify(visitCalls[1][1])), { baseline_id: 'visit-off', scenario_id: 'visit-on', event_only: true });
  assert.equal(visit.AG.flow.ledger, visitOff, 'visit comparison must preserve the displayed run');
  console.log('Receipt A/B request invariants 2/2 PASS');
}

main().catch(e => { console.error(e); process.exitCode = 1; });
