"""Source-review sample metrics and rerun consistency, never fabricated labels."""
from __future__ import annotations


def source_sample_check(reference_facts, automatic_facts):
    """Developer source-check coverage, not exhaustive recall or blind accuracy.

    Match same feature, same document, overlapping source span. Windows can still
    have wrong actor/motivation/stage, hence hit coverage is not semantic accuracy.
    """
    rows = []
    for fact in reference_facts:
        matches = []
        for candidate in automatic_facts:
            if fact["post_id"] != candidate["post_id"] or not set(fact["common_dimensions"]) & set(candidate["common_dimensions"]):
                continue
            if any(max(a["span"][0], b["span"][0]) < min(a["span"][1], b["span"][1]) for a in fact["anchors"] for b in candidate["anchors"]):
                matches.append(candidate["fact_id"])
        rows.append({"fact_id":fact["fact_id"],"retrieved_by_same_dimension_window":bool(matches), "candidate_ids":sorted(matches),
                     "semantic_verdict":"needs_source_review_not_implied_by_span_hit"})
    return {"sample_size":len(rows), "window_hits":sum(row["retrieved_by_same_dimension_window"] for row in rows),
            "sample_selection":"developer_selected_source_examples_not_independent_gold",
            "exhaustive_recall":None,"semantic_precision":None,"rows":rows,"human_review":"pending"}


def consistency(first, second):
    def keys(profile):
        return set(profile["patterns"])
    a,b = keys(first),keys(second)
    return {"pattern_key_jaccard":len(a&b)/len(a|b) if a|b else None,
            "same_scores":{key:first["patterns"][key]["strength_index"] == second["patterns"][key]["strength_index"] for key in sorted(a&b)},
            "same_source_ids":{key:{f for c in first["patterns"][key]["contributions"] for f in c["fact_ids"]} == {f for c in second["patterns"][key]["contributions"] for f in c["fact_ids"]} for key in sorted(a&b)},
            "interpretation":"software_rerun_check_not_independent_LLM_semantic_stability"}


def human_review_rows(persona_ids):
    axes = ("major_action_coverage","independence_and_repetition","distinctive_persona_fidelity","rerun_semantic_stability","evidence_inference_traceability","simulation_specificity","review_effort")
    return [{"persona_id":p,"axis":axis,"verdict":None,"reason":None,"reviewer_ref":None} for p in persona_ids for axis in axes]
