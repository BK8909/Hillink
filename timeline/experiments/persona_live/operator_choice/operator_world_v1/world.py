"""운영자가 편집하는 가상 워커힐 월드 (10/22 · 총괄 C · 격리 연구)

- 운영자가 실제로 결정할 수 있는 변수만 둔다: 행사 개설 · 가격 · 투숙객 할인 · 객실 패키지 포함 · 음식 구성(시음만/안주/페어링 코스) · 셰프 콜라보 · 무알코올 대안 · 시간 · 홍보.
- 좌석 재고 · 대기열 · 정원 경쟁은 범위 밖(이번 단계 제외).
- 가격 출처 등급: ◎ 공식 · ○ 공식 유도 · △ 후기 전언 · 가상(연구용). 등급은 `timeline/prices.py` 메모를 옮겼다.
- 월드와 방문 입력에는 정답 · 기대 행동 · 사전 가설을 넣을 수 없다(`assert_no_results`).
"""
from __future__ import annotations

from copy import deepcopy

PROHIBITED_KEYS = {"expected", "expected_action", "choice", "answer", "action_hypothesis", "hypothesis", "winner",
                   "selected", "truth", "gold", "label_action", "should_choose", "target_action"}

FOOD_LEVELS = {
    # 음식 구성 수준 → 한 끼 충족 비율 · 코스 수 (가상)
    "tasting_only": dict(meal_fraction=0.15, courses=0, label="시음 위주(간단 핑거푸드)"),
    "light_bites": dict(meal_fraction=0.4, courses=1, label="안주 · 가벼운 음식 1종"),
    "pairing_course": dict(meal_fraction=0.8, courses=3, label="음식 페어링 코스 3종"),
}


def hm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def mh(x: int) -> str:
    return f"{x // 60:02d}:{x % 60:02d}"


def offer(id, label, kind, venue, *, window=None, duration=60, price=0, grade="가상", price_note="",
          guest_discount=0, card_benefit=0, in_package=False, meal_fraction=0.0, courses=0, quality="none",
          menu_tags=(), menu_known=True, alcohol_required=False, tasting=False, nonalcoholic_alt=False,
          night_view=False, garden=False, warm_water=False, swimming=False, indoor=True, novelty=0.0,
          seasonal=False, promoted=False, rest_value=0.0, available=True, status="official", repeatable=False, note="", onsite_menu_board=None):
    return dict(id=id, label=label, kind=kind, venue=venue,
                window=window, duration_min=duration,
                price_pp_krw=price, price_source=dict(grade=grade, note=price_note),
                guest_discount_krw=guest_discount, card_benefit_krw=card_benefit, in_package=in_package,
                food=dict(meal_fraction=meal_fraction, courses=courses, quality=quality, menu_tags=list(menu_tags), menu_known=menu_known),
                alcohol=dict(required=alcohol_required, tasting=tasting, nonalcoholic_alt=nonalcoholic_alt),
                space=dict(night_view=night_view, garden=garden, warm_water=warm_water, swimming=swimming, indoor=indoor),
                novelty=novelty, seasonal=seasonal, promoted=promoted, rest_value=rest_value,
                available=available, status=status, repeatable=repeatable, note=note,
                **({} if onsite_menu_board is None else dict(onsite_menu_board=onsite_menu_board)))


