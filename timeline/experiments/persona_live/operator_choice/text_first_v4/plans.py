"""Composable fictional action plans, NOT completed behaviors or an LLM agent."""
from __future__ import annotations


def minute(clock):
    hour, mins = map(int, clock.split(":"))
    if not 0 <= hour <= 23 or not 0 <= mins <= 59:
        raise ValueError("invalid_clock")
    return hour * 60 + mins


def build_plan_candidates(profile, environment):
    """Wine tasting need not replace a full meal. Never selects a fixed winner.

    Operator supplies hypothetical costs, time windows, capacities, availability.
    Profile evidence supports relevance, not guaranteed attendance/alcohol use.
    """
    if not environment.get("fictional"):
        raise ValueError("explicit_fictional_environment_required")
    party_size = environment["party_size"]
    if type(party_size) is not int or party_size < 1:
        raise ValueError("invalid_party_size")
    activities = {r["activity_id"]: r for r in environment["activities"]}
    if len(activities) != len(environment["activities"]):
        raise ValueError("duplicate_activity_id")
    for activity in activities.values():
        if minute(activity["end"]) <= minute(activity["start"]) or type(activity["price_per_person_krw"]) is not int or activity["price_per_person_krw"] < 0:
            raise ValueError("invalid_activity_window_or_price")
        if activity["purpose"] not in {"experience_tasting_atmosphere", "meal", "rest"}:
            raise ValueError("purpose_required_separately_from_meal_size")
    plans = []
    for specification in environment["plan_templates"]:
        steps = [activities[key] for key in specification["activity_ids"]]
        reasons = []
        for i, step in enumerate(steps):
            if not step["available"]:
                reasons.append("activity_unavailable:" + step["activity_id"])
            if step["remaining_capacity"] is not None and step["remaining_capacity"] < party_size:
                reasons.append("insufficient_capacity:" + step["activity_id"])
            if step["reservation_required"] and (step["booking_closes_at"] is None or minute(environment["now"]) + environment["booking_processing_minutes"] > minute(step["booking_closes_at"])):
                reasons.append("booking_window_unusable:" + step["activity_id"])
            if minute(step["start"]) < minute(environment["now"]):
                reasons.append("activity_already_started:" + step["activity_id"])
            if i and minute(steps[i - 1]["end"]) + environment["transfer_minutes"] > minute(step["start"]):
                reasons.append("activity_time_conflict")
        supports = []
        for trait, details in profile["derived_traits"].items():
            if details["strength_score"] and any(trait in step["relevant_traits"] for step in steps):
                supports.append({"trait": trait, "strength_score": details["strength_score"],
                                 "evidence_ids": sorted({e for c in details["contributions"] for e in c["evidence_ids"]})})
        plans.append({"plan_id": specification["plan_id"], "activity_ids": specification["activity_ids"],
                      "feasible": not reasons, "constraints": sorted(set(reasons)),
                      "party_total_krw": sum(s["price_per_person_krw"] for s in steps) * party_size,
                      "includes_meal": any(s["purpose"] == "meal" for s in steps),
                      "profile_relevance": supports, "decision_status": "candidate_not_selected",
                      "reservation_attempted": False, "consumption_completed": False,
                      "inference_limits": ["no confirmed individual wine preference implied", "current context and opportunity costs still need judgment"]})
    return {"version": "text_first_v4_plan_candidates_0.1", "persona_id": profile["persona_id"],
            "plans": plans, "winner": None, "model_calls": 0, "human_review": "pending", "demo_approved": False}


def fictional_wine_environment():
    def activity(key, start, end, cost, purpose, traits, reservation=False):
        return {"activity_id": key, "start": start, "end": end, "price_per_person_krw": cost,
                "purpose": purpose, "relevant_traits": traits, "available": True, "remaining_capacity": 10,
                "reservation_required": reservation, "booking_closes_at": "17:30" if reservation else None}
    return {"fictional": True, "now": "17:00", "party_size": 2, "transfer_minutes": 10, "booking_processing_minutes": 5,
            "activities": [activity("EVENT", "18:00", "19:00", 60000, "experience_tasting_atmosphere", ["new_experience_trial", "seasonal_event_engagement", "space_atmosphere", "alcohol_familiarity"], True),
                           activity("SHORT_TASTING", "18:00", "18:20", 20000, "experience_tasting_atmosphere", ["seasonal_event_engagement", "space_atmosphere"]),
                           activity("DINNER", "19:15", "20:15", 40000, "meal", ["food_engagement"]),
                           activity("ROOM_MEAL_REST", "18:00", "19:00", 20000, "meal", ["food_engagement"])],
            "plan_templates": [{"plan_id": "EVENT_THEN_DINNER", "activity_ids": ["EVENT", "DINNER"]},
                               {"plan_id": "SHORT_TASTING_THEN_DINNER", "activity_ids": ["SHORT_TASTING", "DINNER"]},
                               {"plan_id": "SKIP_EVENT_ROOM_MEAL", "activity_ids": ["ROOM_MEAL_REST"]}]}
