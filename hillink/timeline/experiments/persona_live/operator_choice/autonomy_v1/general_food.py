"""Opt-in pre-selection experiment. No inferred preferences or venue quotas.
A is the default. All numerical adjustments are model assumptions, not paper estimates.
"""
import os,json,hashlib
from pathlib import Path
from datetime import date
VERSION='GENERAL_FOOD_EXPERIMENT_V1'
SOURCES=json.loads(Path(__file__).with_name('general_food_sources.json').read_text())
def policy():
 p=os.environ.get('HILLINK_GENERAL_FOOD_POLICY','A')
 if p not in ('A','B','C'):raise ValueError('E_GENERAL_FOOD_POLICY')
 return p

def adjustment(offer,terms,context,*,existing_repeat=False,common_terms=()):
 p=policy();slot=offer.get('sku_contract',{}).get('service_period')
 if slot not in ('breakfast','lunch','dinner'):
  slot='breakfast' if context['time']<630 else 'lunch' if context['time']<960 else 'dinner'
 obs=context.get('food_observation',{});trace=dict(version=VERSION,policy=p,stage='BEFORE_SELECTION',slot=slot,applied=False,delta=0.,components=[],
  observation_status=obs.get('status','UNVERIFIED'),coefficient_origin='HILLINK_EXPERIMENT_ASSUMPTION_NOT_PAPER_ESTIMATE',
  source_ids=[],prior_event_ids=[],scope='ACTUAL_CURRENT_DECISION_ONLY_NO_LOOKAHEAD_PROJECTION')
 def stop(reason):trace['reason']=reason;return 0.,trace
 if p=='A':return stop('DEFAULT_POLICY_OFF')
 if offer.get('food',{}).get('meal_fraction',0)<.8:return stop('NOT_A_FULL_MEAL')
 if obs.get('status')!='UNOBSERVED_IN_ACCEPTED_INPUT':return stop('PERSONAL_FOOD_LINK_OR_UNRESOLVED_EVIDENCE_PROTECTED')
 if context.get('direct_avoid_venues',{}).get(offer.get('venue')) or any(t.get('fact_ids') and t.get('value',0)<0 for t in terms):
  return stop('SOURCE_LINKED_NEGATIVE_EVIDENCE_PROTECTED')
 # No confidence fabricated from counts. This attenuation is itself a model setting.
 indirect=bool(obs.get('indirect_fact_ids'));strength=.25 if indirect else .5
 trace['strength']=strength
 common_food=next((t for t in common_terms if t.get('factor')=='음식 경험'),None)
 # The existing 1.2 meal-fulfilment baseline is not counted twice. Only its
 # meal-time interaction changes; personal increments remain untouched.
 if common_food:
  baseline=max(0.,float(common_food['value']))
  rate={'breakfast':0.,'lunch':.05,'dinner':.10}[slot]
  delta=round(baseline*rate*strength,6)
  if delta:trace['components'].append(dict(factor='MEAL_TIME_HEDONIC_INTERACTION',delta=delta,base_existing_term=baseline,rate=rate,source_id='CADARIO_2022',coefficient_origin=trace['coefficient_origin'],interpretation='Adjustment of existing common meal term; not a second meal reward'))
 history=context.get('prior_meals',[])
 now=date.fromisoformat(context['date']).toordinal()*1440+context['time']
 recent=[m for m in history if m.get('fraction',0)>=.8 and 0<=now-m.get('end_absolute',now+1)<=2880]
 if p=='C' and slot!='breakfast' and recent:
  positive_repeat=any(t.get('facet')=='routine' and t.get('fact_ids') and t.get('value',0)>0 for t in terms)
  repeat_strength=strength*(.25 if positive_repeat else 1.)
  trace['repeat_strength']=repeat_strength
  if existing_repeat or context.get('explicit_repeat_reason'):trace['repeat_skip_reason']='EXISTING_REPEAT_ADJUSTMENT_OR_EXPLICIT_REPEAT_INTENTION'
  else:
   same=[m for m in recent if m.get('venue_id')==offer.get('venue')]
   tags=set(offer.get('food',{}).get('menu_tags',[]))-{'variety','course','standard'}
   overlap=[(len(tags&set(m.get('menu_tags',[])))/max(1,len(tags|set(m.get('menu_tags',[])))),m) for m in recent]
   similarity,prior=max(overlap,key=lambda z:z[0],default=(0,None))
   if same:
    trace['components'].append(dict(factor='REPEATED_VENUE_EXPERIMENT',delta=round(-.05*repeat_strength,6),source_id='PARK_2014',coefficient_origin=trace['coefficient_origin'],prior_event_ids=[m['event_id'] for m in same],limitation='2/6-week restaurant study extrapolated to 48-hour simulated stay; unvalidated'))
   if similarity and prior:
    trace['components'].append(dict(factor='REPEATED_FOOD_CATEGORY_EXPERIMENT',delta=round(-.15*similarity*repeat_strength,6),source_id='CADARIO_2022',coefficient_origin=trace['coefficient_origin'],similarity=similarity,prior_event_ids=[prior['event_id']],limitation='Menu tag similarity is not proof of identical dish or experienced satiation'))
 trace['delta']=round(sum(c['delta'] for c in trace['components']),6);trace['applied']=bool(trace['delta'])
 trace['source_ids']=sorted({c['source_id'] for c in trace['components']});trace['prior_event_ids']=sorted({i for c in trace['components'] for i in c.get('prior_event_ids',[])})
 trace['sources']=[s for s in SOURCES['sources'] if s['id'] in trace['source_ids']]
 trace['reason']='BOUNDED_EXPERIMENT' if trace['applied'] else 'NO_NON_DUPLICATED_APPLICABLE_TERM'
 return trace['delta'],trace

def planner_adjustment(code,context):
 from .agent_day import LUNCH_ENGINE
 if not code.startswith('lunch_') or code not in LUNCH_ENGINE:return 0.,None
 offer=dict(venue=LUNCH_ENGINE[code],food=dict(meal_fraction=.5 if code in ('lunch_cafe','lunch_bakery') else 1.,menu_tags=[]),sku_contract=dict(service_period='lunch'))
 delta,trace=adjustment(offer,[],context)
 trace['planner_boundary']='B common score not additively decomposed; no duplicate hedonic bonus. C venue memory only; menu not yet selected.'
 return delta,trace
