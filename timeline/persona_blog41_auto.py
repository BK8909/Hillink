"""
blog41 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog41.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 41
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 5, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 딜럭스 객실 투숙",
    "nights": "◎ '2박 3일 동안 우리집으로'",
    "party": "○ '우리집', 피자힐에서 피자·파스타 세트와 음료 2잔 주문 → 2인 추정 · 아이 언급 없음",
    "included_meals": "○ 포함 끼니 언급 없음 · 더뷔페 디너는 식사권, 피자힐은 투숙객 할인 결제",
    "room_minimal": "◎ 객실 비품을 자세히 쓰고 객실에서 배달 치킨 먹음",
    "arrival": "◎ 그랜드 워커힐 주차타워에 주차 후 호텔연결통로로 이동",
    "booked": "○ 더뷔페 식사권 사용 — 사용 전 사전 예약 필수라고 적음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상 (피자힐은 셔틀 이용, 선택 변경 없음)'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.25, "◎ '사실 뷰를 크게 신경 안 쓰는 편인데'"),
    '새로움 추구': (0.75, "◎ '부대시설 뽕을 뽑자!' — 헬스장·수영장·스카이야드·라이브러리 두루 이용 · 디핑 소스 맛이 궁금해 세트 주문, 반반피자로 두 가지 맛봄"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (헬스장·뷔페 붐빔 묘사뿐, 선택 변경 없음)'),
}

PERSONA = Persona(
    name='[자동] blog41 · 비스타 2박 · 2인 추정 (객실·부대시설·더뷔페 디너·피자힐 연재)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=2,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "◎ 그랜드 워커힐 1층 프런트에서 체크인, 카드키 받음",
    "VISTA_ROOM": "◎ 비스타 딜럭스 객실 2박",
    "GRAND_LOBBY": "○ 배달음식은 그랜드 1층 로비에서 받는다고 적고 배달 치킨을 먹음 · 피자힐 셔틀도 그랜드 1층 태블릿으로 호출",
    "FITNESS": "◎ 운동화 대여해 헬스장에서 운동, 야외 러닝 공간도 이용",
    "VISTA_POOL": "◎ 선베드에서 뷰 감상, 유아풀에서 몸 지지고 수영장 마무리",
    "SKYARD": "◎ 발 세척 후 족욕탕 입수, '극락이 따로 없다'",
    "GRAND_LIBRARY": "○ 그랜드 2층 라이브러리 방문, 코믹북·도서 사진",
    "THE_BUFFET": "◎ 평일 더뷔페 디너를 두 시간 정도 식사",
    "PIZZA_HILL": "◎ 셔틀 타고 피자힐, 목요일 점심시간 지나 피자·파스타 식사"
}
TRUTH_PASSED: dict[str, str] = {
    "LE_PASSAGE": "○ 케이크·와인 가격만 구경, 구매 언급 없음",
    "PARKING_TOWER_B1": "○ 주차타워에서 호텔연결통로로 이동해 호텔 지하 1층으로 들어옴"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "○ 언급 없음 (수영장 야외 선베드는 '살 타는 건 싫다')",
    "GRAND_POOL": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_FRONT_DESK', 'VISTA_ROOM', '◎ 체크인 후 비스타 객실 방향으로 이동'), ('GRAND_LOBBY', 'PIZZA_HILL', '◎ 그랜드 1층 태블릿으로 셔틀 호출해 피자힐 이동')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'THE_BUFFET', '◎ 평일 더뷔페 디너, 식사권 사용'), ('중식', 'PIZZA_HILL', '◎ 목요일 점심시간 지난 후 피자·파스타')]
