"""핵심 선택 턴(연구 후보) — 대표 상품 목록(product_catalog.json)으로 한 턴의 후보를 만들고, 내다보기 없이 그 턴만 판단한다.

- V1 엔진 · V1 월드 · R-BASE 후보 코드는 바꾸지 않는다. 점수 함수는 R-BASE 후보(candidate_engine)를 그대로 쓴다.
- 턴 = 한 시점 · 그 턴의 후보 집합 · 최소 상태(끼니 해결 여부 · 동행 인원 · 방문 조건). 하루 최적화 없음.
- 가격 기준(pricing):
    "historical"  : 자료에 적힌 값 그대로(과거 방문 재현용 · 2021 사진은 2021 값)
    "provisional" : 2021 사진 항목만 ×1.10(추정 시나리오 · 운영자 시연용 · 재현 평가 금지) · PDF 항목은 그대로
    "world_v1"    : 기존 월드의 공식 IRD 값(43,000)이 있는 항목은 그 값으로 · 나머지는 historical
- 인원 기준이 자료에 없는 세트(party_basis=None)는 운영자가 party_basis 를 넣기 전에는 후보에서 뺀다(1인 가격을 정하지 않음).
- 단품 피자처럼 나눠 먹는 상품은 share_n(운영자 입력)이 있을 때만 1인 가격 = 가격 ÷ share_n.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from operator_choice.operator_world_v1 import engine as EN
from operator_choice.operator_world_v1 import world as WD
from operator_choice.operator_world_v1_1.candidate import candidate_engine

CATALOG_PATH = Path(__file__).with_name("product_catalog.json")
TURN_TIME = {"breakfast": "08:30", "lunch": "12:30", "event": "16:30", "dinner": "18:30"}
# 10/23 행사 턴 — 기존 V1 월드의 선택지(와인페어 · 산책 · 족욕 · 객실 휴식)만 후보로 두는 한 턴. 새 선택지 · 새 계수 없음.
EVENT_KEEP = ("WINE_FAIR", "FOREST_WALK", "SKYARD", "ROOM_REST")
# 화면의 WINE_FAIR 운영 변수 이름 → 기존 월드 조정값 이름
EVENT_LEVER_MAP = {"price": "price_pp_krw", "guest_discount": "guest_discount_krw", "in_package": "in_package"}
EVENT_VARIANTS = {   # 기존 PRESETS(④ ⑤ ⑥)의 구성 변형 — 값은 그 프리셋 그대로
    "standard": {},
    "nonalc": {"food_level": "light_bites", "nonalcoholic_alt": True, "menu_known": True, "menu_tags": ["wine", "cheese"]},
    "pairing": {"food_level": "pairing_course", "price_pp_krw": 90000, "menu_known": True, "menu_tags": ["wine", "cheese", "seafood"]},
    "chef": {"food_level": "pairing_course", "quality": "chef_collab", "price_pp_krw": 120000, "menu_known": True, "menu_tags": ["wine", "pizza", "garlic"]},
}
TURN_WINDOW = {"breakfast": ("07:00", "10:00"), "lunch": ("11:00", "14:30"), "dinner": ("17:30", "22:30")}
MEAL_KINDS = {"restaurant", "room_meal", "simple_meal"}
KEEP_BASE_DINNER = ("MYONGWOLGWAN", "ONDAL", "GEUMRYONG", "THE_BUFFET", "SIMPLE_MEAL_VIEW")   # 공식 2026 값이 있는 기존 식당은 그대로 후보에


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def price_for(p: dict, pricing: str) -> tuple[int, str]:
    """상품의 기준 가격과 그 출처 설명. 임시 가격은 별도 필드에서만 가져오고 원값은 건드리지 않는다."""
    if pricing == "provisional" and p.get("provisional_sim_price_krw"):
        return p["provisional_sim_price_krw"], f"{p['source']} × 1.10 (추정 · 운영자 설정값 · 실제 판매가 아님)"
    if pricing == "world_v1":
        alt = next((a for a in p.get("alt_prices", []) if a["source"] == "WORLD_V1_IRD"), None)
        if alt:
            return alt["price_krw"], "기존 월드 공식 IRD 기준(월드 주석)"
    return p["price_krw"], f"{p['source']} 원값"


def product_to_offer(p: dict, pricing: str, party_size: int, levers: dict | None = None, room_rest_value: float = 0.6) -> dict | None:
    """카탈로그 상품 → 엔진 선택지. 1인 가격을 정할 수 없으면 None(후보 제외 · 이유는 호출자가 기록)."""
    lv = dict(levers or {})
    if lv.get("available") is False:                      # 10/23 운영자 레버: 이 상품을 이번 턴에 팔지 않음(메뉴 구성 실험) — 계수 아님
        return None
    price, src = price_for(p, pricing)
    if "price" in lv:
        price, src = lv["price"], "운영자 설정 가격"
    basis = lv.get("party_basis", p.get("party_basis"))
    share = lv.get("share_n")
    if p["kind"] == "set" and not basis:
        return None
    if basis:
        pp = price / basis
        unit_note = f"{p['unit']} {price:,}원 ÷ {basis}인" + ("" if p.get("party_basis_stated") or "party_basis" in lv else " (인원 추정)")
    elif share:
        pp = price / share
        unit_note = f"{p['unit']} {price:,}원 ÷ 나눔 {share}인(운영자 입력)"
    else:
        return None
    venue_space = dict(night_view=p["venue"] == "PIZZA_HILL", garden=False, warm_water=False, swimming=False, indoor=True)
    if p["kind"] == "promo" and "포장" in p["name"]:
        venue_space["night_view"] = False                       # 포장해서 객실에서 먹는 행동 — 공간 경험 없음
    o = WD.offer(p["id"], p["name"], "restaurant" if p["venue"] == "PIZZA_HILL" and "포장" not in p["name"] else "room_meal",
                 "ROOM_MEAL" if ("포장" in p["name"] or p["venue"] == "ROOM_MEAL") else p["venue"],
                 window=dict(start=TURN_WINDOW[p["turn"]][0], end=TURN_WINDOW[p["turn"]][1]),
                 duration=90 if p["venue"] == "PIZZA_HILL" and "포장" not in p["name"] else 60,
                 price=round(pp), grade="○" if p["source"].startswith("PH_PDF") else "△",
                 price_note=f"{src} · {unit_note}",
                 guest_discount=lv.get("guest_discount", 0), card_benefit=lv.get("card_benefit", 0), in_package=lv.get("in_package", False),
                 meal_fraction=p["meal_fraction"], courses=p["courses"], quality="standard", menu_tags=p["menu_tags"],
                 rest_value=room_rest_value if o_is_room(p) else 0.0,     # 객실식사 휴식 가치 — 근거 없는 설계 가정(민감도 항목)
                 status="catalog_" + p["source"], note=" · ".join(p.get("assumptions", []) + [f"미확인: {u}" for u in p.get("unverified", [])]))
    o["space"].update(venue_space)
    o["catalog"] = dict(id=p["id"], kind=p["kind"], source=p["source"], pricing=pricing, list_price_krw=price, party_basis=basis, share_n=share)
    return o


def o_is_room(p: dict) -> bool:
    return p["venue"] == "ROOM_MEAL" or "포장" in p["name"]


def turn_world(turn: str = "dinner", pricing: str = "historical", party_size: int = 2, product_levers: dict | None = None,
               base_levers: dict | None = None, include_ids: list[str] | None = None, catalog: dict | None = None, room_rest_value: float = 0.6,
               allow_skip: bool = False) -> tuple[dict, list[dict]]:
    """그 턴의 후보만 담은 월드와 '후보에서 뺀 상품과 이유' 목록."""
    cat = catalog or load_catalog()
    if turn == "event":
        lv = dict((product_levers or {}).get("WINE_FAIR") or {})
        wf = dict(EVENT_VARIANTS.get(lv.pop("variant", "standard") or "standard", {}))
        for k, v in lv.items():
            if k in EVENT_LEVER_MAP and v not in (None, False, ""):
                wf[EVENT_LEVER_MAP[k]] = v
        merged = dict(base_levers or {}); merged["WINE_FAIR"] = dict(merged.get("WINE_FAIR") or {}, **wf)
        base = WD.apply_levers(WD.default_world(), merged)
        offers = [o for o in base["offers"] if o["id"] in EVENT_KEEP]
        for o in offers:
            virtual = o["id"] == "WINE_FAIR" and bool(wf)      # 구성 · 가격 · 할인 · 포함을 바꿨으면 공식 조건이 아니라 연구 프리셋(가상 운영안)
            o["catalog"] = dict(id=o["id"], kind="event" if o["id"] == "WINE_FAIR" else o["kind"], source="PRESET_V1" if virtual else "WORLD_V1", pricing="preset" if virtual else "world_v1",
                                list_price_krw=o["price_pp_krw"], party_basis=1, share_n=None)
            if virtual:
                o["price_source"] = dict(o["price_source"], note="운영자 설정 · 연구 프리셋(가상 운영안) — 구성 · 가격 · 혜택은 공식 자료가 아님 · 음식 구성의 끼니 비중(시음 0.15 · 안주 0.4 · 페어링 0.8)은 설계값")
        return dict(base, offers=offers, turn=turn, pricing=pricing), []
    base = WD.apply_levers(WD.default_world(), base_levers or {})
    keep = [o for o in base["offers"] if turn == "dinner" and o["id"] in KEEP_BASE_DINNER]
    excluded, offers = [], []
    for p in cat["products"]:
        if p["turn"] != turn or (include_ids and p["id"] not in include_ids):
            continue
        o = product_to_offer(p, pricing, party_size, (product_levers or {}).get(p["id"]), room_rest_value)
        if o is None:
            off = ((product_levers or {}).get(p["id"]) or {}).get("available") is False
            excluded.append(dict(id=p["id"], name=p["name"], why="운영자 설정 — 이번 조건에서 판매하지 않음(메뉴 구성 실험)" if off else "인원 기준 미확인 — 운영자가 party_basis 또는 share_n 을 넣기 전에는 1인 가격을 정하지 않음"))
            continue
        offers.append(o)
    if turn == "breakfast":
        # 10/23 아침 턴 — 공식 조식 가격이 없어 뷔페는 운영자 가격 입력 또는 '객실 포함' 일 때만 후보. 건너뛰기(객실에서 쉼)는 기존 휴식 선택지와 같은 형태
        bl = (product_levers or {}).get("BREAKFAST_BUFFET", {})
        inc = bool(bl.get("in_package"))
        if bl.get("price") is None and not inc:
            excluded.append(dict(id="BREAKFAST_BUFFET", name="호텔 조식 뷔페(더뷔페)", why="공식 조식 가격 미확인 — 운영자가 가격을 넣거나 객실 포함으로 정하기 전에는 후보에 넣지 않음"))
        else:
            price = int(bl.get("price") or 0)
            o = WD.offer("BREAKFAST_BUFFET", "호텔 조식 뷔페(더뷔페)", "restaurant", "THE_BUFFET", window=dict(start="07:00", end="10:00"), duration=60,
                         price=price, grade="가정", price_note="객실 포함 · 지불 0(포함 여부는 운영자 설정)" if inc else "운영자 설정 · 공식 가격 미확인(실험 가정)",
                         in_package=inc, meal_fraction=1.0, courses=2, quality="standard", menu_tags=["buffet", "variety", "egg", "bread", "korean"],
                         status="operator_assumption", note="가격 · 구성은 운영자 설정값 · 공식 자료 아님")
            o["catalog"] = dict(id="BREAKFAST_BUFFET", kind="single", source="OPERATOR_INPUT", pricing="operator", list_price_krw=price, party_basis=1, share_n=None)
            offers.append(o)
        o = WD.offer("SKIP_BREAKFAST", "조식 건너뜀(객실에서 쉼)", "rest", "ROOM", window=None, duration=60, price=0, grade="—", rest_value=1.0,
                     status="official", note="기존 월드 '객실에서 쉬기'와 같은 휴식 선택지 · 아침 턴에서는 끼니를 건너뛰는 선택")
        o["catalog"] = dict(id="SKIP_BREAKFAST", kind="single", source="NONE", pricing="none", list_price_krw=0, party_basis=1, share_n=None)
        offers.append(o)
        # 끼니 규칙 재사용 — 저녁 끼니 창을 아침 창으로 바꿔 같은 규칙(끼니 해결 · 식사 시간대의 비식사 감점)을 적용 · 새 계수 없음
        base = dict(base, dinner_window=dict(start="07:00", end="10:00"), main_dinner=dict(start="08:00", end="09:30"))
    if turn == "dinner" and allow_skip:
        # 행사 턴에서 이미 먹은 뒤(상태 연결)에만 '저녁 건너뜀' 을 후보에 둔다 — 기존 월드 '객실에서 쉬기' 와 같은 휴식 선택지
        o = WD.offer("SKIP_DINNER", "저녁 건너뜀(객실에서 쉼)", "rest", "ROOM", window=None, duration=60, price=0, grade="—", rest_value=1.0,
                     status="official", note="행사에서 음식을 먹은 뒤에만 후보 · 기존 월드 '객실에서 쉬기' 와 같은 선택지")
        o["catalog"] = dict(id="SKIP_DINNER", kind="single", source="NONE", pricing="none", list_price_krw=0, party_basis=1, share_n=None)
        offers.append(o)
    w = dict(base, offers=keep + offers, turn=turn, pricing=pricing)
    return w, excluded


def decide_turn(traits: dict, visit: dict, world: dict, turn: str = "dinner", state: dict | None = None, ctx=None) -> dict:
    """한 턴의 판단 — 내다보기 없음. 반환: 선택한 옵션 / 선택하지 않은 옵션 / 이렇게 선택한 이유(항별 값 · 근거)."""
    st = dict(used=set(), hunger=1.0, _depth=99)
    st.update(state or {})
    st["_depth"] = 99
    v = dict(visit, checkin="07:00" if turn == "breakfast" else visit.get("checkin", "15:30"))
    ctx = ctx or (lambda: candidate_engine(c1=True, c2="venue_visits", c3=True))
    with ctx():
        d = EN.decide_at(EN.hm(TURN_TIME[turn]), st, v, traits, world)
    by = {o["id"]: o for o in world["offers"]}
    chosen = by[d["chosen"]]
    others = []
    for r in d["rejected"]:
        o = by[r["offer"]]
        others.append(dict(id=o["id"], label=o["label"], price_pp_krw=o["price_pp_krw"], feasible=r["feasible"], score=r.get("score"),
                           blocked=r.get("blocked", []), catalog=o.get("catalog")))
    others.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    if turn == "breakfast":                                              # 재사용한 끼니 규칙의 표시 이름만 아침으로
        for x in d["terms"]:
            x["factor"] = x["factor"].replace("저녁 끼니 해결", "아침 끼니 해결").replace("저녁을 미룸", "아침 식사 건너뜀")
    return dict(turn=turn, time=TURN_TIME[turn], pricing=world.get("pricing"),
                chosen=dict(id=chosen["id"], label=chosen["label"], price_pp_krw=chosen["price_pp_krw"], score=d["score"], catalog=chosen.get("catalog"),
                            price_note=chosen["price_source"]["note"]),
                not_chosen=others,
                reasons=[dict(factor=x["factor"], value=round(x["value"], 4), facet=x.get("facet"), fact_ids=list(x.get("fact_ids", [])), note=x.get("note", ""))
                         for x in d["terms"]],
                state_after=dict(hunger=max(0.0, round(st["hunger"] - chosen["food"]["meal_fraction"], 4)), used=sorted(st["used"] | {chosen["id"]})))
