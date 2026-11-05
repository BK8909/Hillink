// CL-1025-37 P0 → P1 → P2 — 시연 저장 스토리 재생. 영상과 웹이 같은 story_v3.json · flow_fixture_v1.json(P0 와 같은 저장본) 을 쓴다.
//   P2(최종 제품 동선): 안내 카드 없이 실제 라이브러리에서 시작 → 고객 상세 · 원문 → 같은 고객의 와인페어 하루 → 여러 명 · 개별 확인 → 운영 실험 → 행동근거.
//   · 저장 재생(시연 단계에서만): #demo/ 단계를 재생할 때 고객흐름의 /api/flow 요청을 같은 정규화 키로 저장본에서 찾아 돌려준다. 그 밖(사용자 실행 · #flow/)은 항상 실제 엔진 계산.
//     저장본이 없는 조건(방문 조건 직접 지정 · 운영 변경 등)은 계산하지 않고 알린다 — '실시간 계산'으로 바꾸면 원래 서버 계산.
//   · 시연 스토리: 6장(라이브러리 → 후기 → 행사 → 하루 행동 → 비교 → 결론) · 단계 주소(#demo/D3 등)로 새로고침 · 뒤로가기 · 직접 재진입.
//     P0 단계 주소(#demo/S4b 등)는 같은 장면의 P1 단계로 연결한다. 자유 탐색 중 고객 · 행사를 바꾸면 #flow/<고객>/<0|1>.
//   · P1 장면 순서: 지도 이동을 먼저 재생하고(결정 패널 닫힘) 도착하면 작은 결정 칩 → 다음 단계에서 폭을 줄인 결정 패널.
window.HILLINK_BUILD = "CL-37 product-final";   // 개발 정보 버튼 툴팁 · 콘솔에서 버전 확인용
const DS = { on: true, fx: null, story: null, step: null, last: null, lastRun: null, applying: false, ready: null, fxSha: null, err: null, tok: 0, arrived: null };
const DS_KIND_CLS = { OBS: "obs", IMG: "img", REPLAY: "rep", PREVIEW: "pre" };
const DS_STORY = "/static/demo_story/story_v3.json";
const DS_V1 = { S0: "L1", S1: "L1", S2a: "L2", S2b: "L2", S2c: "L2", S2d: "L2", S3: "O1", S4a: "F1", S4b: "F2", S4c: "M4", S5: "M1", S6: "B1", R1: "L2", R2: "L2", R3: "L2", E1: "O1", D1: "F1", D2: "F1", D3: "F1", D4: "F2", D5: "M4", C1s: "M1", C2s: "M1", Z1: "B1" };   // P0 · P1 단계 주소 → P2 단계

function dsCanon(v) { return v === null || typeof v !== "object" ? v : Array.isArray(v) ? v.map(dsCanon) : Object.fromEntries(Object.keys(v).sort().map(k => [k, dsCanon(v[k])])); }
function dsKey(q) { return JSON.stringify(dsCanon(Object.assign({}, q, { personas: [...(q.personas || [])].sort() }))); }
async function dsSha(buf) { try { const h = await crypto.subtle.digest("SHA-256", buf); return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join(""); } catch (e) { return null; } }

DS.ready = (async () => {
  try {
    const s = await fetch(DS_STORY, { cache: "no-cache" }); DS.story = await s.json();
    const f = await fetch(DS.story.fixture, { cache: "no-cache" }); const buf = await f.arrayBuffer();
    DS.fxSha = await dsSha(buf); DS.fx = JSON.parse(new TextDecoder().decode(buf));
  } catch (e) { DS.err = "저장 스토리를 불러오지 못했습니다"; DS.on = false; }
})();

