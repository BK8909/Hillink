"""
blog40 — 정답 확인본 (소연). 자동 추출 초안 persona_blog40_auto.py 를 원문 r058 과 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 개발용

정답 확인: 소연 · 13분 · 보류 2건

고친 것 둘.
  · 시작 날짜 — 초안은 글 작성일(2026-09-08)인데 원문 첫 줄에 "2024년 2월 … <비스타 워커힐
    서울 더뷔페> 방문" 이 적혀 있다. 2024-02 로 옮겼다. 일자는 없어 15일로 두었다(보류)
  · 끼니 — 초안은 석식으로 넣고 근거를 마름모로 달았는데 설명은 "끼니는 후기에 없음 → 석식은 △ 추정"
    이었다. 규칙 4 는 시간대 표현이 없으면 적지 않는 것이라 뺐다 (보류)

그대로 둔 것
  · 글 뒤쪽의 다른 식당(호텔 밖 한식 다이닝)은 장소 목록 밖이라 넣지 않았다. 초안도 같다
  · 예약은 booked 에 그대로 뒀다 — "1월에 예약하고 2월에 방문", 네이버 예약 선결제라
    방문 목적의 식당 예약이 맞다

보류: 시작 날짜의 일자 — "2024년 2월" 만 있다. 2월 15일로 두었지만 근거는 월까지다
보류: TRUTH_MEALS — 식사를 한 것은 분명한데(수프 · 대게 · 딸기 · QR 커피) 시간대 표현이 없어
      규칙 4 대로 비웠다. 1인 17만 원대 결제라 디너 가격대로 볼 여지는 있지만 원문 근거는 아니다.
      "식사한 건 분명한데 끼니를 못 정하는" 경우를 어떻게 셀지 기준이 있으면 좋겠다

한 체류인가 (체크리스트 0장 · 규칙 2) — 한 글 안에 **다른 날의 방문 둘**이 들어 있다.
2024년 2월 더뷔페와 2024년 10월의 다른 식당이다. 앞의 워커힐 방문만 다루고 뒤는 넣지 않았다
(뒤는 호텔 밖 식당이기도 하다). 초안도 이름에 "2024년 2월 방문분" 이라고 적어 같게 골랐다.

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2024, 2, 15, 17, 0)      # 날짜 ◎ 원문 첫 줄 '2024년 2월 … <비스타 워커힐 서울 더뷔페> 방문' · 일자는 없음(보류) · 시각 △

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 1층 더뷔페 방문 (숙박 없음)",
    "nights": "◎ 식사만 하러 방문",
    "party": "◎ 2인 예약·선결제, 동행자 1명과 방문",
    "included_meals": "◎ 숙박 패키지 없음",
    "room_minimal": "비투숙이라 해당 없음",
    "booked": "◎ '인기가 많아서 1월에 예약하고 2월에 방문' · 네이버 예약 할인으로 2인 선결제",
    "start_time": "△ 끼니·시각이 적혀 있지 않음 → 석식 추정, 이용 30분 전",
    "depart_by": "△ 석식 이용 끝 무렵 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, '○ 인기가 많아서 한 달 전에 미리 예약하고 방문'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.75, '○ 동행자에게 좋은 곳에서 식사하는 경험을 주려고 호텔 뷔페를 골라 예약, 이후 파인다이닝도 일부러 예약'),
    '조망 중시': (0.5, '○ 운 좋게 창가 자리에 앉아 더 행복하게 식사했다 — 좋았다 정도'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (같이 먹었다는 사실만)'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog40 · 비투숙 · 더뷔페 식사 2인 (2024년 2월 방문분 — 뒤의 외부 한식 다이닝 방문은 제외)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival=None,
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 동행자와 더뷔페에서 식사 — 수프, 대게, 딸기, QR 주문 커피"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
# 규칙 4 — 시간대 표현이 원문에 없어 끼니를 적지 않았다 (보류)
TRUTH_MEALS: list[tuple[str, str, str]] = []
