const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/agent.js'),'utf8');
const start=source.indexOf('function agCarriedScenario('),end=source.indexOf('function agScenarioOption(',start);
function carry(AG,ids,same=null){const ctx={AG,structuredClone,agSelectedScenario:()=>same};vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);return ctx.agCarriedScenario(ids);}
const santa={scenario:{event_card_id:'SANTA_KIDS_VILLAGE_2025',entitlements:{A01:{ticket:'family'}}},request:{personas:['A01'],start_date:'2025-12-19'},label:'산타'};
test('2025 event card is kept for a changed multi-customer set with its 2025 date',()=>{const c=carry({scenarioSelection:santa},['A01','A04','A02']);assert.equal(c.scenario.event_card_id,'SANTA_KIDS_VILLAGE_2025');assert.equal(c.start_date,'2025-12-19');assert.deepEqual(Object.keys(c.scenario.entitlements),['A01','A04','A02']);});
test('no selection means no carried card',()=>{assert.equal(carry({scenarioSelection:null},['A01','A04']),null);});
test('wine fair keeps its own path (not carried)',()=>{assert.equal(carry({scenarioSelection:{scenario:{event_card_id:'WINE_FAIR_2026_AUTUMN'},request:{start_date:'2026-10-24'}}},['A01','A04']),null);});
test('same customer set uses the selected scenario, not the carried copy',()=>{assert.equal(carry({scenarioSelection:santa},['A01'],{scenario:santa.scenario}),null);});
