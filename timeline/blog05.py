"""정히뽀의 2025-03-09~10 비스타 방문. 사실과 실행 가정을 분리한다.

실행: python timeline/blog_nayul_vista.py
기본 모델과 후기 기반 방문별 조건의 결과를 모두 출력한다.
위반 0건은 가정을 둔 일정의 정합성이며 실제 시각 복원이나 공식 정책 검증이 아니다.
"""
from datetime import date, datetime, time
from walkerhill_timeline_validator import (
    TimelineSegment, VenueWindow, SourceKind, validate_walkerhill_timeline,
)

SOURCE_URL = "blog05 후기 (URL 은 노션 대응표에만)"
SOURCE_CHECKED = "2026-09-23"
SOURCE_AUTHOR = "정히뽀 (blog05)"
PUBLISHED_AT = "2025-04-16 11:38"
VISIT_DATES = ("2025-03-09", "2025-03-10")
NIGHTS = 1
# 한 명(작성자)의 흐름을 표현한다. 3명 모두 끝까지 동일 동선이라는 뜻이 아니다.
OBSERVATIONS = {
    "adults": 3, "children": None, "infants": None,
    "age": None, "room_number": None, "room_type": None,
    "purpose": "호캉스", "total_stay_price_krw": None,
    "happy_hour_extra_adult_krw": 124000,
    "breakfast_extra_adult_krw": 65600,
    "happy_hour_arrival": "18:00 개시 10분 전 (17:50 환산)",
    "happy_hour_seat": "마지막 남은 창가 자리",
    "happy_hour_seat_reason": "창가에 앉으려고 일찍 방문",
    "happy_hour_reported_hours": ["18:00", "20:00"],
    "happy_hour_duration_min_approx": 120,
    "evening_skyard_arrival_approx": "20:30",
    "evening_skyard_duration_min": None,
    "breakfast_slots_reported": [["07:00", "08:20"], ["08:40", "10:00"]],
    "breakfast_queue_arrival_approx": "08:30 (2부 10분 전 환산)",
    "breakfast_queue_parties_approx": 3,
    "breakfast_actual_wait_min": None,
    "breakfast_seat": "한강뷰", "breakfast_exact_order": None,
    "breakfast_early_arrival_reason": "다른 후기의 긴 대기 경험을 읽음",
    "pool_duration_min_approx": 60, "pool_start_time": None,
    "morning_skyard_duration_min_approx": 30,
    "return_mode": "호텔 셔틀", "return_station": None,
    "party_split": "월요일 짝꿍은 차로 출근, 작성자 등은 셔틀 귀가",
    "satisfaction": "시설·직원·한강뷰 수영과 식사에 만족한다고 서술",
    "revisit_intent": None,
}

# 본문 요약과 위치. 제3자의 대기 경험, 일반 시설 소개는 실제 방문으로 만들지 않는다.
EVIDENCE = {
    "stay": ("도입부", "2025년 3월 9~10일, 일요일 입실·월요일 퇴실이라고 명시"),
    "pool": ("수영장", "비스타 3층 실내 수영장에서 약 1시간 수영했다고 서술"),
    "lounge": ("클럽 라운지 앤 바", "성인 3명; 개시 10분 전 도착해 창가 자리 확보; 두 시간 이용"),
    "sky_night": ("스카이야드", "라운지 후 약 20:30 방문"),
    "breakfast": ("조식", "2부 개시 약 10분 전 줄을 섬; 앞에 약 3팀; 한강뷰에서 식사"),
    "sky_morning": ("조식 끝부분", "아침 식사 후 퇴실 전 약 30분 족욕"),
    "departure": ("셔틀버스", "동행 한 명은 차로 출근, 작성자 등은 셔틀로 귀가"),
}

# 작성자의 당시 설명에 한정. 공식 확인 아님. 음식 제공창과 사전 착석을 분리한다.
VISIT_WINDOWS = {
    (date(2025, 3, 9), "GRAND_CLUB_LOUNGE"): (
        VenueWindow(time(18), time(20), source=SourceKind.REVIEW),
    ),
    (date(2025, 3, 9), "VISTA_CASE_LOUNGE_SEATING"): (
        VenueWindow(time(17, 50), time(18), source=SourceKind.REVIEW),
    ),
    (date(2025, 3, 10), "THE_BUFFET"): (
        VenueWindow(time(7), time(8, 20), source=SourceKind.REVIEW),
        VenueWindow(time(8, 40), time(10), source=SourceKind.REVIEW),
    ),
}

