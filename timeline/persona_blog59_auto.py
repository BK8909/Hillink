"""
blog59 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog59.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 59
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 31, 14, 0)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 여름휴가로 비스타 워커힐 서울에서 1박, 스파 디럭스 한강전망 객실",
    "nights": "◎ 1박이라고 적음",
    "party": "◎ 어른 둘과 아이 셋이 모두 수영복 입고 스파 욕조에 들어감 · 아이 동반",
    "included_meals": "◎ 객실+조식+리버파크 포함 패키지로 예약 · 리버파크 2부에 세미뷔페(18:15-20:00) 포함",
    "room_minimal": "◎ 객실 스파 욕조에서 아이 물놀이, 객실 커피·미니바 이용 등 객실 체류 시간이 있음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, '○ 세미뷔페 줄을 늦게 서서 음식 뜨기까지 한참 걸렸지만 담담히 적음 · 비대면 체크아웃으로 줄 안 서서 편했다고 함'),
    '이동 최소화': (0.5, '○ 리버파크까지 산길이라 걸어가지 않고 셔틀을 타고 편하게 이동 · 그 외 이동을 이유로 계획을 바꾼 문장은 없음'),
    '격식 선호': (0.25, '○ 더파빌리온 가격에 놀라 부담스러웠다고 하고, 쉬어갈 곳이면 더 저렴한 빛의 라운지를 고르겠다고 밝힘 · 리버파크에서 떡볶이 주문'),
    '조망 중시': (0.75, "◎ 조식 예약 때 특이사항에 '창가자리'를 요청 · 한강전망 객실 선택, 빛의 라운지를 한강뷰 때문에 추천"),
    '새로움 추구': (0.75, "○ 체크인 전 워커힐을 둘러보다 더파빌리온 방문, '여름휴가로 왔으니 이것도 하나의 경험' 이라며 시그니처 빙수 주문 · 다음엔 호텔 내부도 둘러보는 일정으로 잡겠다고 함"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (스파 욕조는 다른 사람 신경 안 써도 된다는 언급뿐, 공용 수영장을 피한 이유는 아이 감염 걱정)'),
}

PERSONA = Persona(
    name='[자동] blog59 · 비스타 1박 · 동행자+아이 3인 · 객실+조식+리버파크 패키지',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=3,
    has_child_under_13=True,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'), ('석식', 'RIVERPARK')),
    booked=('RIVERPARK',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_PAVILION": "◎ 체크인 전 잠깐 쉬려고 방문해 시그니처 빙수를 주문해 먹음",
    "VISTA_LOBBY": "◎ 리버파크 키트 수령 때문에 로비에서 직원과 대면 체크인",
    "VISTA_ROOM": "◎ 오후 2시쯤 입실, 스파 디럭스 한강전망 객실에서 1박",
    "RIVERPARK": "◎ 체크인 후 15시부터 리버파크 2부 이용, 떡볶이 주문·세미뷔페 식사",
    "THE_BUFFET": "◎ 월요일 조식 2부, 오전 9시쯤 대기 없이 입장해 식사"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ 더파빌리온이 있는 그랜드 1층 로비를 거쳐 감"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VISTA_POOL": "◎ 리버파크에 오래 있어 다른 부대시설 이용할 시간이 거의 없었다고 적음",
    "GRAND_POOL": "◎ 리버파크에 오래 있어 다른 부대시설 이용할 시간이 거의 없었다고 적음",
    "SKYARD": "◎ 리버파크에 오래 있어 다른 부대시설 이용할 시간이 거의 없었다고 적음",
    "THEATRE_OF_LIGHT": "◎ 우천 대체 혜택으로만 언급, 비가 안 와 리버파크 이용",
    "PIZZA_HILL": "○ 세미뷔페 피자가 피자힐 피자라는 언급뿐, 방문 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 라운지": "○ 더파빌리온보다 가격 부담이 적고 한강뷰가 멋졌다고 비교 — 이용 경험으로 보이나 이번 체류 중인지는 불명"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('THE_PAVILION', 'VISTA_ROOM', '◎ 체크인 전 더파빌리온에 들른 뒤 입실'), ('VISTA_LOBBY', 'VISTA_ROOM', '○ 로비에서 대면 체크인 후 객실 입실'), ('VISTA_ROOM', 'RIVERPARK', '◎ 객실에서 수영복으로 갈아입고 15시부터 리버파크 이용'), ('RIVERPARK', 'THE_BUFFET', '◎ 리버파크는 첫날, 조식은 다음 날 아침')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'THE_PAVILION', '◎ 체크인 전 시그니처 빙수와 호두곶감말이'), ('간식', 'RIVERPARK', '◎ 저녁 전 배고파 QR로 떡볶이 주문'), ('석식', 'RIVERPARK', '◎ 리버파크 2부 세미뷔페에서 저녁'), ('조식', 'THE_BUFFET', '◎ 다음 날 더뷔페 조식 2부')]