// 고객흐름의 /api/flow 만 가로챈다(다른 API 는 그대로)
const dsApi0 = api;
api = async function (path, body) {
  if (path === "/api/flow" && DS.on && DS.step) {   // 10/26 — 저장본 재생은 시연 단계(#demo/…)를 재생할 때만. 사용자가 고객 · 조건을 고르고 ▶ 실행하면(DS.step 해제) 항상 실제 엔진 계산
    await DS.ready;
    if (DS.on && DS.fx) {
      const k = dsKey(body || {}), r = DS.fx.entries[k];
      if (!r) {   // 10/26 — 저장본에 없는 조건(체류 단계 · 건물 · 인원 등을 바꾼 경우)은 같은 엔진으로 실시간 계산(시드 고정 · 저장본 22/22 와 같은 결과 확인). 서버가 거절하면 그때만 '준비되어 있지 않음'
        try { const live = await dsApi0(path, body); DS.last = { key: k, hit: false, live: true }; DS.lastRun = { p: (body.personas || [])[0], e: body.event ? 1 : 0, mode: body.mode }; setTimeout(dsBar, 0); return live; } catch (e) { console.warn("실시간 계산 실패", e && e.message); }
        DS.last = { key: k, hit: false }; if (typeof AG !== "undefined") { AG.runs = []; AG.res = null; AG.plans = null; AG._sc = null; if (typeof setPlay === "function") setPlay(false); } dsBar(); throw new Error("이 조건의 하루는 준비되어 있지 않습니다. 고객이나 조건을 바꿔 다시 실행해 주세요."); }
      DS.last = { key: k, hit: true, sha: DS.fx.entry_sha[k] }; DS.lastRun = { p: (body.personas || [])[0], e: body.event ? 1 : 0, mode: body.mode };
      setTimeout(dsBar, 0);
      return JSON.parse(JSON.stringify(r));
    }
  }
  return dsApi0(path, body);
};

