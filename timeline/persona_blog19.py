"""
blog19 — 정답 확인본 (소연). 자동 추출 초안 persona_blog19_auto.py 를 원문 r010 과 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용

정답 확인: 소연 · 9/28 · 14분 · 보류 1건

초안이 정확한 편이었다. 고친 건 **건물이 다른 노드 둘**과 순서 쌍뿐이다.

9/29 — 보류 두 건을 풀었다 (검증기 결정)
  · 피트니스 → VISTA_FITNESS 로 방문. 검증기에 비스타 웰니스 클럽 체련장 노드를 새로 넣었다.
    원문 "3층 웰니스 센터 - 피트니스 클럽, 수영장" 그대로다
  · 라이브러리 → GRAND_LIBRARY 로 방문. **1차의 내 판단이 틀렸다.** 원문이 이미 공식 이름
    "2층 워커힐 라이브러리" 를 쓰고 있었고, 그랜드 투숙 blog25 의 "워커힐 서울 2층에 라이브러리" 와
    같은 곳이다. 비스타 라이브러리가 따로 있다는 근거는 원문 · 회사 문서 어디에도 없다.
    (이 원문은 "로비 2층" 이 어느 건물 로비인지 적지 않았다. 다만 라이브러리를 하나로 두었으니 몰라도 된다)

보류: PARKING_TOWER_B1 — 원문은 "지하 3층에 주차하면 연결 통로" 인데 노드는 B1(호텔 연결층)이다.
      층이 다르지만 '연결층' 역할이 같아 그대로 뒀다. 비스타 연결층 노드가 필요한지 팀 확인

※ 추출기가 같은 상황을 다르게 처리한다 — 조식 1부 예약을 이 초안은 "투숙 첫날 현장에서 한 것이라 예약 시점 사실에서 제외" 하며
  booked 에서 뺐는데, 다른 초안(blog16)은 THE_BUFFET 을 booked 에 넣었다. 기준을 하나로 정해야 한다.
  booked 는 에이전트에서 +8 이라 동선이 달라진다. 양쪽 다 초안 값을 그대로 두었다.
  (이 메모는 blog16 쪽 파일에는 적지 않았다 — 공통 후기라, 아직 안 끝낸 사람에게 힌트가 될 수 있어서)

10/11 — 시작 날짜를 8/31 → 8/30 으로 고쳤다 (원문 재대조). 원문이 "저희는 어제 1부로 예약을 했습니다.
  토, 일, 월, 공휴일은 사전 예약제를 운영하고 있답니다" 라 조식 날은 1부가 있는 날이다. 9/29 에 채운
  작성일 8/31 체크인이면 조식이 9/1(화)인데 그날은 1부가 없다 (평일 07:00~10:00 · 2026 여름 매일 1부는
  8/31 까지). 체크리스트 시기 규칙 ("일요일" → 작성일 직전 일요일) 처럼 작성일 직전으로 — 8/30(일)
  체크인 · 8/31(월) 조식 1부

성향(TRAIT_EVIDENCE)은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 30, 14, 30)      # 날짜 ○ '어제 1부로 예약' → 조식 날에 1부가 있어야 해 작성일(8/31) 직전 8/30 체크인 (소연 10/11 · 9/29 엔 작성일 8/31) · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 호캉스 후기, 비스타 디럭스 트윈룸 배정",
    "nights": "◎ 호캉스 1박 2일",
    "party": "◎ 작성자와 동행자 1명(2인), 아이 언급 없음",
    "included_meals": "◎ 조식은 투숙객 할인가로 따로 결제 → 포함 아님",
    "booked": "○ 조식 1부 예약은 투숙 첫날 현장에서 한 것이라 예약 시점 사실에서 제외",
    "arrival": "◎ 발렛 가능했지만 그냥 주차타워에 직접 주차",
    "room_minimal": "◎ 객실 음료·커피머신 이용, 체크아웃 전 객실에서 커피 마시고 마무리"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, '◎ 조식을 1부로 미리 예약, 2부는 대기줄이 엄청나니 피곤해도 1부를 권함 (○ 피자 포장 대기는 뷰 감상하며 감수)'),
    '이동 최소화': (None, '근거 없음 → 미상 (셔틀로 피자힐 이동했으나 거리에 대한 선호 언급 없음)'),
    '격식 선호': (0.25, '◎ 피자힐에서 매장 식사 대신 숙소로 포장해 가기로 선택'),
    '조망 중시': (0.5, '◎ 리버뷰 객실·스카이야드 한강 야경·조식 한강뷰를 좋았다고 적음, 뷰 때문에 고른 문장은 없음'),
    '새로움 추구': (0.75, "◎ '1박 2일은 부대시설 이용해야 해서 바쁘죠'라며 바로 웰니스센터로 감, 유명하다는 피자힐·도서관이 있다고 해서 일부러 찾아감"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (체크인 대기 인파 묘사만 있음)'),
}

PERSONA = Persona(
    name='blog19 · 비스타 1박 · 2인',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "PARKING_TOWER_B1": "○ 주차타워에 주차, 지하 연결 통로로 비스타 접근",
    "VISTA_LOBBY": "◎ 로비 키오스크로 체크인 대기, 로비에서 무료 셔틀 이용",
    "VISTA_ROOM": "◎ 11층 디럭스 트윈룸 투숙, 체크아웃 전 객실에서 커피",
    "VISTA_POOL": "◎ 수영장 레인에서 수영",
    "PIZZA_HILL": "◎ 셔틀 타고 피자힐 가서 콤비네이션 피자 포장",
    "SKYARD": "◎ 늦은 저녁 뒤 문 닫기 30분 전에 스카이야드 족욕",
    "THE_BUFFET": "◎ 다음날 아침 더뷔페 조식 1부 식사",
    "VISTA_FITNESS": "◎ '3층 웰니스 센터 - 피트니스 클럽, 수영장 … 바로 옷 갈아입고' 이용, 기구 다양·트레이너 상주",
    "GRAND_LIBRARY": "◎ '2층 워커힐 라이브러리 로비 2층에 도서관이 있다고 해서 가보았어요' — 소파에서 쉼",
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VALET_DESK": "◎ 발렛 가능했지만 그냥 주차타워에 주차",
    "MYONGWOLGWAN": "○ 셔틀로 갈 수 있다는 언급만",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ('VISTA_ROOM', 'VISTA_POOL', '◎ 객실에서 바로 옷 갈아입고 웰니스센터로'),
    ('VISTA_POOL', 'PIZZA_HILL', '◎ 운동했으니 밥 먹으러 피자힐'),
    # 9/29 — 피트니스가 방문이 되어 초안에 있던 ◎ 쌍 둘을 되살렸다 (노드가 없어서 빠졌던 것).
    # 초안의 '조식 뒤 도서관' 은 ○ 이고 원문이 앞뒤를 말하지 않아 규칙 3 대로 넣지 않았다
    ('VISTA_ROOM', 'VISTA_FITNESS', '◎ 객실에서 바로 옷 갈아입고 웰니스센터(피트니스 클럽 · 수영장)로'),
    ('VISTA_FITNESS', 'PIZZA_HILL', '◎ \'운동했으니 밥먹어야겠죠\' — 피자힐'),
    ('PIZZA_HILL', 'SKYARD', '◎ 늦은 저녁 먹고 스카이야드'),
    ('SKYARD', 'THE_BUFFET', '◎ 자기 전 스카이야드, 다음날 아침 조식'),
]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 늦은 저녁으로 피자힐 피자 포장해 숙소에서 먹음'), ('조식', 'THE_BUFFET', '◎ 더뷔페 조식 1부')]
