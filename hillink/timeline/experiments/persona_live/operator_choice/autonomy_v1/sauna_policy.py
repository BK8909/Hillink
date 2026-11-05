"""Facility-specific model tariffs. A 2026 reference is not a 2025 sale quote."""
import copy, hashlib, json
from datetime import date
from pathlib import Path
PATH=Path(__file__).with_name('sauna_policy_20261103.json')
DATA=json.loads(PATH.read_text()); VERSION=DATA['version']

def load(catalog, sha):
    catalog=copy.deepcopy(catalog)
    for p in catalog['products']:
        if p.get('source_line') not in (231,232):continue
        facility='GRAND_SAUNA' if p['source_line']==231 else 'VISTA_SAUNA'
        p.update(facility_id=facility,sauna_policy=VERSION,unit_price_krw=20000 if facility=='GRAND_SAUNA' else 55000,
          price_tier='SIMULATION_ASSUMPTION',price_status='CURRENT_REFERENCE_MODEL_NOT_HISTORICAL_TARIFF',
          price_confirmed=True,charge_policy='FACILITY_GUEST_BUILDING_MODEL',source_service_windows='06:00-22:00',
          source_unit='만 17세 이상 실제 가상 이용 인원 · 투숙 건물별 참고 단가',source_checked_at=DATA['checked_at'],
          price_basis_date=DATA['checked_at'],historical_tariff_confirmed=False,
          facility_rule_note='Facility/building-specific 2026-11-03 reference model; 17+; 06:00-22:00; facility-specific closure and contracted benefits; historical tariff and gender-specific access unconfirmed',
          official_source=DATA['grand_source'] if facility=='GRAND_SAUNA' else DATA['vista_source'],
          label='그랜드 사우나' if facility=='GRAND_SAUNA' else '비스타 웰니스 사우나',
          source_document='2026-11-03 user-confirmed official facility/chatbot model; historical date tariff unverified')
    catalog['sauna_policy']=VERSION
    return catalog,hashlib.sha256((sha+hashlib.sha256(PATH.read_bytes()).hexdigest()).encode()).hexdigest()

def room(a):
    from . import hotel_catalog as H
    return H.BY.get(H.options(a).get('room_products',{}).get(a.pid),{})

def contract(a):
    from . import santa_2026 as S26
    santa=S26.actor_package(a)
    if santa and santa['sauna'] and a.sc['date']<=S26.breakfast_day(a.sc['scenario_snapshot']):
        return dict(facility_id='VISTA_SAUNA',people=2,solo_two_uses=True,frequency_basis='ONE_SELECTED_PACKAGE_NIGHT_TWO_ADULT_USES')
    p=room(a); rule=DATA['room_contracts'].get(p.get('sku_id'))
    pkg=a.vs.get('package_context') or {}
    if pkg.get('id')=='GRAND_SUNGSU_V2_2N':
        rule=DATA['room_contracts']['HC-MENU-007'];p={'valid_from':pkg.get('effective_from'),'valid_until':pkg.get('effective_to')}
    if not rule:return None
    day=a.sc['date']
    if p.get('valid_from') and day<p['valid_from'] or p.get('valid_until') and day>p['valid_until']:return None
    return rule

def facility(a):
    # A selected source benefit names the actual facility, even across buildings.
    c=contract(a)
    if c:return c['facility_id']
    for o in a.sc.get('catalog_options',{}).get('purchase_orders',{}).get(a.pid,[]):
        if o['date']==a.sc['date'] and o['venue_id']=='SAUNA':
            if any(i['sku_id']=='HC-MENU-232' for i in o['items']):return 'VISTA_SAUNA'
    return 'VISTA_SAUNA' if a.B=='VISTA' else 'GRAND_SAUNA'

def participants(a):
    from . import hotel_catalog as H
    p=H.modeled_party(a)
    return p['adult_count']+sum(c.get('age_months') is not None and c['age_months']>=204 for c in p['children']) if p else a.N

