"""V18 experiment: the M4 rule engine shortlists, the model selects one candidate.

Synthetic agents, actions and answers; nothing here is model-quality evidence.
The stored V16 path and the V17 LIVE path are untouched (their own tests cover them).
"""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger  # noqa: F401
from operator_choice.autonomy_v1 import autonomous_agent as A
from operator_choice.autonomy_v1 import m4_shortlist as MS
from operator_choice.autonomy_v1 import agent_provider as P


def agent(**over):
    base=dict(N=2,C={'n':2,'kids':False,'elder':False,'couple':True,'solo':False,'friends':False},
        P={'bars':{'food':0.8,'space':0.8,'value_check':0.8,'benefit':0.2,'rest_need':0.0,'routine':0.8},
           'facets':{'novelty':0.6,'premium':0.8,'food_specific':0.0,'warm_rest':0.2,'swim_aversion':0.0,'active':0.0,'alcohol_familiar':0.8,'alcohol_limit':0.0,'breakfast_priority':0.8,'practical_alt':0.8,'promo':0.0},
           'fact_hits':{'footbath':['T-F07','T-F99']},'facts':[],'daily_hits':{}},
        sc={'date':'2026-12-18','catalog_policy':A.H.POLICY,'hybrid_policy':A.POLICY_V18},hunger_e=0.9,fatigue=0.3,rest_limit=3.0,
        meal_log=[],meals={'breakfast':False,'lunch':True,'dinner':False},B='VISTA',stay=True,checked_in=True,checked_out=False,
        club=False,pid='TEST',vs={'nights':1},phase='mid',visit_history={},room='VISTA_ROOM',end=1380,loc='VISTA_ROOM',done=[],log=[],
        verified_source_context={},traits={'facets':{}})
    base.update(over);a=NS(**base)
    a.ctx=lambda:{'done':set(a.done),'fatigue':a.fatigue,'last_kind':None}
    return a


def actions(meal=True,activity=True,day_end=True):
    out={'room_rest':dict(action_id='room_rest',label='객실 휴식',execution='PLAN',kind='ACTIVITY',location='VISTA_ROOM',start=1071,duration=60,items=[],order_total_krw=0),
         'ROOM_REST':dict(action_id='ROOM_REST',label='객실 휴식',execution='ENGINE',kind='ACTIVITY',location='VISTA_ROOM',start=1071,duration=60,items=[],order_total_krw=0,offer={'id':'ROOM_REST'}),
         'public_rest':dict(action_id='public_rest',label='로비 대기',execution='REST',kind='ACTIVITY',location='VISTA_LOBBY',start=1074,duration=30,items=[],order_total_krw=0),
         'wait_reconsider':dict(action_id='wait_reconsider',label='잠시 대기',execution='WAIT',kind='ACTIVITY',location='VISTA_ROOM',start=1071,duration=10,items=[],order_total_krw=0)}
    if day_end:out['end_day_in_room']=dict(action_id='end_day_in_room',label='객실 복귀 · 하루 마무리',execution='END_DAY',kind='ACTIVITY',location='VISTA_ROOM',start=1071,duration=309,items=[],order_total_krw=0)
    if activity:
        out['activity:footbath:SKU1']=dict(action_id='activity:footbath:SKU1',label='스카이야드 족욕',execution='CONTRACT_ACTIVITY',kind='ACTIVITY',native_code='footbath',location='SKYARD',start=1074,duration=45,items=[dict(sku_id='SKU1',quantity=2)],order_total_krw=0,included=True)
        out['garden_walk']=dict(action_id='garden_walk',label='더글라스 가든 산책',execution='PLAN',kind='ACTIVITY',location='AG_GARDEN',start=1083,duration=40,items=[],order_total_krw=0)
        out['library']=dict(action_id='library',label='라이브러리',execution='PLAN',kind='ACTIVITY',location='GRAND_LIBRARY',start=1077,duration=45,items=[],order_total_krw=0)
        out['fitness']=dict(action_id='fitness',label='피트니스',execution='PLAN',kind='ACTIVITY',location='VISTA_FITNESS',start=1074,duration=45,items=[],order_total_krw=0)
    if meal:
        def comp(sku,label,price,tags,unit='pizza',role='MAIN',q=1,source_unit=''):
            return dict(sku_id=sku,billing_quantity=q,label=label,unit_price_krw=price,role=role,tags=tags,billing_unit=unit,source_unit=source_unit)
        def quote(sku,parts,me):
            total=sum(p['unit_price_krw']*p['billing_quantity'] for p in parts)
            return dict(sku_id=sku,label=' + '.join(p['label'] for p in parts),unit_price_krw=total,price_status='MODEL',venue_id='PIZZA_HILL',service_period='dinner',
                        components=parts,meal_basket=dict(meal_equivalents=me,party_size=2))
        pizza=[quote('P-MS',[comp('P-MS','마르게리타 피자 S',69000,['pizza'])],2),
               quote('P-CL',[comp('P-CL','콤비네이션 피자 L',83000,['pizza'])],3),
               quote('P-QH',[comp('P-QH','피자힐 콰트로 피자 HALL',126000,['pizza'])],4),
               quote('P-PP',[comp('P-PA','봉골레 파스타',49000,['pasta'],'portion'),comp('P-PB','해산물 토마토 파스타',48000,['pasta'],'portion')],2),
               quote('P-PP2',[comp('P-PA2','봉골레 파스타',49000,['pasta'],'portion'),comp('P-PB2','해산물 토마토 파스타',48000,['pasta'],'portion')],2),
               quote('P-SET',[comp('P-SET','커플 세트',184000,['pizza'],'set',source_unit='세트 · 2인')],None),
               quote('P-BEER',[comp('P-BEER','BEER Platter (SHALL WE CHEERS)',49000,[],'set',source_unit='세트 · 생맥주 2잔 + 플래터 1종')],None)]
        ondal=[dict(q,sku_id='O-%d'%i,venue_id='ONDAL',components=[dict(c,sku_id='O-%d'%i,label='온달 메뉴 %d'%i,tags=['korean']) for c in q['components']]) for i,q in enumerate(pizza[:2])]
        for venue,quotes in (('PIZZA_HILL',pizza),('ONDAL',ondal)):
            out['meal:'+venue]=dict(action_id='meal:'+venue,label=venue,execution='MEAL',kind='MEAL',location=venue,venue=venue,period='dinner',start=1085,duration=90,
                existing_orders=[dict(items=[dict(sku_id=p['sku_id'],quantity=p['billing_quantity']) for p in q['components']],total_krw=q['unit_price_krw']) for q in quotes],
                _quotes=quotes,planning_viability='AVAILABLE_NOW')
    return out


