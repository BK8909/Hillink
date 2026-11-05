#!/usr/bin/env python3
"""CL-37 L5 소비 원장 변환 레이어 — 11명 페르소나 엔진(autonomy_v1) 장면 지출 → 기존 L5 구매 행 → L4 · L3 · L2 · L1 집계.

원칙(2026-10-26 강경수 결정)
  · 엔진 · 가격 · 고객 행동은 바꾸지 않는다. 엔진 출력(장면 charge · 턴 결정 price)을 읽어 옮기기만 한다.
  · 상태 4종 + 객실을 구분한다: 실결제 · 무료 · 포함 · 금액 미확인(가격 미정 · 객실). 구매 없음 장면은 원장 행에 넣지 않고 수만 센다.
  · 객실 요금: 확인된 투숙 조건과 맞는 실결제 근거가 없으면 확정 금액을 넣지 않는다 → '금액 미확인' 행 + 가정값 칸(확정 합계 제외).
    가정값은 기존 온톨로지 파이프라인(prices.py room:*)과 같은 '패키지' 기준이며, 엔진이 조식을 '포함'으로 계산한 날은 조식 포함 패키지로 맞춰
    포함 혜택(조식)과 객실료가 이중으로 잡히지 않게 한다(포함 끼니는 0원 · 객실 가정값에만 들어 있음).
  · 11명 엔진 결과만 다룬다. 기존 온톨로지 모집단(revenue_l5.csv · 생성기)과 합치지 않는다 — 비교는 단가 대조 표로만.
  · 기존 L5 열(engine.L5_COLS)은 그대로 쓰고, 원장 전용 열을 뒤에 덧붙인다.

사용
  python3 ledger_l5.py --out DIR            # 저장본(고객이 정한 조건 × 행사 0/1) 하루 원장 + 체류 전체(같은 조건 · 단계별 실시간 계산) 원장 · 집계 · 검증
"""
from __future__ import annotations

import argparse, csv, json, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
FIX = HERE / "static" / "demo_story" / "flow_fixture_v1.json"
FLOW = [sys.executable, str(HERE / "flow_run.py")]
VAT = 1.1
NOMINAL_DATE = "2026-10-24"   # 표기용 가상일(엔진은 날짜를 받지 않음 · 요일 가격 미적용)

L5_COLS = ["구매 날짜", "L1", "L2 부문", "L3 업장", "L4 상품", "성별", "대표자 연령", "구성·방문 목적", "AI 유형", "투숙", "행사", "수량", "결제액", "순매출"]   # viewer/engine.py 와 같은 열
EXTRA = ["고객", "내부 ID", "원장 범위", "체류 단계", "체류 일차", "시각", "장면", "상태", "단가", "과금 단위", "확정 결제액", "가정 결제액", "가격 등급",
         "가격 근거", "엔진 결정", "상품 ID", "라이브러리 유형", "확인 메모"]

# ── 장면 위치 → (L2, L3) — prices.py · 온톨로지 업장 이름(구조만)
LOC_L23 = {
    "THE_BUFFET": ("F&B", "더뷔페"), "PIZZA_HILL": ("F&B", "피자힐"), "MYONGWOLGWAN": ("F&B", "명월관"), "ONDAL": ("F&B", "온달"),
    "GEUMRYONG": ("F&B", "금룡"), "MOEGI": ("F&B", "모에기"), "THE_PAVILION": ("F&B", "파빌리온"), "LE_PASSAGE": ("F&B", "르파사쥬"),
    "LUX_BAR": ("ROOM", "럭스바"), "SKYARD": ("레저", "스카이야드"), "GRAND_POOL": ("레저", "수영장"), "VISTA_POOL": ("레저", "수영장"),
    "WELLNESS_SAUNA": ("레저", "웰니스 사우나"), "THEATRE_OF_LIGHT": ("레저", "빛의 시어터"), "RIVERPARK": ("레저", "리버파크"),
}
ROOM_L3 = {"GRAND": "그랜드", "VISTA": "비스타", "DOUGLAS": "더글라스"}
UNMAPPED_L3 = {"GRAND_LIBRARY": "라이브러리(투숙객 무료 · 온톨로지 업장 없음)", "AG_GARDEN": "더글라스 가든(무료 산책)", "FITNESS": "피트니스(투숙객 무료 · 온톨로지 업장 없음)"}

