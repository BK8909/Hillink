"""
blog30 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog30.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 30
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 9, 15, 0)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 호캉스, 포레스트 뷰 객실 선택",
    "nights": "○ 3시 체크인 후 다음 날 아침 조식 — 1박",
    "party": "△ 인원 명시 없음. 커플 호캉스 맥락으로 2인 추정, 13세 미만 동반 언급 없음",
    "included_meals": "○ 조식은 투숙객 20% 할인 가격(인당 6만8천원)으로 이용 — 포함 아님",
    "room_minimal": "○ 체크인 후 방에서 쉬었고 저녁도 객실에서 시켜 먹음 — 객실 최소 이용 아님"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, '◎ 조식 2부는 웨이팅이 꽤 길다고 해서 1부 오픈런으로 감 — 대기를 시간 선택으로 피함'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (저녁을 간단히 분식으로 한 건 조식을 위한 양 조절이지 격식 선호 근거 아님)'),
    '조망 중시': (0.5, '○ 5만원 추가 한강뷰 업그레이드 대신 포레스트 뷰를 고름(뷰에 돈을 더 내지 않음), 스카이야드 노을 뷰·조식 뷰 테이블은 좋았다고 적음 — 좋았다 수준'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (해 진 뒤 족욕 공간이 붐빈다는 관찰·추천만 있고, 붐빔 때문에 선택을 바꾼 문장은 없음)'),
}

PERSONA = Persona(
    name='[자동] blog30 · 비스타 1박 · 포레스트뷰 객실 · 스카이야드 족욕 + 조식 뷔페 1부 오픈런',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
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
    "VISTA_ROOM": "◎ 3시 체크인 후 방에서 조금 쉬었고, 저녁을 객실에서 시켜 먹음",
    "SKYARD": "◎ 5시쯤 4층 족욕 공간에서 노을을 보며 족욕, 해 진 뒤 숨숨집에서 누워 쉼",
    "LE_PASSAGE": "◎ 와인을 사려고 1층 르파사쥬에 들름",
    "THE_BUFFET": "○ 조식 뷔페 1부 오픈런으로 1등 도착, 뷰 테이블에서 4접시 먹음 (식당 이름은 안 적혔으나 1부·2부 조식 뷔페)"
}
TRUTH_PASSED: dict[str, str] = {
    "VISTA_LOBBY": "○ 체크인·호텔 내부 구경 과정에서 지나감 (따로 이용 언급 없음)"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'SKYARD', '◎ 체크인 후 방에서 쉬다가 5시쯤 4층 족욕 공간으로 감'), ('SKYARD', 'LE_PASSAGE', '◎ 족욕 후 내려와서 호텔 구경하고 르파사쥬에 들름'), ('LE_PASSAGE', 'THE_BUFFET', '◎ 전날 저녁 와인 구매, 다음 날 아침 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '○ 다음 날 조식 뷔페 1부 오픈런으로 4접시 먹음')]
