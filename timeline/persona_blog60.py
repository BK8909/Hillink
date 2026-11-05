"""
정답 확인: 슬기 · 2차 · 보류 있음
보류: facts.property — 건물 이름이 직접 적히지 않아 그랜드로 추정
blog60 — r008 정답 확인. 시험용이므로 에이전트 실행 금지.

성향(TRAIT_EVIDENCE)은 자동 초안 값을 유지한다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 30, 15, 0)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "△ 숙박 건물 명시 없음 · '워커힐 로비에서 체크인, 한강뷰 객실' · 발렛 안내가 그랜드 부스 기준이고 저녁엔 그랜드 16층으로 이동 → 그랜드로 추정",
    "nights": "◎ '1박 2일'",
    "party": "○ LUX 바에서 동행자와 1시까지 — 동행자 1명 외 언급 없음",
    "included_meals": "◎ 패키지 포함 끼니 언급 없음 (조식은 옵션으로 추천만)",
    "room_minimal": "○ 짐만 가볍게 풀고 바로 수영장 이동했으나 객실 뷰를 즐겼다고 적음 → 최소화 아님"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, "◎ 피자힐에 예약 없이 19:30~20:00쯤 가서 '잠깐 웨이팅 후' 창가석 안내 — 담담히 기다림"),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (피자힐은 늘 가는 곳이라 고름, 격식 이유 아님)'),
    '조망 중시': (0.75, "○ '평소에 탁 트인 뷰를 정말 좋아하는데' 야경을 이유로 그랜드 16층 LUX 바로 이동 · 피자힐도 창가석 착석"),
    '새로움 추구': (None, "근거 없음 → 미상 (피자힐·LUX 바 모두 '매번 가는/애정하는 곳' 재방문)"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog60 · 1박 여름 호캉스 · 동행자 1 (리버파크 → 피자힐 → LUX 바)',
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
    note="정답 확인 2차 · 시험용 · 성향 자동 초안 유지",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_LOBBY": "○ '워커힐 로비에 도착해서 빠르게 체크인' (건물 명시 없음, 그랜드로 추정)",
    "GRAND_ROOM": "○ 체크인 후 한강뷰 객실에 들어가 짐을 풂 (건물 명시 없음, 그랜드로 추정)",
    "RIVERPARK": "◎ 16:00 야외 수영장(리버파크)에서 물놀이, 선베드 휴식",
    "PIZZA_HILL": "◎ 20:00 물놀이 후 피자힐에서 피자·파스타로 저녁",
    "LUX_BAR": "◎ 22:00 그랜드 16층 LUX 바에서 샴페인, 동행자와 1시까지 머묾"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THE_BUFFET": "○ 다음 날 선택지/추천만 있고 이번 체류 이용 확정 없음",
    "MYONGWOLGWAN": "○ 다음 날 선택지/추천만 있고 이번 체류 이용 확정 없음",
    "VALET_DESK": "○ 발렛 무료 여부 확인 안내만 있고 본인 이용 확정 없음",
    "GRAND_POOL": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ('GRAND_ROOM', 'RIVERPARK', '◎ 짐 풀고 바로 수영장으로 이동'),
    ('RIVERPARK', 'PIZZA_HILL', '◎ 물놀이 후 출출해져 피자힐로'),
    ('PIZZA_HILL', 'LUX_BAR', '◎ 피자 먹은 뒤 그랜드 16층으로 이동')
]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 수영 후 피자힐에서 콤비네이션 피자·파스타 저녁')]
