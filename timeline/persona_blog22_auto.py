"""
blog22 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog22.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 22
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 1층 더뷔페 방문",
    "nights": "◎ 식사만 하러 방문 (비투숙)",
    "party": "△ 가족 기념일 식사 · 예시 계산이 5인 기준이라 5명으로 추정, 13세 미만 아이 동반 언급 없음",
    "included_meals": "패키지 포함 끼니 없음 (멤버십 식음료 이용권으로 결제 차감)",
    "room_minimal": "비투숙이라 객실 없음",
    "booked": "◎ 방문 전 전화로 예약하며 창가 자리 요청",
    "arrival": "◎ 차를 가지고 방문, 호텔 정문에서 카드 혜택 무료 발렛",
    "depart_by": "△ 평일 런치 12:00~14:30, 끝나는 시각으로 추정",
    "start_at": "날짜·시각 미기재 (평일 런치 12:00 시작 → 11:30 도착 추정이나 날짜 없음)"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '○ 사전 예약은 기념일 자리 요청 목적이며 대기 관련 서술 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '○ 평소 호텔 뷔페를 좋아해 뷔페를 고름 — 코스·정찬 선택 여부는 드러나지 않음 → 미상'),
    '조망 중시': (0.75, "◎ '분위기와 뷰까지 좋은 곳으로 가고 싶어서' 더뷔페로 결정, 미리 전화해 창가 자리를 요청하고 '뷰를 중요하게 생각한다면 꼭 요청' 이라고 스스로 밝힘"),
    '새로움 추구': (0.25, '○ 워커힐을 자주 이용하는 편이며 이번 방문은 더뷔페 한 곳만을 목적으로 함'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, "○ '천천히 이야기하면서 여유롭게 식사' 는 분위기 묘사일 뿐 한적함을 이유로 고른 문장 없음 → 미상"),
}

PERSONA = Persona(
    name='[자동] blog22 · 비스타 더뷔페 평일 런치 · 비투숙 가족 기념일 식사',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=5,
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(14, 30),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival='car_valet',
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 평일 런치로 더뷔페에서 창가 자리 배정받아 식사, 디저트까지 먹음",
    "VALET_DESK": "◎ 호텔 정문에서 발렛 맡기고 바로 식사하러 들어감"
}
TRUTH_PASSED: dict[str, str] = {
    "HOTEL_GATE": "◎ 정문에서 발렛 맡김 (통과)",
    "VISTA_LOBBY": "○ 비스타 건물 안으로 들어가 안내 따라 더뷔페로 이동"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VALET_DESK', 'THE_BUFFET', '◎ 발렛 맡기고 바로 식사하러 들어감')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('중식', 'THE_BUFFET', '◎ 더뷔페 평일 런치 식사')]
