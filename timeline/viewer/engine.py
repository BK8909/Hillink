"""
힐링크 지도 화면의 계산 쪽 — 모델(agent_v4 · generate · revenue · scenario_winefair)을 그대로 돌리고 결과를 JSON 으로 낸다 (10/12 경수)

  python3 engine.py library                       # 화면이 처음 읽는 것 — 날짜 · 장소 이름 · 근거 묶음 (후기 · 가정표 · 운영 창 · 좌석)
  python3 engine.py packages  < cfg.json          # 그 날 · 그 건물 · 그 인원에 팔리는 객실 상품
  python3 engine.py guest     < cfg.json          # 손님 한 팀을 돌린다 — 동선 · 턴마다 후보와 점수 · 지출 줄
  python3 engine.py day --date 2026-10-10 --scenario winefair --scale 1.0     # → cache/2026-10-10_winefair_s100.*
                                                  # 하루 손님 전부를 돌려 좌석표 · 업장별 인원 · 손님 목록을 캐시에 남긴다

모델은 고치지 않는다. 와인페어처럼 모듈을 바꿔 끼우는 시나리오가 있어서, 화면(app.py)은 이 파일을 매번 새 프로세스로 부른다.
행동 선택 근거는 agent_v4 가 Trace.meta 에 남긴 것(같은 턴 후보 · 점수 · 빠진 이유)을 그대로 옮긴다.
"""
from __future__ import annotations

import argparse, copy, csv, importlib, io, contextlib, json, math, pickle, random, re, sys, time as _time
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path.insert(0, str(TL))

import agent_v4, revenue, prices
import generate as G
import version as _version
import walkerhill_timeline_validator as V
from agent_v0 import Persona, TRAITS

CACHE = HERE / "cache"
FAIR_SPOT = "FOREST_PARK"

# 장소 코드 → 화면 이름
LOC_NAMES = {
    "HOTEL_GATE": "정문", "VALET_DESK": "발렛", "PARKING_TOWER_B1": "주차타워 B1", "PARKING_TOWER_4F": "주차타워 4F",
    "GRAND_LOBBY": "그랜드 로비", "GRAND_FRONT_DESK": "그랜드 프런트", "GRAND_ROOM": "그랜드 객실", "GRAND_POOL": "그랜드 실내수영장",
    "GRAND_CLUB_LOUNGE": "그랜드 클럽라운지", "GRAND_LIBRARY": "그랜드 라이브러리", "FITNESS": "그랜드 피트니스", "WELLNESS_SAUNA": "사우나",
    "THE_PAVILION": "더 파빌리온", "GEUMRYONG": "금룡", "LE_PASSAGE": "르파사쥬", "LUX_BAR": "LUX BAR", "ONDAL": "온달",
    "VISTA_LOBBY": "비스타 로비", "VISTA_ROOM": "비스타 객실", "VISTA_POOL": "비스타 수영장", "VISTA_FITNESS": "비스타 피트니스",
    "SKYARD": "스카이야드", "THE_BUFFET": "더뷔페", "MOEGI": "모에기", "RIVERPARK": "리버파크",
    "DOUGLAS_LOBBY": "더글라스 로비", "DOUGLAS_ROOM": "더글라스 객실", "DOUGLAS_LOUNGE": "더글라스 라운지", "DOUGLAS_LIBRARY": "더글라스 라이브러리",
    "PIZZA_HILL": "피자힐", "MYONGWOLGWAN": "명월관", "ANNEX": "애넥스", "FOREST_PARK": "포레스트 파크",
    "THEATRE_OF_LIGHT": "빛의 시어터", "THEATRE_ART_SHOP": "시어터 아트숍", "CU_THEATRE": "CU (시어터)", "CONVENTION": "컨벤션",
    "GOLF_CLUB": "골프 클럽", "TENNEZ_PARK": "테니즈 파크",
}
PROP_NAMES = {"GRAND": "그랜드 워커힐", "VISTA": "비스타 워커힐", "DOUGLAS": "더글라스 하우스"}
# 좌석을 세는 업장 (prices.SEATS 이름) → 장소 코드
SEAT_LOC = {"더뷔페": "THE_BUFFET", "피자힐": "PIZZA_HILL", "금룡": "GEUMRYONG", "명월관": "MYONGWOLGWAN", "모에기": "MOEGI",
            "온달": "ONDAL", "파빌리온": "THE_PAVILION", "럭스바": "LUX_BAR", "르파사쥬": "LE_PASSAGE"}
# 행동 → 화면 색 묶음
KIND = {**{k: "checkin" for k in agent_v4.CHECKIN_KEYS}, "room": "room", "sleep": "room", "meal_other": "room", "meal_out": "checkin",
        "winefair": "event", "fair_food": "event"}


def kind_of(key):
    if key in KIND:
        return KIND[key]
    if key in agent_v4.MEAL_KEYS:
        return "meal"
    return "facility"


def fair_day(d: date) -> bool:
    import scenario_winefair as W
    return d in W.FAIR_DAYS


def iso(t):
    return t.isoformat(timespec="minutes") if isinstance(t, (datetime, date)) else t


# ---------------------------------------------------------------------------
# 시나리오
# ---------------------------------------------------------------------------

def apply_scenario(scenario: str, d: str):
    """winefair — 와인페어 4판 (scenario_winefair.install). none — 행사 없음 (generate --close WINE_FAIR 와 같다)"""
    if scenario == "winefair":
        import scenario_winefair as W
        W.install()
    else:
        import dataclasses
        day = date.fromisoformat(d)
        V.WALKERHILL_VENUE_WINDOWS["WINE_FAIR"] = tuple(
            dataclasses.replace(w, closed=tuple(w.closed) + ((day - timedelta(days=1), day + timedelta(days=2)),))
            for w in V.WALKERHILL_VENUE_WINDOWS["WINE_FAIR"])


# ---------------------------------------------------------------------------
# 근거 묶음 (화면이 한 번 읽는다)
# ---------------------------------------------------------------------------

def _window_text(w) -> str:
    s = f"{w.open_at:%H:%M}~{w.close_at:%H:%M}"
    if w.last_order:
        s += f" (주문 마감 {w.last_order:%H:%M})"
    if w.weekdays is not None:
        s += " · " + "".join("월화수목금토일"[i] for i in sorted(w.weekdays))
    if w.holidays == "+":
        s += "·공휴일"
    elif w.holidays == "-":
        s += " (공휴일 제외)"
    if w.season:
        a, b, c, e = w.season
        s += f" · {a}/{b}~{c}/{e}"
    if w.years:
        s += " · " + ",".join(str(y) for y in sorted(w.years))
    if w.closed:
        s += " · 닫는 날 " + ", ".join(f"{x:%m/%d}" + (f"~{y:%m/%d}" if y != x else "") for x, y in w.closed[:4])
    return f"{w.source.value} {s}"


# 온톨로지 (대표님 모델 · 사이트에서 팀이 채집한 CSV) — 금액이 아니라 비중 · 인원 · 상품 구성을 대조한다
ONTO_L3 = {"더파빌리온": "파빌리온"}        # 온톨로지 업장 이름 → 우리 L3 이름
ONTO_LOC = {"그랜드": "GRAND_ROOM", "비스타": "VISTA_ROOM", "더글라스": "DOUGLAS_ROOM", "더뷔페": "THE_BUFFET", "피자힐": "PIZZA_HILL", "명월관": "MYONGWOLGWAN",
            "금룡": "GEUMRYONG", "온달": "ONDAL", "모에기": "MOEGI", "파빌리온": "THE_PAVILION", "르파사쥬": "LE_PASSAGE", "럭스바": "LUX_BAR"}


def ontology():
    out = {"l3_1010": {}, "persons_1010": {}, "presets": [], "purpose_by_venue": {}, "l4": {}, "l4_by_purpose": {}}
    f = TL / "ontology_l3_1010.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            name = ONTO_L3.get(r["업장"], r["업장"])
            try:
                out["l3_1010"][name] = {"l2": r["L2"], "eok": float(r["온톨로지 10/10 순매출(억)"])}
            except ValueError:
                pass
    f = TL / "ontology_l3_1010_persons.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            name = ONTO_L3.get(r["업장"], r["업장"])
            try:
                out["persons_1010"][name] = int(r["온톨로지 10/10 판매·사용(인·회 · 한호 채집)"])
            except ValueError:
                pass
    f = TL / "ontology_presets.csv"
    if f.exists():
        out["presets"] = list(csv.DictReader(open(f, encoding="utf-8-sig")))
    f = TL / "ontology_dining.csv"
    if f.exists():
        by_v = defaultdict(dict)
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            try:
                by_v[r["업장"]][r["목적"]] = int(r["월 이용 인원(온톨로지 · 슬기 목적 필터 채집)"])
            except ValueError:
                pass
        for loc, d in by_v.items():
            tot = sum(d.values()) or 1
            out["purpose_by_venue"][loc] = {k: round(v / tot, 3) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}
    f = TL / "ontology_journey_shh.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            if r["필터종류"] == "전체":
                name = ONTO_L3.get(r["업장"], r["업장"])
                try:
                    out["l4"].setdefault(name, []).append({"product": r["상품"], "qty": int(r["수량"]), "krw": float(r["순매출"])})
                except ValueError:
                    pass
    f = TL / "ontology_journey_jsg.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            if r["필터종류"] == "목적":
                name = ONTO_L3.get(r["업장"], r["업장"])
                q = "".join(ch for ch in r["수량"] if ch.isdigit())
                if q:
                    out["l4_by_purpose"].setdefault(name, {}).setdefault(r["필터값"], []).append({"product": r["상품"], "qty": int(q)})
    return out


# 10월 전체 온톨로지 긁은 자료 (경수 10/13) — 저장소 밖 폴더 walkerhill_oct_base 에 원본(금액 포함), 저장소 안에는 비율 · 개수만 (ontology_oct_*.csv)
ONTO_L2 = {"ROOM": "ROOM", "F&B": "F&B", "LEISURE": "LEISURE", "EXTERNAL": "EXTERNAL"}


def onto_dir():
    import os
    cands = [os.environ.get("WH_ONTO_DIR"), TL.parents[1] / "walkerhill_oct_base", TL.parents[2] / "walkerhill_oct_base", Path.home() / "Downloads" / "walkerhill_oct_base"]
    for c in cands:
        if c and Path(c).exists():
            return Path(c)
    return None


def _l2(s):
    return s.split(" ")[0].strip() if s else ""


