"""취합 논점 2개 — 각 안으로 가면 어떤 후기 구간이 깨지나 (소연)

  cd timeline && python3 i6_pool_논점_실험.py

논점 1  I6 범위      경수 안(객실 점유만) vs 소연 안(배타 상태 전부)
논점 2  수영장 상태 이름  ENTERED 하나로 vs CHECKED_IN 하나로 vs 둘 다

하는 일: 검증기 전역값을 안별로 바꿔 끼우고 후기 10개 · 회사 시나리오 5개 ·
일부러 틀린 예 2개 · 에이전트를 다시 돌려, 결과가 달라지는 구간만 찍는다.
판단은 하지 않는다 — 문서(docs/논점_I6_수영장상태.md)에 숫자를 넣기 위한 재료.
"""

from __future__ import annotations

import sys
from datetime import datetime

import walkerhill_timeline_validator as V
from walkerhill_timeline_validator import validate_walkerhill_timeline, TimelineSegment
import walkerhill_timeline_scenarios as SC
import blog01, blog02, blog03, blog04, blog05, blog06

# ── 검사 대상 ────────────────────────────────────────────────────────────
CASES: list[tuple[str, list, dict]] = [
    ("blog01 A · 그랜드 2박 · 아는 지점만", blog01.RUN_A, dict(nights=2)),
    ("blog01 B · 그랜드 2박 · 대기 중 이동", blog01.RUN_B, dict(nights=2)),
    ("blog01 C · 그랜드 2박 · 후기 그대로", blog01.RUN_C, dict(nights=2)),
    ("blog02 · 더글라스 1박", blog02.BLOG02_TIMELINE, dict(nights=1)),
    ("blog03 A · 비스타 1박", blog03.STAY_A, dict(nights=1)),
    ("blog03 B · 그랜드 1박", blog03.STAY_B, dict(nights=1)),
    ("blog04 A · 리버파크 비투숙", blog04.VISIT_A, dict(enforce_stay_day=False)),
    ("blog04 B · 클럽스위트 1박", blog04.VISIT_B, dict(nights=1)),
    ("blog05 · 비스타 1박", blog05.build_timeline(), dict(nights=1)),
    ("blog06 · 빛의 시어터 · 피자 포장", blog06.build_timeline(), dict(nights=1)),
]

SCENARIOS: list[tuple[str, list, dict]] = [
    ("회사 draft", SC.draft_timeline(), {}),
    ("회사 corrected", SC.corrected_timeline(), {}),
    ("회사 buffet", SC.buffet_slot_mismatch(), {}),
    ("회사 douglas", SC.douglas_shuttle_omitted(), {}),
    ("회사 double_booked", SC.double_booked(), {}),
]

_key26 = TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK",
                         datetime(2026, 4, 15, 15, 0), datetime(2026, 4, 15, 15, 5))
_hh26 = TimelineSegment("HAPPY_HOUR_ACTIVE", "GRAND_CLUB_LOUNGE",
                        datetime(2026, 4, 15, 18, 0), datetime(2026, 4, 15, 20, 0),
                        machine="M7_Outlet", venue="GRAND_CLUB_LOUNGE")
NEGATIVES: list[tuple[str, list, dict]] = [
    ("일부러 틀린 예 · 2025 해피아워를 2026 에", [_key26, _hh26], {}),
    ("일부러 틀린 예 · 라운지·수영장 동시 점유", blog02.POOL_OVERLAP_PROBE, dict(nights=1)),
]


def agent_cases() -> list[tuple[str, list, dict]]:
    out = []
    import persona_blog01 as P
    for name in ("agent_v0", "agent_v1", "agent_v2"):
        try:
            mod = __import__(name)
        except Exception as exc:                      # v2 가 없는 체크아웃도 있다
            print(f"  (건너뜀 {name}: {exc})")
            continue
        try:
            segs, _ = mod.run_agent(P.PERSONA, datetime(2025, 1, 31, 14, 0), verbose=False)
        except TypeError:
            segs, _ = mod.run_agent(P.PERSONA, datetime(2025, 1, 31, 14, 0))
        out.append((f"{name} · blog01 페르소나", segs, dict(nights=P.PERSONA.nights)))
    return out


def run(cases) -> dict[str, list[str]]:
    """이름 → 위반 한 줄씩. PASS 면 빈 목록."""
    result = {}
    for name, segs, kw in cases:
        r = validate_walkerhill_timeline(segs, **kw)
        result[name] = [f"{v.invariant} {v.code} {v.at:%m-%d %H:%M} {v.detail}"
                        for v in r.violations]
    return result


