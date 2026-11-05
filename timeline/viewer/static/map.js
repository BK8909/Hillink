// 워커힐 지도 — 바탕 그림 static/map_base.png (1564 × 1006 · 10/17 14차 · 투명 배경 · 나무를 줄이고 건물 클레이 입체감을 살린 그림 · 건물 · 길 배치는 10/17 v3 그림과 같아 좌표를 그대로 씀(길 점 대조 0.75 동일)).
//   좌표는 화면 좌표(1000 × 643)이고 실제 축척이 아니다. 건물 · 길의 위치를 원본 그림 좌표로 적고 S() 로 줄인다. 이름표는 그림에 합성하지 않고 #labels 층에서 그린다.
//   온달 · 금룡 등 본관 안 업장은 그랜드 본관 자리. 별관 · '정문' 길은 없음(공식 미니맵에 없음). 출입구는 South Gate(왼쪽 위) · East Gate(왼쪽).
// 이동 시간은 모델(검증기 구내 이동 매트릭스)이 정하고, 여기 길은 "어디로 지나가나"를 보여 주는 그림일 뿐이다.

const MAP_W = 1000, MAP_H = 643, IMG_W = 1564;   // 1006 × 1000 / 1564 = 643
const S = ([x, y]) => [Math.round(x * MAP_W / IMG_W), Math.round(y * MAP_W / IMG_W)];
const mapObj = o => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, S(v)]));

// 장소 코드 → 지도 위 점 (원본 그림 좌표)
const LOC = mapObj({
  HOTEL_GATE: [362, 840], VALET_DESK: [745, 690], PARKING_TOWER_B1: [715, 500], PARKING_TOWER_4F: [737, 478], GRAND_LOBBY: [760, 668], GRAND_FRONT_DESK: [782, 674],
  GRAND_ROOM: [760, 590], GRAND_CLUB_LOUNGE: [766, 560], GRAND_LIBRARY: [726, 658], THE_PAVILION: [712, 650], GEUMRYONG: [802, 650], LE_PASSAGE: [742, 692],
  LUX_BAR: [812, 624], GRAND_POOL: [770, 628], FITNESS: [742, 616], WELLNESS_SAUNA: [790, 604], ONDAL: [786, 640], THEATRE_OF_LIGHT: [772, 726],
  THEATRE_ART_SHOP: [742, 742], CU_THEATRE: [806, 746], CONVENTION: [700, 672], RIVERPARK: [1086, 764], VISTA_LOBBY: [666, 776], VISTA_ROOM: [640, 690],
  VISTA_POOL: [590, 760], VISTA_FITNESS: [606, 782], SKYARD: [652, 716], THE_BUFFET: [692, 790], MOEGI: [712, 770], ANNEX: [700, 618],
  PIZZA_HILL: [352, 402], MYONGWOLGWAN: [222, 626], DOUGLAS_LOBBY: [802, 422], DOUGLAS_ROOM: [842, 400], DOUGLAS_LOUNGE: [770, 432], DOUGLAS_LIBRARY: [872, 436],
  FOREST_PARK: [1120, 382], GOLF_CLUB: [1410, 562], TENNEZ_PARK: [990, 722], GWANGNARU_STN: [362, 840], GANGBYEON_STN: [362, 840], ICN_T1: [362, 840],
  ICN_T2: [362, 840],
});

