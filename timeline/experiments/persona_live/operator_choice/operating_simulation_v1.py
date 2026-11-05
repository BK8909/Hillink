"""Render fixed, human-reviewable operating hypotheses from V3 profile + scenario data.

This is an offline synthesis/report adapter, not an LLM run or probability model.
The action hypotheses are authored scenario content and remain unreviewed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "profile_v3_artifacts"
PROFILE_PATH = ARTIFACTS / "blog41_author_profile_v3.json"
SCENARIO_PATH = HERE / "seasonal_operator_scenarios_v1.json"
OUTPUT_DIR = ARTIFACTS / "seasonal_operator_v1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assemble(profile: dict[str, Any], scenarios: dict[str, Any]) -> dict[str, Any]:
    if profile.get("persona_id") != scenarios.get("persona_id"):
        raise ValueError("persona_profile_mismatch")
    claims = {claim["claim_id"]: claim for claim in profile.get("claims", [])}
    results = []
    for scenario in scenarios.get("scenarios", []):
        missing = sorted(set(scenario["profile_aspects"]) - claims.keys())
        if missing:
            raise ValueError(f"unknown_profile_claims:{scenario['scenario_id']}:{','.join(missing)}")
        results.append({
            "scenario_id": scenario["scenario_id"],
            "season": scenario["season"],
            "operator_question": scenario["operator_question"],
            "virtual_conditions": scenario["virtual_conditions"],
            "options": scenario["options"],
            "profile_context": scenarios["shared_persona_context"],
            "profile_evidence": [
                {
                    "claim_id": claim_id,
                    "aspect": claims[claim_id]["aspect"],
                    "value": claims[claim_id]["value"],
                    "claim_layer": claims[claim_id]["claim_layer"],
                    "scope": claims[claim_id]["scope"],
                    "review_status": claims[claim_id].get("review", "unspecified"),
                }
                for claim_id in scenario["profile_aspects"]
            ],
            "action_hypothesis": scenario["action_hypothesis"],
            "unknowns": scenario["unknowns"],
            "flip_conditions": scenario["flip_conditions"],
            "operator_implication": scenario["operator_implication"],
            "human_review": {
                "rating": None,
                "comments": {key: None for key in scenarios["review_protocol"]["required_comment_fields"]},
                "status": "pending",
            },
            "demo_approved": False,
        })
    return {
        "version": "operating_simulation_v1",
        "persona_id": profile["persona_id"],
        "profile_version": profile["profile_version"],
        "scenario_source_version": scenarios["version"],
        "status": "codex_authored_exploratory_synthesis_not_independent_agent_output",
        "scenario_status": scenarios["scenario_status"],
        "evaluation_target": scenarios["review_protocol"]["purpose"],
        "llm_calls": 0,
        "cost": 0,
        "human_review_status": "pending",
        "demo_approved": False,
        "scenarios": results,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# blog41 시즌별 운영 시뮬레이션 — 사람 검수용",
        "",
        "> 가상 운영 조건을 동일한 작성자 통합 프로필에 적용한 Codex 작성 탐색 종합입니다. 독립 LLM 응답, 실제 고객의 미래 행동 예측, 실제 워커힐 운영 정보가 아닙니다.",
        "",
        f"프로필 `{result['profile_version']}` · 시나리오 `{result['scenario_source_version']}` · LLM 호출 0회 · 사람 검수 대기 · 시연 승인 아님",
        "",
        "## 비교 요약",
        "",
        "| 시즌 / 운영 질문 | 기본 행동 가설 | 판단의 핵심 | 선택을 바꿀 조건 |",
        "|---|---|---|---|",
    ]
    for item in result["scenarios"]:
        hypothesis = item["action_hypothesis"]
        key = " · ".join(e["claim_id"] for e in item["profile_evidence"])
        lines.append(f"| {item['season']} — {item['operator_question']} | **{hypothesis['choice']}** | {hypothesis['statement']} (근거 {key}) | {'; '.join(item['flip_conditions'])} |")
    for item in result["scenarios"]:
        lines.extend([
            "", f"## {item['scenario_id']}", "",
            f"**운영자 질문:** {item['operator_question']}", "",
            "**가상 조건**", "",
        ])
        lines.extend(f"- {condition}" for condition in item["virtual_conditions"])
        lines.extend([
            "", f"**예상 행동 가설 — {item['action_hypothesis']['choice']}**", "",
            item["action_hypothesis"]["statement"], "",
            "**관련 프로필 근거**", "",
        ])
        lines.extend(f"- `{entry['claim_id']}` — {entry['aspect']}: {entry['value']} (층: {entry['claim_layer']}; 범위: {entry['scope']}; 검수: {entry['review_status']})" for entry in item["profile_evidence"])
        lines.extend(["", "**주요 대안**", ""])
        lines.extend(f"- `{alt['choice']}` — {alt['when']}" for alt in item["action_hypothesis"]["alternatives"])
        lines.extend([
            "", "**판단을 바꿀 조건**", "",
        ])
        lines.extend(f"- {condition}" for condition in item["flip_conditions"])
        lines.extend(["", f"**운영 시사점:** {item['operator_implication']}", "", f"**미확인:** {'; '.join(item['unknowns'])}", "", f"**해석 제한:** {item['action_hypothesis']['why_not_a_prediction']}", ""])
    lines.extend([
        "## 사람 검수",
        "",
        "각 시나리오를 `납득 / 보완 필요 / 납득 어려움`으로 표시하고, 아래 네 축과 수정 이유를 기록한다. 현재 평가는 모두 비어 있으며 Codex가 사람 검수를 대신하지 않는다.",
        "",
        "| 시나리오 | 판정 | 페르소나 충실도 | 상황 적합성 | 행동 개연성 | 운영 활용성 | 납득되지 않는 점 / 바꿀 근거 |",
        "|---|---|---|---|---|---|---|",
    ])
    lines.extend(f"| {item['scenario_id']} |  |  |  |  |  |  |" for item in result["scenarios"])
    lines.extend([
        "", "## 검수 시 유의사항", "",
        "- 프로필의 사람 검수 상태는 여전히 대기다. 프로필 근거는 입력된 카드/사용자 제공 페이지 메모의 계보를 유지하며, 모든 원문 전사가 완료됐다는 뜻이 아니다.",
        "- 2인 동행은 규모 가설이며 관계는 미상이다. 동행을 연인/부부로 확정하지 않는다.",
        "- 가격, 시간, 번들, 날씨, 운영 가능성은 이 문서에서 명시한 가상 조건이다.",
        "- 선택 가설은 결론이 아니라 검수할 초안이다. 검수 후에도 미래 행동 정확도나 참가 확률로 표현하지 않는다.",
        "- 시연 승인 manifest 등록 전 별도 사람 검수와 명시적 승인이 필요하다.",
        "",
    ])
    return "\n".join(lines)


def build() -> tuple[dict[str, Any], str]:
    result = assemble(load_json(PROFILE_PATH), load_json(SCENARIO_PATH))
    return result, render_markdown(result)


def write() -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result, markdown = build()
    json_path = OUTPUT_DIR / "blog41_seasonal_operator_simulation_v1.json"
    md_path = OUTPUT_DIR / "HUMAN_REVIEW_PACKET.md"
    # Refuse to silently replace an existing artifact; versioned output is immutable.
    for path, content in ((json_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n"), (md_path, markdown)):
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing_to_overwrite_changed_artifact:{path.name}")
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    return json_path, md_path


if __name__ == "__main__":
    paths = write()
    print(json.dumps({"outputs": [str(path) for path in paths], "scenarios": 4, "llm_calls": 0, "human_review": "pending"}, ensure_ascii=False))
