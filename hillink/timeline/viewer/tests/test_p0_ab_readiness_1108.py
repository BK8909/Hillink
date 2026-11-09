"""운영 A/B: 화면의 실행(서버 기록) 기준 가능 여부 판정과 B 요청 구성 (2026-11-08 P0)."""
import copy, sys
from pathlib import Path
from unittest import mock
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'experiments/persona_live'))
import app  # noqa: E402

BASE = dict(personas=['A01', 'A04'], duration='stay_1', event_mode='none', seed=0, start_date='2026-10-24', judgment_mode='rules',
            behavior_engine='m4_c01', catalog_policy='C01_HOTEL_CATALOG_V1', visit_conditions={'A01': {'building': 'GRAND', 'party_size': 3}},
            simulation_mode='independent', include_ledger=True)
FLOW = dict(ledger=dict(run_id='r' * 64, checks=dict(receipts_equal_L4_L3_L2_L1=True)), plans={'A01': {}, 'A04': {}}, operating_summary={})


def ready(req=None, flow=None, allowed=('A01', 'A04')):
    src = dict(request=copy.deepcopy(req or BASE), flow=copy.deepcopy(flow or FLOW))
    with mock.patch.object(app.agent_jobs, 'source', return_value=src):
        return app.ab_readiness('r' * 64, set(allowed))


def test_displayed_rules_stay_with_catalog_is_available_and_keeps_its_conditions():
    r = ready()
    assert r['available'] and r['conditions']['personas'] == ['A01', 'A04'] and r['conditions']['visit_conditions'] == ['A01']


def test_unavailable_runs_name_the_actual_reason():
    """2026-11-09: day visits and longer stays are no longer blocked; AI runs need a live B (never a replayed answer)."""
    assert ready(dict(BASE, duration='day_visit'))['available'] and ready(dict(BASE, duration='stay_3'))['available']
    with mock.patch.object(app.visit_execution, 'live_status', return_value=(False, 'CALL_LIMIT')):
        for req in (dict(BASE, judgment_mode='replay', hybrid_policy='LLM_AUTONOMOUS_CUSTOMER_V19LS_INT4'),
                    dict(BASE, judgment_mode='live', hybrid_policy='LLM_AUTONOMOUS_CUSTOMER_V19LS')):
            r = ready(req)
            assert not r['available'] and r['reason'] == 'LIVE_REQUIRED_FOR_B' and r['conditions']['live_reason'] == 'CALL_LIMIT'
    with mock.patch.object(app.visit_execution, 'live_status', return_value=(True, None)):
        r = ready(dict(BASE, judgment_mode='replay', hybrid_policy='LLM_AUTONOMOUS_CUSTOMER_V19LS_INT4'))
        assert r['available'] and r['conditions']['b_execution'] == 'NEW_LIVE_JUDGMENT'
    for req, reason in [({k: v for k, v in BASE.items() if k != 'catalog_policy'}, 'CATALOG_PRICING_REQUIRED'),
                        (dict(BASE, simulation_mode='shared_world'), 'SHARED_WORLD_NOT_SUPPORTED')]:
        r = ready(req)
        assert not r['available'] and r['reason'] == reason and r['message'], (reason, r)
    bad = copy.deepcopy(FLOW); bad['ledger']['checks']['receipts_equal_L4_L3_L2_L1'] = False
    assert ready(flow=bad)['reason'] == 'BASE_LEDGER_NOT_BALANCED'
    assert ready(allowed=('A01',))['reason'] == 'CUSTOMER_SCOPE_INVALID'


def test_levers_come_from_the_catalog_and_are_validated():
    lv = {x['venue_id']: x for x in app.ab_levers()}
    assert {'PIZZA_HILL', 'GEUMRYONG', 'THE_BUFFET', 'MYONGWOLGWAN'} <= set(lv)
    assert lv['GEUMRYONG']['discountable'] and lv['GEUMRYONG']['opening']['official'] == '18:00'
    assert lv['PIZZA_HILL']['opening'] is None   # opening time is connected for the research venues only
    co, lever = app.ab_lever_options(BASE, dict(kind='discount', venue_id='GEUMRYONG', percent=20))
    assert lever['sku_count'] == len(lv['GEUMRYONG']['discountable']) and set(co['discount_percent'].values()) == {20}
    import pytest
    for bad, code in [(dict(kind='discount', venue_id='NOWHERE', percent=20), 'UNKNOWN_VENUE'), (dict(kind='discount', venue_id='GEUMRYONG', percent=70), 'DISCOUNT_PERCENT_5_TO_50'),
                      (dict(kind='discount', venue_id='GEUMRYONG', percent=20, sku_ids=['HC-NOT-REAL']), 'NO_DISCOUNTABLE_PRODUCT'),
                      (dict(kind='opening', venue_id='PIZZA_HILL', open='17:00'), 'OPENING_NOT_SUPPORTED')]:
        with pytest.raises(ValueError, match=code): app.ab_lever_options(BASE, bad)
    sku = lv['GEUMRYONG']['discountable'][0]['sku_id']
    with pytest.raises(ValueError, match='DISCOUNT_ALREADY_APPLIED'):
        app.ab_lever_options(dict(BASE, catalog_options=dict(discount_percent={sku: 10})), dict(kind='discount', venue_id='GEUMRYONG', percent=20))


def test_expired_run_is_reported_not_rebuilt():
    with mock.patch.object(app.agent_jobs, 'source', side_effect=ValueError('SERVER_RUN_EXPIRED_REEXECUTE_REQUIRED')):
        r = app.ab_readiness('x' * 64, {'A01'})
    assert not r['available'] and r['reason'] == 'SERVER_RUN_EXPIRED_REEXECUTE_REQUIRED'


def test_b_is_the_same_request_plus_only_the_discount():
    import population_lab as PL
    seen = {}

    def fake_visit(body, include_ledger=True, **kw):
        seen['body'] = copy.deepcopy(body)
        return dict(error='stop')
    with mock.patch.object(app.agent_jobs, 'source', return_value=dict(request=copy.deepcopy(BASE), flow=copy.deepcopy(FLOW))), \
         mock.patch.object(app, 'completed_visit', side_effect=fake_visit):
        out = app.current_run_ab('r' * 64, dict(kind='discount', venue_id='PIZZA_HILL', percent=30))
    assert out['status'] == 'RUN_ERROR'
    b = seen['body']
    assert 'include_ledger' not in b
    assert {k: v for k, v in b.items() if k != 'catalog_options'} == {k: v for k, v in BASE.items() if k not in ('catalog_options', 'include_ledger')}
    assert b['catalog_options']['discount_percent'] == {s: 30 for s in PL.pizza_hill_mains()}


def test_live_status_names_a_missing_api_credential(monkeypatch, tmp_path):
    import visit_execution as VE, openai_credentials
    from test_autonomous_agent import P
    p = tmp_path / 'journal'; P.Budget(p, 20, 400).summary()
    monkeypatch.setenv('HILLINK_LIVE_APPROVAL_REFERENCE', 'test'); monkeypatch.setenv('HILLINK_LLM_EXTERNAL_OPT_IN', '1')
    monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE', str(p)); monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS', '100'); monkeypatch.setenv('HILLINK_AGENT_MAX_USD', '1')
    def missing(): raise openai_credentials.OpenAIConfigError('no key')
    monkeypatch.setattr(openai_credentials, 'load_openai_api_key', missing)
    assert VE.live_status() == (False, 'API_CREDENTIAL_MISSING')
    monkeypatch.setattr(openai_credentials, 'load_openai_api_key', lambda: 'present')
    assert VE.live_status() == (True, None)
