"""Reviewed exchange -> per-stay typed rules. No automatic model extraction here."""
from .extraction_bridge import validate_exchange
from .typed_rules import rule_from_unit, validate_typed


def compile_exchange(exchange, annotations):
    errors = validate_exchange(exchange)
    if errors:
        raise ValueError(",".join(errors))
    ids = [u["unit_id"] for u in exchange["evidence_units"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_extraction_unit")
    rules, quarantined, stays = [], [], set()
    for unit in exchange["evidence_units"]:
        review = annotations.get(unit["unit_id"], {})
        if review.get("original_anchor_verified") and exchange["source_access"] != "permitted_source_checked":
            raise ValueError("anchor_verification_without_permitted_source_access")
        if not review.get("stay_id") or not review.get("reviewer") or review.get("status") not in {"human_checked_summary", "source_checked"}:
            quarantined.append({"unit_id": unit["unit_id"], "reason": "stay_or_explicit_human_review_missing"})
            continue
        stays.add(review["stay_id"])
        rule = rule_from_unit(unit, exchange["agent_id"], review)
        rule["stay_id"] = review["stay_id"]
        rule["reviewer"] = review["reviewer"]
        # Preserve evaluation-aspect boundaries. Unknown/mixed/price-only
        # evaluation remains context, not an overall venue preference.
        rules.append(rule)
    if len(stays) > 1:
        raise ValueError("multiple_stays_require_separate_persona_inputs")
    result = {"version": "reviewed_exchange_bridge_v1", "rules": rules, "quarantined_units": quarantined,
              "stay_id": next(iter(stays), None), "raw_text_extraction_verified": False}
    errors = validate_typed(result)
    if errors:
        raise ValueError(",".join(errors))
    return result