def reasons(p,a,t,duration):
    f=p.get('facility_id');rule=DATA['facilities'][f];why=[]
    if a.B not in rule['rates']:why.append('SAUNA_CROSS_BUILDING_NOT_AUTHORIZED')
    if participants(a)<1:why.append('NO_CONFIRMED_AGE_ELIGIBLE_SAUNA_PARTICIPANT')
    d=date.fromisoformat(a.sc['date'])
    if d.weekday()==rule['closure_weekday'] and (d.day-1)//7+1==rule['closure_ordinal']:why.append(f+'_REGULAR_CLOSURE')
    return why

def product(p,a):
    if not p.get('sauna_policy'):return p
    p=copy.deepcopy(p);f=p['facility_id'];rate=DATA['facilities'][f]['rates'].get(a.B)
    if rate is None:raise ValueError('SAUNA_CROSS_BUILDING_NOT_AUTHORIZED')
    p.update(unit_price_krw=rate,price_key=f+':'+a.B,guest_building=a.B,service_date=a.sc['date'],
      price_status='2026_REFERENCE_APPLIED_TO_OTHER_YEAR_SCENARIO' if a.sc['date'][:4]!='2026' else '2026_REFERENCE_MODEL_NOT_DATE_QUOTE',
      date_specific_tariff_confirmed=False,sauna_eligible_people=participants(a),party_total_people=a.N,
      participant_scope='MODELED_AGE_ELIGIBLE_PARTICIPANTS_NOT_ENTIRE_FAMILY',gender_access=DATA['gender_access'])
    return p

def benefit(a,c):
    from . import hotel_catalog as H
    rule=contract(a);facility_id=c['components'][0].get('facility_id');usage=a.visit_history.get('hotel_entitlement_usage',{})
    key='HC_ROOM_SAUNA_ONCE'
    if (a.vs.get('package_context') or {}).get('id')=='GRAND_SUNGSU_V2_2N':
        used=((a.visit_history.get('benefit_usage') or {}).get('package_entitlements') or {}).get('GRAND_SUNGSU_SAUNA',{})
        if used.get('remaining')==0:return c
    if rule and rule['facility_id']==facility_id:
        cover=rule['people']
        if rule['solo_two_uses'] and participants(a)==1 and usage.get(key):key='HC_ROOM_SAUNA_028_SOLO_SECOND'
        if usage.get(key):return c
    else:
        # Exact contracted room subtype only. Mixed catalog choices are not proof.
        p=room(a);rt=p.get('source_room_types','');nights=a.vs.get('nights',0)
        exact=rt in ('클럽 스위트','더글라스 스위트','빌라')
        if facility_id!='GRAND_SAUNA' or not exact or not nights:return c
        if p.get('valid_from') and a.sc['date']<p['valid_from'] or p.get('valid_until') and a.sc['date']>p['valid_until']:return c
        used=sum(bool(v) for k,v in usage.items() if k.startswith('GRAND_SUITE_SAUNA_NIGHT_'))
        if used>=nights:return c
        key='GRAND_SUITE_SAUNA_NIGHT_'+a.sc['date']
        if usage.get(key):return c
        cover=2
    parts=[];left=cover
    for p in c['components']:
        n=p['billing_quantity'];free=min(left,n);left-=free
        if free:parts.append(dict(p,billing_quantity=free,unit_price_krw=0,original_list_unit_price_krw=p['unit_price_krw'],included_benefit=key))
        if n>free:parts.append(dict(p,billing_quantity=n-free))
    out=H.compose(parts,a,c['service_period']);out.update(hotel_entitlement_key=key,benefit_coverage_people=cover,benefit_facility_id=facility_id,benefit_frequency_basis=rule['frequency_basis'] if rule else 'ONE_USE_PER_ROOM_NIGHT')
    if all(p['unit_price_krw']==0 for p in parts):out['hc_included']=True
    return out
