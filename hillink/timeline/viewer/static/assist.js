// 10/16 힐링크 운영 어시스턴트 — 운영 요약 · 상황 비교가 함께 쓰는 하나의 어시스턴트. 대화 기록은 하나이고, 화면마다 추천 질문과 맥락 표시만 바뀐다.
// 지금 열린 결과(하루 · A/B 비교 · 선택 업장)와 등록된 근거(입력 출처표 · 약한 고리 · 시드 묶음)에서만 답한다. 언어 모델을 쓰지 않는다.
// 자유 입력은 지원하는 질문 중 하나로만 연결하고, 연결되지 않으면 '지금 데이터로는 답할 수 없다' 고 말한다.
const AS = { ctx: null, log: [], target: "rAssist" };
const AQ = [
  // 운영 요약 (하루 전체)
  { id: "bf", page: "report", q: "왜 더뷔페 조식에 몰리나요?", kw: /조식.*(몰|왜)|아침|08:?30|2부/ },
  { id: "busy", page: "report", q: "만석 시간이 가장 긴 업장은 어디인가요?", kw: /혼잡|붐비|붐빈|복잡|만석인 곳|만석 시간/ },
  { id: "flow", page: "report", q: "만석인 손님은 어디로 가나요?", kw: /어디로|행방|막힌|못 먹|못먹/ },
  { id: "ab", page: "report", q: "더뷔페 좌석을 늘리면 무엇이 달라지나요?", kw: /늘리|증설|338|테라스/ },
  { id: "closed", page: "report", q: "더뷔페가 하루 문을 닫으면?", kw: /휴업|문.*닫|닫으면|휴장/ },
  { id: "weak", page: "*", q: "이 결과에서 가장 약한 가정은 무엇인가요?", kw: /약한|가정|불확실|부족|믿을|신뢰/ },
  { id: "prep", page: "report", q: "내일 조식 준비량은 어떻게 보나요?", kw: /준비|발주|식재료|소비량/ },
  // 상황 비교 (전체)
  { id: "c_sum", page: "ask", q: "변경 전후 무엇이 달라졌나요?", kw: /달라|변화|전후|차이/ },
  { id: "c_top", page: "ask", q: "영향을 가장 많이 받은 업장은?", kw: /영향.*(업장|곳)|가장 많이|어디가/ },
  { id: "c_sure", page: "ask", q: "변화가 시드 흔들림보다 큰가요?", kw: /시드|흔들림|확실|우연|유의/ },
  // 상황 비교 + 선택 업장
  { id: "v_change", page: "ask", ven: "*", q: v => `이 상황에서 ${typeof josa === "function" ? josa(v, "은/는") : v + "은(는)"} 어떻게 달라지나요?`, kw: /이 업장|이 식당|이 시설|어떻게 달라/ },
  { id: "v_win", page: "ask", ven: "seat", q: () => "어느 회차가 여전히 막히나요?", kw: /회차|여전히|막히/ },
  { id: "v_flow", page: "ask", ven: "seat", q: v => `${v}에서 막힌 손님은 어디로 갔나요?`, kw: /어디로|행방|이동/ },
  { id: "v_pizza", page: "ask", ven: "PIZZA_HILL", q: () => "홀 · 포장 · 대기 중 어디서 막히나요?", kw: /포장|홀|대기/ },
  { id: "ab", page: "ask", ven: "THE_BUFFET", scn: "seat", q: () => "좌석을 늘리면 몇 명이 더 이용하나요?", kw: /늘리|몇 명|338/ },
  { id: "prep", page: "ask", ven: "THE_BUFFET", q: () => "준비량에는 어떤 입력이 더 필요한가요?", kw: /준비|발주|식재료/ },
  { id: "v_check", page: "ask", ven: "*", q: () => "현장에서 무엇을 확인해야 하나요?", kw: /현장|확인|검토|무엇을/ },
  // 판단 근거 — 이미 있는 정의 · 출처 · 가정을 찾아 설명만 한다 (새 근거를 만들지 않음)
  { id: "e_factor", page: "evidence", q: "어떤 정보가 손님 행동을 가장 잘 설명하나요?", kw: /어떤 정보|설명하|기여|예약 정보|정보 제거|정보 제외|결정 요인/ },
  { id: "e_why", page: "evidence", q: "성향을 추가했는데 왜 개선되지 않았나요?", kw: /왜 개선|성향.*(왜|개선|추가)|나빠/ },
  { id: "e_sel", page: "evidence", q: "지금 고른 조합은 무엇을 뜻하나요?", kw: /고른|선택한|이 조합|지금 조건/ },
  { id: "e_sens", page: "evidence", q: "조식 혼잡에 가장 민감한 가정은 무엇인가요?", kw: /민감|조식 혼잡|기상/ },
  { id: "e_wait", page: "evidence", q: "대기 회피 성향을 행동에서 거꾸로 찾을 수 있나요?", kw: /대기 회피|역추정|줄|대기/ },
  { id: "e_count", page: "evidence", q: "이 수치는 어떻게 세나요?", kw: /세|계산|정의|고유|건|팀 수/ },
  { id: "e_onto", page: "evidence", q: "온톨로지와 비교하는 기준은 무엇인가요?", kw: /온톨로지|참조|기준일|일치|정합/ },
  { id: "e_actual", page: "evidence", q: "이 결과는 실제 워커힐 매출과 얼마나 다른가요?", kw: /실제|실적|매출|정확/ },
  { id: "e_trait", page: "evidence", q: "손님 성향은 결과에 반영되나요?", kw: /성향|페르소나|취향/ },
  { id: "e_hypo", page: "evidence", q: "어떤 가설이 모델에 들어갔나요?", kw: /가설|실험|채택|보류/ },
  { id: "e_chain", page: "evidence", q: "근거 사슬은 어떤 자료를 연결하나요?", kw: /사슬|연결|출처|자료/ },
];
const asVen = () => AS.ctx && AS.ctx.venue ? shortName(AS.ctx.venue) : "";
const asQText = q => typeof q.q === "function" ? q.q(asVen()) : q.q;
function asQs() {
  const c = AS.ctx; if (!c) return [];
  const page = c.page || "report";
  const L = AQ.filter(q => (q.page === "*" || q.page === page) && (!q.ven || (c.venue && (q.ven === "*" || q.ven === c.venue || (q.ven === "seat" && ((c.A && (c.A.venue_detail || {})[c.venue]) || (c.D.venue_detail || {})[c.venue]))))) && (!q.scn || (c.sc && c.sc.kind === q.scn)));
  return page === "evidence" ? [...L.filter(q => q.page === "evidence"), ...L.filter(q => q.page !== "evidence")] : L;
}
// 답이 어느 실행 · 화면에 대한 것인지 — 다른 맥락으로 바뀌면 '이전 실행에 대한 답변' 으로 표시한다
function asCtxKey(c) { return c ? [c.page, c.D && c.D.key, c.sc && c.sc.id, c.sc && c.sc.bKey, c.venue || ""].join("|") : ""; }
function asCtxLabel(c) {
  if (!c) return "";
  if (c.page === "evidence") return c.D ? `판단 근거 · ${c.D.date.slice(5).replace("-", "/")} · ${c.D.knobs ? knobSummary(c.D) : "기본 모델"}` : "판단 근거";
  const D = c.D, dl = `${D.date.slice(5).replace("-", "/")} (${"일월화수목금토"[new Date(D.date + "T12:00:00").getDay()]})`;
  return c.page === "ask" ? `상황 비교 · ${dl} · ${c.sc ? c.sc.label : "-"}${c.venue ? " · " + locName(c.venue) : ""}` : `운영 요약 · ${dl} · ${D.scenario === "winefair" ? "와인페어 있음" : "행사 없음"} · ${knobSummary(D)}`;
}

function assistSet(ctx, target) { AS.ctx = ctx; if (target) AS.target = target; assistRender(); }

