"""
blog42 — 정답 확인본 (소연). 자동 추출 초안 persona_blog42_auto.py 를 원문 r019 와 대조했다.
**시험용** — 정답 확인까지만 하고 에이전트는 돌리지 않았다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 시험용

정답 확인: 소연 · 18분 · 보류 4건

정답(TRUTH)은 고칠 게 없었다. 연작 네 편(숙박 · 클럽라운지 · 조식 · 포레스트파크 · 르파사쥬)이
한 체류이고, 초안이 다섯 곳을 모두 제대로 잡았다. 확인한 것만 적는다.

  · 조식은 비스타 1층 더뷔페가 맞다 — "주중(화~금)에는 조식이 비스타 1층 더뷔페에서 진행" 이라고
    원문이 직접 적었다. 그랜드 투숙인데 비스타 업장을 쓴 경우라 건물만 보고 고치면 안 된다
  · 르파사쥬는 그랜드 1층이고 원문이 "그랜드워커힐 1층에 위치" 라고 적었다 — 노드와 건물이 맞다
  · 포레스트파크는 차량을 호출해 갔고 입장 체크까지 받았다. 소개가 아니라 이용이다 (규칙 5)
  · 클럽라운지 티타임 · 해피아워를 끼니로 센 것은 규칙 4 그대로다

보류: 시작 시각 — 배정 문서가 "시각" 으로 표시한 곳이라 원문과 대조했다. 원문에 있는 시각은
      조식 쪽뿐이다 — "6시30분에 조식 먹으러 방에서 1층으로 내려왔습니다", "1부가 8시10분까지인데
      8시 조금 안되어서 다 먹고 나왔습니다". **도착 · 체크인 시각은 없다.** 그래서 START_AT 의
      14:30 추정을 그대로 두었다
보류: facts.nights — 박 수가 원문에 없다. 연작 어디에도 "1박" · "2박" 이 없어 초안의 1 을 두었다
보류: facts.party_size — 인원이 없다. 초안의 2 를 두었다
보류: facts.included_meals — 클럽스위트 투숙이고 클럽라운지를 썼지만 "포함" 이라고 적힌 문장이
      없어 비워 둔 초안을 유지했다. 1차 blog04 에서도 갈렸던 자리다 (클럽 객실이면 라운지 3종을
      자동으로 포함으로 볼지). 팀 기준이 필요하다

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 30, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐 클럽스위트룸 한강전망 숙박, '그랜드워커힐 호텔에 투숙하면서'",
    "nights": "△ 박 수 적히지 않음 → 1박 추정",
    "party": "△ 인원 적히지 않음 → 2인 추정; 포레스트파크를 '가족들과 같이 투숙하면서 이용하기 좋아보였습니다' 라고 제3자처럼 적어 아이 동반 아님으로 봄",
    "included_meals": "○ 조식 · 라운지 이용은 했으나 '포함' 이라는 문장 없음 → 비움",
    "club_access": "◎ '그랜드워커힐 클럽룸에 투숙하면서 클럽라운지 이용'",
    "arrival": "◎ '무료셔틀버스 이용' — 자차 아님 → null",
    "room_minimal": "○ 객실 체류를 줄였다는 서술 없음",
    "start_time": "○ 적힌 시각은 다음 날 조식(06:30)뿐이라 도착·첫 이용 시각이 아님 → 투숙 기본값"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, "근거 없음 → 미상 ('이른 아침이었지만 사람들이 많더라' 는 묘사뿐)"),
    '이동 최소화': (0.5, "○ 포레스트파크에 '처음 가는 곳이라 갈 때는 차량요청', '돌아올 때에는 도보로 약 5~10분정도 거리라 도보로 이동하였습니다' — 가까운 거리는 걸어서 감"),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (None, '근거 없음 → 미상 (한강전망 객실은 상품명일 뿐 고른 이유가 적히지 않음)'),
    '새로움 추구': (None, "근거 없음 → 미상 ('호텔오면 늘 조식 먹으려고 일찍 일어납니다' 는 습관이지 새로움 추구 아님)"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog42 · 그랜드 클럽룸 투숙 · 조식(더뷔페)·포레스트파크·르파사쥬 연작 후기',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 클럽스위트룸 숙박, '조식 먹으러 방에서 1층으로 내려왔습니다', 빵 '구매후 객실에 올라와서 맛있게 먹었습니다'",
    "GRAND_CLUB_LOUNGE": "◎ '그랜드워커힐 클럽라운지 이용후기(티타임, 해피아워)' · '클럽룸에 투숙하면서 클럽라운지 이용한 후기를' 별도로 올렸다고 명시",
    "THE_BUFFET": "◎ 06:30 방에서 내려가 비스타 1층 더뷔페에서 조식 (착석 시각은 없다), 8시 조금 전에 다 먹고 나옴",
    "FOREST_PARK": "◎ '그랜드워커힐 호텔에 투숙하면서 포레스트 파크를 이용하였습니다', 입장 체크 후 이용",
    "LE_PASSAGE": "◎ '호텔 투숙하면서 빵을 구매하였습니다' — 쿠키·단팥빵 구매"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ '호텔 입구에서 차량을 요청' — 포레스트파크 차량 호출 위해 통과"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음 (차량 호출 목적지 목록에만 등장)",
    "MYONGWOLGWAN": "○ 언급 없음 (차량 호출 목적지 목록에만 등장)"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'THE_BUFFET', "◎ '조식 먹으러 방에서 1층으로 내려왔습니다'"), ('GRAND_CLUB_LOUNGE', 'THE_BUFFET', '○ 티타임·해피아워(첫날 오후·저녁) 이용 후 다음 날 아침 조식'), ('GRAND_ROOM', 'LE_PASSAGE', '○ 투숙 중 빵 구매 후 객실로 돌아옴 — 체크인이 먼저'), ('GRAND_ROOM', 'FOREST_PARK', "○ '투숙하면서' 이용 — 체크인이 먼저")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', '◎ 더뷔페 조식 1부 이용 (06:30 방에서 나섬 · 8시 조금 전 나옴)'), ('간식', 'GRAND_CLUB_LOUNGE', '○ 클럽라운지 티타임 이용 후기를 별도로 올렸다고 명시'), ('석식', 'GRAND_CLUB_LOUNGE', '○ 클럽라운지 해피아워 이용 — 저녁 끼니로 추론'), ('간식', 'LE_PASSAGE', '◎ 쿠키·단팥빵 구매 후 객실에서 먹음 (포장)')]
