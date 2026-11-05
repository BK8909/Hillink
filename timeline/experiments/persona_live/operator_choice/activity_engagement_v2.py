"""Separates observed commitment from preference; generic effort rubric is an assumption."""
from __future__ import annotations

EFFORT_RUBRIC = {
    "VISTA_POOL": {"preparation": 2, "time": None, "movement": 1, "money": None, "planning": None, "physical": 2, "opportunity_cost": None},
    "GRAND_POOL": {"preparation": 2, "time": None, "movement": 1, "money": None, "planning": None, "physical": 2, "opportunity_cost": None},
    "RIVERPARK": {"preparation": 2, "time": None, "movement": 1, "money": None, "planning": None, "physical": 2, "opportunity_cost": None},
    "SKYARD": {"preparation": 0, "time": None, "movement": None, "money": None, "planning": None, "physical": 0, "opportunity_cost": None},
}

def score_event(event: dict) -> dict:
    place = event.get("place")
    generic = EFFORT_RUBRIC.get(place, {k: None for k in ("preparation", "time", "movement", "money", "planning", "physical", "opportunity_cost")})
    return {"event": event, "activity_class": "water_activity" if "POOL" in str(place) or place == "RIVERPARK" else "view_or_facility_visit" if place == "SKYARD" else "other",
        "observed_participation": True, "observed_preference": None,
        "effort_axes": dict(generic), "effort_rubric_status": "generic_scenario_assumption_not_personal_observation",
        "personal_effort_observed": {"preparation": None, "time": None, "movement": None, "money": None, "planning": None, "physical": None, "opportunity_cost": None},
        "interpretation": "행동 투입 단서이며 긍정 평가·선호 강도가 아님."}

def profile_engagement(profile: dict) -> list[dict]:
    return [score_event({"place": e["value"].get("place"), "kind": e["value"].get("kind"), "evidence_ids": e["evidence_ids"]})
            for e in profile.get("behavioral_commitments", [])]
