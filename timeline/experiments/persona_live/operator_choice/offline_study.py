"""Offline choice generation and session exchange; no API/CLI/model invocation.

python3 -m operator_choice.offline_study --write operator_choice/method_v1_artifacts
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from persona_sheet import load_cards
from .decision_method import VERSION, audit_choice, decide, options_from_stage
from .experiment import SYSTEM, input_cell, write_new
from .rules import catalogue, digest
from .scenarios import SPECS
from .typed_rules import refine, validate_typed

HERE = Path(__file__).resolve().parent
REPRESENTATIVES = ("blog59", "blog25", "blog43")
SOURCE_HEAD = "53ddd4e6cf1762f6d0ff4b1cc19a2a90a6e2e34f"


def implementation_sha() -> str:
    return digest({p: (HERE / p).read_text(encoding="utf-8") for p in (
        "typed_rules.py", "decision_method.py", "offline_study.py", "contracts.py", "offline_input.schema.json")})


def build_case(card: dict, typed: dict, scenario: str, environment: str, personal=True, statistics=False, priors=None) -> dict:
    old = input_cell(card, catalogue()["rules"], scenario, environment, personal, False, {"priors": []})
    # Do not feed reviewer leads, global candidate counts, paths, or removed evidence.
    keep = ("rule_id", "kind", "observed_statement", "evaluated_aspect", "evidence_ids", "verification_status",
            "source_verification", "predicate", "decision_usable", "expected_direction", "transfer_scope", "limitations", "unknowns")
    rs = [{k: deepcopy(r[k]) for k in keep} for r in typed["rules"] if personal and r["agent_id"] == card["blog_id"]]
    for r in rs:
        r["source_verification"] = {"source_access": "card_only", "original_anchor_verified": False,
                                    "layer": r["source_verification"].get("layer", "unknown")}
    stage = old["payload"]["current_context"]["stage"]
    context = {
        "scenario": scenario, "goal_continuity": True, "cost_policy": "opportunity_cost", "weather": "clear",
        "goal_continuity_status": "scenario_assumption_not_a_new_observation",
        "assumptions": {"CTX-GOAL-CONTINUITY": "과거 목적을 이번에도 참고한다는 가정. 이를 끈 민감도 결과와 구별한다.",
                        "CTX-payment": "지출에는 기회비용이 있다는 낮은 우선순위의 일반 판단 정책",
                        "CTX-weather": "두 환경 모두 맑고 쾌적함. 우천 테스트는 별도 민감도 조건",
                        **{a["id"]: a["value"] for a in old["payload"]["current_context"]["assumptions"]}},
        "effective_party": old["payload"]["current_context"]["effective_party"],
        "population_facts": {"party_composition": old["payload"]["current_context"]["effective_party"]["composition"],
                             "party_size": old["payload"]["current_context"]["effective_party"]["size"]},
        "stage": stage,
        "policies": {"common_advantages": "cancel_in_pairwise_comparison", "same_source": "one_root_no_addition",
                     "tie": "stable_code_order_not_customer_preference", "cost": "weak_general_opportunity_cost_not_personal_price_trait"},
    }
    payload = {"rules": rs, "options": options_from_stage(stage), "context": context, "population_priors": priors or [] if statistics else []}
    return {"input_version": "offline_choice_input_v2", "customer_id": card["blog_id"], "scenario": scenario,
            "environment": environment, "factors": {"personal": personal, "statistics": statistics},
            "payload": payload, "input_sha256": digest(payload), "source_head": SOURCE_HEAD}


def compute(case: dict) -> dict:
    from .contracts import validate_case
    errors = validate_case(case)
    if errors:
        raise ValueError("invalid_input:" + ",".join(errors))
    p = case["payload"]
    frozen = decide(p["rules"], p["options"], p["context"], p["population_priors"])
    return {"result_version": "offline_choice_result_v2", "customer_id": case["customer_id"],
            "scenario": case["scenario"], "environment": case["environment"], "factors": case["factors"],
            "input_sha256": case["input_sha256"], "input_version": case["input_version"],
            "selection": frozen["selected"], "alternatives": [
                {"option_code": row["option_code"], "in_frontier": row["option_code"] in frozen["frontier"],
                 "comparison": next(p for p in frozen["pairwise"] if {p["a"], p["b"]} == {row["option_code"], frozen["selected"]})}
                for row in frozen["options"] if row["option_code"] != frozen["selected"] and row["feasible"]],
            "factor_contributions": frozen["factor_contributions"], "uncertainty": frozen["uncertainty"],
            "generator": {"kind": "deterministic_method", "model_id": None, "method_version": VERSION,
                          "implementation_sha256": implementation_sha()},
            "review": {"status": "research_unreviewed", "human_plausibility": "pending", "reviewer": None},
            "prechoice_sha256": digest(frozen), "prechoice": frozen,
            "LLM_calls": 0, "API_cost_usd": 0}


def session_packet(case: dict, frozen_result: dict) -> dict:
    """Only fixed evidence and the BEFORE-choice comparison table reach a fresh session.

    The deterministic selected code and old runs/Gold/reviewer statements are not
    in the packet. Launch a fresh session with access to this packet only.
    """
    if case["input_sha256"] != digest(case["payload"]) or frozen_result["input_sha256"] != case["input_sha256"]:
        raise ValueError("input_mismatch")
    table = [{k: row[k] for k in ("option_code", "feasible", "support", "opposition", "actual_conflicts", "unknowns")}
             for row in frozen_result["prechoice"]["options"]]
    public = {"case_id": case["input_sha256"][:16], "input_sha256": case["input_sha256"],
              "evidence_and_environment": case["payload"], "prechoice_table": table}
    return {
        "packet_version": "fresh_session_packet_v1", "case_id": public["case_id"],
        "system": SYSTEM + "\n이 표는 선택 전 계산된 제한적 휴리스틱이다. 선택 결과·정답·기존 답변은 없다. "
                  "원문 관측이 아닌 새 추론은 personal_inference로 적고, 표와 다른 판단이면 현재 조건과 반대 근거를 밝히세요. "
                  "표의 unknown·모순·적용 범위도 검토하세요. 일반 경고를 실제 부정 경험으로 만들지 마세요. "
                  "current_context의 CTX-payment/CTX-weather 및 기존 가정 ID를 상황 이유로 인용할 수 있습니다.",
        "prompt": json.dumps(public, ensure_ascii=False, sort_keys=True),
        "output_schema": json.loads((HERE / "decision.schema.json").read_text(encoding="utf-8")),
        "expected_input_sha256": case["input_sha256"],
        "launch_requirements": {"history": "none", "tools": "only_this_packet_read_allowed_no_other_files_or_network", "workspace": "packet_only_by_instruction_not_OS_attestation",
                                "must_not_receive": ["old_answers", "Gold", "reviewer_comments", "engine_selected_code"]},
    }


def accept_session(case: dict, frozen_result: dict, response: dict, model: dict) -> dict:
    """Validate an externally generated fresh-session answer; no invocation here."""
    from .evaluate import evaluate
    if response.get("input_sha256") != case["input_sha256"] or case["input_sha256"] != digest(case["payload"]):
        raise ValueError("session_input_sha_mismatch")
    if not model.get("model_id") or not model.get("session_isolation_attestation"):
        raise ValueError("model_identity_and_isolation_record_required")
    if frozen_result["input_sha256"] != case["input_sha256"] or frozen_result["prechoice_sha256"] != digest(frozen_result["prechoice"]):
        raise ValueError("frozen_prechoice_modified")
    for key in ("customer_id", "scenario", "environment", "factors"):
        if case.get(key) != frozen_result.get(key):
            raise ValueError("frozen_result_identity_mismatch:" + key)
    p = case["payload"]
    compatibility = {"payload": {"personal_evidence": [
        {"evidence_ids": r["evidence_ids"], "provenance": {"layer": r["source_verification"].get("layer",
            "observed" if r["kind"] in {"explicit_preference", "explicit_evaluation", "behavior_observation"} else "human_inference")}}
        for r in p["rules"]], "population_prior": p["population_priors"],
        "current_context": {"stage": p["context"]["stage"], "assumption_ids": list(p["context"]["assumptions"])}}}
    # An inference can explicitly cite BOTH a personal premise and an experiment
    # premise. Keep the original answer unchanged, and audit those premises in
    # their own layer rather than treating CTX-* as a past personal memory.
    normalized = deepcopy(response.get("output", {}))
    context_ids = set(p["context"]["assumptions"])
    inference = normalized.get("basis", {}).get("personal_inference", {})
    premises = [i for i in inference.get("ids", []) if i in context_ids]
    if premises:
        inference["ids"] = [i for i in inference["ids"] if i not in context_ids]
    check = evaluate(normalized, compatibility)
    check["cross_layer_premises"] = [{"id": i, "source_layer": "current_context", "used_by": "personal_inference",
                                       "personal_memory": False} for i in premises]
    if check["errors"]:
        raise ValueError("invalid_session_result:" + ",".join(check["errors"]))
    return {"result_version": "offline_choice_result_v2", "customer_id": case["customer_id"],
            "scenario": case["scenario"], "environment": case["environment"], "factors": case["factors"],
            "input_sha256": case["input_sha256"], "input_version": case["input_version"],
            "selection": response["output"]["option_code"], "alternatives": response["output"]["alternatives"],
            "output": deepcopy(response["output"]), "generator": {"kind": "independent_session", **model},
            "method_audit": audit_choice(response["output"]["option_code"], frozen_result["prechoice"]),
            "review": {"status": "research_unreviewed", "human_plausibility": "pending", "reviewer": None},
            "reference_method_contributions": frozen_result["factor_contributions"],
            "model_self_report": response["output"]["basis"], "validation": check,
            "billing": {"product_API_calls": 0, "session_cost_usd": None}}


def demo_manifest(results: list[dict], reviews: dict) -> dict:
    """Only actual, explicit human signoff unlocks saved replay; never auto-review."""
    accepted, excluded = [], []
    for result in results:
        key = digest(result)
        review = reviews.get(key, {})
        if (review.get("reviewer_kind") == "human" and review.get("reviewer") and review.get("decision") == "accept"
                and review.get("input_sha256") == result["input_sha256"] and review.get("result_sha256") == key
                and all(review.get(k) is True for k in ("evidence_layers_checked", "uncertainties_checked", "choice_plausibility_checked"))):
            accepted.append({"result_sha256": key, "customer_id": result["customer_id"], "environment": result["environment"], "review": review})
        else:
            excluded.append({"result_sha256": key, "reason": "explicit_human_review_pending"})
    return {"version": "saved_replay_manifest_v1", "capabilities": {"saved_replay_only": True, "arbitrary_condition_generation": False},
            "accepted": accepted, "excluded": excluded}


def study(agents=None, scenario="riverpark") -> dict:
    cards = load_cards()
    typed = refine(cards)
    if validate_typed(typed):
        raise ValueError(validate_typed(typed))
    agents = agents or [b for b, c in cards.items() if c.get("selection_status") == "selected"]
    cases, results, aliases, unique = [], [], [], {}
    for b in agents:
        for environment in ("off", "on"):
            for personal, statistics, label in ((True, True, "A"), (True, False, "B"), (False, True, "C"), (False, False, "D")):
                case = build_case(cards[b], typed, scenario, environment, personal, statistics)
                # Sharing identical deterministic input is not an independent replicate.
                key = (b, case["input_sha256"])
                if key not in unique:
                    unique[key] = len(cases)
                    cases.append(case)
                    results.append(compute(case))
                aliases.append({"customer_id": b, "environment": environment, "condition": label, "case_index": unique[key]})
    return {"version": "offline_method_study_v1", "scenario": scenario, "agents": list(agents), "cases": cases,
            "results": results, "aliases": aliases, "model_calls": 0, "API_cost_usd": 0,
            "statistics_effect_identifiable": False, "independent_LLM_results": 0}


def ablation_summary(data: dict) -> list[dict]:
    lookup = {(c["customer_id"], c["environment"], c["factors"]["personal"]): r for c, r in zip(data["cases"], data["results"])}
    rows = []
    for agent in data["agents"]:
        combos = {f"{env}_{'personal' if personal else 'context'}": lookup[(agent, env, personal)] for env in ("off", "on") for personal in (True, False)}
        rows.append({"customer_id": agent, "selections": {k: v["selection"] for k, v in combos.items()},
                     "frontiers": {k: v["prechoice"]["frontier"] for k, v in combos.items()},
                     "personal_choice_changes": {env: combos[env + "_personal"]["selection"] != combos[env + "_context"]["selection"] for env in ("off", "on")},
                     "environment_choice_changes": combos["off_personal"]["selection"] != combos["on_personal"]["selection"],
                     "interpretation": "deterministic_method_sensitivity_not_empirical_individual_causality"})
    return rows


def policy_sensitivity(data: dict) -> list[dict]:
    rows = []
    for case, result in zip(data["cases"], data["results"]):
        if case["customer_id"] not in REPRESENTATIVES or not case["factors"]["personal"]:
            continue
        p = case["payload"]
        variants = {}
        for label, change in (("goal_continuity_off", {"goal_continuity": False}), ("cost_policy_off", {"cost_policy": "none"})):
            context = {**p["context"], **change}
            d = decide(p["rules"], p["options"], context, p["population_priors"])
            variants[label] = {"selected": d["selected"], "frontier": d["frontier"], "changed": d["selected"] != result["selection"]}
        rows.append({"customer_id": case["customer_id"], "environment": case["environment"],
                     "baseline": result["selection"], "variants": variants})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path)
    args = ap.parse_args()
    data = study()
    summary = ablation_summary(data)
    if args.write:
        write_new(args.write / "typed_rules_v2.json", refine())
        write_new(args.write / "research" / "engine_study_v1.json", data)
        write_new(args.write / "research" / "ablation_summary_v1.json", summary)
        write_new(args.write / "research" / "policy_sensitivity_v1.json", policy_sensitivity(data))
        for i, (case, result) in enumerate(zip(data["cases"], data["results"])):
            if case["factors"]["personal"]:
                write_new(args.write / "fresh_session_packets" / f"{case['customer_id']}_{case['environment']}.json", session_packet(case, result))
        write_new(args.write / "demo" / "reviewed_manifest_v1.json", demo_manifest(data["results"], {}))
    print(json.dumps({"cases": len(data["cases"]), "logical_conditions": len(data["aliases"]), "LLM_calls": 0,
                      "API_cost_usd": 0, "representatives": [r for r in summary if r["customer_id"] in REPRESENTATIVES]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
