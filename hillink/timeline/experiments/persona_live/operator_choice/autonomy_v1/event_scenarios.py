"""C01 card-to-world adapter. Explicit snapshots only; no chooser or LLM policy."""
import copy,csv,hashlib,json
from pathlib import Path
from datetime import date,timedelta
from contextlib import ExitStack,contextmanager
from unittest.mock import patch
from . import candidate_services as C, m4_event, scenario_conditions, wine_admission, santa_2026 as S26
AD=C.AD;M4=C.M4
VERSION='c01-event-card-runtime-v3-admission'
ROOT=Path(__file__).resolve().parents[5]
SOURCE=ROOT/'research/w44_c01/event_cards_sources.csv'
SOURCE_SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
ROWS=list(csv.DictReader(SOURCE.read_text(encoding='utf-8-sig').splitlines()))
IDS=['WINE_FAIR_2026_AUTUMN','SANTA_KIDS_VILLAGE_2025','PIZZA_HILL_GOLDEN_NIGHT_2026','SAVORING_SUMMER_NIGHT_2026','NONE',S26.ID]
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def runtime_signature():return digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(scenario_conditions.__file__),Path(wine_admission.__file__),Path(S26.__file__),S26.PATH]})
def minute(s):
 try:
  h,m=map(int,s.split(':'));assert 0<=h<24 and 0<=m<60;return h*60+m
 except Exception:raise ValueError('EVENT_INVALID_TIME')
def ref(line):return dict(path='research/w44_c01/event_cards_sources.csv',csv_line=line,sha256=SOURCE_SHA,record=ROWS[line-2])

