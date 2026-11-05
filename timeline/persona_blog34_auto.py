"""
blog34 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog34.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 34
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 4, 15, 0)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울 객실 이용",
    "nights": "◎ '1박 동안 꽉 채워서'",
    "party": "○ '저희는' 수영복 입고 셔틀 탑승 — 동행자 1명과 2인으로 추론, 아이 동반 언급 없음",
    "included_meals": "○ 조식을 먹었으나 '포함' 표기 없음",
    "booked": "◎ 리버파크 티켓 부스에서 '예약자와 이용 패키지를 확인' 후 팔찌 수령",
    "arrival": "◎ '차 없이 지하철을 이용', 광나루역 무료 셔틀 → 자차 아님",
    "room_minimal": "◎ 수영 후 객실로 돌아와 씻고, OTT 장치 요청 등 객실 사용"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.25, "◎ 체크인 웨이팅이 있었지만 '로비도 넓고 분위기가 좋아서 기다리는 동안 구경하기도 좋았습니다'"),
    '이동 최소화': (0.75, "○ '락커를 따로 들리고 싶지 않아서' 객실에서 수영복·가운 차림으로 바로 셔틀 탑승 — 동선을 줄이려 선택을 바꿈"),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, "○ 조식 '제일 중요한 뷰가 너무 예뻤다'고 뷰를 가장 중요한 요소로 꼽음 · 럭스바 '한강 뷰 보면서 한잔할 수 있다는 점이 좋았다'"),
    '새로움 추구': (0.75, "◎ '객실에서만 쉬는 호캉스가 아니라' 수영장→바→조식까지 '꽉 채워서 즐기고' — 여러 곳을 일부러 챙김"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.5, "○ 리버파크에 가족 단위 이용객이 꽤 많았지만 '그래도 저는 전체적으로 만족' — 붐빔에 무관"),
}

PERSONA = Persona(
    name='[자동] blog34 · 그랜드 1박 · 2인 · 지하철+셔틀 · 리버파크·럭스바·조식',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('RIVERPARK',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "GWANGNARU_STN": "◎ 광나루역 2번 출구 맞은편 정류장에서 무료 셔틀 탑승",
    "GRAND_FRONT_DESK": "◎ 일요일 오후 3시쯤 도착해 웨이팅 후 체크인",
    "GRAND_LOBBY": "◎ 체크인 대기 중 로비 구경, 1층 리버파크 티켓 부스에서 팔찌 수령 후 로비 앞 셔틀 탑승",
    "GRAND_ROOM": "◎ 그랜드 객실 숙박, 수영 후 돌아와 씻음",
    "RIVERPARK": "◎ 1부를 오후 6시 마감까지 이용, 선베드·맥주",
    "LUX_BAR": "◎ 수영 후 씻고 럭스바에서 한강 뷰 보며 한잔",
    "THE_BUFFET": "○ 다음 날 아침 7시 조식 뷔페 (식당 이름은 적혀 있지 않음 — 그랜드 조식 뷔페로 추론)"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GANGBYEON_STN": "○ 언급 없음 (강변역에서도 탈 수 있다는 안내만)",
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GWANGNARU_STN', 'GRAND_FRONT_DESK', '◎ 광나루역 셔틀로 도착 후 체크인'), ('GRAND_FRONT_DESK', 'GRAND_ROOM', '◎ 체크인 후 객실'), ('GRAND_ROOM', 'RIVERPARK', '○ 락커를 안 쓰려고 수영복·가운 차림으로 셔틀 탑승 — 객실에서 갈아입고 간 것으로 추론'), ('RIVERPARK', 'LUX_BAR', '◎ 리버파크에서 6시까지 놀고 객실에서 씻은 다음 럭스바'), ('LUX_BAR', 'THE_BUFFET', '◎ 럭스바 → 다음 날 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'RIVERPARK', '○ 수영장 안에서 맥주와 간식을 사 먹음'), ('조식', 'THE_BUFFET', '○ 다음 날 아침 7시 조식 뷔페 (식당 이름 미기재)')]
