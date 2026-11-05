"""Visit event audit; observation and repeat inference stay separate."""
from __future__ import annotations
from datetime import date

VERSION='w44-r01-event-context-v1'


def event_memory(events,day,time,policy):
    now=date.fromisoformat(day).toordinal()*1440+time
    past=[e for e in events if e['end_absolute']<=now and e['action_id'].split(':')[0]=='WINE_FAIR']
    attended=[e for e in past if e['action_id']=='WINE_FAIR']
    checks=[e for e in past if e['action_id'].endswith(':check')]
    programs=policy.get('programs_by_date',{})
    current=programs.get(day,{})
    distinct=(bool(attended) and current.get('verified') is True and all(
        programs.get(e['date'],{}).get('verified') is True and
        programs[e['date']].get('program_id')!=current.get('program_id') for e in attended))
    return {'version':VERSION,'prior_attendance':[{k:e.get(k) for k in ('event_id','date','start','end','venue_id','action_id')} for e in attended],
        'prior_information_checks':[{k:e.get(k) for k in ('event_id','date','start','end','action_id')} for e in checks],
        'program_relation':'VERIFIED_DIFFERENT_PROGRAM' if distinct else 'SAME_ENGINE_TEMPLATE_ACTUAL_PROGRAM_DIFFERENCE_UNVERIFIED' if attended else 'FIRST_ATTENDANCE',
        'direct_repeat_intention_fact_ids':policy.get('direct_repeat_intention_fact_ids',[]) if policy.get('direct_repeat_intention_verified') is True else [],
        'meal_service_status':policy.get('meal_service_status','UNVERIFIED'),
        'wine_affinity_fact_ids':policy.get('wine_affinity_fact_ids',[]),
        'real_event_attendance_observed_fact_ids':[],
        'reentry_policy_status':policy.get('reentry_policy_status','UNKNOWN'),
        'different_program_not_invented':True}


def event_adjustment(offer,terms,memory):
    repeat_terms=[t for t in terms if t.get('factor')=='방문 내 행사 재참여 조정(설계 가정)']
    inherited=sum(t['value'] for t in repeat_terms)
    prior=memory.get('prior_attendance',[])
    strong_reason=(memory.get('program_relation')=='VERIFIED_DIFFERENT_PROGRAM' or bool(memory.get('direct_repeat_intention_fact_ids')))
    discovery=[t for t in terms if t.get('facet') in ('novelty','seasonal','promo') and t['value']>0]
    # Existing soft repeat cost is retained unless specific evidence changes
    # the repeat interpretation. Wine enjoyment and scenery stay rewarded.
    restored=-inherited if prior and strong_reason else 0
    removed=sum(t['value'] for t in discovery) if prior and not strong_reason else 0
    # Admission/tasting is not a paid meal or evidence that a meal is supplied.
    # Retain culinary interest, but remove the inherited meal-solving credit
    # only under this explicitly checked event-service contract.
    meal_credit=sum(t['value'] for t in terms if t.get('factor')=='저녁 끼니 해결' and t['value']>0) if memory.get('meal_service_status')=='TASTING_CONFIRMED_MEAL_PURCHASE_UNCONFIRMED' else 0
    delta=restored-removed-meal_credit
    return round(delta,6),{'factor':'EVENT_ATTENDANCE_MEMORY_AND_EVIDENCE_SCOPE','delta':round(delta,6),
        'prior_attendance_event_ids':[e['event_id'] for e in prior],
        'inherited_repeat_delta':inherited,'restored_specific_reason_delta':restored,
        'unsupported_fresh_discovery_delta':-removed,
        'unconfirmed_meal_credit_delta':-meal_credit,
        'meal_service_status':memory.get('meal_service_status'),
        'program_relation':memory.get('program_relation'),
        'source_fact_ids':memory.get('direct_repeat_intention_fact_ids',[]),
        'wine_affinity_is_not_observed_event_attendance':True,
        'venue_familiarity_is_not_event_repeat_intention':True,
        'reentry_policy_status':memory.get('reentry_policy_status'),
        'repeat_is_not_world_blocked':True}
