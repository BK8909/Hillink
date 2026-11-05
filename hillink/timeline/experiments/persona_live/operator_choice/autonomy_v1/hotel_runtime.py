"""Opt-in product/quantity adapter around C01. No BE01 chooser or LLM changes."""
import copy,random,re
from types import SimpleNamespace
from contextlib import contextmanager,ExitStack
from unittest.mock import patch
from . import m4_runtime as M4,hotel_catalog as H,facility_rules as FR,sauna_policy as SA
from .food_evidence import observation,neutral_evidence,contribution
AD=M4.AD;SP=AD.SP;EN=AD.EN
NATIVE_OK=AD.plan_ok
NATIVE_PLAN=AD.plan_do
FOOD={'PIZZA_HILL','MYONGWOLGWAN','GEUMRYONG','ONDAL','MOEGI','THE_BUFFET','ROOM_MEAL','LE_PASSAGE','THE_PAVILION','LUX_BAR'}
PLAN_VENUE={'lunch_pizzahill':'PIZZA_HILL','lunch_myongwol':'MYONGWOLGWAN','lunch_geumryong':'GEUMRYONG','lunch_ondal':'ONDAL','lunch_moegi':'MOEGI','lunch_buffet':'THE_BUFFET','lunch_room':'ROOM_MEAL','lunch_bakery':'LE_PASSAGE','lunch_cafe':'THE_PAVILION','bakery':'LE_PASSAGE','cafe':'THE_PAVILION','luxbar':'LUX_BAR','pool':'POOL','sauna':'SAUNA','footbath':'SKYARD','night_footbath':'SKYARD','forest_walk':'FOREST_PARK','riverpark':'RIVERPARK','theatre':'THEATRE_OF_LIGHT','hc_tennis':'TENNEZ_PARK','hc_golf':'GOLF_CLUB','hc_kidsclub':'KIDSCLUB','lounge':'DOUGLAS_LOUNGE'}
PROGRAMS={f'hc_program_{p["source_line"]}':p for p in H.DATA['products'] if p['venue_id']=='WALKEE'}
PLAN_VENUE.update({k:'WALKEE' for k in PROGRAMS})
def loc(a,venue):
 return a.room if venue=='ROOM_MEAL' else SP.pool(a.B) if venue=='POOL' else ('WELLNESS_SAUNA' if SA.facility(a)=='VISTA_SAUNA' else 'FITNESS') if venue=='SAUNA' else 'AG_GARDEN' if venue=='WALKEE' else venue

def plan_venue(a,code):
 from . import santa_2026 as S26
 p=S26.actor_package(a)
 return 'GRAND_CLUB_LOUNGE' if code=='lounge' and (a.B=='GRAND' or p and p['lounge']) else PLAN_VENUE[code]

def period(code,t):return 'breakfast' if code=='breakfast' else 'lunch' if str(code).startswith('lunch_') else 'snack' if code in ('bakery','cafe','luxbar') else 'dinner' if t>=960 else 'activity'

def dinner_venues():
 # Legacy cafe/bar exclusions must not hide explicitly catalogued dinner mains.
 # Undated snack/bar templates do not become dinner products by inference.
 explicit={p['venue_id'] for p in H.DATA['products'] if p['role']=='MAIN' and 'dinner' in (p.get('service_periods') or []) and p.get('automatic_choice',True)}
 return (FOOD-{'LE_PASSAGE','THE_PAVILION','LUX_BAR'}) | (explicit & FOOD)

def dinner_duration(venue):
 if venue in ('THE_PAVILION','LE_PASSAGE','LUX_BAR'):
  return SP.ACT[{'THE_PAVILION':'lunch_cafe','LE_PASSAGE':'lunch_bakery','LUX_BAR':'luxbar'}[venue]][3]
 return 120 if venue=='GEUMRYONG' else 90 if venue in {'MOEGI','MYONGWOLGWAN','THE_BUFFET','PIZZA_HILL'} else 60

