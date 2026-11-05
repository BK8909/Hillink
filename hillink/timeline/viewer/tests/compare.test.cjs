const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/compare.js'), 'utf8');
function setup(api = async () => [], stubRender = false) {
  const elements = new Map();
  const get = s => { if (!elements.has(s)) elements.set(s, { innerHTML: '' }); return elements.get(s); };
  const refresh = async () => {}; refresh.list = [];
  const c = vm.createContext({
    console, api, setTimeout: fn => fn(), window: { addEventListener() {} },
    LIB: { model_ver: 'm1', input_ver: 'i1', knobs: { seed: { default: 0 }, no_busy_dwell: { default: 0 }, wd_day: { default: null } },
      anomalies: [1,2,3,4,5,6].map(ID => ({ ID, 이름: `상황${ID}`, 설명: '가정' })), dates: [{ date: '2026-10-17', fair: true }] },
    isWeekday: s => ![0,6].includes(new Date(s + 'T12:00:00Z').getUTCDay()), WEEKDAY_ONLY: ['wd_day'],
    refreshDays: refresh, $: get, $$: () => [], DAY: null, MODE: 'ask', DAYCACHE: {}, FLOWCACHE: {},
    esc: s => String(s ?? '').replace(/</g, '&lt;'), locName: s => s, assistSet() {},
  });
  vm.runInContext(source, c);
  const f = vm.runInContext('({ ASK, askPairSpec, askSameConfig, askScenarios, askRunScenario, renderAsk, drawAsk, askEvidencePanel })', c);
  if (stubRender) vm.runInContext('drawAsk = () => {}; renderAsk = async () => {};', c);
  return { c, f, get };
}
const day = (extra = {}) => ({ key: 'day28', date: '2026-10-28', scenario: 'none', scale: 1, theta: {}, model_ver: 'm1', input_ver: 'i1', ...extra });
const anomaly = ID => ({ id: 'an' + ID, kind: 'anom', label: '상황' + ID, a: { ID } });

