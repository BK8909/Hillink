"""
blog49 — 한호 정답 확인
정답 확인: 한호 · 9/29 · 보류 없음 (정확한 인원·포레스트파크 활동은 원문상 미상; 방문은 확인)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
9/28 자동 초안을 원문 r045와 대조했다. 성향(TRAIT_EVIDENCE)은 자동 초안 그대로 두었다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 2, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 12층 디럭스 트윈, 아차산 숲뷰",
    "nights": "○ '두번째 날에는 조식' → 1박 추정",
    "party": "△ '저희'와 동행 언급으로 최소 2명, 정확한 인원은 명시되지 않음",
    "included_meals": "◎ 조식 포함 여부 언급 없음",
    "room_minimal": "○ 객실·미니바 소개 외에 라이브러리·포레스트파크·한강 등 여러 곳 이용",
    "arrival": "◎ 차를 가져왔다고 적었으나 발렛/직접 주차 여부 없음 → null"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.25, '◎ 조식 2부 오픈런으로 10분쯤 먼저 가서 기다렸고, 덕분에 예쁜 자리에 앉았다고 긍정적으로 적음'),
    '이동 최소화': (0.25, '○ 셔틀을 불러 포레스트파크까지 가고, 셔틀버스로 역 주변까지 놀러 다님'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, '◎ 통창뷰를 놓칠 수 없어서 조식 2부 오픈런에 도전'),
    '새로움 추구': (0.75, '○ 포레스트파크에 가 보고 싶어서 셔틀 콜을 신청해 찾아감'),
    '함께 먹기 선호': (0.75, '○ 차를 가져왔지만 동행자와 같이 맥주 한 잔 하려고 셔틀·대중교통으로 다님'),
    '조용함 선호': (None, '근거 없음 → 미상 (한강·라이브러리가 조용해서 좋았다는 묘사만)'),
}

PERSONA = Persona(
    name='[확인 초안] blog49 · 그랜드 디럭스 트윈 1박 · 조식 오픈런',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,  # △ 확인 가능한 최소 인원만 실행용으로 유지; 정확한 인원 미상
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
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 12층 디럭스 트윈 객실 숙박, 무료 미니바 이용",
    "THE_BUFFET": "◎ 둘째 날 더뷔페 2부 조식, 오믈렛·카페라떼 주문",
    "GRAND_LIBRARY": "◎ 객실카드를 찍고 라이브러리에 입장해 좌석·책을 둘러봄",
    "FOREST_PARK": "○ 셔틀을 불러 포레스트파크로 이동하고 놀이 용품·카페를 묘사 (활동 이용은 미상)"
}
TRUTH_PASSED: dict[str, str] = {
    "HOTEL_GATE": "◎ 호텔 정문에서 내부 셔틀을 호출해 포레스트파크로 이동 — 정문은 항상 통과"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'THE_BUFFET', '○ 첫날 객실 투숙, 둘째 날 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '◎ 둘째 날 더뷔페 2부 조식')]