def choice_attributes(contract):
 """Map existing sale metadata to scoring inputs, without inventing courses.

 Minimum quantity describes diners/units, never the number of dishes. Menu
 tags from a composed order must include its selected additional components.
 """
 parts=contract['components']
 tags=list(dict.fromkeys(tag for p in parts for tag in p.get('tags',[])))
 basket=contract.get('meal_basket') or {}
 tags=list(dict.fromkeys(tags+basket.get('source_composition_tags',[])))
 mains=[p for p in parts if p.get('role') not in ('DRINK','ADDON','CHILD_COMPONENT')]
 course=any('course' in p.get('tags',[]) or re.search(r'코스|오마카세|\bcourse\b|\bomakase\b',p.get('label',''),re.I) for p in mains)
 counts=[p['course_count'] for p in mains if isinstance(p.get('course_count'),int) and p['course_count']>0]
 return dict(menu_tags=tags,course_menu=course,courses=max(counts,default=1),basket_menu_diversity=bool(basket.get('menu_diversity')),
  course_count_known=bool(counts),attribute_source='EXISTING_COMPONENT_TAGS_AND_MENU_LABELS_NOT_MINIMUM_QUANTITY')

def offer(a,c,t,duration,world):
 venue=c['venue_id'];first=c['components'][0];v=loc(a,venue);food=venue in FOOD;t=max(t,c.get('candidate_available_at',t))
 template=next((o for o in world.get('_hc_templates',world['offers']) if (o['venue']==venue or o['id']==venue) and (not food or o.get('kind') in ('restaurant','room_meal','simple_meal'))),None)
 if template:o=copy.deepcopy(template)
 else:o=AD.WD.offer('HC_TEMP','product','room_meal' if venue=='ROOM_MEAL' else 'restaurant' if food and c['service_period'] not in ('snack','activity') else 'simple_meal' if food else 'wellness',venue,price=0,meal_fraction=1 if food else 0,quality='standard' if food else 'none')
 oid='HC_'+c['sku_id'];end=1260 if first.get('source_line') in (189,190,191) else max((b for a,b in H.sessions(first)),default=1440)
 discount=0 if c.get('hc_included') else c.get('discount_krw',0)
 o.update(id=oid,label=c['label'],venue=venue,duration_min=duration,available=True,price_pp_krw=(c['unit_price_krw']+discount)/a.N,in_package=False,guest_discount_krw=discount/a.N,card_benefit_krw=0,
  window=dict(start=AD.mh(t),end=AD.mh(min(end,1439))),sku_id=c['sku_id'],sku_contract=c,hc_contract=True,hc_included=c.get('hc_included',False))
 if c.get('hc_included'):o.update(in_package=True)
 if c.get('price_unknown'):o.update(price_pp_krw=None,price_status=c['price_status'])
 attrs=choice_attributes(c)
 fraction=(c.get('meal_basket') or {}).get('meal_fraction',1)
 o['food']=dict(o['food'],**attrs,menu_known=True,meal_fraction=.3 if first['role'] in ('SNACK','DRINK') else fraction if food else 0)
 o['scoring_input_contract']=dict(version='C01_SCORE_ATTRIBUTES_V3',**attrs,meal_basket=copy.deepcopy(c.get('meal_basket')),order_net_krw=c['unit_price_krw'],order_discount_krw=discount,participant_count=a.N,included=bool(c.get('hc_included')))
 AD.ENGINE_LOC[oid]=v;AD.ENGINE_DOMAIN[oid]='식사' if food else '웰니스';AD.VENUE_KO[oid]=c['label']
 o['service_contract']=dict(venue_id=venue,service_window=o['window'],candidate_available_at=t,planning_viability='AVAILABLE_NOW',
  reservation_state='VIRTUAL_RESERVATION_ASSUMPTION' if first.get('requires_reservation') else 'UNKNOWN_NOT_BOOKED',source_sha256=first['source_sha256'],price_status=c['price_status'],catalog_sha256=H.SHA)
 return o

