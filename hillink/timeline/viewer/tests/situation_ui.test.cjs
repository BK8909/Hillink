const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ctx={structuredClone,window:{addEventListener(){}}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/situation.js'),'utf8'),ctx);
const options=JSON.parse(fs.readFileSync(path.join(__dirname,'../static/situation_options.json'),'utf8'));
test('event off/on retains persona, duration, seed and profile facts',()=>{
 const base={event:'none',duration:'stay_2',seed:17};const a=ctx.situationRequest('A01',base,options),b=ctx.situationRequest('A01',{...base,event:'wine'},options);
 assert.deepEqual(JSON.parse(JSON.stringify(a)),{personas:['A01'],duration:'stay_2',event_mode:'none',seed:17,start_date:'2026-10-24',include_ledger:true});
 assert.deepEqual(JSON.parse(JSON.stringify(b)),{personas:['A01'],duration:'stay_2',event_mode:'wine',seed:17,start_date:'2026-10-24',include_ledger:true});
 assert.equal('visit_override' in a,false);
});
test('all four visit durations are supported; future event and invalid duration cannot execute',()=>{
 for(const duration of ['day_visit','stay_1','stay_2','stay_3']) assert.equal(ctx.situationRequest('A01',{event:'none',duration,seed:0},options).duration,duration);
 for(const x of options.events.filter(x=>!x.enabled)) assert.throws(()=>ctx.situationRequest('A01',{event:x.id,duration:'day_visit',seed:0},options));
 assert.throws(()=>ctx.situationRequest('A01',{event:'none',duration:'stay_4',seed:0},options));
});
test('only supported visit inputs reach the engine',()=>{
 const r=ctx.situationRequest('A07',{event:'wine',duration:'stay_1',seed:2,weather:'rain',weekday:'weekday'},options);
 assert.deepEqual(JSON.parse(JSON.stringify(r.personas)),['A07']);
 assert.equal(r.duration,'stay_1');assert.equal(r.event_mode,'wine');assert.equal(r.seed,2);
 assert.equal('weather' in r,false);assert.equal('weekday' in r,false);assert.equal('party_size' in r,false);assert.equal('visit_override' in r,false);
});
test('package context is optional and only sent when explicitly selected',()=>{
 const base={event:'none',duration:'stay_2',seed:17};
 const plain=ctx.situationRequest('A01',base,options);
 const selected=ctx.situationRequest('A01',{...base,package_id:'GRAND_SUNGSU_V2_2N'},options);
 assert.equal('package_id' in plain,false);
 assert.equal(selected.package_id,'GRAND_SUNGSU_V2_2N');
});
test('completed environment inputs survive presentation changes and remain virtual request conditions',()=>{
 const form={event:'none',duration:'stay_2',seed:17,start_date:'2026-10-30',weather:'rain',arrival_time:'14:30'};
 const before=structuredClone(form),r=ctx.situationRequest('A01',form,options);
 assert.equal(r.start_date,'2026-10-30');assert.deepEqual(JSON.parse(JSON.stringify(r.environment)),{weather:'rain',arrival_time:'14:30'});
 assert.equal('weekday' in r,false);assert.equal('visit_override' in r,false);const {detailDraft,...unchanged}=form;assert.deepEqual(unchanged,before);assert.deepEqual(detailDraft.originalOrders,[]);
});

test('focused-input changes coalesce after the native event and cannot redraw a departed screen',()=>{
 const pending=[],old=ctx.situationRender;let renders=0;ctx.requestAnimationFrame=fn=>{pending.push(fn);return pending.length;};ctx.LIBV={situation:'N03'};vm.runInContext("SIT.pid='N03'",ctx);ctx.situationRender=()=>renders++;
 try{ctx.situationQueueRender();ctx.situationQueueRender();assert.equal(pending.length,1);assert.equal(renders,0);pending.shift()();assert.equal(renders,1);ctx.situationQueueRender();ctx.LIBV.situation=null;pending.shift()();assert.equal(renders,1);}finally{ctx.situationRender=old;}
});

test('room packages use catalog dates, building, nights and event; unsupported products cannot remain eligible',()=>{
 const catalog={packages:[{id:'p',runnable:true,minimum_nights:2,nights:2,buildings:['GRAND'],effective_from:'2026-05-18',effective_to:'2026-12-31',event_card_id:null},{id:'s',runnable:true,minimum_nights:1,buildings:['GRAND','VISTA'],effective_from:'2025-12-19',effective_to:'2025-12-25',event_card_id:'SANTA_KIDS_VILLAGE_2025'},{id:'u',runnable:false,minimum_nights:1,buildings:['GRAND'],effective_from:'2026-01-01',effective_to:'2026-12-31'}]};
 const form={duration:'stay_2',start_date:'2026-10-24',visit_conditions:{A01:{building:'GRAND'}}};
 const ids=(f,ev={})=>Array.from(ctx.situationRoomPackages(f,'A01',catalog,ev),x=>x.id);
 assert.deepEqual(ids(form),['p']);assert.deepEqual(ids({...form,duration:'stay_1'}),[]);assert.deepEqual(ids({...form,visit_conditions:{A01:{building:'VISTA'}}}),[]);
 assert.deepEqual(ids({...form,start_date:'2025-12-19'},{event_card_id:'SANTA_KIDS_VILLAGE_2025'}),['s']);
 assert.deepEqual(ids({...form,start_date:'2025-12-26'},{event_card_id:'SANTA_KIDS_VILLAGE_2025'}),[]);
});

test('catalog rooms preserve current event and source dates for every occupied night',()=>{
 const p={id:'HC-ROOM',sku_id:'HC-ROOM',label:'등록 객실',adapter:'catalog_room',catalog_policy:'C01_HOTEL_CATALOG_V1',runnable:true,buildings:['GRAND'],minimum_nights:1,nights:null,effective_from:null,effective_to:null,allowed_dates:['2026-10-24','2026-10-25']};
 const catalog={packages:[p]},event={id:'wine',enabled:true,event:true,event_card_id:'WINE_FAIR_2026_AUTUMN'};
 vm.runInContext('SIT.roomOptions='+JSON.stringify(catalog),ctx);
 try{
 const form={event:'wine',duration:'stay_2',start_date:'2026-10-24',package_id:'HC-ROOM',visit_conditions:{A01:{building:'GRAND'}}};
 assert.equal(ctx.situationRoomPackages(form,'A01',catalog,event).length,1);
 assert.equal(ctx.situationRoomPackages({...form,duration:'stay_3'},'A01',catalog,event).length,0);
 const r=ctx.situationRequest('A01',form,{events:[event]});assert.equal(r.catalog_options.room_products.A01,'HC-ROOM');assert.equal(r.scenario.event_card_id,event.event_card_id);assert.equal('package_id' in r,false);
 }finally{vm.runInContext('delete SIT.roomOptions',ctx);}
});
