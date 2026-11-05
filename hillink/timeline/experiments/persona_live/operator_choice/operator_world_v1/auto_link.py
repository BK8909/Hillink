"""원문 사실 → 성향(facet) · 등급 · 선택지 속성 태그 자동 연결 (10/22 3차 · 공통 정책 · 100명 확장용)

목적: blog41·42·43 를 검수하며 손으로 만든 `relevance.py` 판단 원칙을, 새 작성자의 사실(V4.2 팀 스키마 fact)에 자동으로 적용한다.
입력 fact 필드(V4.2 `team_profile.schema.json $defs.fact`): kind · dimension · actor · time_scope · action_stage · polarity · confidence ·
feature_key · detail · experience_key · common_dimensions. 필드가 없으면(V4.1 개발 표본) feature_key + 요지 문자열만으로 판정한다.

판정 원칙(검수에서 확인한 것)
1. 사실의 의미 → 행동 유형 → 대상(상품 · 경험) → 선택지 속성 순으로 본다. 단어 하나로 성향을 확정하지 않는다.
2. 같은 상품군의 단순 비교 구매(가방 · 향 · 운동복 · 가전)는 '새 경험'이 아니라 '구매 전 가치 비교'다.
3. 무알코올 주문은 음주 친숙성 근거가 아니다(바 · 분위기 근거로만).
4. 혜택 활용은 실제 사용(적용 · 사용 · 교환 · 결제)이 보고된 경우만. 안내 · 소개 · 과거 경험 인용 · 계획은 제외.
5. 이용 후 평가는 '이용 후 가치 평가'로만 — 구매 전 가격 성향으로 옮기지 않는다.
6. 새 식당 · 메뉴 탐색은 '새 경험(새 음식)'이지 '시즌 행사 반응'이 아니다. 시즌 · 한정 · 행사 · 팝업 · 증정이 명시돼야 시즌 반응.
7. 미래 계획 · 추천 · 기대는 제외. 작성자 추정(author_inferred) · 낮은 확신은 약한 근거.
"""
from __future__ import annotations

import re

R, W, X = "rep", "weak", "exclude"

# (정규식, [(facet, 태그 목록)]) — 한국어 요지 · 영문 특성 키를 함께 본다
LEX = [
    (r"무알코올|nonalcoholic", [("space", ["ambience"])]),
    (r"(?<!무알코올 )(와인|맥주|칵테일|하이볼|전통주|소주|위스키)|(?<!non)alcohol(?!_self)|wine|beer|cocktail", [("alcohol_familiar", ["wine", "bar"])]),
    (r"술이 약|음주 내성|low_alcohol", [("alcohol_limit", [])]),
    (r"야경|night_view|밤", [("space", ["night_view"])]),
    (r"정원|숲|산책|garden|forest|walk", [("space", ["garden"])]),
    (r"분위기|ambience|전망|조망|뷰|view(?!_)", [("space", ["ambience", "view_seat"])]),
    (r"장식|연출|decor", [("space", ["decor"])]),
    (r"족욕|footbath", [("warm_rest", ["footbath"])]),
    (r"따뜻|온수|얕은 풀|warm_shallow|warm_pool", [("warm_rest", ["warm_pool"])]),
    (r"수영.*(안 함|않|무서|비선호)|not_swim|swim_preference|pool_visit_not", [("swim_aversion", [])]),
    (r"휴식|쉬려|쉬는|쉼|회복|마사지|recovery|rest_purpose|_break(?!fast)", [("rest_need", ["rest"])]),
    (r"한정|limited", [("novelty", ["limited_goods"]), ("seasonal", ["limited_goods"])]),
    (r"행사|축제|팝업|페어|증정|이벤트|popup|poster|event", [("novelty", ["event"]), ("seasonal", ["event"])]),
    (r"시즌|계절|빙수|seasonal|_ice", [("seasonal", ["seasonal_food"])]),
    (r"광고|홍보|(^|_)ad(_|$)|advert", [("promo", ["promo"])]),
    (r"새 메뉴|다른 메뉴|처음|시그니처|궁금|new_menu|menu_different|curiosity|trial", [("novelty", ["new_food"]), ("food", ["menu_explore"])]),
    (r"코스.*예약|reservation", [("novelty", ["new_food"])]),
    (r"새로 생긴|새 호텔|new_hotel", [("novelty", ["new_place"])]),
    (r"뷔페|buffet", [("food", ["buffet", "menu_explore"])]),
    (r"코스|오마카세|course", [("food", ["course"]), ("premium", ["course"])]),
    (r"셰프|chef", [("premium", ["chef"])]),
    (r"여러 메뉴|두 가지|맛과 소스|두루|flavors|explor", [("food", ["menu_explore"])]),
    (r"디저트|아이스크림|빙수|베이커리|dessert|icecream|bakery|tart|_ice", [("food", ["dessert"])]),
    (r"할인|discount", [("benefit", ["discount"])]),
    (r"쿠폰|바우처|voucher|coupon", [("benefit", ["voucher"])]),
    (r"카드|card", [("benefit", ["card"])]),
    (r"패키지|package", [("benefit", ["package"])]),
    (r"가격 기준|비교|인상 전|작은 구성|소량|교체|pre_|replacement|store_choice|bundle", [("value_check", [])]),
    (r"(피자|마늘|갈릭|말차|타르트|메뉴|음식|소스|조개|pizza|garlic|matcha|tart|shellfish).*(좋아|선호|preference|exception)|(좋아|preference).*(피자|말차|pizza|matcha)", [("food_specific", [])]),
    (r"습관|반복|다시|재방문|habit|repeat|same_purchase", [("routine", ["repeat"])]),
    (r"외부 음식|배달|치킨|external_food", [("practical_alt", ["room_meal"])]),
    (r"조식|breakfast", [("breakfast_priority", [])]),
    (r"헬스|운동(?!복)|피트니스|gym|fitness", [("active", [])]),
]
ACTUAL_USE = r"사용|이용|적용|받|활용|교환|결제|구매|used|applied|topup|discount|coupon|card_benefit|voucher_choice|purchase"
NOT_ACTUAL = r"안내|소개|인용|계획만|plan_not|references|prior_|annual_"
COMMODITY = r"가방|향 제품|운동복|가전|상품 구매|bag|perfume|sportswear|shaver|goods_purchase|sauna_goods|sauna_market"