RECORDS=[dict(fact_ids=['T-F03'],summary='피자힐 콰트로 피자를 포장해 객실에서 나눠 먹었다.',source_scope='wh'),
         dict(fact_ids=['T-F07'],summary='추운 날 족욕과 한강 전망을 좋게 기억했다.',source_scope='wh'),
         dict(fact_ids=['T-F93'],summary='다른 호텔에서 룸서비스 대신 피자힐 같은 피자를 사 먹었다.',source_scope='other')]


def fake_engine_score(a,t,action,c,w,citable):
    # Stand-in for the native product score: nearly flat and price-driven, like the real A07 피자힐 case.
    return round(5.4-c['unit_price_krw']/1e6,3),['테스트'],['T-F03'],False


@pytest.fixture
def shortlist(monkeypatch):
    monkeypatch.setattr(MS,'engine_score',fake_engine_score)
    def run(a=None,acts=None,t=1071,records=RECORDS,**kw):
        a=a or agent();acts=acts if acts is not None else actions()
        return MS.build(a,{},t,acts,{},{},citable=['T-F03','T-F07','T-F93'],records=records,**kw)
    return run


def test_shortlist_keeps_mandatory_candidates_covers_types_and_traces_every_drop(shortlist):
    rows,trace=shortlist()
    ids=[r['action_id'] for r in rows]
    assert len(rows)<=MS.MAX_OPTIONS+1 and 'end_day_in_room' in ids
    types=[r['type'] for r in rows]
    assert 'MEAL' in types and 'ACTIVITY' in types and 'REST' in types and 'DAY_END' in types
    # neutral display order: meals first, day end last; never the mandatory candidate leading the list
    assert types==sorted(types,key=lambda k:{'MEAL':0,'ACTIVITY':2,'REST':3,'DAY_END':4}[k])
    dropped={d['action_id']:d['reason'] for d in trace['dropped']}
    assert dropped['ROOM_REST']=='DUPLICATE_OF:room_rest'
    assert set(dropped)|set(ids)==set(actions())
    assert all(d['reason'] for d in trace['dropped']) and trace['candidate_count']==len(actions())
    foot=next(r for r in rows if r['action_id']=='activity:footbath:SKU1')
    assert foot['m4']['rank_in_type']==1 and foot['m4']['evidence_fact_ids']==['T-F07'] and foot['conditions']['start_time']=='17:54'
    assert foot['m4']['meaning'].startswith('RULE_FIT') and 'NOT_VERIFIED_PREFERENCE' in trace['meaning']


def test_basket_groups_are_chosen_by_criteria_and_keep_every_quoted_variant_of_a_named_menu(shortlist):
    rows,trace=shortlist()
    pizza=next(r for r in rows if r['action_id']=='meal:PIZZA_HILL')
    groups={g['label']:g for g in pizza['basket_groups']}
    # the restaurant's own record names 콰트로 피자: the pizza group is shown for that, with the named item first
    assert groups['피자']['shown_because']=='EXPERIENCE_ITEM' and groups['피자']['experience_fact_ids']==['T-F03']
    opts=[o['label'] for o in groups['피자']['options']]
    assert opts[0]=='피자힐 콰트로 피자 HALL' and '직접 경험 메뉴' in groups['피자']['options'][0]['marks']
    # other quoted pizzas stay selectable, ordered by portion fit for the party then price (S before L)
    assert opts[1:]==['마르게리타 피자 S','콤비네이션 피자 L']
    assert '최저가(인원 충족)' in groups['피자']['options'][1]['marks']
    # top product score keeps a slot; a set stated for this party size is a meaningful choice
    # here the cheapest pizza also has the top score, so pasta comes in as the next score group
    assert groups['파스타']['shown_because']=='NEXT_PRODUCT_SCORE' and len(groups['파스타']['options'])==1      # P-PP2 is the same two dishes
    assert groups['코스·세트']['shown_because']=='SET_FOR_THIS_PARTY_SIZE'
    assert len(pizza['basket_groups'])==MS.MAX_GROUPS
    fit=trace['fit']['meal:PIZZA_HILL']
    reasons={d['sku_id']:d['reason'] for d in fit['dropped_baskets']}
    assert reasons['P-PP2'].startswith('SAME_MAIN_AS:') and reasons['P-BEER'].startswith('NOT_A_MEAL_BASKET_FOR_MEAL_DECISION')
    # every shown option resolves to an engine-quoted contract through the trace index
    idx=fit['basket_index']
    assert all(o['basket_id'] in idx and idx[o['basket_id']]['items'] for g in pizza['basket_groups'] for o in g['options'])
    assert '긍정·부정' in pizza['basket_note']


