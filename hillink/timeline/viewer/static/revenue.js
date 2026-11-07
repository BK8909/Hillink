function revRollupModel(L) {
  const rows=Object.values(L.receipts).flatMap(r=>r.rows), paid=rows.filter(r=>r.paid_krw>0), total=L.totals.paid_krw;
  const rank=d=>d==='ROOM'?0:d==='F&B'?1:d==='레저'?2:3;
  const keys=[r=>[r.customer_id],r=>[r.department,r.venue,r.product],r=>[r.department,r.venue],r=>[r.department],r=>['호텔 전체']];
  const columns=keys.map((key,level)=>{
    const map=new Map(); for(const row of paid){const parts=key(row),k=JSON.stringify(parts);if(!map.has(k))map.set(k,{key:k,parts,rows:[],amount:0});const g=map.get(k);g.rows.push(row);g.amount+=row.paid_krw;}
    let groups=[...map.values()].sort((a,b)=>b.amount-a.amount||a.key.localeCompare(b.key));
    if(level===1||level===2) {
      groups=[...new Set(groups.map(g=>g.parts[0]))].sort((a,b)=>rank(a)-rank(b)).flatMap(department=>{
        const list=groups.filter(g=>g.parts[0]===department);
        if(list.length<=2)return list;
        const rest=list.slice(1);return [list[0],{key:'other:'+department,parts:[department,`그 외 ${rest.length}${level===1?'개 상품':'개 업장'}`],rows:rest.flatMap(g=>g.rows),amount:rest.reduce((n,g)=>n+g.amount,0),other:true}];
      });
    } else if(level===0 && groups.length>6) {
      const rest=groups.slice(5);groups=[...groups.slice(0,5),{key:'other',parts:[`그 외 ${rest.length}팀`],rows:rest.flatMap(g=>g.rows),amount:rest.reduce((n,g)=>n+g.amount,0),other:true}];
    } else if(level===3) groups.sort((a,b)=>rank(a.parts[0])-rank(b.parts[0]));
    return groups.map(g=>({...g,id:`${level}:${g.key}`,level,x:16+level*270,w:228,h:Math.max(104+(total?100*g.amount/total:0),revRollLabelLines(revRollNodeLabel(L,g,level)).length*18+66)}));
  });
  const height=Math.max(330,...columns.map(c=>c.reduce((n,g)=>n+g.h,0)+Math.max(0,c.length-1)*24));
  columns.forEach(c=>{const used=c.reduce((n,g)=>n+g.h,0)+Math.max(0,c.length-1)*24;let y=76+(height-used)/2;c.forEach(g=>{g.y=y;y+=g.h+24;});});
  const links=[];for(let i=0;i<4;i++)for(const a of columns[i])for(const b of columns[i+1]){const ids=new Set(b.rows.map(r=>r.row_id)),matches=a.rows.filter(r=>ids.has(r.row_id));if(matches.length)links.push({a,b,rows:matches,amount:matches.reduce((n,r)=>n+r.paid_krw,0)});}
  for(const column of columns) for(const n of column) {
    for(const [side,sort] of [['a','b'],['b','a']]) {let offset=0;links.filter(l=>l[side]===n).sort((a,b)=>a[sort].y-b[sort].y).forEach(l=>{const h=(n.h-12)*l.amount/n.amount;l[side==='a'?'sy':'ty']=n.y+6+offset+h/2;offset+=h;});}
  }
  return {rows,total,columns,links,height:height+112};
}
function revRollNodeLabel(L,n,level=n.level) {
  return level===0&&!n.other?L.receipts[n.parts[0]].display_id:level===1&&!n.other&&n.parts[2].startsWith('객실 1박')?n.parts[1]+' · '+n.parts[2]:n.parts[n.parts.length-1];
}
function revRollLabelLines(text) {
  const lines=[''];let units=0;
  for(const ch of String(text)){const width=/[ -~]/.test(ch)?.55:1;if(units+width>14){lines.push('');units=0;}lines[lines.length-1]+=ch;units+=width;}
  return lines;
}
function revRollColor(rows) { const ds=new Set(rows.map(r=>r.department));return ds.size!==1?'#8493a1':rows[0].department==='F&B'?'#bd8537':rows[0].department==='레저'?'#298d8d':'#6685a4'; }
function revRollLinksHTML(model,ids,selected,compact=false) {
  return model.links.map(link=>{
    const active=link.rows.some(row=>ids.has(row.row_id)),width=Math.max(compact?.7:.6,(compact?48:100)*link.amount/Math.max(1,model.total)),tone=revRollColor(link.rows),bend=(link.b.x-link.a.x-link.a.w)*.45;
    const path=`M${link.a.x+link.a.w},${link.sy} C${link.a.x+link.a.w+bend},${link.sy} ${link.b.x-bend},${link.ty} ${link.b.x},${link.ty}`;
    return `<path d="${path}" fill="none" stroke="${tone}" stroke-width="${width+1.2}" opacity="${selected?(active?.34:.08):.25}" data-roll-outline pointer-events="none"/><path d="${path}" fill="none" stroke="${tone}" stroke-width="${width}" opacity="${selected?(active?.8:.18):.48}" data-roll-link="${active?'active':'muted'}" data-link-amount="${link.amount}"><title>${rcMoney(link.amount)} · ${(100*link.amount/Math.max(1,model.total)).toFixed(1)}%</title></path>`;
  }).join('');
}
function revRollSurfaceHTML(node,id,radius=8) {
  return `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:color-mix(in srgb,var(--roll-tone) 2%,#fff)"/><stop offset="1" style="stop-color:color-mix(in srgb,var(--roll-tone) 10%,#fff)"/></linearGradient></defs><rect class="rev-roll-surface" style="fill:url(#${id})" x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}" rx="${radius}"/>`;
}
function revRollTabsHTML() {
  return `<div class="rev-roll-tabs"><button class="cf-link" data-rev-view="flow" aria-pressed="${REV.rollView!=='venues'}">L5 → L1 집계 흐름</button><button class="cf-link" data-rev-view="venues" aria-pressed="${REV.rollView==='venues'}">업장 비교</button></div>`;
}
function revRollSelection(L,model) { return REV.rollSelection&&REV.rollSelection.run===L.run_id?model.columns.flat().find(n=>n.id===REV.rollSelection.id):null; }
function revFullRollupHTML(L) {
  const m=revRollupModel(L),selected=revRollSelection(L,m),row=m.rows.find(r=>r.row_id===REV.rollRow),ids=new Set(row?[row.row_id]:selected?selected.rows.map(r=>r.row_id):m.rows.map(r=>r.row_id));
  const titles=['고객별 거래','상품·패키지','업장','부문','호텔 전체'];
  return `<div class="rev-roll-toolbar"><span>같은 실행의 가상 거래</span><button class="cf-link" data-rev-roll-clear>전체 거래 · 선택 해제</button></div><div class="rev-roll-scroll" tabindex="0" aria-label="고객별 거래부터 호텔 전체까지 집계 흐름"><svg class="rev-roll-svg" viewBox="0 0 1340 ${m.height}" style="height:${m.height}px" role="group" aria-label="고객 거래에서 호텔 전체로 집계되는 흐름">${titles.map((t,i)=>{const x=130+270*i;return `<g class="rev-roll-stage"><rect x="${x-18}" y="4" width="36" height="22" rx="7"/><text x="${x}" y="19" class="rev-roll-code" text-anchor="middle">${['L5','L4','L3','L2','L1'][i]}</text><text x="${x}" y="49" class="rev-roll-heading" text-anchor="middle">${t}</text></g>`;}).join('')}${revRollLinksHTML(m,ids,!!(selected||row))}${m.columns.flat().map((n,i)=>{const label=revRollNodeLabel(L,n),active=n.rows.some(r=>ids.has(r.row_id)),lines=revRollLabelLines(label),cx=n.x+n.w/2,top=n.y+(n.h-(lines.length*18+45))/2;return `<g class="rev-roll-node${n.level===4?' rev-roll-total':''}${selected&&selected.id===n.id?' on':''}${(selected||row)&&active?' in-path':''}" style="--roll-tone:${revRollColor(n.rows)}" data-rev-roll="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(label)}, ${rcMoney(n.amount)}, 거래 ${n.rows.length}건" opacity="${active?1:.35}"><title>${esc(n.parts.join(' · '))} · ${n.rows.length}건 · ${rcMoney(n.amount)}</title>${revRollSurfaceHTML(n,'rev-full-surface-'+i,9)}<text class="rev-roll-name" text-anchor="middle">${lines.map((line,i)=>`<tspan x="${cx}" y="${top+15+i*18}">${esc(line)}</tspan>`).join('')}</text><text x="${cx}" y="${top+lines.length*18+22}" text-anchor="middle" class="rev-roll-amount">${rcMoney(n.amount)}</text><text x="${cx}" y="${top+lines.length*18+41}" text-anchor="middle" class="rev-roll-share">${(100*n.amount/Math.max(1,m.total)).toFixed(1)}%</text></g>`;}).join('')}</svg></div><div class="rev-roll-foot">${m.total?`각 열 합계 ${rcMoney(m.total)} · 연결선 굵기는 결제액 비중`:'금액이 확인된 유료 거래가 없습니다.'} · 무료 활동 ${Object.values(L.receipts).flatMap(r=>r.actions||[]).filter(a=>a.purchase_status==='FREE_USE').length}건은 금액 집계와 별도</div>${revUXSelectionHTML(L)}`;
}
function revReasonFor(L,pid,index) {
  if(!REV.flow||!REV.flow.ledger||REV.flow.ledger.run_id!==L.run_id||typeof agBRExplain!=='function')return null;
  return agBRExplain({result:REV.flow,ledger:L},pid,index);
}
function revRowReason(L,row) {
  const plan=REV.flow&&REV.flow.plans[row.customer_id];if(!plan||row.act==='room_night')return null;
  const index=plan.scenes.findIndex((s,i)=>(s.visit_day||1)===(row.visit_day||1)&&s.act===row.act&&agHM(s.t0)===row.time&&(!row.selection_id||!s.basis?.selection_id||row.selection_id===s.basis.selection_id));
  return index>=0?revReasonFor(L,row.customer_id,index):null;
}
function revRollDrillHTML(L) {
  const model=revActiveRollModel(L),node=revRollSelection(L,model),rows=node?node.rows:model.rows,chosen=rows.find(r=>r.row_id===REV.rollRow),reason=chosen&&revRowReason(L,chosen);
  return `<div class="rev-console-heading"><div><span class="rev-command-eyebrow">TRANSACTION TRACE</span><h3>${node?esc(node.level===0&&node.key!=='other'?L.receipts[node.parts[0]].display_id:node.parts[node.parts.length-1]):'고객 거래와 선택 근거'}</h3></div><small>${rows.length}건</small></div><div class="rev-roll-transactions">${rows.map(r=>`<button class="rev-roll-transaction${chosen&&chosen.row_id===r.row_id?' on':''}" data-rev-row="${esc(r.row_id)}"><span><b>${esc(L.receipts[r.customer_id].display_id)} · ${esc(r.visit_date||'')}</b><small>${esc(r.product)}</small></span><strong>${r.status==='금액 미확인'?'금액 미확인':r.paid_krw>0?rcMoney(r.paid_krw):r.purchase_status==='FREE_USE'?'무료 이용':r.purchase_status==='PACKAGE_INCLUDED'?'포함 혜택':'추가 결제 없음'}</strong></button>`).join('')}</div>${chosen?`<div class="rev-roll-evidence"><b>${esc(chosen.venue)} · ${esc(chosen.product)}</b>${reason?`${agReadableHTML(reason.sentences.join(' '),JSON.stringify([L.run_id,chosen.row_id,'reason']),3)}`:''}<p>${esc(chosen.price_status==='VIRTUAL_MODEL_UNIT_PRICE'?'가상 모델 단가':chosen.price_status||chosen.status)} · ${esc(chosen.price_basis||'가격 근거 미기록')}</p>${chosen.act==='room_night'?'<p>선택한 방문 조건에서 생성된 객실박 거래입니다. 객실 수·숙박일과 모델 가격을 연결하며 별도 행동 선택 이유를 생성하지 않습니다.</p>':`<p>${esc(chosen.time||'시각 미기록')} · 선택 사실 근거 ${(chosen.fact_ids||[]).length}개</p>`}<button class="cf-link" data-rev-transaction-action="${esc(chosen.row_id)}">${chosen.act==='room_night'?'고객 방문 조건 보기':'고객 행동·선택 이유 보기'} →</button></div>`:'<p class="rc-note">집계 단계와 거래를 선택하면 해당 고객의 행동으로 돌아갑니다.</p>'}`;
}
function revSetupControlsHTML() {
  const selected=REV.scope==='all'?new Set(REV.allIds):REV.selected;
  return `<div class="rev-controls"><div class="rev-client-control"><label>고객 선택</label>${hlCustomerPickerHTML(REV.allIds,selected,'revenue',REV.pickerOpen)}</div><label>숙박 일정<select class="cf-input" id="revDuration">${[['day_visit','당일 방문 (0박)'],['stay_1','1박 2일'],['stay_2','2박 3일'],['stay_3','3박 4일']].map(([v,t])=>`<option value="${v}"${REV.duration===v?' selected':''}>${t}</option>`).join('')}</select></label><label>기준 데이터<select class="cf-input" id="revReference">${REV_REFERENCE.map(([v,t])=>`<option value="${v}"${REV.referenceProfile===v?' selected':''}>${t}</option>`).join('')}</select></label><label>행동 사전정보<select class="cf-input" id="revPrior"><option value="OFF"${REV.prior==='OFF'?' selected':''}>끄기 (개인 근거만)</option><option value="HOTEL_PRIOR_V1"${REV.prior==='HOTEL_PRIOR_V1'?' selected':''}>켜기 · 연구 (규칙 엔진)</option></select></label><label>행사<select class="cf-input" id="revScenario"><option value="none"${REV.scenario==='none'?' selected':''}>행사 없음</option><option value="wine"${REV.scenario==='wine'?' selected':''}>와인페어 있음</option></select></label><button type="button" id="revRun" class="cf-btn cf-primary"${REV.busy||!revIds().length?' disabled':''}>${REV.busy?'예상 매출 계산 중...':'예상 매출 계산'}</button></div>`;
}
function revNewSetup() {
  const L=REV.ledger||REV.latest&&REV.latest.flow.ledger;if(L){REV.selected=new Set(Object.keys(L.receipts).filter(id=>REV.allIds.includes(id)));REV.duration=L.context.duration;REV.scenario=revScenarioOf(L.context);}
  REV.scope='selected';REV.search='';REV.pickerOpen=false;REV.setupOpen=true;REV.err=null;revRender();
}
function revSetupPanelHTML() {
  return `<section class="rev-settings-panel"><div class="rev-console-heading"><div><h3>새 계산 설정</h3><p>선택한 조건은 계산 버튼을 누를 때 적용됩니다.</p></div>${REV.ledger?'<button class="cf-btn" data-rev-setup-close>닫기 ×</button>':''}</div>${revSetupControlsHTML()}${REV.ledger?`<p class="rev-prior-result">배경은 이전 결과 · ${Object.values(REV.ledger.receipts).map(r=>esc(r.display_id)).join(' · ')} · ${rcMoney(REV.ledger.totals.paid_krw)}</p>`:''}${REV.err?`<p role="alert">${esc(REV.err)}</p>`:''}</section>`;
}
function revConfigHTML() { return `<section class="rev-root rev-command rev-harmonized rev-compact"><header class="rev-command-head"><div class="rev-heading-main"><h2>매출 집계</h2><div class="rev-command-tools"><button class="cf-btn" data-rev-recent>최근 실행</button></div></div></header>${revSetupPanelHTML()}</section>`; }
function revCompactModel(L) {
  const width=REV.compactWidth||920,pad=width*.025,nodeWidth=Math.max(120,Math.min(140,(width*.95-120)/5)),step=(width-2*pad-nodeWidth)/4;
  const full=revRollupModel(L),columns=full.columns.map((column,level)=>{
    let groups=column;
    if(level===0&&column.length>3){const rest=column.slice(2);groups=[...column.slice(0,2),{id:'compact:customers',level,parts:['그 외 '+rest.reduce((n,g)=>n+g.rows.reduce((set,r)=>set.add(r.customer_id),new Set()).size,0)+'팀'],rows:rest.flatMap(g=>g.rows),amount:rest.reduce((n,g)=>n+g.amount,0),other:true}];}
    if((level===1||level===2)&&column.length>3){groups=[...new Set(column.map(g=>g.parts[0]))].map(dept=>{const list=column.filter(g=>g.parts[0]===dept),rows=list.flatMap(g=>g.rows),count=new Set(rows.map(r=>level===1?r.product:r.venue)).size;return {id:'compact:'+level+':'+dept,level,parts:[dept,count===1?(level===1?rows[0].product:rows[0].venue):(dept==='F&B'?'식음료':dept==='ROOM'?'객실 부문':dept)+' · '+count+(level===1?'종':'업장')],rows,amount:list.reduce((n,g)=>n+g.amount,0),summary:true};});}
    const chosen=full.rows.find(r=>r.row_id===REV.rollRow&&r.paid_krw>0),same=(a,b)=>level===0?a.customer_id===b.customer_id:level===1?a.department===b.department&&a.venue===b.venue&&a.product===b.product:level===2?a.department===b.department&&a.venue===b.venue:true;
    if(chosen&&level<3)groups=groups.flatMap(g=>{const selected=g.rows.filter(r=>same(r,chosen)),rest=g.rows.filter(r=>!same(r,chosen));if(!selected.length||!rest.length)return [g];const parts=level===0?[chosen.customer_id]:level===1?[chosen.department,chosen.venue,chosen.product]:[chosen.department,chosen.venue];return [{id:'selected:'+level+':'+JSON.stringify(parts),level,parts,rows:selected,amount:selected.reduce((n,r)=>n+r.paid_krw,0)},{...g,parts:[g.parts[0],'그 외 '+new Set(rest.map(r=>level===0?r.customer_id:level===1?r.product:r.venue)).size+(level===0?'팀':level===1?'종':'업장')],other:true,rows:rest,amount:rest.reduce((n,r)=>n+r.paid_krw,0)}];});
    const h=level===4?72:groups.length>3?48:50,used=groups.length*h+(groups.length-1)*8;
    return groups.map((g,i)=>({...g,x:pad+level*step,w:nodeWidth,h,y:42+Math.max(0,(172-used)/2)+i*(h+8)}));
  }),links=[];
  for(let i=0;i<4;i++)for(const a of columns[i])for(const b of columns[i+1]){const ids=new Set(b.rows.map(r=>r.row_id)),rows=a.rows.filter(r=>ids.has(r.row_id));if(rows.length)links.push({a,b,rows,amount:rows.reduce((n,r)=>n+r.paid_krw,0)});}
  for(const c of columns)for(const n of c)for(const [side,other] of [['a','b'],['b','a']]){let offset=0;links.filter(l=>l[side]===n).sort((a,b)=>a[other].y-b[other].y).forEach(l=>{const h=(n.h-12)*l.amount/n.amount;l[side==='a'?'sy':'ty']=n.y+6+offset+h/2;offset+=h;});}
  return {...full,columns,links,width,height:Math.max(220,...columns.flat().map(n=>n.y+n.h+8))};
}
function revActiveRollModel(L) { return REV.flowExpanded?revRollupModel(L):revCompactModel(L); }
function revShortNodeLabel(L,n) {
  if(n.level===0)return n.other?n.parts[n.parts.length-1]:L.receipts[n.parts[0]].display_id;
  if(n.level===4)return '호텔 전체';
  if(n.level===1&&n.rows.every(r=>r.act==='room_night')){const venues=[...new Set(n.rows.map(r=>r.venue))];return venues.length===1?venues[0]+' · 1박':'객실박 · '+venues.length+'업장';}
  const label=n.parts[n.parts.length-1];return label.replace(/ · 2026.*$/,'').replace(/ · 기존 메뉴.*$/,'');
}
function revRollupHTML(L) {
  if(REV.flowExpanded)return revFullRollupHTML(L);
  const m=revCompactModel(L),node=revRollSelection(L,m),row=m.rows.find(r=>r.row_id===REV.rollRow),ids=new Set(row?[row.row_id]:node?node.rows.map(r=>r.row_id):m.rows.map(r=>r.row_id));
  return `<svg class="rev-compact-sankey" style="height:${m.height}px" viewBox="0 0 ${m.width} ${m.height}" role="group" aria-label="고객·상품·업장·부문·호텔 합계 요약 흐름"><title>연결선 본체의 굵기는 결제액 비중입니다. 전체 상품·거래는 확장 보기에서 확인합니다.</title>${['고객별 거래','상품·패키지','업장','부문','호텔 전체'].map((t,i)=>`<g class="rev-compact-stage"><text x="${m.columns[i][0]?m.columns[i][0].x+m.columns[i][0].w/2:m.width*.025+i*(m.width*.95-140)/4+70}" y="14" text-anchor="middle" class="rev-roll-code">${['L5','L4','L3','L2','L1'][i]}</text><text x="${m.columns[i][0]?m.columns[i][0].x+m.columns[i][0].w/2:m.width*.025+i*(m.width*.95-140)/4+70}" y="34" text-anchor="middle" class="rev-roll-heading">${t}</text></g>`).join('')}${revRollLinksHTML(m,ids,!!(row||node),true)}${m.columns.flat().map((n,i)=>{const active=n.rows.some(r=>ids.has(r.row_id)),label=revShortNodeLabel(L,n),lines=label.length>14?[n.level===1?'상품 묶음':'업장 묶음']:label.length>10?[label.split(' · ')[0],label.includes(' · ')?label.split(' · ').slice(1).join(' · '):'']: [label];return `<g class="rev-roll-node${n.level===4?' rev-roll-total':''}${node&&node.id===n.id?' on':''}${(row||node)&&active?' in-path':''}" style="--roll-tone:${revRollColor(n.rows)}" opacity="${active?1:.5}" data-rev-roll="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(label)} ${rcMoney(n.amount)}"><title>${esc(n.parts.join(' · '))} · ${rcMoney(n.amount)}</title>${revRollSurfaceHTML(n,'rev-compact-surface-'+i)}<text x="${n.x+n.w/2}" y="${n.y+n.h/2-10}" text-anchor="middle" class="rev-roll-name">${esc(lines.filter(Boolean).join(' '))}</text><text x="${n.x+n.w/2}" y="${n.y+n.h/2+5}" text-anchor="middle" class="rev-roll-amount">${rcMoney(n.amount)}</text><text x="${n.x+n.w/2}" y="${n.y+n.h/2+22}" text-anchor="middle" class="rev-roll-share">${(100*n.amount/Math.max(1,m.total)).toFixed(1)}%</text></g>`;}).join('')}</svg>`;
}
function revBoardAmount(row) {
  if(row.status==='금액 미확인'||row.amount_status==='UNKNOWN'||row.purchase_status==='UNKNOWN_AMOUNT')return '금액 미확인';
  return row.purchase_status==='FREE_USE'?'무료 이용':row.purchase_status==='PACKAGE_INCLUDED'?'포함 혜택':rcMoney(row.paid_krw);
}
function revTransactionPanelHTML(L) {
  const m=revActiveRollModel(L),node=revRollSelection(L,m),venue=REV.venue&&L.venues.find(v=>JSON.stringify(v.key)===REV.venue),all=(node?node.rows:m.rows).filter(r=>!venue||r.department===venue.department&&r.venue===venue.name),rows=REV.hourFilter?all.filter(r=>(!r.visit_date||r.visit_date===REV.opsDate)&&Number(String(r.time||'').split(':')[0])===REV.opsHour):all,row=m.rows.find(r=>r.row_id===REV.rollRow);
  return `<div class="rev-console-heading"><h3>${row?'선택 거래':'거래 내역'}</h3><button class="cf-link" data-rev-all-transactions>전체 ${revAllRows(L).length}건 ↗</button></div>${REV.hourFilter?`<div class="rev-active-filter">${REV.opsDate} · ${REV.opsHour}시<button class="cf-link" data-rev-hour-clear>해제</button></div>`:''}${row?`<div class="rev-selected-brief"><small>${esc(L.receipts[row.customer_id].display_id)} · ${esc(row.time||'숙박')}</small><b>${esc(row.product)}</b><strong>${revBoardAmount(row)}</strong><div class="rev-trace-actions"><button class="cf-link" data-rev-transaction-action="${esc(row.row_id)}">고객 행동 →</button><button class="cf-link" data-rev-ux-evidence="${esc(row.row_id)}">정밀 근거 →</button><button class="cf-link" data-rev-detail-open>거래 상세 ↗</button><button class="cf-link" data-rev-roll-clear>해제</button></div></div>`:''}<div class="rev-compact-transactions">${rows.slice(0,row?2:5).map(r=>`<button class="rev-board-transaction${row&&row.row_id===r.row_id?' on':''}" data-rev-row="${esc(r.row_id)}"><time>${esc(r.time||'숙박')}</time><span><b>${esc(r.venue)}</b><small>${esc(L.receipts[r.customer_id].display_id)} · ${esc(r.product)}</small></span><strong>${revBoardAmount(r)}</strong></button>`).join('')||'<p class="rc-note">이 시간대의 유료 거래는 없습니다.</p>'}</div>`;
}
function revCompactChoicesHTML(L,decisions) {
  return decisions.map(({pid,a})=>{const plan=REV.flow.plans[pid],si=plan.scenes.findIndex(s=>s.act===a.action&&agHM(s.t0)===a.time&&(s.visit_day||1)===(a.visit_day||1)),reason=si>=0?revReasonFor(L,pid,si):null;return `<article class="rev-board-choice"><time>${esc(a.time||'')}</time><div><button class="cf-link" data-rev-review="${esc(pid)}|${esc(a.action_id)}"><b>${esc(a.label||a.action)}</b></button><small>${esc(L.receipts[pid].display_id)}</small>${reason?agReadableHTML(reason.sentences.join(' '),JSON.stringify([L.run_id,pid,a.action_id,'board-reason']),1):''}</div></article>`;}).join('')||'<p class="rc-note">표시할 선택 기록이 없습니다.</p>';
}
function revOpsBins(L,date) {
  const bins=Array.from({length:24},(_,hour)=>({hour,actions:[],rows:[],paid:0}));
  for(const [pid,r] of Object.entries(L.receipts||{})) {
    for(const a of r.actions||[]) { if(date && a.visit_date && a.visit_date!==date) continue; const h=Number(String(a.time||'').split(':')[0]);if(a.time&&Number.isInteger(h)&&h>=0&&h<24)bins[h].actions.push({pid,a}); }
    for(const row of r.rows||[]) { if(date && row.visit_date && row.visit_date!==date)continue;const h=Number(String(row.time||'').split(':')[0]);if(row.time&&Number.isInteger(h)&&h>=0&&h<24){bins[h].rows.push(row);bins[h].paid+=row.paid_krw||0;} }
  }
  return bins;
}
function revMetricIcon(kind) {
  const paths={total:'M4 7h16v13H4z M4 7l2-3h12l2 3 M15 12h5v4h-5z',room:'M3 17V9h18v11 M3 14h18 M6 9V4h5v5 M13 9V4h5v5',fnb:'M3 3v6c0 4 6 4 6 0V3 M6 3v18 M3 7h6 M21 3c-4 4-4 9 0 9V3v18',leisure:'M12 21V9 M12 15C3 16 3 7 3 3c6 0 9 4 9 12 M12 17c9 0 9-8 9-12-6 0-9 4-9 12'};
  return `<span class="rev-metric-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[kind]||paths.total}"/></svg></span>`;
}
function revSpendChartHTML(bins,hour,size={}) {
  const early=bins.find(b=>b.actions.length||b.paid), start=Math.min(8,early?early.hour:8), visible=bins.slice(start), maxCash=Math.max(1,...visible.map(b=>b.paid)),maxAct=Math.max(2,2*Math.ceil(Math.max(...visible.map(b=>b.actions.length))/2));
  const width=Math.max(570,size.width||960),height=Math.max(130,size.height||130),left=64,right=30,top=12,bottom=height-22,step=(width-left-right)/visible.length,plot=bottom-top;
  const colors={ROOM:'#5c83a6','F&B':'#d8a449','레저':'#49a39a','분류 미확인':'#a0a6ab'};
  const stacks=visible.map((b,i)=>{let y=bottom;const x=left+i*step+step*.2;return [...new Set(b.rows.map(r=>r.department||'분류 미확인'))].map(dep=>{const n=b.rows.filter(r=>(r.department||'분류 미확인')===dep).reduce((n,r)=>n+(r.paid_krw||0),0),h=plot*n/maxCash;y-=h;return `<rect x="${x}" y="${y}" width="${step*.6}" height="${h}" rx="2" fill="${colors[dep]||colors['분류 미확인']}"><title>${b.hour}시 ${esc(dep)} ${rcMoney(n)}</title></rect>`;}).join('');}).join('');
  const points=visible.map((b,i)=>`${left+(i+.5)*step},${bottom-plot*b.actions.length/maxAct}`);
  return `<div class="rev-spend-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="시간별 부문 결제액 막대와 활동 건수 선. 두 축의 단위는 각각 원과 건수입니다.">${[0,.5,1].map(f=>`<line x1="${left}" y1="${bottom-f*plot}" x2="${width-right}" y2="${bottom-f*plot}" stroke="#ece8e1"/><text x="${left-10}" y="${bottom-f*plot+4}" text-anchor="end" class="rev-axis-label">${Math.round(maxCash*f).toLocaleString('ko-KR')}</text><text x="${width-right+8}" y="${bottom-f*plot+4}" class="rev-axis-label">${Math.round(maxAct*f)}</text>`).join('')}${stacks}<polyline points="${points.join(' ')}" fill="none" stroke="#b0a99d" stroke-width="2"/>${visible.map((b,i)=>`<circle cx="${left+(i+.5)*step}" cy="${bottom-plot*b.actions.length/maxAct}" r="${b.hour===hour?5:3}" fill="white" stroke="${b.hour===hour?'#ae3935':'#b0a99d'}" stroke-width="2"/><text x="${left+(i+.5)*step}" y="${height-5}" text-anchor="middle" class="rev-axis-label">${String(b.hour).padStart(2,'0')}</text>`).join('')}</svg><div class="rev-chart-hitareas" style="left:${100*left/width}%;right:${100*right/width}%;grid-template-columns:repeat(${visible.length},1fr)">${visible.map(b=>`<button class="${b.hour===hour?'on':''}" data-rev-hour="${b.hour}" aria-pressed="${b.hour===hour}" aria-label="${b.hour}시 활동 ${b.actions.length}건, 가상 결제 ${b.paid}원"><span>${b.hour}시 · ${b.actions.length}건 · ${rcMoney(b.paid)}</span></button>`).join('')}</div></div>`;
}
function revDecisionReviewHTML(L,decisions) {
  return decisions.length?decisions.map(({pid,a},i)=>{
    const plan=REV.flow && REV.flow.plans && REV.flow.plans[pid],scene=plan && plan.scenes.find(s=>s.act===a.action && agHM(s.t0)===a.time && (s.visit_day||1)===(a.visit_day||1));
    const reason=scene?revReasonFor(L,pid,plan.scenes.indexOf(scene)):null;
    return `<article class="rev-review-row"><span class="rev-review-time">${esc(a.time||'')}</span><i class="rev-review-dot" aria-hidden="true"></i><div><small>${esc(L.receipts[pid].display_id)} · ${esc(a.visit_date||'')}</small><h4>${esc(a.label||a.action)}</h4>${reason?`<p class="rev-review-factor">${reason.sentences.map(esc).join(' ')}</p>`:''}<p>${(a.considered||[]).length?'비교 대안 · '+esc(a.considered.slice(0,2).map(x=>x.label).join(' / ')):'제외 조건 '+(a.blocked||[]).length+'건 확인'}</p><button class="cf-link" data-rev-review="${esc(pid)}|${esc(a.action_id)}">선택 이유와 후기 근거 →</button></div></article>`;
  }).join(''):'<p class="rc-note">비교 가능한 행동 기록이 없습니다.</p>';
}
function revRoomSummary(roomRows,inRoomRows){
 const unknown=r=>r.status==='금액 미확인'||r.purchase_status==='UNKNOWN_AMOUNT'||r.paid_krw==null;
 const amount=rows=>rows.reduce((n,r)=>n+(r.paid_krw||0),0);
 const part=(label,rows)=>{const n=rows.filter(unknown).length;return n===rows.length?label+' 금액 미확인':label+' '+rcMoney(amount(rows))+(n?' · '+n+'건 미확인':'');};
 const parts=[];
 if(roomRows.length)parts.push(part(inRoomRows.length?'객실':`객실 ${roomRows.length}박 ·`,roomRows));
 if(inRoomRows.length)parts.push(part('룸서비스',inRoomRows));
 return parts.join(' · ')||'객실·룸서비스 거래 없음';
}
// Operator aggregate of the run (operating_reference.aggregate): breakfast covers, dinner where-eaten (external delivery,
// room service, hotel restaurants), composition weights and the reference used. References are labelled by source class
// and never change an agent's choice; weighted values are estimates for the stated guest mix, not ledger totals.
const REV_REFERENCE=[['external','외부 연구 (공개 자료)'],['synthetic_delivery_high_v1','합성 A · 배달 많은 가상 호텔'],['synthetic_hotel_format_b_v1','합성 B · 호텔 실측 형식 시험'],['hotel','호텔 실측 파일 (서버 설정)']];
const REV_OPS_STATUS={WITHIN_REFERENCE:'기준 범위 안',BELOW_REFERENCE:'기준보다 낮음 · 보정 검토',ABOVE_REFERENCE:'기준보다 높음 · 보정 검토',SAMPLE_TOO_SMALL:'표본이 작아 비교하지 않음',NO_REFERENCE:'기준값 없음(실측 입력 대기)',NOT_COMPARABLE:'지표 단위가 달라 비교하지 않음',CONTEXT_ONLY:'참고 정보',NOT_IN_RUN:'이 실행에 해당 없음'};
const REV_VENUE_KO={PIZZA_HILL:'피자힐',GEUMRYONG:'금룡',MOEGI:'모에기',MYONGWOLGWAN:'명월관',ONDAL:'온달',THE_PAVILION:'더 파빌리온',THE_BUFFET:'더뷔페',ROOM_MEAL:'룸서비스',IRD:'룸서비스',DELVINO:'델비노',LE_PASSAGE:'르 파사쥬'};
const REV_DINNER={EXTERNAL_DELIVERY:'외부 배달',HOTEL_RESTAURANT:'호텔 레스토랑',ROOM_SERVICE:'룸서비스',OUTSIDE_OR_OTHER:'기타',NO_DINNER_RECORDED:'저녁 기록 없음'};
const REV_PRIOR_STATUS={APPLICABLE:'적용 가능',NO_COMPARABLE_STATISTIC:'비교 가능한 통계 없음 · 적용 안 함',RANGE_WITHOUT_POINT_VALUE_NOT_APPLIED:'범위값만 있어 적용 안 함'};
function revOpsVal(c,v){return v==null?'—':c.value_kind==='krw'?rcMoney(v):c.value_kind==='rate'?String(v):Math.round(v*100)+'%';}
function revPopulationHTML(o){
  const p=o.population;if(!p)return '';const w=p.weights||{},e=p.estimates||{},m=e.metrics||{};
  const pct=v=>v==null?'—':Math.round(v*100)+'%',row=(k,t,money)=>m[k]?`<tr><td>${t}</td><td>${money?rcMoney(Math.round(m[k].raw)):pct(m[k].raw)}</td><td>${m[k].weighted==null?'—':money?rcMoney(Math.round(m[k].weighted)):pct(m[k].weighted)}</td></tr>`:'';
  const head=w.status&&w.status.startsWith('OK')?`구성 가중치 · ${esc((w.source_ko||[]).join(', '))} · 유효표본 ${w.effective_sample_size} / ${w.teams_weighted}팀 · 최대 가중치 ${w.max_weight}${w.capped?' (상한 적용)':''}${w.unsupported_segments&&w.unsupported_segments.length?` · 표본 없는 구간 ${esc(w.unsupported_segments.join(', '))}(${pct(w.target_share_not_represented)} 미반영)`:''}${w.status==='OK_LOW_EFFECTIVE_SAMPLE'?' · 유효표본이 작아 참고만':''}`:`구성 가중치 없음 · ${esc(w.reason||'')}`;
  return `<details class="rev-ops-pop" data-rev-population><summary>집단 구성 보정 (가중 추정 · 원장 합계 아님)</summary><p class="rc-note">${head}</p>
  <table class="rev-ops-table rev-ops-cmp"><thead><tr><th>지표</th><th>실행한 팀 그대로</th><th>기준 구성 가중</th></tr></thead><tbody>
  ${row('delivery.evening_share','숙박 팀·저녁 중 외부 배달')}${row('dinner.restaurant_share','숙박 팀·저녁 중 호텔 레스토랑')}${row('dinner.room_service_share','숙박 팀·저녁 중 룸서비스')}${row('fnb.dinner_revenue_per_stay_team','숙박 팀당 내부 저녁 가상 매출',true)}</tbody></table>
  <p class="rc-note">가중치는 고객 구성(일행 인원)만 맞춥니다. 배달 비율은 가중의 목표가 아니라 결과로 비교합니다. 개인 행동은 바뀌지 않습니다.</p></details>`;
}
function revGroupABHTML(){
  const g=REV.groupAB,run=REV.latest&&REV.latest.request;
  const can=run&&['stay_1','stay_2'].includes(run.duration);
  const form=`<div class="rev-group-form"><label>피자힐 매장 메인 할인<select class="cf-input" id="revGroupPct">${[10,20,30].map(v=>`<option value="${v}"${REV.groupPct===v?' selected':''}>${v}%</option>`).join('')}</select></label><button type="button" class="cf-btn" data-rev-group-ab${!can||REV.groupBusy?' disabled':''}>${REV.groupBusy?'집단 A/B 실행 중...':'같은 집단으로 A/B 실행'}</button><small>${can?`A: 현재 실행 조건(${esc((REV_REFERENCE.find(r=>r[0]===(run.reference_profile||'external'))||[0,run.reference_profile])[1])} · 행동 사전정보 ${run.behaviour_prior&&run.behaviour_prior!=='OFF'?'켜짐(연구)':'꺼짐'}) · B: A + 피자힐 할인 · 같은 고객·일정·시드`:'숙박(1박·2박) 실행 뒤에 사용할 수 있습니다'}</small></div>`;
  if(REV.groupErr)return form+`<p role="alert">${esc(REV.groupErr)}</p>`;
  if(!g)return form;
  if(g.status!=='DONE'||g.ab.status!=='COMPARABLE_SIMULATION_PAIR')return form+`<p role="alert">비교할 수 없는 실행입니다 · ${esc((g.ab&&g.ab.reasons||[]).join(', ')||g.status)}</p>`;
  const ab=g.ab,k=ab.dinner_kinds,name=id=>typeof dno==='function'?dno(id):id;
  const kinds=Object.keys(REV_DINNER).filter(x=>(k.A[x]||0)+(k.B[x]||0)>0).map(x=>`<tr><td>${REV_DINNER[x]}</td><td>${k.A[x]||0}</td><td>${k.B[x]||0}</td></tr>`).join('');
  const mv=ab.delivery_to_hotel.map(r=>`<li data-group-mover="${esc(r.customer_id)}"><b>${esc(name(r.customer_id))}</b> ${esc(r.date)} · 외부 배달 → ${esc(r.after_label||r.after_venue)} ${rcMoney(r.after_paid_krw)} <small>선택 점수 ${r.after_choice_score??'—'} &gt; 배달 ${r.delivery_score_after??'—'} · 사전정보 ${r.prior_applied?'적용':'미적용'}</small></li>`).join('')||'<li>이동한 고객 없음</li>';
  const st=ab.stayed_with_delivery.map(r=>`<li><b>${esc(name(r.customer_id))}</b> ${esc(r.date)} · 배달 유지 <small>남은 점수 차 ${r.remaining_gap??'—'} · 가장 높은 호텔 저녁 ${esc(r.best_hotel_option||'—')}</small></li>`).join('');
  const other=ab.other_moves.map(r=>`<li><b>${esc(name(r.customer_id))}</b> ${esc(r.change)} · ${esc(r.before_label||'')} → ${esc(r.after_label||'')}</li>`).join('');
  const ven=ab.venue_dinner_revenue.filter(v=>v.A||v.B).map(v=>`<tr><td>${esc(REV_VENUE_KO[v.venue]||v.venue)}</td><td>${rcMoney(v.A)}</td><td>${rcMoney(v.B)}</td><td>${v.delta>0?'+':''}${rcMoney(v.delta)}</td></tr>`).join('');
  return form+`<div data-rev-group-result><p>${g.spec.personas.length}팀 · ${esc(g.spec.duration)} · 피자힐 메인 ${g.lever.percent}% 할인 (${g.lever.sku_count}개 상품)</p>
  <table class="rev-ops-table rev-ops-cmp"><thead><tr><th>저녁 해결 방식(팀·저녁)</th><th>A</th><th>B</th></tr></thead><tbody>${kinds}</tbody></table>
  <h4>외부 배달 → 호텔 업장 이동 ${ab.delivery_to_hotel.length}건</h4><ul class="rev-group-list">${mv}</ul>
  ${st?`<h4>배달을 유지한 고객</h4><ul class="rev-group-list">${st}</ul>`:''}${other?`<h4>그 밖의 선택 변화</h4><ul class="rev-group-list">${other}</ul>`:''}
  <table class="rev-ops-table rev-ops-cmp"><thead><tr><th>업장 저녁 가상 매출</th><th>A</th><th>B</th><th>차이</th></tr></thead><tbody>${ven}</tbody></table>
  ${ab.revenue_decomposition?`<table class="rev-ops-table rev-ops-kv" data-rev-group-decomposition><tbody>
  <tr><th>배달에서 옮겨 온 고객의 새 주문</th><td>${rcMoney(ab.revenue_decomposition.new_spend_from_delivery_movers)}</td></tr>
  <tr><th>기존 고객의 같은 주문 할인 효과</th><td>${rcMoney(ab.revenue_decomposition.same_venue_same_order_price_effect)}</td></tr>
  <tr><th>같은 업장 주문 변경</th><td>${rcMoney(ab.revenue_decomposition.same_venue_order_changed)}</td></tr>
  <tr><th>다른 업장으로 이동</th><td>${rcMoney(ab.revenue_decomposition.venue_switch)}</td></tr>
  <tr><th>호텔 → 배달 이탈</th><td>${rcMoney(ab.revenue_decomposition.lost_to_delivery)}</td></tr>
  <tr><th>저녁 이후 다른 원장 행 변화</th><td>${rcMoney(ab.revenue_decomposition.other_rows_after_dinner_change)}</td></tr>
  <tr><th>호텔 전체 순변화</th><td><b>${rcMoney(ab.revenue_decomposition.hotel_total)}</b></td></tr></tbody></table>`:''}
  <p>호텔 전체 가상 매출(원장) ${rcMoney(ab.hotel_total_krw.A)} → ${rcMoney(ab.hotel_total_krw.B)} (${ab.hotel_total_krw.delta>0?'+':''}${rcMoney(ab.hotel_total_krw.delta)}) · 외부 배달 ${ab.external_delivery.A} → ${ab.external_delivery.B}건(금액 미상 · 호텔 매출 아님)</p>
  <p class="rc-note">${esc(g.limits.join(' · '))}</p></div>`;
}
async function revGroupAB(){
  const run=REV.latest&&REV.latest.request;if(!run)return;
  REV.groupBusy=true;REV.groupErr=null;REV.groupAB=null;revRender();
  try{
    const job=await api('/api/population/experiment',{personas:Object.keys(REV.latest.flow.plans),duration:run.duration,reference_profile:run.reference_profile||'external',behaviour_prior:run.behaviour_prior||'OFF',pizza_hill_discount_percent:REV.groupPct,seed:Number.isInteger(run.seed)?run.seed:0,start_date:run.start_date||'2026-10-24'});
    let row=job;for(let i=0;i<240&&!['DONE','ERROR','CANCELLED'].includes(row.status);i++){await new Promise(r=>setTimeout(r,2500));row=await api('/api/agent/jobs?id='+encodeURIComponent(job.job_id));}
    if(row.status!=='DONE')throw new Error('집단 A/B를 완료하지 못했습니다 ('+row.status+')');
    REV.groupAB=row.result;
  }catch(e){REV.groupErr=e.message||String(e);}
  REV.groupBusy=false;revRender();
}
function revOperatingHTML(o){
  if(!o||!o.breakfast)return '';
  const b=o.breakfast,pct=v=>v==null?'—':Math.round(v*100)+'%',ref=r=>!r?'—':`${r.low!=null?pct(r.low)+'~'+pct(r.high):r.value==null?'수치 없음':pct(r.value)} · ${esc(r.source_ko)}${r.synthetic_label?' · '+esc(r.synthetic_label):''}`;
  const reasons=Object.entries(b.skip_reasons||{}).map(([k,n])=>`${esc(k)} ${n}`).join(' · ')||'없음';
  const rows=(o.comparison||[]).filter(c=>c.simulated!=null||c.reference);
  const d=o.dinner||{by_kind:{}},kinds=Object.keys(REV_DINNER).filter(x=>d.by_kind[x]).map(x=>`${REV_DINNER[x]} ${d.by_kind[x]}`).join(' · ')||'숙박 저녁 없음';
  const notes=(o.sample_notes||[]).map(n=>`<li>${esc(n.split(': ').slice(1).join(': ')||n)}</li>`).join('');
  const refSets=((o.reference||{}).files||[]).map(f=>esc(f.source_set||f.name)).join(' + ')||'기준 데이터 없음';
  return `<section class="rev-console-panel rev-board-ops" data-rev-operating><div class="rev-console-heading"><h3>운영 집계 · 조식 식수와 시설 이용</h3><small>시뮬레이션 집계 · 실측 아님</small></div>
  <p>참여 ${o.teams}팀 · ${o.persons}명 · 숙박 아침 ${o.team_mornings}팀·아침 · 숙박 저녁 ${d.evenings||0}팀·저녁 · 기준 데이터 ${refSets}</p>
  ${notes?`<ul class="rev-ops-notes" data-rev-sample-notes>${notes}</ul>`:''}
  <table class="rev-ops-table rev-ops-kv"><tbody><tr><th>조식 포함 권리</th><td>${b.entitled}명·아침${b.entitlement_unknown_mornings?` (권리 미확인 ${b.entitlement_unknown_mornings}팀·아침)`:''}</td></tr>
  <tr><th>실제 조식 이용</th><td>${b.diners}명·아침 = 포함 혜택 ${b.included_used} + 추가 결제 ${b.paid_diners}${b.diners_split_unknown?` + 구분 미확인 ${b.diners_split_unknown}`:''}</td></tr>
  <tr><th>포함 혜택 미사용</th><td>${b.unused_entitlement}명·아침</td></tr>
  <tr><th>조식 추가 결제 매출</th><td>${rcMoney(b.paid_revenue_krw)} <small>포함 혜택은 객실 패키지에 포함 · 별도 매출로 더하지 않음</small></td></tr>
  <tr><th>조식을 먹지 않은 아침</th><td>${b.skipped_team_mornings}팀·아침 · 사유 ${reasons}</td></tr>
  <tr><th>저녁 해결 방식</th><td data-rev-dinner-kinds>${kinds} <small>외부 배달은 금액 미상 · 호텔 매출 아님</small></td></tr>
  <tr><th>호텔 내부 저녁 가상 매출</th><td>${rcMoney(d.in_hotel_dinner_revenue_krw||0)}</td></tr></tbody></table>
  ${revPopulationHTML(o)}
  <details><summary>기준값과 비교 (${rows.length}개 지표)</summary><table class="rev-ops-table rev-ops-cmp"><thead><tr><th>지표</th><th>이 실행</th><th>기준값</th><th>상태</th></tr></thead><tbody>${rows.map(c=>`<tr data-ops-metric="${esc(c.metric_id)}"><td>${esc(c.name_ko)}</td><td>${revOpsVal(c,c.simulated)}</td><td>${ref(c.reference)}${c.reference?.url?` <a href="${esc(c.reference.url)}" target="_blank" rel="noopener">출처</a>`:''}</td><td>${esc(REV_OPS_STATUS[c.status]||c.status)}</td></tr>`).join('')}</tbody></table>
  <p class="rc-note">외부 연구 값은 다른 호텔·설문 자료로 워커힐 실측이 아닙니다. 합성 값은 개발 검증용 가상 호텔입니다. 호텔 실측값을 넣으면 같은 지표에서 자동으로 우선합니다. 기준값은 집계 비교와 보정 검토에만 쓰며, 행동 사전정보를 켠 연구 실행에서만 개인 근거가 없는 고객의 배달 후보 점수에 기록과 함께 반영됩니다.</p></details>
  <details class="rev-ops-group" data-rev-group${REV.groupAB||REV.groupBusy?' open':''}><summary>집단 운영 실험 · 외부 배달 → 호텔 F&amp;B (연구 · 규칙 엔진)</summary>${revGroupABHTML()}</details></section>`;
}
function revControlHTML(L) {
  const dates=L.visit?L.visit.days.map(d=>d.date):[L.context.start_date].filter(Boolean);
  const date=dates.includes(REV.opsDate)?REV.opsDate:dates[0], bins=revOpsBins(L,date);
  const hour=Number.isInteger(REV.opsHour)?REV.opsHour:bins.reduce((best,b)=>b.paid>best.paid?b:best,bins.find(b=>b.actions.some(x=>(x.a.considered||[]).length))||bins[0]).hour, selected=bins[hour];
  const dept=k=>L.levels.L2.find(g=>g.key[0]===k), money=k=>dept(k)?rcMoney(dept(k).paid_krw):'거래 없음';
  const roomRows=Object.values(L.receipts).flatMap(r=>r.rows).filter(r=>(r.act||r.action_id)==='room_night');
  const connected=roomRows.length&&roomRows.every(r=>r.purchase_status==='SIMULATED_CHARGE');
  const roomUnknown=roomRows.filter(r=>r.status==='금액 미확인'||r.purchase_status==='UNKNOWN_AMOUNT').length;
  const inRoomRows=Object.values(L.receipts).flatMap(r=>r.rows).filter(r=>r.department==='ROOM'&&!['room_night','room_addon'].includes(r.act||r.action_id));
  const inRoomAmount=inRoomRows.reduce((n,r)=>n+(r.paid_krw||0),0), fnbWithIrd=(dept('F&B')?dept('F&B').paid_krw:0)+inRoomAmount;
  const roomKind=r=>String(r.price_status||'').startsWith('SANTA_PACKAGE')?'산타 패키지':'일반 객실';
  // Package admission is an entitlement: a package customer without an executed Santa admission row holds it unused (not an extra fee).
  const santaPkgPids=[...new Set(Object.entries(L.receipts).filter(([,r])=>r.rows.some(x=>(x.act||x.action_id)==='room_night'&&String(x.price_status||'').startsWith('SANTA_PACKAGE'))).map(([p])=>p))];
  const santaUnused=santaPkgPids.filter(p=>!L.receipts[p].rows.some(x=>String(x.act||x.action_id||'').startsWith('CARD_SANTA'))).length;
  const roomByKind=Object.entries(roomRows.reduce((m,r)=>{if(r.status!=='금액 미확인'){m[roomKind(r)]=(m[roomKind(r)]||0)+(r.paid_krw||0);}return m;},{}));
  const roomAmount=roomRows.reduce((n,r)=>n+(r.paid_krw||0),0), roomSources=[...new Set(roomRows.map(r=>String(r.price_status||'').startsWith('SANTA_PACKAGE')?'산타 패키지 가상 기준가(조식·입장 포함)':r.price_evidence_status==='SCENARIO_ASSUMPTION'?'가상 모델 참고':r.price_status==='VIRTUAL_MODEL_UNIT_PRICE'?'가상 객실 모델 단가':r.price_status==='VERIFIED_PACKAGE_TOTAL_ALLOCATION'?'확인된 패키지 총액':r.price_status==='VERIFIED_ROOM_NIGHTLY'?'확인된 객실 단가':r.price_status==='OPERATOR_VIRTUAL_ROOM_RATE_INPUT'?'운영자 입력 가상 객실료':r.price_status==='HISTORICAL_STARTING_RATE_SIMULATION'?'가상 객실 모델 단가':'가격 미확인'))].join(' · ');
  const decisions=Object.entries(L.receipts).flatMap(([pid,r])=>(r.actions||[]).filter(a=>(a.considered||[]).length||(a.blocked||[]).length).map(a=>({pid,a}))).filter(x=>!['arrive','checkin','checkout','leave','idle','wait'].includes(x.a.action)).filter(x=>!date||!x.a.visit_date||x.a.visit_date===date).filter((x,i,list)=>L.team_count===1||list.findIndex(y=>y.pid===x.pid)===i).slice(0,3);
  const headerInfo=typeof noteH==='function'?noteH({title:'실행 원장',what:`run_id ${L.run_id}`,meta:`엔진 ${L.context.engine_version||'미기록'} · ${rcSource(L)}`} ,'flow'):'';
  const share=k=>dept(k)&&L.totals.paid_krw?`${(100*dept(k).paid_krw/L.totals.paid_krw).toFixed(1)}% · 전체 가상 소비 중`:'금액이 확인된 거래 없음';
  const names=Object.values(L.receipts).slice(0,3).map(r=>r.display_id).join(' · ')+(L.team_count>3?` 외 ${L.team_count-3}팀`:'');
  const mode=REV.flow&&REV.flow.engine&&REV.flow.engine.simulation_mode==='shared_world'?'공동 시간축 실행':'개별 방문 실행';
  return `<section class="rev-root rev-command rev-harmonized rev-compact${REV.animateEntry?' rev-entry':''}"><header class="rev-command-head"><div class="rev-heading-main"><h2>매출 집계</h2><div class="rev-command-tools"><button class="cf-btn" data-rev-recent>최근 실행</button><button class="cf-btn" data-rev-new>새 계산</button></div></div><div class="rev-run-summary"><span>${esc(names)} · ${esc(({day_visit:'당일 방문',stay_1:'1박 2일',stay_2:'2박 3일',stay_3:'3박 4일'})[L.context.duration]||L.context.duration||'하루')} · ${esc(dates[0]||'날짜 미기록')}${dates.length>1?' ~ '+esc(dates[dates.length-1]):''} · ${Object.values(L.receipts).every(r=>Number.isInteger(r.party_size))?Object.values(L.receipts).reduce((n,r)=>n+r.party_size,0)+'명':'인원 미확인'} · ${esc(L.context.event_label?(L.context.scenario_enabled?L.context.event_label:L.context.event_label+' · 미개최'):L.context.event?'와인페어':'행사 없음')}</span><details class="rev-run-details"><summary>실행 조건 보기</summary><div class="rev-context-chips"><span>${typeof hlReasonResearchRun==='function'&&hlReasonResearchRun({result:REV.flow,ledger:L})?'연구 저장 실행':'모델 가상 집계'} · 전체 방문 ${L.team_count}팀 · 설정 ${Object.values(L.receipts).every(r=>Number.isInteger(r.party_size))?Object.values(L.receipts).reduce((n,r)=>n+r.party_size,0)+'명':'인원 미확인'}</span><span>${esc(names)}</span><span>${esc(dates[0]||'날짜 미기록')}${dates.length>1?' → '+esc(dates[dates.length-1]):''}</span><span>${esc(({day_visit:'당일 방문',stay_1:'1박 2일',stay_2:'2박 3일',stay_3:'3박 4일'})[L.context.duration]||L.context.duration||'하루')}</span><span>${esc(L.context.event_label?(L.context.scenario_enabled?L.context.event_label:L.context.event_label+' · 미개최'):L.context.event?'와인페어':'행사 없음')}</span><span>${mode} ${headerInfo}</span></div><button class="cf-link" data-rev-new>설정 화면 열기 →</button></details></div></header>
  <div class="rev-command-kpis"><article class="kpi-total">${revMetricIcon('total')}<div><small>전체 가상 소비 · L5 합계</small><strong>${rcMoney(L.totals.paid_krw)}</strong><span>${L.price_class_aggregates?`추정·가정 ${rcMoney(L.price_class_aggregates.estimated_or_assumed_krw)}`:`미확인 ${L.totals.unknown_count||0}건 제외`}</span>${roomUnknown?`<em class="kpi-exclusion" data-room-unpriced="${roomUnknown}">객실료 ${roomUnknown}박 미포함</em>`:''}</div></article><article class="kpi-fnb">${revMetricIcon('fnb')}<div><small>F&B · 식음료</small><strong>${money('F&B')}</strong><span>${share('F&B')}</span>${inRoomAmount?`<span class="kpi-aux" data-fnb-with-ird="${fnbWithIrd}" title="F&B(업장 식음)와 ROOM 부문의 룸서비스를 더한 보조 지표입니다. 합계에는 한 번만 들어갑니다.">룸서비스 포함 ${rcMoney(fnbWithIrd)}</span>`:''}</div></article><article class="kpi-leisure">${revMetricIcon('leisure')}<div><small>레저 · 유료 시설</small><strong>${money('레저')}</strong><span>${share('레저')}</span></div></article><article class="kpi-room">${revMetricIcon('room')}<div><small>ROOM · 객실 부문</small><strong class="${dept('ROOM')?'':'kpi-state'}">${dept('ROOM')?money('ROOM'):roomRows.length?'금액 미확인':'거래 없음'}</strong><span data-room-split title="${esc(roomSources+' · '+revRoomSummary(roomRows,inRoomRows))}">${esc(revRoomSummary(roomRows,inRoomRows))}</span>${santaPkgPids.length?`<em class="kpi-exclusion" data-santa-unused="${santaUnused}" title="산타 패키지 포함 입장 혜택 · 미사용이어도 추가 요금·환불 없음(가상)">${santaUnused?`입장 혜택 보유·미사용 ${santaUnused}팀`:'패키지 입장 사용'}</em>`:''}</div></article></div>

  <div class="rev-board-middle"><section class="rev-console-panel rev-board-flow"><div class="rev-console-heading"><h3>업장별 소비 비교</h3><button class="cf-link" data-rev-expand="venues">전체 보기 ↗</button></div>${revVenueAmountChart(L)}</section><section class="rev-console-panel rev-board-choices">${revOperatorSummaryHTML(L)}</section></div>
  <div class="rev-board-bottom"><section class="rev-console-panel rev-board-time"><div class="rev-console-heading"><div class="rev-roll-tabs" aria-label="분석 보기"><button class="cf-link" data-rev-analysis-view="flow" aria-pressed="${REV.analysisView!=='time'}">L5 → L1 집계 흐름</button><button class="cf-link" data-rev-analysis-view="time" aria-pressed="${REV.analysisView==='time'}">시간대별 활동·소비</button></div>${REV.analysisView!=='time'?'<button class="cf-link" data-rev-expand="flow">확장 보기 ↗</button>':''}</div>${REV.analysisView==='time'?`<div class="rev-console-heading"><select id="revOpsDate" aria-label="활동 일자">${dates.map(d=>`<option${d===date?' selected':''}>${d}</option>`).join('')}</select></div><div class="rev-time-legend"><span>● ROOM</span><span>● F&B</span><span>● 레저</span><small>막대 원 · 선 활동 건수</small></div>${revSpendChartHTML(bins,hour)}<div class="rev-hour-context">${hour}시 · 활동 ${selected.actions.length}건 · 유료 ${rcMoney(selected.paid)}${REV.hourFilter?' · 오른쪽 거래 필터 적용':''}</div>` : revRollupHTML(L)}</section><aside class="rev-console-panel rev-board-ledger">${revTransactionPanelHTML(L)}</aside></div>
  ${revOperatingHTML(typeof REV!=='undefined'&&REV.flow?(REV.flow.operating_summary||REV.flow.result?.operating_summary):null)}
  <footer class="rev-board-footer"><span>고객 행동 시뮬레이션에 따른 가상 매출이며, 실제 매출 예측값은 아닙니다. ${L.totals.net_revenue_krw==null?'결제액 기준 · 순매출 미산정':''}</span><button class="cf-link" data-rev-all-transactions>상세 원장·가격 근거 ↗</button></footer>${revBoardOverlayHTML(L)}${REV.setupOpen?`<div class="rev-overlay" role="dialog" aria-modal="true" aria-label="새 계산 설정">${revSetupPanelHTML()}</div>`:''}</section>`;
}
function revBoardOverlayHTML(L) {
  if(!REV.flowExpanded&&!REV.detailPanel)return '';
  return `<div class="rev-overlay" role="dialog" aria-modal="true" aria-label="집계 상세"><section class="rev-expanded-panel"><div class="rev-console-heading">${REV.flowExpanded?revRollTabsHTML():'<h3>거래·행동·가격 근거</h3>'}<button class="cf-btn" data-rev-overlay-close>닫기 ×</button></div>${REV.flowExpanded?(REV.rollView==='venues'?`<div class="rev-expanded-venues">${revVenueAmountChart(L)}${revDrill(L)}</div>`:revFullRollupHTML(L)):''}${REV.detailPanel==='transactions'?revTransactionsTableHTML(L):REV.detailPanel==='venue'?revDrill(L):revRollDrillHTML(L)}</section></div>`;
}
function revHTML() { return REV.ledger ? revControlHTML(REV.ledger) : revConfigHTML(); }
function revUXSelectionHTML(L) {
  const model=revRollupModel(L),node=revRollSelection(L,model),row=model.rows.find(r=>r.row_id===REV.rollRow);
  if(!node&&!row)return '';
  const label=row?`${L.receipts[row.customer_id].display_id} · ${row.product}`:node.level===0&&!node.other?L.receipts[node.parts[0]].display_id:node.parts[node.parts.length-1];
  return `<section class="ux-revenue-selection" aria-live="polite"><div><small>선택한 거래 맥락 · 같은 실행</small>${agReadableHTML(label,JSON.stringify([L.run_id,row?row.row_id:node.id,'selection']),2)}<span>${row?`${esc(row.visit_date||'')} ${esc(row.time||'숙박')} · ${esc(row.venue)} · ${rcMoney(row.paid_krw)}`:`거래 ${node.rows.length}건 · ${rcMoney(node.amount)}`}</span></div><button class="cf-link" data-rev-roll-clear>선택 해제</button>${row?`<div><button class="cf-link" data-rev-transaction-action="${esc(row.row_id)}">고객 행동 보기 →</button>${row.act!=='room_night'?`<button class="cf-link" data-rev-ux-evidence="${esc(row.row_id)}">정밀 판단 근거 →</button>`:''}</div>`:'<small>아래 거래에서 한 건을 선택하면 고객 행동까지 연결합니다.</small>'}</section>`;
}
async function revUXOpenEvidence(rowId) {
  if(typeof window!=="undefined"&&window.HLNav?.active())return HLNav.fromTransaction(rowId);
  const L=REV.ledger,row=Object.values(L.receipts).flatMap(r=>r.rows).find(r=>r.row_id===rowId);if(!row)return;
  // A ledger lookup must not overwrite a paused flow snapshot with a freshly
  // initialized clock. Reuse the immutable run and validate the exact transaction.
  if(typeof bhRecall==='function'){
    const saved=await bhRecall(L.run_id),plan=saved?.flow?.result?.plans?.[row.customer_id];
    const index=plan?.scenes.findIndex(s=>(s.visit_day||1)===(row.visit_day||1)&&s.act===row.act&&agHM(s.t0)===row.time&&(!row.selection_id||!s.basis?.selection_id||row.selection_id===s.basis.selection_id));
    if(index>=0){const c=bhContextFor(saved,row.customer_id,index,{ledger_tx_id:row.row_id,returnTo:'revenue'});if(c&&c.ledger_tx_id===row.row_id)return bhActivate(saved,c);}
  }
  await revShowCustomer(row.customer_id);if(L.visit)agVisitDaySelect(row.visit_day||1);
  const scenes=agScenes(row.customer_id);
  const scene=scenes.find(s=>s.k!=='move'&&(s.visit_day||1)===(row.visit_day||1)&&s.act===row.act&&agHM(s.t0)===row.time&&(!row.selection_id||!s.basis?.selection_id||row.selection_id===s.basis.selection_id));
  if(scene&&typeof bhFromScene==='function'){agSetScene(scene.si,0);agPause();return bhFromScene(row.customer_id,scene.si,{ledger_tx_id:row.row_id,returnTo:'revenue'});}
}
// Daily behavior revenue and the existing product-condition experiment share a page,
// but keep their requests, ledgers and totals independent.
const REV = { ids: [], allIds: [], selected: new Set(), scope: "selected", latest: null, pendingDemo: null, enteredLatest: null, completedKey: null,
  duration: "day_visit", scenario: "none", search: "", pickerOpen: false, flow: null, baseline: null, ledger: null,
  comparison: null, abPair: null, busy: false, err: null, department: null, venue: null, product: null, customer: null,
  amountBars: false, token: 0, filterToken: 0, completedScenario: null,
  referenceProfile: "external", prior: "OFF", groupAB: null, groupBusy: false, groupErr: null, groupPct: 20 };
