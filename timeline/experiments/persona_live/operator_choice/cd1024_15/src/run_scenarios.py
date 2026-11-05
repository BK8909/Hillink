"""Reproduce CD-14's four Buffet discount runs via the live frozen rule engine."""
import csv,json
from pathlib import Path
from experiment_service import default_request,run_request
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'
OUT.mkdir(exist_ok=True)
summary=[]; customer_rows=[]; candidate_rows=[]; eligibility_rows=None
for amount in (0,10000,20000,40000):
    req=default_request()
    req['scenario_id']=f'CD14_BUFFET_DISCOUNT_{amount}_PER_PERSON'
    if amount:
        req['offer_overrides']={'THE_BUFFET':{'discount_amount':amount,'discount_unit':'per_person','scenario_label':f'Assumed Buffet discount {amount} KRW/person'}}
    result=run_request(req)
    (OUT/f'discount_{amount}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if eligibility_rows is None: eligibility_rows=result['eligibility']
    counts={x['venue_id']:x['scenario_selected_count'] for x in result['venue_aggregates']}
    summary.append({'scenario_id':req['scenario_id'],'buffet_discount_krw_per_person':amount,'geumryong_selected':counts.get('GEUMRYONG',0),'buffet_selected':counts.get('THE_BUFFET',0),'run_status':result['experiment']['run_status'],'scenario_input_sha256':result['experiment']['scenario_input_sha256'],'interpretation':'conditional rule-engine scenario; not demand forecast'})
    for c in result['customers']:
        customer_rows.append({'scenario_id':req['scenario_id'],'buffet_discount_krw_per_person':amount,**c})
    for arm_name in ('baseline','scenario'):
        for person in result[arm_name]['customers']:
            for candidate in person.get('candidates',[]):
                candidate_rows.append({'scenario_id':req['scenario_id'],'arm':arm_name,'persona_id':person['persona_id'],**candidate,'terms_json':json.dumps(candidate.get('terms',[]),ensure_ascii=False,separators=(',',':'))})
def write_rows(path,rows):
    if not rows:return
    flat=[]
    for row in rows:
        flat.append({k:(json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(dict,list)) else v) for k,v in row.items()})
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
write_rows(OUT/'four_discount_summary.csv',summary)
write_rows(OUT/'customer_comparison.csv',customer_rows)
write_rows(OUT/'candidate_scores.csv',candidate_rows)
write_rows(OUT/'eligibility.csv',eligibility_rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
