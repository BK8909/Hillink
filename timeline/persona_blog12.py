"""
blog12 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 텍스트 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2 — v4 계수 확정(fit_v4_result.json) 뒤에 만든 후기. 사람은 정답만 원문과 대조
손으로 만든 persona_blog12.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 12
시험용(held-out) 후기 2 — v4 계수 확정 뒤 봉인. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2019, 2, 9, 14, 30)      # △(추정: 후기에 정확한 날짜 없이 '설연휴가 끝난 주말'로만 언급, 2019년 설날(2/5) 기준 첫 주말인 2/9(토)로 추정, 시각은 기본값 14:30)

FACTS_EVIDENCE = {
    "property": "◎ '비스타 워커힐 디럭스 더블룸 리버뷰' 체크인이라고 명시",
    "nights": "△ 박 수는 명시되지 않음, 호캉스 후기 전개상 1박으로 추정",
    "party": "○ '아이들과' (복수), '동행자', '본인' 언급 → 성인 2 + 아이 2명 정도로 추정, 정확한 인원은 불명확",
    "included_meals": "◎ 음식마다 개별 가격이 적혀 있어(삼선짜장면 1.9만원 등) 패키지에 포함된 식사가 아니라 개별 주문으로 판단됨",
    "room_minimal": "○ 언급 없음, 기본값 false로 둠"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.3, '◎ 비스타 투숙임에도 저녁 식사를 위해 연결 통로를 통해 그랜드 워커힐 금룡까지 이동함, 이동을 꺼리지 않음'),
    '격식 선호': (0.5, '○ 격식있는 중식당이지만 코스가 아닌 단품 메뉴(짜장면·볶음밥·딤섬·탕면)를 개별 주문함, 격식과 캐주얼이 섞임'),
    '조망 중시': (0.8, "◎ '창가에 앉아 멀리 보이는 강을 바라보며 식사', '대형 유리창으로 보이는 리버뷰에서의 식사는 이곳을 더욱 특별하게 만들어 줌' 등 뷰를 여러 차례 강조"),
    '새로움 추구': (0.6, "○ 여러 호텔(서울신라, 제주롯데, 팔선 등)과 비교하며 다양한 곳을 경험했고, 이 중식당에서 딤섬은 '이번이 처음'이라고 밝힘"),
    '함께 먹기 선호': (0.8, "◎ '아이 한숟갈, 본인 한숟갈 먹어보는 볶음밥', '아이들을 먹이고 나서 결국 남은 자장면에 공기밥을 주문', '아이들을 먹이면서도 같이 나눠 먹어도 나쁘지 않은 양' 등 함께 나눠 먹는 모습을 여러 차례 서술"),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog12 · 비스타 리버뷰 1박 · 가족(부부+아이들)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_ROOM": "◎ '비스타 워커힐 디럭스 더블룸 리버뷰' 체크인",
    "VISTA_POOL": "◎ '비스타 워커힐 체크인 후 실내수영장에서 아이들과 재미있게 물놀이를 즐긴후에'",
    "MOEGI": "◎ '일식당 모에기의 데판야끼 후기는 이미 사용기에 작성하였습니다' — 같은 체류 중 이용 — [봉인 확인] 같은 체류의 별도 글. 끼니 시각 미상이라 끼니 정답에서는 뺌",
    "GEUMRYONG": "◎ '저녁식사를 위하여 그랜드 워커힐에 있는 중식당 금룡으로 향하였습니다', 다수 메뉴를 주문해 식사함"
}
TRUTH_PASSED: dict[str, str] = {
    "VISTA_LOBBY": "○ '비스타 워커힐 로비에서 연결 통로를 통하여 이동하면 됩니다' — 금룡으로 가는 경유지로 언급"
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
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['GEUMRYONG', 'MOEGI'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'VISTA_POOL', '◎ 체크인 후 실내수영장에서 물놀이를 즐긴 순서로 서술됨'), ('VISTA_POOL', 'GEUMRYONG', "◎ 수영장 이용 후 '저녁식사를 위하여' 금룡으로 향했다고 명시")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'GEUMRYONG', "◎ '저녁식사를 위하여 그랜드 워커힐에 있는 중식당 금룡으로 향하였습니다', 짜장면·볶음밥·쇼마이·탕면 등을 먹음")]
