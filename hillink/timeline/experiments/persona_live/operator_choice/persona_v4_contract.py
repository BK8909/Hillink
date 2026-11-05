"""Draft cross-reference/stage validator; never creates a populated persona V4."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("persona_profile_v4_draft.schema.json")


def validate(value: dict, public_share=False) -> list[str]:
    import jsonschema
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = ["schema:" + "/".join(map(str, error.absolute_path)) for error in jsonschema.Draft202012Validator(schema).iter_errors(value)]
    if errors:
        return sorted(set(errors))
    if public_share and value["sharing_level"] != "deidentified_research":
        errors.append("restricted_input_not_for_public_share")
    indexes = {}
    for collection, id_field in (("posts", "post_id"), ("visits", "visit_id"), ("experiences", "experience_id"), ("purchases", "purchase_id"), ("evidence", "evidence_id"), ("claims", "claim_id")):
        ids = [row[id_field] for row in value[collection]]
        if len(ids) != len(set(ids)):
            errors.append("duplicate_id:" + collection)
        indexes[collection] = dict(zip(ids, value[collection]))
    posts, evidence, claims = indexes["posts"], indexes["evidence"], indexes["claims"]
    for post in posts.values():
        if post["author_link_status"] == "verified" and not post["author_link_ref"]:
            errors.append("verified_author_link_requires_reference")
    for visit in value["visits"]:
        if not set(visit["post_ids"]) <= posts.keys():
            errors.append("visit_unknown_post")
        if (visit["visit_date"] is None) != (visit["date_precision"] == "unknown"):
            errors.append("unknown_date_cannot_be_fixed")
        if not set(visit["date_evidence_refs"]) <= evidence.keys():
            errors.append("visit_date_evidence_unknown")
        if visit["visit_date"] is not None and not any(evidence.get(ref, {}).get("support_role") == "visit_date" for ref in visit["date_evidence_refs"]):
            errors.append("publication_metadata_is_not_visit_date")
    for item in evidence.values():
        post = posts.get(item["post_id"])
        if post is None:
            errors.append("evidence_unknown_post")
            continue
        if post["access_status"] == "unavailable":
            errors.append("evidence_from_unavailable_source")
        elif post["access_status"] == "metadata_only" and (item["modality"] != "metadata" or item["support_role"] != "metadata"):
            errors.append("body_or_image_evidence_requires_source_access")
        elif item["modality"] in {"photo", "caption", "receipt"} and post["access_status"] != "text_and_media_available":
            errors.append("visual_evidence_requires_media_access")
    for event in value["experiences"]:
        if not set(event["post_ids"]) <= posts.keys() or (event["visit_id"] is not None and event["visit_id"] not in indexes["visits"]):
            errors.append("experience_link_unknown")
        if not set(event["evidence_refs"]) <= evidence.keys():
            errors.append("experience_evidence_unknown")
        if event["participation_status"] == "observed_participation" and not event["evidence_refs"]:
            errors.append("participation_requires_evidence")
        if event["participation_status"] == "observed_participation" and not any(evidence.get(ref, {}).get("support_role") in {"participation", "post_appraisal", "revisit", "first_visit_statement"} for ref in event["evidence_refs"]):
            errors.append("metadata_or_preference_is_not_actual_participation")
        required_role = {"explicit_first": "first_visit_statement", "explicit_repeat": "revisit"}.get(event["first_visit_status"])
        if required_role and not any(evidence.get(ref, {}).get("support_role") == required_role for ref in event["evidence_refs"]):
            errors.append("first_or_repeat_requires_direct_context")
        if any(evidence.get(ref, {}).get("post_id") not in event["post_ids"] for ref in event["evidence_refs"]):
            errors.append("experience_post_and_evidence_mismatch")
    purchase_roots = set()
    for purchase in value["purchases"]:
        if not set(purchase["experience_ids"]) <= indexes["experiences"].keys() or not set(purchase["evidence_refs"]) <= evidence.keys():
            errors.append("purchase_link_unknown")
        if purchase["status"] in {"documented_order", "payment_verified"} and not purchase["evidence_refs"]:
            errors.append("purchase_requires_evidence")
        if purchase["status"] in {"documented_order", "payment_verified"} and not any(evidence.get(ref, {}).get("support_role") in {"purchase_record", "payment_record"} for ref in purchase["evidence_refs"]):
            errors.append("participation_is_not_purchase_record")
        if purchase["status"] == "payment_verified" and purchase["amount_kind"] != "final_paid":
            errors.append("order_or_list_price_is_not_final_payment")
        if purchase["status"] == "payment_verified" and not any(evidence.get(ref, {}).get("support_role") == "payment_record" for ref in purchase["evidence_refs"]):
            errors.append("order_record_is_not_payment_proof")
        if purchase["amount"] is not None and purchase["currency"] is None:
            errors.append("amount_requires_currency")
        roots = {evidence[ref]["source_root"] for ref in purchase["evidence_refs"] if ref in evidence}
        if purchase["status"] in {"documented_order", "payment_verified"} and roots & purchase_roots:
            errors.append("duplicate_purchase_source_reconcile_records")
        if purchase["status"] in {"documented_order", "payment_verified"}:
            purchase_roots |= roots
    visiting = set()
    def source_refs(claim_id):
        if claim_id in visiting:
            errors.append("cyclic_claim_derivation")
            return set()
        if claim_id not in claims:
            errors.append("claim_derivation_unknown")
            return set()
        visiting.add(claim_id)
        claim = claims[claim_id]
        refs = set(claim["evidence_refs"])
        for base in claim["derived_from"]:
            refs |= source_refs(base)
        visiting.remove(claim_id)
        return refs
    for claim in claims.values():
        refs = source_refs(claim["claim_id"])
        if not refs <= evidence.keys():
            errors.append("claim_evidence_unknown")
        sources = [evidence[ref] for ref in refs if ref in evidence]
        if claim["epistemic_status"] != "unknown" and not sources:
            errors.append("claim_requires_evidence")
        if claim["epistemic_status"] != "unknown" and sources and all(e["support_role"] == "metadata" for e in sources):
            errors.append("metadata_cannot_establish_personal_trait")
        if claim["dimension"] == "prepurchase_criteria" and claim["epistemic_status"] != "unknown" and not any(e["support_role"] == "prepurchase_decision" for e in sources):
            errors.append("post_appraisal_cannot_become_prepurchase_criterion")
        if claim["epistemic_status"] in {"observed_fact", "direct_expression"}:
            required_role = {"new_experience_trial": "first_visit_statement", "post_appraisal": "post_appraisal",
                             "specific_preference": "preference", "revisit_expression": "revisit"}.get(claim["dimension"])
            if required_role and not any(e["support_role"] == required_role for e in sources):
                errors.append("direct_claim_requires_matching_source_role")
        source_posts = [posts[e["post_id"]] for e in sources if e["post_id"] in posts]
        if claim["scope"] == "author_provisional" and any(p["author_link_status"] == "unconfirmed" for p in source_posts):
            errors.append("unconfirmed_author_posts_cannot_merge_as_persona")
        if claim["review"]["status"] == "human_checked":
            if not claim["review"]["reviewer_ref"] or any(e["anchor_status"] != "verified_anchor" for e in sources):
                errors.append("checked_claim_requires_reviewer_and_verified_anchors")
            if claim["scope"] == "author_provisional" and any(p["author_link_status"] != "verified" for p in source_posts):
                errors.append("checked_author_claim_requires_verified_author_link")
    return sorted(set(errors))


def inventory_counts(value):
    errors = validate(value)
    if errors:
        raise ValueError("invalid_draft_contract:" + ",".join(errors))
    return {"observed_post_records": len(value["posts"]),
            "body_accessible_posts": sum(p["access_status"] in {"text_available", "text_and_media_available"} for p in value["posts"]),
            "verified_visit_clusters": sum(v["link_status"] == "verified" for v in value["visits"]),
            "uncertain_visit_clusters": sum(v["link_status"] != "verified" for v in value["visits"]),
            "actual_participation_experiences": sum(e["participation_status"] == "observed_participation" for e in value["experiences"]),
            "documented_orders": sum(p["status"] == "documented_order" for p in value["purchases"]),
            "verified_final_payments": sum(p["status"] == "payment_verified" for p in value["purchases"])}
