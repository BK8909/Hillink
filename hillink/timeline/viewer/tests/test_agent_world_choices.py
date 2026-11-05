"""World feasibility/continuity regressions; not evidence of LLM behavior quality."""
import copy
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1 import autonomous_agent as A, candidate_services as C


def actor(minute=653, checkout=True):
    sc=A.AD.scenario(date='2026-09-10',event=False,seed=0)
    sc.update(catalog_policy=A.H.POLICY,hybrid_policy=A.POLICY)
    a=A.AD.Agent('blog41',*A.AD.load_inputs(),sc)
    a.B='GRAND';a.stay=True;a.phase='checkout' if checkout else 'checkin';a.N=2
    a.checked_in=True;a.checked_out=checkout;a.room=None if checkout else 'GRAND_ROOM'
    a.loc='GRAND_LOBBY' if checkout else a.room;a.t=minute;a.end=840 if checkout else 1380
    a.hunger_e=1.;a.fatigue=.983333;a.meals.update(breakfast=True)
    a.food=[(556,'THE_BUFFET')]
    return a,A.AD.World(sc)


def plan(action, **changes):
    order=action.get('existing_orders',[dict(items=action.get('items',[]),total_krw=action.get('order_total_krw',0))])[0]
    return dict(action_id=action['action_id'],items=order['items'],order_total_krw=order['total_krw'],
        supporting_fact_ids=[],counterevidence_fact_ids=[],decision_summary='합성 세계 계약 검사',
        assumptions=['SYNTHETIC_CONTRACT_TEST'],meal_assessment=(dict(kind='FULL_MEAL',modeled_diners=1,intake_assumption='합성 검증 가정',quantity_reason='계약 검사',expected_satiety='UNCERTAIN',uncertainties=['합성 시험']) if action.get('kind') in ('MEAL','BREAKFAST') and action['action_id']!='SKIP_BREAKFAST' else None),sharing_plan='합성 검증용 공유 가정',schedule_impact='',
        why_not_other_plans='',pending_intentions=[],**changes)


def test_checkout_high_need_has_rest_wait_leave_and_upcoming_meals():
    a,w=actor()
    with C.install(a.sc['date']):
        choices,menus,excluded,_=A.action_space(a,w,a.t)
    assert {'public_rest','wait_reconsider','leave_visit'}<=choices.keys()
    assert menus
    assert any(v.get('wait') for v in choices.values() if v['kind']=='MEAL')
    assert not any(v['location'] and v['location'].endswith('_ROOM') for v in choices.values())
    assert 'lounge' not in choices  # public lobby is not a club lounge entitlement
    assert a.fatigue==.983333 and a.hunger_e==1  # generation does not mutate needs


def test_precheckin_alternative_must_leave_time_for_setup_and_booked_session():
    a,w=actor(885,False);a.checked_in=False;a.loc='HOTEL_GATE'
    a.sc['scenario_snapshot']=dict(event_card_id='SANTA_KIDS_VILLAGE_2026',scenario_id='TEST',venue_id='FOREST_PARK',
        assumptions=dict(santa_before_checkin='not_allowed',booked_sessions={a.pid:dict(date=a.sc['date'],start='16:40')}))
    walk=dict(start=901,duration=40,location='AG_GARDEN',execution='PLAN')
    assert 'MODELED_CHECKIN_PREPARATION_CANNOT_REACH_BOOKED_EVENT' in A.schedule_reasons(a,walk)
    waiting=dict(start=893,duration=10,location='GRAND_LOBBY',execution='WAIT')
    assert not A.schedule_reasons(a,waiting)
    a.checked_in=True
    assert not A.schedule_reasons(a,walk)  # no second check-in inserted


def test_infeasible_late_checkin_is_hold_not_a_silent_missed_booking():
    a,w=actor(960,False);a.checked_in=False;a.loc='GRAND_LOBBY';a.done=['arrive']
    a.sc['scenario_snapshot']=dict(event_card_id='SANTA_KIDS_VILLAGE_2026',scenario_id='TEST',venue_id='FOREST_PARK',
        assumptions=dict(santa_before_checkin='not_allowed',booked_sessions={a.pid:dict(date=a.sc['date'],start='16:40')}))
    with patch.dict(os.environ,{'HILLINK_AUTONOMOUS_AGENT':'1'}),patch.object(A.P,'request',side_effect=AssertionError('No payable action can repair this forced setup')):
        assert A.AD.decide(a,w)
    assert a.ended and not a.checked_in
    assert a._autonomous_decisions[-1]['execution_state']=='EXECUTION_HOLD'
    assert a._autonomous_decisions[-1]['choice_scope']=='SCHEDULE_INFEASIBLE_NOT_PREFERENCE'


