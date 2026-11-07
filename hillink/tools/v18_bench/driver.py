"""V18 question-design bench — runs inside the visit subprocess (replaces the FLOW argv).

The main trajectory is fixed: either a script of past choices (V17 policy, e.g. the A07 V17 LIVE
run) or a stored V16 run replayed from its saved answers. At each target decision the bench
builds ONE shortlist from the same validated world and sends it to every variant (A/B/C/D),
so candidates are identical and only the question differs. Shadow answers are validated with
the production validator but never executed; the trajectory does not depend on them.

shadow=offline: schema-valid synthetic answers (contract and size check, no network, no cost).
shadow=live:    real provider calls through agent_provider (budget ledger applies).
"""
import copy, json, os, re, sys, time
sys.path.insert(0, sys.argv[1])
import flow_run  # noqa: E402
from operator_choice.autonomy_v1 import autonomous_agent as A, agent_provider as P, m4_shortlist as MS  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard as G  # noqa: E402
import evidence_check as EC  # noqa: E402
os.umask(0o077)

CFG = json.load(open(os.environ['HL_BENCH_CONFIG'], encoding='utf-8'))
ORIG_REQUEST = P.request
STASH = {}
ORIG_SPACE = A.action_space


def space(a, world, t):
    out = ORIG_SPACE(a, world, t)
    STASH.update(a=a, world=world, t=t, out=out)
    return out


A.action_space = space
if os.environ.get('HL_MAX_OPTIONS'): MS.MAX_OPTIONS = int(os.environ['HL_MAX_OPTIONS'])


