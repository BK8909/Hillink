"""Rule-assisted contextual appraisal extraction; input text is never copied to output."""
from __future__ import annotations
import re

VERSION = "contextual_appraisal_v2.0"

PRICE_NEG = re.compile(r"(?:이나|씩이나|나\s*했다|만만치|비싸|부담|이\s*가격에)")
PRICE_POS = re.compile(r"(?:밖에\s*안|저렴|가성비|합리적\s*가격)")
VALUE_WORTH = re.compile(r"(?:그만한|값어치|가치).{0,12}(?:했다|있|충분|만족)|(?:만족|좋았|괜찮).{0,12}(?:가격|값)")
EXPLICIT_NEG = re.compile(r"(?:싫|불만|최악|별로|불편|맛없|후회|실망)")
EXPLICIT_POS = re.compile(r"(?:좋았|마음에 들|만족|훌륭|추천|편했|안전하게)")
EXPECTATION = re.compile(r"(?:생각보다|기대(?:한|했던|보다)|평범|그냥)")
EXPECTATION_GAP = re.compile(r"(?:기대.{0,16}(?:못|아니|않|평범|보통)|생각보다.{0,16}(?:작|평범|보통|아쉽)|가격대.{0,16}(?:평범|보통|기대에 못))")
CHILD_SIZE = re.compile(r"(?:아이|어린이|애들).{0,12}(?:놀기|이용|쓰기).{0,8}(?:좋|딱|알맞).{0,10}(?:크기|규모)|(?:아이|어린이|애들).{0,8}(?:놀기 좋은 크기)")
ADULT = re.compile(r"성인|어른")
MEAL = re.compile(r"피자|식사|메뉴|맛|재료|음식|조식|뷔페")
POOL = re.compile(r"수영장|풀장|수영")
PRICE = re.compile(r"콜라|가격|요금|비용|원|만원")

def _claim(target, polarity, valence, level, strength, confidence, ids, segments, reasoning, alternatives, implication, facts):
    return {"appraisal_id": f"APP-{len(facts)+1:03d}", "target": target, "polarity": polarity,
      "valence_score": valence, "evidence_strength": strength, "interpretation_confidence": confidence,
      "inference_level": level, "scope": {"kind":"local_experience", "target_scope":target},
      "source_ids": list(ids), "segment_ids": list(segments), "contextual_reasoning": reasoning,
      "alternative_readings": alternatives, "behavioral_implication": implication,
      "stable_trait_status":"not_established_from_single_experience", "raw_text_stored":False}

