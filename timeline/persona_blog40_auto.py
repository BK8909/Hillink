"""
blog40 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog40.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 40
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 8, 17, 0)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 1층 더뷔페 방문 (숙박 없음)",
    "nights": "◎ 식사만 하러 방문",
    "party": "◎ 2인 예약·선결제, 동행자 1명과 방문",
    "included_meals": "◎ 숙박 패키지 없음",
    "room_minimal": "비투숙이라 해당 없음",
    "booked": "◎ 인기가 많아 한 달 전에 예약하고 선결제",
    "start_time": "△ 끼니·시각이 적혀 있지 않음 → 석식 추정, 이용 30분 전",
    "depart_by": "△ 석식 이용 끝 무렵 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, '○ 인기가 많아서 한 달 전에 미리 예약하고 방문'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.75, '○ 동행자에게 좋은 곳에서 식사하는 경험을 주려고 호텔 뷔페를 골라 예약, 이후 파인다이닝도 일부러 예약'),
    '조망 중시': (0.5, '○ 운 좋게 창가 자리에 앉아 더 행복하게 식사했다 — 좋았다 정도'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (같이 먹었다는 사실만)'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog40 · 비투숙 · 더뷔페 식사 2인 (2024년 2월 방문분 — 뒤의 외부 한식 다이닝 방문은 제외)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 동행자와 더뷔페에서 식사 — 수프, 대게, 딸기, QR 주문 커피"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'THE_BUFFET', '◎ 더뷔페에서 식사 (끼니는 후기에 없음 → 석식은 △ 추정)')]
