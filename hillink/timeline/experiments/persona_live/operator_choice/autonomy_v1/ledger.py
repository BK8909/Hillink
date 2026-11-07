"""CL-19 후속(P0) — 행동 이벤트 하나가 지나는 공통 장부: 출입 자격 · 끼니 상태 · 지출.
규칙 · LLM · 정량 엔진 어느 경로로 생긴 행동이든 Agent.add() 에서 이 모듈을 한 번 지난다.

- 출입: 검증기 `walkerhill_timeline_validator.FACILITY_ACCESS`(그랜드 · 비스타 · 더글라스 · 비투숙 칸)를 그대로 쓴다.
  '불가'는 후보에서 뺀다. '모름'은 막지도 열지도 않고, 가격은 '미정'으로 남긴다.
- 지출: `timeline/prices.py` 의 1인 정가(등급 ◎ ○ △)와 정량 엔진 상품 가격을 쓴다.
  가격을 모르면 0원으로 두지 않고 '가격 미정'으로 따로 센다. 산책 · 휴식처럼 살 것이 없는 행동은 '구매 없음'이다.
- 끼니: 시각으로 아침 · 점심 · 저녁 칸을 정하고 양(full · light · skip)을 기록한다. 가벼운 저녁도 저녁이다.
정량 엔진의 점수 · 가중치 · 상품 가격은 바꾸지 않는다(이 장부는 엔진 바깥의 집계).
"""
from __future__ import annotations
import sys
from pathlib import Path

TL = Path(__file__).resolve().parents[4]
try:
    sys.path.insert(0, str(TL))
    import walkerhill_timeline_validator as _V  # noqa: E402
    ACCESS = _V.FACILITY_ACCESS
    _E = _V.Entry
except Exception:   # 검증기를 못 읽으면 출입 검사 없이(기존 규칙만) — 결과에 표시
    ACCESS, _E = {}, None
try:
    import prices as _P  # noqa: E402
    PRICE = dict(_P.PRICE)   # 1인 정가 표(등급 ◎ ○ △) — 읽기만
except Exception:
    PRICE = {}

# 엔진 상품 · 계획기 장소 → 출입표 장소
ENGINE_PLACE = {"SKYARD": "SKYARD", "SKYARD_NIGHT": "SKYARD", "FOREST_WALK": "FOREST_PARK", "SAUNA": "WELLNESS_SAUNA"}   # 와인페어는 외부 손님도 표를 사는 행사 — 숲 일반 출입칸을 쓰지 않음
BLDG = {"GRAND": "grand", "VISTA": "vista", "DOUGLAS": "douglas"}


def guest_class(a):
    """출입표 칸: 투숙 중(체크인 뒤 · 퇴실 전)이면 건물, 아니면 비투숙."""
    if a.stay and a.checked_in and not a.checked_out:
        return BLDG.get(a.B, "non_guest")
    return "non_guest"


def access(a, place):
    """→ (entry 이름, 이유). entry: 무료 · 유료 · 자유 · 불가 · 모름 · None(표에 없음)."""
    fa = ACCESS.get(place)
    if not fa:
        return None, None
    e = getattr(fa, guest_class(a))
    who = {"grand": "그랜드 투숙", "vista": "비스타 투숙", "douglas": "더글라스 투숙", "non_guest": "비투숙(또는 퇴실 뒤)"}[guest_class(a)]
    return e.value, f"{who} → {place} 출입 '{e.value}'(검증기 출입표)"


