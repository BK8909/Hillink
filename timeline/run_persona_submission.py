"""우리 두 페르소나의 가정/실행/부분 평가를 JSON과 Markdown으로 기록.
실행: python timeline/run_persona_submission.py
엔진/검증기/공통 채점기를 수정하지 않는다. 같은 후기 재현 시험이다.
"""
from dataclasses import asdict, replace
from pathlib import Path
import json

import agent_v2
import persona_blog05 as P5
import persona_blog06 as P6
from walkerhill_timeline_validator import validate_walkerhill_timeline

BASE_COMMIT = "c43687d9fdf37eb3e36f7b5d5bb8ede6bb683f44"


def evaluate_partial(segments, module, persona):
    # venue는 검사 키일 수도 있으므로 물리적 장소(location)로 집계한다.
    visited = {s.location for s in segments}
    reachable = agent_v2.reachable(persona)
    observed = set(module.TRUTH_VISITED)
    scorable = observed & reachable
    hit = scorable & visited
    first = {}
    for s in sorted(segments, key=lambda s: s.t_in):
        first.setdefault(s.location, s.t_in)
    orders = []
    for a, b, why in module.TRUTH_ORDER_PAIRS:
        outcome = ("판단 유보: 두 장소 중 미방문 있음" if a not in first or b not in first
                   else "일치" if first[a] < first[b] else "불일치")
        orders.append({"before": a, "after": b, "result": outcome, "evidence": why})
    meals = []
    # 시각/식사 상태가 명시된 경우만 조식 일치 여부를 비교한다.
    for kind, place, evidence in module.TRUTH_MEALS:
        if kind != "조식":
            meals.append({"meal": kind, "result": "판단 유보: 전용 비교 규칙 없음"})
            continue
        found = any(s.location == place and s.state in {"DINING", "TIME_LIMIT_ACTIVE", "IN_LOUNGE"}
                    and 6 <= s.t_in.hour < 11 for s in segments)
        meals.append({"meal": kind, "place": place, "result": "일치" if found else "불일치", "evidence": evidence})
    return {
        "observed_visits": sorted(observed), "scorable_visits": sorted(scorable),
        "matched_visits": sorted(hit), "missed_visits": sorted(scorable - visited),
        "catalog_missing": sorted(observed - reachable),
        "recall": len(hit) / len(scorable) if scorable else None,
        "other_model_visits": sorted(visited - observed),
        "precision": None, "precision_reason": "후기 방문 목록이 완전하지 않으므로 미기록 방문을 오답으로 단정하지 않음",
        "restaurants_exact": None, "restaurant_reason": "확인된 일부 식당 목록만 있어 완전 일치 판단 유보",
        "meal_results": meals or None, "meal_note": "비교 근거 없음" if not meals else "명시된 식사만 비교",
        "order_results": orders,
        "pending_locations": module.TRUTH_LOCATION_PENDING,
        "takeout_result": "판단 유보: 현재 PIZZA_HILL 행동은 매장 식사뿐" if hasattr(module, "TRUTH_TAKEOUT") else None,
    }


def run_case(module, label, overrides=None):
    persona = replace(module.PERSONA, **(overrides or {}))
    # 평가 정답은 실행이 끝난 뒤에만 읽는다.
    segments, traces = agent_v2.run_agent(persona, module.START_AT, verbose=False)
    report = validate_walkerhill_timeline(segments, nights=persona.nights, enforce_stay_day=persona.is_guest)
    return {
        "source": module.SOURCE_ID, "scenario": label, "base_commit": BASE_COMMIT,
        "observed_facts": module.STAY_FACTS,
        "trait_evidence": module.TRAIT_EVIDENCE,
        "assumptions": module.EXPERIMENT_ASSUMPTIONS, "scenario_overrides": overrides or {},
        "start_at": module.START_AT.isoformat(), "start_basis": module.START_AT_BASIS,
        "input_persona": asdict(persona),
        "validation_pass": report.ok, "violations": [asdict(v) for v in report.violations],
        "segment_count": len(segments), "last_event_at": segments[-1].t_out.isoformat() if segments else None,
        "checkout_emitted": any(s.state == "CHECKED_OUT_SETTLED" for s in segments),
        "evaluation": evaluate_partial(segments, module, persona),
        "timeline": [asdict(s) for s in segments], "choices": [asdict(t) for t in traces],
    }


