import copy
from test_agent_world_choices import A, C, actor, plan
from operator_choice.autonomy_v1 import agent_experience as X


def test_legacy_portion_and_llm_meal_intent_join_without_rewriting_execution():
    a,w=actor(980,False);a.food=[]
    with C.install(a.sc['date']):
        actions,menus,_,world=A.action_space(a,w,a.t)
        chosen=actions['meal:PIZZA_HILL'];p=plan(chosen)
        selected=A.validate_plan(a,p,actions,menus,[])
        A._execute(a,w,a.t,selected,p,dict(attempts=[dict(provider=dict(execution='SYNTHETIC_TEST'))]),world)
    before=copy.deepcopy(a.meal_log)
    state=X.meal_history_context(a.meal_log)[0];experience=X.history(a,a.t)[0]
    assert 'size' not in state and 'meal_fraction' not in state
    assert state['legacy_portion_estimate']['size']==before[0]['size']
    assert state['session_id']==experience['session_id']
    assert experience['assessment']['kind']=='FULL_MEAL'
    assert experience['actual_intake']=='NOT_OBSERVED' and a.meal_log==before


def test_departure_arrival_and_service_start_are_separate_before_choice():
    a,w=actor(490,False)
    row=dict(action_id='breakfast',location='THE_BUFFET',start=510,duration=60)
    s=A.model_action(a,490,row)['schedule']
    assert s['departure_time']=='08:10'
    assert s['arrival_time']==X.clock(490+A.AD.SP.travel_min(a.loc,'THE_BUFFET'))
    assert s['start_time']=='08:30' and s['final_leg_departure_time']=='08:10'
    a,w=actor()
    with C.install(a.sc['date']):
        actions,_,_,_=A.action_space(a,w,a.t)
    row=next(v for v in actions.values() if v.get('wait'))
    s=A.model_action(a,a.t,row)['schedule']
    assert row['wait']['location']==a.loc
    assert s['departure_time']==X.clock(row['wait']['end'])
    assert s['final_leg_departure_time']==X.clock(row['wait']['end'])
    assert s['arrival_time']==s['start_time']


def test_skipped_meal_stays_nonconsumption_in_model_context():
    original=[dict(size='skip',slot='lunch',t=710,end=720)]
    projected=X.meal_history_context(original)[0]
    assert projected['meal_execution']=='SKIPPED_NOT_INTAKE'
    assert original[0]['size']=='skip' and projected['start_time']=='11:50'
