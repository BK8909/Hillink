"""Build real choice prompts and a deduplicated 2 x 2 x 2 design without LLM calls.

python3 -m operator_choice.experiment --write operator_choice/artifacts
No run flag: model execution is a separately approved provider operation.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from persona_sheet import load_cards
from .priors import load_registry, select_priors
from .rules import catalogue, digest, validate_rules
from .scenarios import SPECS, build_pair, validate_pair

PILOT_AGENTS = ("blog36", "blog43", "blog25")
SYSTEM = """새로운 가상 호텔 방문에서 한 시간 블록의 활동 하나를 지금 선택하세요. 과거 정답이나 저장 계획은 주어지지 않습니다.
네 근거 층을 구분하세요: personal_observation(카드의 직접 행동·평가 요약), personal_inference(개인 경험에서의 추론), population_prior(확인된 집단 통계), situational_judgment(현재 조건에 대한 일반 판단).
카드 기반 후보는 원문 재검증 완료가 아닙니다. observed_behavior 중 관측 층의 요약만 개인 관측으로, rule_hypothesis와 사람 추론은 개인 추론으로 구분하세요. 이용은 만족이나 재방문 선호와 같지 않습니다. 적용 범위 밖의 취향·연령·주류 선호·개인 기억을 만들지 마세요.
개인 근거가 있으면 우선 검토하고, 통계는 보조 근거로 사용할 수 있습니다. 충돌하면 개인 근거를 우선하며 충돌을 밝히세요. 집단 경향을 개인의 확정 취향으로 바꾸지 마세요. 통계가 주어지지 않으면 통계 수치나 유행을 생성하지 마세요.
일반적인 상황 추론도 충분한 선택 이유입니다. 정보 공백 때문에 모든 판단을 보류할 필요는 없습니다. 불확실성이 중요하면 confidence=낮음과 대안을 표시하세요.
활동을 유지하거나 객실에서 쉬는 선택도 유효합니다. 서로 다른 고객의 선택을 다양하게 만들 목표는 없습니다.
아래 선택지 코드 하나를 고르고 같은 블록의 대안 1~3개와 비교하세요. 선택과 이유를 함께 생성하며 나중에 이유를 재작성하지 않습니다.
근거 ID는 제공된 목록만, 가정 ID는 현재 조건 블록에 있는 것만 인용하세요. 사용하지 않은 층은 text를 비우고 ID도 비우세요. 기여도는 정성 자기보고이며 인과 효과나 행동 확률이 아닙니다.
모든 설명은 한국어로 쓰세요. 지출은 추정이며 실제 결제액이 아닙니다. 총액 미상이면 null입니다."""


def input_cell(card: dict, rules: list[dict], scenario: str, environment: str,
               personal: bool, statistics: bool, registry: dict) -> dict:
    pair = build_pair(scenario, card["a_card"]["observed_visit"]["property"])
    if validate_pair(pair):
        raise ValueError(validate_pair(pair))
    usable = [r for r in rules if r["agent_id"] == card["blog_id"] and r["verification_status"] != "insufficient"]
    if not personal:
        usable = []
    priors, excluded = select_priors(registry, card, scenario)
    if not statistics:
        priors = []
    # Identifiers, reviewers, removed rules, and historical outputs are audit-only.
    p_rules = [{k: r[k] for k in ("rule_id", "observed_behavior", "evaluated_aspect", "evidence_ids", "provenance",
                                  "rule_hypothesis", "applicable_context", "counter_evidence", "confidence_basis")}
               for r in usable]
    for r in p_rules:
        r["provenance"] = {k: v for k, v in r["provenance"].items() if k not in {"card_path", "card_review_status"}}
    context = {
        "effective_party": deepcopy(card["a_card"]["party"]),
        "party_policy": "이번 동행은 카드의 구성·인원 후보를 그대로 둔다. 사람 추론·미상은 확정 사실이 아니며 두 환경에 동일하게 적용한다.",
        "building_policy": "카드의 건물을 가상 숙박의 고정 조건으로 사용한다. 과거 건물의 추론을 새로 관측 확인한 것은 아니다.",
        "assumption_ids": ["CTX-VIRTUAL-STAY", "CTX-SAME-PARTY", "CTX-WEATHER", "CTX-ADMISSION", "CTX-PRICE"],
        "assumptions": [
            {"id": "CTX-VIRTUAL-STAY", "provenance": "scenario_assumption", "value": "가상 1박·15:00 도착·11:00 퇴실, 과거 예약·패키지 이전 없음"},
            {"id": "CTX-SAME-PARTY", "provenance": "scenario_assumption", "value": "동행 구성 후보를 이번에도 동일하게 적용, 추론·미상 보존"},
            {"id": "CTX-WEATHER", "provenance": "scenario_assumption", "value": "두 조건 모두 맑고 쾌적한 날"},
            {"id": "CTX-ADMISSION", "provenance": "scenario_assumption", "value": "이번 블록에서 일행의 시설 입장 가능을 가정, 실제 자격·보호자 비율 확인 아님"},
            {"id": "CTX-PRICE", "provenance": "scenario_assumption", "value": "시설은 고정 로컬 표 참고값, 행사는 가상 일행 요금. 실제 결제·정확한 일행 총액은 생성하지 않음"},
        ],
        "stage": pair[environment],
    }
    # Party remains a fixed situational covariate, never a hidden source of preference.
    for value in context["effective_party"].values():
        value.pop("evidence_ids", None)
        value.pop("review_status", None)
    comp = context["effective_party"]["composition"]
    if comp.get("value") == "anniversary couple and children":
        comp["value"] = "couple and children"  # remove purpose from the retained demographic covariate
    payload = {"personal_evidence": p_rules, "population_prior": priors, "current_context": context}
    prompt = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return {
        "agent_id": card["blog_id"], "scenario": scenario, "environment": environment,
        "factors": {"personal": personal, "statistics": statistics}, "payload": payload,
        "system": SYSTEM, "prompt": prompt, "prompt_sha256": digest({"system": SYSTEM, "prompt": prompt}),
        "audit_only": {"removed_rule_ids": [r["rule_id"] for r in rules if r["agent_id"] == card["blog_id"] and r not in usable],
                       "excluded_priors": excluded, "historical_results_used": False},
    }


def prepare(agents=PILOT_AGENTS, scenario="beer_festival", cards=None, registry=None) -> dict:
    cards = load_cards() if cards is None else cards
    registry = load_registry() if registry is None else registry
    cat = catalogue(cards)
    if validate_rules(cat):
        raise ValueError(validate_rules(cat))
    cells, unique = [], {}
    for b in agents:
        for environment in ("off", "on"):
            for personal, statistics, name in ((True, True, "P+S+E"), (True, False, "P+E"),
                                               (False, True, "S+E"), (False, False, "E")):
                cell = input_cell(cards[b], cat["rules"], scenario, environment, personal, statistics, registry)
                cell["condition"] = name
                # No duplicate paid calls masquerading as a statistics ablation.
                key = cell["prompt_sha256"]
                cell["execution_id"] = unique.setdefault(key, f"X{len(unique) + 1:03d}")
                cells.append(cell)
    return {
        "version": "operator_choice_plan_v1", "scenario": scenario, "agents": list(agents),
        "source_commit": cat["source_commit"], "card_sha256": cat["input_sha256"], "registry_sha256": digest(registry),
        "logical_conditions": len(cells), "unique_calls": len(unique), "model_calls_this_stage": 0,
        "statistics_effect_identifiable": any(c["payload"]["population_prior"] for c in cells),
        "model_spec": {"provider": "claude_cli", "historical_alias": "sonnet", "pinned_model": None,
                       "temperature": "provider_default_unexposed", "seed": "unsupported", "max_retries": 0},
        "approval": {"status": "pending", "proposed_max_calls": len(unique), "budget_usd": 1.5,
                     "cost_estimate_usd": [round(len(unique) * 0.05, 2), round(len(unique) * 0.10, 2)],
                     "cost_basis": "저장된 계획 1회 평균 약 $0.063을 참고한 범위. 새 입력의 토큰별 가격 견적은 아니며 실행 전 재산정 필요.",
                     "stop": ["누적 비용에 다음 호출 예약액을 더하면 예산 초과", "3회 연속 실패", "모델 식별 불일치", "입력 해시 불일치"]},
        "cells": cells,
    }


def write_new(path: Path, data):
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"immutable artifact differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(content)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path)
    args = ap.parse_args()
    cat, plan = catalogue(), prepare()
    if args.write:
        write_new(args.write / "behavior_rules_v1.json", cat)
        write_new(args.write / "beer_pilot_inputs_v1.json", plan)
        cards = load_cards()
        write_new(args.write / "scenario_pairs_v1.json", {s: build_pair(s, "GRAND") for s in SPECS})
        write_new(args.write / "all10_condition_manifest_v1.json", {
            s: [{"agent_id": b, "off_sha256": digest(build_pair(s, c["a_card"]["observed_visit"]["property"])["off"]),
                 "on_sha256": digest(build_pair(s, c["a_card"]["observed_visit"]["property"])["on"])}
                for b, c in cards.items() if c.get("selection_status") == "selected"] for s in SPECS})
    print(json.dumps({"rules": len(cat["rules"]), "agents": len(cat["agents"]),
                      "logical_conditions": plan["logical_conditions"], "unique_calls_pending": plan["unique_calls"],
                      "statistics_effect_identifiable": plan["statistics_effect_identifiable"], "model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