def default_world(season: str = "autumn") -> dict:
    """가을 주말 · 와인페어 기본 월드. 행사 조건은 운영자 변수(가상)."""
    offers = [
        offer("WINE_FAIR", "와인페어(포레스트 파크)", "event", "FOREST",
              window=dict(start="15:30", end="20:00"), duration=120,
              price=55000, grade="◎", price_note="2026 가을 '구름 위의 산책'(PR #71 · #82 · #92 대조): 2부 15:30~20:00(공식 · 1부 11:00~15:00) · 외부 성인 55,000원(공식) · 사전 구매 10%(보도자료) · "
                                               "구매 입장권 포함물 리델 글라스 · 칠링백 · 푸드 교환권 1매(보도자료 · #82: 무료 입장자에게도 주는지는 미상) → 음식은 시음 + 교환권 1매 수준(시음 위주) · "
                                               "일반 투숙객(객실만) 무료 자격 미상(보도자료 문구뿐 · Wine Forest 패키지에 입장권 2매 별도 포함) → 기본은 유료, '투숙객 무료'는 가상 조건 · "
                                               "현장 메뉴 게시 근거 없음 · 입장권 픽업은 프런트(공식) · 행사 날 포레스트 파크 일반 이용 제한(공식)",
              onsite_menu_board=False,
              guest_discount=0, in_package=False,
              meal_fraction=FOOD_LEVELS["tasting_only"]["meal_fraction"], courses=0, quality="standard",
              menu_tags=["wine"], menu_known=False,
              alcohol_required=True, tasting=True, nonalcoholic_alt=False,
              night_view=True, garden=True, indoor=False, novelty=1.0, seasonal=True, promoted=True,
              status="virtual", note="개최 여부 · 음식 구성 · 할인 · 패키지는 연구용 가상 운영 조건"),
        offer("PIZZA_HILL", "피자힐 저녁", "restaurant", "PIZZA_HILL", window=dict(start="17:30", end="21:30"), duration=90,
              price=92000, grade="○", price_note="커플 세트 184,000 ÷ 2(공식 메뉴) · 투숙객 할인 주중 20% · 주말 10%는 후기값(공식 미확인 · PR #92) → 4차부터 기본 월드에서 제외하고 운영 조건으로만 · 공식 문구는 '멤버십 · 카드 제휴 할인 가능'(율 미표기)", guest_discount=0,
              meal_fraction=1.0, courses=2, quality="standard", menu_tags=["pizza", "garlic", "olive_oil", "pasta"], night_view=True,
              note="야경 속성: 공식 보도자료의 '한강 테라스'(PR #92) · 다른 식당은 야경 · 조망 정보가 없어 0(정보 없음 ≠ 야경 없음)"),
        offer("THE_BUFFET", "더뷔페 디너", "restaurant", "THE_BUFFET", window=dict(start="17:30", end="21:30"), duration=120,
              price=198000, grade="◎", price_note="공식 석식 성인가", meal_fraction=1.0, courses=3, quality="standard",
              menu_tags=["buffet", "seafood", "variety"]),
        offer("MYONGWOLGWAN", "명월관 저녁", "restaurant", "MYONGWOLGWAN", window=dict(start="17:30", end="21:30"), duration=90,
              price=78000, grade="◎", price_note="양념갈비 200g 기준", meal_fraction=1.0, courses=1, quality="standard",
              menu_tags=["korean", "bbq"]),
        offer("ONDAL", "온달 저녁(가을바다 꽃게 정찬)", "restaurant", "ONDAL", window=dict(start="17:30", end="21:30"), duration=90,
              price=80000, grade="◎", price_note="2026 가을 메뉴 '가을바다 꽃게 정찬' 80,000원(공식 · PR #92) · 운영 시각은 다른 식당과 같은 가정",
              meal_fraction=1.0, courses=1, quality="standard", menu_tags=["korean", "seafood", "crab"],
              note="4차 추가 · 공식 가을 메뉴만 반영 · 공간 · 할인 정보 없음(임의 추가 안 함)"),
        offer("GEUMRYONG", "금룡 저녁(추미진향 코스)", "restaurant", "GEUMRYONG", window=dict(start="17:30", end="21:30"), duration=120,
              price=150000, grade="◎", price_note="2026 가을 코스 '추미진향' 150,000원(공식 · PR #92) · 코스 구성 수 · 운영 시각은 가정",
              meal_fraction=1.0, courses=3, quality="standard", menu_tags=["chinese", "course"],
              note="4차 추가 · 공식 가을 메뉴만 반영 · 공간 · 할인 정보 없음(임의 추가 안 함)"),
        offer("ROOM_MEAL", "객실에서 식사(룸서비스 · 배달)", "room_meal", "ROOM_MEAL", window=dict(start="17:30", end="22:30"), duration=60,
              price=43000, grade="○", price_note="공식 IRD 메뉴 클럽 샌드위치 기준 · 배달 음식은 가격 다름", meal_fraction=1.0, courses=1, quality="standard",
              menu_tags=["chicken", "sandwich"], rest_value=0.6),
        offer("SIMPLE_MEAL_VIEW", "르파사쥬 빵 · 간단히 먹고 야경", "simple_meal", "LE_PASSAGE", window=dict(start="17:30", end="22:00"), duration=60,
              price=12000, grade="△", price_note="베이커리 가격표 미공개 · 후기 전언", guest_discount=0, meal_fraction=0.5, courses=1, quality="standard",
              menu_tags=["bakery", "egg_tart"], night_view=True),
        offer("SKYARD", "스카이야드 족욕(낮)", "facility", "SKYARD", window=dict(start="15:30", end="19:00"), duration=60,
              price=0, grade="△", price_note="비스타 투숙 무료(후기 전언) · 그 외 객실당 19,000 전언", garden=True, warm_water=True, indoor=False, rest_value=0.5),
        offer("SKYARD_NIGHT", "스카이야드 족욕 · 야경(밤)", "facility", "SKYARD", window=dict(start="19:30", end="22:30"), duration=60,
              price=0, grade="△", price_note="비스타 투숙 무료(후기 전언)", night_view=True, warm_water=True, indoor=False, rest_value=0.5),
        offer("POOL", "실내 수영장", "facility", "POOL", window=dict(start="15:30", end="21:00"), duration=90,
              price=0, grade="◎", price_note="투숙객 무료", warm_water=True, swimming=True, rest_value=0.2),
        offer("SAUNA", "웰니스 사우나", "facility", "SAUNA", window=dict(start="15:30", end="21:00"), duration=60,
              price=20000, grade="◎", price_note="그랜드 피트니스 사우나 1인", warm_water=True, rest_value=0.6),
        offer("FOREST_WALK", "포레스트 파크 산책", "facility", "FOREST", window=dict(start="15:30", end="18:00"), duration=45,
              price=0, grade="◎", price_note="투숙객 무료", garden=True, indoor=False, rest_value=0.3,
              note="와인페어 개최일에는 포레스트 파크 일반 이용 제한(공식 공지 · PR #71) → 엔진이 행사 개최 시 이용 불가로 처리"),
        offer("ROOM_REST", "객실에서 쉬기", "rest", "ROOM", window=None, duration=60, price=0, grade="—", rest_value=1.0, repeatable=True),
    ]
    if season == "summer":
        offers.append(offer("RIVERPARK", "리버파크(야외 수영장)", "facility", "RIVERPARK", window=dict(start="15:30", end="18:00"), duration=120,
                            price=95000, grade="△", price_note="2026 골드 시즌 금~일 1부 성인 · 후기 전언", swimming=True, indoor=False, novelty=0.6, seasonal=True, rest_value=0.1,
                            status="virtual"))
        offers[0]["available"] = False
    return dict(version="operator_world_v1", status="fictional_operating_conditions", season=season,
                day="가을 주말(가상 · 실제 방문일 아님)", offers=offers,
                dinner_window=dict(start="17:00", end="22:00"), main_dinner=dict(start="18:30", end="20:30"),
                sunset="18:00", sunset_note="가정 — 10월 서울 일몰 약 17:45~18:15 · 야경 속성은 활동이 이 시각 뒤까지 이어질 때만",
                levers_note="운영자 변수: 행사 개설 · 가격 · 투숙객 할인 · 패키지 포함 · 음식 구성 · 셰프 콜라보 · 무알코올 대안 · 시간 · 홍보")


