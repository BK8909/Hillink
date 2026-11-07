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

st, saved = call('/api/saved-visits/run?tag=A05-v16-baseline')
check('4 stored V16 run loads', st == 200 and saved['request']['hybrid_policy'] == REPLAY)
st, flow = call('/api/visit', dict(saved['request'], judgment_mode='replay'))
check('4 stored AI judgment replay runs', st == 200 and flow.get('judgment', {}).get('actual') == 'replay', flow.get('judgment', {}).get('actual'))
decs = flow['plans']['A05']['autonomous_decisions']
same = [(d['date'], d['minute'], (d.get('selected_plan') or {}).get('action_id')) for d in decs] == \
       [(d['date'], d['minute'], (d.get('selected_plan') or {}).get('action_id')) for d in saved['result']['plans']['A05']['autonomous_decisions']]
check('4 replay equals the stored decisions', same, len(decs))
origins = {a['provider'].get('execution') for d in decs for a in d.get('attempts', []) if a.get('provider')}
check('4 every model answer came from the stored receipts', origins == {'CACHE_REPLAY'}, origins)

scenes = flow['plans']['A05']['scenes']
check('5 customer flow scenes', len(scenes) >= 8, len(scenes))
check('5 behaviour evidence attached to the judged scenes', any((s.get('basis') or {}).get('autonomous_decision') for s in scenes))

led = flow['ledger']; chk = led['checks']
check('6 ledger receipts = L4..L1 and day totals = visit total',
      chk.get('receipts_equal_L4_L3_L2_L1') is True and chk.get('day_totals_equal_visit_total') is True, chk)
spent = flow['plans']['A05']['summary']['spent_krw']
room = sum(r['paid_krw'] for r in led['levels']['L4'] if any(u.get('unit') in ('room_night', 'room_bundle') for u in r.get('quantity_by_unit') or []))
check('6 ledger total minus room nights = executed spend', led['totals']['paid_krw'] - room == spent, (led['totals']['paid_krw'], room, spent))
executed = sum((d.get('selected_plan') or {}).get('order_total_krw') or 0 for d in decs if d.get('execution_state') == 'EXECUTED')
check('6 orders of the judged decisions are inside the spend', executed <= spent, (executed, spent))

st, opts = call('/api/strategy/options')
check('7 operating strategy options', st == 200 and isinstance(opts, dict) and opts, list(opts)[:4] if isinstance(opts, dict) else opts)
st, live = call('/api/visit', dict(saved['request'], judgment_mode='live', hybrid_policy=LIVE), timeout=60)
check('8 LIVE refused without approval (no rule substitute)', st in (400, 403) and isinstance(live, dict) and live.get('code') and 'plans' not in live,
      (st, live.get('code') if isinstance(live, dict) else live))

# 9. one visit run links customer Facts -> judged action -> orders -> ledger (same run, same visit)
import collections, re
pid = 'A05'; rows = led['receipts'][pid]['rows']
check('9 every ledger row belongs to this run and visit', {r['run_id'] for r in rows} == {led['run_id']} and {r['visit_id'] for r in rows} == {flow['visit_id']},
      ({r['run_id'][:8] for r in rows}, led['run_id'][:8]))
check('9 ledger customers are exactly the requested customers', set(led['receipts']) == set(saved['request']['personas']), list(led['receipts']))
by_day = collections.defaultdict(list)
for sc in scenes: by_day[sc['visit_date']].append(sc)
linked = collections.defaultdict(int); unmatched = []
for r in rows:
    if r.get('scene_index') is None: continue
    sc = by_day[r['visit_date']][r['scene_index']]
    if sc['act'] != r['act']: unmatched.append((r['row_id'], r['act'], sc['act']))
    d = (sc.get('basis') or {}).get('autonomous_decision')
    if d: linked[(d['date'], d['minute'])] += r['paid_krw']
check('9 each ledger row points at the scene that produced it', not unmatched, unmatched[:3])
orders = [(d['date'], d['minute'], (d.get('selected_plan') or {}).get('order_total_krw') or 0) for d in decs if d.get('execution_state') == 'EXECUTED']
check('9 each judged order equals the ledger rows of its scene', all(linked.get((a, b), 0) == t for a, b, t in orders), [(a, b, t, linked.get((a, b))) for a, b, t in orders if t])
nights = sum(1 for r in rows if r['act'] == 'room_night')
check('9 room-night rows = visit nights', nights == flow['visit']['nights'], (nights, flow['visit']['nights']))
st, plib = call('/api/library/personas')
profile = set(re.findall(pid + r'-F\d+', json.dumps([x for x in plib['personas'] if x['id'] == pid], ensure_ascii=False)))
cited = {f for d in decs for k in ('supporting_fact_ids', 'counterevidence_fact_ids') for f in ((d.get('selected_plan') or {}).get(k) or [])}
sent = {f for d in decs for x in ((d.get('input_context') or {}).get('facts') or []) for f in x['fact_ids']}
check('9 cited Facts were sent with the judgment and exist in the customer profile', cited and cited <= sent <= profile, (sorted(cited - sent), sorted(sent - profile)))

# 10. counterexamples: a changed request is a new run; a stored judgment is never reused for other inputs
st, rerun = call('/api/visit', dict(saved['request'], judgment_mode='rules', duration='stay_2'))
check('10 changed condition -> new run id, no rows of the previous run', st == 200 and rerun['ledger']['run_id'] != led['run_id']
      and all(r['run_id'] == rerun['ledger']['run_id'] for c in rerun['ledger']['receipts'].values() for r in c['rows']), rerun['ledger']['run_id'][:8])
st, again = call('/api/visit', dict(saved['request'], judgment_mode='replay'))
check('10 same request -> same run id and same ledger (replay)', st == 200 and again['ledger']['run_id'] == led['run_id'] and again['ledger']['totals'] == led['totals'])
for name, change in (('another customer', dict(personas=['A07'])), ('another start date', dict(start_date='2026-11-14'))):
    st, held = call('/api/visit', dict(saved['request'], judgment_mode='replay', **change))
    states = {d.get('execution_state') for p in ((held or {}).get('plans') or {}).values() for d in p.get('autonomous_decisions') or []} if isinstance(held, dict) else None
    check('10 stored judgment refused for ' + name + ' (hold, no ledger, no rule substitute)', st in (400, 409) and held.get('code') and 'ledger' not in held
          and states <= {'EXECUTION_HOLD'}, (st, held.get('code') if isinstance(held, dict) else held, states))
print('\nHTTP E2E: %d/%d checks passed' % (sum(ok for _, ok in results), len(results)))
