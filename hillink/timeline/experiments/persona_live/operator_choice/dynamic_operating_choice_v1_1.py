"""Profile stages, real outside options and prospective information acquisition.

Offline research heuristics only. V1 files and frozen results are never written.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import json
import math
from pathlib import Path

from .dynamic_operating_choice_v1 import (
    ASPECT_DOMAINS, FOOD_ASPECTS, SPACE_ASPECTS, VALUE_ASPECTS,
    assert_no_results, digest, profile_input as profile_input_v1,
)

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "dynamic_operating_policy_v1_1.json").read_text(encoding="utf-8"))
LABELS = {"reserve_event": "행사 예약 의향", "reserve_restaurant": "일반 식당 예약 의향",
          "room_meal_and_rest": "객실 식사와 휴식 선택", "simple_meal_and_view": "간단한 식사와 야경 선택",
          "inspect_event": "메뉴·현장 확인 후 결정", "keep_existing_schedule": "행사 불참·기존 일정 유지"}


def _roots(claim: dict) -> set[str]:
    return {a["evidence_root"] for a in claim.get("anchors", []) if a.get("evidence_root")}


def profile_input(raw: dict) -> dict:
    clean = profile_input_v1(raw)
    by_id = {c["claim_id"]: c for c in raw["claims"]}
    for claim in clean["claims"]:
        if "transaction" in by_id[claim["claim_id"]]:
            claim["transaction"] = deepcopy(by_id[claim["claim_id"]]["transaction"])
    clean["document_contexts"] = [{"document_id": doc["document_id"], "visit_cluster": doc["visit_cluster"],
                                    "cluster_status": doc["cluster_status"]} for doc in raw.get("documents", [])]
    for claim in clean["claims"]:
        claim["temporal_role"] = "post_experience_local_appraisal" if claim["aspect"] in VALUE_ASPECTS else "past_experience_or_reported_preference"
    clean["purchase_stage_status"] = {"personal_pre_purchase_price_rule": "unconfirmed",
                                     "information_seeking_habit": "unconfirmed",
                                     "post_appraisal_is_pre_purchase_caution": False}
    clean["input_version"] = "author_profile_v3_stage_projection_v1.1"
    assert_no_results(clean)
    return clean


def profile_facets(profile: dict, policy: dict | None = None) -> dict:
    policy = policy or POLICY
    assert_no_results(profile)
    claims = sorted(profile["claims"], key=lambda c: c["claim_id"])
    if len({c["claim_id"] for c in claims}) != len(claims):
        raise ValueError("duplicate_claim_id")
    selected = lambda aspects: [c for c in claims if c["aspect"] in aspects and _roots(c)]
    food = selected(FOOD_ASPECTS)
    food_roots = set().union(*(_roots(c) for c in food)) if food else set()
    space = []
    for claim in selected(SPACE_ASPECTS):
        clone = deepcopy(claim)
        clone["anchors"] = [a for a in clone["anchors"] if a["evidence_root"] not in food_roots]
        if _roots(clone):
            space.append(clone)
    post = selected(VALUE_ASPECTS)
    allocated = food_roots | (set().union(*(_roots(c) for c in space)) if space else set())
    room = []
    for claim in selected({"room_dining_and_external_food"}):
        clone = deepcopy(claim)
        clone["anchors"] = [a for a in clone["anchors"] if a["evidence_root"] not in allocated]
        if _roots(clone):
            room.append(clone)
    # These are known V3 semantic values, not keyword mining of arbitrary reviews.
    menu_rules = {"likes_pizza": "pizza", "garlic_sauce_preferred": "garlic",
                  "garlic_and_olive_oil_flavors_positive": "olive_oil"}
    menu_preferences = []
    for claim in food:
        for token, feature in menu_rules.items():
            if token in str(claim["value"]).split("; "):
                menu_preferences.append({"feature": feature, "claim_id": claim["claim_id"],
                                         "evidence_roots": sorted(_roots(claim)), "stage": "reported_explicit_menu_preference"})
    used = set().union(*(_roots(c) for c in food + space + room)) if food or space or room else set()
    experiences = selected(set(ASPECT_DOMAINS))
    domains = sorted({ASPECT_DOMAINS[c["aspect"]] for c in experiences})
    novel = [c for c in experiences if _roots(c) - used]
    context = {d["document_id"]: d for d in profile.get("document_contexts", [])}
    bundles = {}
    for claim in novel:
        for anchor in claim["anchors"]:
            doc = anchor["document_id"]
            cluster = context.get(doc, {}).get("visit_cluster")
            key = cluster if cluster and not cluster.startswith("UNASSIGNED") else "unassigned_document:" + doc
            bundles.setdefault(key, set()).add(claim["claim_id"])
    qualified = len(domains) >= policy["minimum_experience_domains"] and bool(novel)
    return {
        "trial_and_participation": {
            "observed_domains": domains, "source_bundles": {k: sorted(v) for k, v in sorted(bundles.items())},
            "independent_repeat_trials_confirmed": False,
            "first_visit_status": "unknown",
            "novelty_claim_ids": [c["claim_id"] for c in novel],
            "novelty_roots": sorted(set().union(*(_roots(c) - used for c in novel))) if novel else [],
            "novelty_transfer_range": [0, policy["transfer_levels"]["new_experience_upper"] if qualified else 0],
            "interpretation": "실제 여러 활동에 참여한 경험은 새 경험 검토 가설을 지지한다. 같은 방문 묶음을 반복 방문으로 세지 않는다.",
        },
        "prepurchase_criteria": {
            "personal_price_sensitivity": "unconfirmed", "personal_willingness_to_pay": "unconfirmed",
            "personal_information_seeking": "unconfirmed",
            "observed_transactions": [{"claim_id": c["claim_id"], "transaction": c["transaction"]} for c in claims if "transaction" in c],
            "interpretation": "주문액·혜택 사용과 예약 전 신중함은 별개다. 최초 방문 여부·실제 자기부담액도 확정하지 않는다.",
        },
        "post_experience_evaluation": [{"claim_id": c["claim_id"], "value": c["value"], "scope": c["scope"],
                                         "stage": "post_experience_local_appraisal", "used_in_new_event_price_weight": False} for c in post],
        "menu_preferences": menu_preferences,
        "food_claim_ids": [c["claim_id"] for c in food], "food_roots": sorted(set().union(*(_roots(c) for c in food))) if food else [],
        "space_claim_ids": [c["claim_id"] for c in space], "space_roots": sorted(set().union(*(_roots(c) for c in space))) if space else [],
        "space_context_sources": {
            name: [{"claim_id": c["claim_id"], "roots": sorted(_roots(c))} for c in space
                   if (name == "night_view" and (c["aspect"] == "skyard_night_view" or any("night_view" in r for r in _roots(c))))
                   or (name == "dining_view" and any("breakfast_seat" in r for r in _roots(c)))
                   or (name == "room_view" and any("view_room" in r or "mountain_view_choice" in r for r in _roots(c)))]
            for name in ("night_view", "dining_view", "room_view")
        },
        "room_alternative": {"claim_ids": [c["claim_id"] for c in room],
                             "roots": sorted(set().union(*(_roots(c) for c in room))) if room else [],
                             "interpretation": "실제 객실 내 외부 식사 사례다. 항상 객실 식사를 선호한다는 뜻은 아니다."},
    }


def _number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError("invalid_number:" + name)
    return value


def _unit(value, name):
    if _number(value, name) > 1:
        raise ValueError("unit_range:" + name)


def minute(value: str) -> int:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":" or not (value[:2] + value[3:]).isdigit():
        raise ValueError("HH_MM_required")
    hour, mins = int(value[:2]), int(value[3:])
    if hour > 23 or mins > 59:
        raise ValueError("invalid_clock_time")
    return hour * 60 + mins


def interval(item: dict) -> tuple[int, int]:
    start, end = minute(item["start"]), minute(item["end"])
    if end <= start:
        raise ValueError("same_day_positive_interval_required")
    return start, end


def effective_price(option: dict) -> float:
    seen_ids, seen_entitlements = set(), set()
    for benefit in option.get("benefits", []):
        _number(benefit["amount_krw"], "benefit")
        if benefit["benefit_id"] in seen_ids or benefit["entitlement_id"] in seen_entitlements:
            raise ValueError("duplicate_benefit_or_entitlement")
        if benefit["eligibility"] != "stipulated_for_this_scenario":
            raise ValueError("benefit_eligibility_must_be_explicit")
        seen_ids.add(benefit["benefit_id"])
        seen_entitlements.add(benefit["entitlement_id"])
    net = option["price_krw"] - sum(b["amount_krw"] for b in option.get("benefits", []))
    if net < 0:
        raise ValueError("benefits_exceed_price")
    return net


def validate_environment(env: dict) -> None:
    assert_no_results(env)
    if env.get("version") != "operating_environment_v1.1" or env.get("status") != "fictional_operating_conditions":
        raise ValueError("versioned_fictional_environment_required")
    minute(env["now"])
    visit = env["visit"]
    if int(_number(visit["party_size"], "party_size", 1)) != visit["party_size"]:
        raise ValueError("integer_party_required")
    _unit(visit["meal_goal"], "meal_goal")
    _unit(visit["rest_goal"], "rest_goal")
    for blocked in visit["blocked_intervals"]:
        interval(blocked)
    _number(env["reference_dinner_price_krw"], "reference_price", 1)
    if not env["options"] or len({o["option_id"] for o in env["options"]}) != len(env["options"]):
        raise ValueError("unique_options_required")
    if not any(o["action"] == "keep_existing_schedule" and o["available"] for o in env["options"]):
        raise ValueError("explicit_available_outside_option_required")
    for option in env["options"]:
        if option["action"] not in LABELS or option["action"] == "inspect_event":
            raise ValueError("unknown_immediate_action")
        if not isinstance(option["available"], bool) or not isinstance(option["alcohol_required"], bool):
            raise ValueError("explicit_availability_required")
        _number(option["price_krw"], "price")
        _number(option["effort_minutes"], "effort_minutes")
        effective_price(option)
        _number(option["food_courses"], "food_courses")
        for field in ("serving_fraction_per_course", "food_quality", "novelty", "scenic_space", "rest_fit"):
            _unit(option[field], field)
        if not isinstance(option["menu_tags"], list) or len(set(option["menu_tags"])) != len(option["menu_tags"]):
            raise ValueError("unique_menu_tags_required")
        if not isinstance(option["menu_details_complete"], bool):
            raise ValueError("explicit_menu_information_status_required")
        if option["schedule"] is not None:
            interval(option["schedule"])
        if option["space_context"] not in {"night_view", "dining_view", "room_view", "none"}:
            raise ValueError("unknown_space_context")
        if option["action"] == "keep_existing_schedule" and (option["schedule"] is not None or option["reservation"] is not None or option["price_krw"] != 0):
            raise ValueError("outside_option_must_remain_executable")
        if option["action"] in {"reserve_event", "reserve_restaurant"} and (option["reservation"] is None or option["schedule"] is None):
            raise ValueError("reservation_window_and_activity_schedule_required")
        if option["action"] not in {"reserve_event", "reserve_restaurant"} and option["reservation"] is not None:
            raise ValueError("nonbooking_option_cannot_use_booking_window")
        if option["reservation"] is not None:
            reservation = option["reservation"]
            if minute(reservation["closes_at"]) < minute(reservation["opens_at"]):
                raise ValueError("reservation_window_invalid")
            _number(reservation["processing_minutes"], "booking_time")
            for field in ("capacity", "occupied"):
                if int(_number(reservation[field], field)) != reservation[field]:
                    raise ValueError("integer_seats_required")
            if reservation["occupied"] > reservation["capacity"]:
                raise ValueError("occupied_exceeds_capacity")
    preview = env["preview"]
    if not isinstance(preview["available"], bool):
        raise ValueError("explicit_preview_availability_required")
    interval(preview)
    _number(preview["price_krw"], "preview_price")
    if preview["target_option"] not in {o["option_id"] for o in env["options"]}:
        raise ValueError("preview_target_unknown")
    if set(preview["resolves"]) - {"menu_match"}:
        raise ValueError("preview_cannot_reveal_personal_preference_or_taste_satisfaction")
    if preview["future_seats"] not in {"assumed_remaining_for_planning_only", "unknown"}:
        raise ValueError("explicit_post_preview_seat_assumption_required")


def feasibility(option: dict, env: dict, now: int | None = None) -> list[str]:
    now = minute(env["now"]) if now is None else now
    errors = []
    if not option["available"]:
        errors.append("현재 이용 불가")
    if option["alcohol_required"] and env["visit"].get("alcohol_eligible") is not True:
        errors.append("필수 음주 자격 미확인")
    if option["schedule"]:
        start, end = interval(option["schedule"])
        if start < now:
            errors.append("시작 시각 경과")
        if any(start < b_end and b_start < end for b_start, b_end in map(interval, env["visit"]["blocked_intervals"])):
            errors.append("기존 일정과 충돌")
    if option["reservation"]:
        r = option["reservation"]
        if now < minute(r["opens_at"]) or now + r["processing_minutes"] > minute(r["closes_at"]):
            errors.append("현재 시각에서 예약 처리 불가")
        if r["capacity"] - r["occupied"] < env["visit"]["party_size"]:
            errors.append("가상 잔여 정원 부족")
        if option["schedule"] and now + r["processing_minutes"] > interval(option["schedule"])[0]:
            errors.append("예약 처리 전 행사 시작")
    return errors


def _trace(factor, value, ids=(), roots=(), stage="current_scenario_judgment") -> dict:
    return {"factor": factor, "value": round(value, 6), "claim_ids": list(ids), "evidence_roots": list(roots), "stage": stage}


def evaluate(profile: dict, env: dict, policy: dict | None = None) -> dict:
    policy = POLICY if policy is None else policy
    validate_environment(env)
    for value in policy["weights"].values():
        _number(value, "policy_weight")
    for name, value in policy["transfer_levels"].items():
        _unit(value, "transfer:" + name)
    _unit(policy["general_cost_attention"], "general_cost_attention")
    _number(policy["time_reference_minutes"], "time_reference", 1)
    _number(policy["numerical_tie_tolerance"], "numerical_tolerance")
    facets = profile_facets(profile, policy)
    w, t = policy["weights"], policy["transfer_levels"]
    preferences = {p["feature"]: p for p in facets["menu_preferences"]}
    rows = []
    for option in env["options"]:
        matched = sorted(set(option["menu_tags"]) & preferences.keys())
        # The direct feature replaces broad transfer; it is not a second source vote.
        food_level = 1 if matched else t["food_experience"] if facets["food_claim_ids"] else 0
        food_ids = sorted({preferences[tag]["claim_id"] for tag in matched}) if matched else facets["food_claim_ids"]
        food_roots = sorted({root for tag in matched for root in preferences[tag]["evidence_roots"]}) if matched else facets["food_roots"]
        net = effective_price(option)
        meal = min(1, option["food_courses"] * option["serving_fraction_per_course"])
        space_sources = facets["space_context_sources"].get(option["space_context"], [])
        space_ids = sorted({s["claim_id"] for s in space_sources})
        space_roots = sorted({r for s in space_sources for r in s["roots"]})
        terms = [
            _trace("food_fit", w["food_experience"] * food_level * option["food_quality"] * meal, food_ids, food_roots, "reported_menu_preference" if matched else "limited_food_experience_transfer"),
            _trace("current_meal_goal", w["current_meal_goal"] * env["visit"]["meal_goal"] * meal),
            _trace("current_space_fit", w["scenic_space"] * (t["scenic_space"] if space_ids else 0) * option["scenic_space"], space_ids, space_roots, "scope_limited_" + option["space_context"]),
            _trace("generic_cost", -w["incremental_cost"] * policy["general_cost_attention"] * (net - env["reference_dinner_price_krw"]) / env["reference_dinner_price_krw"] if option["action"] != "keep_existing_schedule" else 0),
            _trace("time_effort", -w["time_burden"] * option["effort_minutes"] / policy["time_reference_minutes"]),
            _trace("room_pattern_and_current_rest_goal", w["room_convenience"] * (t["room_pattern"] if facets["room_alternative"]["claim_ids"] else 0) * env["visit"]["rest_goal"] * option["rest_fit"], facets["room_alternative"]["claim_ids"], facets["room_alternative"]["roots"], "observed_compatible_alternative_plus_current_goal"),
        ]
        uncertain = []
        novelty_high = w["new_experience"] * facets["trial_and_participation"]["novelty_transfer_range"][1] * option["novelty"]
        if novelty_high:
            uncertain.append({"variable": "personal_novelty_transfer", "low": 0, "high": novelty_high,
                              "claim_ids": facets["trial_and_participation"]["novelty_claim_ids"],
                              "evidence_roots": facets["trial_and_participation"]["novelty_roots"], "stage": "uncertain_cross_activity_transfer", "observable_in_preview": False})
        if not option["menu_details_complete"] and not matched and preferences:
            possible_match = w["food_experience"] * (1 - food_level) * option["food_quality"] * meal
            if possible_match:
                uncertain.append({"variable": "menu_match:" + option["option_id"], "low": 0, "high": possible_match,
                                  "claim_ids": sorted({p["claim_id"] for p in preferences.values()}),
                                  "stage": "unresolved_current_menu_fact", "observable_in_preview": True})
        errors = feasibility(option, env)
        fixed = round(sum(term["value"] for term in terms), 6)
        rows.append({"option_id": option["option_id"], "action": option["action"], "feasible": not errors, "constraints": errors,
                     "fixed_score": fixed, "uncertainty": uncertain, "terms": terms, "matched_menu_tags": matched,
                     "meal_adequacy": meal,
                     "net_price_per_person_krw": net, "party_total_krw": net * env["visit"]["party_size"],
                     "extra_party_cost_vs_dinner_krw": (net - env["reference_dinner_price_krw"]) * env["visit"]["party_size"],
                     "score_range": [fixed, round(fixed + sum(u["high"] for u in uncertain), 6)]})
    return {"facets": facets, "options": rows}


def _utility(row, world):
    return row["fixed_score"] + sum(u["high"] if world[u["variable"]] else u["low"] for u in row["uncertainty"])


def _best_regret(rows, worlds, best_scores, epsilon=1e-9):
    regrets = {r["option_id"]: max(best_scores[i] - _utility(r, worlds[i]) for i in range(len(worlds))) for r in rows}
    minimum = min(regrets.values())
    tied = [r for r in rows if regrets[r["option_id"]] - minimum <= epsilon]
    chosen = min(tied, key=lambda r: (r["party_total_krw"], r["option_id"]))
    return chosen, regrets


def decide(profile: dict, env: dict, policy: dict | None = None) -> dict:
    policy = POLICY if policy is None else policy
    table = evaluate(profile, env, policy)
    rows = [row for row in table["options"] if row["feasible"]]
    variables = sorted({u["variable"] for row in rows for u in row["uncertainty"]})
    if len(variables) > 10:
        raise ValueError("research_endpoint_enumeration_limit")
    worlds = [dict(zip(variables, bits)) for bits in product((0, 1), repeat=len(variables))]
    best_scores = [max(_utility(row, world) for row in rows) for world in worlds]
    _, regrets = _best_regret(rows, worlds, best_scores, policy["numerical_tie_tolerance"])
    candidates = [{"option_id": row["option_id"], "action": row["action"], "worst_case_regret": round(regrets[row["option_id"]], 6),
                   "party_total_krw": row["party_total_krw"]} for row in rows]
    preview = env["preview"]
    target = next(row for row in table["options"] if row["option_id"] == preview["target_option"])
    start, end = interval(preview)
    preview_errors = []
    if not preview["available"]:
        preview_errors.append("사전 관람 제공 안 됨")
    if preview["future_seats"] == "unknown":
        preview_errors.append("관람 후 예약 가능 정원의 계획 가정 미확인")
    if start < minute(env["now"]):
        preview_errors.append("사전 관람 시작 시각 경과")
    if any(start < b_end and b_start < end for b_start, b_end in map(interval, env["visit"]["blocked_intervals"])):
        preview_errors.append("사전 관람과 기존 일정 충돌")
    target_option = next(o for o in env["options"] if o["option_id"] == preview["target_option"])
    preview_errors.extend(feasibility(target_option, env, end))
    after = [row for row in rows if not feasibility(next(o for o in env["options"] if o["option_id"] == row["option_id"]), env, end)]
    observable = [u["variable"] for u in target["uncertainty"] if u["observable_in_preview"] and "menu_match" in preview["resolves"]]
    contingency = []
    info_cost, plan_regret = None, None
    if not preview_errors:
        groups = {}
        for i, world in enumerate(worlds):
            groups.setdefault(tuple(world[var] for var in observable), []).append(i)
        plan_regret = 0
        for observed, indices in groups.items():
            branch_worlds = [worlds[i] for i in indices]
            branch_best = [best_scores[i] for i in indices]
            branch, branch_regrets = _best_regret(after, branch_worlds, branch_best, policy["numerical_tie_tolerance"])
            plan_regret = max(plan_regret, branch_regrets[branch["option_id"]])
            contingency.append({"observed_menu_state": dict(zip(observable, observed)), "prospective_action": branch["action"],
                                "prospective_option": branch["option_id"], "status": "conditional_plan_not_observed_result"})
        info_cost = policy["weights"]["time_burden"] * (end - start) / policy["time_reference_minutes"]
        info_cost += policy["weights"]["incremental_cost"] * policy["general_cost_attention"] * preview["price_krw"] / env["reference_dinner_price_krw"]
        candidates.append({"option_id": "PREVIEW_PLAN", "action": "inspect_event", "worst_case_regret": round(plan_regret + info_cost, 6),
                           "party_total_krw": preview["price_krw"] * env["visit"]["party_size"]})
    minimum = min(r["worst_case_regret"] for r in candidates)
    ties = [r for r in candidates if r["worst_case_regret"] - minimum <= policy["numerical_tie_tolerance"]]
    best = min(ties, key=lambda r: (r["party_total_krw"], r["option_id"]))
    action = best["action"]
    selected_id = best["option_id"]
    reservation = action in {"reserve_event", "reserve_restaurant"}
    interest_claims = table["facets"]["food_claim_ids"] + table["facets"]["trial_and_participation"]["novelty_claim_ids"]
    lifecycle = {"interest": {"state": "supported_hypothesis" if interest_claims else "context_only_hypothesis", "status": "inferred_not_observed", "claim_ids": sorted(set(interest_claims))},
                 "information_check": "planned" if action == "inspect_event" else "not_selected",
                 "reservation_intent": "planned" if reservation else "not_selected",
                 "reservation_attempt": "not_executed", "reservation_result": "unknown", "actual_use": "not_started"}
    selected_row = next((r for r in table["options"] if r["option_id"] == selected_id), None)
    alternatives = sorted(candidates, key=lambda r: (r["worst_case_regret"], r["option_id"]))
    reasons = []
    if selected_row:
        reasons = [f"{term['factor']}: {term['value']:+.3f}; 근거 {','.join(term['claim_ids']) or '현재 가상 조건·공통 판단'}" for term in selected_row["terms"] if term["value"]]
    else:
        reasons = ["메뉴 확인으로 달라질 수 있는 선택과 관람의 시간·비용을 비교한 정보 획득 계획이다. 사후 가치 평가를 사전 신중함으로 전환하지 않았다."]
    if action == "inspect_event":
        summary = "메뉴·현장을 확인한 후 선택한다. 제시되지 않은 메뉴 특징을 확인하면 후속 선택이 달라질 수 있고, 관람의 시간·비용까지 비교했을 때 정보 확인 계획이 선택됐다. 개인의 관측된 신중함을 뜻하지 않는다."
    elif action == "reserve_event":
        summary = f"행사 예약 의향을 선택한다. 현재 가상 음식 구성과 새 경험의 가능성을 대안들과 함께 비교한 결과다. 2인 총비용 {selected_row['party_total_krw']:,.0f}원은 명시된 가상값이며, 미확인 와인 취향이나 사전 가격 회피 성향을 전제하지 않는다."
    elif action == "room_meal_and_rest":
        summary = f"가상 객실 식사로 저녁을 해결하고 쉰다. 과거 객실 내 외부 음식 이용은 이 대안의 실제 행동 근거이고, 이번 2인 비용 {selected_row['party_total_krw']:,.0f}원·휴식 목표·이용 가능성은 현재 가정이다. 행사 관심이 없어졌다는 의미는 아니다."
    elif action == "simple_meal_and_view":
        summary = "간단히 식사한 뒤 야경을 즐기는 계획을 선택한다. 이번 식사 충족과 특정 야간 조망 경험을 연결했으며, 행사 불참을 활동 전반의 비선호로 해석하지 않는다."
    elif action == "reserve_restaurant":
        summary = "일반 식당 예약 의향을 선택한다. 현재 식사 목적·가격·메뉴·이용 조건을 행사 및 비예약 대안과 함께 비교한 결과다. 예약 성공이나 실제 이용은 아직 없다."
    else:
        summary = "행사에 참가하지 않고 기존 일정을 유지한다. 유료 예약을 반드시 고르도록 하지 않으며, 현재 조건에서의 비선택을 안정적인 절약 성향으로 만들지 않는다."
    return {"version": "dynamic_operating_choice_v1.1", "policy_version": policy["version"], "persona_id": profile["persona_id"], "simulation_time": env["now"],
            "profile_sha256": digest(profile), "environment_sha256": digest(env), "action": action, "action_label": LABELS[action],
            "selected_option": selected_id, "lifecycle": lifecycle, "reasons": reasons, "alternatives": alternatives,
            "behavior_summary": summary, "numerical_tie_candidates": [r["option_id"] for r in ties],
            "selected_worst_case_regret": best["worst_case_regret"], "information_plan": {"feasible": not preview_errors,
                "constraints": preview_errors, "observable_variables": observable, "contingency": contingency,
                "inspection_cost_index": info_cost, "residual_opportunity_loss_index": plan_regret},
            "audit": table, "uncertainty_worlds": len(worlds), "is_probability": False,
            "personal_pre_purchase_cost_coefficient": None, "general_cost_coefficient": policy["general_cost_attention"],
            "source_stage_check": "post_appraisals_are_retained_but_not_used_as_new_event_purchase_traits",
            "human_review": "pending", "demo_approved": False, "model_calls": 0}


def view_frame(result: dict) -> dict:
    """Proposal DTO only: does not write the current viewer or approved manifest."""
    return {"version": "operating_intent_frame_v1.1", "integration_status": "proposal_only_not_connected",
            "persona_id": result["persona_id"], "simulation_time": result["simulation_time"],
            "producer": "rule_engine_v1.1", "model_id": None, "action": result["action"],
            "action_label": result["action_label"], "target": result["selected_option"],
            "summary": result["behavior_summary"], "lifecycle": deepcopy(result["lifecycle"]),
            "alternatives": deepcopy(result["alternatives"]),
            "input_sha256": result["environment_sha256"], "profile_sha256": result["profile_sha256"],
            "human_review": result["human_review"], "demo_approved": result["demo_approved"]}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Offline V1.1 operating decision; no model execution.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = decide(profile_input(json.loads(args.profile.read_text(encoding="utf-8"))), json.loads(args.environment.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"action": result["action"], "selected_option": result["selected_option"], "model_calls": 0}))


if __name__ == "__main__":
    main()
