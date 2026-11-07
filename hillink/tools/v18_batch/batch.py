"""HILLINK V18 cross-experiment batch (2026-11-06 approval): C / L2 / S2 over many customers.

  python3 tools/v18_batch/batch.py plan                                   # print the job plan (no calls)
  python3 tools/v18_batch/batch.py run --batch-dir <private dir> --shadow offline|live [--workers 2] [--only A,B,C]

Experiments (each job is one run of tools/v18_bench/run.py in its own private run directory):
  A  6 customers x first-day dinner decision + the decision after it x {C, L2, S2} x 3 independent repetitions
  B  3 customers x 2 operator scenarios (couple/anniversary, solo/rest; same building, arrival, breakfast plan)
     x first decision x {C, L2, S2} x 2 repetitions
  C  3 customers x {C, L2, S2}: full-visit LIVE — the policy chooses every action and the engine executes it

One cap for the whole approval, shared by all workers and restarts (tools/v18_bench/guard.py BatchGuard,
file lock): 240 new calls, US$6.00 worst-case reserved, pools A 116 / B 44 / C 80. The shared ledger
(2,500 calls / US$20) applies on top and is checked before the batch starts; the lower remaining room wins.
Per-job dollar caps are fixed so that their sum stays within the batch dollar cap. A job that finished
is not run again; a restarted job reuses its finished calls and never re-sends an interrupted or errored
call (provider errors such as HTTP 503 are counted, not retried). Results land per call in the run folders
as they happen; <batch_dir>/batch_status.json is rewritten after every job.
"""
import argparse, json, os, re, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/v18_bench'))
import guard as G  # noqa: E402

POL = dict(C='LLM_AUTONOMOUS_CUSTOMER_V18BM', L2='LLM_AUTONOMOUS_CUSTOMER_V18L2', S2='LLM_AUTONOMOUS_CUSTOMER_V18S2')
ORDERS = (('C', 'L2', 'S2'), ('L2', 'S2', 'C'), ('S2', 'C', 'L2'))
# evidence richness from the offline scan (citable Facts in the full profile / sent at dinner under C)
A_CUSTOMERS = [('A07', 'rich'), ('A10', 'rich'), ('A02', 'medium'), ('A05', 'medium'), ('N03', 'low'), ('A19', 'low')]
B_CUSTOMERS = [('A07', 'rich'), ('A05', 'medium'), ('N03', 'low')]
C_CUSTOMERS = [('A07', 'rich'), ('A02', 'medium'), ('N03', 'low')]
SCENARIOS = dict(
    couple=dict(building='VISTA', party_size=2, party_composition=dict(adult_count=2, children=[]), breakfast_plan='breakfast_included', visit_purpose='anniversary'),
    solo=dict(building='VISTA', party_size=1, party_composition=dict(adult_count=1, children=[]), breakfast_plan='breakfast_included', visit_purpose='rest'))
BATCH_MAX_CALLS, BATCH_MAX_USD = 240, 6.00
POOLS = dict(A=116, B=44, C=80)
JOB_CAPS = dict(A=(8, 0.15), B=(6, 0.075), C=(14, 0.22))   # per job: calls, worst-case USD (sum of USD caps <= 6.00)


