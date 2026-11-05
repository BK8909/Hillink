"""Population evidence stays outside personal memory and requires an explicit match."""
from __future__ import annotations

import json
from pathlib import Path

REGISTRY = Path(__file__).with_name("population_priors.json")
REQUIRED = {"prior_id", "source_url", "publisher", "survey_period", "country", "sample",
            "measured_question", "observed_tendency", "effect_range", "population",
            "applicability", "scenarios", "review_status", "limitations"}


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def validate_prior(p: dict) -> list[str]:
    missing = REQUIRED - p.keys()
    issues = ["missing_prior_metadata:" + ",".join(sorted(missing))] if missing else []
    if p.get("review_status") == "verified":
        for key in ("source_url", "survey_period", "country", "sample", "measured_question", "observed_tendency", "effect_range", "population", "applicability"):
            if not p.get(key):
                issues.append("incomplete_verified_prior:" + key)
    return issues


def select_priors(registry: dict, card: dict, scenario: str) -> tuple[list[dict], list[dict]]:
    """No age/nationality/household class is inferred to fit a survey group."""
    accepted, excluded = [], []
    facts = {"party_composition": card["a_card"]["party"]["composition"],
             "party_size": card["a_card"]["party"]["size"]}
    for p in registry.get("priors", []):
        errors = validate_prior(p)
        if p.get("review_status") != "verified":
            errors.append("not_verified")
        if scenario not in p.get("scenarios", []):
            errors.append("wrong_measurement_context")
        for field, expected in p.get("applicability", {}).items():
            fact = facts.get(field, {})
            if fact.get("value") != expected or fact.get("provenance") != "observed":
                errors.append("unverified_population_match:" + field)
        if errors:
            excluded.append({"prior_id": p.get("prior_id"), "reasons": errors})
        else:
            accepted.append({**p, "matching_basis": {k: facts[k] for k in p["applicability"]},
                             "conflict_with_personal_evidence": "not_automatically_adjudicated",
                             "individual_preference": False})
    return accepted, excluded
