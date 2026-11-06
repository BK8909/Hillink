"""Early day end is reviewed against what is left, never clock-banned.

Synthetic agents and plans; nothing here is model-quality evidence.
"""
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger  # noqa: F401  (registers the experiments package path)
from operator_choice.autonomy_v1 import autonomous_agent as A


def agent(**over):
    base=dict(N=3,C={'kids':False},sc={'date':'2026-12-18','catalog_policy':A.H.POLICY},hunger_e=0.0,fatigue=0.6,rest_limit=2.6,
        meal_log=[],meals={'breakfast':False,'lunch':True,'dinner':False},B='VISTA',stay=True,checked_in=True,checked_out=False,
        club=False,pid='TEST',vs={'nights':1},phase='mid',visit_history={},room='VISTA_ROOM',end=1380,loc='VISTA_ROOM')
    base.update(over);return NS(**base)


def actions(meal=True,activity=True):
    out={'end_day_in_room':dict(action_id='end_day_in_room',execution='END_DAY',location='VISTA_ROOM',start=1115,duration=265,items=[],order_total_krw=0),
         'room_rest':dict(action_id='room_rest',execution='ENGINE',location='VISTA_ROOM',start=1115,duration=60,items=[],order_total_krw=0),
         'public_rest':dict(action_id='public_rest',execution='REST',location='VISTA_LOBBY',start=1118,duration=30,items=[],order_total_krw=0)}
    if meal:out['meal:PIZZA_HILL']=dict(action_id='meal:PIZZA_HILL',execution='MEAL',venue='PIZZA_HILL',location='PIZZA_HILL',period='dinner',start=1130,duration=90)
    if activity:out['night_walk']=dict(action_id='night_walk',execution='PLAN',location='AG_GARDEN',start=1120,duration=40,items=[],order_total_krw=0)
    return out


def plan(**over):
    p=dict(action_id='end_day_in_room',items=[],order_total_krw=0,supporting_fact_ids=[],counterevidence_fact_ids=[],
        decision_summary='테스트',sharing_plan='해당 없음',schedule_impact='',why_not_other_plans='',pending_intentions=[],assumptions=[],
        current_need_assessment={'state':'COMFORTABLE','reason':'테스트'},meal_assessment=None)
    p.update(over);return p


def test_day_end_before_dinner_with_open_meals_is_rejected_with_the_open_options_and_scale():
    a=agent();acts=actions()
    with pytest.raises(ValueError) as exc:A.validate_plan(a,plan(),acts,{},[])
    text=str(exc.value)
    assert text.startswith('EARLY_DAY_END_WITHOUT_EVENING_MEAL_REVIEW')
    assert 'meal:PIZZA_HILL' in text and 'room_rest' in text and '0.60' in text and '2.60' in text and '23%' in text
    # Room rest keeps the day open and is never reviewed as a day end.
    assert A.validate_plan(a,plan(action_id='room_rest'),acts,{},[])['action_id']=='room_rest'


def test_day_end_after_dinner_with_activities_left_is_reviewed_once_then_free():
    a=agent(meal_log=[dict(slot='dinner',size='full')]);acts=actions(meal=False)
    with pytest.raises(ValueError,match='EARLY_DAY_END_WITH_REMAINING_OPTIONS_REVIEW') as exc:A.validate_plan(a,plan(),acts,{},[])
    assert 'night_walk' in str(exc.value) and '여유' in str(exc.value)
    prior={'plan':{},'reason':str(exc.value)}
    # The replan must name what it compared; an unexplained repeat is rejected again.
    with pytest.raises(ValueError,match='MUST_NAME_COMPARED_OPTIONS'):A.validate_plan(a,plan(),acts,{},[],prior)
    named=plan(why_not_other_plans='night_walk은 이동이 필요하고 피로가 조금 있어 오늘은 마친다')
    assert A.validate_plan(a,named,acts,{},[],prior)['execution']=='END_DAY'


@pytest.mark.parametrize('case',['tired_by_executor_scale','only_rest_left','no_meal_option_after_dinner'])
def test_day_end_stands_when_tired_or_nothing_but_rest_is_left(case):
    a=agent();acts=actions()
    if case=='tired_by_executor_scale':a.fatigue=0.8*2.6
    if case=='only_rest_left':acts=actions(meal=False,activity=False)
    if case=='no_meal_option_after_dinner':a.meal_log=[dict(slot='dinner',size='full')];acts=actions(meal=False,activity=False)
    assert A.early_day_end_reasons(a,plan(),acts)==[]
    assert A.validate_plan(a,plan(),acts,{},[])['execution']=='END_DAY'


def test_replan_before_dinner_may_end_the_day_only_with_an_explicit_full_assessment():
    a=agent();acts=actions()
    prior={'plan':{},'reason':A.early_day_end_reasons(a,plan(),acts)[0]}
    with pytest.raises(ValueError,match='EARLY_DAY_END_WITHOUT_EVENING_MEAL_REVIEW'):A.validate_plan(a,plan(),acts,{},[],prior)
    full=plan(current_need_assessment={'state':'FULL','reason':'늦은 점심이 많아 저녁은 생략'})
    assert A.validate_plan(a,full,acts,{},[],prior)['execution']=='END_DAY'
    # A FULL claim on the first attempt still goes through the review once.
    with pytest.raises(ValueError,match='EARLY_DAY_END'):A.validate_plan(a,full,acts,{},[])


