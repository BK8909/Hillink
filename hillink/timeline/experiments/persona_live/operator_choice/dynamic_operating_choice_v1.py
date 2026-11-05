"""Offline decisions computed from profile evidence and mutable operating inputs.

No model is called. Coefficients are declared research assumptions; outputs are
concrete action hypotheses with source/condition traces, not choice probabilities.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "dynamic_operating_policy_v1.json").read_text(encoding="utf-8"))
PROHIBITED_KEYS = {
    "action_hypothesis", "expected_choice", "gold", "reviewer_opinion",
    "previous_response", "human_review_comments", "decision_mappings",
}
ASPECT_DOMAINS = {
    "gym_participation": "fitness",
    "indoor_pool_and_kids_pool": "pool",
    "skyard_night_view": "scenic_visit",
    "foot_bath_expectation_vs_use": "foot_bath",
    "pizza_food_preference": "dining",
    "buffet_menu_evaluations": "dining",
}
FOOD_ASPECTS = {"pizza_food_preference", "buffet_menu_evaluations"}
VALUE_ASPECTS = {"pizza_hill_taste_and_value", "buffet_price_value"}
SPACE_ASPECTS = {"skyard_night_view", "scenic_space_interest"}
CHOICE_LABELS = {
    "reserve_event": "행사 예약을 선택",
    "reserve_restaurant": "일반 식당 예약을 선택",
    "inspect_then_decide": "행사장을 살펴본 뒤 예약 여부를 결정",
}
FACTOR_LABELS = {
    "food_experience": "음식 경험과 구성의 적합성",
    "current_meal_goal": "이번 저녁 식사 목적 충족",
    "new_experience": "새로운 호텔 경험의 매력",
    "scenic_space": "공간·조망 경험의 적합성",
    "incremental_cost": "대안 대비 실질 비용",
    "time_burden": "시간 투입의 기회비용",
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def assert_no_results(value: object) -> None:
    if isinstance(value, dict):
        leaked = set(value) & PROHIBITED_KEYS
        if leaked:
            raise ValueError("result_or_reviewer_input:" + ",".join(sorted(leaked)))
        for item in value.values():
            assert_no_results(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_results(item)


def profile_input(profile: dict) -> dict:
    """Allowlist decision-relevant claims; exclude old mappings and review prose."""
    allowed = set(ASPECT_DOMAINS) | FOOD_ASPECTS | VALUE_ASPECTS | SPACE_ASPECTS | {
        "room_dining_and_external_food", "party_size_and_relationship", "two_drinks_visual",
    }
    claims = []
    for claim in profile.get("claims", []):
        if claim.get("aspect") not in allowed:
            continue
        claims.append({
            key: deepcopy(claim.get(key))
            for key in ("claim_id", "aspect", "value", "claim_layer", "scope", "anchors", "review")
        })
    if len({c["claim_id"] for c in claims}) != len(claims):
        raise ValueError("duplicate_profile_claim_id")
    result = {"persona_id": profile["persona_id"], "profile_version": profile["profile_version"],
              "source_access_status": profile.get("source_access_status"), "claims": claims}
    assert_no_results(result)
    return result


def _roots(claim: dict) -> set[str]:
    return {a["evidence_root"] for a in (claim.get("anchors") or []) if a.get("evidence_root")}


def profile_factors(profile: dict, policy: dict | None = None) -> dict:
    """Common aspect adapter. One root backs one factor, not repeated inferences."""
    policy = POLICY if policy is None else policy
    assert_no_results(profile)
    claims = profile["claims"]
    used: set[str] = set()
    factors = {}
    groups = (
        ("value_attention", VALUE_ASPECTS),
        ("food_experience", FOOD_ASPECTS),
        ("scenic_space", SPACE_ASPECTS),
    )
    for name, aspects in groups:
        ids, roots = [], set()
        for claim in sorted(claims, key=lambda c: c["claim_id"]):
            new_roots = _roots(claim) - used
            if claim["aspect"] in aspects and new_roots:
                ids.append(claim["claim_id"])
                roots |= new_roots
        used |= roots
        factors[name] = {"support": policy["interpretation_levels"][name] if roots else 0,
                         "claim_ids": ids, "evidence_roots": sorted(roots),
                         "layer": "personal_experience_inference", "calibration": "unvalidated_ordinal_transfer"}
    domains = {ASPECT_DOMAINS[c["aspect"]] for c in claims if c["aspect"] in ASPECT_DOMAINS and _roots(c)}
    novelty_claims = [c for c in claims if c["aspect"] in ASPECT_DOMAINS and _roots(c) - used]
    roots = set().union(*(_roots(c) - used for c in novelty_claims)) if novelty_claims else set()
    qualified = len(domains) >= policy["minimum_experience_domains_for_novelty_inference"] and bool(roots)
    factors["new_experience"] = {
        "support": policy["interpretation_levels"]["new_experience"] if qualified else 0,
        "claim_ids": [c["claim_id"] for c in novelty_claims] if qualified else [],
        "evidence_roots": sorted(roots) if qualified else [],
        "layer": "cross_experience_inference", "calibration": "unvalidated_ordinal_transfer",
        "observed_domains": sorted(domains),
        "limitation": "여러 호텔 경험의 참여는 새 행사를 검토할 단서다. 특정 주류·행사 선호나 참가 의사는 아니다.",
    }
    return factors


def _number(value: object, name: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError("invalid_number:" + name)
    return float(value)


def validate_environment(environment: dict) -> None:
    assert_no_results(environment)
    if environment.get("status") != "fictional_operating_conditions":
        raise ValueError("explicit_fictional_status_required")
    visit = environment["visit"]
    if visit["party_size"] != int(_number(visit["party_size"], "party_size", 1)):
        raise ValueError("integer_party_size_required")
    for name in ("meal_goal",):
        if not 0 <= _number(visit[name], name) <= 1:
            raise ValueError("bounded_visit_factor:" + name)
    _number(visit["free_minutes"], "free_minutes", 1)
    _number(environment["reference_dinner_price_krw"], "reference_dinner_price_krw", 1)
    _number(environment["pairing_courses_per_meal"], "pairing_courses_per_meal", 1)
    if not environment["options"] or len({o["option_id"] for o in environment["options"]}) != len(environment["options"]):
        raise ValueError("nonempty_unique_options_required")
    for option in environment["options"]:
        if option["action"] not in {"reserve_event", "reserve_restaurant"}:
            raise ValueError("unsupported_option_action")
        for name in ("price_krw", "guest_benefit_krw", "duration_minutes", "food_courses"):
            _number(option[name], name)
        if option["guest_benefit_krw"] > option["price_krw"]:
            raise ValueError("benefit_exceeds_price")
        for name in ("novelty", "scenic_space"):
            if not 0 <= _number(option[name], name) <= 1:
                raise ValueError("bounded_option_factor:" + name)
        if not isinstance(option["available"], bool) or not isinstance(option["alcohol_required"], bool):
            raise ValueError("explicit_availability_and_alcohol_rule_required")


def validate_policy(policy: dict) -> None:
    for name in FACTOR_LABELS:
        _number(policy["weights"][name], "weight:" + name)
    for name in ("food_experience", "new_experience", "scenic_space", "value_attention"):
        if not 0 <= _number(policy["interpretation_levels"][name], name) <= 1:
            raise ValueError("bounded_transfer_strength_required")
    _number(policy["default_time_reference_minutes"], "time_reference", 1)
    _number(policy["decision_margin_for_inspection"], "inspection_margin")
    _number(policy["minimum_experience_domains_for_novelty_inference"], "minimum_domains", 1)
    if not 0 <= _number(policy["general_cost_attention_without_personal_evidence"], "general_cost_attention") <= 1:
        raise ValueError("bounded_general_cost_attention_required")


def evaluate(profile: dict, environment: dict, policy: dict | None = None) -> dict:
    """Recalculate every option from current price, food, constraints and profile."""
    policy = deepcopy(POLICY if policy is None else policy)
    validate_policy(policy)
    validate_environment(environment)
    factors = profile_factors(profile, policy)
    weights = policy["weights"]
    visit = environment["visit"]
    cost_attention = factors["value_attention"]["support"] or policy["general_cost_attention_without_personal_evidence"]
    rows = []
    for option in environment["options"]:
        constraints = []
        if not option["available"]:
            constraints.append("이용 또는 예약 가능 선택지로 제공되지 않음")
        if option["duration_minutes"] > visit["free_minutes"]:
            constraints.append("이번 일정의 가용 시간을 초과함")
        if option["alcohol_required"] and visit.get("alcohol_eligible") is not True:
            constraints.append("필수 음주 자격이 확인되지 않음")
        net_price = option["price_krw"] - option["guest_benefit_krw"]
        meal_fraction = min(1.0, option["food_courses"] / environment["pairing_courses_per_meal"])
        money_ratio = (net_price - environment["reference_dinner_price_krw"]) / environment["reference_dinner_price_krw"]
        entries = []

        def add(name, value, explanation, feature=None):
            source = factors.get(feature or name, {})
            entries.append({"factor": name, "contribution": round(value, 6), "reason": explanation,
                            "claim_ids": source.get("claim_ids", []), "evidence_roots": source.get("evidence_roots", []),
                            "layer": source.get("layer", "current_situation_judgment")})

        add("food_experience", weights["food_experience"] * factors["food_experience"]["support"] * meal_fraction,
            f"음식 구성 {option['food_courses']}종; 가상 한 끼 충족도 {meal_fraction:.2f}. 메뉴별 식음 경험을 이번 음식 경험 검토에 제한적으로 적용한다.")
        add("current_meal_goal", weights["current_meal_goal"] * visit["meal_goal"] * meal_fraction,
            f"이번 방문의 저녁 식사 목적 {visit['meal_goal']:.2f}와 음식 충족도의 적합성. 과거 목적을 자동 이전하지 않는다.")
        add("new_experience", weights["new_experience"] * factors["new_experience"]["support"] * option["novelty"],
            f"실제 여러 경험에 참여한 이력과 이번 선택지의 새로움 {option['novelty']:.2f}을 연결한다. 특정 행사 취향으로 확정하지 않는다.")
        add("scenic_space", weights["scenic_space"] * factors["scenic_space"]["support"] * option["scenic_space"],
            f"과거 공간·야경 경험과 가상 공간 속성 {option['scenic_space']:.2f}의 제한적 적합성.")
        add("incremental_cost", -weights["incremental_cost"] * cost_attention * money_ratio,
            f"실질 1인 비용 {net_price:,.0f}원, 비교 식사 {environment['reference_dinner_price_krw']:,.0f}원. 정해진 지불의사가 아닌 이번 대안 대비 비용을 비교한다.", "value_attention")
        add("time_burden", -weights["time_burden"] * option["duration_minutes"] / policy["default_time_reference_minutes"],
            f"{option['duration_minutes']}분을 쓰는 일반적 기회비용; 개인 시간가치를 학습한 값이 아니다.")
        rows.append({"option_id": option["option_id"], "action": option["action"], "feasible": not constraints,
                     "constraints": constraints, "net_price_per_person_krw": net_price,
                     "party_cost_krw": net_price * visit["party_size"], "meal_fraction": meal_fraction,
                     "factors": entries, "score": round(sum(e["contribution"] for e in entries), 6) if not constraints else None})
    return {"profile_factors": factors, "options": rows, "policy_version": policy["version"]}


def decide(profile: dict, environment: dict, policy: dict | None = None) -> dict:
    policy = POLICY if policy is None else policy
    table = evaluate(profile, environment, policy)
    ranked = sorted((r for r in table["options"] if r["feasible"]), key=lambda r: (-r["score"], r["option_id"]))
    if not ranked:
        action, selected, margin = "keep_existing_schedule", None, None
    else:
        best = ranked[0]
        margin = round(best["score"] - ranked[1]["score"], 6) if len(ranked) > 1 else None
        near = margin is not None and margin <= policy["decision_margin_for_inspection"]
        if near and environment.get("preview", {}).get("available"):
            action, selected = "inspect_then_decide", None
        elif near:
            # No arbitrary option-order tie breaker is presented as a strong preference.
            action, selected = "keep_existing_schedule", None
        else:
            action, selected = best["action"], best["option_id"]
    selected_row = next((r for r in ranked if r["option_id"] == selected), None)
    differences = []
    if len(ranked) > 1:
        left = {e["factor"]: e for e in ranked[0]["factors"]}
        for entry in ranked[1]["factors"]:
            delta = round(left[entry["factor"]]["contribution"] - entry["contribution"], 6)
            differences.append({"factor": entry["factor"], "difference": delta,
                                "claim_ids": left[entry["factor"]]["claim_ids"]})
        differences.sort(key=lambda r: (-abs(r["difference"]), r["factor"]))
    reasons = [e["reason"] for e in sorted(selected_row["factors"], key=lambda e: -abs(e["contribution"])) if e["contribution"] != 0] if selected_row else []
    supports = [d for d in differences if d["difference"] > 0]
    opposes = [d for d in differences if d["difference"] < 0]
    if selected_row:
        summary = CHOICE_LABELS[action] + ". "
        summary += (" · ".join(FACTOR_LABELS[d["factor"]] for d in supports[:2]) + "이 상위 대안보다 유리하게 계산됐다.") if supports else "현재 제약 아래에서 이용 가능한 후보로 계산됐다."
        if opposes:
            summary += " 다만 " + " · ".join(FACTOR_LABELS[d["factor"]] for d in opposes[:2]) + "은 반대 요인으로 남는다."
    elif action == "inspect_then_decide":
        summary = "상위 두 선택지의 차이가 작아, 제공된 무료 사전 관람으로 메뉴·분위기를 확인한 뒤 예약 여부를 결정한다."
    else:
        summary = "이용 가능한 선택지가 없거나 차이가 작은 상태여서 기존 일정을 유지한다. 이를 강한 개인 선호로 해석하지 않는다."
    guidance = {
        "food_experience": "음식 구성과 충분한 식사 경험을 구체적으로 제시할 필요가 있다. 코스 수·양을 바꾸어 같은 프로필로 재계산할 수 있다.",
        "current_meal_goal": "이번 고객은 저녁 식사를 해결해야 한다. 시음 중심 행사와 식사 대체 행사를 구분해 안내하고 음식 충족도 변경을 비교할 수 있다.",
        "new_experience": "새 경험을 실제로 이용한 이력이 행사 검토를 뒷받침한다. 기존 식사와 다른 경험이 무엇인지 명시한 조건을 비교할 수 있다.",
        "scenic_space": "이번 가상 공간 속성과 과거 공간 경험의 연결이 작용했다. 전망·분위기의 구체적 차이를 안내하는 조건을 비교할 수 있다.",
        "incremental_cost": "명목 가격보다 혜택 적용 후 실질 지불액을 일반 식사와 함께 비교한다. 할인과 가격 인상에 대한 결과는 각각 재계산해야 한다.",
        "time_burden": "행사와 대체 식사의 소요시간 차이가 작용했다. 일정에 맞는 짧은 회차 조건을 비교할 수 있다.",
    }
    implications = [guidance[d["factor"]] for d in differences[:2] if d["difference"] != 0]
    return {"method_version": "dynamic_operating_choice_v1.0", "policy_version": policy["version"],
            "profile_sha256": digest(profile), "environment_sha256": digest(environment),
            "action": action, "action_label": CHOICE_LABELS.get(action, "기존 일정 유지"), "selected_option": selected,
            "status": "computed_exploratory_action_hypothesis", "margin": margin,
            "dominance_is_small": margin is not None and margin <= policy["decision_margin_for_inspection"],
            "behavior_summary": summary, "reasons": reasons, "supporting_comparison": supports,
            "opposing_comparison": opposes, "top_option_comparison": differences,
            "operator_implications": implications,
            "alternatives": [{"option_id": r["option_id"], "score_gap_from_top": round(ranked[0]["score"] - r["score"], 6) if r["feasible"] else None,
                               "constraints": r["constraints"],
                               "factor_differences_from_top": [{"factor": e["factor"], "difference": round(next(t["contribution"] for t in ranked[0]["factors"] if t["factor"] == e["factor"]) - e["contribution"], 6)} for e in r["factors"]]}
                              for r in table["options"] if r["option_id"] != selected] if ranked else [],
            "audit": table, "reservation_success_claimed": False,
            "uncertainties": ["와인 취향·지불의사는 미확인", "전이 강도와 가중치는 미보정", "사람의 행동 개연성 검수는 대기"],
            "llm_calls": 0, "human_review": "pending", "demo_approved": False}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Compute a new offline action from a V3 profile and fictional environment JSON.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    clean = profile_input(json.loads(args.profile.read_text(encoding="utf-8")))
    environment = json.loads(args.environment.read_text(encoding="utf-8"))
    result = decide(clean, environment)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)
        print(json.dumps({"action": result["action"], "selected_option": result["selected_option"], "environment_sha256": result["environment_sha256"]}))
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
