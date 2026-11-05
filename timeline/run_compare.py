"""
같은 페르소나로 v0 와 v1 을 돌려 정합성과 일치율을 나란히 본다.

  python3 run_compare.py        # 요약
  python3 run_compare.py -v     # v1 턴별 선택 이유까지
"""

from __future__ import annotations

import sys
from datetime import datetime

import persona_blog01 as P
import agent_v0
import agent_v1
from match import evaluate, print_report
from walkerhill_timeline_validator import validate_walkerhill_timeline

D1 = datetime(2025, 1, 31, 14, 0)


def run(mod, title: str, verbose: bool):
    print("=" * 78)
    print(title)
    segments, _ = mod.run_agent(P.PERSONA, D1, verbose=verbose)
    res = validate_walkerhill_timeline(segments, enforce_stay_day=True, nights=P.PERSONA.nights)
    print(f"  정합성 {'PASS' if res.ok else 'FAIL'} — 위반 {len(res.violations)}건"
          f"  세그먼트 {len(segments)}  총 이동 {res.total_travel_min:.0f}분")
    for v in res.violations:
        print(f"    [{v.invariant} {v.code}] {v.detail}")
    print("  경로")
    for s in sorted(segments, key=lambda s: s.t_in):
        print(f"    {s.t_in:%a %H:%M}–{s.t_out:%H:%M}  {s.state:20s} @ {s.venue or s.location}")
    print()
    r = evaluate(segments, P, title=title)
    print_report(r)
    return r


if __name__ == "__main__":
    v = "-v" in sys.argv
    r0 = run(agent_v0, "agent_v0", verbose=False)
    r1 = run(agent_v1, "agent_v1", verbose=v)
    print("=" * 78)
    print(r0.one_line())
    print(r1.one_line())