# ── 라이브러리 유형 → 온톨로지 목적(9) — 이름이 같은 뜻일 때만 대응 · 나머지는 '미대응'으로 남김(확대 단계에서 결정)
TYPE_PURPOSE = {"커플 · 기념일": "커플·기념일", "가족 · 영유아": "가족·친족", "가족 · 부모 동반": "가족·친족", "혼자 휴식": "혼자 휴식",
                "친구 모임": "친구·모임", "업무 · 출장": "비즈니스·접대", "미식": "미식 방문", "스포츠 목적": "골프·스포츠 모임"}
TYPE_FIX = {"blog41": "커플 · 기념일", "blog43": "혼자 휴식", "blog42": None}   # library.js LIB_TYPE_FIX 와 같은 표시 유형

# ── 객실 가정값 — menu.csv 공식 패키지(◎) · 기존 파이프라인 prices.py room:* 와 같은 패키지 기준. (건물, 조식 포함 여부, 1인 여부) → 상품명
ROOM_ASSUME = {
    ("GRAND", False, False): "캠크닉 인더 포레스트 TYPE 1", ("GRAND", True, False): "캠크닉 인더 포레스트 TYPE 2",
    ("VISTA", False, False): "[가을] 어텀 캠크닉 TYPE 1", ("VISTA", True, False): "[가을] 어텀 캠크닉 TYPE 2",
    ("DOUGLAS", False, False): "Rest Together · 2인", ("DOUGLAS", True, False): "Rest Together · 2인",
    ("DOUGLAS", False, True): "[1인] 나홀로 쉼 · 1박", ("DOUGLAS", True, True): "[1인] 나홀로 쉼 · 1박",
}
ROOM_ASSUME_CLUB = {"GRAND": "캠크닉 인더 포레스트 TYPE 3"}   # 클럽 스위트 + 클럽 라운지(조식 포함)


def load_menu():
    rows = list(csv.DictReader((TL / "menu.csv").open(encoding="utf-8-sig")))
    return {(r["업장"], r["상품"]): r for r in rows}


def load_types():
    lib = {p["id"]: p for p in json.loads((HERE / "static" / "persona_library.json").read_text(encoding="utf-8"))["personas"]}
    out = {}
    for pid, p in lib.items():
        out[pid] = TYPE_FIX[pid] if pid in TYPE_FIX else p.get("type_group")
    return out


def display_no():
    t = (HERE / "static" / "display_registry.js").read_text(encoding="utf-8")
    E = json.loads(t[t.index("{"): t.rindex("}") + 1])["entries"]
    return {k: "No." + v["no"] for k, v in E.items()}


