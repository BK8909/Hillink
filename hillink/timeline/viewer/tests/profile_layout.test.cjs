const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/library.js'),'utf8');
function harness(){
 const ctx={setTimeout,clearTimeout,esc:s=>String(s??''),libShort:(s,n)=>s.slice(0,n),LIB:{photos:{}},window:{PLACE_THUMBS:{pick:loc=>({kind:'concept',approved:loc!=='hold'})}},placeImg:loc=>({src:'/'+loc,name:loc}),Image:class {set src(v){queueMicrotask(()=>{this.naturalWidth=v==='/bad'?0:1600;this.naturalHeight=900;v==='/bad'?this.onerror():this.onload();});}}};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('const LIB_PROFILE_IMAGE_CACHE'),source.indexOf('async function libDetail')),ctx);return ctx;
}
const rows=n=>Array.from({length:4},(_,i)=>({place:'place'+i,title:'Actual experience '+i,text:'Observed '+i,stage:'후기',src:'source'+i,eid:'e'+i,image:i<n?{src:'/place'+i,name:'place'+i,width:1600,height:900}:null}));
test('0–3 images use editorial text without placeholders and preserve every available image',()=>{
 const c=harness();for(let n=0;n<4;n++){const html=c.libProfileMoments(rows(n));assert.equal((html.match(/<img /g)||[]).length,n);assert.doesNotMatch(html,/lb-aph0|<svg|이미지 없음/);assert.match(html,/pv3-compact-list/);if(n)assert.match(html,/aspect-ratio:1600\/900/);for(let i=0;i<4;i++)assert.match(html,new RegExp('Actual experience '+i));if(n===3)assert.match(html,/관련 장소 이미지/);}
});
test('four usable images retain the accepted four-card structure',()=>{
 const html=harness().libProfileMoments(rows(4));assert.match(html,/class="lb-acts pvx-acts"/);assert.equal((html.match(/class="lb-act pvx-act/g)||[]).length,4);assert.doesNotMatch(html,/pvx-magazine/);
});
test('registration alone does not admit missing or held assets',async()=>{
 const c=harness(),r=[{place:'good'},{place:'bad'},{place:'hold'},{place:null}];await c.libProfilePrepareImages(r);assert.equal(r[0].image.width,1600);assert.equal(r[1].imageStatus,'LOAD_FAILED');assert.equal(r[2].imageStatus,'APPROVAL_HOLD');assert.equal(r[2].image,undefined);assert(!r[3].image);
});
test('a missing personal score remains three steps without invented causal contribution',()=>{
 const html=harness().libProfileFlowUnavailable({engine:{facts:{}}},'Observed engine choice','No personal contribution');assert.equal((html.match(/class="lib-fs/g)||[]).length,3);assert.match(html,/No personal contribution/);assert.match(html,/연결할 후기 경험이 확인되지/);assert.doesNotMatch(html,/\+0\.\d|확률/);
});
