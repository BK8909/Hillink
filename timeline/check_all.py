"""
취합 검증기 한 번에 점검 — 후기 4편 전부 PASS + 회사 시나리오 5개 결과 불변
(10/5 더뷔페 요일 창으로 둘은 이유를 적고 바꿨다 — 아래 [회사 시나리오]).

  cd timeline && python3 check_all.py

이 스크립트가 전부 OK 여야 검증기 수정을 커밋한다.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from walkerhill_timeline_validator import validate_walkerhill_timeline
import walkerhill_timeline_scenarios as SC

ok_all = True


def chk(name: str, got, want) -> None:
    global ok_all
    good = got == want
    ok_all &= good
    print(f"  {'OK  ' if good else '** 틀림 **'} {name:44s} → {got}" + ("" if good else f"  (기대 {want})"))


print("[후기 6편 · 타임라인 10개 — 전부 PASS 여야 한다]")
import blog01, blog02, blog03, blog04, blog05, blog06
cases = [
    ("blog01 A · 아는 지점만 · 2박",   blog01.RUN_A, dict(nights=2)),
    ("blog01 B · 대기 중 이동 · 2박",  blog01.RUN_B, dict(nights=2)),
    ("blog01 C · 후기 그대로 · 2박",   blog01.RUN_C, dict(nights=2)),
    ("blog02 · 더글라스 1박",          blog02.BLOG02_TIMELINE, dict(nights=1)),
    ("blog03 A · 비스타 1박",          blog03.STAY_A, dict(nights=1)),
    ("blog03 B · 그랜드 1박",          blog03.STAY_B, dict(nights=1)),
    ("blog04 A · 리버파크 비투숙",     blog04.VISIT_A, dict(enforce_stay_day=False)),
    ("blog04 B · 클럽스위트 1박",      blog04.VISIT_B, dict(nights=1)),
    ("blog05 · 비스타 1박 · 2025 해피아워", blog05.build_timeline(), dict(nights=1)),
    ("blog06 · 빛의 시어터 · 피자 포장",  blog06.build_timeline(), dict(nights=1)),
]
for name, segs, kw in cases:
    r = validate_walkerhill_timeline(segs, **kw)
    chk(name, "PASS" if r.ok else [f"{v.invariant}" for v in r.violations], "PASS")

print("\n[통과하면 안 되는 것]")
from datetime import datetime
from walkerhill_timeline_validator import TimelineSegment
_key26 = TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK", datetime(2026, 4, 15, 15, 0), datetime(2026, 4, 15, 15, 5))
_hh26 = TimelineSegment("HAPPY_HOUR_ACTIVE", "GRAND_CLUB_LOUNGE", datetime(2026, 4, 15, 18, 0), datetime(2026, 4, 15, 20, 0),
                        machine="M7_Outlet", venue="GRAND_CLUB_LOUNGE")
r = validate_walkerhill_timeline([_key26, _hh26])
chk("2025 해피아워 창(18–20)은 2026 에 안 열린다 → I3", [v.invariant for v in r.violations], ["I3"])
r = validate_walkerhill_timeline(blog02.POOL_OVERLAP_PROBE, nights=1)
got = {v.invariant for v in r.violations}
# 이 프로브는 키 없이 더글라스 라운지에 들어가서 I5 도 같이 난다 — I1·I4 가 들어 있는지만 본다
chk("라운지·수영장 동시 점유 → I1 + I4 포함", {"I1", "I4"} <= got, True)

print("\n[회사 시나리오 5개 — 10/5 더뷔페 요일 창으로 둘이 바뀜 (소연)]")
# 예제 날짜가 2026-09-21(월) · 22(화) 다. 공식표로 화요일 조식은 07:00~10:00 한 번, 월요일 중식은 12:00~14:30.
#   buffet         화 08:00~09:40 조식 → 통과가 맞다 (I3 → 없음)
#   double_booked  월 13:30~15:30 더뷔페 → 중식 마감 14:30 을 넘어 I3 가 더 붙는다
# 예제의 뜻(2부제 날 슬롯 사이 입장 · 동시 착석)은 바로 아래에서 날짜만 옮겨 원래 결과로 확인한다.
expected = {"draft": ["I3"], "corrected": [], "buffet": [], "douglas": ["I2"], "double_booked": ["I1", "I3", "I4"]}
builders = {
    "draft": SC.draft_timeline, "corrected": SC.corrected_timeline,
    "buffet": SC.buffet_slot_mismatch, "douglas": SC.douglas_shuttle_omitted,
    "double_booked": SC.double_booked,
}
for k, build in builders.items():
    r = validate_walkerhill_timeline(build())
    chk(k, sorted({v.invariant for v in r.violations}), expected[k])
from datetime import timedelta
_day0, _next0 = SC.DAY, SC.NEXT
for k, build, shift, want in (("buffet · 하루 당겨 월요일 조식(2부제)", SC.buffet_slot_mismatch, 1, ["I3"]),
                              ("double_booked · 이틀 당겨 토요일", SC.double_booked, 2, ["I1", "I4"])):
    SC.DAY, SC.NEXT = _day0 - timedelta(days=shift), _next0 - timedelta(days=shift)
    try:
        r = validate_walkerhill_timeline(build())
    finally:
        SC.DAY, SC.NEXT = _day0, _next0
    chk(k, sorted({v.invariant for v in r.violations}), want)

print("\n[에이전트 — 정합성만 (일치율은 run_compare.py)]")
from datetime import datetime
import agent_v0, agent_v1, persona_blog01 as P
for mod, name in ((agent_v0, "v0"), (agent_v1, "v1")):
    segs, _ = mod.run_agent(P.PERSONA, datetime(2025, 1, 31, 14, 0), verbose=False)
    r = validate_walkerhill_timeline(segs, nights=P.PERSONA.nights)
    chk(f"agent_{name} · blog01 페르소나", "PASS" if r.ok else [v.invariant for v in r.violations], "PASS")

print("\n" + ("전부 통과" if ok_all else "** 실패 있음 **"))
sys.exit(0 if ok_all else 1)
