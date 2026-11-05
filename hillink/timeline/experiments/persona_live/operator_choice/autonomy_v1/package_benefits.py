"""Eligibility and redemption of an explicitly selected fire package.
No automatic attendance, retail order, wine brand or internal revenue allocation.
"""
import copy
FAIR_DATES={f'2026-10-{d:02}' for d in (10,11,17,18,24,25)}
KEY='HC_PACKAGE_017_FIRE_REDEMPTION_ONCE_PER_STAY_MODEL'

def selected(a):
    return a.sc.get('catalog_options',{}).get('room_products',{}).get(a.pid)=='HC-MENU-017'

def state(a):
    day=a.sc['date']; weather=(a.sc.get('scenario_snapshot') or {}).get('weather') or {}
    bad=weather.get('condition')=='rain' or weather.get('explicit_pool_safety_closure') is True
    variant='FAIR' if day in FAIR_DATES else 'RAIN' if bad else 'FIRE'
    start,end=(1020,1230) if day<='2026-09-27' else (960,1170)
    if variant=='FAIR':start,end=660,1170
    return dict(variant=variant,service_start=start,service_end=end,
      redemption_used=bool(a.visit_history.get('hotel_entitlement_usage',{}).get(KEY)),
      selected_package=selected(a),frequency_basis='ONCE_PER_STAY_SCENARIO_NOT_CONFIRMED_DAILY',
      weather_basis='EXPLICIT_SCENARIO_RAIN_OR_SAFETY_CLOSURE',rain_replacement='SMORES_ONLY',
      wine_fair_food_vouchers_included=False,
      replacement_pickup_window_basis='SOURCE_FAIR_WINDOW' if variant=='FAIR' else 'SOURCE_FIRE_WINDOW' if variant=='FIRE' else 'SAME_FIRE_WINDOW_SCENARIO_RAIN_PICKUP_UNSPECIFIED')

def exclusions(p,a,t,duration):
    if not p.get('package_benefit_variant'):return []
    s=state(a);why=[]
    if not s['selected_package'] or not a.stay or not a.checked_in or a.checked_out:why.append('SELECTED_CURRENT_GUEST_PACKAGE_REQUIRED')
    if s['variant']!=p['package_benefit_variant']:why.append('PACKAGE_EVENT_WEATHER_VARIANT_MISMATCH')
    if s['redemption_used']:why.append('PACKAGE_BENEFIT_ALREADY_REDEEMED')
    if not s['service_start']<=t or t+duration>s['service_end']:why.append('PACKAGE_REDEMPTION_WINDOW')
    return why

def apply(a,c):
    if len(c.get('components',[]))!=1 or not c['components'][0].get('package_benefit_variant'):return None
    out=copy.deepcopy(c);out.update(hc_included=True,hotel_entitlement_key=KEY,benefit_coverage_people=a.N,package_benefit_state=state(a))
    out['components'][0].update(included_benefit=KEY,package_benefit_state=state(a))
    return out
