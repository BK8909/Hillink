"""Existing-source product contracts for C01 only; never actual POS orders."""
import csv,hashlib,io
from functools import lru_cache
from pathlib import Path
TL=Path(__file__).resolve().parents[4]
SOURCE=TL/'place_assumptions.csv'
MENU=TL/'menu.csv'
VARIANTS={'MOEGI_MIYABI':('미야비 코스',250000,9),'MOEGI_MOMIJI':('모미지 코스',320000,10)}

@lru_cache(maxsize=1)
def makoto_contract():
 rows=list(csv.reader(io.StringIO(SOURCE.read_text(encoding='utf-8-sig'))))
 matches=[(i,row) for i,row in enumerate(rows,1) if len(row)>8 and row[1]=='MOEGI' and row[2]=='코스 · 마코토']
 if len(matches)!=1:raise ValueError('C01_MAKOTO_SOURCE_NOT_UNIQUE')
 line,r=matches[0]
 menu_rows=list(csv.DictReader(io.StringIO(MENU.read_text(encoding='utf-8-sig'))))
 menu=next(x for x in menu_rows if x['업장']=='모에기' and x['상품']=='마코토 코스')
 if menu['단가']!='210000' or '2인 이상' not in menu['단위'] or menu['시간제한']!='18:00-19:30':raise ValueError('C01_MAKOTO_MENU_CONTRACT_CHANGED')
 if r[3]!='210000' or r[4]!='원/인' or r[5]!='DINNER':raise ValueError('C01_MAKOTO_SOURCE_CONTRACT_CHANGED')
 return {'sku_id':'MOEGI-MAKOTO-DINNER-REFERENCE','venue_id':'MOEGI','service_period':'dinner',
   'minimum_party_size':2,'menu_source_sha256':hashlib.sha256(MENU.read_bytes()).hexdigest(),
   'label':'모에기 마코토 저녁 코스 · 기존 공식 메뉴 기준 가상 계산','unit_price_krw':int(r[3]),'billing_unit':'person_meal',
   'source_path':'timeline/place_assumptions.csv','source_line':line,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
   'source_checked_at':r[9],'source_document':'20260630_moegi.pdf p8','price_status':'DATED_OFFICIAL_MENU_SIMULATION_REFERENCE',
   'current_sale_confirmed':False,'reservation_confirmed':False,'transaction_confirmed':False,
   'valid_from':None,'valid_until':None,'applicability_status':'SOURCE_DATE_AND_PDF_FILENAME_ARE_NOT_VALIDITY_DATES','last_order':'19:30','adult_price_only':True,'tax_status':'UNKNOWN'}

def attach(offer,actor):
 if offer['id'] not in ('MOEGI',*VARIANTS):return offer
 contract=dict(makoto_contract())
 if offer['id'] in VARIANTS:
  name,price,page=VARIANTS[offer['id']]
  rows=list(csv.DictReader(io.StringIO(MENU.read_text(encoding='utf-8-sig'))))
  matches=[(i,r) for i,r in enumerate(rows,2) if r['업장']=='모에기' and r['상품']==name]
  if len(matches)!=1:raise ValueError('C01_DINNER_PRODUCT_NOT_UNIQUE')
  line,row=matches[0]
  if row['단가']!=str(price) or '2인 이상' not in row['단위'] or row['시간제한']!='18:00-19:30':raise ValueError('C01_DINNER_PRODUCT_CONTRACT_CHANGED')
  contract.update(sku_id=offer['id']+'-DINNER-REFERENCE',label='모에기 '+name+' · 기존 공식 메뉴 기준 가상 계산',unit_price_krw=price,source_path='timeline/menu.csv',source_line=line,source_sha256=hashlib.sha256(MENU.read_bytes()).hexdigest(),source_document='20260630_moegi.pdf p'+str(page),source_checked_at='UNKNOWN_OLD_CATALOG_DATE')
 if actor.C.get('kids') or actor.N<contract['minimum_party_size']:
  out=dict(offer,sku_resolution={'status':'PARTY_OR_CHILD_MENU_NOT_RESOLVED','reference_sku':contract['sku_id']})
  if offer['id'] in VARIANTS:
   out.update(available=False,status='SKU_PARTY_OR_CHILD_MENU_NOT_RESOLVED')
   out['service_contract']=dict(offer.get('service_contract',{}),planning_viability='BLOCKED',blocked_reason=out['status'])
  return out
 # Party age composition follows the existing persona's modeled travel party;
 # it is not an observed order. No reservation or discount is manufactured.
 out=dict(offer,sku_contract=contract,sku_id=contract['sku_id'],price_pp_krw=contract['unit_price_krw'],
          label=contract['label'],price_status=contract['price_status'],
          price_source={'grade':'◎','note':'기존 공식 '+contract['source_document']+' · 확인 '+contract['source_checked_at']+' · 현재 판매가/예약 미확인 · 가상 계산'})
 out['service_contract']=dict(offer.get('service_contract',{}),price_status=contract['price_status'],
                              sku_id=contract['sku_id'],reservation_state='UNKNOWN_NOT_BOOKED')
 return out
