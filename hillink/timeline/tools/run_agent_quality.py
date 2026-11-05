"""Private, append-only QA runs using an existing approved journal and cache.

Run preflight once before a batch; workers check that preserved journal prefix.
Concurrent reservations after that checkpoint are recorded, never cleared.
cached_live reuses identical requests and labels them CACHE_REPLAY.
"""
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'timeline/viewer'))
import visit_run as V
import ledger_service as L
import agent_evaluation as E
from operator_choice.autonomy_v1 import autonomous_agent as A, agent_provider as P


def save(path,value,compressed=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
        f.write(gzip.compress(data) if compressed else data)


def journal(path):
    # Never let Budget._update create a replacement for a missing shared file.
    with Path(path).open('rb') as f:
        fcntl.flock(f,fcntl.LOCK_SH);raw=f.read()
    state=json.loads(raw);rows=state['requests']
    if state['max_calls']!=2500 or state['max_usd']!=20:
        raise ValueError('EXISTING_2500_USD20_JOURNAL_REQUIRED')
    if not any(x.get('approved_max_calls')==2500 and x.get('unchanged_max_usd')==20
               and x.get('approval_reference') for x in state.get('limit_amendments',[])):
        raise ValueError('EXISTING_APPROVAL_REQUIRED')
    return dict(path=str(Path(path).resolve()),sha256=hashlib.sha256(raw).hexdigest(),
        calls=len(rows),cost_upper_usd=sum(r.get('charged_upper_usd',r['reserved_usd']) for r in rows),
        unresolved=[r['id'] for r in rows if r['state']=='RESERVED'],
        requests_sha256=P.digest(rows),states=dict(Counter(r['state'] for r in rows))),state


def batch_check(args):
    snapshot,state=journal(args.journal)
    if args.command=='preflight':
        if snapshot['unresolved']:raise ValueError('UNSETTLED_PRIOR_REQUESTS_HOLD')
        save(args.batch_state,snapshot)
    else:
        prior=json.loads(Path(args.batch_state).read_text())
        if prior['path']!=snapshot['path'] or prior['unresolved']:
            raise ValueError('BATCH_JOURNAL_MISMATCH')
        if P.digest(state['requests'][:prior['calls']])!=prior['requests_sha256']:
            raise ValueError('PRESERVED_JOURNAL_PREFIX_CHANGED')
    if snapshot['calls']>=2500 or snapshot['cost_upper_usd']>=20:
        raise ValueError('BUDGET_EXHAUSTED')
    return snapshot


def receipt(cache,trace):
    identity=trace['input_sha256']
    # The first-response cache alone cannot identify a repeated live response.
    path=Path(cache)/'live_history'/f"{identity}.{trace['id']}.json"
    if not path.exists():path=Path(cache)/(identity+'.json')
    row=json.loads(path.read_text())
    if (row['origin']!='LIVE_RESPONSES' or row['input_sha256']!=identity
            or row['trace']['id']!=trace['id'] or row['trace'].get('response_id')!=trace.get('response_id')):
        raise ValueError('RECEIPT_IDENTITY_MISMATCH')
    return row


def context_and_lineage(payload,cache):
    pid=payload['request']['personas'][0];plan=payload['result']['plans'][pid]
    facts={};decisions=[];sources=[];lineage=[]
    for d in plan.get('autonomous_decisions',[]):
        refs=[]
        for attempt in d['attempts']:
            trace=attempt.get('provider') or {}
            if trace.get('execution') not in ('LIVE_RESPONSES','CACHE_REPLAY'):continue
            saved=receipt(cache,trace);source=saved['audit_input']['context']
            if saved['answer']!=attempt.get('answer'):raise ValueError('PROVIDER_ANSWER_MISMATCH')
            if saved['audit_input']['policy']!=d['policy']:raise ValueError('POLICY_MISMATCH')
            index=saved['answer']['selected_index'];plans=saved['answer']['plans']
            selected=plans[index] if 0<=index<len(plans) else None
            accepted=not attempt.get('validation_rejection')
            if accepted and d.get('selected_plan')!=selected:raise ValueError('SELECTED_PLAN_MISMATCH')
            if accepted:
                if selected is None:raise ValueError('ACCEPTED_PLAN_INDEX_INVALID')
                action=next((a for a in source['actions'] if a['action_id']==selected['action_id']),None)
                if action is None:raise ValueError('SELECTED_ACTION_NOT_IN_INPUT')
                cited=set(selected['supporting_fact_ids'])|set(selected['counterevidence_fact_ids'])
                if cited-set(source['personal']['citable_fact_ids']):raise ValueError('SELECTED_FACT_NOT_IN_INPUT')
                if action['kind']=='MEAL':
                    products={p['sku_id'] for p in source['menus'][selected['action_id']]}
                    if any(i['sku_id'] not in products for i in selected['items']):raise ValueError('SELECTED_SKU_NOT_IN_INPUT')
                elif selected['items']!=action['items'] or selected['order_total_krw']!=action['order_total_krw']:
                    raise ValueError('FIXED_INPUT_ORDER_MISMATCH')
            if not refs and P.digest(source)!=d['input_sha256']:raise ValueError('INITIAL_CONTEXT_MISMATCH')
            for f in source.get('personal',{}).get('evidence_records',[]):
                for fid in f['fact_ids']:facts[fid]=dict(f,id=fid)
            # Preserve exact source snapshots in the cache; the independent
            # review receives unmodified decision-relevant fields once.
            view={k:source.get(k) for k in ('visit','state','needs_model','meal_experiences',
                'activity_experiences','memory','actions','reassessment','pending_schedule','contract')}
            wanted={i['sku_id'] for p in saved['answer']['plans'] for i in p['items']}
            view['referenced_menu_contracts']=[p for menu in source.get('menus',{}).values()
                                               for p in menu if p['sku_id'] in wanted]
            refs.append(trace['input_sha256'])
            sources.append(dict(input_sha256=trace['input_sha256'],context=view,
                exclusion_summary=dict(count=len(source.get('world_exclusions',source.get('excluded',[]))),
                    full_source_preserved=True)))
            lineage.append(dict(customer=pid,date=d['date'],minute=d['minute'],policy=d['policy'],
                model=trace['model'],model_returned=trace.get('model_returned'),
                input_sha256=trace['input_sha256'],context_sha256=P.digest(source),response_id=trace.get('response_id'),
                reservation_id=trace['id'],execution=trace['execution'],accepted=accepted,
                input_policy=saved['audit_input']['policy'],selected_action_id=(selected or {}).get('action_id')))
        decisions.append(dict(id=P.digest(d),date=d['date'],minute=d['minute'],policy=d['policy'],
            execution_state=d['execution_state'],selected_plan=d.get('selected_plan'),
            considered_plans=[a.get('answer') for a in d['attempts']],source_inputs=refs,
            candidate_count=d.get('candidate_count'),fallback_reason=d.get('fallback_reason')))
    context=dict(customer_id=pid,evidence=list(facts.values()),decision_comparisons=decisions,
        exact_decision_input_summaries=sources,request=payload['request'],
        full_executed_activity_timeline=plan.get('autonomous_memory',{}).get('activity_experiences',[]),
        full_simulation_timeline=[dict(date=s.get('visit_date'),start=s['t0'],end=s['t1'],
            travel_minutes=s.get('travel',0),venue=s.get('loc'),label=s.get('label'),domain=s.get('domain'),
            meal=s.get('meal'),charge=(s.get('basis') or {}).get('charge')) for s in plan['scenes']],
        simulation_scope='VIRTUAL_EXECUTION_NOT_OBSERVED_INTAKE_OR_SATISFACTION',
        limitations='Clock meal slots are not customer meal intent. Access rights are not dedicated dishes. '
            'Numerical needs and portion shares are assumptions. Full exclusion details remain in exact receipts; '
            'this review does not certify all exclusions. Human semantic approval is separate.')
    return context,lineage


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['preflight','visit','review'])
    for name in ('journal','cache','batch-state'):ap.add_argument('--'+name,required=True)
    ap.add_argument('--out',type=Path);ap.add_argument('--tag');ap.add_argument('--request',type=Path)
    ap.add_argument('--fresh-repeat-purpose',help='Explicit planned stochastic replication; otherwise identical inputs replay.')
    args=ap.parse_args()
    before=batch_check(args)
    if args.command=='preflight':print(json.dumps(before));return
    if not args.out or not args.tag or Path(args.tag).name!=args.tag:raise ValueError('OUTPUT_TAG_REQUIRED')
    if args.command=='visit' and (args.out/'PAID_VISIT_HOLD.private.json').exists():
        raise ValueError('NEW_VISITS_HELD_FOR_INPUT_CONTRACT_REPAIR')
    out=args.out/(args.tag+'.private.json.gz')
    target=out if args.command=='visit' else args.out/(args.tag+'-independent.private.json')
    if target.exists():raise ValueError('PRESERVED_RESULT_EXISTS')
    os.environ.update(HILLINK_V12Z_COMMON='1',HILLINK_NATIVE_HYBRID='1',HILLINK_AUTONOMOUS_AGENT='1',
        HILLINK_AGENT_MODE=('live' if args.fresh_repeat_purpose and args.command=='visit' else 'cached_live'),
        HILLINK_LLM_EXTERNAL_OPT_IN='1',HILLINK_LLM_ENABLED='0',
        HILLINK_GENERAL_FOOD_POLICY='A',HILLINK_BREAKFAST_POLICY='BREAKFAST_INCLUDED_DEFAULT_V2',
        HILLINK_AGENT_BUDGET_FILE=str(Path(args.journal).resolve()),HILLINK_AGENT_MAX_USD='20',
        HILLINK_AGENT_MAX_CALLS='2500',HILLINK_AGENT_CACHE=str(Path(args.cache).resolve()),HILLINK_HYBRID='off')
    if args.command=='visit':
        request=json.loads(args.request.read_text());request['hybrid_policy']=A.POLICY
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        configuration=A.configuration()
        start=time.time();result=V.run_visit(request)
        if 'error' not in result:result['ledger']=L.register_visit(result,request)
        payload=dict(request=request,result=result,head=head,configuration=configuration,
            replication_purpose=args.fresh_repeat_purpose,
            source_unchanged_during_execution=configuration['source_sha256']==A.configuration()['source_sha256'],
            elapsed=time.time()-start,budget_before=before,budget_after=journal(args.journal)[0])
        save(out,payload,True)
        if not payload['source_unchanged_during_execution']:raise ValueError('SOURCE_CHANGED_DURING_EXECUTION')
        if 'error' in result:
            print(json.dumps(dict(tag=args.tag,error=result.get('code'))));return
        context,lineage=context_and_lineage(payload,args.cache)
        save(args.out/(args.tag+'-lineage.private.json'),lineage)
        save(args.out/(args.tag+'-summary.private.json'),dict(tag=args.tag,head=head,
            request_sha256=P.digest(request),artifact_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
            audit=E.audit(result,request['personas'][0]),checks=result['ledger']['checks'],
            sources=dict(Counter(r['execution'] for r in lineage)),budget_after=payload['budget_after']))
        print(json.dumps(dict(tag=args.tag,status='SAVED',decisions=len(lineage),elapsed=payload['elapsed'])),flush=True)
    else:
        payload=json.load(gzip.open(out,'rt'));context,lineage=context_and_lineage(payload,args.cache)
        cp=args.out/(args.tag+'-review-context.private.json')
        if cp.exists():
            if json.loads(cp.read_text())!=context:raise ValueError('REVIEW_CONTEXT_CHANGED')
        else:save(cp,context)
        answer=E.review(context)
        save(target,dict(customer_id=payload['request']['personas'][0],source_head=payload['head'],
            evaluator_source_sha256=hashlib.sha256(Path(E.__file__).read_bytes()).hexdigest(),
            context_sha256=P.digest(context),review=answer,contract_audit=E.audit(payload['result'],context['customer_id'])))
        print(json.dumps(dict(tag=args.tag,status=answer['review_status'],findings=len(answer['findings']))),flush=True)


if __name__=='__main__':main()
