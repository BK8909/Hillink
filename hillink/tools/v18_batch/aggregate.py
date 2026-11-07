"""Aggregate a V18 batch folder (tools/v18_batch/batch.py) into one private and one public summary.

  python3 tools/v18_batch/aggregate.py --batch-dir <private batch dir> --out-private <file> --out-public <file>

private: every sample with the model's own reason text, for the blind human review (stays on the Mac).
public:  the same samples without any request/response text — choices, totals, Fact ids, check labels,
         latency/tokens/cost — plus per-policy and per-customer aggregates. Labels computed here are
         mechanical (no model is called): cheapest-marked option as C shows it, occasion words in the
         reason, cited Facts that are the option's own experience links, validation result.
"""
import argparse, glob, json, os, random, re, statistics as st, sys
from collections import Counter, defaultdict

LET = {'LLM_AUTONOMOUS_CUSTOMER_V18BM': 'C', 'LLM_AUTONOMOUS_CUSTOMER_V18L2': 'L2', 'LLM_AUTONOMOUS_CUSTOMER_V18S2': 'S2', 'LLM_AUTONOMOUS_CUSTOMER_V18LS': 'LS', 'LLM_AUTONOMOUS_CUSTOMER_V19LS': 'V19LS'}
OCCASION_RX = r'기념|anniversary'
SOLO_RX = r'혼자|1인|한 사람|홀로|단독'


def load(p):
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return None


_INDEX = {}
REQUESTS_FROM = None   # an offline batch folder with the same plan: its request files are used when the LIVE one is not at hand


def ctx_of(run_dir, key, expect_sha=None):
    r = load(os.path.join(run_dir, 'calls', key + '.request.json'))
    if not r and REQUESTS_FROM and expect_sha:
        if not _INDEX:
            for f in glob.glob(os.path.join(REQUESTS_FROM, 'runs', '*', 'calls', '*.request.json')):
                x = load(f)
                if x: _INDEX.setdefault(x.get('input_sha256'), f)
        r = load(_INDEX[expect_sha]) if expect_sha in _INDEX else None   # only an identical request (same SHA) may stand in
    if not r: return None
    c = {}
    for m in r['request_body']['input'][1:]:
        try: c.update(json.loads(m['content']))
        except ValueError: pass
    return c


def options(ctx):
    return {o['basket_id']: o for x in (ctx or {}).get('candidates', []) for g in x.get('basket_groups') or [] for o in g['options']}


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    k = (len(xs) - 1) * q; f = int(k); c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 2)


def stats(xs):
    xs = [x for x in xs if x is not None]
    return dict(n=len(xs), mean=round(st.mean(xs), 2) if xs else None, median=pct(xs, .5), p90=pct(xs, .9), max=max(xs) if xs else None)


def point_samples(job, run_dir, status):
    out = []
    bench = os.path.join(run_dir, 'bench.jsonl')
    if not os.path.exists(bench): return out
    for line in open(bench, encoding='utf-8'):
        p = json.loads(line)
        c_first = next(((v.get('attempts') or [{}])[0] for v in p['variants'] if LET.get(v['policy']) == 'C'), {})
        c_key = c_first.get('call_key')
        c_ctx = ctx_of(run_dir, c_key, c_first.get('provider_input_sha256')) if c_key else None
        c_opts = options(c_ctx)
        marks_source = 'LIVE_REQUEST' if c_key and os.path.exists(os.path.join(run_dir, 'calls', c_key + '.request.json')) else ('IDENTICAL_OFFLINE_REQUEST' if c_ctx else None)
        cheapest = {b for b, o in c_opts.items() if '최저가(인원 충족)' in (o.get('marks') or [])}
        for v in p['variants']:
            pol = LET.get(v['policy'], v['policy'])
            atts = v.get('attempts') or []
            last = atts[-1] if atts else {}
            ans = last.get('answer') or {}
            plan = last.get('plan') or {}
            basket = plan.get('selected_basket_id')
            o = c_opts.get(basket) or {}
            reason = ' '.join(str(x) for x in (ans.get('reason'), (ans.get('rejected_alternative') or {}).get('reason')) if x)
            cited = (plan.get('supporting_fact_ids') or []) + (plan.get('counterevidence_fact_ids') or [])
            out.append(dict(
                job=job['id'], exp=job['exp'], pid=job['pid'], tier=job['tier'], scenario=job.get('scenario'), rep=job.get('rep'),
                point='%s %s' % (p['date'], p['time']), point_type=None, policy=pol,
                status='OK' if last.get('validation') == 'PASS' else ('ERROR' if last.get('error') else ('BLOCKED' if last.get('blocked') else 'INVALID')),
                error=last.get('error') or last.get('blocked'), first_try_pass=bool(atts) and atts[0].get('validation') == 'PASS', attempts=len(atts),
                selected=plan.get('action_id') or ans.get('selected_action_id'), basket=basket,
                basket_label=' + '.join('%s x%s' % (i.get('label'), i.get('quantity')) for i in o.get('items', [])) or None,
                total_krw=plan.get('order_total_krw'), cheapest_marked_in_C=(basket in cheapest) if basket and c_opts else None, marks_source=marks_source,
                option_experience_fact_ids=o.get('experience_fact_ids') or [], cited=cited, counter=plan.get('counterevidence_fact_ids') or [],
                cites_option_experience=bool(set(cited) & set(o.get('experience_fact_ids') or [])) if basket else None,
                compared=(ans.get('rejected_alternative') or {}).get('action_id'), need=(ans.get('current_need_assessment') or {}).get('state'),
                expected_satiety=(ans.get('meal_assessment') or {}).get('expected_satiety'), diners=(ans.get('meal_assessment') or {}).get('modeled_diners'),
                occasion_word=bool(re.search(OCCASION_RX, reason)), solo_word=bool(re.search(SOLO_RX, reason)),
                seconds=sum(a.get('seconds') or 0 for a in atts if a.get('seconds')) or None,
                reasoning_tokens=sum(a.get('reasoning_tokens') or 0 for a in atts), output_tokens=sum(a.get('output_tokens') or 0 for a in atts),
                input_tokens=sum(a.get('input_tokens') or 0 for a in atts), cost_upper_usd=round(sum(a.get('cost_upper_usd') or 0 for a in atts), 6),
                provider_input_sha256=(atts[0] if atts else {}).get('provider_input_sha256'), shortlist=[r['action_id'] for r in p.get('shortlist') or []],
                _reason=ans.get('reason'), _alt_reason=(ans.get('rejected_alternative') or {}).get('reason'), _sharing=(ans.get('meal_assessment') or {}).get('sharing_plan')))
    # point type by order within the job: first = dinner (A: dinner_after / B: first decision), second = after dinner
    seen = {}
    for s in out:
        seen.setdefault(s['point'], len(seen))
        s['point_type'] = 'dinner' if seen[s['point']] == 0 else 'after_dinner'
    return out


