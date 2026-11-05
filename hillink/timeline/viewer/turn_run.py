"""핵심 선택 턴 실행기(10/23) — 지도 화면의 '에이전트 한 명 / 여러 명'이 부르는 별도 프로세스.
입력(stdin JSON): {"op": "meta"} | {"op": "view", "personas": [...], "cond": {...}} | {"op": "compare", "personas": [...], "base": {...}, "cond": {...}}
계산은 timeline/experiments/persona_live/operator_choice/operator_world_v1_1/turn_view.py 그대로(턴 후보 · R-BASE 점수 함수). 호텔 전체 시뮬레이션 · 좌석 · 대기 없음."""
import json, sys
from pathlib import Path

PL = Path(__file__).resolve().parent.parent / "experiments" / "persona_live"
sys.path.insert(0, str(PL))
from operator_choice.operator_world_v1_1.turn_view import turn_meta, turn_view, turn_compare, load_all_personas  # noqa: E402


def main():
    q = json.loads(sys.stdin.read() or "{}")
    op = q.get("op", "meta")
    if op == "meta":
        out = turn_meta(q.get("turn", "dinner"), load_all_personas())   # 화면은 확장 에이전트까지(R-BASE 5 + 개발 그룹 + 로컬 전용)
    elif op == "view":
        out = turn_view(q["personas"], q.get("cond") or {}, load_all_personas(), states=q.get("states") or None)
    elif op == "compare":
        # states / base_states: 하루 흐름에서 직전 턴(행사)의 상태를 이어 받는다 — 기준 조건은 기준 조건의 직전 턴 상태로
        cond = q.get("cond") or {}
        base = dict(cond, product_levers=(q.get("base") or {}).get("product_levers") or {}, pricing=(q.get("base") or {}).get("pricing", cond.get("pricing", "historical")))
        P = load_all_personas()
        a = turn_view(q["personas"], base, P, states=q.get("base_states") or None)
        b = turn_view(q["personas"], cond, P, states=q.get("states") or None)
        out = dict(before=a, after=b, compare=turn_compare(a, b))
    else:
        raise SystemExit(f"op 없음: {op}")
    sys.stdout.write(json.dumps(out, ensure_ascii=False, default=list))


if __name__ == "__main__":
    main()
