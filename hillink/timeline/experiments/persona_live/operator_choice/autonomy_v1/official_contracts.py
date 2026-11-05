"""Source overlays and party cohorts. No preference or provider changes."""
import copy, hashlib, json
from pathlib import Path
PATH=Path(__file__).with_name('official_menu_overlay.json')
def load(base, base_sha):
    overlay=json.loads(PATH.read_text())
    if overlay['base_catalog_sha256']!=base_sha:raise ValueError('OFFICIAL_OVERLAY_BASE_MISMATCH')
    by={p['sku_id']:copy.deepcopy(p) for p in base['products']}
    for p in overlay['products']:by[p['sku_id']]=copy.deepcopy(p)
    out=copy.deepcopy(base);out['products']=list(by.values());out['official_overlay_version']=overlay['version']
    return out,hashlib.sha256((base_sha+hashlib.sha256(PATH.read_bytes()).hexdigest()).encode()).hexdigest()

def restrictions(p,a,t,period):
    why=[]
    last=p.get('last_order_minute',p.get('last_order_by_period',{}).get(period))
    if last is not None and t>last:why.append('SOURCE_LAST_ORDER_PASSED')
    if p.get('role')=='ROOM':
        if p.get('package_people') and p['package_people']!=a.N:why.append('PACKAGE_PARTY_OPTION_MISMATCH')
        if p.get('package_nights') and p['package_nights']!=a.vs.get('nights'):why.append('PACKAGE_NIGHTS_OPTION_MISMATCH')
        party=a.vs.get('party_composition')
        if p.get('douglas_age_rule') and (a.C.get('kids') and not party or party and any(c.get('age_months') is None or c['age_months']<156 or c.get('school_stage')!='secondary' for c in party['children'])):why.append('DOUGLAS_AGE_QUALIFICATION_UNCONFIRMED_OR_INELIGIBLE')
    return why

def child_parts(p,a,t,duration,period,H,party):
    """Assess each child, preserving unknown age. Never turn unknown into an adult fact."""
    venue=p['venue_id'];out=[]
    for child in party['children']:
        age=child.get('age_months');stage=child.get('school_stage')
        if venue not in ('THE_BUFFET','THEATRE_OF_LIGHT','RIVERPARK') and age is not None and age<36:
            continue  # Scenario: shared food, no independent adult main. Explicit orders may differ.
        if venue=='THE_BUFFET' and age is not None and age<36:
            free=copy.deepcopy(p);free.update(sku_id=p['sku_id']+'-INFANT',label='더뷔페 · 36개월 미만 유아',unit_price_krw=0,price_status='USER_CONFIRMED_INFANT_FREE',age_band='INFANT_UNDER_36_MONTHS',price_tier='EXISTING_REFERENCE')
            c=H.component(free,1,a,assumption='EXPLICIT_VIRTUAL_INFANT_AGE');c['party_cohort']='INFANT'
        else:
            candidates=[]
            for x in H.DATA['products']:
                if x['venue_id']!=venue or x['role']!='CHILD_COMPONENT' or not H.day_ok(x,a.sc['date']):continue
                if venue=='THE_BUFFET' and x['label'].split(' · ')[0]!=p['label'].split(' · ')[0]:continue
                valid=age is not None and age>=36 and stage in ('preschool','elementary')
                if '미취학' in x['source_unit']:valid=valid and stage=='preschool'
                if venue=='THEATRE_OF_LIGHT':valid=age is not None and (age<48 if x['unit_price_krw']==0 else 48<=age<156 if '어린이' in x['label'] else 156<=age<228)
                if valid and not H.eligible(x,a,t,duration,period,True):candidates.append(x)
            if len(candidates)==1:
                c=H.component(candidates[0],1,a,assumption='EXPLICIT_VIRTUAL_CHILD_AGE_AND_STAGE');c['party_cohort']='CHILD'
            elif age is not None and age>=156 and stage=='secondary':
                c=H.component(p,1,a,assumption='EXPLICIT_SECONDARY_AGE_ADULT_TARIFF');c['party_cohort']='ADULT_TARIFF_SECONDARY'
            else:
                proxy=copy.deepcopy(p);proxy.update(sku_id=p['sku_id']+'-UNKNOWN-CHILD-MODEL',pricing_parent_sku_id=p['sku_id'],label=p['label']+' · 연령 미확정 동행 요금 가정',price_tier='SIMULATION_ASSUMPTION',price_status='UNKNOWN_CHILD_AGE_ADULT_RATE_PROXY_NOT_A_VERIFIED_CHILD_FARE')
                c=H.component(proxy,1,a,assumption='UNKNOWN_CHILD_FARE_PROXY; NO_AGE_INVENTED');c['party_cohort']='UNKNOWN_CHILD_FARE'
                if age is not None:
                    c.update(sku_id=p['sku_id']+'-CHILD-MENU-MODEL',label=p['label']+' · 어린이 별도 메뉴·요금 미확인',price_status='KNOWN_AGE_CHILD_MENU_UNAVAILABLE_ADULT_PORTION_MODEL',party_cohort='CHILD_MENU_MODEL',order_quantity_basis='EXPLICIT_AGE_PRESERVED; ADULT_MENU_PORTION_ASSUMPTION')
        c['age_input']=copy.deepcopy(child)
        # Same tariff can share a row; different ages/cohorts remain traceable.
        same=next((z for z in out if z['sku_id']==c['sku_id'] and z['party_cohort']==c['party_cohort']),None)
        if same:same['billing_quantity']+=1;same['age_inputs'].append(c.pop('age_input'))
        else:c['age_inputs']=[c.pop('age_input')];out.append(c)
    return out


