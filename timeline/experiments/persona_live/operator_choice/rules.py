"""Conservative, deterministic card-to-rule candidates; no latent trait scoring."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evidence_ctx import is_evaluator
from persona_sheet import KIND, MEAL, PLACE, PREF, PURPOSE, SCOPE, load_cards

HERE = Path(__file__).resolve().parent
LIVE = HERE.parent

# Shared feature semantics, never customer-specific behavior overrides.
HYPOTHESES = {
    "on_property_convenience": "비용·시간이 비슷하면 호텔 안에서 해결하는 대안을 고려할 수 있다. 실제 외부 이탈을 금지하지 않는다.",
    "quiet_conversation": "대화가 목적일 때 소음·좌석 조건을 비교할 수 있다. 행사 소음이 미상이면 시끄럽다고 단정하지 않는다.",
    "quiet_rest": "휴식 가치와 행사에 쓰는 시간·활력을 함께 비교할 수 있다. 모든 행사에 불참한다는 규칙은 아니다.",
    "low_view_priority": "객실 선택에서 조망의 우선순위가 낮았다는 단서다. 식당 창가·야경·야외 활동으로 확대하지 않는다.",
    "broad_facility_use": "새 시설도 검토할 수 있다는 가설이다. 새로움 선호 점수나 모든 시설 이용 의무로 바꾸지 않는다.",
    "private_room": "식사에서 별실의 사생활·대화 조건을 비교할 수 있다. 야외 행사 전체를 싫어한다는 뜻은 아니다.",
    "club_benefits_over_room_view": "객실 선택에서 혜택과 조망을 교환한 경험이다. 새 방문에 같은 포함 혜택이 있다고 가정하지 않는다.",
    "repeat_visit": "같은 식당을 재방문한 이력을 참고할 수 있다. 모든 측면의 만족이나 다른 식당 회피로 바꾸지 않는다.",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _hypothesis(feature: str, scope: str) -> str:
    if feature in HYPOTHESES:
        return HYPOTHESES[feature]
    return (f"{SCOPE.get(scope, scope)} 범위의 {PREF.get(feature, feature)} 단서를 이번 대안 비교에 참고할 수 있다. "
            "다른 시설·계절의 고정 취향이나 반드시 선택한다는 규칙으로 일반화하지 않는다.")


def extract_candidates(card: dict) -> list[dict]:
    """Return hypotheses from A-card fields; original anchors are NOT reverified here."""
    agent = card["blog_id"]
    a = card["a_card"]
    out = []
    source_warnings = ["카드 요약 ID는 원문 위치 확인을 보장하지 않는다.", "카드의 미상값: " + ", ".join(a["unknowns"])]
    sv = a.get("source_verification", {})
    if sv.get("url_registry_status") == "unresolved":
        source_warnings.append("공개 출처 대응 미해결 상태가 유지된다.")
    if sv.get("same_stay_status") not in {"confirmed", "confirmed_after_splitting_second_visit"}:
        source_warnings.append("같은 체류 여부에 유보가 있다. 방문 간 기억 결합은 추가 확인 대상이다.")

    def add(path, x, behavior, aspect, hypothesis, scope, relevance, default="observed"):
        ids = x.get("evidence_ids", [])
        eligible_ids = [i for i in ids if not is_evaluator(i)]
        layer = x.get("provenance", default)
        excluded = not eligible_ids or layer in {"ai_estimate", "unknown", "scenario_assumption"}
        if ids and not eligible_ids:
            layer = "evaluator_comment"
        out.append({
            "rule_id": f"{agent}.R{len(out) + 1:02d}", "agent_id": agent,
            "observed_behavior": behavior, "evaluated_aspect": aspect,
            "evidence_ids": eligible_ids, "excluded_evaluator_ids": [i for i in ids if is_evaluator(i)],
            "provenance": {"layer": layer, "source_access": "card_only", "card_path": path,
                           "card_review_status": x.get("review_status", "not_specified"),
                           "original_anchor_verified": False, "extractor": "deterministic_fields_v1"},
            "rule_hypothesis": hypothesis,
            "applicable_context": {"scope": scope, "transfer_limit": "유사 맥락에서만 참고하며 강제 행동·성향 점수로 사용하지 않는다."},
            "counter_evidence": source_warnings + ["상반된 직접 평가가 없다는 사실은 호평이나 무조건적 수용의 증거가 아니다."],
            "confidence_basis": "원문 직접 재검증 없음. " + (
                "인용 가능한 개인 단서가 없어 개인 기억 입력에서 제외한다." if excluded else
                "카드의 명시적 선호 요약이나 이용 사실을 참고하되, 만족·재선택 의도와 구별한다."),
            "evidence_level": "insufficient" if excluded else ("direct_observation" if layer == "observed" else "provisional_hypothesis"),
            "verification_status": "insufficient" if excluded else "card_candidate",
            "scenario_relevance": relevance,
        })

    for i, e in enumerate(a["observed_events"]):
        if e["kind"] in {"checkin", "transport", "stay"}:
            continue
        place = e["place"]
        behavior = f"{PLACE.get(place, place)}: {KIND.get(e['kind'], e['kind'])} ({MEAL.get(e.get('meal'), '')})"
        relevance = (["riverpark"] if "POOL" in place or place == "RIVERPARK" else
                     ["wine_fair", "beer_festival"] if e.get("meal") == "drinks" or "LOUNGE" in place else
                     ["wine_fair", "beer_festival", "riverpark"])
        add(f"a_card.observed_events[{i}]", e, behavior,
            {"target": place, "aspect": "use_or_abandonment", "polarity": "unknown"},
            "이용·포기 경험은 새 선택의 참고가 될 수 있다. 이용만으로 만족·주류 취향·야외 선호를 확정하지 않는다.",
            place, relevance)
    for i, p in enumerate(a["explicit_preferences"]):
        feature, scope = p["feature"], p.get("scope", "unknown")
        add(f"a_card.explicit_preferences[{i}]", p, PREF.get(feature, feature),
            {"target": scope, "aspect": feature, "polarity": p.get("polarity", "unknown")},
            _hypothesis(feature, scope), scope, ["wine_fair", "riverpark", "beer_festival"])
    pu = a["purpose"]
    add("a_card.purpose", pu, " · ".join(PURPOSE.get(v, v) for v in pu.get("value") or []),
        {"target": "stay", "aspect": "visit_purpose", "polarity": "unknown"},
        "지난 방문 목적은 이번 판단의 참고다. 이번 목적이 동일하다는 가정은 별도로 표시하고 새 활동도 고려한다.",
        "visit_purpose", ["wine_fair", "riverpark", "beer_festival"], "human_inference")
    for i, c in enumerate(a["constraints"]):
        add(f"a_card.constraints[{i}]", c, c["feature"],
            {"target": "constraint", "aspect": c["feature"], "polarity": "unknown"},
            "개인 제약의 원래 맥락에서 비교한다. 안전·시간·동행의 현재 조건은 별도 운영 가정이며 취향으로 바꾸지 않는다.",
            c["feature"], ["wine_fair", "riverpark", "beer_festival"])
    return out


def catalogue(cards=None) -> dict:
    cards = load_cards() if cards is None else cards
    selected = {b: c for b, c in cards.items() if c.get("selection_status") == "selected"}
    evaluations = json.loads((LIVE / "review" / "visit_evaluations_1021.json").read_text(encoding="utf-8"))
    leads = [{"agent_id": b, "target": target, "status": value["status"], "aspects": value["aspects"],
              "scope": value.get("visit_scope"), "anchors": value.get("anchors", []),
              "source_layer": "reviewer_report", "used_in_decision_inputs": False}
             for b, values in evaluations.items() if not b.startswith("_") for target, value in values.items()]
    return {
        "version": "operator_rules_v1", "source_commit": "e1a48e691db3337e69d2695ae83206146cb4128d",
        "input_sha256": digest(selected), "source_access": "approved_cards_only",
        "independent_evaluation_eligible": False, "rules": [r for c in selected.values() for r in extract_candidates(c)],
        "review_leads": leads,
        "agents": [{"agent_id": b, "unknowns": c["a_card"]["unknowns"],
                    "observed_visit_audit_only": c["a_card"]["observed_visit"],
                    "human_inferences": c["a_card"]["human_inferences"],
                    "ai_traits_status": c["a_card"].get("ai_traits", {}).get("review_status", "unreviewed"),
                    "ai_traits_used": False} for b, c in selected.items()],
    }


def validate_rules(data: dict) -> list[str]:
    issues, seen = [], set()
    for r in data.get("rules", []):
        if r["rule_id"] in seen:
            issues.append("duplicate_rule_id")
        seen.add(r["rule_id"])
        if any(is_evaluator(i) for i in r["evidence_ids"]):
            issues.append("evaluator_as_personal_evidence")
        if r["verification_status"] == "source_verified" and not r["provenance"]["original_anchor_verified"]:
            issues.append("unverified_original_anchor")
        if not r["confidence_basis"] or not r["applicable_context"].get("scope"):
            issues.append("missing_scope_or_basis")
    return issues
