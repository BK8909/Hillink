"""C01 dated menu contracts. Explicit product/unit matching, no coefficient tuning."""
import os as _v12z_os
_V12Z_COMMON = _v12z_os.environ.get('HILLINK_V12Z_COMMON') == '1'
import copy,csv,hashlib,io,re,json
from pathlib import Path
from datetime import date
from functools import lru_cache
from .candidate_products import MENU
import walkerhill_timeline_validator as V
from . import party_orders as PO
MENU_SHA=hashlib.sha256(MENU.read_bytes()).hexdigest()
CONFIRMATIONS=Path(__file__).with_name('product_confirmations.json')
CONFIRMATION_SHA=hashlib.sha256(CONFIRMATIONS.read_bytes()).hexdigest()
CONFIRMED={(r['venue_id'],r['source_line']):r for r in json.loads(CONFIRMATIONS.read_text())['products']}

# Venue templates retain their existing coefficient path. Only known menu tags
# replace incompatible template tags; no premium/novelty bonus is introduced.
SPECS={
 'C01_GEUM_SET1':('GEUMRYONG','금룡','주중 특선 SET ①'),
 'C01_GEUM_SET2':('GEUMRYONG','금룡','주중 특선 SET ②'),
 'C01_GEUM_HWARYONG':('GEUMRYONG','금룡','화룡 코스'),
 'C01_GEUM_LONGEVITY':('GEUMRYONG','금룡','만수무강 코스'),
 'C01_GEUM_CHEF':('GEUMRYONG','금룡','진계도 셰프 스페셜'),
 'C01_GEUM_DO':('GEUMRYONG','금룡','도원경 · 도'),
 'C01_GEUM_WON':('GEUMRYONG','금룡','도원경 · 원'),
 'C01_GEUM_KYUNG':('GEUMRYONG','금룡','도원경 · 경'),
 'C01_ONDAL_SURA':('ONDAL','온달','수라상차림'),
 'C01_ONDAL_COURT':('ONDAL','온달','궁중상차림'),
 'C01_MYONG_SPECIAL2':('MYONGWOLGWAN','명월관','스페셜 모둠 · 2인 식사 포함'),
 'C01_MYONG_SPECIAL4':('MYONGWOLGWAN','명월관','명월관 모둠 한상'),
 'C01_MYONG_SIRLOIN':('MYONGWOLGWAN','명월관','한우 등심 정식'),
 'C01_MYONG_RIB_SET':('MYONGWOLGWAN','명월관','한우 양념갈비 정식'),
 'C01_GEUM_JAJANG_L':('GEUMRYONG','금룡','삼선 자장면 · 점심'),
 'C01_GEUM_JAJANG_D':('GEUMRYONG','금룡','삼선 자장면 · 저녁'),
 'C01_GEUM_XO_L':('GEUMRYONG','금룡','조리장 특선 볶음밥 (XO) · 점심'),
 'C01_GEUM_XO_D':('GEUMRYONG','금룡','조리장 특선 볶음밥 (XO) · 저녁'),
 'C01_MYONG_TANG_KR':('MYONGWOLGWAN','명월관','한우 갈비탕'),
 'C01_MYONG_TANG_US':('MYONGWOLGWAN','명월관','갈비탕 (미국산)'),
 'C01_PIZZA_VONGOLE':('PIZZA_HILL','피자힐','봉골레 파스타'),
 # V1.2(Claude 10/30) menu-gap: menu.csv 에 있던 명월관 구이 1인분 단품
 'C01_MYONG_GRILL_RIB':('MYONGWOLGWAN','명월관','양념갈비'),
 'C01_MYONG_GRILL_RIB_SP':('MYONGWOLGWAN','명월관','특 양념갈비'),
 'C01_MYONG_GRILL_MIX':('MYONGWOLGWAN','명월관','한우 모둠 주물럭'),
 'C01_MYONG_GRILL_SIRLOIN':('MYONGWOLGWAN','명월관','생등심'),
 'C01_MYONG_GRILL_SHORTRIB':('MYONGWOLGWAN','명월관','생갈비'),
}
INDIVIDUAL_MAINS={
 'C01_GEUM_JAJANG_L':['chinese','noodles'],'C01_GEUM_JAJANG_D':['chinese','noodles'],
 'C01_GEUM_XO_L':['chinese','rice'],'C01_GEUM_XO_D':['chinese','rice'],
 'C01_MYONG_TANG_KR':['korean','soup'],'C01_MYONG_TANG_US':['korean','soup'],
 'C01_PIZZA_VONGOLE':['pasta'],
 'C01_MYONG_GRILL_RIB':['korean','grill','beef'],'C01_MYONG_GRILL_RIB_SP':['korean','grill','beef'],'C01_MYONG_GRILL_MIX':['korean','grill','beef'],
 'C01_MYONG_GRILL_SIRLOIN':['korean','grill','beef'],'C01_MYONG_GRILL_SHORTRIB':['korean','grill','beef'],   # V1.2(Claude 10/30) menu-gap
}
# C01 follow-up: existing source row, no new price or quantity assumption.
SPECS['C01_MYONG_BULGOGI_L']=('MYONGWOLGWAN','명월관','숯불 불고기 (점심 한정)')
INDIVIDUAL_MAINS['C01_MYONG_BULGOGI_L']=['korean','grill','beef']
if not _V12Z_COMMON:
 for _key in [k for k in SPECS if k.startswith('C01_MYONG_GRILL_') or k=='C01_MYONG_BULGOGI_L']:
  SPECS.pop(_key);INDIVIDUAL_MAINS.pop(_key,None)
