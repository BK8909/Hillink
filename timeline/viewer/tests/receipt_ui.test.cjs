const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/agent.js'), 'utf8');
const adapter = source.slice(source.indexOf('async function agRunFlow('), source.indexOf('async function agRun()'));
async function check(many) {
  const receipt = { source: 'live_engine', run_id: 'r', receipts: { A07: { paid_krw: 123 } } };
  const ctx = { structuredClone, AG: { mode: many ? 'agents' : 'agent', oneOverride: false, fix: false, iv: 'none' },
    api: async () => ({ ledger: receipt, stories: null, engine: {}, runs: [{ customers: [] }], plans: {}, visits: {}, inputs_sha: 's' }),
    agLeft() {}, agVcOf: x => x, AG_BLD_SHORT: {}, AG_PH_KO: {} };
  vm.createContext(ctx);vm.runInContext(adapter, ctx);
  await ctx.agRunFlow(['A07'], { event: false }, many);
  assert.equal(ctx.AG.flow.ledger, receipt, 'same-run receipt must survive the flow UI adapter');
}
Promise.all([check(false), check(true)]).then(() => console.log('Receipt flow-adapter tests 2/2 PASS')).catch(e => { console.error(e); process.exitCode = 1; });