# state, location, day(1/2), start, end, venue, evidence, time_basis
# 객실/키/정확한 식사 종료/퇴실·승차 시각은 본문 미상. 모든 임시 시각을 표시한다.
ROWS = [
 ("AT_FRONT_DESK", "VISTA_LOBBY", 1, "15:00", "15:08", None, "stay", "시작·종료·로비 내 위치 모두 실행 가정; 실제 체크인 시각 미상"),
 ("KEY_ISSUED", "VISTA_LOBBY", 1, "15:08", "15:10", None, "stay", "키 수령 상태와 시각은 객실 전제 모델 가정"),
 ("IN_ROOM", "VISTA_ROOM", 1, "15:20", "15:35", None, "stay", "시작·종료 가정"),
 ("ENTERED", "VISTA_POOL", 1, "16:00", "17:00", None, "pool", "약 1시간만 본문; 시작·종료·라운지 전 배치는 가정"),
 ("SEATED", "GRAND_CLUB_LOUNGE", 1, "17:50", "18:00", "VISTA_CASE_LOUNGE_SEATING", "lounge", "도착 17:50은 18시-10분 환산; 즉시 착석은 가정"),
 ("HAPPY_HOUR_ACTIVE", "GRAND_CLUB_LOUNGE", 1, "18:00", "20:00", "GRAND_CLUB_LOUNGE", "lounge", "본문 운영창과 두 시간 이용을 조합; 정확한 착석·퇴장 실측은 아님"),
 ("IN_LOUNGE", "SKYARD", 1, "20:30", "21:00", None, "sky_night", "시작 약 20:30 명시; 종료 가정; IN_LOUNGE는 공간 점유 표현"),
 ("IN_ROOM", "VISTA_ROOM", 1, "21:30", "08:15", None, "stay", "객실 복귀·밤새 연속 점유·다음 날 출발 모두 가정"),
 ("IN_QUEUE", "THE_BUFFET", 2, "08:30", "08:40", None, "breakfast", "시작은 약 10분 전 환산; 종료·실제 대기 10분은 가정"),
 ("SEATED", "THE_BUFFET", 2, "08:40", "08:42", "THE_BUFFET", "breakfast", "착석 시각·지속시간 가정"),
 ("DINING", "THE_BUFFET", 2, "08:42", "09:20", "THE_BUFFET", "breakfast", "시작·종료 가정; 메뉴별 주문을 만들지 않음"),
 ("IN_LOUNGE", "SKYARD", 2, "09:50", "10:20", None, "sky_morning", "약 30분만 본문; 시작·종료 가정"),
 ("CHECKED_OUT_SETTLED", "VISTA_LOBBY", 2, "10:40", "10:45", None, "departure", "퇴실 시각·정산 완료 상태 가정; 실제 장소 세부 미상"),
 ("SHUTTLE_BOARDED", "HOTEL_GATE", 2, "11:00", "11:00", None, "departure", "승차 시각·정류장 노드 대응 가정; 하차역·귀가시각 미상으로 생략"),
]

def build_timeline():
    result = []
    for state, location, day, start, end, venue, _, _ in ROWS:
        end_day = day + 1 if end < start else day
        result.append(TimelineSegment(state, location,
            datetime.fromisoformat(f"{VISIT_DATES[day-1]}T{start}"),
            datetime.fromisoformat(f"{VISIT_DATES[end_day-1]}T{end}"), venue=venue))
    return result

def validate_case():
    return validate_walkerhill_timeline(build_timeline(), nights=NIGHTS)

if __name__ == "__main__":
    print(SOURCE_URL)
    print("기본 운영시간 모델(차이를 숨기지 않음):")
    print(validate_walkerhill_timeline(build_timeline()).render())
    print("후기 기반 해당 방문 조건(공식 미확인; 미상 시각은 가정):")
    report = validate_case()
    print(report.render())
    print("검사 제외/한계: 수영장·족욕장 운영시간, 대기 상태의 물리 점유, 정확한 실측 이동시간")
    raise SystemExit(0 if report.ok else 1)
