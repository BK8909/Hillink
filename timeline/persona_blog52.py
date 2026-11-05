"""
blog52 — 한호 시험용 정답 확인 (에이전트 실행 금지)
정답 확인: 한호 · 9/29 · 보류 없음 (정확한 인원·끼니·시각·주차 장소는 원문상 미상)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
9/28 자동 초안을 원문 r056과 대조했다. 성향(TRAIT_EVIDENCE)은 자동 초안 그대로 두었다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 8, 17, 30)      # 날짜 △ 글 작성일 · 시각 △ 자동 추정값 유지; 중식·석식조차 미상이라 실제 도착으로 해석 금지

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 1층 더뷔페만 이용 (숙박 언급 없음)",
    "nights": "◎ 비투숙 — 식당만 이용",
    "party": "△ '저희'로 최소 2명은 확인되나 실제 인원은 적지 않음. 데이트 추천은 본인 동행 증거 아님",
    "included_meals": "○ 비투숙이라 포함 끼니 없음",
    "booked": "△ 창가 자리 예약 방법을 안내했을 뿐 본인이 사전 예약했다는 문장은 없음",
    "arrival": "◎ 발렛은 하지 않고 그냥 주차장에 주차",
    "depart_by": "△ 실제 퇴장 시각 미기재; 20:00은 자동 추정값",
    "room_minimal": "○ 비투숙"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (뷔페 방문만으로 판단 불가)'),
    '조망 중시': (0.5, "◎ '뷰 좋죠 근데 창가자리 못앉음 이슈' — 뷰를 좋게 보지만 그 때문에 고른 문장은 없음"),
    '새로움 추구': (None, '근거 없음 → 미상 (뷔페 안에서 모든 코너를 조금씩 맛봤다는 문장은 장소 선택 근거가 아님)'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (자리가 금방 찼다는 묘사만)'),
}

PERSONA = Persona(
    name='[확인 초안] blog52 · 비투숙 · 비스타 더뷔페 주말 식사 · 자차 직접 주차',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,  # △ 확인 가능한 최소 인원만 실행용으로 유지; 정확한 인원 미상
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),  # 예약 방법 안내와 본인 예약은 구분
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 주말에 더뷔페에서 안쪽 자리에 앉아 고기·일식·중식·한식·디저트까지 식사"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VALET_DESK": "◎ 발렛은 하지 않았다고 적음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "SKYARD": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "건물 미상 층 미상 주차장": "◎ 발렛 없이 직접 주차; 어느 건물·층의 주차장인지는 원문에 없음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = []  # 보류: 식사는 확실하지만 중식·석식 구분 근거가 없음

