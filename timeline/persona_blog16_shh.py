"""
blog16 — 한호 독립 정답 확인본 (9/28, 보류 항목 명시)
정답 확인: 한호 · 2026-09-28 · 소요시간 미기록 · 보류: SKYARD 실제 족욕 여부, PIZZA_HILL 끼니 종류

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog16.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 16
9/28 자동 초안을 복사해 사실·방문 근거만 원문과 대조했다. 성향 근거는 초안 그대로 둔다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 20)      # △ 날짜 미상 · ◎ 비스타 로비 14:20 도착

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 당첨, 디럭스 트윈룸 리버뷰 투숙",
    "nights": "◎ 다음날 조식 후 체크아웃",
    "party": "○ '우리', '둘다 도파민 터졌다' — 본인 + 동행자 1",
    "included_meals": "◎ 조식은 투숙객 할인가로 별도 결제 — 포함 아님",
    "room_minimal": "○ 객실 미니바·스피커 등을 즐김 — 객실 최소 아님",
    "booked": "◎ 조식 1부(06:30~08:10)를 예약",
    "arrival": "○ 회사 조퇴 후 이동 — 수단 언급 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, '○ 체크인 대기줄 44팀을 웃으며 담담히 기다림 · 불만/포기 없음'),
    '이동 최소화': (None, '근거 없음 → 미상 (피자힐 셔틀 이용은 밤길·언덕 안내일 뿐 선택 변경 문장 없음)'),
    '격식 선호': (None, '근거 없음 → 미상 (피자힐은 궁금해서 간 것 · 격식/캐주얼 선택 이유 없음)'),
    '조망 중시': (0.5, "◎ 리버뷰 객실에 '대박사건', 피자힐 '맛은 뷰값' — 좋았다 수준, 뷰 때문에 고른 문장 없음"),
    '새로움 추구': (1.0, "◎ 부대시설 설명지를 '다 즐겼다', '부대시설이 많아 즐기려면 누워서 TV 볼 시간이 없다', 피자힐도 '궁금해서 먹어본'"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (수영장 레인이 여유로웠다는 공간 묘사뿐)'),
}

PERSONA = Persona(
    name='[확인 초안] blog16 · 비스타 1박 · 2인 (회사 휴양소)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_LOBBY": "◎ 14:20쯤 비스타 로비 도착, 체크인 대기",
    "VISTA_ROOM": "◎ 11층 디럭스 트윈 리버뷰 객실 투숙",
    "FITNESS": "○ 피트니스 탈의실에서 직원에게 운동복·라커 안내받음 (운동 여부는 미상)",
    "VISTA_POOL": "◎ 롯데타워 보면서 수영, 레인 여유로웠음",
    "PIZZA_HILL": "◎ 로비 키오스크로 셔틀 호출해 피자힐에서 콤비네이션 피자 먹음",
    "THE_BUFFET": "◎ 다음날 조식 1부에 더뷔페에서 조식 3그릇",
    "GRAND_LIBRARY": "○ 2층 도서관 라운지 소파에 앉아 창밖으로 1층 발렛 구경"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ("VISTA_LOBBY", "VISTA_ROOM", "◎ 로비 체크인 뒤 객실 입실"),
    ("PIZZA_HILL", "THE_BUFFET", "◎ 전날 피자를 먹고 다음 날 조식"),
]
TRUTH_MEALS: list[tuple[str, str, str]] = [("조식", "THE_BUFFET", "◎ 다음 날 조식 1부 이용")]


