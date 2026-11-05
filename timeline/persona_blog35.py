"""
blog35 — 정답 확인본 (소연). 자동 추출 초안 persona_blog35_auto.py 를 원문 r002 와 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 개발용

정답 확인: 소연 · 16분 · 보류 2건

초안이 정확한 편이었다. 고친 것 넷.
  · 주차타워 — 지나감에서 방문으로. "주차타워를 이용했고 차를 세운 후 바로 체크인하러 갔어요" 로
    주차 자체를 서술했다 (규칙 1)
  · CU 편의점 — "지하 1층 카지노 입구 옆 쪽에 위치" 라는 안내뿐이라 어느 칸에도 넣지 않았다 (규칙 1)
  · 더파빌리온 간식 — 카페에서 커피를 마셨고 쿠키는 같이 내준 것이라 끼니에서 뺐다 (규칙 4 —
    음료만 마신 건 끼니가 아니다). 방문지로는 그대로 둔다
  · 순서 쌍에서 프런트가 든 쌍 제거 — 쌍은 머문 곳끼리만 (규칙 3)
  · 프런트 — 방문에서 지나감으로. "체크인을 하고 방 키를 받은 후" 한 줄뿐이라 체크인 그 자체다
    (규칙 1 · blog36 도 같은 이유로 지나감이다)

보류: TRUTH_PASSED 의 포레스트파크 — 산길을 걸어 올라가 둘러봤지만 본인이 "사진만 찍고
      돌아갔" 다고 적었다. 규칙 5 의 "사진만 있고 느낌 · 결과도 없으면 그때 보류" 에 해당해 지나감으로
      두었다. 방문으로 볼지 팀 확인이 필요하다
보류: TRUTH_MEALS 의 첫날 석식 — 호텔 밖 양식 식당이라 장소 목록 밖이다.
      TRUTH_UNREACHABLE 에만 적고 끼니에서 뺐다. 호텔 밖 식사를 끼니로 셀지 기준이 없다 (에이전트는 "식당 외 식사" 를 고를 수 있다)

한 체류인가 (체크리스트 0장) — 이어붙인 글 3편(투숙 · 호텔 밖 저녁 · 조식)이 같은 1박이다.
둘째 · 셋째 글이 "비스타 워커힐에서 호캉스를 하면서" 로 시작한다.

10/11 원문 재대조 — 고친 것 셋
  · 시작 날짜 9/5 → 9/3. 작성일 9/5 는 토요일인데 원문은 체크인 날이 "저희는 평일에 방문했는데" 이고
    조식도 "저희는 평일에 갔어서 오전 7시 오픈이라 한 7시 10분 정도에" 다. 9/5 면 조식이 9/6(일)이라
    둘 다 어긋난다. 작성일 직전 평일 1박 — 9/3(목) 체크인 · 9/4(금) 조식 (07:00 오픈 · 리버파크 운영이
    끝났다는 말과도 맞다 — 2026 리버파크는 8/30 까지)
  · included_meals 근거의 "조식 글은 '내돈내산' 표기" 는 원문에 없다 (초안이 지어낸 말) — 뺐다
  · 성향 근거의 인용 하나를 원문 글자로 ("어딜가든 사실 눈이 즐거운게 좋은 사람")

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 3, 14, 30)      # 날짜 ○ '평일에 방문' · 조식 '평일에 갔어서 오전 7시 오픈' → 작성일(9/5 토) 직전 평일 1박 (소연 10/11) · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 디럭스 더블룸 1박 2일 투숙",
    "nights": "◎ 1박 2일",
    "party": "◎ 동행자와 둘이 방문, 아이 동반 언급 없음",
    "included_meals": "○ 포함 끼니 언급 없음 · 조식 글이 '투숙객 할인 평일 20% 주말 및 공휴일 10%' 를 안내 → 포함 아님",
    "room_minimal": "◎ 객실 묘사·수면 만족 등 객실에서 시간 보냄",
    "arrival": "◎ 차로 방문해 주차타워에 직접 주차 후 체크인"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상 (조식 오픈 시간 방문은 창가 자리 목적)'),
    '이동 최소화': (0.25, '○ 룸서비스 대신 호텔 밖 식당까지 산책 겸 걸어 내려갔다 옴 · 포레스트파크까지 산길 산책'),
    '격식 선호': (0.25, "○ 룸서비스가 비싸서 '가성비' 있는 근처 캐주얼 양식 식당을 골라서 감"),
    '조망 중시': (0.75, "◎ '어딜가든 사실 눈이 즐거운게 좋은 사람' · 조식은 창가(한강뷰) 자리를 위해 오픈 직후 입장, 눈부심도 감수"),
    '새로움 추구': (None, "근거 없음 → 미상 (런치·디너는 '다음에' 희망일 뿐)"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (수영장 한산했다는 묘사뿐)'),
}

PERSONA = Persona(
    name='blog35 · 비스타 1박 · 2인(동행자)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_PAVILION": "◎ 체크인 후 바로 앞 더파빌리온에서 코코넛커피와 쿠키",
    "VISTA_ROOM": "◎ 커피 후 객실로 올라감, 숙박",
    "SKYARD": "○ 같은 층 스카이야드 족욕 — 온도·깊이 '너무 좋았어요' 체험 서술",
    "VISTA_POOL": "◎ 저녁에 3층 실내수영장에서 동행자와 수영",
    "THE_BUFFET": "◎ 다음 날 평일 7시 10분쯤 더뷔페 조식, 창가 자리",
    "PARKING_TOWER_B1": "◎ '주차타워를 이용했고 차를 세운 후 바로 체크인하러 갔어요' — 주차를 직접 서술 (규칙 1)"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_FRONT_DESK": "'체크인을 하고 방 키를 받은 후' 한 줄뿐 — 그 자리에서 일어난 일이 없다 (규칙 1)",
    "FOREST_PARK": "산책 겸 올라가 둘러봤으나 '사진만 찍고 돌아갔'다 — 규칙 5 의 보류 예시에 해당 (보류)",
    "GRAND_LOBBY": "○ 체크인·더파빌리온이 있는 1층 로비를 거쳐 감",
}
# CU 편의점은 위치 안내만이라 어느 칸에도 넣지 않았다 (규칙 1 — 보기만 한 곳)
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "◎ 야외수영장 리버파크는 운영이 끝나 이용 불가",
    "GRAND_POOL": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "호텔 밖 양식 레스토랑": "◎ 첫날 저녁, 룸서비스 대신 근처 양식 식당까지 걸어가 석식"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('THE_PAVILION', 'VISTA_ROOM', '◎ 커피를 다 마시고 객실로 올라옴'), ('VISTA_ROOM', 'VISTA_POOL', '○ 객실 입실 후 저녁에 수영장'), ('VISTA_POOL', 'THE_BUFFET', '○ 수영은 첫날 저녁, 조식은 다음 날 아침')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '◎ 다음 날 7시 10분쯤 더뷔페 조식')]
