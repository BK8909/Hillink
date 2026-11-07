"""V18 question-design bench (A/B/C/D) at fixed decision points with identical candidates.

  python3 tools/v18_bench/run.py --case a07 --targets "2026-11-05 19:35" --run-dir <private dir> [--shadow live --max-calls 8 --max-usd 0.20]

The run directory holds the raw requests and responses and the HTML report; it must be outside the
git repository (it is refused otherwise). A live run needs --max-calls and --max-usd: hard caps for
THIS run, checked before every call (the shared ledger keeps applying on top), and an explicit
confirmation that shows the scope and the ledger. A restart with the same --run-dir reuses finished
calls and never re-sends an interrupted one unless --retry-interrupted is given.

Cases (fixed; see CASES): A07 replays the choices of the V17 LIVE run (2026-11-05, 9034) as a
script; N03 replays its stored V16 baseline answers. The trajectory never depends on the shadow
answers. --shadow live calls the provider for every variant at every target point (plus at most
one replan per variant when the validator rejects); it refuses to start unless the product's
LIVE settings pass and HILLINK_V18_BENCH_LIVE=1 is set explicitly. Offline needs no key.
"""
import argparse, gzip, json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard as G  # noqa: E402
VARIANTS = ['LLM_AUTONOMOUS_CUSTOMER_V18', 'LLM_AUTONOMOUS_CUSTOMER_V18B', 'LLM_AUTONOMOUS_CUSTOMER_V18BM', 'LLM_AUTONOMOUS_CUSTOMER_V18BD']
A07_V17_LIVE = [   # recorded V17 LIVE choices (handover/profile45_review/live_quality_1105/보고서.md §21) and the alternatives it named
    dict(expect='17:51', action='meal:PIZZA_HILL', basket_label='콤비네이션 피자 L', note='피자힐 콤비네이션 L 2인 나눔',
         alternatives=[dict(action='meal:MYONGWOLGWAN'), dict(action='meal:ROOM_MEAL')]),
    dict(expect='19:35', action_contains='night_footbath', note='스카이야드 야간 족욕',
         alternatives=[dict(action_contains='activity:pool'), dict(action='room_rest')]),
    dict(expect='20:29', action='room_rest', note='객실 휴식 60분(일정 유지)', alternatives=[dict(action='library'), dict(action='end_day_in_room')]),
    dict(expect='21:32', action='end_day_in_room', note='오늘 종료', alternatives=[dict(action='meal:ROOM_MEAL'), dict(action='room_rest')]),
    dict(expect='08:10', action='BREAKFAST_BUFFET', note='포함 조식', alternatives=[dict(action='SKIP_BREAKFAST')]),
    dict(expect='09:13', action='library', note='라이브러리', alternatives=[dict(action='garden_walk'), dict(action='room_rest')]),
    dict(expect='10:53', action='leave_visit', note='귀가', alternatives=[dict(action='garden_walk'), dict(action='meal:THE_PAVILION', basket_label='치즈버거')]),
]
CASES = {
    'a07': dict(pid='A07', tag='A07-v16-baseline', main='script', policy='LLM_AUTONOMOUS_CUSTOMER_V17', script=A07_V17_LIVE,
                targets=['2026-11-05 17:51', '2026-11-05 19:35', '2026-11-05 20:29', '2026-11-05 21:32', '2026-11-06 10:53']),
    'n03': dict(pid='N03', tag='N03-v16-baseline', main='replay', policy='LLM_AUTONOMOUS_CUSTOMER_V16', script=None, targets=None, max_points=4),
}


def case_of(name):
    """A fixed case, or any stored V16 baseline as 'pid:<PID>' (its saved answers drive the trajectory)."""
    if name in CASES: return CASES[name]
    if name.startswith('pid:'):
        pid = name[4:]
        return dict(pid=pid, tag='%s-v16-baseline' % pid, main='replay', policy='LLM_AUTONOMOUS_CUSTOMER_V16', script=None, targets=None, max_points=4)
    raise SystemExit('unknown case %s (use %s or pid:<PID>)' % (name, ', '.join(sorted(CASES))))


