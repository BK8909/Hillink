"""
blog23 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog23.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 23
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐서울 클럽스위트룸 투숙",
    "nights": "△ 박 수 명시 없음, 라운지 하루 · 조식 한 번 서술로 1박 추정",
    "party": "○ 라운지에서 혼자 노트북 작업, '다음에 아이들이랑 와도 좋겠다' 는 서술로 아이 미동반·혼자 투숙 추정",
    "included_meals": "◎ 클럽스위트 투숙 시 클럽라운지(티타임·해피아워) 이용 가능 · ◎ 성수기엔 클럽라운지 조식인데 이날은 더뷔페에서 진행",
    "room_minimal": "○ 거실·욕실 2개 스위트의 넓이와 채광을 즐겼다고 서술",
    "arrival": "도착 수단 언급 없음",
    "start_at": "날짜 미기재, 체크인 전 라운지 티타임(13:00~) 이용"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '○ 조식 커피 주문이 밀리지 않아 좋았다는 감상뿐, 대기 행동 서술 없음 → 미상'),
    '이동 최소화': (None, '○ 호텔 밖 식사 계획을 접었지만 이유는 라운지 만족이지 이동 거리가 아님 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.5, '◎ 아차산 뷰 보며 힐링, 뷰 좋았다고 적었으나 라운지에서는 한강뷰 창가 대신 사람 없는 쪽에 앉음 — 뷰가 선택 기준은 아님'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.75, "◎ '한강뷰 창가쪽은 사람들이 좀 있는데, 이쪽은 사람 1도 없어서 편하게 앉아서 노트북' — 한적한 쪽을 골라 앉음"),
}

PERSONA = Persona(
    name='[자동] blog23 · 그랜드 클럽스위트 1박 · 혼자(추정) 클럽라운지 위주',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=1,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'), ('석식', 'GRAND_CLUB_LOUNGE')),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_CLUB_LOUNGE": "◎ 체크인 전 티타임에 짐 놓고 노트북 작업, 해피아워에 문 닫을 때까지 식사·주류",
    "GRAND_ROOM": "◎ 클럽스위트룸(아차산뷰) 투숙",
    "SKYARD": "○ 비스타 스카이야드에 가서 낮과 야경 모습을 보고 다시 객실로 돌아옴",
    "THE_BUFFET": "◎ 이날 조식이 더뷔페에서 진행되어 조식 뷔페를 열 접시 먹음"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 체크인 언급만 있음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_CLUB_LOUNGE', 'GRAND_ROOM', '◎ 체크인 전 라운지 티타임에서 짐 놓고 일 본 뒤 객실'), ('GRAND_CLUB_LOUNGE', 'SKYARD', '○ 후기 서술 순서상 라운지 이후 스카이야드'), ('GRAND_ROOM', 'SKYARD', "○ 스카이야드 다녀와 '다시 객실'"), ('SKYARD', 'THE_BUFFET', '○ 스카이야드 야경 뒤 다음 날 아침 더뷔페 조식'), ('GRAND_CLUB_LOUNGE', 'THE_BUFFET', '◎ 라운지 이용 다음 날 아침 더뷔페 조식'), ('GRAND_ROOM', 'THE_BUFFET', '○ 투숙 다음 날 아침 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'GRAND_CLUB_LOUNGE', '◎ 티타임에 쿠키·마카롱·샌드위치·커피'), ('석식', 'GRAND_CLUB_LOUNGE', '◎ 해피아워 뷔페·주류를 문 닫을 때까지 먹음, 호텔 밖에 나가지 않기로 함'), ('조식', 'THE_BUFFET', '◎ 더뷔페 조식 뷔페')]
