const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function setup(){
 const scene={si:3,k:'flow',act:'theatre',loc:'THEATRE_OF_LIGHT',t0:900,t1:960,visit_day:2};
 const snapshot={flow:{request:{duration:'stay_1'},result:{plans:{P:{scenes:[scene]},Q:{scenes:[scene]}}},ledger:{team_count:1,visit:{}}},returnState:{mode:'agent',one:'P',sel:'P',day:2,cond:{building:'GRAND'},scene,fraction:.37,nowMin:922.2,panelScroll:12,stripScroll:34}};
 const el={scrollTop:0,scrollLeft:0},AG={keep:{},runs:[{turn:'dinner'}],plans:{},visits:{},f:0};
 const ctx={HILLINK_APP_READY:new Promise(()=>{}),window:{addEventListener(){}},structuredClone,URLSearchParams,AG,REV:{},document:{querySelector:()=>el,querySelectorAll:()=>[],addEventListener(){}},revRememberFlow(){},revShowCustomer:async()=>{},setMode:async()=>{await new Promise(r=>setTimeout(r,10));AG.f=0;},agVisitDaySelect:d=>AG.visitDay=d,agScenes:()=>[scene],agSetScene:(si,f)=>{AG.si=si;AG.f=f;},agPause:()=>AG.playing=false,agClock(){},agStripMark(){},api(){throw Error('navigation must not calculate');}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/behavior.js'),'utf8'),ctx);return {ctx,AG,snapshot};
}
test('scene position is restored after asynchronous mode initialization and remains paused',async()=>{const {ctx,AG,snapshot}=setup();assert.equal(await ctx.bhRestore(snapshot,{customer_id:'P',scene_index:0,visit_day:2}),true);assert.equal(AG.f,.37);assert.equal(AG.nowMin,922.2);assert.equal(AG.visitDay,2);assert.equal(AG.playing,false);});
test('switching evidence customer cannot reuse another customer playback fraction',async()=>{const {ctx,AG,snapshot}=setup();await ctx.bhRestore(snapshot,{customer_id:'Q',scene_index:0,visit_day:2});assert.equal(AG.f,0);assert.equal(AG.sel,'Q');});
