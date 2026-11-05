const test=require('node:test'),assert=require('node:assert/strict');
const S=require('../static/strategy_current.js');
const cap={supported:['catalog_discount_percent']};
const competitor={sku:'CATALOG-SKU',label:'기존 메뉴',venue:'PIZZA_HILL',total_krw:80000,price_part:0.6,gap:0.2,same_venue:false,causes:[{category:'SPACE',delta:0.1}]};
const row={customer_id:'X01',date:'2026-10-24',slot:'dinner',decision_key:'X01|date|17:00',status:'ANALYZED',chosen:{venue:'IRD',sku:'IRD-MENU',total_krw:60000,label:'객실 식사'},competitors:[competitor]};
test('candidates come only from eligible recorded priced alternatives, not event presets',()=>{
 for(const event of ['none','WINE_FAIR_2026_AUTUMN','SANTA_KIDS_VILLAGE_2025','PIZZA_HILL_GOLDEN_NIGHT_2026','SAVORING_SUMMER_NIGHT_2026']){
  const cs=S.candidates({event,rows:[row]},'restaurant',cap);assert.equal(cs.length,1);assert.equal(cs[0].sku,competitor.sku);assert.equal(cs[0].space_sensitive,true);
 }
 for(const change of [{sku:null},{total_krw:null},{price_part:0},{venue:'EXTERNAL_DELIVERY'}])assert.equal(S.candidates({rows:[{...row,competitors:[{...competitor,...change}]}]},'restaurant',cap).length,0);
 assert.deepEqual(S.candidates({rows:[row]},'recapture',cap),[]);
 assert.equal(S.candidates({rows:[{...row,chosen:{...row.chosen,venue:'EXTERNAL_DELIVERY'}}]},'recapture',cap).length,1);
});
test('A/B preserves multi customer date, weather, package and engine and changes one SKU discount',()=>{
 const req={personas:['X01','X02'],start_date:'2025-12-19',duration:'stay_2',seed:4,environment:{weather:'rain'},scenario:{event_card_id:'SANTA_KIDS_VILLAGE_2025',entitlements:{X01:{selected_package:true}}},visit_conditions:{X01:{building:'GRAND'}},catalog_options:{discount_percent:{OTHER:10}}};
 const original=structuredClone(req),flow={ledger:{},visit:{breakfast_policy:'BREAKFAST_INCLUDED_DEFAULT_V2',behavior_engine:'m4_c01',simulation_mode:'shared_world'}};
 const {A,B}=S.pair(req,flow,competitor,20);const b=structuredClone(B);delete b.catalog_options.discount_percent['CATALOG-SKU'];assert.deepEqual(b,A);assert.deepEqual(req,original);
 assert.equal(A.start_date,'2025-12-19');assert.equal(A.breakfast_policy,'BREAKFAST_INCLUDED_DEFAULT_V2');
 assert.throws(()=>S.pair(req,flow,competitor,NaN));
});
test('external recapture is an aligned external-to-internal choice, not mere delivery reduction',()=>{
 const flow=(r,paid)=>({rows:r,ledger:{totals:{paid_krw:paid},receipts:{}}}),a=flow([row],100),b=flow([{...row,chosen:{...row.chosen,venue:'PIZZA_HILL'}}],90);
 let m=S.metrics(a,b,x=>({rows:x.rows}),'CATALOG-SKU');assert.equal(m.recaptured,0);assert.equal(m.restaurant_delta,1);assert.equal(m.changed_customers,1);assert.equal(m.paid_delta,-10);
 a.rows=[{...row,chosen:{...row.chosen,venue:'EXTERNAL_DELIVERY'}}];b.ledger.receipts={X01:{rows:[{sku_id:row.chosen.sku,visit_date:row.date,meal:row.slot,paid_krw:90}]}};m=S.metrics(a,b,x=>({rows:x.rows}),'CATALOG-SKU');assert.equal(m.recaptured,1);
 b.rows=[];m=S.metrics(a,b,x=>({rows:x.rows}),'CATALOG-SKU');assert.equal(m.recaptured,0);assert.equal(m.unmatched,1);
});