def ontology_oct():
    """날짜별 L2 · L3 비중, 풀(수용한도 · 요청수요 · 입장허용 · 실이용), 업장별 성별 · 연령 비중. 원본이 있으면 원본에서, 없으면 저장소의 비율 파일에서."""
    out = {"daily": {}, "ga": {}, "src": None}
    d = onto_dir()
    if d and (d / "ontology_l3_oct_all.csv").exists():
        out["src"] = "원본 (walkerhill_oct_base)"
        by = defaultdict(lambda: {"fair": False, "l2": defaultdict(float), "l3": {}, "pools": []})
        for r in csv.DictReader(open(d / "ontology_l3_oct_all.csv", encoding="utf-8-sig")):
            day = by[r["날짜"]]
            l2 = _l2(r["L2_부문"]); name = ONTO_L3.get(r["L3_업장"], r["L3_업장"])
            net = float(r["순매출"] or 0)
            day["l2"][l2] += net
            day["l3"][name] = {"l2": l2, "net": net, "qty": int(float(r["판매수량_합"] or 0))}
            day["fair"] = day["fair"] or (r.get("비고", "").strip() == "와인페어 포함")
        if (d / "persons_oct_daily.csv").exists():
            for r in csv.DictReader(open(d / "persons_oct_daily.csv", encoding="utf-8-sig")):
                if not r["풀이름"]:
                    continue
                by[r["날짜"]]["pools"].append({"venue": ONTO_L3.get(r["L3_업장"], r["L3_업장"]), "l2": _l2(r["L2_부문"]), "id": r["풀ID"], "name": r["풀이름"], "unit": r["단위"],
                                              "cap": int(float(r["수용한도"] or 0)), "req": int(float(r["요청수요"] or 0)), "allow": int(float(r["입장허용"] or 0)), "used": int(float(r["실이용"] or 0))})
        for k, day in by.items():
            tot2 = sum(day["l2"].values()) or 1
            l3 = {}
            for name, x in day["l3"].items():
                sub = day["l2"][x["l2"]] or 1
                l3[name] = {"l2": x["l2"], "share": round(x["net"] / sub, 4), "qty": x["qty"]}     # L2 안 비중 (금액은 안 넘긴다)
            out["daily"][k] = {"fair": day["fair"], "l2": {a: round(b / tot2, 4) for a, b in day["l2"].items()}, "l3": l3, "pools": day["pools"]}
        # 전수 채집 (10/13 저녁) — 프리셋 합계 · 풀 정의 · 조정값 하나씩 바꾼 결과 · 조정값 기본값. 금액은 비율로만
        f = d / "presets" / "summary_all.csv"
        if f.exists():
            for r in csv.DictReader(open(f, encoding="utf-8-sig")):
                try:
                    parts = {k: float(r[k] or 0) for k in ("ROOM", "F&B", "LEISURE", "EXTERNAL")}
                    tot = sum(parts.values()) or 1
                    days = int(r["일수"] or 1)
                    out.setdefault("presets", []).append({
                        "preset": r["날짜프리셋"], "scenario": r["시나리오"], "start": r["시작일"], "end": r["종료일"], "days": days,
                        "room_nights": int(float(r["객실박"] or 0)), "room_nights_day": round(float(r["객실박"] or 0) / days, 1), "occ": float(r["가동률(%)"] or 0),
                        "l2": {k: round(v / tot, 4) for k, v in parts.items()},
                        "knobs": {"occupancy": r.get("객실가동률_손잡이"), "fill": r.get("좌석점유율_손잡이"), "demand": r.get("구매수요배율_손잡이"), "dwell": r.get("식사시간_손잡이")}})
                except (ValueError, KeyError):
                    pass
        f = d / "definitions" / "pools.csv"
        if f.exists():
            for r in csv.DictReader(open(f, encoding="utf-8-sig")):
                try:
                    out.setdefault("pool_def", {})[r["풀ID"]] = {"name": r["풀이름"], "venue": ONTO_L3.get(r["L3_업장"], r["L3_업장"]), "kind": r["종류"],
                                                             "cap_oct": int(float(r["가능량_10월"] or 0)), "req_oct": int(float(r["요청_10월"] or 0)), "used_oct": int(float(r["사용량_10월"] or 0)),
                                                             "cap_1010": int(float(r["가능량_1010"] or 0)), "used_1010": int(float(r["사용량_1010"] or 0)),
                                                             "how": (r.get("설명") or "").split("날짜별 표에서 차이를 확인합니다.")[-1].strip()[:160], "src": r.get("출처", "")}
                except (ValueError, KeyError):
                    pass
        # 풀별 고객 구성비 (가정 원장 · 10월 기준 첫날) — 업장마다 사용량이 가장 큰 풀의 목적 믹스
        f = d / "presets" / "10월 전체" / "기준" / "mix_ledger.csv"
        if f.exists():
            best = {}
            for r in csv.DictReader(open(f, encoding="utf-8-sig")):
                try:
                    used = float(r["기간_사용량"] or 0)
                except ValueError:
                    continue
                name = ONTO_L3.get(r["L3_업장"], r["L3_업장"])
                mix = {k[4:]: round(float(v) / 100, 4) for k, v in r.items() if k.startswith("믹스%_") and v}
                if mix and used >= best.get(name, (-1, None))[0]:
                    best[name] = (used, {"pool": r["풀이름"], "mix": mix})
            out["pool_mix"] = {k: v[1] for k, v in best.items()}
        f = d / "knob_sweeps" / "index.csv"
        if f.exists():
            base = {}
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
            for r in rows:
                if r["조건코드"] == "base":
                    base[r["날짜"]] = float(r["전체순매출"] or 0)
            for r in rows:
                b = base.get(r["날짜"]) or 1
                out.setdefault("sweeps", {}).setdefault(r["날짜"], []).append({"code": r["조건코드"], "name": r["조건"], "pct": round(float(r["기준대비"] or 0) / b * 100, 2)})
        f = d / "definitions" / "knobs.md"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 4 and cells[0].startswith("`") and cells[0].endswith("`"):
                    out.setdefault("knob_defs", []).append({"key": cells[0].strip("`"), "name": cells[1], "default": cells[2], "unit": cells[3]})
        if (d / "dining_gender_age_oct.csv").exists():
            for r in csv.DictReader(open(d / "dining_gender_age_oct.csv", encoding="utf-8-sig")):
                v = out["ga"].setdefault(ONTO_L3.get(r["L3_업장"], r["L3_업장"]), {"age": {}, "sex": {}})
                pct = round(float(r["업장내_순매출비중(%)"] or 0) / 100, 4)
                if r["성별필터"] == "전체" and r["연령필터"] != "전체":
                    v["age"][r["연령필터"]] = pct
                elif r["연령필터"] == "전체" and r["성별필터"] != "전체":
                    v["sex"][r["성별필터"]] = pct
        return out
    f = TL / "ontology_oct_daily.json"
    if f.exists():
        out = json.loads(f.read_text(encoding="utf-8")); out["src"] = "저장소 비율 파일 (ontology_oct_daily.json)"
    return out


def library():
    # 후기 근거 — persona_blog*.py 의 TRUTH_VISITED (후기가 그 장소에 갔다는 판단과 근거 문장)
    reviews = defaultdict(list)
    for f in sorted(TL.glob("persona_blog*.py")):
        name = f.stem
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                m = importlib.import_module(name)
        except Exception:
            continue
        for loc, why in (getattr(m, "TRUTH_VISITED", None) or {}).items():
            reviews[loc].append({"blog": name.replace("persona_", ""), "why": why})
    # 가정표 (소연) — 장소코드별 항목
    assumptions = defaultdict(list)
    for r in csv.DictReader(open(TL / "place_assumptions.csv", encoding="utf-8-sig")):
        code = r.get("장소코드", "-")
        if code and code != "-":
            assumptions[code].append({k: r.get(k, "") for k in ("구분", "항목", "값", "단위", "조건", "등급", "출처", "근거", "확인일", "현장확인", "비고")})
    windows = {code: [_window_text(w) for w in ws] for code, ws in V.WALKERHILL_VENUE_WINDOWS.items()}
    windows.update({code: [f"△ {a:%H:%M}~{b:%H:%M} (에이전트 임시값)" for a, b in ws] for code, ws in agent_v4.TEMP_WINDOWS.items()})
    seats = {SEAT_LOC[k]: dict(v, name=k) for k, v in prices.SEATS.items() if k in SEAT_LOC}
    chain = []
    p = TL.parent / "docs" / "evidence_chain_20261010.csv"
    if p.exists():
        chain = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    access = {}
    for code, fa in getattr(V, "FACILITY_ACCESS", {}).items():
        access[code] = str(fa)
    dates = []
    for d in sorted(G.load_factors()):
        dd = date.fromisoformat(d)
        dates.append({"date": d, "dow": "월화수목금토일"[dd.weekday()], "fair": fair_day(dd)})
    grid = G.load_grid()
    return {
        "dates": dates,
        "loc_names": LOC_NAMES, "prop_names": PROP_NAMES,
        "purposes": [p for p in G.PURPOSES if p != "공항 이동·여행"],
        "ages": sorted({r["연령"] for r in grid}),
        "sexes": sorted({r["성별"] for r in grid}),
        "dining": {k: v for k, v in G.load_dining().items()},
        "reviews": reviews, "assumptions": assumptions, "windows": windows, "seats": seats, "chain": chain, "onto": ontology(), "onto_loc": ONTO_LOC, "onto_oct": ontology_oct(), "knobs": {k: {"name": n, "default": d} for k, (n, d) in KNOBS.items()},
        "n_reviews": len({x["blog"] for v in reviews.values() for x in v}),
        "sns": sns_signals(),
        "model_ver": _version.model_ver(), "input_ver": _version.input_ver(), "v4": V4, "v4_name": V4_NAME,
        # 10/14 성향이 점수에 어떻게 들어가는지 — 화면이 '작용한 요인' 과 '추출됐지만 지금 반영 안 되는 성향' 을 나눠 보여 주는 데 쓴다
        "trait_model": {"lam_trait": agent_v4.THETA_FIT.get("lam_trait"), "traits": list(TRAITS),
                        "always_on": {"대기 회피": "피자힐 · 르파사쥬 포장을 고를 때 (줄 대신 포장 × 계수 takeout)"},
                        "grid_has_traits": False},
        "review_list": review_list(), "grid": grid_rows(), "photos": local_photos(), "anomalies": load_anomalies(), "hypotheses": load_hypotheses(),
        "programs": [{k: r.get(k, "") for k in ("구분", "장소코드", "이름", "회차", "요일", "시작", "끝", "운영 기간", "정원", "정원 단위", "정원 등급", "화면 가정 정원", "화면 가정 근거", "출처")}
                     for r in csv.DictReader(open(TL / "program_capacity.csv", encoding="utf-8-sig"))] if (TL / "program_capacity.csv").exists() else [],
        "provenance": list(csv.DictReader(open(TL / "input_provenance.csv", encoding="utf-8-sig"))) if (TL / "input_provenance.csv").exists() else [],
    }


