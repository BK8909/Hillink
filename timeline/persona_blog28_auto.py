"""
blog28 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog28.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 28
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 2, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 클럽스위트 (10층) 이용",
    "nights": "○ 해피아워 이용 후 '다음 날 아침 식사도 클럽라운지에서' — 1박으로 추론",
    "party": "◎ '4인 가족이 객실 하나에서', 아이들과 동반 · 13세 미만 여부는 ○ (어린이 요금·해피아워 어린이 입장 불가 언급, 엑스트라 베드 추가)",
    "included_meals": "○ 클럽스위트는 '성인 2인 기준' 조식과 클럽라운지 이용이 아이려 있고 어린이만 추가 요금 — '포함' 단어는 없음",
    "booked": "○ 리버파크 이용이 목적이었으나 사전 예약 여부는 적혀 있지 않음",
    "arrival": "○ 주차타워·셔틀은 일반 안내로만 적힘 — 도착 수단 미상",
    "room_minimal": "◎ 방·거실 분리 스위트에서 가족이 머묾 — 객실을 적극 사용"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.75, "◎ '밖에 가능한 나가고 싶지 않아 16층 클럽라운지에서 하기로' · '식사를 위해 동선을 최소화할 수 있었어요' · '많이 움직이지 않고'"),
    '격식 선호': (None, '근거 없음 → 미상 (클럽라운지·피자 포장은 이동·편의 이유로 고름)'),
    '조망 중시': (0.5, "○ 클럽라운지 '한강을 길게 볼 수 있는 시원한 뷰', 스카이야드 야경이 멋졌다 — 좋았다 수준"),
    '새로움 추구': (None, '근거 없음 → 미상 (재방문 계획 언급뿐)'),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (오히려 아이 저녁은 따로 포장)'),
    '조용함 선호': (0.75, "○ 클럽라운지를 고른 장점으로 '붐비지 않는 공간에서 여유있게 식사가 가능하다는 점'을 듦"),
}

PERSONA = Persona(
    name='[자동] blog28 · 그랜드 클럽스위트 1박 · 4인(아이 동반) · 지난 여름 체류',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'GRAND_CLUB_LOUNGE'), ('석식', 'GRAND_CLUB_LOUNGE')),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 그랜드 10층 클럽스위트에서 4인이 숙박",
    "GRAND_CLUB_LOUNGE": "◎ 16층 클럽라운지 해피아워에서 음식을 즐기고, 다음 날 조식도 클럽라운지에서",
    "RIVERPARK": "◎ 여름에 리버파크 이용을 목적으로 다녀와 '너무 만족스러워서'",
    "GRAND_POOL": "◎ '아이와 함께 실내 수영장을 다녀왔어요'",
    "SKYARD": "◎ 스카이야드 족욕에 아이와 발을 담금",
    "PIZZA_HILL": "○ '애들 저녁 식사로 테이크 아웃해서 먹었답니다' (매장 식사는 이전 방문으로 보임)"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THEATRE_OF_LIGHT": "○ 언급 없음 (전시 일정 안내만)",
    "FITNESS": "○ 언급 없음 (수영장만 이용했다고 적음)",
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음 (로비 셔틀 패드는 일반 안내)",
    "GWANGNARU_STN": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음 (주차타워는 일반 안내)",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THE_BUFFET": "○ 성수기라 1층 조식당 대신 클럽라운지에서 조식",
    "THE_PAVILION": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'GRAND_CLUB_LOUNGE', '○ 10층 객실에서 엘리베이터로 16층 클럽라운지로 이동')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'GRAND_CLUB_LOUNGE', '◎ 해피아워에서 안주 겸 식사를 즐김'), ('석식', 'PIZZA_HILL', '○ 아이 저녁으로 피자힐 포장'), ('조식', 'GRAND_CLUB_LOUNGE', '◎ 다음 날 아침 식사를 클럽라운지에서')]