test('normalized receipt SKU fields retain existing-buyer loss and discount burden',()=>{
 const f=(paid)=>({rows:[],ledger:{totals:{paid_krw:paid},receipts:{P:{rows:[{product_sku_id:'SKU',paid_krw:paid,visit_date:'2026-10-24',quantity:1,discount_krw:100-paid}]}}}});
 const m=S.metrics(f(100),f(80),x=>({rows:x.rows}),'SKU');assert.equal(m.retained_price_delta,-20);assert.equal(m.discount_burden,20);
});
test('equal totals cannot establish replay when source identity or actual rows changed',()=>{
 const a={visit:{breakfast_policy:'V2',hotel_catalog_sha256:'catalog',m4_configuration:{source_sha256:{engine:'old'}}},ledger:{run_id:'a',totals:{paid_krw:100},receipts:{P:{rows:[{sku_id:'one',paid_krw:100}]}}}};
 assert.equal(S.replayMatches(a,structuredClone(a)),true);
 const b=structuredClone(a);b.visit.m4_configuration.source_sha256.engine='new';assert.equal(S.replayMatches(a,b),false);
 const c=structuredClone(a);c.ledger.receipts.P.rows[0].sku_id='two';assert.equal(S.replayMatches(a,c),false);
});

test('restaurant attraction excludes internal substitution and unpaid moves are not recapture',()=>{
 assert.equal(S.candidates({rows:[{...row,chosen:{...row.chosen,venue:'GEUMRYONG'}}]},'restaurant',cap).length,0);
 const f=(venue)=>({rows:[{...row,chosen:{...row.chosen,venue}}],ledger:{totals:{paid_krw:0},receipts:{}}});
 assert.equal(S.metrics(f('EXTERNAL_DELIVERY'),f('PIZZA_HILL'),x=>({rows:x.rows}),'SKU').recaptured,0);
});

test('legacy multi-customer wine without an explicit event card is never labeled no-event',()=>{
 const registry={events:[{id:'none',label:'행사 없음'},{id:'wine',event_card_id:'WINE_FAIR_2026_AUTUMN',label:'2026 가을 와인페어'},{id:'santa',event_card_id:'SANTA_KIDS_VILLAGE_2025',label:'2025 산타 키즈 빌리지'}]};
 for(const snapshot of [{},{event_card_id:'NONE'}])assert.equal(S.eventLabel(registry,{scenario_snapshot:snapshot},{event_mode:'wine'}),'2026 가을 와인페어');
 assert.equal(S.eventLabel(registry,{}, {event_mode:'none'}),'행사 없음');
 assert.equal(S.eventLabel(registry,{scenario_snapshot:{event_card_id:'SANTA_KIDS_VILLAGE_2025'}},{event_mode:'none'}),'2025 산타 키즈 빌리지');
 assert.equal(S.eventLabel(registry,{scenario_snapshot:{event_card_id:'UNSUPPORTED'}},{}),'UNSUPPORTED');
});

test('changing only the catalog room contract invalidates a previous analysis',()=>{
 const a={personas:['X01'],duration:'stay_1',catalog_policy:'C01_HOTEL_CATALOG_V1',catalog_options:{room_products:{X01:'HC-MENU-003'}}};
 const b=structuredClone(a);b.catalog_options.room_products.X01='HC-MENU-038';
 assert.notEqual(S.conditionKey(a),S.conditionKey(b));
 assert.equal(S.conditionKey(a),S.conditionKey({...a,include_ledger:true}));
});

test('A/B comparison rejects catalog or room source changes as well as engine changes',()=>{
 const a={visit:{breakfast_policy:'V2',hotel_catalog_sha256:'c1',behavior_engine:'m4_c01',simulation_mode:'shared_world'},ledger:{context:{room_price_source_sha256:'r1'}}};
 for(const change of [b=>b.visit.hotel_catalog_sha256='c2',b=>b.ledger.context.room_price_source_sha256='r2',b=>b.visit.simulation_mode='individual']){const b=structuredClone(a);change(b);assert.notEqual(S.policyKey(a),S.policyKey(b));}
 assert.equal(S.policyKey(a),S.policyKey(structuredClone(a)));
});

