"""Manual session authorization check; contains no model/provider invocation."""
from .rules import digest


def phase_request(plan, phase):
    if phase not in (1, 2):
        raise ValueError("phase_must_be_1_or_2")
    block = next(p for p in plan["approval"]["phases"] if p["phase"] == phase)
    lookup = {r["name"]: r for r in plan["rows"]}
    rows = [lookup[n] for n in block["sessions"]]
    requests = [{"name": r["name"], "input_sha256": r["input_sha256"]} for r in rows]
    return {"phase": phase, "count": len(rows), "requests": requests, "phase_sha256": digest(requests),
            "model_id": "gpt-6.1-sol", "reasoning_effort": "high", "automatic_retries": 0,
            "instruction_prompt_characters": sum(r["instruction_prompt_characters"] for r in rows),
            "product_API_calls": 0, "approval_status": "pending"}


def check_authority(plan, phase, approval, phase1_results=()):
    required = phase_request(plan, phase)
    errors = []
    if not approval.get("approved") or not approval.get("approved_by"):
        errors.append("explicit_user_approval_missing")
    for field in ("phase", "phase_sha256", "model_id", "reasoning_effort"):
        if approval.get(field) != required[field]:
            errors.append("approval_mismatch:" + field)
    if approval.get("max_sessions") != required["count"]:
        errors.append("phase_session_cap_mismatch")
    if phase == 2:
        first = phase_request(plan, 1)
        expected = {r["input_sha256"] for r in first["requests"]}
        supplied = [r.get("input_sha256") for r in phase1_results]
        if len(supplied) != 6 or set(supplied) != expected:
            errors.append("phase1_six_distinct_results_required")
        for r in phase1_results:
            review = r.get("human_review", {})
            result = r.get("result", {})
            if (r.get("structural_errors") != [] or r.get("unresolved_semantic_flags") != []
                    or result.get("input_sha256") != r.get("input_sha256")
                    or result.get("generator", {}).get("model_id") != first["model_id"]
                    or result.get("generator", {}).get("reasoning_effort") != first["reasoning_effort"]
                    or review.get("reviewer_kind") != "human" or not review.get("reviewer")
                    or review.get("decision") != "accept"
                    or review.get("result_sha256") != digest(r.get("result"))
                    or review.get("input_sha256") != r.get("input_sha256")):
                errors.append("phase1_structural_and_human_review_required")
    return sorted(set(errors))