def quote(a,venue,t,duration,slot,C):
 target=loc(a,venue);arrival=t+SP.travel_min(a.loc,target)
 # The collected facilities have canonical physical IDs; programs explicitly
 # reuse a modeled meeting point without asserting an official new facility.
 physical=target
 if venue=='SAUNA':
  fr=FR.block(a,'SAUNA')
  if fr:return [],[dict(venue_id=venue,reasons=[fr])]
  if not FR.sauna_hours_ok(arrival,duration):return [],[dict(venue_id=venue,reasons=['SERVICE_CLOSED_OR_INSUFFICIENT_TIME'])]
 elif physical in C.V.WALKERHILL_VENUE_WINDOWS:
  opts=H.options(a);ov=(opts.get('service_open_overrides') or {}).get(physical)
  check=C.service_check(physical,a.sc['date'],arrival,duration,open_override=AD.hm(ov) if ov else None)
  if not check['eligible']:
   lead=opts.get('dinner_plan_lead_min',45) if slot=='dinner' else 45   # research option: plan dinner further ahead (default 45 = unchanged)
   if slot in ('breakfast','dinner') and check['planning_viability']=='FUTURE_SERVICE_ONLY' and check['candidate_available_at']-arrival<=lead:arrival=check['candidate_available_at']
   else:return [],[dict(venue_id=venue,reasons=[check['blocked_reason']])]
 choices,excluded=H.orders(a,venue,arrival,duration,slot)
 choices=[H.entitlement(a,c) for c in choices]
 for c in choices:c['candidate_available_at']=arrival
 if venue=='SAUNA':
  choices=[c for c in choices if c['components'][0].get('facility_id')==SA.facility(a)]
  choices=FR.mark_unpriced(choices)   # Vista sauna without included use: price unknown, use kept
 # RIVERPARK per room/night use is a separate eligibility state, not weather closure.
 if venue=='RIVERPARK':
  prior=[e for e in a.visit_history.get('m4_history',[]) if e.get('date')==a.sc['date'] and e.get('venue_id')=='RIVERPARK']
  if prior:return [],excluded+[dict(venue_id=venue,reasons=['ROOM_NIGHT_RIVERPARK_ALREADY_USED'])]
 return choices,excluded

def choose(a,choices,t,duration,world):
 offers=[offer(a,c,t,duration,world) for c in choices];rows=[]
 for o in offers:
  unknown=o.get('price_pp_krw') is None   # unknown price: no money term + explicit uncertainty term (same contract as candidate_services.score)
  so=dict(o,price_pp_krw=0,guest_discount_krw=0,card_benefit_krw=0,in_package=False) if unknown else o
  terms=EN.score(so,t,dict(used=set(a.used),hunger=a.hunger_e),dict(a.visit_e,checkin=AD.mh(t)),a.traits,world)
  if unknown:terms=terms+[EN._term('가격 미확인 · 비용 비교 미평가',0,kind='uncertainty')]
  common=EN.score(so,t,dict(used=set(a.used),hunger=a.hunger_e),dict(a.visit_e,checkin=AD.mh(t)),neutral_evidence(a.traits),world)
  rows.append(dict(candidate_id=o['id'],sku_contract=o['sku_contract'],score=sum(x['value'] for x in terms),terms=terms,score_contribution=contribution(terms,common)))
 if not rows:return None,None
 scores={x['candidate_id']:x['score'] for x in rows}
 rng=random.Random(f'{a.rng_base}|HOTEL_PRODUCT|{a.sc["date"]}|{t}|{choices[0]["venue_id"]}')
 selected=SP.pick(rng,list(scores),lambda k:scores[k])[0]
 return next(x for x in offers if x['id']==selected),dict(food_observation=observation(a.traits),phase='AFTER_VENUE_BEFORE_EXECUTION',policy='EXISTING_NATIVE_PRODUCT_PICK_NO_COEFFICIENT_CHANGE',candidates=rows,selected=selected,catalog_sha256=H.SHA,quantity_is_model=True)

POST_VENUE_RULE_CHOOSE = choose  # Fulfillment stays a rule decision; no additional review/provider call.

