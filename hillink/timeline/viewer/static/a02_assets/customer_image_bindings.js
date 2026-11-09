/* Display-only ID joins. Never write a profile, party fact, visit, choice or receipt. */
(()=>{
 'use strict';
 const rows=new Map();
 const ready=fetch('/static/a02_assets/customer_image_map.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('Customer image map unavailable');return r.json();}).then(data=>{
  for(const row of data.customers){
   const entry=typeof HLD==='function'?HLD()[row.customer_id]:HL_DISPLAY.entries[row.customer_id];
   if(!entry||entry.no!==row.display_no)throw Error('Image/customer registry mismatch: '+row.customer_id);
   rows.set(row.customer_id,Object.freeze(row));
  }
 });
 const originalLoad=libLoad;
 libLoad=async function(...args){await Promise.all([originalLoad.apply(this,args),ready]);};
 const oldThumb=libThumbP,oldCImg=libCImg;
 function image(pid,cls){const row=rows.get(pid);return row?`<div class="lb-th ${esc(cls||'')}" data-customer-image="${esc(pid)}"><img src="${esc(row.thumbnail)}" alt="${esc('No.'+row.display_no+' 콘셉트 이미지 · 실제 인물 사진 아님')}" loading="lazy"></div>`:null;}
 libThumbP=(p,cls='')=>image(p.id,cls)||oldThumb(p,cls);
 libCImg=(c,cls='')=>image(c.id,cls)||oldCImg(c,cls);
 const oldComp=agComp;
 agComp=function(pid,n){
  const cp=oldComp(pid,n),row=rows.get(pid),pool=AG.avm||{};
  if(!row||!cp.n)return representative(pid,cp,pool);
  const native=row.native_avatar_key,portrait=row.portrait_key;
  const fits=key=>pool[key]&&pool[key].n_members===cp.n&&(!pool[key].visit_relations||pool[key].visit_relations.includes(cp.rel));
  const preferred=[native,native&&native+'_group2',portrait];
  let key=preferred.find(k=>k&&fits(k));
  if(!key&&cp.av)return cp;
  if(!key)key=[cp.rel==='friends'?'friends_neutral_3':null,`neutral_group_${cp.n}`].find(k=>k&&fits(k));
  if(key)return {...cp,av:key,asset_status:'VALID',asset_slot:null};
  return representative(pid,cp,pool);
 };
 // 10/26 user rule, restored 11/9: a party size without its own picture still shows a picture (mood only — the
 // number of people is the card's '이번 인원', not the drawing). Family types with 4 → the 4-person family sprite,
 // 5 or more → the 5-person family sprite; friends → the friends group; any other group → the neutral group.
 function representative(pid,cp,pool){
  if(cp.av||!cp.n||cp.n<2)return cp;
  const ty=(typeof libP==='function'&&typeof LIBV!=='undefined'&&LIBV.data&&libP(pid)&&(libP(pid).type_group||libP(pid).type))||'';
  const family=/가족|family/.test(ty+' '+cp.rel),friends=/친구|friend/.test(ty+' '+cp.rel);
  const key=[family&&cp.n===4?'family_kid2':null,family&&cp.n>=5?'family_3gen':null,friends?'friends_neutral_3':null,'neutral_group_3','neutral_group_2'].find(k=>k&&pool[k]);
  return key?{...cp,av:key,asset_status:'REPRESENTATIVE_PICTURE',asset_slot:null}:cp;
 }
 const oldChip=libAvChip;
 libAvChip=function(id){
  // Catalogue scene aliases are looked up explicitly; no array-position join.
  const canonical=HLD()[id]?.canonical_customer_id||id,row=rows.get(canonical);
  if(!row)return oldChip(id);
  const party=dnoParty(canonical);
  if(party.n)return oldChip(canonical);
  return `<span class="lb-avc unk" title="고객 대표 캐릭터 · 실제 외모·동행 인원을 뜻하지 않음"><img class="ag-pcav" src="/static/avatars/${esc(row.portrait_key)}_portrait.png" width="26" height="26" alt="대표 캐릭터"><em>인원 확인 전</em></span>`;
 };
 // A catalog card's scene is not a customer ID. Bind its chip to the actual card ID.
 const oldCCard=libCCard;
 libCCard=function(c){return oldCCard({...c,scene:c.id});};
 const oldCDetail=libCDetail;
 libCDetail=function(id){
  const result=oldCDetail(id),row=rows.get(id),hero=document.querySelector('.lb-hero .lb-avc');
  if(row&&hero)hero.outerHTML=libAvChip(id);
  return result;
 };
 window.A02CustomerImages=Object.freeze({ready,rows,version:'a02-45-images-20261031'});
 ready.then(()=>{if(typeof MODE!=='undefined'&&MODE==='library'&&!LIBV.open&&!LIBV.cOpen&&!LIBV.situation)libGrid();}).catch(error=>console.error(error));
})();