for key,name in [('ABALONE','반상 · 전복 돌솥비빔밥'),('SPICY_SOUP','반상 · 온달 육개장'),('BEEF_SOUP','반상 · 한우 도가니 곰탕'),('BULGOGI','반상 · 한우 불고기'),('HAIRTAIL_STEW','반상 · 제주 갈치조림'),('HAIRTAIL_GRILL','반상 · 제주 갈치구이')]:
 SPECS['C01_ONDAL_'+key]=('ONDAL','온달',name)
BILLING_PENDING={}  # Historical intake now resolved by explicit user confirmation.
SETS={2:'커플 세트',3:'트리플 세트',4:'콰트로 세트',6:'세이스 세트'}

@lru_cache(maxsize=1)
def rows():
 return tuple((i,r) for i,r in enumerate(csv.DictReader(io.StringIO(MENU.read_text(encoding='utf-8-sig'))),2))

def find(venue,name):
 matched=[(i,r) for i,r in rows() if r['업장']==venue and r['상품']==name]
 if len(matched)!=1:raise ValueError('C01_MENU_ROW_NOT_UNIQUE:'+venue+'/'+name)
 return matched[0]

def day_ok(row,day):
 d=date.fromisoformat(day)
 if row['판매시작'] and day<row['판매시작']:return False
 if row['판매종료'] and day>row['판매종료']:return False
 rule=row['요일제한'];holiday=V.is_public_holiday(d)
 if holiday and '-공휴일' in rule:return False
 if holiday and '+공휴일' in rule:return True
 weekdays=[i for i,ch in enumerate('월화수목금토일') if ch in rule.split('공휴일')[0]]
 return not weekdays or d.weekday() in weekdays

