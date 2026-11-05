"""워커힐 고객 state machine — 24시간 타임라인 정합성 검증기.

docs/walkerhill-guest-state-machine.md §8(시간 모델) / §9(정합성) 의 실행 가능한 구현.

검사하는 불변식:
  I1 TIMELINE_REWIND        시계 되감기 금지
  I2 TELEPORT               세그먼트 간격 >= 이동 시간
  I3 OUTSIDE_WINDOW         [t_in, t_out] 이 운영 창 안, t_in <= L.O.
  I4 DOUBLE_BOOKED          물리적 위치는 한 시점에 하나
  I5 PRECONDITION_VIOLATED  전제 상태 선행 필요
  I6 DAY_BOUNDARY_VIOLATED  StayDay = [15:00, +1d 11:00]

출처 표기: 시간 상수는 walkerhillTravelTime / walkerhillVenueWindow 에서
OFFICIAL(공식 게시) / ESTIMATED(추정, 실측 교체 필요) 로 구분한다.


=========================================================================
소연 · 검증기 수정 내역
=========================================================================

과제: **공식 홈페이지를 기준으로** 블로그 후기를 상태 열로 바꾸고,
      **정합성 오류 0건**이 나오도록 검증기를 고친다.
      변환이 틀린 걸 검증기에서 고치면 검증기가 느슨해지므로 그 구분이 중요하다.

대상: 후기 2명 · 네 체류/방문 (blog03 2편 · blog04 2편)


── 회사 원본으로 돌린 결과 (재현) ──────────────────────────────────

  STAY_A  (비스타 1박)     KeyError 'VISTA_ROOM -> VISTA_POOL'
  STAY_B  (그랜드 1박)     KeyError 'HOTEL_GATE -> VALET_DESK'
  VISIT_A (리버파크 비투숙) KeyError 'HOTEL_GATE -> PARKING_TOWER_B1'
  VISIT_B (클럽스위트 1박)  위반 2건
      I3 GRAND_CLUB_LOUNGE 영업시간 외 이용 (운영 17:30~19:30 / 요청 16:10~17:00)
      I3 GRAND_CLUB_LOUNGE 영업시간 외 이용 (운영 17:30~19:30 / 요청 07:40~09:00)

  넷 중 셋은 **검증 자체가 안 된다.** 위반 목록이 나오는 게 아니라 멈춘다.


── A. 0건을 막고 있던 것 (3가지) ───────────────────────────────────

 1. 이동 매트릭스에 내 후기가 지나는 지점이 없어 검증이 멈췄다

    걸린 곳  VISTA_ROOM->VISTA_POOL · HOTEL_GATE->VALET_DESK ·
             HOTEL_GATE->PARKING_TOWER_B1
    수정     후기가 지나는 6개 노드만 넣었다 — VALET_DESK ·
             PARKING_TOWER_B1 · PIZZA_HILL · GRAND_POOL · VISTA_POOL ·
             SKYARD. 기존 21개 노드 사이 420쌍의 거리는 한 값도 안 바뀐다
             (selfcheck 안전장치 1 이 잰다).
    주의     분(分) 값은 층 정보만 공식이고 시간은 내 추정(△)이다.
             예외: PARKING_TOWER_B1->GRAND_LOBBY 4분은 회사 §8.4 값.


 2. 클럽라운지 창이 **해피아워 하나뿐**이라 티타임·조식이 반려됐다

    걸린 구간  IN_LOUNGE 04-15 16:10~17:00  -> I3
               IN_LOUNGE 04-16 07:40~09:00  -> I3
    후기       blog04 3편 — 티타임, 그리고 이튿날 아침 라운지 조식 (수요일은 추정 날짜)
    공식       클럽 라운지 운영시간 (2026-09-22 확인)
                 Breakfast 07:00 ~ 10:00
                 Tea Time  13:00 ~ 17:00
                 Happy Hour 17:30 ~ 19:30
    수정       공식 세 창으로 나눴다.
    참고       조식 장소는 공식이 '월~금 더뷔페 / 주말·공휴일 클럽라운지'
               인데, '주중에도 운영 상황에 따라 조식 장소 및 시간이 변경될
               수 있습니다' 라는 단서가 있다. 수요일 라운지 조식은 그 안에
               들어가므로 후기대로 두었다.


 3. 르파사쥬가 **매장 시간과 주문 접수 시간을 한 창**에 뭉쳐 놨다

    걸린 구간  BROWSING  08-04 19:25~19:50 -> I3 (운영 11:00~19:30)
               PICKED_UP 08-04 19:50~19:55 -> I3 (운영 11:00~19:30)
    후기       blog03 1편 — 'TOGO 주문 마감은 오후 7시 30분 … 아슬아슬하게
               성공했는데' / '피자를 기다리는 동안 케이크도 구경했습니다'
               주문과 수령이 다른 시각이다.
    공식       르 파사쥬 페이지 (2026-09-22 확인) 에 둘이 따로 적혀 있다
                 영업시간              연중 09:00 ~ 21:00
                 테이크아웃 피자 주문시간  11:00 ~ 19:30
    수정       `VenueWindow.states` 를 넣어 한 업장 안에서 행위별 창을
               나눴다. 매장 창만 넓히면 반대로 09:30·20:00 **주문**까지
               통과해서 느슨해진다. 변환도 주문·대기·수령을
               TAKEOUT_ORDER · BROWSING · PICKED_UP 으로 갈랐다.


── B. 0건과는 무관하지만 **공식과 값이 달랐던 것** ─────────────────

 4. 피자힐 운영 시간

    등록값  11:30~22:30 · L.O. 21:00
    공식    PIZZA HILL 이용안내 > 영업시간 (2026-09-22 확인) · 회차제 8부
              1부 11:00~12:30 … 7부 20:00~21:30  8부 21:30~23:00
    재현    11:00~12:00 (공식 1부)      -> FAIL
            22:00~23:00 (공식 8부 구간) -> FAIL
    수정    **운영 시간만** 11:00~23:00 으로 맞췄다. L.O. 는 공식에 표기가
            없어 회사 값 21:00 을 그대로 둔다 — 8부가 21:30 에 시작하니
            어긋나 보이지만 그건 내 추론이다. 회차도 모델링하지 않는다.

    ※ 내 후기 시각(19:35~20:10)은 원본에서도 통과해서 **후기로는 안 보였다.**
      공식 페이지를 다시 확인하다 찾았다.
    ※ 여기서 내가 한 번 틀렸다. 처음엔 근거 없이 22:00 으로 좁히고
      ◎(공식) 으로 표시했다. 출처 표기는 이런 걸 막으려고 있는 건데
      내가 그걸 어겼다.


── C. 원본에 **없어서** 채운 것 ────────────────────────────────────

  아래는 틀린 판정을 내던 게 아니다. 원본이 그 장소를 아예 안 다뤄서
  **무조건 통과**시키고 있었다. 채우면 검사가 엄격해지는 쪽이다.

 5. 부대시설(수영장·SKYARD)에 운영 창이 없어 새벽 3시 이용도 통과했다.
    공식 값으로 넣었다. ※ 2026-09-22 에 해당 안내 페이지를 다시 찾지
    못해 **재확인 안 됨**으로 남긴다(selfcheck 대조표에 표시).

 6. 리버파크는 노드는 있는데 운영 창이 **0개** 였다. blog04 2편의
    중심 장면이라 채우지 않으면 그 방문이 통째로 무검사가 된다.
    공식에 2023 시각이 없어 2023년 현장 요금표를 쓰고 ESTIMATED(△) 로 표시했다.
    (2026 시각은 공식 리버파크 페이지에 있다 — 아래 D.8, 10/5 에야 찾았다.)
    채우고 나니 시즌·연도·퇴장 유예가 필요해져 함께 넣었다
    (`season` · `years` · `exit_grace_min`).

    ※ 이 기능들을 넣으면서 내가 만든 버그는 내가 고쳤고, 원래 검증기의
      결함이 아니라서 여기 자세히 적지 않는다. 코드의 가드 주석에 있다.


── D. 10/5 · 요일 기능 — 더뷔페 평일 창 · 리버파크 2026 창 ────────────

  경수 요청. 가정표에 근거가 이미 있던 두 곳이다.

 7. 더뷔페에 **주말 슬롯 6개만** 있었다 (B 처럼 값이 틀린 게 아니라 절반만 있었다).
    평일 정오 뷔페가 반려되고, 평일에도 주말 2부제 시각으로만 들어갔다.
    공식 "운영시간 및 가격" 표 (10~11월 · 12월, 2026-10-05 다시 확인) 를
    요일 · 공휴일과 함께 전부 넣었다. 공식 공지 이미지의 2026 여름 조식
    매일 2부제 (7/17~8/31) 와 매년 12월 석식 매일 2부도 넣었다 (공식 페이지
    웹 보관본 2023 · 2024 · 2026 에 모두 있다 — 지난 해 표와의 차이는 창 주석).
    창에 `weekdays` · `holidays` · `closed` 를 더했다 (VenueWindow 주석).

 8. 리버파크에 2023 년 창만 있어 2026 년 어느 날도 열리지 않았다
    (`generate.py --date 2026-07-18` 의 리버파크 매출 0).
    공식 리버파크 페이지의 2026 시간표를 넣었다 — 블루 6/26~7/16 매일 ·
    골드 7/17~8/30 월~목 통운영 · 금~일 1부 · 2부. 가정표 · 상품표 리버파크 줄도 같은 근거로 고쳤다.

  ※ 회사 §9.5 예제 두 개의 결과가 바뀐다. 예제 날짜가 2026-09-21(월) ·
    22(화) 인데, 공식표로는 화요일 조식이 **2부제가 아니라 07:00~10:00 한 번**,
    월요일 중식이 12:00~14:30 이다.
      뷔페 슬롯 불일치 (화 08:00 조식)  I3 → 통과
      동시 착석 (월 13:30~15:30 중식)   I1 · I4 → I1 · I3 · I4
    예제가 지키려던 것 (2부제 날의 슬롯 사이 입장) 은 그대로 막힌다 —
    같은 예제를 하루 당겨 월요일 조식으로 두면 I3 다 (selfcheck · check_all).


── 여기 넣지 않은 것 ───────────────────────────────────────────────

  · `venue` 를 안 붙이면 창 검사가 생략되는 것. 회사가 필드 주석에
    '없으면 창 검사 생략' 이라고 **명시**해 둔 설계된 동작이다.
    위험하다고 본 건 내 판단이지 원본이 틀린 게 아니라서 되돌렸다.


── 결과 ────────────────────────────────────────────────────────────

  네 체류/방문 모두 **정합성 오류 0건** (I1~I6).
  회사 시나리오 5개의 결과는 원본과 같다 — selfcheck 가 매번 확인한다.
  남은 제약은 NOTES-soyeon.md 에 적었다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path


class SourceKind(Enum):
    """시간 상수의 출처. ESTIMATED 값은 SLA·고객 안내에 쓰면 안 된다."""

    OFFICIAL = "◎"  # walkerhill.com 공식 게시
    DERIVED = "○"  # 공식 운영시간에서 논리적으로 확정
    ESTIMATED = "△"  # 추정치 — 현장 실측으로 교체 필요
    REVIEW = "후기"   # 후기 작성자의 진술 — 그 방문에 대한 관측값. 공식 운영정책이 아님 (슬기 추가)


# --------------------------------------------------------------------------
# 이동 시간 (§8.3 외부 / §8.4 구내)
# --------------------------------------------------------------------------

CHECK_IN_TIME = time(15, 0)  # ◎ 전 프로퍼티 공통
CHECK_OUT_TIME = time(11, 0)  # ◎

# 피크 시간대에는 구내 수직 이동이 2배가 된다 (엘리베이터 혼잡).
PEAK_RANGES = ((time(7, 0), time(9, 0)), (time(15, 0), time(17, 0)))
PEAK_MULTIPLIER = 2

# 더글라스 하우스는 차량 진입 불가 ◎ — 셔틀 호출 대기가 항상 붙는다.
DOUGLAS_SHUTTLE_CALL_WAIT_MIN = 5  # △


@dataclass(frozen=True)
class ExternalLeg:
    """외부 교통편 한 구간. 배차가 있으므로 대기 + 승차로 분해된다."""

    ride_min: int
    headway_min: int
    first_departure: time
    last_departure: time
    source: SourceKind

    def expected_wait_min(self) -> float:
        """균등 도착 가정 하의 기대 대기 시간."""
        return self.headway_min / 2

    def total_min(self) -> float:
        return self.expected_wait_min() + self.ride_min


# 무료 셔틀 10분 배차 구간 ◎ — 그 외 시간대는 15분.
FREE_SHUTTLE_DENSE_RANGES = (
    (time(6, 0), time(7, 0)),
    (time(8, 0), time(9, 0)),
    (time(10, 0), time(13, 0)),
    (time(18, 0), time(18, 30)),
    (time(21, 0), time(21, 30)),
    (time(22, 0), time(22, 30)),
)


def free_shuttle_headway_min(at: datetime) -> int:
    """무료 셔틀 배차 간격. 예외 구간은 10분, 그 외 15분. ◎"""
    for start, end in FREE_SHUTTLE_DENSE_RANGES:
        if start <= at.time() < end:
            return 10
    return 15


WALKERHILL_EXTERNAL_LEGS: dict[tuple[str, str], ExternalLeg] = {
    ("ICN_T1", "HOTEL_GATE"): ExternalLeg(90, 30, time(5, 20), time(23, 15), SourceKind.OFFICIAL),
    ("ICN_T2", "HOTEL_GATE"): ExternalLeg(90, 30, time(5, 0), time(22, 55), SourceKind.OFFICIAL),
    ("HOTEL_GATE", "ICN_T1"): ExternalLeg(90, 30, time(4, 5), time(18, 50), SourceKind.OFFICIAL),
    ("HOTEL_GATE", "ICN_T2"): ExternalLeg(90, 30, time(4, 5), time(18, 50), SourceKind.OFFICIAL),
    ("GWANGNARU_STN", "HOTEL_GATE"): ExternalLeg(8, 15, time(6, 0), time(23, 30), SourceKind.OFFICIAL),
    ("GANGBYEON_STN", "HOTEL_GATE"): ExternalLeg(15, 15, time(6, 0), time(23, 30), SourceKind.OFFICIAL),
}

# 구내 이동 매트릭스 (분). 전부 △ 추정치 — §10 미확보 데이터 참조.
WALKERHILL_INTERNAL_MATRIX: dict[str, dict[str, int]] = {
    # ── 소연 수정 1 · §8.2 에 있는데 §8.4 매트릭스에 없던 지점들 ──────────────
    #
    # 내 블로그 4개 체류 중 **3개가 검증 자체를 못 받았다.** 위반이 나오는 게 아니라
    # KeyError 로 실행이 멈춘다. 없는 지점을 지나면 "갈 수 없다" 가 아니라
    # "판정 불가" 가 되는 건데, 리포트에는 그 사실이 남지 않는다.
    #   VISTA_ROOM→POOL · HOTEL_GATE→VALET_DESK · GRAND_ROOM→PIZZA_HILL
    #   POOL→SKYARD · HOTEL_GATE→PARKING_TOWER_B1
    #
    # 층 정보는 공식 홈페이지에서 가져왔고, **분(分) 값은 전부 내 추정 △** 이다.
    # 회사 실측이 오면 통째로 교체한다.
    "HOTEL_GATE": {"GRAND_LOBBY": 3, "VISTA_LOBBY": 6, "VALET_DESK": 1,
                   "PARKING_TOWER_B1": 5},
    # blog03 후기: "차량에서 캐리어를 꺼내고, 카드사 혜택으로 발렛을 무료로 이용했습니다"
    "VALET_DESK": {"HOTEL_GATE": 1, "GRAND_LOBBY": 2},
    # **이 구간은 내 추정이 아니다.** 회사 §8.4 의 다른 표에 이미 있었다:
    #   "`PARKING_TOWER_B1` → `GRAND_LOBBY` | 호텔 연결통로 ◎ | 4분 △ |
    #    24시간 △ | 짐 많을 때 권장 경로 ◎"
    # HOTEL_GATE→PARKING_TOWER_B1 5분만 내 추정 △ 이다.
    #
    # blog04 1편은 이걸 B3 라고 부른다:
    #   "주차타워 B3층에 주차하면 호텔 입구와 바로 이어져있어"
    #   "주차타워 지하 3층은 호텔 지하 1층과 연결되어 있어요"
    # 두 건물의 층 번호 기준이 다른 것으로 보인다. 노드 이름은 회사 것을 쓴다.
    "PARKING_TOWER_B1": {"HOTEL_GATE": 5, "GRAND_LOBBY": 4},
    # ── bk 추가 · §8.4 더글라스 주차타워 4F 계단 ◎ 06:00–22:00 · 시간 △ ──
    "PARKING_TOWER_4F": {"DOUGLAS_LOBBY": 5},
    "GRAND_LOBBY": {
        "GRAND_FRONT_DESK": 1, "GRAND_ROOM": 4, "GRAND_CLUB_LOUNGE": 5,
        "ONDAL": 3, "GEUMRYONG": 2, "LE_PASSAGE": 2, "THE_PAVILION": 1, "LUX_BAR": 5,
        "VISTA_LOBBY": 8, "VISTA_ROOM": 12, "ANNEX": 7, "DOUGLAS_LOBBY": 11,
        "RIVERPARK": 9, "FOREST_PARK": 10, "CONVENTION": 6, "HOTEL_GATE": 3,
        "VALET_DESK": 2, "PARKING_TOWER_B1": 4,
        # 공식: 그랜드 피트니스 센터 = 호텔 **지하 2층**
        "GRAND_POOL": 6,
    },
    "GRAND_FRONT_DESK": {"GRAND_ROOM": 4, "GRAND_LOBBY": 1},
    "GRAND_ROOM": {
        "GRAND_LOBBY": 4, "GRAND_FRONT_DESK": 4, "GRAND_CLUB_LOUNGE": 3,
        "ONDAL": 6, "GEUMRYONG": 5, "LUX_BAR": 4, "THE_PAVILION": 5,
        "VISTA_LOBBY": 12, "THE_BUFFET": 12, "ANNEX": 11, "DOUGLAS_LOBBY": 15,
        "RIVERPARK": 13, "FOREST_PARK": 14, "CONVENTION": 10,
    },
    "GRAND_CLUB_LOUNGE": {
        "GRAND_ROOM": 3, "GRAND_LOBBY": 5, "ONDAL": 12, "LUX_BAR": 1,
        "VISTA_LOBBY": 13, "THE_BUFFET": 13, "DOUGLAS_LOBBY": 16,
    },
    "ONDAL": {"GRAND_ROOM": 6, "GRAND_LOBBY": 3, "LUX_BAR": 12, "GRAND_CLUB_LOUNGE": 12},
    "LUX_BAR": {"GRAND_ROOM": 4, "GRAND_LOBBY": 5, "ONDAL": 12},
    "THE_BUFFET": {"GRAND_ROOM": 12, "VISTA_LOBBY": 2, "VISTA_ROOM": 4, "GRAND_LOBBY": 8},
    "VISTA_LOBBY": {
        "GRAND_LOBBY": 8, "VISTA_ROOM": 4, "THE_BUFFET": 2, "ANNEX": 5,
        "DOUGLAS_LOBBY": 19, "RIVERPARK": 6, "FOREST_PARK": 12, "CONVENTION": 10,
        # 공식: 비스타 웰니스 클럽 = 비스타 **3층** / SKYARD = 비스타 **4층**
        "VISTA_POOL": 5, "SKYARD": 6,
        "VISTA_FITNESS": 5,   # 웰니스 클럽 3층 — VISTA_POOL 과 같은 층 (아래 "소연 수정 · 9/29")
    },
    "VISTA_ROOM": {"VISTA_LOBBY": 4, "THE_BUFFET": 4, "ANNEX": 9, "GRAND_LOBBY": 12},
    # 별관은 진입점이고 피자힐은 그 안의 별도 노드다 (§8.2 [비스타] 항목).
    "ANNEX": {"GRAND_LOBBY": 7, "VISTA_LOBBY": 5, "RIVERPARK": 8, "FOREST_PARK": 13,
              "PIZZA_HILL": 1, "MYONGWOLGWAN": 1},
    "PIZZA_HILL": {"ANNEX": 1},
    # ── bk 추가 · §8.2 [비스타] 항목에 있는데 매트릭스에 없던 업장·시설 ───────
    #   분(分) 값은 전부 추정 △. 운영 창은 이미 §8.6 표에 있었다 (명월관·모에기).
    "MYONGWOLGWAN": {"ANNEX": 1},                       # 별관 내부 △
    "MOEGI": {"VISTA_LOBBY": 3, "THE_BUFFET": 3},        # 비스타 본관 △
    "FITNESS": {"GRAND_LOBBY": 8},                       # 그랜드 지하 2층 △
    "WELLNESS_SAUNA": {"GRAND_LOBBY": 9},                # △
    "GOLF_CLUB": {"GRAND_LOBBY": 12, "VISTA_LOBBY": 12}, # △
    "TENNEZ_PARK": {"VISTA_LOBBY": 11},                  # △
    # ── 슬기 추가 · 후기에 나오는데 §8.2 에도 없던 곳 (blog06: 빛의 시어터 · CU · 라이브러리) ──
    #   bk 의 blog01 도 같은 셋을 '빈 칸' 으로 남겨 뒀었다. 분(分) 값은 실행용 △.
    #   기존 노드 사이에 지름길을 만들지 않는 가지 연결.
    "THEATRE_OF_LIGHT": {"GRAND_LOBBY": 5},
    "THEATRE_ART_SHOP": {"THEATRE_OF_LIGHT": 1},
    "CU_THEATRE": {"THEATRE_OF_LIGHT": 1},
    "GRAND_LIBRARY": {"GRAND_LOBBY": 3},

    # ── 소연 수정 2 · 수영장은 **하나가 아니라 둘**이다 ─────────────────────
    #
    # 회사 노드 목록에는 `POOL` 이 하나뿐인데, 실제로는 별개 시설 두 곳이다.
    #
    # blog03 가 둘 다 묵고 직접 비교해 놓았다 (4부작 전편에 반복 수록):
    #   "수영장 — 비스타: 여기가 낫습니다. 한강뷰, 레인 2개, 야외 풀까지
    #             그랜드: 작고 실내 느낌이 강해 이용을 건너뛰었습니다"
    #   3편: "그랜드 수영장은 좀 작다는 느낌과 너무 실내 같은 분위기라서 …
    #         건너뛰고 스카이야드를 골랐습니다"
    #   1편: "수영장은 3층입니다" (비스타)
    #
    # 공식 홈페이지도 갈라 놓았다 — 그랜드 피트니스 센터는 **호텔 지하 2층**
    # (매월 세번째 화요일 휴관), 비스타 웰니스 클럽은 **비스타 3층**
    # (매월 둘째 주 수요일 휴관). 운영 시각도 휴관일도 다르다.
    #
    # 노드가 하나면 "비스타 3층에서 놀았다" 와 "그랜드 것을 보고 건너뛰었다" 가
    # 같은 장소가 되고, 이동 시간도 한 값으로 뭉친다. 그래서 갈랐다.
    # 같은 시설 안의 체련장·사우나는 **내 블로그가 지나지 않아** 넣지 않았다.
    # §8.2 에 있는데 매트릭스에 빠진 건 맞지만, 그건 그 시설을 지나는 후기를 맡은
    # 사람이 찾아야 할 몫이다. 미리 채워 두면 그 문제를 만날 기회를 뺏는다.
    "GRAND_POOL": {"GRAND_LOBBY": 6},
    "VISTA_POOL": {"VISTA_LOBBY": 5, "VISTA_FITNESS": 1},
    "SKYARD": {"VISTA_LOBBY": 6},

    # ── 소연 수정 · 9/29 · 피트니스도 **둘**이다 — 이제 후기가 지나가서 넣는다 ───────
    #
    # 위 "수정 2" 에서 비스타 웰니스 클럽의 체련장을 **후기가 지나지 않아** 넣지 않았다.
    # 정답 확인 1 · 2차에서 개발용 후기 세 편이 지나갔다 (시험용은 근거로 쓰지 않았다 — 봉인 대상):
    #   blog19  "3층 웰니스 센터 - 피트니스 클럽, 수영장 … 바로 옷 갈아입고, 웰니스 센터"
    #           "피트니스 클럽은 06:00 - 22:00 이고" ← 아래 운영 창의 근거
    #   blog27  비스타 투숙 · "다음 날에는 호텔 내 헬스장에 갔어요" · 운동복 무료 대여
    #   blog45  비스타 투숙 · 비스타 피트니스클럽 이용, 휴대전화를 로커에 둠 (한호 정답 확인)
    # 회사 문서도 비스타 공통 특전에 "피트니스 & 실내 수영장 무료" 를 따로 적었다 (그랜드 특전과 별개).
    # 그랜드 것과 다른 시설이라는 방증 — 그랜드 투숙 blog39 는 헬스장이 "시설이 후져서 놀랐음 …
    # 너무 낡음" 이고, 비스타 blog19 는 "쾌적하고, 기구도 다양했습니다" 다.
    # 그동안은 FITNESS(그랜드 지하 2층)로 잘못 적거나 목록 밖에 뒀다.
    #
    # 수영장과 같은 3층 클럽 안이라 VISTA_POOL 과 1분으로 잇고, 로비까지는 VISTA_POOL 과 같은 5분 △.
    # 새 가지(leaf)라 기존 노드 사이 거리는 바뀌지 않는다 (selfcheck 안전장치 1).
    #
    # **넣지 않은 것 둘**
    #   · 사우나 — **가르지 않고 WELLNESS_SAUNA 하나로 둔다.** 몇 곳이고 어디인지 확정이 안 된다.
    #     회사 문서는 "웰니스 사우나" 를 그랜드 · 비스타 · 더글라스 패키지 모두에 같은 이름으로 넣었고
    #     노드도 하나다. 그런데 원문에는 가격 · 규모가 다른 사우나가 섞여 있다 —
    #       그랜드 blog21 "2만원 추가 결제" · "사우나의 크기가 작은 대신 온도가 높고"
    #       비스타 blog16 "지하1층의 사우나는 이용권 55,000원! (탕이 6-7개 있다고 한다, 시설 최고일듯)"
    #       비스타 blog29 "피트니스 센터와 온열 사우나를 이용할 수 있는 웰니스 클럽"
    #     비스타 투숙객이 사우나를 **이용한** 후기는 아직 0편이다(위 둘은 안내 · 소개).
    #     가를 근거가 없으니 하나로 두고, 이용 후기가 모이면 그때 가른다
    #     → 10/11 공식: 그랜드 피트니스 센터 · 비스타 웰니스 클럽 둘 다 사우나가 있다 (휴관 공지 둘 다 "실내수영장, 사우나,
    #       피트니스"). 그래도 하나로 둔다 — 시각은 둘 다 06:00~22:00 이고 (비스타는 VISTA SIGNATURE STAY 상세), 비스타 쪽
    #       요금 안내는 공식 페이지에서 숨겨져 (HTML 주석) 공식으로 못 쓴다. 노드는 그랜드 로비에 잇는다 — 운영 창 · 휴관일은
    #       그랜드 피트니스 센터 것 (아래 WELLNESS_SAUNA)
    #   · 비스타 라이브러리 — **따로 있다는 근거가 없다.** 비스타 투숙 blog19 가 부르는 이름이
    #     "2층 워커힐 라이브러리" 로, 그랜드 투숙 blog25 의 "워커힐 서울 2층에 라이브러리" 와 같은
    #     곳이다. 회사 문서 · 노드 목록에도 비스타 라이브러리는 없다. GRAND_LIBRARY 하나로 둔다
    "VISTA_FITNESS": {"VISTA_LOBBY": 5, "VISTA_POOL": 1},
    "DOUGLAS_LOBBY": {
        "DOUGLAS_ROOM": 2, "DOUGLAS_LOUNGE": 1, "DOUGLAS_LIBRARY": 1,
        "GRAND_LOBBY": 11, "VISTA_LOBBY": 19, "FOREST_PARK": 14,
        "PARKING_TOWER_4F": 5,
    },
    "DOUGLAS_ROOM": {"DOUGLAS_LOBBY": 2, "DOUGLAS_LOUNGE": 2},
    "RIVERPARK": {"GRAND_LOBBY": 9, "VISTA_LOBBY": 6, "FOREST_PARK": 11},
    "FOREST_PARK": {"GRAND_LOBBY": 10, "VISTA_LOBBY": 12, "DOUGLAS_LOBBY": 14},
    "CONVENTION": {"GRAND_LOBBY": 6, "VISTA_LOBBY": 10},
}

DOUGLAS_LOCATIONS = frozenset({"DOUGLAS_LOBBY", "DOUGLAS_ROOM", "DOUGLAS_LOUNGE", "DOUGLAS_LIBRARY"})


def is_peak(at: datetime) -> bool:
    return any(start <= at.time() < end for start, end in PEAK_RANGES)


def _internal_adjacency() -> dict[str, dict[str, int]]:
    """구내 매트릭스를 무향 그래프로 정규화한다 (양방향 동일 소요 가정)."""
    graph: dict[str, dict[str, int]] = {}
    for origin, edges in WALKERHILL_INTERNAL_MATRIX.items():
        for destination, minutes in edges.items():
            for a, b in ((origin, destination), (destination, origin)):
                current = graph.setdefault(a, {}).get(b)
                if current is None or minutes < current:
                    graph[a][b] = minutes
    return graph


_INTERNAL_GRAPH = _internal_adjacency()


def _internal_shortest_path_min(origin: str, destination: str) -> int:
    """구내 최단 경로. 매트릭스에 직접 간선이 없으면 로비 등을 경유한다.

    워커힐은 부지가 층·동으로 나뉘어 있어 임의의 두 지점이 직결되지 않는다.
    미등록 쌍을 에러로 만들면 타임라인이 검증 불가가 되므로, 등록된 간선으로
    실제 경유 동선을 계산한다.
    """
    if origin == destination:
        return 0
    if origin not in _INTERNAL_GRAPH or destination not in _INTERNAL_GRAPH:
        raise KeyError(f"이동 시간 그래프에 없는 지점: {origin} -> {destination}")

    import heapq

    best: dict[str, int] = {origin: 0}
    queue: list[tuple[int, str]] = [(0, origin)]
    while queue:
        cost, node = heapq.heappop(queue)
        if node == destination:
            return cost
        if cost > best.get(node, float("inf")):
            continue
        for neighbour, edge in _INTERNAL_GRAPH[node].items():
            candidate = cost + edge
            if candidate < best.get(neighbour, float("inf")):
                best[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour))

    raise KeyError(f"연결되지 않은 지점: {origin} -> {destination}")


def walkerhill_travel_time_min(origin: str, destination: str, departing_at: datetime) -> float:
    """§9.3 T(a, b, t). 외부 구간은 배차 대기를 포함한다."""
    if origin == destination:
        return 0.0

    leg = WALKERHILL_EXTERNAL_LEGS.get((origin, destination))
    if leg is not None:
        headway = (
            free_shuttle_headway_min(departing_at)
            if origin in ("GWANGNARU_STN", "GANGBYEON_STN")
            else leg.headway_min
        )
        return headway / 2 + leg.ride_min

    base = _internal_shortest_path_min(origin, destination)

    # 더글라스는 차량 진입이 안 돼 셔틀을 부른다 ◎. 다만 그건 **건물 사이** 이동일 때다.
    # 원본은 "어느 한쪽이라도 더글라스면" 이라 더글라스 객실 → 같은 건물 라운지(2분)에도
    # 5분이 붙고, 피크면 14분이 됐다 (blog02 조식 구간에서 드러남). 한쪽만 더글라스일 때로 고친다.
    if (origin in DOUGLAS_LOCATIONS) != (destination in DOUGLAS_LOCATIONS):
        base += DOUGLAS_SHUTTLE_CALL_WAIT_MIN  # 차량 진입 불가 → 셔틀 호출 ◎

    return base * PEAK_MULTIPLIER if is_peak(departing_at) else base


# --------------------------------------------------------------------------
# 운영 창 (§8.6)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VenueWindow:
    """업장 운영 창 하나. last_order 는 입장(주문 개시) 마감이다.

    ── 소연 수정 7 · 창에 두 가지를 더했다 ──────────────────────────────

    `season` — 이 창이 존재하는 기간 (월, 일, 월, 일). 비워 두면 연중.
        계절 시설은 **기간마다 운영 방식 자체가 다르다.** blog04 1편이 리버파크
        현장 요금표를 통째로 찍어 올렸는데 이렇게 생겼다.
            EARLY BLUE  2023.6.30~7.21   10:00~19:00 통운영
            GOLD        2023.7.22~8.20   2부제 (1부 10:00~14:30 · 2부 15:00~19:00)
            LATE BLUE   2023.8.21~8.27   10:00~19:00 통운영
        2부제를 연중으로 적으면 블루시즌에 14:30~15:00 를 쓴 하루가 멀쩡한데도
        반려되고, 통운영으로만 적으면 골드시즌 청소 시간이 뚫린다.
        기간을 안 달면 둘 중 하나는 반드시 틀린다.

    `years` — 이 시간표가 유효한 연도. 비워 두면 연도 무관.
        `season` 은 월·일만 비교하므로, 그것만으로는 **2023년 요금표가 2026년에도
        적용된다.** 근거가 특정 연도의 현장 게시물뿐이면 그 연도로 묶어야 한다.
        그러지 않으면 "연도 한정" 이라는 설명과 코드가 어긋난다.
        묶어 두면 다른 해에는 창이 하나도 안 열려 "해당 기간에 운영하지 않음" 이
        되는데, 그게 맞다 — 우리는 그 해 시간표를 모른다.

    `states` — 이 창이 적용되는 상태. 비워 두면 그 업장의 모든 상태.
        한 업장 안에서도 **행위마다 시간이 다르다.** 르 파사쥬는 매장이
        09:00~21:00 인데 피자 주문 접수는 11:00~19:30 이다. 주문을 마감 전에 넣고
        수령은 그 뒤에 하는 게 blog03 1편의 장면이다.
        상태별 창이 하나라도 있으면 그 상태는 **그 창들로만** 판정한다 —
        안 그러면 넓은 매장 창이 좁은 주문 창을 덮어 버린다.

    `exit_grace_min` — 마감 후 **퇴장**까지 주는 유예.
        슬롯 마감과 퇴장 완료는 다른 시각이다. blog04 2편:
        "골드시즌 1부가 2시 30분 마감인데요. 2시 30분까지 꽉꽉 채워 놀고선
         샤워실 가니까 다음 타임을 위해 2시 50분까지? 나와달라 하더라고요"
        **`EXIT_STATES` 에만 적용한다.** 상태를 안 가리면 이용 구간까지 늘어나
        `ENTERED 10:00~14:50` 이 통과한다 — 다음 타임 손님과 겹치는 하루다.

    ── 소연 수정 · 10/5 · 요일 · 공휴일 · 닫는 기간 ─────────────────────

    `weekdays` — 이 창이 여는 요일 (월=0 … 일=6). 비워 두면 매일.
        더뷔페는 같은 끼니라도 **요일마다 회차가 다르다** (공식표):
            중식  월~금 12:00~14:30  /  토 · 일 · 공휴일 1부 11:00~13:00 · 2부 13:30~15:30
        요일 없이 두 벌을 같이 넣으면 뭉쳐서, 토요일 13:00 입장 (1부 · 2부 사이)
        이 평일 통창 덕에 통과한다 — 회사 §9.5 `buffet_slot_mismatch` 의 구멍이다.

    `holidays` — 공휴일 처리. 상품표(menu.csv) `+공휴일 · -공휴일` 과 같은 뜻이다.
        '+' 공휴일이면 요일과 상관없이 연다 · '-' 공휴일이면 요일과 상관없이 닫는다 ·
        None 공휴일을 안 본다. 공휴일은 `PUBLIC_HOLIDAYS` 달력으로 판단한다.
        더뷔페 "토요일 ~ 월요일, 공휴일" 은 weekdays={토,일,월} · '+',
        "화요일 ~ 금요일" 은 그 공휴일 창과 같은 끼니라 '-' 다 (상품표와 같다).

    `closed` — 이 창이 **닫히는 날짜 구간** (시작일, 종료일 — 둘 다 포함).
        공식 공지가 그 해 한정으로 회차를 바꾼 경우다. 2026 여름 (7/17~8/31) 은
        조식이 매일 2부제라 평일 07:00~10:00 창이 닫힌다. `season` 은 월 · 일만
        비교해 해마다 같은 기간이 되므로 '그 해 그 기간만 빼고' 를 못 적는다.
        해마다 되풀이되는 기간 (12월 석식 매일 2부) 은 `season` 으로 적는다.

    판정은 전부 `opens_on` 안에서 한다 — 검증기와 에이전트(v2 · v3 · v4)가
    같은 함수를 부르므로 둘이 같은 날 같은 창을 본다.
    """

    open_at: time
    close_at: time
    last_order: time | None = None
    source: SourceKind = SourceKind.OFFICIAL
    season: tuple[int, int, int, int] | None = None
    years: frozenset[int] | None = None
    states: frozenset[str] | None = None
    exit_grace_min: int = 0
    weekdays: frozenset[int] | None = None
    holidays: str | None = None
    closed: tuple[tuple[date, date], ...] = ()

    def __post_init__(self) -> None:
        # 오타가 조용히 '매일 연다' 나 '안 연다' 가 되지 않게 막는다.
        if self.holidays not in (None, "+", "-"):
            raise ValueError(f"holidays 는 None · '+' · '-' 중 하나 (받은 값 {self.holidays!r})")
        if self.weekdays is not None and not (self.weekdays and self.weekdays <= frozenset(range(7))):
            raise ValueError(f"weekdays 는 0(월)~6(일) 의 비지 않은 집합 (받은 값 {set(self.weekdays)})")
        for a, b in self.closed:
            if a > b:
                raise ValueError(f"closed 구간의 시작이 끝보다 늦다 ({a} > {b})")

    def effective_last_order(self) -> time:
        return self.last_order or self.close_at

    def in_season(self, day: date) -> bool:
        """연도는 빼고 **기간(월·일)만** 본다. 실패 메시지를 가르는 데 쓴다."""
        if self.season is None:
            return True
        m1, d1, m2, d2 = self.season
        start, end, here = (m1, d1), (m2, d2), (day.month, day.day)
        if start <= end:
            return start <= here <= end
        return here >= start or here <= end   # 해를 넘기는 기간

    def on_day_rule(self, day: date) -> bool:
        """요일 · 공휴일 · 닫는 기간만 본다 (연도 · 기간은 빼고). 실패 메시지를 가르는 데 쓴다.

        공휴일 처리는 상품표 `menu.Menu.on_sale` 과 같은 순서다 — 공휴일이면 '+' 는 열고
        '-' 는 닫고, 아니면 요일로 본다.
        """
        if any(a <= day <= b for a, b in self.closed):
            return False
        if self.holidays is not None and is_public_holiday(day):
            return self.holidays == "+"
        return self.weekdays is None or day.weekday() in self.weekdays

    def opens_on(self, day: date) -> bool:
        if self.years is not None and day.year not in self.years:
            return False
        return self.in_season(day) and self.on_day_rule(day)

    def day_rule_text(self) -> str:
        """요일 규칙을 상품표 요일제한 표기로 — '화수목금-공휴일' · '금토일' · '매일'."""
        days = "".join("월화수목금토일"[i] for i in sorted(self.weekdays)) if self.weekdays else "매일"
        hol = {"+": "+공휴일", "-": "-공휴일"}.get(self.holidays or "", "")
        shut = "".join(f" · {a:%Y-%m-%d}~{b:%Y-%m-%d} 닫음" for a, b in self.closed)
        return days + hol + shut


# ── 공휴일 달력 · 소연 10/5 ─────────────────────────────────────────────
#
# 요일 창의 '+ · -공휴일' 이 쓴다. 상품표처럼 대체 · 임시 공휴일도 넣는다.
#   2026  menu.HOLIDAYS_2026 과 같아야 한다 — 「관공서의 공휴일에 관한 규정」(2026.5.1 시행)
#         · 우주항공청 2026 월력요항 (2025.6.30 · 천문연구원 게시 · 근거는 docs/상품표.md '공휴일 달력')
#   2025  우주항공청 2025 월력요항 (2024.6.20 발표 · 천문연구원 게시) + 임시공휴일 둘 —
#         1/27 (2025.1.14 국무회의 의결 · 인사혁신처) · 6/3 (제21대 대통령선거일, 2025.4.8 국무회의)
# selfcheck 가 둘 다 규정으로 다시 계산해 이 표와 맞춘다 (2026 은 menu.py 와도).
#
# **달력이 없는 해는 공휴일이 없는 것으로 본다** (요일로만 판단). 후기 체류가 걸친
# 그런 날짜는 21일이다 (10/5 · persona 시작일 + 박수 · 후기 타임라인에서 뽑음):
#   2019-02-09~10 · 2021-11-15~16 · 2022-08-04~05 · 2023-05-12~13 · 08-05 · 08-26~29 ·
#   09-24~25 · 2024-02-15~16 · 06-15~16 — 그 해 공휴일과 안 겹친다. 가까운 명절은
#   월력요항으로 확인했다 (2019 설 2/4~6 · 2023 추석 9/28~30 · 2024 설 2/9~12).
#   blog06 의 2000-01-01~02 는 날짜를 모르는 후기의 자리값이다 (1/1 은 토요일이라 판정 무관).
# 새 후기가 달력 없는 해의 날짜를 들고 오면 selfcheck 가 알려 준다.
PUBLIC_HOLIDAYS: dict[int, frozenset[date]] = {
    2025: frozenset({
        date(2025, 1, 1),
        date(2025, 1, 27),                                            # 임시공휴일
        date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),      # 설 연휴
        date(2025, 3, 1), date(2025, 3, 3),                           # 삼일절(토) · 대체
        date(2025, 5, 5), date(2025, 5, 6),                           # 어린이날 = 부처님오신날 · 대체
        date(2025, 6, 3),                                             # 대통령선거일 (임시)
        date(2025, 6, 6),
        date(2025, 8, 15),
        date(2025, 10, 3),
        date(2025, 10, 5), date(2025, 10, 6), date(2025, 10, 7),      # 추석 연휴 (5일 일)
        date(2025, 10, 8),                                            # 대체 (추석 연휴가 일요일과 겹침)
        date(2025, 10, 9),
        date(2025, 12, 25),
    }),
    2026: frozenset({
        date(2026, 1, 1),
        date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),      # 설 연휴
        date(2026, 3, 1), date(2026, 3, 2),                           # 삼일절(일) · 대체
        date(2026, 5, 1),                                             # 노동절 (2026.5.1 부터 공휴일)
        date(2026, 5, 5),
        date(2026, 5, 24), date(2026, 5, 25),                         # 부처님오신날(일) · 대체
        date(2026, 6, 3),                                             # 지방선거
        date(2026, 6, 6),
        date(2026, 7, 17),                                            # 제헌절 (2026.5.11 부터 다시 공휴일)
        date(2026, 8, 15), date(2026, 8, 17),                         # 광복절(토) · 대체
        date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26),      # 추석 연휴
        date(2026, 10, 3), date(2026, 10, 5),                         # 개천절(토) · 대체
        date(2026, 10, 9),
        date(2026, 12, 25),
    }),
}


def is_public_holiday(day: date) -> bool:
    """공휴일 · 대체 · 임시 공휴일인가. 달력이 없는 해는 False (위 주석)."""
    return day in PUBLIC_HOLIDAYS.get(day.year, frozenset())


# 요일 묶음 (월=0 … 일=6) — 공식표의 요일 표기 그대로 이름 붙였다.
_MON_FRI = frozenset({0, 1, 2, 3, 4})        # 월요일 ~ 금요일
_TUE_FRI = frozenset({1, 2, 3, 4})           # 화요일 ~ 금요일
_SUN_FRI = frozenset({0, 1, 2, 3, 4, 6})     # 월요일 ~ 금요일, 일요일
_SAT_SUN_MON = frozenset({5, 6, 0})          # 토요일 ~ 월요일
_SAT_SUN = frozenset({5, 6})                 # 토요일 ~ 일요일
_SAT = frozenset({5})                        # 토요일
_MON_THU = frozenset({0, 1, 2, 3})           # 월요일 ~ 목요일 (리버파크 골드)
_FRI_SUN = frozenset({4, 5, 6})              # 금요일 ~ 일요일 (리버파크 골드 2부제)

# 포레스트 파크 입장 제한일 (소연 · 10/7) — 공식 공지 /customer/Notice/3757 ('Updated Date: 2026. 09. 21') [이용 제한일]
#   "2026년 10월 10일 (토) ~ 11일 (일)" · "2026년 10월 17일 (토) ~ 18일 (일)" · "2026년 10월 24일 (토) ~ 25일 (일)" · "2026년 10월 31일 (토)"
# 가정표 FOREST_PARK '입장 제한일 · 2026' 과 같다. 공지는 사유를 안 적었다. 10/10~11 · 17~18 · 24~25 는 캠크닉 패키지 상세
# (8829 · 8830) 의 와인페어 안내 "(10/10~11, 10/17~18, 10/24~25)" · "해당 기간에는 포레스트 파크 일반 이용이 제한되며" 와 같고,
# 10/31 은 공지에만 있다.
_FOREST_PARK_CLOSED_2026 = (
    (date(2026, 10, 10), date(2026, 10, 11)),
    (date(2026, 10, 17), date(2026, 10, 18)),
    (date(2026, 10, 24), date(2026, 10, 25)),
    (date(2026, 10, 31), date(2026, 10, 31)),
)

# 피트니스 · 수영장 · 사우나 정기 휴관일 2026 (소연 · 10/11) — 시설 페이지 '휴관일 확인하기' 가 가리키는 공지 (공지사항 목록엔 안 나온다).
# 가정표 FITNESS · VISTA_FITNESS '정기 휴관일 · 2026' 과 같다 (화면 글자 10/11 다시 확인).
#   그랜드 /customer/Notice/3768 "그랜드 워커힐 서울의 피트니스 센터 정기 점검으로 인해 매월 세 번째 화요일 은 실내수영장, 사우나,
#     피트니스 이용이 불가능합니다. - 2026. 1/20, 2/24, 3/17, 4/21, 5/19, 6/16, 7/21, 9/15, 10/20, 11/17, 12/15"
#   비스타 /customer/Notice/2066 "비스타 워커힐 서울의 웰니스 클럽이 정기 점검으로 인해 매월 둘째 주 수요일 은 실내수영장, 사우나,
#     피트니스 이용이 불가능합니다. - 2026. 1/14, 2/11, 3/11, 4/8, 5/13, 6/10, 7/8, 9/9, 10/14, 11/11, 12/9"
# 규칙 ('셋째 화요일' · '둘째 수요일') 이 아니라 공지에 적힌 날을 쓴다 — 그랜드 2월은 2/24 (2/17 은 설 연휴) · 둘 다 8월은 없다.
# 2026 날짜만 적혀 있어 2026 만 닫는다 (지난 해 후기는 그 해 휴관일을 모른다).
_GRAND_FITNESS_CLOSED_2026 = tuple((date(2026, _m, _d), date(2026, _m, _d)) for _m, _d in (
    (1, 20), (2, 24), (3, 17), (4, 21), (5, 19), (6, 16), (7, 21), (9, 15), (10, 20), (11, 17), (12, 15)))
_VISTA_WELLNESS_CLOSED_2026 = tuple((date(2026, _m, _d), date(2026, _m, _d)) for _m, _d in (
    (1, 14), (2, 11), (3, 11), (4, 8), (5, 13), (6, 10), (7, 8), (9, 9), (10, 14), (11, 11), (12, 9)))
_VISTA_WELLNESS_CLOSED_2026 = tuple((date(2026, _m, _d), date(2026, _m, _d)) for _m, _d in (
    (1, 14), (2, 11), (3, 11), (4, 8), (5, 13), (6, 10), (7, 8), (9, 9), (10, 14), (11, 11), (12, 9)))

# 빛의 시어터 2026 달별 운영 (소연 · 10/11) — 운영사 ((주)티모넷 워커힐지점) 공지사항 deslumieres.co.kr /theatre/notice/noticeView/<번호> 의
# 달력 그림: 1432 '5월 운영 일정 안내' · 1442 '6월 일정 안내' · 1452 '7월' · 1462 '8월' · 1470 '9월' · 1476 '10월'. 그림마다
#   "행사 단체 예약으로 다음과 같이 운영 일정이 변경됩니다." · "별도 안내가 없는 날은 정상운영합니다. 매일 10:00 - 18:40 (입장 마감 18:00)"
#   (5 · 7 · 8월) · "매일 10:00 - 18:15 (입장 마감 18:00)" (6월) · "매일 10:00 - 18:00 (입장 마감 17:00)" (9 · 10월 — 지금 관람 안내와 같다).
# 달력 칸은 둘이다 — '휴관' (하루 종일) · 'HH:MM - HH:MM 입장제한 (Sold out)' (그 시각엔 일반 입장이 안 된다. 그 앞에 들어온 사람은
#   마감까지 본다고 읽는다 — 그림에 퇴장 안내는 없다). 9/27~10/1 휴관은 9월 · 10월 그림 둘 다에 걸쳐 있다 (10월 그림 첫 줄이 10/1 목까지).
# 공지가 없는 달 (1~4월 · 11~12월) 은 지금 관람 안내 (10:00~18:00 · 입장 마감 17:00) 로 둔다. 12/1~2027-1/31 '송년 아트 갈라'
#   (/theatre/venue/banquet) 는 기업 대관 시즌 안내뿐이고 일반 관람을 닫는 날짜가 없다 — 11 · 12월 공지가 나오면 그때 넣는다.
_TOL_DAYS_OFF_2026 = (
    (date(2026, 5, 11), date(2026, 5, 13)), (date(2026, 5, 17), date(2026, 5, 17)),
    (date(2026, 6, 1), date(2026, 6, 3)), (date(2026, 6, 11), date(2026, 6, 11)), (date(2026, 6, 22), date(2026, 6, 25)),
    (date(2026, 7, 2), date(2026, 7, 5)),
    (date(2026, 8, 22), date(2026, 8, 28)),
    (date(2026, 9, 1), date(2026, 9, 9)), (date(2026, 9, 27), date(2026, 10, 1)),
    (date(2026, 10, 6), date(2026, 10, 7)), (date(2026, 10, 11), date(2026, 10, 17)), (date(2026, 10, 29), date(2026, 10, 31)),
)
_TOL_SOLD_OUT_2026 = {   # 날 → 입장 제한 (시작, 끝) — 끝 시각부터 다시 들어간다
    date(2026, 5, 4): ((time(10, 0), time(12, 0)),),
    date(2026, 5, 14): ((time(13, 20), time(15, 20)),),
    date(2026, 5, 19): ((time(13, 20), time(17, 20)),),
    date(2026, 5, 27): ((time(14, 40), time(16, 40)),),
    date(2026, 6, 26): ((time(13, 0), time(15, 30)),),
    date(2026, 7, 1): ((time(12, 40), time(15, 20)),),
    date(2026, 7, 7): ((time(13, 20), time(16, 0)),),
    date(2026, 7, 9): ((time(12, 40), time(16, 0)),),
    date(2026, 7, 10): ((time(10, 0), time(12, 0)),),
    date(2026, 7, 21): ((time(13, 20), time(15, 20)),),
    date(2026, 7, 27): ((time(10, 0), time(11, 20)),),
    date(2026, 8, 7): ((time(12, 0), time(14, 0)),),
    date(2026, 8, 13): ((time(10, 0), time(11, 20)), (time(12, 40), time(14, 40))),
    date(2026, 8, 14): ((time(14, 0), time(16, 0)),),
    date(2026, 10, 20): ((time(15, 0), time(18, 0)),),
}
_TOL_MONTH_HOURS_2026 = (   # (기간, 닫는 시각, 입장 마감) — 9 · 10월은 기본 창과 같아 따로 안 둔다
    ((5, 1, 5, 31), time(18, 40), time(18, 0)),
    ((6, 1, 6, 30), time(18, 15), time(18, 0)),
    ((7, 1, 8, 31), time(18, 40), time(18, 0)),
)

def _theatre_windows() -> tuple["VenueWindow", ...]:
    """빛의 시어터 창 — 기본 (지금 관람 안내) · 2026 달별 시각 · 입장 제한 날의 쪼갠 창.

    입장 제한 날은 기본 · 달별 창을 닫고 그 날 하루짜리 창을 연다 — 제한 앞 (입장 마감 = 제한 시작 1분 전 · 마감까지 관람)
    과 제한 끝부터 (입장 마감은 그 달 값). **창은 시각 순으로 쌓는다** — 에이전트 earliest_start 가 앞에 적힌 창부터 본다.
    """
    one_day = lambda d: dict(season=(d.month, d.day, d.month, d.day), years=frozenset({d.year}))
    sold = tuple((d, d) for d in sorted(_TOL_SOLD_OUT_2026))
    months = tuple((date(2026, a, b), date(2026, c, e)) for (a, b, c, e), _, _ in _TOL_MONTH_HOURS_2026)
    wins = [VenueWindow(time(10, 0), time(18, 0), time(17, 0), source=SourceKind.OFFICIAL,
                        closed=_TOL_DAYS_OFF_2026 + sold + months)]
    for season, close, lo in _TOL_MONTH_HOURS_2026:
        wins.append(VenueWindow(time(10, 0), close, lo, source=SourceKind.OFFICIAL, season=season,
                                years=frozenset({2026}), closed=_TOL_DAYS_OFF_2026 + sold))
    for day in sorted(_TOL_SOLD_OUT_2026):
        close, lo = time(18, 0), time(17, 0)
        for (a, b, c, e), cl, la in _TOL_MONTH_HOURS_2026:
            if (a, b) <= (day.month, day.day) <= (c, e):
                close, lo = cl, la
        start = time(10, 0)
        for s, e in _TOL_SOLD_OUT_2026[day]:
            if s > start:
                last = (datetime.combine(day, s) - timedelta(minutes=1)).time()
                wins.append(VenueWindow(start, close, last, source=SourceKind.OFFICIAL, **one_day(day)))
            start = e
        if start <= lo:
            wins.append(VenueWindow(start, close, lo, source=SourceKind.OFFICIAL, **one_day(day)))
    return tuple(wins)


# 업장별 운영 창. 하나의 업장이 여러 창(중식/석식)을 가질 수 있다. ◎
WALKERHILL_VENUE_WINDOWS: dict[str, tuple[VenueWindow, ...]] = {
    "ONDAL": (
        VenueWindow(time(12, 0), time(15, 0), time(14, 30)),
        VenueWindow(time(18, 0), time(21, 0), time(20, 30)),
    ),
    "GEUMRYONG": (
        VenueWindow(time(12, 0), time(15, 0)),
        VenueWindow(time(18, 0), time(21, 0)),
    ),
    "MYONGWOLGWAN": (
        VenueWindow(time(12, 0), time(15, 0)),
        VenueWindow(time(17, 30), time(21, 0)),
    ),
    "MOEGI": (
        VenueWindow(time(12, 0), time(15, 0)),
        VenueWindow(time(18, 0), time(21, 0)),
    ),
    # ── 소연 수정 8 · 피자힐 마감이 30분 더 관대했다 ───────────────────────
    #
    # 회사 값 11:30~22:30. 공식 홈페이지는 마지막 타임이 **7부 20:30~22:00** 이고
    # "피자힐 Last Order 및 포장 주문은 21:00까지 입니다" 라고 적는다.
    # 30분 **더 관대한** 쪽이라 마감 뒤 착석한 하루를 통과시킨다.
    # 2026-09-22 공식 페이지 재확인 (DINING > PIZZA HILL > 이용안내 > 영업시간):
    #   회차제 8부 — 11:00~12:30 / 12:30~14:00 / 14:00~15:30 / 15:30~17:00 /
    #                17:00~18:30 / 18:30~20:00 / 20:00~21:30 / 21:30~23:00
    #
    # **내가 한 번 틀렸던 자리다.** 회사 원본은 11:30~22:30 L.O.21:00 이었는데,
    # 내가 근거 없이 22:00 으로 **좁히고** ◎(공식) 으로 표시했다. 출처 표기가
    # 지키려던 바로 그것을 내가 어긴 것이다. 공식 값으로 되돌린다.
    #
    # 고친 건 **공식에 적혀 있는 값뿐**이다 — 운영 시간 11:00~23:00.
    # L.O. 는 공식 페이지에 없어서 회사 값 21:00 을 **그대로 둔다.**
    # 8부가 21:30 에 시작하니 21:00 과 어긋나 보이지만, 그건 내 추론이지
    # 공식이 말하는 게 아니다. 없는 값을 지어내면 다음 사람이 그걸 근거로
    # 쓴다 — 내가 22:00 으로 좁혔을 때가 정확히 그 실수였다.
    # 회차 자체도 모델링하지 않는다(더뷔페와 같은 요일·회차 기능이 필요하다).
    # 남은 확인 항목: 8부 21:30 입장이 L.O. 21:00 에 걸리는가 — 현장 확인 필요.
    #
    # ── 소연 수정 · 10/11 · 현장 안내판으로 11:30~22:00 L.O. 21:00 (현장 질문 26 닫음) ──
    #
    # 근거: 10/7 현장 안내판 (경수 사진 · 피자힐 입구 영업시간) — 1부 11:30 시작 · 90분씩 7부 (7부 20:30~22:00) ·
    #   라스트오더 21:00. **비스타 워커힐 서울 피자힐** 공식 페이지 (/vistawalkerhillseoul/dining/PizzaHill · 한 · 영 · 10/11 확인) 가 같다:
    #   "1부 11:30 ~ 13:00 … 7부 20:30 ~ 22:00 Last Order 21:00" · "피자힐 Last Order 및 포장 주문은 21:00까지 입니다"
    # 피자힐은 **비스타 워커힐 서울 피자힐** 하나다 (별관 · 실내 96석). 그랜드 사이트에도 같은 피자힐을 소개하는 페이지가 있는데 옛 값이 남아 있다.
    # 그랜드 사이트에 남은 피자힐 페이지 (/grandwalkerhillseoul/dining/PizzaHill · 한 · 영 · 10/11) 는 아직 위 8부 11:00~23:00
    # (L.O. 표기 없음) — 9/22 에 본 것이 이 페이지다.
    # 현장 안내판과 비스타 페이지가 같아 이쪽을 따른다. 가정표 PIZZA_HILL '운영' · 'Last Order' · 상품표 피자힐 13줄
    # (11:30-21:00) 은 9/30 부터 이 값이었다 — 검증기만 남아 있던 것.
    # 회차는 여전히 안 나눈다 — 에이전트 피자힐 체류가 120분이라 90분 회차 창으로 나누면 피자힐에 앉을 수 없다.
    "PIZZA_HILL": (VenueWindow(time(11, 30), time(22, 0), time(21, 0),
                               source=SourceKind.OFFICIAL),),
    "THE_PAVILION": (VenueWindow(time(9, 0), time(21, 0), time(20, 0)),),
    "LUX_BAR": (VenueWindow(time(20, 0), time(23, 59), source=SourceKind.OFFICIAL),),

    # ── 소연 수정 4 · 클럽라운지는 세 서비스를 따로 연다 ────────────────────
    #
    # 여기 창이 **해피아워 하나뿐**이라, 내 클럽스위트 체류의 라운지 이용 3건이
    # 전부 I3 로 잡혔다. 조식도 티타임도 갈 데가 없다.
    #
    # blog04 3편이 이용시간을 글 속 상자로 적었다:
    #   "〈워커힐 클럽라운지 이용시간〉 조식 7:00~10:00 / 티타임 13:00~17:00
    #    / 해피아워 18:00~20:00"
    #   "저도 알차게 ㅋㅋㅋ 티타임, 해피아워, 조식 모두 사용했는데요"
    #
    # 공식 홈페이지(GRAND ROOMS > 클럽라운지)는 이렇게 게시한다:
    #   "Breakfast 07:00~10:00 / Tea Time 13:00~17:00 / Happy Hour 17:30~19:30"
    #
    # 조식·티타임은 두 출처가 일치한다. **해피아워만 30분씩 어긋난다.**
    # 후기는 2025년 4월 방문이고 홈페이지는 지금 값이라 시기 차로 보인다.
    # 홈페이지가 최신이므로 그쪽을 쓰고, 차이는 NOTES 에 남겼다.
    "GRAND_CLUB_LOUNGE": (
        VenueWindow(time(7, 0), time(10, 0), source=SourceKind.OFFICIAL),     # 조식
        VenueWindow(time(13, 0), time(17, 0), source=SourceKind.OFFICIAL),    # 티타임
        VenueWindow(time(17, 30), time(19, 30), source=SourceKind.OFFICIAL),  # 해피아워
        # ── 2025년 해피아워는 18:00~20:00 이었다 — 후기 두 편이 따로 말한다 ──────
        #   blog04 (2025-04 게시 · 3편 글 속 이용시간 상자) · blog05 (2025-03, "18:00~20:00 · 두 시간")
        #   공식 2026-09 확인값(17:30~19:30)과 다르다. 그 사이 바뀐 것으로 본다.
        #   검증기는 현재 규칙, 후기는 과거 — 창에 유효 연도를 둬서 둘 다 살린다 (Q17).
        VenueWindow(time(18, 0), time(20, 0), source=SourceKind.REVIEW, years=frozenset({2025})),
    ),
    # 더뷔페는 자유 착석이 아니라 1부/2부 고정 슬롯이다. ◎ — 단 **2부제는 요일마다 다르다.**
    #
    # ── 소연 수정 · 10/5 · 요일 창 ─────────────────────────────────────
    #
    # 10/5 전까지는 주말 · 공휴일 슬롯 6개만 있었다. 요일 기능 없이 평일 창을 더하면
    # 두 벌이 뭉쳐 **주말 슬롯 사이 빈 시간이 평일 통창 덕에 통과**하므로 일부러
    # 미뤄 뒀다. 요일 · 공휴일 칸이 생겨서 공식표를 그대로 넣는다.
    #
    # 공식 "운영시간 및 가격" (DINING > 더뷔페, 2026-10-05 다시 확인 · 10~11월과 12월 표):
    #     조식  화요일 ~ 금요일 07:00 ~ 10:00
    #           토요일 ~ 월요일, 공휴일  1부 06:30 ~ 08:10 · 2부 08:30 ~ 10:00
    #     중식  월요일 ~ 금요일 12:00 ~ 14:30
    #           토요일 ~ 일요일, 공휴일  1부 11:00 ~ 13:00 · 2부 13:30 ~ 15:30
    #     석식  월요일 ~ 금요일, 일요일 18:00 ~ 21:00
    #           토요일, 공휴일          1부 17:30 ~ 19:30 · 2부 20:00 ~ 22:00
    #     12월  석식만 바뀐다 — "월요일 ~ 일요일 1부 17:30 ~ 19:30 · 2부 20:00 ~ 22:00"
    #     "대체 공휴일 등 연휴 기간에는 운영 시간이 변경될 수 있습니다."
    # 공식 공지 이미지 (같은 페이지 배너 '더뷔페 조식 운영시간 안내', 10/5 확인):
    #     "더뷔페 조식 2부제 이용 안내 … 골드 시즌 기간 동안 투숙객 증가로 인해 조식 뷔페를
    #      2부제로 운영합니다. 운영 기간 | 7월 17일(금) - 8월 31일(월) · 1부 06:30-08:10 · 2부 08:30-10:00"
    #     요일로 보아 2026 년이다 (2026-07-17 금 · 08-31 월).
    # 영문 페이지에는 지난해 문구가 남아 있다 — "During the Gold Season (July 26 [Sat] – August 31 [Sun]),
    #     The Buffet breakfast will operate in two seatings" (요일로 보아 2025). 회차 시각이 없고, 그 기간에
    #     걸친 후기는 blog14 토 · 일뿐 (주말은 원래 2부제) 이라 2025 창은 넣지 않았다.
    #
    # 공휴일 처리는 상품표 더뷔페 줄과 같다 — 공휴일 창은 '+', 같은 끼니 평일 창은 '-'.
    #
    # 해석 확인 (10/5 · 공식 페이지 웹 보관본 web.archive.org — 2023-11 ~ 2026-04 사본 13개):
    #   · 기본 표는 **2026 년엔 맞다** — 1/21 · 2/22 · 4/21 사본이 지금 표와 같다 (값까지).
    #   · **지난 해는 조식이 달랐다** — 2025: 토~월 · 공휴일 1부 07:00~08:20 · 2부 08:40~10:00 ·
    #     2024: 토 · 일 · 공휴일만 2부제 (같은 시각) · 2023-11: 매일 07:00~10:00 한 번.
    #     중식 · 석식은 세 해 모두 지금과 같다. 검증기는 **지금 표로** 지난 해 후기도 잰다
    #     (팀 방식 — 현재 규칙. 후기가 부딪힐 때만 해마다 창을 둔다 · 클럽라운지 Q17).
    #     blog05 (2025-03-10 월) 조식 08:40 은 2025 표와 맞고 지금 표로도 통과한다.
    #   · 12월 석식 매일 2부는 **해마다** 있었다 (2023 · 2024 · 2026 사본) → season 으로 매년 12월.
    #   · 여름 (골드 시즌) 조식 2부제도 해마다 있었지만 기간이 달랐다 (2024: 7/27~8/18 ·
    #     2025: 7/26~8/31 · 2026: 7/17~8/31) → 2026 공지만 그 해에 묶는다.
    #   · 공휴일 운영은 따로 바뀐 적이 있다 — 2024 사본 "5월5일 (4부제), 5월6일 (3부제),
    #     5월15일 (3부제), 6월6일 (3부제)" · 2025 사본 "5월1일 근로자의 날 3부제 운영".
    #     일요일 공휴일 (2024-05-05) · 대체공휴일 (5/6) 도 평소 요일과 다르게 운영했다 —
    #     공휴일로 보는 것은 맞고, 회차 수 · 시각은 그 날마다 다를 수 있다 (여기선 2부제로 둔다).
    #
    # **창 순서는 시각 순이다.** 에이전트 `earliest_start` 가 그 날 열리는 창 중
    # **앞에 적힌 것부터** 시작 시각을 찾으므로, 순서가 섞이면 이른 회차를 건너뛴다.
    "THE_BUFFET": (
        VenueWindow(time(6, 30), time(8, 10), weekdays=_SAT_SUN_MON, holidays="+"),        # 조식 1부
        VenueWindow(time(6, 30), time(8, 10), season=(7, 17, 8, 31),
                    years=frozenset({2026})),                                              # 2026 여름 조식 1부 · 매일
        VenueWindow(time(7, 0), time(10, 0), weekdays=_TUE_FRI, holidays="-",
                    closed=((date(2026, 7, 17), date(2026, 8, 31)),)),                     # 조식 화~금
        VenueWindow(time(8, 30), time(10, 0), weekdays=_SAT_SUN_MON, holidays="+"),        # 조식 2부
        VenueWindow(time(8, 30), time(10, 0), season=(7, 17, 8, 31),
                    years=frozenset({2026})),                                              # 2026 여름 조식 2부 · 매일
        VenueWindow(time(11, 0), time(13, 0), weekdays=_SAT_SUN, holidays="+"),            # 중식 1부
        VenueWindow(time(12, 0), time(14, 30), weekdays=_MON_FRI, holidays="-"),           # 중식 월~금
        VenueWindow(time(13, 30), time(15, 30), weekdays=_SAT_SUN, holidays="+"),          # 중식 2부
        VenueWindow(time(17, 30), time(19, 30), weekdays=_SAT, holidays="+"),              # 석식 1부
        VenueWindow(time(17, 30), time(19, 30), season=(12, 1, 12, 31)),                  # 12월 석식 1부 · 매일
        VenueWindow(time(18, 0), time(21, 0), weekdays=_SUN_FRI, holidays="-",
                    season=(1, 1, 11, 30)),                                                # 석식 월~금 · 일 (12월 빼고)
        VenueWindow(time(20, 0), time(22, 0), weekdays=_SAT, holidays="+"),                # 석식 2부
        VenueWindow(time(20, 0), time(22, 0), season=(12, 1, 12, 31)),                    # 12월 석식 2부 · 매일
    ),
    "GOLF_CLUB": (VenueWindow(time(6, 0), time(23, 0)),),

    # ── 소연 수정 6 · 부대시설에는 창이 아예 없었다 ─────────────────────────
    #
    # 이 표에 식음업장만 있고 시설이 통째로 빠져 있다. `_fits_any_window` 는
    # 창이 없는 업장을 **무조건 통과**시키므로, 내 네 체류가 지나는 시설이
    # 전부 검사 없이 지나갔다. 확인해 보니 새벽 3시 족욕·수영도 PASS 였다.
    #
    # **내 블로그가 지나는 시설만 넣었다.** 포레스트 파크·테네즈·라이브러리 등도
    # 창이 없는 건 마찬가지지만, 그건 그 시설을 지나는 후기를 맡은 사람의 몫이다.
    #
    # 시각은 공식 홈페이지에서 가져왔다.
    #   그랜드 피트니스 센터(호텔 지하 2층): "06:00 ~ 22:00 (체련, 수영장 21:30까지)"
    #   비스타 웰니스 클럽(비스타 3층): INDOOR POOL 06:00~21:30
    #   SKYARD(비스타 4층): "이용 시간 09:00 ~ 22:00"
    # 소연 수정 · 10/11 — 정기 휴관일 (위 _GRAND_FITNESS_CLOSED_2026 · _VISTA_WELLNESS_CLOSED_2026) 을 닫는 날로.
    # 전엔 가정표에만 있고 창은 매일 열려 있었다 — 생성기가 휴관일 (10/14 비스타 · 10/20 그랜드) 에도 수영장에 보냈다.
    "GRAND_POOL": (VenueWindow(time(6, 0), time(21, 30), source=SourceKind.OFFICIAL, closed=_GRAND_FITNESS_CLOSED_2026),),
    "VISTA_POOL": (VenueWindow(time(6, 0), time(21, 30), source=SourceKind.OFFICIAL, closed=_VISTA_WELLNESS_CLOSED_2026),),
    # 소연 수정 · 9/29 — blog19 원문 "피트니스 클럽은 06:00 - 22:00 이고" (후기 관측)
    #   → 10/11 공식으로 고쳐 적는다 (값 같음): 비스타 웰니스 클럽 페이지 FITNESS "서비스 시간 06:00 ~ 22:00 (매월 둘째 주 수요일
    #     정기 휴관)" (/vistawalkerhillseoul/wellness/Fitness · 가정표 VISTA_FITNESS '운영' ◎) · 휴관일은 비스타 공지
    "VISTA_FITNESS": (VenueWindow(time(6, 0), time(22, 0), source=SourceKind.OFFICIAL, closed=_VISTA_WELLNESS_CLOSED_2026),),
    # 소연 추가 · 10/11 — 사우나. 전엔 창이 없어 에이전트가 임시값 (agent_v4.TEMP_WINDOWS 06:00~21:00 · blog01 안내표) 으로 다녔다.
    # 노드는 하나다 (WELLNESS_SAUNA · 그랜드 로비에 잇는다 · 위 '넣지 않은 것'). 시각이 화면에 보이는 공식 안내는 그랜드 피트니스 센터뿐이다
    # (/grandwalkerhillseoul/activity/Experience · 10/11 확인): "체련장 외에 실내 수영장 시설(성인풀 및 유아풀) 및 사우나 시설을 보유하고"
    #   · "운영시간 : 06:00 ~ 22:00 (체련, 수영장 21:30까지)" — 21:30 예외가 체련 · 수영장뿐이라 사우나는 22:00 까지로 읽는다 (○ 계산).
    # 쉬는 날은 그랜드 공지 (위 _GRAND_FITNESS_CLOSED_2026 — "실내수영장, 사우나, 피트니스").
    # 비스타 쪽 사우나도 같은 시각이다 — VISTA SIGNATURE STAY 상세 (/vistawalkerhillseoul/Package/8848 · 화면 글자) "웰니스 사우나 이용 안내
    #   - 운영 시간: 06:00 ~ 22:00 (휴관일: 10/14, 11/11, 12/9)" (가정표 '운영 · 비스타 웰니스 사우나' ◎). 비스타 휴관일은 노드가 하나라 안 닫는다.
    #   웰니스 클럽 페이지 소스의 SAUNA 안내 (요금 포함) 는 HTML 주석 안이라 화면에 안 나온다 — 근거로 안 쓴다.
    # 후기 blog32 "사우나 7:00 - 16:00" 은 가정표 비고에 남긴다.
    "WELLNESS_SAUNA": (VenueWindow(time(6, 0), time(22, 0), source=SourceKind.DERIVED, closed=_GRAND_FITNESS_CLOSED_2026),),
    # 소연 추가 · 10/11 — 빛의 시어터. 전엔 창이 없어 에이전트가 임시값 (agent_v4.TEMP_WINDOWS 10:00~19:00 · △ blog06) 으로 다녔다.
    # 운영사 관람 안내 (deslumieres.co.kr /theatre/visit/exibition · (주)티모넷 워커힐지점 · 10/11 다시 확인):
    #   "관람시간 매일 10:00 - 18:00 (입장마감 17:00)" · 회차 "01회차 10:00 - 11:00 … 08회차 17:00 - 18:00"
    #   (가정표 THEATRE_OF_LIGHT '운영' · '회차 길이'). 입장 마감 17:00 을 last_order 로 둔다.
    # 10/11 — 2026 달별 공지 (휴관 · 입장 제한 · 5~8월 시각) 를 더했다 (위 _TOL_* · _theatre_windows · 가정표 '휴관일 · 2026' 등).
    #   전엔 1년 내내 같은 창이라 생성기가 10월 휴관일 (10/6~7 · 10/11~17 · 10/29~31) 에도 손님을 보냈다.
    "THEATRE_OF_LIGHT": _theatre_windows(),
    "SKYARD": (VenueWindow(time(9, 0), time(22, 0), source=SourceKind.OFFICIAL),),
    # 소연 수정 · 10/7 — 포레스트 파크 (경수 부탁: 와인페어 날 입장 제한을 시나리오로 돌리려고). 전엔 창이 없어
    # 에이전트가 임시값 (agent_v4.TEMP_WINDOWS 11:00~20:00) 으로 다녔고 검증기는 안 봤다.
    # 공식 체험/활동 페이지 (/grandwalkerhillseoul/activity/Experience · 한 · 영 같음 · 10/7 다시 확인):
    #   "운영시간 : 11:00 ~ 20:00 7/1~9/27 기간에는 21:00까지 연장 운영됩니다."  (가정표 FOREST_PARK '운영')
    # 연장 기간에 연도가 안 적혀 있어 해마다 같은 기간 (season) 으로 둔다 — 지난 해 후기도 지금 표로 잰다 (더뷔페와 같다).
    # 입장 제한일은 위 _FOREST_PARK_CLOSED_2026 — 그 날은 창이 닫혀 에이전트가 안 가고, 가면 I3 로 반려된다.
    "FOREST_PARK": (
        VenueWindow(time(11, 0), time(20, 0), source=SourceKind.OFFICIAL, season=(9, 28, 6, 30), closed=_FOREST_PARK_CLOSED_2026),
        VenueWindow(time(11, 0), time(21, 0), source=SourceKind.OFFICIAL, season=(7, 1, 9, 27)),
    ),
    # 소연 추가 · 10/8 — 와인페어 '구름 위의 산책' (경수 부탁: 와인페어를 모델 안에 넣기). 자리는 포레스트 파크 (에이전트 행동의 location).
    # 공식 Wine Forest 패키지 상세 (/grandwalkerhillseoul/Package/8837 · 비스타 8838 같은 문구 · 10/8 확인):
    #   "① 운영 날짜: 10월 10일 ~ 11일 I 10월 17일 ~ 18일 I 10월 24일 ~ 25일"
    #   "② 운영 시간: 1부: 11:00 ~ 15:00 I 2부: 15:30 ~ 20:00 (입장권 픽업 @프런트)"
    # 가정표 FOREST_PARK '와인페어 운영 날짜 · 2026' · '와인페어 운영 · 1부' · '2부'. 여섯 날이 2026 년 10/10~10/25 의 토 · 일과 같아
    # season + weekdays 로 적는다 (selfcheck 가 하루하루 맞춘다). 포레스트 파크 일반 이용이 막히는 날 중 10/31 은 와인페어 날이 아니다.
    # 상세 ➆ "호텔 사정 및 당일 기상 상황 등에 따라 변동될 수 있습니다" — 비 오는 날은 generate.py --close WINE_FAIR=… 로 돌린다.
    "WINE_FAIR": (
        VenueWindow(time(11, 0), time(15, 0), source=SourceKind.OFFICIAL, season=(10, 10, 10, 25),
                    years=frozenset({2026}), weekdays=_SAT_SUN),                 # 1부
        VenueWindow(time(15, 30), time(20, 0), source=SourceKind.OFFICIAL, season=(10, 10, 10, 25),
                    years=frozenset({2026}), weekdays=_SAT_SUN),                 # 2부
    ),
    # 리버파크만 공식 홈페이지에 시각이 없다 — "운영 기간 : 여름시즌" 한 줄뿐이고
    # 시즌마다 다시 공지하는 모양이다. 여기만 후기의 현장 요금표를 쓴다(△ 관측).
    #
    # **근거가 2023년 현장 게시물뿐이라 `years` 로 그 해에 묶었다.**
    # `season` 은 월·일만 비교하므로, 묶지 않으면 2023년 요금표가 2026년에도
    # 적용된다. 다른 해에는 창이 하나도 안 열려 "해당 기간에 운영하지 않음" 이
    # 되는데 그게 맞다 — 그 해 시간표를 우리는 모른다. (2026 은 10/5 에 아래 넣었다.)
    "RIVERPARK": (
        VenueWindow(time(10, 0), time(19, 0), season=(6, 30, 7, 21),
                    years=frozenset({2023}),
                    source=SourceKind.ESTIMATED),                      # 얼리 블루 · 통운영
        VenueWindow(time(10, 0), time(14, 30), season=(7, 22, 8, 20),
                    years=frozenset({2023}), exit_grace_min=20,
                    source=SourceKind.ESTIMATED),                      # 골드 1부
        VenueWindow(time(15, 0), time(19, 0), season=(7, 22, 8, 20),
                    years=frozenset({2023}), exit_grace_min=20,
                    source=SourceKind.ESTIMATED),                      # 골드 2부
        VenueWindow(time(10, 0), time(19, 0), season=(8, 21, 8, 27),
                    years=frozenset({2023}),
                    source=SourceKind.ESTIMATED),                      # 레이트 블루 · 통운영
        # ── 소연 수정 · 10/5 · 2026 창 ────────────────────────────────────
        #
        # 2023 창만 있어 2026 년엔 어느 날도 안 열렸다 — `generate.py --date 2026-07-18`
        # 리버파크 매출 0. 공식 **리버파크 페이지** (ACTIVITY > 리버파크 ·
        # /grandwalkerhillseoul/activity/Riverpark, 한글 · 영문 10/5 확인) 의 '시즌 운영 시간 & 입장 요금':
        #   Blue  06. 26 ~ 07. 16  10:00 ~ 20:00
        #   Gold  07. 17 ~ 08. 30  월요일~목요일 10:00 ~ 20:00
        #                          금요일~일요일 (2부제 운영) 1부) 10:00 ~ 18:00 · 2부) 15:00 ~ 21:30
        #   "Gold 시즌 2부 입장은 'Savoring Summer Night' 패키지 고객에 한해 가능합니다. (1박당 1회)"
        # 연도 표기는 없다 — 2026 후기 두 편 (blog59 · blog54) 이 옮긴 기간 · 요금과 같아 2026 에 묶는다.
        #
        # ※ 처음엔 체험/활동 페이지의 "운영 기간 : 여름시즌" 한 줄만 보고 '공식엔 시각이 없다' 며
        #   후기 근거 (○) 로 금~일만 넣었다. 리버파크 페이지가 따로 있었다 — 월~목 · 블루가 빠져
        #   여름 평일 리버파크가 통째로 0 이 됐다. 같은 날 다시 찾아 공식 값으로 고쳤다.
        #
        # 요일 · 기간은 상품표(menu.csv) 리버파크 줄과 같다 (selfcheck 가 하루하루 맞춘다).
        # 공휴일 표기는 없어 요일 그대로 본다 (8/17 대체공휴일 월 → 월~목 창).
        # 2부는 1부와 15:00~18:00 이 겹친다 (1부 · 2부는 서로 다른 입장). 2부가 패키지 고객 전용인
        # 것은 창으로 못 적는다 (출입 규칙) — 상품표 · 현장 질문 24 에 남겼다.
        # 8/30 뒤 운영은 페이지에 없어 창을 두지 않는다. 퇴장 유예는 2026 근거가 없어 안 준다.
        VenueWindow(time(10, 0), time(20, 0), season=(6, 26, 7, 16),
                    years=frozenset({2026}),
                    source=SourceKind.OFFICIAL),                       # 2026 블루 · 매일
        VenueWindow(time(10, 0), time(20, 0), season=(7, 17, 8, 30),
                    years=frozenset({2026}), weekdays=_MON_THU,
                    source=SourceKind.OFFICIAL),                       # 2026 골드 · 월~목
        VenueWindow(time(10, 0), time(18, 0), season=(7, 17, 8, 30),
                    years=frozenset({2026}), weekdays=_FRI_SUN,
                    source=SourceKind.OFFICIAL),                       # 2026 골드 1부 · 금~일
        VenueWindow(time(15, 0), time(21, 30), season=(7, 17, 8, 30),
                    years=frozenset({2026}), weekdays=_FRI_SUN,
                    source=SourceKind.OFFICIAL),                       # 2026 골드 2부 · 금~일 · 패키지 고객 전용
    ),
    # ── 소연 수정 5 · 르파사쥬는 매장시간과 주문 접수시간이 다르다 ──────────
    #
    # 회사 값은 창이 하나(11:00~19:30)뿐이라 두 값이 뭉쳐 있다. 그러면
    # 매장 영업 중인 09:30 이용도, 주문 마감 뒤 19:55 수령도 전부 I3 가 된다.
    #
    #   공식 DINING > 르 파사쥬 : 매장 "연중 09:00 ~ 21:00"
    #   피자 주문 접수          : 11:00 ~ 19:30   ← 회사 값 11:00~19:30 이 이것이다
    #
    # blog03 1편이 둘이 다르다는 걸 그대로 보여 준다:
    #   "TOGO 주문 마감은 오후 7시 30분 … 저는 아슬아슬하게 성공했는데,
    #    바로 뒤에 오신 분은 마감돼서 결국 피자힐로 직접 올라가셨습니다"
    #   "피자를 기다리는 동안 케이크도 구경했습니다"
    # 주문은 마감 전에 넣고 수령은 그 뒤에 한다.
    #
    # 매장 창만 넓히면 반대로 09:30·20:00 **주문**까지 통과한다. 그래서
    # `states` 로 주문 상태에만 걸리는 창을 따로 둔다.
    "LE_PASSAGE": (
        VenueWindow(time(9, 0), time(21, 0), source=SourceKind.OFFICIAL),
        VenueWindow(time(11, 0), time(19, 30), source=SourceKind.OFFICIAL,
                    states=frozenset({"TAKEOUT_ORDER"})),
    ),
}

# 물리적으로 한 번에 하나만 점유할 수 있는 상태 (I4).
PHYSICALLY_EXCLUSIVE_STATES = frozenset(
    {
        "SEATED", "DINING", "COURSE_IN_PROGRESS", "IN_ROOM", "IN_LOUNGE",
        "HAPPY_HOUR_ACTIVE", "TIME_LIMIT_ACTIVE", "TAB_OPEN", "IN_TREATMENT",
        "AT_FRONT_DESK", "IN_CHECKIN_QUEUE",
        # ── 한호 추가 · 시설 이용 상태도 물리 점유다 ─────────────────────────
        # 수영장 ENTERED 가 빠져 있어 라운지·수영장 동시 이용을 I1 만 잡고 I4 가 못 잡았다
        # (blog02). 같은 이유로 §3.3 의 다른 시설 이용 상태도 넣는다:
        #   ENTERED   리버파크 · 실내수영장(bk·한호 표기)
        #   CHECKED_IN 스파·사우나·피트니스 · 실내수영장(소연 표기, §3.3 스파 행)
        #   ADMITTED  포레스트 파크 · 전시
        # 실내수영장 상태 이름이 둘로 갈려 있다 — 취합 논점. 정해지면 하나로 줄인다.
        "ENTERED", "CHECKED_IN", "ADMITTED",
    }
)

# ── bk 추가 · 배경 상태 — 위치를 점유하지 않는 대기 ─────────────────────────
#
# 체크인 번호표를 받고 알림을 기다리는 동안 손님은 로비 공연을 보고 라이브러리에 가고
# 비스타 쪽까지 걸어간다 (blog01). 대기가 물리 점유면 그 이동이 전부 I4 이중 점유가 된다.
# 이 상태들은 I1(단조성)·I2(이동 가능성)·I4(물리 점유) 검사에서 뺀다. I3·I6 은 그대로.
#
# 소연 쪽은 같은 문제를 다른 길로 풀었다 — 체크인 전 대기를 M2 의 LOUNGE_WAITING 으로
# 적는다 (blog03·04). 두 방식은 양립한다: LOUNGE_WAITING 도 이 목록에 있다.
BACKGROUND_STATES: frozenset[str] = frozenset(
    {
        "IN_CHECKIN_QUEUE", "LUGGAGE_STORED", "LOUNGE_WAITING",
        "EARLY_ARRIVAL_ROOM_NOT_READY", "WAITLISTED", "WAITLIST_CALLED",
        "IN_QUEUE", "CAPACITY_FULL_WAITING",
    }
)

# ── bk 추가 · I6 하루 경계가 지키는 것은 객실 점유 시간이다 ──────────────────
#
# docs §9.2 는 "체크인 전 / 체크아웃 후 구간은 LUGGAGE_STORED·POST_STAY 로만 존재" 라고
# 적어 체크인 전 구간의 존재를 허용한다. 그런데 원본 구현은 배타 상태 전부를 경계로 막아,
# 체크인 전에 로비 라운지에 앉거나 파빌리온에서 점심을 먹은 것까지 위반이 됐다 (blog01).
# 로비·라운지·업장은 비투숙객도 쓴다. 투숙일 경계로 막을 대상은 객실 점유뿐이다.
#
# ※ 취합 논점 1. 소연 안은 배타 상태 전체에 I6 를 걸고 체크인 전 체류를 대기 상태 이름으로
#   구분한다. 여기서는 객실 점유만 거는 bk 안을 적용했다. 소연 안이 막으려던 것
#   (체크인 전 클럽라운지 이용)은 I6 가 아니라 I5 로 막는다 — 아래 LOCATION_PRECONDITIONS.
#   소연 selfcheck 의 "체크인 전에 IN_LOUNGE 를 쓰면 잡힌다" 기대 하나가 이 결정에 따라 바뀐다.
ROOM_OCCUPANCY_STATES: frozenset[str] = frozenset(
    {
        "IN_ROOM", "OUT_OF_ROOM", "DND_ON",
        "MAKE_UP_ROOM_REQUESTED", "SERVICE_IN_PROGRESS",
    }
)

# 이용을 마치고 **나가는 중**인 상태. `exit_grace_min` 은 여기에만 적용한다.
#
# §3.3 이 시설마다 퇴장 상태를 따로 두고 있다 — 리버파크·포레스트 파크 모두 `EXITED`,
# 스파·사우나·피트니스는 `COMPLETED`.
# 이걸 안 가르면 유예가 **이용 시간까지** 늘려 준다. 리버파크 1부를 14:50 까지
# 이용한 하루가 통과하는데, 그건 다음 타임 손님과 겹치는 하루다.
EXIT_STATES = frozenset({"EXITED", "COMPLETED"})


# 해당 상태에 진입하기 전에 반드시 선행되어야 하는 상태 (I5).
STATE_PRECONDITIONS: dict[str, frozenset[str]] = {
    "DINING": frozenset({"SEATED"}),
    "COURSE_IN_PROGRESS": frozenset({"SEATED"}),
    "IN_ROOM": frozenset({"KEY_ISSUED", "DIGITAL_KEY_ACTIVATED"}),
    "CHECKED_OUT_SETTLED": frozenset({"IN_ROOM"}),
    "HAPPY_HOUR_ACTIVE": frozenset({"KEY_ISSUED", "DIGITAL_KEY_ACTIVATED"}),
}

# ── bk 추가 · 장소 전제 조건 (I5) ─────────────────────────────────────────
# 투숙객 전용 장소는 키를 받은 뒤에만 들어간다 ○. 체크인 전 클럽라운지 이용을 I6(하루 경계)
# 가 아니라 여기서 잡는다 — 이유가 "경계 밖" 이 아니라 "아직 투숙객이 아님" 이라서.
# 배경 상태(대기)에는 적용하지 않는다.
_KEY_STATES = frozenset({"KEY_ISSUED", "DIGITAL_KEY_ACTIVATED"})
LOCATION_PRECONDITIONS: dict[str, frozenset[str]] = {
    "GRAND_CLUB_LOUNGE": _KEY_STATES,
    "DOUGLAS_LOUNGE": _KEY_STATES,
}


# ── 소연 추가 · 9/29 · 시설마다 누가 들어가나 (출입 표) ─────────────────────────
#
# 비투숙 후기 blog18 · blog40 이 v4 에서도 0점이었다. 에이전트가 식당 대신 스카이야드 ·
# 포레스트파크로 가기도 했다. 에이전트는 두 곳을 `requires=("arrive",)` — "도착만 하면 누구나" 로
# 두고 있었는데, 후기는 반대다. 누가 들어가는지를 여기 표로 두고 에이전트가 읽는다
# (9/29 경수가 반영 — agent_v4.catalog 가 불가인 행동을 뺀다).
#
# 칸은 손님 다섯 — 그랜드 · 비스타 · 더글라스 투숙, 클럽 객실(그랜드 · 비스타), 비투숙.
# 값은 다섯 — 무료(특전 · 포함) · 유료(입장권 · 이용권 · 현장 추가 결제) · 자유(자격 없이
# 들어간다. 식당은 먹은 값만) · 불가 · 모름.
# **모름은 막지도 열지도 않는다.** 근거 없는 칸을 채우면 다음 사람이 그걸 근거로 쓴다
# (피자힐을 22:00 으로 좁혔던 내 실수가 그것이다).
#
# 근거는 개발용 후기 원문과 회사 문서만 썼다. 봉인 3 의 11편은 9/29 채점 뒤 개발용으로
# 풀린 다음에 봤다 — 스카이야드 · 포레스트파크의 게시 안내를 옮겨 적은 글이 그 안에 있었다.
# 9/30 에 walkerhill.com 공식 안내와 대조해 셋을 고쳤다 (리버파크 · 테네즈 · 비스타 웰니스 체크아웃).
# 칸마다 근거와 ◎ ○ △ 는 docs/시설_출입_표.md 에 있다. 여기는 다툼이 있는 곳만 옮긴다.
#
# **검증 판정은 바꾸지 않는다.** validate_walkerhill_timeline 은 이 표를 읽지 않는다 —
# 타임라인에는 투숙객인지 · 어느 건물인지가 없다. I5 로 막으려면 따로 재고 정한다.


class Entry(Enum):
    """출입 표의 한 칸 — 이 손님이 이 시설에 들어가나."""

    FREE = "무료"      # 투숙 특전 · 포함
    PAID = "유료"      # 입장권 · 이용권 · 현장 추가 결제로 들어간다
    OPEN = "자유"      # 들어가는 데 자격이 없다 (식당은 먹은 값만)
    NO = "불가"
    UNKNOWN = "모름"   # 근거 없음 — 막지도 열지도 않는다


@dataclass(frozen=True)
class FacilityAccess:
    grand: Entry
    vista: Entry
    douglas: Entry
    non_guest: Entry
    # 클럽 객실이면 건물 칸 대신 이 칸. None 이면 건물 칸 그대로.
    # 더글라스는 클럽 칸이 없다 — 더글라스 페르소나의 club_access 는 더글라스 라운지 자격이다.
    grand_club: Entry | None = None
    vista_club: Entry | None = None
    # True — 체크아웃(키 반납) 뒤엔 못 들어간다는 근거가 있다 (객실 카드로 열거나 · 공식 안내가
    #        "체크아웃 전까지만" 이라고 적음).
    # None — 근거 없음. False 는 쓰지 않는다 ("키가 필요 없다" 를 말한 후기가 없다).
    room_key: bool | None = None

    @property
    def rule(self) -> str:
        """경수가 물은 세 갈래 — 비투숙 칸이 정한다."""
        return {
            Entry.OPEN: "누구나",
            Entry.PAID: "유료면 비투숙도",
            Entry.NO: "투숙객만",
            Entry.UNKNOWN: "비투숙은 모름",
        }[self.non_guest]


_F, _P, _O, _N, _U = Entry.FREE, Entry.PAID, Entry.OPEN, Entry.NO, Entry.UNKNOWN

FACILITY_ACCESS: dict[str, FacilityAccess] = {
    #                                 그랜드 비스타 더글라스 비투숙
    # ── 경수가 짚은 셋 ──────────────────────────────────────────────────
    #
    # 스카이야드 — "비스타 투숙객만" 은 **비투숙 칸만 맞다.** 다른 투숙객은 돈을 내면 들어간다.
    #   blog41 이 게시 안내를 옮겨 적었다:
    #     "스카이야드 이용대상 … ✔️비스타 워커힐 서울 투숙 고객 ✔️그랜드 워커힐 서울 클럽스위트
    #      객실 이상 투숙 고객 ✔️스카이야드 혜택 포함 투숙 고객 ✔️빌라 투숙 고객
    #      ✔️그 외 투숙 고객 유료 이용 가능(객실당 19,000원)"
    #   blog28 도 같은 말 ("… 유료 이용은 객실당 19,000원이에요"). 실제로 들어간 사람 —
    #   blog03 B (그랜드 · 클럽 아님 · 2023-05) "별도 비용이라면 1인당 약 2~3만 원 수준입니다" ·
    #   blog48 · blog51 (그랜드 클럽스위트). 경수가 본 "15번" 문장("비스타 워커힐 투숙객만 이용할 수
    #   있는")은 원문 r015 = blog29 인데 못 씀 글(판매 안내)이라 근거로 안 쓴다 — 무료 대상만 말한 것으로 보인다.
    #   → 비스타 무료 · 그랜드 클럽스위트 무료 · 그 밖의 투숙객(더글라스 포함) 유료 · 비투숙 불가.
    #     클럽룸(스위트 아님)은 안내대로면 유료인데, 페르소나에 클럽 여부만 있어 클럽 전체를 무료로 뒀다 (△)
    #   객실 카드로 올라간다 — blog35 "4층부터는 객실도 함께 있어서 이 곳에 엘레베이터에서 객실 카드를
    #   찍어야 갈 수 있어요" (○ — 체크아웃 뒤엔 못 간다고 본다)
    "SKYARD":            FacilityAccess(_P, _F, _P, _N, grand_club=_F, room_key=True),
    # 포레스트파크 — blog42 가 게시 안내를 옮겨 적었다: "이용대상 : 호텔투숙객 (그랜드, 비스타, 더글라스)
    #   입장료 : 투숙객 무료 객실당 성인 2명, 영유아 2명까지 가능 * 초과인원은 유료입장가능
    #   (성인 3만원, 어린이 2만원)" · "객실 및 이름 확인 후 입장 가능합니다".
    #   blog26 "알고보니 투숙객만 이용 가능한 곳이었다 … 거기서 숙박객 정보 확인하고" ·
    #   blog45 운영 안내 "FOREST PARK 11:00-20:00 11:00-21:00(7/1-9/27) 투숙객 전용".
    #   **다툼 하나** — blog50 "투숙객이 아니시라면 입장료가 있었습니다". 위 안내의 "초과인원은
    #   유료입장가능" (투숙 객실에 딸린 사람)으로 읽었다. 방 없이 온 비투숙이 표를 산 후기는 없다 → 불가.
    #   안의 유료 공간(blog47)은 입장과 별개다
    #   → 9/30 공식 확인 (walkerhill.com 체험/활동): "워커힐 호텔앤리조트 투숙객 전용 시설" ·
    #     "초과 인원은 투숙객에 한해 최대 2인까지 유료 입장이 가능합니다". 위 읽기가 맞았다 (◎)
    "FOREST_PARK":       FacilityAccess(_F, _F, _F, _N),
    # 라이브러리 — blog25 "객실 키가 있어서 입장이 가능하니 체크아웃후에는 입장이 불가능해요"
    #   blog41 "투숙객 전용 라이브러리로 객실 키 터치 후 입장 가능" · blog26 "투숙객이면 카드키로
    #   터치해서" · blog49 · blog50. 비스타 투숙객도 쓴다 (blog19 · blog41).
    #   더글라스 투숙객이 들어간 후기는 없지만 안내가 "투숙객 전용" 이라 무료로 뒀다 (○)
    #   어긋나는 기록 하나 — blog56(비스타) "체크인 전에 2층에 도서관(?)이 있는데 거기서 수유를 했었다".
    #   키를 받기 전이다. 글쓴이도 "(?)" 를 달았다. 표는 체크인 전을 따로 다루지 않아 부딪히지는 않는다
    #   → 9/30 공식 확인: "운영시간 : 07:00 ~ 22:00 (투숙객 전용 시설)" (◎)
    "GRAND_LIBRARY":     FacilityAccess(_F, _F, _F, _N, room_key=True),

    # ── 수영장 · 피트니스 · 사우나 · 리버파크 ─────────────────────────────
    # 실내 수영장 · 피트니스는 건물 특전이다 (회사 문서 그랜드 · 비스타 · 더글라스 공통 특전).
    # 비스타 것은 다른 건물 투숙객 · 비투숙이 못 쓴다 — blog41 "비스타 워커힐 3층에 있는 웰니스 클럽
    # 비스타 워커힐 투숙객 전용이다" · "비스타 투숙객 전용 메인풀". 연간 회원은 예외로 보인다
    # (blog16 "피트니스 연간회원권을 끊어서, 라커에 이름") — 에이전트는 회원을 다루지 않는다.
    # 그랜드 것은 그런 안내가 없다 — 비스타 투숙객 · 비투숙은 모름 (회사 비투숙 타입 POOL_DAY_PASS 는
    # 어느 수영장인지 안 적혔다). 그랜드 헬스장에도 회원은 있다 — blog21 "지금은 회원 신청을 아예
    # 안받는다고 하니"
    # 9/30 공식 확인 (walkerhill.com 비스타 웰니스 클럽) — 피트니스 "비스타 워커힐 서울 투숙객 전용
    # 시설입니다" · 수영장 "비스타워커힐서울 투숙객 전용 시설이며" (◎).
    # 그리고 "모든 부대 시설은 투숙객에 한해 체크아웃 전까지만 이용이 가능합니다"
    # → 체크아웃 뒤 불가로 둔다 (room_key=True). 그랜드 피트니스 쪽 안내에는 이 문장이 없어 모름으로 둔다
    "GRAND_POOL":        FacilityAccess(_F, _U, _F, _U),
    "VISTA_POOL":        FacilityAccess(_N, _F, _N, _N, room_key=True),
    "FITNESS":           FacilityAccess(_F, _U, _F, _U),
    "VISTA_FITNESS":     FacilityAccess(_N, _F, _N, _N, room_key=True),
    # 사우나는 특전이 아니다 — blog21(그랜드) "2만원 추가 결제하고 … 현장에서 결제하게 되어있다"
    #   blog16(비스타) "지하1층의 사우나는 이용권 55,000원". 패키지에 1회 들어 있으면 그건 포함
    #   → 10/11 공식 (그랜드 피트니스 센터): "사우나 : 17세 이상부터 유료 이용 가능 (요금 : 1명 기준 20,000원)" (◎).
    #     비투숙 · 더글라스는 공식에도 안 적혀 모름 그대로
    "WELLNESS_SAUNA":    FacilityAccess(_P, _P, _U, _U),
    # 리버파크 — 투숙객도 따로 낸다 (blog59 "리버파크 자체가 투숙객도 유료로 이용하다 보니" ·
    #   blog27 "실외수영장은 별도 유료").
    #   **9/30 고침 — 비투숙은 불가.** 공식 (walkerhill.com 체험/활동): "객실 투숙객 전용 유료 시설" ·
    #   "야외 수영장은 객실 투숙객 한정 유료 시설로 운영되며 1객실, 1박당 1회 이용 가능합니다" (◎).
    #   9/29 에는 blog04 A(2023)를 근거로 '유료면 비투숙도' 로 뒀는데, 그 방문은 숙박 없이 **숙박 패키지
    #   특전 이용권**으로 들어간 것이었다 ("그 패키지 안에 특전으로 리버파크 성인 2인 이용권이 들어있어서").
    #   지금 규정으로는 그런 손님도 투숙객이 아니다. blog04 A 는 selfcheck 에서 이 사정을 적고 예외로 둔다
    "RIVERPARK":         FacilityAccess(_P, _P, _P, _N),

    # ── 라운지 · 객실 — 자격이 붙은 곳 ────────────────────────────────────
    # 클럽라운지는 클럽 객실 자격이다. 비스타 스위트 패키지도 그랜드 16층을 쓴다
    # (회사 문서 "해피 아워(그랜드 16F, 17:30–19:30)" · blog05 도 GRAND_CLUB_LOUNGE 로 적었다).
    # 클럽이 아닌 투숙객은 모름 — 회사 라운지 상태에 유료 입장(PAID_ACCESS_PURCHASED)이 있어
    # 불가로 못 박지 않았다. 비투숙 불가는 위 LOCATION_PRECONDITIONS(I5)와 같은 판단이다
    "GRAND_CLUB_LOUNGE": FacilityAccess(_U, _U, _U, _N, grand_club=_F, vista_club=_F),
    "DOUGLAS_LOUNGE":    FacilityAccess(_U, _U, _F, _N),
    "DOUGLAS_LIBRARY":   FacilityAccess(_U, _U, _F, _N),
    "DOUGLAS_LOBBY":     FacilityAccess(_U, _U, _O, _U),
    "GRAND_ROOM":        FacilityAccess(_F, _N, _N, _N, room_key=True),
    "VISTA_ROOM":        FacilityAccess(_N, _F, _N, _N, room_key=True),
    "DOUGLAS_ROOM":      FacilityAccess(_N, _N, _F, _N, room_key=True),

    # ── 전시 — 누구나 표를 산다 (blog20 비투숙 "성인입장권 + 딥블루에이드 패키지 상품으로 구매했어요") ──
    "THEATRE_OF_LIGHT":  FacilityAccess(_P, _P, _P, _P),
    "THEATRE_ART_SHOP":  FacilityAccess(_O, _O, _O, _O),
    "CU_THEATRE":        FacilityAccess(_O, _O, _O, _O),

    # ── 식음 — 비투숙도 온다 (회사 비투숙 타입 DINING_ONLY_GUEST) ────────────
    # 개발용 비투숙 후기가 실제로 간 곳: 온달(blog13) · 더뷔페(blog09 · 22 · 24 · 40 · 52) ·
    # 피자힐(blog18 · 57) · 르 파사쥬(blog44). 더뷔페는 안내도 있다 — blog30 "투숙객이 아니더라도
    # 이용은 가능하지만 투숙객은 20% 할인된 가격으로". 나머지는 회사 문서만 (○)
    "ONDAL":             FacilityAccess(_O, _O, _O, _O),
    "GEUMRYONG":         FacilityAccess(_O, _O, _O, _O),
    "MYONGWOLGWAN":      FacilityAccess(_O, _O, _O, _O),
    "MOEGI":             FacilityAccess(_O, _O, _O, _O),
    "PIZZA_HILL":        FacilityAccess(_O, _O, _O, _O),
    "THE_BUFFET":        FacilityAccess(_O, _O, _O, _O),
    "THE_PAVILION":      FacilityAccess(_O, _O, _O, _O),
    "LE_PASSAGE":        FacilityAccess(_O, _O, _O, _O),
    "LUX_BAR":           FacilityAccess(_O, _O, _O, _O),

    # ── 공용 · 교통 ───────────────────────────────────────────────────
    "HOTEL_GATE":        FacilityAccess(_O, _O, _O, _O),
    "VALET_DESK":        FacilityAccess(_O, _O, _O, _O),
    "PARKING_TOWER_B1":  FacilityAccess(_O, _O, _O, _O),
    "PARKING_TOWER_4F":  FacilityAccess(_O, _O, _O, _O),
    "GRAND_LOBBY":       FacilityAccess(_O, _O, _O, _O),
    "GRAND_FRONT_DESK":  FacilityAccess(_O, _O, _O, _O),
    "VISTA_LOBBY":       FacilityAccess(_O, _O, _O, _O),
    "ANNEX":             FacilityAccess(_O, _O, _O, _O),
    "CONVENTION":        FacilityAccess(_O, _O, _O, _O),
    # 골프는 패키지 이용권만 보인다. 누가 들어가는지 근거가 없다
    "GOLF_CLUB":         FacilityAccess(_U, _U, _U, _U),
    # 테네즈 — 9/30 공식 (walkerhill.com 체험/활동): "워커힐 호텔앤리조트 피트니스 회원 및 투숙객 전용
    #   유료 시설입니다" · 주중 80,000 / 일요일·공휴일 100,000 (코트 1면 · 기준 4인). 회원은 예외 —
    #   에이전트는 회원을 다루지 않는다
    "TENNEZ_PARK":       FacilityAccess(_P, _P, _P, _N),
}


def facility_entry(place: str, *, is_guest: bool, building: str | None = None,
                   club_access: bool = False, checked_out: bool = False) -> Entry:
    """이 손님이 이 장소에 들어가나. 표에 없는 장소는 모름.

    building — 투숙 건물 (Persona.property: GRAND · VISTA · DOUGLAS).
    checked_out — 체크아웃 뒤. 체크아웃 뒤 못 들어간다는 근거가 있는 곳(room_key)만 막는다.
    """
    access = FACILITY_ACCESS.get(place)
    if access is None:
        return Entry.UNKNOWN
    if not is_guest:
        return access.non_guest
    if checked_out and access.room_key:
        return Entry.NO
    if club_access:
        club = {"GRAND": access.grand_club, "VISTA": access.vista_club}.get(building or "")
        if club is not None:
            return club
    by_building = {"GRAND": access.grand, "VISTA": access.vista, "DOUGLAS": access.douglas}
    return by_building.get(building or "", Entry.UNKNOWN)


def may_enter(place: str, **guest) -> bool | None:
    """들어가면 True · 못 들어가면 False · 근거가 없으면 None (막지도 열지도 않는다)."""
    entry = facility_entry(place, **guest)
    return None if entry is Entry.UNKNOWN else entry is not Entry.NO


# ── 소연 추가 · 9/30 · 가정표(장소) — 가격 · 좌석 · 객실 수 · 운영 시간 ─────────────────
#
# 멘토링(9/30) 뒤 새 방향 — 에이전트가 움직일 때마다 쓴 돈을 붙여 매출 · 객단가 · ADR · RevPAR 로 합산한다.
# 그 숫자들을 장소 코드별로 모은 표가 place_assumptions.csv 다 (팀 드라이브 가정표의 '장소' 칸).
# 줄마다 값 · 단위 · 조건 · 등급(◎ 공식 / ○ 논리 / △ 추정 / 모름) · 출처 · 근거 문장 · 현장확인이 있다.
# 근거 문장은 출처에 글자 그대로 있다 — 회사 문서는 selfcheck 가 매번 보고, 후기 원문(저장소 밖)과
# 웹 출처(walkerhill.com · 관광공사 · 빛의 시어터 운영사)는 9/30 에 따로 대조했다.
# 설명과 현장 확인 목록은 docs/가정표_장소.md.
#
# 검증 판정(I1~I6)에는 쓰지 않는다. 운영 시간이 검증기 창과 다른 곳은 문서에 적었고 창은 안 바꿨다.
PLACE_ASSUMPTIONS_CSV = Path(__file__).with_name("place_assumptions.csv")


def load_place_assumptions(place: str | None = None) -> list[dict[str, str]]:
    """가정표(장소)를 읽는다. place 를 주면 그 장소 코드 줄만. 값은 문자열 그대로다 (단위 칸을 보고 바꾼다)."""
    with PLACE_ASSUMPTIONS_CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows if place is None else [r for r in rows if r["장소코드"] == place]


# --------------------------------------------------------------------------
# 타임라인
# --------------------------------------------------------------------------


@dataclass
class TimelineSegment:
    """타임라인 한 구간. t_out - t_in 이 그 상태의 dwell time."""

    state: str
    location: str
    t_in: datetime
    t_out: datetime
    machine: str = "M2_Stay"
    venue: str | None = None  # 운영 창을 검사할 업장 키 (없으면 창 검사 생략)

    @property
    def dwell_min(self) -> float:
        return (self.t_out - self.t_in).total_seconds() / 60


@dataclass
class TimelineViolation:
    invariant: str
    code: str
    detail: str
    at: datetime


@dataclass
class TimelineReport:
    violations: list[TimelineViolation] = field(default_factory=list)
    total_travel_min: float = 0.0
    stay_day_span_min: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.violations

    def render(self) -> str:
        head = "PASS — 불변식 I1~I6 모두 충족" if self.ok else f"FAIL — 위반 {len(self.violations)}건"
        lines = [head]
        if self.stay_day_span_min:
            share = self.total_travel_min / self.stay_day_span_min * 100
            lines.append(
                f"  총 이동 시간: {self.total_travel_min:.0f}분 "
                f"(투숙 기간 {self.stay_day_span_min / 60:.0f}시간 중 {share:.1f}%)"
            )
        else:
            lines.append(f"  총 이동 시간: {self.total_travel_min:.0f}분")
        for v in self.violations:
            lines.append(f"  [{v.invariant} {v.code}] {v.at:%m-%d %H:%M}  {v.detail}")
        return "\n".join(lines)


def stay_day_bounds(check_in_date: datetime, nights: int = 1) -> tuple[datetime, datetime]:
    """I6 — 투숙일은 자정이 아니라 15:00 → 체크아웃일 11:00 이다.

    nights — 숙박 일수 (bk 추가). 원본은 1박 고정이라 2박 후기(blog01)의 둘째 날이 통째로 위반이었다.
    """
    start = datetime.combine(check_in_date.date(), CHECK_IN_TIME)
    end = datetime.combine(check_in_date.date() + timedelta(days=nights), CHECK_OUT_TIME)
    return start, end


def _fits_any_window(segment: TimelineSegment) -> tuple[bool, str]:
    """운영 창 검사.

    맞는 창이 없으면 **가장 가까운 창 하나만** 근거로 제시한다. 더뷔페처럼 슬롯이
    6개인 업장에서 전부 나열하면 메시지가 읽히지 않는다.
    """
    windows = WALKERHILL_VENUE_WINDOWS.get(segment.venue or "", ())
    if not windows:
        return True, ""

    requested = f"{segment.t_in:%H:%M}~{segment.t_out:%H:%M}"

    # 그 상태에만 걸리는 창이 하나라도 있으면 **그것들로만** 판정한다.
    # 안 그러면 넓은 매장 창(르 파사쥬 09:00~21:00)이 좁은 주문 창(11:00~19:30)을
    # 덮어 버려서, 마감 뒤 주문도 통과한다.
    scoped = tuple(w for w in windows if w.states and segment.state in w.states)
    general = tuple(w for w in windows if not w.states)
    applicable = scoped or general
    if not applicable:
        # 창이 **전부 상태 한정**인데 이 상태가 어느 목록에도 없다.
        # 여기서 통과시키면 그 업장이 통째로 검사에서 빠진다 — `venue` 를 안 붙였을
        # 때와 같은 실패 방식이고, 리포트에는 PASS 로만 보인다.
        # 어느 창에도 안 걸리는 행위는 그 업장에서 할 수 없는 행위로 본다.
        allowed = sorted({s for w in windows for s in (w.states or ())})
        return False, (
            f"이 업장에 정의되지 않은 행위 ({segment.state} / 요청 {requested}"
            f" · 정의된 상태 {allowed})"
        )
    windows = applicable

    nearest: tuple[VenueWindow, float, bool] | None = None

    for window in windows:
        if not window.opens_on(segment.t_in.date()):
            continue                      # 그 기간·연도에는 존재하지 않는 창
        open_at = datetime.combine(segment.t_in.date(), window.open_at)
        close_at = datetime.combine(segment.t_in.date(), window.close_at)
        last_order = datetime.combine(segment.t_in.date(), window.effective_last_order())

        # 유예는 **나가는 상태에만** 준다. 이용 상태에 주면 마감을 넘겨 노는 하루가
        # 통과해서, 다음 타임 손님과 겹친다.
        grace = window.exit_grace_min if segment.state in EXIT_STATES else 0
        leave_by = close_at + timedelta(minutes=grace)
        within_window = open_at <= segment.t_in and segment.t_out <= leave_by

        # 유예를 쓰는 퇴장이 마감 **이전**까지 길게 걸쳐 있으면 그건 퇴장이 아니라
        # 이용이다. 이걸 안 막으면 구간 전체를 EXITED 로 이름만 바꿔 20분을 더
        # 쓸 수 있다 — `ENTERED 10:00~14:50` 을 막아 놓고 `EXITED 10:00~14:50` 을
        # 열어 두면 같은 구멍이 한 칸 옆으로 옮겨간 것뿐이다.
        if grace and segment.t_out > close_at:
            before_close_min = (close_at - segment.t_in).total_seconds() / 60
            if before_close_min > grace:
                within_window = False

        # `effective_last_order()` 는 L.O. 가 없으면 **마감 시각**을 대신 쓴다.
        # 그 대체값이 퇴장까지 막아서, `EXITED 14:35~14:50` 같은 맞는 퇴장이
        # I3 로 떨어졌다 — 마감 시각에 **정확히** 시작하는 퇴장만 통과했다.
        #
        # 그래서 푸는 건 **L.O. 가 선언되지 않은 창의 퇴장뿐**이다.
        # 상태만 보고 풀면(`state in EXIT_STATES`) L.O. 가 실제로 있는 업장까지
        # 뚫린다. 온달·피자힐·파빌리온이 그런데, 셋 다 §3.2 식음 어휘를 써서
        # `EXITED` 가 올 자리가 아니다 — 이름을 잘못 붙여야만 닿는 통과 경로가
        # 20개 생긴다. 실익 없이 느슨해지는 쪽이라 좁힌다.
        skip_last_order = window.last_order is None and segment.state in EXIT_STATES
        before_last_order = skip_last_order or segment.t_in <= last_order
        if within_window and before_last_order:
            return True, ""

        # 요청 구간이 이 창에서 얼마나 벗어났는지 — 앞뒤 초과분의 합
        overrun_before = max(0.0, (open_at - segment.t_in).total_seconds())
        overrun_after = max(0.0, (segment.t_out - close_at).total_seconds())
        distance = overrun_before + overrun_after
        if nearest is None or distance < nearest[1]:
            nearest = (window, distance, within_window and not before_last_order)

    if nearest is None:
        # 그 날짜에 열리는 창이 **하나도 없다.** 기간(season)이 생기기 전에는
        # 있을 수 없던 경우라 원래 `assert` 로 막혀 있었는데, 리버파크를 비시즌에
        # 쓰면 실제로 생긴다. **위반이지 예외가 아니다** — assert 로 두면
        # 위반 목록이 나오는 대신 검증기가 멈춘다(노드 누락과 같은 실패 방식).
        day = segment.t_in.date()
        # 10/5 — 연도 · 기간은 맞는데 **요일 · 공휴일 · 닫는 기간**에서 빠진 경우를 먼저 말한다.
        # "기간 밖" 으로 읽히면 날짜를 시즌 안쪽으로 옮기는데, 요일이 문제면 안 고쳐진다.
        # '운영하지 않음' 이라고 단정하지 않는다 — 근거가 일부 요일 것뿐이면 **창이 없는 것**과
        # 실제로 닫는 것을 우리가 못 가른다 (처음 리버파크 2026 을 금~일만 넣었을 때가 그랬다).
        same_period = [w for w in windows
                       if (w.years is None or day.year in w.years) and w.in_season(day)]
        if same_period:
            rules = " / ".join(dict.fromkeys(w.day_rule_text() for w in same_period))
            holiday = " · 공휴일" if is_public_holiday(day) else ""
            return False, (
                f"이 요일에 열리는 창 없음 ({day:%Y-%m-%d} {'월화수목금토일'[day.weekday()]}{holiday}"
                f" / 요청 {requested} · 이 기간 창의 요일 {rules})"
            )
        # 시즌은 맞는데 **연도**가 안 맞는 경우를 따로 말한다. 한 문장으로 뭉치면
        # 2026년 사람이 "시즌 밖" 으로 읽고 날짜만 옮기는데, 어느 날짜로 옮겨도
        # 안 열린다 — 그 해 시간표를 우리가 안 가진 것이지 기간 문제가 아니다.
        known_years = sorted({y for w in windows for y in (w.years or ())})
        if known_years and any(w.in_season(day) for w in windows):
            return False, (
                f"이 연도의 운영 시간을 모름 ({day:%Y-%m-%d} / 요청 {requested}"
                f" · 등록된 창은 {known_years} 년 근거뿐)"
            )
        return False, (
            f"해당 기간에 운영하지 않음 ({segment.t_in:%m-%d} / 요청 {requested}"
            f" · 등록된 창 {len(windows)}개는 다른 기간에만 열림)"
        )

    assert nearest is not None
    window, _, past_last_order = nearest
    # 그 날 **열리는** 회차만 센다 (10/5). 등록된 창 전부를 세면 더뷔페가 요일 창 13개라
    # 토요일에 "13개 중" 이 되는데, 그 날 실제 회차는 6개다. 같은 시각 창은 한 번만 센다
    # (2026 여름 조식 매일 2부제는 주말 창과 시각이 같다).
    n_open = len({(w.open_at, w.close_at) for w in windows if w.opens_on(segment.t_in.date())})
    slot_suffix = f" · 운영 슬롯 {n_open}개 중 맞는 구간 없음" if n_open > 1 else ""

    if past_last_order:
        return False, (
            f"주문 마감 경과 (운영 {window.open_at:%H:%M}~{window.close_at:%H:%M}, "
            f"L.O. {window.effective_last_order():%H:%M} / 요청 {requested})"
        )
    return False, (
        f"영업시간 외 이용 (운영 {window.open_at:%H:%M}~{window.close_at:%H:%M} / "
        f"요청 {requested}){slot_suffix}"
    )


def validate_walkerhill_timeline(
    segments: list[TimelineSegment],
    enforce_stay_day: bool = True,
    nights: int = 1,
) -> TimelineReport:
    """§9.3 검증 알고리즘. 위반을 전부 모아서 반환한다 (첫 위반에서 멈추지 않음).

    nights — 숙박 일수. I6 하루 경계를 그만큼 늘린다. 기본 1박.
    """
    report = TimelineReport()
    if not segments:
        return report

    ordered = sorted(segments, key=lambda s: s.t_in)
    # 배경 상태(대기 등)는 위치를 점유하지 않는다. 이동 체인에서 뺀다.
    moving = [s for s in ordered if s.state not in BACKGROUND_STATES]
    day_start, day_end = stay_day_bounds(ordered[0].t_in, nights)
    report.stay_day_span_min = (day_end - day_start).total_seconds() / 60

    for previous, current in zip(moving, moving[1:]):
        # I1 단조성
        if current.t_in < previous.t_out:
            report.violations.append(
                TimelineViolation(
                    "I1", "TIMELINE_REWIND",
                    f"{current.state} 이 {previous.state} 종료({previous.t_out:%H:%M}) 전에 시작",
                    current.t_in,
                )
            )
            continue

        # I2 이동 가능성
        needed = walkerhill_travel_time_min(previous.location, current.location, previous.t_out)
        report.total_travel_min += needed
        gap_min = (current.t_in - previous.t_out).total_seconds() / 60
        if gap_min + 1e-9 < needed:
            report.violations.append(
                TimelineViolation(
                    "I2", "TELEPORT",
                    f"{previous.location}→{current.location} 필요 {needed:.0f}분, "
                    f"확보 {gap_min:.0f}분 (부족 {needed - gap_min:.0f}분)",
                    current.t_in,
                )
            )

    for segment in ordered:
        # I3 운영 창
        fits, reason = _fits_any_window(segment)
        if not fits:
            report.violations.append(
                TimelineViolation("I3", "OUTSIDE_WINDOW", f"{segment.venue}: {reason}", segment.t_in)
            )

        # I6 하루 경계 — 객실 점유 상태에만 (docs §9.2). ROOM_OCCUPANCY_STATES 주석 참조.
        if enforce_stay_day and segment.state in ROOM_OCCUPANCY_STATES:
            if segment.t_in < day_start or segment.t_out > day_end:
                report.violations.append(
                    TimelineViolation(
                        "I6", "DAY_BOUNDARY_VIOLATED",
                        f"{segment.state} 이 StayDay[{day_start:%m-%d %H:%M}~"
                        f"{day_end:%m-%d %H:%M}] 밖",
                        segment.t_in,
                    )
                )

    # I4 물리적 배타성 — 배경 상태(대기)는 위치를 점유하지 않는다
    exclusive = [
        s for s in ordered
        if s.state in PHYSICALLY_EXCLUSIVE_STATES and s.state not in BACKGROUND_STATES
    ]
    for a, b in zip(exclusive, exclusive[1:]):
        if b.t_in < a.t_out:
            report.violations.append(
                TimelineViolation(
                    "I4", "DOUBLE_BOOKED",
                    f"{a.state}@{a.location} 과 {b.state}@{b.location} 구간이 겹침 — "
                    f"동시에 두 장소를 점유할 수 없음",
                    b.t_in,
                )
            )

    # I5 전제 상태
    seen: set[str] = set()
    for segment in ordered:
        required = STATE_PRECONDITIONS.get(segment.state)
        if required and not (required & seen):
            report.violations.append(
                TimelineViolation(
                    "I5", "PRECONDITION_VIOLATED",
                    f"{segment.state} 진입 전 {sorted(required)} 중 하나가 필요",
                    segment.t_in,
                )
            )
        # 장소 전제 — 투숙객 전용 장소는 키 발급 뒤에만 (배경 상태 제외)
        loc_required = LOCATION_PRECONDITIONS.get(segment.location)
        if loc_required and segment.state not in BACKGROUND_STATES and not (loc_required & seen):
            report.violations.append(
                TimelineViolation(
                    "I5", "PRECONDITION_VIOLATED",
                    f"{segment.location} 은 투숙객 전용 — 진입 전 {sorted(loc_required)} 중 하나가 필요",
                    segment.t_in,
                )
            )
        seen.add(segment.state)

    report.violations.sort(key=lambda v: v.at)
    return report
