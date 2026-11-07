"""Offline replay of saved V16 visits under the CURRENT code (implementation SHA not pinned).

Reports, per run: decision origins, END_DAY handling, holds. No network, no key, no cost.
Usage: python3.11 replay_check.py <hillink root> TAG [TAG ...]
"""
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT/'tools/offline_test_guard'))
import sitecustomize  # noqa
os.environ['PYTHONPATH']=str(ROOT/'tools/offline_test_guard')
sys.path.insert(0,str(ROOT/'tools'))
from bootstrap_data import bootstrap

def main(tags):
    data=bootstrap()
    os.environ.update(HILLINK_AGENT_MODE='replay',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',
        HILLINK_AUTONOMOUS_AGENT='1',HILLINK_V12Z_COMMON='1',HILLINK_NATIVE_HYBRID='1',HILLINK_HYBRID='replay',
        HILLINK_ISOLATED_CUSTOMERS='1',HILLINK_REVIEWER_LOCAL='1',HILLINK_ISOLATED_REGISTRY=data['path'],
        HILLINK_ISOLATED_REGISTRY_SHA256=data['sha256'])
    sys.path.insert(0,str(ROOT/'timeline/viewer'))
    import saved_visits as S
    spec=S.manifest()
    out=[]
    for tag in tags:
        payload,row,_,_=S.payload(tag)
        with tempfile.TemporaryDirectory(prefix='hillink-replay-check-') as tmp:
            os.environ['HILLINK_AGENT_CACHE']=tmp
            for entry in row['replay_entries']:
                saved=S._read(entry['path'],spec)
                (Path(tmp)/(entry['input_sha256']+'.json')).write_text(json.dumps(saved,ensure_ascii=False))
            import visit_run
            flow=visit_run.run_visit(payload['request'])
            rep=dict(tag=tag,error=flow.get('error'),code=flow.get('code'))
            for pid,plan in (flow.get('plans') or {}).items():
                decs=plan.get('autonomous_decisions') or []
                old=payload['result']['plans'][pid]['autonomous_decisions']
                rep[pid]=dict(decisions=len(decs),old=len(old),
                    origins=[a['provider'].get('execution') for d in decs for a in d.get('attempts',[]) if a.get('provider')],
                    states=[d.get('execution_state') for d in decs],
                    holds=[d.get('fallback_reason') for d in decs if d.get('execution_state')=='EXECUTION_HOLD'],
                    rejections=[a.get('validation_rejection','')[:80] for d in decs for a in d.get('attempts',[]) if a.get('validation_rejection')],
                    same_selection=[(d['input_sha256'],d.get('selected_plan')) for d in old][:len(decs)]==[(d['input_sha256'],d.get('selected_plan')) for d in decs],
                    scenes_end=[(s.get('act'),s.get('label')) for s in plan.get('scenes',[]) if s.get('act') in ('sleep','room_night')])
            out.append(rep)
            print(json.dumps(rep,ensure_ascii=False))
    return out

if __name__=='__main__':main(sys.argv[2:])