// ---------------------------------------------------------------- 주소 상태
function dsParse() {
  const h = decodeURIComponent(location.hash || "").replace(/^#/, ""), a = h.split("/");
  if (a[0] === "demo" && a[1]) return { kind: "demo", step: DS_V1[a[1]] || a[1], live: a[2] === "live" };
  if (a[0] === "flow" && a[1]) return { kind: "flow", p: a[1], e: a[2] === "1" ? 1 : 0, live: a[3] === "live" };
  if (a[0] === "lib") return { kind: "lib" };
  return null;
}
function dsHash(st) { return st.kind === "demo" ? `#demo/${st.step}${DS.on ? "" : "/live"}` : st.kind === "flow" ? `#flow/${st.p}/${st.e}${DS.on ? "" : "/live"}` : "#lib"; }
function dsPush(st, replace) { const h = dsHash(st); if (location.hash === h) return; (replace ? history.replaceState : history.pushState).call(history, st, "", h); }

const dsWait = async (fn, ms = 15000) => { const t0 = Date.now(); while (!fn()) { if (Date.now() - t0 > ms) return false; await new Promise(r => setTimeout(r, 50)); } return true; };
const dsStep = () => DS.step ? DS.story.steps.find(x => x.id === DS.step) : null;
const dsPresent = () => { document.body.classList.remove("ds-present"); };   // P6 — 발표 모드(메뉴 흐림) 없음: 실제 제품 화면 그대로

async function dsFlow(p, e) {
  if (MODE !== "agent") setMode("agent");
  await dsWait(() => typeof AG !== "undefined" && AG.meta && document.querySelector("#agRun"));
  await dsWait(() => !AG.busy);
  if (AG.mode !== "agent") AG.mode = "agent";
  if (!(AG.meta.personas || []).some(x => x.id === p)) p = null;   // P7 — 실행 승인 11명 밖(열람 전용 등) 고객 주소는 고객을 채우지 않는다(실행 버튼 비활성 · 서버도 403)
  AG.one = p; AG.oneOverride = false; AG.oneAuto = null; AG.iv = "none"; AG.seed = 0; AG.scen = undefined;
  AG.cond.event = !!e; AG.cond.product_levers = {};
  AG.res = null; AG.runs = []; AG.keep.agent = null;
  agLeft(); agReady();   // P6 — 주소로 들어와도 고객 · 조건만 채우고 정지(사용자가 ▶ 실행을 눌러야 하루 시작)
}
async function dsMany(e) {   // 기존 검증 고객 11명 동시 — 저장본 키: mode many · personas 11
  if (MODE !== "agents") setMode("agents");
  await dsWait(() => typeof AG !== "undefined" && AG.meta && document.querySelector("#agRun"));
  await dsWait(() => !AG.busy);
  AG.mode = "agents"; AG.fix = false; AG.many = new Set(AG.meta.personas.map(x => x.id)); AG.iv = "none"; AG.seed = 0; AG.scen = undefined;
  AG.cond.event = !!e; AG.cond.product_levers = {}; AG.res = null; AG.runs = []; AG.keep.agents = null;
  agLeft(); agReady();   // P6 — 정지 상태로 준비만
}
async function dsLib(view) {
  setMode("library");
  await dsWait(() => typeof LIBV !== "undefined" && LIBV.data && LIBV.gal);
  LIBV.q = ""; LIBV.open = null; LIBV.hl && LIBV.hl.clear();
  if (view.m === "draft") { LIBV.type = null; LIBV.evOnly = false; LIBV.draft = view.card; libDraft(view.card); return; }
  LIBV.draft = null; LIBV.type = view.t || null; LIBV.evOnly = view.m === "events"; LIBV.evOpen = view.m === "events"; libGrid();
  document.querySelector("#libraryView").scrollTop = 0;
}
async function dsDetail(view) {
  setMode("library");
  await dsWait(() => typeof LIBV !== "undefined" && LIBV.data && LIBV.gal);
  await dsWait(() => LIBV.links || LIBV.linksDenied, 4000);
  LIBV.q = ""; LIBV.draft = null; LIBV.hl && LIBV.hl.clear(); LIBV.type = view.t || null; LIBV.relOpen = !!view.rel;
  LIBV.open = view.p; libDetail(view.p);
  const V = document.querySelector("#libraryView");
  if (view.scroll) { const el = V.querySelector(view.scroll); if (el) V.scrollTop = Math.max(0, el.offsetTop - 70); } else V.scrollTop = 0;
}
const dsEvT = () => { const ti = AG.runs.findIndex(r => r.turn === "event"); return ti < 0 ? null : { ti, T: agMin(AG.runs[ti].time) }; };
async function dsManyView(v, tok) {
  const have = MODE === "agents" && AG.res && agIsMany(AG.res) && AG.runs.length && AG.runs[0].customers && DS.lastRun && DS.lastRun.mode === "many" && AG.many && AG.many.size === (AG.meta.personas || []).length && !!AG.cond.event === !!v.e;
  if (!have) { await dsMany(v.e); return; }   // P6 — 결과가 없으면 정지된 준비 화면만(사용자가 실행)
  const E = dsEvT(); if (!E) return;
  agManyStop(); if (typeof closeDrawer === "function") closeDrawer();
  if (v.sel) {   // 한 명 고르기 — 행사 결정 시각에 멈춘 채 고른 고객만 강조 · 오른쪽 카드에 성향 · 지금 · 결정 근거
    AG.manyT = E.T; AG.nowMin = E.T; agSetAt("turn", null, E.ti); agManyDraw(E.T); agClock();
    agSelect(v.sel);
    if (v.drawer) { await new Promise(r => setTimeout(r, 900)); if (tok !== DS.tok) return; agChoiceDrawer(v.sel, E.ti); }
  } else {   // 전체 — 행사 시각 조금 전부터 함께 이동
    AG.sel = null; if (AG.keep[AG.mode]) AG.keep[AG.mode].sel = null;
    AG.manyHeld = new Set(AG.runs.map((r, i) => [agMin(r.time), i]).filter(x => x[0] < E.T + (v.from || -50)).map(x => x[1]));
    AG.manyT = E.T + (v.from || -50); agManyDraw(AG.manyT); agStrip(); agPanel && agPanel();
    agClock();   // P6 — 자동 재생하지 않음(재생은 타임라인의 ▶ 로만)
  }
}
function dsChip2(html) { let el = document.getElementById("dsChip"); if (!html) { if (el) el.remove(); return; } if (!el) { el = document.createElement("div"); el.id = "dsChip"; document.body.appendChild(el); } el.className = ""; el.innerHTML = html; dsChipPos(el); }
async function dsOpx(v, tok) {
  setMode("opx");
  await dsWait(() => typeof OPX !== "undefined" && OPX.meta && OPX.form && !OPX.busy && OPX.last, 60000); if (tok !== DS.tok) return;
  const want = Object.assign({}, OPX.meta.default, v.form || {});
  const same = OPX.lastForm && Object.keys(want).every(k => OPX.lastForm[k] === want[k]);
  if (!same) { OPX.form = want; OPX.sel = null; await opxRun(); }
  else opxRender();
  if (tok !== DS.tok) return;
  if (v.form && OPX.last && OPX.last.customers) {   // 바뀐 고객 한 명을 골라 오른쪽에 이유 표시
    const ch = OPX.last.customers.find(c => c.choice_changed);
    if (ch) { OPX.sel = ch.persona_id; opxRender(); }
  }
}
async function dsEvidence(v, tok) {   // P3 — 행동근거는 저장된 결정 기록(같은 저장본)을 직접 읽는다 · 다시 계산하지 않음
  BH.pid = v.p; BH.e = v.e ? 1 : 0; BH.turn = v.turn; BH.tab = v.tab || "case"; BH.open = false; BH.q = ""; if (v.step != null) BH.step = v.step;
  if (MODE !== "evidence") setMode("evidence"); else await renderBehavior();
  await dsWait(() => document.querySelector(BH.tab === "engine" ? "#bvBody .bv-eng" : "#bvBody .bv-case"), 15000); if (tok !== DS.tok) return;
  const el = v.scroll ? document.querySelector("#evidenceView " + v.scroll) : document.querySelector("#evidenceView .bv-head");
  if (el) el.scrollIntoView({ block: "start" });
}

// 결정 턴 · 장면 찾기
function dsTurn(p, turn) {
  const ti = AG.runs.findIndex(r => r.turn === turn); if (ti < 0) return null;
  const L = agScenes(p), si = L.findIndex(x => x.k === "turn" && x.ti === ti);
  return { ti, si, L, c: AG.runs[ti].customers.find(x => x.persona_id === p) || AG.runs[ti].customers[0] };
}
const DS_TURN_KO = { event: "행사 시간", dinner: "저녁", breakfast: "아침", lunch: "점심" };
function dsChipText(p, T) {
  const c = T.c, ch = c.choice, ru = c.runner_up;
  const nm = x => x ? (x.product_label && x.product_label.length <= 14 ? x.product_label : x.venue_label) : "";
  const gap = ru ? ch.score - ru.score : null;
  return { who: dno(p), turn: DS_TURN_KO[AG.runs[T.ti].turn] || AG.runs[T.ti].turn, pick: nm(ch), sc: ch.score.toFixed(2), alt: ru ? (nm(ru) === "객실" ? "객실 휴식" : nm(ru)) : null, asc: ru ? ru.score.toFixed(2) : null, close: gap != null && gap < 0.05 };
}
function dsChip(p, T, opt = {}) {   // 도착 후 작은 결정 칩(지도를 가리지 않음) — 누르면 폭을 줄인 결정 패널
  let el = document.getElementById("dsChip");
  if (!T) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("div"); el.id = "dsChip"; document.body.appendChild(el); }
  const x = dsChipText(p, T);
  el.className = opt.big ? "big" : "";
  el.innerHTML = `<b>${esc(x.who)} · ${esc(x.turn)} 선택</b><span class="dsc-pick">${esc(x.pick)}</span>${x.alt ? `<span class="dsc-vs">점수 ${x.sc} · 다음 대안 ${esc(x.alt)} ${x.asc}${x.close ? " · <em>근소한 차이</em>" : ""}</span>` : ""}${opt.noBtn ? "" : `<button type="button" class="cf-btn cf-sm" id="dsWhy">결정 근거 보기 ▸</button>`}`;
  const w = el.querySelector("#dsWhy"); if (w) w.onclick = () => { dsChip(null); dsDrawer(p, T.ti); };
  dsChipPos(el);
}
function dsChipPos(el) {   // 지도 오른쪽 위 빈 바다 쪽에 붙인다(시계 · 아바타 · 섬을 가리지 않게)
  const m = document.querySelector("#mapWrap") || document.querySelector("#map"); if (!m || innerWidth < 900) { el.style.cssText = ""; return; }
  const r = m.getBoundingClientRect(); if (!r.width) return;
  el.classList.add("corner"); el.style.left = "auto"; el.style.transform = "none"; el.style.top = `${Math.max(64, r.top + 12)}px`; el.style.right = `${Math.max(8, innerWidth - r.right + 12)}px`;
}
function dsDrawer(p, ti) { if (typeof setPlay === "function") setPlay(false); agChoiceDrawer(p, ti); const d = document.getElementById("drawer"); if (d) d.classList.add("ds-narrow"); }
function dsMsg(html) {   // 지도 위 큰 자막(결론 · 비교) — 지도를 가리지 않게 아래쪽
  let el = document.getElementById("dsMsg");
  if (!html) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("div"); el.id = "dsMsg"; document.body.appendChild(el); }
  el.innerHTML = html;
}
function dsClear() { dsCard(null); dsChip(null); dsMsg(null); if (typeof closeDrawer === "function") closeDrawer(); const d = document.getElementById("drawer"); if (d) d.classList.remove("ds-narrow"); if (typeof AG !== "undefined") cancelAnimationFrame(AG.raf); }

