// Same-run L5 receipts. Money comes from the server, never from UI estimates.
const RC = { open: new Set(), demo: new Map(), errors: new Map() };
const rcMoney = n => n == null ? "금액 미확인" : `${Number(n).toLocaleString("ko-KR")}원`;
const rcDelta = n => `${n > 0 ? "+" : n < 0 ? "−" : ""}${rcMoney(Math.abs(n))}`;
const rcVenueName = name => name === "IRD" ? "룸서비스" : name;
const rcSource = ledger => ledger.source === "stored_demo" ? "저장 시연 영수증" : "실제 엔진 실행 결과";
function rcRowAmount(r) {
  return r.status === "금액 미확인" ? (r.assumption_addition_krw ? `가정 ${rcMoney(r.assumption_addition_krw)}` : "금액 미확인") : rcMoney(r.paid_krw);
}
const rcRevenueAction = () => `<div class="rc-action"><button type="button" class="cf-btn cf-primary" data-rc-revenue>이 결과로 매출 집계 보기 →</button></div>`;
function rcReceiptHTML(ledger, pid, comparison, withRevenue = false) {
  const r = ledger && ledger.receipts && ledger.receipts[pid];
  if (!r) return "";
  const key = `${ledger.run_id}|${pid}`, paid = new Map();
  r.rows.filter(x => x.paid_krw > 0).forEach(x => { const a = paid.get(x.venue) || { amount: 0, items: [] }; a.amount += x.paid_krw; a.items.push(x.product); paid.set(x.venue, a); });
  const free = r.rows.filter(x => ["무료", "포함"].includes(x.status)).length;
  return `<section class="rc-receipt" data-rc-p="${esc(pid)}"><div class="cf-sh"><h3>하루 소비 내역</h3><span class="cf-sub">${esc(r.display_id)} · ${r.party_size}인</span></div>
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
    </details>${typeof rcComparisonHTML === "function" ? rcComparisonHTML(pid, ledger, comparison) : ""}${withRevenue ? rcRevenueAction() : ""}</section>`;
}
function rcWire(root, onDecision) {
  root.querySelectorAll("[data-rc-revenue]").forEach(b => b.onclick = rcOpenRevenue);
  root.querySelectorAll("[data-rc-open]").forEach(x => x.ontoggle = () => x.open ? RC.open.add(x.dataset.rcOpen) : RC.open.delete(x.dataset.rcOpen));
  root.querySelectorAll("[data-rc-turn]").forEach(b => b.onclick = () => {
    if (onDecision) { onDecision(b.dataset.rcId, b.dataset.rcTurn); return; }
    const i = AG.runs.findIndex(r => r.turn === b.dataset.rcTurn && r.customers.some(c => c.persona_id === b.dataset.rcId));
    if (i >= 0) agChoiceDrawer(b.dataset.rcId, i);
  });
}
function rcOpenRevenue() {
  const flow = typeof AG !== "undefined" && AG.flow;
  if (!flow || !flow.ledger || !flow.result || !flow.request) return;
  revRememberFlow({ ...flow.result, ledger: flow.ledger }, flow.request);
  REV.enteredLatest = null;
  setMode("opx");
}
function rcCohortHTML(ledger) {
  const total = ledger.totals;
  return `<section class="rc-receipt"><div class="cf-sh"><h3>하루 소비 내역</h3><span class="cf-sub">참여 고객 ${ledger.team_count}팀</span></div><p class="rc-source">${esc(rcSource(ledger))}</p><dl class="rc-totals"><div class="rc-main"><dt>시뮬레이션 결제액</dt><dd>${rcMoney(total.paid_krw)}</dd></div><div><dt>객실 요금 가정</dt><dd>+${rcMoney(total.assumption_addition_krw)}</dd></div><div><dt>가정 포함 금액</dt><dd>${rcMoney(total.with_assumptions_krw)}</dd></div></dl><p class="rc-note">${Object.values(ledger.receipts).map(r => esc(r.display_id)).join(" · ")}</p><p class="rc-note">고객을 선택하면 해당 고객의 상세 소비 내역을 확인할 수 있습니다.</p>${rcRevenueAction()}</section>`;
}
function rcMountPanel() {
  if (typeof AG === "undefined" || !AG.flow || !AG.res) return;
  const pid = AG.mode === "agents" ? AG.sel : AG.one;
  const panel = document.querySelector("#panel"); if (!panel) return;
  let mount = panel.querySelector("#rcReceipt");
  if (!mount) { mount = document.createElement("div"); mount.id = "rcReceipt"; panel.appendChild(mount); }
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
  RC.comparison = null; const token = ++RC.compareToken;
  if (!previous) return;
  api("/api/ledger/compare", { baseline_id: previous.run_id, scenario_id: ledger.run_id }).then(result => {
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