def e2e_visit(job, run_dir, status):
    sm = load(os.path.join(run_dir, 'run_summary.json')) or {}
    e = sm.get('e2e') or {}
    calls = [json.loads(l) for l in open(os.path.join(run_dir, 'e2e_calls.jsonl'), encoding='utf-8')] if os.path.exists(os.path.join(run_dir, 'e2e_calls.jsonl')) else []
    errs = [os.path.basename(f) for f in glob.glob(os.path.join(run_dir, 'calls', '*.error.json'))]
    st_ = sm.get('run_state') or {}
    blocked = [b.get('reason') for b in st_.get('blocked') or []]
    decs = e.get('decisions') or []
    # a visit counts as complete only when every decision was made and executed by the policy, nothing was
    # blocked by a cap and no provider error stopped a decision (the engine's own 'completed' flag is not enough)
    done = bool(e.get('completed')) and not blocked and not errs and bool(decs) and all(d.get('action') and d.get('state') == 'EXECUTED' for d in decs)
    return dict(job=job['id'], pid=job['pid'], tier=job['tier'], policy=job['policy'], completed=done, partial=not done, engine_completed_flag=bool(e.get('completed')),
                error=sm.get('error'), code=sm.get('code'), fallback_reason=e.get('fallback_reason'), calls=st_.get('calls_started'), errors=len(errs),
                blocked=blocked, replans=sum(1 for c in calls if c.get('retry')),
                cost_upper_usd=st_.get('settled_upper_usd'), seconds=round(sum(c.get('seconds') or 0 for c in calls), 1),
                reasoning_tokens=sum(c.get('reasoning_tokens') or 0 for c in calls),
                spent_krw=e.get('spent_krw'), ordered_total_krw=e.get('ordered_total_krw'), ledger_matches_orders=e.get('ledger_matches_orders'),
                meals=e.get('meals'), meal_log=e.get('meal_log'), fatigue_end=e.get('fatigue_end'),
                decisions=[dict(d, facts=d.get('facts')) for d in e.get('decisions') or []],
                _answers=[dict(time=c.get('time'), date=c.get('date'), purpose=c.get('purpose'), retry=c.get('retry'), reason=(c.get('answer') or {}).get('reason'),
                               alt=(c.get('answer') or {}).get('rejected_alternative'), selected=(c.get('answer') or {}).get('selected_action_id'),
                               basket=(c.get('answer') or {}).get('selected_basket_id')) for c in calls])