# 행사 출입 — 시설 출입표(포레스트 파크 일반 이용 '비투숙 불가')와 별도로, 출처가 있는 행사만 명시적으로 연다.
# 표에 없는 행사는 열지 않는다(암묵적 예외 없음). 행사가 열리는 것은 운영자 개입(월드 레버)일 때뿐이며 기본 월드 · CL-11 잠금 조건과 무관.
EVENT_ACCESS = {   # 행사 출입표 — 칸 값은 입장 가능 여부(무료 · 유료). 실제 입장료는 EVENT_FEE(행사 · 연도 한정 장부 규칙)
    "WINE_FAIR": dict(non_guest="유료", grand="무료", vista="무료", douglas="무료",
                      source="2026 와인페어 — 보도자료(일반 성인 55,000원 · 행사 기간 워커힐 투숙객 무료 입장) · 그랜드 · 비스타 가을 패키지 안내(10/10~11 · 10/17~18 · 10/24~25 · 숲 일반 이용 제한 · 행사 무료 입장 · 음식 · 프로그램 별도) · 2부 15:30~20:00",
                      note="입장료는 EVENT_FEE 장부 규칙으로 처리 — 정량 엔진의 상품 가격(55,000원 전원)과 판단 점수는 동결 계약대로 그대로"),
}
EVENT_FEE = {   # CL-1024-21A — 2026 와인페어 입장권에 한정한 방문 조건별 요금(장부 변환). 정량 엔진 · 평가셋 · CL-11 기본 조건은 바꾸지 않음
    "WINE_FAIR": dict(year=2026, adult_krw=55000,
                      guest="known_free",
                      sources=["SK네트웍스 보도자료 2026 와인페어(일반 성인 55,000원 · 행사 기간 투숙객 무료 입장)",
                               "그랜드 워커힐 · 비스타 워커힐 2026 가을 패키지 안내(행사 무료 입장 · 음식 · 프로그램 별도 구매)"],
                      extras="음식 · 유료 프로그램은 현장 별도 구매 — 가격 미정(unknown) · 입장료에 넣지 않음"),
}


def event_fee(a, offer):
    """행사 입장권 장부 — 투숙 중(known_free) · 비투숙 성인 정가 · 퇴실 뒤(투숙객 무료 적용 미확인 → unknown)."""
    f = EVENT_FEE[offer["id"]]
    src = " · ".join(f["sources"])
    ext = dict(extras=f["extras"], fee_rule=f"{f['year']} {offer['id']} 방문 조건 요금", engine_price_krw=offer.get("price_pp_krw"))
    if guest_class(a) != "non_guest":
        return dict(status="무료", price_kind="known_free", krw=0, grade="◎", basis=f"투숙객 무료 입장 — {src}", per="인", **ext)
    if a.stay and a.checked_out:
        return dict(status="가격 미정", price_kind="unknown", krw=None, grade=None, basis="퇴실 뒤 입장 — '행사 기간 투숙객 무료'가 퇴실 당일에도 적용되는지 미확인", **ext)
    kids = bool((getattr(a, "vs", None) or {}).get("kids"))
    return dict(status="유료", price_kind="known_paid", krw=f["adult_krw"] * a.N, grade="◎", per="인",
                basis=f"비투숙 성인 {f['adult_krw']:,}원 × {a.N}인 — {src}" + (" · 아동 요금 미확인(성인 요금으로 계산)" if kids else ""), **ext)


def event_blocked(a, event_id):
    """행사 출입 — 표에 없거나 이 고객 칸이 '불가'면 이유 문자열, 열리면 None."""
    ea = EVENT_ACCESS.get(event_id)
    if not ea:
        return f"{event_id}: 행사 출입 근거 없음(행사 출입표에 없음) — 열지 않음"
    e = ea.get(guest_class(a))
    return None if e in ("무료", "유료", "자유") else f"{event_id}: {guest_class(a)} 출입 '{e}'"


def blocked(a, place):
    e, why = access(a, place)
    return why if e == "불가" else None


