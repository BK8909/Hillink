"""
blog03 후기(4부작)을 상태 열로 옮긴다.

한 사람이 워커힐에 **두 번** 묵은 기록이다.
  체류 A · 비스타 워커힐 1박 — 2022-08-04(목)      ← 1편(수영장·피자힐 TOGO) + 2편(라운지·객실)
  체류 B · 그랜드 워커힐 1박 — 2023-05-12~13(금~토) ← 3편(스카이야드·조식) + 4편(라운지·객실)

1편에서 르파사쥬 TOGO 로 편하게 받은 피자를 3편에서는 마감을 놓쳐 셔틀로 직접 가져온다.
비스타에서는 수영장에서 놀고, 그랜드에서는 수영장을 보고 건너뛴 뒤 스카이야드로 간다.
같은 사람이 같은 부지에서 **두 번 다르게 움직인** 것이 이 4부작의 값어치다.

실행:  cd timeline && python blog03.py

수집 경로: 사람이 브라우저에서 직접 캡처한 것을 판독·전사했다. 긁지 않았다.

── 시각 표기 ─────────────────────────────────────────────────────────────
원문에 **숫자로 적힌 시각은 두 군데뿐**이다.

  ◎ "TOGO 주문 마감은 오후 7시 30분 … 저는 아슬아슬하게 성공했는데"   (1편)
  ◎ "따뜻한 물에서 20분쯤 족욕을 했더니"                              (3편)

방향만 주는 서술이 몇 개 더 있다.

  · "시원한 바람이 부는 저녁 시간대라 기다리기 나쁘지 않았습니다"      (3편) → 피자힐은 저녁
  · "객실에서 수영복으로 갈아입고, 가운을 걸치고 … 그대로 내려갑니다"  (1편) → 객실에서 수영장 직행
  · "차량에서 캐리어를 꺼내고, 카드사 혜택으로 발렛을"                 (4편) → 자차 도착, 발렛

나머지 시각은 순서를 지키려고 찍은 자리표시값이고 미상이다.
이 시각들은 실제 방문 시각을 재현한 값이 아니라 정합성 검증용 배치다.

최종 변환 기준
- 상태 이름과 업장별 어휘는 회사 문서 §3의 해당 행을 따른다.
- 명시되지 않은 시각은 이동시간과 운영 창을 만족하는 검증용 배치다.
- 운영 창의 출처, 검증 결과와 남은 제약은 NOTES-soyeon.md를 참조한다.

검증기 문제와 수정 근거

기준은 공식 홈페이지, 목표는 정합성 오류 0건이다.
회사 원본으로 돌리면 두 체류 모두 KeyError 로 **검증 자체가 멈춘다.**


[1] KeyError — 검증이 아예 멈춤
    걸린 곳  VISTA_ROOM -> VISTA_POOL (체류 A) · HOTEL_GATE -> VALET_DESK (체류 B)
    판정  **검증기.** §8.2 노드 목록엔 있는데 §8.4 매트릭스에 없다.
          위반이 나오는 게 아니라 예외로 멈춰서 나머지도 못 잰다.
    조치  후기가 지나는 노드만 넣었다. 기존 21개 노드 사이 420쌍의 거리는
          한 값도 안 바뀐다 (selfcheck 안전장치 1).

[2] I3 — 08-04 19:25~19:55 르파사쥬 (운영 11:00~19:30)
    후기  1편 "TOGO 주문 마감은 오후 7시 30분 … 아슬아슬하게 성공했는데"
          "피자를 기다리는 동안 케이크도 구경했습니다"
    판정  **검증기.** 19:30 은 매장 마감이 아니라 **주문 접수 마감**이다.
          공식 페이지에 둘이 따로 적혀 있다(2026-09-22 확인) —
          영업시간 연중 09:00~21:00 / 테이크아웃 피자 주문시간 11:00~19:30.
          한 창에 뭉쳐 있어서 매장 09:30 이용도, 마감 뒤 수령도 전부 반려된다.
    조치  `VenueWindow.states` 로 행위별 창을 나눴다. 매장 창만 넓히면
          반대로 09:30·20:00 **주문**까지 통과해서 느슨해진다.
          변환도 주문·대기·수령을 TAKEOUT_ORDER · BROWSING · PICKED_UP 으로 갈랐다.


── 0건과는 무관하지만 공식과 값이 달랐던 것 ──────────────────────

[3] 피자힐 운영 시간이 공식과 다름
    등록값  11:30~22:30
    공식    회차제 8부 · 1부 11:00 ~ 8부 23:00 (2026-09-22 확인)
    판정  **검증기.** 다만 내 후기 시각(19:35~20:10)은 원본에서도 통과해서
          **후기로는 안 보였다.** 공식 페이지를 다시 확인하다 찾았다.
    조치  운영 시간만 11:00~23:00 으로 맞췄다. L.O. 는 공식에 표기가 없어
          회사 값 21:00 을 그대로 둔다 — 8부가 21:30 에 시작하니 어긋나
          보이지만 그건 내 추론이다.


── 원본에 없어서 채운 것 (틀린 판정이 아니라 비어 있던 자리) ─────

[4] 부대시설에 운영 창이 없어 새벽 3시 이용도 통과했다
    판정  **검증기 아님.** 창이 없으면 통과시키는 건 설계된 동작이다
          (대부분의 업장이 그렇다). 그 장소를 아예 안 다루고 있던 것이다.
    조치  후기가 지나는 시설만 공식 값으로 넣었다 — 그랜드·비스타 수영장
          06:00~21:30, SKYARD 09:00~22:00. 채우면 검사가 엄격해지는 쪽이다.
          ※ 2026-09-22 에 해당 안내 페이지를 다시 못 찾아 **재확인 안 됨**으로
            남긴다(selfcheck 대조표에 표시).
          ※ 원본에 수영장 노드가 **아예 없었다.** 그랜드·비스타가 한 노드였던
            게 아니다.
"""

