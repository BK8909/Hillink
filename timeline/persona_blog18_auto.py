"""
blog18 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog18.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 18
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

FACTS_EVIDENCE = {
    "property": "◎ '비스타 워커힐 서울 피자힐' 식사만 — 투숙 없음",
    "nights": "◎ 식사 모임만, 숙박 언급 없음",
    "party": "◎ 본인 + 동행자 2인의 평일 만남, 아동 동반 없음",
    "included_meals": "○ 패키지 없음",
    "room_minimal": "○ 비투숙이라 해당 없음",
    "arrival": "○ 셔틀버스로 워커힐 호텔에 내려 걸어 올라감 — 자차 아님",
    "depart_by": "△ 식사 1회차 1시간 30분 + 걸어서 하산 → 점심 이후로 추정",
    "booked": "○ 좌석을 배정받았다고만 적힘, 예약 명시 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.5, '○ 셔틀 호출을 몰라 언덕을 헥헥대며 걸어서 오간 것을 아쉬워함 · 선택을 바꾼 문장은 없음'),
    '격식 선호': (0.75, "◎ 모임 돈으로 매년 한 번 '고급진 곳에서 식사'하는 풍습으로 이곳을 골라서 감"),
    '조망 중시': (0.5, "◎ 창가 한강뷰 풍경은 '백점 만점에 백점' — 고른 이유는 피자 유명세라 좋았다 수준"),
    '새로움 추구': (0.75, "◎ '언젠가 한번은 가보자고 했던 곳', '한번 와봤으니 되었다, 호기심 해결되어 만족'"),
    '함께 먹기 선호': (0.75, '○ 동행자를 배려해 해산물 샐러드 대신 치즈&과일 샐러드로 바꿔 세트를 함께 나눠 먹음'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog18 · 비투숙 피자힐 식사 · 지인 3인 평일 모임',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=3,
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(13, 30),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "PIZZA_HILL": "◎ 창가 좌석에서 샐러드·콤비네이션 피자·트러플 크림 파스타 세트를 먹음"
}
TRUTH_PASSED: dict[str, str] = {
    "HOTEL_GATE": "○ 셔틀버스로 워커힐 호텔에 내려 오르막길로 걸어 올라감",
    "VALET_DESK": "발렛 요금·주차 정산 안내만",
    "GWANGNARU_STN": "도보 방문 시 셔틀 타는 곳 안내만",
    "GANGBYEON_STN": "도보 방문 시 셔틀 타는 곳 안내만",
    "LE_PASSAGE": "피자 포장 할인 안내만, 포장 이용 문장 없음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_LOBBY": "◎ 로비에서 셔틀 호출하는 걸 몰라 로비를 거치지 않고 걸어서 오감",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('HOTEL_GATE', 'PIZZA_HILL', '○ 셔틀에서 내려 오르막길을 걸어 피자힐 도착')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('중식', 'PIZZA_HILL', '△ 평일 낮 모임·낮 사진 → 점심으로 추정')]
