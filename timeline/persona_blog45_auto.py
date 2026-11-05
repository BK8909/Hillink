"""
blog45 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog45.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 45
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 29, 14, 30)      # 날짜 ◎ 후기 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 디럭스 리버뷰 5층 킹",
    "nights": "◎ 26.8.29-30",
    "party": "○ '우리가 방문했을 때' — 2인 추정, 아이 언급 없음",
    "included_meals": "○ 조식 포함 여부 언급 없음 → 비움",
    "booked": "◎ 더뷔페 조식을 QR 온라인으로 전날 예약 (창가 자리 배정)",
    "arrival": "○ 도착 수단 언급 없음 (셔틀 안내는 일반 정보)",
    "room_minimal": "◎ 피로로 '룸콕만 했다' — 객실 체류 많음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, "◎ 조식 예약으로 '줄을 서지 않으니 복잡하지 않고 더 낫다' · 줄 서서 기다릴 필요 없어 좋다 — 예약으로 대기를 피함"),
    '이동 최소화': (None, '근거 없음 → 미상 (셔틀로 피자힐 왕복, 이동 불만 없음)'),
    '격식 선호': (0.25, '◎ 더뷔페 석식은 비싸고 과식하게 돼서 피자힐 피자 포장을 골라 먹음'),
    '조망 중시': (0.75, '◎ 빨리 예약할수록 창가 자리 가능성 높다며 QR 예약으로 창가 자리를 얻음 · 객실 창 아래 불투명해 풍경 못 보는 걸 단점으로 적음'),
    '새로움 추구': (None, '근거 없음 → 미상 (여러 번 온 재방문객, 이번엔 피로로 룸콕)'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.75, '◎ 사람 붐비지 않을 때 여유롭게 먹으려고 조식 1부 선택 · 스카이야드도 사람 적은 일요일 아침에 가려 함'),
}

PERSONA = Persona(
    name='[자동] blog45 · 비스타 디럭스 리버뷰 1박 · 2인 · 피자힐 포장 석식 + 더뷔페 조식 1부',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_ROOM": "◎ 디럭스 리버뷰 객실 숙박, 무료 미니바 이용, 룸콕",
    "PIZZA_HILL": "◎ 룸에서 QR 테이크아웃 주문 후 구내 셔틀로 가서 콤비·불고기 피자·해산물 샐러드 포장",
    "THE_BUFFET": "◎ 다음날 6시 30분 조식 1부 입장, 창가 자리에서 식사",
    "FITNESS": "◎ '유일하게 이용했던 피트니스클럽' — 핸드폰은 로커에 두고 이용"
}
TRUTH_PASSED: dict[str, str] = {
    "VISTA_LOBBY": "○ 호텔 메인 입구 정거장에서 모니터로 구내 셔틀 호출 (피자힐 왕복)",
    "CU_THEATRE": "○ 칫솔 등 없으면 호텔 내 편의점에서 사면 된다는 언급만",
    "FOREST_PARK": "○ 맥주 축제로 북적이는 것을 봤다는 언급만",
    "RIVERPARK": "○ 방문자들로 북적였다는 언급만",
    "GANGBYEON_STN": "○ 셔틀 안내로만 언급",
    "GWANGNARU_STN": "○ 셔틀 안내로만 언급"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "SKYARD": "◎ 일요일 아침에 가려 했으나 날이 흐려 이용 안 함",
    "VISTA_POOL": "◎ 부대시설 중 피트니스만 이용했다고 적음",
    "WELLNESS_SAUNA": "◎ 부대시설 중 피트니스만 이용했다고 적음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'PIZZA_HILL', '◎ 룸에서 QR 주문 후 30분 뒤 찾으러 감'), ('PIZZA_HILL', 'THE_BUFFET', '◎ 첫날 저녁 피자힐 포장, 다음날 아침 조식'), ('VISTA_ROOM', 'THE_BUFFET', '◎ 첫날 입실, 다음날 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 저녁 식사로 피자힐 피자·샐러드 포장'), ('조식', 'THE_BUFFET', '◎ 1부 06:30 입장 조식')]
