"""C01 explicit virtual party/order inputs. Never writes persona facts or prices."""
import copy
from datetime import date

VERSION = 'c01-explicit-party-orders-v1'
CHILD_MENUS = {'GEUMRYONG':146, 'ONDAL':157, 'MOEGI':196}
VENUES = {'THE_BUFFET','GEUMRYONG','ONDAL','MOEGI','MYONGWOLGWAN','THE_PAVILION','PIZZA_HILL'}

def integer(x, lo, hi):
 return isinstance(x,int) and not isinstance(x,bool) and lo<=x<=hi

def validate(conditions, party_size):
 """Validate declared scenario input, including unknown ages; no inference from kids."""
 out=copy.deepcopy(conditions)
 p=out.get('party_composition')
 if p is not None:
  if not isinstance(p,dict) or set(p)!={'adult_count','children'} or not integer(p['adult_count'],0,8) or not isinstance(p['children'],list):raise ValueError('C01_PARTY_COMPOSITION_INVALID')
  if p['adult_count']+len(p['children'])!=party_size:raise ValueError('C01_PARTY_COUNTS_MUST_EQUAL_PARTY_SIZE')
  for ch in p['children']:
   if not isinstance(ch,dict) or set(ch)-{'age_months','school_stage'}:raise ValueError('C01_CHILD_FIELDS_INVALID')
   if ch.get('age_months') is not None and not integer(ch['age_months'],0,215):raise ValueError('C01_CHILD_AGE_INVALID')
   if ch.get('school_stage') not in (None,'preschool','elementary','secondary'):raise ValueError('C01_CHILD_SCHOOL_STAGE_INVALID')
 orders=out.get('orders',[])
 if not isinstance(orders,list) or len(orders)>32:raise ValueError('C01_ORDERS_INVALID')
 keys=set()
 for o in orders:
  if not isinstance(o,dict) or set(o)!={'date','venue_id','service_period','items'}:raise ValueError('C01_ORDER_FIELDS_INVALID')
  if not isinstance(o['date'],str):raise ValueError('C01_ORDER_DATE_INVALID')
  date.fromisoformat(o['date'])
  if o['venue_id'] not in VENUES or o['service_period'] not in ('breakfast','lunch','dinner','snack'):raise ValueError('C01_ORDER_SCOPE_INVALID')
  k=(o['date'],o['venue_id'],o['service_period'])
  if k in keys:raise ValueError('C01_DUPLICATE_ORDER_SCOPE')
  keys.add(k)
  if not isinstance(o['items'],list) or not 1<=len(o['items'])<=8:raise ValueError('C01_ORDER_ITEMS_INVALID')
  lines=set()
  for item in o['items']:
   if not isinstance(item,dict) or set(item)!={'source_line','quantity'} or not integer(item['source_line'],2,1000) or not integer(item['quantity'],1,32):raise ValueError('C01_ORDER_QUANTITY_INVALID')
   if item['source_line'] in lines:raise ValueError('C01_DUPLICATE_ORDER_LINE')
   lines.add(item['source_line'])
  # Resolve source/service contracts before any simulation starts.
  explicit_order(type('Input',(),{'vs':{'orders':[o], 'party_composition':p},'N':party_size,'sc':{'date':o['date']}})(),o['venue_id'],o['service_period'])
 if p is not None or orders:out['pricing_input_provenance']='EXPLICIT_VIRTUAL_VISIT_NOT_OBSERVED_REVIEW_FACT'
 return out

def party(a):
 return getattr(a,'vs',{}).get('party_composition')

def children_eligible(p,venue):
 for c in p['children']:
  age=c.get('age_months');stage=c.get('school_stage')
  if age is None or stage is None:return False
  if venue=='THE_BUFFET' and not (age>=36 and stage in ('preschool','elementary')):return False
  if venue in ('GEUMRYONG','ONDAL') and stage!='preschool':return False
  if venue=='MOEGI' and stage not in ('preschool','elementary'):return False
 return True

def compose(parts, basis, party_composition=None):
 c=copy.deepcopy(parts[0]);total=sum(x['unit_price_krw']*x['billing_quantity'] for x in parts)
 c.pop('minimum_order_portions',None)  # Minimum belongs to each component, not one combined order.
 c.update(sku_id='C01-MENU-ORDER-'+ '-'.join(str(x['source_line'])+'x'+str(x['billing_quantity']) for x in parts),
  label=' + '.join(x['label'] for x in parts), components=parts,unit_price_krw=total,
  billing_unit='order',billing_quantity=1,order_quantity_basis=basis,quantity_observed=False,
  input_provenance='EXPLICIT_VIRTUAL_VISIT_NOT_OBSERVED_REVIEW_FACT',official_set_sku=False,
  price_status='COMPOSED_ORDER_FROM_EXISTING_MENU_REFERENCES',
  party_composition=copy.deepcopy(party_composition))
 return c

