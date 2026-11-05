"""World/memory regression only. Synthetic decisions are not LLM quality PASS."""
import copy
import os
from unittest.mock import patch
import pytest
from test_agent_world_choices import A, C, actor, plan
from operator_choice.autonomy_v1 import agent_experience as X


def test_santa_child_breakfast_context_uses_selected_package_not_generic_two_adults():
    from operator_choice.autonomy_v1 import event_scenarios as E
    a,_=actor(490,False);a.N=3
    a.vs['party_composition']={'adult_count':2,'children':[{'age_months':84,'school_stage':'elementary'}]}
    a.sc['scenario_snapshot']=E.snapshot(dict(event_card_id='SANTA_KIDS_VILLAGE_2026',
        entitlements={a.pid:dict(selected_package=True,included_people=3,package_id='SANTA_PKG_2026_GRAND_HYVAA_JOULUA')}),'2026-12-18','stay_1')
    a.sc['date']='2026-12-19'
    b=X.visit(a)['breakfast']
    assert b['covered_adults']==2 and b['covered_children']==1 and b['whole_party_covered']
    assert b['applicable_today'] and b['venue']=='THE_BUFFET'
    a.sc['date']='2026-12-20'
    assert X.visit(a)['breakfast']['applicable_today'] is False


def test_meal_history_retains_order_and_assumptions_without_inventing_intake():
    a,w=actor(980,False);a.food=[]
    with C.install(a.sc['date']):
        choices,menus,_,world=A.action_space(a,w,a.t)
        selected=choices['meal:PIZZA_HILL'];p=plan(selected)
        p['meal_assessment'].update(modeled_diners=2,kind='LIGHT_MEAL',expected_satiety='COMFORTABLE')
        action=A.validate_plan(a,p,choices,menus,[])
        rec=dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))])
        A._execute(a,w,a.t,action,p,rec,world)
    h=X.history(a,a.t+240)[0]
    assert [(x['sku_id'],x['quantity']) for x in h['order']]==[(x['sku_id'],x['quantity']) for x in p['items']]
    assert h['order_total_krw']==p['order_total_krw']
    assert h['actual_intake']==h['actual_diners']==h['leftovers']=='NOT_OBSERVED'
    assert h['assessment']['kind']=='LIGHT_MEAL' and h['assessment']['modeled_diners']==2
    assert h['minutes_since_end']==240
    A.advance_needs(a,a.t+240)
    assert a.hunger_e==0  # no timer-forced new eating; model sees elapsed history
    a.visit_history={'autonomous_memory':copy.deepcopy(a._autonomous_memory)}
    before=copy.deepcopy(a._autonomous_memory);X.history(a,a.t+1)[0]['order'].clear()
    assert a._autonomous_memory==before


def test_full_and_light_meals_are_different_context_not_different_price_scores():
    a,w=actor();a._autonomous_memory={'meal_experiences':[
        dict(date=a.sc['date'],end=600,assessment={'kind':'FULL_MEAL'},order=[{'sku_id':'COURSE'}]),
        dict(date=a.sc['date'],end=620,assessment={'kind':'SNACK'},order=[{'sku_id':'SNACK'}])]}
    h=X.history(a,700)
    assert [x['minutes_since_end'] for x in h]==[100,80]
    assert [x['assessment']['kind'] for x in h]==['FULL_MEAL','SNACK']
    assert all('preference_score' not in x for x in h)


def test_reassessment_does_not_invent_a_customer_report_after_waiting():
    a,_=actor();day=a.sc['date']
    a._autonomous_decisions=[
        dict(date=day,minute=600,execution_state='EXECUTED',selected_plan=dict(action_id='wait_reconsider',decision_summary='잠시 대기',current_need_assessment={'state':'UNCERTAIN'})),
        dict(date=day,minute=610,execution_state='PREPARING'),
        dict(date='2000-01-01',minute=605,execution_state='EXECUTED',selected_plan=dict(action_id='OLD'))]
    before=copy.deepcopy(a._autonomous_decisions);c=X.reassessment_context(a,610)
    assert c['minutes_since_previous_decision']==10
    assert [x['action_id'] for x in c['recent_decisions']]==['wait_reconsider']
    assert c['customer_report_channel']=='NOT_PRESENT_IN_THIS_SIMULATION'
    assert c['newly_observed_intake_hunger_or_child_condition'] is False
    assert c['recent_decisions'][0]['need_assessment']['state']=='UNCERTAIN'
    c['recent_decisions'][0]['need_assessment']['state']='HUNGRY'
    assert a._autonomous_decisions==before


