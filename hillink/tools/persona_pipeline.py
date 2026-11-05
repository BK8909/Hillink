"""Single private extraction interface. External inference is never run by this tool."""
import argparse, json, os, sys, hashlib, copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'timeline/experiments/persona_live'),str(ROOT/'timeline/viewer'),str(ROOT/'research/customer_admission')]
from operator_choice.author_validation_v4_2.team_contract import prepare_team_requests,import_team_profile
from operator_choice.author_validation_v4_2.__main__ import private_path,save_private
from core import export,library,history_holds,semantic_audit
import intake_team_profile

def read(p):return json.loads(private_path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def save(root,name,data):return save_private(root,name,data)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['example','prepare','import','approve','register','verify']);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--corpus',type=Path);p.add_argument('--response',type=Path);p.add_argument('--review',type=Path);p.add_argument('--supplied-draft',action='store_true');p.add_argument('--canonicalize-events',action='store_true');p.add_argument('--base-registry',type=Path);p.add_argument('--standalone-registry',action='store_true');p.add_argument('--server',default='http://127.0.0.1:8994');a=p.parse_args();w=private_path(a.workspace)
 if a.stage=='example':
  from bootstrap_data import bootstrap
  import subprocess,shutil
  sample=Path(bootstrap()['path']).parent/'examples/new-author-A14'
  for arguments in (['prepare','--corpus',str(sample/'corpus.json')],['import','--response',str(sample/'supplied_profile.json'),'--supplied-draft','--canonicalize-events']):
   subprocess.run([sys.executable,str(Path(__file__).resolve()),*arguments,'--workspace',str(w)],check=True)
  for name in ('human_review.csv','REVIEW.md','supplier_provenance.json'):shutil.copyfile(sample/name,w/name)
  print('REAL_AUTHOR_EXAMPLE_VALIDATED: 119 posts / 19 Facts; human approval, F016 mixed-stage review and model provenance remain pending')
 elif a.stage=='prepare':
  docs=read(a.corpus);packet=prepare_team_requests(docs,author_role='holdout_new_author')
  save(w,'corpus.json',docs);save(w,'request.json',packet)
  print('SOURCE_VALIDATED: request prepared; model executions 0; import an authorized LLM response')
 elif a.stage=='import':
  packet=read(w/'request.json');raw=read(a.response)
  if a.supplied_draft:
   profile=copy.deepcopy(raw);origin='SUPPLIED_DRAFT_MODEL_NOT_RECORDED'
  else:
   if not all(raw.get(k) for k in ['actual_model_id','actual_session_ref','isolation_description']) or raw.get('input_sha256_private')!=packet['input_sha256_private']:raise ValueError('model_provenance_and_matching_input_required')
   profile=copy.deepcopy(raw['profile']);origin='CALLER_REPORTED_MODEL_PROVENANCE'
  adaptation=None
  if a.canonicalize_events:
   grouped={}
   for fact in profile['STRUCTURED_PROFILE']['facts']:grouped.setdefault(fact['experience_key'],[]).append(fact)
   events=[]
   for key,fs in grouped.items():
    ids={f['fact_id'] for f in fs};event=dict(event_id=key,visit_id=None,link_status='unlinked',stages=sorted({f['action_stage'] for f in fs}),fact_ids=sorted(ids),post_ids=sorted({f['post_id'] for f in fs}))
    for field in ('motives','price_information'):
     values={json.dumps(value,ensure_ascii=False,sort_keys=True):value for old in profile['EVENT_ACTIONS'] if ids&set(old['fact_ids']) for value in old[field]};event[field]=list(values.values())
    events.append(event)
   adaptation=dict(original_event_rows=len(profile['EVENT_ACTIONS']),declared_experience_groups=len(events),source_facts_unchanged=True,semantic_event_identity_approved=False)
   profile['EVENT_ACTIONS']=events
  result=import_team_profile(read(w/'corpus.json'),packet,profile);result['model_provenance']=origin;result['event_adapter']=adaptation;save(w,'response.json',raw);save(w,'source_import.json',result)
  facts=[f for b in result['canonical_batches_private'] for f in b['facts']]
  save(w,'review.json',dict(source_import_sha256=sha(w/'source_import.json'),reviewer='',reviewed_at='',decision='HOLD',fact_decisions={f['fact_id']:'HOLD' for f in facts},event_identity_review='HOLD',actor_time_negation_review='HOLD',model_provenance=origin,model_origin_review='HOLD' if a.supplied_draft else 'CALLER_REPORTED',scope='isolated_runtime_only'))
  preview=save(w,'product_preview_export.json',export(packet['persona_id'],facts))
  report,profile=intake_team_profile.check(str(preview),history_evidence_hold_ids=history_holds(facts),actor_evidence_guard=True)
  audit=semantic_audit(profile,facts)
  save(w,'product_preflight.json',dict(status='READY_FOR_HUMAN_REVIEW' if not report['issues'] and not audit['errors'] else 'PRODUCT_ISSUES_REQUIRE_REVIEW',issues=report['issues'],semantic_link_errors=audit['errors'],registration_performed=False))
  print('ANCHOR_VALIDATED: schema, quotes and event links checked; HUMAN_REVIEW_REQUIRED; product issues='+str(len(report['issues'])))
 elif a.stage=='approve':
  review=read(a.review);source=read(w/'source_import.json');ids={f['fact_id'] for b in source['canonical_batches_private'] for f in b['facts']}
  if source.get('model_provenance')=='SUPPLIED_DRAFT_MODEL_NOT_RECORDED' and review.get('model_origin_review')!='ACKNOWLEDGE_MODEL_UNRECORDED':raise ValueError('model_origin_acknowledgement_required')
  if review.get('source_import_sha256')!=sha(w/'source_import.json') or not review.get('reviewer') or not review.get('reviewed_at') or review.get('decision')!='APPROVE' or review.get('scope')!='isolated_runtime_only' or review.get('event_identity_review')!='APPROVE' or review.get('actor_time_negation_review')!='APPROVE' or set(review.get('fact_decisions',{}))!=ids or any(v!='APPROVE' for v in review['fact_decisions'].values()):raise ValueError('complete_hash_bound_human_review_required')
  save(w,'approval.json',review);print('APPROVED for isolated technical registration; publication is separate')
 elif a.stage=='register':
  source=read(w/'source_import.json');approval=read(w/'approval.json')
  if approval['source_import_sha256']!=sha(w/'source_import.json'):raise ValueError('approved_source_changed')
  facts=[f for b in source['canonical_batches_private'] for f in b['facts']];pid=source['team_profile_private']['STRUCTURED_PROFILE']['persona_id']
  from operator_choice.operator_world_v1_1.turn_view import load_all_personas
  if pid in load_all_personas():raise ValueError('existing_customer_must_not_be_overwritten')
  shared=save(w,'shared_export.json',export(pid,facts));report,profile=intake_team_profile.check(str(shared),history_evidence_hold_ids=history_holds(facts),actor_evidence_guard=True)
  audit=semantic_audit(profile,facts)
  if report['issues'] or audit['errors']:raise ValueError('product_contract_issues_require_review')
  save(w,'profile.json',profile);save(w,'library.json',library(pid,facts));save(w,'product_check.json',report)
  baseline=[];base=a.base_registry
  if not a.standalone_registry and base is None and (ROOT/'handover/data/bundle.json').exists():
   from bootstrap_data import bootstrap
   base=Path(bootstrap()['path'])
  if base is not None:
   from operator_choice.operator_world_v1_1.isolated_registry import _read
   registry=_read(ref(base))
   if registry.get('contract_version')!='hillink-isolated-intake-v1':raise ValueError('base_registry_contract_mismatch')
   baseline=registry['customers']
   for row in baseline:
    if row['customer_id']==pid:raise ValueError('existing_customer_must_not_be_overwritten')
    for key in ('profile','library','source_import','product_check'):_read(row[key])
  baseline.append(dict(customer_id=pid,profile=ref(w/'profile.json'),library=ref(w/'library.json'),source_import=ref(w/'source_import.json'),product_check=ref(w/'product_check.json'),approval_status='ISOLATED_PILOT_APPROVED'))
  save(w,'registry.json',dict(contract_version='hillink-isolated-intake-v1',customers=baseline))
  print(json.dumps(dict(status='REGISTERED_NOT_EXECUTION_VERIFIED',registry_sha256=sha(w/'registry.json'))))
 else:
  import urllib.request,urllib.parse
  u=urllib.parse.urlsplit(a.server)
  if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('loopback_server_required')
  registry=read(w/'registry.json');pid=read(w/'source_import.json')['team_profile_private']['STRUCTURED_PROFILE']['persona_id'];results=[]
  for duration in ('stay_1','stay_2'):
   for event in ('none','wine'):
    request=dict(personas=[pid],duration=duration,event_mode=event,seed=17,behavior_engine='m4',include_ledger=True)
    req=urllib.request.Request(a.server+'/api/visit',data=json.dumps(request).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=600) as response:result=json.load(response)
    ledger=result.get('ledger',{});checks=ledger.get('checks',{})
    if not checks.get('receipts_equal_L4_L3_L2_L1') or not checks.get('day_totals_equal_visit_total'):raise ValueError('visit_ledger_verification_failed')
    results.append(dict(request=request,run_id=ledger['run_id'],checks=checks))
  save(w,'execution_verification.json',dict(status='EXECUTION_VERIFIED_TECHNICAL_ONLY',registry_sha256=sha(w/'registry.json'),results=results));print('EXECUTION_VERIFIED_TECHNICAL_ONLY')
if __name__=='__main__':main()
