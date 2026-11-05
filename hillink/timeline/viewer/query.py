"""운영 어시스턴트 2차 · 조건으로 묻기 (10/16) — 이미 계산한 하루 결과를 날짜 · 업장 · 회차 · 고객군으로 다시 센다.

새 계산이나 언어 모델을 쓰지 않는다. 하루 계산 캐시(<key>.json · <key>.guests.jsonl)만 읽고, 업장 · 회차 집계는 engine.day 와 같은 규칙으로 센다
(행동 단계의 장소가 그 업장이고 체크인이 아닌 단계 · 시작 시각이 회차 창 안 · 포장 주문은 따로 · 인원 = 팀 인원).
그래서 고객군을 '전체'로 두면 화면의 회차별 인원과 같아야 하고, 그 확인 결과(check)를 답에 함께 돌려준다.
그 날 운영 기준(연박 손님 포함)은 실험 결과(static/stay_day.json)가 같은 버전으로 있을 때만 업장 단위로 덧붙인다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from http_boundary import cache_family

HERE = Path(__file__).resolve().parent
STAY_FILE = HERE / "static" / "stay_day.json"      # 연박 집계 묶음 (시험에서 가상 파일로 바꿔 끼울 수 있게 모듈 변수로)
STAY_VENUES = ("THE_BUFFET", "PIZZA_HILL", "MYONGWOLGWAN", "GEUMRYONG", "ONDAL", "MOEGI", "LUX_BAR", "LE_PASSAGE")   # stay_day.py 가 세는 업장
LABEL2LOC = {"더뷔페 조식": "THE_BUFFET", "더뷔페 중식": "THE_BUFFET", "더뷔페 석식": "THE_BUFFET", "피자힐": "PIZZA_HILL", "피자힐 포장": "PIZZA_HILL",
             "금룡": "GEUMRYONG", "명월관": "MYONGWOLGWAN", "모에기": "MOEGI", "온달": "ONDAL", "더 파빌리온": "THE_PAVILION", "LUX BAR": "LUX_BAR", "르파사쥬 포장": "LE_PASSAGE"}
GROUPS = {
    "all": ("전체", lambda p: True),
    "guest": ("투숙", lambda p: p["is_guest"]),
    "day": ("비투숙", lambda p: not p["is_guest"]),
    "kids": ("아동 동반", lambda p: bool(p["kids"])),
    "n1": ("투숙 1박", lambda p: p["is_guest"] and p.get("nights") == 1),
    "n2": ("투숙 2박", lambda p: p["is_guest"] and (p.get("nights") or 0) >= 2),
}


def group_of(gid: str):
    """고객군 하나 또는 여러 조건의 교집합 ('kids,n2,p:가족·친족' — 모두 만족하는 손님만, 손님은 한 번만 센다)"""
    parts = [g for g in str(gid).split(",") if g and g != "all"] if "," in str(gid) else None
    if parts is not None:
        if not parts:
            return GROUPS["all"]
        fs = [group_of(g) for g in parts]
        return (" · ".join(l for l, _ in fs), lambda p, fs=fs: all(f(p) for _, f in fs))
    if gid in GROUPS:
        return GROUPS[gid]
    if gid.startswith("p:"):
        v = gid[2:]
        return (f"목적 {v}", lambda p: p.get("purpose") == v)
    if gid.startswith("a:"):
        v = gid[2:]
        return (f"연령 {v}", lambda p: p.get("age") == v)
    raise ValueError(f"모르는 고객군: {gid}")


def _win_times(D, w):
    y = D["date"][:4]
    t0 = datetime.strptime(f"{y}/{w['t0']}", "%Y/%m/%d %H:%M")
    hh, mm = map(int, w["t1"].split(":"))
    return t0, t0.replace(hour=hh, minute=mm)


def options(cache: Path, key: str):
    """고를 수 있는 업장 · 회차 · 고객군 (그 날 결과에 실제로 있는 값만)"""
    cache_family(cache,key)
    D = json.loads((cache / f"{key}.json").read_text(encoding="utf-8"))
    ven = {loc: dict(name=v["name"], cap=v["cap"], windows=[w["name"] for w in v["windows"]]) for loc, v in D["venue_detail"].items() if v.get("cap")}
    purposes, ages = set(), set()
    for g in D.get("guests", []):
        purposes.add(g.get("purpose") or "미설정"); ages.add(g.get("age") or "미설정")
    groups = [dict(id=k, label=v[0]) for k, v in GROUPS.items()] + [dict(id="p:" + x, label="목적 " + x) for x in sorted(purposes)] + \
             [dict(id="a:" + x, label="연령 " + x) for x in sorted(ages)]
    return dict(key=key, date=D["date"], venues=ven, groups=groups)


def query(cache: Path, key: str, venue: str, window: str = "*", gid: str = "all"):
    cache_family(cache,key)
    D = json.loads((cache / f"{key}.json").read_text(encoding="utf-8"))
    vd = D["venue_detail"]
    if venue not in vd:
        raise ValueError(f"이 날 결과에 없는 업장: {venue}")
    V = vd[venue]
    wins = [w for w in V["windows"] if (w["name"] == window if window not in ("*", "", None) else "익일" not in w["name"])]
    label, keep = group_of(gid)
    if not wins:
        if window not in ("*", "", None):
            raise ValueError(f"이 업장에 없는 회차: {window}")
        # 10/16 QA · 휴업 등으로 이 날 운영 회차가 없고 다음 날 회차만 있는 업장 — 오류가 아니라 '이 날 운영 회차 없음' 으로 답한다
        return dict(key=key, date=D["date"], scenario=D["scenario"], knobs=D.get("knobs", ""), model_ver=D.get("model_ver"), input_ver=D.get("input_ver"),
                    venue=venue, venue_name=V["name"], cap=V["cap"], window="*", group=gid, group_label=label, rows=[], check_ok=True,
                    status="no_window", status_note="이 날 운영 회차가 없습니다 (휴업이거나 다음 날 회차만 있음). 다음 날 회차는 회차 목록에서 따로 고를 수 있습니다.",
                    basis="체크인 고객 기준", operating=None, operating_note=None)
    span = [(w["name"],) + _win_times(D, w) for w in wins]
    res = {w["name"]: dict(persons=0, teams=set(), takeout=0, over_persons=0, over_teams=set(), krw=0.0, persons_all=0, qty=0, buy_teams=set()) for w in wins}

    def win_at(t):
        for n, a, b in span:
            if a <= t < b:
                return n
        return None
    with (cache / f"{key}.guests.jsonl").open(encoding="utf-8") as fd:
        for line in fd:
            det = json.loads(line)
            pp = det["persona"]
            inside = keep(pp)
            seen_over = False
            for s in det["steps"]:
                loc = s.get("venue") if s.get("venue") in vd else (s.get("location") if s.get("location") in vd else None)
                if loc == venue and s["kind"] != "checkin":
                    n = win_at(datetime.fromisoformat(s["t_in"]))
                    if n:
                        r = res[n]
                        if s.get("state") != "TAKEOUT_ORDER":
                            r["persons_all"] += pp["party"]
                        if inside:
                            if s.get("state") == "TAKEOUT_ORDER":
                                r["takeout"] += pp["party"]
                            else:
                                r["persons"] += pp["party"]; r["teams"].add(det["id"])
                            r["krw"] += sum(sp["krw"] for sp in s["spend"] if sp["l3"] == V["name"])
                            q = sum(sp.get("qty", 0) for sp in s["spend"] if sp["l3"] == V["name"])     # 결제 수량 (럭스바 잔 · 병, 르파사쥬 바스켓 …)
                            if q:
                                r["qty"] += q; r["buy_teams"].add(det["id"])
                sw = s.get("switch") or {}
                if inside and not seen_over and LABEL2LOC.get(sw.get("원래")) == venue:
                    seen_over = True       # engine.day 와 같게 손님 · 업장마다 한 번
                    t = datetime.fromisoformat(sw["시각"]) if sw.get("시각") else datetime.fromisoformat(s["t_in"])
                    n = win_at(t)
                    if n:
                        res[n]["over_persons"] += pp["party"]; res[n]["over_teams"].add(det["id"])
    rows = []
    for w in wins:
        r = res[w["name"]]
        rows.append(dict(window=w["name"], kind=w["kind"], t0=w["t0"], t1=w["t1"], persons=r["persons"], teams=len(r["teams"]), takeout=r["takeout"],
                         over_persons=r["over_persons"], over_teams=len(r["over_teams"]), net_krw=round(r["krw"] / 1.1), qty=r["qty"], buy_teams=len(r["buy_teams"]),
                         window_persons=w["persons"], peak_pct=w.get("peak_pct"), check=(r["persons_all"] == w["persons"])))
    out = dict(key=key, date=D["date"], scenario=D["scenario"], knobs=D.get("knobs", ""), model_ver=D.get("model_ver"), input_ver=D.get("input_ver"),
               venue=venue, venue_name=V["name"], cap=V["cap"], window=window or "*", group=gid, group_label=label, rows=rows,
               basis="체크인 고객 기준 (이 날 체크인한 손님 + 그 날 비투숙 · 익일 회차는 이 날 체크인 손님의 다음 날)",
               check_ok=all(r["check"] for r in rows))
    out["operating"], out["operating_note"] = operating(D, venue, gid)
    out["kind"] = "bar" if venue == "LUX_BAR" else ("purchase" if venue == "LE_PASSAGE" else "seat")
    return out


def operating(D, venue, gid):
    """그 날 운영 기준 (연박 집계 · 실험) → (값, 안내). 값이 없을 때 0 이 아니라 None + 이유를 돌려준다 (10/16 QA)
    붙이는 조건: 이 하루가 연박 집계와 같은 조건(v4.1 기본 · 행사 없음 · 규모 100% · 같은 버전 — stay_day.json 의 base_keys) ·
    연박 집계가 세는 업장 · 고객군이 전체 / 투숙 / 비투숙 하나"""
    f = Path(STAY_FILE)
    if not f.exists():
        return None, None
    S = json.loads(f.read_text(encoding="utf-8"))
    if D.get("key") not in (S.get("base_keys") or []) or S.get("model_ver") != D.get("model_ver") or S.get("input_ver") != D.get("input_ver"):
        return None, f"그 날 운영 기준(연박 손님 포함)은 {S.get('condition') or 'v4.1 기본 조건'}에서만 계산했습니다. 이 결과와 조건이 달라 붙이지 않습니다."
    if venue not in STAY_VENUES:
        return None, "이 업장은 그 날 운영 기준(연박 집계)을 아직 계산하지 않았습니다. 0명이라는 뜻이 아닙니다."
    if gid not in ("all", "guest", "day"):
        return None, "연박 집계는 전체 · 투숙 · 비투숙으로만 나뉘어 있어, 이 고객군에는 붙이지 않습니다."
    runs = [r for r in S.get("runs", []) if r["date"] == D["date"] and r.get("warm", 0) >= 2]
    if not runs:
        return None, "이 날짜는 연박 집계를 아직 돌리지 않았습니다." 
    vals = []
    for r in runs:
        g = r["meals"].get(venue) or {}
        vals.append(sum(n for k, n in g.items() if gid == "all" or (gid == "day") == (k == "비투숙")))
    return dict(mean=round(sum(vals) / len(vals), 1), lo=min(vals), hi=max(vals), seeds=[r["seed"] for r in runs], warm=runs[0]["warm"],
                unit=("결제 음료 수량 (잔 · 병)" if venue == "LUX_BAR" else "구매 바스켓 수") if venue in ("LUX_BAR", "LE_PASSAGE") else "착석 인원 (조식 포함 · 그 날 시작한 식사)",
                note="연박 집계 · 실험 · 워밍업 첫날 이월 0 · 업장 하루 단위만 (회차 · 목적 · 연령은 아직 없음)"), None