def contract(line,row,venue,period,quantity,unit='person_meal'):
 c={'sku_id':'C01-MENU-'+venue+'-'+str(line),'venue_id':venue,'service_period':period,
  'label':row['업장']+' '+row['상품']+' · 기존 메뉴 기준 가상 계산',
  'unit_price_krw':int(row['단가']),'billing_unit':unit,'billing_quantity':quantity,
  'source_path':'timeline/menu.csv','source_line':line,'source_sha256':MENU_SHA,
  'source_document':row['근거'],'source_checked_at':'UNKNOWN_CATALOG_REVIEW_DATE',
  'valid_from':row['판매시작'] or None,'valid_until':row['판매종료'] or None,
  'applicability_status':'DATED_MODEL_INPUT_NOT_CURRENT_SALE_APPROVAL',
  'source_unit':row['단위'],'source_day_rule':row['요일제한'],'source_service_windows':row['시간제한'],
  'price_status':'DATED_OFFICIAL_MENU_SIMULATION_REFERENCE' if 'walkerhill.com' in row['근거'] else 'COLLECTED_REFERENCE_SIMULATION_PRICE_NOT_CURRENT_SALE',
  'source_grade':row['등급'],'current_sale_confirmed':False,
  'reservation_confirmed':False,'transaction_confirmed':False,'tax_status':'UNKNOWN'}
 confirmation=CONFIRMED.get((venue,line))
 if confirmation:
  if confirmation['unit_price_krw']!=c['unit_price_krw']:raise ValueError('C01_CONFIRMED_SOURCE_PRICE_CHANGED')
  c.update(sku_id=confirmation['sku_id'],billing_unit=confirmation['billing_unit'],
    billing_quantity=1 if confirmation['billing_unit']=='set' else quantity,
    price_status='EXISTING_MENU_PRICE_USER_CONFIRMED_CONTRACT',
    user_confirmation=dict(confirmation_id=confirmation['confirmation_id'],confirmed_fields=confirmation['confirmed_fields'],
      authority='EXPLICIT_USER_INSTRUCTION',source_path='timeline/experiments/persona_live/operator_choice/autonomy_v1/product_confirmations.json',source_sha256=CONFIRMATION_SHA),
    minimum_order_portions=confirmation.get('minimum_order_portions'),menu_day_rule=confirmation.get('menu_day_rule'))
 return c

def bind(o,c,n):
 out=dict(o,sku_contract=c,sku_id=c['sku_id'],label=c['label'],price_status=c['price_status'],
          price_pp_krw=c['unit_price_krw']*c['billing_quantity']/n,
          price_source={'grade':c.get('source_grade','◎'),'note':'기존 menu.csv:'+str(c['source_line'])+' · 가상 계산 · 현재 판매/예약 미확인'})
 out['service_contract']=dict(o.get('service_contract',{}),sku_id=c['sku_id'],price_status=c['price_status'],reservation_state='UNKNOWN_NOT_BOOKED')
 if c.get('components'):
  out['service_contract']['billing_components']=[{k:x.get(k) for k in ('sku_id','source_line','unit_price_krw','billing_quantity','billing_unit')} for x in c['components']]
  out['service_contract']['pricing_input_provenance']=c.get('input_provenance')
 return out

def source_sessions(row,period):
 """Menu windows, distinct from venue hours; no bridging closed sessions."""
 out=[]
 for interval in row['시간제한'].split(','):
  if not interval or '-' not in interval:continue
  start,end=(int(s[:2])*60+int(s[3:]) for s in interval.split('-'))
  if period=='lunch':end=min(end,16*60)
  elif period=='dinner':start=max(start,16*60)
  if start<end:out.append((start,end))
 return out

def individual_contract(c,unit='portion_meal'):
 return dict(c,billing_unit=unit,quantity_basis='SIMULATED_ONE_COMPLETE_MAIN_OR_CUP_PER_MODELED_ADULT',
    quantity_observed=False,age_basis='EXISTING_MODELED_PARTY_WITH_NO_CHILD_FLAG_NOT_VERIFIED_AGES')

def composed_brunch(main,drink_line,drink,n):
 """Source requires a drink. One composed order, not a new official set SKU."""
 beverage=contract(drink_line,drink,'THE_PAVILION','lunch',n,'cup')
 return dict(main,sku_id=main['sku_id']+'-WITH-'+str(drink_line),
    label=main['label']+' + '+drink['상품'],
    components=[dict(main),beverage],billing_unit='person_meal',billing_quantity=n,
    unit_price_krw=main['unit_price_krw']+beverage['unit_price_krw'],
    price_status='COMPOSED_ORDER_FROM_EXISTING_MENU_REFERENCES',
    order_quantity_basis='SIMULATED_ONE_BRUNCH_AND_ONE_REQUIRED_DRINK_PER_MODELED_ADULT',
    official_set_sku=False,standalone_main_allowed=False)

