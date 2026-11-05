"""Assemble old raw answers and a human worksheet; does not submit a verdict."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from persona_sheet import load_cards
from .experiment import write_new
from .rules import digest

HERE = Path(__file__).resolve().parent
DIMENSIONS = ("structural_citations", "personal_fact_accuracy", "behavior_plausibility",
              "past_goal_transfer", "new_inference_scope", "alternative_reasoning")
NOTES = {
    "blog59_off": {
        "structural_citations": "과거 목적 r006:package를 A층에 인용. 초기 패킷의 source layer 누락으로 검사기는 추론으로 취급했다. 현재 A카드에서는 observed이므로 이것만으로 거짓 기억이라고 판정할 수 없다.",
        "personal_fact_accuracy": "야외 이용·과거 목적·창가/객실 조망이 카드에 있다. 리버파크 만족/재방문 선호는 카드에 없다. 원문 직접 정확성은 미확정이다.",
        "behavior_plausibility": "야외 물놀이를 실내로 대체하는 것은 가능한 가설이다. 일행의 실제 희망·안전·체류 동선은 검증되지 않았다.",
        "past_goal_transfer": "CTX-GOAL-CONTINUITY가 개인 추론의 주요 전제다. 이 입력에서의 선택을 목적 미상 신규 방문에 대한 반응으로 일반화할 수 없다.",
        "new_inference_scope": "야외 목적→실내 물놀이는 새 추론이다. 새 기억으로 말하지 않고 낮은 확신을 표시했으나 실제 대체 의향 근거는 없다.",
        "alternative_reasoning": "휴식 필요가 제시되지 않았다는 이유로 REST를 밀었지만 수영 의사도 관측되지 않았다. 두 선택지에 같은 불확실성 기준을 썼는지 사람이 판단해야 한다.",
        "method_disagreement": "REST는 4개 동률의 코드 타이 선택이며 우월한 휴식 근거가 아니다. VISTA_POOL은 그 frontier 안에 있다. 메서드는 구체적 outdoor_water 목적을 indoor_water로 전이하지 않으므로 제한적 대체 추론을 놓칠 수 있다. 모델 추론의 타당성 역시 별도 검수한다."
    },
    "blog59_on": {
        "structural_citations": "과거 이용 r006:riverpark는 A, 과거 목적+CTX는 B로 분리되어 구조 통과했다. 인용의 의미 함의까지 확인된 것은 아니다.",
        "personal_fact_accuracy": "야외 이용과 과거 목적은 카드 요약에 있으나 야외 시설 만족 평가나 재방문 의사는 없다.",
        "behavior_plausibility": "목적 지속·전원 입장·맑은 날이라는 조건에서 가능한 선택이다. 실제 과거 고객의 재방문 확률은 알 수 없다.",
        "past_goal_transfer": "응답이 스스로 목적 지속 가정을 primary라고 인용한다. 가정을 준 효과와 개인 경험의 자발적 적용을 분리할 새 실행이 필요하다.",
        "new_inference_scope": "과거 목적을 현재에 이전하되 고정 취향이 아니라고 한정했다. 목적 지속이 없을 때도 같은 선택을 할지는 미측정이다.",
        "alternative_reasoning": "VISTA_POOL과 WALK/REST를 비교했다. 어린이 나이·실제 총액 미상을 보존한다. 90분의 준비 시간 및 모든 동행의 의사를 확인한 것은 아니다.",
        "method_disagreement": "메서드와 선택이 같지만 같은 목적 가정과 지지표를 공유했다. LLM이 독자적으로 동일 결론에 도달했다는 증거가 아니다."
    },
    "blog25_off": {
        "structural_citations": "r003:stay의 가족·수영 목적은 카드에서 human_inference인데 A층에도 인용했다. 수영장 이용 r003:pool와 분리해서 판정해야 한다.",
        "personal_fact_accuracy": "실내 수영 이용·조식 조망은 카드에 있다. 과거 목적 요약과 정확한 동행 인원은 추론 수준을 보존해야 한다.",
        "behavior_plausibility": "실내 수영장 선택은 개연성 있는 가설이나 과거 이용만으로 재이용 선호를 입증하지 않는다.",
        "past_goal_transfer": "사람이 추론한 과거 목적에 이번에도 적용한다는 가정이 추가됐다. 추론 위의 추론이라는 점을 보여줘야 한다.",
        "new_inference_scope": "조식 조망을 활동 전반으로 일반화하지 않은 부분은 범위 통제다. 이번 가족 전체의 물놀이 희망은 미상이다.",
        "alternative_reasoning": "기회비용/요금 총액을 미상으로 두었다. 피로 정보 없음이 휴식을 거절하는 충분한 근거인지 별도 검수한다.",
        "method_disagreement": "같은 GRAND_POOL 선택은 목적 지속 가정과 표의 공유로 설명될 수 있다. 목적 지속을 끈 메서드에서도 코드 타이로 같은 결과가 나올 수 있어 선택 코드만으로 개인화 효과를 판단하면 안 된다."
    }
}


def make_review(cards=None):
    cards = load_cards() if cards is None else cards
    old = HERE / "method_v1_artifacts"
    snapshot = json.loads((old / "research/engine_study_v1.json").read_text(encoding="utf-8"))
    typed = json.loads((old / "typed_rules_v2.json").read_text(encoding="utf-8"))
    attempts = []
    for path in sorted((old / "session_responses").glob("*.json")):
        response = json.loads(path.read_text(encoding="utf-8"))
        index = next(i for i, c in enumerate(snapshot["cases"]) if c["input_sha256"] == response["input_sha256"])
        case, frozen = snapshot["cases"][index], snapshot["results"][index]["prechoice"]
        agent = case["customer_id"]
        excluded = {r["rule_id"]: r["observed_statement"] for r in typed["rules"]
                    if r["agent_id"] == agent and r["verification_status"] == "excluded_evaluator_only"}
        leaked = [{"rule_id": r["rule_id"], "label": excluded[r["rule_id"]]}
                  for r in case["payload"]["rules"] if r["rule_id"] in excluded]
        card = cards[agent]["a_card"]
        attempts.append({"response_id": path.stem, "customer_id": agent, "environment": case["environment"],
            "original_input_sha256": response["input_sha256"], "raw_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "raw_response_sha256": digest(response), "raw_response": deepcopy(response),
            "card_facts_for_audit_only": {k: deepcopy(card[k]) for k in ("purpose", "explicit_preferences", "observed_events")},
            "assumptions_received": deepcopy(case["payload"]["context"]["assumptions"]),
            "prechoice_received": True, "reference_selected": frozen["selected"], "reference_frontier": frozen["frontier"],
            "input_integrity_findings": {"evaluator_only_labels_received": leaked, "effect_on_response": "not_identified",
                                         "source_layer_metadata_missing": any("layer" not in r["source_verification"] for r in case["payload"]["rules"])},
            "AI_review_notes_not_verdicts": NOTES[path.stem],
            "human_review": {"reviewer": None, "completed": False, "result": None,
                             "dimensions": {d: {"judgment": None, "reason": None} for d in DIMENSIONS}},
            "demo_approved": False})
    return {"version": "representative_human_review_packet_v1", "intended_reviewer": "경수",
            "source_access": "approved_cards_only_no_new_original_anchor_verification", "new_sessions": 0,
            "human_reviews_completed": 0, "demo_approved": 0, "attempts": attempts,
            "judgment_options": ["수용", "조건부", "부적절", "판단불가"],
            "critical_question": "리버파크 재선택의 근거가 실제 긍정 평가인가, 경험에서의 새로운 추론인가, 입력된 목적 지속 가정인가?"}


def markdown(review):
    by_id = {a["response_id"]: a for a in review["attempts"]}
    off, on = by_id["blog59_off"], by_id["blog59_on"]
    rows = ["# 대표 응답 사람 검수 패킷 — 경수 검토용", "",
            "작성: Codex. 아래 해석은 AI의 검수 제안이지 사람 판정이 아니다. 원문 재검증 0건, 사람 검수 완료 0건, 시연 승인 0건. 기존 응답은 수정하지 않았다.", "",
            "이 문서는 평가자 전용이다. 독립 행동 생성 세션에는 전달하지 않는다. 카드의 human_checked는 과거 카드 필드의 상태이며 이번 응답 검수 완료 표시가 아니다.", "",
            "## 핵심 질문", "", review["critical_question"], "",
            "현재 카드에는 야외 이용과 과거 패키지 목적은 있으나 **리버파크 만족·재방문 희망의 직접 평가가 없다.** 원문에도 없다고 단정한 것은 아니다.", "",
            "## 카드 근거 대조 — 원문 검증과 구분", "",
            "| 근거 ID | 현재 카드에 있는 내용 | 층·범위 | 아직 뒷받침하지 않는 주장 |",
            "|---|---|---|---|",
            "| r006:riverpark | 과거 리버파크 이용 | 관측 행동 요약, 원문 앵커 미검증 | 만족·재방문 선호·실내 대체 의향 |",
            "| r006:package | 여름 가족 휴가·리버파크·조식이라는 과거 목적 | 카드 observed/human_checked, 이번 의사 아님 | 현재도 물놀이하고 싶다는 사실 |",
            "| r006:window_request / r006:room | 조식 창가 / 한강 조망 객실 선호 | 해당 좌석·객실 범위 | 야외 수영장이나 스카이야드 선호 |",
            "| r003:pool | 그랜드 실내 수영장 이용 | 관측 행동 요약, 원문 앵커 미검증 | 재이용 선호·이번 가족 전체의 희망 |",
            "| r003:stay | 가족 호텔 숙박·실내 수영장·조식 목적 | 사람 추론 | 직접 표현한 과거 목적이나 현재 의사 |",
            "| r003:view | 조식에서 조망을 즐김 | 조식 좌석 범위 | 모든 조망 활동·야외 행사 선호 |", "",
            "## blog59 나란히 검토", "", "| 항목 | 야외 수영장 없음 | 야외 수영장 있음 |", "|---|---|---|"]
    for title, left, right in (
        ("선택", off["raw_response"]["output"]["choice"], on["raw_response"]["output"]["choice"]),
        ("과거 사실 요약", "리버파크 이용·여름 가족 휴가 목적. 원문 앵커 미검증", "왼쪽과 같은 고객 근거"),
        ("이번 목적", "과거 목적을 이번에도 참고한다는 가정이 주어짐", "같은 가정이 주어짐"),
        ("새 추론", "야외 물놀이 목적을 실내 물놀이로 대체", "과거 야외 목적이 이번에도 적용된다고 추론"),
        ("주요 전제", "goal_continuity, 전원 입장, 맑음, 요금 총액 미상", "동일 전제 + RIVERPARK 선택지 추가"),
        ("포기한 대안", "WALK / SKYARD / REST", "VISTA_POOL / WALK / REST"),
        ("메서드 비교", "REST는 4개 동률 중 타이 선택. VISTA_POOL도 frontier 안", "같은 목적 가정 아래 RIVERPARK 단독 frontier"),
        ("구조 검사 해석", "초기 출처 층 누락으로 격리. 카드상 과거 목적은 observed", "구조 통과, 원문 사실·행동 개연성 검증과 별개"),
    ):
        rows.append(f"| {title} | {left} | {right} |")
    rows += ["", "REST에 강한 개인적 우위가 있어서 메서드가 고른 것은 아니다. 반대로 모델이 실내 수영장을 골랐다고 올바른 대체 의향이 관측된 것도 아니다. 어느 추론을 허용할지와 그 확신 수준을 사람이 비교해야 한다.", ""]
    for a in review["attempts"]:
        out = a["raw_response"]["output"]
        rows += [f"## {a['response_id']} — 원 응답과 검수 항목", "", f"입력 SHA: `{a['original_input_sha256']}`", "",
                 f"원 파일 SHA: `{a['raw_file_sha256']}`", "", f"선택: {out['choice']} / 비용: 미상 / 응답 확신: {out['confidence']}", ""]
        for layer, label in (("personal_observation", "A 개인 관측"), ("personal_inference", "B 개인 추론"),
                             ("population_prior", "C 통계"), ("situational_judgment", "D 현재 상황")):
            reason = out["basis"][layer]
            rows += [f"### {label} — 원 응답", "", reason["text"] or "사용하지 않음", "",
                     f"근거: {', '.join(reason['ids']) or '없음'} / 기여 자기보고: {reason['contribution']}", ""]
        rows += ["### 포기한 대안 — 원 응답", ""]
        rows += [f"- {x['option_code']}: {x['why_not']}" for x in out["alternatives"]]
        rows += ["", "### 불확실성 — 원 응답", ""]
        rows += [f"- {x}" for x in out["uncertainties"]]
        rows += ["", "### 검수 메모 — Codex 제안, 판정 아님", "", "| 축 | 확인할 내용 | 경수 판정·이유 |", "|---|---|---|"]
        rows += [f"| {d} | {a['AI_review_notes_not_verdicts'][d]} | 미작성 |" for d in DIMENSIONS]
        rows += ["", a["AI_review_notes_not_verdicts"]["method_disagreement"], ""]
        labels = a["input_integrity_findings"]["evaluator_only_labels_received"]
        if labels:
            rows += ["입력 무결성 경고: 초기 패킷에 평가자 전용 축약 라벨이 포함됐다: " + ", ".join(x["label"] for x in labels) +
                     ". 응답에 영향을 미쳤는지는 알 수 없다. 무오염 독립 입력이라고 단정하지 않으며 최신 패킷에서는 제외했다.", ""]
    rows += ["## 경수가 남길 판단", "",
             "각 축에 수용/조건부/부적절/판단불가와 이유를 적는다. 특히 목적 지속 가정이 없는 신규 방문에서도 추론이 설득력 있는지, REST와 물놀이에 같은 불확실성 기준을 적용했는지 판단한다.", "",
             "수정된 이유를 원 응답에 덮어쓰지 않는다. 판정은 응답/입력 해시와 별도로 저장하고, 시연 승인 여부도 명시적으로 결정한다. 답변을 직접 확인하기 전에는 사람 검수 완료·합의·Gold로 표시하지 않는다.", ""]
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path, required=True)
    args = ap.parse_args()
    review = make_review()
    write_new(args.write / "human_review_tasks.json", review)
    # Derived worksheet only, never an existing customer or experiment file.
    path = args.write / "HUMAN_REVIEW_PACKET.md"
    content = markdown(review)
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise FileExistsError(path)
    if not path.exists():
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    print(json.dumps({"old_answers_presented": len(review["attempts"]), "new_sessions": 0, "human_reviews_completed": 0}))


if __name__ == "__main__":
    main()
