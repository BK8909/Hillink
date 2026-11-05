// Read-only views of one live shared-world execution and its original L5 rows.
function sharedWorldSummary(flow) {
  const w=flow && flow.shared_world;
  if (!w || w.mode!=="SHARED_WORLD_CHRONOLOGICAL") return "";
  const decisions=w.days.reduce((n,d)=>n+d.decision_order.length,0);
  return `<details class="ag-world-summary" data-shared-world="live"><summary>공동 시간축 실행 · ${w.customer_ids.length}팀 · ${w.days.length}일 · 실제 결정 ${decisions}회</summary><p>같은 날짜·시각의 운영 조건을 적용하며, 고객별 성향·식사·행사 이력은 분리합니다. 시설 정원·좌석·대기 경쟁·고객 상호작용은 계산하지 않습니다.</p><p>방문 ID ${esc(flow.visit_id.slice(0,12))}</p>${w.days.map(d=>`<p>${esc(d.date)} · 공동 월드 ${esc(d.world_id.slice(0,8))} · 고객 ${d.completed_customer_ids.length}팀 완료 · 결정 ${d.decision_order.length}회</p>`).join("")}</details>`;
}
function sharedOperationsHTML(L) {
  const o=L && L.operations;
  if (!o || o.ledger_run_id!==L.run_id) return "";
  return `<section class="rev-chart-panel" data-shared-operations><h3>공동 실행 · 일자와 시간대별 행동·가상 소비</h3><p class="rc-note">활동·거래 시작 시각 기준입니다. 시간대를 열면 원래 고객·행동·L5 행을 확인합니다. 객실박·시각 미상은 별도입니다. 정원·대기 경쟁은 미지원입니다.</p>${o.buckets.map((b,i)=>`<details data-operation-bucket="${i}"><summary>${esc(b.date)} ${b.hour==null?"객실박·시각 미상":String(b.hour).padStart(2,"0")+"시"} · ${b.team_count}팀 · 활동 ${b.action_count}건 · ${rcMoney(b.paid_krw)}${b.unknown_count?` · 금액 미확인 ${b.unknown_count}건`:""}</summary><p>별도 객실 등 가정액 ${rcMoney(b.room_and_other_assumption_krw)}</p><ul>${b.actions.map(a=>`<li><button type="button" class="cf-link" data-operation-customer="${esc(a.customer_id)}" data-operation-day="${b.day}">${esc(dno(a.customer_id))}</button> · ${String(Math.floor(a.start_minute/60)).padStart(2,"0")}:${String(a.start_minute%60).padStart(2,"0")} · ${esc(a.action_id)} · ${esc(a.venue_id)} · 선택 근거 ${a.decision_packet_ids.length}개</li>`).join("")}${b.transactions.map(t=>`<li data-operation-row="${esc(t.row_id)}">L5 ${esc(t.row_id.slice(0,8))} · ${esc(dno(t.customer_id))} · ${esc(t.product || t.product_id || t.act)} · ${t.unknown_price?"금액 미확인":rcMoney(t.paid_krw)}</li>`).join("")}</ul></details>`).join("")}</section>`;
}
function sharedOperationsWire(root) {
  root.querySelectorAll('[data-operation-customer]').forEach(b=>b.onclick=async()=>{
    await revShowCustomer(b.dataset.operationCustomer);
    if (typeof agVisitDaySelect === "function") agVisitDaySelect(+b.dataset.operationDay);
  });
}
