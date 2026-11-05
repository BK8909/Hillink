"""
blog29 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog29.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 29
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 14, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 주니어 스파 스위트 이용",
    "nights": "△ 박 수 명시 없음 → 1박 추정",
    "party": "△ 인원·동행자 명시 없음 → 2인 추정, 아이 동반 언급 없음(수영장 아동 안내는 일반 정보)",
    "included_meals": "◎ '미리 조식 포함 패키지로 결제', 조식은 1층 더 뷔페에서 먹음",
    "room_minimal": "○ 객실 미니바·정수기까지 알차게 이용, 객실 이용을 줄였다는 문장 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (식당 선택 문장 없음)'),
    '조망 중시': (0.5, '○ 한강 뷰를 제대로 감상할 수 있는 게 큰 장점, 한강이 한눈에 들어오는 스파 욕조 객실이 좋았다는 정도 — 뷰 때문에 고르거나 돈을 더 냈다는 문장은 없음'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog29 · 비스타 주니어 스파 스위트 · 조식 포함 패키지',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'),),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_ROOM": "◎ 주니어 스파 스위트 투숙, 무료 미니바와 정수기 '알차게 이용했어요'",
    "THE_BUFFET": "◎ '조식은 호텔 1층 더 뷔페에서 먹었어요'"
}
TRUTH_PASSED: dict[str, str] = {
    "VISTA_POOL": "언급만 — 운영 시간·규정 등 시설 소개, 이용 문장 없음",
    "RIVERPARK": "언급만 — 야외 수영장은 여름 한시 운영이라는 안내",
    "SKYARD": "언급만 — '꼭 들러보세요' 추천, 이용 문장 없음",
    "FITNESS": "언급만 — 부대시설 소개",
    "WELLNESS_SAUNA": "언급만 — 웰니스 클럽 소개",
    "LE_PASSAGE": "언급만 — 체크아웃 때 빵 챙겨가기 좋다는 추천"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'THE_BUFFET', '○ 투숙 후 다음날 아침 조식으로 추정')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '◎ 조식 포함 패키지로 1층 더 뷔페에서 조식')]
