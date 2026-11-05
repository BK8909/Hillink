"""Bottom-up operational view of one executed visit; never a price model."""
from collections import defaultdict

NON_ACTIVITIES = {'sleep','wake','arrive','leave','checkin','checkout','unpack','pack','idle','wait'}


def build(flow, ledger):
    groups = {}
    def bucket(day, iso, hour):
        key = (day, iso, hour)
        return groups.setdefault(key, dict(day=day, date=iso, hour=hour, actions=[], transactions=[]))
    for pid, plan in flow['plans'].items():
        for index, scene in enumerate(plan['scenes']):
            if scene['act'] in NON_ACTIVITIES or scene['t1']<=scene['t0']:continue
            b=bucket(scene['visit_day'],scene['visit_date'],scene['t0']//60)
            ref={'customer_id':pid,'visit_scene_index':index,'action_id':scene['act'],'venue_id':scene['loc'],
                 'start_minute':scene['t0'],'end_minute':scene['t1'],
                 'decision_packet_ids':(scene['basis'].get('m4') or {}).get('decision_packet_ids',[])}
            b['actions'].append(ref)
    all_rows=[]
    for pid,receipt in ledger['receipts'].items():
        for row in receipt['rows']:
            # Room-night/untimed rows have their own bucket; never pretend a
            # charge occurred at midnight when the source supplies no time.
            hour=None if row['act']=='room_night' or row.get('t0') is None else row['t0']//60
            b=bucket(row['visit_day'],row['visit_date'],hour)
            ref={k:row.get(k) for k in ('row_id','customer_id','venue_id','product_id','product','paid_krw','assumption_addition_krw','amount_status','act','scene_index','visit_day','visit_date')}
            ref['unknown_price']=row['status']=='금액 미확인'
            b['transactions'].append(ref);all_rows.append(row)
    for b in groups.values():
        ids=sorted({x['customer_id'] for x in b['actions']+b['transactions']})
        b.update(customer_ids=ids,team_count=len(ids),action_count=len(b['actions']),
            paid_krw=sum(x['paid_krw'] for x in b['transactions']),
            room_and_other_assumption_krw=sum(x['assumption_addition_krw'] for x in b['transactions']),
            unknown_count=sum(x['unknown_price'] for x in b['transactions']))
        # Distinct venue usage is preserved even when paid totals are equal.
        venues=defaultdict(list)
        for a in b['actions']:venues[a['venue_id']].append(a)
        b['venue_usage']=[{'venue_id':v,'action_count':len(rows),'customer_ids':sorted({a['customer_id'] for a in rows})} for v,rows in sorted(venues.items())]
    buckets=sorted(groups.values(),key=lambda b:(b['day'],-1 if b['hour'] is None else b['hour']))
    paid=sum(b['paid_krw'] for b in buckets);assumed=sum(b['room_and_other_assumption_krw'] for b in buckets)
    row_ids=[r['row_id'] for r in all_rows]
    if len(row_ids)!=len(set(row_ids)) or paid!=ledger['totals']['paid_krw'] or assumed!=ledger['totals']['assumption_addition_krw']:
        raise ValueError('VISIT_OPERATIONS_LEDGER_MISMATCH')
    return dict(version='visit-operations-v1',visit_id=flow['visit_id'],ledger_run_id=ledger['run_id'],
        basis='ACTUAL_EXECUTED_SCENES_AND_SAME_L5_ROWS; HOUR_IS_ACTIVITY_OR_TRANSACTION_START',
        buckets=buckets,checks=dict(unique_rows=True,paid_equals_L1=True,assumptions_equal_L1=True),
        row_count=len(row_ids),paid_krw=paid,assumption_addition_krw=assumed)
