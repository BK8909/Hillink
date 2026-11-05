"""운영 월드 V1.1 후보(C-1 · C-2 · 내다보기 비교) — V1 엔진 파일과 V1.1 연구 확장(engine_ext)은 수정하지 않는다.

이 모듈은 문맥 관리자 안에서만 V1 의 점수 함수를 감싸 바꾼다. 계수 값(W)은 새로 만들지 않는다.

C-1 할인 · 포함 혜택 분리(통제안)
    V1:   혜택·할인 활용 = W.benefit × min(1, b/5만) × (0.3 + 0.7·lv)      b = 포함가 + 투숙객 할인 + 카드 혜택
    후보: 할인 반응      = W.benefit × min(1, 할인/5만) × 0.7·lv(할인 근거: discount · card 태그)
          포함 혜택 활용  = W.benefit × min(1, 포함가/5만) × 0.7·lv(포함 근거: package · voucher 태그)
    - 공통 기저 0.3 만 제거. 개인 기울기 0.7 은 유지(기울기 변경은 별도 가설 · 이 모듈에 없음)
    - 실지불액(공통 가격 항)은 그대로 — 할인은 가격 항에서 한 번만 공통으로 작동
    - 개인 근거가 없으면 두 항 모두 붙지 않음(미관측 = 공통 상품 효용으로만 행동)

C-2 업장 이력과 일반 성향 분리(기존 계수 유지안 · 두 변형)
    V1:   익숙한 곳 = W.familiar × 0.5 × lv(routine · 사람 전체 근거)
          가격 유보 = −W.appraisal × (0.5 + 0.5·lv(post_appraisal · 사람 전체 근거))
    후보: 같은 식 · 같은 계수. lv 를 '그 업장에 관한 사실'에서만 계산.
      "venue_facts"     : 성향 근거 중 그 업장 기록(fact_ids)에 속한 사실만
      "venue_visits"    : 익숙한 곳은 그 업장 실제 이용 기록(서로 다른 경험 단위)을 근거로 기존 수준 산식(질량 · 상한 · 범위 할인) 그대로 적용
    - 새 변환 규칙(횟수별 · 평가별 계수)은 없음
    - '이미 경험한 곳(새로움 낮음)' 항은 사람 성향(새 경험 추구) × 업장 속성(이미 경험)이라 바꾸지 않음(미해결로 기록)

내다보기(LOOKAHEAD) 비교
    V1: 다음 행동은 다음 시점의 '총점'(자체 + 그다음)으로 고르고, 앞 행동의 총점에는 그 다음 행동의 '자체 점수'만 더한다.
    "total": 다음 행동을 고른 기준과 같은 값(다음 행동의 총점)을 더한다 — 비교용 · 채택 아님
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack

from operator_choice.operator_world_v1 import engine as EN
from operator_choice.operator_world_v1 import profile_adapter as PA
from operator_choice.operator_world_v1_1.engine_ext import v11_engine

BENEFIT_LABEL = "혜택 · 할인 활용"
DEAL_LABEL = "할인 반응(개인 근거)"
PKG_LABEL = "포함 혜택 활용(개인 근거)"
FAMILIAR_LABEL = "익숙한 곳 · 실제 이용 경험"
APPRAISAL_LABEL = "이용 후 가격 가치 유보(같은 업장)"


def benefit_terms_c1(o: dict, traits: dict) -> list[dict]:
    """C-1 통제안: 할인 반응과 포함 혜택을 다른 항으로 · 공통 기저 없음 · 개인 기울기 0.7 유지."""
    out = []
    deal = (o["guest_discount_krw"] or 0) + (o["card_benefit_krw"] or 0)
    if deal > 0:
        want = (["discount"] if o["guest_discount_krw"] else []) + (["card"] if o["card_benefit_krw"] else [])
        lv, f, g = EN.ev(traits, "benefit", want)
        if lv:
            out.append(EN._term(DEAL_LABEL, EN.W["benefit"] * min(1.0, deal / 50000) * 0.7 * lv, "benefit", f,
                                f"1인 할인 {deal:,.0f}원 · 할인 근거 수준 {lv:.2f}(잠정 변환)", evidence=g))
    if o.get("in_package"):
        pkg = o["price_pp_krw"]
        lv, f, g = EN.ev(traits, "benefit", ["package", "voucher"])
        if lv:
            out.append(EN._term(PKG_LABEL, EN.W["benefit"] * min(1.0, pkg / 50000) * 0.7 * lv, "benefit", f,
                                f"객실 패키지 포함 1인 {pkg:,.0f}원 · 포함 혜택 근거 수준 {lv:.2f}(잠정 변환)", evidence=g))
    return out


def _restricted(traits: dict, facet: str, fact_ids) -> dict:
    ids = set(fact_ids)
    x = dict(traits["facets"][facet])
    x["evidence"] = [e for e in x["evidence"] if e["fact_id"] in ids]
    return {"facets": {facet: x}}


def _visits_as_evidence(entries: list[dict]) -> dict:
    """그 업장의 실제 이용 기록을 경험 단위 근거로(기존 질량 · 등급 · 산식 그대로)."""
    seen, ev = set(), []
    for v in entries:
        key = v.get("experience") or tuple(v["fact_ids"])
        if key in seen:
            continue
        seen.add(key)
        ev.append(dict(fact_id=v["fact_ids"][0], feature=v.get("feature"), grade="rep", tags=["repeat"], mass=PA.CONF_MASS["medium"], gist=v.get("gist")))
    return {"facets": {"routine": dict(evidence=ev)}}


def venue_terms_c2(o: dict, traits: dict, mode: str) -> list[dict]:
    out = []
    entries = traits.get("venues", {}).get(o["venue"], [])
    used = [v for v in entries if v["kind"] == "used"]
    for v in entries:
        if v["kind"] == "used":
            if mode == "venue_visits":
                lv, _, _ = EN.ev(_visits_as_evidence(used), "routine")
                note = f"이 업장 실제 이용 {len({u.get('experience') for u in used})}회(경험 단위) · 수준 {lv:.2f}(기존 산식)"
            else:
                ids = [i for u in used for i in u["fact_ids"]]
                lv, _, _ = EN.ev(_restricted(traits, "routine", ids), "routine", ["repeat"])
                note = f"이 업장 사실 중 반복 근거만 · 수준 {lv:.2f}"
            if lv:
                out.append(EN._term(FAMILIAR_LABEL, EN.W["familiar"] * 0.5 * lv, "routine", v["fact_ids"], v["gist"] + " · " + note))
            if mode == "venue_visits":
                break          # 경험 단위로 이미 합산 — 업장당 한 항
        elif v["kind"] == "appraisal":
            lv, _, _ = EN.ev(_restricted(traits, "post_appraisal", v["fact_ids"]), "post_appraisal")
            out.append(EN._term(APPRAISAL_LABEL, -EN.W["appraisal"] * (0.5 + 0.5 * lv), "post_appraisal", v["fact_ids"],
                                v["gist"] + f" · 이 업장 평가 근거 수준 {lv:.2f}"))
    return out


@contextmanager
def candidate_engine(c1: bool = False, c2: str | None = None, lookahead: str = "v1", c3: bool | str = False):
    """c1: 할인·혜택 분리 통제안 · c2: None | "venue_facts" | "venue_visits" · lookahead: "v1" | "total"(비교용).
    V1.1 연구 확장(명시적 재방문 거부)은 그대로 켠다 — 후보는 그 위에 얹힌다."""
    orig_score = EN._score

    def _score_c(o, t, state, visit, traits, world):
        terms = orig_score(o, t, state, visit, traits, world)
        if c1:
            terms = [x for x in terms if x["factor"] != BENEFIT_LABEL] + benefit_terms_c1(o, traits)
        if c2:
            terms = [x for x in terms if x["factor"] not in (FAMILIAR_LABEL, APPRAISAL_LABEL)] + venue_terms_c2(o, traits, c2)
        return terms

    with ExitStack() as stack:
        EN._score = _score_c                      # v11_engine 이 이 함수를 다시 감싼다(거부 항은 후보 항 위에서 계산)
        stack.callback(setattr, EN, "_score", orig_score)
        stack.enter_context(v11_engine())
        if c3:
            stack.enter_context(_refuse_reason_gate(mode="three_way" if c3 == "three_way" else "binary"))
        if lookahead == "total":
            stack.enter_context(_lookahead_total())
        yield


@contextmanager
def _lookahead_total():
    """비교용: 앞 행동의 총점 = 자체 점수 + 다음 행동의 '총점'(다음 행동을 고른 기준과 같은 값).
    V1 의 decide_at 은 다음 행동을 decide_at(깊이+1)으로 고른 뒤 그 결과의 score(자체 점수)만 더한다.
    여기서는 깊이 ≥ 1 호출(내다보기 안의 호출)이 돌려주는 score 자리에 그 행동의 총점을 넣어, 부모가 더하는 값을 총점으로 바꾼다.
    다음 행동의 선택 자체(무엇을 고르는가)는 V1 과 같고, 앞 행동에 더해지는 값만 달라진다. 깊이 상한(lookahead_depth)도 같다."""
    orig = EN.decide_at

    def decide_at_total(t, state, visit, traits, world):
        d = orig(t, state, visit, traits, world)
        if state.get("_depth", 0) >= 1:
            d = dict(d, score_self=d["score"], score=d["total"])
        return d

    EN.decide_at = decide_at_total
    try:
        yield
    finally:
        EN.decide_at = orig


REFUSE_LABEL = "명시적 재방문 거부(같은 업장)"
PRICE_REASON = r"가격|비싸|가성비|가심비|원\b|만 ?원|값|지불|결제|가치"
QUALITY_REASON = r"맛(이|은)?\s?(없|별로|좋지 않|아쉽|떨어)|맛없|불친절|서비스(가|는)?\s?(별로|나쁘|아쉽|불만)|위생|청결(하지 않|이 별로)|응대"


def refuse_reason(entry: dict, traits: dict) -> str:
    """C-3: 거부 기록의 이유 — 거부 사실과 같은 경험의 평가 · 유보 기록 요지에서 가격·가치 표현을 찾는다(없으면 other)."""
    txt = " ".join([entry.get("gist", "")] + [v.get("gist", "") for vs in traits.get("venues", {}).values() for v in vs
                                              if v.get("experience") == entry.get("experience") and v["kind"] in ("appraisal", "refuse")])
    import re as _re
    if _re.search(PRICE_REASON, txt):
        return "price_value"
    if _re.search(QUALITY_REASON, txt):
        return "taste_service"
    return "unknown"


@contextmanager
def _refuse_reason_gate(mode: str = "binary"):
    """C-3: V1.1 의 거부 완화(새 조건이 실지출보다 싸진 만큼 완화)는 거부 이유가 가격·가치일 때만.
    binary(기준선 R-BASE): 가격·가치가 아니면(이유 미확인 포함) 완화 없이 전부 상쇄
    three_way: 맛·서비스 거부만 완화 없이 상쇄 · 이유 미확인은 V1.1 그대로(실지출 기준 완화) · 가격·가치는 완화"""
    orig = EN._score

    def _score_gate(o, t, state, visit, traits, world):
        terms = orig(o, t, state, visit, traits, world)
        refs = [v for v in traits.get("venues", {}).get(o["venue"], []) if v.get("kind") == "refuse"]
        reasons = [refuse_reason(r, traits) for r in refs]
        no_relief = [x for x in reasons if x != "price_value"] if mode == "binary" else [x for x in reasons if x == "taste_service"]
        if not refs or not no_relief:
            return terms
        out = []
        for x in terms:
            if x["factor"] == REFUSE_LABEL:
                pull = sum(y["value"] for y in terms if y["facet"] and y["value"] > 0 and y["factor"] != REFUSE_LABEL)
                x = dict(x, value=round(-pull, 4), note=x["note"] + f" · C-3({mode}): 거부 이유 {'/'.join(reasons)} → 가격 완화 없음")
            out.append(x)
        return out

    EN._score = _score_gate
    try:
        yield
    finally:
        EN._score = orig
