// 행동근거 — CL-1025-37 P3 재설계. 두 질문을 나눠 답한다.
//   A. 고객별 판단 근거: 이 고객의 후기 · 같은 작성자의 다른 글에서 무엇을 봤고(① 근거 글) → 어떤 성향으로 읽었고(② 해석) → 이번 결정에 어떤 항이 얼마나 더해졌고(③ 계산)
//      → 무엇이 실측 · 추론 · 미사용 · 연구 중인지(④) → 그래서 무엇을 골랐나(⑤). 결정 기록은 저장된 엔진 실행(flow_fixture_v1 · 고객흐름과 같은 기록)만 쓴다 — 다시 계산하지 않음.
//   B. 엔진이 행동을 재현하는 방법: 6단계 처리 흐름 · 단계별 실제 필드와 상태(현재 사용 중 / 설계 중 / 연구 중).
//   화면 표시는 표시 카드 번호(dno) · 내부 호출은 기존 ID. 원문 링크는 서버가 준 검증 URL 만(libUrl · libStartUrl).
const BH = { pid: "blog41", e: 1, turn: "event", tab: "case", step: 0, type: null, q: "", open: false, flow: null, data: {} };
const BH_TURN = { breakfast: "아침", lunch: "점심", event: "행사 시간", dinner: "저녁" };

function bhKey(pid, e) { return JSON.stringify({ event: !!e, intervention: "none", mode: "one", observe: "day", personas: [pid], product_levers: {}, seed: 0, visit_override: null }); }
async function bhRun_(pid, e) {   // 저장된 실행(고객흐름과 같은 저장본) — 없으면 같은 요청으로 서버(저장 재생 켬이면 저장본에서)
  const k = pid + "|" + e; if (BH.data[k]) return BH.data[k];
  let r = null;
  if (typeof DS !== "undefined") { try { await DS.ready; } catch (x) {} if (DS.on && DS.step && DS.fx && DS.fx.entries) r = DS.fx.entries[bhKey(pid, e)] || null; }   // 10/26 — 저장본은 시연 단계에서만 · 그 밖은 실제 엔진 계산
  if (!r) r = await api("/api/flow", JSON.parse(bhKey(pid, e)));
  BH.data[k] = JSON.parse(JSON.stringify(r)); return BH.data[k];
}
// 고객흐름에서 연 결정을 그대로 가져온다(고객 · 행사 · 턴) — 같은 저장 기록을 찾는다
function bhFromFlow(pid, ti) {
  const R = (typeof AG !== "undefined" && AG.runs[ti]) || null; if (!R) return false;
  BH.pid = pid; BH.e = AG.cond && AG.cond.event ? 1 : 0; BH.turn = R.turn; BH.tab = "case"; BH.flow = { pid, turn: R.turn, e: BH.e, many: !!(AG.res && typeof agIsMany === "function" && agIsMany(AG.res)) };
  BH.data[pid + "|" + BH.e] = JSON.parse(JSON.stringify({ runs: AG.runs, plans: AG.plans || {}, engine: AG.flow && AG.flow.engine, _live: !(typeof DS !== "undefined" && DS.on && DS.last && DS.last.hit) }));   // 지도에서 실제로 본 결정 기록(여러 명 · 실시간 계산 포함) 그대로
  setMode("evidence"); return true;
}

async function renderBehavior() {
  const el = $("#evidenceView");
  if (typeof libLoad === "function") { try { await libLoad(); } catch (e) {} }
  if (typeof AG !== "undefined" && !AG.meta) { try { AG.meta = await api("/api/turn/meta"); } catch (e) {} }
  const ids = ((AG.meta || {}).personas || []).map(p => p.id);
  if (!ids.includes(BH.pid)) BH.pid = ids[0];
  el.innerHTML = `<div class="bv"><div class="bv-head"><div><h2>행동근거</h2><p>후기에서 무엇을 확인했고, 그것이 이번 행동 계산에 어떻게 쓰였는지 따라갑니다</p></div>
    <div class="bv-tabs" role="tablist"><button type="button" role="tab" class="${BH.tab === "case" ? "on" : ""}" data-tab="case">고객별 판단 근거</button><button type="button" role="tab" class="${BH.tab === "engine" ? "on" : ""}" data-tab="engine">엔진 재현 방법</button></div></div>
    <div id="bvBody"><div class="hint">불러오는 중…</div></div></div>`;
  $$("#evidenceView .bv-tabs button").forEach(b => b.onclick = () => { BH.tab = b.dataset.tab; renderBehavior(); });
  if (BH.tab === "engine") return bvEngine(ids);
  return bvCase(ids);
}

