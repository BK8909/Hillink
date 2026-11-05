"""
blog11 — 자동 추출 페르소나 · 2026-10-16 원문 대조로 관찰 정답의 룸서비스 누락 보완 (성향·행동 규칙 미변경)

추출 경로: 후기 텍스트 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2 — v4 계수 확정(fit_v4_result.json) 뒤에 만든 후기. 사람은 정답만 원문과 대조
손으로 만든 persona_blog11.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 11
시험용(held-out) 후기 2 — v4 계수 확정 뒤 봉인. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2021, 11, 15, 14, 30)      # △

FACTS_EVIDENCE = {
    "property": "◎ 더글라스 하우스(워커힐 호텔 뒤편) 투숙",
    "nights": "○ 하루 저녁 일정만 서술되어 1박으로 판단",
    "party": "◎ 동행자와 둘이 방문(기념일)",
    "included_meals": "◎ 더글라스 하우스 투숙 시 라운지(더글라스 아워·조식) 포함 규정 적용",
    "room_minimal": "○ 디럭스룸, 미니멀 객실 언급 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.3, '○ 라운지 앞에서 줄서서 기다렸으나 불만 없이 지켜보며 차분해지는 기분이 들었다고 서술'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.3, '○ 코스 요리 대신 라운지 뷔페를 투고로 받아 객실에서 캐주얼하게 식사'),
    '조망 중시': (0.8, '◎ 숲이 보이는 디럭스룸을 예약했고 식사 중 아차산 노을·달빛을 계속 감상함'),
    '새로움 추구': (0.2, '○ 더글라스 하우스 한 곳(객실·라운지·산책로)에만 머물고 다른 시설 이용 없음'),
    '함께 먹기 선호': (0.8, '◎ 동행자와 함께 느긋하게 식사를 즐겼다고 명시'),
    '조용함 선호': (0.8, '◎ 숲속의 소음 차단과 고요함을 반복해서 강조, 산책로에서도 고요가 바탕이라고 서술'),
}

PERSONA = Persona(
    name='[자동] blog11 · 더글라스 하우스 1박 · 커플 7주년',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='DOUGLAS',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'DOUGLAS_LOUNGE'), ('석식', 'DOUGLAS_LOUNGE')),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 1개",
)

# 실제 주문의 관찰 원장. 가격/수량 미기재는 None이며 0원이나 메뉴표의 다른 음식으로 대체하지 않는다.
OBSERVED_PAYMENTS = (
    dict(id="blog11-room-service-steak", date="2021-11-15", slot="석식",
         venue="DOUGLAS_ROOM", l2="ROOM", l3="IRD",
         product="소갈빗살 스테이크 룸서비스", qty=None, unit="주문 수량 미상",
         included_persons=None, charged_persons=None, krw=None,
         basis="blog11 객실 식사 단락 · 룸서비스 추가 주문 명시 · 2026-10-16 직접 대조",
         note="결제액·수량·구매 당시 단가 미상. 라운지 포장에 추가한 같은 석식. ROOM/IRD는 모델 분류이며 실제 호텔 회계 확인 아님"),
)

TRUTH_VISITED: dict[str, str] = {
    "HOTEL_GATE": "◎ 워커힐 호텔 정문에 도착해 도어맨과 셔틀을 이용함",
    "DOUGLAS_LOBBY": "◎ 더글라스 하우스 로비에서 체크인 수속을 밟음",
    "DOUGLAS_ROOM": "◎ 디럭스 룸 투숙. 라운지 포장 음식과 와인을 객실에서 먹고 룸서비스 소갈빗살 스테이크 추가 주문 (2026-10-16 원문 대조)",
    "DOUGLAS_LOUNGE": "◎ 더글라스 아워 뷔페를 투고로 이용함"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
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
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "더글라스 가든(산책로)": "산책로를 걸으며 이용함",
    "객실 룸서비스": "◎ 라운지 포장 식사에 소갈빗살 스테이크 룸서비스 추가 주문. 모델에 별도 주문 행동이 없어 관찰 보조 기록으로 남김; 별도 업장·추가 석식으로 채점하지 않음 (2026-10-16 원문 대조)"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('HOTEL_GATE', 'DOUGLAS_LOBBY', '◎ 정문에서 셔틀을 타고 더글라스 하우스 로비로 이동'), ('DOUGLAS_LOBBY', 'DOUGLAS_ROOM', '◎ 체크인 후 객실로 이동'), ('DOUGLAS_ROOM', 'DOUGLAS_LOUNGE', '◎ 객실에서 대화 후 저녁 라운지로 이동')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'DOUGLAS_LOUNGE', '◎ 라운지 포장 음식과 와인을 객실에서 먹고 룸서비스 스테이크 추가 주문. 같은 석식의 추가 음식이며 두 번째 끼니로 세지 않음 (2026-10-16 원문 대조)')]
