"""
blog20 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog20.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 20
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 31, 13, 30)      # ◎ 날짜(전시 마지막 날 8/31) · △ 시각은 적히지 않아 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 빛의 시어터 전시 방문",
    "nights": "◎ 전시·카페만 이용한 비투숙",
    "party": "○ 작성자와 아이 동반 명시, '낮잠 자는 아이들'·'우정사진' 으로 다른 동행자와 아이 1쌍 더 추정",
    "included_meals": "◎ 입장권+에이드 패키지로 음료는 티켓 포함이나 전시 연계 카페는 장소 코드 목록에 없음",
    "booked": "◎ 네이버로 성인입장권+음료 패키지 미리 구매",
    "arrival": "○ 지하 주차장이 입구와 연결, 관람객 주차 할인 안내 → 자차 직접 주차",
    "depart_by": "△ 오래 관람하는 전시가 아니라는 언급 + 카페 들름 → 이용 끝 무렵 추정",
    "room_minimal": "비투숙"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (카페만 이용)'),
    '조망 중시': (0.5, '◎ 카페에서 비 오는 한강뷰에 잠깐의 힐링이었다고 적음'),
    '새로움 추구': (0.75, '◎ 핫한 신상 나들이 장소가 뜨면 바로 가 봐야 직성이 풀린다며 전시 마지막 날 일부러 찾아감'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (잔잔하고 조용히 관람할 수 있었다는 공간 묘사만)'),
}

PERSONA = Persona(
    name='[자동] blog20 · 비투숙 · 빛의 시어터 전시 · 아이 동반',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(15, 30),
    included_meals=(),
    booked=('THEATRE_OF_LIGHT',),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "THEATRE_OF_LIGHT": "◎ 입장해 1·2층, 분장실, 거울룸, 게임룸 등을 돌며 관람",
    "PARKING_TOWER_B1": "○ 지하 주차장에 주차해 호텔 입구로 바로 연결"
}
TRUTH_PASSED: dict[str, str] = {
    "THEATRE_ART_SHOP": "◎ 전시 나오는 길 소품샵 옆 사진부스만 이용, 소품샵 이용 언급 없음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "CU_THEATRE": "○ 편의점 가는 통로의 유아휴게실 안내만, 이용 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 시어터 연계 카페": "◎ 전시 보고 나와 카페에서 패키지 음료와 파운드케이크",
    "사진부스(소품샵 옆)": "◎ 방문 기념 사진 촬영"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('PARKING_TOWER_B1', 'THEATRE_OF_LIGHT', '○ 지하 주차 후 입구 들어가자마자 전시관')]
TRUTH_MEALS: list[tuple[str, str, str]] = []