def run_flow(pid, event, vo=None):
    q = {"personas": [pid], "mode": "one", "visit_override": vo, "event": bool(event), "intervention": "none", "product_levers": {}, "observe": "day", "seed": 0}
    r = subprocess.run(FLOW, input=json.dumps(q, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8", cwd=HERE, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"flow_run 실패 {pid}: {r.stderr.strip()[-300:]}")
    return json.loads(r.stdout)


def fixture_entries():
    f = json.loads(FIX.read_text(encoding="utf-8"))
    for k, e in f["entries"].items():
        kk = json.loads(k)
        if kk["mode"] == "one":
            yield kk["personas"][0], int(bool(kk["event"])), e


QTY_RE = re.compile(r"([0-9][0-9,]*)원\s*×\s*([0-9]+)\s*(인|명|객실)")


def turn_choices(e, pid):
    """턴 결정(정량 엔진) — turn → choice(product_id · price) · 장면 금액 독립 대조용"""
    out = {}
    for R in e.get("runs") or []:
        for c in R.get("customers") or []:
            if c.get("persona_id") == pid and c.get("choice"):
                out[R.get("turn")] = c["choice"]
    return out


def day_rows(pid, event, e, scope, day_idx, meta):
    """한 하루(plan) → 원장 행 · 장면 수 · 대조 결과"""
    pl = e["plans"][pid]; v = e["visits"][pid]
    party = int(v.get("party_size") or 1); stay = bool(v.get("stay")); phase = v.get("phase") or ("visit" if not stay else "mid")
    ty = meta["types"].get(pid); purpose = TYPE_PURPOSE.get(ty or "", None)
    base = {"구매 날짜": NOMINAL_DATE, "L1": "전체", "성별": "미설정", "대표자 연령": "미설정",
            "구성·방문 목적": purpose or f"미대응({ty or '유형 확인 중'})", "AI 유형": "미설정", "투숙": "투숙" if stay else "비투숙",
            "행사": "와인페어 있음" if event else "행사 없음", "고객": meta["no"].get(pid, pid), "내부 ID": pid, "원장 범위": scope,
            "체류 단계": {"checkin": "체크인 당일", "mid": "연박 중간일", "checkout": "체크아웃 당일", "visit": "비투숙 당일"}.get(phase, phase),
            "체류 일차": day_idx, "라이브러리 유형": ty or "유형 확인 중"}
    rows, notes, cnt = [], [], defaultdict(int)
    turns = turn_choices(e, pid)
    bf_included = False
    seen_fac = defaultdict(int)
    for sc in pl.get("scenes") or []:
        ch = (sc.get("basis") or {}).get("charge") or {}
        st = ch.get("status")
        if st in (None, "구매 없음"):
            cnt["구매 없음"] += 1; continue
        loc, act = sc.get("loc"), sc.get("act") or ""
        if loc in LOC_L23: l2, l3 = LOC_L23[loc]
        elif loc == "FOREST_PARK": l2, l3 = ("레저", "와인페어") if act == "turn_event" else ("레저", "포레스트 파크")
        elif loc and loc.endswith("_ROOM"): l2, l3 = ("ROOM", "IRD")   # 객실에서 먹는 룸서비스
        else: l2, l3 = ("미매핑", UNMAPPED_L3.get(loc, loc or "?"))
        krw = ch.get("krw"); per = ch.get("per"); basis = ch.get("basis") or ""
        m = QTY_RE.search(basis)
        unit = int(m.group(1).replace(",", "")) if m else (krw if krw is not None else None)
        qty = int(m.group(2)) if m else (party if sc.get("meal") else 1)   # 금액 문구에 인원이 없는 끼니(포함 조식 등)는 일행 전원
        unit_kind = {"인": "1인", "명": "1인", "객실": "객실당"}.get(m.group(3), per) if m else ({"객실": "객실당", "인": "1인"}.get(per, "1인" if sc.get("meal") else "건"))
        status = {"유료": "실결제", "무료": "무료", "포함": "포함", "가격 미정": "금액 미확인"}.get(st, st)
        memo = []
        tchoice = turns.get(sc.get("turn")) if sc.get("turn") else None
        if tchoice:   # 독립 대조: 엔진 결정 1인가 × 인원 = 장면 금액
            pr = tchoice.get("price") or {}
            if status == "실결제":
                exp = (pr.get("paid_krw") or 0) * (qty if m else party)
                if krw != exp: memo.append(f"엔진 결정가 대조 불일치({exp:,})")
            if status == "포함" and not pr.get("in_package"): memo.append("엔진 결정은 포함 아님")
        if status == "포함" and sc.get("meal") == "breakfast": bf_included = True
        if per == "객실" and status == "실결제":
            seen_fac[loc] += 1
            if seen_fac[loc] > 1: memo.append("같은 날 같은 시설 객실당 요금 재부과(1일 1회 규칙 미확인)")
        if status == "실결제" and m and unit * qty != krw: memo.append("단가×수량 ≠ 금액")
        paid = krw if status == "실결제" else 0
        rows.append(dict(base, **{"L2 부문": l2, "L3 업장": l3, "L4 상품": sc.get("label") or act, "수량": qty,
                                   "결제액": paid, "순매출": round(paid / VAT), "시각": f"{sc['t0'] // 60:02d}:{sc['t0'] % 60:02d}",
                                   "장면": act, "상태": status, "단가": unit if unit is not None else "", "과금 단위": unit_kind,
                                   "확정 결제액": paid, "가정 결제액": paid, "가격 등급": ch.get("grade") or "",
                                   "가격 근거": basis[:160], "엔진 결정": "정량 엔진 턴" if sc.get("turn") else "계획기",
                                   "상품 ID": (tchoice or {}).get("product_id", ""), "확인 메모": " | ".join(memo)}))
        cnt[status] += 1
    return rows, cnt, bf_included, base, v


def room_row(base, v, bf_included, menu, nights_here):
    """객실 행 — 확정 금액 없음(실결제 근거 미확인) · 가정값만. nights_here = 이 원장에 넣는 박수(하루 원장: 그 날 밤 1박 · 체크아웃 당일 0)"""
    if not v.get("stay") or nights_here <= 0:
        return None
    B = v.get("building"); party = int(v.get("party_size") or 1); club = bool(v.get("club"))
    name = ROOM_ASSUME_CLUB.get(B) if club else ROOM_ASSUME.get((B, bf_included, party == 1 and B == "DOUGLAS"))
    r = menu.get((ROOM_L3.get(B, B), name)) if name else None
    unit = int(r["단가"]) if r else None
    memo = ["실결제 근거 없음 — 가정값(기존 온톨로지와 같은 패키지 기준)"]
    if bf_included: memo.append("엔진이 조식 '포함'으로 계산 → 조식 포함 패키지로 가정(조식 0원 · 이중 계산 없음)")
    if party > 2: memo.append(f"{party}인 — 패키지는 2인 기준 · 추가 인원 · 객실 수 미확인(1실 가정)")
    rs = v.get("review_stay") or {}
    if rs and rs.get("same") is False: memo.append(f"시뮬레이션 숙박({ROOM_L3.get(B, B)})이 후기 숙박({rs.get('label')})과 다름")
    layer = v.get("layer_stay") or v.get("layer")
    assume = (unit or 0) * nights_here
    return dict(base, **{"L2 부문": "ROOM", "L3 업장": ROOM_L3.get(B, B), "L4 상품": f"객실 1박 · {name or '상품 미정'}", "수량": nights_here,
                         "결제액": 0, "순매출": 0, "시각": "", "장면": "room_night", "상태": "금액 미확인", "단가": unit or "", "과금 단위": "1박 · 객실",
                         "확정 결제액": 0, "가정 결제액": assume, "가격 등급": (r or {}).get("등급", ""),
                         "가격 근거": f"menu.csv {ROOM_L3.get(B, B)} · {name} · {(r or {}).get('단위', '')} · 포함: {((r or {}).get('포함') or '')[:60]}",
                         "엔진 결정": f"방문 조건({layer})", "상품 ID": "", "확인 메모": " | ".join(memo)})


def aggregate(rows):
    agg = {k: defaultdict(lambda: [0, 0, 0]) for k in ("L4", "L3", "L2", "L1", "고객", "고객·일")}
    for r in rows:
        keys = {"L4": (r["L2 부문"], r["L3 업장"], r["L4 상품"]), "L3": (r["L2 부문"], r["L3 업장"]), "L2": (r["L2 부문"],), "L1": ("전체",),
                "고객": (r["원장 범위"], r["행사"], r["고객"]), "고객·일": (r["원장 범위"], r["행사"], r["고객"], r["체류 일차"])}
        for lv, k in keys.items():
            a = agg[lv][(r["원장 범위"], r["행사"]) + k if lv not in ("고객", "고객·일") else k]
            a[0] += int(r["수량"]); a[1] += int(r["확정 결제액"]); a[2] += int(r["가정 결제액"])
    return agg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    menu = load_menu(); meta = {"types": load_types(), "no": display_no()}
    rows, scene_cnt, checks, unmapped = [], defaultdict(int), [], defaultdict(set)

    # 1) 하루 원장 — 저장본 22개(고객이 정한 조건 × 행사 0/1) 그대로
    day_cache = {}
    for pid, ev, e in fixture_entries():
        rr, cnt, bf, base, v = day_rows(pid, ev, e, "하루(저장본)", 1, meta)
        rm = room_row(base, v, bf, menu, 0 if (v.get("phase") == "checkout" or not v.get("stay")) else 1)
        rows += rr + ([rm] if rm else [])
        for s, n in cnt.items(): scene_cnt[("하루(저장본)", s)] += n
        day_cache[(pid, ev)] = (v, sum(int(r["확정 결제액"]) for r in rr))
        # 독립 대조: 장면 charge 합(원장을 거치지 않음) = 원장 실결제 합
        direct = sum(((sc.get("basis") or {}).get("charge") or {}).get("krw") or 0 for sc in e["plans"][pid]["scenes"]
                     if ((sc.get("basis") or {}).get("charge") or {}).get("status") == "유료")
        checks.append(("하루 영수증 = 장면 지출 합", f"{meta['no'].get(pid)} 행사{ev}", direct, day_cache[(pid, ev)][1]))

    # 2) 체류 전체 원장 — 같은 방문 조건(건물 · 인원 · 클럽 · 박수)으로 단계별 하루를 실시간 계산해 이어 붙임(엔진 변경 없음)
    for (pid, ev), (v, _) in sorted(day_cache.items()):
        if not v.get("stay"):
            e = run_flow(pid, ev, None); rr, cnt, bf, base, vv = day_rows(pid, ev, e, "체류 전체", 1, meta); rows += rr
            for s, n in cnt.items(): scene_cnt[("체류 전체", s)] += n
            continue
        n = int(v.get("nights") or 1)
        phases = ["checkin"] + ["mid"] * (n - 1) + ["checkout"]
        for i, ph in enumerate(phases, 1):
            vo = {pid: {"stay": True, "building": v["building"], "phase": ph, "party_size": v["party_size"], **({"club": True} if v.get("club") else {})}}
            e = run_flow(pid, ev, vo)
            rr, cnt, bf, base, vv = day_rows(pid, ev, e, "체류 전체", i, meta)
            rm = room_row(base, vv, bf, menu, 0 if ph == "checkout" else 1)
            rows += rr + ([rm] if rm else [])
            for s, c in cnt.items(): scene_cnt[("체류 전체", s)] += c
            if ph == v.get("phase") and i == (1 if ph == "checkin" else 2 if ph == "mid" else len(phases)):
                checks.append(("저장본 하루 = 같은 조건 실시간 하루", f"{meta['no'].get(pid)} 행사{ev} {ph}", day_cache[(pid, ev)][1], sum(int(r["확정 결제액"]) for r in rr)))

    for r in rows:
        if r["L2 부문"] == "미매핑": unmapped["L3 업장"].add(r["L3 업장"])
        if r["구성·방문 목적"].startswith("미대응"): unmapped["구성·방문 목적"].add(r["구성·방문 목적"])
        if r["상태"] == "금액 미확인" and r["장면"] != "room_night": unmapped["가격"].add(f"{r['L3 업장']} · {r['L4 상품']}")

    # 3) 집계 · 합계 검증(같은 거래 내역에서)
    agg = aggregate(rows)
    for scope in ("하루(저장본)", "체류 전체"):
        for ev in ("행사 없음", "와인페어 있음"):
            R = [r for r in rows if r["원장 범위"] == scope and r["행사"] == ev]
            tot = (sum(int(r["확정 결제액"]) for r in R), sum(int(r["가정 결제액"]) for r in R))
            for lv in ("L4", "L3", "L2"):
                s = [sum(v[i] for k, v in agg[lv].items() if k[0] == scope and k[1] == ev) for i in (1, 2)]
                checks.append((f"{lv} 합 = 원장 합", f"{scope} · {ev}", tot, tuple(s)))
            l1 = agg["L1"][(scope, ev, "전체")]
            checks.append(("L1 = 원장 합", f"{scope} · {ev}", tot, (l1[1], l1[2])))
            cs = [sum(v[i] for k, v in agg["고객"].items() if k[0] == scope and k[1] == ev) for i in (1, 2)]
            checks.append(("고객 영수증 합 = L1", f"{scope} · {ev}", (l1[1], l1[2]), tuple(cs)))
            for k, v in agg["고객"].items():
                if k[0] == scope and k[1] == ev:
                    ds = [sum(x[i] for kk, x in agg["고객·일"].items() if kk[:3] == k) for i in (1, 2)]
                    checks.append(("체류 전체 = 일별 합" if scope == "체류 전체" else "고객 영수증 = 일별 합", f"{scope} · {ev} · {k[2]}", (v[1], v[2]), tuple(ds)))

    # 4) 저장
    cols = L5_COLS + EXTRA
    with (out / "L5_LEDGER_11.csv").open("w", encoding="utf-8-sig", newline="") as fd:
        w = csv.DictWriter(fd, fieldnames=cols); w.writeheader(); [w.writerow({c: r.get(c, "") for c in cols}) for r in rows]
    with (out / "L5_COMPAT_ONTOLOGY_FORMAT.csv").open("w", encoding="utf-8-sig", newline="") as fd:   # 기존 L5 열만 · 확정 결제만(가정값 제외)
        w = csv.writer(fd); w.writerow(L5_COLS)
        for r in rows:
            if r["상태"] == "실결제": w.writerow([r[c] for c in L5_COLS])
    for lv in ("L4", "L3", "L2", "L1"):
        with (out / f"AGG_{lv}.csv").open("w", encoding="utf-8-sig", newline="") as fd:
            w = csv.writer(fd); w.writerow(["원장 범위", "행사", *(["L2 부문", "L3 업장", "L4 상품"][:{"L4": 3, "L3": 2, "L2": 1, "L1": 1}[lv]] if lv != "L1" else ["L1"]), "수량", "확정 결제액", "확정 순매출", "가정 포함 결제액"])
            for k, v in sorted(agg[lv].items()):
                w.writerow([*k, v[0], v[1], round(v[1] / VAT), v[2]])
    with (out / "AGG_CUSTOMER.csv").open("w", encoding="utf-8-sig", newline="") as fd:
        w = csv.writer(fd); w.writerow(["원장 범위", "행사", "고객", "확정 결제액(실결제)", "객실 가정값 포함"])
        for k, v in sorted(agg["고객"].items()): w.writerow([*k, v[1], v[2]])
    ok = all(c[2] == c[3] for c in checks)
    res = {"checks_total": len(checks), "checks_pass": sum(c[2] == c[3] for c in checks), "all_pass": ok,
           "fail": [c for c in checks if c[2] != c[3]], "rows": len(rows), "scene_counts": {f"{k[0]}|{k[1]}": v for k, v in sorted(scene_cnt.items())},
           "unmapped": {k: sorted(v) for k, v in unmapped.items()}}
    (out / "CHECKS.json").write_text(json.dumps({**res, "checks": checks}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