from datetime import datetime

from walkerhill_timeline_validator import (
    TimelineSegment,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)

A1, A2 = "2022-08-04", "2022-08-05"   # 비스타 1박 (목~금)
B1, B2 = "2023-05-12", "2023-05-13"   # 그랜드 1박 (금~토)


def t(day, hhmm):
    return datetime.fromisoformat(f"{day}T{hhmm}")


def seg(state, location, day, a, b, machine="M2_Stay", venue=None, day_out=None):
    return TimelineSegment(state, location, t(day, a), t(day_out or day, b),
                           machine=machine, venue=venue)


# ---------------------------------------------------------------------------
# 체류 A · 비스타 1박 (2022-08-04)
# ---------------------------------------------------------------------------
# 2편: "라운지에 들어서니 고급스러운 갤러리에 들어온 느낌"
#      "1층 라운지 뒤편에 전시공간이 있다 보니, 체크인 대기가 있어도 구경거리가 있어서 좋았습니다"
#      → 체크인 **전에** 라운지·전시공간에 있었다. 대기를 따로 상태로 두지 않고
#        실제로 한 행동(라운지 이용)으로 적는다.
# 1편: "객실에서 수영복으로 갈아입고, 가운을 걸치고, 슬리퍼를 신고 그대로 내려갑니다. 수영장은 3층입니다"
#      "위치는 그랜드 워커힐 쪽 르파사쥬 베이커리입니다" → 비스타 투숙객이 그랜드로 건너간다
#      "TOGO 주문 마감은 오후 7시 30분 … 아슬아슬하게 성공"

