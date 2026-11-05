"""Santa Kids Village room packages — explicit operator selection only.

A package is never bought because a family attends Santa: it applies only when the run's scenario carries an explicit
entitlement for that customer (scenario.entitlements[pid].selected_package). One package covers one room night (the
first night of the stay inside the package stay window); further nights are priced as ordinary rooms. Included
breakfast and Santa admission are settled at 0 so nothing is charged twice. Prices are virtual scenario references,
not confirmed sales.
"""
SANTA_CARD = 'SANTA_KIDS_VILLAGE_2025'
SOURCE_NOTE = ('2025: SK네트웍스 보도자료(2025-12-01, sknetworks.co.kr/pr/news-room/LiZMQgmQELe9pu9v) — 관제 확인 내용 기준 '
               '"559,000원부터"·휘바 욜루아(그랜드)/크리스마스 위시스(비스타)·1박+더뷔페 조식+산타 입장·패키지 고객 3·4부 입장. '
               '세션 내 원문 접근은 차단되어 직접 대조 못 함. 559,000원은 시작가이며 전 객실 등급 확정가 아님. '
               '2026 가격(549,000/597,000/757,000)은 별도 연도 자료로 분리 관리')
SOURCE_STATUS_2025 = 'PRESS_RELEASE_STARTING_PRICE_CONFIRMED_BY_OPERATOR'
SANTA_SESSIONS_2025 = {'3부': '15:20', '4부': '16:30'}   # 패키지 고객 입장 회차(보도자료 기준) · 예약 기본값은 운영자 가정
PACKAGES = {
    'SANTA_PKG_2025': dict(
        package_id='SANTA_PKG_2025', year=2025, label='2025 산타 키즈 빌리지 객실 패키지 · 1박',
        buildings=('GRAND', 'VISTA'), price_krw=559000, nights=1, base_adults=2, base_children=1,
        included=('ROOM_NIGHT', 'BREAKFAST', 'SANTA_ADMISSION'), stay_from='2025-12-19', stay_to='2025-12-25',
        price_status='SANTA_PACKAGE_2025_VIRTUAL_BASE_PRICE', price_class='OPERATOR_SCENARIO_ASSUMPTION',
        price_class_ko='2025 산타 패키지 가상 기준가(보도자료 "559,000원부터" · 건물·등급별 확정가 아님)', source_status=SOURCE_STATUS_2025,
        package_sessions=SANTA_SESSIONS_2025, package_names=('휘바 욜루아(그랜드)', '크리스마스 위시스(비스타)'),
        ambiguity='보도자료는 "559,000원부터"만 확인 · 비스타 등 상위 등급 2025 가격 미확인(597,000은 2026 비스타 자료) → 559,000을 두 건물 공통 가상 기준가로 사용',
        runnable=True),

}

# Source-reviewed 2026 contracts replace only the previously non-runnable 2026 references.
from operator_choice.autonomy_v1 import santa_2026 as S26
PACKAGES.update(S26.PACKAGES)


def selected(flow, pid):
    """The explicitly selected Santa package for this customer, or None."""
    snap = (flow.get('visit') or {}).get('scenario_snapshot') or {}
    if snap.get('event_card_id') == S26.ID:return S26.package(snap,pid)
    if snap.get('event_card_id') != SANTA_CARD:
        return None
    e = (snap.get('entitlements') or {}).get(pid)
    if not e or e.get('selected_package') is not True:
        return None
    return PACKAGES['SANTA_PKG_2025']


def room_night(flow, pid, service_date, night_index):
    """Package pricing for this room night, or None (ordinary room pricing applies)."""
    p = selected(flow, pid)
    if not p or night_index != 0:
        return None
    v = flow['visits'][pid]
    if v.get('building') not in p['buildings'] or not p['stay_from'] <= service_date <= p['stay_to']:
        return None
    people = v.get('party_size') or 0
    base = p['base_adults'] + p['base_children']
    e=((flow.get('visit') or {}).get('scenario_snapshot') or {}).get('entitlements',{}).get(pid,{})
    amount=p['price_krw']
    if p['year']==2026 and e.get('earlybird'):
        from decimal import Decimal, ROUND_HALF_UP
        amount=int((Decimal(amount)*Decimal('0.92')).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    result = dict(virtual_gross_krw=amount, unit_price_krw=amount,
                product=p['label'] + ' (조식·산타 입장 포함)', price_status=p['price_status'],
                price_source='timeline/viewer/santa_packages.py:' + p['package_id'], source_note=(SOURCE_NOTE if p['year']==2025 else p['source']['url']) + ' · ' + p['ambiguity'],
                package_id=p['package_id'], package_price_class=p['price_class'], package_price_class_ko=p['price_class_ko'],
                package_included=list(p['included']), package_base_people=base,
                unpriced_extras=['additional_people'] if people > base else [],
                allocation='ONE_PACKAGE_ONE_FIRST_NIGHT; LATER_NIGHTS_ORDINARY_ROOM_MODEL', tax_status='INCLUDED' if p['year']==2026 else 'UNKNOWN')

    if p['year']==2026:
        result.update(original_list_unit_price_krw=p['price_krw'],discount_krw=p['price_krw']-amount,source_sha256=S26.SHA,package_benefits=p['benefits'],
            price_trace=dict(sku_id=p['package_id'],catalog_unit_price_krw=p['price_krw'],scenario_unit_price_before_discount_krw=p['price_krw'],
                discount_percent=8 if e.get('earlybird') else 0,effective_unit_price_krw=amount,rounding='KRW_HALF_UP',
                source='OFFICIAL_STARTING_RATE_AND_EXPLICIT_BOOKING_DATE',booking_date=e.get('booking_date')))
    return result
