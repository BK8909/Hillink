// 자율 하루 (CL-1024-18) — 후기 기반 고객 11명이 워커힐 월드에서 각자 하루를 진행한다(1명 · 11명 동시 · 운영자 개입 전후).
//   서버 /api/autonomy → autonomy_run.py → operator_choice/autonomy_v1(욕구 → 후보 → 월드 규칙 → 개인 평가 → 실행 → 상태 갱신).
//   화면의 근거는 두 유형 — '후기에서 확인'(그 고객의 후기 사실) · '프로파일 기반 추론'(누적 성향 · 동행 · 상황). 점수 · 출처 등급은 개발 정보에서만.
const AU = { meta: null, sel: new Set(), iv: "none", cmp: true, res: null, focus: null, busy: false, err: null, tm: 16 * 60, play: null, view: "now" };
const AU_DEMO = ["A02", "A04", "A05", "A07", "A10", "blog41", "blog42", "blog43", "A01", "A03", "A08"];   // 메타를 받기 전 라이브러리 버튼 표시용(서버 /api/autonomy/meta 가 기준)
const AU_LOCX = { AG_GARDEN: [381, 238] };   // 지도 그림의 더글라스 가든(map.js LOC 에 없는 계획기 장소)
const AU_DOM = { "식사": "#c8332f", "웰니스": "#3a7ea0", "산책": "#5f9455", "카페": "#b0773a", "문화": "#7a5aa6", "객실 휴식": "#c9bcaa", "행사": "#d39a12", "바": "#5b4a8a", "체류": "#8a7c6c", "휴식": "#d8cdbd", "대기": "#e7dfd2" };
const AU_TRAIT = { food: "식사 경험", space: "공간 · 풍경", value_check: "가격 비교", benefit: "혜택 활용", rest_need: "조용한 휴식", routine: "익숙한 방식", warm_rest: "온수 · 휴식", active: "활동적", alcohol_familiar: "와인 · 주류", novelty: "새 경험", premium: "프리미엄", food_specific: "분명한 음식 취향", practical_alt: "실용적 대안", breakfast_priority: "아침 식사", seasonal: "계절 · 행사", family: "가족 동반", kids: "아이 동반" };
const AU_PH = { checkin: "체크인 날", mid: "연박 중간일", checkout: "체크아웃 날", visit: "당일 방문" };
const AU_BLD = { VISTA: "비스타", GRAND: "그랜드", DOUGLAS: "더글라스" };
const AU_REL = { couple: "커플", spouse: "부부", friend: "친구", friends: "친구", family_kids: "아이 동반 가족", family_parents: "부모님 동반", solo: "혼자", group: "일행" };
const auT = s => { const [h, m] = String(s).split(":"); return +h * 60 + +m; };

async function auEnter() {
  const v = $("#autoView");
  if (!AU.meta) {
    v.innerHTML = `<div class="ox-load">자율 하루 준비 중…</div>`;
    try { AU.meta = await api("/api/autonomy/meta"); } catch (e) { v.innerHTML = `<div class="ox-load">열 수 없습니다 — ${esc(String(e.message || e))}</div>`; return; }
    if (!AU.sel.size) AU.meta.personas.forEach(p => AU.sel.add(p));   // 라이브러리에서 한 고객으로 들어온 경우 그 선택 유지
    try { if (typeof libLoad === "function") await libLoad(); } catch (e) {}
    if (typeof AG !== "undefined" && !AG.avm) { try { const r = await fetch("/static/avatars/manifest.json", { cache: "no-cache" }); AG.avm = r.ok ? await r.json() : {}; } catch (e) { AG.avm = {}; } }
  }
  auRender();
  if (!AU.res && !AU.busy) auRun();
}
const auType = pid => (typeof opxType === "function" ? opxType(pid) : "");
const auAv = (pid, n, s) => { try { return agAvatarIcon(pid, n || 2, s); } catch (e) { return ""; } };
function auGist(pid, fid) {   // 이미 받은 라이브러리 자료에서 그 고객의 후기 사실 요지를 찾는다(새 요청 없음)
  try { const p = LIBV.data.personas.find(x => x.id === pid); const f = p && p.engine && p.engine.facts && p.engine.facts[fid]; return f && !f.hidden ? f.gist : ""; } catch (e) { return ""; }
}
function auVisit(v) { return v ? `${v.stay ? `${AU_BLD[v.building] || v.building} ${v.nights}박 · ${AU_PH[v.phase] || v.phase}` : "당일 방문"} · ${v.party_size}인${AU_REL[v.rel] ? ` · ${AU_REL[v.rel]}` : ""}` : ""; }

