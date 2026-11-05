"""
blog56 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog56.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 56
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 10, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "○ '비스타 워커힐의 경우 객실 안에 젖병 소독기가 세팅되어 있다'며 객실 대여 물품을 설명",
    "nights": "○ 집 밖에서 아이와 잠, '다음날 조식' → 1박 추정",
    "party": "◎ 동행자 둘과 아이 한 명",
    "included_meals": "○ 조식 포함 여부 명시 없음",
    "room_minimal": "○ 아이 수유·재우기 패턴에 맞춰 객실 중심으로 지낸 것으로 보이며 최소화 문장 없음 / arrival: 아이가 카시트에 오래 못 앉아 가까운 곳을 골랐다고 해 자차로 보이나 발렛·직접 주차 여부 불명 → null"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.75, '◎ 포레스트파크는 날이 덥고 유모차를 들고 계단을 올라야 한다는 후기를 보고 가지 않음, 카시트에 오래 못 앉으니 집 근처 호텔로 결정'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (None, "근거 없음 → 미상 (스카이야드 한강 조망은 '날 좋은 날이면 좋을 것 같다'는 가정만)"),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog56 · 비스타 1박 · 아이 동반 가족 · 근거리 호캉스',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=3,
    has_child_under_13=True,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_LIBRARY": "◎ 체크인 전에 2층 도서관에서 아이 수유",
    "VISTA_ROOM": "◎ 사전 요청한 아이 용품이 세팅된 객실에서 숙박",
    "SKYARD": "◎ 비스타 4층 스카이야드에 갔으나 한여름이라 너무 더워 오래 있지 못함",
    "THE_BUFFET": "○ 다음날 조식 먹을 때 더뷔페 옆 수유실 이용"
}
TRUTH_PASSED: dict[str, str] = {
    "CU_THEATRE": "언급만 — 지하 1층 편의점 옆 수유실 안내, 이용 문장 없음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "FOREST_PARK": "◎ 계단·더위 때문에 아이가 걸을 수 있을 때 오기로 하고 가지 않음",
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_LIBRARY', 'VISTA_ROOM', '◎ 체크인 전에 2층 도서관에서 수유'), ('VISTA_ROOM', 'THE_BUFFET', '○ 객실에서 자고 다음날 조식'), ('GRAND_LIBRARY', 'THE_BUFFET', '◎ 체크인 전 도서관 수유, 다음날 조식 때 더뷔페 옆 수유실')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', "○ '다음날 조식 먹을 때' 더뷔페 옆 수유실을 이용했다고 적음")]