def link_fact(fact: dict) -> dict:
    """fact → {facet: (grade, tags)} · 판정 이유(rules)."""
    text = f"{fact.get('feature_key', '')} {fact.get('detail', '')}"
    out: dict[str, tuple[str, list]] = {}
    why = []

    def add(facet, grade, tags, rule):
        g0, t0 = out.get(facet, (None, []))
        order = {R: 2, W: 1, X: 0, None: -1}
        if g0 == X and grade != X:
            return              # 원칙상 제외된 연결은 다른 단어로 되살리지 않음
        if order[grade] >= order[g0] or grade == X:
            out[facet] = (grade, sorted(set(t0) | set(tags)) if grade != X else [])
        why.append(f"{facet}:{grade}:{rule}")

    for pat, links in LEX:
        if re.search(pat, text):
            for facet, tags in links:
                add(facet, R, tags, pat[:24])
    # 원칙 2 — 단순 비교 구매는 새 경험 · 혜택이 아님
    if re.search(COMMODITY, text):
        for f in ("novelty", "benefit", "food_specific"):
            if f in out:
                add(f, X, [], "commodity_purchase")
        add("value_check", W if "value_check" not in out else out["value_check"][0], [], "commodity_purchase")
    # 원칙 3 — 무알코올은 음주 친숙성 아님
    if re.search(r"무알코올|nonalcoholic", text) and "alcohol_familiar" in out:
        add("alcohol_familiar", X, [], "nonalcoholic")
    # 원칙 4 — 혜택은 실제 사용만
    if "benefit" in out and out["benefit"][0] != X:
        if re.search(NOT_ACTUAL, text) or not (re.search(ACTUAL_USE, text) or fact.get("action_stage") in ("purchase_reported", "order_reported", "consumption_reported")):
            add("benefit", X, [], "benefit_not_actual_use")
    if re.search(NOT_ACTUAL, text):
        for f in list(out):
            if f != "value_check":
                add(f, X, [], "not_actual")     # 안내 · 인용 · 계획은 실제 경험 근거가 아님
    # 원칙 5 — 이용 후 평가
    if fact.get("dimension") == "post_appraisal" or re.search(r"가치 유보|실망|다시 사지|value_qualified|disappointment|no_repurchase|voucher_value", text):
        out = {}
        add("post_appraisal", R, [], "post_appraisal")   # 같은 사실을 혜택 · 음식 등 다른 성향에 쓰지 않음
    # 원칙 7 — 시점 · 주체 · 확신
    if fact.get("time_scope") in ("future", "recommended") or fact.get("kind") == "expectation":
        out = {k: (X, []) for k in out}
        why.append("future_or_recommended")
    elif fact.get("actor") == "author_inferred" or fact.get("confidence") == "low":
        out = {k: ((W if g == R else g), t) for k, (g, t) in out.items()}
        why.append("inferred_or_low")
    if fact.get("actor") in ("other", "unknown"):
        out = {k: (X, []) for k in out}
        why.append("not_author")
    # V4.2 dimension 보조(단어가 없을 때)
    dim = fact.get("dimension")
    if dim == "prepurchase_criteria" and "value_check" not in out:
        add("value_check", R, [], "dimension")
    if dim == "specific_preference" and "food_specific" not in out:
        add("food_specific", R, [], "dimension")
    if dim == "revisit_expression" and "routine" not in out:
        add("routine", R, ["repeat"], "dimension")
    return dict(links=out, rules=why)


MENU_LEX = {"pizza": r"피자|pizza", "garlic": r"마늘|갈릭|garlic", "olive_oil": r"올리브", "pasta": r"파스타|pasta", "seafood": r"해산물|해물|조개|seafood|shellfish",
            "cheese": r"치즈|cheese", "korean": r"한식|korean", "matcha": r"말차|matcha", "egg_tart": r"에그타르트|egg_tart", "wine": r"와인|wine",
            "signature_drink": r"시그니처 음료|signature_drink", "bakery": r"빵|베이커리|bakery", "variety": r"여러 메뉴|두 가지|variety"}


def menu_tags(text: str) -> list[str]:
    return [k for k, p in MENU_LEX.items() if re.search(p, text)]
