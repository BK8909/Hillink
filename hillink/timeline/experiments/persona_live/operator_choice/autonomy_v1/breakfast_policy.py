"""Breakfast contract policy (11/03, operator-approved).

BREAKFAST_INCLUDED_DEFAULT_V2 (default): GRAND/VISTA default to a breakfast-included room.
DOUGLAS includes the separate lounge light breakfast right; no upgraded room rate is invented. V1 is retained for historical experiments.

BREAKFAST_CONTRACT_V1 (historical opt-in policy)
  1. room_only (general room)      no automatic breakfast; the buffet is a priced choice (2026 menu / 2025 historical reference)
  2. breakfast_included room       contracted adults (source: 캠크닉 TYPE 2 '더뷔페 조식 · 성인 2인') eat at 0 every stay morning;
                                   other diners are priced; the room night carries the breakfast-included model rate (no double count)
  3. Santa package                 one included breakfast (event_scenarios override), unchanged
LEGACY_STAY_INCLUDED  previous rule: every staying guest's buffet breakfast was assumed included (kept for before/after comparison).
Paid in-room breakfast stays opt-in only (agent_day / catalog), and the morning menu mapping fix stays.
"""
import os
V1='BREAKFAST_CONTRACT_V1'
V2='BREAKFAST_INCLUDED_DEFAULT_V2'
CONTRACT_POLICIES=(V1,V2)
LEGACY='LEGACY_STAY_INCLUDED'
POLICIES=(V1,V2,LEGACY)
PLANS=('room_only','breakfast_included')
CONTRACT_ADULTS=2            # 캠크닉 TYPE 2 · 어텀 캠크닉 TYPE 2: '더뷔페 조식' 성인 2인 기준
INCLUDED_BUILDINGS=('GRAND','VISTA')
# Breakfast-included room model rate = the same package family's TYPE 2 official starting price (TYPE 1 = room-only model rate).
INCLUDED_ROOM_RATE={'GRAND':(313000,'캠크닉 TYPE 2 공식 시작가(객실 + 더뷔페 조식 성인 2인)'),
                    'VISTA':(373000,'어텀 캠크닉 TYPE 2 공식 시작가(객실 + 더뷔페 조식 성인 2인)')}

def policy(sc):
    p=(sc or {}).get('breakfast_policy') or os.environ.get('HILLINK_BREAKFAST_POLICY') or V2
    if p not in POLICIES:raise ValueError('BREAKFAST_POLICY_INVALID')
    return p

def plan(vs, sc=None):
    vs = vs or {}
    if vs.get('breakfast_plan'):
        return vs['breakfast_plan']
    return 'breakfast_included' if policy(sc)==V2 and vs.get('building') in INCLUDED_BUILDINGS+('DOUGLAS',) else 'room_only'

def selected_room(a):
    """An explicit runtime room SKU overrides the generic V2 room plan."""
    if policy(getattr(a,'sc',{}))!=V2 or getattr(a,'sc',{}).get('catalog_policy')!='C01_HOTEL_CATALOG_V1':return None
    sku=(getattr(a,'sc',{}).get('catalog_options') or {}).get('room_products',{}).get(getattr(a,'pid',None))
    if not sku:return None
    from . import hotel_catalog as H
    return H.BY.get(sku)

def covered_adults(a):
    """Buffet adults covered by the selected source contract, or generic room."""
    sc=getattr(a,'sc',{})
    if policy(sc) not in CONTRACT_POLICIES:return 0
    if policy(sc)==V2 and getattr(a,'B',(getattr(a,'vs',{}) or {}).get('building'))=='DOUGLAS':return 0
    room=selected_room(a)
    if room is not None:
        # Never apply the default buffet entitlement to an explicitly room-only
        # catalog purchase. Club/family/conditional breakfast needs its own rule.
        if room['sku_id'] not in ('HC-MENU-003','HC-MENU-023'):return 0
        contract_people=2
    else:
        if plan(getattr(a,'vs',{}),sc)!='breakfast_included':return 0
        contract_people=CONTRACT_ADULTS
    if not (a.stay and getattr(a,'checked_in',True) and not getattr(a,'checked_out',False)) and not getattr(a,'stay',False):return 0
    party=(a.vs or {}).get('party_composition')
    adults=party['adult_count'] if party else a.N
    return min(contract_people,adults)

def whole_party_covered(a):
    party=(a.vs or {}).get('party_composition')
    people=(party['adult_count']+len(party['children'])) if party else a.N
    return covered_adults(a)>=people>0

def validate_plan(value,building,duration,sc=None):
    if value not in PLANS:raise ValueError('조식 조건은 room_only 또는 breakfast_included 중에서 선택해 주세요')
    if value=='breakfast_included' and (duration=='day_visit' or building not in INCLUDED_BUILDINGS+ (('DOUGLAS',) if policy(sc)==V2 else ())):
        raise ValueError('선택한 건물·기간·정책에서 조식 포함 권리를 확인할 수 없습니다')
    return value