def plan():
    jobs = []
    for pid, tier in C_CUSTOMERS[:1]:   # priority: a representative full visit first, for every policy
        for p in ('C', 'L2', 'S2'): jobs.append(dict(id='C_%s_%s' % (pid, p), exp='C', pid=pid, tier=tier, policy=p, args=['--case', 'pid:%s' % pid, '--e2e-policy', POL[p]]))
    ab = []
    for rep in range(3):
        for pid, tier in A_CUSTOMERS:
            order = ORDERS[rep]
            ab.append(dict(id='A_%s_r%d' % (pid, rep + 1), exp='A', pid=pid, tier=tier, rep=rep + 1, order=list(order),
                           args=['--case', 'pid:%s' % pid, '--points', 'dinner_after', '--variants', ','.join(POL[x] for x in order)]))
        if rep < 2:
            for pid, tier in B_CUSTOMERS:
                for sc in ('couple', 'solo'):
                    order = ORDERS[(rep + (sc == 'solo')) % 3]
                    ab.append(dict(id='B_%s_%s_r%d' % (pid, sc, rep + 1), exp='B', pid=pid, tier=tier, rep=rep + 1, scenario=sc, order=list(order),
                                   args=['--case', 'pid:%s' % pid, '--points', 'first_decision', '--arrival', '16:30',
                                         '--visit-conditions', json.dumps(SCENARIOS[sc]), '--variants', ','.join(POL[x] for x in order)]))
    jobs += ab
    for pid, tier in C_CUSTOMERS[1:]:
        for p in ('C', 'L2', 'S2'): jobs.append(dict(id='C_%s_%s' % (pid, p), exp='C', pid=pid, tier=tier, policy=p, args=['--case', 'pid:%s' % pid, '--e2e-policy', POL[p]]))
    for j in jobs:
        j['max_calls'], j['max_usd'] = JOB_CAPS[j['exp']]
    assert sum(j['max_usd'] for j in jobs) <= BATCH_MAX_USD + 1e-9, 'per-job dollar caps exceed the batch cap'
    return jobs


# 2026-11-06 final check: the product's V17 LIVE policy vs LS, both choosing and executing their own actions
# from the visit start, stopped after the first K model decisions (dinner, and the decision after it where the
# day has more); 24 calls / US$0.50 for the whole plan, per-job USD caps summing to <= 0.50.
FINAL = dict(max_calls=24, max_usd=0.50, pools=dict(F=24))
FINAL_CASES = [('A07', 'rich', 2), ('N03', 'low', 1), ('A19', 'low', 1), ('WH-00532', 'medium-mixed', 2), ('A02', 'medium-prior-meal', 2)]
FINAL_POL = dict(V17='LLM_AUTONOMOUS_CUSTOMER_V17', LS='LLM_AUTONOMOUS_CUSTOMER_V18LS', V19LS='LLM_AUTONOMOUS_CUSTOMER_V19LS')


def plan_final():
    jobs = []
    for pid, tier, k in FINAL_CASES:
        for p in ('V17', 'LS'):
            usd = {('V17', 2): 0.07, ('V17', 1): 0.04, ('LS', 2): 0.04, ('LS', 1): 0.025}[(p, k)]
            jobs.append(dict(id='F_%s_%s' % (pid, p), exp='F', pid=pid, tier=tier, policy=p, max_calls=k + 1, max_usd=usd,
                             args=['--case', 'pid:%s' % pid, '--e2e-policy', FINAL_POL[p], '--e2e-max-decisions', str(k)]))
    assert sum(j['max_usd'] for j in jobs) <= FINAL['max_usd'] + 1e-9
    return jobs



# 2026-11-07 P5 (LS stabilisation, approval: 200 calls / US$5.00 for the whole plan, past remainders not used).
# B  product comparison: V17 (product LIVE) vs V19LS, full visits that execute each policy's own choices from the
#    visit start, stopped after K model decisions; 6 customers x 2 policies x 2 repetitions, run order crossed
#    (rep 1: V17 first, rep 2: V19LS first). A07 runs the operator scenario couple/anniversary (purpose given).
# A  cause analysis (first decision only): V17 effort high, V17 effort medium, V18LS, V19LS on 3 customers.
# A and B are reported separately; no single improvement rate is computed across them.
V19 = dict(max_calls=200, max_usd=5.00, pools=dict(B=176, A=24))   # the pools cap actual calls; per-job caps stop a runaway job
V19_B = [('N03', 'negative-memory', 4, None), ('WH-00532', 'mixed', 4, None), ('A02', 'prior-meal-quantity', 4, None),
         ('A07', 'rich-anniversary', 4, 'couple'), ('A19', 'sparse', 3, None), ('A05', 'repeat-activity', 4, None)]
V19_A = ['A02', 'WH-00532', 'A07']
V19_A_SETTINGS = [('V17H', 'LLM_AUTONOMOUS_CUSTOMER_V17', 'high'), ('V17M', 'LLM_AUTONOMOUS_CUSTOMER_V17', 'medium'),
                  ('LS', 'LLM_AUTONOMOUS_CUSTOMER_V18LS', None), ('V19LS', 'LLM_AUTONOMOUS_CUSTOMER_V19LS', None)]