def sns_signals():
    """trend_signals.csv — 업장별 SNS 목적 건수 (화면 업장 카드의 SNS 열 · 근거 사슬 카드)"""
    import trend
    out = {}
    try:
        prop = trend.propensity(draws=2000)
    except Exception:
        prop = {}
    for venue, sig in trend.load_signals().items():
        out[venue] = {"n": sig["n"], "src": sig["src"], "counts": sig["counts"], "raw": sig["raw"],
                      "prop": {k: {kk: round(vv, 3) for kk, vv in x.items()} for k, x in prop.get(venue, {}).items()}}
    return out


def trend_report(theta: dict | None):
    """조정값 trend_w 가 켜진 날 — 모델 사전 · SNS · 목표 · 달성 (가고 싶은 식당 층)"""
    w = float((theta or {}).get("trend_w") or 0)
    if not w:
        return None
    import os as _os, trend
    saved = _os.environ.pop("WH_TREND", None)
    try:
        base = G.load_dining()
    finally:
        if saved is not None:
            _os.environ["WH_TREND"] = saved
    _, rep = trend.adjust(base, G.load_mix(TL / "purpose_mix.csv"), w)
    return rep


# ---------------------------------------------------------------------------
# 손님 만들기
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 변칙 시나리오 (10/14) — anomaly_scenarios.csv 한 줄을 그 날에 적용한다. 크기는 표의 값 × 조정값 anomaly_k (배율의 1 에서 벗어난 몫을 곱함)
# 크기 출처는 signal_stats (한호님 통계) 로 바꿔 넣는 자리 — 지금 값은 가정(△)
# ---------------------------------------------------------------------------

def load_anomalies(name="anomaly_scenarios.csv"):
    f = TL / name
    return list(csv.DictReader(open(f, encoding="utf-8-sig"))) if f.exists() else []


def load_hypotheses():
    return load_anomalies("hypotheses.csv")


