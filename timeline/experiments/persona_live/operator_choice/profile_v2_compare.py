"""Reproducible offline comparison artifacts; no model/session execution."""
from __future__ import annotations
import json
from pathlib import Path
from copy import deepcopy
from .persona_profile_v2 import load_profiles
from .activity_engagement_v2 import profile_engagement
from .decision_v2 import decide, sensitivity
from .profile_v2_scenarios import scenarios, signals_from_profile, options_for, paid_breakfast_case
from .rules import digest
from .appraisal_profile_bridge_v2 import blog41_appraisal_candidates
from .typed_rules import refine
from .decision_method import decide as decide_v1, options_from_stage
from .scenarios import build_pair
from persona_sheet import load_cards

HERE = Path(__file__).resolve().parent
OUT = HERE / "profile_v2_artifacts"

def model_profile(profile):
    """Remove assessor notes and unreviewed AI trait drafts from model context."""
    result = deepcopy(profile)
    result["evaluated_experiences"] = []
    result.pop("contextual_appraisal_candidates", None)
    result.pop("legacy_ai_trait_candidates", None)
    result["model_context_filter"] = "reviewer_reports_unanchored_appraisal_candidates_and_unreviewed_ai_traits_excluded"
    return result

def markdown(profile):
    return f"""# {profile['persona_id']} — 종합 프로필 V2 (잠정)\n\n이 프로필은 승인된 A 카드 요약만 사용했으며 원문 앵커 직접 검증은 아닙니다. 동일 체류 판정: `{profile['source_bundle_status']}`. 사람의 성향 검수 및 시연 승인은 완료되지 않았습니다.\n\n## 현재 카드로 지지되는 인물상\n\nblog41은 VISTA 체류의 카드 기록에서 수영장, 스카이야드, 더뷔페, 피자힐 등 여러 시설·식음 접점을 이용했습니다. 이는 체류 중 여러 시설을 실제 이용한 행동 폭과 탐색 참여를 시사하지만, 각 이용의 만족도·반복 의사나 새로운 와인 행사 선호를 증명하지 않습니다. 카드에는 객실 조망 우선순위가 낮다는 범위 한정 선호가 있고, 이를 식당 조망이나 야외활동으로 확장하지 않습니다. 식음 바우처/할인 사용 기록은 혜택 활용 사실일 뿐 자비 구매 의향이나 일반 가격 민감도의 증거가 아닙니다.\n\n## 구분해서 유지할 추론\n\n- 동행 인원 2명은 사람 검수 추론이며 직접 인원 진술로 확정되지 않았습니다. 관계는 커플·친구·기타 가능성을 경쟁 가설로 둡니다.\n- 과거 방문 목적은 시설 탐방·식음 맥락의 카드 요약입니다. 다음 방문에도 같은 목적이 이어진다는 가정은 하지 않습니다.\n- 연령 자료가 없어 연령대와 그에 따른 통계 집단을 만들지 않습니다.\n- 한호 교차 검수의 식당별 평가 단서는 검수자 보고이며 원문 앵커를 직접 확인하기 전까지 확정 선호로 올리지 않습니다.\n\n## V1에서 추가로 살펴보는 부분\n\nV1의 명시적 선호 규칙은 근거의 직접성·관련성을 보수적으로 비교합니다. V2는 방문 목적, 활동 참여에 필요한 일반적 투입, 혜택/구매 맥락을 별도 범주로 구성해 선택지 적합도를 탐색합니다. 단, 활동 이용을 긍정 선호로 바꾸지 않으며 목적 지속·특정 고객 고정 규칙도 없습니다. 현재 V2 점수는 검증된 예측 성능이나 선택 확률이 아닙니다.\n"""

