"""
정답 확인: 슬기 · 9/28 · 15분
보류: party_size — 라운지에서 혼자 노트북 작업한 정황은 있으나 전체 투숙 인원 명시는 없음
성향: 9/28 추출기 초안 값으로 맞춤 (경수 · 예전 초안 눈금 0.4·0.6·0.7 → 새 눈금). 정답 · 사실은 슬기 확인 그대로

blog23 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 정답 확인 1차(9/24~) — 개발용
손으로 만든 persona_blog23.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 23
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 6, 14, 30)      # (경수 9/29 · 추출기 시기 규칙으로 채움) 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐서울 클럽스위트룸 투숙",
    "nights": "△ 박 수 명시 없음 · 티타임 → 해피아워 → 다음날 조식 흐름으로 1박 추정",
    "party": "△ 라운지에서 혼자 노트북 작업한 정황은 있으나 전체 투숙 인원 명시는 없음 · 아이들은 다음에 데려오고 싶다고 적음(이번엔 미동반)",
    "included_meals": "○ 클럽스위트는 클럽라운지를 거의 종일 이용 가능(해피아워 뷔페 포함) · 조식은 원래 클럽라운지인데 이날은 더뷔페에서 진행",
    "room_minimal": "◎ 방·거실·욕실 2개로 넓고 뷰·욕조가 좋았다고 객실을 즐김",
    "arrival": "도착 수단 언급 없음"
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
    name='[자동] blog23 · 그랜드 클럽스위트 1박 · 혼자 · 클럽라운지 위주',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=1,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('석식', 'GRAND_CLUB_LOUNGE'), ('조식', 'THE_BUFFET')),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_CLUB_LOUNGE": "◎ 체크인 전 티타임 이용, 해피아워 7시 반 마감까지 식사",
    "GRAND_ROOM": "◎ 클럽스위트룸 아차산뷰 투숙",
    "THE_BUFFET": "◎ 이날 조식을 비스타 1층 더뷔페에서 먹음"
}
TRUTH_PASSED: dict[str, str] = {
    "SKYARD": "○ 비스타 스카이야드 족욕 산책 공간을 낮에 구경 · 족욕 이용은 적지 않음 · 이후 다시 객실"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_CLUB_LOUNGE', 'GRAND_ROOM', '◎ 체크인 전 라운지 티타임에서 짐 놓고 일봄 → 이후 객실'), ('GRAND_CLUB_LOUNGE', 'THE_BUFFET', '◎ 전날 티타임·해피아워 후 다음날 조식'), ('GRAND_ROOM', 'THE_BUFFET', '○ 투숙 다음날 아침 조식'), ('GRAND_ROOM', 'SKYARD', "○ 객실 소개 뒤 스카이야드 구경 · 이후 '다시 객실'"), ('GRAND_CLUB_LOUNGE', 'SKYARD', '○ 라운지 티타임·해피아워 소개 뒤 스카이야드')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'GRAND_CLUB_LOUNGE', '◎ 티타임 쿠키·마카롱·샌드위치·커피'), ('석식', 'GRAND_CLUB_LOUNGE', '◎ 해피아워 뷔페·주류를 마감 때까지 먹음'), ('조식', 'THE_BUFFET', '◎ 더뷔페 조식 열 접시')]
