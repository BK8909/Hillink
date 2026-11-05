"""
blog39 — 정답 확인본 (소연). 자동 추출 초안 persona_blog39_auto.py 를 원문 r041 과 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 개발용

정답 확인: 소연 · 15분 · 보류 2건

고친 것 둘.
  · 수영장 — 지나감에서 안 감으로. "수영할 생각 없었음 그래서 그냥 구경만하고 패스함" 이라
    이용하지 않은 것이 적혀 있다. 근거는 원문 명시(마름모)다
  · CU 편의점 — "호텔 내 편의점도 있고" 라는 언급뿐이라 어느 칸에도 넣지 않았다 (규칙 1)

그대로 둔 것
  · 로비는 지나감. 배달을 로비 문 밖에서 받고 조식 뒤 전시 앞에서 사진만 찍었다 — 머문 서술은 없다
  · 헬스장 · 도서관은 그랜드 투숙이라 노드(FITNESS · GRAND_LIBRARY)와 건물이 맞다
  · 배달 음식(닭강정)과 밖에서 사 온 와인은 끼니에 넣지 않았다 (규칙 4)

보류: TRUTH_VISITED 의 더뷔페 — 원문은 "여유롭게 조식을 먹고" 뿐이고 장소 이름이 없다.
      그랜드 투숙객의 조식이라 더뷔페로 둔 초안을 유지했지만 원문 근거는 아니다
보류: 시작 날짜 — "올해 간건아니지만 저장만해두고 안올렸길래", "재작년에 간듯?" 이라 글 작성일과
      2년 가까이 차이 난다. 정확한 날짜가 없어 초안의 작성일을 그대로 두었다
      → 10/11 소연: 2024-09-04 로 옮겼다. 체크리스트 시기 규칙 ("두 달 전" → 작성일에서 뺀 날) 대로
        "재작년" → 작성일 2026-09-04 에서 2년. 원문의 전시 "베르메르부터 반고흐 까지" 는 빛의 시어터가
        2024-05-24 에 연 전시라 (보도 · 다음 전시는 2025-05-01 개막) 해가 맞는다. 일자는 근거가 없다 (보류).
        작성일로 두면 2026 운영사 공지의 9/1~9/9 전시 교체 휴관에 걸려 정답의 전시 관람이 안 된다

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2024, 9, 4, 14, 30)      # 날짜 ○ '재작년에 간듯?' → 작성일(2026-09-04) 에서 2년 · 전시 '베르메르부터 반고흐 까지' (2024-05-24 개막) · 일자 보류 (소연 10/11) · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울 트윈룸 (숲뷰를 보려고 골랐다 — 객실 뷰는 안 적힘)",
    "nights": "◎ 2박 3일",
    "party": "○ 트윈룸 — 2인 추정, 아이 동반 언급 없음",
    "included_meals": "○ 조식 포함 여부 언급 없음 → 비움",
    "booked": "◎ 빛의 시어터는 현장에서 방에서 예매 — 사전 예약 아님",
    "arrival": "○ 오기 전 근처에서 와인 구입 · 도착 수단 언급 없음",
    "room_minimal": "◎ 방에서 영화 보며 쉬는 등 객실 체류 많음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (0.25, '○ 저녁은 호텔 식당 대신 근처에서 산 와인과 배달 닭강정으로 해결'),
    '조망 중시': (0.75, '◎ 뻔한 한강뷰가 지겨워 숲뷰를 보려고 찾다가 그랜드 워커힐을 고름'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.75, '◎ 주변 객실 소음에 참다가 프런트에 전화 · 방음 때문에 다신 안 갈 듯이라고 적음'),
}

PERSONA = Persona(
    name='blog39 · 그랜드 트윈 2박 · 숲뷰 · 빛의 시어터·헬스장·도서관 · 방음 불만',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=2,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 트윈룸 2박, 방에서 쉬고 영화 봄",
    "THEATRE_OF_LIGHT": "◎ 방에서 전시 예매하고 바로 보러 가 사진 찍고 즐김",
    "FITNESS": "◎ 저녁에 헬스장에 가서 운동함 (시설 낡았다고 불만)",
    "GRAND_LIBRARY": "◎ 다음날 조식 후 도서관에 가서 책을 읽음",
    "THE_BUFFET": "○ 다음날 여유롭게 조식을 먹음 (식당 이름 명시 없음 → 더뷔페 추정)"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ 배달을 로비 문 밖에서 받고, 조식 뒤 로비 전시 앞에서 사진만 찍음 — 머문 서술은 없다",
}
# CU 편의점은 "호텔 내 편의점도 있고" 라는 언급뿐이라 어느 칸에도 넣지 않았다 (규칙 1)
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "◎ '수영할 생각 없었음 그래서 그냥 구경만하고 패스함' — 이용하지 않았다고 적혀 있다",
    "GRAND_FRONT_DESK": "○ 소음 때문에 프런트에 전화만 함, 방문 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음 (산책로 언급은 일반 소개)",
    "RIVERPARK": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'THEATRE_OF_LIGHT', '◎ 방에서 쉬다가 예매하고 바로 보러 감'), ('THEATRE_OF_LIGHT', 'FITNESS', '○ 첫날 전시 후 저녁에 헬스장 (서술 순서)'), ('FITNESS', 'GRAND_LIBRARY', '◎ 첫날 저녁 헬스장, 다음날 도서관'), ('THE_BUFFET', 'GRAND_LIBRARY', '◎ 다음날 조식을 먹고 도서관에 감'), ('FITNESS', 'THE_BUFFET', '○ 첫날 저녁 헬스장, 다음날 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '○ 다음날 여유롭게 조식을 먹음 (식당명 미기재, 더뷔페 추정)')]
