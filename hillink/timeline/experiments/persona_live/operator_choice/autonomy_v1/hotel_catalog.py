"""Versioned hotel products, explicit scenario quantities and immutable price quotes.

No personal coefficients, global choice policy or provider calls live here.
"""
import copy,json,hashlib,re,math,random
from pathlib import Path
from datetime import date
import menu as SOURCE_MENU
from . import party_orders as PO
from . import meal_basket as MB
POLICY='C01_HOTEL_CATALOG_V1'
PATH=Path(__file__).with_name('hotel_catalog.json')
DATA=json.loads(PATH.read_text());SHA=hashlib.sha256(PATH.read_bytes()).hexdigest()
from . import official_contracts as OC
from . import package_benefits as PB
BASE_DATA=copy.deepcopy(DATA);BASE_SHA=SHA
DATA,SHA=OC.load(DATA,SHA)
from . import historical_prices as HIST
DATA,SHA=HIST.load(DATA,SHA)   # 11/03: 2025 더뷔페 조식·석식 과거 참고가 (별도 overlay)
from . import sauna_policy as SA
DATA,SHA=SA.load(DATA,SHA)
# Preserve legacy order identity when unrelated reviewed items are appended.
# Execution provenance still carries the complete effective catalog SHA.
PRE_REVIEWED_SHA=SHA
PRE_REVIEWED_SKUS=frozenset(p['sku_id'] for p in DATA['products'])
DATA,SHA=OC.reviewed_additions(DATA,SHA)
DATA,SHA=OC.reviewed_conditions(DATA,SHA)
BY={p['sku_id']:p for p in DATA['products']}
EVENT_PRICES={'C01-EVENT-PIZZA_HILL_GOLDEN_NIGHT_2026':79000,'C01-EVENT-SANTA_KIDS_VILLAGE_2025':200000}
MAIN_ROLES={'MAIN','SNACK','DRINK','ACTIVITY','BREAKFAST','EVENT_ADMISSION'}
TIERS=('OFFICIAL','EXISTING_REFERENCE','COMPARABLE_ESTIMATE','SIMULATION_ASSUMPTION')
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=list).encode()).hexdigest()
def enabled(a):
 scenario=getattr(a,'sc',None)
 return isinstance(scenario,dict) and scenario.get('catalog_policy')==POLICY
def options(a):return a.sc.get('catalog_options') or {}
RESEARCH_OPEN_VENUES={'GEUMRYONG':'18:00','MOEGI':'18:00','ONDAL':'18:00','MYONGWOLGWAN':'17:30'}   # official dinner start (candidate_services.OFFICIAL_DINNER)

def discount_allowed(p):
 return p.get('discount_policy') not in ('NO_DISCOUNT_OR_POINTS','NO_ADDITIONAL_DISCOUNT')

def validate_discount(p,opts):
 key=p.get('pricing_parent_sku_id',p['sku_id']);source=BY.get(key,p)
 if not discount_allowed(source):
  if opts.get('discount_percent',{}).get(key,0) or opts.get('price_overrides',{}).get(key,source['unit_price_krw'])<source['unit_price_krw']:
   raise ValueError('HC_SOURCE_DISCOUNT_NOT_ALLOWED')

