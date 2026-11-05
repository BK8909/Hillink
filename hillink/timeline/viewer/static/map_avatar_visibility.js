/* Map rendering only: scale around the original foot anchor; preserve all model coordinates. */
(()=>{
 'use strict';
 const NS='http://www.w3.org/2000/svg',map=document.querySelector('#map');
 if(!map||window.HLMapAvatarVisibility)return;
 // Do not enlarge further when the existing mobile layout leaves a narrow map.
 const factor=n=>map.getBoundingClientRect().width<240?1:n>4?1.08:n>2?1.15:1.20;
 const selected=o=>!!o.hl||(typeof AG!=='undefined'&&AG.res&&typeof agIsOne==='function'&&agIsOne(AG.res));
 const originalImage=agAvatarImg,originalSvg=agAvatarSvg,originalMove=agAvatarMove;
 agAvatarMove=function(el,key,x,y,o={}){const result=originalMove.apply(this,arguments);if(el.dataset.visualScale){el.dataset.visualAnchorX=x;el.dataset.visualAnchorY=y;}return result;};
 function decorate(html,n,x,y,k,o={},image=true){
  if(o.icon||html.includes('data-visual-scale='))return html;
  const active=selected(o),scale=active?factor(n):1;
  const local=image?`scale(${scale})`:`translate(${x},${y}) scale(${scale}) translate(${-x},${-y})`;
  const h=(n>2?50:n===2?46:42)*k*(o.hl?(o.walk?1.2:1.08):1)*scale;
  return html.replace(/^(<g class="ag-avatar[^"]*)("[^>]*>)([\s\S]*)(<\/g>)$/,
   (_,a,b,body,end)=>`${a} ag-vis-enhanced${active?' ag-vis-selected':''}${b.slice(0,-1)} data-visual-scale="${scale}" data-visual-height="${h}" data-visual-members="${n}" data-visual-anchor-x="${x}" data-visual-anchor-y="${y}"><g class="ag-visual" transform="${local}">${body}</g>${end}`);
 }
 agAvatarImg=function(key,x,y,k,cls='',o={}){return decorate(originalImage.apply(this,arguments),AG.avm[key].n_members,x,y,k,o,true);};
 agAvatarSvg=function(pid,n,x,y,k,cls='',o={}){return decorate(originalSvg.apply(this,arguments),n,x,y,k,o,false);};
 const defs=document.createElementNS(NS,'defs');
 defs.innerHTML=`<filter id="hlAvatarSilhouette" x="-35%" y="-35%" width="170%" height="180%" color-interpolation-filters="sRGB">
  <feMorphology in="SourceAlpha" operator="dilate" radius="2" result="darkMask" data-edge="dark"/>
  <feOffset in="darkMask" dy="1" result="darkOffset" data-edge="offset"/><feFlood flood-color="#393532" flood-opacity=".72"/><feComposite in2="darkOffset" operator="in" result="dark"/>
  <feMorphology in="SourceAlpha" operator="dilate" radius="1.25" result="lightMask" data-edge="light"/>
  <feFlood flood-color="#fff8ed"/><feComposite in2="lightMask" operator="in" result="light"/>
  <feMerge><feMergeNode in="dark"/><feMergeNode in="light"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
 map.insertBefore(defs,map.firstChild);
 function sync(){
  const k=typeof mapK==='function'?mapK():1;
  for(const [name,attr,value] of [['dark','radius',1.9*k],['light','radius',1.25*k],['offset','dy',.9*k]]){
   const node=defs.querySelector(`[data-edge="${name}"]`),v=value.toFixed(2);if(node.getAttribute(attr)!==v)node.setAttribute(attr,v);
  }
  const trail=map.querySelector('#trail');
  // Selected walking figures render above location labels and nonselected pins.
  if(trail?.querySelector('.ag-vis-selected')){if(map.lastElementChild!==trail)map.appendChild(trail);}
  else {const pins=map.querySelector('#pins');if(trail&&pins&&trail.nextElementSibling!==pins)map.insertBefore(trail,pins);}
  const avatar=trail?.querySelector('.ag-vis-selected')||map.querySelector('#agent .single .ag-vis-selected');
  if(!avatar)return;
  const head=Number(avatar.dataset.visualAnchorY)-Number(avatar.dataset.visualHeight),gap=8*k;
  const tags=[...map.querySelectorAll('#route .ag-hl-tag,#agent .single .ag-tag')];
  for(const tag of tags){
   const rect=tag.querySelector('rect'),text=tag.querySelector('text');if(!rect||!text)continue;
   if(!tag.dataset.visibilityReady){
    const w=Number(rect.getAttribute('width'));rect.setAttribute('x',Number(rect.getAttribute('x'))+w*.05);rect.setAttribute('width',w*.9);
    text.style.fontSize=(10.5*k).toFixed(2)+'px';tag.dataset.visibilityReady='1';
   }
   const bottom=Number(rect.getAttribute('y'))+Number(rect.getAttribute('height'));
   tag.setAttribute('transform',`translate(0,${Math.min(0,head-gap-bottom).toFixed(2)})`);
  }
 }
 for(const name of ['agDrawRoute','agDrawMap','agReadyAvatar']){
  const original=window[name];if(typeof original!=='function')continue;
  window[name]=function(...args){const result=original.apply(this,args);sync();return result;};
 }
 window.HLMapAvatarVisibility=Object.freeze({version:'map-avatar-visibility-v1',factor,sync});
})();