def test_same_summary_aliases_share_observation_and_excluded_fact_stays_excluded():
    a,w=actor();a.P=copy.deepcopy(a.P);a.P['hidden']=[];a.lib={}
    a.traits={'evidence_index':{f:dict(gist='가격 때문에 구매하지 않음',posts=['PRIVATE_POST_123']) for f in ['F1','F2','X']},
        'facets':{'value':{'evidence':[dict(fact_id=f,grade='exclude' if f=='X' else 'rep') for f in ['F1','F2','X']]}}}
    got=X.evidence(a,{})
    assert got['citable_fact_ids']==['F1','F2']
    assert len(got['evidence_records'])==1
    assert got['evidence_records'][0]['independent_observation_count'] is None
    assert 'PRIVATE_POST_123' not in str(got) and got['evidence_records'][0]['human_review'].startswith('PENDING')


def test_meal_diners_cannot_exceed_party_and_replan_exhaustion_does_not_rescore():
    a,w=actor();calls=[]
    def invalid(**kw):
        calls.append(copy.deepcopy(kw['context']))
        p=plan(next(x for x in kw['context']['actions'] if x['action_id']=='public_rest'))
        p['action_id']='INVENTED_ACTION'
        return dict(plans=[p],selected_index=0),dict(execution='SYNTHETIC_TEST')
    with C.install(a.sc['date']),patch.dict(os.environ,{'HILLINK_AUTONOMOUS_AGENT':'1'}),patch.object(A.P,'request',invalid):
        assert A.step(a,w,a.t)
    assert a.ended and not a.log
    assert a._autonomous_decisions[-1]['execution_state']=='EXECUTION_HOLD'
    assert len(calls)==2 and calls[1]['previous_rejection']['reason']=='ACTION_NOT_IN_VALIDATED_WORLD'
    with pytest.raises(ValueError,match='DINERS_EXCEED'):
        X.validate_assessment(dict(meal_assessment={'modeled_diners':3}),2,True)


def test_discount_is_a_valid_controlled_intervention_but_fake_base_is_not():
    base=A.H.BY['HC-MENU-091'];assert not A.price_contract_reasons(base)
    for pct in [10,15,20]:
        p=A.H.price(base,{'discount_percent':{base['sku_id']:pct}})
        assert not A.price_contract_reasons(p)
        p['unit_price_krw']+=1
        assert 'OPERATOR_DISCOUNT_BASE_OR_ARITHMETIC_UNVERIFIED' in A.price_contract_reasons(p)
    fake=A.H.price(base,{'price_overrides':{base['sku_id']:1},'discount_percent':{base['sku_id']:20}})
    assert A.price_contract_reasons(fake)


def test_current_visit_does_not_promote_historical_family_or_anniversary():
    a,w=actor();a.C={'kids':True};a.N=4
    v=X.visit(a)
    assert v['party'] is None and v['party_status']=='COMPOSITION_AND_AGES_UNCONFIRMED'
    assert v['contract_party_assumption']['source'].startswith('LEGACY_PARTY_SPLIT')
    assert v['purpose']['status']=='UNCONFIRMED'
    a.vs['breakfast_plan']='room_only';assert X.visit(a)['breakfast']['covered_adults']==0
    a.vs['breakfast_plan']='breakfast_included';assert X.visit(a)['breakfast']['covered_adults']==2
    assert not X.visit(a)['breakfast']['whole_party_covered']


def test_breakfast_nonuse_distinguishes_contract_failure_from_choice():
    assert X.breakfast_outcome('SKIP_BREAKFAST',0,[{'reason':'AGE_UNKNOWN'}]).startswith('CONTRACT_UNAVAILABLE')
    assert X.breakfast_outcome('SKIP_BREAKFAST',1,[]).startswith('VOLUNTARY_NONUSE')
    assert X.breakfast_outcome('BREAKFAST_BUFFET',1,[])=='SIMULATED_BREAKFAST_SELECTED'


def test_evidence_keeps_future_intent_and_actor_separate_from_completed_visit():
    a,w=actor();a.P=copy.deepcopy(a.P);a.P['hidden']=[]
    a.traits={'evidence_index':{f:dict(gist='골프를 이용',posts=['p']) for f in ['F1','F2']},'facets':{}}
    a.lib={'engine':{'facts':{'F1':{'actor':'self','time_scope':'future','action_stage':'intention'},'F2':{'actor':'companion','time_scope':'past','action_stage':'completed'}}}}
    rows=X.evidence(a,{})['evidence_records']
    assert len(rows)==2 and len({x['observation_key'] for x in rows})==2
    assert {x['time_scope'] for x in rows}=={'past','future'}


def test_overnight_elapsed_time_not_replaced_by_unknown_or_new_hunger():
    a,w=actor();a.sc['date']='2026-09-11';a._autonomous_memory={'meal_experiences':[dict(date='2026-09-10',end=1200)]}
    assert X.history(a,480)[0]['minutes_since_end']==720


