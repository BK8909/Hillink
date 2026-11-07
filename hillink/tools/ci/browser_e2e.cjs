// Offline browser end-to-end check (no API key, no model call). Needs `playwright` and Chromium.
//   node tools/ci/browser_e2e.cjs http://127.0.0.1:8994 [screenshot-dir]
// Fails on any page error, console error, HTTP >= 400, or a missing step of the product flow.
const { chromium } = require('playwright');
const fs = require('fs');
const B = (process.argv[2] || 'http://127.0.0.1:8994').replace(/\/$/, '');
const OUT = process.argv[3] || '';
if (OUT) fs.mkdirSync(OUT, { recursive: true });
let failed = false;
const ok = (name, cond, detail = '') => { console.log((cond ? 'PASS ' : 'FAIL ') + name + (detail ? ' · ' + detail : '')); if (!cond) failed = true; };
const shot = async (p, name) => { if (OUT) await p.screenshot({ path: `${OUT}/${name}.png` }); };

(async () => {
  const browser = await chromium.launch();
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [], http = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)); });
  p.on('response', r => { if (r.status() >= 400) http.push(r.status() + ' ' + r.url().replace(B, '')); });
  try {
    await p.goto(B + '/#lib', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
    const body = (await p.textContent('body')).replace(/\s+/g, ' ');
    ok('library shows 45 customers / 28 runnable', /45\s*명.*실행 가능 28/.test(body)); await shot(p, '01-library');

    await p.evaluate(() => { location.hash = '#lib/profile/A05'; }); await p.waitForTimeout(1500);
    const prof = (await p.textContent('#libraryView')).replace(/\s+/g, ' ');
    ok('profile page opens', prof.includes('No.0005'), prof.slice(0, 60)); await shot(p, '02-profile');

    // operating strategy before any run: empty state, no TypeError
    await p.click('button.tab[data-mode="opx"]'); await p.waitForTimeout(1200);
    await p.click('#opxView >> text=운영 전략'); await p.waitForTimeout(1500);
    ok('operating strategy opens before any run (empty state)', await p.$('.st-ab') !== null); await shot(p, '03-strategy-empty');
    await p.click('.st-ab [data-st-close]').catch(() => {});

    await p.evaluate(() => { location.hash = '#situation/A05'; }); await p.waitForSelector('#sitJudgment', { timeout: 20000 }); await p.waitForTimeout(500);
    const modes = await p.$$eval('#sitJudgment option', o => o.map(x => x.textContent.trim()));
    ok('judgment modes use plain labels', modes.join('|') === '저장된 판단 재현 (무과금)|실시간 AI 판단 (API 호출)|규칙 계산 (AI 없음)', modes.join('|'));
    await p.selectOption('#sitJudgment', 'live'); await p.waitForTimeout(800);
    const liveReq = await p.evaluate(() => situationRequest(SIT.pid, situationForm(SIT.pid), SIT.options));
    ok('LIVE request names V19LS', liveReq.hybrid_policy === 'LLM_AUTONOMOUS_CUSTOMER_V19LS', liveReq.hybrid_policy);
    ok('LIVE unavailable notice shown', /사용할 수 없습니다/.test(await p.textContent('#sitLiveStatus')));
    await p.selectOption('#sitJudgment', 'replay'); await p.waitForTimeout(300);
    await p.click('.st-judgment details.st-saved summary'); await p.selectOption('#sitSavedRun', 'A05-v16-baseline'); await p.waitForTimeout(1200);
    await shot(p, '04-situation');
    await p.click('#sitRun');
    await p.waitForFunction(() => (typeof AG !== 'undefined' && AG.flow && !AG.busy) || document.querySelector('.callout'), null, { timeout: 240000 });
    await p.waitForTimeout(1200);
    const st = await p.evaluate(() => ({ actual: AG.flow.result.judgment?.actual, n: AG.flow.result.plans.A05.autonomous_decisions.length, ledger: AG.flow.result.ledger?.checks }));
    ok('stored AI judgment replay renders', st.actual === 'replay' && st.n > 0, JSON.stringify({ actual: st.actual, n: st.n }));
    await shot(p, '05-flow');
    await p.click('button.tab[data-mode="evidence"]'); await p.waitForTimeout(2000);
    ok('behaviour evidence page for the run', (await p.evaluate(() => location.hash)).startsWith('#evidence/run/'), await p.evaluate(() => location.hash.slice(0, 40))); await shot(p, '07-evidence');
    await p.click('button.tab[data-mode="opx"]'); await p.waitForTimeout(2000);
    const rev = (await p.textContent('#opxView')).replace(/\s+/g, ' ');
    ok('revenue view for the same run', (await p.evaluate(() => location.hash)).startsWith('#revenue/run/') && /원/.test(rev), await p.evaluate(() => location.hash.slice(0, 40))); await shot(p, '08-revenue');
    await p.click('#opxView >> text=운영 전략'); await p.waitForTimeout(2000);
    const strat = (await p.textContent('.st-ab')).replace(/\s+/g, ' ');
    ok('operating strategy analyses the current run', /현재 실행 분석/.test(strat)); await shot(p, '09-strategy');
    await p.click('.st-ab [data-st-close]').catch(() => {});
    await p.click('button.tab[data-mode="day"]').catch(() => {}); await p.waitForTimeout(1500);
    const scenes = await p.evaluate(() => agScenes(AG.one).map(s => ({ si: s.si, act: s.act })));
    ok('flow has scenes', scenes.length >= 8, scenes.length);
    await p.evaluate(si => { agPause(); agSetScene(si); }, scenes[Math.min(3, scenes.length - 1)].si); await p.waitForTimeout(600);
    ok('scene dialogue panel renders', (await p.$('#right')) !== null); await shot(p, '06-scene');


    for (const [w, h] of [[1024, 800], [390, 844]]) {
      await p.setViewportSize({ width: w, height: h }); await p.waitForTimeout(500);
      for (const hash of ['#lib', '#situation/A05']) {
        await p.evaluate(x => { location.hash = x; }, hash); await p.waitForTimeout(900);
        const sw = await p.evaluate(() => document.documentElement.scrollWidth);
        ok(`no horizontal overflow ${hash} @${w}px`, sw <= w, sw);
      }
      await shot(p, `10-${w}`);
    }
  } catch (e) { ok('flow completed without exception', false, e.message); }
  ok('no page or console errors', errs.length === 0, errs.slice(0, 3).join(' | '));
  ok('no HTTP >= 400 responses', http.length === 0, http.slice(0, 3).join(' | '));
  await browser.close();
  console.log(failed ? '\nBROWSER E2E: FAILED' : '\nBROWSER E2E: all checks passed');
  process.exit(failed ? 1 : 0);
})();
