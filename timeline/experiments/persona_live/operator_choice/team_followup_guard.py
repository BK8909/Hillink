"""Research-only release/split checks. Does NOT alter libraries, UI or evaluation sets."""
from __future__ import annotations

REPORTED_SEALED_IDS = {"REV-bea98b3d8f343905fd1f", "REV-43526bdbea049cbe0963"}


def identity(row):
    return row.get("review_id") or row.get("source_id") or row.get("id")


def release_preview(records, metadata=(), exposed_ids=()):
    """ID-only preview, including author/series risks, never a public author-key export.

    WH numbers are not identities: V1 and V2 reuse them. Relations are only
    quarantine signals, NOT proof that two records share a visit.
    """
    by_id = {identity(r): r for r in metadata if identity(r)}
    seeds = REPORTED_SEALED_IDS | set(exposed_ids)
    authors = {by_id[i].get("author_key") for i in seeds if i in by_id and by_id[i].get("author_key")}
    held, allowed = [], []
    for row in records:
        rid = identity(row)
        meta = by_id.get(rid, {})
        reasons = []
        if not rid:
            reasons.append("missing_stable_identity")
        if rid in REPORTED_SEALED_IDS:
            reasons.append("reported_sealed_overlap")
        if rid in exposed_ids:
            reasons.append("human_read_development_candidate")
        if meta.get("author_key") and meta["author_key"] in authors and rid not in seeds:
            reasons.append("same_author_quarantine_not_same_stay_proof")
        relations = meta.get("same_stay_candidates", []) + meta.get("author_series", [])
        if any((r.get("review_id") if isinstance(r, dict) else r) in seeds for r in relations):
            reasons.append("reported_relation_requires_review")
        if rid is None or reasons:
            held.append({"review_id": rid, "reasons": reasons})
        else:
            allowed.append(rid)
    return {"mode": "preview_only_not_installed_in_runtime", "allowed_ids": allowed, "held": held,
            "denominator_policy": "no_permanent_reclassification_without_user_approval",
            "independent_eval_eligibility": "not_established_by_release_allowance"}


def inspect_model_input(packet, additional_blocked_ids=()):
    """Exact-ID exposure check, not a semantic/n-gram absence guarantee."""
    import json
    blob = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    found = sorted(i for i in REPORTED_SEALED_IDS | set(additional_blocked_ids) if i in blob)
    return {"blocked_ids_found": found, "pass_exact_id_check": not found,
            "semantic_leakage_absence_proven": False}


def split_advice(*, sealed_overlap=False, human_read=None, model_input=None,
                 same_author_risk=False, same_stay_risk=False, provenance_verified=False):
    if sealed_overlap or same_author_risk or same_stay_risk:
        return "quarantine_pending_user_split_decision"
    if human_read is True or model_input is True:
        return "development_candidate_conservative_not_training_claim"
    if human_read is False and model_input is False and provenance_verified:
        return "independent_evaluation_candidate_requires_approval"
    return "unresolved_exposure_or_provenance"


def vista_party_sensitivity(adults, children, *, policy):
    """No age imputation; admission assumption is not a hotel ruling."""
    if adults != 2 or len(children) != 3:
        raise ValueError("sandbox_scoped_to_two_adults_three_children")
    if policy == "experimental_all_admitted":
        return {"admission": "assumed_allowed", "provenance": "CTX-ADMISSION", "total_cost_krw": None,
                "official_eligibility_verified": False}
    if policy != "official_conditions_only":
        raise ValueError("unknown_admission_policy")
    return {"admission": "unresolved_requires_hotel_confirmation", "total_cost_krw": None,
            "official_eligibility_verified": False, "unknowns": ["child_ages", "extra_child_eligibility",
                "extra_charge", "guardian_ratio"], "not_inferred": ["fifth_person_forbidden", "adult_child_rotation"]}