test('target venue attraction includes another restaurant and filters every candidate by target',()=>{
 const r={...row,chosen:{...row.chosen,venue:'GEUMRYONG'}};
 assert.equal(S.candidates({rows:[r]},'restaurant',cap,null,'PIZZA_HILL').length,1);
 assert.equal(S.candidates({rows:[r]},'restaurant',cap,null,'MOEGI').length,0);
 assert.equal(S.candidates({rows:[r]},'restaurant',cap,null,'GEUMRYONG').length,0);
});
test('opening strategy requires actual time exclusion and supported venue; changes only opening',()=>{
 const cp={supported:[...cap.supported,'catalog_service_open_overrides'],service_open_venues:{GEUMRYONG:'18:00'}};
 const r={...row,time:'17:15',blocked:[{venue:'GEUMRYONG',reasons:[{category:'TIME',code:'SERVICE_NOT_OPEN_YET'}]}]};
 const c=S.candidates({rows:[r]},'restaurant',cp,null,'GEUMRYONG')[0];assert.equal(c.kind,'opening');
 const req={personas:['X01'],catalog_options:{discount_percent:{OLD:10}}};const pair=S.pair(req,{ledger:{}},c,20);
 assert.deepEqual(pair.B.catalog_options.discount_percent,pair.A.catalog_options.discount_percent);
 assert.equal(pair.B.catalog_options.service_open_overrides.GEUMRYONG,'17:00');
 assert.equal(S.candidates({rows:[{...r,time:'20:00'}]},'restaurant',cp,null,'GEUMRYONG').length,0);
});
test('target venue KPI separates restaurant substitution from total restaurant gain',()=>{
 const flow=(venue,paid)=>({rows:[{...row,chosen:{...row.chosen,venue}}],ledger:{totals:{paid_krw:paid},receipts:{X01:{rows:[{department:'F&B',venue_id:venue,paid_krw:paid}]}}}});
 const m=S.metrics(flow('GEUMRYONG',100),flow('PIZZA_HILL',80),x=>({rows:x.rows}),'SKU','PIZZA_HILL');
 assert.equal(m.target_delta,1);assert.equal(m.restaurant_delta,0);assert.equal(m.target_fnb_delta,80);assert.equal(m.paid_delta,-20);assert.equal(m.target_arrivals,1);
});

for(const [name,date,slot] of [['one-night','2026-10-24','dinner'],['two-night-day2','2026-10-25','dinner'],['three-night-middle','2026-10-26','dinner'],['lunch','2026-10-25','lunch']])test('precise changed occurrence: '+name,()=>{
 const scenes=[{visit_date:'2026-10-24',meal:'dinner',basis:{m4:{decision_packet_ids:['first'],event_id:'first-event'}}},
  {visit_date:date,meal:slot,basis:{m4:{decision_packet_ids:['wanted'],event_id:'wanted-event'}}},
  {visit_date:date,meal:slot,basis:{m4:{decision_packet_ids:['later'],event_id:'later-event'}}}];
 for(const side of ['A','B']){const flow={ledger:{run_id:side},plans:{P:{scenes}}},target={run_id:side,customer_id:'P',date,slot,occurrence:2,decision_id:'wanted',event_id:'wanted-event'};
  assert.equal(S.resolveDecisionScene(flow,target).index,1);
  for(const change of [{run_id:'other'},{date:'2026-11-02'},{decision_id:'missing'},{event_id:'later-event'},{decision_id:null,event_id:null}])assert.throws(()=>S.resolveDecisionScene(flow,{...target,...change}));
  assert.throws(()=>S.resolveDecisionScene({...flow,plans:{P:{scenes:[...scenes,scenes[1]]}}},target),/여러 행동/);
 }
});
test('same-meal repeated decisions retain independent A/B packet and event identity',()=>{
 const r=n=>({...row,packet_sha256:'a'+n,event_id:'ae'+n,chosen:{...row.chosen,sku:'old'+n}}),rr=[r(1),r(2)];
 const ff=(id,rows)=>({rows,ledger:{run_id:id,receipts:{},totals:{paid_krw:0}}});
 const a=ff('A',rr),b=ff('B',rr.map((r,i)=>({...r,packet_sha256:'b'+i,event_id:'be'+i,chosen:{...r.chosen,sku:i?'new':r.chosen.sku}})));
 const m=S.metrics(a,b,x=>({rows:x.rows}),'new');assert.equal(m.moves.length,1);assert.equal(m.moves[0].occurrence,2);assert.equal(m.moves[0].A.decision_id,'a2');assert.equal(m.moves[0].B.event_id,'be1');assert.equal(m.moves[0].B.run_id,'B');
});