def test_drink_platters_are_not_meals_and_other_hotel_records_never_protect_a_venue(shortlist,monkeypatch):
    acts=actions()
    q={c['sku_id']:c for c in acts['meal:PIZZA_HILL']['_quotes']}
    assert MS.basket_role(q['P-BEER'])=='DRINK_SNACK' and MS.basket_role(q['P-MS'])=='MEAL' and MS.basket_role(q['P-SET'])=='MEAL'
    # after dinner (not a meal decision) a drink platter may be shown as what it is
    a=agent(meal_log=[dict(slot='dinner',size='full')],meals={'breakfast':False,'lunch':True,'dinner':True})
    fit=MS.meal_fit(a,1071,'meal:PIZZA_HILL',acts['meal:PIZZA_HILL'],{},['T-F03'],RECORDS,meal_decision=False)
    assert any(g['role']=='DRINK_SNACK' for g in fit['groups']), 'after dinner a drink platter is shown as what it is'
    # a record from another hotel that mentions 피자힐-like food does not count as this restaurant's experience
    only_other=[RECORDS[2]]
    rows,trace=shortlist(records=only_other)
    pizza=next(r for r in rows if r['action_id']=='meal:PIZZA_HILL')
    assert all(g['shown_because']!='EXPERIENCE_ITEM' for g in pizza['basket_groups'])
    assert MS.venue_records(agent(),'PIZZA_HILL',only_other,['T-F93'])==[]


def test_the_top_meal_is_never_dropped_while_dinner_is_unresolved_and_rest_is_always_represented(shortlist):
    rows,_=shortlist(a=agent(hunger_e=0.0))
    assert any(r['type']=='MEAL' for r in rows) and any(r['type']=='REST' for r in rows)
    a=agent(meal_log=[dict(slot='dinner',size='full')],meals={'breakfast':False,'lunch':True,'dinner':True})
    rows,trace=shortlist(a=a)
    ids=[r['action_id'] for r in rows]
    assert 'end_day_in_room' in ids and 'room_rest' in ids
    assert all(d['reason'] in ('TYPE_BUDGET_FULL','OPTION_BUDGET_FULL','EVIDENCE_LINKED_BUT_OPTION_BUDGET_FULL') or d['reason'].startswith('DUPLICATE_OF') for d in trace['dropped'])


def test_rule_only_scope_is_limited_to_moments_the_world_decides(shortlist):
    a=agent()
    rows,_=shortlist(a=a)
    assert MS.rule_sufficient(rows,a,1071,actions())==(None,None),'meals and activities always go to the model'
    # rest and day end both possible: the model decides, whatever the fatigue or the clock
    for fatigue,t in ((0.3,1071),(1.4,1071),(0.3,1350)):
        acts=actions(meal=False,activity=False);g=agent(fatigue=fatigue)
        rows,_=shortlist(a=g,acts=acts,t=t)
        assert MS.rule_sufficient(rows,g,t,acts)==(None,None)
    # only day end and the 10-minute wait left: the world has nothing else to offer
    acts={k:v for k,v in actions(meal=False,activity=False).items() if k in ('end_day_in_room','wait_reconsider')}
    assert MS.rule_sufficient([],agent(),1340,acts)==('end_day_in_room','DAY_END_OR_SHORT_WAIT')
    plan=A.rule_plan('end_day_in_room','test',acts)
    assert A.validate_plan(agent(),plan,acts,{},[],None,day_end_review=A.DAY_END_POLICY)['execution']=='END_DAY'
    leave=dict(action_id='leave_visit',label='귀가',execution='LEAVE',kind='ACTIVITY',location='HOTEL_GATE',start=655,duration=15,items=[],order_total_krw=0)
    assert MS.rule_sufficient([],agent(checked_out=True),647,{'leave_visit':leave})==('leave_visit','SINGLE_VALID_ACTION')
    after=dict(leave_visit=leave,wait_reconsider=actions()['wait_reconsider'])
    assert MS.rule_sufficient([],agent(checked_out=True),647,after)==('leave_visit','CHECKED_OUT_NOTHING_LEFT')
    # a lobby rest after checkout is a rest option: the model decides
    assert MS.rule_sufficient([],agent(checked_out=True),647,dict(after,public_rest=actions()['public_rest']))==(None,None)
    # a lunch still open after checkout is a personal choice
    assert MS.rule_sufficient([],agent(checked_out=True),647,dict(after,**{'meal:PIZZA_HILL':actions()['meal:PIZZA_HILL']}))==(None,None)
    assert MS.RULE_SCOPE==('SINGLE_VALID_ACTION','CHECKED_OUT_NOTHING_LEFT','DAY_END_OR_SHORT_WAIT')