function asClose(L) { if (!L) return; L.classList.add("as-closed"); L.classList.remove("as-show"); const b = L.querySelector("#v2Asst"); if (b) { b.setAttribute("aria-pressed", "false"); b.focus({ preventScroll: true }); } }
function asEscWire() {
  if (asEscWire.done) return; asEscWire.done = true;
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    const dr = document.getElementById("drawer"); if (dr && !dr.classList.contains("hidden")) return;   // 상세 패널이 위에 있으면 그것부터 닫힌다
    if (document.querySelector(".nfo-pop")) return;
    const L = document.querySelector(".rlayout.as-show:not(.as-closed)");
    if (L) asClose(L);
  });
}
function assistRender() {
  if (typeof ecLoad === "function" && !ECI) ecLoad();
  const el = document.getElementById(AS.target);
  if (!el) return;
  const c = AS.ctx;
  if (!c) { el.innerHTML = `<div class="as-head"><b>힐링크 운영 어시스턴트</b></div><div class="hint">하루 전체 결과나 상황 비교를 열면 질문할 수 있습니다.</div>`; return; }
  const cur = asCtxKey(c);
  el.innerHTML = `<div class="as-head"><div><b>힐링크 운영 어시스턴트</b><div class="hint">지금 열린 결과와 등록된 근거에서만 답합니다</div></div>${AS.target === "rAssist" ? `<button class="as-x" title="닫기">×</button>` : ""}</div>
    <div class="as-ctx"><small>지금 보고 있는 결과</small><div class="as-ctxv">${esc(asCtxLabel(c))}</div></div>
    ${c.page !== "evidence" ? asqForm() : ""}
    <div class="as-qh">추천 질문</div>
    <div class="as-qs">${asQs().map(q => `<button class="as-q" data-q="${q.id}">${esc(asQText(q))}<span>›</span></button>`).join("")}</div>
    <div class="as-log">${AS.log.map(x => `<div class="as-me">${esc(x.q)}</div><div class="as-ans ${x.key !== cur ? "old" : ""}">${x.key !== cur ? `<div class="as-old">이전 화면 · 실행에 대한 답변입니다 (${esc(x.label)}). 지금 결과로 다시 물어보세요.</div>` : ""}${x.html}</div>`).join("")}</div>
    <form class="as-in"><input type="text" placeholder="질문을 입력하세요 (예: 조식은 왜 몰려?)" maxlength="80"><button type="submit">↵</button></form>
    <div class="hint as-foot">숫자는 시뮬레이션 결과이며 실측이 아닙니다. 괄호의 95% 구간은 같은 손님으로 반복 실행한 모델 변동성이지 예측 구간이 아닙니다. 답에 없는 내용은 만들지 않습니다.</div>`;
  el.querySelectorAll(".as-q").forEach(b => b.onclick = () => assistAsk(b.dataset.q));
  el.querySelector(".as-in").onsubmit = e => { e.preventDefault(); const t = e.target.querySelector("input").value.trim(); if (t) assistFree(t); };
  const x = el.querySelector(".as-x"); if (x) x.onclick = () => asClose(el.closest(".rlayout, .evlayout"));
  // 10/17 리뷰 1 — 1360px 이하에서는 오른쪽 상세 패널과 같은 방식: 바깥(어두운 배경) 클릭 · Esc · 위에 고정된 닫기 버튼으로 닫는다
  const L = el.closest(".rlayout"); if (L && !L.querySelector(":scope > .as-bg")) { const bg = document.createElement("div"); bg.className = "as-bg"; bg.onclick = () => asClose(L); L.appendChild(bg); }
  asEscWire();
  el.querySelectorAll(".as-ans:not(.old) .as-go").forEach(a => a.onclick = () => assistGo(a.dataset.go));
  const lg = el.querySelector(".as-log"); if (lg.lastElementChild) lg.lastElementChild.scrollIntoView({ block: "nearest" });
  asqWire(el);
}

