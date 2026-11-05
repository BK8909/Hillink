"""
blog47 — 한호 정답 확인
정답 확인: 한호 · 9/29 · 보류 없음 (라운지 3~5시 이용은 확인; 간식 실제 섭취량은 미상)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
9/28 자동 초안을 원문 r034와 대조했다. 성향(TRAIT_EVIDENCE)은 자동 초안 그대로 두었다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 11, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 워커힐 더글라스 하우스 투숙 (라운지패키지)",
    "nights": "○ 주말 호캉스, 다음 날 조식 후 체크아웃 → 1박",
    "party": "◎ 동행자와 둘이 방문 · 노키즈존이라 아이 미동반",
    "included_meals": "○ 더글라스 투숙객이 라운지 3~5시 서비스·디너·조식을 이용; 체크리스트 규칙에 따라 간식·석식·조식 포함으로 기록",
    "room_minimal": "근거 없음 → false",
    "arrival": "◎ '차를 가져왔고 그랜드 워커힐 앞에서 발렛 1회 무료' — 발렛 맡기고 셔틀로 이동"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.75, "◎ 추가금 내고 비스타 조식 가려 했으나 '셔틀버스 귀찮음' 으로 라운지 조식을 그냥 먹음 · 수영장/짐이 다른 건물이라 셔틀 타야 하는 점을 불만으로 적음"),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.5, "○ 라운지 '뷰는 대박적으로 좋지만', '이런 뷰까지 얻어낸 건 덤' — 좋았다 정도"),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.75, "○ '조용한 숲캉스, No 키즈 존' 이라 더글라스를 고름 · '간만에 조용한곳에서 힐링한 부분은 만족'"),
}

PERSONA = Persona(
    name='[확인 초안] blog47 · 더글라스 주말 1박 · 동행자 1 (라운지 패키지)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='DOUGLAS',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('간식', 'DOUGLAS_LOUNGE'), ('석식', 'DOUGLAS_LOUNGE'), ('조식', 'DOUGLAS_LOUNGE')),
    booked=(),
    arrival='car_valet',
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "VALET_DESK": "◎ 그랜드 앞에서 차를 발렛 맡기고, 체크아웃 후 그랜드로 가서 차를 찾음",
    "DOUGLAS_LOBBY": "◎ 셔틀로 도착해 로비에서 (온라인) 체크인",
    "DOUGLAS_ROOM": "◎ 안쪽 객실 투숙, 무료 미니바",
    "DOUGLAS_LOUNGE": "◎ 라운지 스낵·디너 메뉴를 평가하고 다음 날 조식은 먹었다고 명시",
    "DOUGLAS_LIBRARY": "◎ '기대없이 갔다가 의외로 좋았던 라이브러리', 동행자와 둘뿐이었음"
}
TRUTH_PASSED: dict[str, str] = {
    "FOREST_PARK": "◎ 산책하다 발견, '포토존에서 사진만 살짝 찍고 나왔다' — 시설 이용 없음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 추가금 내고 비스타 조식 가려다 셔틀 귀찮음으로 라운지 조식을 먹음",
    "GRAND_LIBRARY": "○ 그랜드 도서관이 있다는 사실만 뒤늦게 알았다고 적음 (안 갔다는 직접 문장은 없음)",
    "GRAND_POOL": "○ 언급 없음 (수영장이 다른 건물이라 불편하다는 불만만)",
    "VISTA_POOL": "○ 언급 없음",
    "FITNESS": "○ 언급 없음 (gym이 다른 건물이라 불편하다는 불만만)",
    "RIVERPARK": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'DOUGLAS_LOUNGE', '○ 라운지 3~5시 서비스 사진·메뉴 평가와 이용 후 실망 서술; 체크리스트는 라운지 스낵을 간식으로 셈'), ('석식', 'DOUGLAS_LOUNGE', "○ 디너를 배달 음식과 비교하며 평가해 이용한 것으로 읽힘"), ('조식', 'DOUGLAS_LOUNGE', "◎ 라운지 조식 '그냥 먹었고 만족스러웠다'")]

