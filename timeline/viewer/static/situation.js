// Profile → supported visit conditions → the existing live day engine.
const SIT = { pid: null, options: null, forms: new Map(), busy: false, error: null, token: 0 };
function situationForm(pid) {
  if (!SIT.forms.has(pid)) SIT.forms.set(pid, { event: "none", custom: false, seed: 0, stay: "", building: "", phase: "", party: "" });
  return SIT.forms.get(pid);
}
function situationRequest(pid, form, options) {
  const selected = options.events.find(x => x.id === form.event && x.enabled === true);
  if (!selected) throw new Error("현재 실행 가능한 행사를 선택해 주세요.");
  const request = { personas: [pid], mode: "one", event: selected.event === true, seed: form.seed || 0, intervention: "none", observe: "day", product_levers: {}, visit_override: null };
  if (form.custom) {
    const stay = form.stay === "1", party = Number(form.party);
    if (!["0", "1"].includes(form.stay) || !Number.isInteger(party) || party < 1 || party > 8 || (stay && (!["GRAND", "VISTA", "DOUGLAS"].includes(form.building) || !["checkin", "mid", "checkout"].includes(form.phase)))) throw new Error("방문 조건의 투숙 여부·인원·건물·체류 단계를 선택해 주세요.");
    request.visit_override = { [pid]: { stay, building: stay ? form.building : null, phase: stay ? form.phase : "visit", party_size: party } };
  }
  return request;
}
async function situationOpen(pid, fromFlow = false, updateHash = true) {
  if (SIT.busy) return;
  const token = ++SIT.token; SIT.error = null;
  await libLoad();
  const persona = libP(pid);
  if (!persona || !libPublished(persona) || !libRuntime(pid)) return;
  if (!SIT.options) { const response = await fetch("/static/situation_options.json"); if (!response.ok) throw new Error("상황 선택 자료를 불러오지 못했습니다."); SIT.options = await response.json(); }
  if (token !== SIT.token) return;
  SIT.pid = pid;
  const form = situationForm(pid), last = typeof REV !== "undefined" && REV.latest && REV.latest.flow.plans[pid] ? REV.latest : null;
  if (fromFlow && last) {
    form.event = last.request.event ? "wine" : "none"; form.seed = last.request.seed || 0;
    const visit = (last.request.visit_override || {})[pid]; form.custom = !!visit;
    if (visit) Object.assign(form, { stay: visit.stay ? "1" : "0", building: visit.building || "", phase: visit.phase || "", party: String(visit.party_size) });
  }
  LIBV.situation = pid; LIBV.open = pid;
  if (typeof DS !== "undefined") { DS.step = null; if (typeof dsPresent === "function") dsPresent(); }
  if (updateHash) history.pushState(null, "", `#situation/${encodeURIComponent(pid)}`);
  setMode("library"); situationRender(); const root = document.querySelector("#libraryView"); if (root) root.scrollTop = 0;
}
function situationRender() {
  const root = document.querySelector("#libraryView"), p = SIT.pid && libP(SIT.pid);
  if (!root || !p || !SIT.options) return;
  const scroll = root.scrollTop, form = situationForm(p.id), traits = libTopBars(p.id, 3), opts = SIT.options;
  let ready = true; try { situationRequest(p.id, form, opts); } catch(e) { ready = false; }
  const future = rows => rows.map(x => `<button type="button" class="st-option" disabled aria-disabled="true"><b>${esc(x.label)}</b><span>확장 예정</span></button>`).join("");
  const select = (id, label, items, value, disabled = false) => `<label>${label}<select class="cf-input" id="${id}"${disabled ? " disabled" : ""}><option value="">선택해 주세요</option>${items.map(([key,text]) => `<option value="${key}"${String(value) === key ? " selected" : ""}>${text}</option>`).join("")}</select></label>`;
  root.innerHTML = `<div class="lb st-root"><div class="lb-crumb"><button type="button" class="cf-btn cf-sm" id="sitBack">← 라이브러리로 돌아가기</button><span class="lb-path">페르소나 라이브러리 › ${esc(dno(p.id))} › 상황 설정</span></div>
    <section class="st-hero">${libThumbP(p, "st-thumb")}<div><span class="lb-cty">${esc(libTypeLabel(p))}</span><h1>${esc(dno(p.id))}의 상황별 하루</h1><p>같은 고객이 다른 상황에 놓이면 어떻게 행동할까요?</p><div class="lb-htr">${traits.length ? traits.map(t => `<span>${esc(t.label)}</span>`).join("") : `<span>반복 성향 확인 중</span>`}</div></div></section>
    <section class="st-section"><div class="cf-sh"><h2>행사</h2><span class="cf-sub">행사 없음·와인페어 실제 계산 가능</span></div><div class="st-events">${opts.events.map(x => `<button type="button" class="st-option${form.event === x.id ? " on" : ""}" data-sit-event="${esc(x.id)}" aria-pressed="${form.event === x.id}"${x.enabled !== true || SIT.busy ? " disabled" : ""}><span class="st-option-top"><b>${esc(x.label)}</b><em>${x.enabled ? "실행 가능" : "확장 예정"}</em></span><span>${esc(x.description)}</span></button>`).join("")}</div></section>
    <div class="st-grid"><section class="st-section"><div class="cf-sh"><h2>날씨</h2><span class="cf-sub">계산 미연결</span></div><div class="st-future">${future(opts.weather)}</div></section><section class="st-section"><div class="cf-sh"><h2>방문 시점</h2><span class="cf-sub">계산 미연결</span></div><div class="st-future">${future(opts.timing)}</div></section></div>
    <section class="st-section"><div class="cf-sh"><h2>방문 목적과 동행·체류</h2><span class="cf-sub">기존 고객 프로필 유지</span></div><p class="st-note">기본 실행은 고객의 기존 방문·동행 조건을 유지합니다. 운영자가 직접 정할 때만 아래 조건을 적용합니다.</p><label class="st-custom"><input type="checkbox" id="sitCustom"${form.custom ? " checked" : ""}> 방문·동행 조건 직접 설정</label>
      ${form.custom ? `<div class="st-visit">${select("sitStay","투숙 여부",[["1","투숙"],["0","비투숙"]],form.stay)}${select("sitBuilding","숙박 건물",[["GRAND","그랜드"],["VISTA","비스타"],["DOUGLAS","더글라스"]],form.building,form.stay !== "1")}${select("sitPhase","체류 단계",[["checkin","체크인 당일"],["mid","연박 중간일"],["checkout","체크아웃 당일"]],form.phase,form.stay !== "1")}${select("sitParty","동행 인원",Array.from({length:8},(_,i)=>[String(i+1),`${i+1}명`]),form.party)}</div>` : `<p class="st-current">고객 기본 방문 조건 · 같은 고객·시드에서 행사 여부만 변경</p>`}
      <div class="st-future st-purpose">${opts.purposes.map(x => `<button type="button" class="st-option" disabled><b>${esc(x.label)}</b><span>${esc(x.description)}</span></button>`).join("")}</div></section>
    <div class="st-run"><div><b>${esc(dno(p.id))} · ${esc(opts.events.find(x => x.id === form.event).label)}</b><span>날씨·요일·확장 예정 상황은 이번 계산 입력에 포함되지 않습니다.</span></div><button type="button" class="cf-btn cf-primary" id="sitRun"${!ready || SIT.busy ? " disabled" : ""}>${SIT.busy ? "계산 중…" : "이 상황으로 하루 시뮬레이션 →"}</button></div>${SIT.error ? `<p class="rc-note" role="alert">${esc(SIT.error)}</p>` : ""}</div>`;
  root.querySelector("#sitBack").onclick = () => { LIBV.situation = null; history.pushState(null, "", "#lib"); libDetail(p.id); };
  root.querySelectorAll("[data-sit-event]").forEach(b => b.onclick = () => { if (!opts.events.some(x => x.id === b.dataset.sitEvent && x.enabled)) return; form.event = b.dataset.sitEvent; situationRender(); });
  root.querySelector("#sitCustom").onchange = e => { form.custom = e.target.checked; situationRender(); };
  for (const [id,key] of [["sitStay","stay"],["sitBuilding","building"],["sitPhase","phase"],["sitParty","party"]]) { const input = root.querySelector(`#${id}`); if (input) input.onchange = () => { form[key] = input.value; situationRender(); }; }
  root.querySelector("#sitRun").onclick = situationRun;
  root.scrollTop = scroll;
}
async function situationRun() {
  if (SIT.busy || !SIT.pid) return;
  const pid = SIT.pid, request = situationRequest(pid, situationForm(pid), SIT.options);
  SIT.busy = true; situationRender();
  try {
    if (typeof DS !== "undefined") DS.step = null;
    LIBV.situation = null; AG.engine = "autonomy"; AG.one = pid; AG.mode = "agent"; AG.oneOverride = !!request.visit_override; AG.oneAuto = null; AG.flow = null; AG.plans = null; AG.visits = null; AG.runs = [];
    AG.seed = request.seed; AG.iv = "none"; AG.scen = "day"; AG.exp = null; AG.keep.agent = null; AG.res = null; AG.autorun = true;
    AG.cond = { ...AG.cond, turn: "day", event: request.event, pricing: "historical", product_levers: {} };
    if (request.visit_override) { const visit = request.visit_override[pid]; Object.assign(AG.cond,visit,{club:false}); }
    history.pushState(null,"",`#flow/${encodeURIComponent(pid)}/${request.event ? 1 : 0}/live`);
    setMode("agent");
    const ready = await dsWait(() => AG.one === pid && !AG.autorun && document.querySelector("#agRun"));
    if (!ready) throw new Error("고객 흐름을 준비하지 못했습니다. 다시 실행해 주세요.");
    await agRun();
  } catch(e) { SIT.error = e.message; LIBV.situation = pid; setMode("library"); }
  finally { SIT.busy = false; if (LIBV.situation) situationRender(); }
}
window.addEventListener("hashchange", () => { const match = location.hash.match(/^#situation\/([^/]+)$/); if (match) situationOpen(decodeURIComponent(match[1]),false,false).catch(console.error); });
window.addEventListener("popstate", () => { const match = location.hash.match(/^#situation\/([^/]+)$/); if (match) situationOpen(decodeURIComponent(match[1]),false,false).catch(console.error); });
window.addEventListener("load", () => { const match = location.hash.match(/^#situation\/([^/]+)$/); if (match) situationOpen(decodeURIComponent(match[1]),false,false).catch(console.error); });