def extract(review_segments: list[dict], context: dict | None = None) -> dict:
    """Segments require segment_id/text/evidence_ids. Text is analyzed, not exported."""
    context = context or {}
    if any(not x.get("segment_id") or not x.get("text") for x in review_segments):
        raise ValueError("segments_require_id_and_text")
    text = " ".join(x["text"] for x in review_segments)
    ids = sorted({i for x in review_segments for i in x.get("evidence_ids", [])})
    segment_ids = [x["segment_id"] for x in review_segments]
    claims = []
    separate_cost_count = len(re.findall(r"(?:별도\s*비용|추가\s*(?:요금|비용))", text))
    cost_reference_count = len(re.findall(r"(?:가격|요금|비용|원|콜라)", text))
    repeated_separate_cost = separate_cost_count >= 1 and cost_reference_count >= 2
    direct_expensive = bool(re.search(r"(?:비싸|비쌌|비싼|만만치|부담)", text))
    price_emphasis = PRICE_NEG.search(text) or repeated_separate_cost
    if (price_emphasis or direct_expensive) and (PRICE.search(text) or direct_expensive):
        claims.append(_claim("price_burden", "negative", -1, "D1" if direct_expensive else "D2", 3 if direct_expensive else 2,
            "high" if direct_expensive else "moderate", ids, segment_ids,
            "가격 평가 표현 또는 강조/반복 비용 단서가 단순 가격 기록보다 부담·놀라움 해석을 뒷받침함.",
            ["가격을 강조했지만 즐거운 놀라움일 가능성"], "동일 가격 조건의 재구매 비교에서만 약한 저해 단서", claims))
    elif PRICE_POS.search(text) and PRICE.search(text):
        claims.append(_claim("price_value", "positive", 1, "D2", 2, "moderate", ids, segment_ids,
            "가격을 낮게 지각하는 표현이 포함됨.", ["개인 전반의 절약 성향과는 무관"], "해당 구매의 가격 수용성 단서", claims))
    if VALUE_WORTH.search(text) or re.search(r"추가\s*(?:요금|비용).{0,16}(?:먹을 만|가치|만족)", text):
        claims.append(_claim("value_for_money", "positive", 1, "D1", 3, "high", ids, segment_ids,
            "가격 대비 가치가 있었다는 결론 표현이 확인됨.", [], "유사 상품·가격 범위에서 재구매 가치 판단에 참고", claims))
    if re.search(r"(?:좋|괜찮|훌륭).{0,18}(?:데|지만).{0,22}(?:평범|별로|아쉽|기대에 못|보통)", text):
        claims.append(_claim("taste", "negative", -1, "D2", 2, "moderate", ids, segment_ids,
            "긍정 속성과 맛 평가가 양보/대조 구조를 이루며 맛은 상대적으로 유보됨.",
            ["평범함을 긍정적으로 보는 개인 취향이 있을 수 있음"], "동일 메뉴 기대 조정에 참고; 전체 미식 성향으로 일반화 금지", claims))
    elif EXPECTATION_GAP.search(text) and MEAL.search(text) and not EXPLICIT_POS.search(text):
        claims.append(_claim("taste_or_meal_expectation", "negative", -1, "D2", 2, "moderate", ids, segment_ids,
            "기대/비교 기준과 실제 식사 결과의 간격이 문맥에서 뒷받침됨.",
            ["평범함이 작성자에게는 긍정일 수 있음"], "해당 메뉴·가격·방문 상황에 국한; 미식 성향 전체로 일반화 금지", claims))
    if re.search(r"(?:재료|전망|시설|분위기).{0,14}(?:좋|훌륭).{0,12}(?:데|지만)", text):
        target = "ingredient_quality" if "재료" in text else "specific_positive_attribute"
        claims.append(_claim(target, "positive", 1, "D1", 3, "high", ids, segment_ids,
            "양보절 앞의 구체적 속성은 긍정 평가로 분리됨.", [], "해당 속성 범위에서만 재선택에 참고", claims))
    if CHILD_SIZE.search(text) and ADULT.search(text):
        claims.append(_claim("adult_pool_size_suitability", "negative", -1, "D2", 2, "moderate", ids, segment_ids,
            "성인 이용 맥락과 아동 놀이에 적합하다는 크기 기준이 대비되어 성인 활동 적합성의 아쉬움을 시사함.",
            ["성인도 가볍게 이용하기에는 만족했을 수 있음"], "시설 규모가 다른 수영장에만 제한 전이; 수영 활동 자체의 불호로 일반화 금지", claims))
    if EXPLICIT_NEG.search(text):
        target = "service_or_experience" if not (POOL.search(text) or MEAL.search(text)) else "experience_as_stated"
        claims.append(_claim(target, "negative", -2, "D1", 3, "high", ids, segment_ids,
            "명시적 부정 표현이 대상 경험과 함께 있음.", [], "대상과 상황을 그대로 유지해 사용", claims))
    if EXPLICIT_POS.search(text) and not VALUE_WORTH.search(text) and not (CHILD_SIZE.search(text) and ADULT.search(text)):
        target = "meal_experience" if MEAL.search(text) else "convenience_or_safety"
        claims.append(_claim(target, "positive", 1, "D1", 3, "high", ids, segment_ids,
            "명시적 긍정 표현이 확인됨.", [], "해당 속성·상황 범위에서 사용", claims))
    # Bare usage, amount, timing, or included entitlement does not imply valence or willingness to repurchase.
    if not claims:
        neutral_target = "pool_experience" if POOL.search(text) else "meal_experience" if MEAL.search(text) else "event_description"
        claims.append(_claim(neutral_target, "neutral", 0, "D4", 0, "low", ids, segment_ids,
            "평가 방향을 지지하는 언어·비교 맥락이 충분하지 않아 사실/일정 서술로만 유지.",
            [], "행동 선호나 만족으로 변환하지 않음", claims))
    return {"version":VERSION, "claims":claims, "source_access":"caller_supplied_segments",
            "raw_text_stored":False, "profile_aggregation":"not_performed", "model_calls":0}

def aggregate_stable_traits(appraisals: list[dict]) -> list[dict]:
    """Promote only repeated same-aspect evaluations across verified distinct stays."""
    grouped = {}
    for app in appraisals:
        if app.get("author_identity_status") != "verified" or app.get("stay_identity_status") != "verified": continue
        for claim in app.get("claims", []):
            if claim.get("evidence_strength", 0) < 2 or claim.get("polarity") not in {"positive","negative"}: continue
            key = claim["target"]
            grouped.setdefault(key, []).append((app.get("stay_id"), claim))
    result=[]
    for target, rows in grouped.items():
        stays={sid for sid,_ in rows if sid}
        signs={c["polarity"] for _,c in rows}
        if len(stays)>=2 and len(signs)==1:
            result.append({"target":target,"polarity":next(iter(signs)),"distinct_verified_stays":len(stays),
                "source_ids":sorted({x for _,c in rows for x in c.get("source_ids",[])}),
                "status":"repeated_cross_stay_trait_candidate_not_validated"})
    return result