def test_meal_clock_projection_keeps_elapsed_and_does_not_mutate_memory():
    a,w=actor();a.sc['date']='2026-09-11'
    a._autonomous_memory={'meal_experiences':[dict(date='2026-09-10',start='18:10',end=1150)]}
    original=copy.deepcopy(a._autonomous_memory)
    row=X.history(a,510)[0]
    assert row['start_time']=='18:10' and row['end_time']=='19:10'
    assert row['minutes_since_end']==800 and 'end' not in row
    assert a._autonomous_memory==original


def test_wait_then_meal_clock_context_matches_actual_executor_not_wait_plus_travel():
    a,w=actor();a.food=[]
    with C.install(a.sc['date']):
        choices,menus,_,world=A.action_space(a,w,a.t)
        action=next(v for v in choices.values() if v['kind']=='MEAL' and v.get('wait'))
        original=copy.deepcopy(action)
        projected=A.model_action(a,a.t,action);schedule=projected['schedule']
        assert schedule['travel_minutes']>0 and schedule['wait_minutes']>=0
        assert schedule['travel_minutes']+schedule['wait_minutes']==action['start']-a.t
        assert 'start' not in projected and 'start' not in projected['wait']
        assert action==original
        selected=plan(action)
        executable=A.validate_plan(a,selected,choices,menus,[])
        A._execute(a,w,a.t,executable,selected,dict(attempts=[{'provider':{'execution':'SYNTHETIC_TEST'}}]),world)
        executed=next(x for x in reversed(a.log) if x.get('domain')=='식사')
        assert (executed['t'],executed['e'])==(schedule['start_time'],schedule['end_time'])


def test_breakfast_provides_service_clock_and_records_it_without_changing_offer():
    a,w=actor(490,False);a.log=[]
    offer=dict(id='BREAKFAST_BUFFET',kind='buffet',venue='THE_BUFFET',label='조식',
        duration_min=60,in_package=True,window={'start':'08:30','end':'10:00'})
    original=copy.deepcopy(offer)
    def answer(**kw):
        row=kw['context']['actions'][0]
        assert row['schedule']['start_time']=='08:30' and row['schedule']['end_time']=='09:30'
        assert row['schedule']['travel_minutes']+row['schedule']['wait_minutes']==20
        return dict(plans=[plan(row)],selected_index=0),dict(execution='SYNTHETIC_TEST')
    with patch.object(A.AD.EN,'feasible',return_value=[]),patch.object(A.P,'request',answer):
        result=A.breakfast_choice(a,w,a.t,{'offers':[offer]},lambda:None)
    assert result['chosen']['id']=='BREAKFAST_BUFFET' and offer==original
    saved=a._autonomous_decisions[-1]['input_context']['actions'][0]
    assert saved['schedule']['start_time']=='08:30'


def test_booking_clock_does_not_change_original_schedule_contract():
    a,w=actor();a.sc['scenario_snapshot']=dict(scenario_id='SANTA_TEST',venue_id='FOREST_PARK',
        assumptions={'booked_sessions':{a.pid:dict(date=a.sc['date'],start='16:40')}})
    projected=A.model_booking(a)
    assert projected['start_time']=='16:40' and 'start' not in projected
    assert A.booked_event(a)['start']==1000


def test_skip_lunch_does_not_visit_restaurant_or_record_consumption():
    a,w=actor(710);a.food=[];a.meals['lunch']=False
    with C.install(a.sc['date']):
        actions,menus,_,world=A.action_space(a,w,a.t)
        selected=actions['lunch_skip'];p=plan(selected)
        checked=A.validate_plan(a,p,actions,menus,[])
        rec=dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))])
        A._execute(a,w,a.t,checked,p,rec,world)
    assert a.loc not in A.HR.FOOD
    assert all(x['domain']!='식사' for x in a.log)
    assert A.meal_state(a)['meals']['lunch'] is False
    assert A.meal_state(a)['meal_decision_resolved']['lunch'] is True
    assert not getattr(a,'_autonomous_memory',{}).get('meal_experiences')


def test_run_context_is_actual_allowlisted_input_not_current_profile():
    ctx=dict(personal={'secret_raw':'PRIVATE','evidence_records':[dict(fact_ids=['F1'],summary='관련 요약',url='PRIVATE'),dict(fact_ids=['F2'],summary='인용하지 않음')]},visit={'date':'2026-09-11'},state={'time':'12:00'},menus={},actions=[])
    result=X.decision_context(ctx,[dict(supporting_fact_ids=['F1'])])
    assert result['facts']==[dict(fact_ids=['F1'],summary='관련 요약')]
    ctx['personal']['evidence_records'][0]['summary']='CHANGED'
    assert result['facts'][0]['summary']=='관련 요약' and 'PRIVATE' not in str(result)