def test_after_lunch_extreme_fatigue_is_not_forced_to_buy_theatre():
    a,w=actor(754);a.loc='THE_PAVILION';a.fatigue=1.875;a.hunger_e=0
    a.food=[(754,'THE_PAVILION')];a.meals['lunch']=True
    with C.install(a.sc['date']):
        choices,_,excluded,_=A.action_space(a,w,a.t)
    assert {'public_rest','wait_reconsider','leave_visit'}<=choices.keys()
    assert any('RECENT_MEAL' in x['reasons'] for x in excluded)
    assert len(choices)>1


def test_wait_then_lunch_uses_legal_wait_location_and_one_order():
    a,w=actor()
    with C.install(a.sc['date']):
        choices,menus,_,world=A.action_space(a,w,a.t)
        row=next(v for v in choices.values() if v['kind']=='MEAL' and v.get('wait'))
        p=plan(row);selected=A.validate_plan(a,p,choices,menus,[])
        record=dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))],input_sha256='test')
        A._execute(a,w,a.t,selected,p,record,world)
    waits=[x for x in a.log if x['act']=='idle']
    assert waits and waits[0]['loc']=='GRAND_LOBBY'
    assert 'autonomous_decision' not in waits[0]['internal']
    charged=[x for x in a.log if x.get('internal',{}).get('autonomous_decision')]
    assert len(charged)==1 and charged[0]['charge']['krw']==p['order_total_krw']
    assert A.AD.hm(charged[0]['t'])==selected['start']
    assert all(A.AD.hm(x['e'])<=A.AD.hm(y['t']) for x,y in zip(a.log,a.log[1:]))


def test_lobby_closure_is_not_bypassed_and_booked_event_prevents_departure():
    a,w=actor()
    with patch.object(w,'closed_at',return_value={'GRAND_LOBBY':(600,900)}):
        excluded=[];choices=A.control_actions(a,w,a.t,excluded)
    assert 'public_rest' not in choices and 'wait_reconsider' not in choices
    assert any('OPERATOR_CLOSURE_OVERLAP' in e['reasons'] for e in excluded)
    a.sc['scenario_snapshot']=dict(scenario_id='TEST_EVENT',venue_id='FOREST_PARK',
        assumptions=dict(booked_sessions={a.pid:dict(date=a.sc['date'],start='13:00')}))
    assert 'BOOKED_EVENT_NOT_COMPLETED_OR_CANCELLED' in A.schedule_reasons(a,choices['leave_visit'])


def test_room_rest_has_no_minimum_fatigue_but_still_requires_room_rights():
    a,w=actor(1000,False);a.fatigue=0;a.food=[];a.hunger_e=0
    a.log=[dict(act='room_rest',loc=a.room,t='15:00',e='16:40',domain='객실 휴식')]
    a.done=['room_rest'];a.P=copy.deepcopy(a.P);a.P['bars']['rest_need']=0
    original={};assert A.AD.plan_ok(a,'room_rest',a.t,w,original) is None
    physical=copy.copy(a);physical._world_contract_only=True
    assert A.AD.plan_ok(physical,'room_rest',a.t,w,{})==a.room
    physical.checked_out=True
    assert A.AD.plan_ok(physical,'room_rest',a.t,w,{}) is None


def test_invalid_plan_gets_specific_rejection_then_replans_without_scoring():
    a,w=actor();calls=[]
    def answer(**kw):
        calls.append(copy.deepcopy(kw['context']))
        row=next(x for x in kw['context']['actions'] if x['action_id']=='public_rest')
        p=plan(row)
        if len(calls)==1:p['action_id']='INVENTED_LOUNGE'
        return dict(plans=[p],selected_index=0),dict(execution='SYNTHETIC_TEST')
    with C.install(a.sc['date']),patch.dict(os.environ,{'HILLINK_AUTONOMOUS_AGENT':'1'}),patch.object(A.P,'request',answer):
        assert A.step(a,w,a.t)
    d=a._autonomous_decisions[-1]
    assert calls[1]['previous_rejection']['reason']=='ACTION_NOT_IN_VALIDATED_WORLD'
    assert len(d['attempts'])==2 and d['execution_state']=='EXECUTED'
    assert d['price_score_rerank'] is False
    assert d['state_after']['fatigue']<d['state_before']['fatigue']
    assert d['candidate_count']>1 and not a.left


