"""
blog43 — 정답 확인본 (소연). 자동 추출 초안 persona_blog43_auto.py 를 원문 r023 과 대조해 고쳤다.
**시험용** — 정답 확인까지만 하고 에이전트는 돌리지 않았다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 시험용

정답 확인: 소연 · 19분 · 보류 없음

고친 것 둘.
  · 더뷔페 — 지나감에서 안 감(◎)으로. 원문은 안내만이 아니라 **실제로 갔다가 포기한** 기록이다.
    "차량 호출해서 왔는데 이미 9시가 좀 넘은 시간인데 대기가 대기가... 기다리다가 10시 되겠더라구요ㅠㅠ
    다시 급하게 더글라스 라운지로" — 체크리스트가 ◎ 의 예로 든 "대기가 길어 포기" 그 자체다.
    (처음에 "안내만" 으로 잘못 읽어 고쳤다가 원문을 다시 보고 되돌렸다)
  · 순서 쌍에서 로비에서 객실로 가는 쌍 제거 — 로비는 체크인 절차 안쪽이다 (규칙 3)

확인한 것
  · 혼자다. 온전히 본인 시간을 보냈다는 서술만 있고 동행자가 한 번도 나오지 않는다 —
    초안의 1인이 맞다 (배정 문서가 "혼자인지 추정" 으로 표시한 곳)
  · 아이 동반 아님이 확실하다. 더글라스는 만 13세부터 입장이라 원문도 "노키즈존" 이라고 적었다
  · 포함 끼니는 더글라스 라운지의 조식 · 석식(더글라스 아워)으로 두었다 — 체크리스트 1장의
    "더글라스 = 라운지 포함" 그대로다
  · 날짜와 시각이 원문에 있다. "9월 첫 시작", "9월 시작날엔 비가 왔었거든요" 로 9월 1일이고,
    "주차하고 세시 반 정도에 왔는데" 로 15:30 이다. 새 추출기가 둘 다 제대로 잡았다
  · 주차는 "주차하고" 한 마디뿐이라 주차타워를 넣지 않았다 (규칙 1 — 주차 자체를 서술해야 방문)

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 1, 15, 30)      # 날짜 ◎ 후기 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ '워커힐 더글라스 하우스에 숙박하러 왔어요' · 디럭스 마운틴뷰 더블룸",
    "nights": "○ 체크인 당일 밤 '굿나잇' 후 다음 날 조식·체크아웃 → 1박",
    "party": "△ 동행자 언급 전혀 없음, '온전히 종일 제 시간을' · 노키즈존 성인전용이라 아이 미동반",
    "included_meals": "◎ 더글라스 투숙 → 라운지 라이트 스낵·더글라스 아워·조식 포함 (더뷔페 조식은 인당 추가금)",
    "room_minimal": "○ 객실 미니바·테라스·욕실을 길게 즐김 → 최소화 아님",
    "start_date": "○ '9월 첫 시작', '9월 시작날엔 비가 왔었거든요' → 9월 1일 방문",
    "arrival": "○ '주차하고 세시 반 정도에 왔는데' — 발렛 언급 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, "◎ 추가금 내고 더뷔페 조식 가려 차량 호출해 갔으나 대기가 길어 '기다리다가 10시 되겠더라' 포기하고 더글라스 라운지로 돌아감"),
    '이동 최소화': (None, '근거 없음 → 미상 (차량 호출로 더뷔페까지 이동함)'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.5, "○ 라운지에서 '비 내리는 한강 뷰 바라보며 앉아있으니 그래두 좋네요', 라이브러리 숲뷰 좋았다 — 좋았다 정도"),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.75, "◎ '수영장, 짐도 이용가능하지만 … 조용한 공간에서 휴식에만 집중' — 조용함을 이유로 부대시설을 건너뜀"),
}

PERSONA = Persona(
    name='blog43 · 더글라스 1박 · 혼자(추정) 휴식 호캉스',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=1,
    has_child_under_13=False,
    nights=1,
    property='DOUGLAS',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'DOUGLAS_LOUNGE'), ('석식', 'DOUGLAS_LOUNGE')),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로",
)

TRUTH_VISITED: dict[str, str] = {
    "DOUGLAS_LOBBY": "◎ 더글라스 하우스 로비 도착, 키 받아 객실로",
    "DOUGLAS_ROOM": "◎ 디럭스 마운틴뷰 더블룸 투숙, 미니바 이용",
    "DOUGLAS_LOUNGE": "◎ 라이트 스낵(15~17시), 더글라스 아워(19~21시) 와인·치즈, 다음 날 조식을 라운지에서 먹음",
    "DOUGLAS_LIBRARY": "◎ '조식먹고 체크아웃 하기 전 잠시 들른 라이브러리'"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ 주차 후 도착한 로비가 붐볐다 — 이후 차량 호출로 더글라스로 이동, 머문 기록 없음",
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 조식을 먹으러 차량을 호출해 갔으나 9시 넘어 대기가 길어 포기하고 더글라스 라운지로 돌아왔다 — 체크리스트의 ◎ 예시('대기가 길어 포기')에 해당",
    "GRAND_POOL": "◎ '수영장, 짐도 이용가능하지만 … 휴식에만 집중'",
    "VISTA_POOL": "◎ '수영장, 짐도 이용가능하지만 … 휴식에만 집중'",
    "FITNESS": "◎ '짐도 이용가능하지만 … 휴식에만 집중'",
    "RIVERPARK": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('DOUGLAS_ROOM', 'DOUGLAS_LOUNGE', "◎ 객실 구경 후 '스낵 타임 즐기러 라운지로'"), ('DOUGLAS_LOUNGE', 'DOUGLAS_LIBRARY', '◎ 다음 날 라운지 조식 먹고 체크아웃 전 라이브러리')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'DOUGLAS_LOUNGE', '◎ 라이트 스낵 타임에 쿠키·마카롱 등 가져와 먹음'), ('석식', 'DOUGLAS_LOUNGE', '◎ 더글라스 아워에 레드 와인 두 종·큐브 치즈 등'), ('조식', 'DOUGLAS_LOUNGE', '◎ 더뷔페 대기 포기 후 라운지 라이트 브렉퍼스트')]
