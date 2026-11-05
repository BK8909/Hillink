"""V1.1 controlled study: broader alternatives and separated decision stages.

Prepares new artifacts only; no model/provider/session execution path is present.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from . import dynamic_operating_choice_v1 as v1
from . import dynamic_wine_study_v1 as study_v1
from .dynamic_operating_choice_v1_1 import (
    LABELS, POLICY, decide, evaluate, feasibility, minute, profile_input, view_frame,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "dynamic_wine_v1_1_artifacts"
PROFILE_PATH = HERE / "profile_v3_artifacts" / "blog41_author_profile_v3.json"
SYSTEM = """고정 프로필과 가상 현재 환경을 바탕으로 구체적인 다음 행동 하나를 판단한다.
여러 호텔 활동에 참여한 이력은 새 경험에 대한 개방성을 추론할 단서다. 동일 방문 내 활동을 독립적인 반복 방문으로 세지 않는다.
이용 후 가격 대비 만족에 유보적이었다는 평가와 예약 전에 돈 쓰기를 주저했다는 행동은 다르다. 확인되지 않은 사전 가격 민감성·지불 한계·정보 확인 습관을 개인 사실로 만들지 않는다.
새 행사에 대한 직접 선호가 없어도 개인 메뉴 기호, 경험 이력, 현재 목적과 일반 상황 판단을 조합할 수 있다.
행사·식당 예약 의향, 메뉴·현장 확인, 객실 식사·휴식, 간단한 식사·야경, 행사 불참·기존 일정 중 제공된 실제 후보를 비교한다.
관심, 확인 계획, 예약 의향, 실제 예약 시도·결과, 실제 이용을 구분한다. 아직 수행한 행동은 없다.
가격·패키지·메뉴·시간·정원·관람 조건은 연구용 가상값이다. 실제 호텔 운영 사실로 표현하지 않는다.
정답·기존 행동·사람 의견은 제공되지 않았다. 보조 표가 있는 조건은 분석 보조 조건이며 그 내용을 정답으로 따를 필요는 없다."""


def wine_conditions(expanded=True):
    def reservation():
        return {"opens_at": "16:00", "closes_at": "17:50", "processing_minutes": 5, "capacity": 20, "occupied": 18}

    def option(code, action, price, courses, serving, quality, effort, space, space_context, rest, novelty=0, reserve=False):
        return {"option_id": code, "action": action, "available": True, "price_krw": price,
                "benefits": [], "food_courses": courses, "serving_fraction_per_course": serving,
                "food_quality": quality, "menu_tags": [], "menu_details_complete": True,
                "novelty": novelty, "scenic_space": space, "space_context": space_context,
                "rest_fit": rest, "effort_minutes": effort, "alcohol_required": False,
                "schedule": {"start": "18:00", "end": "20:00"} if reserve else {"start": "18:00", "end": "19:00"},
                "reservation": reservation() if reserve else None,
                "chef_collaboration": None, "package_label": None}

    event = option("WINE_FAIR", "reserve_event", 120000, 3, 1 / 3, 1, 120, .8, "night_view", 0, 1, True)
    event["menu_details_complete"] = False
    dinner = option("REGULAR_DINNER", "reserve_restaurant", 100000, 3, 1 / 3, 1, 120, .4, "dining_view", 0, reserve=True)
    dinner["menu_tags"] = ["standard_dinner"]
    room = option("ROOM_MEAL", "room_meal_and_rest", 25000, 1, 1, .5, 60, 0, "none", 1)
    room["menu_tags"] = ["chicken"]
    simple = option("SIMPLE_MEAL_VIEW", "simple_meal_and_view", 40000, 1, 1, .5, 90, .8, "night_view", 0)
    simple["schedule"]["end"] = "19:30"
    outside = option("KEEP_SCHEDULE", "keep_existing_schedule", 0, 0, 0, 0, 0, 0, "none", 0)
    outside["schedule"] = None
    base = {
        "version": "operating_environment_v1.1", "status": "fictional_operating_conditions", "now": "17:00",
        "visit": {"party_size": 2, "relationship": "unspecified", "payer_count": None, "meal_goal": 1, "rest_goal": .5,
                  "purpose": "가상 2인 휴식 숙박 중 저녁 식사와 자유시간", "alcohol_eligible": True, "blocked_intervals": []},
        "reference_dinner_price_krw": 100000,
        "options": [event, dinner] + ([room, simple] if expanded else []) + [outside],
        "preview": {"available": True, "target_option": "WINE_FAIR", "start": "17:30", "end": "17:45",
                    "price_krw": 0, "resolves": ["menu_match"], "future_seats": "assumed_remaining_for_planning_only"},
        "assumptions": [
            "모든 운영 조건·가격·정원·메뉴·품질 수준·시간은 연구용 가상값이다.",
            "행사의 같은 크기 음식 3코스를 한 끼로 보는 양 가정은 유지한다. 음식 이름·품질은 별도 입력이다.",
            "객실 식사는 1인 25,000원(2인 총50,000원)과 60분을 가정한다. 원문의 실제 가격이나 배달 가능 정책으로 주장하지 않는다.",
            "간단한 식사와 야경은 1인40,000원, 90분, 현재 이용 가능하다고 가정한다.",
            "관람으로 메뉴·재료를 확인할 수 있다고 가정하지만 실제 맛 만족도나 개인 성향은 알 수 없다.",
            "관람 뒤 잔여 정원은 계획용 가정이다. 예약 성공은 아직 발생하지 않았다.",
            "식음 품질1.0/간단 식사0.5, 휴식 목표0.5는 초기 가상 시나리오 지표로서 측정된 개인 효용이 아니다.",
        ],
    }
    out = {key: deepcopy(base) for key in "ABCD"}
    out["B"]["options"][0]["food_courses"] = 1
    out["C"]["options"][0]["benefits"] = [{"benefit_id": "stay_guest_30000", "entitlement_id": "guest_event_credit",
                                           "amount_krw": 30000, "eligibility": "stipulated_for_this_scenario"}]
    out["D"]["options"][0]["price_krw"] = 160000
    return out


def compact(result):
    return {key: result[key] for key in ("action", "action_label", "selected_option", "lifecycle", "selected_worst_case_regret")}


def variants(profile, base):
    cases = {}
    for key, value in (("menu_familiar", ["pizza", "garlic", "olive_oil"]), ("menu_other", ["seafood", "cheese"])):
        changed = deepcopy(base)
        changed["options"][0]["menu_details_complete"] = True
        changed["options"][0]["menu_tags"] = value
        cases[key] = {"environment": changed, "result": decide(profile, changed)}
    for key, modify in (
        ("preview_off", lambda e: e["preview"].update(available=False)),
        ("preview_too_late", lambda e: e["preview"].update(start="17:45", end="17:55")),
        ("room_meal_unavailable", lambda e: e["options"][2].update(available=False)),
        ("chef_label_only", lambda e: e["options"][0].update(chef_collaboration="가상 셰프 콜라보")),
        ("package_label_only", lambda e: e["options"][0].update(package_label="가상 객실+행사 패키지")),
        ("package_credit", lambda e: e["options"][0].update(benefits=[{"benefit_id": "package_credit", "entitlement_id": "entry_credit", "amount_krw": 40000, "eligibility": "stipulated_for_this_scenario"}])),
        ("low_food_quality", lambda e: e["options"][0].update(food_quality=.4)),
        ("sold_out", lambda e: e["options"][0]["reservation"].update(occupied=20)),
    ):
        changed = deepcopy(base)
        modify(changed)
        cases[key] = {"environment": changed, "result": decide(profile, changed)}
    for available in (True, False):
        changed = deepcopy(base)
        changed["options"][0]["price_krw"] = 200000
        changed["preview"]["available"] = available
        cases["price_200000_preview_" + str(available).lower()] = {"environment": changed, "result": decide(profile, changed)}
    return cases


def packet(profile, env, assisted):
    inputs = {"profile": deepcopy(profile), "environment": deepcopy(env)}
    if assisted:
        table = evaluate(profile, env)
        inputs["qualitative_analysis_aid"] = [
            {"option_id": row["option_id"], "feasible": row["feasible"], "constraints": row["constraints"],
             "matched_menu_tags": row["matched_menu_tags"],
             "evidence_uses": [{"factor": t["factor"], "claim_ids": t["claim_ids"], "stage": t["stage"]} for t in row["terms"]],
             "unknown_current_menu": any(u["variable"].startswith("menu_match:") for u in row["uncertainty"])}
            for row in table["options"]]
    v1.assert_no_results(inputs)
    claim_ids = [c["claim_id"] for c in profile["claims"]]
    schema = {"type": "object", "additionalProperties": False,
              "required": ["action", "selected_option", "interest", "reason", "evidence_uses", "alternatives", "change_conditions", "operator_implication", "uncertainty", "lifecycle"],
              "properties": {
                  "action": {"enum": list(LABELS)},
                  "selected_option": {"enum": [o["option_id"] for o in env["options"]] + ["PREVIEW_PLAN"]},
                  "interest": {"type": "string", "minLength": 1}, "reason": {"type": "string", "minLength": 1},
                  "evidence_uses": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                      "required": ["claim_id", "use", "explanation"], "properties": {
                          "claim_id": {"enum": claim_ids}, "use": {"enum": ["past_participation", "explicit_menu_preference", "post_appraisal_context", "prepurchase_trait", "current_fit_inference"]},
                          "explanation": {"type": "string", "minLength": 1}}}},
                  **{key: {"type": "array", "items": {"type": "string", "minLength": 1}} for key in ("alternatives", "change_conditions", "uncertainty")},
                  "operator_implication": {"type": "string", "minLength": 1},
                  "lifecycle": {"type": "object", "additionalProperties": False,
                      "required": ["reservation_attempt", "reservation_result", "actual_use"],
                      "properties": {"reservation_attempt": {"const": "not_executed"}, "reservation_result": {"const": "unknown"}, "actual_use": {"const": "not_started"}}},
              }}
    return {"version": "wine_packet_v1.1", "mode": "qualitatively_assisted" if assisted else "unassisted",
            "system": SYSTEM, "inputs": inputs, "response_schema": schema}


def validate_response(response, request):
    import jsonschema
    errors = sorted({e.message for e in jsonschema.Draft202012Validator(request["response_schema"]).iter_errors(response)})
    if errors:
        return errors
    profile, env = request["inputs"]["profile"], request["inputs"]["environment"]
    if response["action"] == "inspect_event":
        if response["selected_option"] != "PREVIEW_PLAN" or not decide(profile, env)["information_plan"]["feasible"]:
            errors.append("invalid_preview_plan")
    else:
        option = next((o for o in env["options"] if o["option_id"] == response["selected_option"]), None)
        if option is None or option["action"] != response["action"] or feasibility(option, env):
            errors.append("action_option_or_feasibility_mismatch")
    claims = {c["claim_id"]: c for c in profile["claims"]}
    for use in response["evidence_uses"]:
        if claims[use["claim_id"]]["aspect"] in v1.VALUE_ASPECTS and use["use"] != "post_appraisal_context":
            errors.append("post_appraisal_miscast_as_pre_purchase_evidence")
    return sorted(set(errors))


def build():
    raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile = profile_input(raw)
    frozen = json.loads((HERE / "dynamic_wine_v1_artifacts" / "computed_study.json").read_text(encoding="utf-8"))
    conditions, restricted = wine_conditions(), wine_conditions(expanded=False)
    cells = {}
    for key, env in conditions.items():
        reduced = deepcopy(frozen["profile"])
        reduced["claims"] = [c for c in reduced["claims"] if c["aspect"] not in v1.VALUE_ASPECTS]
        cells[key] = {"environment": env, "v1_frozen_result": frozen["conditions"][key]["method_result"],
                      "v1_price_stage_ablation": v1.decide(reduced, study_v1.wine_conditions()[key]),
                      "v1_1_restricted_result": decide(profile, restricted[key]), "v1_1_result": decide(profile, env)}
    sensitivity = {"prices": [], "food_courses": [], "old_D_boundary": [], "new_D_policy": []}
    for price in (60000, 90000, 120000, 160000, 200000, 240000):
        env = deepcopy(conditions["A"])
        env["options"][0]["price_krw"] = price
        sensitivity["prices"].append({"price_per_person": price, "party_total": price * env["visit"]["party_size"], "result": compact(decide(profile, env))})
    for count in (0, 1, 2, 3):
        env = deepcopy(conditions["A"])
        env["options"][0]["food_courses"] = count
        sensitivity["food_courses"].append({"count": count, "result": compact(decide(profile, env))})
    for boundary in (.1, .25, .5):
        p = deepcopy(v1.POLICY)
        p["weights"]["new_experience"] *= .75
        p["decision_margin_for_inspection"] = boundary
        r = v1.decide(frozen["profile"], study_v1.wine_conditions()["D"], p)
        sensitivity["old_D_boundary"].append({"boundary": boundary, "novelty_multiplier": .75, "action": r["action"], "margin": r["margin"]})
    for coefficient in (.25, .5, .75):
        p = deepcopy(POLICY)
        p["general_cost_attention"] = coefficient
        sensitivity["new_D_policy"].append({"generic_cost_attention": coefficient, "result": compact(decide(profile, conditions["D"], p))})
    for coefficient in (0, .55):
        p = deepcopy(POLICY)
        p["transfer_levels"]["new_experience_upper"] = coefficient
        sensitivity["new_D_policy"].append({"novelty_upper": coefficient, "result": compact(decide(profile, conditions["D"], p))})
    no_post = deepcopy(profile)
    no_post["claims"] = [c for c in no_post["claims"] if c["aspect"] not in v1.VALUE_ASPECTS]
    changed_purpose = deepcopy(conditions["B"])
    changed_purpose["visit"]["rest_goal"] = 0
    return {"version": "dynamic_wine_study_v1.1", "profile": profile, "policy": deepcopy(POLICY), "conditions": cells,
            "D_variants": variants(profile, conditions["D"]), "sensitivity": sensitivity,
            "D_post_appraisal_removal": decide(no_post, conditions["D"]),
            "D_profile_removal": decide(dict(profile, claims=[]), conditions["D"]),
            "B_no_current_rest_goal": {"environment": changed_purpose, "result": decide(profile, changed_purpose)},
            "generalization": "only_one_author_integrated_V3_profile_available; no_other_customer_profiles_invented",
            "model_calls": 0, "human_review": "pending", "demo_approved": False}


def _write(path: Path, value):
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError("versioned_artifact_changed:" + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def report(study):
    lines = ["# blog41 가상 와인페어 V1.1 — 운영 조건과 다음 행동", "",
             "같은 고객에게 A~D의 음식·가격·혜택만 바꿔 계산했다. 사후 가치 평가를 사전 가격 회피 성향으로 쓰지 않는다. 규칙 엔진의 탐색 결과이며 독립 LLM·사람 검수·시연 승인은 아직 없다.", "",
             "| 조건 | 음식 | 2인 실질 행사비 | 보존 V1 | V1.1 다음 행동 | 예약·이용 상태 |", "|---|---:|---:|---|---|---|"]
    for key, cell in study["conditions"].items():
        event = cell["v1_1_result"]["audit"]["options"][0]
        r = cell["v1_1_result"]
        lines.append(f"| {key} | {cell['environment']['options'][0]['food_courses']}종 | {event['party_total_krw']:,.0f}원 | {cell['v1_frozen_result']['action_label']} | {r['action_label']} | 시도 없음·결과 미상·이용 전 |")
    lines.extend(["", "## 선택에 연결된 사람의 서로 다른 면", "",
                  "- 경험 참여: 운동·수영·족욕은 P6 한 묶음이며 독립 반복 방문으로 계산하지 않는다. 새 경험에 대한 개방성은 범위가 있는 추론이다.",
                  "- 구매 전 기준: 개인의 가격 회피·지불 한계·현장 확인 습관은 미확인이다. 모든 고객에게 적용하는 일반 비용 비교만 사용한다.",
                  "- 경험 후 평가: 피자힐·더뷔페 가치 유보는 국소적인 사후 평가로 보존하며 새 행사의 사전 가격 가중치에 넣지 않는다.",
                  "- 실제 메뉴 기호: 피자·갈릭·올리브오일 특징은 메뉴가 제시되면 직접 연결한다. 같은 근거를 음식 일반 관심에 다시 더하지 않는다.",
                  "- 객실 식사: 실제 외부 음식 이용 경험은 대안의 근거다. 현재 가격·가능 여부·휴식 목적은 가상 조건이다.", ""])
    for key, cell in study["conditions"].items():
        r = cell["v1_1_result"]
        lines.extend([f"## {key}: {r['action_label']}", "", "관심 상태: " + r["lifecycle"]["interest"]["state"] + "; 관심과 예약 의향은 별도다.", "",
                      r["behavior_summary"], "",
                      "선택 이유·대안의 근거는 아래 계산 기록으로 검수한다. 사전 관람은 메뉴 정보가 실제 판단을 바꿀 수 있는 경우에 경쟁하는 계획이며, 단순한 점수 근접 후처리가 아니다.", "",
                      "<details><summary>대안·계산 근거</summary>", "", "| 행동 후보 | 가능한가 | 최대 기회손실 지표(연구 가정) |", "|---|---|---:|"])
        for row in r["alternatives"]:
            lines.append(f"| {LABELS[row['action']]} | 가상 조건상 가능 | {row['worst_case_regret']:.3f} |")
        for row in r["audit"]["options"]:
            if not row["feasible"]:
                lines.append(f"| {row['option_id']} | {'; '.join(row['constraints'])} | — |")
        lines.extend(["", "운영자 해석: 실제 메뉴·정량·품질 정보와 실질 총액을 제시하고, 일반 식사·객실 식사 등 대안의 조건을 함께 비교한다. 셰프 이름이나 패키지 이름만으로는 행동 보너스를 부여하지 않는다.", "",
                      "이 지표는 선언된 불확실성 구간에서 최선값을 놓치는 최대 차이다. 실제 고객의 후회 감정·효용·확률을 측정한 값이 아니다.", "", *["- " + s for s in r["reasons"]], "",
                      json.dumps(r["information_plan"], ensure_ascii=False, indent=2), "", "</details>", ""])
    lines.extend(["## D에서 운영자가 바꾼 값", "", "| 변경 | 다음 행동 |", "|---|---|"])
    for key, cell in study["D_variants"].items():
        lines.append(f"| {key} | {cell['result']['action_label']} |")
    lines.extend(["", "## 사람 검수", "",
                  "각 축에 납득 / 보완 필요 / 납득 어려움과 이유를 남긴다. 사용자 예비 의견을 공식 사람 검수로 등록하지 않았다.", "",
                  "| 조건 | 페르소나 충실도·이유 | 상황 적합성·이유 | 행동 개연성·이유 | 운영 활용성·이유 |", "|---|---|---|---|---|",
                  *[f"| {key} | 미검수 | 미검수 | 미검수 | 미검수 |" for key in study["conditions"]], "",
                  "LLM 무표·질적 보조표 조건은 미실행이다. 보조 조건은 계산 보조를 받은 판단이고, 무표 조건도 제시된 후보 목록으로 선택 공간이 제한된다.", ""])
    return "\n".join(lines)


def write():
    study = build()
    manifest = {"version": study["version"], "profile_sha256": v1.digest(study["profile"]), "policy_sha256": v1.digest(POLICY),
                "packets": [], "execution_approved": False, "model_calls": 0,
                "proposed_execution": {"model": "gpt-6.1-sol", "reasoning": "high", "sessions": 8, "responses_per_session": 1, "retries": 0, "product_api": 0,
                                       "phases": [{"phase": 1, "sessions": 4, "mode": "unassisted", "approved": False},
                                                  {"phase": 2, "sessions": 4, "mode": "assisted", "approved": False}],
                                       "isolation": "one_new_context_per_packet; actual_OS_and_tools_isolation_to_be_recorded_if_approved"}}
    for condition, cell in study["conditions"].items():
        _write(OUT / "environments" / (condition + ".json"), cell["environment"])
        for assisted in (False, True):
            mode = "assisted" if assisted else "unassisted"
            request = packet(study["profile"], cell["environment"], assisted)
            name = f"packets/{condition}_{mode}.json"
            _write(OUT / name, request)
            manifest["packets"].append({"condition": condition, "mode": mode, "file": name, "request_sha256": v1.digest(request)})
    preserved = [HERE / name for name in ("dynamic_operating_choice_v1.py", "dynamic_operating_policy_v1.json", "dynamic_wine_study_v1.py")]
    preserved += sorted((HERE / "dynamic_wine_v1_artifacts").rglob("*.json"))
    manifest["preserved_v1_sha256"] = {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in preserved}
    manifest["source_sha256"] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in
                                  ("dynamic_operating_choice_v1_1.py", "dynamic_operating_policy_v1_1.json", "dynamic_wine_study_v1_1.py")}
    _write(OUT / "computed_study.json", study)
    _write(OUT / "viewer_frames_proposal.json", {key: view_frame(cell["v1_1_result"]) for key, cell in study["conditions"].items()})
    _write(OUT / "preparation_manifest.json", manifest)
    _write(OUT / "HUMAN_REVIEW_PACKET.md", report(study))
    return manifest


if __name__ == "__main__":
    value = write()
    print(json.dumps({"manifest_sha256": v1.digest(value), "packets": len(value["packets"]), "model_calls": 0}))
