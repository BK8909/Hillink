"""Generic decision adapter for author-profile claims; outputs are not probabilities."""
from __future__ import annotations

from copy import deepcopy
from .decision_v2 import decide


def signals_from_profile(profile: dict, scenario_id: str, condition: str, input_mode: str = "exploratory_research") -> list[dict]:
    """Translate only explicit, scope-matched profile mappings into V2 scorer signals.

    A claim contributes only where its mapping names this scenario/condition.
    Unmapped conditions stay unknown; there are no persona-ID branches.
    """
    if input_mode not in {"exploratory_research", "verified_or_demo"}:
        raise ValueError("unknown_input_mode:" + input_mode)
    signals=[]
    for claim in profile.get("claims", []):
        if not claim.get("decision_usable", False):
            continue
        if input_mode == "verified_or_demo" and claim.get("review") != "human_review_approved":
            continue
        for mapping in claim.get("decision_mappings", []):
            if mapping.get("scenario") != scenario_id or condition not in mapping.get("conditions", []):
                continue
            if mapping.get("status") == "unknown_for_condition":
                continue
            for option, direction in mapping.get("option_directions", {}).items():
                signals.append({"signal_id":f"{claim['claim_id']}:{scenario_id}:{condition}:{option}",
                    "evidence_root":mapping.get("evidence_root", claim["claim_id"]),
                    "category":mapping.get("category", "personal_fit"), "options":[option],
                    "direction":direction, "reliability":mapping["reliability"],
                    "relevance":mapping["relevance"], "basis":mapping["basis"],
                    "source_state":claim.get("review"), "is_probability":False})
    return signals


def compare(options: list[dict], profile: dict, scenario_id: str, condition: str,
            input_mode: str = "exploratory_research") -> dict:
    if input_mode == "verified_or_demo" and profile.get("human_review_status") != "approved":
        return {"method":"profile_fit_v3","selected":None,"status":"blocked_unreviewed_profile",
            "options":[],"signals_used":0,"profile_version":profile.get("profile_version"),
            "scenario":scenario_id,"condition":condition,"human_review":"pending","demo_approved":False}
    signals=signals_from_profile(profile, scenario_id, condition, input_mode)
    result=decide(deepcopy(options), signals)
    result.update({"profile_version":profile.get("profile_version"),"scenario":scenario_id,
        "condition":condition,"input_mode":input_mode,"signals_used":len(signals),
        "interpretation":"exploratory_rank_not_future_behavior_or_probability",
        "human_review":"pending","demo_approved":False})
    return result
