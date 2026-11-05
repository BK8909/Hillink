"""
blog39 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog39.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 39
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 4, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울 트윈룸, 숲뷰",
    "nights": "◎ 2박 3일",
    "party": "○ 트윈룸 — 2인 추정, 아이 동반 언급 없음",
    "included_meals": "○ 조식 포함 여부 언급 없음 → 비움",
    "booked": "◎ 빛의 시어터는 현장에서 방에서 예매 — 사전 예약 아님",
    "arrival": "○ 오기 전 근처에서 와인 구입 · 도착 수단 언급 없음",
    "room_minimal": "◎ 방에서 영화 보며 쉬는 등 객실 체류 많음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.25, '○ 저녁은 호텔 식당 대신 근처에서 산 와인과 배달 닭강정으로 해결'),
    '조망 중시': (0.75, '◎ 뻔한 한강뷰가 지겨워 숲뷰를 보려고 찾다가 그랜드 워커힐을 고름'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.75, '◎ 주변 객실 소음에 참다가 프런트에 전화 · 방음 때문에 다신 안 갈 듯이라고 적음'),
}

PERSONA = Persona(
    name='[자동] blog39 · 그랜드 트윈 2박 · 숲뷰 · 빛의 시어터·헬스장·도서관 · 방음 불만',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=2,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 트윈룸 2박, 방에서 쉬고 영화 봄",
    "THEATRE_OF_LIGHT": "◎ 방에서 전시 예매하고 바로 보러 가 사진 찍고 즐김",
    "FITNESS": "◎ 저녁에 헬스장에 가서 운동함 (시설 낡았다고 불만)",
    "GRAND_LIBRARY": "◎ 다음날 조식 후 도서관에 가서 책을 읽음",
    "THE_BUFFET": "○ 다음날 여유롭게 조식을 먹음 (식당 이름 명시 없음 → 더뷔페 추정)"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_POOL": "◎ 수영할 생각 없어 구경만 하고 패스",
    "GRAND_LOBBY": "○ 로비에서 사진만 찍음 · 배달 음식을 로비 문 밖에서 받음",
    "CU_THEATRE": "○ 호텔 내 편의점이 있다는 언급만"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 소음 때문에 프런트에 전화만 함, 방문 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음 (산책로 언급은 일반 소개)",
    "RIVERPARK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'THEATRE_OF_LIGHT', '◎ 방에서 쉬다가 예매하고 바로 보러 감'), ('THEATRE_OF_LIGHT', 'FITNESS', '○ 첫날 전시 후 저녁에 헬스장 (서술 순서)'), ('FITNESS', 'GRAND_LIBRARY', '◎ 첫날 저녁 헬스장, 다음날 도서관'), ('THE_BUFFET', 'GRAND_LIBRARY', '◎ 다음날 조식을 먹고 도서관에 감'), ('FITNESS', 'THE_BUFFET', '○ 첫날 저녁 헬스장, 다음날 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '○ 다음날 여유롭게 조식을 먹음 (식당명 미기재, 더뷔페 추정)')]