def test_expand_selection_fixes_the_order_from_the_engine_basket_index(shortlist):
    rows,trace=shortlist();acts=actions()
    pizza=next(r for r in rows if r['action_id']=='meal:PIZZA_HILL')
    cl=next(o for g in pizza['basket_groups'] for o in g['options'] if o['label']=='콤비네이션 피자 L')
    sel=dict(selected_action_id='meal:PIZZA_HILL',selected_basket_id=cl['basket_id'],reason='테스트 선택',supporting_fact_ids=['T-F03'],counterevidence_fact_ids=[],
             rejected_alternative=dict(action_id='meal:ONDAL',reason='오늘은 피자'),next_intent='내일 족욕',
             current_need_assessment=dict(state='HUNGRY',reason='테스트'),
             meal_assessment=dict(kind='FULL_MEAL',modeled_diners=2,sharing_plan='둘이 나눔',quantity_reason='한 판',expected_satiety='COMFORTABLE'))
    plan,alt=A.expand_selection(sel,rows,acts,{},trace)
    assert plan['items']==[dict(sku_id='P-CL',quantity=1)] and plan['order_total_krw']==83000 and plan['selected_basket_id']==cl['basket_id']
    assert plan['why_not_other_plans']=='meal:ONDAL: 오늘은 피자' and plan['pending_intentions']==['내일 족욕'] and plan['sharing_plan']=='둘이 나눔'
    assert alt['action_id']=='meal:ONDAL' and alt['v18_alternative']
    A.X.validate_assessment(plan,2,True)
    with pytest.raises(ValueError,match='MEAL_REQUIRES_A_SHORTLISTED_BASKET'):A.expand_selection(dict(sel,selected_basket_id='meal:PIZZA_HILL#99'),rows,acts,{},trace)
    with pytest.raises(ValueError,match='MEAL_REQUIRES_A_SHORTLISTED_BASKET'):A.expand_selection(sel,rows,acts,{},None)
    with pytest.raises(ValueError,match='SELECTED_ACTION_NOT_IN_SHORTLIST'):A.expand_selection(dict(sel,selected_action_id='fitness'),rows,acts,{},trace)
    with pytest.raises(ValueError,match='BASKET_ONLY_FOR_MEALS'):A.expand_selection(dict(sel,selected_action_id='room_rest'),rows,acts,{},trace)
    rest,_=A.expand_selection(dict(sel,selected_action_id='room_rest',selected_basket_id=None,meal_assessment=None),rows,acts,{},trace)
    assert rest['items']==[] and rest['order_total_krw']==0 and rest['meal_assessment'] is None


def test_v18_policies_are_registered_as_experiments_without_touching_v16_or_v17():
    assert A.LIVE_POLICY_PREVIOUS==A.POLICY_V17 and A.LIVE_POLICY==A.POLICY_V19LS and A.POLICIES[A.POLICY]['select'] is False and A.POLICIES[A.POLICY_V17]['select'] is False
    assert A.V18_VARIANTS==(A.POLICY_V18,A.POLICY_V18B,A.POLICY_V18BM,A.POLICY_V18BD)
    for name in A.V18_VARIANTS:
        spec=A.POLICIES[name]
        assert spec['select'] and spec['day_end_review']==A.DAY_END_POLICY
        assert 'plans' not in spec['schema']['properties'] and 'selected_action_id' in spec['schema']['properties']
    # one variable at a time: B vs A only the evidence block; C vs B only effort; D vs B only the output contract
    A_,B_,C_,D_=(A.POLICIES[n] for n in A.V18_VARIANTS)
    assert A_['context']=='AUTONOMOUS_CONTEXT_V18_SHORTLIST' and B_['context']==C_['context']==D_['context']=='AUTONOMOUS_CONTEXT_V18_COMPACT'
    assert A_['schema'] is B_['schema'] is C_['schema'] and D_['schema'] is A.SELECTION_V18D
    assert A_['effort'] is None and B_['effort'] is None and C_['effort']=='medium' and D_['effort'] is None
    assert A_['system']==B_['system']==C_['system'] and D_['system']!=B_['system'] and 'evidence_scope' in A.SYSTEM_V18_COMMON
    assert A_['prefix_message']==B_['prefix_message']==C_['prefix_message']==D_['prefix_message']=='personal'
    assert set(A.SELECTION_V18D['properties'])=={'selected_action_id','selected_basket_id','fact_ids','reason','rejected_action_id','need'}
    cfg=A.configuration()['policy_versions']
    assert cfg[A.POLICY_V18]['selection']=='M4_SHORTLIST_THEN_LLM_SELECTION' and cfg[A.POLICY_V18]['max_plans']==1 and cfg[A.POLICY_V17]['max_plans']==3
    assert A.policy_of(agent())==A.POLICY_V18
    # V18 context: candidates replace actions/menus/exclusions; stable blocks still lead the wire
    ctx=A.context_v18(agent(),1071,dict(personal={'citable_fact_ids':[]},visit={},state={'time':'17:51','fatigue':0.3},actions=[],menus={'x':[]},world_exclusions=[1]),actions(meal=False),
                      [dict(action_id='room_rest',type='REST')],dict(policy=MS.SHORTLIST_POLICY,candidate_count=5,dropped=[]))
    assert list(ctx)[:2]==['personal','visit'] and 'menus' not in ctx and 'world_exclusions' not in ctx and ctx['candidates'][0]['action_id']=='room_rest'
    assert ctx['state']['fatigue_scale']['level']=='여유' and ctx['shortlist']['candidate_count']==5
    # prefix message layout: the evidence block becomes its own, byte-identical user message
    import visit_execution
    assert A.POLICY_V18 in visit_execution.POLICIES and visit_execution.LIVE_POLICY==A.POLICY_V19LS and visit_execution.PREVIOUS_LIVE_POLICY==A.POLICY_V17 and A.POLICY_V17 in visit_execution.POLICIES


