"""
blog15 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 텍스트 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2 — v4 계수 확정(fit_v4_result.json) 뒤에 만든 후기. 사람은 정답만 원문과 대조
손으로 만든 persona_blog15.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 15
시험용(held-out) 후기 2 — v4 계수 확정 뒤 봉인. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2023, 8, 28, 14, 30)      # △(추정)

FACTS_EVIDENCE = {
    "property": "△ 건물(그랜드/비스타/더글라스) 언급 없음, 기본값으로 추정",
    "nights": "◎ '다음날 체크아웃하고 먹은 팥빙수'로 1박 확인",
    "party": "△ 아이 기념일로 방문, 동행자와 함께한 것으로 보이나 정확한 인원 언급 없음",
    "included_meals": "○ 언급 없음 — 조식 등은 후기에서 '포함'이라고 명시되지 않아 truth.meals로만 처리",
    "room_minimal": "○ 객실 등급/미니멀룸 관련 언급 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.2, '○ 피자 포장, 망고빙수·팥빙수 등 캐주얼한 음식 위주로 즐겼고 코스·정찬 언급은 없음'),
    '조망 중시': (None, '근거 없음 → 미상'),
    '새로움 추구': (0.7, '○ 1박이라는 짧은 일정 동안 키즈클럽·수영장·피자힐·빙수(2회)·조식 등 다양한 시설을 두루 이용'),
    '함께 먹기 선호': (None, '일행과 함께 먹었다는 서술 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog15 · 워커힐 1박 · 아이 동반 호캉스',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=True,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ '주문 후 가지러갔다가 룸에서 먹었네요'로 객실 체류 확인",
    "GRAND_POOL": "△ '워커힐도 수영장이 있어... 유아풀이 생각보다 작지만... 아이가 들어가 놀기엔 괜찮았습니다'로 실내 수영장 이용 확인, 구체 동(棟)은 property 추정에 따름",
    "PIZZA_HILL": "◎ '피자힐에서 시켜먹은 피자는 맛있었어요... 주문 후 가지러갔다가'로 직접 방문·픽업 확인"
}
TRUTH_PASSED: dict[str, str] = {
    "THE_PAVILION": "△ '워커힐 하면 유명한 망고빙수', 체크아웃 후 먹은 팥빙수 — 워커힐 명물 빙수 판매처로 통상 더파빌리온을 추정(구체 상호 언급 없음) — [봉인 확인] 이용은 했지만 장소가 추정(△)이라 채점에서 뺌",
    "THE_BUFFET": "△ '조식! 생각보다 먹을게 많았고... 만족도 높았어요' — 조식 장소 구체 언급 없어 더뷔페로 추정 — [봉인 확인] 이용은 했지만 장소가 추정(△)이라 채점에서 뺌"
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
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
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
    "PARKING_TOWER_B1": "○ 언급 없음",
    "RIVERPARK": "◎ '좀더 큰 아이들이 있다면... 야외수영장 오픈하는 날짜 맞춰 가는게 좋을듯해요'로 야외수영장은 이용하지 않은 것으로 읽힘",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "키즈클럽": "○ '볼풀장, 주방놀이, 자동차, 책, 미끄럼틀' 등을 갖춘 키즈클럽을 아이와 함께 이용한 것으로 서술"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_POOL', 'PIZZA_HILL', '○ 수영장 이야기 다음에 피자힐 주문 이야기가 이어짐'), ('PIZZA_HILL', 'THE_PAVILION', '○ 피자를 먹은 이야기 다음에 망고빙수 이야기가 이어짐'), ('THE_PAVILION', 'THE_BUFFET', '○ 1일차 망고빙수(더파빌리온 첫 방문) 이후 다음날 조식을 먹음')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '△ 피자힐에서 피자를 사서 룸에서 먹음(식사 시간대 불명, 석식으로 추정)')]
