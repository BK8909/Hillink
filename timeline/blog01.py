"""
후기 한 편을 검증기에 넣어 본다.

대상: blog01 후기 — 그랜드 2박 (URL 은 노션 대응표에만)
      [그랜드 워커힐] 체크인, 디럭스 트윈, 리버뷰 저층 · 2박 3일 · 성인2 + 아이2

실행:  cd timeline && python3 blog01_yisohee.py

원문에서 시각이 명시된 곳은 "3시대 조금 일찍 체크인" 한 군데뿐이다.
나머지 시각은 순서를 유지하기 위한 자리표시값이며 미상이다.
"""

from datetime import datetime

from walkerhill_timeline_validator import (
    TimelineSegment,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)

D1 = "2025-01-31"  # 금 — 원문에 날짜 없음. 금·토·일 2박이라는 서술만 있음
D2 = "2025-02-01"  # 토


def t(day: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}")


def seg(state, location, day, a, b, machine="M2_Stay", venue=None, day_out=None):
    return TimelineSegment(
        state=state,
        location=location,
        t_in=t(day, a),
        t_out=t(day_out or day, b),
        machine=machine,
        venue=venue,
    )


# ---------------------------------------------------------------------------
# 실행 A — 검증기가 아는 지점만 사용한 축약판
#           발렛 · 수영장 · 라이브러리 · 사진부스를 뺀 것
# ---------------------------------------------------------------------------

RUN_A = [
    seg("ARRIVED_ON_PROPERTY", "GRAND_LOBBY",     D1, "14:10", "14:15"),
    seg("LUGGAGE_STORED",      "GRAND_LOBBY",     D1, "14:15", "14:20"),
    seg("IN_CHECKIN_QUEUE",    "GRAND_LOBBY",     D1, "14:20", "14:55"),
    seg("AT_FRONT_DESK",       "GRAND_FRONT_DESK",D1, "14:55", "15:05"),
    seg("KEY_ISSUED",          "GRAND_FRONT_DESK",D1, "15:08", "15:10"),
    seg("IN_ROOM",             "GRAND_ROOM",      D1, "15:18", "18:10"),
    # 2박 3일이므로 둘째 날이 이어진다
    seg("IN_ROOM",             "GRAND_ROOM",      D1, "18:10", "08:00", day_out=D2),
    seg("TIME_LIMIT_ACTIVE",   "THE_BUFFET",      D2, "08:30", "10:00",
        machine="M7_Outlet", venue="THE_BUFFET"),
]

# ---------------------------------------------------------------------------
# 실행 B — 체크인 대기 중 실제로 한 행동을 넣은 것
#           로비 공연을 보고 2층 라이브러리에 갔다가 비스타 쪽까지 걸어갔다
# ---------------------------------------------------------------------------

RUN_B = RUN_A[:3] + [
    seg("IN_LOUNGE", "GRAND_LOBBY",  D1, "14:22", "14:32", machine="M7_Outlet"),
    seg("SEATED",    "VISTA_LOBBY",  D1, "14:40", "14:50", machine="M7_Outlet"),
    # 비스타에서 그랜드 프런트까지 9분. 자리표시값을 그만큼 뒤로 민다.
    seg("AT_FRONT_DESK", "GRAND_FRONT_DESK", D1, "14:59", "15:05"),
] + RUN_A[4:]

# ---------------------------------------------------------------------------
# 실행 C — 후기 그대로. 검증기가 모르는 지점이 들어간다
# ---------------------------------------------------------------------------

RUN_C = [
    seg("SELF_DRIVE_ARRIVING", "HOTEL_GATE",  D1, "14:00", "14:05", machine="M5_Transport"),
    seg("VALET_RECEIVED",      "VALET_DESK",  D1, "14:06", "14:10", machine="M5_Transport"),
    seg("ARRIVED_ON_PROPERTY", "GRAND_LOBBY", D1, "14:12", "14:15"),
    seg("LUGGAGE_STORED",      "GRAND_LOBBY", D1, "14:15", "14:20"),
    seg("IN_CHECKIN_QUEUE",    "GRAND_LOBBY", D1, "14:20", "14:55"),
    seg("IN_LOUNGE",           "GRAND_LOBBY", D1, "14:22", "14:32", machine="M7_Outlet"),
    seg("SEATED",              "VISTA_LOBBY", D1, "14:40", "14:50", machine="M7_Outlet"),
    seg("AT_FRONT_DESK",       "GRAND_FRONT_DESK", D1, "14:59", "15:05"),
    seg("KEY_ISSUED",          "GRAND_FRONT_DESK", D1, "15:08", "15:10"),
    seg("IN_ROOM",             "GRAND_ROOM",  D1, "15:18", "16:30"),
    seg("ENTERED",             "GRAND_POOL",        D1, "16:55", "18:00", machine="M7_Outlet"),
    seg("IN_ROOM",             "GRAND_ROOM",  D1, "18:15", "08:00", day_out=D2),
    seg("TIME_LIMIT_ACTIVE",   "THE_BUFFET",  D2, "08:30", "10:00",
        machine="M7_Outlet", venue="THE_BUFFET"),
    seg("SEATED",              "PIZZA_HILL",  D2, "18:00", "18:05",
        machine="M7_Outlet", venue="PIZZA_HILL"),
    seg("DINING",              "PIZZA_HILL",  D2, "18:05", "20:00",
        machine="M7_Outlet", venue="PIZZA_HILL"),
]

# ---------------------------------------------------------------------------

def run(title, segments, enforce_stay_day=True, nights=2):
    print("=" * 62)
    print(title)
    print("=" * 62)
    try:
        report = validate_walkerhill_timeline(
            segments, enforce_stay_day=enforce_stay_day, nights=nights
        )
        print(report.render())
    except Exception as e:
        print(f"검증 불가 — {type(e).__name__}: {e}")
        print("위반 목록이 나오는 게 아니라 검증 자체가 멈춘다.")
    print()


if __name__ == "__main__":
    run("A · 아는 지점만 · 2박", RUN_A)
    run("B · 체크인 대기 중 이동 포함", RUN_B)
    run("C · 후기 그대로 (발렛 · 수영장 포함)", RUN_C)

    print("=" * 62)
    print("이동 시간 조회 — 후기에 나오는 구간")
    print("=" * 62)
    for a, b, when in [
        ("GRAND_FRONT_DESK", "GRAND_ROOM", t(D1, "15:10")),
        ("GRAND_LOBBY", "VISTA_LOBBY", t(D1, "14:35")),
        ("GRAND_LOBBY", "ANNEX", t(D1, "18:00")),
        ("GRAND_ROOM", "THE_BUFFET", t(D2, "08:00")),
    ]:
        try:
            print(f"  {when:%H:%M}  {a} -> {b}  {walkerhill_travel_time_min(a, b, when):.1f}분")
        except Exception as e:
            print(f"  {when:%H:%M}  {a} -> {b}  오류: {e}")

    print()
    print("검증기가 모르는 지점 확인")
    for name in ["PIZZA_HILL", "MYONGWOLGWAN", "MOEGI", "GRAND_POOL", "VALET_DESK",
                 "FITNESS", "WELLNESS_SAUNA", "SKYARD"]:
        try:
            walkerhill_travel_time_min("GRAND_LOBBY", name, t(D1, "18:00"))
            print(f"  {name}  있음")
        except Exception:
            print(f"  {name}  없음")