def plan_v19():
    jobs = []
    for rep in (1, 2):
        order = ('V17', 'V19LS') if rep == 1 else ('V19LS', 'V17')
        for pid, tier, k, sc in V19_B:
            for p in order:
                usd = (0.25 if p == 'V17' else 0.11) * k / 4   # worst-case reservation per call measured 11/06: V17 ~0.023, LS ~0.013
                extra = ['--arrival', '16:30', '--visit-conditions', json.dumps(SCENARIOS[sc])] if sc else []
                jobs.append(dict(id='B_%s_%s_r%d' % (pid, p, rep), exp='B', pid=pid, tier=tier, policy=p, rep=rep, scenario=sc,
                                 max_calls=2 * k, max_usd=round(usd, 3),
                                 args=['--case', 'pid:%s' % pid, '--e2e-policy', FINAL_POL[p], '--e2e-max-decisions', str(k)] + extra))
    for pid in V19_A:
        for name, pol, effort in V19_A_SETTINGS:
            jobs.append(dict(id='A_%s_%s' % (pid, name), exp='A', pid=pid, policy=name, max_calls=2,
                             max_usd=0.05 if pol.endswith('V17') else 0.03, env=dict(HILLINK_AGENT_EFFORT=effort) if effort else {},
                             args=['--case', 'pid:%s' % pid, '--e2e-policy', pol, '--e2e-max-decisions', '1']))
    assert sum(j['max_usd'] for j in jobs) <= V19['max_usd'] + 1e-9, 'per-job dollar caps exceed the approval'
    assert sum(j['max_calls'] for j in jobs if j['exp'] == 'A') <= V19['pools']['A']
    return jobs



# 2026-11-07 P5 follow-up (approval in the user's directive: at most 16 new calls, US$0.05): the V19LS-only
# day-end review match, re-checked LIVE on A07 (anniversary scenario) and A05, 2 repetitions each. Each run
# reuses its own P5 V19LS checkpoint for the decisions BEFORE the day-end point (identical requests; the
# guard refuses any identity mismatch), so new calls go only to the day-end decision (first answer + the
# re-plan after the review) and the next decisions (next day breakfast and the one after it).
# The approval is enforced by the batch guard on the charged upper bound with one worker (one reservation
# outstanding at a time); per-job caps are runaway stops and count worst-case reservations, not cost.
SEED_BATCH = None
V19D = dict(max_calls=16, max_usd=0.05, pools=dict(D=16))
# (pid, scenario, cutoff, P5 decisions before the cutoff per rep); +3 decisions after them: day end (first answer
# and, if reviewed, its re-plan), next-day breakfast, the decision after it -> at most 4 new calls per run.
V19D_CASES = [('A07', 'couple', '2026-11-05_2128', {1: 3, 2: 3}), ('A05', None, '2026-11-07_2129', {1: 3, 2: 4})]


def plan_v19d():
    jobs = []
    for pid, sc, cutoff, seeds in V19D_CASES:
        for rep in (1, 2):
            extra = ['--arrival', '16:30', '--visit-conditions', json.dumps(SCENARIOS[sc])] if sc else []
            jobs.append(dict(id='D_%s_V19LS_r%d' % (pid, rep), exp='D', pid=pid, policy='V19LS', rep=rep, scenario=sc,
                             max_calls=4, max_usd=0.06, seed=dict(job='B_%s_V19LS_r%d' % (pid, rep), before=cutoff),
                             args=['--case', 'pid:%s' % pid, '--e2e-policy', FINAL_POL['V19LS'], '--e2e-max-decisions', str(seeds[rep] + 3)] + extra))
    assert sum(j['max_calls'] for j in jobs) <= V19D['max_calls']
    return jobs


def plan_v19d_cont():
    """Offline continuation of the v19d runs to the end of the visit: every finished call of the v19d batch is
    reused (identity-checked), the decisions after it get the schema-valid synthetic answer (no provider), so
    the next-day breakfast, the rest of the stay and the checkout can be checked without a new call.
    Reported separately from the LIVE part (decision owners show OFFLINE_SYNTHETIC calls as such)."""
    jobs = []
    for j in plan_v19d():
        a = list(j['args']); a[a.index('--e2e-max-decisions') + 1] = '40'
        jobs.append(dict(j, id=j['id'], exp='D', max_calls=40, args=a, seed=dict(job=j['id'], before='9999-99-99_9999')))
    return jobs



