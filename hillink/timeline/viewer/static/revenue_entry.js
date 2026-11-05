/* Presentation-only entry. No run, ledger or filter values are written here. */
(function(){'use strict';
const reduce=matchMedia('(prefers-reduced-motion: reduce)');
let active=[],serial=0;
function cancel(){active.forEach(a=>a.cancel());active=[];}
function enter(){
 cancel();
 const panel=document.querySelector('#opxView .rev-command');
 if(!panel||MODE!=='opx'||reduce.matches||panel.querySelector('.rev-overlay'))return;
 const mobile=matchMedia('(max-width:650px)').matches,distance=mobile?16:28,duration=mobile?420:600;
 const animate=(el,delay,main=false)=>{
  if(!el)return;
  const animation=el.animate([{opacity:0,transform:`perspective(1200px) translateY(${main?20:distance}px) rotateX(${main ? 1 : 3}deg) scale(${main ? 0.98 : 0.97})`},{opacity:1,transform:'perspective(1200px) translateY(0) rotateX(0deg) scale(1)'}],{duration:main?550:duration,delay,easing:'cubic-bezier(.22,.7,.3,1)',fill:'backwards'});
  active.push(animation);
 };
 animate(panel,0,true);
 panel.querySelectorAll('.rev-command-kpis>article').forEach((el,i)=>animate(el,(mobile?240:400)+i*(mobile?80:120)));
 ['.rev-board-flow','.rev-board-choices','.rev-board-time','.rev-board-ledger'].forEach((sel,i)=>animate(panel.querySelector(sel),(mobile?[620,700,900,1000]:[950,1050,1350,1500])[i]));
 panel.dataset.entrySequence=String(++serial);
 // A diagnostic event contains no customer, run or financial data.
 document.dispatchEvent(new CustomEvent('hillink:revenue-motion',{detail:{sequence:serial,mobile,duration:mobile?1420:2100}}));
}
reduce.addEventListener('change',()=>{if(reduce.matches)cancel();});
document.addEventListener('hillink:navigation',e=>{
 if(e.detail.view!=='revenue'){cancel();return;}
 if(e.detail.fresh)enter();
});
window.HLRevenueEntry={enter,cancel};
})();