def _kv(s):
    out = {}
    for part in (s or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = float(v)
    return out


def apply_anomaly(aid, k, date_s, factors, day_config, table="anomaly_scenarios.csv"):
    import dataclasses, os as _os
    row = next((r for r in load_anomalies(table) if int(r["ID"]) == aid), None)
    if row is None:
        return None
    sc = lambda m: 1 + (m - 1) * k
    d = date.fromisoformat(date_s)
    applied = []
    for code in [c for c in (row["닫음"] or "").split(";") if c]:
        if code in V.WALKERHILL_VENUE_WINDOWS:
            V.WALKERHILL_VENUE_WINDOWS[code] = tuple(dataclasses.replace(w, closed=tuple(w.closed) + ((d, d),)) for w in V.WALKERHILL_VENUE_WINDOWS[code])
            applied.append(f"{LOC_NAMES.get(code, code)} 닫음")
    for p, m in _kv(row["목적 배율"]).items():
        if p in factors.get(date_s, {}):
            factors[date_s][p] *= sc(m)
            applied.append(f"{p} 손님 × {sc(m):.2f}")
    if row["비투숙 배율"]:
        m = sc(float(row["비투숙 배율"]))
        base = day_config["scenarios"]["base"]
        day_config["scenarios"]["base"] = int(round(base * m))
        applied.append(f"비투숙 {base} → {day_config['scenarios']['base']}팀 (× {m:.2f})")
    bst = {v: sc(m) for v, m in _kv(row["가고 싶음 배율"]).items()}
    if bst:
        prev = json.loads(_os.environ.get("WH_BOOST") or "{}")
        for v, m in bst.items():
            prev[v] = prev.get(v, 1.0) * m       # 변칙 · 가설을 같이 켜면 곱한다
        _os.environ["WH_BOOST"] = json.dumps(prev)
        for v, m in bst.items():
            pp, _, vv = v.rpartition("|")
            applied.append(f"{pp + ' 손님의 ' if pp else ''}{LOC_NAMES.get(vv, vv)} 가고 싶음 × {m:.2f}")
    for v, m in _kv(row["가격 배율"]).items():
        mm = revenue.menu_mod.default()
        name = LOC_SEAT.get(v, v)
        if mm is not None:
            for r in mm.by_venue.get(name, []):
                r["단가"] = r["단가"] * sc(m) if isinstance(r["단가"], (int, float)) else r["단가"]
            applied.append(f"{name} 단가 × {sc(m):.2f}")
    if table != "anomaly_scenarios.csv":
        return {"id": aid, "name": row["이름"], "applied": applied, "evidence": row["근거"], "predict": row["예측"], "judge": row["판정 기준"],
                "grade": row["등급"], "owner": row["담당"], "status": row["상태"]}
    return {"id": aid, "name": row["이름"], "k": k, "applied": applied, "src": row["크기 출처 (signal_stats · 문서)"], "grade": row["등급"],
            "desc": row["설명"], "limit": row["한계"]}


# ---------------------------------------------------------------------------
# 후기 손님 재현 (10/14 · 대표님 10/13 피드백 — 손님 설정이 어느 후기에서 왔는지, 후기가 실제로 간 곳과 모델 동선을 나란히)
# 링크 · 사진은 저장소 밖 로컬 파일에서만 읽는다: viewer/links.local.csv (후기,링크) · viewer/photos.local/<장소코드>.jpg (공식 · 현장 사진)
# ---------------------------------------------------------------------------
import re as _re

LINKS_LOCAL = HERE / "links.local.csv"
PHOTOS_LOCAL = HERE / "photos.local"


def local_links():
    if not LINKS_LOCAL.exists():
        return {}
    out = {}
    for r in csv.reader(open(LINKS_LOCAL, encoding="utf-8-sig")):
        if len(r) >= 2 and r[0].strip().startswith("blog"):
            out[r[0].strip()] = r[1].strip()
    return out


def local_photos():
    if not PHOTOS_LOCAL.is_dir():
        return {}
    out = {}
    for f in sorted(PHOTOS_LOCAL.iterdir()):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            out.setdefault(f.stem.split("__")[0], []).append(f.name)   # LOC.jpg 또는 LOC__2.jpg
    return out


def _review_names():
    from sealed import SEALED_WAIT
    out = []
    for f in sorted(TL.glob("persona_blog*.py")):
        m = _re.fullmatch(r"persona_blog(\d\d)", f.stem)
        if m and int(m.group(1)) not in SEALED_WAIT:
            out.append(f.stem)
    return out


class _Alt:
    """한 후기에 체류가 둘인 파일(blog03 · blog04)의 *_ALT 를 본체처럼 읽는다 (run_all._Alt 와 같다)"""
    FIELDS = ("PERSONA", "START_AT", "TRUTH_VISITED", "TRUTH_PASSED", "TRUTH_NOT_VISITED", "TRUTH_UNREACHABLE", "TRUTH_RESTAURANTS", "TRUTH_ORDER_PAIRS", "TRUTH_MEALS")

    def __init__(self, mod):
        for f in self.FIELDS:
            if hasattr(mod, f + "_ALT"):
                setattr(self, f, getattr(mod, f + "_ALT"))
        self.__doc__ = mod.__doc__


def review_list():
    from sealed import unusable
    links = local_links()
    rows = []
    for name in _review_names():
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                mod = importlib.import_module(name)
        except Exception:
            continue
        if unusable(mod) or not hasattr(mod, "PERSONA"):
            continue
        blog = name.replace("persona_", "")
        for alt, P in ((False, mod), (True, _Alt(mod) if hasattr(mod, "PERSONA_ALT") else None)):
            if P is None:
                continue
            p = P.PERSONA
            st = getattr(P, "START_AT", None)
            rows.append({"blog": blog, "alt": alt, "name": p.name, "is_guest": p.is_guest, "property": p.property, "nights": p.nights,
                         "party": p.party_size, "kids": p.has_child_under_13, "purpose": getattr(p, "purpose", None),
                         "start": iso(st) if st else None, "n_truth": len(getattr(P, "TRUTH_VISITED", {}) or {}),
                         "link": links.get(blog)})
    return rows


def review_guest(cfg):
    """후기 페르소나 한 편을 돌리고, 후기가 간 곳(정답)과 모델 동선을 대조한다 — run_all 과 같은 조건 (좌석 경쟁 없음)"""
    from match import evaluate
    blog = cfg["blog"]
    with contextlib.redirect_stdout(io.StringIO()):
        mod = importlib.import_module("persona_" + blog)
    P = _Alt(mod) if cfg.get("alt") and hasattr(mod, "PERSONA_ALT") else mod
    p = P.PERSONA
    start = getattr(P, "START_AT", None) or datetime(2025, 1, 31, 14, 0)
    if cfg.get("situation"):
        return review_situation(cfg, P, p, start, blog)
    apply_scenario("none", start.date().isoformat())
    catch = Catch()
    out = run_detail(p, start, None, catch)
    segs, _ = catch.last
    reach = agent_v4.reachable(p) if hasattr(agent_v4, "reachable") else None
    r = evaluate(segs, P, title=blog, reachable=reach)
    tv = P.TRUTH_VISITED
    # 같은 손님을 K번 (하루 시뮬레이션과 같은 v4 맞춘 계수 · 확률 선택) — 장소마다 '갈 확률' (blend_v4 의 v4 쪽과 같은 방법)
    from match import visits_from_segments
    K = int(cfg.get("k", agent_v4.K_RUNS))
    cnt, recs, precs = defaultdict(int), [], []
    for i in range(K):
        sg, _ = agent_v4.run_agent(p, start, verbose=False, theta=agent_v4.THETA_FIT, rng=random.Random(revenue.SEED + i))
        rr = evaluate(sg, P, title=blog, reachable=reach)
        recs.append(rr.recall); precs.append(rr.precision)
        for pl in {v.place for v in visits_from_segments(sg)}:
            cnt[pl] += 1
    prob = {k: round(v / K, 3) for k, v in cnt.items()}
    visited = [{"loc": k, "name": LOC_NAMES.get(k, k), "why": str(v), "hit": k in r.hit, "scorable": k in r.truth_scorable,
                "p": prob.get(k, 0.0), "grade": str(v)[:1] if str(v)[:1] in "◎○△" else ""} for k, v in tv.items()]
    tp = getattr(P, "TRUTH_PASSED", {}) or {}
    tn = getattr(P, "TRUTH_NOT_VISITED", {}) or {}
    out["review"] = {
        "blog": blog, "alt": bool(cfg.get("alt")), "link": local_links().get(blog),
        "visited": visited,
        "passed": [{"loc": k, "name": LOC_NAMES.get(k, k), "why": str(v), "agent": k in r.agent_places} for k, v in tp.items()],
        "extra": [{"loc": k, "name": LOC_NAMES.get(k, k), "why": (str(tn[k]) if k in tn else "후기에 언급 없음"), "p": prob.get(k, 0.0)} for k in sorted(r.extra)],
        "k": K, "recall_k": round(sum(recs) / K, 3), "precision_k": round(sum(precs) / K, 3),
        "forbidden": sorted(r.forbidden_hit),
        "recall": round(r.recall, 3), "precision": round(r.precision, 3), "n_scorable": len(r.truth_scorable), "n_hit": len(r.hit),
        "restaurants": r.restaurants_label, "order": None if r.order_rate is None else round(r.order_rate, 3),
        "meals": None if r.meal_rate is None else round(r.meal_rate, 3),
        "facts": getattr(mod, "FACTS_EVIDENCE", {}) if not cfg.get("alt") else getattr(mod, "FACTS_EVIDENCE_ALT", getattr(mod, "FACTS_EVIDENCE", {})),
    }
    out["crowd_note"] = "후기 손님 혼자 — 좌석 경쟁 없음 (46편 대조와 같은 조건)"
    out["scenario"] = "none"
    return out


def _hm(s, default):
    try:
        h, m = (int(x) for x in str(s).split(":"))
        return time(h, m)
    except Exception:
        return default


def packages(cfg):
    mm = revenue.menu_mod.default()
    if mm is None:
        return []
    d = cfg.get("date", "2026-10-10")
    prop = cfg.get("property", "GRAND")
    tmp = Persona(name="", traits={}, party_size=int(cfg.get("party", 2)), has_child_under_13=bool(cfg.get("kids")),
                  nights=int(cfg.get("nights", 1)), property=prop, is_guest=True)
    rows, _ = mm.candidates("room", tmp, datetime.fromisoformat(d).replace(hour=15))
    out = []
    for r in rows:
        incl, club = mm.package_terms(r)
        out.append({"name": r["상품"], "krw": r["단가"], "unit": r["단위"], "grade": r["등급"], "incl": r["포함"],
                    "meals": [list(x) for x in incl], "club": club})
    out.sort(key=lambda x: (x["krw"], x["name"]))
    return out


def build_persona(cfg, rng):
    d = cfg.get("date", "2026-10-10")
    is_guest = bool(cfg.get("is_guest", True))
    party = max(1, int(cfg.get("party", 2)))
    kids = bool(cfg.get("kids")) and party >= 2
    purpose = cfg.get("purpose") or "커플·기념일"
    prop = cfg.get("property", "GRAND") if is_guest else "GRAND"
    if kids and prop == "DOUGLAS":
        prop = "GRAND"          # 더글라스 패키지는 전부 초등학생 이하 동반 불가 (generate.pick_property 와 같은 규칙)
    nights = max(1, int(cfg.get("nights", 1))) if is_guest else 0
    arrive = _hm(cfg.get("arrive"), time(15, 0) if is_guest else time(11, 0))
    start = datetime.combine(date.fromisoformat(d), arrive)
    incl, club, package = (), False, None
    pk = cfg.get("package", "auto")
    if is_guest:
        if pk == "auto":
            incl, club, package = G.room_booking(prop, party, kids, nights, start.replace(hour=15, minute=0), rng)
        elif pk and pk != "none":
            mm = revenue.menu_mod.default()
            row = mm.row_of(revenue.menu_mod.ROOM_VENUE[prop], pk) if mm else None
            if row is not None:
                incl, club = mm.package_terms(row)
                package = pk
    pref = cfg.get("prefers", "auto")
    if pref == "auto":
        prefers = G.pick_prefer(purpose, G.load_dining(), rng, G.P_PREFER_GUEST if is_guest else G.P_PREFER_DAY)
    elif pref:
        prefers = (pref,)
    else:
        prefers = ()
    booked = (FAIR_SPOT,) if (cfg.get("wf_go") and cfg.get("scenario") == "winefair" and fair_day(start.date())) else ()
    p = Persona(
        name=f"화면 손님 · {purpose}", traits={k: None for k in TRAITS}, party_size=party, has_child_under_13=kids,
        nights=nights, property=prop, is_guest=is_guest, included_meals=tuple(incl), club_access=bool(club), package=package,
        sex=cfg.get("sex") or None, age_band=cfg.get("age") or None, purpose=purpose, prefers=tuple(prefers), booked=booked,
        wake_at=_hm(cfg.get("wake"), None) if cfg.get("wake") else None,
        depart_by=_hm(cfg.get("depart"), time(22, 0)), arrival=cfg.get("arrival") or None,
        note="지도 화면에서 만든 손님")
    return p, start


def persona_dict(p: Persona, start: datetime):
    return {"name": p.name, "is_guest": p.is_guest, "property": p.property, "prop_name": PROP_NAMES.get(p.property),
            "nights": p.nights, "party": p.party_size, "kids": p.has_child_under_13, "sex": p.sex, "age": p.age_band,
            "purpose": p.purpose, "ai_type": p.ai_type, "package": p.package, "included": [list(x) for x in p.included_meals], "club": p.club_access,
            "prefers": list(p.prefers), "booked": list(p.booked), "arrival": p.arrival, "start": iso(start),
            "traits": {k: p.traits.get(k) for k in TRAITS},          # 10/14 후기에서 뽑은 성향 7개 (None = 후기에 근거 없음) — 화면에서 반영 여부와 같이 보여 준다
            "depart": p.depart_by.strftime("%H:%M") if not p.is_guest else None,
            "wake": p.wake_at.strftime("%H:%M") if p.wake_at else agent_v4.WAKE_AT.strftime("%H:%M")}


# ---------------------------------------------------------------------------
# 한 팀 돌리기 — revenue.spend_lines 를 그대로 쓰면서 동선 · 근거를 받아 둔다
# ---------------------------------------------------------------------------

class Catch:
    """agent_v4.run_agent 를 감싸서 마지막으로 돈 손님의 동선 · 트레이스를 받는다 (모델은 안 바뀐다)"""
    def __init__(self):
        self.base = agent_v4.run_agent
        self.last = None
        agent_v4.run_agent = self.run

    def run(self, p, start, *a, **kw):
        segs, traces = self.base(p, start, *a, **kw)
        self.last = (segs, traces)
        return segs, traces


def _clean_why(xs):
    return [str(x) for x in xs]


def run_detail(p, start, cap, catch: Catch):
    m = SimpleNamespace(PERSONA=p, START_AT=start)
    lines = revenue.spend_lines(m, k=1, capacity=cap)
    segs, traces = catch.last
    return detail_json(p, start, segs, traces, lines)


def detail_json(p, start, segs, traces, lines):
    by_at = defaultdict(list)
    for ln in lines:
        by_at[(ln["key"], ln["at"])].append(ln)
    steps = []
    for i, t in enumerate(traces):
        mt = t.meta or {}
        key = mt.get("key", t.chosen)
        sp = [dict(product=str(l["product"]), krw=l["krw"], l2=l["l2"], l3=l["l3"], qty=l["qty"], grade=l["grade"], note=l["note"])
              for l in by_at.get((key, t.start), [])]
        steps.append({
            "i": i, "label": t.chosen, "key": key, "kind": kind_of(key), "location": mt.get("location"), "venue": mt.get("venue"),
            "state": mt.get("state"), "t_in": iso(t.start), "t_out": iso(mt.get("t_out")) if mt.get("t_out") else None,
            "pts": mt.get("pts"), "why": _clean_why(t.why), "travel": mt.get("travel"), "wait": mt.get("wait"),
            "rank": mt.get("rank"), "top_gap": mt.get("top_gap"), "tau": mt.get("tau"),
            "considered": t.considered, "feasible": t.feasible,
            "alts": [dict(a, t=iso(a["t"]), why=_clean_why(a["why"])) for a in mt.get("alts", [])],
            "rejected": list(mt.get("rejected", t.rejected)),
            "switch": {k: (iso(v) if isinstance(v, datetime) else v) for k, v in (t.switch or {}).items()},
            "spend": sp,
        })
    seg_out = [{"state": s.state, "location": s.location, "t_in": iso(s.t_in), "t_out": iso(s.t_out)} for s in segs]
    total = sum(l["krw"] for l in lines)
    by_l2 = defaultdict(float)
    for l in lines:
        by_l2[l["l2"]] += l["krw"]
    return {"persona": persona_dict(p, start), "steps": steps, "segments": seg_out,
            "spend_total": total, "spend_by_l2": dict(by_l2), "n_lines": len(lines)}


def crowd_env(cfg, d):
    """10/16 '다른 손님(호텔 전체 환경)' — 그 날 손님들이 잡은 좌석(cap.pkl) 위에 이 손님을 넣고, 그 하루를 돌린 조정값(회차 끝까지 · 줄 상한 등)과
    변동 상황도 이 손님에게 똑같이 건다. 예전에는 좌석만 가져오고 조정값은 기본값으로 돌아, 같은 날 안의 손님과 규칙이 달랐다"""
    if not cfg.get("crowd"):
        return None, "이 손님 혼자 — 좌석 경쟁 없음", None
    f = CACHE / f"{cfg['crowd']}.cap.pkl"
    if not f.exists():
        return None, "하루 계산 캐시가 없어 혼자 돌림", None
    cap = pickle.load(f.open("rb"))
    anom = None
    try:
        D = json.loads((CACHE / f"{cfg['crowd']}.json").read_text(encoding="utf-8"))
        th = {k: v for k, v in (D.get("theta") or {}).items() if k in KNOBS and k not in ("seed", "anomaly", "anomaly_k", "hypo", "trend_w", "search_w", "posting_k")}
        agent_v4.THETA_FIT.update(th)
        if (D.get("theta") or {}).get("anomaly") and not cfg.get("anomaly"):
            anom = apply_anomaly(int(D["theta"]["anomaly"]), float(D["theta"].get("anomaly_k") or 1.0), d, G.load_factors(), {"scenarios": {"base": 0}})
    except Exception:
        pass
    return cap, "그 날 손님들이 이미 잡은 좌석 위에 들어감 (" + cfg["crowd"] + ")", anom


def review_situation(cfg, P, p, start, blog):
    """10/16 같은 후기 페르소나를 다른 상황(날짜 · 행사 · 변동 상황 · 호텔 전체 환경)에 놓고 한 번 돌린다.
    후기에 적힌 손님 속성(인원 · 객실 · 포함 끼니 · 도착 시각)은 그대로 두고 날짜만 옮긴다. 결과는 모델의 가상 추론이며 관측이 아니다"""
    d = cfg.get("date", "2026-10-10")
    scenario = cfg.get("scenario", "none")
    apply_scenario(scenario, d)
    anomaly = None
    if cfg.get("anomaly"):
        anomaly = apply_anomaly(int(cfg["anomaly"]), float(cfg.get("anomaly_k") or 1.0), d, G.load_factors(), {"scenarios": {"base": 0}})
    cap, crowd_note, env_anom = crowd_env(cfg, d)
    if anomaly is None and env_anom:
        anomaly = env_anom
    start2 = datetime.combine(date.fromisoformat(d), start.time())
    catch = Catch()
    out = run_detail(p, start2, cap, catch)
    out["crowd_note"] = crowd_note
    out["lam_trait"] = agent_v4.THETA_FIT.get("lam_trait")
    out["scenario"] = scenario
    out["anomaly"] = anomaly
    out["origin"] = {"blog": blog, "alt": bool(cfg.get("alt")), "orig_start": iso(start),
                     "truth": [{"loc": k, "name": LOC_NAMES.get(k, k)} for k in (P.TRUTH_VISITED or {})]}
    if cap is not None:
        out["turned_away_here"] = [dict(key=k, t=iso(t)) for who, k, t in cap.events if who == p.name]
    return out


def guest(cfg):
    d = cfg.get("date", "2026-10-10")
    scenario = cfg.get("scenario", "none")
    apply_scenario(scenario, d)
    # 10/14 변동 상황 — 하루 전체와 같은 변칙 시나리오(휴업 · 가격 · 가고 싶음 배율)를 이 손님에게도 건다. 손님 수 배율은 혼잡(crowd) 날에 이미 들어 있다
    anomaly = None
    if cfg.get("anomaly"):
        anomaly = apply_anomaly(int(cfg["anomaly"]), float(cfg.get("anomaly_k") or 1.0), d, G.load_factors(), {"scenarios": {"base": 0}})
    rng = random.Random(int(cfg.get("seed", 7)))
    p, start = build_persona(cfg, rng)
    cap, crowd_note, env_anom = crowd_env(cfg, d)
    if anomaly is None and env_anom:
        anomaly = env_anom
    catch = Catch()
    out = run_detail(p, start, cap, catch)
    out["crowd_note"] = crowd_note
    out["lam_trait"] = agent_v4.THETA_FIT.get("lam_trait")          # 10/14 성향 반영 강도 (0 이면 성향 7개가 점수에 안 들어감)
    out["scenario"] = scenario
    out["anomaly"] = anomaly
    if cap is not None:
        out["turned_away_here"] = [dict(key=k, t=iso(t)) for who, k, t in cap.events if who == p.name]
    return out


# ---------------------------------------------------------------------------
# 하루 전체 — generate.py 와 같은 기본값으로 그 날 손님을 전부 돌린다
# ---------------------------------------------------------------------------

# 업장 회차 — 검증기 운영 창을 그 날짜에 맞게 고르고, 창이 하나뿐이고 회차 수(prices.SEATS turns)가 여럿이면 같은 길이로 나눈다 (피자힐 90분 7부)
LOC_SEAT = {v: k for k, v in SEAT_LOC.items()}   # 장소 코드 → 좌석표 이름 (SEAT_LOC 는 이름 → 코드)


def _count(teams, ki):
    out = defaultdict(int)
    for attrs in teams.values():
        out[attrs[ki]] += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _sum_by(d5, ki, vi):
    out = defaultdict(int)
    for k, vals in d5.items():
        out[k[ki]] += vals[vi]
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def venue_windows(loc: str, d: date):
    from agent_v0 import meal_kind_at
    ws = [w for w in V.WALKERHILL_VENUE_WINDOWS.get(loc, ()) if not w.states and w.opens_on(d)]
    out = []
    for w in sorted(ws, key=lambda w: w.open_at):
        t0 = datetime.combine(d, w.open_at); t1 = datetime.combine(d, w.close_at)
        if t1 <= t0:
            t1 += timedelta(days=1)
        out.append([t0, t1])
    name = LOC_SEAT.get(loc)
    turns = prices.SEATS.get(name, {}).get("turns", 1) if name else 1
    if len(out) == 1 and turns > 1:
        t0, t1 = out[0]
        step = (t1 - t0) / turns
        out = [[t0 + step * i, t0 + step * (i + 1)] for i in range(turns)]
    # 이름 — 끼니 종류 + 부
    named, cnt = [], defaultdict(int)
    for t0, t1 in out:
        kind = meal_kind_at(t0 + (t1 - t0) / 2) or meal_kind_at(t0) or ""
        cnt[kind] += 1
        named.append({"name": f"{kind} {cnt[kind]}부" if kind else f"{t0:%H:%M} 회차", "kind": kind, "t0": t0, "t1": t1})
    kinds = defaultdict(int)
    for x in named:
        kinds[x["kind"]] += 1
    for x in named:
        if kinds[x["kind"]] == 1 and x["kind"]:
            x["name"] = x["kind"]
    return named


# 시나리오 조정값 (10/13 실험 3) — 키 · 이름 · 기본값. 기본값만이면 캐시 키에 안 붙고 전과 같다
# 10/16 기본 모델 정의 — 화면의 '온톨로지 정합' 묶음. 이 정의가 바뀌면 engine.py 해시(model_ver)가 바뀌어
# 예전 결과는 '예전 기준' 으로 표시되고, 새 기본으로 다시 계산해야 한다 (restamp 로 버전만 바꾸지 않는다)
# v4.1 = v4 + 중식 · 석식 혼잡 시 체류 단축 끔 (no_busy_dwell 2 · 근거사슬 7-19 · 세 가지 확인 통과). 조식까지 끄는 1 과 예전 방식(없음)은 비교용
V4_NAME = "v4.1"
V4 = {"next_window": 1, "reserve_wait": 1, "queue_max": 30, "takeout_cap": 40, "bar_nightcap": 0.16, "purpose_onto": 1, "passage_rate": 0.62,
      "fine_dwell": 120, "moegi_seats": 40, "turn_hold": 1, "no_busy_dwell": 2, "rooms_onto": 1, "order_mix": 1, "wd_day": 0.5, "rooms_formula": 1, "rng_team": 1}

KNOBS = {"next_window": ("다음 회차 보기", 0), "wait_horizon": ("대기 상한 (분)", 150), "takeout_base": ("피자힐 포장 감점", 0.0),
         "reserve_wait": ("예약 대기 (벌점 없음)", 0), "queue_max": ("회차 안 줄 서기 상한 (분)", None), "takeout_cap": ("포장 하루 한도 (판)", None),
         "bar_nightcap": ("럭스바 저녁 뒤 한잔 비율", None), "purpose_onto": ("목적 섞기 · 온톨로지 배분", 0),
         "passage_rate": ("르파사쥬 독립 구매 비율", None), "fine_dwell": ("파인다이닝 식사시간 (분)", None), "moegi_seats": ("모에기 좌석", None), "turn_hold": ("회차제 좌석 회차 끝까지", 0), "rooms_onto": ("객실 수 · 온톨로지 (507 · 244 · 50)", 0),
         "search_w": ("월별 검색 관심 반영 (선호 가정)", 0), "posting_k": ("비투숙 피자힐 미식 게시 배수 가정", 0),
         "trend_w": ("SNS 신호 가중", 0), "seed": ("시드", 0),
         "anomaly": ("변칙 시나리오", 0), "anomaly_k": ("변칙 크기 배수", None), "hypo": ("가설", 0),
         "order_mix": ("투숙 · 비투숙 처리 순서 섞기", 0),
         "wd_dine": ("평일 저녁 호텔 식당 계획 비율 (투숙)", None), "wd_named": ("유명 업장은 평일에도 그대로", 0),
         "wd_day": ("평일 비투숙 손님 배율", None),
         "wd_biz": ("평일 비즈니스 · 접대 비투숙은 그대로", 0), "biz_party": ("평일 비즈니스 · 접대 일행 별실 규모", 0),
         "rooms_formula": ("객실 산식 · 건물별 목표 − 이월 (한호님 참고계수)", 0),
         "rng_team": ("손님마다 다른 난수 (팀 이름 기준)", 0),
         "buffet_seats": ("더뷔페 좌석", None),
         "meal_split": ("식당 외 식사 분리 (비투숙 호텔 밖 식사)", 0),
         "no_busy_dwell": ("붐빌 때 체류 단축 끄기", 0)}


def knob_suffix(theta: dict | None) -> str:
    th = {k: v for k, v in (theta or {}).items() if k in KNOBS and v != KNOBS[k][1]}
    if not th:
        return ""
    short = {"next_window": "nw", "wait_horizon": "wh", "takeout_base": "tb", "reserve_wait": "rw", "queue_max": "qm", "takeout_cap": "tc", "bar_nightcap": "bn", "purpose_onto": "po", "passage_rate": "pr", "fine_dwell": "fd", "moegi_seats": "ms", "turn_hold": "th", "rooms_onto": "ro", "search_w": "sw", "posting_k": "pk", "trend_w": "tw", "seed": "sd", "anomaly": "an", "anomaly_k": "ak", "hypo": "hy", "order_mix": "om", "wd_dine": "wd", "wd_named": "wn", "wd_day": "wy", "wd_biz": "wb", "biz_party": "bp", "rooms_formula": "rf", "rng_team": "rt", "buffet_seats": "bs", "meal_split": "mx", "no_busy_dwell": "nb"}
    return "_k" + "-".join(f"{short[k]}{th[k]:g}" for k in sorted(th))


def knob_label(theta: dict | None) -> str:
    th = {k: v for k, v in (theta or {}).items() if k in KNOBS and v != KNOBS[k][1]}
    flags = ("next_window", "reserve_wait", "purpose_onto", "turn_hold", "rooms_onto", "order_mix", "wd_named", "wd_biz", "biz_party", "rooms_formula")

    def one(k, v):
        if k == "no_busy_dwell":
            return KNOBS[k][0] + (" (중식 · 석식만)" if v == 2 else "")
        return KNOBS[k][0] if k in flags else f"{KNOBS[k][0]} {v:g}"
    return " · ".join(one(k, v) for k, v in sorted(th.items()))


# 평일 비즈니스 · 접대 비투숙 일행 분포 (△) — 명월관 별실 9실 80석 · 온달 별실 2~4 · 5~10 · 8~12인 · 더뷔페 별실 10~24석 (가정표 ◎) · 웨스틴조선 홍연 8인 이상 예약 +58% (아시아경제 2026-05-24)
BIZ_PARTY = "2:0.3/4:0.3/6:0.2/8:0.15/10:0.05"
def switch_summary(recs, meal_steps, team_party):
    """전환 집계 (10/14 · docs/행동근거_집계단위_20261013 정의)
    - events: 턴 수 (한 팀이 여러 번 셀 수 있다) · teams: 고유 팀 · persons: 그 팀들의 일행 수 합 (턴마다 더하지 않음)
    - '원래' 는 공급 제한(만석 · 대기)으로 빠진, 고른 곳보다 점수가 높았던 후보다. 자리가 있었으면 반드시 갔다는 뜻은 아니다
    - meal_outcome: 끼니 후보가 빠진 경우 같은 팀 · 날짜 · 끼니에 결국 무엇을 먹었는지 (팀 · 날짜 · 끼니마다 한 번)"""
    mk = agent_v4.meal_kind_at
    by_pair, by_from = {}, {}
    for r in recs:
        k = (r["원래"], r["대체"])
        x = by_pair.setdefault(k, {"from": r["원래"], "to": r["대체"], "events": 0, "ids": set()}); x["events"] += 1; x["ids"].add(r["id"])
        y = by_from.setdefault(r["원래"], {"from": r["원래"], "events": 0, "ids": set()}); y["events"] += 1; y["ids"].add(r["id"])
    out_pair = sorted(({"from": x["from"], "to": x["to"], "events": x["events"], "teams": len(x["ids"])} for x in by_pair.values()), key=lambda d: -d["events"])
    out_from = sorted(({"from": y["from"], "events": y["events"], "teams": len(y["ids"]), "persons": sum(team_party.get(i, 0) for i in y["ids"])} for y in by_from.values()), key=lambda d: -d["teams"])
    # 최종 끼니 결과
    cat = {}
    cases = {}
    for r in recs:
        if r["원래_키"] not in agent_v4.MEAL_KEYS or r["원래_키"] in ("lux", "lounge_h"):
            continue
        t = datetime.fromisoformat(r["시각"] or r["t_in"]); kind = mk(t)
        if not kind:
            continue
        ck = (r["id"], t.date().isoformat(), kind)
        if ck in cases:
            continue
        final = None
        for si, tin, key, label, venue in meal_steps.get(r["id"], []):
            ti = datetime.fromisoformat(tin)
            if si >= r["si"] and ti.date() == t.date() and mk(ti) == kind:
                final = (key, label, venue); break
        if final is None:
            c = "같은 끼니 식사 기록 없음"
        else:
            key, label, venue = final
            orig_venue = agent_v4.KEY_VENUE.get(r["원래_키"]) if hasattr(agent_v4, "KEY_VENUE") else None
            if key in ("pizza_to", "lepassage"):
                c = "포장"
            elif key == "meal_other":
                c = "호텔 밖 · 객실 식사"
            elif key == "meal_out":
                c = "호텔 밖 식사 (방문 종료)"
            elif key in ("lounge_b", "lounge_h"):
                c = "클럽 라운지 (포함)"
            elif r["원래"] and label and str(label).split()[0] == str(r["원래"]).split()[0]:
                c = "같은 업장 다른 회차"
            else:
                c = "다른 호텔 식당"
        cases[ck] = c
    for c in cases.values():
        cat[c] = cat.get(c, 0) + 1
    teams = {r["id"] for r in recs}
    return {"events": len(recs), "teams": len(teams), "persons": sum(team_party.get(i, 0) for i in teams),
            "by_pair": out_pair, "by_from": out_from,
            "meal_cases": len(cases), "meal_outcome": dict(sorted(cat.items(), key=lambda kv: -kv[1]))}


WEEKDAY_ONLY = ("wd_day", "wd_dine", "wd_named", "wd_biz", "biz_party")   # 평일에만 작동하는 조정값


def norm_theta(date_s: str, theta: dict | None) -> dict:
    """평일이 아닌 날(주말 · 공휴일)에는 평일 전용 조정값을 뺀다 — 10/14 v4 기본에 평일 비투숙 ×0.5 를 넣어도 주말 계산 키 · 시드 묶음이 그대로 맞도록"""
    th = dict(theta or {})
    if not agent_v4.is_weekday(datetime.strptime(date_s, "%Y-%m-%d").date()):
        for k in WEEKDAY_ONLY:
            th.pop(k, None)
    return th


def day_key(date_s: str, scenario: str, scale: float, theta: dict | None = None) -> str:
    return f"{date_s}_{scenario}_s{round(scale * 100)}" + knob_suffix(norm_theta(date_s, theta))


def day(date_s: str, scenario: str, scale: float, theta: dict | None = None):
    CACHE.mkdir(parents=True, exist_ok=True)
    theta = norm_theta(date_s, {k: v for k, v in (theta or {}).items() if k in KNOBS})
    agent_v4.THETA_FIT.update(theta)           # 이 프로세스에서만 (app 은 엔진을 매번 새로 띄운다)
    if theta.get("purpose_onto"):
        import os as _os
        _os.environ["WH_PURPOSE_MIX"] = "onto"   # generate.load_mix 가 '온톨로지 배분' 열을 쓴다
    if theta.get("rooms_formula"):
        import os as _os
        _os.environ["WH_ROOM_FORMULA"] = "1"   # generate.guests_for 가 건물별 목표 객실박 − 이월로 체크인 수를 정한다
    if theta.get("rooms_onto"):
        for _p, _n in (("GRAND", 507), ("VISTA", 244), ("DOUGLAS", 50)):
            prices.ROOMS[_p]["n"] = _n           # generate · revenue 가 같은 dict 를 본다
    if theta.get("rng_team"):
        revenue.RNG_TEAM = True                 # 10/14 손님마다 다른 난수 (팀 이름 기준) — 리뷰 피드백: 같은 시드 비교가 같은 조건인지
    if theta.get("seed"):
        # 10/14 시드 묶음 — 손님 생성(generate.SEED) · 에이전트 선택 · 상품 추첨(revenue.SEED)을 같이 옮긴다. 0 이면 전과 같다
        G.SEED = 20261001 + int(theta["seed"])
        revenue.SEED = 20260930 + int(theta["seed"])
    # Reset our opt-in controls on each call, including when switched back off.
    import os as _os
    _os.environ["WH_SEARCH_WEIGHT"] = str(theta.get("search_w") or 0)
    if theta.get("posting_k"):
        _os.environ["WH_POSTING_K"] = str(theta["posting_k"])
    else:
        _os.environ.pop("WH_POSTING_K", None)
    if theta.get("trend_w"):
        import os as _os
        _os.environ["WH_TREND"] = str(float(theta["trend_w"]))   # generate.load_dining 이 SNS 신호 쪽으로 기운다 (trend.py)
    key = day_key(date_s, scenario, scale, theta)
    f = lambda ext: CACHE / (key + ext)
    prog = f(".progress.json")

    def progress(done, total, phase):
        prog.write_text(json.dumps({"done": done, "total": total, "phase": phase}), encoding="utf-8")

    progress(0, 0, "손님 만드는 중")
    apply_scenario(scenario, date_s)
    grid, factors = G.load_grid(), G.load_factors()
    day_config = G.load_day_scenarios()
    pmix = G.load_mix(TL / "purpose_mix.csv")
    amix = G.load_mix(TL / "age_mix.csv", key="연령")
    tmix = G.load_type_mix()
    anomaly = apply_anomaly(int(theta["anomaly"]), float(theta.get("anomaly_k") or 1.0), date_s, factors, day_config) if theta.get("anomaly") else None
    hypo = apply_anomaly(int(theta["hypo"]), 1.0, date_s, factors, day_config, table="hypotheses.csv") if theta.get("hypo") else None
    # 10/14 가설 H4 — 평일 비투숙 손님 규모 배율 (wd_day). 비투숙 기본 311팀은 주말(10/10)에서 역산한 값이라 평일에도 객실 비율만큼만 줄어든다
    # 10/14 가설 H5 — wd_biz: 비즈니스 · 접대 비투숙은 평일 배율에서 뺀다 (온톨로지 날짜 배율은 비즈니스가 평일에 더 높다) · biz_party: 그 일행을 별실 규모로
    _wd_env = {}
    if agent_v4.is_weekday(datetime.strptime(date_s, "%Y-%m-%d").date()):
        if theta.get("wd_biz") and theta.get("wd_day") is not None:
            _wd_env.update(thin=float(theta["wd_day"]), exempt=["비즈니스·접대"])      # 팀 수는 generate 가 목적별로 줄인다
        elif theta.get("wd_day") is not None:
            _b = day_config["scenarios"]["base"]
            day_config["scenarios"]["base"] = int(round(_b * float(theta["wd_day"])))
        if theta.get("biz_party"):
            _wd_env["party"] = {"비즈니스·접대": BIZ_PARTY}
    if _wd_env:
        import os as _os
        _os.environ["WH_WD"] = json.dumps(_wd_env, ensure_ascii=False)
    from capacity import Capacity
    cap = Capacity()
    # 10/13 실험 조정값 moegi_seats — 온톨로지는 모에기 공식 103석 중 다이닝 홀 40석만 쓴다 (스시바 · 데판 · 별실 제외). 기본 없음 (103)
    if theta.get("moegi_seats") and "모에기" in cap.cap:
        cap.cap["모에기"] = int(theta["moegi_seats"])
    # 10/14 운영 조건 비교 (A/B) — 더뷔페 좌석. 기본 없음 (홀 288석). 예: 338 = 테라스 50석을 식사에 쓰는 경우 (prices.SEATS 출처: 테라스 50석은 소규모 연회)
    if theta.get("buffet_seats") and "더뷔페" in cap.cap:
        cap.cap["더뷔페"] = int(theta["buffet_seats"])
    cap.prune(datetime.strptime(date_s, "%Y-%m-%d"))
    with contextlib.redirect_stdout(io.StringIO()):
        stays = G.guests_for(date_s, grid, factors, scale=scale, purpose_mix=pmix, type_mix=tmix, carry={},
                             day_parties=None, day_scenario="base", day_config=day_config, age_mix=amix)
    # 10/14 조정값 order_mix — 생성기는 투숙 팀을 모두 먼저, 비투숙 팀을 뒤에 둔다. 좌석은 먼저 돈 손님이 잡으므로 비투숙 손님은 늘 남은 자리만 본다.
    # 켜면 그 날 손님 순서를 시드 고정으로 섞는다 (예약 시점이 섞여 있다는 중립 가정). 기본 꺼짐 — 전과 같다
    if theta.get("order_mix"):
        stays = list(stays)
        random.Random(G.SEED + 7).shuffle(stays)
    catch = Catch()
    n = len(stays)
    guests = []
    t0 = _time.time()
    detail_path = f(".guests.jsonl")
    with detail_path.open("w", encoding="utf-8") as fd:
        offsets = []
        for i, (gid, label, m) in enumerate(stays):
            p = m.PERSONA
            lines = revenue.spend_lines(m, k=1, capacity=cap)
            segs, traces = catch.last
            det = detail_json(p, m.START_AT, segs, traces, lines)
            det["id"] = gid
            offsets.append(fd.tell())
            fd.write(json.dumps(det, ensure_ascii=False) + "\n")
            guests.append({
                "id": gid, "is_guest": p.is_guest, "property": p.property, "party": p.party_size, "kids": p.has_child_under_13,
                "age": p.age_band, "purpose": p.purpose, "nights": p.nights, "package": p.package,
                "fair": FAIR_SPOT in p.booked, "wf_ext": "와인페어 #" in p.name,
                "spend": det["spend_total"], "n_switch": sum(1 for s in det["steps"] if s["switch"]),
                "path": [(s["location"], s["t_in"], s["t_out"]) for s in det["segments"]],
                "acts": [s["label"] for s in det["steps"] if s["kind"] not in ("checkin",)][:14],
            })
            if i % 10 == 0 or i == n - 1:
                el = _time.time() - t0
                progress(i + 1, n, f"손님 돌리는 중 · 남은 시간 약 {el / (i + 1) * (n - i - 1):.0f}초")
    # 좌석표 · 업장별 인원 (10분 칸 · 그 날 10:00 ~ 다음날 13:00 — 그 날 체크인 손님의 다음날 조식 · 체크아웃까지)
    d0 = datetime.strptime(date_s, "%Y-%m-%d").replace(hour=10)
    slots = [d0 + timedelta(minutes=10 * k) for k in range(6 * 27)]
    seats = {}
    for venue, booked in cap.booked.items():
        if venue not in SEAT_LOC:
            continue
        seats[SEAT_LOC[venue]] = {"name": venue, "cap": cap.cap[venue],
                                  "load": [sum(nn for a, b, nn in booked if a <= t < b) for t in slots]}
    present = defaultdict(lambda: [0] * len(slots))
    for g in guests:
        for loc, a, b in g["path"]:
            ta, tb = datetime.fromisoformat(a), datetime.fromisoformat(b)
            for k, t in enumerate(slots):
                if ta <= t < tb:
                    present[loc][k] += g["party"]
    summary = cap.summary(datetime.strptime(date_s, "%Y-%m-%d").date())
    by_l2 = defaultdict(float)
    by_l3 = defaultdict(float)
    # 업장별 — 회차 · L4 상품 · L5 집계행 · 수용 범위 초과 수요 (사람 단위)
    day0 = datetime.strptime(date_s, "%Y-%m-%d").date()
    vd = {}
    for name, loc in SEAT_LOC.items():
        wins = venue_windows(loc, day0) + [dict(w, name=w["name"] + " (익일)")
                                           for w in venue_windows(loc, day0 + timedelta(days=1)) if w["t0"].hour < 13 or w["kind"] == "조식"]
        vd[loc] = {"name": name, "cap": cap.cap.get(name, 0), "turns": prices.SEATS.get(name, {}).get("turns", 1),
                   "windows": [dict(w, adults=0, kids=0, parties=0, takeout=0, over_ids=set(), over_persons=0, peak=0) for w in wins],
                   "l4": defaultdict(lambda: [0, 0.0]), "l4_day": defaultdict(int), "l5": defaultdict(lambda: [0, 0, 0.0]), "l5_ids": defaultdict(set),
                   "teams": {}, "guest_ids": set(), "over_ids": set(), "over_persons": 0}
    label2loc = {"더뷔페 조식": "THE_BUFFET", "더뷔페 중식": "THE_BUFFET", "더뷔페 석식": "THE_BUFFET", "피자힐": "PIZZA_HILL", "피자힐 포장": "PIZZA_HILL",
                 "금룡": "GEUMRYONG", "명월관": "MYONGWOLGWAN", "모에기": "MOEGI", "온달": "ONDAL", "더 파빌리온": "THE_PAVILION", "LUX BAR": "LUX_BAR", "르파사쥬 포장": "LE_PASSAGE"}
    room_extra = 0.0
    # 10/14 집계 단위 정리 (docs/행동근거_집계단위_20261013) — 턴 수 · 고유 팀 · 팀 기반 인원 · 최종 끼니 결과를 나눠 센다
    by_l2_day = defaultdict(float)          # 그 날(date_s) 일어난 지출만 — 그 날 들어온 손님 몫 (전날 들어온 손님의 오늘 지출은 없다)
    sw_recs = []                            # 전환 한 건 = 공급 제한으로 빠진 더 높은 점수의 후보가 있었던 턴
    meal_steps = defaultdict(list)          # 손님별 식음 행동 (최종 끼니 결과 연결용)
    team_party = {}
    with detail_path.open(encoding="utf-8") as fd:
        for line in fd:
            det = json.loads(line)
            pp = det["persona"]
            kids_n = 1 if pp["kids"] else 0
            seen_over = set()
            team_party[det["id"]] = pp["party"]
            for si, s in enumerate(det["steps"]):
                if s.get("key") in agent_v4.MEAL_KEYS:
                    meal_steps[det["id"]].append((si, s["t_in"], s.get("key"), s.get("label"), s.get("venue") or s.get("location")))
                if (s.get("switch") or {}).get("원래"):
                    sw_recs.append(dict(id=det["id"], party=pp["party"], si=si, t_in=s["t_in"], **{k: s["switch"].get(k) for k in ("원래", "원래_키", "대체", "대체_키", "사유", "시각")}))
                for sp in s["spend"]:
                    by_l2[sp["l2"]] += sp["krw"]
                    by_l3[sp["l3"]] += sp["krw"]
                    if s["t_in"][:10] == date_s:
                        q = sp.get("qty", 1) or 1
                        by_l2_day[sp["l2"]] += sp["krw"] / q if (sp["l2"] == "ROOM" and sp["l3"] in ("그랜드", "비스타", "더글라스") and q > 1) else sp["krw"]
                    # 온톨로지 대조용 — 객실은 첫 밤만 (온톨로지는 하루 객실박, 하루 전체는 체크인 날에 박수 전부를 적는다)
                    if sp["l2"] == "ROOM" and sp["l3"] in ("그랜드", "비스타", "더글라스") and sp.get("qty", 1) > 1:
                        room_extra += sp["krw"] * (1 - 1 / sp["qty"])
                loc = s.get("venue") if s.get("venue") in vd else (s.get("location") if s.get("location") in vd else None)
                if loc and s["kind"] != "checkin":
                    t = datetime.fromisoformat(s["t_in"])
                    v = vd[loc]
                    v["guest_ids"].add(det["id"])
                    v["teams"][det["id"]] = (pp["purpose"] or "미설정", pp["age"] or "미설정", "투숙" if pp["is_guest"] else "비투숙", pp.get("sex") or "미설정")
                    for w in v["windows"]:
                        if w["t0"] <= t < w["t1"]:
                            if s.get("state") == "TAKEOUT_ORDER":
                                w["takeout"] += pp["party"]
                            else:
                                w["adults"] += pp["party"] - kids_n; w["kids"] += kids_n; w["parties"] += 1
                            break
                    for sp in s["spend"]:
                        if sp["l3"] == v["name"]:
                            v["l4"][sp["product"]][0] += sp["qty"]; v["l4"][sp["product"]][1] += sp["krw"]
                            if s["t_in"][:10] == date_s:
                                v["l4_day"][sp["product"]] += sp["qty"]          # 그 날 하루치 (온톨로지 하루 풀과 대조용)
                            k5 = (pp["purpose"] or "미설정", pp["age"] or "미설정", pp.get("ai_type") or "미설정", "투숙" if pp["is_guest"] else "비투숙", pp.get("sex") or "미설정")
                            v["l5"][k5][0] += 1; v["l5"][k5][1] += sp["qty"]; v["l5"][k5][2] += sp["krw"]; v["l5_ids"][k5].add(det["id"])
                sw = s.get("switch") or {}
                if sw.get("원래") in label2loc:
                    oloc = label2loc[sw["원래"]]
                    if oloc in vd and (det["id"], oloc) not in seen_over:
                        seen_over.add((det["id"], oloc))
                        v = vd[oloc]
                        v["over_ids"].add(det["id"]); v["over_persons"] += pp["party"]
                        t = datetime.fromisoformat(sw["시각"]) if sw.get("시각") else datetime.fromisoformat(s["t_in"])
                        for w in v["windows"]:
                            if w["t0"] <= t < w["t1"]:
                                w["over_ids"].add(det["id"]); w["over_persons"] += pp["party"]
                                break
    venue_detail = {}
    for loc, v in vd.items():
        name = v["name"]
        booked = cap.booked.get(name, [])
        wins = []
        for w in v["windows"]:
            pts = [w["t0"]] + [a for a, b, nn in booked if w["t0"] < a < w["t1"]]
            peak = max((sum(nn for a, b, nn in booked if a <= t < b) for t in pts), default=0)
            persons = w["adults"] + w["kids"]
            wins.append({"name": w["name"], "kind": w["kind"], "t0": w["t0"].strftime("%m/%d %H:%M"), "t1": w["t1"].strftime("%H:%M"),
                         "parties": w["parties"], "persons": persons, "adults": w["adults"], "kids": w["kids"], "takeout": w["takeout"],
                         "occ_pct": round(persons / v["cap"] * 100) if v["cap"] else None, "peak_pct": round(peak / v["cap"] * 100) if v["cap"] else None,
                         "over_persons": w["over_persons"], "over_parties": len(w["over_ids"])})
        same = [w for w in wins if "익일" not in w["name"]]
        venue_detail[loc] = {"name": name, "cap": v["cap"], "turns": v["turns"], "windows": wins,
                             "persons_day": sum(w["persons"] for w in same), "takeout_day": sum(w["takeout"] for w in same),
                             "peak_day": max([w["peak_pct"] or 0 for w in same], default=0),
                             "peak_window": max(same, key=lambda w: w["peak_pct"] or 0)["name"] if same else "",
                             "parties": len(v["guest_ids"]), "over_persons": v["over_persons"], "over_parties": len(v["over_ids"]),
                             "krw": by_l3.get(name, 0.0),
                             "l4": [{"product": k, "qty": q, "krw": kw} for k, (q, kw) in sorted(v["l4"].items(), key=lambda kv: -kv[1][1])[:12]],
                             # parties = 고유 팀 (10/14 — 전에는 구매 줄 수였다) · lines = 구매 줄 수
                             "l5": [{"purpose": k[0], "age": k[1], "ai_type": k[2], "guest": k[3], "parties": len(v["l5_ids"][k]), "lines": c, "qty": q, "krw": kw}
                                    for k, (c, q, kw) in sorted(v["l5"].items(), key=lambda kv: -kv[1][2])[:10]],
                             # 온톨로지 대조용 — 전체 집계 (목적별 팀 수 · 상품별 수량)
                             # 팀 비중 = 이 업장을 이용한 고유 팀 (10/14 — 전에는 구매 줄 수). 구매 줄 비중은 *_lines
                             "by_purpose": _count(v["teams"], 0), "by_age": _count(v["teams"], 1), "by_guest": _count(v["teams"], 2), "by_sex": _count(v["teams"], 3),
                             "by_purpose_lines": _sum_by(v["l5"], 0, 0), "by_guest_lines": _sum_by(v["l5"], 3, 0),
                             "l4_qty": {k: q for k, (q, kw) in v["l4"].items()}, "l4_qty_day": dict(v["l4_day"])}
    switches = defaultdict(int)
    for r in agent_v4.SWITCH_LOG:
        switches[(r["원래"], r["대체"])] += 1
    switch = switch_summary(sw_recs, meal_steps, team_party)
    res = {
        "key": key, "date": date_s, "scenario": scenario, "scale": scale, "theta": theta, "knobs": knob_label(theta), "built": datetime.now().isoformat(timespec="seconds"),
        "model_ver": _version.model_ver(), "input_ver": _version.input_ver(),     # 10/14 — 같은 키라도 코드 · 입력이 바뀌면 다른 결과
        "n": n, "n_guest": sum(1 for g in guests if g["is_guest"]), "persons": sum(g["party"] for g in guests),
        "total": sum(by_l2.values()), "by_l2": by_l2, "room_extra_nights": room_extra, "room_nights": sum(g["nights"] for g in guests if g["is_guest"]), "by_l3": dict(sorted(by_l3.items(), key=lambda kv: -kv[1])),
        "slots": [t.strftime("%H:%M") for t in slots], "slot0": slots[0].isoformat(timespec="minutes"), "seats": seats, "present": present,
        "venues": [{"name": v, "cap": c, "seated": s_, "away": a_, "wait_min": round(w_)} for v, c, s_, a_, w_ in summary],
        # n = 전환 건수(턴), teams = 고유 팀 (10/14)
        "switches": [dict(x, n=x["events"]) for x in switch["by_pair"][:20]], "switch": switch,
        "total_day": sum(by_l2_day.values()), "by_l2_day": dict(by_l2_day),
        "n_switch": len(agent_v4.SWITCH_LOG), "n_switch_teams": switch["teams"], "venue_detail": venue_detail, "trend": trend_report(theta), "anomaly": anomaly, "hypo": hypo,
        "total_net": sum(by_l2.values()) / 1.1,
        "guests": [{k: v for k, v in g.items() if k != "path"} for g in guests],
        "offsets": offsets,
    }
    f(".json").write_text(json.dumps(res, ensure_ascii=False, default=str), encoding="utf-8")
    pickle.dump(cap, f(".cap.pkl").open("wb"))
    progress(n, n, "끝")


def day_guest(key: str, idx: int):
    meta = json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8"))
    with (CACHE / f"{key}.guests.jsonl").open(encoding="utf-8") as fd:
        fd.seek(meta["offsets"][idx])
        det = json.loads(fd.readline())
    det["crowd_note"] = f"그 날 손님 {meta['n']}팀 중 하나 ({key})"
    det["scenario"] = meta["scenario"]
    return det


L5_COLS = ["구매 날짜", "L1", "L2 부문", "L3 업장", "L4 상품", "성별", "대표자 연령", "구성·방문 목적", "AI 유형", "투숙", "행사", "수량", "결제액", "순매출"]


def l5_export(key: str):
    """하루 캐시 → 온톨로지 집계행과 같은 열의 CSV 글. 한 줄 = (날짜 · 업장 · 상품 · 성별 · 연령 · 목적 · AI 유형 · 투숙) 묶음의 수량 · 결제액 · 순매출(결제액/1.1)"""
    meta = json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8"))
    agg = defaultdict(lambda: [0, 0.0])
    with (CACHE / f"{key}.guests.jsonl").open(encoding="utf-8") as fd:
        for line in fd:
            det = json.loads(line); pp = det["persona"]
            for st in det["steps"]:
                for sp in st["spend"]:
                    day = st["t_in"][:10]
                    k = (day, sp["l2"], sp["l3"], sp["product"], pp.get("sex") or "미설정", pp.get("age") or "미설정", pp.get("purpose") or "미설정",
                         pp.get("ai_type") or "미설정", "투숙" if pp["is_guest"] else "비투숙")
                    agg[k][0] += sp["qty"]; agg[k][1] += sp["krw"]
    fair = "와인페어 있음" if meta["scenario"] == "winefair" else "행사 없음"
    out = io.StringIO(); w = csv.writer(out); w.writerow(L5_COLS)
    for k, (q, krw) in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], -kv[1][1])):
        w.writerow([k[0], "전체", {"ROOM": "ROOM", "F&B": "F&B", "레저": "LEISURE"}.get(k[1], k[1]), k[2], k[3], k[4], k[5], k[6], k[7], k[8], fair, q, round(krw), round(krw / 1.1)])
    return out.getvalue()


