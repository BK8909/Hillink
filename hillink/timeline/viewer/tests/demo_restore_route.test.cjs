const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
test('restoring a day view cannot rewrite the immutable run URL as a new execution',()=>{
 const handlers={},ctx={window:{addEventListener(){}},document:{addEventListener:(k,f)=>handlers[k]=f,getElementById:()=>null},location:{hash:'#flow/A06/0/run/confirmed'},HILLINK_APP_READY:new Promise(()=>{}),fetch:()=>new Promise(()=>{}),api(){},console:{info(){}},AG:{mode:'agent',one:'A06',cond:{event:false}},BH:{restoring:true}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/demo_story.js'),'utf8'),ctx);let pushes=0;ctx.dsPush=()=>pushes++;
 handlers['hl:agrun']();assert.equal(pushes,0);
 ctx.BH.restoring=false;handlers['hl:agrun']();assert.equal(pushes,1);
});