STAY_A = [
    seg("ARRIVED_ON_PROPERTY", "VISTA_LOBBY", A1, "14:30", "14:35"),
    # 체크인 **전**이라 업장 세션이 아니라 대기 상태다.
    # M2 에 `LOUNGE_WAITING` 이 있다 (EARLY_ARRIVAL_ROOM_NOT_READY · LUGGAGE_STORED 와
    # 같은 줄). `IN_LOUNGE` 는 업장 세션이라 여기 쓰면 I6 에 걸린다.
    seg("LOUNGE_WAITING", "VISTA_LOBBY", A1, "14:35", "15:15"),
    seg("AT_FRONT_DESK", "VISTA_LOBBY", A1, "15:15", "15:25"),
    seg("KEY_ISSUED",   "VISTA_LOBBY", A1, "15:25", "15:28"),
    seg("IN_ROOM",      "VISTA_ROOM",  A1, "15:36", "16:40"),
    # "수영장은 3층입니다" — 비스타 쪽. 그랜드 수영장과 **다른 시설**이다.
    # 16:40 출발은 피크(15~17)라 객실→수영장이 9분의 두 배인 18분으로 잡힌다.
    #
    # 상태는 §3.3 "스파·사우나·그랜드피트니스" 행의 `CHECKED_IN` 을 쓴다.
    # `ENTERED` 는 **리버파크(야외)** 행이라 여기 쓰면 안 된다 —
    # 실내 수영장은 피트니스 센터 안이라 세션 어휘가 다르다.
    seg("CHECKED_IN", "VISTA_POOL", A1, "17:00", "18:30",
        machine="M7_Outlet", venue="VISTA_POOL"),
    seg("IN_ROOM", "VISTA_ROOM", A1, "18:40", "19:00"),
    # 르 파사쥬는 §3.2 **구르메 스토어** 행이고 어휘가 따로다:
    #   `BROWSING` `TAKEOUT_ORDER` `PICKUP_SCHEDULED` `PICKED_UP` …
    # 피자힐 포장(§3.2 테이크아웃 행)의 `TAKEOUT_ORDERED` 와 **이름이 다르다.**
    #
    # **주문·대기·수령을 나눈다.** 매장은 21:00 까지지만 피자 주문 접수는 19:30 마감이라,
    # 셋을 한 구간으로 묶으면 주문 창을 넘겨 버린다. 후기도 셋을 따로 적는다.
    #   "TOGO 주문 마감은 오후 7시 30분 … 저는 아슬아슬하게 성공했는데"   ← 주문
    #   "피자를 기다리는 동안 케이크도 구경했습니다" / "에노테카에 가 봤더니"  ← 대기
    #   "슬슬 피자가 나올 것 같아 자리로 돌아갔습니다"                      ← 수령
    seg("TAKEOUT_ORDER", "LE_PASSAGE", A1, "19:20", "19:25",
        machine="M7_Outlet", venue="LE_PASSAGE"),
    seg("BROWSING", "LE_PASSAGE", A1, "19:25", "19:50",
        machine="M7_Outlet", venue="LE_PASSAGE"),
    seg("PICKED_UP", "LE_PASSAGE", A1, "19:50", "19:55",
        machine="M7_Outlet", venue="LE_PASSAGE"),
    seg("IN_ROOM", "VISTA_ROOM", A1, "20:10", "10:30", day_out=A2),
    seg("CHECKED_OUT_SETTLED", "VISTA_LOBBY", A2, "10:36", "10:45"),
]


# ---------------------------------------------------------------------------
# 체류 B · 그랜드 1박 (2023-05-12 ~ 13)
# ---------------------------------------------------------------------------
# 4편: "차량에서 캐리어를 꺼내고, 카드사 혜택으로 발렛을 무료로 이용했습니다"
#      "2층 제일 안쪽에 자리 잡은 라이브러리입니다"
# 3편: "그랜드 워커힐에도 수영장이 있습니다. 잠깐 가 봤는데 … 건너뛰고 스카이야드를 골랐습니다"
#      "스카이야드는 비스타 워커힐 건물 쪽에 있는 야외 족욕 시설입니다"
#      "따뜻한 물에서 20분쯤 족욕을 했더니"
#      "TOGO 주문 시간대를 놓쳐 버렸습니다 … 결국 셔틀을 타고 직접 다녀왔습니다"
#      "갈 때는 셔틀버스, 올 때는 세단이었으니까요"

