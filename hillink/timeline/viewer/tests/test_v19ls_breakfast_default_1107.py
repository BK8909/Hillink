"""V19LS-P2 research policy: included breakfast as the default, with exceptions (no key, no cost).

Three situations (directive b3582ba3 section 3):
  whole party included, one option, no morning exception sign  -> rule default, no model call, recorded as a rule
  included, but a record / intention / state / schedule may matter -> the model decides (with the default-principle line)
  extra payment or partly covered party                            -> the model decides (who eats, who pays)
The rule assigns no probability and removes no Fact; it only decides whether a call is needed. A repeated skip of an
included breakfast with no concrete reason is asked once to reconsider; the second answer stands.
The product V19LS policy is unchanged.
"""
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v18_shortlist_selection_1105 import A, FIXTURE  # noqa: E402
from operator_choice.autonomy_v1 import ls_stability as L  # noqa: E402


def row(aid, included=True, price=0, duration=60):
    return dict(action_id=aid, duration=duration, conditions=dict(included=included, price_krw=price))


BF = row('BREAKFAST_BUFFET'); SKIP = row('SKIP_BREAKFAST', included=False)
FAT = dict(level='여유')


def route(rows=(BF, SKIP), records=(), memory=None, fatigue=FAT, recent=(), left=600, party=2):
    return L.breakfast_route(list(rows), list(records), memory or {}, fatigue, list(recent), left, party)


def test_clear_included_case_is_the_rule_default():
    r = route()
    assert r['route'] == L.BREAKFAST_DEFAULT and r['action_id'] == 'BREAKFAST_BUFFET' and not r['reasons']


@pytest.mark.parametrize('kw,reason', [
    (dict(records=[dict(fact_ids=['X-F1'], summary='조식은 늘 붐벼서 건너뛰었다')]), 'PERSONAL_RECORD:X-F1'),
    (dict(records=[dict(fact_ids=['X-F2'], summary='체크아웃 전에 서둘러 나갔다')]), 'PERSONAL_RECORD:X-F2'),
    (dict(records=[dict(fact_ids=['X-F3'], summary='맛있었다', about=['meal:BREAKFAST_BUFFET'])]), 'PERSONAL_RECORD:X-F3'),
    (dict(memory=dict(breakfast_decisions=[dict(outcome='VOLUNTARY_NONUSE_AMONG_VALID_OPTIONS_NOT_STABLE_PREFERENCE')])), 'SKIPPED_EARLIER_THIS_VISIT'),
    (dict(memory=dict(pending_intentions=[dict(text='내일 아침 일찍 외출')])), 'PENDING_INTENTION'),
    (dict(fatigue=dict(level='피곤')), 'TIRED'),
    (dict(recent=[dict(act='WINE_BAR', label='와인바', loc='BAR')]), 'LATE_DRINK_OR_FOOD_BEFORE'),
    (dict(left=90), 'TIGHT_SCHEDULE'),
    (dict(rows=[BF, row('ROOM_BREAKFAST'), SKIP]), 'SEVERAL_INCLUDED_OPTIONS'),
])
def test_exception_signs_send_the_decision_to_the_model(kw, reason):
    r = route(**kw)
    assert r['route'] == 'LLM_EXCEPTION_CHECK' and reason in r['reasons']


def test_unrelated_records_do_not_block_the_default():
    assert route(records=[dict(fact_ids=['X-F9'], summary='수영장 물이 차가웠다', flags=['부정'])])['route'] == L.BREAKFAST_DEFAULT


@pytest.mark.parametrize('rows', [
    [row('BREAKFAST_BUFFET', included=None, price=85000), SKIP],                                          # not included
    [row('BREAKFAST_BUFFET', included=dict(status='PARTIAL', included_persons=2, paid_persons=1), price=85000), SKIP],   # 2 of 3
    [row('BREAKFAST_BUFFET#D2', included=dict(status='PARTIAL', diners=2, not_eating=1)), SKIP],
])
def test_paid_or_partly_covered_party_goes_to_the_model(rows):
    assert route(rows=rows, party=3)['route'] == 'LLM_EXTRA_PAYMENT_OR_PARTY'


def test_default_answer_is_labelled_as_a_rule_not_a_model_statement():
    ans = L.default_breakfast_answer(BF, 2)
    assert ans['selected_action_id'] == 'BREAKFAST_BUFFET' and '규칙 기본 판단' in ans['reason'] and '모델 호출 없음' in ans['reason']
    assert ans['meal_assessment']['modeled_diners'] == 2 and not ans['supporting_fact_ids']


SKIPPED = dict(breakfast_decisions=[dict(outcome='VOLUNTARY_NONUSE_AMONG_VALID_OPTIONS_NOT_STABLE_PREFERENCE')])


def skip(reason='오늘은 건너뜁니다.', cited=()):
    return dict(selected_action_id='SKIP_BREAKFAST', reason=reason, supporting_fact_ids=list(cited), counterevidence_fact_ids=[])


def test_repeated_forfeit_without_reason_is_asked_once():
    with pytest.raises(ValueError, match=L.BREAKFAST_FORFEIT_REVIEW):
        L.forfeit_review(skip(), [BF, SKIP], [], SKIPPED, 2, None)
    L.forfeit_review(skip(), [BF, SKIP], [], SKIPPED, 2, dict(validation_rejection=L.BREAKFAST_FORFEIT_REVIEW))   # second answer stands


