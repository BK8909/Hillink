"""원문 관찰과 실행용 가정을 분리한 blog06. 실행: python timeline/blog06.py.
0건은 아래 가정으로 만든 상태 열의 정합성이다. 미상 시각의 실측 검증이 아니다.
"""
from datetime import datetime
from walkerhill_timeline_validator import TimelineSegment, validate_walkerhill_timeline

SOURCE_URL = "blog06 후기 (URL 은 노션 대응표에만)"
SOURCE_CHECKED = "2026-09-23"
# 게시일을 방문일로 사용하지 않는다. 날짜는 실행용 좌표일 뿐이다.
VISIT_DATE = None
D1, D2 = "2000-01-01", "2000-01-02"
NIGHTS = 1  # 본문의 당일/다음 날 퇴실 흐름을 이번 사례 범위로 해석.
FACTS = {
    "arrival": "15시 체크인 시간에 맞춰 도착했다고 서술",
    "room": "체크인 후 객실에서 짐 정리와 휴식",
    "theatre": "16시 도슨트 예약; 17:30 종료 후 추가 관람·아트샵, 약 17:50",
    "snack": "남편이 배고파 전시장 옆 CU에서 간식",
    "transport": "추위와 이동 부담 때문에 셔틀 선택",
    "pizza": "예약 없이 방문, 앞에 11팀, 예상 60~90분 안내 후 포장 선택",
    "return": "포장 수령 후 셔틀로 객실 복귀",
    "meal": "객실에서 식사·휴식 후 19시 조금 넘어 수영장",
    "pool_end": "수영 후 나온 시각 21:30",
    "next_day": "다음 날 늦잠·시리얼 식사 후 라이브러리, 이후 퇴실",
}
# 리뷰의 예상 대기/셔틀 대기/가격을 실제 체류·이동시간으로 대체하지 않는다.
OBSERVATIONS = {
    "expected_dine_in_wait_min": [60, 90],
    "actual_dine_in_wait_min": None,
    "outbound_shuttle_wait_min": [2, 3],
    "return_shuttle_wait_min": {"less_than": 1},
    "shuttle_ride_min": None,
    "order": ["불고기피자 라지", "연어샐러드"],
    "approx_order_total_krw": 100000,
    "age": None, "room_number": None, "party_count": None,
}
# (state, location, day, in, out, machine, venue, evidence_key, time_basis)
# exact = 본문 명시, approx = 대략, reservation = 예약, assumed = 실행용 가정.
# 모든 종료점/시작점을 별도로 표시하며 체크인 완료·키발급은 전제 모델 가정.
ROWS = [
 ("AT_FRONT_DESK","GRAND_FRONT_DESK",D1,"15:00","15:08","M2_Stay",None,"arrival","in:arrival exact, desk assignment assumed; out:assumed"),
 ("KEY_ISSUED","GRAND_FRONT_DESK",D1,"15:08","15:10","M2_Stay",None,"room","in/out:assumed prerequisite, key receipt not directly stated"),
 ("IN_ROOM","GRAND_ROOM",D1,"15:18","15:30","M2_Stay",None,"room","in/out:assumed"),
 ("BROWSING","CU_THEATRE",D1,"15:50","15:55","M7_Outlet",None,"snack","in/out and placement before show:assumed"),
 ("IN_SESSION","THEATRE_OF_LIGHT",D1,"16:00","17:30","M7_Outlet",None,"theatre","in:reservation, attendance start assumed; out:exact"),
 ("BROWSING","THEATRE_OF_LIGHT",D1,"17:30","17:40","M7_Outlet",None,"theatre","in:exact boundary; out:assumed"),
 ("BROWSING","THEATRE_ART_SHOP",D1,"17:41","17:50","M7_Outlet",None,"theatre","in:assumed; out:approx"),
 ("SHUTTLE_WAITING","HOTEL_GATE",D1,"18:00","18:03","M5_Transport",None,"transport","in/out:assumed; 3min wait within observed range"),
 ("TAKEOUT_ORDERED","PIZZA_HILL",D1,"18:15","18:20","M7_Outlet","PIZZA_HILL","pizza","in/out:assumed"),
 ("HANDED_OVER","PIZZA_HILL",D1,"18:20","18:30","M7_Outlet","PIZZA_HILL","return","in/out:assumed, includes unmeasured packaging"),
 ("IN_ROOM","GRAND_ROOM",D1,"18:50","19:00","M2_Stay",None,"meal","in/out:assumed; room meal, not dine-in at pizza hill"),
 ("ENTERED","GRAND_POOL",D1,"19:15","21:30","M7_Outlet",None,"pool_end","in:assumed representative of after19; out:exact"),
 ("IN_ROOM","GRAND_ROOM",D1,"21:45","09:45","M2_Stay",None,"next_day","in/out and overnight room continuity:assumed"),
 ("IN_LOUNGE","GRAND_LIBRARY",D2,"10:00","10:50","M7_Outlet",None,"next_day","in/out:assumed; IN_LOUNGE represents occupied reading space"),
 ("CHECKED_OUT_SETTLED","GRAND_FRONT_DESK",D2,"10:54","11:00","M2_Stay",None,"next_day","in/out and settlement:assumed, actual checkout time unknown"),
]
def build_timeline():
    result = []
    for state, loc, day, a, b, machine, venue, _, _ in ROWS:
        end_day = D2 if day == D1 and b < a else day
        result.append(TimelineSegment(state,loc,datetime.fromisoformat(f"{day}T{a}"),
            datetime.fromisoformat(f"{end_day}T{b}"),machine=machine,venue=venue))
    return result

# 팀 통합용 계약. 통과 대상 사례만 열거한다.
CASES = [("blog06", build_timeline, True, NIGHTS)]

if __name__ == "__main__":
    report = validate_walkerhill_timeline(build_timeline(), nights=NIGHTS)
    print("blog06 | " + SOURCE_URL)
    print("주의:", "미상 시각은 가정. 0건은 관찰 사실의 완전성·실측 정확성을 보장하지 않음.")
    print(report.render())
    raise SystemExit(0 if report.ok else 1)