def snapshot(config,start,duration):
 if not isinstance(config,dict) or set(config)-{'event_card_id','enabled','assumptions','weather','entitlements','arrival_time','wine_admission'}:raise ValueError('EVENT_SCENARIO_FIELDS_INVALID')
 admission=wine_admission.validate(config.get('wine_admission'))
 eid=config.get('event_card_id')
 if eid not in IDS:raise ValueError('EVENT_CARD_NOT_SUPPORTED')
 if admission and eid!=IDS[0]:raise ValueError('WINE_ADMISSION_REQUIRES_WINE_SCENARIO')
 enabled=config.get('enabled',True)
 if not isinstance(enabled,bool):raise ValueError('EVENT_ENABLED_MUST_BE_BOOLEAN')
 assumptions=copy.deepcopy(config.get('assumptions') or {})
 if not isinstance(assumptions,dict) or set(assumptions)-{'sessions','duration_min','meal_fraction','historical_model_prices_acknowledged','admission_allowed_as_virtual_condition','booked_sessions','santa_before_checkin'}:raise ValueError('EVENT_ASSUMPTION_FIELDS_INVALID')
 if eid==S26.ID:
  S26.validate(config,start,duration)
  assumptions.update(sessions=copy.deepcopy(S26.SESSIONS),duration_min=70,meal_fraction=0)
 sessions=assumptions.get('sessions');minutes=assumptions.get('duration_min');missing=[]
 base={'WINE_FAIR_2026_AUTUMN':('FOREST_PARK','2026-10-10','2026-10-25',[5,6],81),
  'SANTA_KIDS_VILLAGE_2025':('FOREST_PARK','2025-12-19','2025-12-25',list(range(7)),64),
  'PIZZA_HILL_GOLDEN_NIGHT_2026':('PIZZA_HILL','2026-09-10','2026-09-18',[3,4],99),
  'SAVORING_SUMMER_NIGHT_2026':('RIVERPARK','2026-07-17','2026-08-30',[4,5,6],132),
  S26.ID:('FOREST_PARK','2026-12-18','2026-12-25',list(range(7)),None),
  'NONE':('NONE','1900-01-01','9999-12-31',list(range(7)),None)}[eid]
 if eid==IDS[0]:sessions=[['15:30','20:00']];minutes=120
 elif eid==IDS[3]:sessions=[['15:00','21:30']]
 if not sessions and eid!='NONE':missing.append('SESSION_TIMES_NOT_RECORDED; EXPLICIT_ASSUMPTION_REQUIRED')
 elif sessions and (not isinstance(sessions,list) or any(not isinstance(s,list) or len(s)!=2 or minute(s[0])>=minute(s[1]) for s in sessions)):raise ValueError('EVENT_SESSIONS_INVALID')
 if minutes is None and eid!='NONE':missing.append('DURATION_NOT_RECORDED; EXPLICIT_ASSUMPTION_REQUIRED')
 elif minutes is None:pass
 elif type(minutes)!=int or not 5<=minutes<=240:raise ValueError('EVENT_DURATION_INVALID')
 if sessions and minutes and not any(minute(b)-minute(a)>=minutes for a,b in sessions):raise ValueError('EVENT_DURATION_EXCEEDS_SESSION')
 if eid==IDS[1] and sessions and len(sessions)!=4:raise ValueError('SANTA_SOURCE_HAS_FOUR_SESSIONS')
 booked=assumptions.get('booked_sessions')
 # Operator assumption: these customers already hold a booking for one declared session.
 # It fixes attendance timing only; eligibility, price and every later choice stay with the engine.
 if booked is not None:
  if eid not in (IDS[1],S26.ID):raise ValueError('BOOKED_SESSIONS_SANTA_ONLY')
  if not isinstance(booked,dict) or not booked or len(booked)>32:raise ValueError('BOOKED_SESSIONS_INVALID')
  starts={a for a,_ in (sessions or [])}
  for pid,b in booked.items():
   if not isinstance(pid,str) or not isinstance(b,dict) or set(b)!={'date','start'}:raise ValueError('BOOKED_SESSION_FIELDS_INVALID')
   date.fromisoformat(b['date'])
   if b['start']=='auto':
    if not {'15:20','16:30'}<=starts:raise ValueError('BOOKED_SESSION_AUTO_REQUIRES_PACKAGE_SESSIONS')
   elif b['start'] not in starts:raise ValueError('BOOKED_SESSION_START_NOT_DECLARED')
 bc=assumptions.get('santa_before_checkin')
 if bc is not None and (eid not in (IDS[1],S26.ID) or bc not in ('operator_virtual_allowed','not_allowed')):raise ValueError('SANTA_BEFORE_CHECKIN_INVALID')
 fraction=assumptions.get('meal_fraction',0)
 if type(fraction) not in (int,float) or not 0<=fraction<=1:raise ValueError('EVENT_MEAL_FRACTION_INVALID')
 weather=config.get('weather') or {'condition':'clear'}
 if not isinstance(weather,dict) or set(weather)-{'condition','rain_forecast_lead_days','explicit_pool_safety_closure'} or weather.get('condition') not in ('clear','rain'):raise ValueError('EVENT_WEATHER_INVALID')
 if weather.get('rain_forecast_lead_days') not in (None,0,1,2,3):raise ValueError('EVENT_WEATHER_LEAD_INVALID')
 if weather.get('explicit_pool_safety_closure') not in (None,True,False):raise ValueError('EVENT_SAFETY_CLOSURE_INVALID')
 arrival=config.get('arrival_time')
 if arrival is not None and (not isinstance(arrival,str) or len(arrival)!=5 or not 7*60<=minute(arrival)<=20*60):raise ValueError('SCENARIO_ARRIVAL_SUPPORTED_07_00_TO_20_00_ONLY')
 entitlements=config.get('entitlements') or {}
 if eid!=S26.ID and (not isinstance(entitlements,dict) or any(not isinstance(v,dict) or set(v)-{'included_people','selected_package'} or v.get('selected_package') is not True or type(v.get('included_people'))!=int or not 1<=v['included_people']<=8 for v in entitlements.values())):raise ValueError('EVENT_PACKAGE_ASSUMPTION_INVALID')
 if start[:4]!='2026' and assumptions.get('historical_model_prices_acknowledged') is not True:raise ValueError('HISTORICAL_VISIT_REQUIRES_MODEL_PRICE_ASSUMPTION_ACK')
 # Card source row numbers are physical CSV lines, including the header.
 sources=[ref(base[4])] if base[4] else [dict(path='OPERATOR_SCENARIO_INPUT',source_state='OPERATOR_ASSUMPTION_NOT_OFFICIAL_EVENT',record={'행사 · 상품명':'행사 없음'})]
 if eid==S26.ID:sources=[S26.source()]
 if eid==IDS[0]:sources.append(dict(path='timeline/place_assumptions.csv',sha256=hashlib.sha256((ROOT/'timeline/place_assumptions.csv').read_bytes()).hexdigest(),scope='Existing accepted wine execution reused unchanged'))
 if eid==IDS[3]:sources.append(dict(path='docs/운영근거_환경변수_혜택_소연_1020.md',sha256=hashlib.sha256((ROOT/'docs/운영근거_환경변수_혜택_소연_1020.md').read_bytes()).hexdigest(),scope='Gold second session 15:00–21:30, package only, once per occupied room night; semi-buffet cancellation separate from pool'))
 result=dict(weather_source='VIRTUAL_OPERATOR_CONDITION_NOT_ACTUAL_FORECAST',source_event_start_unconfirmed=(eid==IDS[2]),date_rule_note='Only four dates supported after the dated September 7 press reference; actual Golden Night start remains unknown' if eid==IDS[2] else None,scenario_version=VERSION,event_card_id=eid,enabled=enabled,start_date=start,duration=duration,venue_id=base[0],
  source_date_range=[base[1],base[2]],weekdays=base[3],sessions=sessions,duration_min=minutes,meal_fraction=fraction,
  weather=weather,arrival_time=arrival,arrival_source='OPERATOR_VIRTUAL_FIRST_DAY_ONLY' if arrival else 'UNCHANGED_NATIVE_PROFILE_DEFAULT',runtime_sha256=runtime_signature(),wine_admission=admission,entitlements=entitlements,sources=sources,assumptions=assumptions,missing_fields=missing,
  contract_status='HOLD_REQUIRED_EXECUTION_FIELDS' if missing else 'EXECUTABLE_WITH_DECLARED_ASSUMPTIONS' if assumptions else 'EXISTING_VERIFIED_EXECUTION',
  reservation_state='UNKNOWN_NOT_BOOKED',prices_are_simulation_references=True,
  applicability_note='Historical event scenario; not a currently operating event. 2026 model prices outside the event are virtual references, not reconstructed historic sales.')
 if eid==S26.ID:
  result.update(applicability_note='2026 official package sessions; starting rates only, no confirmed booking or prediction',reservation_state='OPERATOR_BOOKING_ASSUMPTION' if booked else 'UNKNOWN_NOT_BOOKED',contract_status='OFFICIAL_2026_WITH_EXPLICIT_VIRTUAL_PACKAGE',santa_contract_sha256=S26.SHA)
 result['scenario_id']='C01-EVENT-'+digest(result)[:24];result['snapshot_sha256']=digest(result)
 return result

