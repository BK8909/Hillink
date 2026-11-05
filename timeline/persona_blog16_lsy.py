"""
blog16 — 정답 확인본 (소연). 자동 추출 초안 persona_blog16_auto.py 를 원문 r014 와 대조해 고쳤다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용

정답 확인: 소연 · 9/28 · 18분 · 보류 3건

보류: START_AT 의 날짜 — "올해 하계 휴양소", "날씨 너무 좋규", "금욜" 로 여름 금요일인데
      초안은 2025-01-01 이다. 정확한 날짜가 없어 고치지 않았다.
      확인해 보니 이 후기가 쓰는 업장(비스타 수영장 · 스카이야드 · 피자힐 · 더뷔페)에는 시즌·연도
      창이 없어 **정답 타임라인 검증에는 영향이 없다.** 다만 두 군데에 걸린다 —
      에이전트가 후보를 고를 때(리버파크처럼 여름 시즌 창이 있는 곳은 1월이면 아예 안 열린다)와,
      나중에 계절별로 집계할 때다 (멘토링 질문 6번: 수집 후기의 96%가 8–9월이라 여름 쏠림)
보류: TRUTH_UNREACHABLE 의 비스타 피트니스 — 노드 FITNESS 는 그랜드 지하 2층이다(GRAND_LOBBY 8분).
      원문은 비스타 부대시설 안내지의 피트니스라 같은 곳이 아니다. 비스타 웰니스 클럽 노드가 없다
보류: TRUTH_UNREACHABLE 의 비스타 2층 도서관 라운지 — 노드 GRAND_LIBRARY 는 그랜드 2층이다.
      원문은 비스타 2층이고 "2층 창문으로 1층 발렛" 이라 비스타 로비 위다
      ※ 정답에서 뺐으므로 에이전트가 그랜드 쪽 노드에 가면 정밀 감점이 된다. 실제로는 같은 종류의
        시설을 이용했으니, 노드가 생기기 전까지 이게 맞는지 팀 확인이 필요하다.
→ 10/11 소연: 위 보류는 9/29 합본 persona_blog16.py 에서 정리됐다 — 피트니스는 VISTA_FITNESS 로 옮겼고
  라이브러리는 GRAND_LIBRARY 그대로다. 원문은 "도서관 2층에 도서관 라운지가 있다" 로 건물을 적지 않았다
  ('비스타 2층' 은 투숙 건물로 미룬 내 추정이었다). 이 파일은 1차 일치율 기록이라 칸은 그대로 두고,
  인용만 원문 글자로 고쳤다

성향(TRAIT_EVIDENCE)은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 20)      # 시각 ◎ '14시 20분쯤 비스타워커힐 로비에 도착' · 날짜 △ (보류)

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
    '새로움 추구': (1.0, "◎ 부대시설 설명지를 '다 즐겼다', '부대시설이 많아 즐기려면 누워서 TV 볼 시간이 없서~', 피자힐도 '궁금해서 먹어본'"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (수영장 레인이 여유로웠다는 공간 묘사뿐)'),
}

PERSONA = Persona(
    name='blog16 · 비스타 1박 · 2인 (회사 휴양소)',
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
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_LOBBY": "◎ 14:20쯤 비스타 로비 도착, 체크인 대기",
    "VISTA_ROOM": "◎ 11층 디럭스 트윈 리버뷰 객실 투숙",
    "VISTA_POOL": "◎ 롯데타워 보면서 수영, 레인 여유로웠음",
    "PIZZA_HILL": "◎ 로비 키오스크로 셔틀 호출해 피자힐에서 콤비네이션 피자 먹음",
    "SKYARD": "◎ 스카이야드 족욕, 발이 매끈해짐",
    "THE_BUFFET": "◎ 다음날 조식 1부에 더뷔페에서 조식 3그릇"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    # 사우나 · 발렛은 초안이 TRUTH_PASSED 로 뒀는데, 지나간 곳이 아니라 **안 간 곳**이다.
    # "안 갔다" 고 적힌 건 아니라 ◎ 가 아니라 ○ 로 둔다 (체크리스트의 ◎ 기준).
    "WELLNESS_SAUNA": "○ 이용권 55,000원 · '탕이 6-7개 있다고 한다', '시설 최고일듯' — 전해 들은 말뿐",
    "VALET_DESK": "○ 2층 창문으로 남이 발렛하는 것을 구경만 — 본인이 발렛을 썼다는 서술 없음",
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
TRUTH_UNREACHABLE: dict[str, str] = {
    "비스타 3층 웰니스 클럽 피트니스": "◎ 탈의실 직원이 운동복·라커 안내, 만족도 최고 — 노드 FITNESS 는 그랜드 지하 2층이라 다른 곳",
    "비스타 2층 라이브러리": "◎ 소파에 앉아 창밖으로 1층 발렛 구경 — 노드 GRAND_LIBRARY 는 그랜드 2층이라 다른 곳",
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'VISTA_POOL', '○ 체크인 후 부대시설 이용'), ('VISTA_ROOM', 'PIZZA_HILL', '○ 체크인 후 저녁에 셔틀로 피자힐'), ('PIZZA_HILL', 'THE_BUFFET', "◎ '전날 피자 4.5조각 먹고' 다음날 조식")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '○ 전날 피자 4.5조각 · 밤에 셔틀 이용 언급 → 저녁'), ('조식', 'THE_BUFFET', '◎ 다음날 조식 1부 7시쯤 더뷔페')]
