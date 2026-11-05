"""Dated Santa 2026 contract. No preference coefficients or 2025 ticket prices."""
import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

PATH = Path(__file__).with_name('santa_2026_contract.json')
DATA = json.loads(PATH.read_text())
SHA = hashlib.sha256(PATH.read_bytes()).hexdigest()
ID = DATA['event_id']
SESSIONS = DATA['sessions']
PACKAGES = {}
for key, building, label, price, breakfast, lounge, sauna in (
    ('GRAND_HYVAA_JOULUA', 'GRAND', 'Grand Hyvää', 549000, 'THE_BUFFET', False, False),
    ('GRAND_JOULUA', 'GRAND', 'Grand Joulua', 829000, 'CLUB_WEEKDAY_BUFFET', True, False),
    ('VISTA_DELUXE', 'VISTA', 'Vista Christmas Wishes Deluxe', 597000, 'THE_BUFFET', False, False),
    ('VISTA_SIGNATURE', 'VISTA', 'Vista Christmas Wishes Signature', 757000, 'THE_BUFFET', True, True),
):
    pid = 'SANTA_PKG_2026_' + key
    PACKAGES[pid] = dict(package_id=pid, year=2026, label=label+' · 1박', buildings=(building,),
        price_krw=price, nights=1, base_adults=2, base_children=1,
        included=('ROOM_NIGHT', 'BREAKFAST', 'SANTA_ADMISSION', 'PHOTO_ONCE', 'GIFT_ONCE'),
        stay_from=DATA['dates'][0], stay_to=DATA['dates'][1],
        price_status='SANTA_PACKAGE_2026_OFFICIAL_STARTING_PRICE_REFERENCE',
        price_class='OFFICIAL_STARTING_RATE_NOT_CONFIRMED_SALE',
        price_class_ko='공식 시작가를 적용한 가상 객실 가격 · 날짜별 확정가 아님',
        source_status='OFFICIAL_CAPTURE_AND_PAGE_CHECKED_20261104', source=next(s for s in DATA['sources'] if s['key']==('vista' if building=='VISTA' else 'grand')),
        package_sessions={'3부':'15:20','4부':'16:40'}, breakfast_venue=breakfast,
        lounge=lounge, sauna=sauna, runnable=True,
        ambiguity='예약·재고 미확인. 1박 시작가, 추가 객실 인원·식음 10% 혜택의 SKU/중복 적용은 미검수.',
        benefits=dict(breakfast=breakfast, happy_hour=('17:30–19:30 · 17시 이후 만 12세 이하 제한' if sauna else '클럽 해피아워 · 시간은 기존 모델 참고, 17시 이후 만 12세 이하 제한') if lounge else None,
                      tea_time=key=='GRAND_JOULUA', sauna='VISTA · 만 17세 이상 · 2인 1회 또는 1인 2회' if sauna else None))

def package(snapshot, pid):
    if (snapshot or {}).get('event_card_id') != ID:
        return None
    e = snapshot.get('entitlements', {}).get(pid, {})
    return PACKAGES.get(e.get('package_id')) if e.get('selected_package') is True else None

def validate(config, start, duration):
    """Only the two source-confirmed package sessions are executable."""
    if not DATA['dates'][0] <= start <= DATA['dates'][1]:
        raise ValueError('SANTA_2026_OUTSIDE_OFFICIAL_PERIOD')
    a = config.get('assumptions') or {}
    if not isinstance(config.get('entitlements',{}),dict):raise ValueError('SANTA_2026_PACKAGE_FIELDS_INVALID')
    if a.get('sessions', SESSIONS) != SESSIONS:
        raise ValueError('SANTA_2026_PACKAGE_SESSIONS_3_AND_4_ONLY')
    if a.get('duration_min', 70) != 70 or a.get('meal_fraction', 0) != 0:
        raise ValueError('SANTA_2026_70_MIN_NOT_A_MEAL')
    for pid, e in (config.get('entitlements') or {}).items():
        if not isinstance(e, dict) or set(e)-{'selected_package','included_people','package_id','booking_date','earlybird'}:
            raise ValueError('SANTA_2026_PACKAGE_FIELDS_INVALID')
        if e.get('selected_package') is not True or e.get('package_id') not in PACKAGES or e.get('included_people') != 3:
            raise ValueError('SANTA_2026_PACKAGE_CONTRACT_REQUIRED')
        if duration == 'day_visit':
            raise ValueError('SANTA_2026_PACKAGE_REQUIRES_ROOM_NIGHT')
        booked = e.get('booking_date')
        if booked is not None:
            if not isinstance(booked,str):raise ValueError('BOOKING_DATE_INVALID')
            date.fromisoformat(booked)
            if booked > start:raise ValueError('BOOKING_AFTER_ARRIVAL')
        if type(e.get('earlybird', False)) is not bool:raise ValueError('EARLYBIRD_BOOLEAN_REQUIRED')
        if e.get('earlybird') and not (booked and '2026-11-02' <= booked <= '2026-11-08'):
            raise ValueError('EARLYBIRD_REQUIRES_ELIGIBLE_BOOKING_DATE')
    bookings=a.get('booked_sessions') or {}
    if not isinstance(bookings,dict):raise ValueError('BOOKED_SESSIONS_INVALID')
    for pid, b in bookings.items():
        if not isinstance(b,dict):raise ValueError('BOOKED_SESSION_FIELDS_INVALID')
        if pid not in config.get('entitlements', {}):raise ValueError('SANTA_2026_SESSION_REQUIRES_PACKAGE')
        if b.get('date') != start:raise ValueError('SANTA_2026_INCLUDED_ADMISSION_FIRST_DAY_ONLY')
        if b.get('start') not in ('15:20','16:40'):raise ValueError('SANTA_2026_EXPLICIT_SESSION_REQUIRED')

