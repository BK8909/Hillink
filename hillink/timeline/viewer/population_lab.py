"""Group experiments on the rules engine (no model calls): baseline / behaviour prior with a reference profile /
reference swap / operator A/B, with continuity checks and per-customer trace-back.

    python population_lab.py <out.private.json> [--duration stay_1] [--personas A01,A02,...]

Every condition is a full visit run of the same customers, dates, seed and engine; only the stated factor changes.
A/B pairs are compared only when every non-experiment input and the reference provenance are identical.
"""
import copy
import json
import sys
import time

import ledger_service as LS
import operating_reference as OR
import population as POP
import visit_run as VR

PIZZA_HILL_DINE_IN_MAINS = None   # filled from the catalog: discountable MAIN SKUs of PIZZA_HILL


def pizza_hill_mains():
    from operator_choice.autonomy_v1 import hotel_catalog as H
    return sorted(s['sku_id'] for s in H.BY.values() if s.get('venue_id') == 'PIZZA_HILL' and s.get('role') == 'MAIN' and H.discount_allowed(s))


def base_request(personas, duration, prior='OFF', profile='external', catalog_options=None, seed=0, start='2026-11-13', coefficient=None):
    r = dict(personas=list(personas), duration=duration, event_mode='none', seed=seed, start_date=start, behavior_engine='m4_c01',
             catalog_policy='C01_HOTEL_CATALOG_V1', simulation_mode='independent', behaviour_prior=prior, reference_profile=profile)
    if coefficient is not None: r['behaviour_prior_coefficient'] = coefficient
    if catalog_options: r['catalog_options'] = copy.deepcopy(catalog_options)
    return r


def run(request, profile=None):
    t = time.time(); flow = VR.run_visit(request)
    if flow.get('error'): return dict(request=request, error=flow)
    ledger = LS.register_visit(flow, request)
    prof = profile or request.get('reference_profile', 'external')
    summary = OR.aggregate(flow, profile=prof)
    entries = OR.load(profile=prof)[0]
    w = POP.weights(flow, entries, 'party_size')
    return dict(request=request, flow=flow, ledger=ledger, summary=summary, weights=w, estimates=POP.estimates(flow, w if w.get('status', '').startswith('OK') else None),
                seconds=round(time.time() - t, 1))