def clock(t):
    return '%02d:%02d' % (t // 60, t % 60)


def matches(spec, action_id):
    if spec.get('action'): return action_id == spec['action']
    if spec.get('action_contains'): return spec['action_contains'] in action_id
    return False


def find_quote(action, label):
    for c in action.get('_quotes') or []:
        if label and label in c['label']: return c
    return None


def script_answer(kw, i):
    """V17-format plan for scripted step i (the past choice), with a compared option named so a
    day-end review passes on the replan exactly as it did in the recorded run."""
    steps = CFG['script']; step = steps[min(i, len(steps) - 1)]
    actions = {r['action_id']: r for r in kw['context']['actions']}
    key = next((k for k in actions if matches(step, k)), None)
    if key is None: raise RuntimeError('SCRIPT_ACTION_NOT_AVAILABLE: %s at %s' % (step, kw['context']['state'].get('time')))
    row = actions[key]; meal = row.get('kind') in ('MEAL', 'BREAKFAST') and key != 'SKIP_BREAKFAST'
    items, total = copy.deepcopy(row.get('items', [])), row.get('order_total_krw', 0)
    if row.get('kind') == 'MEAL':
        engine = (STASH.get('out') or ({},))[0].get(key, {})
        q = find_quote(engine, step.get('basket_label'))
        if q is None: raise RuntimeError('SCRIPT_BASKET_NOT_QUOTED: %s' % step.get('basket_label'))
        items = [dict(sku_id=p['sku_id'], quantity=p['billing_quantity']) for p in q['components']]; total = q['unit_price_krw']
    others = [k for k in actions if k not in (key, 'end_day_in_room')][:3]
    n = kw['context']['visit'].get('party_size') or 2
    plan = dict(action_id=key, items=items, order_total_krw=total, decision_summary='기록된 선택 재현: ' + step.get('note', key),
                supporting_fact_ids=[], counterevidence_fact_ids=[], assumptions=['RECORDED_CHOICE_REPLAY'], sharing_plan='기록된 선택 재현',
                schedule_impact='', why_not_other_plans='비교한 후보: ' + ', '.join(others), pending_intentions=[],
                current_need_assessment=dict(state='COMFORTABLE', reason='기록된 선택 재현'),
                meal_assessment=dict(kind='FULL_MEAL', modeled_diners=n, intake_assumption='재현', quantity_reason='재현', expected_satiety='UNCERTAIN', uncertainties=[]) if meal else None)
    return dict(plans=[plan], selected_index=0), dict(execution='SCRIPTED_RECORDED_CHOICE', input_sha256='script')


def synthetic(spec, rows, step, prior=None):
    """Offline shadow answer: the recorded choice when the shortlist holds it, else the first candidate.
    --offline-pick "HH:MM=action" forces that candidate (first attempt and replan alike) so the
    validator's rejection and the one replan can be exercised without a model; on the replan the
    answer names the candidate it compared, as the day-end review asks."""
    forced = (CFG.get('offline_pick') or {}).get((step or {}).get('expect'))
    sel = next((r for r in rows if forced and r['action_id'] == forced), None) or next((r for r in rows if step and matches(step, r['action_id'])), rows[0])
    basket = None
    if sel['type'] == 'MEAL':
        opts = [o for g in sel['basket_groups'] for o in g['options']]
        basket = next((o['basket_id'] for o in opts if step and step.get('basket_label') and step['basket_label'] in o['label']), opts[0]['basket_id'])
    alt = next((r['action_id'] for r in rows if r['action_id'] != sel['action_id']), None)
    meal = sel['type'] in ('MEAL', 'BREAKFAST')
    if prior and forced:
        alt = next((r['action_id'] for r in rows if r['type'] not in ('REST', 'DAY_END') and r['action_id'] != sel['action_id']), alt)
    if spec.get('minimal_output'):
        return dict(selected_action_id=sel['action_id'], selected_basket_id=basket, fact_ids=[], reason='오프라인 합성 답', rejected_action_id=alt, need='COMFORTABLE')
    out = dict(selected_action_id=sel['action_id'], selected_basket_id=basket, reason='오프라인 합성 답' + (' · 비교: %s' % alt if prior and forced else ''), supporting_fact_ids=[], counterevidence_fact_ids=[],
               rejected_alternative=dict(action_id=alt or '', reason='오프라인 합성'), next_intent=None,
               current_need_assessment=dict(state='COMFORTABLE', reason='합성'),
               meal_assessment=dict(kind='FULL_MEAL', modeled_diners=2, sharing_plan='합성', quantity_reason='합성', expected_satiety='UNCERTAIN') if meal else None)
    if out.get('meal_assessment') and 'quantity_reason' not in spec['schema']['properties']['meal_assessment']['anyOf'][0]['properties']:
        out['meal_assessment'].pop('quantity_reason')
    if 'need_estimate' in spec['schema']['properties']:
        del out['current_need_assessment']
        out['need_estimate'] = dict(modeled_state='SATISFIED', confidence='LOW', basis=['ENGINE_ESTIMATE'], differs_from_engine_because=None, reason='합성')
    return out


def offline_day_end_probe(rows, t, prior, schema=None):
    """(offline only, HL_OFFLINE_DAY_END=structured|word|bare) From 21:00 the synthetic customer ends the day,
    to exercise the day-end review without a model. The replan answer after the review either names the
    remaining candidate structurally (rejected_alternative.action_id), compares it by a distinctive label
    word, or only mentions that word (must stay held)."""
    mode = os.environ.get('HL_OFFLINE_DAY_END')
    if not mode or CFG.get('shadow') == 'live' or str(t) < '2100': return None
    if not any(r['action_id'] == 'end_day_in_room' for r in rows): return None
    other = next((r for r in rows if r['type'] not in ('REST', 'DAY_END')), None)
    rest = next((r['action_id'] for r in rows if r['type'] == 'REST'), '')
    from operator_choice.autonomy_v1 import ls_stability as LSS
    word = (LSS.label_words((other or {}).get('label')) or [''])[0]
    reason, alt = '저녁과 휴식을 마쳐 오늘을 마칩니다(오프라인 합성)', dict(action_id=rest, reason='합성')
    if prior and other:
        if mode == 'structured': alt = dict(action_id=other['action_id'], reason='저녁을 먹은 지 얼마 안 돼 추가 식사는 필요 없음(합성)')
        elif mode == 'word': reason = '추가 %s 식사보다 오늘을 마치는 편이 맞습니다(합성)' % word
        else: reason = '%s %s' % (word, word)
    return dict(selected_action_id='end_day_in_room', selected_basket_id=None, reason=reason, supporting_fact_ids=[], counterevidence_fact_ids=[],
                rejected_alternative=alt, next_intent=None, current_need_assessment=dict(state='COMFORTABLE', reason='합성'), meal_assessment=None,
                **({'tradeoff_note': None} if 'tradeoff_note' in ((schema or {}).get('properties') or {}) else {}))


def live(policy, spec, ctx, purpose, capture=None, expected_identity=None):
    saved = {k: os.environ.get(k) for k in ('HILLINK_AGENT_MODE', 'HILLINK_LLM_EXTERNAL_OPT_IN')}
    os.environ.update(HILLINK_AGENT_MODE='live', HILLINK_LLM_EXTERNAL_OPT_IN='1')
    try:
        return ORIG_REQUEST(policy=policy, system=spec['system'], context=ctx, schema=spec['schema'], purpose=purpose, max_output=16000,
                            stable_prefix=True, effort=spec['effort'], prefix_message=spec['prefix_message'], capture=capture,
                            expected_identity=expected_identity)
    finally:
        for k, v in saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v


# ---------------------------------------------------------------- per-run guard and checkpoints
# Independent of the shared ledger (which the provider still updates): this run may start at most
# max_calls new calls and reserve at most max_usd of worst-case cost (the provider's own ceiling
# formula), checked BEFORE each call. Every call leaves files in <run_dir>/calls/:
#   <key>.inflight.json  written before the call, removed when it ends
#   <key>.request.json   the exact request body and its identity digest
#   <key>.response.json  answer, provider trace and the raw API response body
#   <key>.error.json     a provider error (the call happened; it is not repeated automatically)
# A restart reuses a finished call and never re-sends an interrupted or errored one unless
# --retry-interrupted is given.
Blocked = G.Blocked
_guard = None


def guard():
    global _guard
    if _guard is None:
        _guard = G.Guard(CFG['run_dir'], CFG['max_calls'], CFG['max_usd'], retry=bool(CFG.get('retry_interrupted')), mode=CFG['shadow'])
    return _guard


def run_state():
    return guard().state()


def ceiling_for(payload):
    rates = P.PRICES[payload['model']]
    wire = json.dumps(payload, ensure_ascii=False).encode()
    return ((len(wire) + 4096) * max(rates['input'], rates['write']) + payload['max_output_tokens'] * rates['output']) / 1e6


def guarded_call(key, policy, spec, ctx, purpose, rows, step):
    """Compute THIS call's exact body and identity first; the guard compares them with the checkpoint
    before reusing, re-sending or sending anything."""
    model = os.environ.get('HILLINK_AGENT_MODEL', 'gpt-6-luna'); effort = spec['effort'] or os.environ.get('HILLINK_AGENT_EFFORT', 'high')
    payload = P.build_payload(system=spec['system'], context=ctx, schema=spec['schema'], model=model, effort=effort, max_output=16000,
                              stable_prefix=True, prefix_message=spec['prefix_message'])
    identity = P.request_identity(policy, purpose, payload)
    def send(capture):
        if CFG['shadow'] == 'live':
            return live(policy, spec, ctx, purpose, capture, expected_identity=identity)
        # offline: no provider received anything, so no provider-side body match is claimed
        return synthetic(spec, rows, step, ctx.get('previous_rejection')), dict(execution='OFFLINE_SYNTHETIC', input_sha256=identity, seconds=0, usage={})
    return guard().call(key, policy, purpose, payload, identity, P.REQUEST_POLICY, ceiling_for(payload), send, step)


def call_key(a, t, policy, attempt):
    """One file name per customer, date, time, variant and attempt."""
    return re.sub(r'[^A-Za-z0-9_-]', '', '%s_%s_%s_%s_a%d' % (a.pid, a.sc['date'], clock(t).replace(':', ''), policy.replace('LLM_AUTONOMOUS_CUSTOMER_', ''), attempt))


def coverage_of(rows, trace, step):
    """Is the recorded choice (and each recorded alternative) selectable in the shared shortlist?"""
    def check(spec):
        row = next((r for r in rows if matches(spec, r['action_id'])), None)
        out = dict(spec=spec, in_shortlist=bool(row))
        if row is None:
            drop = next((d for d in trace['dropped'] if matches(spec, d['action_id'])), None)
            out['excluded_reason'] = drop and drop['reason']
            out['in_world'] = any(matches(spec, k) for k in trace['fit'])
        elif spec.get('basket_skus'):
            index = (trace['fit'].get(row['action_id']) or {}).get('basket_index') or {}
            shown = {o['basket_id'] for g in row.get('basket_groups', []) for o in g['options']}
            hit = next((b for b, x in index.items() if b in shown and sorted(i['sku_id'] for i in x['items']) == spec['basket_skus']), None)
            out['basket_selectable'] = bool(hit); out['basket'] = hit and index[hit]['label']
            if not hit:
                quotes = (STASH['out'][0].get(row['action_id']) or {}).get('_quotes') or []
                q = next((c for c in quotes if sorted(p['sku_id'] for p in c['components']) == spec['basket_skus']), None)
                if q is None:
                    out['basket_excluded_reason'] = 'ORDER_NOT_AMONG_ENGINE_QUOTES (a free composition the quoted-basket contract cannot express)'
                else:
                    fit = trace['fit'].get(row['action_id']) or {}
                    d = next((d for d in fit.get('dropped_baskets') or [] if d.get('sku_id') == q['sku_id']), None)
                    out['basket_excluded_reason'] = d and d['reason']
        elif spec.get('basket_label'):
            opts = [o for g in row.get('basket_groups', []) for o in g['options']]
            hit = next((o for o in opts if spec['basket_label'] in o['label']), None)
            out['basket_selectable'] = bool(hit); out['basket'] = hit and dict(label=hit['label'], total_krw=hit['total_krw'], marks=hit['marks'])
            if not hit:
                fit = trace['fit'].get(row['action_id']) or {}
                d = next((d for d in fit.get('dropped_baskets') or [] if spec['basket_label'] in str(d.get('label'))), None)
                out['basket_excluded_reason'] = d and d['reason']
        return out
    return dict(choice=check(step), alternatives=[check(x) for x in step.get('alternatives', [])]) if step else None


def score_dump(a, t, actions, w, personal, rows, trace, path):
    """Offline analysis: for every candidate the M4 fit and, for meal candidates, the product-score terms
    (factor, value, fact ids) of each scored basket. Numbers and ids only."""
    cite = personal['citable_fact_ids']; out = dict(time=clock(t), shown=[r['action_id'] for r in rows], dropped=trace['dropped'], candidates={},
               menu_prefs=a.traits.get('menu'), facets={k: dict(level=v.get('level'), evidence=v.get('evidence')) for k, v in (a.traits.get('facets') or {}).items()},
               bars=(a.P or {}).get('bars'))
    for key, action in actions.items():
        fit = (trace.get('fit') or {}).get(key) or {}
        rec = dict(type=MS.kind_of(key, action), fit=fit.get('fit'), basis=fit.get('basis'), shown=key in out['shown'])
        if action.get('execution') == 'MEAL':
            baskets = []
            for c in action.get('_quotes') or []:
                o = MS.HR.offer(a, c, action['start'], action['duration'], w)
                unknown = o.get('price_pp_krw') is None
                so = dict(o, price_pp_krw=0, guest_discount_krw=0, card_benefit_krw=0, in_package=False) if unknown else o
                terms = MS.AD.EN.score(so, t, dict(used=set(a.used), hunger=a.hunger_e), dict(a.visit_e, checkin=MS.AD.mh(t)), a.traits, w)
                baskets.append(dict(label=c['label'], total_krw=c['unit_price_krw'], price_pp_krw=o.get('price_pp_krw'), tags=sorted({tg for p in c.get('components', []) for tg in p.get('tags', [])}), menu_tags=sorted(set((o.get('food') or {}).get('menu_tags') or [])),
                                    meal_equivalents=(c.get('meal_basket') or {}).get('meal_equivalents'),
                                    fit=round(sum(x['value'] for x in terms), 3),
                                    terms=[dict(factor=x['factor'], value=round(x['value'], 3), facet=x.get('facet'), facts=[f for f in x.get('fact_ids', []) if f in cite]) for x in terms]))
            baskets.sort(key=lambda b: -b['fit'])
            rec['baskets'] = baskets
        out['candidates'][key] = rec
    with open(path, 'a', encoding='utf-8') as f: f.write(json.dumps(out, ensure_ascii=False, default=str) + '\n')


def shadow(kw, step):
    a = STASH['a']; t = STASH['t']; actions, menus, excluded, w = STASH['out']
    personal = kw['context']['personal']
    base = {k: v for k, v in kw['context'].items() if k not in ('actions', 'menus', 'world_exclusions', 'previous_rejection')}
    rows, trace = MS.build(a, STASH['world'], t, actions, menus, w, personal['citable_fact_ids'], max_options=MS.MAX_OPTIONS, records=personal.get('evidence_records'))
    point = dict(pid=a.pid, date=a.sc['date'], time=clock(t), recorded_step=step, candidate_count=len(actions),
                 shortlist=[dict(action_id=r['action_id'], type=r['type'], shown_because=r['m4'].get('shown_because'),
                                 groups=[dict(label=g['label'], shown_because=g['shown_because'], options=[(o['label'], o['total_krw']) for o in g['options']]) for g in r.get('basket_groups', [])])
                            for r in rows],
                 dropped=trace['dropped'], recorded_coverage=coverage_of(rows, trace, step), rule=MS.rule_sufficient(rows, a, t, actions), variants=[])
    if os.environ.get('HL_BENCH_SCORE_DUMP') and CFG['shadow'] == 'offline':   # analysis only: M4 score terms behind the shortlist
        score_dump(a, t, actions, w, personal, rows, trace, os.environ['HL_BENCH_SCORE_DUMP'])
    if point['rule'][0]:   # V18 would not ask the model here; no shadow calls
        with open(CFG['out'], 'a', encoding='utf-8') as f: f.write(json.dumps(point, ensure_ascii=False, default=str) + '\n')
        return
    lists = {'M4_FIT': (rows, trace)}
    for policy in CFG['variants']:
        mode = A.POLICIES[policy].get('shortlist', 'M4_FIT')
        if mode not in lists:   # a selection variant (P) gets its own shortlist from the same validated world
            lists[mode] = MS.build(a, STASH['world'], t, actions, menus, w, personal['citable_fact_ids'], max_options=MS.MAX_OPTIONS, records=personal.get('evidence_records'), selection=mode)
        v_rows, v_trace = lists[mode]
        spec = A.resolved_spec(A.POLICIES[policy], v_rows)
        full, cite, cov = A.variant_request(a, t, base, actions, v_rows, v_trace, personal, spec)
        wire = P.serialize_context(full, True)
        rec = dict(policy=policy, request_chars=len(wire), system_chars=len(spec['system']), effort=spec['effort'] or os.environ.get('HILLINK_AGENT_EFFORT', 'high'),
                   citable=len(cite), coverage=cov and {k: cov[k] for k in ('full_citable', 'sent_facts', 'sent_records', 'unsent', 'unsent_scope', 'per_candidate', 'candidate_links_sent')},
                   sent_fact_ids=sorted(cite) if cov else None, candidates_sha256=P.digest(v_rows), attempts=[],
                   venue_records_unsent=EC.unsent(personal, v_rows, cite, MS.venue_names),
                   shortlist_selection=mode, shown=[r['action_id'] for r in v_rows])
        prior = None
        for attempt in range(2):
            ctx = dict(full, previous_rejection=prior) if prior else full
            begin = time.monotonic()
            key = call_key(a, t, policy, attempt + 1)
            try:
                answer, trace_p = guarded_call(key, policy, spec, ctx, 'BENCH_CUSTOMER_ACTION_SELECTION', v_rows, step)
            except Blocked as exc:
                rec['attempts'].append(dict(call_key=key, blocked=str(exc))); break
            except P.ProviderUnavailable as exc:
                rec['attempts'].append(dict(call_key=key, error=str(exc), provider=getattr(exc, 'trace', None))); break
            usage = (trace_p or {}).get('usage') or {}
            out = dict(call_key=key, answer=answer, execution=trace_p.get('execution'), reused_from_checkpoint=bool(trace_p.get('reused_from_checkpoint')),
                       seconds=trace_p.get('seconds', round(time.monotonic() - begin, 3)),
                       input_tokens=usage.get('input_tokens'), cached_tokens=(usage.get('input_tokens_details') or {}).get('cached_tokens'),
                       output_tokens=usage.get('output_tokens'), reasoning_tokens=(usage.get('output_tokens_details') or {}).get('reasoning_tokens'),
                       cost_upper_usd=trace_p.get('charged_upper_usd'), provider_input_sha256=trace_p.get('input_sha256'), response_id=trace_p.get('response_id'),
                       model_returned=trace_p.get('model_returned'))
            try:
                plan, alt_plan = A.expand_answer(answer, v_rows, actions, menus, v_trace, a, spec)
                out['plan'] = plan; out['alternative_plan'] = alt_plan
                A.validate_selection(a, plan, actions, menus, cite, prior, spec, [r['action_id'] for r in v_rows], t)
                out.update(validation='PASS', selected=plan['action_id'], basket=plan.get('selected_basket_id'), total_krw=plan['order_total_krw'],
                           facts=plan['supporting_fact_ids'] + plan['counterevidence_fact_ids'])
            except ValueError as exc:
                out.update(validation=str(exc)[:300])
            rec['attempts'].append(out)
            if out.get('validation') != 'PASS' and attempt == 0:
                prior = dict(plan=answer, reason=out['validation']); continue
            break
        point['variants'].append(rec)
    if len(lists) > 1:
        point['shortlist_by_selection'] = {m: dict(shown=[r['action_id'] for r in rl], meal_reasons={k: v for k, v in (tr.get('shown_because') or {}).items() if k.startswith('meal:')},
                                                   personal_signal={k: dict(records=v['records'], tier=v.get('tier'), confirmed_positive=v.get('confirmed_positive'), confirmed_negative=v.get('confirmed_negative'), unclassified=len(v.get('unclassified') or [])) for k, v in (tr.get('personal_signal') or {}).items()},
                                                   m4_fit_meal_order=tr.get('m4_fit_meal_order')) for m, (rl, tr) in lists.items()}
    with open(CFG['out'], 'a', encoding='utf-8') as f:
        f.write(json.dumps(point, ensure_ascii=False, default=str) + '\n')


def script_index(kw):
    """The scripted step for this decision, by its recorded time (the visit runs one subprocess per day)."""
    t = kw['context']['state'].get('time')
    for i, step in enumerate(CFG.get('script') or []):
        if step.get('expect') == t: return i
    raise RuntimeError('TRAJECTORY_DEVIATED_FROM_RECORD: no recorded choice at %s' % t)


# ---------------------------------------------------------------- full-visit LIVE (main='e2e')
# The visit runs under the V18 policy itself: every provider call the agent makes (action selection,
# breakfast) goes through the same per-run guard, checkpoint files and batch-wide cap as the bench, and
# the validated answer is EXECUTED by the engine, so later decisions see its consequences. Offline,
# a schema-valid synthetic answer (first shown candidate) is executed instead, at no cost.
E2E_SEQ = {}


E2E_DECISIONS = {'n': 0}


def e2e_request(**kw):
    ctx = kw['context']; policy = kw['policy']
    limit = CFG.get('e2e_max_decisions')
    if limit and not ctx.get('previous_rejection'):
        # count decisions across the visit's day subprocesses (the checkpoint folder survives them)
        done = sum(1 for f in os.listdir(os.path.join(CFG['run_dir'], 'calls')) if f.endswith('_a1.response.json') or f.endswith('_a1.error.json')) if os.path.isdir(os.path.join(CFG['run_dir'], 'calls')) else 0
        if done >= limit: raise P.ProviderUnavailable('BENCH_STOPPED_AFTER_%d_DECISIONS' % limit)
    model = kw.get('model') or os.environ.get('HILLINK_AGENT_MODEL', 'gpt-6-luna')
    effort = kw.get('effort') or os.environ.get('HILLINK_AGENT_EFFORT', 'high')
    payload = P.build_payload(system=kw['system'], context=ctx, schema=kw['schema'], model=model, effort=effort, max_output=kw.get('max_output', 6000),
                              stable_prefix=kw.get('stable_prefix', False), prefix_message=kw.get('prefix_message'))
    identity = P.request_identity(policy, kw['purpose'], payload)
    t = str((ctx.get('state') or {}).get('time') or '0000').replace(':', ''); date = (ctx.get('visit') or {}).get('date') or 'nodate'
    base = re.sub(r'[^A-Za-z0-9_-]', '', '%s_%s_%s_%s_%s' % (CFG.get('pid'), date, t, policy.replace('LLM_AUTONOMOUS_CUSTOMER_', ''), kw['purpose'][:12]))
    E2E_SEQ[base] = E2E_SEQ.get(base, 0) + 1
    key = '%s_a%d' % (base, E2E_SEQ[base])
    def send(capture):
        if CFG['shadow'] == 'live':
            saved = {k: os.environ.get(k) for k in ('HILLINK_AGENT_MODE', 'HILLINK_LLM_EXTERNAL_OPT_IN')}
            os.environ.update(HILLINK_AGENT_MODE='live', HILLINK_LLM_EXTERNAL_OPT_IN='1')
            try: return ORIG_REQUEST(**dict(kw, capture=capture, expected_identity=identity))
            finally:
                for k, v in saved.items():
                    if v is None: os.environ.pop(k, None)
                    else: os.environ[k] = v
        if 'plans' in (kw['schema'].get('properties') or {}):   # V16/V17 plan format: first listed action, engine items
            acts = [r for r in ctx.get('actions') or [] if r.get('action_id') != 'end_day_in_room'] or ctx.get('actions') or []
            if not acts: raise P.ProviderUnavailable('E2E_OFFLINE_NO_ACTIONS')
            row = acts[0]; meal = row.get('kind') in ('MEAL', 'BREAKFAST')
            plan = dict(action_id=row['action_id'], items=copy.deepcopy(row.get('items', [])), order_total_krw=row.get('order_total_krw', 0), decision_summary='오프라인 합성 답',
                        supporting_fact_ids=[], counterevidence_fact_ids=[], assumptions=[], sharing_plan='합성', schedule_impact='',
                        why_not_other_plans='비교한 후보: ' + ', '.join(r['action_id'] for r in acts[1:3]), pending_intentions=[],
                        current_need_assessment=dict(state='COMFORTABLE', reason='합성'),
                        meal_assessment=dict(kind='FULL_MEAL', modeled_diners=(ctx.get('visit') or {}).get('party_size') or 2, intake_assumption='합성', quantity_reason='합성', expected_satiety='UNCERTAIN', uncertainties=[]) if meal else None)
            return dict(plans=[plan], selected_index=0), dict(execution='OFFLINE_SYNTHETIC', input_sha256=identity, seconds=0, usage={})
        rows = ctx.get('candidates') or []
        if not rows: raise P.ProviderUnavailable('E2E_OFFLINE_NO_CANDIDATES')
        probe = offline_day_end_probe(rows, t, ctx.get('previous_rejection'), kw['schema'])
        if probe: return probe, dict(execution='OFFLINE_SYNTHETIC', input_sha256=identity, seconds=0, usage={})
        return synthetic(dict(schema=kw['schema']), rows, None, ctx.get('previous_rejection')), dict(execution='OFFLINE_SYNTHETIC', input_sha256=identity, seconds=0, usage={})
    step = dict(purpose=kw['purpose'], time=t, date=date)
    answer, trace = guard().call(key, policy, kw['purpose'], payload, identity, P.REQUEST_POLICY, ceiling_for(payload), send, step)
    usage = (trace or {}).get('usage') or {}
    with open(os.path.join(CFG['run_dir'], 'e2e_calls.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(dict(kind='E2E_CALL', key=key, purpose=kw['purpose'], date=date, time=t, policy=policy, execution=trace.get('execution'),
                                reused_from_checkpoint=bool(trace.get('reused_from_checkpoint')), retry=bool(ctx.get('previous_rejection')),
                                seconds=trace.get('seconds'), input_tokens=usage.get('input_tokens'), cached_tokens=(usage.get('input_tokens_details') or {}).get('cached_tokens'),
                                output_tokens=usage.get('output_tokens'), reasoning_tokens=(usage.get('output_tokens_details') or {}).get('reasoning_tokens'),
                                cost_upper_usd=trace.get('charged_upper_usd'), provider_input_sha256=trace.get('input_sha256'), answer=answer), ensure_ascii=False, default=str) + '\n')
    return answer, trace


