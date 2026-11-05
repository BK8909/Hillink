"""
blog46 — 한호 정답 확인
정답 확인: 한호 · 9/29 · 보류 없음 (주차 층·편의점 위치·족욕 자체는 미상; 스카이야드 방문은 확인)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
9/28 자동 초안을 원문 r016과 대조했다. 성향(TRAIT_EVIDENCE)은 자동 초안 그대로 두었다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 4, 20, 0)      # 날짜 △ 글 작성일 · 시각 △ '20시 넘었을 것 같다'의 하한, 정확한 도착 시각 아님

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 스파 있는 방(스파 디럭스)으로 예약",
    "nights": "◎ 행사 끝나고 밤에 체크인, 다음 날 아침 시설 이용 후 모바일 체크아웃",
    "party": "○ 행사 후 동행자와 둘이 호텔에서 숙박",
    "included_meals": "◎ 포함 끼니 언급 없음 (미니바만 무료)",
    "room_minimal": "◎ 뜨끈한 물에 몸 지지려고 스파룸을 골라 욕조·미니바를 즐김",
    "arrival": "○ 주차타워 아무 곳에나 주차하고 실내로 이동했다고 적음 → 자차 직접 주차",
    "start_time": "△ 호텔 도착이 20시를 넘었을 것 같다고 적음; 20:00은 실행용 하한"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, "◎ 모바일 체크아웃으로 줄 안 서고 바로 체크아웃 — '완전 편함'"),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, '◎ 워커힐과 다른 호텔 사이에서 고민하다 한강뷰로 가려고 워커힐을 고름'),
    '새로움 추구': (0.75, "○ '아침에라도 시설 좀 즐겨보려고' 수영장 → 스카이야드를 차례로 찾아감"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (수영장이 텅 비어 여유로웠다는 묘사만)'),
}

PERSONA = Persona(
    name='[확인 초안] blog46 · 비스타 스파 디럭스 1박 · 2인 · 늦은 체크인',
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
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_ROOM": "◎ 스파 디럭스 객실에 숙박, 스파 목욕·미니바 이용",
    "VISTA_POOL": "◎ 아침에 수영복 입고 수영장만 가서 수영, 한강뷰",
    "SKYARD": "◎ 수영장 후 스카이야드로 가 더위·뜨거운 족욕탕 물·전망을 직접 묘사 (발 담금 자체는 미상)"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "◎ 시간 되면 가고 싶었는데 정신이 없어 못 감, 다음에 꼭 가겠다고 함",
    "FOREST_PARK": "◎ 늦게 체크인해서 가보지도 못함",
    "RIVERPARK": "◎ 리버파크도 가볼 시간 없었음",
    "FITNESS": "○ 그랜드 피트니스 방문 언급 없음 (미이용한 곳은 비스타 수영장 옆 피트니스)",
    "THE_BUFFET": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "워커힐 층 미상 공용 주차타워": "○ 주차장에서 호텔로 이동하며 편의점에 들름. 실제 주차 층은 원문에 없음",
    "건물 미상 층 미상 편의점": "◎ 주차장에서 객실로 가는 길에 간식을 구매. CU_THEATRE인지 원문만으로는 불명확"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'VISTA_POOL', '◎ 객실에서 자고 아침에 수영복·가운 입고 수영장'), ('VISTA_POOL', 'SKYARD', '◎ 수영장 갔다가 씻고 스카이야드로 향함')]
TRUTH_MEALS: list[tuple[str, str, str]] = []

