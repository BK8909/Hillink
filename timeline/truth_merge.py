"""
공통 후기 — 넷이 따로 확인한 파일을 다수결로 합쳐 persona_blogNN.py 를 만든다

  python3 truth_merge.py 25                 # persona_blog25_<이니셜>.py 전부 → persona_blog25.py
  python3 truth_merge.py 25 kks lsy shh jsg

- 칸(방문 · 지나감 · 안 감 ◎ · 끼니 · 순서 · 식당 · 목록 밖 · 사실)마다 항목별로 과반이면 넣는다
- 동률(2:2)은 넣지 않고 docstring 에 '보류(동률)' 로 남긴다 — 규칙으로 정한 뒤 손으로 고친다
- 근거 문장과 성향 · 이름은 첫 번째 사람(기본 kks)의 파일을 그대로 쓴다 (성향은 원래 넷이 같다)
- 개인 후기와 같은 이름(persona_blogNN.py)이 돼야 run_all · persona_compare 가 읽는다
"""

from __future__ import annotations

import glob, importlib, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FACTS = ("property", "is_guest", "nights", "party_size", "has_child_under_13", "club_access",
         "included_meals", "booked", "arrival")


def load(n, who):
    return importlib.import_module(f"persona_blog{n:02d}_{who}")


def vote(mods, get):
    c = Counter()
    for m in mods:
        for it in get(m):
            c[it] += 1
    half = len(mods) / 2
    keep = {it for it, k in c.items() if k > half}
    ties = {it for it, k in c.items() if k == half}
    return keep, ties


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 1
    n = int(sys.argv[1])
    who = sys.argv[2:] or sorted(
        m.group(1) for f in glob.glob(str(HERE / f"persona_blog{n:02d}_*.py"))
        if (m := re.fullmatch(rf"persona_blog{n:02d}_(\w+)\.py", Path(f).name)) and m.group(1) != "auto")
    if "kks" in who:
        who = ["kks"] + [w for w in who if w != "kks"]
    mods = [load(n, w) for w in who]
    base = mods[0]
    src = Path(HERE / f"persona_blog{n:02d}_{who[0]}.py").read_text(encoding="utf-8")

    holds = []

    def pick_dict(attr, evid_default="○ (다수결 — 근거는 첫 파일에 없음)"):
        keep, ties = vote(mods, lambda m: set(getattr(m, attr, {})))
        holds.extend(f"{attr} 의 {t}" for t in sorted(ties))
        out = {}
        for k in sorted(keep):
            ev = next((getattr(m, attr, {})[k] for m in mods if k in getattr(m, attr, {})), evid_default)
            out[k] = ev
        return out

    visited = pick_dict("TRUTH_VISITED")
    passed = pick_dict("TRUTH_PASSED")
    unreach = pick_dict("TRUTH_UNREACHABLE")
    # 안 감: ◎ 는 다수결, 나머지는 어느 파일에든 있고 방문 · 지나감에 없는 코드를 ○ 로
    keep_no, ties_no = vote(mods, lambda m: {k for k, v in m.TRUTH_NOT_VISITED.items() if str(v).startswith("◎")})
    holds.extend(f"TRUTH_NOT_VISITED ◎ 의 {t}" for t in sorted(ties_no))
    not_visited = {}
    for m in mods:
        for k, v in m.TRUTH_NOT_VISITED.items():
            if k in visited or k in passed:
                continue
            if k in keep_no:
                not_visited[k] = next(vv for mm in mods for kk, vv in mm.TRUTH_NOT_VISITED.items() if kk == k and str(vv).startswith("◎"))
            elif k not in not_visited:
                not_visited[k] = v if not str(v).startswith("◎") else "○ 언급 없음"
    keep_m, ties_m = vote(mods, lambda m: {(a, b) for a, b, *_ in m.TRUTH_MEALS})
    holds.extend(f"TRUTH_MEALS 의 {a}@{b}" for a, b in sorted(ties_m))
    meals = [next(tuple(x) for m in mods for x in m.TRUTH_MEALS if (x[0], x[1]) == ab) for ab in sorted(keep_m)]
    keep_o, ties_o = vote(mods, lambda m: {(a, b) for a, b, *_ in m.TRUTH_ORDER_PAIRS})
    holds.extend(f"TRUTH_ORDER_PAIRS 의 {a}→{b}" for a, b in sorted(ties_o))
    pairs = [next(tuple(x) for m in mods for x in m.TRUTH_ORDER_PAIRS if (x[0], x[1]) == ab) for ab in sorted(keep_o)]
    keep_r, _ = vote(mods, lambda m: set(m.TRUTH_RESTAURANTS))

    # 사실 — 값마다 다수결. 동률이면 첫 파일 값 + 보류
    fact_over = {}
    for f in FACTS:
        c = Counter(repr(getattr(m.PERSONA, f, None)) for m in mods)
        v, k = c.most_common(1)[0]
        if k <= len(mods) / 2 and len(c) > 1:
            holds.append(f"facts.{f} — 동률 {dict(c)}")
        elif v != repr(getattr(base.PERSONA, f, None)):
            fact_over[f] = v
    # START_AT — 첫 파일 값. 다르면 보류
    starts = Counter(m.START_AT for m in mods)
    if len(starts) > 1:
        holds.append("START_AT — " + " · ".join(f"{w} {m.START_AT:%m-%d %H:%M}" for w, m in zip(who, mods)))

    def d(x):
        import json
        return json.dumps(x, ensure_ascii=False, indent=4)

    def sub(name, value):
        nonlocal src
        pat = re.compile(rf"^{name}: [^=]+= .*?(?=^[A-Za-z_#]|\Z)", re.S | re.M)
        assert pat.search(src), name
        src = pat.sub(f"{name}: {TYPES[name]} = {value}\n", src, count=1)

    TYPES = {"TRUTH_VISITED": "dict[str, str]", "TRUTH_PASSED": "dict[str, str]",
             "TRUTH_NOT_VISITED": "dict[str, str]", "TRUTH_UNREACHABLE": "dict[str, str]",
             "TRUTH_RESTAURANTS": "frozenset[str]", "TRUTH_ORDER_PAIRS": "list[tuple[str, str, str]]",
             "TRUTH_MEALS": "list[tuple[str, str, str]]"}
    sub("TRUTH_VISITED", d(visited)); sub("TRUTH_PASSED", d(passed)); sub("TRUTH_NOT_VISITED", d(not_visited))
    sub("TRUTH_UNREACHABLE", d(unreach)); sub("TRUTH_RESTAURANTS", f"frozenset({sorted(keep_r)!r})")
    sub("TRUTH_ORDER_PAIRS", repr(pairs)); sub("TRUTH_MEALS", repr(meals))
    for f, v in fact_over.items():
        src, k = re.subn(rf"^(\s+{f}=).*?,(\s*(#.*)?)$", rf"\g<1>{v},\2", src, count=1, flags=re.M)
        assert k == 1, f

    head = [f"정답 합침: blog{n:02d} — {len(who)}명 다수결 ({' · '.join(who)}) · truth_merge.py"]
    if holds:
        head.append("보류(동률 · 규칙으로 정한 뒤 손으로): " + " / ".join(holds))
    src = re.sub(r'^"""\n', '"""\n' + "\n".join(head) + "\n\n", src, count=1)
    out = HERE / f"persona_blog{n:02d}.py"
    out.write_text(src, encoding="utf-8")
    importlib.invalidate_caches(); importlib.import_module(out.stem)
    print(f"→ {out.name}  방문 {len(visited)} · 지나감 {len(passed)} · 안 감 ◎ {len(keep_no)} · 끼니 {len(meals)} · 순서 {len(pairs)}")
    for h in holds:
        print("  보류:", h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
