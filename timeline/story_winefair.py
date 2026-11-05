"""
와인페어 손님 이야기 — 4판 조건으로 10/10 (토) 를 그대로 돌리면서, 대표 손님 몇 명의 하루를 그대로 받아 적는다 (10/11 경수)

  python3 story_winefair.py                 # 10/10 · 기본 가정 · 손님 넷의 타임라인 + 지출 줄

고르는 손님 (행사에 간 팀 중 처음 걸리는 하나씩)
  A. 행사가 새로 불러온 외부 손님 · 20대 · 커플
  B. 와인페어 든 패키지로 묵는 아이 동반 가족 (투숙 · 무료 입장 · 1부 어린이 무료)
  C. 50세 이상 투숙객 (아이 없음) — 행사 들렀다가 저녁은 호텔 한식 · 중식 · 일식 · 뷔페
  D. 원래 오던 비투숙 손님이 행사에도 들른 경우
수정한 모델 없음 — scenario_winefair.install() 위에 run_agent 만 감싸서 지나가는 손님을 받아 적는다.
"""
from __future__ import annotations

import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario_winefair as W
import agent_v4, revenue, generate as G

DATE = "2026-10-10"
caught: dict[str, tuple] = {}
spent: dict[str, list] = {}

PICK = {
    "A": lambda p: (not p.is_guest) and "와인페어 #" in p.name and p.age_band == "20~29세" and p.purpose == "커플·기념일",
    "B": lambda p: p.is_guest and p.has_child_under_13 and p.package and ("Wine" in p.package or "캠크닉" in p.package or "불멍" in p.package) and "FOREST_PARK" in p.booked,
    "C": lambda p: p.is_guest and p.age_band == "50세 이상" and not p.has_child_under_13 and "FOREST_PARK" in p.booked,
    "D": lambda p: (not p.is_guest) and "와인페어 #" not in p.name and not p.name.endswith("W"),
}


def main():
    W.install()
    base_run = agent_v4.run_agent

    def run(p, start, *a, **kw):
        segs, traces = base_run(p, start, *a, **kw)
        went = any(t.chosen == "와인페어" for t in traces)
        dinner = any(t.chosen in ("금룡", "명월관", "온달", "모에기", "더뷔페 석식") for t in traces)
        for k, f in PICK.items():
            if k not in caught and went and f(p) and (k != "C" or dinner):
                caught[k] = (p, start, segs, traces)
        return segs, traces
    agent_v4.run_agent = run

    base_lines = revenue.spend_lines

    def lines(m, *a, **kw):
        out = base_lines(m, *a, **kw)
        for k, v in caught.items():
            if v[0] is m.PERSONA and k not in spent:
                spent[k] = out
        return out
    revenue.spend_lines = lines

    sys.argv = [sys.argv[0], "--date", DATE]
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        G.main()

    for k in "ABCD":
        if k not in caught:
            print(f"\n[{k}] 못 찾음"); continue
        p, start, segs, traces = caught[k]
        print(f"\n[{k}] {p.name} · {p.sex} {p.age_band} · {p.purpose} · {p.party_size}인{' · 아동 동반' if p.has_child_under_13 else ''}"
              f" · {'투숙 ' + p.property + ' ' + str(p.nights) + '박' if p.is_guest else '비투숙'}"
              f"{' · ' + p.package if p.package else ''} · 예약 {p.booked} · 포함 {p.included_meals} · 도착 {start:%m/%d %H:%M}")
        for s in segs:
            print(f"   {s.t_in:%a %H:%M}–{s.t_out:%H:%M}  {s.state:20s} {s.location}")
        for t in traces:
            why = " · ".join(t.why[:3])
            print(f"      ▸ {t.start:%H:%M} {t.chosen:12s} ({t.feasible}/{t.considered}) {why}")
        if k in spent:
            tot = 0
            for ln in spent[k]:
                tot += ln["krw"]
                print(f"   ₩ {ln['t']:9s} {ln['l3']:10s} {str(ln['product'])[:28]:28s} {ln['krw']:>10,.0f}  {ln['note']}")
            print(f"   ₩ 합 {tot:,.0f} (결제액)")


if __name__ == "__main__":
    main()
