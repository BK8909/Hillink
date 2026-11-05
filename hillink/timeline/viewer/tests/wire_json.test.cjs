const test=require('node:test'),assert=require('node:assert/strict');
const {unpack}=require('../static/wire_json.js');
test('wire references preserve original typed values without prototype pollution',()=>{
 const wire={hillink_transport:'HILLINK_JSON_DAG_V1',nodes:[['d',[['value','source'],['__proto__','safe']]],['a',[{r:0},{r:0}]],['d',[['plans',{r:1}],['quantity',2],['boolean',true]]]],root:{r:2}};
 const out=unpack(wire);assert.deepEqual(out.plans[0],out.plans[1]);assert.equal(out.quantity,2);assert.equal(out.boolean,true);assert.equal(Object.getPrototypeOf(out.plans[0]),Object.prototype);assert.equal(out.plans[0].__proto__,'safe');assert.equal({}.safe,undefined);
});
test('forward, cyclic and unknown wire references fail closed',()=>{
 for(const r of [-1,0,100,'0'])assert.throws(()=>unpack({hillink_transport:'HILLINK_JSON_DAG_V1',nodes:[['a',[{r}]]],root:{r:0}}));
 const ordinary={plans:{A:{}}};assert.equal(unpack(ordinary),ordinary);
});
test('display normalization visits shared subtrees once and preserves original model evidence',()=>{
 const fs=require('fs'),vm=require('vm'),path=require('path'),source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');let visits=0;
 const ctx={WeakSet,term:s=>{visits++;return s.replace('끼니','식사')},noName:s=>s.replace('개발자','')};vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('function deName('),source.indexOf('// 10/19 소연')),ctx);
 const original={selected_plan:{decision_summary:'개발자 끼니 원 판단'}},shared={label:'끼니 표시'},input={a:shared,b:shared,aliasOfOriginal:original,plans:{A:{autonomous_decisions:[original]}},recorded_review:{finding:'개발자 끼니 평가 원문'}};
 const out=ctx.deName(input);assert.equal(out.aliasOfOriginal.selected_plan.decision_summary,'개발자 끼니 원 판단');assert.equal(out.a,out.b);assert.equal(out.a.label,'식사 표시');assert.equal(out.plans.A.autonomous_decisions[0].selected_plan.decision_summary,'개발자 끼니 원 판단');assert.equal(out.recorded_review.finding,'개발자 끼니 평가 원문');
});