# ------------------------------------------------------------------ continuity (multi-day state carried into decisions)
def continuity(flow, ledger=None):
    """Multi-day checks per customer: the next day's first decision input carries the previous day's meals,
    activities, venues and state; repeated dinners (Pizza Hill, delivery); breakfast-to-lunch/dinner gaps; room nights
    in the ledger equal the nights stayed; executed spend equals the customer's non-room ledger rows."""
    out = {}
    dinners = {}
    for r in OR.dinner_rows(flow): dinners.setdefault(r['customer_id'], []).append(r)
    for pid, plan in (flow.get('plans') or {}).items():
        scenes = plan.get('scenes') or []
        days = sorted({s.get('visit_date') for s in scenes if s.get('visit_date')})
        decs = (plan.get('m4') or {}).get('decisions') or []
        checks = []
        for i, day in enumerate(days[1:], 1):
            prev = [s for s in scenes if s.get('visit_date') == days[i - 1]]
            first = next((x for x in decs if (x.get('packet') or {}).get('context_factors', {}).get('date') == day), None)
            cf = (first or {}).get('packet', {}).get('context_factors', {})
            prior_meals = cf.get('prior_meals') or []
            acts = cf.get('activities') or []
            prev_dinner = next((r for r in dinners.get(pid, []) if r['date'] == days[i - 1]), None)
            ms = cf.get('meal_state') or {}
            checks.append(dict(day=day, decision_found=first is not None, prior_meals_in_input=len(prior_meals),
                               previous_day_meals=len([s for s in prev if s.get('meal')]),
                               last_prior_meal=(prior_meals[-1] or {}).get('action_id') if prior_meals else None,
                               previous_dinner=(prev_dinner or {}).get('label'),
                               previous_day_activities_in_input=sum(1 for a in acts if a.get('date') == days[i - 1]),
                               visited_venues_in_input=sorted({a.get('venue_id') for a in acts if a.get('venue_id')})[:15],
                               fatigue_in_input=cf.get('fatigue_proxy'), satiety_in_input=ms.get('satiety_proxy'),
                               carried=None if not first else len(prior_meals) > 0 and any(a.get('date') == days[i - 1] for a in acts)))
        dn = dinners.get(pid, [])
        meals = sorted(((s.get('visit_date'), s.get('t0'), s.get('meal')) for s in scenes if s.get('meal') in ('breakfast', 'lunch', 'dinner')), key=lambda x: (x[0], x[1] or 0))
        gaps = [dict(day=d, after=m0, before=m1, minutes=t1 - t0) for (d, t0, m0), (d1, t1, m1) in zip(meals, meals[1:]) if d == d1 and t0 is not None and t1 is not None]
        tested = [c for c in checks if c['decision_found']]   # a check-out day may have no model-free decision packet to carry into
        row = dict(days=days, nights=max(0, len(days) - 1), checks=checks, ok=all(c['carried'] for c in tested) if tested else None,
                   days_without_decision=[c['day'] for c in checks if not c['decision_found']],
                   dinners=[(r['date'], r['kind'], r['venue']) for r in dn],
                   repeat_pizza_hill=sum(r['venue'] == 'PIZZA_HILL' for r in dn), repeat_delivery=sum(r['kind'] == 'EXTERNAL_DELIVERY' for r in dn),
                   shortest_same_day_meal_gap_min=min((g['minutes'] for g in gaps), default=None),
                   spent_krw=(plan.get('summary') or {}).get('spent_krw'))
        if ledger:
            rows = (ledger.get('receipts') or {}).get(pid, {}).get('rows') or []
            row.update(ledger_room_nights=sum(1 for r in rows if r.get('act') == 'room_night'),
                       ledger_non_room_krw=sum(r['paid_krw'] for r in rows if r.get('act') != 'room_night'))
            row['room_nights_match'] = row['ledger_room_nights'] == row['nights']
            row['orders_match_ledger'] = row['spent_krw'] == row['ledger_non_room_krw']
        out[pid] = row
    return out


