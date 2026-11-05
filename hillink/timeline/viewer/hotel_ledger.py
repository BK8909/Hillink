"""C01 component L5 expansion and price-class rollups; no D01 sum formulas."""
import copy,hashlib,sys
from pathlib import Path
TL=Path(__file__).resolve().parents[1]
for _path in (TL,TL/"experiments/persona_live"):
 if str(_path) not in sys.path:sys.path.insert(0,str(_path))
from types import SimpleNamespace
from operator_choice.autonomy_v1 import hotel_catalog as H

def expand(raw,traces):
 out=[]
 for row in raw:
  c=row.get('선택 SKU 계약') or {}
  if not (c.get('catalog_policy')==H.POLICY or str(c.get('sku_id','')).startswith('HC-ROOM-ORDER-')) or not c.get('components'):
   out.append(row);continue
  if c.get('price_unknown'):   # unknown-price order (e.g. Vista sauna): one 가격 미정 row, never split into priced components
   out.append(row);continue
  included=row['상태'] in ('포함','무료');parent=row['_row_key'];parts=c['components']
  assert sum(x['unit_price_krw']*x['billing_quantity'] for x in parts)==c.get('list_amount_krw',c['unit_price_krw'])
  for i,p in enumerate(parts):
   r=copy.deepcopy(row);q=p['billing_quantity'];unit=0 if included else p['unit_price_krw'];amount=unit*q
   p=copy.deepcopy(p)
   for field in ('selection_id','final_candidate_id'):
    if c.get(field):p[field]=c[field]
   p.update(included_benefit=c.get('included_benefit') or p.get('included_benefit'),original_list_unit_price_krw=(p.get('price_trace') or {}).get('scenario_unit_price_before_discount_krw',p.get('original_list_unit_price_krw',p['unit_price_krw'])),unit_price_krw=unit)
   key=hashlib.sha256(f'{parent}|HC_LINE|{i}|{p["sku_id"]}'.encode()).hexdigest()[:24]
   r.update({'_row_key':key,'L4 상품':p['label'],'상품 ID':p['sku_id'],'단가':unit,'수량':q,'판매 수량':q,'판매 단위':p['billing_unit'],'과금 단위':p['billing_unit'],
     '결제액':amount,'확정 결제액':amount,'가정 결제액':amount,'선택 SKU 계약':p,'_hc_parent_order_id':parent,'_hc_price_tier':p['price_tier'],
     '순매출':'','순매출 상태':'세금 기준 미확인','_net_ex_vat_krw':None,'확인 메모':row['확인 메모']+' | HC 주문 구성품; 부모 주문 금액 중복 합산 안 함'})
   if amount==0:r['상태']='포함' if included or p.get('included_benefit') else '무료'
   if p.get('venue_id') in ('PARKING','VALET'):r.update({'L2 부문':'기타','L3 업장':'주차' if p['venue_id']=='PARKING' else '발렛'})
   if row.get('_room_pricing'):
    if i==0:
     r['_room_pricing'].update(virtual_gross_krw=amount,unit_price_krw=unit,product=p['label'])
    else:
     r.pop('_room_pricing',None);r['장면']='room_addon'
   traces[key]=dict(copy.deepcopy(traces[parent]),parent_order_id=parent,component_index=i,sku_id=p['sku_id'])
   p['parent_order_id']=parent
   if row.get('_room_pricing'):
    if i>0:traces[key].pop('room_pricing',None);traces[key]['act']='room_addon'
    else:traces[key]['room_pricing']=copy.deepcopy(r['_room_pricing'])
   out.append(r)
  assert sum(x['확정 결제액'] for x in out[-len(parts):])==row['확정 결제액']
 return out

