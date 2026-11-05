import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1 import hybrid_review as R, agent_provider as P


def test_legacy_control_uses_same_budget_transport_without_old_http():
    cfg=dict(mode='live',model='gpt-6-luna',effort='high',cache=None,max_usd=20)
    trace=dict(execution='LIVE_RESPONSES',charged_upper_usd=.001,usage=dict(input_tokens=1,output_tokens=2))
    with patch.dict(os.environ,dict(HILLINK_AGENT_BUDGET_FILE='test-only',HILLINK_HYBRID_MAX_USD='20',HILLINK_LLM_EXTERNAL_OPT_IN='1')):
        with patch.object(P,'request',return_value=({'choice':'VALID'},trace)) as call:
            with patch.object(R.urllib.request,'urlopen',side_effect=AssertionError('old unshared transport')):
                answer,record=R._call_once(dict(customer={}),cfg)
    assert call.call_args.kwargs['purpose']=='LEGACY_SELECTIVE_REVIEW_CONTROL'
    assert answer['choice']=='VALID' and record['provider_response_received']
    assert record['shared_provider']==trace


def test_shared_budget_exhaustion_does_not_fall_back_to_unmetered_http():
    cfg=dict(mode='live',model='gpt-6-luna',effort='high',cache=None,max_usd=20)
    with patch.dict(os.environ,dict(HILLINK_AGENT_BUDGET_FILE='test-only',HILLINK_HYBRID_MAX_USD='20',HILLINK_LLM_EXTERNAL_OPT_IN='1')):
        with patch.object(P,'request',side_effect=P.ProviderUnavailable('USD_LIMIT')):
            with patch.object(R.urllib.request,'urlopen',side_effect=AssertionError('budget bypass')):
                answer,record=R._call_once(dict(customer={}),cfg)
    assert answer is None and record['error']=='USD_LIMIT'
    assert not record['network_attempted']


def test_visit_label_does_not_claim_hybrid_success_on_fallback_or_synthetic():
    from visit_run import decision_backend
    p={'X':dict(autonomous_decisions=[dict(execution_state='RULE_FALLBACK')],trace=dict(llm_calls=1))}
    assert decision_backend(p,'requested').startswith('Rule fallback')
    p['X']['autonomous_decisions'][0]['execution_state']='EXECUTED'
    assert '(live)' in decision_backend(p,'requested')
    p['X']['trace']=dict(llm_calls=0,llm_replays=1)
    assert '(cache replay)' in decision_backend(p,'requested')
    p['X']['trace']={}
    assert 'synthetic or unverified provider' in decision_backend(p,'requested')
    assert decision_backend({'X':{}},'requested')=='Rules · requested LLM review not applied'