# 계획기 활동 · 엔진 상품 → (가격표 키, 단위). None = 구매 없음
PLAN_PRICE = {
    "lunch_pizzahill": ("pizza", "인", "피자힐 커플 세트 ÷ 2(시간대 구분 없는 메뉴 가격 가정)"),
    "lunch_myongwol": (53000, "인", "명월관 점심 한정 불고기 53,000(prices.py 출처 문장 · ◎)"),
    "lunch_geumryong": ("geum", "인", "금룡 요일 제한 없는 가장 싼 코스(점심 · 저녁)"),
    "lunch_moegi": (140000, "인", "모에기 점심 정식 140,000~(prices.py 출처 문장 · ◎)"),
    "lunch_ondal": (None, "인", "온달 점심 낮것상은 주중 한정 — 토요일 점심 가격 미확인"),
    "lunch_bakery": ("lepassage", "인", "르 파사쥬(베이커리 가격표 미공개 · 후기 전언)"),
    "bakery": ("lepassage", "인", "르 파사쥬(베이커리 가격표 미공개 · 후기 전언)"),
    "lunch_cafe": ("pavilion", "인", "더 파빌리온 가을 디저트 1인"),
    "cafe": ("pavilion", "인", "더 파빌리온 가을 디저트 1인"),
    "lunch_room": (43000, "인", "공식 IRD 클럽 샌드위치 기준(○)"),
    "lunch_outside": (None, "인", "호텔 밖 식사 — 호텔 지출 아님 · 가격 미상"),
    "theatre": ("theatre", "인", "빛의 시어터 성인"),
    "sauna": ("sauna", "인", "그랜드 피트니스 사우나 1명"),
    "luxbar": ("lux", "인", "럭스바 칵테일 1잔"),
    "tennez": (None, "인", "테네즈 파크 투숙객 유료 — 가격 미확인"),
    "lounge": (0, "인", "클럽 객실 요금에 포함"),
    "pool": (0, "인", "투숙객 무료"), "fitness": (0, "인", "투숙객 무료"), "library": (0, "인", "투숙객 전용 무료"),
    "forest_walk": (0, "인", "투숙객 무료"),
}
NO_PURCHASE = {"wake", "sleep", "arrive", "leave", "checkin", "checkout", "pack", "unpack", "idle", "wait", "move", "room_rest", "room_bath", "room_nap",
               "ROOM_REST", "garden_walk", "night_walk", "lunch_skip", "SKIP_BREAKFAST"}
FOOTBATH = {"footbath", "night_footbath", "SKYARD", "SKYARD_NIGHT"}


def _price_of(key):
    if isinstance(key, int):
        return key, "◎"
    v = PRICE.get(key) if key else None
    if not v:
        return None, None
    return v.get("krw"), v.get("grade")