def venue_bias(flow):
    """Why dinners concentrate on one venue: for each executed dinner decision, the best candidate of every venue,
    the margin to the best other venue, the terms that make that margin, candidate counts per venue, exact ties,
    and venues excluded at that time (opening hours, service windows)."""
    rows, excluded, counts, space = [], {}, {}, {}
    for pid, plan in (flow.get('plans') or {}).items():
        dn = {r['event_id']: r for r in OR.dinner_rows({'plans': {pid: plan}, 'visits': flow['visits']}) if r.get('event_id')}
        for x in (plan.get('m4') or {}).get('decisions') or []:
            pk = x.get('packet') or {}
            if pk.get('kind') != 'QUANTITATIVE' or x.get('actual_next_event_id') not in dn: continue
            cands = [c for c in pk['candidates'] if c.get('world_allowed') and _score(c) is not None and (c.get('meal_fraction') or 0) >= 0.8]
            venue = lambda c: 'EXTERNAL_DELIVERY' if c['candidate_id'] == 'EXTERNAL_DELIVERY' else ((c.get('scoring_input_contract') or {}).get('venue_id') or c.get('candidate_label', '')[:6])
            best = {}
            for c in cands:
                v = _venue_of(c)
                counts.setdefault(v, []).append(1)
                if v not in best or _score(c) > _score(best[v]): best[v] = c
                sp = sum(t['value'] for t in c.get('terms') or [] if t.get('facet') == 'space' and t.get('value'))
                space.setdefault(v, []).append(sp)
            for e in pk.get('catalog_excluded_candidates') or []:
                if e.get('venue_id') and not e.get('sku_id'):
                    for r in e.get('reasons') or []: excluded.setdefault(e['venue_id'], {}).setdefault(r, 0); excluded[e['venue_id']][r] += 1
            chosen = next((c for c in pk['candidates'] if c['candidate_id'] == x['selected_action']), None)
            if not chosen: continue
            cv = _venue_of(chosen)
            others = sorted((c for v, c in best.items() if v != cv), key=_score, reverse=True)
            alt = others[0] if others else None
            tsum = lambda c: {t['factor']: t['value'] for t in c.get('terms') or [] if t.get('value')}
            diff = {}
            if alt:
                ta, tb = tsum(chosen), tsum(alt)
                diff = {k: round(ta.get(k, 0) - tb.get(k, 0), 4) for k in set(ta) | set(tb) if abs(ta.get(k, 0) - tb.get(k, 0)) > 1e-9}
            rows.append(dict(customer_id=pid, time=pk['context_factors'].get('time'), chosen_venue=cv, chosen=chosen.get('candidate_label'),
                             runner_up_venue=_venue_of(alt) if alt else None, runner_up=(alt or {}).get('candidate_label'),
                             margin=round(_score(chosen) - _score(alt), 4) if alt else None, exact_tie=bool(alt) and _score(chosen) == _score(alt),
                             term_difference=dict(sorted(diff.items(), key=lambda kv: -abs(kv[1]))[:6]),
                             venues_available=sorted(best)))
    share = {}
    for r in rows: share[r['chosen_venue']] = share.get(r['chosen_venue'], 0) + 1
    term_totals = {}
    for r in rows:
        if r['chosen_venue'] == 'PIZZA_HILL':
            for k, v in r['term_difference'].items(): term_totals[k] = term_totals.get(k, 0) + v
    n_ph = max(1, share.get('PIZZA_HILL', 0))
    return dict(decisions=len(rows), chosen_by_venue=share, candidates_per_decision_by_venue={k: round(len(v) / max(1, len(rows)), 1) for k, v in counts.items()},
                mean_term_advantage_of_pizza_hill_over_runner_up={k: round(v / n_ph, 4) for k, v in sorted(term_totals.items(), key=lambda kv: -abs(kv[1]))[:10]},
                margins=sorted(r['margin'] for r in rows if r['margin'] is not None), exact_ties=sum(r['exact_tie'] for r in rows),
                mean_space_term_by_venue={k: round(sum(v) / len(v), 3) for k, v in space.items()},
                share_of_space_term_without_personal_evidence='W.space 1.5 x 0.3 = 0.45 is given to every customer for a night-view venue after sunset (engine.py space term); personal space evidence adds up to 1.05',
                excluded_venue_reasons=excluded, rows=rows)


_LABEL_VENUE = None


def _venue_of(c):
    """Venue of a candidate from the hotel catalog (component labels), not from guesses."""
    global _LABEL_VENUE
    if c is None: return None
    if c['candidate_id'] in ('EXTERNAL_DELIVERY', 'ROOM_REST'): return c['candidate_id']
    if _LABEL_VENUE is None:
        from operator_choice.autonomy_v1 import hotel_catalog as H
        _LABEL_VENUE = {}
        for x in H.BY.values():
            if x.get('label') and x.get('venue_id'): _LABEL_VENUE.setdefault(x['label'], set()).add(x['venue_id'])
    label = c.get('candidate_label') or ''
    for part in [label] + label.split(' + '):
        v = _LABEL_VENUE.get(part.strip())
        if v and len(v) == 1: return next(iter(v))
    return 'UNMAPPED:' + label[:16]


