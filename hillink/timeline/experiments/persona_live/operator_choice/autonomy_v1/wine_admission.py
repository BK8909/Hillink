"""C01 wine ENTRY contract. No attendance policy, meal or purchase inference."""
import copy,csv,hashlib
from pathlib import Path
VERSION='c01-wine-admission-v1'
ROOT=Path(__file__).resolve().parents[5]
SOURCE=ROOT/'timeline/place_assumptions.csv'
SOURCE_SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
ROWS=list(csv.DictReader(SOURCE.read_text(encoding='utf-8-sig').splitlines()))
# Source CSV uses Korean labels; no copied author text or API credentials.
def source_rows():
 return [dict(source_path='timeline/place_assumptions.csv',source_line=i,source_sha256=SOURCE_SHA,record=r)
  for i,r in enumerate(ROWS,2) if any('와인페어 입장료' in str(v) for v in r.values())]
MODES={'auto','guest_admission','package_included','paid_ticket'}
def validate(value):
 if value is None:return {}
 if not isinstance(value,dict):raise ValueError('WINE_ADMISSION_INPUT_INVALID')
 for pid,v in value.items():
  if not isinstance(pid,str) or not isinstance(v,dict) or set(v)-{'mode','adult_tickets','child_tickets'} or v.get('mode','auto') not in MODES:raise ValueError('WINE_ADMISSION_INPUT_INVALID')
  counts=[v.get('adult_tickets'),v.get('child_tickets')]
  if any(x is not None and (type(x)!=int or not 0<=x<=8) for x in counts):raise ValueError('WINE_TICKET_COUNTS_INVALID')
  if any(x is not None for x in counts) and any(x is None for x in counts):raise ValueError('WINE_TICKET_COUNTS_MUST_BE_COMPLETE')
 return copy.deepcopy(value)
def contract(actor,snapshot,t):
 cfg=snapshot.get('wine_admission',{}).get(actor.pid,{})
 mode=cfg.get('mode','auto');included=snapshot.get('entitlements',{}).get(actor.pid)
 current_guest=actor.stay and actor.checked_in and not actor.checked_out
 c=dict(sku_id='C01-WINE-ENTRY-UNKNOWN',venue_id='FOREST_PARK',service_period='event',
  unit_price_krw=None,billing_quantity=1,billing_unit='order',price_status='AMOUNT_UNKNOWN',
  admission_mode=mode,paid_ticket_benefits_included=False,package_entitlement_applied=False,
  additional_food_drink=dict(status='NOT_SELECTED_NOT_CHARGED',price_status='AMOUNT_UNKNOWN',requires='SEPARATE_ACTUAL_PURCHASE_AND_PRODUCT_PRICE_CONTRACT'),
  source_path='timeline/place_assumptions.csv',source_sha256=SOURCE_SHA,source_refs=source_rows(),
  scenario_id=snapshot['scenario_id'],snapshot_sha256=snapshot['snapshot_sha256'],contract_version=VERSION,
  current_sale_confirmed=False,reservation_confirmed=False,transaction_confirmed=False,
  input_provenance='SCENARIO_NOT_OBSERVED_REVIEW_FACT',tax_status='UNKNOWN')
 if mode=='package_included':
  if not current_guest:
   c['unknown_reason']='CURRENT_GUEST_PACKAGE_ELIGIBILITY_UNCONFIRMED';return c
  if not included or included.get('selected_package') is not True or actor.N>included['included_people']:
   c['unknown_reason']='EXPLICIT_PACKAGE_COVERAGE_REQUIRED';return c
  c.update(sku_id='C01-WINE-PACKAGE-ENTRY',unit_price_krw=0,price_status='PACKAGE_INCLUDED_ENTRY_NOT_NEW_REVENUE',package_entitlement_applied=True,
    benefits_status='ENTRY_ONLY_OTHER_PACKAGE_BENEFITS_NOT_CONFIRMED',coverage_input=copy.deepcopy(included));return c
 if mode in ('auto','guest_admission') and current_guest:
  c.update(sku_id='C01-WINE-GUEST-FREE-ENTRY',unit_price_krw=0,price_status='GUEST_FREE_ENTRY_ONLY',benefits_status='PAID_TICKET_GOODS_FOOD_VOUCHER_NOT_INCLUDED');return c
 if mode=='guest_admission' or mode=='auto' and actor.stay:
  c['unknown_reason']='BEFORE_CHECKIN_OR_AFTER_CHECKOUT_GUEST_FREE_SCOPE_UNCONFIRMED';return c
 # Deliberate paid ticket purchase is separate from a guest's free admission.
 adult=cfg.get('adult_tickets');child=cfg.get('child_tickets')
 if adult is None:
  party=getattr(actor,'vs',{}).get('party_composition')
  if party and not party['children']:adult=party['adult_count'];child=0
  elif not actor.C.get('kids'):adult=actor.N;child=0;c['ticket_count_basis']='VIRTUAL_NONCHILD_PARTY_TICKET_ASSUMPTION_NOT_VERIFIED_AGES'
  else:c['unknown_reason']='PAID_TICKET_ADULT_CHILD_COUNTS_AND_AGE_ELIGIBILITY_UNRESOLVED';return c
 if adult+child!=actor.N:
  c['unknown_reason']='PAID_TICKET_COUNTS_MUST_MATCH_MODELED_ATTENDEES';return c
 if child and t>=15*60:
  # Second session child applicability remains inconsistent in the collected card.
  c['unknown_reason']='SECOND_SESSION_CHILD_TICKET_ELIGIBILITY_UNCONFIRMED';return c
 if child and adult==0:
  c['unknown_reason']='CHILD_WITHOUT_ADULT_ENTRY_UNCONFIRMED';return c
 c.update(sku_id='C01-WINE-PAID-TICKET-ORDER',unit_price_krw=55000*adult,price_status='DATED_PAID_TICKET_MODEL_REFERENCE',paid_ticket_benefits_included=True,
   ticket_components=[dict(ticket='adult',quantity=adult,unit_price_krw=55000),dict(ticket='accompanied_first_session_child',quantity=child,unit_price_krw=0)],
   benefits=['wine_tasting_adults_only','riedel_glass','chilling_bag','one_food_voucher_per_paid_adult_ticket','raffle_entry'],
   benefits_status='SOURCE_LISTED_PAID_TICKET_BENEFITS_NOT_EXTRA_PURCHASES',alcohol_age_eligibility='UNKNOWN_NOT_CONFIRMED_BY_TICKET_COUNT')
 return c

