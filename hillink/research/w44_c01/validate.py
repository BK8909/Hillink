"""Finite real execution matrix. Offline, no provider calls, no stored replay."""
import json,sys,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'research/w44_m01'))
os.environ['HILLINK_LLM_EXTERNAL_OPT_IN']='0'
from execute_cohort import IDS,run,canonical
OUT=Path('/private/tmp/hillink-c01-qa');OUT.mkdir(exist_ok=True,mode=0o700)
report={'status':'RUNNING','engine':'m4_c01','independent':[],'shared':[],'paid_provider_calls':0}
def write():
 (OUT/'TEST_MATRIX.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
def main():
 try:
  for event in ('none','wine'):
   for pid in IDS:
    q=dict(personas=[pid],duration='stay_2',event_mode=event,seed=0,start_date='2026-10-24',behavior_engine='m4_c01')
    f,r=run(q);report['independent'].append(r);write()
    if pid=='A08':
     (OUT/f'a08_{event}.json').write_text(json.dumps({'request':q,'flow':f,'ledger':f['ledger']},ensure_ascii=False))
    print('INDIVIDUAL',pid,event,r['totals']['paid_krw'],flush=True)
  for n in range(4):
   for event in ('none','wine'):
    q=dict(personas=IDS,duration='day_visit' if n==0 else 'stay_'+str(n),event_mode=event,seed=0,start_date='2026-10-24',behavior_engine='m4_c01',simulation_mode='shared_world')
    f,r=run(q)
    assert len(f['shared_world']['days'])==n+1
    for day in f['shared_world']['days']:
     order=day['decision_order'];assert [x['decision_minute'] for x in order]==sorted(x['decision_minute'] for x in order)
     assert sorted(day['completed_customer_ids'])==sorted(IDS)
    assert f['ledger']['virtual_revenue']['room']['virtual_gross_krw']==(5804000*n//2)
    r['room_virtual_gross_krw']=f['ledger']['virtual_revenue']['room']['virtual_gross_krw']
    report['shared'].append(r);write()
    if n==2:(OUT/f'ten_{event}.json').write_text(json.dumps(f,ensure_ascii=False))
    print('SHARED',n,event,r['totals']['paid_krw'],flush=True)
  report['status']='PASS'
 except Exception as e:report.update(status='FAIL',error=str(e));raise
 finally:write()
if __name__=='__main__':main()