// 길 — 그림의 흰 길을 따라 찍은 점 (s South Gate 길 · k 왼쪽 길 → 명월관 → 비스타 서쪽 · p 피자힐 둘레 · d 피자힐 → 더글라스 → 정자 · e East Gate(왼쪽 아래 출구) · n 그랜드 북쪽 → 정자 · f 그랜드 정면 → 테네즈 · w 그랜드 동쪽 → 리버파크 · g · h 정자 둘레 → 애스톤 · q 그랜드 북쪽 → 주차타워 → 더글라스). 장소는 가장 가까운 점에 붙는다
const NODE = mapObj({
  s0: [100, 295], s1: [160, 303], s2: [230, 325], s3: [300, 348], s4: [370, 372], s5: [430, 392], s6: [480, 402], s7: [520, 405],
  d0: [520, 405], d1: [560, 335], d2: [620, 320], d3: [680, 325], d4: [740, 345], d5: [800, 368], d6: [850, 388], d7: [905, 405],
  d8: [960, 452], d9: [1020, 472], d10: [1080, 490], d11: [1140, 520], d12: [1204, 552], p0: [520, 405], p1: [526, 445], p2: [526, 488],
  p3: [506, 524], p4: [474, 546], p5: [440, 556], p6: [402, 574], p7: [386, 620], p8: [400, 665], p9: [432, 700], p10: [472, 716],
  k0: [160, 303], k1: [135, 345], k2: [120, 400], k3: [118, 470], k4: [128, 520], k5: [145, 560], k6: [178, 594], k7: [225, 618],
  k8: [275, 652], k9: [330, 688], k10: [385, 710], k11: [440, 716], k12: [472, 716], k13: [500, 720], k14: [530, 725], k15: [560, 730],
  e0: [365, 835], e1: [427, 783], e2: [467, 743], e3: [507, 724], n0: [474, 546], n1: [540, 545], n2: [600, 540], n3: [660, 538],
  n4: [720, 533], n5: [780, 530], n6: [836, 525], n7: [900, 508], n8: [964, 512], n9: [1040, 545], n10: [1110, 580], n11: [1160, 580],
  n12: [1204, 552], f0: [600, 545], f1: [588, 600], f2: [600, 640], f3: [635, 665], f4: [690, 680], f5: [730, 690], f6: [760, 712],
  f7: [800, 722], f8: [850, 720], f9: [900, 712], f10: [952, 702], w0: [805, 533], w1: [870, 582], w2: [905, 600], w3: [950, 620],
  w4: [1000, 640], w5: [1022, 652], w6: [1055, 690], w7: [1100, 720], w8: [1140, 758], w9: [1180, 790], w10: [1220, 800], w11: [1270, 790],
  g0: [1204, 552], g1: [1196, 576], g2: [1204, 640], g3: [1212, 688], g4: [1228, 720], g5: [1260, 744], g6: [1324, 760], g7: [1388, 776],
  q0: [720, 533], q1: [712, 486], q2: [712, 445], q3: [716, 395], q4: [735, 358], h0: [1204, 552], h1: [1260, 592], h2: [1324, 640],
  h3: [1380, 696], h4: [1404, 752], h5: [1396, 768], h6: [1388, 776],
  // 10/17 · 비스타 서쪽에서 그랜드 북쪽 길로 올라가는 대각선 길 (그림의 흰 길). 건물 진입부는 건물에 닿은 길 위 점 — 그랜드 w0(북동쪽 길 갈림) · 비스타 v1(북서쪽 길) · 더글라스 d6 · 시어터 f8
  v0: [480, 694], v1: [540, 662], v2: [600, 615], v3: [650, 575], v4: [690, 526],
});
const EDGES = [
  ["s0", "s1"], ["s1", "s2"], ["s2", "s3"], ["s3", "s4"], ["s4", "s5"], ["s5", "s6"], ["s6", "s7"], ["d0", "d1"], ["d1", "d2"], ["d2", "d3"],
  ["d3", "d4"], ["d4", "d5"], ["d5", "d6"], ["d6", "d7"], ["d7", "d8"], ["d8", "d9"], ["d9", "d10"], ["d10", "d11"], ["d11", "d12"], ["p0", "p1"],
  ["p1", "p2"], ["p2", "p3"], ["p3", "p4"], ["p4", "p5"], ["p5", "p6"], ["p6", "p7"], ["p7", "p8"], ["p8", "p9"], ["p9", "p10"], ["k0", "k1"],
  ["k1", "k2"], ["k2", "k3"], ["k3", "k4"], ["k4", "k5"], ["k5", "k6"], ["k6", "k7"], ["k7", "k8"], ["k8", "k9"], ["k9", "k10"], ["k10", "k11"],
  ["k11", "k12"], ["k12", "k13"], ["k13", "k14"], ["e0", "e1"], ["e1", "e2"], ["e2", "e3"], ["n0", "n1"], ["n1", "n2"], ["n2", "n3"],
  ["n3", "n4"], ["n4", "n5"], ["n5", "n6"], ["n6", "n7"], ["n7", "n8"], ["n8", "n9"], ["n9", "n10"], ["n10", "n11"], ["n11", "n12"],
  ["f8", "f9"], ["f9", "f10"], ["w0", "w1"],
  ["w1", "w2"], ["w2", "w3"], ["w3", "w4"], ["w4", "w5"], ["w5", "w6"], ["w6", "w7"], ["w7", "w8"], ["w8", "w9"], ["w9", "w10"], ["w10", "w11"],
  ["g0", "g1"], ["g1", "g2"], ["g2", "g3"], ["g3", "g4"], ["g4", "g5"], ["g5", "g6"], ["g6", "g7"], ["q0", "q1"], ["q1", "q2"], ["q2", "q3"],
  ["q3", "q4"], ["h0", "h1"], ["h1", "h2"], ["h2", "h3"], ["h3", "h4"], ["h4", "h5"], ["h5", "h6"], ["s7", "d0"], ["s7", "p0"], ["s1", "k0"],
  ["p10", "k12"], ["e3", "k13"], ["p4", "n0"], ["n6", "w0"], ["n12", "d12"], ["n12", "g0"], ["n12", "h0"], ["g7", "h6"], ["f10", "w3"],
  ["w11", "g6"], ["q0", "n4"], ["q4", "d4"],
  ["k12", "v0"], ["v0", "v1"], ["v1", "v2"], ["v2", "v3"], ["v3", "v4"], ["v4", "n3"], ["v4", "n4"], ["n5", "w0"],
];
// 10/17 · 지운 길: n2 → f0 → … → f7 (그랜드 수영장 잔디와 비스타 · 컨벤션 건물 위를 가로지르던 선). 그림에 흰 길이 없는 곳에는 길을 만들지 않는다
// 장소 → 길 위 진입점. 한 건물 안 장소는 모두 같은 진입점을 쓴다(건물 안 통로는 그리지 않는다)
const ANCHOR = {
  HOTEL_GATE: "e0", GWANGNARU_STN: "e0", GANGBYEON_STN: "e0", ICN_T1: "e0", ICN_T2: "e0",
  VALET_DESK: "w0", PARKING_TOWER_B1: "q2", PARKING_TOWER_4F: "q2", ANNEX: "v3",
  RIVERPARK: "w8", TENNEZ_PARK: "w6", PIZZA_HILL: "p2", MYONGWOLGWAN: "k8", FOREST_PARK: "d10", GOLF_CLUB: "h2",
};
const BLDG_ENT = { GRAND: "w0", VISTA: "vE_", DOUGLAS: "d6", THEATRE: "f8" };   // vE_ 는 아래에서 v1 로 바꾼다 (건물 정의가 뒤에 있음)

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