def _grid_weights():
    grid = G.load_grid()
    pmix = G.load_mix(TL / "purpose_mix.csv"); amix = G.load_mix(TL / "age_mix.csv", key="연령")
    gp, ga = defaultdict(float), defaultdict(float)
    for r in grid:
        gp[r["목적"]] += r["비중"]; ga[r["연령"]] += r["비중"]
    w = [(r["비중"] * pmix.get(r["목적"], 0) / gp[r["목적"]] * amix.get(r["연령"], 0) / ga[r["연령"]])
         if (r["목적"] != "공항 이동·여행" and gp[r["목적"]] > 0 and ga[r["연령"]] > 0) else 0.0 for r in grid]
    return grid, w


def grid_rows():
    """10/16 화면 '고객 유형표에서 선택' — 유형표 줄 전체 (한 줄은 개인이 아니라 고객군 정의). 근거 문장의 주소는 화면에 안 보낸다"""
    grid, w = _grid_weights()
    tot = sum(w) or 1.0
    out = []
    for i, (r, wi) in enumerate(zip(grid, w)):
        src = re.sub(r"https?://\S+", "", r["근거"]).split(";")[0].strip()
        out.append({"i": i, "sex": r["성별"], "age": r["연령"], "purpose": r["목적"], "party": r["인원수"], "kids": r["아동동반"],
                    "nights": r["박수"], "share": round(wi / tot, 6), "src": src[:60]})
    return out