def main():
    cases = [
        run_case(P5, "기본: 확인 성인만·예약 우대 없음"),
        run_case(P5, "가정 변경: 클럽 이용 자격 있음", {"club_access": True}),
        run_case(P5, "가정 변경: 성인 3+아동 1", {"party_size": 4, "has_child_under_13": True}),
        run_case(P6, "기본: 성인 2명·GRAND 가정"),
        run_case(P6, "가정 변경: VISTA 숙박", {"property": "VISTA"}),
        run_case(P6, "가정 변경: DOUGLAS 숙박", {"property": "DOUGLAS"}),
    ]
    out = Path(__file__).resolve().parents[1] / "docs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "persona-results.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# 페르소나 실행 결과", "", f"기준 커밋: `{BASE_COMMIT}`", "",
        "후기 사실과 실험 가정을 분리한 재현 시험이다. 새 상황 예측 성능이나 실제 성격 측정 결과가 아니다.", "",
        "| 후기 | 실험 조건 | 정합성 | 확인 장소 재현 | 기록된 상태 수 |",
        "|---|---|---|---|---|"]
    for c in cases:
        e = c["evaluation"]
        numerator, denominator = len(e["matched_visits"]), len(e["scorable_visits"])
        value = f"{numerator}/{denominator} ({e['recall']:.0%})" if denominator else "판단 유보"
        lines.append(f"| {c['source']} | {c['scenario']} | {'PASS' if c['validation_pass'] else 'FAIL'} | {value} | {c['segment_count']} |")
    lines += ["", "## 해석", "",
        "- 기본 조건과 변형 조건은 모두 가정이다. 유리한 결과만 선택하거나 성향을 결과에 맞춰 변경하지 않았다.",
        "- 정합성 PASS는 발생한 상태 열이 규칙을 만족한다는 뜻이다. 체류 전체나 체크아웃 완료를 보장하지 않는다.",
        "- precision(정밀도)·식당 완전 일치: 후기의 모든 방문이 기록됐다고 알 수 없어 판단 유보.",
        "- blog06 끼니: 식당 내 식사 정답이 없어 판단 유보. 피자 포장과 매장 식사는 서로 다른 행동이다.",
        "- 공통 run_all.py는 빈 끼니 정답에 0%를 표시하고 식당 완전 일치를 비교한다. 이 수치를 확정 성능으로 제출하지 않는다.",
        "- v2는 완료 시각에 도달해도 체크아웃 상태를 자동 생성하지 않는다. 이번 변경에서 엔진 행동은 수정하지 않았다.",
        "- 원문 재열람 차단으로 기존 본문 검수 요약을 사용했다. 미상은 STAY_FACTS/OBSERVED_PERSONA에 그대로 남겼다.", ""]
    for c in (cases[0], cases[3]):
        e = c["evaluation"]
        lines += [f"## {c['source']} 기본 조건 상세", "",
            f"- 일치: {', '.join(e['matched_visits']) or '없음'}",
            f"- 미재현: {', '.join(e['missed_visits']) or '없음'}",
            f"- 에이전트에 없는 확인 장소: {', '.join(e['catalog_missing']) or '없음'}",
            f"- 위치 추가 확인: {e['pending_locations']}",
            f"- 마지막 기록: {c['last_event_at']}; 체크아웃 상태 생성: {c['checkout_emitted']}", ""]
    (out / "persona-results.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    if any(not c["validation_pass"] for c in cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