def mixed_person_contract(c,a):
 """Adult course plus eligible child menu; fixed sets stay unchanged."""
 from . import menu_connections as M
 if c['billing_unit']=='set':return c
 p=party(a)
 if not p:return c if not a.C.get('kids') else None
 if not p['children']:
  return dict(c,billing_quantity=p['adult_count'],age_basis='EXPLICIT_VIRTUAL_ADULT_COUNT')
 venue=c['venue_id']
 if venue not in CHILD_MENUS or not children_eligible(p,venue):return None
 if c.get('minimum_order_portions',0)>p['adult_count'] or ('2인 이상' in c.get('source_unit','') and p['adult_count']<2):return None
 line=CHILD_MENUS[venue];r=dict(M.rows())[line]
 if not M.day_ok(r,a.sc['date']) or not M.source_sessions(r,c['service_period']):return None
 parts=[]
 if p['adult_count']:parts.append(dict(c,billing_quantity=p['adult_count']))
 parts.append(M.contract(line,r,venue,c['service_period'],len(p['children'])))
 return compose(parts,'EXPLICIT_PARTY_ADULT_MAIN_PLUS_ELIGIBLE_CHILD_MENU_MODEL',p)

def explicit_order(a,venue,period,minute=None):
 """Explicit quantity is independent of guest count. Unsupported/add-on orders fail closed."""
 from . import menu_connections as M
 orders=[x for x in getattr(a,'vs',{}).get('orders',[]) if (x['date'],x['venue_id'],x['service_period'])==(a.sc['date'],venue,period)]
 if not orders:return None
 names={'THE_PAVILION':'파빌리온','MYONGWOLGWAN':'명월관','THE_BUFFET':'더뷔페','GEUMRYONG':'금룡','ONDAL':'온달','MOEGI':'모에기','PIZZA_HILL':'피자힐'}
 # Scope of this adapter: existing complete mains/courses, shared sets and
 # listed coffee. Other optional/add-on SKUs cannot become standalone meals.
 known={M.find(v,n)[0] for _,v,n in M.SPECS.values()}|set(range(158,164))|{204,205}
 if venue=='THE_BUFFET':known|={i for i,r in M.rows() if r['업장']=='더뷔페'}
 parts=[]
 for item in orders[0]['items']:
  line=item['source_line'];r=dict(M.rows()).get(line)
  if line not in known or not r or r['업장']!=names[venue] or not M.day_ok(r,a.sc['date']):raise ValueError('C01_ORDER_SOURCE_OR_DATE_NOT_SUPPORTED')
  sessions=M.source_sessions(r,period)
  if not sessions:raise ValueError('C01_ORDER_SERVICE_PERIOD_NOT_SUPPORTED')
  if venue=='THE_PAVILION' and period!='snack':raise ValueError('C01_DRINK_ONLY_ORDER_NOT_A_COMPLETE_MEAL')
  if venue=='THE_BUFFET' and not r['상품'].startswith({'breakfast':'조식','lunch':'중식','dinner':'석식'}.get(period,'INVALID')+' · '):raise ValueError('C01_BUFFET_SKU_MEAL_PERIOD_MISMATCH')
  if minute is not None and not any(start<=minute<end for start,end in sessions):return None
  if '사전 예약' in r['근거']:raise ValueError('C01_ORDER_RESERVATION_UNCONFIRMED')
  if venue=='THE_BUFFET':
   p=party(a)
   if p is None:raise ValueError('C01_BUFFET_ORDER_PARTY_COMPOSITION_REQUIRED')
   child='어린이' in r['단위']
   limit=len(p['children']) if child else p['adult_count']
   if item['quantity']>limit or child and not children_eligible(p,venue):raise ValueError('C01_BUFFET_ORDER_AGE_OR_DINER_COUNT_INELIGIBLE')
   role='어린이' if child else '성인'
   if sum(x['quantity'] for x in orders[0]['items'] if role in dict(M.rows())[x['source_line']]['단위'])>limit:raise ValueError('C01_BUFFET_ORDER_DUPLICATE_DINERS')
  elif '미취학' in r['단위'] or '어린이' in r['단위']:raise ValueError('C01_EXPLICIT_CHILD_ORDER_NEEDS_ELIGIBILITY')
  unit='cup' if line in (204,205) else 'set' if '세트' in r['단위'] else 'portion_meal'
  if venue=='THE_BUFFET':unit='person_meal'
  c=M.contract(line,r,venue,period,item['quantity'],unit)
  if c.get('minimum_order_portions',2 if '2인 이상' in r['단위'] else 1)>item['quantity']:raise ValueError('C01_MINIMUM_ORDER_PORTIONS_NOT_MET')
  # Fixed-person sets must use the established set-size adapter, not this path.
  if unit=='set':raise ValueError('C01_EXPLICIT_FIXED_SET_USE_EXISTING_SET_CONTRACT')
  parts.append(c)
 return compose(parts,'EXPLICIT_VIRTUAL_ORDER_QUANTITY_NOT_GUEST_COUNT',party(a))
