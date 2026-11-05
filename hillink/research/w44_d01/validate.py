import importlib.util,json,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'w44_m01/execute_cohort.py';s=importlib.util.spec_from_file_location('cohort',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
original=m.run
old=json.loads(Path('/private/tmp/hillink-w44-m01-qa/cohort_results.json').read_text())
def run(q):
 f,r=original(q);v=f['ledger']['virtual_revenue'];rows=v['rows'];n=f['visit']['nights'];assert len([x for x in rows if x['action_id']=='room_night'])==len(q['personas'])*n
 assert sum(x['virtual_gross_krw'] or 0 for x in rows)==v['levels']['L1']['virtual_gross_krw']
 assert v['levels']['L1']['virtual_gross_krw']==v['room']['virtual_gross_krw']+v['nonroom']['virtual_gross_krw']
 assert {x['row_id'] for x in rows}=={x['row_id'] for receipt in f['ledger']['receipts'].values() for x in receipt['rows']}
 key='shared' if len(q['personas'])>1 else 'independent'
 b=next(x for x in old[key] if x['request']==q)
 assert [x['behavioral_signature'] for x in r['customers']]==[x['behavioral_signature'] for x in b['customers']]
 r['virtual_revenue']={k:v[k] for k in ('room','nonroom','levels','historical_menu_room_assumption_krw')}
 if q['personas']==['A08']:r['room_examples']=[x for x in rows if x['action_id']=='room_night']
 return f,r
m.run=run;m.main()
