"""Fresh M4 executions and evidence; never imports stored visit results."""
import argparse,collections,hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'timeline/viewer'))
os.environ['HILLINK_LLM_EXTERNAL_OPT_IN']='0'
import visit_run as VR
import ledger_service as LS
IDS=['A01','A02','A03','A04','A05','A07','A08','A10','blog41','blog42']

def canonical(f,pid):
 return [{k:e.get(k) for k in ('event_id','date','start','end','action_id','venue_id','fraction')} for e in f['plans'][pid]['m4']['activity_history']]
def signature(f,pid):
 return hashlib.sha256(json.dumps(canonical(f,pid),sort_keys=True).encode()).hexdigest()
def customer(f,L,pid):
 plan=f['plans'][pid];m=plan['m4'];scenes=plan['scenes'];v=f['visits'][pid];rows=L['receipts'][pid]['rows']
 decisions=m['decisions'];terms=[t for d in decisions for c in d['packet']['candidates'] for t in c.get('terms',[]) if t.get('facet') and t.get('value')]
 marginal=[(key,val['weight_delta_at_fixed_state']) for d in decisions for c in d['packet']['candidates'] for key,val in c.get('profile_feature_marginals',{}).items() if abs(val['weight_delta_at_fixed_state'])>.00001]
 perday=collections.defaultdict(list)
 for s in scenes:perday[s['visit_day']].append(s)
 assert all(all(a['t1']<=b['t0'] for a,b in zip(ss,ss[1:])) for ss in perday.values()),'OVERLAP '+pid
 assert all(s['t0']<=s['t1']<=1380 for s in scenes),'TIME_END '+pid
 assert len({r['row_id'] for r in rows})==len(rows)
 assert all(d['packet']['context_factors']['customer_id']==pid for d in decisions)
 assert len([r for r in rows if r['act']=='room_night'])==f['visit']['nights']
 assert all(day['flow']['visits'][pid]['party_size']==v['party_size'] and day['flow']['visits'][pid]['building']==v['building'] for day in f['visit_days'])
 meals=[e for e in m['activity_history'] if e['fraction']>=.8 and e.get('meal_slot')]
 close=[]
 for a,b in zip(meals,meals[1:]):
  gap=b['end_absolute']-VR.AD.hm(b['end'])+VR.AD.hm(b['start'])-a['end_absolute']
  if 0<=gap<120:close.append({'prior':a['event_id'],'next':b['event_id'],'gap_minutes':gap,'status':'REVIEW_NOT_AUTOMATIC_FAILURE'})
 actions=[s for s in scenes if s['act'] not in VR.NON_ACTION_CODES]
 return dict(customer_id=pid,customer_type=L['receipts'][pid]['customer_type'],conditions={k:v.get(k) for k in ('building','party_size','duration','nights','club')},
  behavioral_signature=signature(f,pid),behavior_profile_sha256=m['behavior_profile_sha256'],facts_traits_sha256=m['facts_traits_sha256'],
  selection_count=len(decisions),nonzero_trait_score_terms=len(terms),nonzero_planner_feature_differences=len(marginal),
  actual_personalization_signal=bool(terms or marginal),
  paid_krw=sum(r['paid_krw'] for r in rows),room_assumption_krw=sum(r['assumption_addition_krw'] for r in rows),unknown_count=sum(r['status']=='금액 미확인' for r in rows),
  action_count=len(actions),transaction_count=len(rows),trace_scope='actual contributing terms or fixed-state single-feature ablations; not human quality approval',
  activities=[{k:s.get(k) for k in ('visit_day','visit_date','t0','t1','act','loc','meal','domain')} for s in actions],
  full_meal_short_gap_review=close,technical_status='PASS')
def run(q):
 started=time.monotonic();f=VR.run_visit(q)
 if f.get('error'):raise RuntimeError(f)
 L=LS.register_visit(f,q);f['ledger']=L
 assert L['checks']['day_totals_equal_visit_total'] and L['checks']['receipts_equal_L4_L3_L2_L1']
 assert sum(r['paid_krw'] for c in L['receipts'].values() for r in c['rows'])==L['totals']['paid_krw']
 return f,{'request':q,'visit_id':f['visit_id'],'ledger_run_id':L['run_id'],'engine':f['engine'],'seconds':round(time.monotonic()-started,3),'totals':L['totals'],'checks':L['checks'],'customers':[customer(f,L,pid) for pid in q['personas']]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True,mode=0o700);out.chmod(0o700)
 def write(name,x):
  p=out/name;p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600)
 source=VR.AD.load_inputs();assert set(IDS)<=set(VR.AD.DEMO)&set(source[0])
 report={'status':'RUNNING','cohort':IDS,'excluded':'blog43 is also runnable; omitted only to keep this cohort at 10. Eight named profiles plus two development comparison profiles; not proof of 10 independently verified authors','source_author_pending':['blog41','blog42'],'independent':[],'shared':[],'paid_api_calls':0,'capacity_and_queues_supported':False}
 independent={}
 try:
  for event in ('none','wine'):
   for pid in IDS:
    q=dict(personas=[pid],duration='stay_2',event_mode=event,seed=0,start_date='2026-10-24',simulation_mode='independent')
    f,r=run(q);independent[event,pid]=canonical(f,pid);report['independent'].append(r)
    write('cohort_results.json',report);print('INDEPENDENT',event,pid,r['totals']['paid_krw'],flush=True)
  for duration in ('stay_2','day_visit','stay_1','stay_3'):
   for event in ('none','wine'):
    q=dict(personas=IDS,duration=duration,event_mode=event,seed=0,start_date='2026-10-24',simulation_mode='shared_world')
    f,r=run(q);w=f['shared_world']
    for day in w['days']:
     order=day['decision_order'];assert [e['decision_minute'] for e in order]==sorted(e['decision_minute'] for e in order)
     assert set(day['completed_customer_ids'])==set(IDS) and day['world_instance_count']==1
     assert len({x['customer_id'] for x in order})==10
    if duration=='stay_2':
     assert all(canonical(f,pid)==independent[event,pid] for pid in IDS)
     r['same_as_independent_when_no_contention']=True
     write('private_shared_'+event+'.json',f)
    r['world_days']=[{'date':d['date'],'world_id':d['world_id'],'steps':len(d['decision_order']),'interleave_switches':sum(a['customer_id']!=b['customer_id'] for a,b in zip(d['decision_order'],d['decision_order'][1:]))} for d in w['days']]
    r['operations_checks']=f['ledger']['operations']['checks'];r['operations_bucket_count']=len(f['ledger']['operations']['buckets'])
    report['shared'].append(r);write('cohort_results.json',report);print('SHARED',duration,event,r['totals']['paid_krw'],flush=True)
  report['status']='PASS'
 except Exception as e:
  report['status']='FAIL';report['error']=str(e);raise
 finally:write('cohort_results.json',report)
if __name__=='__main__':main()
