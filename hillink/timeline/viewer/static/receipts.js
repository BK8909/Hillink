// Same-run L5 receipts. Money comes from the server, never from UI estimates.
const RC = { open: new Set(), demo: new Map(), errors: new Map(), ab: new Map(), abPending: new Set() };
const rcMoney = n => n == null ? "금액 미확인" : `${Number(n).toLocaleString("ko-KR")}원`;
const rcDelta = n => `${n > 0 ? "+" : n < 0 ? "−" : ""}${rcMoney(Math.abs(n))}`;
const rcVenueName = name => name === "IRD" ? "룸서비스" : name;
const rcSource = ledger => ledger.source === "stored_demo" ? "저장 시연 영수증" : "실제 엔진 실행 결과";
function rcRowAmount(r) {
  return r.status === "금액 미확인" ? (r.assumption_addition_krw ? `가정 ${rcMoney(r.assumption_addition_krw)}` : "금액 미확인") : rcMoney(r.paid_krw);
}
const rcRevenueAction = () => `<div class="rc-action"><button type="button" class="cf-btn cf-primary" data-rc-revenue>이 결과로 매출 집계 보기 →</button></div>`;
// Native billing quantities are separate from engine row multiplicity and party size.
function rcQuantityView(row) {
  const contract=row.sku_contract||{},unknown=row.status==='금액 미확인'||row.amount_status==='UNKNOWN'||row.purchase_status==='UNKNOWN_AMOUNT';
  const unit=u=>({cup:'잔',person:'인분',portion_meal:'인분',set:'세트',order:'건',room_night:'객실박'})[u]||u||'단위 미확인';
  const clean=text=>{let name=String(text||'품목').replace(/\s*·\s*기존 메뉴 기준 가상 계산.*$/,'');if(row.venue&&name.startsWith(row.venue+' '))name=name.slice(row.venue.length+1);return name;};
  const parts=(contract.components&&contract.components.length?contract.components:contract.sku_id&&contract.billing_quantity!=null?[contract]:[]).map(c=>({label:clean(c.label),quantity:c.billing_quantity??null,unit:unit(c.billing_unit),unit_price_krw:c.unit_price_krw??null,source_line:c.source_line??null}));
  const orderUnit=row.billing_unit||contract.billing_unit,orderQuantity=row.billing_quantity??contract.billing_quantity;
  return {unknown,parts,order_count:['order','건'].includes(orderUnit)&&Number.isInteger(orderQuantity)?orderQuantity:null,explicit:contract.order_quantity_basis==='EXPLICIT_VIRTUAL_ORDER_QUANTITY_NOT_GUEST_COUNT'&&contract.input_provenance==='EXPLICIT_VIRTUAL_VISIT_NOT_OBSERVED_REVIEW_FACT'};
}
function rcQuantityHTML(row) {
  const q=rcQuantityView(row);
  if(q.unknown)return '<div class="rc-quantity"><b>주문 수량·금액 미확인</b><p class="rc-note">미지정 정보는 무료 이용이나 판매수량 1로 처리하지 않습니다.</p></div>';
  return `<div class="rc-quantity">${q.parts.length?q.parts.map(p=>`<div class="rc-quantity-item"><b>${esc(p.label)} · ${p.quantity==null?'수량 미확인':p.quantity+esc(p.unit)}</b>${p.quantity!=null&&p.unit_price_krw!=null?`<p>${rcMoney(p.unit_price_krw)} × ${p.quantity}${esc(p.unit)} = ${rcMoney(p.unit_price_krw*p.quantity)}</p>`:''}</div>`).join(''):'<p class="rc-note">이 거래의 품목별 판매수량은 미확인입니다.</p>'}${q.order_count!=null?`<small>주문 ${q.order_count}건 · 품목 수량과 구분</small>`:''}<p class="rc-note">${q.explicit?'수량 근거: 이번 방문에 명시한 가상 주문':'수량 근거: 저장된 상품·가격 계약'}</p></div>`;
}
function rcNativeRowScene(flow,row) {
  const data=flow&&(flow.result||flow),plan=data&&data.plans&&data.plans[row.customer_id];if(!plan)return null;
  const matches=plan.scenes.map((scene,index)=>({scene,index})).filter(({scene})=>(scene.visit_day||1)===(row.visit_day||1)&&scene.act===row.act&&agHM(scene.t0)===row.time);
  if(matches.length!==1)return null;const found=matches[0],m4=found.scene.basis&&found.scene.basis.m4||{};
  return {...found,native_event_id:m4.event_id||null,native_packet_ids:m4.decision_packet_ids||[]};
}
function rcTransactionHTML(L,row,flow) {
  const q=rcQuantityView(row),native=rcNativeRowScene(flow,row),why=native&&typeof agBRExplain==='function'?agBRExplain(flow,row.customer_id,native.index):null,receipt=L.receipts[row.customer_id];
  const conditions=flow.result&&flow.result.visit&&flow.result.visit.resolved_conditions&&flow.result.visit.resolved_conditions[row.customer_id];
  return `<div class="u06-transaction"><h3>${esc(q.unknown&&row.act==='cafe'?'카페 주문':row.product.replace(/\s*·\s*기존 메뉴 기준 가상 계산.*$/,''))}</h3><strong>${q.unknown?'금액 미확인':rcMoney(row.paid_krw)}</strong><p class="rc-visit-scope">선택 고객 1팀 · 방문 설정 ${receipt.party_size??conditions?.party_size??'미확인'}명${q.order_count!=null?' · 주문 '+q.order_count+'건':''}</p>${rcQuantityHTML(row)}<p class="rc-note">${esc(row.visit_date||'')} ${esc(row.time||'숙박')} · ${esc(row.department||'분류 미확인')} / ${esc(row.venue)}</p>${why?`<section class="rc-choice-reason"><h4>이 장소를 고른 이유</h4><p>${why.sentences.map(esc).join(' ')}</p></section>`:''}<details class="rc-transaction-source"><summary>가격·입력·식별 정보</summary><p>${esc(row.price_basis||'가격 근거 미기록')}</p><pre>${esc(JSON.stringify({run_id:L.run_id,visit_id:row.visit_id,ledger_tx_id:row.row_id,native_event_id:native&&native.native_event_id,native_packet_ids:native&&native.native_packet_ids,engine_row_quantity:row.quantity,quantity_role:row.quantity_role,billing_quantity:row.billing_quantity,billing_unit:row.billing_unit,price_status:row.price_status||row.price_source_status,sku_contract:row.sku_contract||null,resolved_conditions:conditions||null},null,2))}</pre></details><button class="cf-btn" id="u06RowAction">${row.act==='room_night'?'방문 조건 보기':'해당 행동·근거 보기'} →</button></div>`;
}
function rcReceiptHTML(ledger, pid, comparison, withRevenue = false) {
  if (withRevenue && typeof agU06ReceiptHTML === "function") return agU06ReceiptHTML(ledger, pid, comparison);
  const r = ledger && ledger.receipts && ledger.receipts[pid];
  if (!r) return "";
  const receiptTitle = ledger.visit ? "체류 전체 소비 내역" : "하루 소비 내역";
  const key = `${ledger.run_id}|${pid}`, paid = new Map();
  r.rows.filter(x => x.paid_krw > 0).forEach(x => { const a = paid.get(x.venue) || { amount: 0, items: [] }; a.amount += x.paid_krw; a.items.push(x.product); paid.set(x.venue, a); });
  const free = r.rows.filter(x => ["무료", "포함"].includes(x.status)).length;
  const noPurchase = (r.actions || []).filter(x => x.purchase_status === "NO_PURCHASE" || (x.considered || []).length || (x.blocked || []).length);
  return `<section class="rc-receipt" data-rc-p="${esc(pid)}"><div class="cf-sh"><h3>${receiptTitle}</h3><span class="cf-sub">${esc(dno(r.customer_id))} · ${r.party_size}인</span></div>
    <p class="rc-source">${esc(rcSource(ledger))} · 실제 고객의 결제 기록이 아닙니다</p>
    <dl class="rc-totals"><div class="rc-main"><dt>시뮬레이션 결제액</dt><dd>${rcMoney(r.paid_krw)}</dd></div>
      <div><dt>객실 요금 가정</dt><dd>+${rcMoney(r.assumption_addition_krw)}</dd></div><div><dt>가정 포함 금액</dt><dd>${rcMoney(r.with_assumptions_krw)}</dd></div></dl>
    <ul class="rc-summary">${[...paid.entries()].sort((a,b) => b[1].amount-a[1].amount).map(([v,x]) => `<li><span>${esc(rcVenueName(v))}</span><b>${rcMoney(x.amount)}</b></li>`).join("")}${free ? `<li><span>무료 · 포함 이용 ${free}건</span><span>추가 결제 없음</span></li>` : ""}</ul>
    ${r.unknown_count ? `<p class="rc-note">금액 미확인 ${r.unknown_count}건은 기본 결제액에서 제외했습니다.</p>` : ""}
    <details class="rc-detail" data-rc-open="${esc(key)}"${RC.open.has(key) ? " open" : ""}><summary>이용 · 가격 근거 자세히 보기</summary>
      <ol>${r.rows.map(x => `<li><div class="rc-item-head"><span>${esc(x.time || "숙박")} · ${esc(rcVenueName(x.venue))}</span><b>${rcRowAmount(x)}</b></div><p>${esc(x.product)}</p>
        <div class="rc-meta">${esc(x.status)} · 수량 ${x.quantity} · ${esc(x.unit_basis || "단위 미확인")}${x.unit_price_krw != null ? ` · 단가 ${rcMoney(x.unit_price_krw)}` : ""}</div>
        <details><summary>가격 근거${x.turn ? " · 판단 연결" : ""}</summary><p>${esc(x.price_basis || "가격 근거 미확인")}</p>${x.notes.map(n => `<p class="rc-note">${esc(n)}</p>`).join("")}
          <p class="rc-meta">${esc(x.product_id || "상품 코드 미확인")}${x.price_grade ? ` · 가격 등급 ${esc(x.price_grade)}` : ""}</p>
          ${x.turn ? `<button type="button" class="cf-link" data-rc-turn="${esc(x.turn)}" data-rc-id="${esc(pid)}">이 선택의 판단 근거</button>` : ""}</details></li>`).join("")}</ol>
    </details>${noPurchase.length ? `<details class="rc-detail"><summary>소비로 계산되지 않은 행동·대안 ${noPurchase.length}건</summary><p class="rc-note">방문 행동과 선택하지 않은 후보는 구매 행 및 매출 합계에 포함하지 않습니다.</p><ul class="rc-summary">${noPurchase.map(a => `<li><span>${esc(a.time || "")} · ${esc(a.label || a.action || "행동")}</span><small>${esc(a.purchase_status === "NO_PURCHASE" ? "구매 없음" : "대안 · 소비 미발생")}</small></li>${[...(a.considered || []), ...(a.blocked || [])].map(x => `<li><span>${esc(x.label || "대안")}</span><small>${esc(x.reason || "선택하지 않음")}</small></li>`).join("")}`).join("")}</ul></details>` : ""}${typeof rcComparisonHTML === "function" ? rcComparisonHTML(pid, ledger, comparison) : ""}${rcABHTML(ledger, pid)}${withRevenue ? rcRevenueAction() : ""}</section>`;
}
function rcWire(root, onDecision) {
  root.querySelectorAll("[data-rc-revenue]").forEach(b => b.onclick = rcOpenRevenue);
  root.querySelectorAll("[data-rc-ab]").forEach(b => b.onclick = () => rcRunAB(b.dataset.rcAb));
  root.querySelectorAll("[data-rc-open]").forEach(x => x.ontoggle = () => x.open ? RC.open.add(x.dataset.rcOpen) : RC.open.delete(x.dataset.rcOpen));
  root.querySelectorAll("[data-rc-turn]").forEach(b => b.onclick = () => {
    if (onDecision) { onDecision(b.dataset.rcId, b.dataset.rcTurn); return; }
    const i = AG.runs.findIndex(r => r.turn === b.dataset.rcTurn && r.customers.some(c => c.persona_id === b.dataset.rcId));
    if (i >= 0) agChoiceDrawer(b.dataset.rcId, i);
  });
}
function rcABHTML(ledger, pid) {
  if (!ledger || ledger.source !== "live_engine" || !AG.flow || !AG.flow.request || AG.flow.ledger.run_id !== ledger.run_id) return "";
  const request = AG.flow.request;
  const supported = (request.intervention || "none") === "none";
  const pair = RC.ab.get(ledger.run_id);
  const pending = RC.abPending.has(ledger.run_id);
  const button = supported ? `<button type="button" class="cf-btn" data-rc-ab="${esc(ledger.run_id)}"${pending ? " disabled" : ""}>${pending ? "반대 행사 조건 계산 중…" : "행사 없음 ↔ 와인페어 비교"}</button>` : `<p class="rc-note">현재 개입 조건에서는 행사만 바꾼 비교를 만들 수 없습니다.</p>`;
  if (!pair) return `<section class="rc-ab"><h4>같은 고객 상황 A/B 비교</h4><p class="rc-note">현재 실제 실행과 동일한 고객·방문 조건·시드에서 행사 조건만 바꿔 다시 계산합니다.</p>${button}</section>`;
  if (pair.error) return `<section class="rc-ab"><h4>같은 고객 상황 A/B 비교</h4><p class="rc-note">비교를 완료하지 못했습니다: ${esc(pair.error)}</p>${button}</section>`;
  const c = pair.comparison && pair.comparison.customers && pair.comparison.customers[pid];
  if (!c) return `<section class="rc-ab"><h4>같은 고객 상황 A/B 비교</h4><p class="rc-note">선택 고객의 두 실행 결과를 비교할 수 없습니다.</p>${button}</section>`;
  const currentIsOff = !pair.current_event;
  const off = currentIsOff ? pair.current : pair.other, on = currentIsOff ? pair.other : pair.current;
  const offRow = off.receipts[pid], onRow = on.receipts[pid];
  const changes = c.row_changes || [];
  const actions = c.activity_changes || [];
  const venueChanges = c.venues || [];
  return `<section class="rc-ab"><h4>같은 고객 상황 A/B 비교</h4><p class="rc-note">고객·프로필 지문·시드·방문 조건은 같고 행사 조건만 바꿔 각각 실제 계산했습니다.</p>
    <table class="rc-compare-table"><thead><tr><th>${ledger.visit ? "체류 전체" : "하루"}</th><th>행사 없음</th><th>와인페어</th><th>차이</th></tr></thead><tbody><tr><th>시뮬레이션 결제액</th><td>${rcMoney(offRow.paid_krw)}</td><td>${rcMoney(onRow.paid_krw)}</td><td>${rcDelta(onRow.paid_krw-offRow.paid_krw)}</td></tr></tbody></table>
    <p class="rc-note">${c.changed ? `행동 ${actions.length}건 · 소비 행 ${changes.length}건이 달라졌습니다.` : "변화 없음 · 두 조건의 행동과 소비가 같습니다."}</p>
    ${venueChanges.length ? `<details><summary>업장별 소비 차이 ${venueChanges.length}건 보기</summary><ul class="rc-summary">${venueChanges.map(x => `<li><span>${esc(x.venue)}</span><small>${rcMoney(x.before_krw)} → ${rcMoney(x.after_krw)} · ${rcDelta(x.delta_krw)}</small></li>`).join("")}</ul></details>` : ""}
    ${actions.length ? `<details><summary>달라진 행동 ${actions.length}건 보기</summary><ul class="rc-transitions">${actions.map(x => `<li>${esc(x.slot)} · ${esc((x.before || {}).label || "없음")} → ${esc((x.after || {}).label || "없음")}</li>`).join("")}</ul></details>` : ""}
    ${changes.length ? `<details><summary>달라진 소비 행 ${changes.length}건 보기</summary><ol>${changes.map(x => { const old = x.before, next = x.after, r = next || old; return `<li><div class="rc-item-head"><span>${esc(r.time || r.slot || "행동")} · ${esc(rcVenueName(r.venue || ""))}</span><b>${rcDelta(x.delta_krw)}</b></div><p>${old ? `${esc(old.product)} (${esc(old.status)})` : "없음"} → ${next ? `${esc(next.product)} (${esc(next.status)})` : "없음"}</p><div class="rc-meta">${[...new Set([...(x.before_fact_ids || []), ...(x.after_fact_ids || [])])].length ? `근거 ID ${esc([...new Set([...(x.before_fact_ids || []), ...(x.after_fact_ids || [])])].join(" · "))}` : "직접 연결된 사실 ID 없음"}</div>${r.turn ? `<button type="button" class="cf-link" data-rc-turn="${esc(r.turn)}" data-rc-id="${esc(pid)}">이 선택의 판단 근거</button>` : ""}</li>`; }).join("")}</ol></details>` : ""}
    ${button}</section>`;
}
async function rcRunAB(runId) {
  const flow = typeof AG !== "undefined" && AG.flow;
  if (!flow || !flow.ledger || flow.ledger.run_id !== runId || !flow.request || (flow.request.intervention || "none") !== "none") return;
  if (RC.abPending.has(runId)) return;
  RC.abPending.add(runId); rcMountPanel();
  try {
    const isVisit = !!flow.ledger.visit;
    const currentEvent = flow.request.event_mode ? flow.request.event_mode === "wine" : Boolean(flow.request.event);
    const otherEvent = !currentEvent;
    const request = isVisit
      ? { personas: flow.request.personas, duration: flow.request.duration, start_date: flow.request.start_date,
          seed: flow.request.seed, event_mode: otherEvent ? "wine" : "none", include_ledger: true,
          ...(flow.request.package_id ? { package_id: flow.request.package_id } : {}) }
      : { ...flow.request, event: otherEvent, include_ledger: true };
    const otherResult = await api(isVisit ? "/api/visit" : "/api/flow", request);
    if (otherResult.error || !otherResult.ledger || otherResult.ledger.source !== "live_engine") throw new Error(otherResult.error || "실제 엔진 영수증이 없습니다");
    const comparison = await api("/api/ledger/compare", {
      baseline_id: currentEvent ? otherResult.ledger.run_id : flow.ledger.run_id,
      scenario_id: currentEvent ? flow.ledger.run_id : otherResult.ledger.run_id,
      event_only: true
    });
    if (!comparison.comparable) throw new Error(comparison.message || "같은 조건의 비교 결과가 아닙니다");
    const offLedger = currentEvent ? otherResult.ledger : flow.ledger;
    const onLedger = currentEvent ? flow.ledger : otherResult.ledger;
    if (typeof revRememberAB === "function") revRememberAB(offLedger, onLedger, comparison);
    RC.ab.set(runId, { current: flow.ledger, other: otherResult.ledger, comparison, current_is_baseline: true, current_event: currentEvent });
  } catch (e) { RC.ab.set(runId, { error: e.message, current_is_baseline: true, current_event: flow.request.event_mode ? flow.request.event_mode === "wine" : Boolean(flow.request.event) }); }
  finally { RC.abPending.delete(runId); rcMountPanel(); }
}
function rcOpenRevenue() {
  if(window.HLNav?.active())return HLNav.go("revenue");
  const navigation=typeof BH==='undefined'?0:(BH.navToken||0);
  const flow = typeof AG !== "undefined" && AG.flow;
  if (!flow || !flow.ledger || !flow.result || !flow.request) return;
  revRememberFlow({ ...flow.result, ledger: flow.ledger }, flow.request);
  REV.enteredLatest = null;
  const main = document.querySelector("main");
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (main && !reduce) main.classList.add("rev-transition-origin");
  const enter = () => {
    if (main) main.classList.remove("rev-transition-origin");
    if (navigation !== (typeof BH === 'undefined' ? 0 : (BH.navToken || 0))) return; // a later header navigation wins
    REV.transitionDispatch = true;
    setMode("opx");
    REV.transitionDispatch = false;
    REV.animateEntry = !reduce;
  };
  if (reduce) enter();
  else window.setTimeout(enter, 150);
}
function rcCohortHTML(ledger) {
  const total=ledger.totals,free=Object.values(ledger.receipts).flatMap(r=>r.rows).filter(r=>['FREE_USE','PACKAGE_INCLUDED'].includes(r.purchase_status));
  return `<section class="frp-section frp-spend frp-cohort-spend" data-cohort-section="spend"><div class="frp-spend-heading"><h3>${ledger.visit?'체류 전체':'하루'} 가상 소비</h3><strong>${rcMoney(total.paid_krw)}</strong><small>현재 실행 전체 ${ledger.team_count}팀 · 가상 실행 원장</small></div><div class="frp-department-list">${ledger.levels.L2.map(g=>`<div class="frp-department-line ${g.key[0]==='ROOM'?'room':g.key[0]==='F&B'?'fnb':g.key[0]==='레저'?'leisure':''}"><span><i aria-hidden="true"></i>${esc(g.key[0])}</span><b>${g.unknown_count&&!g.paid_krw?'금액 미확인':rcMoney(g.paid_krw)}</b></div>`).join('')}</div><p class="frp-use-count">무료·포함 이용 ${free.length}건 · 소비 합계와 별도</p>${total.unknown_count?`<p class="rc-note">금액 미확인 ${total.unknown_count}건은 합계에서 제외</p>`:''}<p class="frp-note">고객 1팀을 선택하면 같은 시각의 행동과 소비 상세를 봅니다.</p>${total.assumption_addition_krw?`<details><summary>가격 비교 가정</summary><p>기존 비교 가정 ${rcMoney(total.assumption_addition_krw)} · 결제 합계와 별도</p></details>`:''}${rcRevenueAction()}</section>`;
}
function rcMountPanel() {
  if (typeof AG === "undefined" || !AG.flow || !AG.res) return;
  const pid = AG.mode === "agents" ? AG.sel : AG.one;
  const panel = document.querySelector("#panel"); if (!panel) return;
  let mount = panel.querySelector("#rcReceipt");
  if (!mount) { mount = document.createElement("div"); mount.id = "rcReceipt"; panel.appendChild(mount); }
  if (AG.flow.ledger && JSON.stringify(agAllIds().slice().sort()) !== JSON.stringify(Object.keys(AG.flow.ledger.receipts).sort())) {
    mount.innerHTML = '<p class="rc-note" role="status">현재 지도와 연결된 소비 원장을 확인할 수 없습니다. 해당 저장 실행으로 돌아가 주세요.</p>'; return;
  }
  if (AG.flow.ledger) { mount.innerHTML = pid ? rcReceiptHTML(AG.flow.ledger, pid, undefined, true) : rcCohortHTML(AG.flow.ledger); rcWire(mount); return; }
  if (typeof DS !== "undefined" && DS.last && DS.last.hit && DS.last.key) {
    const key = DS.last.key, flow = AG.flow;
    mount.innerHTML = `<p class="rc-note">저장 시연의 영수증을 확인하고 있습니다.</p>`;
    if (!RC.demo.has(key)) RC.demo.set(key, api("/api/ledger/demo", { key }));
    RC.demo.get(key).then(ledger => { flow.ledger = ledger; if (flow.result) flow.result.ledger = ledger; if (typeof revRememberDemoLedger === "function") revRememberDemoLedger(ledger, key); if (AG.flow === flow) rcMountPanel(); }).catch(() => {
      if (AG.flow === flow) mount.innerHTML = `<p class="rc-note">저장 시연의 영수증을 불러오지 못했습니다. 실제 계산으로 다시 실행해 주세요.</p>`;
    });
  } else mount.innerHTML = `<p class="rc-note">이 실행의 영수증을 받지 못했습니다. 같은 조건으로 다시 실행해 주세요.</p>`;
}

