// 2026-11-09 전체분석 탭 — 후기 28명의 사실 기록을 종합한 워커힐 운영 제안(정적 자료 static/overall_analysis.json). 핵심 결론 → 우선 추천 3 → 문제 · 근거 · 제안 · 검증.
// 시뮬레이션 실행 결과가 아니라 프로파일 근거 분석이며, 실행 · 원장 · 엔진 상태를 읽거나 바꾸지 않는다. 후기 원문 없음(고객 ID와 행동 범주만).
(function (root) {
  const OA = { data: null, error: null };
  const e = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ids = list => list.length ? list.map(x => `<span class="oa-id">${e(x)}</span>`).join('') : '<span class="oa-none">없음</span>';

  function bars(rows, tone, total, max) {   // 좋아한 것 · 아쉬워한 것을 같은 눈금(max)으로 그린다
    return `<ol class="oa-bars oa-${tone}">${rows.map(r => {
      const n = r.customers.length;
      return `<li><div class="oa-bar-head"><b>${e(r.label)}</b><span>${n}명 / ${total}</span></div>` +
        `<div class="oa-track" aria-hidden="true"><i style="width:${(100 * n / max).toFixed(1)}%"></i></div>` +
        `<p>${e(r.pattern)}</p><div class="oa-ids">${ids(r.customers)}</div></li>`;
    }).join('')}</ol>`;
  }

  function render(d) {
    const total = d.age_groups.reduce((s, g) => s + g.customers.length, 0);
    const scale = Math.max(1, ...[...d.liked, ...d.lacked].map(r => r.customers.length));
    const byRank = Object.fromEntries(d.proposals.map(p => [p.rank, p]));
    const topRanks = new Set(d.top3.flatMap(t => t.ranks));
    const ageRows = d.age_groups.map(g => `<tr><th>${e(g.label)}</th><td class="oa-num">${g.customers.length}명</td><td>${e(g.basis)}</td><td><div class="oa-ids">${ids(g.customers)}</div></td></tr>`).join('');
    const props = d.proposals.map(p => `<tr class="${topRanks.has(p.rank) ? 'oa-top-row' : ''}"><td class="oa-num">${p.rank}</td><th>${e(p.title)}${topRanks.has(p.rank) ? '<span class="oa-flag">우선</span>' : ''}</th><td>${e(p.basis)}</td><td>${e(p.change)}</td><td>${e(p.metric)}</td></tr>`).join('');
    const side = d.side_patterns.map(s => `<li><b>${e(s.label)}</b> ${s.customers.length}명 — ${e(s.pattern)} <span class="oa-ids">${ids(s.customers)}</span></li>`).join('');
    const top = d.top3.map((t, i) => `<article class="oa-pick oa-pick-${e(t.key)}"><span class="oa-pick-label">${i + 1} · ${e(t.label)}</span><b>${e(t.title)}</b>` +
      `<p>${e(t.evidence)}</p><small>전략표 ${t.ranks.map(r => `${r}. ${e(byRank[r] ? byRank[r].title : '')}`).join(' · ')}</small></article>`).join('');
    const ab = d.ab_reference;
    return `<div class="oa">
<div class="oa-head"><div><span class="oa-eyebrow">전체분석</span><h2>후기 ${total}명을 종합한 워커힐 운영 제안</h2>
<p>${e(d.question)} · ${e(d.scope)} · 기준일 ${e(d.as_of)}</p></div>
<div class="oa-badges"><span>${e(d.kind_label)}</span><span>${e(d.privacy)}</span></div></div>

<section class="oa-conclusion" aria-label="핵심 결론"><span class="oa-eyebrow">핵심 결론</span><p>${e(d.conclusion)}</p>
<div class="oa-mini"><span><b>${total}명</b> 후기 종합</span><span><b>${d.liked.length}개</b> 긍정 경험 패턴</span><span><b>${d.lacked.length}개</b> 불편 패턴</span><span><b>${d.proposals.length}개</b> 운영 개선안</span></div></section>

<section class="oa-picks" aria-label="우선 추천 3개">${top}</section>

<section class="oa-sec oa-problem"><h3>1. 문제</h3><p class="oa-lead">${e(d.problem.statement)}</p>
<p class="oa-note">${e(d.problem.premise_status)}</p><p>${e(d.problem.question)} 우리가 프로파일링한 블로그 후기 작성자가 바로 그 손님입니다.</p></section>

<section class="oa-sec"><h3>2. 고객 근거</h3>
<p class="oa-lead">공간 경험은 반복해서 좋은 평가를 받았고, 불편은 식음 가격과 이용 과정(예약·대기·조식 시간·시설 조건)에 몰렸습니다.</p>
<div class="oa-two"><div><h4>좋아한 경험</h4>${bars(d.liked, 'good', total, scale)}</div><div><h4>아쉬운 경험</h4>${bars(d.lacked, 'bad', total, scale)}</div></div>
<h4>공통 경험 패턴</h4><ul class="oa-side">${side}</ul>
<details class="oa-age"><summary>분석 대상과 연령 추정 기준</summary><p class="oa-note">${e(d.age_note)} 기준 — ${e(d.age_rule)}</p>
<div class="oa-tablewrap"><table class="oa-table"><thead><tr><th>구분</th><th>인원</th><th>판단 근거</th><th>고객</th></tr></thead><tbody>${ageRows}</tbody></table></div></details></section>

<section class="oa-sec"><h3>3. 운영 제안</h3>
<p class="oa-lead">강점인 공간 경험은 상품의 중심에 두고, 이용 과정의 불편은 먼저 줄입니다. 일곱 가지 개선안 모두 고객 근거 → 운영자가 변경할 사항 → 검증 지표로 이어집니다.</p>
<div class="oa-tablewrap"><table class="oa-table"><thead><tr><th>순번</th><th>개선안</th><th>고객 근거</th><th>운영자가 변경할 사항</th><th>검증 지표</th></tr></thead><tbody>${props}</tbody></table></div>
<p class="oa-note">${e(d.deferred)}</p>
<aside class="oa-ab"><span class="oa-eyebrow">${e(ab.label)}</span><p>${e(ab.finding)}</p><p><b>${e(ab.implication)}</b></p><p class="oa-note">${e(ab.separation)}</p></aside></section>

<section class="oa-sec"><h3>4. 검증 방법</h3>
<p class="oa-lead">시뮬레이션 결과만으로 효과가 있다고 말하지 않습니다. 전제 확인 → 시뮬레이션 사전 점검 → 현장 파일럿 순서로 판정합니다.</p>
<ol class="oa-steps">${d.validation.map(v => `<li><b>${e(v.step)}</b><span>${e(v.detail)}</span></li>`).join('')}</ol>
<p><b>최종 성공 기준</b> · ${e(d.success)}</p>
<h4>한계</h4><ul class="oa-limits">${d.limits.map(x => `<li>${e(x)}</li>`).join('')}</ul></section>
</div>`;
  }

  async function oaLoad() {
    if (OA.data) return OA.data;
    const r = await fetch('/static/overall_analysis.json', { cache: 'no-cache' });
    if (!r.ok) throw Error('전체분석 자료를 불러오지 못했습니다 (' + r.status + ')');
    OA.data = await r.json();
    return OA.data;
  }

  async function oaEnter() {
    const el = document.getElementById('analysisView');
    if (!el) return;
    if (!OA.data) el.innerHTML = '<div class="oa"><p class="oa-note">불러오는 중…</p></div>';
    try { el.innerHTML = render(await oaLoad()); el.scrollTop = 0; }
    catch (err) { OA.error = err.message; el.innerHTML = `<div class="oa"><div class="callout">${e(err.message)}</div></div>`; }
  }

  root.HLAnalysis = { render, oaLoad, state: OA };
  root.oaEnter = oaEnter;
  if (typeof module !== 'undefined') module.exports = { render };
})(typeof window !== 'undefined' ? window : globalThis);
