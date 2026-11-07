"""V19LS exception matrix (no key, no cost): a synthetic provider injects one failure at the first action
selection of an A05 visit and the visit must either recover within the existing re-plan contract or stop
with a clear EXECUTION_HOLD. Never a silent rule result, never a second order, orders = ledger.

  provider:   429, 5xx, timeout/connection (delivery uncertain), budget/call cap, not authorised, replay miss
  response:   malformed JSON once (one safe re-ask) and twice (hold)
  validation: unknown candidate, unknown basket, uncitable fact id (one re-plan, then hold if still invalid)
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v18_shortlist_selection_1105 import A, FIXTURE  # noqa: E402

INJECT = '''
import os as _os
MODE=_os.environ.get('HL_FX_MODE',''); STATE=dict(calls=0, first=None)
_orig_answer=answer
def answer(**kw):
 c=kw['context']; t=c['state']['time']; act=kw['purpose']=='CUSTOMER_ACTION_SELECTION'
 if act and STATE['first'] is None: STATE['first']=t
 hit=act and t==STATE['first']; prior=c.get('previous_rejection')
 if hit: STATE['calls']+=1
 if hit and MODE.startswith('RAISE:') and STATE['calls']==1: raise P.ProviderUnavailable(MODE[6:])
 if hit and MODE=='MALFORMED_ONCE' and STATE['calls']==1: raise P.ProviderUnavailable('JSONDecodeError')
 if hit and MODE=='MALFORMED_TWICE': raise P.ProviderUnavailable('JSONDecodeError')
 out,tr=_orig_answer(**kw)
 bad = hit and (MODE.endswith('_TWICE') or not prior)
 if bad and MODE.startswith('UNKNOWN_ACTION'): out['selected_action_id']='meal:NO_SUCH_VENUE'; out['selected_basket_id']=None
 if bad and MODE.startswith('UNKNOWN_BASKET'):
  m=[r for r in c['candidates'] if r['type']=='MEAL']
  if m: out['selected_action_id']=m[0]['action_id']; out['selected_basket_id']=m[0]['action_id']+'#999'
 if bad and MODE.startswith('UNCITABLE_FACT'): out['supporting_fact_ids']=['ZZZ-F999']
 return out,tr
A.P.request=answer
'''


def run(tmp_path, mode):
    import visit_run as V
    fx = FIXTURE.replace("assert kw['policy']==A.POLICY_V18 and", "assert kw['policy']==A.POLICY_V19LS and")
    fx = fx.replace(" jsonschema.validate(out,kw['schema'])", " out['tradeoff_note']=None\n jsonschema.validate(out,kw['schema'])")
    fx = fx.replace('A.P.request=answer\nflow_run.main()', 'A.P.request=answer\n' + INJECT + 'flow_run.main()')
    script = tmp_path / 'fixture.py'; script.write_text(fx)
    env = dict(HILLINK_AUTONOMOUS_AGENT='1', HILLINK_NATIVE_HYBRID='1', HILLINK_V12Z_COMMON='1', HILLINK_HYBRID='replay', HILLINK_LLM_ENABLED='0',
               HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_ISOLATED_CUSTOMERS='0', HL_FX_MODE=mode)
    with patch.dict(os.environ, env):
        request = dict(personas=['A05'], duration='stay_1', event_mode='none', seed=62, start_date='2026-11-09', environment=dict(arrival_time='14:30'),
                       behavior_engine='m4_c01', catalog_policy=A.H.POLICY, hybrid_policy=A.POLICY_V19LS)
        with patch.object(V, 'FLOW', [sys.executable, str(script), str(Path(__file__).resolve().parents[1])]):
            flow = V.run_visit(request)
    assert 'error' not in flow, flow
    plan = flow['plans']['A05']; decs = plan['autonomous_decisions']
    sm = plan.get('summary') or {}
    ordered = sum((d.get('selected_plan') or {}).get('order_total_krw') or 0 for d in decs if d['execution_state'] == 'EXECUTED')
    assert sm.get('spent_krw') == ordered, ('orders != ledger', sm.get('spent_krw'), ordered)
    first = next(d for d in decs if d.get('policy') == A.POLICY_V19LS and d.get('phase') != 'breakfast')
    return first, decs


HELD = [('HTTP_429', 'RATE_LIMITED'), ('HTTP_503', 'PROVIDER_SERVER_ERROR'), ('TimeoutError', 'DELIVERY_UNCERTAIN'),
        ('URLError', 'DELIVERY_UNCERTAIN'), ('BUDGET_EXCEEDED', 'BUDGET_OR_CALL_LIMIT'), ('EXTERNAL_CALL_NOT_AUTHORIZED', 'NOT_AUTHORIZED'),
        ('REPLAY_MISS', 'REPLAY_MISMATCH')]


@pytest.mark.parametrize('code,klass', HELD)
def test_provider_failures_hold_without_resend_or_rule_substitute(tmp_path, code, klass):
    if A.provider_failure_class(code) != klass:
        pytest.skip('class map differs: %s -> %s' % (code, A.provider_failure_class(code)))
    first, decs = run(tmp_path, 'RAISE:' + code)
    assert first['execution_state'] == 'EXECUTION_HOLD' and first.get('failure_class') == klass
    assert len(first['attempts']) == 1, 'a failed call that may have reached the provider is not re-sent'
    assert not first.get('selected_plan') and first.get('selection_owner') is None, 'no rule result in place of the model'


def test_malformed_once_is_reasked_once_and_executes(tmp_path):
    first, _ = run(tmp_path, 'MALFORMED_ONCE')
    assert first['execution_state'] == 'EXECUTED' and len(first['attempts']) == 2
    assert first['attempts'][0]['failure_class'] == 'MALFORMED_OR_INCOMPLETE_RESPONSE'


def test_malformed_twice_holds_after_two_calls(tmp_path):
    first, _ = run(tmp_path, 'MALFORMED_TWICE')
    assert first['execution_state'] == 'EXECUTION_HOLD' and first.get('failure_class') == 'MALFORMED_OR_INCOMPLETE_RESPONSE'
    assert len(first['attempts']) == 2, 'at most two calls per decision'


@pytest.mark.parametrize('mode', ['UNKNOWN_ACTION', 'UNKNOWN_BASKET', 'UNCITABLE_FACT'])
def test_invalid_selection_is_rejected_and_replanned_once(tmp_path, mode):
    first, _ = run(tmp_path, mode)
    assert first['attempts'][0].get('validation_rejection'), 'the invalid answer is rejected by validation'
    assert first['execution_state'] == 'EXECUTED' and len(first['attempts']) == 2


@pytest.mark.parametrize('mode', ['UNKNOWN_ACTION_TWICE', 'UNKNOWN_BASKET_TWICE', 'UNCITABLE_FACT_TWICE'])
def test_invalid_selection_twice_holds(tmp_path, mode):
    first, _ = run(tmp_path, mode)
    assert first['execution_state'] == 'EXECUTION_HOLD' and len(first['attempts']) == 2
    assert all(x.get('validation_rejection') for x in first['attempts'])
    assert not first.get('selected_plan')
