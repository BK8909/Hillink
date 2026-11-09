"""Offline HTTP end-to-end check against a running product server (no API key, no model call).

  python tools/ci/http_e2e.py http://127.0.0.1:8994

Flow: build and policy identity -> customer library -> profile/source records -> stored AI judgment replay
-> customer flow and behaviour evidence -> orders and virtual revenue ledger -> operating strategy entry
-> LIVE request refused without approval (no silent rule substitute). Exit 1 on the first failed check.
"""
import json, sys, urllib.error, urllib.request

BASE = sys.argv[1].rstrip('/')
LIVE, PREVIOUS, REPLAY = 'LLM_AUTONOMOUS_CUSTOMER_V19LS', 'LLM_AUTONOMOUS_CUSTOMER_V17', 'LLM_AUTONOMOUS_CUSTOMER_V16'
DEMO = {'A01', 'A02', 'A03', 'A04', 'A05', 'A07', 'A08', 'A10', 'blog41', 'blog42', 'blog43'}
results = []


def call(path, body=None, timeout=600):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw or b'null')
        except ValueError: return e.code, raw[:200]


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (' · ' + str(detail) if detail else ''))
    if not ok: sys.exit(1)


st, page = None, None
with urllib.request.urlopen(BASE + '/', timeout=60) as r: st, page = r.status, r.read().decode('utf-8', 'replace')
check('1 index page', st == 200 and '<html' in page.lower())
st, build = call('/api/build'); check('1 build identity', st == 200 and build.get('head'), build)
st, cap = call('/api/runtime/capabilities')
check('1 LIVE default policy is V19LS', st == 200 and cap.get('live_policy') == LIVE, cap.get('live_policy'))
check('1 LIVE disabled in this environment; replay and rules available',
      cap['judgment_modes'] == {'rules': True, 'replay': True, 'live': False}, cap['judgment_modes'])
check('1 V16 replay and V17 remain registered', REPLAY in cap['replay_policies'] and PREVIOUS in cap['replay_policies'])

st, lib = call('/api/library/personas')
demo = {p['id'] for p in lib.get('personas', [])}
check('2 library: 11 demo customers', st == 200 and demo == DEMO, sorted(demo))
iso = set(cap.get('isolated_customers') or [])
check('2 library: 28 runnable (11 demo + 17 SHA-validated)', len(demo | iso) == 28, len(demo | iso))
st, full = call('/api/library')
check('3 profile/source records served', st == 200 and full.get('review_list'), len(full.get('review_list') or []))

# Public product: V16 is a historical internal regression only, not a selectable saved visit.
st, saved_index = call('/api/saved-visits')
check('4 public saved list excludes retired V16', st == 200 and isinstance(saved_index.get('runs'), list)
      and all('-v16-' not in r.get('tag','') for r in saved_index['runs']))
st, retired = call('/api/saved-visits/run?tag=A05-v16-baseline')
check('4 retired V16 is not served as a product visit', st == 410 and retired.get('code') == 'RETIRED_V16_SAVED_VISIT')

request = dict(personas=['A05'], duration='stay_1', event_mode='none', seed=0, start_date='2026-10-24',
               include_ledger=True, judgment_mode='rules', behavior_engine='m4_c01', catalog_policy='C01_HOTEL_CATALOG_V1')
st, flow = call('/api/visit', request)
check('5 public rules visit runs with no model call', st == 200 and flow.get('judgment', {}).get('actual') == 'rules',
      (st, flow.get('judgment') if isinstance(flow,dict) else flow))
scenes = flow['plans']['A05']['scenes']
check('5 customer flow scenes', len(scenes) >= 5, len(scenes))
check('5 rules scenes have recorded choice explanation', any((s.get('basis') or {}).get('choice') for s in scenes))

led = flow['ledger']
checks = led['checks']
check('6 receipts and day totals match ledger levels',
      checks.get('receipts_equal_L4_L3_L2_L1') is True and checks.get('day_totals_equal_visit_total') is True, checks)
rows = led['receipts']['A05']['rows']
check('6 every ledger row from this run and visit',
      bool(rows) and {r['run_id'] for r in rows} == {led['run_id']}
      and {r['visit_id'] for r in rows} == {flow['visit_id']})
nights = sum(r['act'] == 'room_night' for r in rows)
check('6 room nights equal visit duration', nights == flow['visit']['nights'] == 1, nights)
spent = flow['plans']['A05']['summary']['spent_krw']
room = sum(r['paid_krw'] for r in rows if r['act'] == 'room_night')
check('6 customer spend plus room charges equals total paid', spent + room == led['totals']['paid_krw'],
      (spent, room, led['totals']['paid_krw']))

st, opts = call('/api/strategy/options')
check('7 strategy options are available for the same rules run', st == 200 and isinstance(opts,dict) and bool(opts))
st, live = call('/api/visit', dict(request, judgment_mode='live', hybrid_policy=LIVE), timeout=60)
check('8 LIVE refused without authorization, never silently rules',
      st in (400,403) and isinstance(live,dict) and live.get('code') and 'ledger' not in live,
      (st, live.get('code') if isinstance(live,dict) else live))

st, same = call('/api/visit', request)
check('9 same rules visit and ledger are deterministic',
      st == 200 and same['ledger']['run_id'] == led['run_id'] and same['ledger']['totals'] == led['totals'])
st, different = call('/api/visit', dict(request, duration='stay_2'))
check('9 changing duration creates a distinct run without old rows',
      st == 200 and different['ledger']['run_id'] != led['run_id']
      and all(r['run_id'] == different['ledger']['run_id'] for c in different['ledger']['receipts'].values() for r in c['rows']))
st, blocked = call('/api/visit', dict(request, judgment_mode='replay', hybrid_policy='LLM_AUTONOMOUS_CUSTOMER_V19LS_INT4'))
check('10 no saved match never becomes a fabricated replay',
      st in (400,409) and isinstance(blocked,dict) and blocked.get('code') and 'ledger' not in blocked,
      (st, blocked.get('code') if isinstance(blocked,dict) else blocked))

print('\nHTTP E2E: %d/%d checks passed' % (sum(ok for _, ok in results), len(results)))
