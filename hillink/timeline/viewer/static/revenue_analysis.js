/* Consumption analytics use the selected run's immutable L5 records. */
function revAllRows(L) { return Object.values(L.receipts||{}).flatMap(r=>r.rows||[]); }
function revRowClass(r) {
  if(r.amount_status==='UNKNOWN'||r.purchase_status==='UNKNOWN_AMOUNT')return 'UNRESOLVED';
  if(r.purchase_status==='PACKAGE_INCLUDED'||r.included_benefit)return r.paid_krw>0?'PAID_PRICED':'INCLUDED';
  if(r.purchase_status==='FREE_USE')return 'FREE';
  return r.paid_krw>0?'PAID_PRICED':'NO_PURCHASE';
}
function revPriceClass(r) {
  if(r.room_pricing?.price_reference_contract||r.sku_contract?.price_reference_contract)return '공식 시작가 참고 · 견적 아님';
  const tier=r.price_tier||r.sku_contract?.price_tier||r.room_pricing?.price_tier;
  if(r.sku_contract?.source_grade==='△'&&(!tier||tier==='EXISTING_REFERENCE'))return '가정 단가';
  if(!tier&&r.price_status==='VIRTUAL_MODEL_UNIT_PRICE')return '가정 단가';
  if(!tier&&/DATED_OFFICIAL_MENU_SIMULATION_REFERENCE|COLLECTED_REFERENCE_SIMULATION_PRICE_NOT_CURRENT_SALE|EXISTING_MENU_PRICE_USER_CONFIRMED_CONTRACT|COMPOSED_ORDER_FROM_EXISTING_MENU_REFERENCES|COMPOSED_PARENT_SET_WITH_PER_PERSON_ADDONS/.test(r.price_status||''))return '과거 참고';
  return ({OFFICIAL:'확인 출처',EXISTING_REFERENCE:'과거 참고',COMPARABLE_ESTIMATE:'비교 추정',SIMULATION_ASSUMPTION:'가정 단가'})[tier]||({ '◎':'기존 출처','○':'과거 참고','△':'가정 단가'})[r.price_grade]||(r.price_status==='VIRTUAL_MODEL_UNIT_PRICE'?'가정 단가':'가격 등급 미기록');
}
function revRoomReferenceHTML(r) {
  const c=r.room_pricing?.price_reference_contract||r.sku_contract?.price_reference_contract;if(!c)return '';
  return `<p class="rc-note" data-room-starting-reference>${esc(c.note)}<br>참고 상품: ${esc(c.reference_name)} · ${Number(c.starting_price_krw).toLocaleString('ko-KR')}원~ / ${esc(c.starting_price_unit)} · 기준 ${c.reference_people??'미확인'}명<br>이번 조건: ${c.scenario_people??'미확인'}명 · ${c.scenario_nights??'미확인'}박 · 적용일 ${esc(c.service_date)}${c.within_source_period?'':' · 출처 판매 기간 밖 참고가'}</p>`;
}
function revTypeLabel(r) { return ({PAID_PRICED:'유료',INCLUDED:'포함 혜택',FREE:'무료 이용',UNRESOLVED:'미산정',NO_PURCHASE:'비과금'})[revRowClass(r)]; }
function revIsProjection(r) { return r.order_origin==='SEPARATE_VIRTUAL_ORDER_PROJECTION'||r.sku_contract?.order_origin==='SEPARATE_VIRTUAL_ORDER_PROJECTION'||/^MODEL-HISTORICAL-/.test(r.product_sku_id||r.product_id||''); }
function revDirectEvent(r) {
  return /^C01-EVENT-|^WINE_FAIR/.test(r.product_sku_id||r.product_id||'')||r.venue_id==='WINE_FAIR'||r.act==='wine_fair'||r.event_contract?.event_id;
}
function revRank(rows,key) {
  const m=new Map();for(const r of rows){const k=key(r);const g=m.get(k)||{label:k,amount:0,quantity:0,units:new Set()};g.amount+=r.paid_krw||0;g.quantity+=r.billing_quantity||r.quantity||0;g.units.add(r.billing_unit||r.unit_basis||'미확인');m.set(k,g);}
  return [...m.values()].sort((a,b)=>b.amount-a.amount||a.label.localeCompare(b.label));
}
// Presentation only: every amount and link comes from this run's recorded L5 rows.
function revAnalysisRowsHTML(rows,limit=4) {
  return `<ul class="rev-analysis-records">${rows.slice(0,limit).map(r=>`<li><small>${esc(r.visit_date||'일자 미기록')} ${esc(r.time||'')} · ${esc(dno(r.customer_id))} · ${esc(r.venue||'')}</small><span>${esc(r.product)}</span><span class="rev-analysis-math">${r.unit_price_krw==null?'단가 미기록':rcMoney(r.unit_price_krw)} × ${esc(String(r.billing_quantity??r.quantity??'수량 미기록'))} <small>${esc(r.billing_unit||r.unit_basis||'')}</small> = ${revBoardAmount(r)}</span><small>${esc(revTypeLabel(r))}${r.paid_krw>0?' · '+esc(revPriceClass(r)):''}${revIsProjection(r)?' · 별도 가상 주문 투영':''}</small>${r.sku_contract?.source_resolution?.note?`<small>${esc(r.sku_contract.source_resolution.note)}</small>`:''}${r.act==='room_night'?'<small>객실박 거래 · 별도 행동 선택 없음</small>':`<button class="cf-link" data-rev-ux-evidence="${esc(r.row_id)}">거래·행동 근거 ›</button>`}</li>`).join('')}</ul>${rows.length>limit?`<button class="cf-link" data-rev-all-transactions>전체 거래에서 ${rows.length}건 확인 ›</button>`:''}`;
}
function revOperatorSummaryHTML(L) {
  const ids=Object.keys(L.receipts||{}),pid=ids.includes(REV.analysisCustomer)?REV.analysisCustomer:ids.length===1?ids[0]:null;
  const rows=revAllRows(L).filter(r=>!pid||r.customer_id===pid),paid=rows.filter(r=>r.paid_krw>0),sum=paid.reduce((n,r)=>n+r.paid_krw,0),venues=revRank(paid,r=>r.venue),products=revRank(paid,r=>r.product);
  const events=rows.filter(revDirectEvent),participated=events.filter(r=>!revIsProjection(r)),participants=new Set(participated.map(r=>r.customer_id)),eventAmount=events.reduce((n,r)=>n+(r.paid_krw||0),0),included=rows.filter(r=>revRowClass(r)==='INCLUDED'),free=rows.filter(r=>revRowClass(r)==='FREE');
  const eventCount=new Set(participated.map(r=>JSON.stringify([r.customer_id,r.visit_date,r.action_id||r.selection_id||r.time]))).size;
  const flagged=rows.filter(r=>revRowClass(r)==='UNRESOLVED'||r.paid_krw>0&&revPriceClass(r)!=='확인 출처');
  const issues=(L.consumption_audit?.issues||[]).filter(x=>!pid||x.customer_id===pid),unscoped=pid?(L.consumption_audit?.issues||[]).filter(x=>!x.customer_id).length:0;
  const context=JSON.stringify([L.run_id,pid]);if(REV.analysisContext!==context){REV.analysisContext=context;REV.analysisExpanded=new Set();}
  const group=(key,title,label,amount,body)=>`<details class="rev-analysis-group" data-analysis-group="${key}"${REV.analysisExpanded.has(key)?' open':''}><summary><small>${esc(title)}</small><span class="rev-analysis-label">${esc(label)}</span><span class="rev-analysis-value">${esc(amount)}</span><span class="rev-analysis-chevron" aria-hidden="true">⌄</span></summary><div class="rev-analysis-body">${body}</div></details>`;
  const rankList=groups=>groups.slice(0,3).map(g=>`<div class="rev-summary-line"><span>${esc(g.label)}</span><span>${rcMoney(g.amount)} · ${sum?(100*g.amount/sum).toFixed(1):0}%</span></div>`).join('');
  const scenario=REV.flow?.visit?.scenario_snapshot||REV.flow?.result?.visit?.scenario_snapshot||{},scenarioLabel=scenario.sources?.[0]?.record?.['행사 · 상품명']||L.context?.event_label||(L.context?.event?'행사 있음 (이름 미기록)':'행사 선택 정보 미기록');
  return `<div class="rev-console-heading"><h3>소비 분석</h3><select id="revAnalysisCustomer" aria-label="소비 분석 고객"><option value="">${ids.length===1?'개인 소비':'전체 고객'}</option>${ids.length>1?ids.map(id=>`<option value="${esc(id)}"${pid===id?' selected':''}>${esc(dno(id))}</option>`).join(''):''}</select></div><div class="rev-consumption-summary"><div class="rev-summary-total"><span>${pid?esc(dno(pid))+' 고객 일행 가상 소비':'이 실행의 전체 가상 소비'}</span><b>${rcMoney(sum)}</b></div>
  ${group('venue',pid?'가장 많이 소비한 업장':'매출 1위 업장',venues[0]?.label||'유료 소비 없음',venues.length?rcMoney(venues[0].amount)+(!pid&&sum?' · '+(100*venues[0].amount/sum).toFixed(1)+'%':''):'—',rankList(venues)+revAnalysisRowsHTML(paid.filter(r=>r.venue===venues[0]?.label)))}
  ${group('product',pid?'가장 많이 소비한 상품':'매출 상위 상품',products[0]?.label||'구매 기록 없음',products.length?rcMoney(products[0].amount):'—',rankList(products)+revAnalysisRowsHTML(paid.filter(r=>products.slice(0,3).some(g=>g.label===r.product))))}
  ${group('event','행사 참여·직접 소비',pid?'참여 '+eventCount+'건':'참여 고객 '+participants.size+'명',rcMoney(eventAmount),`<p>선택 시나리오: ${esc(scenarioLabel)}</p><p>행사 상품·행동에 직접 연결된 기록만 집계합니다. 같은 날짜의 다른 소비는 제외합니다. 별도 가상 주문 투영은 참여 인원에서 제외합니다.</p>${events.length?revAnalysisRowsHTML(events):'<p>직접 참여·거래 연결 기록 없음 · 실제 미참여를 별도로 추정하지 않음</p>'}`)}
  ${group('benefits','포함 혜택·무료 이용','포함 '+included.length+'건 · 무료 '+free.length+'건','추가 결제 0원',included.length+free.length?revAnalysisRowsHTML([...included,...free]):'<p>현재 원장에 기록된 포함·무료 이용 없음</p>')}
  ${group('checks','거래·가격 확인 사항',flagged.length+issues.length?'확인 '+(flagged.length+issues.length)+'건':'연결 이상 기록 없음','',`<p>참고·가정 가격 사용은 계산 오류와 구분합니다.</p>${revRank(flagged,r=>revPriceClass(r)).map(g=>`<div class="rev-summary-line"><span>${esc(g.label)}</span><span>${rcMoney(g.amount)}</span></div>`).join('')}${issues.length?`<p>이 범위의 주문·원장 검사 ${issues.length}건 확인 필요</p>`:''}${unscoped?`<p>고객이 특정되지 않은 실행 전체 검사 ${unscoped}건 · 개인 오류로 단정하지 않음</p>`:''}${revAnalysisRowsHTML(flagged)}`)}
  <p class="rev-analysis-foot">가상 소비의 구성입니다. 실제 매출·인과 효과가 아닙니다.</p></div>`;
}
function revTransactionsState(L) {
  if(!REV.transactions||REV.transactions.runId!==L.run_id)REV.transactions={runId:L.run_id,customer:'',venue:'',date:'',type:'',page:0};return REV.transactions;
}
function revTransactionsTableHTML(L) {
  const st=revTransactionsState(L),all=revAllRows(L),rows=all.filter(r=>(!st.customer||r.customer_id===st.customer)&&(!st.venue||r.venue===st.venue)&&(!st.date||r.visit_date===st.date)&&(!st.type||revRowClass(r)===st.type));
  const size=25,pages=Math.max(1,Math.ceil(rows.length/size));st.page=Math.min(st.page,pages-1);
  const option=(key,label,values)=>`<label>${label}<select data-rev-table-filter="${key}" aria-label="거래 ${label}"><option value="">전체</option>${values.map(([value,text])=>`<option value="${esc(value)}"${st[key]===value?' selected':''}>${esc(text)}</option>`).join('')}</select></label>`;
  const chosen=all.find(r=>r.row_id===REV.rollRow),counts=Object.fromEntries(['PAID_PRICED','FREE','INCLUDED','UNRESOLVED'].map(k=>[k,all.filter(r=>revRowClass(r)===k).length]));
  return `<div class="rev-table-summary">전체 ${all.length}건 · 유료 ${counts.PAID_PRICED}건 · 무료 ${counts.FREE}건 · 포함 혜택 ${counts.INCLUDED}건${counts.UNRESOLVED?' · 미산정 '+counts.UNRESOLVED+'건':''}</div><div class="rev-table-filters">${option('customer','고객',Object.keys(L.receipts).map(id=>[id,dno(id)]))}${option('venue','업장',[...new Set(all.map(r=>r.venue))].sort().map(v=>[v,v]))}${option('date','날짜',[...new Set(all.map(r=>r.visit_date).filter(Boolean))].sort().map(v=>[v,v]))}${option('type','거래 구분',[['PAID_PRICED','유료'],['FREE','무료 이용'],['INCLUDED','포함 혜택'],['UNRESOLVED','미산정']])}</div><p class="rev-table-mobile-hint">표를 가로로 밀면 수량·금액·거래 구분을 볼 수 있습니다.</p><div class="rev-table-scroll"><table class="rev-transactions-table"><thead><tr><th>일시</th><th>고객</th><th>업장</th><th>상품·활동</th><th>수량</th><th class="rev-number">금액</th><th>구분</th></tr></thead><tbody>${rows.slice(st.page*size,(st.page+1)*size).map(r=>`<tr data-rev-row="${esc(r.row_id)}" tabindex="0" class="${REV.rollRow===r.row_id?'on':''}"><td>${esc(r.visit_date||'일자 미기록')}<small>${esc(r.time||'숙박')}</small></td><td>${esc(dno(r.customer_id))}</td><td>${esc(r.venue)}</td><td><button class="cf-link" data-rev-table-select="${esc(r.row_id)}">${esc(r.product)}</button>${revIsProjection(r)?'<small>별도 가상 주문 투영</small>':''}</td><td>${esc(String(r.billing_quantity??r.quantity??'미확인'))}<small>${esc(r.billing_unit||r.unit_basis||'단위 미기록')}</small></td><td class="rev-number"><b>${revBoardAmount(r)}</b></td><td>${esc(revTypeLabel(r))}<small>${r.paid_krw>0?esc(revPriceClass(r)):''}</small></td></tr>`).join('')||'<tr><td colspan="7">조건에 맞는 거래가 없습니다.</td></tr>'}</tbody></table></div><div class="rev-table-pagination"><span>필터 ${rows.length}건 / 원장 ${all.length}건 · ${st.page+1} / ${pages}쪽</span><div><button class="cf-btn" data-rev-table-page="-1"${st.page===0?' disabled':''}>이전</button><button class="cf-btn" data-rev-table-page="1"${st.page+1>=pages?' disabled':''}>다음</button></div></div>${chosen?`<div class="rev-table-selection"><b>${esc(dno(chosen.customer_id))} · ${esc(chosen.product)} · ${revBoardAmount(chosen)}</b><p>${esc(chosen.price_basis||'가격 근거 미기록')} · ${esc(revPriceClass(chosen))}</p>${revRoomReferenceHTML(chosen)}${chosen.act==='room_night'?'<p>객실박 거래 · 별도 행동 선택 없음</p>':`<button class="cf-link" data-rev-ux-evidence="${esc(chosen.row_id)}">이 거래의 정밀 근거 →</button>`}</div>`:''}`;
}
function revAnalysisWire(root) {
  root.querySelectorAll('[data-analysis-group]').forEach(el=>el.ontoggle=()=>{if(!el.isConnected)return;if(el.open)REV.analysisExpanded.add(el.dataset.analysisGroup);else REV.analysisExpanded.delete(el.dataset.analysisGroup);});
  const customer=root.querySelector('#revAnalysisCustomer');if(customer)customer.onchange=()=>{REV.analysisCustomer=customer.value;revRender();};
  root.querySelectorAll('[data-rev-table-filter]').forEach(el=>el.onchange=()=>{const st=revTransactionsState(REV.ledger);st[el.dataset.revTableFilter]=el.value;st.page=0;revRender();});
  root.querySelectorAll('[data-rev-table-page]').forEach(el=>el.onclick=()=>{revTransactionsState(REV.ledger).page+=Number(el.dataset.revTablePage);revRender();});
  root.querySelectorAll('[data-rev-table-select]').forEach(el=>el.onclick=e=>{e.stopPropagation();REV.rollRow=el.dataset.revTableSelect;revRender();});
  root.querySelectorAll('.rev-transactions-table tr[data-rev-row]').forEach(el=>el.onkeydown=e=>{if(e.key==='Enter'){REV.rollRow=el.dataset.revRow;revRender();}});
}

