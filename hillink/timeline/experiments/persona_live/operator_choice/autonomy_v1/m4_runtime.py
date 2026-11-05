"""Live M4 integration. One worker, one persona, one chronological day.

One shared World and chronological decision queue are used for multi-agent visits.
Only approved runtime inputs are read. No research snapshot is an execution
input; the source commit below documents the port, not a replay mechanism.
"""
from __future__ import annotations
import copy,hashlib,inspect,json,random
from contextlib import contextmanager
from pathlib import Path
from .m4_context import AD,SP,M4Context,patch,digest

VERSION='m4-live-v2-shared-world'
SOURCE_COMMIT='ae37786b0c3a6cbb0de6ef71f2b0758cc293d191'

def configuration():
    root=Path(__file__).parent
    sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in
             ('m4_runtime.py','general_food.py','general_food_sources.json','food_evidence.py','m4_context.py','m4_meal.py','m4_event.py','consumption_orders.py','hotel_catalog.py','official_contracts.py','official_menu_overlay.json','package_benefits.py','breakfast_policy.py','douglas_light_breakfast.py')}
    for name,module in (('native_agent',AD),('native_planner',SP),('native_score',AD.EN),('native_world',AD.WD),('native_ledger',AD.LG)):
        sources[name]=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
    from . import general_food as GF
    sources['general_food_policy']=digest({'policy':GF.policy(),'version':GF.VERSION})
    menu=Path(AD.__file__).parents[4]/'menu.csv'
    sources['menu_catalog']=hashlib.sha256(menu.read_bytes()).hexdigest()
    return {'version':VERSION,'research_source_commit':SOURCE_COMMIT,'source_sha256':sources,
            'general_food_policy':GF.policy(),'meal_minutes':240,'consistent_lookahead':True,'provider_calls':0,
            'shared_world_scheduler':'EARLIEST_NEXT_DECISION_STABLE_CUSTOMER_ID','capacity_and_queues_supported':False,
            'sha256':digest(sources),'execution_mode':'LIVE_RULES_COMPUTATION_NOT_SNAPSHOT_REPLAY'}

def fact_ids(value):
    found=set()
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if isinstance(k,str) and k.startswith(('A','F','P','B')) and any(c.isdigit() for c in k):found.add(k)
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
        elif isinstance(x,str) and len(x)<100 and x.replace('_','').replace('-','').isalnum() and any(c.isdigit() for c in x):found.add(x)
    walk(value);return found

def evidence_policy(known):
    # Reviewed mixed appraisal is bounded by its actual source ID. This is not
    # an assumption about every persona or a ban on a restaurant revisit.
    reviews={}
    if 'A08S_E29' in known:
        reviews['PIZZA_HILL']={'food_appraisal':'MIXED','space_appraisal':'POSITIVE','explicit_repeat_intention':False,
          'source_fact_ids':['A08S_E29'],'status':'SOURCE_ANCHORED_ANALYST_REVIEW_HUMAN_PENDING'}
    event={'programs_by_date':{},'direct_repeat_intention_verified':False,'direct_repeat_intention_fact_ids':[],
      'wine_affinity_fact_ids':[f for f in ('A08S_E23','A08S_E45','A08S_E73','A08S_E74','A08S_E76') if f in known],
      'meal_service_status':'TASTING_CONFIRMED_MEAL_PURCHASE_UNCONFIRMED',
      'reentry_policy_status':'CROSS_DATE_GUEST_ADMISSION; SAME_DAY_REENTRY_UNVERIFIED',
      'program_identity_status':'SINGLE_ENGINE_TEMPLATE_DATE_PROGRAM_DIFFERENCE_UNVERIFIED'}
    return reviews,event

def _new_stage(pid,scenario,inputs):
    if scenario.get('planner','rules') != 'rules':
        raise ValueError('M4_PAID_REASONER_DISABLED')
    known=fact_ids(inputs[0][pid]);reviews,event=evidence_policy(known)
    stage=M4Context('M4_LIVE',meal_state_enabled=True,consistent_lookahead=True,event_context=event,reviews=reviews)
    stage.known_fact_ids=known
    stage.events=copy.deepcopy(((scenario.get('visit_state') or {}).get(pid) or {}).get('m4_history') or [])
    stage.initial_event_count=len(stage.events)
    return stage

