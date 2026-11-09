// Display only: every number is from a live /api/visit decision packet.
function agM4LiveData() {
  const data = AG.visitData, ledger = AG.flow && AG.flow.ledger;
  return data && data.engine && data.engine.behavior_engine === "m4" && data.ledger && ledger &&
    ledger.source === "live_engine" && ledger.run_id === data.ledger.run_id ? data : null;
}
function agM4ChoicePanel(pid, ti) {
  const data = agM4LiveData(), plan = data && data.plans[pid], run = AG.runs[ti] || AG.res;
  if (!plan || !plan.m4 || !run) return "";
  const customer = run.customers.find(c => c.persona_id === pid), day = data.visit_days.find(d => d.day_index === (run.visit_day || AG.visitDay));
  if (!customer || !day) return "";
  const id = customer.choice.product_id;
  const choices = plan.m4.decisions.filter(d => d.packet.context_factors.date === day.date && d.selected_action === id && d.execution_status === "EXECUTED");
  const decision = choices.sort((a,b) => Math.abs(a.packet.context_factors.time-agMin(run.time))-Math.abs(b.packet.context_factors.time-agMin(run.time)))[0];
  if (!decision) return `<section class="ch-sec m4-live-trace"><h4>M4 실제 방문 상태</h4><p>이 턴은 기존 전용 판단 경로의 선택입니다. 실행된 식사는 이후 M4 식사 상태에 전달됩니다.</p></section>`;
  return agM4DecisionPanel(pid, decision);
}
function agM4ActivityPanel(pid, scene) {
  const data = agM4LiveData(), plan = data && data.plans[pid], links = scene.basis && scene.basis.m4;
  if (!plan || !plan.m4 || !links) return "";
  const decision = plan.m4.decisions.find(d => links.decision_packet_ids.includes(d.packet.packet_sha256) && d.execution_status === "EXECUTED");
  return decision ? agM4DecisionPanel(pid, decision) : "";
}
function agM4DecisionPanel(pid, decision) {
  const id = decision.selected_action;
  const packet = decision.packet, ctx = packet.context_factors, row = packet.candidates.find(c => c.candidate_id === id);
  const number = v => v == null ? "—" : Number(v).toFixed(3);
  const rows = packet.candidates.map(c => `<tr><td>${esc(c.candidate_id)}${c.candidate_id === id ? " · 선택" : ""}</td><td>${number(c.base_score)}</td><td>${number(c.context_adjustment)}</td><td>${number(c.final_score)}</td><td>${number(c.final_with_lookahead)}</td><td>${esc(c.world_allowed ? "허용" : c.block_reason || "제약")}</td></tr>`).join("");
  let terms = (row.terms || []).filter(t => t.value).map(t => `<li>${esc(t.factor)}: ${number(t.value)}${t.fact_ids && t.fact_ids.length ? ` · 근거 ${t.fact_ids.map(esc).join(", ")}` : " · 상황/설계 항"}</li>`).join("");
  if (packet.kind === "PLANNER") terms += Object.entries(row.profile_feature_marginals || {}).filter(([k,v]) => v.weight_delta_at_fixed_state).map(([k,v]) => `<li>${esc(k)}=${number(v.value)} · 이 값 하나를 0.5로 바꾼 고정 상태 기여 ${number(v.weight_delta_at_fixed_state)} (합산 인과효과 아님)</li>`).join("");
  const sampling = decision.sampling;
  const selectionLabel = sampling ? `후보 가중치 추첨 · 해당 후보 확률 ${(100 * sampling.probabilities[id]).toFixed(2)}%` : "최대 후속 포함 점수 선택 · 확률 아님";
  const prior = ctx.event_memory && ctx.event_memory.prior_attendance || [];
  const eventText = prior.length ? `이전 실제 시뮬레이션 참석 ${prior.map(e => `${e.date} ${e.start}–${e.end}`).join(", ")}. 같은 프로그램의 세부 차이는 미확인입니다.` : "이 방문에서 완료한 이전 행사 참석 없음. 안내 확인은 참석과 구분합니다.";
  const meal = ctx.last_meal;
  return `<section class="ch-sec m4-live-trace" data-m4-packet="${esc(packet.packet_sha256)}"><h4>M4 · 선택 전에 계산한 방문 맥락</h4>
    <p>${esc(selectionLabel)}</p><p><b>${esc(id)}</b> · 자체 ${number(row.final_score)} · 후속 행동 포함 ${number(row.final_with_lookahead)}</p>
    <p>${esc(eventText)}</p><p>${meal ? `이전 식사 ${esc(meal.date)} ${esc(meal.end)} · ${esc(meal.action_id)}` : "이전 식사 실행 기록 없음"}. 식사량·포만감은 기록에서 계산한 추정이며 실제 고객의 허기 관측이 아닙니다.</p>
    <details><summary>선택하지 않은 대안 · 실제 점수 · 제약</summary><div style="overflow-x:auto"><table class="ag-rt"><tr><th>후보</th><th>기본</th><th>맥락</th><th>자체</th><th>후속 포함</th><th>조건</th></tr>${rows}</table></div></details>
    <details><summary>실제 성향·상황 기여와 Fact ID</summary><ul class="ag-plain">${terms}</ul></details>
    <p class="hint">실시간 M4 규칙 계산 · 스냅샷 재생 아님 · LLM 호출 0. Fact 연결은 관측 경험을 새 상황에 적용한 추론과 구분합니다. 후속 포함 점수는 선택 확률이 아닙니다.</p></section>`;
}