// Extend precise evidence only; preserve v3 narrative and all existing sections.
if(typeof bhEvidenceHTML==='function'){
 const revenueOriginalEvidence=bhEvidenceHTML;
 bhEvidenceHTML=function(m,c){
  const html=revenueOriginalEvidence(m,c),flow=m.flow?.result||m.flow,scene=flow?.plans?.[c.customer_id]?.scenes?.[c.scene_index],decision=scene?.basis?.menu_decision;
  if(!decision)return html;
  const tpl=document.createElement('template');tpl.innerHTML=html;const target=tpl.content.querySelector('.ux-evidence-candidates');if(!target)return html;
  const selected=decision.candidates?.find(p=>p.candidate_id===decision.selected),contract=scene.basis.charge?.sku_contract;
  const money=tpl.content.querySelector('.ux-evidence-money');if(money&&(m.rows||[]).length>1){const note=document.createElement('small');note.textContent='이 행동 주문 합계 '+rcMoney(m.rows.reduce((n,r)=>n+(r.paid_krw||0),0))+' · 선택한 L5 구성품 금액과 구분';money.appendChild(note);}
  target.insertAdjacentHTML('beforeend',`<details class="rev-menu-decision"><summary>업장 선택 후 메뉴 결정 · ${esc(decision.status)}</summary><p>업장 선택을 유지하고 적격 메뉴를 비교한 규칙 판단입니다. 이 단계의 LLM 호출은 없습니다.</p>${decision.unspecified_meal_model?'<p>실제 적격 단품이 확인되지 않아 기존 같은 업장의 단가를 참조한 가상 식사 주문입니다. 최소 2인 코스를 1인 주문한 것으로 처리하지 않습니다.</p>':''}<p>${esc(contract?.label||'적격 메뉴 미확정')} · ${rcMoney(scene.basis.charge?.krw)}</p><p>인원·수량: ${esc(decision.party_assumption?.source||'기존 방문 조건')} · 어린이 연령이 없으면 실제 연령을 확정하지 않습니다.</p>${selected?`<p>선택 메뉴 점수 ${Number(selected.score).toFixed(2)} · 후보 ${decision.candidates.length}개</p>`:''}<ul>${(contract?.components||[]).map(p=>`<li>${esc(p.label)}${/UNKNOWN-CHILD-MODEL/.test(p.sku_id)?' (어린이 연령 미확인 · 성인 단가 가정)':''} × ${p.billing_quantity} · ${rcMoney(p.unit_price_krw)} / ${esc(p.billing_unit)} · ${esc(p.source_grade==='△'&&p.price_tier==='EXISTING_REFERENCE'?'시뮬레이션 가정':({OFFICIAL:'확인 출처',EXISTING_REFERENCE:'과거 참고',COMPARABLE_ESTIMATE:'비교 추정',SIMULATION_ASSUMPTION:'시뮬레이션 가정'})[p.price_tier]||p.price_tier)}</li>`).join('')}</ul><details><summary>메뉴 후보와 실제 평가 항목</summary>${(decision.candidates||[]).map(p=>`<p>${esc(p.sku_contract?.label||p.candidate_id)} · ${Number(p.score).toFixed(2)} · ${(p.terms||[]).map(t=>esc(t.factor||t.name||t.key||'평가 항목')+' '+esc(String(t.value))).join(' / ')}</p>`).join('')}</details></details>`);
  return tpl.innerHTML;
 };
}