def resolved_price_tier(row):
 c=row.get('sku_contract') or {};room=row.get('room_pricing') or {}
 tier=c.get('price_tier') or room.get('price_tier')
 # Keep the immutable quote's declared tier, but do not call a source-marked
 # assumption a historical verified price (e.g. Jan-Sep buffet proxy prices).
 if c.get('source_grade')=='△' and tier in (None,'EXISTING_REFERENCE'):
  return 'SIMULATION_ASSUMPTION'
 if tier:return tier
 status=row.get('price_status') or c.get('price_status') or room.get('price_status') or ''
 if status=='VIRTUAL_MODEL_UNIT_PRICE':return 'SIMULATION_ASSUMPTION'
 if status in ('DATED_OFFICIAL_MENU_SIMULATION_REFERENCE','COLLECTED_REFERENCE_SIMULATION_PRICE_NOT_CURRENT_SALE','EXISTING_MENU_PRICE_USER_CONFIRMED_CONTRACT','COMPOSED_ORDER_FROM_EXISTING_MENU_REFERENCES','COMPOSED_PARENT_SET_WITH_PER_PERSON_ADDONS'):
  return 'EXISTING_REFERENCE'
 return 'LEGACY_OR_INCLUDED'

def annotate(ledger):
 if not any((r.get('sku_contract') or {}).get('catalog_sha256') or (r.get('room_pricing') or {}).get('catalog_sha256') for receipt in ledger['receipts'].values() for r in receipt['rows']):return ledger
 groups={t:dict(amount_krw=0,transaction_rows=0,row_ids=[]) for t in H.TIERS};groups['LEGACY_OR_INCLUDED']=dict(amount_krw=0,transaction_rows=0,row_ids=[])
 for receipt in ledger['receipts'].values():
  for row in receipt['rows']:
   c=row.get('sku_contract') or {};tier=resolved_price_tier(row)
   if c.get('sku_id') and not row.get('sku_id'):row['sku_id']=c['sku_id']
   if c.get('sku_id') and not row.get('product_sku_id'):
    row.update(product_sku_id=c['sku_id'],sku_identity_source='EXISTING_CONTRACT_NO_NEW_SKU')
   row['product_classification']='INCLUDED_BENEFIT' if row.get('purchase_status')=='PACKAGE_INCLUDED' else 'NONSALE_FREE_SERVICE' if row.get('paid_krw')==0 and row.get('purchase_status')=='FREE_USE' else 'PRICED_VIRTUAL_PRODUCT' if row.get('paid_krw',0)>0 else 'UNCONFIRMED_OR_NONPURCHASE'
   if tier in H.TIERS:row.update(price_tier=tier,price_tier_declared=c.get('price_tier') or (row.get('room_pricing') or {}).get('price_tier'),price_tier_resolution='SOURCE_GRADE_OR_RECORDED_STATUS_V2')
   g=groups[tier];g['amount_krw']+=row['paid_krw'];g['transaction_rows']+=1;g['row_ids'].append(row['row_id'])
   if c.get('catalog_sha256'):
    row.update(price_tier=tier,parent_order_id=c.get('parent_order_id'),catalog_sha256=c['catalog_sha256'],discount_krw=0 if row.get('purchase_status') in ('PACKAGE_INCLUDED','FREE_USE') else c.get('discount_krw',0)*c.get('billing_quantity',1),price_trace=copy.deepcopy(c.get('price_trace')),included_benefit=c.get('included_benefit'),quantity_observed=False)
    if c.get('venue_id') in ('PARKING','VALET'):row['venue_id']=c['venue_id']
 assert sum(g['amount_krw'] for g in groups.values())==ledger['totals']['paid_krw']
 ledger['price_class_aggregates']=dict(policy_version='source-grade-resolution-v2',classes=groups,confirmed_current_source_krw=groups['OFFICIAL']['amount_krw'],historical_reference_krw=groups['EXISTING_REFERENCE']['amount_krw'],
  estimated_or_assumed_krw=sum(groups[t]['amount_krw'] for t in ('COMPARABLE_ESTIMATE','SIMULATION_ASSUMPTION')),actual_cash_observed=False,
  note='Source price class, not observed sales; dated references and model assumptions separated. Tax UNKNOWN unless independently supplied.')
 return ledger

