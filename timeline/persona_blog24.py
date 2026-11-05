"""
정답 확인: 슬기 · 9/28 · 15분 · 보류 없음
성향: 9/28 추출기 초안 값으로 맞춤 (경수 · 예전 초안 눈금 0.4·0.6·0.7 → 새 눈금). 정답 · 사실은 슬기 확인 그대로

blog24 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 정답 확인 1차(9/24~) — 개발용
손으로 만든 persona_blog24.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 24
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 31, 11, 30)      # (경수 9/29 · 추출기 시기 규칙으로 채움) 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 1층 더뷔페",
    "nights": "◎ 런치 뷔페 식사만 · 숙박 언급 없음",
    "party": "○ 데이트 식사·수다 타임 서술로 동행자 1명 추정 · 아이 언급 없음",
    "included_meals": "포함 끼니 없음 (비투숙)",
    "room_minimal": "비투숙이라 객실 없음",
    "booked": "예약 언급 없음",
    "arrival": "도착 수단 언급 없음",
    "start_at": "△ 런치 이용시간 12:00~14:30, 비투숙 기본 규칙으로 이용 시작 30분 전 추정",
    "depart_by": "△ 런치 운영 종료 14:30 무렵으로 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.5, '◎ 들어서자마자 보이는 한강뷰가 좋았고 통창 한강뷰에 힐링했다고 적음 — 뷰 때문에 골랐다는 문장은 없음'),
    '새로움 추구': (0.25, "◎ '뭘 먹든 한우물만 파는 스타일이라 맛있으면 그거만 집중공략' 이라고 스스로 밝힘, 방문도 더뷔페 한 곳"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog24 · 비스타 더뷔페 런치 · 비투숙 · 2인 데이트',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(14, 30),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 런치 뷔페 이용"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음 (비투숙)",
    "SKYARD": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('중식', 'THE_BUFFET', '◎ 런치 뷔페')]
