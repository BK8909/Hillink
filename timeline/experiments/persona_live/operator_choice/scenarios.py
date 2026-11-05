"""Matched afternoon opportunity sets. Historical stage.py is never modified."""
from __future__ import annotations

from copy import deepcopy

import stage as ST

BLOCK = {"id": "afternoon", "start": "15:30", "end": "17:00", "max_choices": 1}
SPECS = {
    "riverpark": {"date": "2026-08-22", "question": "같은 여름 날 야외 수영장 선택지가 추가되면 무엇을 유지·대체하는가?",
                  "delta": "add_RIVERPARK", "interpretation": "개장 선택지 유무 효과. 계절·날짜·날씨는 동일."},
    "wine_fair": {"date": "2026-10-24", "question": "와인페어 개최로 일반 피크닉 공간이 바뀌면 무엇을 유지·대체하는가?",
                  "delta": "replace_FOREST_PARK_with_WINE_FAIR",
                  "interpretation": "행사 추가와 일반 피크닉 공간 대체의 결합 효과. 순수 행사 매력 효과와 구별."},
    "beer_festival": {"date": "2026-10-24", "question": "같은 오후에 가상 맥주 행사가 추가되면 기존 활동과 무엇을 비교하는가?",
                      "delta": "add_BEER_FESTIVAL", "interpretation": "신규 오후 활동 추가. SKYARD와 같은 블록에서 경쟁하며 저녁 식사 대체 실험이 아님."},
}


def _event(code, name, text) -> dict:
    return {"code": code, "name": name, "slot": ST.SLOTS[0], "text": text,
            "price": "일행 전체 50,000원 [가상 실험 요금 · 실제 판매가 아님]",
            "grade": "scenario_assumption", "source": "operator_choice/v1 hypothetical_offer", "virtual": True,
            "eligibility": "성인 주류 제공, 비음주·미성년 동행은 무알코올 대안. 음주 의무 없음 [가상 실험 조건]"}


def build_pair(scenario: str, property: str) -> dict:
    spec = SPECS[scenario]
    raw = ST.build_stage(spec["date"], property, False)
    keep = {"GRAND_POOL", "VISTA_POOL", "SKYARD", "WALK", "REST", "DOUGLAS_SNACK", "THEATRE_OF_LIGHT"}
    options = [deepcopy(o) for o in raw["options"] if o["slot"] == ST.SLOTS[0] and o["code"] in keep]
    common = {
        "scenario_id": scenario, "simulation_date": spec["date"], "observed_date": None,
        "virtual_visit": True, "block": dict(BLOCK), "property": property,
        "weather": "맑고 쾌적함 [고정된 가상 조건]",
        "stay_terms": "가상 1박. 과거 예약·패키지는 이전하지 않는다. 15:00 도착·11:00 퇴실 [실행 가정]",
        "question": spec["question"], "interpretation": spec["interpretation"],
        "conditions": [
            "날짜·동행·객실·날씨·기본 선택지·안내 문구는 두 조건에서 같다.",
            "동행 인원·나이 미상은 그대로다. 이번 블록의 시설 입장은 일행 전원 가능하다고 가정한다(실제 자격 확인 아님).",
            "시설의 현지 표 요금은 버전 고정 참고값. 실제 결제·현재 판매가로 취급하지 않는다. 총액 미상이면 null.",
            "그 외의 식사·행사는 이 90분 선택 실험에서 제시하지 않는다. 선택하지 않은 활동도 비선호로 간주하지 않는다.",
        ], "options": options, "source": "stage.py local snapshot + explicit experimental assumptions",
    }
    if scenario == "wine_fair":
        common["options"].append({"code": "FOREST_PARK", "name": "포레스트 파크 일반 피크닉",
                                  "slot": ST.SLOTS[0], "text": "같은 15:30~17:00 블록 이용 [가상 비교 조건]",
                                  "price": "무료 [가상 비교 조건]", "grade": "scenario_assumption",
                                  "source": "operator_choice/v1 control_space", "virtual": True})
    off, on = deepcopy(common), deepcopy(common)
    off["environment"] = "off"
    on["environment"] = "on"
    if scenario == "riverpark":
        river = next(deepcopy(o) for o in raw["options"] if o["code"] == "RIVERPARK")
        river["text"] += " · 비교 블록 15:30~17:00 [가상 실행 조건]"
        on["options"].append(river)
    elif scenario == "wine_fair":
        on["options"] = [o for o in on["options"] if o["code"] != "FOREST_PARK"]
        on["options"].append(_event("WINE_FAIR", "[가상 비교 조건] 와인페어", "포레스트 파크 15:30~17:00. 일반 피크닉 공간 대체. 글라스·푸드 교환권·무료 입장 혜택은 가정하지 않는다."))
    else:
        on["options"].append(_event("BEER_FESTIVAL", "[가상 행사] 비어 페스티벌",
                                     "별도 지정 공간 15:30~17:00, 맥주 시음·무알코올 음료. 음악 크기 등 소음은 미상. SKYARD와 기존 공간은 그대로 운영."))
    return {"off": off, "on": on}


def validate_pair(pair: dict) -> list[str]:
    a, b = deepcopy(pair["off"]), deepcopy(pair["on"])
    scenario = a["scenario_id"]
    oa = {o["code"]: o for o in a.pop("options")}
    ob = {o["code"]: o for o in b.pop("options")}
    a.pop("environment"); b.pop("environment")
    errors = []
    if a != b:
        errors.append("unmatched_environment_covariates")
    expected_add = {"riverpark": {"RIVERPARK"}, "wine_fair": {"WINE_FAIR"}, "beer_festival": {"BEER_FESTIVAL"}}[scenario]
    expected_remove = {"FOREST_PARK"} if scenario == "wine_fair" else set()
    if set(ob) - set(oa) != expected_add or set(oa) - set(ob) != expected_remove:
        errors.append("unexpected_option_delta")
    if any(oa[c] != ob[c] for c in oa.keys() & ob.keys()):
        errors.append("shared_option_changed")
    if any(o["slot"] != ST.SLOTS[0] for o in list(oa.values()) + list(ob.values())):
        errors.append("non_competing_time_slot")
    return errors
