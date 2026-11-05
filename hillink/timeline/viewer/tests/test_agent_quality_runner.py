"""Offline evidence preservation tests; no API calls or shared journal writes."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import run_agent_quality as Q


def test_missing_journal_is_never_recreated(tmp_path):
    missing=tmp_path/'missing.json'
    with pytest.raises(FileNotFoundError):Q.journal(missing)
    assert not missing.exists()


def test_preflight_preserves_bytes_and_holds_unsettled_prior_requests(tmp_path):
    p=tmp_path/'journal.json';batch=tmp_path/'batch.json'
    value=dict(max_calls=2500,max_usd=20,limit_amendments=[dict(approved_max_calls=2500,
        unchanged_max_usd=20,approval_reference='TEST_ONLY')],requests=[dict(id='r',state='RESERVED',reserved_usd=.01)])
    p.write_text(json.dumps(value,indent=2));before=p.read_bytes()
    args=SimpleNamespace(command='preflight',journal=p,batch_state=batch)
    with pytest.raises(ValueError,match='UNSETTLED'):Q.batch_check(args)
    assert p.read_bytes()==before and not batch.exists()


def test_first_cache_cannot_substitute_for_a_different_live_response(tmp_path):
    trace=dict(input_sha256='hash',id='second',response_id='response2')
    Q.save(tmp_path/'hash.json',dict(origin='LIVE_RESPONSES',input_sha256='hash',
        trace=dict(id='first',response_id='response1')))
    with pytest.raises(ValueError,match='RECEIPT_IDENTITY'):Q.receipt(tmp_path,trace)
    Q.save(tmp_path/'live_history/hash.second.json',dict(origin='LIVE_RESPONSES',input_sha256='hash',trace=trace))
    assert Q.receipt(tmp_path,trace)['trace']==trace


def test_saved_artifacts_are_not_overwritten(tmp_path):
    p=tmp_path/'evidence.json';Q.save(p,{'original':True})
    with pytest.raises(FileExistsError):Q.save(p,{'replacement':True})
    assert json.loads(p.read_text())=={'original':True}