def random_profile(seed=None, row=None):
    """고객 유형표에서 한 줄 — generate.py 와 같은 가중 (목적 · 연령 섞기). row 를 주면 그 줄에서 (인원 · 박수 · 아동은 시드로 뽑음)"""
    rng = random.Random(seed)
    grid, w = _grid_weights()
    if row is not None:
        r = grid[int(row)]
    else:
        r = rng.choices(grid, weights=w)[0]
    party = G.pick_dist(r["인원수"], rng)
    nights = G.pick_dist(r["박수"], rng)
    kid = rng.random() < r["아동동반"] and party >= 2
    return {"sex": r["성별"], "age": r["연령"], "purpose": r["목적"], "party": party, "kids": kid,
            "is_guest": nights > 0, "nights": max(1, nights), "row": re.sub(r"https?://\S+", "", r["근거"])[:160],
            "row_i": grid.index(r), "seed": seed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["library", "packages", "guest", "review", "day", "day_guest", "random", "onto_export", "l5_export"])
    ap.add_argument("--date"); ap.add_argument("--scenario", default="none"); ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out"); ap.add_argument("--key"); ap.add_argument("--idx", type=int); ap.add_argument("--seed", type=int)
    ap.add_argument("--row", type=int)
    ap.add_argument("--theta", default="{}", help='시나리오 조정값 JSON, 예: {"next_window":1,"wait_horizon":300,"takeout_base":-2.5}')
    a = ap.parse_args()
    real_out = sys.stdout
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):       # 모델이 찍는 글은 버린다 — 표준 출력엔 JSON 하나만
        if a.cmd == "library":
            res = library()
        elif a.cmd == "packages":
            res = packages(json.loads(sys.stdin.read() or "{}"))
        elif a.cmd == "guest":
            res = guest(json.loads(sys.stdin.read() or "{}"))
        elif a.cmd == "review":
            res = review_guest(json.loads(sys.stdin.read() or "{}"))
        elif a.cmd == "day":
            th = json.loads(a.theta or "{}")
            day(a.date, a.scenario, a.scale, th); res = {"ok": True, "key": day_key(a.date, a.scenario, a.scale, th)}
        elif a.cmd == "day_guest":
            res = day_guest(a.key, a.idx)
        elif a.cmd == "l5_export":
            txt = l5_export(a.key)
            p = Path(a.out) if a.out else (CACHE / f"{a.key}.l5.csv")
            p.write_text("\ufeff" + txt, encoding="utf-8")
            res = {"ok": True, "out": str(p), "rows": txt.count("\n") - 1}
        elif a.cmd == "onto_export":
            # 원본 폴더(walkerhill_oct_base) → 저장소용 비율 · 개수 파일. 금액은 넘기지 않는다
            o = ontology_oct()
            if not o["src"] or "원본" not in o["src"]:
                res = {"ok": False, "why": "walkerhill_oct_base 폴더를 못 찾음 (WH_ONTO_DIR 또는 저장소 옆)"}
            else:
                keep = {k: o[k] for k in ("daily", "ga", "presets", "pool_def", "sweeps", "knob_defs", "pool_mix") if k in o}
                (TL / "ontology_oct_daily.json").write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
                res = {"ok": True, "days": len(o["daily"]), "venues_ga": len(o["ga"]), "out": str(TL / "ontology_oct_daily.json")}
        else:
            res = random_profile(a.seed, a.row)
    real_out.write(json.dumps(res, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
