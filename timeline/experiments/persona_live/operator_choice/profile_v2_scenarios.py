"""V2 scenario cards: all prices and changes are explicit experiment assumptions."""
from copy import deepcopy

def scenarios():
    return {
      "wine_fair_addition": {"question": "신규 와인 행사가 추가되면 기존 일정과 비교해 참여를 고려하는가?", "changed": ["event_available"], "scenario_assumptions": {"price_krw": None, "wine_preference": "not_assumed", "replaces_existing_activity": False}, "options": ["REST", "WALK", "SKYARD", "THE_BUFFET", "WINE_FAIR"]},
      "wine_fair_replacement": {"question": "행사로 기존 포레스트파크 운영이 대체되면 선택은 달라지는가?", "changed": ["event_available", "FOREST_PARK_availability"], "scenario_assumptions": {"price_krw": None, "wine_preference": "not_assumed", "replaces_existing_activity": True}, "options": ["REST", "WALK", "SKYARD", "WINE_FAIR"]},
      "riverpark": {"question": "리버파크 개장이 물 활동 선택을 바꾸는가?", "changed": ["RIVERPARK_availability"], "scenario_assumptions": {"season": "summer", "weather": "not_specified", "admission": "must_be_checked", "price_krw": None}, "options": ["REST", "WALK", "VISTA_POOL", "RIVERPARK"]},
      "paid_breakfast": {"question": "조식 포함 혜택이 없을 때 유료 조식을 구매하는가?", "changed": ["entitlement", "price", "breakfast_alternative"], "conditions": ["included", "self_paid", "voucher_or_membership", "same_quality_price_varied"], "scenario_assumptions": {"restaurant_price_krw": None, "entitlement": "off_or_voucher_or_included_separate_conditions", "breakfast_quality": "held_constant", "alternatives": ["room_rest", "other_meal"]}, "options": ["BUY_BREAKFAST", "USE_VOUCHER", "ALTERNATIVE", "SKIP"]}
    }

def signals_from_profile(profile, options):
    """Generic bounded mappings; source facts never become satisfaction claims."""
    codes = {o["option_code"] for o in options}
    result = []
    for pref in profile.get("explicit_preferences", []):
        value = pref.get("value", {})
        if value.get("feature") == "broad_facility_use":
            applicable = sorted(codes & {"WINE_FAIR", "RIVERPARK", "VISTA_POOL", "SKYARD"})
            if applicable:
                result.append({"signal_id":"profile-facility-breadth", "evidence_root":"|".join(pref["evidence_ids"]),
                  "category":"personal_fit", "options":applicable, "direction":1, "reliability":.65,
                  "relevance":.25, "basis":"카드상 시설 이용 폭 단서의 약한 범위 제한 전이; 만족/신규 행사 취향으로 일반화하지 않음."})
    for event in profile.get("behavioral_commitments", []):
        place = str(event.get("value", {}).get("place", ""))
        if "POOL" in place or place == "RIVERPARK":
            applicable = sorted(codes & {"RIVERPARK", "VISTA_POOL", "GRAND_POOL"})
            if applicable:
                result.append({"signal_id":"profile-water-activity:" + place,
                  "evidence_root":"|".join(event["evidence_ids"]), "category":"engagement_fit",
                  "options":applicable, "direction":1, "reliability":.7, "relevance":.45,
                  "basis":"과거 물 활동 이용은 참여 경험의 제한적 전이; 만족도·실내외 선호는 미상."})
    return result

def options_for(scenario_id, env):
    spec = scenarios()[scenario_id]
    codes = list(spec["options"])
    if scenario_id == "riverpark" and env == "off": codes.remove("RIVERPARK")
    if scenario_id == "riverpark" and env == "on": pass
    if scenario_id == "wine_fair_addition" and env == "off": codes.remove("WINE_FAIR")
    if scenario_id == "wine_fair_replacement" and env == "off": codes.remove("WINE_FAIR"); codes.append("FOREST_PARK")
    if scenario_id.startswith("wine_fair") and env == "on": pass
    return [{"option_code": c, "available": True, "scenario_assumption": True} for c in codes]

def paid_breakfast_case(condition):
    """Price values below are fictional sensitivity levels, never hotel prices."""
    levels = {
      "included": ("USE_INCLUDED", "SKIP", None, "included_in_package"),
      "self_paid": ("BUY_BREAKFAST", "ALTERNATIVE", 35000, "self_paid_hypothetical"),
      "voucher": ("USE_VOUCHER", "BUY_BREAKFAST", None, "voucher_eligibility_stipulated"),
      "price_low": ("BUY_BREAKFAST", "ALTERNATIVE", 25000, "hypothetical_price_level"),
      "price_high": ("BUY_BREAKFAST", "ALTERNATIVE", 55000, "hypothetical_price_level"),
    }
    a,b,price,status=levels[condition]
    codes=list(dict.fromkeys((a,b,"SKIP")))
    options=[{"option_code":code,"available":True,"scenario_assumption":True} for code in codes]
    signals=[]
    if price is not None:
        signals.append({"signal_id":"CTX-breakfast-price-"+condition,"evidence_root":"CTX-breakfast-price-"+condition,
          "category":"context_adjustment","options":[a],"direction":-1 if price<=35000 else -2,
          "reliability":1.0,"relevance":min(1.0,price/55000),
          "basis":"가상 가격 수준으로 인한 일반 기회비용 민감도. 개인 절약 성향이 아님."})
    return {"condition":condition,"options":options,"signals":signals,"price_krw":price,
      "price_status":status,"voucher_eligibility":"stipulated_for_condition_only" if condition=="voucher" else "not_assumed",
      "historical_entitlement_transferred":False}
