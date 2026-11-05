"""
blog35 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog35.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 35
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 5, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 디럭스 더블룸 1박 2일 투숙",
    "nights": "◎ 1박 2일",
    "party": "◎ 동행자와 둘이 방문, 아이 동반 언급 없음",
    "included_meals": "○ 포함 끼니 언급 없음 · 조식 글은 '내돈내산' 표기, 투숙객 할인가 안내 → 포함 아님",
    "room_minimal": "◎ 객실 묘사·수면 만족 등 객실에서 시간 보냄",
    "arrival": "◎ 차로 방문해 주차타워에 직접 주차 후 체크인"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상 (조식 오픈 시간 방문은 창가 자리 목적)'),
    '이동 최소화': (0.25, '○ 룸서비스 대신 호텔 밖 식당까지 산책 겸 걸어 내려갔다 옴 · 포레스트파크까지 산길 산책'),
    '격식 선호': (0.25, "○ 룸서비스가 비싸서 '가성비' 있는 근처 캐주얼 양식 식당을 골라서 감"),
    '조망 중시': (0.75, "◎ '어딜 가든 눈이 즐거운 게 좋은 사람' · 조식은 창가(한강뷰) 자리를 위해 오픈 직후 입장, 눈부심도 감수"),
    '새로움 추구': (None, "근거 없음 → 미상 (런치·디너는 '다음에' 희망일 뿐)"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (수영장 한산했다는 묘사뿐)'),
}

PERSONA = Persona(
    name='[자동] blog35 · 비스타 1박 · 2인(동행자)',
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
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "◎ 그랜드 워커힐 건물에서 체크인",
    "THE_PAVILION": "◎ 체크인 후 바로 앞 더파빌리온에서 코코넛커피와 쿠키",
    "VISTA_ROOM": "◎ 커피 후 객실로 올라감, 숙박",
    "SKYARD": "○ 같은 층 스카이야드 족욕 — 온도·깊이 '너무 좋았어요' 체험 서술",
    "VISTA_POOL": "◎ 저녁에 3층 실내수영장에서 동행자와 수영",
    "THE_BUFFET": "◎ 다음 날 평일 7시 10분쯤 더뷔페 조식, 창가 자리"
}
TRUTH_PASSED: dict[str, str] = {
    "FOREST_PARK": "◎ 산책 겸 둘러보러 가서 사진만 찍고 돌아감",
    "GRAND_LOBBY": "○ 체크인·더파빌리온이 있는 1층 로비 통과",
    "CU_THEATRE": "△ 지하 1층 위치 안내만, 이용 언급 없음",
    "PARKING_TOWER_B1": "△ 주차타워 주차 후 체크인하러 이동 (층 미기재)"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "◎ 야외수영장 리버파크는 운영이 끝나 이용 불가",
    "GRAND_POOL": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
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
TRUTH_UNREACHABLE: dict[str, str] = {
    "호텔 밖 양식 레스토랑": "◎ 첫날 저녁, 룸서비스 대신 근처 양식 식당까지 걸어가 석식"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_FRONT_DESK', 'THE_PAVILION', '◎ 체크인하고 방 키 받은 후 바로 앞 카페 이용'), ('THE_PAVILION', 'VISTA_ROOM', '◎ 커피를 다 마시고 객실로 올라옴'), ('VISTA_ROOM', 'VISTA_POOL', '○ 객실 입실 후 저녁에 수영장'), ('VISTA_POOL', 'THE_BUFFET', '○ 수영은 첫날 저녁, 조식은 다음 날 아침')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'THE_PAVILION', '◎ 체크인 후 코코넛커피와 쿠키'), ('조식', 'THE_BUFFET', '◎ 다음 날 7시 10분쯤 더뷔페 조식')]
