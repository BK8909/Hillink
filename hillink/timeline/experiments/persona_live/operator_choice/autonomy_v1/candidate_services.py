"""C01 service-window adapter. No preference changes, bookings or price imports.

Explicit m4_c01 execution preserves m4/legacy and their frozen demonstrations.
Official collected windows retain calendar predicates instead of unioning all
historical sessions. New venue-only choices have null prices, never free SKUs.
"""
from __future__ import annotations
import os as _v12z_os
_V12Z_COMMON = _v12z_os.environ.get('HILLINK_V12Z_COMMON') == '1'
import copy
import hashlib
from contextlib import ExitStack, contextmanager
from datetime import date, time
from pathlib import Path
from unittest.mock import patch
from . import m4_runtime as M4
from . import candidate_products as PRODUCTS
from . import menu_connections as MEALS
from . import lunch_products as LUNCH_PRODUCTS
from . import party_orders as PO
from . import hotel_catalog as HC, hotel_runtime as HR
from . import facility_rules as FR
AD=M4.AD
SP=AD.SP
EN=AD.EN
import walkerhill_timeline_validator as V
from ..operator_world_v1_1 import turn_candidate as TC

VERSION='m4-c01-service-windows-v2-party-orders'
OFFICIAL_DINNER={
 'MOEGI':('18:00','21:00','https://www.walkerhill.com/vistawalkerhillseoul/dining/MOEGI'),
 'MYONGWOLGWAN':('17:30','21:00','https://www.walkerhill.com/vistawalkerhillseoul/dining/Myongwolgwan'),
 'GEUMRYONG':('18:00','21:00','https://www.walkerhill.com/grandwalkerhillseoul/dining/Geumryong'),
 'ONDAL':('18:00','21:00','https://www.walkerhill.com/dining/Ondal'),
}

def configuration():
 c=copy.deepcopy(M4.configuration())
 c['version']=VERSION
 c['source_sha256']['hotel_catalog']=HC.SHA
 c['source_sha256']['hotel_runtime']=hashlib.sha256(Path(HR.__file__).read_bytes()).hexdigest()
 c['source_sha256']['hotel_contract']=hashlib.sha256(Path(HC.__file__).read_bytes()).hexdigest()
 c['source_sha256']['party_orders']=hashlib.sha256(Path(PO.__file__).read_bytes()).hexdigest()
 c['source_sha256']['menu_connections']=hashlib.sha256(Path(MEALS.__file__).read_bytes()).hexdigest()
 c['source_sha256']['user_product_confirmations']=MEALS.CONFIRMATION_SHA
 c['source_sha256']['lunch_products']=hashlib.sha256(Path(LUNCH_PRODUCTS.__file__).read_bytes()).hexdigest()
 c['source_sha256']['candidate_products']=hashlib.sha256(Path(PRODUCTS.__file__).read_bytes()).hexdigest()
 c['source_sha256']['product_menu_source']=hashlib.sha256(PRODUCTS.MENU.read_bytes()).hexdigest()
 c['source_sha256']['product_operating_source']=hashlib.sha256(PRODUCTS.SOURCE.read_bytes()).hexdigest()
 c['source_sha256']['candidate_services']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 c['source_sha256']['dated_windows']=hashlib.sha256(Path(V.__file__).read_bytes()).hexdigest()
 c['sha256']=M4.digest(c['source_sha256'])
 c['promotion_status']='EXPLICIT_API_CANDIDATE_NOT_DEFAULT'
 return c

def windows(venue,day,action=None):
 """Use source calendar/state predicates, not a union of years and sessions."""
 d=date.fromisoformat(day)
 raw=V.WALKERHILL_VENUE_WINDOWS.get(venue,())
 if venue=='DOUGLAS_LOUNGE':raw=(V.VenueWindow(time(7),time(22)),)
 if venue=='DOUGLAS_LIBRARY':raw=(V.VenueWindow(time(0),time(23,59)),)
 scoped=[w for w in raw if w.states and action in w.states]
 chosen=scoped or [w for w in raw if not w.states]
 return [w for w in chosen if w.opens_on(d)]