RC.byCohort = new Map();
RC.comparison = null;
RC.compareToken = 0;
function rcContext(c) {
  const ph = { checkin: "체크인", mid: "연박 중간일", checkout: "체크아웃", visit: "당일 방문" };
  const building = { GRAND: "그랜드", VISTA: "비스타", DOUGLAS: "더글라스" };
  return [c.event ? "와인페어 있음" : "행사 없음", ph[c.phase], c.stay === false ? "비투숙" : building[c.building], c.party_size ? `${c.party_size}인` : ""].filter(Boolean).join(" · ");
}
function rcAcceptLedger(ledger) {
  if (!ledger || ledger.source !== "live_engine") { RC.comparison = null; return; }
  const cohort = Object.keys(ledger.receipts).sort().join("|") + `|${ledger.context.seed}`;
  const previous = RC.byCohort.get(cohort); RC.byCohort.set(cohort, ledger);
  if (previous && previous.run_id === ledger.run_id) return;
  if (previous) {
    const a = previous.context || {}, b = ledger.context || {};
    const changed = [...new Set([...Object.keys(a), ...Object.keys(b)])].filter(k => k !== "event" && JSON.stringify(a[k]) !== JSON.stringify(b[k]));
    if (changed.length || Boolean(a.event) === Boolean(b.event)) return;
  }
  RC.comparison = null; const token = ++RC.compareToken;
  if (!previous) return;
  api("/api/ledger/compare", { baseline_id: previous.run_id, scenario_id: ledger.run_id, event_only: true }).then(result => {
    if (token !== RC.compareToken) return;
    RC.comparison = result; rcMountPanel();
  }).catch(e => { if (token === RC.compareToken) { RC.comparison = { error: e.message, scenario_id: ledger.run_id }; rcMountPanel(); } });
}
function rcComparisonHTML(pid, ledger, suppliedComparison) {
  const comparison = suppliedComparison === undefined ? RC.comparison : suppliedComparison;
  if (!comparison || comparison.scenario_id !== ledger.run_id) return `<p class="rc-note">같은 고객·시드로 상황을 바꿔 다시 실행하면 직전 영수증과 비교합니다.</p>`;
  if (comparison.error || !comparison.comparable) return `<p class="rc-note">${esc(comparison.error || comparison.message)}</p>`;
  const c = comparison.customers[pid]; if (!c) return "";
  const rows = [{ name: "시뮬레이션 결제액", before_krw: c.before_krw, after_krw: c.after_krw, delta_krw: c.delta_krw }, ...c.departments];
  const labels = { selection: "선택 변화", price_condition: "가격·포함 조건 변화", time_rule: "시간 규칙 변화", interaction: "복합 변화 · 분류 미확정" };
  return `<section class="rc-comparison"><h4>상황을 바꾸면 이렇게 달라집니다</h4><p class="rc-note">직전: ${esc(rcContext(c.before_context))}<br>이번: ${esc(rcContext(c.after_context))}</p>
    <table class="rc-compare-table"><thead><tr><th>구분</th><th>직전 조건</th><th>이번 조건</th><th>차이</th></tr></thead><tbody>${rows.map(r => `<tr><th>${esc(r.name)}</th><td data-label="직전">${rcMoney(r.before_krw)}</td><td data-label="이번">${rcMoney(r.after_krw)}</td><td data-label="차이">${rcDelta(r.delta_krw)}</td></tr>`).join("")}</tbody></table>
    ${c.transitions.length ? `<ul class="rc-transitions">${c.transitions.map(t => `<li>${esc(rcVenueName(t.before_venue))} · ${esc(t.before_product)} → ${esc(rcVenueName(t.after_venue))} · ${esc(t.after_product)}</li>`).join("")}</ul>` : `<p class="rc-note">주요 식사·행사에서 업장·상품 전환이 확인되지 않았습니다.</p>`}
    <details><summary>금액 변화 분류</summary><ul class="rc-summary">${Object.entries(c.decomposition).map(([k,n]) => `<li><span>${labels[k]}</span><b>${rcDelta(n)}</b></li>`).join("")}</ul><p class="rc-note">${esc(comparison.caveat)}</p></details></section>`;
}