# ------------------------------------------------------------------ A/B
def comparable(a, b, allowed=('catalog_options',)):
    reasons = []
    ra = {k: v for k, v in a['request'].items() if k not in allowed}; rb = {k: v for k, v in b['request'].items() if k not in allowed}
    if ra != rb: reasons.append('NON_EXPERIMENT_INPUT_CHANGED:' + ','.join(sorted(k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k))))
    pa = (a['flow'].get('visit') or {}).get('behaviour_prior'); pb = (b['flow'].get('visit') or {}).get('behaviour_prior')
    if 'behaviour_prior' not in allowed and (pa or {}).get('provenance') != (pb or {}).get('provenance'): reasons.append('REFERENCE_PROVENANCE_CHANGED')
    if set(a['flow']['plans']) != set(b['flow']['plans']): reasons.append('CUSTOMER_SCOPE_MISMATCH')
    if a['ledger']['run_id'] == b['ledger']['run_id']: reasons.append('SAME_RUN_ID')
    for side, x in (('A', a), ('B', b)):
        rows = [r for c in x['ledger']['receipts'].values() for r in c['rows']]
        if {r.get('run_id') for r in rows} - {x['ledger']['run_id']}: reasons.append(side + ':OTHER_RUN_ROWS')
        if not x['ledger']['checks'].get('receipts_equal_L4_L3_L2_L1'): reasons.append(side + ':LEDGER_NOT_BALANCED')
    return reasons


def _decision_at(plan, row):
    """The decision that produced this dinner scene (same M4 event id); its candidates by id."""
    for x in (plan.get('m4') or {}).get('decisions') or []:
        pk = x.get('packet') or {}
        if row.get('event_id') and x.get('actual_next_event_id') == row['event_id'] and pk.get('kind') == 'QUANTITATIVE':
            return x, {c['candidate_id']: c for c in pk['candidates']}
    return None, {}


def _score(c):
    return c.get('final_with_lookahead') if c.get('final_with_lookahead') is not None else c.get('final_score')