test('모든 미계산 상황을 남기고, 등록된 행사 날짜에서만 행사 선택을 제공한다', async () => {
  const { f } = setup();
  const rows = await f.askScenarios(day());
  assert.equal(rows.length, 7);
  assert.equal(rows.some(x => x.id === 'an3'), true);
  assert.equal(rows.every(x => !x.ok), true);
  assert.equal((await f.askScenarios(day({ date: '2026-10-17' }))).length, 8);
});
test('비교 요청은 날짜·행사·규모·0인 가정·좌석을 보존하고 변칙과 시드만 분리한다', () => {
  const { f } = setup();
  const D = day({ scenario: 'winefair', scale: .5, theta: { wd_day: 0, buffet_seats: 317, seed: 2, anomaly: 4, anomaly_k: .5 } });
  const p = f.askPairSpec(D, anomaly(3));
  assert.equal(p.base.date, '2026-10-28'); assert.equal(p.base.scenario, 'winefair'); assert.equal(p.base.scale, .5);
  assert.equal(p.base.theta.wd_day, 0); assert.equal(p.base.theta.buffet_seats, 317);
  assert.equal(p.base.theta.anomaly, undefined); assert.equal(p.base.theta.seed, undefined);
  assert.equal(p.comp.theta.anomaly, 3); assert.equal(p.comp.theta.anomaly_k, .5);
  assert.equal(D.theta.anomaly, 4);
});
test('다른 날짜·행사·규모·버전·시드·0인 조정값의 결과를 잘못 재사용하지 않는다', async () => {
  const { f, c } = setup();
  const D = day({ theta: { wd_day: 0 } });
  const base = day({ key: 'A', theta: { wd_day: 0 } });
  const B = day({ key: 'B', theta: { wd_day: 0, anomaly: 3 } });
  for (const wrong of [{ date: '2026-10-21' }, { scenario: 'winefair' }, { scale: .5 }, { model_ver: 'old' }, { input_ver: 'old' }, { theta: { wd_day: .5, anomaly: 3 } }, { theta: { wd_day: 0, anomaly: 3, seed: 1 } }]) {
    c.refreshDays.list = [base, { ...B, ...wrong }];
    assert.equal((await f.askScenarios(D)).find(x => x.id === 'an3').ok, false);
  }
  c.refreshDays.list = [base, B];
  const found = (await f.askScenarios(D)).find(x => x.id === 'an3');
  assert.equal(found.ok, true); assert.equal(found.seed0, true); assert.equal(found.bKey, 'B');
});
test('완전히 일치하는 반복 계산을 단일 계산보다 우선한다 (bands 요약에 scale이 없어도 확인)', async () => {
  const band = { date: '2026-10-28', scenario: 'none', model_ver: 'm1', input_ver: 'i1', base_key: 'A', compare_key: 'B', theta: {}, compare: { anomaly: 3 }, seeds: 3 };
  const { f, c } = setup(async () => [band]);
  c.refreshDays.list = [day({ key: 'A' }), day({ key: 'B', theta: { anomaly: 3 } })];
  const r = (await f.askScenarios(day())).find(x => x.id === 'an3');
  assert.equal(r.band.seeds, 3); assert.equal(r.seed0, undefined);
  band.compare = { anomaly: 3, anomaly_k: 2 };
  assert.equal((await f.askScenarios(day())).find(x => x.id === 'an3').seed0, true);
});
test('A/B 계산 완료 후 결과를 갱신하며, 날짜를 바꿔도 이전 날짜로 되돌리지 않는다', async () => {
  const posts = []; let polls = 0;
  const { f, c } = setup(async (url, cfg) => {
    if (url === '/api/day') { posts.push(cfg); return { status: posts.length === 1 ? 'done' : 'running', key: posts.length === 1 ? 'A' : 'B' }; }
    if (url.startsWith('/api/day/status')) return ++polls === 1 ? { status: 'running', total: 100, done: 50 } : { status: 'done' };
    throw Error('unexpected request');
  }, true);
  c.DAY = day({ date: '2026-10-21', key: 'new-date' });
  c.DAYCACHE.A = {}; c.FLOWCACHE.B = {};
  await f.askRunScenario(day(), anomaly(3));
  assert.equal(posts.length, 2); assert.equal(posts[0].date, '2026-10-28'); assert.equal(posts[1].theta.anomaly, 3);
  assert.equal(c.DAY.key, 'new-date'); assert.equal(f.ASK.job, null); assert.equal(f.ASK.error, null);
  assert.equal(c.DAYCACHE.A, undefined); assert.equal(c.FLOWCACHE.B, undefined);
});
test('중복 클릭은 한 번만 실행하고 실패한 계산은 다시 시도할 수 있다', async () => {
  let release, requests = 0;
  const hold = new Promise(resolve => { release = resolve; });
  const { f, c } = setup(async url => {
    requests++;
    if (requests === 1) return hold;
    if (url === '/api/day') return { status: 'running', key: 'B' };
    return { status: 'error', error: '검증용 실패' };
  }, true);
  c.DAY = day();
  const p = f.askRunScenario(day(), anomaly(3));
  await f.askRunScenario(day(), anomaly(4)); assert.equal(requests, 1);
  release({ status: 'done', key: 'A' }); await p;
  assert.equal(f.ASK.job, null); assert.match(f.ASK.error.message, /검증용 실패/);
});
test('늦게 끝난 이전 날짜 조회가 새 날짜 화면을 덮어쓰지 않는다', async () => {
  const waits = [];
  const { f, c } = setup(() => new Promise(resolve => waits.push(resolve)));
  c.DAY = day({ date: '2026-10-17', key: 'old' }); const old = f.renderAsk();
  c.DAY = day({ key: 'new' }); const now = f.renderAsk();
  waits[1]([]); await now; waits[0]([]); await old;
  assert.equal(f.ASK.cur.D.key, 'new');
});
test('미계산 화면의 일곱 버튼을 활성화하고, 오른쪽에 이전 날짜 답을 남기지 않는다', async () => {
  const { f, c, get } = setup(); c.DAY = day();
  await f.renderAsk();
  const html = get('#askView').innerHTML;
  assert.equal((html.match(/data-scn=/g) || []).length, 7);
  assert.equal(/disabled/.test(html), false);
  assert.match(html, /10\/28/); assert.match(html, /시드 0 한 번/);
  assert.match(get('#askAssist').innerHTML, /10\/28/); assert.doesNotMatch(get('#askAssist').innerHTML, /10\/17/);
});

test('계산 기록의 기존 적용값과 조사 후보를 구분하고 출처·분모·가정 문구를 표시한다', () => {
  const { f } = setup();
  const evidence = JSON.parse(fs.readFileSync(path.join(__dirname, '../static/anomaly_evidence.json'), 'utf8'));
  const html = f.askEvidencePanel({ sc: anomaly(4), evidence, B: { anomaly: { applied: ['비투숙 × 1.10', '피자힐 선호 × 1.50'], src: '기존 모델 가정', grade: '△' } } });
  assert.match(html, /이번 계산에 적용/); assert.match(html, /비투숙 × 1.10/); assert.match(html, /피자힐 선호 × 1.50/);
  assert.match(html, /S01W/); assert.match(html, /분모/); assert.match(html, /직전4주 평균/); assert.match(html, /가정:/);
  assert.match(html, /1.406/); assert.match(html, /1.72/); assert.match(html, /1.883/); assert.match(html, /자동 적용하지 않음/);
  const rain = f.askEvidencePanel({ sc: anomaly(3), evidence, B: {} });
  assert.match(rain, /S02D/); assert.match(rain, /33일/); assert.match(rain, /발생 빈도 미확정/); assert.match(rain, /출처 기록 없음/);
  assert.equal(f.askEvidencePanel({ sc: { kind: 'seat' } }), '');
});