def diff(base: dict, other: dict, label: str) -> int:
    """base 대비 달라진 것만 찍는다. 반환 = 달라진 건수."""
    changed = 0
    for name in base:
        b, o = base[name], other[name]
        if b == o:
            continue
        changed += 1
        print(f"\n  ▸ {name}")
        for line in o:
            if line not in b:
                print(f"      + {line}")
        for line in b:
            if line not in o:
                print(f"      - {line}")
    if changed == 0:
        print(f"  달라진 것 없음 — {label} 로 가도 이 목록은 그대로다")
    return changed


# ── 논점 1 · I6 범위 ─────────────────────────────────────────────────────
def issue_i6(all_cases) -> None:
    print("=" * 78)
    print("논점 1 · I6(투숙 기간) 범위 — 어떤 상태에 하루 경계를 거나")
    print("=" * 78)
    print("  경수 안(현행) ROOM_OCCUPANCY_STATES:", ", ".join(sorted(V.ROOM_OCCUPANCY_STATES)))
    소연안 = frozenset(V.PHYSICALLY_EXCLUSIVE_STATES | V.ROOM_OCCUPANCY_STATES) - V.BACKGROUND_STATES
    print("  소연 안 배타 상태 전부:", ", ".join(sorted(소연안)))
    print(f"  → 새로 경계가 걸리는 상태 {len(소연안 - V.ROOM_OCCUPANCY_STATES)}개:",
          ", ".join(sorted(소연안 - V.ROOM_OCCUPANCY_STATES)))

    base = run(all_cases)
    원래 = V.ROOM_OCCUPANCY_STATES
    try:
        V.ROOM_OCCUPANCY_STATES = 소연안
        print("\n[소연 안으로 갈 때 새로 깨지는 구간]")
        n = diff(base, run(all_cases), "소연 안")
    finally:
        V.ROOM_OCCUPANCY_STATES = 원래
    print(f"\n  요약 — 소연 안으로 가면 지금 통과하는 타임라인 중 {n}개의 결과가 바뀐다")

    # 소연 안이 막으려던 것이 경수 안에서도 막히는지 (I5 가 대신 잡는가)
    print("\n[소연 안이 막으려던 것 — 체크인 전 클럽라운지 이용]")
    pre = [
        TimelineSegment("IN_LOUNGE", "GRAND_CLUB_LOUNGE",
                        datetime(2026, 4, 15, 13, 0), datetime(2026, 4, 15, 14, 0),
                        machine="M7_Outlet", venue="GRAND_CLUB_LOUNGE"),
        TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK",
                        datetime(2026, 4, 15, 15, 0), datetime(2026, 4, 15, 15, 5)),
    ]
    r = validate_walkerhill_timeline(pre, nights=1)
    print("  경수 안(현행):", [f"{v.invariant}" for v in r.violations] or "PASS  ← 못 잡으면 문제")
    try:
        V.ROOM_OCCUPANCY_STATES = 소연안
        r2 = validate_walkerhill_timeline(pre, nights=1)
        print("  소연 안      :", [f"{v.invariant}" for v in r2.violations] or "PASS")
    finally:
        V.ROOM_OCCUPANCY_STATES = 원래

    # 경수 안의 구멍을 I5 로 메울 수 있나 — IN_LOUNGE 에 키 전제를 걸어 본다
    print("\n[구멍 (가) 를 I5 로 메우면 — IN_LOUNGE 에 키 전제]")
    print("  IN_LOUNGE 를 쓰는 곳:")
    for name, segs, _ in all_cases:
        for s in segs:
            if s.state == "IN_LOUNGE":
                print(f"    {s.location:22s} {s.t_in:%m-%d %H:%M}~{s.t_out:%H:%M}  {name}")
    원래전제 = V.STATE_PRECONDITIONS
    try:
        V.STATE_PRECONDITIONS = dict(원래전제, IN_LOUNGE=frozenset({"KEY_ISSUED", "DIGITAL_KEY_ACTIVATED"}))
        diff(base, run(all_cases), "IN_LOUNGE 키 전제")
    finally:
        V.STATE_PRECONDITIONS = 원래전제
    print("  → 로비 라운지·스카이야드·라이브러리는 비투숙객도 쓴다. 상태 이름으로는 걸 수 없다.")

    print("\n[구멍 (나) — 체류일 밖 식사가 잡히나]")
    late = [
        TimelineSegment("KEY_ISSUED", "VISTA_LOBBY",
                        datetime(2022, 8, 4, 15, 15), datetime(2022, 8, 4, 15, 20)),
        TimelineSegment("IN_ROOM", "VISTA_ROOM",
                        datetime(2022, 8, 4, 15, 30), datetime(2022, 8, 4, 22, 0)),
        TimelineSegment("SEATED", "ONDAL",
                        datetime(2022, 8, 7, 18, 30), datetime(2022, 8, 7, 20, 0),
                        machine="M7_Outlet", venue="ONDAL"),
    ]
    r = validate_walkerhill_timeline(late, nights=1)
    print("  경수 안(현행):", [v.invariant for v in r.violations] or "PASS  ← 안 잡힌다")


