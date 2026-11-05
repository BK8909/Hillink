"""C01 conditional menu selection after native lunch-venue selection.

No venue weight multiplication, new preference coefficient, booking or provider.
Uses the native score terms and native weighted pick within the selected venue.
"""
import copy,random,re
from . import menu_connections as M
from . import party_orders as PO

VERSION='c01-lunch-menu-selection-v1'
VENUES={'lunch_geumryong':('GEUMRYONG','금룡'),'lunch_ondal':('ONDAL','온달'),
        'lunch_myongwol':('MYONGWOLGWAN','명월관'),'lunch_moegi':('MOEGI','모에기'),
        'lunch_pizzahill':('PIZZA_HILL','피자힐'),'cafe':('THE_PAVILION','파빌리온'),
        'lunch_cafe':('THE_PAVILION','파빌리온')}
EXTRA={
 'C01_GEUM_AUTUMN':('GEUMRYONG','금룡','추미진향 (가을 한정)'),
 'C01_ONDAL_AUTUMN':('ONDAL','온달','가을바다 꽃게 정찬 (가을 한정)'),
 'C01_ONDAL_LUNCH':('ONDAL','온달','낮것상 (주중 점심)'),
 'C01_MYONG_AUTUMN':('MYONGWOLGWAN','명월관','능이버섯 등심 불고기 한상 (가을 한정)'),
 'C01_MOEGI_LUNCH':('MOEGI','모에기','런치 모에기 코스'),
 'C01_MOEGI_SASHIMI':('MOEGI','모에기','생선회 정식 (SASHIMI SET)'),
 'C01_MOEGI_UDON':('MOEGI','모에기','전복 냄비 우동 정식'),
 'C01_MOEGI_SOBA':('MOEGI','모에기','모에기 스시와 소바 정식'),
 'C01_MOEGI_EEL':('MOEGI','모에기','요비모도시 장어 정식'),
 'C01_PAV_COFFEE_HOT':('THE_PAVILION','파빌리온','아메리카노 HOT'),
 'C01_PAV_COFFEE_ICE':('THE_PAVILION','파빌리온','아메리카노 ICE'),
 'C01_PAV_FALL_SET':('THE_PAVILION','파빌리온','가을 디저트 FALL IN PAVILION'),
 'C01_PAV_BRUNCH_HOT':('THE_PAVILION','파빌리온','더파빌리온 브런치'),
 'C01_PAV_BRUNCH_ICE':('THE_PAVILION','파빌리온','더파빌리온 브런치'),
}
for size,name in M.SETS.items():EXTRA['C01_PIZZA_SET'+str(size)]=('PIZZA_HILL','피자힐',name)
SPECS=dict(M.SPECS,**EXTRA)

def hm(s):return int(s[:2])*60+int(s[3:])

