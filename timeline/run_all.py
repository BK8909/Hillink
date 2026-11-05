"""
후기마다 페르소나가 있으면 에이전트를 돌려 일치율을 한 표로.

  python3 run_all.py            # v2 (기본 — 봉인 시험 두 번 모두 제일 나음, docs/v4_교차검증_시험.md)
  python3 run_all.py v3         # v3 · v4 (실험)
  python3 run_all.py v1         # v1 (그랜드 투숙만 됨 — 비교용)

persona_blog0N.py 가 있는 후기만 돈다. 없는 후기는 '페르소나 없음' 으로 표시.
한 후기에 체류가 둘이면 (`PERSONA_ALT` 등 `*_ALT` — blog03 · blog04) 둘 다 돈다.
각 페르소나 파일은 PERSONA · TRUTH_VISITED · TRUTH_ORDER_PAIRS · TRUTH_RESTAURANTS · TRUTH_MEALS ·
TRUTH_NOT_VISITED · TRUTH_PASSED · TRUTH_UNREACHABLE · START_AT(선택) 를 둔다 — persona_blog01.py 참조.
"""

from __future__ import annotations

import importlib, sys
from datetime import datetime

from match import evaluate, print_report
from walkerhill_timeline_validator import validate_walkerhill_timeline

args = [a for a in sys.argv[1:] if not a.startswith("-")]
which = args[0] if args else "v2"
agent = importlib.import_module(f"agent_{which}")
verbose = "-v" in sys.argv

TRUTH_FIELDS = ("PERSONA", "START_AT", "TRUTH_VISITED", "TRUTH_PASSED", "TRUTH_NOT_VISITED",
                "TRUTH_UNREACHABLE", "TRUTH_RESTAURANTS", "TRUTH_ORDER_PAIRS", "TRUTH_MEALS")


class _Alt:
    """한 후기에 체류가 둘인 파일(blog03 · blog04 — 소연)의 `*_ALT` 를 본체처럼 읽는다."""
    def __init__(self, mod):
        for f in TRUTH_FIELDS:
            if hasattr(mod, f + "_ALT"):
                setattr(self, f, getattr(mod, f + "_ALT"))


def run_one(P, label):
    start = getattr(P, "START_AT", datetime(2025, 1, 31, 14, 0))
    segs, _ = agent.run_agent(P.PERSONA, start, verbose=verbose)
    rep = validate_walkerhill_timeline(segs, enforce_stay_day=P.PERSONA.is_guest, nights=P.PERSONA.nights)
    reach = agent.reachable(P.PERSONA) if hasattr(agent, "reachable") else None
    r = evaluate(segs, P, title=f"{label} · {which}", reachable=reach)
    r.title = f"{label} {P.PERSONA.name[:18]}"
    if verbose:
        print_report(r)
    return (rep, r)


# 시험용(held-out) — 에이전트를 한 번도 이 후기에 맞춰 고치지 않은 것. docs/시험용_후기_봉인.txt 에 해시
HELD_OUT: set[int] = set()   # 07–10 · 11–15 는 각각 한 번 채점 뒤 개발용 (docs/시험용_후기_봉인.txt · _2.txt). 다음 시험용은 새로 봉인
import glob, re
from sealed import SEALED_WAIT, unusable   # 2차 시험용 — 봉인 전 · 채점 전에는 아예 돌리지 않는다
NUMS = sorted(({int(m.group(1)) for f in glob.glob("persona_blog*.py")
               if (m := re.fullmatch(r"persona_blog(\d\d)\.py", f.split("/")[-1]))} | set(range(1, 7))) - SEALED_WAIT)

rows = []
for n in NUMS:
    name = f"persona_blog{n:02d}"
    try:
        P = importlib.import_module(name)
    except ModuleNotFoundError:
        rows.append((f"blog{n:02d}", None)); continue
    if unusable(P):
        print(f"blog{n:02d} — 못 씀 (정답 확인에서 표시) · 건너뜀"); continue
    rows.append((f"blog{n:02d}", run_one(P, f"blog{n:02d}")))
    if hasattr(P, "PERSONA_ALT"):
        rows.append((f"blog{n:02d}", run_one(_Alt(P), f"blog{n:02d}")))

print(f"\n=== 에이전트 {which} · 후기별 일치율 ===")
print(f"{'후기':26s} {'정합성':6s} {'집합 재현/정밀':16s} {'식당':6s} {'순서':6s} {'끼니':6s} {'금지':4s} {'빈칸'}")
for key, val in rows:
    if val is None:
        print(f"{key:26s} —      페르소나 없음 (persona_{key}.py)"); continue
    rep, r = val
    o = "—" if r.order_rate is None else f"{r.order_rate:.0%}"
    print(f"{r.title:26s} {'PASS' if rep.ok else 'FAIL':6s} {r.recall:>5.0%} / {r.precision:<6.0%}  "
          f"{r.restaurants_label:6s} {o:6s} {r.meal_label:>4s}   {len(r.forbidden_hit):<4d} {len(r.unreachable)}")
def _avg(sel):
    vals = [v[1] for k, v in rows if v is not None and sel(int(k[4:6]))]
    if not vals:
        return None
    return (sum(r.recall for r in vals) / len(vals), sum(r.precision for r in vals) / len(vals), len(vals))

for label, sel in (("개발용 (고치면서 본 후기)", lambda n: n not in HELD_OUT), ("시험용 (봉인 · 처음 보는 후기)", lambda n: n in HELD_OUT)):
    a = _avg(sel)
    if a:
        print(f"  평균 · {label:24s} 재현 {a[0]:.0%} / 정밀 {a[1]:.0%}  (체류 {a[2]})")
print("\n끼니 — = 정답 끼니가 없어 판단 유보 · 식당 '부분·' = 후기가 식당을 다 적었는지 모름 (확인된 식당을 갔나만 봄)")
print("숫자 읽는 법: 재현 = 후기가 간 곳 중 에이전트도 간 비율 · 정밀 = 에이전트가 간 곳 중 후기도 간 비율.")
print("v1 은 blog01 로 고쳐서 blog01 이 높다. 다른 후기가 진짜 점수.")