// 길은 그림에 그려져 있으므로 점 사이를 곧게 잇는다 (점을 촘촘히 찍어 굽은 길을 따른다)
const BEND = {};
function edgePts(a, b, n = 10) {
  const p = NODE[a], q = NODE[b], c = BEND[a + ">" + b] || [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, u = 1 - t;
    out.push([u * u * p[0] + 2 * u * t * c[0] + t * t * q[0], u * u * p[1] + 2 * u * t * c[1] + t * t * q[1]]);
  }
  return out;
}
const ADJ = {};
for (const [a, b] of EDGES) {
  (ADJ[a] = ADJ[a] || []).push(b); (ADJ[b] = ADJ[b] || []).push(a);
}

function nodePath(a, b) {
  if (a === b) return [a];
  const best = { [a]: 0 }, prev = {}, todo = new Set(Object.keys(NODE));
  while (todo.size) {
    let u = null;
    for (const n of todo) if (best[n] !== undefined && (u === null || best[n] < best[u])) u = n;
    if (u === null || u === b) break;
    todo.delete(u);
    for (const v of ADJ[u] || []) {
      const c = best[u] + dist(NODE[u], NODE[v]);
      if (best[v] === undefined || c < best[v]) { best[v] = c; prev[v] = u; }
    }
  }
  const out = [b];
  while (out[0] !== a && prev[out[0]]) out.unshift(prev[out[0]]);
  return out[0] === a ? out : [a, b];
}

