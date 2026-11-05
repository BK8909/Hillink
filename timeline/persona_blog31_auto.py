"""
blog31 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog31.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 31
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 10, 15, 30)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐 서울 디럭스 리버뷰 객실",
    "nights": "○ 체크인 후 다음 날 아침 조식 → 1박",
    "party": "◎ 동행자와 둘이 투숙, 동반 아동 없음",
    "included_meals": "○ 포함 끼니 언급 없음",
    "room_minimal": "◎ 객실에서 낮잠 자고 쉬다가 저녁 먹으러 감",
    "arrival": "○ 주차타워 지하 3층이 호텔 지하 1층과 연결돼 이동이 편하다고 적음 → 주차타워 직접 주차",
    "start_time": "◎ '체크인 15:30' 표기 (체크인 전 라운지에서 대기)"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.25, '◎ 체크인을 기다리면서 로비 라운지에서 애프터눈티를 즐김'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (더뷔페가 방문 목적이지만 코스·정찬은 아님)'),
    '조망 중시': (0.5, "◎ '한강이 보이는 뷰' 좋았다 정도"),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog31 · 그랜드 1박 · 2인 (더뷔페 디너 목적)',
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
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_PAVILION": "◎ 체크인을 기다리며 라운지(파빌리온)에서 애프터눈티",
    "GRAND_FRONT_DESK": "○ '드디어 체크인'",
    "GRAND_ROOM": "◎ 디럭스 리버뷰 객실, 낮잠·휴식",
    "THE_BUFFET": "◎ 저녁 더뷔페 식사, 디저트까지 · 다음 날 조식(○)"
}
TRUTH_PASSED: dict[str, str] = {
    "PARKING_TOWER_B1": "○ 주차타워에서 호텔 지하 1층으로 연결 이동",
    "GRAND_LOBBY": "○ 저녁 후 호텔 한 바퀴 산책"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('THE_PAVILION', 'GRAND_ROOM', '◎ 체크인 기다리며 애프터눈티 → 드디어 체크인'), ('GRAND_ROOM', 'THE_BUFFET', '◎ 방에서 낮잠 자고 쉬다가 저녁 먹으러 더뷔페')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'THE_PAVILION', '◎ 체크인 전 애프터눈티'), ('석식', 'THE_BUFFET', '◎ 저녁 더뷔페'), ('조식', 'THE_BUFFET', '○ 다음 날 해 뜨자마자 조식 (장소 미기재, 더뷔페 추정)')]