def composed_dessert(parent,extra_line,extra,n):
 if n<=2:raise ValueError('C01_DESSERT_EXTRA_REQUIRES_PARENT_AND_EXTRA_DINERS')
 base=dict(parent,billing_unit='set',billing_quantity=1)
 addon=contract(extra_line,extra,'THE_PAVILION','snack',n-2,'person_addon')
 return dict(base,sku_id=base['sku_id']+'-WITH-'+str(extra_line)+'-N'+str(n),
    label=base['label']+f' + {n-2}인 추가',components=[base,addon],
    unit_price_krw=base['unit_price_krw']+addon['unit_price_krw']*(n-2),
    price_status='COMPOSED_PARENT_SET_WITH_PER_PERSON_ADDONS',
    order_quantity_basis='SIMULATED_ONE_TWO_PERSON_PARENT_SET_PLUS_ADDITIONAL_MODELED_PARTICIPANTS',
    official_set_sku=False,standalone_addon_allowed=False)

def variants(world):
 by={o['id']:o for o in world['offers']}
 for code,(base,venue,name) in SPECS.items():
  line,row=find(venue,name)
  o=copy.deepcopy(by[base]);o.update(id=code,label=venue+' '+name,price_pp_krw=None)
  # Do not give a new rice/soup dish the old seasonal crab menu's affinity.
  if base=='ONDAL':
   o['food']=dict(o['food'],menu_tags=['korean'],menu_known=False)
  if code in INDIVIDUAL_MAINS:
   o['food']=dict(o['food'],menu_tags=INDIVIDUAL_MAINS[code],courses=1,menu_known=True)
  world['offers'].append(o)
 return world

