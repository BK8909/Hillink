"""
blog54 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog54.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 54
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 7, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 대망의 첫번째 호텔 그랜드 워커힐 서울, 그랜드 객실 리버뷰",
    "nights": "○ 체크인 후 저녁·아침 풍경을 객실에서 봄 → 1박 추정",
    "party": "○ '저희는' 실내수영장 이용, 트윈 침대 셀렉 → 2인 추정",
    "included_meals": "◎ 포함 끼니 언급 없음 (무료 미니바만)",
    "room_minimal": "◎ 리버뷰 보며 객실에 오래 머물고 와인·치즈, 수영장·헬스장도 이용",
    "arrival": "◎ 자차로 와서 주차탑 지하층에 직접 주차, 호텔 입구와 연결"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, '◎ 트윈을 골랐지만 청소가 덜 됐다는 말에 빨리 들어가고 싶어서 더블베드로 바꿈'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, '○ 가장 마음에 든 건 리버뷰, 다시 오면 역시 리버뷰 객실을 선택하겠다고 함'),
    '새로움 추구': (0.75, "○ 서울 호텔을 '섭렵하고 있다'며 일부러 새 호텔을 찾아다님"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (체크인 때 로비가 붐볐다는 묘사만)'),
}

PERSONA = Persona(
    name='[자동] blog54 · 그랜드 리버뷰 1박 · 2인 · 자차 (본문 앞 외부 빵집 글은 오는 길)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "PARKING_TOWER_B1": "○ 주차탑 호텔 연결층(후기는 지하3층이라 적음)에 주차하고 호텔 입구로 들어감",
    "GRAND_FRONT_DESK": "◎ 대기표를 뽑고 기다렸다가 직원에게 체크인",
    "GRAND_ROOM": "◎ 리버뷰 객실에 숙박, 미니바·정수기 이용, 빵·와인 먹으며 뷰 감상",
    "GRAND_POOL": "◎ 객실에서 이동해 지하2층 실내수영장 이용",
    "FITNESS": "◎ 헬스장도 이용"
}
TRUTH_PASSED: dict[str, str] = {
    "CU_THEATRE": "주차장에서 엘리베이터 가는 길에 CU 편의점이 보였다는 언급만",
    "GRAND_LOBBY": "◎ 엘리베이터로 로비 1층에 올라가 체크인 대기",
    "RIVERPARK": "객실 창으로 실외 수영장이 보이고 입장료·운영기간 안내만",
    "THE_BUFFET": "뷔페가 있는 곳 앞 로비 소파와 역사 공간을 구경",
    "THE_PAVILION": "○ 객실로 돌아오는 길에 본 로비 카페",
    "HOTEL_GATE": "○ '이곳이 워커힐 입구' 사진만"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "외부 빵집(호텔 밖, 오는 길)": "◎ 호텔 오는 길에 빵을 사 와서 객실에서 먹음 — 호텔 밖이라 코드 없음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('PARKING_TOWER_B1', 'GRAND_FRONT_DESK', '◎ 주차 후 연결 입구 → 엘리베이터로 로비 1층 체크인'), ('GRAND_FRONT_DESK', 'GRAND_ROOM', '◎ 체크인 후 객실 입실'), ('GRAND_ROOM', 'GRAND_POOL', '◎ 객실에서 이동해 지하2층 수영장')]
TRUTH_MEALS: list[tuple[str, str, str]] = []