def test_day_end_record_marks_a_model_day_end_not_an_observed_sleep():
    cfg=A.configuration()
    assert cfg['live_policy']==A.POLICY_V17 and cfg['policy_versions'][A.POLICY_V17]['day_end_review']=='EVENING_MEAL_REVIEW_BEFORE_DAY_END_V1' and cfg['policy_versions'][A.POLICY]['day_end_review'] is None
    src=Path(A.__file__).read_text(encoding='utf-8')
    assert "'day_end':'MODEL_DAY_END_IN_ROOM_NOT_OBSERVED_SLEEP'" in src


def test_stored_v16_policy_replays_without_the_day_end_review_and_v17_applies_it():
    a=agent();acts=actions()
    assert A.validate_plan(a,plan(),acts,{},[],None,day_end_review=None)['execution']=='END_DAY'
    assert A.POLICIES[A.POLICY]['day_end_review'] is None and A.POLICIES[A.POLICY]['stable_prefix'] is False
    assert A.POLICIES[A.POLICY_V17]['day_end_review']==A.DAY_END_POLICY and A.LIVE_POLICY==A.POLICY_V17
    with pytest.raises(ValueError,match='EARLY_DAY_END'):A.validate_plan(a,plan(),acts,{},[],None,day_end_review=A.POLICIES[A.POLICY_V17]['day_end_review'])
    a16=agent(sc={'hybrid_policy':A.POLICY,'date':'2026-12-18','catalog_policy':A.H.POLICY});a17=agent(sc={'hybrid_policy':A.POLICY_V17,'date':'2026-12-18','catalog_policy':A.H.POLICY})
    assert A.policy_of(a16)==A.POLICY and A.policy_of(a17)==A.POLICY_V17
    assert A.POLICIES[A.POLICY]['system']!=A.POLICIES[A.POLICY_V17]['system'] and 'fatigue_scale' in A.POLICIES[A.POLICY_V17]['system']
    assert A.POLICIES[A.POLICY_V17]['schema']['properties']['plans']['maxItems']==3


def test_v17_context_leads_with_stable_blocks_and_explains_fatigue_and_what_is_left():
    from operator_choice.autonomy_v1 import agent_provider as P
    a=agent(fatigue=0.78,rest_limit=2.89);acts=actions()
    base=dict(state=dict(time='19:39',fatigue=0.78),actions=[dict(action_id=k,execution=v['execution']) for k,v in acts.items()],
              personal=dict(citable_fact_ids=[]),visit=dict(date='2026-12-18'),menus={},world_exclusions=[])
    ctx=A.context_v17(a,1179,base,acts)
    assert list(ctx)[:2]==['personal','visit'] and list(ctx)[-3:]==['actions','menus','world_exclusions']
    scale=ctx['state']['fatigue_scale'];assert scale['ratio_percent']==27 and scale['level']=='여유' and scale['rest_limit']==2.89
    left=ctx['state']['today_remaining'];assert left['dinner_resolved'] is False and left['open_meal_options']==1 and left['open_activity_options']==1 and left['day_end_option']=='end_day_in_room'
    scopes={r['action_id']:r.get('scope') for r in ctx['actions']}
    assert scopes['end_day_in_room']=='CLOSES_TODAY' and scopes['room_rest']=='KEEPS_TODAY_OPEN' and scopes['night_walk'] is None
    wire=P.serialize_context(ctx,stable_prefix=True)
    assert wire.startswith('{"personal":') and '"visit":' in wire[:200]
    assert P.serialize_context(ctx,stable_prefix=False).startswith('{"actions":')
    assert P.serialize_context(ctx,stable_prefix=True)!=P.serialize_context(ctx,stable_prefix=False)


def test_only_a_declared_child_bedtime_reason_may_close_the_day_without_naming_activities(monkeypatch):
    declared={'adult_count':2,'children':[{'age_months':60,'school_stage':'preschool'}]}
    a=agent(C={'kids':True},vs={'nights':1,'party_composition':declared},meal_log=[dict(slot='dinner',size='full')]);acts=actions(meal=False)
    with pytest.raises(ValueError) as exc:A.validate_plan(a,plan(),acts,{},[])
    assert '동행 어린이' in str(exc.value)
    prior={'plan':{},'reason':str(exc.value)}
    # Mentioning a child is not enough: the reason must be about the child's sleep/rest and dinner must be done.
    with pytest.raises(ValueError,match='MUST_NAME_COMPARED_OPTIONS'):A.validate_plan(a,plan(why_not_other_plans='아이와 함께라 산책은 생략'),acts,{},[],prior)
    with pytest.raises(ValueError,match='MUST_NAME_COMPARED_OPTIONS'):A.validate_plan(a,plan(why_not_other_plans='아이 취침 시간',current_need_assessment={'state':'HUNGRY','reason':'x'}),acts,{},[],prior)
    assert A.validate_plan(a,plan(why_not_other_plans='아이 취침 시간이라 산책은 생략'),acts,{},[],prior)['execution']=='END_DAY'
    # The runtime 'kids' guess without a declared composition does not unlock it; neither does a party without children.
    guess=agent(C={'kids':True},meal_log=[dict(slot='dinner',size='full')])
    with pytest.raises(ValueError) as exc2:A.validate_plan(guess,plan(),acts,{},[])
    assert '동행 어린이' not in str(exc2.value)
    with pytest.raises(ValueError,match='MUST_NAME_COMPARED_OPTIONS'):A.validate_plan(guess,plan(why_not_other_plans='아이 취침 시간이라 산책은 생략'),acts,{},[],{'plan':{},'reason':str(exc2.value)})
    # A declared child never forces an early end: the first attempt is still reviewed and the day may go on.
    assert A.validate_plan(a,plan(action_id='night_walk'),acts,{},[])['action_id']=='night_walk'
