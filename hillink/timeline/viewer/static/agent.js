// 10/23 에이전트 한 명 · 여러 명 — 핵심 선택 턴(저녁)을 기존 지도 · 오른쪽 패널 · 드로어에 연결한다.
// 계산은 서버 /api/turn (turn_run.py → turn_view.py) 그대로. 화면은 엔진이 돌려준 값만 쓰고 연출용 점수를 만들지 않는다.
// 호텔 전체 시뮬레이션 · 좌석 · 대기 · 혼잡 표현 없음 — 같은 업장을 여러 에이전트가 골라도 서로 영향이 없다.
// 10/23 2차 · 기존 손님 한 팀 화면의 장소 사진(.gnow) · 지도 길(route · markerPath) · 위치 점(agentDot)을 다시 쓴다.
//   출발 위치는 시나리오 입력(투숙 건물 객실 / 비투숙 정문), 선택 장소는 엔진 결과, 둘 사이 선은 '표시용 연결'(이동 시간 · 경로를 계산하지 않음).
const AG = {
  meta: null, mode: "agent", one: null, many: new Set(["A02", "A04", "A05", "A07", "A10"]),
  cond: { turn: "day", event: false, stay: true, building: "VISTA", party_size: 2, pricing: "historical", product_levers: {} },
  duration: "stay_1", judgmentMode: 'rules',
  res: null, runs: [], ti: 0, sel: null, busy: false, keep: {},
  at: "turn", f: 1, raf: 0, open: new Set(),
  visits: null, fix: false,
  engine: (() => { try { return localStorage.getItem("wh_engine") === "legacy" ? "legacy" : "autonomy"; } catch (e) { return "autonomy"; } })(),   // CL-1024-22R — 고객 흐름의 행동 엔진(기본 autonomy_v1 · 기존 엔진은 개발 정보에서만 비교용)
  iv: "none", oneOverride: false, flow: null, visitRequest: null, visitData: null, visitDay: 1,   // 마지막 실행 및 방문 기간별 표시 상태
  // 10/24 보충2 — 여러 명: 투숙 · 건물 · 박수 · 체류 단계 · 동행은 고객이 정한다(visits). fix = 실험용 공통 조건 고정
};
const agIsMany = R => !!R && (R._mode === "agents" || R.customers.length > 1);
const agIsOne = R => !!R && !agIsMany(R);
const AG_TURN = { day: "방문", breakfast: "아침", event: "행사", dinner: "저녁" };
// 와인페어 — 기존 V1 월드 선택지 그대로(행사 턴 16:30). 가격 · 할인 · 포함 · 구성은 기존 프리셋 값을 운영자가 고른다
const AG_WINE = { product_id: "WINE_FAIR", label: "와인페어 입장(시음 + 푸드 교환권 1매)", venue_id: "FOREST", kind: "event", price_krw: 55000, party_basis: 1 };
const AG_WINE_VAR = [["standard", "기본 구성"], ["nonalc", "무알코올 대안 · 55,000"], ["pairing", "페어링 코스 · 90,000"], ["chef", "셰프 콜라보 · 120,000"]];   // 값은 그대로 · 표시 이름만 짧게(자세한 구성은 도움말)
// 아침 뷔페 — 공식 가격이 없어 운영자가 가격을 넣거나 '객실 포함' 으로 정할 때만 후보(엔진 turn_candidate 와 같은 규칙)
const AG_BUFFET = { product_id: "BREAKFAST_BUFFET", label: "조식 뷔페(더뷔페)", venue_id: "THE_BUFFET", kind: "single", price_krw: null, party_basis: 1 };
const AG_CLS = { common: "공통 계산", review: "후기 근거", assumption: "설계 가정", transfer: "맥락 이전 추론", out_of_scope: "출처 충돌" };
const agWon = v => (v == null ? "-" : Math.round(v).toLocaleString("ko-KR") + "원");
const agNum = v => (v == null ? "-" : (+v).toFixed(2));
const agVColor = v => (v === "ROOM_MEAL" || v === "ROOM" ? "var(--k-room)" : v === "FOREST" ? "var(--k-event)" : v === "SKYARD" ? "var(--k-facility)" : (typeof venColor === "function" && venColor(v)) || "var(--ink2)");
const agDot = v => `<i class="vdot" style="background:${agVColor(v)}" aria-hidden="true"></i>`;
const agShort = s => String(s || "").replace(/^(룸서비스|피자힐|호텔) /, "").replace(/\(더뷔페\)$/, "");
// CL-1024-14 A-2 — 메뉴 표시 이름: 업장 접두어를 떼고 옵션은 괄호 대신 ' - ' 로(표시 전용 · 상품 ID · 엔진 입력 그대로)
const agMenu = s => { const t = String(s || "").replace(/^(룸서비스|피자힐|호텔|르 ?파사쥬|명월관|온달|금룡|더뷔페|모에기|스카이야드|와인페어) /, "").replace(/\(더뷔페\)$/, "").trim();
  const m = t.match(/^(.*?)\s*\((.+)\)\s*$/); return m && m[1] ? `${m[1]} - ${m[2]}` : t; };
// CL-1024-14 A-1 — 장면 사진: 시설 · 식음은 그 장소 사진, 객실은 이 고객이 실제로 묵는 건물의 객실 사진일 때만(다른 건물 객실 사진은 쓰지 않음). 정문 · 이동은 사진 없음
function agSceneImg(sc, pid) {
  if (!sc || !sc.loc || typeof placeImg !== "function" || /HOTEL_GATE/.test(sc.loc)) return null;
  const m = sc.loc.match(/^([A-Z]+)_ROOM$/);
  if (m) { const V = AG.res ? agVC(pid, AG.res) : null; if (!V || !V.stay || V.B !== m[1]) return null; }
  return placeImg(sc.loc);
}
// 요지는 기존 구조화 사실의 표시값이며, 없거나 비어 있으면 새 설명을 만들지 않는다.
const agEvidenceText = (c, id) => {
  const text = c.evidence && c.evidence[id];
  return typeof text === "string" && text.trim() ? text : "설명 확인 필요";
};

// 얇은 선형 아이콘 — place_thumbs.js 와 같은 24 격자 · 선 1.6
const AG_ICON = {
  pizza: '<path d="M4 6.5C9 3.8 15 3.8 20 6.5L12 21z"/><path d="M5.6 9.2c4-1.8 8.8-1.8 12.8 0"/><circle cx="10" cy="12" r="1"/><circle cx="14" cy="14.5" r="1"/>',
  pasta: '<path d="M3.5 12h17a8.5 8.5 0 0 1-17 0z"/><path d="M8 12c0-3 2-5 4-5s4 2 4 5M10 12c0-1.8.9-3 2-3s2 1.2 2 3"/>',
  room: '<path d="M4 17h16M5.5 17a6.5 6.5 0 0 1 13 0M12 8.5V7M10.5 7h3"/><path d="M3 20h18"/>',
  set: '<ellipse cx="9" cy="13" rx="6" ry="3.2"/><ellipse cx="15" cy="10" rx="6" ry="3.2"/><path d="M3 13v1.6c0 1.8 2.7 3.2 6 3.2s6-1.4 6-3.2V13"/>',
  tag: '<path d="M3.5 12.5V4h8.5l8.5 8.5-8 8z"/><circle cx="8" cy="8.5" r="1.3"/>',
  gift: '<rect x="4" y="9" width="16" height="11" rx="1.5"/><path d="M3 9h18M12 9v11M12 9c-1.5-3.5-5.5-4-5.5-1.5S10 9 12 9zm0 0c1.5-3.5 5.5-4 5.5-1.5S14 9 12 9z"/>',
  people: '<circle cx="9" cy="8" r="3"/><path d="M3.5 19c.6-3.3 2.8-5 5.5-5s4.9 1.7 5.5 5"/><circle cx="16.5" cy="9" r="2.4"/><path d="M15.5 14.2c2.6-.3 4.6 1.3 5 4.8"/>',
};
const agIcon = (k, cls = "") => `<svg class="ag-ic ${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${AG_ICON[k] || AG_ICON.room}</svg>`;
// 10/24 09-B 구조화 도움말 — 무엇을 의미하나요? / 어떤 근거인가요?(실제 후기 · 추출 성향 · 운영 조건 · 추정 흐름) / 주의할 점
const noteH = (o, variant = "") => `<button type="button" class="nfo nt${variant === "flow" ? " nfo-flow-info" : ""}" data-note="${esc(o.what || "")}" data-nj="${esc(JSON.stringify(o))}"${variant === "flow" ? ` aria-expanded="false" aria-controls="agInfoPopover" aria-haspopup="dialog"` : ""} aria-label="설명" title="설명 보기">i</button>`;
let agInfoAnchor = null;
function agInfoPosition(pop) {
  if (!pop || !agInfoAnchor || !agInfoAnchor.isConnected) return;
  if (innerWidth <= 600) { pop.style.left="8px"; pop.style.right="8px"; pop.style.top="auto"; pop.style.bottom="max(8px, env(safe-area-inset-bottom))"; return; }
  pop.style.right="auto"; pop.style.bottom="auto";
  const a=agInfoAnchor.getBoundingClientRect(), w=pop.offsetWidth, h=pop.offsetHeight, gap=8;
  let x=a.right+gap;
  if(x+w>innerWidth-8) x=a.left-w-gap;
  x=Math.max(8,Math.min(x,innerWidth-w-8));
  let y=a.top;
  if(y+h>innerHeight-8) y=a.bottom-h;
  y=Math.max(8,Math.min(y,innerHeight-h-8));
  pop.style.left=`${x}px`; pop.style.top=`${y}px`;
}
function agInfoClose(restore=false) {
  const pop=document.getElementById("agInfoPopover"), anchor=agInfoAnchor;
  if(pop) pop.remove();
  document.querySelectorAll(".nfo-flow-info[aria-expanded='true']").forEach(b=>b.setAttribute("aria-expanded","false"));
  agInfoAnchor=null;
  if(restore && anchor && anchor.isConnected) anchor.focus();
}
function agInfoOpen(button, keyboard=false) {
  const old=document.getElementById("agInfoPopover");
  if(old && agInfoAnchor===button) { agInfoClose(false); return; }
  agInfoClose(false);
  let data={}; try { data=JSON.parse(button.dataset.nj||"{}"); } catch (_) {}
  const pop=document.createElement("section"); pop.id="agInfoPopover"; pop.className="nfo-pop nj ag-flow-pop";
  pop.setAttribute("role","dialog"); pop.setAttribute("aria-modal","false"); pop.setAttribute("aria-labelledby","agInfoTitle");
  const points=Array.isArray(data.points)&&data.points.length?`<ul>${data.points.slice(0,3).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:"";
  pop.innerHTML=`<div class="ag-flow-pop-head"><b id="agInfoTitle">${esc(data.title||"설명")}</b><button type="button" class="ag-flow-info-close" aria-label="설명 닫기">×</button></div><p>${esc(data.what||button.dataset.note||"")}</p>${points}${data.meta?`<small class="ag-flow-pop-meta">${esc(data.meta)}</small>`:""}${data.caution?`<small class="ag-flow-pop-meta">${esc(data.caution)}</small>`:""}`;
  document.body.appendChild(pop); agInfoAnchor=button; button.setAttribute("aria-expanded","true"); agInfoPosition(pop);
  pop.querySelector(".ag-flow-info-close").addEventListener("click",()=>agInfoClose(true));
  if(keyboard) pop.querySelector(".ag-flow-info-close").focus();
}
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest(".nfo-flow-info"); if(!b) return;
  e.preventDefault(); e.stopImmediatePropagation(); agInfoOpen(b,e.detail===0);
},true);
document.addEventListener("pointerdown",e=>{const p=document.getElementById("agInfoPopover");if(p&&!e.target.closest("#agInfoPopover,.nfo-flow-info"))agInfoClose(false);},true);
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&document.getElementById("agInfoPopover")){e.preventDefault();agInfoClose(true);}},true);
document.addEventListener("scroll",()=>agInfoPosition(document.getElementById("agInfoPopover")),true);
window.addEventListener("resize",()=>agInfoPosition(document.getElementById("agInfoPopover")));
function agCurrentEngineInfo() {
  const f=AG.flow||{}, r=f.result||{}, e=f.engine||r.engine||AG.visitData&&AG.visitData.engine||null;
  if(!f.ledger&&!e) return {label:"실행 후 확인",meta:"실행 전에는 엔진 버전과 모델 호출 여부가 아직 없습니다."};
  const version=e&&(e.version||e.name)||"버전 미기록", behavior=e&&e.behavior_engine;
  const label=f.ledger&&f.ledger.source==="stored_demo"?`저장 시연 · ${version}`:behavior==="m4"?`M4 · ${version}`:e&&e.name?`${e.name} · ${version}`:version;
  let calls="실제 호출 기록 없음";
  if(e&&Number.isInteger(e.llm_calls)) calls=`LLM 호출 ${e.llm_calls}회`;
  else { const backend=String(e&&(e.llm_backend||e.backend)||""); const m=backend.match(/LLM\s*호출\s*(\d+)/i); if(m) calls=`LLM 호출 ${m[1]}회`; else if(/rules|규칙/i.test(backend)) calls="규칙 기반 · 호출 횟수 미기록"; else if(/llm/i.test(backend)) calls="모델 호출 상태 미기록"; }
  return {label,meta:`${calls}${e&&e.seed!=null?` · 시드 ${e.seed}`:""}`};
}
const agProdIcon = p => p.kind === "set" ? "set" : /PIZZA/.test(p.product_id) ? "pizza" : /PASTA|SPAGHETTI/.test(p.product_id) ? "pasta" : "room";

async function agEnter(mode) {
  AG.mode = mode;
  { const m = document.getElementById("map"); if (m) { m.setAttribute("viewBox", "0 46 1000 540"); document.body.classList.add("ag-map-crop"); } }   // CL-12 §1 — 섬 그림의 위아래 빈 종이를 잘라 같은 비율로 크게(높이가 좁은 화면에서 약 15~20%)
  const sec = $(".mode-agent"); sec.classList.remove("hidden");
  if (!AG.meta) {
    sec.innerHTML = `<div class="g-scroll"><div class="hint" style="padding:12px 2px">불러오는 중…</div></div>`;
    try { AG.meta = await api("/api/turn/meta"); } catch (e) { sec.innerHTML = `<div class="g-scroll"><div class="callout">불러오기 실패 — ${esc(e.message)}</div></div>`; return; }
  }
  if (!AG.metaB) { try { AG.metaB = await api("/api/turn/meta?turn=breakfast"); } catch (e) { AG.metaB = { products: [] }; } }
  if (!AG.avm) { try { const r = await fetch("/static/avatars/manifest.json", { cache: "no-cache" }); AG.avm = r.ok ? await r.json() : {}; } catch (e) { AG.avm = {}; } }
  if (typeof libLoad === "function" && typeof LIBV !== "undefined" && !LIBV.data) { try { await libLoad(); } catch (e) {} }   // 아바타 팀 구성(유형) · 원문 링크에 라이브러리 자료가 필요
  if (!AG.manyInit && AG.meta) { AG.manyInit = true; AG.many = new Set(AG.meta.personas.map(p => p.id)); }   // 여러 명 기본 = 시뮬레이션 가능한 전원
  agLeft();
  cancelAnimationFrame(AG.raf); agMapReset();
  if (AG.autorun) { AG.autorun = false; AG.keep[mode] = null; AG.res = null; AG.runs = []; AG.plans = null; AG.visits = null; agReady(); return; }   // P6 — 라이브러리 '하루 보기'는 고객 · 조건만 채운다(실행은 사용자가 ▶)
  const kp = AG.keep[mode];   // 모드마다 마지막 결과를 따로 둔다 — 한 명 ↔ 여러 명을 오가도 결과가 사라지지 않게
  if (kp) {
    // Restore the ledger with its own map/plans, never the last run from another mode.
    AG.flow = kp.flow ? {...kp.flow,applied:kp.flow.applied||[],skipped:kp.flow.skipped||[]} : null; AG.visitData = AG.flow && AG.flow.ledger && AG.flow.ledger.visit ? AG.flow.result : null;
    AG.runs = kp.runs; AG.ti = kp.runs.length - 1; AG.res = AG.runs[AG.ti]; AG.sel = kp.sel; AG.plans = kp.plans || null; AG.visits = kp.visits || null;
    AG.visitDay = AG.runs[0]?.visit_day || 1; AG._sc = null; agShow(false);
  } else { AG.res = null; AG.runs = []; AG.plans = null; AG.visits = null; agReady(); }
}

// ---------------------------------------------------------------- 왼쪽 ① ② ③ ④ (선택 · 입력 · 실행만 — 해석은 오른쪽)
// CL-1025-37 hotfix(CD-15 29건) — 결정 입력에 후기 성향 항 · 사실 ID 가 없으면 엔진 문장의 '…을 중시하는 성향' 주장을 화면에 내지 않는다(엔진 · 기록은 그대로)
const AG_CLAIM_RX = /성향|중시|기울|취향|좋아/;
const AG_GENERIC_WHY = "공통 행동 규칙에 따른 선택(후기 성향 점수 미반영)";
function agWhySafe(why, grounded) {
  if (!why || grounded || !AG_CLAIM_RX.test(why)) return why;
  const rest = why.replace(/^.*?(?:을|를) 중시하는 성향(?:이라|에 맞춰)\s*/, "");
  return AG_GENERIC_WHY + (rest !== why && !AG_CLAIM_RX.test(rest) ? ` · ${rest}` : "");
}
const agScGround = b => !!(b && (((b.facts || []).length) || ((b.traits || []).length)));
const agCGround = c => (c.reasons || []).reduce((s, t) => s + ((t.parts && t.parts.review) || 0), 0) > 1e-6 || (c.direct_review_fact_ids || []).length > 0;   // 후기 몫 합이 선택을 실제로 밀어 준 경우만
function agTurnGround(runs, turn, pid, visitDay) { if (!turn) return false; const R = runs.find(r => r.turn === turn && (!visitDay || !r.visit_day || r.visit_day === visitDay)), c = R && (R.customers || []).find(x => x.persona_id === pid); return !!(c && agCGround(c)); }
function agLeft() {   // CL-1024-13 — 왼쪽: ① 고객(선택 컴포넌트) ② 방문 · 환경(라벨-컨트롤 행) ③ 운영 조건(상품 표) · 실행 바(스크롤과 겹치지 않음)
  const M = AG.meta, many = AG.mode === "agents", c = AG.cond;
  const auto = many && !AG.fix;   // 여러 명 기본: 투숙 · 건물 · 체류 단계 · 동행은 고객이 정한다(실험용 고정은 따로)
  if (auto) c.turn = "day";
  const pick = many ? agCustPicker() : `<div class="fr fr-top"><select id="agOne" aria-label="고객"><option value=""${AG.one ? "" : " selected"}>${AG.one ? "고객 선택 초기화" : "고객을 선택하세요"}</option>${agByNo(M.personas).map(p=>`<option value="${p.id}"${p.id===AG.one?' selected':''}>${esc(dno(p.id))} · ${esc(agTypeFull(p.id)||'유형 확인 중')}${p.isolated_qa?' · 검토 중':''}</option>`).join('')}</select></div>${AG.one ? `<div class="pc2" id="agPcard"></div>` : ""}`;
  const dinP = M.products.filter(p => p.kind !== "promo"), bfP = ((AG.metaB || {}).products || []).filter(p => p.kind !== "promo");
  const useB = (c.turn === "day" || c.turn === "breakfast") && c.stay, useD = c.turn === "day" || c.turn === "dinner", useE = (c.turn === "day" || c.turn === "event") && c.event;
  const nChanged = Object.keys(c.product_levers).length;
  // 핵심 턴(한 명 · 고정 모드) — 같은 폭 세그먼트 한 줄 · 시각은 아래 안내 줄
  const dayLab = c.stay && c.phase === "checkin" ? "체크인 당일" : c.stay && c.phase === "checkout" ? "체크아웃 당일" : c.stay ? "하루 전체" : "방문";
  const dayDesc = c.stay && c.phase === "checkin" ? (c.event ? "행사 · 저녁" : "저녁") : c.stay && c.phase === "checkout" ? "아침" : c.event && c.stay ? "아침 · 행사 · 저녁" : c.event ? "행사 · 저녁" : c.stay ? "아침 · 저녁" : "저녁";
  const turns = [["day", "하루"], ["breakfast", "아침"], ["event", "행사"], ["dinner", "저녁"]].map(([k, t]) => {
    const hide = (k === "event" && !c.event) || (c.stay && c.phase === "checkin" && k === "breakfast") || (c.stay && c.phase === "checkout" && (k === "event" || k === "dinner"));
    const dis = hide || (k === "breakfast" && !c.stay);
    return `<button type="button" data-t="${k}" class="${c.turn === k ? "on" : ""}"${dis ? " disabled" : ""} title="${k === "day" ? esc(dayLab + " · " + dayDesc) : esc(t + " " + ({ breakfast: "08:30", event: "16:30", dinner: "18:30" })[k])}">${t}</button>`; }).join("");
  const turnHint = c.turn === "day" ? `${dayLab} — ${dayDesc}` : `${({ breakfast: "아침 08:30", event: "행사 16:30", dinner: "저녁 18:30" })[c.turn] || ""} 한 턴만`;
  const fr = (lab, ctl, opt = {}) => `<div class="fr${opt.cls ? " " + opt.cls : ""}">${opt.for ? `<label class="fr-k" for="${opt.for}">${lab}</label>` : `<span class="fr-k">${lab}</span>`}<div class="fr-v">${ctl}${opt.hint ? `<div class="fr-h">${opt.hint}</div>` : ""}</div></div>`;
  const helpScen = noteH({ what: "어떤 날 · 어떤 고객 집단을 관찰할지 정합니다. 하루 전체 운영 = 하루 종일 머무는 연박 고객 중심, 오후 행사 중심 = 행사 날에 맞춰 체크인하는 고객이 많은 날, 주말 숙박 고객 = 숙박 고객만.", basis: ["운영 조건 · 계산"], caution: "실제 방문 통계가 없어 관찰 구성은 시연 가정입니다. 관찰할 날(체류 단계)의 비중만 바꾸며, 선정된 고객이 무엇을 할지는 바꾸지 않습니다." });
  const helpCond = noteH({ what: "방문 기간은 운영자가 0~3박으로 정하고, 고객마다 후기 경험과 유형 · 성향을 바탕으로 건물 · 동행 조건을 구성합니다.", basis: ["실제 후기", "추출 성향", "운영 조건 · 계산"], caution: "숙박 · 객실 선택에는 정량 계수가 없어 점수 · 확률을 매기지 않습니다(규칙 계획기 · 시드 고정). 특정 조건만 비교하려면 실험용 고정을 켜세요." });
  const NEW = AG.engine === "autonomy";
  const engineInfo=agCurrentEngineInfo();
  const AG_IVS = [["none", "운영 변경 없음"], ["wine_fair_1300", "13:00 와인페어 개최 공지(2부 15:30~20:00)"], ["pizzahill_full", "15:00 피자힐 저녁 17:30~20:30 예약 마감"], ["pool_check", "12:00 실내 수영장 16:00~19:00 점검"]];
  const env = [
    NEW ? fr(`하루 전체${noteH({ title:"하루 시뮬레이션", what:"고객의 체크인부터 식사·활동·휴식·체크아웃까지 방문 흐름을 계산합니다.", points:["시간대와 이용 조건에 따라 선택할 수 있는 활동이 달라집니다."] },"flow")}`, `<div class="fr-static"><b>하루 전체</b></div>`) :
    auto ? fr("핵심 턴", `<div class="fr-static"><b>하루 전체</b><span>고객마다 체류 단계가 달라 참여 턴이 다릅니다</span></div>`)
         : fr("핵심 턴", `<div class="cf-seg cf-seg4" id="agTurn" role="group" aria-label="핵심 턴">${turns}</div>`, { hint: esc(turnHint) }),
    fr("행사", `<select id="agEvent"><option value="0"${c.event ? "" : " selected"}>행사 없음</option><option value="1"${c.event ? " selected" : ""}>와인페어 있음</option>${agScenarioOption()}</select>`, { for: "agEvent" }),
    auto ? fr(`관찰 구성${helpScen}`, `<select id="agScen">${AG_SCEN.map(([k, t]) => `<option value="${k}"${(AG.scen || "day") === k ? " selected" : ""}>${t}</option>`).join("")}</select>`, { for: "agScen" }) : "",
    auto ? fr(`고객 조건${helpCond}`, `<div class="fr-static"><b>프로필 기반</b><span>건물 · 동행 인원</span></div>`) : "",
    many ? fr(`실험용${noteH({title:"같은 조건 고정",what:"켜면 모든 고객에게 같은 투숙·건물·동행 조건을 적용합니다. 끄면 고객별 프로필 기반 방문 조건을 유지합니다."},"flow")}`, `<label class="cf-switch"><input type="checkbox" id="agFix"${AG.fix ? " checked" : ""}><span>같은 조건 고정</span></label>`, { hint: "" }) : "",
    fr(`방문 기간${noteH({title:"방문 기간",what:"체크인·연박·체크아웃 단계는 선택한 0~3박 기간에 맞춰 날짜별로 자동 계산합니다."},"flow")}`, `<select id="agDuration" aria-label="방문 전체 체류 기간"><option value="day_visit"${AG.duration === "day_visit" ? " selected" : ""}>당일 방문 (0박)</option><option value="stay_1"${AG.duration === "stay_1" ? " selected" : ""}>1박 2일</option><option value="stay_2"${AG.duration === "stay_2" ? " selected" : ""}>2박 3일</option><option value="stay_3"${AG.duration === "stay_3" ? " selected" : ""}>3박 4일</option></select>`, { for: "agDuration" }),
    !auto ? fr("건물", `<select id="agBld"${c.stay ? "" : " disabled"}>${Object.entries(M.buildings).map(([k, v]) => `<option value="${k}"${k === c.building ? " selected" : ""}>${esc(v.replace(" 워커힐", ""))}</option>`).join("")}</select>`, { for: "agBld", cls: c.stay ? "" : "fr-dim" }) : "",
    !auto ? fr("동행 인원", `<select id="agParty">${[1, 2, 3, 4, 5, 6, 7, 8].map(n => `<option value="${n}"${n === c.party_size ? " selected" : ""}>${n}명</option>`).join("")}</select>`, { for: "agParty" }) : "",
    NEW ? "" : fr("행동 계획", `<select id="agBackend" title="주요 결정(아침 · 행사 · 저녁) 사이의 체류 행동을 누가 구성하나 — 엔진 결정은 바뀌지 않음"><option value="rules"${(AG.backend || "rules") === "rules" ? " selected" : ""}>규칙 계획기 (기본)</option><option value="auto"${AG.backend === "auto" ? " selected" : ""}>LLM 계획기 (키 필요)</option></select>`, { for: "agBackend", hint: (AG.backend || "rules") === "rules" ? "시드 고정 · 같은 조건 = 같은 하루" : "키가 없거나 검증 실패면 규칙 계획기로 대체(표시됨)" }),
  ].join("");
  // 운영 조건 — 시간 그룹(아침 · 행사 · 저녁) 접기 · 상품 표(이름 | 가격 | 조정)
  const grp = (key, title, time, venues) => {
    const ids = venues.flatMap(v => v.rows.map(p => p.product_id)), ch = ids.filter(id => c.product_levers[id]).length;
    const open = AG.grpOpen ? AG.grpOpen.has(key) : ch > 0;
    return `<details class="pe-grp" data-g="${key}"${open ? " open" : ""}><summary><b>${title}</b><span class="pe-time">${time}</span><span class="pe-cnt">${ids.length}개${ch ? ` · <em>${ch}개 바꿈</em>` : ""}</span></summary>
      ${venues.map(v => `<div class="pe-vh">${agDot(v.vid)}<span>${v.title}</span>${v.help ? noteH({ what: v.help, basis: ["운영 조건 · 계산"] }) : ""}</div>${v.rows.map(agProdRow).join("")}`).join("")}</details>`;
  };
  const groups = [
    useB ? grp("breakfast", "아침", "08:30", [{ vid: "THE_BUFFET", title: "조식 뷔페", help: "공식 조식 가격을 확인하지 못했습니다. 운영자가 가격을 넣거나 '객실 포함'을 고를 때만 후보에 들어갑니다.", rows: [AG_BUFFET] }, { vid: "ROOM_MEAL", title: "객실 조식", help: "룸서비스 메뉴 사진(2021년경) 가격입니다. 현재 가격과 다를 수 있습니다.", rows: bfP }]) : "",
    useE ? grp("event", "행사", "16:30", [{ vid: "FOREST", title: "와인페어 · 포레스트 파크", help: "기존 월드의 와인페어 선택지(입장권 55,000 · 시음 + 푸드 교환권 1매)를 행사 턴 16:30 에 씁니다. 대안은 산책 · 족욕 · 객실 휴식. 가격 · 할인 · 구성은 연구 프리셋(가상 운영안)입니다.", rows: [AG_WINE] }]) : "",
    useD ? grp("dinner", "저녁", "18:30", [{ vid: "PIZZA_HILL", title: "피자힐", help: "피자힐 메뉴판(2026-07) 가격입니다. 세트 · 나눔 메뉴는 인원 기준이 자료에 없어 인원을 넣어야 후보에 들어갑니다.", rows: dinP.filter(p => p.venue_id === "PIZZA_HILL") }, { vid: "ROOM_MEAL", title: "객실 식사", help: "룸서비스 메뉴 사진(2021년경) 가격입니다.", rows: dinP.filter(p => p.venue_id === "ROOM_MEAL") }]) : "",
  ].join("");
  $(".mode-agent").innerHTML = `<div class="g-scroll cf-left">
    <section class="cf-sec"><div class="cf-sh"><span class="cf-no">1</span><h3>${many ? "고객" : "고객 프로필"}</h3><span class="cf-sub">${many ? "함께 볼 고객 고르기" : "어떤 고객을 볼까요?"}</span></div>${pick}</section>
    <section class="cf-sec"><div class="cf-sh"><span class="cf-no">2</span><h3>방문 · 환경</h3><span class="cf-sub ag-execution-info">실행 정보${noteH({title:"실행 정보",what:"후기 기반 성향과 현재 방문 조건으로 행동을 선택합니다.",meta:`${engineInfo.label} · ${engineInfo.meta}`},"flow")}</span></div><div class="fr-list">${env}</div></section>
    <section class="cf-sec"><div class="cf-sh"><span class="cf-no">3</span><h3>운영 조건</h3><span class="cf-sub">가격 · 할인 · 혜택</span><span class="cf-badge${nChanged ? " on" : ""}" id="agChgN">${nChanged ? `${nChanged}개 바꿈` : "기본값"}</span></div>
      ${AG.exp ? `<div class="ag-expl"><b>실험 조건 적용 중</b> ${esc(AG.exp.title || AG.exp.question)} · ${esc(AG.exp.change || AG.exp.levers)} <button type="button" id="agExpOff">해제</button></div>` : ""}
      ${NEW ? `<div class="fr-list ag-ivrow">${fr(`운영 변경${noteH({ title:"운영 조건 변경", what:"행사·혜택 등 지원되는 조건을 바꾸어 고객의 가상 방문 결과를 비교합니다.", points:["대표 상품의 가격·혜택과 조식 포함 조건을 반영합니다.","그 밖의 메뉴 단위 조건은 상품 조건 실험에서 확인합니다."] },"flow")}`, `<select id="agIv">${AG_IVS.map(([k, t]) => `<option value="${k}"${AG.iv === k ? " selected" : ""}>${esc(t)}</option>`).join("")}</select>`, { for: "agIv", hint: AG.iv !== "none" ? "변경 전 하루와 나란히 계산합니다" : "" })}</div>
` : ""}
      <div class="ag-lvchips" id="agLvChips"></div>
      <div class="pe" id="agOps">${groups}
        <div class="fr pe-pricing"${NEW ? ' style="display:none"' : ""}><label class="fr-k" for="agPricing">가격 기준</label><div class="fr-v"><select id="agPricing"><option value="historical"${c.pricing === "historical" ? " selected" : ""}>자료 원값</option><option value="provisional"${c.pricing === "provisional" ? " selected" : ""}>룸서비스 +10% 추정</option><option value="world_v1"${c.pricing === "world_v1" ? " selected" : ""}>기존 월드 값</option></select><div class="fr-h">자료 원값 = 피자힐 2026-07 · 룸서비스 2021년경. 비워 둔 가격은 자료 값.</div></div></div>
      </div>
    </section>
  </div>
  ${typeof document !== "undefined" && document.body.classList.contains("devmode") ? `<div class="dev ag-engdev">행동 엔진(개발 · 비교용) <select id="agEngine"><option value="autonomy"${NEW ? " selected" : ""}>새 엔진 autonomy_v1</option><option value="legacy"${NEW ? "" : " selected"}>기존 엔진(turn_view + 계획기)</option></select></div>` : ""}
  <div class="g-runbar cf-run"><label>행동 판단 <select class="cf-input" id="agJudgment"${AG.busy?' disabled':''}>${HLVisitExecution.options(AG.judgmentMode||'rules')}</select><small id="agLiveStatus" role="status" hidden></small></label><div class="cf-run-b"><button id="agRun" class="cf-btn cf-primary">${AG.flow?"가상 방문 다시 생성":"가상 방문 생성"}</button><button id="agReset" class="cf-btn">조건 초기화</button></div>
    <div class="cf-run-h"><span class="gh-sub">${nChanged || c.pricing !== "historical" ? "바꾼 조건은 기본 조건과 나란히 비교" : "같은 엔진으로 1회 계산"}</span><span class="ra-sub" id="agHint"></span></div></div>`;
  agLvChips();
  // These legacy turn editors are not part of the full-visit request contract.
  // Keep them readable instead of silently pretending their values were applied.
  if (AG.duration && !(typeof DS !== 'undefined' && DS.step)) {
    document.querySelectorAll('#left .ag-prod input,#left .ag-prod select,#agIv').forEach(e=>{e.disabled=true;e.title='방문 전체 계산에는 이 개별 변경이 연결되지 않았습니다.';});
    const iv=document.querySelector('#agIv');
    { const rb0=$('#agRun'); if(AG.dateNotice && rb0 && !document.querySelector('#agDateNote')) rb0.closest('div').insertAdjacentHTML('beforebegin',`<p id="agDateNote" role="status" style="font-size:12px;line-height:1.6;color:#85633c;padding:0 16px">${esc(AG.dateNotice)}</p>`); }
    if(iv && !document.querySelector('#agVisitLimit'))iv.closest('.ag-ivrow').insertAdjacentHTML('afterend','<p id="agVisitLimit" style="font-size:12px;line-height:1.6;color:#85633c;padding:0 16px">상품별 가격·할인은 방문 조건의 운영 개입 → SKU 가격·할인에서 새 계산에 적용합니다. 이 표의 업장 단위 운영 설정은 별도입니다.</p>');
  }
  if (many) agCustPickerWire(); else { $("#agOne").onchange = e => { AG.one = e.target.value; agStale(); agLeft(); }; agPcard(); }
  { const rb = $("#agRun"); if (rb) rb.disabled = many ? !AG.many.size : !AG.one; }
  $("#agEvent").onchange = e => { AG.scenarioSelection=null;if(AG.visitRequest)delete AG.visitRequest.scenario; c.event = e.target.value === "1"; if (!c.event && c.turn === "event") c.turn = "day"; agStale(); agLeft(); };
  const xo = $("#agExpOff"); if (xo) xo.onclick = () => { AG.exp = null; agLeft(); if (AG.res) agPanel(); };
  const duration = $("#agDuration"); if (duration) duration.onchange = e => { const displayedBuilding = document.querySelector('#agBld')?.value;
    AG.duration = e.target.value;
    // Restore the explicitly displayed valid option; never invent a building in validation.
    if (AG.duration !== 'day_visit' && !c.building && Object.hasOwn(AG.meta.buildings, displayedBuilding)) c.building = displayedBuilding;
    AG.oneAuto = null; AG.oneOverride = true; c.stay = AG.duration !== "day_visit"; c.turn = "day"; agStale(); agLeft(); };
  $$("#agTurn button[data-t]").forEach(b => b.onclick = () => { c.turn = b.dataset.t; agLeft(); });
  const bld = $("#agBld"); if (bld) bld.onchange = e => { AG.oneAuto = null; AG.oneOverride = true; c.club = false; c.building = e.target.value; agStale(); if (!many) agPcard(); };
  const pty = $("#agParty"); if (pty) pty.onchange = e => { AG.oneAuto = null; AG.oneOverride = true; c.party_size = +e.target.value; agStale(); if (!many) agPcard(); };
  const fx = $("#agFix"); if (fx) fx.onchange = e => { AG.fix = e.target.checked; agLeft(); };
  const scn = $("#agScen"); if (scn) scn.onchange = e => { AG.scen = e.target.value; };
  const bk = $("#agBackend"); if (bk) bk.onchange = e => { AG.backend = e.target.value; agLeft(); };
  const ivs = $("#agIv"); if (ivs) ivs.onchange = e => { AG.iv = e.target.value; agLeft(); };
  const eng = $("#agEngine"); if (eng) eng.onchange = e => { AG.engine = e.target.value; try { localStorage.setItem("wh_engine", AG.engine); } catch (x) {} AG.keep = {}; AG.res = null; AG.runs = []; agLeft(); agEmpty(); };
  $("#agPricing").onchange = e => { c.pricing = e.target.value; };
  $$("#agOps .pe-grp").forEach(d => d.ontoggle = () => { AG.grpOpen = AG.grpOpen || new Set($$("#agOps .pe-grp[open]").map(x => x.dataset.g)); d.open ? AG.grpOpen.add(d.dataset.g) : AG.grpOpen.delete(d.dataset.g); });
  $$("#agOps .ag-more-btn").forEach(b => b.onclick = () => {
    const r = b.closest(".ag-prod"), id = r.dataset.pid, on = !r.classList.contains("open");
    r.classList.toggle("open", on); b.textContent = on ? "−" : "+"; b.setAttribute("aria-expanded", on);
    on ? AG.open.add(id) : AG.open.delete(id);
  });
  $$("#agOps input[data-p], #agOps select[data-p]").forEach(inp => inp.onchange = () => {
    const p = inp.dataset.p, k = inp.dataset.k, lv = Object.assign({}, c.product_levers[p] || {});
    if (inp.tagName === "SELECT") { if (inp.value && inp.value !== "standard") lv[k] = inp.value; else delete lv[k]; }
    else if (inp.type === "checkbox" && k === "available") { if (inp.checked) lv[k] = false; else delete lv[k]; inp.closest(".ag-prod").classList.toggle("off", inp.checked); }
    else if (inp.type === "checkbox") { if (inp.checked) lv[k] = true; else delete lv[k]; }
    else { const v = inp.value === "" ? null : +inp.value; if (v == null || isNaN(v) || (k !== "guest_discount" && v <= 0)) delete lv[k]; else lv[k] = v; }
    if (Object.keys(lv).length) c.product_levers[p] = lv; else delete c.product_levers[p];
    const n = Object.keys(c.product_levers).length, s = $("#agChgN"); if (s) { s.classList.toggle("on", n > 0); s.textContent = n ? `${n}개 바꿈` : "기본값"; }
    if (k === "party_basis" || k === "share_n") inp.closest(".ag-prod").classList.toggle("off", !lv[k]);
    agLvChips(); const g4 = $(".g-runbar .gh-sub"); if (g4) g4.textContent = n || c.pricing !== "historical" ? "바꾼 조건은 기본 조건과 나란히 비교" : "같은 엔진으로 1회 계산";
    if (p === "BREAKFAST_BUFFET") { const row = inp.closest(".ag-prod"), off = !lv.price && !lv.in_package, f = row.querySelector(".ag-flag.need"); row.classList.toggle("off", off); if (f) f.style.display = off ? "" : "none"; }
  });
  if (AG.pendingConditions && AG.flow) {
    const hint=document.querySelector('#agHint');
    if(hint)hint.textContent='조건 변경 중 · 아래 지도·소비는 이전 방문 결과입니다. 가상 방문을 다시 생성하면 반영됩니다.';
  }
  $("#agRun").onclick = agRun;
  HLVisitExecution.bindAvailability($("#agJudgment"),$("#agLiveStatus"),$("#agRun"),agReplayBlock);
  $("#agJudgment").onchange=e=>{AG.judgmentMode=e.target.value;AG.pendingConditions=true;agClearRunFailure();};
  $("#agReset").onclick = () => { AG.oneAuto = null; AG.oneOverride = false; AG.iv = "none"; AG.cond = { turn: c.turn, event: false, stay: true, building: "VISTA", party_size: 2, pricing: "historical", product_levers: {} }; AG.open.clear(); AG.grpOpen = null; agLeft(); };
}
// 상품 한 줄 — 이름(줄바꿈 허용 · 잘라내지 않음) | 가격(오른쪽 정렬 · 같은 자리폭) | 조정 버튼(같은 크기) · 펼치면 옵션 행(라벨 | 컨트롤)
function agProdRow(p) {
  const c = AG.cond, lv = c.product_levers[p.product_id] || {}, needN = p.party_basis == null, nk = p.kind === "set" ? "party_basis" : "share_n";
  const wine = p.product_id === "WINE_FAIR", ph = p.venue_id === "PIZZA_HILL" || wine, rm = (p.venue_id === "ROOM_MEAL" && p.kind !== "set") || p.product_id === "BREAKFAST_BUFFET" || wine, buf = p.product_id === "BREAKFAST_BUFFET";
  const opt = (lab, ctl) => `<div class="pe-opt"><span class="pe-ok">${lab}</span><div class="pe-ov">${ctl}</div></div>`;
  const extra = [
    ph ? opt(`${agIcon("tag")}할인`, `<input class="pe-num" type="number" min="0" step="1000" data-k="guest_discount" data-p="${p.product_id}" value="${lv.guest_discount || ""}" placeholder="0" aria-label="할인 금액"><span class="pe-unit">원</span>`) : "",
    needN ? opt(`${agIcon("people")}${p.kind === "set" ? "세트 인원" : "나눔 인원"}`, `<input class="pe-num" type="number" min="1" max="8" step="1" data-k="${nk}" data-p="${p.product_id}" value="${lv[nk] || ""}" placeholder="—" aria-label="인원"><span class="pe-unit">명</span>`) : "",
    rm ? opt(`${agIcon("gift")}혜택`, `<label class="cf-check"><input type="checkbox" data-k="in_package" data-p="${p.product_id}"${lv.in_package ? " checked" : ""}><span>객실 포함</span></label>`) : "",
    !wine && !buf ? opt("판매", `<label class="cf-check"><input type="checkbox" data-k="available" data-p="${p.product_id}"${lv.available === false ? " checked" : ""}><span>판매 안 함</span></label>`) : "",
    wine ? opt("구성", `<select data-k="variant" data-p="WINE_FAIR" aria-label="와인페어 구성">${AG_WINE_VAR.map(([k, t]) => `<option value="${k}"${(lv.variant || "standard") === k ? " selected" : ""}>${t}</option>`).join("")}</select>`) : "",
  ].join("");
  const off = (needN && !lv[nk]) || (buf && !lv.price && !lv.in_package) || lv.available === false, open = AG.open.has(p.product_id);
  const flags = [lv.guest_discount ? `<span class="ag-flag">할인 ${agWon(lv.guest_discount)}</span>` : "", lv.in_package ? `<span class="ag-flag">객실 포함</span>` : "", lv.available === false ? `<span class="ag-flag need">판매 안 함</span>` : "",
    off && buf ? `<span class="ag-flag need">가격 미확인 — 가격 입력 또는 객실 포함</span>` : off && needN && lv.available !== false ? `<span class="ag-flag need">인원 기준 필요</span>` : ""].filter(Boolean).join("");
  return `<div class="pe-row ag-prod${off ? " off" : ""}${open ? " open" : ""}" data-pid="${p.product_id}">
    <div class="pe-name"><span class="pe-ic" style="color:${agVColor(p.venue_id)}">${agIcon(agProdIcon(p))}</span><b>${esc(p.label)}</b></div>
    <div class="pe-flags">${flags || `<span class="pe-def">${p.price_krw == null ? "가격 자료 없음" : "자료 가격"}</span>`}</div>
    <input class="ag-price pe-price" type="number" min="0" step="1000" data-k="price" data-p="${p.product_id}" value="${lv.price || ""}" placeholder="${p.price_krw == null ? "가격" : p.price_krw.toLocaleString("ko-KR")}" aria-label="${esc(p.label)} 가격">
    ${extra ? `<button type="button" class="ag-more-btn pe-tg" aria-expanded="${open}" title="할인 · 인원 · 혜택 · 판매">${open ? "−" : "+"}</button><div class="ag-pi pe-opts">${extra}</div>` : `<span class="pe-tg0"></span>`}
  </div>`;
}
// ① 여러 명 고객 선택 — 선택 수 · 전체/해제 · 검색 · 유형 필터(목록만 거름 · 선택은 그대로) · 2열 선택 행
const AG_TY_ORDER = ["가족", "커플", "친구", "혼자", "미식", "행사", "웰니스", "개발 그룹", "미확정", "기타"];
// CL-1024-14 — 유형 표시는 라이브러리와 같은 대표 유형(개발 그룹 고객도 근거가 있으면 유형 아래 · 없으면 '유형 확인 중')
const agTypeRaw = lp => !lp ? "" : typeof libTypeOf === "function" ? (libTypeOf(lp) || "유형 확인 중") : (lp.type_group || lp.type || "");
const agTypeFull = id => agTypeRaw(agLibP(id));
// 10/26 — 고객 목록은 표시 번호 순(No.0001 → No.0011) · 엔진 입력 순서와 무관(표시만)
const agByNo = arr => [...arr].sort((a, b) => (dno(a.id) < dno(b.id) ? -1 : dno(a.id) > dno(b.id) ? 1 : 0));
// Shared presentation component; selections remain owned by their existing screens.
function hlCustomerPickerHTML(ids,selected,prefix,open=false) {
  const picked=ids.filter(id=>selected.has(id)),label=picked.length===ids.length&&ids.length?'전체 '+ids.length+'팀':picked.length+'팀 선택',names=picked.slice(0,2).map(dno).join(' · ');
  return `<details class="hl-customer-picker" data-picker="${prefix}"${open?' open':''}><summary><b>${label}</b><span>${esc(names||'고객을 선택하세요')}${picked.length>2?' 외 '+(picked.length-2)+'팀':''}</span></summary><div class="hl-picker-pop" popover="manual"><button type="button" class="cf-link hl-picker-close" data-picker-close>닫기 ×</button><label class="hl-picker-search">고객 검색<input class="cf-input" type="search" data-picker-search placeholder="번호 · 유형 · 핵심 특징" aria-label="고객 검색"></label><label class="hl-picker-all"><input type="checkbox" data-picker-all${picked.length===ids.length&&ids.length?' checked':''}>전체 ${ids.length}팀 선택</label><div class="hl-picker-list">${ids.map(id=>{const lp=agLibP(id)||{},meta=AG.meta&&AG.meta.personas.find(p=>p.id===id),feature=(meta&&meta.bars||[]).filter(b=>b.status==='observed').slice(0,1).map(b=>b.label).join(''),type=agTypeFull(id)||'유형 확인 중';return `<label data-picker-option data-search="${esc((dno(id)+' '+id+' '+type+' '+feature).toLowerCase())}"><input type="checkbox" data-picker-id="${esc(id)}"${selected.has(id)?' checked':''}><span><b>${esc(dno(id))}</b><strong>${esc(type)}</strong><small>${esc(feature)}</small></span></label>`;}).join('')}</div></div></details>`;
}
function hlCustomerPickerWire(root,ids,selected,onChange,onToggle,searchState=null) {
  const box=root.querySelector('.hl-customer-picker');if(!box)return;
  const pop=box.querySelector('.hl-picker-pop'),place=()=>{
    const r=box.querySelector('summary').getBoundingClientRect();
    if(box.dataset.picker==='revenue'){
      const below=innerHeight-r.bottom-18,above=r.top-18;
      const down=below>=Math.min(480,pop.scrollHeight)||below>=above;
      pop.style.width=Math.min(Math.max(340,r.width),innerWidth-24)+'px';
      pop.style.maxHeight=Math.max(80,Math.min(520,down?below:above))+'px';
      const size=pop.getBoundingClientRect();
      pop.style.left=Math.max(12,Math.min(r.left,innerWidth-size.width-12))+'px';
      pop.style.top=Math.max(12,down?r.bottom+6:r.top-size.height-6)+'px';
    }else{
      pop.style.left=Math.max(12,Math.min(r.left,innerWidth-402))+'px';
      pop.style.top=Math.min(r.bottom+6,innerHeight-Math.min(440,pop.scrollHeight)-12)+'px';
    }
  };
  if(box.dataset.picker==='revenue'){
    root._pickerEvents?.abort();root._pickerEvents=new AbortController();
    const options={signal:root._pickerEvents.signal},relocate=()=>{if(box.isConnected&&box.open)place();};
    window.addEventListener('resize',relocate,options);
    document.addEventListener('scroll',relocate,{...options,capture:true});
  }
  box.ontoggle=()=>{if(!box.isConnected)return;if(onToggle)onToggle(box.open);if(box.open){pop.showPopover();place();}else pop.hidePopover();};
  pop.querySelector('[data-picker-close]').onclick=()=>{box.open=false;};
  requestAnimationFrame(()=>{if(box.isConnected&&box.open){pop.showPopover();place();}});
  const all=box.querySelector('[data-picker-all]'),options=[...box.querySelectorAll('[data-picker-id]')];all.indeterminate=selected.size>0&&selected.size<ids.length;
  const commit=()=>onChange(new Set(options.filter(e=>e.checked).map(e=>e.dataset.pickerId)));
  options.forEach(e=>e.onchange=commit);all.onchange=()=>{options.forEach(e=>e.checked=all.checked);commit();};
  const search=box.querySelector('[data-picker-search]'),filter=()=>{const q=search.value.trim().toLowerCase();box.querySelectorAll('[data-picker-option]').forEach(row=>row.hidden=!!q&&!row.dataset.search.includes(q));};
  search.value=searchState?.query||'';filter();
  search.oninput=()=>{if(searchState)searchState.onChange(search.value);filter();};
}
function agCustPicker() { return hlCustomerPickerHTML(agByNo(AG.meta.personas).map(p=>p.id),AG.many,'flow',!!AG.pickerOpen); }
function agCustPickerWire() {
  hlCustomerPickerWire(document.querySelector('.mode-agent'),AG.meta.personas.map(p=>p.id),AG.many,selected=>{AG.many=selected;AG.pickerOpen=true;agStale();agLeft();},open=>AG.pickerOpen=open,{query:AG.pickerSearch,onChange:q=>AG.pickerSearch=q});
}
// CL-11 §2 — 관찰 구성(시연 가정) · 유형 집단 고르기
const AG_SCEN = [["day", "하루 전체 운영"], ["event", "오후 행사 중심"], ["weekend", "주말 숙박 고객"]];
const agTypeOf = id => { const t = agTypeRaw(agLibP(id)); return /가족/.test(t) ? "가족" : /커플/.test(t) ? "커플" : /혼자/.test(t) ? "혼자" : /친구/.test(t) ? "친구" : /미식/.test(t) ? "미식" : /행사/.test(t) ? "행사" : /웰니스/.test(t) ? "웰니스" : /개발/.test(t) ? "개발 그룹" : /확인 중/.test(t) ? "미확정" : t || "기타"; };
function agTypeChips() {
  const M = AG.meta.personas.map(x => x.id), cnt = {}; M.forEach(id => { const t = agTypeOf(id); cnt[t] = (cnt[t] || 0) + 1; });
  return `<div class="ag-types" id="agTypes"><span>유형 집단</span><button type="button" data-ty="*" class="${!AG.tyF || AG.tyF === "*" ? "on" : ""}">전체 ${M.length}</button>${Object.entries(cnt).map(([t, n]) => `<button type="button" data-ty="${esc(t)}" class="${AG.tyF === t ? "on" : ""}">${esc(t)} ${n}</button>`).join("")}</div>`;
}
// 바꾼 운영 조건 칩(목업의 '운영 변경' 칩) — 상품마다 한 칩 · × 로 되돌림
function agLvChips() {
  const el = $("#agLvChips"), c = AG.cond; if (!el) return;
  const ids = Object.keys(c.product_levers);
  el.innerHTML = ids.map(pid => { const t = agLeverText({ [pid]: c.product_levers[pid] }) || pid; return `<span class="ag-lvc" title="${esc(t)}"><span>${esc(t)}</span><button type="button" data-x="${esc(pid)}" aria-label="이 조건 되돌리기">×</button></span>`; }).join("");
  el.classList.toggle("hidden", !ids.length);
  $$("#agLvChips [data-x]").forEach(b => b.onclick = () => { delete c.product_levers[b.dataset.x]; agLeft(); });
}
// CL-1025-24 — 후기 숙박(관측) vs 이번 기본 시나리오(성향 가중 추첨) · 운영자가 후기 숙박 조건을 고르면 '운영자가 정한 조건'으로 실행
function agRsLine(pid) {
  if (AG.engine !== "autonomy" || !AG.oneRS || AG.oneRS.pid !== pid || !AG.oneRS.rs || !AG.oneRS.rs.building) return "";
  const R = AG.oneRS.rs, c = AG.cond, nm = k => AG_BLD_SHORT[k] || k;
  if (R.pending) return `<p class="pc2-rs warn"><span>숙박 단서</span>${esc(R.text)}</p>`;
  if (R.same) return `<p class="pc2-rs"><span>${R.building === "NONSTAY" ? "후기 방문" : "후기 숙박"}</span><b>${esc(R.label)}</b> · 기본 시나리오와 같음</p>`;
  const onRev = AG.oneOverride && ((R.building === "NONSTAY" && !c.stay) || (c.stay && c.building === R.building && !!c.club === !!R.club));
  return `<p class="pc2-rs"><span>후기 숙박</span><b>${esc(R.label)}</b> · 기본 시나리오 <b>${esc(nm(R.drawn))}</b>${noteH({ what: R.text, basis: ["실제 후기", "운영 조건 · 계산"], caution: "기본 시나리오는 후기를 복사하지 않는 성향 가중 추첨입니다. 아래 버튼은 운영자가 후기와 같은 숙박 조건을 정해 실행하는 것이며, 고객이 정한 조건이 아닙니다." })}</p>
    ${onRev ? `<p class="pc2-rs on">지금: 운영자가 정한 후기 숙박 조건${R.club ? "(클럽 객실 · 라운지 이용 가능)" : ""}</p>` : `<button type="button" class="cf-btn pc2-rsb" id="agRsRun">후기 숙박 조건으로 실행${R.club ? "(클럽 객실)" : ""}</button>`}`;
}
// 왼쪽 에이전트 카드 — 식별 · 근거 상태 · 프로파일 버튼만 (성향 막대는 오른쪽에 한 번만)
// 10/26 — 고객을 바꾸면 카드 아바타 · 인원이 바로 그 고객 기준으로 바뀌게: 고객이 정한 조건(이 고객 실행 결과) → 확인된 동행 인원 → 입력값(운영자가 정한 경우는 입력값 그대로)
function agShowN(pid) {
  if (AG.oneVisit && AG.oneVisit.pid === pid && AG.oneVisit.v && AG.oneVisit.v.party_size) return AG.oneVisit.v.party_size;
  if (AG.engine === "autonomy" && !AG.oneOverride) { const c = AG_COMP[pid], P = typeof dnoParty === "function" ? dnoParty(pid) : {}, m = AG_AVMAP[pid];
    const n = (c && c.n) || P.n || (m && m.supported); if (n) return n; }
  return AG.cond.party_size;
}
function agPcard() {   // CL-1024-13 — 대표 영역(아바타 · ID · 유형 · 한 줄 설명) → 정의 목록(원문 동행 · 이번 인원 · 후기 근거) → 같은 크기 버튼 두 개 → 적용 상태
  const p = AG.meta.personas.find(x => x.id === AG.one), el = $("#agPcard"); if (!p || !el) return;
  const N = agShowN(p.id), cp = agComp(p.id, N), nObs = p.bars.filter(b => b.status === "observed").length, lp = agLibP(p.id) || {};
  const full = agTypeFull(p.id), sub = full.split(" · ").slice(1).join(" · "), mine = AG.oneAuto && AG.oneAuto.pid === p.id;
  el.innerHTML = `<div class="pc2-head"><div class="pc2-av" title="${esc(AG_AV_NOTE)}">${agAvatarIcon(p.id, N, 56)}</div>
      <div class="pc2-hb"><div class="pc2-id"><b>${esc(dno(p.id))}</b><span class="pc2-ty">${esc(agTypeOf(p.id))}</span>${sub ? `<span class="pc2-sub">${esc(sub)}</span>` : ""}</div>${lp.label ? `<p class="pc2-lab">${esc(lp.label)}</p>` : ""}</div></div>
    <dl class="pc2-dl"><div><dt>원문 동행</dt><dd>${esc(cp.src || "확인 안 됨")}</dd></div><div><dt>이번 인원</dt><dd>${N}인${!cp.src ? `<em class="pc2-tag">시뮬레이션 가정</em>` : ""}${cp.src && !cp.match ? `<span class="pc2-warn">원문과 다름 · 지도는 ${N}인</span>` : ""}</dd></div>
      <div><dt>후기 근거</dt><dd>성향 ${nObs}/${p.bars.length} 확인${noteH({ title:"성향 근거 확인", what:`${p.bars.length}개 성향 항목 중 ${nObs}개에서 실제 후기 근거가 확인되었습니다.`, points:[`${p.bars.length-nObs}개는 근거가 확인되지 않았으며, 선호가 없거나 0점이라는 뜻은 아닙니다.`], caution:"원문 교차검증 진행 중" },"flow")}</dd></div></dl>
    <div class="pc2-acts"><button type="button" class="cf-btn" id="agProf">프로파일 보기</button><button type="button" class="cf-btn${mine || (AG.engine === "autonomy" && !AG.oneOverride) ? " on" : ""}" id="agAutoOne" title="이 고객의 후기 경험 · 유형 · 성향으로 투숙 여부 · 건물 · 체류 단계 · 동행을 정해 아래 입력에 넣습니다(운영자가 바꿀 수 있음)">${mine ? "다시 정하기" : "이 고객이 정하기"}</button></div>
    `;
  const nights=({day_visit:0,stay_1:1,stay_2:2,stay_3:3})[AG.duration];
  const summary=`${nights?`${nights}박 방문`:"당일 방문"} · ${N}명`;
  if(p.isolated_qa)el.insertAdjacentHTML("beforeend",'<p class="st-private-note">검토 중 · 소유자 전용</p>');
  el.insertAdjacentHTML("beforeend", `<div class="pc2-visit-row"><span>${esc(summary)}</span><button type="button" class="cf-link" id="agSituation">상황 다시 설정</button></div>` + agRsLine(p.id));
  $("#agSituation").onclick = () => situationOpen(p.id, true);
  const rsb = $("#agRsRun"); if (rsb) rsb.onclick = () => { const R = AG.oneRS.rs, c = AG.cond; AG.oneAuto = null; AG.oneOverride = true; c.stay = R.building !== "NONSTAY"; if (c.stay) { c.building = R.building; c.phase = c.phase && c.phase !== "visit" ? c.phase : "mid"; } c.club = !!R.club; agLeft(); agRun(); };
  $("#agProf").onclick = () => p.isolated_qa ? window.HillinkPrivateIntake.show(p.id) : agCustDrawer(p.id);
  $("#agAutoOne").onclick = () => { if (AG.engine === "autonomy") { AG.oneOverride = false; AG.oneAuto = null; agPcard(); return; } agAutoOne(p.id); };
}
async function agAutoOne(pid) {   // 보충2 — 한 명 모드에서도 고객이 자기 방문 조건을 정할 수 있다(결과는 왼쪽 입력에 반영 · 운영자가 덮어쓸 수 있음)
  try {
    const c0 = AG_COMP[pid], comp = c0 ? { [pid]: { n: c0.n, rel: c0.rel, kids: c0.rel === "family_kids", elder: c0.rel === "family_parents" } } : {};
    const seed = (AG.oneAuto && AG.oneAuto.pid === pid ? AG.oneAuto.seed + 1 : (AG.seed || 0));
    const r = await api("/api/stay", { op: "visit", personas: [pid], cond: { event: AG.cond.event }, comp, seed });
    const v = r.visits && r.visits[pid]; if (!v) return;
    const c = AG.cond; c.stay = !!v.stay; AG.duration = v.stay ? ({ 1: "stay_1", 2: "stay_2", 3: "stay_3" }[v.nights] || "stay_1") : "day_visit"; if (v.stay) { c.building = v.building; c.phase = v.phase; } c.party_size = v.party_size; c.turn = "day";
    AG.oneAuto = { pid, seed, v, short: v.stay ? `${AG_BLD_SHORT[v.building]} ${v.nights}박 · ${AG_PH_KO[v.phase]} · ${v.party_size}인` : `비투숙 당일 방문 · ${v.party_size}인` };
    agLeft();
  } catch (e) { console.warn("visit 실패", e); }
}
// ---------------------------------------------------------------- 실행
// 10/24 보충1 수정본 — 체류·행동 계획(stay_run.py): 엔진 결정은 그대로 넘기고 그 사이 행동만 받는다. 시드 고정으로 같은 조건 = 같은 하루
const agDecisions = (runs, pid, before) => runs.filter(R=>!R.display_only).map(R => { const RR = before ? (R._before || R) : R, c = agCustOf(RR, pid); if (!c) return null; const cc = R.compare && R.compare.customers.find(y => y.persona_id === pid);
  // CL-1024-12 긴급 보충 — 정량 결정 잠금 데이터: 결정 ID · 시각 · 장소 · 상품 ID · 참여/불참 · 비교 대안 · 출처. 계획기는 읽기만(바꾸면 실행 차단)
  const ev = R.turn === "event", part = ev ? (c.choice.venue_id === "FOREST" ? "participate" : "skip") : (c.choice.venue_id === "ROOM" ? "skip" : "purchase");
  const alts = [c.runner_up, ...(c.not_chosen || [])].filter(Boolean).slice(0, 3).map(a => a.product_id || a.venue_id).filter(Boolean);
  return { decision_id: `${pid}|${R.turn}|${R.time}`, turn: R.turn, time: R.time, loc: c.choice.map_loc, label: AG_TURN[R.turn], product_id: c.choice.product_id || c.choice.venue_id, product_label: c.choice.product_label, venue_id: c.choice.venue_id,
    participation: part, alternatives: alts.length ? alts : (c.best_other_venue ? [c.best_other_venue.venue_id] : []), source: before ? "turn_view:base_condition" : "turn_view", changed: !before && !!(cc && cc.status === "changed"),
    token: c.decision_token || null }; }).filter(Boolean);   // CL-1024-22R — 서버 발급 증표(서버가 같은 결과에서 다시 계산해 대조)
async function agFetchPlans(ids, runs, cond, ph, visits) {
  try {
    const decisions = {}, base = {}, comp = {}, condBy = {};
    let anyCmp = false;
    ids.forEach(pid => { decisions[pid] = agDecisions(runs, pid, false); if (runs.some(R => R.compare)) { anyCmp = true; base[pid] = agDecisions(runs, pid, true); }
      const v = visits && visits[pid], cp = agComp(pid, v ? v.party_size : cond.party_size); comp[pid] = { n: cp.n, rel: v ? v.rel : cp.rel, kids: v ? !!v.kids : cp.rel === "family_kids", elder: v ? !!v.elder : cp.rel === "family_parents" };
      if (v) condBy[pid] = { stay: !!v.stay, building: v.stay ? v.building : cond.building, party_size: v.party_size, phase: v.stay ? v.phase : "visit" }; });
    const r = await api("/api/stay", { op: "plan", personas: ids, cond: Object.assign({}, cond, { phase: ph }), cond_by: visits ? condBy : undefined, decisions, base_decisions: anyCmp ? base : undefined, comp, seed: AG.seed || 0, backend: AG.backend || "rules" });
    AG.llmAvail = !!r.llm_available; return r.plans || null;
  } catch (e) { console.warn("stay plan 실패 — 간이 흐름으로", e); return null; }
}
async function agRunTurns(ids, cond, ph) {   // 같은 방문 조건의 에이전트 묶음 — 핵심 턴마다 같은 엔진으로 계산(엔진 · 계수 변경 없음)
  const turns = cond.turn === "day" ? [cond.stay && ph !== "checkin" && "breakfast", cond.event && ph !== "checkout" && "event", ph !== "checkout" && "dinner"].filter(Boolean) : [cond.turn], runs = [];
  let states = null, baseStates = null;   // 행사 턴 → 저녁 턴: 이용 · 허기 상태를 잇는다(기준 조건은 기준 조건의 행사 결과로)
  for (const t of turns) {
    const ct = Object.assign({}, cond, { turn: t }), lv = {};
    const want = t === "breakfast" ? new Set(["BREAKFAST_BUFFET", ...((AG.metaB || {}).products || []).map(p => p.product_id)]) : t === "event" ? new Set(["WINE_FAIR"]) : new Set(AG.meta.products.map(p => p.product_id));
    for (const [k, v] of Object.entries(cond.product_levers)) if (want.has(k)) lv[k] = v;
    ct.product_levers = lv;
    const base = { product_levers: lv.BREAKFAST_BUFFET ? { BREAKFAST_BUFFET: lv.BREAKFAST_BUFFET } : {}, pricing: "historical" };
    const changed = Object.keys(lv).filter(k => k !== "BREAKFAST_BUFFET").length > 0 || cond.pricing !== "historical" || (t === "dinner" && states && baseStates && JSON.stringify(states) !== JSON.stringify(baseStates));
    let r;
    if (changed) {   // 운영 조건을 바꿨으면 같은 에이전트 · 같은 방문 조건의 기준 조건 결과와 나란히 계산(turn_compare)
      const x = await api("/api/turn", { op: "compare", personas: ids, cond: ct, base, states: states || undefined, base_states: baseStates || undefined }); r = x.after; r.compare = x.compare; r._before = x.before;
      if (t === "event") { baseStates = {}; x.before.customers.forEach(c => baseStates[c.persona_id] = c.state_after.engine_state); }
    } else r = await api("/api/turn", { op: "view", personas: ids, cond: ct, states: states || undefined });
    if (t === "event") { states = {}; r.customers.forEach(c => states[c.persona_id] = c.state_after.engine_state); if (!baseStates) baseStates = states; }
    r._mode = AG.mode; if (r._before) r._before._mode = AG.mode; runs.push(r);
  }
  return runs;
}
// 보충2 — 여러 명 자율 모드: 묶음별 결과를 턴별로 합친다(고객마다 vc = 자기 방문 조건). 비교 결과가 있는 묶음과 없는 묶음이 섞이면 없는 쪽은 '유지'로 채운다
function agMergeRuns(byT, rs, vc) {
  const kept = c => ({ persona_id: c.persona_id, status: "kept", before: { product_id: c.choice.product_id, product_label: c.choice.product_label, venue_id: c.choice.venue_id, map_loc: c.choice.map_loc, score: c.choice.score }, after: { product_id: c.choice.product_id, product_label: c.choice.product_label, venue_id: c.choice.venue_id, map_loc: c.choice.map_loc, score: c.choice.score }, venue_changed: false, score_delta: 0, top_drivers: [], kept_reason: null });
  rs.forEach(R => {
    R.customers.forEach(c => { c.vc = vc; }); if (R._before) R._before.customers.forEach(c => { c.vc = vc; });
    const M = byT[R.turn];
    if (!M) { byT[R.turn] = R; R._auto = true; return; }
    const n0 = M.customers.length;
    M.customers.push(...R.customers);
    if (R.compare || M.compare) {
      if (!M.compare) { M.compare = { summary: { changed: 0, score_only: 0, kept: n0 }, customers: M.customers.slice(0, n0).map(kept) }; M._before = { customers: M.customers.slice(0, n0).map(c => Object.assign({}, c)), _mode: M._mode }; }
      if (R.compare) { M.compare.customers.push(...R.compare.customers); for (const k of ["changed", "score_only", "kept"]) M.compare.summary[k] += R.compare.summary[k] || 0; M._before.customers.push(...R._before.customers); }
      else { M.compare.customers.push(...R.customers.map(kept)); M.compare.summary.kept += R.customers.length; M._before.customers.push(...R.customers.map(c => Object.assign({}, c))); }
    }
    if (R.excluded && R.excluded.length && !(M.excluded && M.excluded.length)) M.excluded = R.excluded;
  });
}
// Product execution binding only: an explicitly selected scenario follows its customer set.
function agSelectedScenario(ids) {
  const selection=AG.scenarioSelection;
  return selection && JSON.stringify([...selection.personas].sort())===JSON.stringify([...ids].sort()) ? selection : null;
}
// An event card is a visit environment shared by every selected customer; it is kept when the customer set changes.
function agCarriedScenario(ids) {
  const s=AG.scenarioSelection;
  if(!s || agSelectedScenario(ids) || s.scenario.event_card_id==='WINE_FAIR_2026_AUTUMN')return null;
  const scenario=structuredClone(s.scenario);
  if(scenario.entitlements){const value=Object.values(scenario.entitlements)[0];scenario.entitlements=Object.fromEntries(ids.map(id=>[id,structuredClone(value)]));}
  return {scenario,start_date:s.request.start_date,label:s.label};
}
function agScenarioOption() {
  const ids=AG.mode==='agents'?[...AG.many]:[AG.one],selected=agSelectedScenario(ids)||agCarriedScenario(ids);
  if(!selected || selected.scenario.event_card_id==='WINE_FAIR_2026_AUTUMN')return '';
  return `<option value="scenario" selected>${esc(selected.label)}</option>`;
}
// Replay from this page reproduces the last replayed visit only; anything else needs saved conditions (situation page).
function agReplayBlock(mode){
  if(mode!=='replay'||AG.visitRequest)return null;
  const last=AG.flow&&AG.flow.request;
  return last&&last.judgment_mode==='replay'?null:HLVisitExecution.REPLAY_NEEDS_SAVED;
}
function agClearRunFailure(){document.querySelectorAll('.ag-run-failure').forEach(x=>x.remove());}
async function agRunFlow(ids, cond, auto) {
  if (!(typeof DS !== "undefined" && DS.on && DS.step)) {
    const selection=agSelectedScenario(ids);
    const sameCustomers=AG.flow?.request?.personas?.length===ids.length && ids.every(id=>AG.flow.request.personas.includes(id));
    const commonRequest=Object.fromEntries(['start_date','environment','behavior_engine','catalog_policy','catalog_options','hybrid_policy','simulation_mode'].filter(k=>AG.flow?.request?.[k]!==undefined).map(k=>[k,structuredClone(AG.flow.request[k])]));
    // A fresh situation form is a complete request, not a continuation of the previous run.
    const selectedRequest=AG.visitRequest?{}:selection?structuredClone(selection.request):sameCustomers?structuredClone(AG.flow.request):commonRequest;
    if (!selection) delete selectedRequest.scenario;
    const carried=!AG.visitRequest&&agCarriedScenario(ids);
    if(carried){selectedRequest.scenario=carried.scenario;selectedRequest.start_date=carried.start_date;selectedRequest.behavior_engine='m4_c01';}
    if (selectedRequest.duration && selectedRequest.duration !== AG.duration) delete selectedRequest.package_id;
    const request = { ...selectedRequest, ...(AG.visitRequest ? structuredClone(AG.visitRequest) : {}), personas: [...ids], duration: (AG.visitRequest && AG.visitRequest.duration) || AG.duration || (cond.stay ? "stay_1" : "day_visit"), event_mode: cond.event ? "wine" : "none", seed: AG.seed || 0, start_date: (AG.visitRequest && AG.visitRequest.start_date) || selectedRequest.start_date || "2026-10-24", include_ledger: true };
    if (!AG.visitRequest && AG.visitData && AG.visitData.visit.package_id && request.duration === AG.visitData.visit.duration && ids.every(pid => AG.visitData.plans[pid])) request.package_id = AG.visitData.visit.package_id;
    if (!AG.visitRequest && ((ids.length === 1 && AG.oneOverride) || (ids.length > 1 && AG.fix))) {
      request.visit_conditions = Object.fromEntries(ids.map(pid => [pid, {...(request.visit_conditions?.[pid]||{}), building: request.duration === "day_visit" ? null : cond.building, party_size: cond.party_size, club: !!cond.club}]));
    }
    // 2025 dates exist only inside an explicit event-card scenario (server date policy); a plain visit moves to the 2026 default date, visibly.
    AG.dateNotice=null;
    if(!request.scenario && String(request.start_date)<'2026-01-01'){AG.dateNotice=`행사 카드 없이 계산하는 방문이라 ${request.start_date} 대신 2026-10-24로 계산했습니다 (2025년은 행사 시나리오에서만 지원).`;request.start_date='2026-10-24';}
    Object.assign(request,HLVisitExecution.request(request,HLVisitExecution.modeOf(AG.visitRequest)||AG.judgmentMode||'rules',AG.visitRequest?.hybrid_policy||null));
    if(request.judgment_mode==='rules')delete request.hybrid_policy;
    if(request.judgment_mode==='replay'&&!AG.visitRequest){   // checked before any request: never send a replay that cannot match
      const last=AG.flow&&AG.flow.request;
      if(!last||last.judgment_mode!=='replay')throw new Error(HLVisitExecution.REPLAY_NEEDS_SAVED);
      const diff=HLVisitExecution.runDiff(request,last);if(diff.length)throw new Error(HLVisitExecution.replayChanged(diff));
    }
    AG.runningRequest=structuredClone(request);
    const r = await api("/api/visit", request);
    if (r.error) throw new Error(r.error);
    if(request.scenario && (!r.visit || !r.visit.scenario_snapshot || r.visit.scenario_snapshot.event_card_id!==request.scenario.event_card_id))throw new Error('선택한 행사 조건이 실제 계산에 전달되지 않았습니다.');
    AG.scenarioSelection=request.scenario?{personas:[...ids],scenario:structuredClone(request.scenario),request:structuredClone(request),label:r.visit.scenario_snapshot.sources[0].record['행사 · 상품명']}:null;
    if (!r.ledger || r.ledger.source !== "live_engine") throw new Error("방문 실행의 실제 원장을 확인하지 못했습니다.");
    if (typeof revRememberFlow === "function") revRememberFlow(r, request);
    AG.pendingConditions = false; AG.visitData = r; AG.visitDay = 1; AG.visitRequest = null;
    AG.duration = r.visit.duration;
    if (ids.length === 1 && r.visits[ids[0]]) {
      const resolved = r.visits[ids[0]];
      AG.cond = {...AG.cond, stay: resolved.stay, building: resolved.building, party_size: resolved.party_size, club: !!resolved.club};
    }
    AG.flow = { result: structuredClone(r), request: structuredClone(request), ledger: r.ledger,
      stories: r.stories || null, engine: r.engine, intervention: { id: "none" }, applied: [], skipped: [],
      notices: r.notices || [], sha: r.visit_inputs_sha };
    if (typeof rcAcceptLedger === "function") rcAcceptLedger(r.ledger);
    for (const run of r.runs || []) { run._mode = AG.mode; run._auto = ids.length > 1 && !AG.fix; }
    const view = agVisitDayView(r, 1);
    if (!view.runs.length) throw new Error("첫 방문 일자의 행동 실행 결과가 없습니다.");
    if (ids.length === 1) {
      const pid = ids[0], v = view.visits[pid];
      AG.oneVisit = { pid, v, short: `${r.visit.duration === "day_visit" ? "비투숙 당일 방문" : `${r.visit.nights}박 방문`} · ${v.party_size}인` };
    }
    agLeft(); // Reflect the executed duration/building/party in the controls.
    return { ...view, visitData: r };
  }
  AG.visitData = null; AG.visitDay = 1;
  const one = ids.length === 1 && AG.mode !== "agents";
  const ov = (one && AG.oneOverride) || (!one && AG.fix);
  const vo = ov ? Object.fromEntries(ids.map(pid => [pid, { stay: !!cond.stay, building: cond.stay ? cond.building : null, phase: cond.stay ? (cond.phase || "mid") : "visit", party_size: cond.party_size, club: !!(one && cond.club && cond.stay && cond.building === "GRAND") }])) : null;
  const request = { personas: ids, mode: one ? "one" : "many", visit_override: vo, event: !!cond.event, intervention: AG.iv || "none", product_levers: cond.product_levers || {}, observe: AG.scen || "day", seed: AG.seed || 0 };
  const r = await api("/api/flow", request);
  if (r.error) throw new Error(r.error);
  if (typeof revRememberFlow === "function") revRememberFlow(r, request);
  AG.flow = { result: structuredClone(r), request: structuredClone(request), ledger: r.ledger || null, stories: r.stories || null, engine: r.engine, intervention: r.intervention, applied: r.levers_applied || [], skipped: r.levers_not_applied || [], notices: r.notices || [], sha: r.inputs_sha };
  if (typeof rcAcceptLedger === "function") rcAcceptLedger(r.ledger);
  const many = !one;
  r.runs.forEach(R => { R._mode = AG.mode; R._auto = many && !AG.fix; if (R._before) R._before._mode = AG.mode;
    if (many) [R, R._before].filter(Boolean).forEach(X => X.customers.forEach(c => { const v = r.visits[c.persona_id]; if (v) c.vc = agVcOf(v); })); });
  if (one && r.visits[ids[0]]) { const v0 = r.visits[ids[0]]; AG.oneRS = { pid: ids[0], rs: v0.review_stay || null, club: !!v0.club, ovr: !!AG.oneOverride }; }
  if (one) { const v = r.visits[ids[0]]; if (v && !AG.oneOverride) { const c = AG.cond; c.stay = !!v.stay; if (v.stay) { c.building = v.building; c.phase = v.phase; } c.party_size = v.party_size;
    AG.oneVisit = { pid: ids[0], v, short: (v.stay ? `${AG_BLD_SHORT[v.building] || v.building} ${v.nights}박 · ${AG_PH_KO[v.phase] || v.phase} · ${v.party_size}인` : `비투숙 당일 방문 · ${v.party_size}인`) + (v.layer === "generated" ? " [시뮬레이션 가정]" : v.layer === "mixed" ? " [일부 시뮬레이션 가정]" : "") }; agLeft(); } }
  return { runs: r.runs, plans: r.plans, visits: many ? r.visits : null };
}
// Display frame for a real activity-only day. Never written into result.runs or the ledger.
// It anchors the map to recorded arrival; it is not a new meal, purchase or scored decision.
function agActivityFrame(day, plans, visits) {
  const customers=Object.entries(plans).filter(([,p])=>p.status==='ok'&&p.scenes.length).map(([pid,p])=>{
    const first=p.scenes[0],v=visits[pid]||{},label=(AG.meta?.personas||[]).find(x=>x.id===pid)?.label||pid;
    return {persona_id:pid,persona:{label,bars:[]},vc:agVcOf(v),
      choice:{map_loc:first.loc,venue_id:first.loc,venue_label:first.label,product_label:first.label,score:null,price:{}},
      reasons:[],reason_totals:{},not_chosen:[],evidence:{},evidence_status:{},display_only:true};
  });
  if(!customers.length)return [];
  const v=visits[customers[0].persona_id]||{},first=Math.min(...customers.map(c=>plans[c.persona_id].scenes[0].t0));
  return [{display_only:true,turn:'day',time:agHM(first),visit_day:day.day_index,visit_date:day.date,
    conditions:{...structuredClone(v),turn:'day',event:!!day.event,product_levers:{}},
    building:{id:v.building,label:AG.meta?.buildings?.[v.building]||v.building||''},customers,excluded:[]}];
}
function agVisitDayView(visitData, dayNumber) {
  const day = (visitData.visit_days || []).find(x => x.day_index === dayNumber);
  if (!day) return { runs: [], plans: {}, visits: {} };
  let runs = (visitData.runs || []).filter(r => r.visit_day === dayNumber);
  const plans = {};
  for (const [pid, source] of Object.entries(visitData.plans || {})) {
    const plan = {...source};
    plan.scenes = (source.scenes || []).filter(s => s.visit_day === dayNumber).map(s=>({...s}));
    plan.summary = { ...(plan.summary || {}), visit_day: dayNumber, visit_date: day.date, day_phase: day.phase };
    plans[pid] = plan;
  }
  const visits = structuredClone(visitData.visits || {});
  for (const value of Object.values(visits)) value.phase = day.phase;
  for (const [pid, state] of Object.entries(day.state_after || {})) if (visits[pid]) visits[pid].benefit_usage = structuredClone(state.benefit_usage || {});
  if(!runs.length)runs=agActivityFrame(day,plans,visits);
  return { runs, plans, visits, day };
}
// Date slices are display-only; full visitData and flow/ledger remain intact.
function agAdvanceVisitDay() {
  const next = AG.visitData?.visit_days?.find(d => d.day_index > AG.visitDay && agVisitDayView(AG.visitData,d.day_index).runs.length);
  if (!next) return false;
  agVisitDaySelect(next.day_index);
  if (agIsMany(AG.res)) agPlayManyTime(true); else agPlayFrom(0);
  return true;
}
function agVisitDaySelect(dayNumber) {
  if (!AG.visitData) return;
  const view = agVisitDayView(AG.visitData, dayNumber);
  if (!view.runs.length) return;
  cancelAnimationFrame(AG.raf);
  AG.playing = false; AG.paused = false; AG.ended = false; AG.f = 0;
  AG.manyT = null; AG.manyHeld = null; AG._disp = null; AG._dispT = null; AG.openLoc = null;
  AG.visitDay = dayNumber; AG.runs = view.runs; AG.plans = view.plans; AG.visits = view.visits;
  AG.ti = AG.runs.length - 1; AG.res = AG.runs[AG.ti]; AG.sel = AG.mode === "agents" ? AG.sel : AG.one;
  AG.focusLoc = null; AG._sc = null; AG.si = 0; AG.keep[AG.mode] = { runs: AG.runs, sel: AG.sel, plans: AG.plans, visits: AG.visits, flow: AG.flow };
  agPlanHint(); agShow(false); document.dispatchEvent(new Event("hl:agrun"));
}
// LIVE runs call the model once per decision and the server reports nothing until the whole visit is done, so the
// only honest progress signal is elapsed time against a measured range. No decision count is invented from the clock.
// 2026-11-08 measurement (v21/v22 LIVE, 2 nights, 69 visits): 18~30 decisions, about 10 s per decision on average
// (p90 about 15~17 s), whole visit about 3~6 min. Other durations were not re-measured: no time is promised for them.
const AG_RUN_LATENCY = '판단마다 대개 10~20초(11월 측정)';
const AG_RUN_EXPECT = { day_visit: [2, 3, '시간은 판단 수에 따라 달라짐'], stay_1: [8, 12, '시간은 판단 수에 따라 달라짐'], stay_2: [18, 30, '측정 참고 약 3~6분 · 조건에 따라 달라짐'], stay_3: [20, 31, '시간은 판단 수에 따라 달라짐'] };
function agRunTicker(button, teams, mode, duration) {
  const bar = button.closest('.g-runbar'); let note = document.querySelector('#agGenerationStatus');
  if (!note && bar) { note = document.createElement('p'); note.id = 'agGenerationStatus'; note.setAttribute('role', 'status'); bar.appendChild(note); }
  const t0 = Date.now(), base = teams > 1 ? `${teams}팀 가상 방문 생성 중…` : '가상 방문 생성 중…';
  const expect = AG_RUN_EXPECT[duration] || AG_RUN_EXPECT.stay_1;
  const label = (typeof HLVisitExecution!=='undefined'?HLVisitExecution.isLive(mode):mode === 'live') ? `새로운 LLM 판단 실행 중 · ${AG_RUN_LATENCY} · ${duration === 'day_visit' ? '당일' : duration.replace('stay_', '') + '박'} 방문은 보통 ${expect[0]}~${expect[1]}회(${expect[2]})${teams > 1 ? ' · 팀 수만큼 곱' : ''} · 이 화면을 떠나면 결과를 받을 수 없습니다`
    : mode === 'rules' ? '규칙 계산 중 · LLM 호출 없음' : '저장된 LLM 판단 재생 중 · 유료 호출 없음';
  if (note) note.textContent = label;
  const tick = () => { const s = Math.round((Date.now() - t0) / 1000); button.textContent = `${base} ${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  const timer = setInterval(tick, 1000); tick();
  return () => { clearInterval(timer); };
}
async function agRun() {
  if (AG.busy) return;
  if (AG.mode !== "agents" && !AG.one) { agReady(); return; }
  const ids = AG.mode === "agents" ? [...AG.many] : [AG.one];
  let generated=false; AG.lastGenerationError = null; AG.busy = true; const b = $("#agRun"); b.disabled = true; b.dataset.busy='1'; b.textContent = "계산 중…";
  agClearRunFailure();
  // The request and mode are fixed for this run: lock the controls that would change them until it ends.
  const locked=[...document.querySelectorAll('.mode-agent .cf-left select,.mode-agent .cf-left input,.mode-agent .cf-left button:not(#agRun)')].filter(x=>!x.disabled);locked.forEach(x=>x.disabled=true);
  const modeName=({rules:'규칙 계산',replay:'저장된 판단 재현',live:'실시간 AI 판단',live_improved:'실시간 AI 판단 · 개선형'})[HLVisitExecution.modeOf(AG.visitRequest)||AG.judgmentMode||'rules']||'방문 생성';
  try {
    const cond = JSON.parse(JSON.stringify(AG.cond)), auto = AG.mode === "agents" && !AG.fix;
    const ph = cond.stay ? (cond.phase || "mid") : "visit";   // 체류 단계: checkin(오후 시작 · 조식 없음) · mid(연박 중간일) · checkout(조식 뒤 체크아웃) · visit(비투숙)
    let runs, visits = null;
    if (AG.duration) {   // 선택한 전체 기간을 /api/visit duration 계약으로 전달
      b.textContent = ids.length > 1 ? `${ids.length}팀 가상 방문 생성 중…` : "가상 방문 생성 중…";
      const stopTicker = agRunTicker(b, ids.length, HLVisitExecution.modeOf(AG.visitRequest) || AG.judgmentMode || 'rules', AG.duration);
      let F; try { F = await agRunFlow(ids, cond, auto); } finally { stopTicker(); }
      runs = F.runs; visits = F.visits;
      if (!runs.length) throw new Error("이 고객은 실행 가능한 방문 행동이 없습니다. 조건을 확인해 다시 실행하세요.");
      AG.runs = runs; AG.ti = runs.length - 1; AG.res = runs[AG.ti]; AG.visits = visits;
      AG.sel = ids.length === 1 ? ids[0] : null; AG.focusLoc = null; AG.plans = F.plans; AG._sc = null; AG._rate = 0;
      AG.keep[AG.mode] = { runs, sel: AG.sel, plans: AG.plans, visits, flow: AG.flow };
      agPlanHint(); agShow(false); generated=true; document.dispatchEvent(new Event("hl:agrun")); return;
    }
    if (auto) {   // 운영자는 호텔(행사 · 가격 · 혜택)을 정하고, 고객은 자기 방문 조건(투숙 · 건물 · 박수 · 체류 단계 · 동행)을 정한다
      cond.turn = "day";
      const comp0 = {}; ids.forEach(pid => { const c = AG_COMP[pid]; if (c) comp0[pid] = { n: c.n, rel: c.rel, kids: c.rel === "family_kids", elder: c.rel === "family_parents" }; });
      b.textContent = "가상 방문 생성 중…";
      const vr = await api("/api/stay", { op: "visit", personas: ids, cond: { event: cond.event, scenario: AG.scen || "day" }, comp: comp0, seed: AG.seed || 0 });
      visits = vr.visits || {};
      const groups = {};
      ids.forEach(pid => { const v = visits[pid] || (visits[pid] = { stay: true, building: "VISTA", phase: "mid", party_size: 2, nights: 1, rel: "group", layer: "generated", why: "기본값" }); const key = `${v.stay ? 1 : 0}|${v.stay ? v.building : "-"}|${v.party_size}|${v.stay ? v.phase : "visit"}`; (groups[key] = groups[key] || { v, ids: [] }).ids.push(pid); });
      const G = Object.values(groups), byT = {}; let gi = 0;
      for (const g of G) {
        b.textContent = `가상 방문 생성 중… 조건 묶음 ${++gi}/${G.length}`;
        const gc = Object.assign({}, cond, { stay: !!g.v.stay, building: g.v.stay ? g.v.building : cond.building, party_size: g.v.party_size, phase: g.v.stay ? g.v.phase : null });
        agMergeRuns(byT, await agRunTurns(g.ids, gc, g.v.stay ? g.v.phase : "visit"), agVcOf(g.v));
      }
      runs = ["breakfast", "event", "dinner"].filter(t => byT[t]).map(t => byT[t]);
      runs.forEach(R => { R._mode = AG.mode; R._auto = true; R.conditions = Object.assign({}, R.conditions, { mixed: true }); });
    } else runs = await agRunTurns(ids, cond, ph);
    if (!runs.length) throw new Error("계산할 턴이 없습니다");
    AG.runs = runs; AG.ti = runs.length - 1; AG.res = runs[AG.ti]; AG.visits = visits;
    AG.sel = ids.length === 1 ? ids[0] : null; AG.focusLoc = null;
    b.textContent = "가상 방문 생성 중…";
    AG.plans = await agFetchPlans(ids, runs, cond, ph, visits);   // 체류·행동 계획 계층(엔진 결정 사이) — 실패하면 화면 안 간이 흐름으로
    AG.keep[AG.mode] = { runs, sel: AG.sel, plans: AG.plans, visits, flow: AG.flow };
    agPlanHint();
    agShow(false); generated=true; document.dispatchEvent(new Event("hl:agrun"));
  } catch (e) {
    AG.lastGenerationError = e.message;
    if (AG.res) agPanel();
    else $("#panel").innerHTML = '';
    $("#panel").insertAdjacentHTML('afterbegin', `<div class="callout ag-run-failure" role="alert">${esc(modeName)} 실행 실패 — ${esc(e.message)}${AG.flow ? '<br>이전 방문 결과를 유지합니다. 조건이나 판단 방식을 바꾼 뒤 다시 생성해 주세요.' : ''}</div>`);
  }
  finally { AG.busy = false; AG.runningRequest=null; locked.forEach(x=>{if(x.isConnected)x.disabled=false;});/* the mode select may have been re-rendered during the run with the busy state */{const j=document.querySelector('#agJudgment');if(j)j.disabled=false;} b.dataset.busy=''; b.disabled = (AG.mode !== "agents" && !AG.one) || b.dataset.modeBlocked==='1'; b.textContent = AG.flow ? "가상 방문 다시 생성" : "가상 방문 생성";
    const current=document.querySelector('#agRun');if(current)current.textContent=b.textContent;
    let notice=document.querySelector('#agGenerationStatus');
    if(generated){if(!notice){notice=document.createElement('p');notice.id='agGenerationStatus';notice.setAttribute('role','status');current?.closest('.g-runbar')?.appendChild(notice);}notice.textContent='가상 방문이 생성되었습니다. ▶ 재생으로 방문 흐름을 확인하세요.';}
    else if(notice)notice.remove();
  }
}

function agPlanHint() {   // §9 — 요청 계획기 · 실제 사용 계획기 · 대체 이유를 화면에서 구별
  const el = $("#agHint"); if (!el) return;
  if(AG.flow?.result?.judgment){el.textContent=HLVisitExecution.label(AG.flow.result);return;}
  if (AG.engine === "autonomy" && AG.flow) { const F = AG.flow, n = Object.keys(AG.plans || {}).length;
    el.innerHTML = `<span class="ag-plm" data-engine="${esc(F.engine.name)}">${n}팀 실행${F.intervention && F.intervention.id !== "none" ? ` · 운영 변경 <b>${esc(F.intervention.label.split("(")[0])}</b>` : ""}${(F.applied||[]).length ? ` · 메뉴 조건 반영 ${(F.applied||[]).length}` : ""}${(F.skipped||[]).length ? ` · <b class="ag-blk">조건 미반영 ${(F.skipped||[]).length}</b>` : ""}</span>${typeof sharedWorldSummary === "function" ? sharedWorldSummary(F.result) : ""}`; return; } const P = Object.values(AG.plans || {}); if (!P.length) { el.textContent = ""; return; }
  const used = {}; P.forEach(p => used[p.backend] = (used[p.backend] || 0) + 1); const req = P[0].requested, why = [...new Set(P.map(p => p.fallback_reason).filter(Boolean))];
  const blk = P.filter(p => p.status && p.status !== "ok").length, fb = P.filter(p => p.trace && p.trace.profile_fallback_used).length;
  el.innerHTML = `<span class="ag-plm${req !== "rules" && !used.llm ? " fb" : ""}">행동 계획 · 요청 <b>${req === "rules" ? "규칙" : "LLM"}</b> · 실제 <b>${used.llm ? `LLM ${used.llm}명` : ""}${used.llm && used.rules ? " · " : ""}${used.rules ? `규칙 ${used.rules}명` : ""}</b>${why.length ? ` · 대체 이유: ${esc(why.join(" / "))}` : ""}${blk ? ` · <b class="ag-blk">실행 차단 ${blk}명</b>` : ""}${fb ? ` · 프로파일 미로드 ${fb}명(일반 시연 계획)` : ""}</span>`;
}
// ---------------------------------------------------------------- 아바타(한 명 모드) — 10/24 06-A
// 팀 구성은 라이브러리 유형(type_group)에서 고른다 · 인원은 방문 조건(party_size)에 맞춘다. 사실적 인물 대신 작은 캐릭터형(머리 + 몸) · 자산이 오면 static/avatars/<key>.svg 로 교체
const AG_PARTY = {   // 관계 → 구성원(adult · child · elder) — 도형 아바타용
  solo: ["adult"], couple: ["adult", "adultB"], spouse: ["adult", "adultB"], friend: ["adult", "adultB"], family_kids: ["adult", "adultB", "child", "child"], family_parents: ["adult", "elder", "elderB"], friends: ["adult", "adultB", "adultC"],
};
// 10/24 09-C 원문에서 확인된 동행 구성 — n(인원) · rel(관계) · label(화면 문구). av 는 인원 · 관계 · 성별이 모두 확인된 경우에만(그 외는 중립 도형)
const AG_COMP = {
  A01: { n: 4, rel: "family_kids", label: "가족 4인 · 아이 동반" },
  A02: { n: 3, rel: "family_parents", label: "본인 + 부모 · 3인" },
  A03: { n: 2, rel: "couple", label: "커플 2인" },
  A04: { n: 1, rel: "solo", label: "혼자" },
  A05: { n: 3, rel: "friends", label: "친구 3인" },
  A07: { n: 2, rel: "spouse", label: "부부 2인", av: "couple_wine" },
  A10: { n: 2, rel: "friend", label: "친구 2인" },
};
function agPartyKey(pid, partySize) { const cp = agComp(pid, partySize); return cp.rel; }   // 호환
// 현재 시나리오 인원(1순위) → 확인된 동행 구성(2순위) → 맞는 자산(3순위) → 중립 인원 표시(4순위)
function agComp(pid, N) {   // CL-11 §5 — 확인된 동행(원문) · 고객이 정한 방문 조건(여러 명) · 시나리오 인원으로 관계를 정하고, 인원이 맞는 유형 그림이 있으면 쓴다(성별 확인 여부와 무관 · ⓘ 에 '실제 외모 아님')
  N = Math.max(1, +N || 1);
  const c = AG_COMP[pid], v = AG.visits && AG.visits[pid], neutral = n => Array.from({ length: n }, (_, i) => ["adult", "adultB", "adultC", "adultD", "adultE", "adultF"][i] || "adult");
  const mm = AG_AVMAP[pid];
  const rel = c && c.n === N ? c.rel : mm && mm.rel && mm.supported === N ? mm.rel : v && v.party_size === N && v.rel && v.rel !== "group" ? v.rel : N === 1 ? "solo" : "group";
  const k = agAvKey(pid, rel, N), av = k && AG.avm && AG.avm[k] ? k : null;   // 10/26 — 인원이 꼭 맞는 그림이 없으면 기본 그림(agAvFallback)으로 빠짐없이 표시
  const members = c && c.n === N ? (AG_PARTY[c.rel] || neutral(N)) : AG_PARTY[rel] && AG_PARTY[rel].length === N ? AG_PARTY[rel] : neutral(N);
  if (c && c.n === N) return { rel, n: N, label: c.label, scen: `${N}인`, members, av, src: c.label, match: true };
  const lab = v && v.party_size === N && v.rel !== "group" ? `${AG_PARTY_LABEL[rel] || rel} · ${N}인` : `${N}인 구성`;
  if (c) return { rel, n: N, label: lab, scen: `${N}인`, members, av, src: c.label, match: false };
  return { rel, n: N, label: v ? lab : `${N}인 · 동행 미확인`, scen: `${N}인`, members, av, src: null, match: false };
}
const AG_AV_COLOR = { adult: ["#a0563f", "#f2d3b8"], adultB: ["#4f6f86", "#efcfb3"], adultC: ["#7a6b4f", "#f1d2b5"], adultD: ["#6d5a7e", "#efcfb3"], adultE: ["#5f7a63", "#f2d3b8"], adultF: ["#8a6a4a", "#efcfb3"], child: ["#c98a3e", "#f5dcc4"], elder: ["#6f6a60", "#ecd6c2"], elderB: ["#8c7461", "#efd8c4"] };
function agAvatarSvg(pid, partySize, x, y, k, cls = "", o = {}) {   // 확인된 자산이 맞으면 이미지, 아니면 인원수만큼 중립 도형
  const cp = agComp(pid, partySize);
  if (cp.av) return agAvatarImg(cp.av, x, y, k, cls, o);
  k = k * (o.icon ? 1 : 1.45);   // 지도에서 이미지 아바타와 비슷한 키(약 38~40px)로
  const members = cp.members, n = members.length, gap = (n > 3 ? 12 : 14) * k, x0 = x - ((n - 1) * gap) / 2;
  const one = (m, i) => { const [cb, ch] = AG_AV_COLOR[m] || AG_AV_COLOR.adult, child = m === "child", h = child ? 19 * k : 26 * k, w = child ? 10 * k : 13 * k, r = child ? 4.5 * k : 6 * k, cx = x0 + i * gap, base = y + 1 * k;
    return `<g class="ag-avm ${m}"><ellipse class="ag-avsh" cx="${cx}" cy="${base + 1.5 * k}" rx="${w * 0.75}" ry="${2.2 * k}"/><rect x="${cx - w / 2}" y="${base - h + r * 2}" width="${w}" height="${h - r * 2}" rx="${w * 0.42}" fill="${cb}"/><circle cx="${cx}" cy="${base - h + r}" r="${r}" fill="${ch}"/></g>`; };
  const hs = agHlScale(o), tf = hs ? ` transform="translate(${x.toFixed(2)},${y.toFixed(2)})${hs} translate(${(-x).toFixed(2)},${(-y).toFixed(2)})"` : "";
  return `<g class="ag-avatar ${cls}${o.hl ? " ag-sel" : ""}" data-p="${pid}" data-party="${cp.rel}" data-n="${n}"${tf}>${members.map(one).join("")}</g>`;
}
function agAvatarIcon(pid, N, size = 52) {   // 왼쪽 카드용 대표 아바타(자산 초상 또는 중립 도형)
  const cp = agComp(pid, N);
  if (cp.av) return `<img class="ag-pcav" src="/static/avatars/${cp.av}_portrait.png" alt="" width="${size}" height="${size}">`;
  return `<svg class="ag-pcav" viewBox="0 0 60 60" width="${size}" height="${size}" aria-hidden="true">${agAvatarSvg(pid, N, 30, 50, cp.n > 3 ? 0.95 : 1.25, "", { icon: true })}</svg>`;
}
function agAvatarAsset(pid, partySize) { const cp = agComp(pid, partySize); return cp.av ? { key: cp.av, why: cp.src } : null; }
// CL-1025-37 P1 — 한 명 모드 지도 아바타 강조(그림 자체는 그대로): 이동 중 1.16배 · 정지 1.06배(발 밑 기준) · 외곽선 · 그림자는 CSS(.ag-sel)
const agHlScale = o => o && o.hl ? ` scale(${o.walk ? 1.2 : 1.08})` : "";
// No.0006's existing wine-pair strip faces right. Its third pose has clean boundaries.
// Keep source assets/mapping intact; crop only this walking render to avoid adjacent fragments.
function agAvatarRenderFrame(key,o={}) {
  const A=AG.avm[key],row=o.walk?A.side:A.front;
  if(key==='couple_wine'&&o.walk)return {x:330,y:0,w:163,h:160,sheetW:493,sheetH:160,flip:o.dir<0};
  return {x:(o.walk?(Math.floor(o.frame||0)%row.n+row.n)%row.n:0)*row.cw,y:0,w:row.cw,h:row.ch,sheetW:row.cw*row.n,sheetH:row.ch,flip:!!(o.walk&&o.dir>0)};
}
function agAvatarImg(key,x,y,k,cls='',o={}) {
  const A=AG.avm[key],f=agAvatarRenderFrame(key,o),H=(A.n_members>2?50:A.n_members===2?46:42)*k,W=H*f.w/f.h,src=`/static/avatars/${key}_${o.walk?'side':'front'}.png`;
  return `<g class="ag-avatar ag-avimg ${cls}${o.hl?' ag-sel':''}" data-av="${key}" data-walk="${o.walk?1:0}" transform="translate(${x.toFixed(2)},${y.toFixed(2)})${agHlScale(o)}"><ellipse class="ag-avsh" cx="0" cy="${1.5*k}" rx="${W*.38}" ry="${3*k}"/><g class="ag-avflip" transform="${f.flip?'scale(-1,1)':''}"><svg x="${-W/2}" y="${-H}" width="${W}" height="${H}" viewBox="${f.x} ${f.y} ${f.w} ${f.h}" overflow="hidden" preserveAspectRatio="xMidYMax meet"><image href="${src}" width="${f.sheetW}" height="${f.sheetH}"/></svg></g></g>`;
}
function agAvatarMove(el,key,x,y,o={}) {
  const f=agAvatarRenderFrame(key,o);el.setAttribute('transform',`translate(${x.toFixed(2)},${y.toFixed(2)})${agHlScale(o)}`);const fg=el.querySelector('.ag-avflip');if(fg)fg.setAttribute('transform',f.flip?'scale(-1,1)':'');const sv=el.querySelector('svg');if(sv)sv.setAttribute('viewBox',`${f.x} ${f.y} ${f.w} ${f.h}`);
}
const AG_PARTY_LABEL = { solo: "1인", couple: "커플", spouse: "부부", friend: "친구 동행", family_kids: "가족 · 아이 동반", family_parents: "가족 · 부모 동반", friends: "친구 모임", group: "일행" };
// ---------------------------------------------------------------- 출발 → 선택 장소 (시나리오 입력 → 엔진 결과)
function agStart(R, pid) { const V = agVC(pid, R); return V.stay ? `${V.B}_ROOM` : "HOTEL_GATE"; }
function agStartName(R, pid) { const V = agVC(pid, R); return V.stay ? `${V.bl} 객실` : "호텔 도착 (정문)"; }
const agCustOf = (run, pid) => run ? (run.customers.find(x => x.persona_id === pid) || (run.customers.length === 1 && !agIsMany(run) ? run.customers[0] : null)) : null;
const agAnyCust = pid => { for (const R of (AG.runs.length ? AG.runs : [AG.res])) { const c = R && R.customers.find(x => x.persona_id === pid); if (c) return c; } return null; };
const agAllIds = () => AG.visits ? Object.keys(AG.visits) : (AG.res ? AG.res.customers.map(c => c.persona_id) : []);
// 고객별 방문 조건(보충2) — 여러 명 자율 모드는 고객 객체의 vc, 그 외는 공통 조건
const agVcOf = v => ({ stay: !!v.stay, B: v.stay ? v.building : null, bl: v.stay ? ((AG.meta && AG.meta.buildings && AG.meta.buildings[v.building]) || v.building) : "", party: v.party_size, phase: v.stay ? v.phase : "visit", nights: v.nights, v });
function agVC(pid, R) {
  R = R || AG.res;
  let c = pid ? agCustOf(R, pid) : null;
  if (!(c && c.vc) && pid && AG.visits) c = agAnyCust(pid);
  if (c && c.vc) return c.vc;
  return { stay: !!R.conditions.stay, B: R.conditions.stay ? R.building.id : null, bl: R.building.label, party: R.conditions.party_size, phase: R.conditions.stay ? (R.conditions.phase || "mid") : "visit", v: null };
}
// i 번째 턴으로 가는 구간 — 첫 턴은 출발 위치(시나리오 입력)에서, 다음 턴은 직전 턴의 선택 장소에서
function agSeg(pid, i) {
  const R = (AG.runs.length ? AG.runs[i] : AG.res), c = agCustOf(R, pid); if (!c) return { same: true };
  const pc = i > 0 ? agCustOf(AG.runs[i - 1], pid) : null, a = pc ? pc.choice.map_loc : agStart(R, pid), b = c.choice.map_loc;
  const aName = pc ? (pc.choice.venue_id === "ROOM_MEAL" ? `${agVC(pid, R).bl} 객실` : pc.choice.venue_label) : agStartName(R, pid);
  if (!LOC[a] || !LOC[b] || a === b) return { a, b, aName, same: a === b };
  const r = route(a, b);
  return { a, b, aName, r, ...markerPath(a, b, r) };
}
function agPath(c) { return agSeg(c.persona_id, AG.ti); }
const agCur = () => { const R = AG.res; return R ? (R.customers.find(x => x.persona_id === AG.sel) || (AG.sel && AG.visits ? agAnyCust(AG.sel) : null) || (agIsOne(R) ? R.customers[0] : null)) : null; };

// ---------------------------------------------------------------- 하루 장면(10/24 08-C) — 결정 턴(엔진) 사이를 흐름 구간으로 잇는다
// 장면 종류: start(시나리오 입력 · 출발) · move(표시용 연결) · turn(엔진 결과 · 여기서 멈춤) · flow(턴 사이 · 성향 기반 구성 · 엔진 계산 아님 · 실제 관측 아님)
// 흐름 구간의 장소는 프로필 성향 두 가지(휴식 · 공간)와 투숙 여부만으로 고르며 규칙을 화면(ⓘ · 상세)에 그대로 적는다. 구매 · 식사 · 음주 같은 사건은 만들지 않는다.
const agMin = t => { const m = /^(\d{1,2}):(\d{2})/.exec(t || ""); return m ? +m[1] * 60 + +m[2] : null; };
const agHM = m => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(Math.round(m) % 60).padStart(2, "0")}`;
const AG_TURN_DUR = { breakfast: 60, event: 75, dinner: 90 };   // 턴 칸의 화면 길이(분) — 체류 시간을 계산한 값이 아니라 시간 바 표시용
const AG_FLOW_RULE = "흐름 구간 규칙(성향 기반 · 엔진 계산 아님): 공간 · 풍경 성향 0.5 이상 → 정원 산책, 휴식 성향 0.5 이상(투숙) → 객실 휴식, 그 외 → 호텔 둘러보기. 점심 · 낮 시간은 엔진 턴이 없어 식사 여부 · 장소를 계산하지 않고 호텔 안에 머무는 것으로만 표시합니다. 저녁 뒤는 투숙이면 객실 복귀, 비투숙이면 귀가.";
if (typeof LOC !== "undefined" && !LOC.AG_GARDEN) { LOC.AG_GARDEN = S([600, 352]); ANCHOR.AG_GARDEN = "d2"; }   // 더글라스 가든 산책 지점(그림 라벨 자리 · 표시용)
function agLvl(c, k) { const b = ((c.persona || {}).bars || []).find(x => x.key === k); return b && b.level != null ? b.level : 0; }
function agFlowSpot(c, R, slot, prevLoc, used) {
  const V = agVC(c.persona_id, R), stay = V.stay, B = V.B || "GRAND", room = `${B}_ROOM`, lobby = LOC[`${B}_LOBBY`] ? `${B}_LOBBY` : "GRAND_LOBBY", BL = V.bl || R.building.label;
  const rest = agLvl(c, "rest_need") >= 0.5, space = agLvl(c, "space") >= 0.5;
  const walk = { loc: "AG_GARDEN", label: "정원 산책", short: "정원 산책", name: "더글라스 가든", why: "공간 · 풍경 성향" }, rm = { loc: room, label: "객실 휴식", short: "객실 휴식", name: `${BL} 객실`, why: "휴식 성향" }, lb = { loc: lobby, label: "호텔 둘러보기", short: "둘러보기", name: `${BL.replace(" 워커힐", "")} 로비 주변`, why: "기본 흐름" };
  if (slot === "am") return space ? walk : rest && stay ? rm : lb;
  if (slot === "noon") return Object.assign({}, lb, { label: "점심 · 낮 시간", short: "점심 · 낮", why: "엔진 턴 없음 · 식사 여부 · 장소 계산 안 함" });
  if (slot === "pm") return rest && stay ? rm : space && !(used && used.has("AG_GARDEN")) ? walk : stay ? Object.assign({}, rm, { label: "객실에서 잠시 휴식", short: "객실 휴식", why: "투숙 기본 흐름" }) : lb;
  if (slot === "eve") return stay ? Object.assign({}, rm, { label: "객실 복귀 · 휴식", short: "객실 복귀", why: "투숙 기본 흐름" }) : { loc: "HOTEL_GATE", label: "귀가", short: "귀가", name: "정문", why: "비투숙 기본 흐름" };
  return Object.assign({}, lb, { label: slot === "gap" ? "다음 일정 전 · 잠시 머무름" : "자유 시간", short: slot === "gap" ? "잠시 머무름" : "자유 시간", why: "기본 흐름" });
}
// 10/24 09-H 후기 근거 중간 장면 — 라이브러리 구조화 사실 중 워커힐 방문의 시설 이용(수영장 · 족욕 · 포레스트 산책 · 사우나 · 정원)만.
//   식사 · 구매 · 라운지(식음) · 기대/거절 사실은 쓰지 않는다. 이번 시뮬레이션에서 실제로 이용했다는 뜻이 아니라 '이전 방문 경험'을 흐름 장소로 쓰는 것.
const AG_EVK = [
  { k: "pool", re: /수영|swim|pool|실내 ?풀|풀장/, loc: B => (B === "VISTA" ? "VISTA_POOL" : "GRAND_POOL"), label: "수영장 이용", short: "수영장", name: B => (B === "VISTA" ? "비스타 수영장" : "그랜드 수영장") },
  { k: "foot", re: /족욕|footbath/, loc: () => "SKYARD", label: "스카이야드 족욕", short: "족욕", name: () => "스카이야드" },
  { k: "forest", re: /포레스트|forest/, loc: () => "FOREST_PARK", label: "포레스트 파크 산책", short: "포레스트", name: () => "포레스트 파크" },
  { k: "sauna", re: /사우나|피트니스|sauna|fitness|gym/, loc: () => "WELLNESS_SAUNA", label: "사우나 · 피트니스", short: "사우나", name: () => "그랜드 웰니스" },
  { k: "garden", re: /정원|garden/, loc: () => "AG_GARDEN", label: "정원 산책", short: "정원 산책", name: () => "더글라스 가든" },
];
function agEvidenceSpots(pid, R, avoid) {
  const lp = typeof libP === "function" && typeof LIBV !== "undefined" && LIBV.data ? libP(pid) : null, F = lp && lp.engine && lp.engine.facts; if (!F) return [];
  const B = agVC(pid, R).B || "GRAND", out = [], seen = new Set();
  for (const [fid, f] of Object.entries(F)) {
    if (!f.wh || f.hidden || ["expectation", "decline", "motive", "purchase"].includes(f.kind)) continue;
    const txt = `${f.gist || ""} ${(f.features || []).join(" ")}`;
    if (/안 ?했|못 ?했|하지 않|않았|취소|대신|not_/.test(txt)) continue;   // 이용하지 않은 경험은 제외
    for (const E of AG_EVK) {
      if (!E.re.test(txt)) continue;
      const loc = E.loc(B); if (avoid.has(loc) || !LOC[loc]) break;
      const hint = /오전|아침|_am\b|\bam\b/.test(txt) ? "am" : /오후|_pm\b|\bpm\b/.test(txt) ? "pm" : /밤|야간|night|야경/.test(txt) ? "night" : null;
      const o = seen.has(E.k) ? out.find(x => x.k === E.k) : null;
      if (o) { o.fids.push(fid); if (!o.hint && hint) o.hint = hint; break; }
      seen.add(E.k); out.push({ k: E.k, loc, label: E.label, short: E.short, name: E.name(B), fids: [fid], hint, src: "review" }); break;
    }
  }
  return out.filter(x => x.hint !== "night").sort((a, b) => b.fids.length - a.fids.length);
}
function agScenesLegacy(pid) {   // (대체) 계획 계층이 없을 때의 간이 흐름 — pid 없음(여러 명) → 장소 없는 공통 시간표
  const runs = AG.runs.length ? AG.runs : (AG.res ? [AG.res] : []); if (!runs.length) return [];
  const key = (pid || "*") + "|" + runs.map(r => r.turn + (r.time || "")).join(",") + "|" + runs.length;
  if (AG._sc && AG._sc.key === key) return AG._sc.list;
  const R0 = runs[0], stay = agVC(pid, R0).stay, c0 = pid ? agCustOf(R0, pid) : null;
  const S0 = [], tFirst = agMin(R0.time) || (R0.turn === "breakfast" ? 510 : R0.turn === "event" ? 990 : 1110);
  const startLoc = agStart(R0, pid), startAt = stay ? tFirst - 60 : tFirst - 45;
  let s = { k: "start", ti: 0, t0: startAt, t1: startAt + (stay ? 45 : 30), loc: startLoc, label: stay ? "출발 준비" : "호텔 도착", name: agStartName(R0, pid), src: "input" };
  S0.push(s);
  let prevLoc = startLoc, prevEnd = s.t1, prevC = null; const usedLoc = new Set();
  const EV = pid ? agEvidenceSpots(pid, R0, new Set(runs.map(R => (agCustOf(R, pid) || { choice: {} }).choice.map_loc).filter(Boolean))) : [];
  const takeEv = slot => { if (slot !== "am" && slot !== "pm" && slot !== "gap") return null; const i = EV.findIndex(x => !x.hint || x.hint === slot || slot === "gap"); return i >= 0 ? EV.splice(i, 1)[0] : null; };
  const mv = (a, b, ti, t1) => { if (!pid || !LOC[a] || !LOC[b] || a === b) return null; const r = route(a, b); const mp = markerPath(a, b, r); if (!mp.mk || !mp.mk.total) return null; return { k: "move", ti, t0: t1 - 15, t1, a, b, r, mk: mp.mk, label: "이동", src: "link" }; };
  const fill = (t0, t1, ti, c, R) => {   // 턴 사이 흐름 — 길면 오전 · 점심 · 오후로 나눈다
    const out = [], len = t1 - t0; if (len < 40) return out;
    const spots = [];
    if (len >= 150 && t0 < 705 && t1 > 810) { if (705 - t0 >= 40) spots.push(["am", t0, 705]); spots.push(["noon", Math.max(t0, 705), Math.min(t1, 810)]); if (t1 - 810 >= 40) spots.push(["pm", 810, t1]); }
    else spots.push([t0 >= 1200 ? "eve" : t0 >= 780 ? "pm" : t0 >= 690 ? "noon" : len < 75 ? "gap" : "am", t0, t1]);
    for (const [slot, a, b] of spots) { const evs = c ? takeEv(slot) : null; const sp = evs ? Object.assign({ why: evs.hint ? `후기 경험 · ${evs.hint === "am" ? "오전" : "오후"} 이용` : "후기 경험 · 시각 미확인(시간대 추정)" }, evs) : c ? agFlowSpot(c, R, slot, prevLoc, usedLoc) : { loc: null, label: slot === "noon" ? "점심 · 낮" : slot === "eve" ? "저녁 이후" : slot === "gap" ? "잠시 머무름" : "자유 시간", why: "성향 기반 흐름 · 계산 없음" };
      const sc = { k: "flow", ti, t0: a, t1: b, slot, loc: sp.loc, label: sp.label, short: sp.short || sp.label, name: sp.name, why: sp.why, src: sp.src === "review" ? "review" : "assumed", fids: sp.fids || null, hint: sp.hint || null };
      if (pid && sp.loc && prevLoc && sp.loc !== prevLoc && LOC[sp.loc] && LOC[prevLoc]) { const r = route(prevLoc, sp.loc), mp = markerPath(prevLoc, sp.loc, r); if (mp.mk && mp.mk.total && !r.unknown) { sc.mk = mp.mk; sc.from = prevLoc; } }
      out.push(sc); if (sp.loc) { prevLoc = sp.loc; usedLoc.add(sp.loc); } }
    return out;
  };
  runs.forEach((R, i) => {
    const c = pid ? agCustOf(R, pid) : null, t0 = agMin(R.time) || tFirst, loc = c ? c.choice.map_loc : null;
    const gapEnd = t0 - 15;
    if (i > 0) S0.push(...fill(prevEnd, Math.max(prevEnd, gapEnd), i - 1, prevC, runs[i - 1]));
    const m = loc ? mv(prevLoc, loc, i, t0) : null; if (m) S0.push(m);
    S0.push({ k: "turn", ti: i, t0, t1: t0 + (AG_TURN_DUR[R.turn] || 60), loc, label: AG_TURN[R.turn], src: "engine" });
    prevLoc = loc || prevLoc; prevEnd = t0 + (AG_TURN_DUR[R.turn] || 60); prevC = c;
  });
  const last = runs[runs.length - 1], cl = pid ? agCustOf(last, pid) : null;
  if (cl || !pid) { const sp = cl ? agFlowSpot(cl, last, "eve", prevLoc) : { loc: null, label: "저녁 이후", short: "저녁 이후", why: "성향 기반 흐름 · 계산 없음" }; const sc = { k: "flow", ti: runs.length - 1, t0: prevEnd, t1: Math.max(prevEnd + 60, 1320), slot: "eve", loc: sp.loc, label: sp.label, short: sp.short || sp.label, name: sp.name, why: sp.why, src: "assumed" };
    if (pid && sp.loc && prevLoc && sp.loc !== prevLoc && LOC[sp.loc] && LOC[prevLoc]) { const r = route(prevLoc, sp.loc), mp = markerPath(prevLoc, sp.loc, r); if (mp.mk && mp.mk.total && !r.unknown) { sc.mk = mp.mk; sc.from = prevLoc; } }
    S0.push(sc); }
  S0.forEach((x, i) => x.si = i);
  AG._sc = { key, list: S0 }; return S0;
}
// 계획 계층의 장면(stay_run) → 화면 장면. 활동 사이 이동은 도착 시각 앞 travel 분 동안(지도 길을 따라 표시용 연결).
const AG_ACT_SHORT = { wake: "기상", unpack: "짐 정리", room_rest: "객실 휴식", room_nap: "아이와 휴식", room_bath: "욕조 휴식", room_snack: "객실 간식", pool: "수영장", sauna: "사우나", fitness: "피트니스", footbath: "족욕", night_footbath: "야경 족욕",
  forest_walk: "포레스트", garden_walk: "정원 산책", riverpark: "리버파크", tennez: "테네즈 파크", cafe: "카페", bakery: "빵 · 음료", lounge: "라운지", library: "라이브러리", theatre: "빛의 시어터",
  lunch_ondal: "점심 · 온달", lunch_geumryong: "점심 · 금룡", lunch_myongwol: "점심 · 명월관", lunch_moegi: "점심 · 모에기", lunch_pizzahill: "점심 · 피자힐", lunch_bakery: "점심 · 빵", lunch_cafe: "점심 · 카페", lunch_room: "점심 · 객실", lunch_skip: "점심 건너뜀", lunch_outside: "점심 · 외부",
  luxbar: "럭스바", night_walk: "저녁 산책", room_night: "객실 복귀", checkin: "체크인", checkout: "체크아웃", pack: "짐 정리", arrive: "도착", leave: "귀가", sleep: "하루 마무리",
  SKYARD: "족욕", SKYARD_NIGHT: "야경 족욕", POOL: "수영장", SAUNA: "사우나", ROOM_REST: "객실 휴식", FOREST_WALK: "포레스트", ROOM_MEAL: "룸서비스", SIMPLE_MEAL_VIEW: "빵 · 야경", PIZZA_HILL: "피자힐", MYONGWOLGWAN: "명월관", ONDAL: "온달", GEUMRYONG: "금룡", THE_BUFFET: "더뷔페",
  "WINE_FAIR:check": "와인페어 안내", "PIZZA_HILL:full": "피자힐 마감", "POOL:full": "수영장 마감", idle: "쉬어 감", wait: "여유 시간", lunch_skip: "점심 건너뜀" };
const AG_ACT_ICON = { wake: "start", unpack: "home", room_rest: "rest", room_nap: "rest", room_bath: "rest", room_snack: "noon", pool: "pool", sauna: "sauna", fitness: "sauna", footbath: "foot", night_footbath: "foot", forest_walk: "forest", garden_walk: "garden", riverpark: "walk", tennez: "walk",
  cafe: "noon", bakery: "noon", lounge: "lobby", library: "rest", theatre: "lobby", luxbar: "noon", night_walk: "walk", room_night: "home", checkin: "lobby", checkout: "lobby", pack: "home", arrive: "start", leave: "move", sleep: "rest",
  SKYARD: "foot", SKYARD_NIGHT: "foot", POOL: "pool", SAUNA: "sauna", ROOM_REST: "rest", FOREST_WALK: "forest", ROOM_MEAL: "noon", SIMPLE_MEAL_VIEW: "noon", "WINE_FAIR:check": "lobby", "PIZZA_HILL:full": "noon", "POOL:full": "pool", idle: "rest", wait: "lobby" };
function agScenes(pid) {
  const runs = AG.runs.length ? AG.runs : (AG.res ? [AG.res] : []); if (!runs.length) return [];
  const pm = pid && AG.plans && AG.plans[pid];
  if (pm && pm.status && pm.status !== "ok") return agScenesBlocked(pid, pm, runs);   // 월드 검증에서 실행 차단 · 프로파일 미로드 — 간이 흐름으로 대신 재생하지 않는다
  const plan = pm && pm.scenes; if (!plan || !plan.length) return agScenesLegacy(pid);
  const key = "plan|" + pid + "|" + (AG.flow?.ledger?.run_id || "") + "|" + (AG.visitDay || 1) + "|" + runs.map(r => r.turn + (r.time || "")).join(",") + "|" + plan.length + "|" + (AG.plans[pid].backend || "");
  if (AG._sc && AG._sc.key === key) return AG._sc.list;
  const R0 = runs[0], S0 = [];
  let prev = null;
  plan.forEach((ps, i) => {
    const ti = ps.layer === "engine" ? Math.max(0, runs.findIndex(r => r.turn === ps.turn && (!ps.visit_day || !r.visit_day || r.visit_day === ps.visit_day))) : (prev ? prev.ti : 0);
    const loc = LOC[ps.loc] ? ps.loc : (prev ? prev.loc : agStart(R0, pid));
    if (prev && prev.loc !== loc && LOC[prev.loc] && LOC[loc]) {   // 이동 장면 — 도착 시각 앞 travel 분(앞 장면 끝보다 이르지 않게)
      const r = route(prev.loc, loc), mp = markerPath(prev.loc, loc, r);
      if (mp.mk && mp.mk.total && !r.unknown) { const tr = Math.max(4, Math.min(ps.travel || 8, ps.t0 - prev.t1 > 0 ? ps.t0 - prev.t1 : 8)); S0.push({ k: "move", ti, t0: Math.max(prev.t1, ps.t0 - tr), t1: ps.t0, a: prev.loc, b: loc, r, mk: mp.mk, label: "이동", src: "link" }); }
    }
    const base = { ti, t0: ps.t0, t1: ps.t1, loc, act: ps.act, label: ps.label, short: AG_ACT_SHORT[ps.act] || ps.label, name: agPlaceName(loc, runs[ti]), why: agWhySafe(ps.why, ps.turn ? agTurnGround(runs, ps.turn, pid, ps.visit_day) : agScGround(ps.basis)), why_raw: ps.why, basis: ps.basis || {}, cond_dep: !!ps.cond_dep, consume: !!ps.consume, kind: ps.kind, icon: AG_ACT_ICON[ps.act] || "walk", meal: ps.meal || null, visit_day: ps.visit_day || null, visit_date: ps.visit_date || null, day_phase: ps.day_phase || null };
    if (ps.layer === "engine") S0.push(Object.assign(base, { k: "turn", src: "engine", key: true, label: AG_TURN[ps.turn] || ps.label }));
    else if (i === 0) S0.push(Object.assign(base, { k: "start", src: "input", name: agPlaceName(loc, R0) }));
    else S0.push(Object.assign(base, { k: "flow", src: ps.layer === "review" ? "review" : "generated", slot: ps.meal === "lunch" ? "noon" : ps.t0 >= 1200 ? "eve" : ps.t0 >= 780 ? "pm" : "am", fids: (ps.basis && ps.basis.facts) || null }));
    prev = S0[S0.length - 1];
  });
  S0.forEach((x, i) => x.si = i);
  AG._sc = { key, list: S0 }; return S0;
}
function agScenesBlocked(pid, pm, runs) {   // 차단된 계획 — 재생할 장면 없이 시작 위치에 '실행 차단'만 둔다(이유는 패널 · 드로어에)
  const key = "blocked|" + pid + "|" + (pm.status || ""); if (AG._sc && AG._sc.key === key) return AG._sc.list;
  const loc = agStart(runs[0], pid), why = (pm.validation && pm.validation.final && pm.validation.final.issues || []).filter(x => x.severity === "blocked").map(x => x.msg).slice(0, 3).join(" / ") || pm.error || "월드 검증 실패";
  const S0 = [{ k: "start", si: 0, ti: 0, t0: 9 * 60, t1: 22 * 60, loc, label: "계획 실행 차단", short: "실행 차단", name: agPlaceName(loc, runs[0]), why, src: "blocked", basis: {}, icon: "start", blocked: true }];
  AG._sc = { key, list: S0 }; return S0;
}
const agScene = () => { const L = agScenes(AG.sel || (AG.res && agIsOne(AG.res) ? AG.res.customers[0].persona_id : null)); return L[AG.si] || null; };
// 10/24 09-D 재생 — '하루 시간 진행'(머무름: 시간에 비례)과 '장소 간 이동 애니메이션'(길 길이에 비례)을 따로 정한다. 엔진 시각 · 결과와 무관한 화면 연출.
// 10/24 보충1 수정본 — 재생: 하루 시간은 '분 → 초' 비율(기본 하루 전체 약 150초)로 흐르고, 이동은 길 길이에 비례(4~9초), 주요 결정은 자동으로 잠시 머문 뒤 이어진다
const AG_SPEED = { slow: 1.6, normal: 1, fast: 0.5 };
const AG_PACE = { daySec: 150, keyHold: 9000, consumeMin: 4000, walkMin: 4000, walkMax: 9000, walkBase: 2500, walkPerUnit: 7, flowMin: 2800, restMax: 7000, flowMax: 12000, start: 2500 };
function agDayRate() {   // 분/초
  const c = agCur(), L = c ? agScenes(c.persona_id) : agScenes(null); if (!L.length) return 6;
  const stay = L.filter(x => x.k !== "move").reduce((a, x) => a + (x.t1 - x.t0), 0);
  return Math.max(3, stay / AG_PACE.daySec);
}
const agWalkMs = mk => Math.max(AG_PACE.walkMin, Math.min(AG_PACE.walkMax, AG_PACE.walkBase + (mk ? mk.total : 0) * AG_PACE.walkPerUnit));
function agSceneDur(sc) {   // 화면 연출 길이(ms) — 모델 시각 · 이동 시간과 무관
  const m = AG_SPEED[AG.speed || "normal"] || 1, rate = AG._rate || (AG._rate = agDayRate());
  if (sc.k === "start") { sc._wf = 0; return AG_PACE.start * m; }
  if (sc.k === "move") { sc._wf = 1; return agWalkMs(sc.mk) * m; }
  const mins = Math.max(5, sc.t1 - sc.t0), raw = (mins / rate) * 1000;
  if (sc.k === "turn") { sc._wf = 0; return Math.max(AG_PACE.keyHold, Math.min(raw, AG_PACE.keyHold * 1.4)) * m; }
  sc._wf = 0;
  const cap = sc.kind === "rest" ? AG_PACE.restMax : AG_PACE.flowMax, floor = sc.consume ? AG_PACE.consumeMin : AG_PACE.flowMin;
  return Math.max(floor, Math.min(cap, raw)) * m;
}
function agPlanMs(pid, fromSi, toTurn) {   // 검수용 — 장면 구간의 예상 재생 시간(ms)
  const L = agScenes(pid); let t = 0; for (let i = fromSi; i < L.length; i++) { if (L[i].k === "turn" && i !== fromSi && toTurn) break; t += agSceneDur(L[i]); } return t;
}
// 재생 — 하루가 끝까지 흐른다. 주요 결정(엔진 턴)에서는 자동으로 잠시 머물렀다가 이어간다(멈추지 않음). 일시정지하면 그 자리에서 계속.
function agPlayFrom(si, f0 = 0, opt = {}) {
  cancelAnimationFrame(AG.raf);
  const c = agCur(); if (!c) return;
  const L = agScenes(c.persona_id); if (!L.length) return;
  si = Math.max(0, Math.min(L.length - 1, si));
  AG.playing = true; AG.paused = false; agStripState();
  let i = si, d = agSceneDur(L[i]), t0 = performance.now() - (d ? f0 * d : 0);
  const stopAtTurn = !!opt.stopAtTurn;
  const step = now => {
    let e = now - t0;
    while (e >= d) { if (stopAtTurn && L[i].k === "turn" && i !== si) break; e -= d; i++; t0 = now - e; if (i >= L.length) { i = L.length - 1; agSetScene(L[i].si, 1); if (agAdvanceVisitDay()) return; AG.playing = false; AG.ended = true; agStripState(); return; } d = agSceneDur(L[i]); }
    const sc = L[i];
    if (stopAtTurn && sc.k === "turn" && e >= d) { agSetScene(sc.si, 1); AG.playing = false; agStripState(); return; }
    const f = d ? Math.min(1, e / d) : 1;
    agSetScene(sc.si, sc.k === "move" ? f * f * (3 - 2 * f) : f);
    AG.raf = requestAnimationFrame(step);
  };
  AG.raf = requestAnimationFrame(step);
}
function agPlay(fromTi) {   // 호환 — 처음부터 재생(실행 직후)
  const c = agCur(); if (!c) return;
  AG._rate = null; AG.ended = false;
  agPlayFrom(0);
}
function agPause() { cancelAnimationFrame(AG.raf); AG.playing = false; AG.paused = true; if (AG.manyAnim) AG.manyAnim.paused = true; agStripState(); }
function agPlayToggle() {   // ▶ 재생 / ❚❚ 일시정지 / ▶ 계속
  if (AG.playing) return agPause();
  if (AG.res && agIsMany(AG.res)) return AG.ended ? agRestart() : agPlayManyTime();
  const c = agCur(); if (!c) return; const L = agScenes(c.persona_id), sc = L[AG.si];
  if (!sc || AG.ended) return agRestart();
  agPlayFrom(AG.si, sc.k === "start" ? 0 : (AG.f || 0));
}
function agSkipNext() {   // ⏭ 다음 주요 장면(엔진 결정)으로 — 보조 조작
  cancelAnimationFrame(AG.raf); AG.playing = false; AG.paused = false;
  const n = Math.max(AG.runs.length, 1);
  if (AG.res && agIsMany(AG.res)) { agManyStop(); agSetAt("turn", null, AG.at === "turn" ? (AG.ti + 1) % n : AG.ti); agStripState(); return; }
  const c = agCur(); if (!c) return; const L = agScenes(c.persona_id);
  let j = L.findIndex((x, i) => x.k === "turn" && i > (AG.si == null ? -1 : AG.si));
  if (j < 0) j = L.findIndex(x => x.k === "turn");
  if(j<0)j=L.findIndex((x,i)=>i>(AG.si??-1)&&(x.basis?.decision||(x.basis?.m4?.decision_packet_ids||[]).length));
  if(j>=0)agSetScene(j, 1); agStripState();
}
function agRestart() {   // ↺ 전체 방문 처음부터
  if (AG.visitData) agVisitDaySelect(AG.visitData.visit_days[0].day_index);
  if (AG.res && agIsMany(AG.res)) { agManyStop(); AG.manyT = null; return agPlayManyTime(true); }
  AG.ended = false; agPlayFrom(0);
}
function agPlayNext() { return agSkipNext(); }   // 호환
// ---------------------------------------------------------------- 여러 명 — 공통 시간축 위에서 각자의 계획대로 움직인다(시간 구동)
function agManyWindow() {
  const ids = agAllIds();
  let a = Infinity, b = -Infinity;
  ids.forEach(pid => { const L = agScenes(pid); if (L.length) { a = Math.min(a, L[0].t0); b = Math.max(b, L[L.length - 1].t1); } });
  if (!isFinite(a)) { a = 7 * 60; b = 22 * 60; }
  return [a, b];
}
function agManyPos(pid, T) {   // 시각 T 의 위치 · 상태 {loc, pos, moving, sc, f}
  const L = agScenes(pid); if (!L.length) return null;
  if (AG.visits && (T < L[0].t0 - 0.01 || T > L[L.length - 1].t1 + 0.01)) return { away: T < L[0].t0 ? "pre" : "post", sc: T < L[0].t0 ? L[0] : L[L.length - 1] };   // 자율 모드 — 자기 체류 창 밖(도착 전 · 퇴실 뒤)
  let cur = null, prevStay = null;
  for (const sc of L) { if (sc.k === "move") continue; if (sc.t0 <= T) { prevStay = cur; cur = sc; } else break; }
  if (!cur) { const f0 = L.find(x => x.k !== "move"); return { loc: f0.loc, pos: LOC[f0.loc], moving: false, sc: f0, f: 0 }; }
  if (T < cur.t1 || cur === L[L.length - 1]) return { loc: cur.loc, pos: LOC[cur.loc], moving: false, sc: cur, f: Math.min(1, (T - cur.t0) / Math.max(1, cur.t1 - cur.t0)) };
  const nxt = L.slice(L.indexOf(cur) + 1).find(x => x.k !== "move"); if (!nxt) return { loc: cur.loc, pos: LOC[cur.loc], moving: false, sc: cur, f: 1 };
  const mv = L.slice(L.indexOf(cur) + 1).find(x => x.k === "move" && x.t1 <= nxt.t0 + 1);
  if (mv && T >= mv.t0 && mv.mk) { const f = (T - mv.t0) / Math.max(1, mv.t1 - mv.t0), ff = f * f * (3 - 2 * f); return { loc: null, pos: along(mv.mk, ff), moving: true, sc: mv, f: ff, to: nxt }; }
  return { loc: cur.loc, pos: LOC[cur.loc], moving: false, sc: cur, f: 1, idle: true };
}
function agManyStop() { cancelAnimationFrame(AG.raf); AG.playing = false; AG.manyMoving = false; AG.manyAnim = null; $("#agent").classList.remove("ag-moving"); $("#map").classList.remove("ag-many-live"); }
function agPlayManyTime(restart) {
  cancelAnimationFrame(AG.raf);
  const R = AG.res; if (!R) return;
  const [wa, wb] = agManyWindow();
  const turnTimes = (AG.runs.length ? AG.runs : [R]).map((r, i) => [agMin(r.time), i]).filter(x => x[0] != null).sort((a, b) => a[0] - b[0]);
  const m = AG_SPEED[AG.speed || "normal"] || 1, rate = Math.max(3, (wb - wa) / 170);   // 분/초 — 여러 명은 하루 약 170초 + 주요 결정 머무름
  let T = restart || AG.manyT == null ? wa : AG.manyT;
  if (T >= wb - 1) T = wa;
  AG.manyMoving = true; AG.playing = true; AG.paused = false; AG.manyAnim = { paused: false }; agStripState(); $("#map").classList.add("ag-many-live");
  let last = performance.now(), hold = 0, held = new Set(AG.manyHeld || []);
  if (restart) held.clear();
  AG.manyHeld = held;
  const step = now => {
    const dt = (now - last) / 1000; last = now;
    if (hold > 0) { hold -= dt * 1000; if (hold <= 0) { $("#agent").classList.remove("ag-moving"); } AG.raf = requestAnimationFrame(step); return; }
    T += dt * rate / m; AG.manyT = T; AG.nowMin = T;
    const tt = turnTimes.find(([t, i]) => T >= t && !held.has(i));   // 주요 결정 시각 — 모두의 선택을 핀으로 보여 주며 잠시 머문다(자동 이어짐)
    if (tt) { held.add(tt[1]); T = tt[0]; AG.manyT = T; AG.nowMin = T; agManyDraw(T, tt[1]); agSetAt("turn", null, tt[1]); AG.nowMin = T; agClock(); agStripState(); hold = AG_PACE.keyHold * m; AG.raf = requestAnimationFrame(step); return; }
    agManyDraw(T); agClock(); agStripNow(T);
    if (T >= wb) { if (agAdvanceVisitDay()) return; AG.playing = false; AG.manyMoving = false; AG.manyAnim = null; AG.ended = true; agStripState(); return; }
    AG.raf = requestAnimationFrame(step);
  };
  AG.raf = requestAnimationFrame(step);
}
function agManyDraw(T, holdTi) {   // CL-12 — 3명 이상 모인 곳은 인원 집합(누르면 펼침), 1~2명은 ID 원, 고른 고객은 초상 + 붉은 테두리, 고른 고객의 현재 이동은 붉은 점선 · 다음 이동은 옅은 점선
  const R = AG.res; if (!R) return; const k = typeof mapK === "function" ? mapK() : 1;
  const O = agOpsAt(T);
  if (AG.openLoc && !String(AG.openLoc).startsWith("MV:") && !O.byLoc[AG.openLoc]) AG.openLoc = null;   // CL-1024-16 — 모두 떠난 자리의 펼침은 닫음(다시 모여도 집합부터)
  let g = `<defs><clipPath id="agClipC" clipPathUnits="objectBoundingBox"><circle cx=".5" cy=".5" r=".5"/></clipPath></defs>`, top = "";
  const pins = [];   // 개별 마커 — 그린 뒤 서로 겹치면 살짝 밀어낸다(알약 폭 기준)
  const obs = [], clus = [];    // CL-1024-15 — 인원 집합은 움직이지 않는 장애물(개별 마커가 집합을 덮던 문제) · 같은 자리에 겹친 집합(스카이야드 · 비스타 객실)은 서로 비켜 그림
  for (const L of Object.values(O.byLoc)) {
    const at = LOC[L.loc]; if (!at) continue;
    const others = L.ids.filter(id => id !== AG.sel), hasSel = L.ids.includes(AG.sel), open = AG.openLoc === L.loc;
    if (others.length >= 3 && !open) {
      clus.push({ loc: L.loc, ids: others, cats: others.map(id => O.cur[id].cat), x: at[0], y: at[1], sel: hasSel ? AG.sel : null, selCat: hasSel ? O.cur[AG.sel].cat : null });
      continue;
    }
    const ids = hasSel ? [...others, AG.sel] : others, n = ids.length, rr = n > 1 ? Math.max(14, (open ? 30 : 22) * n / (2 * Math.PI)) * k : 0;
    const cols = Math.min(3, n), rows = Math.ceil(n / cols);   // 펼친 집합 = 앵커 아래 3열 격자(ID 를 읽을 수 있는 간격)
    const slot = id => { let h = 0; for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return (h % 360) / 360; };   // CL-1024-16 — 둘레 자리 각도를 ID 로 고정(구성원이 드나들어도 남은 고객이 튀지 않게 · 겹치면 밀어내기)
    ids.forEach((id, i) => { const a = -Math.PI / 2 + 2 * Math.PI * slot(id), cur = O.cur[id];
      const gx = i % cols, gy = Math.floor(i / cols), rowN = gy === rows - 1 ? n - gy * cols : cols;
      const x = open ? at[0] + (gx - (rowN - 1) / 2) * 62 * k : at[0] + rr * Math.cos(a), y = open ? at[1] + 26 * k + gy * 24 * k : at[1] + rr * Math.sin(a);
      pins.push({ id, x, y, cat: cur.cat, on: AG.sel === id, grp: open ? L.loc : null, title: `${esc(dno(id))} · ${esc(agScLabel(cur.p.sc, id))} · ${esc(agPlaceName(L.loc, R))}` }); });

  }
  // CL-1024-15 — 이동 중 마커: 같은 길 위에 겹쳐 맨 위 한 명만 눌리던 문제(18:18 · 21:00). 가까운 3명 이상은 '이동 중' 집합(누르면 펼침), 나머지는 밀어내기에 참여(고른 고객은 제자리)
  const mvs = O.moving.filter(([id]) => id !== AG.sel), mgroups = [];
  // CL-1024-16 — 이동 중 집합의 깜빡임 방지(이력 유지): 묶일 때 16 · 풀릴 때 26(지도 단위 × 배율) — 이미 묶인 무리는 조금 벌어져도 유지, 시각이 크게 바뀌면 새로 계산.
  //   집합 표시: 3명 이상, 또는 직전 프레임에 표시되던 무리는 2명까지 유지. 고객 위치(이동 기록)는 바꾸지 않고 표시만 묶는다.
  const JOIN = 16 * k, LEAVE = 26 * k, pos = Object.fromEntries(mvs.map(([id, p]) => [id, p.pos]));
  if (!AG._mvg || Math.abs((AG._mvgT ?? T) - T) > 5) AG._mvg = [];
  AG._mvgT = T;
  const cen = ids => { const xs = ids.map(i => pos[i]); return [xs.reduce((a, q) => a + q[0], 0) / xs.length, xs.reduce((a, q) => a + q[1], 0) / xs.length]; };
  const used = new Set(), next = [];
  AG._mvg.forEach(G => { let ids = G.ids.filter(i => pos[i]); for (let it = 0; it < 2 && ids.length; it++) { const c = cen(ids); ids = ids.filter(i => Math.hypot(pos[i][0] - c[0], pos[i][1] - c[1]) < LEAVE); }
    if (ids.length >= 2) { ids.forEach(i => used.add(i)); next.push({ key: G.key, ids, shown: G.shown }); } });
  mvs.forEach(([id]) => { if (used.has(id)) return; const q = pos[id];
    const G = next.find(G => { const c = cen(G.ids); return Math.hypot(q[0] - c[0], q[1] - c[1]) < JOIN; }) || null;
    if (G) { G.ids.push(id); used.add(id); return; }
    const F = mvs.filter(([j]) => !used.has(j) && j !== id && Math.hypot(pos[j][0] - q[0], pos[j][1] - q[1]) < JOIN).map(([j]) => j);
    if (F.length >= 2) { const ids = [id, ...F]; ids.forEach(i => used.add(i)); next.push({ key: "MV:" + id + "~" + Math.round(T), ids, shown: false }); } });
  next.forEach(G => { G.shown = G.ids.length >= 3 || (G.shown && G.ids.length >= 2); });
  AG._mvg = next;
  if (AG.openLoc && String(AG.openLoc).startsWith("MV:") && !next.some(G => G.key === AG.openLoc && G.shown)) AG.openLoc = null;
  next.forEach(G => { const c = cen(G.ids); if (G.shown) mgroups.push({ key: G.key, ids: G.ids, x: c[0], y: c[1] }); else G.ids.forEach(i => mgroups.push({ ids: [i], x: pos[i][0], y: pos[i][1] })); });
  mvs.forEach(([id, p]) => { if (!used.has(id)) mgroups.push({ ids: [id], x: p.pos[0], y: p.pos[1] }); });
  const mvTitle = id => { const p = O.cur[id].p; return `${esc(dno(id))} → ${esc(p.to ? agScLabel(p.to, id) : "이동 중")}`; };
  if (AG.sel && O.cur[AG.sel] && O.cur[AG.sel].p.moving) { const p = O.cur[AG.sel].p; pins.push({ id: AG.sel, x: p.pos[0], y: p.pos[1], cat: "move", mv: true, on: true, title: mvTitle(AG.sel) }); }
  mgroups.forEach(G => {
    const key = G.key || "MV:" + G.ids[0], open = AG.openLoc === key;
    if (G.key && !open) { clus.push({ loc: key, ids: G.ids, cats: G.ids.map(() => "move"), x: G.x, y: G.y }); return; }
    if (G.key) { const n = G.ids.length, cols = Math.min(3, n), rows = Math.ceil(n / cols);
      G.ids.forEach((id, i) => { const gx = i % cols, gy = Math.floor(i / cols), rowN = gy === rows - 1 ? n - gy * cols : cols; pins.push({ id, x: G.x + (gx - (rowN - 1) / 2) * 62 * k, y: G.y + 26 * k + gy * 24 * k, cat: "move", mv: true, on: false, grp: key, title: mvTitle(id) }); });
      return; }
    G.ids.forEach(id => { const p = O.cur[id].p; pins.push({ id, x: p.pos[0], y: p.pos[1], cat: "move", mv: true, on: false, title: mvTitle(id) }); });
  });
  for (let it = 0; it < 12; it++) { let mv = false;   // 집합끼리 겹치면 가로로 비킴(지름 + 여유)
    for (let i = 0; i < clus.length; i++) for (let j = i + 1; j < clus.length; j++) { const a = clus[i], c = clus[j], dx = c.x - a.x, dy = c.y - a.y, d = Math.hypot(dx, dy), need = 42 * k;
      if (d < need) { mv = true; const ux = d > 0.5 ? dx / d : 1, uy = d > 0.5 ? dy / d : 0, m = (need - d) / 2 + 0.5; a.x -= ux * m; a.y -= uy * m; c.x += ux * m; c.y += uy * m; } }
    if (!mv) break; }
  let cg = "";   // 집합은 받침판보다 위에 그림
  clus.forEach(C => { cg += agClusterSvg(C.loc, C.ids, C.cats, +C.x.toFixed(1), +C.y.toFixed(1), k, false); obs.push({ x: C.x, y: C.y, r: 20 * k });
    if (C.sel) top += agMarkerSvg(C.sel, +(C.x + 26 * k).toFixed(1), +(C.y - 18 * k).toFixed(1), k, C.selCat, true, `<title>${esc(C.sel)}</title>`); });
  const pw = q => q.on ? 22 * k : ((q.id.replace(/^blog/, "b").length * 6.4 + 9) * k) / 2 + 2 * k, phq = q => q.on ? 22 * k : 10.5 * k;
  // CL-1024-16 — 재생 중에는 직전 프레임의 '표시 오프셋'(둘레 자리 · 밀어내기로 실제 위치에서 비켜 그린 몫)에서 출발해 새 자리로 한 프레임 6(× 배율)씩만 옮기고,
  //   그 위에서 밀어내기를 돌린다 → 튀지 않으면서 겹치지도 않음. 실제 위치 · 이동 기록은 그대로. 정지 · 시각 이동 · 고른 고객은 바로 정위치.
  if (AG.playing && AG._dispT != null && Math.abs(T - AG._dispT) < 3 && AG._disp) {
    const lim = 6 * k;
    pins.forEach(q => { if (q.on) return; const tp = O.cur[q.id] && O.cur[q.id].p.pos, d = AG._disp[q.id]; if (!tp || !d) return;
      const px = tp[0] + d[0], py = tp[1] + d[1], dx = q.x - px, dy = q.y - py, m = Math.hypot(dx, dy); if (m > lim) { q.x = px + dx / m * lim; q.y = py + dy / m * lim; } });
  }
  for (let it = 0; it < 24; it++) {
    let moved = false;
    for (const a of pins) for (const o of obs) { if (a.on) continue; const dx = a.x - o.x, dy = a.y - o.y, ox = pw(a) + o.r - Math.abs(dx), oy = phq(a) + o.r - Math.abs(dy);   // 집합에서 비켜 남(집합은 그대로)
      if (ox > 0 && oy > 0) { moved = true; if (oy < ox) a.y += (oy + 1) * (dy >= 0 ? 1 : -1); else a.x += (ox + 1) * (dx >= 0 ? 1 : -1); } }
    for (let i = 0; i < pins.length; i++) for (let j = i + 1; j < pins.length; j++) {
      const a = pins[i], b = pins[j], dx = b.x - a.x, dy = b.y - a.y, ox = pw(a) + pw(b) - Math.abs(dx), oy = phq(a) + phq(b) - Math.abs(dy);
      if (ox > 0 && oy > 0) { moved = true; const wa = a.on ? 0 : (b.on ? 1 : 0.5), wb = 1 - wa;   // 고른 고객은 제자리, 주변이 비켜 남
        if (oy < ox) { const m = (oy + 1) * (dy >= 0 ? 1 : -1); a.y -= m * wa; b.y += m * wb; } else { const m = (ox + 1) * (dx >= 0 ? 1 : -1); a.x -= m * wa; b.x += m * wb; } }
    }
    if (!moved) break;
  }
  AG._disp = Object.fromEntries(pins.filter(q => O.cur[q.id] && O.cur[q.id].p.pos).map(q => [q.id, [q.x - O.cur[q.id].p.pos[0], q.y - O.cur[q.id].p.pos[1]]])); AG._dispT = T;
  // CL-1024-15 — 펼친 집합은 옅은 받침판 위에 모아 지도 그림과 구분(개별 고객을 알아보기 쉽게)
  const plates = {}; pins.forEach(q => { if (!q.grp) return; const b = plates[q.grp] = plates[q.grp] || [1e9, 1e9, -1e9, -1e9]; const hw = pw(q), hh = phq(q); b[0] = Math.min(b[0], q.x - hw); b[1] = Math.min(b[1], q.y - hh); b[2] = Math.max(b[2], q.x + hw); b[3] = Math.max(b[3], q.y + hh); });
  let xs = "";   // 닫기(×)는 받침판 오른쪽 위 — 다른 집합에 가리지 않게 맨 위에
  Object.entries(plates).forEach(([key, b]) => { const pd = 7 * k, X = b[2] + pd, Y = b[1] - pd; g += `<rect class="ag-clu-plate" x="${(b[0] - pd).toFixed(1)}" y="${Y.toFixed(1)}" width="${(b[2] - b[0] + 2 * pd).toFixed(1)}" height="${(b[3] - b[1] + 2 * pd).toFixed(1)}" rx="${(10 * k).toFixed(1)}"/>`;
    xs += `<g class="ag-clu-x" data-loc="${key}"><title>집합 접기</title><circle cx="${X.toFixed(1)}" cy="${Y.toFixed(1)}" r="${8 * k}" fill="#fff" stroke="#bfb29c"/><text x="${X.toFixed(1)}" y="${Y.toFixed(1)}" text-anchor="middle" dominant-baseline="central" style="font-size:${11 * k}px">×</text></g>`; });
  g += cg;
  pins.forEach(q => { let svg = agMarkerSvg(q.id, +q.x.toFixed(1), +q.y.toFixed(1), k, q.cat, q.on, `<title>${q.title}</title>`); if (q.mv) svg = svg.replace('class="ag-pin ag-mk', 'class="ag-pin ag-mk ag-mv'); if (q.on) top += svg; else g += svg; });
  let h = "";
  O.moving.forEach(([id, p]) => { const on = AG.sel === id;
    if (on && p.sc.mk && p.sc.mk.pts.length > 1) h += `<g class="wr ag-wr"><path class="wrEdge" d="${ptsD(p.sc.mk.pts)}"/><path class="wrLine" d="${ptsD(p.sc.mk.pts)}"/></g>`; });
  if (AG.sel && O.cur[AG.sel] && !O.cur[AG.sel].p.moving) {   // 머무는 중이면 다음 이동 경로를 옅게
    const L = agScenes(AG.sel), cur = O.cur[AG.sel].p.sc, nx = L.slice(L.indexOf(cur) + 1).find(x => x.k === "move");
    if (nx && nx.mk && nx.mk.pts.length > 1) h += `<g class="wr ag-wrn"><path class="wrLine" d="${ptsD(nx.mk.pts)}"/></g>`;
  }
  if (AG.sel && O.cur[AG.sel]) { const p = O.cur[AG.sel].p, pos = p.pos, lab = `${dno(AG.sel)} · ${p.moving ? "이동 중" : agScShort(p.sc, AG.sel)}`, tw = (typeof textW === "function" ? textW(lab, 11 * k, true) : lab.length * 7 * k) + 14 * k, th = 19 * k, x = pos[0], y = pos[1] - 32 * k;
    top += `<g class="ag-tag ag-seltag"><rect x="${x - tw / 2}" y="${y - th}" width="${tw}" height="${th}" rx="${th / 2}"/><text x="${x}" y="${y - th / 2}" text-anchor="middle" dominant-baseline="central" style="font-size:${11 * k}px">${esc(lab)}</text></g>`; }
  $("#agent").innerHTML = g + xs + top; $("#trail").innerHTML = ""; $("#route").innerHTML = h;
  if (!AG.manyMoving || !AG._labT || performance.now() - AG._labT > 600) { AG._labT = performance.now(); agManyLabels(); }
  $$("#agent .ag-pin").forEach(e => e.onclick = ev => { ev.stopPropagation(); agSelect(e.dataset.p); });
  $$("#agent .ag-clu").forEach(e => e.onclick = ev => { ev.stopPropagation(); AG.openLoc = e.dataset.loc; AG._opsAt = 0; agManyDraw(AG.manyT != null ? AG.manyT : T); });
  $$("#agent .ag-clu-x").forEach(e => e.onclick = ev => { ev.stopPropagation(); AG.openLoc = null; AG._opsAt = 0; agManyDraw(AG.manyT != null ? AG.manyT : T); });
  AG.manyLive = { T, groups: Object.fromEntries(Object.entries(O.byLoc).map(([l, a]) => [l, a.ids])), moving: O.moving.map(([id, p]) => [id, p.to ? p.to.label : ""]), away: { pre: O.pre, post: O.post } };
  const now = performance.now();
  if (holdTi != null || !AG._opsAt || now - AG._opsAt > 220) { AG._opsAt = now; agOpsPanel(T, O); }
}
function agPanelLive() { return agOpsPanel(AG.manyLive ? AG.manyLive.T : AG.manyT); }   // 호환 — 운영 패널로 통합(CL-11)
function agTurnCardFor(c, sc) { const keepTi = AG.ti, keepRes = AG.res; AG.ti = sc.ti; AG.res = AG.runs[sc.ti] || keepRes; const cc = agCustOf(AG.res, c.persona_id); const h = cc ? agTurnCard(cc, true) : ""; AG.ti = keepTi; AG.res = keepRes; return h; }
function agUseTurn(ti) {   // 선택한 턴으로 지도 핀 · 시계 · 오른쪽을 바꾼다
  if (!AG.runs.length || ti === AG.ti) return false;
  AG.ti = ti; AG.res = AG.runs[ti]; agClock(); agDrawMap(); return true;
}
function agSetScene(si, f) {   // 장면 번호로 상태를 맞춘다(한 명 모드)
  const c = agCur(), L = agScenes(c ? c.persona_id : null), sc = L[si]; if (!sc) return;
  const at = sc.k === "flow" ? "mid" : sc.k;
  const tc = agUseTurn(sc.ti), wasAt = AG.at, wasSi = AG.si;
  AG.si = si; AG.at = at; AG.f = f == null ? (at === "start" ? 0 : 1) : f;
  AG.nowMin = at === "turn" ? sc.t0 : sc.t0 + (sc.t1 - sc.t0) * (AG.f || 0);
  if (AG.res && agIsOne(AG.res) && (tc || ((wasAt === "turn") !== (at === "turn")))) agDrawMap(); else agDrawRoute();
  agClock(); agStripMark();
  if (tc || wasSi !== si || wasAt !== at) { agPanel(); agStripState(); }
}
function agSetAt(at, f, ti) {   // 호환 — 상태 이름 + 턴 번호로(여러 명 모드 · 시간축)
  if (AG.res && agIsMany(AG.res) && !AG.fix) {   // CL-11 — 여러 명(자율): 그 턴 시각으로 운영 화면 전체를 맞춘다
    if (ti != null && AG.runs[ti]) { AG.ti = ti; AG.res = AG.runs[ti]; }
    AG.at = at; const T = AG.manyMoving && AG.manyT != null ? AG.manyT : agMin(AG.res.time);
    agManyRender(T); agStripState(); return;
  }
  const c = agCur();
  if (AG.res && agIsMany(AG.res) && ti != null && !AG.manyMoving) { const R = AG.runs[ti]; if (R) { AG.manyT = agMin(R.time); AG.nowMin = AG.manyT; } }
  if (c && AG.res && agIsOne(AG.res)) {   // 한 명 — 해당하는 장면으로
    const L = agScenes(c.persona_id), i = L.findIndex(x => (at === "mid" ? x.k === "flow" : x.k === at) && x.ti === (ti == null ? AG.ti : ti));
    if (i >= 0) return agSetScene(i, f);
  }
  const tc = ti != null && agUseTurn(ti);
  const changed = tc || at !== AG.at;
  const wasAt = AG.at;
  AG.at = at; AG.f = f == null ? (at === "start" ? 0 : 1) : f; AG.nowMin = null;
  const L = agScenes(c ? c.persona_id : null), i = L.findIndex(x => (at === "mid" ? x.k === "flow" : x.k === at) && x.ti === AG.ti); AG.si = i >= 0 ? i : AG.si;
  if (AG.res && agIsOne(AG.res) && (tc || ((wasAt === "turn") !== (at === "turn")))) agDrawMap(); else agDrawRoute();
  agClock();
  if (changed) { agPanel(); agStripState(); }
}
function agTeamSummary(ids=agAllIds()) { const sizes=ids.map(id=>agVC(id).party),known=sizes.every(n=>Number.isInteger(n)&&n>0);return `고객 ${ids.length}팀 · 방문 설정 ${known?sizes.reduce((a,b)=>a+b,0)+'명':'인원 미확인'}`; }
function agClock(Rx) {
  const R = Rx || AG.res; if (!R) return;
  const sc = AG.res && agIsOne(AG.res) ? agScene() : null, flow = AG.at === "mid", mv = AG.at === "move" || AG.manyMoving;
  const tm = AG.nowMin != null ? agHM(AG.nowMin) : flow ? "낮" : (R.time || "--:--");
  const manyAuto = agIsMany(R) && !AG.fix && AG.nowMin != null, tiNow = manyAuto ? agTurnAt(AG.nowMin) : -1;
  const what = manyAuto ? (tiNow >= 0 ? `${AG_TURN[AG.runs[tiNow].turn]} · 주요 결정` : `${agOpsAt(AG.nowMin).present.length}팀 호텔 안${AG.manyMoving ? " · 각자 활동 중" : ""}`) : AG.manyMoving ? `${agAllIds().length}팀이 각자 체류 중` : sc && sc.k === "flow" ? `${sc.label}` : sc && sc.k === "move" ? `${sc.b ? (agPlaceName(sc.b, R)) : "다음 장소"}(으)로 이동` : sc && sc.k === "start" ? sc.label : flow ? "낮 · 자유 시간" : AG_TURN[R.turn] + " 턴";
  $("#clock b").textContent = tm;
  $("#clock span").innerHTML = `<em class="ck-t${flow ? " gen" : mv ? " mv" : ""}">${esc(what)}</em>${AG.runs.length > 1 && !manyAuto ? `<i class="ck-s">하루 ${AG.ti + 1}/${AG.runs.length}</i>` : ""}<small class="ck-c">${agIsMany(R) && !AG.fix ? `${agTeamSummary()}` : agIsOne(R) ? (()=>{const v=agVC(AG.one,R);return `${v.stay?esc(v.bl||R.building.label)+" 투숙":"비투숙"} · ${v.party}명`;})() : `${R.conditions.stay ? esc(R.building.label) + " 투숙" : "비투숙"} · ${R.conditions.party_size}인`}${R.conditions.event ? " · 와인페어" : ""}</small>`;
}
const AG_LOCNAME = { AG_GARDEN: "더글라스 가든", HOTEL_GATE: "정문", GRAND_LOBBY: "그랜드 로비", VISTA_LOBBY: "비스타 로비", DOUGLAS_LOBBY: "더글라스 로비", PIZZA_HILL: "피자힐", FOREST_PARK: "포레스트 파크", SKYARD: "스카이야드", THE_BUFFET: "더뷔페", MYONGWOLGWAN: "명월관", LE_PASSAGE: "르 파사쥬",
  VISTA_POOL: "비스타 수영장", GRAND_POOL: "그랜드 수영장", WELLNESS_SAUNA: "그랜드 웰니스 사우나", VISTA_FITNESS: "비스타 피트니스", FITNESS: "피트니스", GRAND_LIBRARY: "라이브러리", GRAND_CLUB_LOUNGE: "클럽 라운지", THE_PAVILION: "더 파빌리온", LUX_BAR: "럭스바", ONDAL: "온달", GEUMRYONG: "금룡", MOEGI: "모에기", THEATRE_OF_LIGHT: "빛의 시어터", TENNEZ_PARK: "테네즈 파크", RIVERPARK: "리버파크" };
function agPlaceName(loc, R) { if (/_ROOM$/.test(loc || "")) { const B = loc.replace(/_ROOM$/, ""); return `${(AG.meta && AG.meta.buildings && AG.meta.buildings[B]) || (R || AG.res).building.label} 객실`; } return AG_LOCNAME[loc] || (typeof PLACE_NAME !== "undefined" && PLACE_NAME[loc]) || loc; }

// ---------------------------------------------------------------- 지도
function agMapReset() {
  $("#heat").innerHTML = ""; $("#trail").innerHTML = ""; $("#route").innerHTML = ""; $("#dim").innerHTML = ""; $("#agent").innerHTML = ""; $("#vcline").innerHTML = "";
  $("#pins").innerHTML = ""; $("#map").classList.remove("gfocus");
  $$("#labels .lab").forEach(t => t.classList.remove("hlDest", "hlB", "dup", "ag-hl", "ag-under"));
  $("#mapLegend").classList.add("hidden");
}
function agEmpty() {
  cancelAnimationFrame(AG.raf); agMapReset();
  $("#mapEmpty").classList.remove("hidden");
  $("#mapEmpty").innerHTML = `왼쪽에서 ① ${AG.mode === "agents" ? "에이전트들" : "에이전트"}과 ② 환경을 정하고 ④ <b>실행</b>을 누르세요`;
  $("#clock b").textContent = "--:--"; $("#clock span").textContent = "";
  $("#panel").innerHTML = "";
  $("#strip").innerHTML = ""; $("#strip").classList.add("ag-off");
}
// 준비 상태는 선택된 입력 위치에 기존 아바타만 표시한다. 행동·원장·이동은 생성하지 않는다.
function agReadyAvatar() {
  if (AG.mode === "agents" || !AG.one || AG.res || AG.runs.length || AG.busy) return;
  const c = AG.cond, loc = c.stay ? `${c.building}_ROOM` : "HOTEL_GATE", at = LOC[loc];
  if (!at) return;
  const k = typeof mapK === "function" ? mapK() : 1, [x, y] = at;
  const n = AG.oneOverride ? c.party_size : agShowN(AG.one), label = `${dno(AG.one)} · 준비`;
  const cp = agComp(AG.one, n), members = cp.av && AG.avm[cp.av] ? AG.avm[cp.av].n_members : n;
  const top = (members > 2 ? 50 : members === 2 ? 46 : 42) * k + 12 * k;
  const w = (typeof textW === "function" ? textW(label, 11.5 * k, true) : label.length * 7 * k) + 14 * k, h = 20 * k;
  $("#agent").innerHTML = `<g class="ag-pin single on ag-prepared" data-p="${esc(AG.one)}" data-start="${loc}" style="--vc:var(--k-room)">${agAvatarSvg(AG.one, n, x, y, k, "here", {hl:true})}<g class="ag-tag"><rect x="${x - w / 2}" y="${y - top - h}" width="${w}" height="${h}" rx="${h / 2}"/><text x="${x}" y="${y - top - h * .32}" text-anchor="middle" style="font-size:${11.5 * k}px">${esc(label)}</text></g><title>${esc(dno(AG.one))} · ${esc(locName(loc))} · 실행 전</title></g>`;
}
// P6 — 준비(정지) 화면: 고객 · 조건만 보이고 시계 · 아바타 · 타임라인은 움직이지 않는다. 사용자가 가상 방문 생성을 눌러야 하루 시작
function agReady() {
  if (typeof setPlay === "function") setPlay(false);
  cancelAnimationFrame(AG.raf); AG.playing = false; agManyStop && agManyStop(); agMapReset();
  const many = AG.mode === "agents", p = !many && AG.one ? dno(AG.one) : null;
  $("#mapEmpty").classList.remove("hidden");
  $("#mapEmpty").innerHTML = many ? `<div class="ar-t"><b>${AG.many ? AG.many.size : 0}명</b>을 같은 조건에 넣을 준비가 되었습니다</div><span>조건을 확인하고 왼쪽 아래 <b>가상 방문 생성</b>을 누르면 가상 방문이 생성됩니다</span>`
    : p ? `<div class="ar-t"><b>${esc(p)}</b>의 하루를 시작할 준비가 되었습니다</div><span>${AG.cond.event ? "와인페어 있는 날 · " : ""}조건을 확인하고 왼쪽 아래 <b>가상 방문 생성</b>을 누르세요</span>`
    : `<div class="ar-t"><b>고객을 먼저 선택하세요</b></div><span>왼쪽 ① 고객에서 한 명을 고르고, 조건을 정한 뒤 <b>가상 방문 생성</b>을 누르면 가상 방문이 생성됩니다</span>`;
  $("#mapEmpty").classList.add("ag-ready");
  $("#clock b").textContent = "--:--"; $("#clock span").textContent = "";
  $("#panel").innerHTML = `<div class="ag-ready-p">${many ? "실행하면 여기에 이 시각의 고객 현황과, 지도에서 고른 고객의 선택 이유가 나옵니다." : "실행하면 여기에 이 고객이 고른 곳과 이유, 고르지 않은 대안이 나옵니다."}</div>`;
  $("#strip").innerHTML = ""; $("#strip").classList.add("ag-off");
  const rb = $("#agRun"); if (rb) rb.disabled = many ? !AG.many.size : !AG.one;
  agReadyAvatar();
}
// 고객 · 조건이 바뀌면 이전 결과(다른 사람 · 다른 조건)를 지우고 준비 화면으로 — 낡은 타이머가 남지 않게
function agStale() {
  if (typeof AG === "undefined" || AG.busy) return;
  if (!AG.res && !AG.runs.length) return agReady();
  agPause(); AG.pendingConditions = true;
  // Draft controls are not a new execution. Keep the last successful map and ledger.
  const hint = document.querySelector('#agHint');
  if (hint) hint.textContent = '조건 변경 중 · 지도와 매출은 이전 생성 결과입니다. 다시 생성하면 반영됩니다.';
}
function agShow(play) {
  const R = AG.res; if (!R) return agEmpty();
  cancelAnimationFrame(AG.raf);
  $("#mapEmpty").classList.add("hidden"); $("#mapEmpty").classList.remove("ag-ready");
  AG.at = "turn"; AG.f = 1; AG.nowMin = null; AG._sc = null; AG._rate = null; AG.ended = false; AG.manyT = null; AG.manyHeld = null; AG_LABKEY = ""; agManyStop();
  { const c = agCur(); const L = agScenes(c ? c.persona_id : null); const i = L.findIndex(x => x.k === "turn" && x.ti === AG.ti); AG.si = i >= 0 ? i : 0; if (i >= 0) AG.nowMin = L[i].t0; }
  if (AG.visitData) {
    AG.paused = false; AG.f = 0; AG.si = 0;
    const first = agScenes(AG.sel || AG.one)[0];
    if (first) { AG.ti = first.ti; AG.res = AG.runs[first.ti]; AG.at = first.k === 'flow' ? 'mid' : first.k; AG.nowMin = first.t0; }
    play = false; // Opening/calculating a visit never starts the animation.
  }
  agClock(); agDrawMap(); agStrip(); agPanel();
  if (AG.visitData && agIsMany(AG.res)) { const [start] = agManyWindow(); AG.manyT = start; agManyRender(start); }
  if (play && agCur() && !agIsMany(R)) agPlay();
  else if (play && agIsMany(R) && !AG.fix) agPlayManyTime(true);   // CL-11 — 여러 명도 실행하면 하루를 바로 재생
}
// 실험용 고정 모드 — 이 턴의 결정 장소마다: 3명 이상이면 인원 집합(누르면 펼침), 아니면 ID 알약(고른 고객은 초상)
const agTurnCat = (R, ch) => ch.venue_id === "ROOM" ? "room" : R.turn === "event" ? (ch.venue_id === "FOREST" ? "culture" : ch.venue_id === "SKYARD" ? "well" : "walk") : "meal";
function agFixGroup(loc, cs, at, k, R) {
  const ids = cs.map(c => c.persona_id), others = ids.filter(id => id !== AG.sel), hasSel = ids.includes(AG.sel), open = AG.openLoc === loc, cat = id => agTurnCat(R, cs.find(c => c.persona_id === id).choice);
  let g = "";
  if (others.length >= 3 && !open) { g += agClusterSvg(loc, others, others.map(cat), at[0], at[1], k, false); if (hasSel) g += agMarkerSvg(AG.sel, at[0] + 26 * k, at[1] - 18 * k, k, cat(AG.sel), true); return g; }
  const list = hasSel ? [...others, AG.sel] : others, n = list.length, cols = Math.min(3, n), rows = Math.ceil(n / cols);
  list.forEach((id, i) => { const gx = i % cols, gy = Math.floor(i / cols), rowN = gy === rows - 1 ? n - gy * cols : cols;
    const x = n === 1 ? at[0] : at[0] + (gx - (rowN - 1) / 2) * 62 * k, y = n === 1 ? at[1] : at[1] + (open ? 26 * k : 0) + gy * 24 * k;
    g += agMarkerSvg(id, +x.toFixed(1), +y.toFixed(1), k, cat(id), AG.sel === id, `<title>${esc(dno(id))} · ${esc(agChoiceName(R, cs.find(c => c.persona_id === id).choice))}</title>`); });
  if (open) g += `<g class="ag-clu-x" data-loc="${loc}"><circle cx="${at[0]}" cy="${at[1]}" r="${7 * k}" fill="#fff" stroke="#bfb29c"/><text x="${at[0]}" y="${at[1]}" text-anchor="middle" dominant-baseline="central" style="font-size:${10 * k}px">×</text></g>`;
  return g;
}
function agDrawMap() {
  if (AG.res && agIsMany(AG.res) && !AG.fix) {   // CL-11 — 여러 명(자율)은 시각 T 의 초상 마커 지도
    agMapReset(); $("#map").classList.add("agmode"); $("#mapLegend").classList.remove("hidden");
    $("#mapLegend").innerHTML = `<span><i class="ag-lgm"></i>고객 번호(테두리 색 = 지금 활동 · 숫자 = 같은 곳 인원)</span>${["meal", "well", "culture", "walk", "room"].map(k => `<span><i class="ag-lgc" style="background:${AG_CAT[k].color}"></i>${AG_CAT[k].label.split(" · ")[0]}</span>`).join("")}${noteH({ what: "고객마다 생성된 하루 계획에서 지금 시각의 위치를 표시합니다. 같은 곳에 여러 명이 있으면 둘러 놓고 인원을 적습니다. 이동 중인 고객은 길 위의 작은 초상입니다.", basis: ["운영 조건 · 계산", "추출 성향"], caution: AG_AV_NOTE + " 이동 경로 · 시간은 표시용입니다." })}`;
    AG._opsAt = 0; return agManyDraw(AG.manyT != null ? AG.manyT : agMin(AG.res.time));
  }
  agMapReset();
  const R = AG.res, k = typeof mapK === "function" ? mapK() : 1, many = agIsMany(R);
  const groups = {};
  R.customers.forEach(c => { (groups[c.choice.map_loc] = groups[c.choice.map_loc] || []).push(c); });
  const cand = new Set(); R.customers.forEach(c => c.not_chosen.forEach(o => o.feasible && cand.add(o.map_loc)));
  $("#pins").innerHTML = [...cand].filter(l => LOC[l] && !groups[l]).map(l => `<g class="pin faded" data-loc="${l}"><circle cx="${LOC[l][0]}" cy="${LOC[l][1]}" r="3.5"/></g>`).join("");
  let g = "";
  for (const [loc, cs] of Object.entries(groups)) {
    const at = LOC[loc]; if (!at) continue;
    if (many) { g += agFixGroup(loc, cs, at, k, R); continue; }   // CL-1024-13 — 실험용 고정 모드도 자율 모드와 같은 마커 · 집합 표현(엔진 계산 · 위치 규칙은 그대로)
    cs.forEach((c, i) => {
      const n = cs.length, a = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(n, 1), rr = n > 1 ? Math.max(15, 20 * n / (2 * Math.PI)) * k : 0;   // 인원이 많을수록 부채꼴을 넓혀 핀이 겹치지 않게(점 간격 ≥ 20)
      const x = at[0] + rr * Math.cos(a), y = at[1] + rr * Math.sin(a), on = AG.sel === c.persona_id || !many;
      const dim = many && AG.sel && !on;
      const pl = agShort(c.choice.product_label), vl = c.choice.venue_label;
      const tag = !many ? `${AG_TURN[R.turn]} · ${agPlace(R, c.choice, c.persona_id)}` : c.persona_id;   // 09-F 지도에는 장소명 우선(상품명은 오른쪽 · 시간 바에)
      const tw = (typeof textW === "function" ? textW(tag, 11.5 * k, true) : tag.length * 7) + 14 * k, th = 20 * k;
      const avH = !many && AG.at === "turn" ? (() => { const av = agAvatarAsset(c.persona_id, agVC(c.persona_id, R).party); const nm = av && AG.avm[av.key] ? AG.avm[av.key].n_members : 1; return (nm > 2 ? 50 : nm === 2 ? 46 : 42) * k + 8 * k; })() : 28 * k;   // 이름표는 아바타 머리 위
      const ty = y - (many ? 13 * k : avH) - th;
      const body = many ? `<circle class="ag-halo" cx="${x}" cy="${y}" r="${13 * k}"/><circle class="ag-dot" cx="${x}" cy="${y}" r="${8 * k}"/>`
        : `<circle class="ag-halo" cx="${x}" cy="${y}" r="${16 * k}"/>${AG.at === "turn" ? agAvatarSvg(c.persona_id, agVC(c.persona_id, R).party, x, y, k, "here") : `<circle class="ag-dot ag-ghost" cx="${x}" cy="${y}" r="${6 * k}"/>`}`;
      g += `<g class="ag-pin${on ? " on" : ""}${dim ? " dim" : ""}${many ? "" : " single"}" data-p="${c.persona_id}" style="--vc:${agVColor(c.choice.venue_id)}">` + body +
        (many && !on && cs.length < 7 ? (() => { const lx = at[0] + (rr + 15 * k) * Math.cos(a), ly = at[1] + (rr + 15 * k) * Math.sin(a) + 4 * k, an = Math.cos(a) > 0.3 ? "start" : Math.cos(a) < -0.3 ? "end" : "middle";
          return `<text class="ag-pid" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${an}" style="font-size:${10 * k}px">${esc(dno(c.persona_id))}</text>`; })() : "") +
        ((!many && AG.at === "turn") || (many && on) ? `<g class="ag-tag"><rect x="${x - tw / 2}" y="${ty}" width="${tw}" height="${th}" rx="${th / 2}"/><text x="${x}" y="${ty + th * 0.68}" text-anchor="middle" style="font-size:${11.5 * k}px">${esc(tag)}</text></g>` : "") +
        `<title>${esc(dno(c.persona_id))} · ${esc(c.choice.venue_label)} · ${esc(c.choice.product_label)} · 점수 ${agNum(c.choice.score)}</title></g>`;
    });
    if (many && cs.length > 1) { const rr0 = Math.max(15, 20 * cs.length / (2 * Math.PI)) * k, tw = 44 * k, th = 18 * k, x = at[0], y = at[1] + rr0 + 17 * k; g += `<g class="ag-cnt ag-cl${AG.focusLoc === loc ? " on" : ""}" data-loc="${loc}"><rect x="${x - tw / 2}" y="${y - th / 2}" width="${tw}" height="${th}" rx="${th / 2}"/><text x="${x}" y="${y + 4 * k}" text-anchor="middle" style="font-size:${11 * k}px">${cs.length}명 ▾</text><title>${esc(cs.map(c => c.persona_id).join(" · "))} — 누르면 목록</title></g>`; }
    else if (many) { g += `<g class="ag-cnt"><text x="${at[0] + 16 * k}" y="${at[1] + 4 * k}" text-anchor="start" style="font-size:${11 * k}px">1명</text></g>`; }
  }
  if (many && R._auto) {   // 보충2 — 이 턴의 결정이 없는 고객(체크인 전 · 체크아웃 뒤 · 비투숙 낮)은 그 시각 자기 위치에 옅은 점으로
    const T = AG.manyT != null ? AG.manyT : (agMin(R.time) || 0), here = new Set(R.customers.map(c => c.persona_id)), og = {};
    agAllIds().filter(id => !here.has(id)).forEach(id => { const p = agManyPos(id, T); if (!p || p.away || !p.pos) return; (og[p.loc || "mv:" + id] = og[p.loc || "mv:" + id] || []).push({ id, p }); });
    for (const arr of Object.values(og)) { const n = arr.length, rr = n > 1 ? Math.max(12, 18 * n / (2 * Math.PI)) * k : 0; arr.forEach(({ id, p }, i) => { const a = -Math.PI / 2 + (2 * Math.PI * i) / n, x = p.pos[0] + rr * Math.cos(a), y = p.pos[1] + rr * Math.sin(a), on = AG.sel === id;
      g += `<g class="ag-pin ag-live ag-other${on ? " on" : ""}" data-p="${id}" style="--vc:var(--k-room)"><circle class="ag-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${5.5 * k}"/><title>${esc(dno(id))} · ${esc(p.sc.label || "")} · 이 턴의 결정 없음 · ${esc(agVisitShort(id))}</title></g>`; }); }
  }
  $("#agent").innerHTML = g;
  $$("#agent .ag-pin").forEach(e => e.onclick = ev => { ev.stopPropagation(); const p = e.dataset.p; if (AG.sel === p) agDrawer(p); else agSelect(p); });
  $$("#agent .ag-clu").forEach(e => e.onclick = ev => { ev.stopPropagation(); AG.openLoc = e.dataset.loc; AG.focusLoc = e.dataset.loc; agDrawMap(); agPanel(); const h = $("#agClH"), pn = $("#panel"); if (h && pn) pn.scrollTop = Math.max(0, h.offsetTop - pn.offsetTop - 8); });   // 펼침 + 오른쪽 '이 지점에 모인 고객' 목록(기존 기능 유지)
  $$("#agent .ag-clu-x").forEach(e => e.onclick = ev => { ev.stopPropagation(); AG.openLoc = null; AG.focusLoc = null; agDrawMap(); agPanel(); });
  $$("#agent .ag-cl").forEach(e => e.onclick = ev => { ev.stopPropagation(); AG.focusLoc = AG.focusLoc === e.dataset.loc ? null : e.dataset.loc; agDrawMap(); agPanel(); const h = $("#agClH"), pn = $("#panel"); if (h && pn) pn.scrollTop = Math.max(0, h.offsetTop - pn.offsetTop - 8); });
  $("#map").classList.add("agmode");
  agHlLabels();
  agDrawRoute();
  $("#mapLegend").classList.remove("hidden");
  $("#mapLegend").innerHTML = `<span><i class="ag-lg"></i>${AG_TURN[R.turn]}에 고른 곳</span><span><i class="ag-lg3"></i>출발 위치</span><span><i class="ag-lg4"></i>이동</span><span><i class="ag-lg2"></i>다른 후보 업장</span>${noteH({ what: "출발 위치는 방문 조건(투숙 건물 객실 · 비투숙은 정문)이고, 선택한 업장은 이번 턴의 엔진 결과입니다. 둘 사이의 선은 지도 길을 따라 이은 표시용 연결이며 이동 시간 · 경로를 계산한 것이 아닙니다. 같은 업장을 여러 에이전트가 골라도 서로 영향을 주지 않습니다.", basis: ["운영 조건 · 계산"] })}`;
}
// 선택한 에이전트 한 명의 출발 표시 · 연결선 · 위치 점만 그린다 (여러 명이어도 나머지는 핀만)
function agDrawRoute() {
  const R = AG.res, c = agCur();
  $("#route").innerHTML = "";
  if (!R || !c) { $("#trail").innerHTML = ""; return; }
  const k = typeof mapK === "function" ? mapK() : 1, n = Math.max(AG.runs.length, 1), pid = c.persona_id;
  let h = "", t = "";
  const arrow = r => { const q = along(r, 0.55), q2 = along(r, 0.57), ang = Math.atan2(q2[1] - q[1], q2[0] - q[0]) * 180 / Math.PI, sz = 6.5 * k;
    return `<path class="wrArrow" d="M${(-sz).toFixed(1)},${(-sz * 0.7).toFixed(1)} L${(sz * 0.6).toFixed(1)},0 L${(-sz).toFixed(1)},${(sz * 0.7).toFixed(1)} Z" transform="translate(${q[0].toFixed(1)},${q[1].toFixed(1)}) rotate(${ang.toFixed(1)})"/>`; };
  const placed = [];   // 글자 상자끼리 겹치면 아래로 한 칸씩 내린다(출발 · 다른 턴 표식이 같은 자리일 때)
  const tag = (x, y, lbl, cls) => { const tw = (typeof textW === "function" ? textW(lbl, 11 * k, false) : lbl.length * 7) + 12 * k, th = 18 * k; let ty = y + 10 * k;
    for (let g = 0; g < 4; g++) { const hit = placed.some(b => !(x + tw / 2 < b[0] || x - tw / 2 > b[2] || ty + th < b[1] || ty > b[3])); if (!hit) break; ty += th + 2 * k; }
    placed.push([x - tw / 2, ty, x + tw / 2, ty + th]);
    return `<g class="${cls}"><rect x="${x - tw / 2}" y="${ty}" width="${tw}" height="${th}" rx="${th / 2}"/><text x="${x}" y="${ty + th * 0.68}" text-anchor="middle" style="font-size:${11 * k}px">${esc(lbl)}</text></g>`; };
  const oneR = agIsOne(R), SCN = oneR ? agScenes(pid) : null, wps = [];
  if (SCN) {   // 09-F 한 명 — 하루 장면의 경로: 지금 움직이는 구간만 붉은 점선 · 지나온 길은 옅은 중립색 · 앞으로 갈 길은 더 옅게
    const curSi = AG.si == null ? -1 : AG.si, curSc = SCN[curSi], moving = curSc && (curSc.k === "move" || (curSc.k === "flow" && curSc.mk && (AG.f || 0) < (curSc._wf || 0)));
    SCN.forEach((x, i) => {
      const r = x.k === "move" ? x.r : x.k === "flow" && x.mk ? route(x.from, x.loc) : null; if (!r || r.unknown || r.internal || r.link || r.near || !x.mk || x.mk.pts.length < 2) return;
      const cls = i === curSi && moving ? "ag-wr" : i < curSi || (i === curSi && !moving) ? "ag-wrp" : "ag-wrn";
      h += `<g class="wr ${cls}"><path class="wrEdge" d="${ptsD(x.mk.pts)}"/><path class="wrLine" d="${ptsD(x.mk.pts)}"/>${cls === "ag-wr" ? arrow(x.mk) : ""}</g>`; });
  }
  for (let i = 0; i < n; i++) {
    const sg = agSeg(pid, i);
    if (!SCN && !sg.same && sg.r && sg.r.pts.length > 1 && !sg.r.unknown && !sg.r.internal && !sg.r.link && !sg.r.near)
      h += `<g class="wr ag-wr${i === AG.ti ? "" : " ag-wr2"}"><path class="wrEdge" d="${ptsD(sg.r.pts)}"/><path class="wrLine" d="${ptsD(sg.r.pts)}"/>${arrow(sg.r)}</g>`;
    if (n > 1 && i !== AG.ti) {   // 다른 턴의 선택 장소(같은 에이전트) — 작은 표식
      const oc = agCustOf(AG.runs[i], pid), L0 = oc && LOC[oc.choice.map_loc];
      if (L0) wps.push([L0, `${AG_TURN[AG.runs[i].turn]} · ${agPlace(AG.runs[i], oc.choice)}`]);
    }
  }
  const s0 = agSeg(pid, 0), S = LOC[s0.a || agStart(R)];
  const one = agIsOne(R), sc = one ? agScene() : null;
  // 현재 위치 — 장면 기준(한 명) · 상태 기준(여러 명)
  let pos = null, walking = false, dirx = 0, gen = false;
  if (one && sc) {
    if (sc.k === "start") pos = LOC[sc.loc] || S;
    else if (sc.k === "move") { pos = along(sc.mk, AG.f); walking = true; dirx = (along(sc.mk, Math.min(1, (AG.f || 0) + 0.02))[0] - pos[0]) || (along(sc.mk, 1)[0] - along(sc.mk, 0)[0]); }
    else if (sc.k === "flow") { gen = true; const wfr = sc._wf != null ? sc._wf : (agSceneDur(sc), sc._wf), wf = sc.mk && wfr > 0 ? Math.min(1, (AG.f || 0) / wfr) : 1;   // 흐름 구간 — 앞(걷는 몫)은 걸어가고 나머지는 머무른다
      if (sc.mk && wf < 1) { const ff = wf * wf * (3 - 2 * wf); pos = along(sc.mk, ff); walking = true; gen = false; dirx = (along(sc.mk, Math.min(1, ff + 0.02))[0] - pos[0]) || (along(sc.mk, 1)[0] - along(sc.mk, 0)[0]); }
      else pos = LOC[sc.loc] || LOC[c.choice.map_loc]; }
    if (sc.k === "flow" && pos && !walking) h += `<g class="ag-fspot${sc.src === "review" ? " rv" : ""}"><circle cx="${pos[0]}" cy="${pos[1]}" r="${14 * k}"/>${tag(pos[0], pos[1] + 2 * k, sc.short || sc.label, "ag-stag ag-ftag")}</g>`;
  } else {
    const cur = agSeg(pid, AG.ti);
    if (AG.at === "start") pos = S;
    else if (AG.at === "move" && cur.mk) { pos = along(cur.mk, AG.f); walking = true; dirx = (along(cur.mk, Math.min(1, (AG.f || 0) + 0.02))[0] - pos[0]) || (along(cur.mk, 1)[0] - along(cur.mk, 0)[0]); }
    else if (AG.at === "mid") { pos = LOC[c.choice.map_loc]; gen = true; }
  }
  // 다른 턴의 선택 장소 표식 — 현재 아바타와 겹치면 글자는 빼고 점만(아바타 발 밑을 가리지 않게)
  const anc = pos || (AG.at === "turn" ? LOC[c.choice.map_loc] : null), nearPos = (q, d) => anc && Math.hypot(anc[0] - q[0], anc[1] - q[1]) < d * k;
  wps.forEach(([L0, lbl]) => { h += `<g class="ag-wp"><circle cx="${L0[0]}" cy="${L0[1]}" r="${6 * k}"/>${nearPos(L0, 70) ? "" : tag(L0[0], L0[1], lbl, "ag-stag")}</g>`; });
  // 출발 표시 — 현재 위치와 겹치면 글자를 옆으로 비킨다(아바타 발 밑을 가리지 않게)
  if (S && !(n === 1 && s0.same)) { const lbl = `출발 · ${agStartName(R)}`;
    h += `<g class="ag-start"><circle cx="${S[0]}" cy="${S[1]}" r="${6 * k}"/>${nearPos(S, 70) ? "" : tag(S[0], S[1], lbl, "ag-stag")}</g>`; }
  const wo = walking ? { walk: true, frame: Math.floor((AG.f || 0) * (sc && sc.k === "flow" ? 10 : 14)), dir: dirx, hl: one } : { hl: one };
  if (one && pos) {   // CL-1025-37 P1 — 선택 고객 강조: 발 밑 접지 그림자 · 따뜻한 원형 조명(이동 중만 은은한 맥동) · 이동 중 표기(실제 장면의 목적지 이름만)
    const dest = walking && sc ? (sc.k === "move" ? agPlaceName(sc.b, R) : sc.name || sc.label || "") : "";
    const lbl = walking ? `${dno(pid)} · 이동 중${dest ? " → " + dest : ""}` : "";
    const tw = lbl ? (typeof textW === "function" ? textW(lbl, 12 * k, true) : lbl.length * 8) + 16 * k : 0, th = 20 * k, ly = pos[1] - 74 * k;
    h += `<g class="ag-hl${walking ? " mv" : ""}"><ellipse class="ag-hl-gnd" cx="${pos[0].toFixed(1)}" cy="${(pos[1] + 2 * k).toFixed(1)}" rx="${(18 * k).toFixed(1)}" ry="${(5 * k).toFixed(1)}"/><circle class="ag-hl-glow" cx="${pos[0].toFixed(1)}" cy="${(pos[1] - 20 * k).toFixed(1)}" r="${(40 * k).toFixed(1)}"/><circle class="ag-hl-ring" cx="${pos[0].toFixed(1)}" cy="${(pos[1] - 20 * k).toFixed(1)}" r="${(31 * k).toFixed(1)}" style="stroke-width:${(2.4 * k).toFixed(2)}px"/>${lbl ? `<g class="ag-hl-tag"><rect x="${(pos[0] - tw / 2).toFixed(1)}" y="${ly.toFixed(1)}" width="${tw.toFixed(1)}" height="${th.toFixed(1)}" rx="${(th / 2).toFixed(1)}"/><text x="${pos[0].toFixed(1)}" y="${(ly + th * 0.69).toFixed(1)}" text-anchor="middle" style="font-size:${(12 * k).toFixed(1)}px">${esc(lbl)}</text></g>` : ""}</g>`;
  }
  const av = one && pos ? agAvatarAsset(pid, agVC(pid, R).party) : null;
  const keep = av && $("#trail .ag-avimg"), reuse = keep && keep.dataset.av === av.key && keep.dataset.walk === (walking ? "1" : "0") && keep.classList.contains("gen") === gen && keep.classList.contains("ag-sel") === !!wo.hl;
  if (pos && !reuse) t += !one ? `<circle class="agentDot${gen ? " gen" : ""}" cx="${pos[0].toFixed(1)}" cy="${pos[1].toFixed(1)}" r="${8 * k}"/>`
    : agAvatarSvg(pid, agVC(pid, R).party, pos[0], pos[1], k, gen ? "gen" : walking ? "walk" : "", wo);
  $("#route").innerHTML = h;
  if (reuse) agAvatarMove(keep, av.key, pos[0], pos[1], wo); else $("#trail").innerHTML = t;   // 아바타 요소는 재생 중 유지(이미지 깜빡임 · 미표시 방지)
  agLabelsAvoid(anc, walking && one && sc && sc.mk ? sc.mk : null, k, walking);
}
// 건물 이름표가 현재 아바타 · 이동선을 가리지 않게 — 이동선에 걸린 이름표는 기존 네 방향 비킴(LABSHIFT) · 아바타와 겹치는 이름표는 옅게
let AG_LABKEY = "";
function agLabelsAvoid(pos, mk, k, walking) {   // 09-F 건물 이름표 — 이동 중에는 이동선에서 비키고(구간당 한 번), 멈춰 있으면 아바타 · 이름표 상자에서 실제로 비킨다
  if (typeof drawLabels !== "function" || typeof LABSHIFT === "undefined") return;
  const avEl = $("#trail .ag-avatar") || $("#agent .ag-pin.single .ag-avatar"), tgEl = $("#agent .ag-pin.single .ag-tag");
  const svgBox = el => { if (!el) return null; try { const r = el.getBoundingClientRect(), m = $("#map").getScreenCTM().inverse(), pt = $("#map").createSVGPoint(); pt.x = r.left; pt.y = r.top; const a = pt.matrixTransform(m); pt.x = r.right; pt.y = r.bottom; const b = pt.matrixTransform(m); return [a.x, a.y, b.x, b.y]; } catch (x) { return null; } };
  let box = svgBox(avEl); const tb = svgBox(tgEl);
  if (!box && pos) box = [pos[0] - 20 * k, pos[1] - 50 * k, pos[0] + 20 * k, pos[1] + 6 * k];
  const key = walking ? (mk ? "mk" + mk.total.toFixed(0) + (mk.pts[0] || []).join(",") : "w") : box ? "st" + box.map(v => Math.round(v / 6)).join(",") + (tb ? "t" + tb.map(v => Math.round(v / 6)).join(",") : "") : "";
  if (key !== AG_LABKEY) {
    AG_LABKEY = key; LABSHIFT.clear(); LABLINE = null;
    let pts = [];
    if (walking && mk && mk.pts && mk.pts.length > 1) pts = mk.pts.filter((_, i) => i % 2 === 0);
    else if (!walking) [box, tb].filter(Boolean).forEach(b => { for (let gx = 0; gx <= 4; gx++) for (let gy = 0; gy <= 3; gy++) pts.push([b[0] + (b[2] - b[0]) * gx / 4, b[1] + (b[3] - b[1]) * gy / 3]); });
    if (pts.length) { LABLINE = pts; $$("#labels .lab").forEach(t => { let b; try { b = t.getBBox(); } catch (x) { return; } if (pts.some(q => q[0] > b.x - 3 && q[0] < b.x + b.width + 3 && q[1] > b.y - 3 && q[1] < b.y + b.height + 3)) LABSHIFT.add(t.dataset.name); }); }
    drawLabels(); agHlLabels();
  }
  $$("#labels .lab").forEach(t => { let b; try { b = t.getBBox(); } catch (x) { return; } const hit = box && !(b.x + b.width < box[0] || b.x > box[2] || b.y + b.height < box[1] || b.y > box[3]); t.classList.toggle("ag-under", !!hit); });
}
function agHlLabels() {
  const R = AG.res; if (!R) return; const many = agIsMany(R);
  const nm = { PIZZA_HILL: "피자힐", MYONGWOLGWAN: "명월관", ONDAL: "온달", GEUMRYONG: "금룡", THE_BUFFET: "더뷔페", LE_PASSAGE: "르 파사쥬", FOREST: "포레스트 파크", SKYARD: "비스타 워커힐" };
  const names = new Set(R.customers.filter(c => !many || !AG.sel || c.persona_id === AG.sel).map(c => c.choice.venue_id === "ROOM_MEAL" || c.choice.venue_id === "ROOM" ? agVC(c.persona_id, R).bl : nm[c.choice.venue_id]));
  $$("#labels .lab").forEach(t => t.classList.toggle("ag-hl", names.has(t.dataset.name)));
}
function agSelect(pid) {
  const many = AG.res && agIsMany(AG.res);
  AG.sel = pid; if (AG.keep[AG.mode]) AG.keep[AG.mode].sel = pid; AG._sc = null;
  if (many && !AG.fix) {   // CL-11 — 재생을 멈추지 않고 고른 고객 카드 · 개인 일정 띠만 바꾼다
    const T = AG.manyT != null ? AG.manyT : agMin(AG.res.time);
    AG._opsAt = 0; agManyDraw(T); agStrip(); agStripNow(T); const pn = $("#panel"), right = $("#right"); if (pn) pn.scrollTop = 0; if (right) right.scrollTop = 0; return;
  }
  if (many && AG.manyMoving) { agManyDraw(AG.manyT); agStripState(); return; }   // 재생 중 — 멈추지 않고 강조만 바꾼다
  if (many) { cancelAnimationFrame(AG.raf); if (AG.at !== "mid") AG.at = "turn"; AG.f = 1; }   // 여러 명 — 보고 있던 턴을 유지하고 고객만 바꾼다(하루 재생 없음)
  agDrawMap(); agStrip(); agPanel(); if (!many) agPlay(); else agDrawRoute();
  const sh = $("#agSelH"), pn = $("#panel"); if (sh && pn) pn.scrollTop = Math.max(0, sh.offsetTop - pn.offsetTop - 8);   // 여러 명 — 고른 고객 상세로 스크롤
}

// ---------------------------------------------------------------- 아래 · 턴 타임라인 (분 단위 시간축이 아니라 확인된 지점만)
function agCtl(many) {   // CL-1024-13 — 재생 조작: 주 버튼(재생/일시정지) · 보조(주요 결정 · 처음부터) · 속도 — 같은 높이 · 한 줄
  return `<div class="tl2-ctl" role="group" aria-label="재생 조작">
    <button type="button" class="cf-btn cf-sm tl2-play ag-play" title="재생 · 주요 결정에서 잠시 머묾"><i class="tli">▶</i><small>방문 재생</small></button>
    <button type="button" class="cf-btn cf-sm ag-replay" title="다음 주요 결정으로"><i class="tli">⏭</i><span>주요 결정</span></button>
    <button type="button" class="cf-btn cf-sm ag-restart" title="처음부터 다시 보기"><i class="tli">↺</i><span>처음부터</span></button>
    <select id="agSpeed" class="tl2-spd" aria-label="재생 속도"><option value="slow"${AG.speed === "slow" ? " selected" : ""}>느리게</option><option value="normal"${!AG.speed || AG.speed === "normal" ? " selected" : ""}>보통</option><option value="fast"${AG.speed === "fast" ? " selected" : ""}>빠르게</option></select>
  </div>`;
}
function agCtlWire() {
  const b1 = $("#strip .ag-play"), b2 = $("#strip .ag-replay"), b3 = $("#strip .ag-restart"), sp = $("#agSpeed");
  if (b1) b1.onclick = agPlayToggle; if (b2) b2.onclick = agSkipNext; if (b3) b3.onclick = agRestart;
  if (sp) sp.onchange = e => { AG.speed = e.target.value; if (AG.playing && !(AG.res && agIsMany(AG.res))) { const keep = AG.f || 0; agPlayFrom(AG.si, keep); } };
}
const AG_TL_HELP = { what: "아래 띠는 고객의 하루를 실제 시각에 맞춰 그린 것입니다. 맨 위는 시각, 붉은 표식은 엔진이 계산한 주요 결정(재생이 잠시 머묾), 그 아래 얇은 띠는 일반 활동(색 = 활동 종류)입니다. 칸이 좁으면 이름을 생략하고, 누르면 그 시점의 상세가 오른쪽(여러 명은 활동 상세)에 나옵니다.", basis: ["운영 조건 · 계산", "실제 후기", "추출 성향"], caution: "주요 결정 외의 행동은 엔진 점수가 아니라 행동 계획기가 프로파일로 구성한 것입니다. 이동 시간은 표시용입니다." };
// 공통 시간축 — 시각(고정 좌표) · 주요 결정 · 활동 띠(시간 비례) · 현재 시각선. 이름은 칸에 들어갈 때만 표시(잘라 넣지 않음)
function agTlTicks(wa, wb) { const span = wb - wa; let h = ""; for (let m = Math.ceil(wa / 60) * 60; m <= wb; m += 60) h += `<i style="left:${((m - wa) / span * 100).toFixed(3)}%" data-m="${m}"><span>${String(m / 60).padStart(2, "0")}:00</span></i>`; return h; }
function agTlSeg(sc, pid, wa, span, opt = {}) {
  const cat = sc.blocked ? "room" : agCatOf(sc, pid), key = sc.k === "turn", mv = sc.k === "move";
  const l = ((Math.max(sc.t0, wa) - wa) / span * 100), w = Math.max(0.25, (Math.min(sc.t1, wa + span) - Math.max(sc.t0, wa)) / span * 100);
  const lab = mv || key ? "" : agScShort(sc, pid), full = mv ? "이동" : agScLabel(sc, pid);   // 주요 결정 이름은 위 표식 줄에만
  const at = sc.k === "flow" ? "mid" : sc.k;
  return `<button type="button" class="tl2-seg${key ? " key" : mv ? " mv" : sc.src === "review" ? " rv" : ""}" data-si="${sc.si}" data-at="${at}" data-ti="${sc.ti}" style="left:${l.toFixed(3)}%;width:${w.toFixed(3)}%;--vc:${key ? "var(--c-key)" : AG_CAT[cat].color}" title="${agHM(sc.t0)}–${agHM(sc.t1)} · ${esc(full)}${sc.src === "review" ? " · 후기에 같은 경험" : ""}" aria-label="${agHM(sc.t0)} ${esc(full)}"><i class="tl2-bar"></i>${lab ? `<span class="tl2-lab">${esc(lab)}</span>` : ""}</button>`;
}
function agTlKey(R, i, t, txt, sub, chg, wa, span) {
  return `<button type="button" class="tl2-key${chg ? " chg" : ""}" data-at="turn" data-ti="${i}" style="left:${((t - wa) / span * 100).toFixed(3)}%" title="${esc(txt)}${sub ? " · " + esc(sub) : ""}"><b>${esc(agHM(t))}</b><span>${esc(AG_TURN[R.turn] || R.turn)}</span>${chg ? `<em>변경</em>` : ""}</button>`;
}
function agTlFrame(title, sub, legend, help, rows, wa, wb) {
  return `<div class="tl2" data-wa="${wa}" data-wb="${wb}">
    <div class="tl2-head">${agCtl()}<div class="tl2-title"><b>${title}</b>${sub ? `<span>${sub}</span>` : ""}</div>${noteH(help)}</div>
    <div class="tl2-grid" id="agAxis2"><span class="tl2-rk"></span><div class="tl2-ticks">${agTlTicks(wa, wb)}</div>
      ${rows.map(r => `<span class="tl2-rk${r.cls ? " " + r.cls : ""}">${r.label}</span><div class="tl2-track ${r.band || ""}" data-band="${r.band || ""}">${r.html}</div>`).join("")}
      <i class="tl2-cur" id="agAxCur"><b></b></i></div><div class="tl2-legend">${legend}</div></div>`;
}
function agVisitDayNav() {
  if (!AG.visitData || !AG.visitData.visit_days || AG.visitData.visit_days.length < 2) return "";
  const names = { visit: "당일 방문", checkin: "체크인", mid: "연박", checkout: "체크아웃" };
  return `<nav class="ag-visit-days" aria-label="방문 날짜 선택">${AG.visitData.visit_days.map(d => `<button type="button" data-visit-day="${d.day_index}" class="${d.day_index === AG.visitDay ? "on" : ""}" aria-pressed="${d.day_index === AG.visitDay}"><b>${d.day_index}일차</b><span>${esc(d.date)} · ${names[d.phase] || d.phase}</span></button>`).join("")}</nav>`;
}
function agTlLegend(cats) { return cats.map(k => `<span><i style="background:${k === "key" ? "var(--c-key)" : AG_CAT[k].color}"></i>${k === "key" ? "주요 결정" : AG_CAT[k].label.split(" · ")[0]}</span>`).join(""); }
function agTlFit() {   // 이름표가 칸 폭 안에 들어가지 않으면 숨긴다(띠 · 누르기 · 툴팁은 그대로) · 시각 글자가 붐비면 2시간 간격
  const g = $("#agAxis2"); if (!g) return;
  $$("#strip .tl2-seg").forEach(s => { const lb = s.querySelector(".tl2-lab"); if (!lb) return; lb.hidden = false; if (lb.scrollWidth > s.clientWidth - 4) lb.hidden = true; });
  const tk = $$("#strip .tl2-ticks i"); if (tk.length > 1) { const w = tk[1].getBoundingClientRect().left - tk[0].getBoundingClientRect().left; tk.forEach((t, k) => t.classList.toggle("odd", w < 46 && k % 2 === 1)); }
  // 주요 결정 표식 — 앞 표식과 겹치면 '시각+이름' → '이름만'으로 줄이고(시각은 축 · 툴팁), 그래도 겹치면 앞 표식을 이름만으로
  const keys = $$("#strip .tl2-key"); keys.forEach(k => k.classList.remove("lift"));
  for (let i = 1; i < keys.length; i++) { const a = keys[i - 1], b = keys[i]; if (b.getBoundingClientRect().left < a.getBoundingClientRect().right + 4) { b.classList.add("lift"); if (b.getBoundingClientRect().left < a.getBoundingClientRect().right + 4) a.classList.add("lift"); } }
}
function agTlCursor(T) {   // 현재 시각선 — 시간 비례 위치(라벨 열 제외) · 근처 정시 글자 숨김
  const g = $("#agAxis2"), cur = $("#agAxCur"), tl = $("#strip .tl2"); if (!g || !cur || !tl || T == null) return;
  const wa = +tl.dataset.wa, wb = +tl.dataset.wb, tr = g.querySelector(".tl2-ticks"); if (!tr) return;
  const f = Math.max(0, Math.min(1, (T - wa) / Math.max(1, wb - wa))), gb = g.getBoundingClientRect(), tb = tr.getBoundingClientRect();
  cur.style.left = `${(tb.left - gb.left + f * tb.width).toFixed(1)}px`; cur.querySelector("b").textContent = agHM(T); cur.dataset.t = agHM(T);
  const cb = cur.querySelector("b").getBoundingClientRect();   // 시각선 이름표와 실제로 겹치는 정시 글자만 숨김
  $$("#strip .tl2-ticks i").forEach(t => { t.classList.remove("near"); const sp = t.querySelector("span"); if (!sp) return; const r = sp.getBoundingClientRect(); if (!(r.right < cb.left - 3 || r.left > cb.right + 3)) t.classList.add("near"); });
}
function agStrip() {
  const el = $("#strip"), R = AG.res, c = agCur();
  if (R && agIsMany(R)) return agStripMany(el);
  if (!R || !c) { el.innerHTML = ""; el.classList.add("ag-off"); return; }
  el.classList.remove("ag-off"); el.style.height = "";
  const runs = AG.runs.length ? AG.runs : [R], pid = c.persona_id, L = agScenes(pid), cp = agComp(pid, agVC(pid, R).party);
  const wa = Math.floor(Math.min(...L.map(x => x.t0)) / 60) * 60, wb = Math.ceil(Math.max(...L.map(x => x.t1)) / 60) * 60, span = Math.max(60, wb - wa);
  const keys = L.filter(x => x.k === "turn").map(x => { const run = runs[x.ti], cc = run.compare && run.compare.customers.find(y => y.persona_id === pid), ch = agCustOf(run, pid);
    return agTlKey(run, x.ti, x.t0, `${AG_TURN[run.turn]} ${agHM(x.t0)}`, ch ? agChoiceName(run, ch.choice) : "", cc && cc.status === "changed", wa, span).replace('data-at="turn"', `data-at="turn" data-si="${x.si}"`); }).join("");
  const segs = L.map(x => agTlSeg(x, pid, wa, span)).join("");
  const cats = [...new Set(L.filter(x => x.k !== "turn" && x.k !== "move").map(x => agCatOf(x, pid)))];
  const frameTitle = AG.visitData ? `${esc(dno(pid))} 방문 · ${AG.visitDay}일차` : `${esc(dno(pid))}의 ${runs.length > 1 ? "하루" : AG_TURN[R.turn] + " 턴"}`;
  el.innerHTML = agTlFrame(frameTitle, esc(cp.scen || ""), agTlLegend(["key", ...AG_CAT_ORDER.filter(k => cats.includes(k))]), AG_TL_HELP,
    [{ label: "주요 결정", band: "tl2-keys", html: keys }, { label: "활동", band: "tl2-acts", html: segs }], wa, wb);
  if (AG.visitData) {
    el.innerHTML = agVisitDayNav() + el.innerHTML;
    el.querySelectorAll("[data-visit-day]").forEach(button => button.onclick = () => agVisitDaySelect(Number(button.dataset.visitDay)));
  }
  agCtlWire(); agTlFit();
  $$("#strip [data-si]").forEach(b => b.onclick = () => { cancelAnimationFrame(AG.raf); AG.playing = false; AG.paused = false; const sc = L.find(x => x.si === +b.dataset.si); agSetScene(+b.dataset.si, sc && sc.k === "move" ? 0.5 : sc && sc.k === "flow" ? 1 : null); agStripState(); });
  agStripState();
}
function agStripCell(sc, pid, runs) { return agTlSeg(sc, pid, 0, 1440); }   // 호환(이전 이름)
function agStripMany(el) {   // 여러 명 — 주요 결정(시각 · 인원) · 활동 밀도(15분 · 종류별 인원) · 고른 고객의 하루(활동 띠) · 공통 시간축
  const runs = AG.runs.length ? AG.runs : [AG.res], [wa, wb] = agManyWindow(), span = Math.max(60, wb - wa);
  const sum = run => { const m = {}; run.customers.forEach(x => m[x.choice.venue_id] = (m[x.choice.venue_id] || 0) + 1); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([v, k]) => `${agVenueName(run, v).split(" · ")[0].replace(/\(.*\)/, "")} ${k}`).join(" · "); };
  const nAll = agAllIds().length;
  const keys = runs.map((run, i) => agTlKey(run, i, agMin(run.time) || 0, `${AG_TURN[run.turn]} ${run.time} · ${run.customers.length}팀`, sum(run), run.compare && run.compare.customers.some(y => y.status === "changed"), wa, span).replace("</span>", ` <small>${run.customers.length}팀</small></span>`)).join("");
  const step = 15, maxN = Math.max(1, nAll); let dens = "";
  for (let t = Math.floor(wa / step) * step; t < wb; t += step) { const O = agOpsAt(t + step / 2); const segs = AG_CAT_ORDER.filter(k => (O.byCat[k] || []).length).map(k => [k, O.byCat[k].length]);
    dens += `<span class="dn" data-t="${t + step / 2}" style="left:${((t - wa) / span * 100).toFixed(3)}%;width:${(step / span * 100).toFixed(3)}%" title="${agHM(t)}–${agHM(t + step)} · 호텔 안 ${O.present.length}팀${segs.length ? " · " + segs.map(([k, n]) => `${AG_CAT[k].label} ${n}`).join(" · ") : ""}">${segs.map(([k, n]) => `<i style="height:${(n / maxN * 100).toFixed(1)}%;background:${AG_CAT[k].color}"></i>`).join("")}</span>`; }
  const sel = AG.sel && agAllIds().includes(AG.sel) ? AG.sel : null;
  const me = sel ? agScenes(sel).map(x => agTlSeg(x, sel, wa, span).replace('class="tl2-seg', 'class="tl2-seg tl2-me')).join("") : `<span class="tl2-empty">지도 · 오른쪽에서 고객을 누르면 그 고객의 하루가 여기에 나옵니다</span>`;
  el.classList.remove("ag-off"); el.style.height = "";
  el.innerHTML = agTlFrame(`고객 ${nAll}팀의 방문`, "", agTlLegend(["key", "meal", "well", "culture", "walk", "room", "move"]),
    { what: "맨 위는 시각, 붉은 표식은 엔진이 계산한 주요 소비 결정(재생이 잠시 머묾), 가운데 막대는 15분마다 호텔 안 고객이 무엇을 하는지(활동 종류별 인원), 고객을 고르면 맨 아래에 그 고객의 하루가 활동 띠로 나옵니다. 막대 · 띠를 누르면 그 시각으로 갑니다.", basis: ["운영 조건 · 계산", "추출 성향", "실제 후기"], caution: "주요 결정 외의 활동은 행동 계획기가 프로파일 · 동행 · 체류 단계로 구성한 것이며 엔진 점수가 아닙니다. 이동 시간은 표시용입니다." },
    [{ label: "주요 결정", band: "tl2-keys", html: keys }, { label: "활동 밀도", band: "tl2-dens", html: dens }, { label: sel ? esc(dno(sel)) : "고객", cls: sel ? "tl2-rk-me" : "", band: "tl2-acts", html: me }], wa, wb);
  if (AG.visitData) {
    el.innerHTML = agVisitDayNav() + el.innerHTML;
    el.querySelectorAll("[data-visit-day]").forEach(button => button.onclick = () => agVisitDaySelect(Number(button.dataset.visitDay)));
  }
  agCtlWire(); agTlFit();
  $$("#strip .tl2-key").forEach(b => { b.onclick = ev => { ev.stopPropagation(); agManyJump(agMin(runs[+b.dataset.ti].time)); AG.at = "turn"; agStripState(); }; });
  $$("#strip .tl2-dens .dn").forEach(b => b.onclick = () => agManyJump(+b.dataset.t));
  $$("#strip .tl2-me").forEach(b => b.onclick = () => { const sc = agScenes(sel).find(x => x.si === +b.dataset.si); if (!sc) return; agManyJump(sc.t0 + Math.min(5, (sc.t1 - sc.t0) / 2)); if (sc.k !== "move") agActDrawer(sel, sc.si); });
  agStripState();
}
function agStripNow(nowMin) {   // 여러 명 — 현재 시각선 · 고른 고객의 지금 활동 표시
  agTlCursor(nowMin);
  $$("#strip .tl2-me").forEach(b => { const sc = AG.sel && agScenes(AG.sel).find(x => x.si === +b.dataset.si); b.classList.toggle("now", !!sc && nowMin >= sc.t0 && nowMin < sc.t1); });
}
function agStripMark() {   // 한 명 — 현재 장면 안 진행에 맞춘 시각선(매 프레임)
  if (!(AG.res && agIsOne(AG.res))) return;
  const c = agCur(); if (!c) return; const sc = agScenes(c.persona_id)[AG.si]; if (!sc) return;
  agTlCursor(sc.k === "turn" ? sc.t0 : sc.t0 + (AG.f || 0) * (sc.t1 - sc.t0));
}
function agStripState() {
  const one = AG.res && agIsOne(AG.res);
  $$("#strip [data-si]").forEach(b => b.classList.toggle("sel", one && +b.dataset.si === AG.si));
  if (!one) { $$("#strip .tl2-key").forEach(b => b.classList.toggle("sel", AG.at === "turn" && +b.dataset.ti === AG.ti)); if (AG.manyT != null) agStripNow(AG.manyT); else if (AG.res) agStripNow(agMin(AG.res.time)); }
  agStripMark();
  const pb = $("#strip .ag-play");
  if (pb) { pb.querySelector(".tli").textContent = AG.playing ? "❚❚" : "▶";
    pb.querySelector("small").textContent = AG.playing ? "일시정지" : AG.paused ? "이어보기" : AG.ended ? "처음부터 재생" : "방문 재생";
    pb.classList.toggle("on", !!AG.playing); }
}
// ---------------------------------------------------------------- 오른쪽 — 사진 → 장소 · 행동 · 시간 → 선택 결과 → 이유 → 성향 → 상세
function agBars(bars, compact) {
  return `<div class="ag-bars${compact ? " sm" : ""}">${bars.map(b => b.status === "observed"
    ? `<div class="ag-bar f-${b.key}"><span class="ag-bl">${esc(b.label)}</span><span class="ag-bt"><i style="width:${Math.round(b.level * 100)}%"></i></span><span class="ag-bv">근거 ${b.evidence_count}건</span></div>`
    : `<div class="ag-bar none"><span class="ag-bl">${esc(b.label)}</span><span class="ag-bt"></span><span class="ag-bv">근거 미확인</span></div>`).join("")}</div>`;
}
function agStack(c) {
  const t = c.reason_totals, pos = Object.entries(t).filter(([, v]) => v > 0), sum = pos.reduce((a, [, v]) => a + v, 0) || 1;
  return `<div class="ag-stack" title="선택 점수를 이룬 몫(양의 값)">${pos.map(([k, v]) => `<i class="s-${k}" style="width:${(v / sum * 100).toFixed(1)}%"></i>`).join("")}</div>
    <div class="ag-skey">${["review", "common", "assumption", "transfer", "out_of_scope"].filter(k => k in t).map(k => `<span${k === "out_of_scope" ? ' class="dev-only"' : ""}><i class="s-${k}"></i>${AG_CLS[k]} ${agNum(t[k])}</span>`).join("")}</div>`;
}
function agTop(c) {
  return c.reasons.filter(r => r.parts.review > 0.01 || r.parts.assumption > 0.01).sort((a, b) => (b.parts.review + b.parts.assumption) - (a.parts.review + a.parts.assumption)).slice(0, 2);
}
function agWhy(c) {
  const top = agTop(c);
  if (!top.length) return "";
  return `<ul class="ag-why">${top.map(r => { const rv = r.parts.review > r.parts.assumption; return `<li${rv && r.fact_ids.length ? ` class="lnk" data-ff="${esc(r.fact_ids.join(","))}" title="이 항의 근거가 나온 후기 경험 보기"` : ""}><span class="ag-rc s-${rv ? "review" : "assumption"}"></span><span class="ag-wt">${escP(r.factor)}</span><b>+${agNum(rv ? r.parts.review : r.parts.assumption)}</b><span class="hint">${rv ? `후기 근거 ${r.fact_ids.length}건 ›` : "설계 가정"}</span></li>`; }).join("")}</ul>`;
}
// 운영자가 먼저 읽는 한두 문장 — 엔진이 돌려준 항 · 근거 요지만으로 만든다(없는 이유를 지어내지 않음)
const agJosa = (w, a, b) => { const ch = (w || "").trim().slice(-1).charCodeAt(0); return ch >= 0xac00 && ch <= 0xd7a3 && (ch - 0xac00) % 28 ? a : b; };
function agSentence(c) {
  const V = c.choice.venue_id === "ROOM_MEAL" ? "객실 식사" : c.choice.venue_id === "FOREST" ? "와인페어" : c.choice.venue_id === "SKYARD" ? "스카이야드 족욕" : c.choice.venue_id === "ROOM" ? "객실 휴식" : c.choice.venue_label;
  const rv = c.reasons.filter(r => r.parts.review > 0.01).sort((a, b) => b.parts.review - a.parts.review).slice(0, 2);
  const o = c.best_other_venue, near = o && o.margin < 0.15;
  let s, gist = "";
  const T = c.reason_totals, strong = rv.length && T.review >= 0.3 && T.review >= T.assumption;
  if (rv.length) {
    const names = rv.map(r => r.factor.replace(/ · /g, "·").replace(/\s*\([^)]*\)\s*$/, "")), last = names[names.length - 1], nm = names.length > 1 ? names[0] + agJosa(names[0], "과", "와") + " " + last : last;
    s = strong ? `후기에서 ${nm}${agJosa(last, "이", "가")} 드러나는 고객으로, 이번 조건에서는 ${V}${agJosa(V, "을", "를")} 골랐습니다.`
      : `이번 조건에서는 가격과 기본 조건이 크게 작용해 ${V}${agJosa(V, "을", "를")} 골랐고, 후기에서 드러난 ${nm}${agJosa(last, "이", "가")} 이를 조금 더 받쳤습니다.`;
    const f = (rv[0].fact_ids || []).map(x => agEvidenceText(c, x)).find(t => t !== "설명 확인 필요");   // 요지가 없으면 지어내지 않고 생략(코덱스 b0d2015 규칙)
    if (f) gist = f.length > 56 ? f.slice(0, 55) + "…" : f;
  } else if ((c.reasons||[]).some(r=>Math.abs((r.parts||{}).review||0)>1e-6)) {
    s = `이번 선택에는 개인 후기 기여 ${agU06Signed(T.review||0)}가 반영됐습니다. ${T.review<0?'선택 점수를 낮춘 항이며, 미반영을 뜻하지 않습니다.':'양수와 음수 기여의 합계를 구분해 봅니다.'}`;
  } else {
    s = `이번 조건에서는 가격과 기본 조건만으로 ${V}${agJosa(V, "을", "를")} 골랐습니다 — 이 고객만의 성향이 드러난 선택은 아닙니다.`;
  }
  // 근거 없는 설계 가정(객실 휴식 가치)이 다른 업장과의 차이보다 크면 같은 문장에 밝힌다 — 가정이 결정을 좌우하는 선택(02-D)
  if (T.assumption > 0.01 && o && o.margin != null && T.assumption > o.margin) s += ` 객실에서 쉬는 가치(설계값)가 ${o.venue_label}${agJosa(o.venue_label, "과", "와")}의 차이보다 커서, 이 값에 따라 결과가 달라질 수 있습니다.`;
  const ff = rv.flatMap(r => r.fact_ids || []);
  return { p: `<div class="ag-say"><p>${esc(s)}</p></div>`, gist: gist ? `<button type="button" class="ag-gist" data-ff="${esc(ff.join(","))}" title="이 근거가 나온 후기 경험을 프로파일에서 보기"><span>근거 경험</span>${esc(gist)} <b>›</b></button>` : "" };
}
// 운영 조건을 바꿨을 때 — 기본 조건 대비 선택 변화
function agCmp(c) {
  const C = AG.res.compare; if (!C) return "";
  const x = C.customers.find(y => y.persona_id === c.persona_id); if (!x) return "";
  const box = (v, lab) => `<div class="ag-cb"><span>${lab}</span>${agDot(v.venue_id)}<b>${esc(({ ROOM_MEAL: "객실 식사", PIZZA_HILL: "피자힐", MYONGWOLGWAN: "명월관", ONDAL: "온달", GEUMRYONG: "금룡", THE_BUFFET: "더뷔페", LE_PASSAGE: "르 파사쥬", ROOM: "객실", FOREST: "와인페어", SKYARD: "족욕", NONE: "결정 없음", POOL: "수영장", SAUNA: "사우나" })[v.venue_id] || v.venue_id)}</b><em>${esc(agShort(v.product_label))}</em></div>`;
  const drv = x.top_drivers.slice(0, 2).map(d => `<span class="${d.delta < 0 ? "neg" : "pos"}">${esc(d.factor)} ${d.delta > 0 ? "+" : ""}${agNum(d.delta)}</span>`).join("");
  if (x.status === "changed") return `<div class="ag-cmp2 chg"><div class="ag-cmh">운영 조건 변경 · 선택이 바뀜</div><div class="ag-cmr">${box(x.before, "기본 조건")}<i>→</i>${box(x.after, "바꾼 조건")}</div>${drv ? `<div class="ag-drv">${drv}</div><small class="hint">선택 전후 상품의 기여 차이 · 변경한 운영 조건의 순수 효과가 아닙니다</small>` : ""}</div>`;
  return `<div class="ag-cmp2"><div class="ag-cmh">운영 조건 변경 · 선택 유지${x.status === "score_only" ? ` <span class="hint">점수 ${x.score_delta > 0 ? "+" : ""}${agNum(x.score_delta)}</span>` : ""}</div></div>`;
}
const AG_FACET = { space: /공간|야경|전망|조망/, food: /음식|식사 경험|미식/, value_check: /지불|가격|가치/, benefit: /혜택|할인|포함/, rest_need: /휴식|회복/, routine: /익숙|이용 경험|재방문/ };
function agBarsFor(c) {   // 이번 선택에 작용한 성향을 먼저 · 최대 5개
  const used = new Set(Object.keys(AG_FACET).filter(k => c.reasons.some(r => r.parts.review > 0.1 && AG_FACET[k].test(r.factor))));
  const bars = [...c.persona.bars].sort((a, b) => (used.has(b.key) - used.has(a.key)) || ((b.status === "observed") - (a.status === "observed"))).slice(0, 5);
  return { html: agBars(bars).replace(/<div class="ag-bar f-(\w+)">/g, (m, k) => used.has(k) ? `<div class="ag-bar f-${k} used">` : m), n: used.size, used: c.persona.bars.filter(x => used.has(x.key) && x.status === "observed") };
}
function agToProfile(pid, ff) {
  if (typeof libOpen === "function" && typeof LIBV !== "undefined") { libOpen(pid, ff); return; }
  agProfile(pid);
}
const agPlace = (R, ch, pid) => ch.venue_id === "ROOM_MEAL" || ch.venue_id === "ROOM" ? `${agVC(pid, R).bl} 객실` : ch.venue_label;
const agChoiceName = (R, ch) => R.turn === "event" && ch.venue_id === "FOREST" ? "와인페어 · 포레스트 파크"
  : R.turn === "event" && ch.venue_id === "SKYARD" ? "족욕 · 스카이야드" : `${ch.venue_label} · ${agShort(ch.product_label)}`;
const agIsSkip = ch => ch.venue_id === "ROOM";
// 핵심 선택 사이의 연결 장면 — 프로필 성향으로 고른 일상 문장(구매 · 방문 · 음주 같은 사건은 만들지 않음 · 엔진 계산 아님)
function agMidLine(c, R, nR) {
  const lv = k => { const b = (c.persona.bars || []).find(x => x.key === k); return b && b.level != null ? b.level : 0; };
  const who = lv("rest_need") >= 0.5 ? "조용히 쉬는 시간을 중요하게 여기는" : lv("space") >= 0.5 ? "공간과 풍경을 즐기는" : lv("food") >= 0.5 ? "식사 경험을 중요하게 여기는" : "자기 속도로 하루를 보내는";
  const inRoom = ["ROOM_MEAL", "ROOM"].includes(c.choice.venue_id);   // 위치 표시는 직전 장소에 머무르므로 장면도 그 자리에 맞춘다
  const doing = inRoom ? (lv("space") >= 0.5 && lv("rest_need") < 0.5 ? "객실 창밖 풍경을 보며 쉬는" : "객실에서 잠시 쉬는")
    : lv("space") >= 0.5 ? "주변 정원을 천천히 걸으며 시간을 보내는" : "근처에서 잠시 쉬며 다음 일정을 기다리는";
  return `${who} 이 고객은 ${agPlace(R, c.choice, c.persona_id)}에서 ${AG_TURN[R.turn]}을 마친 뒤${nR ? ` ${AG_TURN[nR.turn]}(${nR.time || ""}) 전까지` : ""} ${doing} 흐름으로 이어집니다.`;
}
function agFlowLine(c, R, fl, nR) {   // 장면별 한 문장 — 성향 수준(휴식 · 공간)과 장면 규칙만으로
  const lv = k => agLvl(c, k), who = lv("rest_need") >= 0.5 ? "조용히 쉬는 시간을 중요하게 여기는" : lv("space") >= 0.5 ? "공간과 풍경을 즐기는" : lv("food") >= 0.5 ? "식사 경험을 중요하게 여기는" : "자기 속도로 하루를 보내는";
  const nxt = nR ? ` ${AG_TURN[nR.turn]}(${nR.time || ""}) 전까지` : "";
  const d = fl.slot === "noon" ? `점심 시간대를 호텔 안에서 보내는 것으로 두었습니다(이 시간대에는 엔진 턴이 없어 식사 여부 · 장소를 계산하지 않음)`
    : fl.loc === "AG_GARDEN" ? `${fl.name}을 천천히 걷는 흐름으로 이어집니다` : /_ROOM$/.test(fl.loc || "") ? `${fl.name}에서 쉬는 흐름으로 이어집니다` : fl.loc === "HOTEL_GATE" ? `하루를 마치고 돌아가는 흐름으로 이어집니다` : `${fl.name || "호텔 안"}을 둘러보는 흐름으로 이어집니다`;
  return `${who} 이 고객은 ${AG_TURN[R.turn]}을 마친 뒤${nxt} ${d}.`;
}
// ---------------------------------------------------------------- 10/24 09-A 오른쪽 — 한 정보 영역: 시각 · 장면 → 이미지 · 선택 → 이유 → 가격 · 대안 · 조건 영향 → 링크 → (펼침) 상세
const AG_TRAIT_KO = { food: "식사 경험", space: "공간 · 풍경", value_check: "가격 확인", benefit: "혜택 활용", rest_need: "휴식", routine: "익숙함", warm_rest: "온수 · 휴식", active: "활동적", alcohol_familiar: "와인 · 주류", novelty: "새 경험", premium: "프리미엄", food_specific: "음식 취향", practical_alt: "실용적 대안", breakfast_priority: "아침 식사", seasonal: "계절 · 행사", promo: "홍보 · 혜택" };
const AG_SC_ICON = {
  start: '<path d="M5 20V9l7-5 7 5v11"/><path d="M10 20v-6h4v6"/>', move: '<path d="M4 12h13"/><path d="M13 7l5 5-5 5"/>',
  walk: '<circle cx="13" cy="4.5" r="1.8"/><path d="M10 21l2-6 3 3v3M9 11l3-3 3 2 2 3M12 8l-2 5"/>', rest: '<path d="M3 18V8M3 14h18v4M7 14v-2.5a2 2 0 0 1 2-2h8a4 4 0 0 1 4 4V14"/><circle cx="7" cy="10" r="1.6"/>',
  lobby: '<path d="M4 20h16M6 20V8h12v12M9 11h2M13 11h2M9 15h2M13 15h2"/>', noon: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
  pool: '<path d="M3 17c2 1.3 4 1.3 6 0s4-1.3 6 0 4 1.3 6 0M3 21c2 1.3 4 1.3 6 0s4-1.3 6 0 4 1.3 6 0M8 14V5a2 2 0 0 1 4 0M16 14V5a2 2 0 0 0-4 0M8 8h8"/>',
  foot: '<path d="M4 16c2 1.3 4 1.3 6 0s4-1.3 6 0 3 1 4 .5M8 13V6M12 12V5M16 13V7"/>', forest: '<path d="M12 3l5 7h-3l4 6H6l4-6H7z"/><path d="M12 16v5"/>',
  sauna: '<path d="M6 21h12M8 17h8l1-5H7zM9 9c0-2 1.5-2 1.5-4M13 9c0-2 1.5-2 1.5-4"/>', garden: '<circle cx="12" cy="9" r="4"/><path d="M12 13v8M8 21h8"/>', home: '<path d="M4 11l8-6 8 6v9H4z"/><path d="M10 20v-5h4v5"/>',
};
const agScIcon = k => `<svg class="rp-ic" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${AG_SC_ICON[k] || AG_SC_ICON.walk}</svg>`;
const AG_WHY_HELP = { what: "엔진이 이번 조건에서 이 선택을 고른 이유를, 후기 근거가 큰 항목부터 한두 문장으로 옮긴 것입니다.", basis: ["실제 후기", "추출 성향", "운영 조건 · 계산"], caution: "후기에서 관측한 이번 방문의 행동이 아니라 시뮬레이션 결과입니다. 근거 없는 설계값(객실 휴식 가치)에 기대는 경우 문장에 함께 적습니다." };
const AG_ALT_HELP = { what: "같은 계산에서 다음으로 점수가 높았던 다른 업장입니다.", basis: ["운영 조건 · 계산"], caution: "점수 차는 선택 확률이나 방문 비율이 아닙니다. 0.15보다 작으면 '근소'로, 조건이 조금만 바뀌어도 선택이 바뀔 수 있습니다." };
// CL-1024-14 A-2 — 제목 위계: 업장(가장 큼) → 선택 메뉴(한 단계 작게 · 옵션은 ' - ') → 가격(독립 행)
const agVenueTitle = (R, ch, pid) => R.turn === "event" ? (ch.venue_id === "FOREST" ? "와인페어 · 포레스트 파크" : ch.venue_id === "SKYARD" ? "스카이야드" : `${agVC(pid, R).bl} 객실`)
  : ch.venue_id === "ROOM_MEAL" || ch.venue_id === "ROOM" ? `${agVC(pid, R).bl} 객실` : (ch.venue_label || ch.venue_id);
const agMenuTitle = (R, ch) => R.turn === "event" ? (ch.venue_id === "FOREST" ? "와인페어 참여" : ch.venue_id === "SKYARD" ? "족욕" : "행사 대신 객실 휴식")
  : ch.venue_id === "ROOM" ? (R.turn === "breakfast" ? "아침 건너뜀" : "저녁 건너뜀") : ch.venue_id === "ROOM_MEAL" ? `룸서비스 · ${agMenu(ch.product_label)}` : agMenu(ch.product_label);
// CL-1024-14 A-3 — 상세 정보: ①선택한 상품 ②실제 점수 비교 대상 ③조건 때문에 제외된 후보(이유) ④점수에 영향을 준 조건 · 근거. 긴 계산 문장은 개발 정보에서만
const agWhyShort = w => { const t = String(w || ""); if (/인원 기준 미확인/.test(t)) return "인원 기준 미확인 · 1인 가격 미정"; return t.split(/\s+—\s+/)[0].replace(/\b[a-z]+_[a-z_]+\b/g, "").replace(/\s{2,}/g, " ").trim() || "조건 불충족"; };
function agDetailTables(R, c, sy, gistOk, chained) {
  const ch = c.choice, pr = ch.price || {}, paid = pr.paid_krw != null ? pr.paid_krw : pr.pp_krw;
  const nm = x => x.venue_id === "ROOM_MEAL" ? `룸서비스 · ${agMenu(x.product_label)}` : `${(x.venue_label || "").replace(/\(.*\)$/, "")} · ${agMenu(x.product_label)}`;
  const scored = (c.not_chosen || []).filter(x => x.feasible && x.score != null).sort((a, b) => b.score - a.score);
  const top = scored.slice(0, 4);
  const blockedNC = (c.not_chosen || []).filter(x => !x.feasible).map(x => ({ label: nm(x), why: (x.blocked || []).join(" · ") }));
  const exc = [...R.excluded.map(e => ({ label: agShort(e.product_label).replace(/^(룸서비스|피자힐) /, ""), venue: /^룸서비스/.test(e.product_label) ? "룸서비스" : /^피자힐/.test(e.product_label) ? "피자힐" : "", why: e.why })), ...blockedNC.map(x => ({ label: x.label, venue: "", why: x.why }))];
  const exLabel = e => e.venue ? `${e.venue} · ${agMenu(e.label)}` : agMenu(e.label);
  return `<div class="rp-ds"><h5>선택한 상품</h5><div class="rp-tbl rp-tsel"><div><b>${esc(nm(ch))}</b><span>${paid != null ? `1인 ${agWon(paid)}` : "가격 없음"}</span><span class="num">점수 ${agNum(ch.score)}</span></div></div></div>
    ${top.length ? `<div class="rp-ds"><h5>실제 점수 비교 대상 <small>${scored.length}개 중 상위 ${top.length}</small></h5><div class="rp-tbl rp-tcmp"><div class="rp-th"><span>후보</span><span>점수</span><span>선택과 차</span></div>${top.map(x => `<div><span>${esc(nm(x))}</span><span class="num">${agNum(x.score)}</span><span class="num">−${agNum(ch.score - x.score)}</span></div>`).join("")}</div></div>` : ""}
    ${exc.length ? (() => { const tbl = `<div class="rp-tbl rp-texc"><div class="rp-th"><span>후보</span><span>처리</span><span>이유</span></div>${exc.map(e => `<div><span>${esc(exLabel(e))}</span><span class="rp-x">제외</span><span>${esc(agWhyShort(e.why))}</span></div>`).join("")}</div>`;
      const by = {}; exc.forEach(e => { const w = agWhyShort(e.why); by[w] = (by[w] || 0) + 1; });   // CL-1024-15 — 많으면 사유별 개수부터, 펼치면 상품 목록
      const sum = `<div class="rp-tbl rp-tsum"><div class="rp-th"><span>제외 사유</span><span>상품 수</span></div>${Object.entries(by).sort((a, b) => b[1] - a[1]).map(([w, n]) => `<div><span>${esc(w)}</span><span class="num">${n}개</span></div>`).join("")}</div>`;
      return `<div class="rp-ds"><h5>후보에서 제외 <small>점수를 계산하지 않음 · ${exc.length}개</small></h5>${exc.length > 3 ? `${sum}<details class="rp-exd"><summary>제외 상품 ${exc.length}개 보기</summary>${tbl}</details>` : tbl}<div class="dev rp-devw">${esc(exc.map(e => `${e.label}: ${e.why}`).join(" / "))}</div></div>`; })() : ""}
    <div class="rp-ds"><h5>점수에 영향을 준 조건과 근거</h5>${agStack(c)}
      ${gistOk ? `<div class="rp-gist">${sy.gist}</div>` : sy.gist ? `<div class="rp-mut">대표 후기 근거는 화면 표시 기준에 따라 숨김</div>` : ""}
      ${chained ? `<div class="rp-mut">이전 행사 턴의 결과(상태)를 이어서 계산</div>` : ""}</div>`;
}
// U06: presentation-only views of the existing decision packet and L5 ledger.
function agUXNext(pid,scene) {
  const list=agScenes(pid),here=scene || (typeof agScene==='function' && agScene()) || list.find(s=>s.k==='turn' && s.ti===AG.ti);
  const i=list.findIndex(s=>here && s.si===here.si), next=i>=0 && list.slice(i+1).find(s=>s.k!=='move');
  return next?`<div class="ux-next"><small>다음 일정</small><span>${agHM(next.t0)} · ${esc(agScLabel(next,pid))}</span></div>`:'<div class="ux-next"><small>다음 일정</small><span>방문 일정 종료</span></div>';
}
function agUXMultiReasons(pid,scene) {
  if(!scene||scene.k==='turn')return '';
  const d=agU06Packet(pid,scene),row=d&&d.packet.candidates.find(c=>c.candidate_id===d.selected_action);
  const terms=row&&(row.terms||[]).filter(t=>t.value).slice().sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).slice(0,2);
  const lines=terms&&terms.length?'<small>현재 행동의 선택 전 계산 항</small>'+terms.map(t=>`<p>${esc(t.factor)} <b>${agU06Signed(t.value)}</b></p>`).join(''):'';
  return `<div class="ux-current-reasons">${lines}<button class="rp-link" data-ux-scene="${scene.si}" data-ux-person="${esc(pid)}">이 행동의 자세한 판단 근거 →</button></div>`;
}
document.addEventListener('click',ev=>{
  const turn=ev.target.closest('[data-ux-reason]'), activity=ev.target.closest('[data-ux-scene]');
  if(turn && !turn.closest('#drawer')){if(typeof bhFromFlow==='function')bhFromFlow(turn.dataset.uxReason,+turn.dataset.uxTi);}
  if(activity && typeof bhFromScene==='function'){if(activity.closest('#drawer'))closeDrawer();bhFromScene(activity.dataset.uxPerson,+activity.dataset.uxScene);}
});
// Right-panel presentation only. Original run, decisions, avatar mappings and L5 rows stay read-only.
// Presentation-only reading state: never stored in runs, decisions or ledgers.
const AG_READING = new Map();
let agReadingSerial=0;
function agReadingKey(pid,scene,kind) { return JSON.stringify([AG.flow&&AG.flow.ledger&&AG.flow.ledger.run_id,pid,scene&&scene.visit_date||AG.visitDay,scene&&scene.si,kind]); }
function agReadableHTML(text,key,lines=3,extra='') {
  const id='ag-reading-'+(++agReadingSerial),open=AG_READING.get(key)===true;
  return `<div class="ag-readable ${extra}${open?' expanded':''}" data-reading-key="${esc(key)}" style="--reading-lines:${lines}"><div class="ag-readable-body" id="${id}">${esc(String(text||''))}</div><button type="button" class="rp-link" data-reading-toggle aria-expanded="${open}" aria-controls="${id}"${open?'':' hidden'}>${open?'접기':'더보기'}</button></div>`;
}
function agReadableMount(root) {
  const measure=()=>root.querySelectorAll('[data-reading-key]').forEach(el=>{const body=el.querySelector('.ag-readable-body'),button=el.querySelector('[data-reading-toggle]');if(!body||!button)return;button.hidden=!el.classList.contains('expanded')&&body.scrollHeight<=body.clientHeight+1;});
  measure();requestAnimationFrame(()=>{if(root.isConnected)measure();});
}
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-reading-toggle]');if(!button)return;
  event.preventDefault();event.stopImmediatePropagation();const el=button.closest('[data-reading-key]'),open=!el.classList.contains('expanded');AG_READING.set(el.dataset.readingKey,open);el.classList.toggle('expanded',open);button.setAttribute('aria-expanded',String(open));button.textContent=open?'접기 ∧':el.classList.contains('frp-fact-summary')?'이어서 보기 ∨':'더보기';agReadableMount(el.parentNode);
});
function agBRData(c,sc) {
  const pid=c.persona_id,L=AG.flow&&AG.flow.ledger,receipt=L&&L.receipts[pid],plan=AG.flow&&AG.flow.result.plans[pid];
  const index=plan&&sc?plan.scenes.findIndex(s=>(s.visit_day||1)===(sc.visit_day||AG.visitDay||1)&&s.t0===sc.t0&&s.t1===sc.t1&&(s.act===sc.act||sc.k==='turn'&&s.turn===AG.res.turn)):-1;
  const rows=receipt&&sc?(receipt.rows||[]).filter(r=>(r.visit_day||1)===(sc.visit_day||AG.visitDay||1)&&r.act!=='room_night'&&(r.scene_index===index||r.act===sc.act&&r.time===agHM(sc.t0))):[];
  const decision=sc&&sc.k!=='turn'?agU06Packet(pid,sc):null,row=decision&&decision.packet.candidates.find(x=>x.candidate_id===decision.selected_action);
  const factIds=sc&&sc.k==='turn'?[...new Set((c.reasons||[]).filter(t=>Math.abs((t.parts||{}).review||0)>1e-8).flatMap(t=>t.fact_ids||[]))]:[...new Set([...(row?(row.terms||[]).filter(t=>Math.abs(t.value||0)>1e-8).flatMap(t=>t.fact_ids||[]):[]),...((sc&&sc.basis&&sc.basis.facts)||[]),...((sc&&sc.fids)||[])])];
  return {pid,L,receipt,index,rows,decision,row,factIds};
}
// Arrival is a scene asset, not a HOTEL_GATE place thumbnail. Share its lookup.
function agArrivalImage() {
  if(typeof placeImg!=='function')return null;
  const stored=window.PLACE_THUMBS?.arrival?.();
  return placeImg('ARRIVAL')||(stored?{src:'/static/place_img/'+encodeURIComponent(stored.file),name:stored.name||'호텔 도착',credit:stored.credit,loc:'HOTEL_GATE'}:null);
}
function agDepartureImage() {
  const stored = window.PLACE_THUMBS?.end?.();
  return (typeof placeImg === 'function' && placeImg('ROUTE_END')) || (stored ? {src:'/static/place_img/'+encodeURIComponent(stored.file),name:stored.name||'일정 종료 · 귀가',credit:stored.credit,loc:'HOTEL_GATE'} : null);
}
function agBRImage(sc,pid) {
  if(!sc||typeof placeImg!=='function')return null;
  const V=agVC(pid),key=sc.act==='leave'?'ROUTE_END':sc.act==='arrive'||sc.loc==='HOTEL_GATE'?'ARRIVAL':sc.act==='checkin'&&V.B?V.B+'_FRONT_DESK':sc.loc;
  const image=(key==='ROUTE_END'?agDepartureImage():key==='ARRIVAL'?agArrivalImage():placeImg(key))||(sc.act==='checkin'&&V.B?placeImg(V.B+'_LOBBY'):null)||agSceneImg(sc,pid);
  return image?{...image,key:image===null?sc.loc:key}:null;
}
function agBRFactTag(text,f) {
  if(/수영|사우나|족욕|피트니스|산책|웰니스|휴식/.test(text))return '휴식·웰니스';
  if(/피자|뷔페|식사|음식|조식|메뉴|파스타|와인/.test(text))return /좋아|선호|취향|맛/.test(text)?'식사 취향':'구매·소비';
  if(/객실|숙소|전망|라운지/.test(text))return '객실·숙박';
  if(/동행|가족|부모|친구|배우자/.test(text))return '동행';
  return ['purchase','participation'].includes(f.kind)?'구매·소비':'경험·선택';
}
function agBRFacts(pid,c,sc,all=false) {
  const lp=agLibP(pid)||{},F=lp.engine&&lp.engine.facts||{},D=c&&sc?agBRData(c,sc):{factIds:[]},seen=new Set();
  const saved=c&&sc&&AG.flow&&typeof hlReasonView==='function'?hlReasonView(AG.flow,pid,D.index):null;
  const convert=id=>{const f=F[id]||{},record=saved&&saved.personal_evidence&&saved.personal_evidence[id]?saved.personal_evidence[id].gist:c&&c.evidence&&typeof c.evidence[id]==='string'?c.evidence[id]:null,text=record||f.gist;if(!text||f.hidden||seen.has(text)||(typeof LIB_SENS!=='undefined'&&LIB_SENS.test(text)))return null;seen.add(text);return {id,...f,text,direct:D.factIds.includes(id),scope:lp.group==='dev'&&!f.post?'후기 요약 · 원문 미연결':f.wh===true?'워커힐 후기':f.wh===false?'다른 경험':'출처 범위 미확인'};};
  if(c&&sc&&AG.flow){D.factIds=agBRExplain(AG.flow,pid,D.index).fact_ids;}
  const selected=D.factIds.map(convert).filter(Boolean);
  const fallback=Object.keys(F).sort((a,b)=>Number(!!F[b].wh)-Number(!!F[a].wh)).map(convert).filter(Boolean);
  return all?[...selected,...fallback]:selected.length?selected.slice(0,2):fallback.slice(0,2);
}
function agBRFactCards(pid,facts,si) {
  return `<ul class="frp-fact-cards">${facts.map(f=>{
    const url=typeof libUrl==='function'&&f.post?libUrl(f.post):null;
    // Gists are extracted summaries, not verbatim customer quotations.
    const quote=typeof f.source_quote==='string'?f.source_quote:null,text=quote||f.text;
    return `<li class="frp-fact-card" data-frp-fact-search="${esc(f.id+' '+f.text)}" data-fact-direct="${!!f.direct}"><div class="frp-fact-tags"><span>${esc(agBRFactTag(f.text,f))} · ${f.direct?'선택 기록에 인용된 근거 · 인과 기여 미검증':'개인 성향의 참고 경험'}</span></div><small class="frp-quote-kind">${quote?'원문 발췌':'후기에서 추출한 요약'} · ${esc(f.scope)}</small>${agReadableHTML(text,agReadingKey(pid,{si,visit_date:AG.visitDay},'fact:'+f.id),4,'frp-fact-summary') .replace('더보기','이어서 보기 ∨')}<div class="frp-fact-links">${url?libA(url,'원문 보기 ↗'):''}<button type="button" class="cf-link" data-frp-fact="${esc(f.id)}" data-frp-person="${esc(pid)}" data-frp-scene="${si==null?'':si}">연결된 Fact ›</button></div></li>`;
  }).join('')}</ul>`;
}
function agBREvidence(c,sc) {
  const facts=agBRFacts(c.persona_id,c,sc),direct=facts.some(f=>f.direct);
  return `<section class="frp-section frp-evidence" data-frp-section="evidence"><h3>후기 근거</h3>${facts.length?(direct?agBRFactCards(c.persona_id,facts,sc.si):`<p class="frp-note">이 행동에 직접 연결된 후기 기여는 확인되지 않았습니다.</p><details class="frp-context-facts"><summary>고객의 과거 후기 ${facts.length}건</summary>${agBRFactCards(c.persona_id,facts,sc.si)}</details>`):'<p class="frp-note">표시할 수 있는 후기 사실이 없습니다.</p>'}</section>`;
}
function agBRCompanion(pid) {
  const V=agVC(pid),cp=agComp(pid,V.party),lp=agLibP(pid)||{},meta=(AG.meta.personas||[]).find(p=>p.id===pid),nights=AG.flow&&AG.flow.result.visit&&AG.flow.result.visit.nights;
  const duration=nights!=null?(nights?`${nights}박 ${nights+1}일`:'당일 방문'):V.nights?`${V.nights}박 방문`:V.stay?'숙박 방문':'당일 방문';
  return `<section class="frp-section frp-companion" data-frp-section="companion"><div class="frp-section-heading"><h3>동행 구성</h3><button class="rp-link" data-frp-customer="${esc(pid)}">고객 상세 →</button></div><div class="frp-person-row">${agAvatarIcon(pid,V.party,40)}<div><b>${esc(dno(pid))}</b><span>${esc(cp.label||V.party+'명')}</span></div></div>${lp.label?`<p class="frp-person-intro">${esc(lp.label)}</p>`:''}<div class="frp-chips"><span>${V.party}명</span><span>${esc(duration)}</span>${V.stay&&V.bl?`<span>${esc(V.bl)}</span>`:''}${meta?meta.bars.filter(b=>b.status==='observed').slice(0,2).map(b=>`<span>${esc(b.label)}</span>`).join(''):''}</div><p class="frp-avatar-note">동행 인원과 특징을 요약한 시각 표현입니다.</p></section>`;
}
// Read-only presentation of a recorded decision. Identity is also the future reason-record handoff.
// BE01 records have not been supplied/accepted: do not backfill them onto M4 runs.
function agBRReasonIdentity(flow,pid,index) {
  const data=flow.result||flow,L=flow.ledger||data.ledger;
  if(!L||!L.run_id||typeof bhContextFor!=='function')return null;
  const ref=bhContextFor({flow:{result:data,ledger:L}},pid,index);if(!ref)return null;
  const raw=data.plans[pid].scenes[index],ids=raw.basis&&raw.basis.m4&&raw.basis.m4.decision_packet_ids||[],d=data.plans[pid].m4&&(data.plans[pid].m4.decisions||[]).find(d=>d.execution_status==='EXECUTED'&&ids.includes(d.packet.packet_sha256));
  const event=d&&d.actual_next_event_id||ref.action_id;
  return {...ref,event_id:event||null,key:JSON.stringify([ref.run_id,pid,ref.visit_id,ref.visit_day,ref.decision_id||event||index])};
}
function agBRExplain(flow,pid,index) {
  const agentPlan=(flow?.result||flow)?.plans?.[pid];
  const agent=window.HLAgentDecisionView?.view(HLAgentDecisionView.resolve(agentPlan?.scenes[index],agentPlan));
  if(agent)return {identity:agBRReasonIdentity(flow,pid,index),sentences:[agent.summary],fact_ids:agent.fact_ids,
    source_engine:agent.decision.policy,uses:[{kind:'RECORDED_PRECHOICE_LLM_PLAN',path:`plans[${JSON.stringify(pid)}].scenes[${index}].basis.autonomous_decision`}],external_reason_record_status:'NOT_APPLIED'};
  if((flow?.result||flow)?.plans?.[pid]?.trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_'))return {identity:agBRReasonIdentity(flow,pid,index),sentences:['이 장면은 별도의 LLM 판단 기록이 없습니다. 실행 절차와 자율 선택을 구분합니다.'],fact_ids:[],uses:[]};
  const saved=typeof hlReasonView==='function'&&hlReasonView(flow,pid,index);if(saved)return saved;
  const data=flow&&flow.result||flow,L=flow&&flow.ledger||data&&data.ledger,plan=data&&data.plans&&data.plans[pid],raw=plan&&plan.scenes[index];
  if(!raw||!L||!L.run_id)return {sentences:['연결된 실행의 판단 기록을 확인하지 못했습니다.'],fact_ids:[],uses:[],identity:null};
  const identity=agBRReasonIdentity(flow,pid,index),prefix=flow.result?'$.result':'$',base=prefix+'.plans['+JSON.stringify(pid)+']',uses=[];
  const result=(sentences,facts=[])=>({identity,source_engine:data.engine&&data.engine.behavior_engine||'unrecorded',sentences,fact_ids:[...new Set(facts)],uses,external_reason_record_status:'NOT_PROVIDED_NOT_APPLIED'});
  const procedure={arrive:'방문 시작 시각에 맞춰 호텔에 도착하는 공통 진행 절차입니다.',checkin:'선택한 숙박 조건에 따라 객실 이용을 시작하는 공통 절차입니다.',checkout:'숙박 종료일에 맞춰 객실 이용을 마치는 공통 절차입니다.',leave:'이번 방문의 종료 조건에 따른 귀가 절차입니다.',unpack:'선택한 객실에 도착한 뒤 짐을 정리하는 방문 진행 장면입니다.'};
  if(procedure[raw.act]){uses.push({path:base+'.scenes['+index+']',kind:'PROCEDURE',fields:['act','day_phase','visit_day']});return result([procedure[raw.act]]);}
  const ids=raw.basis&&raw.basis.m4&&raw.basis.m4.decision_packet_ids||[],di=plan.m4?(plan.m4.decisions||[]).findIndex(d=>d.execution_status==='EXECUTED'&&ids.includes(d.packet.packet_sha256)):-1,d=di>=0?plan.m4.decisions[di]:null,p=d&&d.packet,ci=p?p.candidates.findIndex(c=>c.candidate_id===d.selected_action):-1,row=ci>=0?p.candidates[ci]:null;
  const dp=base+'.m4.decisions['+di+']',cp=dp+'.packet.candidates['+ci+']';
  const ri=(data.runs||[]).findIndex(r=>(r.visit_day||1)===(raw.visit_day||1)&&r.turn===raw.turn),run=ri>=0?data.runs[ri]:null,customerIndex=run?run.customers.findIndex(c=>c.persona_id===pid):-1,c=customerIndex>=0?run.customers[customerIndex]:null;
  const turn=/^turn_/.test(raw.act||''),terms=turn&&c?(c.reasons||[]):row&&row.terms||[],tp=turn&&c?prefix+'.runs['+ri+'].customers['+customerIndex+'].reasons':cp+'.terms';
  const labels={space:'공간과 전망을 즐기려는 성향',rest_need:'휴식과 회복을 중시하는 성향',warm_rest:'온수·족욕으로 쉬려는 성향',food:'음식 경험을 중시하는 성향',food_specific:'후기에서 확인한 메뉴 기호',value_check:'가격 대비 내용을 비교하는 성향',routine:'경험한 곳을 다시 고려하는 성향',active:'운동을 즐기려는 성향',alcohol_familiar:'술과 음료에 익숙한 성향',alcohol_limit:'음주를 절제하는 성향',breakfast_priority:'조식을 중시하는 성향',benefit:'혜택을 활용하는 성향',practical_alt:'대안을 비교하는 성향'};
  const personal=terms.map((t,i)=>({t,i,value:turn?Number((t.parts||{}).review||0):/profile/.test(t.kind||'')?Number(t.value||0):0})).filter(x=>Math.abs(x.value)>1e-8&&labels[x.t.facet]);
  const negative=turn&&c.reason_totals&&c.reason_totals.review< -1e-8;
  const selected=personal.filter(x=>negative?x.value<0:x.value>0).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value)).filter((x,i,a)=>a.findIndex(y=>y.t.facet===x.t.facet)===i).slice(0,2);
  const recordTerm=(t,i)=>uses.push({path:tp+'['+i+']',kind:turn?(t.parts&&Math.abs(t.parts.review||0)>1e-8?'REVIEW_TERM':'COMMON_TERM'):t.kind||'TRACE_TERM',value:turn?t.parts:t.value,fact_ids:t.fact_ids||[]});
  const facts=terms.filter(t=>Math.abs(turn?(t.parts||{}).review||0:t.value||0)>1e-8).flatMap(t=>t.fact_ids||[]);
  const mealIndex=terms.findIndex(t=>/저녁 식사 해결/.test(t.factor||'')&&(turn?(t.parts||{}).common:t.value)>0),time=mealIndex>=0?'방문 계산상 저녁 식사를 채우는 시점에, ':'';
  if(mealIndex>=0)recordTerm(terms[mealIndex],mealIndex);
  if(selected.length){
    selected.forEach(x=>recordTerm(x.t,x.i));
    const consonant=text=>(text.charCodeAt(text.length-1)-44032)%28!==0, noun=selected.map(x=>labels[x.t.facet]).reduce((a,b)=>a?a+(consonant(a)?'과 ':'와 ')+b:b,''),sentences=[negative?`${time}이 고객의 ${noun}${consonant(noun)?'은':'는'} 이 선택에 불리하게 반영됐습니다.`:`${time}이 고객의 ${noun}${consonant(noun)?'이':'가'} 이번 선택을 뒷받침했습니다.`];
    const priceIndex=terms.findIndex(t=>/1인 지불액|가격 부담/.test(t.factor||'')&&(turn?(t.parts||{}).common:t.value)<0),alt=turn&&c.best_other_venue,lookahead=terms.findIndex(t=>/^이어지는 다음 일정/.test(t.factor||'')&&t.value>0);
    if(priceIndex>=0){recordTerm(terms[priceIndex],priceIndex);sentences.push(`가격은 부담 요인으로 반영됐고${alt?' '+(alt.venue_label||alt.product_label)+'도 대안으로 함께 검토됐습니다.':' 다른 조건과 함께 비교됐습니다.'}`);if(alt)uses.push({path:prefix+'.runs['+ri+'].customers['+customerIndex+'].best_other_venue',kind:'RECORDED_ALTERNATIVE'});}
    else if(row&&row.next){uses.push({path:cp+'.next',kind:'LOOKAHEAD_NOT_OBSERVED_FUTURE'});sentences.push(`내다보기에서는 ${row.next.time||''} ${row.next.label}도 함께 고려했습니다.`);}
    else if(lookahead>=0){recordTerm(terms[lookahead],lookahead);sentences.push('이후 일정까지 함께 고려한 기록이며, 이 성향만으로 선택이 결정된 것은 아닙니다.');}
    else if(d&&d.sampling)sentences.push('다른 허용 활동도 함께 비교한 결과이며, 이 요인만으로 선택을 단정하지 않습니다.');
    return result(sentences,facts);
  }
  // A neutral-feature comparison is not an additive causal contribution or a new observed Fact.
  const marginal=row&&Object.entries(row.profile_feature_marginals||{}).filter(([key,m])=>labels[key.split('.').pop()]&&m.value!==0&&Math.abs(m.weight_delta_at_fixed_state||0)>1e-8).sort((a,b)=>Math.abs(b[1].weight_delta_at_fixed_state)-Math.abs(a[1].weight_delta_at_fixed_state))[0];
  if(marginal){const [key,m]=marginal;uses.push({path:cp+'.profile_feature_marginals['+JSON.stringify(key)+']',kind:'FIXED_STATE_SINGLE_FEATURE_COMPARISON_NOT_ADDITIVE_CAUSE',value:m});const only=d.sampling&&d.sampling.candidate_order.length===1;if(only)uses.push({path:dp+'.sampling.candidate_order',kind:'AVAILABLE_CANDIDATES'});return result([`${agHM(p.context_factors.time)}의 상태를 고정한 비교에서, ${labels[key.split('.').pop()]} 항목을 중립값으로 바꾸면 이 활동의 가중치가 ${m.weight_delta_at_fixed_state>0?'낮아졌습니다':'높아졌습니다'}.`,only?'이 시점에 실행 가능한 후보는 이 활동 하나였습니다.':'이 값은 성향별 비교 기록이며, 단독 선택 원인이나 합산 가능한 기여도가 아닙니다.']);}
  if(row&&(row.context_factors||[]).some(f=>f.factor==='MEAL_GAP_PORTION_PROXY')){uses.push({path:cp+'.context_factors',kind:'SIMULATED_MEAL_STATE_NOT_OBSERVED_HUNGER'});return result(['이전 식사 뒤 남은 식사량을 추정한 방문 상태가 이 활동의 식사 분량과 비교됐습니다.','이 상태는 실제 배고픔의 관측값이 아닌 모의 추정입니다.']);}
  if(row){uses.push({path:cp,kind:'AVAILABLE_CANDIDATE_WITHOUT_PERSONAL_ATTRIBUTION'});return result(['현재 시각과 이용 조건을 통과한 활동이지만, 개인 성향이 선택에 영향을 준 항목은 저장 기록에서 확인되지 않습니다.']);}
  uses.push({path:base+'.scenes['+index+'].why',kind:'RECORDED_SCENE_EXPLANATION'});return result([raw.why||'이 장면의 개별 선택 이유는 저장 기록에서 확인되지 않습니다.']);
}
function agBRWhy(c,sc,D) {
  const explanation=agBRExplain(AG.flow,c.persona_id,D.index);
  return `<section class="frp-section frp-why" data-frp-section="why" data-reason-key="${esc(explanation.identity&&explanation.identity.key||'')}"><div class="frp-section-heading"><h3>왜 이 행동인가</h3><button class="rp-link" data-ux-scene="${sc.si}" data-ux-person="${esc(c.persona_id)}">행동근거 보기 →</button></div>${explanation.raw_record?`<div class="frp-chips"><span>${esc(explanation.run_label||'연구 저장 실행')}</span><span>${esc(explanation.method_label)}</span>${(explanation.tags||[]).map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}${agReadableHTML(explanation.sentences.join(' '),agReadingKey(c.persona_id,sc,'reason'),3,'frp-state-reason')}</section>`;
}
function agBRCard(c,sc) {
  if(!sc)return agTurnCard(c,false);
  const pid=c.persona_id,R=AG.runs[sc.ti]||AG.res,D=agBRData(c,sc),V=agVC(pid),im=agBRImage(sc,pid),meal=sc.k==='turn'&&['breakfast','lunch','dinner'].includes(R.turn)&&!['NONE','ROOM'].includes(c.choice.venue_id);
  const title=meal?`${AG_TURN[R.turn]} 식사`:agScLabel(sc,pid),place=agPlaceName(sc.loc,R),name=sc.k==='turn'?agU06Name(R,c.choice):null;
  const product=name&&(agMenuTitle(R,c.choice)||name.menu),showProduct=product&&!/^(아침|점심|저녁|식사|조식)$/.test(product)&&!title.includes(product),description=showProduct?product:typeof hlReasonView==='function'&&hlReasonView(AG.flow,pid,D.index)?'':sc.why||sc.name||'';
  const day=sc.visit_day||AG.visitDay||1,scenes=agScenes(pid),index=scenes.findIndex(s=>s.si===sc.si),next=scenes.slice(index+1).filter(s=>s.k!=='move'&&(s.visit_day||AG.visitDay||1)===day&&s.t0>=sc.t1).slice(0,2);
  const schedule=`<section class="frp-section frp-schedule" data-frp-section="schedule"><h3>다음 일정</h3>${next.length?`<ol>${next.map(s=>`<li data-frp-go="${s.si}" data-frp-person="${esc(pid)}" tabindex="0"><time>${agHM(s.t0)}</time>${agReadableHTML(agScLabel(s,pid),agReadingKey(pid,s,'next-label'),2)}</li>`).join('')}</ol>`:'<p class="frp-note">오늘의 일정이 끝났습니다.</p>'}<button class="rp-link" data-frp-customer="${esc(pid)}" data-frp-customer-tab="day">전체 일정 보기 →</button></section>`;
  return `<section class="frp-brief u06-choice" data-frp-person="${esc(pid)}"><section class="frp-section frp-current" data-frp-section="current"><div class="frp-current-meta"><span>${esc(dno(pid))} · ${day}일차</span><time>${agHM(sc.t0)}–${agHM(sc.t1)}</time></div>${im?`<div class="frp-current-media"><img class="frp-current-thumb" src="${im.src}" alt="${esc(im.name)}" width="1600" height="900"></div>`:''}<h2>${esc(title)}</h2><span class="frp-place">${esc(place)}</span>${typeof revSceneConsumptionHTML==='function'?revSceneConsumptionHTML(AG.flow,pid,sc):''}${description?`${agReadableHTML(description,agReadingKey(pid,sc,'product'),2,'frp-current-description')}`:''}</section>${schedule}${agBRWhy(c,sc,D)}<div class="frp-receipt-slot" data-frp-receipt-slot></div></section>`;
}
document.addEventListener('click',event=>{
  const tab=event.target.closest('[data-frp-detail-tab]');if(tab){const root=tab.closest('.frp-spend'),key=root.dataset.frpDetailKey;AG._frpDetailTab=AG._frpDetailTab||{};AG._frpDetailTab[key]=tab.dataset.frpDetailTab;root.querySelectorAll('[data-frp-detail-tab]').forEach(b=>b.setAttribute('aria-selected',String(b===tab)));root.querySelectorAll('[data-frp-detail-pane]').forEach(p=>p.hidden=p.dataset.frpDetailPane!==tab.dataset.frpDetailTab);return;}
  const customer=event.target.closest('[data-frp-customer]');if(customer){agCustDrawer(customer.dataset.frpCustomer,customer.dataset.frpCustomerTab||'ov');return;}
  const go=event.target.closest('[data-frp-go]');if(go){const scene=agScenes(go.dataset.frpPerson).find(s=>s.si===+go.dataset.frpGo);if(scene){if(AG.mode==='agents')agManyJump(scene.t0);else{agPause();agSetScene(scene.si);}}return;}
  const button=event.target.closest('[data-frp-fact]');if(!button)return;
  const pid=button.dataset.frpPerson,si=button.dataset.frpScene,fid=button.dataset.frpFact;
  if(si!==''&&typeof bhFromScene==='function'&&bhFromScene(pid,+si)){libOpen(pid,[fid],bhContextURL(BH.context));}
  else if(typeof libOpen==='function')libOpen(pid,[fid]);
});

function agU06PanelChrome() {
  const panel=document.querySelector('#panel');if(!panel)return;
  agReadableMount(panel);
  const slot=panel.querySelector('[data-frp-receipt-slot]'),receipt=panel.querySelector('#rcReceipt');if(slot&&receipt&&receipt.parentNode!==slot)slot.appendChild(receipt);
  if(!panel.querySelector('.u06-panel-tools'))panel.insertAdjacentHTML('afterbegin','<div class="u06-panel-tools"><b>선택·소비 상세</b><button type="button" data-u06-panel-close aria-label="상세 패널 닫기">닫기 ×</button></div>');
  if(!document.querySelector('#u06PanelOpen'))document.body.insertAdjacentHTML('beforeend','<button type="button" id="u06PanelOpen" aria-controls="right">선택·소비 보기</button>');
  const close=panel.querySelector('[data-u06-panel-close]'), open=document.querySelector('#u06PanelOpen');
  close.onclick=()=>{document.body.classList.add('u06-panel-collapsed');open.focus();};
  open.onclick=()=>{document.body.classList.remove('u06-panel-collapsed');close.focus();};
  open.setAttribute('aria-expanded',String(!document.body.classList.contains('u06-panel-collapsed')));
}
function agU06ActionName(id) {
  return ({POOL:'실내 수영장',PIZZA_HILL:'피자힐',MYONGWOLGWAN:'명월관',ONDAL:'온달',GEUMRYONG:'금룡',THE_BUFFET:'더뷔페',ROOM_MEAL:'룸서비스',ROOM:'객실에서 쉬기',SAUNA:'웰니스 사우나',SKYARD:'스카이야드 족욕',SKYARD_NIGHT:'스카이야드 야경 족욕',WINE_FAIR:'와인페어',FOREST:'와인페어'})[id] || AG_ACT_SHORT[id] || '다른 활동';
}
function agU06BlockLabel(text) {
  return String(text||'이용 조건 미충족').replace(/RESEARCH_ACTUAL_ARRIVAL_EXCEEDS_EXISTING_TIME_LIMIT/g,'도착·이용 시간 제한').replace(/\b[A-Z][A-Z_]{5,}\b/g,'상세 이용 조건').replace(/\s*·\s*상세 이용 조건/g,'');
}
function agU06Packet(pid, sc) {
  const data=typeof agM4LiveData==='function' && agM4LiveData(), plan=data && data.plans[pid];
  const ids=sc.basis && sc.basis.m4 && sc.basis.m4.decision_packet_ids || [];
  return plan && plan.m4 && plan.m4.decisions.find(d=>d.execution_status==='EXECUTED' && ids.includes(d.packet.packet_sha256));
}
function agU06ActivityCard(c,sc) {
  const d=agU06Packet(c.persona_id,sc), p=d && d.packet, row=p && p.candidates.find(x=>x.candidate_id===d.selected_action);
  if (!row) return agSceneCard(c,sc);
  const im=agSceneImg(sc,c.persona_id), terms=(row.terms||[]).filter(t=>Math.abs(t.value||0)>1e-6).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
  const review=terms.filter(t=>(t.fact_ids||[]).length), state=terms.filter(t=>!(t.fact_ids||[]).length), sampling=d.sampling;
  const score=x=>x.final_with_lookahead ?? x.final_score;
  const alt=p.candidates.filter(x=>x.candidate_id!==d.selected_action && x.world_allowed && score(x)!=null).sort((a,b)=>score(b)-score(a))[0];
  const raw=(AG.flow.ledger.receipts[c.persona_id].rows||[]).filter(r=>(r.visit_day||1)===(sc.visit_day||AG.visitDay||1) && (r.act===sc.act || r.action_id===sc.act) && r.time===agHM(sc.t0));
  const blocked=p.candidates.filter(x=>!x.world_allowed);
  const blockedHTML=blocked.length?`<details><summary>이용할 수 없었던 후보 ${blocked.length}개</summary><ul class="ag-plain">${blocked.map(x=>`<li>${esc(agU06ActionName(x.candidate_id))} · ${esc(agU06BlockLabel(x.block_reason))}</li>`).join('')}</ul></details>`:'';
  const status=raw.some(r=>r.status==='금액 미확인')?'금액 미확인':raw.some(r=>r.purchase_status==='PACKAGE_INCLUDED'||r.status==='포함')?'포함 혜택':raw.some(r=>r.purchase_status==='FREE_USE'||r.status==='무료')?'무료 이용':raw.length?rcMoney(raw.reduce((n,r)=>n+(r.paid_krw||0),0)):'거래 원장 미연결';
  const reason=(title,badge,ts)=>ts.length?`<div class="u06-reason"><div><b>${title}</b><small>${badge}</small></div><p>${ts.slice(0,2).map(t=>`${esc(t.factor)} <strong>${agU06Signed(t.value)}</strong>`).join(' · ')}</p></div>`:'';
  return `<section class="rp u06-choice u06-activity"><div class="rp-eye"><span>${esc(dno(c.persona_id))} · ${agHM(sc.t0)}–${agHM(sc.t1)} · 활동</span></div><div class="u06-hero">${im?`<button type="button" id="agImg" title="${esc(im.name)} 크게 보기"><img src="${im.src}" alt="${esc(im.name)}"></button>`:''}<div><h2>${esc(sc.label)}</h2><span>${esc(agPlaceName(sc.loc,AG.res))}</span></div></div><div class="u06-reasons">${reason('후기와 연결된 요인',review.some(t=>/profile_and/.test(t.kind||''))?'후기·이용 조건 혼합항':'후기 기반 추론',review)}${reason('현재 방문 요인',state.some(t=>/profile_and/.test(t.kind||''))?'프로파일·현재 조건 혼합항':'환경·공통 규칙',state)}${!review.length&&!state.length?`<div class="u06-reason"><div><b>기록된 선택 방식</b><small>현재 방문 조건</small></div><p>${sampling?'허용된 활동 중 가중치 추첨으로 선택했습니다.':'기록된 후보 점수로 비교했습니다.'} 항목별 기여는 정밀 기록에서 확인합니다.</p></div>`:''}</div><details class="u06-contributions-fold"><summary>선택 방식·비교 점수</summary><p class="u06-margin">${sampling?'후보 가중치 추첨으로 선택 · 최고 점수 선택과 다름':'후속 활동 포함 점수로 비교'}</p><div class="u06-comparison"><div class="u06-score-row chosen"><small>실제 선택</small><span>${esc(agU06ActionName(d.selected_action))}</span><strong>${agNum(score(row))}</strong></div>${alt?`<div class="u06-score-row alternative"><small>비교 대안</small><span>${esc(agU06ActionName(alt.candidate_id))}</span><strong>${agNum(score(alt))}</strong></div><p class="u06-margin">점수 차 ${agU06Signed(score(row)-score(alt))} · 점수는 결제액·선택 확률이 아닙니다</p>`:''}</div></details><div class="u06-payment u06-activity-payment"><div><small>이번 활동의 이용 구분</small><strong>${status}</strong></div></div>${agUXNext(c.persona_id,sc)}<div class="ux-action-links"><button type="button" class="rp-link" data-ux-scene="${sc.si}" data-ux-person="${esc(c.persona_id)}">자세한 판단 근거 →</button><button type="button" class="rp-link" data-pf="${esc(c.persona_id)}">고객 프로필</button></div></section>`;
}
function agU06ReceiptHTML(L,pid,comparison) {
  const r=L.receipts[pid]; if(!r)return '';
  const rows=r.rows||[], groups=new Map(), free=rows.filter(x=>x.purchase_status==='FREE_USE'||x.purchase_status==='PACKAGE_INCLUDED'||['무료','포함'].includes(x.status));
  for(const x of rows.filter(x=>x.paid_krw>0)) {
    const dept=x.department||'분류 미확인';if(!groups.has(dept))groups.set(dept,{amount:0,venues:new Map()});const g=groups.get(dept);g.amount+=x.paid_krw;
    const v=x.venue||'업장 미확인';if(!g.venues.has(v))g.venues.set(v,{amount:0,rows:[]});g.venues.get(v).amount+=x.paid_krw;g.venues.get(v).rows.push(x);
  }
  const color=k=>k==='ROOM'?'room':k==='F&B'?'fnb':k==='레저'?'leisure':'unknown';
  const key=`${L.run_id}|${pid}`, selectedDay=AG.visitDay||1, selectedTurn=AG.res && AG.res.turn, scene=AG.mode==='agent' && agScene();
  const focused=x=>(x.visit_day||1)===selectedDay && (scene && scene.k!=='turn'? x.time===agHM(scene.t0):x.turn===selectedTurn);
  const sorted=[...groups].sort((a,b)=>['ROOM','F&B','레저'].indexOf(a[0])-['ROOM','F&B','레저'].indexOf(b[0]));
  const departments=[...new Set(['ROOM','F&B','레저',...rows.map(x=>x.department||'분류 미확인')])].map(dept=>{
    const g=groups.get(dept),all=rows.filter(x=>(x.department||'분류 미확인')===dept),unknown=all.filter(x=>x.status==='금액 미확인').length;
    const label=g?rcMoney(g.amount):unknown?'금액 미확인':dept==='ROOM'&&L.visit&&L.visit.nights>0&&!all.length?'거래 미연결':'유료 거래 없음';
    return `<div class="frp-department-line ${color(dept)}"><span><i aria-hidden="true"></i>${esc(dept)}</span><b>${label}</b>${g&&unknown?`<small>미확인 ${unknown}건 별도</small>`:''}</div>`;
  }).join('');
  // Stay spend hierarchy (U06 V3 restore): total → L2 departments → L3 venues → free/included/unconfirmed → per-transaction drawer. Same ledger rows only.
  const venueList=[...groups].flatMap(([k,g])=>[...g.venues].map(([v,x])=>({dept:k,venue:v,...x}))).sort((a,b)=>b.amount-a.amount);
  const rowBtn=row=>`<button type="button" data-u06-row="${esc(row.row_id)}"><span>${esc(row.visit_date||'')} ${esc(row.time||'숙박')} · ${esc(row.product)}</span><b>${row.status==='금액 미확인'?'금액 미확인':row.paid_krw>0?rcMoney(row.paid_krw):row.purchase_status==='PACKAGE_INCLUDED'||row.status==='포함'?'포함 혜택':row.purchase_status==='FREE_USE'||row.status==='무료'?'무료 이용':'추가 결제 없음'}</b></button>`;
  const venues=`<div class="frp-venue-list" aria-label="업장별 소비">${venueList.length?venueList.map(x=>`<details class="u06-venue frp-venue-line ${color(x.dept)}${x.rows.some(focused)?' focused':''}"><summary><span><i aria-hidden="true"></i>${esc(rcVenueName(x.venue))}${x.rows.some(focused)?'<em>현재 장면</em>':''}</span><b>${rcMoney(x.amount)}</b></summary><div>${x.rows.map(rowBtn).join('')}</div></details>`).join(''):'<p class="rc-note">유료 거래가 없습니다.</p>'}</div>`;
  const included=free.filter(x=>x.purchase_status==='PACKAGE_INCLUDED'||x.status==='포함'),freeUse=free.filter(x=>!included.includes(x)),unknownRows=rows.filter(x=>x.status==='금액 미확인');
  const names=list=>[...new Set(list.map(x=>rcVenueName(x.venue)))].slice(0,3).join(' · ')+(new Set(list.map(x=>x.venue)).size>3?' 외':'');
  const benefitLine=(label,list,cls)=>list.length?`<div class="frp-benefit-line ${cls}"><span>${label} <b>${list.length}건</b></span><small>${esc(names(list))}</small></div>`:'';
  const benefits=free.length||unknownRows.length?`<div class="frp-benefits">${benefitLine('무료 이용',freeUse,'free')}${benefitLine('패키지 포함',included,'included')}${benefitLine('가격 미확인',unknownRows,'unknown')}<details class="frp-benefit-detail"><summary>무료·포함·미확인 상세</summary><div class="frp-free-list">${[...freeUse,...included,...unknownRows].map(rowBtn).join('')}</div></details>${unknownRows.length?'<p class="rc-note">가격 미확인은 무료나 0원 결제로 보지 않고 합계에서 제외합니다.</p>':''}</div>`:'';
  const ledger=`<div class="u06-ledger-rows">${rows.map(rowBtn).join('')}</div>`;
  const tabs=[['ledger','전체 원장',ledger],['compare','비교',rcComparisonHTML(pid,L,comparison)+rcABHTML(L,pid)]],active=AG._frpDetailTab&&AG._frpDetailTab[key]==='compare'?'compare':'ledger';
  // Flow panel shows a short spend summary; venues, benefits and the full ledger stay one
  // click away in the same card (same ledger rows), and 매출 집계 has the full view.
  return `<section class="rc-receipt u06-receipt frp-spend" data-frp-section="spend" data-frp-detail-key="${esc(key)}" data-rc-p="${esc(pid)}"><div class="frp-spend-heading"><h3>${L.visit?'체류 전체':'하루'} 가상 소비</h3><strong>${rcMoney(r.paid_krw)}</strong><small>${esc(r.display_id||dno(pid))} · 방문 ${r.party_size??'미확인'}명 · 실행 원장 기준 가상 소비</small></div><div class="frp-department-list">${departments}</div>${r.unknown_count?`<p class="rc-note">금액 미확인 ${r.unknown_count}건은 합계에서 제외</p>`:''}<details class="frp-spend-more"><summary>업장별 소비 · 무료·포함 · 전체 원장</summary><h4 class="frp-tier-title">업장별 소비</h4>${venues}${benefits?`<h4 class="frp-tier-title">무료·포함·미확인</h4>${benefits}`:''}<details class="frp-spend-detail" data-rc-open="${esc(key)}"${RC.open.has(key)?' open':''}><summary>전체 원장 · 조건 비교</summary><div class="frp-detail-tabs" role="tablist" aria-label="소비 상세">${tabs.map(([id,label])=>`<button type="button" role="tab" id="frp-tab-${esc(pid)}-${id}" aria-controls="frp-pane-${esc(pid)}-${id}" aria-selected="${active===id}" data-frp-detail-tab="${id}">${label}</button>`).join('')}</div>${tabs.map(([id,label,html])=>`<div role="tabpanel" id="frp-pane-${esc(pid)}-${id}" aria-labelledby="frp-tab-${esc(pid)}-${id}" data-frp-detail-pane="${id}"${active===id?'':' hidden'}>${html}</div>`).join('')}</details></details>${rcRevenueAction()}</section>`;
}
document.addEventListener('click',ev=>{
  const b=ev.target.closest('[data-u06-row]');if(!b)return;
  const L=AG.flow && AG.flow.ledger, r=L && Object.values(L.receipts).flatMap(r=>r.rows).find(r=>r.row_id===b.dataset.u06Row);if(!r)return;
  openDrawer(`${L.receipts[r.customer_id].display_id} · ${r.venue}`,'같은 실행의 가상 거래',rcTransactionHTML(L,r,AG.flow),root=>{
    root.querySelector('#u06RowAction').onclick=()=>{closeDrawer();if(typeof agVisitDaySelect==='function' && L.visit && (AG.visitDay||1)!==(r.visit_day||1))agVisitDaySelect(r.visit_day||1);if(r.act==='room_night')return agCustDrawer(r.customer_id);const sc=agScenes(r.customer_id).find(s=>s.k!=='move' && ((s.visit_day||1)===(r.visit_day||1)) && (s.act===r.act || s.k==='turn' && AG.runs[s.ti].turn===r.turn) && agHM(s.t0)===r.time);if(sc){if(AG.mode==='agents')agManyJump(sc.t0);else agSetScene(sc.si);if(AG.flow.result.engine.behavior_engine==='m4_c01'&&typeof bhFromScene==='function')bhFromScene(r.customer_id,sc.si,{ledger_tx_id:r.row_id});else agActDrawer(r.customer_id,sc.si);}};
  },{});
});
function agU06Signed(value) { return `${value>0?'+':value<0?'−':''}${Math.abs(value||0).toFixed(2)}`; }
function agU06Name(R,choice) {
  const rawVenue=agVenueTitle(R,choice,AG.one||AG.sel),venue=/^[A-Z_]+$/.test(rawVenue)?agU06ActionName(choice.venue_id):rawVenue, full=choice.product_label||'';
  let menu=agMenu(full).replace(new RegExp('^'+venue.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s*'),'').trim();
  if(/정찬/.test(menu))menu=`${R.turn==='dinner'?'저녁':R.turn==='lunch'?'점심':''} 정찬`.trim();
  else menu=menu.replace(/\([^)]*\)/g,'').trim();
  return {venue,menu,full};
}
function agU06Reasons(c) {
  const terms=c.reasons||[],totals=c.reason_totals||{},common=terms.filter(t=>Math.abs((t.parts||{}).common||0)>1e-6).sort((a,b)=>Math.abs(b.parts.common)-Math.abs(a.parts.common)).slice(0,2);
  const review=terms.filter(t=>Math.abs((t.parts||{}).review||0)>1e-6).sort((a,b)=>Math.abs(b.parts.review)-Math.abs(a.parts.review));
  const title=t=>t.factor.startsWith('이어지는 다음 일정')?'다음 일정 고려':t.factor.replace(/\s*\([^)]*\)/g,'');
  const row=(heading,badge,text)=>`<div class="u06-reason"><div><b>${heading}</b><small>${badge}</small></div><p>${text}</p></div>`;
  let html=row('현재 조건의 기여','공통 행동 규칙',common.length?common.map(t=>`${esc(title(t))} <strong>${agU06Signed(t.parts.common)}</strong>`).join(' · '):'선택 전 항목별 기여 기록 없음');
  html+=row('개인 후기 기여',review.some(t=>(t.fact_ids||[]).length)?'후기 근거 연결':'선택 전 점수 기록',review.length?`${esc(title(review[0]))} <strong>${agU06Signed(review[0].parts.review)}</strong>${totals.review<0?' · 선택 점수를 낮춤':Math.abs(totals.review||0)<1e-6?' · 양·음 기여 상쇄':''}`:'이번 선택에 반영된 후기 점수 항목 없음');
  const inference=terms.filter(t=>Math.abs((t.parts||{}).assumption||0)>1e-6||Math.abs((t.parts||{}).transfer||0)>1e-6).sort((a,b)=>Math.abs((b.parts.assumption||0)+(b.parts.transfer||0))-Math.abs((a.parts.assumption||0)+(a.parts.transfer||0)))[0];
  if(inference)html+=row('추론·모델 가정','프로파일 추론 / 설계 가정',`${esc(title(inference))} <strong>${agU06Signed((inference.parts.assumption||0)+(inference.parts.transfer||0))}</strong>`);
  return `<div class="u06-reasons">${html}</div>`;
}
function agU06Payment(R,c) {
  const ledger=AG.flow&&AG.flow.ledger,receipt=ledger&&ledger.receipts[c.persona_id],day=R.visit_day||AG.visitDay||1;
  const rows=receipt?(receipt.rows||[]).filter(r=>r.turn===R.turn&&(r.visit_day||1)===day):[];
  const known=rows.length&&rows.every(r=>r.status!=='금액 미확인'),amount=known?rows.reduce((n,r)=>n+r.paid_krw,0):null;
  const label=amount==null?'금액 미확인':amount>0?agWon(amount):rows.some(r=>r.purchase_status==='PACKAGE_INCLUDED'||r.status==='포함')?'포함 혜택':rows.every(r=>r.purchase_status==='FREE_USE'||r.status==='무료')?'무료 이용':'추가 결제 없음';
  const units=[...new Set(rows.map(r=>r.unit_price_krw).filter(x=>x!=null))];
  const unit=rows.length===1&&units.length===1?`${/인|person/i.test(rows[0].unit_basis||'')?'1인 기준':'거래 단가'} ${agWon(units[0])}`:rows.length?'품목별 단가는 상세 원장 기준':'가격 원장 미연결';
  return `<div class="u06-payment"><div><small>동행 구성에 따른 가상 결제액</small><strong>${label}</strong></div><span>${esc(unit)}</span></div>`;
}
function agU06Comparison(R,c) {
  const selected=agU06Name(R,c.choice),o=c.best_other_venue,alt=o&&agU06Name(R,o),score=o&&(Number.isFinite(o.score)?o.score:c.choice.score-o.margin),delta=o&&c.choice.score-score;
  return `<div class="u06-comparison"><div class="u06-score-row chosen"><small>선택</small><span>${esc(selected.venue)}</span><strong>${agNum(c.choice.score)}</strong></div>${o?`<div class="u06-score-row alternative"><small>가까운 대안</small><span>${esc(alt.venue)}${alt.menu?`<em> — ${esc(alt.menu)}</em>`:''}</span><strong>${agNum(score)}</strong></div><p class="u06-margin">점수 차 <b>${agU06Signed(delta)}</b>${Math.abs(delta)<.15?' · 근소한 차이, 강한 개인 선호로 단정하지 않음':''}</p>`:'<p class="u06-margin">비교 가능한 대안 기록 없음</p>'}</div>`;
}
function agTurnCard(c, compact) {
  const R=AG.res,T=c.reason_totals||{},name=agU06Name(R,c.choice),sy=agSentence(c);
  const im=!compact&&typeof placeImg==='function'?placeImg(c.choice.map_loc):null;
  return `<section class="rp u06-choice"><div class="rp-eye"><span>${esc(dno(c.persona_id))} · ${esc(R.time||'')} ${esc(AG_TURN[R.turn])}</span></div><div class="u06-hero">${im?`<button type="button" id="agImg" title="${esc(im.name)} 크게 보기"><img src="${im.src}" alt="${esc(im.name)}"></button>`:''}<div><small>이번 선택</small><h2>${esc(name.venue)}</h2><span>${esc(agMenuTitle(R,c.choice)||name.menu)}</span></div></div>${agU06Reasons(c)}<details class="u06-contributions-fold"><summary>선택·대안 점수</summary>${agU06Comparison(R,c)}</details><details class="u06-contributions-fold"><summary>개인·공통 점수 기여</summary><div class="u06-contributions"><div><small>개인 후기 기여</small><b>${agU06Signed(T.review||0)}</b></div><div><small>공통 규칙 기여</small><b>${agU06Signed(T.common||0)}</b></div></div></details>${agU06Payment(R,c)}${agUXNext(c.persona_id)}<div class="ux-action-links"><button type="button" class="rp-link" data-ux-reason="${esc(c.persona_id)}" data-ux-ti="${AG.ti}">자세한 판단 근거 →</button><button type="button" class="rp-link" data-pf="${esc(c.persona_id)}">고객 프로필</button></div></section>`;
}
// 오른쪽(한 명) — 오늘 흐름: 앞 장면 · 지금 · 다음 장면 · 다음 결정(시간 | 활동 | 장소) — 누르면 그 장면으로
function agDayFlow(pid, si) {
  const L = agScenes(pid).filter(x => x.k !== "move"); const i = L.findIndex(x => x.si === si); if (i < 0) return "";
  const from = Math.max(0, i - 2), to = Math.min(L.length, i + 4), rows = L.slice(from, to);
  return `<section class="rp2-flow"><h4>오늘 흐름</h4><ol>${rows.map(x => { const key = x.k === "turn", now = x.si === si;
    return `<li class="${now ? "now" : x.si < si ? "past" : ""}${key ? " key" : ""}" data-go="${x.si}" tabindex="0"><time>${agHM(x.t0)}</time><div><b>${esc(agScLabel(x, pid))}</b><span>${esc(agPlaceName(x.loc, AG.runs[x.ti]))}</span></div></li>`; }).join("")}</ol></section>`;
}
function agSceneCard(c, sc) {
  const R = AG.res, L = agScenes(c.persona_id), nx = L.slice((sc.si || 0) + 1).find(x => x.k === "turn"), nR = nx ? AG.runs[nx.ti] : null, nc = nR ? agCustOf(nR, c.persona_id) : null;
  const slotName = { am: "오전", noon: "점심 · 낮", pm: "오후", eve: "저녁 이후", gap: "턴 사이" };
  let eye, ic, title, sub, line, tag = "", help = null, tech = "", extra = "";
  if (sc.k === "start") { eye = `${agHM(sc.t0)} · 출발`; ic = "start"; title = sc.label; sub = sc.name; line = `${agVC(c.persona_id, R).stay ? `${agVC(c.persona_id, R).bl}에 투숙한 상태에서` : "정문으로 도착해"} 하루를 시작합니다.`; tag = `<span class="rp-tag in">시나리오 입력</span>`; help = { what: "하루의 출발 위치입니다. 투숙이면 고른 건물의 객실, 비투숙이면 정문입니다.", basis: ["운영 조건 · 계산"], caution: "출발 시각은 첫 결정 턴 앞에 둔 표시용 시각입니다." }; }
  else if (sc.k === "move") { const to = L[(sc.si || 0) + 1]; eye = `${agHM(sc.t0)}–${agHM(sc.t1)} · 이동`; ic = "move"; title = `${agPlaceName(sc.b, R)}(으)로 이동`; sub = `${agPlaceName(sc.a, R)}에서 출발`; line = `${to && to.k === "turn" ? `${AG_TURN[AG.runs[to.ti].turn]} 결정 장소로` : "다음 장소로"} 가는 중입니다.`; tag = `<span class="rp-tag mv">표시용 이동</span>`; help = { what: "지도 길을 따라 출발지와 도착지를 이은 선입니다.", basis: ["운영 조건 · 계산"], caution: "실제 이동 경로 · 이동 시간을 계산한 것이 아닙니다." }; }
  else if (sc.act) {   // 계획 계층의 장면 — 성향 · 동행 · 앞선 행동으로 구성(후기 경험이 있으면 표시)
    const rv = sc.src === "review", B = sc.basis || {};
    eye = `${agHM(sc.t0)}–${agHM(sc.t1)}${sc.meal === "lunch" ? " · 점심" : ""}`; ic = sc.icon || "walk"; title = sc.label; sub = sc.name || "";
    line = sc.why || "";
    tag = rv ? `<span class="rp-tag rv">후기 경험</span>` : sc.consume ? `<span class="rp-tag cs">이용 · 소비</span>` : `<span class="rp-tag as">프로파일 기반</span>`;
    const tl = (B.traits || []).map(k => AG_TRAIT_KO[k] || k).join(" · ");
    help = { what: rv ? "후기에 같은 경험이 남아 있어, 이 고객의 성향과 함께 이 시간대의 행동으로 구성했습니다." : "엔진 결정 사이의 시간을 이 고객의 성향 · 동행 · 앞선 활동으로 구성한 행동입니다.", basis: rv ? ["실제 후기", "추출 성향"] : ["추출 성향"], basis_note: tl ? `작용한 성향: ${tl}` : "", caution: sc.consume ? "이용 · 소비 장면이지만 가격 · 점수를 계산하지 않았습니다(운영자가 조건을 바꾸는 결정은 아침 · 행사 · 저녁 턴)." : "엔진이 계산한 선택이 아니며 실제 관측도 아닙니다." };
    if (sc.cond_dep) tag += `<span class="rp-tag chg">조건 영향</span>`;
    if (B.decision) tag += `<span class="rp-tag cs">정량 엔진 판단</span>`;
    extra = agPayLine(B.charge) + agAltLine(B.choice) + ((B.evidence || []).some(e => e.type !== "후기에서 확인") ? `<div class="rp-sev">${agEvHtml(c.persona_id, B.evidence)}</div>` : "");
    tech = (B.facts && B.facts.length) || tl ? `<details class="rp-more"><summary>상세 정보</summary><div class="rp-more-b">${tl ? `<div class="rp-row"><span>작용한 성향</span><span>${esc(tl)}</span></div>` : ""}${B.facts && B.facts.length ? `<div class="rp-row rp-row-col"><span>연결한 후기 사실</span><span class="rp-mut">${esc(B.facts.join(" · "))}</span></div>` : ""}<div class="rp-row"><span>생성 계층</span><span class="rp-mut">${rv ? "후기 경험 + 계획기" : "행동 계획기(" + (AG.plans && AG.plans[c.persona_id] ? AG.plans[c.persona_id].backend : "rules") + ")"}</span></div></div></details>` : "";
  }
  else {
    const rv = sc.src === "review";
    eye = `${agHM(sc.t0)}–${agHM(sc.t1)} · ${slotName[sc.slot] || "턴 사이"}`;
    ic = rv ? sc.k === "flow" && ({ pool: "pool", foot: "foot", forest: "forest", sauna: "sauna", garden: "garden" })[(AG_EVK.find(e => e.label === sc.label) || {}).k] || "walk" : sc.slot === "noon" ? "noon" : sc.slot === "eve" ? "home" : sc.loc === "AG_GARDEN" ? "walk" : /_ROOM$/.test(sc.loc || "") ? "rest" : "lobby";
    title = sc.label; sub = sc.name || "";
    line = rv ? `후기에서 이 고객이 ${sc.label} 경험을 남긴 기록이 있어, 이 시간대를 그 흐름으로 구성했습니다.${sc.hint ? "" : " 후기에 이용 시각이 없어 시간대는 추정입니다."}` : agFlowLine(c, R, sc, nR);
    tag = rv ? `<span class="rp-tag rv">후기 경험</span>` : `<span class="rp-tag as">추정 흐름</span>`;
    help = rv ? { what: "후기에 남은 워커힐 시설 이용 경험(이전 방문)을 이 시간대의 흐름 장소로 썼습니다.", basis: ["실제 후기", "추정 흐름"], basis_note: sc.hint ? "후기에 이용 시간대가 적혀 있음" : "이용 시각은 후기에 없어 시간대만 추정", caution: "이번 시뮬레이션에서 실제로 이용했다는 뜻이 아니며 엔진이 계산한 선택도 아닙니다. 요금 · 구매는 계산하지 않습니다." }
      : { what: "엔진 결정 턴 사이의 시간을 고객 성향(휴식 · 공간)과 투숙 여부로 이은 장면입니다.", basis: ["추출 성향", "추정 흐름"], basis_note: sc.why || "", caution: `엔진 계산이 아니며 실제 관측도 아닙니다.${sc.slot === "noon" ? " 점심 식사 여부 · 장소는 계산하지 않았습니다." : ""}` };
    if (rv && sc.fids) tech = `<details class="rp-more"><summary>상세 정보</summary><div class="rp-more-b"><div class="rp-row rp-row-col"><span>연결한 후기 사실</span><span class="rp-mut">${esc(sc.fids.join(" · "))}</span></div></div></details>`;
  }
  const scIm = sc.act ? agSceneImg(sc, c.persona_id) : null;   // CL-11 §5 — 시설 · 식음 장면은 장소 그림(있을 때만 · 빈 사진 상자 없음)
  return `<section class="rp rp-scene ag-gen">
    <div class="rp-eye"><span>${esc(eye)}</span>${tag}</div>
    ${scIm ? `<div class="rp-img rp-img-s"><img src="${scIm.src}" alt="${esc(scIm.name)}"><span class="rp-cred">${esc(scIm.credit)}</span></div>` : ""}
    <div class="rp-shead"><span class="rp-icw">${agScIcon(ic)}</span><div><h2 class="rp-title gn-act">${esc(title)}</h2>${sub ? `<div class="rp-sub gn-place">${esc(sub)}</div>` : ""}</div></div>
    <p class="rp-line">${esc(line)}</p>${extra}
    <div class="rp-basis">${help ? `<span>${sc.k === "flow" ? (sc.src === "review" ? "후기 경험 + 성향으로 구성" : "성향 · 동행 · 앞선 활동으로 구성") : sc.k === "move" ? "지도 길을 따라 이동" : "시나리오 입력"}</span>${noteH(help)}` : ""}</div>
    ${sc.act || sc.k === "start" ? `<div class="rp-links"><button type="button" class="rp-link" data-actd="${c.persona_id}|${sc.si}">활동 상세 ›</button><button type="button" class="rp-link" data-pf="${c.persona_id}">고객 상세 ›</button></div>` : ""}
    ${agDayFlow(c.persona_id, sc.si)}
    ${tech}
  </section>`;
}
// CL-1024-22R — 새 엔진 장면의 지출(공통 장부) · 다른 선택(검토 후보 · 이 시각 막힌 선택) · 운영 변경 반응(같은 실행 기록에서 만든 이야기)
function agPayLine(ch) {
  if (!ch || !["유료", "포함", "가격 미정", "무료"].includes(ch.status) || (ch.status === "무료" && !ch.fee_rule)) return "";
  if (ch.fee_rule) return `<div class="rp-pay">${ch.price_kind === "known_free" ? "입장료 0원 · 투숙객 무료 입장" : ch.price_kind === "known_paid" ? `입장료 ${agWon(ch.krw)} · 비투숙 성인 요금` : "입장료 미확인 · 퇴실 뒤 투숙객 무료 적용 여부 확인 필요"}<small>음식 · 유료 프로그램은 현장에서 따로 구매 — 가격 미정</small></div>`;
  return `<div class="rp-pay">지출 · ${esc(ch.status)}${ch.krw ? ` ${agWon(ch.krw)}${ch.party_estimate ? "(추정)" : ""}` : ""}${ch.basis && !/[A-Z]{3,}/.test(ch.basis) ? `<small>${esc(String(ch.basis).split(" · ")[0])}</small>` : ""}${ch.party_note ? `<small class="rp-est">${esc(ch.party_note)}</small>` : ""}</div>`;
}
// CL-1025-24 — 근거 수준 표시: 후기에서 확인(직접 이용) · 후기 회피 근거(다시 가지 않겠다는 직접 경험) · 불확실 · 프로파일 기반 추론(확장 이유 포함)
function agEvHtml(pid, evs) {
  const gist = f => { try { const lp = agLibP(pid), F = lp && lp.engine && lp.engine.facts[f]; return F && !F.hidden ? F.gist : ""; } catch (x) { return ""; } };
  return (evs || []).map(e => e.type === "후기에서 확인" ? `<em class="rp-ev r">후기에서 확인</em>${esc(((e.fact_ids || []).map(gist).filter(Boolean)[0]) || e.about || "")}`
    : e.type === "후기 회피 근거" ? `<em class="rp-ev a">후기 회피 근거</em>${esc(e.about || "")}${(e.fact_ids || []).map(gist).filter(Boolean)[0] ? ` — “${esc((e.fact_ids || []).map(gist).filter(Boolean)[0])}”` : ""}`
    : e.type === "불확실" ? `<em class="rp-ev u">불확실</em>${esc(e.about || "")}`
    : `<em class="rp-ev p">프로파일 기반 추론</em>${esc((e.traits || []).map(t => AG_TRAIT_KO[t] || t).join(" · ") || e.about || "")}${e.ext_reasons ? `<small class="rp-mut"> (${esc([...new Set(Object.values(e.ext_reasons))].join(" · "))})</small>` : ""}`).join("<br>");
}
function agAltLine(c) {
  if (!c || (!(c.considered || []).length && !(c.blocked || []).length)) return "";
  return `<details class="rp-alt2"><summary>다른 선택은?</summary>${(c.considered || []).length ? `<div><span>함께 본 후보</span>${c.considered.map(a => `${esc(a.label)} <i>${esc(a.note)}</i>`).join(" · ")}</div>` : ""}${(c.blocked || []).length ? `<div><span>이 시각 막힌 선택</span>${c.blocked.map(a => `${esc(a.label)} <i>${esc(a.note)}</i>`).join(" · ")}</div>` : ""}</details>`;
}
function agStory(pid) {
  const S = AG.engine === "autonomy" && AG.flow && AG.flow.stories && AG.flow.stories[pid]; if (!S) return "";
  const li = (k, b, cls) => `<li${cls ? ` class="${cls}"` : ""}><span>${k}</span><div>${b}</div></li>`;
  const ev = evs => agEvHtml(pid, evs);
  let body;
  if (S.keep_reason) body = li("새 조건", esc(S.notice.text)) + li("반응", esc(S.keep_reason));
  else { const ci = S.steps.findIndex(x => x.kind === "선택");
    body = (S.before.length ? li("원래 계획", S.before.map(b => `${esc(b.t)} ${esc(b.label)}`).join(" · ")) : "") + li("새 조건", esc(S.notice.text)) +
      S.steps.map((x, i) => (i === ci && (S.considered.length || S.blocked.length) ? li("검토", [S.considered.length ? `함께 본 후보: ${S.considered.map(c => esc(c.label)).join(", ")}` : "", S.blocked.length ? `막힌 선택: ${S.blocked.map(c => `${esc(c.label)}(${esc(c.note)})`).join(", ")}` : ""].filter(Boolean).join("<br>")) : "") +
        li(x.kind, x.kind === "선택" ? `<b>${esc(x.t)} ${esc(x.label)}</b> — ${esc(x.why || "")}${agPayLine(x.charge)}<div class="rp-sev">${ev(x.evidence)}</div>` : `${esc(x.t)} ${esc(x.label)} — ${esc(x.why || "")}`, x.kind === "마감 확인" ? "hit" : "")).join(""); }
  return `<section class="rp rp-story${S.keep_reason ? " keep" : ""}"><div class="rp-eye"><span>운영 변경 반응</span><em class="rp-st${S.keep_reason ? "" : " chg"}">${esc(S.cls)}</em></div><ol class="rp-stl">${body}</ol></section>`;
}
function agDetail(c) {
  const one = agIsOne(AG.res), sc = one ? agScene() : null;
  if(one&&sc)return agBRCard(c,sc);
  if (one && sc && sc.k !== "turn" && sc.basis && sc.basis.m4) return agU06ActivityCard(c, sc);
  if (one && sc && sc.k !== "turn" && !(sc.k === "start" && false)) return agSceneCard(c, sc);
  return agTurnCard(c, !one);
}
const AG_XCLS = { direct: "직접 관련 경험", transfer: "유사 경험 기반 · 전이 가설", common: "공통 계산 중심", na: "현재 평가 불가", situation: "운영 상황 기준" };
function agExpInfo(X) {   // 짧게 세 가지만 — 착안 근거 · 바꾼 조건 · 계산하지 않은 것. 사실 ID · 분류 · 버전은 프로파일 · 카드 접기에서
  const why = X.basis && X.basis[0] ? X.basis[0].why.replace(/^\(팀 최신본\)\s*/, "") : "";
  const not = X.engine_note && X.engine_note.includes("—") ? X.engine_note.split("—").slice(1).join("—").trim() : (X.unverified && X.unverified[0]) || "";
  return [why && `착안: ${why}`, `바꾼 조건: ${X.change || X.levers}`, not && `계산하지 않은 것: ${not}`].filter(Boolean).join(" · ");
}
function agExpHead(X, sub) {   // 여러 명 모드 상단 제목 — 기존 g-id 구조 재사용
  return `<div class="g-id"><div class="g-name">운영 실험 · ${esc(X.title || X.question)}${noteI(agExpInfo(X))}</div><div class="g-run">${esc(X.change || X.levers)}${sub ? ` · ${sub}` : ""}</div></div>`;
}
function agExpRow(X, c) {   // 한 명 모드 — 사진 카드 아래 '기준 → 변경' 비교 행 머리말
  return `<div class="ag-xrow"><span class="ag-expk">운영 실험</span><b>${esc(X.title || X.question)}</b>${noteI(agExpInfo(X))}<span class="hint ag-xchg">${esc(X.change || X.levers)}</span></div>`;
}
const agChg = (R, pid) => ((R.compare.customers.find(y => y.persona_id === pid) || {}).status === "changed") ? 1 : 0;
// 여러 명 · 조건 변경 — 기존 조건 vs 변경 조건 비교 행(기존 ag-cmp2 모양 재사용) + 실제 계산 결과 한 줄
// 03 운영자가 직접 바꾼 상품 조건을 한 줄로(비교 행 제목) — 상품 이름 + 바꾼 값만
function agLeverText(L) {
  if (!L) return "";
  const all = [AG_WINE, ...(((AG.meta || {}).products) || []), ...(((AG.metaB || {}).products) || [])], won = n => Number(n).toLocaleString("ko-KR");
  return Object.entries(L).map(([pid, lv]) => {
    const p = all.find(x => x.product_id === pid), nm = pid === "WINE_FAIR" ? "와인페어" : p ? agShort(p.label) : pid, base = p && p.price_krw;
    const parts = [];
    if (lv.price != null && lv.price !== "") parts.push(base ? `${won(base)} → ${won(lv.price)}` : `가격 ${won(lv.price)}`);
    if (lv.guest_discount) parts.push(`투숙객 할인 ${won(lv.guest_discount)}${base ? ` (${won(base)} → ${won(base - lv.guest_discount)})` : ""}`);
    if (lv.in_package) parts.push("객실 포함");
    if (lv.available === false) parts.push("판매 안 함");
    if (lv.variant && lv.variant !== "standard") { const v = AG_WINE_VAR.find(([k]) => k === lv.variant); parts.push(v ? v[1].split(" · ")[0] : lv.variant); }
    return parts.length ? `${nm} ${parts.join(" · ")}` : "";
  }).filter(Boolean).join(" / ");
}
// 보충2 — 고객별 방문 조건 표시(한 줄 · 분포 타일). 점수 · 확률 없음
const AG_BLD_SHORT = { VISTA: "비스타", GRAND: "그랜드", DOUGLAS: "더글라스", NONSTAY: "비투숙" }, AG_PH_KO = { checkin: "체크인 당일", mid: "연박 중간일", checkout: "체크아웃 당일", visit: "당일 방문" };
function agVisitShort(pid) { const V = agVC(pid); const v = V.v; if (!v) return ""; return v.stay ? `${AG_BLD_SHORT[v.building] || v.building} ${v.nights}박 · ${AG_PH_KO[v.phase]} · ${v.party_size}인` : `비투숙 당일 방문 · ${v.party_size}인`; }
const AG_VISIT_HELP = { what: "이 고객의 투숙 여부 · 건물 · 박수 · 체류 단계 · 동행은 운영자 입력이 아니라, 후기 경험(같은 숙박 · 방문 형태)과 유형 · 성향, 행사 유무로 에이전트가 정한 것입니다.", basis: ["실제 후기", "추출 성향", "운영 조건 · 계산"], caution: "숙박 · 객실 선택에는 정량 계수가 없어 점수 · 확률을 매기지 않았습니다(규칙 계획기 · 시드 고정 · 같은 조건 = 같은 결과). 후기의 과거 조건이 가장 무겁지만 그대로 복사하지는 않습니다." };
function agVisitLine(pid) {
  const V = agVC(pid), v = V.v; if (!v) return "";
  const rv = v.layer_stay === "review", opts = (v.options || []).map(o => AG_BLD_SHORT[o] || o).join(" · ");
  const pkg = v.package_context, ent = Object.values((v.benefit_usage || {}).package_entitlements || {})[0];
  const pkgLine = pkg ? `<span class="rp-tag as">${esc(pkg.label)} · 가상 시나리오</span>${ent ? `<span class="rp-tag as">사우나 혜택 ${ent.used_count}/${ent.limit}회 사용 · 잔여 ${ent.remaining}회</span>` : ""}` : "";
  return `<div class="rp-visit"><span class="rp-vk">이번 방문</span><b>${esc(agVisitShort(pid))}</b><span class="rp-tag ${rv ? "rv" : "as"}">${rv ? "후기 경험" : "프로파일 구성"}</span>${pkgLine}${noteH(Object.assign({}, AG_VISIT_HELP, { basis: rv ? AG_VISIT_HELP.basis : ["추출 성향", "운영 조건 · 계산"], basis_note: (v.basis && v.basis.facts && v.basis.facts.length ? `연결한 후기 사실: ${v.basis.facts.join(" · ")} · ` : "후기에 숙박 단서가 없어 유형 · 성향으로 구성 · ") + `동행: ${v.layer_party === "review" ? "후기에서 확인" : "유형 기준"}` + (opts ? ` · 고려한 선택지: ${opts}` : "") }))}</div>`;
}
function agVisitDist() {
  const Vs = AG.visits; if (!Vs) return "";
  const ids = Object.keys(Vs), bc = {}, pc = {};
  ids.forEach(id => { const v = Vs[id]; const k = v.stay ? v.building : "NONSTAY"; bc[k] = (bc[k] || 0) + 1; const ph = v.stay ? v.phase : "visit"; pc[ph] = (pc[ph] || 0) + 1; });
  const ord = ["GRAND", "VISTA", "DOUGLAS", "NONSTAY"], pord = ["checkin", "mid", "checkout", "visit"];
  return `<section class="ag-blk ag-vdist"><div class="rp-eye"><span>고객별 방문 조건 · ${ids.length}명이 각자 정함</span>${noteH(Object.assign({}, AG_VISIT_HELP, { what: "같은 운영 조건(행사 · 가격 · 혜택)에서 고객마다 자기 후기 경험 · 유형 · 성향으로 투숙 여부 · 건물 · 박수 · 체류 단계 · 동행을 정한 결과의 분포입니다. 고객 ID를 누르면 그 고객이 무엇을 골랐는지 보입니다." }))}</div>
    <div class="ag-big ag-big4">${ord.filter(k => bc[k]).map(k => `<div class="ag-bv" style="--vc:${k === "NONSTAY" ? "var(--ink2)" : "var(--k-room)"}"><span class="ag-bvl">${esc(AG_BLD_SHORT[k])}</span><b>${bc[k]}<small>명</small></b></div>`).join("")}</div>
    <div class="ag-vph">${pord.filter(k => pc[k]).map(k => `<span>${AG_PH_KO[k]} <b>${pc[k]}</b></span>`).join("")}<span class="rp-mut">동행 ${ids.filter(id => Vs[id].layer_party === "review").length}명 후기 확인 · ${ids.filter(id => Vs[id].layer_party !== "review").length}명 유형 기준</span></div>
    <ul class="ag-vlist">${ids.map(id => `<li data-p="${id}" class="${AG.sel === id ? "on" : ""}" tabindex="0"><b>${esc(dno(id))}</b><span>${esc(agVisitShort(id))}</span><em class="${Vs[id].layer_stay === "review" ? "rv" : "as"}">${Vs[id].layer_stay === "review" ? "후기" : "구성"}</em></li>`).join("")}</ul></section>`;
}
function agManyCmp(R) {
  const X = AG.exp, cmp = R.compare, bv = {}, av = {};
  cmp.customers.forEach(c => { bv[c.before.venue_id] = (bv[c.before.venue_id] || 0) + 1; av[c.after.venue_id] = (av[c.after.venue_id] || 0) + 1; });
  const lab = v => ({ ROOM_MEAL: "객실 식사", ROOM: R.turn === "event" ? "객실 휴식" : "건너뜀", PIZZA_HILL: "피자힐", FOREST: "와인페어", SKYARD: "족욕", LE_PASSAGE: "르 파사쥬", THE_BUFFET: "더뷔페", MYONGWOLGWAN: "명월관", ONDAL: "온달", GEUMRYONG: "금룡", NONE: "결정 없음" })[v] || v;
  const side = (o, title) => `<div class="ag-cb"><span>${title}</span>${Object.entries(o).sort((a, b) => b[1] - a[1]).map(([v, n]) => `<div class="ag-cbl">${agDot(v)}${esc(lab(v))} <b>${n}</b></div>`).join("")}</div>`;
  const asmDep = cmp.customers.filter(c => c.before.product_id !== c.after.product_id).map(c => (R.customers || []).find(x => x.persona_id === c.persona_id))
    .filter(x => x && x.reason_totals.assumption > 0.01 && x.best_other_venue && x.reason_totals.assumption > x.best_other_venue.margin).length;   // 02-D 설계 가정 의존
  return `<div class="ag-cmp2 ${cmp.summary.changed ? "chg" : ""}"><div class="ag-cmh">${X ? esc(X.change || X.levers) : esc(agLeverText(R.conditions && R.conditions.product_levers) || "운영 조건 변경")} · <b>${cs_n(cmp)} 중 ${cmp.summary.changed}명</b> 선택 변경${asmDep ? `<span class="hint" title="바뀐 선택 가운데 근거 없는 설계 가정(객실 휴식 가치)이 다른 업장과의 차이보다 큰 고객 — 가정 없이는 결과가 달라질 수 있음"> · ${asmDep}명은 객실 휴식 설계값 영향이 큼</span>` : ""}</div><div class="ag-cmr">${side(bv, "기존 조건")}<i>→</i>${side(av, "변경 조건")}</div></div>`;
}
const cs_n = cmp => cmp.customers.length + "명";
function agPanel() {
  const R = AG.res; if (!R) return;
  if (agIsMany(R) && !AG.fix) return agOpsPanel(AG.manyT != null ? AG.manyT : agMin(R.time));
  const cs = R.customers, c = agCur();
  const X = AG.exp;
  let h = "";
  if (cs.length > 1) {
    const vl = v => v === "ROOM_MEAL" ? (R.turn === "breakfast" ? "객실 조식" : "객실 식사") : v === "ROOM" ? (R.turn === "event" ? "객실 휴식" : R.turn === "breakfast" ? "아침 건너뜀" : "저녁 건너뜀") : v === "FOREST" ? "와인페어" : v === "SKYARD" ? "족욕" : null;
    const byV = {}; cs.forEach(x => { const k = x.choice.venue_id; (byV[k] = byV[k] || { n: 0, label: vl(k) || x.choice.venue_label }).n++; });
    const vs = Object.entries(byV).sort((a, b) => b[1].n - a[1].n);
    if (X) h += `<div class="rp-exp"><span>운영 실험</span>${esc(X.title || X.question)}${noteH({ what: agExpInfo(X), basis: ["운영 조건 · 계산"], caution: "실험 카드의 조건을 적용한 가상 운영안입니다." })}</div>`;
    const nAll = agAllIds().length;
    if (R._auto) h += agVisitDist();
    h += `<section class="ag-blk ag-res"><div class="rp-eye"><span>${esc(R.time || "")} · ${AG_TURN[R.turn]} 선택 · 고객 ${cs.length}팀${nAll > cs.length ? `<small class="rp-mut"> / ${nAll}팀 중 이 시각 호텔에 있는 고객</small>` : ""}</span>${noteH({ what: "고른 에이전트들의 엔진 선택을 업장별로 센 숫자입니다.", basis: ["운영 조건 · 계산"], caution: "실제 방문객 수나 수요 예측이 아닙니다. 에이전트끼리 좌석 · 대기로 서로 영향을 주지 않습니다." })}</div>
      <div class="ag-big">${vs.map(([v, o]) => `<div class="ag-bv" style="--vc:${agVColor(v)}"><span class="ag-bvl">${agDot(v)}${esc(o.label)}</span><b>${o.n}<small>명</small></b></div>`).join("")}</div>
      ${R.compare ? agManyCmp(R) : ""}</section>`;
    if (AG.focusLoc && cs.some(x => x.choice.map_loc === AG.focusLoc)) {
      const inL = cs.filter(x => x.choice.map_loc === AG.focusLoc), v0 = inL[0].choice;
      h += `<section class="ag-blk ag-clb"><div class="ag-blkh" id="agClH"><b>${agDot(v0.venue_id)}${esc(vl(v0.venue_id) || v0.venue_label)} · ${inL.length}명</b><span>이 지점에 모인 고객 · 누르면 상세</span><button type="button" class="linkbtn" id="agClOff">닫기</button></div>
        <ul class="ag-roster ag-clr">${inL.map(x => `<li data-p="${x.persona_id}" class="${AG.sel === x.persona_id ? "on" : ""}" tabindex="0"><b>${esc(dno(x.persona_id))}</b><span class="ag-rl">${esc(agShort(x.choice.product_label))}</span><span class="ag-rm">${x.best_other_venue ? `<span class="ag-mgk">대안 차</span> ${agNum(x.best_other_venue.margin)}` : ""}</span></li>`).join("")}</ul></section>`;
    }
    if (c) { const here = cs.includes(c); h += `<div class="ag-selh" id="agSelH"><b>${esc(dno(c.persona_id))}</b><span>선택 상세</span><button type="button" class="linkbtn" id="agSelOff">선택 해제</button></div>${agVisitLine(c.persona_id)}${agStory(c.persona_id)}` + (here ? agDetail(c) : `<section class="rp rp-scene ag-gen"><div class="rp-eye"><span>${esc(R.time || "")} · ${AG_TURN[R.turn]}</span><span class="rp-tag as">이 결정 없음</span></div><p class="rp-line">${esc(agVisitShort(c.persona_id))} 조건이라 이 시각의 ${AG_TURN[R.turn]} 결정이 없습니다. 아래 시간축 재생이나 이 고객의 하루 띠에서 다른 시각을 보세요.</p></section>`); }
    h += `<section class="ag-blk"><div class="ag-blkh"><b>에이전트별 선택</b><span>누르면 지도에서 강조</span>${noteH({ what: "고객마다 이번 턴에 고른 업장 · 상품입니다. 오른쪽 숫자는 다른 업장 최고 대안과의 점수 차입니다.", basis: ["운영 조건 · 계산"], caution: "점수 차는 확률이 아닙니다. 0.15보다 작으면 '근소'." })}</div>
      <ul class="ag-roster">${[...cs].sort((a, b) => R.compare ? (agChg(R, b.persona_id) - agChg(R, a.persona_id)) : 0).map(x => { const o = x.best_other_venue, cc = R.compare && R.compare.customers.find(y => y.persona_id === x.persona_id), chg = cc && cc.status === "changed";
        return `<li data-p="${x.persona_id}" class="${AG.sel === x.persona_id ? "on" : ""}${chg ? " chg" : ""}" tabindex="0"><b>${esc(dno(x.persona_id))}</b><span class="ag-rl">${x.vc && x.vc.v ? `<i class="ag-rvb" title="${esc(agVisitShort(x.persona_id))}">${esc(x.vc.stay ? AG_BLD_SHORT[x.vc.B] : "비투숙")}</i>` : ""}${chg ? `<s>${esc(vl(cc.before.venue_id) || cc.before.venue_label)}</s><i>→</i>` : ""}${agDot(x.choice.venue_id)}<b>${esc(vl(x.choice.venue_id) || x.choice.venue_label)}</b> <span>${esc(agShort(x.choice.product_label))}</span></span><span class="ag-rm">${cc ? (chg ? '<em class="ag-chg">변경</em>' : R.turn === "event" && x.choice.venue_id === "FOREST" ? '<em class="ag-keep">기존 참여</em>' : '<em class="ag-keep">유지</em>') : ""}${o ? `${o.margin < 0.15 ? '<em class="ag-near">근소</em>' : ""}<span class="ag-mgk">대안 차</span> ${agNum(o.margin)}` : ""}</span></li>`; }).join("")}</ul></section>`;
  }
  if (c && cs.length === 1 && AG.from === c.persona_id) h = `<button class="back ag-backp" data-pf="${c.persona_id}">← ${esc(dno(c.persona_id))} 프로파일로</button>` + h;
  if (c && cs.length === 1) h += agStory(c.persona_id) + agDetail(c);
  $("#panel").innerHTML = h;
  if (typeof rcMountPanel === "function") rcMountPanel();
  agU06PanelChrome();
  const co = $("#agClOff"); if (co) co.onclick = () => { AG.focusLoc = null; agDrawMap(); agPanel(); };
  const so = $("#agSelOff"); if (so) so.onclick = () => { AG.sel = null; if (AG.keep[AG.mode]) AG.keep[AG.mode].sel = null; cancelAnimationFrame(AG.raf); agDrawMap(); agStrip(); agPanel(); };
  $$("#panel [data-dr]").forEach(b => b.onclick = () => agChoiceDrawer(b.dataset.dr, AG.ti));   // CL-11 — 계산 내역은 선택 상세 드로어
  $$("#panel [data-pf]").forEach(b => b.onclick = () => agCustDrawer(b.dataset.pf, "ev"));   // 프로파일 · 후기 근거도 드로어(페이지 이동 없음)
  $$("#panel [data-why]").forEach(b => b.onclick = () => { const ti = AG.runs.indexOf(AG.res); if (typeof setPlay === "function") setPlay(false); cancelAnimationFrame(AG.raf); AG.playing = false; agStripState && agStripState(); agChoiceDrawer(b.dataset.why, ti >= 0 ? ti : AG.ti); });   // P5 — 오른쪽 패널의 '자세한 판단 근거' → 폭 제한 결정 패널
  $$("#panel [data-bh]").forEach(b => b.onclick = () => { const ti = AG.runs.indexOf(AG.res); bhFromFlow(b.dataset.bh, ti >= 0 ? ti : AG.ti); });   // P3 — 지도에서 보던 결정(같은 저장 기록) 그대로
  $$("#panel [data-actd]").forEach(b => b.onclick = () => { const [id, si] = b.dataset.actd.split("|"); agActDrawer(id, +si); });
  $$("#panel [data-go]").forEach(li => { const go = () => { cancelAnimationFrame(AG.raf); AG.playing = false; AG.paused = false; agSetScene(+li.dataset.go, 1); agStripState(); }; li.onclick = go; li.onkeydown = e => { if (e.key === "Enter") go(); }; });
  $$("#panel [data-ff]").forEach(b => b.onclick = () => c && agToProfile(c.persona_id, b.dataset.ff.split(",").filter(Boolean)));
  const xm = $("#agExpMany"); if (xm) xm.onclick = () => { const toMany = AG.mode !== "agents"; if (toMany) { AG.one = AG.exp.agent; AG.keep.agents = null; } else { AG.keep.agent = null; } AG.autorun = true; cancelAnimationFrame(AG.raf); setMode(toMany ? "agents" : "agent"); };
  $$("#panel .ag-roster li[data-p], #panel .ag-vlist li[data-p]").forEach(li => { li.onclick = () => agSelect(li.dataset.p); li.onkeydown = e => { if (e.key === "Enter") agSelect(li.dataset.p); }; });
  const img = $("#agImg"); if (img && c && typeof openPlaceImage === "function") img.onclick = () => openPlaceImage(c.choice.map_loc);
}

// ---------------------------------------------------------------- 드로어(기존 openDrawer 재사용)
function agProfile(pid) {
  const p = AG.meta.personas.find(x => x.id === pid); if (!p) return;
  const h = `<div class="card"><h4>성향 전체</h4>${agBars(p.bars)}
      <div class="hint">막대 = 엔진이 쓰는 성향 수준 · 근거 = 그 성향에 연결된 후기 사실 수(점수 아님) · 근거 미확인 = 0점이 아니라 후기에서 확인하지 못함</div></div>
    <div class="card"><h4>상태</h4><table class="kv ag-kv"><tr><td>출처</td><td>실제 후기 작성자의 워커힐 후기 + 같은 작성자의 다른 경험 글</td></tr><tr><td>추출</td><td>추출 완료 · 독립 검증 전</td></tr></table>
      <div class="hint">대표 후기 · 유사 경험 · 추출 사실을 함께 보는 상세 프로파일은 페르소나 라이브러리에서 연결합니다.</div></div>`;
  openDrawer(`${p.label} · 프로파일`, "후기 기반 성향", h);
}
function agDrawer(pid) {
  const R = AG.res, c = R.customers.find(x => x.persona_id === pid); if (!c) return;
  const pr = c.choice.price;
  const priceLine = p => `${agWon(p.pp_krw)}${p.party_basis ? ` <span class="hint">(${agWon(p.list_krw)} ÷ ${p.party_basis}인${p.party_basis_stated === false ? " · 추정" : ""})</span>` : p.share_n ? ` <span class="hint">(${agWon(p.list_krw)} ÷ 나눔 ${p.share_n}인)</span>` : ""}`;
  const srcBadges = p => `<span class="badge">${esc(p.menu_as_of || "")}</span>${p.is_estimate ? `<span class="badge warn">추정 가격</span>` : ""}${p.operator_set ? `<span class="badge">운영자 설정</span>` : ""}`;
  const maxAbs = Math.max(...c.reasons.map(r => Math.abs(r.value)), 0.01);
  const bar = r => {
    const seg = ["common", "review", "transfer", "out_of_scope", "assumption"].filter(k => Math.abs(r.parts[k] || 0) > 1e-6).map(k => `<i class="s-${k}${r.parts[k] < 0 ? " neg" : ""}" style="width:${(Math.abs(r.parts[k]) / maxAbs * 100).toFixed(1)}%"></i>`).join("");
    const sub = r.product_direct_visits === 0 || r.score_provenance_conflict || r.parts.transfer ? `<div class="hint ag-prov">${r.product_direct_visits === 0 ? esc(r.note) : r.parts.transfer ? `맥락 이전 추론 +${agNum(r.parts.transfer)}(같은 업장의 다른 메뉴 · 끼니 — 이 상품 직접 경험 아님)` : ""}${r.score_provenance_conflict ? `<span class="dev-only">${r.product_direct_visits === 0 || r.parts.transfer ? " · " : ""}출처 충돌 +${agNum(r.score_provenance_conflict.amount)}(개발 정보 · 동결 입력 진단)</span>` : ""}</div>` : "";
    return `<tr><td>${escP(r.factor)}${sub}</td><td class="ag-rb">${seg}</td><td class="num${r.value < 0 ? " neg" : ""}">${r.value > 0 ? "+" : ""}${agNum(r.value)}</td></tr>`;
  };
  // 10/23 · 대표 근거 3개만 먼저(기여가 큰 항부터 · 같은 사실 한 번) — 나머지는 '추가 근거 보기'. 사실마다 원문 게시글 링크(검증된 수집 표에서만)
  const agSrc = fid => { try { const lp = typeof libP === "function" && LIBV.data ? libP(c.persona_id) : null, f = lp && lp.engine && lp.engine.facts[fid];
      const u = (f && f.post && libUrl(f.post)) || (lp && lp.group === "dev" ? libStartUrl(lp) : null); return u ? libA(u, "원문 ↗", "sm") : ""; } catch (e) { return ""; } };
  const rvR = c.reasons.filter(r => r.parts.review && r.fact_ids.length).sort((a, b) => b.parts.review - a.parts.review), seenF = new Set(), top3 = [];
  for (const r of rvR) for (const f of r.fact_ids) if (top3.length < 3 && !seenF.has(f) && agEvidenceText(c, f) !== "설명 확인 필요") { seenF.add(f); top3.push([r, f]); }
  const nAll = rvR.reduce((a, r) => a + r.fact_ids.length, 0);
  const ev = rvR.length ? `<ul class="ag-top3">${top3.map(([r, f]) => `<li><span class="ag-t3f">${escP(r.factor)}</span><span class="ag-t3g">${esc(agEvidenceText(c, f))}</span><span class="ag-t3m"><span class="badge">${esc(fidD(f))}</span>${agSrc(f)}</span></li>`).join("")}</ul>` +
    (nAll > top3.length ? `<details class="ag-ev ag-more2"><summary>추가 근거 보기 <span class="hint">${nAll - top3.length}건 · 항목별</span></summary>${rvR.map(r => `<details class="ag-ev"><summary>${escP(r.factor)} <span class="hint">후기 근거 ${r.fact_ids.length}건 · +${agNum(r.parts.review)}</span></summary><ul>${r.fact_ids.map(f => `<li><span class="badge">${esc(fidD(f))}</span> ${esc(agEvidenceText(c, f))} ${agSrc(f)}</li>`).join("")}</ul></details>`).join("")}</details>` : "") : "";
  const asm = c.reasons.filter(r => r.parts.assumption);
  const others = c.not_chosen.filter(o => o.feasible && o.score != null).slice(0, 8);
  const im = typeof placeImg === "function" ? placeImg(c.choice.map_loc) : null;
  const h = `
    <div class="card"><h4>선택한 옵션</h4>
      ${im ? `<figure class="ag-dimg"><img src="${im.src}" alt="${esc(im.name)}"><figcaption>${esc(im.credit)}</figcaption></figure>` : ""}
      <div class="ag-pick">${agDot(c.choice.venue_id)}<b>${esc(agChoiceName(R, c.choice))}</b></div>
      <table class="kv ag-kv"><tr><td>선택 점수</td><td><b>${agNum(c.choice.score)}</b></td></tr><tr><td>1인 지불</td><td>${priceLine(pr)}</td></tr><tr><td>가격 · 메뉴 출처</td><td>${srcBadges(pr)}</td></tr></table></div>
    <div class="card"><h4>이렇게 선택한 이유</h4>${agStack(c)}
      <table class="ag-rt">${c.reasons.map(bar).join("")}<tr class="sum"><td>합계</td><td></td><td class="num">${agNum(c.choice.score)}</td></tr></table>
      <div class="hint">공통 계산 = 후기 근거가 없어도 누구에게나 같은 값(끼니 · 기본 음식 · 지불액 등) · 후기 근거 = 이 에이전트의 후기에서 연결된 몫 · 설계 가정 = 출처 없이 월드 설계로 들어간 값${c.reason_totals.transfer ? " · 맥락 이전 추론 = 같은 업장의 다른 메뉴 · 끼니 경험에서 넓힌 몫(이 상품 직접 경험 아님)" : ""}${c.reason_totals.out_of_scope ? `<span class="dev-only"> · 출처 충돌 = 제품 범위 밖 사실이 동결 입력에 남은 몫(개발 정보 · SCORE_PROVENANCE_CONFLICT)</span>` : ""}</div>
      ${c.product_direct_visits === 0 || (c.direct_review_fact_ids && !c.direct_review_fact_ids.length && c.reason_totals.transfer) ? `<div class="hint ag-prov"><b>이 상품 직접 이용 근거 없음</b> — 후기에서 이 상품을 먹거나 이용한 기록이 없습니다(직접 이용 0회).</div>` : ""}</div>
    ${ev ? `<div class="card"><h4>후기 근거 요지</h4><div class="hint">제공된 구조화 사실의 요지입니다. 원문 직접 대조·사람 검수 완료를 뜻하지 않습니다.</div>${ev}</div>` : `<div class="card"><h4>후기 근거 요지</h4><div class="hint">이번 선택에는 후기 근거가 작용한 항이 없습니다.</div></div>`}
    ${asm.length ? `<div class="card"><h4>설계 가정</h4><ul class="ag-plain">${asm.map(r => `<li>${escP(r.factor)} +${agNum(r.parts.assumption)} — 객실 식사의 휴식 가치(0.6)는 공식 정보나 후기 근거가 연결되지 않은 설계 가정입니다.</li>`).join("")}</ul></div>` : ""}
    <div class="card"><h4>선택하지 않은 옵션</h4><table class="ag-ot"><tr><th>옵션</th><th>1인</th><th>점수</th><th>차이</th></tr>${others.map(o => `<tr><td>${agDot(o.venue_id)}${esc(agChoiceName(R, o))}${o.price.is_estimate ? ' <span class="badge warn">추정</span>' : ""}</td><td>${agWon(o.price.pp_krw)}</td><td>${agNum(o.score)}</td><td>${agNum(c.choice.score - o.score)}</td></tr>`).join("")}</table>
      ${R.excluded.length ? `<div class="hint">후보에서 뺀 상품: ${R.excluded.map(e => esc(e.product_label)).join(" · ")} — 인원 기준이 자료에 없어 운영자가 인원을 넣어야 비교합니다.</div>` : ""}</div>
    <div class="card"><h4>페르소나 성향 전체</h4>${agBars(c.persona.bars)}</div>`;
  openDrawer(`${dno(c.persona_id)} · ${AG_TURN[R.turn]} 턴`, agChoiceName(R, c.choice), h);
}
window.addEventListener("resize", () => { if ((MODE === "agent" || MODE === "agents") && AG.res) { agDrawMap(); agTlFit(); agStripState(); } });

// ================================================================ 10/24 CL-1024-11 — 행동 가시성 · 운영 패널 · 시간축 · 아바타 · 드로어
// 원칙: 화면의 모든 숫자 · 피드 · 일정은 실제 생성된 장면(agScenes)과 엔진 결과에서만 만든다. 점유율 · 매출 · 확률은 만들지 않는다.
const agBatchim = w => { const c = String(w || "").trim().slice(-1).charCodeAt(0); return c >= 0xAC00 && c <= 0xD7A3 ? (c - 0xAC00) % 28 : 0; };
const agRo = w => `${w}${(b => b === 0 || b === 8 ? "로" : "으로")(agBatchim(w))}`;
const agEul = w => `${w}${agBatchim(w) ? "을" : "를"}`;
// 활동 분류 — 운영자가 보는 묶음(식음 · 수영/사우나/족욕 · 행사/문화 · 산책 · 객실 · 도착/퇴실 · 이동 · 호텔 밖)
const AG_CAT = {
  meal: { label: "식음", color: "#e07a2c", icon: "noon" }, well: { label: "수영 · 사우나 · 족욕", color: "#3f8f8a", icon: "pool" }, culture: { label: "행사 · 문화", color: "#a8324e", icon: "lobby" },
  walk: { label: "산책 · 야외", color: "#6f9a4f", icon: "walk" }, room: { label: "객실", color: "#5f7aa6", icon: "rest" }, stay: { label: "도착 · 체크인 · 퇴실", color: "#8f8a83", icon: "lobby" },
  move: { label: "이동", color: "#b9ad9b", icon: "move" }, out: { label: "호텔 밖", color: "#a99c88", icon: "move" },
};
const AG_CAT_ORDER = ["meal", "well", "culture", "walk", "room", "stay", "out", "move"];
function agCatOf(sc, pid) {
  if (!sc) return "stay"; if (sc.k === "move") return "move";
  if (sc.k === "turn") { const R = AG.runs[sc.ti], c = R && agCustOf(R, pid), v = c ? c.choice.venue_id : ""; if (R && R.turn === "event") return v === "FOREST" ? "culture" : v === "SKYARD" ? "well" : "room"; return v === "ROOM" ? "room" : "meal"; }
  const a = sc.act || "";
  if (a === "lunch_outside") return "out";
  if (/^lunch_|^cafe$|^bakery$|^luxbar$|^room_snack$|^(ROOM_MEAL|SIMPLE_MEAL_VIEW|PIZZA_HILL|MYONGWOLGWAN|ONDAL|GEUMRYONG|THE_BUFFET|BREAKFAST_BUFFET|RS_)/.test(a)) return "meal";
  if (/^pool$|^sauna$|^fitness$|footbath$|^(SKYARD|SKYARD_NIGHT|POOL|SAUNA)$/.test(a)) return "well";
  if (/^WINE_FAIR/.test(a)) return "culture";
  if (/^FOREST_WALK$/.test(a)) return "walk";
  if (/^(idle|wait)$/.test(a) && !/_ROOM$/.test(sc.loc || "")) return "stay";
  if (/^theatre$|^library$|^lounge$/.test(a)) return "culture";
  if (/walk$|^riverpark$|^tennez$/.test(a)) return "walk";
  if (/^arrive$|^checkin$|^checkout$|^leave$/.test(a) || sc.k === "start" && !/_ROOM$/.test(sc.loc || "")) return "stay";
  return "room";
}
const agTurnAct = (R, ch) => R.turn === "event" ? (ch.venue_id === "FOREST" ? "와인페어 참여" : ch.venue_id === "SKYARD" ? "와인페어 대신 족욕" : "행사 대신 객실 휴식") : R.turn === "breakfast" ? (ch.venue_id === "ROOM" ? "아침 건너뜀" : `아침 · ${agMenu(ch.product_label)}`) : (ch.venue_id === "ROOM" ? "저녁 건너뜀" : `저녁 · ${agMenu(ch.product_label)}`);
const agScLabel = (sc, pid) => { if (sc.k === "turn") { const R = AG.runs[sc.ti], c = R && agCustOf(R, pid); return c ? agTurnAct(R, c.choice) : sc.label; } return sc.label || ""; };
const agScShort = (sc, pid) => sc.k === "turn" ? (AG_TURN[AG.runs[sc.ti].turn] || sc.label) : (sc.short || sc.label || "");
// ---------------------------------------------------------------- 시각 T 의 운영 현황(전원)
function agOpsAt(T) {
  const o = { T, present: [], pre: [], post: [], moving: [], byCat: {}, byLoc: {}, cur: {} };
  agAllIds().forEach(id => {
    const p = agManyPos(id, T); if (!p) return;
    if (p.away) { o[p.away].push([id, p.sc]); return; }
    o.present.push(id); const cat = p.moving ? "move" : agCatOf(p.sc, id); o.cur[id] = { p, cat };
    if (p.moving) o.moving.push([id, p]);
    else { const L = o.byLoc[p.loc] = o.byLoc[p.loc] || { loc: p.loc, cat, ids: [], acts: {} }; L.ids.push(id); const lb = agScLabel(p.sc, id); L.acts[lb] = (L.acts[lb] || 0) + 1; }
    (o.byCat[cat] = o.byCat[cat] || []).push(id);
  });
  return o;
}
// 실시간 행동 피드 — 장면이 시작된 순간(이동 시작 · 활동 시작 · 주요 결정)을 시각 역순으로. 생성 장면에서만 만든다
function agFeed(T, span = 150, n = 7) {
  const ev = [];
  agAllIds().forEach(id => {
    const L = agScenes(id);
    L.forEach((sc, i) => {
      if (sc.t0 > T + 0.01 || sc.t0 < T - span) return;
      if (sc.k === "move") { const prev = L.slice(0, i).reverse().find(x => x.k !== "move"), next = L.slice(i + 1).find(x => x.k !== "move"); if (!next) return;
        ev.push({ t: sc.t0, id, cat: "move", txt: `${prev ? `${agScShort(prev, id)}${/^(arrive|checkin|checkout|wake|unpack|pack)$/.test(prev.act || "") ? " 후" : " 마치고"} ` : ""}${agRo(agPlaceName(next.loc, AG.runs[next.ti]))} 이동` }); return; }
      if (sc.k === "turn") { const R = AG.runs[sc.ti], c = agCustOf(R, id); if (!c) return; const cc = R.compare && R.compare.customers.find(y => y.persona_id === id);
        ev.push({ t: sc.t0, id, cat: agCatOf(sc, id), key: true, txt: `${agTurnAct(R, c.choice)}${cc && cc.status === "changed" ? " · 조건 변경으로 바뀜" : ""}` }); return; }
      ev.push({ t: sc.t0, id, cat: agCatOf(sc, id), txt: sc.act === "arrive" ? `호텔 도착${sc.why ? ` · ${sc.why}` : ""}` : sc.act === "leave" ? "귀가" : `${sc.label}${sc.act && sc.name && !/객실/.test(sc.label) && !sc.label.includes(sc.name) ? ` · ${sc.name}` : ""}` });
    });
  });
  return ev.sort((a, b) => b.t - a.t || (b.key ? 1 : 0) - (a.key ? 1 : 0)).slice(0, n);
}
// ---------------------------------------------------------------- 아바타 자산(§5) — 유형 · 동행 인원이 맞는 그림. 실제 작성자의 성별 · 외모를 뜻하지 않음
const AG_AV_NOTE = "그림은 고객 유형과 이번 동행 인원을 알아보기 위한 표현이며, 실제 작성자의 성별 · 나이 · 외모가 아닙니다.";
// CL-1024-11 보충 — 기존 11명은 ID 기준 직접 매핑(유형 문자열로 다시 고르지 않음). supported = 그림 속 인원. 시나리오 인원이 다르면 그림을 쓰지 않고 중립 도형 + 필요 자산 보고
// asset_ko = 사용자 자산 목록의 이름(그림 내용으로 대응 · 아래 보고서 표), illustrated = 그림이 표현하는 구성(실제 작성자 신상 아님)
const AG_AVMAP = {
  A01: { av: "family_kid2", asset_ko: "자녀동반_가족형", ty: "가족 · 영유아", illustrated: "성인 2 + 아이 2", supported: 4, status: "MAPPED", note: "원문 동행 가족 4인 · 아이 동반" },
  A02: { av: "family_3gen", asset_ko: "3대가족_조부모동반", ty: "가족 · 부모 동반", illustrated: "성인 2 + 아이 1 + 조부모 2", supported: 5, status: "NEEDS_ASSET", note: "원문 동행 = 본인 + 부모 3인 → 5인 그림 강제 안 함 · 필요 자산: 성인 1 + 부모 2" },
  A03: { av: "couple_vacation", asset_ko: "일반커플_휴양형", ty: "커플 · 기념일", illustrated: "성인 2", supported: 2, status: "MAPPED", note: "커플 · 휴양형 기본(기념일형은 근거 확인 전 미적용)" },
  A04: { av: "solo_casual", asset_ko: "1인_휴식형", ty: "혼자 휴식", illustrated: "성인 1", supported: 1, status: "MAPPED", note: "원문 혼자 투숙" },
  A05: { av: "friends_2f", asset_ko: "여자2인_친구형", ty: "친구 모임", illustrated: "성인 2", supported: 2, status: "NEEDS_ASSET", note: "원문 친구 3인 → 2인 그림 강제 안 함 · 필요 자산: 친구 3인" },
  A07: { av: "couple_wine", asset_ko: "행사_미식형_커플", ty: "미식", illustrated: "성인 2", supported: 2, status: "MAPPED", note: "원문 배우자 동행 · 미식" },
  A08: { av: "solo_casual", asset_ko: "1인_휴식형", ty: "웰니스", illustrated: "성인 1", supported: 1, status: "CONDITIONAL", note: "1인 시나리오에 한정 · 후기 사실(A08S_E01)은 배우자 동행 → 2인이면 필요 자산: 웰니스 부부 2인" },
  A10: { av: "friends_2f", asset_ko: "여자2인_친구형", ty: "행사 체험", illustrated: "성인 2", supported: 2, status: "MAPPED", note: "원문 친구 1명 동행 · 그림의 성별은 실제 성별 아님" },
  blog41: { rel: "couple", av: "couple_vacation", asset_ko: "일반커플_휴양형", ty: "개발 그룹 · 커플형", illustrated: "성인 2", supported: 2, status: "MAPPED", note: "사용자 정정(10/24 03:00) 커플형 확정 · 기념일 근거 없음 → 휴양형" },
  blog42: { av: null, asset_ko: null, ty: "개발 그룹", illustrated: null, supported: null, status: "UNVERIFIED", note: "구조화 프로파일에 동행 관계 · 인원 · 목적 정보 없음(트윈베드 이용만으로 관계 · 성별을 정하지 않음) · 원문 확인 필요" },
  blog43: { av: "solo_casual", asset_ko: "1인_휴식형", ty: "개발 그룹", illustrated: "성인 1", supported: 1, status: "CONDITIONAL", note: "혼자 체류 조건(1인)에 한정 · 동행 정보는 구조화 프로파일에 없음" },
};
// 10/26 사용자 지시 — 인원이 맞는 그림이 없는 고객은 기본 그림으로 빠짐없이: 1인 = 1인_휴식형 · 친구 3인 이상 = 여자2인_친구형 · 그 밖의 여러 명 = 3대가족_조부모동반
// (그림은 분위기 표시용 · 실제 인원 · 외모 아님. 인원 표시는 카드의 '이번 인원' 값이 기준)
function agAvFallback(pid, rel, n) {
  const ty = (typeof libP === "function" && typeof LIBV !== "undefined" && LIBV.data && libP(pid) && (libP(pid).type_group || libP(pid).type)) || (AG_AVMAP[pid] && AG_AVMAP[pid].ty) || "";
  if (n <= 1) return "solo_casual";
  if (/^friend/.test(rel || "") || /친구/.test(ty)) return "friends_2f";
  if (n === 2 && /^(couple|spouse)$/.test(rel || "")) return "couple_vacation";
  return "family_3gen";
}
function agAvKey(pid, rel, n) { return agAvExact(pid, rel, n) || agAvFallback(pid, rel, n); }
function agAvExact(pid, rel, n) {
  const m = AG_AVMAP[pid]; if (m) return m.av && m.supported === n ? m.av : null;   // ID 매핑이 있으면 그것만(인원이 다르면 → 기본 그림)
  const c = AG_COMP[pid]; if (c && c.av && c.n === n) return c.av;
  const ty = (typeof libP === "function" && typeof LIBV !== "undefined" && LIBV.data && libP(pid) && (libP(pid).type_group || libP(pid).type)) || "";
  if (rel === "family_kids") return n === 4 ? "family_kid2" : n === 3 ? "family_kid1" : null;
  if (rel === "family_parents") return n === 5 ? "family_3gen" : null;
  if (n === 1) return /업무|출장/.test(ty) ? "solo_office" : /스포츠|웰니스/.test(ty) ? "solo_hiker" : "solo_casual";
  if (n === 2) return rel === "friend" ? "friends_2f" : rel === "spouse" ? "couple_vacation" : "couple_smart";
  return null;
}
function agPortrait(pid, n) { const cp = agComp(pid, n); return cp.av && AG.avm && AG.avm[cp.av] ? `/static/avatars/${cp.av}_portrait.png` : null; }
// 여러 명 지도 마커 — 초상(있으면) + 활동색 테두리 + ID. 고른 고객은 크게 · 붉은 테두리
function agMarkerSvg(id, x, y, k, cat, on, extra = "") {   // CL-1024-13 — 기본: 흰 알약 + 진한 ID(가운데 정렬 · 활동은 테두리 색) / 고른 고객: 초상 + 붉은 테두리(이름표는 따로)
  const V = agVC(id), col = (AG_CAT[cat] || AG_CAT.room).color, lab = dnoS(id);
  if (!on) {
    const h = 18 * k, w = (lab.length * 6.8 + 12) * k;
    return `<g class="ag-pin ag-mk${AG.sel ? " dim" : ""}" data-p="${id}" style="--vc:${col}"><rect class="ag-mk-ring" x="${(x - w / 2).toFixed(1)}" y="${(y - h / 2).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="${(h / 2).toFixed(1)}" fill="#fff" stroke="${col}" stroke-width="${(2.2 * k).toFixed(2)}"/><text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" class="ag-mk-n" style="font-size:${(10.5 * k).toFixed(2)}px">${esc(lab)}</text><circle class="ag-dot ag-hit" cx="${x}" cy="${y}" r="${Math.max(w / 2, 11 * k).toFixed(1)}" style="fill:transparent;stroke:none"/>${extra}</g>`;
  }
  const src = agPortrait(id, V.party), r = 20.2 * k;   // CL-1024-14 — 고른 고객 6% 크게(19 → 20.2)
  const face = src ? `<circle cx="${x}" cy="${y}" r="${r}" fill="#fff"/><image href="${src}" x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" preserveAspectRatio="xMidYMin slice" clip-path="url(#agClipC)"/>`
    : `<circle cx="${x}" cy="${y}" r="${r}" fill="#fff"/><text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" class="ag-mk-n" style="font-size:${11 * k}px">${esc(lab)}</text>`;
  return `<g class="ag-pin ag-mk on" data-p="${id}" style="--vc:${col}">${face}<circle class="ag-mk-ring" cx="${x}" cy="${y}" r="${r}" fill="none" stroke="var(--c-key)" stroke-width="${3 * k}"/><circle class="ag-mk-act" cx="${x + r * 0.72}" cy="${y + r * 0.72}" r="${5 * k}" fill="${col}" stroke="#fff" stroke-width="${1.6 * k}"/><circle class="ag-dot ag-hit" cx="${x}" cy="${y}" r="${Math.max(r, 11 * k)}" style="fill:transparent;stroke:none"/>${extra}</g>`;
}
// 같은 곳 3명 이상 = 인원 집합 — 모든 집합 같은 크기 · 숫자 정확히 가운데(dominant-baseline) · 활동 종류는 바깥 고리 비율
function agClusterSvg(loc, ids, cats, x, y, k, open) {
  const n = ids.length, r = 15 * k, R = r + 2.6 * k, cnt = {}; cats.forEach(c => cnt[c] = (cnt[c] || 0) + 1);
  let a0 = -Math.PI / 2, arcs = "";
  AG_CAT_ORDER.filter(c => cnt[c]).forEach(c => { const m = cnt[c], a1 = a0 + 2 * Math.PI * m / n, large = a1 - a0 > Math.PI ? 1 : 0;
    arcs += m === n ? `<circle cx="${x}" cy="${y}" r="${R}" fill="none" stroke="${AG_CAT[c].color}" stroke-width="${3.6 * k}"/>`
      : `<path d="M${(x + R * Math.cos(a0)).toFixed(2)},${(y + R * Math.sin(a0)).toFixed(2)} A${R},${R} 0 ${large} 1 ${(x + R * Math.cos(a1)).toFixed(2)},${(y + R * Math.sin(a1)).toFixed(2)}" fill="none" stroke="${AG_CAT[c].color}" stroke-width="${3.6 * k}"/>`; a0 = a1; });
  return `<g class="ag-clu${open ? " open" : ""}" data-loc="${loc}"><circle class="ag-clu-bg" cx="${x}" cy="${y}" r="${r}" fill="#2b2420"/>${arcs}<text class="ag-clu-n" x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" style="font-size:${(n > 9 ? 12.5 : 13.5) * k}px">${n}</text><circle class="ag-hit" cx="${x}" cy="${y}" r="${R + 2 * k}" style="fill:transparent;stroke:none"/><title>${esc(String(loc).startsWith("MV:") ? "이동 중" : agPlaceName(loc, AG.res))} · ${n}명 — 누르면 펼침</title></g>`;
}
// 지도 이름표 — 마커 · 집합과 겹치는 시설 이름표는 비켜 그린다(겹침 집합이 바뀔 때만 다시 그림), 그래도 겹치면 옅게
function agManyLabels() {
  if (typeof drawLabels !== "function" || typeof LABSHIFT === "undefined") return;
  const boxes = $$("#agent .ag-mk, #agent .ag-clu, #agent .ag-seltag").map(g => { try { const b = g.getBBox(); return [b.x - 2, b.y - 2, b.x + b.width + 2, b.y + b.height + 2]; } catch (e) { return null; } }).filter(Boolean);
  const hitOf = t => { let b; try { b = t.getBBox(); } catch (e) { return false; } return boxes.some(q => !(b.x + b.width < q[0] || b.x > q[2] || b.y + b.height < q[1] || b.y > q[3])); };
  const names = $$("#labels .lab").filter(hitOf).map(t => t.dataset.name).sort(), key = names.join("|");
  if (key !== AG.labKey) { AG.labKey = key; LABSHIFT.clear(); LABLINE = boxes.flatMap(q => [[q[0], q[1]], [q[2], q[1]], [q[0], q[3]], [q[2], q[3]], [(q[0] + q[2]) / 2, (q[1] + q[3]) / 2]]); names.forEach(n => LABSHIFT.add(n)); drawLabels(); }
  $$("#labels .lab").forEach(t => t.classList.toggle("ag-under", hitOf(t)));
}
// ---------------------------------------------------------------- 여러 명 오른쪽 운영 패널(§3) — A 현황 · (선택 고객) · D 주요 결정 · B 시설별 활동 · C 행동 피드 · E 방문 조건(접힘)
const AG_TDUR = t => ({ breakfast: 60, event: 75, dinner: 90 })[t] || 60;
function agTurnAt(T) { for (let i = 0; i < AG.runs.length; i++) { const t0 = agMin(AG.runs[i].time); if (t0 != null && T >= t0 - 0.01 && T <= t0 + AG_TDUR(AG.runs[i].turn)) return i; } return -1; }
function agNextTurn(T) { let best = -1; AG.runs.forEach((r, i) => { const t0 = agMin(r.time); if (t0 > T + 0.01 && (best < 0 || t0 < agMin(AG.runs[best].time))) best = i; }); return best; }
const agVenueName = (R, v) => v === "ROOM_MEAL" ? (R.turn === "breakfast" ? "객실 조식" : "객실 식사(룸서비스)") : v === "ROOM" ? (R.turn === "event" ? "객실 휴식" : R.turn === "breakfast" ? "아침 건너뜀" : "저녁 건너뜀") : v === "FOREST" ? "와인페어 · 포레스트 파크" : v === "SKYARD" ? "족욕 · 스카이야드" : ((R.customers.find(x => x.choice.venue_id === v) || {}).choice || {}).venue_label || AG_VEN_KO[v] || v;
const AG_VEN_KO = { PIZZA_HILL: "피자힐", MYONGWOLGWAN: "명월관", ONDAL: "온달", GEUMRYONG: "금룡", THE_BUFFET: "더뷔페", LE_PASSAGE: "르 파사쥬", POOL: "수영장", SAUNA: "사우나", NONE: "결정 없음" };
const agChip = id => `<button type="button" class="ag-idc${AG.sel === id ? " on" : ""}" data-p="${esc(id)}">${agPortrait(id, agVC(id).party) ? `<img src="${agPortrait(id, agVC(id).party)}" alt="">` : ""}${esc(dno(id))}</button>`;
const agThumb = loc => { const im = loc === "HOTEL_GATE" || loc === "ARRIVAL" ? agArrivalImage() : typeof placeImg === "function" ? placeImg(loc) : null; return im ? `<img class="ag-th" src="${im.src}" alt="" loading="lazy">` : `<span class="ag-th ag-th0"></span>`; };
const agFactorName = f => String(f || "").replace(/\s*\([^)]*\)\s*$/, "").replace(/ · /g, "·");
function agDecisionBlock(ti, T) {   // CL-12 §2 — 주요 소비 결정: 업장 · 상품 · 가격 · 주된 이유 · 비교 대안 · 바뀐 고객(고객 명단은 드로어에서)
  const R = AG.runs[ti]; if (!R) return "";
  const by = {}; R.customers.forEach(c => { const v = c.choice.venue_id; const o = by[v] = by[v] || { v, loc: c.choice.map_loc, cs: [], prods: {}, price: null };
    o.cs.push(c); const pl = agShort(c.choice.product_label); o.prods[pl] = (o.prods[pl] || 0) + 1; const pr = c.choice.price; if (pr && o.price == null) o.price = pr.paid_krw != null ? pr.paid_krw : pr.pp_krw; });
  const rows = Object.values(by).sort((a, b) => b.cs.length - a.cs.length);
  const venues = new Set(); R.customers.forEach(c => { venues.add(c.choice.venue_id); c.not_chosen.forEach(o => o.feasible && venues.add(o.venue_id)); });
  const vn = [...venues].map(v => agVenueName(R, v).replace(/\(.*\)/, "").split(" · ")[0]).join(" · ");
  const why = cs => { const m = {}; cs.forEach(c => { const rv = c.reasons.filter(r => r.parts.review > 0.01).sort((a, b) => b.parts.review - a.parts.review)[0]; const k = rv ? agFactorName(rv.factor) : "가격 · 기본 조건"; m[k] = (m[k] || 0) + 1; }); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([k, n]) => `${k}${cs.length > 1 ? ` ${n}` : ""}`).join(" · "); };
  const alt = cs => { const m = {}; let near = 0; cs.forEach(c => { const o = c.best_other_venue; if (!o) return; m[o.venue_id] = (m[o.venue_id] || 0) + 1; if (o.margin < 0.15) near++; }); const top = Object.entries(m).sort((a, b) => b[1] - a[1])[0]; return top ? `${agVenueName(R, top[0]).split(" · ")[0].replace(/\(.*\)/, "")}${near ? ` · 근소 ${near}명` : ""}` : "—"; };
  const chg = R.compare ? R.compare.customers.filter(c => c.status === "changed") : [];
  const ev = R.turn === "event" ? (() => { const yes = (by.FOREST || { cs: [] }).cs.length;
    if (R.engine === "autonomy_v1") { const st = Object.values((AG.flow && AG.flow.stories) || {}); const chk = st.filter(x => /^행사 안내만/.test(x.cls)).length, off = st.length ? st.length - yes - chk : null;   // 새 엔진: 행사 턴에는 참여한 고객만 있으므로 안내만 확인 · 그 밖은 이야기에서 센다
      return `<div class="dc-sum"><b>참여 ${yes}명</b><span>${chk ? `안내만 확인 ${chk}명 · ` : ""}${off != null ? `참여 안 함 ${off}명` : ""}</span></div>`; }
    return `<div class="dc-sum"><b>참여 ${yes}명</b><span>불참 ${R.customers.length - yes}명</span></div>`; })() : `<div class="dc-sum"><b>${R.customers.length}명</b><span>이 시각 결정</span></div>`;
  const active = T != null && agTurnAt(T) === ti;
  return `<section class="ops-blk ops-dc${active ? " on" : ""}"><div class="ops-h"><b>${esc(R.time || "")} ${AG_TURN[R.turn]} · 주요 소비 결정</b>${noteH({ what: "정량 엔진이 계산한 주요 소비 선택입니다. 업장마다 고른 인원 · 대표 상품 · 1인 가격 · 주된 이유(가장 크게 작용한 후기 근거 항) · 비교 대안을 요약합니다. 고객별 선택과 점수는 '고객별 선택 · 근거'에서 봅니다.", basis: ["운영 조건 · 계산", "실제 후기"], basis_note: `이번 비교 후보 업장: ${vn}`, caution: "인원은 시뮬레이션 고객 수이며 수요 예측이 아닙니다. 근소 = 다른 업장 대안과 점수 차 0.15 미만 — 강한 선호로 보지 않습니다." })}</div>
    ${ev}${chg.length ? `<div class="dc-cmp chg">운영 조건 변경으로 <b>${chg.length}명</b> 바뀜 · ${chg.map(c => `${esc(dno(c.persona_id))} ${esc(agShort(c.before.product_label))} → ${esc(agShort(c.after.product_label))}`).join(" · ")}</div>` : R.compare ? `<div class="dc-cmp">운영 조건을 바꿨지만 이 결정에서 바뀐 고객은 없음</div>` : ""}
    <div class="dc-rows">${rows.map(r => `<div class="dc-row" style="--vc:${agVColor(r.v)}">${agThumb(r.v === "FOREST" ? "FOREST_PARK" : r.loc)}<div class="dc-b"><div class="dc-t"><b>${esc(agVenueName(R, r.v))}</b><em>${r.cs.length}명</em></div>
      <dl class="dc-dl"><div><dt>상품</dt><dd>${esc(Object.entries(r.prods).sort((a, b) => b[1] - a[1]).map(([p, n]) => `${p}${n > 1 ? ` ${n}` : ""}`).join(" · "))}${r.price != null ? ` · 1인 ${agWon(r.price)}` : ""}</dd></div><div><dt>주된 이유</dt><dd>${esc(why(r.cs))}</dd></div><div><dt>비교 대안</dt><dd>${esc(alt(r.cs))}</dd></div></dl></div></div>`).join("")}</div>
    <div class="dc-f"><button type="button" class="linkbtn" data-dr="${ti}">고객별 선택 · 근거 보기 ›</button></div></section>`;
}
function agCohortTransitHTML(pid,T,p) {
  const V=agVC(pid),next=agScenes(pid).filter(sc=>sc.k!=='move'&&sc.t0>T).slice(0,2),target=p.to||p.sc,im=agBRImage(target,pid),title=p.away==='pre'?'도착 전':p.away==='post'?'방문 종료':p.moving&&target?.loc?'이동 → '+agPlaceName(target.loc,AG.res):'이동 중';
  return `<div class="frp-cohort-selected" id="agSelH"><div class="frp-cohort-selection"><b>${esc(dno(pid))}</b><button class="rp-link" id="agSelOff">전체 현황으로 →</button></div><section class="frp-brief"><section class="frp-section frp-current"><div class="frp-current-meta"><span>${esc(dno(pid))} · ${AG.visitDay||1}일차</span><time>${agHM(T)}</time></div>${im?`<div class="frp-current-media"><img class="frp-current-thumb" src="${im.src}" alt="${esc(im.name)}" width="1600" height="900"></div>`:''}<h2>${title}</h2><span class="frp-place">${p.moving?esc(agPlaceName(target.loc,AG.res))+' 방향':p.away==='pre'?'방문 시작 전':'오늘의 방문 일정 종료'}</span></section><section class="frp-section frp-schedule"><h3>다음 일정</h3>${next.length?`<ol>${next.map(sc=>`<li><time>${agHM(sc.t0)}</time>${agReadableHTML(agScLabel(sc,pid),agReadingKey(pid,sc,'next-label'),2)}</li>`).join('')}</ol>`:'<p class="frp-note">오늘의 일정이 끝났습니다.</p>'}<button class="rp-link" data-frp-customer="${esc(pid)}" data-frp-customer-tab="day">전체 일정 보기 →</button></section>${agBRCompanion(pid)}<div class="frp-receipt-slot" data-frp-receipt-slot></div></section></div>`;
}
function agSelCard(id, T) {
  const L = agScenes(id), p = agManyPos(id, T), V = agVC(id), cp = agComp(id, V.party);
  const nowSc = p && !p.away ? (p.moving ? p.to : p.sc) : null, i0 = nowSc ? L.indexOf(nowSc) : -1;
  if(p&&(p.moving||p.away))return agCohortTransitHTML(id,T,p);
  const nexts = (p && p.away === "pre" ? L : L.slice(i0 + 1)).filter(x => x.k !== "move" && x !== nowSc).slice(0, 3);
  if(nowSc&&!p.moving){const current=agCustOf(AG.runs[nowSc.ti]||AG.res,id)||agAnyCust(id);if(current)return `<div class="ops-sel frp-cohort-selected" id="agSelH"><div class="frp-cohort-selection"><b>${esc(dno(id))}</b><button class="rp-link" id="agSelOff">전체 현황으로 →</button></div>${agBRCard(current,nowSc)}</div>`;}
  const nowTxt = !p ? "" : p.away === "pre" ? `아직 도착 전 · ${agHM(p.sc.t0)} ${esc(agScLabel(p.sc, id))}부터` : p.away === "post" ? `${agHM(p.sc.t1)} ${esc(agScLabel(p.sc, id))} · 방문 종료` : p.moving ? `${esc(agRo(agPlaceName(p.to.loc, AG.runs[p.to.ti])))} 이동 중 · ${esc(agScLabel(p.to, id))}` : `${esc(agScLabel(p.sc, id))} · ${esc(agPlaceName(p.sc.loc, AG.runs[p.sc.ti]))}`;
  const cat = p && !p.away ? (p.moving ? "move" : agCatOf(p.sc, id)) : "stay";
  return `<section class="ops-blk ops-sel" id="agSelH"><div class="sel-h">${agAvatarIcon(id, V.party, 44)}<div class="sel-b"><div class="sel-t"><b>${esc(dno(id))}</b><span>${esc(cp.label)}</span><button type="button" class="linkbtn" id="agSelOff">선택 해제</button></div>${V.v ? `<div class="sel-v">${esc(agVisitShort(id))}</div>` : ""}</div></div>
    <div class="sel-now" style="--vc:${(AG_CAT[cat] || AG_CAT.room).color}"><span class="sel-k">지금</span><span>${nowTxt}</span>${nowSc && nowSc.k === "turn" ? `<button type="button" class="linkbtn" data-ch="${id}|${nowSc.ti}">선택 이유 ›</button>` : ""}</div>
    ${nowSc&&nowSc.k==='turn'?agSelWhy(id):`${agUXMultiReasons(id,nowSc)}<details class="sel-more"><summary>이 방문의 식사·행사 주요 결정</summary>${agSelWhy(id)}</details>`}
    ${nexts.length ? `<ol class="sel-next">${nexts.map(x => `<li${x.k === "turn" ? ' class="key"' : ""}><time>${agHM(x.t0)}</time><span>${esc(agScLabel(x, id))}</span><small>${esc(agPlaceName(x.loc, AG.runs[x.ti]))}</small></li>`).join("")}</ol>` : ""}
    ${(() => { const st = agStory(id); return st ? `<details class="sel-story"${AG.flow && AG.flow.stories && AG.flow.stories[id] && !AG.flow.stories[id].keep_reason ? " open" : ""}><summary>운영 변경 반응 · ${esc(AG.flow.stories[id].cls.split(" · ")[0])}</summary>${st}</details>` : ""; })()}
    <div class="sel-f"><button type="button" class="rp-link" data-cd="${id}">고객 상세 ›</button><span class="hint">아래 시간축에 이 고객의 하루가 표시됩니다</span></div></section>`;
}
// CL-1025-37 P2 — 여러 명에서 고른 고객: 성향(후기 근거로 측정된 것만) · 이번 주요 결정(선택 · 다음 대안 · 후기 몫/공통 계산) · 근거 패널 열기
function agSelWhy(id) {
  const ds = AG.runs.map((R, ti) => ({ R, ti, c: R.customers.find(x => x.persona_id === id) })).filter(x => x.c);
  if (!ds.length) return "";
  const bars = ((ds[0].c.persona || {}).bars || []).filter(b => b.status === "observed").sort((a, b) => b.level - a.level).slice(0, 2);
  const row = ({ R, ti, c }) => { const o = c.best_other_venue, T = c.reason_totals || {}, rv = T.review || 0;
    return `<li><b>${esc(AG_TURN[R.turn] || R.turn)}</b><span class="sw-c">${esc(agChoiceName(R, c.choice))}</span><span class="sw-m">${o ? `다음 대안 ${esc(agShort(o.product_label))} · 차 ${agNum(o.margin)}${o.margin < 0.15 ? " · 근소" : ""}` : ""}</span><span class="sw-s ${rv > 0.05 ? "rv" : ""}">${Math.abs(rv)>1e-6 ? `후기 기여 ${agU06Signed(rv)}` : "후기 기여 항 없음"}</span><button type="button" class="linkbtn" data-ch="${esc(id)}|${ti}">근거 ›</button></li>`; };
  return `<div class="sel-why">${bars.length ? `<div class="sel-tr"><span class="sel-k">성향</span>${bars.map(b => `<i>${esc(b.label)}</i>`).join("")}<em>후기 근거로 측정</em></div>` : `<div class="sel-tr"><span class="sel-k">성향</span><em>후기 근거로 측정된 성향 없음</em></div>`}
    ${(() => { const f = ds.find(x => x.ti === AG.ti) || ds.find(x => x.R.turn === "event") || ds[ds.length - 1], rest = ds.filter(x => x !== f);
      return `<ol class="sel-dec">${row(f)}</ol>${rest.length ? `<details class="sel-more"><summary>이 고객의 다른 결정 ${rest.length}개</summary><ol class="sel-dec">${rest.map(row).join("")}</ol></details>` : ""}`; })()}</div>`;
}
function agFeedGroup(F) {   // 같은 시각 같은 턴의 결정은 한 줄로("16:30 행사 결정 11명 · 와인페어 3 · 족욕 8")
  const out = [], seen = {};
  F.forEach(e => { if (!e.key) return out.push(e); const R = AG.runs.find(r => agMin(r.time) === e.t); const k = e.t + "|" + (R ? R.turn : ""); if (seen[k]) { seen[k].ids.push(e.id); return; }
    const g = { t: e.t, key: true, cat: e.cat, ids: [e.id], R }; seen[k] = g; out.push(g); });
  out.forEach(g => { if (!g.ids) return; const R = g.R; if (!R) { g.txt = "주요 결정"; return; } const m = {}; R.customers.filter(c => g.ids.includes(c.persona_id)).forEach(c => { const v = agVenueName(R, c.choice.venue_id).split(" · ")[0].replace(/\(.*\)/, ""); m[v] = (m[v] || 0) + 1; });
    g.txt = `${AG_TURN[R.turn]} 결정 · ${Object.entries(m).sort((a, b) => b[1] - a[1]).map(([v, n]) => `${v} ${n}`).join(" · ")}`; });
  return out;
}
function agCohortNextHTML(T) {
  const upcoming=agAllIds().flatMap(pid=>agScenes(pid).filter(sc=>sc.k==='turn'&&sc.t0>T+.01).map(sc=>({pid,sc}))).sort((a,b)=>a.sc.t0-b.sc.t0),groups=[];
  for(const item of upcoming){const key=item.sc.t0+'|'+agScLabel(item.sc,item.pid);let group=groups.find(g=>g.key===key);if(!group){if(groups.length===2)break;group={key,...item,ids:[]};groups.push(group);}group.ids.push(item.pid);}
  return `<section class="frp-section frp-cohort-next" data-cohort-section="next"><h3>다음 주요 일정</h3>${groups.length?groups.map(g=>`<div class="frp-cohort-next-row"><time>${agHM(g.sc.t0)}</time><div>${agReadableHTML(agScLabel(g.sc,g.pid),agReadingKey(g.pid,g.sc,'cohort-next'),2)}<div class="dc-ids">${g.ids.map(agChip).join('')}</div></div></div>`).join(''):'<p class="frp-note">오늘 남은 주요 결정이 없습니다.</p>'}</section>`;
}
function agOpsPanel(T, O) {
  const el=$('#panel');if(!el||!AG.res)return;
  if(T==null)T=AG.manyT!=null?AG.manyT:agMin(AG.res.time)||0;
  O=O||agOpsAt(T);const count=k=>(O.byCat[k]||[]).length;
  const stat=(kind,value,label)=>`<div data-live-stat="${kind}" data-count="${value}"><b>${value}</b><span>${label}</span></div>`;
  const summary=`<section class="frp-section frp-cohort-now" data-cohort-section="now"><div class="frp-section-heading"><h3>현재 요약</h3><time>${agHM(T)}</time></div><p class="frp-note">현재 실행 · ${agTeamSummary()}</p><div class="frp-live-stats">${stat('teams',agAllIds().length,'고객 팀')}${stat('people',agAllIds().reduce((n,id)=>n+(agVC(id).party||0),0),'방문 인원')}${stat('moving',O.moving.length,'이동 팀')}${stat('room',count('room'),'객실 팀')}</div><div class="frp-chips"><span>체류 중 <b class="${O.present.length?'frp-live-present':'frp-live-zero'}">${O.present.length}</b>팀</span>${O.pre.length?`<span>도착 전 ${O.pre.length}팀</span>`:''}${O.post.length?`<span>방문 종료 ${O.post.length}팀</span>`:''}</div></section>`;
  const facilities=`<section class="frp-section frp-cohort-facilities" data-cohort-section="facilities"><h3>시설별 고객</h3>${Object.values(O.byLoc).filter(g=>g.ids.length).map(g=>`<article class="frp-facility"><div class="frp-facility-heading">${agThumb(g.loc)}<div><b>${esc(agPlaceName(g.loc,AG.res))}</b><small>${g.ids.length}팀</small></div></div>${agReadableHTML(Object.entries(g.acts).map(([name,n])=>name+(n>1?' · '+n+'팀':'')).join(' · '),JSON.stringify([AG.flow&&AG.flow.ledger.run_id,AG.visitDay,g.loc,JSON.stringify(g.acts)]),2)}<div class="dc-ids">${g.ids.map(agChip).join('')}</div></article>`).join('')}${O.moving.length?`<article class="frp-facility"><b>이동 중 · ${O.moving.length}팀</b><div class="dc-ids">${O.moving.map(([pid])=>agChip(pid)).join('')}</div></article>`:''}${!O.present.length?'<p class="frp-note">현재 호텔 안에 머무는 고객이 없습니다.</p>':''}</section>`;
  const feed=agFeedGroup(agFeed(T,150,14)).slice(0,7),recent=`<section class="frp-section frp-cohort-recent" data-cohort-section="recent"><h3>최근 행동</h3>${feed.length?`<ol>${feed.map(e=>`<li><time>${agHM(e.t)}</time><div><div class="dc-ids">${e.ids?e.ids.map(agChip).join(''):agChip(e.id)}</div>${agReadableHTML(e.txt,JSON.stringify([AG.flow&&AG.flow.ledger.run_id,AG.visitDay,e.ids||e.id,e.t,e.cat,e.txt,'feed']),2)}</div></li>`).join('')}</ol>`:'<p class="frp-note">최근 2시간 사이 시작한 활동이 없습니다.</p>'}</section>`;
  const selected=AG.sel&&agAllIds().includes(AG.sel)?agSelCard(AG.sel,T):'',keep=el.scrollTop;
  el.innerHTML=`<div class="ops frp-cohort">${selected||summary+agCohortNextHTML(T)+facilities+recent}</div>`;
  if(typeof rcMountPanel==='function')rcMountPanel();agU06PanelChrome();el.scrollTop=keep;
  $$('#panel [data-p]').forEach(b=>b.onclick=event=>{event.stopPropagation();agSelect(b.dataset.p);});
  $$('#panel [data-cd]').forEach(b=>b.onclick=()=>agCustDrawer(b.dataset.cd));
  $$('#panel [data-ch]').forEach(b=>b.onclick=()=>{const [pid,ti]=b.dataset.ch.split('|');agChoiceDrawer(pid,+ti);});
  const back=$('#agSelOff');if(back)back.onclick=()=>{AG.sel=null;if(AG.keep[AG.mode])AG.keep[AG.mode].sel=null;agManyRender(AG.manyT);agStrip();const right=$('#right');if(right)right.scrollTop=0;};
}
function agManyRender(T) { if (T == null) return; AG.manyT = T; AG.nowMin = T; const ti = agTurnAt(T); if (ti >= 0 && ti !== AG.ti) { AG.ti = ti; AG.res = AG.runs[ti]; } AG._opsAt = 0; agManyDraw(T); agClock(); agStripNow(T); }
function agManyJump(T) { agManyStop(); AG.paused = !!AG.manyHeld; agManyRender(T); agStripState(); }
const agQ = (root, s) => Array.from((root || document).querySelectorAll(s));
// ---------------------------------------------------------------- 드로어(§6) — 페이지 이동 없이 상세. 열 때 재생 중이면 잠시 멈추고, 닫으면 같은 자리에서 이어서 재생
if (typeof openDrawer === "function" && typeof closeDrawer === "function" && !window._agDrWrapped) {
  window._agDrWrapped = true;
  const _od = openDrawer, _cd = closeDrawer;
  openDrawer = function (...a) { const inAg = document.querySelector(".mode-agent:not(.hidden)") && AG.res; if (inAg && AG.playing) { AG._drResume = true; agPause(); } return _od.apply(this, a); };
  closeDrawer = function (...a) { const r = _cd.apply(this, a); if (AG._drResume) { AG._drResume = false; if (!AG.playing && AG.res) agPlayToggle(); } return r; };
}
const agTabs = (tabs, act) => `<div class="dr-tabs" role="tablist">${tabs.map(([k, t]) => `<button type="button" role="tab" data-tab="${k}" class="${k === act ? "on" : ""}">${t}</button>`).join("")}</div>`;
const agTabWire = root => { agQ(root, ".dr-tabs [data-tab]").forEach(b => b.onclick = () => { agQ(root, ".dr-tabs [data-tab]").forEach(x => x.classList.toggle("on", x === b)); agQ(root, "[data-pane]").forEach(p => p.classList.toggle("hidden", p.dataset.pane !== b.dataset.tab)); }); };
const agLibP = pid => (typeof libP === "function" && typeof LIBV !== "undefined" && LIBV.data ? libP(pid) : null);
const AG_KIND_KO = { purchase: "구매 · 소비", participation: "이용 · 참여", appraisal: "평가", motive: "동기", expectation: "기대 · 다음 관심", decline: "거절 · 안 함", preference: "선호" };
function agResolvedConditionsHTML(pid) {
  const flow=AG.flow,visit=flow&&flow.result.visit,resolved=visit&&visit.resolved_conditions&&visit.resolved_conditions[pid];if(!resolved)return '';
  const declared=flow.request&&flow.request.visit_conditions&&flow.request.visit_conditions[pid],composition=resolved.party_composition;
  return `<details class="rc-resolved"><summary>실제 적용된 방문 조건</summary><p>방문 설정 ${resolved.party_size}명 · ${composition?'성인 '+composition.adult_count+'명 / 아동 '+composition.children.length+'명':'연령 구성 UNKNOWN (미지정)'}</p><p class="frp-note">${declared?'명시값은 이번 방문의 가상 설정입니다.':'직접 입력하지 않은 상세 정보는 UNKNOWN으로 유지합니다.'}</p></details>`;
}
function agCustDrawer(pid, tab = "ov") {
  const p = (AG.meta.personas || []).find(x => x.id === pid), lp = agLibP(pid) || {}, V = agVC(pid), cp = agComp(pid, V.party), pt = agPortrait(pid, V.party);
  const seenG = new Set(), F = Object.entries((lp.engine && lp.engine.facts) || {}).filter(([, f]) => !f.hidden && f.gist && !seenG.has(f.gist) && seenG.add(f.gist)).map(([id, f]) => Object.assign({ id }, f));   // 같은 요지(사건 분할 사실) 한 번만
  const whF = F.filter(f => f.wh), cons = whF.filter(f => ["purchase", "participation"].includes(f.kind)).slice(0, 5), dec = F.filter(f => f.kind === "decline").slice(0, 3);
  const counters = (lp.traits || []).flatMap(t => (t.counter || []).map(c => ({ t: t.trait, c }))).slice(0, 3);
  const rules = (lp.rules || []).slice(0, 3);
  const L = AG.res ? agScenes(pid) : [], T = AG.manyT != null && agIsMany(AG.res) ? AG.manyT : AG.nowMin;
  // 방문 실행은 날짜별 시간축을 이어서 보이되, 날짜 경계와 체류 단계를 분리해 표시한다.
  let previousVisitDay = null;
  const day = L.filter(x => x.k !== "move").map(x => { const cat = agCatOf(x, pid), now = T != null && T >= x.t0 && T < x.t1, key = x.k === "turn", R = AG.runs[x.ti], c = key && R ? agCustOf(R, pid) : null;
    const boundary = x.visit_day != null && x.visit_day !== previousVisitDay ? `<li class="cd-day-head">${x.visit_day}일차 · ${esc(x.visit_date || "날짜 미확인")} · ${esc(({checkin:"체크인",mid:"연박",checkout:"체크아웃",visit:"당일 방문"})[x.day_phase] || "방문")}</li>` : "";
    if (x.visit_day != null) previousVisitDay = x.visit_day;
    const what = key && c ? agTurnAct(R, c.choice) : agScLabel(x, pid), quiet = !key && ["rest"].includes(x.kind);
    return `${boundary}<li class="${key ? "key" : ""}${now ? " now" : ""}${quiet ? " quiet" : ""}" style="--vc:${AG_CAT[cat].color}" tabindex="0" ${key ? `data-ch="${pid}|${x.ti}"` : `data-act="${x.si}"`}><time>${agHM(x.t0)}</time><i class="cd-dot"></i><div class="cd-b"><div class="cd-t"><b>${esc(what)}</b>${key ? `<em class="cd-key">주요 결정</em>` : x.src === "review" ? `<em class="cd-rv">후기 경험</em>` : ""}</div><small>${esc(agPlaceName(x.loc, R))} · ${Math.round(x.t1 - x.t0)}분</small>${x.why && !quiet ? `<p>${esc(x.why)}</p>` : ""}</div><span class="cd-go">›</span></li>`; }).join("");
  const compactScenes=L.filter(x=>x.k!=='move'), currentIndex=Math.max(0,compactScenes.findIndex(x=>x.si===AG.si)), shortDay=compactScenes.slice(currentIndex,currentIndex+4).map(x=>`<li data-act="${x.si}" tabindex="0"><time>${agHM(x.t0)}</time><span>${esc(agScLabel(x,pid))}</span></li>`).join('');
  const ov=`<div class="cd-sec"><h4>이번 방문에서 보는 고객</h4><div class="ux-customer-chips">${p?p.bars.filter(b=>b.status==='observed').slice(0,3).map(b=>`<span>${esc(b.label)}</span>`).join(''):''}</div><h4>선택한 행동과 다음 일정</h4><ol class="cd-day frp-short-day">${shortDay}</ol>${agResolvedConditionsHTML(pid)}<p class="hint">전체 일정은 ‘오늘 일정’, 과거 후기 자료는 ‘후기 근거’에서 확인합니다.</p></div>`;
  const viewScene=AG.mode==='agent'&&AG.one===pid?agScene():null,viewCustomer=agCustOf(AG.res,pid)||agAnyCust(pid);
  const evidenceFacts=agBRFacts(pid,viewCustomer,viewScene,true);
  const ev = `<h3 class="frp-drawer-title">후기 근거</h3><label class="ux-drawer-search">후기 사실 검색<input type="search" id="uxDrawerSearch" placeholder="행동·장소·Fact ID"></label>${agBRFactCards(pid,evidenceFacts,viewScene&&viewScene.si).replace('class="frp-fact-cards"','class="cd-list cd-ev frp-fact-cards"')}`;
  const nights=AG.flow&&AG.flow.result.visit&&AG.flow.result.visit.nights,stayText=nights!=null?(nights?`${nights}박 ${nights+1}일`:'당일 방문'):(V.stay?'숙박 방문':'당일 방문');
  const head = `<div class="cd-head frp-customer-head">${pt?`<img class="cd-pt" src="${pt}" alt="">`:`<span class="cd-pt cd-pt0">${agAvatarIcon(pid,V.party,52)}</span>`}<div><div class="cd-id"><b>${esc(dno(pid))}</b><span>${esc(lp.type_group||lp.type||'')}</span></div><p class="frp-person-intro">${esc(lp.label||cp.label||'현재 방문 조건으로 보는 고객')}</p><div class="frp-chips"><span>${esc(cp.label||V.party+'명')}</span><span>${esc(stayText)}</span>${V.stay&&V.bl?`<span>${esc(V.bl)}</span>`:''}${p?p.bars.filter(b=>b.status==='observed').slice(0,2).map(b=>`<span>${esc(b.label)}</span>`).join(''):''}</div><p class="frp-avatar-note">동행 인원과 특징을 요약한 시각 표현입니다.</p></div></div>`;
  const h = head + agTabs([["ov", "개요"], ["day", "오늘 일정"], ["ev", "후기 근거"]], tab) +
    `<div data-pane="ov"${tab === "ov" ? "" : ' class="hidden"'}>${ov}</div><div data-pane="day"${tab === "day" ? "" : ' class="hidden"'}><ol class="cd-day">${day || `<li>실행 결과가 없습니다.</li>`}</ol>${AG.plans && AG.plans[pid] ? `<div class="hint">${esc(agPlanMetaText(AG.plans[pid]))}</div>` : ""}</div><div data-pane="ev"${tab === "ev" ? "" : ' class="hidden"'}>${ev}</div>
    <div class="cd-foot"><button type="button" class="linkbtn" id="cdLib">라이브러리에서 전체 프로파일 열기 ↗</button><span class="hint">시뮬레이션 화면을 떠납니다</span></div>`;
  openDrawer(`${dno(pid)} · 고객 상세`, lp.type_group || "", h, root => {
    agTabWire(root);
    const search=root.querySelector("#uxDrawerSearch");if(search)search.oninput=()=>root.querySelectorAll(".cd-ev li").forEach(li=>li.hidden=!li.textContent.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()));
    agQ(root, "[data-ch]").forEach(b => b.onclick = () => { const [id, t] = b.dataset.ch.split("|"); agChoiceDrawer(id, +t); });
    agQ(root, "[data-act]").forEach(b => b.onclick = () => agActDrawer(pid, +b.dataset.act));
    agQ(root, ".cd-day li").forEach(li => li.onkeydown = e => { if (e.key === "Enter") li.click(); });
    const lb = root.querySelector("#cdLib"); if (lb) lb.onclick = () => { AG._drResume = false; closeDrawer(); agToProfile(pid); };
  }, { wide: true });
}
function agChoiceDrawer(pid,ti) {
  const R=AG.runs[ti]||AG.res,c=R && R.customers.find(x=>x.persona_id===pid);if(!c)return;
  const keepR=AG.res,keepTi=AG.ti;AG.res=R;AG.ti=ti;let html;try{html=agTurnCard(c,true);}finally{AG.res=keepR;AG.ti=keepTi;}
  openDrawer(`${dno(pid)} · ${R.time} 선택`,'현재 방문의 행동 요약',html,root=>{
    root.querySelectorAll('[data-ux-reason]').forEach(b=>b.onclick=()=>{closeDrawer();bhFromFlow(pid,ti);});
    root.querySelectorAll('[data-pf]').forEach(b=>b.onclick=()=>{closeDrawer();agToProfile(pid);});
  },{});
}
function agDecisionDrawer(ti) {
  const R = AG.runs[ti]; if (!R) return;
  const rows = [...R.customers].sort((a, b) => a.choice.venue_id.localeCompare(b.choice.venue_id)).map(x => { const o = x.best_other_venue, cc = R.compare && R.compare.customers.find(y => y.persona_id === x.persona_id), chg = cc && cc.status === "changed";
    return `<li data-ch="${x.persona_id}|${ti}" tabindex="0">${agChip(x.persona_id)}<span class="dd-c">${agDot(x.choice.venue_id)}<b>${esc(agVenueName(R, x.choice.venue_id).split(" · ")[0])}</b> ${esc(agShort(x.choice.product_label))}${chg ? ` <em class="ag-chg">변경 · 전 ${esc(agShort(cc.before.product_label))}</em>` : ""}</span><span class="dd-a">${o ? `${o.margin < 0.15 ? '<em class="ag-near">근소</em> ' : ""}대안 ${esc((o.venue_label || agVenueName(R, o.venue_id)).split(" · ")[0])} · 차 ${agNum(o.margin)}` : ""}</span></li>`; }).join("");
  openDrawer(`${R.time} ${AG_TURN[R.turn]} · 고객별 선택`, `${R.customers.length}명 · 누르면 선택 상세`, `${agDecisionBlock(ti, null).replace(/<button type="button" class="linkbtn" data-dr="[^"]*">[^<]*<\/button>/, "")}<ul class="ag-dd">${rows}</ul>`, root => {
    agQ(root, "[data-ch]").forEach(li => li.onclick = ev => { if (ev.target.closest(".ag-idc")) return; const [id, t] = li.dataset.ch.split("|"); agChoiceDrawer(id, +t); });
    agQ(root, ".ag-idc").forEach(b => b.onclick = ev => { ev.stopPropagation(); agCustDrawer(b.dataset.p, "day"); });
  }, { wide: true });
}
function agActDrawer(pid, si) {   // CL-1024-13 — 활동 상세: 사진(있을 때) → 활동 · 장소 → 정의 목록(시간 · 분류) → 앞뒤 흐름 → 이유 → 구성 근거
  const L = agScenes(pid), sc = L.find(x => x.si === si); if (!sc) return;
  if (sc.k === "turn") return agChoiceDrawer(pid, sc.ti);
  if(sc.basis && sc.basis.m4) {
    const R=AG.runs[sc.ti]||AG.res,c=R && R.customers.find(x=>x.persona_id===pid);if(c){
      openDrawer(`${dno(pid)} · ${agHM(sc.t0)} ${sc.label}`,'현재 방문의 활동 요약',agU06ActivityCard(c,sc),root=>{root.querySelectorAll('[data-pf]').forEach(b=>b.onclick=()=>{closeDrawer();agToProfile(pid);});},{});return;
    }
  }
  const i = L.indexOf(sc), prev = L.slice(0, i).reverse().find(x => x.k !== "move"), next = L.slice(i + 1).find(x => x.k !== "move"), B = sc.basis || {};
  const im = agSceneImg(sc, pid), lp = agLibP(pid), facts = (B.facts || []).map(f => { const x = lp && lp.engine && lp.engine.facts[f]; return x && !x.hidden ? [f, x.gist] : null; }).filter(Boolean);
  const tl = (B.traits || []).map(k => AG_TRAIT_KO[k] || k).join(" · "), place = agPlaceName(sc.loc, AG.runs[sc.ti]);
  const row = (x, lab) => x ? `<li class="${x === sc ? "now" : ""}${x.k === "turn" ? " key" : ""}"><span class="ad-k">${lab}</span><time>${agHM(x.t0)}</time><b>${esc(agScLabel(x, pid))}</b><small>${esc(agPlaceName(x.loc, AG.runs[x.ti]))}</small></li>` : "";
  const h = `<div class="ad">
    ${im ? `<figure class="ad-img"><img src="${im.src}" alt="${esc(im.name)}"><figcaption>${esc(im.credit)}</figcaption></figure>` : ""}
    <div class="ad-head"><h3>${esc(sc.label)}</h3><p>${esc(place)} · ${agHM(sc.t0)}–${agHM(sc.t1)} (${Math.round(sc.t1 - sc.t0)}분)</p></div>
    <dl class="ad-dl"><div><dt>분류</dt><dd>${AG_CAT[agCatOf(sc, pid)].label}${sc.consume ? " · 이용 · 소비(가격 계산 없음)" : ""}</dd></div>
      <div><dt>근거</dt><dd>${sc.src === "review" ? "후기 경험 + 행동 계획기" : sc.k === "start" ? "방문 조건(시작)" : "행동 계획기 — 성향 · 동행 · 앞선 활동"}</dd></div>
      ${tl ? `<div><dt>작용한 성향</dt><dd>${esc(tl)}</dd></div>` : ""}${(B.cond || []).length ? `<div><dt>조건</dt><dd>${esc(B.cond.join(" · "))}</dd></div>` : ""}</dl>
    ${typeof agM4ActivityPanel === "function" ? agM4ActivityPanel(pid, sc) : ""}
    ${sc.why ? `<section class="ad-sec"><h4>왜 이 활동인가</h4><p>${esc(sc.why)}</p>${sc.cond_dep ? `<p class="ad-warn">운영 조건 변경 뒤 기준 조건의 하루와 달라진 장면입니다.</p>` : ""}</section>` : ""}
    <section class="ad-sec"><h4>앞뒤 흐름</h4><ol class="ad-flow">${row(prev, "앞")}${row(sc, "지금")}${row(next, "다음")}</ol></section>
    <section class="ad-sec"><h4>연결한 후기 사실</h4>${facts.length ? `<ul class="ad-facts">${facts.map(([f, g]) => `<li><p>${esc(g)}</p><small>${esc(f)} · 요지(원문 인용 아님)</small></li>`).join("")}</ul>` : `<p class="ad-mut">직접 연결된 후기 사실은 없습니다 — 성향 · 동행 · 앞선 활동 · 영업시간으로 구성했습니다.</p>`}</section>
    <p class="ad-mut">${esc(agPlanMetaText(AG.plans && AG.plans[pid]))}</p></div>`;
  openDrawer(`${dno(pid)} · ${agHM(sc.t0)} ${sc.short || sc.label}`, "활동 상세", h, root => {}, {});
}
function agPlanMetaText(pm) {
  if (!pm) return "행동 계획기 결과 없음";
  if(pm.trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_')){const t=pm.trace;return `${typeof HLVisitExecution!=='undefined'&&HLVisitExecution.isImproved(t.planner_backend)?'개선형 판단 기준':t.planner_backend} · 실제 API ${t.llm_calls||0}회 · 캐시 재생 ${t.llm_replays||0}회 · ${t.planner_backend_fallback_used?'규칙 폴백 포함':'규칙 폴백 없음'}`;}
  const used = pm.backend === "llm" ? "LLM 계획기" : "규칙 계획기", req = pm.requested === "auto" || pm.requested === "llm" ? "LLM 계획기" : "규칙 계획기";
  const st = pm.status && pm.status !== "ok" ? " · 실행 차단(월드 검증)" : "", t = pm.trace || {};
  const pf = t.profile_fallback_used ? " · 프로파일 미로드 — 일반 시연 계획" : t.daily_behavior_loaded ? " · 일상 행동 자료 사용" : "";
  return (req === used ? `실제 사용: ${used}` : `요청: ${req} · 실제 사용: ${used}${pm.fallback_reason ? ` · 대체 이유: ${pm.fallback_reason}` : ""}`) + st + pf;
}

// P6 — 왼쪽 고객 · 조건을 바꾸면 이전 결과를 지우고 준비 화면(정지)으로. 재생 속도 · 검색 · 목록 거르기는 결과를 지우지 않는다
document.addEventListener("change", ev => {
  const t = ev.target; if (!t || !t.closest || !t.closest(".mode-agent") || typeof AG === "undefined") return;
  if (t.matches("#agCsQ, #agTypes, #agOne, #agEngine")) return;
  setTimeout(agStale, 0);
}, true);
document.addEventListener("click", ev => {
  const t = ev.target; if (!t || !t.closest || typeof AG === "undefined") return;
  if (!t.closest("#agDuration, #agTurn button, #agMany [data-p], #agSelAll, #agSelNone, #agShowSel, #agShowAdd, #agReset, #agExpOff, .pe-adj, .pe-step")) return;
  setTimeout(agStale, 0);
}, true);

document.addEventListener('keydown',event=>{const go=event.target.closest('[data-frp-go]');if(go&&(event.key==='Enter'||event.key===' ')){event.preventDefault();go.click();}});

document.addEventListener('pointerdown',e=>{if(!e.target.closest('.hl-customer-picker'))document.querySelectorAll('.hl-customer-picker[open]').forEach(box=>box.open=false);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.hl-customer-picker[open]').forEach(box=>{box.open=false;box.querySelector('summary').focus();e.stopImmediatePropagation();});});