const ROUTE_CACHE = {};
// 10/17 · 장소 a → b. (1) 같은 건물 안이면 길을 그리지 않는다 — internal (표시만 '건물 안 이동')
//   (2) 다른 곳이면 a 의 진입점 → 길(그림의 흰 길을 따라 찍은 점) → b 의 진입점. 장소 점 ↔ 진입점 사이(건물 안 · 마당)는 선을 그리지 않는다
//   그림 위 길은 개략 표시이며 실제 보행 경로 · 출입구 위치가 아니다. 이동 시간은 모델(검증기 구내 이동 매트릭스)이 정한다
// 길 계산용 건물 소속 — 하루 지도의 건물 묶음(BLDG)에 더해, 그 묶음에 없지만 같은 건물 안에 있는 업장 (온달 = 그랜드 본관 · 검증기 이동표 그랜드 로비 3분)
const ROUTE_IN = { ONDAL: "GRAND" };
// 10/17 · 건물끼리 실내로 이어진 곳 — 공식 가이드맵(walkerhill.com/Map): "그랜드 워커힐 서울과 비스타 워커힐 서울 간의 이동은 B1 또는 로비 층 통로를 이용해 주시기 바랍니다."
//   통로가 있다는 것만 확인됐고 어디로 지나는지는 모르므로 바깥 길을 그리지 않고 '연결 통로로 이동' 으로만 표시한다
const LINKED = { "GRAND|VISTA": "그랜드 ↔ 비스타 연결 통로 (B1 · 로비 층)" };
const bldgOf = l => LOC2B[l] || ROUTE_IN[l] || null;
function anchorOf(l) { const b = bldgOf(l); return b ? (BLDG_ENT[b] === "vE_" ? "v1" : BLDG_ENT[b]) : ANCHOR[l]; }
function route(a, b) {
  const k = a + ">" + b;
  if (ROUTE_CACHE[k]) return ROUTE_CACHE[k];
  const pa = LOC[a] || [500, 500], pb = LOC[b] || [500, 500];
  const ba = bldgOf(a), bb = bldgOf(b);
  let r;
  const lk = ba && bb && ba !== bb ? LINKED[[ba, bb].sort().join("|")] : null;
  if (ba && ba === bb) r = { pts: [BLDG[ba].at], internal: true, bldg: ba };
  else if (lk) r = { pts: [[(BLDG[ba].at[0] + BLDG[bb].at[0]) / 2, (BLDG[ba].at[1] + BLDG[bb].at[1]) / 2]], link: lk, bldgs: [ba, bb] };
  else {
    const na = anchorOf(a), nb = anchorOf(b);
    if (!na || !nb) r = { pts: [pa, pb], unknown: true };
    else if (na === nb) r = { pts: [NODE[na]], sameEntrance: true };
    else {
      const np = nodePath(na, nb), pts = [NODE[np[0]]];
      for (let i = 1; i < np.length; i++) pts.push(...edgePts(np[i - 1], np[i]).slice(1));
      r = { pts, nodes: np };
      // 가까운 두 곳인데 그림의 길로는 크게 돌아야 하면(직선의 2.5배 이상) — 실제 통로를 모르므로 돌아가는 선을 그리지 않는다
      let len = 0; for (let i = 1; i < pts.length; i++) len += dist(pts[i - 1], pts[i]);
      const st = dist(pa, pb);
      if (st < 140 && len > 2.5 * Math.max(st, 30)) r = { pts: [[(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2]], near: true, len: Math.round(len) };
    }
  }
  r.from = pa; r.to = pb;
  const lens = [0];
  for (let i = 1; i < r.pts.length; i++) lens.push(lens[i - 1] + dist(r.pts[i - 1], r.pts[i]));
  r.lens = lens; r.total = lens[lens.length - 1];
  return (ROUTE_CACHE[k] = r);
}

function along(r, f) {
  if (!r.total) return r.pts[0];
  const L = Math.max(0, Math.min(1, f)) * r.total;
  for (let i = 1; i < r.pts.length; i++) {
    if (L <= r.lens[i]) {
      const t = (L - r.lens[i - 1]) / ((r.lens[i] - r.lens[i - 1]) || 1);
      const a = r.pts[i - 1], b = r.pts[i];
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    }
  }
  return r.pts[r.pts.length - 1];
}

// ---------------------------------------------------------------------------
// 그림
// ---------------------------------------------------------------------------
function rng(seed) { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; }

function smoothPath(pts) {
  if (pts.length < 3) return "M" + pts.map(p => p.join(",")).join(" L");
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
    d += ` Q${pts[i][0]},${pts[i][1]} ${mx},${my}`;
  }
  const l = pts[pts.length - 1];
  return d + ` L${l[0]},${l[1]}`;
}

