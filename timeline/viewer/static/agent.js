// 10/23 에이전트 한 명 · 여러 명 — 핵심 선택 턴(저녁)을 기존 지도 · 오른쪽 패널 · 드로어에 연결한다.
// 계산은 서버 /api/turn (turn_run.py → turn_view.py) 그대로. 화면은 엔진이 돌려준 값만 쓰고 연출용 점수를 만들지 않는다.
// 호텔 전체 시뮬레이션 · 좌석 · 대기 · 혼잡 표현 없음 — 같은 업장을 여러 에이전트가 골라도 서로 영향이 없다.
// 10/23 2차 · 기존 손님 한 팀 화면의 장소 사진(.gnow) · 지도 길(route · markerPath) · 위치 점(agentDot)을 다시 쓴다.
//   출발 위치는 시나리오 입력(투숙 건물 객실 / 비투숙 정문), 선택 장소는 엔진 결과, 둘 사이 선은 '표시용 연결'(이동 시간 · 경로를 계산하지 않음).
const AG = {
  meta: null, mode: "agent", one: null, many: new Set(["A02", "A04", "A05", "A07", "A10"]),
  cond: { turn: "day", event: false, stay: true, building: "VISTA", party_size: 2, pricing: "historical", product_levers: {} },
  res: null, runs: [], ti: 0, sel: null, busy: false, keep: {},
  at: "turn", f: 1, raf: 0, open: new Set(),
  visits: null, fix: false,
  engine: (() => { try { return localStorage.getItem("wh_engine") === "legacy" ? "legacy" : "autonomy"; } catch (e) { return "autonomy"; } })(),   // CL-1024-22R — 고객 흐름의 행동 엔진(기본 autonomy_v1 · 기존 엔진은 개발 정보에서만 비교용)
  iv: "none", oneOverride: false, flow: null,   // 운영 변경(새 엔진) · 한 명 모드에서 운영자가 방문 조건을 직접 정했는가 · 마지막 /api/flow 응답의 이야기 · 엔진 정보
  // 10/24 보충2 — 여러 명: 투숙 · 건물 · 박수 · 체류 단계 · 동행은 고객이 정한다(visits). fix = 실험용 공통 조건 고정
};
const agIsMany = R => !!R && (R._mode === "agents" || R.customers.length > 1);
const agIsOne = R => !!R && !agIsMany(R);
const AG_TURN = { breakfast: "아침", event: "행사", dinner: "저녁" };
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
const noteH = o => `<button type="button" class="nfo nt" data-note="${esc(o.what || "")}" data-nj="${esc(JSON.stringify(o))}" aria-label="설명" title="설명 보기">i</button>`;
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
  if (kp) { AG.runs = kp.runs; AG.ti = kp.runs.length - 1; AG.res = AG.runs[AG.ti]; AG.sel = kp.sel; AG.plans = kp.plans || null; AG.visits = kp.visits || null; agShow(false); } else { AG.res = null; AG.runs = []; AG.plans = null; AG.visits = null; agReady(); }
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
function agTurnGround(runs, turn, pid) { if (!turn) return false; const R = runs.find(r => r.turn === turn), c = R && (R.customers || []).find(x => x.persona_id === pid); return !!(c && agCGround(c)); }
function agLeft() {   // CL-1024-13 — 왼쪽: ① 고객(선택 컴포넌트) ② 방문 · 환경(라벨-컨트롤 행) ③ 운영 조건(상품 표) · 실행 바(스크롤과 겹치지 않음)
  const M = AG.meta, many = AG.mode === "agents", c = AG.cond;
  const auto = many && !AG.fix;   // 여러 명 기본: 투숙 · 건물 · 체류 단계 · 동행은 고객이 정한다(실험용 고정은 따로)
  if (auto) c.turn = "day";
  const pick = many ? agCustPicker() : `<div class="fr fr-top"><select id="agOne" aria-label="고객">${AG.one ? "" : `<option value="" selected disabled>고객을 선택하세요</option>`}${agByNo(M.personas).map(p => `<option value="${p.id}"${p.id === AG.one ? " selected" : ""}>${esc(dno(p.id))} · ${esc(agTypeFull(p.id) || p.label)}</option>`).join("")}</select></div><div class="pc2" id="agPcard"></div>`;
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
  const helpCond = noteH({ what: "여러 명 모드에서는 운영자가 호텔(행사 · 가격 · 혜택)을 정하고, 고객마다 자기 후기 경험과 유형 · 성향으로 투숙 여부 · 건물 · 박수 · 체류 단계 · 동행을 정합니다.", basis: ["실제 후기", "추출 성향", "운영 조건 · 계산"], caution: "숙박 · 객실 선택에는 정량 계수가 없어 점수 · 확률을 매기지 않습니다(규칙 계획기 · 시드 고정). 특정 조건만 비교하려면 실험용 고정을 켜세요." });
  const NEW = AG.engine === "autonomy";
  const AG_IVS = [["none", "운영 변경 없음"], ["wine_fair_1300", "13:00 와인페어 개최 공지(2부 15:30~20:00)"], ["pizzahill_full", "15:00 피자힐 저녁 17:30~20:30 예약 마감"], ["pool_check", "12:00 실내 수영장 16:00~19:00 점검"]];
  const env = [
    NEW ? fr("하루", `<div class="fr-static"><b>하루 전체</b><span>고객이 아침부터 귀가 · 취침까지 스스로 계획합니다(아침 · 행사 · 저녁은 정량 엔진 판단)</span></div>`) :
    auto ? fr("핵심 턴", `<div class="fr-static"><b>하루 전체</b><span>고객마다 체류 단계가 달라 참여 턴이 다릅니다</span></div>`)
         : fr("핵심 턴", `<div class="cf-seg cf-seg4" id="agTurn" role="group" aria-label="핵심 턴">${turns}</div>`, { hint: esc(turnHint) }),
    fr("행사", `<select id="agEvent"><option value="0"${c.event ? "" : " selected"}>행사 없음</option><option value="1"${c.event ? " selected" : ""}>와인페어 있음</option></select>`, { for: "agEvent" }),
    auto ? fr(`관찰 구성${helpScen}`, `<select id="agScen">${AG_SCEN.map(([k, t]) => `<option value="${k}"${(AG.scen || "day") === k ? " selected" : ""}>${t}</option>`).join("")}</select>`, { for: "agScen" }) : "",
    auto ? fr(`고객 조건${helpCond}`, `<div class="fr-static"><b>각 고객이 정함</b><span>투숙 · 건물 · 박수 · 체류 단계 · 동행</span></div>`) : "",
    many ? fr("실험용", `<label class="cf-switch"><input type="checkbox" id="agFix"${AG.fix ? " checked" : ""}><span>같은 조건 고정</span></label>`, { hint: AG.fix ? "비교 실험 — 아래 투숙 · 건물 · 동행을 모두에게 적용(자율 선택 아님)" : "켜면 모든 고객에게 같은 투숙 · 건물 · 동행" }) : "",
    !auto ? fr("투숙", `<div class="cf-seg cf-seg2" id="agStay" role="group" aria-label="투숙"><button type="button" data-v="1" class="${c.stay ? "on" : ""}">투숙</button><button type="button" data-v="0" class="${c.stay ? "" : "on"}">비투숙</button></div>`) : "",
    !auto && c.stay ? fr("체류 단계", `<select id="agPhase" title="체크인 당일 = 오후부터 · 연박 중간일 = 아침부터 · 체크아웃 당일 = 아침 뒤 11시 퇴실"><option value="checkin"${c.phase === "checkin" ? " selected" : ""}>체크인 당일</option><option value="mid"${(c.phase || "mid") === "mid" ? " selected" : ""}>연박 중간일</option><option value="checkout"${c.phase === "checkout" ? " selected" : ""}>체크아웃 당일</option></select>`, { for: "agPhase", hint: (c.phase || "mid") === "mid" ? "아침부터" : c.phase === "checkin" ? "오후 체크인부터" : "아침 뒤 11시 퇴실" }) : "",
    !auto ? fr("건물", `<select id="agBld"${c.stay ? "" : " disabled"}>${Object.entries(M.buildings).map(([k, v]) => `<option value="${k}"${k === c.building ? " selected" : ""}>${esc(v.replace(" 워커힐", ""))}</option>`).join("")}</select>`, { for: "agBld", cls: c.stay ? "" : "fr-dim" }) : "",
    !auto ? fr("동행 인원", `<select id="agParty">${[1, 2, 3, 4, 5, 6].map(n => `<option value="${n}"${n === c.party_size ? " selected" : ""}>${n}명</option>`).join("")}</select>`, { for: "agParty" }) : "",
    NEW ? fr("행동 엔진", `<div class="fr-static"><b>autonomy_v1 · 규칙</b><span>LLM 호출 0 · 시드 고정<br>(같은 조건 = 같은 하루)</span></div>`) : fr("행동 계획", `<select id="agBackend" title="주요 결정(아침 · 행사 · 저녁) 사이의 체류 행동을 누가 구성하나 — 엔진 결정은 바뀌지 않음"><option value="rules"${(AG.backend || "rules") === "rules" ? " selected" : ""}>규칙 계획기 (기본)</option><option value="auto"${AG.backend === "auto" ? " selected" : ""}>LLM 계획기 (키 필요)</option></select>`, { for: "agBackend", hint: (AG.backend || "rules") === "rules" ? "시드 고정 · 같은 조건 = 같은 하루" : "키가 없거나 검증 실패면 규칙 계획기로 대체(표시됨)" }),
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
    <section class="cf-sec"><div class="cf-sh"><span class="cf-no">1</span><h3>${many ? "고객" : "고객 한 명"}</h3><span class="cf-sub">${many ? "함께 볼 고객 고르기" : "어떤 고객을 볼까요?"}</span></div>${pick}</section>
    <section class="cf-sec"><div class="cf-sh"><span class="cf-no">2</span><h3>방문 · 환경</h3><span class="cf-sub">어떤 조건에서 볼까요?</span></div><div class="fr-list">${env}</div></section>
    <section class="cf-sec"><div class="cf-sh"><span class="cf-no">3</span><h3>운영 조건</h3><span class="cf-sub">가격 · 할인 · 혜택</span><span class="cf-badge${nChanged ? " on" : ""}" id="agChgN">${nChanged ? `${nChanged}개 바꿈` : "기본값"}</span></div>
      ${AG.exp ? `<div class="ag-expl"><b>실험 조건 적용 중</b> ${esc(AG.exp.title || AG.exp.question)} · ${esc(AG.exp.change || AG.exp.levers)} <button type="button" id="agExpOff">해제</button></div>` : ""}
      ${NEW ? `<div class="fr-list ag-ivrow">${fr(`운영 변경${noteH({ what: "하루 도중 운영자가 시설 조건을 바꿉니다. 공지 시각 이후 고객마다 자기 성향 · 상황으로 원래 계획을 유지하거나 바꾸거나 대안을 고릅니다.", basis: ["운영 조건 · 계산"], caution: "피자힐 마감 · 수영장 점검은 가상 운영 변경입니다. 와인페어 일정 · 요금은 2026 공식 안내 기준(투숙객 무료 · 비투숙 성인 55,000원)." })}`, `<select id="agIv">${AG_IVS.map(([k, t]) => `<option value="${k}"${AG.iv === k ? " selected" : ""}>${esc(t)}</option>`).join("")}</select>`, { for: "agIv", hint: AG.iv !== "none" ? "변경 전 하루와 나란히 계산합니다" : "" })}</div>
        <div class="fr-h ag-newlv">아래 메뉴 조건 중 새 엔진(업장 단위)에 옮기는 것은 대표 상품뿐입니다 — 피자힐 커플 세트(가격 · 할인 · 판매) · 룸서비스 클럽 샌드위치 · 와인페어 · 조식 객실 포함. 나머지 메뉴 단위 조건은 '운영 실험' 탭에서 계산합니다.</div>` : ""}
      <div class="ag-lvchips" id="agLvChips"></div>
      <div class="pe" id="agOps">${groups}
        <div class="fr pe-pricing"${NEW ? ' style="display:none"' : ""}><label class="fr-k" for="agPricing">가격 기준</label><div class="fr-v"><select id="agPricing"><option value="historical"${c.pricing === "historical" ? " selected" : ""}>자료 원값</option><option value="provisional"${c.pricing === "provisional" ? " selected" : ""}>룸서비스 +10% 추정</option><option value="world_v1"${c.pricing === "world_v1" ? " selected" : ""}>기존 월드 값</option></select><div class="fr-h">자료 원값 = 피자힐 2026-07 · 룸서비스 2021년경. 비워 둔 가격은 자료 값.</div></div></div>
      </div>
    </section>
  </div>
  ${typeof document !== "undefined" && document.body.classList.contains("devmode") ? `<div class="dev ag-engdev">행동 엔진(개발 · 비교용) <select id="agEngine"><option value="autonomy"${NEW ? " selected" : ""}>새 엔진 autonomy_v1</option><option value="legacy"${NEW ? "" : " selected"}>기존 엔진(turn_view + 계획기)</option></select></div>` : ""}
  <div class="g-runbar cf-run"><div class="cf-run-b"><button id="agRun" class="cf-btn cf-primary">▶ 시뮬레이션 실행</button><button id="agReset" class="cf-btn">조건 초기화</button></div>
    <div class="cf-run-h"><span class="gh-sub">${nChanged || c.pricing !== "historical" ? "바꾼 조건은 기본 조건과 나란히 비교" : "같은 엔진으로 1회 계산"}</span><span class="ra-sub" id="agHint"></span></div></div>`;
  agLvChips();
  if (many) agCustPickerWire(); else { $("#agOne").onchange = e => { AG.one = e.target.value; agStale(); agLeft(); }; agPcard(); }
  { const rb = $("#agRun"); if (rb) rb.disabled = !many && !AG.one; }
  $("#agEvent").onchange = e => { c.event = e.target.value === "1"; if (!c.event && c.turn === "event") c.turn = "day"; agLeft(); };
  const xo = $("#agExpOff"); if (xo) xo.onclick = () => { AG.exp = null; agLeft(); if (AG.res) agPanel(); };
  $$("#agStay button").forEach(b => b.onclick = () => { AG.oneAuto = null; AG.oneOverride = true; c.club = false; c.stay = b.dataset.v === "1"; if (!c.stay) c.turn = "dinner"; agLeft(); });
  $$("#agTurn button[data-t]").forEach(b => b.onclick = () => { c.turn = b.dataset.t; agLeft(); });
  const bld = $("#agBld"); if (bld) bld.onchange = e => { AG.oneAuto = null; AG.oneOverride = true; c.club = false; c.building = e.target.value; if (!many) agPcard(); };
  const pty = $("#agParty"); if (pty) pty.onchange = e => { AG.oneAuto = null; AG.oneOverride = true; c.party_size = +e.target.value; if (!many) agPcard(); };
  const fx = $("#agFix"); if (fx) fx.onchange = e => { AG.fix = e.target.checked; agLeft(); };
  const scn = $("#agScen"); if (scn) scn.onchange = e => { AG.scen = e.target.value; };
  const ph = $("#agPhase"); if (ph) ph.onchange = e => { AG.oneAuto = null; AG.oneOverride = true; c.phase = e.target.value; if (c.phase === "checkout" && c.turn !== "day" && c.turn !== "breakfast") c.turn = "day"; agLeft(); };
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
  $("#agRun").onclick = agRun;
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
function agCustPicker() {
  const ids = agByNo(AG.meta.personas).map(x => x.id), cnt = {}, sel = {}; ids.forEach(id => { const t = agTypeOf(id); cnt[t] = (cnt[t] || 0) + 1; if (AG.many.has(id)) sel[t] = (sel[t] || 0) + 1; });
  const tyF = AG.tyF && AG.tyF !== "*" ? AG.tyF : null, q = (AG.csQ || "").trim().toLowerCase();
  const show = id => (!tyF || agTypeOf(id) === tyF) && (!q || id.toLowerCase().includes(q) || dno(id).toLowerCase().includes(q) || agTypeFull(id).toLowerCase().includes(q));
  const types = Object.keys(cnt).sort((a, b) => AG_TY_ORDER.indexOf(a) - AG_TY_ORDER.indexOf(b));
  const nShow = ids.filter(show).length;
  return `<div class="cs">
    <div class="cs-top"><div class="cs-count"><b>${AG.many.size}</b><span>/ ${ids.length}명 선택</span></div><div class="cs-acts"><button type="button" class="cf-btn cf-sm" id="agSelAll"${AG.many.size === ids.length ? " disabled" : ""}>전체 선택</button><button type="button" class="cf-btn cf-sm" id="agSelNone">선택 해제</button></div></div>
    <div class="cs-tools"><input type="search" id="agCsQ" class="cf-input" placeholder="번호 검색" value="${esc(AG.csQ || "")}" aria-label="고객 검색">
      <select id="agTypes" class="cs-tysel" aria-label="유형으로 목록 거르기(선택은 바뀌지 않음)">${[["*", `유형 전체`], ...types.map(t => [t, `${t.replace("개발 그룹", "개발")} ${sel[t] || 0}/${cnt[t]}`])].map(([k, t]) => `<option value="${esc(k)}"${(k === "*" && !tyF) || tyF === k ? " selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
    <ul class="cs-list" id="agMany" aria-label="고객 목록">${ids.map(id => { const on = AG.many.has(id), full = agTypeFull(id), sub = full.split(" · ").slice(1).join(" · ");
      return `<li${show(id) ? "" : " hidden"}><button type="button" data-p="${id}" class="cs-row${on ? " on" : ""}" aria-pressed="${on}" title="${esc(dno(id))} · ${esc(full || agTypeOf(id))}"><span class="cs-chk" aria-hidden="true"></span><span class="cs-id">${esc(dno(id))}</span><span class="cs-tt">${esc(agTypeOf(id).replace("개발 그룹", "개발"))}</span></button></li>`; }).join("")}</ul>
    ${tyF || q ? `<div class="cs-foot"><span>${nShow}명 표시 중</span><button type="button" class="cf-link" id="agShowSel">보이는 고객만 선택</button><button type="button" class="cf-link" id="agShowAdd">추가로 선택</button></div>` : ""}
    <div class="cs-note">고른 고객은 같은 운영 조건에서 서로 영향을 주지 않고 각자 판단합니다${noteH({ what: "입력 버전이 다른 고객(개발 그룹 · 로컬 전용)이 섞여 있으면 프로파일의 버전 표시를 확인하세요. 유형 칸은 목록만 거르며 고른 고객을 바꾸지 않습니다.", basis: ["운영 조건 · 계산"] })}</div>
  </div>`;
}
function agCustPickerWire() {
  const ids = AG.meta.personas.map(x => x.id), keepScroll = () => { const g = $(".mode-agent .g-scroll"); return g ? g.scrollTop : 0; }, rerender = () => { const s = keepScroll(); agLeft(); const g = $(".mode-agent .g-scroll"); if (g) g.scrollTop = s; };
  $$("#agMany button[data-p]").forEach(b => b.onclick = () => { const p = b.dataset.p; AG.many.has(p) ? AG.many.delete(p) : AG.many.add(p); if (!AG.many.size) AG.many.add(p); rerender(); });
  const tys = $("#agTypes"); if (tys) tys.onchange = e => { AG.tyF = e.target.value; rerender(); };   // 목록만 거름 — 선택은 그대로
  const all = $("#agSelAll"); if (all) all.onclick = () => { AG.many = new Set(ids); rerender(); };
  const none = $("#agSelNone"); if (none) none.onclick = () => { const vis = $$("#agMany li:not([hidden]) [data-p]").map(b => b.dataset.p); AG.many = new Set([vis[0] || ids[0]]); rerender(); };
  const q = $("#agCsQ"); if (q) q.oninput = e => { AG.csQ = e.target.value; const s = keepScroll(), pos = e.target.selectionStart; agLeft(); const n = $("#agCsQ"); if (n) { n.focus(); n.setSelectionRange(pos, pos); } const g = $(".mode-agent .g-scroll"); if (g) g.scrollTop = s; };
  const vs = () => $$("#agMany li:not([hidden]) [data-p]").map(b => b.dataset.p);
  const ss = $("#agShowSel"); if (ss) ss.onclick = () => { const v = vs(); if (v.length) AG.many = new Set(v); rerender(); };
  const sa = $("#agShowAdd"); if (sa) sa.onclick = () => { vs().forEach(id => AG.many.add(id)); rerender(); };
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
      <div><dt>후기 근거</dt><dd>성향 ${nObs}/${p.bars.length} 확인${noteH({ what: `이 고객의 성향 ${p.bars.length}개 중 ${nObs}개가 실제 후기에서 확인됐습니다. 나머지는 '근거 미확인'으로, 0점이라는 뜻이 아닙니다.`, basis: ["실제 후기", "추출 성향"], caution: `추출은 끝났지만 독립 검증 전입니다. 입력 버전 ${p.pipeline || "R-BASE-1022"}.` })}</dd></div></dl>
    <div class="pc2-acts"><button type="button" class="cf-btn" id="agProf">프로파일 보기</button><button type="button" class="cf-btn${mine || (AG.engine === "autonomy" && !AG.oneOverride) ? " on" : ""}" id="agAutoOne" title="이 고객의 후기 경험 · 유형 · 성향으로 투숙 여부 · 건물 · 체류 단계 · 동행을 정해 아래 입력에 넣습니다(운영자가 바꿀 수 있음)">${mine ? "다시 정하기" : "이 고객이 정하기"}</button></div>
    <p class="pc2-note">${AG.engine === "autonomy" ? (AG.oneOverride ? "운영자가 정한 방문 조건 · 투숙 · 건물 · 체류 단계 · 동행 = 아래 입력값" : `방문 조건은 고객이 정함 <span class="nb">(후기 · 유형 · 성향)</span>${AG.oneVisit && AG.oneVisit.pid === p.id ? `<span class="pc2-v"><b>${esc(AG.oneVisit.short.replace(/\s*\[[^\]]*\]$/, ""))}</b>${/\[([^\]]*)\]$/.test(AG.oneVisit.short) ? `<em class="pc2-tag">${esc(AG.oneVisit.short.match(/\[([^\]]*)\]$/)[1])}</em>` : ""}</span>` : `<span class="pc2-v">실행하면 이 고객이 정한 조건이 아래에 표시됩니다</span>`}`) : mine ? `고객이 정한 조건 적용 중 · <b>${esc(AG.oneAuto.short)}</b>` : "투숙 · 건물 · 체류 단계 · 동행 = 아래 입력값"}</p>`;
  el.insertAdjacentHTML("beforeend", agRsLine(p.id) + `<button type="button" class="cf-link st-return" id="agSituation">상황 다시 설정</button>`);
  $("#agSituation").onclick = () => situationOpen(p.id, true);
  const rsb = $("#agRsRun"); if (rsb) rsb.onclick = () => { const R = AG.oneRS.rs, c = AG.cond; AG.oneAuto = null; AG.oneOverride = true; c.stay = R.building !== "NONSTAY"; if (c.stay) { c.building = R.building; c.phase = c.phase && c.phase !== "visit" ? c.phase : "mid"; } c.club = !!R.club; agLeft(); agRun(); };
  $("#agProf").onclick = () => agCustDrawer(p.id);
  $("#agAutoOne").onclick = () => { if (AG.engine === "autonomy") { AG.oneOverride = false; AG.oneAuto = null; agPcard(); return; } agAutoOne(p.id); };
}
async function agAutoOne(pid) {   // 보충2 — 한 명 모드에서도 고객이 자기 방문 조건을 정할 수 있다(결과는 왼쪽 입력에 반영 · 운영자가 덮어쓸 수 있음)
  try {
    const c0 = AG_COMP[pid], comp = c0 ? { [pid]: { n: c0.n, rel: c0.rel, kids: c0.rel === "family_kids", elder: c0.rel === "family_parents" } } : {};
    const seed = (AG.oneAuto && AG.oneAuto.pid === pid ? AG.oneAuto.seed + 1 : (AG.seed || 0));
    const r = await api("/api/stay", { op: "visit", personas: [pid], cond: { event: AG.cond.event }, comp, seed });
    const v = r.visits && r.visits[pid]; if (!v) return;
    const c = AG.cond; c.stay = !!v.stay; if (v.stay) { c.building = v.building; c.phase = v.phase; } c.party_size = v.party_size; c.turn = "day";
    AG.oneAuto = { pid, seed, v, short: v.stay ? `${AG_BLD_SHORT[v.building]} ${v.nights}박 · ${AG_PH_KO[v.phase]} · ${v.party_size}인` : `비투숙 당일 방문 · ${v.party_size}인` };
    agLeft();
  } catch (e) { console.warn("visit 실패", e); }
}
// ---------------------------------------------------------------- 실행
// 10/24 보충1 수정본 — 체류·행동 계획(stay_run.py): 엔진 결정은 그대로 넘기고 그 사이 행동만 받는다. 시드 고정으로 같은 조건 = 같은 하루
const agDecisions = (runs, pid, before) => runs.map(R => { const RR = before ? (R._before || R) : R, c = agCustOf(RR, pid); if (!c) return null; const cc = R.compare && R.compare.customers.find(y => y.persona_id === pid);
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
async function agRunFlow(ids, cond, auto) {
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
async function agRun() {
  if (AG.busy) return;
  if (AG.mode !== "agents" && !AG.one) { agReady(); return; }
  const ids = AG.mode === "agents" ? [...AG.many] : [AG.one];
  AG.busy = true; const b = $("#agRun"); b.disabled = true; b.textContent = "계산 중…";
  try {
    const cond = JSON.parse(JSON.stringify(AG.cond)), auto = AG.mode === "agents" && !AG.fix;
    const ph = cond.stay ? (cond.phase || "mid") : "visit";   // 체류 단계: checkin(오후 시작 · 조식 없음) · mid(연박 중간일) · checkout(조식 뒤 체크아웃) · visit(비투숙)
    let runs, visits = null;
    if (AG.engine === "autonomy") {   // CL-1024-22R — 새 행동 엔진: 하루 전체를 autonomy_v1 이 만들고, 서버 어댑터가 화면 계약(runs · plans · visits)으로 옮긴다
      b.textContent = ids.length > 1 ? `${ids.length}명 하루 계산 중…` : "하루 계산 중…";
      const F = await agRunFlow(ids, cond, auto);
      runs = F.runs; visits = F.visits;
      if (!runs.length) throw new Error("이 고객은 오늘 정량 결정(아침 · 행사 · 저녁) 없이 하루를 마칩니다 — 방문 조건을 바꿔 다시 실행하세요");
      AG.runs = runs; AG.ti = runs.length - 1; AG.res = runs[AG.ti]; AG.visits = visits;
      AG.sel = ids.length === 1 ? ids[0] : null; AG.focusLoc = null; AG.plans = F.plans; AG._sc = null; AG._rate = 0;
      AG.keep[AG.mode] = { runs, sel: AG.sel, plans: AG.plans, visits, flow: AG.flow };
      agPlanHint(); agShow(true); document.dispatchEvent(new Event("hl:agrun")); return;
    }
    if (auto) {   // 운영자는 호텔(행사 · 가격 · 혜택)을 정하고, 고객은 자기 방문 조건(투숙 · 건물 · 박수 · 체류 단계 · 동행)을 정한다
      cond.turn = "day";
      const comp0 = {}; ids.forEach(pid => { const c = AG_COMP[pid]; if (c) comp0[pid] = { n: c.n, rel: c.rel, kids: c.rel === "family_kids", elder: c.rel === "family_parents" }; });
      b.textContent = "고객별 방문 조건 정하는 중…";
      const vr = await api("/api/stay", { op: "visit", personas: ids, cond: { event: cond.event, scenario: AG.scen || "day" }, comp: comp0, seed: AG.seed || 0 });
      visits = vr.visits || {};
      const groups = {};
      ids.forEach(pid => { const v = visits[pid] || (visits[pid] = { stay: true, building: "VISTA", phase: "mid", party_size: 2, nights: 1, rel: "group", layer: "generated", why: "기본값" }); const key = `${v.stay ? 1 : 0}|${v.stay ? v.building : "-"}|${v.party_size}|${v.stay ? v.phase : "visit"}`; (groups[key] = groups[key] || { v, ids: [] }).ids.push(pid); });
      const G = Object.values(groups), byT = {}; let gi = 0;
      for (const g of G) {
        b.textContent = `계산 중… 조건 묶음 ${++gi}/${G.length}`;
        const gc = Object.assign({}, cond, { stay: !!g.v.stay, building: g.v.stay ? g.v.building : cond.building, party_size: g.v.party_size, phase: g.v.stay ? g.v.phase : null });
        agMergeRuns(byT, await agRunTurns(g.ids, gc, g.v.stay ? g.v.phase : "visit"), agVcOf(g.v));
      }
      runs = ["breakfast", "event", "dinner"].filter(t => byT[t]).map(t => byT[t]);
      runs.forEach(R => { R._mode = AG.mode; R._auto = true; R.conditions = Object.assign({}, R.conditions, { mixed: true }); });
    } else runs = await agRunTurns(ids, cond, ph);
    if (!runs.length) throw new Error("계산할 턴이 없습니다");
    AG.runs = runs; AG.ti = runs.length - 1; AG.res = runs[AG.ti]; AG.visits = visits;
    AG.sel = ids.length === 1 ? ids[0] : null; AG.focusLoc = null;
    b.textContent = "하루 구성 중…";
    AG.plans = await agFetchPlans(ids, runs, cond, ph, visits);   // 체류·행동 계획 계층(엔진 결정 사이) — 실패하면 화면 안 간이 흐름으로
    AG.keep[AG.mode] = { runs, sel: AG.sel, plans: AG.plans, visits };
    agPlanHint();
    agShow(true); document.dispatchEvent(new Event("hl:agrun"));
  } catch (e) { $("#panel").innerHTML = `<div class="callout">계산 실패 — ${esc(e.message)}</div>`; }
  finally { AG.busy = false; b.disabled = AG.mode !== "agents" && !AG.one; b.textContent = "▶ 시뮬레이션 실행"; }
}

function agPlanHint() {   // §9 — 요청 계획기 · 실제 사용 계획기 · 대체 이유를 화면에서 구별
  const el = $("#agHint"); if (!el) return;
  if (AG.engine === "autonomy" && AG.flow) { const F = AG.flow, n = Object.keys(AG.plans || {}).length;
    el.innerHTML = `<span class="ag-plm" data-engine="${esc(F.engine.name)}">행동 엔진 <b>${esc(F.engine.name)}</b> · ${esc(F.engine.backend)} · ${n}명${F.intervention && F.intervention.id !== "none" ? ` · 운영 변경 <b>${esc(F.intervention.label.split("(")[0])}</b>` : ""}${F.applied.length ? ` · 메뉴 조건 반영 ${F.applied.length}` : ""}${F.skipped.length ? ` · <b class="ag-blk">새 엔진 미반영 ${F.skipped.length}</b>` : ""}</span>`; return; } const P = Object.values(AG.plans || {}); if (!P.length) { el.textContent = ""; return; }
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
function agAvatarImg(key, x, y, k, cls, o = {}) {   // 발 밑 = (x, y) · 정면은 서 있기, 측면은 걷기 프레임(원본이 왼쪽을 봄 → 오른쪽 이동이면 뒤집기)
  // 그룹은 translate(x, y) 로만 움직이고 안쪽 좌표는 발 밑 (0, 0) 기준 — 재생 중에는 요소를 다시 만들지 않고 transform · viewBox 만 바꾼다(이미지 깜빡임 방지)
  const A = AG.avm[key], row = o.walk ? A.side : A.front, H = (A.n_members > 2 ? 50 : A.n_members === 2 ? 46 : 42) * k, W = H * row.cw / row.ch;
  const fi = o.walk ? (o.frame || 0) % row.n : 0, src = `/static/avatars/${key}_${o.walk ? "side" : "front"}.png`;
  const flip = o.walk && o.dir > 0 ? "scale(-1,1)" : "";
  return `<g class="ag-avatar ag-avimg ${cls}${o.hl ? " ag-sel" : ""}" data-av="${key}" data-walk="${o.walk ? 1 : 0}" transform="translate(${x.toFixed(2)},${y.toFixed(2)})${agHlScale(o)}"><ellipse class="ag-avsh" cx="0" cy="${1.5 * k}" rx="${W * 0.38}" ry="${3 * k}"/><g class="ag-avflip" transform="${flip}"><svg x="${-W / 2}" y="${-H}" width="${W}" height="${H}" viewBox="${fi * row.cw} 0 ${row.cw} ${row.ch}" preserveAspectRatio="xMidYMax meet"><image href="${src}" width="${row.cw * row.n}" height="${row.ch}"/></svg></g></g>`;
}
function agAvatarMove(el, key, x, y, o = {}) {   // 이미 그려진 아바타를 제자리에서 옮긴다(이미지 요소 유지)
  const A = AG.avm[key], row = o.walk ? A.side : A.front, fi = o.walk ? (o.frame || 0) % row.n : 0;
  el.setAttribute("transform", `translate(${x.toFixed(2)},${y.toFixed(2)})${agHlScale(o)}`);
  const fg = el.querySelector(".ag-avflip"); if (fg) fg.setAttribute("transform", o.walk && o.dir > 0 ? "scale(-1,1)" : "");
  const sv = el.querySelector("svg"); if (sv) sv.setAttribute("viewBox", `${fi * row.cw} 0 ${row.cw} ${row.ch}`);
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
  luxbar: "럭스바", night_walk: "저녁 산책", room_night: "객실 복귀", checkin: "체크인", checkout: "체크아웃", pack: "짐 정리", arrive: "도착", leave: "귀가", sleep: "취침",
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
  const key = "plan|" + pid + "|" + runs.map(r => r.turn + (r.time || "")).join(",") + "|" + plan.length + "|" + (AG.plans[pid].backend || "");
  if (AG._sc && AG._sc.key === key) return AG._sc.list;
  const R0 = runs[0], S0 = [];
  let prev = null;
  plan.forEach((ps, i) => {
    const ti = ps.layer === "engine" ? Math.max(0, runs.findIndex(r => r.turn === ps.turn)) : (prev ? prev.ti : 0);
    const loc = LOC[ps.loc] ? ps.loc : (prev ? prev.loc : agStart(R0, pid));
    if (prev && prev.loc !== loc && LOC[prev.loc] && LOC[loc]) {   // 이동 장면 — 도착 시각 앞 travel 분(앞 장면 끝보다 이르지 않게)
      const r = route(prev.loc, loc), mp = markerPath(prev.loc, loc, r);
      if (mp.mk && mp.mk.total && !r.unknown) { const tr = Math.max(4, Math.min(ps.travel || 8, ps.t0 - prev.t1 > 0 ? ps.t0 - prev.t1 : 8)); S0.push({ k: "move", ti, t0: Math.max(prev.t1, ps.t0 - tr), t1: ps.t0, a: prev.loc, b: loc, r, mk: mp.mk, label: "이동", src: "link" }); }
    }
    const base = { ti, t0: ps.t0, t1: ps.t1, loc, act: ps.act, label: ps.label, short: AG_ACT_SHORT[ps.act] || ps.label, name: agPlaceName(loc, runs[ti]), why: agWhySafe(ps.why, ps.turn ? agTurnGround(runs, ps.turn, pid) : agScGround(ps.basis)), why_raw: ps.why, basis: ps.basis || {}, cond_dep: !!ps.cond_dep, consume: !!ps.consume, kind: ps.kind, icon: AG_ACT_ICON[ps.act] || "walk", meal: ps.meal || null };
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
    while (e >= d) { if (stopAtTurn && L[i].k === "turn" && i !== si) break; e -= d; i++; t0 = now - e; if (i >= L.length) { i = L.length - 1; agSetScene(L[i].si, 1); AG.playing = false; AG.ended = true; agStripState(); return; } d = agSceneDur(L[i]); }
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
  if (AG.res && agIsMany(AG.res)) return agPlayManyTime();
  const c = agCur(); if (!c) return; const L = agScenes(c.persona_id), sc = L[AG.si];
  if (!sc || AG.ended) { AG.ended = false; return agPlayFrom(0); }
  agPlayFrom(AG.si, sc.k === "start" ? 0 : (AG.f || 0));
}
function agSkipNext() {   // ⏭ 다음 주요 장면(엔진 결정)으로 — 보조 조작
  cancelAnimationFrame(AG.raf); AG.playing = false; AG.paused = false;
  const n = Math.max(AG.runs.length, 1);
  if (AG.res && agIsMany(AG.res)) { agManyStop(); agSetAt("turn", null, AG.at === "turn" ? (AG.ti + 1) % n : AG.ti); agStripState(); return; }
  const c = agCur(); if (!c) return; const L = agScenes(c.persona_id);
  let j = L.findIndex((x, i) => x.k === "turn" && i > (AG.si == null ? -1 : AG.si));
  if (j < 0) j = L.findIndex(x => x.k === "turn");
  agSetScene(j, 1); agStripState();
}
function agRestart() {   // ↺ 처음부터
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
    if (T >= wb) { AG.playing = false; AG.manyMoving = false; AG.manyAnim = null; AG.ended = true; agStripState(); return; }
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
function agClock(Rx) {
  const R = Rx || AG.res; if (!R) return;
  const sc = AG.res && agIsOne(AG.res) ? agScene() : null, flow = AG.at === "mid", mv = AG.at === "move" || AG.manyMoving;
  const tm = AG.nowMin != null ? agHM(AG.nowMin) : flow ? "낮" : (R.time || "--:--");
  const manyAuto = agIsMany(R) && !AG.fix && AG.nowMin != null, tiNow = manyAuto ? agTurnAt(AG.nowMin) : -1;
  const what = manyAuto ? (tiNow >= 0 ? `${AG_TURN[AG.runs[tiNow].turn]} · 주요 결정` : `${agOpsAt(AG.nowMin).present.length}명 호텔 안${AG.manyMoving ? " · 각자 활동 중" : ""}`) : AG.manyMoving ? `${agAllIds().length}명이 각자 체류 중` : sc && sc.k === "flow" ? `${sc.label}` : sc && sc.k === "move" ? `${sc.b ? (agPlaceName(sc.b, R)) : "다음 장소"}(으)로 이동` : sc && sc.k === "start" ? sc.label : flow ? "낮 · 자유 시간" : AG_TURN[R.turn] + " 턴";
  $("#clock b").textContent = tm;
  $("#clock span").innerHTML = `<em class="ck-t${flow ? " gen" : mv ? " mv" : ""}">${esc(what)}</em>${AG.runs.length > 1 && !manyAuto ? `<i class="ck-s">하루 ${AG.ti + 1}/${AG.runs.length}</i>` : ""}<small class="ck-c">${R._auto ? `고객별 방문 조건 · ${agAllIds().length}명` : `${R.conditions.stay ? esc(R.building.label) + " 투숙" : "비투숙"} · ${R.conditions.party_size}인`}${R.conditions.event ? " · 와인페어" : ""}</small>`;
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
// P6 — 준비(정지) 화면: 고객 · 조건만 보이고 시계 · 아바타 · 타임라인은 움직이지 않는다. 사용자가 ▶ 시뮬레이션 실행을 눌러야 하루 시작
function agReady() {
  if (typeof setPlay === "function") setPlay(false);
  cancelAnimationFrame(AG.raf); AG.playing = false; agManyStop && agManyStop(); agMapReset();
  const many = AG.mode === "agents", p = !many && AG.one ? dno(AG.one) : null;
  $("#mapEmpty").classList.remove("hidden");
  $("#mapEmpty").innerHTML = many ? `<div class="ar-t"><b>${AG.many ? AG.many.size : 0}명</b>을 같은 조건에 넣을 준비가 되었습니다</div><span>조건을 확인하고 왼쪽 아래 <b>▶ 시뮬레이션 실행</b>을 누르면 하루가 시작됩니다</span>`
    : p ? `<div class="ar-t"><b>${esc(p)}</b>의 하루를 시작할 준비가 되었습니다</div><span>${AG.cond.event ? "와인페어 있는 날 · " : ""}조건을 확인하고 왼쪽 아래 <b>▶ 시뮬레이션 실행</b>을 누르세요</span>`
    : `<div class="ar-t"><b>고객을 먼저 선택하세요</b></div><span>왼쪽 ① 고객에서 한 명을 고르고, 조건을 정한 뒤 <b>▶ 시뮬레이션 실행</b>을 누르면 하루가 시작됩니다</span>`;
  $("#mapEmpty").classList.add("ag-ready");
  $("#clock b").textContent = "--:--"; $("#clock span").textContent = "";
  $("#panel").innerHTML = `<div class="ag-ready-p">${many ? "실행하면 여기에 이 시각의 고객 현황과, 지도에서 고른 고객의 선택 이유가 나옵니다." : "실행하면 여기에 이 고객이 고른 곳과 이유, 고르지 않은 대안이 나옵니다."}</div>`;
  $("#strip").innerHTML = ""; $("#strip").classList.add("ag-off");
  const rb = $("#agRun"); if (rb) rb.disabled = !many && !AG.one;
  agReadyAvatar();
}
// 고객 · 조건이 바뀌면 이전 결과(다른 사람 · 다른 조건)를 지우고 준비 화면으로 — 낡은 타이머가 남지 않게
function agStale() {
  if (typeof AG === "undefined" || AG.busy) return;
  if (!AG.res && !AG.runs.length) return agReady();
  AG.res = null; AG.runs = []; AG.plans = null; AG.visits = null; AG.sel = null; AG.keep[AG.mode] = null;
  if (typeof closeDrawer === "function") closeDrawer();
  agReady();
}
function agShow(play) {
  const R = AG.res; if (!R) return agEmpty();
  cancelAnimationFrame(AG.raf);
  $("#mapEmpty").classList.add("hidden"); $("#mapEmpty").classList.remove("ag-ready");
  AG.at = "turn"; AG.f = 1; AG.nowMin = null; AG._sc = null; AG._rate = null; AG.ended = false; AG.manyT = null; AG.manyHeld = null; AG_LABKEY = ""; agManyStop();
  { const c = agCur(); const L = agScenes(c ? c.persona_id : null); const i = L.findIndex(x => x.k === "turn" && x.ti === AG.ti); AG.si = i >= 0 ? i : 0; if (i >= 0) AG.nowMin = L[i].t0; }
  agClock(); agDrawMap(); agStrip(); agPanel();
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
    AG._opsAt = 0; agManyDraw(T); agStrip(); agStripNow(T); const pn = $("#panel"); if (pn) pn.scrollTop = 0; return;
  }
  if (many && AG.manyMoving) { agManyDraw(AG.manyT); agStripState(); return; }   // 재생 중 — 멈추지 않고 강조만 바꾼다
  if (many) { cancelAnimationFrame(AG.raf); if (AG.at !== "mid") AG.at = "turn"; AG.f = 1; }   // 여러 명 — 보고 있던 턴을 유지하고 고객만 바꾼다(하루 재생 없음)
  agDrawMap(); agStrip(); agPanel(); if (!many) agPlay(); else agDrawRoute();
  const sh = $("#agSelH"), pn = $("#panel"); if (sh && pn) pn.scrollTop = Math.max(0, sh.offsetTop - pn.offsetTop - 8);   // 여러 명 — 고른 고객 상세로 스크롤
}

// ---------------------------------------------------------------- 아래 · 턴 타임라인 (분 단위 시간축이 아니라 확인된 지점만)
function agCtl(many) {   // CL-1024-13 — 재생 조작: 주 버튼(재생/일시정지) · 보조(주요 결정 · 처음부터) · 속도 — 같은 높이 · 한 줄
  return `<div class="tl2-ctl" role="group" aria-label="재생 조작">
    <button type="button" class="cf-btn cf-sm tl2-play ag-play" title="재생 · 주요 결정에서 잠시 머묾"><i class="tli">▶</i><small>재생</small></button>
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
  el.innerHTML = agTlFrame(`${esc(dno(pid))}의 ${runs.length > 1 ? "하루" : AG_TURN[R.turn] + " 턴"}`, esc(cp.scen || ""), agTlLegend(["key", ...AG_CAT_ORDER.filter(k => cats.includes(k))]), AG_TL_HELP,
    [{ label: "주요 결정", band: "tl2-keys", html: keys }, { label: "활동", band: "tl2-acts", html: segs }], wa, wb);
  agCtlWire(); agTlFit();
  $$("#strip [data-si]").forEach(b => b.onclick = () => { cancelAnimationFrame(AG.raf); AG.playing = false; AG.paused = false; const sc = L.find(x => x.si === +b.dataset.si); agSetScene(+b.dataset.si, sc && sc.k === "move" ? 0.5 : sc && sc.k === "flow" ? 1 : null); agStripState(); });
  agStripState();
}
function agStripCell(sc, pid, runs) { return agTlSeg(sc, pid, 0, 1440); }   // 호환(이전 이름)
function agStripMany(el) {   // 여러 명 — 주요 결정(시각 · 인원) · 활동 밀도(15분 · 종류별 인원) · 고른 고객의 하루(활동 띠) · 공통 시간축
  const runs = AG.runs.length ? AG.runs : [AG.res], [wa, wb] = agManyWindow(), span = Math.max(60, wb - wa);
  const sum = run => { const m = {}; run.customers.forEach(x => m[x.choice.venue_id] = (m[x.choice.venue_id] || 0) + 1); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([v, k]) => `${agVenueName(run, v).split(" · ")[0].replace(/\(.*\)/, "")} ${k}`).join(" · "); };
  const nAll = agAllIds().length;
  const keys = runs.map((run, i) => agTlKey(run, i, agMin(run.time) || 0, `${AG_TURN[run.turn]} ${run.time} · ${run.customers.length}명`, sum(run), run.compare && run.compare.customers.some(y => y.status === "changed"), wa, span).replace("</span>", ` <small>${run.customers.length}명</small></span>`)).join("");
  const step = 15, maxN = Math.max(1, nAll); let dens = "";
  for (let t = Math.floor(wa / step) * step; t < wb; t += step) { const O = agOpsAt(t + step / 2); const segs = AG_CAT_ORDER.filter(k => (O.byCat[k] || []).length).map(k => [k, O.byCat[k].length]);
    dens += `<span class="dn" data-t="${t + step / 2}" style="left:${((t - wa) / span * 100).toFixed(3)}%;width:${(step / span * 100).toFixed(3)}%" title="${agHM(t)}–${agHM(t + step)} · 호텔 안 ${O.present.length}명${segs.length ? " · " + segs.map(([k, n]) => `${AG_CAT[k].label} ${n}`).join(" · ") : ""}">${segs.map(([k, n]) => `<i style="height:${(n / maxN * 100).toFixed(1)}%;background:${AG_CAT[k].color}"></i>`).join("")}</span>`; }
  const sel = AG.sel && agAllIds().includes(AG.sel) ? AG.sel : null;
  const me = sel ? agScenes(sel).map(x => agTlSeg(x, sel, wa, span).replace('class="tl2-seg', 'class="tl2-seg tl2-me')).join("") : `<span class="tl2-empty">지도 · 오른쪽에서 고객을 누르면 그 고객의 하루가 여기에 나옵니다</span>`;
  el.classList.remove("ag-off"); el.style.height = "";
  el.innerHTML = agTlFrame(`에이전트 ${nAll}명의 하루`, "", agTlLegend(["key", "meal", "well", "culture", "walk", "room", "move"]),
    { what: "맨 위는 시각, 붉은 표식은 엔진이 계산한 주요 소비 결정(재생이 잠시 머묾), 가운데 막대는 15분마다 호텔 안 고객이 무엇을 하는지(활동 종류별 인원), 고객을 고르면 맨 아래에 그 고객의 하루가 활동 띠로 나옵니다. 막대 · 띠를 누르면 그 시각으로 갑니다.", basis: ["운영 조건 · 계산", "추출 성향", "실제 후기"], caution: "주요 결정 외의 활동은 행동 계획기가 프로파일 · 동행 · 체류 단계로 구성한 것이며 엔진 점수가 아닙니다. 이동 시간은 표시용입니다." },
    [{ label: "주요 결정", band: "tl2-keys", html: keys }, { label: "활동 밀도", band: "tl2-dens", html: dens }, { label: sel ? esc(dno(sel)) : "고객", cls: sel ? "tl2-rk-me" : "", band: "tl2-acts", html: me }], wa, wb);
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
    pb.querySelector("small").textContent = AG.playing ? "일시정지" : AG.paused ? "계속" : AG.ended ? "처음부터 재생" : "재생";
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
function agTurnCard(c, compact) {
  const R = AG.res, o = c.best_other_venue, near = o && o.margin < 0.15, T = c.reason_totals, sy = agSentence(c), pr = c.choice.price;
  const im = !compact && typeof placeImg === "function" ? placeImg(c.choice.map_loc) : null;
  const cc = R.compare && R.compare.customers.find(y => y.persona_id === c.persona_id), chg = cc && cc.status === "changed";
  const act = R.turn === "event" && c.choice.venue_id === "FOREST" ? "와인페어 참여" : R.turn === "event" && c.choice.venue_id === "SKYARD" ? "스카이야드 족욕" : agShort(c.choice.product_label);
  const paid = pr.paid_krw != null ? pr.paid_krw : pr.pp_krw;
  const priceTxt = pr.price_kind === "known_free" ? "입장료 0원 · 투숙객 무료 입장 · 음식 · 프로그램 별도(가격 미정)" : pr.price_kind === "unknown" ? "입장료 미확인 · 퇴실 뒤 투숙객 무료 적용 여부 확인 필요"
    : `1인 ${agWon(paid)}${pr.in_package ? " · 객실 포함" : pr.guest_discount_krw ? ` · 할인 ${agWon(pr.guest_discount_krw)}` : ""}${pr.price_kind === "known_paid" ? " · 비투숙 성인 입장료 · 음식 · 프로그램 별도" : ""}`;
  const cmpTxt = cc ? (chg ? `기본 조건이면 <b>${esc(agShort(cc.before.product_label))}</b> → 바꾼 조건에서 <b>${esc(agShort(cc.after.product_label))}</b>` : `바꾼 조건에서도 같은 선택${cc.status === "score_only" ? ` <span class="rp-mut">(점수 ${cc.score_delta > 0 ? "+" : ""}${agNum(cc.score_delta)})</span>` : ""}`) : "";
  const gistOk = sy.gist && !/화면에서 제외/.test(sy.gist);
  const chained = c.state_after && c.state_after.chained;
  return `<section class="rp${compact ? " rp-c" : ""}">
    <div class="rp-eye"><span>${esc(dno(c.persona_id))} · ${esc(R.time || "")} ${AG_TURN[R.turn]} 선택</span>${cc ? `<em class="rp-st${chg ? " chg" : ""}">${chg ? "조건 변경으로 바뀜" : "조건 변경 · 유지"}</em>` : ""}</div>
    <div class="rp3-res">${im ? `<button type="button" class="rp3-th" id="agImg" title="${esc(im.name)} 크게 보기"><img src="${im.src}" alt="${esc(im.name)}"></button>` : ""}<div><span class="rp3-k">이번 행동</span><h2 class="rp-title gn-place">${esc(agVenueTitle(R, c.choice, c.persona_id))}</h2><div class="rp-menu gn-act">${esc(agMenuTitle(R, c.choice))}</div></div></div>
    ${AG.exp && !compact ? `<div class="rp-exp"><span>운영 실험</span>${esc(AG.exp.title || AG.exp.question)}${noteH({ what: agExpInfo(AG.exp), basis: ["운영 조건 · 계산"], caution: "실험 카드의 조건을 적용한 가상 운영안입니다." })}</div>` : ""}
    <div class="rp3-why"><div class="rp3-wh"><span class="rp3-k">이유</span>${T.review > 0.05 ? `<em class="rp3-tag rv">후기 근거 +${agNum(T.review)}</em>` : `<em class="rp3-tag">공통 규칙에 따른 결정</em>`}</div>
      <p>${esc(agWhySafe(c.why || "", agCGround(c)) || "")}</p></div>
    <table class="rp3-cmp"><tbody><tr class="on"><th>선택</th><td>${agDot(c.choice.venue_id)}${esc(agChoiceName(R, c.choice))}</td><td class="num">${agNum(c.choice.score)}</td></tr>
      ${o ? `<tr><th>대안</th><td>${agDot(o.venue_id)}${esc(agChoiceName(R, o))}${near ? ` <em class="rp-near">근소</em>` : ""}</td><td class="num">${agNum(c.choice.score - o.margin)}</td></tr>` : ""}</tbody></table>
    <button type="button" class="rp3-go" data-why="${c.persona_id}">자세한 판단 근거 ›</button>
    <details class="rp3-d rp3-more"><summary>가격 · 점수 구성 · 다른 화면</summary>
    <dl class="rp3-kv">
      ${pr.price_kind === "known_free" ? `<div><dt>입장료</dt><dd>0원 · 투숙객 무료</dd></div><div><dt>음식 · 프로그램</dt><dd>별도 · 금액 미정</dd></div>` : pr.price_kind === "unknown" ? `<div><dt>입장료</dt><dd>미확인 · 확인 필요</dd></div>` : paid != null ? `<div><dt>1인 금액</dt><dd>${esc(agWon(paid))}${pr.in_package ? " · 객실 포함" : pr.guest_discount_krw ? ` · 할인 ${esc(agWon(pr.guest_discount_krw))}` : ""}</dd></div>` : ""}
      <div><dt>점수 구성</dt><dd><span class="rp3-rv">후기 ${agNum(T.review)}</span> · 공통 ${agNum(T.common)}${T.assumption > 0.01 ? ` · 설계값 ${agNum(T.assumption)}` : ""}</dd></div>
      ${cmpTxt ? `<div><dt>조건 영향</dt><dd>${cmpTxt}</dd></div>` : ""}
      ${pr.party_note ? `<div><dt>금액 기준</dt><dd>${esc(pr.party_note)}</dd></div>` : ""}
    </dl>
    ${(c.avoid || []).length || (c.uncertain || []).length ? `<dl class="rp-dl">${(c.avoid || []).length ? `<div><dt>고르지 않은 곳</dt><dd>${agEvHtml(c.persona_id, c.avoid)}</dd></div>` : ""}${(c.uncertain || []).length ? `<div><dt>불확실</dt><dd>${agEvHtml(c.persona_id, c.uncertain)}</dd></div>` : ""}</dl>` : ""}
    <div class="rp-links"><button type="button" class="rp-link" data-dr="${c.persona_id}">계산 내역 · 다른 후보</button><button type="button" class="rp-link" data-pf="${c.persona_id}">프로파일 · 후기 근거</button>${typeof renderBehavior === "function" ? `<button type="button" class="rp-link rp-link-main ag-bhl" data-bh="${c.persona_id}">행동근거 보기 ›</button>` : ""}</div>
    <div class="rp-more-b">${agDetailTables(R, c, sy, gistOk, chained)}
        ${AG.exp ? `<button type="button" class="rp-link" id="agExpMany">${AG.res._mode === "agents" ? "이 고객 한 명만 보기" : "다른 고객과 비교"}</button>` : ""}</div></details>
    ${!compact && agIsOne(R) ? `<details class="rp3-d rp3-day"><summary>오늘 흐름</summary>${agDayFlow(c.persona_id, AG.si)}</details>` : ""}
  </section>`;
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
  return `<div class="rp-visit"><span class="rp-vk">이번 방문</span><b>${esc(agVisitShort(pid))}</b><span class="rp-tag ${rv ? "rv" : "as"}">${rv ? "후기 경험" : "프로파일 구성"}</span>${noteH(Object.assign({}, AG_VISIT_HELP, { basis: rv ? AG_VISIT_HELP.basis : ["추출 성향", "운영 조건 · 계산"], basis_note: (v.basis && v.basis.facts && v.basis.facts.length ? `연결한 후기 사실: ${v.basis.facts.join(" · ")} · ` : "후기에 숙박 단서가 없어 유형 · 성향으로 구성 · ") + `동행: ${v.layer_party === "review" ? "후기에서 확인" : "유형 기준"}` + (opts ? ` · 고려한 선택지: ${opts}` : "") }))}</div>`;
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
    h += `<section class="ag-blk ag-res"><div class="rp-eye"><span>${esc(R.time || "")} · ${AG_TURN[R.turn]} 선택 · 에이전트 ${cs.length}명${nAll > cs.length ? `<small class="rp-mut"> / ${nAll}명 중 이 시각 호텔에 있는 고객</small>` : ""}</span>${noteH({ what: "고른 에이전트들의 엔진 선택을 업장별로 센 숫자입니다.", basis: ["운영 조건 · 계산"], caution: "실제 방문객 수나 수요 예측이 아닙니다. 에이전트끼리 좌석 · 대기로 서로 영향을 주지 않습니다." })}</div>
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
const agThumb = loc => { const im = typeof placeImg === "function" ? placeImg(loc) : null; return im ? `<img class="ag-th" src="${im.src}" alt="" loading="lazy">` : `<span class="ag-th ag-th0"></span>`; };
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
function agSelCard(id, T) {
  const L = agScenes(id), p = agManyPos(id, T), V = agVC(id), cp = agComp(id, V.party);
  const nowSc = p && !p.away ? (p.moving ? p.to : p.sc) : null, i0 = nowSc ? L.indexOf(nowSc) : -1;
  const nexts = (p && p.away === "pre" ? L : L.slice(i0 + 1)).filter(x => x.k !== "move" && x !== nowSc).slice(0, 3);
  const nowTxt = !p ? "" : p.away === "pre" ? `아직 도착 전 · ${agHM(p.sc.t0)} ${esc(agScLabel(p.sc, id))}부터` : p.away === "post" ? `${agHM(p.sc.t1)} ${esc(agScLabel(p.sc, id))} · 방문 종료` : p.moving ? `${esc(agRo(agPlaceName(p.to.loc, AG.runs[p.to.ti])))} 이동 중 · ${esc(agScLabel(p.to, id))}` : `${esc(agScLabel(p.sc, id))} · ${esc(agPlaceName(p.sc.loc, AG.runs[p.sc.ti]))}`;
  const cat = p && !p.away ? (p.moving ? "move" : agCatOf(p.sc, id)) : "stay";
  return `<section class="ops-blk ops-sel" id="agSelH"><div class="sel-h">${agAvatarIcon(id, V.party, 44)}<div class="sel-b"><div class="sel-t"><b>${esc(dno(id))}</b><span>${esc(cp.label)}</span><button type="button" class="linkbtn" id="agSelOff">선택 해제</button></div>${V.v ? `<div class="sel-v">${esc(agVisitShort(id))}</div>` : ""}</div></div>
    <div class="sel-now" style="--vc:${(AG_CAT[cat] || AG_CAT.room).color}"><span class="sel-k">지금</span><span>${nowTxt}</span>${nowSc && nowSc.k === "turn" ? `<button type="button" class="linkbtn" data-ch="${id}|${nowSc.ti}">선택 이유 ›</button>` : ""}</div>
    ${agSelWhy(id)}
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
    return `<li><b>${esc(AG_TURN[R.turn] || R.turn)}</b><span class="sw-c">${esc(agChoiceName(R, c.choice))}</span><span class="sw-m">${o ? `다음 대안 ${esc(agShort(o.product_label))} · 차 ${agNum(o.margin)}${o.margin < 0.15 ? " · 근소" : ""}` : ""}</span><span class="sw-s ${rv > 0.05 ? "rv" : ""}">${rv > 0.05 ? `후기 근거 +${agNum(rv)}` : "공통 규칙으로 정해짐"}</span><button type="button" class="linkbtn" data-ch="${esc(id)}|${ti}">근거 ›</button></li>`; };
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
function agOpsPanel(T, O) {
  const el = $("#panel"); if (!el || !AG.res) return;
  if (T == null) T = AG.manyT != null ? AG.manyT : agMin(AG.res.time) || 0;
  O = O || agOpsAt(T);
  const n = k => (O.byCat[k] || []).length, fac = n("meal") + n("well") + n("culture") + n("walk");
  const A = `<section class="ops-a"><div class="ops-eye"><span>${agHM(T)} · 에이전트 ${agAllIds().length}명 운영 현황</span>${noteH({ what: "지금 시각에 각 고객이 생성된 하루 계획의 어느 장면에 있는지 센 숫자입니다. 시설 · 식음 = 식음업장 · 수영/사우나/족욕 · 행사/문화 · 산책.", basis: ["운영 조건 · 계산", "추출 성향"], caution: "객실 공급량이 없어 점유율은 만들지 않았고, 가격이 없는 행동(산책 · 시설 이용)에는 매출을 계산하지 않습니다. 고객 수는 시뮬레이션 인원입니다." })}</div>
    <div class="ops-stats"><div><b>${O.present.length}</b><span>체류 중</span></div><div><b>${fac}</b><span>시설 · 식음</span></div><div><b>${O.moving.length}</b><span>이동 중</span></div><div><b>${n("room")}</b><span>객실</span></div><div class="mut"><b>${O.pre.length}</b><span>도착 예정</span></div><div class="mut"><b>${O.post.length}</b><span>방문 종료</span></div></div></section>`;
  const ti = agTurnAt(T), nt = agNextTurn(T);
  const D = ti >= 0 ? agDecisionBlock(ti, T) : nt >= 0 ? `<button type="button" class="ops-next allow-wrap" data-jt="${nt}"><span>다음 주요 결정</span><b>${esc(AG.runs[nt].time)} ${AG_TURN[AG.runs[nt].turn]}</b><small>${AG.runs[nt].customers.length}명 해당 · 누르면 이동</small></button>` : "";
  const inDec = new Set(ti >= 0 ? AG.runs[ti].customers.filter(c => { const p = O.cur[c.persona_id]; return p && !p.p.moving && p.p.sc && p.p.sc.k === "turn"; }).map(c => c.persona_id) : []);   // 결정 중인 고객은 위 결정 블록에서만(중복 없음)
  if (inDec.size) { Object.values(O.byLoc).forEach(L => { L.ids = L.ids.filter(id => !inDec.has(id)); L.acts = {}; L.ids.forEach(id => { const lb = agScLabel(O.cur[id].p.sc, id); L.acts[lb] = (L.acts[lb] || 0) + 1; }); }); Object.keys(O.byCat).forEach(k => O.byCat[k] = O.byCat[k].filter(id => !inDec.has(id))); }
  const cats = AG_CAT_ORDER.filter(k => k !== "move" && n(k));
  const B = `<section class="ops-blk"><div class="ops-h"><b>시설별 활동</b><span>${inDec.size ? `결정 중 ${inDec.size}명 제외` : "지금 누가 어디서 무엇을"}</span></div>${cats.length ? cats.map(k => {
      const locs = Object.values(O.byLoc).filter(L => L.cat === k), rooms = k === "room" ? (() => { const m = {}; locs.forEach(L => { const B = /_ROOM$/.test(L.loc) ? L.loc : "기타"; (m[B] = m[B] || { loc: B, ids: [], acts: {} }).ids.push(...L.ids); Object.entries(L.acts).forEach(([a, c]) => m[B].acts[a] = (m[B].acts[a] || 0) + c); }); return Object.values(m); })() : locs;
      return `<div class="fa-cat" style="--vc:${AG_CAT[k].color}"><div class="fa-ch"><i></i><b>${AG_CAT[k].label}</b><em>${n(k)}명</em></div>${rooms.map(L => `<div class="fa-row">${agThumb(L.loc)}<div class="fa-b"><div class="fa-t"><b>${esc(L.loc === "기타" ? "객실" : agPlaceName(L.loc, AG.res))}</b><em>${L.ids.length}</em></div><div class="fa-a">${esc(Object.entries(L.acts).sort((a, b) => b[1] - a[1]).map(([a, c]) => c > 1 ? `${a} ${c}` : a).join(" · "))}</div><div class="dc-ids">${L.ids.map(agChip).join("")}</div></div></div>`).join("")}</div>`; }).join("") : `<div class="hint">${inDec.size ? "모든 체류 고객이 주요 결정 중입니다." : "지금 호텔 안에 머무는 고객이 없습니다."}</div>`}
    ${O.moving.length ? `<div class="fa-cat" style="--vc:${AG_CAT.move.color}"><div class="fa-ch"><i></i><b>이동 중</b><em>${O.moving.length}명</em></div><div class="fa-mv">${O.moving.map(([id, p]) => `<span>${agChip(id)}<small>→ ${esc(p.to ? agPlaceName(p.to.loc, AG.runs[p.to.ti]) : "")}</small></span>`).join("")}</div></div>` : ""}</section>`;
  const F = agFeedGroup(agFeed(T, 150, 14)).slice(0, 7);
  const C = `<section class="ops-blk"><div class="ops-h"><b>실시간 행동</b><span>방금 시작 · 끝난 · 바뀐 행동</span></div>${F.length ? `<ul class="ops-feed">${F.map(e => `<li class="${e.key ? "key" : ""}" style="--vc:${(AG_CAT[e.cat] || AG_CAT.room).color}"><time>${agHM(e.t)}</time>${e.ids ? `<span class="ag-idn">${e.ids.length}명</span>` : agChip(e.id)}<span>${esc(e.txt)}</span></li>`).join("")}</ul>` : `<div class="hint">최근 2시간 사이 시작한 활동이 없습니다.</div>`}</section>`;
  const E = AG.visits ? `<details class="ops-blk ops-e"${AG._eOpen ? " open" : ""}><summary><b>고객 방문 조건</b><span>${agAllIds().length}명이 각자 정한 숙박 · 방문 · 동행</span></summary>${agVisitDist()}</details>` : "";
  const S = AG.sel && agAllIds().includes(AG.sel) ? agSelCard(AG.sel, T) : "";
  const keep = el.scrollTop;
  // P6 — 고객을 고르면 그 고객의 결정이 먼저 보이게: 시설별 활동 · 실시간 행동은 접어 둔다(펼치면 그대로)
  const BC = S ? `<details class="ops-fold"${AG._fOpen ? " open" : ""}><summary><b>시설별 활동 · 실시간 행동</b><span>지금 호텔 전체 보기</span></summary>${B}${C}</details>` : B + C;
  el.innerHTML = `<div class="ops">${A}${S}${ti >= 0 ? D + BC : BC + D}${E}</div>`;
  if (typeof rcMountPanel === "function") rcMountPanel();
  el.scrollTop = keep;
  $$("#panel [data-p]").forEach(b => b.onclick = ev => { ev.stopPropagation(); agSelect(b.dataset.p); });
  $$("#panel [data-dr]").forEach(b => b.onclick = () => agDecisionDrawer(+b.dataset.dr));
  $$("#panel [data-cd]").forEach(b => b.onclick = () => agCustDrawer(b.dataset.cd));
  $$("#panel [data-ch]").forEach(b => b.onclick = () => { const [id, t] = b.dataset.ch.split("|"); agChoiceDrawer(id, +t); });
  $$("#panel [data-jt]").forEach(b => b.onclick = () => agManyJump(agMin(AG.runs[+b.dataset.jt].time)));
  const so = $("#agSelOff"); if (so) so.onclick = () => { AG.sel = null; if (AG.keep[AG.mode]) AG.keep[AG.mode].sel = null; agManyRender(T); agStrip(); };
  const ed = $("#panel .ops-e"); if (ed) ed.ontoggle = () => { AG._eOpen = ed.open; };
  const fo = $("#panel .ops-fold"); if (fo) fo.ontoggle = () => { AG._fOpen = fo.open; };
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
function agCustDrawer(pid, tab = "ov") {
  const p = (AG.meta.personas || []).find(x => x.id === pid), lp = agLibP(pid) || {}, V = agVC(pid), cp = agComp(pid, V.party), pt = agPortrait(pid, V.party);
  const seenG = new Set(), F = Object.entries((lp.engine && lp.engine.facts) || {}).filter(([, f]) => !f.hidden && f.gist && !seenG.has(f.gist) && seenG.add(f.gist)).map(([id, f]) => Object.assign({ id }, f));   // 같은 요지(사건 분할 사실) 한 번만
  const whF = F.filter(f => f.wh), cons = whF.filter(f => ["purchase", "participation"].includes(f.kind)).slice(0, 5), dec = F.filter(f => f.kind === "decline").slice(0, 3);
  const counters = (lp.traits || []).flatMap(t => (t.counter || []).map(c => ({ t: t.trait, c }))).slice(0, 3);
  const rules = (lp.rules || []).slice(0, 3);
  const L = AG.res ? agScenes(pid) : [], T = AG.manyT != null && agIsMany(AG.res) ? AG.manyT : AG.nowMin;
  // CL-1024-12 §3 — 오늘 일정: 시간축 목록(시간 · 활동 · 장소 · 이유 한 줄 · 주요 결정 표시). 주요 소비 결정은 굵게 강조, 휴식 · 이동성 활동은 조용히
  const day = L.filter(x => x.k !== "move").map(x => { const cat = agCatOf(x, pid), now = T != null && T >= x.t0 && T < x.t1, key = x.k === "turn", R = AG.runs[x.ti], c = key && R ? agCustOf(R, pid) : null;
    const what = key && c ? agTurnAct(R, c.choice) : agScLabel(x, pid), quiet = !key && ["rest"].includes(x.kind);
    return `<li class="${key ? "key" : ""}${now ? " now" : ""}${quiet ? " quiet" : ""}" style="--vc:${AG_CAT[cat].color}" tabindex="0" ${key ? `data-ch="${pid}|${x.ti}"` : `data-act="${x.si}"`}><time>${agHM(x.t0)}</time><i class="cd-dot"></i><div class="cd-b"><div class="cd-t"><b>${esc(what)}</b>${key ? `<em class="cd-key">주요 결정</em>` : x.src === "review" ? `<em class="cd-rv">후기 경험</em>` : ""}</div><small>${esc(agPlaceName(x.loc, R))} · ${Math.round(x.t1 - x.t0)}분</small>${x.why && !quiet ? `<p>${esc(x.why)}</p>` : ""}</div><span class="cd-go">›</span></li>`; }).join("");
  const ov = `<div class="cd-sec"><h4>핵심 성향</h4>${p ? agBars(p.bars) : ""}<div class="hint">막대 = 엔진이 쓰는 성향 수준 · 근거 = 연결된 후기 사실 수</div></div>
    ${cons.length ? `<div class="cd-sec"><h4>대표 소비 · 이용 행동</h4><ul class="cd-list">${cons.map(f => `<li><span>${esc(f.gist)}</span><em>${esc(AG_KIND_KO[f.kind] || "")}</em></li>`).join("")}</ul></div>` : ""}
    ${counters.length || dec.length ? `<div class="cd-sec"><h4>주요 반례 · 하지 않은 것</h4><ul class="cd-list">${counters.map(x => `<li><span>${esc(x.c)}</span><em>성향 '${esc(x.t.slice(0, 18))}…' 의 반례</em></li>`).join("")}${dec.map(f => `<li><span>${esc(f.gist)}</span><em>거절 · 안 함</em></li>`).join("")}</ul></div>` : ""}
    ${rules.length ? `<div class="cd-sec"><h4>행동 규칙(검증 전 가설)</h4><ul class="cd-list">${rules.map(r => `<li><span><b>${esc(r.condition)}</b> → ${esc(r.hypothesis)}</span><em>근거 ${r.evidence || 0}건</em></li>`).join("")}</ul></div>` : ""}`;
  const ev = `<div class="hint">구조화 사실의 요지입니다(원문 · 작성자 정보는 싣지 않음). 워커힐 방문 사실을 먼저, 다른 숙박 · 여행 경험은 뒤에 둡니다.</div><ul class="cd-list cd-ev">${[...whF, ...F.filter(f => !f.wh)].slice(0, 40).map(f => `<li><span>${esc(f.gist)}</span><em>${f.wh ? "워커힐 · " : ""}${esc(AG_KIND_KO[f.kind] || "사실")} · ${esc(f.id)}</em></li>`).join("")}</ul>${F.length > 40 ? `<div class="hint">외 ${F.length - 40}건 — 라이브러리 화면에서 전체 보기</div>` : ""}`;
  const head = `<div class="cd-head">${pt ? `<img class="cd-pt" src="${pt}" alt="">` : `<span class="cd-pt cd-pt0">${agAvatarIcon(pid, V.party, 64)}</span>`}<div><div class="cd-id"><b>${esc(dno(pid))}</b><span>${esc(lp.type_group || lp.type || "")}</span></div>${lp.label ? `<p class="cd-lab">${esc(lp.label)}</p>` : ""}
      <dl class="cd-dl"><div><dt>이번 방문</dt><dd>${V.v ? esc(agVisitShort(pid)) : `${V.stay ? esc(V.bl) + " 투숙" : "비투숙"} · ${V.party}인`}${V.v ? ` <span class="rp-tag ${V.v.layer_stay === "review" ? "rv" : "as"}">${V.v.layer_stay === "review" ? "후기 경험" : "프로파일 구성"}</span>` : ""}</dd></div><div><dt>동행</dt><dd>${esc(cp.label)}${cp.src && !cp.match ? ` <span class="hint">(원문: ${esc(cp.src)})</span>` : ""}</dd></div>${p ? `<div><dt>핵심 성향</dt><dd>${esc(p.bars.filter(b => b.status === "observed").sort((a, b) => b.level - a.level).slice(0, 3).map(b => b.label).join(" · ") || "후기 근거 성향 없음")}</dd></div>` : ""}</dl>
      <div class="hint cd-avn">${esc(AG_AV_NOTE)}</div></div></div>`;   // 자산 관리 상태(MAPPED 등)는 고객 설명에 싣지 않는다 — 개발 정보에서만
  const h = head + agTabs([["ov", "개요"], ["day", "오늘 일정"], ["ev", "후기 근거"]], tab) +
    `<div data-pane="ov"${tab === "ov" ? "" : ' class="hidden"'}>${ov}</div><div data-pane="day"${tab === "day" ? "" : ' class="hidden"'}><ol class="cd-day">${day || `<li>실행 결과가 없습니다.</li>`}</ol>${AG.plans && AG.plans[pid] ? `<div class="hint">${esc(agPlanMetaText(AG.plans[pid]))}</div>` : ""}</div><div data-pane="ev"${tab === "ev" ? "" : ' class="hidden"'}>${ev}</div>
    <div class="cd-foot"><button type="button" class="linkbtn" id="cdLib">라이브러리에서 전체 프로파일 열기 ↗</button><span class="hint">시뮬레이션 화면을 떠납니다</span></div>`;
  openDrawer(`${dno(pid)} · 고객 상세`, lp.type_group || "", h, root => {
    agTabWire(root);
    agQ(root, "[data-ch]").forEach(b => b.onclick = () => { const [id, t] = b.dataset.ch.split("|"); agChoiceDrawer(id, +t); });
    agQ(root, "[data-act]").forEach(b => b.onclick = () => agActDrawer(pid, +b.dataset.act));
    agQ(root, ".cd-day li").forEach(li => li.onkeydown = e => { if (e.key === "Enter") li.click(); });
    const lb = root.querySelector("#cdLib"); if (lb) lb.onclick = () => { AG._drResume = false; closeDrawer(); agToProfile(pid); };
  }, { wide: true });
}
function agChoiceDrawer(pid, ti) {   // 선택 상세 — 기존 계산 내역 드로어에 '핵심 이유 · 개인/공통 기여 · 근소 여부'를 앞에 붙인다
  const keepR = AG.res, keepTi = AG.ti, R = AG.runs[ti] || AG.res; if (!R) return;
  const c = R.customers.find(x => x.persona_id === pid); if (!c) return;
  AG.res = R; AG.ti = ti;
  try { agDrawer(pid); } finally { AG.res = keepR; AG.ti = keepTi; }
  const body = $("#drBody"); if (!body) return;
  { const dw = $("#drawer"); if (dw) dw.classList.add("ag-narrow"); }
  if (typeof bhFromFlow === "function") setTimeout(() => { const b = $("#drBody"); if (!b || b.querySelector(".ag-tobh")) return; const x = document.createElement("div"); x.className = "ag-tobh"; x.innerHTML = `<button type="button" class="cf-btn cf-sm">행동근거에서 단계별로 보기 ›</button><span class="hint">원문 → 사실 → 성향 → 조건 → 결정</span>`; x.querySelector("button").onclick = () => { closeDrawer(); bhFromFlow(pid, ti); }; b.insertBefore(x, b.firstChild); }, 0);   // CL-1025-37 P2 — 결정 패널은 폭을 줄여 지도 · 이동 장면을 가리지 않는다
  // CL-1024-12 §3 — 정보 순서: ①상품 · 업장 이미지 ②핵심 이유 ③비교 대안 ④가격 · 혜택 · 운영 조건 ⑤개인/공통 기여 ⑥상세 점수 · 원문 근거(아래 기존 내용)
  const o = c.best_other_venue, near = o && o.margin < 0.15, T = c.reason_totals, sy = agSentence(c), ch = c.choice, pr = ch.price || {};
  const im = typeof placeImg === "function" ? placeImg(ch.map_loc) : null, cc = R.compare && R.compare.customers.find(y => y.persona_id === pid);
  const lev = (R.cond && R.cond.product_levers) ? Object.entries(R.cond.product_levers).filter(([k]) => k === ch.product_id) : [];
  const priceTxt = pr.paid_krw != null ? `실결제 1인 ${agWon(pr.paid_krw)}` : pr.pp_krw != null ? `1인 ${agWon(pr.pp_krw)}` : "가격 정보 없음(이용 · 비소비 선택)";
  const top = document.createElement("div"); top.className = "ag-ch-top";
  top.innerHTML = `<div class="ch-hero">${im ? `<img src="${im.src}" alt="${esc(im.name)}">` : ""}<div><small>${esc(R.time)} ${esc(AG_TURN[R.turn])} · 선택</small><b>${esc(agVenueTitle(R, ch, pid))}</b><span>${esc(agMenuTitle(R, ch))}</span>${cc && cc.status === "changed" ? `<em class="ag-chg">운영 조건 변경으로 바뀜 · 전 ${esc(agShort(cc.before.product_label))}</em>` : ""}</div></div>
    <section class="ch-sec"><h4>핵심 이유</h4>${sy.p}</section>
    <section class="ch-sec"><h4>비교 대안</h4>${o ? `<p>다른 업장 최고 대안은 <b>${esc(agChoiceName(R, o))}</b>, 점수 차 ${agNum(o.margin)}.</p>${near ? `<div class="ag-ch-alt near"><b>근소한 차이</b> — 강한 선호로 보지 않습니다. 조건이 조금만 바뀌어도 선택이 바뀔 수 있습니다.</div>` : ""}` : `<p class="hint">비교할 다른 업장 후보가 없습니다.</p>`}</section>
    <section class="ch-sec"><h4>가격 · 혜택 · 운영 조건</h4><p>${esc(priceTxt)}${lev.length ? ` · 이번 운영 조건 적용` : ""}${R.cond && R.cond.pricing && R.cond.pricing !== "historical" ? ` · 가격 기준 ${esc(R.cond.pricing)}` : ""}</p></section>
    <section class="ch-sec"><h4>개인 근거와 공통 계산</h4><div class="ag-ch-tot"><span><i class="s-review"></i>개인 후기 근거 <b>${agNum(T.review)}</b></span><span><i class="s-common"></i>공통 계산 <b>${agNum(T.common)}</b></span>${T.assumption ? `<span><i class="s-assumption"></i>설계 가정 <b>${agNum(T.assumption)}</b></span>` : ""}${T.transfer ? `<span><i class="s-transfer"></i>맥락 이전 추론 <b>${agNum(T.transfer)}</b></span>` : ""}${T.out_of_scope ? `<span class="dev-only"><i class="s-out_of_scope"></i>출처 충돌 <b>${agNum(T.out_of_scope)}</b></span>` : ""}</div>${c.product_direct_visits === 0 ? `<p class="hint">이 상품 직접 이용 근거 없음(직접 이용 0회)</p>` : ""}</section>
    <h4 class="ch-more">상세 점수 · 원문 근거</h4>`;
  body.insertBefore(top, body.firstChild);
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
    ${sc.why ? `<section class="ad-sec"><h4>왜 이 활동인가</h4><p>${esc(sc.why)}</p>${sc.cond_dep ? `<p class="ad-warn">운영 조건 변경 뒤 기준 조건의 하루와 달라진 장면입니다.</p>` : ""}</section>` : ""}
    <section class="ad-sec"><h4>앞뒤 흐름</h4><ol class="ad-flow">${row(prev, "앞")}${row(sc, "지금")}${row(next, "다음")}</ol></section>
    <section class="ad-sec"><h4>연결한 후기 사실</h4>${facts.length ? `<ul class="ad-facts">${facts.map(([f, g]) => `<li><p>${esc(g)}</p><small>${esc(f)} · 요지(원문 인용 아님)</small></li>`).join("")}</ul>` : `<p class="ad-mut">직접 연결된 후기 사실은 없습니다 — 성향 · 동행 · 앞선 활동 · 영업시간으로 구성했습니다.</p>`}</section>
    <p class="ad-mut">${esc(agPlanMetaText(AG.plans && AG.plans[pid]))}</p></div>`;
  openDrawer(`${dno(pid)} · ${agHM(sc.t0)} ${sc.short || sc.label}`, "활동 상세", h, root => {}, {});
}
function agPlanMetaText(pm) {
  if (!pm) return "행동 계획기 결과 없음";
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
  if (!t.closest("#agStay button, #agTurn button, #agMany [data-p], #agSelAll, #agSelNone, #agShowSel, #agShowAdd, #agReset, #agExpOff, .pe-adj, .pe-step")) return;
  setTimeout(agStale, 0);
}, true);