@pytest.mark.parametrize('ans,memory,rows', [
    (skip(), {}, [BF, SKIP]),                                         # first skip this visit: no check
    (skip('어젯밤 과음해서 늦잠을 잡니다.'), SKIPPED, [BF, SKIP]),         # concrete exception named
    (skip(cited=['X-F1']), SKIPPED, [BF, SKIP]),                      # cited Fact
    (skip(), SKIPPED, [row('BREAKFAST_BUFFET', included=None, price=85000), SKIP]),   # nothing included to forfeit
    (dict(skip(), selected_action_id='BREAKFAST_BUFFET'), SKIPPED, [BF, SKIP]),
])
def test_no_forfeit_check_when_explained_first_or_not_included(ans, memory, rows):
    L.forfeit_review(ans, rows, [], memory, 2, None)


def test_principle_line_is_research_only():
    assert any('포함된 조식을 이용하는 것이 기본' in x for x in L.P2_LINES)
    assert not any('포함된 조식을 이용하는 것이 기본' in x for x in L.SYSTEM_LINES)
    assert A.POLICIES[A.POLICY_V19LS_P2]['breakfast_default'] and not A.POLICIES[A.POLICY_V19LS].get('breakfast_default')


# ------------------------------------------------------------------ end to end (synthetic provider, no cost)
OLD = "  sel=next((r['action_id'] for r in rows if r['type']=='BREAKFAST'),rows[0]['action_id']); meal=sel!='SKIP_BREAKFAST'; alt=('SKIP_BREAKFAST','합성')"
TERMS = """import os as _os, re as _re
from operator_choice.autonomy_v1 import ls_stability as _L
if _os.environ.get('HL_BR_TERMS')=='never': _L.MORNING_TERMS=_re.compile(r'(?!x)x'); _L.LATE_ACTS=_re.compile(r'(?!x)x')
if _os.environ.get('HL_BR_TERMS')=='always': _L.MORNING_TERMS=_re.compile(r'')
"""


def visit(tmp_path, policy, terms):
    import visit_run as V
    fx = FIXTURE.replace("assert kw['policy']==A.POLICY_V18 and", "assert kw['policy']==%r and" % policy)
    fx = fx.replace(" jsonschema.validate(out,kw['schema'])", " out['tradeoff_note']=None\n jsonschema.validate(out,kw['schema'])")
    fx = fx.replace("A.P.request=answer\n", TERMS + "A.P.request=answer\n")
    assert OLD in fx
    script = tmp_path / 'fixture.py'; script.write_text(fx)
    env = dict(HILLINK_AUTONOMOUS_AGENT='1', HILLINK_NATIVE_HYBRID='1', HILLINK_V12Z_COMMON='1', HILLINK_HYBRID='replay', HILLINK_LLM_ENABLED='0',
               HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_ISOLATED_CUSTOMERS='0', HL_BR_TERMS=terms)
    req = dict(personas=['A07'], duration='stay_1', event_mode='none', seed=62, start_date='2026-11-09', environment=dict(arrival_time='14:30'),
               behavior_engine='m4_c01', catalog_policy=A.H.POLICY, hybrid_policy=policy)
    with patch.dict(os.environ, env), patch.object(V, 'FLOW', [sys.executable, str(script), str(Path(__file__).resolve().parents[1])]):
        flow = V.run_visit(req)
    assert 'error' not in flow, flow
    plan = flow['plans']['A07']
    assert all(d['execution_state'] == 'EXECUTED' for d in plan['autonomous_decisions'])
    return flow, next(d for d in plan['autonomous_decisions'] if d.get('phase') == 'breakfast')


HAS = 'A07' in __import__('visit_run').AD.load_inputs()[0]


@pytest.mark.skipif(not HAS, reason='approved A07 execution inputs unavailable')
def test_clear_included_breakfast_runs_without_a_model_call(tmp_path):
    import ledger_service as LS
    import operating_reference as OR
    flow, bf = visit(tmp_path, A.POLICY_V19LS_P2, 'never')
    assert bf['breakfast_route']['route'] == L.BREAKFAST_DEFAULT
    assert bf['selection_owner'] == L.BREAKFAST_DEFAULT and bf['llm_calls'] == 0 and bf['attempts'] == []
    assert bf['selected_plan']['selection_policy'] == 'RULE_DEFAULT_INCLUDED_BREAKFAST_NO_LLM_CALL' and bf['selected_plan']['order_total_krw'] == 0
    assert bf['input_context']   # what the model would have seen stays recorded
    led = LS.register_visit(flow, dict(personas=['A07'], duration='stay_1', event_mode='none', seed=62, start_date='2026-11-09'))
    assert led['checks']['receipts_equal_L4_L3_L2_L1']
    b = OR.aggregate(flow)['breakfast']
    assert (b['entitled'], b['included_used'], b['paid_revenue_krw']) == (2, 2, 0) and b['decided_by'] == {L.BREAKFAST_DEFAULT: 1}


@pytest.mark.skipif(not HAS, reason='approved A07 execution inputs unavailable')
def test_exception_sign_keeps_the_model_call(tmp_path):
    _, bf = visit(tmp_path, A.POLICY_V19LS_P2, 'always')
    assert bf['breakfast_route']['route'] == 'LLM_EXCEPTION_CHECK'
    assert bf['selection_owner'].startswith('LLM') and len(bf['attempts']) == 1


@pytest.mark.skipif(not HAS, reason='approved A07 execution inputs unavailable')
def test_product_v19ls_breakfast_is_unchanged(tmp_path):
    _, bf = visit(tmp_path, A.POLICY_V19LS, 'never')
    assert 'breakfast_route' not in bf and bf['selection_owner'].startswith('LLM') and len(bf['attempts']) == 1