def validate_visits(snapshot, visits, request):
    if not snapshot or snapshot['event_card_id'] != ID:return
    if request.get('package_id') or request.get('catalog_options', {}).get('room_products'):
        raise ValueError('SANTA_2026_NO_SECOND_ROOM_PACKAGE')
    for pid in snapshot['entitlements']:
        p=package(snapshot,pid);v=visits[pid];party=v.get('party_composition') or {}
        if v['building'] not in p['buildings']:raise ValueError('SANTA_2026_PACKAGE_BUILDING_MISMATCH')
        if party.get('adult_count') != 2 or len(party.get('children', [])) != 1 or v['party_size'] != 3:
            raise ValueError('SANTA_2026_EXTRA_ROOM_OCCUPANTS_HOLD_REQUIRES_2_ADULT_1_CHILD')

def source():
    return dict(path='timeline/experiments/persona_live/operator_choice/autonomy_v1/santa_2026_contract.json',
        sha256=SHA, csv_line=None, record={'행사 · 상품명':DATA['title'], '구분':'공식 계약 · 가상 실행',
        '출처 (공식 · 당시 안내)':' / '.join(s['url'] for s in DATA['sources']), '확인 시점':'2026-11-04'},
        capture_sources=copy.deepcopy(DATA['sources']))

def actor_package(a):
    snap=a.sc.get('scenario_snapshot')
    p=package(snap,a.pid)
    return p if p and a.sc['date']<=breakfast_day(snap) else None

def breakfast_day(snapshot):return (date.fromisoformat(snapshot['start_date'])+timedelta(days=1)).isoformat()

def benefit(a, c):
    """Source-covered breakfast, no extra order or charge; one package morning."""
    p=actor_package(a)
    if not p:return None
    s=a.sc['scenario_snapshot']
    if c['venue_id']=='GRAND_CLUB_LOUNGE' and p['lounge']:
        sku=c['components'][0]['sku_id'];key=p['package_id']+'_'+sku
        if not a.visit_history.get('hotel_entitlement_usage',{}).get(key):
            out=copy.deepcopy(c);out.update(hc_included=True,hotel_entitlement_key=key,benefit_coverage_people=3);return out
    if c['service_period']=='breakfast' and c['venue_id']=='THE_BUFFET' and a.sc['date']==breakfast_day(s):
        # Joulua weekend breakfast is supplied by the club adapter, never relabelled buffet.
        if p['breakfast_venue']=='CLUB_WEEKDAY_BUFFET' and date.fromisoformat(a.sc['date']).weekday()>=5:return None
        key=p['package_id']+'_BREAKFAST'
        if not a.visit_history.get('hotel_entitlement_usage',{}).get(key):
            out=copy.deepcopy(c);out.update(hc_included=True,hotel_entitlement_key=key,benefit_coverage_people=3)
            return out
    return None


def lounge_reasons(a, product, t, duration):
    p=actor_package(a)
    if not p or not p['lounge']:return None
    why=[];sku=product['sku_id'];party=a.vs.get('party_composition') or {}
    if t+duration>17*60 and any(c.get('age_months') is None or c['age_months']<13*12 for c in party.get('children',[])):
        why.append('SANTA_PACKAGE_17H_CHILD_RESTRICTION_PARTY_SPLIT_NOT_MODELED')
    if p['sauna'] and sku!='HC-GRAND-LOUNGE-278':why.append('SIGNATURE_HAPPY_HOUR_ONLY_NO_CLUB_TEA_BREAKFAST')
    if sku=='HC-GRAND-LOUNGE-276':why.append('PACKAGE_BREAKFAST_USES_SEPARATE_MORNING_CONTRACT')
    key=p['package_id']+'_'+sku
    if a.visit_history.get('hotel_entitlement_usage',{}).get(key):why.append('PACKAGE_LOUNGE_SERVICE_ALREADY_USED')
    return why