def options(a,code,t,templates,service_check,duration,travel):
 """Return allowed and explicitly excluded products; no missing-price fallback."""
 if code not in VENUES:return [],[]
 venue,_=VENUES[code];arrival=t+travel;allowed=[];excluded=[]
 period='snack' if code=='cafe' else 'lunch'
 for key,(base,name,product) in SPECS.items():
  if base!=venue:continue
  if venue=='THE_PAVILION' and (key.startswith('C01_PAV_BRUNCH') != (code=='lunch_cafe')):continue
  line,row=M.find(name,product)
  c=M.contract(line,row,venue,period,a.N)
  why=[]
  if not M.day_ok(row,a.sc['date']):why.append('MENU_DATE_OR_DAY_NOT_APPLICABLE')
  if '2인 이상' in row['단위'] and a.N<2:why.append('MENU_MINIMUM_TWO')
  fixed_party_set='세트' in row['단위'] and re.search(r'세트.*?(\d+)인',row['단위']) and '성인' not in row['단위']
  if a.C.get('kids') and not PO.party(a) and not fixed_party_set:why.append('ADULT_CHILD_MENU_COUNTS_UNRESOLVED')
  if '세트' in row['단위']:
   match=re.search(r'세트.*?(\d+)인',row['단위'])
   dessert_extra=key=='C01_PAV_FALL_SET' and a.N>2
   if not dessert_extra and (not match or a.N!=int(match.group(1))):why.append('SET_SERVING_SIZE_NOT_MATCHED')
   c.update(billing_unit='set',billing_quantity=1)
   if dessert_extra:
    extra_line,extra=M.find('파빌리온','가을 디저트 · 1인 추가')
    if not M.day_ok(extra,a.sc['date']):why.append('PARENT_ADDON_DATE_NOT_APPLICABLE')
    c=M.composed_dessert(c,extra_line,extra,a.N)
  if '사전 예약' in row['근거']:why.append('ADVANCE_RESERVATION_NOT_CONFIRMED')
  # A source menu's end may be last order, not the venue's closing time.
  is_last_order='Last order' in row['근거'] or 'Last order' in row['시간제한']
  sessions=[]
  for interval in row['시간제한'].split(','):
   if not interval or '-' not in interval:continue
   start,end=map(hm,interval.split('-'))
   if period=='lunch':
    if start>=16*60:continue  # dinner-only SKU never enters lunch.
    end=min(end,16*60)
   sessions.append(dict(start=start,end=end,last_order=is_last_order))
  fits=[s for s in sessions if s['start']<=arrival and (arrival<=s['end'] if s['last_order'] else arrival+duration<=s['end'])]
  if not fits:why.append('MENU_LUNCH_WINDOW_OR_LAST_ORDER_NOT_FITTING')
  check=service_check(venue,a.sc['date'],arrival,duration)
  if not check['eligible']:why.append(check['blocked_reason'])
  if key in M.BILLING_PENDING:
   c.update(sku_id=M.BILLING_PENDING[key],listed_amount_krw=c['unit_price_krw'],unit_price_krw=None,billing_quantity=None,
      billing_unit='portion_person_mapping_pending',price_status='BILLING_UNIT_PENDING_NEWER_CATALOG')
  c.update(resolution_layer='PRE_ACTION_CONDITIONAL_LUNCH_MENU_SELECTION',source_service_windows=row['시간제한'],
           order_confirmation='SIMULATED_CHOICE_NOT_ACTUAL_ORDER',service_channel='STANDARD_DINING_NOT_PRIVATE_ROOM')
  if why:
   excluded.append(dict(candidate_id=key,sku_id=c['sku_id'],source_line=line,reasons=why));continue
  o=copy.deepcopy(templates[base]);o.update(id=key,label=c['label'],duration_min=duration,available=True)
  # The existing lunch duration is retained as a model assumption, not a
  # measured course duration. No borrowed seafood tag for unknown dishes.
  if base in ('ONDAL','MOEGI'):o['food']=dict(o['food'],menu_tags=['korean'] if base=='ONDAL' else ['japanese'],menu_known=False)
  if key in M.INDIVIDUAL_MAINS:
   o['food']=dict(o['food'],menu_tags=M.INDIVIDUAL_MAINS[key],courses=1,menu_known=True)
   c=M.individual_contract(c)
  if PO.party(a) and c['billing_unit']!='set':
   if base=='THE_PAVILION' or key in M.INDIVIDUAL_MAINS:
    if a.C.get('kids'):continue  # No child main/drink quantity inferred; explicit orders below.
   else:
    c=PO.mixed_person_contract(c,a)
    if c is None:continue
  if key.startswith('C01_PIZZA_SET'):
   o['food']=dict(o['food'],menu_tags=['pizza','pasta'])
  if key in ('C01_PAV_COFFEE_HOT','C01_PAV_COFFEE_ICE'):c=M.individual_contract(c,'cup')
  if key.startswith('C01_PAV_BRUNCH'):
   drink_line,drink=M.find('파빌리온','아메리카노 HOT' if key.endswith('HOT') else '아메리카노 ICE')
   c=M.composed_brunch(c,drink_line,drink,a.N)
  if c['unit_price_krw'] is None:o.update(sku_contract=c,sku_id=c['sku_id'],price_pp_krw=None,price_status=c['price_status'])
  else:o=M.bind(o,c,a.N)
  s=fits[0];o['window']={'start':f'{s["start"]//60:02d}:{s["start"]%60:02d}','end':f'{check["service_window"]["until"]//60:02d}:{check["service_window"]["until"]%60:02d}'}
  o['service_contract']=dict(check,venue_id=venue,sku_id=c['sku_id'],menu_service_window=s,
     price_status=c['price_status'],reservation_state='UNKNOWN_NOT_BOOKED',duration_status='EXISTING_LUNCH_DURATION_MODEL_ASSUMPTION')
  allowed.append(o)
 order=PO.explicit_order(a,venue,period,arrival)
 if order and service_check(venue,a.sc['date'],arrival,duration)['eligible']:
  o=copy.deepcopy(templates[venue]);o.update(id='C01_EXPLICIT_ORDER_'+venue,duration_min=duration,available=True)
  allowed=[M.bind(o,order,a.N)];allowed[0]['service_contract']=dict(service_check(venue,a.sc['date'],arrival,duration),sku_id=order['sku_id'],price_status=order['price_status'],reservation_state='UNKNOWN_NOT_BOOKED')
 if not allowed:
  check=service_check(venue,a.sc['date'],arrival,duration)
  if check['eligible']:
   # Missing age/order-unit inputs do not close an otherwise open venue.
   # This is a venue choice, never an inferred adult menu or a free meal.
   o=copy.deepcopy(templates[venue]);o.update(id='C01_LUNCH_VENUE_ONLY_'+venue,
      label=VENUES[code][1]+(' 카페' if period=='snack' else ' 점심')+' · 주문 상품/금액 미확인',price_pp_krw=None,
      duration_min=duration,c01_lunch_venue_only=True,price_status='AMOUNT_UNKNOWN',
      service_contract=dict(check,venue_id=venue,price_status='AMOUNT_UNKNOWN'),
      sku_id=None)
   o.pop('sku_contract',None);o['food']=dict(o['food'],menu_known=False)
   allowed.append(o)
 return allowed,excluded