# ── 논점 2 · 수영장 상태 이름 ────────────────────────────────────────────
def issue_pool(all_cases) -> None:
    print("\n" + "=" * 78)
    print("논점 2 · 실내수영장 상태 이름 — ENTERED vs CHECKED_IN")
    print("=" * 78)

    print("[지금 두 이름을 쓰는 구간 — 어디서 무엇을 가리키나]")
    for name, segs, _ in all_cases:
        hits = [s for s in segs if s.state in ("ENTERED", "CHECKED_IN")]
        for s in hits:
            print(f"  {s.state:11s} {s.location:22s} {s.t_in:%m-%d %H:%M}~{s.t_out:%H:%M}  {name}")

    base = run(all_cases)
    원래 = V.PHYSICALLY_EXCLUSIVE_STATES
    for 뺄것, label in (("CHECKED_IN", "ENTERED 하나로 통일"), ("ENTERED", "CHECKED_IN 하나로 통일")):
        print(f"\n[{label} — {뺄것} 을 배타 상태에서 뺐을 때 I4 가 못 잡는 것]")
        try:
            V.PHYSICALLY_EXCLUSIVE_STATES = frozenset(원래 - {뺄것})
            diff(base, run(all_cases), label)
        finally:
            V.PHYSICALLY_EXCLUSIVE_STATES = 원래
        print(f"  ※ 위 '달라진 것 없음' 은 검증기가 안전하다는 뜻이 아니다 — 이름만 바꾸고"
              f" 타임라인 쪽 {뺄것} 표기를 그대로 두면 그 구간이 I4 검사에서 통째로 빠진다.")

    print("\n[이름을 바꿀 때 운영 창(I3)이 따라 깨지나 — 상태 한정 창이 있는지]")
    for venue in ("GRAND_POOL", "VISTA_POOL", "RIVERPARK", "WELLNESS_SAUNA", "FITNESS"):
        wins = V.WALKERHILL_VENUE_WINDOWS.get(venue, ())
        scoped = [w for w in wins if w.states]
        print(f"  {venue:15s} 창 {len(wins)}개 · 상태 한정 창 {len(scoped)}개"
              + ("  ← 이름 바꾸면 I3 도 따라 깨진다" if scoped else "  (이름과 무관)"))

    print("\n[퇴장 유예가 걸리는 상태 — 이름을 바꾸면 같이 봐야 하는 곳]")
    print("  EXIT_STATES:", ", ".join(sorted(V.EXIT_STATES)),
          "→ 리버파크·포레스트파크는 EXITED, 스파 계열은 COMPLETED.")
    print("  실내수영장을 ENTERED 로 부르면 퇴장은 EXITED, CHECKED_IN 으로 부르면 COMPLETED 가 짝이다.")


def main() -> None:
    all_cases = CASES + SCENARIOS + NEGATIVES + agent_cases()
    print(f"검사 대상 {len(all_cases)}개 (후기 {len(CASES)} · 회사 {len(SCENARIOS)} "
          f"· 틀린 예 {len(NEGATIVES)} · 에이전트 {len(all_cases) - len(CASES) - len(SCENARIOS) - len(NEGATIVES)})\n")
    baseline = run(all_cases)
    깨진것 = {k: v for k, v in baseline.items() if v and not k.startswith(("회사", "일부러"))}
    print("기준선 — 후기·에이전트 중 지금 위반이 있는 것:", 깨진것 or "없음")
    issue_i6(all_cases)
    issue_pool(all_cases)


if __name__ == "__main__":
    main()
