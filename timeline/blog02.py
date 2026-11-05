"""블로그 02 — 더글라스 하우스 방문 후기를 상태 타임라인으로 변환.

대상: blog02 후기 — 더글라스하우스 1박 (URL 은 노션 대응표에만)

실행: cd timeline && python blog02.py

블로그는 과거 방문 기록일 수 있다. 따라서 후기의 행동 순서와 페르소나 근거로만
쓰고, 현재 운영시간·이동시간·시설 데이터는 이 저장소의 검증기 값을 우선한다.
후기에 방문 날짜는 없고 토요일이라는 언급만 있으므로, 2024-06-15는 실행용 가정이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from walkerhill_timeline_validator import TimelineSegment, validate_walkerhill_timeline


DAY = "2024-06-15"       # 토요일 — 후기에는 정확한 방문 날짜가 없음
NEXT_DAY = "2024-06-16"
SOURCE_URL = "blog02 (노션 대응표 참조)"


def t(hhmm: str, *, next_day: bool = False) -> datetime:
    return datetime.fromisoformat(f"{NEXT_DAY if next_day else DAY}T{hhmm}")


def seg(
    state: str,
    location: str,
    start: str,
    end: str,
    *,
    next_day: bool = False,
    end_next_day: bool = False,
    machine: str = "M2_Stay",
    venue: str | None = None,
) -> TimelineSegment:
    return TimelineSegment(
        state=state,
        location=location,
        t_in=t(start, next_day=next_day),
        t_out=t(end, next_day=end_next_day or next_day),
        machine=machine,
        venue=venue,
    )


@dataclass(frozen=True)
class Persona:
    name: str
    party_size: int
    priorities: tuple[str, ...]
    evidence: tuple[str, ...]


PERSONA = Persona(
    name="친구와 라운지·수영을 함께 즐기는 휴식형",
    party_size=4,
    priorities=("무료 셔틀", "함께 앉기", "라운지", "수영", "조용한 휴식", "전망"),
    evidence=(
        "광나루역 무료 셔틀을 이용했다.",
        "여러 명이라 4인석과 뷔페 가까운 자리를 골랐다.",
        "라이트 스낵·수영·더글라스 아워·다음 날 조식을 순서대로 이용했다.",
    ),
)


# 팀장님 요청 형식: 위반 하나를 고칠 때마다 후기 근거 / 책임 판정 / 수정 내용을 세 줄로 남긴다.
# 세 건 모두 검증기 결함이 아니라, 과거 후기의 대략적인 시간을 현재 T(A→B,t)에
# 그대로 대입한 변환 오류다. 검증기 상수는 수정하지 않는다.
FIX_LOG = (
    (
        "후기: 광나루역 무료 셔틀을 이용했고 14:40경 워커힐에 도착했다고 기록했다.",
        "판정: 변환 오류 — 8분 탑승시간만 반영하고 현재 모델의 기대 대기 7.5분을 누락했다.",
        "수정: 현재 외부 이동 16분을 확보하도록 셔틀 출발 기준시각을 14:24로 정규화했다.",
    ),
    (
        "후기: 그랜드에서 더글라스 하우스까지 차량 이동은 약 3분이라고 기록했다.",
        "판정: 변환 오류 — 3분 탑승시간을 프런트 출발부터 객실 도착까지의 시간으로 사용했다.",
        "수정: 현재 모델의 피크 이동 38분을 반영해 키 수령 15:11 → 객실 15:49로 배치했다.",
    ),
    (
        "후기: 라이트 스낵을 먹는 사이 수영장을 이용했다고 기록했다.",
        "판정: 변환 오류 — 라운지에서 수영장으로의 실제 이동 시간을 생략하면 I2 순간이동이 된다.",
        "수정: 라운지 종료 16:24 → 수영 시작 17:20으로, 현재 그래프의 피크 이동 56분을 확보했다.",
    ),
    (
        "후기: 라운지 이용 뒤 수영장으로 이동했다는 순서가 기록되어 있다.",
        "판정: 검증기 오류 — 수영장 이용 상태 ENTERED가 I4 물리 점유 목록에서 빠져 겹침을 I1만 잡았다.",
        "수정: ENTERED를 물리 점유 상태에 추가해 라운지·수영장 동시 이용을 I4 DOUBLE_BOOKED로도 검출한다.",
    ),
    (
        "후기: 다음 날 조식을 07:30경 이용했다고 기록했다.",
        "판정: 변환 오류 — 객실에서 라운지까지의 현재 피크 이동 14분보다 10분 여유가 짧다.",
        "수정: '07:30경' 범위 안에서 조식 좌석 착석을 07:34로 정규화하고, SEATED → DINING으로 행동을 분리했다.",
    ),
)


# 현재 검증기 기준 최종 타임라인. 라운지의 과거 운영시간은 현재 값으로 취급하지
# 않으므로 venue을 넣지 않는다. 현 모델에 DOUGLAS_LOUNGE 운영 창이 없다는 사실은
# 별도 커버리지 과제로 남기며, 이 파일이 임의의 영업시간을 추가하지 않는다.
BLOG02_TIMELINE = [
    # 광나루역 셔틀 이용 + 14:40경 호텔 도착. 현재 외부 이동 모델의 16분(8분 탑승 +
    # 기대 대기)을 확보하기 위한 14:24 출발 기준시각이며, 후기의 분 단위 기록은 아니다.
    seg("SHUTTLE_BOARDED", "GWANGNARU_STN", "14:24", "14:24", machine="M5_Transport"),
    seg("ARRIVED_ON_PROPERTY", "HOTEL_GATE", "14:40", "14:43"),
    # 15시 전 대기는 현재 검증기의 배경 상태다. 대기 중 위치는 이동 체인에 고정하지 않는다.
    seg("IN_CHECKIN_QUEUE", "GRAND_FRONT_DESK", "14:44", "15:00"),
    seg("AT_FRONT_DESK", "GRAND_FRONT_DESK", "15:00", "15:08"),
    seg("KEY_ISSUED", "GRAND_FRONT_DESK", "15:08", "15:11"),
    seg("IN_ROOM", "DOUGLAS_ROOM", "15:49", "16:04"),
    # 후기의 라이트 스낵·더글라스 아워는 행동 순서의 근거다. 현재 운영창은 미등록이므로 I3를
    # 우회하려는 값이 아니라, venue=None으로 '현재 운영시간 미검증'임을 명시한다.
    seg("IN_LOUNGE", "DOUGLAS_LOUNGE", "16:18", "16:24", machine="M7_Outlet"),
    seg("ENTERED", "GRAND_POOL", "17:20", "18:20", machine="M7_Outlet"),
    seg("HAPPY_HOUR_ACTIVE", "DOUGLAS_LOUNGE", "19:00", "20:00", machine="M7_Outlet"),
    seg("IN_ROOM", "DOUGLAS_ROOM", "20:07", "07:20", end_next_day=True),
    # 후기가 말한 '조식'은 실제 식사 상태로 보존한다. 다만 현재 공식 운영창 표에는
    # DOUGLAS_LOUNGE 조식 창이 없으므로 venue=None으로 두어 I3 검증 범위 밖임을 명시한다.
    seg("SEATED", "DOUGLAS_LOUNGE", "07:34", "07:36", next_day=True, machine="M7_Outlet"),
    seg("DINING", "DOUGLAS_LOUNGE", "07:36", "08:04", next_day=True, machine="M7_Outlet"),
]


# 이번 검증기 수정의 회귀점검. 최종 BLOG02_TIMELINE에는 이 겹침이 없으며 PASS해야 한다.
# 단일 고객이 라운지에 있는 동안 수영장에 입장한 잘못된 변환은 I1뿐 아니라 I4도 내야 한다.
POOL_OVERLAP_PROBE = [
    seg("IN_LOUNGE", "DOUGLAS_LOUNGE", "16:18", "16:24", machine="M7_Outlet"),
    seg("ENTERED", "GRAND_POOL", "16:20", "17:20", machine="M7_Outlet"),
]


def print_fix_log() -> None:
    print("[위반 수정 기록]")
    for number, record in enumerate(FIX_LOG, start=1):
        print(f"{number}.")
        print("  " + "\n  ".join(record))


def assert_pool_overlap_is_detected() -> None:
    report = validate_walkerhill_timeline(POOL_OVERLAP_PROBE, nights=1)
    invariants = {violation.invariant for violation in report.violations}
    if not {"I1", "I4"}.issubset(invariants):
        raise AssertionError(f"수영장 겹침이 I1·I4로 검출되지 않음: {report.render()}")
    print("PASS — 회귀점검: 라운지·수영장 동시 점유를 I1 및 I4로 검출")


def main() -> None:
    print("=" * 72)
    print(f"Blog 02 페르소나: {PERSONA.name} / {PERSONA.party_size}명")
    print(f"근거: {SOURCE_URL}")
    print("- " + "\n- ".join(PERSONA.evidence))
    print("※ 후기의 시간은 과거 기록이며, 검증 기준은 현재 GitHub 모델입니다.\n")

    print_fix_log()
    print("\n[최종 상태 타임라인 검증]")
    print(validate_walkerhill_timeline(BLOG02_TIMELINE, nights=1).render())
    print("\n[검증기 수정 회귀점검]")
    assert_pool_overlap_is_detected()
    print("\n[현재 데이터 커버리지 메모]")
    print("- DOUGLAS_LOUNGE의 현재 조식 운영 창은 검증기 표에 미등록: 조식 시간대의 I3 검증은 보류")
    print("- 과거 후기의 라이트 스낵·더글라스 아워 시간은 검증기 상수로 반영하지 않음")


if __name__ == "__main__":
    main()