const REV_SCENARIOS = { none: "행사 없음", wine: "와인페어 있음", wine_fair_1300: "와인페어 13시 시작", pizzahill_full: "피자힐 이용 조건 변경", pool_check: "수영장 점검" };
function revRunContextHTML(L) {
  if (!L) return "";
  const c=L.context||{}, ids=Object.keys(L.receipts||{}), dates=L.visit&&L.visit.days||[];
  const span=dates.length ? `${dates[0].date} – ${dates[dates.length-1].date}` : c.start_date||"날짜 미확인";
  const duration={day_visit:"당일",stay_1:"1박 2일",stay_2:"2박 3일",stay_3:"3박 4일"}[c.duration]||c.duration||"기간 미확인";
  const event=c.event?"와인페어":"행사 없음", engine=c.engine_version||REV.flow&&REV.flow.engine&&REV.flow.engine.version||"미기록";
  const detail=typeof noteH==="function"?noteH({title:"현재 실행 정보",what:`run_id ${L.run_id}`,meta:`엔진 ${engine} · ${rcSource(L)}`,caution:"같은 방문의 행동과 L5 원장을 재계산 없이 이어봅니다."},"flow"):"";
  return `<section class="rev-run-context rev-context-line"><b>가상 실행 · ${ids.map(id=>esc(L.receipts[id].display_id||dno(id))).join(" · ")}</b><span>${esc(span)} · ${esc(duration)} · ${esc(event)} · ${esc(REV.flow&&REV.flow.engine&&REV.flow.engine.behavior_engine==="m4"?"M4 방문 실행":"기록된 방문 실행")}${L.external_spend&&L.external_spend.count?` · 외부 배달 ${L.external_spend.count}건(호텔 매출 제외 · 금액 미상)`:""}</span>${detail}</section>`;
}
function revActivityHTML(L) {
  if (!L || L.operations && L.operations.ledger_run_id===L.run_id) return "";
  const buckets=new Map();
  for (const [pid,r] of Object.entries(L.receipts||{})) {
    for (const a of r.actions||[]) {
      const date=a.visit_date||L.visit&&L.visit.days.find(d=>d.day_index===a.visit_day)?.date||L.context&&L.context.start_date||"일자 미상";
      const hour=a.time?`${String(a.time).slice(0,2)}시`:"시각 미상", key=`${date}|${hour}`;
      if(!buckets.has(key)) buckets.set(key,{date,hour,actions:[]});
      buckets.get(key).actions.push({pid,r,a});
    }
  }
  const groups=[...buckets.values()];
  if(!groups.length) return `<section class="rev-chart-panel"><h3>시간대별 고객 활동</h3><p class="rc-note">이 실행의 시간대별 활동 내역은 제공되지 않았습니다.</p></section>`;
  groups.sort((a,b)=>a.date.localeCompare(b.date)||a.hour.localeCompare(b.hour));
  return `<section class="rev-chart-panel rev-activity" aria-label="시간대별 고객 활동"><div class="cf-sh"><h3>시간대별 고객 활동</h3><span class="cf-sub">실제 실행의 선택 행동 · 이동 자체는 매출에 포함하지 않음</span></div>${groups.map((g,i)=>`<details data-operation-bucket="${i}"><summary>${esc(g.date)} · ${esc(g.hour)} · ${g.actions.length}건</summary><ul>${g.actions.map(({pid,r,a})=>`<li><button type="button" class="cf-link" data-operation-customer="${esc(pid)}" data-operation-day="${Number(a.visit_day)||1}">${esc(r.display_id||dno(pid))}</button> · ${esc(a.time||"시각 미상")} · ${esc(a.label||a.action||a.action_id||"활동")} · ${esc(a.purchase_status||"구매 없음")}${a.row_id?` · L5 연결`:` · 거래행 없음`}</li>`).join("")}</ul></details>`).join("")}</section>`;
}
function revEvidenceHTML(cmp) {
  if(!cmp||!cmp.comparable||!cmp.customers) return "";
  const values=Object.values(cmp.customers), changed=values.filter(x=>x.changed), actions=values.reduce((n,x)=>n+(x.activity_changes||[]).length,0), rows=values.reduce((n,x)=>n+(x.row_changes||[]).length,0);
  return `<section class="rev-evidence" aria-label="행사 조건 비교 근거"><b>동일 고객 조건 비교</b><span>${changed.length}/${values.length}팀 행동 변화 · 행동 차이 ${actions}건 · L5 소비 행 차이 ${rows}건 · 결제액 차이 ${rcDelta(cmp.delta_krw)}</span><small>비교 가능한 실제 시뮬레이션 결과 요약이며 실제 매출 예측이 아닙니다.</small></section>`;
}
function revObservationsHTML(L,cmp) {
  const items=[], buckets=new Map();
  for(const [pid,r] of Object.entries(L.receipts||{})) for(const a of r.actions||[]) {
    if(!a.time||!a.venue_id||a.action==="move") continue;
    const key=`${a.visit_date||L.context.start_date||""} ${a.time.slice(0,2)}시 · ${a.venue_id}`;
    if(!buckets.has(key)) buckets.set(key,[]); buckets.get(key).push({pid,a});
  }
  const peak=[...buckets.entries()].sort((a,b)=>b[1].length-a[1].length)[0];
  if(peak) items.push(`<article><small>시간대별 시설 이용</small><h4>${esc(peak[0])}</h4><p>선택 활동 ${peak[1].length}건이 기록됐습니다.</p><button class="cf-link" data-operation-customer="${esc(peak[1][0].pid)}" data-operation-day="${peak[1][0].a.visit_day||1}">해당 고객 행동 확인 →</button></article>`);
  const venue=L.venues.filter(v=>v.paid_krw>0).sort((a,b)=>b.paid_krw-a.paid_krw)[0];
  if(venue) items.push(`<article><small>가상 소비가 가장 큰 업장</small><h4>${esc(rcVenueName(venue.name))}</h4><p>${venue.team_count}팀 · L5 결제액 ${rcMoney(venue.paid_krw)}</p><button class="cf-link" data-rev-venue="${esc(JSON.stringify(venue.key))}">고객과 선택 근거 확인 →</button></article>`);
  if(cmp&&cmp.comparable) { const pair=Object.entries(cmp.customers||{}).find(([id,c])=>(c.activity_changes||[]).length&&L.receipts[id]); if(pair) items.push(`<article><small>행사 조건 비교</small><h4>${esc(L.receipts[pair[0]].display_id)}의 행동 변화</h4><p>같은 방문 조건에서 행동 ${(pair[1].activity_changes||[]).length}건이 달라졌습니다.</p><button class="cf-link" data-operation-customer="${esc(pair[0])}" data-operation-day="1">기록된 고객 행동 확인 →</button></article>`); }
  return `<section class="rev-observations"><div class="cf-sh"><h3>이번 방문에서 살펴볼 것</h3><span class="cf-sub">실제 시뮬레이션 기록</span></div>${items.length?`<div class="rev-observation-grid">${items.slice(0,3).join("")}</div>`:`<p class="rc-note">관찰 항목을 구성할 행동 기록이 아직 없습니다.</p>`}</section>`;
}
function revConsumptionHTML(L) {
  const room=L.levels.L2.filter(g=>/ROOM|객실/i.test(g.key[0]));
  const paidRoom=Object.values(L.receipts||{}).some(r=>(r.rows||[]).some(x=>(x.act||x.action_id)==="room_night" && x.purchase_status==="SIMULATED_CHARGE" && x.paid_krw>0));
  return `<section class="rev-chart-panel"><div class="cf-sh"><h3>소비와 시설 이용</h3><span class="cf-sub">활동과 결제는 별도 기록</span></div><div class="rev-consumption"><article><small>현재 L5 시뮬레이션 결제액</small><strong>${rcMoney(L.totals.paid_krw)}</strong><p>금액 미확인 거래는 합계에서 제외</p></article><article><small>ROOM</small><strong>${paidRoom?"객실박 거래 연결됨":"객실박 결제 미연결"}</strong><p>객실 모델 가정액은 합계에서 제외합니다.${room.length?` 기존 ROOM 부문 ${room.map(g=>rcMoney(g.paid_krw)).join(" · ")}은 바·룸서비스 등 부문 거래이며 객실박 요금과 다릅니다.`:""}</p></article>${L.levels.L2.filter(g=>!/ROOM|객실/i.test(g.key[0])).map(g=>`<article><small>${esc(g.key[0])}</small><strong>${rcMoney(g.paid_krw)}</strong><p>현재 실행의 가상 거래</p></article>`).join("")}</div></section>`;
}
function revProfileContext(receipt, context) {
  const parts = [rcContext({ ...context, ...receipt })];
  if (receipt.stay && receipt.nights) parts.push(`${receipt.nights}박`);
  return parts.filter(Boolean).join(" · ");
}
async function revInit() {
  if (!REV.allIds.length) {
    const meta = await api("/api/turn/meta?turn=dinner");
    REV.allIds = meta.personas.map(p => p.id).sort((a,b) => dno(a).localeCompare(dno(b)));
    REV.personaSearch = Object.fromEntries(meta.personas.map(p => [p.id, (p.bars || []).map(x => typeof x === "string" ? x : (x.label || x.key || "")).filter(Boolean).join(" ")]));
  }
}
const revScenarioOf = request => request.intervention && request.intervention !== "none" ? request.intervention :
  (request.event_mode ? request.event_mode === "wine" : !!request.event) ? "wine" : "none";
