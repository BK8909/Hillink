"""
blog20 — 정답 확인본 (소연). 자동 추출 초안 persona_blog20_auto.py 를 원문 r055 와 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용

정답 확인: 소연 · 9/28 · 15분 · 보류 2건

초안이 셋 중 가장 정확했다. 방문지 · 주차 · 카페 처리(장소 코드가 없어 UNREACHABLE)까지 원문과 맞다.
고친 건 인원 하나다.

party_size 4 → 2. 원문에 동행 성인이 한 번도 나오지 않는다. 글은 아이와 둘이 다녀온 나들이로 시작하고
화자는 끝까지 보호자 한 사람이다. 초안은 아이를 가리키는 복수 표현과 "우정사진" 으로 동행자 한 쌍을
더 추정했는데, 둘 다 아이 하나를 가리킬 수도 있는 표현이라 두 단계 추정이 된다.
확실한 건 성인 1 + 영유아 1 이라 2 로 두었다.

보류: facts.party_size — 위 이유로 2 로 두었지만 복수 표현과 "우정사진" 을 근거로 4 로 볼 여지도 있다.
      인원은 동선(식당 좌석 · 시설 정원)에 영향이 크니 팀 기준이 필요하다
보류: TRUTH_MEALS — 카페에서 패키지 음료와 파운드케이크를 먹었다. 음료만이면 끼니가 아니지만
      케이크가 있어 간식으로 볼 여지가 있다. 다만 그 카페에 장소 코드가 없어 적을 자리가 없다
      (TRUTH_UNREACHABLE 의 "빛의 시어터 연계 카페"). 카페 노드가 생기면 다시 본다

성향(TRAIT_EVIDENCE)은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 31, 13, 30)      # ◎ 날짜(전시 마지막 날 8/31) · △ 시각은 적히지 않아 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 빛의 시어터 전시 방문",
    "nights": "◎ 전시·카페만 이용한 비투숙",
    "party": "◎ 작성자와 영유아 1 — 동행 성인은 원문에 없음 (초안의 4인은 두 단계 추정이라 2 로 고침 · 보류)",
    "included_meals": "◎ 입장권+에이드 패키지로 음료는 티켓 포함이나 전시 연계 카페는 장소 코드 목록에 없음",
    "booked": "◎ 네이버로 성인입장권+음료 패키지 미리 구매",
    "arrival": "○ 지하 주차장이 입구와 연결, 관람객 주차 할인 안내 → 자차 직접 주차",
    "depart_by": "△ 오래 관람하는 전시가 아니라는 언급 + 카페 들름 → 이용 끝 무렵 추정",
    "room_minimal": "비투숙"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (카페만 이용)'),
    '조망 중시': (0.5, '◎ 카페에서 비 오는 한강뷰에 잠깐의 힐링이었다고 적음'),
    '새로움 추구': (0.75, '◎ 핫한 신상 나들이 장소가 뜨면 바로 가 봐야 직성이 풀린다며 전시 마지막 날 일부러 찾아감'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (잔잔하고 조용히 관람할 수 있었다는 공간 묘사만)'),
}

PERSONA = Persona(
    name='blog20 · 비투숙 · 빛의 시어터 전시 · 아이 동반',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=True,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(15, 30),
    included_meals=(),
    booked=('THEATRE_OF_LIGHT',),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "THEATRE_OF_LIGHT": "◎ 입장해 1·2층, 분장실, 거울룸, 게임룸 등을 돌며 관람",
    "PARKING_TOWER_B1": "○ 지하 주차장에 주차해 호텔 입구로 바로 연결"
}
TRUTH_PASSED: dict[str, str] = {
    "THEATRE_ART_SHOP": "◎ 전시 나오는 길 소품샵 옆 사진부스만 이용, 소품샵 이용 언급 없음"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "CU_THEATRE": "○ 편의점 가는 통로의 유아휴게실 안내만, 이용 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "GRAND_LOBBY": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 시어터 연계 카페": "◎ 전시 보고 나와 카페에서 패키지 음료와 파운드케이크",
    "사진부스(소품샵 옆)": "◎ 방문 기념 사진 촬영"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
# 체크리스트 ③ — 쌍은 **머문 곳끼리만**. 주차타워는 도착 동선이라 뺀다
# (blog19 에서도 주차타워→로비 쌍을 같은 이유로 뺐다). 이 글은 전시 한 곳이라 남는 쌍이 없다.
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = []
