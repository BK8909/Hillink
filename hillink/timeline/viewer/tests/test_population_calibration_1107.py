"""General hotel simulator research layer (no key, no cost; rules engine only).

Reference contract (source classes incl. synthetic test data, denominators, segments), composition weights
(normalized, ESS, cap, unsupported segments, unknown segments excluded, behaviour never a weight target),
the hotel behaviour prior (personal evidence first, traced, only the evening-level delivery share accepted),
and the operator A/B (same customers and inputs; only the Pizza Hill price changes; movers traced to scores).
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import operating_reference as OR  # noqa: E402
import population as POP  # noqa: E402
import visit_run as VR  # noqa: E402
from operator_choice.autonomy_v1 import hotel_prior as HP  # noqa: E402


def entry(**kw):
    e = dict(metric_id='delivery.evening_share_per_stay', source_class='HOTEL_MEASURED', value=0.3, period='2026-09~10', segment='all',
             sample_size=900, source=dict(kind='배달 반입 기록'))
    e.update(kw); return e


# ------------------------------------------------------------------ reference contract
@pytest.mark.parametrize('bad,err', [
    (dict(source_class='SYNTHETIC_TEST', sample_size=None), 'SYNTHETIC_LABEL_REQUIRED'),
    (dict(synthetic_label='가상'), 'SYNTHETIC_VALUE_CANNOT_BE_HOTEL_MEASURED'),
    (dict(source_class='UNKNOWN'), 'UNKNOWN_WITH_VALUE'),
    (dict(metric_id='composition.party_size_share', segment='party_size:7'), 'UNSUPPORTED_SEGMENT:party_size:7'),
    (dict(level='TEAM_STAY'), 'DENOMINATOR_LEVEL_MISMATCH:TEAM_STAY!=TEAM_EVENING'),
    (dict(metric_id='fnb.in_hotel_dinner_revenue_per_stay_team', value=0.5), 'VALUE_RANGE'),
    (dict(sample_size=None), 'MISSING_SAMPLE_SIZE')])
def test_reference_entries_are_rejected_for_contract_errors(bad, err):
    assert err in OR.validate(entry(**bad))


def test_breakfast_external_figures_are_context_only_after_correction():
    used, _ = OR.load()
    germain = [e for e in used if (e.get('source') or {}).get('publisher') == 'Hotelier Magazine']
    assert len(germain) == 2 and {e['metric_id'] for e in germain} == {'breakfast.hotel_share_by_sales_mode'}
    assert all(e['comparability'] == 'DENOMINATOR_UNCONFIRMED_CONTEXT_ONLY' and e['corrected_from_metric'] for e in germain)
    assert OR.resolve('breakfast.use_share_when_included', entries=used) is None   # hotel-measured only now
    assert OR.resolve('delivery.evening_share_per_stay', entries=used)['source_class'] == 'UNKNOWN'


def test_profiles_and_provenance():
    assert OR.load(profile='none') == ([], [])
    used, rejected = OR.load(profile='synthetic_delivery_high_v1')
    assert not rejected and OR.resolve('delivery.evening_share_per_stay', entries=used)['source_class'] == 'SYNTHETIC_TEST'
    prov = OR.provenance('synthetic_delivery_high_v1')
    assert [f['source_set'] for f in prov['files']] == ['EXTERNAL_RESEARCH_2026-11-07', 'SYNTHETIC_DELIVERY_HIGH_HOTEL_V1'] and all(len(f['sha256']) == 64 for f in prov['files'])
    with pytest.raises(ValueError, match='HOTEL_REFERENCE_FILE_REQUIRED'):
        OR.load(profile='hotel')
    with pytest.raises(ValueError, match='UNKNOWN_REFERENCE_PROFILE'):
        OR.load(profile='made_up')


# ------------------------------------------------------------------ behaviour prior resolution
def write(tmp_path, entries, name='hotel.json'):
    f = tmp_path / name; f.write_text(json.dumps(dict(schema=OR.SCHEMA, source_set='TEST', entries=entries), ensure_ascii=False)); return str(f)


def test_coefficient_only_from_the_fixed_grid():
    assert VR.resolve_behaviour_prior('HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1', 1.2)['coefficient'] == 1.2
    with pytest.raises(ValueError, match='COEFFICIENT_NOT_IN_FIXED_SENSITIVITY_GRID'):
        VR.resolve_behaviour_prior('HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1', 2.37)


def test_prior_resolution_states(tmp_path, monkeypatch):
    assert VR.resolve_behaviour_prior('OFF', 'external') is None
    assert VR.resolve_behaviour_prior('HOTEL_PRIOR_V1', 'external')['status'] == 'NO_COMPARABLE_STATISTIC'
    syn = VR.resolve_behaviour_prior('HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1')
    assert syn['status'] == 'APPLICABLE' and syn['reference']['value'] == 0.35 and syn['reference']['source_class'] == 'SYNTHETIC_TEST'
    # a hotel file with only the team-level share is a different denominator: the evening prior is refused
    monkeypatch.setenv('HILLINK_OPERATING_REFERENCE', write(tmp_path, [entry(metric_id='delivery.team_share_per_stay', value=0.4)]))
    assert VR.resolve_behaviour_prior('HOTEL_PRIOR_V1', 'hotel')['status'] == 'DENOMINATOR_MISMATCH_ONLY_DELIVERY_TEAM_SHARE_PER_STAY'
    # the hotel's own evening share replaces nothing else and is used as is
    monkeypatch.setenv('HILLINK_OPERATING_REFERENCE', write(tmp_path, [entry(value=0.27)]))
    hotel = VR.resolve_behaviour_prior('HOTEL_PRIOR_V1', 'hotel')
    assert hotel['status'] == 'APPLICABLE' and hotel['reference']['source_class'] == 'HOTEL_MEASURED' and hotel['reference']['value'] == 0.27
    with pytest.raises(ValueError):
        VR.resolve_behaviour_prior('MAKE_IT_35', 'external')


def prior_env(status='APPLICABLE', value=0.35):
    return {'HILLINK_BEHAVIOUR_PRIOR_JSON': json.dumps(dict(policy='HOTEL_PRIOR_V1', status=status, coefficient=0.8,
                                                            reference=dict(metric_id=HP.METRIC, value=value, source_class='SYNTHETIC_TEST')))}


DELIVERY = dict(id='EXTERNAL_DELIVERY', venue='EXTERNAL_DELIVERY')


def test_prior_off_leaves_no_trace():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('HILLINK_BEHAVIOUR_PRIOR_JSON', None)
        assert HP.adjustment(DELIVERY, [], dict(time=1080), {}, 0) == (0.0, None)


@pytest.mark.parametrize('ctx,terms,level,reason', [
    (dict(time=1080), [], 0.4, 'PERSONAL_PRACTICAL_ALT_EVIDENCE_PROTECTED'),
    (dict(time=1080), [dict(fact_ids=['F1'], value=-0.5)], 0, 'SOURCE_LINKED_NEGATIVE_EVIDENCE_PROTECTED'),
    (dict(time=1080, direct_avoid_venues={'EXTERNAL_DELIVERY': True}), [], 0, 'SOURCE_LINKED_NEGATIVE_EVIDENCE_PROTECTED'),
    (dict(time=720), [], 0, 'NOT_A_DINNER_DECISION')])
def test_personal_evidence_and_conditions_come_first(ctx, terms, level, reason):
    with patch.dict(os.environ, prior_env()):
        delta, trace = HP.adjustment(DELIVERY, terms, ctx, {}, level)
    assert delta == 0 and trace['applied'] is False and trace['reason'] == reason


def test_prior_applies_with_the_existing_coefficient_only_to_delivery():
    with patch.dict(os.environ, prior_env(value=0.35)):
        delta, trace = HP.adjustment(DELIVERY, [], dict(time=1080), {}, 0)
        assert delta == pytest.approx(0.28) and trace['applied'] and trace['coefficient'] == 0.8
        assert HP.adjustment(dict(id='PIZZA_HILL', venue='PIZZA_HILL'), [], dict(time=1080), {}, 0) == (0.0, None)
    with patch.dict(os.environ, prior_env(status='NO_COMPARABLE_STATISTIC')):
        assert HP.adjustment(DELIVERY, [], dict(time=1080), {}, 0)[1]['reason'] == 'NO_COMPARABLE_STATISTIC'


# ------------------------------------------------------------------ composition weights
def fake(sizes, rel=None, kinds=None):
    plans, visits = {}, {}
    for i, n in enumerate(sizes):
        pid = 'T%02d' % i
        kind = (kinds or {}).get(pid, 'HOTEL_RESTAURANT')
        dinner = dict(visit_date='2026-11-13', meal='dinner', act='turn_dinner', loc='PIZZA_HILL', t0=1080,
                      basis=dict(charge=dict(status='유료', krw=50000, sku_contract=dict(venue_id='PIZZA_HILL'))))
        if kind == 'EXTERNAL_DELIVERY':
            dinner = dict(visit_date='2026-11-13', meal='dinner', act='turn_dinner', loc='VISTA_ROOM', t0=1080,
                          basis=dict(charge=dict(external_spend=dict(amount_krw=None))))
        plans[pid] = dict(scenes=[dinner, dict(visit_date='2026-11-14', act='checkout', loc='LOBBY')])
        visits[pid] = dict(stay=True, party_size=n, rel=(rel or {}).get(pid))
    return dict(plans=plans, visits=visits)


COMP = [dict(metric_id='composition.party_size_share', source_class='SYNTHETIC_TEST', value=v, period='합성', segment=s, synthetic_label='t', source=dict(kind='합성'), source_set='S')
        for s, v in (('party_size:1', 0.2), ('party_size:2', 0.5), ('party_size:3+', 0.3))]


def test_weights_match_composition_and_record_ess():
    w = POP.weights(fake([1, 2, 2, 2, 2, 3, 3, 2, 2, 2]), COMP)
    assert w['status'].startswith('OK') and w['sample_counts'] == {'party_size:1': 1, 'party_size:2': 7, 'party_size:3+': 2}
    ws = w['weights']; assert abs(sum(ws.values()) / len(ws) - 1) < 1e-3
    share = lambda seg: sum(x for k, x in ws.items() if POP.segments(fake([1, 2, 2, 2, 2, 3, 3, 2, 2, 2]))[k]['party_size'] == seg) / sum(ws.values())
    assert share('party_size:1') == pytest.approx(0.2, abs=1e-3) and share('party_size:3+') == pytest.approx(0.3, abs=1e-3)
    assert 0 < w['effective_sample_size'] <= 10 and w['target_share_not_represented'] == 0


def test_weights_are_capped_and_missing_segments_reported():
    w = POP.weights(fake([1] + [2] * 29), COMP, cap=3.0)
    assert w['capped'] and w['max_weight'] <= 3.0 + 1e-6
    assert w['unsupported_segments'] == ['party_size:3+'] and w['target_share_not_represented'] == pytest.approx(0.3)


def test_weights_refuse_bad_targets_and_ignore_behaviour():
    assert POP.weights(fake([2, 2]), COMP[:2])['reason'] == 'TARGET_SHARES_DO_NOT_SUM_TO_ONE'
    mixed = [dict(COMP[0], source_set='X')] + COMP[1:]
    assert POP.weights(fake([1, 2, 3]), mixed)['reason'] == 'MIXED_SOURCE_SETS_FOR_ONE_COMPOSITION'
    assert POP.weights(fake([2, 2]), [])['reason'] == 'NO_COMPOSITION_REFERENCE'
    assert POP.weights(fake([1, 2, 3]), [dict(COMP[0], period='2025')] + COMP[1:])['reason'] == 'MIXED_PERIODS_FOR_ONE_COMPOSITION'
    a = POP.weights(fake([1, 2, 2, 3]), COMP)
    b = POP.weights(fake([1, 2, 2, 3], kinds={'T01': 'EXTERNAL_DELIVERY', 'T03': 'EXTERNAL_DELIVERY'}), COMP)
    assert a['weights'] == b['weights']   # behaviour outcomes never move the weights


def test_unknown_companion_is_excluded_not_guessed():
    comp = [dict(metric_id='composition.companion_type_share', source_class='SYNTHETIC_TEST', value=v, period='합성', segment=s, synthetic_label='t', source=dict(kind='합성'), source_set='S')
            for s, v in (('companion:family', 0.4), ('companion:couple', 0.6), ('companion:friends', 0.0), ('companion:solo', 0.0))]
    w = POP.weights(fake([2, 2, 3], rel={'T00': 'couple', 'T01': 'group', 'T02': 'family_kids'}), comp, 'companion')
    assert w['excluded_unknown_segment'] == ['T01'] and set(w['weights']) == {'T00', 'T02'}


def test_estimates_raw_and_weighted_and_delivery_is_not_revenue():
    r = fake([1, 2, 2, 3], kinds={'T00': 'EXTERNAL_DELIVERY'})
    s = OR.aggregate(r)
    assert s['dinner']['by_kind']['EXTERNAL_DELIVERY'] == 1 and s['dinner']['in_hotel_dinner_revenue_krw'] == 150000
    e = POP.estimates(r, POP.weights(r, COMP))
    assert e['metrics']['delivery.evening_share']['raw'] == 0.25 and e['metrics']['delivery.evening_share']['weighted'] != 0.25
    assert POP.estimates(r)['metrics']['fnb.dinner_revenue_per_stay_team']['weighted'] is None


def test_small_or_day_runs_explain_why_rates_are_missing():
    day = dict(plans={'X': dict(scenes=[dict(visit_date='2026-11-13', meal='dinner', loc='PIZZA_HILL', act='d')])}, visits={'X': dict(stay=False, party_size=3)})
    notes = OR.aggregate(day)['sample_notes']
    assert any(n.startswith('NO_STAY_TEAM') for n in notes) and any(n.startswith('NO_STAY_MORNING') for n in notes) and any(n.startswith('TEAMS_BELOW') for n in notes)


# ------------------------------------------------------------------ engine runs (rules, no model): prior ON/OFF and the operator A/B
HAS = {'A03', 'A04', 'A05'} <= set(VR.AD.load_inputs()[0])
RUNS = {}


def lab_run(prior, profile, discount=None):
    import population_lab as PL
    key = (prior, profile, bool(discount))
    if key not in RUNS:
        RUNS[key] = PL.run(PL.base_request(['A03', 'A04', 'A05'], 'stay_1', prior, profile, dict(discount_percent=discount) if discount else None))
    return RUNS[key]


@pytest.mark.skipif(not HAS, reason='approved execution inputs unavailable')
def test_prior_off_keeps_the_previous_run_identity_and_choices():
    import population_lab as PL
    off = lab_run('OFF', 'external')
    plain = VR.run_visit({k: v for k, v in off['request'].items() if k not in ('behaviour_prior', 'reference_profile')})
    assert plain['visit']['visit_id'] == off['flow']['visit']['visit_id']
    ext = lab_run('HOTEL_PRIOR_V1', 'external')
    assert ext['flow']['visit']['behaviour_prior']['status'] == 'NO_COMPARABLE_STATISTIC'
    pair = PL.ab(off, ext, ('behaviour_prior', 'reference_profile'))
    assert pair['status'] == 'COMPARABLE_SIMULATION_PAIR' and not pair['delivery_to_hotel'] and not pair['other_moves']


@pytest.mark.skipif(not HAS, reason='approved execution inputs unavailable')
def test_synthetic_prior_moves_only_customers_without_personal_evidence_and_ab_traces_movers():
    import population_lab as PL
    off, on = lab_run('OFF', 'external'), lab_run('HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1')
    change = PL.ab(off, on, ('behaviour_prior', 'reference_profile'))
    to_delivery = {m['customer_id'] for m in change['other_moves'] if m['after'] == 'EXTERNAL_DELIVERY'}
    assert to_delivery and 'A03' not in to_delivery   # A03's restaurant lead exceeds the prior
    traces = [c['hotel_prior'] for p in on['flow']['plans'].values() for d in p['m4']['decisions'] for c in d['packet'].get('candidates', []) if c.get('hotel_prior')]
    assert traces and all(t['reference']['source_class'] == 'SYNTHETIC_TEST' for t in traces)
    assert on['ledger']['external_spend']['hotel_revenue_krw'] == 0 and on['ledger']['external_spend']['count'] == len(to_delivery)
    b = lab_run('HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1', {s: 20 for s in PL.pizza_hill_mains()})
    pair = PL.ab(on, b)
    assert pair['status'] == 'COMPARABLE_SIMULATION_PAIR'
    for m in pair['delivery_to_hotel']:
        assert m['after_venue'] == 'PIZZA_HILL' and m['after_choice_score'] >= m['delivery_score_after'] and m['prior_applied'] is True
    assert pair['hotel_total_krw']['delta'] == b['ledger']['totals']['paid_krw'] - on['ledger']['totals']['paid_krw']
    assert pair['hotel_total_krw']['A'] == on['ledger']['totals']['paid_krw']   # ledger actual totals, not weighted estimates
    assert pair['external_delivery']['spend_krw'] is None
    dec = pair['revenue_decomposition']
    assert dec['hotel_total'] == pair['hotel_total_krw']['delta'] == dec['dinner_total'] + dec['other_rows_after_dinner_change']
    assert dec['new_spend_from_delivery_movers'] == sum(m['after_paid_krw'] for m in pair['delivery_to_hotel'])
    assert dec['same_venue_same_order_price_effect'] <= 0   # the same Pizza Hill order costs less after the discount


@pytest.mark.skipif(not HAS, reason='approved execution inputs unavailable')
def test_ab_refuses_changed_inputs_or_other_customers():
    import population_lab as PL
    on = lab_run('HOTEL_PRIOR_V1', 'synthetic_delivery_high_v1')
    off = lab_run('OFF', 'external')
    assert 'NON_EXPERIMENT_INPUT_CHANGED:behaviour_prior,reference_profile' in PL.ab(off, on)['reasons'][0]
    other = dict(on, flow=dict(on['flow'], plans={k: v for k, v in on['flow']['plans'].items() if k != 'A05'}))
    assert 'CUSTOMER_SCOPE_MISMATCH' in PL.comparable(on, other)
    assert 'SAME_RUN_ID' in PL.comparable(on, on)


@pytest.mark.skipif(not HAS, reason='approved execution inputs unavailable')
def test_prior_is_refused_with_a_model_policy():
    r = VR.run_visit(dict(personas=['A05'], duration='stay_1', seed=0, behaviour_prior='HOTEL_PRIOR_V1', reference_profile='synthetic_delivery_high_v1',
                          hybrid_policy='LLM_AUTONOMOUS_CUSTOMER_V19LS'))
    assert r.get('code') == 'E_VISIT_BEHAVIOUR_PRIOR_RULES_ONLY'
