// 2026-11-09 전체분석 탭 — 정적 프로파일 근거 분석의 자료 계약과 화면 연결.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = path.join(__dirname, '../static');
const data = JSON.parse(fs.readFileSync(path.join(S, 'overall_analysis.json'), 'utf8'));
const { render } = require(path.join(S, 'analysis.js'));

test('age groups partition the 28 runnable profiles once each, no middle-aged without clear evidence', () => {
  const all = data.age_groups.flatMap(g => g.customers);
  assert.equal(all.length, 28);
  assert.equal(new Set(all).size, 28);
  assert.deepEqual(data.age_groups.find(g => g.key === 'middle').customers, []);
});

test('every evidence row only names classified customers and counts match the ids', () => {
  const known = new Set(data.age_groups.flatMap(g => g.customers));
  for (const row of [...data.liked, ...data.lacked, ...data.side_patterns]) {
    assert.ok(row.customers.length > 0, row.label);
    assert.equal(new Set(row.customers).size, row.customers.length, row.label);
    for (const id of row.customers) assert.ok(known.has(id), `${row.label}: ${id}`);
  }
});

test('the view states it is profile evidence, not a simulation result, and carries no review text', () => {
  assert.match(data.kind_label, /시뮬레이션 실행 결과 아님/);
  const html = render(data);
  assert.match(html, /시뮬레이션 실행 결과 아님/);
  assert.ok(html.indexOf('핵심 결론') < html.indexOf('1. 문제'), 'conclusion comes before the four sections');
  assert.ok(html.includes(data.conclusion));
  assert.ok(html.includes(data.ab_reference.finding) && html.includes(data.ab_reference.separation));
  for (const p of data.proposals) assert.ok(html.includes(p.title));
  assert.ok(!/<script/i.test(html));
  // liked and lacked bars share one scale: 9 customers = 100%, 7 customers = 77.8%
  assert.match(html, /width:100\.0%/);
  assert.match(html, /width:77\.8%/);
});

test('the tab sits right after 행동근거 and routes to a full-screen view', () => {
  const idx = fs.readFileSync(path.join(S, 'index.html'), 'utf8');
  const ev = idx.indexOf('data-mode="evidence"'), an = idx.indexOf('data-mode="analysis"');
  assert.ok(ev > 0 && an > ev && idx.slice(ev, an).split('<button').length === 2, 'analysis tab directly follows evidence');
  assert.match(idx, /<section id="analysisView"><\/section>/);
  assert.match(idx, /static\/analysis\.js/);
  const app = fs.readFileSync(path.join(S, 'app.js'), 'utf8');
  assert.match(app, /if \(m === "analysis"\)[\s\S]{0,600}oaEnter\(\)/);
  assert.match(app, /\$\("main"\)\.classList\.remove\("analysis"\)/);
});

test('fixed counts, seven proposals and the top three are kept', () => {
  const count = rows => Object.fromEntries(rows.map(r => [r.label, r.customers.length]));
  assert.deepEqual(Object.values(count(data.liked)), [9, 7, 6, 6, 5, 3]);
  assert.deepEqual(Object.values(count(data.lacked)), [7, 5, 4, 4, 2, 1]);
  assert.deepEqual(data.proposals.map(p => p.rank), [1, 2, 3, 4, 5, 6, 7]);
  for (const p of data.proposals) assert.ok(p.basis && p.change && p.metric, p.title);
  assert.deepEqual(data.top3.map(t => t.label), ['경험 강화', '소비 확대', '이용 편의']);
  const ranks = new Set(data.proposals.map(p => p.rank));
  for (const t of data.top3) for (const r of t.ranks) assert.ok(ranks.has(r));
  const html = render(data);
  assert.equal((html.match(/class="oa-pick /g) || []).length, 3);
  assert.equal((html.match(/<tr class="(oa-top-row)?"><td class="oa-num">/g) || []).length, 7);
});
