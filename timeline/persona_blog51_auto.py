"""
blog51 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog51.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 51
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 6, 14, 0)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 클럽 마운틴뷰 트윈 스위트 투숙",
    "nights": "◎ 일월 투숙, 월요일 조식 후 체크아웃",
    "party": "◎ 3인 호캉스, 성인 셋",
    "included_meals": "○ 2인 요금에 클럽라운지·조식·수영장이 들어 있고 1인 추가 시 라운지·조식·수영장 요금을 더 낸다고 적음 · 라운지는 티타임·해피아워, 평일 조식은 비스타 더뷔페",
    "room_minimal": "◎ 객실에서 쉬다가 라운지 재방문, 조식 후 객실로 돌아와 한숨 더 잠"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, '○ 해피아워 초반 줄 서서 음식을 가져왔고 30분 뒤 한산해졌다고 담담히 적음'),
    '이동 최소화': (0.5, '○ 해피아워에서 음식 가지러 왔다갔다할 동선을 생각해 1층 안쪽 자리를 고름 · 그 외 비스타 스카이야드·더뷔페까지 이동'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.5, '○ 티타임에 흐린 날에도 창가 자리를 잡았지만, 객실은 리버뷰를 라운지에서 볼 수 있으니 더 저렴한 마운틴뷰로 골랐고 해피아워 자리도 동선으로 고름'),
    '새로움 추구': (0.75, '◎ 예전에 더글라스는 투숙해 봐서 이번엔 그랜드 클럽을 골랐다고 밝힘 · 평소 잘 못 먹는 음식 위주로 먹음'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.5, '○ 사람이 적다는 직원 안내로 조식 1부에 갔지만 한산해서 늦잠 잘 수 있는 2부에 갈걸 후회 — 붐빔 회피보다 편의 우선'),
}

PERSONA = Persona(
    name='[자동] blog51 · 그랜드 클럽 트윈 스위트 1박 · 성인 3인',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=3,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('간식', 'GRAND_CLUB_LOUNGE'), ('석식', 'GRAND_CLUB_LOUNGE'), ('조식', 'THE_BUFFET')),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_CLUB_LOUNGE": "◎ 체크인 전 티타임, 3시 이후 재방문, 해피아워 2시간 이용",
    "GRAND_ROOM": "◎ 11층 클럽 트윈 스위트에 짐을 두고 쉼, 투숙",
    "SKYARD": "◎ 셋이서 한강을 보며 족욕",
    "GRAND_POOL": "◎ 해피아워 후 소화시킬 겸 그랜드 실내수영장 이용",
    "THE_BUFFET": "◎ 월요일 조식 1부, 오전 7시쯤 비스타 1층 더뷔페에서 식사"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "◎ 예약한 객실에 야외수영장이 포함되지 않아 이용하지 않았다고 적음",
    "GRAND_FRONT_DESK": "○ 언급 없음 (라운지 자리로 직원이 객실키를 가져다줌)",
    "VISTA_POOL": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_CLUB_LOUNGE', 'GRAND_ROOM', '◎ 체크인 전 티타임 후 객실키를 받아 객실로 감'), ('GRAND_ROOM', 'GRAND_POOL', '◎ 객실 입실 뒤 해피아워 후 실내수영장'), ('GRAND_CLUB_LOUNGE', 'GRAND_POOL', '◎ 해피아워를 즐기고 소화시킬 겸 수영장'), ('GRAND_POOL', 'THE_BUFFET', '◎ 수영장은 첫날 저녁, 조식은 다음 날 아침'), ('GRAND_ROOM', 'SKYARD', '○ 객실 소개 뒤 스카이야드 족욕 — 정확한 시점은 안 적힘')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'GRAND_CLUB_LOUNGE', '◎ 체크인 전 티타임 디저트·커피, 3시 이후 에그타르트·귤'), ('석식', 'GRAND_CLUB_LOUNGE', '◎ 해피아워에서 폭립·생선구이 등으로 2시간 식사'), ('조식', 'THE_BUFFET', '◎ 월요일 더뷔페 조식 1부')]