def test_provider_prefix_message_splits_the_evidence_block(monkeypatch):
    seen={}
    class Fake:
        def __init__(self,data):self.data=data
        def read(self):return json.dumps(dict(status='completed',usage=dict(input_tokens=10,output_tokens=5),output=[dict(type='message',content=[dict(type='output_text',text='{"x":1}')])])).encode()
        def __enter__(self):return self
        def __exit__(self,*a):return False
    def urlopen(req,timeout,context):
        seen['payload']=json.loads(req.data);return Fake(None)
    monkeypatch.setattr(P.urllib.request,'urlopen',urlopen)
    monkeypatch.setattr(P,'load_openai_api_key',lambda:'k',raising=False)
    import types
    monkeypatch.setitem(sys.modules,'openai_credentials',types.SimpleNamespace(load_openai_api_key=lambda:'k'))
    budget=NS(reserve=lambda m,meta:'rid',settle=lambda rid,**kw:dict(kw,charged_upper_usd=0))
    monkeypatch.setattr(P,'configured_budget',lambda:budget)
    with patch.dict(os.environ,dict(HILLINK_AGENT_MODE='live',HILLINK_LLM_EXTERNAL_OPT_IN='1',HILLINK_AGENT_CACHE='')):
        answer,trace=P.request(policy='T',system='s',context=dict(personal={'a':1},state={'b':2}),schema={'type':'object','properties':{'x':{'type':'integer'}},'required':['x'],'additionalProperties':False},
                               purpose='TEST',effort='medium',stable_prefix=True,prefix_message='personal')
    msgs=seen['payload']['input']
    assert [m['role'] for m in msgs]==['system','user','user'] and msgs[1]['content']=='{"personal":{"a":1}}' and msgs[2]['content']=='{"state":{"b":2}}'
    assert seen['payload']['reasoning']=={'effort':'medium'} and answer=={'x':1}


FIXTURE='''import json,sys
sys.path.insert(0,sys.argv[1])
import flow_run, jsonschema
from operator_choice.autonomy_v1 import autonomous_agent as A, agent_provider as P
def answer(**kw):
 c=kw['context']; rows=c['candidates']; prior=c.get('previous_rejection'); by={r['action_id']:r for r in rows}
 assert kw['policy']==A.POLICY_V18 and kw['prefix_message']=='personal' and list(c)[:2]==['personal','visit'] and 'menus' not in c and 'actions' not in c
 assert len(rows)<=A.MS.MAX_OPTIONS+1 and all(len(r.get('basket_groups') or [])<=3 for r in rows)
 meals=[r for r in rows if r['type']=='MEAL']; acts=[r for r in rows if r['type']=='ACTIVITY']; rests=[r for r in rows if r['type']=='REST' and r['action_id']!='wait_reconsider']
 n=c['visit'].get('party_size') or 2; basket=None; meal=False
 if kw['purpose']=='BREAKFAST_SELECTION':
  sel=next((r['action_id'] for r in rows if r['type']=='BREAKFAST'),rows[0]['action_id']); meal=sel!='SKIP_BREAKFAST'; alt=('SKIP_BREAKFAST','합성')
 elif 'end_day_in_room' in by and not prior:
  sel='end_day_in_room'; alt=((acts or rests or rows)[0]['action_id'],'합성: 바로 오늘을 마친다')
 elif prior and 'MEAL_REVIEW' in prior['reason'] and meals:
  sel=meals[0]['action_id']; basket=meals[0]['basket_groups'][-1]['options'][-1]['basket_id']; meal=True; alt=('end_day_in_room','합성: 저녁 전이라 미룸')
 elif prior and 'end_day_in_room' in by:
  sel='end_day_in_room'; alt=((acts or rests)[0]['action_id'],'합성: 비교한 후보 '+', '.join(r['action_id'] for r in (acts+rests)[:2]))
 elif 'leave_visit' in by:
  sel='leave_visit'; alt=(rows[0]['action_id'] if rows[0]['action_id']!='leave_visit' else rows[-1]['action_id'],'합성')
 elif acts: sel=acts[0]['action_id']; alt=((rests or rows)[0]['action_id'],'합성')
 elif meals: sel=meals[0]['action_id']; basket=meals[0]['basket_groups'][0]['options'][0]['basket_id']; meal=True; alt=(rows[-1]['action_id'],'합성')
 else: sel=rows[0]['action_id']; alt=(rows[-1]['action_id'],'합성')
 out=dict(selected_action_id=sel,selected_basket_id=basket,reason='합성 선택 '+sel,supporting_fact_ids=[],counterevidence_fact_ids=[],rejected_alternative=dict(action_id=alt[0],reason=alt[1]),
  next_intent=None,current_need_assessment=dict(state='COMFORTABLE',reason='합성'),
  meal_assessment=dict(kind='FULL_MEAL',modeled_diners=n,sharing_plan='합성',quantity_reason='합성',expected_satiety='UNCERTAIN') if meal else None)
 jsonschema.validate(out,kw['schema'])
 return out,dict(execution='SYNTHETIC_TEST',input_sha256='fixture')
A.P.request=answer
flow_run.main()
'''


