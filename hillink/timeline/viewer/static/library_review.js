/* One owner library; server authorization and approval flags are unchanged. */
(()=>{
 const privateIds=()=>new Set((AG.meta?.personas||[]).filter(p=>p.isolated_qa).map(p=>p.id));
 const originalC=libC,originalPub=libPub,originalPublished=libPublished,originalLoad=libLoad,originalThumb=libThumbP;
 let ready;
 const patternForBar={food:'food_exploration',space:'space_atmosphere',value_check:'prepurchase_value',benefit:'benefit_use',rest_need:'recovery_service',routine:'practical_repeat_use'};
 let displayReady;
 async function recoverDisplayTraits(){
  if(!displayReady)displayReady=Promise.all(originalPub().filter(p=>!(p.traits||[]).length&&libEng(p.id)).map(async p=>{
   try {
   const response=await fetch('/api/strategy/evidence?customer='+encodeURIComponent(p.id));if(!response.ok)return;
   const bundle=await response.json();if(bundle.customer_id!==p.id)return;
   p.display_list_line=libLine(p); // Preserve the existing visit summary before adding a signature.
   p.traits=(libEng(p.id).bars||[]).filter(b=>b.status==='observed').map(b=>({id:b.key,trait:b.label,
    fact_ids:[...new Set((bundle.patterns?.[patternForBar[b.key]]?.contributions||[]).flatMap(c=>c.fact_ids))].filter(id=>p.engine?.facts?.[id]?.gist),
    strength:'observed',display_basis:'EXISTING_PATTERN',semantic_status:'SEMANTIC_HOLD'})).filter(t=>t.fact_ids.length);
   } catch (_) { p.display_projection_status='SEMANTIC_HOLD'; }
  }));await displayReady;
 }
 libLoad=async function(){await originalLoad();await recoverDisplayTraits();if(!privateIds().size)return;if(!ready)ready=Promise.all([...privateIds()].map(async id=>{const d=await HillinkPrivateIntake.load(id),p=d.customer,c=originalC().find(c=>c.id===id),m=libEng(id);p.type_group=c?.type||null;p.label='사용 가능한 후기 사실 '+p.engine.n+'개 · 개인 성향과 방문 조건으로 선택';p.traits=(m.bars||[]).filter(b=>b.status==='observed').map(b=>({id:b.key,trait:b.label,support:[],fact_ids:(d.facets[b.key]?.evidence||[]).filter(e=>e.grade==='rep'&&p.engine.facts[e.fact_id]?.gist).map(e=>e.fact_id),strength:'observed',display_basis:'EXISTING_FACET',semantic_status:'SEMANTIC_HOLD'}));p.wh_events=[];p.other_events=[];p.rules=[];}));await ready;};
 libPub=()=>[...originalPub(),...[...privateIds()].map(id=>HillinkPrivateIntake.get(id)).filter(p=>p&&!originalPub().some(x=>x.id===p.id))];
 libC=()=>originalC().filter(c=>!privateIds().has(c.id));
 libPublished=p=>originalPublished(p)||privateIds().has(p.id)&&!!HillinkPrivateIntake.get(p.id);
 libThumbP=function(p,cls=''){const card=originalC().find(c=>c.id===p.id);if(card)return libCImg(card,cls);if(privateIds().has(p.id))return `<div class="lb-th lb-th0 ${cls}"><span>고객 이미지 연결 확인 중</span></div>`;return originalThumb(p,cls);};
 const grid=libGrid;libGrid=function(){const ids=[...privateIds()];if(ids.some(id=>!HillinkPrivateIntake.get(id))){document.querySelector('#libraryView').innerHTML='<div class="lb"><p role="status">고객 프로필을 불러오는 중…</p></div>';libLoad().then(()=>grid());return;}return grid();};
 const enter=libEnter;libEnter=async()=>{await libLoad();return enter();};
 (async()=>{await HILLINK_APP_READY;await libLoad();if(MODE==='library'&&!LIBV.situation&&!LIBV.open)libGrid();})();
 const route=libApplyRoute;libApplyRoute=function(hash){
  const match=hash.match(/^#lib\/(?:card|draft)\/([^?]+)(.*)$/);if(match){const old=decodeURIComponent(match[1]),id=HLD()[old]?.canonical_customer_id||old;if(privateIds().has(id))return route('#lib/profile/'+encodeURIComponent(id)+match[2]);}
  return route(hash==='#lib/review'?'#lib':hash);
 };
 const load=HillinkPrivateIntake.load;HillinkPrivateIntake.show=async(id,facts=[])=>{await load(id);libOpen(id,facts);};
})();