def attach(o,a,t):
 day=a.sc['date'];period='lunch' if t<16*60 else 'dinner'
 venue=o.get('venue');order=PO.explicit_order(a,venue,period)
 if order and o['id']==venue:
  if all(any(max(t,start)+o.get('duration_min',0)<=end for start,end in source_sessions(dict(rows())[part['source_line']],period)) for part in order['components']):return bind(o,order,a.N)
 if o['id']=='PIZZA_HILL':
  if a.N not in SETS:return dict(o,price_pp_krw=None,price_status='AMOUNT_UNKNOWN',
     sku_resolution={'status':'SET_SIZE_NOT_MATCHED_NO_ORDER_QUANTITY_ASSUMED'})
  line,row=find('피자힐',SETS[a.N])
  result=bind(o,contract(line,row,'PIZZA_HILL',period,1,'set'),a.N)
  result['food']=dict(o['food'],menu_tags=['pizza','pasta'])
  result['sku_contract']['unselected_components']=['pizza flavor','pasta variety','included drink selection'];return result
 if o['id']=='MYONGWOLGWAN':
  return dict(o,price_pp_krw=None,price_status='AMOUNT_UNKNOWN',label='명월관 식사 · 메뉴/판매분 수량 미확인',sku_resolution={'status':'PORTION_QUANTITY_NOT_INPUT; DO_NOT_MULTIPLY_PERSON_COUNT'})
 if o['id']=='THE_BUFFET':
  return buffet(o,a,'dinner',t)
 if o['id'] in ('GEUMRYONG','ONDAL'):
  venue,name=('금룡','추미진향 (가을 한정)') if o['id']=='GEUMRYONG' else ('온달','가을바다 꽃게 정찬 (가을 한정)')
  line,row=find(venue,name)
  if not day_ok(row,day) or a.N<2 or a.C.get('kids'):
   return dict(o,price_pp_krw=None,price_status='AMOUNT_UNKNOWN',label=venue+' 식사 · 적용 메뉴/인원 미확인')
  return bind(o,contract(line,row,o['id'],period,a.N),a.N)
 if o['id'] not in SPECS:return o
 base,venue,name=SPECS[o['id']];line,row=find(venue,name)
 sessions=source_sessions(row,period)
 if not sessions:
  return dict(o,available=False,status='SKU_SERVICE_PERIOD_NOT_AVAILABLE',
    service_contract=dict(o.get('service_contract',{}),planning_viability='BLOCKED',blocked_reason='SKU_SERVICE_PERIOD_NOT_AVAILABLE'))
 start,end=min(sessions)
 old=o.get('window') or {'start':'00:00','end':'23:59'}
 minute=lambda s:int(s[:2])*60+int(s[3:])
 start=max(start,minute(old['start']))
 # V1.2(Claude 10/30) order-window: 업장 공식 창이 메뉴 시간제한보다 늦게 끝나면 메뉴 끝 = 주문 마감(식사는 업장 종료까지)
 _order_deadline=None
 if _V12Z_COMMON and minute(old['end'])>end:
  _order_deadline=end;end=minute(old['end'])
 else:end=min(end,minute(old['end']))
 o=dict(o,window={'start':f'{start//60:02d}:{start%60:02d}','end':f'{end//60:02d}:{end%60:02d}'})
 if _order_deadline is not None:o['order_deadline']=f'{_order_deadline//60:02d}:{_order_deadline%60:02d}'
 if max(t,start)+o['duration_min']>end or (_order_deadline is not None and max(t,start)>_order_deadline):
  return dict(o,available=False,status='SKU_SERVICE_WINDOW_NOT_FITTING',
    service_contract=dict(o.get('service_contract',{}),planning_viability='BLOCKED',blocked_reason='SKU_SERVICE_WINDOW_NOT_FITTING'))
 if '사전 예약' in row['근거']:
  return dict(o,available=False,status='ADVANCE_RESERVATION_NOT_CONFIRMED',
     service_contract=dict(o.get('service_contract',{}),planning_viability='RESERVATION_REVIEW_REQUIRED',blocked_reason='ADVANCE_RESERVATION_NOT_CONFIRMED'))
 minimum=2 if '2인 이상' in row['단위'] else 1
 set_match=re.search(r'세트.*?(\d+)인',row['단위'])
 if set_match and a.N!=int(set_match.group(1)):
  return dict(o,available=False,status='SET_SERVING_SIZE_NOT_MATCHED',service_contract=dict(o.get('service_contract',{}),planning_viability='BLOCKED',blocked_reason='SET_SERVING_SIZE_NOT_MATCHED'))
 if not day_ok(row,day) or a.N<minimum or (a.C.get('kids') and not PO.party(a) and not set_match):
  return dict(o,available=False,status='SKU_DATE_PARTY_OR_CHILD_MENU_INELIGIBLE',
              service_contract=dict(o.get('service_contract',{}),planning_viability='BLOCKED',blocked_reason='SKU_DATE_PARTY_OR_CHILD_MENU_INELIGIBLE'))
 if o['id'] in BILLING_PENDING:
  c=contract(line,row,base,period,None,'portion_person_mapping_pending')
  c.update(sku_id=BILLING_PENDING[o['id']],listed_amount_krw=int(row['단가']),unit_price_krw=None,price_status='BILLING_UNIT_PENDING_NEWER_CATALOG',review_source='research/w44_c01/sources/verified_price_catalog.json')
  return dict(o,sku_contract=c,sku_id=c['sku_id'],price_pp_krw=None,price_status=c['price_status'],label=venue+' '+name+' · 과금 단위 미확인',service_contract=dict(o.get('service_contract',{}),sku_id=c['sku_id'],price_status=c['price_status']))
 c=contract(line,row,base,period,1 if set_match else a.N,'set' if set_match else 'person_meal')
 if o['id'] in INDIVIDUAL_MAINS:c=individual_contract(c)
 c=PO.mixed_person_contract(c,a)
 if c is None:return dict(o,available=False,status='CHILD_MENU_ELIGIBILITY_UNRESOLVED',price_pp_krw=None,price_status='AMOUNT_UNKNOWN',sku_resolution={'status':'CHILD_MENU_ELIGIBILITY_UNRESOLVED'},service_contract=dict(o.get('service_contract',{}),planning_viability='BLOCKED',blocked_reason='CHILD_MENU_ELIGIBILITY_UNRESOLVED'))
 return bind(o,c,a.N)