@contextmanager
def install(C):
 original_init=AD.Agent.__init__
 def init(a,*args,**kw):
  original_init(a,*args,**kw)
  if H.enabled(a):
   room=H.BY.get(H.options(a).get('room_products',{}).get(a.pid,''),{})
   if a.B=='GRAND' and '클럽 라운지' in room.get('included_description',''):
    a.club=True;a.vs['club']=True;a.vs['club_source']='OPERATOR_SELECTED_CATALOG_PACKAGE'
 original_for=AD.engine_world_for;original_charge=AD.LG.charge;original_ok=AD.plan_ok;original_plan=AD.plan_do;original_bf=AD.breakfast_step;original_finish=AD.finish
 def finish(a):
  if H.enabled(a):
   scopes=set()
   for order in H.options(a).get('purchase_orders',{}).get(a.pid,[]):
    if order['date']!=a.sc['date'] or order['venue_id'] not in ('PARKING','VALET'):continue
    if order['service_period']!='booking':raise ValueError('ANCILLARY_BOOKING_PERIOD_REQUIRED')
    key=(order['date'],order['venue_id'])
    if key in scopes:raise ValueError('DUPLICATE_ANCILLARY_ORDER')
    scopes.add(key);parts=[]
    for item in order['items']:
     p=H.BY[item['sku_id']];part=H.component(p,item['quantity'],a,assumption='EXPLICIT_OPERATOR_ANCILLARY_QUANTITY_NOT_PERSON_COUNT')
     if p['sku_id']=='HC-MENU-255':
      if not any(x.get('loc')=='THEATRE_OF_LIGHT' for x in a.log) and p['sku_id'] not in H.options(a).get('virtual_reservations',{}).get(a.pid,[]):raise ValueError('PARKING_EXHIBITION_TICKET_QUALIFICATION_REQUIRED')
      part['billing_unit']='initial_three_hour_block'
     if p['sku_id']=='HC-SRC-GRAND-PARKING-EXTRA' and a.stay and not a.checked_out:
      part.update(unit_price_krw=0,discount_krw=0,included_benefit='SOURCE_PARKING_DURING_ROOM_STAY')
     if order['venue_id']=='VALET' and a.B=='DOUGLAS' and a.stay and not a.visit_history.get('hotel_entitlement_usage',{}).get('DOUGLAS_ONE_VALET'):
      free=dict(part,billing_quantity=1,unit_price_krw=0,discount_krw=0,included_benefit='DOUGLAS_ONE_VALET');parts.append(free);part['billing_quantity']-=1
     if part['billing_quantity']:parts.append(part)
    c=H.compose(parts,a,'booking')
    if order['venue_id']=='VALET' and a.B=='DOUGLAS' and a.stay:c['hotel_entitlement_key']='DOUGLAS_ONE_VALET'
    o=dict(id='HC_'+c['sku_id'],label=c['label'],venue=c['venue_id'],sku_contract=c,hc_contract=True)
    a.add('purchase',o['id'],o['label'],a.loc,min(a.t,1439),0,'부가서비스','explicit_operator_order','운영자가 명시한 부가서비스 주문 · 이동/음식 섭취를 만들지 않습니다.',[],dict(fulfillment='EXPLICIT_ANCILLARY_BOOKING',sku_contract=c),offer=o)
  return original_finish(a)
 from ..operator_world_v1_1 import turn_candidate as TC
 original_turn=TC.turn_world;bf_stack=[]
 def for_actor(a,world,t):
  LEAD[0]=H.options(a).get('dinner_plan_lead_min') if H.enabled(a) else None   # read by the feasibility wrapper for this decision
  w=original_for(a,world,t)
  if not H.enabled(a):return w
  # Full catalog supplies real eligible products; old aggregate venue prices
  # are not extra meals competing with their SKU equivalents.
  w['_hc_templates']=w['offers']
  w['offers']=[o for o in w['offers'] if o['venue'] not in FOOD or o.get('kind') not in ('restaurant','room_meal','simple_meal') or o['id']=='SKIP_BREAKFAST']
  exclusions=list(w.get('hotel_catalog_exclusions',[]))
  if t>=930:
   for venue in sorted(dinner_venues()):
    dur=(H.options(a).get('research_dinner_duration_min') or {}).get(venue) or dinner_duration(venue)   # research sensitivity (default = model length)
    choices,excluded=quote(a,venue,t,dur,'dinner',C);exclusions.extend(excluded)
    if venue in {'LE_PASSAGE','THE_PAVILION','LUX_BAR'}:
     explicit=[]
     for c in choices:
      if any(p.get('role')=='MAIN' and 'dinner' in (p.get('service_periods') or []) for p in c['components']):explicit.append(c)
      else:exclusions.append(dict(venue_id=venue,sku_id=c['sku_id'],reasons=['DINNER_MAIN_SERVICE_NOT_EXPLICIT']))
     choices=explicit
    arrival=t+SP.travel_min(a.loc,loc(a,venue))
    for c in choices:
     o=offer(a,c,arrival,dur,w)
     # Catalog additions must pass the same physical-place and post-meal gate
     # as native candidates. A different SKU is not a new meal entitlement.
     reasons=AD.meal_revisit_reasons(a,t,loc(a,venue)) if venue in FOOD and o.get('food',{}).get('meal_fraction',0)>0 else []
     if reasons:
      exclusions.append(AD.meal_exclusion(a,t,loc(a,venue),venue,reasons,o['id'],c['sku_id']))
      continue
     if AD._engine_closure_interval(a,world,t,o):o.update(available=False,status='OPERATOR_CLOSURE')
     w['offers'].append(o)
  for old in list(w['offers']):
   venue={'POOL':'POOL','SAUNA':'SAUNA','SKYARD':'SKYARD','SKYARD_NIGHT':'SKYARD'}.get(old['id'])
   if not venue:continue
   choices,excluded=quote(a,venue,t,old['duration_min'],'activity',C);exclusions.extend(excluded)
   w['offers'].remove(old)
   for c in choices:
    o=offer(a,c,t+SP.travel_min(a.loc,loc(a,venue)),old['duration_min'],w)
    if not any(x['id']==o['id'] for x in w['offers']):w['offers'].append(o)
  w['hotel_catalog_exclusions']=exclusions
  # External delivery keeps its scoring-only price parity with the hotel dinners actually offered now (catalog SKUs).
  for d in [o for o in w['offers'] if o['id']==AD.DELIVERY_ID]:
   w['offers'].remove(d);d=AD.delivery_parity({k:v for k,v in d.items() if k!='price_reference'},[o for o in w['offers'] if o.get('hc_contract') and o['venue'] in FOOD])
   if d is not None:w['offers'].append(d)
   else:exclusions.append(dict(venue_id=AD.DELIVERY_ID,reasons=[AD.DELIVERY_NO_REFERENCE]))
  return w
 def plan_ok(a,code,t,world,why_out,revisit=False):
  if not H.enabled(a) and code.startswith('hc_'):why_out[code]='CATALOG_POLICY_NOT_ENABLED';return None
  if not H.enabled(a) or code not in PLAN_VENUE:return original_ok(a,code,t,world,why_out,revisit)
  # Existing activity/repeat/check-out rules remain; only obsolete fixed-SKU
  # checks and October-only river closure are superseded by dated catalog data.
  ctx=patch.dict(AD.SEASON_CLOSED,{},clear=True) if code=='riverpark' else patch.dict(AD.SEASON_CLOSED,{})
  with ctx,patch.dict(AD.NOT_ELIGIBLE,{},clear=code=='lounge'):result=NATIVE_OK(a,code,t,world,why_out,revisit)
  if not result:return None
  if code=='sauna':result=loc(a,'SAUNA')
  dur=SP.ACT[code][3];choices,excluded=quote(a,plan_venue(a,code),t,dur,period(code,t),C)
  if code in PROGRAMS:choices=[c for c in choices if c['components'][0]['sku_id']==PROGRAMS[code]['sku_id']]
  if not choices:why_out[code]='HC_NO_ELIGIBLE_PRODUCT:'+','.join(sorted({r for x in excluded for r in x['reasons']}));return None
  return result
 def plan_do(a,code,target,t,weights,rej,source='planner_rules',note=None):
  if not H.enabled(a) or code not in PLAN_VENUE:return original_plan(a,code,target,t,weights,rej,source,note)
  if code=='sauna':target=loc(a,'SAUNA')
  choices,excluded=quote(a,plan_venue(a,code),t,SP.ACT[code][3],period(code,t),C)
  if code in PROGRAMS:choices=[c for c in choices if c['components'][0]['sku_id']==PROGRAMS[code]['sku_id']]
  o,trace=choose(a,choices,t+SP.travel_min(a.loc,target),SP.ACT[code][3],world=AD.World(a.sc).engine_world(t))
  if o is None:raise ValueError('HC_EXECUTION_WITHOUT_ELIGIBLE_ORDER')
  original_add=AD.Agent.add
  def add(actor,*args,**kw):
   if actor is a and len(args)>1 and args[1]==code:
    args=list(args);args[2]=o['label'];kw['offer']=o
    if len(args)>10:args[10]=dict(args[10] or {},hotel_product_decision=trace)
    else:kw['internal']=dict(kw.get('internal') or {},hotel_product_decision=trace)
   return original_add(actor,*args,**kw)
  with patch.object(AD.Agent,'add',add):return NATIVE_PLAN(a,code,target,t,weights,rej,source,note)
 LEAD=[None];original_feasible=AD.EN.feasible
 def feasible(o,t,state,visit):
  # Research option (default off): a dinner restaurant may be planned up to LEAD minutes before it opens (wait costed as usual).
  if LEAD[0] and t>=900 and o.get('kind') in ('restaurant','room_meal','simple_meal'):
   with patch.dict(AD.EN.POLICY,{'meal_lead_min':max(LEAD[0],AD.EN.POLICY['meal_lead_min'])}):return original_feasible(o,t,state,visit)
  return original_feasible(o,t,state,visit)
 def charge(a,code,kind,target,offer=None,in_package=False):
  if H.enabled(a) and code=='tennez' and offer is None:return dict(status='구매 없음',krw=0,basis='테니스 시설 둘러보기 · 코트 예약/플레이 구매 아님')
  if (offer or {}).get('hc_contract'):
   out=H.charge(offer['sku_contract'],included=offer.get('hc_included',False))
   key=offer['sku_contract'].get('hotel_entitlement_key')
   if key:
    out['hotel_entitlement_key']=key;a.visit_history.setdefault('hotel_entitlement_usage',{})[key]=1
   return out
  return original_charge(a,code,kind,target,offer,in_package)
 def breakfast(a,world,t):
  if not H.enabled(a):return original_bf(a,world,t)
  bf_stack.append(a)
  original_add=AD.Agent.add
  def breakfast_add(actor,*args,**kw):
   selected=kw.get('offer') or {}
   if actor is a and selected.get('hc_contract'):
    kw['start_at']=max(t,AD.hm(selected['window']['start'])) if selected.get('window') else t
   return original_add(actor,*args,**kw)
  try:
   from . import breakfast_policy as BP
   # V1: the room contract / package override decides (agent_day); LEGACY: every staying guest included (previous policy).
   own=copy.copy(world);own.sc=dict(world.sc) if BP.policy(world.sc) in BP.CONTRACT_POLICIES else dict(world.sc,breakfast_in_package=bool(a.stay and a.checked_in and not a.checked_out))
   with patch.object(AD.Agent,'add',breakfast_add):return original_bf(a,own,t)
  finally:bf_stack.pop()
 def covered_breakfast(a,c,covered):
  # Breakfast-included room: contracted adults at 0 (included benefit), every other diner keeps the composed price.
  parts=[];left=covered
  for p in c['components']:
   if left and p.get('role')=='MAIN' and p['billing_quantity']>0:
    k=min(left,p['billing_quantity']);left-=k
    inc=copy.deepcopy(p);inc.update(billing_quantity=k,original_list_unit_price_krw=p['unit_price_krw'],unit_price_krw=0,included_benefit='ROOM_BREAKFAST_INCLUDED_CONTRACT',price_status='ROOM_CONTRACT_INCLUDED_NOT_NEW_SALE');parts.append(inc)
    if p['billing_quantity']-k:parts.append(dict(copy.deepcopy(p),billing_quantity=p['billing_quantity']-k))
   else:parts.append(copy.deepcopy(p))
  out=H.compose(parts,a,'breakfast');out['candidate_available_at']=c.get('candidate_available_at');out['room_breakfast_contract']=dict(covered_adults=covered)
  return out
 def turn_world(*args,**kw):
  w,excluded=original_turn(*args,**kw)
  if not bf_stack or (args[0] if args else kw.get('turn'))!='breakfast':return w,excluded
  a=bf_stack[-1];t=a.t;choices,_=quote(a,'THE_BUFFET',t,60,'breakfast',C)
  for o in w['offers']:
   if o['id']=='BREAKFAST_BUFFET' and choices:
    from . import breakfast_policy as BP
    c=choices[0]
    if BP.policy(a.sc) in BP.CONTRACT_POLICIES:
     inc=bool(o.get('in_package'))   # lever set by agent_day from the room contract or a package override
     if not inc and BP.covered_adults(a):c=covered_breakfast(a,c,BP.covered_adults(a))
    else:inc=a.stay
    o.update(available=True,window=dict(start=AD.mh(c['candidate_available_at']),end=AD.mh(c['candidate_available_at']+60)),sku_contract=c,hc_contract=True,hc_included=inc,price_pp_krw=0 if inc else c['unit_price_krw']/a.N,in_package=inc)
   elif o['id']=='BREAKFAST_BUFFET' and not choices:o.update(available=False,status='NO_ELIGIBLE_BREAKFAST_SERVICE')
   elif o['id'].startswith('RS_'):
    if a.pid not in H.options(a).get('paid_breakfast_ird_customers',[]):o.update(available=False,status='PAID_IRD_REQUIRES_EXPLICIT_SCENARIO_OPT_IN')
    else:
     p=next((p for p in H.DATA['products'] if p.get('native_product_id')==o['id']),None)
     if p:
      c=H.compose([H.component(p,a.N,a)],a,'breakfast');o.update(hc_contract=True,sku_contract=c,price_pp_krw=c['unit_price_krw']/a.N,in_package=False)
  return w,excluded
 with ExitStack() as stack:
  for obj,key,value in [(AD.EN,'feasible',feasible),(AD.Agent,'__init__',init),(AD,'finish',finish),(AD,'engine_world_for',for_actor),(AD.LG,'charge',charge),(AD,'plan_ok',plan_ok),(AD,'plan_do',plan_do),(AD,'breakfast_step',breakfast),(TC,'turn_world',turn_world)]:stack.enter_context(patch.object(obj,key,value))
  for mapping in (AD.ENGINE_LOC,AD.ENGINE_DOMAIN,AD.VENUE_KO):stack.enter_context(patch.dict(mapping,{}))
  # A golf POI already exists in the world; reuse the native sports activity
  # class for planning. No new personal score coefficient is introduced.
  stack.enter_context(patch.dict(SP.ACT,{'hc_golf':('실내 골프',lambda b:'GOLF_CLUB','wellness',60,True,True),'hc_kidsclub':('키즈클럽',lambda b:'KIDSCLUB','culture',120,False,True),'hc_tennis':('테니스 60분 · 시간 단위 가정',lambda b:'TENNEZ_PARK','outdoor',60,False,True)}))
  program_actions={}
  for code,p in PROGRAMS.items():
   dur=H.sessions(p)[0][1]-H.sessions(p)[0][0]
   program_actions[code]=(p['label'],lambda b:'AG_GARDEN','wellness' if '요가' in p['label'] else 'outdoor',dur,False,True)
  stack.enter_context(patch.dict(SP.ACT,program_actions))
  native_weight=SP.act_weight
  def act_weight(code,*args,**kw):
   alias='tennez' if code in ('hc_golf','hc_tennis') else 'theatre' if code=='hc_kidsclub' else 'fitness' if code in PROGRAMS and '요가' in PROGRAMS[code]['label'] else 'forest_walk' if code in PROGRAMS else code
   if alias!=code:
    args=list(args);args[0]=copy.deepcopy(args[0])
    for k in ('fact_hits','daily_hits'):args[0].get(k,{}).pop(alias,None)
   return native_weight(alias,*args,**kw)
  stack.enter_context(patch.object(SP,'act_weight',act_weight))
  stack.enter_context(patch.object(AD,'LEISURE',AD.LEISURE+['hc_golf','hc_tennis','hc_kidsclub']+list(PROGRAMS)))
  yield