def validate(opts,ids):
 if opts is None:return {}
 if not isinstance(opts,dict) or set(opts)-{'room_products','purchase_orders','virtual_reservations','paid_breakfast_ird_customers','price_overrides','discount_percent','price_sensitivity_factor','operating_overrides','dinner_plan_lead_min','service_open_overrides','research_dinner_duration_min'}:raise ValueError('HC_OPTIONS_INVALID')
 o=copy.deepcopy(opts)
 for key in ('price_overrides','discount_percent'):
  if not isinstance(o.get(key,{}),dict):raise ValueError('HC_PRICE_MAP_INVALID')
 for key in ['room_products','purchase_orders','virtual_reservations']:
  if key in o and (not isinstance(o[key],dict) or set(o[key])-set(ids)):raise ValueError('HC_CUSTOMER_SCOPE_INVALID')
 if set(o.get('paid_breakfast_ird_customers',[]))-set(ids):raise ValueError('HC_BREAKFAST_CUSTOMER_INVALID')
 for pid,sku in o.get('room_products',{}).items():
  if sku not in BY or BY[sku]['role']!='ROOM':raise ValueError('HC_ROOM_PRODUCT_INVALID')
 for sku,amount in o.get('price_overrides',{}).items():
  if sku not in BY and sku not in EVENT_PRICES or type(amount)!=int or amount<0 or amount==0 and BY.get(sku,{}).get('unit_price_krw',1)!=0:raise ValueError('HC_PRICE_OVERRIDE_INVALID')
 for sku in set(o.get('price_overrides',{}))|{k for k,v in o.get('discount_percent',{}).items() if v}:
  if BY.get(sku,{}).get('price_confirmed') is False and BY[sku].get('charge_policy')=='PRICE_UNKNOWN_UNLESS_INCLUDED_USE_KEPT':raise ValueError('HC_PRICE_UNCONFIRMED_NOT_EDITABLE')
  if sku in BY:validate_discount(BY[sku],o)
 for sku,percent in o.get('discount_percent',{}).items():
  if sku not in BY and sku not in EVENT_PRICES or type(percent) not in (int,float) or not math.isfinite(percent) or not 0<=percent<=100:raise ValueError('HC_DISCOUNT_INVALID')
 if any(k not in BY or not BY[k].get('requires_operating_override') for k in o.get('operating_overrides',[])):raise ValueError('HC_OPERATING_OVERRIDE_SCOPE_INVALID')
 # Research-only operator scenarios (default off): how far ahead a dinner may be planned, and virtual earlier dinner openings.
 if 'dinner_plan_lead_min' in o and (type(o['dinner_plan_lead_min'])!=int or not 45<=o['dinner_plan_lead_min']<=180):raise ValueError('HC_DINNER_PLAN_LEAD_INVALID')
 so=o.get('service_open_overrides',{})
 if not isinstance(so,dict) or any(v not in RESEARCH_OPEN_VENUES or not isinstance(t,str) or not re.fullmatch(r'(1[6-7]):(00|30)',t) or t>=RESEARCH_OPEN_VENUES[v] for v,t in so.items()):raise ValueError('HC_SERVICE_OPEN_OVERRIDE_INVALID')
 dd=o.get('research_dinner_duration_min',{})   # model-assumption sensitivity (dining length), never an operator lever
 if not isinstance(dd,dict) or any(v not in RESEARCH_OPEN_VENUES or type(m)!=int or not 60<=m<=180 for v,m in dd.items()):raise ValueError('HC_RESEARCH_DINNER_DURATION_INVALID')
 factor=o.get('price_sensitivity_factor',1)
 if type(factor) not in (int,float) or not .5<=factor<=2:raise ValueError('HC_SENSITIVITY_FACTOR_INVALID')
 for pid,orders in o.get('purchase_orders',{}).items():
  if not isinstance(orders,list):raise ValueError('HC_ORDERS_INVALID')
  for order in orders:
   if set(order)!={'date','venue_id','service_period','items'} or not order['items']:raise ValueError('HC_ORDER_FIELDS_INVALID')
   date.fromisoformat(order['date'])
   for i in order['items']:
    if set(i)!={'sku_id','quantity'} or i['sku_id'] not in BY or BY[i['sku_id']]['venue_id']!=order['venue_id'] or type(i['quantity'])!=int or not 1<=i['quantity']<=32:raise ValueError('HC_ORDER_ITEM_INVALID')
   if order['service_period']!='booking' and all(BY[i['sku_id']]['role'] in ('ADDON','CHILD_COMPONENT') for i in order['items']):raise ValueError('HC_ADDON_WITHOUT_MAIN_ORDER')
 return o