def service_check(venue,day,minute,duration=0,action=None,open_override=None):
 ws=windows(venue,day,action)
 def mins(x):return x.hour*60+x.minute
 rows=[{'from':min(mins(w.open_at),open_override) if open_override is not None and mins(w.open_at)>=16*60 else mins(w.open_at),'open_override':open_override if open_override is not None and mins(w.open_at)>=16*60 else None,'until':mins(w.close_at),
        'last_order':mins(w.last_order) if w.last_order else None,
        'source_state':str(w.source),'source':'timeline/walkerhill_timeline_validator.py'} for w in ws]
 if not rows:
  return {'eligible':False,'planning_viability':'UNKNOWN_OR_NO_APPLICABLE_SESSION',
          'blocked_reason':'NO_APPLICABLE_DATED_SERVICE_WINDOW','service_window':[],
          'candidate_available_at':None,'reservation_state':'UNKNOWN_NOT_BOOKED'}
 for r in rows:
  start=max(minute,r['from'])
  if start+duration<=r['until'] and start<r['until'] and (r['last_order'] is None or start<=r['last_order']):
   return {'eligible':minute>=r['from'],'planning_viability':'AVAILABLE_NOW' if minute>=r['from'] else 'FUTURE_SERVICE_ONLY',
           'blocked_reason':None if minute>=r['from'] else 'SERVICE_NOT_OPEN_YET',
           'candidate_available_at':start,'service_window':r,'reservation_state':'UNKNOWN_NOT_BOOKED'}
 return {'eligible':False,'planning_viability':'NO_FITTING_SESSION','blocked_reason':'SERVICE_CLOSED_OR_INSUFFICIENT_TIME',
         'candidate_available_at':None,'service_window':rows,'reservation_state':'UNKNOWN_NOT_BOOKED'}

def eligibility_reasons(a,o,t,world):
 """Additional native eligibility parity checks, before score/choice."""
 why=[]
 fr=FR.block(a,o['id'])
 if fr:why.append(fr)
 if o['id'] in AD.GUEST_ENGINE and o['id']!='ROOM_REST' and (not a.stay or not a.checked_in or a.checked_out):
  why.append('CURRENT_CHECKED_IN_GUEST_REQUIRED')
 d=date.fromisoformat(a.sc['date'])
 if o['id']=='GEUMRYONG' and a.N<2 and (d.weekday()==5 or V.is_public_holiday(d)):
  # Existing menu source: Saturday/holiday dinner is course-only; all
  # approved course contracts require a minimum order of two. A solo team
  # has not explicitly ordered two portions. Venue inquiry remains possible.
  why.append('COURSE_ONLY_MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY')
 return why