def ab(a, b, allowed=('catalog_options',)):
    reasons = comparable(a, b, allowed)
    if reasons: return dict(status='NOT_COMPARABLE', reasons=reasons)
    ra = {(r['customer_id'], r['date']): r for r in OR.dinner_rows(a['flow'])}
    rb = {(r['customer_id'], r['date']): r for r in OR.dinner_rows(b['flow'])}
    moves, stays = [], []
    for key in sorted(ra):
        x, y = ra[key], rb.get(key)
        if y is None: continue
        pid, date = key
        _, ca = _decision_at(a['flow']['plans'][pid], x)
        dec_b, cb = _decision_at(b['flow']['plans'][pid], y)
        sel_b = cb.get(dec_b['selected_action']) if dec_b else None
        dl_a, dl_b = ca.get('EXTERNAL_DELIVERY'), cb.get('EXTERNAL_DELIVERY')
        prior = (dl_b or {}).get('hotel_prior') or {}
        row = dict(customer_id=pid, date=date, before=x['kind'], after=y['kind'], before_venue=x['venue'], after_venue=y['venue'],
                   before_label=x['label'], after_label=y['label'], before_paid_krw=x['paid_krw'], after_paid_krw=y['paid_krw'],
                   prior_applied=prior.get('applied'), prior_reason=prior.get('reason'))
        if sel_b and dl_b:
            row.update(after_choice_score=_score(sel_b), delivery_score_after=_score(dl_b), delivery_score_before=_score(dl_a) if dl_a else None,
                       delivery_price_reference_krw=dict(A=(dl_a or {}).get('price_reference', {}).get('per_person_krw'), B=(dl_b or {}).get('price_reference', {}).get('per_person_krw')),
                       chosen_terms_after=[t for t in sel_b.get('terms', []) if t.get('value')][:8])
        if x['kind'] != y['kind'] or x['venue'] != y['venue']:
            row['change'] = '%s->%s' % (x['kind'], y['kind']); moves.append(row)
        elif x['kind'] == 'EXTERNAL_DELIVERY':
            best = max((c for k, c in cb.items() if k != 'EXTERNAL_DELIVERY' and c.get('world_allowed') and _score(c) is not None
                        and (c.get('meal_fraction') or 0) >= 0.8), key=_score, default=None)
            row.update(why_not_moved='DELIVERY_STILL_HIGHER', remaining_gap=round(_score(dl_b) - _score(best), 4) if best else None,
                       best_hotel_option=(best or {}).get('candidate_label'))
            stays.append(row)
    la, lb = a['ledger'], b['ledger']
    # where the hotel total change comes from (ledger rows, hotel revenue only; external delivery spend stays unknown)
    dec = dict(new_spend_from_delivery_movers=0, lost_to_delivery=0, same_venue_same_order_price_effect=0, same_venue_order_changed=0,
               venue_switch=0, members={})
    for key, x in ra.items():
        y = rb.get(key)
        if y is None: continue
        d = y['paid_krw'] - x['paid_krw']
        if x['kind'] == 'EXTERNAL_DELIVERY' and y['kind'] in ('HOTEL_RESTAURANT', 'ROOM_SERVICE'): k = 'new_spend_from_delivery_movers'
        elif y['kind'] == 'EXTERNAL_DELIVERY' and x['kind'] in ('HOTEL_RESTAURANT', 'ROOM_SERVICE'): k = 'lost_to_delivery'
        elif x['kind'] == y['kind'] == 'EXTERNAL_DELIVERY': continue
        elif x['venue'] == y['venue']: k = 'same_venue_same_order_price_effect' if x['label'] == y['label'] else 'same_venue_order_changed'
        else: k = 'venue_switch'
        dec[k] += d
        if d: dec['members'].setdefault(k, []).append(dict(customer_id=key[0], date=key[1], before=x['label'], after=y['label'], A=x['paid_krw'], B=y['paid_krw'], delta=d))
    dinner_delta = sum(v for k, v in dec.items() if k != 'members')
    total_delta = lb['totals']['paid_krw'] - la['totals']['paid_krw']
    per_customer = {}
    for pid in la['receipts']:
        ta = sum(r['paid_krw'] for r in la['receipts'][pid]['rows']); tb = sum(r['paid_krw'] for r in (lb['receipts'].get(pid) or {}).get('rows', []))
        if ta != tb: per_customer[pid] = dict(A=ta, B=tb, delta=tb - ta)
    dec.update(dinner_total=dinner_delta, other_rows_after_dinner_change=total_delta - dinner_delta, hotel_total=total_delta, per_customer=per_customer,
               note='other_rows_after_dinner_change = 저녁 선택이 바뀐 뒤 이어진 활동·야식 등 다른 원장 행의 변화')
    va, vb = a['summary']['dinner']['by_venue'], b['summary']['dinner']['by_venue']
    venues = sorted(set(va) | set(vb))
    return dict(status='COMPARABLE_SIMULATION_PAIR', interpretation='OBSERVED_SIMULATION_DIFFERENCE_UNDER_THE_ENGINE_ASSUMPTIONS_NOT_A_PREDICTED_PROMOTION_EFFECT',
                delivery_to_hotel=[m for m in moves if m['before'] == 'EXTERNAL_DELIVERY' and m['after'] in ('HOTEL_RESTAURANT', 'ROOM_SERVICE')],
                other_moves=[m for m in moves if not (m['before'] == 'EXTERNAL_DELIVERY' and m['after'] in ('HOTEL_RESTAURANT', 'ROOM_SERVICE'))],
                stayed_with_delivery=stays,
                dinner_kinds=dict(A=a['summary']['dinner']['by_kind'], B=b['summary']['dinner']['by_kind']),
                venue_dinner_revenue=[dict(venue=v, A=va.get(v, {}).get('paid_krw', 0), B=vb.get(v, {}).get('paid_krw', 0),
                                          delta=vb.get(v, {}).get('paid_krw', 0) - va.get(v, {}).get('paid_krw', 0)) for v in venues],
                hotel_total_krw=dict(A=la['totals']['paid_krw'], B=lb['totals']['paid_krw'], delta=lb['totals']['paid_krw'] - la['totals']['paid_krw']),
                external_delivery=dict(A=a['summary']['dinner']['by_kind']['EXTERNAL_DELIVERY'], B=b['summary']['dinner']['by_kind']['EXTERNAL_DELIVERY'],
                                       spend_krw=None, note='외부 배달 금액은 미상 · 호텔 매출 아님'),
                revenue_decomposition=dec, run_ids=dict(A=la['run_id'], B=lb['run_id']))