def room_price(flow,pid,service_date,night_index,night_count,base_rates,source_sha):
 v=flow['visits'][pid];opts=flow['visit'].get('catalog_options',{});sku=opts.get('room_products',{}).get(pid);frozen={x['sku_id']:x for x in flow['visit'].get('hotel_price_snapshot',H.DATA)['products']};p=frozen.get(sku) if sku else None
 stay_id=H.digest([flow['visit_id'],pid]);base=dict(version='hotel-catalog-room-v1',stay_id=stay_id,room_id=stay_id+':1',room_count=1,building=v['building'],service_date=service_date,
  billing_unit='room_night',room_count_basis='ONE_ROOM_PER_TEAM_NOT_PARTICIPANT_COUNT',participant_count=v['party_size'],tax_status='UNKNOWN',net_ex_vat_krw=None,actual_cash_observed=False,package_id=sku,price_tier='EXISTING_REFERENCE',catalog_sha256=flow['visit'].get('hotel_catalog_sha256',H.SHA))
 package=flow['visit'].get('package_context') or {}
 if package.get('price_status') in ('VERIFIED_TOTAL','VERIFIED_ROOM_NIGHTLY') and package.get('price_source'):
  # Keep the existing D01 validation/allocation for a confirmed selected package.
  # The opt-in catalog must not replace it with a lower-priority starting rate.
  from room_revenue import native_price
  legacy=copy.deepcopy(flow);legacy['visit'].pop('catalog_policy',None)
  verified=native_price(legacy,pid,service_date,night_index,night_count)
  if verified.get('price_status','').startswith('VERIFIED_'):
   verified.update(price_tier='OFFICIAL',catalog_sha256=base['catalog_sha256'])
   return with_room_addons(verified,flow,pid,night_index)
 if not p:
  import room_revenue as RR, santa_packages as SPK
  santa=SPK.room_night(flow,pid,service_date,night_index)
  if santa:
   priced=dict(base,source_sha256=source_sha,price_tier='SIMULATION_ASSUMPTION',**{k:v2 for k,v2 in santa.items() if k not in ('tax_status','source_sha256')})
   if str(santa.get('package_id','')).startswith('SANTA_PKG_2026_'):priced.update(source_sha256=santa['source_sha256'],tax_status=santa['tax_status'])
   return with_room_addons(priced,flow,pid,night_index)
  if RR.operator_rate(flow,v['building']) is not None:
   return with_room_addons(dict(base,source_sha256=source_sha,price_tier='SIMULATION_ASSUMPTION',**RR.operator_fields(flow,v['building'])),flow,pid,night_index)
  bf=RR.breakfast_room_fields(flow,pid,v['building'])
  if bf:
   return with_room_addons(dict(base,source_sha256=source_sha,price_tier='SIMULATION_ASSUMPTION',**{k:x for k,x in bf.items() if k!='tax_status'}),flow,pid,night_index)
  rate=flow['visit'].get('hotel_base_room_rates',base_rates).get('room:'+v['building']);amount=rate['krw'] if rate else None
  ref=H.OC.room_reference(H.BY[{'GRAND':'HC-MENU-002','VISTA':'HC-MENU-022','DOUGLAS':'HC-MENU-018'}[v['building']]],service_date=service_date,people=v['party_size'],nights=night_count,selected=False)
  other=not service_date.startswith(RR.MODEL_RATE_YEAR)
  return with_room_addons(dict(base,unit_price_krw=amount,virtual_gross_krw=amount,price_source='timeline/prices.py',source_sha256=source_sha,product='객실 1박 · 가상 객실 모델 단가' if other else '객실 1박 · 기존 패키지 시작가 모델',price_status='HISTORICAL_STARTING_RATE_SIMULATION',model_rate_outside_model_year=other,price_reference_contract=ref,source_note=(RR.MODEL_NOTE_OTHER_YEAR+' · ' if other else '')+ref['note']),flow,pid,night_index)
 condition=flow['visit'].get('resolved_conditions',{}).get(pid,{})
 a=SimpleNamespace(sc={'date':service_date,'catalog_options':opts},N=v['party_size'],B=v['building'],stay=True,checked_in=True,checked_out=False,vs=dict(nights=night_count,party_composition=condition.get('party_composition',v.get('party_composition'))),C={'kids':bool((condition.get('party_composition',v.get('party_composition')) or {}).get('children')) or v.get('kids',False)},pid=pid)
 why=H.eligible(p,a,0,0,period='booking')
 if why:raise ValueError('HC_ROOM_NOT_ELIGIBLE:'+','.join(why))
 p=H.price(p,opts);amount=p['unit_price_krw'];trace=copy.deepcopy(p.get('price_trace'))
 discount=p.get('discount_krw',0)
 if p['billing_unit']=='room_bundle':
  q,rem=divmod(amount,night_count);amount=q+(night_index<rem)
  original=p['unit_price_krw']+discount;oq,ore=divmod(original,night_count);discount=oq+(night_index<ore)-amount
  if trace:trace=dict(sku_id=p['sku_id'],scope='ALLOCATED_ROOM_NIGHT',source_bundle_quote=trace,service_date=service_date,night_index=night_index,night_count=night_count,effective_unit_price_krw=amount,scenario_unit_price_before_discount_krw=amount+discount)
 return with_room_addons(dict(base,product=p['label'],unit_price_krw=amount,virtual_gross_krw=amount,price_source=p['source_path'],source_sha256=p['source_sha256'],
  price_tier=p['price_tier'],price_status=p['price_status'],selected_room_sku_id=p['sku_id'],price_trace=trace,discount_krw=discount,allocation='ONE_SELECTED_PACKAGE_ALLOCATED_ONCE' if p['billing_unit']=='room_bundle' else 'ONE_ROOM_UNIT_EACH_NIGHT',included_description=p.get('included_description',''),price_reference_contract=H.OC.room_reference(p,service_date=service_date,people=v['party_size'],nights=night_count,selected=True) if p.get('price_is_starting_rate') else None),flow,pid,night_index)


