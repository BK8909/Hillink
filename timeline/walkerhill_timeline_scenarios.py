"""docs/walkerhill-guest-state-machine.md §9.4 / §9.5 의 예시 타임라인.

실행하면 두 가지를 보여준다.
  1. 초안 타임라인이 온달 L.O. 초과로 FAIL 하는 것
  2. 수정안이 I1~I6 전부 PASS 하는 것
그리고 §9.5 의 대표 깨짐 패턴들이 실제로 잡히는지 확인한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from walkerhill_timeline_validator import (
    TimelineSegment,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)

DAY = datetime(2026, 9, 21)
NEXT = DAY + timedelta(days=1)


def at(hour: int, minute: int, next_day: bool = False) -> datetime:
    base = NEXT if next_day else DAY
    return base.replace(hour=hour, minute=minute)


def draft_timeline() -> list[TimelineSegment]:
    """§9.4 초안 — 해피아워를 끝까지 쓰고 온달로 이동한다."""
    return [
        TimelineSegment("AT_FRONT_DESK", "GRAND_FRONT_DESK", at(15, 15), at(15, 18)),
        TimelineSegment("IN_CHECKIN_QUEUE", "GRAND_FRONT_DESK", at(15, 18), at(15, 31)),
        TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK", at(15, 31), at(15, 34)),
        TimelineSegment("IN_ROOM", "GRAND_ROOM", at(15, 42), at(17, 20)),
        TimelineSegment(
            "HAPPY_HOUR_ACTIVE", "GRAND_CLUB_LOUNGE", at(17, 30), at(19, 30),
            machine="M7_Outlet", venue="GRAND_CLUB_LOUNGE",
        ),
        TimelineSegment("SEATED", "ONDAL", at(19, 42), at(19, 45), machine="M7_Outlet", venue="ONDAL"),
        TimelineSegment(
            "COURSE_IN_PROGRESS", "ONDAL", at(19, 45), at(21, 45),
            machine="M7_Outlet", venue="ONDAL",
        ),
    ]


def corrected_timeline() -> list[TimelineSegment]:
    """§9.4 수정안 — 해피아워를 55분만 쓰고 온달을 18:40에 시작한다."""
    return [
        TimelineSegment("AT_FRONT_DESK", "GRAND_FRONT_DESK", at(15, 15), at(15, 18)),
        TimelineSegment("IN_CHECKIN_QUEUE", "GRAND_FRONT_DESK", at(15, 18), at(15, 31)),
        TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK", at(15, 31), at(15, 34)),
        TimelineSegment("IN_ROOM", "GRAND_ROOM", at(15, 42), at(17, 24)),
        TimelineSegment(
            "HAPPY_HOUR_ACTIVE", "GRAND_CLUB_LOUNGE", at(17, 30), at(18, 25),
            machine="M7_Outlet", venue="GRAND_CLUB_LOUNGE",
        ),
        TimelineSegment("SEATED", "ONDAL", at(18, 37), at(18, 40), machine="M7_Outlet", venue="ONDAL"),
        TimelineSegment(
            "COURSE_IN_PROGRESS", "ONDAL", at(18, 40), at(20, 40),
            machine="M7_Outlet", venue="ONDAL",
        ),
        TimelineSegment("TAB_OPEN", "LUX_BAR", at(20, 52), at(22, 32), machine="M7_Outlet", venue="LUX_BAR"),
        TimelineSegment("IN_ROOM", "GRAND_ROOM", at(22, 36), at(7, 30) + timedelta(days=1)),
        TimelineSegment(
            "TIME_LIMIT_ACTIVE", "THE_BUFFET", at(8, 30, True), at(10, 0, True),
            machine="M7_Outlet", venue="THE_BUFFET",
        ),
        TimelineSegment("IN_ROOM", "GRAND_ROOM", at(10, 24, True), at(10, 50, True)),
        TimelineSegment("CHECKED_OUT_SETTLED", "GRAND_FRONT_DESK", at(10, 54, True), at(11, 0, True)),
    ]


def buffet_slot_mismatch() -> list[TimelineSegment]:
    """§9.5 — 뷔페는 자유 착석이 아니라 1부/2부 고정 슬롯이다."""
    return [
        TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK", at(15, 31), at(15, 34)),
        TimelineSegment("IN_ROOM", "GRAND_ROOM", at(15, 42), at(7, 30) + timedelta(days=1)),
        TimelineSegment(
            "TIME_LIMIT_ACTIVE", "THE_BUFFET", at(8, 0, True), at(9, 40, True),
            machine="M7_Outlet", venue="THE_BUFFET",
        ),
    ]


def douglas_shuttle_omitted() -> list[TimelineSegment]:
    """§9.5 — 더글라스는 차량 진입 불가. 셔틀 호출 대기를 빼면 순간이동이 된다."""
    return [
        TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK", at(15, 31), at(15, 34)),
        TimelineSegment("IN_LOUNGE", "DOUGLAS_LOUNGE", at(15, 40), at(16, 40)),
    ]


def double_booked() -> list[TimelineSegment]:
    """§9.5 — 두 업장에 동시 착석. 비투숙 고객이라 StayDay 검사는 끈다."""
    return [
        TimelineSegment("SEATED", "ONDAL", at(12, 30), at(12, 35), machine="M7_Outlet", venue="ONDAL"),
        TimelineSegment("DINING", "ONDAL", at(12, 35), at(14, 0), machine="M7_Outlet", venue="ONDAL"),
        TimelineSegment(
            "TIME_LIMIT_ACTIVE", "THE_BUFFET", at(13, 30), at(15, 30),
            machine="M7_Outlet", venue="THE_BUFFET",
        ),
    ]


def report_last_bus() -> str:
    """§9.5 막차 절벽 — 저녁 식사 후 공항행 6705 탑승이 가능한지."""
    from walkerhill_timeline_validator import WALKERHILL_EXTERNAL_LEGS

    leg = WALKERHILL_EXTERNAL_LEGS[("HOTEL_GATE", "ICN_T1")]
    dinner_end = at(20, 40)
    feasible = dinner_end.time() <= leg.last_departure
    verdict = "탑승 가능" if feasible else "LAST_BUS_MISSED → 리무진·택시 분기 필요"
    return (
        f"  저녁 종료 {dinner_end:%H:%M} / 공항행 막차 {leg.last_departure:%H:%M} "
        f"({leg.source.value}) → {verdict}"
    )


# (제목, 타임라인 생성기, StayDay 검사 여부) — 비투숙 고객은 StayDay가 없다.
SCENARIOS = [
    ("§9.4 초안 (온달 L.O. 초과 예상)", draft_timeline, True),
    ("§9.4 수정안", corrected_timeline, True),
    ("§9.5 뷔페 슬롯 불일치", buffet_slot_mismatch, True),
    ("§9.5 더글라스 셔틀 누락", douglas_shuttle_omitted, True),
    ("§9.5 동시 착석 (비투숙 고객)", double_booked, False),
]


def main() -> None:
    for title, build, enforce_stay_day in SCENARIOS:
        print(f"\n=== {title} ===")
        print(validate_walkerhill_timeline(build(), enforce_stay_day=enforce_stay_day).render())

    print("\n=== §9.5 막차 절벽 ===")
    print(report_last_bus())

    print("\n=== 이동 시간 샘플 (§8.3 / §8.4) ===")
    samples = [
        ("GWANGNARU_STN", "HOTEL_GATE", at(8, 30)),
        ("GANGBYEON_STN", "HOTEL_GATE", at(14, 0)),
        ("ICN_T1", "HOTEL_GATE", at(9, 0)),
        ("GRAND_LOBBY", "GRAND_ROOM", at(16, 0)),
        ("GRAND_LOBBY", "GRAND_ROOM", at(22, 0)),
        ("GRAND_LOBBY", "DOUGLAS_LOBBY", at(19, 0)),
    ]
    for origin, destination, when in samples:
        minutes = walkerhill_travel_time_min(origin, destination, when)
        peak = " (피크 ×2)" if minutes and origin in ("GRAND_LOBBY",) and when.hour in (16, 8) else ""
        print(f"  {when:%H:%M}  {origin:>14} → {destination:<16} {minutes:5.1f}분{peak}")


if __name__ == "__main__":
    main()