def make():
    profiles = load_profiles()
    for p in profiles.values(): p["activity_engagement"] = profile_engagement(p)
    profiles["blog41"]["contextual_appraisal_candidates"] = blog41_appraisal_candidates(profiles["blog41"])
    model_profiles = {k:model_profile(v) for k,v in profiles.items()}
    cards = load_cards()
    v1_rules = refine(cards)["rules"]
    out = {"version":"persona_profile_v2_artifacts_0.1", "model_calls":0,
      "profiles":profiles, "scenarios":scenarios(), "decisions":{},
      "llm_packets":{}, "llm_execution":"not_run_no_approval", "human_review":"pending", "demo_approval":False}
    for scenario in scenarios():
      for env in (() if scenario == "paid_breakfast" else ("off","on")):
        opts=options_for(scenario,env)
        signals = signals_from_profile(profiles["blog41"], opts)
        key=f"blog41:{scenario}:{env}"
        out["decisions"][key] = {"decision": decide(opts,signals), "sensitivity": sensitivity(opts,signals),
           "input_sha256": digest({"profile":profiles["blog41"],"scenario":scenarios()[scenario],"environment":env,"signals":signals,"options":opts}),
           "status":"exploratory_method_output_not_observed_behavior"}
        if scenario in {"riverpark", "wine_fair_replacement"}:
          v1name = "riverpark" if scenario == "riverpark" else "wine_fair"
          stage = build_pair(v1name, cards["blog41"]["a_card"]["observed_visit"]["property"])[env]
          out["decisions"][key]["v1_ordinal_method"] = decide_v1(
              [r for r in v1_rules if r["agent_id"] == "blog41"], options_from_stage(stage),
              {"goal_continuity":False,"cost_policy":"opportunity_cost"})
        else:
          out["decisions"][key]["v1_ordinal_method"] = {"status":"not_comparable_scenario_not_supported_in_v1"}
        # Independent future session input has no prechoice table or method result.
        out["llm_packets"][key] = {"packet_version":"profile_v2_no_table_pending_v1", "persona_id":"blog41",
          "profile":model_profiles["blog41"], "scenario":scenarios()[scenario], "environment":env,
          "options":opts, "must_not_receive":["decision_v2 output","V1 result","historical response","Gold","reviewer answer"],
          "status":"prepared_not_executed", "packet_sha256":digest({"profile":profiles["blog41"],"scenario":scenarios()[scenario],"environment":env,"options":opts})}
    out["paid_breakfast_sensitivity"] = {}
    for condition in ("included", "self_paid", "voucher", "price_low", "price_high"):
        case = paid_breakfast_case(condition)
        case["signals"] = signals_from_profile(profiles["blog41"], case["options"]) + case["signals"]
        key = "blog41:paid_breakfast:" + condition
        result = decide(case["options"], case["signals"])
        out["paid_breakfast_sensitivity"][key] = {**case, "decision_method":result,
            "input_sha256":digest({"profile":profiles["blog41"], **case}),
            "status":"scenario_sensitivity_not_personal_purchase_prediction"}
        out["llm_packets"][key] = {"packet_version":"profile_v2_no_table_pending_v1", "persona_id":"blog41",
          "profile":model_profiles["blog41"], "scenario":scenarios()["paid_breakfast"], "condition":case,
          "must_not_receive":["decision_v2 output","V1 result","historical response","Gold","reviewer answer"],
          "status":"prepared_not_executed", "packet_sha256":digest({"profile":profiles["blog41"],"scenario":scenarios()["paid_breakfast"],"condition":case})}
    return out

def write():
    OUT.mkdir(exist_ok=True)
    data=make()
    (OUT/"profiles_v2.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"blog41_profile_v2.json").write_text(json.dumps(data["profiles"]["blog41"],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"blog41_profile_v2.md").write_text(markdown(data["profiles"]["blog41"]),encoding="utf-8")
    (OUT/"comparison_summary.json").write_text(json.dumps({k:v["decision"] for k,v in data["decisions"].items()},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return data

if __name__ == "__main__":
    x=write(); print(json.dumps({"profiles":list(x["profiles"]),"decisions":len(x["decisions"]),"prepared_packets":len(x["llm_packets"]),"model_calls":x["model_calls"]}))
