"""
blog52 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog52.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 52
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 8, 17, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 1층 더뷔페만 이용 (숙박 언급 없음)",
    "nights": "◎ 비투숙 — 식당만 이용",
    "party": "○ '저희' · 데이트 추천 — 2인 추정, 아이 언급 없음",
    "included_meals": "○ 비투숙이라 포함 끼니 없음",
    "booked": "○ '창가 자리는 빨리 예약해야 앉을 수 있다, 저희는 안쪽에 앉았다' — 예약 방문 추정",
    "arrival": "◎ 발렛은 하지 않고 그냥 주차장에 주차",
    "depart_by": "△ 식사 시각 미기재 — 주말 석식 18:00 시작 · 약 2시간 이용 추정",
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
    name='[자동] blog52 · 비투숙 · 비스타 더뷔페 주말 식사 · 2인 · 자차 직접 주차',
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
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 주말에 더뷔페에서 안쪽 자리에 앉아 고기·일식·중식·한식·디저트까지 식사"
}
TRUTH_PASSED: dict[str, str] = {
    "VISTA_LOBBY": "○ 더뷔페가 있는 비스타 건물 1층으로 이동"
}
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
    "주차장(위치 미상)": "◎ 발렛 없이 주차장에 직접 주차 — 어느 주차장인지 명시 없음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'THE_BUFFET', '○ 주말 더뷔페 식사 (중식·석식 명시 없음 — 석식은 △ 추정)')]
