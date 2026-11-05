const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function setup(source='live_engine', engine='m4', run='current') {
  const data = {engine:{behavior_engine:engine},ledger:{run_id:'current'},plans:{}};
  const ctx = {AG:{visitData:data,flow:{ledger:{source,run_id:run}}}};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/m4-trace.js'),'utf8'),ctx);
  return {ctx,data};
}
test('M4 trace uses the exact current live visit',()=>{const {ctx,data}=setup();assert.equal(ctx.agM4LiveData(),data);});
test('stored demo cannot display old live M4 trace',()=>{const {ctx}=setup('stored_demo');assert.equal(ctx.agM4LiveData(),null);});
test('legacy execution is never called live M4',()=>{const {ctx}=setup('live_engine','legacy');assert.equal(ctx.agM4LiveData(),null);});
test('a different receipt run cannot borrow M4 explanations',()=>{const {ctx}=setup('live_engine','m4','previous');assert.equal(ctx.agM4LiveData(),null);});
