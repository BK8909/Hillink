"""Prepare goal/table attribution contrasts. Never invokes or approves a session.

python3 -m operator_choice.causal_p0 --write operator_choice/causal_p0_artifacts
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from persona_sheet import load_cards
from .contracts import validate_case
from .decision_method import decide, VERSION
from .experiment import write_new
from .offline_study import build_case, implementation_sha
from .rules import digest
from .typed_rules import refine

HERE = Path(__file__).resolve().parent
SOURCE_HEAD = "afebc9a7d64b2e8660112eda47b76d8a371970c5"
GOAL_MODES = ("experience_only", "past_purpose_unconfirmed", "assumed_continuity")
SYSTEM = """고정된 가상 호텔 환경에서 이번 15:30~17:00 활동 하나를 선택하세요. 과거 정답이나 저장 답변은 없습니다.
personal_observation은 카드에 관측으로 표시된 과거 행동·평가 요약, personal_inference는 사람 추론 및 개인 경험에서 도출한 새 추론, population_prior는 제공된 검증 통계, situational_judgment는 현재 조건에 대한 판단입니다.
원문 앵커는 재검증되지 않았습니다. 이용 경험, 만족 평가, 과거 방문 목적, 이번 방문 목적은 서로 다릅니다. 과거 이용을 긍정 평가나 재방문 의사로 바꾸지 마세요. 이번 목적이 미상이어도 일반 상황 판단과 제한적 추론으로 선택할 수 있습니다.
사람 추론은 관측 기억이 아닙니다. 새 추론의 전제·한계·반대 근거를 밝히세요. 개인 근거와 가정이 함께 필요하면 personal_inference에서 각각의 ID를 인용하세요. CTX 가정 자체를 개인 관측으로 인용하지 마세요.
통계가 없으면 수치·집단 경향·개인의 연령·주류 취향을 만들지 마세요. 선택하지 않은 활동은 비선호가 아닙니다. 모든 고객이 다른 행동을 할 필요도 없습니다.
선택 코드 하나, 대안 1~3개, 네 층의 이유, 불확실성을 같은 응답에 기록하세요. 원래 후기와 같은 행동을 맞히는 목표는 없습니다. 사용하지 않은 층은 text와 ids를 비우고 not_used로 표시하세요. 기여도는 자기보고이지 인과 효과나 확률이 아닙니다.
예상 지출은 관측 결제액이 아닙니다. 일행 총액 미상은 null로 두세요. 현재 피로·모든 동행의 의사 등 주어지지 않은 사항도 사실로 만들지 마세요.
입력에 사전 비교표가 있으면 이를 제한된 엔진 보조 자료로 취급하세요. 정답이 아니며 따르지 않아도 됩니다. 표가 없으면 개인 근거와 환경만으로 판단하세요. 모든 설명은 한국어로 쓰고 최종 JSON 전체는 가능한 한 6,000자 이내로 작성하세요."""


def make_case(cards, typed, agent, environment, mode, scenario="riverpark"):
    if mode not in GOAL_MODES:
        raise ValueError("unknown_goal_mode")
    case = build_case(cards[agent], typed, scenario, environment)
    case["source_head"] = SOURCE_HEAD
    p = case["payload"]
    # The old packets accidentally retained two evaluator-only constraints as
    # context. Do not carry even non-directional evaluator comments forward.
    p["rules"] = [r for r in p["rules"] if r["verification_status"] != "excluded_evaluator_only"
                  and r["source_verification"]["layer"] not in {"evaluator_comment", "ai_estimate", "unknown"}]
    if mode == "experience_only":
        p["rules"] = [r for r in p["rules"] if r["kind"] != "choice_motivation"]
    c = p["context"]
    continuing = mode == "assumed_continuity"
    c["goal_continuity"] = continuing
    c["goal_continuity_status"] = "explicit_experiment_assumption" if continuing else "not_assumed"
    c["current_visit_purpose"] = {"value": None, "status": "not_observed",
                                  "past_purpose_applied_by_assumption": continuing}
    c["assumptions"]["CTX-GOAL-CONTINUITY"] = (
        "과거 목적 요약을 이번 선택에도 참고한다는 실험 가정. 현재 의사를 관측한 사실은 아니다."
        if continuing else "이번 방문 목적은 미상이며 과거 목적의 지속은 가정하지 않는다. 새 추론을 금지한다는 뜻은 아니다.")
    case["input_sha256"] = digest(p)
    errors = validate_case(case)
    if errors:
        raise ValueError(errors)
    return case


def neutral_evidence(case):
    """No predicates/ranks/expected direction in either table condition's evidence."""
    rules = case["payload"]["rules"]
    return [{"evidence_item": r["rule_id"], "kind": r["kind"], "statement": r["observed_statement"],
             "temporal_scope": "historical_visit_not_current_intent",
             "recorded_aspect": deepcopy(r["evaluated_aspect"]), "evidence_ids": r["evidence_ids"],
             "source_layer": r["source_verification"]["layer"], "source_access": "card_only",
             "original_anchor_verified": False} for r in rules]