def price(p,opts=None):
 p=copy.deepcopy(p);opts=opts or {}
 validate_discount(p,opts)
 key=p.get('pricing_parent_sku_id',p['sku_id']);original=p['unit_price_krw'];explicit=key in opts.get('price_overrides',{})
 if explicit:
  p.update(unit_price_krw=opts['price_overrides'][key],price_tier='SIMULATION_ASSUMPTION',price_status='EXPLICIT_RUN_PRICE_OVERRIDE_NOT_CONFIRMED',price_override_source='OPERATOR_SCENARIO')
 if not explicit and p['price_tier'] in ('COMPARABLE_ESTIMATE','SIMULATION_ASSUMPTION') and p['unit_price_krw']:
  p['unit_price_krw']=round(p['unit_price_krw']*opts.get('price_sensitivity_factor',1))
 before=p['unit_price_krw'];percent=opts.get('discount_percent',{}).get(key,0)
 if percent:
  from decimal import Decimal,ROUND_HALF_UP
  p['unit_price_krw']=int((Decimal(before)*(Decimal(100)-Decimal(str(percent)))/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
  p.update(price_tier='SIMULATION_ASSUMPTION',price_status='OPERATOR_DISCOUNT_SCENARIO_NOT_CONFIRMED')
 if explicit or percent:
  p['price_trace']=dict(sku_id=p['sku_id'],catalog_unit_price_krw=original,scenario_unit_price_before_discount_krw=before,discount_percent=percent,effective_unit_price_krw=p['unit_price_krw'],rounding='KRW_HALF_UP',source='NEW_RUN_OPERATOR_INPUT')
  p['discount_krw']=before-p['unit_price_krw']
 return p

def sessions(p):
 result=[]
 for part in p['source_service_windows'].split(','):
  if not part:continue
  a,b=part.split('-');hm=lambda s:int(s[:2])*60+int(s[3:])
  lo,hi=hm(a),hm(b);result.append((lo,hi if hi>lo else hi+1440))
 return result

def day_ok(p,day):
 d=date.fromisoformat(day)
 if p.get('valid_from') and day<p['valid_from'] or p.get('valid_until') and day>p['valid_until']:return False
 days,hol,fixed=SOURCE_MENU._parse_days(p['source_day_rule'])
 if fixed is not None:return d.strftime('%m-%d') in fixed
 if days is None:return True
 if days=='weekday':return d.weekday() in (6,0,1,2,3)
 if days=='weekend':return d.weekday() in (4,5)
 holiday=SOURCE_MENU.Menu.is_holiday(d)
 if hol=='+' and holiday:return True
 return not (hol=='-' and holiday) and d.weekday() in days

def eligible(p,a,t,duration=30,period=None,allow_components=False):
 from . import santa_2026 as S26
 santa=S26.actor_package(a)
 why=OC.restrictions(p,a,t,period)+PB.exclusions(p,a,t,duration)+(SA.reasons(p,a,t,duration) if p.get('sauna_policy') else []);day=a.sc['date'];unit=p['source_unit'];party=PO.party(a);current=a.stay and a.checked_in and not a.checked_out
 if not day_ok(p,day):why.append('DATE_OR_SALE_DAY')
 if p.get('reviewed_available_from') and day<p['reviewed_available_from']:why.append('BEFORE_REVIEWED_MENU_ADMISSION_NOT_OFFICIAL_SALE_START')
 ov=(options(a).get('service_open_overrides') or {}).get(p.get('venue_id'));ses=[(min(lo,int(ov[:2])*60+int(ov[3:])) if ov and lo>=960 else lo,hi) for lo,hi in sessions(p)]   # research: virtual earlier dinner opening
 if santa and santa['sauna'] and p['sku_id']=='HC-GRAND-LOUNGE-278':ses=[(1050,1170)]
 if ses and not any(lo<=t and t+duration<=hi for lo,hi in ([(lo,1260) for lo,hi in ses] if p.get('source_line') in (189,190,191) else ses)):why.append('SERVICE_OR_COMPLETION_WINDOW')
 if p.get('source_line') in (189,190,191) and t>1170:why.append('SOURCE_LAST_ORDER_PASSED')
 if p.get('requires_operating_override') and p['sku_id'] not in options(a).get('operating_overrides',[]):why.append('OPERATING_REOPENING_UNKNOWN_EXPLICIT_VIRTUAL_OVERRIDE_REQUIRED')
 if p['venue_id']=='GRAND_CLUB_LOUNGE':
  extra=S26.lounge_reasons(a,p,t,duration)
  if extra is not None:
   why+=extra
   if not current:why.append('CURRENT_GUEST_REQUIRED')
  elif a.B!='GRAND' or not getattr(a,'club',False) or not current:why.append('GRAND_CLUB_ROOM_REQUIRED')
 if p['venue_id']=='DOUGLAS_LOUNGE' and (a.B!='DOUGLAS' or not current or a.N>3):why.append('DOUGLAS_LOUNGE_COVERAGE_UNKNOWN')
 if p['venue_id']=='KIDSCLUB' and (not party or not party['children'] or any(c.get('age_months') is None or not 12<=c['age_months']<72 for c in party['children'])):why.append('KIDSCLUB_AGE_BAND_REQUIRED')
 if p['role']=='ROOM':
  if not a.stay:why.append('OVERNIGHT_REQUIRED')
  if a.B!=p['venue_id']:why.append('BUILDING_MISMATCH')
  if p['billing_unit']=='room_bundle' and a.vs['nights']!=2:why.append('ROOM_BUNDLE_TWO_NIGHTS_REQUIRED')
 if p['role'] in {'ADDON','CHILD_COMPONENT'} and not allow_components:why.append('REQUIRES_PARENT_ORDER_NOT_STANDALONE')
 if p['role'] in {'GROUP_RESERVATION','LEGACY_BASKET'}:why.append('SPECIAL_GROUP_OR_LEGACY_AGGREGATE_NOT_STANDALONE')
 if p['venue_id'] in {'POOL','SAUNA','RIVERPARK','GOLF_CLUB','TENNEZ_PARK','WALKEE','ROOM_MEAL','FOREST_PARK','SKYARD'} and not current and p['role']!='ROOM':why.append('CURRENT_GUEST_REQUIRED')
 weather=(a.sc.get('scenario_snapshot') or {}).get('weather') or {}
 if p['venue_id']=='RIVERPARK' and weather.get('explicit_pool_safety_closure'):why.append('EXPLICIT_POOL_SAFETY_CLOSURE')
 if p.get('source_line') in (224,225) and weather.get('condition')=='rain' and weather.get('rain_forecast_lead_days')==2:why.append('SEMIBUFFET_CANCELLED_POOL_REMAINS_SEPARATE')
 if p['venue_id']=='FOREST_PARK' and PB.selected(a) and a.sc['date'] in PB.FAIR_DATES and not p.get('package_benefit_variant'):why.append('FOREST_GENERAL_USE_REPLACED_BY_WINE_FAIR')
 if p['venue_id']=='WINE_FAIR':why.append('USE_SEPARATE_EVENT_ADMISSION_CONTRACT')
 if p['venue_id']=='ROOM_MEAL' and p['role']=='BREAKFAST' and a.pid not in options(a).get('paid_breakfast_ird_customers',[]):why.append('PAID_IRD_BREAKFAST_REQUIRES_EXPLICIT_OPT_IN')
 if p.get('service_periods') and period not in p['service_periods']:why.append('NATIVE_SOURCE_MEAL_CONTRACT_PERIOD')
 if period=='breakfast' and p['venue_id']=='THE_BUFFET' and not p['label'].startswith('조식'):why.append('MEAL_PERIOD')
 if period=='lunch' and p['venue_id']=='THE_BUFFET' and not p['label'].startswith('중식'):why.append('MEAL_PERIOD')
 if period=='dinner' and p['venue_id']=='THE_BUFFET' and not p['label'].startswith('석식'):why.append('MEAL_PERIOD')
 if period=='breakfast' and p['venue_id']!='THE_BUFFET' and p['role']!='BREAKFAST':why.append('MEAL_PERIOD')
 if period!='breakfast' and p['role']=='BREAKFAST':why.append('MEAL_PERIOD')
 if p.get('requires_reservation') and p['sku_id'] not in options(a).get('virtual_reservations',{}).get(a.pid,[]):why.append('RESERVATION_NOT_CONFIRMED_OR_VIRTUALLY_DECLARED')
 if p['venue_id'] in {'WALKEE','TENNEZ_PARK'} and p['role']=='ACTIVITY' and p['sku_id'] not in options(a).get('virtual_reservations',{}).get(a.pid,[]):why.append('PROGRAM_OPERATION_AND_RESERVATION_DECLARATION_REQUIRED')
 if '동반 불가' in unit and a.C.get('kids'):why.append('CHILDREN_NOT_ELIGIBLE')
 required_age=20 if '20세 이상' in unit else 17 if p['venue_id']=='SAUNA' or '17세 이상' in unit else 6 if '6세 이상' in unit or '6~10세' in unit else None
 if required_age and p['venue_id']!='SAUNA' and a.C.get('kids') and (not party or any(c.get('age_months') is None or c['age_months']<required_age*12 for c in party['children'])):why.append('AGE_QUALIFICATION_UNKNOWN_OR_INELIGIBLE')
 if '6~10세' in unit and (not party or not party['children'] or any(c.get('age_months') is None or not 72<=c['age_months']<132 for c in party['children'])):why.append('KIDS_PROGRAM_AGE_REQUIRED')
 if (p['venue_id']=='LUX_BAR' or p.get('age_restricted_alcohol') or any(w in p['label'].lower() for w in ('beer','wine','맥주','칵테일','하이볼'))) and '무알코올' not in p['label'] and a.C.get('kids'):why.append('ALCOHOL_PARTY_QUALIFICATION_UNKNOWN')
 if p.get('source_line') in (233,234):
  if p['source_line']==234 and a.B!='VISTA' or p['source_line']==233 and a.B=='VISTA':why.append('POOL_BUILDING')
 if p.get('source_line')==235 and a.B=='VISTA':why.append('GRAND_POOL_REFERENCE_NOT_VISTA')
 if p.get('source_line')==242 and not OC.skyard_included(a,BY.get(options(a).get('room_products',{}).get(a.pid,''),{})):why.append('FREE_SKYARD_COVERAGE_NOT_PRESENT')
 if p.get('source_line')==243 and OC.skyard_included(a,BY.get(options(a).get('room_products',{}).get(a.pid,''),{})):why.append('USE_INCLUDED_SKYARD_NOT_PAID_SKU')
 if p['role'] in ('SNACK','DRINK') and period in ('lunch','dinner') and not allow_components:why.append('DRINK_OR_SNACK_NOT_A_MAIN_MEAL')
 if p['role']=='CHILD_COMPONENT' and not party:why.append('CHILD_COMPOSITION_REQUIRED')
 if p['venue_id']=='TENNEZ_PARK' and a.N>6:why.append('MAX_TENNIS_PARTY_SIX')
 if p['venue_id']=='TENNEZ_PARK' and date.fromisoformat(day).month in (12,1,2) and t+duration>1080:why.append('TENNIS_WINTER_CLOSE_1800')
 if p['minimum_quantity']>a.N and p['role'] not in {'ADDON','CHILD_COMPONENT'}:why.append('MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY')
 if p['billing_unit']=='set':
  size=re.search(r'세트.*?(\d+)인',unit)
  if size and int(size[1])!=a.N:why.append('FIXED_SET_PARTY_SIZE')
 return why

def modeled_party(a):
 p=PO.party(a)
 if p:return p
 if getattr(a,'C',{}).get('kids'):
  adults=min(2,max(1,a.N-1))
  return dict(adult_count=adults,children=[dict(age_months=None,school_stage=None) for _ in range(a.N-adults)],source='LEGACY_PARTY_SPLIT_SCENARIO_ASSUMPTION_NOT_OBSERVED')
 return None

def quantity(p,a):
 unit=p['billing_unit'];party=modeled_party(a)
 if p.get('sauna_policy'):return SA.participants(a)
 if p['venue_id']=='WALKEE' and '6~10세' in p['source_unit']:return len(party['children']) if party else 0
 if p['role']=='CHILD_COMPONENT':return len(party['children']) if party else 0
 if unit=='person':return party['adult_count'] if party and (p['category']=='F&B' or p['venue_id'] in ('THEATRE_OF_LIGHT','RIVERPARK')) else a.N
 if unit=='portion':return a.N-sum(c.get('age_months') is not None and c['age_months']<36 for c in party['children']) if party else a.N
 if unit=='pizza':
  servings=6 if '세이스' in p['label'] else 3 if re.search(r'\bL\b',p['label']) else 2
  if '콰트로' in p['label']:servings=4
  return math.ceil(a.N/servings)
 return 1

def component(p,q,a,*,assumption=None):
 p=price(SA.product(p,a),options(a));c={k:copy.deepcopy(v) for k,v in p.items() if k not in ('change_history',)}
 c.update(billing_quantity=q,quantity_observed=False,order_quantity_basis=assumption or 'COMMON_VIRTUAL_ORDER_NOT_OBSERVED',
  applicability_status='SIMULATION_PRODUCT_CONTRACT_NOT_BOOKING',current_sale_confirmed=False,reservation_confirmed=False,transaction_confirmed=False,
  party_composition=copy.deepcopy(modeled_party(a)),catalog_sha256=SHA,input_provenance='OPERATOR_SIMULATION_NOT_REVIEW_FACT',tax_status='UNKNOWN')
 return c

def order_identity(parts):
 identity=copy.deepcopy(parts)
 for p in identity:
  if p['sku_id'] in PRE_REVIEWED_SKUS or p.get('pricing_parent_sku_id') in PRE_REVIEWED_SKUS:
   p['catalog_sha256']=PRE_REVIEWED_SHA
  else:
   p.pop('catalog_sha256',None)
 return 'HC-ORDER-'+digest(identity)[:20]

def compose(parts,a,period):
 if not parts:return None
 total=sum(p['unit_price_krw']*p['billing_quantity'] for p in parts)
 tier=max((p['price_tier'] for p in parts),key=TIERS.index)
 label=('더뷔페 '+{'breakfast':'조식','lunch':'점심','dinner':'저녁'}.get(period,period)+' 식사') if parts[0]['venue_id']=='THE_BUFFET' else ' + '.join(p['label'] for p in parts)
 return dict(sku_id=order_identity(parts),label=label,venue_id=parts[0]['venue_id'],
  unit_price_krw=total,billing_quantity=1,billing_unit='order',components=parts,catalog_policy=POLICY,price_tier=tier,price_status='COMPOSED_'+tier,
  tax_status='UNKNOWN',source_path='hotel_catalog.json',source_sha256=SHA,catalog_sha256=SHA,quantity_observed=False,
  participant_count=a.N,service_period=period,discount_krw=sum(p.get('discount_krw',0)*p['billing_quantity'] for p in parts),included_benefit=None,quantity_assumptions=dict(copy.deepcopy(DATA['assumptions']),infant_meal_policy='Known infants under 36 months share food by scenario default; no independent adult main unless explicitly ordered. This is not a free-menu policy.'),
  input_provenance='EXPLICIT_SIMULATION_ORDER_NOT_OBSERVED_FACT',current_sale_confirmed=False,reservation_confirmed=False,transaction_confirmed=False)

def explicit_order(a,venue,period,t,duration):
 orders=[x for x in options(a).get('purchase_orders',{}).get(a.pid,[]) if (x['date'],x['venue_id'],x['service_period'])==(a.sc['date'],venue,period)]
 if not orders:return None
 if len(orders)!=1:raise ValueError('HC_DUPLICATE_ORDER')
 parts=[];parent=False
 for i in orders[0]['items']:
  p=BY[i['sku_id']];why=eligible(p,a,t,duration,period,allow_components=True)
  why=[r for r in why if r!='MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY']
  if p.get('sauna_policy') and i['quantity']>SA.participants(a):why.append('SAUNA_PARTICIPANTS_EXCEED_ELIGIBLE_AGES')
  if i['quantity']<p['minimum_quantity']:why.append('SOURCE_MINIMUM_ORDER_QUANTITY')
  if why:raise ValueError('HC_ORDER_INELIGIBLE:'+p['sku_id']+':'+','.join(why))
  parent|=p['role'] not in ('ADDON','CHILD_COMPONENT');parts.append(component(p,i['quantity'],a,assumption='EXPLICIT_VIRTUAL_MIXED_ORDER_QUANTITY'))
 if not parent:raise ValueError('HC_ADDON_WITHOUT_MAIN_ORDER')
 for p in parts:
  if p.get('required_parent_sku_ids') and not set(p['required_parent_sku_ids'])&{x['sku_id'] for x in parts if x is not p}:raise ValueError('HC_REQUIRED_PARENT_PRODUCT_MISSING')
  if p.get('required_parent_semantic') and not any(p['required_parent_semantic'] in x['label'] for x in parts if x is not p):raise ValueError('HC_REQUIRED_PARENT_SEMANTIC_MISSING')
 # Upgrade quantities refer to existing included drinks, never extra servings.
 upgrades=sum(p['billing_quantity'] for p in parts if p.get('upgrade_pool')=='included_drinks')
 drinks=sum(p['billing_quantity']*p.get('included_components',{}).get('drinks',0) for p in parts if isinstance(p.get('included_components'),dict))
 if upgrades>drinks:raise ValueError('HC_UPGRADES_EXCEED_INCLUDED_DRINKS')
 for p in parts:
  if p.get('maximum_per_parent_unit') and not p.get('upgrade_pool'):
   available=sum(x['billing_quantity'] for x in parts if x['sku_id'] in p.get('required_parent_sku_ids',[]))
   if p['billing_quantity']>available*p['maximum_per_parent_unit']:raise ValueError('HC_ADDON_EXCEEDS_PARENT_UNITS')
 if venue=='THE_BUFFET':
  if sum(p['billing_quantity'] for p in parts)>a.N:raise ValueError('HC_BUFFET_ADMISSIONS_EXCEED_PARTY')
  party=PO.party(a)
  if party:
   adults=sum(p['billing_quantity'] for p in parts if p.get('age_band')=='ADULT')
   if adults>party['adult_count']+sum(c.get('school_stage')=='secondary' for c in party['children']):raise ValueError('HC_BUFFET_ADULT_COHORT_EXCEEDED')
   kids=sum(p['billing_quantity'] for p in parts if p['role']=='CHILD_COMPONENT')
   eligible_kids=sum(c.get('age_months') is not None and c['age_months']>=36 and c.get('school_stage') in ('preschool','elementary') for c in party['children'])
   if kids>eligible_kids:raise ValueError('HC_BUFFET_CHILD_COHORT_UNCONFIRMED_OR_EXCEEDED')
 if venue=='THE_PAVILION':
  brunch=sum(p['billing_quantity'] for p in parts if p.get('source_line')==203)
  drinks=sum(p['billing_quantity'] for p in parts if p['role']=='DRINK')
  if drinks<brunch:raise ValueError('HC_REQUIRED_BRUNCH_BEVERAGE_QUANTITY')
 if venue=='TENNEZ_PARK' and any(p['role']=='ACTIVITY' for p in parts):
  # Common one-hour session includes one can; only excess is additional sale.
  ball=next((p for p in parts if p['source_line']==247),None)
  if ball:
   parts.remove(ball);free=copy.deepcopy(ball);free.update(billing_quantity=1,original_list_unit_price_krw=ball['unit_price_krw'],unit_price_krw=0,included_benefit='TENNIS_ONE_CAN_PER_MODELED_HOUR');parts.append(free)
   if ball['billing_quantity']>1:parts.append(dict(ball,billing_quantity=ball['billing_quantity']-1))
 return compose(parts,a,period)

def orders(a,venue,t,duration,period):
 try:explicit=explicit_order(a,venue,period,t,duration)
 except ValueError as e:
  if str(e).startswith('HC_ORDER_INELIGIBLE:'):return [],[dict(venue_id=venue,reasons=[str(e)])]
  raise
 if explicit:return [MB.metadata(explicit,a,'EXPLICIT_OPERATOR_ORDER') if venue in MB.VENUES else explicit],[]
 allowed=[];excluded=[]
 package=BY.get(options(a).get('room_products',{}).get(a.pid,''),{})
 products=[p for p in DATA['products'] if p['venue_id']==venue and (p['role'] in MAIN_ROLES or p['sku_id'] in package.get('included_sku_allowance',{})) and p['role']!='EVENT_ADMISSION' and p.get('automatic_choice',True)]
 if venue=='ROOM_MEAL' and period=='breakfast':products=[p for p in products if p['role']=='BREAKFAST']   # an in-room breakfast is a breakfast item, never an all-day/lunch menu
 for p in products:
  why=eligible(p,a,t,duration,period)
  if why:excluded.append(dict(sku_id=p['sku_id'],reasons=why));continue
  q=quantity(p,a)
  if q<p['minimum_quantity']:
   excluded.append(dict(sku_id=p['sku_id'],reasons=['MINIMUM_AFTER_PARTY_ALLOCATION']));continue
  parts=[component(p,q,a)]
  party=modeled_party(a)
  if (p['category']=='F&B' or venue in ('THEATRE_OF_LIGHT','RIVERPARK')) and p['billing_unit']=='person' and party and party['children']:
   parts.extend(OC.child_parts(p,a,t,duration,period,H=__import__(__name__,fromlist=['']),party=party))
  if venue=='DOUGLAS_LOUNGE' and a.N==3 and package.get('package_people',2)<a.N:parts.append(component(BY['HC-DOUGLAS-LOUNGE-EXTRA'],1,a,assumption='MODELED_EXTRA_PERSON_DAY_PASS_FREQUENCY_UNVERIFIED'))
  if venue in ('POOL','FOREST_PARK') and p['unit_price_krw']==0:
   mp=modeled_party(a) or dict(adult_count=a.N,children=[])
   # Grand's infant inclusion is not a blanket waiver for every child.
   # Unknown child coverage is priced as an explicit model proxy, not free.
   if venue=='POOL':
    covered=[];uncovered=[]
    for ch in mp['children']:
     age=ch.get('age_months');ok=age is not None and (age<204 if a.B=='VISTA' else ch.get('school_stage')=='preschool' and age<72)
     (covered if ok else uncovered).append(ch)
    extra_adults=max(0,mp['adult_count']-2);extra_children=max(0,len(covered)-2)+len(uncovered)
   else:extra_adults=max(0,mp['adult_count']-2);extra_children=max(0,len(mp['children'])-2)
   if extra_adults+extra_children>2:
    excluded.append(dict(sku_id=p['sku_id'],reasons=['MAX_EXTRA_FACILITY_PEOPLE']));continue
   if venue=='POOL':
    for cohort,qextra in (('ADULT',extra_adults),('CHILD_FARE_UNVERIFIED',extra_children)):
     if qextra:parts.append(component(OC.pool_extra_product(BY['HC-MENU-235'],a,cohort),qextra,a,assumption='PER_ENTRY_MODEL; DATE_SPECIFIC_TARIFF_UNCONFIRMED; CHILD_AGE_PRESERVED'))
   else:
    for line,qextra in ((237,extra_adults),(238,extra_children)):
     if qextra:parts.append(component(BY[f'HC-MENU-{line:03}'],qextra,a,assumption='MODELED_EXTRA_PARTICIPANTS_PER_ENTRY_FREQUENCY_NOT_VERIFIED'))
  if venue=='TENNEZ_PARK' and a.N>4:
   parts.append(component(BY['HC-MENU-246'],a.N-4,a,assumption='MODEL_60_MINUTE_COURT_SESSION_EXTRA_PERSONS_NOT_EXTRA_COURTS'))
  if venue=='THE_PAVILION' and p.get('requires_beverage_per_portion'):
   # Each eligible drink creates a complete candidate BEFORE native scoring.
   # The selected candidate retains the drink; nothing is attached at settlement.
   drinks=[x for x in DATA['products'] if x['venue_id']==venue and x['role']=='DRINK' and x.get('automatic_choice',True) and not eligible(x,a,t,duration,period,True)]
   for drink in drinks:
    bundle=parts+[component(drink,q,a,assumption='REQUIRED_BEVERAGE_SELECTED_IN_COMPLETE_CANDIDATE')]
    c=compose(bundle,a,period);c['required_drink_choice']=drink['sku_id'];allowed.append(c)
   if not drinks:excluded.append(dict(sku_id=p['sku_id'],reasons=['REQUIRED_BEVERAGE_NO_ELIGIBLE_CANDIDATE']))
  else:allowed.append(compose(parts,a,period))
 return MB.alternatives(allowed,a,period,__import__(__name__,fromlist=[''])),excluded

def charge(c,*,included=False):
 if c.get('price_unknown') and not included:
  out=copy.deepcopy(c);out.update(unit_price_krw=None,list_amount_krw=None,included_benefit=None,discount_krw=0)
  for part in out.get('components',[]):part.update(unit_price_krw=None,price_status=c['price_status'],discount_krw=0)
  return dict(status='가격 미정',krw=None,per='건',sku_contract=out,c01_structured_order_quantity=True,auto_charge=False,price_kind=c['price_status'],
   basis=c.get('price_unknown_basis','가격 미확인')+' · 실제 구매/예약 아님',discount_krw=0)
 amount=0 if included else c['unit_price_krw']
 out=copy.deepcopy(c);out.update(included_benefit=('ALL_VIRTUAL_GUESTS_BREAKFAST' if c.get('service_period')=='breakfast' else c.get('hotel_entitlement_key')) if included else None,
  list_amount_krw=c['unit_price_krw'],unit_price_krw=amount,price_status='PACKAGE_INCLUDED_NOT_NEW_REVENUE' if included else c['price_status'])
 return dict(status='포함' if included else '무료' if amount==0 else '유료',krw=amount,per='건',sku_contract=out,
  c01_structured_order_quantity=True,auto_charge=False,price_kind=out['price_status'],
  basis='호텔 상품 시뮬레이션 주문 · '+out['price_status']+' · 실제 구매/예약 아님',discount_krw=0 if included else c.get('discount_krw',0))

def entitlement(a,c):
 """Selected source package benefits; eligibility/price inputs, not preference."""
 from . import santa_2026 as S26
 santa=S26.benefit(a,c)
 if santa:return santa
 if c['venue_id']=='SAUNA':return SA.benefit(a,c)
 room=BY.get(options(a).get('room_products',{}).get(a.pid,''),{})
 benefit=PB.apply(a,c)
 if benefit:return benefit
 text=room.get('included_description','');venue=c['venue_id'];slot=c['service_period'];phase=getattr(a,'phase','mid')
 allowances=room.get('included_sku_allowance',{})
 for sku,limit in allowances.items():
  key='HC_PACKAGE_'+room['sku_id']+'_'+sku
  if a.visit_history.get('hotel_entitlement_usage',{}).get(key):continue
  if len(c.get('components',[]))==1 and c['components'][0]['sku_id']==sku and c['components'][0]['billing_quantity']<=limit:
   c=copy.deepcopy(c);c.update(hc_included=True,hotel_entitlement_key=key,benefit_coverage_people=room['package_people'],benefit_frequency_basis=room['benefit_frequency_basis']);return c
 key=None;cover=2
 m=re.search(r'(?:성인\s*)?(\d+)인',room.get('source_unit',''))
 if m:cover=int(m[1])
 if venue=='SKYARD' and OC.skyard_included(a,room) and any(p.get('source_line')==242 for p in c['components']):
  c=copy.deepcopy(c);c.update(hc_included=True,hotel_entitlement_key='HC_SKYARD_INCLUDED_'+a.sc['date'],benefit_coverage_people=a.N);return c
 if venue in ('SKYARD','DOUGLAS_LOUNGE') and c['unit_price_krw']:
  c=copy.deepcopy(c);day_key='HC_'+venue+'_MODELED_DAYPASS_'+a.sc['date']
  c.update(hotel_entitlement_key=day_key,daypass_scope='MODEL_PER_ROOM_DAY_NOT_CONFIRMED_OFFICIAL_REENTRY',price_tier='SIMULATION_ASSUMPTION')
  for part in c['components']:part['price_tier']='SIMULATION_ASSUMPTION';part['price_status']='COLLECTED_AMOUNT_WITH_MODEL_PER_DAY_UNIT'
  if a.visit_history.get('hotel_entitlement_usage',{}).get(day_key):c['hc_included']=True
  return c
 if venue=='SAUNA' and '사우나' in text:key='HC_ROOM_SAUNA_ONCE'
 if venue=='THE_BUFFET' and slot=='dinner' and ('더뷔페 디너' in text or '더뷔페 석식' in text) and ('입실일' not in text or phase=='checkin'):key='HC_ROOM_DINNER_'+a.sc['date']
 if venue=='THE_BUFFET' and slot=='lunch' and '더뷔페 중식' in text and ('퇴실일' not in text or phase=='checkout'):key='HC_ROOM_LUNCH_'+a.sc['date']
 if key=='HC_ROOM_SAUNA_ONCE' and room.get('sku_id')=='HC-MENU-028' and a.N==1 and a.visit_history.get('hotel_entitlement_usage',{}).get(key):
  key='HC_ROOM_SAUNA_028_SOLO_SECOND'   # official 8744 sauna type: 2 persons x 1 or 1 person x 2
 if not key or a.visit_history.get('hotel_entitlement_usage',{}).get(key):return c
 c=copy.deepcopy(c);c['hotel_entitlement_key']=key;c['benefit_coverage_people']=cover
 if a.N<=cover:
  c['hc_included']=True;return c
 left=cover;parts=[]
 for p in c['components']:
  if p['billing_unit']!='person':return c  # Shared set cannot be split into fictitious person prices.
  q=p['billing_quantity'];free=min(left,q);left-=free
  if free:parts.append(dict(p,billing_quantity=free,original_list_unit_price_krw=p['unit_price_krw'],unit_price_krw=0,included_benefit=key))
  if q>free:parts.append(dict(p,billing_quantity=q-free))
 mixed=compose(parts,a,slot);mixed.update(hotel_entitlement_key=key,benefit_coverage_people=cover)
 return mixed
