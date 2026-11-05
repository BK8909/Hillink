"""Contract and budget tests; synthetic responses are not model-quality evidence."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import os
import subprocess
from unittest.mock import patch

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1 import autonomous_agent as A, agent_provider as P


def test_budget_is_cumulative_and_crash_reservations_are_not_free(tmp_path):
    path=tmp_path/'usage.json'
    b=P.Budget(path,.02,3)
    r=b.reserve(.008,{'purpose':'TEST'})
    restarted=P.Budget(path,20,400)
    assert restarted.summary()['max_usd']==.02
    assert restarted.summary()['unresolved']==1
    r2=restarted.reserve(.008,{'purpose':'TEST'})
    with pytest.raises(P.ProviderUnavailable,match='USD_LIMIT'):b.reserve(.008,{})
    b.settle(r2,cost=.001,status='COMPLETED')
    assert b.summary()['cost_upper_usd']==pytest.approx(.009)
    b.settle(r,status='ERROR')
    assert b.summary()['cost_upper_usd']==pytest.approx(.009)
    with pytest.raises(ValueError,match='ALREADY'):b.settle(r,cost=0,status='COMPLETED')


def test_failed_requests_count_and_invalid_budget_rejected(tmp_path):
    b=P.Budget(tmp_path/'usage',20,1)
    rid=b.reserve(.001,{})
    b.settle(rid,status='ERROR')
    with pytest.raises(P.ProviderUnavailable,match='CALL_LIMIT'):b.reserve(.001,{})
    for amount in (float('nan'),float('inf'),0,21):
        with pytest.raises(ValueError):P.Budget(tmp_path/'bad',amount,2)


def fixture():
    a=NS(N=2,C={'kids':False},sc={'date':'2026-09-10','catalog_policy':A.H.POLICY},
        hunger_e=1,meal_log=[],B='GRAND',stay=True,checked_in=True,checked_out=False,
        club=False,pid='TEST',vs={'nights':1},phase='checkin',visit_history={},room='GRAND_ROOM',end=1380)
    products=[A.H.price(A.H.BY[k],{}) for k in ('HC-MENU-091','HC-MENU-096','HC-MENU-084')]
    key='meal:PIZZA_HILL'
    actions={key:dict(execution='MEAL',venue='PIZZA_HILL',location='PIZZA_HILL',period='dinner',start=1080,duration=90)}
    plan=dict(action_id=key,items=[dict(sku_id='HC-MENU-091',quantity=1),dict(sku_id='HC-MENU-096',quantity=1)],
        order_total_krw=122000,sharing_plan='2인 공유 가정',meal_assessment=dict(kind='FULL_MEAL',modeled_diners=2,intake_assumption='모델 가정',quantity_reason='계약 검증용',expected_satiety='UNCERTAIN',uncertainties=[]),supporting_fact_ids=['F1'],counterevidence_fact_ids=[])
    return a,actions,{key:products},plan


def test_llm_order_is_exactly_validated_before_charge_and_inputs_unchanged():
    a,actions,menus,plan=fixture();before=copy.deepcopy(a.sc)
    got=A.validate_plan(a,plan,actions,menus,['F1'])['contract']
    assert a.sc==before
    assert got['unit_price_krw']==122000
    assert [p['billing_quantity'] for p in got['components']]==[1,1]
    assert A.H.charge(got)['krw']==122000
    assert got['meal_basket']['session_rule']=='ONE_SELECTED_BASKET_ONE_MEAL_SESSION'


@pytest.mark.parametrize('change,reason',[
    ({'supporting_fact_ids':['OTHER_CUSTOMER']},'FACT_NOT'),
    ({'order_total_krw':1},'TOTAL_MISMATCH'),
    ({'items':[{'sku_id':'INVENTED','quantity':1}]},'SKU_NOT'),
    ({'items':[{'sku_id':'HC-MENU-091','quantity':True}]},'INVALID_QUANTITY'),
    ({'items':[{'sku_id':'HC-MENU-091','quantity':1}]*2},'DUPLICATE'),
    ({'action_id':'CLOSED_VENUE'},'ACTION_NOT')])
def test_rejects_fabricated_fact_price_sku_and_quantity(change,reason):
    a,actions,menus,plan=fixture()
    with pytest.raises(ValueError,match=reason):A.validate_plan(a,dict(plan,**change),actions,menus,['F1'])


def test_couple_set_keeps_included_drinks_and_price_without_additions():
    a,actions,menus,plan=fixture()
    plan.update(items=[dict(sku_id='HC-MENU-084',quantity=1)],order_total_krw=184000)
    c=A.validate_plan(a,plan,actions,menus,['F1'])['contract']
    assert len(c['components'])==1
    assert c['components'][0]['included_components']['drinks']==2
    assert A.H.charge(c)['krw']==184000


def test_post_checkout_room_and_overlapping_checkout_are_rejected():
    a,actions,menus,plan=fixture()
    a.checked_out=True
    actions['ROOM_REST']=dict(execution='ENGINE',location='GRAND_ROOM',start=720,duration=60)
    with pytest.raises(ValueError,match='CHECKED_IN_ROOM'):
        A.validate_plan(a,dict(plan,action_id='ROOM_REST',items=[],order_total_krw=0),actions,menus,['F1'])
    a.checked_out=False;a.phase='checkout';a.room='GRAND_ROOM'
    assert A.schedule_reasons(a,dict(location='PIZZA_HILL',start=660,duration=120))==['CHECKOUT_PREPARATION_AND_TRAVEL_OVERLAP']


def test_facility_quote_is_a_purchase_not_a_zero_cost_activity():
    a,actions,menus,plan=fixture()
    actions['paid']=dict(execution='ENGINE',location='SKYARD',start=1080,duration=60,
        items=[dict(sku_id='REAL_FACILITY_QUOTE',quantity=2)],order_total_krw=19000)
    with pytest.raises(ValueError,match='ACTIVITY_FIXED_ORDER_MISMATCH'):
        A.validate_plan(a,dict(plan,action_id='paid',items=[],order_total_krw=0,meal_assessment=None),actions,menus,['F1'])
    selected=dict(plan,action_id='paid',items=actions['paid']['items'],order_total_krw=19000,meal_assessment=None)
    assert A.validate_plan(a,selected,actions,menus,['F1'])['order_total_krw']==19000


def test_synthetic_prechoice_visit_preserves_order_ledger_and_marks_origin(tmp_path):
    import visit_run as V
    import ledger_service as L
    script=tmp_path/'fixture.py'
    script.write_text('''import sys
sys.path.insert(0,sys.argv[1])
import flow_run
from operator_choice.autonomy_v1 import autonomous_agent as A
def answer(**kw):
 c=kw['context']; actions=c['actions']
 selected=next((x for x in actions if x['kind']=='MEAL'),actions[0])
 order=selected.get('existing_orders',[dict(items=selected.get('items',[]),total_krw=selected.get('order_total_krw',0))])[0]
 plan=dict(action_id=selected['action_id'],items=order.get('items',[]),order_total_krw=order.get('total_krw',0),decision_summary='합성 계약 시험',supporting_fact_ids=[],counterevidence_fact_ids=[],assumptions=['TEST'],meal_assessment=(dict(kind='FULL_MEAL',modeled_diners=1,intake_assumption='합성',quantity_reason='검증',expected_satiety='UNCERTAIN',uncertainties=[]) if selected['kind'] in ('MEAL','BREAKFAST') and selected['action_id']!='SKIP_BREAKFAST' else None),sharing_plan='합성 검증',schedule_impact='',why_not_other_plans='',pending_intentions=['다음 날 상황 재검토'])
 return dict(plans=[plan],selected_index=0),dict(execution='SYNTHETIC_TEST',input_sha256='fixture')
A.P.request=answer
flow_run.main()
''')
    with patch.dict(os.environ,dict(HILLINK_AUTONOMOUS_AGENT='1',HILLINK_NATIVE_HYBRID='1',HILLINK_V12Z_COMMON='1',
        HILLINK_HYBRID='replay',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_ISOLATED_CUSTOMERS='0')):
        request=dict(personas=['A02'],duration='stay_1',event_mode='none',seed=17,start_date='2026-09-10',
            behavior_engine='m4_c01',catalog_policy=A.H.POLICY,hybrid_policy=A.POLICY)
        with patch.object(V,'FLOW',[sys.executable,str(script),str(Path(__file__).resolve().parents[1])]):
            flow=V.run_visit(request)
        assert 'error' not in flow,flow
        ledger=L.register_visit(flow,request)
        assert ledger['checks']['receipts_equal_L4_L3_L2_L1']
        scenes=flow['plans']['A02']['scenes']
        selected=[s for s in scenes if s['source']=='llm_plan_autonomous']
        assert selected
        assert all(s['basis']['autonomous_decision']['selection_owner']=='LLM' for s in selected)
        assert all(s['basis']['autonomous_decision']['attempts'][-1]['provider']['execution']=='SYNTHETIC_TEST' for s in selected)
        assert any(s['meal'] in ('lunch','dinner') for s in selected)
        assert any(s['basis']['autonomous_decision'].get('phase')=='breakfast' for s in selected)
        assert all(s['basis']['engine']=='LLM_INTENT_WITH_M4_CONTRACT_VALIDATION' for s in selected)
        assert flow['plans']['A02']['trace']['llm_calls']==0  # synthetic is not a live API call
        assert len(flow['plans']['A02']['autonomous_decisions'])==sum(len(d['flow']['plans']['A02']['autonomous_decisions']) for d in flow['visit_days'])
        first,second=[d['flow']['plans']['A02'] for d in flow['visit_days']]
        history=second['autonomous_decisions'][0]['input_context']['activity_experiences']
        assert any(x['date']=='2026-09-10' for x in history)
        assert any(x['action']=='sleep' for x in history)  # captured after the last day-1 LLM call
        assert first['autonomous_memory']['customer_id']==second['autonomous_memory']['customer_id']=='A02'
        assert all(x['satisfaction']=='NOT_OBSERVED' for x in history)
