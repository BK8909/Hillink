"""Visit meal continuity in an isolated research engine.

Fractions are native meal-equivalent templates, not measured consumption or
physiological fullness. Four-hour linear decay reuses the previous research
assumption; parameters are not fitted to A08's desired actions.
"""
from __future__ import annotations
from datetime import date

VERSION='w44-r01-meal-continuity-v1'
DECAY_MINUTES=240.0
EVENING_TARGET=1.0


def absolute_minute(day,time):
    return date.fromisoformat(day).toordinal()*1440+time


def meal_state(events, day, time, *, projected=(), extra_meal_reason=None, decay_minutes=DECAY_MINUTES):
    if decay_minutes<=0:raise ValueError("DECAY_MINUTES_MUST_BE_POSITIVE")
    now=absolute_minute(day,time)
    meals=[e for e in [*events,*projected] if e.get('meal_slot') and e.get('fraction',0)>0 and e['end_absolute']<=now]
    satiety_terms=[]
    for e in meals:
        elapsed=now-e['end_absolute']
        remaining=e['fraction']*max(0.0,1.0-elapsed/decay_minutes)
        if remaining:
            satiety_terms.append({'event_id':e['event_id'],'elapsed_minutes':elapsed,
                'meal_fraction_template':e['fraction'],'remaining_satiety_proxy':round(remaining,6),
                'projected':bool(e.get('projected'))})
    satiety=min(1.0,sum(e['remaining_satiety_proxy'] for e in satiety_terms))
    evening=[e for e in meals if e['date']==day and e['meal_slot']=='dinner']
    consumed=sum(e['fraction'] for e in evening)
    # Additional eating is permitted only by an explicit scenario/source
    # reason; never inferred merely because the last candidate is available.
    reason=extra_meal_reason or {}
    extra=0.0
    if reason and reason.get('evidence_status') not in ('SOURCE_ANCHORED','EXPLICIT_RESEARCH_SCENARIO'):
        raise ValueError('EXTRA_MEAL_REASON_UNVERIFIED')
    if reason.get('source_fact_ids') and reason.get('reason_kind') in ('EXPLICIT_SNACK_PREFERENCE','EXPLICIT_ACTIVITY_OR_SCHEDULE_NEED'):
        extra=float(reason.get('additional_meal_equivalent',0))
        if not 0<=extra<=1.0:raise ValueError('EXTRA_MEAL_EQUIVALENT_OUT_OF_SCOPE')
    remaining=max(0.0,EVENING_TARGET+extra-consumed)
    appetite=max(0.0,1.0-satiety)
    target=min(appetite,remaining)
    last=max(meals,key=lambda e:e['end_absolute']) if meals else None
    return {'version':VERSION,'satiety_proxy':round(satiety,6),'appetite_proxy':round(appetite,6),
        'evening_meal_equivalent_consumed':round(consumed,6),'remaining_evening_target':round(remaining,6),
        'current_meal_target_proxy':round(target,6),'last_meal_id':last['event_id'] if last else None,
        'minutes_since_last_meal_end':now-last['end_absolute'] if last else None,
        'satiety_terms':satiety_terms,'meal_event_ids':[e['event_id'] for e in meals],
        'extra_meal_reason':reason if extra else None,
        'assumptions':{'decay_minutes':decay_minutes,'evening_target':EVENING_TARGET,
                       'fraction_unit':'NATIVE_MEAL_EQUIVALENT_NOT_CALORIES_OR_OBSERVED_PORTION'},
        'status':'SIMULATED_ESTIMATE_NOT_OBSERVED_HUNGER',
        'native_hunger_counter_meaning':'REMAINING_EVENING_MEAL_NOT_A_TIME_VARYING_APPETITE'}


def meal_role(events,event):
    if not event.get('meal_slot'):return 'NOT_CONFIRMED_MEAL'
    if event.get('fraction',0)<=0:return 'MEAL_SKIPPED' if 'skip' in event.get('action_id','').lower() else 'NO_CONFIRMED_INTAKE'
    previous=[e for e in events if e['event_id']!=event['event_id'] and e['date']==event['date'] and
              e.get('meal_slot')==event['meal_slot'] and e['end_absolute']<=absolute_minute(event['date'],event['start_minute'])]
    if previous:return 'SUPPLEMENTAL_LATE_MEAL' if event['meal_slot']=='dinner' else 'SUPPLEMENTAL_MEAL'
    return 'LIGHT_MEAL' if event['fraction']<.8 else 'MAIN_MEAL'


def oversized_offer_adjustment(offer,state,meal_coefficient):
    # A light first course + full second meal may be justified, but native
    # credit for the remaining .5 must not pretend the second order is .5.
    if offer.get('kind') not in ('restaurant','room_meal','simple_meal'):
        return 0.0,[]
    fraction=offer['food']['meal_fraction']
    excess=max(0.0,fraction-state['current_meal_target_proxy'])
    if not excess:return 0.0,[]
    delta=-float(meal_coefficient)*excess
    return round(delta,6),[{'factor':'MEAL_PORTION_ABOVE_REMAINING_TARGET',
        'offer_fraction_template':fraction,'current_target_proxy':state['current_meal_target_proxy'],
        'excess_fraction_template':round(excess,6),'coefficient_source':'EXISTING_EN_W_MEAL',
        'coefficient':float(meal_coefficient),'delta':round(delta,6),
        'inference':'RESEARCH_FIT_COST_NOT_PHYSIOLOGICAL_FACT_OR_PRICE_CHANGE'}]


def projected_meal(offer,day,start,end):
    if offer.get('kind') not in ('restaurant','room_meal','simple_meal') or offer['food']['meal_fraction']<=0:
        return None
    slot='dinner' if start>=16*60+30 else 'lunch' if start>=11*60 else 'breakfast'
    return {'event_id':f"projected:{day}:{start}:{offer['id']}",'date':day,'start_minute':start,
            'end_absolute':absolute_minute(day,end),'meal_slot':slot,'fraction':offer['food']['meal_fraction'],
            'venue_id':offer['venue'],'menu_tags':offer['food'].get('menu_tags',[]),
            'projected':True,'kind':'LOOKAHEAD_NOT_EXECUTED'}


def catalog_intake_slot(offer, record):
    """Only an executed, charged/included food order establishes intake.

    Venue/SKU aliases are not action names in the legacy meal-slot table.
    Do not turn alcohol, a standalone drink, a proposal or a payment-only
    projection into a meal. Portion/decay assumptions remain unchanged.
    """
    if not offer.get('hc_contract') or offer.get('food',{}).get('meal_fraction',0)<=0:return None
    contract=offer.get('sku_contract') or {}
    charge=record.get('charge') or {}
    committed=charge.get('sku_contract') or {}
    if committed.get('sku_id')!=contract.get('sku_id') or charge.get('status') not in ('유료','포함','무료'):return None
    if not any(p.get('role') in ('MAIN','SNACK','BREAKFAST') for p in contract.get('components',[])):return None
    period=contract.get('service_period')
    return period if period in ('breakfast','lunch','dinner','snack') else None
