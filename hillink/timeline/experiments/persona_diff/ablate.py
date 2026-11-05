"""고객 입력 하나씩 빼기 · 근거 없는 칸 빼기 · 결정 이유 분해 · 중복 · 포화 점검 (10/20 · 총괄 C · 격리)

  python3 ablate.py                     # 10팀 × (손 정답본 A · 자동 추출본 B) × (기록 날짜 · 공통 가상 날짜) → out/
  python3 ablate.py --teams blog41 --k 12

같은 손님 · 같은 시작 · 같은 난수(revenue.SEED + i) — 바꾼 칸 말고는 모두 같다. 공용 계수 THETA_FIT 그대로.
결과는 계산 항과 행동 키만 담는다(근거 문장 · 원문 없음).
"""
from __future__ import annotations

import argparse, json, math
from collections import Counter, defaultdict
from datetime import datetime, time
from pathlib import Path

import card, core, term_map

COMMON_DAY = datetime(2026, 8, 28)       # 가상 공통 날짜(금) — 리버파크 골드 시즌 안 · 도착 시:분은 팀마다 그대로
TRAITS = ["대기 회피", "이동 최소화", "격식 선호", "조망 중시", "새로움 추구", "함께 먹기 선호", "조용함 선호"]


def neutral(p, f: str):
    """칸 f 를 '근거 없음'일 때의 값으로. None 이면 이 고객에게는 바꿀 것이 없음(이미 중립)."""
    if f.startswith("trait:"):
        k = f[6:]
        return None if p.traits.get(k) is None else dict(traits={**p.traits, k: None})
    if f == "traits_all":
        return None if all(v is None for v in p.traits.values()) else dict(traits={k: None for k in p.traits})
    table = dict(party_size=2, has_child_under_13=False, arrival=None, included_meals=(), booked=(), club_access=False,
                 room_minimal=False, prefers=(), property="GRAND")
    if f == "nights":
        return dict(nights=1) if p.is_guest and p.nights != 1 else None
    if f == "depart_by":
        return dict(depart_by=time(20, 0)) if not p.is_guest and p.depart_by != time(20, 0) else None
    if f in table:
        return None if getattr(p, f) == table[f] else {f: table[f]}
    raise KeyError(f)


FIELDS = ["property", "nights", "depart_by", "party_size", "has_child_under_13", "club_access", "included_meals", "booked",
          "arrival", "room_minimal"] + [f"trait:{t}" for t in TRAITS] + ["traits_all"]
CARD_ONLY_SET = dict(purpose="커플·기념일", ai_type="FOHE", age_band="30~49세", sex="여성", package="시험 상품", note="시험")   # 시험값 — 결과가 같아야 함


def start_neutral(start: datetime, is_guest: bool) -> datetime:
    return start.replace(hour=14, minute=30) if is_guest else start


def ablations(p, start, k):
    base = core.run(p, start, k)
    out = {}
    for f in FIELDS:
        kw = neutral(p, f)
        if kw is None:
            out[f] = dict(applicable=False); continue
        out[f] = dict(applicable=True, **core.compare(base, core.run(core.with_fields(p, **kw), start, k)))
    s2 = start_neutral(start, p.is_guest)
    out["start_time"] = dict(applicable=s2 != start, **(core.compare(base, core.run(p, s2, k)) if s2 != start else {}))
    out["card_only"] = dict(applicable=True, **core.compare(base, core.run(core.with_fields(p, **CARD_ONLY_SET), start, k)))
    return base, out


def evidence_gated(blog, auto, p, start, k, base):
    """근거 등급으로 칸 빼기 — G1 △ · 등급 없음 칸을 중립으로 / G2 G1 + 성향 전부(AI 값) / G3 ◎ 만 남김."""
    c = card.build(blog, auto)
    res = {}
    for name, drop in [("G1_drop_assumed", {"△", None}), ("G2_G1_plus_ai_traits", {"△", None}), ("G3_observed_only", {"△", "○", None})]:
        kw, dropped = {}, []
        for f, x in c["fields"].items():
            if f in ("start_at", "is_guest") or x["grade"] not in drop:
                continue
            n = neutral(p, f) if f in FIELDS else None
            if n:
                kw.update(n); dropped.append(f)
        st = start
        if c["fields"]["start_at"].get("time_grade") in drop and p.is_guest:
            st = start_neutral(start, True)
            if st != start:
                dropped.append("start_time")
        if name == "G2_G1_plus_ai_traits":
            n = neutral(p, "traits_all")
            if n:
                kw.update(n); dropped.append("traits_all")
        other = core.run(core.with_fields(p, **kw), st, k) if (kw or st != start) else base
        res[name] = dict(dropped=dropped, **core.compare(base, other))
    return res


