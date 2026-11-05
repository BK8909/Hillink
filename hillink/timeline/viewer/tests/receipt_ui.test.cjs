const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/agent.js'), 'utf8');
const adapter = source.slice(source.indexOf('function agSelectedScenario('), source.indexOf('async function agRun()'));
async function check(many) {
  const receipt = { source: 'live_engine', run_id: 'r', receipts: { A07: { paid_krw: 123 } } };
  const ctx = { HLVisitExecution:require('../static/visit_execution.js'), structuredClone, AG: { mode: many ? 'agents' : 'agent', oneOverride: false, fix: false, iv: 'none', duration:'stay_2', cond:{} },
    // The adapter now consumes /api/visit. Keep the original same-receipt
    // assertion while supplying the actual visit response contract.
    api: async (route, body) => {
      assert.equal(route,'/api/visit');
      return { ledger: receipt, stories: null, engine: {},
        visit:{duration:body.duration,nights:2}, visit_days:[{day_index:1,date:'2026-10-24',phase:'checkin'}],
        runs:[{visit_day:1,customers:[]}], plans:{A07:{scenes:[]}},
        visits:{A07:{building:'DOUGLAS',party_size:2,stay:true}}, visit_inputs_sha:'s' };
    },
    agLeft() {}, agVcOf: x => x, AG_BLD_SHORT: {}, AG_PH_KO: {} };
  vm.createContext(ctx);vm.runInContext(adapter, ctx);
  await ctx.agRunFlow(['A07'], { event: false }, many);
  assert.equal(ctx.AG.flow.ledger, receipt, 'same-run receipt must survive the flow UI adapter');
}
Promise.all([check(false), check(true)]).then(() => console.log('Receipt flow-adapter tests 2/2 PASS')).catch(e => { console.error(e); process.exitCode = 1; });
