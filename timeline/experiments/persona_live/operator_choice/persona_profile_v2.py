"""Evidence-layered composite profiles from approved A-cards (not raw-source verification)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
CARDS = HERE.parents[2] / "group_inputs_v1" / "cards" / "customer_card_pairs_v1.json"

LAYER = {
    "observed": ("observed_fact", "card_stated", .9),
    "human_inference": ("strong_inference", "reviewer_inference_not_source_anchor", .65),
    "unknown": ("unknown", "unknown", 0.0),
    "ai_estimate": ("competing_hypothesis", "unreviewed_ai_estimate", .25),
}

def _claim(value, evidence, provenance, scope, rationale, alternatives=None):
    layer, status, strength = LAYER.get(provenance, ("context_inference", provenance, .4))
    return {"value": deepcopy(value), "claim_type": layer, "provenance": provenance,
            "evidence_ids": list(evidence or []), "source_access": "approved_card_only",
            "anchor_verified": False, "confidence_basis": status,
            "heuristic_strength": strength, "scope": scope, "inference": rationale,
            "alternative_hypotheses": alternatives or []}

def build_profile(card: dict) -> dict:
    a = card["a_card"]
    pid = card["blog_id"]
    sv = a["source_verification"]
    party = a["party"]
    party_size = party["size"]
    composition = party["composition"]
    purposes = a["purpose"]
    contexts = [{"stay_id": card["stay_id"], "source_ids": [sv.get("r_id")],
                 "same_stay_status": sv.get("same_stay_status"),
                 "party": _claim({"size": party_size.get("value"), "composition": composition.get("value")},
                    party_size.get("evidence_ids", []) + composition.get("evidence_ids", []),
                    "observed" if party_size.get("provenance") == composition.get("provenance") == "observed" else "human_inference",
                    "this_stay_only", "동행 표기는 현재 A 카드의 출처 층을 보존함."),
                 "purpose": _claim(purposes.get("value"), purposes.get("evidence_ids"), purposes.get("provenance", "unknown"),
                    "this_stay_only", "과거 목적이며 이번 방문에도 지속된다는 뜻이 아님.")}]
    relationships = []
    if party_size.get("value") == 2 and composition.get("value") is None:
        relationships = [_claim(x, party_size.get("evidence_ids", []), "human_inference", "this_stay_only",
            "2인 단서만으로 관계를 확정하지 않음.", ["다른 동행 관계 가능성"])
            for x in ("커플 가능성", "친구 가능성", "기타 동행 가능성")]
    prefs = []
    for p in a.get("explicit_preferences", []):
        claim = _claim({"feature": p.get("feature"), "polarity": p.get("polarity"), "scope": p.get("scope")},
                       p.get("evidence_ids"), "observed", p.get("scope", "unspecified"),
                       "카드상 명시 선호; 다른 범위로 확대하지 않음.")
        claim["claim_type"] = "explicit_preference"
        prefs.append(claim)
    events = []
    for e in a.get("observed_events", []):
        if e.get("kind") in {"stay", "checkin", "transport"}: continue
        events.append(_claim({"kind": e.get("kind"), "place": e.get("place"), "meal": e.get("meal"), "session": e.get("session")},
                             e.get("evidence_ids"), "observed", "recorded_use_not_satisfaction", "이용 사실은 만족·선호의 확정 근거가 아님."))
    benefits = [_claim({"item": ent.get("item"), "use_status": ent.get("use_status"), "quantity": ent.get("quantity")},
                       ent.get("evidence_ids"), ent.get("provenance", "unknown"), "this_stay_only",
                       "혜택 사용은 동일 항목의 자비 구매 의향을 입증하지 않음.") for ent in a.get("entitlements", [])]
    reviewer_leads = []
    if pid == "blog41":
        # PR90 C01-C03 are cross-review leads, not source-verified customer memories.
        reviewer_leads = [
          {"review_id":"PR90:C01", "claim":"피자힐 가격 가치 평가 후보", "aspect":"price_value_not_global_food_like", "status":"reviewer_report_unverified_anchor", "decision_usable":False},
          {"review_id":"PR90:C02", "claim":"스카이야드 야경 경험과 재방문 의향 구별", "aspect":"visit_not_repeat_intent", "status":"reviewer_report_unverified_anchor", "decision_usable":False},
          {"review_id":"PR90:C03", "claim":"더뷔페 메뉴 평가와 가격 가치 유보 후보", "aspect":"mixed_menu_and_value_evaluation", "status":"reviewer_report_unverified_anchor", "decision_usable":False},
        ]
    legacy_ai = a.get("ai_traits", {})
    derived = []
    places = {e["value"].get("place") for e in events}
    if len(places) >= 3:
        derived.append(_claim({"trait":"within_stay_facility_breadth", "direction":"supports_considering_varied_on_property_activities", "decision_usable":True},
            sorted({x for e in events for x in e["evidence_ids"]}), "human_inference", "similar multi-activity hotel stays",
            "한 체류에서 여러 종류의 시설·식음 접점이 기록되어 있어 새로운 호텔 내 활동을 대안으로 검토할 여지가 있다는 약한 가설. 선호/만족/재방문 의향은 아님.",
            ["동선상 부수 이용일 수 있음", "동행 또는 패키지가 이용을 유도했을 수 있음"]))
    return {"persona_id": pid, "profile_version": "persona_profile_v2.0",
        "source_review_ids": [sv.get("r_id")], "source_bundle_status": sv.get("same_stay_status"),
        "source_access": "approved_card_only", "raw_source_verified": False,
        "stay_contexts": contexts, "party_relationship_hypotheses": relationships,
        "demographic_hypotheses": [_claim(None, [], "unknown", "person_level", "카드에 연령 자료가 없음; 나이를 유추해 보충하지 않음.")],
        "trip_purposes": [_claim(purposes.get("value"), purposes.get("evidence_ids"), purposes.get("provenance", "unknown"), "this_stay_only", "현재 방문과 구별되는 과거 목적.")],
        "explicit_preferences": prefs, "evaluated_experiences": reviewer_leads, "behavioral_commitments": events,
        "activity_engagement": [], "purchase_and_benefit_patterns": benefits,
        "price_and_value_orientation": [_claim("unknown_unless_explicitly_evaluated", [], "unknown", "person_level", "결제액·가치 평가 자료만으로 일반 가격 민감성을 만들지 않음.")],
        "decision_style": [], "derived_traits": derived, "alternative_hypotheses": relationships,
        "legacy_ai_trait_candidates": {"values": legacy_ai.get("values", {}), "review_status": legacy_ai.get("review_status", "unreviewed"), "used_in_v2": False},
        "evidence_roots": sorted({x for ev in events for x in ev["evidence_ids"]} | {x for p in prefs for x in p["evidence_ids"]}),
        "profile_uncertainties": list(a.get("unknowns", [])), "review_status": "card_based_provisional_no_raw_anchor_verification",
        "independent_evaluation_eligible": False}

def load_profiles(ids=("blog41", "blog25", "blog59", "blog43")):
    data = json.loads(CARDS.read_text(encoding="utf-8"))
    return {c["blog_id"]: build_profile(c) for c in data["cards"] if c["blog_id"] in ids and c.get("selection_status") == "selected"}
