"""UI projection of executable package catalogs; no second product catalog."""
from package_entitlements import PACKAGE_CATALOG
from santa_packages import PACKAGES, SANTA_CARD
from datetime import date,timedelta
from functools import lru_cache
import copy,re


def hotel_catalog():
    # Same runtime import path/overlay as the visit engine, including OC metadata.
    from hotel_ledger import H
    return H


@lru_cache(maxsize=1)
def catalog_room_options():
    H=hotel_catalog();rows=[];aliases=[]
    dates=[(date(2025,1,1)+timedelta(days=n)).isoformat() for n in range(730)]
    for p in H.DATA['products']:
        if p['role']!='ROOM':continue
        if p['sku_id']=='HC-MENU-007':
            aliases.append(dict(sku_id=p['sku_id'],option_id='GRAND_SUNGSU_V2_2N',reason='SAME_SOURCE_TWO_NIGHT_PACKAGE_USE_EXISTING_ADAPTER'))
            continue
        text=p.get('included_description','');unit=p.get('source_unit','')
        people=p.get('package_people');m=re.search(r'성인\s*(\d+)인',unit)
        reference_people=int(m[1]) if m else None
        nights=p.get('package_nights') or (2 if p['billing_unit']=='room_bundle' else None)
        room_only=text.strip().startswith('객실만')
        direct_breakfast=p['sku_id'] in ('HC-MENU-003','HC-MENU-023')
        runnable=(room_only or direct_breakfast) and p['venue_id'] in ('GRAND','VISTA','DOUGLAS') and isinstance(p.get('unit_price_krw'),int) and p['unit_price_krw']>0
        reason=None if runnable else '복합 포함 혜택·자격·이용 횟수의 전체 연결 확인 필요'
        dates_ok=[d for d in dates if H.day_ok(p,d)]
        summary=('등록 객실만 상품 · 조식은 실제 유료 선택 시 결제' if room_only else '등록 객실+성인 2인 조식 · 기프트는 상품 설명으로만 보존' if direct_breakfast else '등록 상품 · 자료/혜택 연결 확인 필요')
        if p['venue_id']=='DOUGLAS' and room_only:summary='등록 더글라스 객실 · 기본 라운지 라이트 조식 권리 유지'
        rows.append(dict(id=p['sku_id'],label=p['label'],buildings=[p['venue_id']],nights=nights,minimum_nights=nights or 1,
            effective_from=p.get('valid_from'),effective_to=p.get('valid_until'),event_card_id=None,runnable=runnable,adapter='catalog_room',
            not_runnable_reason=reason,summary=summary,details=text+' · 기존 등록 가격을 사용한 가상 비교이며 날짜별 예약 확정가가 아닙니다.',
            sku_id=p['sku_id'],catalog_policy=H.POLICY,catalog_sha256=H.SHA,
            room_price_krw=p['unit_price_krw'],billing_unit=p['billing_unit'],price_status=p['price_status'],price_tier=p['price_tier'],
            price_is_starting_rate=p.get('price_is_starting_rate',False),actual_date_quote=False,source_unit=unit,
            source_room_types=p.get('source_room_types'),source_day_rule=p.get('source_day_rule',''),allowed_dates=dates_ok,
            validity_status='DATED_SOURCE_PERIOD' if p.get('valid_from') and p.get('valid_until') else 'SOURCE_DATE_RANGE_UNSPECIFIED_REFERENCE_ONLY',
            eligibility_dates_basis='EXISTING_HC_DAY_OK_2025_2026_NOT_CONFIRMED_SALE_AVAILABILITY',
            required_party_size=people,reference_people=reference_people,party_qualification=dict(douglas_age_rule=p.get('douglas_age_rule',False),source_unit=unit),
            included_description=text,breakfast_contract='SOURCE_ADULT_TWO_BUFFET' if direct_breakfast else 'DOUGLAS_FACILITY_LIGHT_BREAKFAST' if room_only and p['venue_id']=='DOUGLAS' else 'ROOM_ONLY_NO_AUTOMATIC_BUFFET' if room_only else 'REQUIRES_CONTRACT_REVIEW',
            benefit_scope='ROOM_AND_BUFFET_BREAKFAST_ONLY_GIFT_DESCRIPTION_NOT_EXECUTED' if direct_breakfast else 'ROOM_AND_INTRINSIC_FACILITY_RIGHTS' if room_only else 'PARTIAL_EXISTING_RUNTIME_NOT_FULLY_VERIFIED',
            source=copy.deepcopy(p.get('official_source') or dict(file=p['source_path'],sha256=p['source_sha256'])),
            request_fields=dict(catalog_policy=H.POLICY,catalog_options={'room_products':{'<customer_id>':p['sku_id']}},visit_conditions={'<customer_id>':{'building':p['venue_id']}})))
    return rows,aliases



def room_options():
    packages = []
    for p in PACKAGE_CATALOG.values():
        packages.append(dict(id=p['id'], label=p['label'], buildings=[p['building']],
                             nights=p['nights'], minimum_nights=p['nights'],
                             effective_from=p['effective_from'], effective_to=p['effective_to'],
                             event_card_id=None, runnable=True, adapter='package_id',
                             summary='객실 패키지 · 포함 혜택 적용', details=p['qualification'] + ' · ' + p['source']))
    for p in PACKAGES.values():
        packages.append(dict(id=p['package_id'], label=p['label'], buildings=list(p['buildings']),
                             nights=None, minimum_nights=p['nights'],
                             effective_from=p['stay_from'], effective_to=p['stay_to'],
                             event_card_id=SANTA_CARD if p['year'] == 2025 else 'SANTA_KIDS_VILLAGE_2026',
                             runnable=p['runnable'], adapter='event_entitlement', benefits=p.get('benefits'), price_krw=p['price_krw'], package_sessions=p.get('package_sessions'),
                             summary='산타 패키지 · 객실 1박·조식·행사 포함',
                             details=p.get('ambiguity') or p.get('not_runnable_reason', '')))
    catalog,aliases=catalog_room_options()
    packages.extend(copy.deepcopy(catalog))
    return dict(version='ROOM_OPTIONS_CATALOG_V2', packages=packages,catalog_room_count=len(catalog)+len(aliases),
                catalog_room_projected_count=len(catalog),catalog_room_runnable_count=sum(p['runnable'] for p in catalog),catalog_aliases=copy.deepcopy(aliases))