test('analysis preparation preserves input contracts and explicitly changes only the pricing engine',()=>{
 const q={personas:['P'],duration:'stay_2',start_date:'2025-12-19',environment:{arrival_time:'19:30',weather:'rain'},scenario:{event_card_id:'SANTA_KIDS_VILLAGE_2025',assumptions:{booked_sessions:{P:{start:'14:10'}}}},visit_conditions:{P:{building:'VISTA',breakfast_plan:'room_only'}},catalog_options:{room_products:{P:'registered-package'}},seed:4};
 const before=structuredClone(q),f={ledger:{},visit:{breakfast_policy:'V2',simulation_mode:'shared_world'}};
 const result=S.prepareRequest(q,f,{catalog_policy:'catalog'});assert.deepEqual(q,before);
 for(const k of Object.keys(q))assert.deepEqual(result[k],q[k]);
 assert.equal(result.behavior_engine,'m4_c01');assert.equal(result.catalog_policy,'catalog');assert.equal(result.breakfast_policy,'V2');assert.equal(result.simulation_mode,'shared_world');
 assert.throws(()=>S.prepareRequest(null,f,{}));
});
test('registered venue directory and preparation state do not depend on execution quotes',()=>{
 const catalog={products:['PIZZA_HILL','GEUMRYONG','MOEGI','ONDAL','MYONGWOLGWAN','THE_BUFFET'].map(venue_id=>({venue_id,category:'F&B',role:'MAIN'}))};
 assert.equal(S.venues(catalog).length,6);
 assert.equal(S.readiness({visit:{}},{rows:[row]},'PIZZA_HILL',[]).code,'PREPARE');
 const ready={visit:{catalog_policy:'catalog',hotel_price_snapshot:{}}};
 assert.equal(S.readiness(ready,{rows:[]},'MOEGI',[]).code,'NO_DECISIONS');
 assert.equal(S.readiness(ready,{rows:[row]},'MOEGI',[]).code,'ABSENT');
 assert.equal(S.readiness(ready,{rows:[row]},'PIZZA_HILL',[]).code,'NO_CANDIDATE');
 assert.equal(S.readiness(ready,{rows:[{...row,blocked:[{venue:'MOEGI',reasons:[]}]}]},'MOEGI',[]).code,'CONSTRAINED');
 assert.equal(S.readiness(ready,{rows:[row]},'PIZZA_HILL',[competitor]).code,'READY');
});
test('cafe evidence resolves the recorded snack occurrence without a scene meal label',()=>{
 const scene={visit_date:'2026-09-11',t0:656,act:'cafe',meal:null,turn:null,basis:{m4:{event_id:'cafe2',decision_packet_ids:['packet2']}}};
 const activity={event_id:'cafe2',date:'2026-09-11',start_minute:656,meal_slot:'snack'};
 const flow={ledger:{run_id:'run'},plans:{P:{scenes:[scene]}},visit_days:[{flow:{plans:{P:{m4:{activity_history:[activity]}}}}}]};
 const target={run_id:'run',customer_id:'P',date:'2026-09-11',slot:'snack',event_id:'cafe2',decision_id:'packet2'};
 assert.equal(S.resolveDecisionScene(flow,target).index,0);
 for(const change of [{date:'2026-09-10'},{start_minute:655},{event_id:'other'},{meal_slot:'dinner'}]){
  const changed=structuredClone(flow);Object.assign(changed.visit_days[0].flow.plans.P.m4.activity_history[0],change);assert.throws(()=>S.resolveDecisionScene(changed,target));
 }
});
