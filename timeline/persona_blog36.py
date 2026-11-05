"""
blog36 — 정답 확인본 (소연). 자동 추출 초안 persona_blog36_auto.py 를 원문 r037 과 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 개발용

정답 확인: 소연 · 11분 · 보류 1건

초안이 정확했다. 고친 것은 하나다.
  · 프런트 — 방문에서 지나감으로. "체크인해서 조금 쉬다가" 한 줄뿐이고 그 자리에서 일어난 일이
    적혀 있지 않다 (규칙 1 — 체크인했다는 한 줄만으로는 방문이 아니다)

확인한 것
  · 룸서비스 피자와 LUX 바 와인은 끼니에 넣지 않았다 (규칙 4 — 룸서비스 제외 · 음료는 끼니 아님).
    초안도 같게 처리해 두었다
  · 헬스장은 그랜드 투숙이라 노드 FITNESS(그랜드 지하 2층)와 건물이 맞다.
    1차 blog16 · 19 처럼 비스타 시설을 그랜드 노드로 적은 경우가 아니다

보류: facts.arrival — "체크인한 뒤에 다시 차 타고 나갈 필요 없이" 로 자차인 건 보이지만 발렛인지
      직접 주차인지 없다. 초안대로 None 으로 두었다

10/11 원문 재대조 — property 근거의 "딜럭스 한강뷰 객실" 은 원문에 없다 (초안이 붙인 말). 원문은
  객실 이름 · 건물을 적지 않았고 "2차는 호텔 16층 LUX BAR" · "호텔 위에 있는 바에 가기로. 우리가 간 곳은
  그랜드 워커힐 서울 16층 LUX BAR" 라 그랜드 투숙으로 본다 (○). 이름표에서도 뺐다

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 1, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "○ 객실 이름 · 건물은 안 적힘 — '2차는 호텔 16층 LUX BAR' · '호텔 위에 있는 바' 가 그랜드 워커힐 서울 16층이라 그랜드 투숙",
    "nights": "◎ '같이 하루 자고 오기로', '짧은 1박'",
    "party": "◎ 작성자와 동행자 3명 · ○ 모두 성인으로 추론 (함께 와인·바 이용, 아이 동반 언급 없음)",
    "included_meals": "○ 끼니 포함 언급 없음",
    "booked": "◎ '저녁은 워커힐 명월관으로 예약했다'",
    "arrival": "○ '체크인한 뒤에 다시 차 타고 나갈 필요 없이' — 차로 온 것으로 보이나 발렛/직접 주차 구분 없음",
    "room_minimal": "◎ 체크인 후 객실에서 쉬고, 밤에 객실에서 와인·룸서비스"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.75, "◎ '다시 차 타고 나갈 필요 없이 ... 다 안에서 해결할 수 있는 게 좋았다' · 명월관 후 '밖으로 이동할 필요도 없고 그냥 엘리베이터 타고 올라와서' 바로 LUX 바 — 동선을 이유로 일정 구성"),
    '격식 선호': (None, '근거 없음 → 미상 (명월관은 동행자 제안)'),
    '조망 중시': (0.5, "○ LUX 바 '창가 쪽은 정말 야경이 다했다' — 좋았다 수준"),
    '새로움 추구': (0.25, "◎ '다시 간다고 해도 ... 코스는 또 그대로 할 것 같다' — 같은 코스 반복 선호"),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (함께 먹었다는 사실뿐)'),
    '조용함 선호': (0.75, "◎ '너무 시끄럽지 않고 오래 이야기할 수 있는 곳이 좋은데 명월관이 그런 면에서는 잘 맞았다' · 분위기가 차분해서 마음에 듦"),
}

PERSONA = Persona(
    name='blog36 · 그랜드 1박 · 4인(성인) · 기념일 · 명월관→LUX 바',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('MYONGWOLGWAN',),
    arrival=None,
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 체크인 후 쉬고, 밤에 돌아와 룸서비스 피자와 와인",
    "MYONGWOLGWAN": "◎ 저녁을 명월관에서 한우 숯불구이로 먹음",
    "LUX_BAR": "◎ 명월관 후 16층 LUX 바에서 와인 한 병, 재즈 라이브",
    "FITNESS": "◎ 다음 날 아침 헬스장에서 운동"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_FRONT_DESK": "'체크인해서 조금 쉬다가' 한 줄뿐 — 그 자리에서 일어난 일이 없다 (규칙 1)",
    "ANNEX": "○ 명월관이 본관이 아닌 별관에 있어 그리로 감"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GOLF_CLUB": "○ 언급 없음 ('골프도 가능' 안내만)",
    "GRAND_POOL": "○ 언급 없음 ('운동 or 수영' 추천만)",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음 (피자는 룸서비스)",
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
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['MYONGWOLGWAN'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'MYONGWOLGWAN', "◎ '체크인해서 조금 쉬다가 저녁은 명월관'"), ('MYONGWOLGWAN', 'LUX_BAR', '◎ 명월관 저녁 후 바로 LUX 바'), ('LUX_BAR', 'FITNESS', '◎ LUX 바 → 객실 룸서비스 → 다음 날 아침 헬스장')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'MYONGWOLGWAN', '◎ 명월관에서 한우 숯불구이 저녁')]
