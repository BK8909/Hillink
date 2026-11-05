"""
blog57 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog57.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 57
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 5, 17, 30)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "○ 비투숙 — 주차 후 워커힐호텔 1층 로비에서 셔틀 이용 (그랜드 쪽으로 추론)",
    "nights": "◎ 피자힐 식사만 하고 귀가 ('돌아오는 길에')",
    "party": "○ '4인 콰트로 세트' 주문, 동행자와 아이들 · 13세 미만은 ○ (아이들이 불꽃놀이를 처음 봄 등 어린 아이로 추론)",
    "included_meals": "◎ 비투숙, 선결제 예약 식사 — 포함 끼니 없음",
    "booked": "◎ 네이버로 피자힐 5시 30분 타임 예약·선결제",
    "arrival": "◎ '주차타워에 주차 후' 호텔로 연결 — 자차 직접 주차",
    "room_minimal": "◎ 비투숙",
    "depart_by": "△ 17:30~19:00 식사 후 빛의 라운지 등 들렀다가 떠난 것으로 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, "○ '인기가 있어 주말 예약은 최소 한 달 전에' — 미리 예약해 대기를 피함"),
    '이동 최소화': (None, '근거 없음 → 미상 (셔틀은 이용 사실뿐)'),
    '격식 선호': (0.25, '○ 기념일 식사로 캐주얼한 피자·파스타 식당(피자힐)을 골라 감'),
    '조망 중시': (0.75, "◎ 배정 좌석에서 '뻥 뚫린 한강뷰가 보이는 좌석도 있어서 살짝 아쉬웠어요' — 좌석 뷰를 선택 기준으로 따짐 · 해질녘 노을 언급"),
    '새로움 추구': (0.25, "◎ 피자힐 '4번째 방문' — 같은 곳 재방문, 목적지 하나"),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (4인 세트를 함께 먹었다는 사실뿐)'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog57 · 비투숙 · 피자힐 디너 · 4인(아이 동반) · 자차 · 기념일',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(19, 30),
    included_meals=(),
    booked=('PIZZA_HILL',),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "PARKING_TOWER_B1": "○ 주차타워에 주차 후 호텔 연결층으로 이동 (후기는 '지하 3층이 호텔로 연결'이라 적음)",
    "GRAND_LOBBY": "◎ '워커힐호텔 1층 로비에서 셔틀서비스를 이용'",
    "PIZZA_HILL": "◎ 5시 30분 타임에 4인 콰트로 세트·파스타·샐러드 식사"
}
TRUTH_PASSED: dict[str, str] = {
    "THEATRE_ART_SHOP": "○ 기프트샵 구경만 하고 '다음에 사려고' 사진만 찍음 (빛의 라운지 근처 기프트샵으로 추론)"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음 (비투숙)",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음 (비투숙)",
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
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 라운지 카페": "○ 아이가 포즈를 취한 사진 — 들렀으나 주문 여부는 불명"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('PARKING_TOWER_B1', 'GRAND_LOBBY', '○ 주차 후 호텔로 연결 → 1층 로비에서 셔틀'), ('GRAND_LOBBY', 'PIZZA_HILL', '◎ 1층 로비에서 셔틀을 타고 피자힐 아래까지 이동')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 5시 30분 디너 타임에 피자·파스타·샐러드')]