def test_v18_visit_runs_end_to_end_with_shortlists_rule_moments_and_the_day_end_review(tmp_path):
    import visit_run as V
    script=tmp_path/'fixture.py';script.write_text(FIXTURE)
    with patch.dict(os.environ,dict(HILLINK_AUTONOMOUS_AGENT='1',HILLINK_NATIVE_HYBRID='1',HILLINK_V12Z_COMMON='1',
        HILLINK_HYBRID='replay',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_ISOLATED_CUSTOMERS='0')):
        request=dict(personas=['A05'],duration='stay_1',event_mode='none',seed=62,start_date='2026-11-09',environment=dict(arrival_time='14:30'),
            behavior_engine='m4_c01',catalog_policy=A.H.POLICY,hybrid_policy=A.POLICY_V18)
        with patch.object(V,'FLOW',[sys.executable,str(script),str(Path(__file__).resolve().parents[1])]):
            flow=V.run_visit(request)
    assert 'error' not in flow,flow
    decs=flow['plans']['A05']['autonomous_decisions']
    assert decs and all(d['policy']==A.POLICY_V18 for d in decs) and flow['plans']['A05']['trace']['planner_backend']==A.POLICY_V18
    assert all(d['execution_state']=='EXECUTED' for d in decs),[d.get('fallback_reason') for d in decs]
    llm=[d for d in decs if d.get('selection_owner','').startswith('LLM')]
    assert llm and all(d['shortlist']['policy']==MS.SHORTLIST_POLICY and 1<=len(d['shortlist_ids'])<=MS.MAX_OPTIONS+1 for d in llm if 'shortlist' in d)
    # every selection is PLAN-shaped for the existing screens and the record says who selected
    for d in llm:
        p=d['selected_plan'];assert p['selection_policy']=='V18_M4_SHORTLIST_LLM_SELECTION' and d['attempts'][-1]['answer']['plans'][0]['action_id']==p['action_id']
        assert 'selection' in d['attempts'][-1] and d['llm_calls']==len(d['attempts'])
    agree=[d['m4_agreement'] for d in llm if d.get('m4_agreement')]
    assert agree and all('agrees_with_m4_top' in x for x in agree)
    meals=[d for d in llm if d['selected_plan']['action_id'].startswith('meal:')]
    assert meals and all(d['selected_plan']['selected_basket_id'] and d['selected_plan']['items'] for d in meals)
    ends=[d for d in decs if d['selected_plan']['action_id']=='end_day_in_room']
    assert ends
    reviewed=[d for d in ends if d.get('day_end_review',{}).get('first_choice_rejected')]
    assert reviewed,'the synthetic provider tries to end the day first; the V18 review must have rejected that once'
    rule=[d for d in decs if d.get('selection_owner')=='M4_RULE']
    for d in rule:assert d['attempts']==[] and d['llm_calls']==0 and d['rule_basis']
    scenes=flow['plans']['A05']['scenes']
    assert all('취침' not in (s.get('label') or '') for s in scenes)
    # the full V16 menus never reached the model under V18, but the record keeps the products it ordered
    assert all(d['input_context']['products'] for d in meals)


def test_a_directly_evidence_linked_candidate_is_shown_even_when_its_score_is_lower(shortlist):
    a=agent();a.P=dict(a.P,fact_hits={'footbath':['T-F07'],'lunch_ondal':['T-F03']})
    records=RECORDS[:2]+[dict(fact_ids=['T-F03'],summary='온달 한식을 먹었다.',source_scope='wh')]
    rows,trace=shortlist(a=a,records=records)
    ondal=next(r for r in rows if r['action_id']=='meal:ONDAL')
    assert ondal['m4']['shown_because']=='DIRECT_PERSONAL_EVIDENCE_LINK' and 'T-F03' in ondal['m4']['direct_evidence_fact_ids']
    assert not [d for d in trace['dropped'] if d.get('direct_evidence_fact_ids')]
    # another hotel's record linked by the review linker is shown as similar experience, never as protection
    a.P=dict(a.P,fact_hits={'footbath':['T-F07'],'lunch_ondal':['T-F93']})
    rows,trace=shortlist(a=a,records=RECORDS)
    ondal=next((r for r in rows if r['action_id']=='meal:ONDAL'),None)
    fit=trace['fit']['meal:ONDAL'] if 'meal:ONDAL' in trace['fit'] else None
    assert ondal is None or ondal['m4']['shown_because']!='DIRECT_PERSONAL_EVIDENCE_LINK'


def test_review_findings_people_words_scope_and_meal_rows_without_meal_options(shortlist,monkeypatch):
    # people/target words never make a dish an "experience menu" (커플로 방문 != 커플 세트를 먹음)
    records=[dict(fact_ids=['T-F03'],summary='피자힐은 커플로 방문해 창가에 앉았다.',source_scope='wh')]
    rows,_=shortlist(records=records)
    pizza=next(r for r in rows if r['action_id']=='meal:PIZZA_HILL')
    sets=next(g for g in pizza['basket_groups'] if g['label']=='코스·세트')
    assert sets['shown_because']!='EXPERIENCE_ITEM' and '직접 경험 메뉴' not in sets['options'][0]['marks']
    # a record whose scope is unconfirmed is neither protection nor 'elsewhere'
    a=agent();a.P=dict(a.P,fact_hits={'footbath':['T-U1']})
    rows,_=MS.build(a,{},1071,actions(),{},{},citable=['T-F03','T-F07','T-U1'],records=RECORDS+[dict(fact_ids=['T-U1'],summary='족욕을 했다.',source_scope='UNRESOLVED')])
    foot=next(r for r in rows if r['action_id']=='activity:footbath:SKU1')
    assert foot['m4']['direct_evidence_fact_ids']==[] and foot['m4']['similar_elsewhere_fact_ids']==[] and foot['m4']['scope_unconfirmed_fact_ids']==['T-U1']
    # while dinner is open, a venue with only drink/dessert baskets is not offered as a meal candidate
    acts=actions();acts['meal:PIZZA_HILL']['_quotes']=[q for q in acts['meal:PIZZA_HILL']['_quotes'] if q['sku_id']=='P-BEER']
    rows,trace=shortlist(acts=acts)
    assert 'meal:PIZZA_HILL' not in [r['action_id'] for r in rows]
    assert {'action_id':'meal:PIZZA_HILL','type':'MEAL','fit':None,'reason':'NO_MEAL_OPTION_FOR_THIS_DECISION'} in trace['dropped']


