"""
못 씀: 협찬 글('워커힐호텔로부터 제공을 받아') — 봉인 시험용은 협찬 제외 원칙. 대기열의 협찬 표지가 이 표현을 못 잡았다 (고침) (경수)

blog33 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog33.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 33
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 10, 13, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 1층 로비 라운지 더파빌리온 이용",
    "nights": "◎ 애프터눈티만 이용, 숙박 언급 없음",
    "party": "◎ 동행자와 웰컴드링크 하나씩 선택 — 2인",
    "included_meals": "◎ 패키지 포함 끼니 없음 (제공받은 리뷰)",
    "room_minimal": "비투숙 → false",
    "booked": "◎ '미리 예약을 해두었더니, 예약석으로 안내'",
    "arrival": "주차 방법은 안내만, 본인 도착 수단 명시 없음",
    "start_time": "△ 방문 시각 없음 — 이용 시작 14:00 가정, 30분 전",
    "depart_by": "△ 방문 시각 없음 — 약 1시간 반 이용 후로 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, '○ 체크인 전후 주중에도 웨이팅이 있다며 미리 예약해 예약석으로 입장 — 예약으로 대기를 피함 (주중 할인 목적도 겹침)'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (None, '근거 없음 → 미상 (한강뷰는 워커힐 일반 소개)'),
    '새로움 추구': (None, '근거 없음 → 미상 (시즌 신메뉴 리뷰, 워커힐은 자주 찾는 곳)'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog33 · 비투숙 · 더파빌리온 가을 애프터눈티 · 동행자 1',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(15, 30),
    included_meals=(),
    booked=('THE_PAVILION',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_PAVILION": "◎ 예약석에서 가을 애프터눈티 세트(웰컴드링크·디저트 트레이·커피, 아메리카노 리필) 이용"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ 더파빌리온이 그랜드 1층 로비 라운지 — 통과"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "PIZZA_HILL": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VALET_DESK": "○ 발렛은 제휴카드 소지 시 추천 안내만, 본인 이용 언급 없음",
    "PARKING_TOWER_B1": "○ 주차타워는 안내만, 본인 이용 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'THE_PAVILION', '◎ 가을 애프터눈티 디저트 트레이와 커피·웰컴드링크')]
