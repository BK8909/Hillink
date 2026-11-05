// Daily behavior revenue and the existing product-condition experiment share a page,
// but keep their requests, ledgers and totals independent.
const REV = { ids: [], allIds: [], selected: new Set(), scope: "recent", latest: null, pendingDemo: null, enteredLatest: null, completedKey: null, typeOptions: [],
  scenario: "none", type: "", stay: "all", flow: null, baseline: null, ledger: null,
  comparison: null, busy: false, err: null, department: null, venue: null, product: null, customer: null,
  amountBars: false, token: 0, filterToken: 0, completedScenario: null };
const REV_SCENARIOS = { none: "행사 없음", wine: "와인페어 있음", wine_fair_1300: "와인페어 13시 시작", pizzahill_full: "피자힐 이용 조건 변경", pool_check: "수영장 점검" };
async function revInit() {
  if (!REV.allIds.length) { const meta = await api("/api/turn/meta?turn=dinner"); REV.allIds = meta.personas.map(p => p.id).sort((a,b) => dno(a).localeCompare(dno(b))); }
}
const revScenarioOf = request => request.intervention && request.intervention !== "none" ? request.intervention : request.event ? "wine" : "none";
function revRememberFlow(flow, request) {
  if (!flow || !flow.plans) return;
  if (!flow.ledger) {
    if (typeof DS !== "undefined" && DS.last && DS.last.hit) { REV.pendingDemo = { flow: structuredClone(flow), request: structuredClone(request), key: DS.last.key }; REV.latest = null; if (REV.scope === "recent") revInvalidate(); }
    return;
  }
  if (!["live_engine", "stored_demo"].includes(flow.ledger.source)) return;
  REV.pendingDemo = null;
  REV.latest = { flow: structuredClone(flow), request: structuredClone(request) };
  REV.typeOptions = [...new Set([...REV.typeOptions, ...flow.ledger.customer_types])];
}
function revRememberDemoLedger(ledger, key) {
  const pending = REV.pendingDemo;
  if (!pending || pending.key !== key || ledger.source !== "stored_demo") return;
  revRememberFlow({ ...pending.flow, ledger }, pending.request);
  if (typeof MODE !== "undefined" && MODE === "opx" && REV.scope === "recent") revUseRecent();
}
const revIds = () => REV.scope === "all" ? [...REV.allIds] : REV.scope === "selected" ? [...REV.selected].filter(id => REV.allIds.includes(id)).sort((a,b) => dno(a).localeCompare(dno(b))) : REV.latest ? Object.keys(REV.latest.flow.plans) : [];
const revDraftKey = () => JSON.stringify([REV.scope, revIds().slice().sort(), REV.scenario, REV.scope === "recent" && REV.latest ? REV.latest.flow.ledger.run_id : null]);
function revRequest(kind) {
  const ids = revIds(), source = REV.latest ? REV.latest.request : {};
  const request = { ...structuredClone(source), personas: ids, mode: ids.length === 1 ? "one" : "many", seed: source.seed || 0,
    event: kind === "wine", intervention: ["none", "wine"].includes(kind) ? "none" : kind, observe: source.observe || "day", product_levers: source.product_levers || {} };
  if (source.visit_override) {
    const values = Object.values(source.visit_override), uniform = values.length && values.every(v => JSON.stringify(v) === JSON.stringify(values[0]));
    request.visit_override = Object.fromEntries(ids.filter(id => uniform || source.visit_override[id]).map(id => [id, structuredClone(uniform ? values[0] : source.visit_override[id])]));
    if (!Object.keys(request.visit_override).length) request.visit_override = null;
  }
  return request;
}
async function revUseRecent() {
  if (!REV.latest) return;
  ++REV.token; ++REV.filterToken;
  REV.busy = false; REV.err = null; REV.scope = "recent";
  REV.ids = revIds(); REV.scenario = revScenarioOf(REV.latest.request);
  REV.flow = structuredClone(REV.latest.flow); REV.baseline = null; REV.type = ""; REV.stay = "all";
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
    REV.type = ""; REV.stay = "all";
    await revUseRecent();
  }
}
async function revRun() {
  if (REV.scope === "recent") { await revUseRecent(); return; }
  if (REV.busy || !revIds().length) return;
  const token = ++REV.token, kind = REV.scenario, key = revDraftKey(), request = revRequest(kind);
  ++REV.filterToken;
  REV.busy = true; REV.err = null; revRender();
  try {
    const baseline = await api("/api/flow", revRequest("none"));
    const flow = kind === "none" ? baseline : await api("/api/flow", request);
    if (flow.ledger.source !== "live_engine") throw new Error("실제 고객 흐름 계산 결과를 확인하지 못했습니다. 다시 실행해 주세요.");
    if (token !== REV.token) return;
    REV.ids = request.personas; REV.baseline = baseline; REV.flow = flow; REV.completedScenario = kind; REV.completedKey = key;
    REV.typeOptions = [...new Set([...REV.typeOptions, ...flow.ledger.customer_types])];
    if (!flow.ledger.customer_types.includes(REV.type)) REV.type = "";
    REV.department = REV.venue = REV.product = REV.customer = null;
    await revFilter();
  } catch (e) { REV.err = e.message; }
  finally { if (token === REV.token) { REV.busy = false; revRender(); } }
}
async function revFilter() {
  if (!REV.flow || !REV.baseline) return;
  const token = ++REV.filterToken, flow = REV.flow, baseline = REV.baseline;
  const filters = { customer_type: REV.type || null, stay_status: REV.stay };
  const [ledger, comparison] = await Promise.all([
    api("/api/ledger/filter", { run_id: flow.ledger.run_id, ...filters }),
    api("/api/ledger/compare", { baseline_id: baseline.ledger.run_id, scenario_id: flow.ledger.run_id, ...filters })
  ]);
  if (token !== REV.filterToken) return;
  REV.ledger = ledger; REV.comparison = comparison;
  const valid = ledger.venues.some(v => JSON.stringify(v.key) === REV.venue);
  if (!valid) REV.venue = REV.product = REV.customer = null;
  revRender();
}
function revHTML() {
  const L = REV.ledger, recent = REV.scope === "recent", types = REV.typeOptions, cmp = REV.comparison;
  const status = REV.busy ? "실제 하루 행동 계산 중…" : L ? `${REV_SCENARIOS[REV.completedScenario]} · ${recent ? rcSource(L) + " 그대로 보기" : "실제 엔진 계산 완료"}` : "계산 전 · 집계할 고객과 상황을 선택해 주세요";
  return `<section class="rev-root"><div class="rev-title"><div><h2>하루 행동 기반 가상 매출</h2><p>고객이 선택한 하루 영수증에서 상품·업장·부문 합계로 이어집니다.</p></div><span class="rev-basis">${L ? `참여 고객 ${L.team_count}팀 기준` : `선택 고객 ${revIds().length}팀`}</span></div>
    <div class="rev-scope" role="group" aria-label="집계 범위">${[["recent","최근 시뮬레이션"],["selected","고객 직접 선택"],["all",`전체 ${REV.allIds.length}명`]].map(([key,label]) => `<button type="button" class="cf-btn${REV.scope === key ? " cf-primary" : ""}" data-rev-scope="${key}"${REV.busy || (key === "recent" && !REV.latest) ? " disabled" : ""}>${label}</button>`).join("")}</div>
    ${REV.scope === "selected" ? `<fieldset class="rev-picker"><legend>실행 고객 선택 · ${REV.selected.size}명</legend>${REV.allIds.map(id => `<label><input type="checkbox" data-rev-select="${esc(id)}"${REV.selected.has(id) ? " checked" : ""}${REV.busy ? " disabled" : ""}><span><b>${esc(dno(id))}</b><small>${esc(typeof opxType === "function" ? opxType(id) : "")}</small></span></label>`).join("")}</fieldset>` : ""}
    ${REV.scope === "recent" && !REV.latest ? `<p class="rc-note">고객 흐름에서 실제 시뮬레이션을 실행하면 같은 고객·조건·영수증을 여기서 이어봅니다.</p>` : ""}
    ${recent ? (L ? `<div class="rev-readonly"><b>${esc(rcSource(L))}</b><span>${esc(REV_SCENARIOS[REV.completedScenario])} · 실행 고객 ${L.team_count}팀 · 당시 방문·인원 조건 유지</span></div>` : "") : `<div class="rev-controls"><label>고객 유형<select class="cf-input" id="revType"><option value="">전체 유형</option>${types.map(t => `<option value="${esc(t)}"${REV.type === t ? " selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
      <label>상황 · 행사<select class="cf-input" id="revScenario">${Object.entries(REV_SCENARIOS).map(([k,v]) => `<option value="${k}"${REV.scenario === k ? " selected" : ""}>${v}</option>`).join("")}</select></label>
      <label>투숙 여부<select class="cf-input" id="revStay">${[["all","전체 고객"],["staying","투숙 고객"],["non_staying","비투숙 고객"]].map(([k,v]) => `<option value="${k}"${REV.stay === k ? " selected" : ""}>${v}</option>`).join("")}</select></label>
      <button type="button" id="revRun" class="cf-btn cf-primary"${REV.busy || !revIds().length ? " disabled" : ""}>${REV.busy ? "계산 중…" : "하루 매출 계산"}</button></div>`}
    <p class="rev-status" role="status">${esc(status)}</p>${REV.err ? `<p class="rc-note" role="alert">${esc(REV.err)}</p>` : ""}
    ${L ? `<div class="rev-cohort"><b>집계 결과 · ${L.team_count}팀</b><span>${Object.values(L.receipts).map(r => esc(r.display_id)).join(" · ")}</span><details><summary>고객별 집계 조건</summary><ul>${Object.values(L.receipts).map(r => `<li>${esc(r.display_id)} · ${esc(rcContext({ ...L.context, ...r }))}</li>`).join("")}</ul></details></div>
    <div class="rev-summary"><div><span>전체 시뮬레이션 결제액</span><strong>${rcMoney(L.totals.paid_krw)}</strong><small>참여 고객 ${L.team_count}팀의 가상 소비 합계</small></div><div>${recent ? `<span>실행 고객</span><b>${L.team_count}팀</b><small>기존 실행 결과 · 재계산 없음</small>` : `<span>기준 실행 대비</span><b>${cmp && cmp.comparable ? rcDelta(cmp.delta_krw) : "비교 미확정"}</b><small>${cmp && !cmp.comparable ? esc(cmp.message) : `${esc(REV_SCENARIOS[revScenarioOf(REV.baseline.ledger.context)] || "기준 조건")} · 같은 고객·시드`}</small>`}</div><div><span>객실 요금 가정</span><b>+${rcMoney(L.totals.assumption_addition_krw)}</b><small>가정 포함 ${rcMoney(L.totals.with_assumptions_krw)}</small></div></div>
    ${L.input_missing.length ? `<p class="rc-note">실행 입력 미연결 ${L.input_missing.length}명은 이번 계산과 합계에서 제외했습니다.</p>` : ""}${L.totals.unknown_count ? `<p class="rc-note">금액 미확인 ${L.totals.unknown_count}건은 기본 결제액에 포함하지 않았습니다.</p>` : ""}
    <div class="rev-sectors"><button type="button" class="cf-btn cf-sm${!REV.department ? " cf-primary" : ""}" data-rev-dept="">호텔 합계</button>${L.levels.L2.map(g => `<button type="button" class="cf-btn cf-sm${REV.department === g.key[0] ? " cf-primary" : ""}" data-rev-dept="${esc(g.key[0])}">${esc(g.key[0])} · ${rcMoney(g.paid_krw)}</button>`).join("")}</div>
    <div class="rev-layout"><section class="rev-venues"><div class="cf-sh"><h3>${REV.department ? esc(REV.department) + " · " : ""}업장별 가상 매출</h3><span class="cf-sub">금액순 · 같은 고객 집합</span></div>${revVenues(L)}</section><aside class="rev-drill">${revDrill(L)}</aside></div>` : `<div class="rev-empty">${REV.busy ? "고객별 실제 하루를 계산하고 있습니다." : recent ? "고객 흐름의 마지막 실행 결과를 기다리고 있습니다." : "계산 전 · 고객과 조건을 선택한 뒤 하루 매출 계산을 눌러 주세요."}</div>`}
    <p class="rc-note">실제 호텔 매출이나 전체 고객의 예측치가 아닙니다. 원장·상품·업장·부문·호텔 합계는 같은 거래 행에서 계산합니다.</p></section>`;
}
function revVenues(L) {
  const list = L.venues.filter(v => !REV.department || v.department === REV.department);
  if (!list.length) return `<p class="rc-note">이 고객 집합에서 해당 이용 내역이 없습니다.</p>`;
  return `<table class="rev-table"><thead><tr><th>업장</th><th>이용 팀</th><th>가상 결제액</th><th>기준 실행 대비</th><th>주요 고객 유형</th></tr></thead><tbody>${list.map(v => {
    const key = JSON.stringify(v.key), delta = REV.comparison && REV.comparison.comparable ? REV.comparison.venues.find(x => JSON.stringify(x.key) === key) : null;
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
function revRender() { const mount = document.querySelector("#revenueContent"); if (mount) { mount.innerHTML = revHTML(); revWire(); } }
function revWire() {
  const root = document.querySelector("#revenueContent"); if (!root) return;
  root.querySelectorAll("[data-rev-scope]").forEach(b => b.onclick = async () => {
    if (REV.busy) return;
    REV.scope = b.dataset.revScope; REV.err = null;
    if (REV.scope === "selected" && !REV.selected.size) Object.keys((REV.ledger || {}).receipts || {}).forEach(id => REV.selected.add(id));
    REV.ids = revIds();
    if (REV.scope === "recent" && REV.latest) { try { await revUseRecent(); } catch(e) { REV.err = e.message; revRender(); } }
    else { revInvalidate(); revRender(); }
  });
  root.querySelectorAll("[data-rev-select]").forEach(input => input.onchange = () => {
    input.checked ? REV.selected.add(input.dataset.revSelect) : REV.selected.delete(input.dataset.revSelect);
    REV.ids = revIds(); revInvalidate(); revRender();
  });
  const run = root.querySelector("#revRun"); if (run) run.onclick = revRun;
  const scenario = root.querySelector("#revScenario"); if (scenario) scenario.onchange = () => { REV.scenario = scenario.value; revInvalidate(); revRender(); };
  const ty = root.querySelector("#revType"); if (ty) ty.onchange = () => { REV.type = ty.value; revInvalidate(); revRender(); };
  const stay = root.querySelector("#revStay"); if (stay) stay.onchange = () => { REV.stay = stay.value; revInvalidate(); revRender(); };
  root.querySelectorAll("[data-rev-dept]").forEach(b => b.onclick = () => { REV.department = b.dataset.revDept || null; REV.venue = REV.product = REV.customer = null; revRender(); });
  root.querySelectorAll("[data-rev-venue]").forEach(b => b.onclick = () => { REV.venue = b.dataset.revVenue; REV.product = REV.customer = null; revRender(); });
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
  setMode("agents");
  if (typeof dsWait === "function") await dsWait(() => AG.meta && document.querySelector("#agRun"));
  AG.engine = "autonomy"; AG.many = new Set(Object.keys(r.plans)); AG.fix = false; AG.seed = r.engine.seed;
  AG.cond.event = r.ledger.context.event; AG.sel = pid; AG.plans = r.plans; AG.visits = r.visits; AG.runs = r.runs;
  AG.runs.forEach(R => { R._mode = "agents"; R._auto = true; R.customers.forEach(c => { c.vc = agVcOf(r.visits[c.persona_id]); }); if (R._before) { R._before._mode = "agents"; } });
  AG.ti = Math.max(0, AG.runs.findIndex(R => R.customers.some(c => c.persona_id === pid))); AG.res = AG.runs[AG.ti];
  RC.comparison = REV.comparison;
  AG.flow = { result: structuredClone(r), request: { ...structuredClone(r.ledger.context), personas: Object.keys(r.plans), mode: Object.keys(r.plans).length > 1 ? "many" : "one" }, ledger: r.ledger, stories: r.stories || null, engine: r.engine, intervention: r.intervention, applied: r.levers_applied || [], skipped: r.levers_not_applied || [], notices: r.notices || [], sha: r.inputs_sha };
  AG.keep.agents = { runs: AG.runs, sel: pid, plans: AG.plans, visits: AG.visits, flow: AG.flow };
  agLeft(); agPlanHint(); agShow(false);
}
