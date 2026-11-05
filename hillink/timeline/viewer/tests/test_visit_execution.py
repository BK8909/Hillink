"""Product-mode boundaries, no credentials or provider calls."""
import copy,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
import visit_execution as V

def request(mode):
    return dict(personas=['A02'],judgment_mode=mode,behavior_engine='m4_c01',
                catalog_policy='C01_HOTEL_CATALOG_V1',hybrid_policy=V.POLICY)

def test_rules_and_replay_are_child_only_environments(monkeypatch):
    monkeypatch.setenv('HILLINK_AUTONOMOUS_AGENT','1')
    monkeypatch.setenv('HILLINK_AGENT_MODE','replay')
    source=request('rules');before=copy.deepcopy(source)
    rules,env,_=V.configure(source)
    assert source==before and 'hybrid_policy' not in rules
    assert env['HILLINK_AGENT_MODE']=='off'
    assert os.environ['HILLINK_AGENT_MODE']=='replay'
    replay,env,_=V.configure(request('replay'))
    assert replay['hybrid_policy']==V.POLICY
    assert env['HILLINK_AGENT_MODE']=='replay' and env['HILLINK_LLM_EXTERNAL_OPT_IN']=='0'
    assert 'judgment_mode' not in replay

def test_disabled_autonomous_policy_never_runs_rules(monkeypatch):
    monkeypatch.setenv('HILLINK_AUTONOMOUS_AGENT','0')
    with pytest.raises(ValueError,match='AUTONOMOUS_ENGINE_DISABLED'):V.configure(request('replay'))

def test_live_requires_separate_approval_before_provider(monkeypatch):
    monkeypatch.setenv('HILLINK_AUTONOMOUS_AGENT','1')
    monkeypatch.delenv('HILLINK_LIVE_APPROVAL_REFERENCE',raising=False)
    with pytest.raises(ValueError,match='LIVE_APPROVAL_REQUIRED'):V.configure(request('live'))

def test_budget_preflight_does_not_create_or_reset_journal(tmp_path,monkeypatch):
    monkeypatch.setenv('HILLINK_LIVE_APPROVAL_REFERENCE','SYNTHETIC_TEST_APPROVAL')
    monkeypatch.setenv('HILLINK_LLM_EXTERNAL_OPT_IN','1')
    p=tmp_path/'journal.json';monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE',str(p))
    monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS','2500');monkeypatch.setenv('HILLINK_AGENT_MAX_USD','20')
    assert V.live_status()==(False,'EXISTING_SHARED_BUDGET_REQUIRED')
    assert not p.exists()
    state=dict(max_calls=2500,max_usd=20,requests=[dict(reserved_usd=20,charged_upper_usd=20)],
        limit_amendments=[dict(approved_max_calls=2500,unchanged_max_usd=20,approval_reference='SYNTHETIC')])
    p.write_text(json.dumps(state));original=p.read_bytes()
    assert V.live_status()==(False,'USD_LIMIT')
    assert p.read_bytes()==original

@pytest.mark.parametrize('state,origin',[('EXECUTION_HOLD','CACHE_REPLAY'),('VALIDATED','LIVE_RESPONSES'),('RULE_FALLBACK','CACHE_REPLAY')])
def test_incomplete_or_wrong_origin_is_blocked(state,origin):
    flow=dict(plans={'A02':dict(autonomous_decisions=[dict(execution_state=state,attempts=[dict(provider=dict(execution=origin))])])})
    result=V.describe(flow,'replay')
    assert result['code']=='V16_EXECUTION_HOLD'
    assert result['judgment']['actual']=='BLOCKED'

def test_every_customer_needs_independent_decisions():
    d=dict(execution_state='VALIDATED',attempts=[dict(provider=dict(execution='CACHE_REPLAY'))])
    flow=dict(plans={'A01':dict(autonomous_decisions=[d]),'A02':dict(autonomous_decisions=[])})
    assert 'error' in V.describe(flow,'replay')
    flow['plans']['A02']['autonomous_decisions']=[copy.deepcopy(d)]
    flow.pop('error');flow.pop('code')
    assert V.describe(flow,'replay')['judgment']['actual']=='replay'

def test_cache_uses_only_manifest_verified_full_input_receipts(tmp_path,monkeypatch):
    entry=dict(path='receipt',input_sha256='a'*64)
    monkeypatch.setattr(V.saved_visits,'manifest',lambda:dict(v16_runs=[dict(tag='A02-baseline',replay_entries=[entry])]))
    monkeypatch.setattr(V.saved_visits,'_read',lambda path,spec:dict(origin='LIVE_RESPONSES',input_sha256='b'*64,answer={}))
    with pytest.raises(ValueError,match='INVALID_APPROVED_RECEIPT'):V.prepare_replay_cache(tmp_path/'cache')
