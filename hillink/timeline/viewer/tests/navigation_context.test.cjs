const test=require('node:test'),assert=require('node:assert/strict');
const {historyMarker,sameAction}=require('../static/navigation_context.js');
test('history contains routing identifiers only, no run payload, reviews or input conditions',()=>{
 const entry={id:'entry1',view:'flow',run:'runA',flow:{request:{privateProfile:'secret'}},profile:{facts:['private quote']},ui:{controls:['private search']}};
 assert.deepEqual(historyMarker(entry),{hillinkNav:{id:'entry1',run:'runA',view:'flow'}});
});
test('playback fractions apply only to the same run, customer, visit day and actual action',()=>{
 const raw={t0:1102,t1:1162,act:'turn_dinner'},context={run_id:'runA',customer_id:'A02',visit_day:1},state={run_id:'runA',sel:'A02',day:1,scene:raw,fraction:.3};
 assert.equal(sameAction(state,context,raw),true);
 for(const change of [{run_id:'runB'},{customer_id:'A04'},{visit_day:2}])assert.equal(sameAction(state,{...context,...change},raw),false);
 for(const change of [{t0:1112},{t1:1172},{act:'turn_lunch'}])assert.equal(sameAction(state,context,{...raw,...change}),false);
 assert.equal(sameAction(state,context,null),false);
});

test('new A/B native scene resolves exact time/action without a presentation kind',()=>{
 const {sceneMatches}=require('../static/navigation_context.js');
 const native={t0:1129,t1:1189,act:'dinner'},view={...native,k:'flow'};
 assert.equal(sceneMatches(view,native),true);
 assert.equal(sceneMatches({...view,t0:1130},native),false);
 assert.equal(sceneMatches({...view,act:'rest'},native),false);
 assert.equal(sceneMatches(view,{...native,k:'move'}),false);
});

test('navigation copies mutable screen state while retaining one engine payload per run',()=>{
 const {copyEntry}=require('../static/navigation_context.js');
 const payload={plans:{A01:{scenes:[{act:'lunch'}]}},ledger:{run_id:'A',totals:{paid_krw:100}}};
 const entry={ui:{scroll:[['',90,0]]},flow:{si:3,cond:{event:false}},context:{run_id:'A'},revenue:{fields:{selected:new Set(['A01'])},request:{personas:['A01']},flow:payload,ledger:payload.ledger}};
 const copies=Array.from({length:20},()=>copyEntry(entry));
 copies[0].ui.scroll[0][1]=400;copies[0].flow.si=9;copies[0].revenue.fields.selected.add('A02');copies[0].revenue.request.personas.push('A02');
 assert.equal(entry.ui.scroll[0][1],90);assert.equal(entry.flow.si,3);assert.equal(entry.revenue.fields.selected.size,1);assert.deepEqual(entry.revenue.request.personas,['A01']);
 for(const copy of copies){assert.strictEqual(copy.revenue.flow,payload);assert.strictEqual(copy.revenue.ledger,payload.ledger);}
 assert.equal(new Set(copies.map(c=>c.revenue.flow)).size,1);
});


test('first receipt-to-flow navigation supplies screen-only lever defaults without changing native input',()=>{
 const {flowControls}=require('../static/navigation_context.js');
 const native={stay:false,building:'GRAND',party_size:2};
 const screen=flowControls(native);
 assert.deepEqual(Object.keys(screen.product_levers),[]);
 screen.product_levers.MENU={discount_percent:10};
 assert.deepEqual(native,{stay:false,building:'GRAND',party_size:2});
 const existing={product_levers:{MENU:{discount_percent:20}}};
 const restored=flowControls(existing);restored.product_levers.MENU.discount_percent=10;
 assert.equal(existing.product_levers.MENU.discount_percent,20);
 assert.deepEqual(flowControls(null),{product_levers:{}});
});


test('generic flow entry uses only the current run recorded start when no playback exists',()=>{
 const {initialAction}=require('../static/navigation_context.js');
 const result={plans:{A03:{scenes:[{t0:900,visit_day:1,act:'arrive'}]},A04:{scenes:[{t0:870,visit_day:1,act:'arrive'}]}}};
 assert.deepEqual(initialAction(result),{customer_id:'A03',scene_index:0,visit_day:1,many:true});
 assert.equal(initialAction({plans:{A03:{scenes:[]}}}),null);
 assert.equal(initialAction({plans:{A03:result.plans.A03}}).many,false);
});


test('revenue-only runs retain their actual request instead of a different previous visit or ledger summary',()=>{
 const {revenueRequest}=require('../static/navigation_context.js');
 const current={ledger:{run_id:'new',context:{duration:'day_visit'}},flow:{request:{personas:['A03'],seed:17,behavior_engine:'m4_c01'}},latest:{flow:{ledger:{run_id:'old'}},request:{personas:['A01'],seed:0}}};
 const request=revenueRequest(current);assert.deepEqual(request,current.flow.request);request.personas.push('A02');assert.deepEqual(current.flow.request.personas,['A03']);
});
