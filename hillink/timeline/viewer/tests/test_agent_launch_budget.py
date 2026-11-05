import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('check_agent_budget',Path(__file__).resolve().parents[2]/'tools/check_agent_budget.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_launch_never_silently_lowers_approved_shared_limit(tmp_path,monkeypatch):
 p=tmp_path/'journal.json';p.write_text(json.dumps({'max_calls':1000,'max_usd':20,'requests':[{'reserved_usd':.01}],
  'limit_amendments':[{'approved_max_calls':1000,'unchanged_max_usd':20,'approval_reference':'TEST'}]}));before=p.read_bytes()
 monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE',str(p));monkeypatch.setenv('HILLINK_AGENT_MAX_USD','20');monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS','400')
 with pytest.raises(ValueError,match='MUST_MATCH'):module.check()
 monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS','1000');assert module.check()['used_calls']==1
 assert p.read_bytes()==before

@pytest.mark.parametrize('limit', [1500, 2500])
def test_launch_accepts_recorded_amendment_without_writing(tmp_path,monkeypatch,limit):
 p=tmp_path/'journal.json';p.write_text(json.dumps({'max_calls':limit,'approved_global_max_calls':limit,'max_usd':20,'requests':[],
  'limit_amendments':[{'approved_max_calls':limit,'unchanged_max_usd':20,'approval_reference':'TEST'}]}));before=p.read_bytes()
 monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE',str(p));monkeypatch.setenv('HILLINK_AGENT_MAX_USD','20');monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS',str(limit))
 assert module.check()['max_calls']==limit
 assert p.read_bytes()==before
