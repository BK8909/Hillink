"""Open-vocabulary source facts, discourse context and separated purchase stages."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
import hashlib
import re

from . import VERSION

DIMENSIONS = {"participation_history", "new_experience_trial", "prepurchase_criteria", "post_appraisal", "specific_preference", "revisit_expression"}
KINDS = {"participation", "purchase", "motive", "preference", "appraisal", "expectation", "revisit", "decline", "comparison"}
STAGES = {"reservation_reported", "order_reported", "purchase_reported", "participation_reported", "consumption_reported", "not_applicable"}


def opaque(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", value) is not None


def normalize_facts(document, proposals):
    """The caller's private text is mandatory. Never accepts a card as raw input.

    Exact spans establish alignment, not source authenticity or human approval.
    Model/human descriptions remain private until separately deidentified.
    """
    if document.get("source_class") not in {"authorized_text", "synthetic_fixture"}:
        raise ValueError("authorized_text_or_synthetic_source_required")
    if any(not opaque(document.get(key)) for key in ("post_id", "persona_id")):
        raise ValueError("opaque_document_identity_required")
    text = document["text"]
    result, ids = [], set()
    for supplied in proposals:
        row = deepcopy(supplied)
        for key in ("fact_id", "experience_key", "feature_key"):
            if not opaque(row.get(key)):
                raise ValueError("opaque_fact_experience_feature_keys_required")
        if row["fact_id"] in ids:
            raise ValueError("duplicate_fact_id")
        ids.add(row["fact_id"])
        if row.get("kind") not in KINDS or row.get("dimension") not in DIMENSIONS or row.get("action_stage") not in STAGES:
            raise ValueError("fact_kind_dimension_or_stage_invalid")
        if row.get("actor") not in {"author", "author_inferred", "other", "unknown"}:
            raise ValueError("actor_scope_required")
        if row.get("time_scope") not in {"source_experience", "historical", "future", "recommended", "mixed"}:
            raise ValueError("time_scope_required")
        if row.get("polarity") not in {"positive", "negative", "mixed", "neutral"} or row.get("confidence") not in {"high", "medium", "low"}:
            raise ValueError("polarity_confidence_required")
        anchors = row.get("anchors", [])
        if not anchors:
            raise ValueError("full_source_anchor_required")
        for anchor in anchors:
            start, end = anchor["span"]
            if not 0 <= start < end <= len(text) or text[start:end] != anchor["quote"]:
                raise ValueError("fact_anchor_not_in_source")
        if not row.get("detail") or not isinstance(row["detail"], str):
            raise ValueError("free_detail_required_not_fixed_tag_only")
        if not isinstance(row.get("common_dimensions"), list):
            raise ValueError("later_common_mapping_required_may_be_empty")
        # Local appraisal does not establish a pre-purchase rule by mere relabeling.
        if row["dimension"] == "prepurchase_criteria" and row["kind"] == "appraisal":
            raise ValueError("post_appraisal_is_not_prepurchase_behavior")
        if row["dimension"] == "post_appraisal" and "prepurchase_value" in row["common_dimensions"]:
            raise ValueError("post_appraisal_cannot_map_to_advance_price_aversion")
        if row["kind"] == "purchase" and row["action_stage"] not in {"reservation_reported", "order_reported", "purchase_reported"}:
            raise ValueError("purchase_does_not_prove_attendance")
        if row["kind"] == "participation" and row["action_stage"] not in {"participation_reported", "consumption_reported"}:
            raise ValueError("participation_stage_required")
        row.update(persona_id=document["persona_id"], post_id=document["post_id"], scope=document["scope"],
                   source_class=document["source_class"], review_status="developer_source_check_pending_human_review",
                   source_alignment="exact_text_spans_checked", original_text_private=True)
        row["source_sha256_private"] = hashlib.sha256(text.encode()).hexdigest()
        result.append(row)
    return {"version": VERSION, "persona_id": document["persona_id"], "post_id": document["post_id"],
            "source_class": document["source_class"], "scope": document["scope"], "facts": sorted(result, key=lambda r:r["fact_id"])}


def premium_context(fact):
    """No money-only luxury rule. Units/purpose are independently retained."""
    context = fact.get("purchase_context", {})
    actual = fact["kind"] in {"participation", "purchase"}
    position = context.get("positioning")
    basis = context.get("positioning_basis")
    valid_classification = position == "premium_experience" and basis in {"source_product_category", "reviewed_product_taxonomy"}
    unit = context.get("purchase_unit", "unknown")
    amount = context.get("reported_amount_krw")
    if amount is not None and (type(amount) not in {int, float} or amount < 0):
        raise ValueError("invalid_reported_amount")
    return {"premium_experience_supported": bool(actual and valid_classification and context.get("purpose") in {"experiential", "special_dining", "special_stay"}),
            "reported_amount_krw": amount, "amount_kind": context.get("amount_kind", "unknown"),
            "purchase_unit": unit, "purpose": context.get("purpose", "unknown"),
            "unit_resolved": unit in {"per_person", "per_item", "party_total"},
            "personal_final_payment_verified": False,
            "reason": "product_class_and_actual_purpose_not_absolute_price"}


def explicit_date(value, quote):
    """Publication dates are never a visit-date input to this helper."""
    canonical = date.fromisoformat(value)
    numbers = list(map(int, re.findall(r"\d+", quote)))
    if [canonical.year, canonical.month, canonical.day] != numbers[:3]:
        raise ValueError("explicit_visit_date_not_supported_by_quote")
    return value