def with_room_addons(result,flow,pid,night_index):
 opts=flow['visit'].get('catalog_options',{});start=flow['visit']['start_date'];day=result['service_date'];parts=[]
 for order in opts.get('purchase_orders',{}).get(pid,[]):
  if order['venue_id']!=result['building'] or order['service_period']!='booking':continue
  if order['date'] not in (start,day):continue
  for item in order['items']:
   frozen={x['sku_id']:x for x in flow['visit'].get('hotel_price_snapshot',H.DATA)['products']}
   p=frozen[item['sku_id']]
   if p['role']!='ADDON':raise ValueError('HC_ROOM_ADDON_ROLE_REQUIRED')
   if not H.day_ok(p,day):raise ValueError('HC_ROOM_ADDON_DATE')
   nightly='1박' in p['source_unit']
   if not nightly and night_index>0:continue
   a=SimpleNamespace(sc={'catalog_options':opts},pid=pid)
   part=H.component(p,item['quantity'],a,assumption='EXPLICIT_ROOM_ADDON_QUANTITY_NOT_ROOM_COUNT');part['catalog_sha256']=flow['visit'].get('hotel_catalog_sha256',H.SHA);parts.append(part)
 if result['virtual_gross_krw'] is None:
  if parts:raise ValueError('HC_ROOM_ADDON_REQUIRES_PRICED_ROOM_NIGHT')
  return result
 base=dict(sku_id=result.get('selected_room_sku_id') or (result.get('package_id') if str(result.get('package_id','')).startswith('SANTA_PKG_2026_') else None) or 'HC-ROOM-BASE-'+result['building'],label=result['product'],venue_id=result['building'],unit_price_krw=result['virtual_gross_krw'],billing_quantity=1,billing_unit='room_night',source_path=result['price_source'],source_sha256=result['source_sha256'],catalog_sha256=H.SHA,price_tier=result['price_tier'],price_status=result['price_status'])
 base.update(price_reference_contract=copy.deepcopy(result.get('price_reference_contract')),price_trace=copy.deepcopy(result.get('price_trace')),discount_krw=result.get('discount_krw',0))
 all_parts=[base]+parts
 result.update(virtual_gross_krw=sum(p['unit_price_krw']*p['billing_quantity'] for p in all_parts),room_order_contract=dict(sku_id='HC-ROOM-ORDER-'+H.digest(all_parts)[:20],label='객실 및 명시 추가 주문',venue_id=result['building'],billing_unit='order',billing_quantity=1,unit_price_krw=sum(p['unit_price_krw']*p['billing_quantity'] for p in all_parts),components=all_parts,catalog_sha256=H.SHA,source_sha256=H.SHA,source_path='hotel_catalog.json',price_tier=max((p['price_tier'] for p in all_parts),key=H.TIERS.index),price_status='EXPLICIT_ROOM_COMPONENT_ORDER'))
 return result
