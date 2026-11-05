// 힐링크 손님 지도 — 화면 동작 (서버: app.py · 계산: engine.py)
"use strict";

const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const KCOL = { checkin: "var(--k-checkin)", room: "var(--k-room)", meal: "var(--k-meal)", facility: "var(--k-facility)", event: "var(--k-event)" };
const KNAME = { checkin: "도착 · 체크인", room: "객실", meal: "식사", facility: "시설", event: "행사" };
const won = v => (v == null ? "-" : Math.round(v).toLocaleString("ko-KR") + "원");
const eok = v => (v / 1e8).toFixed(2) + "억";
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// P6 — 짧은 괄호 · 대괄호 묶음이 다음 줄에 혼자 떨어지지 않게 한 덩어리로(넘치면 덩어리 안에서 줄바꿈 · 가로 스크롤 없음)
const escP = s => esc(s).replace(/(\S*)([(\[][^()\[\]]{1,40}[)\]])(\S*)/g, (m, a, g, b) => `<span class="nb">${a}${g}${b}</span>`);
// 10/14 — 모델 안의 선택지 이름을 화면용 이름으로 (최종 식사 선택 표와 같은 말을 쓴다)
const ALT_NAME = { "식당 외 식사": "호텔 밖 · 객실 식사" };
const altName = s => (ALT_NAME[s] || (typeof s === "string" ? s.replace(/더 파빌리온/g, "더파빌리온").replace(/르파사쥬/g, "르 파사쥬") : s));   // 10/19 업장 공식 표기 (nmDisp 와 같은 규칙)
// 10/16 최종 식사 선택의 표시 이름 — 엔진이 쓰는 키는 그대로 두고 화면 글만 바꾼다
const outName = s => term(String(s));
const tmin = s => Date.parse(s) / 60000;
const hhmm = m => { const d = new Date(m * 60000); return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); };
const dlabel = m => { const d = new Date(m * 60000); return `${d.getMonth() + 1}/${d.getDate()}(${"일월화수목금토"[d.getDay()]})`; };
const gradeCls = g => (String(g).includes("◎") ? "g1" : String(g).includes("○") ? "g2" : "g3");

let LIB = null, MODE = "day";
let G = null;            // 손님 결과
let SEL = null;          // 고른 행동 번호
let T = 0, PLAY = false, last = 0;
let DAY = null, DAYT = 0;        // 하루 결과 · 하루 화면 시각(칸 번호)
const DAYCACHE = {};

// ---------------------------------------------------------------------------
async function api(path, body) {
  const payload = path === "/api/flow" && body ? { ...body, include_ledger: true } : body;
  const r = await fetch(path, payload ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : {});
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(j.error || r.statusText);
  return deName(j);
}
// 10/15 화면에는 팀원 이름을 쓰지 않는다 — 장부 · 문서에서 온 문장의 이름(님 · 조사 포함)을 표시 단계에서 지운다. 장부 원본은 그대로
const NAME_RE = /(?<![_A-Za-z0-9가-힣])(강경수|경수|소연|한호|슬기|나율)(님)?(이|가|의|은|는|과|와|께서)?(?![_A-Za-z0-9가-힣])\s*/g;
function noName(s) {
  if (typeof s !== "string" || !NAME_RE.test(s)) { NAME_RE.lastIndex = 0; return s; }
  NAME_RE.lastIndex = 0;
  return s.replace(NAME_RE, "")
    .replace(/\(\s*[·,]\s*/g, "(").replace(/\s*[·,]\s*\)/g, ")").replace(/\(\s*\)/g, "")
    .replace(/(\s*·\s*){2,}/g, " · ").replace(/^\s*[·,]\s*/, "").replace(/\s*[·,]\s*$/, "")
    .replace(/\s+:/g, ":").replace(/ {2,}/g, " ").trim();
}
// 10/16 화면 용어 — 장부 · 엔진 기록의 '끼니' 를 운영 용어(식사 · 식사 시간대 · 패키지 포함 식사)로. 엔진 · 장부 원본은 그대로, 표시 단계에서만
const TERMS = [
  [/같은 끼니 식사 기록 없음/g, "같은 식사 시간대 이용 기록 없음"], [/고유 끼니/g, "고유 식사 건"], [/막힌 끼니/g, "이용이 제한된 식사"],
  [/포함 끼니/g, "패키지 포함 식사"], [/끼니 최종 결과/g, "최종 식사 선택"], [/끼니 최종/g, "최종 식사"], [/회\/끼니/g, "회/식사 시간대"],
  [/끼니당/g, "식사 시간대당"], [/끼니별/g, "식사 시간대별"], [/(날짜\s*·\s*)끼니/g, "$1식사 시간대"], [/같은 끼니/g, "같은 식사 시간대"], [/끼니/g, "식사"],
];
function term(s) { if (typeof s !== "string" || s.indexOf("끼니") < 0) return s; for (const [re, to] of TERMS) s = s.replace(re, to); return s; }
function deName(o) {
  if (typeof o === "string") return term(noName(o));
  if (Array.isArray(o)) { for (let i = 0; i < o.length; i++) o[i] = deName(o[i]); return o; }
  if (o && typeof o === "object") {
    for (const k of Object.keys(o)) {
      const v = deName(o[k]), nk = term(k);
      if (nk !== k) { delete o[k]; o[nk] = v; } else o[k] = v;
    }
    return o;
  }
  return o;
}
// 10/19 소연 ①-1 · ①-2 · ②-9 — 공식 표기에 맞춘 화면 이름 (엔진 이름표 engine.LOC_NAMES 는 모델 지문에 들어가므로 화면에서만 바꾼다)
const LOC_DISP = { THE_PAVILION: "더파빌리온", LE_PASSAGE: "르 파사쥬", TENNEZ_PARK: "테네즈 파크" };
const locName = c => LOC_DISP[c] || (LIB && LIB.loc_names[c]) || c;
// 서버 결과의 이름 문자열(막힌 곳 · 흐름 · 이벤트의 '더 파빌리온' 등)과 맞출 때는 엔진 이름도 함께 본다
const locKey = c => (LIB && LIB.loc_names[c]) || c;
const locNames = c => [...new Set([locKey(c), locName(c)])];
// 매출 표의 L3 업장 이름 · L4 내부 코드 → 화면 이름. 실제 구매 상품이 특정되지 않은 코드는 '대표 단가' 임을 밝히고 상품 이름을 지어내지 않는다
const L3_DISP = { 파빌리온: "더파빌리온", 르파사쥬: "르 파사쥬", 럭스바: "LUX BAR" };
const l3Disp = n => L3_DISP[n] || n;
const L4_DISP = { meal_other: "식당 밖 식사 (배달 · 편의점 등)", ondal: "온달 식사 (모델 대표 단가 · 상품 미특정)", pool: "수영장 이용", skyard: "스카이야드 이용" };
const l4Disp = n => L4_DISP[n] || n;
// 막힌 곳 이름(서버 문자열 · '더 파빌리온') 의 화면 표기 — 데이터 키(data-cons 등)는 그대로 두고 보이는 글자만 바꾼다 (운영 요약 · 고객 흐름 공용)
const nmDisp = s => String(s == null ? "" : s).replace(/더 파빌리온/g, "더파빌리온").replace(/르파사쥬/g, "르 파사쥬");
// 10/17 UX 11차 · 화면 아래 긴 안내문 대신 ⓘ — 짧은 한 줄만 보이고 설명은 눌러서 (주절주절 안내문이 화면을 더럽힌다는 리뷰)
// 10/17 UX 13차 · 업장 식별색 — 상태색(빨강 · 주황 · 초록 · 파랑)과 겹치지 않는 낮은 채도 계열. 이름 옆 작은 점으로만 쓰고, 운영 요약 · 상황 비교 · 상세에서 같은 업장은 같은 점
const VEN_COLOR = { THE_BUFFET: "#7b5ea7", THE_PAVILION: "#2a9d8f", PIZZA_HILL: "#8b5a2b", MYONGWOLGWAN: "#7a8b3a", GEUMRYONG: "#b06a8f", ONDAL: "#6b6f85", MOEGI: "#c29a3d", LE_PASSAGE: "#9c6b4e", LUX_BAR: "#5e7d8c", FOREST_PARK: "#6e8f5a", SKYARD: "#8a7f9c" };
const VEN_NAME_COLOR = { "더뷔페": "#7b5ea7", "더파빌리온": "#2a9d8f", "더 파빌리온": "#2a9d8f", "피자힐": "#8b5a2b", "명월관": "#7a8b3a", "금룡": "#b06a8f", "온달": "#6b6f85", "모에기": "#c29a3d", "르파사쥬": "#9c6b4e", "르 파사쥬": "#9c6b4e", "럭스바": "#5e7d8c", "LUX BAR": "#5e7d8c", "포레스트 파크": "#6e8f5a", "스카이야드": "#8a7f9c" };
const venColor = x => VEN_COLOR[x] || (Object.keys(VEN_NAME_COLOR).find(k => String(x || "").startsWith(k)) ? VEN_NAME_COLOR[Object.keys(VEN_NAME_COLOR).find(k => String(x || "").startsWith(k))] : null);
const vdot = x => { const c = venColor(x); return c ? `<i class="vdot" style="background:${c}" aria-hidden="true"></i>` : ""; };
const noteI = (text, tone) => `<button class="nfo nt${tone ? " " + tone : ""}" data-note="${esc(text)}" aria-label="설명" title="설명 보기">i</button>`;
const capN = (short, long) => `<div class="cap">${short}${long ? noteI(long) : ""}</div>`;
// 15차 · 손님 이름은 짧게 'blog32 · 워커힐 2인', 후기 요약(객실 · 목적 · 성향)은 ⓘ 뒤로
const gShort = p => { if (!p) return ""; const nm = String(p.name || ""), id = nm.split(" · ")[0].trim();
  return p.party ? `${id} · 워커힐 ${p.party}인` : id; };
const gFull = p => { if (!p) return ""; const nm = String(p.name || ""); return p.prop_name && !nm.includes(p.prop_name) ? `${nm} · ${p.prop_name}` : nm; };
document.addEventListener("click", e => {
  const b = e.target.closest && e.target.closest(".nfo.nt"); if (!b) return;
  const was = b.getAttribute("aria-expanded") === "true";
  document.querySelectorAll(".nfo-pop").forEach(x => x.remove()); document.querySelectorAll(".nfo[aria-expanded='true']").forEach(x => x.setAttribute("aria-expanded", "false"));
  if (was) return;
  const pop = document.createElement("div"); pop.className = "nfo-pop"; pop.setAttribute("role", "dialog");
  let nj = null; try { nj = b.dataset.nj ? JSON.parse(b.dataset.nj) : null; } catch (x) { nj = null; }
  if (nj) {   // 10/24 09-B 구조화 도움말 — 세 구획 · 근거 종류 태그
    pop.classList.add("nj");
    const tags = (nj.basis || []).map(t => `<span class="nj-tag nj-${({ "실제 후기": "rv", "추출 성향": "tr", "운영 조건": "op", "운영 조건 · 계산": "op", "추정 흐름": "as" })[t] || "x"}">${esc(t)}</span>`).join("");
    pop.innerHTML = `${nj.title ? `<b>${esc(nj.title)}</b>` : ""}<h5>무엇을 의미하나요?</h5><p>${esc(nj.what || "")}</p>${tags || nj.basis_note ? `<h5>어떤 근거인가요?</h5><p class="nj-tags">${tags}${nj.basis_note ? `<span class="nj-bn">${esc(nj.basis_note)}</span>` : ""}</p>` : ""}${nj.caution ? `<h5>주의할 점</h5><p>${esc(nj.caution)}</p>` : ""}<button type="button" class="nj-x" aria-label="닫기">닫기</button>`;
  } else pop.innerHTML = `<p>${esc(b.dataset.note)}</p>`;
  document.body.appendChild(pop);
  const nx = pop.querySelector(".nj-x"); if (nx) nx.onclick = () => { pop.remove(); b.setAttribute("aria-expanded", "false"); };
  const r = b.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
  let x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), innerWidth - w - 8), y = r.bottom + 8;
  if (y + h > innerHeight - 8) y = r.top - h - 8;
  y = Math.max(8, Math.min(y, innerHeight - h - 8));   // 위 · 아래 모두 모자라면 화면 안으로
  pop.style.left = x + "px"; pop.style.top = y + "px"; b.setAttribute("aria-expanded", "true");
  if (!noteI.wired) { noteI.wired = true;
    document.addEventListener("mousedown", ev => { if (!ev.target.closest(".nfo-pop, .nfo")) { document.querySelectorAll(".nfo-pop").forEach(x => x.remove()); document.querySelectorAll(".nfo.nt[aria-expanded='true']").forEach(x => x.setAttribute("aria-expanded", "false")); } });
    document.addEventListener("scroll", () => document.querySelectorAll(".nfo-pop").forEach(x => x.remove()), true); }
});

// ---------------------------------------------------------------------------
// 시작
// ---------------------------------------------------------------------------
async function init() {
  drawBase($("#base"));
  drawLabels();
  LIB = await api("/api/library");   // CL-1024-16 — 원문 링크 포함 여부는 서버가 정함(로컬 검수 환경일 때만)
  loadMapPhotos();
  if (LIB.v4) { PRE.full = Object.assign({}, LIB.v4); V4N = LIB.v4_name || V4N; }   // 10/16 기본 모델 정의는 서버(engine.V4) 하나만
  const dateOpts = LIB.dates.map(d => `<option value="${d.date}">${d.date.slice(5).replace("-", "/")} (${d.dow})${d.fair ? " · 와인페어" : ""}</option>`).join("");
  $("#fDate").innerHTML = dateOpts; $("#dDate").innerHTML = dateOpts;
  $("#fDate").value = "2026-10-10"; $("#dDate").value = "2026-10-10";
  $("#fSex").innerHTML = LIB.sexes.map(s => `<option>${s}</option>`).join("");
  $("#fAge").innerHTML = LIB.ages.map(s => `<option>${s}</option>`).join("");
  $("#fPurpose").innerHTML = LIB.purposes.map(s => `<option>${s}</option>`).join("");
  const dining = ["THE_BUFFET", "PIZZA_HILL", "GEUMRYONG", "MYONGWOLGWAN", "MOEGI", "ONDAL", "THE_PAVILION", "LUX_BAR", "LE_PASSAGE"];
  $("#fPrefer").innerHTML = `<option value="auto">자동 — 목적별 확률 (생성기와 같음)</option><option value="">없음</option>` +
    dining.map(c => `<option value="${c}">${locName(c)}</option>`).join("");
  $("#kHypo").innerHTML = `<option value="">없음</option>` + (LIB.hypotheses || []).map(a => `<option value="${a.ID}">H${a.ID} ${esc(a.이름)}</option>`).join("");
  $("#kAnom").innerHTML = `<option value="">추가 변동 없음</option>` + (LIB.anomalies || []).map(a => `<option value="${a.ID}">${esc(a.이름)}</option>`).join("");
  $("#fAnom").innerHTML = `<option value="">추가 변동 없음</option>` + (LIB.anomalies || []).map(a => `<option value="${a.ID}">${esc(a.이름)}</option>`).join("");
  const RL = LIB.review_list || [];
  if (!RL.length) $("#reviewHint").textContent = "후기 목록이 비어 있습니다 — 화면 서버(app.py)를 껐다 켠 뒤 새로고침해 주세요.";
  $("#fReview").innerHTML = RL.map((r, i) => `<option value="${i}" title="${esc(r.name)}">${esc(rvTitle(r))} · ${r.party}인</option>`).join("");   // 10/17 UX 4차 · 자세한 손님 정보는 아래 후기 카드에
  $("#fReview").onchange = () => { reviewInfo(); personaCard(); sitSync(); };
  reviewInfo();
  gridInit();
  drawPins();
  bind();
  syncForm();
  await refreshPackages();
  await refreshDays();
  // 10/19 소연 ③-1 — 계산해 둔 날이 없는 새 PC 에서는 아래 loadDay 가 불리지 않아 조정값이 HTML 기본(체류 단축 하나)으로 남고,
  // 첫 '하루 돌리기'가 기본 모델이 아닌 '조정값 직접 설정' 으로 계산됐다. 처음에는 늘 기본 모델(v4.1 · 서버 engine.V4)로 맞추고,
  // 계산해 둔 날이 있으면 loadDay 가 그 날의 조정값으로 다시 맞춘다
  setKnobs(Object.assign({}, PRE.full));
  setSrc("blog");
  setMode("library");   // 10/23 첫 화면은 페르소나 라이브러리(시연 1단계)
  // 처음 열 때는 v4 기본(온톨로지 정합 · 행사 없음) 날을 먼저 — 없으면 그 날짜의 아무 날
  const L0 = refreshDays.list || [], d0 = $("#dDate").value;
  const isV4 = d => isV4Theta(d.theta, d.date) && Object.keys(d.theta || {}).every(k => k in PRE.full);
  const first = L0.find(d => d.date === d0 && d.scale === 1 && d.scenario === "none" && isV4(d)) || L0.find(d => d.date === d0 && d.scale === 1) || L0[0];
  // 초기 주소는 index.html에서 정규화한다. 내부 화면 이동은 기존 라우터를 따른다.
  // 10/23 예전 하루 전체 결과는 더 이상 불러오지 않는다(호텔 전체 시뮬레이션 화면 제거)   // 10/18 19차b-3 · 해시(#evidence… · #oneteam…)로 들어왔을 때 뒤늦게 끝난 loadDay 가 화면을 고객 흐름으로 되돌리지 않게 먼저 기다린다(계산해 둔 날이 있는 PC 에서만 재현되던 문제)
  try { await applyHashRoute(); } catch (e) { console.warn("hash route", e); }
}

// 조정값 묶음 — "온톨로지 정합" = v4 (10/14 처리 순서 섞기 · 평일 비투숙 ×0.5 · 객실 산식 포함. 평일 비투숙 배율은 주말 · 공휴일에는 계산에서 빠진다)
const PRE = { onto: { next_window: 1, wait_horizon: 300, takeout_base: -2.5 }, reserve: { next_window: 1, reserve_wait: 1, queue_max: 30, takeout_cap: 60 }, full: { next_window: 1, reserve_wait: 1, queue_max: 30, takeout_cap: 40, bar_nightcap: 0.16, purpose_onto: 1, passage_rate: 0.62, fine_dwell: 120, moegi_seats: 40, turn_hold: 1, rooms_onto: 1, order_mix: 1, wd_day: 0.5, rooms_formula: 1, rng_team: 1, no_busy_dwell: 2 }, base: {} };
// 10/16 v4.1 = v4 + 중식 · 석식 혼잡 시 체류 단축 끔 (근거사슬 7-19). 정의는 engine.V4 (LIB.v4) 가 기준이고 위 값은 서버를 못 읽을 때의 대비
let V4N = "v4.1";
const V4_LABEL = () => "온톨로지 정합 " + V4N;

// 10/14 결과 버전 — 지금 코드 · 입력과 다른 버전으로 계산된 결과면 알린다 (다시 돌리면 최신)
function isStale(D) { return !!(D && LIB && (D.model_ver !== LIB.model_ver || D.input_ver !== LIB.input_ver)); }
function staleNote(D) {
  if (!isStale(D)) return "";
  // 10/16 — 시연 화면에서 기술 경고 대신 무엇을 하면 되는지를 먼저. 버전 해시는 개발 정보를 켰을 때만
  return `<div class="callout stale" data-stale="${esc(D.key)}">이 결과는 <b>예전 기준으로 계산한 결과</b>입니다. 그 뒤 모델이나 입력 표가 바뀌어 지금 기준과 숫자가 다를 수 있습니다. ` +
    `<button class="rbtn small" data-rerun="${esc(D.key)}">같은 조건으로 다시 계산</button> <span class="rr-st hint"></span>` +
    `<span class="dev hint"> · 결과 ${esc(D.model_ver || "기록 없음")}/${esc(D.input_ver || "-")} · 지금 ${esc(LIB.model_ver)}/${esc(LIB.input_ver)}</span></div>`;
}
document.addEventListener("click", async e => {
  const b = e.target.closest && e.target.closest("[data-rerun]");
  if (!b || b.disabled) return;
  const D = DAYCACHE[b.dataset.rerun] || DAY; if (!D) return;
  const st = b.parentElement.querySelector(".rr-st"); b.disabled = true;
  try {
    const r = await api("/api/day", { date: D.date, scenario: D.scenario, scale: D.scale, theta: D.theta || {} });
    const t0 = Date.now();
    for (;;) {
      const s = await api("/api/day/status?key=" + encodeURIComponent(r.key));
      if (s.status === "done") break;
      if (s.status === "error" || s.status === "lost") throw new Error(s.error || "계산이 끊겼습니다");
      if (st) st.textContent = `다시 계산하는 중 ${s.total ? `${s.done}/${s.total}팀 · ` : ""}${Math.round((Date.now() - t0) / 1000)}초 지남`;
      await new Promise(res => setTimeout(res, 1000));
    }
    delete DAYCACHE[r.key]; delete FLOWCACHE[r.key];
    await refreshDays(); await loadDay(r.key);
  } catch (err) { if (st) st.textContent = "다시 계산하지 못했습니다: " + err.message; b.disabled = false; }
});
// 화면용 짧은 이름 — 계산 키 · 조정값 나열 대신 (전체 나열은 개발 정보 켜면)
const HOLIDAYS = new Set(["2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-05", "2026-10-09"]);   // agent_v4.HOLIDAYS 와 같게
const isWeekday = ds => { if (!ds) return true; const w = new Date(ds + "T12:00:00").getDay(); return w >= 1 && w <= 5 && !HOLIDAYS.has(ds); };
const WEEKDAY_ONLY = ["wd_day", "wd_dine", "wd_named", "wd_biz", "biz_party"];
// 그 날에 실제로 적용되는 v4 묶음 — 주말 · 공휴일이면 평일 전용 조정값을 뺀다 (engine.norm_theta 와 같게)
function v4For(ds) { const p = Object.assign({}, PRE.full); if (!isWeekday(ds)) WEEKDAY_ONLY.forEach(k => delete p[k]); return p; }
// 효과가 '확실' 한지 — 같은 시드끼리 짝지은 차이의 95% 구간이 0을 넘지 않고, 거의 매번(시드 수 − 1 이상) 같은 방향 (10/14 · 시드 5개로 잰 편차 배수는 편차 자체가 흔들려 기준에서 뺌)
const sureEffect = (e, n) => !!(e && e.lo95 != null && (e.lo95 > 0 || e.hi95 < 0) && e.same_sign >= n - 1);
function isV4Theta(th, ds) { th = th || {}; const p = v4For(ds); return Object.keys(p).every(k => th[k] === p[k]); }
function knobSummary(d) { const k = knobParts(d); return [k.base, ...k.extra].join(" · "); }
function knobParts(d) {
  const th = d.theta || {}, extra = [];
  if (th.anomaly) { const a = (LIB.anomalies || []).find(x => String(x.ID) === String(th.anomaly)); extra.push("변동 상황: " + (a ? a.이름 : th.anomaly) + (th.anomaly_k ? ` ×${th.anomaly_k}` : "")); }
  if (th.hypo) { const h = (LIB.hypotheses || []).find(x => String(x.ID) === String(th.hypo)); extra.push("가설 H" + th.hypo + (h ? " " + h.이름 : "")); }
  if (th.search_w) extra.push("검색 관심 가정 " + th.search_w);
  if (th.posting_k) extra.push("피자힐 미식 게시 " + th.posting_k + "배 가정");
  if (th.trend_w) extra.push("SNS 신호 반영 " + th.trend_w);
  if (th.wd_day != null && th.wd_day !== PRE.full.wd_day) extra.push(`평일 비투숙 ×${th.wd_day}`);
  if (th.wd_biz) extra.push("비즈니스 · 접대 평일 유지");
  if (th.biz_party) extra.push("비즈니스 일행 별실 규모");
  if (th.buffet_seats) extra.push(`더뷔페 좌석 ${th.buffet_seats}석`);
  if ((th.no_busy_dwell || 0) !== (PRE.full.no_busy_dwell || 0)) extra.push(th.no_busy_dwell == 1 ? "조식까지 체류 단축 끔 (실험)" : th.no_busy_dwell == 2 ? "중식 · 석식 체류 단축 끔" : "혼잡 시 체류 단축 켬 (v4 방식)");
  if (th.meal_split) extra.push(th.meal_split == 2 ? "비투숙 막히면 호텔 밖 식사" : "비투숙 호텔 밖 식사");   // 10/16 실험 조정값 (식당 외 식사 분리)
  if (th.wd_dine != null) extra.push(`평일 저녁 식당 계획 ${Math.round(th.wd_dine * 100)}%` + (th.wd_named ? " · 유명 업장 제외" : ""));
  // 10/14 에 v4 에 차례로 더한 것 — 이것만 빠진 날은 "v4 (… 반영 전)" 으로 (평일 비투숙 배율은 값이 달라도 v4 로 보고 위에서 값을 붙인다)
  const LATER = { order_mix: "처리 순서 섞기", wd_day: "평일 비투숙", rooms_formula: "객실 산식", rng_team: "손님마다 다른 난수" };   // 10/16 체류 단축(no_busy_dwell)은 값이 달라도 v4.1 로 보고 위에서 비교용으로 붙인다
  const p = v4For(d.date), off = Object.keys(p).filter(k => th[k] !== p[k] && !(k === "wd_day" && th.wd_day != null) && k !== "no_busy_dwell");
  const base = !off.length ? V4_LABEL()
    : off.every(k => k in LATER) ? `v4 (${off.map(k => LATER[k]).join(" · ")} 반영 전)` : "조정값 직접 설정";
  return { base, extra };
}
function dayLabel(key) {
  const d = (refreshDays.list || []).find(x => x.key === key);
  if (!d) return "계산해 둔 하루";
  return `${d.date.slice(5).replace("-", "/")} · ${d.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${d.knobs ? knobSummary(d) : "기본 모델"}`;
}
const niceKeys = s => String(s || "").replace(/\(?(20\d\d-\d\d-\d\d_[A-Za-z0-9_.\-]+)\)?/g, (m, k) => `(${dayLabel(k)})`);

// 개발 정보 켜기 · 끄기 — 경영 · 운영 화면에서는 파일 이름 · 계산 키 · 조정값 전체를 숨긴다
function bindDev() {
  const b = $("#btnDev"); if (!b) return;
  let on = false; try { on = localStorage.getItem("wh_dev") === "1"; } catch (e) { }
  const apply = () => { document.body.classList.toggle("devmode", on); b.classList.toggle("on", on); };
  b.onclick = () => { on = !on; try { localStorage.setItem("wh_dev", on ? "1" : "0"); } catch (e) { } apply(); };
  apply();
}

function bindKnobs() {
  // PRE 는 맨 위 (변칙 예측표도 v4 기준을 찾을 때 씀)
  $$("#knobs [data-knob]").forEach(b => b.onclick = () => {   // 조정값 묶음을 바꿔도 고른 변동 상황은 그대로
    const keep = { anomaly: +$("#kAnom").value || undefined, anomaly_k: +$("#kAnomK").value || undefined };
    setKnobs(Object.assign({}, PRE[b.dataset.knob] || {}, keep));
  });
}
function bind() {
  bindKnobs(); bindDev();
  $$("nav .tab").forEach(b => b.onclick = () => setMode(b.dataset.mode));
  { const bh = $("#brandHome"); if (bh) bh.onclick = () => { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {} setMode("library"); }; }   // 10/23 로고 클릭 = 페르소나 라이브러리(해시도 지움)
  $$("#flowSeg button").forEach(b => b.onclick = () => setMode(b.dataset.m));
  $("#knobs").addEventListener("change", () => { if (MODE === "settings") renderSettings(); });
  $("#btnSetRun").onclick = () => { setMode("day"); $("#btnDay").click(); };
  $("#btnSetV4").onclick = () => { const b = document.querySelector('.knobpre button[data-knob="full"]'); if (b) b.click(); renderSettings(); };
  $$("#fGuest button").forEach(b => b.onclick = () => { $$("#fGuest button").forEach(x => x.classList.toggle("on", x === b)); syncForm(); refreshPackages(); });
  ["#fDate", "#fScenario"].forEach(s => $(s).onchange = () => { syncForm(); refreshPackages(); refreshCrowd(); sitSync(); });
  ["#fProp", "#fNights", "#fParty", "#fKids"].forEach(s => $(s).onchange = () => { syncForm(); refreshPackages(); });
  $("#fPackage").onchange = pkgHint;
  $("#fCrowd").onchange = () => { refreshCrowd.touched = true; crowdHint(); sitSync(); };
  $("#btnRun").onclick = () => runSim("one");
  $("#btnRandom").onclick = () => randomGuest();
  $$("#srcSeg button").forEach(b => b.onclick = () => setSrc(b.dataset.s));
  $("#btnCmp").onclick = () => runSim("cmp");
  $("#btnRev").onclick = () => runSim("rev");
  $("#fAnom").onchange = sitSync;
  ["#gfPurpose", "#gfAge", "#gfSex", "#gfStay", "#gfKids"].forEach(s => $(s).onchange = gridRender);
  $("#pDetail").addEventListener("change", () => { if (SRC !== "blog") { if (SRC === "grid" && GRIDPICK) GRIDPICK.edited = true; personaCard(); } });
  $$(".presets button[data-preset]").forEach(b => b.onclick = () => preset(b.dataset.preset));   // 조정값 묶음 버튼(data-knob)은 따로
  $("#btnPlay").onclick = () => setPlay(!PLAY);
  $$("#mapView button").forEach(b => b.onclick = () => setMapView(b.dataset.v));
  $$("#routeAll button").forEach(b => b.onclick = () => setRouteAll(b.dataset.r === "all"));   // 16차 · 지금 행동 | 전체 동선 두 칸
  $("#slider").oninput = e => {
    setPlay(false);
    if (MODE === "guest" && G) { T = G.t0 + (G.t1 - G.t0) * e.target.value / 1000; drawFrame(); }
    if (MODE === "day" && DAY) { DAYT = Math.round((DAY.slots.length - 1) * e.target.value / 1000); if (MAPVIEW !== "now") setMapView("now"); drawDay(); }
  };
  $("#btnDay").onclick = startDay;
  ["#dDate", "#dScenario", "#dScale"].forEach(s => $(s).onchange = () => { syncDayForm(); });
  window.addEventListener("resize", () => { if (MODE === "guest" && G) drawStrip(); if (MODE === "day" && DAY) drawDayStrip(); });
  requestAnimationFrame(tick);
}

function setMode(m) {
  // 10/23 지도 페이지는 '에이전트 한 명 / 여러 명' 두 모드만 — 예전 하루 전체 · 손님 한 팀 · 호텔 전체 화면으로 가는 길은 에이전트 모드로 돌린다(소스는 보존)
  if (m === "day" || m === "guest" || m === "report" || m === "ask" || m === "settings") m = MODE === "agents" ? "agents" : "agent";
  if (m === "auto") {   // CL-1024-18 자율 하루 — 화면 전체(static/autonomy.js) · 기존 고객흐름 상태는 건드리지 않음
    if (m !== MODE && typeof closeDrawer === "function") closeDrawer();
    MODE = m; setPlay(false);
    $$("nav .tab").forEach(b => b.classList.toggle("on", b.dataset.mode === "auto"));
    ["report", "evidence", "settings", "ask", "guest", "library", "opx"].forEach(k => $("main").classList.remove(k));
    $("main").classList.add("auto");
    auEnter();
    return;
  }
  $("main").classList.remove("auto");
  if (m === "opx") {   // CL-1024-17 운영 실험 — 화면 전체(static/opx.js) · 기존 고객흐름 상태는 건드리지 않음
    if (m !== MODE && typeof closeDrawer === "function") closeDrawer();
    MODE = m; setPlay(false);
    $$("nav .tab").forEach(b => b.classList.toggle("on", b.dataset.mode === "opx"));
    ["report", "evidence", "settings", "ask", "guest", "library", "auto"].forEach(k => $("main").classList.remove(k));
    $("main").classList.add("opx");
    opxEnter();
    return;
  }
  $("main").classList.remove("opx");
  if (m === "library") {   // 10/23 페르소나 라이브러리 — 화면 전체(static/library.js)
    if (m !== MODE && typeof closeDrawer === "function") closeDrawer();
    MODE = m; setPlay(false);
    $$("nav .tab").forEach(b => b.classList.toggle("on", b.dataset.mode === "library"));
    ["report", "evidence", "settings", "ask", "guest"].forEach(k => $("main").classList.remove(k));
    $("main").classList.add("library");
    libEnter();
    return;
  }
  $("main").classList.remove("library");
  if (m === "agent" || m === "agents") {
    if (m !== MODE && typeof closeDrawer === "function") closeDrawer();
    MODE = m; setPlay(false);
    $$("nav .tab").forEach(b => b.classList.toggle("on", b.dataset.mode === "day"));
    $$("#flowSeg button").forEach(b => b.classList.toggle("on", b.dataset.m === m));
    $("#flowSeg").classList.remove("hidden");
    ["report", "evidence", "settings", "ask"].forEach(k => $("main").classList.remove(k));
    $("main").classList.add("guest");
    $(".mode-guest").classList.add("hidden"); $(".mode-day").classList.add("hidden");
    $("#askView").classList.add("hidden"); $("#mapView").classList.add("hidden"); $("#routeAll").classList.add("hidden");
    $("#controls").classList.add("hidden"); $("#strip").classList.remove("hidden"); $("#strip").style.height = "";
    const vc = document.getElementById("visitCard"); if (vc) vc.classList.add("hidden");
    agEnter(m);
    return;
  }
  { const sa = document.querySelector(".mode-agent"); if (sa) sa.classList.add("hidden"); $("#strip").classList.remove("ag-off"); }
  // 10/19 UX 22차 · 소연 ③-8 — 상위 탭을 바꾸면 이전 화면에서 연 상세 창(drawer)을 닫는다 (같은 탭 안 이동은 그대로)
  if (m !== MODE && !(MODE === "day" && m === "guest") && !(MODE === "guest" && m === "day") && typeof closeDrawer === "function") closeDrawer();
  MODE = m;
  if (m !== "guest") { const vc = document.getElementById("visitCard"), vl = document.getElementById("vcline"); if (vc) vc.classList.add("hidden"); if (vl) vl.innerHTML = ""; VCKEY = ""; }
  // 10/14 메뉴 재구성 — 손님 한 팀은 '고객 흐름' 안의 두 번째 보기
  $$("nav .tab").forEach(b => b.classList.toggle("on", b.dataset.mode === (m === "guest" ? "day" : m)));
  $$("#flowSeg button").forEach(b => b.classList.toggle("on", b.dataset.m === m));
  $("#flowSeg").classList.toggle("hidden", m === "ask");      // 상황 비교에서는 '하루 전체 / 손님 한 팀' 선택이 쓰이지 않는다
  // 운영 요약 · 판단 근거 · 모델 설정은 화면 전체를 쓰는 쪽 — 지도 · 근거 패널은 '고객 흐름' 에서
  $("main").classList.toggle("report", m === "report");
  $("main").classList.toggle("evidence", m === "evidence");
  $("main").classList.toggle("settings", m === "settings");
  $("main").classList.toggle("guest", m === "guest");
  $("main").classList.toggle("ask", m === "ask");   // 10/17 UX 10차 · 상황 비교는 어시스턴트를 닫아 두고 필요할 때 연다 (main.as-on)
  if (m === "report") { setPlay(false); renderReport(); return; }
  if (m === "evidence") { setPlay(false); if (typeof renderBehavior === "function" && !(typeof EV !== "undefined" && EV.legacy)) renderBehavior(); else renderEvidence(); return; }   // 10/24 행동근거(이전 연구 화면은 EV.legacy 일 때만)
  if (m === "settings") { setPlay(false); renderSettings(); return; }
  $(".mode-guest").classList.toggle("hidden", m !== "guest");
  $(".mode-day").classList.toggle("hidden", m === "guest");
  $("#askView").classList.toggle("hidden", m !== "ask");
  $("#controls").classList.toggle("hidden", m === "ask"); $("#strip").classList.toggle("hidden", m === "ask");
  setPlay(false);
  $("#heat").innerHTML = ""; $("#trail").innerHTML = ""; $("#agent").innerHTML = "";
  $("#mapView").classList.toggle("hidden", m !== "day"); $("#routeAll").classList.toggle("hidden", !(m === "guest" && G)); $("#map").classList.remove("gfocus"); $("#mapLegend").classList.toggle("hidden", !(m === "day" || (m === "guest" && G)));
  $("#dim").innerHTML = ""; $("#route").innerHTML = "";
  $("#skipNight").parentElement.classList.toggle("hidden", m !== "guest"); $("#slowMove").parentElement.classList.toggle("hidden", m !== "guest");
  if (m === "guest") {
    $("#strip").style.height = "";
    $("#mapEmpty").classList.toggle("hidden", !!G);
    $("#mapEmpty").innerHTML = "왼쪽에서 ① 손님과 ② 환경을 정하고 ③ <b>실행</b>을 누르세요";
    for (const kk of Object.keys(LABSTAT)) delete LABSTAT[kk];
    if (G) { drawPins(); drawStrip(); drawFrame(); renderPanel(); } else { drawLabels(); $("#strip").innerHTML = ""; $("#panel").innerHTML = emptyPanel(); $("#clock b").textContent = "--:--"; $("#clock span").textContent = ""; }
  } else if (m === "ask") {
    $("#mapEmpty").classList.add("hidden");
    renderAsk();
  } else {
    $("#mapEmpty").classList.toggle("hidden", !!DAY);
    $("#mapEmpty").innerHTML = "왼쪽에서 날짜를 정하고 <b>하루 돌리기</b>를 누르거나, 계산해 둔 날을 고르세요";
    if (DAY) showDay(DAY); else { $("#strip").innerHTML = ""; $("#panel").innerHTML = `<div class="empty">하루 전체를 돌리면 지도에 업장별 인원이 뜨고,<br>업장을 누르면 회차별 점유율 · 수용 범위 초과 수요 ·<br>L4 상품 · L5 집계행이 나옵니다.</div>`; }
    drawPins();
  }
}
// 10/17 UX 1차 — 공통 상세 패널 (우측 drawer). 기본 화면에는 핵심만 두고, 긴 표 · 근거 · 대조는 여기서 연다.
//   openDrawer(title, sub, html, wire) — wire(root) 는 넣은 뒤 이벤트를 붙이는 함수. ESC · 닫기 · 바깥 클릭으로 닫는다.
function openDrawer(title, sub, html, wire, opts) {
  let d = document.getElementById("drawer");
  if (!d) {
    d = document.createElement("div"); d.id = "drawer"; d.className = "drawer hidden";
    d.innerHTML = `<div class="dr-head"><div class="dr-t"><b id="drTitle"></b><span id="drSub" class="hint"></span></div><button id="drClose" class="dr-x" title="닫기 (Esc)" aria-label="닫기">✕</button></div><div id="drBody" class="dr-body"></div>`;
    document.body.appendChild(d);
    const bg = document.createElement("div"); bg.id = "drawerBg"; bg.className = "drawer-bg hidden"; document.body.appendChild(bg);
    d.querySelector("#drClose").onclick = closeDrawer; bg.onclick = closeDrawer;
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !d.classList.contains("hidden")) closeDrawer(); });
  }
  d.classList.toggle("wide", !!(opts && opts.wide)); d.classList.remove("ag-narrow", "ds-narrow"); d.querySelector("#drTitle").textContent = title || "";
  d.querySelector("#drSub").textContent = sub || "";
  const body = d.querySelector("#drBody"); body.innerHTML = html || ""; body.scrollTop = 0;
  d.classList.remove("hidden"); document.getElementById("drawerBg").classList.remove("hidden");
  if (wire) try { wire(body); } catch (e) { console.error(e); }
}
// CL-1025-37 P3 — 표시 카드 번호(읽기 전용 레지스트리 static/display_registry.js). 화면 표시는 번호, 내부 라우팅 · 엔진 호출은 기존 ID 그대로.
//   승인된 P-#### 가 있으면 그것을 우선, 없으면 임시 표시 카드 번호 'No. ####'(사람 정본 번호 아님).
const HLD = () => (window.HL_DISPLAY && window.HL_DISPLAY.entries) || {};
// P6 — 근거 ID 표시: 기본 화면은 고객 내부 ID 접두어(A02- · blog41-)를 떼고 '근거 F08' 로. 개발 정보에서는 원래 ID
const fidD = f => document.body.classList.contains("devmode") ? String(f ?? "") : String(f ?? "").replace(/^(A\d{2}|blog\d{2})-/, "근거 ");
const idTxt = t => document.body.classList.contains("devmode") ? String(t ?? "") : String(t ?? "").replace(/\b(A\d{2}|blog\d{2})(?=[-\s·]|$)(?!-F|-X)/g, m => dno(m)).replace(/\b(A\d{2}|blog\d{2})-/g, "");
function dno(id) { const e = HLD()[id]; return e ? (e.p_id || `No.${e.no}`) : (id == null ? "" : String(id)); }
function dnoS(id) { const e = HLD()[id]; return e ? (e.p_id || e.no) : String(id || "").replace(/^blog/, "b"); }
function dnoResolve(q) { q = String(q || "").trim().replace(/^No\.?\s*/i, ""); const E = HLD(); if (E[q]) return q; const k = Object.keys(E).find(x => E[x].no === q.padStart(4, "0") || E[x].p_id === q); return k || q; }
function dnoParty(id) { const e = HLD()[id]; return e ? { n: e.party, origin: e.party_origin, label: e.party_label, scen: e.scenario_party } : { n: null, origin: "UNKNOWN", label: "동행 인원 확인 전" }; }
function closeDrawer() { const d = document.getElementById("drawer"), bg = document.getElementById("drawerBg"); if (d) d.classList.add("hidden"); if (bg) bg.classList.add("hidden"); }

const emptyPanel = () => `<div class="empty">손님을 돌리면 여기에 하루 요약이 나오고,<br>지도 아래 일정에서 행동을 누르면 <b>왜 그걸 골랐는지</b>가 나옵니다.</div>`;

// ---------------------------------------------------------------------------
// 설정
// ---------------------------------------------------------------------------
const isGuest = () => $("#fGuest .on").dataset.v === "1";
const curDate = () => LIB.dates.find(d => d.date === $("#fDate").value) || {};

function syncForm() {
  const g = isGuest();
  $$(".only-guest").forEach(e => e.classList.toggle("hidden", !g));
  $$(".only-day").forEach(e => e.classList.toggle("hidden", g));
  const fair = curDate().fair;
  $("#fScenario").disabled = !fair;
  if (!fair) $("#fScenario").value = "none";
  $("#wfWrap").classList.toggle("hidden", !(fair && $("#fScenario").value === "winefair"));
  if ($("#fKids").checked && $("#fProp").value === "DOUGLAS") $("#fProp").value = "GRAND";
  $("#fProp").querySelector('[value="DOUGLAS"]').disabled = $("#fKids").checked;
}

async function refreshPackages() {
  if (!isGuest()) return;
  const cfg = formCfg();
  const keep = $("#fPackage").value;
  try {
    const list = await api("/api/packages", cfg);
    $("#fPackage").innerHTML = `<option value="auto">자동 — 그 날 팔리는 상품 중 무작위 (생성기와 같음)</option><option value="none">정하지 않음</option>` +
      list.map(p => `<option value="${esc(p.name)}" data-incl="${esc(p.incl)}" data-meals="${esc(p.meals.map(m => m[0]).join(","))}" data-club="${p.club ? 1 : 0}" data-grade="${esc(p.grade)}">${esc(p.name)} · ${(p.krw / 10000).toFixed(1)}만</option>`).join("");
    if ([...$("#fPackage").options].some(o => o.value === keep)) $("#fPackage").value = keep;
    pkgHint();
  } catch (e) { $("#pkgHint").textContent = "상품 목록을 못 읽음: " + e.message; }
}
function pkgHint() {
  const o = $("#fPackage").selectedOptions[0];
  if (!o || !o.dataset.incl) { $("#pkgHint").textContent = o && o.value === "auto" ? "식사 포함 혜택 · 라운지는 고른 상품에서 정해집니다" : ""; return; }
  $("#pkgHint").innerHTML = `<span class="g ${gradeCls(o.dataset.grade)}">${esc(o.dataset.grade)}</span> 포함: ${esc(o.dataset.incl).slice(0, 120)}` +
    (o.dataset.meals ? ` · 식사 포함 혜택 ${esc(o.dataset.meals)}` : "") + (o.dataset.club === "1" ? " · 라운지" : "");
}

async function refreshDays() {
  const list = await api("/api/day/list");
  refreshDays.list = list;
  refreshCrowd();
  renderDayList();
}
// 10/17 UX — 목록 그리기를 분리: 날을 열 때 API 를 다시 부르지 않고 고른 날 표시만 바로 바꾼다
function renderDayList() {
  const list = refreshDays.list || [];
  const cur = d => d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver && !/반영 전/.test(d.knobs ? knobSummary(d) : "");   // 버전이 같아도 지금 v4 조정값이 빠진 예전 계산은 아래로
  const shown = list.filter(d => !(d.theta && d.theta.seed))     // 시드 묶음(band.py)의 시드 1~ 는 목록에서 숨김 — 범위 카드로만 본다
    .sort((a, b) => (cur(b) - cur(a)) || a.date.localeCompare(b.date));   // 10/14 지금 버전으로 계산한 날을 위로, 예전 계산은 아래에 흐리게
  // 10/16 한 줄 목록 — 날짜 · 행사 · 바꾼 상황만 한 줄로, 조정값은 '자세히' 안에 묶어서
  const open = refreshDays.open || (refreshDays.open = new Set());
  const now = shown.filter(cur), past = shown.filter(d => !cur(d));
  const pastOpen = refreshDays.pastOpen || (DAY && past.some(d => d.key === DAY.key));
  // 10/17 UX — 지금 기준 목록은 고른 날 + 최근 3개까지만 보이고 나머지는 '모두 보기' 로 접는다 (지시서 1-1)
  const SHOW = 4, curKey = DAY && DAY.key;
  const head = now.filter((d, i) => i < SHOW || d.key === curKey), rest = now.filter(d => !head.includes(d));
  const restOpen = refreshDays.restOpen || false;
  $("#dayList").innerHTML = shown.length ? head.map(d => dayRow(d, true, open.has(d.key))).join("") + (!now.length ? `<div class="hint">지금 기준으로 계산한 날이 아직 없습니다.</div>` : "")
    + (rest.length ? `<details class="dpast drest" ${restOpen ? "open" : ""}><summary>모두 보기 · ${rest.length}개 더</summary>${rest.map(d => dayRow(d, true, open.has(d.key))).join("")}</details>` : "")
    + (past.length ? `<details class="dpast" ${pastOpen ? "open" : ""}><summary>예전 기준으로 계산한 날 ${past.length}개</summary>${past.map(d => dayRow(d, false, open.has(d.key))).join("")}</details>` : "")
    : `<div class="hint">아직 없습니다.</div>`;
  const dp = $("#dayList .dpast:not(.drest)"); if (dp) dp.ontoggle = () => { refreshDays.pastOpen = dp.open; };
  const dr = $("#dayList .drest"); if (dr) dr.ontoggle = () => { refreshDays.restOpen = dr.open; };
  $$("#dayList .d .dr").forEach(e => e.onclick = () => loadDay(e.parentElement.dataset.key));
  $$("#dayList .d .dmore").forEach(b => b.onclick = ev => {
    ev.stopPropagation();
    const box = b.closest(".d"), k = box.dataset.key, on = !box.classList.contains("open");
    box.classList.toggle("open", on); b.setAttribute("aria-expanded", on); on ? open.add(k) : open.delete(k);
  });
}
// 계산해 둔 날 한 줄: 날짜(요일) · 행사 · 바꾼 상황 태그 · 팀 수
const KNOB_GROUP = [
  ["손님 구성", ["meal_split", "order_mix", "purpose_onto", "rng_team", "wd_day", "wd_dine", "wd_named", "wd_biz", "biz_party", "search_w", "posting_k", "trend_w"]],
  ["업장 · 좌석 · 회차", ["no_busy_dwell", "turn_hold", "next_window", "queue_max", "reserve_wait", "wait_horizon", "buffet_seats", "moegi_seats", "fine_dwell", "takeout_cap", "takeout_base", "bar_nightcap", "passage_rate"]],
  ["객실", ["rooms_onto", "rooms_formula"]],
];
const KNOB_SKIP = new Set(["anomaly", "anomaly_k", "hypo", "seed"]);
function dayTags(d) {   // 한 줄에 보일 '바꾼 것' — 기본(v4)과 다른 것만
  if (!d.knobs) return ["기본 모델"];
  const k = knobParts(d);
  return [...k.extra.map(x => x.replace(/^변동 상황: /, "").replace(/^(가설 H\d+) .*/, "$1")), ...(k.base === "조정값 직접 설정" ? [k.base] : [])];   // 'v4 (… 반영 전)' 은 '예전 기준' 표시와 자세히 안의 모델 줄로
}
const KNOB_FLAG = new Set(["next_window", "reserve_wait", "purpose_onto", "turn_hold", "rooms_onto", "order_mix", "wd_named", "wd_biz", "biz_party", "rooms_formula", "rng_team"]);
// 조정값 이름과 값을 읽기 좋게 — 켜고 끄는 것은 '켬', 비율은 %, 단위가 이름에 붙은 것은 값 뒤로
function knobPair(k, v) {
  let name = nmDisp(((LIB.knobs || {})[k] || {}).name || k), val;
  if (k === "meal_split") val = v == 2 ? "막혔을 때만" : "식사 시간대마다";
  else if (k === "no_busy_dwell") val = v == 2 ? "중식 · 석식만 끔" : "조식까지 모두 끔 (실험)";
  else if (KNOB_FLAG.has(k)) val = "켬";
  else {
    const u = name.match(/\s*\((분|판)\)\s*$/);
    const n = typeof v === "number" ? +v.toFixed(3) : v;
    if (u) { name = name.replace(u[0], ""); val = `${n}${u[1]}`; }
    else if (/비율/.test(name) && typeof v === "number" && v <= 1) val = `${Math.round(v * 100)}%`;
    else if (/배율|배수/.test(name)) val = `×${n}`;
    else if (/좌석$/.test(name)) val = `${n}석`;
    else val = String(n);
  }
  return `<dt>${esc(name)}</dt><dd>${esc(val)}</dd>`;
}
function dayRow(d, isCur, isOpen) {
  const dt = new Date(d.date + "T00:00:00"), md = `${dt.getMonth() + 1}/${dt.getDate()} (${"일월화수목금토"[dt.getDay()]})`;
  const tags = dayTags(d), th = d.theta || {}, K = LIB.knobs || {};
  const an = th.anomaly ? (LIB.anomalies || []).find(x => String(x.ID) === String(th.anomaly)) : null;
  const sit = th.anomaly ? `변동 상황 ${an ? an.이름 : th.anomaly}${th.anomaly_k && th.anomaly_k != 1 ? ` ×${th.anomaly_k}` : ""}` : th.hypo ? `가설 H${th.hypo}` : "추가 변동 없음";
  const model = d.knobs ? knobParts(d).base : "기본 모델";
  // 조정값은 'v4 기본과 다른 것' 을 먼저, v4 기본 그대로인 것은 한 번 더 접어서
  const p4 = v4For(d.date), keys = new Set([...Object.keys(th), ...Object.keys(p4)].filter(k => !KNOB_SKIP.has(k) && K[k]));
  const val = k => k in th ? th[k] : K[k].default;
  const isSet = k => val(k) != null && val(k) !== K[k].default;
  const diff = [...keys].filter(k => (k in p4 ? val(k) !== p4[k] : isSet(k)));
  const same = [...keys].filter(k => k in p4 && val(k) === p4[k]);
  const pair = k => isSet(k) ? knobPair(k, val(k)) : `<dt>${esc(nmDisp(K[k].name).replace(/\s*\((분|판)\)\s*$/, ""))}</dt><dd class="off">꺼짐</dd>`;
  const grouped = ks => { const used = new Set(), out = KNOB_GROUP.map(([g, gk]) => { const r = gk.filter(k => ks.includes(k)); r.forEach(k => used.add(k)); return r.length ? `<div class="dg"><b>${g}</b><dl>${r.map(pair).join("")}</dl></div>` : ""; }).join(""); const rest = ks.filter(k => !used.has(k)); return out + (rest.length ? `<div class="dg"><b>기타</b><dl>${rest.map(pair).join("")}</dl></div>` : ""); };
  const knobHtml = !d.knobs ? `<div class="hint dk">조정값 없이 기본 모델로 계산한 날입니다.</div>`
    : `<div class="dk">${diff.length ? `<div class="dhd">${V4N} 기본과 다른 조정값</div>${grouped(diff)}` : `<div class="dhd">조정값은 ${V4N} 기본 그대로</div>`}
       ${same.length ? `<details class="dv4"><summary>${V4N} 기본 조정값 ${same.length}개</summary>${grouped(same)}</details>` : ""}</div>`;
  const det = `<div class="ddet">
      <dl class="dsum"><dt>상황</dt><dd>${d.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${esc(sit)}</dd>
      <dt>모델</dt><dd>${esc(model)} · 규모 ${Math.round(d.scale * 100)}%</dd>
      <dt>손님</dt><dd>${d.n.toLocaleString()}팀</dd>
      <dt>계산</dt><dd>${esc(d.built.replace("T", " ").slice(0, 16))}${isCur ? "" : " · 예전 기준"}</dd></dl>
      ${knobHtml}
      <div class="dev dkey">${esc(d.key)}<br>${esc(d.knobs || "")}</div>
    </div>`;
  return `<div class="d ${DAY && DAY.key === d.key ? "on" : ""} ${isCur ? "" : "old"} ${isOpen ? "open" : ""}" data-key="${d.key}" title="${isCur ? "" : "지금 기준보다 예전 조건으로 계산한 날입니다. 기록으로만 남겨 둡니다"}">
    <div class="dr"><span class="dd">${md}</span>${d.scenario === "winefair" ? `<span class="dt ev">와인페어</span>` : ""}${tags.map(t => `<span class="dt">${esc(t)}</span>`).join("")}${isCur ? "" : `<span class="dt old">예전 기준</span>`}<span class="dn">${d.n.toLocaleString()}팀</span><button class="dmore" aria-expanded="${isOpen}" aria-label="계산 조건 자세히" title="계산 조건 자세히"></button></div>${det}</div>`;
}
function refreshCrowd() {
  const list = (refreshDays.list || []).filter(d => d.date === $("#fDate").value && d.scenario === $("#fScenario").value && !(d.theta && d.theta.seed));
  const keep = $("#fCrowd").value;
  const cur = d => d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver;
  const lab = d => `손님 ${d.n.toLocaleString()}팀과 함께` + (envIsBase(d) ? "" : ` · ${esc(d.knobs ? knobSummary(d).replace(V4_LABEL() + " · ", "") : "기본 모델")}`) + `${d.scale !== 1 ? ` (규모 ${Math.round(d.scale * 100)}%)` : ""}${cur(d) ? "" : " · 예전 계산"}`;
  list.sort((a, b) => (envIsBase(b) - envIsBase(a)) || (cur(b) - cur(a)));
  $("#fCrowd").innerHTML = `<option value="">혼자 · 좌석 경쟁 없음</option>` + list.map(d => `<option value="${d.key}">${lab(d)}</option>`).join("");
  if ((keep || refreshCrowd.touched) && [...$("#fCrowd").options].some(o => o.value === keep)) $("#fCrowd").value = keep;
  else $("#fCrowd").value = defaultEnvKey();
  crowdHint();
}
function crowdHint() {
  const n = (refreshDays.list || []).filter(d => d.date === $("#fDate").value && d.scenario === $("#fScenario").value).length;
  $("#crowdHint").textContent = n ? "" : "이 날짜는 하루 전체 계산이 없어 혼자만 돌릴 수 있습니다 (하루 전체 탭에서 계산하면 생김).";
}

function formCfg() {
  return {
    date: $("#fDate").value, scenario: $("#fScenario").value, crowd: $("#fCrowd").value,
    is_guest: isGuest(), property: $("#fProp").value, nights: +$("#fNights").value, party: +$("#fParty").value,
    kids: $("#fKids").checked, sex: $("#fSex").value, age: $("#fAge").value, purpose: $("#fPurpose").value,
    package: $("#fPackage").value || "auto", prefers: $("#fPrefer").value, wf_go: $("#fWf").checked && !$("#wfWrap").classList.contains("hidden"),
    arrive: $("#fArrive").value, depart: $("#fDepart").value, wake: $("#fWake").value, arrival: $("#fArrival").value, seed: +$("#fSeed").value || 7,
    anomaly: $("#fAnom").value || null,     // 10/14 변동 상황 — 휴업 · 가격 · 가고 싶음 배율을 이 손님에게도 (손님 수 배율은 '다른 손님' 날에 들어 있다)
  };
}

function setGuest(on) { $$("#fGuest button").forEach(x => x.classList.toggle("on", (x.dataset.v === "1") === on)); }

async function preset(k) {
  const P = {
    A: { guest: false, party: 2, kids: false, sex: "여성", age: "20~29세", purpose: "커플·기념일", wf: true, arrive: "11:00", depart: "22:00" },
    B: { guest: true, prop: "GRAND", nights: 2, party: 3, kids: true, sex: "여성", age: "30~49세", purpose: "가족·친족", wf: true, arrive: "15:00", pkg: "캠크닉 인더 포레스트 TYPE 1" },
    C: { guest: true, prop: "VISTA", nights: 2, party: 2, kids: false, sex: "남성", age: "50세 이상", purpose: "휴식·산책 동행", wf: true, arrive: "15:00", pkg: "auto" },
    D: { guest: false, party: 4, kids: true, sex: "여성", age: "30~49세", purpose: "가족·친족", wf: false, arrive: "11:00", depart: "22:00" },
  }[k];
  $("#fDate").value = "2026-10-10"; $("#fScenario").value = "winefair";
  setGuest(P.guest);
  if (P.prop) $("#fProp").value = P.prop;
  if (P.nights) $("#fNights").value = P.nights;
  $("#fParty").value = P.party; $("#fKids").checked = P.kids; $("#fSex").value = P.sex; $("#fAge").value = P.age; $("#fPurpose").value = P.purpose;
  $("#fArrive").value = P.arrive; if (P.depart) $("#fDepart").value = P.depart;
  $("#fPrefer").value = "auto";
  syncForm(); $("#fWf").checked = P.wf;
  await refreshPackages(); refreshCrowd();
  if (P.pkg && [...$("#fPackage").options].some(o => o.value === P.pkg)) { $("#fPackage").value = P.pkg; pkgHint(); }
  $$(".presets button[data-preset]").forEach(b => b.classList.toggle("on", b.dataset.preset === k));
  GRIDPICK = { preset: k }; $$("#gridList tr.on").forEach(r => r.classList.remove("on"));
  personaCard();
  readyHint(`${k} 손님을 채웠습니다. 세부 값에서 고칠 수 있습니다`);
}
function readyHint(msg) {
  const b = $("#btnRun");
  b.title = msg;
  $("#runHint").style.color = "var(--ink2)"; $("#runHint").textContent = msg;
}

async function randomGuest(row) {
  const seed = row != null ? (+$("#fSeed").value || 7) : Math.floor(Math.random() * 1e6);
  const r = await api("/api/random?seed=" + seed + (row != null ? "&row=" + row : ""));
  setGuest(r.is_guest);
  $("#fParty").value = Math.min(6, r.party); $("#fKids").checked = r.kids; $("#fSex").value = r.sex; $("#fAge").value = r.age; $("#fPurpose").value = r.purpose;
  $("#fNights").value = Math.min(3, r.nights); $("#fArrive").value = r.is_guest ? "15:00" : (Math.random() < 0.4 ? "11:00" : "17:00");
  $("#fPackage").value = "auto"; $("#fPrefer").value = "auto";
  syncForm(); await refreshPackages();
  $$(".presets button").forEach(b => b.classList.remove("on"));
  GRIDPICK = { row: r.row_i, seed: r.seed, src: r.row, random: row == null };
  $$("#gridList tr").forEach(t => t.classList.toggle("on", +t.dataset.i === r.row_i));
  personaCard();
  readyHint(row != null ? `유형표 ${r.row_i + 1}번 줄로 한 팀을 만들었습니다` : `무작위로 유형표 ${r.row_i + 1}번 줄이 나왔습니다`);
}

// ---------------------------------------------------------------------------
// 손님 한 팀
// ---------------------------------------------------------------------------
// 고른 후기 — 본문 링크(로컬 파일 links.local.csv 에 있을 때) · 이 손님 설정 요약
// 10/17 카드 정리 — 제목은 'blog16 · 비스타 워커힐', 아래 줄에 세부 조건만. 상태 배지는 중립색,
//   빨간색은 실제로 누르는 '이 설정으로 편집' 버튼에만. '본문 후기 보기' 는 테두리 버튼으로 나란히
const rvTitle = r => {
  const ab = (/^(?:\[[^\]]*\]\s*)?blog\d+\s*([A-Z])\b/.exec(r.name || "") || [])[1];
  const prop = r.is_guest ? ((LIB.prop_names || {})[r.property] || r.property) : "비투숙";
  return `${r.blog}${ab ? " " + ab : r.alt ? " 둘째 체류" : ""} · ${prop}`;
};
// 후기 이름에서 숙소 · 박 수 · 인원처럼 이미 다른 칸에 있는 말을 빼고 남는 설명 (예: '회사 휴양소' · '스카이야드')
const rvTag = r => ((/^\[([^\]]*)\]/.exec(r.name || "") || [])[1] || "").replace(/^자동$/, "자동 추출");
const rvExtra = r => (r.name || "").replace(/^(?:\[[^\]]*\]\s*)?blog\d+\s*[A-Z]?\s*[·:]?\s*/, "")
  .split(/\s*[·()]\s*/)
  .map(t => t.replace(/(그랜드|비스타|더글라스(\s*하우스)?)(\s*워커힐)?|\d+\s*박|\d+\s*인|비투숙/g, " ").replace(/\s+/g, " ").trim())
  .filter(Boolean).join(" · ");
const ICON_EDIT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h4M12 17h8M16 5v4M10 15v4"/></svg>';
const ICON_OUT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
function reviewInfo() {
  const r = (LIB.review_list || [])[+$("#fReview").value];
  const el = $("#reviewInfo");
  if (!r) { el.innerHTML = ""; return; }
  const x = rvExtra(r);
  const xs = x.length > 24 ? x.slice(0, 23) + "…" : x;
  const who = [r.is_guest ? `${r.nights}박` : "비투숙", `${r.party}명`, r.kids && !/아이/.test(x) ? "아이 동반" : null, r.purpose || xs || null].filter(Boolean).join(" · ");
  const tag = rvTag(r);
  const when = [r.start ? `후기 날짜 ${dShort(r.start)}` : null, `방문 장소 ${r.n_truth}곳`].filter(Boolean).join(" · ");
  // 10/17 UX 3차 · 같은 정보 한 번씩 · 버튼은 둘 다 보조 버튼 (주 버튼은 ③ '이 조건으로 실행' 하나)
  el.innerHTML = `<div class="rv-meta rv-who" title="${esc(r.name)}">${esc(who)}</div>
    <div class="rv-meta">${esc(when)}</div>${tag ? `<div class="rv-badges"><span class="badge" title="페르소나 정답 확인 상태">${esc(tag)}</span></div>` : ""}
    <div class="rv-acts">
      <button class="rv-btn" id="toCustom" title="이 후기 손님의 값으로 '직접 만들기' 를 채워 편집합니다">${ICON_EDIT}<span>설정 편집</span></button>
      ${r.link ? `<a class="rv-btn" href="${esc(r.link)}" target="_blank" rel="noopener" title="새 창에서 블로그 본문을 엽니다">${ICON_OUT}<span>본문 보기</span></a>`
        : `<span class="rv-btn off" title="본문 주소가 아직 연결되지 않은 글입니다">${ICON_OUT}<span>본문 링크 없음</span></span>`}
    </div>`;
}

// ---------------------------------------------------------------------------
// 10/16 손님 한 팀 — ① 누구를 ② 어떤 상황에 ③ 원래와 무엇이 달라졌나
// ---------------------------------------------------------------------------
let SRC = "blog";          // 페르소나 경로: blog · grid · custom
let GRIDPICK = null;       // 유형표에서 고른 줄 · 시드 (같은 손님으로 다시 비교하려고 남긴다)
const curReview = () => (LIB.review_list || [])[+$("#fReview").value];

function setSrc(k) {
  SRC = k;
  $$("#srcSeg button").forEach(b => b.classList.toggle("on", b.dataset.s === k));
  $$(".mode-guest .src").forEach(e => e.classList.toggle("hidden", e.dataset.s !== k));
  $("#pDetail").classList.toggle("hidden", k === "blog");
  if (k === "custom") $("#pDetail").open = true;
  if (k === "grid" && !GRIDPICK) $("#gridPick").open = true;
  personaCard(); sitSync();
}
// 지금 운영(v4 기본)으로 그 날 손님을 모두 돌린 하루 — '기준 운영' 의 환경
function envIsBase(d) { return !!d && !(d.theta && d.theta.seed) && d.knobs != null && knobSummary(d) === V4_LABEL(); }
function defaultEnvKey(date, scen) {
  date = date || $("#fDate").value; scen = scen || $("#fScenario").value;
  const L = (refreshDays.list || []).filter(d => d.date === date && d.scenario === scen && envIsBase(d));
  const cur = L.find(d => d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver);
  return (cur || L[0] || {}).key || "";
}
const dShort = s => `${s.slice(5, 7).replace(/^0/, "")}/${s.slice(8, 10).replace(/^0/, "")}`;
// 10/17 UX 2차 · ③ 세 가지 실행 목적의 설명 글 — (a) 이 조건으로 실행 (b) 같은 날짜의 기준 운영과 비교 (c) 후기 행동 재현 평가 (블로그 손님만)
function sitSync() {
  const blog = SRC === "blog", env = defaultEnvKey();
  const same = !$("#fAnom").value && $("#fCrowd").value === env;
  $("#runCmpTxt").textContent = same ? "② 조건을 바꾸면 비교할 수 있어요" : "";
  $("#btnCmp").disabled = same;
  $("#runHint").textContent = "";
  $("#revCheck").classList.toggle("hidden", !blog);
  if (blog) { const r = curReview(); $("#reviewHint").textContent = r ? `· 후기 날짜${r.start ? ` ${dShort(r.start)}` : ""} · 좌석 경쟁 없이` : ""; }
}
function personaCard() {
  const el = $("#personaCard"); if (!el || !LIB) return;
  let title, meta, badge;
  if (SRC === "blog") {
    el.innerHTML = "";           // 후기 손님은 위 후기 카드가 곧 페르소나 카드
    const b = $("#toCustom"); if (b) b.onclick = reviewToCustom;
    return;
  } else {
    const g = isGuest();
    title = `${$("#fPurpose").value} · ${$("#fSex").value} ${$("#fAge").value}`;
    meta = [g ? `${{ GRAND: "그랜드", VISTA: "비스타", DOUGLAS: "더글라스" }[$("#fProp").value]} ${$("#fNights").value}박` : "비투숙", `${$("#fParty").value}인`, $("#fKids").checked ? "아이 동반" : null, `도착 ${$("#fArrive").value}`].filter(Boolean).join(" · ");
    const P = GRIDPICK || {};
    badge = SRC === "grid" ? (P.preset ? `<span class="badge">시연용 손님 ${P.preset}</span>` : P.row != null ? `<span class="badge">유형표 ${P.row + 1}번 줄 · 시드 ${P.seed}</span>${P.edited ? `<span class="badge warn">값 고침</span>` : ""}` : `<span class="hint">아직 고르지 않았습니다</span>`)
      : `<span class="badge">직접 만든 손님</span>`;
  }
  el.innerHTML = `<div class="pc-t">${esc(title)}</div><div class="pc-m">${esc(meta)}</div><div class="pc-b">${badge}</div>`;
  const b = $("#toCustom"); if (b) b.onclick = reviewToCustom;
}
async function reviewToCustom() {
  const r = curReview(); if (!r) return;
  setGuest(r.is_guest);
  if (r.is_guest) { $("#fProp").value = r.property; $("#fNights").value = Math.min(3, r.nights); }
  $("#fParty").value = Math.min(6, r.party); $("#fKids").checked = !!r.kids; if (r.purpose) $("#fPurpose").value = r.purpose;
  if (r.start) $("#fArrive").value = r.start.slice(11, 16);
  syncForm(); await refreshPackages();
  setSrc("custom");
  readyHint(`${r.blog} 의 인원 · 객실 · 목적을 가져왔습니다. 식사 포함 혜택 · 동선 근거는 후기 손님만 갖고 있어 여기서는 다시 정해집니다`);
}

// 고객 유형표 — 줄 전체를 목적 · 연령 · 대표자 · 숙박 · 아이 동반으로 걸러 고른다
function gridInit() {
  const R = LIB.grid || [];
  const opts = k => [...new Set(R.map(r => r[k]))].map(v => `<option>${esc(v)}</option>`).join("");
  $("#gfPurpose").innerHTML = `<option value="">전체</option>` + opts("purpose");
  $("#gfAge").innerHTML = `<option value="">전체</option>` + opts("age");
  $("#gfSex").innerHTML = `<option value="">전체</option>` + opts("sex");
  gridRender();
}
const gNum = s => +String(s).split(":")[0];
function gridRender() {
  const R = (LIB.grid || []).filter(r => (!$("#gfPurpose").value || r.purpose === $("#gfPurpose").value) && (!$("#gfAge").value || r.age === $("#gfAge").value)
    && (!$("#gfSex").value || r.sex === $("#gfSex").value) && ($("#gfStay").value === "" || gNum(r.nights) === +$("#gfStay").value) && (!$("#gfKids").checked || +r.kids > 0))
    .sort((a, b) => b.share - a.share);
  $("#gridCount").textContent = `(${R.length} / ${(LIB.grid || []).length}줄)`;
  $("#gridList").innerHTML = `<table class="t gt"><tr><th>#</th><th>목적</th><th>대표자</th><th class="n">인원</th><th>숙박</th><th class="n">비중</th></tr>` +
    R.map(r => `<tr data-i="${r.i}" class="${GRIDPICK && GRIDPICK.row === r.i ? "on" : ""}${r.share ? "" : " off"}" title="${esc(r.src)}${r.share ? "" : " · 하루 생성에는 쓰지 않는 줄"}"><td class="hint">${r.i + 1}</td><td>${esc(r.purpose)}</td><td>${esc(r.sex)} ${esc(r.age)}</td><td class="n">${gNum(r.party)}인${+r.kids ? " · 아이" : ""}</td><td>${gNum(r.nights) ? gNum(r.nights) + "박" : "비투숙"}</td><td class="n">${r.share ? (r.share * 100).toFixed(2) + "%" : "-"}</td></tr>`).join("") + `</table>`;
  $$("#gridList tr[data-i]").forEach(t => t.onclick = () => randomGuest(+t.dataset.i));
}

// 실행 요청 세 가지 — baseReq(true): 선택 날짜의 기준 운영 (추가 변동 없음 · 그 날 손님들과 함께) = 비교의 기준 · baseReq(false): 후기 행동 재현 평가 (후기 날짜 · 좌석 경쟁 없이, 블로그 손님만)
//   changedReq(): ②에서 고른 날짜 · 행사 · 변동 상황 · 좌석 경쟁 그대로 = '이 조건으로 실행'
function baseReq(cmp) {
  const c = formCfg();
  if (SRC === "blog") {
    const r = curReview();
    // 비교의 기준은 후기 손님을 ②와 같은 날짜 · 추가 변동 없음 · 기준 운영에 놓은 것 (날짜 차이가 섞이지 않게). 후기 재현 평가는 따로(③ 별도 검증)
    return cmp ? { url: "/api/review", body: { blog: r.blog, alt: r.alt, situation: 1, date: c.date, scenario: c.scenario, anomaly: null, crowd: defaultEnvKey() } }
      : { url: "/api/review", body: { blog: r.blog, alt: r.alt } };
  }
  return { url: "/api/guest", body: Object.assign(formCfg(), { anomaly: null, crowd: defaultEnvKey() }) };
}
function changedReq() {
  const c = formCfg();
  if (SRC === "blog") { const r = curReview(); return { url: "/api/review", body: { blog: r.blog, alt: r.alt, situation: 1, date: c.date, scenario: c.scenario, anomaly: c.anomaly, crowd: c.crowd } }; }
  return { url: "/api/guest", body: c };
}
const runOf = async q => { const r = await api(q.url, q.body); r._crowd = q.body.crowd || null; r._req = q.body; return r; };
async function runSim(kind) {
  kind = kind || "one";
  if (SRC === "blog" && !curReview()) { $("#runHint").textContent = "후기 목록을 못 읽었습니다. 화면 서버(app.py)를 껐다 켠 뒤 새로고침해 주세요."; return; }
  if (kind === "rev" && SRC !== "blog") return;
  const b = $({ one: "#btnRun", cmp: "#btnCmp", rev: "#btnRev" }[kind]); const all = [$("#btnRun"), $("#btnCmp")];
  all.forEach(x => x.disabled = true); const lbl = b.innerHTML; b.textContent = "돌리는 중…"; $("#runHint").textContent = "";
  try {
    if (kind === "cmp") {
      const [A, B] = await Promise.all([runOf(baseReq(true)), runOf(changedReq())]);
      for (const r of [A, B]) if (r._crowd) await ensureDay(r._crowd);
      B._cmp = { A, blog: SRC === "blog" };
      showGuest(B);
    } else {
      const res = await runOf(kind === "rev" ? baseReq(false) : changedReq());
      if (res._crowd) await ensureDay(res._crowd);
      showGuest(res);
    }
    if (SRC !== "blog") $$(".presets button").forEach(x => x.classList.toggle("on", GRIDPICK && x.dataset.preset === GRIDPICK.preset));
  } catch (e) { alertPanel(e.message); }
  b.innerHTML = lbl; sitSync(); $("#btnRun").disabled = false;
}

// 식사 시간대별로 어디서 먹었나 — 기준 운영 · 변경 운영을 같은 줄에 놓으려고 '몇째 날 · 조식/중식/석식' 으로 묶는다
function mealsOf(R) {
  const d0 = Date.parse(R.persona.start.slice(0, 10));
  const out = {};
  for (const s of R.steps) {
    if (!(s.kind === "meal" || s.key === "meal_other")) continue;
    const h = +s.t_in.slice(11, 13), day = Math.round((Date.parse(s.t_in.slice(0, 10)) - d0) / 864e5) + 1;
    const k = `${day}일차 ${h < 11 ? "조식" : h < 16 ? "중식" : "석식"}`;
    const nm = s.key === "meal_other" ? "호텔 밖 · 객실 식사" : (locName(s.venue || s.location) || s.label);
    out[k] = out[k] ? out[k] + " · " + nm : nm;
  }
  return out;
}
const nSwitch = R => R.steps.filter(s => s.switch && s.switch["원래"]).length;
const fnbOf = R => (R.spend_by_l2 || {})["F&B"] || 0;
const envName = R => { if (!R._crowd) return "혼자 (좌석 경쟁 없음)"; const d = (refreshDays.list || []).find(x => x.key === R._crowd); return (d && envIsBase(d) ? `지금 운영 (${V4N})` : dayLabel(R._crowd).replace(/^\d+\/\d+ · (행사 없음|와인페어 있음) · (온톨로지 정합 v4 · )?/, "")) + " · 그 날 손님들과 함께"; };
function legsOf(R) {
  const segs = R.segments.map(s => ({ ...s, a: tmin(s.t_in), b: tmin(s.t_out) })).sort((x, y) => x.a - y.a);
  const out = []; let prev = segs.length ? segs[0].location : "HOTEL_GATE";
  for (const s of segs) { if (s.location !== prev) out.push(route(prev, s.location)); prev = s.location; }
  return out;
}
function alertPanel(msg) { $("#panel").innerHTML = `<div class="callout">계산 실패 — ${esc(msg)}</div>`; }

async function ensureDay(key) {
  if (!key) return null;
  if (!DAYCACHE[key]) DAYCACHE[key] = await api("/api/day/result?key=" + encodeURIComponent(key));
  return DAYCACHE[key];
}

function showGuest(res) {
  G = res; SEL = null;
  const segs = res.segments.map(s => ({ ...s, a: tmin(s.t_in), b: tmin(s.t_out) })).sort((x, y) => x.a - y.a);
  const steps = res.steps.map(s => ({ ...s, a: tmin(s.t_in), b: s.t_out ? tmin(s.t_out) : tmin(s.t_in) + 5 }));
  // 구간마다: 직전 장소에서 이동 → (대기) → 이 구간. 이동 분은 그 행동 트레이스의 travel
  let prevLoc = segs.length ? segs[0].location : "HOTEL_GATE", prevEnd = segs.length ? segs[0].a - 10 : 0;
  const legs = [];
  for (const s of segs) {
    const st = steps.find(x => Math.abs(x.a - s.a) < 0.5 && x.location === s.location) || steps.find(x => Math.abs(x.a - (s.a + 3)) < 0.5 && x.location === s.location);
    if (s.location !== prevLoc) {
      const r = route(prevLoc, s.location);
      // 10/17 8차 · 이동 시간은 모델 값(travel)만 쓴다. 모델 값이 없는 이동은 지도 그림의 길이로 시간을 지어내지 않고 2분 전환으로만 보인다
      //   → 지도 길 · 건물 묶음을 바꿔도 화면의 시각 · 순서가 바뀌지 않는다
      let tr = st && st.travel != null ? st.travel : 2;
      // 10/19 K1 · 엔진이 행동 기록 없이 끼워 넣는 '객실에서 대기'(IN_ROOM)는 시작이 '직전 끝 + 객실까지 이동' 으로 정해진다(agent_v4 객실 대기 삽입).
      //   → 그 차이 전체가 모델의 이동 시간이라 2분 전환 대신 그대로 쓴다. 지어내는 값 없음 · 30분 넘는 차이는 이동으로 보지 않음
      if (!st && s.state === "IN_ROOM" && s.a - prevEnd > tr && s.a - prevEnd <= 30) tr = s.a - prevEnd;
      tr = Math.max(1, Math.min(tr, s.a - prevEnd));
      legs.push({ from: prevLoc, to: s.location, a: prevEnd, b: prevEnd + tr, r, next: st || s, ...markerPath(prevLoc, s.location, r) });
    }
    prevLoc = s.location; prevEnd = s.b;
  }
  G.segs = segs; G.st = steps; G.legs = legs; G.iv = buildStates();   // 19차 · 공통 상태 구간표
  G.t0 = (segs[0] ? segs[0].a : steps[0].a) - 10;
  G.t1 = Math.max(...segs.map(s => s.b), ...steps.map(s => s.b));
  T = G.t0;
  $("#mapEmpty").classList.add("hidden");
  drawPins(); drawStrip(); drawFrame(); renderPanel();
  setPlay(true);
}

// 10/17 9차 · 위치 표시가 따라 움직이는 길 — 출발 장소 점 → (지도에 그린 길) → 도착 장소 점.
//   선은 지금처럼 그린 길(r.pts)만 긋고, 장소 점 ↔ 진입점 · 건물 안 · 연결 통로 · 가까운 곳은 선 없이 위치 표시만 옮긴다 → 이동 시작 · 끝에서 위치가 튀지 않는다
//   시각은 모델 이동 시간(행동 시작 · 끝) 그대로이고, 그 사이를 화면에서만 나눠 보간한다 (행동 결과 · 이동 시간은 바꾸지 않음)
function polyR(pts) { const lens = [0]; for (let i = 1; i < pts.length; i++) lens.push(lens[i - 1] + dist(pts[i - 1], pts[i])); return { pts, lens, total: lens[lens.length - 1] }; }
function markerPath(a, b, r) {
  const pa = LOC[a], pb = LOC[b];
  if (!pa || !pb) return { mk: r, l0: 0 };
  if (r.internal || r.link || r.near) return { mk: polyR([pa, pb]), l0: 0 };
  if (r.unknown || r.pts.length < 1) return { mk: r, l0: 0 };
  return { mk: polyR([pa, ...r.pts, pb]), l0: dist(pa, r.pts[0]) };
}
// 그린 길을 f(0~1)에서 둘로 — 지나온 쪽 · 남은 쪽
function cutPts(r, f) {
  const L = Math.max(0, Math.min(1, f)) * r.total, a = [r.pts[0]], b = [];
  for (let i = 1; i < r.pts.length; i++) {
    if (!b.length && r.lens[i] <= L) a.push(r.pts[i]);
    else { if (!b.length) { const q = along(r, L / (r.total || 1)); a.push(q); b.push(q); } b.push(r.pts[i]); }
  }
  if (!b.length) b.push(r.pts[r.pts.length - 1]);
  return [a, b];
}
// 지도 보기 — 기본은 '지금 행동' (현재 이동 구간 · 현재 위치만 진하게). '전체 동선 보기' 를 누르면 하루 동선 · 들른 순서 번호 · 비교 기준 동선
let ROUTEALL = false, BFKEY = "";
// 지금 있는 곳 · 가는 곳의 건물 모양 (건물이면 업장 점들을 감싼 타원, 건물 밖 장소면 그 점 둘레 원)
function focusShape(loc) {
  const b = loc && bldgOf(loc);
  if (b && BLDG[b]) { const e = bldgHL(b); return { id: b, el: `<ellipse cx="${e.cx}" cy="${e.cy}" rx="${e.rx + 14}" ry="${e.ry + 12}"/>` }; }
  const p = loc && LOC[loc]; return p ? { id: loc, el: `<circle cx="${p[0]}" cy="${p[1]}" r="38"/>` } : null;
}
function setRouteAll(on) {
  ROUTEALL = !!on;
  $$("#routeAll button").forEach(b => { b.classList.toggle("on", (b.dataset.r === "all") === ROUTEALL); b.setAttribute("aria-pressed", (b.dataset.r === "all") === ROUTEALL ? "true" : "false"); });
  // 16차 · 모드가 바뀌면 오른쪽 카드(지금 행동 ↔ 전체 동선 요약) · 지도 전체 경로 · 말풍선 자리를 처음부터 다시 그린다
  NOWSTEP_I = null; RCKEY = ""; RAKEY = ""; RCHL = null; RCOPEN.clear(); RC_CUR = -2; NOWTAG.key = "";
  if (G && MODE === "guest") { drawPins(); BUBPOS.key = ""; drawFrame(); }
}
// ---------------------------------------------------------------------------
// 10/17 UX 16차 · '지금 행동' | '전체 동선' 두 모드
//   지금 행동: 현재 위치 · 지금 이동 구간 · 그 장소 그림 (이전 그대로)
//   전체 동선: 하루 경로 전체를 지도에 상시 표시(차콜 · 이동 방향 화살표 · 지나온 길 실선 · 앞으로 갈 길 점선) + 장소마다 방문 번호 묶음,
//             오른쪽은 '방문 단위' 요약(장소 기준 연속 체류 묶음 · 재방문은 새 번호 · 그 방문의 주요 행동 보존). 현재 시점은 코발트 위치 표시 · 지금 줄 강조로만
//   값은 시뮬레이션 trace(segments · steps · legs) 그대로 — 새 지점 · 시각 · 경로를 만들지 않고 화면에서 묶기만 한다.
//   건물 안 · 연결 통로 · 가까운 곳 · 진입점을 모르는 구간은 선을 그리지 않는다(목록에 '건물 안 이동' · '경로 미확인').
// ---------------------------------------------------------------------------
let GHOST = "", RAKEY = "", RCKEY = "", VISITS = null;
// 방문 구간 — segments 를 시간순으로 훑어 같은 장소가 이어지면 한 방문, 다른 곳에 갔다 돌아오면 새 방문
function visitsOf() {
  if (!G) return [];
  if (VISITS && VISITS.g === G) return VISITS.list;
  const V = [];
  for (const s of G.segs) {
    const last = V[V.length - 1];
    if (last && last.loc === s.location) { last.b = Math.max(last.b, s.b); last.segs.push(s); }
    else V.push({ loc: s.location, a: s.a, b: s.b, segs: [s], n: V.length + 1, leg: null, steps: [], k: 1, total: 1 });
  }
  const cnt = {};
  V.forEach((v, i) => { cnt[v.loc] = (cnt[v.loc] || 0) + 1; v.k = cnt[v.loc]; v.leg = i ? (G.legs[i - 1] || null) : null; });   // legs[i-1] = i 번째 방문으로 들어오는 이동 (showGuest 와 같은 규칙)
  V.forEach(v => { v.total = cnt[v.loc]; });
  // 행동 → 방문: 같은 장소의 방문 중 시작 시각이 들어가는 것, 없으면 시각이 가장 가까운 것 (행동을 버리지 않는다)
  for (const s of G.st) {
    const c = V.filter(v => v.loc === s.location);
    if (!c.length) continue;
    const v = c.find(x => s.a >= x.a - 1 && s.a <= x.b) || c.reduce((p, q) => Math.abs(q.a - s.a) < Math.abs(p.a - s.a) ? q : p);
    v.steps.push(s);
  }
  VISITS = { g: G, list: V };
  return V;
}
// 그 방문 안의 주요 행동 — 같은 이름이 이어지면 한 번만 (체크인 → 객실 → 룸서비스 식)
function visitActs(v) {
  const out = [];
  for (const s of v.steps) { const l = labOk(s.label) || GSTATE[s.kind] || ""; if (l && out[out.length - 1] !== l) out.push(l); }
  return out;
}
// 이동 구간 설명 — 선을 그리는 이동인지, 건물 안 · 연결 통로 · 가까운 곳(선 없음)인지, 경로를 모르는지
function legDesc(l) {
  if (!l) return null;
  const r = l.r, mins = Math.max(1, Math.round(l.b - l.a)), m = `${mins}분`;
  if (r.internal) return { kind: "in", txt: `${bName(r.bldg) || "건물"} 안 이동 · ${m}` };
  if (r.link) return { kind: "in", txt: `그랜드 ↔ 비스타 연결 통로 · ${m}` };
  if (r.near || r.sameEntrance) return { kind: "in", txt: `가까운 곳으로 이동 · ${m}` };
  if (r.unknown || !r.pts || r.pts.length < 2) return { kind: "unk", txt: `경로 미확인 · ${m}` };
  return { kind: "walk", txt: `지도의 길로 이동 · ${m}` };
}
// 지도 — 하루 경로 전체 (#route 층). 지나온 길 실선 · 앞으로 갈 길 점선 · 이동 방향 화살표. 지금 이동 구간은 drawFrame(#trail)이 코발트로 덧그린다
function drawRouteAll() {
  const el = $("#route"); if (!el) return;
  if (!(G && MODE === "guest" && ROUTEALL)) return;
  const k = mapK();
  const legs = G.legs.filter(l => l.r.pts.length > 1 && !l.r.unknown);
  const nDone = legs.filter(l => T >= l.b).length, cur = legs.findIndex(l => l.a <= T && T < l.b);
  const key = `${nDone}|${cur}|${k.toFixed(2)}|${legs.length}`;
  if (key === RAKEY) return; RAKEY = key;
  let h = "";
  legs.forEach((l, i) => {
    const r = l.r, st = T >= l.b ? "past" : (l.a <= T && l.b > T) ? "cur" : "fut";
    const fr = r.total > 260 ? [0.3, 0.72] : [0.5];   // 긴 길은 화살표 둘
    let ar = "";
    for (const f of fr) {
      const p = along(r, f), q = along(r, Math.min(1, f + 0.02)), ang = Math.atan2(q[1] - p[1], q[0] - p[0]) * 180 / Math.PI, sz = 6.5 * k;
      ar += `<path class="wrArrow" d="M${(-sz).toFixed(1)},${(-sz * 0.7).toFixed(1)} L${(sz * 0.6).toFixed(1)},0 L${(-sz).toFixed(1)},${(sz * 0.7).toFixed(1)} Z" transform="translate(${p[0].toFixed(1)},${p[1].toFixed(1)}) rotate(${ang.toFixed(1)})"/>`;
    }
    h += `<g class="wr ${st}" data-leg="${i}"><path class="wrEdge" d="${ptsD(r.pts)}"/><path class="wrLine" d="${ptsD(r.pts)}"/>${ar}</g>`;
  });
  el.innerHTML = GHOST + h;
}
// 17차 · 지도 이름표 둘째 줄 — 건물은 '내부 n구간'(그 건물 안에서 머문 방문 구간 수 · 입장 횟수 아님), 건물 밖 방문지는 'n회 방문'
let NOWTAG = { key: "", d: [0, 0] };
let GVSTAT = {}, RCHL = null, RCOPEN = new Set(), RC_HOLD = 0, RC_CUR = -2;
function visitStat() {
  const out = {};
  for (const v of visitsOf()) {
    if (!LOC[v.loc]) continue;
    const b = bldgOf(v.loc), key = b || v.loc;
    if (!out[key]) out[key] = { n: 0, vkey: key, bldg: !!b };
    out[key].n++;
  }
  for (const o of Object.values(out)) o.line2 = o.bldg ? `내부 ${o.n}구간` : `${o.n}회 방문`;
  return out;
}
// 이름표가 없는 방문지(건물 밖)만 점 옆에 작은 이름 — 새 좌표를 만들지 않고 장소 점 옆에
function orphanNames() {
  const has = new Set(LABELS.map(l => l.b || l.loc).filter(Boolean)), k = mapK();
  return Object.values(GVSTAT).filter(o => !o.bldg && !has.has(o.vkey) && LOC[o.vkey]).map(o => {
    const [x, y] = LOC[o.vkey];
    return `<text class="vplace" data-vkey="${o.vkey}" x="${(x + 9 * k).toFixed(1)}" y="${(y + 4 * k).toFixed(1)}" style="font-size:${(11.5 * k).toFixed(1)}px">${esc(nameOk(o.vkey) || locName(o.vkey))}${o.n > 1 ? ` · ${o.n}회` : ""}</text>`;
  }).join("");
}
// 지도 이름표를 누르면 — 오른쪽 목록에서 그 건물 · 장소의 방문만 강조 (다시 누르면 해제). 지도에는 선 · 라벨을 더하지 않는다
function hlVisits(key) {
  RCHL = RCHL === key ? null : key; RCKEY = ""; RC_HOLD = Date.now() + 8000;
  const el = document.getElementById("nowStep"); if (el && ROUTEALL) drawRouteCard(el);
  const li = RCHL && el && el.querySelector(".rc-v.hl"); const ls = el && el.querySelector(".rc-list");
  if (li && ls) { const bar = ls.querySelector(".rc-hlbar"); ls.scrollTop = Math.max(0, li.offsetTop - (bar ? bar.offsetHeight : 0) - 2); }   // 강조 막대 아래로 첫 줄이 온전히
  $$("#labels .lab[data-vkey]").forEach(e => e.classList.toggle("vsel", e.dataset.vkey === RCHL));
}
const visitKey = v => bldgOf(v.loc) || v.loc;
// 그 방문 시각으로 — 지도 · 시계 · 일정 띠 · 오른쪽이 drawFrame 한 번으로 같이 움직인다
function gotoVisit(n) {
  const v = visitsOf()[n - 1]; if (!v) return;
  SEL = null; setPlay(false); T = Math.min(v.a + 0.5, G.t1); drawFrame();
}
// 오른쪽 — 17차 · 전체 동선 카드. 머리(곳 · 방문 수 · 시뮬레이션 표식) → 현재(방문 n/N · 시각 · 지금 행동) → 방문 목록(한 방문 두 줄 · 내부 스크롤)
//   첫 줄 시각 · 장소 · 재방문 n/N, 둘째 줄 주요 행동. 이동 방식 · 시각 범위 · 결제 · 선택 이유는 펼침(현재 방문은 자동, 나머지는 ▸).
//   방문 사이 '기록되지 않은 시간 간격'(이동이 끝나고 다음 체류가 시작될 때까지 trace 에 행동이 없는 시간 · 10분 이상)은 접혀 있어도 얇은 줄로 보인다
const fmMin = m => m >= 60 ? `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ""}` : `${m}분`;
const visitGap = v => v.leg ? Math.round(v.a - v.leg.b) : 0;
function drawRouteCard(el) {
  const V = visitsOf(), now = nowAt(T);
  const isGap = !!(now && (now.mode === "gap" || now.mode === "unres"));   // 19차 · 위치가 확정되지 않은 시각에는 어떤 방문도 '현재' 로 칠하지 않는다
  const cur = isGap ? -1 : V.findIndex(v => v.a <= T && T < v.b);
  const nRec = isGap && now.S && now.S.b != null ? V.findIndex(v => v.a <= now.S.b + 0.01 && now.S.b < v.b) : -1;   // 다음 기록이 들어 있는 방문
  const next = cur < 0 ? (nRec >= 0 ? nRec : V.findIndex(v => v.a > T)) : -1;
  const moving = !!(now && now.mode === "move");
  const focus = cur >= 0 ? cur : (moving || isGap) ? next : -1;   // 이동 중 · 기록 없는 시간이면 가는 방문을 현재처럼
  const key = `${G.persona.start}|${V.length}|${G.st.length}|${G.spend_total}|${focus}|${isGap}|${[...RCOPEN].join(",")}|${RCHL}`;
  if (RCKEY !== key || !el.querySelector(".rc")) {
    const old = el.querySelector(".rc-list"), keep = old ? old.scrollTop : 0;
    const places = new Set(V.map(v => v.loc)).size;
    let rows = "", lastDay = null;
    if (RCHL) { const o = GVSTAT[RCHL]; rows += `<li class="rc-hlbar"><span>${esc(o && o.bldg ? `${bName(RCHL)} 안 방문 ${o.n}구간` : `${nameOk(RCHL) || locName(RCHL)} 방문 ${o ? o.n : ""}회`)} 강조</span><button type="button" class="rc-hlx" aria-label="강조 해제">해제</button></li>`; }
    V.forEach((v, i) => {
      const d = dlabel(v.a);
      if (lastDay && d !== lastDay) rows += `<li class="rc-day">${esc(d)} · 다음 날</li>`;
      lastDay = d;
      const gap = visitGap(v);
      if (gap >= 10) rows += `<li class="rc-gap">세부 일정 미지정 · ${fmMin(gap)}</li>`;
      const acts = visitActs(v), open = i === focus || RCOPEN.has(v.n);
      const sw = v.steps.find(s => s.switch && s.switch["원래"]);
      const stt = i === focus ? (isGap ? " nextrec" : " now") : v.b <= T ? " past" : " fut";
      rows += `<li class="rc-v${stt}${open ? " open" : ""}${RCHL && visitKey(v) === RCHL ? " hl" : ""}" data-v="${v.n}">` +
        `<span class="rc-n">${v.n}</span>` +
        `<span class="rc-b"><span class="rc-l1"><span class="rc-t">${hhmm(v.a)}</span><b>${esc(nameOk(v.loc) || locName(v.loc))}</b>${v.total > 1 ? `<i class="rc-again" title="이곳 ${v.total}번 중 ${v.k}번째">${v.k}/${v.total}</i>` : ""}${sw ? `<i class="rc-sw">만석</i>` : ""}</span>` +
        `<small>${esc(acts.slice(0, 3).join(" · "))}${acts.length > 3 ? ` 외 ${acts.length - 3}` : ""}</small></span>` +
        `<button type="button" class="rc-x" data-x="${v.n}" aria-label="${open ? "접기" : "펼치기"}" aria-expanded="${open}">${open ? "▾" : "▸"}</button></li>`;
      if (open) {
        const ld = legDesc(v.leg), amt = v.steps.reduce((a, s) => a + (s.spend || []).reduce((x, y) => x + y.krw, 0), 0);
        const si = v.steps.length ? G.st.indexOf(v.steps[0]) : -1;
        rows += `<li class="rc-det" data-v="${v.n}">` +
          (ld ? `<div class="rc-dl"><span>들어온 길</span>${esc(ld.txt)}</div>` : `<div class="rc-dl"><span>들어온 길</span>하루의 첫 방문</div>`) +
          (visitGap(v) >= 10 ? `<div class="rc-dl gapd"><span>도착 뒤</span>${hhmm(v.leg.b)} 도착(모델 이동 계산) → ${hhmm(v.a)} 시작 · 사이 ${fmMin(visitGap(v))} 세부 일정 미지정 · 현재 위치 미확정${v.steps[0] && v.steps[0].wait ? ` (모델 대기값 ${Math.round(v.steps[0].wait)}분은 점수 계산에만 쓰임)` : ""}</div>` : "") +
          (() => { const gs = G.iv.filter(x => x.k === "gap" && x.a >= v.a && x.b <= v.b && x.b - x.a >= 1); return gs.length ? `<div class="rc-dl gapd"><span>중간</span>${gs.map(x => `${hhmm(x.a)}–${hhmm(x.b)} 세부 일정 미지정`).join(" · ")}</div>` : ""; })() +
          `<div class="rc-dl"><span>머문 시간</span>${v.segs[0] && v.segs[0].state === "SEATED" ? `${hhmm(v.a)} 착석 · ${hhmm(v.segs[0].b)} 식사 시작 ~ ${hhmm(v.b)}` : `${hhmm(v.a)} ~ ${hhmm(v.b)}`}${v.b - v.a >= 1 ? ` · ${fmMin(Math.round(v.b - v.a))}` : ""}</div>` +
          `<div class="rc-dl"><span>행동</span>${esc(acts.join(" → ") || "기록된 행동 없음")}</div>` +
          (sw ? `<div class="rc-dl sw"><span>만석</span>${esc(nmDisp(sw.switch["원래"]))} 만석 → ${esc(altName(sw.label))}</div>` : "") +
          `<div class="rc-dl"><span>결제</span>${amt ? won(amt) : "없음"}</div>` +
          `<div class="rc-acts">${i !== focus ? `<button type="button" class="rc-go" data-v="${v.n}">이 시점으로</button>` : ""}${si >= 0 ? `<button type="button" class="rc-why" data-i="${si}">모델 선택 근거</button>` : ""}</div></li>`;
      }
    });
    const posTxt = cur >= 0 ? `방문 ${cur + 1}/${V.length}` : isGap && focus >= 0 ? `다음 기록 · 방문 ${focus + 1}/${V.length}` : focus >= 0 ? `방문 ${focus}/${V.length} → ${focus + 1}` : "";
    el.innerHTML = `<div class="rc">
      <div class="rc-h"><b>하루 전체 동선</b><span>${places}곳 · ${V.length}회 방문</span><em class="rc-sim">모델 시뮬레이션 결과${noteI("이 동선은 모델이 만든 하루 전체 시뮬레이션 결과이며 이미 일어난 관측 기록이 아닙니다. 앞으로 갈 곳도 같은 계산에서 나온 예측입니다. 방문은 같은 장소에 이어서 머문 구간을 하나로 묶은 것이고(다른 곳에 다녀오면 새 방문), 시각 · 장소 · 행동은 trace 값 그대로입니다. '기록되지 않은 시간 간격' 은 이동이 끝나거나 체류가 끝난 뒤 다음 기록이 시작될 때까지 trace 에 위치 · 행동이 없는 시간(세부 일정 미지정)이며 대기 · 머무름으로 보지 않습니다.")}</em></div>
      <div class="rc-now"><small><span class="rc-pos">${posTxt}</span> · <b class="rc-nt">${hhmm(T)}</b></small><div class="rc-na"></div></div>
      <ol class="rc-list">${rows}</ol></div>`;
    const ls = el.querySelector(".rc-list");
    ls.scrollTop = keep;
    // 사용자가 목록을 직접 살펴보는 동안(휠 · 터치 · 끌기 · 키)은 자동으로 현재 방문을 찾아가지 않는다
    ["wheel", "touchstart", "pointerdown", "keydown"].forEach(ev => ls.addEventListener(ev, () => { RC_HOLD = Date.now() + 6000; }, { passive: true }));
    ls.querySelectorAll(".rc-v[data-v]").forEach(li => li.onclick = () => { RC_HOLD = 0; gotoVisit(+li.dataset.v); });
    ls.querySelectorAll(".rc-x").forEach(b => b.onclick = ev => { ev.stopPropagation(); const n = +b.dataset.x; RCOPEN.has(n) ? RCOPEN.delete(n) : RCOPEN.add(n); RC_HOLD = Date.now() + 6000; RCKEY = ""; drawRouteCard(el); });
    ls.querySelectorAll(".rc-go").forEach(b => b.onclick = ev => { ev.stopPropagation(); RC_HOLD = 0; gotoVisit(+b.dataset.v); });
    ls.querySelectorAll(".rc-why").forEach(b => b.onclick = ev => { ev.stopPropagation(); selectStep(+b.dataset.i); });
    const hx = ls.querySelector(".rc-hlx"); if (hx) hx.onclick = ev => { ev.stopPropagation(); hlVisits(RCHL); };
    RCKEY = key;
    // 현재 방문이 바뀌면 목록 안에서만 찾아간다 (패널 전체는 움직이지 않음 · 사용자가 보는 중이면 건너뜀)
    if (focus !== RC_CUR) { RC_CUR = focus; if (Date.now() > RC_HOLD) { const li = ls.querySelector(".rc-v.now"); if (li && (li.offsetTop < ls.scrollTop + 4 || li.offsetTop + li.offsetHeight + 90 > ls.scrollTop + ls.clientHeight)) { let pv = li.previousElementSibling; while (pv && !pv.classList.contains("rc-v")) pv = pv.previousElementSibling; ls.scrollTop = Math.max(0, (pv ? pv.offsetTop : li.offsetTop) - 1); } } }   // 바로 앞 방문 한 줄이 온전히 보이게
  }
  // 매 프레임 — 시각 · 지금 행동 한 줄만 바꾼다
  const nt = el.querySelector(".rc-nt"); if (nt) nt.textContent = hhmm(T);
  let act = "";
  if (!now) act = T < G.st[0].a ? "아직 도착 전" : V.some(v => v.a > T) ? "기록된 행동이 없는 시간" : "오늘 일정 끝";
  else if (moving) { const pa = posAt(T), ln = pa.moving ? legNames(pa.moving) : null; act = ln ? `이동 중 · ${ln.from} → ${ln.to}` : "이동 중"; }
  else if (now.mode === "gap") { const ui = unrecInfo(T); act = `다음 행동 전 · 세부 일정 미지정 · 마지막 기록 ${ui.last ? `${hhmm(ui.last.t)} ${nameOk(ui.last.loc) || ""} ${ui.last.how === "체류 끝" ? "체류 종료" : "도착"}` : "없음"}`; }
  else if (now.mode === "unres") act = `위치 미확정 · ${now.why}`;
  else act = `${now.place || ""}${now.mode === "stay" ? " · 머무는 중" : now.act && now.act !== now.place ? ` · ${now.act}` : ""}`;
  const na = el.querySelector(".rc-na"); if (na && na.textContent !== act) na.textContent = act;
  // 지도 이름표 — 지금 있는(가는) 건물 · 장소만 코발트
  const fk = focus >= 0 && !isGap ? visitKey(V[focus]) : null;
  $$("#labels .lab[data-vkey]").forEach(e => { e.classList.toggle("vcur", e.dataset.vkey === fk); });
}
// 건물 강조 영역 — 그 건물 업장 점들을 감싸는 타원 (새 좌표를 만들지 않고 이미 있는 장소 점에서만)
const BHL = {};
function bldgHL(id) {
  if (BHL[id]) return BHL[id];
  const ps = BLDG[id].locs.map(l => LOC[l]).filter(Boolean);
  const xs = ps.map(p => p[0]), ys = ps.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  return (BHL[id] = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, rx: (x1 - x0) / 2 + 22, ry: (y1 - y0) / 2 + 18 });
}
// 말풍선 글자 — 시설 이용 중: '포레스트 파크 · 와인페어 이용 중' (장소 이름과 겹치는 낱말은 한 번만)
function actPhrase(st, place) {
  let a = String(labOk(st && st.label) || "").trim();
  const k = st && st.kind;
  if (!place) return a;
  const pw = String(place).split(" ");
  if (a === place || pw.includes(a) || place.replace(/\s/g, "").endsWith(a.replace(/\s/g, ""))) a = "";
  else { const w = a.split(" "); if (w.length > 1 && place.includes(w[0])) a = w.slice(1).join(" "); }
  if (k === "checkin") return a ? `${place} · ${a}` : place;
  if (k === "room") return /·/.test(a) ? `${place} · ${a}` : `${place} · ${!a || a === "객실" ? "휴식" : a} 중`;
  return `${place} · ${a ? a + " " : ""}이용 중`;
}
const bName = id => (BLDG[id] ? BLDG[id].name : null);
const inName = (n, id) => { const w = (bName(id) || "").split(" ")[0]; return w && String(n || "").startsWith(w + " ") ? String(n).slice(w.length + 1) : n; };
// 출발 · 도착 이름 — 건물 밖으로 나가면 출발은 건물 이름 (그랜드 워커힐 → 포레스트 파크)
function legNames(l) {
  const fa = bldgOf(l.from), tb = bldgOf(l.to);
  const from = fa && fa !== tb ? bName(fa) : nameOk(l.from), to = nameOk(l.to);
  return { from: from || "출발", to: to || "도착" };
}

let BUBPOS = { key: "", d: null };
function mapK() {
  const r = $("#map").getBoundingClientRect();
  const sc = Math.min(r.width / MAP_W, r.height / MAP_H) || 1;
  return Math.max(1, 1 / sc);
}
function bubblePos(key, q, w, h, k, leg) {
  k = k || 1;
  const g = 16 * k, C = [[-w / 2, -h - g], [-w / 2, g], [g, -h / 2], [-w - g, -h / 2], [g * 0.6, -h - g * 0.6], [-w - g * 0.6, -h - g * 0.6], [g * 0.6, g * 0.6], [-w - g * 0.6, g * 0.6]];
  // 16차 · 전체 동선 모드에서는 방문 번호 묶음이 위치 표시 둘레에 모여 있어 한 칸 더 먼 자리도 후보에 넣는다 (번호 묶음을 가리지 않게)
  if (ROUTEALL) C.push([-w / 2, -h - g * 2.4], [-w / 2, g * 2.4], [g * 2.4, -h / 2], [-w - g * 2.4, -h / 2], [g * 1.6, -h - g * 1.6], [-w - g * 1.6, -h - g * 1.6], [g * 1.6, g * 1.6], [-w - g * 1.6, g * 1.6]);
  key = key + "|" + Math.round(w) + "|" + Math.round(h);
  if (BUBPOS.key !== key || !BUBPOS.d) {
    // 9차 · 말풍선은 한 구간 동안 위치 표시와 같은 간격을 두고 따라간다 → 그 구간 전체(출발 → 도착)를 놓고
    //   지금 이동 선 · 출발 · 도착 표시 · 바탕 건물 이름 · 들른 곳 이름과 덜 겹치는 쪽을 한 번 고른다 (구간 중간에 자리를 바꾸지 않음)
    const pts = []; for (const l of (ROUTEALL ? G.legs : leg ? [leg] : [])) for (let i = 0; i <= 30; i++) pts.push(along(l.r, i / 30));
    const marks = leg && LOC[leg.from] && LOC[leg.to] ? [LOC[leg.from], LOC[leg.to]] : [];
    const at = leg ? [0, .2, .4, .6, .8, 1].map(f => along(leg.mk || leg.r, f)) : [q];
    const lbl = $$("#pins .visitLbl, #labels .lab:not(.off):not(.dup), #agent .odLbl").map(e => { try { const b = e.getBBox(); b.w8 = e.classList && (e.classList.contains("hlDest") || e.classList.contains("hlB")) ? 6 : (e.tagName === "rect" ? 8 : 1); return b; } catch (x) { return null; } }).filter(Boolean);   // 16차 · 방문 번호 묶음(rect)은 세게 피한다
    let best = null;
    C.forEach(([dx, dy], ci) => {
      let sc = ci >= 8 ? 1.2 : ci >= 4 ? 0.5 : 0;
      for (const o of at) {
        const x = o[0] + dx, y = o[1] + dy;
        if (x < 4 || y < 4 || x + w > MAP_W - 4 || y + h > MAP_H - 4) sc += 40;
        for (const r of pts) if (r[0] > x - 6 && r[0] < x + w + 6 && r[1] > y - 6 && r[1] < y + h + 6) sc += 3;
        for (const m of marks) if (m[0] > x - 14 * k && m[0] < x + w + 14 * k && m[1] > y - 14 * k && m[1] < y + h + 14 * k) sc += 25;
        for (const b of lbl) sc += Math.max(0, Math.min(x + w, b.x + b.width) - Math.max(x, b.x)) * Math.max(0, Math.min(y + h, b.y + b.height) - Math.max(y, b.y)) / 60 * (b.w8 || 1);
      }
      if (!best || sc < best.sc) best = { sc, d: [dx, dy] };
    });
    BUBPOS = { key, d: best.d };
  }
  let x = q[0] + BUBPOS.d[0], y = q[1] + BUBPOS.d[1];
  x = Math.min(MAP_W - w - 4, Math.max(4, x)); y = Math.min(MAP_H - h - 4, Math.max(4, y));
  return [x, y];
}
function stepAt(t) { return G.st.find(s => s.a <= t && t < s.b); }
// 10/17 UX 4차 · 지금 시각에 보여 줄 수 있는 위치와 행동 — 지도 말풍선 · 위치 표시 · 시계 · 오른쪽 대표 영역 · 일정 띠가 모두 이 기준을 쓴다.
//   step: 행동 구간 안 · move: 이동 구간 안 · stay: 행동 결정은 없지만 상태 기록(segment)상 그 장소에 있음 (예: 객실에 머묾)
//   wait: 다음 행동 장소에 먼저 와서 기다림 (도착한 곳 = 다음 행동 장소일 때만) · null: 보여 줄 위치가 없음 (도착 전 · 하루 끝 · 기록 없는 빈 구간)
//   장소 이름이 비었거나 코드 그대로(이름 대응 실패)면 이름 대신 행동 이름을 쓰고, 둘 다 없으면 말풍선 글자를 비워 말풍선을 그리지 않는다.
const nameOk = c => { const n = c && LIB && LIB.loc_names ? LIB.loc_names[c] : null; return n && String(n).trim() ? String(n).trim() : null; };
const labOk = x => (x == null ? null : (String(altName(x)).trim() || null));
// 10/18 UX 19차 · 공통 상태 판정 — 손님 한 팀의 하루를 겹치지 않는 구간표(G.iv)로 한 번 만들고, 지도 · 상태 카드 · 시간표 · 전체 동선 목록이 모두 stateAt(t) 만 본다.
//   stay  · 체류 구간(segment) 안 — 그 장소에 있음. 그 시각의 행동(step)이 없으면 '머무는 중 · 세부 행동 미지정'
//   move  · 이동 구간(leg · 직전 체류 끝 + 모델 이동 분) 안 — 출발 → 도착
//   gap   · 기록된 끝(체류 끝 또는 이동 도착)과 다음 기록 시작 사이 — '다음 행동 전 · 세부 일정 미지정'. 현재 위치는 미확정(마지막 기록 위치를 현재로 쓰지 않음)
//   unres · 구간은 있으나 지도 좌표가 없거나 시각이 뒤집힌 구간 — 위치 미확정(데이터 · 매핑 문제). 정상 공백(gap)과 구분
//   pre · end · 첫 기록 전 · 마지막 기록 뒤
//   새 행동 · 위치 · 시각을 만들지 않고 trace 의 segments · steps 와 이미 계산된 legs 만 쓴다.
function buildStates() {
  const iv = [];
  const bad = (loc, a, b) => (!LOC[loc] ? "좌표 없음" : !(b >= a) ? "시각 오류" : null);
  for (const g of G.segs) iv.push({ k: "stay", a: g.a, b: g.b, loc: g.location, seg: g, unres: bad(g.location, g.a, g.b) });
  for (const l of G.legs) if (l.b > l.a) iv.push({ k: "move", a: l.a, b: l.b, loc: l.to, from: l.from, leg: l, unres: !LOC[l.to] || !LOC[l.from] ? "좌표 없음" : null });
  // 체류 구간 밖에 걸친 행동(step)도 그 장소의 체류로 본다 (행동이 곧 위치 근거)
  for (const st of G.st) if (!iv.some(x => x.a < st.b - 0.01 && x.b > st.a + 0.01)) iv.push({ k: "stay", a: st.a, b: st.b, loc: st.location, step: st, unres: bad(st.location, st.a, st.b) });
  iv.sort((x, y) => x.a - y.a || (x.k === "move" ? -1 : 1));
  const out = []; let end = null, prev = null;
  for (const x of iv) {
    if (end != null && x.a > end + 0.01) out.push({ k: "gap", a: end, b: x.a, last: prev.k === "move" ? { t: end, loc: prev.loc, how: "도착 · 모델 이동 계산" } : { t: end, loc: prev.loc, how: "체류 끝" }, nextIv: x });
    out.push(x);
    if (end == null || x.b >= end) { end = x.b; prev = x; }
  }
  out.forEach(x => { if (x.unres) x.k = "unres"; });
  return out;
}
function lastMark(now, k) {
  const L = now.mode === "gap" && now.last && LOC[now.last.loc] ? LOC[now.last.loc] : null; if (!L) return "";
  const txt = `마지막 기록 ${hhmm(now.last.t)}`, fs = 11 * k;
  return `<g class="lastMark"><title>마지막 기록 · ${esc(nameOk(now.last.loc) || "")} ${esc(now.last.how)} · 지금 그곳에 있다는 뜻이 아님</title><circle cx="${L[0]}" cy="${L[1]}" r="${(7 * k).toFixed(1)}"/><text x="${(L[0] + 11 * k).toFixed(1)}" y="${(L[1] + fs * 0.36).toFixed(1)}" style="font-size:${fs.toFixed(1)}px">${esc(txt)}</text></g>`;
}
function stateAt(t) {
  if (!G || !G.iv || !G.iv.length) return { k: "none" };
  const first = G.iv[0].a, last = Math.max(...G.iv.map(x => x.b));
  if (t < first) return { k: "pre", first };
  if (t >= last) return { k: "end", last };
  let hit = null; for (const x of G.iv) if (x.a <= t && t < x.b) { if (!hit || x.k === "move") hit = x; }   // 겹치면 이동이 먼저 (체류 끝 · 이동 시작 경계)
  return hit || { k: "unres", a: t, b: t, why: "구간 없음" };
}
function nowAt(t) {
  if (!G || !G.st.length) return null;
  const S = stateAt(t), nx = nextStep(t);
  if (S.k === "pre" || S.k === "end" || S.k === "none") return null;
  if (S.k === "move") {
    const l = S.leg, pa = posAt(t), to = l.to;
    const lab = labOk(l.next && l.next.label) || nameOk(to);
    return { mode: "move", key: "m" + G.legs.indexOf(l), p: pa.moving === l ? pa.p : along(l.mk || l.r, (t - l.a) / (l.b - l.a)), loc: to, place: nameOk(to), act: lab, nx, S };
  }
  if (S.k === "gap") {
    const nxt = S.nextIv, nl = nxt.loc;
    return { mode: "gap", key: "g" + G.iv.indexOf(S), loc: null, ploc: null, last: S.last, place: null, act: "다음 행동 전 · 세부 일정 미지정", nx, nextLoc: nl, S };
  }
  if (S.k === "unres") {
    const code = S.loc || "";
    return { mode: "unres", key: "u" + G.iv.indexOf(S), loc: null, ploc: null, place: null, code, why: S.unres || S.why || "", act: "위치 미확정", nx, S };
  }
  // stay — 그 시각의 행동이 있으면 행동, 없으면 '머무는 중'
  const st = stepAt(t);
  if (st && LOC[st.location]) return { mode: "step", key: "s" + G.st.indexOf(st), p: LOC[st.location], loc: st.venue || st.location, ploc: st.location, place: nameOk(st.venue || st.location) || nameOk(st.location), act: labOk(st.label), st, nx, S };
  return { mode: "stay", key: "y" + G.iv.indexOf(S), p: LOC[S.loc], loc: S.loc, ploc: S.loc, place: nameOk(S.loc), act: nameOk(S.loc) ? "머무는 중" : null, nx, S };
}
function nextStep(t) { return G.st.find(s => s.a >= t); }
// 17차 마무리 · 식당 행동은 착석(SEATED 구간 · 3분) 뒤 식사(step) — 방문 시작은 착석, 행동 시작은 식사. '다음' 은 착석 기준으로 보인다
function seatA(s) { if (!s) return null; const sg = G.segs.find(x => x.location === s.location && x.state === "SEATED" && x.a <= s.a + 0.01 && s.a - x.a <= 5); return sg ? sg.a : s.a; }
// 다음 행동 전(gap) — 마지막 기록(체류 끝 또는 이동 도착)과 다음 기록. 그 사이의 위치 · 행동은 trace 에 없다 (stateAt 의 gap 구간 그대로)
function unrecInfo(t) {
  const S = stateAt(t), nx = nextStep(t);
  const last = S.k === "gap" ? S.last : null;
  return { last, next: nx ? { t: seatA(nx), label: labOk(nx.label) || nameOk(nx.location) || "다음 행동", seat: seatA(nx) !== nx.a } : null };
}

function posAt(t) {
  for (const l of G.legs) if (l.a <= t && t < l.b) return { p: along(l.mk || l.r, (t - l.a) / (l.b - l.a)), moving: l };
  const s = G.segs.find(x => x.a <= t && t < x.b);
  if (s) return { p: LOC[s.location] || [500, 500], seg: s };
  // 이동 끝나고 다음 구간 전 = 그 자리에서 대기
  let last = null;
  for (const l of G.legs) if (l.b <= t) last = l;
  const prev = G.segs.filter(x => x.b <= t).pop();
  const loc = last && (!prev || last.b >= prev.b) ? last.to : prev ? prev.location : G.segs[0].location;
  return { p: LOC[loc] || [500, 500], waiting: loc };
}

// 지금 보여 줄 '만석으로 바뀐 선택' — 그 행동으로 가는 중 · 하는 중 · 기다리는 중. 지도 표시와 오른쪽 카드가 같은 기준을 쓴다
function curSwitch(now) {
  if (!now) return null;
  const pa = now.mode === "move" ? posAt(T) : null;
  const s = now.mode === "move" ? (pa.moving && pa.moving.next) : now.st;   // 19차 · 다음 행동 전(gap) · 위치 미확정에는 다음 행동의 만석을 미리 띄우지 않는다
  return s && s.switch && s.switch["원래"] ? s.switch : null;
}
// 만석 표시 — '원래' 업장 이름 → 지도 장소. 이름이 정확히 같거나 '이름 + 식사' 인 곳을 먼저, 없으면 첫 낱말(두 글자 이상)로
function fullLoc(label) {
  const L = String(label || "").trim(), keys = Object.keys(LOC).filter(l => nameOk(l));
  return keys.find(l => locNames(l).includes(L)) || keys.find(l => locNames(l).some(n => L.startsWith(n + " "))) ||
    keys.find(l => locNames(l).some(n => { const w = n.split(" ")[0]; return w.length >= 2 && w === L.split(" ")[0]; })) || null;
}
function fullBadge(sw, q, k) {
  const loc = fullLoc(sw["원래"]); if (!loc || !LOC[loc]) return "";
  const v = LOC[loc], why = /만석/.test(sw["사유"] || "") || !sw["사유"] ? "만석" : String(sw["사유"]).slice(0, 10);
  const txt = `${nmDisp(sw["원래"]).replace(/\s*(조식|중식|석식)$/, "")} · ${why}`, fs = 12.5 * k, h = 24 * k, padX = 11 * k, iconW = 14 * k, gapI = 6 * k, w = padX * 2 + iconW + gapI + textW(txt, fs, true);   // 15차 · 실제 글자 폭으로 재서 아이콘 + 글자가 가운데 오게 (양옆 여백 같음)
  // 자리: 업장 점 주변 네 곳 중 지금 말풍선 · 위치 점 · 건물 이름과 덜 겹치는 곳
  const ab = (() => { const r = $("#agent .agentBubble rect"); return r ? [+r.getAttribute("x"), +r.getAttribute("y"), +r.getAttribute("width"), +r.getAttribute("height")] : null; })();
  const lbl = $$("#labels .lab").map(e => { try { const b = e.getBBox(); return [b.x, b.y, b.width, b.height]; } catch (x) { return null; } }).filter(Boolean);
  const over = (a, b) => Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));
  let best = null;
  for (const [dx, dy] of [[10 * k, -h - 10 * k], [-w - 10 * k, -h - 10 * k], [10 * k, 10 * k], [-w - 10 * k, 10 * k]]) {
    const r = [v[0] + dx, v[1] + dy, w, h];
    let sc = (r[0] < 4 || r[1] < 4 || r[0] + w > MAP_W - 4 || r[1] + h > MAP_H - 4) ? 1e6 : 0;
    if (ab) sc += over(r, ab) * 3; sc += over(r, [q[0] - 14 * k, q[1] - 14 * k, 28 * k, 28 * k]) * 3;
    for (const b of lbl) sc += over(r, b);
    if (!best || sc < best.sc) best = { sc, r };
  }
  const [x, y] = best.r, cx = x + w / 2 < v[0] ? x + w : x, cy = y + h / 2 < v[1] ? y + h : y;
  FBRECT = [x, y, w, h];
  return `<g class="fullBadge" role="img" aria-label="${esc(nmDisp(sw["원래"]))} ${esc(why)} · 이 때문에 선택이 바뀜"><title>${esc(nmDisp(sw["원래"]))} ${esc(why)}${sw["시각"] ? ` · ${esc(String(sw["시각"]).slice(11, 16))}` : ""} · 그래서 ${esc(altName(sw["대체"] || ""))}(으)로 바꿈 · 누르면 변경 내역</title>` +
    `<line x1="${v[0]}" y1="${v[1]}" x2="${cx.toFixed(1)}" y2="${cy.toFixed(1)}"/><circle class="fbDot" cx="${v[0]}" cy="${v[1]}" r="${(6 * k).toFixed(1)}"/>` +
    `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="${(5 * k).toFixed(1)}"/>` +
    `<path class="fbIcon" transform="translate(${(x + padX).toFixed(1)},${(y + h / 2 - 6.5 * k).toFixed(1)}) scale(${(k).toFixed(3)})" d="M7 0.8 L13.6 12.2 H0.4 Z"/><text class="fbBang" x="${(x + padX + 7 * k).toFixed(1)}" y="${(y + h / 2 + 4.4 * k).toFixed(1)}" text-anchor="middle" style="font-size:${(9.5 * k).toFixed(1)}px">!</text>` +
    `<text x="${(x + padX + iconW + gapI).toFixed(1)}" y="${(y + h / 2 + fs * 0.36).toFixed(1)}" style="font-size:${fs.toFixed(1)}px">${esc(txt)}</text></g>`;
}
// 9차 · 만석으로 바뀐 목적지 잇기 — 만석이 난 업장 → 실제로 고른 곳. 빨간 점선 화살표 (이동 경로가 아니라 '선택이 바뀜' 표시)
//   시작은 만석 표시 상자 가장자리(업장끼리 가까운 건물 안에서도 보이게), 끝은 바뀐 목적지(도착 고리 · 위치 표시) 바로 앞
let FBRECT = null;
function swArrow(sw, to, k) {
  const b = to && LOC[to], R = FBRECT;
  if (!b || !R) return "";
  const a = [Math.min(Math.max(b[0], R[0]), R[0] + R[2]), Math.min(Math.max(b[1], R[1]), R[1] + R[3])];
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy);
  if (L < 26 * k) return "";
  const cx = (a[0] + b[0]) / 2 - dy * 0.22, cy = (a[1] + b[1]) / 2 + dx * 0.22;
  const ex = b[0] - cx, ey = b[1] - cy, el = Math.hypot(ex, ey) || 1, back = 19 * k;
  const bx = b[0] - ex / el * back, by = b[1] - ey / el * back;
  const hs = 7 * k, ux = ex / el, uy = ey / el;
  const head = `M${(bx + ux * hs).toFixed(1)},${(by + uy * hs).toFixed(1)} L${(bx - uy * hs * 0.6).toFixed(1)},${(by + ux * hs * 0.6).toFixed(1)} L${(bx + uy * hs * 0.6).toFixed(1)},${(by - ux * hs * 0.6).toFixed(1)} Z`;
  return `<g class="swArrow"><title>${esc(nmDisp(sw["원래"]))} 만석 → ${esc(altName(sw["대체"] || "") || nameOk(to) || "")}(으)로 선택 변경 · 이동 경로 아님</title><path class="swLine" d="M${a[0]},${a[1]} Q${cx.toFixed(1)},${cy.toFixed(1)} ${bx.toFixed(1)},${by.toFixed(1)}"/><path class="swHead" d="${head}"/></g>`;
}
function drawFrame() {
  if (!G) return;
  const { p, moving } = posAt(T);
  const now = nowAt(T);
  const k = mapK();
  // 10/17 9차 · 동선 — 기본 '지금 행동' 보기: 지나온 길은 얇고 옅게, 앞으로 갈 길은 숨기고, 지금 이동 구간만 흰 외곽 + 코발트 굵은 선
  //   (지금 구간 안에서 지나온 쪽은 진하게, 남은 쪽은 옅게 — 위치 표시가 그 선을 따라 움직인다). '전체 동선 보기' 에서는 앞으로 갈 길(점선)도
  let fut = "", done = "", cur = "";
  for (const l of G.legs) {
    if (l.r.pts.length < 2) continue;      // 건물 안 이동 · 연결 통로 · 같은 진입점 · 가까운 곳은 선을 그리지 않는다
    if (l.r.unknown) continue;              // 16차 · 진입점을 모르는 구간은 직선을 긋지 않는다 (목록에 '경로 미확인')
    if (ROUTEALL) { if (!(l.a <= T && T < l.b)) continue; }   // 16차 · 전체 동선 모드: 하루 경로 전체는 #route 층(drawRouteAll)에, 여기서는 지금 구간만
    if (T >= l.b) done += `<path d="${ptsD(l.r.pts)}"/>`;
    else if (T < l.a) { /* 지금 행동 보기에서는 앞으로 갈 길을 숨긴다 */ }
    else {
      const f = (T - l.a) / (l.b - l.a), fl = l.mk && l.mk !== l.r ? (f * l.mk.total - l.l0) / (l.r.total || 1) : f;
      const [a, b] = cutPts(l.r, fl);
      cur = `<path class="trail now-edge" d="${ptsD(l.r.pts)}"/><path class="trail now-ahead" d="${ptsD(b)}"/>` + (a.length > 1 ? `<path class="trail now" d="${ptsD(a)}"/>` : "");
    }
  }
  // 고른 행동이 있으면 그 행동으로 가는 길을 따로 (옅은 넓은 띠)
  const sel = SEL != null ? G.st[SEL] : null;
  const legSel = sel ? [...G.legs].reverse().find(l => l.to === sel.location && l.a <= sel.a + 0.5) : null;
  $("#trail").innerHTML = fut + (done ? `<g class="trail done${ROUTEALL ? "" : " faint"}">${done}</g>` : "") + (legSel && legSel.r.pts.length > 1 && !legSel.r.unknown ? `<path class="legSel" d="${ptsD(legSel.r.pts)}"/>` : "") + cur;
  drawRouteAll();
  // 만석 표시는 지금 위치(코발트 표시)와 분리해 '만석이 난 업장' 자리에 따로. 그 행동으로 가는 중 · 하는 중 · 기다리는 중에만
  const sw = curSwitch(now);
  const mv = now && now.mode === "move" && moving ? moving : null, mvR = mv ? mv.r : null;
  const inB = mvR && mvR.internal ? mvR.bldg : null, lkB = mvR && mvR.link ? mvR.bldgs : null;
  const ln = mv ? legNames(mv) : null;
  let bub = "", sub = "", subH = "", clockTxt = "", prog = null;
  if (now) {
    if (mv) {
      const act = now.act && now.act !== now.place ? now.act : null, mins = Math.round(mv.b - mv.a);
      // 건물 안 · 연결 통로는 선이 없으므로 출발 → 도착을 말풍선 둘째 줄에서 구별 (출발은 옅게, 도착은 굵게)
      const od = (f, t) => { sub = `${f} → ${t} · ${mins}분`; subH = `<tspan class="bfrom">${esc(f)} →</tspan> <tspan class="bto">${esc(t)}</tspan><tspan class="bfrom"> · ${mins}분</tspan>`; };
      if (inB) { bub = `${bName(inB)} 내부 이동`; od(ln.from, ln.to); }   // 10차 · 시계 · 오른쪽 카드와 같은 이름 그대로
      else if (lkB) { bub = "그랜드 ↔ 비스타 연결 통로"; od(ln.from, ln.to); }
      else { bub = `${ln.from} → ${ln.to}`; sub = `이동 중 · ${mins}분`; }
      clockTxt = `${inB ? bName(inB) + " 내부 이동" : lkB ? "연결 통로로 이동" : "이동 중"} · ${ln.from} → ${ln.to}${act && !String(ln.to).includes(act) ? ` · ${act}` : ""}`;
    } else if (now.mode === "step") { bub = actPhrase(now.st, now.place) || now.act || ""; clockTxt = now.act || now.place || ""; }
    else if (now.mode === "stay") { bub = `${now.place} · 머무는 중`; clockTxt = bub; }
    // 10/17 UX 11차 · 한곳에 오래 머물 때 지도가 멈춘 것처럼 보이지 않게 — 말풍선 둘째 줄에 '48분 경과 / 총 120분' 과 얇은 진행 띠 (10분 이상 머무는 구간만 · 새 이동은 만들지 않음)
    if (!mv && (now.mode === "step" || now.mode === "stay")) {
      const iv = now.mode === "step" ? now.st : (posAt(T).seg || null);
      if (iv && iv.b - iv.a >= 10) { const tot = Math.round(iv.b - iv.a), el = Math.max(0, Math.min(tot, Math.round(T - iv.a))); const fm = m => m >= 120 ? `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ""}` : `${m}분`;
        // 상자 너비는 글자 수가 가장 긴 경우(경과 = 총)로 고정 — 분이 바뀔 때마다 상자가 줄었다 늘었다 하지 않게 (10/17 사용자: 꿀렁거려 어지러움)
        prog = { f: Math.max(0, Math.min(1, (T - iv.a) / (iv.b - iv.a))), txt: `${fm(el)} 경과 / 총 ${fm(tot)}`, wtxt: `${fm(tot)} 경과 / 총 ${fm(tot)}` }; sub = prog.txt; subH = `<tspan class="bprog">${esc(prog.txt)}</tspan>`; }
    }
    else if (now.mode === "gap") { const ui = unrecInfo(T);   // 19차 · 말풍선 없음(현재 위치가 없으므로) · 시계 글자만
      clockTxt = `다음 행동 전 · 세부 일정 미지정 · 마지막 기록 ${ui.last ? `${hhmm(ui.last.t)} ${nameOk(ui.last.loc) || ""} ${ui.last.how.split(" · ")[0]}` : "없음"}${ui.next ? ` · 다음 ${hhmm(ui.next.t)} ${ui.next.label}` : ""}`; }
    else if (now.mode === "unres") clockTxt = `위치 미확정 · ${now.why}${now.code ? ` (${nameOk(now.code) || now.code})` : ""}`;
  }
  const q = now ? (now.mode === "move" ? p : now.p) : null;
  // 시선 모으기 — 지도를 확대 · 이동하지 않고, 현재 위치 둘레만 밝게 두고 바깥을 옅게 누른다 (위치를 따라 부드럽게 옮겨 감)
  const hole = $("#spotHole");
  if (hole) { hole.style.transform = q ? `translate(${q[0].toFixed(1)}px, ${q[1].toFixed(1)}px)` : ""; $("#dim").classList.toggle("nospot", !q || ROUTEALL); }
  const fs = !now ? [] : (mv ? [focusShape(mv.from), focusShape(mv.to)] : [focusShape(now.ploc || now.loc)]).filter(Boolean);
  const fk = ROUTEALL ? "" : fs.map(f => f.id).join("|");
  if (fk !== BFKEY) { BFKEY = fk; const cp = $("#bfClip"); if (cp) cp.innerHTML = ROUTEALL ? "" : [...new Map(fs.map(f => [f.id, f.el])).values()].join(""); }
  const noLive = !!now && (now.mode === "gap" || now.mode === "unres");   // 19차 · 현재 위치를 확정할 수 없으면 실시간 위치 표시를 그리지 않는다
  if (!now || noLive) { $("#agent").innerHTML = noLive ? lastMark(now, k) : ""; $$("#labels .lab.hlB, #labels .lab.dup, #labels .lab.hlDest").forEach(t => t.classList.remove("hlB", "dup", "hlDest")); }
  else {
    let g = "";
    // 건물 안 · 연결 통로 이동 — 길은 그리지 않고 그 건물 영역을 밝히고, 출발(빈 원) · 도착(코발트 고리)을 구별해 둔다
    const hlB = inB ? [inB] : lkB || [];
    // 연결 통로는 길을 지어내지 않고 두 건물을 짧게 번갈아 강조해 '건너가는 중' 을 보인다 (출발 → 도착 순)
    hlB.forEach(b => { const e = bldgHL(b); g += `<ellipse class="bHL${lkB ? ` alt alt${b === bldgOf(mv.from) ? 0 : 1}` : ""}" cx="${e.cx}" cy="${e.cy}" rx="${(e.rx + 6 * k).toFixed(1)}" ry="${(e.ry + 6 * k).toFixed(1)}"/>`; });
    const fromB = mv && !inB && !lkB ? bldgOf(mv.from) : null;
    $$("#labels .lab").forEach(t => t.classList.toggle("hlB", hlB.some(b => t.dataset.name === bName(b)) || (!!fromB && t.dataset.name === bName(fromB))));
    // 14차 · 현재 행동 말풍선과 같은 시설(건물)의 이름표는 중복이라 숨긴다 (이동 중에는 도착지 강조를 위해 남긴다)
    const curB = mv ? null : bldgOf(now.ploc || now.loc), curName = mv ? null : (curB ? bName(curB) : now.place);
    $$("#labels .lab").forEach(t => t.classList.toggle("dup", !ROUTEALL && !!curName && t.dataset.name === curName));   // 17차 · 전체 동선 모드는 건물 이름표가 방문 구간 수를 실으므로 숨기지 않는다
    // 14차 · 지금 이동 구간 선이 지나는 이름표는 옅게 (선 · 표시가 가려지지 않게). 강조된 출발 · 도착 건물은 그대로
    if (mv && mvR && mvR.pts.length > 1) { const pts = mvR.pts.filter((_, i) => i % 3 === 0); LABLINE = pts; const onLine = t => { let b; try { b = t.getBBox(); } catch (x) { return false; } return pts.some(q => q[0] > b.x - 2 && q[0] < b.x + b.width + 2 && q[1] > b.y - 2 && q[1] < b.y + b.height + 2); };
      // 강조된(출발 · 도착) 이름표가 선에 걸리면 반대 방향으로 한 번 옮기고(구간마다 한 번), 나머지는 옅게
      let moved = false;
      $$("#labels .lab").forEach(t => { if (t.classList.contains("hlDest") || t.classList.contains("hlB")) { t.classList.remove("online"); if (onLine(t) && !LABSHIFT.has(t.dataset.name)) { LABSHIFT.add(t.dataset.name); moved = true; } return; } t.classList.toggle("online", onLine(t)); });
      if (moved) { drawLabels(); $$("#labels .lab").forEach(t => { const nm = t.dataset.name; t.classList.toggle("hlB", hlB.some(b => nm === bName(b)) || (!!fromB && nm === bName(fromB))); t.classList.toggle("online", !t.classList.contains("hlB") && onLine(t)); }); } }
    else { $$("#labels .lab.online").forEach(t => t.classList.remove("online")); if (LABSHIFT.size) { LABSHIFT.clear(); LABLINE = null; drawLabels(); } }
    if (mv && LOC[mv.from] && LOC[mv.to] && dist(LOC[mv.from], LOC[mv.to]) > 30 * k) {   // 건물 안처럼 두 점이 위치 표시보다 가까우면 점 대신 말풍선 둘째 줄로
      const o = LOC[mv.from], d = LOC[mv.to];
      g += `<circle class="origDot" cx="${o[0]}" cy="${o[1]}" r="${(5.5 * k).toFixed(1)}"><title>출발 · ${esc(ln.from)}</title></circle>` +
        `<circle class="destRing" cx="${d[0]}" cy="${d[1]}" r="${(11 * k).toFixed(1)}"><title>도착 · ${esc(ln.to)}</title></circle><circle class="destDot" cx="${d[0]}" cy="${d[1]}" r="${(3.5 * k).toFixed(1)}"/>`;
    }
    const unrec = "";
    g += `<circle class="agentHalo${unrec}" cx="${q[0]}" cy="${q[1]}" r="${(17 * k).toFixed(1)}"/>` +
      `<circle class="agentPulse${unrec}" cx="${q[0]}" cy="${q[1]}" r="${(15 * k).toFixed(1)}"/>` +
      `<circle class="agentDot${unrec}" cx="${q[0]}" cy="${q[1]}" r="${(11.5 * k).toFixed(1)}"/>` +
      (ROUTEALL || unrec ? "" : `<text class="agentNum" x="${q[0]}" y="${(q[1] + 4.2 * k).toFixed(1)}" text-anchor="middle" style="font-size:${(12 * k).toFixed(1)}px">${G.persona.party}</text>`);   // 16차 · 전체 동선 모드에서는 번호 원과 헷갈리지 않게 인원수 숫자를 뺀다 (인원은 오른쪽 이름에)
    // 도착지 이름 — 바탕에 같은 이름이 있으면 그 이름을 강조하고, 없으면 도착 고리 옆에 (건물 안 · 연결 통로는 말풍선 둘째 줄에)
    $$("#labels .lab.hlDest").forEach(t => t.classList.remove("hlDest"));
    if (mv && !inB && !lkB && LOC[mv.to]) {
      // 14차 · 도착지가 건물 안 장소(더글라스 객실 등)면 그 건물 이름표를 도착지로 강조한다
      const d = LOC[mv.to], tb = bldgOf(mv.to), tn = tb ? bName(tb) : ln.to;
      const same = $$("#labels .lab").find(t => { const r = t.querySelector("rect, text"); return t.dataset.name === tn && r && Math.hypot(+r.getAttribute("x") - d[0], +r.getAttribute("y") - d[1]) < 120; });
      if (same) same.classList.add("hlDest");
      else if (!ROUTEALL) { const fs = 13 * k; g += `<text class="odLbl" x="${(d[0] + 15 * k).toFixed(1)}" y="${(d[1] + fs * 0.36).toFixed(1)}" style="font-size:${fs.toFixed(1)}px">${esc(ln.to)}</text>`; }
    }
    if (bub && ROUTEALL) {   // 17차 · 전체 동선 모드: 검은 말풍선 대신 위치 표시 위 한 줄 (지도 · 이름표를 가리지 않게)
      const vs = visitsOf(), ci = vs.findIndex(v => v.a <= T && T < v.b);
      const txt = mv ? `이동 중 → ${ln.to}` : `지금 · ${now.place || ""}`;
      const fs = 12 * k, w = textW(txt, fs, true) + 14 * k, hh = 20 * k, gp = 17 * k;
      // 자리: 위 · 아래 · 오른쪽 · 왼쪽 중 이름표와 덜 겹치는 곳 (구간마다 한 번 고르고 그 구간 동안 유지)
      const tk = `${now.key}|${Math.round(w)}`;
      if (NOWTAG.key !== tk) {
        const lb = $$("#labels .lab:not(.off)").map(e => { try { return e.getBBox(); } catch (x) { return null; } }).filter(Boolean);
        const C = [[-w / 2, -gp - hh], [-w / 2, gp], [gp, -hh / 2], [-gp - w, -hh / 2]];
        let best = null;
        C.forEach(([dx, dy], i) => { const x0 = q[0] + dx, y0 = q[1] + dy; let sc = i * 0.5; if (x0 < 4 || y0 < 4 || x0 + w > MAP_W - 4 || y0 + hh > MAP_H - 4) sc += 1e5;
          for (const b of lb) sc += Math.max(0, Math.min(x0 + w, b.x + b.width) - Math.max(x0, b.x)) * Math.max(0, Math.min(y0 + hh, b.y + b.height) - Math.max(y0, b.y));
          if (!best || sc < best.sc) best = { sc, d: [dx, dy] }; });
        NOWTAG = { key: tk, d: best.d };
      }
      const x = Math.max(4, Math.min(MAP_W - w - 4, q[0] + NOWTAG.d[0])), y = Math.max(4, Math.min(MAP_H - hh - 4, q[1] + NOWTAG.d[1]));
      g += `<g class="nowTag${mv ? " mv" : ""}"><rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${hh.toFixed(1)}" rx="${(hh / 2).toFixed(1)}"/><text x="${(x + w / 2).toFixed(1)}" y="${(y + hh / 2 + fs * 0.36).toFixed(1)}" text-anchor="middle" style="font-size:${fs.toFixed(1)}px">${esc(txt)}</text></g>`;
    } else if (bub) {
      const fs = 13.5 * k, fs2 = 11.5 * k, subW = prog ? prog.wtxt : sub, w = Math.max(56 * k, bub.length * fs * 0.98 + 24 * k, subW ? subW.length * fs2 * 0.98 + 24 * k : 0), h = sub ? 46 * k : 26 * k;
      const pos = bubblePos(now.key + (ROUTEALL ? "A" : ""), q, w, h, k, mv);
      g += `<g class="agentBubble"><rect x="${pos[0].toFixed(1)}" y="${pos[1].toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="${(13 * k).toFixed(1)}"/>` +
        `<text x="${(pos[0] + w / 2).toFixed(1)}" y="${(pos[1] + (sub ? 16 * k : h / 2) + fs * 0.36).toFixed(1)}" text-anchor="middle" style="font-size:${fs.toFixed(1)}px">${esc(bub)}</text>` +
        (sub ? `<text class="bsub" x="${(pos[0] + w / 2).toFixed(1)}" y="${(pos[1] + 37 * k).toFixed(1)}" text-anchor="middle" style="font-size:${fs2.toFixed(1)}px">${subH || esc(sub)}</text>` : "") +
        (prog ? `<rect class="bprogT" x="${(pos[0] + 12 * k).toFixed(1)}" y="${(pos[1] + h - 5 * k).toFixed(1)}" width="${(w - 24 * k).toFixed(1)}" height="${(2.5 * k).toFixed(1)}" rx="${(1.2 * k).toFixed(1)}"/><rect class="bprogF" x="${(pos[0] + 12 * k).toFixed(1)}" y="${(pos[1] + h - 5 * k).toFixed(1)}" width="${((w - 24 * k) * prog.f).toFixed(1)}" height="${(2.5 * k).toFixed(1)}" rx="${(1.2 * k).toFixed(1)}"/>` : "") + `</g>`;
    }
    if (sw) { FBRECT = null; const fbH = fullBadge(sw, q, k); g += swArrow(sw, mv ? mv.to : now.ploc, k) + fbH; }
    $("#agent").innerHTML = g;
    const fb = $("#agent .fullBadge"); if (fb) fb.onclick = () => openSwitchDetail();
    // 만석 표시 · 말풍선 · 도착지 이름이 덮는 지도 이름표(장소 · 건물)는 그 동안만 숨긴다 — 강조한 도착 · 건물 이름은 남김
    const boxes = $$("#agent .fullBadge rect, #agent .agentBubble rect, #agent .odLbl").map(e => { try { return e.getBBox(); } catch (x) { return null; } }).filter(Boolean);
    $$("#pins .visitLbl, #pins .vplace, #labels .lab").forEach(t => { let hit = false;
      if (boxes.length && !t.classList.contains("hlDest") && !t.classList.contains("hlB")) { try { const b = t.getBBox(); hit = boxes.some(bb => b.x < bb.x + bb.width && b.x + b.width > bb.x && b.y < bb.y + bb.height && b.y + b.height > bb.y); } catch (e) {} }
      t.classList.toggle("underBadge", hit); });
  }
  if (!$("#agent .fullBadge, #agent .agentBubble, #agent .odLbl, #agent .nowTag")) $$(".underBadge").forEach(t => t.classList.remove("underBadge"));
  $("#clock b").textContent = hhmm(T);
  $("#clock span").textContent = clockTxt ? `${dlabel(T)} · ${clockTxt}` : dlabel(T);
  $("#clock").classList.toggle("slowed", !!(PLAY && SLOWED));
  $("#slider").value = Math.round(1000 * (T - G.t0) / (G.t1 - G.t0));
  const ph = $("#strip .playhead");
  if (ph) ph.style.left = (STRIP.x(T)) + "px";
  drawVisitCard(moving);
  drawNowStep();
  // 지금 하는 행동을 일정 띠에서 보이게
  if (PLAY && ph) {
    const sc = $("#strip");
    const x = STRIP.x(T);
    if (x < sc.scrollLeft + 40 || x > sc.scrollLeft + sc.clientWidth - 80) sc.scrollLeft = x - 80;
  }
}

// ---------------------------------------------------------------------------
// 10/16 지도 방문 사진 카드 — 손님이 장소에 도착하면 그 지점 옆에 사진 카드. 이동을 시작하면 숨기고 다음 장소에서 바뀐다.
//   후기 손님: 그 블로그가 그 장소에서 찍은 사진(후기에서 관측된 방문일 때만) → 없으면 공식 사진
//   유형표 · 직접 만든 손님 · 후기에서 관측되지 않은 새 방문: 공식 사진. 사진이 없는 장소는 카드를 띄우지 않는다
//   사진은 저장소 밖 photos.local/ 에서만 (/api/photos). 시각 자료이지 시뮬레이션 행동의 증거가 아니다
// ---------------------------------------------------------------------------
let MAPPH = { official: {}, review: {}, credit: {} }, VCKEY = "";
const VISIT_CARD_ON_MAP = false;   // 10/17 UX 3차 · 장소 그림은 오른쪽 맨 위 대표 영역으로 옮김 (true 면 지도 위 카드도 다시 보임)
async function loadMapPhotos() { try { MAPPH = await api("/api/photos"); } catch (e) {} VCKEY = ""; }
const photoURL = f => "/local-photo/" + f.split("/").map(encodeURIComponent).join("/");
function visitPhoto(s) {
  const keys = [s.venue, s.location].filter(Boolean);
  const blog = G.review && G.review.blog ? String(G.review.blog).replace(/_ALT$/, "") : null;
  if (blog && MAPPH.review[blog]) {
    const seen = new Set((G.review.visited || []).map(v => v.loc));
    for (const k of keys) if (seen.has(k) && (MAPPH.review[blog][k] || []).length) return { f: MAPPH.review[blog][k][0], src: "review", blog, loc: k };
  }
  for (const k of keys) if ((MAPPH.official[k] || []).length) return { f: MAPPH.official[k][0], src: "official", loc: k, newVisit: !!(blog && !(G.review.visited || []).some(v => v.loc === k)) };
  return null;
}
function drawVisitCard(moving) {
  const card = $("#visitCard"), line = $("#vcline");
  const hide = () => { if (card) card.classList.add("hidden"); if (line) line.innerHTML = ""; VCKEY = ""; };
  if (!card || MODE !== "guest" || !G || moving || !VISIT_CARD_ON_MAP) return hide();
  const st = stepAt(T);
  if (!st || !LOC[st.location]) return hide();
  const ph = visitPhoto(st);
  if (!ph) return hide();
  const wrap = $("#mapWrap"), svg = $("#map");
  const key = `${G.st.indexOf(st)}|${ph.f}|${wrap.clientWidth}x${wrap.clientHeight}`;
  if (key === VCKEY && !card.classList.contains("hidden")) return;
  VCKEY = key;
  const credit = MAPPH.credit[ph.f] || "";
  card.innerHTML = `<img src="${photoURL(ph.f)}" alt="${esc(locName(ph.loc))} 사진"><div class="vc-meta"><span class="vc-src ${ph.src}">${ph.src === "review" ? `후기 사진 · ${esc(ph.blog)}` : "공식 사진"}</span><b>${esc(st.label || locName(ph.loc))}</b>${ph.newVisit ? `<small>후기에 없던 방문 · 장소 참고 사진</small>` : ""}${credit ? `<small>${esc(credit)}</small>` : ""}</div>`;
  card.onclick = () => placePanel(ph.loc);
  card.classList.remove("hidden");
  // 자리 고르기 — 지점 주변 8곳 중 동선 · 방문 지점 · 장소 이름 · 말풍선 · 시계 · 범례와 덜 겹치고 지도 안에 들어오는 곳
  const W = card.offsetWidth || 190, H = card.offsetHeight || 160;
  const ctm = svg.getScreenCTM(), wr = wrap.getBoundingClientRect();
  const toPx = (x, y) => { const pt = svg.createSVGPoint(); pt.x = x; pt.y = y; const q = pt.matrixTransform(ctm); return [q.x - wr.left, q.y - wr.top]; };
  const [ax, ay] = toPx(...LOC[st.location]);
  const rel = el => { const r = el.getBoundingClientRect(); return [r.left - wr.left, r.top - wr.top, r.width, r.height]; };
  const boxes = [...$$("#pins .visitLbl"), ...$$("#agent .agentBubble"), ...$$("#pins .pin.visited")].map(e => [rel(e), 4]);
  for (const id of ["#clock", "#mapLegend", "#mapView"]) { const e = $(id); if (e && e.offsetParent) boxes.push([rel(e), 30]); }
  const route = [];
  for (const l of G.legs) for (let i = 0; i <= 30; i++) route.push(toPx(...along(l.r, i / 30)));
  const g = 22, cands = [[g, -H / 2], [-W - g, -H / 2], [g, -H - g / 2], [-W - g, -H - g / 2], [g, g / 2], [-W - g, g / 2], [-W / 2, -H - g], [-W / 2, g]];
  const over = (a, b) => Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));
  let best = null;
  for (const [dx, dy] of cands) {
    const r = [ax + dx, ay + dy, W, H];
    let sc = 0;
    if (r[0] < 6 || r[1] < 6 || r[0] + W > wr.width - 6 || r[1] + H > wr.height - 6) sc += 1e6;
    for (const [b, wt] of boxes) sc += over(r, b) * wt / 100;
    for (const q of route) if (q[0] > r[0] - 6 && q[0] < r[0] + W + 6 && q[1] > r[1] - 6 && q[1] < r[1] + H + 6) sc += 5;
    if (ax > r[0] - 10 && ax < r[0] + W + 10 && ay > r[1] - 10 && ay < r[1] + H + 10) sc += 1e5;      // 방문 지점 자체는 절대 가리지 않는다
    if (!best || sc < best.sc) best = { sc, x: r[0], y: r[1] };
  }
  card.style.left = Math.round(best.x) + "px"; card.style.top = Math.round(best.y) + "px";
  // 지점과 카드 잇는 선 (지도 좌표로)
  const inv = ctm.inverse(), toSvg = (x, y) => { const pt = svg.createSVGPoint(); pt.x = x + wr.left; pt.y = y + wr.top; const q = pt.matrixTransform(inv); return [q.x, q.y]; };
  const ex = Math.min(Math.max(ax, best.x), best.x + W), ey = Math.min(Math.max(ay, best.y), best.y + H);
  const [sx, sy] = LOC[st.location], [tx, ty] = toSvg(ex, ey);
  line.innerHTML = `<line class="vcline" x1="${sx}" y1="${sy}" x2="${tx.toFixed(1)}" y2="${ty.toFixed(1)}"/>`;
}
window.addEventListener("resize", () => { VCKEY = ""; if (MODE === "guest" && G) drawFrame(); });

function tick(now) {
  const dt = last ? Math.min(0.1, (now - last) / 1000) : 0; last = now;   // 9차 · 탭을 다시 열었을 때 등 한 프레임이 길어도 0.1초 넘게 건너뛰지 않음
  if (PLAY) {
    let sp = +$("#speed").value;   // 화면 1초에 몇 분
    if (MODE === "guest" && G) {
      const s = G.segs.find(x => x.a <= T && T < x.b);
      if ($("#skipNight").checked && s && s.state === "IN_ROOM" && (s.b - s.a) > 240) sp *= 12;
      // 9차 · 이동 구간은 어떤 재생 속도에서도 화면에서 1초 이상 걸리게 — 빠른 재생에서 위치 표시가 한 번에 건너뛰지 않도록 (모델 시각은 그대로)
      //   10/17 UX 10차 · '이동 천천히' 로 켜고 끔. 늦추는 동안 시계에 표시하고, 끄면 고른 배속 그대로 (모델 시각 · 일정 · 위치 계산은 어느 쪽이든 같다)
      const slow = $("#slowMove").checked, mvl = slow ? G.legs.find(l => l.a <= T && T < l.b) : null;
      const sp0 = sp; if (mvl) sp = Math.min(sp, Math.max(0.5, (mvl.b - mvl.a) / moveMinSec(+$("#speed").value)));
      SLOWED = sp < sp0;
      const nxl = slow && !mvl ? G.legs.find(l => l.a > T) : null;   // 한 프레임에 이동 구간 하나를 통째로 건너뛰지 않게 다음 구간 시작에서 한 번 멈춘다
      T = nxl ? Math.min(T + dt * sp, nxl.a) : T + dt * sp;
      if (T >= G.t1) { T = G.t1; setPlay(false); }
      drawFrame();
    } else if (MODE === "day" && DAY) {
      DAYACC = (DAYACC || 0) + dt * sp / 10;
      if (DAYACC >= 1) { DAYT += Math.floor(DAYACC); DAYACC -= Math.floor(DAYACC); if (DAYT >= DAY.slots.length - 1) { DAYT = DAY.slots.length - 1; setPlay(false); } drawDay(); }
    }
  }
  requestAnimationFrame(tick);
}
let DAYACC = 0;
const MOVE_MIN_SEC = 1.0;
// 10/17 UX 10차 · 빠르게 · 아주 빠르게에서는 0.7초 — 하루 재생이 고른 배속보다 지나치게 길어지지 않게 (59명 측정: 아주 빠르게 6.4초 → 1초 규칙 11.2초)
const moveMinSec = sp => sp >= 40 ? 0.7 : MOVE_MIN_SEC;
let SLOWED = false;
function setPlay(on) {
  if (on && MODE === "guest" && G && T >= G.t1) T = G.t0;
  if (on && MODE === "day" && DAY && DAYT >= DAY.slots.length - 1) DAYT = 0;
  if (on && MODE === "day" && MAPVIEW !== "now") { MAPVIEW = "now"; $$("#mapView button").forEach(b => b.classList.toggle("on", b.dataset.v === "now")); }
  PLAY = on; $("#btnPlay").textContent = on ? "❚❚" : "▶";
}

// 지도 위 장소 점 — 손님 한 팀에서는 바탕을 누르고 그 팀의 하루 동선 · 들른 곳만 진하게 (10/15 v1.31)
const ptsD = pts => "M" + pts.map(q => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" L");
// ---------------------------------------------------------------------------
// 10/17 14차 · 지도 이름표 — HTML/SVG 층(#labels)의 작은 카드. 두 모드가 같은 부품을 쓰되 보여 주는 것과 강조가 다르다
//   하루 전체: 일반 시설은 이름만 · 주요 호텔은 자리가 있으면 이름 아래 작은 글씨로 인원 · 업장 수 · 혼잡은 실제일 때만 작은 배지 (drawDay 가 LABSTAT 에 채움)
//   손님 한 팀: 카드 · 그림자 없이 작은 회갈색 글자 (주요 호텔만 옅은 카드), 집계 글자 없음. 현재 행동 말풍선과 같은 시설의 이름표는 숨김 (drawFrame)
//   글자 크기는 화면 기준(일반 12.5px · 주요 13.5px · 보조 11px)이라 지도 배율 k 로 환산한다. 카드 너비는 가장 긴 숫자 틀로 재서 재생 중 흔들리지 않는다
const LABSTAT = {}, LABSHIFT = new Set(); let LABLINE = null;   // LABSHIFT = 이번 구간에서 이동선에 걸린 이름표 → 네 방향 중 선과 안 겹치는 자리로 · LABLINE = 지금 이동 구간 점들
let LABW_CANVAS = null;
function textW(t, px, bold) {
  const c = LABW_CANVAS || (LABW_CANVAS = document.createElement("canvas").getContext("2d"));
  c.font = `${bold ? 700 : 500} ${px}px Pretendard, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", system-ui, sans-serif`;
  return c.measureText(t).width;
}
function labelTarget(l) { return l.b ? { b: l.b } : l.loc ? { loc: l.loc } : null; }
function drawLabels() {
  const svg = $("#labels"); if (!svg) return;
  const k = mapK(), guest = MODE === "guest" && !!G, open = MODE === "day" ? OPENB : null;
  const out = [];
  for (const l of LABELS) {
    const st = MODE === "day" && (l.b || l.loc) ? LABSTAT[l.b || l.loc] : (guest && ROUTEALL && (l.b || l.loc) ? GVSTAT[l.b || l.loc] || null : null);   // 17차 · 전체 동선: 건물 '내부 n구간' · 방문지 'n회 방문'   // 15차 · 운영 수치는 하루 전체에서만 (손님 한 팀은 돌리기 전에도 이름만)
    const line2 = st && st.line2 && open !== l.b ? st.line2 : null, badge = st && st.badge && open !== l.b ? st.badge : null;
    const f = (l.big ? 13.5 : l.aux ? 11 : 12.5) * k, f2 = 11 * k, fb = 10.5 * k, padX = 7 * k, padY = 4 * k, gap = 6 * k;
    const bw = badge ? textW(badge, fb, true) + 10 * k : 0;
    const w1 = textW(l.name, f, !!l.big) + (badge && !line2 ? bw + gap : 0), w2 = line2 ? textW(st.line2w || line2, f2) + (badge ? bw + gap : 0) : 0;
    const w = Math.max(w1, w2) + padX * 2, h = (line2 ? f + f2 + 5 * k : f) + padY * 2 + 1 * k;
    const place = d => d === "n" ? [l.at[0] - w / 2, l.at[1] - h + 4 * k] : d === "s" ? [l.at[0] - w / 2, l.at[1] - f + 1 * k] : d === "e" ? [l.at[0] + 14 * k, l.at[1] - h / 2] : d === "w" ? [l.at[0] - w - 14 * k, l.at[1] - h / 2]
      : d === "ne" ? [l.at[0] + 10 * k, l.at[1] - h - 12 * k] : d === "nw" ? [l.at[0] - w - 10 * k, l.at[1] - h - 12 * k] : d === "se" ? [l.at[0] + 10 * k, l.at[1] + 12 * k] : [l.at[0] - w - 10 * k, l.at[1] + 12 * k];
    let dir = l.dir, [x, y] = place(dir);
    if (y < 2 || y + h > MAP_H - 2) { dir = l.alt; [x, y] = place(dir); }
    if (LABSHIFT.has(l.name) && LABLINE) {   // 이동선에 걸린 이름표 — 기본 · 반대 · 좌 · 우 중 선과 겹치지 않는 첫 자리
      const hits = (px, py) => LABLINE.filter(q => q[0] > px - 4 && q[0] < px + w + 4 && q[1] > py - 4 && q[1] < py + h + 4).length;
      let best = null;
      for (const d of [l.dir, l.alt, "e", "w", "ne", "nw", "se", "sw"]) { const [px, py] = place(d); if (px < 3 || px + w > MAP_W - 3 || py < 2 || py + h > MAP_H - 2) continue; const n = hits(px, py); if (!best || n < best.n) best = { d, px, py, n }; if (n === 0) break; }
      if (best) { dir = best.d; x = best.px; y = best.py; }
    }
    x = Math.max(3, Math.min(MAP_W - w - 3, x)); y = Math.max(2, Math.min(MAP_H - h - 2, y));
    const tg = labelTarget(l), attrs = tg ? (tg.b ? ` data-b="${tg.b}"` : ` data-loc="${tg.loc}"`) : "";
    const cls = `lab${l.big ? " big" : ""}${l.aux ? " aux" : ""}${tg ? " hit" : ""}${open === l.b ? " opened" : ""}${line2 ? " two" : ""}${st && st.vkey ? " vlab" : ""}`;
    const tx = x + padX, ty1 = y + padY + f * 0.82;
    let g = `<g class="${cls}" data-name="${esc(l.name)}"${attrs}${st && st.vkey ? ` data-vkey="${st.vkey}"` : ""}>` + (guest && !l.big && !line2 ? "" : `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="${(6 * k).toFixed(1)}"/>`) +
      `<text class="t1" x="${tx.toFixed(1)}" y="${ty1.toFixed(1)}" style="font-size:${f.toFixed(1)}px">${esc(l.name)}</text>`;
    if (line2) g += `<text class="t2" x="${tx.toFixed(1)}" y="${(ty1 + f2 + 4 * k).toFixed(1)}" style="font-size:${f2.toFixed(1)}px">${esc(line2)}</text>`;
    if (badge) { const bx = x + w - padX - bw, by = line2 ? ty1 + 4 * k + f2 - fb * 0.95 : ty1 - fb * 0.95, bh = fb * 1.45;
      g += `<g class="badge ${st.badgeCls || "full"}"><rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="${(bh / 2).toFixed(1)}"/><text x="${(bx + bw / 2).toFixed(1)}" y="${(by + bh * 0.72).toFixed(1)}" text-anchor="middle" style="font-size:${fb.toFixed(1)}px">${esc(badge)}</text></g>`; }
    out.push(g + `</g>`);
  }
  svg.innerHTML = out.join("");
  // 이름표끼리 겹치면 — 우선순위(펼친 · 주요 호텔 → 일반 → 보조)가 낮은 쪽을 반대 방향으로 옮기고, 그래도 겹치면 숨긴다
  const els = $$("#labels .lab"), pri = e => e.classList.contains("opened") ? 3 : e.classList.contains("big") ? 2 : e.classList.contains("aux") ? 0 : 1;
  const bb = e => { try { return e.getBBox(); } catch (x) { return null; } }, ov = (a, b) => a && b && !(a.x + a.width < b.x - 2 || b.x + b.width < a.x - 2 || a.y + a.height < b.y - 1 || b.y + b.height < a.y - 1);
  const byPri = [...els].sort((a, b) => pri(b) - pri(a)), kept = [];
  for (const e of byPri) {
    let b = bb(e); if (!b) continue;
    if (kept.some(q => ov(b, q))) {
      const l = LABELS.find(x => x.name === e.dataset.name), r = e.querySelector("rect"), ts = e.querySelectorAll("text"), bd = e.querySelector(".badge");
      if (l) { // 반대 방향으로 한 번 옮겨 본다 (세로 방향만 바꿈: n ↔ s)
        const dy = (l.dir === "n" ? 1 : -1) * (b.height - 4 * k + (l.dir === "n" ? (b.height - (13.5 * k)) : 0));
        const shift = (el, attr, d) => el && el.setAttribute(attr, (+el.getAttribute(attr) + d).toFixed(1));
        shift(r, "y", dy); ts.forEach(t => shift(t, "y", dy)); if (bd) { shift(bd.querySelector("rect"), "y", dy); shift(bd.querySelector("text"), "y", dy); }
        b = bb(e);
        if (kept.some(q => ov(b, q)) || b.y < 2 || b.y + b.height > MAP_H - 2) { e.classList.add("off"); continue; }
      } else { e.classList.add("off"); continue; }
    }
    kept.push(b);
  }
  $$("#labels .lab[data-loc]").forEach(e => e.onclick = () => placePanel(e.dataset.loc));
  $$("#labels .lab[data-b]").forEach(e => e.onclick = () => { if (MODE === "day" && DAY) { OPENB = OPENB === e.dataset.b ? null : e.dataset.b; drawDay(); } else placePanel(BLDG[e.dataset.b].locs[0]); });
  // 17차 · 전체 동선 모드: 방문한 건물 · 장소 이름표를 누르면 지도에 무엇을 더 그리지 않고 오른쪽 목록에서 그 방문들을 강조한다
  $$("#labels .lab[data-vkey]").forEach(e => e.onclick = ev => { ev.stopPropagation(); hlVisits(e.dataset.vkey); });
}
window.addEventListener("resize", () => { drawLabels(); if (MODE === "day" && DAY) declutterLabels(); });

function drawPins() {
  const guest = !!(G && MODE === "guest");
  const visited = new Set(guest ? G.segs.map(s => s.location) : []);
  const show = Object.keys(LOC).filter(c => !/STN|ICN/.test(c) && (guest || !LOC2B[c]) && !(guest && ROUTEALL && bldgOf(c)));   // 하루 전체에서는 건물 안 장소를 건물 원 하나로 · 17차 마무리: 전체 동선에서는 건물 안 장소 점을 숨긴다(건물 이름표 '내부 n구간' 이 대신함)
  const truth = new Map((guest && G.review ? G.review.visited : []).map(t => [t.loc, t]));
  if (guest) $("#pins").classList.remove("dimmed");
  // 10/17 9차 · 범례 — 지금 행동 보기와 전체 동선 보기에서 보이는 것만
  if (guest) { $("#mapLegend").classList.remove("hidden"); $("#mapLegend").innerHTML = ROUTEALL
    // 16차 · 전체 동선 모드 범례 — 하루 경로(차콜 · 화살표) · 방문 번호 · 현재 위치(코발트)
    ? `<span><i class="lg-cur"></i>현재 위치</span><span><i class="lg-past"></i>지나온 길</span><span><i class="lg-fut2"></i>앞으로 갈 길</span><span><i class="lg-now"></i>지금 이동 구간</span>` + (G._cmp ? `<span><i class="ghostkey"></i>기준 운영 동선</span>` : "") + `<span class="muted">건물 이름 아래 '내부 n구간'${noteI("건물 안에서 머문 방문 구간 수입니다(입장 횟수가 아님). 이름표를 누르면 오른쪽 목록에서 그 방문들이 강조됩니다. 선은 건물 사이 이동 중 지도의 길로 확인된 구간만 그리고, 건물 안 이동 · 연결 통로는 오른쪽 목록의 '들어온 길' 에 적습니다.")}</span><span class="muted">모델 시뮬레이션 결과${noteI("이 경로는 모델이 만든 하루 전체 시뮬레이션 결과이며 실제 관측 기록이 아닙니다. 앞으로 갈 곳도 같은 계산에서 나온 예측입니다.")}</span>`
    : `<span><i class="lg-cur"></i>현재 위치</span><span><i class="lg-od"></i>출발 → <i class="lg-dest"></i>도착</span><span><i class="lg-now"></i>지금 이동 구간</span><span><i class="lg-done"></i>지나온 길</span><span><i class="lg-full"></i>만석이 난 곳<i class="lg-sw"></i>바뀐 목적지</span><span><i class="lg-in"></i>건물 안 · 연결 통로 이동</span><span><i class="lg-last"></i>마지막 기록 (현재 위치 아님)</span><span class="muted">개략 이동 표시${noteI("선은 지도의 길을 따라 그린 개략 이동 표시이고 실제 보행 경로가 아닙니다. 건물 안 통로와 그랜드 ↔ 비스타 연결 통로(B1 · 로비 층)는 선을 그리지 않습니다. 위치 표시는 모델의 행동 시작 · 끝 시각 사이를 화면에서만 나눠 움직입니다.")}</span>` + (G._cmp ? `<span class="muted">기준 운영 동선은 '전체 동선'에서</span>` : ""); }
  // 시선 모으기 막 — 바깥은 종이색으로 옅게 누르고, 현재 위치 둘레(구멍)는 그대로. 구멍은 drawFrame 이 위치를 따라 옮긴다 (확대 · 이동 없음)
  $("#dim").innerHTML = guest ? `<defs><radialGradient id="spotG"><stop offset="0" stop-color="#000"/><stop offset=".55" stop-color="#000"/><stop offset="1" stop-color="#fff"/></radialGradient>` +
    `<mask id="spotMask" maskUnits="userSpaceOnUse" x="0" y="0" width="${MAP_W}" height="${MAP_H}"><rect width="${MAP_W}" height="${MAP_H}" fill="#fff"/><circle id="spotHole" cx="0" cy="0" r="190" fill="url(#spotG)"/></mask></defs>` +
    `<rect class="spotDim" width="${MAP_W}" height="${MAP_H}" fill="#fbf6ec" mask="url(#spotMask)"/><rect class="flatDim" width="${MAP_W}" height="${MAP_H}" fill="#fbf6ec"/>` +
    // 10/17 UX 10차 · 지금 건물 · 목적지 건물만 바탕 그림 원래 채도 · 대비로 (종이색 막 위에 같은 그림을 그 건물 모양으로 오려 덮음). 주변은 그대로 옅게
    `<clipPath id="bfClip"></clipPath><image id="bfImg" href="${MAP_IMG}" x="0" y="0" width="${MAP_W}" height="${MAP_H}" preserveAspectRatio="none" clip-path="url(#bfClip)"/>` : "";
  BFKEY = "";
  $("#map").classList.toggle("gfocus", guest && !ROUTEALL);
  const rb = $("#routeAll"); if (rb) rb.classList.toggle("hidden", !guest);
  GHOST = guest && G._cmp && ROUTEALL ? legsOf(G._cmp.A).filter(r => r.pts.length > 1 && !r.unknown).map(r => `<path class="routeGhost" d="${ptsD(r.pts)}"/>`).join("") : "";
  $("#route").innerHTML = GHOST; RAKEY = ""; RCKEY = ""; if (G !== (VISITS && VISITS.g)) { RCHL = null; RCOPEN.clear(); RC_CUR = -2; }   // 새로 돌린 손님이면 오른쪽 방문 목록도 다시 만든다
  // 17차 · 전체 동선 지도는 번호를 얹지 않는다 — 건물 이름표 둘째 줄에 '내부 n구간', 건물 밖 방문지 이름표에 'n회 방문' (GVSTAT · drawLabels).
  //   이름표가 없는 방문지(발레 데스크 등)만 작은 이름 글자를 점 옆에 둔다
  GVSTAT = guest && ROUTEALL ? visitStat() : {};
  const names = guest && ROUTEALL ? orphanNames() : "";
  $("#pins").innerHTML = show.map(c => {
    const [x, y] = LOC[c];
    const v = visited.has(c);
    const t = truth.get(c);
    const ring = t ? `<circle class="truthring ${v ? "ok" : "miss"}" cx="${x}" cy="${y}" r="9"/>` : "";
    return `<g class="pin hit ${v ? "visited" : guest ? "faded" : ""}" data-loc="${c}"><title>${esc(locName(c))}${t ? " · 후기가 간 곳" + (v ? " · 모델도 감" : " · 모델은 안 감") : ""}</title>${ring}<circle cx="${x}" cy="${y}" r="${v ? 5.5 : 3.5}"/></g>`;
  }).join("") + names;
  $$("#pins .pin").forEach(e => e.onclick = () => placePanel(e.dataset.loc));
  $$("#pins .vplace").forEach(e => e.onclick = ev => { ev.stopPropagation(); hlVisits(e.dataset.vkey); });
  if (guest || MODE !== "day") { for (const kk of Object.keys(LABSTAT)) delete LABSTAT[kk]; drawLabels(); }
  declutterLabels();
}
// 10/17 UX 4차 · 지도 이름표 정리 — 손님 한 팀에서는 바탕 건물 이름을 흐리게 하고, 들른 곳 · 인원 이름표와 겹치는 건물 이름은 숨긴다
function declutterLabels() {
  const svg = $("#map"); if (!svg) return;
  svg.classList.toggle("gmode", MODE === "guest" && !!G);
  const occ = [...$$("#pins .visitLbl"), ...$$("#pins .vplace"), ...$$("#heat .heatLbl"), ...(MODE === "guest" && !ROUTEALL ? [] : $$("#pins .pin.visited"))].map(e => { try { return e.getBBox(); } catch (x) { return null; } }).filter(Boolean);
  const fc = MODE === "day" ? FANC : null;
  $$("#labels .lab").forEach(t => {
    let b; try { b = t.getBBox(); } catch (x) { return; }
    let hit = occ.some(o => !(b.x + b.width < o.x - 2 || o.x + o.width < b.x - 2 || b.y + b.height < o.y - 1 || o.y + o.height < b.y - 1));
    // 펼친 건물 판 안에 걸리는 다른 이름표는 숨긴다 (펼친 건물 자신은 이름만 남김)
    if (fc) { const cx = Math.max(b.x, Math.min(fc.x, b.x + b.width)), cy = Math.max(b.y, Math.min(fc.y, b.y + b.height)); if (Math.hypot(cx - fc.x, cy - fc.y) < fc.R + 6) hit = true; }   // 카드가 펼친 판에 걸치면 숨김 (펼친 건물 자신 포함 · 판 제목이 이름을 대신함)
    t.classList.toggle("off", hit);
  });
}

// ---------------------------------------------------------------------------
// 일정 띠
// ---------------------------------------------------------------------------
const STRIP = { x: () => 0 };
function drawStrip() {
  const el = $("#strip");
  el.style.height = "";
  const span = G.t1 - G.t0;
  const ppm = Math.max((el.clientWidth - 20) / span, 0.85);
  const W = span * ppm + 20;
  STRIP.x = t => 10 + (t - G.t0) * ppm;
  let h = `<div class="strip-inner" style="width:${W}px">`;
  h += `<div class="strip-axis">`;
  const step = ppm > 2.5 ? 30 : ppm > 1.2 ? 60 : 120;
  for (let t = Math.ceil(G.t0 / step) * step; t <= G.t1; t += step) {
    const d = new Date(t * 60000);
    const isDay = d.getHours() === 0 && d.getMinutes() === 0;
    h += `<span class="${isDay ? "day" : ""}" style="left:${STRIP.x(t)}px">${isDay ? dlabel(t) : hhmm(t)}</span>`;
  }
  h += `</div>`;
  for (const l of G.legs) {
    const x = STRIP.x(l.a), w = Math.max(2, (l.b - l.a) * ppm);
    h += `<div class="blk k-move" style="left:${x}px;top:30px;width:${w}px;height:6px;padding:0;border-radius:3px" title="이동 ${Math.round(l.b - l.a)}분"></div>`;
  }
  // 19차 · 체류(행동 없음) · 세부 일정 미지정 · 위치 미확정 구간을 공통 구간표(G.iv)에서 그린다 — 지도 · 상태 카드와 같은 판정
  for (const g of G.iv) {
    const x = STRIP.x(g.a), w = Math.max(3, (g.b - g.a) * ppm - 1);
    if (g.k === "gap") { h += `<div class="blk k-gap" data-ta="${g.a}" data-tb="${g.b}" style="left:${x}px;top:40px;width:${w}px" title="세부 일정 미지정 ${hhmm(g.a)}–${hhmm(g.b)} · 마지막 기록 ${esc(nameOk(g.last.loc) || "")} ${g.last.how === "체류 끝" ? "체류 종료" : "도착"} · 현재 위치 미확정">${w > 70 ? "일정 미지정" : ""}</div>`; continue; }
    if (g.k === "unres") { h += `<div class="blk k-unres" data-ta="${g.a}" data-tb="${g.b}" style="left:${x}px;top:40px;width:${w}px" title="위치 미확정 · ${esc(g.unres || "")} (${esc(g.loc || "")}) ${hhmm(g.a)}–${hhmm(g.b)}">${w > 60 ? "위치 미확정" : ""}</div>`; continue; }
    if (g.k !== "stay" || !g.seg || G.st.some(s => s.a < g.b - 0.5 && s.b > g.a + 0.5) || !nameOk(g.loc)) continue;
    h += `<div class="blk k-stay" data-ta="${g.a}" data-tb="${g.b}" style="left:${x}px;top:40px;width:${w}px" title="${esc(nameOk(g.loc))} · 머무는 중 ${hhmm(g.a)}–${hhmm(g.b)} (세부 행동 미지정)">${w > 60 ? "머무는 중" : ""}</div>`;
  }
  G.st.forEach((s, i) => {
    const x = STRIP.x(s.a), w = Math.max(6, (s.b - s.a) * ppm - 1);
    const amt = s.spend.reduce((a, b) => a + b.krw, 0);
    h += `<div class="blk k-${s.kind} ${s.switch && s.switch["원래"] ? "switch" : ""} ${SEL === i ? "sel" : ""}" data-i="${i}" data-ta="${s.a}" data-tb="${s.b}" style="left:${x}px;top:40px;width:${w}px" title="${esc(nmDisp(s.label))} ${hhmm(s.a)}–${hhmm(s.b)}">${w > 34 ? esc(nmDisp(s.label)) : ""}<small>${w > 50 ? hhmm(s.a) : ""}</small></div>`;
    if (amt > 0 && w > 40) h += `<div style="position:absolute;left:${x}px;top:80px;font-size:10px;color:var(--ink2)">${(amt / 10000).toFixed(1)}만</div>`;
  });
  h += `<div class="legend" style="position:absolute;left:10px;bottom:2px">${Object.entries(KNAME).map(([k, n]) => `<span><i style="background:${KCOL[k]}"></i>${n}</span>`).join("")}<span><i style="background:#d9cfbf"></i>이동</span><span><i class="lg-stay"></i>머무는 중</span><span><i class="lg-gap"></i>일정 미지정</span><span><i class="lg-unres"></i>위치 미확정</span><span class="muted">${noteI("머무는 중: 체류 기록은 있으나 그 시각의 세부 행동이 정해지지 않음. 일정 미지정: 체류가 끝나거나 이동이 도착한 뒤 다음 기록까지 위치 · 행동이 정해지지 않은 시간(현재 위치 미확정 · 머무름 · 대기로 보지 않음). 위치 미확정: 기록은 있으나 지도 좌표 · 시각 데이터를 확인해야 하는 구간.")}</span><span style="color:var(--neg)">만석 = 원래 가려던 곳에 자리가 없었음</span></div>`;
  h += `<div class="playhead" style="left:${STRIP.x(T)}px"></div></div>`;
  el.innerHTML = h;
  $$("#strip .blk[data-i]").forEach(e => e.onclick = () => selectStep(+e.dataset.i));
}

function selectStep(i) {
  SEL = i;
  const s = G.st[i];
  T = s.a + 0.5; setPlay(false);
  $$("#strip .blk[data-i]").forEach(e => e.classList.toggle("sel", +e.dataset.i === i));
  drawFrame(); renderStep(s);
}

// ---------------------------------------------------------------------------
// 오른쪽 — 손님 한 팀 (10/17 UX 3차 · 주인공은 선택한 손님)
//   맨 위: 모델 시각 · 지금 장소 그림 · 지금 행동 · 다음 행동 (drawNowStep 이 행동이 바뀔 때마다)
//   그다음: 지금까지 결제 · 들른 곳 (같은 때 갱신) → 주요 변화 한 가지 (만석 선택 변경 · 비교 요약 · 재현 평가 요약)
//   맨 아래: 하루 일정. 선택 이유 · 전체 계산 · 손님 조건 · 비교표 · 재현 평가 표는 넓은 상세 패널에서
// ---------------------------------------------------------------------------
const PIMG_BADGE = { concept: "콘셉트 이미지", team_photo: "팀 촬영 사진", official_permitted: "공식 사진" };
// 장소 그림 — 시설 썸네일 목록(place_img/manifest.json, 콘셉트 이미지)이 먼저, 없으면 로컬 현장 사진, 둘 다 없으면 null
// 10/17 8차 · 그림과 모델 장소가 어긋나 잠시 쓰지 않는 콘셉트 이미지 — 사우나 그림은 한강 뷰 노천탕(비스타 웰니스 클럽 쪽 모습)인데
//   모델의 WELLNESS_SAUNA 는 그랜드 피트니스 센터(지하 2층 · 전망 없음) 한 곳이다. 모델에서 두 사우나를 나누면 비스타 쪽에 다시 쓴다 (파일은 그대로 둠)
// 10/17 15차 · 사용자가 새 사우나 그림(실내 탕)을 줘서 보류를 풂. 다시 막을 때는 { WELLNESS_SAUNA: true }
const IMG_HOLD = {};
function placeImg(loc) {
  if (!loc || IMG_HOLD[loc]) return null;
  let it = null; try { const P = window.PLACE_THUMBS; it = P ? (P.pick ? P.pick(loc) : (P.list() || {})[loc]) : null; } catch (e) {}   // 15차 · 와인페어 날 포레스트 파크는 와인페어 그림
  if (it) return { src: "/static/place_img/" + encodeURIComponent(it.file), name: it.name || locName(loc), credit: it.credit || PIMG_BADGE[it.kind] || "", loc };
  const f = ((LIB.photos || {})[loc] || [])[0];
  if (f) return { src: "/local-photo/" + encodeURIComponent(f), name: locName(loc), credit: "현장 사진", loc };
  return null;
}
const GSTATE = { checkin: "도착 · 체크인", room: "객실", meal: "식사 중", facility: "시설 이용 중", event: "행사 참여", checkout: "체크아웃" };
function guestRunLabel() {
  const p = G.persona, d = dShort(p.start);
  if (G.review) return `후기 행동 재현 평가 · 후기 날짜 ${d} · 좌석 경쟁 없음`;
  const env = G._crowd ? "그 날 손님들과 함께" : "혼자 · 좌석 경쟁 없음";
  const an = G.anomaly ? G.anomaly.name : "추가 변동 없음";
  return G._cmp ? `기준 운영과 비교 · ${d} · ${an}` : `${d} · ${an} · ${env}`;
}
function renderPanel() {
  const p = G.persona;
  const nsw = G.st.filter(s => s.switch && s.switch["원래"]).length;
  let h = evReturnBar() + (G._back ? `<button class="back" id="backList">← 좌석 제약 팀 목록으로</button>` : "");
  h += `<div class="g-id"><div class="g-name">${esc(gShort(p))}${gFull(p) !== gShort(p) ? noteI(gFull(p)) : ""}</div><div class="g-run">${esc(guestRunLabel())}</div></div>`;
  h += `<div class="gnow" id="nowStep"></div>`;
  h += `<div class="tiles g-tiles" id="gTiles"></div>`;
  // 주요 변화 한 가지 — 비교 실행이면 비교 요약, 후기 재현 평가면 재현 요약, 아니면 만석으로 바뀐 선택
  if (G._cmp) h += cmpSummary(G);
  else if (G.review) h += reviewSummary(G.review);
  else h += switchSummary(nsw);
  h += `<div class="card g-day"><div class="g-sec">하루 일정 <span>${G.st.length}개 행동 · 누르면 모델 선택 근거</span></div><ul class="itin withph">${itinRows()}</ul></div>`;
  h += `<div class="dact"><button class="rv-btn" id="btnGuestCond">손님 조건</button><button class="rv-btn" id="btnGuestDetail" title="매출이 합쳐지는 길 L5 → L1 · 선택에 작용한 요인 · 성향">선택 계산 · 결제 상세</button></div>`;
  $("#panel").innerHTML = h;
  $("#btnGuestDetail").onclick = () => openGuestDetail();
  $("#btnGuestCond").onclick = () => openGuestCond();
  const bc = $("#btnCmpDetail"); if (bc) bc.onclick = () => openCmpDetail(G);
  const br = $("#btnRevDetail"); if (br) br.onclick = () => openDrawer(`후기 행동 재현 평가 · ${G.review.blog}`, "후기에 적힌 날짜 · 좌석 경쟁 없이 같은 손님을 여러 번 돌린 결과", reviewCard(G.review), null, { wide: true });
  const bs = $("#btnSwDetail"); if (bs) bs.onclick = () => openSwitchDetail();
  NOWSTEP_I = null; drawNowStep();
  if (G._back) $("#backList").onclick = () => { const f = G._back; setMode("day"); f(); };
  $$("#panel .itin li[data-i]").forEach(e => e.onclick = () => selectStep(+e.dataset.i));
  bindReturnBar();
}
// 하루 일정 — 장소 그림은 식사 · 시설 · 행사, 객실은 같은 객실이 이어지면 첫 줄, 체크인 · 체크아웃 장소는 그림이 있을 때 첫 줄만
function itinRows() {
  let lastRoom = null, lastDesk = null;
  return G.st.map((s, i) => {
    const loc = s.venue || s.location, amt = s.spend.reduce((a, b) => a + b.krw, 0), im = placeImg(loc);
    const desk = (s.kind === "checkin" || s.kind === "checkout") && !!im && loc !== lastDesk;
    lastDesk = (s.kind === "checkin" || s.kind === "checkout") ? loc : null;
    const isRoom = s.kind === "room", show = desk || s.kind === "meal" || s.kind === "facility" || s.kind === "event" || (isRoom && loc !== lastRoom);
    if (isRoom) lastRoom = loc;
    const th = show && im ? `<img class="ithumb" src="${im.src}" alt="" loading="lazy">` : `<i class="ithumb blank"></i>`;
    const sw = s.switch && s.switch["원래"];
    return `<li data-i="${i}" class="${sw ? "isw" : ""}"><span class="it-t">${hhmm(s.a)}</span>${th}<span class="it-l"><i class="dot" style="background:${KCOL[s.kind]}"></i>${esc(altName(s.label))}${sw ? `<em class="sw">${esc(nmDisp(sw))} 만석</em>` : ""}</span><span class="amt">${amt ? (amt / 10000).toFixed(1) + "만" : ""}</span></li>`;
  }).join("");
}
function switchSummary(nsw) {
  const ta = (G.turned_away_here || []).length;
  if (!nsw) return `<div class="card g-state ok"><div class="gs-row"><span class="gs-dot ok"></span><b>선택 변경 없음</b></div><div class="gs-line">가려던 곳에 자리가 있어 계획대로 이용했습니다.${ta ? ` 좌석이 차서 후보에서 빠진 적은 ${ta}번 있습니다.` : ""}</div>${ta ? `<button class="rv-btn gs-btn" id="btnSwDetail">빠진 후보 보기</button>` : ""}</div>`;
  const S = G.st.filter(s => s.switch && s.switch["원래"]);
  const f = S[0];
  return `<div class="card g-state warn"><div class="gs-row"><span class="gs-dot warn"></span><b>만석으로 선택 변경 ${nsw}번</b></div>
    <div class="gs-line">${hhmm(f.a)} · <b>${esc(nmDisp(f.switch["원래"]))}</b> 만석 → ${esc(altName(f.label))}</div>${nsw > 1 ? `<div class="gs-line">그 밖에 ${nsw - 1}번 더 바뀜</div>` : ""}
    <button class="rv-btn gs-btn" id="btnSwDetail">변경 내역 · 빠진 후보</button></div>`;
}
function openSwitchDetail() {
  const S = G.st.map((s, i) => ({ s, i })).filter(x => x.s.switch && x.s.switch["원래"]);
  const ta = G.turned_away_here || [];
  let h = S.length ? `<div class="sw-list">${S.map(({ s, i }) => `<button class="sw-item" data-i="${i}"><span class="sw-t">${dlabel(s.a)} ${hhmm(s.a)}</span><span class="sw-m"><b>${esc(nmDisp(s.switch["원래"]))}</b> <span class="sw-x">만석</span> → <b>${esc(altName(s.label))}</b><small>${esc(s.switch["사유"] || "")} · 점수 ${s.switch["원래_점수"]} → ${s.switch["대체_점수"]}</small></span></button>`).join("")}</div>` : `<p class="hint">만석 때문에 바뀐 선택은 없습니다.</p>`;
  if (ta.length) {
    // 행동 키 → 화면 이름: 이 손님의 후보 목록에 나온 이름을 먼저, 없으면 고정 표
    const NM = { ondal: "온달", geum: "금룡", myong: "명월관", moegi: "모에기", pizza: "피자힐", buffet_b: "더뷔페 조식", buffet_l: "더뷔페 중식", buffet_d: "더뷔페 석식", pavilion: "더 파빌리온", lux: "럭스바", lounge: "클럽 라운지", pool: "실내수영장", forest: "포레스트 파크", sauna: "사우나" };
    G.st.forEach(s => (s.alts || []).forEach(a => { if (a.key && a.label && !NM[a.key]) NM[a.key] = a.label; }));
    const cnt = {}; ta.forEach(x => cnt[x.key] = (cnt[x.key] || 0) + 1);
    h += `<h4 class="dr-h">좌석이 차서 후보에서 빠진 횟수 <span class="hint">행동을 고를 때마다 셈 · 같은 곳이 여러 번 셀 수 있음</span></h4><table class="t dr-tbl"><colgroup><col><col style="width:120px"></colgroup><thead><tr><th>후보</th><th class="n">빠진 횟수</th></tr></thead><tbody>${Object.entries(cnt).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<tr><td>${esc(altName(NM[k] || k))}</td><td class="n">${n}번</td></tr>`).join("")}</tbody></table>`;
  }
  openDrawer(`${gShort(G.persona)} · 선택 변경 · 빠진 후보`, "항목을 누르면 그 행동의 모델 선택 근거로 갑니다", h, root => {
    root.querySelectorAll(".sw-item[data-i]").forEach(b => b.onclick = () => { closeDrawer(); selectStep(+b.dataset.i); });
  });
}
function reviewSummary(R) {
  const pc = x => Math.round((x || 0) * 100);
  return `<div class="card g-state"><div class="gs-row"><b>후기 행동 재현 평가</b><span class="gs-tag">관측 vs 모델</span></div>
    <div class="gs-kv"><span>후기 방문 중 모델도 감</span><b>${pc(R.recall_k)}%</b></div>
    <div class="gs-kv"><span>모델 방문 중 후기에도 있음</span><b>${pc(R.precision_k)}%</b></div>
    <div class="gs-line">이번 동선 ${R.n_hit} / ${R.n_scorable}곳 일치 · 비율은 ${R.k}번 돌린 평균</div>
    <button class="rv-btn gs-btn" id="btnRevDetail">재현 평가 표 보기</button></div>`;
}
// 비교 — 오른쪽에는 무엇이 얼마나 달라졌나 세 줄, 전체 표는 넓은 상세 패널(openCmpDetail)
function cmpParts(B) {
  const A = B._cmp.A, mA = mealsOf(A), mB = mealsOf(B);
  const keys = [...new Set([...Object.keys(mA), ...Object.keys(mB)])].sort();
  const changed = keys.filter(k => mA[k] !== mB[k]);
  return { A, mA, mB, keys, changed };
}
const signedWon = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(Math.round(v)).toLocaleString("ko-KR") + "원";
function cmpSummary(B) {
  const { A, keys, changed } = cmpParts(B);
  const dT = (B.spend_total || 0) - (A.spend_total || 0), sA = nSwitch(A), sB = nSwitch(B);
  const head = changed.length ? `${changed[0]} ${(cmpParts(B).mA[changed[0]] || "기록 없음")} → ${(cmpParts(B).mB[changed[0]] || "기록 없음")}` : "두 운영에서 같은 곳을 골랐습니다";
  return `<div class="card g-state" id="cmpSum"><div class="gs-row"><b>기준 운영 → 변경 운영</b><span class="gs-tag">${esc(B.anomaly ? B.anomaly.name : envName(B).split(" · ")[0])}</span></div>
    <div class="gs-kv"><span>팀 결제 합계</span><b class="${dT ? "chg" : ""}">${signedWon(dT)}</b></div>
    <div class="gs-kv"><span>만석으로 바꾼 선택</span><b class="${sA !== sB ? "chg" : ""}">${sA}번 → ${sB}번</b></div>
    <div class="gs-kv"><span>식사 장소가 바뀐 끼니</span><b class="${changed.length ? "chg" : ""}">${changed.length} / ${keys.length}끼</b></div>
    <div class="gs-line">${esc(head)}</div>
    <button class="rv-btn gs-btn" id="btnCmpDetail">전체 비교표 보기</button></div>`;
}
function openCmpDetail(B) {
  const blog = B._cmp.blog, { A, mA, mB, keys, changed } = cmpParts(B);
  const sit = R => [`${dShort(R.persona.start)} · ${R.scenario === "winefair" ? "와인페어 있음" : "행사 없음"}`, R === A ? "추가 변동 없음" : (R.anomaly ? R.anomaly.name : "추가 변동 없음"), envName(R)];
  const box = (t, R, on) => `<div class="cd-box ${on ? "on" : ""}"><small>${t}</small>${sit(R).map((x, i) => `<div class="${i === 1 && on && R.anomaly ? "chg" : ""}">${esc(x)}</div>`).join("")}</div>`;
  let h = `<div class="cd-sit">${box("기준 운영", A, false)}${box("변경 운영", B, true)}</div>`;
  const pref = R => (R.persona.prefers || []).map(locName).join(" · ") || "없음";
  h += `<h4 class="dr-h">끼니별 식사 장소</h4><table class="t cd-t"><colgroup><col style="width:24%"><col style="width:38%"><col style="width:38%"></colgroup>
    <thead><tr><th>끼니</th><th>기준 운영</th><th>변경 운영</th></tr></thead><tbody>
    <tr><td>가고 싶은 식당</td><td>${esc(pref(A))}</td><td class="${pref(A) !== pref(B) ? "chg" : ""}">${esc(pref(B))}</td></tr>` +
    keys.map(k => `<tr><td>${k}</td><td>${esc(mA[k] || "-")}</td><td class="${mA[k] !== mB[k] ? "chg" : ""}">${esc(mB[k] || "-")}</td></tr>`).join("") + `</tbody></table>`;
  const num = (lab, a, b, fmt, dfmt) => `<tr><td>${lab}</td><td class="n">${fmt(a)}</td><td class="n ${a !== b ? "chg" : ""}">${fmt(b)}</td><td class="n">${dfmt(b - a)}</td></tr>`;
  const cnt = v => v + "번", dc = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v) + "번";
  h += `<h4 class="dr-h">결과 수치</h4><table class="t cd-t"><colgroup><col style="width:28%"><col style="width:24%"><col style="width:24%"><col style="width:24%"></colgroup>
    <thead><tr><th>항목</th><th class="n">기준 운영</th><th class="n">변경 운영</th><th class="n">차이</th></tr></thead><tbody>` +
    num("만석으로 바꾼 선택", nSwitch(A), nSwitch(B), cnt, dc) + num("팀 결제 · 식음", fnbOf(A), fnbOf(B), won, signedWon) + num("팀 결제 · 전체", A.spend_total || 0, B.spend_total || 0, won, signedWon) + `</tbody></table>`;
  // 왜 달라졌나 — 운영 조건 · 좌석 경쟁 · 날짜에서 찾고, 취향 때문이라고 쓰지 않는다 (이전 비교 카드와 같은 규칙)
  const why = [];
  if (changed.length) why.push(`<b>바뀐 선택</b>: ${esc(changed.map(k => `${k} ${mA[k] || "기록 없음"} → ${mB[k] || "기록 없음"}`).join(" · "))}`);
  if (B.anomaly) why.push(`<b>${esc(B.anomaly.name)}</b>: ${esc((B.anomaly.applied || []).join(" · "))}`);
  if (envName(A) !== envName(B)) why.push(`운영 조건이 다릅니다: ${esc(envName(A))} → ${esc(envName(B))}`);
  const blk = R => R.steps.filter(s => s.switch && s.switch["원래"]).map(s => `${nmDisp(s.switch["원래"])} 만석 → ${altName(s.label)}`);
  const bA = blk(A), bB = blk(B), onlyB = bB.filter(x => !bA.includes(x)), onlyA = bA.filter(x => !bB.includes(x));
  if (onlyB.length) why.push(`변경 운영에서만 만석으로 빠진 곳: ${esc(onlyB.slice(0, 4).join(" · "))}${onlyB.length > 4 ? " 외" : ""}`);
  if (onlyA.length) why.push(`기준 운영에서만 만석으로 빠졌던 곳: ${esc(onlyA.slice(0, 4).join(" · "))}${onlyA.length > 4 ? " 외" : ""}`);
  if (!changed.length && A.spend_total === B.spend_total) why.push(`이 손님은 두 운영에서 같은 선택을 했습니다. 변경 운영이 이 손님의 후보에 닿지 않았거나, 기준 운영에서도 이미 그 업장이 막혀 있었기 때문입니다${bA.length ? ` (기준 운영에서도 만석으로 바꾼 선택 ${bA.length}번)` : ""}`);
  if (envName(A) !== envName(B)) why.push(`이 손님은 다른 손님이 모두 자리를 잡은 뒤에 들어가므로 늘린 좌석이 이미 차 있을 수 있습니다. 좌석 조건의 효과는 '상황 비교' 의 A/B 카드에서 보는 것이 더 정확합니다`);
  h += `<h4 class="dr-h">왜 달라졌나</h4><ul class="cd-why">${why.map(x => `<li>${x}</li>`).join("")}</ul>
    <p class="hint">성향 점수는 지금 모델의 선택에 쓰이지 않습니다(강도 0). 차이는 운영 조건 · 좌석 경쟁 · 날짜, 그리고 경로가 한 번 갈라진 뒤의 확률 선택 순서에서 나옵니다. ${blog ? "두 열 모두 모델 결과이고, 후기 방문 기록과의 대조는 왼쪽 ③ 별도 검증에서 봅니다. " : ""}지도의 회색 점선이 기준 운영 동선입니다.</p>`;
  openDrawer(`기준 운영 vs 변경 운영 · ${gShort(G.persona)}`, "같은 손님 · 같은 시드 · 같은 날짜", h, null, { wide: true });
}
// 손님 조건 — 이전 '손님 조건 자세히' 접기 내용 그대로
function openGuestCond() {
  const p = G.persona;
  const h = `<dl class="kv">
      <dt>후기 요약</dt><dd>${esc(gFull(p))}</dd>
      ${p.is_guest ? `<dt>객실 상품</dt><dd>${esc(p.package || "정하지 않음")}</dd><dt>포함</dt><dd>${p.included.length ? p.included.map(x => `${x[0]} ${locName(x[1])}`).join(" · ") : "식사 포함 혜택 없음"}${p.club ? " · 라운지 자격" : ""}</dd>` : `<dt>떠나는 시각</dt><dd>${p.depart}</dd>`}
      <dt>가고 싶은 곳</dt><dd>${p.prefers.length ? p.prefers.map(locName).join(" · ") + " (+3점)" : "없음"}</dd>
      <dt>예약 · 표</dt><dd>${p.booked.length ? p.booked.map(c => c === "FOREST_PARK" ? "와인페어 가기로 함 (+5 · +5)" : locName(c)).join(" · ") : "없음"}</dd>
      <dt>도착</dt><dd>${G.persona.start.replace("T", " ")}${p.arrival ? " · " + (p.arrival === "car_valet" ? "발렛" : "직접 주차") : ""}${p.is_guest ? " · 기상 " + p.wake : ""}</dd>
      <dt>다른 손님</dt><dd>${esc(niceKeys(G.crowd_note))}</dd>
      <dt>행사</dt><dd>${G.scenario === "winefair" ? "와인페어 있음 (투숙객 무료 입장 · 외부 손님 유료 · 표에 음식 교환권)" : "행사 없음"}</dd>
    </dl>${G.origin ? `<p class="hint">${esc(G.origin.blog)} 후기 손님의 속성(인원 · 객실 · 포함 끼니 · 도착 시각)은 그대로 두고 날짜만 ${esc(G.persona.start.slice(0, 10))} 로 옮겨 돌린 가상 실행입니다. 관측이 아닙니다.</p>` : ""}`;
  openDrawer(`${gShort(p)} · 손님 조건`, guestRunLabel(), h);
}
// 장소 그림 크게 보기
function openPlaceImage(loc) {
  const im = placeImg(loc); if (!im) return placePanel(loc);
  openDrawer(im.name, im.credit, `<figure class="pimg-big"><img src="${im.src}" alt="${esc(im.name)}"></figure><div class="dact" style="grid-template-columns:1fr"><button class="rv-btn" id="btnPlaceMore">${esc(im.name)} 업장 상세 보기</button></div>`, root => {
    root.querySelector("#btnPlaceMore").onclick = () => { closeDrawer(); placePanel(loc); };
  });
}
// 맨 위 대표 영역 — 행동이 바뀔 때만 다시 그리고, 그 사이에는 시각만 바꾼다
let NOWSTEP_I = null;
function drawNowStep() {
  const el = document.getElementById("nowStep"); if (!el || !G) return;
  const pn = document.getElementById("panel"); if (pn) pn.classList.toggle("rmode-all", ROUTEALL);   // 17차 · 전체 동선에서는 행동 단위 '하루 일정' 카드를 숨긴다(방문 목록과 중복)
  if (ROUTEALL) {   // 16차 · 전체 동선 모드: 현재 행동 카드 자리에 하루 전체 방문 요약 (현재 시각 · 행동은 그 카드 첫 줄에)
    NOWSTEP_I = null; drawRouteCard(el); drawGuestTiles();
    const stN = nowAt(T) && nowAt(T).st; $$("#panel .itin li[data-i]").forEach(li => li.classList.toggle("now", !!stN && +li.dataset.i === G.st.indexOf(stN)));
    return;
  }
  const now = nowAt(T), nx = nextStep(T);
  const key = now ? now.key : "x" + (nx ? G.st.indexOf(nx) : "end");
  if (key === NOWSTEP_I) { const tm = el.querySelector(".ns-t"); if (tm) tm.textContent = hhmm(T); return; }
  NOWSTEP_I = key;
  // 10/17 UX 4차 · 지도 말풍선과 같은 기준(nowAt). 보여 줄 위치가 없으면 장소 · 그림을 비우고 '다음 행동' 만 — 이전 장소를 대신 보이지 않는다
  const st = now && now.st, loc = now && now.mode !== "gap" && now.mode !== "unres" ? now.loc : null;   // 17차 마무리 · 기록 없는 시간에는 장소 그림을 띄우지 않는다
  const state = !now ? (T < G.st[0].a ? "도착 전" : nx ? "행동 사이" : "하루 끝") : now.mode === "move" ? "이동 중" : now.mode === "stay" ? "머무는 중" : now.mode === "gap" ? "다음 행동 전" : now.mode === "unres" ? "위치 미확정" : (GSTATE[st.kind] || "이용 중");
  // 15차 · 하루 일정이 끝나면 '동선 종료' 그림 (목록에 있을 때만)
  //   도착 전에는 '도착 전' 그림 (호텔 입구 · 짐 내리는 모습)
  let endIt = null; try { const P = window.PLACE_THUMBS; if (P && state === "하루 끝" && P.end) endIt = P.end(); else if (P && state === "도착 전" && P.arrival) endIt = P.arrival(); } catch (e) {}
  const ui = now && now.mode === "gap" ? unrecInfo(T) : null;
  const im = loc ? placeImg(loc) : endIt ? { src: "/static/place_img/" + encodeURIComponent(endIt.file), name: endIt.name || "", credit: endIt.credit || "" } : null, place = now ? (now.place || "") : "";
  const act = !now ? (T < G.st[0].a ? "아직 도착 전입니다" : nx ? "기록된 행동이 없는 시간입니다" : "오늘 일정이 끝났습니다") : now.mode === "stay" ? "머무는 중" : (now.act || place || "");
  const swo = curSwitch(now), sw = swo && swo["원래"];
  el.innerHTML = `<button class="gn-img ${im ? "" : "none"}" title="${esc(place || "현재 위치 없음")}${im ? " 크게 보기" : ""}" ${loc ? "" : "disabled"}>
      ${im ? `<img src="${im.src}" alt="${esc(place)}">` : `<span class="gn-noimg">${esc(now && (now.mode === "gap" || now.mode === "unres") ? "현재 위치 미확정" : place || "현재 위치 정보 없음")}</span>`}
      <span class="gn-time">모델 시각 <b class="ns-t">${hhmm(T)}</b></span>
      <span class="gn-state ${now && now.mode === "move" ? "mv" : sw ? "sw" : !now ? "off" : ""}">${sw && now.mode !== "move" ? "만석 · 선택 변경" : state}</span>
      ${im ? `<span class="gn-credit">${esc(im.credit)}</span>` : ""}
    </button>
    <div class="gn-body">
      ${now && (now.mode === "gap" || now.mode === "unres") ? "" : place && (now.mode === "move" || place !== act) ? `<div class="gn-place">${now.mode === "move" ? "가는 곳 · " : ""}${esc(place)}</div>` : ""}
      <div class="gn-act ${now ? "" : "off"}">${esc(act)}</div>
      ${now && now.mode === "stay" ? `<div class="gn-sub">세부 행동 미지정</div>` : ""}
      ${ui ? `<dl class="gn-dl"><dt>마지막 기록</dt><dd>${ui.last ? `${hhmm(ui.last.t)} · ${esc(nameOk(ui.last.loc) || "")} ${ui.last.how === "체류 끝" ? "체류 종료" : "도착 <small>(모델 이동 계산)</small>"}` : "없음"}</dd><dt>현재 위치</dt><dd>미확정${noteI("마지막 기록 뒤 다음 기록이 시작될 때까지 이 손님의 위치 · 행동은 시뮬레이션에서 정해지지 않았습니다. 머무름 · 이동 · 대기로 단정하지 않습니다. 모델은 이 시간을 다음 행동의 대기값으로만 점수에 반영합니다.")}</dd></dl>` : ""}
      ${now && now.mode === "unres" ? `<dl class="gn-dl"><dt>기록 장소</dt><dd>${esc(nameOk(now.code) || now.code || "-")}</dd>${stepAt(T) ? `<dt>행동</dt><dd>${esc(labOk(stepAt(T).label) || "")}</dd>` : ""}<dt>까닭</dt><dd>${esc(now.why)} · 데이터 · 지도 매핑 확인 필요</dd></dl>` : ""}
      ${loc === "WELLNESS_SAUNA" ? `<div class="gn-note">모델의 사우나는 그랜드 피트니스 센터(지하 2층) 한 곳입니다. 비스타 웰니스 클럽(3층) 사우나는 아직 모델에 따로 없습니다.</div>` : ""}
      ${sw ? `<div class="gn-sw" tabindex="0" title="지도에서 만석이 난 곳을 강조합니다"><div class="sw-flow"><span class="sf-a"><small>원래 선택</small><b>${esc(nmDisp(sw))}</b></span><i aria-hidden="true">→</i><span class="sf-b"><small>${swo["시각"] ? esc(String(swo["시각"]).slice(11, 16)) : "그때"}</small><b>${esc(/만석/.test(swo["사유"] || "") || !swo["사유"] ? "만석" : swo["사유"])}</b></span><i aria-hidden="true">→</i><span class="sf-c"><small>실제 대체 선택</small><b>${esc(altName(swo["대체"] || (st && st.label) || ""))}</b></span></div>${fullLoc(sw) ? `<div class="sf-note">지도의 빨간 표시가 만석이 난 곳입니다</div>` : ""}</div>` : ""}
      <div class="gn-next"><span>${ui ? "다음 일정" : "다음"}</span>${nx && nx !== st ? `${hhmm(seatA(nx))} · ${esc(altName(nx.label))}${seatA(nx) !== nx.a ? ` <small class="gn-seat">착석 · 식사 ${hhmm(nx.a)}</small>` : ""}` : now ? "오늘 마지막 행동" : "없음"}</div>
    </div>`;
  if (loc) el.querySelector(".gn-img").onclick = () => openPlaceImage(loc);
  const gs = el.querySelector(".gn-sw");
  if (gs) { const hl = on => { const b = document.querySelector("#agent .fullBadge"); if (b) b.classList.toggle("hl", on); };
    gs.onmouseenter = gs.onfocus = () => hl(true); gs.onmouseleave = gs.onblur = () => hl(false); }
  const curL = now && now.mode !== "move" ? now.ploc : null;
  $$("#pins .pin").forEach(g => g.classList.toggle("cur", g.dataset.loc === curL));
  drawGuestTiles();
  $$("#panel .itin li[data-i]").forEach(li => li.classList.toggle("now", !!st && +li.dataset.i === G.st.indexOf(st)));
}
// 지금까지 결제 · 들른 곳 — 모델 시각까지 시작한 행동만 더한다.
//   10/17 UX 4차 · 시점이 다른 두 숫자를 구분: 제목에 모델 시각을 넣고(“19:29까지”), 하루 전체 값은 막대 끝의 옅은 칸과 아래 줄로만
function drawGuestTiles() {
  const el = document.getElementById("gTiles"); if (!el) return;
  const done = G.st.filter(s => s.a <= T), lc = s => s.venue || s.location;
  const paid = done.reduce((a, s) => a + s.spend.reduce((x, y) => x + y.krw, 0), 0);
  const seen = new Set(done.map(lc)), all = new Set(G.st.map(lc));
  const end = T >= G.t1 - 0.5 || done.length === G.st.length;
  const at = end ? "하루 전체" : `${hhmm(T)}까지`;
  const tile = (lab, big, frac, tot) => `<div class="tile gt"><small><b>${at}</b> ${lab}</small><span class="big${String(big).length >= 11 ? " long xl" : String(big).length >= 10 ? " long" : ""}">${big}</span>` +
    `<span class="gt-bar" title="진한 칸 = ${at} · 옅은 칸 = 하루 전체"><i style="width:${Math.round(Math.min(1, frac) * 100)}%"></i></span>` +
    `<span class="sub">${end ? "모든 행동 끝" : `하루 전체 <b>${tot}</b>`}</span></div>`;
  el.innerHTML = tile("결제", won(paid), G.spend_total ? paid / G.spend_total : 0, won(G.spend_total)) + tile("들른 곳", `${seen.size}곳`, all.size ? seen.size / all.size : 0, `${all.size}곳`);
}

// 가설 실험 — 근거 · 예측 · 판정 기준 (hypotheses.csv)
// 10/17 UX — 손님 한 팀 상세 (매출이 합쳐지는 길 · 선택 요인 · 성향) · 내용은 이전 우측 패널 그대로
function openGuestDetail() {
  if (!G) return;
  let h = "";
  h += rollupCard();
  h += `<details class="card"><summary><b>이 손님의 선택에 작용한 요인 · 성향</b></summary><div class="hint" style="margin:6px 0">고른 행동마다 점수에 들어간 사유를 요인별로 더했습니다 (+ 는 그 행동을 고르게 한 쪽, − 는 막은 쪽).</div>${factorTable(G.st)}${traitTable(G.persona)}<div class="hint">${traitNote()}</div></details>`;
  openDrawer(`${gShort(G.persona)} · 선택 계산 · 결제 상세`, `${G.persona.start.slice(0, 10)} · ${G.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${niceKeys(G.crowd_note)}`, h, root => {
    root.querySelectorAll(".rlink[data-gomode]").forEach(a => a.onclick = () => { closeDrawer(); setMode(a.dataset.gomode); });
  });
}
function hypoCard(D) {
  const A = D.hypo;
  if (!A) return "";
  const live = (LIB.hypotheses || []).find(h => +h.ID === +A.id);
  const status = live ? live["상태"] : A.status;
  const op = live && live["운영 표시"], nx = live && live["다음 확인"];
  return `<div class="card anom"><h4>가설 실험 H${A.id} — ${esc(A.name)}</h4>${op ? `<div><span class="hstate ${HSTATE_CLS[op] || ""}">${esc(op)}</span>${nx ? ` <span class="hint">다음 확인: ${esc(nx)}</span>` : ""}</div>` : ""}<div class="callout info">상태 — ${esc(status || "")}</div>
    <ul class="applied">${A.applied.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
    <dl class="kv"><dt>근거</dt><dd>${esc(A.evidence)}</dd><dt>예측</dt><dd>${esc(A.predict)}</dd><dt>판정 기준</dt><dd>${esc(A.judge)}</dd><dt>담당</dt><dd>${esc(A.owner)} · ${esc(A.grade)}</dd></dl></div>`;
}
// 변칙 시나리오 — 무엇을 바꿨고 크기는 어디서 왔나
function anomalyCard(D) {
  const A = D.anomaly;
  if (!A) return "";
  return `<div class="card anom"><h4>변칙 시나리오 — ${esc(A.name)}${A.k !== 1 ? ` <span class="hint">(크기 ×${A.k})</span>` : ""}</h4>
    <div>${esc(A.desc)}</div><ul class="applied">${A.applied.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
    <dl class="kv"><dt>크기 출처</dt><dd>${esc(A.src)} <b>${esc(A.grade)}</b></dd><dt>한계</dt><dd>${esc(A.limit || "-")}</dd></dl></div>`;
}
// 시드 범위 — band.py 가 남긴 cache/band_<키>.json 이 있으면 (같은 조정값을 시드만 바꿔 여러 번)
async function bandCard(D) {
  const el = document.getElementById("bandCard");
  if (!el) return;
  let B;
  try { B = await api("/api/day/band?key=" + encodeURIComponent(D.key)); } catch (e) { return; }
  if (!B || !B.base) return;
  const isComp = B.compare_key === D.key;
  const S = isComp ? B.comp : B.base;
  const f = v => Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : (+v).toFixed(Math.abs(v) < 10 ? 2 : 1);
  const names = Object.keys(S);
  const strongOf = n => sureEffect(B.effect && B.effect[n], B.seeds);
  if (B.effect) names.sort((a, b) => (strongOf(b) - strongOf(a)) || ((B.effect[b].ratio || 0) - (B.effect[a].ratio || 0)));
  const nStrong = names.filter(strongOf).length;
  let h = `<details class="card band" open><summary><b>시드 ${B.seeds}개 범위</b>${B.effect ? ` <span class="hint">· 시드 반복에서 방향이 일관된 효과 ${nStrong}개 (위쪽 색 줄 · 실제 효과 검증은 아님)</span>` : ""} <span class="hint">(손님 생성 · 확률 선택 · 상품 추첨을 시드만 바꿔 ${B.seeds}번)</span></summary><table class="t"><tr><th>지표</th><th class="n">평균</th><th class="n">범위</th>${B.effect ? `<th class="n">${isComp ? "이 조정값 효과" : "비교 조정값 효과"}</th><th class="n">편차 대비</th>` : ""}</tr>` +
    names.map(n => {
      const s = S[n], e = B.effect && B.effect[n];
      const strong = sureEffect(e, B.seeds);
      return `<tr><td>${esc(n)}</td><td class="n">${f(s.mean)}</td><td class="n hint">${f(s.min)} ~ ${f(s.max)}</td>${e ? `<td class="n" style="color:${strong ? (e.diff > 0 ? "var(--pos)" : "var(--neg)") : "var(--ink3, #999)"}">${e.diff > 0 ? "+" : ""}${f(e.diff)}</td><td class="n hint">${e.ratio == null ? "-" : e.ratio + "배"} · ${e.same_sign}/${B.seeds}</td>` : ""}</tr>`;
    }).join("") +
    `</table><div class="hint">범위 = 시드 ${B.seeds}개의 최소 ~ 최대.${B.effect ? ` 효과 = 같은 시드끼리 짝지은 차이의 평균 (같은 시드면 손님이 같다). 편차 대비 = 효과 ÷ 시드 표준편차, 그 뒤 숫자는 ${B.seeds}번 중 같은 방향인 횟수. 색이 있는 줄은 짝지은 차이의 95% 구간이 0을 넘지 않고 거의 매번 같은 방향 — 시드 운이 아니라 조정값이 만든 차이로 읽어도 되는 것.` : ""}<span class="dev"> timeline/viewer/band.py</span></div></details>`;
  el.innerHTML = h;
}
// 오늘 한눈에 — 경영 · 운영 쪽이 처음 보는 자리 (10/14). 숫자 다섯 개 → 업장 막대 → 한 줄 요약, 누르면 아래 상세로
function dayStatsCard(D) {
  // 부문 비중은 온톨로지와 같은 기준 — 객실 첫 밤만, 온톨로지에 줄이 없는 와인페어 · 푸드트럭 · 빛의 시어터 제외 (ontoDayCard 와 같음)
  const NOT_IN_ONTO = ["와인페어", "와인페어 푸드트럭", "빛의 시어터"];
  const B2 = D.by_l2 || {};
  const l2 = { ROOM: (B2.ROOM || 0) - (D.room_extra_nights || 0), "F&B": B2["F&B"] || 0,
               "레저": (B2["레저"] || 0) - NOT_IN_ONTO.filter(k => l3of(D, k) === "레저").reduce((a, k) => a + (D.by_l3[k] || 0), 0) };
  const tot = Object.values(l2).reduce((a, b) => a + b, 0) || 1;
  const net = v => eok(v / 1.1);
  const th = D.theta || {};
  const rooms = th.rooms_onto ? 801 : 875;
  const occ = D.n_guest ? Math.round(D.n_guest / rooms * 100) : null;      // 그 날 체크인 객실 (한 팀 한 객실) ÷ 객실 수 — 온톨로지 '그 날 판매 객실박' 과 같은 뜻
  const vd = D.venue_detail || {};
  const V = Object.entries(vd).filter(([, v]) => v.parties > 0).map(([loc, v]) => ({ loc, v, occ: occOf(v), krw: v.krw || 0 }));
  const busiest = V.filter(x => x.occ != null).sort((a, b) => (b.occ - a.occ) || ((b.v.over_persons || 0) - (a.v.over_persons || 0)))[0];
  const topRev = V.slice().sort((a, b) => b.krw - a.krw)[0];
  const O = ontoRef(D); const oL2 = O && O.l2 ? O.l2 : null; const oTot = oL2 ? Object.values(oL2).reduce((a, b) => a + b, 0) || 1 : 1;
  const pc = x => Math.round(x * 100);
  const tile = (label, big, sub) => `<div class="kpi"><small>${label}</small><span class="big">${big}</span><span class="sub">${sub}</span></div>`;
  // 10/17 UX 2차 · 이 카드는 '전체 지표 상세' (드로어) 맨 위에 들어간다. 오른쪽 패널은 opsPanel 이 그린다 (숫자 · 함수는 그대로)
  let h = `<div class="card summary"><h4>하루 지표 <span class="vtag cum">하루 누적</span> <span class="hint">${esc(D.date.slice(5).replace("-", "/"))} · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"}${" · " + esc(knobSummary(D))}</span></h4><div class="kpis k3">` +
    tile("체류 매출 (그날 들어온 손님)", net(D.total), `<span id="kpiBand">VAT 제외 · 결제액 ${eok(D.total)}</span>${D.total_day != null ? ` · 그중 그날 지출 ${net(D.total_day)}` : ""}`) +
    tile("방문 팀", `${D.n.toLocaleString()}팀`, `${D.persons.toLocaleString()}명 · 투숙 ${D.n_guest} · 비투숙 ${D.n - D.n_guest}`) +
    (() => { const GG = D.guests || [], sw = GG.filter(g => (g.n_switch || 0) > 0).length;   // 팀 단위 · 중복 없음 (초과 수요는 막힌 팀의 일행 수라 팀 수와 단위가 다르다)
      return tile("공급 제한 겪은 팀", `${GG.length ? Math.round(sw / GG.length * 100) : 0}%`, `${GG.length.toLocaleString()}팀 중 ${sw.toLocaleString()}팀${busiest ? ` · 가장 꽉 찬 곳 ${esc(locName(busiest.loc))}` : ""}`); })() +
    `</div><details class="sfold"><summary>객실 · 부문 비중 더 보기</summary><div class="kpis">` +
    tile("투숙 팀 (그 날 체크인)", `${(D.n_guest || 0).toLocaleString()}팀`, occ != null ? `한 팀 한 객실로 보면 가동률 ${occ}% · ${rooms}실 기준` : "") +
    tile("부문 비중", `${pc((l2.ROOM || 0) / tot)} : ${pc((l2["F&B"] || 0) / tot)} : ${pc((l2["레저"] || 0) / tot)}`, `객실(첫 밤) : 식음 : 레저${oL2 ? ` · 온톨로지 ${pc((oL2.ROOM || 0) / oTot)} : ${pc((oL2["F&B"] || 0) / oTot)} : ${pc((oL2.LEISURE || 0) / oTot)}` : ""}`) +
    `</div></details>`;
  // 업장 한눈에 — 이용 인원 막대 (한 색) · 최고 점유율 · 초과 수요. 누르면 업장 상세. 매출 순 위 3곳만 먼저, 나머지는 펼치기
  const rows = V.filter(x => x.v.cap && x.v.persons_day > 0).sort((a, b) => b.krw - a.krw);
  const mx = Math.max(1, ...rows.map(x => x.v.persons_day || 0));
  const vrow = x => {
    const v = x.v, o = x.occ;
    return `<div class="vb click" data-loc="${x.loc}" title="${esc(locName(x.loc))} — 이 날 이용 ${v.persons_day} 인 · 회 · 순매출 ${net(x.krw)}"><span class="nm">${esc(locName(x.loc))}</span><span class="tr"><i style="width:${(v.persons_day || 0) / mx * 100}%"></i></span><span class="n">${(v.persons_day || 0).toLocaleString()}</span><span class="n ${o >= 95 ? "full" : ""}">${o == null ? "" : o + "%"}</span><span class="n ov">${v.over_persons ? "+" + v.over_persons + "명" : ""}</span></div>`;
  };
  h += `<div class="vbars"><div class="vb head"><span class="hint">업장 · 매출순</span><span class="hint" title="하루 이용 (인 · 회 · 회전 포함)">하루 이용</span><span class="hint">인 · 회</span><span class="hint" title="가장 붐비는 회차의 좌석 점유율">점유</span><span class="hint" title="수용 범위 초과 수요 · 막힌 팀의 일행 수 (팀마다 이 업장에서 처음 막힌 회차에 한 번)">초과</span></div>` + rows.slice(0, 3).map(vrow).join("") +
    (rows.length > 3 ? `<details class="vmore"><summary>전체 ${rows.length}개 업장 보기</summary>${rows.slice(3).map(vrow).join("")}</details>` : "") + `</div>`;
  const lines = [];
  if (topRev) lines.push(`매출 1위 업장: ${locName(topRev.loc)} (${net(topRev.krw)})`);
  if (busiest && busiest.occ >= 95) lines.push(`가장 꽉 찬 곳: ${locName(busiest.loc)} · 회차 점유 ${Math.round(busiest.occ)}% · 초과 수요 ${busiest.v.over_persons || 0}명 (막힌 팀의 일행 수)`);
  if (oL2) { const d = pc((l2["F&B"] || 0) / tot) - pc((oL2["F&B"] || 0) / oTot); lines.push(d === 0 ? "식음 비중: 온톨로지와 같음" : `식음 비중: 온톨로지보다 ${Math.abs(d)}p ${d > 0 ? "높음" : "낮음"}`); }
  h += `<div class="readline">${lines.map(x => `<div>${esc(x)}</div>`).join("")}</div><div class="hint">업장을 누르면 회차별 점유율 · 상품 · 온톨로지 대조로 내려갑니다. 초과 수요는 자리가 없어 다른 선택을 한 팀의 일행 수입니다(팀마다 업장별 한 번 · 중복 없음).</div></div>`;
  setTimeout(async () => {      // 시드 범위가 있으면 순매출 타일에 범위
    try { const B = await api("/api/day/band?key=" + encodeURIComponent(D.key)); const S = B && (B.compare_key === D.key ? B.comp : B.base); if (S && S["순매출 (억)"]) { const r = S["순매출 (억)"]; const el = document.getElementById("kpiBand"); if (el) el.textContent = `시드 ${B.seeds}개 ${(r.min / 1).toFixed(2)} ~ ${r.max.toFixed(2)}억`; } } catch (e) {}
  }, 0);
  return h;
}
// 프로그램 · 시설 — 운영 조건표(소연님 program_capacity.csv)의 정원 대비 이 날 모델 동시 인원 · 온톨로지 프로그램 풀 (대표님 10/13 '숲 체험 40명 중 4명이면 10%')
function programCard(D) {
  const P = LIB.programs || [];
  if (!P.length || !D.slots) return "";
  const d = new Date(D.date + "T00:00:00"), dow = "일월화수목금토"[d.getDay()];
  const ymd = D.date;
  const runs = r => {
    if (/리뉴얼|운영 안/.test(r["운영 기간"])) return false;
    if (!(r["요일"] === "매일" || r["요일"].includes(dow))) return false;
    const m = r["운영 기간"].match(/(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2})(-\d{2})?/);
    if (m) { const end = m[3] ? m[2] + m[3] : m[2] + "-31"; return m[1] <= ymd && ymd <= end; }
    return true;
  };
  const mins = t => { const [h, m] = (t || "0:0").split(":").map(Number); return h * 60 + m; };
  const peak = (loc, a, b) => {
    const pr = (D.present || {})[loc]; if (!pr) return null;
    let mx = 0;
    D.slots.forEach((t, k) => { const tm = mins(t) + (k >= 84 ? 1440 : 0); if ((tm >= a && tm < b) || (tm >= a + 1440 && tm < b + 1440)) mx = Math.max(mx, pr[k] || 0); });
    return mx;
  };
  const PD = ((LIB.onto_oct || {}).pool_def) || {};
  const onto = name => Object.values(PD).find(p => p.kind === "assumed" && p.venue && /워키/.test(p.venue) && name.includes(p.name));
  const rows = P.filter(runs);
  if (!rows.length) return "";
  const pc = (a, b) => b ? Math.round(a / b * 100) + "%" : "";
  const body = rows.map(r => {
    const capN = parseFloat(r["정원"]);
    const cap = !isNaN(capN) ? { n: capN, txt: `${r["정원"]} ${r["정원 단위"]} ${r["정원 등급"]}` } : (r["화면 가정 정원"] ? { n: +r["화면 가정 정원"], txt: `${r["화면 가정 정원"]} △ 화면 가정` } : null);
    const a = mins(r["시작"]), b = mins(r["끝"]);
    const pk = r["장소코드"] && r["장소코드"] !== "-" ? peak(r["장소코드"], a, b) : null;
    const model = r["장소코드"] === "-" ? '<span class="hint">모델에 행동 없음</span>' : pk == null ? '<span class="hint">이 날 이용 없음</span>' : `${pk}명${cap && cap.n ? ` · <b>${pc(pk, cap.n)}</b>` : ""}`;
    const o = onto(r["이름"]);
    const ot = o ? `${o.used_1010} / ${o.cap_1010}명 · ${pc(o.used_1010, o.cap_1010)} <span class="hint">가정</span>` : "";
    return `<tr><td>${esc(r["이름"])}<div class="hint">${esc(r["회차"])} · ${esc(r["시작"])}~${esc(r["끝"])}</div></td><td>${cap ? esc(cap.txt) : '<span class="hint">정원 비공개</span>'}</td><td class="n">${model}</td><td class="n">${ot}</td></tr>`;
  }).join("");
  return `<details class="card" open><summary><b>프로그램 · 시설 — 수용 범위 대비 이용</b> <span class="hint">(${D.date.slice(5)} ${dow} · 운영 중 ${rows.length}개)</span></summary><table class="t tight"><tr><th>프로그램 · 시설</th><th>정원</th><th class="n">모델 최대<br>동시 인원</th><th class="n">온톨로지<br>10/10</th></tr>${body}</table>
    <div class="hint">모델 최대 동시 인원 = 운영 시간 안에서 같은 시각에 그 장소에 있던 사람 수의 최댓값 (그 날 10시 ~ 다음날 13시 계산 범위 — 아침 시설은 다음날 아침 투숙객). 정원은 운영 조건표 (◎ 공식 · ○ 현장 · 간접 · △ 화면 가정). 공식에 정원이 없는 곳은 '정원 비공개' 로 두고 % 를 만들지 않습니다. 온톨로지 쪽은 프로그램 풀의 정원 · 이용 가정(일 정원 20명 · 적격 객실박 × 1%). 워키 프로그램은 아직 모델에 행동이 없어 온톨로지 가정만 나란히 둡니다.</div></details>`;
}

// 손님 한 팀의 매출이 합쳐지는 길 — L5 집계행 → L4 상품 → L3 업장 → L2 부문 → L1 (대표님 10/13 '아래에서 합산돼 올라가는 구조')
function rollupCard() {
  const p = G.persona;
  const lines = G.st.flatMap(s => s.spend.map(x => ({ ...x, when: s.t_in })));
  if (!lines.length) return "";
  const L2N = { ROOM: "객실 (ROOM)", "F&B": "식음 (F&B)", "레저": "레저 (LEISURE)" };
  const tree = {};
  for (const x of lines) {
    const a = (tree[x.l2] = tree[x.l2] || { krw: 0, l3: {} });
    const b = (a.l3[x.l3] = b0(a.l3[x.l3]));
    a.krw += x.krw; b.krw += x.krw;
    const c = (b.l4[x.product] = b.l4[x.product] || { krw: 0, qty: 0, grade: x.grade });
    c.krw += x.krw; c.qty += x.qty || 0;
  }
  function b0(v) { return v || { krw: 0, l4: {} }; }
  const day = G._crowd ? DAYCACHE[G._crowd] : null;
  const share = l3 => {
    if (!(day && day.by_l3 && day.by_l3[l3])) return "";
    const mine = lines.filter(x => x.l3 === l3).reduce((s, x) => s + x.krw, 0);
    return mine ? ` <span class="hint">· 그 날 이 업장 매출의 ${(mine / day.by_l3[l3] * 100).toFixed(2)}%</span>` : "";
  };
  const l5 = [p.start.slice(0, 10), p.sex || "성별 미설정", p.age || "연령 미설정", p.purpose || "목적 미설정", p.ai_type || "유형 미설정", p.is_guest ? "투숙" : "비투숙"];
  const tot = lines.reduce((s, x) => s + x.krw, 0);
  let h = `<div class="card rollup"><h4>이 팀의 매출이 합쳐지는 길 <span class="hint">L5 → L4 → L3 → L2 → L1</span></h4>
    <div class="hint">L5 집계행 열 — ${l5.map(esc).join(" · ")} (같은 열의 다른 손님과 한 줄로 합쳐짐)</div>
    <div class="tree up"><div class="l1"><span>L1 전체 매출에 더해지는 몫</span><span>${won(tot)}</span></div>`;
  for (const [l2, a] of Object.entries(tree).sort((x, y) => y[1].krw - x[1].krw)) {
    h += `<div class="l2"><span>L2 ${esc(L2N[l2] || l2)}</span><span>${won(a.krw)}</span></div>`;
    for (const [l3, b] of Object.entries(a.l3).sort((x, y) => y[1].krw - x[1].krw)) {
      h += `<div class="l3"><span>L3 ${esc(l3Disp(l3))}${share(l3)}</span><span>${won(b.krw)}</span></div>`;
      for (const [l4, c] of Object.entries(b.l4).sort((x, y) => y[1].krw - x[1].krw))
        h += `<div class="l4"><span>L4 ${esc(l4Disp(l4))}${c.qty ? ` × ${c.qty}` : ""} <span class="hint">${esc(c.grade || "")}</span></span><span>${c.krw ? won(c.krw) : "포함 · 0원"}</span></div>`;
    }
  }
  h += `</div><div class="hint">결제액 기준(VAT 포함). 식사 포함 혜택은 객실 상품에 들어 있어 0원으로 남습니다. 하루 전체 계산과 같이 돌린 손님이면 그 날 업장 매출에서 이 팀이 차지하는 몫이 붙습니다. ${GRADE_LEGEND.menu}.</div></div>`;
  return h;
}

// 후기 손님 재현 — 후기가 간 곳(정답 확인본) vs 모델 (같은 손님 K번 · 갈 확률)
function reviewCard(R) {
  const pc = x => Math.round((x || 0) * 100) + "%";
  const meter = x => `<span class="pmeter"><i style="width:${Math.round((x || 0) * 100)}%"></i></span>`;
  const rows = R.visited.slice().sort((a, b) => (b.p || 0) - (a.p || 0));
  const photos = LIB.photos || {};
  const thumb = loc => (photos[loc] || []).slice(0, 1).map(f => `<img class="thumb" src="/local-photo/${encodeURIComponent(f)}" alt="${esc(locName(loc))}">`).join("");
  let h = `<div class="card review"><h4>후기 행동 재현 평가 — ${esc(R.blog)}${R.alt ? " 둘째 체류" : ""} ${R.link ? `<a class="hint" href="${esc(R.link)}" target="_blank" rel="noopener">본문 열기 ↗</a>` : `<span class="hint">본문 링크 없음</span>`}</h4>
    <div class="tiles"><div class="tile" title="후기가 간 곳 중 모델도 간 곳의 비율"><small>후기 방문 중 모델도 감</small><span class="big">${pc(R.recall_k)}</span><br><span class="hint">${R.k}번 평균 · 이번 동선 ${R.n_hit}/${R.n_scorable}</span></div>
    <div class="tile" title="모델이 간 곳 중 후기에도 있는 곳의 비율"><small>모델 방문 중 후기에도 있음</small><span class="big">${pc(R.precision_k)}</span><br><span class="hint">식당 ${esc(R.restaurants)}${R.meals != null ? " · 식사 " + pc(R.meals) : ""}</span></div></div>
    <table class="t"><tr><th>후기가 간 곳</th><th class="n">모델이 갈 확률</th><th>후기 근거</th></tr>` +
    rows.map(t => `<tr><td>${thumb(t.loc)}${esc(t.name)}${t.hit ? ' <span class="okmark">이번 동선 ✓</span>' : ""}</td><td class="n">${t.scorable ? meter(t.p) + " " + pc(t.p) : '<span class="hint">모델 행동 목록에 없음</span>'}</td><td class="hint">${esc(t.why)}</td></tr>`).join("") +
    `</table>`;
  if (R.extra.length) h += `<details><summary>모델만 간 곳 ${R.extra.length}곳 (후기엔 없음)</summary><table class="t">${R.extra.map(t => `<tr><td>${esc(t.name)}</td><td class="n">${pc(t.p)}</td><td class="hint">${esc(t.why)}</td></tr>`).join("")}</table></details>`;
  const F = R.facts || {};
  if (Object.keys(F).length) h += `<details><summary>이 손님 설정의 근거 (후기에서 뽑은 사실)</summary><dl class="kv">${Object.entries(F).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></details>`;
  h += `<div class="hint">지도의 고리 = 후기가 간 곳 (초록 = 모델도 감 · 주황 = 모델은 안 감). 갈 확률은 하루 시뮬레이션과 같은 v4 계수(확률 선택)로 같은 손님을 ${R.k}번 돌린 비율이고, 46편 대조표의 재현 · 정밀(76% · 46%)은 계수 기본값(항상 1등 선택)으로 잰 값이라 숫자가 다를 수 있습니다. 좌석 경쟁 없이 돌립니다.</div></div>`;
  return h;
}

// ---------------------------------------------------------------------------
// 오른쪽 — 행동 하나의 근거
// ---------------------------------------------------------------------------
function whyBars(list) {
  const items = list.map(w => { const m = String(w).match(/^(.*?)\s([+-]\d+(?:\.\d+)?)$/); return m ? [m[1], +m[2]] : [w, 0]; });
  const mx = Math.max(1, ...items.map(x => Math.abs(x[1])));
  return `<div class="why">${items.map(([k, v]) => `<div class="r"><span>${esc(k)}</span><span><span class="b" style="display:block;width:${Math.abs(v) / mx * 100}%;background:${v >= 0 ? "var(--pos)" : "var(--neg)"};margin-left:${v >= 0 ? 0 : "auto"}"></span></span><span class="v" style="color:${v >= 0 ? "var(--pos)" : "var(--neg)"}">${v >= 0 ? "+" : ""}${v.toFixed(2)}</span></div>`).join("")}</div>`;
}

// 가설 운영 표시 → 색 (hypotheses.csv '운영 표시' 열 · 10/14)
const HSTATE_CLS = { "모델 기본값 반영": "on", "영향 미미": "minor", "외부 근거 보강 필요": "ext", "현장 확인 필요": "site" };
// 10/14 설명을 정직하게 — 점수에 실제로 작용한 요인과, 후기에서 뽑았지만 지금 점수에 안 들어가는 성향을 나눠 보여 준다
const FACTOR_GROUP = [[/^대기/, "대기 시간"], [/^이동/, "이동 거리"], [/예약 포함/, "패키지 포함 식사"], [/호텔 조식 두고|때 · 식당 밖|^(조식|중식|석식|야식) 때$/, "식사 시간"],
  [/예약한 곳/, "예약"], [/가고 싶던 곳/, "가고 싶은 식당 (목적별 선호)"], [/아동 동반/, "아이 동반"], [/객실에서 쉼|직전에도 객실|객실 체류/, "객실에서 쉬기"],
  [/줄 대신 포장/, "줄 대신 포장 (성향 '대기 회피')"], [/포장 기본/, "포장 감점"], [/체크인|입실|취침/, "정해진 일정 (체크인 · 취침)"],
  [/구매 계획|한잔 계획|바 계획/, "구매 · 한잔 계획 (목적별 비율)"], [/평일 저녁/, "평일 저녁 계획"], [/함께 먹기|격식|캐주얼|조망|조용함|붐빔|이미 가 봄|처음|대기\(성향\)/, "성향 (후기 추출)"]];
function factorOf(reason) { for (const [re, g] of FACTOR_GROUP) if (re.test(reason)) return g; return reason; }
function parseWhy(w) { const m = String(w).match(/^(.*?)\s([+-]\d+(?:\.\d+)?)$/); return m ? [m[1], +m[2]] : [String(w), 0]; }
// 고른 행동들의 점수 사유를 요인별로 더한다 → [[요인, 점수 합, 횟수]] (절댓값 큰 순)
function factorSummary(steps) {
  const acc = {};
  for (const s of steps || []) for (const w of s.why || []) {
    const [r, v] = parseWhy(w); if (!v) continue;
    const g = factorOf(r); acc[g] = acc[g] || [0, 0]; acc[g][0] += v; acc[g][1] += 1;
  }
  return Object.entries(acc).map(([g, [v, n]]) => [g, v, n]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
}
// 성향 7개의 상태 — 후기에 근거 없음 / 추출됨 · 지금 반영 안 됨 / 일부 반영 / 반영
function traitRows(persona) {
  const TM = (LIB && LIB.trait_model) || {}, lam = TM.lam_trait, on = TM.always_on || {};
  const tr = (persona && persona.traits) || {};
  return (TM.traits || Object.keys(tr)).map(k => {
    const v = tr[k];
    const st = v == null ? ["none", "후기에 근거 없음"] : lam > 0 ? ["on", `반영 (강도 ${lam})`] : on[k] ? ["part", `일부만 반영 — ${on[k]}`] : ["off", "추출됐지만 지금 점수에 안 들어감"];
    return { k, v, cls: st[0], st: st[1] };
  });
}
function traitNote() {
  const lam = ((LIB && LIB.trait_model) || {}).lam_trait;
  return lam > 0 ? `성향은 강도 ${lam}로 점수에 들어갑니다.` :
    `후기에서 뽑은 성향 7개는 '대기 회피'가 포장을 고를 때 쓰이는 것 말고는 지금 모델의 점수에 들어가지 않습니다. 후기 46편 교차검증에서 성향 강도(lam_trait)가 모든 폴드에서 0으로 골라졌기 때문입니다. 즉 성향을 넣으면 맞추지 않은 후기의 동선 재현이 오히려 나빠졌습니다. 성향을 하나씩 켜 보는 실험(성향 빼기 · 넣기)은 선택 사항으로 남겨 두었습니다. 강도가 0이라 지금은 '대기 회피' 하나만 결과를 바꿀 수 있습니다. 하루 전체 손님(고객 유형표)은 성향 값이 아예 없고 목적 · 인원 · 아이 동반 · 객실 상품 · 목적별 가고 싶은 식당만 받습니다.`;
}
function factorTable(steps) {
  const F = factorSummary(steps).filter(x => !/정해진 일정/.test(x[0])); if (!F.length) return "";
  const mx = Math.max(1, ...F.map(x => Math.abs(x[1])));
  return `<table class="t rt"><tr><th>요인</th><th></th><th class="n">점수 합</th><th class="n">횟수</th></tr>${F.slice(0, 10).map(([g, v, n]) => `<tr><td>${esc(g)}</td><td style="width:35%"><span style="display:block;height:7px;border-radius:3px;width:${Math.abs(v) / mx * 100}%;background:${v >= 0 ? "var(--pos)" : "var(--neg)"}"></span></td><td class="n">${v > 0 ? "+" : ""}${v.toFixed(1)}</td><td class="n">${n}</td></tr>`).join("")}</table><div class="hint">체크인 · 취침처럼 시간이 되면 정해지는 행동의 점수는 뺐습니다.</div>`;
}
function traitTable(persona) {
  const R = traitRows(persona);
  if (R.every(r => r.v == null)) return `<div class="hint">이 손님은 성향 값이 없습니다. 하루 전체 손님과 같은 방식(목적 · 인원 · 아이 동반 · 객실 상품 · 목적별 가고 싶은 식당)으로 만든 손님입니다. 성향은 '고객 흐름 › 손님 한 팀' 에서 후기 손님을 그대로 돌리면 볼 수 있습니다.</div>`;
  return `<table class="t rt"><tr><th>성향 (후기에서 추출)</th><th class="n">값</th><th>지금 모델에서</th></tr>${R.map(r => `<tr><td>${esc(r.k)}</td><td class="n">${r.v == null ? "-" : (+r.v).toFixed(2)}</td><td><span class="tstate ${r.cls}">${esc(r.st)}</span></td></tr>`).join("")}</table>`;
}

function rejectGroups(list) {
  const g = {};
  for (const r of list) {
    const [name, ...rest] = String(r).split(": ");
    let why = rest.join(": ") || r;
    why = why.replace(/시작이 \d+분 뒤/, "다음 운영 시간이 너무 멂").replace(/만석 \(자리 \d+분 뒤\)/, "만석 (자리 나는 데 너무 오래)");
    (g[why] = g[why] || []).push(name);
  }
  return Object.entries(g).sort((a, b) => b[1].length - a[1].length);
}

const REASON_HELP = {
  "다음 운영 시간이 너무 멂": "지금부터 3시간 안에 시작할 수 없는 곳",
  "남은 운영 창 없음": "오늘 운영 시간이 끝났거나 이 날 닫는 곳",
  "만석": "그 날 다른 손님이 좌석을 다 잡아 운영 시간 안에 자리가 안 남",
  "동반 아동 제한": "아이 동반 불가 업장",
  "종료 시각 넘김": "체크아웃 · 떠나는 시각 전에 못 끝냄",
};

function chainFor(s) {
  const C = LIB.chain || [];
  const out = [];
  const by = id => C.find(c => c["근거ID"] === id);
  if (s.key === "geum" && by("EC01")) out.push(by("EC01"));
  if ((["pizza_to", "lepassage"].includes(s.key) || (s.switch && s.switch["원래"])) && by("EC02")) out.push(by("EC02"));
  if (s.switch && /더뷔페/.test(s.switch["원래"] || "") && by("EC03")) out.push(by("EC03"));
  if (["winefair", "fair_food"].includes(s.key) && by("EC04")) out.push(by("EC04"));
  if (["pizza_to", "lepassage"].includes(s.key) && G.persona.age === "20~29세" && by("EC05")) out.push(by("EC05"));
  return [...new Set(out)];
}

// ---------------------------------------------------------------------------
// 5단계 (10/15 v1.32) 근거 고리 — 근거 → 적용 계수 → 후보 점수 · 확률 → 선택 → 운영 결과를 한 카드에
// 계수 값은 손님 기록의 점수 사유에서 거꾸로 읽는다 (대기 12분 −0.45 → 30분당 1.12). 화면이 따로 계수표를 들고 있지 않아 모델과 어긋날 일이 없다
// ---------------------------------------------------------------------------
const COEF = [
  // [사유 패턴, 계수 이름, 화면 이름, 양을 읽는 법, 계수 출처, 입력 근거(입력 출처표 '입력' 열)]
  [/^대기 (\d+)분$/, "w_wait", "대기 비용", m => +m[1] / 30, "30분당", "후기 46편 교차검증", "행동 점수 계수"],
  [/^이동 (\d+)분$/, "w_travel", "이동 비용", m => +m[1] / 20, "20분당", "후기 46편 교차검증 · 이동 시간은 구내 이동 매트릭스", "행동 점수 계수"],
  [/예약 포함$/, "included", "패키지에 포함된 식사", null, "", "후기 46편 교차검증 · 포함 여부는 그 날 객실 상품표", "행동 점수 계수"],
  [/때 · 식당 밖$/, "meal + meal_other", "식사 시간대 · 식당 밖 식사", null, "", "식사 6.0 고정 + 교차검증 가감", "행동 점수 계수"],
  [/^(조식|중식|석식|야식) 때$/, "meal", "식사 시간대 · 식당 식사", null, "", "기준값 6.0 (교차검증에서 고정)", "행동 점수 계수"],
  [/호텔 조식 두고 방에서/, "bfast_room", "투숙객이 조식을 방에서", null, "", "후기 46편 교차검증", "행동 점수 계수"],
  [/^객실에서 쉼$/, "room_rest", "객실에서 쉬기", null, "", "후기 46편 교차검증", "행동 점수 계수"],
  [/직전에도 객실|객실 체류 최소형/, "규칙", "객실 연속 체류 감점", null, "", "고정 규칙", null],
  [/아동 동반/, "kids", "아이 동반", null, "", "후기 46편 교차검증", "행동 점수 계수"],
  [/^예약한 곳$/, "booked", "미리 예약한 곳", null, "", "후기 46편 교차검증 · 예약은 후기에 적힌 것만", "행동 점수 계수"],
  [/^가고 싶던 곳$/, "prefer", "가고 싶은 식당", null, "", "기본값 3.0 (예약보다 약하게) · 어느 식당인지는 목적별 선호표", "가고 싶은 식당"],
  [/줄 대신 포장/, "takeout × 대기 회피", "줄 대신 포장", null, "", "교차검증 계수 × 후기에서 뽑은 성향 '대기 회피'", "행동 점수 계수"],
  [/포장 기본 감점/, "takeout_base", "포장 감점 (조정값)", null, "", "실험용 조정값", null],
  [/르파사쥬 구매 계획/, "passage_rate", "르 파사쥬 독립 구매 계획", null, "", "목적별 비율 × 조정값 (온톨로지 포장 비중)", "르 파사쥬 독립 구매"],
  [/한잔 계획|바 계획/, "bar_nightcap", "저녁 뒤 한잔 계획", null, "", "목적별 비율 × 조정값", "럭스바 저녁 뒤 한잔"],
  [/평일 저녁 호텔 식당 계획 없음/, "wd_dine", "평일 저녁 계획 (가설 H4a)", null, "", "가설 조정값", null],
  [/포함 저녁 두고 다른 저녁/, "incl_block", "포함 저녁이 남았는데 다른 저녁", null, "", "규칙 (99 = 사실상 금지)", null],
  [/체크인 절차|밤이라 취침/, "규칙", "정해진 일정", null, "", "체크인 · 취침은 점수 비교 없이 순서대로", null],
  [/입실 절차/, "규칙", "첫 입실 (짐 풀기)", null, "", "키를 받은 뒤 처음 객실에 가는 건 절차", null],
  [/포장 음식 객실에서/, "규칙", "포장해 온 음식 먹기", null, "", "포장한 음식은 객실에서 먹는다 (식사는 포장할 때 셈)", null],
  [/빈 시간 채우기/, "규칙", "빈 시간 채우기", null, "", "다음 일정 전 빈 시간에 할 수 있는 활동을 먼저", null],
];
function coefRow(w) {
  const [r, v] = parseWhy(w);
  for (const [re, name, nm, qty, unit, src, prov] of COEF) {
    const m = r.match(re);
    if (!m) continue;
    const q = qty ? qty(m) : null;
    const c = q ? Math.abs(v) / q : Math.abs(v);
    return { r, v, name, nm, coef: name === "규칙" ? null : c, unit, q, src, prov };
  }
  return { r, v, name: /격식|캐주얼|조망|조용함|붐빔|함께 먹기|이미 가 봄|처음|성향/.test(r) ? "lam_trait" : "?", nm: r, coef: null, src: "성향 강도 lam_trait 0 이라 지금은 점수에 안 들어감", prov: null };
}
function stepProbs(s) {
  // 같은 턴 후보 (기록은 상위 여섯) 의 선택 확률 — v4 는 exp((점수 − 1등 점수) / τ) 에 비례해 고른다
  const al = (s.alts || []).slice();
  if (!al.some(a => a.key === s.key)) al.push({ label: s.label, key: s.key, pts: s.pts, t: s.t_in });
  const top = Math.max(...al.map(a => a.pts));
  const tau = s.tau || 0;
  const ws = al.map(a => tau > 0 ? Math.exp((a.pts - top) / tau) : (a.pts === top ? 1 : 0));
  const sum = ws.reduce((a, b) => a + b, 0) || 1;
  return { rows: al.map((a, i) => ({ ...a, p: ws[i] / sum })).sort((a, b) => b.pts - a.pts), approx: (s.feasible || 0) > al.length, tau };
}
function chainCard(s) {
  const P = G.persona;
  const fixed = s.kind === "checkin" || (s.why || []).some(w => /체크인 절차|밤이라 취침|입실 절차|포장 음식 객실에서/.test(w));
  const rows = (s.why || []).map(coefRow).filter(x => x.v || x.name === "규칙");
  const prov = new Map((LIB.provenance || []).map(r => [r["입력"], r]));
  // ① 근거 — 이 손님 설정이 어디서 왔나 + 이 선택에 걸린 입력의 출처 등급 + 근거 사슬
  const who = G.review ? `블로그 후기 손님 (${esc(G.review.blog || "")} · 후기에서 뽑은 설정)` : P.is_guest ? `고객 유형표 한 줄 · 목적 '${esc(P.purpose)}' · 객실 상품 '${esc(P.package || "-")}'` : `비투숙 손님 · 목적 '${esc(P.purpose)}'`;
  const used = [...new Set(rows.map(x => x.prov).filter(Boolean))];
  if (P.prefers && P.prefers.length && rows.some(x => x.name === "prefer")) used.push("식당 가고 싶음 비율");
  const provChips = used.map(n => prov.get(n)).filter(Boolean).map(r => `<span class="tag" title="${esc(r["출처"] || "")} · ${esc(r["표본 · 근거"] || "")}">${esc(r["등급"])} ${esc(r["입력"])}</span>`).join("");
  const ec = chainFor(s).map(c => `<span class="tag ec" title="${esc(c["예측문장"])}">${esc(c["근거ID"])} ${esc(String(c["예측문장"]).slice(0, 26))}…</span>`).join("");
  const rv = G.review && (G.review.visited || []).find(v => v.loc === s.location);
  const revLine = rv ? `<div class="hint" style="color:var(--ink2)">후기에도 간 곳 · ${esc(rv.grade)} ${esc(String(rv.why).replace(/^[◎○△]\s*/, "").slice(0, 90))}</div>` : "";
  let h = `<div class="card chain"><h4>이 선택의 근거 고리</h4><ol class="chainol">`;
  h += `<li><b>근거</b><div>${who}</div>${revLine}${provChips || ec ? `<div class="chips">${provChips}${ec}</div><div class="hint">${GRADE_LEGEND.prov} · EC 는 근거 사슬. 칩에 마우스를 올리면 출처</div>` : ""}</li>`;
  // ② 적용 계수
  if (fixed) h += `<li><b>적용 규칙</b><div>${esc(rows[0] ? rows[0].src : "정해진 절차")}</div></li>`;
  else h += `<li><b>적용 계수</b><table class="t coef"><tr><th>요인</th><th>계수</th><th class="n">점수</th></tr>${rows.map(x =>
    `<tr><td>${esc(x.nm)}${x.q ? ` <span class="hint">${esc(x.r.replace(/^(대기|이동) /, ""))}</span>` : ""}<div class="hint">${esc(x.src)}</div></td><td>${x.coef != null ? `${x.coef.toFixed(2)}${x.unit ? " / " + x.unit : ""}` : x.name === "규칙" ? "규칙" : "-"}<span class="dev"> <code>${esc(x.name)}</code></span></td><td class="n" style="color:${x.v >= 0 ? "var(--pos)" : "var(--neg)"}">${x.v >= 0 ? "+" : ""}${x.v.toFixed(2)}</td></tr>`).join("")}
    <tr class="sum"><td colspan="2">합계 (이 후보의 점수)</td><td class="n">${s.pts >= 0 ? "+" : ""}${(+s.pts).toFixed(2)}</td></tr></table>${s.wait > 0 && !rows.some(x => x.name === "w_wait") ? `<div class="hint">기다림 ${Math.round(s.wait)}분에는 대기 비용이 붙지 않았습니다. 객실에서 다음 창을 기다리는 시간과 예약 뒤 다음 회차 시작까지의 시간은 줄로 세지 않는 규칙 때문입니다.</div>` : ""}</li>`;
  // ③ 후보 점수 · 확률
  if (!fixed && (s.alts || []).length > 1) {
    const pr = stepProbs(s);
    h += `<li><b>후보 점수 · 선택 확률</b> <span class="hint">이 시각 갈 수 있는 후보 ${s.feasible}개${pr.approx ? " 중 점수 상위 " + pr.rows.length + "개" : ""} · τ ${pr.tau}</span>` +
      `<div class="probs">${pr.rows.map(a => `<div class="pr ${a.key === s.key ? "me" : ""}"><span class="nm">${esc(a.label)}</span><span class="bar"><i style="width:${Math.max(1, a.p * 100)}%"></i></span><span class="v">${Math.round(a.p * 100)}%</span><span class="pts">${a.pts >= 0 ? "+" : ""}${(+a.pts).toFixed(2)}</span></div>`).join("")}</div>` +
      `<div class="hint">확률 = exp((점수 − 1등 점수) ÷ τ) 의 비율. 점수 차가 τ(${pr.tau}) 보다 크게 벌어지면 거의 1등을 고릅니다${pr.approx ? ". 기록에 남은 상위 후보로 계산해 실제 확률은 이보다 조금 낮을 수 있습니다" : ""}.</div></li>`;
  }
  // ④ 선택
  const pr = !fixed && (s.alts || []).length > 1 ? stepProbs(s).rows.find(a => a.key === s.key) : null;
  h += `<li><b>선택</b><div>${esc(nmDisp(s.label))} · ${hhmm(s.a)}${fixed ? " · 정해진 절차" : ` · 점수 ${s.rank}등${pr ? ` · 확률 ${Math.round(pr.p * 100)}%` : ""}`}</div>` +
    (s.switch && s.switch["원래"] ? `<div class="hint" style="color:var(--neg)">원래 1순위 ${esc(nmDisp(s.switch["원래"]))} (점수 ${s.switch["원래_점수"]}) 는 ${esc(s.switch["사유"])}로 후보에서 빠짐</div>` : "") + `</li>`;
  // ⑤ 운영 결과
  const amt = (s.spend || []).reduce((a, b) => a + b.krw, 0);
  const D = G._crowd ? DAYCACHE[G._crowd] : null;
  let seat = "";
  if (D && D.seats[s.location]) {
    const k = Math.floor((s.a - tmin(D.slot0)) / 10);
    if (k >= 0 && k < D.slots.length) { const ld = D.seats[s.location].load[k], cap = D.seats[s.location].cap; seat = `그 시각 ${esc(locName(s.location))} 좌석 ${ld}/${cap} (${Math.round(ld / cap * 100)}%) · 이 팀 ${P.party}명 포함`; }
  }
  const vd = D && D.venue_detail && D.venue_detail[s.location];
  const incl = rows.some(x => x.name === "included");
  const res = [amt ? `지출 ${won(amt)} → ${esc((s.spend[0] || {}).l3 || "")} 매출 (L4 ${s.spend.length}줄)` : incl ? "따로 결제 없음 · 객실 상품 값에 들어 있는 식사" : "지출 없음", seat, vd ? `그 날 ${esc(locName(s.location))} 하루 이용 ${((vd.persons_day || 0) + (vd.takeout_day || 0)).toLocaleString()}명 중 하나` : ""].filter(Boolean);
  h += `<li><b>운영 결과</b><div>${res.join("<br>")}</div>${s.switch && s.switch["원래"] ? `<div id="chainFinal" class="hint">이용이 제한된 식사가 결국 어디서 해결됐는지 찾는 중…</div>` : ""}</li></ol>`;
  if (!fixed) h += `<div class="hint">계수는 점수 사유에서 읽은 값입니다. 성향 7개는 지금 강도 0이라 이 고리에 나오지 않습니다 (판단 근거 화면 ④).</div>`;
  h += `</div>`;
  return h;
}
async function fillChainFinal(s) {
  const el = $("#chainFinal");
  if (!el || !G._crowd || G._idx == null) { if (el) el.remove(); return; }
  try {
    const F = await flowOf(G._crowd);
    const ev = (F.events || []).find(e => e.idx === G._idx && e.from === s.switch["원래"] && Math.abs(tmin(e.t) - tmin(s.switch["시각"] || s.t_in)) < 1);
    if (!$("#chainFinal")) return;
    if (ev && ev.final) $("#chainFinal").innerHTML = `이용이 제한된 ${esc(ev.meal || "식사")}의 최종 선택: <b>${esc(outName(ev.final))}</b>${ev.final_at && !String(ev.final).startsWith(ev.final_at) ? ` (${esc(ev.final_at)})` : ""}${ev.included ? " · 패키지에 포함된 식사였음" : ""} · 고객 이동 정산 기록`;
    else $("#chainFinal").textContent = "식사가 아닌 행동이라 정산 대상이 아닙니다 (바 · 라운지 한잔 등).";
  } catch (e) { el.remove(); }
}

function placeCards(loc, venue, atMin) {
  let h = "";
  const win = (LIB.windows[venue] || []).concat(venue !== loc ? (LIB.windows[loc] || []) : []);
  const seat = LIB.seats[loc];
  let load = "";
  const D = G && G._crowd ? DAYCACHE[G._crowd] : (MODE === "day" ? DAY : null);
  if (seat && D && D.seats[loc] && atMin != null) {
    const k = Math.floor((atMin - tmin(D.slot0)) / 10);
    if (k >= 0 && k < D.slots.length) load = ` · 그 시각 다른 손님 ${D.seats[loc].load[k]}명 / ${D.seats[loc].cap}석`;
  }
  if (win.length || seat) {
    h += `<div class="card"><h4>${esc(locName(loc))} — 운영 · 좌석</h4>`;
    if (win.length) h += `<div style="font-size:12px;line-height:1.6">${win.slice(0, 6).map(w => esc(w)).join("<br>")}${win.length > 6 ? `<br><span class="hint">외 ${win.length - 6}개 창</span>` : ""}</div>`;
    if (seat) h += `<div style="margin-top:6px;font-size:12px"><span class="g ${gradeCls(seat.grade)}">${esc(seat.grade)}</span> 좌석 ${seat.n}석 · ${esc(seat.src)}${load}</div>`;
    h += `<div class="hint" style="margin-top:4px">${GRADE_LEGEND.place}</div></div>`;
  }
  const asm = LIB.assumptions[loc] || [];
  if (asm.length) {
    h += `<div class="card"><h4>가정표 (${asm.length}줄)</h4><table class="t">${asm.slice(0, 8).map(a => `<tr><td><span class="g ${gradeCls(a["등급"])}">${esc(a["등급"])}</span> ${esc(a["항목"])}</td><td>${esc(a["값"])}${esc(a["단위"] ? " " + a["단위"] : "")}${a["조건"] ? `<br><span class="hint">${esc(a["조건"]).slice(0, 80)}</span>` : ""}</td></tr>`).join("")}</table>
      ${asm.length > 8 ? `<details><summary>나머지 ${asm.length - 8}줄</summary><table class="t">${asm.slice(8).map(a => `<tr><td><span class="g ${gradeCls(a["등급"])}">${esc(a["등급"])}</span> ${esc(a["항목"])}</td><td>${esc(a["값"])} ${esc(a["단위"])}</td></tr>`).join("")}</table></details>` : ""}</div>`;
  }
  const rv = LIB.reviews[loc] || [];
  h += `<div class="card"><h4>후기 근거 — ${rv.length ? `${rv.length}편에 이 장소가 나옴` : "후기에 이 장소가 없음"}</h4>` +
    rv.slice(0, 4).map(r => `<div class="quote"><b>${esc(r.blog)}</b> ${esc(r.why)}</div>`).join("") +
    (rv.length > 4 ? `<details><summary>나머지 ${rv.length - 4}편</summary>${rv.slice(4).map(r => `<div class="quote"><b>${esc(r.blog)}</b> ${esc(r.why)}</div>`).join("")}</details>` : "") +
    `<div class="hint">페르소나 파일의 정답(TRUTH_VISITED) 판단 문장 — 본문이 아니라 정답 확인 때 적은 근거입니다.</div></div>`;
  return h;
}

function renderStep(s) {
  const loc = s.location, venue = s.venue || loc;
  const amt = s.spend.reduce((a, b) => a + b.krw, 0);
  let h = evReturnBar() + `<div class="rx-stepbar"><button class="back">← 하루 요약으로</button><button class="rv-btn rx-ev" id="btnStepEv" title="이 행동의 선택지 · 점수 항 · 후기 확인 · 왜 알 수 없는가를 판단 근거에서 봅니다">이 행동의 판단 근거 ›</button></div>`;
  // 17차 마무리 · 이 화면은 모델의 점수 · 규칙 계산이다. 실제 손님의 이유(후기 원문 근거)나 역추적 가설과 섞이지 않게 맨 위에서 밝힌다
  h += `<div class="step-src"><b>모델 선택 근거</b><span>점수 · 규칙으로 계산한 값 · 실제 손님의 이유가 아님</span>${noteI("이 화면의 사유와 점수는 모델(v4)이 후보를 고를 때 쓴 점수 · 규칙입니다. 후기 원문에 적힌 손님의 이유(원문 근거)나, 행동에서 이유를 거꾸로 추정한 역추적 가설과는 다른 층이며 검증 수준도 다릅니다. 원문 근거 · 역추적 가설 · 검증 수준은 판단 근거 탭에서 구분해 봅니다.")}</div>`;
  const im = placeImg(venue) || placeImg(loc);
  if (im) h += `<button class="gn-img st-img" id="stepImg" title="${esc(im.name)} 크게 보기"><img src="${im.src}" alt="${esc(im.name)}"><span class="gn-time">${dlabel(s.a)} <b>${hhmm(s.a)}</b></span><span class="gn-credit">${esc(im.credit)}</span></button>`;
  h += `<div class="card"><span class="chip" style="background:${KCOL[s.kind]}">${KNAME[s.kind]}</span>
    <h4 style="margin-top:6px;font-size:16px">${esc(altName(s.label))}</h4>
    <dl class="kv"><dt>시각</dt><dd>${dlabel(s.a)} ${hhmm(s.a)} – ${hhmm(s.b)} (${Math.round(s.b - s.a)}분)</dd>
    <dt>장소</dt><dd>${esc(locName(loc))}</dd>
    <dt>오기까지</dt><dd>이동 ${s.travel ?? "-"}분 · 모델 대기값 ${s.wait ?? 0}분${s.wait ? noteI("도착(이동 계산)부터 이 행동을 시작할 수 있을 때(개점 · 회차 · 착석)까지의 분입니다. 모델은 이 값을 점수 계산에만 쓰고, 그 시간의 위치 · 행동은 기록하지 않습니다.") : ""}</dd>
    <dt>지출</dt><dd>${amt ? won(amt) : "0원"}</dd></dl></div>`;
  if (s.switch && s.switch["원래"]) {
    h += `<div class="callout"><b>원래는 ${esc(nmDisp(s.switch["원래"]))}</b>에 가려 했습니다 (점수 ${s.switch["원래_점수"]}). ${esc(s.switch["사유"])}이라 후보에서 빠져 <b>${esc(altName(s.switch["대체"]))}</b>(${s.switch["대체_점수"]})를 골랐습니다.</div>`;
  }
  const n = s.alts.length;
  h += chainCard(s);
  if (n > 1 && s.kind !== "checkin") {
    h += `<div class="card"><h4>후보별 점수 사유 (자세히)</h4><table class="t"><tr><th>후보</th><th>시작</th><th class="n">점수</th></tr>` +
      s.alts.map(a => `<tr class="${a.key === s.key ? "me" : ""}"><td>${esc(a.label)}<details><summary>이유</summary>${whyBars(a.why)}<div class="hint">이동 ${a.travel}분 · 모델 대기값 ${a.wait}분 <span class="hint">(시작 가능 시각까지 · 업장 앞 줄 아님)</span></div></details></td><td>${hhmm(tmin(a.t))}</td><td class="n">${a.pts >= 0 ? "+" : ""}${a.pts}</td></tr>`).join("") + `</table></div>`;
  }
  const groups = rejectGroups(s.rejected);
  if (groups.length) {
    h += `<div class="card"><h4>후보에서 빠진 것 (${s.rejected.length})</h4>` + groups.map(([why, names]) =>
      `<div style="font-size:12px;margin:4px 0"><b>${esc(why)}</b>${REASON_HELP[why] ? ` <span class="hint">— ${REASON_HELP[why]}</span>` : ""}<br>${names.map(x => `<span class="tag">${esc(x)}</span>`).join("")}</div>`).join("") + `</div>`;
  }
  if (s.spend.length) {
    h += `<div class="card"><h4>매출 줄</h4><table class="t"><tr><th>상품</th><th class="n">수량</th><th class="n">금액</th></tr>` +
      s.spend.map(x => `<tr><td><span class="g ${gradeCls(x.grade)}">${esc(x.grade)}</span> ${esc(x.product)}<br><span class="hint">${esc(x.l2)} · ${esc(x.l3)}${x.note ? " · " + esc(x.note) : ""}</span></td><td class="n">${x.qty}</td><td class="n">${won(x.krw)}</td></tr>`).join("") +
      `</table><div class="hint">메뉴판 정가 상품표에서 그 날 · 그 시각에 팔리는 상품 중 하나를 고른 것<span class="dev"> (menu.csv)</span></div></div>`;
  }
  for (const c of chainFor(s)) {
    h += `<div class="callout ${c["근거ID"] === "EC04" ? "wine" : "info"}"><b>근거 사슬 ${esc(c["근거ID"])}</b> — ${esc(c["예측문장"])}<br><span class="hint">확실성 ${esc(c["확실성"])} · 한계: ${esc(c["반대사례_한계"]).slice(0, 140)}</span></div>`;
  }
  if (s.kind !== "checkin") h += placeCards(loc, venue, s.a);
  $("#panel").innerHTML = h;
  $("#panel .back").onclick = () => { SEL = null; $$("#strip .blk").forEach(e => e.classList.remove("sel")); renderPanel(); };
  const bev = $("#btnStepEv"); if (bev) bev.onclick = () => evShowAction(G.st.indexOf(s));
  bindReturnBar();
  const si = $("#stepImg"); if (si) si.onclick = () => openPlaceImage(placeImg(venue) ? venue : loc);
  $("#panel").scrollTop = 0;
  if (s.switch && s.switch["원래"]) fillChainFinal(s);
}

// ---------------------------------------------------------------------------
// 10/15 P0-B 더뷔페 조식 준비량 계산 예시 — 회차별 예상 이용 인원 × 품목 선택률 × 1회 소비량 (가정 입력)
// 발주량이 아니다: 재고 · 입고 · 포장 단위가 없으면 발주량을 낼 수 없다. 선택률 · 소비량은 비워 두고 현장 값을 넣게 한다
// ---------------------------------------------------------------------------
const PREP_ITEMS = [
  { name: "달걀 요리 (오믈렛 등)", unit: "개", served: "○ 제공 확인 · 후기 1편 (2부 조식 오믈렛 주문)" },
  { name: "우유 (라떼 · 시리얼)", unit: "mL", served: "○ 제공 확인 · 후기 1편 (카페라떼 주문)" },
  { name: "빵", unit: "개", served: "△ 제공 여부 후기 근거 없음 · 확인 필요" },
];
const PREP = PREP_ITEMS.map(() => ({ lo: "", mid: "", hi: "", amt: "" }));
let PREP_W = null;
// 10/16 연박 집계(실험 · viewer/stay_day.py) — 그 날 머무는 손님 기준 조식 인원. 기본 하루 계산과 별도 파일(static/stay_day.json)
let STAYDAY = null;
async function stayLoad() { if (!STAYDAY) { try { STAYDAY = await api("/static/stay_day.json"); } catch (e) { STAYDAY = { runs: [] }; } } return STAYDAY; }
// 조식 날짜(date)의 연박 집계 — 지금 모델 버전 · 워밍업 2일 이상만. 회차별 평균 · 범위 · 무리별 평균
function stayBreakfast(date, D) {
  // 10/16 QA · 이 하루(D)가 연박 집계와 같은 조건(v4.1 기본 · 같은 모델 · 입력 버전)일 때만 — 다른 조건에 기본 연박 값을 붙이지 않는다
  if (typeof stayMatch !== "function" || !stayMatch(D)) return null;
  const R = ((STAYDAY || {}).runs || []).filter(r => r.date === date && r.warm >= 2 && r.model_ver === D.model_ver && r.input_ver === D.input_ver);
  if (!R.length) return null;
  const wins = [...new Set(R.flatMap(r => Object.keys(r.buffet_breakfast || {})))].filter(w => w !== "창 밖").sort();
  const sum = o => Object.values(o || {}).reduce((a, b) => a + b, 0);
  const rows = wins.map(w => {
    const tot = R.map(r => sum((r.buffet_breakfast || {})[w]));
    const grp = {};
    R.forEach(r => Object.entries((r.buffet_breakfast || {})[w] || {}).forEach(([g, n]) => grp[g] = (grp[g] || 0) + n / R.length));
    return { name: w, mean: Math.round(tot.reduce((a, b) => a + b, 0) / R.length), lo: Math.min(...tot), hi: Math.max(...tot), grp };
  });
  return { n: R.length, rows, cap: R[0].buffet_cap, peak: Math.max(...R.map(r => r.buffet_breakfast_peak || 0)), warm: R[0].warm,
           inhouse: Math.round(R.reduce((a, r) => a + (r.checks || {}).inhouse_rooms, 0) / R.length) };
}
function prepCard(v, D) {
  const bw = v.windows.filter(w => w.kind === "조식" && (w.persons || w.over_persons));
  if (!bw.length) return "";
  // A/B 카드를 열어 둔 날이면 B(좌석 늘림) 하루의 회차별 인원도 입력으로 다시 쓴다 (새 비교 엔진 없음)
  const DB = typeof AB_LAST !== "undefined" && AB_LAST && AB_LAST.date === D.date && AB_LAST.b && DAYCACHE[AB_LAST.b.compare_key];
  const bB = DB && ((DB.venue_detail || {}).THE_BUFFET || {}).windows;
  PREP_W = bw.map(w => ({ name: w.name.replace(" (익일)", ""), n: w.persons, adults: w.adults, kids: w.kids, over: w.over_persons,
    nB: bB ? ((bB.find(x => x.name === w.name) || {}).persons ?? null) : null }));
  const bfDate = (bw[0].t0 && String(bw[0].t0).match(/(\d+)\/(\d+)/)) ? D.date.slice(0, 5) + String(bw[0].t0).match(/(\d+)\/(\d+)/).slice(1).map(x => x.padStart(2, "0")).join("-") : null;
  const SB = bfDate ? stayBreakfast(bfDate, D) : null;
  if (SB) PREP_W.forEach(w => { const r = SB.rows.find(x => x.name === w.name); w.nS = r ? r.mean : null; });
  const peak = PREP_W.reduce((a, w) => (w.n > a.n ? w : a), PREP_W[0]);
  let h = `<div class="card prep"><h4>조식 준비량 계산 예시 <span class="hint">가정 입력 · 발주량 아님</span></h4>` +
    `<div class="callout warn">계산 방식 예시 · <b>실제 준비 인원이 아님</b>${noteI("아래 인원은 실제 워커힐 운영 실적이 아니라 시뮬레이션 손님의 착석 기록입니다. 체크인 날 하루만 계산해 그 날 머무는 전체 손님(연박 손님과 이월 객실)을 반영하지 않으므로 실제 준비 인원으로 해석할 수 없습니다.")}</div>`;
  h += `<table class="t tight"><tr><th>회차</th><th class="n">착석</th><th class="n">성인 · 아동</th>${bB ? `<th class="n">B ${DB.venue_detail.THE_BUFFET.cap}석</th>` : ""}<th class="n">막힘</th></tr>` +
    PREP_W.map(w => `<tr><td>${esc(w.name)}${w === peak ? ` <span class="hint">피크</span>` : ""}</td><td class="n"><b>${w.n}명</b></td><td class="n">${w.adults} · ${w.kids}</td>${bB ? `<td class="n">${w.nB ?? "-"}명</td>` : ""}<td class="n hint">${w.over ? w.over + "명" : ""}</td></tr>`).join("") +
    `</table>${capN("이 날 체크인 손님의 다음날 조식만", "착석은 시뮬레이션에서 앉은 인원(회전 포함)이고, 막힘(좌석 제약을 겪은 팀의 일행 수)은 더하지 않습니다. 이 날 체크인한 투숙객의 다음날 조식만 셉니다. 연박 손님과 이월 객실을 함께 다루지 않아(신규 체크인만 생성), 빠진 손님을 더한다고 실제 인원이 되는 구조가 아닙니다. 클럽 라운지 조식 · 객실 · 호텔 밖 아침은 더뷔페 준비량에 넣지 않습니다. 아동은 고객 유형표가 '아이 동반 여부'만 있어 팀당 1명으로 셉니다(△).")}`;
  if (SB) {
    const md = bfDate.slice(5).replace("-", "/");
    const gs = [...new Set(SB.rows.flatMap(r => Object.keys(r.grp)))].filter(g => g !== "비투숙");
    h += `<h5 style="margin-top:14px">${md} 아침 · 그 날 머무는 손님 기준 <span class="hint">연박 집계 · 실험 · 시드 ${SB.n}개</span></h5>` +
      `<table class="t tight"><tr><th>회차</th><th class="n">착석 평균</th>${gs.map(g => `<th class="n">${esc(g.replace("그 전날 체크인", "2일 전 입실").replace("전날 체크인", "전날 입실").replace("당일 체크인", "당일 입실"))}</th>`).join("")}</tr>` +
      SB.rows.map(r => `<tr><td>${esc(r.name)}</td><td class="n"><b>${r.mean}명</b><div class="hint">${r.lo} ~ ${r.hi}</div></td>${gs.map(g => `<td class="n">${Math.round(r.grp[g] || 0)}</td>`).join("")}</tr>`).join("") + `</table>` +
      capN(`그 날 머무는 손님 기준 · 실험 · 앞 ${SB.warm}일 이어 생성`, `앞 ${SB.warm}일을 이어 생성해 연박 손님(이월 객실)을 넣고, 여러 날에 걸친 손님이 같은 좌석표를 함께 쓴 결과입니다. 위 표(체크인 날 기준)는 '전날 입실' 무리만 세던 범위입니다. 그 날 밤 투숙 객실 평균 ${SB.inhouse}실 · 좌석 ${SB.cap}석 · 아침 동시 점유 최고 ${SB.peak}명. 워밍업 첫날 이월은 0으로 시작하므로 실제 호텔 장부를 복원한 값은 아닙니다. 또 모델은 식음 행동을 체류 중 한 번만 고르므로 2박 손님의 두 번째 아침 더뷔페 조식이 생기지 않아, 체크아웃 날 아침 인원이 적게 나올 수 있습니다(모델 규칙의 한계 · 근거사슬 7-27).`);
  }
  h += `<div class="prepf">품목별 회차 소비량 = 착석 인원 × 품목 선택률 × 선택한 사람의 1회 평균 소비량</div>`;
  h += `<table class="t prept"><tr><th>품목</th><th>선택률 (0~1)</th><th>1회량</th></tr>` +
    PREP_ITEMS.map((it, i) => `<tr><td>${esc(it.name)}<div class="hint">${esc(it.served)}</div></td>` +
      `<td>${["lo", "mid", "hi"].map(k => `<input class="prepin" data-i="${i}" data-k="${k}" type="number" min="0" max="1" step="0.05" placeholder="${k === "lo" ? "낮음" : k === "mid" ? "기준" : "높음"}" value="${PREP[i][k]}">`).join("")}</td>` +
      `<td><input class="prepin" data-i="${i}" data-k="amt" type="number" min="0" step="0.5" placeholder="${esc(it.unit)}" value="${PREP[i].amt}"> <span class="hint">${esc(it.unit)}</span></td></tr>`).join("") + `</table>`;
  h += `<div id="prepOut"></div>`;
  h += `<details class="idet"><summary>가장 민감한 입력 · 현장에 요청할 자료</summary><div class="hint" style="line-height:1.7">식이 곱셈이라 선택률과 1회 소비량은 같은 비율로 결과를 바꿉니다. 지금 가장 흔들리는 입력은 <b>인원 자체</b>입니다: 그 날 머무는 전체 손님(연박 · 이월 객실)이 반영되지 않았고, 2부(08:30) 쏠림에는 30분 단위 기상 시각 가정(△)의 영향이 큽니다. 필요한 자료(우선순위 순): ① 회차별 실제 입장 인원과 그 날 투숙 중인 조식 포함 객실 수 ② 메뉴별 선택률 · 1인 소비량(주방 생산 기록, 내부 자료라 공개가 어려울 수 있음) ③ 재고 · 입고 · 폐기 ④ 품목별 발주 단위. ③ · ④가 있어야 '발주량'을 말할 수 있습니다.</div></details></div>`;
  setTimeout(() => {
    $$("#panel .prep input.prepin").forEach(e => e.oninput = () => { PREP[+e.dataset.i][e.dataset.k] = e.value; prepCalc(); });
    prepCalc();
  }, 0);
  return h;
}
function prepCalc() {
  const el = $("#prepOut");
  if (!el || !PREP_W) return;
  const num = x => (x === "" || x == null || isNaN(+x)) ? null : +x;
  const hasB = PREP_W.some(w => w.nB != null);
  const hasS = PREP_W.some(w => w.nS != null);
  const cols = PREP_W.length + 1;
  const errs = [];
  const rows = PREP_ITEMS.map((it, i) => {
    const p = PREP[i], a = num(p.amt), r = { lo: num(p.lo), mid: num(p.mid), hi: num(p.hi) };
    // 10/16 입력 검증 — 선택률 0~1, 소비량 0 이상, 낮음 ≤ 기준 ≤ 높음. 어긋나면 계산하지 않는다
    const bad = [];
    for (const k of ["lo", "mid", "hi"]) if (r[k] != null && (r[k] < 0 || r[k] > 1)) bad.push("선택률은 0~1");
    if (a != null && a < 0) bad.push("1회 소비량은 0 이상");
    if (r.lo != null && r.mid != null && r.lo > r.mid) bad.push("낮음 ≤ 기준");
    if (r.mid != null && r.hi != null && r.mid > r.hi) bad.push("기준 ≤ 높음");
    $$(`#panel .prep input.prepin[data-i="${i}"]`).forEach(e => e.classList.toggle("bad", bad.length > 0));
    if (bad.length) { errs.push(`${it.name}: ${[...new Set(bad)].join(" · ")}`); return `<tr><td>${esc(it.name)}</td><td colspan="${cols}" class="hint" style="color:var(--neg)">입력 확인: ${esc([...new Set(bad)].join(" · "))}</td></tr>`; }
    if (a == null || r.mid == null) return `<tr><td>${esc(it.name)}</td><td colspan="${cols}" class="hint">기준 선택률과 1회 소비량을 넣으면 계산합니다</td></tr>`;
    const f = (n, k) => r[k] == null ? null : n * r[k] * a;
    const cell = (n, nB, nS) => {
      const m = f(n, "mid"), lo = f(n, "lo"), hi = f(n, "hi");
      let c = `<td class="n"><b>${Math.round(m).toLocaleString()}</b>${lo != null && hi != null ? `<div class="hint">${Math.round(lo).toLocaleString()} ~ ${Math.round(hi).toLocaleString()}</div>` : ""}`;
      if (hasB && nB != null) { const mb = f(nB, "mid"), d = mb - m; c += `<div class="hint">B ${Math.round(mb).toLocaleString()} (${d >= 0 ? "+" : ""}${Math.round(d).toLocaleString()})</div>`; }
      if (hasS && nS != null) c += `<div class="hint">머무는 손님 기준 ${Math.round(f(nS, "mid")).toLocaleString()}</div>`;
      return c + `</td>`;
    };
    const tot = PREP_W.reduce((s, w) => s + w.n, 0);
    const totB = hasB && PREP_W.every(w => w.nB != null) ? PREP_W.reduce((s, w) => s + w.nB, 0) : null;
    const totS = hasS && PREP_W.every(w => w.nS != null) ? PREP_W.reduce((s, w) => s + w.nS, 0) : null;
    return `<tr><td>${esc(it.name)} <span class="hint">${esc(it.unit)}</span></td>${PREP_W.map(w => cell(w.n, w.nB, w.nS)).join("")}${cell(tot, totB, totS)}</tr>`;
  });
  el.innerHTML = `<table class="t tight"><tr><th>품목</th>${PREP_W.map(w => `<th class="n">${esc(w.name.replace("조식 ", ""))}</th>`).join("")}<th class="n">합계</th></tr>${rows.join("")}</table>` +
    capN("예시 계산 · 실제 소비 예측 · 발주량 아님", `굵은 숫자는 지금 좌석(A)의 기준 선택률, 그 아래는 낮음 ~ 높음${hasB ? ", 'B' 는 좌석을 늘린 하루의 기준값과 A 대비 차이" : ""}${hasS ? ", '머무는 손님 기준' 은 연박 집계(실험)의 회차별 평균 인원으로 같은 식을 계산한 값" : ""}. 입력한 가정과 시뮬레이션 인원으로 계산한 예시이며, 실제 소비 예측이나 발주량이 아닙니다.`);
}

function placePanel(loc) {
  const back = MODE === "guest" && G ? "하루 요약으로" : MODE === "ask" ? "질문으로" : "하루 전체로";
  let h = `<button class="back">← ${back}</button><div class="card"><h4 style="font-size:16px">${esc(locName(loc))}</h4><span class="dev hint">${loc}</span></div>`;
  const D = MODE === "guest" && G ? (G._crowd ? DAYCACHE[G._crowd] : null) : DAY;
  const v = D && D.venue_detail && D.venue_detail[loc];
  if (v) {
    const o = occOf(v);
    const persons = v.persons_day || 0, takeout = v.takeout_day || 0;
    h += `<div class="tiles"><div class="tile"><small>L3 순매출</small><span class="big">${eok(v.krw / 1.1)}</span><br><span class="hint">${D.date} · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"}</span></div>
      <div class="tile"><small>최고 점유율 · ${seatLabel(loc, v.cap)}</small><span class="big" style="color:${o >= 95 ? "var(--neg)" : ""}">${o == null ? "-" : o + "%"}</span><br><span class="hint">${esc(v.peak_window || "")} · 이용 ${persons}명${takeout ? " · 포장 " + takeout + "명" : ""} · ${v.parties}팀</span></div></div>`;
    if (v.over_persons) h += `<div class="callout">자리가 없어 다른 선택을 한 손님 <b>${v.over_parties}팀 · ${v.over_persons}명</b>${noteI("이 업장에 가려 했으나 공급 제한(만석 · 대기)으로 다른 선택을 한 손님입니다. 팀마다 이 업장에서 처음 막힌 회차에 한 번만 센 일행 수라 중복이 없습니다.")}</div>`;
    const ws = v.windows.filter(w => w.persons || w.takeout || w.over_persons);
    if (ws.length) h += `<div class="card"><h4>회차별</h4><table class="t tight winT"><tr><th>회차</th><th>시간</th><th class="n">착석</th><th class="n">점유</th><th class="n">막힘${noteI("자리가 없어 다른 선택을 한 팀의 일행 수 · 팀마다 처음 막힌 회차에 한 번")}</th></tr>` +
      ws.map(w => `<tr><td>${esc(w.name.replace(" (익일)", ""))}${/익일/.test(w.name) ? `<div class="hint">다음날</div>` : ""}</td><td class="tm">${w.t0.slice(6)}~${w.t1}</td><td class="n">${w.persons}명${w.takeout ? `<div class="hint">포장 ${w.takeout}</div>` : ""}</td><td class="n" style="color:${w.peak_pct >= 95 ? "var(--neg)" : ""}">${w.peak_pct == null ? "-" : w.peak_pct + "%"}</td><td class="n" style="color:${w.over_persons ? "var(--neg)" : ""}">${w.over_persons ? w.over_persons + "명" : ""}</td></tr>`).join("") +
      `</table>${capN("착석 = 회전 포함 · 점유 = 같은 시각 최대 ÷ 좌석", "이용 인원은 회전을 포함한 착석 인원, 점유율은 같은 시각 최대 착석 ÷ 좌석입니다. '다음날' 회차는 이 날 체크인한 손님의 다음날 식사만 셉니다.")}</div>`;
    if (loc === "THE_BUFFET") h += prepCard(v, D);
    if (v.l4.length) h += `<div class="card"><h4>L4 상품 · 수량 · 순매출</h4><table class="t"><tr><th>상품</th><th class="n">수량</th><th class="n">순매출</th></tr>${v.l4.map(x => `<tr><td>${esc(l4Disp(x.product))}</td><td class="n">${x.qty}</td><td class="n">${won(x.krw / 1.1)}</td></tr>`).join("")}</table></div>`;
    if (v.l5.length) h += `<div class="card"><h4>L5 집계행 · 누가 샀나</h4><div class="l5"><span class="h">구성·방문 목적</span><span class="h">대표자 연령</span><span class="h">AI 유형</span><span class="h">투숙</span><span class="h n">팀</span><span class="h n">순매출</span>${v.l5.map(x => `<span>${esc(x.purpose)}</span><span>${esc(x.age)}</span><span>${esc(x.ai_type)}</span><span>${esc(x.guest)}</span><span class="n">${x.parties}</span><span class="n">${(x.krw / 1.1 / 10000).toFixed(0)}만</span>`).join("")}</div><div class="hint">순매출 큰 순 10줄. 손님 목록에서 한 팀을 누르면 동선으로 내려갑니다.</div></div>`;
    h += ontoPlaceCard(loc, v);
  } else if (MODE !== "guest" && DAY && DAY.present[loc]) {
    const pr = DAY.present[loc]; const mx = Math.max(...pr);
    h += `<div class="card"><h4>이 날 시간대별 인원 (최대 ${mx}명)</h4><div style="display:flex;align-items:flex-end;height:60px;gap:1px">${pr.map((v, i) => `<div title="${DAY.slots[i]} ${v}명" style="flex:1;height:${mx ? v / mx * 100 : 0}%;background:${i === DAYT ? "var(--red)" : "var(--k-facility)"}"></div>`).join("")}</div><div class="hint">그 날 10:00 ~ 다음날 13:00 · 10분 칸</div></div>`;
  }
  h += placeCards(loc, loc, MODE === "guest" && G ? T : (DAY ? tmin(DAY.slot0) + DAYT * 10 : null));
  $("#panel").innerHTML = h;
  $("#panel .back").onclick = () => (MODE === "guest" && G ? renderPanel() : MODE === "ask" ? renderAsk() : DAY ? dayPanel() : null);
  $("#panel").scrollTop = 0;
}

// ---------------------------------------------------------------------------
// 하루 전체
// ---------------------------------------------------------------------------
function syncDayForm() {
  const d = LIB.dates.find(x => x.date === $("#dDate").value) || {};
  $("#dScenario").disabled = !d.fair;
  if (!d.fair) $("#dScenario").value = "none";
}

function knobCfg() {
  const th = {};
  if ($("#kNext").checked) th.next_window = 1;
  if (+$("#kWait").value !== 150) th.wait_horizon = +$("#kWait").value;
  if (+$("#kTake").value !== 0) th.takeout_base = +$("#kTake").value;
  if ($("#kReserve").checked) th.reserve_wait = 1;
  if ($("#kQueue").value) th.queue_max = +$("#kQueue").value;
  if ($("#kTcap").value) th.takeout_cap = +$("#kTcap").value;
  if ($("#kBar").value) th.bar_nightcap = +$("#kBar").value;
  if ($("#kPurpose").checked) th.purpose_onto = 1;
  if ($("#kPass").value) th.passage_rate = +$("#kPass").value;
  if ($("#kDwell").value) th.fine_dwell = +$("#kDwell").value;
  if ($("#kMoegi").value) th.moegi_seats = +$("#kMoegi").value;
  if ($("#kBufSeats").value) th.buffet_seats = +$("#kBufSeats").value;
  if ($("#kHold").checked) th.turn_hold = 1;
  if ($("#kNoBusy") && $("#kNoBusy").value) th.no_busy_dwell = +$("#kNoBusy").value;
  if ($("#kRooms").checked) th.rooms_onto = 1;
  if ($("#kRoomFormula").checked) th.rooms_formula = 1;
  if ($("#kRngTeam").checked) th.rng_team = 1;
  if ($("#kSearch").value) th.search_w = +$("#kSearch").value;
  if ($("#kPosting").value) th.posting_k = +$("#kPosting").value;
  if ($("#kTrend").value) th.trend_w = +$("#kTrend").value;
  if ($("#kHypo").value) th.hypo = +$("#kHypo").value;
  if ($("#kOrder").checked) th.order_mix = 1;
  if ($("#kWdDine").value) th.wd_dine = +$("#kWdDine").value;
  if ($("#kWdNamed").checked && th.wd_dine != null) th.wd_named = 1;
  if ($("#kWdDay").value) th.wd_day = +$("#kWdDay").value;
  if ($("#kWdBiz").checked && th.wd_day != null) th.wd_biz = 1;
  if ($("#kBizParty").checked) th.biz_party = 1;
  if ($("#kAnom").value) { th.anomaly = +$("#kAnom").value; if ($("#kAnomK").value) th.anomaly_k = +$("#kAnomK").value; }
  return th;
}
function setKnobs(th) {
  $("#kNext").checked = !!(th && th.next_window);
  $("#kWait").value = String((th && th.wait_horizon) || 150);
  $("#kTake").value = String((th && th.takeout_base) || 0);
  $("#kReserve").checked = !!(th && th.reserve_wait);
  $("#kQueue").value = th && th.queue_max ? String(th.queue_max) : "";
  $("#kTcap").value = th && th.takeout_cap ? String(th.takeout_cap) : "";
  $("#kBar").value = th && th.bar_nightcap ? String(th.bar_nightcap) : "";
  $("#kPurpose").checked = !!(th && th.purpose_onto);
  $("#kPass").value = th && th.passage_rate ? String(th.passage_rate) : "";
  $("#kDwell").value = th && th.fine_dwell ? String(th.fine_dwell) : "";
  $("#kMoegi").value = th && th.moegi_seats ? String(th.moegi_seats) : "";
  $("#kBufSeats").value = th && th.buffet_seats ? String(th.buffet_seats) : "";
  $("#kHold").checked = !!(th && th.turn_hold);
  if ($("#kNoBusy")) $("#kNoBusy").value = th && th.no_busy_dwell ? String(th.no_busy_dwell) : "";
  $("#kRooms").checked = !!(th && th.rooms_onto);
  $("#kRoomFormula").checked = !!(th && th.rooms_formula);
  $("#kRngTeam").checked = !!(th && th.rng_team);
  $("#kSearch").value = th && th.search_w ? String(th.search_w) : "";
  $("#kPosting").value = th && th.posting_k ? String(th.posting_k) : "";
  $("#kTrend").value = th && th.trend_w ? String(th.trend_w) : "";
  $("#kAnom").value = th && th.anomaly ? String(th.anomaly) : "";
  $("#kHypo").value = th && th.hypo ? String(th.hypo) : "";
  $("#kOrder").checked = !!(th && th.order_mix);
  $("#kWdDine").value = th && th.wd_dine != null ? String(th.wd_dine) : "";
  $("#kWdNamed").checked = !!(th && th.wd_named);
  $("#kWdDay").value = th && th.wd_day != null ? String(th.wd_day) : "";
  $("#kWdBiz").checked = !!(th && th.wd_biz);
  $("#kBizParty").checked = !!(th && th.biz_party);
  $("#kAnomK").value = th && th.anomaly_k ? String(th.anomaly_k) : "";
  $("#knobs").open = !!(th && Object.keys(th).length);
}
const knobText = d => d.knobs ? d.knobs : "";
async function startDay() {
  const cfg = { date: $("#dDate").value, scenario: $("#dScenario").value, scale: +$("#dScale").value, theta: knobCfg() };
  let r;
  try { r = await api("/api/day", cfg); }
  catch (e) { $("#dayProg").classList.remove("hidden"); $("#dayProg span").textContent = "시작하지 못했습니다: " + e.message + " · 화면 서버(app.py)를 껐다 켠 뒤 다시 눌러 주세요"; return; }
  if (r.status === "done") return loadDay(r.key);
  $("#dayProg").classList.remove("hidden");
  $("#btnDay").disabled = true;
  // 10/16 진행 표시 — 지난 시간과, 최근 속도로 다시 잰 남은 시간 (좌석이 찰수록 한 팀이 느려져 엔진의 처음 평균은 짧게 나온다)
  const t0 = Date.now(), hist = [];
  let none = 0;
  const mmss = sec => sec >= 60 ? `${Math.floor(sec / 60)}분 ${Math.round(sec % 60)}초` : `${Math.round(sec)}초`;
  const stop = msg => { $("#btnDay").disabled = false; $("#dayProg span").textContent = msg; };
  const poll = async () => {
    let s;
    try { s = await api("/api/day/status?key=" + encodeURIComponent(r.key)); }
    catch (e) { return stop("진행 상황을 읽지 못했습니다: " + e.message + " · 화면 서버가 켜져 있는지 확인해 주세요"); }
    const el = (Date.now() - t0) / 1000;
    $("#dayProg i").style.width = (s.total ? s.done / s.total * 100 : 3) + "%";
    if (s.status === "done") { $("#btnDay").disabled = false; $("#dayProg").classList.add("hidden"); await refreshDays(); return loadDay(r.key); }
    if (s.status === "error") return stop("실패: " + s.error);
    if (s.status === "lost") return stop("계산 중에 화면 서버가 다시 켜져 이 계산이 끊겼습니다. 하루 돌리기를 다시 눌러 주세요");
    if (s.status === "none" && ++none > 8) return stop("계산이 시작되지 않았습니다. 화면 서버(app.py)를 껐다 켠 뒤 다시 눌러 주세요");
    let txt = "손님 만드는 중";
    if (s.total) {
      hist.push([Date.now(), s.done]);
      const old = hist[Math.max(0, hist.length - 15)];
      const rate = (s.done - old[1]) / Math.max(1, (Date.now() - old[0]) / 1000);
      txt = s.done >= s.total ? "결과 정리 중 (좌석표 · 업장 · 매출)" : `손님 돌리는 중 ${s.done.toLocaleString()} / ${s.total.toLocaleString()}팀` + (rate > 0 && hist.length > 3 ? ` · 남은 시간 약 ${mmss((s.total - s.done) / rate * 1.1)}` : "");
    }
    $("#dayProg span").textContent = `${txt} · ${mmss(el)} 지남`;
    setTimeout(poll, 1000);
  };
  poll();
}

async function loadDay(key) {
  DAY = await ensureDay(key);
  if (refreshDays.list) renderDayList();
  $("#dDate").value = DAY.date; syncDayForm(); $("#dScenario").value = DAY.scenario;
  if ([...$("#dScale").options].some(o => +o.value === DAY.scale)) $("#dScale").value = String(DAY.scale);
  // 10/16 주말 · 공휴일 하루는 평일 전용 조정값(평일 비투숙 배율 등)이 키에서 빠져 있다. 그 하루를 열었다고 설정에서 지우면
  // 다음에 평일을 돌릴 때 v4 의 평일 값이 빠진 채 돌아가므로, 주말 하루를 열 때는 지금 설정의 평일 값을 그대로 둔다
  const th = Object.assign({}, DAY.theta || {});
  if (!isWeekday(DAY.date)) {
    const cur = knobCfg(), v4 = v4For(DAY.date);
    const isV4 = Object.keys(v4).every(k => th[k] === v4[k]);
    WEEKDAY_ONLY.forEach(k => { if (th[k] == null) { const v = isV4 ? PRE.full[k] : cur[k]; if (v != null) th[k] = v; } });   // v4 하루였으면 v4 의 평일 값을 채운다
  }
  setKnobs(th);
  DAYT = 30;   // 15:00
  if (MODE === "ask") renderAsk(); else if (MODE === "report") renderReport(); else if (MODE !== "day") setMode("day"); else showDay(DAY);
  refreshDays();
}

function showDay(D) {
  $("#mapEmpty").classList.add("hidden");
  $("#trail").innerHTML = ""; $("#agent").innerHTML = "";
  drawPins(); drawDayStrip(); drawDay(); dayPanel();
}

// 색은 좌석 점유율 하나만 뜻한다 (10/15 v1.31) — 빨강은 만석에 가까운 혼잡에만 쓰고, 좌석이 없는 곳은 회청색
function loadColor(r) {
  if (r == null) return "#7d8fa8";
  if (r >= 0.95) return "#b8232f";
  if (r >= 0.75) return "#d98a3a";
  if (r >= 0.5) return "#e3c06b";
  if (r > 0) return "#a9c08a";
  return "#e6dfd2";
}
const LOADLEG = `<span><i style="background:#a9c08a"></i>~50%</span><span><i style="background:#e3c06b"></i>50%~</span><span><i style="background:#d98a3a"></i>75%~</span><span><i style="background:#b8232f"></i>95%~ 혼잡 (만석에 가까움)</span>`;

let MAPVIEW = "now", OPENB = null, FANC = null;   // 지도: 지금 시각 / 하루 누적 · 펼친 건물 · 펼친 판(이름표 가림 계산용)
function setMapView(v) {
  MAPVIEW = v;
  $$("#mapView button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  if (v === "day") setPlay(false);
  if (DAY) drawDay();
}

// 하루 누적의 색 = 그 업장이 만석(95% 이상)이었던 시간 — 하루 최고 점유율은 거의 모든 식당이 100% 라 구분이 안 된다
function fullColor(h, peak) {
  if (h == null) return loadColor(null);
  if (h >= 3) return "#b8232f";
  if (h >= 1) return "#d98a3a";
  if (h > 0) return "#e3c06b";
  return peak > 0 ? "#a9c08a" : "#e6dfd2";
}
const FULLLEG = `<span><i style="background:#a9c08a"></i>만석 없음</span><span><i style="background:#e3c06b"></i>만석 1시간 미만</span><span><i style="background:#d98a3a"></i>1~3시간</span><span><i style="background:#b8232f"></i>3시간 이상 혼잡</span>`;

// 지도 상태줄 · 이 날이 기준 운영인지 변칙 · 조정값을 바꾼 날(변경)인지
function dayCond(D) {
  const k = knobParts(D), th = Object.assign({}, D.theta || {}); delete th.anomaly; delete th.anomaly_k;
  return k.extra.length ? ` · 변경 운영: ${k.extra.join(" · ")}` : isV4Theta(th, D.date) ? " · 기준 운영" : ` · 변경 운영: ${k.base}`;
}
function drawDay() {
  const D = DAY, k = DAYT, cum = MAPVIEW === "day";
  // 지금 시각: 그 10분 칸의 인원 · 좌석 점유율 / 하루 누적: 업장별 하루 이용 인원 · 만석이었던 시간
  let items;
  if (cum) items = Object.entries(D.venue_detail || {}).filter(([l]) => LOC[l]).map(([l, v]) => {
    const st = D.seats[l];
    const fullH = st ? st.load.filter(x => x / st.cap >= 0.95).length / 6 : null;
    return { loc: l, v: (v.persons_day || 0) + (v.takeout_day || 0), peak: v.peak_day, fullH, over: v.over_persons || 0 };
  });
  else {
    items = Object.entries(D.present).map(([l, a]) => ({ loc: l, v: a[k], ratio: D.seats[l] ? D.seats[l].load[k] / D.seats[l].cap : null })).filter(x => x.v > 0 && LOC[x.loc]);
    for (const l of Object.keys(D.seats)) if (LOC[l] && !items.some(x => x.loc === l)) items.push({ loc: l, v: 0, ratio: 0 });   // 좌석 있는 식당은 비어 있어도 보인다
  }
  const col = m => cum ? fullColor(m.fullH, m.peak) : loadColor(m.ratio);
  const rad = v => Math.min(cum ? 30 : 36, 4 + Math.sqrt(v) * (cum ? 1.0 : 1.5));
  const marks = [], groups = {};
  let fanC = null;
  for (const it of items) { const b = LOC2B[it.loc]; if (b) (groups[b] = groups[b] || []).push(it); else marks.push({ ...it, x: LOC[it.loc][0], y: LOC[it.loc][1] }); }
  let under = "";
  for (const [bid, mem] of Object.entries(groups)) {
    const B = BLDG[bid];
    if (mem.length === 1 && OPENB !== bid) { marks.push({ ...mem[0], x: LOC[mem[0].loc][0], y: LOC[mem[0].loc][1] }); continue; }
    if (OPENB === bid) {
      mem.sort((a, b) => b.v - a.v);
      const R = 64 + mem.length * 4;
      under += `<circle class="fanBack" cx="${B.at[0]}" cy="${B.at[1]}" r="${R + 34}"/><text class="fanTitle" x="${B.at[0]}" y="${Math.max(14, B.at[1] - R - 40)}" text-anchor="middle">${esc(B.name)} 안 업장 · × 로 접기</text>`;
      fanC = { x: B.at[0], y: B.at[1], R: R + 34 };
      mem.forEach((m, i) => {
        const [x, y] = fanPos(bid, mem.length, i);
        under += `<line class="fanLine" x1="${B.at[0]}" y1="${B.at[1]}" x2="${x}" y2="${y}"/>`;
        marks.push({ ...m, x, y, fan: Math.sign(x - B.at[0]) || 1, always: true });
      });
      marks.push({ bid, x: B.at[0], y: B.at[1], v: -1, close: true });
    } else {
      const ag = { bid, x: B.at[0], y: B.at[1], v: mem.reduce((a, m) => a + m.v, 0), n: mem.length };
      if (cum) { const hs = mem.map(m => m.fullH).filter(h => h != null); ag.fullH = hs.length ? Math.max(...hs) : null; ag.peak = Math.max(0, ...mem.map(m => m.peak || 0)); ag.full = mem.filter(m => m.fullH >= 3).length; }
      else { const rs = mem.map(m => m.ratio).filter(r => r != null); ag.ratio = rs.length ? Math.max(...rs) : null; ag.full = mem.filter(m => m.ratio != null && m.ratio >= 0.95).length; }
      marks.push(ag);
    }
  }
  marks.sort((a, b) => b.v - a.v);
  // 14차 · 이름 · 인원 글자는 #labels 의 이름표 카드가 맡는다 (건물: 이름 아래 작은 줄 '81명 · 업장 4곳', 혼잡은 실제일 때만 배지 · 일반 시설: 이름만, 혼잡 배지만).
  //   원 옆 글자는 펼친 건물 안 업장(always)에만 단다. 같은 이름 · 수치가 두 번 보이지 않게
  for (const kk of Object.keys(LABSTAT)) delete LABSTAT[kk];
  for (const m of marks) {
    if (m.close) continue;
    if (m.bid) LABSTAT[m.bid] = cum ? { line2: `하루 ${m.v.toLocaleString()}명 · 업장 ${m.n}곳`, line2w: `하루 0,000명 · 업장 0곳`, badge: m.full ? `만석 ${m.full}곳` : null }
      : { line2: `${m.v.toLocaleString()}명 · 업장 ${m.n}곳`, line2w: `000명 · 업장 0곳`, badge: m.full ? `혼잡 ${m.full}` : null };
    else if (!m.always) LABSTAT[m.loc] = cum ? { badge: m.fullH >= 0.5 ? `만석 ${m.fullH.toFixed(1)}시간` : null } : { badge: m.ratio != null && m.ratio >= 0.95 ? "혼잡" : m.ratio != null && m.ratio >= 0.75 ? "붐빔" : null, badgeCls: m.ratio >= 0.95 ? "full" : "busy" };
    if (m.always) { const t = `${locName(m.loc)} ${m.v.toLocaleString()}${cum && m.fullH ? ` · 만석 ${m.fullH.toFixed(1)}시간` : ""}`, r = rad(m.v), left = m.fan < 0; m.lbl = { x: left ? m.x - r - 5 : m.x + r + 5, anchor: left ? "end" : "start", t }; }
  }
  const tip = m => m.bid ? `${BLDG[m.bid].name} · 업장 ${m.n}곳 · ${m.v}명 · 누르면 안의 업장이 펼쳐집니다` :
    `${locName(m.loc)} ${m.v}${cum ? " 인 · 회" : "명"}` + (cum ? (m.fullH != null ? ` · 만석이었던 시간 ${m.fullH.toFixed(1)}시간 · 초과 수요 ${m.over}명(막힌 팀의 일행 수)` : "") : (m.ratio != null && D.seats[m.loc] ? ` · 좌석 ${D.seats[m.loc].load[k]}/${D.seats[m.loc].cap}` : ""));
  // 건물을 펼치면: 다른 표시 → 펼친 판(바탕 · 선) → 펼친 업장 순으로 그려 판 위가 가려지지 않게. 판 안에 걸리는 다른 이름표는 뺀다
  const inFan = m => fanC && !m.always && !m.close && Math.hypot(m.x - fanC.x, m.y - fanC.y) < fanC.R + 10;
  if (fanC) for (const m of marks) if (inFan(m)) m.lbl = null;
  FANC = fanC;
  const order = [...marks.filter(m => !m.always && !m.close), { under: true }, ...marks.filter(m => m.always || m.close)];
  $("#pins").classList.toggle("dimmed", !!fanC);
  $("#heat").innerHTML = order.map(m => {
    if (m.under) return under;
    if (m.close) return `<g class="hit bclose" data-b="${m.bid}"><title>${esc(BLDG[m.bid].name)} 접기</title><circle cx="${m.x}" cy="${m.y}" r="10"/><text x="${m.x}" y="${m.y + 5}" text-anchor="middle">×</text></g>`;
    const r = rad(m.v);
    return `<g class="hit ${m.bid ? "bgrp" : ""}" ${m.bid ? `data-b="${m.bid}"` : `data-loc="${m.loc}"`}><title>${esc(tip(m))}</title>` +
      (m.bid ? `<circle class="bring" cx="${m.x}" cy="${m.y}" r="${r + 4}"/>` : "") +
      `<circle class="heatDot" cx="${m.x}" cy="${m.y}" r="${r}" fill="${col(m)}"/>` +
      (m.bid ? `<text class="bplus" x="${m.x}" y="${m.y + 4}" text-anchor="middle">+</text>` : "") + `</g>`;
  }).join("") + order.filter(m => m.lbl).map(m => `<text class="heatLbl ${m.bid ? "b" : ""}" x="${m.lbl.x}" y="${m.y + 4}" text-anchor="${m.lbl.anchor}">${esc(m.lbl.t)}</text>`).join("");
  $$("#heat .hit[data-loc]").forEach(e => e.onclick = () => placePanel(e.dataset.loc));
  drawLabels();
  declutterLabels();
  $$("#heat .hit[data-b]").forEach(e => e.onclick = () => { OPENB = OPENB === e.dataset.b ? null : e.dataset.b; drawDay(); });
  const scen = D.scenario === "winefair" ? "와인페어 있음" : "행사 없음";
  if (cum) {
    const tot = items.reduce((a, b) => a + b.v, 0);
    $("#clock b").textContent = "하루 누적";
    $("#clock span").textContent = `${D.date.slice(5).replace("-", "/")} · ${scen}${dayCond(D)} · 하루 누적 기준 · 업장 ${items.length}곳 하루 이용 ${tot.toLocaleString()}명 · 원 크기 = 하루 이용 인원 · 색 = 만석이었던 시간`;
  } else {
    const total = Object.values(D.present).reduce((a, arr) => a + (arr[k] || 0), 0);
    $("#clock b").textContent = D.slots[k];
    $("#clock span").textContent = `${dlabel(tmin(D.slot0) + k * 10)} · ${scen}${dayCond(D)} · 모델 시각 기준 · 호텔 안 ${total.toLocaleString()}명 · 원 크기 = 이 시각 인원 · 색 = 지금 좌석 점유율`;
  }
  drawNowCard();
  $("#mapLegend").innerHTML = `${cum ? FULLLEG : LOADLEG}<span><i style="background:#7d8fa8"></i>좌석 없는 곳</span><span class="muted">점선 테두리 = 건물 (누르면 안의 업장)</span>`;
  $("#slider").value = Math.round(1000 * k / (D.slots.length - 1));
  const ph = $("#strip .playhead");
  if (ph) ph.style.left = (66 + k * 8 + 4) + "px";
}

// 10/17 UX 2차 · 시각에 따라 바뀌는 세 칸 — 어두운 대표 카드(이 시각 호텔 안 인원) · 지금 좌석이 가장 찬 곳 · 업장별 좌석 점유 상위 3곳.
//   하루 누적 보기에서는 업장 하루 이용 인원 · 만석이었던 시간이 가장 긴 곳 · 만석 시간 상위 3곳.
function loadLevel(r) { return r >= 0.95 ? "혼잡" : r >= 0.5 ? "보통" : "여유"; }
function drawNowCard() {
  const el = document.getElementById("nowCard"), D = DAY; if (!el || !D || !D.slots) return;
  const k = DAYT, cum = MAPVIEW === "day";
  const seats = Object.entries(D.seats || {}).filter(([l, v]) => v.cap && LOC[l]);
  const dateK = `${+D.date.slice(5, 7)}월 ${+D.date.slice(8, 10)}일`;
  const tf = document.getElementById("topFull");
  // 10/17 UX 3차 · '가장 찬 곳' 과 '상위 3곳' 을 한 카드로 — 1위는 크게, 2 ~ 4위는 아래 줄로 (같은 업장을 두 번 보이지 않는다)
  const row = (l, ratio, right, w) => `<button class="t3r" data-loc="${l}"><span class="nm">${esc(locName(l))}</span><span class="bar"><i style="width:${Math.min(100, Math.round((w == null ? ratio : w) * 100))}%;background:${loadColor(ratio)}"></i></span><span class="n ${ratio >= 0.95 ? "full" : ""}">${right}</span></button>`;
  const lead = (name, big, unit, lvl, ratio, l, r) => `<div class="tf-row"><b class="tf-name">${esc(name)}</b><span class="tf-pct ${lvl === "혼잡" ? "full" : ""}">${big}<span class="u">${unit}</span></span><span class="lvl l-${lvl}">${lvl}</span></div><div class="bar"><i style="width:${Math.min(100, Math.round(ratio * 100))}%;background:${loadColor(ratio)}"></i></div><div class="tf-sub"><span>${l}</span><span>${r}</span></div>`;
  let first = null;
  if (cum) {
    const tot = Object.values(D.venue_detail || {}).reduce((a, v) => a + (v.persons_day || 0) + (v.takeout_day || 0), 0);
    const take = Object.values(D.venue_detail || {}).reduce((a, v) => a + (v.takeout_day || 0), 0);
    // 연인원 — 식음 업장 회차별 착석 인원 + 포장 인원을 하루 동안 더한 값. 같은 손님이 끼니마다 · 업장마다 다시 세어진다 (고유 손님 수 아님)
    el.innerHTML = `<small>식음 업장 이용 연인원 (끼니마다 셈 · 포장 포함)</small><div class="hero-n">${tot.toLocaleString()}<span class="u">명</span></div><div class="hero-foot"><span class="badge">하루 누적</span><span>고유 고객 ${D.persons.toLocaleString()}명</span></div>`;
    el.title = `업장별 하루 착석 인원(회차마다 셈) + 포장 ${take.toLocaleString()}명. 같은 손님이 조식 · 석식을 모두 이용하면 2명으로 셉니다.`;
    const R = seats.map(([l, v]) => { const vd = (D.venue_detail || {})[l] || {}; return { l, h: v.load.filter(x => x / v.cap >= 0.95).length / 6, peak: (vd.peak_day || 0) / 100, over: vd.over_persons || 0 }; })
      .filter(r => r.h > 0).sort((a, b) => b.h - a.h || b.peak - a.peak || b.over - a.over);
    const mxH = Math.max(0.1, ...R.map(r => r.h)), b = R[0];
    if (tf) tf.innerHTML = !b ? `<small>만석이었던 식당</small><div class="tf-none">이 날 만석(95% 이상)이었던 식당이 없습니다.</div>`
      : `<small>${R.length === 1 ? "만석이었던 식당" : "만석 시간이 가장 긴 곳"}</small>` + lead(locName(b.l), b.h.toFixed(1), "시간", "혼잡", b.peak, `최고 점유 ${Math.round(b.peak * 100)}%`, b.over ? `초과 수요 ${b.over.toLocaleString()}명` : "초과 수요 없음") +
        (R.length > 1 ? `<div class="t3-h">다음으로 만석이 길었던 곳</div>` + R.slice(1, 4).map(r => row(r.l, r.peak, `${r.h.toFixed(1)}시간`, r.h / mxH)).join("") : "");
    first = b && b.l;
  } else {
    const total = Object.values(D.present || {}).reduce((a, arr) => a + (arr[k] || 0), 0);
    el.innerHTML = `<small>이 시각 호텔 안 고객</small><div class="hero-n">${total.toLocaleString()}<span class="u">명</span></div><div class="hero-foot"><span class="badge">모델 시각 ${esc(D.slots[k])}</span><span>모델 계산 · ${dateK}</span></div>`;
    el.title = "";
    const R = seats.map(([l, v]) => ({ l, ld: v.load[k] || 0, cap: v.cap, r: (v.load[k] || 0) / v.cap })).filter(r => r.ld > 0).sort((a, b) => b.r - a.r || b.ld - a.ld);
    const b = R[0];
    const title = !b ? "지금 이용 중인 식당" : R.length === 1 ? (b.r >= 0.95 ? "현재 혼잡 업장" : "지금 이용 중인 식당") : "지금 좌석이 가장 찬 곳";
    if (tf) tf.innerHTML = `<small>${title}</small>` + (!b ? `<div class="tf-none">이 시각에 앉아 있는 식당 손님이 없습니다.</div>`
      : lead(locName(b.l), Math.round(b.r * 100), "%", loadLevel(b.r), b.r, `${b.ld.toLocaleString()} / ${b.cap.toLocaleString()}석`, b.r >= 0.95 ? "좌석이 모두 찼어요" : "") +
        (R.length > 1 ? `<div class="t3-h">다음으로 찬 곳</div>` + R.slice(1, 4).map(r => row(r.l, r.r, `${Math.round(r.r * 100)}%`)).join("") : `<div class="tf-note">이 시각 손님이 앉아 있는 식당은 이곳 하나입니다.</div>`));
    first = b && b.l;
  }
  if (tf) {
    if (first) tf.dataset.loc = first; else delete tf.dataset.loc;
    const head = tf.querySelector(".tf-row");
    if (head) { head.classList.add("click"); head.onclick = () => placePanel(first); }
  }
  document.querySelectorAll("#panel .t3r[data-loc]").forEach(b => b.onclick = e => { e.stopPropagation(); placePanel(b.dataset.loc); });
}

function drawDayStrip() {
  const D = DAY;
  const rows = Object.entries(D.seats).filter(([, v]) => Math.max(...v.load) > 0);
  let h = `<div class="strip-inner heatgrid" style="width:${66 + D.slots.length * 8 + 20}px;padding-top:20px">`;
  h += `<div class="strip-axis" style="left:66px">${D.slots.map((s, i) => (i % 6 === 0 ? `<span class="${s === "00:00" ? "day" : ""}" style="left:${i * 8 + 4}px">${s === "00:00" ? dlabel(tmin(D.slot0) + i * 10) : s}</span>` : "")).join("")}</div>`;
  for (const [loc, v] of rows) {
    h += `<div class="hrow"><span class="nm">${esc(v.name)}</span>${v.load.map((x, i) => `<span class="c" data-k="${i}" title="${esc(v.name)} ${D.slots[i]} · ${x}/${v.cap}석" style="width:7px;background:${loadColor(x / v.cap)}"></span>`).join("")}</div>`;
  }
  h += `<div class="legend" style="margin-left:66px">${LOADLEG}<span>좌석 대비 앉아 있는 인원 · 칸을 누르면 그 시각으로</span></div>`;
  h += `<div class="playhead" style="left:${66 + DAYT * 8 + 4}px"></div></div>`;
  // 식당 줄 수만큼 띠를 키운다 (줄 15px + 눈금 · 범례 · 가로 스크롤 막대)
  $("#strip").style.height = (20 + rows.length * 15 + 26 + 18) + "px";
  $("#strip").innerHTML = h;
  $$("#strip .c").forEach(e => e.onclick = () => { DAYT = +e.dataset.k; setPlay(false); if (MAPVIEW !== "now") setMapView("now"); else drawDay(); });
}

let DAYFILTER = "all", DAYSORT = "spend";
const L2N = { ROOM: "ROOM 객실", "F&B": "F&B 식음", "레저": "LEISURE 레저" };
// 10/19 소연 ①-9 · ①-10 — 좌석 수의 범위 · 등급을 함께. 모에기 40 은 홀만 센 모델 조정값(전체 103석 = 스시바 · 홀 · 데판야끼 · 별실), 르 파사쥬 30 은 추정
function seatLabel(loc, cap) {
  if (loc === "MOEGI" && cap && cap < 103) return `홀 ${cap}석 기준 <span class="hint">(전체 103석 · 모델 조정값)</span>`;
  if (loc === "LE_PASSAGE") return `${cap}석 <span class="gtxt">△</span> <span class="hint">(홈페이지에 좌석 표기 없음 · 추정)</span>`;
  return `${cap}석`;
}
function occOf(v) { return v.cap ? (v.peak_day || 0) : null; }   // 최고 점유율 = 최대 동시 착석 ÷ 좌석 (그 날 회차 중)

// 10/17 UX 2차 · 오른쪽 '운영 상황' — 카드 하나에 핵심 숫자 하나. 맨 위 어두운 카드(이 시각 호텔 안)만 강조, 나머지는 밝게.
//   시각에 따라 바뀌는 두 칸(#nowCard · #topFull)은 drawNowCard 가 채우고, 하루 누적 타일 둘은 여기서. 세부 지표 · 근거는 '전체 지표 상세' 드로어.
function dayPanel() {
  const D = DAY;
  const net = v => eok(v / 1.1);
  const GG = D.guests || [], sw = GG.filter(g => (g.n_switch || 0) > 0).length, swp = GG.length ? Math.round(sw / GG.length * 100) : 0;
  const dateK = `${+D.date.slice(5, 7)}월 ${+D.date.slice(8, 10)}일`;
  const dow = "일월화수목금토"[new Date(D.date + "T00:00:00").getDay()];
  let h = `<div class="ops-head"><b>운영 상황</b><span class="hint">${esc(D.date.slice(5).replace("-", "/"))} (${dow}) · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"}${D.anomaly && D.anomaly.name ? " · " + esc(D.anomaly.name) : ""}</span></div>`;
  h += `<div class="hero" id="nowCard"></div>`;
  h += `<div class="card topfull" id="topFull"></div>`;
  h += `<div class="tiles ops-tiles">` +
    `<div class="tile"><small>하루 방문 팀</small><span class="big">${D.n.toLocaleString()}팀</span><span class="sub">고유 고객 ${D.persons.toLocaleString()}명</span></div>` +
    `<div class="tile" title="VAT 제외 · 결제액 ${eok(D.total)}"><small>체류 매출</small><span class="big">${net(D.total)}</span><span class="sub">모델 추정 · VAT 제외</span></div></div>`;
  h += `<div class="card insight"><small>운영 인사이트</small><div class="ins-line">${GG.length ? `${GG.length.toLocaleString()}팀 중 <b>${sw.toLocaleString()}팀 (${swp}%)</b>이 만석 · 대기로 다른 곳을 골랐습니다.` : "손님 목록이 없는 날입니다."}</div>` +
    `<div class="dact"><a class="rv-btn rv-main" data-gomode="report">운영 요약 보기 →</a><button class="rv-btn" id="btnDayDetail" title="매출 계산 · 온톨로지 대조 · 가설 · 변칙 · 시드 범위 · 출처 · 손님 목록">전체 지표 상세</button></div></div>`;
  h += `<div class="hint ops-note">${D.knobs ? `조정값 ${esc(knobSummary(D))} · ` : ""}시드 0 한 번 계산한 값 · 실제 운영 기록이 아닙니다.</div>`;
  if (staleNote(D)) h += staleNote(D);
  $("#panel").innerHTML = h;
  $$("#panel .rlink[data-gomode], #panel .rv-btn[data-gomode]").forEach(a => a.onclick = () => setMode(a.dataset.gomode));
  const bd = $("#btnDayDetail"); if (bd) bd.onclick = () => openDayDetail();
  drawNowCard();
}
// 10/17 UX — 하루 전체 상세 (매출 트리 · 온톨로지 · 가설 · 변칙 · SNS · 시드 범위 · 출처 · CSV · 프로그램 · 조정값 전후 · 손님 목록) 는 공통 상세 패널에서 연다.
//   카드 내용 · 숫자 · 근거 · 만드는 함수는 이전 우측 패널 그대로 (지시서 0: 근거 삭제 없음).
function openDayDetail() {
  const D = DAY; if (!D) return;
  const l2 = D.by_l2 || {};
  const net = v => eok(v / 1.1);
  const after = [];
  let h = dayStatsCard(D);
  h += `<details class="card fold"><summary><h4>매출 계산 보기 · L1 전체 → L2 부문 → L3 업장 (순매출)</h4></summary><div class="tree">
    <div class="l1"><span>L1 전체</span><span>${net(D.total)}</span></div>
    ${["ROOM", "F&B", "레저"].map(k => `<div class="l2"><span>L2 ${L2N[k]}</span><span>${net(l2[k] || 0)}</span></div>` +
      Object.entries(D.by_l3).filter(([n, v]) => v > 0 && l3of(D, n) === k).map(([n, v]) => `<div class="l3" data-loc="${loc3(D, n)}"><span>${esc(l3Disp(n))}</span><span>${net(v)}</span></div>`).join("")).join("")}
    </div><div class="hint">업장을 누르면 L4 상품 · L5 집계행으로 내려갑니다. 빛의 시어터는 호텔 매출 밖 참고 줄입니다.</div></details>`;
  h += ontoDayCard(D);
  h += hypoCard(D);
  h += anomalyCard(D);
  h += trendCard(D);
  h += `<div id="bandCard"></div>`;
  after.push(() => bandCard(D));
  h += provenanceCard();
  h += `<div class="card"><h4>L5 집계행 내보내기</h4><a class="ghost wide btn" href="/api/day/l5.csv?key=${encodeURIComponent(D.key)}" download>CSV 내려받기 — 온톨로지 집계행과 같은 열</a><div class="hint">구매 날짜 · L1 · L2 · L3 업장 · L4 상품 · 성별 · 대표자 연령 · 구성·방문 목적 · AI 유형 · 투숙 · 행사 · 수량 · 결제액 · 순매출. 사이트에서 같은 필터로 긁은 표와 줄 단위로 맞춰 보는 용도. 엑셀 · 검수본은 노션 · 드라이브에만 둡니다.</div></div>`;
  // 점유율 · 수용 범위 초과 수요
  const vd = D.venue_detail || {};
  const rows = Object.entries(vd).filter(([, v]) => v.parties > 0 || v.over_persons > 0).sort((a, b) => b[1].krw - a[1].krw);
  h += programCard(D);
  const kn = D.knobs || "";
  const sameVer = d => d.model_ver === D.model_ver && d.input_ver === D.input_ver;      // 10/14 — 다른 코드 · 입력으로 계산한 결과와는 비교하지 않는다
  const canonAll = th => JSON.stringify(Object.keys(th || {}).sort().map(k => [k, th[k]]));
  const base = kn ? (refreshDays.list || []).find(d => d.date === D.date && d.scale === D.scale && d.scenario === D.scenario && !d.knobs && sameVer(d)) : null;
  if (base) {
    h += `<div class="card" id="cmpk"><h4>조정값 전후 — 불러오는 중…</h4></div>`;
    after.push(() => ensureDay(base.key).then(B => compareGeneric("cmpk", D, B, `조정값 전후 (${esc(kn)} − 기본)`, "같은 날 · 같은 행사 · 같은 규모에서 조정값만 다른 두 계산의 차이. 손님 생성은 같으니 차이는 전부 행동 선택에서 나옵니다.")));
  }
  // 한 조정값만 끈 날과 비교 — SNS 신호 가중 · 변칙 시나리오 (나머지 조정값은 같음)
  const FOCUS = [
    { keys: ["trend_w"], id: "cmpt", on: D.theta && D.theta.trend_w, title: () => `SNS 신호 가중 전후 (강도 ${D.theta.trend_w} − 끔 · 나머지 조정값 같음)`, hint: "같은 손님에게 '가고 싶은 식당' 만 SNS 구성 쪽으로 바꾼 두 계산의 차이. 업장 이용 · 매출 차이는 그 선호가 자리 · 회차 · 대체를 거쳐 남은 몫입니다.", miss: "SNS 신호 가중 전후 비교는 같은 조정값에서 'SNS 신호 가중' 만 끈 날을 한 번 더 돌리면 나옵니다." },
    { keys: ["order_mix"], id: "cmpo", on: D.theta && D.theta.order_mix, title: () => "처리 순서 섞기 전후 (섞음 − 투숙 먼저 · 나머지 조정값 같음)", hint: "같은 손님을 좌석 잡는 순서만 바꿔 돌린 차이 — 비투숙 손님이 늘 남은 자리만 보던 구조가 업장 이용을 얼마나 바꾸는지.", miss: "처리 순서 전후 비교는 같은 조정값에서 순서 섞기만 끈 날을 한 번 더 돌리면 나옵니다." },
    { keys: ["hypo"], id: "cmph", on: D.theta && D.theta.hypo, title: () => `가설 실험 전후 (H${D.theta.hypo} ${esc((D.hypo || {}).name || "")} − 끔 · 나머지 조정값 같음)`, hint: "같은 손님에게 가설이 말하는 입력 하나만 바꾼 두 계산의 차이 — 예측대로 움직였는지 아래 '시드 범위' 카드의 편차 대비와 같이 봅니다.", miss: "가설 실험 전후 비교는 같은 조정값에서 가설만 끈 날을 한 번 더 돌리면 나옵니다." },
    { keys: ["anomaly", "anomaly_k"], id: "cmpa", on: D.theta && D.theta.anomaly, title: () => `변칙 시나리오 전후 (${esc((D.anomaly || {}).name || "")} − 평상시 · 나머지 조정값 같음)`, hint: "같은 날 · 같은 조정값에서 변칙 하나만 넣은 계산과 평상시의 차이 — 손님이 어디로 옮기고 매출이 어디서 빠지고 붙는지.", miss: "변칙 시나리오 전후 비교는 같은 조정값에서 변칙 시나리오만 뺀 날(평상시)을 한 번 더 돌리면 나옵니다." },
  ];
  for (const F of FOCUS) {
    if (!F.on) continue;
    const canon = th => JSON.stringify(Object.keys(th || {}).filter(k => !F.keys.includes(k)).sort().map(k => [k, th[k]]));
    const off = (refreshDays.list || []).find(d => d.date === D.date && d.scale === D.scale && d.scenario === D.scenario && !F.keys.some(k => d.theta && d.theta[k]) && canon(d.theta) === canon(D.theta) && sameVer(d));
    if (off) {
      h += `<div class="card" id="${F.id}"><h4>${esc(F.title())} — 불러오는 중…</h4></div>`;
      after.push(() => ensureDay(off.key).then(B => compareGeneric(F.id, D, B, F.title(), F.hint)));
    } else h += `<div class="hint">${F.miss}</div>`;
  }
  const other = (refreshDays.list || []).find(d => d.date === D.date && d.scale === D.scale && d.scenario !== D.scenario && canonAll(d.theta) === canonAll(D.theta) && sameVer(d));   // 행사만 다르고 조정값 · 버전이 같은 날만
  if (other) {
    h += `<div class="card" id="cmp"><h4>${D.scenario === "winefair" ? "행사 없음" : "와인페어 있음"}과 비교 — 불러오는 중…</h4></div>`;
    after.push(() => ensureDay(other.key).then(O => compareCard(D, O)));
  } else if (LIB.dates.find(x => x.date === D.date && x.fair)) {
    h += `<div class="callout info">같은 날을 ${D.scenario === "winefair" ? "행사 없음" : "와인페어 있음"}으로도 돌려 두면 시나리오 비교가 나옵니다.</div>`;
  }
  if (D.switches.length) h += `<details><summary>공급 제한으로 바뀐 선택 (${D.n_switch.toLocaleString()}건 · ${(D.n_switch_teams ?? "-").toLocaleString()}팀)</summary><table class="t"><tr><th>빠진 후보</th><th>대신 고른 곳</th><th class="n">건</th><th class="n">팀</th></tr>${D.switches.slice(0, 8).map(s => `<tr><td>${esc(s.from)}</td><td>${esc(altName(s.to))}</td><td class="n">${s.events ?? s.n}</td><td class="n">${s.teams ?? "-"}</td></tr>`).join("")}</table><div class="hint">건 = 손님이 후보를 고를 때마다 센 횟수(같은 팀이 여러 번 셀 수 있음) · 팀 = 고유 팀. '빠진 후보' 는 공급 제한(만석 · 대기)으로 빠진, 고른 곳보다 점수가 높았던 후보입니다. 자리가 있었으면 반드시 그곳에 갔다는 뜻은 아닙니다.</div></details>`;
  h += `<div id="guestListCard">${guestListHtml(D)}</div>`;
  openDrawer("하루 전체 · 전체 지표 상세", `${D.date} · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${knobSummary(D)} · 시드 0 한 번 (시드 범위는 아래 카드)`, h, root => {
    wireDayDetail(root);
    after.forEach(f => f());
  });
}
function guestListHtml(D) {
  const F = { all: () => true, guest: g => g.is_guest, day: g => !g.is_guest, fair: g => g.fair, sw: g => g.n_switch > 0 };
  const list = D.guests.map((g, i) => ({ ...g, i })).filter(F[DAYFILTER]);
  list.sort((a, b) => DAYSORT === "spend" ? b.spend - a.spend : DAYSORT === "sw" ? b.n_switch - a.n_switch : a.i - b.i);
  return `<div class="card"><h4>손님 목록 — 누르면 그 팀의 하루를 지도에서</h4>
    <div class="filter">${[["all", "전체"], ["guest", "투숙"], ["day", "비투숙"], ["fair", "와인페어"], ["sw", "공급 제한 겪음"]].map(([k, n]) => `<button data-f="${k}" class="${DAYFILTER === k ? "on" : ""}">${n}</button>`).join("")}
    <span style="flex:1"></span>${[["spend", "순매출 순"], ["sw", "제한 순"], ["id", "번호 순"]].map(([k, n]) => `<button data-s="${k}" class="${DAYSORT === k ? "on" : ""}">${n}</button>`).join("")}</div>
    <table class="t"><tr><th>손님</th><th>한 일</th><th class="n">순매출</th></tr>${list.slice(0, 60).map(g => `<tr class="click" data-i="${g.i}"><td>${g.is_guest ? PROPS[g.property] + " " + g.nights + "박" : g.wf_ext ? "와인페어 외부" : "비투숙"} · ${g.party}인${g.kids ? " · 아이" : ""}<br><span class="hint">${esc(g.age || "")} · ${esc(g.purpose || "")}</span></td><td style="font-size:11px">${esc(g.acts.filter(a => !["객실", "취침", "짐 맡김", "체크인 대기", "프런트 응대", "키 수령", "도착"].includes(a)).slice(0, 5).join(" → "))}${g.n_switch ? ` <span style="color:var(--neg)">제한 ${g.n_switch}</span>` : ""}</td><td class="n">${(g.spend / 1.1 / 10000).toFixed(0)}만</td></tr>`).join("")}</table>
    <div class="hint">${list.length.toLocaleString()}팀 중 60팀까지</div></div>`;
}
function wireDayDetail(root) {
  const redraw = () => { const c = root.querySelector("#guestListCard"); if (c) { c.innerHTML = guestListHtml(DAY); wireDayDetail(root); } };
  root.querySelectorAll(".filter [data-f]").forEach(b => b.onclick = () => { DAYFILTER = b.dataset.f; redraw(); });
  root.querySelectorAll(".filter [data-s]").forEach(b => b.onclick = () => { DAYSORT = b.dataset.s; redraw(); });
  root.querySelectorAll("tr.click[data-i]").forEach(e => e.onclick = () => { closeDrawer(); openDayGuest(+e.dataset.i); });
  root.querySelectorAll(".rlink[data-gomode]").forEach(a => a.onclick = () => { closeDrawer(); setMode(a.dataset.gomode); });
  root.querySelectorAll("tr.click[data-loc], .tree .l3[data-loc], .vb.click[data-loc]").forEach(e => e.onclick = () => { if (e.dataset.loc && e.dataset.loc !== "null") { closeDrawer(); placePanel(e.dataset.loc); } });
}
const L3LOC = { 그랜드: "GRAND_ROOM", 비스타: "VISTA_ROOM", 더글라스: "DOUGLAS_ROOM", 더뷔페: "THE_BUFFET", 피자힐: "PIZZA_HILL", 금룡: "GEUMRYONG", 명월관: "MYONGWOLGWAN", 모에기: "MOEGI", 온달: "ONDAL", 파빌리온: "THE_PAVILION", 럭스바: "LUX_BAR", 르파사쥬: "LE_PASSAGE", 실내수영장: "GRAND_POOL", "웰니스 사우나": "WELLNESS_SAUNA", "빛의 시어터": "THEATRE_OF_LIGHT", 와인페어: "FOREST_PARK", "와인페어 푸드트럭": "FOREST_PARK", 스카이야드: "SKYARD", 리버파크: "RIVERPARK", 포레스트파크: "FOREST_PARK" };
function loc3(D, name) { return L3LOC[name] || null; }
function l3of(D, name) {
  // 업장 → L2 (결제 줄의 l2 를 모르면 이름으로)
  if (["그랜드", "비스타", "더글라스"].includes(name)) return "ROOM";
  if (["실내수영장", "웰니스 사우나", "빛의 시어터", "와인페어", "스카이야드", "리버파크", "포레스트파크", "pool", "skyard"].includes(name)) return "레저";
  return "F&B";
}
const PROPS = { GRAND: "그랜드", VISTA: "비스타", DOUGLAS: "더글라스" };

// ---------------------------------------------------------------------------
// 온톨로지 대조 — 모델 결과를 온톨로지(대표님 모델) 비중과 나란히 놓는다. 금액은 쓰지 않고 비율만.
// ---------------------------------------------------------------------------
const ONTO_L2N = { ROOM: "ROOM 객실", "F&B": "F&B 식음", LEISURE: "LEISURE 레저" };
const shares = obj => { const t = Object.values(obj).reduce((a, b) => a + b, 0) || 1; return Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, v / t])); };
function pair(label, a, b, note) {
  // a = 모델, b = 온톨로지 (0~1). 둘 다 없으면 안 그린다
  const pa = a == null ? null : Math.round(a * 100), pb = b == null ? null : Math.round(b * 100);
  const gap = pa != null && pb != null ? pa - pb : null;
  return `<div class="pair"><span class="lb">${esc(label)}</span>
    <div class="bars"><i class="m" style="width:${pa || 0}%"></i><i class="o" style="width:${pb || 0}%"></i></div>
    <span class="v">${pa == null ? "-" : pa + "%"}</span><span class="v o">${pb == null ? "-" : pb + "%"}</span>
    <span class="g" style="color:${gap == null || Math.abs(gap) < 5 ? "var(--muted)" : gap > 0 ? "var(--pos)" : "var(--neg)"}">${gap == null ? "" : (gap > 0 ? "+" : "") + gap + "p"}${note ? ` <span class="hint">${esc(note)}</span>` : ""}</span></div>`;
}
const pairHead = () => `<div class="pair head"><span></span><span></span><span class="v">모델</span><span class="v o">온톨로지</span><span class="g">차이</span></div>`;
function ontoRef(D) {
  // 온톨로지 쪽 비중 — 10월 날짜별 자료(onto_oct)가 있으면 그 날, 없으면 10/10 L3 표 또는 10월 기준 프리셋
  const OO = (LIB.onto_oct || {}).daily || {}; const O = LIB.onto || {};
  if (OO[D.date]) {
    const d = OO[D.date]; const l2 = { ROOM: d.l2.ROOM || 0, "F&B": d.l2["F&B"] || 0, LEISURE: d.l2.LEISURE || 0 };   // 대외사업 제외
    return { src: `온톨로지 ${D.date.slice(5).replace("-", "/")} (${d.fair ? "와인페어 포함" : "와인페어 미포함"} · ${(LIB.onto_oct.src || "")})`, l2, l3: d.l3, pools: d.pools, fair: d.fair, daily: true };
  }
  const l2 = {}, l3 = {};
  if (D.date === "2026-10-10" && Object.keys(O.l3_1010 || {}).length) {
    for (const [n, x] of Object.entries(O.l3_1010)) { l2[x.l2] = (l2[x.l2] || 0) + x.eok; }
    const sub = {}; for (const [n, x] of Object.entries(O.l3_1010)) sub[x.l2] = (sub[x.l2] || 0) + x.eok;
    for (const [n, x] of Object.entries(O.l3_1010)) l3[n] = { l2: x.l2, share: x.eok / sub[x.l2] };
    l2.LEISURE = l2.LEISURE || 0;
    return { src: "온톨로지 10/10 업장별 순매출 (L3 표)", l2, l3, pools: null, daily: false };
  }
  const p = (O.presets || []).find(r => r["프리셋"] === "기준" && r["시나리오"] === "10월 전체");
  if (p) { l2.ROOM = +p.ROOM; l2["F&B"] = +p["F&B"]; l2.LEISURE = +p.LEISURE; }
  return { src: "온톨로지 10월 기준 프리셋 (L2 만 · 대외 제외)", l2, l3: null, pools: null, daily: false };
}
// 온톨로지 풀 ↔ 모델 값 — 단위를 맞춘다 (인 = 착석 인원, 세트 = 팀, 판·잔·건 = L4 수량)
function poolModel(p, v, weekday) {
  const same = v.windows.filter(w => !w.name.includes("익일"));
  // 하루 전체는 체크인 날 하나만 돌려 전날 손님의 오늘 중식이 없다 — 오늘 손님의 다음날 중식을 그 대리로 더한다 (한호님 연속 실행 역산과 같은 생각)
  const nxtLunch = v.windows.filter(w => w.name.includes("익일") && w.kind === "중식").reduce((a, w) => a + w.persons, 0);
  const sumP = kinds => same.filter(w => kinds.includes(w.kind)).reduce((a, w) => a + w.persons, 0) + (kinds.includes("중식") ? nxtLunch : 0);
  const sumT = kinds => same.filter(w => kinds.includes(w.kind)).reduce((a, w) => a + w.parties, 0);
  const L4 = v.l4_qty_day || v.l4_qty || {};     // 그 날 하루치 (없으면 체류 전체)
  const qty = re => Object.entries(L4).filter(([n]) => re.test(n)).reduce((a, [, q]) => a + q, 0);
  const allQty = Object.values(L4).reduce((a, b) => a + b, 0);
  switch (p.id) {
    case "room-grand": case "room-vista": case "room-douglas": return [null, ""];
    case "breakfast": return [null, "모델은 포함 조식과 추가 유료 조식을 아직 못 가릅니다"];
    case "buffet-week": return [sumP(["중식"]), "중식 착석"];
    case "buffet-peak": return weekday ? [sumP(["석식"]), "석식 착석 (평일은 중식이 주중 풀로 따로)"] : [sumP(["중식", "석식"]), "중식 + 석식 착석"];
    case "pizza-hall": return [same.reduce((a, w) => a + w.persons, 0) + nxtLunch, "홀 착석 인원 + 다음날 중식(전날 손님 대리) (온톨로지 가능량 672 = 96석 × 7회 → 좌석 단위)"];
    case "pizza-takeout": return [qty(/포장/), "포장 상품 수량"];
    case "pizza-addon": return [qty(/에이드/), "에이드 변경 수량"];
    case "pavilion": return [qty(/디저트|빙수/), "가을 디저트 세트 · 빙수 수량 (온톨로지 풀은 계절 디저트만 세고 나머지 상시 메뉴는 미산정 — 카페 착석 전체와는 다른 단위)"];
    case "lux": return [allQty, "음료 수량"];
    case "passage": return [allQty, "바스켓 수량"];
    default: {
      // '세트' 단위 풀도 가능량이 좌석 × 회차라 좌석(인원) 단위로 본다 (온톨로지: 세트는 좌석 수로 나눠 주문 수로 바꿈)
      if (/^geum/.test(p.id)) return [sumP(["중식", "석식"]), "중식 + 석식 착석 (모델은 홀 · PDR 을 가르지 않아 금룡 풀을 합쳐 비교)"];
      if (/week|lunch/.test(p.id)) return [sumP(["중식"]), "중식 착석"];
      const both = /휴일/.test(p.name) && !weekday;      // 평일엔 '저녁·휴일' 풀이 저녁만 (점심은 주중 풀)
      return [sumP(["석식"]) + (both ? sumP(["중식"]) : 0), both ? "중식 + 석식 착석" : "석식 착석"];
    }
  }
}
function ontoDayCard(D) {
  const R = ontoRef(D); if (!Object.keys(R.l2).length) return "";
  // 온톨로지에 없는 줄은 빼고 비교 — 와인페어 · 푸드트럭(온톨로지 10/10 에 행사 매출 줄이 없다) · 빛의 시어터(호텔 밖). 객실은 첫 밤만 (온톨로지는 하루 객실박)
  const NOT_IN_ONTO = ["와인페어", "와인페어 푸드트럭", "빛의 시어터"];
  const excl = NOT_IN_ONTO.reduce((a, k) => a + (D.by_l3[k] || 0), 0);
  const leisure = (D.by_l2["레저"] || 0) - NOT_IN_ONTO.filter(k => l3of(D, k) === "레저").reduce((a, k) => a + (D.by_l3[k] || 0), 0);
  const roomNight = (D.by_l2.ROOM || 0) - (D.room_extra_nights || 0);
  const ours2 = shares({ ROOM: roomNight, "F&B": D.by_l2["F&B"] || 0, LEISURE: leisure });
  const ours2raw = shares({ ROOM: D.by_l2.ROOM || 0, "F&B": D.by_l2["F&B"] || 0, LEISURE: D.by_l2["레저"] || 0 });
  const onto2 = shares(R.l2);
  let h = `<div class="card onto"><h4>온톨로지 대조 — L2 비중 <span class="hint">(ROOM : F&B : LEISURE, 순매출 비율 · 대외 제외)</span></h4>`;
  if (R.daily && R.fair) h += `<div class="callout info">온톨로지 이 날은 <b>와인페어 수요 효과 포함</b>이지만 행사 매출 줄(입장권 · 푸드트럭)은 없습니다. 모델의 <b>행사 없음</b>(date_factors 배율만, 행사 매출 없음)이 정의가 같고, <b>와인페어 있음</b>은 그 위에 외부 150팀 · 입장권 · 푸드트럭을 더한 것입니다. 아래 비율은 행사 줄을 빼고 셉니다.</div>`;
  h += pairHead() + ["ROOM", "F&B", "LEISURE"].map(k => pair(ONTO_L2N[k], ours2[k], onto2[k])).join("") +
    `<div class="hint">온톨로지 쪽은 ${esc(R.src)}. 모델 쪽은 객실을 첫 밤만 세고(2박 손님의 둘째 밤 ${eok((D.room_extra_nights || 0) / 1.1)} 제외 — 온톨로지는 하루 객실박), 온톨로지에 줄이 없는 와인페어 · 푸드트럭 · 빛의 시어터(${eok(excl / 1.1)})는 뺀 비율입니다. 그대로 세면 ${Math.round(ours2raw.ROOM * 100)} : ${Math.round(ours2raw["F&B"] * 100)} : ${Math.round(ours2raw.LEISURE * 100)}. 럭스바 · IRD 는 온톨로지에서 ROOM 으로 잡혀 있어 모델(F&B)과 분류가 다릅니다.</div>`;
  if (R.l3) {
    const fbO = {}, fbM = {};
    for (const [n, x] of Object.entries(R.l3)) if (x.l2 === "F&B") fbO[n] = x.share;
    for (const [n, v] of Object.entries(D.by_l3)) if (l3of(D, n) === "F&B" && n !== "IRD" && n !== "럭스바") fbM[n] = v;
    const sO = shares(fbO), sM = shares(fbM);
    const names = [...new Set([...Object.keys(fbO), ...Object.keys(fbM)])].filter(n => (sO[n] || 0) >= 0.005 || (sM[n] || 0) >= 0.005).sort((a, b) => ((sO[b] || 0) + (sM[b] || 0)) - ((sO[a] || 0) + (sM[a] || 0)));
    h += `<h4 style="margin-top:10px">F&B 안 업장 비중</h4>${pairHead()}` + names.map(n => pair(n, sM[n] ?? null, sO[n] ?? null)).join("");
    const rmO = {}, rmM = {};
    for (const n of ["그랜드", "비스타", "더글라스"]) { if (R.l3[n]) rmO[n] = R.l3[n].share; rmM[n] = D.by_l3[n] || 0; }
    const rO = shares(rmO), rM = shares(rmM);
    h += `<h4 style="margin-top:10px">ROOM 건물 비중</h4>${pairHead()}` + ["그랜드", "비스타", "더글라스"].map(n => pair(n, rM[n], rO[n])).join("");
    const gaps = names.map(n => [n, Math.round(((sM[n] || 0) - (sO[n] || 0)) * 100)]).filter(r => Math.abs(r[1]) >= 5).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    if (gaps.length) h += `<div class="callout info" style="margin-top:8px">F&B 비중 차이 5p 이상: ${gaps.map(([n, g]) => `${esc(n)} ${g > 0 ? "+" : ""}${g}p`).join(" · ")}</div>`;
  }
  // 풀 대조 — 온톨로지의 수용한도 · 실이용 vs 모델 (단위 맞춤)
  const vd = D.venue_detail || {};
  if (R.pools) {
    // 같은 업장에 휴일 풀이 둘(금룡 휴일 홀 · 휴일 PDR)이면 모델은 홀 · PDR 을 못 가르므로 한 줄로 합친다
    const act = R.pools.filter(p => p.cap > 0 && L3LOC[p.venue] && vd[L3LOC[p.venue]]);
    // 객실박 — 온톨로지 수용한도(객실 수) · 실이용 vs 모델 체크인 팀 (첫 밤)
    const rp = R.pools.filter(p => /^room-/.test(p.id));
    if (rp.length && D.guests) {
      const cnt = { GRAND: 0, VISTA: 0, DOUGLAS: 0 }; D.guests.forEach(g => { if (g.is_guest && cnt[g.property] != null) cnt[g.property]++; });
      const m = { "room-grand": cnt.GRAND, "room-vista": cnt.VISTA, "room-douglas": cnt.DOUGLAS };
      h += `<h4 style="margin-top:10px">객실박 — 온톨로지 객실 수 · 판매 vs 모델 체크인 팀</h4><table class="t"><tr><th>건물</th><th class="n">온톨로지 객실</th><th class="n">판매</th><th class="n">모델 팀</th><th class="n">대비</th></tr>` +
        rp.map(p => { const v = m[p.id]; const r = Math.round(v / (p.used || 1) * 100); return `<tr><td>${esc(p.venue)}${p.req > p.allow ? ` <span class="hint">요청 ${p.req} &gt; 허용 ${p.allow}</span>` : ""}</td><td class="n">${p.cap}</td><td class="n">${p.used}</td><td class="n">${v}</td><td class="n" style="color:${r > 110 || r < 90 ? "var(--neg)" : ""}">${r}%</td></tr>`; }).join("") +
        `</table><div class="hint">모델은 이 날 체크인한 팀(첫 밤)이고 전날 2박 손님은 없습니다(체크인 날 하나만 돌림). ${D.theta && (D.theta.rooms_formula || D.theta.rooms_onto) ? `이 계산은 객실 수를 온톨로지와 같은 507 · 244 · 50 으로 두고${D.theta.rooms_formula ? ", 건물마다 그 날 채울 객실(목표 객실박 − 이월 객실)을 먼저 정해" : ""} 체크인 팀을 냅니다 (v4 조정값).` : `모델 기본 객실 수는 그랜드 557 · 비스타 253 · 더글라스 65 이고 온톨로지는 507 · 244 · 50 입니다 (홈페이지 '총 557' 을 그랜드 507 + 더글라스 50 으로 읽음). 모델이 더 크면 객실 수 가정 차이입니다.`}</div>`;
    }
    const merged = [];
    for (const p of act) {
      // 모델이 가르지 못하는 풀은 업장 하나로 합친다 — 금룡 (홀 · PDR · 주중 · 휴일)
      const twin = /^geum/.test(p.id) ? act.filter(q => /^geum/.test(q.id)) : act.filter(q => q.venue === p.venue && q.unit === p.unit && /휴일/.test(q.name));
      if (twin.length >= 2 && (/^geum/.test(p.id) || /휴일/.test(p.name))) {
        if (twin[0] === p) merged.push({ ...p, id: p.id + "+", name: `${p.venue} 전체 (풀 ${twin.length}개 합)`, cap: twin.reduce((a, q) => a + q.cap, 0), req: twin.reduce((a, q) => a + q.req, 0), allow: twin.reduce((a, q) => a + q.allow, 0), used: twin.reduce((a, q) => a + q.used, 0) });
      } else merged.push(p);
    }
    const weekday = R.pools.some(q => /-week$/.test(q.id) && q.cap > 0);     // 온톨로지가 주중 풀을 연 날 = 평일
    const rows = merged.map(p => { const v = vd[L3LOC[p.venue]]; const [m, how] = poolModel(p, v, weekday); return { p, v, m, how, loc: L3LOC[p.venue] }; });
    const PD = (LIB.onto_oct || {}).pool_def || {};
    if (rows.length) h += `<h4 style="margin-top:10px">풀별 이용 — 온톨로지 가능량 · 실이용 vs 모델 <span class="hint">(점유율 = 실이용 ÷ 가능량, 온톨로지 정의)</span></h4><table class="t"><tr><th>풀</th><th class="n">가능량</th><th class="n">온톨로지</th><th class="n">모델</th><th class="n">대비</th></tr>` +
      rows.map(({ p, m, how, loc }) => { const r = m == null ? null : Math.round(m / (p.used || 1) * 100); const uo = p.cap ? Math.round(p.used / p.cap * 100) : null, um = p.cap && m != null ? Math.round(m / p.cap * 100) : null; const pd = PD[p.id.replace(/\+$/, "")]; return `<tr class="click" data-loc="${loc}"><td>${esc(p.name)} <span class="hint">${esc(p.unit)}${p.req > p.allow ? ` · 요청 ${p.req} &gt; 허용 ${p.allow}` : ""}</span>${pd && pd.how ? `<br><span class="hint">${esc(pd.how)}</span>` : ""}</td><td class="n">${p.cap}</td><td class="n">${p.used}<br><span class="hint">${uo == null ? "" : uo + "%"}</span></td><td class="n" title="${esc(how)}">${m == null ? "-" : m}<br><span class="hint">${um == null ? "" : um + "%"}</span></td><td class="n" style="color:${r == null ? "var(--muted)" : r < 70 || r > 130 ? "var(--neg)" : ""}">${r == null ? "" : r + "%"}</td></tr>`; }).join("") +
      `</table><div class="hint">온톨로지는 업장을 풀(가능량 = 좌석 × 회차 · 요청수요 · 입장허용 · 실이용)로 보고, 식당 고객 수 = 좌석 × 회차 × <b>점유율 55%</b> × 수요 배율로 만듭니다 — 멘토링 때 물은 55% 의 분모가 이 가능량입니다. 작은 글자 % 가 그 정의의 점유율(온톨로지 · 모델). 모델 값은 단위를 맞춘 것 (좌석형 풀은 착석 인원 — 온톨로지의 '세트' 표기도 가능량이 좌석 × 회차라 좌석 단위, 판 · 잔 · 건 = L4 수량, 모델 칸에 마우스를 올리면 무엇을 셌는지). 더뷔페 조식은 온톨로지가 추가 유료 조식만 세어 비교하지 않습니다. 중식은 하루 전체가 체크인 날 하나라 전날 투숙객의 오늘 중식이 빠지므로 오늘 손님의 다음날 중식을 대리로 더합니다. 피자힐 포장은 온톨로지에서 홀과 별개의 독립 수요(한도 60판 · 기준 30판/일)입니다.</div>`;
    // 조정값 하나씩 바꾼 결과 (온톨로지 쪽) — 어느 가정이 매출을 얼마나 움직이는지
    const SW = ((LIB.onto_oct || {}).sweeps || {})[D.date];
    if (SW && SW.length > 1) h += `<details><summary>온톨로지 조정값을 하나씩 바꾸면 (이 날 · 기준 대비 순매출)</summary><table class="t"><tr><th>조정값</th><th class="n">기준 대비</th></tr>${SW.filter(x => x.code !== "base").map(x => `<tr><td>${esc(x.name)}</td><td class="n" style="color:${x.pct < 0 ? "var(--neg)" : x.pct > 0 ? "var(--pos)" : ""}">${x.pct > 0 ? "+" : ""}${x.pct}%</td></tr>`).join("")}</table><div class="hint">온톨로지 사이트에서 조정값을 하나만 바꿔 다시 계산한 값 (경수 10/13 채집). 우리 조정값 전후 카드와 같은 자리 — 좌석 점유율 55 → 100 이 +34%, 행사 효과 0 이 −6% 수준.</div></details>`;
    const prog = R.pools.filter(p => p.l2 === "LEISURE" && p.cap > 0);
    if (prog.length) h += `<details><summary>프로그램 정원 · 이용 (온톨로지 · 모델에는 아직 없음)</summary><table class="t"><tr><th>프로그램</th><th class="n">정원</th><th class="n">실이용</th></tr>${prog.map(p => `<tr><td>${esc(p.name)}</td><td class="n">${p.cap}${esc(p.unit)}</td><td class="n">${p.used}</td></tr>`).join("")}</table><div class="hint">운영 조건표의 정원과 같은 기준입니다. 모델에는 실내수영장 · 사우나만 있고 숲 · 웰니스 프로그램은 아직 행동에 없습니다.</div></details>`;
  } else if (R.daily === false && D.date === "2026-10-10") {
    const P = (LIB.onto || {}).persons_1010 || {};
    const rows = Object.entries(P).map(([n, po]) => { const loc = L3LOC[n]; const v = loc && vd[loc]; const pm = v ? (v.persons_day || 0) + (v.takeout_day || 0) : null; return [n, pm, po, loc]; }).filter(r => r[1] != null).sort((a, b) => b[2] - a[2]);
    if (rows.length) h += `<h4 style="margin-top:10px">이용 인원 — 온톨로지 대비</h4><table class="t"><tr><th>업장</th><th class="n">모델</th><th class="n">온톨로지 대비</th></tr>` +
      rows.map(([n, pm, po, loc]) => { const r = Math.round(pm / po * 100); return `<tr class="click" data-loc="${loc}"><td>${esc(n)}</td><td class="n">${pm}명</td><td class="n" style="color:${r < 70 || r > 130 ? "var(--neg)" : ""}">${r}%</td></tr>`; }).join("") + `</table>`;
  } else if (!R.l3) {
    h += `<div class="hint">업장별 대조는 10월 날짜별 온톨로지 자료가 있을 때 나옵니다.<span class="dev"> (walkerhill_oct_base 폴더 또는 ontology_oct_daily.json)</span></div>`;
  }
  const PR = (LIB.onto_oct || {}).presets || [];
  if (PR.length) {
    const base = PR.filter(x => x.scenario === "기준");
    h += `<details><summary>온톨로지 프리셋 여섯 — 시즌 비교 (기준 시나리오 · 비율)</summary><table class="t tight"><tr><th>프리셋</th><th>기간</th><th class="n">객실<br>박/일</th><th class="n">가동률</th><th class="n">ROOM</th><th class="n">F&B</th><th class="n">LEIS.</th><th class="n">대외</th></tr>` +
      base.map(x => `<tr><td>${esc(x.preset)}</td><td class="hint">${x.start.slice(5)}~${x.end.slice(5)} · ${x.days}일</td><td class="n">${x.room_nights_day}</td><td class="n">${x.occ}%</td><td class="n">${Math.round(x.l2.ROOM * 100)}</td><td class="n">${Math.round(x.l2["F&B"] * 100)}</td><td class="n">${Math.round(x.l2.LEISURE * 100)}</td><td class="n">${Math.round(x.l2.EXTERNAL * 100)}</td></tr>`).join("") +
      `</table><div class="hint">날짜 프리셋은 기간만 바꾸고 조정값은 그대로(79 · 55 · 100 · 120). 보수 · 확대는 70 · 40 · 80 · 150 / 88 · 70 · 120 · 90. 여름은 LEISURE(리버파크)가 6%, 겨울은 0. 모델을 다른 계절로 돌려 이 표와 놓는 것이 시즌 비교입니다.</div></details>`;
  }
  return h + `</div>`;
}
// SNS 신호 — 업장 카드: 모델 · SNS 게시물 · 온톨로지 목적 구성 나란히 (trend_signals.csv)
function snsPlaceCard(loc, v, po) {
  const S = (LIB.sns || {})[loc];
  if (!S || !S.n) return "";
  const pm = v.by_purpose || {}, sM = shares(pm), tot = S.n;
  const keys = Object.keys(S.counts).sort((a, b) => (S.counts[b] - S.counts[a]) || ((sM[b] || 0) - (sM[a] || 0)));
  const pct = x => x == null ? "-" : Math.round(x * 100) + "%";
  // 15차 · 좁은 오른쪽 열에 맞게 5열로 — 'SNS 근거' 는 목적 아래 작은 줄로, 게시 성향 90% 구간은 마우스를 올리면 보이게
  return `<div class="card onto"><h4>SNS 후기 대조 — 구성 · 방문 목적 <span class="hint">게시물 ${tot}건</span></h4><table class="t tight snsT"><tr><th>목적</th><th class="n">모델</th><th class="n">SNS</th><th class="n">온톨</th><th class="n">성향</th></tr>` +
    keys.map(k => { const r = S.raw[k] || {}, g = (S.prop || {})[k];
      const gt = g ? `<span title="게시 성향 90% 구간 ${g.lo.toFixed(1)} ~ ${g.hi.toFixed(1)}${g.lo > 1 ? " · 더 올림" : g.hi < 1 ? " · 덜 올림" : ""}">${g.r.toFixed(2)}${g.lo > 1 ? "↑" : g.hi < 1 ? "↓" : ""}</span>` : "-";
      return `<tr><td>${esc(k)}<div class="hint">${r["건수"] || 0}건 · 명시 ${r["명시"] || 0} · 추정 ${r["추정"] || 0}</div></td><td class="n">${pct(sM[k] ?? 0)}</td><td class="n">${pct(S.counts[k] / tot)}</td><td class="n">${pct(po ? (po[k] ?? 0) : null)}</td><td class="n">${gt}</td></tr>`; }).join("") +
    `</table>${capN("모델 · SNS · 온톨로지 구성비 · 성향 = SNS ÷ 온톨로지", "SNS 는 게시물 수 비중, 온톨로지는 가정 원장의 고객 구성비(10월), 모델은 이 날 산 팀 비중입니다. 셋이 같은 방향을 가리키는 목적이 근거가 강한 쪽입니다. 0건은 이번 표본에서 못 봤다는 뜻이지 손님이 없다는 뜻이 아닙니다. 성향 = SNS 비중 ÷ 온톨로지 구성비(90% 구간은 숫자에 마우스를 올리면 보임) — 1보다 크면 그 목적 손님이 더 많이 올린다는 가설이고, ↑ · ↓ 는 구간이 1을 넘거나 밑도는 경우입니다.")}</div>`;
}
// SNS 신호 가중이 켜진 날 — 근거 사슬: SNS 구성 → 가고 싶은 식당(목표 · 달성) → 실제 이용 → 매출
function trendCard(D) {
  const T = D.trend;
  if (!T) return "";
  const vd = D.venue_detail || {};
  const pct = x => x == null ? "-" : (x * 100).toFixed(0) + "%";
  return Object.entries(T).map(([loc, r]) => {
    const v = vd[loc] || {}, sM = shares(v.by_purpose || {});
    return `<div class="card onto"><h4>근거 사슬 — SNS 신호 → 가고 싶은 식당 → 실제 이용 · ${esc(locName(loc))} <span class="hint">(강도 ${r.w} · SNS ${r.n}건 · 사전 ${r.K}건 섞음)</span></h4><table class="t"><tr><th>목적</th><th class="n">SNS</th><th class="n">모델 사전</th><th class="n">목표</th><th class="n">가고 싶음</th><th class="n">실제 이용</th></tr>` +
      r.rows.map(x => `<tr><td>${esc(x.purpose)}</td><td class="n">${pct(x.sns_raw)}</td><td class="n">${pct(x.model_prior)}</td><td class="n">${pct(x.target)}</td><td class="n">${pct(x.achieved)}${x.capped ? ' <span class="hint">상한</span>' : ""}</td><td class="n">${pct(sM[x.purpose] ?? 0)}</td></tr>`).join("") +
      `</table><div class="hint">SNS = 게시물 목적 비중. 모델 사전 = 이 업장을 가고 싶어 하는 손님의 원래 목적 구성 (목적 구성 × 선호 식당). 목표 = 표본이 적어 모델 사전 ${r.K}건어치를 섞고 강도만큼 SNS 쪽으로 옮긴 값. 가고 싶음 = 실제로 바꾼 뒤 구성 (한 목적 손님의 ${Math.round(r.cap * 100)}% 넘게 한 업장으로 몰지 않는 상한 때문에 못 미칠 수 있음). 실제 이용 = 자리 · 회차 · 대체를 거친 이 날 이용 팀 구성. 가고 싶음과 실제 이용의 차이가 공급 제한이 만드는 몫입니다. 손님 수와 매출 변화는 아래 '조정값 전후' 비교로 봅니다.</div></div>`;
  }).join("");
}
// 입력 출처표 — 이 날 계산에 들어간 수요 · 공급 입력이 어디서 왔는지 (input_provenance.csv)
function provenanceCard() {
  const P = LIB.provenance || [];
  if (!P.length) return "";
  const G = { "◎": "공식 자료", "○": "참조 모델(온톨로지) 값 또는 후기로 맞춘 값", "△": "가정 · 임시값" };
  const cnt = P.reduce((a, r) => (a[r["등급"].slice(0, 1)] = (a[r["등급"].slice(0, 1)] || 0) + 1, a), {});
  return `<details class="card"><summary>입력 출처표 — 이 계산에 들어간 입력 ${P.length}개 (${Object.entries(cnt).map(([g, n]) => `${g} ${n}`).join(" · ")})</summary><table class="t prov"><tr><th>입력</th><th>지금 값</th><th>등급 · 출처</th></tr>` +
    P.map(r => `<tr><td>${esc(r["입력"])}<div class="hint">${esc(r["파일 · 자리"])} · ${esc(r["담당"])}</div></td><td>${esc(r["지금 값"])} <span class="hint">${esc(r["단위"])}</span></td><td><b title="${esc(G[r["등급"].slice(0, 1)] || "")}">${esc(r["등급"])}</b> ${esc(r["출처"])}<div class="hint">${esc(r["표본 · 근거"])}${r["비고"] ? ` — ${esc(r["비고"])}` : ""}</div></td></tr>`).join("") +
    `</table><div class="hint">${GRADE_LEGEND.prov}. 운영 수치(좌석 · 회차 · 정원)는 호텔 쪽 확인이 오면 그대로 바꾸고, 수요 쪽(목적 · 연령 · 가고 싶은 식당 · 비투숙)은 SNS · 통계 · 후기 근거로 등급을 올립니다.<span class="dev"> timeline/input_provenance.csv</span></div></details>`;
}
function ontoPlaceCard(loc, v) {
  const O = LIB.onto || {}; const name = Object.entries(LIB.onto_loc || {}).find(([, c]) => c === loc)?.[0] || v.name;
  let h = "";
  // 목적 비중은 온톨로지 가정 원장(풀별 고객 구성비)을 먼저, 없으면 목적 필터 채집(슬기님)
  const PM = ((LIB.onto_oct || {}).pool_mix || {})[name];
  const po = (PM && PM.mix) || (O.purpose_by_venue && O.purpose_by_venue[loc]);
  const pm = v.by_purpose || v.l5.reduce((a, x) => (a[x.purpose] = (a[x.purpose] || 0) + x.parties, a), {});
  if (po && Object.keys(pm).length) {
    const sM = shares(pm);
    const keys = [...new Set([...Object.keys(po), ...Object.keys(pm)])].sort((a, b) => ((po[b] || 0) + (sM[b] || 0)) - ((po[a] || 0) + (sM[a] || 0)));
    h += `<div class="card onto"><h4>온톨로지 대조 — 구성·방문 목적 <span class="hint">(팀 비중)</span></h4>${pairHead()}` + keys.map(k => pair(k, sM[k] ?? null, po[k] ?? null)).join("") +
      capN("모델 = 이 날 산 팀 · 온톨로지 = 10월 구성비", `온톨로지 쪽은 ${PM ? `가정 원장의 고객 구성비 (${PM.pool} · 10월 기준)` : "월 이용 인원의 목적 필터"} 비율, 모델 쪽은 이 날 이 업장에서 산 팀의 목적 비중${v.by_purpose ? "" : " (상위 10줄만 · 다시 돌리면 전체)"}. 목적 구성은 가정값이라 여기서 차이가 크면 그 표(purpose_mix.csv)를 손봅니다.`) + `</div>`;
  }
  h += snsPlaceCard(loc, v, po);
  const GA = ((LIB.onto_oct || {}).ga || {})[name];
  if (GA && (v.by_age || v.by_sex)) {
    const aM = shares(v.by_age || {}), sM = shares(v.by_sex || {});
    const ak = [...new Set([...Object.keys(GA.age), ...Object.keys(aM)])].filter(k => k !== "미설정"), sk = [...new Set([...Object.keys(GA.sex), ...Object.keys(sM)])].filter(k => k !== "미설정");
    h += `<div class="card onto"><h4>온톨로지 대조 — 대표자 연령 · 성별 <span class="hint">(온톨로지 10월 순매출 비중 vs 모델 팀 비중)</span></h4>${pairHead()}` +
      ak.map(k => pair(k, aM[k] ?? null, GA.age[k] ?? null)).join("") + `<div style="height:6px"></div>` + sk.map(k => pair(k, sM[k] ?? null, GA.sex[k] ?? null)).join("") +
      capN("단위가 다름 · 연령 구성은 가정값", "온톨로지 쪽은 업장 안 순매출 비중(성별 · 연령 필터), 모델 쪽은 이 날 산 팀 수 비중이라 단위가 다릅니다. 연령 구성은 가정값입니다(age_mix.csv).") + `</div>`;
  }
  const lo = O.l4 && O.l4[name];
  const lm = v.l4_qty ? Object.entries(v.l4_qty) : v.l4.map(x => [x.product, x.qty]);
  if (lo && lo.length && lm.length) {
    const tO = lo.reduce((a, x) => a + x.qty, 0) || 1, tM = lm.reduce((a, x) => a + x[1], 0) || 1;
    const col = (rows, cls) => rows.map(([n, q]) => `<div class="r"><span>${esc(n)}</span><span class="n">${Math.round(q * 100)}%</span></div>`).join("");
    h += `<div class="card onto"><h4>온톨로지 대조 — L4 상품 구성 <span class="hint">(수량 비중 · 상위 6)</span></h4><div class="twocol"><div><b>모델</b>${col(lm.sort((a, b) => b[1] - a[1]).slice(0, 6).map(([n, q]) => [n, q / tM]))}</div><div><b>온톨로지</b>${col(lo.slice().sort((a, b) => b.qty - a.qty).slice(0, 6).map(x => [x.product, x.qty / tO]))}</div></div>
      ${capN("상품 이름이 달라 나란히만 둠", "상품 이름이 서로 달라 줄을 맞추지 않고 나란히 둡니다. 온톨로지 쪽은 고객 여정 자료(전체 필터)의 월 수량, 모델 쪽은 이 날 수량. 포장 비중이 모델에서 크면 피자힐 포장 가정을 봅니다.")}</div>`;
  }
  return h;
}

// ---------------------------------------------------------------------------
// 질문 · 바꿔 보기 — 계산해 둔 하루에서 답을 뽑는다
// ---------------------------------------------------------------------------
let ASKSEL = null;
function pct(a, b) { return b ? Math.round(a / b * 100) : 0; }
function bar(label, v, mx, right, col) { return `<div class="bar"><span>${esc(label)}</span><div class="tr"><i style="width:${mx ? Math.min(100, v / mx * 100) : 0}%;background:${col || "var(--k-facility)"}"></i></div><span>${right}</span></div>`; }

// 10/16 — 예전 상황 비교 카드 묶음. 새 상황 비교(compare.js)의 '상세 A/B 비교 · 예전 카드' 안에 그대로 그린다
async function renderAskLegacy(el) {
  const D = DAY;
  const date = D ? D.date : $("#dDate").value;
  const list = refreshDays.list || [];
  // 10/17 · 와인페어 효과는 같은 모델 · 입력 버전, 같은 조정값(시드 · 변칙 없음), 같은 규모의 두 하루끼리만 비교한다. 아무 하루나 짝짓지 않는다
  const curVer = d => d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver;
  const canonTh = th => JSON.stringify(Object.keys(th || {}).sort().map(k => [k, th[k]]));
  const plain = d => d.date === date && d.scale === 1 && !(d.theta && (d.theta.seed || d.theta.anomaly));
  const Ws = list.filter(d => plain(d) && d.scenario === "winefair"), Ns = list.filter(d => plain(d) && d.scenario === "none");
  let W = null, N = null;
  for (const w of Ws.filter(curVer)) { const n = Ns.find(n => curVer(n) && canonTh(n.theta) === canonTh(w.theta)); if (n) { W = w; N = n; break; } }
  const wfMismatch = !W && Ws.length && Ns.length;   // 둘 다 있지만 버전이나 조정값이 달라 짝이 안 맞음
  let h = `<div class="ask-head legacy">${date.slice(5).replace("-", "/")} · 예전 비교 카드</div><div class="ask-sub">계산해 둔 하루에서 답을 뽑습니다. 답 한 줄 → 그림 → 왜(오른쪽)의 순서이고, 값마다 ◎ 공식 · ○ 현장 · △ 추정이 붙어 있습니다.</div>`;
  if (!D) { el.innerHTML = h + `<div class="callout info">먼저 왼쪽에서 하루를 돌리거나 계산해 둔 날을 고르세요.</div>`; return; }
  const vd = D.venue_detail || {};
  const cards = [];
  // 1. 더뷔페 조식
  const bf = vd.THE_BUFFET;
  if (bf) {
    const bw = bf.windows.filter(w => w.kind === "조식" && (w.persons || w.over_persons));
    const tot = bw.reduce((a, w) => a + w.persons, 0), over = bw.reduce((a, w) => a + w.over_persons, 0);
    cards.push({ id: "bf", loc: "THE_BUFFET", h: `<h5>${bw.some(w => w.name.includes("익일")) ? "다음날 아침" : "아침"} 더뷔페 조식에 몇 명이 올까?</h5><div class="big">${tot.toLocaleString()}명</div>` +
      bw.map(w => bar(w.name.replace(" (익일)", ""), w.persons, bf.cap, `${w.persons}명 · ${w.peak_pct}%`, w.peak_pct >= 95 ? "var(--neg)" : "var(--k-meal)")).join("") +
      (over ? `<div style="font-size:12px;color:var(--neg)">수용 범위 초과 수요 ${over}명 (막힌 팀의 일행 수 · 중복 없음)</div>` : `<div class="hint">좌석 안에서 받았습니다</div>`) +
      `<div class="hint">시뮬레이션 착석 인원 · 이 날 체크인한 손님의 다음날 조식만(전체 체류 손님 미반영 · 실제 준비 인원으로 해석 불가) · 좌석 ${bf.cap}석 기준 · 준비량 계산 예시(가정 입력)는 업장 패널에</div>` });
  }
  // 10/14 운영 조건 비교 (A/B) — 맨 앞에. 같은 손님 · 같은 시드에서 좌석 조건 하나만 바꾼 결과
  try { const ab = await abCard(D); if (ab) cards.unshift(ab); } catch (e) { }
  // 변칙 상황 예측표 — anomaly_scenarios × 시드 묶음 (band.py). 평상시 대비 차이 · 흔들림 대비 · 같은 방향 횟수
  try {
    const ALLB0 = (await api("/api/bands")).filter(b => b.compare && b.compare.anomaly && b.date === date);
    // 10/14 — 지금 코드 · 입력 버전으로 돌린 묶음을 우선. 없으면 예전 계산을 쓰되 표 아래에 밝힌다
    const CUR = ALLB0.filter(b => b.model_ver === LIB.model_ver && b.input_ver === LIB.input_ver);
    // 10/16 v4.1 — 예전 모델 버전의 묶음은 섞지 않는다 (없으면 표를 띄우지 않음)
    const ALLB = CUR, OLDB = false;
    // 같은 기준(이 날의 조정값 − 변칙 · 시드)에서 돌린 줄만. 없으면 v4 기본(순서 섞기 포함) 기준 → 그것도 없으면 있는 것 중 가장 많은 기준
    // 주말 · 공휴일에는 평일 전용 조정값(wd_day 등)이 계산에 쓰이지 않으므로 비교 기준에서도 뺀다 (10/14)
    const wdOff = !isWeekday(date);
    const sig = t => JSON.stringify(Object.entries(t || {}).filter(([k, v]) => !["anomaly", "anomaly_k", "seed"].includes(k) && !(wdOff && WEEKDAY_ONLY.includes(k)) && v != null && v !== 0 && v !== false).sort());
    const groups = {};
    ALLB.forEach(b => (groups[sig(b.theta)] = groups[sig(b.theta)] || []).push(b));
    const want = [sig(Object.assign({}, D.theta || {})), sig(v4For(date))];
    const gk = want.find(k => groups[k]);   // 10/16 — 이 날의 조정값 또는 기본 모델과 같은 기준으로 돌린 묶음만 (다른 기준을 끌어오지 않음)
    const BS = gk ? groups[gk] : [];
    if (BS.length) {
      const AN = Object.fromEntries((LIB.anomalies || []).map(a => [String(a.ID), a]));
      const f = v => Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : (+v).toFixed(Math.abs(v) < 10 ? 2 : 1);
      const rows = BS.sort((a, b) => a.compare.anomaly - b.compare.anomaly).map(b => {
        const a = AN[String(b.compare.anomaly)] || {}, E = b.effect;
        const rev = E["순매출 (억)"];
        const moves = Object.entries(E).filter(([n]) => / 이용 \(명\)$/.test(n)).sort((x, y) => Math.abs(y[1].diff) - Math.abs(x[1].diff)).slice(0, 3);
        const strong = e => sureEffect(e, b.seeds);
        return `<tr class="click" data-key="${esc(b.compare_key)}"><td><b>${esc(a.이름 || "변칙 " + b.compare.anomaly)}</b>${b.compare.anomaly_k ? ` ×${b.compare.anomaly_k}` : ""}<div class="hint">크기 ${esc(a.등급 || "△")} · ${esc((a["크기 출처 (signal_stats · 문서)"] || "").split(" — ")[0].replace(/한호님 · /g, "").replace(/ \(한호님\)/g, ""))}</div></td>
          <td class="n" style="color:${rev.diff < 0 ? "var(--neg)" : "var(--pos)"}">${rev.diff > 0 ? "+" : ""}${f(rev.diff)}억<div class="hint">95% 구간 ${f(rev.lo95)} ~ ${f(rev.hi95)}</div></td>
          <td class="n">${(() => { const t = E["공급 제한 겪은 팀 (팀)"]; return t ? `<span style="${strong(t) ? "font-weight:700" : ""}">${t.diff > 0 ? "+" : ""}${Math.round(t.diff)}팀</span><div class="hint">${Math.round(t.lo95)} ~ ${Math.round(t.hi95)}</div>` : "-"; })()}</td>
          <td>${moves.map(([n, e]) => `<span class="mv ${strong(e) ? "strong" : ""}">${esc(n.replace(" 이용 (명)", ""))} ${e.diff > 0 ? "+" : ""}${Math.round(e.diff)} 인 · 회</span>`).join(" ")}</td></tr>`;
      }).join("");
      cards.push({ id: "anom", loc: null, wide: true, h: `<h5>이런 일이 생기면 하루가 어떻게 바뀌나? <span class="hint">(변칙 시나리오 · 평상시 대비 · 시드 ${BS[0].seeds}개 · 기준 ${gk === want[0] ? "이 날 조정값" : gk === want[1] ? "온톨로지 정합 v4" : "다른 조정값"})</span></h5>
        <table class="t"><tr><th>상황</th><th class="n">체류 매출</th><th class="n">공급 제한 겪은 팀</th><th>손님이 가장 크게 옮긴 곳</th></tr>${rows}</table>${OLDB ? `<div class="hint" style="color:var(--neg)">지금 코드 · 입력 버전으로 다시 돌린 묶음이 없어 예전 계산을 보여 줍니다.</div>` : ""}
        <div class="hint">줄을 누르면 그 상황의 하루로 넘어갑니다. 굵은 이동은 같은 시드끼리 짝지은 차이의 95% 구간이 0을 넘지 않고 거의 매번 같은 방향인 것입니다. 변화 크기는 아직 가정(△)이라 방향과 손님이 옮겨 가는 곳을 먼저 읽습니다. 공개 통계가 들어오면 크기를 바꿉니다.</div>` });
    }
  } catch (e) { }
  // 2. 와인페어 효과
  if (W && N) {
    const [w, n] = await Promise.all([ensureDay(W.key), ensureDay(N.key)]);
    const diff = (w.total - n.total) / 1.1;
    const keys = [...new Set([...Object.keys(w.by_l3), ...Object.keys(n.by_l3)])];
    const rows = keys.map(k => [k, (w.by_l3[k] || 0) - (n.by_l3[k] || 0)]).filter(r => Math.abs(r[1]) >= 1e6).sort((a, b) => b[1] - a[1]);
    const mx = Math.max(...rows.map(r => Math.abs(r[1])));
    cards.push({ id: "wf", loc: "FOREST_PARK", h: `<h5>와인페어를 하면 어디가 바빠지나?</h5><div class="big" style="color:${diff >= 0 ? "var(--pos)" : "var(--neg)"}">${diff >= 0 ? "+" : ""}${eok(diff)}</div><div class="hint">L1 순매출 ${pct(w.total - n.total, n.total) >= 0 ? "+" : ""}${pct(w.total - n.total, n.total)}% · 손님 ${w.n - n.n >= 0 ? "+" : ""}${w.n - n.n}팀</div>` +
      rows.slice(0, 5).map(([k, v]) => bar(k, Math.abs(v), mx, `${v >= 0 ? "+" : "−"}${(Math.abs(v) / 1.1 / 1e4).toFixed(0)}만`, v >= 0 ? "var(--pos)" : "var(--neg)")).join("") });
  } else if (wfMismatch) {
    cards.push({ id: "wfx", soft: true, h: `<h5>와인페어를 하면 어디가 바빠지나?</h5><div class="big" style="color:var(--muted)">비교 불가</div><div class="hint">이 날짜의 '와인페어 있음' 과 '행사 없음' 계산이 서로 다른 모델 · 입력 버전이거나 조정값이 달라 차이를 보여 주지 않습니다. 지금 기준(${esc(LIB.model_ver)} / ${esc(LIB.input_ver)})으로 같은 조정값에서 두 조건을 다시 계산하면 나옵니다. 위 '와인페어 진행' 칩이 그 계산을 합니다.</div>` });
  } else if (LIB.dates.find(x => x.date === date && x.fair)) {
    cards.push({ id: "wf0", soft: true, h: `<h5>와인페어를 하면 어디가 바빠지나?</h5><div class="big" style="color:var(--muted)">[둘 다 돌려야]</div><div class="hint">같은 날을 행사 없음 · 와인페어 있음으로 각각 돌려 두면 늘어난 몫이 업장별로 나뉘어 나옵니다.</div>` });
  }
  // 3. 저녁에 먼저 차는 식당
  const din = Object.entries(vd).map(([loc, v]) => { const ws = v.windows.filter(w => w.kind === "석식" && !w.name.includes("익일")); const p = Math.max(0, ...ws.map(w => w.peak_pct || 0)); return [loc, p, ws.reduce((a, w) => a + w.over_persons, 0)]; }).filter(r => r[1] > 0).sort((a, b) => b[1] - a[1]);
  if (din.length) cards.push({ id: "din", loc: din[0][0], h: `<h5>저녁에 어느 식당이 먼저 차나?</h5><div class="big">${esc(locName(din[0][0]))} ${din[0][1]}%</div>` +
    din.slice(0, 6).map(([loc, p, o]) => bar(locName(loc), p, 100, `${p}%${o ? " · 초과 " + o + "명" : ""}`, p >= 95 ? "var(--neg)" : p >= 75 ? "#e0552b" : "var(--k-facility)")).join("") + `<div class="hint">석식 회차 중 가장 높은 점유율 · 좌석 × 회차 대비</div>` });
  // 4. 객실 · 손님 구성
  const l2 = D.by_l2 || {};
  cards.push({ id: "room", loc: "GRAND_ROOM", h: `<h5>이 날 객실과 손님은?</h5><div class="big">${D.n_guest}팀 투숙</div>` +
    bar("ROOM 객실", l2.ROOM || 0, D.total, eok((l2.ROOM || 0) / 1.1), "var(--k-room)") + bar("F&B 식음", l2["F&B"] || 0, D.total, eok((l2["F&B"] || 0) / 1.1), "var(--k-meal)") + bar("LEISURE", l2["레저"] || 0, D.total, eok((l2["레저"] || 0) / 1.1), "var(--k-facility)") +
    `<div class="hint">비투숙 ${D.n - D.n_guest}팀 · 전체 ${D.persons.toLocaleString()}명 · 가동률은 주말 공급 상한(객실 875실)에 걸립니다</div>` });
  // 5. 미리 돌려 둔 조건 변경 (문서)
  cards.push({ id: "doc", soft: true, h: `<h5>조건을 바꾸면? (미리 돌려 둔 결과)</h5><div style="font-size:12px;line-height:1.7">더뷔페 평일 하루 휴업 → 식음 −33% · 전체 −14%<br>좌석 점유율 55%로 → 식음 −23%<br>평일 젊은 층 10% 할인 → −280 ~ +2,080만 원 (새 손님 0~50팀)</div><div class="hint">민감도 실험 · 평일 젊은 층 프로모션 실험에서 미리 돌린 값<span class="dev"> — docs/시드_10회_병목지도 · 민감도_첫_판 · 평일 젊은 층 프로모션 문서</span></div>` });
  // 6. 정원
  cards.push({ id: "cap", soft: true, h: `<h5>숲 체험 · 와인페어 정원은 채워지나?</h5><div class="big" style="color:var(--muted)">[정원 자료 필요]</div><div class="hint">프로그램별 정원 · 회차가 들어오면 "수용 가능 대비 몇 %"로 보여 줍니다. 지금은 식당 좌석만 셉니다.</div>` });
  h += `<div class="ask-grid">${cards.map(c => `<div class="qcard ${c.soft ? "soft" : ""} ${c.wide ? "wide" : ""} ${ASKSEL === c.id ? "on" : ""}" data-id="${c.id}" data-loc="${c.loc || ""}">${c.h}${c.loc ? `<div class="hint" style="color:var(--red)">업장 패널에서 왜 그런지 보기 →</div>` : ""}</div>`).join("")}</div>`;
  el.innerHTML = h;
  $$("#askView tr.click[data-key]").forEach(e => e.onclick = ev => { ev.stopPropagation(); setMode("day"); loadDay(e.dataset.key); });
  $$("#askView [data-abday]").forEach(e => e.onclick = ev => { ev.stopPropagation(); setMode("day"); loadDay(e.dataset.abday); });
  $$("#askView .qcard[data-loc]").forEach(e => e.onclick = () => { if (!e.dataset.loc) return; ASKSEL = e.dataset.id; $$("#askView .qcard").forEach(x => x.classList.toggle("on", x === e)); placePanel(e.dataset.loc); });
}

function compareCard(D, O) {
  const el = $("#cmp"); if (!el) return;
  const [W, N] = D.scenario === "winefair" ? [D, O] : [O, D];
  const keys = [...new Set([...Object.keys(W.by_l3), ...Object.keys(N.by_l3)])];
  const rows = keys.map(k => [k, (W.by_l3[k] || 0) - (N.by_l3[k] || 0)]).filter(r => Math.abs(r[1]) >= 5e5).sort((a, b) => b[1] - a[1]);
  const diff = W.total - N.total;
  const mx = Math.max(1, ...rows.map(r => Math.abs(r[1])));
  el.innerHTML = `<h4>와인페어 있음 − 행사 없음 (같은 날 · 같은 규모)</h4>
    <div style="font-size:12px;margin-bottom:6px">결제액 <b>${diff >= 0 ? "+" : ""}${eok(diff)}</b> (${(diff / N.total * 100).toFixed(1)}%) · 손님 ${W.n - N.n >= 0 ? "+" : ""}${W.n - N.n}팀 · 전환 ${W.n_switch - N.n_switch >= 0 ? "+" : ""}${W.n_switch - N.n_switch}건</div>
    <div class="why">${rows.slice(0, 10).map(([k, v]) => `<div class="r" style="grid-template-columns:1fr 80px 70px"><span>${esc(k)}</span><span><span class="b" style="display:block;width:${Math.abs(v) / mx * 100}%;background:${v >= 0 ? "var(--pos)" : "var(--neg)"};margin-left:${v >= 0 ? 0 : "auto"}"></span></span><span class="v" style="color:${v >= 0 ? "var(--pos)" : "var(--neg)"}">${v >= 0 ? "+" : ""}${(v / 1e4).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}만</span></div>`).join("")}</div>
    <div class="hint">하루(체크인 날) 기준이라 행사 사흘 합계와는 숫자가 다릅니다. 50만 원 미만 차이는 뺐습니다.</div>`;
}

function compareGeneric(id, A, B, title, hint) {
  const el = $("#" + id); if (!el) return;
  const keys = [...new Set([...Object.keys(A.by_l3), ...Object.keys(B.by_l3)])];
  const rows = keys.map(k => [k, (A.by_l3[k] || 0) - (B.by_l3[k] || 0)]).filter(r => Math.abs(r[1]) >= 5e5).sort((a, b) => b[1] - a[1]);
  const diff = A.total - B.total; const mx = Math.max(1, ...rows.map(r => Math.abs(r[1])));
  const va = A.venue_detail || {}, vb = B.venue_detail || {};
  const prow = Object.keys(va).filter(l => (va[l].parties || vb[l] && vb[l].parties)).map(l => [l, (va[l].persons_day || 0) - ((vb[l] || {}).persons_day || 0), (va[l].over_persons || 0) - ((vb[l] || {}).over_persons || 0)]).filter(r => r[1] || r[2]);
  el.innerHTML = `<h4>${title}</h4>
    <div style="font-size:12px;margin-bottom:6px">결제액 <b>${diff >= 0 ? "+" : ""}${eok(diff)}</b> (${(diff / B.total * 100).toFixed(1)}%) · 전환 ${A.n_switch - B.n_switch >= 0 ? "+" : ""}${A.n_switch - B.n_switch}건</div>
    <div class="why">${rows.slice(0, 10).map(([k, v]) => `<div class="r" style="grid-template-columns:1fr 80px 70px"><span>${esc(k)}</span><span><span class="b" style="display:block;width:${Math.abs(v) / mx * 100}%;background:${v >= 0 ? "var(--pos)" : "var(--neg)"};margin-left:${v >= 0 ? 0 : "auto"}"></span></span><span class="v" style="color:${v >= 0 ? "var(--pos)" : "var(--neg)"}">${v >= 0 ? "+" : ""}${(v / 1e4).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}만</span></div>`).join("")}</div>
    ${prow.length ? `<table class="t" style="margin-top:6px"><tr><th>업장</th><th class="n">이용 (인 · 회)</th><th class="n">초과 수요 <span class="hint">(막힌 팀의 일행 수)</span></th></tr>${prow.map(([l, p, o]) => `<tr><td>${esc(locName(l))}</td><td class="n" style="color:${p > 0 ? "var(--pos)" : p < 0 ? "var(--neg)" : ""}">${p > 0 ? "+" : ""}${p}</td><td class="n" style="color:${o < 0 ? "var(--pos)" : o > 0 ? "var(--neg)" : ""}">${o > 0 ? "+" : ""}${o}</td></tr>`).join("")}</table>` : ""}
    <div class="hint">${hint} 50만 원 미만 차이는 뺐습니다.</div>`;
}

// 하루 손님을 열면 왼쪽 설정도 그 손님으로 맞춘다 (조금 바꿔 다시 돌려 볼 수 있게)
async function fillForm(p, scenario) {
  $("#fDate").value = p.start.slice(0, 10); $("#fScenario").value = scenario || "none";
  setGuest(p.is_guest);
  if (p.is_guest) { $("#fProp").value = p.property; $("#fNights").value = Math.min(3, p.nights); }
  $("#fParty").value = Math.min(6, p.party); $("#fKids").checked = p.kids;
  if (p.sex) $("#fSex").value = p.sex; if (p.age) $("#fAge").value = p.age; if (p.purpose) $("#fPurpose").value = p.purpose;
  $("#fArrive").value = p.start.slice(11, 16); if (p.depart) $("#fDepart").value = p.depart; if (p.wake) $("#fWake").value = p.wake;
  $("#fPrefer").value = p.prefers.length ? p.prefers[0] : "";
  $("#fArrival").value = p.arrival || "";
  syncForm(); $("#fWf").checked = p.booked.includes("FOREST_PARK");
  await refreshPackages(); refreshCrowd();
  if (p.package && [...$("#fPackage").options].some(o => o.value === p.package)) { $("#fPackage").value = p.package; pkgHint(); }
  else if (p.is_guest) $("#fPackage").value = "none";
}

// 10/14 운영 요약 카드 → 숫자를 만든 실제 손님 기록으로 내려가기 (리뷰 피드백: '설명으로 이동' 과 '기록으로 이동' 둘 다)
// 정산은 check_flow.py (손님 상세 기록만 다시 읽어 시도 · 고유 식사 건 · 최종 상태를 세고 하루 결과와 맞는지 확인) 결과를 쓴다
const FLOWCACHE = {};
async function flowOf(key) { if (!FLOWCACHE[key]) FLOWCACHE[key] = await api("/api/day/flow?key=" + encodeURIComponent(key)); return FLOWCACHE[key]; }
function locOfLabel(label) { const w = String(label || "").split(" ")[0]; return Object.keys((DAY && DAY.venue_detail) || {}).find(l => locNames(l).some(n => n.split(" ")[0] === w || n === w || n.replace(/\s/g, "") === w.replace(/\s/g, ""))) || null; }
function flowChecks(F) { return F.checks ? `<div class="hint">정산 검증 ${F.ok ? "통과" : "실패"} — ${F.checks.map(c => `${c.ok ? "✓" : "✗"} ${esc(outName(c.name))}`).join(" · ")}</div>` : ""; }
// 10/15 읽기 흐름 — '왜 이 회차에 몰리나': 혼잡 수치 → 회차 조건 → 적용된 가정 → 근거의 한계 → 확인할 자료 (조식처럼 회차가 갈린 식사만)
function whyCrowd(from, loc) {
  const kind = (String(from).match(/조식|중식|석식/) || [])[0];
  const v = loc && DAY && DAY.venue_detail && DAY.venue_detail[loc];
  if (!kind || !v) return "";
  const ws = v.windows.filter(w => w.kind === kind && (w.persons || w.over_persons));
  if (ws.length < 2) return "";
  const cap = v.cap;
  const rows = ws.map(w => `${esc(w.name.replace(" (익일)", ""))} ${w.t0.slice(6)}~${w.t1} · 착석 ${w.persons}명(좌석 ${cap}석 대비 ${Math.round(w.persons / cap * 100)}%)${w.over_persons ? ` · 초과 수요 ${w.over_persons}명(막힌 팀의 일행 수 · 처음 막힌 회차)` : " · 여유"}`).join("<br>");
  const asm = kind === "조식"
    ? `<li>손님 기상 시각은 30분 단위 여섯 칸(06:30~09:00)으로 만든 임시값입니다(△). 1부가 끝난 뒤 준비를 마친 손님이 모두 2부 시작 시각에 줄을 서는 모양이 여기서 생깁니다.</li>`
    : "";
  return `<div class="card why"><h4>왜 이 회차에 몰리나</h4>` +
    `<div class="whys"><b>회차 조건</b><div>${rows}</div></div>` +
    `<div class="whys"><b>적용된 가정</b><ul>${asm}<li>회차 안 줄 서기는 30분을 넘으면 포기합니다(△ 후기 1편). 조식이 객실 상품에 포함된 손님도 같은 규칙을 받습니다.</li><li>좌석은 회차가 끝날 때까지 잡습니다(회차제 · 조정값).</li></ul></div>` +
    `<div class="whys"><b>근거의 한계</b><div>'${kind === "조식" ? "1부는 남고 2부에 몰린다" : "특정 회차에 몰린다"}' 는 모델 안에서 일관되게 나오지만, 몰리는 시각과 줄을 포기하는 시간은 실제 기록으로 확인되지 않았습니다.</div></div>` +
    `<div class="whys"><b>확인할 자료</b><div>${esc(locName(loc))} ${kind} 회차별 입장 인원 · 대기 시간 · 포기 비율 (약한 고리 2 · 3순위)</div></div>` +
    `<a class="rlink" id="toWeak">약한 고리와 확인할 자료 (판단 근거 ⑦) →</a></div>`;
}
// 10/17 리뷰 4 — key 를 받으면 그 하루(같은 날짜 · 시드 · 입력 · 모델)를 연 뒤 같은 집합을 다시 만든다. 운영 요약 순위의 고유 팀 수와 맞는지 화면에 적는다
async function showConstrained(from, key, all) {
  if (key && (!DAY || DAY.key !== key)) await loadDay(key);
  if (!DAY) return;
  if (MODE !== "day") setMode("day");
  const F = await flowOf(DAY.key);
  if (F.error) { $("#panel").innerHTML = `<div class="callout">${esc(F.error)}</div>`; return; }
  const ev = (F.events || []).filter(e => e.from === from);
  const byTeam = {}; ev.forEach(e => { (byTeam[e.idx] = byTeam[e.idx] || []).push(e); });
  const teams = Object.entries(byTeam).map(([i, es]) => ({ i: +i, es, g: (DAY.guests || [])[+i] || {} }));
  const fin = {}; teams.forEach(t => { const f = t.es.find(e => e.final && !e.repeat) || t.es[0]; const k = f.final || `다른 행동 (${altName(f.to)})`; fin[k] = (fin[k] || 0) + 1; });
  const loc = locOfLabel(from);
  const rk = ((DAY.switch || {}).by_from || []).find(r => r.from === from);
  const same = rk && rk.teams === teams.length && rk.events === ev.length && F.key === DAY.key && (!F.model_ver || F.model_ver === DAY.model_ver);
  let h = `<button class="back" id="backDay">← 하루 전체로</button><div class="card"><h4 style="font-size:16px">${esc(nmDisp(from))}에서 좌석 제약을 경험한 ${teams.length}팀 <span class="hint">(고유 팀)</span></h4>` +
    `<div class="setbasis"><span>${esc(DAY.date.slice(5).replace("-", "/"))} · 시드 ${(DAY.theta || {}).seed || 0} · 모델 ${esc(DAY.model_ver || "-")} · 입력 ${esc(DAY.input_ver || "-")}</span>` +
    (rk ? `<span class="${same ? "ok" : "bad"}">${same ? `운영 요약 순위와 같은 집합 · 고유 팀 ${rk.teams} · 선택 기준 ${rk.events}건` : `운영 요약 순위와 다름 · 순위 ${rk.teams}팀 / 이 목록 ${teams.length}팀`}</span>` : "") + `</div>` +
    `<div class="hint">점수가 더 높았던 ${esc(nmDisp(from))}이 만석 · 대기로 후보에서 빠진 일이 한 번 이상 있는 고유 팀입니다 (선택 기준 ${ev.length}건). 자리가 있었으면 반드시 갔다는 뜻은 아닙니다.</div>` +
    `<table class="t" style="margin-top:8px"><tr><th>그 식사 · 시간대의 최종 상태</th><th class="n">팀</th></tr>${Object.entries(fin).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<tr><td>${esc(outName(k))}</td><td class="n">${n}</td></tr>`).join("")}</table>` +
    (loc ? `<button class="ghost wide" id="toVenue">${esc(locName(loc))} 회차별 점유율 보기</button>` : "") + flowChecks(F) + `</div>` + whyCrowd(from, loc);
  h += `<div class="card"><h4>팀 목록 <span class="hint">· 누르면 그 손님이 왜 그렇게 골랐는지</span></h4><table class="t"><tr><th>손님</th><th>시각</th><th>대신 고른 곳 → 최종</th></tr>` +
    teams.slice(0, all ? teams.length : 80).map(t => { const e = t.es[0], g = t.g;
      return `<tr class="click" data-i="${t.i}"><td>${g.is_guest ? (PROPS[g.property] || "") + " " + g.nights + "박" : "비투숙"} · ${g.party}인${g.kids ? " · 아이" : ""}<br><span class="hint">${esc(g.purpose || "")}</span></td><td class="n">${esc(String(e.t).slice(11, 16))}</td><td style="font-size:11.5px">${esc(altName(e.to))}${e.final ? `<br><span class="hint">→ ${esc(e.final_at || e.final)}</span>` : ""}${t.es.length > 1 ? ` <span class="hint">(${t.es.length}번)</span>` : ""}</td></tr>`; }).join("") +
    `</table>${teams.length > 80 && !all ? `<button class="ghost wide" id="consAll">나머지 ${teams.length - 80}팀 더 보기 (모두 ${teams.length}팀)</button>` : ""}</div>`;
  $("#panel").innerHTML = h;
  $("#backDay").onclick = () => showDay(DAY);
  if (loc) $("#toVenue").onclick = () => placePanel(loc);
  if ($("#toWeak")) $("#toWeak").onclick = () => goWeak();
  if ($("#consAll")) $("#consAll").onclick = () => showConstrained(from, null, true);
  $$("#panel tr.click[data-i]").forEach(r => r.onclick = () => openDayGuest(+r.dataset.i, () => showConstrained(from, null, all)));
}
// 10/15 G1 — 이용이 제한된 식사 최종 상태를 투숙 · 비투숙으로 나눈다 (고유 식사 건 · 식사 기준 분모).
// 모델의 '식당 외 식사(호텔 밖 · 객실)' 는 객실 키가 있어야 고를 수 있어 비투숙 손님에게는 없다 → 두 줄의 차이는 선호가 아니라 선택지 구성 차이
const STAY_NOTE = "객실에서 먹기는 객실 이용 자격이 있어야 하지만, 호텔 밖에서 먹기는 비투숙 손님도 당연히 할 수 있습니다. 그런데 모델은 이 둘을 '식당 외 식사' 한 선택지로 묶고 객실 키가 있어야 고르게 만들어, 비투숙 손님은 막히면 다른 호텔 식당 · 포장 · 기록 없음 중에서만 갈립니다. 그래서 투숙 · 비투숙의 차이는 선호 차이가 아니고, 근거가 모자라서라기보다 선택지를 정의한 모델 구조에서 나옵니다.";
function flowByStay(F, D) {
  const out = { 투숙: {}, 비투숙: {} }, n = { 투숙: 0, 비투숙: 0 };
  const G = (D && D.guests) || [];
  for (const e of (F && F.events) || []) {
    if (!e.final || e.repeat || !G[e.idx]) continue;
    const k = G[e.idx].is_guest ? "투숙" : "비투숙";
    out[k][e.final] = (out[k][e.final] || 0) + 1; n[k]++;
  }
  return { out, n };
}

async function showFlow() {
  if (!DAY) return;
  if (MODE !== "day") setMode("day");
  const F = await flowOf(DAY.key);
  if (F.error) { $("#panel").innerHTML = `<div class="callout">${esc(F.error)}</div>`; return; }
  const OUT = F.outcome || {};
  let h = `<button class="back" id="backDay">← 하루 전체로</button><div class="card"><h4 style="font-size:16px">이용이 제한된 식사 ${F.cases}건은 어디로 갔나</h4>` +
    `<div class="hint">공급 제한으로 식사 후보가 빠진 경우를 고객팀 · 날짜 · 식사 시간대마다 한 번 세었습니다 (같은 식사 시간대에 여러 번 막힌 시도까지 세면 ${F.attempts}건). 최종 상태는 같은 식사 시간대에 결국 먹은 곳입니다.</div>` +
    (() => { const S = flowByStay(F, DAY);
      return `<table class="t" style="margin-top:8px"><tr><th>최종 상태</th><th class="n">건</th><th class="n">비율</th><th class="n">투숙 ${S.n.투숙}건</th><th class="n">비투숙 ${S.n.비투숙}건</th></tr>${Object.entries(OUT).map(([k, n]) => `<tr><td>${esc(outName(k))}</td><td class="n">${n}</td><td class="n">${pct(n, F.cases)}%</td><td class="n">${pct(S.out.투숙[k] || 0, S.n.투숙)}%</td><td class="n">${k === "호텔 밖 · 객실 식사" ? `<span class="hint">선택지 없음</span>` : pct(S.out.비투숙[k] || 0, S.n.비투숙) + "%"}</td></tr>`).join("")}</table>` +
        `<div class="callout warn" style="margin-top:8px"><b>읽을 때 주의</b> · ${STAY_NOTE} 후기에서 막혀서 다른 유료 호텔 식당으로 간 사례는 0건이지만, 실제로 막혀 포기한 후기가 2편뿐이라 '전환하지 않는다'는 증거가 아니라 관찰할 표본이 부족하다는 뜻입니다.</div>`; })() +
    `${flowChecks(F)}</div>`;
  h += `<div class="card"><h4>막힌 곳 → 최종으로 먹은 곳 <span class="hint">· 업장을 누르면 그 팀들</span></h4><table class="t"><tr><th>막힌 곳</th><th>최종</th><th class="n">건</th></tr>` +
    Object.entries(F.flow || {}).map(([o, c]) => Object.entries(c).map(([w, n], j) => `<tr${j ? "" : ` class="click" data-from="${esc(o)}"`}><td>${j ? "" : `<b>${esc(o)}</b>`}</td><td>${esc(outName(w))}</td><td class="n">${n}</td></tr>`).join("")).join("") + `</table></div>`;
  $("#panel").innerHTML = h;
  $("#backDay").onclick = () => showDay(DAY);
  $$("#panel tr.click[data-from]").forEach(r => r.onclick = () => showConstrained(r.dataset.from));
}
async function openDayGuest(i, back) {
  const det = await api(`/api/day/guest?key=${encodeURIComponent(DAY.key)}&idx=${i}`);
  det._crowd = DAY.key; det._idx = i;
  det._back = back || null;
  setMode("guest");
  showGuest(det);
  fillForm(det.persona, det.scenario).then(() => { setSrc("custom"); $("#fCrowd").value = DAY.key; crowdHint(); personaCard(); });
}

const HILLINK_APP_READY = init().catch(e => { document.body.insertAdjacentHTML("afterbegin", `<div class="callout">시작 실패: ${esc(e.message)}</div>`); });
stayLoad();

// ---------------------------------------------------------------------------
// 10/18 UX 18차(연구 연결) · 손님 한 팀 ↔ 판단 근거 왕복 (판단근거_핵심발견_증거연결_1018.md v5 4절)
//   식별자 = 체류 ID(blog) + 실행 ID(run · 화면은 늘 run 0 = revenue.SEED+0) + 행동 순번(step i) + 행동 키. 시각은 보조 표시.
//   그 실행에 그 행동이 없으면 다른 실행을 만들어 보이지 않고 '이 실행에서는 선택되지 않음' 으로만 표시한다.
// ---------------------------------------------------------------------------
let EV_RETURN = null;      // 판단 근거에서 넘어온 뒤 '돌아가기' 표시용 { stay, run, key }
function reviewIndexOf(stay) { const RL = LIB.review_list || []; let i = RL.findIndex(r => r.blog === stay && !r.alt); if (i < 0) i = RL.findIndex(r => r.blog === stay); return i; }
async function openReviewStay(stay, run, key) {
  const i = reviewIndexOf(stay);
  if (i < 0) { alert(`후기 목록에 ${stay} 가 없습니다`); return; }
  if (run !== 0) { console.warn("손님 한 팀 화면은 실행 run 0 만 만든다 — 요청 run", run); }
  EV_RETURN = { stay, run: 0, key };
  setMode("guest"); setSrc("blog");
  $("#fReview").value = String(i); reviewInfo(); personaCard(); sitSync();
  await runSim("rev");
  if (!G || !G.review || G.review.blog !== stay) return;
  const si = G.st.findIndex(s => s.key === key);
  if (si >= 0) { selectStep(si); }
  else {
    renderPanel();
    const v = (G.review.visited || []).find(x => x.loc === keyPlace(key));
    const p = v && v.p != null ? ` · 화면 난수 12회 중 ${Math.round(v.p * 100)}% 에서 그 장소에 감` : "";
    $("#panel").insertAdjacentHTML("afterbegin", `<div class="callout rx-none"><b>이 실행(run 0)에서는 '${esc(keyName(key))}' 이 선택되지 않았습니다</b>${esc(p)}<br><span class="hint">다른 실행의 행동을 만들어 보이지 않습니다. 선택 비율은 판단 근거의 색인(research_index.json) 과 12회 평균을 보세요.</span></div>`);
  }
}
const KEY_PLACE = { pizza: "PIZZA_HILL", pizza_to: "PIZZA_HILL", buffet_b: "THE_BUFFET", buffet_l: "THE_BUFFET", buffet_d: "THE_BUFFET", moegi: "MOEGI", geum: "GEUMRYONG", myong: "MYONGWOLGWAN", ondal: "ONDAL", lepassage: "LE_PASSAGE", pavilion: "THE_PAVILION", lux: "LUX_BAR", skyard: "SKYARD", library: "GRAND_LIBRARY", sauna: "WELLNESS_SAUNA", forest: "FOREST_PARK", winefair: "FOREST_PARK", river: "RIVERPARK", theatre: "THEATRE_OF_LIGHT" };
function keyPlace(key) { return KEY_PLACE[key] || null; }
function keyName(key) { const NM = { pizza_to: "피자힐 포장", pizza: "피자힐", buffet_b: "더뷔페 조식", buffet_d: "더뷔페 석식", meal_other: "식당 외 식사", moegi: "모에기", skyard: "스카이야드", pool: "실내수영장", library: "라이브러리", sauna: "사우나" }; return NM[key] || key; }
// 손님 한 팀 → 판단 근거: 지금 선택한 행동(step) 을 들고 판단 근거의 '이 행동의 판단 근거' 패널로
function evShowAction(i) {
  const s = G.st[i]; if (!s) return;
  const stay = G.review && G.review.blog ? G.review.blog : (G._req && G._req.blog) ? String(G._req.blog) : "custom";   // 17차 마무리 세션 지적: 손님 이름 전체가 주소에 들어가지 않게 — 후기 손님은 blog 번호 · 격자 · 직접 만든 손님은 custom
  EV_ACTION.cur = { stay, run: 0, stepIdx: i, key: s.key, t: `${dlabel(s.a)} ${hhmm(s.a)}`, step: s, review: G.review || null };
  location.hash = `evidence?stay=${encodeURIComponent(stay)}&run=0&step=${i}&key=${encodeURIComponent(s.key)}`;
  if (typeof EV !== "undefined") EV.view = "find";   // 19차b — 행동 패널은 '핵심 발견' 화면 맨 위
  setMode("evidence");
}
function backToGuestStep(A) {
  if (!A) return;
  EV_RETURN = { stay: A.stay, run: 0, key: A.key };   // 19차b — 돌아온 동선에도 '← 판단 근거로' 줄을 남겨 왕복을 이어 간다
  if (G && G.st && G.st[A.stepIdx] && G.st[A.stepIdx].key === A.key && (A.stay === "custom" || (G.review ? G.review.blog === A.stay : String((G._req || {}).blog || "") === A.stay))) { setMode("guest"); selectStep(A.stepIdx); location.hash = `oneteam?stay=${encodeURIComponent(A.stay)}&run=0&step=${A.stepIdx}&key=${encodeURIComponent(A.key)}`; return; }
  openReviewStay(A.stay, 0, A.key);
}
function evReturnBar() {
  if (!EV_RETURN) return "";
  return `<div class="rx-ret"><span>판단 근거에서 왔습니다 · ${esc(EV_RETURN.stay)} · run 0</span><button class="rv-btn" id="rxRet">← 판단 근거로</button></div>`;
}
function bindReturnBar() { const b = $("#rxRet"); if (b) b.onclick = () => { setMode("evidence"); }; }
// 처음 열 때 해시로 들어온 경우 (#oneteam?stay=..&key=.. · #evidence?stay=..&key=..)
async function applyHashRoute() {
  const h = location.hash.replace(/^#/, ""); if (!h) return;
  const [path, q] = h.split("?"); const P = new URLSearchParams(q || "");
  if (path === "oneteam" && P.get("stay")) await openReviewStay(P.get("stay"), +(P.get("run") || 0), P.get("key") || "");
  else if (path === "evidence" && P.get("stay") && P.get("key")) { await openReviewStay(P.get("stay"), 0, P.get("key")); const k = P.get("key"), si = P.get("step"); let i = si != null && G && G.st && G.st[+si] && G.st[+si].key === k ? +si : (G && G.st ? G.st.findIndex(s => s.key === k) : -1); if (i >= 0) evShowAction(i); }
  else if (/^evidence(\/(find|bench|detail))?$/.test(path)) { if (typeof EV !== "undefined") EV.view = path.split("/")[1] || "find"; setMode("evidence"); }   // 19차b 세 화면 직접 진입
}

// P6 — 가운데점(·) 앞 줄바꿈 방지: 'A · B' 의 앞 공백을 줄바꿈 없는 공백으로 바꿔 줄 첫머리에 '· 동행' 처럼 점이 오지 않게 한다(표시 텍스트만 · 자료는 그대로)
(() => {
  const RX = / · /g, NB = " · ";
  const fix = root => { const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => n.nodeValue.includes(" · ") && !(n.parentElement && n.parentElement.closest("script,style,textarea,input,option")) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
    const L = []; let n; while ((n = tw.nextNode())) L.push(n); L.forEach(t => { t.nodeValue = t.nodeValue.replace(RX, NB); }); };
  const mo = new MutationObserver(ms => { mo.disconnect(); for (const m of ms) { if (m.type === "characterData") { if (m.target.nodeValue.includes(" · ")) m.target.nodeValue = m.target.nodeValue.replace(RX, NB); } else m.addedNodes.forEach(x => { if (x.nodeType === 3) { if (x.nodeValue.includes(" · ")) x.nodeValue = x.nodeValue.replace(RX, NB); } else if (x.nodeType === 1) fix(x); }); } start(); });
  const start = () => mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  const go = () => { fix(document.body); start(); };
  if (document.body) go(); else document.addEventListener("DOMContentLoaded", go);
})();