def choose(a,code,t,world,offers,excluded,AD):
 """Native score and weighted sampling; conditional on an already chosen venue."""
 if not offers:return None,None
 state=dict(used=set(a.used),hunger=1.0)  # lunch need already passed native planner.
 visit=dict(a.visit_e,checkin=AD.mh(t));rows=[]
 from ..operator_world_v1_1.candidate import candidate_engine
 with candidate_engine(c1=True,c2='venue_visits',c3=True):
  for o in offers:
   terms=AD.EN.score(o,t,state,visit,a.traits,dict(world,offers=offers))
   score=sum(x['value'] for x in terms)
   rows.append(dict(candidate_id=o['id'],sku_id=o.get('sku_id'),base_score=score,final_score=score,
     terms=[{k:x.get(k) for k in ('factor','value','facet','fact_ids','kind')} for x in terms],
     world_allowed=True,service_contract=o['service_contract'],sku_contract=o.get('sku_contract')))
 weights={r['candidate_id']:r['final_score'] for r in rows}
 rng=random.Random(f'{a.rng_base}|C01_LUNCH_PRODUCT|{t}|{a.steps}|{code}')
 preview=random.Random();preview.setstate(rng.getstate());u=preview.random()
 chosen=AD.SP.pick(rng,[o['id'] for o in offers],lambda k:weights[k])[0]
 effective={k:max(.05,v) for k,v in weights.items()};total=sum(effective.values())
 packet=dict(version=VERSION,kind='VENUE_PRODUCT_SELECTION' if code=='cafe' else 'LUNCH_PRODUCT_SELECTION',context_factors=dict(customer_id=a.pid,date=a.sc['date'],time=t,location_id=a.loc),
    selected_venue_action=code,candidates=rows,world_excluded_candidates=excluded,
    source_evidence={},world_constraints='Only source-window and native venue-rule eligible supplied candidates; actual booking/order not confirmed.',
    choice_policy='NATIVE_SCORE_AND_PICK_AFTER_VENUE_SELECTION_NO_LOOKAHEAD',
    provider_calls=0,model_version=VERSION)
 record=dict(packet=packet,llm_choice=None,selection_phase='BEFORE_ACTION_AND_CHARGE',selected_action=code,
    selected_product_id=chosen,sampling=dict(mode='NATIVE_WEIGHTED_SAMPLING_CONDITIONAL_ON_VENUE',uniform=u,
    candidate_order=list(weights),candidate_weights=effective,probabilities={k:v/total for k,v in effective.items()}),
    execution_status='EXECUTED')
 return next(o for o in offers if o['id']==chosen),record