def decisive(runs) -> dict:
    """고른 행동 vs 가장 높은 다른 후보 — 점수 차를 입력 칸별로 나누고, 그 칸의 차를 빼면 순위가 뒤집히는 칸을 '결정적'으로 센다."""
    dec, n, stochastic = Counter(), 0, 0
    for r in runs:
        for d in r:
            others = [a for a in d["alts"] if a["key"] != d["key"]]
            if not others:
                continue
            a = max(others, key=lambda x: x["pts"])
            margin = d["pts"] - a["pts"]
            n += 1
            if margin <= 0:
                stochastic += 1                       # tau 0.5 확률 선택으로 1등이 아닌 것을 고름
                continue
            byf = defaultdict(float)
            for lab, v in d["terms"]:
                if v is not None:
                    byf[term_map.classify(lab)[0]] += v
            for lab, v in a["terms"]:
                if v is not None:
                    byf[term_map.classify(lab)[0]] -= v
            for f, dv in byf.items():
                if dv > 0 and margin - dv <= 0:
                    dec[f] += 1
    return dict(decisions=n, chosen_not_top=stochastic, decisive_field=dict(dec.most_common()))


def overlap(runs, p) -> dict:
    """같은 결정에 큰 가점이 겹치는지 · 포화(거의 확정 선택) · 줄 없는데 '줄 대신 포장' 가점."""
    stack, sat, n, takeout_nowait, takeout_total = Counter(), Counter(), 0, 0, 0
    tau = core.agent_v4.THETA_FIT["tau"]
    for r in runs:
        for d in r:
            n += 1
            fs = sorted({term_map.classify(l)[0] for l, v in d["terms"] if v is not None and abs(v) >= 3})
            if len(fs) >= 2:
                stack[" + ".join(fs)] += 1
            ws = [math.exp((a["pts"] - max(x["pts"] for x in d["alts"])) / tau) for a in d["alts"]] if d["alts"] else []
            pc = next((math.exp((a["pts"] - max(x["pts"] for x in d["alts"])) / tau) for a in d["alts"] if a["key"] == d["key"]), None)
            if pc is not None and ws and pc / sum(ws) >= 0.95 and d["key"] not in core.agent_v4.CHECKIN_KEYS and d["key"] not in ("sleep", "room"):
                big = max(((term_map.classify(l)[0], v) for l, v in d["terms"] if v is not None), key=lambda x: x[1], default=(None, 0))
                sat[big[0]] += 1
            for c in [dict(terms=d["terms"], wait=d["wait"])] + d["alts"]:
                if any(l == "줄 대신 포장" for l, v in c["terms"]):
                    takeout_total += 1
                    takeout_nowait += (c.get("wait") or 0) == 0
    return dict(decisions=n, big_term_stacks=dict(stack.most_common(8)), saturated_by=dict(sat.most_common(6)),
                takeout_trait_bonus=dict(total_candidates=takeout_total, with_zero_wait=takeout_nowait))


def ab_compare(blog, k, start_mode):
    pa, sa = core.load_persona(blog)
    pb, sb = core.load_persona(blog, auto=True)
    if start_mode == "common":
        sa, sb = core.at_common_date(sa, COMMON_DAY), core.at_common_date(sb, COMMON_DAY)
    ca, cb = card.build(blog), card.build(blog, True)
    diff = {f: [ca["fields"][f]["value"], cb["fields"][f]["value"]] for f in ca["fields"] if ca["fields"][f]["value"] != cb["fields"][f]["value"]}
    tdiff = {t: [ca["traits"][t]["value"], cb["traits"][t]["value"]] for t in ca["traits"] if ca["traits"][t]["value"] != cb["traits"][t]["value"]}
    return dict(field_diff=diff, trait_diff=tdiff, behavior=core.compare(core.run(pa, sa, k), core.run(pb, sb, k)))


def team(blog, k, start_mode):
    p, start = core.load_persona(blog)
    if start_mode == "common":
        start = core.at_common_date(start, COMMON_DAY)
    base, abl = ablations(p, start, k)
    return dict(blog=blog, start=start.isoformat(), place_p=core.place_p(base), ablation=abl,
                evidence_gated=evidence_gated(blog, False, p, start, k, base), decisive=decisive(base), overlap=overlap(base, p),
                ab_track=ab_compare(blog, k, start_mode))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", nargs="*", default=core.TEAMS)
    ap.add_argument("--k", type=int, default=core.K)
    ap.add_argument("--out", default=str(core.HERE / "out"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {mode: {b: team(b, a.k, mode) for b in a.teams} for mode in ("recorded", "common")}
    meta = dict(theta=core.agent_v4.THETA_FIT, k=a.k, seed_base=core.SEED_BASE, common_day=COMMON_DAY.date().isoformat(),
                note="시험값 아님 — 실제 고객 파일 · 공용 계수 그대로. card_only 줄의 값만 시험값(결과가 같아야 함)")
    (out / "ablation.json").write_text(json.dumps(dict(meta=meta, results=res), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({m: {b: {f: (x.get("identical"), x.get("max_abs_delta")) for f, x in r["ablation"].items() if x.get("applicable")}
                          for b, r in rs.items()} for m, rs in res.items()}, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