def test_executed_facility_and_sleep_survive_overnight_without_satisfaction_claim():
    a,w=actor(1200,False)
    a.log=[dict(t='19:00',e='19:40',act='footbath',label='족욕',loc='SKYARD',domain='시설',source='llm_plan_autonomous'),
           dict(t='23:00',e='23:30',act='sleep',label='취침',loc='GRAND_ROOM',domain='휴식',source='obligation')]
    a._autonomous_memory={'pending_intentions':['내일 다른 시설을 검토']}
    X.remember_activities(a,1410)
    original=copy.deepcopy(a._autonomous_memory)
    tomorrow,_=actor(480,False);tomorrow.sc['date']='2026-09-11';tomorrow.log=[]
    tomorrow.visit_history={'autonomous_memory':original}
    rows=X.activity_history(tomorrow,480)
    assert [x['action'] for x in rows]==['footbath','sleep']
    assert rows[0]['minutes_since_end']==740
    assert all(x['satisfaction']=='NOT_OBSERVED' for x in rows)
    assert len(rows)==2 and '내일 다른 시설' not in str(rows)
    rows[0]['label']='changed'
    assert original==a._autonomous_memory
    assert tomorrow._autonomous_memory['activity_experiences'][0]['label']=='족욕'


def test_merged_rest_replaces_episode_and_invalid_or_future_proposal_is_not_memory():
    a,w=actor(600,False)
    a.log=[dict(t='09:00',e='09:30',act='idle',label='로비 휴식',loc='GRAND_LOBBY')]
    assert len(X.activity_history(a,600))==1
    a.log[0]['e']='10:00'
    a.log.append(dict(t='10:00',e='11:00',act='footbath',loc='SKYARD'))
    a.log.append(dict(t='09:00',e='09:30',act='not_executed',internal={'autonomous_decision':{'execution_state':'VALIDATED'}}))
    rows=X.activity_history(a,600)
    assert len(rows)==1 and rows[0]['end_time']=='10:00'
    assert len(X.activity_history(a,600))==1


def test_memory_cannot_be_reused_for_another_customer():
    a,w=actor();a.visit_history={'autonomous_memory':{'customer_id':'OTHER_CUSTOMER','activity_experiences':[]}}
    with pytest.raises(ValueError,match='MEMORY_CUSTOMER_MISMATCH'):
        X.remember_activities(a,a.t)


def test_breakfast_model_and_evidence_receive_completed_previous_day_activity():
    a,w=actor(490,False);a.log=[]
    a.visit_history={'autonomous_memory':{'customer_id':a.pid,'activity_experiences':[
        dict(date='2026-09-09',start=1150,end=1200,action='footbath',label='족욕',location='SKYARD',satisfaction='NOT_OBSERVED')]}}
    offers={'offers':[dict(id='SKIP_BREAKFAST',label='skip',duration_min=20)]}
    def answer(**kw):
        assert kw['context']['activity_experiences'][0]['action']=='footbath'
        assert kw['context']['activity_experiences'][0]['minutes_since_end']==730
        return dict(plans=[plan(kw['context']['actions'][0])],selected_index=0),dict(execution='SYNTHETIC_TEST')
    with patch.object(A.AD.EN,'feasible',return_value=[]),patch.object(A.P,'request',answer):
        A.breakfast_choice(a,w,a.t,offers,lambda:None)
    recorded=a._autonomous_decisions[-1]['input_context']['activity_experiences']
    assert len(recorded)==1 and recorded[0]['action']=='footbath'
    a._autonomous_memory['activity_experiences'].clear()
    assert recorded[0]['action']=='footbath'


def test_validated_scene_snapshot_joins_only_the_matching_executed_decision():
    a,w=actor(1300,False)
    d=dict(input_sha256='abc',customer_id=a.pid,date=a.sc['date'],minute=1245,
        policy=A.POLICY,contract_sha256='sku',execution_state='VALIDATED',
        selected_plan={'action_id':'night_footbath','items':[]})
    a.log=[dict(t='20:48',e='21:28',act='night_footbath',label='야간 족욕',loc='SKYARD',
                internal={'autonomous_decision':copy.deepcopy(d)})]
    a._autonomous_decisions=[dict(d,execution_state='EXECUTED')]
    rows=X.activity_history(a,1300)
    assert len(rows)==1 and rows[0]['selected_action_id']=='night_footbath'
    assert rows[0]['start_time']=='20:48' and rows[0]['end_time']=='21:28'
    assert 'start' not in rows[0] and 'end' not in rows[0]
    for key in ('customer_id','date','minute','policy','input_sha256','contract_sha256','selected_plan'):
        a._autonomous_decisions=[dict(d,execution_state='EXECUTED',**{key:'OTHER'})]
        assert X.activity_history(a,1300)==[]
    a._autonomous_decisions=[dict(d,execution_state='EXECUTED')]*2
    assert X.activity_history(a,1300)==[]