def charge(a, code, kind, loc, offer=None, in_package=False):
    # External delivery is not a hotel sale: hotel revenue 0, the guest's outside spend amount is unknown.
    if (offer or {}).get("id") == "EXTERNAL_DELIVERY" or str(code) == "EXTERNAL_DELIVERY":
        return dict(status="구매 없음", krw=0, grade=None, basis="외부 배달 · 호텔 매출 아님 · 고객 외부 지출 금액 미상(시뮬레이션 가정)",
                    external_spend=dict(amount_krw=None, status="EXTERNAL_AMOUNT_UNKNOWN", hotel_revenue_krw=0))
    # A selected package's sauna entitlement is settled by the package rule below (included once, then
    # charged), not re-sold by the catalog order that replaced the engine offer.
    if (offer or {}).get("hc_contract") and (offer.get("venue") == "SAUNA" or str(code).split(":")[0].lower() == "sauna") and not offer.get("hc_included"):
        rules = (getattr(a, "vs", {}).get("package_context") or {}).get("benefits") or {}
        bid = next((b for b, r in rules.items() if r.get("facility") == "SAUNA"), None)
        if bid and not any(p.get('sauna_policy') for p in (offer.get('sku_contract') or {}).get('components',[])):
            plain = {k: v for k, v in offer.items() if k not in ("hc_contract", "sku_contract")}
            out = charge(a, "sauna", kind, loc, dict(plain, package_entitlement_id=bid), in_package)
            if out.get("entitlement_id") == bid:
                return out
    if (offer or {}).get("id") == "DOUGLAS_LIGHT_BREAKFAST":
        from . import douglas_light_breakfast as DLB
        return DLB.charge(a)
    # Structured orders are fixed before this common ledger boundary.
    if (offer or {}).get("hc_contract"):
        from . import hotel_catalog as H
        key = offer["sku_contract"].get("hotel_entitlement_key")
        if key:
            a.visit_history.setdefault("hotel_entitlement_usage", {})[key] = 1
        out=H.charge(offer["sku_contract"], included=bool(in_package or offer.get("hc_included")))
        pkg=(getattr(a,'vs',{}) or {}).get('package_context') or {}
        if pkg.get('id')=='GRAND_SUNGSU_V2_2N' and key=='HC_ROOM_SAUNA_ONCE':
            out.update(entitlement_id='GRAND_SUNGSU_SAUNA',entitlement_scope='per_visit',included_people=2,entitlement_consumed=True)
        return out
    """→ dict(status, krw, grade, basis). status: 구매 없음 · 무료 · 포함 · 유료 · 가격 미정"""
    base = str(code).split(":")[0]
    package = getattr(a, "vs", {}).get("package_context") or {}
    rules = package.get("benefits") or {}
    usage = ((getattr(a, "visit_history", {}).get("benefit_usage") or {}).get("package_entitlements") or {})
    package_benefit = next(((bid, rule) for bid, rule in rules.items()
                            if rule.get("facility") == "SAUNA" and base.lower() == "sauna"), None)
    if package_benefit:
        benefit_id, rule = package_benefit
        remaining = (usage.get(benefit_id) or {}).get("remaining", rule.get("limit", 0))
        if remaining > 0 and (in_package or (offer or {}).get("package_entitlement_id") == benefit_id or offer is None):
            if a.N > rule["included_people"]:
                return dict(status="가격 미정", krw=None, grade=None,
                            basis=f"패키지 포함 {rule['included_people']}인 · 방문 {a.N}인 · 초과 인원 과금 조건 미확인",
                            per="체류당", entitlement_id=benefit_id, entitlement_scope=rule["scope"],
                            included_people=rule["included_people"], actual_party_size=a.N,
                            unpriced_extra_people=a.N-rule["included_people"], entitlement_consumed=True, auto_charge=False)
            return dict(status="포함", krw=0, grade=(offer or {}).get("price_source", {}).get("grade", "◎"),
                        basis=f"선택 시나리오 패키지 혜택 · {rule['scope']} {rule['limit']}회 · {rule['included_people']}인",
                        per="체류당", entitlement_id=benefit_id, entitlement_scope=rule["scope"],
                        included_people=rule["included_people"], auto_charge=False)
        if remaining <= 0:
            return dict(status="가격 미정", krw=None, grade=None,
                        basis="패키지 포함 횟수 사용 완료 · 추가 이용 과금 조건 미확인",
                        per="체류당", entitlement_id=benefit_id, entitlement_scope=rule["scope"], auto_charge=False)
    if str(code).endswith(":check") or str(code).endswith(":full"):
        return dict(status="구매 없음", krw=0, grade=None, basis="안내 확인 · 이용 포기")
    if base.lower() == "sauna" and getattr(a, "B", None) == "VISTA" and not in_package:
        return dict(status="가격 미정", krw=None, grade=None, basis="비스타 웰니스 사우나 — 현재 공식 요금 미확인(숨김 HTML 주석 금액 미사용) · 0원 아님")
    if base in NO_PURCHASE:
        return dict(status="구매 없음", krw=0, grade=None, basis="살 것이 없는 행동")
    if base in FOOTBATH:
        e, why = access(a, "SKYARD")
        if e == "무료":
            return dict(status="무료", krw=0, grade="△", basis=why + " · prices.py skyard")
        if e == "유료":
            return dict(status="유료", krw=19000, grade="△", basis=why + " · 객실당 19,000(후기가 옮긴 게시 안내)", per="객실")
        return dict(status="가격 미정", krw=None, grade=None, basis=why or "출입표 없음")
    if offer is not None and offer.get("id") in EVENT_FEE:   # 행사 입장권 — 방문 조건별 장부 규칙(엔진 가격은 internal 에 그대로)
        return event_fee(a, offer)
    if offer is not None:   # 정량 엔진 상품 — 엔진이 쓴 가격 그대로(엔진 계약)
        if in_package and offer.get("package_entitlement_id"):
            return dict(status="포함", krw=0, grade=offer.get("price_source", {}).get("grade"),
                        basis="선택 시나리오 패키지 혜택", entitlement_id=offer["package_entitlement_id"],
                        entitlement_scope="per_visit", included_people=offer.get("package_included_people"), auto_charge=False)
        if in_package:
            return dict(status="포함", krw=0, grade=offer.get("price_source", {}).get("grade"), basis="조식 객실 포함 가정(운영 레버)")
        g = (offer.get("price_source") or {}).get("grade")
        p = offer.get("price_pp_krw")
        if p is None or (p == 0 and g in ("가상", None) and offer.get("kind") not in ("rest",)):
            return dict(status="가격 미정", krw=None, grade=g, basis="엔진 상품 가격 미확인")
        out = max(0, p - (offer.get("guest_discount_krw") or 0) - (offer.get("card_benefit_krw") or 0))
        total = out * a.N
        if float(out).is_integer():
            return dict(status="무료" if out == 0 else "유료", krw=int(total), grade=g, basis=f"정량 엔진 상품 가격 {int(p):,}원 × {a.N}인", per="인")
        # A per-person price that is not a whole won (e.g. a breakfast whose room contract covers part of the party, spread
        # over the party) is billed as one party total: KRW stays an integer and no fractional unit price reaches the ledger.
        total = int(round(total))
        return dict(status="무료" if total == 0 else "유료", krw=total, grade=g,
                    basis=f"정량 엔진 상품 가격 {total:,}원 × 1세트({a.N}인 일행 합계 · 1인 환산 단가가 정수가 아님)", per="세트")
    if base in PLAN_PRICE:
        key, unit, note = PLAN_PRICE[base]
        krw, g = _price_of(key)
        if krw is None:
            return dict(status="가격 미정", krw=None, grade=None, basis=note)
        return dict(status="무료" if krw == 0 else "유료", krw=krw * a.N, grade=g, basis=f"{note} · {krw:,}원 × {a.N}인", per="인")
    return dict(status="가격 미정", krw=None, grade=None, basis="가격표에 없는 활동")


MEAL_SLOTS = (("breakfast", 0, 11 * 60), ("lunch", 11 * 60, 16 * 60), ("dinner", 16 * 60 + 30, 24 * 60))


def meal_slot(t):
    for k, s, e in MEAL_SLOTS:
        if s <= t < e:
            return k
    return None


def record_meal(a, code, kind, domain, t, fraction=None):
    """식사 행동이면 끼니 칸 · 양 기록. 간식(snack)은 끼니가 아님."""
    base = str(code).split(":")[0]
    if base == "lunch_skip":
        a.meals["lunch"] = True; a.meal_log.append(dict(t=t, slot="lunch", size="skip", code=base)); return "lunch"
    if base == "SKIP_BREAKFAST":
        a.meals["breakfast"] = True; a.meal_log.append(dict(t=t, slot="breakfast", size="skip", code=base)); return "breakfast"
    if domain != "식사":
        return None
    slot = meal_slot(t)
    if not slot:
        return None
    size = "light" if (fraction is not None and fraction < 0.8) else "full"
    a.meals[slot] = True
    a.meal_log.append(dict(t=t, slot=slot, size=size, code=base))
    return slot
