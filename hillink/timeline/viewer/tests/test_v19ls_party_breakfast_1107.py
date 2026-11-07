"""V19LS-P2 research policy: party-subset breakfast (no key, no cost).

When the room contract covers only part of the party (k of N adults), the breakfast choice offers: everyone eats
(k included + N-k paid), only some eat (m diners, 1 <= m < N: min(m,k) included + max(0,m-k) paid, N-m not eating), or skip.
The product V19LS policy is unchanged (no variants).
Checked: candidates, contract lines, integer KRW, ledger rows and diners, meal fraction, modeled-diners validation.
A synthetic provider makes the choice: this proves the contracts, not the model's behaviour quality.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v18_shortlist_selection_1105 import A, FIXTURE  # noqa: E402
from operator_choice.autonomy_v1 import ls_stability as LSS  # noqa: E402

PICK = """  import os as _o; pick=_o.environ.get('HL_PB_PICK','D'); bfs=[r for r in rows if r['type']=='BREAKFAST']
  part={r['action_id'].split('#D')[1]:r for r in bfs if '#D' in r['action_id']}
  sel=(part[pick[1]]['action_id'] if pick[:1]=='D' and pick[1:2] in part else 'SKIP_BREAKFAST' if pick=='SKIP' else next((r['action_id'] for r in bfs if '#D' not in r['action_id']),rows[0]['action_id']))
  meal=sel!='SKIP_BREAKFAST'; alt=('SKIP_BREAKFAST','합성')
  inc=next((r['conditions'].get('included') for r in rows if r['action_id']==sel),None) or {}
  if inc.get('diners') and not (pick=='D2_WRONG_DINERS' and not prior): n=inc['diners']"""
OLD = "  sel=next((r['action_id'] for r in rows if r['type']=='BREAKFAST'),rows[0]['action_id']); meal=sel!='SKIP_BREAKFAST'; alt=('SKIP_BREAKFAST','합성')"


def visit(tmp_path, pick, policy='P2'):
    import visit_run as V
    import ledger_service as LS
    pol = A.POLICY_V19LS_P2 if policy == 'P2' else A.POLICY_V19LS
    fx = FIXTURE.replace("assert kw['policy']==A.POLICY_V18 and", "assert kw['policy']==%r and" % pol)
    fx = fx.replace(" jsonschema.validate(out,kw['schema'])", " out['tradeoff_note']=None\n jsonschema.validate(out,kw['schema'])")
    assert OLD in fx
    script = tmp_path / 'fixture.py'; script.write_text(fx.replace(OLD, PICK))
    env = dict(HILLINK_AUTONOMOUS_AGENT='1', HILLINK_NATIVE_HYBRID='1', HILLINK_V12Z_COMMON='1', HILLINK_HYBRID='replay', HILLINK_LLM_ENABLED='0',
               HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_ISOLATED_CUSTOMERS='0', HL_PB_PICK=pick)
    req = dict(personas=['A05'], duration='stay_1', event_mode='none', seed=62, start_date='2026-11-09', environment=dict(arrival_time='14:30'),
               behavior_engine='m4_c01', catalog_policy=A.H.POLICY, hybrid_policy=pol)
    with patch.dict(os.environ, env), patch.object(V, 'FLOW', [sys.executable, str(script), str(Path(__file__).resolve().parents[1])]):
        flow = V.run_visit(req)
    assert 'error' not in flow, flow
    led = LS.register_visit(flow, req)
    plan = flow['plans']['A05']
    bf = next(d for d in plan['autonomous_decisions'] if d.get('phase') == 'breakfast')
    rows = [r for c in led['receipts'].values() for r in c['rows'] if r.get('venue_id') == 'THE_BUFFET']
    act = [e for e in plan['m4']['activity_history'] if str(e.get('action_id')).startswith('BREAKFAST_BUFFET')]
    ordered = sum((d.get('selected_plan') or {}).get('order_total_krw') or 0 for d in plan['autonomous_decisions'] if d['execution_state'] == 'EXECUTED')
    assert plan['summary']['spent_krw'] == ordered
    assert led['checks']['receipts_equal_L4_L3_L2_L1'] and led['checks']['day_totals_equal_visit_total']
    for r in (r for c in led['receipts'].values() for r in c['rows']):
        assert isinstance(r['paid_krw'], int) and (r.get('unit_price_krw') is None or isinstance(r['unit_price_krw'], int))
    return bf, rows, act


def test_only_covered_people_eat(tmp_path):
    bf, rows, act = visit(tmp_path, 'D2')
    assert bf['candidate_ids'] == ['BREAKFAST_BUFFET', 'SKIP_BREAKFAST', 'BREAKFAST_BUFFET#D1', 'BREAKFAST_BUFFET#D2']
    assert bf['selected_plan']['action_id'] == 'BREAKFAST_BUFFET#D2' and bf['selected_plan']['order_total_krw'] == 0
    assert bf['selected_plan']['meal_assessment']['modeled_diners'] == 2
    assert [(r['billing_quantity'], r['paid_krw'], r['purchase_status'], r['participant_count']) for r in rows] == [(2, 0, 'PACKAGE_INCLUDED', 2)]
    assert act[0]['fraction'] == round(2 / 3, 4)


def test_one_person_eats_one_included_breakfast_left_unused(tmp_path):
    bf, rows, act = visit(tmp_path, 'D1')
    assert bf['selected_plan']['action_id'] == 'BREAKFAST_BUFFET#D1' and bf['selected_plan']['order_total_krw'] == 0
    assert bf['selected_plan']['meal_assessment']['modeled_diners'] == 1
    assert [(r['billing_quantity'], r['paid_krw'], r['purchase_status'], r['participant_count']) for r in rows] == [(1, 0, 'PACKAGE_INCLUDED', 1)]
    assert act[0]['fraction'] == round(1 / 3, 4)


def test_product_v19ls_has_no_party_subset_choices(tmp_path):
    bf, rows, act = visit(tmp_path, 'ALL', policy='V19LS')
    assert bf['candidate_ids'] == ['BREAKFAST_BUFFET', 'SKIP_BREAKFAST']


def test_everyone_eats_two_included_one_paid(tmp_path):
    bf, rows, act = visit(tmp_path, 'ALL')
    assert bf['selected_plan']['action_id'] == 'BREAKFAST_BUFFET' and bf['selected_plan']['order_total_krw'] == 85000
    assert sorted((r['billing_quantity'], r['paid_krw'], r['purchase_status']) for r in rows) == [(1, 85000, 'SIMULATED_CHARGE'), (2, 0, 'PACKAGE_INCLUDED')]
    assert act[0]['fraction'] == 1.0


def test_nobody_eats(tmp_path):
    bf, rows, act = visit(tmp_path, 'SKIP')
    assert bf['selected_plan']['action_id'] == 'SKIP_BREAKFAST' and rows == [] and act == []


def test_modeled_diners_must_match_the_chosen_diners(tmp_path):
    bf, rows, act = visit(tmp_path, 'D2_WRONG_DINERS')
    assert [a.get('validation_rejection') for a in bf['attempts']] == ['MODELED_DINERS_DIFFER_FROM_BREAKFAST_DINERS', None]
    assert bf['execution_state'] == 'EXECUTED' and bf['selected_plan']['meal_assessment']['modeled_diners'] == 2


def compose(parts, m):
    return dict(components=parts, unit_price_krw=sum(p['unit_price_krw'] * p['billing_quantity'] for p in parts), participant_count=m)


def offer(k, paid, child=False, **kw):
    parts = [dict(sku_id='B', role='MAIN', billing_quantity=k, unit_price_krw=0, included_benefit=LSS.INCLUDED_KEY),
             dict(sku_id='B', role='MAIN', billing_quantity=paid, unit_price_krw=85000)]
    if child: parts.append(dict(sku_id='C', role='CHILD', billing_quantity=1, unit_price_krw=40000))
    return dict(dict(id='BREAKFAST_BUFFET', label='더뷔페 조식', hc_contract=True, hc_included=False, venue='THE_BUFFET', food=dict(meal_fraction=1.0),
                     sku_contract=dict(components=parts, candidate_available_at=420)), **kw)


def test_general_party_sizes_and_excluded_cases():
    v = LSS.party_breakfast_variants(offer(2, 2), 4, compose)   # 4 adults, room covers 2
    got = [(x['id'], x['party_breakfast']['diners'], x['party_breakfast']['included'], x['party_breakfast']['paid'],
            x['party_breakfast']['not_eating'], x['party_breakfast']['waived_included'], x['sku_contract']['unit_price_krw']) for x in v]
    assert got == [('BREAKFAST_BUFFET#D1', 1, 1, 0, 3, 1, 0), ('BREAKFAST_BUFFET#D2', 2, 2, 0, 2, 0, 0), ('BREAKFAST_BUFFET#D3', 3, 2, 1, 1, 0, 85000)]
    for x in v:
        c = x['sku_contract']
        assert all(isinstance(p['billing_quantity'], int) and p['billing_quantity'] > 0 for p in c['components'])
        assert sum(p['billing_quantity'] for p in c['components']) == x['party_breakfast']['diners'] == c['participant_count']
        assert isinstance(c['unit_price_krw'], int) and c['unit_price_krw'] == 85000 * x['party_breakfast']['paid']
    assert LSS.party_breakfast_variants(offer(1, 0), 1, compose) == []                    # nobody to leave out
    assert LSS.party_breakfast_variants(offer(2, 1, child=True), 4, compose) == []        # child menus: no variants
    assert LSS.party_breakfast_variants(offer(2, 1, hc_included=True), 3, compose) == []  # whole party included
    plain = offer(2, 1); plain['sku_contract']['components'] = [dict(sku_id='B', role='MAIN', billing_quantity=3, unit_price_krw=85000)]
    assert LSS.party_breakfast_variants(plain, 3, compose) == []                          # no room coverage
    other = offer(2, 1); other['sku_contract']['components'][1]['sku_id'] = 'B2'
    assert LSS.party_breakfast_variants(other, 3, compose) == []                          # different sale terms: no equal-eligibility assumption
