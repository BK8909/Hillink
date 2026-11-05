"""Offline comparison of V1 availability, card V2, and author-profile V3."""
from __future__ import annotations
import json
from pathlib import Path

from .author_profile_v3 import write as write_profile
from .decision_v2 import decide
from .decision_v3 import compare as compare_v3
from .persona_profile_v2 import load_profiles
from .profile_v2_scenarios import signals_from_profile

HERE=Path(__file__).resolve().parent
OUT=HERE/"profile_v3_artifacts"

SCENARIOS={
 "pizza_revisit":{
   "question":"피자힐 정가·동일 20% 할인·추가 할인과 대체 선택의 비교",
   "conditions":{
     "regular_price":{"status":"directional_counterfactual_from_discounted_review","options":["PIZZA_HILL","ALT_RESTAURANT","ROOM_DINING","REST"]},
     "same_20_percent_discount":{"status":"observed_price_condition_revisited_as_sensitivity_not_repeat_intent","options":["PIZZA_HILL","ALT_RESTAURANT","ROOM_DINING","REST"]},
     "additional_discount_unquantified":{"status":"not_scored_price_response_unknown","options":["PIZZA_HILL","ALT_RESTAURANT","ROOM_DINING","REST"]}},
   "assumptions":{"only_price_condition_changes; menu_and_context_held_unspecified":True}},
 "buffet_dinner":{
   "question":"더뷔페 메뉴 평가와 정가·혜택 이용의 비교",
   "conditions":{
     "full_price":{"options":["THE_BUFFET","ALT_DINING","ROOM_DINING","REST"]},
     "voucher_or_discount":{"options":["THE_BUFFET","ALT_DINING","ROOM_DINING","REST"]}},
   "assumptions":{"actual_eligibility_and_out_of_pocket_amount_unknown":True}},
 "paid_breakfast":{
   "question":"포함 조식 이용과 별도 유료 구매의 구분",
   "conditions":{
     "included":{"options":["USE_INCLUDED","SKIP","ALTERNATIVE"]},
     "self_paid":{"options":["BUY_BREAKFAST","ALTERNATIVE","SKIP"]},
     "voucher":{"options":["USE_VOUCHER","BUY_BREAKFAST","ALTERNATIVE","SKIP"]}},
   "assumptions":{"no_current_price_supplied":True}},
 "wine_fair":{
   "question":"미식 경험과 2인 동행 가설이 신규 와인 행사 검토에 주는 영향",
   "conditions":{"event_details_unknown":{"options":["WINE_FAIR","THE_BUFFET","SKYARD","WALK","REST"]}},
   "assumptions":{"price_schedule_food_pairing_alcohol_options_and_guest_relation_unknown":True}}
}

def _options(codes): return [{"option_code":x,"available":True} for x in codes]

def make():
    profile=write_profile()
    old=load_profiles()["blog41"]
    comparisons={}
    for sid, spec in SCENARIOS.items():
        for condition, cfg in spec["conditions"].items():
            opts=_options(cfg["options"])
            base_signals=signals_from_profile(old,opts)
            comparisons[f"{sid}:{condition}"]={
              "scenario":sid,"condition":condition,"assumptions":spec["assumptions"],
              "V1":{"status":"not_comparable_v1_has_no_equivalent_dining_scenario","result":None},
              "existing_V2":{"status":"card_profile_baseline_no_matching_reviewed_signal" if not base_signals else "card_profile_signal_baseline",
                  "result":decide(opts,base_signals),"signals_used":len(base_signals)},
              "author_integrated_V3":compare_v3(opts,profile,sid,condition),
              "interpretation":"offline_method_comparison_not_observed_behavior_or_prediction"
            }
    return {"version":"author_profile_v3_scenario_comparison_0.1","profile_version":profile["profile_version"],
            "model_calls":0,"human_review":"pending","demo_approved":False,"comparisons":comparisons}

def write():
    OUT.mkdir(exist_ok=True)
    result=make()
    path=OUT/"scenario_comparison_v3.json"
    content=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing_to_overwrite_changed_artifact:{path.name}")
    else:
        path.write_text(content,encoding="utf-8")
    return result

if __name__=="__main__":
    result=write()
    print(json.dumps({"scenarios":len(result["comparisons"]),"model_calls":0,"status":"offline_only"}))
