"use strict";

// 실제 후기 결제는 가상 손님의 시뮬레이션 매출과 다른 표에서 보여 준다.
function renderObservedPayments(root) {
  const wrap = document.createElement("div");
  wrap.className = "rwrap";
  wrap.innerHTML = `<details class="card" open id="observedPaymentsCard">
    <summary><b>후기 추가 결제 · 월별 집계</b></summary>
    <p class="hint">확보한 후기의 추가 결제만 실제 결제월로 합산합니다. 호텔 전체 월 매출이나 가상 손님의 예측 매출이 아닙니다.</p>
    <form class="row"><label>결제월 <input type="month" aria-label="후기 결제월"></label>
    <button type="submit">해당 월 조회</button><button type="button" data-all>전체 월</button>
    <button type="button" data-refresh>다시 집계</button></form>
    <div aria-live="polite" data-result>집계 중…</div></details>`;
  root.prepend(wrap);
  const form = wrap.querySelector("form"), input = wrap.querySelector("input");
  const box = wrap.querySelector("[data-result]");
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
  const money = n => n == null ? "미상" : Math.round(n).toLocaleString("ko-KR") + "원";
  let selected = "all", request = 0;
  async function load(month) {
    selected = month;
    const token = ++request;
    box.textContent = "집계 중…";
    try {
      const response = await fetch("/api/observed-payments?month=" + encodeURIComponent(month));
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "집계 실패");
      if (token !== request || !box.isConnected) return;
      const s = data.summary;
      box.innerHTML = `<p><b>확인된 추가 결제 부분합 ${money(s.known_subtotal_krw)}</b> · 금액 미상 ${s.unknown_count}건 · 부문 미배부 ${s.unallocated_count}건</p>` +
        `<p class="hint">자료가 있는 결제월: ${data.available_months.map(escape).join(" · ") || "없음"}. 금액 미상은 0원이 아니며 확인된 금액만 부분합에 포함합니다.</p>`;
      if (data.no_records) {
        box.innerHTML += `<p>선택한 월에 확보한 결제 기록이 없습니다. 해당 월 매출이 0원이라는 뜻은 아닙니다.</p>`;
        return;
      }
      box.innerHTML += `<table class="t"><thead><tr><th>결제월</th><th>확인된 결제 부분합</th><th>금액 미상</th></tr></thead><tbody>` +
        data.months.map(m => `<tr><td>${escape(m.month)}</td><td>${money(m.known_subtotal_krw)}</td><td>${m.unknown_count}건</td></tr>`).join("") + `</tbody></table>` +
        `<details><summary>결제 근거와 업장별 세부 기록</summary><div style="overflow-x:auto"><table class="t"><thead><tr><th>결제일 · 후기</th><th>부문 · 업장</th><th>추가 결제/주문</th><th>결제액</th><th>순매출 환산</th><th>확인 범위</th></tr></thead><tbody>` +
        data.rows.map(r => `<tr><td>${escape(r.date)}<br>${escape(r.source)}</td><td>${escape(r.l2 || "부문 미배부")}<br>${escape(r.l3)}</td><td>${escape(r.product)}</td><td>${money(r.krw)}</td><td>${money(r.net)}</td><td>${escape(r.payment_status)}<br>${escape(r.note)}<br><small>${escape(r.basis)}</small></td></tr>`).join("") +
        `</tbody></table></div><p class="hint">${escape(data.vat_basis)}. 부분합을 전체 숙박·식사 매출로 해석하지 않습니다.</p></details>`;
    } catch (error) {
      if (token === request && box.isConnected) box.textContent = "집계하지 못했습니다: " + error.message;
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); if (input.value) load(input.value); });
  wrap.querySelector("[data-all]").onclick = () => { input.value = ""; load("all"); };
  wrap.querySelector("[data-refresh]").onclick = () => load(selected);
  load("all");
}