def test_leave_is_selected_and_ends_visit_without_fake_purchase():
    a,w=actor(754)
    excluded=[];row=A.control_actions(a,w,a.t,excluded)['leave_visit'];p=plan(row)
    record=dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))])
    A._execute(a,w,a.t,row,p,record,{})
    assert a.left and a.ended
    assert a.log[-1]['act']=='leave' and a.log[-1]['charge']['krw']==0


def test_early_dinner_contract_records_meal_even_in_legacy_clock_gap():
    a,w=actor(968,False);a.food=[];a.meals.update(breakfast=False)
    with C.install(a.sc['date']):
        choices,menus,_,world=A.action_space(a,w,a.t)
        row=choices['meal:PIZZA_HILL'];p=plan(row)
        selected=A.validate_plan(a,p,choices,menus,[])
        assert 960<=selected['start']<990
        record=dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))])
        A._execute(a,w,a.t,selected,p,record,world)
    assert a.meals['dinner'] and len(a.meal_log)==1
    assert a.meal_log[0]['slot']=='dinner' and a.hunger_e==0
    assert a.log[-1]['meal_slot']=='dinner'
    A.advance_needs(a,a.t+120)
    assert a.hunger_e==0  # elapsed time alone no longer prescribes hunger
    A.advance_needs(a,a.t+120)  # repeated reads do not compound hunger
    assert a.hunger_e==0  # elapsed time alone no longer prescribes hunger


def test_breakfast_satiation_is_separate_from_next_meal_revisit_gates():
    a,w=actor(550,False);a.food=[];a.meals.update(breakfast=False)
    a.add('engine','BREAKFAST_BUFFET','조식','THE_BUFFET',490,60,'식사','world_rule','',[])
    A.settle_meal(a,A.AD.hm(a.log[-1]['t']),'breakfast',1,1)
    assert a.hunger_e==0 and len(a.meal_log)==1
    A.advance_needs(a,a.t+60)
    assert a.hunger_e==0  # V6 re-evaluates needs from meal experience
    assert 'RECENT_MEAL' in A.AD.meal_revisit_reasons(a,a.t+60,'PIZZA_HILL')


def test_numeric_estimates_are_not_validated_agent_products():
    a,w=actor(1000,False);a.food=[]
    with C.install(a.sc['date']):choices,menus,excluded,_=A.action_space(a,w,a.t)
    assert not any(p['sku_id']=='HC-LP-SANDWICH' for rows in menus.values() for p in rows)
    assert not any(i['sku_id']=='HC-GOLF-60' for c in choices.values() for i in c.get('items',[]))
    assert any('ESTIMATED_PRODUCT_PRICE_OR_UNIT_NOT_EXECUTABLE' in x['reasons'] for x in excluded)
    # Registered reference prices retain their provenance; this is not a
    # requirement to fabricate a current confirmed hotel quote.
    assert A.price_contract_reasons(dict(price_status='OFFICIAL_MENU_REFERENCE_VALIDITY_NOT_GUARANTEED'))==[]


def test_unknown_child_breakfast_rate_is_excluded_and_not_personalization():
    a,w=actor(490,False)
    bad=dict(sku_id='BAD',price_status='UNKNOWN_CHILD_AGE_ADULT_RATE_PROXY_NOT_A_VERIFIED_CHILD_FARE',
        unit_price_krw=85000,billing_quantity=1)
    offers={'offers':[dict(id='UNCONFIRMED_FARE',label='unknown',sku_contract=dict(components=[bad],unit_price_krw=85000),duration_min=60),
        dict(id='SKIP_BREAKFAST',label='skip',duration_min=20)]}
    def respond(**kw):
        assert len(kw['context']['actions'])==1
        assert kw['context']['excluded'][0]['reasons']==['CHILD_AGE_AND_PRICE_CONTRACT_REQUIRED']
        return dict(plans=[plan(kw['context']['actions'][0])],selected_index=0),dict(execution='SYNTHETIC_TEST')
    with patch.object(A.AD.EN,'feasible',return_value=[]),patch.object(A.P,'request',respond):
        result=A.breakfast_choice(a,w,a.t,offers,lambda:None)
    assert result['chosen']['id']=='SKIP_BREAKFAST'
    assert a._autonomous_decisions[-1]['choice_scope']=='SINGLE_VALID_ACTION_NOT_PERSONALIZATION'


