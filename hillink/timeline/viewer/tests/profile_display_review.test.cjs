const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const adapter=require('../static/profile_display_review.js');
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../handover/data/profile-display-review.json')));
test('45 display pairs remain distinct and evidence-limited customers remain HOLD',()=>{
 assert.equal(Object.keys(manifest.customers).length,45);
 for(const [id,r] of Object.entries(manifest.customers)){
  assert(r.changes.list_line && r.changes.signature,id);assert.notEqual(r.changes.list_line,r.changes.signature,id);
  assert(r.source_anchors.every(a=>a.customer_id===id),id);
  assert.equal(r.engine_changed,false);assert.equal(r.semantic_approval,false);assert.equal(r.thumbnail_approval,false);
 }
 for(const id of ['blog42','blog43'])assert.equal(manifest.customers[id].status,'EVIDENCE_LIMITED_DISPLAY_ONLY');
});
test('profile and catalog render the same wording without modifying engine inputs',()=>{
 for(const [id,r] of Object.entries(manifest.customers)){
  const original={id,engine:{facts:{'N15-F004':{gist:'original engine fact'}}},traits:[{level:0.2}]},saved=JSON.stringify(original);
  const p=adapter.profile(original,r),c=adapter.catalog({id,summary:'previous'},r);
  assert.equal(p.display_list_line,c.summary);assert.equal(p.display_signature,c.display_signature);
  assert.equal(JSON.stringify(original),saved);assert.deepEqual(p.traits,original.traits);
  if(id!=='N15')assert.deepEqual(p.engine,original.engine);
 }
});
test('profile availability does not depend on whether a display tagline exists',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../static/library.js'),'utf8');
 const state=source.match(/function libState\(p\) \{([^\n]+)\}/)[1];
 const fn=new Function('libHasProfile','libApproved','libRuntime','p',state);
 const p={id:'blog41'};assert.deepEqual(fn(()=>true,()=>true,()=>true,p),{has_profile:true,publish_approved:true,is_runnable:true});
 assert.equal(fn(()=>true,()=>false,()=>true,p).publish_approved,false);
});

test('missing companion evidence cannot classify blog43 as a solo visit',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../static/library.js'),'utf8');
 const fix=new Function(source.slice(0,source.indexOf('const LIB_CLAIM'))+';return LIB_TYPE_FIX.blog43')();
 assert.equal(fix.type,null);assert.equal(fix.label,'휴식 · 동행 미확인');
});
