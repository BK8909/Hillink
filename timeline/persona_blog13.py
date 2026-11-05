"""
blog13 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 텍스트 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2 — v4 계수 확정(fit_v4_result.json) 뒤에 만든 후기. 사람은 정답만 원문과 대조
손으로 만든 persona_blog13.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 13
시험용(held-out) 후기 2 — v4 계수 확정 뒤 봉인. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2023, 9, 24, 18, 30)      # △

FACTS_EVIDENCE = {
    "property": "△ 온달·금룡·더뷔페가 함께 위치한 워커힐 2층 식당가로 소개됨(통상 그랜드 워커힐 건물 소재)",
    "nights": "◎ 식당 이용만 언급되고 투숙에 대한 언급이 전혀 없음 → 비투숙 0박",
    "party": "◎ 동행자들과 함께 저녁 식사를 했고 아이의자·아이식기·어린이 반상이 등장해 아이 동반이 확인되나, 정확한 인원수는 언급되지 않음",
    "included_meals": "◎ 14만5천원 코스를 직접 주문/결제해 먹은 식사로 숙박 패키지에 '포함'된다는 표현이 없음 → 빈 배열",
    "room_minimal": "◎ 비투숙(식당 이용만)이므로 해당 없음",
    "booked": "○ [봉인 확인] 룸 코스 · '다른 식당이 예약 안 될 때' 서술 — 온달이 방문 목적"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.8, '◎ 14만5천원짜리 궁중상차림 코스를 주문했고, 코스 구성과 분위기가 좋았다고 평가함'),
    '조망 중시': (None, '근거 없음 → 미상'),
    '새로움 추구': (0.2, '◎ 이전에도 온달을 여러 차례(왕왕) 방문한 이력이 있고 이번에도 같은 곳을 재방문함'),
    '함께 먹기 선호': (0.6, '○ 동행자들과 한 룸에서 한 테이블에 앉아 함께 식사한 후기 전반'),
    '조용함 선호': (0.6, "○ '손님과 조용히 얘기하고 싶을 때' 방문할 만한 곳이라고 스스로 평가함"),
}

PERSONA = Persona(
    name='[자동] blog13 · 온달 한정식 코스 저녁 · 동행자 동반(아이 포함)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=True,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(21, 0),
    included_meals=(),
    booked=('ONDAL',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "ONDAL": "◎ 온달에서 궁중상차림 코스로 저녁 식사를 함 (전복구이, 생선회, 너비아니, 냉면 등 코스 전체를 먹음)"
}
TRUTH_PASSED: dict[str, str] = {
    "GEUMRYONG": "온달의 위치를 설명하며 같은 층에 있는 식당으로 언급만 됨",
    "THE_BUFFET": "온달의 위치를 설명하며 같은 층에 있는 식당으로 언급만 됨"
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
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
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
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['ONDAL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'ONDAL', '◎ 워커힐 온달에서 궁중상차림 코스로 저녁 식사를 함')]
