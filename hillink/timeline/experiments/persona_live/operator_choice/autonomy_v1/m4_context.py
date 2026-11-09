"""M4 live visit selection, ported from accepted research ae37786.

Installed only within one isolated /api/visit daily worker. No provider,
credential, replay fixture, price table, or source prose is loaded here.
"""
from __future__ import annotations
import copy,hashlib,inspect,json,random
from contextlib import contextmanager
from datetime import date
from . import agent_day as AD
from .food_evidence import observation,neutral_evidence,contribution
from . import general_food as GF
from . import hotel_prior as HP
from . import diag_repeat as DR
EN,SP=AD.EN,AD.SP
VERSION='m4-live-context-v1'
ASSUMPTIONS={'meal_gap_full_minutes':240,'minimum_gap_proxy':.3,'context_fit_unit_weight':1.0,'repeat_experience_discount':1.0}
REVIEWS={}
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=list).encode()).hexdigest()
class _Scope:
    @staticmethod
    @contextmanager
    def object(obj,name,value):
        previous=getattr(obj,name);setattr(obj,name,value)
        try:yield
        finally:setattr(obj,name,previous)
patch=_Scope()

def meal_gap_adjustment(code,context,*,full_minutes=None):
    if not code.startswith('lunch_') or context['minutes_since_meal_end'] is None:
        return 0.0,[]
    fraction=.0 if code=='lunch_skip' else .5 if code in ('lunch_cafe','lunch_bakery') else 1.0
    desired=min(1.0,max(ASSUMPTIONS['minimum_gap_proxy'],context['minutes_since_meal_end']/(full_minutes or ASSUMPTIONS['meal_gap_full_minutes'])))
    delta=-abs(fraction-desired)*ASSUMPTIONS['context_fit_unit_weight']
    return round(delta,6),[{'factor':'MEAL_GAP_PORTION_PROXY','candidate_meal_fraction':fraction,
        'target_fraction_proxy':desired,'delta':round(delta,6),'inference':'RESEARCH_ASSUMPTION_NOT_REPORTED_HUNGER'}]


def repeat_adjustment(offer,terms,context,reviews):
    previous=[m for m in context['prior_meals'] if m['venue_id']==offer['venue'] and m['fraction']>=.8]
    review=reviews.get(offer['id'],reviews.get(offer['venue'],{}))
    tags=set(offer['food'].get('menu_tags',[]))
    overlap=max((len(tags&set(m['menu_tags']))/max(1,len(tags|set(m['menu_tags']))) for m in previous),default=0)
    applies=(previous and offer['food']['meal_fraction']>=.8 and overlap>0 and
             review.get('food_appraisal') in ('MIXED','NEGATIVE') and
             not review.get('explicit_repeat_intention') and
             not context.get('explicit_repeat_reason'))
    if not applies:return 0.0,[]
    # Do not count the same menu/space discovery as a new experience when a
    # full comparable meal already happened and source appraisal is weak.
    duplicate=[t for t in terms if t.get('facet') in ('food_specific','space','routine') and t['value']>0]
    delta=-sum(t['value'] for t in duplicate)*ASSUMPTIONS['repeat_experience_discount']
    return round(delta,6),[{'factor':'CONDITIONAL_REPEATED_MEAL_EXPERIENCE_SATURATION',
         'delta':round(delta,6),'prior_meal_ids':[m['event_id'] for m in previous],
         'menu_similarity':overlap,'source_fact_ids':review['source_fact_ids'],
         'suppressed_native_terms':[{k:t.get(k) for k in ('factor','facet','value')} for t in duplicate],
         'inference':'CONDITIONAL_RESEARCH_CONTEXT_RULE_NOT_REVISIT_BAN',
         'counter_signal':'Prior view appraisal was positive; diminished discovery is an assumption, not observed aversion.'}]


class M4Context:
    def __init__(self,arm,reviews=None,*,meal_state_enabled=False,extra_meal_reason=None,meal_decay_minutes=240.0,consistent_lookahead=False,event_context=None):
        self.arm=arm;self.reviews=reviews if reviews is not None else REVIEWS
        self.events=[];self.movements=[];self.decisions=[];self.active=[];self.plan=None;self.known_fact_ids=set()
        self.meal_state_enabled=meal_state_enabled;self.extra_meal_reason=extra_meal_reason;self.projected=[]
        self.meal_decay_minutes=meal_decay_minutes;self.consistent_lookahead=consistent_lookahead;self.event_context=event_context
    def snapshot(self,a,t):
        d=a.sc['date'];now=date.fromisoformat(d).toordinal()*1440+t
        history=[e for e in self.events if e['end_absolute']<=now]
        meals=[e for e in history if e['meal_slot'] and e['fraction']>0]
        last=max(meals,key=lambda e:e['end_absolute']) if meals else None
        snapshot={'date':d,'time':t,'location_id':a.loc,'last_meal':last,
            'minutes_since_meal_end':now-last['end_absolute'] if last else None,
            'prior_meals':meals,'activities':[{k:e[k] for k in ('date','action_id','venue_id','start','end','kind')} for e in history[-12:]],
            'fatigue_proxy':a.fatigue,'next_known_deadline':a.visit_e.get('end'),
            'companions':{k:v for k,v in a.C.items() if isinstance(v,(bool,int,str))},
            'customer_id':a.pid,'food_observation':observation(a.traits),'profile_values':{'bars':copy.deepcopy(a.P['bars']),'facets':copy.deepcopy(a.P['facets'])},
            'explicit_repeat_reason':False,'reservation_or_benefit_repeat_reason':'NOT_PROVIDED_NOT_PROVEN_ABSENT',
            'inference_boundary':'elapsed time and fatigue are simulated state; hunger/mood are not observed facts'}
        if GF.policy()!='A':
            snapshot['direct_avoid_venues']={v:ids for v in AD.VENUE_KO if (ids:=a.avoid_facts(v))}
        if self.meal_state_enabled:
            from .m4_meal import meal_state
            snapshot['meal_state']=meal_state(self.events,d,t,extra_meal_reason=self.extra_meal_reason,decay_minutes=self.meal_decay_minutes)
        if self.event_context is not None:
            from .m4_event import event_memory
            snapshot['event_memory']=event_memory(self.events,d,t,self.event_context)
        return snapshot
    def packet(self,kind,context,candidates):
        p={'version':VERSION,'kind':kind,'context_factors':copy.deepcopy(context),'candidates':candidates,
           'source_evidence':{
            'A08S_E29':{'meaning':'Previous pizza/pasta meal, portions left over, mixed taste appraisal, view valued; no expressed next-day repeat wish.'},
            'A08S_E28':{'meaning':'Room-service noodle satisfaction and light healthy breakfast; tea and reading.'},
            'A08S_E46':{'meaning':'Wait accepted after ordering; next bus used. Not universal wait preference.'},
            'A08S_E53':{'meaning':'Last travel day alternative restaurant chosen to avoid queue; contextual.'}},
           'world_constraints':'Only supplied world_allowed candidates can be selected; suggestions outside them are rejected.',
           'model_version':VERSION}
        if self.event_context is not None:
            from .m4_event import VERSION as event_version
            p['model_version']=event_version
        p['source_evidence']={k:v for k,v in p['source_evidence'].items() if k in self.known_fact_ids}
        p['packet_sha256']=digest(p);return p
    def preselect(self,a,candidates,weights):
        if not self.plan:return None
        context=self.plan['context'];code_weights=self.plan['base_weights']
        rows=[]
        for code in candidates:
            delta,factors=meal_gap_adjustment(code,context,full_minutes=self.meal_decay_minutes if self.meal_state_enabled else None) if self.arm!='A' else (0,[])
            rows.append({'candidate_id':code,'base_score':code_weights[code],
                         'context_adjustment':delta,'context_factors':factors,
                         'final_score':weights[code],'world_allowed':True,
                         **({'general_food_evidence':GF.planner_adjustment(code,context)[1]} if GF.policy()!='A' else {}),
                         'duration_min':SP.ACT[code][3],
                         'travel_min':SP.travel_min(a.loc,SP.ACT[code][1](a.B)) if SP.ACT[code][1](a.B) else 0})
        packet=self.packet('PLANNER',context,rows);response=None
        record={'packet':packet,'llm_choice':response,'selection_phase':'BEFORE_SAMPLING',
                'selected_action':response['candidate_id'] if response else None}
        self.decisions.append(record)
        return None
    @contextmanager
    def install(self):
        original_add,original_plan,original_score,original_decide=AD.Agent.add,AD.plan_choose,EN.score,EN.decide_at
        original_feasible=EN.feasible
        original_plan_ok=AD.plan_ok
        stage=self
        def plan_ok(a,code,t,world,why_out,revisit=False):
            loc=original_plan_ok(a,code,t,world,why_out,revisit=revisit)
            if loc and stage.event_context is not None and a.stay and a.phase!='checkout':
                end=t+SP.travel_min(a.loc,loc)+SP.ACT[code][3]+SP.travel_min(loc,a.room)
                if end>a.end:
                    why_out[code]='RESEARCH_ACTIVITY_AND_ROOM_RETURN_EXCEED_DAY_END'
                    return None
            return loc
        def add(a,*args,**kwargs):
            # A zero-length sleep onset at the hard visit end is a marker,
            # not an invented 15 minutes of activity after the day ends.
            if stage.meal_state_enabled and len(args)>=6 and args[1]=='sleep':
                values=list(args);travel=SP.travel_min(a.loc,values[3]) if a.loc!=values[3] else 0
                values[5]=max(0,min(values[5],a.end-values[4]-travel));args=tuple(values)
            rec=original_add(a,*args,**kwargs)
            for move in a.log:
                if move['act']!='move':continue
                item={'date':a.sc['date'],'start':move['t'],'end':move['e'],
                      'from':move.get('loc_from'),'to':move['loc'],
                      'travel_min':move.get('internal',{}).get('travel_min')}
                if item not in stage.movements:stage.movements.append(item)
            if rec.get('act') in ('move','wait'):return rec
            offer=kwargs.get('offer') or {};slot=rec.get('meal_slot')
            if not slot and stage.meal_state_enabled:
                from .m4_meal import catalog_intake_slot
                slot=catalog_intake_slot(offer,rec)
                if slot:rec['meal_slot']=slot
            event_id=digest([a.pid,a.sc['date'],rec.get('t'),rec['act'],rec['loc']])[:20]
            existing=next((e for e in stage.events if e['event_id']==event_id),None)
            if existing is not None:
                if stage.meal_state_enabled:
                    existing['end']=rec['e'];existing['end_absolute']=date.fromisoformat(a.sc['date']).toordinal()*1440+AD.hm(rec['e'])
                return rec
            fraction=offer.get('food',{}).get('meal_fraction',.5 if slot and 'cafe' in rec['act'] or slot and 'bakery' in rec['act'] else 1.0 if slot and 'skip' not in rec['act'].lower() else 0)
            stage.events.append({'event_id':event_id,'date':a.sc['date'],'start':rec['t'],'end':rec['e'],
                'end_absolute':date.fromisoformat(a.sc['date']).toordinal()*1440+AD.hm(rec['e']),
                'action_id':rec['act'],'venue_id':offer.get('venue',rec['loc']) if offer.get('hc_contract') else rec['loc'],'location_id':rec['loc'],'kind':args[0] if args else kwargs.get('kind'),
                'meal_slot':slot,'fraction':fraction,'menu_tags':offer.get('food',{}).get('menu_tags',[]),
                'meal_inference':'native meal fraction or documented planner meal-class approximation'})
            if stage.meal_state_enabled:
                from .m4_meal import meal_role
                event=stage.events[-1];event['start_minute']=AD.hm(rec['t'])
                event['role']=meal_role(stage.events,event)
                event['intake_status']='SIMULATED_MEAL_NOT_REAL_OBSERVATION' if event.get('meal_slot') and event['fraction']>0 else 'UNCONFIRMED_OFFER_TEMPLATE_EXCLUDED_FROM_SATIETY' if event['fraction']>0 else 'NO_CONFIRMED_MEAL'
            return rec
        def plan(a,t,world,codes,wfn,domain_hint=None):
            ctx=stage.snapshot(a,t);base={c:float(wfn(c)) for c in codes}
            stage.plan={'context':ctx,'base_weights':base,'agent':a}
            def adjusted(c):
                delta,_=meal_gap_adjustment(c,ctx,full_minutes=stage.meal_decay_minutes if stage.meal_state_enabled else None) if stage.arm!='A' else (0,[])
                gd,_=GF.planner_adjustment(c,ctx) if GF.policy()!='A' else (0,None)
                return float(wfn(c))+delta+gd
            try:return original_plan(a,t,world,codes,adjusted,domain_hint)
            finally:stage.plan=None
        def feasible(o,t,state,visit):
            reasons=original_feasible(o,t,state,visit)
            if stage.meal_state_enabled and stage.active and not state.get('_depth',0):
                active=stage.active[-1];a=active.get('agent')
                if a is not None:
                    loc=AD.ENGINE_LOC.get(o['id'],a.loc)
                    loc=a.room if loc=='@room' else SP.pool(a.B) if loc=='@pool' else loc
                    start=t+SP.travel_min(a.loc,loc)
                    if o.get('window'):start=max(start,EN.hm(o['window']['start']))
                    deadline=EN.hm(visit['end'])
                    if o.get('window'):deadline=min(deadline,EN.hm(o['window']['end']))
                    if start+o['duration_min']>deadline:
                        reasons=list(reasons)+['RESEARCH_ACTUAL_ARRIVAL_EXCEEDS_EXISTING_TIME_LIMIT']
                    if stage.event_context is not None and a.stay and a.phase!='checkout' and start+o['duration_min']+SP.travel_min(loc,a.room)>a.end:
                        reasons=list(reasons)+['RESEARCH_ACTIVITY_AND_ROOM_RETURN_EXCEED_DAY_END']
            return reasons
        def score(o,t,state,visit,traits,world):
            terms=original_score(o,t,state,visit,traits,world)
            terms=DR.space_base_off(terms,EN.W)   # diagnostic switch, OFF unless HILLINK_DIAG_SPACE_BASE=off
            if o.get('price_reference'):   # external delivery: price compared at parity, not a payment amount
                terms=[dict(x,factor='점수 계산 가격(경쟁 호텔 저녁 최저가 · 가상 비교 기준)') if x['factor']=='1인 지불액' else x for x in terms]
            if stage.active:
                active=stage.active[-1];ctx=active['context']
                delta,factors=repeat_adjustment(o,terms,ctx,stage.reviews) if stage.arm!='A' else (0,[])
                diag_delta,diag_trace=DR.visit_memory(o,terms,ctx,traits,delta,ASSUMPTIONS['repeat_experience_discount'])   # OFF unless HILLINK_DIAG_VISIT_MEMORY=on
                if diag_trace:delta+=diag_delta;factors=list(factors)+[diag_trace]
                meal_terms=[]
                event_terms=[]
                if stage.event_context is not None and o['kind']=='event':
                    from .m4_event import event_adjustment
                    event_delta,event_trace=event_adjustment(o,terms,ctx.get('event_memory',{}))
                    delta+=event_delta
                    factors.append(event_trace)
                    if event_delta:
                        label='행사 입장과 미확인 식사 해결 점수 분리' if event_delta==event_trace['unconfirmed_meal_credit_delta'] else '행사 이력과 신규 경험 근거 구분'
                        event_terms=[EN._term(label,event_delta,kind='context',fact_ids=event_trace.get('source_fact_ids',[]))]
                if stage.meal_state_enabled:
                    from .m4_meal import meal_state,oversized_offer_adjustment
                    estimate=meal_state(stage.events,ctx['date'],t,projected=stage.projected,extra_meal_reason=stage.extra_meal_reason,decay_minutes=stage.meal_decay_minutes)
                    extra_delta,extra_factors=oversized_offer_adjustment(o,estimate,EN.W['meal'])
                    delta+=extra_delta;factors+=extra_factors
                    meal_terms=[EN._term('식사량과 현재 남은 끼니 추정의 차이',extra_delta,kind='context')] if extra_delta else []
                    if state.get('_depth',0) and extra_factors:
                        active.setdefault('meal_lookahead_trace',[]).append({'candidate_id':o['id'],'time':t,'depth':state['_depth'],
                            'projected_meal_ids':[m['event_id'] for m in stage.projected],
                            'meal_state':estimate,'base_score':round(sum(x['value'] for x in terms),6),
                            'context_adjustment':round(delta,6),'fit_factors':extra_factors,
                            'score_after_context':round(sum(x['value'] for x in terms)+delta,6),
                            'status':'HYPOTHETICAL_LOOKAHEAD_NOT_EXECUTED_OR_CHARGED'})
                hp,hpt=(0,None)
                if not state.get('_depth',0):
                    hp,hpt=HP.adjustment(o,terms,ctx,traits,EN.ev(traits,'practical_alt',{'room_meal':1.0,'alt_meal':0.5})[0] if o['id']==HP.TARGET_ACTION and HP.config() else 0)
                if not state.get('_depth',0):
                    common=original_score(o,t,state,visit,neutral_evidence(traits),world)
                    gd,gt=GF.adjustment(o,terms,ctx,existing_repeat=any(f.get('factor')=='CONDITIONAL_REPEATED_MEAL_EXPERIENCE_SATURATION' for f in factors),common_terms=common) if GF.policy()!='A' else (0,None)
                    active['scores'][o['id']]={'score_contribution':contribution(terms,common),'base_score':round(sum(x['value'] for x in terms),6),
                        'context_adjustment':delta,'context_factors':factors,'terms':copy.deepcopy(terms),**({'general_food_evidence':gt} if gt else {}),**({'hotel_prior':hpt} if hpt else {})}
                if delta:
                    repeat_delta=sum(x['delta'] for x in factors if x['factor']=='CONDITIONAL_REPEATED_MEAL_EXPERIENCE_SATURATION')
                    terms=list(terms)+([EN._term('체류 식사 경험의 조건부 중복 보상 조정',repeat_delta,kind='context',fact_ids=[f for x in factors for f in x.get('source_fact_ids',[])])] if repeat_delta else [])+meal_terms+event_terms
                if diag_delta:
                    terms=list(terms)+[EN._term('진단: 체류 중 같은 업장 재방문 발견가치 조정(개인 근거 없음)',diag_delta,kind='context')]
                if not state.get('_depth',0) and gd:
                    terms=list(terms)+[EN._term('일반 식사 행동 보완 · 실험 가정',gd,kind='general_research_assumption')]
                if hp:
                    terms=list(terms)+[EN._term('호텔 투숙객 일반 행동 사전정보(외부 배달) · 연구 가정',hp,kind='general_research_assumption')]
            return terms
        def decide(t,state,visit,traits,world):
            caller=inspect.currentframe().f_back.f_locals
            agent=caller.get('a')
            if state.get('_depth',0) or agent is None:
                if not stage.meal_state_enabled or not stage.active:return original_decide(t,state,visit,traits,world)
                from .m4_meal import meal_state,projected_meal
                offer=caller.get('o');projection=None
                if offer is not None:
                    projection=projected_meal(offer,stage.active[-1]['context']['date'],caller.get('st',t),t)
                if projection:stage.projected.append(projection)
                try:
                    estimate=meal_state(stage.events,stage.active[-1]['context']['date'],t,projected=stage.projected,extra_meal_reason=stage.extra_meal_reason,decay_minutes=stage.meal_decay_minutes)
                    result=original_decide(t,dict(state,hunger=estimate['current_meal_target_proxy']),visit,traits,world)
                    return dict(result,score_self=result['score'],score=result['total']) if stage.consistent_lookahead else result
                finally:
                    if projection:stage.projected.pop()
            actual=world is caller.get('w')
            ctx=stage.snapshot(agent,t);current={'context':ctx,'scores':{},'agent':agent};stage.active.append(current)
            if stage.meal_state_enabled:
                offers=[]
                for offer in world['offers']:
                    o=copy.deepcopy(offer)
                    if o['kind']=='rest':
                        loc=AD.ENGINE_LOC.get(o['id'],agent.loc);loc=agent.room if loc=='@room' else loc
                        arrival=t+SP.travel_min(agent.loc,loc)
                        if o.get('window'):arrival=max(arrival,EN.hm(o['window']['start']))
                        deadline=EN.hm(visit['end'])
                        if o.get('window'):deadline=min(deadline,EN.hm(o['window']['end']))
                        o['duration_min']=max(0,min(o['duration_min'],deadline-arrival))
                    offers.append(o)
                world=dict(world,offers=offers)
            world=DR.sku_cap(world)   # diagnostic switch, OFF unless HILLINK_DIAG_SKU_CAP is set
            choice_state=dict(state,hunger=ctx['meal_state']['current_meal_target_proxy']) if stage.meal_state_enabled else state
            if stage.meal_state_enabled:ctx['meal_state']['native_counter_before']=state['hunger']
            try:d=original_decide(t,choice_state,visit,traits,world)
            finally:stage.active.pop()
            if not actual:return d
            by={o['id']:o for o in world['offers']};allrows=[{'offer':d['chosen'],'label':d['label'],'major_reason':'not chosen by pre-action reasoner','feasible':True,'score':d['score'],'total':d['total'],'next':d['next_plan']}]+d['rejected']
            rows=[]
            for r in allrows:
                oid=r['offer'];s=current['scores'].get(oid,{})
                rows.append({'candidate_id':oid,'candidate_label':by[oid]['label'],'base_score':s.get('base_score'),
                    'context_adjustment':s.get('context_adjustment',0),'context_factors':s.get('context_factors',[]),
                    'final_score':r.get('score'),'final_with_lookahead':r.get('total'),'world_allowed':r['feasible'],
                    'next':r.get('next'),'duration_min':by[oid]['duration_min'],
                    'scoring_input_contract':copy.deepcopy(by[oid].get('scoring_input_contract')),
                    'score_contribution':copy.deepcopy(s.get('score_contribution')),
                    **({'general_food_evidence':copy.deepcopy(s['general_food_evidence'])} if s.get('general_food_evidence') else {}),
                    **({'hotel_prior':copy.deepcopy(s['hotel_prior'])} if s.get('hotel_prior') else {}),
                    'meal_fraction':by[oid]['food']['meal_fraction'],'menu_tags':by[oid]['food'].get('menu_tags',[]),
                    'travel_min':SP.travel_min(agent.loc,agent.room if AD.ENGINE_LOC.get(oid)=='@room' else SP.pool(agent.B) if oid=='POOL' else AD.ENGINE_LOC.get(oid,agent.loc)),
                    'terms':[{k:x.get(k) for k in ('factor','value','facet','kind','fact_ids')} for x in s.get('terms',[])],
                    'block_reason':r.get('major_reason') if not r['feasible'] else None,
                    **({'price_reference':copy.deepcopy(by[oid]['price_reference'])} if by[oid].get('price_reference') else {}),
                    **({'external_spend':copy.deepcopy(by[oid]['external_spend'])} if by[oid].get('external_spend') else {})})
            packet=stage.packet('QUANTITATIVE',ctx,rows)
            packet['catalog_excluded_candidates']=copy.deepcopy(world.get('hotel_catalog_exclusions',[]))
            if stage.consistent_lookahead:packet['lookahead_value_kind']='CHILD_TOTAL_SAME_AS_CHILD_SELECTION_OBJECTIVE'
            if stage.meal_state_enabled:
                packet['meal_lookahead_trace']=current.get('meal_lookahead_trace',[])
                packet['packet_sha256']=digest({k:v for k,v in packet.items() if k!='packet_sha256'})
            response=None
            stage.decisions.append({'packet':packet,'llm_choice':response,'selected_action':d['chosen'],
                'selection_phase':'BEFORE_AGENT_EXECUTION','decision_mode':'MAX_TOTAL_WITH_CONTEXT',
                'provisional_native_choice':allrows[0]['offer']})
            return d
        with patch.object(AD.Agent,'add',add),patch.object(AD,'plan_choose',plan),patch.object(AD,'plan_ok',plan_ok),patch.object(EN,'score',score),patch.object(EN,'decide_at',decide),patch.object(EN,'feasible',feasible):
            yield
