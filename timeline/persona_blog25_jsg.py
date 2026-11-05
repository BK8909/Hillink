"""
정답 확인: 슬기 · 2차 · 보류 없음
blog25 — 정답 확인 2차 공통 파일.

원문 r003과 체크리스트 기준으로 TRUTH_*와 facts만 대조했다.
성향(TRAIT_EVIDENCE)은 자동 초안 값을 유지한다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 3, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐 서울 318호 배정, 주차타워뷰",
    "nights": "◎ 다음날 조식 먹고 짐 싸면 바로 체크아웃",
    "party": "◎ 4명이 워커힐에 온 건 처음 — 동행자 1 · 아이 2 (아이 어메니티·가운 제공)",
    "included_meals": "◎ '더뷔페 2인 조식포함' 패키지",
    "booked": "◎ 체크인 직후 조식 2부(08:30~) 예약",
    "arrival": "◎ 주차타워에 주차함, 지하 3층 호텔 연결통로 언급",
    "room_minimal": "○ 체크인 후 짐 정리·침대에서 놀기 등 객실 체류 있음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상 (조식 줄이 길었다고만 적고, 예약은 체크인 시 안내에 따른 것)'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (석식 장소 미기재)'),
    '조망 중시': (0.5, '◎ 조식 때 뷰 좋은 공간에서 식사해 아주 좋았다 · 뷰 보며 먹으니 더 맛있었다 — 좋았다 수준, 뷰로 고른 문장 없음'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog25 · 그랜드 1박 · 가족 4인(아이 동반) · 조식·수영장 패키지',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'),),
    booked=('THE_BUFFET',),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인 2차 · 성향 자동 초안 유지",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 체크인하자마자 조식 예약 안내를 받음",
    "GRAND_ROOM": "◎ 객실 배정받아 짐 풀고 아이들이 침대에서 놀고 숙박",
    "GRAND_POOL": "◎ 체크인하고 바로 실내수영장에서 저녁 먹기 전까지 실컷 놂",
    "THE_BUFFET": "◎ 다음날 조식 2부 예약 후 더뷔페에서 조식",
    "PARKING_TOWER_B1": "◎ 주차타워에 주차했고 지하 3층 호텔 연결통로를 언급함"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_LIBRARY": "◎ 체크아웃 후 객실키가 없어 들어가 보진 못했다고 적음",
    "LE_PASSAGE": "○ 르파사쥬 케이크가 객실로 전달됨 — 방문 언급 없음",
    "THEATRE_OF_LIGHT": "○ 패키지에 초대권 포함이라고만 언급, 관람 언급 없음",
    "CU_THEATRE": "○ 지하 편의점 소개만 있고 구매·이용 언급 없음",
    "RIVERPARK": "○ 언급 없음 (해시태그만)",
    "FOREST_PARK": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ('GRAND_ROOM', 'GRAND_POOL', '◎ 객실에서 짐 풀고 수영장 갈 준비'),
    ('GRAND_POOL', 'THE_BUFFET', '◎ 첫날 수영장, 다음날 아침 조식'),
]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '◎ 2부 예약 후 더뷔페 조식')]
