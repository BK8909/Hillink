"""Human-adjudicated semantic evaluation, separate from lexical window coverage.

This module computes submitted judgments; it does not issue human approval or
authenticate reviewers, and it never reads sealed Gold/evaluation datasets.
"""
from .common import digest, require_opaque

VERDICTS={"supported","partial","unsupported","wrong_actor","wrong_time_or_stage","overgeneralized"}


def review_template(candidate_facts, reference_inventory):
    return {"reference_sha256_private":digest(reference_inventory),"human_review":"pending",
            "rows":[{"candidate_id":f["fact_id"],"verdict":None,"matched_reference_ids":[],
                     "semantic_unit_id":None,
                     "actor_correct":None,"stage_correct":None,"scope_correct":None,
                     "reason":None,"reviewer_ref":None} for f in candidate_facts],
            "missing_reference_ids":[],"review_minutes":None,
            "post_adjudications":[{"post_id":post,"compensation_status":None,"voluntary_ad_response_preserved":None,
                                     "false_exclusion_or_missed_ad":None,"reason":None,"reviewer_ref":None} for post in reference_inventory.get("source_post_ids",[])],
            "experience_link_adjudications":[],"free_trait_and_context_rule_adjudications":[],
            "effort_log":{"collection_minutes":None,"semantic_extraction_minutes":None,"source_linking_minutes":None,
                          "human_review_minutes":None,"photo_note_minutes":None,"actual_token_or_session_usage":None,
                          "reported_api_cost":None,"measurement_ref":None,"not_automatically_estimated":True},
            "semantic_metrics":None,"demo_approved":False}


def semantic_summary(candidate_facts,reference_inventory,review):
    if review.get("reference_sha256_private") != digest(reference_inventory):
        raise ValueError("reference_inventory_changed_after_review_preparation")
    if reference_inventory.get("origin") == "developer_selected_62" or reference_inventory.get("used_for_method_development",True):
        return {"semantic_metrics":None,"reason":"development_source_checks_not_independent_quality_labels",
                "human_review":"not_certified_by_software","demo_approved":False}
    if reference_inventory.get("origin") != "human_source_inventory" or reference_inventory.get("status") != "reviewed":
        return {"semantic_metrics":None,"reason":"human_source_inventory_not_ready","demo_approved":False}
    if review.get("human_review") != "submitted":
        return {"semantic_metrics":None,"reason":"human_semantic_judgments_pending","demo_approved":False}
    require_opaque(reference_inventory.get("persona_id"))
    source_posts=set(reference_inventory.get("source_post_ids",[]))
    if not source_posts or any(f.get("persona_id")!=reference_inventory["persona_id"] or f.get("post_id") not in source_posts for f in candidate_facts):
        raise ValueError("semantic_review_author_or_source_scope_mismatch")
    references=reference_inventory.get("units",[])
    ref_ids={r["reference_id"] for r in references}
    if len(ref_ids)!=len(references):
        raise ValueError("duplicate_reference_unit")
    if any(type(r.get("coverage_eligible")) is not bool for r in references):
        raise ValueError("reference_coverage_scope_must_be_declared")
    candidate_ids={f["fact_id"] for f in candidate_facts}
    if len(candidate_ids)!=len(candidate_facts):
        raise ValueError("duplicate_candidate_unit")
    rows=review.get("rows",[])
    if len(rows)!=len(candidate_ids) or {r["candidate_id"] for r in rows}!=candidate_ids:
        raise ValueError("each_candidate_needs_one_semantic_review")
    covered=set(); supported=0; semantic_units=set()
    for row in rows:
        require_opaque(row.get("reviewer_ref"))
        if row.get("verdict") not in VERDICTS or not row.get("reason"):
            raise ValueError("semantic_verdict_and_reason_required")
        if any(type(row.get(key)) is not bool for key in ("actor_correct","stage_correct","scope_correct")):
            raise ValueError("separate_actor_stage_scope_judgments_required")
        links=set(row.get("matched_reference_ids",[]))
        if not links<=ref_ids:
            raise ValueError("semantic_link_to_unknown_reference")
        if row["verdict"]=="supported":
            require_opaque(row.get("semantic_unit_id"))
            if not all(row[k] for k in ("actor_correct","stage_correct","scope_correct")):
                raise ValueError("supported_verdict_conflicts_with_error_axes")
            supported+=1; covered.update(links); semantic_units.add(row["semantic_unit_id"])
    eligible={r["reference_id"] for r in references if r["coverage_eligible"]}
    missing=eligible-covered
    if set(review.get("missing_reference_ids",[]))!=missing:
        raise ValueError("missing_actions_require_explicit_review")
    metrics={"candidate_supported_fraction":supported/len(candidate_ids) if candidate_ids else None,
             "reviewed_inventory_coverage":len(covered&eligible)/len(eligible) if eligible else None,
             "candidate_count":len(candidate_ids),"covered_reference_units":len(covered&eligible),
             "supported_unique_semantic_units":len(semantic_units),"duplicate_supported_candidates":supported-len(semantic_units),
             "eligible_reference_units":len(eligible),"missing_reference_ids":sorted(missing),
             "error_counts":{v:sum(r["verdict"]==v for r in rows) for v in sorted(VERDICTS-{"supported"})}}
    return {"semantic_metrics":metrics,"judgment_source":"submitted_human_adjudications_not_machine_truth",
            "reviewer_identity_authenticated":False,"human_review":"submitted_not_automatically_approved",
            "independent_quality_established":False,
            "holdout_protocol_eligible":reference_inventory.get("frozen_before_extraction") is True and reference_inventory.get("author_role")=="holdout_new_author",
            "extraction_stability_requires_second_independent_extraction":True,"demo_approved":False}


def compare_reviewed_runs(first,second,reference_inventory,first_review,second_review):
    summaries=[semantic_summary(facts,reference_inventory,review) for facts,review in ((first,first_review),(second,second_review))]
    if any(summary["semantic_metrics"] is None for summary in summaries):
        return {"reviewed_reference_coverage_jaccard":None,"reason":"semantic_reviews_or_reference_pending","independent_stability_established":False}
    def covered(review):
        return {ref for row in review["rows"] if row["verdict"]=="supported" for ref in row["matched_reference_ids"]}
    a,b=covered(first_review),covered(second_review)
    return {"reviewed_reference_coverage_jaccard":len(a&b)/len(a|b) if a|b else None,
            "first_only_reference_ids":sorted(a-b),"second_only_reference_ids":sorted(b-a),
            "all_free_traits_semantically_compared":False,"session_independence_verified":False,
            "same_source_and_method_verified_by_this_function":False,
            "independent_stability_established":False,"source":"submitted_human_semantic_matches_not_window_overlap"}