// ── 10/16 운영 어시스턴트 2차 · 조건으로 묻기 — 날짜 · 업장 · 회차 · 고객군을 골라 이미 계산한 결과를 다시 센다 (서버 query.py · 새 계산 · 언어 모델 없음)
// 답마다 어느 계산(날짜 · 버전 · 시드 · 집계 기준)에서 나왔는지와 숫자에 걸린 가정을 근거 성격과 함께 붙인다.
const ASQ = { key: null, venue: "THE_BUFFET", window: "*", group: "all", g2: "", g3: "", opts: {}, open: true };
function asqDays() {
  const L = (typeof refreshDays !== "undefined" && refreshDays.list) || [];
  return L.filter(d => d.model_ver === LIB.model_ver && d.input_ver === LIB.input_ver && !(d.theta && d.theta.seed))
    .sort((a, b) => a.date.localeCompare(b.date) || String(a.knobs).localeCompare(String(b.knobs)));
}
const asqDayLabel = d => `${d.date.slice(5).replace("-", "/")} (${"일월화수목금토"[new Date(d.date + "T12:00:00").getDay()]})${d.scenario === "winefair" ? " · 와인페어" : ""}${(() => { const k = typeof knobParts === "function" ? knobParts(d).extra : []; return k.length ? " · " + k.join(" · ") : ""; })()}`;
function asqForm() {
  const days = asqDays();
  if (!ASQ.key || !days.some(d => d.key === ASQ.key)) ASQ.key = (AS.ctx && AS.ctx.D && days.some(d => d.key === AS.ctx.D.key)) ? AS.ctx.D.key : (days[0] || {}).key;
  if (!ASQ.key) return "";
  return `<details class="asq" ${ASQ.open ? "open" : ""}><summary>조건으로 묻기 <span class="hint">날짜 · 업장 · 회차 · 고객군</span></summary>
    <div class="asq-f"><select id="asqDay" title="날짜 (지금 버전으로 계산해 둔 날)">${days.map(d => `<option value="${esc(d.key)}" ${d.key === ASQ.key ? "selected" : ""}>${esc(asqDayLabel(d))}</option>`).join("")}</select>
    <select id="asqVen" title="업장"></select><select id="asqWin" title="회차"></select><select id="asqGrp" title="고객군"></select><select id="asqG2" title="추가 조건 (모두 만족)"></select><select id="asqG3" title="추가 조건 (모두 만족)"></select>
    <button id="asqGo" type="button">조회</button></div>
    <div class="hint">이미 계산한 하루 결과를 다시 셉니다(체크인 고객 기준). 그 날 운영 기준(연박 손님 포함) 값은 실험 결과가 있는 날만 업장 하루 단위로 덧붙입니다.</div></details>`;
}
const asqGroupParam = () => { const L = [...new Set([ASQ.group, ASQ.g2, ASQ.g3].filter(g => g && g !== "all"))]; return L.length > 1 ? L.join(",") : (L[0] || "all"); };
async function asqOpts(key) { if (!ASQ.opts[key]) ASQ.opts[key] = await api("/api/day/qopts?key=" + encodeURIComponent(key)); return ASQ.opts[key]; }
async function asqWire(el) {
  const box = el.querySelector(".asq"); if (!box) return;
  box.ontoggle = () => { ASQ.open = box.open; };
  const fill = async () => {
    let O; try { O = await asqOpts(ASQ.key); } catch (e) { return; }
    const ven = Object.entries(O.venues);
    if (!O.venues[ASQ.venue]) ASQ.venue = (ven[0] || [])[0];
    const V = O.venues[ASQ.venue] || { windows: [] };
    if (ASQ.window !== "*" && !V.windows.includes(ASQ.window)) ASQ.window = "*";
    if (!O.groups.some(g => g.id === ASQ.group)) ASQ.group = "all";
    const sv = el.querySelector("#asqVen"), sw = el.querySelector("#asqWin"), sg = el.querySelector("#asqGrp");
    if (!sv) return;
    sv.innerHTML = ven.map(([loc, v]) => `<option value="${loc}" ${loc === ASQ.venue ? "selected" : ""}>${esc(v.name)}</option>`).join("");
    sw.innerHTML = `<option value="*">회차 전체 (이 날)</option>` + V.windows.map(w => `<option ${w === ASQ.window ? "selected" : ""}>${esc(w)}</option>`).join("");
    sg.innerHTML = O.groups.map(g => `<option value="${esc(g.id)}" ${g.id === ASQ.group ? "selected" : ""}>${esc(g.label)}</option>`).join("");
    const extra = cur => `<option value="">+ 조건 없음</option>` + O.groups.filter(g => g.id !== "all").map(g => `<option value="${esc(g.id)}" ${g.id === cur ? "selected" : ""}>+ ${esc(g.label)}</option>`).join("");
    el.querySelector("#asqG2").innerHTML = extra(ASQ.g2); el.querySelector("#asqG3").innerHTML = extra(ASQ.g3);
  };
  el.querySelector("#asqDay").onchange = e => { ASQ.key = e.target.value; fill(); };
  el.querySelector("#asqVen").onchange = e => { ASQ.venue = e.target.value; ASQ.window = "*"; fill(); };
  el.querySelector("#asqWin").onchange = e => { ASQ.window = e.target.value; };
  el.querySelector("#asqGrp").onchange = e => { ASQ.group = e.target.value; };
  el.querySelector("#asqG2").onchange = e => { ASQ.g2 = e.target.value; };
  el.querySelector("#asqG3").onchange = e => { ASQ.g3 = e.target.value; };
  el.querySelector("#asqGo").onclick = () => asqAsk();
  await fill();
}
async function asqAsk() {
  const days = asqDays(), d = days.find(x => x.key === ASQ.key) || {};
  let R;
  try { R = await api(`/api/day/query?key=${encodeURIComponent(ASQ.key)}&venue=${ASQ.venue}&window=${encodeURIComponent(ASQ.window)}&group=${encodeURIComponent(asqGroupParam())}`); }
  catch (e) { asPush("조건으로 묻기", `<p>이 조건으로는 결과를 셀 수 없습니다 (${esc(e.message || "")}).</p>`); return; }
  if (R.error) { asPush("조건으로 묻기", `<p>이 조건으로는 결과를 셀 수 없습니다 (${esc(R.error)}).</p>`); return; }
  const q = `${asqDayLabel(d)} · ${R.venue_name} · ${R.window === "*" ? "회차 전체" : R.window} · ${R.group_label}`;
  asPush(q, asqAnswer(R, d));
}
function asqAnswer(R, d) {
  // 10/16 QA · 이 날 운영 회차가 없는 업장(휴업 · 다음 날 회차만)은 오류가 아니라 그 사실을 답한다
  if (R.status === "no_window") return `<p class="as-one"><b>${esc(R.venue_name)}</b> · ${esc(R.status_note)}</p><p class="as-lim">0명이라는 뜻이 아니라 이 날 열린 회차가 없다는 뜻입니다. 시뮬레이션 기록이며 실측이 아닙니다.</p>`;
  const rows = R.rows, sum = k => rows.reduce((a, r) => a + (r[k] || 0), 0);
  const P = sum("persons"), T = sum("teams"), TO = sum("takeout"), OP = sum("over_persons"), OT = sum("over_teams"), W = sum("window_persons"), K = sum("net_krw"), Q = sum("qty"), QT = sum("buy_teams");
  const one = rows.length === 1 ? rows[0] : null;
  const share = W ? Math.round(P / W * 100) : null;
  const bar = R.venue === "LUX_BAR" || R.venue === "LE_PASSAGE";
  const kRev = K ? ` · 이 고객군이 ${esc(R.venue_name)}에서 쓴 순매출 ${Math.round(K / 1e4).toLocaleString()}만 원` : "";
  let h;
  // 업장 종류마다 주지표를 집계 단위에 맞춘다 — 르파사쥬: 구매 바스켓 · 럭스바: 착석 인원과 결제 음료 수량(잔 · 병)을 함께 · 식당: 착석 인 · 회
  if (R.kind === "purchase") h = `<p class="as-one"><b>${esc(R.group_label)}</b> 구매 바스켓 ${asNum(Q)}건 (${asNum(QT)}팀)${TO ? ` · 포장 주문 손님 ${asNum(TO)}명` : ""}${kRev}.</p><p class="hint">르파사쥬는 앉아서 먹는 곳이 아니라 구매하는 곳이라 착석 인원을 주지표로 쓰지 않습니다.</p>`;
  else if (R.kind === "bar") h = `<p class="as-one"><b>${esc(R.group_label)}</b> 착석 ${asNum(P)}명 (${asNum(T)}팀) · 결제 음료 수량 ${asNum(Q)} (잔 · 병 섞임)${one ? ` · 좌석 ${R.cap}석 · 같은 시각 최고 점유 ${one.peak_pct ?? "-"}%` : ""}${kRev}.</p>`;
  else h = `<p class="as-one"><b>${esc(R.group_label)}</b> 착석 ${asNum(P)} 인 · 회 (${asNum(T)}팀)${TO ? ` · 포장 ${asNum(TO)}명` : ""}${R.group !== "all" && W ? ` · 같은 회차 전체 ${asNum(W)}명 중 ${share}%` : ""}` +
    `${one ? ` · 좌석 ${R.cap}석 · 같은 시각 최고 점유 ${one.peak_pct ?? "-"}%` : ""}${OP ? ` · 자리 · 대기 때문에 다른 선택 ${asNum(OP)}명 (${asNum(OT)}팀)` : ""}${kRev}.</p>`;
  if (rows.length > 1) h += R.kind === "purchase"
    ? `<table class="t as-t"><tr><th>회차</th><th class="n">구매 건</th><th class="n">구매 팀</th></tr>${rows.filter(r => r.qty).map(r => `<tr><td>${esc(r.window)}</td><td class="n">${asNum(r.qty)}</td><td class="n">${asNum(r.buy_teams)}</td></tr>`).join("")}</table>`
    : `<table class="t as-t"><tr><th>회차</th><th class="n">착석 인 · 회</th><th class="n">팀</th>${R.kind === "bar" ? `<th class="n">결제 수량</th>` : ""}<th class="n">최고 점유</th><th class="n">다른 선택</th></tr>${rows.filter(r => r.persons || r.over_persons || r.window_persons || r.qty).map(r => `<tr><td>${esc(r.window)}<div class="hint">${esc(r.t0.slice(6))}~${esc(r.t1)}</div></td><td class="n">${asNum(r.persons)}</td><td class="n">${asNum(r.teams)}</td>${R.kind === "bar" ? `<td class="n">${asNum(r.qty)}</td>` : ""}<td class="n">${r.peak_pct ?? "-"}%</td><td class="n">${r.over_persons ? asNum(r.over_persons) : ""}</td></tr>`).join("")}</table>`;
  if (R.group.includes(",")) h += `<p class="hint">여러 조건을 모두 만족하는 손님만 셉니다. 한 손님(팀)은 조건이 여럿이어도 한 번만 셉니다.</p>`;
  if (R.kind === "bar") h += `<p class="hint">착석 인원과 결제 음료 수량은 다른 단위입니다. 결제에는 잔과 병이 섞여 있어 잔 수로 읽지 않습니다. 온톨로지 '잔'과의 비교는 단위 미확정(△)입니다.</p>`;
  const O = R.operating;
  if (!O && R.operating_note) h += `<p class="hint">그 날 운영 기준: ${esc(R.operating_note)}</p>`;
  if (O) h += `<p><b>참고 · 다른 기준</b> — 위 숫자와 더하거나 바로 비교하지 마세요. <b>그 날 운영 기준</b> (연박 손님 포함 · 실험 · 시드 ${O.seeds.length}개): ${R.venue_name} 하루 ${Math.round(O.mean).toLocaleString()}${bar ? "" : "명"} (${Math.round(O.lo).toLocaleString()}~${Math.round(O.hi).toLocaleString()} · 시드 평균) · 단위 ${esc(O.unit)}. 회차 · 목적 · 연령으로는 아직 나누지 않았습니다.</p>`;
  const wk = isWeekday(R.date), kinds = new Set(rows.filter(r => r.persons || r.window_persons || r.over_persons).map(r => r.kind));
  const tags = [
    evTag("calc", "이 숫자", calcRef(d && d.key === R.key ? d : { date: R.date, model_ver: R.model_ver, input_ver: R.input_ver }, `시드 0 · ${R.basis}${R.check_ok ? " · 전체 합이 화면 회차별 인원과 일치" : " · 전체 합이 화면과 다름 · 확인 필요"}`)),
    evTag("op", `${R.venue_name} 좌석 ${R.cap}석 · 회차 · 운영 창`, evRef("prices.SEATS")),
    evTag("asm", "손님 처리 순서 (좌석 잡는 순서)", evRef("조정값 order_mix", "먼저 생성된 손님이 체류 전체 자리를 먼저 잡음 · 근거사슬 7-27")),
  ];
  const GP = R.group.split(",");
  if (GP.some(g => ["all", "day"].includes(g))) tags.push(evTag("asm", "비투숙 팀 수", evRef("generate.DAY_SCALE", wk ? "평일은 " + evRef("조정값 wd_day") : "")));
  if (GP.some(g => g.startsWith("p:") || g === "all")) tags.push(evTag("asm", "목적 섞기", evRef("purpose_mix.csv")));
  if (GP.some(g => g.startsWith("a:"))) tags.push(evTag("asm", "연령 섞기", evRef("age_mix.csv")));
  if (GP.some(g => ["kids", "n1", "n2", "guest"].includes(g))) tags.push(evTag("asm", "고객 구성 격자 (일행 · 아동 · 박수)", evRef("persona_grid.csv")));
  if (kinds.has("조식")) tags.push(evTag("asm", "조식 기상 시각 분포", evRef("generate.WAKE_SPREAD")), evTag("ref", "조식 포함 패키지 비중", evRef("generate.BREAKFAST_PKG")));
  if (GP.includes("n2") || kinds.has("조식")) tags.push(evTag("asm", "식음 행동은 체류 중 한 번 (모델 규칙)", "2박 손님의 두 번째 조식 · 둘째 밤 바가 생기지 않음 · 근거사슬 7-27 · 날짜별 선택 실험 진행 중"));
  h += evList(tags, "근거");
  h += `<p class="as-lim">시뮬레이션 손님의 기록이며 실측이 아닙니다. 실제 고객 행동으로 확인된 값이 아니라 모델이 만든 손님의 선택입니다. 체크인 고객 기준이라 전날 체크인한 연박 손님은 이 표에 없습니다(익일 회차는 이 날 체크인 손님의 다음 날).</p>`;
  h += asLinks(asLink(`${R.venue_name} 패널 열기`, "venue:" + R.venue));
  return h;
}

function assistFree(text) {
  const hit = asQs().find(q => q.kw.test(text));
  if (!hit) {
    asPush(text, `<p>지금 데이터로는 답할 수 없는 질문입니다. 이 어시스턴트는 지금 열린 결과로 답할 수 있는 질문만 받습니다. 위의 질문 가운데 가까운 것을 골라 주세요.</p>`);
    return;
  }
  assistAsk(hit.id, text);
}
function asPush(q, html) {
  AS.log.push({ q, html, key: asCtxKey(AS.ctx), label: asCtxLabel(AS.ctx) });
  AS.log = AS.log.slice(-6);
  assistRender();
}

function assistAsk(id, asked) {
  const q = asQs().find(x => x.id === id) || AQ.find(x => x.id === id);
  let html;
  try { html = (ASW[id] || (() => "<p>준비 중입니다.</p>"))(AS.ctx); }
  catch (e) { html = `<p>지금 결과로는 답을 만들지 못했습니다 (${esc(e.message)}).</p>`; }
  asPush(asked || asQText(q), html);
}

const asLink = (t, go) => `<a class="as-go" data-go="${esc(go)}">${esc(t)} →</a>`;
const asLinks = (...xs) => `<div class="as-links">${xs.filter(Boolean).join("")}</div>`;
const asNum = n => Math.round(n).toLocaleString();