def bind(actor,offer,snapshot,t):
 c=contract(actor,snapshot,t);o=copy.deepcopy(offer)
 from . import hotel_catalog as H
 if H.enabled(actor) and c.get('ticket_components') and c.get('unit_price_krw') is not None:
  parts=[]
  for ticket in c['ticket_components']:
   if not ticket['quantity']:continue
   key='HC-MENU-240' if ticket['ticket']=='adult' else 'HC-MENU-241'
   part=H.component(H.BY[key],ticket['quantity'],actor)
   if ticket['unit_price_krw']==0:part.update(unit_price_krw=0,included_benefit='SOURCE_FREE_CHILD_ADMISSION',discount_krw=0)
   parts.append(part)
  total=H.compose(parts,actor,'event')
  c.update(components=parts,unit_price_krw=total['unit_price_krw'],catalog_policy=H.POLICY,catalog_sha256=H.SHA,price_tier=total['price_tier'],discount_krw=total['discount_krw'])
  if any(p.get('price_trace') for p in parts):c['price_status']=total['price_status']
  for ticket,part in zip([x for x in c['ticket_components'] if x['quantity']],parts):ticket.update(unit_price_krw=part['unit_price_krw'],price_trace=part.get('price_trace'))
 o.update(sku_contract=c,sku_id=c['sku_id'],price_status=c['price_status'],
          price_pp_krw=None if c['unit_price_krw'] is None else c['unit_price_krw']/actor.N,
          in_package=c['package_entitlement_applied'],guest_discount_krw=0,card_benefit_krw=0)
 o.setdefault('service_contract',{}).update(admission_contract=copy.deepcopy(c),price_status=c['price_status'])
 return o

def charge(offer):
 c=copy.deepcopy(offer['sku_contract']);amount=c['unit_price_krw']
 status='가격 미정' if amount is None else '포함' if c['package_entitlement_applied'] else '무료' if amount==0 else '유료'
 return dict(status=status,krw=amount,per='건',sku_contract=c,auto_charge=False,c01_structured_order_quantity=amount is not None,
  price_kind=c['price_status'],basis='와인페어 입장 계약: '+c['price_status']+'; 추가 식음 구매 별도 · 실구매/예약 미확인',
  unknown_reason=c.get('unknown_reason'),event_entry_only=True)