def buffet_rows():
 from . import historical_prices as HIST
 return tuple(rows())+tuple(HIST.menu_rows())   # 11/03: 2025 과거 참고가 overlay (menu.csv 는 그대로)

def buffet_contract(line,row,period,quantity):
 from . import historical_prices as HIST
 return HIST.patch_contract(contract(line,row,'THE_BUFFET',period,quantity),row)

def buffet(o,a,period,t,covered_adults=0):
 if o.get('in_package'):return o  # Included use does not become a separate sale.
 order=PO.explicit_order(a,'THE_BUFFET',period,t)
 if order:return bind(o,order,a.N)
 p=PO.party(a)
 if a.C.get('kids') and p is None:
  return dict(o,price_pp_krw=None,price_status='AMOUNT_UNKNOWN',sku_resolution={'status':'ADULT_CHILD_COUNTS_AND_AGES_REQUIRED'})
 names={'breakfast':'조식','lunch':'중식','dinner':'석식'}
 matches=[(i,r) for i,r in buffet_rows() if r['업장']=='더뷔페' and r['상품'].startswith(names[period]+' · 성인') and day_ok(r,a.sc['date'])]
 if len(matches)!=1:return dict(o,price_pp_krw=None,price_status='AMOUNT_UNKNOWN',sku_resolution={'status':'NO_UNIQUE_DATED_BUFFET_PRICE'})
 line,row=matches[0]
 adults=p['adult_count'] if p else a.N
 # Breakfast-included room contract: covered adults pay nothing; only the uncovered diners are a sale.
 covered=min(covered_adults,adults) if period=='breakfast' else 0
 if p is None and not covered:return bind(o,buffet_contract(line,row,period,a.N),a.N)
 parts=[]
 if adults-covered:parts.append(buffet_contract(line,row,period,adults-covered))
 if p and p['children']:
  # Same cohort rules as the catalog order (official_contracts.child_parts), so the score price equals the order price:
  # 36m~elementary = child fare · under 36m = free · unknown/secondary = adult-rate proxy (age never invented).
  fare=[c for c in p['children'] if c.get('age_months') is not None and c['age_months']>=36 and c.get('school_stage') in ('preschool','elementary')]
  infant=[c for c in p['children'] if c.get('age_months') is not None and c['age_months']<36]
  secondary=[c for c in p['children'] if c.get('age_months') is not None and c['age_months']>=156 and c.get('school_stage')=='secondary']
  proxy=len(p['children'])-len(fare)-len(infant)-len(secondary)
  if secondary:
   x=buffet_contract(line,row,period,len(secondary));x.update(sku_id=x['sku_id']+'-SECONDARY-ADULT-TARIFF',label=x['label']+' · 중학생 이상 성인 요금',party_cohort='ADULT_TARIFF_SECONDARY',order_quantity_basis='EXPLICIT_SECONDARY_AGE_ADULT_TARIFF');parts.append(x)
  if fare:
   child=[(i,r) for i,r in buffet_rows() if r['업장']=='더뷔페' and r['상품'].startswith(names[period]+' · 어린이') and day_ok(r,a.sc['date'])]
   if len(child)!=1:return dict(o,price_pp_krw=None,price_status='AMOUNT_UNKNOWN')
   i,r=child[0];parts.append(buffet_contract(i,r,period,len(fare)))
  if proxy:
   x=buffet_contract(line,row,period,proxy);x.update(sku_id=x['sku_id']+'-UNKNOWN-CHILD-MODEL',label=x['label']+' · 연령 미확정 동행 요금 가정',price_status='UNKNOWN_CHILD_AGE_ADULT_RATE_PROXY_NOT_A_VERIFIED_CHILD_FARE',party_cohort='UNKNOWN_CHILD_FARE');parts.append(x)
 if not parts:return dict(o,in_package=True,price_pp_krw=0,room_breakfast_contract=dict(covered_adults=covered))
 out=bind(o,PO.compose(parts,'EXPLICIT_VIRTUAL_PARTY_ALL_MODELED_BUFFET_DINERS',p) if p else parts[0],a.N)
 if covered:out['sku_contract']=dict(out['sku_contract'],room_breakfast_contract=dict(covered_adults=covered,basis='ROOM_BREAKFAST_INCLUDED_CONTRACT_ADULTS'));out['room_breakfast_contract']=dict(covered_adults=covered)
 return out