def test_variant_b_request_differs_from_a_only_in_the_persona_block():
    import json
    a=agent();acts=actions(meal=False)
    rows=[dict(action_id='room_rest',type='REST',m4=dict(trait_terms=[])),dict(action_id='end_day_in_room',type='DAY_END',m4=dict(trait_terms=[]))]
    trace=dict(policy=MS.SHORTLIST_POLICY,candidate_count=2,dropped=[],fit={})
    base=dict(personal=dict(citable_fact_ids=['T-F07'],profile=dict(customer_type='x',summary='y'),evidence_grades={},evidence_records=RECORDS[1:2]),
              visit=dict(date='2026-12-18'),state=dict(time='17:51',fatigue=0.3),needs_model=dict(policy='N'),reassessment=dict(prev='p'),memory=dict(pending_intentions=[]),
              meal_experiences=[],activity_experiences=[],actions=[],menus={},world_exclusions=[])
    full_a,_,_=A.variant_request(a,1071,base,acts,rows,trace,base['personal'],A.POLICIES[A.POLICY_V18])
    full_b,cite,_=A.variant_request(a,1071,base,acts,rows,trace,base['personal'],A.POLICIES[A.POLICY_V18B])
    rest=lambda c:{k:json.dumps(v,ensure_ascii=False,sort_keys=True) for k,v in c.items() if k!='personal'}
    assert rest(full_a)==rest(full_b) and list(full_a)==list(full_b) and list(full_a)[0]=='personal'
    assert list(full_a['personal'])==list(full_b['personal']) and full_a['personal']['evidence_scope']['mode']=='FULL_PERSONA_EVIDENCE'
    assert full_b['personal']['evidence_scope']['mode']=='CANDIDATE_RELATED_EVIDENCE'
    # A, B and C send the same system prompt and message layout; D differs only after the output marker
    specs=[A.POLICIES[p] for p in A.V18_VARIANTS]
    assert len({s['system'] for s in specs if not s.get('minimal_output')})==1 and {s['prefix_message'] for s in specs}=={'personal'}
    d=A.POLICIES[A.POLICY_V18BD]['system']
    assert d.split('\n응답 작성:')[0]==A.SYSTEM_V18.split('\n응답 작성:')[0]==A.SYSTEM_V18_COMMON and d!=A.SYSTEM_V18


def test_one_candidate_per_sold_contract_keeps_both_names_evidence(shortlist):
    acts=actions(meal=False)
    acts['activity:night_footbath:SKU1']=dict(acts['activity:footbath:SKU1'],action_id='activity:night_footbath:SKU1',label='스카이야드 야경 족욕',native_code='night_footbath',contract=dict(sku_id='SKU1'))
    acts['activity:footbath:SKU1']['contract']=dict(sku_id='SKU1')
    rows,trace=shortlist(acts=acts,t=1175)
    ids=[r['action_id'] for r in rows]
    assert 'activity:night_footbath:SKU1' in ids and 'activity:footbath:SKU1' not in ids, 'after 18:00 the night name is kept'
    night=next(r for r in rows if r['action_id']=='activity:night_footbath:SKU1')
    assert 'T-F07' in night['m4']['direct_evidence_fact_ids'], 'the day variant evidence (same facility) is carried over'
    assert any(d['reason']=='SAME_CONTRACT_AS:activity:night_footbath:SKU1' for d in trace['dropped'])


def test_an_operator_applied_event_is_always_shown_never_chosen_for_the_model(shortlist):
    """2026-11-09: the wine fair was a valid candidate in 17 LIVE decisions but the score-ranked budget showed it once.
    An event the operator applied is now always offered while it can be joined; the model still decides."""
    acts=actions()
    acts['WINE_FAIR']=dict(action_id='WINE_FAIR',label='와인페어(포레스트 파크)',execution='ENGINE',kind='ACTIVITY',location='FOREST_PARK',start=1080,duration=90,items=[],order_total_krw=0,offer={'id':'WINE_FAIR'})
    acts['CARD_SAVORING_SUMMER_NIGHT_2026']=dict(action_id='CARD_SAVORING_SUMMER_NIGHT_2026',label='Savoring Summer Night',execution='ENGINE',kind='ACTIVITY',location='RIVERPARK',start=1080,duration=120,items=[],order_total_krw=0,offer={'id':'CARD_SAVORING_SUMMER_NIGHT_2026'})
    rows,trace=shortlist(acts=acts)
    ids=[r['action_id'] for r in rows]
    assert 'WINE_FAIR' in ids and 'CARD_SAVORING_SUMMER_NIGHT_2026' in ids and 'end_day_in_room' in ids
    rows2,_=shortlist()
    assert not any(r['action_id']=='WINE_FAIR' or r['action_id'].startswith('CARD_') for r in rows2)   # no event, nothing added


