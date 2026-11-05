"""Price executed room nights without changing behavioral inputs or cash claims."""
import hashlib,importlib.util
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
P=Path(__file__).resolve().parents[1]/'prices.py'
SOURCE_SHA256=hashlib.sha256(P.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('hillink_reference_prices',P);prices=importlib.util.module_from_spec(spec);spec.loader.exec_module(prices)

def build(flow,ledger):
    package=flow['visit'].get('package_context') or {}
    rows=[]
    for pid,receipt in ledger['receipts'].items():
        nights=[r for r in receipt['rows'] if r['act']=='room_night']
        # Only a trusted server catalog total can outrank the model rate.
        total=package.get('verified_total_krw')
        verified=(type(total) is int and total>0 and package.get('price_status')=='VERIFIED_TOTAL' and bool(package.get('price_source')))
        for r in receipt['rows']:
            room=r['act']=='room_night';v=flow['visits'][pid]
            item=dict(row_id=r['row_id'],visit_id=flow['visit_id'],customer_id=pid,date=r['visit_date'],
                department=r['department'],venue=r['venue'],product=r['product'],action_id=r['act'],
                original_scene_index=r.get('scene_index'),visit_day=r['visit_day'],quantity=r['quantity'],
                virtual_gross_krw=r['paid_krw'] if r['status']!='금액 미확인' else None,
                price_status='EXISTING_SIMULATED_CHARGE_OR_INCLUDED',net_ex_vat_krw=None,tax_status='UNKNOWN')
            if room and r.get("room_pricing"):
                item.update(r["room_pricing"])
            elif room:
                rate=prices.PRICE.get('room:'+str(v['building']))
                item.update(venue=prices.ROOM_L3.get(v['building'],v['building']),building=v['building'],room_count=1,
                    occupancy_basis='ONE_ROOM_PER_TEAM_SCENARIO_ASSUMPTION_NOT_PARTY_SIZE',quantity=1,billing_unit='room_night',
                    product='객실 1박 · GitHub 패키지 시작가 모델',price_status='MODEL_STARTING_RATE_NOT_CURRENT_SALE',
                    price_source='timeline/prices.py:room:'+str(v['building']),source_sha256=SOURCE_SHA256,
                    source_note=rate['src'] if rate else 'UNKNOWN_BUILDING',unit_price_krw=rate['krw'] if rate else None,
                    virtual_gross_krw=rate['krw'] if rate else None,tax_status='MODEL_VAT_INCLUDED_10_PERCENT',
                    package_id=package.get('id'),package_price_status='VERIFIED_TOTAL' if verified else 'TOTAL_UNAVAILABLE_FALLBACK_MODEL' if package else 'NO_SELECTED_PACKAGE')
                if verified:
                    # Allocate one total exactly once across the existing night
                    # rows; retain every physical night and its inverse link.
                    i=nights.index(r);n=len(nights);q,rem=divmod(total,n)
                    item.update(virtual_gross_krw=q+(i<rem),unit_price_krw=None,product=package['label'],
                        price_status='VERIFIED_PACKAGE_TOTAL_ALLOCATION',price_source=package['price_source'],
                        tax_status=package.get('tax_status','UNKNOWN'),package_total_krw=total,
                        allocation='INTEGER_REMAINDER_BY_CHRONOLOGICAL_NIGHT')
                if item['virtual_gross_krw'] is not None and item['tax_status'] in ('MODEL_VAT_INCLUDED_10_PERCENT','VAT_INCLUDED_10_PERCENT'):
                    item['net_ex_vat_krw']=float((Decimal(item['virtual_gross_krw'])/Decimal('1.1')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
            rows.append(item)
    def aggregate(items):
        known=[r for r in items if r['virtual_gross_krw'] is not None]
        return dict(virtual_gross_krw=sum(r['virtual_gross_krw'] for r in known),unknown_count=len(items)-len(known),
            net_ex_vat_krw=round(sum(r['net_ex_vat_krw'] or 0 for r in items),2) if all(r['net_ex_vat_krw'] is not None for r in items) else None,
            known_net_ex_vat_krw=round(sum(r['net_ex_vat_krw'] or 0 for r in items),2),row_ids=[r['row_id'] for r in items])
    levels={}
    for level,keys in [('L4',('department','venue','product')),('L3',('department','venue')),('L2',('department',))]:
        groups={}
        for row in rows:groups.setdefault(tuple(row[k] for k in keys),[]).append(row)
        levels[level]=[dict(key=list(k),**aggregate(v)) for k,v in sorted(groups.items())]
    levels['L1']=aggregate(rows)
    rooms=[r for r in rows if r['action_id'] in ('room_night','room_addon')];nonroom=[r for r in rows if r['action_id'] not in ('room_night','room_addon')]
    assert len({r['row_id'] for r in rows})==len(rows)
    return dict(version='virtual-room-revenue-v1',visit_id=flow['visit_id'],ledger_run_id=ledger['run_id'],
        basis='SAME_L5_ROW_IDS_REVALUED; DO_NOT_ADD_LEGACY_ASSUMPTIONS',rows=rows,levels=levels,
        room=aggregate(rooms),nonroom=aggregate(nonroom),
        historical_menu_room_assumption_krw=ledger.get('visit',{}).get('historical_menu_room_assumption_krw',ledger['totals']['assumption_addition_krw']),
        actual_cash_observed=False,all_in_expected_total_krw=levels['L1']['virtual_gross_krw'] if not levels['L1']['unknown_count'] else None)

NATIVE_VERSION = 'native-room-l5-v4'   # v4: virtual room model rate on every date (labelled as a model rate, not that date's sale price), explicit Santa package night, operator room-rate input
MODEL_RATE_YEAR = '2026-'
ROOM_BUILDINGS = ('GRAND','VISTA','DOUGLAS')
UNKNOWN_NOTE = '객실료 금액 미확인 · 합계에서 제외'
MODEL_NOTE_OTHER_YEAR = '가상 객실 모델 단가 · 2026 모델 단가를 시나리오 기준가로 사용 · 해당 날짜의 확정 판매가 아님'

def operator_rate(flow, building):
    """Explicit per-night virtual room rate the operator declared for this run (never inferred)."""
    rates = ((flow.get('visit') or {}).get('virtual_room_rates') or {}).get('rates') or {}
    amount = rates.get(building)
    return amount if type(amount) is int and amount > 0 else None

def operator_fields(flow, building):
    amount = operator_rate(flow, building)
    return dict(virtual_gross_krw=amount, unit_price_krw=amount, product='객실 1박 · 운영자 입력 가상 객실료',
                price_status='OPERATOR_VIRTUAL_ROOM_RATE_INPUT', price_source='request.virtual_room_rates.'+building,
                tax_status='UNKNOWN', source_note='운영자가 이번 실행에 명시한 가상 객실료 · 실제 판매가 아님')

def breakfast_room_fields(flow, pid, building):
    """Breakfast-included room (11/03 breakfast contract V1): TYPE 2 starting price of the same package family; the
    contracted adults' breakfast is then 0 in F&B, so the benefit is counted once (in the room night)."""
    import sys
    from operator_choice.autonomy_v1 import breakfast_policy as BP
    v = flow['visits'][pid]
    sc = {'breakfast_policy': (flow.get('visit') or {}).get('breakfast_policy')}
    if BP.policy(sc) not in BP.CONTRACT_POLICIES or BP.plan(v, sc) != 'breakfast_included':
        return None
    rate = BP.INCLUDED_ROOM_RATE.get(building)
    if not rate:
        return None
    amount, src = rate
    return dict(virtual_gross_krw=amount, unit_price_krw=amount, product='객실 1박 · 조식 포함 가상 모델 단가(성인 2인 조식)',
                price_status='VIRTUAL_MODEL_UNIT_PRICE_BREAKFAST_INCLUDED', price_source='operator_choice/autonomy_v1/breakfast_policy.py:INCLUDED_ROOM_RATE.'+building,
                source_note=src+' · 실제 판매가 아님 · 조식 혜택은 객실 금액에만 반영(식음 원장 0원)', tax_status='MODEL_VAT_INCLUDED_10_PERCENT',
                breakfast_included_in_room=True, breakfast_contract_adults=BP.CONTRACT_ADULTS,
                model_rate_outside_model_year=not service_year_is_model(flow))

def service_year_is_model(flow):
    return str((flow.get('visit') or {}).get('start_date') or '').startswith(MODEL_RATE_YEAR)

def native_price(flow, pid, service_date, night_index, night_count):
    """Trusted visit/catalog inputs only; party size never becomes room quantity."""
    if flow['visit'].get('catalog_policy')=='C01_HOTEL_CATALOG_V1':
        import hotel_ledger
        result = hotel_ledger.room_price(flow,pid,service_date,night_index,night_count,prices.PRICE,SOURCE_SHA256)
        from operator_choice.autonomy_v1 import douglas_light_breakfast as DLB
        result.update(DLB.room_fields(flow['visits'][pid],{'breakfast_policy':flow['visit'].get('breakfast_policy')}))
        return result
    v = flow['visits'][pid]
    package = flow['visit'].get('package_context') or {}
    building = v.get('building')
    stay_id = hashlib.sha256(f"{flow['visit_id']}|{pid}".encode()).hexdigest()[:24]
    result = dict(version=NATIVE_VERSION, stay_id=stay_id, room_id=stay_id+':1', room_count=1,
                  room_count_basis='ONE_ROOM_PER_TEAM_SCENARIO_ASSUMPTION', billing_unit='room_night',
                  package_id=package.get('id'), building=building, service_date=service_date,
                  participant_count=v.get('party_size'), unpriced_extras=['additional_people'] if v.get('party_size',1)>2 else [],
                  room_type_basis='BUILDING_BASE_MODEL_NOT_VERIFIED_ROOM_CATEGORY', included_benefits_repriced=False,
                  virtual_gross_krw=None, unit_price_krw=None, net_ex_vat_krw=None,
                  price_status='UNKNOWN_ROOM_PRICE', tax_status='UNKNOWN', actual_cash_observed=False,
                  price_source=None, product='객실 1박 · 요금 미확인', source_sha256=SOURCE_SHA256, source_note=UNKNOWN_NOTE)
    # Project model rates have no authority outside the approved 2026 scenario.
    eligible = service_date.startswith(MODEL_RATE_YEAR) and building in prices.ROOM_L3
    if package:
        eligible = eligible and package.get('building') == building and package.get('nights') == night_count
        eligible = eligible and package.get('effective_from','9999') <= service_date <= package.get('effective_to','0000')
    total = package.get('verified_total_krw')
    party_ok = not package or v.get('party_size', 1) <= package.get('party_size', 0)
    import santa_packages as SPK
    santa = SPK.room_night(flow, pid, service_date, night_index)
    if santa:
        result.update(santa)
    elif eligible and party_ok and type(total) is int and total > 0 and package.get('price_status') == 'VERIFIED_TOTAL' and package.get('price_source'):
        q, rem = divmod(total, night_count)
        result.update(virtual_gross_krw=q+(night_index<rem), product=package['label'],
                      price_status='VERIFIED_PACKAGE_TOTAL_ALLOCATION', price_source=package['price_source'],
                      tax_status=package.get('tax_status','UNKNOWN'), package_total_krw=total,
                      allocation='INTEGER_REMAINDER_BY_CHRONOLOGICAL_NIGHT')
    elif eligible and party_ok and type(package.get('verified_room_nightly_krw')) is int and package['verified_room_nightly_krw'] > 0 and package.get('price_status') == 'VERIFIED_ROOM_NIGHTLY' and package.get('price_source'):
        amount=package['verified_room_nightly_krw']
        result.update(virtual_gross_krw=amount, unit_price_krw=amount, product='객실 1박 · 확인된 객실 요금',
                      price_status='VERIFIED_ROOM_NIGHTLY', price_source=package['price_source'], tax_status=package.get('tax_status','UNKNOWN'))
    elif operator_rate(flow, building) is not None:
        result.update(operator_fields(flow, building))
    elif breakfast_room_fields(flow, pid, building):
        result.update(breakfast_room_fields(flow, pid, building))
    elif building in prices.ROOM_L3:
        rate=prices.PRICE.get('room:'+str(building))
        if rate:
            other_year = not service_date.startswith(MODEL_RATE_YEAR)
            result.update(virtual_gross_krw=rate['krw'],unit_price_krw=rate['krw'],
                          product='객실 1박 · 가상 객실 모델 단가' if other_year else '객실 1박 · 2026 가상 모델 단가',price_status='VIRTUAL_MODEL_UNIT_PRICE',
                          model_rate_outside_model_year=other_year,
                          price_source='timeline/prices.py:room:'+building,source_note=rate['src'],
                          tax_status='MODEL_VAT_INCLUDED_10_PERCENT',
                          package_price_status='TOTAL_UNAVAILABLE_MODEL_FALLBACK' if package else 'NO_SELECTED_PACKAGE')
            if other_year: result['source_note']=MODEL_NOTE_OTHER_YEAR
            result['breakfast_included_in_room']=False   # TYPE 1 starting price = room only (breakfast is a separate choice under V1)
    if result['price_status']=='VIRTUAL_MODEL_UNIT_PRICE':
        from hotel_ledger import H
        ref=H.OC.room_reference(H.BY[{'GRAND':'HC-MENU-002','VISTA':'HC-MENU-022','DOUGLAS':'HC-MENU-018'}[building]],service_date=service_date,people=v.get('party_size'),nights=night_count,selected=False)
        result.update(price_reference_contract=ref,source_note=(MODEL_NOTE_OTHER_YEAR+' · ' if result.get('model_rate_outside_model_year') else '')+ref['note'])
    amount=result['virtual_gross_krw']
    if amount is not None and result['tax_status'] in ('VAT_INCLUDED_10_PERCENT','MODEL_VAT_INCLUDED_10_PERCENT'):
        result['net_ex_vat_krw']=float((Decimal(amount)/Decimal('1.1')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    from operator_choice.autonomy_v1 import douglas_light_breakfast as DLB
    result.update(DLB.room_fields(v,{'breakfast_policy':flow['visit'].get('breakfast_policy')}))
    return result


def apply_native(raw, pricing):
    """Price the existing room-night row once before the normal L5 aggregation."""
    amount=pricing['virtual_gross_krw']
    if pricing.get('room_order_contract'):
        raw['선택 SKU 계약']=pricing['room_order_contract']
        raw['_c01_structured_order_quantity']=True
    elif pricing.get('selected_room_sku_id'):
        raw['선택 SKU 계약']=dict(sku_id=pricing['selected_room_sku_id'],label=pricing['product'],
            billing_unit='room_night',billing_quantity=1,unit_price_krw=amount,
            price_tier=pricing['price_tier'],price_status=pricing['price_status'],source_path=pricing['price_source'],
            source_sha256=pricing['source_sha256'],catalog_sha256=pricing.get('catalog_sha256'),quantity_observed=False)
        raw['_c01_structured_order_quantity']=True
    raw['_legacy_room_assumption_krw']=raw.get('가정 결제액',0)
    raw.update({'L2 부문':'ROOM','L3 업장':prices.ROOM_L3.get(pricing['building'],str(pricing['building'])),
                'L4 상품':pricing['product'],'상품 ID':pricing.get('selected_room_sku_id') or (pricing['package_id'] if str(pricing.get('package_id') or '').startswith('SANTA_PKG') else None) or 'ROOM_NIGHT_'+str(pricing['building']),
                '수량':1,'판매 수량':1,'판매 단위':'객실박','과금 단위':'객실박',
                '단가':pricing['unit_price_krw'] if pricing['unit_price_krw'] is not None else '',
                '확정 결제액':amount or 0,'결제액':amount or 0,'가정 결제액':amount or 0,
                '상태':'가상 결제' if amount is not None else '금액 미확인',
                '가격 근거':pricing['price_source'] or '객실 가격 미확인',
                '가격 등급':'산타 패키지 가상 기준가' if pricing.get('package_id','') and str(pricing.get('package_id')).startswith('SANTA_PKG') else '공식 시작가 참고 시나리오' if pricing.get('price_reference_contract') else '가상 모델 단가' if pricing['price_status']=='VIRTUAL_MODEL_UNIT_PRICE' else '운영자 입력 가상 단가' if pricing['price_status']=='OPERATOR_VIRTUAL_ROOM_RATE_INPUT' else '조식 포함 가상 모델 단가' if pricing['price_status']=='VIRTUAL_MODEL_UNIT_PRICE_BREAKFAST_INCLUDED' else '확인 단가' if amount is not None else '미확인',
                '확인 메모':'가상 실행 거래 · 실제 예약 확정액 아님 · '+pricing['price_status'],
                '순매출':pricing['net_ex_vat_krw'] if pricing['net_ex_vat_krw'] is not None else '',
                '순매출 상태':'가상 모델 VAT 10% 제외' if pricing['net_ex_vat_krw'] is not None else '세금 기준 미확인',
                '_room_pricing':pricing,'_net_ex_vat_krw':pricing['net_ex_vat_krw']})
