"""Fresh official 14:10 Santa A/S1/S2 native runs; private raw evidence only.
No prior result fallback, no external LLM calls, no engine modifications.
"""
import argparse,copy,gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def fingerprint():
 paths=subprocess.check_output(['git','ls-files','timeline'],cwd=ROOT,text=True).splitlines()
 return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths if Path(p).suffix in ('.py','.json','.csv') and '/tests/' not in p and '/static/' not in p}
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--scenario',choices=['A','S1','S2'],required=True);ap.add_argument('--private-dir',type=Path,required=True)
 ap.add_argument('--families-only',action='store_true');ap.add_argument('--child-age-months',type=int,choices=[24,60,96]);ap.add_argument('--nights',type=int,choices=[1,2,3]);ap.add_argument('--first-customer-only',action='store_true')
 ap.add_argument('--registry',type=Path,required=True);ap.add_argument('--registry-sha256',required=True);ap.add_argument('--expected-commit',required=True)
 args=ap.parse_args();os.umask(0o077)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if commit!=args.expected_commit:raise RuntimeError('SOURCE_COMMIT_MISMATCH')
 if hashlib.sha256(args.registry.read_bytes()).hexdigest()!=args.registry_sha256:raise RuntimeError('PRIVATE_REGISTRY_SHA_MISMATCH')
 os.environ.update(HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_V12Z_COMMON='1',HILLINK_NATIVE_HYBRID='1',HILLINK_HYBRID='replay',HILLINK_GENERAL_FOOD_POLICY='A',HILLINK_BREAKFAST_POLICY='BREAKFAST_INCLUDED_DEFAULT_V2',HILLINK_ISOLATED_CUSTOMERS='1',HILLINK_ISOLATED_REGISTRY=str(args.registry.resolve()),HILLINK_ISOLATED_REGISTRY_SHA256=args.registry_sha256,HILLINK_REVIEWER_LOCAL='1',HTTP_PROXY='http://127.0.0.1:9',HTTPS_PROXY='http://127.0.0.1:9')
 sys.path.insert(0,str(ROOT/'timeline/viewer'))
 import visit_run as V
 import ledger_service as L
 preset=json.loads((ROOT/'timeline/viewer/static/strategy_santa_ab.json').read_text());fixed=preset['fixed'];families=preset['booked_families']
 ids=sorted(V.IR.allowed_personas(V.AD.DEMO));assert len(ids)==28 and len(families)==6
 conditions={f['id']:dict(party_size=3,party_composition={'adult_count':2,'children':[{}]},**({'building':f['building']} if f.get('building') else {})) for f in families}
 if args.families_only:ids=sorted(f['id'] for f in families)
 if args.first_customer_only:ids=ids[:1]
 conditions={k:v for k,v in conditions.items() if k in ids}
 if args.child_age_months is not None:
  for v in conditions.values():v['party_composition']['children']=[{'age_months':args.child_age_months,'school_stage':'elementary' if args.child_age_months==96 else 'preschool'}]
 booking={f['id']:{'date':fixed['start_date'],'start':fixed['booked_start']} for f in families if f['id'] in ids}
 request=dict(personas=ids,duration=fixed['duration'],seed=fixed['seed'],start_date=fixed['start_date'],event_mode='none',include_ledger=True,behavior_engine='m4_c01',simulation_mode='shared_world',breakfast_policy='BREAKFAST_INCLUDED_DEFAULT_V2',scenario={'event_card_id':'SANTA_KIDS_VILLAGE_2025','assumptions':{**copy.deepcopy(fixed['scenario_assumptions']),'booked_sessions':booking},'arrival_time':fixed['arrival_time']},visit_conditions=conditions,catalog_policy='C01_HOTEL_CATALOG_V1',catalog_options={})
 if args.nights:request['duration']='stay_'+str(args.nights)
 if args.scenario!='A':
  promo=next(p for p in preset['promotions'] if p['id']==args.scenario);request['catalog_options']={'discount_percent':{promo['sku_id']:promo['default_percent']}}
 target=args.private_dir.resolve();target.mkdir(parents=True,exist_ok=True)
 stem=target/args.scenario
 if stem.with_suffix('.flow.private.json.gz').exists():raise RuntimeError('EXISTING_RUN_PRESERVED_USE_NEW_DIRECTORY')
 initial=fingerprint();start=time.monotonic()
 meta={'scenario':args.scenario,'request':request,'source_commit':commit,'source_fingerprint':initial,'registry_sha':args.registry_sha256,'input_definition':'strategy_santa_ab.json official14:10 preset plus explicit shared_world and breakfast V2','preset_sha256':hashlib.sha256((ROOT/'timeline/viewer/static/strategy_santa_ab.json').read_bytes()).hexdigest(),'paid_llm_calls':0,'source_mode':'FRESH_NATIVE_RUN_VISIT_AND_REGISTER_VISIT'}
 stem.with_suffix('.request.private.json').write_text(json.dumps(request,ensure_ascii=False,indent=2))
 print('START',args.scenario,commit,flush=True)
 flow=V.run_visit(request)
 if flow.get('error'):raise RuntimeError(flow['error'])
 flow['ledger']=L.register_visit(flow,request)
 if fingerprint()!=initial:raise RuntimeError('SOURCE_MUTATED_DURING_RUN')
 if flow['ledger'].get('source')!='live_engine':raise RuntimeError('NOT_LIVE_ENGINE')
 if flow['visit'].get('breakfast_policy')!='BREAKFAST_INCLUDED_DEFAULT_V2':raise RuntimeError('BREAKFAST_POLICY_MISMATCH')
 data_path=stem.with_suffix('.flow.private.json.gz')
 with gzip.open(data_path,'wt',encoding='utf-8',compresslevel=1) as f:json.dump(flow,f,ensure_ascii=False,default=list)
 meta.update(run_id=flow['ledger']['run_id'],visit_id=flow['visit_id'],elapsed_seconds=round(time.monotonic()-start,2),source_unchanged=True,raw_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest(),raw_bytes=data_path.stat().st_size,paid_krw=flow['ledger']['totals']['paid_krw'],checks=flow['ledger']['checks'])
 stem.with_suffix('.meta.private.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 print(json.dumps({k:meta[k] for k in ['scenario','source_commit','run_id','elapsed_seconds','paid_krw','raw_sha256','checks']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