# 2026-11-07 A05 follow-up (approval in the user's directive: at most 4 new calls, US$0.05 -> US$0.02): the
# V19LS meal-quantity display (party_fit, portion-shortfall flag) at A05's first dinner decision, and the
# partly included breakfast (2 of 3 diners covered by the room contract) at the next morning's breakfast.
# Dinner: a fresh visit stopped after its first model decision (1 call each). Breakfast: the evening before
# is taken from an OFFLINE synthetic run of the same code (plan v19e-seed, no provider; identity-checked
# reuse), so the only new call is the breakfast decision itself (1 call each). Reported as such.
V19E = dict(max_calls=4, max_usd=0.02, pools=dict(E=4))


def plan_v19e_seed():
    return [dict(id='S_A05_V19LS', exp='E', pid='A05', policy='V19LS', rep=0, max_calls=40,
                 args=['--case', 'pid:A05', '--e2e-policy', FINAL_POL['V19LS'], '--e2e-max-decisions', '20'])]


def plan_v19e():
    jobs = []
    for rep in (1, 2):
        jobs.append(dict(id='E_A05_dinner_r%d' % rep, exp='E', pid='A05', policy='V19LS', rep=rep, max_calls=1, max_usd=0.02,
                         args=['--case', 'pid:A05', '--e2e-policy', FINAL_POL['V19LS'], '--e2e-max-decisions', '1']))
    for rep in (1, 2):
        jobs.append(dict(id='E_A05_breakfast_r%d' % rep, exp='E', pid='A05', policy='V19LS', rep=rep, max_calls=1, max_usd=0.02,
                         seed=dict(job='S_A05_V19LS', before='2026-11-08_0800'),
                         args=['--case', 'pid:A05', '--e2e-policy', FINAL_POL['V19LS'], '--e2e-max-decisions', 'SEEDS+1']))
    assert sum(j['max_calls'] for j in jobs) <= V19E['max_calls']
    return jobs


KEY_TIME = re.compile(r'_(\d{4}-\d{2}-\d{2})_(\d{4})_')


def seed_checkpoint(job, seed_batch, run_dir):
    """Copy the finished P5 calls of this run that are strictly before the cutoff (request + response only;
    never run_state, errors or in-flight records). Returns the copied keys."""
    if not job.get('seed') or not seed_batch: return []
    src = os.path.join(seed_batch, 'runs', job['seed']['job'], 'calls'); dst = G.secure_dir(os.path.join(run_dir, 'calls'))
    if os.listdir(dst): return []   # resumed run: keep what is there
    cut = job['seed']['before']; copied = []
    for name in sorted(os.listdir(src)):
        if not name.endswith('.response.json'): continue
        key = name[:-len('.response.json')]; m = KEY_TIME.search(key)
        if not m or '%s_%s' % m.groups() >= cut: continue
        for kind in ('request', 'response'):
            shutil.copyfile(os.path.join(src, '%s.%s.json' % (key, kind)), os.path.join(dst, '%s.%s.json' % (key, kind)))
            os.chmod(os.path.join(dst, '%s.%s.json' % (key, kind)), 0o600)
        copied.append(key)
    return copied


def ledger_room():
    path = os.environ.get('HILLINK_AGENT_BUDGET_FILE')
    if not path: return None
    r = json.load(open(path, encoding='utf-8'))['requests']
    used = sum(x.get('charged_upper_usd', x['reserved_usd']) for x in r)
    return dict(calls=len(r), used_usd=round(used, 6), unresolved=sum(x.get('state') == 'RESERVED' for x in r),
                room_calls=int(os.environ.get('HILLINK_AGENT_MAX_CALLS', '2500')) - len(r), room_usd=round(float(os.environ.get('HILLINK_AGENT_MAX_USD', '20')) - used, 6))


LOCK = threading.Lock()


def write_status(batch_dir, status):
    with LOCK:
        G.write_private(os.path.join(batch_dir, 'batch_status.json'), status)