@contextmanager
def _step_scope(stage):
    original_pick=SP.pick
    def pick(rng,items,wfn,k=1,floor=.05):
        if not stage.plan:return original_pick(rng,items,wfn,k=k,floor=floor)
        candidates=list(items);weights={c:float(wfn(c)) for c in candidates}
        stage.preselect(stage.plan['agent'],candidates,weights)
        before=rng.getstate();chosen=original_pick(rng,candidates,wfn,k=k,floor=floor)
        record=stage.decisions[-1]
        actor=stage.plan['agent'];original_profile=actor.P
        for row in record['packet']['candidates']:
            code=row['candidate_id'];marginals={}
            try:
                for group in ('bars','facets'):
                    for trait,value in original_profile.get(group,{}).items():
                        if not isinstance(value,(int,float)):continue
                        neutral=copy.deepcopy(original_profile);neutral[group][trait]=.5;actor.P=neutral
                        marginals[group+'.'+trait]={'value':value,'neutral_reference':.5,
                            'weight_delta_at_fixed_state':round(weights[code]-float(wfn(code)),6),
                            'interpretation':'SINGLE_FEATURE_ABLATION_NOT_ADDITIVE_CAUSAL_EFFECT'}
                        actor.P=original_profile
            finally:actor.P=original_profile
            row['profile_feature_marginals']=marginals
            row['candidate_fact_ids']=list(original_profile.get('fact_hits',{}).get(code,[]))
        rejected=inspect.currentframe().f_back.f_locals.get('rej') or {}
        record['packet']['world_excluded_candidates']=[{'candidate_id':c,'reason':why} for c,why in rejected.items()]
        record['packet']['packet_sha256']=digest({k:v for k,v in record['packet'].items() if k!='packet_sha256'})
        record['selected_action']=str(chosen[0]) if chosen else None
        sample={c:max(floor,w) for c,w in weights.items()};total=sum(sample.values());preview=random.Random();preview.setstate(before)
        record['sampling']={'uniform':preview.random(),'candidate_order':candidates,'candidate_weights':sample,
                            'probabilities':{c:w/total for c,w in sample.items()},'mode':'NATIVE_WEIGHTED_SAMPLING'}
        return chosen
    with stage.install(),patch.object(SP,'pick',pick):
        yield

def _annotate(result,stage,pid,scenario,inputs):
    # Match a proposal to the actual next execution, not a similarly named
    # action somewhere else in the day. This never changes the execution.
    for record in stage.decisions:
        ctx=record['packet']['context_factors'];now=ctx['time']
        day_events=[e for e in stage.events[stage.initial_event_count:] if e['date']==ctx['date']]
        def hm(t):return int(t.split(':')[0])*60+int(t.split(':')[1])
        actual=next((e for e in day_events if hm(e['start'])<=now<hm(e['end'])),None)
        if actual is None:actual=next((e for e in day_events if hm(e['start'])>=now),None)
        record['actual_next_event_id']=actual['event_id'] if actual else None
        record['actual_next_action']=actual['action_id'] if actual else None
        record['execution_status']='EXECUTED' if actual and actual['action_id']==record['selected_action'] else 'INFORMATION_CHECK_NOT_ATTENDANCE' if actual and actual['action_id']==record['selected_action']+':check' else 'PROPOSAL_REPLACED_OR_NOT_EXECUTED'
    result['m4']={'date':scenario['date'],'configuration':configuration(),'decisions':stage.decisions,'activity_history':stage.events,
      'new_activity_count':len(stage.events)-stage.initial_event_count,'movement_history':stage.movements,
      'behavior_profile_sha256':digest(SP.profile(pid,inputs[0][pid],inputs[1].get(pid) or [],inputs[2])),
      'facts_traits_sha256':digest(inputs[0][pid]['traits']),
      'runtime_profile_sha256':digest({'persona':inputs[0][pid],'bars':inputs[1].get(pid),'library':inputs[2].get(pid)}),
      'fact_id_set_sha256':digest(sorted(stage.known_fact_ids)),'source_evidence_scope':'Approved runtime Fact IDs; observations versus inferred candidate contribution remain separate.',
      'provider_calls':0}
    return result