def experiment(spec):
    """One group A/B for the operator screen: A = current conditions, B = A + Pizza Hill dine-in mains discount."""
    disc = {sku: spec['pizza_hill_discount_percent'] for sku in pizza_hill_mains()}
    common = dict(prior=spec['behaviour_prior'], profile=spec['reference_profile'], seed=spec['seed'], start=spec['start_date'])
    a = run(base_request(spec['personas'], spec['duration'], **common))
    b = run(base_request(spec['personas'], spec['duration'], catalog_options=dict(discount_percent=disc), **common))
    if a.get('error') or b.get('error'): return dict(status='RUN_ERROR', A=a.get('error'), B=b.get('error'))
    return dict(status='DONE', spec=spec, lever=dict(kind='PIZZA_HILL_DINE_IN_MAIN_DISCOUNT', percent=spec['pizza_hill_discount_percent'], sku_count=len(disc)),
                A=lean(a), B=lean(b), ab=ab(a, b), continuity=continuity(a['flow']) if spec['duration'] != 'day_visit' else None,
                limits=['규칙 엔진 실행 결과이며 실제 프로모션 반응 예측이 아님', '배달 점수 비교 가격은 같은 시점 최저가 호텔 저녁(가상 기준)',
                        '외부 배달 금액은 미상 · 호텔 매출에 포함하지 않음', '고객 간 좌석·대기 상호작용 없음(독립 실행)'])


def lean(x):
    """What is kept from one condition in the lab output (the full flow stays in the private file)."""
    if x.get('error'): return x
    decs = [d for p in x['flow']['plans'].values() for d in (p.get('m4') or {}).get('decisions') or []]
    prior_traces = [c['hotel_prior'] for d in decs for c in (d.get('packet') or {}).get('candidates') or [] if c.get('hotel_prior')]
    return dict(request=x['request'], run_id=x['ledger']['run_id'], ledger_total_krw=x['ledger']['totals']['paid_krw'],
                ledger_checks=x['ledger']['checks'], summary=x['summary'], weights=x['weights'], estimates=x['estimates'],
                behaviour_prior=(x['flow'].get('visit') or {}).get('behaviour_prior'),
                prior_applied=sum(t['applied'] for t in prior_traces), prior_skipped={r: sum(1 for t in prior_traces if t.get('reason') == r) for r in {t.get('reason') for t in prior_traces}},
                dinner_rows=OR.dinner_rows(x['flow']), seconds=x['seconds'])


