"""Structural evidence checks, not automatic judgments of human plausibility."""
from __future__ import annotations

import json
from pathlib import Path

LAYERS = ("personal_observation", "personal_inference", "population_prior", "situational_judgment")
DECISION_SCHEMA = json.loads(Path(__file__).with_name("decision.schema.json").read_text(encoding="utf-8"))


def evaluate(output: dict, cell: dict) -> dict:
    import jsonschema
    errors = ["schema:" + e.message for e in jsonschema.Draft202012Validator(DECISION_SCHEMA).iter_errors(output)]
    if errors:
        return {"errors": errors, "review_signals": [], "human_review_status": "pending"}
    payload = cell["payload"]
    options = {o["code"]: o for o in payload["current_context"]["stage"]["options"]}
    if output["option_code"] not in options:
        errors.append("unavailable_option")
    ids = {i for r in payload["personal_evidence"] for i in r["evidence_ids"]}
    direct = {i for r in payload["personal_evidence"] if r["provenance"]["layer"] == "observed" for i in r["evidence_ids"]}
    prior_ids = {p["prior_id"] for p in payload["population_prior"]}
    allowed = {"personal_observation": direct, "personal_inference": ids,
               "population_prior": prior_ids, "situational_judgment": set(payload["current_context"]["assumption_ids"])}
    signals = []
    for layer in LAYERS:
        reason = output["basis"][layer]
        if set(reason["ids"]) - allowed[layer]:
            errors.append("unsupported_citation:" + layer)
        if reason["text"] and layer != "situational_judgment" and not reason["ids"]:
            errors.append("uncited_evidence_claim:" + layer)
        if not reason["text"] and reason["contribution"] != "not_used":
            errors.append("empty_reason_contributes:" + layer)
        if reason["text"] and reason["contribution"] == "not_used":
            errors.append("reason_marked_unused:" + layer)
    if output["basis"]["population_prior"]["text"] and not prior_ids:
        errors.append("population_claim_without_input")
    for alternative in output["alternatives"]:
        if alternative["option_code"] not in options or alternative["option_code"] == output["option_code"]:
            errors.append("invalid_alternative")
    if output["basis"]["personal_observation"]["text"]:
        signals.append("card_summary_is_not_original_anchor:check_claim_scope_and_polarity")
    if output["basis"]["population_prior"]["text"]:
        signals.append("review_ecological_inference_and_personal_contradictions")
    return {"errors": errors, "review_signals": signals, "human_review_status": "pending",
            "semantic_support": "requires_independent_review", "predicted_probability": None}


def compare(before: dict, after: dict) -> dict:
    """No desired direction and no diversity score. Unchanged choices are valid."""
    return {"before": before["option_code"], "after": after["option_code"],
            "changed": before["option_code"] != after["option_code"],
            "estimated_cost_before_krw": before["est_cost_krw"], "estimated_cost_after_krw": after["est_cost_krw"],
            "cost_difference_krw": (after["est_cost_krw"] - before["est_cost_krw"]
                                    if before["est_cost_krw"] is not None and after["est_cost_krw"] is not None else None),
            "plausibility": "human_review_pending", "stay_outcome": "not_measured_by_single_block"}