def active(s,day):return s['event_card_id']!='NONE' and s['enabled'] and s['source_date_range'][0]<=day<=s['source_date_range'][1] and date.fromisoformat(day).weekday() in s['weekdays']

def schedule(s):
 nights={'day_visit':0,'stay_1':1,'stay_2':2,'stay_3':3}[s['duration']];start=date.fromisoformat(s['start_date'])
 return [dict(day_index=i+1,date=(start+timedelta(days=i)).isoformat(),phase='visit' if nights==0 else 'checkin' if i==0 else 'checkout' if i==nights else 'mid',event=active(s,(start+timedelta(days=i)).isoformat()) and s['event_card_id']==IDS[0]) for i in range(nights+1)]

def eligibility(a,s):
 reasons=[];day=a.sc['date']
 if not active(s,day):reasons.append('EVENT_NOT_ACTIVE_ON_DATE')
 reasons+=s['missing_fields']
 if s['event_card_id']==IDS[1]:
  p=a.vs.get('party_composition')
  if not p or p['adult_count']!=2 or len(p['children'])!=1:reasons.append('SOURCE_FAMILY_TICKET_PARTY_2_ADULT_1_CHILD_NOT_MATCHED_OR_UNKNOWN')
 if s['event_card_id']==S26.ID:
  p=S26.package(s,a.pid)
  if not p:reasons.append('SANTA_2026_PACKAGE_REQUIRED_FOR_CONFIRMED_SESSIONS')
  if not (s['assumptions'].get('booked_sessions') or {}).get(a.pid):reasons.append('SANTA_2026_SESSION_RESERVATION_NOT_DECLARED')
  if s['assumptions'].get('santa_before_checkin')=='not_allowed' and not a.checked_in:reasons.append('SANTA_2026_CHECKIN_REQUIRED_BEFORE_ADMISSION')
  if day!=s['start_date']:reasons.append('SANTA_2026_INCLUDED_ADMISSION_FIRST_DAY_ONLY')
  if any(x.get('event_card_id')==S26.ID for x in a.visit_history.get('scenario_event_usage',[])):reasons.append('SANTA_2026_ADMISSION_ALREADY_USED')
 if s['event_card_id']==IDS[2] and s['assumptions'].get('admission_allowed_as_virtual_condition') is not True:reasons.append('2026_ADMISSION_UNCONFIRMED_EXPLICIT_VIRTUAL_CONDITION_REQUIRED')
 room_key=day if a.phase!='checkout' else (date.fromisoformat(day)-timedelta(days=1)).isoformat()
 if s['event_card_id']==IDS[3]:
  if not a.stay or not a.checked_in or a.checked_out:reasons.append('CURRENT_CHECKED_IN_GUEST_REQUIRED')
  if a.B not in ('GRAND','VISTA'):reasons.append('SAVORING_PACKAGE_PROPERTY_NOT_ELIGIBLE')
  if a.pid not in s['entitlements']:reasons.append('SAVORING_PACKAGE_NOT_SELECTED')
  elif a.N>s['entitlements'][a.pid]['included_people']:reasons.append('PACKAGE_PARTY_COVERAGE_NOT_CONFIRMED')
  if any(x['room_night_key']==room_key and x['event_card_id']==s['event_card_id'] for x in a.visit_history.get('scenario_event_usage',[])):reasons.append('ROOM_NIGHT_EVENT_ENTITLEMENT_ALREADY_USED')
  w=s['weather']
  if w.get('explicit_pool_safety_closure') is True:reasons.append('EXPLICIT_SCENARIO_SAFETY_CLOSURE; NOT_INFERRED_FROM_RAIN')
  elif w['condition']=='rain' and w.get('rain_forecast_lead_days')==2:reasons.append('D2_FORECAST_SEMIBUFFET_CANCELLED; POOL_NOT_AUTOMATICALLY_CLOSED')
 return reasons,room_key

