"""
못 씀: 정보글 뒤에 여러 이용객 후기가 섞여 있고 글쓴이 직접 방문 기록이 아님
blog53 — 자동 추출 페르소나 초안 유지.

체크리스트 0번 기준으로 쓸 수 없는 글로 판단하여 정답 칸은 고치지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 4, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울 숙박 후기, 메인 호텔 지하 2층 실내 수영장 이용",
    "nights": "◎ '1박이었는데도 제대로 쉬고 온 기분'",
    "party": "◎ 동행자와 둘이 서울에서 하루 호캉스 (아이 언급 없음)",
    "included_meals": "○ 조식은 먹었지만 패키지 포함이라고 적히지 않음 → 비움",
    "room_minimal": "○ 객실 체류를 줄였다는 서술 없음",
    "arrival": "○ 이 체류의 도착 수단은 적혀 있지 않음 (지하철·셔틀 후기는 별도 이용객 문단)",
    "stay_choice": "○ '최근 이용객 후기' 에 체류가 여러 개 섞여 있어 이용 장소가 가장 많은 첫 문단(동행자 1박: 객실·수영장·사우나·조식)만 다룸"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.75, "○ '멀리 여행 가기는 귀찮아서 서울에서 하루 호캉스' · '밖으로 나갈 생각이 안 들더라' — 먼 이동을 이유로 가까운 곳을 고름"),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (None, '근거 없음 → 미상'),
    '새로움 추구': (None, '근거 없음 → 미상 (수영장·사우나 이용 사실만 있음)'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog53 · 못 씀 후보 · 정보글 뒤 이용객 후기 중 첫 번째 체류',
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
    arrival=None,
    room_minimal=False,
    note="못 씀 후보 · 자동 초안 유지",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "○ '체크인하고' 1박 투숙",
    "GRAND_POOL": "◎ '체크인하고 수영장에서 놀다가' (그랜드 투숙객용 실내 수영장)",
    "WELLNESS_SAUNA": "◎ '수영장에서 놀다가 사우나까지 이용하니까'",
    "THE_BUFFET": "○ '다음 날에는 조식 먹고' — 호텔 조식은 더 뷔페에서 운영된다고 본문이 안내"
}
TRUTH_PASSED: dict[str, str] = {
    "RIVERPARK": "언급만 (여름 시즌 시설 소개), 이용 안 함",
    "PIZZA_HILL": "언급만 (주변 맛집 추천), 이용 안 함",
    "ONDAL": "언급만 (추천), 이용 안 함",
    "GEUMRYONG": "언급만 (추천), 이용 안 함",
    "GWANGNARU_STN": "언급만 (셔틀 안내), 이 체류에서 이용 서술 없음",
    "GANGBYEON_STN": "언급만 (셔틀 안내)"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "FITNESS": "○ 언급 없음 (사우나 위치 안내로만 등장)",
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'GRAND_POOL', "◎ '체크인하고 수영장에서 놀다가'"), ('GRAND_POOL', 'WELLNESS_SAUNA', "◎ '수영장에서 놀다가 사우나까지'"), ('WELLNESS_SAUNA', 'THE_BUFFET', "◎ 사우나 후 '다음 날에는 조식 먹고'")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', "○ '다음 날에는 조식 먹고 천천히 준비해서 나왔어요' — 장소는 본문 안내(더 뷔페)로 추론")]
