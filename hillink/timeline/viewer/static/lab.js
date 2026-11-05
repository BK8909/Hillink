// 10/20 개별 페르소나 실험실 · UX 23차 — 후기 손님 한 팀 · 같은 시드 · 환경 변수 없음 / 있음 비교
//   주인공은 고객: ① 무엇이 달라졌나(한두 문장) → ② 행동 이야기(어디서 · 무엇을 · 왜) → ③ 행동을 누르면 넓은 창에서 근거 네 칸.
//   데이터는 R 실행 결과 파일만(서버 lab.py 가 읽어 줌). '왜' 는 실제 계산에 들어간 점수 항만 풀어 쓴다 — 사후 설명을 만들지 않는다.
//   이동 감점만으로 뽑힌 행동에는 고객 이유가 있는 것처럼 쓰지 않는다.
//   app.js 의 $ · $$ · esc · api · curReview · SRC · locName · LOC · LOC2B · BLDG · openDrawer · closeDrawer · MODE 를 쓴다.
(function () {
  "use strict";
  let AV = null, VAR = "", LAST = null, SIDE = "changed", ROWS = [], SEL = -1, PULSE = false;
  const K = () => (LAST && LAST.meta && LAST.meta.K) || 12;
  const cnt = p => Math.round((p || 0) * K());
  const OFFVAR = { autumn: "가을 산책", beer: "맥주 테라스" };
  const PLACE_EXTRA = { WINE_FAIR: "와인페어", RIVERPARK: "리버파크", FOREST_PARK: "포레스트 파크" };
  const pname = c => PLACE_EXTRA[c] && !(typeof LIB !== "undefined" && LIB && LIB.loc_names && LIB.loc_names[c]) ? PLACE_EXTRA[c] : (typeof locName === "function" ? locName(c) : c);
  const PROC = /절차/;
  const QUIET = /^(주차|도착|짐 맡김|체크인 대기|프런트 응대|키 수령|취침)$/;
  const made = iso => { if (!iso) return ""; const d = new Date(iso); return isNaN(d) ? String(iso).slice(0, 16) : `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
  const fmtDate = iso => { const d = new Date(iso.slice(0, 10) + "T12:00:00"); return `${d.getMonth() + 1}/${d.getDate()}(${"일월화수목금토"[d.getDay()]})`; };

  // ── 계산 항 → 쉬운 말 (항목 이름은 engine 의 why 문자열 그대로 · 숫자는 근거 창에서만)
  const TERM = [
    [/^이동 (\d+)분/, m => ({ k: "move", t: `이동 ${m[1]}분` })],
    [/^대기 (\d+)분/, m => ({ k: "wait", t: `대기 ${m[1]}분 예상` })],
    [/^석식 때 · 식당 밖/, () => ({ k: "meal", t: "저녁 시간 · 식당 밖에서 해결" })],
    [/^중식 때 · 식당 밖/, () => ({ k: "meal", t: "점심 시간 · 식당 밖에서 해결" })],
    [/^조식 때 · 식당 밖/, () => ({ k: "meal", t: "아침 시간 · 식당 밖에서 해결" })],
    [/^석식 때/, () => ({ k: "meal", t: "저녁 시간" })],
    [/^중식 때/, () => ({ k: "meal", t: "점심 시간" })],
    [/^조식 때/, () => ({ k: "meal", t: "아침 시간" })],
    [/^예약한 곳/, () => ({ k: "fact", t: "예약해 둔 곳" })],
    [/^조식 예약 포함/, () => ({ k: "fact", t: "조식이 상품에 포함" })],
    [/^아동 동반/, () => ({ k: "fact", t: "아이와 함께" })],
    [/^포장 음식 객실에서/, () => ({ k: "fact", t: "포장해 와서 객실에서 먹기" })],
    [/^객실에서 쉼/, () => ({ k: "rest", t: "객실에서 쉬기" })],
    [/^밤이라 취침/, () => ({ k: "rest", t: "밤이라 잠자리에" })],
    [/^호텔 조식 두고 방에서/, () => ({ k: "neg", t: "호텔 조식 대신 방에서 먹는 감점" })],
    [/^직전에도 객실/, () => ({ k: "neg", t: "방금도 객실이라 감점" })],
    [/절차/, () => ({ k: "proc", t: "정해진 절차" })],
  ];
  const termOf = w => { const v = parseFloat((String(w).match(/([-+]\d+(\.\d+)?)\s*$/) || [])[1]); for (const [re, f] of TERM) { const m = String(w).match(re); if (m) return Object.assign(f(m), { v, raw: w }); } return { k: "other", t: String(w).replace(/\s*[-+]\d+(\.\d+)?\s*$/, ""), v, raw: w }; };
  // 이 행동이 왜 뽑혔나 — 한 줄
  function whyLine(s) {
    const T = (s.why || []).map(termOf), pos = T.filter(t => t.v > 0 && t.k !== "proc"), neg = T.filter(t => (t.k === "move" || t.k === "wait"));
    if (T.some(t => t.k === "proc")) return { cls: "proc", txt: "정해진 절차" };
    if (!pos.length) return { cls: "none", txt: `끌리는 이유 점수는 없음 — 이동 부담이 비슷한 후보들 가운데 확률로 뽑힘${s.rank > 1 ? ` (후보 중 ${s.rank}위)` : ""}` };
    return { cls: "pos", txt: pos.map(t => t.t).join(" · ") + (neg.length ? ` · ${neg.map(t => t.t).join(" · ")}` : "") };
  }

  // ── 후기 근거(정답 확인 파일의 방문 · 미방문 · 지나감 판단 요지 · 원문 인용 아님)
  function reviewEv(loc) {
    const E = LAST.evidence;
    if (E.visited[loc]) return { cls: "ok", tag: "후기에 있음", txt: E.visited[loc] };
    if (E.not_visited[loc]) { const un = /언급 없음/.test(E.not_visited[loc]); return { cls: un ? "un" : "no", tag: un ? "언급 없음" : "가지 않음", txt: E.not_visited[loc] }; }
    if (E.passed[loc]) return { cls: "un", tag: "지나감", txt: E.passed[loc] };
    return { cls: "un", tag: "언급 없음", txt: "후기에 이 장소 이야기가 없습니다 — 안 갔다는 뜻은 아닙니다(⏸)." };
  }

  // ── 왼쪽: 변수 칩 · 기준 / 변경 조건
  function blogNow() { try { return SRC === "blog" && curReview() ? curReview().blog : null; } catch (e) { return null; } }
  function okVar(v) { const b = blogNow(); return !!(AV && b && AV.blogs[b] && AV.blogs[b][v]); }
  function reason(v) {
    if (!AV) return "실험 결과 목록을 읽는 중입니다";
    const b = blogNow();
    if (!b) return "① 에서 '블로그 후기' 손님을 고르면 열립니다";
    if (!AV.blogs[b]) return `${b} 는 아직 R 실험 결과가 없습니다(지금은 ${Object.keys(AV.blogs).join(" · ")})`;
    return (AV.reasons || {})[v] || "R 실험 결과가 없습니다";
  }
  function paintLeft() {
    const box = $("#labVars"); if (!box) return;
    box.querySelectorAll("button[data-v]").forEach(b => {
      const v = b.dataset.v, ok = !v || okVar(v);
      b.classList.toggle("off", !ok); b.classList.toggle("on", v === VAR); b.setAttribute("aria-pressed", String(v === VAR));
      b.title = !v ? "② 의 날짜 · 행사 · 변동으로 지금 계산합니다" : ok ? "저장된 실험 결과가 있습니다" : reason(v);
    });
    $("#left").classList.toggle("pl-var", !!VAR);
    const ok = !!VAR && okVar(VAR), V = AV && AV.vars && AV.vars[VAR];
    const vd = x => x && x.virtual ? String(x.virtual).replace(/^가상 조건 · /, "").replace(/ — 실제 방문일 아님$/, "") : "";
    // 조건을 고르면 ② 의 기준 환경 줄(날짜 · 행사 · 변동)은 접고, 저장된 실험의 기준 · 변경을 한 상자에 (같은 자리 · 중복 없음)
    $("#labBase").innerHTML = "";
    $("#labCond").innerHTML = !VAR ? "" : ok && V
      ? `<dt>기준</dt><dd>${esc(vd(V.base) || V.base_txt || "")}</dd><dt>변경</dt><dd><b>${esc(V.var_txt || "")}</b> · 나머지는 같음</dd><dd class="pl-virt">저장된 실험의 날짜(가상 조건 · 실제 방문일 아님) · 평가자 관심 점수 반영 전</dd>`
      : `<dd class="pl-offwhy"><b>${esc(OFFVAR[VAR] || (V && V.name) || "이 조건")}</b> — 아직 볼 수 없습니다. ${esc(reason(VAR))}</dd>`;
    const btn = $("#btnLab"); if (btn) { btn.disabled = !ok; }
  }
  function paintCrowd() {
    const s = $("#fCrowd"), o = $("#crowdSum"); if (!s || !o) return;
    const t = s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : "";
    o.textContent = t ? `· ${t.length > 22 ? t.slice(0, 22) + "…" : t}` : "";
  }

  async function init() {
    const box = $("#labVars"); if (!box) return;
    box.querySelectorAll("button[data-v]").forEach(b => b.onclick = () => { VAR = b.dataset.v; if (!VAR) exitLab(); paintLeft(); });
    $("#btnLab").onclick = run;
    const fr = $("#fReview"); if (fr) fr.addEventListener("change", () => { paintLeft(); exitLab(); });
    $$("#srcSeg button").forEach(b => b.addEventListener("click", () => setTimeout(() => { paintLeft(); exitLab(); }, 0)));
    const br = $("#btnRun"); if (br) br.addEventListener("click", exitLab, true);
    const bc = $("#btnCmp"); if (bc) bc.addEventListener("click", exitLab, true);
    const fc = $("#fCrowd"); if (fc) { fc.addEventListener("change", paintCrowd); new MutationObserver(paintCrowd).observe(fc, { childList: true }); }
    paintLeft(); paintCrowd();
    try { AV = await api("/api/lab", { avail: true }); } catch (e) { AV = { blogs: {}, reasons: {}, vars: {} }; }
    paintLeft();
  }

  // ── 실험 모드 진입 / 해제 (지도 위 기존 손님 경로는 숨기고, 이야기에 나온 곳만 표시)
  function enterLab() {
    document.body.classList.add("pl-mode");
    const c = $("#clock"); if (c) { c.querySelector("b").textContent = fmtDate(LAST.changed.start); c.querySelector("span").textContent = "가상 조건 · 저장된 실험 결과"; }
  }
  function exitLab() {
    if (!document.body.classList.contains("pl-mode")) return;
    document.body.classList.remove("pl-mode");
    const g = document.getElementById("labMarks"); if (g) g.innerHTML = "";
    const lg = document.getElementById("labLegend"); if (lg) lg.remove();
  }
  document.addEventListener("click", e => { const t = e.target.closest && e.target.closest("nav .tab, #flowSeg button"); if (t && t.dataset.m !== "guest" && t.dataset.mode !== "day") exitLab(); }, true);

  async function run() {
    const hint = $("#labHint"), b = $("#btnLab"), r = blogNow();
    if (!r || !okVar(VAR)) { paintLeft(); return; }
    b.disabled = true; b.textContent = "불러오는 중…";
    try {
      LAST = await api("/api/lab", { blog: r, var: VAR });
      SIDE = "changed"; SEL = -1; enterLab(); render();
      hint.textContent = `불러온 결과 · R ${LAST.meta.plan} · ${made(LAST.meta.created_at) || "계산 시각 미상"} 계산 · 지금 새로 계산하지 않았습니다`;
    } catch (e) { hint.textContent = "읽지 못했습니다: " + e.message; }
    b.disabled = false; b.textContent = "저장된 실험 결과 불러오기";
  }

  // ── 지도 표시: 이야기에 나온 곳 · 고른 행동
  function markMap() {
    const svg = document.getElementById("map"); if (!svg || !LAST) return;
    let g = document.getElementById("labMarks");
    if (!g) { g = document.createElementNS("http://www.w3.org/2000/svg", "g"); g.id = "labMarks"; svg.appendChild(g); }
    const at = c => (LOC2B[c] && BLDG[LOC2B[c]] ? BLDG[LOC2B[c]].at : LOC[c]);
    const seen = new Map();
    ROWS.forEach((r, i) => { if (r.quiet) return; const p = at(r.s.location); if (!p) return; const k = p.join(","); if (!seen.has(k)) seen.set(k, { p, rows: [] }); seen.get(k).rows.push(i); });
    const cur = SEL >= 0 ? ROWS[SEL] : null, cp = cur ? at(cur.s.location) : null;
    let h = [...seen.values()].map(({ p, rows }) => `<circle class="lm ${rows.some(i => ROWS[i].focus) ? "focus" : ""}" cx="${p[0]}" cy="${p[1]}" r="11"/>`).join("");
    if (cp) {
      const lab = `${cur.time} ${cur.s.label}`, w = Math.max(90, lab.length * 19 + 30);
      h += `<circle class="lm-ring${PULSE ? " pulse" : ""}" cx="${cp[0]}" cy="${cp[1]}" r="20"/><g class="lm-tag" transform="translate(${Math.min(990 - w, Math.max(10, cp[0] - w / 2))},${Math.max(6, cp[1] - 64)})"><rect width="${w}" height="36" rx="18"/><text x="${w / 2}" y="24.5" text-anchor="middle">${esc(lab)}</text></g>`;
    }
    g.innerHTML = h;
    if (!document.getElementById("labLegend")) {
      const d = document.createElement("div"); d.id = "labLegend"; d.className = "legend maplegend pl-legend";
      d.innerHTML = `<span><i class="lg-lab"></i>이야기에 나온 곳</span><span><i class="lg-labf"></i>바꾼 조건과 관련된 곳</span><span><i class="lg-labc"></i>고른 행동</span>`;
      $("#mapWrap").appendChild(d);
    }
  }

  // ── 오른쪽 패널
  function headline(L) {
    const f = L.diff.filter(x => (L.focus || []).includes(x.act));
    const others = L.diff.filter(x => !(L.focus || []).includes(x.act) && !QUIET.test(x.act) && Math.abs(x.delta) >= 0.08).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 3);
    const line = x => `<li><b>${esc(x.act)}</b> <span class="pl-n">${K()}번 중 ${cnt(x.base)}번 → <b>${cnt(x.var)}번</b></span></li>`;
    const fLines = f.length ? f.map(line).join("") : `<li><b>${esc((L.focus || [])[0] || L.var_name)}</b> <span class="pl-n">한 번도 고르지 않음</span></li>`;
    // 바꾼 조건과 관련된 행동이 이동 감점만으로 뽑혔는지 — 근거 정직성 문장
    const fs = (L.changed.steps || []).filter(s => (L.focus || []).includes(s.label));
    const onlyMove = fs.length && fs.every(s => (s.why || []).map(termOf).every(t => t.k === "move" || t.k === "wait"));
    const note = onlyMove ? `지금 모델에는 '${esc(L.var_name)}' 를 고를 고객 이유 점수가 없습니다. 이 변화는 고를 수 있는 후보가 하나 늘어 생긴 확률 차이입니다.`
      : `이 변화는 같은 손님 · 같은 시드로 ${K()}번씩 돌린 결과의 차이입니다(평가자 관심 점수 미반영).`;
    return `<section class="pl-card pl-head">
      <div class="pl-kicker"><span class="pl-saved">저장된 실험 결과</span> ${esc(L.blog)} · R ${esc(L.meta.plan)}${made(L.meta.created_at) ? ` · ${esc(made(L.meta.created_at))} 계산` : ""}</div>
      <h4>${esc(L.var_txt)}이면, 이 손님은?</h4>
      <div class="pl-virtual">${esc(L.virtual || "가상 조건")}</div>
      <ul class="pl-key">${fLines}${others.map(line).join("")}</ul>
      <p class="pl-note">${note}</p>
      <button type="button" class="rv-btn gs-btn pl-link" data-act="diff">달라진 행동 · 그대로인 행동 전체 보기 →</button>
    </section>`;
  }
  function buildRows(D) {
    const rows = []; let proc = null;
    const startD = D.start.slice(0, 10);
    (D.steps || []).forEach((s, i) => {
      const day = Math.round((new Date(s.t_in.slice(0, 10)) - new Date(startD)) / 864e5) + 1;
      const quiet = PROC.test((s.why || []).join(" ")) || QUIET.test(s.label);
      if (quiet) { if (proc && proc.day === day) { proc.labels.push(s.label); return; } proc = { quiet: true, day, time: s.t_in.slice(11, 16), labels: [s.label], s }; rows.push(proc); return; }
      proc = null;
      rows.push({ day, time: s.t_in.slice(11, 16), s, i, focus: (LAST.focus || []).includes(s.label) });
    });
    return rows;
  }
  function story(D) {
    ROWS = buildRows(D); let lastDay = 0;
    return ROWS.map((r, ri) => {
      let h = "";
      if (r.day !== lastDay) { lastDay = r.day; const d = new Date(D.start.slice(0, 10) + "T12:00:00"); d.setDate(d.getDate() + r.day - 1); h += `<div class="pl-day">${r.day}일차 <span>${d.getMonth() + 1}/${d.getDate()}(${"일월화수목금토"[d.getDay()]})</span></div>`; }
      if (r.quiet) return h + `<div class="pl-row quiet"><span class="t">${esc(r.time)}</span><span class="a">${esc(r.labels.join(" · "))}</span></div>`;
      const w = whyLine(r.s), ev = reviewEv(r.s.location);
      return h + `<button type="button" class="pl-row ${r.focus ? "focus" : ""} ${SEL === ri ? "sel" : ""}" data-r="${ri}">
        <span class="t">${esc(r.time)}</span>
        <span class="a">${esc(r.s.label)}<span class="pl-ev ${ev.cls}">${esc(ev.tag)}</span></span>
        <span class="w ${w.cls}">${esc(w.txt)}</span></button>`;
    }).join("");
  }
  // 선택한 행동 줄 — 근거 창을 닫아도 남고, ← → 로 시간 순서대로 지도 위 위치를 따라간다
  const navIdx = () => ROWS.map((r, i) => [r, i]).filter(([r]) => !r.quiet).map(([, i]) => i);
  function selBar() {
    if (SEL < 0 || !ROWS[SEL]) return `<div class="pl-selbar empty">행동을 누르면 지도에 위치가 표시되고 근거 창이 열립니다</div>`;
    const r = ROWS[SEL], idx = navIdx(), pos = idx.indexOf(SEL);
    return `<div class="pl-selbar"><div class="pl-selt"><span class="hint">선택한 행동 ${pos + 1} / ${idx.length}</span><b>${r.day}일차 ${esc(r.time)} · ${esc(r.s.label)}</b><span class="pl-selp">${esc(pname(r.s.location))}</span></div>
      <div class="pl-selb"><button type="button" class="rv-btn" data-step="-1" ${pos <= 0 ? "disabled" : ""} aria-label="이전 행동">←</button><button type="button" class="rv-btn" data-ev="1">근거 보기</button><button type="button" class="rv-btn" data-step="1" ${pos >= idx.length - 1 ? "disabled" : ""} aria-label="다음 행동">→</button></div></div>`;
  }
  function step(d) {
    const idx = navIdx(), pos = idx.indexOf(SEL), n = idx[Math.max(0, Math.min(idx.length - 1, (pos < 0 ? -1 : pos) + d))];
    if (n == null) return; SEL = n; render(true);
    const row = $("#panel").querySelector(`.pl-row[data-r="${n}"]`); if (row) row.scrollIntoView({ block: "nearest" });
  }
  function showOnMap() {
    closeDrawer(); PULSE = true; markMap(); PULSE = false;
    if (innerWidth <= 900) { const m = $("#mapWrap"); if (m) m.scrollIntoView({ behavior: "smooth", block: "start" }); }
  }
  function render(keep) {
    const L = LAST, P = $("#panel"); const D = SIDE === "changed" ? L.changed : L.base;
    const scr = $("#right"), keepTop = keep ? scr.scrollTop : 0;
    P.innerHTML = `<div class="pl-wrap">${headline(L)}
      <section class="pl-card pl-storycard">
        <div class="pl-sh"><h4>행동 이야기</h4><span class="hint">행동을 누르면 근거</span></div>
        <div class="seg pl-seg" role="group" aria-label="볼 조건"><button type="button" data-s="changed" class="${SIDE === "changed" ? "on" : ""}">${esc(L.var_txt)}</button><button type="button" data-s="base" class="${SIDE === "base" ? "on" : ""}">${esc(L.base_txt)}</button></div>
        ${selBar()}
        <div class="pl-story">${story(D)}</div>
        <p class="pl-foot">한 번 실행한 하루입니다(시드 ${esc(String(L.meta.seed_base || ""))} · 화면 손님 한 팀과 같은 계산). 횟수는 위 ${K()}번 결과를 보세요.</p>
      </section>
      <details class="pl-card pl-spend"><summary>소비 <span class="hint">보조 정보 · 정가 환산</span></summary>
        <p>${esc(L.var_txt)} ${Math.round(L.changed.spend_total || 0).toLocaleString()}원 · ${esc(L.base_txt)} ${Math.round(L.base.spend_total || 0).toLocaleString()}원 — 객실 상품은 모델이 자동 배정한 값이라 실제 구매 상품이 아닐 수 있습니다.</p>
      </details>
      <details class="pl-card pl-meta"><summary>실험 기록 <span class="hint">R ${esc(L.meta.plan)} · 모델 ${esc(L.meta.model_ver || "-")}</span></summary>
        <p>결과 파일 ${L.meta.files.map(esc).join(" · ")} · ${K()}회 · 시드 ${esc(String(L.meta.seed_base))}부터 · 모델 ${esc(L.meta.model_ver || "-")} · 입력 ${esc(L.meta.input_ver || "-")} · 저장소 ${esc(L.meta.git_head || "-")} · 성향 강도 ${esc(String(L.meta.lam_trait))} · ${esc(L.meta.interest)}</p>
      </details></div>`;
    P.scrollTop = 0; scr.scrollTop = keepTop;
    P.querySelectorAll("[data-step]").forEach(b => b.onclick = () => step(+b.dataset.step));
    const evb = P.querySelector("[data-ev]"); if (evb) evb.onclick = () => openEv(SEL);
    P.querySelectorAll(".pl-seg button").forEach(b => b.onclick = () => { SIDE = b.dataset.s; SEL = -1; render(); });
    P.querySelectorAll(".pl-row[data-r]").forEach(r => r.onclick = () => openEv(+r.dataset.r));
    P.querySelector('[data-act="diff"]').onclick = openDiff;
    markMap();
  }

  // ── 넓은 창: 행동 근거 네 칸
  function assumptions(s) {
    const a = [];
    const T = (s.why || []).map(termOf);
    if (!T.some(t => t.v > 0 && t.k !== "proc")) a.push("이 행동을 끌어당긴 고객 이유 점수가 없습니다. 이동 · 대기 감점이 비슷한 후보들 사이에서 확률(τ 0.5)로 뽑혔습니다 — 고객 성향 때문이라고 읽지 않습니다.");
    if (s.rank > 1) a.push(`점수 순위로는 ${s.rank}위였지만 확률 선택이라 뽑혔습니다(1위와 차이 ${s.top_gap != null ? (+s.top_gap).toFixed(2) : "-"}).`);
    if (LAST.meta.lam_trait === 0) a.push("후기에서 뽑은 성향 값은 지금 계산에 쓰이지 않습니다(강도 0).");
    a.push("평가자 관심 · 비선호 점수는 아직 반영되지 않았습니다(평가 시트 입력 뒤).");
    a.push(LAST.virtual || "가상 조건입니다.");
    return a;
  }
  function openEv(ri) {
    const D = SIDE === "changed" ? LAST.changed : LAST.base;
    const idx = ROWS.map((r, i) => [r, i]).filter(([r]) => !r.quiet).map(([, i]) => i);
    if (!idx.includes(ri)) return;
    SEL = ri; render(true);
    const r = ROWS[ri], s = r.s, ev = reviewEv(s.location), w = whyLine(s);
    const T = (s.why || []).map(termOf);
    const dx = LAST.diff.find(x => x.act === s.label);
    const pos = idx.indexOf(ri), prev = idx[pos - 1], next = idx[pos + 1];
    const alts = (s.alts || []).slice(0, 5);
    const sideTxt = SIDE === "changed" ? LAST.var_txt : LAST.base_txt;
    const html = `<div class="pl-evd">
      <div class="pl-ev-top">
        <div class="pl-ev-when">${r.day}일차 ${esc(r.time)} · ${esc(pname(s.location))} · <span class="hint">${esc(sideTxt)}</span></div>
        <h3>${esc(s.label)}</h3>
        <p class="pl-ev-why ${w.cls}">${esc(w.txt)}</p>
        ${dx ? `<div class="pl-ev-p">이 행동이 ${K()}번 중 나온 횟수 <b>${esc(LAST.base_txt)} ${cnt(dx.base)}번</b> → <b>${esc(LAST.var_txt)} ${cnt(dx.var)}번</b></div>` : ""}
      </div>
      <div class="pl-ev4">
        <section><h5>후기 근거 <span class="pl-ev ${ev.cls}">${esc(ev.tag)}</span></h5><p>${esc(ev.txt)}</p><p class="hint">정답 확인 때 적은 요지입니다(원문 인용 아님).</p></section>
        <section><h5>적용된 환경</h5><p>${r.focus ? `<b>${esc(LAST.var_txt)}</b> — ${esc(LAST.env)}` : `이 행동에는 바꾼 조건(${esc(LAST.var_name)})이 직접 걸리지 않습니다.`}</p><p class="hint">${esc(LAST.virtual || "")}</p></section>
        <section class="wide"><h5>모델이 실제로 쓴 점수 항</h5>
          <ul class="pl-terms">${T.map(t => `<li class="${t.v > 0 ? "p" : t.v < 0 ? "n" : ""}"><span>${esc(t.t)}</span><b>${isNaN(t.v) ? "" : (t.v > 0 ? "+" : "") + t.v.toFixed(2)}</b></li>`).join("") || `<li><span>계산 항 없음</span></li>`}</ul>
          <p class="hint">합계 ${s.pts != null ? (+s.pts).toFixed(2) : "-"}${s.rank ? ` · 후보 중 ${s.rank}위` : ""} · 그 시각 탈락한 후보 ${(s.rejected || []).length}개</p>
          ${alts.length ? `<table class="t pl-alts"><tr><th>그 시각 다른 후보</th><th class="n">점수</th><th>들어간 항</th></tr>${alts.map(a => `<tr class="${a.label === s.label ? "me" : ""}"><td>${esc(a.label || "")}</td><td class="n">${a.pts != null ? (+a.pts).toFixed(2) : "-"}</td><td>${esc((a.why || []).map(x => termOf(x).t).join(" · "))}</td></tr>`).join("")}</table>` : ""}
        </section>
        <section class="wide"><h5>가정 · 모르는 것</h5><ul>${assumptions(s).map(x => `<li>${esc(x)}</li>`).join("")}</ul></section>
      </div>
      <div class="pl-ev-nav"><button type="button" class="rbtn" data-go="${prev ?? ""}" ${prev == null ? "disabled" : ""}>← 이전 행동</button><button type="button" class="rv-btn pl-mapbtn" data-map="1">지도에서 보기</button><button type="button" class="rbtn" data-go="${next ?? ""}" ${next == null ? "disabled" : ""}>다음 행동 →</button></div>
    </div>`;
    openDrawer(`${s.label} · 근거`, `${LAST.blog} · ${sideTxt} · R ${LAST.meta.plan}`, html, root => {
      root.querySelectorAll("[data-go]").forEach(b => b.onclick = () => { if (b.dataset.go !== "") openEv(+b.dataset.go); });
      root.querySelector("[data-map]").onclick = showOnMap;
    }, { wide: true });
  }
  function openDiff() {
    const L = LAST;
    const rows = L.diff.filter(x => !QUIET.test(x.act)).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    const ch = rows.filter(x => Math.abs(x.delta) >= 0.08 || (L.focus || []).includes(x.act)), same = rows.filter(x => !ch.includes(x));
    const bar = x => { const w = Math.min(100, Math.abs(x.delta) * 100); return `<span class="pl-bar ${x.delta >= 0 ? "up" : "down"}" style="width:${w}%"></span>`; };
    const tr = x => `<tr class="${(L.focus || []).includes(x.act) ? "focus" : ""}"><td>${esc(x.act)}</td><td class="n">${cnt(x.base)}번</td><td class="n">${cnt(x.var)}번</td><td>${bar(x)} <span class="hint">${x.delta > 0 ? "+" : ""}${Math.round(x.delta * 100)}%p</span></td></tr>`;
    openDrawer("달라진 행동 · 그대로인 행동", `${L.blog} · ${K()}번씩 · ${L.base_txt} → ${L.var_txt}`, `<div class="pl-diffwrap">
      <table class="t pl-diff"><tr><th>달라진 행동</th><th class="n">${esc(L.base_txt)}</th><th class="n">${esc(L.var_txt)}</th><th>변화</th></tr>${ch.map(tr).join("") || `<tr><td colspan="4">눈에 띄게 달라진 행동이 없습니다 — 이것도 결과입니다</td></tr>`}</table>
      <table class="t pl-diff same"><tr><th>그대로인 행동</th><th class="n">${esc(L.base_txt)}</th><th class="n">${esc(L.var_txt)}</th><th></th></tr>${same.map(tr).join("")}</table>
      <p class="hint">${K()}번 중 그 행동이 한 번 이상 나온 횟수입니다. 8%p(12번 중 1번) 미만 차이는 '그대로' 로 묶었습니다. 주차 · 체크인 같은 절차와 취침은 뺐습니다.</p></div>`, null, { wide: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
