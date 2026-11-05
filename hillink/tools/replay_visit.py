"""Re-execute one submitted V16 visit using its exact original provider receipts.

No key or cost journal is needed. A missing cache entry holds execution; network
access is blocked before any engine import. Output must be a new file.
"""
import argparse, gzip, json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/offline_test_guard'))
import sitecustomize
os.environ['PYTHONPATH']=str(ROOT/'tools/offline_test_guard')+(os.pathsep+os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')
sys.path.insert(0,str(ROOT/'tools'))
from bootstrap_data import bootstrap

def replay(tag,output):
    output=Path(output)
    if output.exists():raise ValueError('OUTPUT_MUST_BE_NEW')
    data=bootstrap()
    os.environ.update(HILLINK_AGENT_MODE='replay',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',
        HILLINK_AUTONOMOUS_AGENT='1',HILLINK_V12Z_COMMON='1',HILLINK_NATIVE_HYBRID='1',
        HILLINK_HYBRID='replay',HILLINK_ISOLATED_CUSTOMERS='1',HILLINK_REVIEWER_LOCAL='1',
        HILLINK_ISOLATED_REGISTRY=data['path'],HILLINK_ISOLATED_REGISTRY_SHA256=data['sha256'])
    sys.path.insert(0,str(ROOT/'timeline/viewer'))
    import saved_visits as S
    payload,row,_,_=S.payload(tag);spec=S.manifest()
    with tempfile.TemporaryDirectory(prefix='hillink-v16-replay-') as tmp:
        os.environ['HILLINK_AGENT_CACHE']=tmp
        for entry in row['replay_entries']:
            saved=S._read(entry['path'],spec)
            target=Path(tmp)/(entry['input_sha256']+'.json')
            if target.exists() and json.loads(target.read_text())['answer']!=saved['answer']:
                raise ValueError('AMBIGUOUS_SAME_INPUT_RESPONSES_REQUIRE_SEQUENCE_REVIEW')
            target.write_text(json.dumps(saved,ensure_ascii=False))
        import visit_run,ledger_service
        from operator_choice.autonomy_v1 import autonomous_agent as A
        if A.configuration()['source_sha256']!=payload['configuration']['source_sha256']:
            raise ValueError('EXECUTION_IMPLEMENTATION_CHANGED')
        flow=visit_run.run_visit(payload['request'])
        if 'error' in flow:raise ValueError('REPLAY_EXECUTION_FAILED:'+str(flow.get('code')))
        flow['ledger']=ledger_service.register_visit(flow,payload['request'])
        for pid,plan in flow['plans'].items():
            old=payload['result']['plans'][pid]['autonomous_decisions'];new=plan['autonomous_decisions']
            if [(d['input_sha256'],d.get('selected_plan')) for d in old]!=[(d['input_sha256'],d.get('selected_plan')) for d in new]:
                raise ValueError('REPLAY_DECISIONS_DIFFER_FROM_SUBMITTED_VISIT')
            if any(a['provider']['execution']!='CACHE_REPLAY' for d in new for a in d['attempts'] if a.get('provider')):
                raise ValueError('NON_REPLAY_PROVIDER')
        output.write_bytes(gzip.compress(json.dumps(dict(request=payload['request'],result=flow,
            current_paid_calls=0,source_tag=tag,human_approval=False),ensure_ascii=False).encode(),mtime=0))
        print(json.dumps(dict(tag=tag,output=str(output),current_paid_calls=0,
            decisions_match=True,checks=flow['ledger']['checks'])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();replay(a.tag,a.output)