def skyard_included(a, room):
    """A club flag is not proof of a qualifying room; Club Deluxe is excluded."""
    if not (a.stay and a.checked_in and not a.checked_out):return False
    if a.B=='VISTA':return True
    if a.B!='GRAND':return False
    text=room.get('source_room_types','')+' '+room.get('label','')
    if '클럽 딜럭스' in text:return False
    # Mixed room options remain unconfirmed; never infer a selected subtype.
    if '+' in room.get('source_room_types',''):return False
    return '클럽 스위트' in text or ('SKYARD' in room.get('included_description','') and bool(room))

def pool_extra_product(p,a,cohort):
    """Preserve Grand adult reference; other buildings/ages remain explicit models."""
    x=copy.deepcopy(p)
    if a.B=='VISTA':
        x.update(sku_id=p['sku_id']+'-VISTA-MODEL',pricing_parent_sku_id=p['sku_id'],label='비스타 수영장 초과 인원 · 가상 요금',unit_price_krw=20000,price_tier='SIMULATION_ASSUMPTION',source_grade='△',price_status='VISTA_EXTRA_FEE_UNVERIFIED_NOT_GRAND_FAQ',source_document='Existing 20,000 scenario retained; Grand FAQ does not establish Vista tariff')
        x['source_resolution']=dict(status='VISTA_EXTRA_FEE_UNVERIFIED',note='비스타 추가 인원 20,000원 가정 · 그랜드 공식 FAQ 요금과 별개')
    elif cohort!='ADULT':
        x.update(sku_id=p['sku_id']+'-CHILD-MODEL',pricing_parent_sku_id=p['sku_id'],label='그랜드 수영장 연령·어린이 요금 미확정',price_tier='SIMULATION_ASSUMPTION',source_grade='△',price_status='CHILD_FARE_UNVERIFIED_ADULT_REFERENCE_PROXY')
        x['source_resolution']['note']+=' 이번 행은 어린이·연령 미확정 인원의 성인 단가 참고 가정이며 성인으로 확정하지 않음.'
    x['party_cohort']=cohort;x['service_date']=a.sc['date'];x['date_specific_tariff_confirmed']=False
    return x


def room_reference(p, *, service_date, people, nights, selected):
    """Starting-rate provenance; never a dated quote or implicit package sale."""
    inside=bool((not p.get('valid_from') or service_date>=p['valid_from']) and (not p.get('valid_until') or service_date<=p['valid_until']))
    return dict(reference_sku_id=p['sku_id'],reference_name=p['label'],
        source=copy.deepcopy(p.get('official_source') or dict(file=p['source_path'],sha256=p['source_sha256'])),
        starting_price_krw=p['unit_price_krw'],starting_price_unit=p['billing_unit'],
        reference_people=p.get('package_people'),reference_nights=p.get('package_nights'),
        reference_room_types=p.get('source_room_types'),valid_from=p.get('valid_from'),valid_until=p.get('valid_until'),
        service_date=service_date,within_source_period=inside,scenario_people=people,scenario_nights=nights,
        selected_source_package=selected,actual_date_quote=False,
        benefits_assigned_from_reference=False if not selected else 'SELECTED_PACKAGE_ENTITLEMENT_CONTRACT',
        status='OFFICIAL_STARTING_RATE_SCENARIO_NOT_RESERVATION_QUOTE' if selected and inside else 'REFERENCE_STARTING_RATE_FOR_DIFFERENT_DATE_OR_ROOM_CONFIGURATION',
        note='공식 시작가를 사용한 가상 요금 · 날짜별 예약 확정가 아님. '+('선택 패키지의 인원·박수·자격 조건을 별도 검사합니다.' if selected else '참고 패키지와 동일 객실·인원 구성이 아니며 참고 패키지 혜택을 자동 부여하지 않습니다.'))


def reviewed_additions(base, base_sha):
    path=Path(__file__).with_name('reviewed_menu_20261104.json')
    overlay=json.loads(path.read_text());out=copy.deepcopy(base)
    existing={x['sku_id'] for x in base['products']}
    if any(x['sku_id'] in existing for x in overlay['products']):raise ValueError('REVIEWED_ADDITION_MUST_NOT_REPLACE_EXISTING_SKU')
    out['products']+=copy.deepcopy(overlay['products']);out['reviewed_additions_version']=overlay['version']
    return out,hashlib.sha256((base_sha+hashlib.sha256(path.read_bytes()).hexdigest()).encode()).hexdigest()


def reviewed_conditions(base, base_sha):
    """Reviewed sale restrictions, separate from immutable source/catalog inputs."""
    path=Path(__file__).with_name('reviewed_conditions_20261104.json')
    overlay=json.loads(path.read_text());out=copy.deepcopy(base)
    by={p['sku_id']:p for p in out['products']}
    for row in overlay['conditions']:
        p=by[row['sku_id']]
        if p['unit_price_krw']!=row['expected_unit_price_krw']:
            raise ValueError('REVIEWED_CONDITION_PRICE_MISMATCH')
        p['discount_policy']=row['discount_policy']
        p['reviewed_sale_condition_source']=copy.deepcopy(row['source'])
    out['reviewed_conditions_version']=overlay['version']
    return out,hashlib.sha256((base_sha+hashlib.sha256(path.read_bytes()).hexdigest()).encode()).hexdigest()
