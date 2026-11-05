"""Offline input and stored-result integrity checks, without model invocation."""
from __future__ import annotations

import json
from pathlib import Path
import jsonschema
from .rules import digest


def validate_case(case):
    schema = json.loads(Path(__file__).with_name("offline_input.schema.json").read_text(encoding="utf-8"))
    issues = ["schema:" + e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(case)]
    if issues:
        return issues
    p = case["payload"]
    if case["input_sha256"] != digest(p):
        issues.append("input_sha_mismatch")
    codes = [o["option_code"] for o in p["options"]]
    if len(codes) != len(set(codes)):
        issues.append("duplicate_option")
    if set(codes) != {o["code"] for o in p["context"]["stage"]["options"]}:
        issues.append("stage_option_mismatch")
    if p["context"]["scenario"] != case["scenario"]:
        issues.append("scenario_mismatch")
    if p["context"]["goal_continuity"] and "CTX-GOAL-CONTINUITY" not in p["context"]["assumptions"]:
        issues.append("unregistered_goal_transfer_assumption")
    if not case["factors"]["personal"] and p["rules"]:
        issues.append("personal_ablation_leak")
    if not case["factors"]["statistics"] and p["population_priors"]:
        issues.append("statistics_ablation_leak")
    for r in p["rules"]:
        if r["decision_usable"] and (r["kind"] == "behavior_observation" or not r["predicate"] or not r["evidence_ids"]
                                      or r["source_verification"]["layer"] in {"ai_estimate", "evaluator_comment", "unknown"}):
            issues.append("unusable_evidence_promoted")
        if r["verification_status"] == "source_verified" and not r["source_verification"]["original_anchor_verified"]:
            issues.append("unverified_anchor_promoted")
    return issues


def validate_stored_result(case, result):
    issues = []
    for key in ("customer_id", "environment", "scenario", "input_sha256", "input_version", "factors"):
        if result.get(key) != case.get(key):
            issues.append("result_identity_mismatch:" + key)
    options = {o["option_code"] for o in case["payload"]["options"] if o["available"]}
    if result.get("selection") not in options:
        issues.append("unavailable_selection")
    if result.get("generator", {}).get("kind") == "deterministic_method":
        if result.get("prechoice_sha256") != digest(result.get("prechoice")):
            issues.append("prechoice_sha_mismatch")
        if result.get("selection") != result.get("prechoice", {}).get("selected"):
            issues.append("selection_does_not_match_frozen_method")
    elif result.get("generator", {}).get("kind") == "independent_session":
        if result.get("validation", {}).get("errors"):
            issues.append("invalid_session_result")
    else:
        issues.append("unknown_generator_kind")
    if result.get("review", {}).get("status") not in {"research_unreviewed", "human_reviewed"}:
        issues.append("unknown_review_status")
    return issues