@contextmanager
def install(day):
 original_init=AD.Agent.__init__
 def init(a,*args,**kwargs):
  original_init(a,*args,**kwargs)
  p=PO.party(a)
  if p is not None:
   a.C=dict(a.C,kids=bool(p['children']))
 original_evidence_policy=M4.evidence_policy
 def evidence_policy(known):
  reviews,event=original_evidence_policy(known)
  # Product aliases keep the existing venue review/state rule. No new
  # appraisal or repeat coefficient is created for a newly priced menu.
  for key,(venue,_,_) in MEALS.SPECS.items():
   if venue in reviews:reviews[key]=copy.deepcopy(reviews[venue])
  return reviews,event
 original_lunch_weight=SP.lunch_weight
 def lunch_weight(code,P,C,ctx):
  if code!='lunch_buffet':return original_lunch_weight(code,P,C,ctx)
  # Reuse native general restaurant coefficients, with only this candidate's
  # facts/daily evidence. Never borrow Ondal's personal history or venue match.
  profile=copy.deepcopy(P);context=copy.deepcopy(ctx)
  for field in ('fact_hits','daily_hits'):
   profile.setdefault(field,{})
   if code in profile[field]:profile[field]['lunch_ondal']=profile[field][code]
   else:profile[field].pop('lunch_ondal',None)
  context['dinner_loc']='ONDAL' if ctx.get('dinner_loc')=='THE_BUFFET' else None
  return original_lunch_weight('lunch_ondal',profile,C,context)
 original_turn=TC.turn_world
 original_breakfast=AD.breakfast_step
 breakfast_actor=[]
 def breakfast(a,world,t):
  breakfast_actor.append((a,t))
  try:
   with patch.dict(TC.TURN_TIME,{"breakfast":AD.mh(t)}):return original_breakfast(a,world,t)
  finally:breakfast_actor.pop()
 def turn_world(*args,**kwargs):
  w,excluded=original_turn(*args,**kwargs)
  if not breakfast_actor or (args[0] if args else kwargs.get("turn"))!="breakfast":return w,excluded
  a,t=breakfast_actor[-1];w=copy.deepcopy(w)
  if not any(o["id"]=="BREAKFAST_BUFFET" for o in w["offers"]):
   w["offers"].append(AD.WD.offer("BREAKFAST_BUFFET","더뷔페 조식 · 상품/금액 미확인","restaurant","THE_BUFFET",window={"start":"06:30","end":"10:00"},duration=60,price=None,meal_fraction=1,quality="standard",menu_tags=("buffet","variety")))
   excluded=[x for x in excluded if x.get("id")!="BREAKFAST_BUFFET"]
  from . import breakfast_policy as BP, douglas_light_breakfast as DLB
  if BP.policy(a.sc)==BP.V2:
   light=DLB.offer(a,t,SP.travel_min(a.loc,DLB.VENUE))
   if light is not None and light['available']:w['offers'].append(light)
   elif light is not None:excluded.append(dict(id=DLB.ID,name=DLB.LABEL,why=light['status']))
  else:
   if a.B=='DOUGLAS' and a.stay and a.checked_in and not a.checked_out and a.N<=2 and 420<=t and t+30<=600:
    o=AD.WD.offer('DOUGLAS_LIGHT_BREAKFAST','더글라스 라이트 조식 · 포함 혜택','restaurant','DOUGLAS_LOUNGE',window={'start':'07:00','end':'10:00'},duration=30,price=0,grade='◎',in_package=True,meal_fraction=.5,quality='standard',menu_tags=('bread',))
    o['service_contract']={'venue_id':'DOUGLAS_LOUNGE','service_window':o['window'],'candidate_available_at':t,'planning_viability':'AVAILABLE_NOW','source_state':'OFF-DOUGLAS-FACILITY','reservation_state':'NOT_REQUIRED_FOR_INCLUDED_LOUNGE_USE','price_status':'INCLUDED_NOT_NEW_REVENUE','blocked_reason':None,'duration_status':'SIMULATION_ASSUMPTION_30_MIN'}
    w['offers'].append(o)
  for o in w["offers"]:
   if o["id"]=="BREAKFAST_BUFFET":
    check=service_check("THE_BUFFET",day,t+SP.travel_min(a.loc,"THE_BUFFET"),o["duration_min"])
    if not check["eligible"]:o["available"]=False;o["status"]=check["blocked_reason"]
    o["service_contract"]=check
    from . import breakfast_policy as BP
    priced=MEALS.buffet(o,a,'breakfast',t,covered_adults=BP.covered_adults(a));o.update(priced)
  return w,excluded
 original_engine_world_for=AD.engine_world_for
 def engine_world_for(a,world,t):
  w=original_engine_world_for(a,world,t)
  offers=[]
  for raw in w['offers']:
   o=MEALS.attach(PRODUCTS.attach(copy.deepcopy(raw),a),a,t)
   if raw['id'] in ('MOEGI',*PRODUCTS.VARIANTS) and PO.party(a):
    name=PRODUCTS.VARIANTS[raw['id']][0] if raw['id'] in PRODUCTS.VARIANTS else '마코토 코스'
    line,row=MEALS.find('모에기',name)
    c=PO.mixed_person_contract(MEALS.contract(line,row,'MOEGI','dinner',a.N),a)
    if c is not None:
     o=MEALS.bind(copy.deepcopy(raw),c,a.N);o['sku_contract']['last_order']='19:30'
   if PO.explicit_order(a,raw['venue'],'lunch' if t<960 else 'dinner') and raw['id']!=raw['venue']:
    o.update(available=False,status='EXPLICIT_VIRTUAL_ORDER_OTHER_SKU_NOT_ORDERED')
   why=eligibility_reasons(a,o,t,world)
   if _V12Z_COMMON and o.get('order_deadline') and max(t+SP.travel_min(a.loc,o['venue']),AD.hm(o['window']['start']))>AD.hm(o['order_deadline']):why.append('SKU_ORDER_DEADLINE_PASSED')   # V1.2(Claude 10/30) order-window
   if o.get('sku_contract') and o['sku_contract'].get('last_order'):
    arrival=t+SP.travel_min(a.loc,o['venue'])
    if max(arrival,18*60)>19*60+30:why.append('DINNER_COURSE_LAST_ORDER_PASSED')
   if why:
    o['available']=False;o['status']='; '.join(why)
    o.setdefault('service_contract',{}).update(planning_viability='BLOCKED',blocked_reason=o['status'])
    if 'COURSE_ONLY_MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY' in why:
     o['service_contract'].update(venue_operating=True,planning_viability='VENUE_INQUIRY_ONLY_ORDER_QUANTITY_REQUIRED',
       source_rule='timeline/menu.csv:132-144; course minimum order, Saturday/public-holiday dinner service')
   offers.append(o)
  # An open venue is a container for its menus, not an extra zero-cost meal.
  # Keep venue-only execution if no priced, source-eligible menu can fit.
  st=dict(used=set(a.used),hunger=a.hunger_e);visit=dict(a.visit_e,checkin=AD.mh(t))
  for o in offers:
   if o['id'] not in ('GEUMRYONG','ONDAL','MYONGWOLGWAN','PIZZA_HILL','MOEGI') or not o.get('available') or o.get('price_pp_krw') is not None:continue
   matches=[x['id'] for x in offers if x['id']!=o['id'] and x['venue']==o['venue'] and x.get('sku_contract') and x.get('price_pp_krw') is not None and x.get('available') and not EN.feasible(x,(t+SP.travel_min(a.loc,x['venue']) if _V12Z_COMMON else t),st,visit)]   # V1.2(Claude 10/30) order-window: 도착 시각 기준
   if matches:
    o.update(available=False,status='VENUE_EXECUTION_REPRESENTED_BY_ELIGIBLE_PRODUCTS')
    o['service_contract']=dict(o.get('service_contract',{}),venue_operating=True,
       planning_viability='AVAILABLE_AS_VENUE_WITH_PRODUCT_CHOICES',
       selection_role='VENUE_CONTAINER_NOT_SEPARATE_UNPRICED_MEAL',
       eligible_product_ids=matches,blocked_reason='CHOOSE_AVAILABLE_PRODUCT_FOR_MEAL_EXECUTION')
  return dict(w,offers=offers)
 original_world=AD.World.engine_world
 original_score=EN._score
 original_cost=EN.out_of_pocket
 original_raw=AD.turn_raw
 def turn_raw(a,d_terms,rejected,chosen,o,w,t,world_kind,score,total=None):
  result=original_raw(a,d_terms,rejected,chosen,o,w,t,world_kind,score,total)
  result["runtime_offers"]=copy.deepcopy(w["offers"])
  result["decision_minute"]=t
  return result
 original_charge=AD.LG.charge
 def charge(a,code,kind,loc,offer=None,in_package=False):
  from . import breakfast_policy as BP, douglas_light_breakfast as DLB
  if (offer or {}).get('id')==DLB.ID and BP.policy(a.sc)==BP.V2:return DLB.charge(a)
  if (offer or {}).get('c01_lunch_venue_only'):
   return dict(status='가격 미정',krw=None,grade=None,basis='업장 선택; 연령 구성/메뉴/주문 단위 미확인 · 무료 아님',auto_charge=False)
  if loc in ("DOUGLAS_LOUNGE","DOUGLAS_LIBRARY"):
   if a.B!="DOUGLAS" or not a.stay or not a.checked_in or a.checked_out:
    return dict(status="가격 미정",krw=None,grade=None,basis="더글라스 이용 자격 미확인",auto_charge=False)
   if loc=="DOUGLAS_LOUNGE" and a.N>2:
    return dict(status="가격 미정",krw=None,grade=None,basis="라운지 추가 인원 승인·요금 주기 미확인",auto_charge=False)
   return dict(status="포함",krw=0,grade="◎",basis="더글라스 투숙객 전용 · 라운지 객실당 2인 포함 / 라이브러리 이용",auto_charge=False)
  selected_contract=(offer or {}).get('sku_contract') or MEALS.planner_contract(code,a)
  if selected_contract and selected_contract.get('billing_unit')=='portion_person_mapping_pending':
   return dict(status='가격 미정',krw=None,grade='◎',sku_contract=selected_contract,price_kind='billing_unit_unknown',basis='기존 게시 금액 '+str(selected_contract['listed_amount_krw'])+'원 · 최신 검수에서 1인분 기준 미확인 · 인원 자동 곱셈 안 함',auto_charge=False)
  if selected_contract and (selected_contract['sku_id'].startswith('C01-MENU-') or selected_contract.get('user_confirmation')) and not in_package:
   selected_contract=dict(selected_contract,resolution_layer=selected_contract.get('resolution_layer') or ('PRE_ACTION_NATIVE_PRODUCT_CANDIDATE' if offer else 'EXISTING_PLANNER_FIXED_MENU_MAPPING_NOT_SKU_PREFERENCE_SCORE'))
   return MEALS.bill(selected_contract,a)
  if code in ('cafe','lunch_cafe'):
   return dict(status='가격 미정',krw=None,grade='◎',basis='카페 이용: 실제 음료/디저트 주문 미확인; 2인 세트 인원·시간 조건 불일치',auto_charge=False)
  if code=='lunch_myongwol':
   return dict(status='가격 미정',krw=None,grade='◎',basis='명월관 점심 53,000원/200g 판매분 · 주문 수량 입력 없음 · 인원수 자동 곱셈 안 함',auto_charge=False)
  result=original_charge(a,code,kind,loc,offer,in_package)
  if (offer or {}).get('sku_contract'):
   c=offer['sku_contract'];result=dict(result,sku_contract=c,price_kind='dated_model_reference',
      basis=f"기존 공식 {c['source_document']} · {c['source_checked_at']} 확인 · 가상 단가 {c['unit_price_krw']:,}원 × {a.N}인 · 현재 판매·예약 미확인")
  return result
 original_ok=AD.plan_ok
 original_plan_do=AD.plan_do
 def lunch_options(a,code,t,world):
  templates={o['id']:o for o in world.engine_world(t)['offers']}
  if code in ('cafe','lunch_cafe'):
   # Existing cafe activity, neutral product template. A drink is not a meal;
   # neither a bakery affinity nor a new satiety estimate is imported.
   templates['THE_PAVILION']=AD.WD.offer('THE_PAVILION','파빌리온 카페 상품','simple_meal','THE_PAVILION',
     duration=SP.ACT[code][3],price=None,meal_fraction=0 if code=='cafe' else .5,
     quality='none' if code=='cafe' else 'standard',menu_tags=() if code=='cafe' else ('brunch',))
  return LUNCH_PRODUCTS.options(a,code,t,templates,service_check,SP.ACT[code][3],SP.travel_min(a.loc,SP.ACT[code][1](a.B)))
 def plan_do(a,code,loc,t,weights,rej,source='planner_rules',note=None):
  _ow=getattr(a,'_open_wait',{}) or {};_open=_ow.pop(code,None)   # V1.2(Claude 10/30) order-window open-wait: 개점까지 대기 장면
  _open=_open[1] if _V12Z_COMMON and _open and _open[0]==t else None;a._open_wait={}
  if _open is not None and t+SP.travel_min(a.loc,loc)<_open:
   _arr=t+SP.travel_min(a.loc,loc)
   a.add('wait','wait',SP.ACT[code][0]+' · 개점 대기',loc,t,_open-_arr,'대기','world_rule',f'{AD.mh(_open)} 개점까지 기다립니다.',[])
   t=a.t
  if code not in LUNCH_PRODUCTS.VENUES:return original_plan_do(a,code,loc,t,weights,rej,source,note)
  offers,excluded=lunch_options(a,code,t,AD.World(a.sc))
  o,record=LUNCH_PRODUCTS.choose(a,code,t,AD.World(a.sc).engine_world(t),offers,excluded,AD)
  if o is None:raise RuntimeError('C01_LUNCH_SELECTION_WITHOUT_FEASIBLE_PRODUCT')
  add=AD.Agent.add
  def selected_add(actor,*args,**kwargs):
   if actor is a and len(args)>1 and args[1]==code:
    values=list(args);values[2]=o['label']
    if len(values)>10:values[10]=dict(values[10] or {},c01_product_decision=record)
    else:kwargs['internal']=dict(kwargs.get('internal') or {},c01_product_decision=record)
    kwargs['offer']=o
    return add(actor,*values,**kwargs)
   return add(actor,*args,**kwargs)
  with patch.object(AD.Agent,'add',selected_add):
   return original_plan_do(a,code,loc,t,weights,rej,source,note)
 original_annotate=M4._annotate
 d=date.fromisoformat(day)
 daily={k:[(w.open_at.hour*60+w.open_at.minute,w.close_at.hour*60+w.close_at.minute)
            for w in windows(k,day)] for k in V.WALKERHILL_VENUE_WINDOWS}
 daily.update(DOUGLAS_LOUNGE=[(420,1320)],DOUGLAS_LIBRARY=[(0,1439)])
 def world(self,t):
  w=copy.deepcopy(original_world(self,t))
  # Generic meal template: duration/meal fraction are simulation assumptions;
  # no Makoto/TSUKI SKU, course count, premium score or asserted payment.
  w['offers'].append(AD.WD.offer('MOEGI','모에기 저녁 · 상품/금액 미확인','restaurant','MOEGI',
     window={'start':'18:00','end':'21:00'},duration=90,price=None,
     price_note='Venue-level choice only; dinner SKU not approved',meal_fraction=1,
     quality='standard',menu_known=False))
  for code,(name,price,page) in PRODUCTS.VARIANTS.items():
   variant=copy.deepcopy(w['offers'][-1]);variant.update(id=code,label='모에기 '+name+' · 상품 조건 확인');w['offers'].append(variant)
  w=MEALS.variants(w)
  for o in w['offers']:
   venue=AD.ENGINE_LOC.get(o['id'],o['venue'])
   if o['id'] in OFFICIAL_DINNER:
    start,end,url=OFFICIAL_DINNER[o['id']]
    o['window']={'start':start,'end':end}
    o['service_source']={'url':url,'checked_at':'2026-10-28','state':'OFFICIAL_HOURS_CHECKED_ONLY'}
   if venue in V.WALKERHILL_VENUE_WINDOWS and o['kind']!='event':
    period='dinner' if o['kind']=='restaurant' else None
    ws=windows(venue,day)
    if period:ws=[x for x in ws if x.close_at.hour*60+x.close_at.minute>16*60]
    valid=[x for x in ws if max(t,x.open_at.hour*60+x.open_at.minute)+o['duration_min']<=x.close_at.hour*60+x.close_at.minute]
    if valid:
     win=min(valid,key=lambda x:x.open_at)
     # A single applicable session; never bridge closed gaps.
     o['window']={'start':AD.mh(max(win.open_at.hour*60+win.open_at.minute,AD.hm(o['window']['start']) if period and o.get('window') else 0)),'end':win.close_at.strftime('%H:%M')}
     if win.last_order and max(t,AD.hm(o['window']['start']))>win.last_order.hour*60+win.last_order.minute:
      o['available']=False;o['status']='LAST_ORDER_PASSED'
    else:o['available']=False;o['status']='NO_FITTING_DATED_SERVICE_WINDOW'
   if o['id']=='ONDAL':
    # Official weekday/weekend last order; party rule checked in feasibility.
    o['last_order']=20*60 if d.weekday()>=5 or d in V.PUBLIC_HOLIDAYS else 20*60+30
    if t>o['last_order']:o['available']=False;o['status']='LAST_ORDER_PASSED'
   if o['id']=='MOEGI':
    o['price_status']='AMOUNT_UNKNOWN';o['sku_id']=None
   o['service_contract']={'venue_id':venue,'service_window':o.get('window'),
      'candidate_available_at':max(t,AD.hm(o['window']['start'])) if o.get('window') else t,
      'planning_viability':'FUTURE_SERVICE_ONLY' if o.get('window') and t<AD.hm(o['window']['start']) else 'AVAILABLE_NOW' if o['available'] else 'BLOCKED',
      'reservation_state':'UNKNOWN_NOT_BOOKED','price_status':o.get('price_status','EXISTING_MODEL_PRICE_NOT_CURRENT_SALE'),
      'source_state':o.get('service_source',{}).get('state','EXISTING_COLLECTED_WINDOW'),
      'blocked_reason':None if o['available'] else o.get('status')}
  return w
 def cost(o):
  return None if o.get('price_pp_krw') is None else original_cost(o)
 def score(o,*args):
  if o.get('price_pp_krw') is not None:return original_score(o,*args)
  # Omit the monetary term explicitly; null remains on the actual offer and
  # decision. Zero here is only an arithmetic sentinel for the old scorer.
  known=copy.deepcopy(o);known['price_pp_krw']=0
  known['guest_discount_krw']=known['card_benefit_krw']=0;known['in_package']=False
  return original_score(known,*args)+[EN._term('가격 미확인 · 비용 비교 미평가',0,kind='uncertainty')]
 def plan_ok(a,code,t,world,why_out,revisit=False):
  loc=SP.ACT[code][1](a.B);arrival=t+SP.travel_min(a.loc,loc)
  if loc in ('DOUGLAS_LOUNGE','DOUGLAS_LIBRARY'):
   if a.B!='DOUGLAS' or not a.stay or not a.checked_in or a.checked_out:
    why_out[code]='DOUGLAS_CURRENT_GUEST_REQUIRED';return None
   if loc=='DOUGLAS_LOUNGE' and a.N>2:
    why_out[code]='EXTRA_LOUNGE_PERSON_APPROVAL_UNKNOWN';return None
   # Existing lounge preference; only property/eligibility mapping is repaired.
   with patch.dict(AD.NOT_ELIGIBLE,{},clear=True):
    return original_ok(a,code,t,world,why_out,revisit)
  fr=FR.block(a,code)   # facility rule set 11/02: building-specific closure date, unpriced Vista sauna
  if fr:
   why_out[code]=fr;return None
  if code=='sauna' and not FR.sauna_hours_ok(arrival,SP.ACT[code][3]):
   why_out[code]='SERVICE_CLOSED_OR_INSUFFICIENT_TIME';return None
  if loc in V.WALKERHILL_VENUE_WINDOWS and code!='sauna':   # sauna node closure is building-specific (FR.block)
   result=service_check(loc,day,arrival,SP.ACT[code][3])
   if _V12Z_COMMON and not result['eligible'] and result.get('blocked_reason')=='SERVICE_NOT_OPEN_YET' and result.get('candidate_available_at') is not None and result['candidate_available_at']-arrival<=EN.WAIT_LEAD_MIN:   # V1.2(Claude 10/30) order-window open-wait
    a._open_wait=dict(getattr(a,'_open_wait',{}) or {},**{code:(t,result['candidate_available_at'])})   # 결정 시각과 함께 저장(다른 결정 · 다른 날에 남지 않게)
    result=dict(result,eligible=True)
    t=result['candidate_available_at']-SP.travel_min(a.loc,loc)   # 이후 영업시간 · 상품 검사는 개점 도착 기준
   if not result['eligible']:
    why_out[code]=result['blocked_reason'];return None
  if code in ('lunch_moegi','lunch_myongwol','lunch_geumryong','lunch_ondal') and arrival>=16*60:
   why_out[code]='LUNCH_SKU_NOT_VALID_FOR_DINNER';return None
  if loc=='ONDAL' and (d.weekday()>=5 or d in V.PUBLIC_HOLIDAYS) and a.N<2:
   why_out[code]='WEEKEND_COURSE_MINIMUM_TWO';return None
  result=original_ok(a,code,t,world,why_out,revisit)
  if result and code in LUNCH_PRODUCTS.VENUES:
   offers,excluded=lunch_options(a,code,t,world)
   if not offers:
    why_out[code]='NO_ELIGIBLE_LUNCH_PRODUCT; '+ '; '.join(sorted({r for x in excluded for r in x['reasons']}));return None
  return result
 original_feasible=EN.feasible
 def feasible(o,t,state,visit):
  why=original_feasible(o,t,state,visit)
  if o['id']=='ONDAL' and (d.weekday()>=5 or d in V.PUBLIC_HOLIDAYS) and visit['party_size']<2:
   why=list(why)+['WEEKEND_COURSE_MINIMUM_TWO']
  return why
 def annotate(result,stage,pid,scenario,inputs):
  result=original_annotate(result,stage,pid,scenario,inputs)
  result['m4']['configuration']=configuration()
  world_instance=AD.World(scenario)
  for record in result['m4']['decisions']:
   packet=record['packet'];t=packet['context_factors']['time']
   offers={o['id']:o for o in world_instance.engine_world(t)['offers']}
   actual=next((x['internal']['turn_raw']['runtime_offers'] for x in result.get('log',[]) if x.get('internal',{}).get('turn_raw',{}).get('runtime_offers') and x['internal']['turn_raw'].get('decision_minute')==t),None)
   if actual:offers={o['id']:o for o in actual}
   for row in packet['candidates']:
    if row['candidate_id'] in offers:
     row['service_contract']=offers[row['candidate_id']]['service_contract']
     o=offers[row['candidate_id']]
     if actual and o.get('hc_contract'):
      c=o['sku_contract'];row['product_quote']=dict(sku_id=c['sku_id'],total_krw=c['unit_price_krw'],included=bool(o.get('in_package')),source='ACTUAL_PRE_SELECTION_RUNTIME_OFFER',components=[{k:copy.deepcopy(p[k]) for k in ('sku_id','billing_quantity','unit_price_krw','price_trace') if k in p} for p in c.get('components',[])])
   packet['packet_sha256']=M4.digest({k:v for k,v in packet.items() if k!='packet_sha256'})
  for row in result.get('log',[]):
   if row.get('internal',{}).get('hotel_product_decision'):
    result['m4'].setdefault('hotel_product_decisions',[]).append(dict(copy.deepcopy(row['internal']['hotel_product_decision']),time=row['t'],date=scenario['date'],customer_id=pid))
   record=copy.deepcopy(row.get('internal',{}).get('c01_product_decision'))
   if record:
    record['packet']['packet_sha256']=M4.digest(record['packet'])
    record['actual_next_action']=row['act'];record['execution_status']='EXECUTED'
    result['m4']['decisions'].append(record)
  result['m4']['decisions'].sort(key=lambda r:r['packet']['context_factors']['time'])
  return result
 with ExitStack() as stack:
  for obj,key,val in [(AD.Agent,'__init__',init),(AD,'engine_world_for',engine_world_for),(SP,'WIN',daily),(SP,'lunch_weight',lunch_weight),(AD.World,'engine_world',world),(EN,'_score',score),
      (EN,'out_of_pocket',cost),(EN,'feasible',feasible),(AD,'plan_ok',plan_ok),(AD,'plan_do',plan_do),(AD.LG,'charge',charge),(TC,'turn_world',turn_world),(AD,'breakfast_step',breakfast),(AD,'turn_raw',turn_raw),(M4,'_annotate',annotate),(M4,'evidence_policy',evidence_policy)]:
   stack.enter_context(patch.object(obj,key,val))
  for mapping,values in [(AD.ENGINE_LOC,dict({'MOEGI':'MOEGI'},**{k:'MOEGI' for k in PRODUCTS.VARIANTS},**{k:v[0] for k,v in MEALS.SPECS.items()})),(AD.ENGINE_DOMAIN,dict({'MOEGI':'식사','DOUGLAS_LIGHT_BREAKFAST':'식사'},**{k:'식사' for k in PRODUCTS.VARIANTS},**{k:'식사' for k in MEALS.SPECS})),
      (AD.VENUE_KO,dict({'MOEGI':'모에기'},**{k:'모에기' for k in PRODUCTS.VARIANTS},**{k:v[1] for k,v in MEALS.SPECS.items()})),(AD.LUNCH_ENGINE,{'lunch_moegi':'MOEGI','lunch_buffet':'THE_BUFFET'}),
      (SP.ACT,{'lunch_buffet':('더뷔페 점심',lambda b:'THE_BUFFET','lunch',90,False,True),
       'lounge':('투숙 건물 라운지',lambda b:'DOUGLAS_LOUNGE' if b=='DOUGLAS' else 'GRAND_CLUB_LOUNGE',*SP.ACT['lounge'][2:]),
       'library':(SP.ACT['library'][0],lambda b:'DOUGLAS_LIBRARY' if b=='DOUGLAS' else 'GRAND_LIBRARY',*SP.ACT['library'][2:])}),
      (SP.BLDG_OF,{'DOUGLAS_LOUNGE':'DOUGLAS','DOUGLAS_LIBRARY':'DOUGLAS'}),
      (AD.LG.PLAN_PRICE,{'lunch_buffet':(None,'person','더뷔페 점심 상품·금액 미확인')})]:
   stack.enter_context(patch.dict(mapping,values))
  stack.enter_context(patch.object(SP,"LUNCH",SP.LUNCH+["lunch_buffet"]))
  stack.enter_context(HR.install(__import__(__name__,fromlist=[''])))
  from . import native_hybrid
  stack.enter_context(native_hybrid.install(__import__(__name__,fromlist=[''])))
  from . import operational_environment
  stack.enter_context(operational_environment.install())
  yield

def run_one(pid,scenario,inputs):
 with install(scenario['date']):return M4.run_one(pid,scenario,inputs)

def run_many(pids,scenario,inputs):
 with install(scenario['date']):return M4.run_many(pids,scenario,inputs)
