const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function harness(){
 const requests=[];const ctx={HLStrategyExperiment:require('../static/strategy_experiment.js'),revRender:()=>{},document:{querySelector:()=>null,getElementById:()=>null,createElement:()=>({}),head:{appendChild:()=>{}}},setTimeout:()=>{},console,
  libLoad:async()=>{},libP:()=>({}),libTypeOf:()=> '검수 유형',
  fetch:async url=>{requests.push(url);return {ok:true,json:async()=>url==='/api/turn/meta'?{personas:[{id:'A01'}]}:{}}}};
 vm.createContext(ctx);const source=fs.readFileSync(path.join(__dirname,'../static/strategy_ab.js'),'utf8');
 vm.runInContext(source.replace('observe();\n})();',"currentHTML=()=>'<div>CURRENT_RUN</div>';labHTML=()=>'<div>LAB</div>';globalThis.testAccess={ST,ensure,panelHTML,strategyView};\n})();"),ctx);
 return {requests,...ctx.testAccess};
}
test('retired or unknown tab state falls back to the current run and leaves only two tabs',()=>{
 const h=harness();for(const old of ['archive','research','saved',undefined,'broken']){
  h.ST.view=old;const html=h.panelHTML();assert.equal(h.ST.view,'live');assert.match(html,/CURRENT_RUN/);
  assert.doesNotMatch(html,/저장된 연구 사례|data-st-view="archive"/);assert.equal((html.match(/role="tab"/g)||[]).length,2);
 }
 h.ST.view='lab';assert.match(h.panelHTML(),/>LAB</);assert.equal(h.ST.view,'lab');
});
test('opening a current or stale research view never loads stored Santa research',async()=>{
 const h=harness();await h.ensure(true);await h.ensure();assert.ok(h.requests.includes('/api/runtime/capabilities'));
 assert.ok(h.requests.includes('/static/event_scenario_options.json'));assert.equal(h.requests.length,5);
 assert.equal(h.requests.some(x=>/strategy_santa|ledger\/run|api\/visit/.test(x)),false);
});
