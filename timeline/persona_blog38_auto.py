"""
blog38 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog38.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 38
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 1, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "△ 숙박 건물 명시 없음 — 더뷔페가 비스타 워커힐 1층이라 비스타로 추정",
    "nights": "○ '전날 디너 뷔페를 거하게 먹었어도 설레이면서 잠들었던' → 전날 디너 후 숙박, 1박 추정",
    "party": "△ 인원 명시 없음 → 2인 추정, 아이 동반 언급 없음",
    "included_meals": "○ 조식·디너 포함 여부 명시 없음",
    "room_minimal": "△ 객실 언급 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (뷔페만 이용, 코스·캐주얼을 고른 문장 없음)'),
    '조망 중시': (0.5, "◎ '한강뷰와 숲뷰를 보며 여유롭게 아침' — 좋았다 정도"),
    '새로움 추구': (0.25, "○ '호텔 조식 뷔페 중 좋아하는 곳이 워커힐 더뷔페', '다시 방문하고 싶은 조식, 단연 더뷔페' — 익숙한 한 곳을 반복 선호, 디너·조식 모두 더뷔페"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog38 · 더뷔페 디너+조식 · 투숙 추정 · 조식 재방문 선호',
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
    "THE_BUFFET": "◎ 전날 디너 뷔페를 먹고 다음날 더뷔페 조식을 여러 접시 먹음"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'THE_BUFFET', "◎ '전날 디너 뷔페를 거하게 먹었어도', '어제 디너에 대게가 있었던 곳' — 같은 더뷔페 디너"), ('조식', 'THE_BUFFET', '◎ 더뷔페 조식을 샐러드·스프·볶음밥 등으로 먹음')]
