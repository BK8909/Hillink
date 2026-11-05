/* Presentation of the already validated local registry; no publication mutation. */
(()=>{
 const profiles=new Map(),details=new Map();
 async function load(id){
  if(!libEng(id)?.isolated_qa)return null;
  if(!details.has(id)){
   const r=await fetch('/api/runtime/intake?customer='+encodeURIComponent(id));
   if(!r.ok)throw new Error('비공개 검수 프로필을 열지 못했습니다.');
   const d=await r.json();if(d.customer.id!==id||d.public_approval!==false)throw new Error('검수 고객 연결을 확인해 주세요.');
   details.set(id,d);profiles.set(id,d.customer);
  }return details.get(id);
 }
 async function show(id, factIds=[]){
  const d=await load(id);if(!d)return;
  let el=document.querySelector('#privateIntakeDialog');if(!el){el=document.createElement('dialog');el.id='privateIntakeDialog';document.body.append(el);}
  const bars=libEng(id)?.bars||[];
  el.innerHTML=`<button class="cf-btn" data-close>닫기</button><h2>${esc(id)} · 비공개 검수 프로필</h2><p>${esc(d.caution)}</p><p>기술 RUNNABLE · 사람 의미 승인 대기 · 공개·시연 승인 0</p>${d.holds.map(h=>`<p>${esc(h)}</p>`).join('')}<h3>실행에 연결된 개인 성향</h3>${bars.map(x=>`<p><b>${esc(x.label)}</b> · ${x.status==='observed'?'후기 근거 있음':'근거 미확인'} · ${x.level==null?'UNKNOWN':x.level}</p>`).join('')}<details><summary>성향별 Fact 연결</summary>${Object.entries(d.facets).map(([k,v])=>`<p><b>${esc(k)}</b>: ${v.evidence.map(e=>esc(e.fact_id)).join(', ')||'근거 미확인'}</p>`).join('')}</details><details><summary>후기 Fact ${d.customer.engine.n}개</summary>${Object.entries(d.customer.engine.facts).map(([id,f])=>`<p data-intake-fact="${esc(id)}"><b>${esc(id)}</b> · ${esc(f.gist)} <small>${esc(f.actor||'UNKNOWN')} / ${esc(f.time_scope||'UNKNOWN')}</small></p>`).join('')}</details><details><summary>입력 버전</summary><p>프로필 SHA256 ${esc(d.lineage.profile_sha256)}</p><p>라이브러리 SHA256 ${esc(d.lineage.library_sha256)}</p></details><button class="cf-btn cf-primary" data-condition>이 고객의 방문 조건 설정</button>`;
  el.querySelector('[data-close]').onclick=()=>el.close();el.querySelector('[data-condition]').onclick=()=>{el.close();situationOpen(id);};if(!el.open)el.showModal();
  const review=LIBV.displayReview?.[id];
  for(const [fid,text] of Object.entries(review?.changes.fact_summaries||{})){
   const row=[...el.querySelectorAll('[data-intake-fact]')].find(x=>x.dataset.intakeFact===fid);
   if(row){const previous=row.innerHTML;row.innerHTML=`<b>${esc(fid)}</b> · ${esc(text)} <small>원문 대조 표시 보정 · 엔진 입력은 변경하지 않음</small><details><summary>현재 보존된 엔진 입력</summary>${previous}</details>`;}
  }
  if(factIds.length){const fact=[...el.querySelectorAll("[data-intake-fact]")].find(x=>factIds.includes(x.dataset.intakeFact));if(fact){fact.closest("details").open=true;fact.style.background="#fff1cc";fact.scrollIntoView({block:"center"});}}
 }
 window.HillinkPrivateIntake={get:id=>profiles.get(id),load,show};
})();