def dinner_and_after(decs):
    """The first-day dinner decision (the first decision at or after 16:30 on the first date whose stored
    choice is a meal) and the decision right after it — the same decision TYPES for every customer,
    at each customer's own time."""
    first = decs[0]['date']
    times = [(d['date'], d['minute'], (d.get('selected_plan') or {}).get('action_id', '')) for d in decs if d.get('phase') != 'breakfast']
    i = next((k for k, (dt, m, act) in enumerate(times) if dt == first and m >= 16 * 60 + 30 and act.startswith('meal:')), None)
    if i is None: raise SystemExit('NO_FIRST_DAY_DINNER_DECISION')
    return ['%s %02d:%02d' % (dt, m // 60, m % 60) for dt, m, _ in times[i:i + 2]]


def git_top():
    import subprocess
    try: return Path(subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()).resolve()
    except Exception: return ROOT.parent.resolve()


def request_diff_summary(run_dir, out):
    """Per point: candidate hash per variant and the field-level A/B, B/C, B/D verdicts of the first
    attempts' actual request bodies (field paths and sizes only, no request text)."""
    import request_diff as RD
    letters = dict(zip(VARIANTS, 'ABCD'), LLM_AUTONOMOUS_CUSTOMER_V18N='N', LLM_AUTONOMOUS_CUSTOMER_V18L='L', LLM_AUTONOMOUS_CUSTOMER_V18S='S', LLM_AUTONOMOUS_CUSTOMER_V18P='P', LLM_AUTONOMOUS_CUSTOMER_V18L2='L2', LLM_AUTONOMOUS_CUSTOMER_V18M='M', LLM_AUTONOMOUS_CUSTOMER_V18S2='S2', LLM_AUTONOMOUS_CUSTOMER_V18LS='LS', LLM_AUTONOMOUS_CUSTOMER_V19LS='V19LS')
    res = []
    if not out.exists(): return res
    for line in open(out, encoding='utf-8'):
        p = json.loads(line); bodies = {}; hashes = {}
        for v in p.get('variants', []):
            first = (v.get('attempts') or [{}])[0]
            hashes[letters.get(v['policy'], v['policy'])] = v.get('candidates_sha256')
            req = run_dir / 'calls' / ('%s.request.json' % first.get('call_key'))
            if first.get('call_key') and req.exists():
                r = json.load(open(req, encoding='utf-8')); bodies[letters.get(v['policy'], v['policy'])] = r['request_body']
        pairs = RD.compare_all(bodies)
        lean = RD.compare_lean(bodies['C'], bodies['L']) if 'C' in bodies and 'L' in bodies else None
        neutral = RD.compare_lean(bodies['C'], bodies['S'], 'C<->S', ordered=False) if 'C' in bodies and 'S' in bodies else None
        neutral2 = None
        if 'C' in bodies and 'S2' in bodies:
            from operator_choice.autonomy_v1 import autonomous_agent as AA
            neutral2 = dict(preservation=RD.compare_lean(bodies['C'], bodies['S2'], 'C<->S2', ordered=False),
                            exact=RD.compare_transformed(bodies['C'], bodies['S2'], lambda c: AA.neutral_presentation(c, 'NAME'), 'C<->S2',
                                                         'S2 요청 = C 요청에 중립 제시(이름순·점수/가격 사유 중립화) 적용 + 시스템 문장 1줄'))
        ls = None
        if 'LS' in bodies:
            from operator_choice.autonomy_v1 import autonomous_agent as AA
            ls = dict(vs_L2=RD.compare_transformed(bodies['L2'], bodies['LS'], lambda c: AA.neutral_presentation(c, 'NAME'), 'L2<->LS',
                                                   'LS 요청 = L2 요청에 중립 제시(이름순·점수/가격 사유 중립화) 적용 + 시스템 문장 1줄') if 'L2' in bodies else None,
                      vs_S2=RD.compare_evidence_superset(bodies['S2'], bodies['LS']) if 'S2' in bodies else None)
        unsent = {letters.get(v['policy'], v['policy']): v.get('venue_records_unsent') for v in p.get('variants', [])}
        res.append(dict(point='%s %s %s' % (p['pid'], p['date'], p['time']), candidates_sha256=hashes, ls=ls, venue_records_unsent=unsent,
                        candidates_identical=len(set(hashes.values())) == 1,
                        pairs=[dict(pair=x['pair'], verdict=x['verdict'], differing_paths=[d['path'] for d in x['differences']],
                                    unexpected=[d['path'] for d in x['unexpected']], structure_differences=x['structure_differences']) for x in pairs],
                        lean_vs_c=lean, neutral_vs_c=neutral, neutral2_vs_c=neutral2))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True, help='a07, n03 or pid:<PID> (any stored V16 baseline)')
    ap.add_argument('--points', choices=['dinner_after', 'first_decision'], default=None,
                    help='dinner_after: the stored run\'s first-day dinner decision and the next one; first_decision: the first decision of this (possibly changed) scenario, then stop')
    ap.add_argument('--visit-conditions', default=None, help='JSON merged into this customer\'s visit_conditions (operator scenario)')
    ap.add_argument('--arrival', default=None, help='arrival time HH:MM (operator scenario)')
    ap.add_argument('--stop-after-targets', action='store_true', help='end the visit after the last target (needed when the scenario changed and stored answers no longer apply)')
    ap.add_argument('--e2e-max-decisions', type=int, default=None, help='full-visit LIVE: stop after this many model decisions (replans not counted)')
    ap.add_argument('--e2e-policy', default=None, help='full-visit LIVE: this V18 policy chooses every action and its choices are executed')
    ap.add_argument('--shadow', choices=('offline', 'live'), default='offline')
    ap.add_argument('--variants', default=','.join(VARIANTS))
    ap.add_argument('--targets', default=None, help='comma list of "YYYY-MM-DD HH:MM" (default: the case targets)')
    ap.add_argument('--run-dir', default=None, help='private folder outside the repository (required for live)')
    ap.add_argument('--max-calls', type=int, default=None, help='hard cap on new provider calls in this run (required for live)')
    ap.add_argument('--max-usd', type=float, default=None, help='hard cap on worst-case cost reserved by this run (required for live)')
    ap.add_argument('--offline-pick', default=None, help='(offline only) "HH:MM=action_id,..." forces the synthetic answer at that time, to exercise rejection and replan')
    ap.add_argument('--retry-interrupted', action='store_true', help='re-send calls that were interrupted or ended in a provider error')
    ap.add_argument('--yes', action='store_true', help='skip the interactive confirmation (the scope is still printed)')
    ap.add_argument('--out', default=None, help='(offline) point summaries; default <run-dir>/bench.jsonl')
    args = ap.parse_args()
    case = case_of(args.case)
    targets = args.targets.split(',') if args.targets else case['targets']
    e2e = args.e2e_policy
    if e2e:
        if args.targets or args.points or args.stop_after_targets: sys.exit('--e2e-policy runs the whole visit; no targets')
        args.variants = e2e; targets = None
    variants = args.variants.split(',')
    live = args.shadow == 'live'
    if live and (args.run_dir is None or args.max_calls is None or args.max_usd is None):
        sys.exit('A live run needs --run-dir, --max-calls and --max-usd.')
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else Path(tempfile.mkdtemp(prefix='hillink-v18-run-'))
    top = git_top()
    if run_dir == top or top in run_dir.parents:
        sys.exit('The run directory holds raw requests/responses and must be outside the git repository: %s' % run_dir)
    # private by construction: folders 0700, files 0600 (also for the visit subprocess, which inherits the umask)
    os.umask(0o077)
    if run_dir.exists():
        try: G.check_private_tree(str(run_dir))
        except G.Blocked as exc: sys.exit(str(exc))
    G.secure_dir(str(run_dir))
    max_calls = args.max_calls if args.max_calls is not None else 10 ** 6
    max_usd = args.max_usd if args.max_usd is not None else 10.0 ** 6
    if args.shadow == 'offline':
        sys.path.insert(0, str(ROOT / 'tools/offline_test_guard')); import sitecustomize  # noqa: F401
        # the visit runs in a subprocess: put the network guard on its path too
        os.environ['PYTHONPATH'] = str(ROOT / 'tools/offline_test_guard') + (os.pathsep + os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')
    sys.path.insert(0, str(ROOT / 'tools')); from bootstrap_data import bootstrap
    data = bootstrap()
    os.environ.update(HILLINK_AGENT_MODE='replay', HILLINK_LLM_ENABLED='0', HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_AUTONOMOUS_AGENT='1',
                      HILLINK_V12Z_COMMON='1', HILLINK_NATIVE_HYBRID='1', HILLINK_HYBRID='replay', HILLINK_ISOLATED_CUSTOMERS='1', HILLINK_REVIEWER_LOCAL='1',
                      HILLINK_ISOLATED_REGISTRY=data['path'], HILLINK_ISOLATED_REGISTRY_SHA256=data['sha256'])
    sys.path.insert(0, str(ROOT / 'timeline/viewer'))
    sys.path.insert(0, str(ROOT / 'timeline/experiments/persona_live'))
    import hotel_ledger  # noqa: F401
    import visit_run as V, saved_visits as S
    from operator_choice.autonomy_v1 import agent_provider as P
    ledger_before = None
    if live:
        if os.environ.get('HILLINK_V18_BENCH_LIVE') != '1':
            sys.exit('LIVE bench needs HILLINK_V18_BENCH_LIVE=1 (paid calls).')
        os.environ.update(HILLINK_LLM_EXTERNAL_OPT_IN='1')
        from visit_execution import live_status
        ok, reason = live_status()
        if not ok: sys.exit('LIVE not available: ' + str(reason))
        os.environ['HILLINK_LLM_EXTERNAL_OPT_IN'] = '0'   # the main trajectory stays offline; the driver opts in per shadow call
        ledger_before = P.configured_budget().summary()
        # in a batch, sibling workers' calls are in flight in the shared ledger; only those are tolerated
        sibling = 0
        bg = G.batch_guard()
        if bg is not None:
            with bg.locked() as bst: sibling = sum(1 for e in bst['entries'].values() if e['state'] == 'RESERVED')
        if ledger_before['unresolved'] > sibling or ledger_before['max_calls'] - ledger_before['calls'] < max_calls or ledger_before['max_usd'] - ledger_before['cost_upper_usd'] < max_usd:
            sys.exit('Shared ledger cannot cover this run: %s; this run caps at %d calls / $%.2f.' % (ledger_before, max_calls, max_usd))
        state = run_dir / 'run_state.json'
        print('== V18 bench LIVE ==')
        print('case %s · points %s · variants %s' % (args.case, targets, ', '.join(v.replace('LLM_AUTONOMOUS_CUSTOMER_', '') for v in variants)))
        print('run caps: at most %d new calls, at most $%.2f worst-case reserved (checked before every call)' % (max_calls, max_usd))
        print('shared ledger now: %d calls · $%.4f upper · caps %d calls / $%.2f · unresolved %d' % (ledger_before['calls'], ledger_before['cost_upper_usd'], ledger_before['max_calls'], ledger_before['max_usd'], ledger_before['unresolved']))
        if state.exists(): print('resuming run folder:', json.load(open(state)))
        print('model %s · effort default %s · run folder %s' % (os.environ.get('HILLINK_AGENT_MODEL', 'gpt-6-luna'), os.environ.get('HILLINK_AGENT_EFFORT', 'high'), run_dir))
        if not args.yes and input('Type RUN to start paid calls: ').strip() != 'RUN':
            sys.exit('Not started.')
    payload, row, _, _ = S.payload(case['tag'])
    request = dict(payload['request'], hybrid_policy=e2e or case['policy'])
    if args.visit_conditions:
        vc = dict((request.get('visit_conditions') or {}).get(case['pid']) or {}); vc.update(json.loads(args.visit_conditions))
        request['visit_conditions'] = dict(request.get('visit_conditions') or {}, **{case['pid']: vc})
    if args.arrival:
        request['environment'] = dict(request.get('environment') or {}, arrival_time=args.arrival)
    if args.points == 'dinner_after' and not targets:
        targets = dinner_and_after(payload['result']['plans'][case['pid']]['autonomous_decisions'])
    out = Path(args.out).resolve() if args.out else run_dir / 'bench.jsonl'
    if out.parent != run_dir:
        sys.exit('--out must be inside the run directory (it holds request summaries): %s' % out)
    if out.exists():
        out.rename(out.with_suffix('.%d.jsonl' % int(__import__('time').time())))   # keep the earlier summary; calls are reused from checkpoints
    import subprocess
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    manifest = dict(case=args.case, e2e_policy=e2e, visit_conditions=(request.get('visit_conditions') or {}).get(case['pid']), environment=request.get('environment'),
                    batch=os.environ.get('HL_BATCH_JOB'), shadow=args.shadow, targets=targets, variants=variants, max_calls=max_calls, max_usd=max_usd, code_commit=head,
                    model=os.environ.get('HILLINK_AGENT_MODEL', 'gpt-6-luna'), effort_default=os.environ.get('HILLINK_AGENT_EFFORT', 'high'),
                    ledger_before=ledger_before, started_at=__import__('time').strftime('%Y-%m-%d %H:%M:%S'))
    G.write_private(str(run_dir / ('manifest.%s.json' % manifest['started_at'].replace(' ', '_').replace(':', ''))), manifest)
    with tempfile.TemporaryDirectory(prefix='hillink-v18-bench-') as tmp:
        cache = (run_dir / 'provider-cache') if live else Path(tmp) / 'responses'
        G.secure_dir(str(cache))
        spec = S.manifest()
        for entry in row.get('replay_entries', []):
            G.write_private_text(str(cache / (entry['input_sha256'] + '.json')), json.dumps(S._read(entry['path'], spec), ensure_ascii=False))
        if targets is None and case['main'] == 'replay' and not e2e and args.points != 'first_decision':
            decs = payload['result']['plans'][case['pid']]['autonomous_decisions']
            times = ['%s %02d:%02d' % (d['date'], d['minute'] // 60, d['minute'] % 60) for d in decs if d.get('phase') != 'breakfast']
            targets = times[:case.get('max_points', 4)]
        recorded = None
        if case['main'] == 'replay' and not e2e:
            recorded = []
            for d in payload['result']['plans'][case['pid']]['autonomous_decisions']:
                sel = d.get('selected_plan') or {}
                answer = ((d.get('attempts') or [{}])[-1].get('answer') or {})
                alts = [p['action_id'] for p in answer.get('plans', []) if p.get('action_id') != sel.get('action_id')]
                step = dict(expect='%s %02d:%02d' % (d['date'], d['minute'] // 60, d['minute'] % 60), action=sel.get('action_id'),
                            alternatives=[dict(action=x) for x in dict.fromkeys(alts)])
                if str(sel.get('action_id', '')).startswith('meal:'):
                    step['basket_skus'] = sorted(i['sku_id'] for i in sel.get('items', []))
                recorded.append(step)
        cfg = dict(main='e2e' if e2e else case['main'], pid=case['pid'], e2e_max_decisions=args.e2e_max_decisions, stop_after_targets=bool(args.stop_after_targets), first_only=args.points == 'first_decision', script=case['script'], recorded=recorded, targets=targets, variants=variants, shadow=args.shadow, out=str(out),
                   run_dir=str(run_dir), max_calls=max_calls, max_usd=max_usd, retry_interrupted=args.retry_interrupted,
                   offline_pick=(dict(x.split('=', 1) for x in args.offline_pick.split(',')) if args.offline_pick and not live else None))
        cfg_path = Path(tmp) / 'bench.json'; cfg_path.write_text(json.dumps(cfg, ensure_ascii=False))
        env = dict(HILLINK_AGENT_CACHE=str(cache), HL_BENCH_CONFIG=str(cfg_path))
        with patch.dict(os.environ, env), patch.object(V, 'FLOW', [sys.executable, str(ROOT / 'tools/v18_bench/driver.py'), str(ROOT / 'timeline/viewer')]):
            flow = V.run_visit(request)
    decs = (flow.get('plans') or {}).get(case['pid'], {}).get('autonomous_decisions') or []
    state = json.load(open(run_dir / 'run_state.json')) if (run_dir / 'run_state.json').exists() else None
    summary = dict(case=args.case, shadow=args.shadow, error=flow.get('error'), code=flow.get('code'), targets=targets, run_dir=str(run_dir), run_state=state,
                   ledger_after=P.configured_budget().summary() if live else None,
                   trajectory=[('%s %02d:%02d' % (d['date'][5:], d['minute'] // 60, d['minute'] % 60), (d.get('selected_plan') or {}).get('action_id'), d.get('execution_state')) for d in decs],
                   points=sum(1 for _ in open(out, encoding='utf-8')) if out.exists() else 0)
    summary['request_diff'] = request_diff_summary(run_dir, out)
    if e2e:
        pl = (flow.get('plans') or {}).get(case['pid'], {}); sm = pl.get('summary') or {}
        steps = [dict(date=d['date'], time='%02d:%02d' % (d['minute'] // 60, d['minute'] % 60), action=(d.get('selected_plan') or {}).get('action_id'),
                      items=(d.get('selected_plan') or {}).get('items'), total_krw=(d.get('selected_plan') or {}).get('order_total_krw'),
                      owner=d.get('selection_owner'), state=d.get('execution_state'), llm_calls=d.get('llm_calls'),
                      attempts=len(d.get('attempts') or []), facts=((d.get('selected_plan') or {}).get('supporting_fact_ids') or []) + ((d.get('selected_plan') or {}).get('counterevidence_fact_ids') or []),
                      need=((d.get('selected_plan') or {}).get('current_need_assessment') or {}).get('state'),
                      hold_code=str(d.get('fallback_reason') or '').split(':')[0] or None if d.get('execution_state') == 'EXECUTION_HOLD' else None,
                      failure_class=d.get('failure_class'),
                      rejections=[str(x.get('validation_rejection')).split(':')[0] for x in d.get('attempts') or [] if x.get('validation_rejection')],
                      day_end_review=d.get('day_end_review') and {k: d['day_end_review'].get(k) for k in ('first_choice_rejected', 'accepted_on')},
                      day_end_match=d.get('day_end_match'),
                      diagnostics=[x.get('code') for x in d.get('selection_diagnostics') or []]) for d in decs]
        ordered = sum(x['total_krw'] or 0 for x in steps if x['state'] == 'EXECUTED')
        summary['e2e'] = dict(policy=e2e, status=pl.get('status'), fallback_reason=pl.get('fallback_reason'), completed=bool(sm.get('completed')) and not flow.get('error'),
                              last_action=steps[-1]['action'] if steps else None, spent_krw=sm.get('spent_krw'), spent_known_krw=sm.get('spent_known_krw'),
                              unpriced=sm.get('unpriced'), ordered_total_krw=ordered, ledger_matches_orders=(sm.get('spent_krw') == ordered) if sm.get('spent_krw') is not None else None,
                              meals=sm.get('meals'), meal_log=[dict(t='%02d:%02d' % (m['t'] // 60, m['t'] % 60), slot=m.get('slot'), size=m.get('size'), relation=m.get('meal_relation')) for m in sm.get('meal_log') or []],
                              fatigue_end=sm.get('fatigue_end'), decisions=steps)
    G.write_private(str(run_dir / 'run_summary.json'), summary)
    import report
    html = report.write(run_dir, out)
    summary['report'] = str(html)
    loose = G.loose_entries(str(run_dir))
    summary['permissions'] = 'PRIVATE_0700_0600' if not loose else dict(not_private=loose)
    G.write_private(str(run_dir / 'run_summary.json'), summary)
    if loose:
        print(json.dumps(summary, ensure_ascii=False, default=str))
        sys.exit('Run folder has files readable by group/others: %s' % loose[:3])
    print(json.dumps(summary, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