def render_packet(case, frozen, table):
    c = case["payload"]["context"]
    # Internal policies and machine option attributes are not personal evidence.
    context = {k: deepcopy(c[k]) for k in ("stage", "effective_party", "current_visit_purpose", "assumptions")}
    evidence = {"personal_evidence": neutral_evidence(case), "population_priors": [], "current_context": context}
    public = {"evidence_and_environment": evidence}
    if table:
        public["prechoice_table"] = [{k: row[k] for k in ("option_code", "feasible", "support", "opposition", "actual_conflicts", "unknowns")}
                                    for row in frozen["options"]]
    prompt = json.dumps(public, ensure_ascii=False, sort_keys=True)
    schema = json.loads((HERE / "decision.schema.json").read_text(encoding="utf-8"))
    request = {"system": SYSTEM, "prompt": prompt, "output_schema": schema}
    return {"packet_version": "goal_table_attribution_v1", **request,
            "expected_input_sha256": digest(request), "evidence_sha256": digest(evidence),
            "launch_requirements": {"approval": "pending_no_execution", "history": "none",
                "tools": "read_only_this_packet_then_no_tools", "isolation": "instructions_not_OS_guarantee",
                "must_not_receive": ["old_answers", "other_customer_answers", "Gold", "review_packet", "engine_selected_code"]}}


def packet_hash(packet):
    return digest({k: packet[k] for k in ("system", "prompt", "output_schema")})


def check_table_pair(a, b):
    errors = []
    if a["system"] != b["system"] or a["output_schema"] != b["output_schema"]:
        errors.append("unmatched_instructions_or_output")
    left, right = json.loads(a["prompt"]), json.loads(b["prompt"])
    if "prechoice_table" in left or "prechoice_table" not in right:
        errors.append("wrong_table_treatment")
    right.pop("prechoice_table", None)
    if left != right or a["evidence_sha256"] != b["evidence_sha256"]:
        errors.append("non_table_covariates_changed")
    if any(p["expected_input_sha256"] != packet_hash(p) for p in (a, b)):
        errors.append("request_hash_mismatch")
    return errors


def check_environment_pair(a, b):
    """Check the no-table riverpark pair: same evidence, only option availability."""
    left, right = json.loads(a["prompt"]), json.loads(b["prompt"])
    if "prechoice_table" in left or "prechoice_table" in right:
        return ["environment_check_requires_no_table_packets"]
    sa = left["evidence_and_environment"]["current_context"]["stage"]
    sb = right["evidence_and_environment"]["current_context"]["stage"]
    oa, ob = ({o["code"]: o for o in s.pop("options")} for s in (sa, sb))
    sa.pop("environment"); sb.pop("environment")
    errors = []
    if left != right:
        errors.append("non_environment_covariates_changed")
    if set(ob) - set(oa) != {"RIVERPARK"} or set(oa) - set(ob):
        errors.append("unexpected_environment_delta")
    if any(oa[code] != ob[code] for code in oa.keys() & ob.keys()):
        errors.append("shared_option_changed")
    return errors


def assess_response(row, frozen_case, packet, response, model):
    """Future import only; does not run a session or replace its original answer."""
    from .offline_study import accept_session
    case, frozen = frozen_case["case"], frozen_case["frozen_prechoice"]
    expected = render_packet(case, frozen, row["table"])
    if packet_hash(packet) != packet["expected_input_sha256"] or packet != expected or row["input_sha256"] != packet_hash(packet):
        raise ValueError("packet_or_treatment_mismatch")
    if response.get("input_sha256") != packet_hash(packet):
        raise ValueError("actual_request_sha_mismatch")
    if model.get("model_id") != "gpt-6.1-sol" or model.get("reasoning_effort") != "high":
        raise ValueError("model_configuration_mismatch")
    if frozen_case["prechoice_sha256"] != digest(frozen):
        raise ValueError("frozen_comparison_changed")
    # Existing structural checker uses the method case hash. Translate only its
    # private validation envelope, not the original answer or stored request ID.
    translated = {"input_sha256": case["input_sha256"], "output": deepcopy(response.get("output", {}))}
    envelope = {k: case[k] for k in ("customer_id", "environment", "scenario", "factors", "input_sha256")}
    envelope.update(prechoice=frozen, prechoice_sha256=frozen_case["prechoice_sha256"], factor_contributions=frozen["factor_contributions"])
    result = accept_session(case, envelope, translated, model)
    result.update(input_sha256=packet_hash(packet), input_version=packet["packet_version"],
                  engine_case_sha256=case["input_sha256"], table_provided=row["table"], goal_mode=row["goal_mode"],
                  evidence_sha256=packet["evidence_sha256"], raw_response_sha256=digest(response))
    return {"raw_response": deepcopy(response), "result": result, "human_review": "pending", "demo_approved": False}