VISIT_VARIANTS = {
    "default": dict(label="일반 2인 숙박 · 휴식과 식음 반반", rest_goal=0.5, purpose="휴식 · 식음 중심 숙박(가정 · 원문의 과거 동행을 이전하지 않음)"),
    "rest": dict(label="조용한 휴식이 목적인 2인 숙박", rest_goal=0.85, purpose="조용한 휴식 · 재충전이 목적(가정 · blog43 더글라스 방문 맥락을 이번 방문 목적으로 지정)"),
}


def default_visit(persona_id: str, variant: str = "default") -> dict:
    vv = VISIT_VARIANTS[variant]
    return dict(persona_id=persona_id, visit_variant=variant, visit_label=vv["label"], party_size=2, companions="2인(가정)", purpose=vv["purpose"],
                rest_goal=vv["rest_goal"], alcohol_eligible=True, breakfast_included=True, checkin="15:30", end="23:00",
                assumptions=["동행 · 목적 · 조식 포함은 이번 가상 방문의 가정이며 원문 사실이 아님"])


def apply_levers(world: dict, levers: dict) -> dict:
    """운영자 변수 묶음을 월드에 적용(원본 보존)."""
    w = deepcopy(world)
    by = {o["id"]: o for o in w["offers"]}
    for oid, change in (levers or {}).items():
        if oid not in by:
            raise KeyError(f"unknown offer {oid}")
        o = by[oid]
        for k, v in change.items():
            if k == "food_level":
                lv = FOOD_LEVELS[v]
                o["food"]["meal_fraction"] = lv["meal_fraction"]; o["food"]["courses"] = lv["courses"]; o["food_level"] = v
            elif k in ("menu_tags", "menu_known", "quality"):
                o["food"][k] = v
            elif k in ("nonalcoholic_alt", "tasting", "required"):
                o["alcohol"][k] = v
            elif k == "window":
                o["window"] = v
            elif k in o:
                o[k] = v
            else:
                raise KeyError(f"unknown lever {k} for {oid}")
    return w


def assert_no_results(obj, path="input"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in PROHIBITED_KEYS:
                raise ValueError(f"prohibited_result_key:{path}.{k}")
            assert_no_results(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_no_results(v, f"{path}[{i}]")


def validate_world(world: dict):
    assert_no_results(world, "world")
    ids = [o["id"] for o in world["offers"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_offer_id")
    if not any(o["kind"] == "rest" and o["available"] for o in world["offers"]):
        raise ValueError("rest_option_required")
    for o in world["offers"]:
        f = o["food"]
        if not 0 <= f["meal_fraction"] <= 1:
            raise ValueError(f"meal_fraction_range:{o['id']}")
        if o["price_pp_krw"] < 0 or o["guest_discount_krw"] < 0 or o["card_benefit_krw"] < 0:
            raise ValueError(f"negative_price:{o['id']}")
        if o["window"] and hm(o["window"]["end"]) <= hm(o["window"]["start"]):
            raise ValueError(f"window_order:{o['id']}")


def validate_visit(visit: dict):
    assert_no_results(visit, "visit")
    if visit["party_size"] < 1 or not 0 <= visit["rest_goal"] <= 1:
        raise ValueError("visit_range")