function tree(x, y, r, c, trunk) {
  return `<g class="tree"><rect x="${x - 1.4}" y="${y}" width="2.8" height="${r * 1.1}" fill="${trunk}"/>` +
    `<circle cx="${x}" cy="${y - r * 0.2}" r="${r}" fill="${c}"/>` +
    `<circle cx="${x - r * 0.6}" cy="${y + r * 0.15}" r="${r * 0.7}" fill="${c}"/>` +
    `<circle cx="${x + r * 0.6}" cy="${y + r * 0.1}" r="${r * 0.72}" fill="${c}"/></g>`;
}

function box(x, y, w, h, d, front, side, top, extra = "") {
  // 간단한 등각 상자 (x,y = 앞면 왼쪽 아래)
  return `<g>${extra}<polygon points="${x},${y} ${x + w},${y} ${x + w},${y - h} ${x},${y - h}" fill="${front}"/>` +
    `<polygon points="${x + w},${y} ${x + w + d},${y - d * 0.6} ${x + w + d},${y - h - d * 0.6} ${x + w},${y - h}" fill="${side}"/>` +
    `<polygon points="${x},${y - h} ${x + w},${y - h} ${x + w + d},${y - h - d * 0.6} ${x + d},${y - h - d * 0.6}" fill="${top}"/></g>`;
}

function windows(x, y, w, h, cols, rows, c) {
  let s = "";
  const cw = w / cols, rh = h / rows;
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++)
    s += `<rect x="${x + i * cw + cw * 0.25}" y="${y - h + j * rh + rh * 0.3}" width="${cw * 0.5}" height="${rh * 0.45}" fill="${c}"/>`;
  return s;
}

const MAP_IMG = "/static/map_base.png";   // 14차 · 투명 배경 PNG — 종이색 위에 그대로 놓인다 (종이색 막 없음)
function drawBase(svg) {
  svg.innerHTML = `<image href="${MAP_IMG}" x="0" y="0" width="${MAP_W}" height="${MAP_H}" preserveAspectRatio="none"/>`;
}

