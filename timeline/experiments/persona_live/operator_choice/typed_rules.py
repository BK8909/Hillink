"""Versioned semantic refinement of the frozen 66 candidates; no trait fitting."""
from __future__ import annotations

from copy import deepcopy

from .rules import catalogue

# Predicates refer to explicit option attributes, not names or customer IDs.
PREFERENCE_PREDICATES = {
    "quiet_rest": ("rest", ["stay", "activity"]),
    "on_property_convenience": ("onsite", ["itinerary", "stay", "activity"]),
    "quiet_conversation": ("quiet", ["dining"]),
    "private_room": ("private", ["dining"]),
    "view_enjoyment": ("view", ["breakfast_seating"]),
    "low_view_priority": ("view", ["room_view"]),
    "view_walk": ("view", ["evening_walk"]),
    "view_seating": ("view", ["buffet"]),
    "window_seat": ("view", ["breakfast_seating"]),
    "window_seat_enjoyment": ("view", ["buffet"]),
    "river_view_seat": ("view", ["restaurant_seating"]),
    "river_view_room": ("view", ["room_view"]),
    "river_view_hotel": ("view", ["hotel_choice"]),
}
GOALS = {"indoor_pool": "indoor_water", "riverpark": "outdoor_water", "quiet_rest": "rest",
         "conversation": "conversation", "dining": "dining", "hotel_exploration": "exploration",
         "hotel_facility_exploration": "exploration", "morning_facilities": "morning_activity"}


def refine(cards=None) -> dict:
    from persona_sheet import load_cards
    cards = load_cards() if cards is None else cards
    old = catalogue(cards)
    result = []
    for r in old["rules"]:
        card = cards[r["agent_id"]]["a_card"]
        path = r["provenance"]["card_path"]
        kind, predicate = "context_only", None
        if ".observed_events[" in path:
            kind = "behavior_observation"
        elif ".explicit_preferences[" in path:
            kind = "explicit_preference"
            feature = r["evaluated_aspect"]["aspect"]
            if feature in PREFERENCE_PREDICATES:
                attribute, domains = PREFERENCE_PREDICATES[feature]
                # A low priority is not avoidance; a visit is not liking.
                if feature != "low_view_priority":
                    predicate = {"attribute": attribute, "expected": True, "domains": domains,
                                 "direction": "oppose" if r["evaluated_aspect"]["polarity"] == "avoid" else "support"}
            elif feature == "repeat_visit":
                predicate = {"attribute": "venue", "expected": r["evaluated_aspect"]["target"],
                             "domains": ["dining"], "direction": "support"}
        elif path == "a_card.purpose":
            kind = "choice_motivation"
            goals = [GOALS[g] for g in card["purpose"].get("value") or [] if g in GOALS]
            if goals:
                predicate = {"goals": goals, "requires": "goal_continuity", "direction": "support"}
        elif ".constraints[" in path:
            kind = "contextual_constraint"
        usable = bool(predicate) and r["verification_status"] != "insufficient"
        result.append({
            "rule_id": r["rule_id"], "agent_id": r["agent_id"], "kind": kind,
            "observed_statement": r["observed_behavior"], "evaluated_aspect": r["evaluated_aspect"],
            "evidence_ids": r["evidence_ids"], "source_verification": deepcopy(r["provenance"]),
            "verification_status": "anchor_pending" if r["verification_status"] != "insufficient" else "excluded_evaluator_only",
            "predicate": predicate, "decision_usable": usable,
            "expected_direction": predicate["direction"] if usable else "none",
            "strength_basis": ("card_stated_preference" if kind == "explicit_preference" else "bounded_goal_transfer") if usable else "no_directional_evidence",
            "transfer_scope": r["applicable_context"],
            "limitations": ["원문 앵커 직접 재검증 없음", "과거 목적의 이번 적용은 goal_continuity 가정이 있을 때만" if kind == "choice_motivation" else "기록된 대상·측면·맥락 밖으로 확대 금지"],
            "actual_conflicts": [], "reported_conflicts": [],
            "unknowns": list(card["unknowns"]),
            "general_cautions": ["이용 사실은 긍정 선호가 아니다", "미선택은 비선호가 아니다"],
        })
    # Reporter leads remain outside the inference/personal-memory payload.
    for r in result:
        r["reported_conflicts"] = [deepcopy(x) for x in old["review_leads"]
                                   if x["agent_id"] == r["agent_id"] and x["target"] == r["evaluated_aspect"]["target"]]
    return {"version": "typed_rules_v2", "rules": result, "source_access": "cards_only",
            "originals_verified_this_stage": 0, "source_card_sha256": old["input_sha256"]}


def rule_from_unit(unit: dict, agent_id: str, review: dict) -> dict:
    """Bridge a reviewed extraction unit; automatic drafts never become preferences."""
    aspect = unit["evaluated_aspect"]
    verified = bool(review.get("original_anchor_verified") and review.get("reviewer") and unit["evidence_ids"])
    if unit.get("original_anchor_verified") and not verified:
        raise ValueError("original_anchor_verification_requires_review_and_ids")
    polarity = aspect["polarity"]
    approved = review.get("status") in {"human_checked_summary", "source_checked"}
    usable = approved and polarity in {"positive", "negative"} and aspect.get("aspect", "overall") == "overall"
    return {"rule_id": unit["unit_id"], "agent_id": agent_id,
            "kind": "explicit_evaluation" if polarity != "unknown" else "behavior_observation",
            "observed_statement": unit["observed_behavior"], "evaluated_aspect": aspect,
            "evidence_ids": list(unit["evidence_ids"]),
            "source_verification": {"original_anchor_verified": verified, "source_access": "permitted_source_checked" if verified else "unavailable"},
            "verification_status": "source_verified" if verified else "anchor_pending" if approved else "automatic_draft",
            "predicate": {"attribute": "venue", "expected": aspect["target"], "domains": [unit["context"].get("domain", "activity")],
                          "direction": "support" if polarity == "positive" else "oppose"} if usable else None,
            "decision_usable": usable, "expected_direction": "support" if polarity == "positive" and usable else "oppose" if usable else "none",
            "strength_basis": "reviewed_aspect_evaluation" if usable else "no_directional_evidence",
            "transfer_scope": {"scope": aspect["target"], "transfer_limit": "같은 평가 대상과 측면에만 적용"},
            "limitations": [], "actual_conflicts": [], "reported_conflicts": [], "unknowns": [], "general_cautions": []}


def validate_typed(data: dict) -> list[str]:
    issues = []
    ids = set()
    for r in data["rules"]:
        if r["rule_id"] in ids:
            issues.append("duplicate_rule")
        ids.add(r["rule_id"])
        if r["kind"] == "behavior_observation" and r["decision_usable"]:
            issues.append("visit_promoted_to_preference")
        if r["decision_usable"] and (not r["predicate"] or not r["evidence_ids"] or r["verification_status"] in {"automatic_draft", "excluded_evaluator_only"}):
            issues.append("unusable_rule_promoted")
        if r["verification_status"] == "source_verified" and not r["source_verification"]["original_anchor_verified"]:
            issues.append("unverified_anchor_promoted")
    return issues
