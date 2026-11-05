"""Synthetic extraction gates; no inference or production approval."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'timeline/experiments/persona_live'),str(ROOT/'timeline/experiments/persona_live/tests')]
from test_team_contract_v4_2 import profile,doc
TOOL=ROOT/'tools/persona_pipeline.py'
def run(w,stage,*args):
 return subprocess.run([sys.executable,str(TOOL),stage,'--workspace',str(w),*map(str,args)],capture_output=True,text=True)
def test_exact_source_and_human_approval_gate(tmp_path):
 corpus=tmp_path/'corpus.json';corpus.write_text(json.dumps([doc()]));w=tmp_path/'workspace'
 assert run(w,'prepare','--corpus',corpus).returncode==0
 packet=json.loads((w/'request.json').read_text());response=tmp_path/'response.json'
 body=dict(actual_model_id='SYNTHETIC_TEST_NO_MODEL',actual_session_ref='SYNTHETIC',isolation_description='synthetic fixture only',input_sha256_private=packet['input_sha256_private'],profile=profile());response.write_text(json.dumps(body))
 assert run(w,'import','--response',response).returncode==0
 review=json.loads((w/'review.json').read_text());assert review['decision']=='HOLD'
 assert run(w,'approve','--review',w/'review.json').returncode!=0
 assert not (w/'approval.json').exists()
 assert run(w,'register').returncode!=0
 # A changed input cannot be imported under the original model request hash.
 body['input_sha256_private']='0'*64;response.write_text(json.dumps(body))
 w2=tmp_path/'other';assert run(w2,'prepare','--corpus',corpus).returncode==0
 assert run(w2,'import','--response',response).returncode!=0
 assert not (w2/'source_import.json').exists()

def test_synthetic_registration_isolated_and_sha_bound(tmp_path):
 corpus=tmp_path/'corpus.json';corpus.write_text(json.dumps([doc()]));w=tmp_path/'workspace'
 assert run(w,'prepare','--corpus',corpus).returncode==0
 packet=json.loads((w/'request.json').read_text());response=tmp_path/'response.json'
 response.write_text(json.dumps(dict(actual_model_id='SYNTHETIC_NO_MODEL',actual_session_ref='SYNTHETIC',isolation_description='test only',input_sha256_private=packet['input_sha256_private'],profile=profile())))
 assert run(w,'import','--response',response).returncode==0
 review=json.loads((w/'review.json').read_text());review.update(reviewer='SYNTHETIC_TEST_REVIEWER',reviewed_at='2026-11-05T00:00:00Z',decision='APPROVE',event_identity_review='APPROVE',actor_time_negation_review='APPROVE');review['fact_decisions']={k:'APPROVE' for k in review['fact_decisions']}
 reviewed=tmp_path/'reviewed.json';reviewed.write_text(json.dumps(review))
 assert run(w,'approve','--review',reviewed).returncode==0
 result=run(w,'register','--standalone-registry');assert result.returncode==0,result.stderr[-1500:]
 registry=json.loads((w/'registry.json').read_text());assert registry['customers'][0]['customer_id']=='NEW'
 assert registry['customers'][0]['approval_status']=='ISOLATED_PILOT_APPROVED'
 import os,hashlib
 from unittest.mock import patch
 from operator_choice.operator_world_v1_1.isolated_registry import registrations
 with patch.dict(os.environ,{'HILLINK_ISOLATED_CUSTOMERS':'1','HILLINK_ISOLATED_REGISTRY':str(w/'registry.json'),'HILLINK_ISOLATED_REGISTRY_SHA256':hashlib.sha256((w/'registry.json').read_bytes()).hexdigest()}):
  assert set(registrations())=={'NEW'}
  # Complete the protocol with synthetic approved fixture data, separately from
  # the real A14 draft, whose human approval must remain pending.
  import threading
  sys.path.insert(0,str(ROOT/'timeline/viewer'))
  import app,http_boundary
  with patch.object(app,'DEPLOY','local'),patch.object(app,'REVIEWER_LOCAL',True),patch.dict(os.environ,{'HILLINK_AUTONOMOUS_AGENT':'0','HILLINK_LLM_ENABLED':'0','HILLINK_LLM_EXTERNAL_OPT_IN':'0','HILLINK_AGENT_MODE':'off'}):
   server=http_boundary.LocalHTTPServer(('127.0.0.1',0),app.H)
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    verified=run(w,'verify','--server',f'http://127.0.0.1:{server.server_port}')
    assert verified.returncode==0,verified.stderr[-1000:]
    checks=json.loads((w/'execution_verification.json').read_text())
    assert len(checks['results'])==4
    assert all(r['checks']['receipts_equal_L4_L3_L2_L1'] for r in checks['results'])
   finally:server.shutdown();server.server_close();thread.join()
  (w/'profile.json').write_text('{}')
  import pytest
  with pytest.raises(ValueError,match='sha_mismatch'):registrations()

def test_real_author_example_stops_at_human_approval(tmp_path):
 w=tmp_path/'real-author'
 result=run(w,'example');assert result.returncode==0,result.stderr[-1000:]
 corpus=json.loads((w/'corpus.json').read_text());source=json.loads((w/'source_import.json').read_text())
 assert len(corpus)==119
 assert source['team_profile_private']['STRUCTURED_PROFILE']['persona_id']=='A14'
 assert sum(len(b['facts']) for b in source['canonical_batches_private'])==19
 assert len(source['team_profile_private']['EVENT_ACTIONS'])==8
 assert source['model_provenance']=='SUPPLIED_DRAFT_MODEL_NOT_RECORDED'
 assert run(w,'approve','--review',w/'review.json').returncode!=0
 assert run(w,'register').returncode!=0
 assert not (w/'registry.json').exists()

def test_real_author_mixed_stage_requires_review(tmp_path):
 w=tmp_path/'real-author'
 result=run(w,'example');assert result.returncode==0,result.stderr[-1000:]
 source=json.loads((w/'source_import.json').read_text());facts=[f for b in source['canonical_batches_private'] for f in b['facts']]
 sys.path.insert(0,str(ROOT/'tools'))
 import persona_pipeline as pipeline
 export=tmp_path/'shared.json';export.write_text(json.dumps(pipeline.export('A14',facts)))
 report,profile=pipeline.intake_team_profile.check(str(export),history_evidence_hold_ids=pipeline.history_holds(facts),actor_evidence_guard=True)
 assert [issue['fact'] for issue in report['issues']]==['A14-F016']
 mixed=next(f for f in facts if f['fact_id']=='A14-F016')
 assert mixed['kind']=='decline' and mixed['action_stage']=='consumption_reported'
 assert pipeline.semantic_audit(profile,facts)['errors']==[]
 assert not (w/'registry.json').exists()
