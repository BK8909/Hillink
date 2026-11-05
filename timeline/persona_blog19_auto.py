"""
blog19 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog19.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 19
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

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
    '새로움 추구': (0.75, "◎ '1박 2일은 부대시설 이용해야 해서 바쁘다'며 바로 웰니스센터로 감, 유명하다는 피자힐·도서관이 있다고 해서 일부러 찾아감"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (체크인 대기 인파 묘사만 있음)'),
}

PERSONA = Persona(
    name='[자동] blog19 · 비스타 1박 · 커플',
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
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "PARKING_TOWER_B1": "○ 주차타워에 주차, 지하 연결 통로로 비스타 접근",
    "VISTA_LOBBY": "◎ 로비 키오스크로 체크인 대기, 로비에서 무료 셔틀 이용",
    "VISTA_ROOM": "◎ 11층 디럭스 트윈룸 투숙, 체크아웃 전 객실에서 커피",
    "FITNESS": "◎ 옷 갈아입고 웰니스센터 피트니스 클럽 이용, 기구 다양",
    "VISTA_POOL": "◎ 수영장 레인에서 수영",
    "PIZZA_HILL": "◎ 셔틀 타고 피자힐 가서 콤비네이션 피자 포장",
    "SKYARD": "◎ 늦은 저녁 뒤 문 닫기 30분 전에 스카이야드 족욕",
    "THE_BUFFET": "◎ 다음날 아침 더뷔페 조식 1부 식사",
    "GRAND_LIBRARY": "◎ 로비 2층 도서관에 가서 소파에서 쉼"
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
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('PARKING_TOWER_B1', 'VISTA_LOBBY', '○ 주차 후 연결 통로로 들어가 체크인'), ('VISTA_LOBBY', 'VISTA_ROOM', '◎ 키오스크 체크인 후 객실 배정'), ('VISTA_ROOM', 'FITNESS', '◎ 객실에서 바로 옷 갈아입고 웰니스센터로'), ('VISTA_ROOM', 'VISTA_POOL', '◎ 객실에서 바로 옷 갈아입고 웰니스센터로'), ('FITNESS', 'PIZZA_HILL', '◎ 운동했으니 밥 먹으러 피자힐'), ('VISTA_POOL', 'PIZZA_HILL', '◎ 운동 후 피자힐'), ('PIZZA_HILL', 'SKYARD', '◎ 늦은 저녁 먹고 스카이야드'), ('SKYARD', 'THE_BUFFET', '◎ 자기 전 스카이야드, 다음날 아침 조식'), ('THE_BUFFET', 'GRAND_LIBRARY', '○ 조식 뒤 도서관, 이후 숙소로 돌아와 체크아웃')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 늦은 저녁으로 피자힐 피자 포장해 숙소에서 먹음'), ('조식', 'THE_BUFFET', '◎ 더뷔페 조식 1부')]
