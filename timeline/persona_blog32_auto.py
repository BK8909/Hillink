"""
blog32 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog32.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 32
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 2, 14, 0)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울 클럽 스위트 트윈 리버뷰 객실 투숙",
    "nights": "◎ '1박 2일 워커힐 호캉스', 일-월 숙박",
    "party": "◎ 동행자와 둘이 결혼기념 호캉스, 아이 동반 언급 없음",
    "included_meals": "○ 클럽 객실은 평일 조식을 더뷔페에서 먹는다고 적음(일-월 숙박이라 월요일 조식 더뷔페). 라운지 티타임·해피아워는 club_access 로 처리. 리버파크는 패키지에 미포함이라고 명시",
    "room_minimal": "○ 객실 이용을 줄였다는 문장 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, "◎ 해피아워 음식 줄이 줄지 않자 '결국 대기 줄이 계속 늘어나서 포기하고' 나눠서 가져오기로 전략을 바꿈, 줄에 대한 불만 표현"),
    '이동 최소화': (None, '근거 없음 → 미상 (건물이 여러 개라 찾기 어려웠다는 묘사만 있고 선택을 바꾸지 않음)'),
    '격식 선호': (None, '근거 없음 → 미상 (식당을 고른 문장 없음, 라운지·조식만 이용)'),
    '조망 중시': (0.5, "◎ 해피아워 때 '야경볼겸 창가자리'에 앉았으나, 티타임 때는 눈부시고 테이블이 좁아 한강뷰 창가자리에서 안쪽으로 옮김 → 섞임"),
    '새로움 추구': (0.75, "◎ '쉴틈 없었던 호캉스 스케줄', '실내수영장부터 해피아워, 야외 족욕, 사우나까지 정말 알차고 알뜰하게 즐기고 옴' — 여러 시설을 일부러 돌아봄"),
    '함께 먹기 선호': (0.75, "○ 해피아워에서 동행자가 잠시 자리를 비우자 '오면 같이 줄서려고' 와인 마시며 기다림"),
    '조용함 선호': (0.75, "◎ 스카이야드 족욕이 '사람이 너무 많아서 우리는 조금만 시간 보내다가' 나옴, 여유롭게 즐기려면 노을 시간대 추천"),
}

PERSONA = Persona(
    name='[자동] blog32 · 그랜드 클럽 스위트 1박 · 커플 기념일 · 부대시설 알차게',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'),),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_CLUB_LOUNGE": "◎ 체크인 전 라운지 애프터눈티(커피·다과·독서), 저녁 해피아워에서 와인과 음식",
    "GRAND_ROOM": "◎ 클럽 스위트 트윈 리버뷰 객실 투숙, 수영 후 한 층 위 객실로 변경",
    "GRAND_POOL": "◎ 실내수영장에서 자유형 연습, 다음날 아침 수영도 함",
    "SKYARD": "◎ 해피아워 후 소화시킬 겸 비스타 4층 족욕카페에 가서 잠깐 시간 보내고 야경 봄",
    "WELLNESS_SAUNA": "◎ 체크아웃 전 아침 수영 후 사우나 이용",
    "THE_BUFFET": "◎ 월요일 조식 1부 6:30에 더뷔페에서 먹음"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LIBRARY": "◎ 라이브러리에 들렀으나 너무 어두워 '그냥 구경만하구 나왔당'"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "◎ '리버파크 포함된 패키지가 아니라서 실내수영장 이용', 객실에서 멀리 보이기만 함",
    "VISTA_POOL": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음 (더글라스하우스는 산책 중 근처만 지나고 추천만 함)"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "산책로": "◎ 조식 후 더글라스하우스 쪽으로 작게 한 바퀴 산책, 비스타 쪽에서 한강 구경"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_CLUB_LOUNGE', 'GRAND_ROOM', '◎ 일찍 도착해 라운지 티타임 후 3시쯤 키 받아 객실로'), ('GRAND_ROOM', 'GRAND_POOL', "◎ 객실 들어간 뒤 '부지런히 수영장으로 고고'"), ('GRAND_POOL', 'SKYARD', '◎ 첫날 수영 → 해피아워 → 족욕카페 순서'), ('SKYARD', 'THE_BUFFET', '◎ 족욕은 첫날 밤, 조식은 다음날 아침'), ('SKYARD', 'WELLNESS_SAUNA', '◎ 족욕은 첫날 밤, 사우나는 다음날 체크아웃 전')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'GRAND_CLUB_LOUNGE', '◎ 체크인 전 라운지 애프터눈티에서 커피와 다과'), ('석식', 'GRAND_CLUB_LOUNGE', "◎ 해피아워 음식이 많아 '저녁 따로 먹지않아도 충분했다'"), ('조식', 'THE_BUFFET', '◎ 월요일 조식을 더뷔페 1부에 먹음')]