def test_meal_context_v2_is_research_only_room_service_time_unconfirmed_and_one_more_restaurant(shortlist,monkeypatch):
    """2026-11-09 (INT5M): room service had wait 0 with no recorded delivery time, and only one restaurant was ever compared.
    The switch is OFF for INT4 (saved records) and ON only under INT5M; it never chooses or removes a candidate."""
    acts=actions()
    rq=[dict(q,venue_id='ROOM_MEAL') for q in acts['meal:PIZZA_HILL']['_quotes'][:2]]
    acts['meal:ROOM_MEAL']=dict(acts['meal:PIZZA_HILL'],action_id='meal:ROOM_MEAL',label='객실 룸서비스',location='VISTA_ROOM',venue='ROOM_MEAL',start=1071,duration=60,_quotes=rq)
    monkeypatch.delenv('HILLINK_RESEARCH_MEAL_CONTEXT_V2',raising=False)
    rows,_=shortlist(acts=acts)
    room=next(r for r in rows if r['action_id']=='meal:ROOM_MEAL')
    assert room['conditions']['wait_minutes']==0 and 'delivery_time' not in room['conditions']
    off=[r['action_id'] for r in rows if r['type']=='MEAL']
    monkeypatch.setenv('HILLINK_RESEARCH_MEAL_CONTEXT_V2','1')
    rows,trace=shortlist(acts=acts)
    room=next(r for r in rows if r['action_id']=='meal:ROOM_MEAL')
    assert room['conditions']['wait_minutes'] is None and '미확인' in room['conditions']['delivery_time']
    on=[r['action_id'] for r in rows if r['type']=='MEAL']
    assert {'meal:PIZZA_HILL','meal:ONDAL'}<=set(on) and set(off)<=set(on) and 'end_day_in_room' in [r['action_id'] for r in rows]


def test_int5m_policy_runs_exactly_int4_plus_meal_context():
    env=A.policy_environment(A.POLICY_V19LS_INT5M,{'HILLINK_RESEARCH_REST_CONTINUE':'1','PATH':'x'})
    on={k for k,v in env.items() if k.startswith('HILLINK_RESEARCH_')}
    both={'HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED','HILLINK_RESEARCH_MEAL_SECOND_RESTAURANT'}
    assert on==set(A.INT4_SWITCHES)|both and env['PATH']=='x'   # default part set A3 = MEAL_CONTEXT_V2
    for v,parts in (('A1',{'HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED'}),('A2',{'HILLINK_RESEARCH_MEAL_SECOND_RESTAURANT'}),('A3',both)):
        env=A.policy_environment(A.POLICY_V19LS_INT5M,{'HILLINK_INT5M_VARIANT':v})
        assert {k for k in env if k.startswith('HILLINK_RESEARCH_')}==set(A.INT4_SWITCHES)|parts
    import pytest
    with pytest.raises(ValueError): A.policy_environment(A.POLICY_V19LS_INT5M,{'HILLINK_INT5M_VARIANT':'A9'})
    assert {k for k,v in A.policy_environment(A.POLICY_V19LS_INT4,{}).items()}==set(A.INT4_SWITCHES)


def test_int5m_parts_are_independent(shortlist,monkeypatch):
    """A1 changes only the room-service timing note; A2 only adds a restaurant slot (separation study 2026-11-09)."""
    acts=actions()
    rq=[dict(q,venue_id='ROOM_MEAL') for q in acts['meal:PIZZA_HILL']['_quotes'][:2]]
    acts['meal:ROOM_MEAL']=dict(acts['meal:PIZZA_HILL'],action_id='meal:ROOM_MEAL',label='객실 룸서비스',location='VISTA_ROOM',venue='ROOM_MEAL',start=1071,duration=60,_quotes=rq)
    for k in ('HILLINK_RESEARCH_MEAL_CONTEXT_V2','HILLINK_RESEARCH_MEAL_SECOND_RESTAURANT','HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED'): monkeypatch.delenv(k,raising=False)
    rows0=shortlist(acts=acts)[0]; a0=[r['action_id'] for r in rows0 if r['type']=='MEAL']
    room0=next(r for r in rows0 if r['action_id']=='meal:ROOM_MEAL')
    monkeypatch.setenv('HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED','1')
    rows,_=shortlist(acts=acts); room=next(r for r in rows if r['action_id']=='meal:ROOM_MEAL')
    a1=[r['action_id'] for r in rows if r['type']=='MEAL']
    assert room['conditions']['wait_minutes'] is None and '미확인' in room['conditions']['delivery_time']
    assert {k:v for k,v in room['conditions'].items() if k not in ('wait_minutes','delivery_time','basis')}=={k:v for k,v in room0['conditions'].items() if k not in ('wait_minutes','basis')}
    # only the invented 0-minute wait is replaced; a guest outside the room keeps the way back (offline A0/A1 check: 2 of 28 visits)
    away=agent(loc='VISTA_LOBBY')
    monkeypatch.delenv('HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED')
    t0=next(r for r in shortlist(a=away,acts=acts)[0] if r['action_id']=='meal:ROOM_MEAL')['conditions']['travel_minutes']
    monkeypatch.setenv('HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED','1')
    t1=next(r for r in shortlist(a=away,acts=acts)[0] if r['action_id']=='meal:ROOM_MEAL')['conditions']['travel_minutes']
    assert t0>0 and t1==t0
    monkeypatch.delenv('HILLINK_RESEARCH_MEAL_ROOM_DELIVERY_UNCONFIRMED'); monkeypatch.setenv('HILLINK_RESEARCH_MEAL_SECOND_RESTAURANT','1')
    rows,_=shortlist(acts=acts); room=next(r for r in rows if r['action_id']=='meal:ROOM_MEAL')
    a2=[r['action_id'] for r in rows if r['type']=='MEAL']
    assert room['conditions']['wait_minutes']==0 and 'delivery_time' not in room['conditions']
    assert a1==a0 and set(a0)<=set(a2)   # A1 never changes exposure; A2 only adds
