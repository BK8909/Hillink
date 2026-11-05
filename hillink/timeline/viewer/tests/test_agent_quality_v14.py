"""Contract regressions, not model or human semantic approval."""
import copy
from test_agent_world_choices import A, C, actor, plan


def test_late_night_has_executable_day_end_with_memory_and_no_extra_wait():
    a,w=actor(1339,False)
    with C.install(a.sc['date']):
        actions,menus,_,world=A.action_space(a,w,a.t)
        assert {'wait_reconsider','end_day_in_room'}<=actions.keys()
        choice=plan(actions['end_day_in_room'])
        selected=A.validate_plan(a,choice,actions,menus,[])
        record=dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))])
        A._execute(a,w,a.t,selected,choice,record,world)
    assert a.ended and not a.left and a.t==a.end
    assert a.log[-1]['act']=='sleep' and a.log[-1]['loc']==a.room
    assert not any(x['act']=='wait' for x in a.log)
    assert record['execution_state']=='EXECUTED'


def test_day_end_cannot_skip_booking_or_checkout_or_use_unchecked_room():
    a,w=actor(1000,False)
    a.sc['scenario_snapshot']=dict(event_card_id='TEST',scenario_id='TEST',venue_id='FOREST_PARK',
        assumptions=dict(booked_sessions={a.pid:dict(date=a.sc['date'],start='18:00')}))
    with C.install(a.sc['date']):
        actions,_,excluded,_=A.action_space(a,w,a.t)
    assert 'end_day_in_room' not in actions
    assert any('BOOKED_EVENT_NOT_COMPLETED_OR_CANCELLED' in x['reasons'] for x in excluded)
    for checked_in,checked_out,phase in [(False,False,'checkin'),(True,False,'checkout'),(True,True,'checkout')]:
        a.checked_in=checked_in;a.checked_out=checked_out;a.phase=phase
        assert 'end_day_in_room' not in A.control_actions(a,w,a.t,[])


def test_breakfast_access_is_not_a_child_dish_and_source_contract_is_unchanged():
    contract=dict(components=[dict(sku_id='INFANT',label='36개월 미만 유아',billing_quantity=1,
        billing_unit='person',tags=['buffet'],role='MAIN',included_components=None)])
    before=copy.deepcopy(contract)
    rows=A.breakfast_item_contracts(contract)
    assert rows[0]['semantics']=='PERSON_ACCESS_ENTITLEMENT'
    assert rows[0]['label']=='36개월 미만 유아' and rows[0]['quantity']==1
    assert rows[0]['included_components'] is None
    rows[0]['tags'].clear()
    assert contract==before


def test_clock_meal_slot_is_not_a_customer_intent_or_later_meal_ban():
    a,w=actor(1090,False);a.food=[];a.meals['dinner']=True
    a.meal_log=[dict(t=925,end=985,slot='dinner',size='full')]
    with C.install(a.sc['date']):
        actions,_,_,_=A.action_space(a,w,a.t)
    assert any(x['kind']=='MEAL' for x in actions.values())
    assert 'NOT_CUSTOMER_MEAL_INTENT' in A.meal_state(a)['meal_period_basis']
