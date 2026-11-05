"""Evaluation plumbing: no fabricated human labels, image gains or generation runs."""
from __future__ import annotations


def compare_media_profiles(text_only, selected_media, measurement=None):
    if text_only["persona_id"] != selected_media["persona_id"] or text_only["source_post_ids"] != selected_media["source_post_ids"]:
        raise ValueError("same_author_same_posts_required_for_media_ablation")
    if text_only["policy_version"] != selected_media["policy_version"] or text_only["policy_weights"] != selected_media["policy_weights"]:
        raise ValueError("hold_aggregation_policy_fixed")
    measurement = measurement or {}
    allowed = {"collection_seconds", "review_seconds", "storage_bytes", "valid_added_evidence", "false_inferences_removed", "false_inferences_added", "behavior_explanation_review", "reviewer_ref"}
    if not measurement.keys() <= allowed:
        raise ValueError("unknown_measurement")
    if any(key in measurement for key in ("valid_added_evidence", "false_inferences_removed", "false_inferences_added", "behavior_explanation_review")) and not measurement.get("reviewer_ref"):
        raise ValueError("human_judgment_requires_actual_reviewer_reference")
    for name in ("collection_seconds", "review_seconds", "storage_bytes", "valid_added_evidence", "false_inferences_removed", "false_inferences_added"):
        if name in measurement and (type(measurement[name]) not in {int, float} or measurement[name] < 0):
            raise ValueError("nonnegative_measurement_required")
    text_refs = {r for refs in text_only["six_dimensions"].values() for r in refs}
    augmented_refs = {r for refs in selected_media["six_dimensions"].values() for r in refs}
    return {"version": "text_first_media_ablation_0.1", "persona_id": text_only["persona_id"],
            "new_candidate_evidence_ids": sorted(augmented_refs - text_refs),
            "trait_score_delta": {k: round(v["strength_score"] - text_only["derived_traits"][k]["strength_score"], 6) for k, v in selected_media["derived_traits"].items()},
            "measurements": measurement, "human_review": "externally_reported_not_authenticated" if measurement.get("reviewer_ref") else "pending",
            "actual_image_gain_established": False, "behavior_improvement_established": False,
            "limitations": ["metric slots are not measurements", "media availability flag alone is not an image intervention", "validity and behavior effects require paired review"]}


def batch_preflight(authors):
    if len(authors) != len(set(authors)):
        raise ValueError("duplicate_author_group")
    return {"requested_author_groups": len(authors), "recommended_initial_real_sample": "3-5_author_groups",
            "ready_for_100_author_rollout": False, "provider_connected": False, "model_calls": 0,
            "pending": ["authorized full text", "event linkage checks", "human extraction review", "actual processing usage and labor measurements"]}