def contract(a,s):
 eid=s['event_card_id'];base=dict(sku_id='C01-EVENT-'+eid,venue_id=s['venue_id'],label=next(x['record']['행사 · 상품명'] for x in s['sources'] if 'record' in x),
  billing_unit='order',billing_quantity=None,unit_price_krw=None,source_path='research/w44_c01/event_cards_sources.csv',source_line=s['sources'][0]['csv_line'],source_sha256=SOURCE_SHA,
  source_document=s['sources'][0]['record']['출처 (공식 · 당시 안내)'],source_checked_at=s['sources'][0]['record']['확인 시점'],
  price_status='AMOUNT_UNKNOWN',scenario_id=s['scenario_id'],snapshot_sha256=s['snapshot_sha256'],current_sale_confirmed=False,reservation_confirmed=False,transaction_confirmed=False,tax_status='UNKNOWN')
 if eid==S26.ID:
  p=S26.package(s,a.pid);base.update(source_path=S26.source()['path'],source_sha256=S26.SHA,tax_status='INCLUDED')
  if p:base.update(unit_price_krw=0,billing_quantity=1,price_status='SELECTED_SANTA_PACKAGE_INCLUDED_ADMISSION_NOT_NEW_SALE',included_in_package=p['package_id'])
  else:base['unknown_reason']='2026_STANDALONE_BASE_TICKET_UNCONFIRMED_NO_2025_PRICE_REUSE'
 elif eid==IDS[1]:
  p=a.vs.get('party_composition')
  if p and p['adult_count']==2 and len(p['children'])==1 and (s.get('entitlements') or {}).get(a.pid,{}).get('selected_package') is True:
   # Explicitly selected Santa room package: admission is part of the package total, settled once at 0 (never charged again).
   base.update(unit_price_krw=0,billing_quantity=1,price_status='SELECTED_SANTA_PACKAGE_INCLUDED_ADMISSION_NOT_NEW_SALE',included_in_package='SANTA_PKG_2025')
  elif p and p['adult_count']==2 and len(p['children'])==1:base.update(unit_price_krw=200000,billing_quantity=1,price_status='PRESS_RECORDED_TWO_ADULT_ONE_CHILD_GROUP_SIMULATION_REFERENCE')
  else:base['unknown_reason']='SOURCE_GROUP_2_ADULT_1_CHILD_NOT_MATCHED; NO_ADULT_ONLY_TICKET_PRICE'
 elif eid==IDS[3]:
  e=s['entitlements'].get(a.pid)
  if e and a.N<=e['included_people']:base.update(unit_price_krw=0,billing_quantity=1,price_status='SELECTED_VIRTUAL_PACKAGE_ENTITLEMENT_NOT_NEW_SALE')
  else:base['unknown_reason']='PACKAGE_COVERAGE_OR_EXTRA_PEOPLE_PRICE_UNCONFIRMED'
 else:base['unknown_reason']='2026_GOLDEN_NIGHT_PRICE_NOT_RECORDED; DO_NOT_BORROW_2025_PRICE'
 from . import hotel_catalog as H
 if H.enabled(a) and eid in (IDS[1],IDS[2]):
  # Pricing assumptions never relax party/reservation/date eligibility.
  count=a.N if eid==IDS[2] else 1
  unit=H.EVENT_PRICES[base['sku_id']] if eid==IDS[2] else base['unit_price_krw']
  if unit is not None:
   p=dict(base,unit_price_krw=unit,price_tier='SIMULATION_ASSUMPTION' if eid==IDS[2] else 'EXISTING_REFERENCE',price_status='EXPLICIT_GOLDEN_EVENT_PRICE_ASSUMPTION_79000_PER_PARTICIPANT_NOT_VERIFIED' if eid==IDS[2] else base['price_status'],billing_unit='person' if eid==IDS[2] else 'order')
   part=H.component(p,count,a,assumption='VIRTUAL_EVENT_ATTENDEE_PRICE_NOT_OBSERVED_AGE_OR_SALE')
   c=H.compose([part],a,'event');base.update(unit_price_krw=c['unit_price_krw'],billing_quantity=1,components=[part],catalog_policy=H.POLICY,catalog_sha256=H.SHA,price_tier=c['price_tier'],price_status=c['price_status'],discount_krw=c['discount_krw'])
   if base.get('unknown_reason'):base['source_price_limitation']=base.pop('unknown_reason')
 return base

