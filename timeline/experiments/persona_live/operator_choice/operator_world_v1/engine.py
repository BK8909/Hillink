"""고객 에이전트 행동 엔진 — 프로필 특성 + 이번 방문 + 운영 월드 → 결정 시점마다 새로 판단 (10/22 · 총괄 C · 격리 연구)

- 결정은 시점(체크인 뒤 15:30부터)마다 '지금 할 수 있는 선택지'를 모두 평가해 고른다. 고른 행동이 끝나면 다음 결정. 하루가 끝날 때까지 반복(연속 행동).
- 점수는 계산 항(term)의 합이고, 모든 항은 특성 수준 × 선택지 속성 × 역할 계수 로 만든다. 항마다 근거 fact_id 를 붙인다.
  → 이유 문장은 계산에 실제로 들어간 항에서만 만든다(사후 설명 금지). 사전 작성된 행동 · 정답은 입력에서 거부한다.
- 숫자는 효용 지표이지 확률 · 지불 의사 · 학습된 계수가 아니다. 계수는 모두 초기 가설이며 특정 고객 결과에 맞춰 조정하지 않았다.
- 좌석 · 대기 · 정원 경쟁은 모델링하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from .gists import gist
from .profile_adapter import MASS_FULL, SCOPE_TRANSFER
from .relevance import GRADE_WEIGHT
from .world import FOOD_LEVELS, apply_levers, assert_no_results, hm, mh, validate_visit, validate_world

VERSION = "operator_world_engine_v1"
# 공통 정책 스위치(3차 · 모든 고객에게 같은 규칙). 비교 실행은 POLICY 를 바꿔 같은 입력으로 다시 돌린다.
POLICY = dict(
    fact_share=True,     # 한 선택지 안에서 같은 원문 사실이 여러 성향 항에 쓰이면 그 사실의 질량을 쓰인 항 수로 나눔(사실 하나 = 한 몫)
    lookahead=True,      # 지금 선택 + 그 뒤 바로 이어질 최선의 선택(한 단계)까지 함께 비교 — '이 저녁을 어떻게 보낼까'를 공정하게
    meal_lead_min=60,    # 식사 선택지는 시작 60분 전부터 후보(기다리는 시간은 비용으로 계산) — 행사 결정 시점에 저녁 대안이 빠지지 않게
    lookahead_depth=2,   # 4차 연구 정책: 다음 계획을 고를 때도 같은 방식으로 몇 단계 내다볼지(1 = 다음 계획은 그 시점 점수만 · 2 = 다음 계획도 한 단계 더)
)
LOOKAHEAD_W = 1.0       # 가정 — 다음 한 단계 가치의 반영 비율
_SHARE: dict = {}       # score 계산 중 사실별 질량 배수(정책 fact_share)

W = dict(novelty=2.0, food=3.0, food_specific=1.5, premium=1.0, space=1.5, warm=1.5, swim=2.0, rest=2.0, benefit=1.5,
         familiar=0.8, appraisal=1.0, practical=0.8, alcohol=1.5, alcohol_familiar=1.2, cost=2.0, value=1.5, meal=3.0, breakfast=0.8, time=0.2)
COST_ATTENTION = 0.5          # 공통 상황 판단(개인 성향 아님) — 5만 원당 W.cost × 0.5 = 1.0
COST_UNIT = 50000
HUNGER_DONE = 0.3             # 남은 끼니가 이보다 작으면 식당 · 객실 식사 · 간단 식사는 후보에서 빠짐(이미 먹음)
WAIT_LEAD_MIN = 30            # 시작까지 30분 이내면 기다렸다가 시작(공통 규칙 R-W1 과 같은 값 · 가정)
VALUE_PRICE_PER_CONTENT = 120000   # 가정 — 내용 지수 1.0 의 1인 기준 가격
QUALITY_MULT = {"none": 0.0, "standard": 1.0, "chef_collab": 1.15}
CONSIDER_MARGIN = 0.6         # 1·2위 차이가 이보다 작고 행사 메뉴가 미공개면 '입장 전 안내 확인'
INTEREST_MARGIN = 1.0         # 행사가 2위 안에서 이 차이 안이면 '관심은 있었음'
REST_PURPOSE_THRESHOLD = 0.7  # 가정 — 이 이상이면 '휴식이 목적인 방문'
FATIGUE_PER_HOUR = 0.12       # 가정 — 체크인 뒤 시간이 갈수록 휴식 가치 상승
POLICY_NOTES = [
    "계수(W)는 초기 가설 · 특정 고객 · 조건의 결과에 맞춰 조정하지 않음",
    "비용 항은 공통 상황 판단(0.5)이며 개인 가격 회피 성향이 아님 · 구매 전 가치 비교 특성은 '내용 대비 가격 초과분'에만 작용",
    "이용 후 가격 가치 평가는 같은 업장 재선택에만 작용",
    "'관심' · '입장 전 안내 확인' · '참여 의향' · '참여하지 않음'은 행동 단계이며 예약 성공 · 실제 이용을 뜻하지 않음",
]


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _term(factor, value, facet=None, fact_ids=(), note="", kind="profile", evidence=None):
    return dict(factor=factor, value=round(value, 4), facet=facet, fact_ids=list(fact_ids), note=note, kind=kind, evidence=list(evidence or []))


def out_of_pocket(o: dict) -> float:
    if o.get("in_package"):
        return 0.0
    return max(0.0, o["price_pp_krw"] - o["guest_discount_krw"] - o["card_benefit_krw"])


def benefit_amount(o: dict) -> float:
    return (o["price_pp_krw"] if o.get("in_package") else 0.0) + o["guest_discount_krw"] + o["card_benefit_krw"]


def feasible(o: dict, t: int, state: dict, visit: dict) -> list[str]:
    why = []
    if not o["available"]:
        why.append("운영하지 않음")
    start = t
    if o["window"]:
        s, e = hm(o["window"]["start"]), hm(o["window"]["end"])
        lead = POLICY["meal_lead_min"] if o["kind"] in ("restaurant", "room_meal", "simple_meal") else WAIT_LEAD_MIN
        if t < s - lead:
            why.append(f"아직 시작 전({o['window']['start']})")
        start = max(t, s)
        if start + o["duration_min"] > e:
            why.append(f"운영 종료({o['window']['end']}) 전에 끝낼 수 없음")
    if start + o["duration_min"] > hm(visit["end"]):
        why.append("하루 종료 시각 넘김")
    if o["id"] in state["used"] and not o.get("repeatable"):
        why.append("오늘 이미 이용")
    if o["alcohol"]["required"] and not visit["alcohol_eligible"] and not o["alcohol"]["nonalcoholic_alt"]:
        why.append("주류 행사 · 음주 불가 동행")
    if o["kind"] in ("restaurant", "room_meal", "simple_meal") and state["hunger"] < HUNGER_DONE:
        why.append("오늘 저녁을 이미 먹음")
    return why


def ev(traits: dict, facet: str, wanted=()) -> tuple[float, list[str], list[dict]]:
    """선택지 속성(wanted)과 맞는 근거만 골라 수준을 계산. wanted 는 태그 목록 또는 {태그: 가중치}.
    태그가 없는 근거는 성향 전체에 해당(가중치 1). 제외(X) 근거는 들어가지 않는다. 반환: (수준, fact_ids, 근거[{fact_id, gist, weight}])."""
    x = traits["facets"][facet]
    wmap = dict(wanted) if isinstance(wanted, dict) else {k: 1.0 for k in wanted}
    matched = []
    for e in x["evidence"]:
        if e["grade"] == "exclude":
            continue
        if not wmap or not e["tags"]:
            wt = 1.0
        else:
            hits = [wmap[t] for t in e["tags"] if t in wmap]
            if not hits:
                continue
            wt = max(hits)
        matched.append((e, wt))
    if not matched:
        return 0.0, [], []
    eff = {id(e): e["mass"] * GRADE_WEIGHT[e["grade"]] * wt * _SHARE.get(e["fact_id"], 1.0) for e, wt in matched}
    mass = sum(eff.values())
    level = min(1.0, mass / MASS_FULL) * SCOPE_TRANSFER
    matched.sort(key=lambda ew: (ew[0]["grade"] != "rep", -eff[id(ew[0])]))
    return round(level, 4), [e["fact_id"] for e, _ in matched], [dict(fact_id=e["fact_id"], gist=e["gist"], weight=wt, grade=e["grade"],
                                                                  share=round(_SHARE.get(e["fact_id"], 1.0), 4), mass_eff=round(eff[id(e)], 4)) for e, wt in matched]


def score(o: dict, t: int, state: dict, visit: dict, traits: dict, world: dict) -> list[dict]:
    """공통 정책 fact_share: 1차 계산에서 같은 사실이 몇 개 성향 항에 쓰였는지 세고, 2차 계산에서 사실 질량을 그 수로 나눈다."""
    global _SHARE
    _SHARE = {}
    terms = _score(o, t, state, visit, traits, world)
    if not POLICY["fact_share"]:
        return terms
    if traits.get("evidence_granularity") != "fact":
        # 근거 ID 가 '글' 단위(수동 파일럿)면 같은 글의 서로 다른 사실을 구별할 수 없어 중복 판정을 하지 않는다(사실 단위 입력이 오면 자동 적용)
        return terms
    count = {}
    for x in terms:
        if x["facet"] and x["kind"] != "context":
            for f in set(x["fact_ids"]):
                count[f] = count.get(f, 0) + 1
    shared = {f: 1.0 / n for f, n in count.items() if n > 1}
    if not shared:
        return terms
    _SHARE = shared
    try:
        terms = _score(o, t, state, visit, traits, world)
    finally:
        _SHARE = {}
    for x in terms:
        k = [f for f in x["fact_ids"] if f in shared]
        if k:
            x["shared_facts"] = {f: round(shared[f], 4) for f in k}
    return terms


def _score(o: dict, t: int, state: dict, visit: dict, traits: dict, world: dict) -> list[dict]:
    F = traits["facets"]
    terms = []
    food = o["food"]; sp = o["space"]; al = o["alcohol"]
    q = QUALITY_MULT[food["quality"]]
    is_event = o["kind"] == "event"

    # 새 경험 · 시즌 · 홍보 — 선택지 종류에 맞는 근거만(행사 ↔ event · limited_goods · new_place · new_food / 상품 쇼핑은 제외)
    if o["novelty"] > 0:
        want = {"event": 1.0, "limited_goods": 1.0, "new_place": 0.5, "new_food": 0.5} if is_event else {"new_place": 1.0, "event": 0.5}
        lv, f, g = ev(traits, "novelty", want)
        if lv:
            terms.append(_term("새 경험 시도", W["novelty"] * o["novelty"] * 0.6 * lv, "novelty", f, "시즌 한정 · 처음 보는 행사", evidence=g))
        if o["seasonal"]:
            lv, f, g = ev(traits, "seasonal", {"event": 1.0, "limited_goods": 1.0, "seasonal_food": 0.5})
            if lv:
                terms.append(_term("시즌 행사 · 한정 반응", W["novelty"] * o["novelty"] * 0.4 * lv, "seasonal", f, evidence=g))
        if o["promoted"]:
            lv, f, g = ev(traits, "promo", ["promo"])
            if lv:
                terms.append(_term("홍보를 보고 움직임", W["novelty"] * o["novelty"] * 0.3 * lv, "promo", f, evidence=g))
    # 음식
    snack = 1.0      # 음식에 기대는 가치(음식 경험 · 메뉴 기호 · 셰프 코스)의 반영 비율 — 이미 저녁을 먹었으면 작아짐
    if food["meal_fraction"] > 0 and q > 0:
        # 3차 공통 규칙: 음식 경험은 '남은 배고픔'만큼만 온전히 — 이미 일부 먹었으면 나머지는 간식 수준(0.3). 두 끼를 연달아 먹어 음식 경험이 두 번 온전히 쌓이는 문제 방지
        h0 = state["hunger"]
        # 5차: 남은 배고픔을 넘는 부분은 보상하지 않음(나눠 먹을 때 초과분 0.3을 또 주던 중복 제거) · 이미 배부르면 간식 수준(한 접시의 0.3)만
        portion = max(min(h0, food["meal_fraction"]), 0.3 * food["meal_fraction"])
        snack = portion / food["meal_fraction"]
        # 3차 공통 규칙(선택지 쪽 관련성): 근거 태그는 그 선택지가 실제로 제공하는 음식 경험과 맞을 때만 들어간다.
        # 객실 식사(룸서비스 · 배달)는 '메뉴 탐색 · 코스 · 시그니처' 경험이 아니므로 음식 성향 근거를 받지 않고(기본 한 끼 가치만), 개인 근거는 '실용적 식사 대안' 항으로만 들어간다.
        # 간단 식사(베이커리)는 디저트 · 베이커리 근거만, 시그니처는 약하게.
        if is_event:
            want = {"course": 1.0, "menu_explore": 1.0, "new_food": 0.5}
        elif o["kind"] == "restaurant":
            # 4차 공통 규칙: 식당마다 실제로 제공하는 음식 경험의 근거만 — 뷔페 탐색 근거는 뷔페에, 코스 근거는 코스(3단 이상)에.
            # 모든 식당에 같은 근거를 똑같이 주면 고객의 음식 경험이 식당을 구별하지 못하고 가격 · 공간 속성만 남는다(3차 피자힐 편중 원인 중 하나).
            mt = set(food["menu_tags"])
            want = {"menu_explore": 0.5}
            if mt & {"buffet", "variety"}:
                want.update(buffet=1.0, menu_explore=1.0)
            if food["courses"] >= 3:
                want["course"] = 1.0
        else:
            want = {"dessert": 1.0, "signature": 0.5}
        if o["kind"] == "room_meal":
            lv, f, g = 0.0, [], []      # 객실 식사: 음식 성향 근거 없음(기본 한 끼 가치만)
        else:
            lv, f, g = ev(traits, "food", want)
        terms.append(_term("음식 경험" if snack == 1.0 else "간식 · 디저트", W["food"] * food["meal_fraction"] * q * (0.4 + 0.6 * lv) * snack, "food", f,
                           f"한 끼 충족 {food['meal_fraction']:.0%} · 코스 {food['courses']} · 품질 {food['quality']}", kind="profile_and_offer", evidence=g))
        if food["menu_known"]:
            match, mfacts, mnotes = 0.0, [], []
            for m in traits["menu"]:
                hit = [tg for tg in m["tags"] if tg in food["menu_tags"]]
                if hit:
                    match += m["weight"] * min(1.0, len(hit) / 2)
                    mfacts += m["fact_ids"]; mnotes.append(f"{m['gist']}({','.join(hit)})")
            if match:
                lv, _, _ = ev(traits, "food_specific")
                # 4차 공통 규칙: 메뉴 기호도 '먹을 수 있는 만큼'만 — 이미 저녁을 먹은 뒤의 코스는 기호가 맞아도 덜 매력적(끼니 상태 반영)
                terms.append(_term("구체적 메뉴 기호 일치" if match > 0 else "피하는 메뉴 포함", W["food_specific"] * match * (0.5 + 0.5 * lv) * (snack if match > 0 else 1.0),
                                   "food_specific", mfacts, " · ".join(mnotes) + ("" if snack == 1.0 else f" · 이미 먹어서 {snack:.0%}만 반영")))
        elif is_event:
            terms.append(_term("메뉴 미공개", 0.0, None, (), "메뉴가 공개되지 않아 기호 일치를 계산할 수 없음(불확실)", kind="uncertainty"))
    if food["quality"] == "chef_collab":
        lv, f, g = ev(traits, "premium", ["chef", "course"])
        # 4차: 셰프를 만나는 체험(0.3)은 끼니와 무관, 프리미엄 음식 가치(0.7 × 근거)는 남은 끼니만큼
        terms.append(_term("셰프 콜라보 · 프리미엄 식음", W["premium"] * (0.3 + 0.7 * lv * snack), "premium", f,
                           "" if snack == 1.0 else f"이미 먹어서 음식 가치는 {snack:.0%}만", evidence=g))
    # 공간 — 선택지의 공간 속성(야경 / 정원)과 맞는 근거만
    # 5차 공통 규칙: 야경은 활동이 일몰 뒤까지 이어질 때만(공식 2부 15:30 시작 행사가 17:30에 끝나면 야경 없음)
    ts0 = max(t, hm(o["window"]["start"])) if o["window"] else t
    sp = dict(sp, night_view=bool(sp["night_view"] and ts0 + o["duration_min"] > hm(world.get("sunset", "18:00"))))
    if sp["night_view"] or sp["garden"]:
        want = {}
        if sp["night_view"]:
            want.update({"night_view": 1.0, "view_seat": 0.7, "ambience": 0.7, "decor": 0.5})
        if sp["garden"]:
            want.update({"garden": 1.0, "ambience": max(want.get("ambience", 0), 0.7)})
        lv, f, g = ev(traits, "space", want)
        label = "야경 · 공간 경험" if sp["night_view"] and not sp["garden"] else ("정원 · 산책 경험" if sp["garden"] and not sp["night_view"] else "야경 · 정원 · 공간 경험")
        terms.append(_term(label, W["space"] * (0.3 + 0.7 * lv), "space", f, evidence=g))
    if sp["warm_water"]:
        lv, f, g = ev(traits, "warm_rest", {"footbath": 1.0, "warm_pool": 0.5} if o["venue"] == "SKYARD" else {"warm_pool": 1.0, "footbath": 0.5})
        terms.append(_term("온수 · 족욕 휴식", W["warm"] * (0.2 + 0.8 * lv), "warm_rest", f, evidence=g))
    if sp["swimming"]:
        lv, f, g = ev(traits, "swim_aversion")
        if lv:
            terms.append(_term("수영 비선호", -W["swim"] * lv, "swim_aversion", f, "물놀이 자체를 피함(원문)", evidence=g))
    # 휴식
    if o["rest_value"] > 0:
        fatigue = FATIGUE_PER_HOUR * max(0, (t - hm(visit["checkin"])) / 60)
        lv, f, g = ev(traits, "rest_need", ["rest"])
        if F["rest_need"].get("conditional_on") and visit["rest_goal"] < REST_PURPOSE_THRESHOLD:
            lv *= 0.5          # '휴식이 목적일 때' 조건부 성향 — 이번 방문 목적이 휴식이 아니면 절반만(가정)
        terms.append(_term("휴식 · 회복", W["rest"] * o["rest_value"] * (visit["rest_goal"] * (0.4 + 0.9 * lv) + fatigue), "rest_need", f,
                           f"이번 방문 휴식 목표 {visit['rest_goal']} · 체크인 뒤 {(t - hm(visit['checkin'])) / 60:.1f}시간", kind="profile_and_context", evidence=g))
    # 혜택 — 혜택 종류와 맞는 근거만
    b = benefit_amount(o)
    if b > 0:
        want = (["package", "voucher"] if o.get("in_package") else []) + (["discount"] if o["guest_discount_krw"] else []) + (["card"] if o["card_benefit_krw"] else [])
        lv, f, g = ev(traits, "benefit", want)
        terms.append(_term("혜택 · 할인 활용", W["benefit"] * min(1.0, b / 50000) * (0.3 + 0.7 * lv), "benefit", f,
                           f"1인 {b:,.0f}원 혜택" + (" · 객실 패키지 포함" if o.get("in_package") else ""), evidence=g))
    # 같은 시설 · 업장 실제 이용 경험
    for v in traits["venues"].get(o["venue"], []):
        if v["kind"] == "used":
            lv, _, _ = ev(traits, "routine", ["repeat"])
            if lv:
                terms.append(_term("익숙한 곳 · 실제 이용 경험", W["familiar"] * 0.5 * lv, "routine", v["fact_ids"], v["gist"]))
            lvn, _, _ = ev(traits, "novelty", ["new_place"])
            if lvn and o["novelty"] == 0:
                terms.append(_term("이미 경험한 곳(새로움 낮음)", -W["familiar"] * 0.25 * lvn, "novelty", v["fact_ids"], v["gist"]))
        elif v["kind"] == "appraisal":
            lv, _, _ = ev(traits, "post_appraisal")
            terms.append(_term("이용 후 가격 가치 유보(같은 업장)", -W["appraisal"] * (0.5 + 0.5 * lv), "post_appraisal", v["fact_ids"], v["gist"]))
        elif v["kind"] == "avoid_swim" and sp["swimming"]:
            terms.append(_term("수영장에 가도 수영은 안 함", -W["swim"] * 0.3, "swim_aversion", v["fact_ids"], v["gist"]))
    if o["kind"] == "room_meal":
        lv, f, g = ev(traits, "practical_alt", {"room_meal": 1.0, "alt_meal": 0.5})
        if lv:
            terms.append(_term("실용적 식사 대안(객실에서 먹기)", W["practical"] * lv, "practical_alt", f, evidence=g))
    # 주류
    if al["required"]:
        if al["tasting"]:
            lv, f, g = ev(traits, "alcohol_familiar", {"wine": 1.0, "bar": 0.5})
            if lv:
                terms.append(_term("와인 · 주류를 즐긴 경험(행사와 직접 관련)", W["alcohol_familiar"] * lv, "alcohol_familiar", f, evidence=g))
        lv, f, g = ev(traits, "alcohol_limit")
        if lv:
            mult = 0.3 if al["nonalcoholic_alt"] else 1.0
            terms.append(_term("음주량 부담" + (" · 무알코올 대안 있음" if al["nonalcoholic_alt"] else ""), -W["alcohol"] * lv * mult, "alcohol_limit", f, evidence=g))
    # 비용 · 가치
    pp = out_of_pocket(o)
    if pp > 0:
        terms.append(_term("1인 지불액", -W["cost"] * COST_ATTENTION * pp / COST_UNIT, None, (), f"{pp:,.0f}원(공통 상황 판단 · 개인 성향 아님)", kind="context"))
        content = 0.6 * food["meal_fraction"] * q + 0.3 * o["novelty"] + 0.2 * (1 if (sp["night_view"] or sp["garden"]) else 0)
        expected = content * VALUE_PRICE_PER_CONTENT
        lv, f, g = ev(traits, "value_check")
        if pp > expected and lv:
            terms.append(_term("구매 전 가치 비교(내용 대비 가격 초과)", -W["value"] * lv * (pp - expected) / 100000, "value_check", f,
                               f"내용 지수 {content:.2f} → 기준 {expected:,.0f}원 < 지불 {pp:,.0f}원", evidence=g))
    elif o.get("in_package"):
        terms.append(_term("패키지에 포함(추가 지불 없음)", 0.0, None, (), "패키지 가격 자체는 이 비교의 범위 밖", kind="context"))
    # 끼니
    dw = world["dinner_window"]; md = world["main_dinner"]
    h = state["hunger"]
    ts = max(t, hm(o["window"]["start"])) if o["window"] else t      # 실제 시작 시각
    te = ts + o["duration_min"]
    # 5차 공통 규칙: 저녁 시간대에 '끝나는' 식사도 이른 저녁으로 인정(예: 15:30~17:30 페어링 코스) — 공식 2부 15:30 시작 행사 대응
    if hm(dw["start"]) < te and ts < hm(dw["end"]) and h > 0:
        if food["meal_fraction"] > 0:
            terms.append(_term("저녁 끼니 해결", W["meal"] * min(h, food["meal_fraction"]), None, (), f"남은 끼니 {h:.0%} 중 {min(h, food['meal_fraction']):.0%} 해결", kind="context"))
        elif hm(md["start"]) <= ts < hm(md["end"]) and h >= 0.7:
            terms.append(_term("저녁을 미룸", -W["meal"] * 0.5 * h, None, (), "저녁 시간대에 식사가 아닌 선택", kind="context"))
    # 시간 · 조식
    if o["window"] and t < hm(o["window"]["start"]):
        wait = hm(o["window"]["start"]) - t
        terms.append(_term("시작까지 기다림", -W["time"] * wait / 30, None, (), f"{wait}분 뒤 시작", kind="context"))
    if o["duration_min"] > 120:
        terms.append(_term("긴 소요 시간", -W["time"] * (o["duration_min"] - 120) / 30, None, (), kind="context"))
    if t >= hm("21:30") and o["duration_min"] > 60:
        lv, f, g = ev(traits, "breakfast_priority")
        if lv:
            terms.append(_term("내일 조식을 위해 일찍 마무리", -W["breakfast"] * lv, "breakfast_priority", f, evidence=g))
    return terms


def decide_at(t: int, state: dict, visit: dict, traits: dict, world: dict) -> dict:
    cands = []
    end = hm(visit["end"])
    offers = []
    for o in world["offers"]:
        if o["kind"] == "rest" and t + o["duration_min"] > end:
            o = dict(o, duration_min=max(15, end - t))      # 남은 시간만큼 쉼
        offers.append(o)
    world = dict(world, offers=offers)
    # 5차 공통 규칙(공식): 포레스트 파크에서 행사가 열리는 날에는 포레스트 파크 일반 이용이 제한됨 → 산책 불가
    forest_event = any(x["kind"] == "event" and x["venue"] == "FOREST" and x["available"] for x in world["offers"])
    for o in world["offers"]:
        blocked = feasible(o, t, state, visit)
        if forest_event and o["kind"] != "event" and o["venue"] == "FOREST":
            blocked = blocked + ["행사 날 포레스트 파크 일반 이용 제한(공식 공지)"]
        if blocked:
            cands.append(dict(offer=o["id"], label=o["label"], kind=o["kind"], feasible=False, blocked=blocked, score=None, terms=[]))
            continue
        terms = score(o, t, state, visit, traits, world)
        cands.append(dict(offer=o["id"], label=o["label"], kind=o["kind"], feasible=True, blocked=[], score=round(sum(x["value"] for x in terms), 4), terms=terms))
    ok = [c for c in cands if c["feasible"]]
    for c in ok:
        c["total"] = c["score"]
        c["next"] = None
    depth = state.get("_depth", 0)
    if POLICY["lookahead"] and depth < POLICY["lookahead_depth"]:
        by = {o["id"]: o for o in world["offers"]}
        for c in ok:
            o = by[c["offer"]]
            st = max(t, hm(o["window"]["start"])) if o["window"] else t
            t2 = st + o["duration_min"]
            if t2 >= end:
                continue
            s2 = dict(used=set(state["used"]) | {o["id"]}, hunger=state["hunger"], _depth=depth + 1)
            if o["food"]["meal_fraction"] > 0 and st < hm(world["dinner_window"]["end"]):     # 5차: 저녁 전에 먹은 음식도 저녁 배고픔을 줄임
                s2["hunger"] = max(0.0, round(s2["hunger"] - o["food"]["meal_fraction"], 4))
            nxt = decide_at(t2, s2, visit, traits, dict(world, offers=[x for x in world["offers"]]))
            c["next"] = dict(offer=nxt["chosen"], label=nxt["label"], score=nxt["score"], time=nxt["starts"])
            c["total"] = round(c["score"] + LOOKAHEAD_W * nxt["score"], 4)
    ok.sort(key=lambda c: (-c["total"], c["kind"] != "rest", c["offer"]))
    top = ok[0]; second = ok[1] if len(ok) > 1 else None
    margin = round(top["total"] - second["total"], 4) if second else None
    offer = next(o for o in world["offers"] if o["id"] == top["offer"])
    stage = "선택"
    if offer["kind"] == "event":
        unknown = any(x["kind"] == "uncertainty" for x in top["terms"])
        stage = CHECK_STAGE if (margin is not None and margin < CONSIDER_MARGIN and unknown and not offer.get("_checked")) else "참여 의향"
    event_view = []
    for c in cands:
        if c["kind"] == "event" and c["offer"] != top["offer"]:
            if not c["feasible"]:
                event_view.append(dict(offer=c["offer"], stage="참여 불가", why=c["blocked"]))
            elif top["total"] - c["total"] <= INTEREST_MARGIN:
                event_view.append(dict(offer=c["offer"], stage="관심은 있었으나 다른 선택", gap=round(top["total"] - c["total"], 3)))
            else:
                event_view.append(dict(offer=c["offer"], stage="관심 낮음 · 참여하지 않음", gap=round(top["total"] - c["total"], 3)))
    return dict(time=mh(t), chosen=top["offer"], label=top["label"], kind=offer["kind"], stage=stage, score=top["score"], total=top["total"],
                next_plan=top["next"], runner_up_next=(second["next"] if second else None),
                margin=margin, runner_up=(second["offer"] if second else None), terms=top["terms"],
                reasons=reasons_from_terms(top["terms"], traits),
                rejected=[dict(offer=c["offer"], label=c["label"], feasible=c["feasible"], score=c["score"], total=c.get("total"),
                               next=c.get("next"), major_reason=major_reason(c, top)) for c in cands if c["offer"] != top["offer"]],
                event_stages=event_view, starts=mh(max(t, hm(offer["window"]["start"])) if offer["window"] else t),
                ends=mh((max(t, hm(offer["window"]["start"])) if offer["window"] else t) + offer["duration_min"]), out_of_pocket_pp=out_of_pocket(offer),
                food_fraction=offer["food"]["meal_fraction"])


def major_reason(c: dict, top: dict) -> str:
    if not c["feasible"]:
        return " · ".join(c["blocked"])
    # 1위와 비교해 가장 크게 뒤진 항
    mine = {x["factor"]: x["value"] for x in c["terms"]}
    theirs = {x["factor"]: x["value"] for x in top["terms"]}
    keys = set(mine) | set(theirs)
    worst = sorted(keys, key=lambda k: mine.get(k, 0.0) - theirs.get(k, 0.0))
    k = worst[0] if worst else None
    if k is None:
        return "차이 없음"
    d = mine.get(k, 0.0) - theirs.get(k, 0.0)
    out = f"{k}에서 {d:+.2f}"
    if c.get("next") and top.get("next") and c["next"]["offer"] != top["next"]["offer"]:
        out += f" · 다음 계획 {c['next']['label']}({c['next']['score']:+.2f}) vs {top['next']['label']}({top['next']['score']:+.2f})"
    return out


def reasons_from_terms(terms: list[dict], traits: dict) -> list[dict]:
    out = []
    for x in sorted(terms, key=lambda x: -abs(x["value"])):
        if x["kind"] == "uncertainty":
            out.append(dict(text=x["note"], value=0.0, evidence=[], layer="불확실"))
            continue
        if x.get("evidence"):
            seen, ev = set(), []
            for e in x["evidence"]:
                if e["gist"] in seen:
                    continue
                seen.add(e["gist"]); ev.append(dict(fact_id=e["fact_id"], gist=e["gist"], grade=e.get("grade"), weight=e.get("weight")))
            ev = ev[:4]
        else:
            ev = [dict(fact_id=f, gist=traits["evidence_index"].get(f, {}).get("gist", "")) for f in x["fact_ids"][:4]]
        layer = {"profile": "원문 경험(프로필)", "profile_and_offer": "프로필 × 운영 조건", "profile_and_context": "프로필 × 이번 방문", "context": "현재 조건"}.get(x["kind"], x["kind"])
        out.append(dict(text=x["factor"] + (f" — {x['note']}" if x["note"] else ""), value=x["value"], evidence=ev, n_evidence=len(x["fact_ids"]), layer=layer, facet=x["facet"]))
    return out


BROWSE_MIN = 15      # 가정(가상 행동) — 입장 전 안내를 확인하는 시간(입장 전 · 비용 없음)
CHECK_STAGE = "입장 전 안내 확인"
ATTEND_STAGES = ("참여 의향", "안내 확인 뒤 참여")
CHECKED_STAGES = ("안내 확인 뒤 참여", "안내 확인 뒤 다른 선택")


def _browse_step(d: dict, o: dict, t: int) -> tuple[dict, bool]:
    """'입장 전 안내 확인'(가상 행동) — 메뉴가 공개되지 않았고 1 · 2위 차이가 작을 때, 입장권을 사기 전에 안내를 확인한다.
    5차 정보 규칙: 확인으로 새로 알 수 있는 것은 '현장에서 실제로 공개된 정보'뿐이다.
      - 공식 공개 정보(규모 · 가격 · 입장권 포함물)는 이미 판단에 들어가 있다.
      - 메뉴는 현장 메뉴 게시 근거가 없으므로(onsite_menu_board=False) 새로 알 수 없다 → 같은 정보로 다시 판단.
      - 운영자가 '현장 메뉴 게시'를 켜면(가상 조건) 그때만 메뉴가 공개된다.
    반환: (확인 단계, 메뉴를 새로 알게 됐는지)"""
    st = max(t, hm(o["window"]["start"])) if o["window"] else t
    revealed = bool(o.get("onsite_menu_board"))
    info = ("운영자 설정(가상 조건): 행사장 입구에 메뉴 게시 → 메뉴를 확인하고 다시 판단" if revealed else
            "현장에서 새로 확인할 수 있는 정보 없음(현장 메뉴 게시 근거 없음 · 공식 공개 정보는 이미 반영) → 같은 정보로 다시 판단")
    b = dict(d)
    b["_plan_next"] = d.get("next_plan")
    b.update(action="browse", label=f"{o['label']} — 입장 전 안내 확인(가상 행동)", starts=mh(st), ends=mh(st + BROWSE_MIN),
             out_of_pocket_pp=0.0, food_fraction=0.0, next_plan=None, info_revealed=("menu" if revealed else None),
             browse_note=f"메뉴 미공개 · 1 · 2위 차이가 작아 입장권을 사기 전에 안내 확인(가상 행동 · {BROWSE_MIN}분 가정) · {info}")
    return b, revealed


def _note_plan_change(steps: list[dict], d: dict) -> None:
    """앞 단계에서 세운 '다음 계획'과 지금 실제 선택이 다르면 그 이유를 계산 결과에서 적는다(재판단 설명)."""
    if not steps or not steps[-1].get("next_plan"):
        return
    plan = steps[-1]["next_plan"]
    if plan["offer"] == d["chosen"] and d.get("action") != "browse":
        d["plan_change"] = None
        return
    if d.get("action") == "browse" and plan["offer"] == d["chosen"]:
        why = "계획대로 행사로 이동했지만, 메뉴가 공개되지 않았고 1 · 2위 차이가 작아 입장권을 사기 전에 안내부터 확인함(가상 행동)"
    elif d.get("action") == "browse":
        # 5차: 목적지 자체가 바뀐 경우 — 계획한 선택지와 지금 선택(행사)의 합계를 비교해 설명
        c = next((r for r in d["rejected"] if r["offer"] == plan["offer"]), None)
        nxt = d.get("_plan_next")
        head = f"계획했던 {plan['label']} 대신 행사 쪽으로 바꿈 — "
        if c is None:
            why = head + "계획한 선택지가 이 시각의 후보에 없음"
        elif not c["feasible"]:
            why = head + f"계획한 선택지는 지금 불가: {c['major_reason']}"
        else:
            why = (head + f"다시 판단하니 행사(지금 {d['score']:+.2f}" + (f" + 다음 {nxt['label']} {nxt['score']:+.2f}" if nxt else "") +
                   f" = {d['total']:+.2f})이 계획한 {c['label']}(합계 {c['total']:+.2f})보다 큼 · 다만 메뉴 미공개 · 차이가 작아 입장권을 사기 전에 안내부터 확인(가상 행동)")
    else:
        c = next((r for r in d["rejected"] if r["offer"] == plan["offer"]), None)
        if c is None:
            why = "계획한 선택지가 이 시각의 후보에 없음"
        elif not c["feasible"]:
            why = f"계획한 {c['label']}은(는) 지금 불가: {c['major_reason']}"
        else:
            nxt = d.get("next_plan")
            why = (f"다시 판단하니 {d['label']}(지금 {d['score']:+.2f}" + (f" + 다음 {nxt['label']} {nxt['score']:+.2f}" if nxt else "") +
                   f" = {d['total']:+.2f})이 계획한 {c['label']}(합계 {c['total']:+.2f})보다 큼")
    d["plan_change"] = dict(planned=plan["offer"], planned_label=plan["label"], why=why)


def simulate_day(traits: dict, visit: dict, world: dict) -> dict:
    validate_world(world); validate_visit(visit); assert_no_results(traits.get("facets", {}), "traits")
    t = hm(visit["checkin"]); end = hm(visit["end"])
    state = dict(used=set(), hunger=1.0)
    steps = []
    world_sha = sha(world)
    world = deepcopy(world)     # 들러본 뒤 '메뉴 공개' 상태는 이 고객의 하루 안에서만
    while t < end:
        d = decide_at(t, state, visit, traits, world)
        if d["kind"] == "event" and d["stage"] == CHECK_STAGE:
            o = next(x for x in world["offers"] if x["id"] == d["chosen"])
            b, revealed = _browse_step(d, o, t)
            b["hunger_after"] = state["hunger"]
            _note_plan_change(steps, b)
            b.pop("_plan_next", None)
            steps.append(b)
            o["_checked"] = True                     # 같은 행사의 안내를 두 번 확인하지 않음
            if revealed:
                o["food"]["menu_known"] = True       # 현장 메뉴 게시(가상 조건)일 때만 메뉴 공개
            t = hm(b["ends"])
            continue
        d["action"] = "attend" if d["kind"] == "event" else "do"
        _note_plan_change(steps, d)
        steps.append(d)
        state["used"].add(d["chosen"])
        if d["food_fraction"] > 0 and hm(d["starts"]) < hm(world["dinner_window"]["end"]):      # 5차: 저녁 전 음식도 저녁 배고픔을 줄임
            state["hunger"] = max(0.0, round(state["hunger"] - d["food_fraction"], 4))
        d["hunger_after"] = state["hunger"]
        t = hm(d["ends"])
    total = sum(s["out_of_pocket_pp"] for s in steps) * visit["party_size"]
    return dict(version=VERSION, persona_id=visit["persona_id"], traits_sha=sha(traits["facets"]), world_sha=world_sha, visit_sha=sha(visit),
                steps=steps, party_total_out_of_pocket_krw=total, events=event_summary(steps, world), policy_notes=POLICY_NOTES,
                model_calls=0, human_review="pending", demo_approved=False)


def event_summary(steps: list[dict], world: dict) -> list[dict]:
    out = []
    for o in world["offers"]:
        if o["kind"] != "event":
            continue
        browsed = next((s for s in steps if s["chosen"] == o["id"] and s.get("action") == "browse"), None)
        chosen = next((s for s in steps if s["chosen"] == o["id"] and s.get("action") != "browse"), None)
        if chosen:
            stage = "안내 확인 뒤 참여" if browsed else chosen["stage"]
            out.append(dict(event=o["id"], label=o["label"], stage=stage, time=chosen["starts"], score=chosen["score"], margin=chosen["margin"],
                            browsed_at=browsed["starts"] if browsed else None))
            continue
        if browsed:
            out.append(dict(event=o["id"], label=o["label"], stage="안내 확인 뒤 다른 선택", browsed_at=browsed["starts"],
                            why="안내를 확인한 뒤 다시 판단해 다른 일정을 고름(입장권 미구매)"))
            continue
        views = [v for s in steps for v in s["event_stages"] if v["offer"] == o["id"]]
        feasible_views = [v for v in views if v["stage"] != "참여 불가"]
        if feasible_views:
            best = min(feasible_views, key=lambda v: v["gap"])
            out.append(dict(event=o["id"], label=o["label"], stage=best["stage"], gap=best["gap"]))
        elif views:
            out.append(dict(event=o["id"], label=o["label"], stage="참여 불가", why=views[0].get("why")))
        else:
            out.append(dict(event=o["id"], label=o["label"], stage="후보로 올라오지 않음"))
    return out


# --------------------------------------------------------------------------- 운영자가 바꿔볼 조건(반전 조건)

LEVER_SCAN = [
    ("price_pp_krw", "가격", [0, 20000, 30000, 40000, 55000, 70000, 90000, 120000, 160000]),
    ("guest_discount_krw", "투숙객 할인", [0, 10000, 20000, 30000, 55000]),
    ("in_package", "객실 패키지 포함", [False, True]),
    ("food_level", "음식 구성", ["tasting_only", "light_bites", "pairing_course"]),
    ("quality", "셰프 콜라보", ["standard", "chef_collab"]),
    ("nonalcoholic_alt", "무알코올 대안", [False, True]),
]


def flip_conditions(traits: dict, visit: dict, world: dict, event_id: str, base: dict | None = None) -> list[dict]:
    """행사 하나에 대해 운영자 변수를 하나씩 바꿔 봤을 때 행사 참여 여부(단계)가 바뀌는 최소 변경을 찾는다. 계산 결과이지 작성된 서술이 아니다."""
    base = base or simulate_day(traits, visit, world)
    base_stage = next(e["stage"] for e in base["events"] if e["event"] == event_id)
    base_in = base_stage in ATTEND_STAGES
    o = next(x for x in world["offers"] if x["id"] == event_id)
    out = []
    for key, label, values in LEVER_SCAN:
        cur = o.get(key) if key in o else (o["food"].get(key) if key in o["food"] else o["alcohol"].get(key, o.get("food_level")))
        if key == "food_level":
            cur = o.get("food_level") or next((k for k, v in FOOD_LEVELS.items() if abs(v["meal_fraction"] - o["food"]["meal_fraction"]) < 1e-9), None)
        ordered = sorted(values, key=lambda v: abs(v - cur)) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else values
        for v in ordered:
            if v == cur:
                continue
            w2 = apply_levers(world, {event_id: {key: v}})
            r = simulate_day(traits, visit, w2)
            st = next(e["stage"] for e in r["events"] if e["event"] == event_id)
            now_in = st in ATTEND_STAGES
            if now_in != base_in:
                out.append(dict(lever=key, lever_label=label, from_value=cur, to_value=v, stage_from=base_stage, stage_to=st,
                                direction="참여로 바뀜" if now_in else "참여하지 않음으로 바뀜"))
                break   # 그 변수에서 첫 반전만(가장 작은 변경)
    return out


def compare(base: dict, changed: dict) -> dict:
    """같은 고객 · 조건 전후 비교. 시간 순서대로 짝을 맞춰 바뀐 행동과 바뀐 이유를 적는다."""
    a = {s["time"]: s for s in base["steps"]}; b = {s["time"]: s for s in changed["steps"]}
    times = sorted(set(a) | set(b), key=hm)
    rows = []
    for tm in times:
        sa, sb = a.get(tm), b.get(tm)
        if sa and sb:
            same = sa["chosen"] == sb["chosen"]
            rows.append(dict(time=tm, before=sa["chosen"], after=sb["chosen"], changed=not same,
                             stage_before=sa["stage"], stage_after=sb["stage"], reason_delta=term_delta(sa, sb)))
        else:
            rows.append(dict(time=tm, before=sa["chosen"] if sa else None, after=sb["chosen"] if sb else None, changed=True,
                             stage_before=sa["stage"] if sa else None, stage_after=sb["stage"] if sb else None, reason_delta=[]))
    ev = []
    for e1 in base["events"]:
        e2 = next(e for e in changed["events"] if e["event"] == e1["event"])
        ev.append(dict(event=e1["event"], before=e1["stage"], after=e2["stage"], changed=e1["stage"] != e2["stage"]))
    return dict(rows=rows, events=ev, cost_before=base["party_total_out_of_pocket_krw"], cost_after=changed["party_total_out_of_pocket_krw"],
                sequence_before=[s["chosen"] for s in base["steps"]], sequence_after=[s["chosen"] for s in changed["steps"]])


def term_delta(sa: dict, sb: dict) -> list[dict]:
    ta = {x["factor"]: x["value"] for x in sa["terms"]}; tb = {x["factor"]: x["value"] for x in sb["terms"]}
    out = []
    for k in sorted(set(ta) | set(tb), key=lambda k: -abs(tb.get(k, 0) - ta.get(k, 0))):
        d = round(tb.get(k, 0.0) - ta.get(k, 0.0), 4)
        if abs(d) > 1e-9:
            out.append(dict(factor=k, before=ta.get(k), after=tb.get(k), delta=d))
    return out[:6]


def run(persona_traits: dict, visit: dict, world: dict, levers: dict | None = None, event_id: str = "WINE_FAIR") -> dict:
    w = apply_levers(world, levers) if levers else deepcopy(world)
    day = simulate_day(persona_traits, visit, w)
    flips = flip_conditions(persona_traits, visit, w, event_id, day) if any(o["id"] == event_id for o in w["offers"]) else []
    return dict(day=day, flip_conditions=flips, levers=levers or {}, world=w)