// ---------------------------------------------------------------- A. 고객별 판단 근거
function bvTypeOf(id) { const p = typeof libP === "function" && LIBV.data ? libP(id) : null; return p && typeof libTypeOf === "function" ? (libTypeOf(p) || "유형 확인 중") : "유형 확인 중"; }
function bvPicker(ids, runs) {
  const types = [...new Set(ids.map(bvTypeOf))];
  const list = ids.filter(id => (!BH.type || bvTypeOf(id) === BH.type) && (!BH.q || [dno(id), id, bvTypeOf(id)].join(" ").toLowerCase().includes(BH.q.toLowerCase())));
  const turns = runs.map(R => R.turn);
  return `<div class="bv-pick">
    <label class="bv-f"><span>유형</span><select id="bvType"><option value="">전체 유형</option>${types.map(t => `<option${t === BH.type ? " selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
    <div class="bv-f bv-who"><span>고객</span><button type="button" id="bvWho" aria-expanded="${BH.open}">${typeof agAvatarIcon === "function" ? agAvatarIcon(BH.pid, (dnoParty(BH.pid).n || 1), 22) : ""}<b>${esc(dno(BH.pid))}</b><em>${esc(bvTypeOf(BH.pid))}</em><i>▾</i></button>
      ${BH.open ? `<div class="bv-pop"><input type="search" id="bvQ" placeholder="번호 · 유형 검색" value="${esc(BH.q)}" aria-label="고객 검색"><ul>${list.map(id => `<li><button type="button" data-p="${esc(id)}" class="${id === BH.pid ? "on" : ""}"><b>${esc(dno(id))}</b><span>${esc(bvTypeOf(id))}</span></button></li>`).join("") || `<li class="bv-none">맞는 고객 없음</li>`}</ul><div class="bv-popn">결정 기록이 있는 실행 검증 고객 ${ids.length}명 · 시각 초안 카드는 행동 실행 전이라 목록에 없음</div></div>` : ""}</div>
    <label class="bv-f"><span>하루 조건</span><select id="bvE"><option value="1"${BH.e ? " selected" : ""}>와인페어 있음</option><option value="0"${BH.e ? "" : " selected"}>와인페어 없음</option></select></label>
    <label class="bv-f"><span>결정</span><select id="bvTurn">${runs.filter(R => R.customers.some(x => x.persona_id === BH.pid)).map(R => { const c = R.customers.find(x => x.persona_id === BH.pid); return `<option value="${R.turn}"${R.turn === BH.turn ? " selected" : ""}>${esc(BH_TURN[R.turn] || R.turn)} ${esc(R.time || "")} · ${esc(agShort(c.choice.product_label))}</option>`; }).join("")}</select></label>
    <button type="button" class="cf-btn" id="bvBack">이 고객의 하루 보기 ›</button></div>`;
}
async function bvCase(ids) {
  const pid = BH.pid, e = BH.e; let F;
  try { F = await bhRun_(pid, e); } catch (x) { $("#bvBody").innerHTML = `<div class="callout">결정 기록을 불러오지 못했습니다 — ${esc(x.message)}</div>`; return; }
  if (pid !== BH.pid || e !== BH.e) return;   // 고르는 사이 바뀌었으면 버림(근거 섞임 방지)
  const runs = F.runs.filter(R => R.customers.some(x => x.persona_id === pid)); if (!runs.length) { $("#bvBody").innerHTML = `<div class="callout">이 고객의 결정 기록이 없습니다.</div>`; return; } if (!runs.some(R => R.turn === BH.turn)) BH.turn = (runs.find(R => R.turn === "event") || runs[runs.length - 1]).turn;
  const R = runs.find(R => R.turn === BH.turn), c = R.customers.find(x => x.persona_id === pid) || R.customers[0];
  $("#bvBody").innerHTML = bvPicker(ids, runs) + bvCaseBody(pid, R, c, F);
  bvWire(ids);
}
function bvWire(ids) {
  const W = $("#bvWho"); if (W) W.onclick = () => { BH.open = !BH.open; bvCase(ids).then(() => { const q = $("#bvQ"); if (q) q.focus(); }); };
  const q = $("#bvQ"); if (q) q.oninput = () => { const pos = q.selectionStart; BH.q = q.value; bvCase(ids).then(() => { const n = $("#bvQ"); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (x) {} } }); };
  $$("#bvBody .bv-pop [data-p]").forEach(b => b.onclick = () => { BH.pid = b.dataset.p; BH.open = false; BH.q = ""; BH.flow = null; bvCase(ids); });
  const t = $("#bvType"); if (t) t.onchange = () => { BH.type = t.value || null; if (BH.type && bvTypeOf(BH.pid) !== BH.type) { const f = ids.find(id => bvTypeOf(id) === BH.type); if (f) BH.pid = f; } BH.open = false; bvCase(ids); };
  const ee = $("#bvE"); if (ee) ee.onchange = () => { BH.e = +ee.value; bvCase(ids); };
  const tt = $("#bvTurn"); if (tt) tt.onchange = () => { BH.turn = tt.value; bvCase(ids); };
  const bk = $("#bvBack"); if (bk) bk.onclick = () => { if (typeof libSim === "function") { AG.cond.event = !!BH.e; AG.cond.product_levers = {}; AG.mode = "agent"; libSim(BH.pid); } };
  const pf = $("#bvProf"); if (pf) pf.onclick = () => typeof libOpen === "function" && libOpen(BH.pid);
  $$("#bvBody [data-ff]").forEach(b => b.onclick = () => typeof libOpen === "function" && libOpen(BH.pid, b.dataset.ff.split(",").filter(Boolean)));
}
const bvJosa = w => { const ch = String(w || "").replace(/[^가-힣]+$/, "").slice(-1), c = ch.charCodeAt(0); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? "을" : "를"; };   // 받침 있으면 '을'
const bvN = v => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2);
function bvCaseBody(pid, R, c, FL) {
  const P = (LIBV.data ? libP(pid) : null) || {}, Fx = (P.engine && P.engine.facts) || {};
  const T = c.reason_totals || {}, ch = c.choice, o = c.best_other_venue, ru = c.runner_up;
  const reasons = [...c.reasons], revR = reasons.filter(r => (r.parts.review || 0) > 0.005).sort((a, b) => b.parts.review - a.parts.review);
  const used = [...new Set(revR.flatMap(r => r.fact_ids || []))];
  const fOk = f => Fx[f] && !Fx[f].hidden && Fx[f].gist && !(typeof LIB_SENS !== "undefined" && LIB_SENS.test(Fx[f].gist));
  const llm = /llm/i.test(String(c.decision_engine || "") + String(R.engine || ""));
  const vName = R.turn === "event" && ch.venue_id === "FOREST" ? "와인페어" : agShort(ch.product_label);
  // 스냅샷
  const close = o && o.margin < 0.15;
  const snap = `<section class="bv-snap"><div class="bv-sn-l"><div class="bv-kick">${esc(dno(pid))} · ${esc(BH_TURN[R.turn] || R.turn)} ${esc(R.time || "")} · ${esc(ch.venue_label)}</div>
      <h3>${esc(vName)}${bvJosa(vName)} 고른 이유</h3>
      <div class="bv-chips"><span class="bv-chip">${BH.e ? "와인페어가 열린 날" : "행사 없는 날"}</span><span class="bv-chip ${T.review > 0.05 ? "rv" : ""}">${T.review > 0.05 ? `후기 근거 ${bvN(T.review)}` : "공통 규칙에 따른 결정"}</span></div></div>
    <div class="bv-sn-r"><table class="bv-cmp"><tr class="on"><th>선택</th><td>${esc(agShort(ch.product_label))}</td><td class="n">${ch.score.toFixed(2)}</td></tr>${ru ? `<tr><th>다음 대안</th><td>${esc(agShort(ru.product_label))}</td><td class="n">${ru.score.toFixed(2)}</td></tr>` : ""}</table>
      <div class="bv-gap">${o ? `<div>다른 업장 최고 대안과 점수 차 <b>${o.margin.toFixed(2)}</b>${close ? " · 근소" : ""}</div>` : ""}<span>점수는 효용 차이 · 확률 아님</span></div></div></section>`;
  // ① 근거 글 — 이번 결정에 쓰인 사실이 나온 글(같은 작성자) → 나머지는 관찰된 배경
  const posts = {}; used.forEach(f => { const pp = Fx[f] && Fx[f].post; const k = pp || "_none"; (posts[k] = posts[k] || []).push(f); });
  const evByPost = {}; [...(P.wh_events || []), ...(P.other_events || [])].forEach(ev => (ev.posts || []).forEach(pp => { (evByPost[pp] = evByPost[pp] || []).push(ev); }));
  const startU = typeof libStartUrl === "function" ? libStartUrl(P) : null;
  const postRows = Object.entries(posts).filter(([k]) => k !== "_none").map(([pp, fs]) => { const u = typeof libUrl === "function" ? libUrl(pp) : null, ev = (evByPost[pp] || [])[0], wh = fs.some(f => Fx[f].wh);
    return `<tr><td><span class="bv-src ${wh ? "wh" : ""}">${wh ? "워커힐 후기" : "같은 작성자 · 다른 글"}</span></td><td>${esc(libShort ? libShort((ev && ev.detail) || Fx[fs[0]].gist, 70) : (ev && ev.detail) || "")}</td><td class="n">${fs.filter(fOk).length}</td><td>${u ? libA(u, "원문 보기 ↗", "sm") : `<em class="bv-mute">원문 연결 확인 중</em>`}</td></tr>`; });
  const loose = (posts._none || []).filter(fOk);
  const s1 = `<section class="bv-sec"><div class="bv-sh"><i>1</i><h4>근거 글</h4><span>이번 결정에 쓰인 후기 사실 ${used.length}개가 나온 글 · 같은 작성자 기준</span></div>
    <div class="bv-src-top">${startU ? libA(startU, "대표 후기 원문 보기 ↗", "lb-srcbtn") : `<span class="lb-srcbtn off">원문 연결 확인 중</span>`}<span class="bv-mute">원문은 외부 블로그 · 아래 문장은 후기에서 추출 · 검수한 요약(원문 인용 아님)</span></div>
    ${postRows.length ? `<table class="bv-tbl"><thead><tr><th>글</th><th>확인된 행동 요지</th><th class="n">쓰인 사실</th><th>원문</th></tr></thead><tbody>${postRows.slice(0, 5).join("")}</tbody></table>${postRows.length > 5 ? `<details class="bv-more bv-pmore"><summary>근거 글 ${postRows.length - 5}편 더 보기 <span>모두 ${postRows.length}편 · 같은 작성자</span></summary><table class="bv-tbl"><tbody>${postRows.slice(5).join("")}</tbody></table></details>` : ""}` : ""}
    ${loose.length ? `<div class="bv-facts"><div class="bv-lab">${postRows.length ? "글 연결이 없는 사실" : "대표 후기에서 추출한 사실(글별 연결은 이 고객 자료에 없음)"}</div><ul>${loose.slice(0, 2).map(f => `<li><code>${esc(f)}</code>${esc(Fx[f].gist)}</li>`).join("")}</ul>${loose.length > 2 ? `<details class="bv-more"><summary>사실 ${loose.length - 2}개 더 보기</summary><ul>${loose.slice(2).map(f => `<li><code>${esc(f)}</code>${esc(Fx[f].gist)}</li>`).join("")}</ul></details>` : ""}</div>` : ""}
    ${!used.length ? `<p class="bv-empty">이 결정에는 후기 사실이 점수에 연결되지 않았습니다 — 공통 규칙에 따른 결정입니다.</p>` : ""}</section>`;
  // ② 성향 해석 — 관측 사실 | 프로파일 해석 | 반례 · 한계 | 이번 기여
  const bars = (c.persona && c.persona.bars) || [];
  const traits = P.traits || [];
  const rowT = r => { const b = bars.find(x => x.key === r.facet), fs = (r.fact_ids || []).filter(fOk), tr = traits.find(t => (t.support || []).length && (r.factor || "").split(/[ ·(]/).some(w => w.length > 1 && (t.trait || "").includes(w)));
    return `<tr><td><b>${escP(r.factor)}</b>${r.note ? `<div class="bv-mute">${esc(r.note)}</div>` : ""}</td><td>${fs.length ? `${esc(libShort(Fx[fs[0]].gist, 46))}${fs.length > 1 ? ` <span class="bv-mute">외 ${fs.length - 1}건</span>` : ""}` : `<span class="bv-mute">사실 문장 비공개 · 연결 없음</span>`}</td>
      <td>${b ? `<div class="bv-bar"><i style="width:${Math.round(b.level * 100)}%"></i></div><span class="bv-mute">${esc(b.label)} · 근거 ${b.evidence_count}건</span>` : `<span class="bv-mute">성향 막대 밖 — 후기 사실이 이 항에 직접 연결</span>`}</td>
      <td>${tr && (tr.counter || [])[0] ? esc(libShort(tr.counter[0], 40)) : `<span class="bv-mute">${traits.length ? "반례 기록 없음" : "반례 분석 전"}</span>`}</td><td class="n rv">${bvN(r.parts.review)}</td></tr>`; };
  const s2 = `<section class="bv-sec"><div class="bv-sh"><i>2</i><h4>어떻게 성향으로 읽었나</h4><span>관측 사실과 프로파일 해석을 나눠 봅니다</span></div>
    ${revR.length ? `<table class="bv-tbl bv-mx"><thead><tr><th>성향 · 제약 항목</th><th>관측 사실(후기 요약)</th><th>프로파일 해석(엔진 입력)</th><th>반례 · 한계</th><th class="n">이번 기여</th></tr></thead><tbody>${revR.map(rowT).join("")}</tbody></table>` : `<p class="bv-empty">이번 결정에 후기 성향이 더해진 항이 없습니다.</p>`}</section>`;
  // ③ 계산 기여 — 항별 분해 막대 + 후보 비교
  const rs = reasons.slice().sort((a, b) => Math.abs(b.value) - Math.abs(a.value)), mx = Math.max(0.01, ...rs.map(r => Math.abs(r.value)));
  const seg = r => ["common", "review", "assumption"].filter(k => Math.abs(r.parts[k] || 0) > 1e-6).map(k => `<i class="s-${k}${r.parts[k] < 0 ? " neg" : ""}" style="width:${(Math.abs(r.parts[k]) / mx * 100).toFixed(1)}%" title="${({ common: "공통 규칙", review: "후기 근거", assumption: "설계값" })[k]} ${r.parts[k].toFixed(2)}"></i>`).join("");
  const cands = [ch, ...(c.not_chosen || [])].filter(x => x && x.score != null).slice(0, 5);
  const s3 = `<section class="bv-sec"><div class="bv-sh"><i>3</i><h4>계산에 실제로 더해진 값</h4><span>엔진 기록(reasons · reason_totals) 그대로 · 원문 인용만으로는 점수에 넣지 않음</span></div>
    <div class="bv-tot"><div><b class="rv">${bvN(T.review || 0)}</b><span>후기 근거(개인)</span></div><div><b>${bvN(T.common || 0)}</b><span>공통 규칙(가격 · 끼니 · 이동 · 다음 일정)</span></div>${(T.assumption || 0) > 0.005 ? `<div><b class="as">${bvN(T.assumption)}</b><span>설계값</span></div>` : ""}<div><b>${ch.score.toFixed(2)}</b><span>선택 점수</span></div></div>
    <div class="bv-calc">${rs.map(r => `<div class="bv-cr"><span class="bv-cf">${escP(r.factor)}${r.facet ? `<code>${esc(r.facet)}</code>` : ""}</span><span class="bv-cb">${seg(r)}</span><b class="n">${bvN(r.value)}</b></div>`).join("")}</div>
    <div class="ag-skey"><span><i class="s-review"></i>후기 근거</span><span><i class="s-common"></i>공통 규칙</span><span><i class="s-assumption"></i>설계값</span></div>
    <details class="bv-more"><summary>후보 비교 · 결정 엔진</summary><table class="bv-tbl"><thead><tr><th>후보</th><th>업장</th><th class="n">점수</th></tr></thead><tbody>${cands.map((x, i) => `<tr class="${i === 0 ? "on" : ""}"><td>${esc(agShort(x.product_label))}</td><td>${esc(x.venue_label)}</td><td class="n">${x.score.toFixed(2)}</td></tr>`).join("")}</tbody></table>
      <p class="bv-mute">결정 엔진: ${esc(c.decision_engine || "-")} · 하루 엔진: ${esc(R.engine || FL.engine || "-")}</p></details></section>`;
  // ④ 근거 상태 — 실측 · 정성 추론 · 미사용 · 연구 중
  const notUsed = bars.filter(b => b.status === "observed" && !revR.some(r => r.facet === b.key)).map(b => b.label);
  const sc = ((FL.plans || {})[pid] || {}).scenes || [], nGen = sc.filter(s => s.layer === "generated").length, nRev = sc.filter(s => s.layer === "review").length, nEng = sc.filter(s => s.layer === "engine").length;
  const s4 = `<section class="bv-sec"><div class="bv-sh"><i>4</i><h4>부족한 근거는 어떻게 채웠나</h4><span>실측 · 추론 · 미사용 · 연구 중을 나눕니다</span></div>
    <div class="bv-4"><div class="k ok"><b>실측 사실</b><p>이번 점수에 연결된 후기 사실 <strong>${used.length}개</strong></p></div>
      <div class="k inf"><b>정성 추론</b><p>${traits.length ? `반복 취향 ${traits.length}개 · 조건부 규칙 ${(P.rules || []).length}개(분석 해석 — 이번 점수에 직접 쓰이지 않음)` : "반복 취향 분석 전 — 엔진 성향 수준만 사용"}</p></div>
      <div class="k no"><b>사용되지 않음</b><p>${notUsed.length ? `측정됐지만 이번 결정에 쓰이지 않은 성향: ${notUsed.map(esc).join(" · ")}` : "측정된 성향은 모두 이번 결정에 관여"}</p></div>
      <div class="k rs"><b>연구 중</b><p>${llm ? "LLM 보완 실행됨" : "이번 결과는 LLM 추론을 사용하지 않았습니다"} · 후기에 없는 하루 장면은 규칙 기반 계획기가 채움(이 하루: 엔진 결정 ${nEng} · 후기 장면 ${nRev} · 생성 장면 ${nGen} [시뮬레이션 가정])</p></div></div></section>`;
  // ⑤ 그래서 이번 행동
  const bg = [...(P.wh_events || [])].filter(ev => !(ev.facts || []).some(f => used.includes(f)) && !(typeof LIB_SENS !== "undefined" && LIB_SENS.test(ev.detail || ""))).slice(0, 3);
  const s5 = `<section class="bv-sec bv-fin"><div class="bv-sh"><i>5</i><h4>그래서 이번 행동</h4></div>
    <p class="bv-con"><b>${esc(agShort(ch.product_label))}</b> — ${esc((c.why || "").replace(/\s+/g, " "))}</p>
    ${revR.length ? `<div class="bv-why"><span class="bv-lab">이번 선택의 이유(실제 기여)</span>${revR.slice(0, 3).map(r => `<span class="bv-chip rv">${escP(r.factor)} ${bvN(r.parts.review)}</span>`).join("")}</div>` : `<div class="bv-why"><span class="bv-lab">이번 선택의 이유</span><span class="bv-chip">공통 규칙에 따른 결정 · 실제 개인화 점수 기여 0</span></div>`}
    ${bg.length ? `<div class="bv-bg"><span class="bv-lab">관찰된 배경(결정 기여 미확인)</span><ul>${bg.map(ev => `<li>${esc(libShort(ev.detail, 70))}</li>`).join("")}</ul></div>` : ""}
    <div class="bv-act"><button type="button" class="cf-btn" id="bvProf">고객 프로필 보기</button>${used.length ? `<button type="button" class="cf-btn" data-ff="${esc(used.join(","))}">프로필에서 이 사실들 보기</button>` : ""}</div></section>`;
  return `<div class="bv-case">${snap}${s1}${s2}${s3}${s4}${s5}</div>`;
}

// ---------------------------------------------------------------- B. 엔진 재현 방법
const BV_STEPS = [
  { t: "후기 · 연관 글 확보", st: "현재 사용 중", s: "ok", what: "같은 작성자의 워커힐 후기를 먼저, 이어서 연관 호텔 · 다이닝 · 여행 글을 모읍니다. 광고성 글과 같은 체류를 여러 번 쓴 글은 따로 표시합니다.", fields: "audit.walkerhill · audit.unique_posts · wh_events[].posts", plan: "계획: 최근 최대 50개 글까지(고객마다 확보량이 다름 — 실제 확보량은 고객별 판단 근거의 근거 글 표)" },
  { t: "사실 · 행동 · 시점 추출", st: "현재 사용 중", s: "ok", what: "글에서 실제 한 일(이용 · 주문 · 참여 · 구매)과 시점을 사실 ID 단위로 뽑고, 같은 방문인지 연결 상태(확인 · 추정 · 미확인)를 붙입니다.", fields: "engine.facts{id: gist · post · wh} · wh_events[].stage · link", plan: "사실은 요약 문장이며 원문 인용이 아님 · 아동 · 건강 문장은 화면에서 제외" },
  { t: "다층 프로파일", st: "현재 사용 중", s: "ok", what: "여러 경험에서 반복된 선호 · 제약을 성향 수준(0~1)과 근거 건수로 정리하고, 반례와 확인 안 된 성향은 따로 둡니다.", fields: "persona.bars[key · level · evidence_count · status] · traits[support · counter]", plan: "신뢰도 · 근거 강도 · 효용 가중치를 한 숫자로 합치지 않음 — 계수화 v0 개선은 설계 중" },
  { t: "월드 · 행사 조건 · 후보", st: "현재 사용 중", s: "ok", what: "날짜 · 시각 · 투숙 여부 · 행사 운영 · 가격 · 이용 자격으로 그때 고를 수 있는 후보만 남깁니다. 자격이 안 되면 점수 비교에서 빠집니다.", fields: "runs[].conditions · not_chosen[].feasible · blocked · price", plan: "와인페어는 2026 가을 운영 기간(10/25 종료) 기준 저장 시나리오" },
  { t: "행동 계산 · 보완", st: "규칙 사용 중 · LLM 연구 중", s: "mix", what: "후보마다 공통 규칙(가격 · 끼니 · 이동 · 다음 일정)과 후기 근거(성향 × 상황) 몫을 더해 가장 높은 후보를 고릅니다. 후기에 없는 장면은 규칙 기반 계획기가 채웁니다. LLM 보완은 근거 제한 · 후보 제약 · 출력 검증을 거치는 연구 단계이며, 저장된 시연 결과에는 쓰이지 않았습니다.", fields: "reasons[factor · facet · parts{common · review · assumption} · fact_ids] · reason_totals · decision_engine", plan: "llm_backend: rules(LLM 호출 0) — 저장된 시연 결과는 규칙 계산이며 LLM 혼합 결과가 아님" },
  { t: "결정 기록 · 검증", st: "현재 사용 중(재현성) · 개인화 유효성 별도", s: "mix", what: "선택 · 비선택 대안 · 항별 기여 · 사실 ID 를 결정 기록으로 남겨 되짚습니다. 같은 입력이면 같은 결과인지(재현성)와, 후기 성향이 실제로 선택을 바꾸는지(개인화 유효성)는 따로 검증합니다.", fields: "runner_up · best_other_venue · score_basis · 저장본 entry_sha", plan: "" },
];
async function bvEngine(ids) {
  let ex = null; try { const F = await bhRun_(BH.pid, BH.e); const R = F.runs.find(r => r.turn === BH.turn) || F.runs[0]; ex = { R, c: R.customers[0], F }; } catch (e) {}
  const P = (LIBV.data ? libP(BH.pid) : null) || {}, A = P.audit || {}, E = P.engine || {};
  const i = BH.step, S = BV_STEPS[i];
  const exTxt = !ex ? "" : [
    `${dno(BH.pid)}: 워커힐 글 ${A.walkerhill ?? "-"} · 분석한 글 ${A.unique_posts ?? (P.wh_events ? "-" : "대표 후기 1편")}`,
    `${dno(BH.pid)}: 엔진이 쓰는 후기 사실 ${Object.keys(E.facts || {}).length}개 · 행동 묶음 ${(P.wh_events || []).length + (P.other_events || []).length}개`,
    `${dno(BH.pid)}: 측정된 성향 ${(ex.c.persona.bars || []).filter(b => b.status === "observed").length}개 · 확인 안 된 성향 ${(ex.c.persona.bars || []).filter(b => b.status !== "observed").length}개`,
    `${dno(BH.pid)} ${BH_TURN[ex.R.turn]} ${ex.R.time}: 후보 ${1 + (ex.c.not_chosen || []).length}개 중 점수 비교 ${[ex.c.choice, ...(ex.c.not_chosen || [])].filter(x => x.score != null).length}개`,
    `${dno(BH.pid)} ${BH_TURN[ex.R.turn]}: 후기 근거 ${bvN(ex.c.reason_totals.review || 0)} · 공통 규칙 ${bvN(ex.c.reason_totals.common || 0)} · LLM 호출 없음`,
    `${dno(BH.pid)}: 다음 대안 ${agShort((ex.c.runner_up || {}).product_label || "-")} · 저장본 기록 그대로 재생`][i];
  $("#bvBody").innerHTML = `<div class="bv-eng">
    <ol class="bv-flow">${BV_STEPS.map((x, k) => `<li class="${k === i ? "on" : ""} ${x.s}"><button type="button" data-st="${k}"><i>${k + 1}</i><b>${esc(x.t)}</b><em>${esc(x.st)}</em></button></li>`).join("")}</ol>
    <section class="bv-stp"><div class="bv-stp-h"><span class="bv-stn">${i + 1} / 6</span><h3>${esc(S.t)}</h3><span class="bv-stt ${S.s}">${esc(S.st)}</span></div>
      <p class="bv-stw">${esc(S.what)}</p>
      <dl class="bv-kv">${exTxt ? `<div><dt>지금 고른 고객에서</dt><dd>${esc(exTxt)}</dd></div>` : ""}${S.plan ? `<div><dt>범위</dt><dd>${esc(S.plan.replace(/llm_backend: rules\(LLM 호출 0\) — /, ""))}</dd></div>` : ""}</dl>
      <details class="bv-more"><summary>기술 상세 · 실제 사용된 데이터 항목</summary><p class="bv-mute"><code>${esc(S.fields)}</code></p></details></section>
    <section class="bv-sec"><div class="bv-sh"><h4>재현성과 개인화 유효성은 다른 검증입니다</h4></div>
      <table class="bv-tbl"><thead><tr><th>질문</th><th>방법</th><th>현재 상태</th></tr></thead><tbody>
        <tr><td>같은 입력이면 같은 결정인가(재현성)</td><td>기존 11명 × 결정 264개를 다시 계산해 기록과 대조 · 저장본 26개 바이트 대조</td><td><b class="ok">통과</b> 264/264 · 26/26</td></tr>
        <tr><td>후기 성향이 실제로 선택을 바꾸는가(개인화 유효성)</td><td>후기 근거를 뺀 대조군(no-sidecar)과 비교 · 결정 시점에 허용된 정보만 사용 · 정답지 누출 방지</td><td><b class="rs">별도 게이트 · 검증 중</b></td></tr>
        <tr><td>후기에 없는 행동을 LLM 으로 보완하면 나아지는가</td><td>근거 제한 · 후보 제약 · 출력 검증 뒤 규칙 결과와 비교</td><td><b class="rs">연구 중</b> · 시연 결과에는 쓰지 않음</td></tr></tbody></table></section></div>`;
  $$("#bvBody .bv-flow [data-st]").forEach(b => b.onclick = () => { BH.step = +b.dataset.st; bvEngine(ids); });
}