function revRememberFlow(flow, request) {
  if (!flow || !flow.plans) return;
  flow.request=structuredClone(request);
  if (!flow.ledger) {
    if (typeof DS !== "undefined" && DS.last && DS.last.hit) { REV.pendingDemo = { flow: structuredClone(flow), request: structuredClone(request), key: DS.last.key }; REV.latest = null; if (REV.scope === "recent") revInvalidate(); }
    return;
  }
  if (!["live_engine", "stored_demo"].includes(flow.ledger.source)) return;
  REV.pendingDemo = null;
  REV.latest = { flow: structuredClone(flow), request: structuredClone(request) };
}
function revRememberDemoLedger(ledger, key) {
  const pending = REV.pendingDemo;
  if (!pending || pending.key !== key || ledger.source !== "stored_demo") return;
  revRememberFlow({ ...pending.flow, ledger }, pending.request);
  if (typeof MODE !== "undefined" && MODE === "opx" && REV.scope === "recent") revUseRecent();
}
function revRememberAB(offLedger, onLedger, comparison) {
  if (!offLedger || !onLedger || !comparison || !comparison.comparable || offLedger.source !== "live_engine" || onLedger.source !== "live_engine" ||
      Boolean(offLedger.context.event) || !Boolean(onLedger.context.event) || comparison.baseline_id !== offLedger.run_id || comparison.scenario_id !== onLedger.run_id) return;
  REV.abPair = { off: structuredClone(offLedger), on: structuredClone(onLedger), comparison: structuredClone(comparison) };
}
const revIds = () => REV.scope === "all" ? [...REV.allIds] : REV.scope === "selected" ? [...REV.selected].filter(id => REV.allIds.includes(id)).sort((a,b) => dno(a).localeCompare(dno(b))) : REV.latest ? Object.keys(REV.latest.flow.plans) : [];
const revDraftKey = () => JSON.stringify([REV.scope, revIds().slice().sort(), REV.duration, REV.scenario, REV.scope === "recent" && REV.latest ? REV.latest.flow.ledger.run_id : null]);
function revRequest(kind) {
  const ids = revIds(), source = REV.latest ? REV.latest.request : {};
  if (!["day_visit", "stay_1", "stay_2", "stay_3"].includes(REV.duration)) throw new Error("지원하지 않는 체류 일정입니다.");
  const request = { personas: ids, duration: REV.duration, event_mode: kind === "wine" ? "wine" : "none",
    seed: Number.isInteger(source.seed) ? source.seed : 0, start_date: "2026-10-24", include_ledger: true };
  if (source.behavior_engine==='m4_c01') {
    request.behavior_engine='m4_c01';
    if(source.visit_conditions)request.visit_conditions=Object.fromEntries(ids.filter(id=>source.visit_conditions[id]).map(id=>[id,structuredClone(source.visit_conditions[id])]));
    if(source.simulation_mode)request.simulation_mode=source.simulation_mode;
  }
  if (REV.scope === "recent" && source.package_id) request.package_id = source.package_id;
  if (REV.referenceProfile !== "external") request.reference_profile = REV.referenceProfile;
  if (REV.prior !== "OFF") { request.behaviour_prior = REV.prior; request.behavior_engine = "m4_c01"; request.catalog_policy = "C01_HOTEL_CATALOG_V1"; request.simulation_mode = "independent"; }
  return request;
}
async function revUseRecent() {
  if (!REV.latest) return;
  ++REV.token; ++REV.filterToken;
  REV.busy = false; REV.err = null; REV.scope = "recent";REV.setupOpen=false;
  REV.ids = revIds(); REV.scenario = revScenarioOf(REV.latest.request);
  REV.duration = REV.latest.request.duration || (REV.latest.flow.ledger.context || {}).duration || "day_visit";
  REV.flow = {...REV.latest.flow}; REV.baseline = null;
  REV.completedScenario = REV.scenario; REV.completedKey = revDraftKey();
  REV.department = REV.venue = REV.product = REV.customer = null;
  REV.ledger = REV.flow.ledger; REV.comparison = null;
  revRender();
}
function revInvalidate() {
  ++REV.token; ++REV.filterToken;
  REV.flow = REV.baseline = REV.ledger = REV.comparison = null; REV.completedKey = null;
  REV.department = REV.venue = REV.product = REV.customer = null; REV.err = null;
}
async function revEnter() {
  if (REV.pendingDemo && !REV.latest) { REV.scope = "recent"; revInvalidate(); return; }
  if (REV.latest && REV.enteredLatest !== REV.latest.flow.ledger.run_id) {
    REV.enteredLatest = REV.latest.flow.ledger.run_id;
    await revUseRecent();
  }
}
async function revRun() {
  if (REV.scope === "recent") { await revUseRecent(); return; }
  if (REV.busy || !revIds().length) return;
  REV.setupOpen=false;
  const token = ++REV.token, kind = REV.scenario, key = revDraftKey(), request = revRequest(kind);
  ++REV.filterToken;
  REV.pickerOpen = false;
  REV.busy = true; REV.err = null; revRender();
  try {
    const flow = await api("/api/visit", request);
    flow.request=structuredClone(request);
    const baseline = kind === "none" ? flow : await api("/api/visit", revRequest("none"));
    if (flow.ledger.source !== "live_engine") throw new Error("실제 고객 흐름 계산 결과를 확인하지 못했습니다. 다시 실행해 주세요.");
    if (token !== REV.token) return;
    REV.ids = request.personas; REV.baseline = baseline; REV.flow = flow; REV.completedScenario = kind; REV.completedKey = key;
    REV.department = REV.venue = REV.product = REV.customer = null;
    await revFilter();
  } catch (e) { REV.err = e.message; }
  finally { if (token === REV.token) { REV.busy = false; revRender(); } }
}
async function revFilter() {
  if (!REV.flow) return;
  const token = ++REV.filterToken, flow = REV.flow, baseline = REV.baseline;
  const eventOnly = baseline && flow.ledger.source === "live_engine" && baseline.ledger.source === "live_engine" &&
    Boolean(baseline.ledger.context.event) !== Boolean(flow.ledger.context.event);
  const [ledger, comparison] = await Promise.all([
    Promise.resolve(flow.ledger),
    baseline && baseline.ledger.run_id !== flow.ledger.run_id
      ? api("/api/ledger/compare", { baseline_id: baseline.ledger.run_id, scenario_id: flow.ledger.run_id, event_only: eventOnly })
      : Promise.resolve(null)
  ]);
  if (token !== REV.filterToken) return;
  REV.ledger = ledger; REV.comparison = comparison;
  const valid = ledger.venues.some(v => JSON.stringify(v.key) === REV.venue);
  if (!valid) REV.venue = REV.product = REV.customer = null;
  revRender();
}
function revLegacyHTML() {
  const L = REV.ledger, recent = REV.scope === "recent", cmp = REV.comparison;
  const eventCmp = L ? revEventComparison(L) : null;
  const comparisonValue = cmp && cmp.comparable ? rcDelta(cmp.delta_krw) : (REV.completedScenario === "none" && !recent ? "기준 실행" : "비교 미확정");
  const comparisonLabel = cmp && cmp.comparable ? `${esc(REV_SCENARIOS[revScenarioOf(REV.baseline.ledger.context)] || "기준 조건")} · 같은 고객·시드`
    : REV.completedScenario === "none" && !recent ? "행사 없음 기준 결과 · 비교 실행 없음" : cmp && !cmp.comparable ? esc(cmp.message) : "행사 없음 기준과 비교";
  const status = REV.busy ? "방문 전체 행동을 날짜별로 계산 중…" : L ? `${REV_SCENARIOS[REV.completedScenario]} · ${recent ? rcSource(L) + " 그대로 보기" : "실제 엔진 계산 완료"}` : "계산 전 · 고객과 체류 조건을 선택해 주세요";
  const durationLabel = {day_visit:"비투숙 · 당일 방문",stay_1:"1박 2일",stay_2:"2박 3일",stay_3:"3박 4일"}[REV.duration] || REV.duration;
  return `<section class="rev-root${REV.animateEntry?" rev-entry":""}"><div class="rev-title"><div><h2>방문 행동 기반 가상 소비</h2><p>고객의 날짜별 연속 행동과 거래를 한 번의 방문으로 합산합니다.</p></div><span class="rev-basis">${L ? `참여 고객 ${L.team_count}팀 기준` : `선택 고객 ${revIds().length}팀`}</span></div>
    <div class="rev-mode-row"><button type="button" class="cf-btn${recent ? " cf-primary" : ""}" data-rev-recent${REV.busy || !REV.latest ? " disabled" : ""}>마지막 시뮬레이션 불러오기</button><span>${recent ? "마지막 고객 흐름 결과를 재계산하지 않고 표시 중" : "저장된 결과는 새 계산에 섞지 않습니다."}</span>${recent ? `<button type="button" class="cf-link" data-rev-new>새 시뮬레이션 설정</button>` : ""}</div>
    ${!recent ? revSetupControlsHTML() : ""}
    ${REV.scope === "recent" && !REV.latest ? `<p class="rc-note">고객 흐름에서 실제 시뮬레이션을 실행하면 같은 고객·조건·영수증을 여기서 이어봅니다.</p>` : ""}
    ${L ? revRunContextHTML(L) : ""}
    <p class="rev-status" role="status">${esc(status)}</p>${REV.err ? `<p class="rc-note" role="alert">${esc(REV.err)}</p>` : ""}
    ${L ? `${revObservationsHTML(L,eventCmp)}${revConsumptionHTML(L)}
    ${typeof sharedOperationsHTML === "function" ? sharedOperationsHTML(L) : ""}${revActivityHTML(L)}
    ${L.input_missing.length ? `<p class="rc-note">실행 입력 미연결 ${L.input_missing.length}명은 이번 계산과 합계에서 제외했습니다.</p>` : ""}${L.totals.unknown_count ? `<p class="rc-note">금액 미확인 ${L.totals.unknown_count}건은 기본 결제액에 포함하지 않았습니다.</p>` : ""}
    <div class="rev-sectors"><button type="button" class="cf-btn cf-sm${!REV.department ? " cf-primary" : ""}" data-rev-dept="">호텔 합계</button>${L.levels.L2.filter(g => !/ROOM|객실/i.test(g.key[0]) || g.paid_krw > 0).map(g => `<button type="button" class="cf-btn cf-sm${REV.department === g.key[0] ? " cf-primary" : ""}" data-rev-dept="${esc(g.key[0])}">${esc(g.key[0])} · ${rcMoney(g.paid_krw)}</button>`).join("")}</div>
    ${L ? `<section class="rev-chart-panel"><div class="cf-sh"><h3>업장별 가상 소비</h3><span class="cf-sub">현재 원장 · 금액순 · 참여 고객 ${L.team_count}팀</span></div>${revVenueAmountChart(L)}</section>` : ""}
    ${eventCmp ? `${revEvidenceHTML(eventCmp)}<section class="rev-chart-panel"><div class="cf-sh"><h3>행사 전후 업장별 소비 변화</h3><span class="cf-sub">행사 없음 → 와인페어 · 같은 고객 집합 · 실제 엔진 재계산</span></div>${revEventDeltaChart(eventCmp)}</section>` : ""}
    ${typeof sharedOperationsHTML === "function" ? sharedOperationsHTML(L) : ""}
    <div class="rev-layout"><section class="rev-venues"><div class="cf-sh"><h3>${REV.department ? esc(REV.department) + " · " : ""}업장별 가상 매출</h3><span class="cf-sub">금액순 · 같은 고객 집합</span></div>${revVenues(L, eventCmp)}</section><aside class="rev-drill">${revDrill(L)}</aside></div><details class="rev-details"><summary>상세 원장 · 날짜별 결제와 가격 산정 근거</summary><div class="rev-cohort"><b>집계 결과 · ${L.team_count}팀</b><span>${Object.values(L.receipts).map(r => esc(r.display_id)).join(" · ")}</span><details><summary>고객 유형과 계산된 방문 조건·출처</summary><ul>${Object.values(L.receipts).map(r => `<li><b>${esc(r.display_id)} · ${esc(r.customer_type)}</b> · ${esc(revProfileContext(r, L.context))} · ${esc(r.visit_profile_note || "방문 조건 출처 미확인")}</li>`).join("")}</ul></details></div>
    ${L.visit ? `<section class="rev-chart-panel"><div class="cf-sh"><h3>체류 전체 소비 · ${durationLabel}</h3><span class="cf-sub">${esc(L.visit.start_date)} 시작 · ${L.visit.nights}박 · ${L.visit.day_count}일</span></div><table class="rev-table"><thead><tr><th>일자</th><th>단계</th><th>행사</th><th>시뮬레이션 결제액</th><th>${L.virtual_revenue?"객실 모델액":"객실 가정액"}</th></tr></thead><tbody>${L.visit.days.map(d=>`<tr><th>${esc(d.date)}</th><td>${esc(d.phase)}</td><td>${d.event_available?"와인페어":"행사 없음"}</td><td>${rcMoney(d.paid_krw)}</td><td>${rcMoney(L.virtual_revenue?L.virtual_revenue.rows.filter(r=>r.action_id==="room_night"&&r.date===d.date).reduce((n,r)=>n+(r.virtual_gross_krw||0),0):d.assumption_addition_krw)}</td></tr>`).join("")}</tbody></table><p class="rc-note">날짜별 거래 합계가 체류 전체 L5 원장에 연결됩니다. 객실 가정액은 시뮬레이션 결제액에 포함하지 않습니다.</p></section>` : ""}
<details><summary>가격 산정 근거 · 과거 객실 가정</summary><p class="rc-note">과거 가격 어댑터의 객실 가정액 ${rcMoney(L.totals.assumption_addition_krw)}. M4 행동 선택의 결제 결과와 별도이며 기본 결제 합계에 더하지 않습니다.</p></details></details>` : `<div class="rev-empty">${REV.busy ? "고객의 방문 전체 행동을 계산하고 있습니다." : recent ? "고객 흐름의 마지막 실행 결과를 기다리고 있습니다." : "계산 전 · 고객과 조건을 선택한 뒤 방문 전체 시뮬레이션을 실행해 주세요."}</div>`}
    <p class="rc-note">고객 행동 시뮬레이션에 따른 가상 매출이며, 실제 매출 예측값은 아닙니다.</p></section>`;
}
function revEventComparison(L) {
  if (REV.scope === "recent") {
    const p = REV.abPair;
    return p && [p.off.run_id, p.on.run_id].includes(L.run_id) ? p.comparison : null;
  }
  if (!REV.comparison || !REV.comparison.comparable || !REV.baseline || !REV.flow || !REV.baseline.ledger || !REV.flow.ledger) return null;
  return Boolean(REV.baseline.ledger.context.event) !== Boolean(REV.flow.ledger.context.event) ? REV.comparison : null;
}
function revVenueAmountChart(L) {
  const list=L.venues.filter(v => !REV.department || v.department===REV.department).filter(v => v.paid_krw>0 || v.unknown_count>0);
  if (!list.length) return `<p class="rc-note">현재 집계에 표시할 업장 소비가 없습니다.</p>`;
  const max=Math.max(1,...list.map(v=>v.paid_krw));
  return `<ol class="rev-chart" aria-label="업장별 시뮬레이션 소비액">${list.slice().sort((a,b)=>b.paid_krw-a.paid_krw).slice(0,REV.flowExpanded||REV.detailPanel?list.length:5).map(v=>`<li><button type="button" class="rev-chart-row" data-rev-department="${esc(v.department)}" data-rev-venue="${esc(JSON.stringify(v.key))}"><span class="rev-chart-label">${esc(rcVenueName(v.name))}<small>${esc(v.department)} · ${v.team_count}팀</small></span><span class="rev-chart-track"><i style="width:${Math.max(0,100*v.paid_krw/max)}%"></i></span><b>${v.unknown_count&&!v.paid_krw?"금액 미확인":rcMoney(v.paid_krw)}</b></button></li>`).join("")}</ol>${!REV.flowExpanded&&!REV.detailPanel&&list.length>5?`<button class="cf-link" data-rev-expand="venues">전체 ${list.length}개 업장 보기 ↗</button>`:""}`;
}
function revEventDeltaChart(cmp) {
  const list=(cmp.venues||[]).filter(v=>!REV.department || v.department===REV.department).filter(v=>v.before_krw || v.after_krw || v.delta_krw);
  if (!list.length) return `<p class="rc-note">두 조건에서 업장 소비 변화가 없습니다.</p>`;
  const max=Math.max(1,...list.map(v=>Math.abs(v.delta_krw)));
  return `<ol class="rev-chart rev-delta-chart" aria-label="행사 전후 업장별 소비액 변화">${list.slice().sort((a,b)=>Math.abs(b.delta_krw)-Math.abs(a.delta_krw)).map(v=>{const w=Math.min(50,50*Math.abs(v.delta_krw)/max),left=v.delta_krw<0?50-w:50;return `<li><button type="button" class="rev-chart-row" data-rev-venue="${esc(JSON.stringify(v.key))}"><span class="rev-chart-label">${esc(rcVenueName(v.name))}<small>${esc(v.department)}</small></span><span class="rev-delta-track"><i class="${v.delta_krw>0?"up":v.delta_krw<0?"down":"flat"}" style="left:${left}%;width:${w}%"></i></span><b>${rcDelta(v.delta_krw)}</b></button></li>`;}).join("")}</ol><p class="rc-note">업장을 선택하면 상품·고객 상세를 엽니다. 그래프 증감 합계는 비교 응답의 고객·업장 합계와 일치합니다.</p>`;
}
function revVenues(L, comparison=REV.comparison) {
  const list = L.venues.filter(v => !REV.department || v.department === REV.department).filter(v => !/ROOM|객실/i.test(v.department) || v.paid_krw > 0);
  if (!list.length) return `<p class="rc-note">이 고객 집합에서 해당 이용 내역이 없습니다.</p>`;
  return `<table class="rev-table"><thead><tr><th>업장</th><th>이용 팀</th><th>가상 결제액</th><th>기준 실행 대비</th><th>주요 고객 유형</th></tr></thead><tbody>${list.map(v => {
    const key = JSON.stringify(v.key), delta = comparison && comparison.comparable ? comparison.venues.find(x => JSON.stringify(x.key) === key) : null;
    return `<tr class="${key === REV.venue ? "on" : ""}"><th><button type="button" class="cf-link" data-rev-venue="${esc(key)}">${esc(rcVenueName(v.name))}</button><small>${esc(v.department)}${v.unknown_count ? ` · 금액 미확인 ${v.unknown_count}건` : ""}</small></th><td data-label="이용 팀">${v.team_count}팀</td><td data-label="가상 결제액">${v.unknown_count && !v.paid_krw ? "금액 미확인" : rcMoney(v.paid_krw)}</td><td data-label="기준 대비">${delta ? rcDelta(delta.delta_krw) : "—"}</td><td class="rev-types" data-label="고객 유형">${v.types.slice(0,2).map(t => `${esc(t.name)} ${t.team_count}팀`).join(" · ")}${v.types.length > 2 ? ` 외 ${v.types.length-2}유형` : ""}</td></tr>`;
  }).join("")}</tbody></table>`;
}
function revDrill(L) {
  const v = L.venues.find(x => JSON.stringify(x.key) === REV.venue);
  if (!v) return `<div class="rev-empty">업장을 선택하면 상품과 이용 고객을 확인할 수 있습니다.</div>`;
  const products = L.levels.L4.filter(g => g.key[0] === v.department && g.key[1] === v.name);
  const customers = v.customer_ids.filter(id => !REV.product || L.receipts[id].rows.some(r => r.department === v.department && r.venue === v.name && r.product === REV.product));
  const max = Math.max(1, ...v.types.map(t => REV.amountBars ? t.paid_krw : t.team_count));
  return `<div class="cf-sh"><h3>${esc(rcVenueName(v.name))}</h3><span class="cf-sub">${v.team_count}팀 · ${rcMoney(v.paid_krw)}</span></div>
    <p class="rc-note">호텔 → ${esc(v.department)} → ${esc(rcVenueName(v.name))} → 상품 → 고객 영수증</p>
    <h4>이용 고객 구성</h4><button type="button" class="cf-link" id="revBarToggle">${REV.amountBars ? "이용 팀 수로 보기" : "금액 비중으로 보기"}</button>
    <ul class="rev-bars">${v.types.map(t => { const value = REV.amountBars ? t.paid_krw : t.team_count; return `<li><span>${esc(t.name)}</span><b>${REV.amountBars ? rcMoney(value) : value + "팀"}</b><span class="rev-track"><i style="width:${100 * value / max}%"></i></span></li>`; }).join("")}</ul>
    <p class="rc-note">${REV.amountBars ? "금액 기준이며 이용 팀 비중과 다릅니다." : "같은 고객의 반복 이용은 이용 팀 수에서 한 번만 셉니다. 표본 내 팀 수입니다."}</p>
    <h4>상품별 내역</h4><ul class="rc-summary">${products.map(g => `<li><button type="button" class="cf-link rev-product-name${REV.product === g.key[2] ? " on" : ""}" data-rev-product="${esc(g.key[2])}">${esc(g.key[2])}</button><b>${g.unknown_count && !g.paid_krw ? "금액 미확인" : rcMoney(g.paid_krw)}</b></li>`).join("")}</ul>
    ${REV.product ? `<button type="button" class="cf-link" id="revAllProducts">모든 상품의 고객 보기</button>` : ""}<h4>이용 고객 · ${REV.product ? "선택 상품" : "해당 업장"} 소비액</h4><div class="rev-customer-list">${customers.map(id => { const r = L.receipts[id], amount = r.rows.filter(x => x.department === v.department && x.venue === v.name && (!REV.product || x.product === REV.product)).reduce((sum,x) => sum + x.paid_krw, 0); return `<button type="button" class="rev-customer-line${REV.customer === id ? " on" : ""}" data-rev-customer="${esc(id)}"><span><b>${esc(r.display_id)}</b><small>${esc(r.customer_type)}</small></span><b>${rcMoney(amount)}</b></button>`; }).join("")}</div>
    ${REV.customer && customers.includes(REV.customer) ? `<button type="button" class="cf-link" id="revCustomerFlow">이 실행의 고객흐름·판단 근거 보기</button>${rcReceiptHTML(L, REV.customer, REV.comparison)}` : ""}`;
}
function revWireRollNodes(root) {
  root.querySelectorAll('[data-rev-roll]').forEach(button=>{
    const select=()=>{REV.rollSelection={run:REV.ledger.run_id,id:button.dataset.revRoll};REV.rollRow=null;revRender();};
    button.onclick=select;button.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select();}};
  });
}
// Fit the time plot to the available card content, not by scaling text or data.
function revFitSpendChart(root) {
  const chart=root.querySelector('.rev-spend-chart'),L=REV.ledger;
  if(!chart||!L)return;
  const width=Math.max(570,Math.round(chart.clientWidth)),height=Math.max(130,Math.round(chart.clientHeight));
  const identity=width+'x'+height;
  if(chart.dataset.plotSize===identity)return;
  chart.dataset.plotSize=identity;
  const date=root.querySelector('#revOpsDate')?.value, bins=revOpsBins(L,date);
  const hour=Number(root.querySelector('[data-rev-hour].on')?.dataset.revHour??REV.opsHour??0);
  const tpl=document.createElement('template');tpl.innerHTML=revSpendChartHTML(bins,hour,{width,height});
  const svg=tpl.content.querySelector('svg');svg.style.width=width+'px';
  chart.querySelector('svg').replaceWith(svg);
  const hit=chart.querySelector('.rev-chart-hitareas');
  hit.style.setProperty('left','64px','important');hit.style.setProperty('right','auto','important');
  hit.style.setProperty('width',(width-94)+'px','important');
  hit.style.setProperty('top','12px','important');hit.style.setProperty('bottom','22px','important');
}
function revFitCompactGraph(root) {
  const graph=root.querySelector('.rev-compact-sankey');if(!graph||!REV.ledger)return;
  const width=Math.round(graph.getBoundingClientRect().width);
  if(width<1||Math.abs(graph.viewBox.baseVal.width-width)<.5)return;
  REV.compactWidth=width;graph.outerHTML=revRollupHTML(REV.ledger);revWireRollNodes(root);
}
function revSetupView(root) {
  if(!root.querySelector('.rev-settings-panel'))return null;
  const active=document.activeElement,picker=root.querySelector('[data-picker="revenue"]');
  const focus=picker?.contains(active)?active.matches('[data-picker-search]')?'search':active.matches('[data-picker-all]')?'all':active.dataset.pickerId?{customer:active.dataset.pickerId}:null:null;
  return {focus,selection:focus==='search'?[active.selectionStart,active.selectionEnd]:null,
    listScroll:picker?.querySelector('.hl-picker-list')?.scrollTop||0,
    pageScroll:document.querySelector('#opxView')?.scrollTop||0};
}
function revRestoreSetupView(root,snapshot) {
  if(!snapshot||!root.querySelector('.rev-settings-panel'))return;
  const picker=root.querySelector('[data-picker="revenue"]'),s=snapshot.focus;
  const active=s==='search'?picker?.querySelector('[data-picker-search]'):s==='all'?picker?.querySelector('[data-picker-all]'):s?.customer?[...picker.querySelectorAll('[data-picker-id]')].find(x=>x.dataset.pickerId===s.customer):null;
  active?.focus({preventScroll:true});
  if(snapshot.selection&&active)active.setSelectionRange(...snapshot.selection);
  const list=picker?.querySelector('.hl-picker-list');if(list)list.scrollTop=snapshot.listScroll;
  const page=document.querySelector('#opxView');if(page)page.scrollTop=snapshot.pageScroll;
}
function revRender() {
  const mount=document.querySelector('#revenueContent');if(!mount)return;
  const snapshot=revSetupView(mount),chart=mount.querySelector('.rev-roll-scroll'),left=chart?.scrollLeft||0;
  mount.innerHTML=revHTML();revWire();const next=mount.querySelector('.rev-roll-scroll');if(next)next.scrollLeft=left;
  requestAnimationFrame(()=>{if(mount.isConnected)revRestoreSetupView(mount,snapshot);});
}
function revWire() {
  const root = document.querySelector("#revenueContent"); if (!root) return;
  agReadableMount(root);revFitCompactGraph(root);revAnalysisWire(root);
  if(REV.spendObserver)REV.spendObserver.disconnect();
  const spend=root.querySelector(".rev-spend-chart");
  if(spend){REV.spendObserver=new ResizeObserver(()=>revFitSpendChart(root));REV.spendObserver.observe(spend);revFitSpendChart(root);}
  if(REV.graphObserver)REV.graphObserver.disconnect();
  const graphPanel=root.querySelector('.rev-board-time');
  if(graphPanel){REV.graphObserver=new ResizeObserver(()=>revFitCompactGraph(root));REV.graphObserver.observe(graphPanel);}
  root.querySelectorAll('.rev-overlay').forEach(el=>el.onclick=e=>{if(e.target===el){REV.setupOpen=false;REV.flowExpanded=false;REV.detailPanel=null;revRender();}});
  hlCustomerPickerWire(root,REV.allIds,REV.scope==='all'?new Set(REV.allIds):REV.selected,selected=>{REV.selected=selected;REV.scope=selected.size===REV.allIds.length?'all':'selected';REV.pickerOpen=true;revRender();},open=>REV.pickerOpen=open,{query:REV.search,onChange:q=>REV.search=q});
  root.querySelectorAll('[data-rev-setup-close]').forEach(b=>b.onclick=()=>{REV.setupOpen=false;REV.err=null;revRender();});
  root.querySelectorAll('[data-rev-expand]').forEach(b=>b.onclick=()=>{REV.rollView=b.dataset.revExpand||'flow';REV.flowExpanded=true;REV.rollSelection=null;revRender();});
  root.querySelectorAll('[data-rev-overlay-close]').forEach(b=>b.onclick=()=>{REV.flowExpanded=false;REV.detailPanel=null;revRender();});
  root.querySelectorAll('[data-rev-all-transactions]').forEach(b=>b.onclick=()=>{REV.detailPanel='transactions';REV.rollSelection=null;revRender();});
  root.querySelectorAll('[data-rev-detail-open]').forEach(b=>b.onclick=()=>{REV.detailPanel='transaction';revRender();});
  root.querySelectorAll('[data-rev-hour-clear]').forEach(b=>b.onclick=()=>{REV.hourFilter=false;revRender();});

  const activity=root.querySelector(".ux-revenue-activity");if(activity)activity.ontoggle=()=>{if(activity.isConnected)REV.uxActivityOpen=activity.open;};
  root.querySelectorAll('[data-rev-ux-evidence]').forEach(b=>b.onclick=()=>revUXOpenEvidence(b.dataset.revUxEvidence));
  root.querySelectorAll('[data-rev-review]').forEach(b=>b.onclick=async()=>{
    const raw=b.dataset.revReview, L=REV.ledger;
    const entry=Object.entries(L.receipts).flatMap(([pid,r])=>(r.actions||[]).map(a=>({pid,a}))).find(x=>`${x.pid}|${x.a.action_id}`===raw);if(!entry)return;
    await revShowCustomer(entry.pid);if(typeof agVisitDaySelect==='function' && L.visit)agVisitDaySelect(entry.a.visit_day||1);
    const scene=agScenes(entry.pid).find(s=>s.k!=='move' && (s.visit_day||1)===(entry.a.visit_day||1) && agHM(s.t0)===entry.a.time && (s.act===entry.a.action || s.k==='turn' && AG.runs[s.ti].turn===entry.a.turn));
    if(scene){agSetScene(scene.si);agActDrawer(entry.pid,scene.si);}
  });
  if (root.querySelector(".rev-entry")) {
    REV.animateEntry = false;
    if(!window.HLNav?.state.busy)requestAnimationFrame(()=>window.HLRevenueEntry?.enter());
    window.setTimeout(() => root.querySelector(".rev-entry")?.classList.remove("rev-entry"), 1400);
  }
  root.querySelectorAll("[data-rev-hour]").forEach(b=>b.onclick=()=>{REV.opsHour=Number(b.dataset.revHour);REV.hourFilter=true;REV.opsDate=REV.opsDate||(REV.ledger.visit?.days[0]?.date||REV.ledger.context.start_date);REV.rollRow=null;revRender();});
  const opsDate=root.querySelector("#revOpsDate"); if(opsDate) opsDate.onchange=()=>{REV.opsDate=opsDate.value;REV.rollRow=null;revRender();};
  if (typeof sharedOperationsWire === "function") sharedOperationsWire(root);
  root.querySelectorAll('[data-rev-view]').forEach(b=>b.onclick=()=>{REV.rollView=b.dataset.revView;REV.rollSelection=null;REV.rollRow=null;REV.venue=REV.product=REV.customer=null;revRender();});
  root.querySelectorAll('[data-rev-analysis-view]').forEach(b=>b.onclick=()=>{REV.analysisView=b.dataset.revAnalysisView;revRender();});
  revWireRollNodes(root);
  const closeRoll=root.querySelector("[data-rev-roll-close]");if(closeRoll)closeRoll.onclick=()=>{REV.rollSelection=null;REV.rollRow=null;revRender();};
  root.querySelectorAll('[data-rev-roll-clear]').forEach(clear=>clear.onclick=()=>{REV.rollSelection=null;REV.rollRow=null;revRender();});
  root.querySelectorAll('[data-rev-row]').forEach(b=>b.onclick=()=>{REV.rollRow=b.dataset.revRow;revRender();});
  root.querySelectorAll('[data-rev-transaction-action]').forEach(b=>b.onclick=async()=>{
    const row=Object.values(REV.ledger.receipts).flatMap(r=>r.rows).find(r=>r.row_id===b.dataset.revTransactionAction);if(!row)return;
    if(window.HLNav?.active()&&row.act!=='room_night')return HLNav.fromTransaction(row.row_id,'flow');
    await revShowCustomer(row.customer_id);if(typeof agVisitDaySelect==='function')agVisitDaySelect(row.visit_day||1);
    if(row.act==='room_night'){agCustDrawer(row.customer_id);return;}
    if(Number.isInteger(row.scene_index)){const raw=AG.plans[row.customer_id].scenes[row.scene_index];const scene=agScenes(row.customer_id).find(s=>s.k!=='move'&&raw&&s.t0===raw.t0&&s.t1===raw.t1&&s.act===raw.act);if(scene)agActDrawer(row.customer_id,scene.si);}
  });
  const recent = root.querySelector("[data-rev-recent]"); if (recent) recent.onclick = async () => { if (REV.busy) return; REV.scope = "recent"; await revUseRecent(); };
  root.querySelectorAll("[data-rev-new]").forEach(button => button.onclick = revNewSetup);
  const allClient = root.querySelector("#revAll"); if (allClient) allClient.onchange = () => { REV.scope = allClient.checked ? "all" : "selected"; revInvalidate(); revRender(); };
  const details = root.querySelector(".rev-client-picker"); if (details) details.ontoggle = () => { REV.pickerOpen = details.open; };
  const search = root.querySelector("#revSearch"); if (search) search.oninput = () => { REV.search = search.value; const q = REV.search.trim().toLocaleLowerCase(); root.querySelectorAll("[data-rev-client]").forEach(row => { row.hidden = q && !row.dataset.search.includes(q); }); };
  root.querySelectorAll("[data-rev-select]").forEach(input => input.onchange = () => {
    input.checked ? REV.selected.add(input.dataset.revSelect) : REV.selected.delete(input.dataset.revSelect);
    REV.scope = "selected"; REV.ids = revIds(); revInvalidate(); revRender();
  });
  const run = root.querySelector("#revRun"); if (run) run.onclick = revRun;
  const duration = root.querySelector("#revDuration"); if (duration) duration.onchange = () => { REV.duration = duration.value; revRender(); };
  const scenario = root.querySelector("#revScenario"); if (scenario) scenario.onchange = () => { REV.scenario = scenario.value; revRender(); };
  const refSel = root.querySelector("#revReference"); if (refSel) refSel.onchange = () => { REV.referenceProfile = refSel.value; revRender(); };
  const priorSel = root.querySelector("#revPrior"); if (priorSel) priorSel.onchange = () => { REV.prior = priorSel.value; revRender(); };
  const gpct = root.querySelector("#revGroupPct"); if (gpct) gpct.onchange = () => { REV.groupPct = Number(gpct.value); };
  const grun = root.querySelector("[data-rev-group-ab]"); if (grun) grun.onclick = revGroupAB;
  root.querySelectorAll("[data-rev-dept]").forEach(b => b.onclick = () => { REV.department = b.dataset.revDept || null; REV.venue = REV.product = REV.customer = null; revRender(); });
  root.querySelectorAll("[data-rev-venue]").forEach(b => b.onclick = () => { REV.venue = b.dataset.revVenue; REV.product = REV.customer = null;REV.rollRow=null;REV.detailPanel='venue';revRender(); });
  root.querySelectorAll("[data-rev-product]").forEach(b => b.onclick = () => { REV.product = b.dataset.revProduct; REV.customer = null; revRender(); });
  root.querySelectorAll("[data-rev-customer]").forEach(b => b.onclick = () => { REV.customer = b.dataset.revCustomer; revRender(); });
  const all = root.querySelector("#revAllProducts"); if (all) all.onclick = () => { REV.product = null; revRender(); };
  const bars = root.querySelector("#revBarToggle"); if (bars) bars.onclick = () => { REV.amountBars = !REV.amountBars; revRender(); };
  const flow = root.querySelector("#revCustomerFlow"); if (flow) flow.onclick = () => revShowCustomer(REV.customer);
  rcWire(root, async (pid, turn) => {
    await revShowCustomer(pid);
    const i = AG.runs.findIndex(r => r.turn === turn && r.customers.some(c => c.persona_id === pid));
    if (i >= 0) agChoiceDrawer(pid, i);
  });
}
async function revShowCustomer(pid) {
  if (!REV.flow || !REV.flow.plans[pid]) return;
  const r = structuredClone(REV.flow);
  await setMode("agents");
  if (typeof dsWait === "function") await dsWait(() => AG.meta && document.querySelector("#agRun"));
  AG.engine = "autonomy"; AG.many = new Set(Object.keys(r.plans)); AG.fix = false; AG.seed = r.engine.seed;
  AG.cond.event = r.ledger.context.event; AG.sel = pid; AG.visitData = r.ledger.visit ? r : null; AG.visitDay = 1; AG.visitRequest = null;
  const visitView = AG.visitData ? agVisitDayView(r, 1) : null;
  AG.plans = visitView ? visitView.plans : r.plans; AG.visits = visitView ? visitView.visits : r.visits; AG.runs = visitView ? visitView.runs : r.runs;
  AG.runs.forEach(R => { R._mode = "agents"; R._auto = true; R.customers.forEach(c => { c.vc = agVcOf(r.visits[c.persona_id]); }); if (R._before) { R._before._mode = "agents"; } });
  AG.ti = Math.max(0, AG.runs.findIndex(R => R.customers.some(c => c.persona_id === pid))); AG.res = AG.runs[AG.ti];
  RC.comparison = REV.comparison;
  AG.flow = { result: structuredClone(REV.flow), request: REV.latest&&REV.latest.flow.ledger.run_id===r.ledger.run_id?structuredClone(REV.latest.request):{ ...structuredClone(r.ledger.context), personas: Object.keys(r.plans), mode: Object.keys(r.plans).length > 1 ? "many" : "one" }, ledger: r.ledger, stories: r.stories || null, engine: r.engine, intervention: r.intervention, applied: r.levers_applied || [], skipped: r.levers_not_applied || [], notices: r.notices || [], sha: r.inputs_sha };
  AG.keep.agents = { runs: AG.runs, sel: pid, plans: AG.plans, visits: AG.visits, flow: AG.flow };
  agLeft(); agPlanHint(); agShow(false);
}

document.addEventListener('keydown',e=>{if(e.key==='Escape'&&typeof MODE!=='undefined'&&MODE==='opx'&&!document.querySelector('.hl-customer-picker[open]')){REV.setupOpen=false;REV.flowExpanded=false;REV.detailPanel=null;revRender();}});