def run_job(job, batch_dir, shadow, status):
    run_dir = os.path.join(batch_dir, 'runs', job['id'])
    if job.get('seed'): G.secure_dir(run_dir); job['seeded'] = seed_checkpoint(job, SEED_BATCH, run_dir) or job.get('seeded')
    if 'SEEDS+1' in job['args']:
        n = sum(1 for f in os.listdir(os.path.join(run_dir, 'calls')) if f.endswith('_a1.response.json'))
        if not n: raise SystemExit('%s: no seeded decisions; refusing to run' % job['id'])
        job['args'] = [str(n + 1) if x == 'SEEDS+1' else x for x in job['args']]
    cmd = [sys.executable, str(ROOT / 'tools/v18_bench/run.py')] + job['args'] + ['--shadow', shadow, '--run-dir', run_dir]
    if shadow == 'live': cmd += ['--max-calls', str(job['max_calls']), '--max-usd', str(job['max_usd']), '--yes']
    env = dict(os.environ, HL_BATCH_DIR=batch_dir, HL_BATCH_POOL=job['exp'], HL_BATCH_JOB=job['id'], **(job.get('env') or {}))
    if shadow == 'live': env['HILLINK_V18_BENCH_LIVE'] = '1'
    begin = time.time()
    with open(run_dir + '.console.txt', 'a', encoding='utf-8') as log:
        os.chmod(run_dir + '.console.txt', 0o600)
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT)).returncode
    summary = None
    try: summary = json.load(open(os.path.join(run_dir, 'run_summary.json'), encoding='utf-8'))
    except (OSError, ValueError): pass
    st = (summary or {}).get('run_state') or {}
    rec = dict(rc=rc, seconds=round(time.time() - begin, 1), calls_started=st.get('calls_started'), settled_upper_usd=st.get('settled_upper_usd'),
               blocked=[b.get('reason') for b in st.get('blocked') or []], error=(summary or {}).get('error'), code=(summary or {}).get('code'),
               done=rc == 0 and summary is not None and not st.get('blocked'),
               seeded_calls=len(job.get('seeded') or []), reused=st.get('reused'),
               e2e=(summary or {}).get('e2e') and {k: summary['e2e'][k] for k in ('completed', 'spent_krw', 'ordered_total_krw', 'ledger_matches_orders', 'last_action')})
    with LOCK:
        status['jobs'][job['id']] = rec
    try: status['batch_guard'] = json.load(open(os.path.join(batch_dir, 'batch_guard.json'), encoding='utf-8'))
    except (OSError, ValueError): pass
    status['batch_guard'] = {k: v for k, v in (status.get('batch_guard') or {}).items() if k != 'entries'}
    write_status(batch_dir, status)
    print('[%s] %s rc=%d calls=%s $%s %s%s' % (time.strftime('%H:%M:%S'), job['id'], rc, rec['calls_started'], rec['settled_upper_usd'],
                                              'done' if rec['done'] else 'NOT DONE', (' blocked=%s' % rec['blocked']) if rec['blocked'] else ''), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['plan', 'run'])
    ap.add_argument('--batch-dir'); ap.add_argument('--shadow', choices=['offline', 'live'], default='offline')
    ap.add_argument('--workers', type=int, default=2); ap.add_argument('--only', default='A,B,C')
    ap.add_argument('--limit', type=int, default=None, help='first N jobs only (tests)')
    ap.add_argument('--plan', choices=['cross', 'final', 'v19', 'v19d', 'v19d-cont', 'v19e-seed', 'v19e'], default='cross')
    ap.add_argument('--seed-batch', default=None, help='v19d: the P5 batch folder whose checkpoints are reused before the cutoff')
    args = ap.parse_args()
    global SEED_BATCH
    SEED_BATCH = os.path.abspath(os.path.expanduser(args.seed_batch)) if args.seed_batch else None
    if args.plan in ('v19d-cont', 'v19e-seed') and args.shadow != 'offline': sys.exit(args.plan + ' is offline only')
    if args.plan == 'v19e' and args.cmd == 'run' and not SEED_BATCH: sys.exit('v19e needs --seed-batch (the v19e-seed folder)')
    if args.plan == 'v19e' and args.cmd == 'run' and args.workers != 1: sys.exit('v19e runs with --workers 1')
    if args.plan in ('v19d', 'v19d-cont') and args.cmd == 'run' and not SEED_BATCH: sys.exit('v19d needs --seed-batch (the P5 batch folder)')
    if args.plan == 'v19d' and args.cmd == 'run' and args.workers != 1: sys.exit('v19d runs with --workers 1 (one reservation at a time)')
    jobs = plan_v19e() if args.plan == 'v19e' else plan_v19e_seed() if args.plan == 'v19e-seed' else plan_v19d() if args.plan == 'v19d' else plan_v19d_cont() if args.plan == 'v19d-cont' else plan_final() if args.plan == 'final' else plan_v19() if args.plan == 'v19' else [j for j in plan() if j['exp'] in args.only.split(',')]
    jobs = jobs[:args.limit]
    if args.cmd == 'plan':
        for j in jobs: print(j['id'], j['exp'], j['max_calls'], j['max_usd'], ' '.join(j['args']))
        print('jobs', len(jobs), 'sum of per-job USD caps', round(sum(j['max_usd'] for j in jobs), 3)); return
    if not 1 <= args.workers <= 3: sys.exit('workers must be 1..3')
    batch_dir = os.path.abspath(os.path.expanduser(args.batch_dir)); os.umask(0o077)
    G.secure_dir(batch_dir); G.secure_dir(os.path.join(batch_dir, 'runs'))
    max_calls, max_usd = (V19E['max_calls'], V19E['max_usd']) if args.plan == 'v19e' else (160, 999.0) if args.plan in ('v19d-cont', 'v19e-seed') else (V19D['max_calls'], V19D['max_usd']) if args.plan == 'v19d' else (FINAL['max_calls'], FINAL['max_usd']) if args.plan == 'final' else (V19['max_calls'], V19['max_usd']) if args.plan == 'v19' else (BATCH_MAX_CALLS, BATCH_MAX_USD)
    pools = V19E['pools'] if args.plan == 'v19e' else dict(E=160) if args.plan == 'v19e-seed' else dict(D=160) if args.plan == 'v19d-cont' else V19D['pools'] if args.plan == 'v19d' else FINAL['pools'] if args.plan == 'final' else V19['pools'] if args.plan == 'v19' else POOLS
    room = ledger_room() if args.shadow == 'live' else None
    if room:
        if room['unresolved']: sys.exit('shared ledger has unresolved calls: %s' % room)
        max_calls, max_usd = min(max_calls, room['room_calls']), min(max_usd, room['room_usd'])
    gs = G.BatchGuard.init(batch_dir, max_calls, max_usd, pools)
    status_path = os.path.join(batch_dir, 'batch_status.json')
    status = json.load(open(status_path, encoding='utf-8')) if os.path.exists(status_path) else dict(started_at=time.strftime('%Y-%m-%d %H:%M:%S'), shadow=args.shadow, jobs={})
    if status.get('shadow') != args.shadow: sys.exit('batch folder was started as %s' % status.get('shadow'))
    status.update(ledger_at_start=status.get('ledger_at_start') or room, caps=dict(calls=gs['max_calls'], usd=gs['max_usd'], pools=pools), plan=[j['id'] for j in jobs])
    write_status(batch_dir, status)
    todo = [j for j in jobs if not (status['jobs'].get(j['id']) or {}).get('done')]
    print('batch %s · %s · %d jobs (%d to run) · cap %d calls / $%.2f · pools %s · workers %d' % (batch_dir, args.shadow, len(jobs), len(todo), gs['max_calls'], gs['max_usd'], pools, args.workers), flush=True)
    # the representative full visits go first and alone-ish: they are submitted first, the pool keeps order
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(lambda j: run_job(j, batch_dir, args.shadow, status), todo))
    g = json.load(open(os.path.join(batch_dir, 'batch_guard.json'), encoding='utf-8'))
    status['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S'); status['ledger_at_end'] = ledger_room() if args.shadow == 'live' else None
    write_status(batch_dir, status)
    print('batch end · calls %d · reserved/charged upper $%.4f · pools %s' % (g['calls'], g['reserved_usd'], {k: v['calls'] for k, v in g['pools'].items()}), flush=True)


if __name__ == '__main__':
    main()
