"""Opt-in fresh BE01 execution. Frozen research dependencies are mounted read-only.

The response keeps the native C01 candidate engine and D01 ledger arithmetic.
The planning policy and its invocation are reported as separate provenance.
"""
from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys, uuid

VERSION = 'BE01_SHARED_TIME_INTAKE_25fc2a899514_active'
SEAL_ID = '25fc2a899514e9455eb14f0116fafe6963e0a3538b4c8a31351a62cdf26e59b3'
CUSTOMERS = frozenset(['A01','A02','A03','A04','A05','A07','A08','A10','blog41','blog42','blog43'])
BUNDLE = Path(os.environ.get('HILLINK_BE01_BUNDLE','/private/tmp/hillink-be01-cohort-20261029'))
RUNNER = Path(__file__).with_name('be01_runner')/'run_be01.py'
OUTPUT = Path('/private/tmp/hillink-be01-product-new-20261029')

def error(code, message):
    return {'error': message, 'code': code}

def validate_request(request):
    ids=request.get('personas')
    if not isinstance(ids,list) or not ids or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids) or set(ids)-CUSTOMERS:
        return error('E_BE01_CUSTOMERS','BE01 검수 고객을 선택해 주세요.')
    if request.get('duration')!='stay_2' or request.get('event_mode')!='wine' or request.get('start_date','2026-10-24')!='2026-10-24':
        return error('E_BE01_SCENARIO','BE01 시범은 2박·와인페어 방문에서 실행할 수 있습니다.')
    scenario=request.get('scenario')
    if (scenario is not None and scenario!={'event_card_id':'WINE_FAIR_2026_AUTUMN'}) or request.get('package_id'):
        return error('E_BE01_SCOPE','이 행사·패키지는 현재 BE01 시범 검수 범위에 없습니다.')
    if type(request.get('seed',0)) is not int or not 0<=request.get('seed',0)<=9999:
        return error('E_BE01_SEED','시드 입력을 확인해 주세요.')
    if request.get('simulation_mode','shared_world' if len(ids)>1 else 'independent') not in ('independent','shared_world'):
        return error('E_BE01_MODE','실행 방식을 확인해 주세요.')

def validate_result(result,reasons,links,request):
    flow=result['flow'];ids=request['personas'];run=result['run_id'];ledger=result['ledger']
    if result['engine_version']!=VERSION or result['provider_calls']!=0 or flow['visit_id']!=run or set(flow['plans'])!=set(ids):
        raise ValueError('BE01 response version/customer mismatch')
    if reasons['run_id']!=run:raise ValueError('BE01 reason run mismatch')
    seen=set()
    for r in reasons['records']:
        pid=r['customer_id'];key=(r['run_id'],pid,r['actual_event_id'])
        if pid not in flow['plans'] or r['run_id']!=run or key in seen:raise ValueError('BE01 reason ownership mismatch')
        seen.add(key)
        events=[e for e in flow['plans'][pid]['m4']['activity_history'] if e['event_id']==r['actual_event_id']]
        if len(events)!=1 or events[0]['action_id']!=r['action'] or events[0]['date']!=r['time']['date'] or events[0]['start']!=r['time']['start']:
            raise ValueError('BE01 reason/action mismatch')
    native_rows={row['row_id']:(pid,row) for pid,receipt in ledger['receipts'].items() for row in receipt['rows']}
    if len(links)!=len(native_rows):raise ValueError('BE01 transaction count mismatch')
    for link in links:
        if link['run_id']!=run or link['row_id'] not in native_rows or native_rows[link['row_id']][0]!=link['customer_id']:
            raise ValueError('BE01 transaction ownership mismatch')
        if link['event_id'] and (run,link['customer_id'],link['event_id']) not in seen:
            raise ValueError('BE01 transaction reason missing')
    return flow

def run_visit(request):
    invalid=validate_request(request)
    if invalid:return invalid
    try:
        seal=json.loads((BUNDLE/'SEAL.json').read_text())
        if seal['identity']!=SEAL_ID:raise ValueError('Frozen bundle identity mismatch')
        # Each invocation gets an empty, unique output path. Never read cohort/runs.
        OUTPUT.mkdir(exist_ok=True,mode=0o700)
        invocation=uuid.uuid4().hex;directory=OUTPUT/invocation;directory.mkdir(mode=0o700)
        native={k:v for k,v in request.items() if k not in ('behavior_engine','include_ledger','scenario')}
        native.update(behavior_engine='m4_c01',start_date=request.get('start_date','2026-10-24'),seed=request.get('seed',0))
        native.setdefault('simulation_mode','shared_world' if len(native['personas'])>1 else 'independent')
        q=directory/'request.json';q.write_text(json.dumps(native,ensure_ascii=False));q.chmod(0o600)
        started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        process=subprocess.run([sys.executable,str(RUNNER),'--bundle',str(BUNDLE),'--request',str(q),'--policy','active','--out',str(directory/'result')],capture_output=True,text=True,timeout=7200,env={**os.environ,'HILLINK_LLM_EXTERNAL_OPT_IN':'0'})
        (directory/'execution.log').write_text(process.stdout+'\n'+process.stderr)
        if process.returncode:raise ValueError('Frozen BE01 runner failed')
        output=directory/'result';result=json.loads((output/'run.json').read_text());reasons=json.loads((output/'reasons.json').read_text());links=json.loads((output/'transaction_links.json').read_text())
        flow=validate_result(result,reasons,links,native)
        if request.get('scenario'):
            from operator_choice.autonomy_v1 import event_scenarios as ES
            # This sole supported card is an explicit translation to the sealed
            # runner's native wine switch; no event code is patched into the seal.
            current=Path(__file__).resolve().parents[1]/'place_assumptions.csv'
            frozen=BUNDLE/'frozen/runtime/timeline/place_assumptions.csv'
            if current.read_bytes()!=frozen.read_bytes():raise ValueError('Wine source differs from frozen runtime')
            flow['visit']['scenario_snapshot']=ES.snapshot(request['scenario'],native['start_date'],native['duration'])
        flow['engine'].update(requested_behavior_engine='be01',candidate_engine='m4_c01',policy_engine='be01_shared_time_intake',policy_version=VERSION,llm_calls=0,fresh_invocation_id=invocation)
        # Native flow/ledger IDs remain intact. The ledger run is a separate issued ID.
        flow['be01']={'version':VERSION,'execution_run_id':result['run_id'],'invocation_id':invocation,'computed_at':started,'sealed_runtime_identity':SEAL_ID,'reason_bundle':reasons,'transaction_links':links,'policy_trace':result['policy_trace'],'execution_lineage':result['execution_lineage'],'native_ledger':{'run_id':result['ledger']['run_id'],'totals':result['ledger']['totals'],'customer_totals':{pid:{'paid_krw':r['paid_krw'],'unknown_count':r['unknown_count']} for pid,r in result['ledger']['receipts'].items()}},'provider_calls':0,'execution_mode':'NEW_PROCESS_NEW_EMPTY_OUTPUT_NO_STORED_RUN_INPUT'}
        if request.get('scenario'):flow['be01']['scenario_binding']={'method':'EXPLICIT_WINE_CARD_TO_EQUIVALENT_NATIVE_EVENT_MODE','input':request['scenario'],'native_event_mode':native['event_mode'],'source_bytes_equal':True}
        return flow
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        # No native-policy fallback disguised as BE01 and no paid provider fallback.
        sys.stderr.write('BE01 fresh execution failed: '+str(exc)+'\n')
        return error('E_BE01_EXECUTION','BE01 새 방문 계산을 완료하지 못했습니다. 실행 기록을 확인해 주세요.')
