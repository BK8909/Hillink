"""Four controlled wine-event conditions; calculate offline, freeze unexecuted LLM packets."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .dynamic_operating_choice_v1 import POLICY, assert_no_results, decide, digest, evaluate, profile_input

HERE = Path(__file__).resolve().parent
OUT = HERE / "dynamic_wine_v1_artifacts"
PROFILE = HERE / "profile_v3_artifacts" / "blog41_author_profile_v3.json"
FACTOR_LABELS = {
    "food_experience": "식음 경험의 제한적 전이",
    "current_meal_goal": "이번 저녁 목적의 충족도",
    "new_experience": "새로운 호텔 경험 검토",
    "scenic_space": "공간·조망 경험",
    "incremental_cost": "대안 대비 실질 비용",
    "time_burden": "현재 일정의 시간 투입",
}
SYSTEM = """제공된 프로필과 이번 가상 환경만 사용하여 호텔 고객의 구체적인 다음 행동을 판단한다.
후기의 사실, 개인 경험에서 도출한 추론, 현재 환경 판단을 구별한다. 여러 호텔 경험의 참여는 새로운 경험을 검토할 단서가 될 수 있다.
명시적 주류 취향이 없다는 사실을 비선호로 바꾸지 않는다. 과거 목적을 이번 목적이라고 확정하지 않는다.
행사 예약, 일반 식당 예약, 명시된 무료 사전 관람 후 결정, 기존 일정 유지 중 하나를 고른다.
예약 선택은 예약 성공이나 실제 이용 완료가 아니다. 제시된 출력 스키마를 지킨다.
다른 응답·정답·검수 의견은 제공되지 않았다. 점수표가 제공된 경우에도 그 합계나 권위를 정답으로 취급하지 말고 근거를 독립적으로 검토한다."""


def wine_conditions() -> dict[str, dict]:
    base = {
        "status": "fictional_operating_conditions",
        "event_title": "가상 가을 와인·푸드 페어",
        "visit": {"party_size": 2, "party_description": "성인 동행 2인으로 설정; 관계 미상",
                  "purpose": "휴식 목적 숙박 중 저녁 식사와 자유시간", "meal_goal": 1.0,
                  "free_minutes": 150, "alcohol_eligible": True},
        "schedule": {"event": "18:00–20:00", "restaurant": "18:00–20:00", "reservation_deadline": "17:50"},
        "reference_dinner_price_krw": 100000,
        "pairing_courses_per_meal": 3,
        "preview": {"available": True, "time": "17:30–17:45", "price_krw": 0,
                    "condition": "공개 메뉴·분위기를 확인 가능; 시음·식사는 포함하지 않으며 예약 성공은 보장하지 않음"},
        "options": [
            {"option_id": "WINE_FAIR", "action": "reserve_event", "available": True,
             "price_krw": 120000, "guest_benefit_krw": 0, "food_courses": 3,
             "novelty": 1.0, "scenic_space": 0.8, "duration_minutes": 120,
             "alcohol_required": False,
             "description": "와인 시음 4종과 음식 페어링. 같은 크기의 실질적 음식 3코스를 한 끼로 설정. 비음주 동행은 무알코올 대체 가능"},
            {"option_id": "REGULAR_DINNER", "action": "reserve_restaurant", "available": True,
             "price_krw": 100000, "guest_benefit_krw": 0, "food_courses": 3,
             "novelty": 0.0, "scenic_space": 0.4, "duration_minutes": 120,
             "alcohol_required": False, "description": "행사 없는 일반 저녁 식사; 충분한 한 끼, 보통의 실내 공간"},
        ],
        "assumptions": [
            "일시·메뉴·가격·분위기 수치·입장 자격·비음주 대안은 연구용 가상값이다. 실제 워커힐 운영 사실이 아니다.",
            "한 코스의 양과 품질을 고정하고 세 코스를 저녁 한 끼로 보는 초기 계산 가정이다. 코스 수가 실제 만족도를 측정하는 것은 아니다.",
            "새로움과 공간 적합도는 호텔이 제시한 가상 선택지 속성이며 고객의 관측 선호 점수가 아니다.",
            "이번 동행과 목적은 실험 조건이며 과거 후기에서 확정된 동행·목적으로 저장하지 않는다.",
            "어떤 성인에게도 음주나 와인 선호를 요구하지 않는다. 자격과 개인적 음주 선호는 별개다.",
        ],
    }
    conditions = {key: deepcopy(base) for key in "ABCD"}
    conditions["B"]["options"][0]["food_courses"] = 1
    conditions["C"]["options"][0]["guest_benefit_krw"] = 30000
    conditions["D"]["options"][0]["price_krw"] = 160000
    return conditions


def response_schema(option_ids: list[str], claim_ids: list[str]) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["action", "selected_option", "rationale", "personal_facts", "personal_inferences", "current_context", "alternatives", "change_conditions", "operator_implication", "uncertainty"],
        "properties": {
            "action": {"enum": ["reserve_event", "reserve_restaurant", "inspect_then_decide", "keep_existing_schedule"]},
            "selected_option": {"enum": option_ids + [None]},
            "rationale": {"type": "string", "minLength": 1},
            "personal_facts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                "required": ["claim_id", "statement"], "properties": {"claim_id": {"enum": claim_ids}, "statement": {"type": "string", "minLength": 1}}}},
            "personal_inferences": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                "required": ["claim_ids", "inference", "limitation"], "properties": {
                    "claim_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"enum": claim_ids}},
                    "inference": {"type": "string", "minLength": 1}, "limitation": {"type": "string", "minLength": 1}}}},
            **{key: {"type": "array", "items": {"type": "string", "minLength": 1}} for key in ("current_context", "alternatives", "change_conditions", "uncertainty")},
            "operator_implication": {"type": "string", "minLength": 1},
        },
    }


def packet(profile: dict, environment: dict, with_factors: bool) -> dict:
    inputs = {"profile": deepcopy(profile), "environment": deepcopy(environment)}
    if with_factors:
        table = evaluate(profile, environment)
        inputs["factor_table"] = [{"option_id": row["option_id"], "feasible": row["feasible"],
                                   "constraints": row["constraints"], "factors": row["factors"]} for row in table["options"]]
    assert_no_results(inputs)
    return {"version": "dynamic_wine_packet_v1", "mode": "with_factors" if with_factors else "profile_and_environment_only",
            "system": SYSTEM, "inputs": inputs,
            "response_schema": response_schema([o["option_id"] for o in environment["options"]], [c["claim_id"] for c in profile["claims"]])}


def validate_response(response: dict, request: dict) -> list[str]:
    """Structural intake only; human plausibility still requires actual review."""
    import jsonschema
    errors = sorted({error.message for error in jsonschema.Draft202012Validator(request["response_schema"]).iter_errors(response)})
    if errors:
        return errors
    options = {o["option_id"]: o for o in request["inputs"]["environment"]["options"]}
    feasibility = {o["option_id"]: o["feasible"] for o in evaluate(request["inputs"]["profile"], request["inputs"]["environment"])["options"]}
    action, selected = response["action"], response["selected_option"]
    if action.startswith("reserve_"):
        if selected not in options or options[selected]["action"] != action:
            errors.append("action_option_mismatch")
        elif not feasibility[selected]:
            errors.append("unavailable_selection")
    elif selected is not None:
        errors.append("non_reservation_action_requires_null_option")
    if action == "inspect_then_decide" and not request["inputs"]["environment"]["preview"]["available"]:
        errors.append("preview_unavailable")
    return errors


def condition_sweeps(profile: dict, environment: dict) -> dict:
    """Actual recomputation. Grid is fixed before reading experiment outcomes."""
    out = {"price": [], "food": []}
    for price in (60000, 90000, 120000, 160000, 200000):
        changed = deepcopy(environment)
        changed["options"][0]["price_krw"] = price
        decision = decide(profile, changed)
        out["price"].append({"price_krw": price, "net_price_krw": price - changed["options"][0]["guest_benefit_krw"],
                             "action": decision["action"], "selected_option": decision["selected_option"]})
    for courses in (0, 1, 2, 3):
        changed = deepcopy(environment)
        changed["options"][0]["food_courses"] = courses
        decision = decide(profile, changed)
        out["food"].append({"food_courses": courses, "action": decision["action"], "selected_option": decision["selected_option"]})
    return out


def build(profile: dict | None = None) -> dict:
    profile = profile_input(json.loads(PROFILE.read_text(encoding="utf-8"))) if profile is None else deepcopy(profile)
    conditions = wine_conditions()
    cells = {}
    for condition, environment in conditions.items():
        method = decide(profile, environment)
        sensitivity = []
        for name in ("new_experience", "incremental_cost"):
            for multiplier in (0.75, 1.25):
                varied = deepcopy(POLICY)
                varied["weights"][name] *= multiplier
                sensitivity.append({"factor": name, "multiplier": multiplier, "result": decide(profile, environment, varied)["action"]})
        sweeps = condition_sweeps(profile, environment)
        cells[condition] = {"environment": environment, "method_result": method,
                           "tested_change_conditions": {axis: [row for row in rows if row["action"] != method["action"]] for axis, rows in sweeps.items()},
                           "weight_sensitivity": sensitivity,
                           "packets": {mode: packet(profile, environment, mode == "with_factors") for mode in ("without_factors", "with_factors")}}
    transitions = []
    baseline = cells["A"]["method_result"]
    for condition in "BCD":
        changed = cells[condition]["method_result"]
        baseline_event = baseline["audit"]["options"][0]
        changed_event = changed["audit"]["options"][0]
        changed_factors = [new["factor"] for old, new in zip(baseline_event["factors"], changed_event["factors"]) if old["contribution"] != new["contribution"]]
        transitions.append({"comparison": "A→" + condition, "action_before": baseline["action"], "action_after": changed["action"],
                            "action_changed": baseline["action"] != changed["action"], "changed_factors": changed_factors,
                            "event_score_change": round(changed_event["score"] - baseline_event["score"], 6)})
    return {"version": "dynamic_wine_study_v1.0", "profile": profile, "profile_sha256": digest(profile),
            "policy": deepcopy(POLICY), "policy_sha256": digest(POLICY), "conditions": cells,
            "computed_condition_changes": transitions,
            "computed_sensitivity": condition_sweeps(profile, conditions["A"]),
            "method_profile_ablation": decide(dict(profile, claims=[]), conditions["A"]),
            "llm_calls": 0, "llm_execution_approved": False, "human_review": "pending", "demo_approved": False}


def report(study: dict) -> str:
    lines = ["# blog41 × 가상 가을 와인페어 — 조건 변경과 행동 재판단", "",
             "고정 프로필과 가상 환경에서 공통 계산으로 만든 행동 가설이다. 독립 LLM 세션은 미실행이며 사람 검수·시연 승인은 대기다.", "",
             "동일 프로필을 고정하고 A를 기준으로 B는 음식 수만, C는 숙박객 혜택만, D는 가격만 변경했다.", "",
             "| 조건 | 음식 수 | 실질 1인 비용 | 계산된 행동 | 상위 후보 차이 |", "|---|---:|---:|---|---:|"]
    for key, cell in study["conditions"].items():
        option = cell["environment"]["options"][0]
        result = cell["method_result"]
        lines.append(f"| {key} | {option['food_courses']} | {option['price_krw'] - option['guest_benefit_krw']:,}원 | {result['action_label']} / {result['selected_option']} | {result['margin']} |")
    lines.extend(["", "## 운영 조건이 실제로 바꾼 판단", ""])
    for transition in study["computed_condition_changes"]:
        lines.append(f"- {transition['comparison']}: {', '.join(FACTOR_LABELS[f] for f in transition['changed_factors'])} 항목의 계산 기여가 바뀜 → {transition['action_before']}에서 {transition['action_after']}. 행동 변경 여부: {transition['action_changed']}. 동행·이번 방문 목적은 동일하다.")
    lines.extend(["", "## 같은 작성자 프로필에서 계산에 연결한 근거", ""])
    factors = study["conditions"]["A"]["method_result"]["audit"]["profile_factors"]
    for name, feature in factors.items():
        label = "가격 가치 평가의 주목도" if name == "value_attention" else FACTOR_LABELS[name]
        lines.append(f"- {label}: {', '.join(feature['claim_ids']) or '해당 개인 근거 없음'} → {feature['layer']}. 고정된 탐색 전이 강도 {feature['support']}이며 행동 확률이 아니다.")
    lines.extend(["", "실제 여러 시설의 참여 이력으로 새 경험 검토를 추론했다. C14의 리뷰 작성 상세성은 계산에서 제외했고, C09 음료 사진은 주류 취향으로 연결하지 않았다. C06은 이용 사실만 경험 다양성에 쓰며 만족 방향을 부여하지 않았다.", ""])
    for key, cell in study["conditions"].items():
        result = cell["method_result"]
        lines.extend(["", f"## 조건 {key}", "", f"**행동:** {result['action_label']} ({result['selected_option'] or '예약 선택 전 확인'})", "",
                      result["behavior_summary"], "",
                      "**운영 시사점:** " + " ".join(result["operator_implications"]), "",
                      "**새로 계산한 주요 이유**", ""])
        if result["reasons"]:
            lines.extend(f"- {reason}" for reason in result["reasons"])
        else:
            lines.append("- 상위 선택지의 차이가 작거나 이용 제약이 있어, 사전 관람 가능 조건 또는 기존 일정에 따라 행동을 정했다.")
        lines.extend(["", "<details><summary>계산 근거와 대안 비교</summary>", "", "| 선택지 | 내부 탐색 점수 | 음식 충족도 | 이용 제약 |", "|---|---:|---:|---|"])
        for row in result["audit"]["options"]:
            lines.append(f"| {row['option_id']} | {row['score']} | {row['meal_fraction']:.2f} | {'; '.join(row['constraints']) or '가상 조건상 없음'} |")
        lines.extend(["", "상위 후보 간 차이를 만든 항목: " + ", ".join(f"{FACTOR_LABELS[d['factor']]} {d['difference']:+.3f}" for d in result["top_option_comparison"]), ""])
        lines.extend(["해당 조건에서 실제 재계산하여 다른 행동이 나온 값: " + json.dumps(cell["tested_change_conditions"], ensure_ascii=False), "",
                      "가격·새 경험 가중치 ±25%의 계산 행동: " + ", ".join(f"{r['factor']}×{r['multiplier']}: {r['result']}" for r in cell["weight_sensitivity"]), "", "</details>", ""])
    lines.extend(["## 실제 재계산으로 확인한 변경 조건", "", "| 변경 변수 | 값 | 행동 |", "|---|---:|---|"])
    for axis, rows in study["computed_sensitivity"].items():
        for row in rows:
            lines.append(f"| {axis} | {row.get('price_krw', row.get('food_courses'))} | {row['action']} / {row['selected_option']} |")
    lines.extend(["", "## 사람 검수 — 독립 모델 응답은 아직 없음", "",
                  "개인 근거를 모두 제거한 A 조건의 계산 행동: " + study["method_profile_ablation"]["action_label"] + ". 계산 구조 안에서의 제거 비교이며 실제 개인 행동의 인과효과는 아니다.", "",
                  "A~D × 프로필·환경만 / 요인표 포함 8개 입력은 생성됐지만 실행되지 않았다. 요인표 없는 조건에는 계산 결과·행동·순위·기존 가설·검수 의견이 없다. 요인표 포함 조건도 합계나 승자 선택 없이 요인별 기여를 제공한다.", "",
                  "| 조건 | 계산 행동의 개연성 | 무표 LLM 행동 | 유표 LLM 행동 | 성향 연결 | 변화의 타당성 | 운영 활용 | 구체적 의견 |",
                  "|---|---|---|---|---|---|---|---|", *[f"| {key} | 미검수 | 미실행 | 미실행 |  |  |  |  |" for key in study["conditions"]], "",
                  "판정은 납득 / 보완 필요 / 납득 어려움과 구체적 이유로 남긴다. 미래 행동 예측 정확도나 참가 확률로 평가하지 않는다.", ""])
    return "\n".join(lines)


def _write_new(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError("immutable_artifact_changed:" + path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write() -> dict:
    study = build()
    manifest = {"version": study["version"], "profile_sha256": study["profile_sha256"], "policy_sha256": study["policy_sha256"],
                "packets": [], "independent_sessions_executed": 0, "execution_approved": False,
                "proposed_session_contract": {"count": 8, "model_id": "gpt-6.1-sol", "reasoning_effort": "high",
                    "one_packet_per_independent_session": True, "responses_per_packet": 1, "automatic_retries": 0,
                    "isolation": "fresh_conversational_context_proposed; actual_tool_and_OS_isolation_must_be_recorded_at_execution",
                    "product_api_calls": 0, "usage_estimate": "packet character counts supplied; session tokens not yet measured; no monetary conversion",
                    "stop_conditions": ["input_hash_or_model_mismatch", "evaluation_or_other_response_exposure", "structural_response_failure", "unsupported_personal_memory"]}}
    manifest["source_sha256"] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in
        ("dynamic_operating_choice_v1.py", "dynamic_wine_study_v1.py", "dynamic_operating_policy_v1.json")}
    for condition, cell in study["conditions"].items():
        _write_new(OUT / "environments" / f"{condition}.json", json.dumps(cell["environment"], ensure_ascii=False, indent=2) + "\n")
        for mode, request in cell["packets"].items():
            name = f"{condition}_{mode}.json"
            _write_new(OUT / "packets" / name, json.dumps(request, ensure_ascii=False, indent=2) + "\n")
            manifest["packets"].append({"condition": condition, "mode": mode, "file": "packets/" + name,
                                        "request_sha256": digest(request), "serialized_characters": len(json.dumps(request, ensure_ascii=False))})
    stored = deepcopy(study)
    for condition, cell in stored["conditions"].items():
        cell["packets"] = [row for row in manifest["packets"] if row["condition"] == condition]
    _write_new(OUT / "computed_study.json", json.dumps(stored, ensure_ascii=False, indent=2) + "\n")
    _write_new(OUT / "preparation_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_new(OUT / "HUMAN_REVIEW_PACKET.md", report(study))
    return manifest


if __name__ == "__main__":
    result = write()
    print(json.dumps({"packets": len(result["packets"]), "request_set_sha256": digest(result), "model_calls": 0}))
