"""Operating reference interface and operator aggregate (no key, no cost).

References: schema validation, source-class precedence (a hotel-measured value supplied via HILLINK_OPERATING_REFERENCE
replaces the external proxy for the same metric), the shipped template is rejected until filled, and references never
reach an agent. Aggregate: breakfast person-mornings (entitled / included use / paid / unused / skip reasons) and paid
revenue that matches the ledger, with included breakfasts adding no revenue.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import operating_reference as OR  # noqa: E402


def entry(**kw):
    e = dict(metric_id='breakfast.use_share_when_included', source_class='HOTEL_MEASURED', value=0.81, period='2026-01~2026-09',
             segment='all', sample_size=12000, unit='PERSON_MORNING', source=dict(kind='HOTEL_POS_AND_PMS', title='walkerhill breakfast covers'))
    e.update(kw); return e


def test_shipped_external_entries_are_valid_and_labelled():
    used, rejected = OR.load()
    assert used and not rejected
    # 2026-11-07 correction: delivery has no public observation (UNKNOWN, no value); external breakfast figures are context only
    assert {e['source_class'] for e in used} == {'EXTERNAL_RESEARCH', 'UNKNOWN'}
    assert all(e['source'].get('url') and e.get('period') and e.get('comparability') for e in used if e['source_class'] == 'EXTERNAL_RESEARCH')
    assert all(e.get('value') is None for e in used if e['source_class'] == 'UNKNOWN')


@pytest.mark.parametrize('bad,err', [
    (dict(value=1.4), 'VALUE_RANGE'), (dict(value=None), 'NO_VALUE'), (dict(period=None), 'MISSING_PERIOD'),
    (dict(sample_size=None), 'MISSING_SAMPLE_SIZE'), (dict(source={}), 'MISSING_SOURCE_KIND'), (dict(source_class='GUESS'), 'SOURCE_CLASS'),
    (dict(value=None, low=0.8, high=0.6), 'LOW_ABOVE_HIGH'), (dict(metric_id='breakfast.made_up'), 'UNKNOWN_METRIC:breakfast.made_up')])
def test_invalid_entries_are_rejected(bad, err):
    assert err in OR.validate(entry(**bad))


def test_unknown_class_needs_no_value():
    assert OR.validate(entry(source_class='UNKNOWN', value=None, sample_size=None)) == []


def test_unfilled_template_is_rejected_never_used():
    used, rejected = OR.load(HERE / 'operating_reference/hotel_measured_template.json')
    assert not [e for e in used if e['source_class'] == 'HOTEL_MEASURED']
    assert rejected and all(e['errors'] for e in rejected)


def test_hotel_measured_overrides_external_for_the_same_metric(tmp_path, monkeypatch):
    f = tmp_path / 'walkerhill.json'
    f.write_text(json.dumps(dict(schema=OR.SCHEMA, entries=[entry()])), encoding='utf-8')
    # 2026-11-07 correction: no external value is mapped to the entitled-guest denominator any more (hotel-measured only)
    assert OR.resolve('breakfast.use_share_when_included') is None
    monkeypatch.setenv('HILLINK_OPERATING_REFERENCE', str(f))
    after = OR.resolve('breakfast.use_share_when_included')
    assert after['source_class'] == 'HOTEL_MEASURED' and after['value'] == 0.81
    # a metric the hotel did not supply keeps the external context source
    assert {e['source_class'] for e in OR.load()[0] if e['metric_id'] == 'breakfast.hotel_share_by_sales_mode'} == {'EXTERNAL_RESEARCH'}
    rows = {r['metric_id']: r for r in OR.compare({'breakfast.included_use_rate': 0.9}, teams=40)}
    r = rows['breakfast.use_share_when_included']
    assert r['reference']['source_ko'] == '호텔 실측' and r['status'] == 'ABOVE_REFERENCE'
    assert OR.compare({'breakfast.included_use_rate': 0.83}, teams=40)[0]['status'] == 'WITHIN_REFERENCE'


def test_small_runs_and_context_metrics_are_not_judged(tmp_path, monkeypatch):
    rows = {r['metric_id']: r for r in OR.compare({'breakfast.included_use_rate': 0.2}, teams=3)}
    assert rows['breakfast.use_share_when_included']['status'] == 'NO_REFERENCE'   # hotel-measured only
    f = tmp_path / 'h.json'; f.write_text(json.dumps(dict(schema=OR.SCHEMA, entries=[entry()])), encoding='utf-8')
    monkeypatch.setenv('HILLINK_OPERATING_REFERENCE', str(f))
    rows = {r['metric_id']: r for r in OR.compare({'breakfast.included_use_rate': 0.2}, teams=3)}
    assert rows['breakfast.use_share_when_included']['status'] == 'SAMPLE_TOO_SMALL'
    assert rows['breakfast.habit_always_share']['status'] in ('CONTEXT_ONLY', 'NOT_COMPARABLE')
    assert rows['breakfast.included_room_share']['status'] == 'CONTEXT_ONLY'


def test_references_never_reach_the_agent_layer():
    root = HERE / 'experiments/persona_live'
    hits = [p for p in root.rglob('*.py') if 'operating_reference' in p.read_text(encoding='utf-8', errors='ignore')]
    assert hits == []


# ------------------------------------------------------------------ aggregate on real engine runs
import visit_run as VR  # noqa: E402
import ledger_service as LS  # noqa: E402

HAS_INPUT = 'A05' in VR.AD.load_inputs()[0]


def run(req):
    flow = VR.run_visit(req); assert 'error' not in flow
    led = LS.register_visit(flow, req)
    buffet = sum(r['paid_krw'] for c in led['receipts'].values() for r in c['rows'] if r.get('act') == 'turn_breakfast')
    return OR.aggregate(flow), buffet


A05 = dict(personas=['A05'], duration='stay_2', event_mode='none', seed=0, start_date='2026-10-24')


@pytest.mark.skipif(not HAS_INPUT, reason='approved A05 execution inputs unavailable')
def test_catalog_run_two_of_three_covered():
    s, buffet = run(dict(A05, behavior_engine='m4_c01', catalog_policy='C01_HOTEL_CATALOG_V1')); b = s['breakfast']
    assert (s['teams'], s['persons'], s['team_mornings']) == (1, 3, 2)
    assert b['entitled'] == 4 and b['not_entitled'] == 2
    assert b['diners'] == b['included_used'] + b['paid_diners'] + b['diners_split_unknown']
    assert b['unused_entitlement'] == b['entitled'] - b['included_used']
    assert b['paid_revenue_krw'] == buffet   # included breakfasts add nothing; extra payment matches the ledger
    assert s['basis'].startswith('SIMULATION_AGGREGATE_NOT_OBSERVED')


@pytest.mark.skipif(not HAS_INPUT, reason='approved A05 execution inputs unavailable')
def test_legacy_set_price_does_not_invent_a_paid_split():
    s, buffet = run(A05); b = s['breakfast']
    assert b['paid_revenue_krw'] == buffet == 170000
    assert b['diners'] == b['diners_split_unknown'] == 6 and b['paid_diners'] == 0 and b['included_used'] == 0
    assert b['entitlement_unknown_mornings'] == 2 and s['simulated']['breakfast.included_use_rate'] is None


def p2_visit(tmp_path, pick):
    from test_v19ls_party_breakfast_1107 import visit
    seen = {}; orig = LS.register_visit
    def keep(flow, req): seen['flow'] = flow; return orig(flow, req)
    with patch.object(LS, 'register_visit', keep):
        visit(tmp_path, pick)
    return OR.aggregate(seen['flow'])


def test_partial_breakfast_two_covered_eat_one_rests(tmp_path):
    b = p2_visit(tmp_path, 'D2')['breakfast']
    assert (b['entitled'], b['diners'], b['included_used'], b['paid_diners'], b['paid_revenue_krw'], b['unused_entitlement']) == (2, 2, 2, 0, 0, 0)


def test_partial_breakfast_three_eat_one_paid(tmp_path):
    b = p2_visit(tmp_path, 'ALL')['breakfast']
    assert (b['diners'], b['included_used'], b['paid_diners']) == (3, 2, 1)
    assert b['paid_revenue_krw'] == 85000   # only the uncovered guest; the two included breakfasts are not counted again


def test_skip_keeps_entitlement_unused_with_a_reason(tmp_path):
    b = p2_visit(tmp_path, 'SKIP')['breakfast']
    assert (b['diners'], b['unused_entitlement'], b['skipped_team_mornings']) == (0, 2, 1)
    assert sum(b['skip_reasons'].values()) == 1 and b['decided_by']


def test_day_visits_do_not_enter_per_stay_service_rates():
    day = dict(plans={'X': dict(scenes=[dict(visit_date='2026-11-09', loc='POOL_INDOOR', act='pool'), dict(visit_date='2026-11-09', meal='dinner', act='dinner', loc='PIZZA_HILL')])},
               visits={'X': dict(party_size=2, stay=False)})
    s = OR.aggregate(day)
    assert s['services']['stay_teams'] == 0 and s['services']['pool_teams'] == 0 and s['services']['dinner_evenings'] == 0
    assert s['simulated']['pool.team_use_rate'] is None and s['simulated']['dinner.in_hotel_capture_rate'] is None
    assert s['team_mornings'] == 0 and s['breakfast']['diners'] == 0
