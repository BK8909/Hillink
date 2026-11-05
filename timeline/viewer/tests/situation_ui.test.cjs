const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ctx={window:{addEventListener(){}}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/situation.js'),'utf8'),ctx);
const options=JSON.parse(fs.readFileSync(path.join(__dirname,'../static/situation_options.json'),'utf8'));
test('event off/on retains persona, seed and automatic visit profile',()=>{
 const base={event:'none',custom:false,seed:0};const a=ctx.situationRequest('A01',base,options),b=ctx.situationRequest('A01',{...base,event:'wine'},options);
 assert.equal(a.event,false);assert.equal(b.event,true);assert.equal(a.visit_override,null);assert.equal(b.visit_override,null);
 assert.deepEqual(JSON.parse(JSON.stringify({...a,event:true})),JSON.parse(JSON.stringify(b)));
});
test('future event and unfinished visit conditions cannot execute',()=>{
 for(const x of options.events.filter(x=>!x.enabled)) assert.throws(()=>ctx.situationRequest('A01',{event:x.id,seed:0},options));
 assert.throws(()=>ctx.situationRequest('A01',{event:'none',custom:true,stay:'1',party:'2',phase:'',building:''},options));
});
test('valid operator visit conditions are mapped without future axes',()=>{
 const r=ctx.situationRequest('A07',{event:'wine',seed:2,custom:true,stay:'0',party:'2',weather:'rain',weekday:'weekday'},options);
 assert.deepEqual(JSON.parse(JSON.stringify(r.visit_override)),{A07:{stay:false,building:null,phase:'visit',party_size:2}});
 assert.equal('weather' in r,false);assert.equal('weekday' in r,false);assert.equal(r.seed,2);
});
