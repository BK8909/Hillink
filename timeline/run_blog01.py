"""
1단계 루프 한 바퀴: 후기 1편 페르소나 → 에이전트 → 검증기 → 일치율.

  python3 run_blog01.py          # 요약
  python3 run_blog01.py -v       # 턴별 선택 이유까지
"""

from __future__ import annotations

import sys
from datetime import datetime

import persona_blog01 as P
from agent_v0 import run_agent
from match import evaluate, print_report
from walkerhill_timeline_validator import validate_walkerhill_timeline

D1 = datetime(2025, 1, 31, 14, 0)   # 금요일 14:00 도착. 후기의 유일한 시각 '3시대 조금 일찍 체크인'에 맞춤

def main(verbose: bool = False):
    P.print_persona()
    print()
    segments, traces = run_agent(P.PERSONA, D1, max_turns=40, verbose=verbose)

    res = validate_walkerhill_timeline(segments, enforce_stay_day=True, nights=P.PERSONA.nights)
    print(f"정합성  {'PASS' if res.ok else 'FAIL'} — 위반 {len(res.violations)}건"
          f"  세그먼트 {len(segments)}  총 이동 {res.total_travel_min:.0f}분")
    for v in res.violations:
        print(f"  [{v.invariant} {v.code}] {v.detail}")
    print()

    print("경로")
    for s in sorted(segments, key=lambda s: s.t_in):
        print(f"  {s.t_in:%a %H:%M}–{s.t_out:%H:%M}  {s.state:22s} @ {s.venue or s.location}")
    print()

    r = evaluate(segments, P, title="agent_v0 · blog01 페르소나")
    print_report(r)
    print(r.one_line())
    return r


if __name__ == "__main__":
    main(verbose="-v" in sys.argv)