@contextmanager
def install(sc):
 s=sc['scenario_snapshot'];eid=s['event_card_id'];day=sc['date'];oid='CARD_'+eid
 original_world=AD.World.engine_world;original_for=AD.engine_world_for;original_charge=AD.LG.charge;original_block=AD.LG.event_blocked;original_adjust=m4_event.event_adjustment;original_annotate=M4._annotate;original_breakfast=AD.breakfast_step
 def world(w,t):
  result=original_world(w,t)
  if eid in (IDS[0],'NONE'):return result
  sessions=s['sessions'] or [['00:00','00:01']];fits=[x for x in sessions if max(t,minute(x[0]))+(s['duration_min'] or 1)<=minute(x[1])]
  window=(fits or [sessions[-1]])[0]
  label=s['sources'][0]['record']['행사 · 상품명']
  offer=AD.WD.offer(oid,label,'event',s['venue_id'],window={'start':window[0],'end':window[1]},duration=s['duration_min'] or 1,price=None,grade=s['sources'][0]['record']['구분'],
    meal_fraction=s['meal_fraction'],quality='standard' if s['meal_fraction'] else 'none',
    menu_tags=['bbq','beer'] if eid==IDS[2] else ['buffet','variety'] if eid==IDS[3] else ['coffee','juice'] if eid==S26.ID else ['hot_chocolate'],
    garden=True,swimming=(eid==IDS[3]),indoor=False,novelty=0,seasonal=True,available=active(s,day) and not s['missing_fields'],price_note='Card-source facts and explicit virtual execution assumptions remain separate')
  offer['service_contract']=dict(venue_id=s['venue_id'],service_window=offer['window'],candidate_available_at=max(t,minute(window[0])),planning_viability='FUTURE_SERVICE_ONLY' if t<minute(window[0]) else 'AVAILABLE_NOW',source_state=s['contract_status'],source_sha256=SOURCE_SHA,scenario_id=s['scenario_id'],snapshot_sha256=s['snapshot_sha256'],reservation_state='UNKNOWN_NOT_BOOKED',duration_source='EXPLICIT_SCENARIO_ASSUMPTION')
  if eid==S26.ID:offer['service_contract'].update(source_sha256=S26.SHA,duration_source='OFFICIAL_PACKAGE_SESSION_70_MIN')
  if eid in (IDS[1],S26.ID):scenario_conditions.apply_session(offer,s,day,t)
  result['offers'].append(offer);return result
 def for_actor(a,w,t):
  result=original_for(a,w,t)
  if eid==IDS[0]:
   result['offers']=[wine_admission.bind(a,o,s,t) if o['id']=='WINE_FAIR' else o for o in result['offers']]
  for o in result['offers']:
   o.setdefault('service_contract',{}).update(scenario_weather=copy.deepcopy(s['weather']),weather_effect='ADVISORY_ONLY; NO_UNVERIFIED_CLOSURE_OR_PREFERENCE_BONUS',scenario_id=s['scenario_id'])
   if o['id']!=oid:continue
   if eid in (IDS[1],S26.ID):
    binding=(s['assumptions'].get('booked_sessions') or {}).get(a.pid,{})
    bound=s
    if eid==S26.ID and binding.get('date')==day:
     bound=dict(s,sessions=[x for x in s['sessions'] if x[0]==binding.get('start')])
    scenario_conditions.apply_session(o,bound,day,t,AD.SP.travel_min(a.loc,s['venue_id']))
    if bound is not s:
     o['service_contract'].update(event_session_index=3 if binding['start']=='15:20' else 4,reservation_state='OPERATOR_BOOKED_SESSION_ASSUMPTION')
   why,key=eligibility(a,s);c=contract(a,s)
   o.update(sku_contract=c,sku_id=c['sku_id'],price_status=c['price_status'],price_pp_krw=None if c['unit_price_krw'] is None else c['unit_price_krw']/a.N)
   if why:o.update(available=False,status='; '.join(why))
   o['service_contract'].update(eligible=not why,eligibility_reasons=why,blocked_reason='; '.join(why) or None,price_status=c['price_status'],room_night_key=key)
  return result
 def blocked(a,key):return None if key==oid else original_block(a,key)
 def charge(a,code,kind,loc,offer=None,in_package=False):
  if (offer or {}).get('santa_package_breakfast') and eid==S26.ID:
   p=S26.actor_package(a);key=p['package_id']+'_BREAKFAST'
   a.visit_history.setdefault('hotel_entitlement_usage',{})[SANTA_BF_KEY]=1
   a.visit_history['hotel_entitlement_usage'][key]=1
   venue='GRAND_CLUB_LOUNGE' if (offer or {}).get('id')=='SANTA_2026_CLUB_BREAKFAST' else 'THE_BUFFET'
   c=dict(sku_id=key,venue_id=venue,label=offer['label'],billing_unit='included_benefit',billing_quantity=1,unit_price_krw=0,included_in_package=p['package_id'],price_status='PACKAGE_INCLUDED_NOT_NEW_REVENUE',source_path=S26.source()['path'],source_sha256=S26.SHA,tax_status='INCLUDED')
   return dict(status='포함',krw=0,grade='공식 계약 · 가상 사용',basis='패키지 조식 권리 사용 · 별도 구매 아님',sku_contract=c,hotel_entitlement_key=key,santa_package_id=p['package_id'],auto_charge=False)
  if (offer or {}).get('santa_package_breakfast'):
   a.visit_history.setdefault('hotel_entitlement_usage',{})[SANTA_BF_KEY]=1
   return dict(status='포함',krw=0,grade='가정',basis='산타 객실 패키지 포함 조식 · 패키지 총액에 포함 · 추가 결제 0원',hotel_entitlement_key=SANTA_BF_KEY,santa_package_id=(S26.actor_package(a) or {}).get('package_id','SANTA_PKG_2025'),auto_charge=False)
  if eid==IDS[0] and (offer or {}).get('id')=='WINE_FAIR':
   if str(code).endswith((':check',':full')):return dict(status='구매 없음',krw=0,basis='안내 확인 · 참가/구매 아님')
   return wine_admission.charge(offer)
  if (offer or {}).get('id')!=oid:return original_charge(a,code,kind,loc,offer,in_package)
  if str(code).endswith((':check',':full')):return dict(status='구매 없음',krw=0,basis='행사 정보 확인 · 실제 참가/구매 아님')
  c=offer['sku_contract'];why,key=eligibility(a,s)
  if why:return dict(status='가격 미정',krw=None,sku_contract=c,basis='; '.join(why),auto_charge=False)
  if c['unit_price_krw'] is None:return dict(status='가격 미정',krw=None,sku_contract=c,basis=c.get('unknown_reason','EVENT_AMOUNT_UNKNOWN'),auto_charge=False)
  out=dict(status='포함' if eid==IDS[3] or c.get('included_in_package') else '유료',krw=c['unit_price_krw']*c['billing_quantity'],per='건',grade=s['sources'][0]['record']['구분'],sku_contract=c,basis=f"기존 행사 자료 가상 계산 {c['unit_price_krw']}원 × {c['billing_quantity']}건; 예약/실결제 미확인")
  if eid in (IDS[3],S26.ID):
   out['scenario_event_usage']=dict(event_card_id=eid,room_night_key=key,date=day);a.visit_history.setdefault('scenario_event_usage',[]).append(out['scenario_event_usage'])
  return out
 SANTA_BF_KEY='SANTA_PKG_2025_INCLUDED_BREAKFAST_ONCE' if eid!=S26.ID else 'SANTA_2026_INCLUDED_BREAKFAST_ONCE'
 santa_bf=[]
 def santa_breakfast_due(a):
  # Explicit Santa package only: its breakfast is the first breakfast of the stay (the morning after the package night), used once.
  if eid==S26.ID:return bool(S26.actor_package(a) and a.stay and a.checked_in and not a.checked_out and day==S26.breakfast_day(s) and not a.visit_history.get('hotel_entitlement_usage',{}).get(SANTA_BF_KEY))
  return (eid==IDS[1] and (s.get('entitlements') or {}).get(a.pid,{}).get('selected_package') is True and a.stay and a.checked_in and not a.checked_out
          and '2025-12-20'<=day<='2025-12-26' and not a.visit_history.get('hotel_entitlement_usage',{}).get(SANTA_BF_KEY))
 from ..operator_world_v1_1 import turn_candidate as TC
 original_turn_world=TC.turn_world
 def turn_world(*args,**kw):
  w,excluded=original_turn_world(*args,**kw)
  if not santa_bf or (args[0] if args else kw.get('turn'))!='breakfast':return w,excluded
  w=copy.deepcopy(w)
  for o in w['offers']:
   if o['id']=='BREAKFAST_BUFFET':
    if eid==S26.ID:
     p=S26.actor_package(santa_bf[-1])
     if p['breakfast_venue']=='CLUB_WEEKDAY_BUFFET' and date.fromisoformat(day).weekday()>=5:
      o.update(id='SANTA_2026_CLUB_BREAKFAST',venue='GRAND_CLUB_LOUNGE',label='클럽 라운지 조식 · Joulua 포함',available=True,in_package=True,price_pp_krw=0,santa_package_breakfast=True,hc_contract=False)
      o.pop('sku_contract',None);continue
    # Included in the selected package: offered at 0 even where no 2025 buffet sale record exists (no amount is invented).
    o.update(available=True,status=None,in_package=True,price_pp_krw=0,label='더뷔페 조식 · 산타 패키지 포함',santa_package_breakfast=True)
    o.setdefault('service_contract',{}).update(eligible=True,blocked_reason=None,price_status='SANTA_PACKAGE_INCLUDED_BREAKFAST_NOT_NEW_SALE',package_id=(S26.actor_package(santa_bf[-1]) or {}).get('package_id','SANTA_PKG_2025'))
  return w,excluded
 def breakfast(a,world,t):
  if santa_breakfast_due(a):
   santa_bf.append(a)
   try:
    own=copy.copy(world);own.sc=dict(world.sc,breakfast_in_package=True,breakfast_entitlement_override=True)
    return original_breakfast(a,own,t)
   finally:santa_bf.pop()
  if eid==IDS[3] and a.pid in s['entitlements']:
   # Source package explicitly excludes breakfast. Do not alter other agents.
   own_world=copy.copy(world);own_world.sc=dict(world.sc,breakfast_in_package=False,breakfast_entitlement_override=False)
   return original_breakfast(a,own_world,t)
  return original_breakfast(a,world,t)
 def adjustment(o,terms,memory):
  if o['id']==oid:
   own_memory={'prior_attendance':[], 'program_relation':'NOT_WINE_PROGRAM', 'direct_repeat_intention_fact_ids':[],
    'meal_service_status':'BUNDLED_SEMIBUFFET_WITH_DECLARED_MEAL_FRACTION' if s['meal_fraction']>=.8 else 'TASTING_CONFIRMED_MEAL_PURCHASE_UNCONFIRMED'}
   delta,trace=original_adjust(o,terms,own_memory);trace['event_card_id']=eid;trace['policy']='Existing M4 meal-service interpretation reused; no wine affinity or repeat intention borrowed';return delta,trace
  return original_adjust(o,terms,memory)
 def annotate(*args,**kw):
  out=original_annotate(*args,**kw);out['m4']['scenario_id']=s['scenario_id'];out['m4']['scenario_snapshot_sha256']=s['snapshot_sha256'];out['m4']['scenario_candidate_evaluations']=out.pop('scenario_candidate_evaluations',[]);return out
 with ExitStack() as stack:
  for obj,key,value in [(TC,'turn_world',turn_world),(AD,'breakfast_step',breakfast),(AD.World,'engine_world',world),(AD,'engine_world_for',for_actor),(AD.LG,'event_blocked',blocked),(AD.LG,'charge',charge),(m4_event,'event_adjustment',adjustment),(M4,'_annotate',annotate)]:stack.enter_context(patch.object(obj,key,value))
  stack.enter_context(patch.dict(AD.ENGINE_LOC,{oid:s['venue_id']}));stack.enter_context(patch.dict(AD.ENGINE_DOMAIN,{oid:'식사' if s['meal_fraction']>=.8 else '행사'}));stack.enter_context(patch.dict(AD.VENUE_KO,{oid:s['sources'][0]['record']['행사 · 상품명']}))
  if eid==S26.ID:stack.enter_context(patch.dict(AD.ENGINE_LOC,{'SANTA_2026_CLUB_BREAKFAST':'GRAND_CLUB_LOUNGE'}))
  stack.enter_context(scenario_conditions.install(sc,oid))
  yield

def run_one(pid,sc,inputs):
 with C.install(sc['date']),install(sc):return M4.run_one(pid,sc,inputs)
def run_many(ids,sc,inputs):
 with C.install(sc['date']),install(sc):
  result=M4.run_many(ids,sc,inputs);result['shared_world']['scenario_snapshot_sha256']=sc['scenario_snapshot']['snapshot_sha256'];return result
