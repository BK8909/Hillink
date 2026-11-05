"""Transport-only fixtures. Mock success is never an LLM quality result."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import flow_run
from operator_choice.autonomy_v1 import agent_provider as P


def test_key_order_is_canonical_and_repeated_live_results_are_preserved(tmp_path,monkeypatch):
    import openai_credentials
    monkeypatch.setattr(openai_credentials,'load_openai_api_key',lambda:'TEST_ONLY')
    monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE',str(tmp_path/'budget.json'))
    monkeypatch.setenv('HILLINK_AGENT_MAX_USD','1')
    monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS','10')
    monkeypatch.setenv('HILLINK_LLM_EXTERNAL_OPT_IN','1')
    monkeypatch.setenv('HILLINK_AGENT_CACHE',str(tmp_path/'cache'))
    monkeypatch.setenv('HILLINK_AGENT_MODE','live')
    common=dict(policy='TEST',system='TEST',purpose='TEST',schema={'type':'object','properties':{'value':{'type':'integer'}},'required':['value'],'additionalProperties':False})
    def response(value):
        return io.BytesIO(json.dumps({'id':'test'+str(value),'status':'completed','model':'gpt-6-luna',
            'usage':{'input_tokens':10,'output_tokens':10},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'value':value})}]}]}).encode())
    with patch.object(P.urllib.request,'urlopen',side_effect=[response(1),response(2)]) as network:
        a,ta=P.request(**common,context={'b':2,'a':{'y':3,'x':4}})
        b,tb=P.request(**common,context={'a':{'x':4,'y':3},'b':2})
    assert network.call_count==2 and ta['input_sha256']==tb['input_sha256']
    assert a!=b and len(list((tmp_path/'cache/live_history').glob('*.json')))==2
    monkeypatch.setenv('HILLINK_AGENT_MODE','replay')
    with patch.object(P.urllib.request,'urlopen',side_effect=AssertionError('replay must not call API')):
        replay,trace=P.request(**common,context={'a':{'x':4,'y':3},'b':2})
    assert replay==a and trace['execution']=='CACHE_REPLAY' and trace['current_call_cost_usd']==0
    assert P.configured_budget().summary()['calls']==2
    assert json.loads((tmp_path/'cache'/f"{ta['input_sha256']}.json").read_text())['answer']==a