def make_plan(cards=None):
    cards = load_cards() if cards is None else cards
    typed = refine(cards)
    cases, rows, packets, paired = [], [], {}, []
    for agent in ("blog59", "blog25", "blog43"):
        modes = GOAL_MODES if agent == "blog59" else ("past_purpose_unconfirmed",)
        for mode in modes:
            for env in ("off", "on"):
                case = make_case(cards, typed, agent, env, mode)
                p = case["payload"]
                frozen = decide(p["rules"], p["options"], p["context"], p["population_priors"])
                index = len(cases)
                cases.append({"case": case, "frozen_prechoice": frozen, "prechoice_sha256": digest(frozen),
                              "method_version": VERSION, "implementation_sha256": implementation_sha()})
                labels = []
                for table in ((False, True) if agent == "blog59" else (False,)):
                    name = f"{agent}_{mode}_{env}_{'table' if table else 'no_table'}"
                    packet = render_packet(case, frozen, table)
                    packets[name] = packet
                    rows.append({"name": name, "customer_id": agent, "goal_mode": mode, "environment": env,
                                 "table": table, "case_index": index, "input_sha256": packet["expected_input_sha256"],
                                 "evidence_sha256": packet["evidence_sha256"], "instruction_prompt_characters": len(SYSTEM) + len(packet["prompt"]),
                                 "review_status": "not_generated"})
                    labels.append(name)
                if len(labels) == 2:
                    errors = check_table_pair(packets[labels[0]], packets[labels[1]])
                    if errors:
                        raise ValueError(errors)
                    paired.append({"without_table": labels[0], "with_table": labels[1], "only_difference": "prechoice_table"})
    environment_pairs = []
    for row in rows:
        if row["table"] or row["environment"] != "off":
            continue
        other = next(r for r in rows if r["customer_id"] == row["customer_id"] and r["goal_mode"] == row["goal_mode"]
                     and r["environment"] == "on" and not r["table"])
        errors = check_environment_pair(packets[row["name"]], packets[other["name"]])
        if errors:
            raise ValueError(errors)
        environment_pairs.append({"off": row["name"], "on": other["name"], "only_difference": "RIVERPARK_availability_and_environment_label"})
    core = [r["name"] for r in rows if r["goal_mode"] == "past_purpose_unconfirmed" and not r["table"]]
    remainder = [r["name"] for r in rows if r["name"] not in core]
    return {"version": "goal_table_preparation_v1", "source_head": SOURCE_HEAD, "cases": cases, "rows": rows,
            "table_pairs": paired, "packets": packets, "generation_sessions_this_stage": 0,
            "environment_pairs": environment_pairs,
            "method_results_only": True, "goal_modes": list(GOAL_MODES),
            "preparation_implementation_sha256": digest(Path(__file__).read_text(encoding="utf-8")),
            "approval": {"status": "pending", "recommended_max_sessions": 16, "automatic_retries": 0,
                "request_set_sha256": digest([{k: r[k] for k in ("name", "input_sha256")} for r in rows]),
                "phases": [{"phase": 1, "sessions": core, "count": 6},
                           {"phase": 2, "sessions": remainder, "count": 10, "requires": "phase_1_inspected_no_unresolved_structural_failure"}],
                "model_id": "gpt-6.1-sol", "reasoning_effort": "high", "interface": "independent_Codex_session_not_product_API",
                "parameters": {"seed": "not_exposed", "temperature": "not_exposed", "requested_output_characters_max": 6000,
                               "output_limit_enforcement": "instruction_only"},
                "usage": {"input_instruction_prompt_characters": sum(r["instruction_prompt_characters"] for r in rows),
                          "schema_characters_total": sum(len(json.dumps(p["output_schema"], ensure_ascii=False, sort_keys=True)) for p in packets.values()),
                          "output_characters_requested_max_total": 16 * 6000, "exact_tokens": None,
                          "token_note": "모델 tokenizer 및 내부 추론 사용량은 미측정. 문자 수를 토큰이나 과금액으로 환산하지 않음"},
                "product_API_calls": 0, "session_cost_usd": None,
                "stop": ["approval/input/model mismatch", "any extra file/history exposure", "first structural failure: preserve and review, do not retry", "session cap reached"]}}


def method_summary(plan):
    rows = []
    for index, item in enumerate(plan["cases"]):
        treatment = next(r for r in plan["rows"] if r["case_index"] == index)
        frozen = item["frozen_prechoice"]
        rows.append({"customer_id": treatment["customer_id"], "goal_mode": treatment["goal_mode"],
                     "environment": treatment["environment"], "selected": frozen["selected"],
                     "frontier": frozen["frontier"], "selection_basis": frozen["selection_basis"],
                     "interpretation": "method_sensitivity_not_observed_LLM_effect"})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path, required=True)
    args = ap.parse_args()
    plan = make_plan()
    packets = plan.pop("packets")
    write_new(args.write / "preparation_manifest.json", plan)
    write_new(args.write / "method_sensitivity.json", method_summary(plan))
    for name, packet in packets.items():
        write_new(args.write / "packets" / f"{name}.json", packet)
    print(json.dumps({"prepared_sessions_pending_approval": len(packets), "frozen_method_cases": len(plan["cases"]),
                      "new_sessions": 0, "product_API_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
