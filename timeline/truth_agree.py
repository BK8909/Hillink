"""
정답 확인 — 사람끼리 얼마나 같게 봤나 (기준 맞추기용)

같은 후기를 여럿이 따로 확인한 파일을 나란히 놓고, 칸마다 누가 넣고 누가 뺐는지 보여 준다.
자동 추출 초안(_auto)도 한 줄로 같이 놓는다 — 사람들이 모두 뺀 걸 자동이 넣었으면 추출기 쪽 문제.

  python3 truth_agree.py 16                 # persona_blog16_*.py 를 전부 찾아 비교
  python3 truth_agree.py 16 kks lsy shh jsg # 사람만 골라서

파일 이름: persona_blog16_<이니셜>.py (kks 경수 · lsy 소연 · shh 한호 · jsg 슬기)
"""

from __future__ import annotations

import glob, importlib, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FACTS = ("property", "is_guest", "nights", "party_size", "has_child_under_13", "club_access",
         "included_meals", "booked", "arrival")


def load(n: int, who: str):
    return importlib.import_module(f"persona_blog{n:02d}_{who}")


def items(m) -> dict[str, set]:
    out = {
        "방문": set(m.TRUTH_VISITED),
        "지나감": set(getattr(m, "TRUTH_PASSED", {})),
        "안 감 ◎": {k for k, v in m.TRUTH_NOT_VISITED.items() if str(v).startswith("◎")},
        "끼니": {f"{a}@{b}" for a, b, *_ in m.TRUTH_MEALS},
        "순서": {f"{a}→{b}" for a, b, *_ in m.TRUTH_ORDER_PAIRS},
        "식당": set(m.TRUTH_RESTAURANTS),
        "목록 밖": set(getattr(m, "TRUTH_UNREACHABLE", {})),
    }
    p = m.PERSONA
    for f in FACTS:
        v = getattr(p, f, None)
        out.setdefault("사실", set()).add(f"{f}={sorted(v) if isinstance(v, (tuple, list)) else v}")
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 1
    n = int(sys.argv[1])
    who = sys.argv[2:] or sorted(
        m.group(1) for f in glob.glob(str(HERE / f"persona_blog{n:02d}_*.py"))
        if (m := re.fullmatch(rf"persona_blog{n:02d}_(\w+)\.py", Path(f).name)) and m.group(1) != "auto")
    if len(who) < 2:
        print(f"사람 파일이 {len(who)}개뿐 — persona_blog{n:02d}_<이니셜>.py 가 둘 이상 필요"); return 1
    people = {w: items(load(n, w)) for w in who}
    try:
        auto = items(load(n, "auto"))
    except ModuleNotFoundError:
        auto = None

    print(f"blog{n:02d} — {len(who)}명 ({' · '.join(who)})" + ("  + 자동 초안" if auto else ""))
    total_all = total_items = 0
    for cat in people[who[0]]:
        union = set().union(*(p[cat] for p in people.values()))
        if auto:
            union |= auto[cat]
        if not union:
            continue
        print(f"\n  [{cat}]")
        for it in sorted(union):
            got = [w for w in who if it in people[w][cat]]
            k = len(got)
            if k in (0, len(who)):
                mark = "모두" if k else "아무도 안 넣음"
            else:
                mark = f"갈림 {k}/{len(who)}  넣음: {' '.join(got)}"
            if 0 < k:
                total_items += 1
                total_all += k == len(who)
            a = ("  · 자동 " + ("넣음" if it in auto[cat] else "뺌")) if auto else ""
            if k != len(who) or (auto and it not in auto[cat]):
                print(f"    {it:38s} {mark}{a}")
        agree = sum(1 for it in union if 0 < sum(it in p[cat] for p in people.values()) == len(who))
        print(f"    — 모두 같게 넣은 것 {agree} (위에 안 나온 건 전원 일치 · 자동도 같음)")
    rate = total_all / total_items if total_items else 1.0
    print(f"\n전원 일치 {total_all}/{total_items} = {rate:.0%}  ← 갈린 줄마다 체크리스트에 규칙 한 줄")
    return 0


if __name__ == "__main__":
    sys.exit(main())