// 이름표 (10/17 14차) — 그림에 글자가 없으므로 #labels 층에서 작은 카드로 덧씌운다. at = 기준점(원본 그림 좌표), dir = 기본 방향 · alt = 가장자리에서 잘릴 때 반대 방향,
//   big = 주요 호텔(한 단계 강하게), b = 건물 묶음(BLDG) · loc = 시설 코드 (누르면 기존 시설 선택과 연결). 카드는 건물 지붕 · 길 · 표시를 가리지 않게 기준점에서 dir 쪽 여백에 놓인다
const LABELS = [
  { name: "피자힐", at: S([352, 332]), dir: "n", alt: "s", big: 1, loc: "PIZZA_HILL" },
  { name: "명월관", at: S([222, 556]), dir: "n", alt: "s", big: 1, loc: "MYONGWOLGWAN" },
  { name: "주차타워", at: S([668, 440]), dir: "n", alt: "s", loc: "PARKING_TOWER_B1" },
  { name: "더글라스 하우스", at: S([822, 348]), dir: "n", alt: "s", big: 1, b: "DOUGLAS" },
  { name: "포레스트 파크", at: S([1120, 330]), dir: "n", alt: "s", big: 1, loc: "FOREST_PARK" },
  { name: "힐링 포레스트", at: S([810, 108]), dir: "n", alt: "s" },
  { name: "더글라스 가든", at: S([596, 316]), dir: "n", alt: "s" },
  { name: "그랜드 워커힐", at: S([766, 528]), dir: "n", alt: "s", big: 1, b: "GRAND" },
  { name: "빛의 시어터 · 컨벤션", at: S([905, 812]), dir: "s", alt: "n", big: 1, b: "THEATRE" },
  { name: "비스타 워커힐", at: S([600, 824]), dir: "s", alt: "n", big: 1, b: "VISTA" },
  { name: "테네즈 파크", at: S([990, 688]), dir: "n", alt: "s", loc: "TENNEZ_PARK" },
  { name: "리버파크", at: S([1086, 806]), dir: "s", alt: "n", loc: "RIVERPARK" },
  { name: "골프클럽", at: S([1410, 520]), dir: "n", alt: "s", loc: "GOLF_CLUB" },
  { name: "애스톤 하우스", at: S([1472, 700]), dir: "n", alt: "s" },
];
// 옛 호출 호환 (글자 · x · y · 큰 글씨)
const BUILDING_LABELS = LABELS.map(l => [l.name, l.at[0], l.at[1], l.big]);

// 업장이 여러 개 들어 있는 건물 (10/15 v1.31) — 하루 전체 지도에서는 건물 하나로 묶어 보이고, 누르면 안의 업장이 펼쳐진다
const BLDG = {
  GRAND: { name: "그랜드 워커힐", locs: ["GRAND_LOBBY", "GRAND_FRONT_DESK", "GRAND_ROOM", "GRAND_CLUB_LOUNGE", "GRAND_LIBRARY", "THE_PAVILION", "GEUMRYONG", "LE_PASSAGE", "LUX_BAR", "GRAND_POOL", "FITNESS", "WELLNESS_SAUNA"] },
  VISTA: { name: "비스타 워커힐", locs: ["VISTA_LOBBY", "VISTA_ROOM", "VISTA_POOL", "VISTA_FITNESS", "SKYARD", "THE_BUFFET", "MOEGI"] },
  DOUGLAS: { name: "더글라스 하우스", locs: ["DOUGLAS_LOBBY", "DOUGLAS_ROOM", "DOUGLAS_LOUNGE", "DOUGLAS_LIBRARY"] },
  THEATRE: { name: "빛의 시어터 · 컨벤션", locs: ["THEATRE_OF_LIGHT", "THEATRE_ART_SHOP", "CU_THEATRE", "CONVENTION"] },
};
const LOC2B = {};
for (const [id, b] of Object.entries(BLDG)) {
  b.at = [Math.round(b.locs.reduce((a, l) => a + LOC[l][0], 0) / b.locs.length), Math.round(b.locs.reduce((a, l) => a + LOC[l][1], 0) / b.locs.length)];
  for (const l of b.locs) LOC2B[l] = id;
}
BLDG.VISTA.at = S([640, 740]);   // 건물 몸통 가운데
// 펼친 건물 안 업장 자리 — 건물 중심을 둘러싼 원 위에 고르게 (지도 밖으로 안 나가게)
function fanPos(id, n, i) {
  const b = BLDG[id], R = 64 + n * 4, a = -Math.PI / 2 + (2 * Math.PI * i) / n;
  return [Math.max(24, Math.min(MAP_W - 24, b.at[0] + R * Math.cos(a))), Math.max(24, Math.min(MAP_H - 24, b.at[1] + R * Math.sin(a)))];
}

// 10/17 시설 썸네일 — 표시 전용 모듈을 따로 불러온다 (static/place_img/manifest.json 이 비어 있으면 화면 변화 없음)
(function () { const s = document.createElement("script"); s.src = "/static/place_thumbs.js"; s.defer = true; document.head.appendChild(s); })();
