"""
blog48 — 한호 정답 확인
정답 확인: 한호 · 9/29 · 보류 없음 (평일 클럽 조식은 체크리스트 규칙에 따라 더뷔페로 기록)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
9/28 자동 초안을 원문 r033과 대조했다. 성향(TRAIT_EVIDENCE)은 자동 초안 그대로 두었다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 7, 27, 14, 30)      # 날짜 ◎ 후기 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울, 클럽 스위트 더블 한강뷰 (글 제목)",
    "nights": "◎ 2026.7.27~2026.07.28",
    "party": "◎ 동행자와 둘 (아이 없음)",
    "included_meals": "○ 클럽 객실에서 해피아워·조식 이용; 체크리스트 규칙에 따라 해피아워는 라운지, 평일 조식은 더뷔페 포함으로 기록",
    "booked": "◎ '룸 패키지에 포함된 빛의 씨어터 전시를 보고 왔당'",
    "club_access": "◎ 클럽 스위트 숙박, 해피아워 라운지 이용, '클럽스위트에서 숙박을하면 SKYARD를 이용할 수 있어서'",
    "arrival": "○ 도착 수단 언급 없음",
    "room_minimal": "○ '방에서 놀다가', 새벽까지 객실 파티 — 객실 체류 줄이지 않음",
    "start_time": "○ 체크인 시각 없음; 17:30 은 해피아워 운영시간에 맞춰 라운지로 온 시각이고 그 전에 이미 객실에 있었음 → 투숙 기본값"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (라운지·치킨 배달은 선택 이유가 적히지 않음)'),
    '조망 중시': (0.75, "◎ SKYARD 에서 '족욕보다는 야경보러 온 나', 더워서 '다시 야경보러 감' — 뷰를 이유로 머묾"),
    '새로움 추구': (0.75, "○ 'SKYARD를 이용할 수 있어서 다녀왔당', '야경도 보고 족욕도 하고 할거 다해따', 체크아웃 후 전시까지 '알차게' — 이용 가능한 곳을 일부러 챙겨 감"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[확인 초안] blog48 · 그랜드 클럽스위트 1박 · 2인 기념일',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('석식', 'GRAND_CLUB_LOUNGE'), ('조식', 'THE_BUFFET')),
    booked=('THEATRE_OF_LIGHT',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ '방에서 놀다가', 밤에 객실에서 파티, 조식 후 '와서 또 잠'",
    "GRAND_CLUB_LOUNGE": "◎ '해피아워 시간 맞춰서 라운지에 왔당' — 음식·주류 이용",
    "THE_BUFFET": "○ 다음 날 평일 조식 이용; 본문 장소명은 없으나 체크리스트의 평일 클럽 조식 기준 적용",
    "SKYARD": "◎ 'SKYARD를 이용할 수 있어서 다녀왔당' — 족욕하고 야경 봄",
    "LE_PASSAGE": "○ 르 파사쥬에서 사 온 케이크를 객실에서 먹음 (누가 직접 구매했는지는 미상)",
    "THEATRE_OF_LIGHT": "◎ '체크아웃 하고 룸 패키지에 포함된 빛의 씨어터 전시를 보고 왔당'"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['LE_PASSAGE'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'GRAND_CLUB_LOUNGE', "◎ 방에서 놀다가 해피아워 시간 맞춰 라운지로"), ('GRAND_CLUB_LOUNGE', 'SKYARD', '○ 해피아워 뒤 스카이야드로 감'), ('SKYARD', 'THEATRE_OF_LIGHT', "◎ 첫날 스카이야드 방문 뒤 다음 날 체크아웃하고 전시 관람")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'GRAND_CLUB_LOUNGE', "◎ 해피아워 '저녁시간때라 따뜻한 음식' — 피자·나시고랭·아귀구이 등"), ('간식', 'LE_PASSAGE', '◎ 르 파사쥬에서 사 온 하트케이크로 밤에 객실 파티 (포장)'), ('조식', 'THE_BUFFET', '○ 다음 날 평일 조식 이용 — 장소명 미기재, 체크리스트의 평일 클럽 조식 기준 적용')]