// Immutable L5 only. No price lookup and no amount inferred from a venue label.
function revSceneConsumptionRows(flow,pid,sc) {
  const day=sc.visit_day||1,time=String(Math.floor(sc.t0/60)).padStart(2,'0')+':'+String(sc.t0%60).padStart(2,'0');
  return (flow?.ledger?.receipts?.[pid]?.rows||[]).filter(r=>(r.visit_day||1)===day&&r.time===time&&r.act===sc.act&&(!r.selection_id||!sc.basis?.selection_id||r.selection_id===sc.basis.selection_id));
}
function revSceneConsumptionHTML(flow,pid,sc) {
  const rows=revSceneConsumptionRows(flow,pid,sc);if(!rows.length)return '';
  const states=rows.map(revRowClass);if(states.every(s=>s==='NO_PURCHASE'))return '';
  const total=rows.reduce((s,r)=>s+(r.paid_krw||0),0),n=(flow?.result||flow)?.visits?.[pid]?.party_size;
  const unknown=states.includes('UNRESOLVED'),scope=n>1?`일행 ${n}명 전체`:n===1?'개인 소비':'과금 인원 미기록';
  const line=r=>`<li><span>${esc(r.sku_contract?.venue_id==='THE_BUFFET'?({ADULT:'성인',UNKNOWN_CHILD_FARE:'연령 미확정 동행 · 성인 요금 가정',CHILD:'어린이',INFANT:'36개월 미만 유아',ADULT_TARIFF_SECONDARY:'성인 요금 대상 청소년'})[r.sku_contract.party_cohort]||r.product:r.product)}</span><small>${r.amount_status==='UNKNOWN'?'금액 미산정':r.unit_price_krw==null?'단가 미기록':`${Number(r.unit_price_krw).toLocaleString('ko-KR')}원 × ${esc(String(r.billing_quantity??r.quantity??'수량 미기록'))}`}${revRowClass(r)==='INCLUDED'?' · 포함 혜택 · 추가 결제 0원':revRowClass(r)==='FREE'?' · 무료 이용':''}${r.sku_contract?.party_cohort==='UNKNOWN_CHILD_FARE'?' · 연령 미확정 요금 가정':''}</small></li>`;
  const amount=r=>r.amount_status==='UNKNOWN'?'미산정':Number(r.paid_krw||0).toLocaleString('ko-KR')+'원';
  const discounts=rows.every(r=>r.discount_krw!=null)?rows.reduce((n,r)=>n+Number(r.discount_krw),0):null;
  const priceText=r=>({'확인 출처':'확인된 상품 출처의 가격을 사용한 가상 주문','과거 참고':'기존 상품 참고가를 사용한 가상 주문','비교 추정':'유사 상품 비교가를 사용한 가상 주문','가정 단가':'시나리오 가정 단가를 사용한 가상 주문'})[revPriceClass(r)]||revPriceClass(r);
  const unit=r=>({person:'1인',portion:'인분',order:'주문',set:'세트',cup:'잔',glass:'잔',bottle:'병',piece:'개',night:'박',pizza:'판'})[r.billing_unit||r.sku_contract?.billing_unit]||'판매 단위 별도 기록 확인';
  return `<section class="frp-scene-consumption" data-consumption-run="${esc(flow.ledger.run_id)}"><div class="frp-consumption-head"><span>이번 장면의 소비</span><strong>${unknown&&total===0?'금액 미산정':total.toLocaleString('ko-KR')+'원'}</strong></div><small>${esc([...new Set(rows.map(r=>r.venue).filter(Boolean))].join(' · '))} · ${scope}</small><ul>${rows.slice(0,2).map(line).join('')}</ul>${rows.length>2?`<details class="frp-consumption-more"><summary>나머지 ${rows.length-2}개 항목 펼침</summary><ul>${rows.slice(2).map(line).join('')}</ul></details>`:''}<div class="ev-receipt-totals"><span>할인</span><span>${discounts==null?'별도 기록 없음':discounts.toLocaleString('ko-KR')+'원'}</span><span>추가 결제</span><b>${unknown&&total===0?'미산정':total.toLocaleString('ko-KR')+'원'}</b></div>${unknown?'<small>미산정 항목은 합계 제외 · 무료 이용과 구분</small>':''}${rows.some(r=>r.row_id)?`<details class="frp-transaction-detail"><summary>가격·거래 근거 자세히 보기</summary>${rows.map(r=>`<article data-l5-row="${esc(r.row_id||'')}"><b>${esc(r.product)}</b><dl><div><dt>업장 · 일시</dt><dd>${esc(r.venue||'')}<br>${esc(r.visit_date||'')} ${esc(r.time||'')}</dd></div><div><dt>수량 · 단가</dt><dd>${esc(String(r.billing_quantity??r.quantity??'미기록'))} ${esc(unit(r))} · ${r.unit_price_krw==null?'단가 미기록':Number(r.unit_price_krw).toLocaleString('ko-KR')+'원'}</dd></div><div><dt>할인</dt><dd>${r.discount_krw==null?'별도 기록 없음':Number(r.discount_krw).toLocaleString('ko-KR')+'원'}</dd></div><div><dt>결제 반영액</dt><dd>${amount(r)} · ${esc(revTypeLabel(r))}</dd></div></dl><p class="ev-price-note">${esc(priceText(r))}</p></article>`).join('')}</details>`:''}</section>`;
}