def run_one(pid,scenario,inputs):
    stage=_new_stage(pid,scenario,inputs)
    with _step_scope(stage):
        result=AD.run_one(pid,scenario,inputs)
    return _annotate(result,stage,pid,scenario,inputs)


def run_many(pids,scenario,inputs):
    """Live cooperative discrete-event simulation, not batched replay.

    Each native decision advances one agent to its next boundary. The queue
    then selects the earliest agent time again. Operations are shared; seats,
    reservations, queue waits and social interactions are not modeled. No
    capacity is invented and no customer's history or RNG is shared.
    """
    if not pids or len(pids)!=len(set(pids)):
        raise ValueError('M4_SHARED_WORLD_REQUIRES_UNIQUE_CUSTOMERS')
    if scenario.get('planner','rules')!='rules':
        raise ValueError('M4_PAID_REASONER_DISABLED')
    # Stable IDs resolve simultaneous decisions without API input-order bias.
    ids=sorted(pids);world=AD.World(scenario)
    agents={pid:AD.Agent(pid,*inputs,scenario) for pid in ids}
    stages={pid:_new_stage(pid,scenario,inputs) for pid in ids}
    live=set(ids);order=[]
    while live:
        pid=min(live,key=lambda k:(agents[k].t,k));a=agents[pid]
        if len(order)>=len(ids)*100 or a.steps>90:
            raise RuntimeError('M4_SHARED_WORLD_DECISION_LIMIT')
        t=a.t;before=len(a.log)
        operations={'levers':world.levers_at(t),'closed':world.closed_at(t)}
        with _step_scope(stages[pid]):
            progressed=AD.decide(a,world)
        order.append({'sequence':len(order),'customer_id':pid,'decision_minute':t,
            'decision_time':AD.mh(t),'next_decision_minute':a.t,
            'world_rules_sha256':digest(operations),'world_event_available':bool((operations['levers'].get('WINE_FAIR') or {}).get('available')),
            'activity_ids':[e['event_id'] for e in stages[pid].events[stages[pid].initial_event_count:] if e['start']>=AD.mh(t)],
            'new_log_entries':len(a.log)-before,'progressed':bool(progressed)})
        if not progressed or a.ended or a.left:live.remove(pid)
        elif a.t<=t:
            raise RuntimeError('M4_SHARED_WORLD_TIME_DID_NOT_ADVANCE')
    results={pid:_annotate(AD.finish(a),stages[pid],pid,scenario,inputs) for pid,a in agents.items()}
    # Exact intervals are derived from this live execution (not a second run).
    occupancy={}
    for pid,a in agents.items():
        for row in a.log:
            if row['act'] in ('move','wait','sleep','wake','arrive','leave') or row['e']<=row['t']:continue
            # Rooms with the same building code are private to each team.
            if row['loc'].endswith('_ROOM'):continue
            occupancy.setdefault(row['loc'],[]).append({'customer_id':pid,'start':row['t'],'end':row['e'],'action_id':row['act']})
    return {'personas':results,'shared_world':{
        'version':'m4-shared-world-v1','mode':'SHARED_WORLD_CHRONOLOGICAL','date':scenario['date'],
        'customer_ids':ids,'world_id':digest({'date':scenario['date'],'seed':scenario.get('seed',0),'rules':scenario.get('levers'),
            'changes':scenario.get('changes'),'closed':scenario.get('closed'),'configuration':configuration()['sha256']})[:24],
        'world_instance_count':1,'scheduler':'EARLIEST_NEXT_DECISION_STABLE_CUSTOMER_ID',
        'decision_order':order,'public_venue_intervals':occupancy,'completed_customer_ids':sorted(results),
        'capacity_and_queues_supported':False,'customer_interactions_supported':False,
        'scope':'공동 시간축·운영 조건 적용. 시설 정원·좌석·대기 경쟁·고객 상호작용은 미지원. 객실은 고객별 독립 공간.',
        'provider_calls':0}}
