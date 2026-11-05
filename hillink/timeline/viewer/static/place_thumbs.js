// 10/17 시설 썸네일 — 업장 상세(장소를 눌렀을 때)와 손님 한 팀 '하루 일정' 에 장소 이미지를 붙인다.
//   이미지 목록은 static/place_img/manifest.json 하나로 관리한다 (파일 · 종류 · 출처 · 사용 권한).
//   목록이 비어 있으면 화면을 바꾸지 않는다 → 이미지가 준비되기 전 시연 화면은 그대로.
//   목록에 이미지가 하나라도 있으면: 있는 곳은 작은 이미지(지연 로딩), 없는 곳은 시설 종류 아이콘을 보인다.
//   실제 사진이 아닌 이미지는 '콘셉트 이미지' 표지를 단다. 사용 허락이 확인되지 않은 사진은 목록에 넣지 않는다.
//   계산 · 캐시와 무관한 표시 전용 파일이며 app.js 를 고치지 않고 #panel 변화만 보고 덧붙인다.
(function () {
  "use strict";
  const BASE = "/static/place_img/";
  const assetURL = it => BASE + encodeURIComponent(it.file) + (it.revision ? "?v=" + encodeURIComponent(it.revision) : "");
  const BADGE = { concept: "콘셉트 이미지", team_photo: "팀 촬영 사진", official_permitted: "공식 사진 · 사용 허락" };
  // 시설 종류 → 아이콘 (이미지가 없을 때)
  const CAT = {
    dining: ["THE_BUFFET", "PIZZA_HILL", "MYONGWOLGWAN", "GEUMRYONG", "ONDAL", "MOEGI", "THE_PAVILION", "LE_PASSAGE"],
    bar: ["LUX_BAR", "GRAND_CLUB_LOUNGE", "DOUGLAS_LOUNGE"],
    room: ["GRAND_ROOM", "VISTA_ROOM", "DOUGLAS_ROOM"],
    leisure: ["GRAND_POOL", "VISTA_POOL", "WELLNESS_SAUNA", "FITNESS", "VISTA_FITNESS", "GOLF_CLUB", "TENNEZ_PARK"],
    culture: ["THEATRE_OF_LIGHT", "THEATRE_ART_SHOP", "FOREST_PARK", "SKYARD", "RIVERPARK", "GRAND_LIBRARY", "DOUGLAS_LIBRARY", "CONVENTION"],
  };
  const catOf = loc => Object.keys(CAT).find(k => CAT[k].includes(loc)) || "place";
  const ICON = {
    dining: '<path d="M7 3v8M5 3v4a2 2 0 0 0 4 0V3M7 11v10M16 3c-2 0-3 2-3 5s1 4 3 4v9" />',
    bar: '<path d="M5 4h14l-7 8zM12 12v7M8 20h8" />',
    room: '<path d="M3 18V8M3 14h18v4M21 18v-4a3 3 0 0 0-3-3H9v3M6 11.5a1.5 1.5 0 1 0 0-.01" />',
    leisure: '<path d="M3 16c2 0 2 1.5 4.5 1.5S10 16 12 16s2 1.5 4.5 1.5S19 16 21 16M3 12c2 0 2 1.5 4.5 1.5S10 12 12 12s2 1.5 4.5 1.5S19 12 21 12M8 9V4M16 9V4" />',
    culture: '<path d="M12 3l2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.8z" />',
    place: '<path d="M12 21s-6-5.6-6-11a6 6 0 0 1 12 0c0 5.4-6 11-6 11zM12 12.5a2.5 2.5 0 1 0 0-.01" />',
  };
  const svg = c => `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICON[c] || ICON.place}</svg>`;
  const esc2 = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let M = null;   // { LOC: {file, kind, credit, license} }
  let X = {};     // 상황별 · 동선 종료 이미지 (at · when · use)

  async function load() {
    try {
      const r = await fetch(BASE + "manifest.json", { cache: "no-cache" });
      const j = r.ok ? await r.json() : {};
      const items = j.items || {};
      M = {}; X = {};
      for (const [loc, it] of Object.entries(items)) if (it && it.file && BADGE[it.kind]) (it.at || it.use ? X : M)[loc] = it;
    } catch (e) { M = {}; X = {}; }
  }
  // 상황에 따라 바뀌는 이미지 — 와인페어 날 포레스트 파크는 와인페어 이미지 (at · when)
  const scen = () => { try { if (typeof MODE !== "undefined" && MODE === "guest" && G) return G.scenario; if (typeof DAY !== "undefined" && DAY) return DAY.scenario; } catch (e) {} return null; };
  // 10/18 · 와인페어 행동은 venue 코드가 WINE_FAIR(자리는 FOREST_PARK)라 장소 코드로는 그림을 못 찾던 문제 — 상황 이미지의 키(WINE_FAIR)와 같으면 그 그림
  const itemFor = loc => { if (X[loc] && X[loc].at) return X[loc]; const sc = scen(); for (const it of Object.values(X)) if (it.at === loc && (!it.when || it.when === sc)) return it; return M[loc]; };
  const endItem = () => Object.values(X).find(it => it.use === "route_end") || null;
  const arrItem = () => Object.values(X).find(it => it.use === "arrival") || null;
  const active = () => M && Object.keys(M).length > 0;
  const nameOf = loc => { try { return (typeof locName === "function" ? locName(loc) : loc); } catch (e) { return loc; } };

  // 업장 상세 — '← 돌아가기' 다음 카드의 장소 코드(span.hint)로 장소를 알아낸다
  function decoratePlace(panel) {
    const card = panel.querySelector(":scope > button.back + .card");
    if (!card || card.dataset.pthumb) return;
    const hint = card.querySelector(":scope > span.hint");
    const loc = hint && /^[A-Z][A-Z0-9_]+$/.test(hint.textContent.trim()) ? hint.textContent.trim() : null;
    if (!loc) return;
    card.dataset.pthumb = "1";
    const it = itemFor(loc);
    const fig = document.createElement("figure");
    fig.className = "pthumb" + (it ? "" : " none");
    fig.innerHTML = it
      ? `<img src="${assetURL(it)}" alt="${esc2(nameOf(loc))} ${esc2(BADGE[it.kind])}" loading="lazy" decoding="async" width="${it.width || 400}" height="${it.height || 300}"><figcaption><small>${esc2(it.credit || BADGE[it.kind])}</small></figcaption>`
      : `<span class="pt-icon">${svg(catOf(loc))}</span><figcaption><small>이미지 준비 중</small></figcaption>`;
    const img = fig.querySelector("img");
    if (img) img.onerror = () => { fig.className = "pthumb none"; fig.innerHTML = `<span class="pt-icon">${svg(catOf(loc))}</span><figcaption><small>이미지를 불러오지 못함</small></figcaption>`; };
    card.appendChild(fig);
  }

  // 손님 한 팀 '하루 일정' — 줄마다 장소 코드는 G.st[i] 에서 (app.js 의 전역 G)
  function decorateItin(panel) {
    const ul = panel.querySelector("ul.itin");
    if (!ul || ul.dataset.pthumb || ul.classList.contains("withph")) return;   // 로컬 사진(photos.local)이 이미 붙은 경우 그대로 둔다
    let st = null;
    try { st = (typeof G !== "undefined" && G && G.st) ? G.st : null; } catch (e) { st = null; }
    if (!st) return;
    ul.dataset.pthumb = "1";
    ul.classList.add("withph");
    let lastRoom = null;   // 객실은 같은 객실이 이어지면 첫 줄에만
    let lastDesk = null;
    for (const li of ul.querySelectorAll(":scope > li[data-i]")) {
      const s = st[+li.dataset.i]; if (!s) continue;
      const loc = s.venue || s.location, isRoom = s.kind === "room";
      // 체크인 · 체크아웃 줄(로비 · 프런트)은 이미지가 있을 때만 붙인다 — 없는 곳에 아이콘을 늘어놓지 않으려고
      const desk = (s.kind === "checkin" || s.kind === "checkout") && !!itemFor(loc) && loc !== lastDesk;   // 같은 곳이 이어지면 첫 줄에만
      lastDesk = (s.kind === "checkin" || s.kind === "checkout") ? loc : null;
      const show = desk || s.kind === "meal" || s.kind === "facility" || s.kind === "event" || (isRoom && loc !== lastRoom);
      if (isRoom) lastRoom = loc;
      const it = show ? itemFor(loc) : null;
      const el = document.createElement(it ? "img" : "i");
      if (it) {
        el.className = "ithumb"; el.src = assetURL(it); el.alt = ""; el.loading = "lazy"; el.decoding = "async";
        el.title = `${nameOf(loc)} · ${BADGE[it.kind]}`;
        el.onerror = () => { const i = document.createElement("i"); i.className = "ithumb none pt-mini"; i.innerHTML = svg(catOf(loc)); el.replaceWith(i); };
      } else if (show) { el.className = "ithumb none pt-mini"; el.title = "이미지 준비 중"; el.innerHTML = svg(catOf(loc)); }
      else el.className = "ithumb blank";
      li.insertBefore(el, li.children[1] || null);
    }
  }

  function run() {
    if (!active()) return;
    const panel = document.getElementById("panel");
    if (!panel) return;
    decoratePlace(panel);
    decorateItin(panel);
  }

  // 지도 위 방문 카드 — 손님이 장소에 도착하면 뜨는 카드. app.js 의 drawVisitCard 를 감싸서,
  //   로컬 사진(photos.local)이 없는 장소에만 콘셉트 이미지를 넣고 표지를 '콘셉트 이미지' 로 바꾼다.
  //   경로 '../static/place_img/…' 는 브라우저가 '/static/place_img/…' 로 정리하므로 서버 수정이 필요 없다.
  function hookVisitCard() {
    if (window.__ptVC || typeof drawVisitCard !== "function") return;
    const orig = drawVisitCard; window.__ptVC = true;
    window.drawVisitCard = function (moving) {
      try {
        if (typeof MAPPH !== "undefined" && MAPPH) {
          MAPPH.official = MAPPH.official || {}; MAPPH.credit = MAPPH.credit || {};
          const ours = f => /place_img\//.test(f || "");
          const set = (loc, it) => {
            const f = ".." + assetURL(it), cur = MAPPH.official[loc] || [];
            if (!cur.length || ours(cur[0])) MAPPH.official[loc] = [f];   // 로컬 사진이 있으면 그대로 · 우리 이미지끼리는 상황에 맞게 바꾼다
            if (MAPPH.official[loc][0] === f) MAPPH.credit[f] = it.credit || "";
          };
          for (const loc of new Set([...Object.keys(M), ...Object.values(X).map(it => it.at).filter(Boolean)])) { const it = itemFor(loc); if (it) set(loc, it); }
          const e = endItem(); if (e) set("ROUTE_END", e);
        }
      } catch (e) {}
      const r = orig.apply(this, arguments);
      try {
        const card = document.getElementById("visitCard"), img = card && card.querySelector("img");
        if (img && /place_img\//.test(img.getAttribute("src") || "")) {
          // 빨간 표지 = 장소 이름 · 맨 아래 한 줄 = '콘셉트 이미지 · 실제 사진 아님' (목록의 credit)
          const file = (img.getAttribute("src") || "").split("/").pop().split("?")[0];
          const ent = [...Object.entries(X), ...Object.entries(M)].find(([, it]) => it.file === file);
          const loc = ent ? ent[0] : null, name = ent ? (ent[1].name || nameOf(loc)) : "";
          const tag = card.querySelector(".vc-src");
          if (tag && !tag.dataset.pt) {
            tag.textContent = name; tag.className = "vc-src concept"; tag.dataset.pt = "1";
            const bold = card.querySelector(".vc-meta b");
            if (bold && name && (name.includes(bold.textContent.trim()) || bold.textContent.trim() === name)) bold.remove();
          }
        }
      } catch (e) {}
      return r;
    };
  }

  async function init() {
    await load();
    if (!active()) return;   // 이미지가 없으면 아무것도 바꾸지 않는다
    hookVisitCard();
    try { if (typeof VCKEY !== "undefined") VCKEY = ""; } catch (e) {}
    const panel = document.getElementById("panel");
    if (!panel) return;
    new MutationObserver(() => run()).observe(panel, { childList: true });
    run();
  }
  window.PLACE_THUMBS = { url: assetURL, reload: async () => { await load(); run(); }, list: () => M, extra: () => X, pick: loc => (M ? itemFor(loc) : null), end: () => endItem(), arrival: () => arrItem() };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