def test_subsequent_meal_is_a_separate_session_with_explicit_relationship():
    a,w=actor(980,False);a.food=[];a.meal_log=[];a.loc='PIZZA_HILL'
    for start in [980,1230]:
        a.add('engine','TEST_MEAL','meal', 'PIZZA_HILL',start,60,'식사','world_rule','',[])
        A.settle_meal(a,start,'dinner',.75,1)
    assert [r['period_ordinal'] for r in a.meal_log]==[1,2]
    assert len({r['session_id'] for r in a.meal_log})==2
    assert a.meal_log[-1]['meal_relation']=='ADDITIONAL_AFTER_COMPLETED_MEAL'


def test_skip_resolves_schedule_without_claiming_food_consumed():
    a,w=actor(490,False);a.meals['breakfast']=False;a.meal_log=[]
    prior_food=list(a.food)
    a.add('engine','SKIP_BREAKFAST','skip',a.room,a.t,20,'객실 휴식','world_rule','',[])
    state=A.meal_state(a)
    assert state['meal_decision_resolved']['breakfast'] is True
    assert state['meals']['breakfast'] is False
    assert a.meals['breakfast'] is True  # preserve the scheduler, no repeat loop
    assert a.hunger_e==1 and a.food==prior_food


def test_unverified_pool_daypass_and_unit_models_cannot_be_executed():
    statuses=['VISTA_EXTRA_FEE_UNVERIFIED_NOT_GRAND_FAQ',
        'CHILD_FARE_UNVERIFIED_ADULT_REFERENCE_PROXY',
        'KNOWN_AGE_CHILD_MENU_UNAVAILABLE_ADULT_PORTION_MODEL',
        'NON_VISTA_ACCESS_SCENARIO_NOT_OFFICIAL_PAID_PRODUCT',
        'VENUE_CHANNEL_MISMATCH_KEEP_SCENARIO','VENUE_MENU_MISMATCH_KEEP_SCENARIO',
        'COLLECTED_AMOUNT_WITH_MODEL_PER_DAY_UNIT','POSTED_COURT_AMOUNT_WITH_MODEL_60_MINUTE_UNIT']
    for status in statuses:
        assert A.price_contract_reasons(dict(components=[dict(price_status=status,unit_price_krw=20000)]))
    assert A.price_contract_reasons(dict(price_tier='SIMULATION_ASSUMPTION',unit_price_krw=19000))
    a,w=actor(1000,False);a.food=[]
    with C.install(a.sc['date']):choices,_,excluded,_=A.action_space(a,w,a.t)
    assert not any(x.get('contract',{}).get('daypass_scope')=='MODEL_PER_ROOM_DAY_NOT_CONFIRMED_OFFICIAL_REENTRY' for x in choices.values())


def test_historical_spa_fact_is_not_a_current_room_bath_contract():
    a,w=actor(1000,False);a.food=[]
    a.verified_source_context['spa_room']={'value':True,'fact_ids':['HISTORICAL_FACT']}
    with C.install(a.sc['date']):choices,_,excluded,_=A.action_space(a,w,a.t)
    assert 'room_bath' not in choices and 'room_rest' in choices
    assert any(x['action_id']=='room_bath' and 'CURRENT_ROOM_BATH_FACILITY_UNCONFIRMED' in x['reasons'] for x in excluded)


def test_checkout_meal_must_allow_travel_and_full_departure():
    a,w=actor(738,True);a.end=840
    action=dict(start=738,duration=90,location='MOEGI',execution='MEAL')
    assert 'RETURN_TRAVEL_AND_DEPARTURE_EXCEED_VISIT_END' in A.schedule_reasons(a,action)
    action['duration']=60
    assert 'RETURN_TRAVEL_AND_DEPARTURE_EXCEED_VISIT_END' not in A.schedule_reasons(a,action)


def test_precheckin_choice_is_agent_decision_not_scored_activity():
    a,w=actor(885,False);a.checked_in=False;a.phase='checkin';a.done=['arrive'];called=[]
    def select(*args):called.append(args[2]);return True
    with patch.dict(os.environ,{'HILLINK_AUTONOMOUS_AGENT':'1'}),patch.object(A,'step',select),patch.object(A.AD,'plan_choose',side_effect=AssertionError('scored fallback')):
        assert A.AD.decide(a,w)
    assert called==[885]