function auRender() {
  const v = $("#autoView"); if (!v) return;
  v.innerHTML = `<div class="ox au"><aside class="ox-l">${auLeft()}</aside><section class="ox-c" id="auC">${auCenter()}</section><aside class="ox-r" id="auR">${auRight()}</aside></div>`;
  auWire();
}
function auLeft() {
  const m = AU.meta, n = AU.sel.size;
  return `<div class="ox-ls"><div class="ox-h"><h2>자율 하루</h2><p>후기 기반 고객 ${m.personas.length}명 · 각자 방문 조건 · 각자 하루</p></div>
    <div class="ox-grp"><div class="ox-lab">고객 <span class="cf-badge">${n}명 선택</span></div>
      <div class="au-pick">${m.personas.map(p => `<button type="button" class="ox-pill${AU.sel.has(p) ? " on" : ""}" data-au="${esc(p)}">${auAv(p, 2, 20)}${esc(p)}</button>`).join("")}</div>
      <div class="au-row"><button type="button" class="cf-link" id="auAll">전체 11명</button><button type="button" class="cf-link" id="auNone">모두 해제</button></div>
      <p class="ox-note">1명만 고르면 개별 실행, 여러 명이면 같은 월드 · 같은 시계로 동시에 실행합니다.</p></div>
    <div class="ox-grp"><div class="ox-lab">운영자 개입</div>
      <select class="cf-input" id="auIv">${Object.entries(m.interventions).map(([k, l]) => `<option value="${k}" ${AU.iv === k ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
      <label class="cf-check"><input type="checkbox" id="auCmp" ${AU.cmp ? "checked" : ""}>개입 전 하루와 비교</label></div></div>
    <div class="ox-run"><div class="ox-st ox-st-${AU.busy ? "busy" : AU.err ? "err" : AU.res ? "ok" : "idle"}">${AU.busy ? "하루를 진행하는 중…" : AU.err ? esc(AU.err) : AU.res ? `${Object.keys(AU.res.personas).length}명 하루 완료 · ${AU.res.mode === "many" ? "동시 실행" : "개별 실행"}` : "실행 전"}</div>
      <button type="button" class="cf-btn cf-primary" id="auRun" ${AU.busy || !n ? "disabled" : ""}>${n === 1 ? "1명 하루 실행" : `${n}명 동시 실행`}</button></div>`;
}
function auBar(log, base) {   // 07:00~23:00 하루 막대 — 영역별 색
  const T0 = 7 * 60, T1 = 23 * 60, W = T1 - T0;
  const seg = x => { const a = Math.max(T0, auT(x.t)), b = Math.min(T1, auT(x.e)); if (b <= a || x.act === "move") return ""; return `<i class="au-seg" style="left:${(a - T0) / W * 100}%;width:${(b - a) / W * 100}%;background:${AU_DOM[x.domain] || "#ddd"}" title="${esc(x.t)} ${esc(x.label)}"></i>`; };
  return `<div class="au-bar${base ? " base" : ""}">${log.map(seg).join("")}</div>`;
}
function auCenter() {
  const R = AU.res;
  if (!R) return `<div class="ox-empty">${AU.busy ? "고객들이 하루를 진행하고 있습니다…" : "고객을 고르고 실행하세요."}</div>`;
  const ids = Object.keys(R.personas), C = R.compare || {};
  const hours = [7, 9, 11, 13, 15, 17, 19, 21, 23].map(h => `<span style="left:${(h - 7) / 16 * 100}%">${h}</span>`).join("");
  const ivLine = R.intervention && R.intervention.id !== "none" ? `<div class="ox-mode ox-mode-compete"><b>운영자 개입</b> ${esc(R.intervention.label)}</div>` : "";
  const cls = Object.values(C).reduce((m, v) => { const k = v.cls.split(" · ")[0]; m[k] = (m[k] || 0) + 1; return m; }, {});
  const rows = ids.map(pid => { const r = R.personas[pid], c = C[pid];
    const acts = r.log.filter(x => !["move", "wait", "idle"].includes(x.act));
    const hl = acts.filter(x => x.source === "quantitative_engine" || x.source === "planner_rules").slice(0, 4).map(x => x.label.replace(/\(.*?\)/g, "")).join(" → ");
    return `<div class="au-p${AU.focus === pid ? " on" : ""}" data-aup="${esc(pid)}"><div class="au-ph">${auAv(pid, r.visit.party_size, 30)}<div><b>${esc(pid)}</b><span class="ox-sub">${esc(auType(pid))}</span></div><span class="au-v">${esc(auVisit(r.visit))}</span>${c ? `<span class="au-cls au-cls-${c.cls.startsWith("원래") ? "keep" : "chg"}">${esc(c.cls.split(" · ")[0])}</span>` : ""}</div>
      ${c && R.baseline ? `<div class="au-bars"><span class="au-bl">개입 전</span>${auBar(R.baseline[pid].log, true)}<span class="au-bl">개입 뒤</span>${auBar(r.log)}</div>` : auBar(r.log)}
      <div class="au-hl">${esc(hl)}</div></div>`; }).join("");
  const legend = Object.entries(AU_DOM).filter(([k]) => !["대기", "휴식"].includes(k)).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join("");
  return `<div class="ox-what"><div class="ox-k">${R.mode === "many" ? "동시 실행 · 같은 월드 · 같은 시계" : "개별 실행"}</div><h3>${ids.length}명의 하루</h3>
      <p>고객마다 숙박 · 동행 · 체류 단계를 각자의 후기와 성향으로 정하고, 그 시각 할 수 있는 행동 가운데 스스로 고릅니다.</p></div>
    ${auMap()}
    ${ivLine}${Object.keys(cls).length ? `<div class="au-sum">${Object.entries(cls).map(([k, n]) => `<span><b>${n}</b> ${esc(k)}</span>`).join("")}</div>` : ""}
    <div class="ox-sec"><div class="au-scale">${hours}</div>${rows}<div class="au-leg">${legend}</div></div>`;
}
function auRight() {
  const R = AU.res; if (!R) return `<div class="ox-empty">고객을 고르면 시간순 행동이 나옵니다.</div>`;
  const pid = AU.focus && R.personas[AU.focus] ? AU.focus : Object.keys(R.personas)[0]; const r = R.personas[pid], c = (R.compare || {})[pid];
  const newKeys = new Set(((c && c.new) || []).map(x => x.join("|")));
  const dev = (() => { try { return localStorage.getItem("wh_dev") === "1" || document.body.classList.contains("devmode"); } catch (e) { return false; } })();
  const ev = x => (x.evidence || []).map(e => e.type === "후기에서 확인"
      ? `<div class="au-ev au-ev-r"><b>후기에서 확인</b>${(e.fact_ids || []).map(f => auGist(pid, f)).filter(Boolean).slice(0, 2).map(g => `<span>${esc(g)}</span>`).join("") || `<span>${esc(e.about)} · 후기 사실 ${(e.fact_ids || []).length}건</span>`}</div>`
      : `<div class="au-ev au-ev-p"><b>프로파일 기반 추론</b><span>${(e.traits || []).map(t => AU_TRAIT[t] || t).join(" · ") || esc(e.about)}</span></div>`).join("");
  const items = r.log.filter(x => x.act !== "move" && !(x.act === "wait" && auT(x.e) - auT(x.t) < 20)).map(x => `<li class="au-it${newKeys.has(`${x.act}|${x.loc}`) ? " new" : ""}${auT(x.t) <= AU.tm && AU.tm < auT(x.e) ? " now" : ""}" style="--dc:${AU_DOM[x.domain] || "#ccc"}" data-aut="${esc(x.t)}">
      <div class="au-tm">${esc(x.t)}</div><div class="au-bd"><b>${esc(x.label)}</b>${x.why ? `<p>${esc(x.why)}</p>` : ""}${auCharge(x.charge)}${ev(x)}${auChoice(x)}
      ${dev && x.internal && Object.keys(x.internal).length ? `<details class="au-dev"><summary>개발 정보</summary><code>${esc(JSON.stringify(Object.assign({ source: x.source }, x.internal)).slice(0, 900))}</code></details>` : ""}</div></li>`).join("");
  return `<div class="ox-rh">${auAv(pid, r.visit.party_size, 44)}<div><b>${esc(pid)}</b><span>${esc(auType(pid))}</span></div><button type="button" class="cf-link au-prof" data-auprof="${esc(pid)}">프로파일 보기</button></div>
    <p class="au-vline">${esc(auVisit(r.visit))}</p>${auStory(pid)}
    <div class="au-lh">시간순 행동 <span>행동을 누르면 지도에서 그 시각으로 이동</span></div>
    <ol class="au-log">${items}</ol>`;
}
function auWire() {
  $$("#autoView [data-au]").forEach(b => b.onclick = () => { const p = b.dataset.au; AU.sel.has(p) ? AU.sel.delete(p) : AU.sel.add(p); auRender(); });
  const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e[ev] = fn; };
  on("auAll", "onclick", () => { AU.meta.personas.forEach(p => AU.sel.add(p)); auRender(); });
  on("auNone", "onclick", () => { AU.sel.clear(); auRender(); });
  on("auIv", "onchange", e => { AU.iv = e.target.value; });
  on("auCmp", "onchange", e => { AU.cmp = e.target.checked; });
  on("auRun", "onclick", () => auRun());
  $$("#autoView [data-aup]").forEach(el => el.onclick = () => auFocus(el.dataset.aup));
  auWireMap(); auWireRight();
}
function auFocus(pid) { AU.focus = pid; AU.follow = false; $$("#autoView [data-aup]").forEach(z => z.classList.toggle("on", z.dataset.aup === pid)); auRefresh(); const r = $("#auR"); if (r) r.scrollTop = 0; }
function auRefresh() {   // 지도 · 오른쪽만 다시 그림(왼쪽 · 하루 막대 상태 유지)
  const m = $("#auMapBox"); if (m) { m.outerHTML = auMap(); auWireMap(); }
  const r = $("#auR"); if (r) { const top = r.scrollTop; r.innerHTML = auRight(); auWireRight(); const cur = r.querySelector(".au-it.now"); if (cur && AU.follow) cur.scrollIntoView({ block: "nearest" }); else r.scrollTop = top; }
}
function auWireRight() {
  $$("#auR [data-aut]").forEach(li => li.onclick = ev => { if (ev.target.closest("details, button, a")) return; AU.tm = auT(li.dataset.aut) + 1; AU.follow = false; auRefresh(); });
  $$("#auR [data-auprof]").forEach(b => b.onclick = () => { setMode("library"); setTimeout(() => { try { libOpen(b.dataset.auprof); } catch (e) {} }, 0); });
}
// ── 지도 — 선택한 시각에 고객이 어디서 무엇을 하는지(같은 실행 기록 · 새 계산 없음) ──
const auP = l => AU_LOCX[l] || (typeof LOC !== "undefined" ? LOC[l] : null);
function auPos(log, t) {
  if (!log.length || t < auT(log[0].t)) return null;
  let last = null;
  for (const x of log) {
    const a = auT(x.t), b = auT(x.e);
    if (t >= a && t < b) {
      if (x.act === "move" && auP(x.loc_from) && auP(x.loc)) { const f = (t - a) / Math.max(1, b - a), p0 = auP(x.loc_from), p1 = auP(x.loc); return { p: [p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f], x, moving: true }; }
      return auP(x.loc) ? { p: auP(x.loc), x } : null;
    }
    if (a <= t) last = x;
  }
  if (!last || ["leave"].includes(last.act) || (last.act === "checkout" && last.loc === "HOTEL_GATE")) return null;
  return auP(last.loc) ? { p: auP(last.loc), x: last, after: true } : null;
}
function auMap() {
  const R = AU.res; if (!R || typeof MAP_W === "undefined") return `<div id="auMapBox"></div>`;
  const ids = Object.keys(R.personas), t = AU.tm, fx = AU.focus && R.personas[AU.focus] ? AU.focus : ids[0];
  const at = ids.map(pid => ({ pid, s: auPos(R.personas[pid].log, t) })).filter(o => o.s);
  const grp = {}; at.forEach(o => { const k = o.s.moving ? o.pid : o.s.p.join(","); (grp[k] = grp[k] || []).push(o); });
  const marks = Object.values(grp).flatMap(g => g.map((o, i) => { const n = g.length, a = -Math.PI / 2 + 2 * Math.PI * i / n, rr = n > 1 ? 15 + n * 2 : 0;
    const x = o.s.p[0] + rr * Math.cos(a), y = o.s.p[1] + rr * Math.sin(a), on = o.pid === fx, cp = (typeof agComp === "function") ? agComp(o.pid, R.personas[o.pid].visit.party_size) : {}, r0 = on ? 15 : 11;
    const img = cp && cp.av ? `<clipPath id="auc-${o.pid}"><circle cx="${x}" cy="${y}" r="${r0}"/></clipPath><image href="/static/avatars/${cp.av}_portrait.png" x="${x - r0}" y="${y - r0}" width="${r0 * 2}" height="${r0 * 2}" preserveAspectRatio="xMidYMin slice" clip-path="url(#auc-${o.pid})"/>` : "";
    return `<g class="au-mk${on ? " on" : ""}" data-aumk="${esc(o.pid)}"><title>${esc(o.pid)} · ${esc(o.s.x.label)}</title><circle cx="${x}" cy="${y}" r="${r0 + 2}" class="au-mkr" style="stroke:${AU_DOM[o.s.x.domain] || "#999"}"/>${img}${on || n === 1 ? `<text x="${x}" y="${y + r0 + 12}" class="au-mkt">${esc(o.pid)}</text>` : ""}</g>`; }));
  const fl = R.personas[fx].log.filter(x => x.act !== "move" && auP(x.loc));
  const pts = fl.filter((x, i) => i === 0 || x.loc !== fl[i - 1].loc).map(x => auP(x.loc));
  const path = pts.length > 1 ? `<polyline class="au-path" points="${pts.map(p => p.join(",")).join(" ")}"/>` + pts.map((p, i) => `<circle class="au-pdot" cx="${p[0]}" cy="${p[1]}" r="3.5"/>`).join("") : "";
  const cur = at.find(o => o.pid === fx), hh = String(Math.floor(t / 60)).padStart(2, "0") + ":" + String(t % 60).padStart(2, "0");
  const ivAt = R.intervention && R.intervention.id !== "none" ? (AU.meta.iv_at || {})[R.intervention.id] : null;
  return `<div class="au-map" id="auMapBox"><div class="au-mh"><b>${hh}</b><span>${at.length}명 현장 · ${esc(fx)} ${cur ? `<em>${esc(cur.s.x.label)}${cur.s.moving ? " (이동 중)" : ""}</em>` : "<em>현장에 없음</em>"}</span>
      <button type="button" class="cf-btn cf-sm" id="auPlay">${AU.play ? "❚❚ 멈춤" : "▶ 재생"}</button></div>
    <div class="au-mwrap"><svg viewBox="0 0 ${MAP_W} ${MAP_H}" class="au-svg"><image href="${MAP_IMG}" x="0" y="0" width="${MAP_W}" height="${MAP_H}" preserveAspectRatio="none"/>${path}${marks.join("")}</svg></div>
    <input type="range" id="auTm" min="${7 * 60}" max="${23 * 60}" step="5" value="${t}" class="au-range" aria-label="지도 시각">
    <div class="au-mfoot"><span>07:00</span><span>지도 점선 = ${esc(fx)}의 오늘 동선 · 아바타 테두리 색 = 지금 하는 행동 영역 · 이동 시간은 지도 거리감 연출값</span><span>23:00</span></div></div>`;
}
function auWireMap() {
  const r = $("#auTm"); if (r) r.oninput = e => { AU.tm = +e.target.value; AU.follow = true; auRefresh(); };
  $$("#autoView [data-aumk]").forEach(g => g.onclick = () => auFocus(g.dataset.aumk));
  const pb = $("#auPlay"); if (pb) pb.onclick = () => { if (AU.play) { clearInterval(AU.play); AU.play = null; auRefresh(); return; }
    if (AU.tm >= 23 * 60) AU.tm = 7 * 60; AU.follow = true;
    AU.play = setInterval(() => { if (MODE !== "auto" || AU.tm >= 23 * 60) { clearInterval(AU.play); AU.play = null; auRefresh(); return; } AU.tm += 5; auRefresh(); }, 120); auRefresh(); };
}
// ── 운영자 개입 이야기 — 원래 계획 → 새 조건 → 검토한 대안 → 선택(서버 stories · 실행 기록에서 만든 것) ──
function auEvShort(pid, evs) {
  return (evs || []).map(e => e.type === "후기에서 확인" ? `<span class="au-tag r">후기에서 확인</span>${esc((e.fact_ids || []).map(f => auGist(pid, f)).filter(Boolean)[0] || e.about || "")}` : `<span class="au-tag p">프로파일 기반 추론</span>${esc((e.traits || []).map(t => AU_TRAIT[t] || t).join(" · ") || e.about || "")}`).join("<br>");
}
function auStory(pid) {
  const S = (AU.res.stories || {})[pid]; if (!S) return "";
  const step = (k, body, cls) => `<li${cls ? ` class="${cls}"` : ""}><span class="au-sk">${k}</span><div>${body}</div></li>`;
  const notice = step("새 조건", esc(S.notice.text));
  if (S.keep_reason) return `<div class="au-story keep"><div class="au-sh">운영자 개입 · <b>${esc(S.cls)}</b></div><ol>${notice}${step("반응", esc(S.keep_reason))}</ol></div>`;
  const ci = S.steps.findIndex(x => x.kind === "선택");
  const rows = S.steps.map((x, i) => {
    const pre = i === ci && (S.considered.length || S.blocked.length) ? step("검토", [S.considered.length ? `함께 본 후보: ${S.considered.map(c => esc(c.label)).join(", ")}` : "", S.blocked.length ? `막힌 선택: ${S.blocked.map(c => `${esc(c.label)}(${esc(c.note)})`).join(", ")}` : ""].filter(Boolean).join("<br>")) : "";
    const body = x.kind === "선택" ? `<b>${esc(x.t)} ${esc(x.label)}</b> — ${esc(x.why || "")}${auCharge(x.charge)}<div class="au-sev">${auEvShort(pid, x.evidence)}</div>` : `${esc(x.t)} ${esc(x.label)} — ${esc(x.why || "")}`;
    return pre + step(x.kind, body, x.kind === "마감 확인" ? "hit" : "");
  }).join("");
  return `<div class="au-story"><div class="au-sh">운영자 개입 · <b>${esc(S.cls)}</b></div><ol>
    ${S.before.length ? step("원래 계획", S.before.map(b => `${esc(b.t)} ${esc(b.label)}`).join(" · ")) : ""}${notice}${rows}</ol></div>`;
}
function auCharge(c) {   // 공통 장부(ledger) — 유료 · 포함만 한 줄로(구매 없음 · 무료는 생략)
  if (c && c.fee_rule) {   // 행사 입장권(방문 조건별) — 입장료와 현장 추가 지출을 나눠 표시
    const fee = c.price_kind === "known_free" ? "입장료 0원 · 투숙객 무료 입장" : c.price_kind === "known_paid" ? `입장료 ${Number(c.krw).toLocaleString("ko-KR")}원 · 비투숙 성인 요금` : "입장료 미확인 · 퇴실 뒤 투숙객 무료 적용 여부 확인 필요";
    return `<div class="au-pay">${esc(fee)}<br><i>음식 · 유료 프로그램은 현장에서 따로 구매 — 가격 미정</i></div>`;
  }
  if (!c || !["유료", "포함", "가격 미정"].includes(c.status)) return "";
  return `<div class="au-pay">지출 · ${esc(c.status)}${c.krw ? ` ${Number(c.krw).toLocaleString("ko-KR")}원` : ""}${c.basis && !/[A-Z]{3,}/.test(c.basis) ? ` <i>${esc(String(c.basis).split(" · ")[0])}</i>` : ""}</div>`;
}
function auChoice(x) {
  const c = x.choice; if (!c || (!c.considered.length && !c.blocked.length) || ["move", "wait"].includes(x.act)) return "";
  return `<details class="au-ch"><summary>다른 선택은?</summary>${c.considered.length ? `<div>함께 본 후보 — ${c.considered.map(a => `${esc(a.label)} <i>${esc(a.note)}</i>`).join(" · ")}</div>` : ""}${c.blocked.length ? `<div>이 시각 막힌 선택 — ${c.blocked.map(a => `${esc(a.label)} <i>${esc(a.note)}</i>`).join(" · ")}</div>` : ""}</details>`;
}
// 라이브러리 · 다른 화면에서 한 고객의 자율 하루로 바로 가기
function auCan(pid) { return ((AU.meta && AU.meta.personas) || AU_DEMO).includes(pid); }
function auOpenFor(pid, iv) { AU.sel = new Set([pid]); AU.focus = pid; AU.res = null; AU.err = null; if (iv) AU.iv = iv; setMode("auto"); }
async function auRun() {
  if (AU.busy || !AU.sel.size) return;
  AU.busy = true; AU.err = null; auRender();
  const ids = AU.meta.personas.filter(p => AU.sel.has(p));
  try {
    const r = await fetch("/api/autonomy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ personas: ids, mode: ids.length > 1 ? "many" : "one", intervention: AU.iv, compare: AU.cmp && AU.iv !== "none" }) });
    const j = await r.json(); if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
    AU.res = j; if (AU.play) { clearInterval(AU.play); AU.play = null; }
    AU.tm = AU.iv === "pizzahill_full" ? 18 * 60 : AU.iv === "pool_check" ? 16 * 60 + 30 : AU.iv === "wine_fair_1300" ? 16 * 60 + 30 : 12 * 60; AU.follow = true;
    if (!AU.focus || !j.personas[AU.focus]) AU.focus = (AU.focus && j.personas[AU.focus] && (!j.compare || !j.compare[AU.focus].cls.startsWith("원래"))) ? AU.focus : Object.keys(j.compare || {}).find(p => !j.compare[p].cls.startsWith("원래")) || ids[0];
  } catch (e) { AU.err = "실행 실패 — " + (e.message || e); }
  AU.busy = false; auRender();
}
