"""
blog37 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog37.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 37
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 5, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "○ '그랜드 워커힐 숙박후기' 단락, 그랜드 추천",
    "nights": "△ 박 수 언급 없음 → 1박 추정",
    "party": "△ 인원 언급 없음 → 2인 추정 · 본인 아이 동반 언급 없음 (아이·가족 동반은 일반 추천 문구)",
    "included_meals": "○ 포함 끼니 언급 없음 (포함 혜택 비교하라는 일반 조언뿐)",
    "arrival": "◎ 짐 간단히 챙겨 대중교통(셔틀)으로 다녀옴 → 자차 아님",
    "room_minimal": "○ 근거 없음 → 기본값"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.75, '○ 도심보다 호텔 안에서 이것저것 즐길 수 있는 곳을 찾는 편이라고 밝힘 · 아침부터 식당 찾아 이동하지 않아도 되는 게 만족도를 높인다고 적음'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, '○ 호텔을 고를 때 객실에서 풍경도 보는 곳을 찾는 편이라고 스스로 밝힘'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog37 · 그랜드 숙박(홍보성 안내글) · 대중교통 · 구체 이용 기록 거의 없음',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "○ 그랜드 워커힐 숙박후기로 소개 (객실 이용 묘사는 일반론 수준)"
}
TRUTH_PASSED: dict[str, str] = {
    "GWANGNARU_STN": "○ 셔틀로 대중교통 방문 — 광나루역·강변역 중 어느 쪽인지 불명",
    "GANGBYEON_STN": "○ 셔틀로 대중교통 방문 — 광나루역·강변역 중 어느 쪽인지 불명",
    "GRAND_POOL": "○ 실내 수영장 소개·추천만",
    "FOREST_PARK": "○ 소개·추천만",
    "RIVERPARK": "○ 8월 30일까지 운영된 시즌 시설이라는 안내만",
    "THEATRE_OF_LIGHT": "○ 전시 소개·추천만",
    "THE_BUFFET": "○ 조식 추천만, 식사 언급 없음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "DOUGLAS_ROOM": "○ 호텔 비교 설명으로만 언급",
    "VISTA_ROOM": "○ 호텔 비교 설명으로만 언급",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = []
