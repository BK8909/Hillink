"""Import immutable session attempts, including invalid ones, without calling a model."""
from __future__ import annotations

from copy import deepcopy
from .offline_study import accept_session, demo_manifest
from .rules import digest
from .decision_method import audit_choice


def review_attempt(case, frozen, response, model):
    record = {"version": "session_attempt_v1", "customer_id": case["customer_id"],
              "environment": case["environment"], "input_sha256": case["input_sha256"],
              "raw_response": deepcopy(response), "raw_response_sha256": digest(response),
              "model": deepcopy(model), "prechoice_sha256": frozen["prechoice_sha256"],
              "method_audit": audit_choice(response.get("output", {}).get("option_code", ""), frozen["prechoice"]),
              "review": {"status": "research_unreviewed", "human_plausibility": "pending"}}
    try:
        record["validated_result"] = accept_session(case, frozen, response, model)
        record["structural_status"] = "passed_not_semantically_verified"
    except ValueError as error:
        record["structural_status"] = "quarantined"
        record["validation_error"] = str(error)
    # A citation checker cannot establish entailment or absence of invented
    # personal memories. No attempt is implicitly approved for the demo.
    record["demo_eligible"] = False
    return record


def compare_attempts(before, after):
    if before["customer_id"] != after["customer_id"] or (before["environment"], after["environment"]) != ("off", "on"):
        raise ValueError("matching_customer_off_on_required")
    choices = [r["raw_response"]["output"]["option_code"] for r in (before, after)]
    return {"customer_id": before["customer_id"], "before": choices[0], "after": choices[1],
            "changed": choices[0] != choices[1], "structurally_valid_pair": all(
                r["structural_status"] == "passed_not_semantically_verified" for r in (before, after)),
            "interpretation": "single_session_pair_not_probability_or_causal_identification",
            "human_review": "pending", "demo_eligible": False}


def main():
    import argparse
    import json
    from pathlib import Path
    from .experiment import write_new
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--responses", type=Path, required=True)
    ap.add_argument("--write", type=Path, required=True)
    args = ap.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    attempts = []
    model = {"model_id": "gpt-6.1-sol", "reasoning_effort": "high", "interface": "Codex_session",
             "identity_basis": "orchestrator_configuration_not_API_attestation",
             "session_isolation_attestation": "fresh_fork_none_packet_only_read_by_instruction_not_OS_sandbox"}
    for path in sorted(args.responses.glob("*.json")):
        response = json.loads(path.read_text(encoding="utf-8"))
        index = next(i for i, c in enumerate(snapshot["cases"]) if c["input_sha256"] == response["input_sha256"])
        attempts.append(review_attempt(snapshot["cases"][index], snapshot["results"][index], response, model))
    by_key = {(a["customer_id"], a["environment"]): a for a in attempts}
    pairs = [compare_attempts(by_key[(b, "off")], by_key[(b, "on")])
             for b in sorted({a["customer_id"] for a in attempts}) if (b, "off") in by_key and (b, "on") in by_key]
    report = {"version": "independent_session_review_v1", "attempts": attempts, "pairs": pairs,
              "generation_sessions": len(attempts), "product_API_calls": 0, "session_cost_usd": None,
              "human_reviewed": 0, "source_anchors_verified": 0,
              "demo_manifest": demo_manifest([a["validated_result"] for a in attempts if "validated_result" in a], {})}
    write_new(args.write, report)
    print(json.dumps({"sessions": len(attempts), "passed": sum("validated_result" in a for a in attempts),
                      "quarantined": sum(a["structural_status"] == "quarantined" for a in attempts),
                      "demo_approved": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
