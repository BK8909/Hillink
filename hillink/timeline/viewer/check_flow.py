"""고객 이동 정산 검증 (10/14 · 리뷰 피드백) — 공급 제한으로 끼니 후보가 빠진 손님이 결국 어디서 먹었는지 끝까지 정산되는지 확인한다.

engine.switch_summary 와 따로, 손님 상세 기록(cache/<키>.guests.jsonl)만 읽어 다시 센다.
  1) 시도(턴)와 고유 끼니(팀 · 날짜 · 끼니)를 나눠 센다
  2) 고유 끼니마다 최종 상태가 정확히 하나인지 (중복 · 누락 없음)
  3) 최종 상태 합 = 고유 끼니 수, 하루 결과(day JSON)의 meal_cases · meal_outcome · 전환 건 · 팀과 같은지
  4) 빠진 업장 → 최종 업장 흐름표 (예: 더뷔페 석식에서 막힌 팀이 어디서 먹었나) 를 cache/flow_<키>.json 으로 남긴다

  python3 check_flow.py --key 2026-10-10_none_s100_k...
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from http_boundary import cache_family

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import agent_v4  # noqa: E402

CACHE = HERE / "cache"
SKIP_ORIG = {"lux", "lounge_h"}           # 바 · 라운지 한잔은 끼니로 보지 않는다 (engine 과 같은 정의)
TAKEOUT = {"pizza_to", "lepassage"}
LOUNGE = {"lounge_b", "lounge_h"}


def venue_word(label):
    return str(label or "").split()[0] if label else ""


def final_state(orig_label, step):
    if step is None:
        return "같은 끼니 식사 기록 없음", None
    k = step["key"]
    if k in TAKEOUT:
        return "포장", step["label"]
    if k == "meal_other":
        return "호텔 밖 · 객실 식사", "호텔 밖 · 객실"
    if k == "meal_out":                 # 10/16 실험 조정값 meal_split — 비투숙 손님이 호텔 밖에서 먹고 방문을 끝냄
        return "호텔 밖 식사 (방문 종료)", "호텔 밖 (방문 종료)"
    if k in LOUNGE:
        return "클럽 라운지 (포함)", step["label"]
    if venue_word(step["label"]) == venue_word(orig_label):
        return "같은 업장 다른 회차", step["label"]
    return "다른 호텔 식당", step["label"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    a = ap.parse_args()
    cache_family(CACHE,a.key)
    D = json.loads((CACHE / f"{a.key}.json").read_text(encoding="utf-8"))
    mk = agent_v4.meal_kind_at
    attempts = 0
    cases = {}                      # (팀, 날짜, 끼니) → (원래, 최종 상태, 최종 업장)
    dup = 0
    sw_events, sw_teams = 0, set()
    flow = defaultdict(Counter)     # 원래 → 최종 업장
    events = []                     # 화면 내려가기용 — 전환 한 건마다 (손님 번호 · 빠진 곳 · 대신 고른 곳 · 끼니면 최종 상태)
    with open(CACHE / f"{a.key}.guests.jsonl", encoding="utf-8") as fd:
        for idx, line in enumerate(fd):
            g = json.loads(line)
            gid, steps = g.get("id"), g["steps"]
            meals = [s for s in steps if s["key"] in agent_v4.MEAL_KEYS]
            for s in steps:
                sw = s.get("switch") or {}
                if not sw.get("원래"):
                    continue
                sw_events += 1; sw_teams.add(gid)
                ev = {"idx": idx, "id": gid, "from": sw["원래"], "to": sw.get("대체"), "why": sw.get("사유"), "t": sw.get("시각") or s["t_in"],
                      "s_from": sw.get("원래_점수"), "s_to": sw.get("대체_점수")}
                events.append(ev)
                if sw.get("원래_키") not in agent_v4.MEAL_KEYS or sw.get("원래_키") in SKIP_ORIG:
                    continue
                t = datetime.fromisoformat(sw.get("시각") or s["t_in"]); kind = mk(t)
                if not kind:
                    continue
                attempts += 1
                ev["meal"] = kind
                ev["included"] = any(x and x[0] == kind for x in (g.get("persona") or {}).get("included") or [])   # 그 끼니가 객실 상품에 포함된 팀인가
                ck = (gid, t.date().isoformat(), kind)
                if ck in cases:
                    ev["final"] = cases[ck][1]; ev["final_at"] = cases[ck][2]; ev["repeat"] = True
                    continue
                fin = next((m for m in meals if m["i"] >= s["i"] and datetime.fromisoformat(m["t_in"]).date() == t.date()
                            and mk(datetime.fromisoformat(m["t_in"])) == kind), None)
                st, where = final_state(sw["원래"], fin)
                if ck in cases:
                    dup += 1
                cases[ck] = (sw["원래"], st, where)
                ev["final"], ev["final_at"] = st, where
                flow[sw["원래"]][where or st] += 1
    outcome = Counter(st for _, st, _ in cases.values())
    S = D.get("switch") or {}
    checks = [
        ("고유 끼니마다 최종 상태 하나 (중복 없음)", dup == 0, f"중복 {dup}"),
        ("최종 상태 합 = 고유 끼니 수", sum(outcome.values()) == len(cases), f"{sum(outcome.values())} = {len(cases)}"),
        ("고유 끼니 수 = 하루 결과 meal_cases", len(cases) == S.get("meal_cases"), f"{len(cases)} vs {S.get('meal_cases')}"),
        ("최종 상태별 수 = 하루 결과 meal_outcome", dict(outcome) == (S.get("meal_outcome") or {}), f"{dict(outcome)} vs {S.get('meal_outcome')}"),
        ("전환 건 = 하루 결과 events", sw_events == S.get("events"), f"{sw_events} vs {S.get('events')}"),
        ("전환 팀 = 하루 결과 teams", len(sw_teams) == S.get("teams"), f"{len(sw_teams)} vs {S.get('teams')}"),
    ]
    # 10/16 좌석 동시 점유 — 모든 예약 시작 시각에서 동시 착석 ≤ 좌석 수 (cache/<키>.cap.pkl)
    capf = CACHE / f"{a.key}.cap.pkl"
    if capf.exists():
        import pickle
        cap = pickle.load(capf.open("rb"))
        over = cap.over_cap() if hasattr(cap, "over_cap") else []
        if not hasattr(cap, "over_cap"):            # 예전 Capacity 로 저장된 파일
            for v, bk in cap.booked.items():
                for t in sorted(set(x[0] for x in bk)):
                    load = sum(n for s0, s1, n in bk if s0 <= t < s1)
                    if load > cap.cap[v]:
                        over.append((v, cap.cap[v], load, t))
        worst = {}
        for v, c, load, t in over:
            if load - c > worst.get(v, (0, 0, None))[0]:
                worst[v] = (load - c, load, t)
        checks.append(("좌석 동시 점유 ≤ 좌석 수 (모든 예약 시작 시각)", not over,
                       "초과 없음" if not over else " · ".join(f"{v} {w[1]}명 / {cap.cap[v]}석 ({w[2]:%m-%d %H:%M})" for v, w in worst.items())))
    ok = all(c[1] for c in checks)
    for name, good, note in checks:
        print(("통과 " if good else "실패 ") + name + " · " + note)
    print(f"끼니 시도(턴) {attempts}건 · 고유 끼니 {len(cases)}건")
    out = {"key": a.key, "model_ver": D.get("model_ver"), "input_ver": D.get("input_ver"), "ok": ok,
           "checks": [{"name": n, "ok": g, "note": t} for n, g, t in checks],
           "attempts": attempts, "cases": len(cases), "outcome": dict(outcome.most_common()),
           "flow": {o: dict(c.most_common()) for o, c in sorted(flow.items(), key=lambda kv: -sum(kv[1].values()))},
           "events": events}
    (CACHE / f"flow_{a.key}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