STAY_B = [
    seg("SELF_DRIVE_ARRIVING", "HOTEL_GATE", B1, "14:40", "14:45", machine="M5_Transport"),
    seg("VALET_RECEIVED", "VALET_DESK", B1, "14:46", "14:52", machine="M5_Transport"),
    seg("ARRIVED_ON_PROPERTY", "GRAND_LOBBY", B1, "14:55", "15:00"),
    # 여기도 체크인 전이다 (체크인 15:32). 같은 이유로 LOUNGE_WAITING.
    seg("LOUNGE_WAITING", "GRAND_LOBBY", B1, "15:00", "15:30"),
    seg("AT_FRONT_DESK", "GRAND_FRONT_DESK", B1, "15:32", "15:40"),
    seg("KEY_ISSUED",   "GRAND_FRONT_DESK", B1, "15:40", "15:43"),
    seg("IN_ROOM",      "GRAND_ROOM",       B1, "15:51", "16:20"),
    # "잠깐 가 봤는데" — 그랜드 것을 둘러보고 나왔다. 비스타 것과 다른 시설.
    seg("CHECKED_IN", "GRAND_POOL", B1, "16:45", "16:55",
        machine="M7_Outlet", venue="GRAND_POOL"),
    # 족욕 20분 ◎ + 앞뒤 구경.
    # 그랜드 지하 2층 → 비스타 4층이라 피크에 40분이 걸린다(기본 20분 × 2).
    #
    # **SKYARD 는 §3.3 비-식음 시설 세션 표에 행이 없다.** 노드 목록(§8.2)과
    # 비스타 공통특전(§6.2)에만 나온다. 세션 상태가 정의돼 있지 않아서,
    # 같은 야외 입장형인 포레스트 파크 행(`TICKETED ADMITTED EXITED`)의
    # `ADMITTED` 를 빌려 썼다. **회사에 물어야 할 항목**이다.
    # machine 은 M7 이다 — §3.3 은 §3(M7 OutletSessionMachine) 안에 있다.
    # (M8 은 `IssueMachine` 이라 시설 세션과 무관하다.)
    seg("ADMITTED", "SKYARD", B1, "17:35", "18:20", machine="M7_Outlet", venue="SKYARD"),
    seg("IN_ROOM", "GRAND_ROOM", B1, "18:40", "19:20"),
    seg("TAKEOUT_ORDERED", "PIZZA_HILL", B1, "19:35", "20:10",
        machine="M7_Outlet", venue="PIZZA_HILL"),
    seg("IN_ROOM", "GRAND_ROOM", B1, "20:25", "08:00", day_out=B2),
    seg("TIME_LIMIT_ACTIVE", "THE_BUFFET", B2, "08:30", "09:50",
        machine="M7_Outlet", venue="THE_BUFFET"),
    seg("IN_ROOM", "GRAND_ROOM", B2, "10:10", "10:40"),
    seg("CHECKED_OUT_SETTLED", "GRAND_FRONT_DESK", B2, "10:48", "10:55"),
]


STAYS = [
    ("체류 A · 비스타 1박 (2022-08-04) — 3층 수영장 · 르파사쥬 TOGO 마감 직전", STAY_A),
    ("체류 B · 그랜드 1박 (2023-05-12~13) — 스카이야드 족욕 · TOGO 놓쳐 피자힐 직접", STAY_B),
]


def main():
    for title, segments in STAYS:
        print("=" * 72)
        print(title)
        print("=" * 72)
        try:
            print(validate_walkerhill_timeline(segments, enforce_stay_day=True).render())
        except Exception as exc:  # noqa: BLE001
            print(f"검증 불가 — {type(exc).__name__}: {exc}")
            print("위반 목록이 나오는 게 아니라 검증 자체가 멈춘다.")
        print()

    print("=" * 72)
    print("이동 시간 조회 — 후기에 나오는 구간")
    print("=" * 72)
    legs = [
        ("VISTA_ROOM", "VISTA_POOL", t(A1, "16:40")),
        ("VISTA_ROOM", "LE_PASSAGE", t(A1, "19:00")),
        ("GRAND_ROOM", "GRAND_POOL", t(B1, "16:20")),
        ("GRAND_POOL", "SKYARD", t(B1, "16:40")),
        ("GRAND_ROOM", "PIZZA_HILL", t(B1, "19:20")),
        ("GRAND_ROOM", "THE_BUFFET", t(B2, "08:00")),
    ]
    for a, b, when in legs:
        try:
            print(f"  {when:%m-%d %H:%M}  {a:<12} -> {b:<12} "
                  f"{walkerhill_travel_time_min(a, b, when):5.1f}분")
        except Exception as exc:  # noqa: BLE001
            print(f"  {when:%m-%d %H:%M}  {a:<12} -> {b:<12} 오류: {exc}")


if __name__ == "__main__":
    main()
