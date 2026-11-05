const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/agent.js'),'utf8');
const start=source.indexOf('async function agRunFlow('),end=source.indexOf('    const r = await api("/api/visit", request);',start);
function build(AG){const ctx={HLVisitExecution:require('../static/visit_execution.js'),AG,structuredClone,agSelectedScenario:()=>AG.scenarioSelection,agCarriedScenario:()=>null};vm.createContext(ctx);vm.runInContext(source.slice(start,end)+'return request;}}',ctx);return ctx.agRunFlow(['A08'],{event:false,stay:true,building:'GRAND',party_size:2},false);}
test('fresh no-event package request cannot inherit previous Vista event or entitlement',async()=>{const old={personas:['A08'],duration:'stay_1',scenario:{event_card_id:'SAVORING_SUMMER_NIGHT_2026'},visit_conditions:{A08:{building:'VISTA'}},start_date:'2026-07-17'};const fresh={personas:['A08'],duration:'stay_2',package_id:'GRAND_SUNGSU_V2_2N',start_date:'2026-10-24',visit_conditions:{A08:{building:'GRAND'}}};const request=await build({flow:{request:old},scenarioSelection:{request:old},visitRequest:fresh,duration:'stay_2',seed:0});assert.equal(request.scenario,undefined);assert.equal(request.visit_conditions.A08.building,'GRAND');assert.equal(request.package_id,fresh.package_id);assert.equal(request.start_date,fresh.start_date);});
test('left-panel continuation retains selected event but updates displayed stay conditions',async()=>{const old={personas:['A08'],duration:'stay_1',scenario:{event_card_id:'WINE_FAIR_2026_AUTUMN'},environment:{weather:'rain'},visit_conditions:{A08:{building:'VISTA',party_composition:{adults:2}}}};const request=await build({flow:{request:old},scenarioSelection:{request:old},duration:'stay_2',oneOverride:true,seed:17});assert.equal(request.scenario.event_card_id,'WINE_FAIR_2026_AUTUMN');assert.equal(request.environment.weather,'rain');assert.equal(request.visit_conditions.A08.building,'GRAND');assert.equal(request.visit_conditions.A08.party_composition.adults,2);});


function dayView(data){const ctx={AG:{meta:{personas:[],buildings:{GRAND:'그랜드'}}},structuredClone,agHM:n=>`${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`,agVcOf:v=>({stay:!!v.stay,party:v.party_size,v})};vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('function agActivityFrame('),source.indexOf('// Date slices are display-only')),ctx);return ctx.agVisitDayView(data,1);}
test('activity-only native day remains viewable without inventing a meal or modifying the execution',()=>{
 const data={runs:[],visit_days:[{day_index:1,date:'2026-10-24',phase:'visit'}],visits:{A03:{stay:false,party_size:2}},plans:{A03:{status:'ok',scenes:[{visit_day:1,t0:900,t1:915,act:'arrive',loc:'HOTEL_GATE',label:'도착'},{visit_day:1,t0:980,t1:1010,act:'bakery',loc:'LE_PASSAGE',label:'빵'}]}}};
 const before=JSON.stringify(data),v=dayView(data);
 assert.equal(v.runs.length,1);assert.equal(v.runs[0].display_only,true);assert.equal(v.runs[0].turn,'day');assert.equal(v.runs[0].customers[0].choice.score,null);assert.equal(v.runs[0].customers[0].choice.price.paid_krw,undefined);assert.equal(v.plans.A03.scenes.length,2);assert.equal(JSON.stringify(data),before);
});
test('display fallback does not replace existing decisions or fabricate activities for an empty day',()=>{
 const actual={visit_day:1,turn:'dinner',customers:[]};
 const data={runs:[actual],visit_days:[{day_index:1}],plans:{},visits:{}};
 assert.strictEqual(dayView(data).runs[0],actual);
 assert.equal(dayView({...data,runs:[]}).runs.length,0);
});

test('stored visits without lever metadata can switch date without crashing the plan hint',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../static/agent.js'),'utf8'),el={};
 const ctx={AG:{engine:'autonomy',flow:{engine:{name:'autonomy'},result:{}},plans:{A01:{}}},$:()=>el,esc:x=>x};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('function agPlanHint('),source.indexOf('// ---------------------------------------------------------------- 아바타')),ctx);
 assert.doesNotThrow(()=>ctx.agPlanHint());assert.match(el.innerHTML,/1팀 실행/);
});
