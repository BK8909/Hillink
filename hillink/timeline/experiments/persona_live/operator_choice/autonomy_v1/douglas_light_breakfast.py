"""Official Douglas lounge right, isolated to breakfast policy V2.

No extra room rate or automatic extra-person sale is inferred. The meal's
30-minute duration / 0.5 light-food fraction retain the existing Douglas candidate assumptions.
"""
from . import breakfast_policy as BP
from ..operator_world_v1 import world as WD

SOURCE='https://www.walkerhill.com/grandwalkerhillseoul/douglas/Facility'
ID='DOUGLAS_LIGHT_BREAKFAST'
VENUE='DOUGLAS_LOUNGE'
LABEL='더글라스 라이트 조식 · 포함 혜택'


def entitled(a):
    return (BP.policy(getattr(a,'sc',{}))==BP.V2 and getattr(a,'B',None)=='DOUGLAS'
            and bool(getattr(a,'stay',False)) and bool(getattr(a,'checked_in',False))
            and not getattr(a,'checked_out',False))


def room_fields(vs,sc):
    if BP.policy(sc)!=BP.V2 or vs.get('building')!='DOUGLAS':return {}
    return dict(breakfast_included_in_room=True,breakfast_contract_people=2,
                breakfast_contract_kind=ID,breakfast_contract_venue=VENUE,
                breakfast_contract_window={'start':'07:00','end':'10:00'},
                breakfast_contract_source=SOURCE,breakfast_contract_additional_people='PRIOR_CONFIRMATION_REQUIRED_NOT_AUTO_CHARGED',
                room_rate_changed_for_breakfast=False)


def offer(a,t,travel_min=0):
    if not entitled(a):return None
    # The current engine chooses for the entire team; it cannot silently assign
    # an unconfirmed third guest or split the party into a different entitlement.
    available=a.N<=2 and max(t+travel_min,7*60)+30<=10*60
    status='OFFICIAL_INCLUDED_RIGHT' if available else ('ADDITIONAL_PERSON_ACCESS_REQUIRES_CONFIRMATION' if a.N>2 else 'LIGHT_BREAKFAST_SERVICE_CLOSED_OR_INSUFFICIENT_TIME')
    o=WD.offer(ID,LABEL,'restaurant',VENUE,window={'start':'07:00','end':'10:00'},duration=30,
               price=0,grade='◎',price_note='더글라스 투숙 객실당 2인 라운지 이용 포함 · '+SOURCE,
               in_package=True,meal_fraction=.5,courses=1,quality='standard',
               menu_tags=['bread'],available=available,status=status,
               note='공식: 라이트 조식·07~10·객실당2인. 모델 가정: 30분·기존 더글라스 후보의 0.5 끼니 충족도. 추가인원 사전확인 전 자동과금 없음')
    o['service_contract']=dict(venue_id=VENUE,service_window=o['window'],candidate_available_at=max(t,420),
        planning_viability='AVAILABLE_NOW' if available else 'UNAVAILABLE',source_state='OFF-DOUGLAS-FACILITY',
        reservation_state='NOT_REQUIRED_FOR_INCLUDED_LOUNGE_USE' if a.N<=2 else 'ADDITIONAL_PERSON_CONFIRMATION_REQUIRED',
        price_status='INCLUDED_NOT_NEW_REVENUE',blocked_reason=None if available else status,duration_status='SIMULATION_ASSUMPTION_30_MIN')
    o['douglas_light_breakfast_contract']=dict(sku_id=ID,venue_id=VENUE,label=LABEL,included_people=2,
        actual_party_size=a.N,source_path=SOURCE,service_window=o['window'],additional_person_confirmation_required=a.N>2)
    return o


def charge(a):
    if not entitled(a) or a.N>2:
        return dict(status='가격 미정',price_kind='unknown',krw=None,grade=None,
                    basis='더글라스 라운지 추가 인원 또는 출입 권리 확인 필요 · 자동과금 없음',auto_charge=False)
    return dict(status='포함',price_kind='known_included',krw=0,grade='◎',per='인',
        basis='더글라스 투숙 객실당 2인 라이트 조식 이용 권리 · '+SOURCE,
        facility_entitlement_id=ID,entitlement_scope='per_morning',included_people=2,actual_party_size=a.N,
        auto_charge=False,sku_contract=dict(sku_id=ID,label=LABEL,venue_id=VENUE,billing_unit='person',
        billing_quantity=a.N,unit_price_krw=0,source_path=SOURCE,price_status='OFFICIAL_FACILITY_INCLUDED_NOT_NEW_SALE'))
