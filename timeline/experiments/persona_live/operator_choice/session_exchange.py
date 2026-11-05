"""Offline response import, human worksheet and saved-replay gate. NO generation.

Raw attempts are immutable. Invalid attempts stop a batch; no repair/retry path.
Human signatures are recorded attestations, not authenticated digital signatures.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .causal_p0 import assess_response, packet_hash
from .rules import digest
from .session_phase_gate import check_authority, phase_request

AXES = ("structure_and_ids", "personal_facts", "behavior_plausibility", "current_goal_application",
        "new_inference_scope", "alternative_comparison")


def load_frozen(root=None):
    root = root or Path(__file__).parent / "causal_p0_artifacts"
    plan = json.loads((root / "preparation_manifest.json").read_text())
    plan["packets"] = {r["name"]: json.loads((root / "packets" / (r["name"] + ".json")).read_text())
                       for r in plan["rows"]}
    return plan


def _launch_errors(plan, phase, approval, name, model, phase1_results=()):
    errors = check_authority(plan, phase, approval, phase1_results)
    if name not in {r["name"] for r in phase_request(plan, phase)["requests"]}:
        errors.append("request_not_in_approved_phase")
    required = {"model_id": "gpt-6.1-sol", "reasoning_effort": "high", "history": "none",
                "provided_inputs": "single_frozen_packet", "automatic_retries": 0, "product_API_calls": 0}
    for field, expected in required.items():
        if model.get(field) != expected:
            errors.append("launch_record_mismatch:" + field)
    for field in ("session_id", "session_isolation_attestation", "actual_isolation_level"):
        if not model.get(field):
            errors.append("launch_record_missing:" + field)
    if model.get("test_fixture") or model.get("provider") == "fake":
        errors.append("test_fixture_not_real_session")
    return errors


def import_attempt(plan, name, raw_bytes, model, approval, directory, *, phase=1, phase1_results=()):
    """Preserve exact bytes FIRST, then validate. Never invokes a model/provider.

    Directory is a new research batch. Every request can be imported only once.
    A failed attempt halts further imports in that batch pending user direction.
    """
    directory = Path(directory)
    row = next((r for r in plan["rows"] if r["name"] == name), None)
    if row is None:
        raise ValueError("unknown_request_name")
    if directory.exists():
        for path in directory.glob("*/assessment.json"):
            if json.loads(path.read_text())["status"] == "quarantined_stop":
                raise ValueError("batch_stopped_preserve_failure_no_retry")
    attempt = directory / name
    attempt.mkdir(parents=True, exist_ok=False)
    (attempt / "raw_response.bin").write_bytes(raw_bytes)
    record = {"version": "session_import_v1", "request_name": name, "input_sha256": row["input_sha256"],
              "raw_bytes_sha256": hashlib.sha256(raw_bytes).hexdigest(), "model": deepcopy(model),
              "approval_sha256": digest(approval), "approval": deepcopy(approval), "phase": phase,
              "status": "quarantined_stop", "structural_errors": [],
              "evidence_check": "pending", "behavior_plausibility": "pending_human",
              "human_review": "pending", "demo_approved": False, "product_API_calls": 0,
              "unresolved_semantic_flags": ["new_inference_and_memory_require_human_review"]}
    errors = _launch_errors(plan, phase, approval, name, model, phase1_results)
    try:
        response = json.loads(raw_bytes)
        if not isinstance(response, dict):
            raise ValueError("response_must_be_object")
        record["parsed_response_sha256"] = digest(response)
        if errors:
            raise ValueError(";".join(errors))
        imported = assess_response(row, plan["cases"][row["case_index"]], plan["packets"][name], response, model)
        record.update(status="structural_pass_research_unreviewed", imported=imported,
                      result_sha256=digest(imported["result"]), evidence_check="ids_and_layers_pass_semantics_pending")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        record["structural_errors"] = [str(exc)]
    # Exclusive files, no automatic correction of source-layer or memory mistakes.
    with (attempt / "assessment.json").open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return record


def revalidate(plan, record, raw_bytes):
    errors = []
    if record.get("status") != "structural_pass_research_unreviewed" or record.get("structural_errors") != []:
        return ["not_structurally_accepted"]
    if hashlib.sha256(raw_bytes).hexdigest() != record.get("raw_bytes_sha256"):
        return ["raw_response_bytes_changed"]
    try:
        response = json.loads(raw_bytes)
        if record.get("approval_sha256") != digest(record.get("approval")):
            errors.append("approval_record_changed")
        if record.get("phase") != 1:
            errors.append("replay_only_phase1_supported")
        errors.extend(_launch_errors(plan, 1, record.get("approval", {}), record["request_name"], record["model"]))
        row = next(r for r in plan["rows"] if r["name"] == record["request_name"])
        actual = assess_response(row, plan["cases"][row["case_index"]], plan["packets"][row["name"]], response, record["model"])
        if (actual != record.get("imported") or digest(response) != record.get("parsed_response_sha256")
                or digest(actual["result"]) != record.get("result_sha256")
                or actual["result"]["input_sha256"] != record.get("input_sha256")):
            errors.append("assessment_or_input_changed")
    except (ValueError, TypeError, KeyError, StopIteration) as exc:
        errors.append("revalidation_failed:" + str(exc))
    return errors


def replay_manifest(plan, attempts=(), reviews=None, approvals=None):
    """Export ONLY complete off/on pairs with six-axis human and demo signoff.

    attempts: [(record, exact_raw_bytes)]. Reviews/approvals keyed by result SHA.
    No manifest flag can turn method-only or fake-provider output into a real run.
    Human review is trusted external input, never computed here.
    """
    reviews, approvals = reviews or {}, approvals or {}
    accepted, rejected = [], []
    seen = set()
    allowed = {r["name"] for r in phase_request(plan, 1)["requests"]}
    for record, raw in attempts:
        errors = revalidate(plan, record, raw)
        if record.get("request_name") not in allowed:
            errors.append("not_phase1_request")
        if record.get("request_name") in seen:
            errors.append("duplicate_request")
        seen.add(record.get("request_name"))
        result = record.get("imported", {}).get("result", {})
        key = record.get("result_sha256")
        review, signoff = reviews.get(key, {}), approvals.get(key, {})
        for label, obj in (("human_review", review), ("demo_approval", signoff)):
            if (obj.get("input_sha256") != record.get("input_sha256") or obj.get("result_sha256") != key
                    or obj.get("raw_bytes_sha256") != record.get("raw_bytes_sha256")):
                errors.append(label + "_hash_binding_missing")
        if (review.get("reviewer_kind") != "human" or not review.get("reviewer")
                or review.get("decision") != "accept" or review.get("unresolved_semantic_flags") != []
                or not all(review.get("axes", {}).get(axis, {}).get("decision") == "accept"
                           and review["axes"][axis].get("rationale") for axis in AXES)):
            errors.append("six_axis_human_review_required")
        if signoff.get("approved") is not True or not signoff.get("approved_by"):
            errors.append("explicit_demo_approval_required")
        if result.get("generator", {}).get("kind") != "independent_session":
            errors.append("independent_session_required")
        if errors:
            rejected.append({"request_name": record.get("request_name"), "reasons": sorted(set(errors))})
            continue
        accepted.append({"customer_id": result["customer_id"], "environment": result["environment"],
                         "scenario": result["scenario"], "input_sha256": result["input_sha256"],
                         "result_sha256": key, "raw_bytes_sha256": record["raw_bytes_sha256"],
                         "model": result["generator"], "input_version": result["input_version"],
                         "engine_case_sha256": result["engine_case_sha256"],
                         "choice": result["output"], "prechoice_method_audit": result["method_audit"],
                         "method_contributions_not_causal": result["reference_method_contributions"],
                         "model_self_report_not_causal": result["model_self_report"],
                         "human_review": review, "demo_approval": signoff})
    complete = []
    for row in accepted:
        pair = [r for r in accepted if r["customer_id"] == row["customer_id"]]
        if len(pair) != 2 or {r["environment"] for r in pair} != {"off", "on"}:
            rejected.append({"customer_id": row["customer_id"], "reasons": ["approved_off_on_pair_incomplete"]})
        else:
            complete.append(row)
    return {"version": "reviewed_saved_comparison_v1", "saved_replay_only": True,
            "arbitrary_condition_generation": False, "product_API_calls": 0,
            "accepted": complete, "excluded": rejected, "approval_authenticated_by_software": False}


def comparison_worksheet(plan, records=()):
    """No generated responses by default; never fills blank choices from the method."""
    by_name = {r["request_name"]: r for r in records}
    rows = []
    for request in phase_request(plan, 1)["requests"]:
        name = request["name"]
        row = next(r for r in plan["rows"] if r["name"] == name)
        packet = plan["packets"][name]
        data = json.loads(packet["prompt"])["evidence_and_environment"]
        evidence = data["personal_evidence"]
        record = by_name.get(name)
        output = (record or {}).get("imported", {}).get("result", {}).get("output")
        rows.append({"customer_id": row["customer_id"], "environment": row["environment"],
            "request_name": name, "input_sha256": packet_hash(packet),
            "source_access": "card_only_original_anchor_not_verified",
            "historical_experience": [e for e in evidence if e["kind"] != "choice_motivation"],
            "past_purpose_not_current_intent": [e for e in evidence if e["kind"] == "choice_motivation"],
            "situation_constraints_and_assumptions": data["current_context"],
            "output": deepcopy(output), "new_inference": output["basis"]["personal_inference"] if output else None,
            "choice": output["option_code"] if output else None,
            "alternatives": output["alternatives"] if output else None,
            "unknowns": ["이번 목적 미상", "원문 앵커 미확인", "실제 입장 자격·일행 총비용 미확정"],
            "generation_status": record["status"] if record else "not_generated",
            "human_review": {"reviewer": None, "decision": None,
                             "axes": {a: {"decision": None, "rationale": None} for a in AXES}},
            "demo_approved": False})
    return {"version": "phase1_off_on_human_worksheet_v1", "rows": rows,
            "original_text_direct_verifications_this_stage": 0, "automatic_notes_are_human_review": False}