async function dsApply(st) {
  await DS.ready;
  if (!st) st = { kind: "demo", step: DS.story.default_step || DS.story.steps[0].id };
  if (st.live !== undefined) DS.on = !st.live && !!DS.fx;
  DS.applying = true; const tok = ++DS.tok; DS.arrived = null;
  try {
    if (st.kind === "demo") {
      const S = DS.story.steps.find(x => x.id === st.step) || DS.story.steps[0];
      DS.step = S.id; dsPresent(); dsClear();
      const v = S.view;
      if (v.m === "flow") { await dsFlow(v.p, v.e); }   // P6 — 고객 · 조건만 채운 정지 화면(자동 재생 · 자동 선택 없음)
      else if (v.m === "many") await dsManyView(v, tok);
      else if (v.m === "detail") await dsDetail(v);
      else if (v.m === "opx") await dsOpx(v, tok);
      else if (v.m === "evidence") await dsEvidence(v, tok);
      else if (v.m === "card") { await dsLib({ m: "lib" }); }   // P6 — 전면 안내 카드 없음
      else await dsLib(v);
    } else if (st.kind === "flow") { DS.step = null; dsPresent(); dsClear(); await dsFlow(st.p, st.e); }
    else { DS.step = null; dsPresent(); dsClear(); await dsLib({ m: "lib" }); }
  } finally { if (tok === DS.tok) { DS.applying = false; dsBar(); } }
}
function dsGo(stepId, replace) { const st = { kind: "demo", step: stepId }; dsPush(st, replace); dsApply(st); }
function dsMove(d) { const L = DS.story.steps; let i = L.findIndex(x => x.id === DS.step); if (i < 0) { const c = dsAutoCh(); i = Math.max(0, L.findIndex(x => x.ch === c)); if (d > 0) d = 0; } const j = Math.min(L.length - 1, Math.max(0, i + d)); dsGo(L[j].id); }
function dsChapter(cid) { const S = DS.story.steps.find(x => x.ch === cid); if (S) dsGo(S.id); }
const dsIsSituationRoute = () => /^#situation\/[^/]+$/.test(location.hash);
window.addEventListener("popstate", () => { if (!dsIsSituationRoute() && !(typeof bhRouteMatch === 'function' && bhRouteMatch())) dsApply(dsParse()); });
// Fragment navigation from revenue must prepare the requested flow without computing it.
window.addEventListener("hashchange", () => { if (/^#(?:flow|demo|lib)(?:\/|$)/.test(location.hash) && !(typeof bhRouteMatch === 'function' && bhRouteMatch())) dsApply(dsParse()); });

// P6 — 자유 탐색 자동 재실행 없음: 고객 · 조건을 바꿔도 사용자가 ▶ 시뮬레이션 실행을 눌러야 계산 · 재생한다.
// 실행이 끝나면 주소(#flow/고객/행사)에 남겨 새로고침 · 뒤로가기에서 같은 고객 · 조건의 정지 화면으로 돌아온다.
document.addEventListener("hl:agrun", () => { if ((typeof BH !== "undefined" && BH.restoring) || typeof AG === "undefined" || AG.mode !== "agent" || !AG.one) return; DS.lastRun = { p: AG.one, e: AG.cond.event ? 1 : 0, mode: "one" }; DS.step = null; dsPush({ kind: "flow", p: AG.one, e: AG.cond.event ? 1 : 0 }); });
// 시연 단계에서 사용자가 조건 · 메뉴를 직접 조작하면 자유 탐색으로 전환(발표 모드 해제)
document.addEventListener("change", ev => { if (!DS.step || DS.applying || !ev.target.closest || !ev.target.closest("#agLeft, .ag-left, #left")) return; DS.step = null; dsPresent(); dsChip(null); dsMsg(null); setTimeout(dsBar, 0); }, true);
document.addEventListener("click", ev => {
  if (!DS.step || !ev.target.closest) return;
  // 시연 스토리의 흐름 단계에서 조건을 바꾸지 않고 ▶를 누르면 저장된 실행을 재생한다.
  // 라이브러리 등 다른 시연 단계에서 시작한 실행은 자유 실행이므로 DS.step을 해제한다.
  // 조건 변경(change 이벤트)은 위에서 이미 DS.step을 비워 실엔진을 호출한다.
  if (ev.target.closest("#agRun")) {
    const view = DS.story && DS.story.steps.find(x => x.id === DS.step)?.view;
    if (view && ["flow", "many"].includes(view.m)) return;
    DS.step = null; dsPresent(); dsChip(null); dsMsg(null); dsCard(null); setTimeout(dsBar, 0); return;
  }
  if (DS.applying) return;
  if (ev.target.closest("#agReset, nav .tab")) { DS.step = null; dsPresent(); dsChip(null); dsMsg(null); dsCard(null); setTimeout(dsBar, 0); }
}, true);

// ---------------------------------------------------------------- 화면: 아래 스토리 바(6장) · 단계 카드
function dsBadges(kinds) { const L = DS.story.legend; return (kinds || []).map(k => `<span class="ds-k ${DS_KIND_CLS[k]}" title="${esc(L[k].note)}">${esc(L[k].label)}</span>`).join(""); }
const dsDev = () => document.body.classList.contains("devmode");
function dsAutoCh() {   // P5 — 자유 탐색(실제 클릭) 중에도 지금 보고 있는 제품 화면에 맞춰 장 안내를 맞춘다
  const M = typeof MODE !== "undefined" ? MODE : "";
  return M === "library" ? (typeof LIBV !== "undefined" && (LIBV.open || LIBV.draft) ? "C2" : "C1") : M === "agent" ? "C3" : M === "agents" ? "C4" : M === "opx" ? "C5" : M === "evidence" ? "C6" : null;
}
function dsBar() {   // P6 — 화면 아래 시연 챕터 바 삭제(상단 메뉴와 중복). 남아 있는 요소 · 여백만 정리
  const el = document.getElementById("dsBar"); if (el) el.remove();
  document.body.classList.remove("ds-on", "ds-live", "ds-present");
}
// 자유 탐색 중 화면(모드 · 고객 상세)이 바뀌면 장 안내만 다시 그린다

function dsFixtureFacts() {   // 단계 카드 숫자 = 저장본에서 계산(손으로 적지 않음)
  const E = DS.fx.entries, k = e => Object.keys(E).find(x => x.includes('"mode":"many"') && x.includes(`"event":${e}`) && (JSON.parse(x).personas || []).length === DS.fx.personas.length);
  const a = E[k(false)], b = E[k(true)], ids = Object.keys(a.plans);
  const acts = (r, p) => r.plans[p].scenes.map(s => s.act).join(" ");
  const changed = ids.filter(p => acts(a, p) !== acts(b, p));
  const ev = (b.runs.find(r => r.turn === "event") || { customers: [] }).customers;   // 행사 턴 = 엔진 기록에서 와인페어 참여(flow_run.turn_of)
  return { n: ids.length, changed, entered: ev.map(c => ({ id: c.persona_id, review: c.reason_totals.review, score: c.choice.score, runner: c.runner_up && c.runner_up.score })) };
}
async function dsCard(card) {
  if (card && !(typeof LIBV !== "undefined" && LIBV.gal)) { try { const j = await api("/api/library/gallery"); if (typeof LIBV !== "undefined") LIBV.gal = j.cards || []; } catch (e) {} }
  let el = document.getElementById("dsCard");
  if (!card) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("div"); el.id = "dsCard"; document.body.appendChild(el); }
  const L = DS.story.ledger, Lg = DS.story.legend, O = DS.story.observations, G = (typeof LIBV !== "undefined" && LIBV.gal) || [];
  const img = cid => { const c = G.find(x => x.card_id === cid); return c && c.image ? `<img src="${esc(c.image.src)}" alt="고객별 생성 이미지 초안">` : ""; };
  const audit = `<details class="ds-audit"><summary>자료 상태 · 검증 상세</summary><p>저장본 ${esc(DS.fxSha || "")} · 엔진 ${esc((DS.fx.engine_head || "").slice(0, 7))} · seed 0 · LLM 호출 0</p><p>앱 고객 원장 ${L.app_ledger}명 · 실행 검증 ${L.runnable}명 · 고객별 이미지 초안 ${L.image_drafts}장(사람 승인 ${L.human_image_approved}) · ID 일치 ${L.id_match}(유형 충돌 ${L.type_conflict}) · 이미지에만 ${L.image_only} · 원장에만 ${L.app_only}</p></details>`;
  let html = "";
  if (card === "intro") html = `<h2>${esc(DS.story.title)}</h2><p class="ds-sub">실제 후기에서 확인한 경험으로 고객을 정리하고, 행사 조건에 따라 하루가 어떻게 달라지는지 저장된 엔진 실행으로 보여드립니다.</p>
    <ol class="ds-road">${(DS.story.chapters || []).map((c, k) => `<li><i>${k + 1}</i>${esc(c.label)}</li>`).join("")}</ol>
    <div class="ds-leg">${Object.entries(Lg).map(([k, v]) => `<div><span class="ds-k ${DS_KIND_CLS[k]}">${esc(v.label)}</span><p>${esc(v.note)}</p></div>`).join("")}</div>${audit}`;
  else if (card === "cases") {
    const mini = cid => { const o = O[cid]; if (!o) return ""; const ok = o.lines.find(l => /LP/.test(l.src)); return `<div class="ds-case">${img(cid)}<div><h3>${esc(o.title)}</h3><p><span class="dsl ok">확인된 경험</span>${esc(ok ? ok.text : "")}</p><p><span class="dsl unk">아직 모르는 것</span>${esc((o.unknown || [])[0] || "")}</p></div></div>`; };
    html = `<h2>다른 후기 사례</h2><p class="ds-sub">후기 관측 사례입니다 — 행동 엔진으로 실행하지 않았습니다.</p><div class="ds-cases">${(DS.story.featured || []).slice(2).map(mini).join("")}</div>`;
  } else if (card === "switch") html = `<div class="ds-sw"><div class="ds-swa"><span class="ds-k obs">후기 관측 사례</span><h3>A27 · N27 · 후기 사례</h3><p>후기에서 확인한 경험 · 행동 엔진 실행 전</p></div><div class="ds-swarr" aria-hidden="true">→</div>
      <div class="ds-swb"><span class="ds-k rep">저장된 엔진 실행</span><h3>기존 검증 고객 A08</h3><p>실행 허용 고객 · 10/24 행사일 기준 저장된 하루</p></div></div>
    <p class="ds-big ds-swcap">이어서, 저장된 엔진 실행이 있는 기존 검증 고객 A08의 하루입니다.<br><b>앞의 후기 사례와는 다른 사람입니다.</b></p>`;
  else if (card === "obs_vs_hyp") {
    const F = dsFixtureFacts(), a8 = F.entered.find(x => x.id === "A08");
    html = `<h2>관측과 가설</h2><div class="ds-2">
      <section><span class="ds-k rep">관측 · 저장된 실행</span><h3>와인페어를 열었을 때</h3><ul><li>기존 검증 고객 ${F.n}명 중 <b>${F.changed.length}명</b>의 하루가 달라짐</li><li><b>${F.entered.length}명</b>이 행사 시간에 와인페어를 고름(${F.entered.map(x => esc(x.id)).join(" · ")})</li>${a8 ? `<li>A08: 와인페어 ${a8.score.toFixed(2)} vs 다음 대안 ${a8.runner.toFixed(2)} · 후기 근거 몫 ${a8.review.toFixed(2)}</li>` : ""}</ul></section>
      <section class="hyp"><span class="ds-k pre">가설 · 아직 만들지 않음</span><h3>표본에 적게 잡히는 방문</h3><ul><li>비투숙 외부 방문 · 단체 · 블로그를 쓰지 않는 고객을 가정 유형으로 더하는 층</li><li>보정 배수는 정하지 않음 — 관측과 섞어 합계를 만들지 않음</li></ul></section></div>${audit}`;
  }
  el.innerHTML = `<div class="ds-card ds-c-${card}">${html}</div>`;
}

// 기본 화면 초기화가 끝난 뒤 주소를 적용해 시연 화면이 뒤늦게 덮이지 않도록 한다.
(async () => { const initialRoute=location.hash; await HILLINK_APP_READY; await DS.ready; if (location.hash!==initialRoute || DS.err || dsIsSituationRoute() || (typeof bhRouteMatch === "function" && bhRouteMatch())) return; const st = dsParse() || { kind: "lib" }; if (!dsParse() || DS_V1[(location.hash.split("/")[1] || "")]) history.replaceState(st, "", dsHash(st)); await dsApply(st); })();

try { console.info("HILLINK " + window.HILLINK_BUILD + " — 고객흐름은 ▶ 시뮬레이션 실행을 눌러야 시작"); const d = document.getElementById("btnDev"); if (d) d.title = (d.title || "") + " · 화면 버전 " + window.HILLINK_BUILD; } catch (e) {}
