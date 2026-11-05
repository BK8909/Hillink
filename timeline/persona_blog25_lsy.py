"""
blog25 — 정답 확인본 (소연). 자동 추출 초안 persona_blog25_auto.py 를 원문 r003 과 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용

정답 확인: 소연 · 22분 · 보류 4건

고친 것 (규칙 1~5)
  · 라이브러리 — 초안은 "지나감" 인데 원문은 "객실키가 없어서 들어가 보진 못했어요" 다.
    지나간 게 아니라 못 간 곳이고, 못 갔다고 적혀 있으니 안 간 곳의 근거는 원문 명시(마름모)다
  · 빛의 시어터 · 르파사쥬 — 패키지 안내와 "미니 케이크를 보내주셨는데" 뿐이라 지나간 곳이 아니다 → 안 감
  · CU 편의점 — "있어서 간단한 스낵 사기에도 좋아 보이고요" 는 보기만 한 것이라 어느 칸에도 안 넣는다 (규칙 1)
  · 주차타워 — 초안은 지나감 ("주차타워 주차 후 호텔 연결통로 이용 추정 (층 명시 없음)") 인데 원문에 "주차타워에 주차했는데 지하 3층에 호텔
    연결통로" 가 있다. 주차 자체를 서술했으니 방문이다 (규칙 1)
  · 순서 쌍에서 프런트에서 객실로 가는 쌍 제거 (규칙 3 — 체크인 절차 안쪽)
  · 시작 날짜 — 초안은 글 작성일 9/3 인데 원문에 "전 8월말에 방문했는데" 가 있다

보류: TRUTH_VISITED 의 프런트 — "조식을 체크인하자마자 바로 예약하라 얘기 주시더라고요" 로
      그 자리에서 받은 안내가 이후 동선(조식 2부)을 정했다고 보아 방문으로 두었다. 다만 규칙 1 의
      '"체크인했다" 한 줄뿐이면 프런트는 TRUTH_PASSED' 와 경계가 가깝다. 공통 후기라 여기서 갈릴 수 있다
보류: 시작 날짜 — "8월말" 만 있고 일자가 없어 8/30 으로 두었다. 글 작성일(9/3)보다는 가깝지만
      정확하지 않다. 조식 사전예약제(1부 · 2부)가 토 · 일 · 월 · 공휴일이라 (더뷔페 공식 안내) 주말일 가능성이 있다
      → 10/11: 2026 여름 (7/17~8/31) 은 매일 1부 · 2부라 8월 말엔 요일 근거가 안 된다 (검증기 창). 8/30 그대로
보류: facts.booked 의 더뷔페 — 조식은 패키지 포함이고 2부 예약은 체크인 직후 현장에서 한 것이다.
      1차에서도 갈렸던 자리라 초안 값을 그대로 두었다. 팀 기준이 필요하다
보류: facts.booked 의 빛의 시어터 — 초대권 2장이 패키지에 포함됐지만 관람 기록이 없다. 예약 시점
      사실로는 맞지만 booked 는 에이전트에서 +8 이라 안 간 곳으로 유도한다. "포함됐으나 안 씀" 을
      어떻게 적을지 기준이 없어 초안 값을 두었다

한 체류인가 (체크리스트 0장) — 이어붙인 글 2편(투숙 후기 + 더뷔페 조식 후기)이 같은 1박이다.
조식 편이 "워커힐 투숙후기는 위의 링크 확인해주세요" 로 앞 글을 가리킨다.

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 30, 14, 30)      # 날짜 △ '전 8월말에 방문했는데' · 일자는 없음(보류) · 시각 △

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐 서울 318호 배정, 주차타워뷰",
    "nights": "◎ 다음날 조식 먹고 짐 싸면 바로 체크아웃",
    "party": "◎ 4명이 워커힐에 온 건 처음 — 동행자 1 · 아이 2 (아이 어메니티·가운 제공)",
    "included_meals": "◎ '더뷔페 2인 조식포함' 패키지",
    "booked": "◎ 체크인 직후 조식 2부(08:30~) 예약 · ◎ 빛의 시어터 초대권 2장 패키지 포함(사용 언급은 없음)",
    "arrival": "◎ 주차타워에 주차함 (발렛 언급 없음)",
    "room_minimal": "○ 체크인 후 짐 정리·침대에서 놀기 등 객실 체류 있음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상 (조식 줄이 길었다고만 적고, 예약은 체크인 시 안내에 따른 것)'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (석식 장소 미기재)'),
    '조망 중시': (0.5, '◎ 조식 때 뷰 좋은 공간에서 식사해 아주 좋았다 · 뷰 보며 먹으니 더 맛있었다 — 좋았다 수준, 뷰로 고른 문장 없음'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog25 · 그랜드 1박 · 가족 4인(아이 동반) · 조식·수영장·빛의 시어터 초대권 패키지',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'),),
    booked=('THE_BUFFET', 'THEATRE_OF_LIGHT'),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 체크인하자마자 조식 예약 안내를 받음",
    "GRAND_ROOM": "◎ 객실 배정받아 짐 풀고 아이들이 침대에서 놀고 숙박",
    "GRAND_POOL": "◎ 체크인하고 바로 실내수영장에서 저녁 먹기 전까지 실컷 놂",
    "THE_BUFFET": "◎ 다음날 조식 2부 예약 후 더뷔페에서 조식",
    "PARKING_TOWER_B1": "◎ '주차타워에 주차했는데 지하 3층에 호텔 연결통로가 따로 있으니' — 주차를 직접 서술"
}
# 규칙 ① — 보기만 한 곳(CU 편의점)은 어느 칸에도 안 넣는다.
# 나머지는 지나간 곳이 아니라 안 간 곳이라 아래 칸으로 옮겼다.
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_LIBRARY": "◎ '객실키가 없어서 들어가 보진 못했어요' — 체크아웃 뒤라 입장 불가",
    "THEATRE_OF_LIGHT": "○ 초대권 2장이 패키지에 포함됐다는 안내만 · 관람 기록 없음",
    "LE_PASSAGE": "○ 르파사쥬 미니 케이크를 객실로 보내 줌 — 본인이 간 서술 없음",
    "RIVERPARK": "○ 언급 없음 (해시태그만)",
    "FOREST_PARK": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'GRAND_POOL', '◎ 객실에서 짐 풀고 수영장 갈 준비'), ('GRAND_POOL', 'THE_BUFFET', '◎ 첫날 수영장, 다음날 아침 조식'), ('GRAND_ROOM', 'THE_BUFFET', '◎ 첫날 객실 입실, 다음날 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '◎ 2부 예약 후 더뷔페 조식')]