def aggregate(samples, visits):
    out = {}
    for pol in ('C', 'L2', 'S2'):
        xs = [s for s in samples if s['policy'] == pol]
        ok = [s for s in xs if s['status'] == 'OK']
        meal = [s for s in ok if s['point_type'] == 'dinner']
        out[pol] = dict(samples=len(xs), ok=len(ok), errors=sum(s['status'] == 'ERROR' for s in xs), blocked=sum(s['status'] == 'BLOCKED' for s in xs),
                        invalid=sum(s['status'] == 'INVALID' for s in xs),
                        first_try_pass_rate=round(sum(s['first_try_pass'] for s in xs) / len(xs), 3) if xs else None,
                        replan_rate=round(sum(s['attempts'] > 1 for s in xs) / len(xs), 3) if xs else None,
                        seconds=stats([s['seconds'] for s in ok]), reasoning_tokens=stats([s['reasoning_tokens'] for s in ok]),
                        cost_upper_usd=round(sum(s['cost_upper_usd'] for s in xs), 6),
                        dinner=dict(n=len(meal), cheapest_marked_in_C=sum(bool(s['cheapest_marked_in_C']) for s in meal),
                                    cites_option_experience=sum(bool(s['cites_option_experience']) for s in meal),
                                    no_fact_cited=sum(not s['cited'] for s in meal), totals=stats([s['total_krw'] for s in meal]),
                                    venues=dict(Counter(s['selected'] for s in meal))),
                        e2e=dict(visits=sum(v['policy'] == pol for v in visits), completed=sum(v['completed'] for v in visits if v['policy'] == pol),
                                 ledger_matches=sum(bool(v['ledger_matches_orders']) for v in visits if v['policy'] == pol),
                                 spent_krw=[v['spent_krw'] for v in visits if v['policy'] == pol]))
    by_group = defaultdict(lambda: defaultdict(list))
    for s in samples:
        if s['status'] != 'OK': continue
        g = '%s|%s|%s|%s' % (s['exp'], s['pid'], s['scenario'] or 'base', s['point_type'])
        by_group[g][s['policy']].append('%s%s' % (s['selected'], (' ' + s['basket_label']) if s['basket_label'] else ''))
    dist = {g: {p: dict(Counter(v)) for p, v in d.items()} for g, d in sorted(by_group.items())}
    return out, dist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--requests-from', default=None, help='offline batch folder of the same plan (request files, used only when SHA-identical)')
    ap.add_argument('--batch-dir', required=True); ap.add_argument('--out-private', required=True); ap.add_argument('--out-public', required=True)
    args = ap.parse_args()
    global REQUESTS_FROM; REQUESTS_FROM = args.requests_from
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import batch as BT
    jobs = {j['id']: j for j in BT.plan()}
    status = load(os.path.join(args.batch_dir, 'batch_status.json')) or {}
    guard = load(os.path.join(args.batch_dir, 'batch_guard.json')) or {}
    samples, visits = [], []
    for jid, job in jobs.items():
        rd = os.path.join(args.batch_dir, 'runs', jid)
        if not os.path.isdir(rd): continue
        if job['exp'] == 'C': visits.append(e2e_visit(job, rd, status))
        else: samples.extend(point_samples(job, rd, status))
    agg, dist = aggregate(samples, visits)
    random.seed(1106)
    blind = list(range(len(samples))); random.shuffle(blind)
    for i, j in enumerate(blind): samples[j]['blind_id'] = 'S%03d' % (i + 1)
    entries = (guard.get('entries') or {}).values()
    run = dict(batch_dir=os.path.basename(os.path.normpath(args.batch_dir)), shadow=status.get('shadow'), started_at=status.get('started_at'), finished_at=status.get('finished_at'),
               ledger_at_start=status.get('ledger_at_start'), ledger_at_end=status.get('ledger_at_end'),
               guard=dict(calls=guard.get('calls'), reserved_usd=guard.get('reserved_usd'), pools={k: v.get('calls') for k, v in (guard.get('pools') or {}).items()},
                          states=dict(Counter(e['state'] for e in entries))),
               jobs=dict(total=len(jobs), started=sum(1 for j in jobs if os.path.isdir(os.path.join(args.batch_dir, 'runs', j))),
                         done=sum(1 for v in (status.get('jobs') or {}).values() if v.get('done'))))
    priv = dict(run=run, aggregate=agg, distribution=dist, samples=samples, visits=visits)
    pub = dict(note='De-identified V18 batch summary. No request/response text; reasons and raw answers stay in the private batch folder.',
               run=run, aggregate=agg, distribution=dist,
               samples=[{k: v for k, v in s.items() if not k.startswith('_')} for s in samples],
               visits=[{k: v for k, v in x.items() if not k.startswith('_')} for x in visits])
    for path, val in ((args.out_private, priv), (args.out_public, pub)):
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(val, f, ensure_ascii=False, indent=1, default=str)
        os.chmod(tmp, 0o600); os.replace(tmp, path)
    print(json.dumps(dict(run=run, aggregate={p: {k: a[k] for k in ('samples', 'ok', 'errors', 'first_try_pass_rate')} for p, a in agg.items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()