def sensitivity(ids, dur, c0):
    """Fixed coefficient grid (0.4 / 0.8 / 1.2, never fitted) x synthetic shares (B 0.20 / A 0.35). Checks: the
    delivery candidate's added score grows with coefficient and share; customers whose personal evidence protects
    them keep their baseline dinner; group delivery counts move in the same direction."""
    base = {(r['customer_id'], r['date']): r for r in OR.dinner_rows(c0['flow'])}
    rows = []
    for profile, share in (('synthetic_hotel_format_b_v1', 0.20), ('synthetic_delivery_high_v1', 0.35)):
        for coef in (0.4, 0.8, 1.2):
            x = run(base_request(ids, dur, 'HOTEL_PRIOR_V1', profile, coefficient=coef))
            traces = {}
            for pid, plan in x['flow']['plans'].items():
                for d in (plan.get('m4') or {}).get('decisions') or []:
                    for c in (d.get('packet') or {}).get('candidates') or []:
                        if c.get('hotel_prior'): traces.setdefault(pid, []).append(c['hotel_prior'])
            protected = sorted(pid for pid, ts in traces.items() if all(t.get('reason') == 'PERSONAL_PRACTICAL_ALT_EVIDENCE_PROTECTED' for t in ts))
            now = {(r['customer_id'], r['date']): r for r in OR.dinner_rows(x['flow'])}
            changed_protected = sorted({k[0] for k in now if k[0] in protected and (now[k]['kind'], now[k]['venue'], now[k]['label']) != (base[k]['kind'], base[k]['venue'], base[k]['label'])})
            deltas = sorted({t['delta'] for ts in traces.values() for t in ts if t.get('applied')})
            rows.append(dict(profile=profile, share=share, coefficient=coef, added_score=deltas, delivery_evenings=x['summary']['dinner']['by_kind']['EXTERNAL_DELIVERY'],
                             evenings=x['summary']['dinner']['evenings'], to_delivery=sorted({k[0] for k in now if now[k]['kind'] == 'EXTERNAL_DELIVERY' and base[k]['kind'] != 'EXTERNAL_DELIVERY'}),
                             protected_customers=len(protected), protected_changed=changed_protected, ledger_total_krw=x['ledger']['totals']['paid_krw'],
                             in_hotel_dinner_krw=x['summary']['dinner']['in_hotel_dinner_revenue_krw']))
            print('sens', profile, coef, rows[-1]['delivery_evenings'], flush=True)
            del x
    mono = all(a['delivery_evenings'] <= b['delivery_evenings'] for a, b in zip(rows, rows[1:]) if a['profile'] == b['profile'])
    by_share = all(r1['delivery_evenings'] <= r2['delivery_evenings'] for r1 in rows for r2 in rows if r1['coefficient'] == r2['coefficient'] and r1['share'] < r2['share'])
    return dict(rows=rows, monotonic_in_coefficient=mono, monotonic_in_share=by_share, protected_choices_preserved=all(not r['protected_changed'] for r in rows),
                note='계수 격자는 실행 전에 고정했고 목표 비율에 맞춰 고르지 않음. 0.8은 엔진의 기존 실용 대안 계수.')


def main():
    """Runs the conditions one at a time and keeps at most three full flows in memory (the result file holds the
    lean summaries, comparisons and traces; full flows are not written)."""
    out = sys.argv[1]
    args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
    dur = args.get('--duration', 'stay_1')
    ids = args.get('--personas', '').split(',') if args.get('--personas') else sorted(VR.IR.allowed_personas(VR.AD.DEMO))
    discount = {sku: 20 for sku in pizza_hill_mains()}
    prior = ('behaviour_prior', 'reference_profile')
    result = dict(duration=dur, personas=ids, conditions={}, statistics_on_off={})

    def step(name, req):
        x = run(req); print(name, x.get('seconds'), (x.get('summary') or {}).get('dinner', {}).get('by_kind'), flush=True)
        result['conditions'][name] = lean(x); return x
    c0 = step('C0_baseline', base_request(ids, dur))
    result['continuity'] = continuity(c0['flow'], c0['ledger'])
    result['venue_concentration'] = venue_bias(c0['flow'])
    if args.get('--sensitivity'):
        result['sensitivity'] = sensitivity(ids, dur, c0)
        json.dump(result, open(out, 'w'), ensure_ascii=False); print('written (sensitivity)', out); return
    for name, profile in (('C1_prior_external', 'external'), ('C3_prior_synthetic_format_b', 'synthetic_hotel_format_b_v1')):
        x = step(name, base_request(ids, dur, 'HOTEL_PRIOR_V1', profile))
        result['statistics_on_off'][name] = ab(c0, x, prior); del x
    c2 = step('C2_prior_synthetic_high', base_request(ids, dur, 'HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1'))
    result['statistics_on_off']['C2_prior_synthetic_high'] = ab(c0, c2, prior); del c0
    result['continuity_prior_on'] = continuity(c2['flow'], c2['ledger'])
    b = step('B_pizza_hill_20_off', base_request(ids, dur, 'HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1', dict(discount_percent=discount)))
    result['ab_pizza_hill'] = ab(c2, b)
    json.dump(result, open(out, 'w'), ensure_ascii=False)
    print('written', out)


if __name__ == '__main__':
    main()