def planner_contract(code,a):
 if code=='cafe' and a.N==2:
  line,row=find('파빌리온','가을 디저트 FALL IN PAVILION')
  last=(getattr(a,'log',[]) or [{}])[-1].get('t')
  minute=int(last[:2])*60+int(last[3:]) if last else a.t
  if day_ok(row,a.sc['date']) and 11*60<=minute and minute+40<=20*60:return contract(line,row,'THE_PAVILION','snack',1,'set')
 if code=='lunch_pizzahill' and a.N in SETS:
  line,row=find('피자힐',SETS[a.N]);return contract(line,row,'PIZZA_HILL','lunch',1,'set')
 if code in ('lunch_ondal','lunch_geumryong','lunch_moegi') and not a.C.get('kids'):
  venue,name,canonical={'lunch_ondal':('온달','낮것상 (주중 점심)','ONDAL'),'lunch_geumryong':('금룡','화룡 코스','GEUMRYONG'),'lunch_moegi':('모에기','전복 냄비 우동 정식','MOEGI')}[code]
  line,row=find(venue,name);minimum=2 if '2인 이상' in row['단위'] else 1
  if day_ok(row,a.sc['date']) and a.N>=minimum:return contract(line,row,canonical,'lunch',a.N)
 if code=='lunch_buffet':
  o=buffet({'id':'THE_BUFFET'},a,'lunch',a.t);return o.get('sku_contract')
 return None

def bill(c,a):
 count=c.get('billing_quantity',a.N);unit={'set':'세트','portion_meal':'인분','cup':'잔','order':'건'}.get(c['billing_unit'],'인')
 if c.get('minimum_order_portions') and count<c['minimum_order_portions']:
  raise ValueError('C01_MINIMUM_ORDER_PORTIONS_NOT_MET')
 components=c.get('components') or []
 for component in components:
  if component.get('minimum_order_portions') and component['billing_quantity']<component['minimum_order_portions']:
   raise ValueError('C01_MINIMUM_ORDER_PORTIONS_NOT_MET')
 if components and sum(x['unit_price_krw']*x['billing_quantity'] for x in components)!=c['unit_price_krw']*count:
  raise ValueError('C01_COMPOSED_ORDER_TOTAL_MISMATCH')
 source=' + '.join(str(x['source_line']) for x in components) if components else str(c['source_line'])
 detail=' · 구성 주문('+ ' + '.join(f"{x['unit_price_krw']}원×{x['billing_quantity']}" for x in components)+'), 공식 세트 SKU 아님' if components else ''
 return dict(status='유료',krw=c['unit_price_krw']*count,grade=c.get('source_grade','◎'),per=unit,
    sku_contract=c,price_kind='dated_model_reference',
    basis=f"기존 menu.csv:{source} 가상 계산 단가 {c['unit_price_krw']:,}원 × {count}{unit}{detail} · 현재 판매/예약 미확인")