def request(**kw):
    if CFG['main'] == 'e2e':
        try: return e2e_request(**kw)
        except Blocked as exc: raise P.ProviderUnavailable('BENCH_GUARD_BLOCKED: %s' % exc)
    retry = bool(kw['context'].get('previous_rejection'))
    idx = script_index(kw) if CFG['main'] == 'script' else None
    if kw['purpose'] == 'CUSTOMER_ACTION_PLAN' and not retry:
        t = kw['context']['state'].get('time'); date = kw['context']['visit'].get('date')
        step = CFG['script'][idx] if idx is not None else next((r for r in CFG.get('recorded') or [] if r['expect'] == '%s %s' % (date, t)), None)
        targets = CFG.get('targets') or []
        if CFG.get('first_only'):
            shadow(kw, step)
            raise P.ProviderUnavailable('BENCH_STOPPED_AFTER_FIRST_DECISION')
        if not targets or t in targets or ('%s %s' % (date, t)) in targets:
            shadow(kw, step)
            if CFG.get('stop_after_targets') and targets and ('%s %s' % (date, t)) == targets[-1]:
                # the operator scenario differs from the stored run, so its saved answers cannot drive the rest
                raise P.ProviderUnavailable('BENCH_STOPPED_AFTER_TARGETS')
    if CFG['main'] == 'script':
        return script_answer(kw, idx)
    return ORIG_REQUEST(**kw)


A.P.request = request
flow_run.main()
