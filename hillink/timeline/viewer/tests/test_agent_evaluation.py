from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_evaluation import audit


def test_independent_audit_finds_amount_mismatch_without_repairing_ledger():
    scene=dict(visit_date='2026-09-10',t0=1080,t1=1140,loc='SKYARD',label='시설',
        basis=dict(charge=dict(krw=19000),autonomous_decision=dict(selected_plan=dict(order_total_krw=0,items=[]))))
    f=dict(plans={'X':dict(scenes=[scene])},ledger=dict(checks={k:True for k in
        ('receipts_equal_L4_L3_L2_L1','day_totals_equal_visit_total','room_nights_equal_duration','date_rows_unique')}))
    result=audit(f,'X')
    assert result['findings'][0]['code']=='PLANNED_EXECUTED_AMOUNT_MISMATCH'
    assert scene['basis']['charge']['krw']==19000
    assert result['behavior_quality_status']=='REQUIRES_SEPARATE_SEMANTIC_AND_HUMAN_REVIEW'


def test_missing_ledger_is_not_a_pass():
    result=audit(dict(plans={'X':dict(scenes=[])}),'X')
    assert result['contract_status']=='ISSUES_FOUND'
    assert len(result['findings'])==4


def test_duplicate_planned_sku_rows_are_summed_independently():
    scene=dict(visit_date='2026-09-10',t0=1080,t1=1140,loc='PIZZA_HILL',label='식사',
        basis=dict(charge=dict(krw=200,sku_contract=dict(components=[dict(sku_id='P',billing_quantity=2)])),
            autonomous_decision=dict(selected_plan=dict(order_total_krw=200,
                items=[dict(sku_id='P',quantity=1),dict(sku_id='P',quantity=1)]))))
    flow=dict(plans={'X':dict(scenes=[scene])},ledger=dict(checks={k:True for k in
        ('receipts_equal_L4_L3_L2_L1','day_totals_equal_visit_total','room_nights_equal_duration','date_rows_unique')}))
    assert audit(flow,'X')['findings']==[]
    scene['basis']['charge']['sku_contract']['components'][0]['billing_quantity']=1
    assert audit(flow,'X')['findings'][0]['code']=='PLANNED_EXECUTED_SKU_QUANTITY_MISMATCH'


def test_audit_catches_departure_after_recorded_day_end_without_repair():
    scene=dict(visit_date='2026-11-05',t0=836,t1=851,loc='HOTEL_GATE',label='귀가',basis={})
    d=dict(date='2026-11-05',minute=738,execution_state='EXECUTED',input_context={'state':{'day_end':'14:00'}})
    result=audit(dict(plans={'X':dict(scenes=[scene],autonomous_decisions=[d])}), 'X')
    assert any(x['code']=='DAY_END_EXCEEDED' for x in result['findings'])
    assert scene['t1']==851


def test_booked_event_nonattendance_is_not_a_quality_pass_or_dislike():
    d=dict(date='2026-12-18',minute=885,execution_state='EXECUTED',input_context={'visit':{'scenario':{
        'event_card_id':'SANTA_KIDS_VILLAGE_2026','assumptions':{'booked_sessions':{'X':{'date':'2026-12-18','start':'16:40'}}}}}})
    f=dict(plans={'X':dict(scenes=[],autonomous_decisions=[d])})
    assert any(x['code']=='OPERATOR_BOOKED_EVENT_NOT_REACHED' for x in audit(f,'X')['findings'])
    f['plans']['X']['scenes']=[dict(visit_date='2026-12-18',t0=1000,t1=1070,act='CARD_SANTA_KIDS_VILLAGE_2026',loc='FOREST_PARK')]
    assert not any(x['code']=='OPERATOR_BOOKED_EVENT_NOT_REACHED' for x in audit(f,'X')['findings'])