function assistGo(go) {
  const [fn, ...rest] = go.split(":"), arg = rest.join(":");
  if (MODE === "ask" && typeof askOpen === "function") {
    if (fn === "askven") return askSelectVenue(arg);
    if (fn === "askab") { const d = document.getElementById("cmpAb"); if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth" }); } return; }
    if (fn === "venue") return askSelectVenue(arg);
    if (fn === "aday" || fn === "flowk") return askOpen((fn === "aday" ? "day:" : "flow:") + arg);
  }
  if (fn === "venue") { setMode("day"); placePanel(arg); }
  else if (fn === "constrained") { setMode("day"); showConstrained(arg); }
  else if (fn === "flow") { setMode("day"); showFlow(); }
  else if (fn === "ask") setMode("ask");
  else if (fn === "weak") goWeak();
  else if (fn === "evsec") evOpen(+arg);
  else if (fn === "lab") { if (MODE !== "evidence") setMode("evidence"); setTimeout(() => { const e = document.getElementById("labMain"); e && e.scrollIntoView({ behavior: "smooth", block: "start" }); }, 60); }
  else if (fn === "mapday") { setMode("day"); setMapView("day"); }
  else if (fn === "day") { setMode("day"); loadDay(arg); }
}

function asBreakfast(D) {
  const bf = (D.venue_detail || {}).THE_BUFFET;
  return bf ? bf.windows.filter(w => w.kind === "조식" && (w.persons || w.over_persons)) : [];
}

// 질문별 답 — 모두 지금 하루(D) · 정산 기록(FL) · 묶음(bands)에서 계산
const ASW = {
  bf(c) {
    const D = c.D, ws = asBreakfast(D), cap = ((D.venue_detail || {}).THE_BUFFET || {}).cap;
    if (!ws.length) return `<p>이 날은 더뷔페 조식 기록이 없습니다.</p>`;
    const over = ws.filter(w => w.over_persons > 0);
    let h = `<ol class="as-ol">`;
    h += `<li><b>회차별 결과</b> ${ws.map(w => `${esc(w.name.replace(" (익일)", ""))}(${w.t0.slice(-5)}~${w.t1}) ${asNum(w.persons)}명 착석 · 좌석의 ${w.peak_pct}%${w.over_persons ? ` · 초과 수요 ${asNum(w.over_persons)}명` : " · 여유"}`).join(" / ")}. 초과 수요는 자리가 없어 다른 선택을 한 팀의 일행 수이고, 팀마다 이 업장에서 처음 막힌 회차에 한 번만 셉니다.</li>`;
    const ev = c.FL && !c.FL.error ? (c.FL.events || []).filter(e => /더뷔페/.test(e.from) && e.meal === "조식") : [];
    if (ev.length) {
      const first = {}; ev.forEach(e => { if (!first[e.id] || e.t < first[e.id]) first[e.id] = e.t; });
      const cnt = {}; Object.values(first).forEach(t => { const k = t.slice(11, 16); cnt[k] = (cnt[k] || 0) + 1; });
      const [tk, tn] = Object.entries(cnt).sort((a, b) => b[1] - a[1])[0];
      const n = Object.keys(first).length;
      h += `<li><b>언제 막히나</b> 좌석 제약을 겪은 ${asNum(n)}팀 중 ${asNum(tn)}팀(${pctS(tn, n)}%)이 ${tk}에 처음 막혔습니다.</li>`;
    }
    if (ws.length > 1 && over.length && over.length < ws.length) h += `<li><b>왜 그 시각인가 (모델 규칙)</b> 앞 회차가 끝난 뒤 준비를 마친 손님은 다음 회차 시작 시각에 한꺼번에 줄을 섭니다. 그래서 회차 경계 직후에 수요가 모입니다.</li>`;
    h += `<li><b>적용된 가정</b> 손님 기상 시각은 06:30~09:00 을 30분 단위로 나눈 임시값입니다 ${gradeChip("△")}. 회차 안 줄 서기는 30분을 넘기면 포기합니다 ${gradeChip("△")}. 좌석 ${cap ? asNum(cap) + "석" : ""} · 회차는 가정표 값입니다.</li></ol>`;
    h += `<p class="as-lim">'${over.length ? "뒤 회차에 몰린다" : "몰리지 않는다"}' 는 모델 결과로 말할 수 있지만, 시각 자체가 실제 수요인지는 회차별 입장 기록으로 확인해야 합니다.</p>`;
    h += evList([evTag("calc", "회차별 착석 · 초과 수요", calcRef(D, "시드 0 한 번")), evTag("op", "더뷔페 좌석 · 회차", evRef("prices.SEATS", "업장마다 등급이 다름")),
      evTag("asm", "회차 안 줄 서기 상한 30분", evRef("조정값 queue_max")), evTag("asm", "손님 기상 시각 분포", evRef("generate.WAKE_SPREAD"))], "근거 성격 · 출처");
    return h + asLinks(asLink("더뷔페 회차 보기", "venue:THE_BUFFET"), ev.length ? asLink("좌석 제약을 겪은 팀 보기", "constrained:더뷔페 조식") : "", asLink("적용된 가정 · 확인할 자료", "weak"));
  },
  busy(c) {
    const D = c.D;
    const R = Object.entries(D.venue_detail || {}).filter(([l, v]) => v.cap && D.seats && D.seats[l]).map(([l, v]) => {
      const st = D.seats[l]; return { l, v, fullH: st.load.filter(x => x / st.cap >= 0.95).length / 6 };
    }).filter(x => x.fullH > 0 || x.v.over_persons > 0).sort((a, b) => b.fullH - a.fullH || (b.v.over_persons || 0) - (a.v.over_persons || 0)).slice(0, 4);
    if (!R.length) return `<p>이 날은 좌석이 95% 넘게 찬 업장이 없습니다.</p>`;
    return `<p class="as-one">기준: 좌석이 95% 넘게 찬 시간이 긴 순서입니다. 자리를 못 잡은 팀이 가장 많은 곳은 운영 요약의 '오늘의 핵심' 에서, 지금 시각에 가장 찬 곳은 고객 흐름의 '지금' 카드에서 봅니다(기준이 달라 순서가 다를 수 있습니다).</p><ol class="as-ol">${R.map(x => `<li><b>${esc(locName(x.l))}</b> 좌석이 95% 넘게 찬 시간 ${x.fullH.toFixed(1)}시간 · 가장 붐빈 회차 ${esc(x.v.peak_window || "-")}${x.v.over_persons ? ` · 초과 수요 ${asNum(x.v.over_persons)}명(막힌 팀의 일행 수)` : ""}</li>`).join("")}</ol>` +
      `<p class="as-lim">혼잡 시간은 10분 칸마다 좌석 점유율이 95% 이상인 칸을 더한 것입니다. 좌석 · 회차는 가정표 값입니다.</p>` +
      evList([evTag("calc", "좌석 점유 · 혼잡 시간", calcRef(D, "시드 0 한 번")), evTag("op", "업장 좌석 · 회차 · 운영 창", evRef("prices.SEATS", "업장마다 등급이 다름"))], "근거 성격 · 출처") +
      asLinks(asLink("지도에서 하루 누적 보기", "mapday"), asLink(`${locName(R[0].l)} 회차 보기`, `venue:${R[0].l}`));
  },
  flow(c) {
    const D = c.D, SW = D.switch || {}, MO = SW.meal_outcome || {}, n = SW.meal_cases || 0;
    if (!n) return `<p>이 날은 이용이 제한된 식사 기록이 없습니다.</p>`;
    const rows = Object.entries(MO).sort((a, b) => b[1] - a[1]);
    let h = `<p>좌석 제약으로 이용이 제한된 식사 ${asNum(n)}건(고객팀 · 날짜 · 식사 시간대마다 한 번)의 최종 결과입니다.</p><ol class="as-ol">${rows.map(([k, v]) => `<li><b>${esc(outName(k))}</b> ${pctS(v, n)}% (${asNum(v)}건)</li>`).join("")}</ol>`;
    const S = c.FL && !c.FL.error ? flowByStay(c.FL, D) : null;
    if (S && S.n.투숙 && S.n.비투숙) {
      const p = (k, x) => pctS(S.out[k][x] || 0, S.n[k]);
      h += `<p><b>투숙 · 비투숙이 다릅니다</b> 투숙 ${asNum(S.n.투숙)}건은 호텔 밖 · 객실 ${p("투숙", "호텔 밖 · 객실 식사")}%, 비투숙 ${asNum(S.n.비투숙)}건은 다른 호텔 식당 ${p("비투숙", "다른 호텔 식당")}%입니다.</p>`;
    }
    h += `<p class="as-lim">이 차이는 손님 취향이 아니라 모델의 선택지 구조에서 나옵니다. 지금 모델은 '객실 식사' 와 '호텔 밖 식사' 를 한 선택지로 묶어 객실 키가 있는 투숙객만 고르게 합니다. 막힌 뒤 실제 행선지를 보여 주는 후기는 2편뿐입니다.</p>`;
    h += evList([evTag("calc", `이용이 제한된 식사 ${asNum(n)}건의 행방`, calcRef(D, "시드 0 한 번")), evTag("asm", "식당 외 식사 선택지 (객실 키 필요)", evRef("계수 meal_other"))], "근거 성격 · 출처");
    return h + asLinks(asLink("막힌 곳 → 최종 흐름 보기", "flow"), asLink("약한 고리 1순위 보기", "weak"));
  },
  ab(c) {
    const b = c.AB;
    if (!b) return `<p>이 날은 좌석 조건 비교를 계산해 두지 않았습니다. 지금은 10/10 (토)에 더뷔페 288석 → 338석 비교가 있습니다.</p>` + asLinks(asLink("상황 비교 열기", "ask"));
    const E = b.effect || {}, row = (k, u, d = 0) => E[k] ? `${E[k].diff > 0 ? "+" : ""}${(+E[k].diff).toFixed(d)}${u} (95% 구간 ${(+E[k].lo95).toFixed(d)} ~ ${(+E[k].hi95).toFixed(d)})` : "-";
    return `<p>같은 날 · 같은 손님으로 더뷔페 좌석만 ${b.compare.buffet_seats}석으로 바꿔 ${b.seeds}번씩 짝지어 비교한 결과입니다.</p><ol class="as-ol">` +
      `<li><b>다음날 조식 이용</b> ${row("더뷔페 다음날 조식 이용 (명)", " 인 · 회")}</li>` +
      `<li><b>중식 · 석식 · 다음날 중식 이용</b> ${row("더뷔페 이용 (명)", " 인 · 회")}</li>` +
      `<li><b>공급 제한을 겪은 팀 (호텔 전체)</b> ${row("공급 제한 겪은 팀 (팀)", "팀")}</li>` +
      `<li><b>체류 매출</b> ${row("순매출 (억)", "억", 2)}</li></ol>` +
      `<p class="as-lim">좌석을 늘려도 제약을 겪는 팀 대부분이 남는 것은 특정 회차에 수요가 몰리기 때문입니다. 테라스를 식사에 쓸 수 있는지와 늘리는 비용은 모델에 없습니다. 괄호는 시드 짝 비교의 95% 구간으로, 모델을 반복해 돌린 변동성이지 예측 구간이 아닙니다.</p>` +
      asLinks(asLink("상황 비교에서 풀린 팀 보기", "ask"));
  },
  closed(c) {
    const b = (c.ANOM || []).find(x => +x.compare.anomaly === 1);
    if (!b && c.page === "ask") return `<p>상황 비교 화면에서는 위쪽 '더뷔페 하루 휴업' 칩을 누르면 같은 손님 · 시드 5쌍 짝 비교 결과가 나옵니다(10/10 (토) 계산돼 있음).</p>`;
    if (!b) return `<p>이 날은 '더뷔페 하루 휴업' 상황을 계산해 두지 않았습니다. 지금은 10/10 (토) 기준으로 계산돼 있습니다.</p>` + asLinks(asLink("상황 비교 열기", "ask"));
    const E = b.effect || {}, r = E["순매출 (억)"], t = E["공급 제한 겪은 팀 (팀)"];
    const mv = Object.entries(E).filter(([k, e]) => / 이용 \(명\)$/.test(k) && sureEffect(e, b.seeds)).sort((x, y) => Math.abs(y[1].diff) - Math.abs(x[1].diff)).slice(0, 3);
    return `<p>같은 손님 · 같은 시드로 더뷔페만 하루 닫고 ${b.seeds}번씩 짝지어 비교한 결과입니다.</p><ol class="as-ol">` +
      (r ? `<li><b>체류 매출</b> ${r.diff > 0 ? "+" : ""}${(+r.diff).toFixed(2)}억 (95% 구간 ${(+r.lo95).toFixed(2)} ~ ${(+r.hi95).toFixed(2)})</li>` : "") +
      (t ? `<li><b>공급 제한을 겪은 팀</b> ${t.diff > 0 ? "+" : ""}${Math.round(t.diff)}팀</li>` : "") +
      (mv.length ? `<li><b>손님이 옮겨 간 곳</b> ${mv.map(([k, e]) => `${esc(k.replace(" 이용 (명)", ""))} ${e.diff > 0 ? "+" : ""}${Math.round(e.diff)} 인 · 회`).join(" · ")}</li>` : "") + `</ol>` +
      `<p class="as-lim">다른 업장이 다 받아 주지 못해 손실로 남습니다. 휴업 상황의 크기와 손님 반응은 가정${gradeChip("△")}이고, 범위는 모델 반복 변동성이지 실제 손실 예측이 아닙니다.</p>` +
      evList([evTag("calc", "휴업 전후 체류 매출 · 이동", calcRef(c.D, `같은 손님 · 같은 시드 ${b.seeds}쌍 짝 비교`)), evTag("asm", "휴업 상황의 크기와 손님 반응", evRef("anomaly_scenarios.csv")), evTag("prop", "다른 업장의 대체 수용 여력 확인", "관련 실험 없음 · 효과 미실험")], "근거 성격 · 출처") +
      asLinks(asLink("이 상황의 하루 열어 보기", "day:" + b.compare_key), asLink("변칙 상황 표 보기", "ask"));
  },
  weak() {
    const W = (typeof WEAK !== "undefined" ? WEAK : []).slice(0, 3);
    if (!W.length) return `<p>약한 고리 목록을 읽지 못했습니다.</p>`;
    return `<p class="as-one">근거가 약하면서 결과를 크게 움직이는 가정 순서입니다. 같은 손님 · 같은 시드에서 가정 하나씩 바꿔 잰 영향 기준입니다(10/10 · 시드 3).</p><ol class="as-ol">` +
      W.map(w => `<li><b>${esc(w.name)}</b> ${gradeChip(w.grade)} ${esc(w.line)}<div class="hint">영향: ${esc(w.sens)}</div><div class="hint">필요한 자료: ${esc(w.need)}</div></li>`).join("") + `</ol>` +
      `<p class="as-lim">범위는 신뢰구간이 아니라 검토한 가정에서 나온 결과 범위입니다.</p>` +
      asLinks(asLink("약한 고리 전체와 필요한 자료", "weak"));
  },
  prep(c) {
    const ws = asBreakfast(c.D);
    if (!ws.length) return `<p>이 날은 더뷔페 조식 기록이 없습니다.</p>`;
    return `<p>모델상 착석 인원은 ${ws.map(w => `${esc(w.name.replace(" (익일)", ""))} ${asNum(w.persons)}명`).join(" · ")}입니다. 준비량은 '착석 인원 × 품목 선택률 × 1회 소비량' 으로 계산하며, 선택률과 소비량은 현장 값을 넣어야 합니다.</p>` +
      (() => { const m = String(ws[0].t0 || "").match(/(\d+)\/(\d+)/); const SB = m && typeof stayBreakfast === "function" ? stayBreakfast(c.D.date.slice(0, 5) + m[1].padStart(2, "0") + "-" + m[2].padStart(2, "0"), c.D) : null;
        return SB ? `<p><b>그 날 머무는 손님 기준</b> (연박 집계 · 실험 · 시드 ${SB.n}개): ${SB.rows.map(r => `${esc(r.name)} ${asNum(r.mean)}명(${r.lo}~${r.hi})`).join(" · ")}. 전날 · 그 전날 체크인한 연박 손님이 같은 좌석을 함께 쓴 결과입니다.</p>` : ""; })() +
      `<p class="as-lim">위 첫 숫자는 이 날 체크인한 손님의 다음날 조식만 센 결과입니다. 그 날 머무는 손님 기준은 앞 날짜를 이어 생성한 실험 값이고(워밍업 첫날 이월 0), 둘 다 실제 운영 실적이 아닙니다.</p>` +
      asLinks(asLink("준비량 계산 예시 열기 (더뷔페 패널)", "venue:THE_BUFFET"));
  },
};

// ── 상황 비교 답 — 결론 한 줄 · 핵심 수치 · 왜 · 확인할 것 · 바로가기
const asSec = (k, body) => body ? `<div class="as-sec"><b>${k}</b>${body}</div>` : "";
function asSureList(sc) {
  const b = sc.band, E = b.effect || {};
  return Object.entries(VEN_M).map(([loc, ms]) => { const m = ms[0], e = m && E[m[0]]; return e ? { loc, m, e, sure: sureEffect(e, b.seeds) } : null; }).filter(Boolean);
}
Object.assign(ASW, {
  c_sum(c) {
    const sc = c.sc; if (!sc) return `<p>비교할 상황을 먼저 고르세요.</p>`;
    if (!sc.band) {
      const d = (c.B.total - c.A.total) / 1.1 / 1e8;
      return `<p class="as-one">${esc(sc.label)}: 체류 매출 ${fmtD(d, 2)}억 (시드 0 한 번).</p>` + asSec("왜 한 번뿐인가", "이 비교는 손님 구성이 달라(행사 손님이 더해짐) 같은 손님끼리 짝지어 반복 비교하지 않았습니다. 크기를 흔들림과 구분할 수 없습니다.") + asLinks(asLink("A/B 상세", "askab"));
    }
    const E = sc.band.effect || {}, n = sc.band.seeds, r = E["순매출 (억)"], t = E["공급 제한 겪은 팀 (팀)"];
    const mv = asSureList(sc).filter(x => x.sure).sort((x, y) => Math.abs(y.e.diff) - Math.abs(x.e.diff)).slice(0, 3);
    const tw = t ? (t.diff >= 0 ? `${Math.round(t.diff)}팀 늘어납니다` : `${Math.round(-t.diff)}팀 줄어듭니다`) : "";
    return `<p class="as-one">'${esc(sc.label)}' 상황에서는 체류 매출이 ${Math.abs(r.diff).toFixed(2)}억 ${r.diff < 0 ? "줄고" : "늘고"}${sureEffect(r, n) ? "" : "(흔들림과 구분되지 않음)"}${tw ? `, 공급 제한을 겪는 팀이 ${tw}` : "."}</p>` +
      asSec(`핵심 수치 (시드 ${n}쌍 평균)`, `<ol class="as-ol"><li>체류 매출 ${fmtD(r.diff, 2)}억 (95% 구간 ${(+r.lo95).toFixed(2)} ~ ${(+r.hi95).toFixed(2)})</li>${t ? `<li>공급 제한을 겪은 팀 ${fmtD(t.diff)}팀 (95% 구간 ${Math.round(t.lo95)} ~ ${Math.round(t.hi95)})</li>` : ""}${mv.map(x => `<li>${esc(shortName(x.loc))} ${esc(x.m[1])} ${fmtD(x.e.diff)}${x.m[2]}</li>`).join("")}</ol><div class="hint">같은 손님 · 같은 시드 ${n}쌍 짝 비교 평균</div>`) +
      asSec("왜", sc.kind === "seat" ? "좌석 수만 바꾼 가정 실험입니다. 늘어난 좌석이 몰리는 회차에서 더 받는 몫이 이용 변화로 나옵니다." : (sc.a ? esc(anomLead(sc.a).replace(/\.?$/, ".")) + " 적용한 가정: " + esc(anomLines(sc.a, +((((c.D || {}).theta) || {}).anomaly_k || 1)).map(([x, y]) => `${x} ${y}`).join(" · ")) + "." : "변칙 상황을 넣어 수요 · 공급을 바꿨습니다.") + ` 상황의 크기는 가정${gradeChip((sc.a || {}).등급 || "△")}입니다.`) +
      asSec("확인할 것", sc.kind === "seat" ? "테라스를 식사에 쓸 수 있는지 · 비용은 모델에 없습니다." : "상황 크기의 근거(통계 · 동향)와 실제로 이런 날의 업장별 이용 기록") +
      asLinks(asLink("A/B 상세", "askab"), asLink("B 하루 열기", "aday:" + sc.bKey));
  },
  c_top(c) {
    const sc = c.sc; if (!sc || !sc.band) return `<p>짝 비교가 없는 상황이라 업장 순위를 매기지 않습니다. 업장을 직접 골라 시드 0 결과를 보세요.</p>`;
    const L = asSureList(sc).sort((x, y) => Math.abs(y.e.diff) - Math.abs(x.e.diff));
    const S = L.filter(x => x.sure);
    return `<p class="as-one">${S.length ? `이용 변화가 가장 큰 곳은 ${esc(shortName(S[0].loc))}(${fmtD(S[0].e.diff)}${S[0].m[2]})입니다.` : "흔들림과 구분되는 이용 변화가 있는 업장이 없습니다."}</p>` +
      asSec("업장별 (짝 비교 평균)", `<ol class="as-ol">${L.map(x => `<li><a class="as-go" data-go="askven:${x.loc}">${esc(shortName(x.loc))}</a> ${esc(x.m[1])} ${x.sure ? `<b>${fmtD(x.e.diff)}${x.m[2]}</b>` : `<span class="hint">뚜렷한 변화 확인 안 됨 (${fmtD(x.e.diff)}${x.m[2]})</span>`}</li>`).join("")}</ol>`) +
      `<p class="as-lim">'이용' 은 그 날 중식 · 석식과 다음날 중식을 더한 인원입니다(온톨로지 대조와 같은 정의). 업장 이름을 누르면 그 업장 상세로 갑니다.</p>`;
  },
  c_sure(c) {
    const sc = c.sc; if (!sc || !sc.band) return `<p>이 상황은 시드 한 번(0)만 있어 흔들림과 비교할 수 없습니다.</p>`;
    const E = sc.band.effect || {}, n = sc.band.seeds, ks = Object.keys(E), S = ks.filter(k => sureEffect(E[k], n));
    return `<p class="as-one">지표 ${ks.length}개 중 ${S.length}개가 시드 반복에서 방향이 일관된 변화입니다 (실제 효과 검증은 아님).</p>` +
      asSec("시드 반복에서 방향 일관", `<ol class="as-ol">${S.slice(0, 6).map(k => `<li>${esc(k.replace(/ 이용 \(명\)$/, " 이용 (인 · 회)").replace(/ 초과 수요 \(명\)$/, " 초과 수요 (막힌 팀의 일행 수)"))} ${fmtD(E[k].diff, Math.abs(E[k].diff) < 10 ? 2 : 0)} (95% 구간 ${(+E[k].lo95).toFixed(1)} ~ ${(+E[k].hi95).toFixed(1)})</li>`).join("")}</ol>`) +
      asSec("판정 기준", `같은 손님 · 같은 시드 ${n}쌍의 차이로 95% 구간을 냈고, 구간이 0을 넘지 않으며 거의 매번 같은 방향일 때 '시드 반복에서 방향 일관' 으로 봅니다. 이 범위는 정한 모델과 가정 안에서 반복해 돌린 변동성이지, 실제 호텔에서 효과가 확인됐다는 뜻이나 실제 결과의 예측 구간이 아닙니다.`) + asLinks(asLink("A/B 상세 표", "askab"));
  },
  v_change(c) {
    const loc = c.venue, sc = c.sc, va = (c.A.venue_detail || {})[loc], vb = (c.B.venue_detail || {})[loc];
    const ms = sc.band ? (VEN_M[loc] || []).filter(([k]) => (sc.band.effect || {})[k]) : [];
    const E = sc.band ? sc.band.effect : {}, n = sc.band ? sc.band.seeds : 1;
    const one = ms.length ? ms.filter(([k]) => sureEffect(E[k], n)).map(([k, lab, u]) => `${lab} ${fmtD(E[k].diff)}${u}`).join(", ") : "";
    return `<p class="as-one">${esc(locName(loc))}: ${one || (ms.length ? "흔들림과 구분되는 변화가 없습니다" : "짝 비교 지표가 없어 시드 0 결과만 있습니다")}.</p>` +
      (va || vb ? asSec("시드 0 한 번", `이용 팀 ${(va || {}).parties || 0} → ${(vb || {}).parties || 0}팀 · 이용 ${(va || {}).persons_day || 0} → ${(vb || {}).persons_day || 0} 인 · 회 · 초과 수요 ${(va || {}).over_persons || 0} → ${(vb || {}).over_persons || 0}명(막힌 팀의 일행 수)`) : asSec("시드 0 한 번", "이 시설은 좌석 · 매출을 업장 단위로 집계하지 않아 머문 인원만 있습니다.")) +
      asSec("확인할 것", esc(VEN_NEED[loc] || "회차 · 시간대별 실제 이용 인원")) + asLinks(asLink("업장 상세로", "askven:" + loc));
  },
  v_win(c) {
    const loc = c.venue, vb = (c.B.venue_detail || {})[loc];
    if (!vb) return `<p>이 업장은 회차 기록이 없습니다.</p>`;
    const ws = vb.windows.filter(w => w.persons || w.over_persons), O = ws.filter(w => w.over_persons > 0);
    return `<p class="as-one">${O.length ? `B 에서도 ${O.map(w => esc(w.name.replace(" (익일)", " (다음날)"))).join(" · ")}에 초과 수요가 남습니다.` : "B 에서는 모든 회차가 좌석 안에 들어옵니다."}</p>` +
      asSec("회차별 (B · 시드 0)", `<ol class="as-ol">${ws.map(w => `<li>${esc(w.name.replace(" (익일)", " (다음날)"))} ${w.persons}명 · 점유 ${w.peak_pct}%${w.over_persons ? ` · 초과 ${w.over_persons}명` : ""}</li>`).join("")}</ol>`) +
      asSec("왜", "회차제 좌석은 회차 끝까지 자리를 잡고, 앞 회차가 끝난 뒤 준비를 마친 손님은 다음 회차 시작에 몰립니다. 기상 시각 분포는 임시값" + gradeChip("△") + "입니다.") +
      asLinks(asLink("업장 상세로", "askven:" + loc), asLink("적용된 가정", "weak"));
  },
  v_flow(c) {
    const loc = c.venue, w0 = locKey(loc).split(" ")[0];
    const pick = F => { const o = {}; for (const [k, v] of Object.entries((F && F.flow) || {})) if (k.split(" ")[0] === w0) for (const [x, n] of Object.entries(v)) o[x] = (o[x] || 0) + n; return o; };
    const a = pick(c.FA), b = pick(c.FB), tb = Object.values(b).reduce((x, y) => x + y, 0), ta = Object.values(a).reduce((x, y) => x + y, 0);
    if (!ta && !tb) return `<p>이 업장에서 좌석 제약으로 이용이 제한된 식사가 없습니다.</p>`;
    const top = Object.entries(b).sort((x, y) => y[1] - x[1]);
    return `<p class="as-one">B 에서 이 업장에서 이용이 제한된 식사 ${tb}건(고유 식사 건, A ${ta}건) 중 가장 많이 간 곳은 ${top.length ? esc(top[0][0]) + ` ${pctS(top[0][1], tb)}%` : "-"}입니다.</p>` +
      asSec("최종 (B · 정산 기록)", `<ol class="as-ol">${top.map(([k, v]) => `<li>${esc(k)} ${v}건 · ${pctS(v, tb)}%</li>`).join("")}</ol>`) +
      `<p class="as-lim">'호텔 밖 · 객실 식사' 는 객실 식사와 호텔 밖 식사를 한 선택지로 묶은 것이고, 투숙객만 고를 수 있습니다. 비투숙 손님이 이 선택지를 못 고르는 것은 모델 구조의 한계입니다.</p>` +
      asLinks(asLink("B 하루의 흐름 보기", "flowk:" + c.sc.bKey), asLink("약한 고리 1순위", "weak"));
  },
  v_pizza(c) {
    const va = (c.A.venue_detail || {}).PIZZA_HILL || {}, vb = (c.B.venue_detail || {}).PIZZA_HILL || {};
    const why = {}; for (const e of (c.FB && c.FB.events) || []) if (/피자힐/.test(e.from || "")) why[e.why || "기타"] = (why[e.why || "기타"] || 0) + 1;
    const cap = (vb.takeout_day || 0) >= 40;
    return `<p class="as-one">B 에서 피자힐 홀 초과 수요 ${vb.over_persons || 0}명(막힌 팀의 일행 수), 포장 ${vb.takeout_day || 0}판${cap ? " (하루 한도 40판에 닿음)" : ""}입니다.</p>` +
      asSec("핵심 수치 (시드 0)", `<ol class="as-ol"><li>홀 이용 인원 ${va.persons_day || 0} → ${vb.persons_day || 0}명</li><li>홀 초과 수요 ${va.over_persons || 0} → ${vb.over_persons || 0}명</li><li>포장 ${va.takeout_day || 0} → ${vb.takeout_day || 0}판</li>${Object.keys(why).length ? `<li>막힌 이유 (선택 기준 건): ${Object.entries(why).map(([k, v]) => `${esc(k)} ${v}건`).join(" · ")}</li>` : ""}</ol>`) +
      asSec("왜", `포장 하루 한도 40판은 온톨로지 기준 수요에서 나온 값${gradeChip("○")}이지 실제 처리 능력이 아닙니다. 줄 30분 상한${gradeChip("△")}을 넘기면 다른 선택을 합니다.`) +
      asSec("확인할 것", esc(VEN_NEED.PIZZA_HILL)) + asLinks(asLink("업장 상세로", "askven:PIZZA_HILL"));
  },
  v_check(c) {
    const loc = c.venue;
    return `<p class="as-one">${esc(locName(loc))}에서 확인할 자료: ${esc(VEN_NEED[loc] || "회차 · 시간대별 실제 이용 인원")}.</p>` +
      asSec("구분", "확인된 운영 조건(좌석 · 운영 창, 가정표 등급 표시) · 모델 계산 결과(A/B 차이) · 미검증 검토안(효과를 실험하지 않은 안내)을 업장 상세 ④에 나눠 두었습니다.") +
      `<p class="as-lim">모델은 인력 배치 · 식자재 발주량을 계산하지 않습니다${/GEUMRYONG|MYONGWOLGWAN/.test(loc) ? ". 별실 · 단체 수요도 따로 다루지 않습니다(모델 미지원)" : ""}.</p>` +
      asLinks(asLink("업장 상세 ④로", "askven:" + loc), asLink("약한 고리 전체", "weak"));
  },
});

// 판단 근거 질문 — 판단 근거 화면에 이미 있는 표(EV_DEFS · 입력 출처표 · 가설표 · 근거 사슬 · 약한 고리)에서만 꺼낸다
Object.assign(ASW, {
  e_count() {
    const pick = ["공급 제한을 겪은 팀", "건 · 팀", "체류 매출", "95% 구간의 뜻"];
    return `<p class="as-one">화면의 숫자는 정해진 단위로 셉니다. 같은 말이라도 팀 · 건 · 인원이 다릅니다.</p><ol class="as-ol">${EV_DEFS.filter(d => pick.includes(d[0])).map(([a, b]) => `<li><b>${esc(a)}</b> ${esc(b)}</li>`).join("")}</ol>` +
      `<p class="as-lim">나머지 ${EV_DEFS.length - pick.length}가지 정의는 ① 숫자를 세는 방법에 있습니다.</p>` + asLinks(asLink("① 숫자 정의", "evsec:1"));
  },
  e_onto() {
    const R = EV.holdout || [], dl = ds => ds.slice(5).replace("-", "/");
    const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
    const rows = R.map(x => { const ms = Object.entries(x.ven).filter(([l]) => !UNIT_TBD.has(l)).map(([, a]) => mean(a)); return `${dl(x.date)} ${ms.filter(v => v >= 90 && v <= 110).length}/${ms.length}곳`; });
    return `<p class="as-one">기준일 10/10 (토)에 제공해 주신 온톨로지 모델과 업장별 이용을 맞춘 뒤, 같은 설정을 다른 날짜에 그대로 적용해 비교합니다.</p>` +
      asSec("핵심 수치", rows.length ? `업장 이용이 온톨로지의 90~110% 안에 든 곳: ${esc(rows.join(" · "))} (시드 평균 · 단위 대응이 확인된 업장만 · 피자힐 홀 · 명월관 · 럭스바는 단위 미확정)` : "날짜별 표를 아직 모으는 중입니다. ② 를 펼치면 표가 채워집니다.") +
      asSec("왜", "평일 두 날(10/7 · 10/14)은 평일 비투숙 배율을 정할 때 참고해 엄밀한 독립 검증이 아닙니다. 독립 검증에는 모델 수정에 쓰지 않은 새 날짜가 필요합니다.") +
      `<p class="as-lim">${EV_ONTO_NOTE}</p>` + asLinks(asLink("② 참조 모델 비교", "evsec:2"));
  },
  e_actual() {
    return `<p class="as-one">현재 데이터로는 확인할 수 없습니다.</p>` +
      asSec("왜", "워커힐의 실제 영업 실적을 받지 않았습니다. 비교한 것은 제공해 주신 온톨로지 참조 모델과의 차이이고, 시드 범위는 모델 반복 변동성이지 실제 매출 예측 구간이 아닙니다.") +
      asSec("확인할 것", "실제 실적과 비교하려면 날짜별 업장 이용 인원이나 매출 비율 같은 현장 자료가 필요합니다.") +
      asLinks(asLink("② 참조 모델 비교", "evsec:2"), asLink("⑦ 확보할 자료", "evsec:7"));
  },
  e_trait() {
    const TM = LIB.trait_model || {}, part = Object.entries(TM.always_on || {});
    return `<p class="as-one">${TM.lam_trait > 0 ? `성향이 강도 ${TM.lam_trait}로 점수에 들어갑니다.` : "후기에서 뽑은 성향 점수는 지금 행동 선택 점수에 반영되지 않습니다 (강도 0)."}</p>` +
      (part.length ? asSec("일부만 쓰이는 것", part.map(([k, v]) => `${esc(k)}: ${esc(v)}`).join(" · ")) : "") +
      asSec("왜", "후기 46편 교차검증에서 성향 강도가 모든 폴드에서 0으로 골라졌습니다. 성향을 넣으면 맞추지 않은 후기의 동선 재현이 나빠졌습니다.") +
      `<p class="as-lim">그래서 결과의 차이를 손님 취향 탓으로 설명하지 않습니다.</p>` + asLinks(asLink("④ 성향 적용", "evsec:4"));
  },
  e_hypo() {
    const HY = LIB.hypotheses || [], OPS = ["모델 기본값 반영", "영향 미미", "외부 근거 보강 필요", "현장 확인 필요"];
    return `<p class="as-one">가설 ${HY.length}개를 같은 손님 · 짝지은 시드로 비교해 운영 표시로 나눴습니다.</p><ol class="as-ol">${OPS.map(o => { const L = HY.filter(x => hOp(x) === o); return L.length ? `<li><b>${o}</b> ${L.map(x => `${hLabel(x)} ${esc(hName(x))}`).join(" · ")}</li>` : ""; }).join("")}</ol>` +
      asLinks(asLink("⑤ 가설 실험", "evsec:5"));
  },
  e_factor() {
    const F = typeof FACTOR !== "undefined" ? FACTOR : null;
    if (!F) return `<p class="as-one">실험 결과가 아직 읽히지 않았습니다. 잠시 뒤 다시 물어보세요.</p>`;
    const A = F.groups[0].res, b = A.A.brier;
    return `<p class="as-one">후기 ${F.groups[0].n} 체류에서 이번에 비교한 정보 중에는 예약 정보 제거의 성능 하락 폭이 가장 컸습니다. 성향 점수를 넣으면 Brier 는 오히려 나빠졌습니다.</p>` +
      asSec("핵심 수치", `Brier(낮을수록 좋음) 기준 ${b.toFixed(3)} → 예약 정보 제외 ${A.C1.brier.toFixed(3)} · 식사 포함 혜택 제외 ${A.C2.brier.toFixed(3)} · 둘 다 제외 ${A.C3.brier.toFixed(3)} · 성향 강도 1 ${A.B1.brier.toFixed(3)}. 재현율은 ${pct1(A.A.recall)}% → 예약 제외 ${pct1(A.C1.recall)}%.`) +
      asSec("왜", "예약과 포함 식사는 그 손님이 어디서 무엇을 할지 직접 정해 둔 사실이라, 빼면 모델이 그 손님의 동선을 놓칩니다.") +
      asSec("확인할 것", "방문 목적 · 아동 동반 · 공급 제약은 늘 들어 있어 빼 본 적이 없으므로, 그 정보와의 독립적인 설명력 비교는 아직 없습니다. 새 후기로 독립 검증도 필요합니다. 예약 · 식사 포함 혜택은 후기에서 사후 복원한 사실이라 호텔이 사전에 가진 예약 기록과 같은 뜻은 아닙니다.") +
      `<p class="as-lim">여러 체류의 평균 결과이며, 한 손님의 행동 원인을 단정하지 않습니다.</p>` + asLinks(asLink("행동 역추적 ③ 결과", "lab"), asLink("④ 성향 적용", "evsec:4"));
  },
  e_why() {
    const F = typeof FACTOR !== "undefined" ? FACTOR : null;
    if (!F) return `<p class="as-one">실험 결과가 아직 읽히지 않았습니다.</p>`;
    const A = F.groups[0].res, W = F.groups.find(g => g.id === "wait"), V = F.groups.find(g => g.id === "view");
    return `<p class="as-one">성향 점수를 추가하면 일부 행동의 선택 확률은 달라지지만, 전체 확률 예측의 Brier 점수는 악화됐습니다. 재현율은 ${pct1(A.A.recall)}% → ${pct1(A.B1.recall)}% 로 소폭 올랐습니다.</p>` +
      asSec("핵심 수치", `강도 1이면 ${A.B1.moved}개 체류에서 장소 확률이 0.25 넘게 움직이고, 기준보다 나아진 체류 ${A.B1.cmp.better} · 같은 체류 ${A.B1.cmp.same} · 나빠진 체류 ${A.B1.cmp.worse}. 조망을 중시하는 손님 묶음은 Brier ${V.res.A.brier.toFixed(3)} → ${V.res.B1.brier.toFixed(3)}, 대기 회피가 높은 손님 묶음만 ${W.res.A.brier.toFixed(3)} → ${W.res.B1.brier.toFixed(3)} 로 조금 나아졌습니다(차이는 작음).`) +
      asSec("왜 (가능한 설명)", "후기의 성향은 만족한 경험을 적은 것이라 선택을 정한 이유와 다를 수 있고, 예약 · 포함 식사처럼 직접 조건이 이미 행동을 설명하고 있으며, 성향이 갈릴 상황(대기 · 대체 선택)이 표본에 적습니다. 어느 것이 주된 이유인지는 이 실험만으로 가를 수 없습니다.") +
      asSec("확인할 것", "대기 · 혼잡을 실제로 겪은 후기 11체류로 대기 회피를 따로 역추정하는 실험을 진행할 예정입니다.") +
      `<p class="as-lim">'성향이 행동에 영향을 주지 않는다' 가 아니라 '지금 자료와 모델에서 성향 점수의 추가 설명력을 입증하지 못했다' 입니다.</p>` + asLinks(asLink("행동 역추적 ③ 결과", "lab"), asLink("④ 성향 적용", "evsec:4"));
  },
  e_sel() {
    const F = typeof FACTOR !== "undefined" ? FACTOR : null, L = EV && EV.lab;
    if (!F || !L) return `<p class="as-one">행동 역추적 화면의 선택을 읽지 못했습니다.</p>`;
    const G = F.groups.find(g => g.id === L.group) || F.groups[0], C = labCond(F);
    if (!C) return `<p class="as-one">지금 고른 조합(예약 ${L.book ? "포함" : "제외"} · 식사 포함 혜택 ${L.incl ? "포함" : "제외"} · 성향 ${({ off: "제외", "0": "기본", "1": "강도 1", "2": "강도 2" })[L.trait]})은 실험하지 않은 조합이라 답할 숫자가 없습니다.</p>` + asSec("확인할 것", "정보를 하나씩 바꾼 조건만 측정했습니다. ③ 아래 목록에서 측정한 조건을 고르세요.");
    const r = G.res[C.id], base = G.res.A;
    if (C.id === "A") return `<p class="as-one">'${esc(G.name)}' (${G.n} 체류)를 기본 모델로 본 결과입니다. Brier ${base.brier.toFixed(3)} · 재현율 ${pct1(base.recall)}% · 정밀도 ${pct1(base.precision)}%.</p>` + asSec("왜", "요인을 빼거나 성향 강도를 바꾸면 이 값과 비교합니다.");
    const v = typeof labSig === "function" && labSig(F, G, C.id) === false ? { t: "흔들림과 구분되지 않음" } : labVerdict(r.brier - base.brier);
    return `<p class="as-one">'${esc(G.name)}' (${G.n} 체류)에서 '${esc(C.name)}' 은 기본 모델과 비교해 ${{ "확률 예측 성능 크게 악화": "확률 예측 성능(Brier)이 크게 나빠졌습니다", "확률 예측 성능 악화": "확률 예측 성능(Brier)이 나빠졌습니다", "확률 예측 성능 개선": "확률 예측 성능(Brier)이 나아졌습니다", "차이 거의 없음": "Brier 차이가 거의 없습니다", "흔들림과 구분되지 않음": "Brier 차이가 체류별 흔들림(2 표준오차)과 구분되지 않습니다" }[v.t] || v.t}.</p>` +
      asSec("핵심 수치", `Brier ${base.brier.toFixed(3)} → ${r.brier.toFixed(3)} (${labD(r.brier - base.brier, 4)}) · 재현율 ${pct1(base.recall)}% → ${pct1(r.recall)}% · 나아진 · 같은 · 나빠진 체류 ${r.cmp.better} · ${r.cmp.same} · ${r.cmp.worse}`) +
      asSec("조건", (C.note ? esc(C.note) + " · " : "") + "같은 손님 · 같은 난수로 정보만 바꾼 비교입니다.") + `<p class="as-lim">묶음 평균이며 한 손님의 원인을 단정하지 않습니다.</p>`;
  },
  e_wait() {
    const W = typeof WAITINV !== "undefined" ? WAITINV : null;
    if (!W) return `<p class="as-one">대기 회피 역추정 결과 파일을 아직 읽지 못했습니다. 행동 역추적에서 '대기 후 선택한 행동' 을 열면 읽습니다.</p>` + asLinks(asLink("행동 역추적", "lab"));
    const M = W.cases.filter(c => c.kind === "model"), I = M.filter(c => c.informative);
    const by = k => W.cases.filter(c => c.kind === k).length;
    const pc = v => `${Math.round(v * 100)}%`;
    return `<p class="as-one">제한된 사례에서 '줄 앞에서 대기 회피가 선택을 바꾼다' 는 조건부 가설의 추가 설명력은 ${W.verdict.includes("보임") ? "탐색에서 보였습니다" : "확인되지 않았습니다"}(탐색 결과 · 개인의 실제 성향을 알아낸 것이 아님). 후기 대기 행동 ${W.cases.length}건 중 지금 모델이 '줄을 설까, 다른 걸 할까' 로 표현하는 것은 ${M.length}건이고, 그중 값을 가릴 수 있는 사례는 ${I.length}건입니다.</p>` +
      asSec("핵심 수치", I.map(c => `${esc(c.blog)} · ${esc(c.obs)}: 값 0 → 1 이면 ${c.effect >= 0 ? "+" : "−"}${Math.round(Math.abs(c.effect) * 100)}%p (${c.effect_clear ? "흔들림보다 큼" : "흔들림 안"})`).join(" · ") +
        `. 하나씩 빼기: ${W.loo.map(x => `${esc(x.blog)} 은 다른 사례로 고른 값 ${x.v_others.toFixed(1)}에서 ${pc(x.p_others)} (지금 기본 ${pc(x.p_current)})`).join(" · ")}.`) +
      asSec("왜", `나머지는 모델 밖입니다 · 업장 안의 음식 줄 ${by("inside")}건, 시각 · 예약으로 미리 피함 ${by("plan")}건, 포함 식사 규칙 ${by("rule")}건. 후기의 대기 행동 대부분은 다른 곳으로 옮기기보다 같은 업장을 지키고 시각 · 형태를 바꿨습니다. 지금 v4.1 규칙에서는 객실에서 출발한 손님의 줄이 대기 벌점으로 세지지 않아, 대기 회피 값이 움직이는 것은 포장 가점뿐입니다.`) +
      asSec("확인할 것", "줄 앞에서의 선택(대기 · 포장 · 이탈)이 적힌 현장 기록이나 새 후기가 있어야 가설을 다시 볼 수 있습니다. 그 전에 모델에서는 객실에서 출발한 손님의 식당 앞 줄을 대기로 셀지부터 정해야 합니다.") +
      `<p class="as-lim">${esc(W.caveat)}</p>` + asLinks(asLink("행동 역추적 · 대기 후 선택", "lab"));
  },
  e_sens() {
    const F = typeof FACTOR !== "undefined" ? FACTOR : null, S = F && F.sensitivity;
    if (!S) return `<p class="as-one">민감도 기록을 읽지 못했습니다.</p>`;
    return `<p class="as-one">조식 회차별 혼잡은 손님 기상 시각 분포 가정에 가장 민감합니다.</p>` +
      `<ol class="as-ol">${S.rows.map(r => `<li><b>${esc(r.name)}</b> (지금 ${esc(r.base)}) · ${esc(r.metric)} ${r.base_v} → ${r.alt.map((a, i) => `${esc(a)} ${r.alt_v[i]}`).join(" · ")}</li>`).join("")}</ol>` +
      asSec("확인할 것", "더뷔페 조식 회차별 입장 인원 · 대기 기록이 있으면 기상 시각 가정을 바로 가릴 수 있습니다. 줄 서기 상한은 예약 대기가 켜진 지금 규칙에서는 결과를 움직이지 않습니다.") +
      `<p class="as-lim">${esc(S.note)} (${esc(S.date)} · 시드 ${S.seeds}).</p>` + asLinks(asLink("⑦ 약한 고리", "evsec:7"));
  },
  e_chain() {
    const CH = LIB.chain || [], cnt = {};
    CH.forEach(c => { const k = gradeOf(c["확실성"]) || "기타"; cnt[k] = (cnt[k] || 0) + 1; });
    return `<p class="as-one">손님 근거(후기 · SNS · 현장) → 행동 근거 → 모델 결과 → 교차 근거 → 예측 문장을 한 줄로 이은 기록이 ${CH.length}개 있습니다.</p>` +
      asSec("핵심 수치", `확실성 ${Object.entries(cnt).map(([k, v]) => `${k} ${v}개`).join(" · ")}`) +
      asSec("확인할 것", "각 기록에 반대 사례 · 한계와 다음 확인이 같이 적혀 있습니다.") + asLinks(asLink("⑥ 근거 사슬", "evsec:6"), asLink("③ 입력 출처", "evsec:3"));
  },
});
