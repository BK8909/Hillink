"""체류·행동 계획 계층 (10/24 · CL-1023-09 보충1 수정본) — 동결 엔진(아침 · 행사 · 저녁 결정)을 바꾸지 않고, 그 결정 앞뒤로 고객이 호텔에
머무는 동안의 연속 행동을 프로파일로 구성한다.

세 계층의 역할
  · 정량 엔진(turn_view) : 운영상 중요한 선택(아침 · 행사 참여 · 저녁)의 점수 · 대안 · 결과 — 여기서는 입력으로만 받고 손대지 않는다
  · 행동 계획기(이 파일)  : 체크인 · 휴식 · 점심 · 간식 · 시설 이용 · 산책 · 저녁 이후처럼 일상 체류 행동을 프로파일(성향 · 후기 경험 · 동행 · 목적 ·
                           체류 단계 · 앞선 활동)로 구성한다. 규칙 백엔드(결정적 · 시드 고정)와 LLM 백엔드(같은 구조 출력 · 검증 후 사용 · 실패 시 규칙)
  · 월드 실행기(validate) : 영업시간 · 장소 존재 · 시간 겹침 · 엔진 결정 보존 · 이동 시간을 검사한다

장면마다 남기는 것: 시작 · 길이 · 장소 · 활동 · 이유(성향 · 조건) · 앞 행동과의 연결 · 주요 결정 여부 · 운영 조건 의존 · 생성 계층(review / engine / generated)
가격 · 점수 · 확률을 새로 만들지 않는다(엔진 결정에만 가격이 있다). 원문 · 실명 · 링크는 다루지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from datetime import time as dtime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parents[3]   # timeline/
CACHE = TL / "viewer" / "cache"

# ---------------------------------------------------------------- 월드: 시설 · 영업시간 · 건물
def _windows():
    """검증기의 업장 영업시간(상태 조건 없는 창만). 없으면 보수적 기본값."""
    try:
        import sys
        sys.path.insert(0, str(TL))
        import walkerhill_timeline_validator as V  # noqa
        out = {}
        for code, ws in V.WALKERHILL_VENUE_WINDOWS.items():
            arr = []
            for w in ws:
                if getattr(w, "states", None):
                    continue
                arr.append((w.open_at.hour * 60 + w.open_at.minute, w.close_at.hour * 60 + w.close_at.minute))
            if arr:
                out[code] = sorted(set(arr))
        return out
    except Exception:
        return {}

WIN = _windows()
DEFAULT_WIN = {"VISTA_ROOM": [(0, 1440)], "GRAND_ROOM": [(0, 1440)], "DOUGLAS_ROOM": [(0, 1440)], "GRAND_LOBBY": [(0, 1440)], "VISTA_LOBBY": [(0, 1440)], "DOUGLAS_LOBBY": [(0, 1440)],
               "HOTEL_GATE": [(0, 1440)], "AG_GARDEN": [(6 * 60, 22 * 60)], "GRAND_LIBRARY": [(7 * 60, 22 * 60)], "FITNESS": [(6 * 60, 22 * 60)]}

def open_at(loc, t0, t1):
    ws = WIN.get(loc) or DEFAULT_WIN.get(loc)
    if not ws:
        return True
    return any(a <= t0 and t1 <= b for a, b in ws)

BLDG_OF = {"VISTA_ROOM": "VISTA", "VISTA_LOBBY": "VISTA", "VISTA_POOL": "VISTA", "VISTA_FITNESS": "VISTA", "SKYARD": "VISTA", "THE_BUFFET": "VISTA", "MOEGI": "VISTA",
           "GRAND_ROOM": "GRAND", "GRAND_LOBBY": "GRAND", "GRAND_POOL": "GRAND", "FITNESS": "GRAND", "WELLNESS_SAUNA": "GRAND", "GRAND_LIBRARY": "GRAND", "GRAND_CLUB_LOUNGE": "GRAND",
           "ONDAL": "GRAND", "GEUMRYONG": "GRAND", "LE_PASSAGE": "GRAND", "THE_PAVILION": "GRAND", "LUX_BAR": "GRAND",
           "DOUGLAS_ROOM": "DOUGLAS", "DOUGLAS_LOBBY": "DOUGLAS", "AG_GARDEN": "DOUGLAS", "PIZZA_HILL": "PIZZA", "MYONGWOLGWAN": "MYONG", "FOREST_PARK": "FOREST",
           "RIVERPARK": "RIVER", "TENNEZ_PARK": "RIVER", "THEATRE_OF_LIGHT": "THEATRE", "HOTEL_GATE": "GATE"}
# 건물 사이 표시용 이동 시간(분) — 실제 측정값이 아니라 그림 지도의 거리감을 따른 연출값
_D = {("VISTA", "GRAND"): 6, ("VISTA", "DOUGLAS"): 12, ("VISTA", "PIZZA"): 14, ("VISTA", "MYONG"): 12, ("VISTA", "FOREST"): 14, ("VISTA", "RIVER"): 8, ("VISTA", "THEATRE"): 5, ("VISTA", "GATE"): 8,
      ("GRAND", "DOUGLAS"): 8, ("GRAND", "PIZZA"): 12, ("GRAND", "MYONG"): 12, ("GRAND", "FOREST"): 10, ("GRAND", "RIVER"): 8, ("GRAND", "THEATRE"): 5, ("GRAND", "GATE"): 10,
      ("DOUGLAS", "PIZZA"): 8, ("DOUGLAS", "MYONG"): 14, ("DOUGLAS", "FOREST"): 8, ("DOUGLAS", "RIVER"): 14, ("DOUGLAS", "THEATRE"): 12, ("DOUGLAS", "GATE"): 16,
      ("PIZZA", "MYONG"): 8, ("PIZZA", "FOREST"): 16, ("PIZZA", "RIVER"): 18, ("PIZZA", "THEATRE"): 14, ("PIZZA", "GATE"): 12,
      ("MYONG", "FOREST"): 18, ("MYONG", "RIVER"): 16, ("MYONG", "THEATRE"): 12, ("MYONG", "GATE"): 8,
      ("FOREST", "RIVER"): 10, ("FOREST", "THEATRE"): 12, ("FOREST", "GATE"): 18, ("RIVER", "THEATRE"): 6, ("RIVER", "GATE"): 12, ("THEATRE", "GATE"): 8}

def travel_min(a, b):
    if not a or not b or a == b:
        return 0
    ba, bb = BLDG_OF.get(a, "GRAND"), BLDG_OF.get(b, "GRAND")
    if ba == bb:
        return 3
    return _D.get((ba, bb)) or _D.get((bb, ba)) or 10

def room(b): return f"{b}_ROOM" if b in ("VISTA", "GRAND", "DOUGLAS") else "GRAND_ROOM"
def lobby(b): return f"{b}_LOBBY" if b in ("VISTA", "GRAND", "DOUGLAS") else "GRAND_LOBBY"
def pool(b): return "VISTA_POOL" if b == "VISTA" else "GRAND_POOL"

# 활동 카탈로그 — code: (표시 이름, 장소 fn(building), 종류, 기본 길이(분), 성인 전용, 소비 행동(돈을 쓰는 장면) 여부)
ACT = {
    "unpack":        ("객실 짐 정리 · 휴식", room, "rest", 35, False, False),
    "room_rest":     ("객실 휴식", room, "rest", 60, False, False),
    "room_nap":      ("객실에서 아이와 휴식", room, "rest", 75, False, False),
    "room_bath":     ("객실 욕조에서 휴식", room, "rest", 50, False, False),
    "room_snack":    ("객실에서 간단히 먹기", room, "lunch", 40, False, False),
    "pool":          ("수영장 이용", pool, "wellness", 75, False, False),
    "sauna":         ("사우나 · 피트니스", lambda b: "WELLNESS_SAUNA", "wellness", 55, True, False),
    "fitness":       ("피트니스", lambda b: "VISTA_FITNESS" if b == "VISTA" else "FITNESS", "wellness", 45, True, False),
    "footbath":      ("스카이야드 족욕", lambda b: "SKYARD", "wellness", 45, False, False),
    "night_footbath": ("스카이야드 야경 족욕", lambda b: "SKYARD", "wellness", 40, False, False),
    "forest_walk":   ("포레스트 파크 산책", lambda b: "FOREST_PARK", "outdoor", 50, False, False),
    "garden_walk":   ("더글라스 가든 산책", lambda b: "AG_GARDEN", "outdoor", 40, False, False),
    "riverpark":     ("리버파크 산책", lambda b: "RIVERPARK", "outdoor", 50, False, False),
    "tennez":        ("테네즈 파크 둘러보기", lambda b: "TENNEZ_PARK", "outdoor", 35, False, False),
    "cafe":          ("더 파빌리온에서 커피 · 디저트", lambda b: "THE_PAVILION", "snack", 40, False, True),
    "bakery":        ("르 파사쥬에서 빵 · 음료", lambda b: "LE_PASSAGE", "snack", 25, False, True),
    "lounge":        ("클럽 라운지 이용", lambda b: "GRAND_CLUB_LOUNGE", "snack", 50, False, False),
    "library":       ("라이브러리에서 책 · 음악", lambda b: "GRAND_LIBRARY", "rest", 45, False, False),
    "theatre":       ("빛의 시어터 관람", lambda b: "THEATRE_OF_LIGHT", "culture", 70, False, True),
    "lunch_ondal":   ("온달에서 점심", lambda b: "ONDAL", "lunch", 70, False, True),
    "lunch_geumryong": ("금룡에서 점심", lambda b: "GEUMRYONG", "lunch", 70, False, True),
    "lunch_myongwol": ("명월관에서 점심", lambda b: "MYONGWOLGWAN", "lunch", 70, False, True),
    "lunch_moegi":   ("모에기에서 점심", lambda b: "MOEGI", "lunch", 65, False, True),
    "lunch_pizzahill": ("피자힐에서 점심", lambda b: "PIZZA_HILL", "lunch", 70, False, True),
    "lunch_bakery":  ("르 파사쥬 빵 · 샌드위치로 점심", lambda b: "LE_PASSAGE", "lunch", 35, False, True),
    "lunch_cafe":    ("카페에서 가볍게 점심", lambda b: "THE_PAVILION", "lunch", 45, False, True),
    "lunch_room":    ("객실에서 간단히 점심", room, "lunch", 40, False, False),
    "lunch_skip":    ("점심 건너뛰기 · 늦은 간식", lambda b: "THE_PAVILION", "lunch", 30, False, True),
    "lunch_outside": ("호텔 밖에서 점심", lambda b: "HOTEL_GATE", "lunch", 90, False, False),
    "luxbar":        ("럭스바에서 한잔", lambda b: "LUX_BAR", "bar", 60, True, True),
    "night_walk":    ("저녁 산책 · 야경", lambda b: "AG_GARDEN", "outdoor", 35, False, False),
    "room_night":    ("객실 복귀 · 휴식", room, "rest", 90, False, False),
    "checkin":       ("체크인", lobby, "stay", 20, False, False),
    "checkout":      ("체크아웃", lobby, "stay", 20, False, False),
    "wake":          ("기상 · 준비", room, "rest", 40, False, False),
    "pack":          ("짐 정리", room, "rest", 30, False, False),
    "arrive":        ("호텔 도착", lambda b: "HOTEL_GATE", "stay", 15, False, False),
    "leave":         ("귀가", lambda b: "HOTEL_GATE", "stay", 15, False, False),
    "sleep":         ("취침", room, "rest", 60, False, False),
}
LUNCH = ["lunch_ondal", "lunch_geumryong", "lunch_myongwol", "lunch_moegi", "lunch_pizzahill", "lunch_bakery", "lunch_cafe", "lunch_room", "lunch_skip", "lunch_outside"]
EV_RE = {  # 후기 사실(요지 · 특징명)과 활동의 연결 — 식음 · 구매 사실도 '이전 경험'으로 연결만 한다(이번 이용을 뜻하지 않음)
    "pool": r"수영|swim|pool", "sauna": r"사우나|sauna|피트니스|fitness|gym", "fitness": r"피트니스|fitness|gym", "footbath": r"족욕|footbath", "night_footbath": r"야경.*족욕|족욕.*야경|night_footbath",
    "forest_walk": r"포레스트|forest", "garden_walk": r"정원|garden", "riverpark": r"리버파크|riverpark", "cafe": r"카페|cafe|디저트|dessert|커피", "bakery": r"르 ?파사쥬|빵|bakery|베이커리",
    "lounge": r"라운지|lounge", "library": r"라이브러리|library|독서|reading", "theatre": r"빛의 시어터|theatre", "luxbar": r"럭스바|lux ?bar|바에서|와인 한잔",
    "lunch_pizzahill": r"피자힐.*점심|점심.*피자힐", "lunch_myongwol": r"명월관", "lunch_ondal": r"온달", "lunch_geumryong": r"금룡", "lunch_moegi": r"모에기", "lunch_bakery": r"르 ?파사쥬|샌드위치", "lunch_room": r"객실에서.*(먹|식사)|룸서비스",
    "room_bath": r"욕조|bath_rest", "room_rest": r"객실에서 쉬|휴식|rest", "late": r"늦잠|late_sleep|늦게 일어", "early": r"일찍 도착|체크인 전|early_arrival|얼리 ?체크인", "linger": r"퇴실 ?(뒤|후)|체크아웃 ?(뒤|후)|late_checkout|레이트 ?체크아웃", "lunch_visit": r"점심|런치|lunch",
}

# ---------------------------------------------------------------- 프로파일 읽기
def _lv(bars, k):
    for b in bars or []:
        if b.get("key") == k and b.get("status") == "observed":
            return float(b.get("level") or 0)
    return 0.0

def _facet(traits, k):
    f = ((traits or {}).get("facets") or {}).get(k) or {}
    return float(f.get("level") or 0) if f.get("present") else 0.0, f.get("direction", 1)

def profile(pid, persona, bars, lib):
    """계획기가 보는 프로파일 — 성향 수준(막대 · 파셋) · 동행 · 유형 · 워커힐 후기 사실(요지 · 특징명)."""
    tr = (persona or {}).get("traits") or {}
    lp = (lib or {}).get(pid) or {}
    facts = ((lp.get("engine") or {}).get("facts") or {})
    wh = {k: v for k, v in facts.items() if v.get("wh") and not v.get("hidden")}
    P = {
        "id": pid, "type": lp.get("type_group") or lp.get("type") or "", "party_src": tr.get("visit_companion"),
        "bars": {k: _lv(bars, k) for k in ("food", "space", "value_check", "benefit", "rest_need", "routine")},
        "facets": {k: _facet(tr, k)[0] for k in ("novelty", "premium", "food_specific", "warm_rest", "swim_aversion", "active", "alcohol_familiar", "alcohol_limit", "breakfast_priority", "practical_alt", "promo")},
        "facts": [{"id": k, "gist": v.get("gist", ""), "feat": " ".join(v.get("features") or []), "kind": v.get("kind")} for k, v in wh.items()],
        "n_wh": len(wh),
        "vfs": lp.get("visit_feature_summary") or {},
    }
    P["fact_hits"] = fact_hits(P["facts"])
    P["src"] = "registry"
    return P

NEG_BASE = r"안 ?했|못 ?했|하지 않|않았|취소|대신|not_|aversion|포기"   # 본제품 11명 기준(변경 금지 — 회귀 보존)
NEG_QA = NEG_BASE + r"|생략|실패|cancel|skip|decline"                      # QA 후보: 신규 자료의 특징 키 표기(cancel_swim 등) 반영

EV_RE_QA = {"room_rest": r"객실에서 쉬|객실 휴식|room_rest"}   # QA: 'rest' 가 'forest' 안에서 맞는 문제 회피(본제품 11명 패턴은 회귀 보존 위해 그대로)

def fact_hits(facts, neg_rx=NEG_BASE, over=None):
    """후기 사실(요지 · 특징명) → 활동 코드별 근거 사실 ID(부정 · 대체 사실 제외)."""
    out = {}
    for code, rx in dict(EV_RE, **(over or {})).items():
        r = re.compile(rx)
        ids = [f["id"] for f in facts if r.search(f["gist"]) or r.search(f["feat"])]
        neg = [f["id"] for f in facts if (r.search(f["gist"]) or r.search(f["feat"])) and re.search(neg_rx, f["gist"] + " " + f["feat"])]
        pos = [i for i in ids if i not in neg]
        if pos:
            out[code] = pos
    return out

def daily_hits(daily):
    """일상 행동 12슬롯 → 활동 코드별 근거. 관찰 요약(observed · 사실 ID 동반)과 LLM 가설(hypothesis)을 따로 센다.
    슬롯의 '기본 활동' 대응표는 두지 않는다 — 그 고객의 슬롯 문장에 실제로 그 활동이 나올 때만 연결(유형 대본 방지)."""
    out = {}
    for slot, v in (daily or {}).items():
        for code, rx in EV_RE.items():
            if code in ("early", "linger", "late", "lunch_visit", "room_rest"):
                continue   # 너무 넓은 패턴(휴식 · 점심)은 슬롯 문장 대응에서 제외
            r = re.compile(rx)
            segs = [x for x in re.split(r"\s*/\s*", v.get("observed_summary") or "") if x and not re.search(NEG_QA, x)]   # 부정 · 생략 요지는 근거 아님
            if v.get("observed") and any(r.search(x) for x in segs):
                out.setdefault(code, []).append({"slot": slot, "label": v.get("label"), "layer": "observed", "facts": (v.get("observed_fact_ids") or [])[:3]})
            elif r.search(v.get("hypothesis") or ""):
                out.setdefault(code, []).append({"slot": slot, "label": v.get("label"), "layer": "hypothesis", "facts": []})
    return out

def qa_profile(pid, raw, st):
    """QA 후보(정량 등록부 밖) → 계획기 프로파일. stay_qa_profiles.to_planner 의 결과에 활동 근거를 붙인다."""
    from . import stay_qa_profiles as QA
    P, qa = QA.to_planner(pid, raw, st)
    P["type"] = st.get("type_hint") or ""
    P["fact_hits"] = fact_hits(P["facts"], NEG_QA, EV_RE_QA)
    P["trait_evidence"] = {k: v["walkerhill"] + v["other"] for k, v in qa["trait_evidence"].items() if v["level"]}
    P["daily_hits"] = daily_hits(P.get("daily"))
    P["src"] = "qa_profile"
    qa["activity_links"] = {"facts": {k: v[:3] for k, v in P["fact_hits"].items()},
                            "daily": {k: [f"{x['slot']}:{x['layer']}" for x in v] for k, v in P["daily_hits"].items()}}
    return P, qa

# ---------------------------------------------------------------- 규칙 백엔드: 활동 점수(성향 · 동행 · 맥락) — 화면에 수치로 내보내지 않는다
def comp_of(pid, N, comp):
    c = comp or {}
    return {"n": N, "kids": bool(c.get("kids")) and N >= 3, "elder": bool(c.get("elder")), "couple": c.get("rel") in ("couple", "spouse") and N == 2, "solo": N == 1, "friends": c.get("rel") in ("friend", "friends") and N >= 2}

def act_weight(code, P, C, ctx):
    """활동의 적합도(0 이하 = 후보 아님). 성향 · 동행 · 맥락(앞선 활동 · 피로 · 시간대)."""
    b, f = P["bars"], P["facets"]
    w = 0.3
    if code in ("pool",):
        w += 1.2 * (1 - f["swim_aversion"]) * (0.6 + 0.8 * (1 if C["kids"] else 0) + 0.5 * f["active"] + 0.4 * (1 if C["friends"] else 0))
        if f["swim_aversion"] > 0.3: w -= 0.8
        if C["elder"]: w -= 0.3
    elif code == "sauna":
        w += 0.9 * (b["rest_need"] + f["warm_rest"]) + 0.5 * (1 if C["elder"] else 0) + 0.3 * (1 if C["solo"] else 0)
        if C["kids"]: w -= 1.0
    elif code == "fitness":
        w += 1.0 * f["active"] - 0.3 + (0.3 if C["solo"] else 0)
    elif code in ("footbath", "night_footbath"):
        w += 0.8 * (f["warm_rest"] + b["rest_need"]) + 0.6 * b["space"] + (0.3 if C["couple"] else 0)
        if code == "night_footbath": w += 0.3 * (1 if C["couple"] else 0) - (0.5 if C["kids"] else 0)
    elif code in ("forest_walk", "garden_walk", "riverpark", "night_walk", "tennez"):
        w += 1.1 * b["space"] + 0.3 * f["active"] + (0.4 if C["kids"] and code == "riverpark" else 0) + (0.3 if C["elder"] and code in ("garden_walk", "forest_walk") else 0)
        if code == "night_walk": w += 0.3 * (1 if C["couple"] else 0) - (0.4 if C["kids"] else 0)
    elif code in ("cafe", "bakery"):
        w += 0.8 * b["food"] + 0.6 * f["food_specific"] + 0.3 * f["novelty"] + (0.3 if C["couple"] else 0)
        if code == "bakery": w += 0.4 * b["value_check"] + 0.3 * f["practical_alt"]
    elif code == "lounge":
        w += 0.9 * b["benefit"] + 0.4 * f["premium"] - 0.2
    elif code == "library":
        w += 0.7 * b["rest_need"] + (0.5 if C["solo"] else 0) - (0.5 if C["kids"] else 0)
    elif code == "theatre":
        w += 0.7 * f["novelty"] + 0.5 * b["space"] + (0.4 if C["kids"] else 0) + 0.2 * f["premium"]
    elif code in ("room_rest", "room_nap", "room_bath"):
        w += 0.9 * b["rest_need"] + 0.5 * f["warm_rest"] + 0.3 * ctx.get("fatigue", 0)
        if code == "room_nap": w += (0.9 if C["kids"] else -1.5)
        if code == "room_bath": w += (0.3 if ctx.get("spa_room") else -0.6) + (0.2 if C["solo"] or C["couple"] else -0.3)
    elif code == "luxbar":
        w += 1.0 * f["alcohol_familiar"] - 1.2 * f["alcohol_limit"] + 0.4 * b["space"] + (0.3 if C["couple"] or C["friends"] else 0) - (1.5 if C["kids"] else 0) - (0.4 if C["elder"] else 0)
    # 후기에 그 경험이 있으면 가중 · 이미 한 활동은 감점 · 같은 종류 연속 감점
    if code in P["fact_hits"]: w += 0.5 + 0.1 * min(3, len(P["fact_hits"][code]))
    w += daily_boost(P, code)
    if code in ctx.get("done", ()): w -= 1.2
    kind = ACT[code][2]
    if ctx.get("last_kind") == kind and kind in ("wellness", "outdoor"): w -= 0.4
    if ctx.get("fatigue", 0) >= 2 and kind in ("wellness", "outdoor", "culture"): w -= 0.5
    if ACT[code][4] and C["kids"]: w -= 2.0   # 성인 전용
    return w

def lunch_weight(code, P, C, ctx):
    b, f = P["bars"], P["facets"]
    dinner_loc = ctx.get("dinner_loc")
    w = 0.4
    if code in ("lunch_ondal", "lunch_geumryong", "lunch_myongwol", "lunch_moegi"):
        w += 1.0 * b["food"] + 0.7 * f["premium"] + 0.4 * f["food_specific"] - 0.8 * b["value_check"] - (0.6 if C["kids"] else 0)
        if code == "lunch_myongwol": w += 0.2 * (1 if C["elder"] else 0)
        if code == "lunch_moegi": w += 0.2 * f["novelty"]
    elif code == "lunch_pizzahill":
        w += 0.8 * b["food"] + (0.6 if C["kids"] or C["friends"] else 0) + 0.3 * b["space"] - (1.5 if dinner_loc == "PIZZA_HILL" else 0)
    elif code == "lunch_bakery":
        w += 0.9 * b["value_check"] + 0.5 * f["practical_alt"] + 0.3 * b["food"] + (0.3 if C["kids"] else 0)
    elif code == "lunch_cafe":
        w += 0.6 * b["food"] + 0.4 * f["food_specific"] + (0.3 if C["couple"] or C["solo"] else 0)
    elif code == "lunch_room":
        w += 0.8 * b["rest_need"] + 0.5 * b["value_check"] + (0.5 if C["kids"] else 0) + 0.3 * ctx.get("fatigue", 0)
    elif code == "lunch_skip":
        w += 0.6 * (1 - f["breakfast_priority"]) + 0.4 * b["rest_need"] + (0.3 if ctx.get("late_breakfast") else 0) - (0.7 if C["kids"] or C["elder"] else 0)
    elif code == "lunch_outside":
        w += 0.5 * b["routine"] * (1 if not ctx.get("stay") else 0.3) + 0.3 * f["novelty"] - 0.6 - (0.8 if C["kids"] or C["elder"] else 0)
    if code in P["fact_hits"]: w += 0.6
    w += daily_boost(P, code)
    if dinner_loc and ACT[code][1]("VISTA") == dinner_loc: w -= 1.0   # 같은 식당을 하루 두 번은 피함
    return w

def daily_boost(P, code):
    """일상 행동 자료 가중(QA 고객만) — 관찰 근거 0.45 · 가설만 0.15. 고정값(결과에 맞춘 조정 아님)."""
    h = (P.get("daily_hits") or {}).get(code)
    if not h: return 0.0
    return 0.45 if any(x["layer"] == "observed" for x in h) else 0.15

def pick(rng, items, wfn, k=1, floor=0.05):
    cand = [(c, max(floor, wfn(c))) for c in items]
    out = []
    for _ in range(k):
        if not cand: break
        tot = sum(w for _, w in cand)
        r = rng.random() * tot
        acc = 0
        for i, (c, w) in enumerate(cand):
            acc += w
            if acc >= r:
                out.append(c); cand.pop(i); break
    return out

def josa(w, a, b):
    """받침 있으면 a(을/은/이/과/으로) 없으면 b(를/는/가/와/로). ㄹ 받침 + 으로 → 로."""
    w = (w or "").rstrip(" )")
    if not w: return b
    ch = ord(w[-1])
    if not (0xAC00 <= ch <= 0xD7A3): return b
    jong = (ch - 0xAC00) % 28
    if a == "으로" and jong == 8: return "로"
    return a if jong else b

# ---------------------------------------------------------------- 이유 문장(성향 라벨 · 조건) — 화면용 · 수치 없음
BAR_LABEL = {"food": "식사 경험을 중시하는", "space": "공간과 풍경을 즐기는", "value_check": "가격을 따져 보는", "benefit": "혜택을 챙기는", "rest_need": "조용한 휴식을 중시하는", "routine": "익숙한 방식을 선호하는"}
FACET_LABEL = {"warm_rest": "온수 · 휴식을 좋아하는", "active": "몸을 움직이는 것을 좋아하는", "alcohol_familiar": "와인 · 주류에 익숙한", "novelty": "새 경험을 시도하는", "premium": "프리미엄 경험을 찾는", "food_specific": "음식 취향이 분명한", "practical_alt": "실용적인 대안을 고르는", "breakfast_priority": "아침 식사를 챙기는"}

def why(code, P, C, ctx):
    b, f = P["bars"], P["facets"]
    top = sorted([(v, k) for k, v in b.items()] + [(v * 0.9, k) for k, v in f.items() if k in FACET_LABEL], reverse=True)
    rel = {
        "pool": ["active", "space"], "sauna": ["rest_need", "warm_rest"], "fitness": ["active"], "footbath": ["warm_rest", "rest_need", "space"], "night_footbath": ["warm_rest", "space"],
        "forest_walk": ["space", "active"], "garden_walk": ["space"], "riverpark": ["space"], "night_walk": ["space"], "tennez": ["space"], "cafe": ["food", "food_specific"], "bakery": ["value_check", "food"],
        "lounge": ["benefit", "premium"], "library": ["rest_need"], "theatre": ["novelty", "space"], "room_rest": ["rest_need"], "room_nap": ["rest_need"], "room_bath": ["warm_rest", "rest_need"], "luxbar": ["alcohol_familiar", "space"],
        "lunch_ondal": ["food", "premium"], "lunch_geumryong": ["food", "premium"], "lunch_myongwol": ["food"], "lunch_moegi": ["food", "novelty"], "lunch_pizzahill": ["food"], "lunch_bakery": ["value_check", "practical_alt"],
        "lunch_cafe": ["food_specific", "food"], "lunch_room": ["rest_need", "value_check"], "lunch_skip": ["rest_need"], "lunch_outside": ["routine", "novelty"],
    }.get(code, [])
    traits = [k for k in rel if (b.get(k, 0) if k in b else f.get(k, 0)) >= 0.3][:2]
    tl = " · ".join(BAR_LABEL.get(k) or FACET_LABEL.get(k) for k in traits)
    who = []
    if C["kids"]: who.append("아이와 함께")
    if C["elder"]: who.append("부모님과 함께")
    if C["couple"]: who.append("둘이서")
    if C["friends"]: who.append("친구와")
    if C["solo"]: who.append("혼자")
    name = ACT[code][0]
    if code not in LUNCH:
        base = f"{tl + ' 성향에 맞춰 ' if tl else ''}{(who[0] + ' ') if who else ''}{name}{josa(name, '을', '를')} 이어 갑니다."
    elif code == "lunch_skip":
        base = "아침을 든든히 먹어 점심은 건너뛰고 늦은 간식으로 대신합니다."
    elif code == "lunch_outside":
        base = f"{tl + ' 성향이라 ' if tl else ''}점심은 호텔 밖에서 해결하고 돌아옵니다."
    else:
        pl = name.replace("에서 점심", "").replace("로 점심", "").replace(" 빵 · 샌드위치", " 빵 · 샌드위치")
        base = f"{tl + ' 성향이라 ' if tl else ''}점심은 {pl}{josa(pl, '으로', '로')} 해결합니다."
    if ctx.get("fatigue", 0) >= 2 and ACT[code][2] == "rest":
        base = "앞선 활동으로 피로가 쌓여 객실에서 쉬어 갑니다."
    if code in P["fact_hits"]:
        base += " 후기에서도 같은 경험이 확인됩니다."
    dh = (P.get("daily_hits") or {}).get(code) or []
    ob = [x for x in dh if x["layer"] == "observed"]
    if ob:
        base += f" 일상 행동 자료('{ob[0]['label']}')의 관찰 요지와 이어집니다."
    elif dh:
        base += f" 일상 행동 자료('{dh[0]['label']}')의 가설(관찰 아님)을 참고했습니다."
    return base, traits

# ---------------------------------------------------------------- 계획 본체(규칙 백엔드)

# ---------------------------------------------------------------- 방문 상태(보충2 · 10/24) — 투숙 여부 · 건물 · 박수 · 체류 단계 · 동행은 운영자가 아니라 에이전트가 정한다
# 근거 순서: ①후기에 적힌 워커힐 숙박 · 방문 경험(review) → ②유형 · 성향으로 보완(generated) → ③월드 조건(행사 유무)이 바꾸는 부분.
# 후기의 과거 조건을 그대로 복사하지 않는다 — 가장 무게가 크지만, 다른 선택지도 시드에 따라 나온다. 점수 · 확률은 화면에 내지 않는다.
HOTEL_RE = {"VISTA": r"비스타|vista", "GRAND": r"그랜드|클럽 ?라운지|클럽 ?스위트|grand|워커힐 ?호텔", "DOUGLAS": r"더글라스|douglas"}
NONSTAY_RE = r"비투숙|워크 ?인|당일|식사만|방문만|식당 재방문"
BLD_KO = {"VISTA": "비스타 워커힐", "GRAND": "그랜드 워커힐", "DOUGLAS": "더글라스 하우스"}
TYPE_DEFAULT = {   # 후기에 숙박 단서가 없을 때 유형별 출발 가중치(생성 계층) — 건물 · 비투숙
    "업무": {"GRAND": 1.0, "VISTA": 0.6}, "혜택": {"VISTA": 1.0, "GRAND": 0.7}, "웰니스": {"DOUGLAS": 0.9, "GRAND": 0.8, "VISTA": 0.5},
    "미식": {"NONSTAY": 0.9, "VISTA": 0.6, "GRAND": 0.5}, "행사": {"VISTA": 0.8, "NONSTAY": 0.7, "GRAND": 0.5}, "커플": {"DOUGLAS": 0.8, "VISTA": 0.8, "GRAND": 0.6},
    "영유아": {"VISTA": 1.0, "GRAND": 0.5}, "아이": {"VISTA": 1.0, "GRAND": 0.5}, "학령": {"VISTA": 0.9, "GRAND": 0.6}, "부모": {"GRAND": 0.9, "VISTA": 0.7},
    "혼자": {"VISTA": 0.9, "GRAND": 0.5, "DOUGLAS": 0.4}, "친구": {"VISTA": 0.9, "GRAND": 0.5}, "스포츠": {"GRAND": 0.8, "VISTA": 0.7}, "공항": {"GRAND": 0.8, "VISTA": 0.6},
}
TYPE_PARTY = {"영유아": (4, "family_kids"), "아이": (3, "family_kids"), "학령": (4, "family_kids"), "부모": (3, "family_parents"), "커플": (2, "couple"), "혼자": (1, "solo"), "친구": (3, "friends"),
              "업무": (1, "solo"), "미식": (2, "couple"), "웰니스": (2, "couple"), "행사": (2, "friend"), "혜택": (2, "couple"), "스포츠": (2, "friend"), "공항": (2, "couple")}

def visit_state(P, world, comp=None, seed=0):
    """→ {stay, building, nights, phase, party_size, rel, kids, elder, layer, basis:{facts, traits, type}, why, options:[...]}.
    world: {event: bool}. comp: 후기에서 확인된 동행 {n, rel}(없으면 유형으로)."""
    scen = (world or {}).get("scenario") or "day"   # 관찰 구성(운영자 · 시연 가정): day 하루 전체 운영 · event 오후 행사 중심 · weekend 주말 숙박 고객
    rng = random.Random(f"visit|{P['id']}|{seed}|{int(bool((world or {}).get('event')))}|{scen}")
    ty = P.get("type") or ""
    vfs_form = str((P.get("vfs") or {}).get("방문 형태") or "")
    facts = P.get("facts") or []
    txt_of = lambda f: f"{f.get('gist', '')} {f.get('feat', '')}"
    hits, fids, nights_seen, interest = {}, {}, [], set()
    for f in facts:
        t = txt_of(f)
        exp = f.get("kind") in ("expectation", "decline")
        for b, rx in HOTEL_RE.items():
            if re.search(rx, t, re.I):
                if exp: interest.add(b)
                else:
                    hits[b] = hits.get(b, 0) + 1; fids.setdefault(b, []).append(f["id"])
        if not exp and re.search(NONSTAY_RE, t):
            hits["NONSTAY"] = hits.get("NONSTAY", 0) + 1; fids.setdefault("NONSTAY", []).append(f["id"])
        for m in re.findall(r"(\d)박", t):
            nights_seen.append(int(m))
    # 방문 형태 요약(라이브러리) — 숙박 · 비투숙 · 건물 · 박수
    vf_b = None
    for b, rx in HOTEL_RE.items():
        if re.search(rx, vfs_form, re.I): vf_b = b
    if vfs_form:
        if re.search(NONSTAY_RE, vfs_form): hits["NONSTAY"] = hits.get("NONSTAY", 0) + 2
        elif "숙박" in vfs_form and vf_b: hits[vf_b] = hits.get(vf_b, 0) + 2
        for m in re.findall(r"(\d)박", vfs_form): nights_seen.append(int(m))
    # 후보 가중치
    W = {}
    review = {k: v for k, v in hits.items() if v}
    if review:
        tot = sum(review.values())
        for k, v in review.items(): W[k] = 0.6 + 0.9 * v / tot          # 후기 경험 — 가장 무겁다
        for k in ("VISTA", "GRAND", "DOUGLAS", "NONSTAY"):
            if k not in W: W[k] = 0.18                                 # 다른 선택지도 열어 둔다(복사 금지)
    else:
        key = next((k for k in TYPE_DEFAULT if k in ty), None)
        W = dict(TYPE_DEFAULT.get(key) or {"VISTA": 0.7, "GRAND": 0.7, "NONSTAY": 0.5})
        for k in ("VISTA", "GRAND", "DOUGLAS", "NONSTAY"): W.setdefault(k, 0.15)
    f, b = P["facets"], P["bars"]
    W["GRAND"] += 0.2 * f["premium"]; W["DOUGLAS"] += 0.2 * f["premium"] + 0.15 * b["space"]
    W["VISTA"] += 0.15 * b["value_check"]; W["NONSTAY"] += 0.1 * b["value_check"]
    for k in interest: W[k] += 0.3 * max(0.3, f["novelty"])            # 후기에 '다음 관심'으로 적은 건물
    if (world or {}).get("event") and f["alcohol_familiar"] > 0.4 and not (comp or {}).get("kids"): W["NONSTAY"] += 0.15   # 행사 날 당일 방문 가능성
    if (comp or {}).get("kids"): W["NONSTAY"] -= 0.1; W["VISTA"] += 0.1
    if scen == "weekend": W["NONSTAY"] = 0.0   # 관찰 집단 = 숙박 고객만(행동이 아니라 관찰 대상 선정)
    choice = pick(rng, [k for k in W if W[k] > 0], lambda k: W[k])[0]
    stay = choice != "NONSTAY"; building = choice if stay else None
    layer_b = "review" if (review and choice in review) else "generated"
    # 박수 · 체류 단계
    nights = max(nights_seen) if nights_seen else (2 if rng.random() < (0.45 if any(k in ty for k in ("미식", "웰니스", "커플", "부모")) else 0.3) else 1)
    nights_by_scen = False
    if stay:
        # 체류 단계 = 관찰하는 날이 이 고객 숙박의 어느 날인가. 관찰 구성(시연 가정)이 '어느 날을 보나'를 정하고, 고객 성향은 그 안에서만 작용한다
        if scen == "event":       # 오후 행사 중심 — 행사 날에 맞춰 체크인하는 고객이 많은 날을 관찰
            ph_w = {"checkin": 0.6, "mid": 0.25, "checkout": 0.15}   # 행사 날 오후 · 저녁을 보는 날 — 체크아웃 고객은 적게 관찰
            if (world or {}).get("event") and ("행사" in ty or f["alcohol_familiar"] > 0.5 or f["novelty"] > 0.5):
                ph_w["checkin"] += 0.2
        elif scen == "weekend":   # 주말 숙박 — 토요일 관찰: 금~일 2박의 중간일 · 토요일 체크인 · 토요일 체크아웃
            ph_w = {"checkin": 0.4, "mid": 0.35, "checkout": 0.25}
        else:                     # 하루 전체 운영 — 하루 종일 호텔에 머무는 날(연박 중간일)을 중심으로 관찰
            ph_w = {"checkin": 0.25, "mid": 0.55, "checkout": 0.2}
        phase = pick(rng, list(ph_w), lambda k: ph_w[k])[0]
        if phase == "mid" and nights < 2: nights = 2; nights_by_scen = True   # 관찰 구성상 연박 고객으로 관찰(후기 박수와 다를 수 있음 · 표시)
    else:
        phase = "visit"; nights = 0
    # 동행
    if comp and comp.get("n"):
        n, rel, layer_p = int(comp["n"]), comp.get("rel") or "group", "review"
    else:
        key = next((k for k in TYPE_PARTY if k in ty), None)
        n, rel = TYPE_PARTY.get(key) or (2, "group"); layer_p = "generated"
    kids = rel == "family_kids"; elder = rel == "family_parents"
    why = []
    if stay:
        why.append(f"{BLD_KO[building]} {nights}박" + (" — 후기에 같은 숙박 경험" if layer_b == "review" else " — 유형 · 성향으로 구성") + (" · 연박은 관찰 구성 가정" if nights_by_scen else ""))
        why.append({"checkin": "체크인 당일(오후부터)", "mid": "연박 중간일(아침부터)", "checkout": "체크아웃 날(아침 뒤 퇴실)"}[phase])
    else:
        why.append("비투숙 당일 방문" + (" — 후기에 같은 방문 형태" if layer_b == "review" else " — 유형 · 성향으로 구성"))
    why.append(f"{n}인 · " + ("후기에서 확인된 동행" if layer_p == "review" else "유형 기준 동행"))
    return {"stay": stay, "building": building or "VISTA", "nights": nights, "phase": phase, "party_size": n, "rel": rel, "kids": kids, "elder": elder, "scenario": scen, "nights_by_scenario": nights_by_scen,
            "layer": layer_b if layer_b == layer_p else "mixed", "layer_stay": layer_b, "layer_party": layer_p,
            "basis": {"facts": (fids.get(choice) or [])[:4], "type": ty, "traits": [k for k in ("premium", "novelty", "value_check") if (f.get(k, 0) if k != "value_check" else b["value_check"]) >= 0.5]},
            "why": " · ".join(why), "options": sorted([k for k in W if W[k] > 0.2], key=lambda k: -W[k])[:4]}

def plan_rules(P, decisions, cond, comp, seed=0, base_plan=None):
    """decisions: [{turn, time:'HH:MM', loc, label, product_label, venue_id, changed, chained}] (엔진 결과 · 손대지 않음)
    cond: {stay, building, party_size, event, phase: checkin|mid|checkout|visit, pricing, product_levers}"""
    rng = random.Random(f"{P['id']}|{seed}|{cond.get('building')}|{cond.get('party_size')}|{cond.get('phase')}|{int(bool(cond.get('event')))}")
    B = cond.get("building") or "VISTA"; stay = bool(cond.get("stay")); N = int(cond.get("party_size") or 1)
    phase = cond.get("phase") or ("mid" if stay else "visit")
    C = comp_of(P["id"], N, comp)
    D = {d["turn"]: d for d in decisions}
    dinner_loc = (D.get("dinner") or {}).get("loc")
    S = []
    ctx = {"room_ok": stay and phase in ("mid", "checkout"), "done": set(), "fatigue": 0, "last_kind": None, "stay": stay, "dinner_loc": dinner_loc, "spa_room": "vista_spa_room" in " ".join(f["feat"] for f in P["facts"])}
    def tmin(s): h, m = s.split(":"); return int(h) * 60 + int(m)
    def add(code, t0, dur=None, loc=None, layer="generated", key=False, extra=None):
        dur = dur if dur is not None else ACT[code][3]
        loc = loc or ACT[code][1](B)
        txt, traits = why(code, P, C, ctx) if code in ACT and code not in ("checkin", "checkout", "wake", "pack", "arrive", "leave", "sleep", "unpack") else ("", [])
        sc = {"t0": t0, "t1": t0 + dur, "loc": loc, "act": code, "label": ACT[code][0], "kind": ACT[code][2], "layer": layer, "key": key, "consume": ACT[code][5],
              "why": txt, "basis": {"traits": traits, "facts": P["fact_hits"].get(code, [])[:3], "cond": [f"{N}인", "투숙" if stay else "비투숙", B]},
              "prev": S[-1]["act"] if S else None, "cond_dep": False}
        if P["fact_hits"].get(code): sc["layer"] = "review"
        if P.get("trait_evidence") and traits:
            sc["basis"]["trait_facts"] = {t: P["trait_evidence"].get(t, [])[:3] for t in traits}
        dh = (P.get("daily_hits") or {}).get(code)
        if dh:
            sc["basis"]["daily"] = [f"{x['slot']}:{x['layer']}" for x in dh[:2]]
            obf = [f for x in dh if x["layer"] == "observed" for f in x["facts"]]
            if obf:
                sc["basis"]["facts"] = list(dict.fromkeys(sc["basis"]["facts"] + obf))[:4]; sc["layer"] = "review"
        if extra: sc.update(extra)
        if not sc["why"] and sc.get("note"): sc["why"] = sc["note"]
        if code == "arrive" and sc.get("note"):   # 도착 방식의 근거(후기 사실이 있으면 연결)
            k = "early" if "체크인 전" in sc["note"] else "lunch_visit" if "점심" in sc["note"] else None
            if k and P["fact_hits"].get(k): sc["basis"]["facts"] = P["fact_hits"][k][:3]; sc["layer"] = "review"
        S.append(sc)
        if code == "checkin": ctx["room_ok"] = True     # 객실 · 투숙객 전용 시설은 체크인 뒤부터
        if code == "checkout": ctx["room_ok"] = False   # 체크아웃 뒤에는 공용 시설만
        ctx["done"].add(code); ctx["last_kind"] = ACT[code][2]
        if ACT[code][2] in ("wellness", "outdoor", "culture"): ctx["fatigue"] += 1
        if ACT[code][2] == "rest": ctx["fatigue"] = max(0, ctx["fatigue"] - 1)
        return sc
    def add_engine(d, dur):
        sc = {"t0": tmin(d["time"]), "t1": tmin(d["time"]) + dur, "loc": d["loc"], "act": f"turn_{d['turn']}", "label": d.get("label") or d["turn"], "kind": "decision", "layer": "engine", "key": True, "consume": True,
              "why": "", "basis": {"traits": [], "facts": [], "cond": []}, "prev": S[-1]["act"] if S else None, "cond_dep": bool(d.get("changed")), "turn": d["turn"], "product": d.get("product_label"), "product_id": d.get("product_id") or d.get("venue_id"), "venue_id": d.get("venue_id")}
        S.append(sc); ctx["last_kind"] = "decision"
        if d["turn"] == "breakfast" and (d.get("venue_id") == "ROOM"): ctx["late_breakfast"] = True
        return sc
    def fill(t0, t1, slots, pool):
        """t0~t1 사이를 1~2개 활동으로 채운다(이동 시간 · 영업시간 반영). 남는 시간은 객실 휴식."""
        t = t0
        for _ in range(slots):
            if t1 - t < 35: break
            cands = [c for c in pool if open_at(ACT[c][1](B), t + travel_min(S[-1]["loc"], ACT[c][1](B)), min(t1, t + ACT[c][3] + travel_min(S[-1]["loc"], ACT[c][1](B))))]
            cands = [c for c in cands if c not in ctx["done"] and not (c == "night_footbath" and "footbath" in ctx["done"]) and act_weight(c, P, C, ctx) > 0.2
                     and (ctx["room_ok"] or ACT[c][1](B) not in GUEST_ONLY)]
            if not cands: break
            c = pick(rng, cands, lambda x: act_weight(x, P, C, ctx))[0]
            tr = travel_min(S[-1]["loc"], ACT[c][1](B))
            dur = min(ACT[c][3], t1 - t - tr)
            if dur < 25: break
            add(c, t + tr, dur, extra={"travel": tr})
            t += tr + dur + rng.choice([0, 5, 10])
        if t1 - t >= 30 and stay and ctx["room_ok"]:
            tr = travel_min(S[-1]["loc"], room(B))
            if t1 - t - tr >= 25: add("room_rest", t + tr, t1 - t - tr, extra={"travel": tr})
    WELL = ["pool", "sauna", "fitness", "footbath", "forest_walk", "garden_walk", "riverpark", "tennez", "cafe", "bakery", "lounge", "library", "theatre", "room_rest", "room_nap", "room_bath"]
    # 결정 턴에서 이미 고른 시설은 활동 후보에서 뺀다(족욕을 행사 턴에서 골랐으면 오후 족욕 중복 없음)
    for d in decisions:
        if d.get("venue_id") == "SKYARD": ctx["done"].add("footbath")
    # ----- 하루 뼈대(체류 단계별)
    def do_lunch(excl=(), lo=12 * 60):
        """점심(자연스러운 식사 행동) — 영업시간 · 성향 · 동행 · 같은 날 저녁 장소를 보고 고른다."""
        cands = [c for c in LUNCH if c not in excl and open_at(ACT[c][1](B), max(lo, S[-1]["t1"]) + travel_min(S[-1]["loc"], ACT[c][1](B)), 13 * 60 + 30)]
        if not cands: return None
        lc = pick(rng, cands, lambda x: lunch_weight(x, P, C, ctx))[0]
        tr = travel_min(S[-1]["loc"], ACT[lc][1](B)); lt = max(S[-1]["t1"] + tr, lo + rng.choice([0, 10, 20, 30]))
        while not open_at(ACT[lc][1](B), lt, lt + 30) and lt < 13 * 60 + 30: lt += 10   # 업장 여는 시각까지 기다림
        return add(lc, lt, ACT[lc][3], extra={"travel": tr, "meal": "lunch"})
    if phase == "visit":   # 비투숙 당일 방문 — 도착 시각은 성향 · 후기로(점심을 먹으러 오는 고객 · 오후 행사에 맞춰 오는 고객)
        first = min(tmin(d["time"]) for d in decisions) if decisions else 1110
        lunch_come = bool(P["fact_hits"].get("lunch_visit")) or P["bars"]["food"] >= 0.55 or (P["bars"]["space"] >= 0.5 and rng.random() < 0.5)
        if lunch_come:
            add("arrive", 11 * 60 + 20 + rng.choice([0, 10, 20]), 15, extra={"travel": 0, "note": "점심부터 방문"})
            do_lunch(excl=("lunch_room", "lunch_outside", "lunch_skip"), lo=11 * 60 + 50)
            fill(S[-1]["t1"] + 5, first - 10, 2, ["forest_walk", "garden_walk", "riverpark", "cafe", "bakery", "theatre", "footbath", "tennez"])
        else:
            add("arrive", first - 75, 15, extra={"travel": 0})
            fill(first - 60, first - 10, 1, ["forest_walk", "garden_walk", "riverpark", "cafe", "bakery", "theatre", "footbath"])
        if D.get("event"):
            add_engine(D["event"], 75)
            if D.get("dinner"):
                gap = tmin(D["dinner"]["time"]) - S[-1]["t1"]
                if gap >= 40: fill(S[-1]["t1"] + 5, tmin(D["dinner"]["time"]) - 10, 1, ["garden_walk", "cafe", "tennez"])
                add_engine(D["dinner"], 90)
        elif D.get("dinner"):
            add_engine(D["dinner"], 90)
        t = S[-1]["t1"]
        if P["facets"]["alcohol_familiar"] > 0.4 and not C["kids"] and open_at("LUX_BAR", t + 10, t + 60) and rng.random() < 0.5: add("luxbar", t + 10, 50, extra={"travel": travel_min(S[-1]["loc"], "LUX_BAR")})
        add("leave", S[-1]["t1"] + 10, 15, extra={"travel": travel_min(S[-1]["loc"], "HOTEL_GATE")})
        return S
    if phase == "checkin":   # 체크인 당일 — 일찍 와서 점심 · 시설부터(후기 '체크인 전 일찍 도착' · 활동적 · 새 경험) 또는 오후 도착
        early = bool(P["fact_hits"].get("early")) or (max(P["facets"]["active"], P["facets"]["novelty"], P["bars"]["food"]) >= 0.5 and rng.random() < 0.6)
        if early:
            add("arrive", 11 * 60 + 10 + rng.choice([0, 15, 30]), 15, extra={"travel": 0, "note": "체크인 전 도착 · 짐 맡김"})
            do_lunch(excl=("lunch_room", "lunch_outside"), lo=11 * 60 + 50)
            fill(S[-1]["t1"] + 5, 14 * 60 + 50, 2, ["garden_walk", "forest_walk", "riverpark", "tennez", "cafe", "bakery", "theatre", "library", "lounge"])
        else:
            add("arrive", 14 * 60 + 25 + rng.choice([0, 10, 20]), 15, extra={"travel": 0})
        add("checkin", 15 * 60, 20, extra={"travel": travel_min(S[-1]["loc"], lobby(B))})
        add("unpack", S[-1]["t1"] + 5, 30, extra={"travel": 3})
        nxt = tmin(D["event"]["time"]) if D.get("event") else (tmin(D["dinner"]["time"]) if D.get("dinner") else 18 * 60 + 30)
        fill(S[-1]["t1"] + 5, nxt - 10, 2 if nxt - S[-1]["t1"] > 110 else 1, ["pool", "sauna", "footbath", "garden_walk", "forest_walk", "cafe", "bakery", "lounge", "tennez", "room_bath"])
    elif phase in ("mid", "checkout"):
        late = bool(P["fact_hits"].get("late")) or (P["bars"]["rest_need"] >= 0.6 and P["facets"]["breakfast_priority"] < 0.3 and rng.random() < 0.5)
        bf = D.get("breakfast")
        wake_t = (tmin(bf["time"]) - 40) if bf else (9 * 60 if late else 7 * 60 + 45)
        add("wake", wake_t, 35 if bf else 45, extra={"travel": 0})
        if bf:
            add_engine(bf, 60 if bf.get("venue_id") != "ROOM" else 20)
        elif late:
            add("room_rest", S[-1]["t1"], 40, extra={"travel": 0, "note": "늦잠 · 아침 생략"})
    # ----- 투숙 공통: 오전 → 점심 → 오후 → (행사) → 저녁 → 저녁 이후
    if phase == "checkout":   # 체크아웃 날 — 퇴실 뒤 바로 귀가하거나(휴식 · 실용) 점심 · 산책을 더 하고 떠남(후기 '퇴실 뒤' · 공간 · 식사 성향)
        fill(S[-1]["t1"] + 5, 10 * 60 + 25, 1, ["pool", "sauna", "garden_walk", "forest_walk", "cafe", "bakery", "footbath", "riverpark"])
        add("pack", max(S[-1]["t1"] + 3, 10 * 60 + 25), 30, extra={"travel": travel_min(S[-1]["loc"], room(B))})
        add("checkout", 11 * 60, 20, extra={"travel": 3})
        linger = bool(P["fact_hits"].get("linger")) or (max(P["bars"]["space"], P["bars"]["food"]) >= 0.5 and rng.random() < 0.6)
        if linger:
            do_lunch(excl=("lunch_room", "lunch_skip"), lo=11 * 60 + 40)
            fill(S[-1]["t1"] + 5, 14 * 60 + 40, 1, ["forest_walk", "garden_walk", "riverpark", "tennez", "cafe", "theatre", "footbath"])
        elif P["bars"]["food"] >= 0.5 and rng.random() < 0.5 and open_at("THE_PAVILION", 11 * 60 + 25, 12 * 60): add("cafe", 11 * 60 + 25, 35, extra={"travel": travel_min(S[-1]["loc"], "THE_PAVILION")})
        add("leave", S[-1]["t1"] + 10, 15, extra={"travel": travel_min(S[-1]["loc"], "HOTEL_GATE")})
        return S
    if phase == "mid":
        # 오전(아침 뒤 ~ 11:40)
        fill(S[-1]["t1"] + 5, 11 * 60 + 40, 2 if P["facets"]["active"] >= 0.3 or P["bars"]["space"] >= 0.5 else 1, WELL)
        # 점심(12:00 ~ 13:30 사이에서 성향에 맞게)
        do_lunch()
        nxt = tmin(D["event"]["time"]) if D.get("event") else (tmin(D["dinner"]["time"]) if D.get("dinner") else 18 * 60 + 30)
        # 오후(점심 뒤 ~ 다음 결정 전)
        fill(S[-1]["t1"] + 5, nxt - 10, 2 if nxt - S[-1]["t1"] > 150 else 1, WELL)
    if D.get("event") and phase != "checkout":
        add_engine(D["event"], 75)
        if D.get("dinner"):
            gap = tmin(D["dinner"]["time"]) - S[-1]["t1"]
            if gap >= 45: fill(S[-1]["t1"] + 5, tmin(D["dinner"]["time"]) - 10, 1, ["room_rest", "garden_walk", "cafe", "tennez"])
    if D.get("dinner") and phase != "checkout":
        add_engine(D["dinner"], 90)
    # 저녁 이후
    t = S[-1]["t1"] + 10
    ev = [c for c in ["luxbar", "night_footbath", "night_walk", "library", "room_night"] if c == "room_night" or (c not in ctx["done"] and not (c == "night_footbath" and "footbath" in ctx["done"])) and open_at(ACT[c][1](B), t + travel_min(S[-1]["loc"], ACT[c][1](B)), t + travel_min(S[-1]["loc"], ACT[c][1](B)) + 40)]
    def eve_w(c):
        if c == "room_night": return 0.8 + 0.8 * P["bars"]["rest_need"] + (0.6 if C["kids"] else 0) + 0.3 * ctx["fatigue"]
        return act_weight(c, P, C, ctx)
    c = pick(rng, ev, eve_w)[0]
    if c != "room_night":
        add(c, t + travel_min(S[-1]["loc"], ACT[c][1](B)), ACT[c][3], extra={"travel": travel_min(S[-1]["loc"], ACT[c][1](B))})
        t = S[-1]["t1"] + 5
    add("room_night", t + travel_min(S[-1]["loc"], room(B)), max(40, 22 * 60 + 30 - t), extra={"travel": travel_min(S[-1]["loc"], room(B))})
    # 운영 조건 의존 표시 — 기준 조건 계획과 비교해 첫 변경 이후 달라진 장면
    if base_plan:
        changed_from = None
        for i, sc in enumerate(S):
            bsc = base_plan[i] if i < len(base_plan) else None
            if sc["layer"] == "engine" and sc.get("cond_dep"): changed_from = sc["t0"]
            if changed_from is not None and sc["t0"] >= changed_from and (not bsc or bsc.get("act") != sc.get("act") or bsc.get("loc") != sc.get("loc")): sc["cond_dep"] = True
    return S

# ---------------------------------------------------------------- 월드 실행기: 검증
WORLD_PLACES = None
def world_places():
    """월드에 있는 장소 코드 — 건물 표 · 영업시간 표 · 활동 카탈로그(세 건물) · 엔진 결정 장소. 여기에 없는 장소는 검증 실패."""
    global WORLD_PLACES
    if WORLD_PLACES is None:
        w = set(BLDG_OF) | set(WIN) | set(DEFAULT_WIN)
        for c, v in ACT.items():
            for b in ("VISTA", "GRAND", "DOUGLAS"):
                w.add(v[1](b))
        WORLD_PLACES = w
    return WORLD_PLACES

def _hm(t): h, m = str(t).split(":")[:2]; return int(h) * 60 + int(m)

# 투숙객 전용(가정) — 실제 워커힐 운영 규칙 전체를 검증한 표가 아니다. 객실 · 수영장 · 피트니스 · 사우나 · 클럽 라운지 · 라이브러리.
GUEST_ONLY = {"VISTA_ROOM", "GRAND_ROOM", "DOUGLAS_ROOM", "VISTA_POOL", "GRAND_POOL", "VISTA_FITNESS", "FITNESS", "WELLNESS_SAUNA", "GRAND_CLUB_LOUNGE", "GRAND_LIBRARY"}
SEV = {"UNKNOWN_PLACE": "blocked", "DECISION_MISSING_OR_DUPLICATED": "blocked", "DECISION_TIME_CHANGED": "blocked", "DECISION_PLACE_CHANGED": "blocked",
       "DECISION_PRODUCT_CHANGED": "blocked", "DECISION_EXTRA": "blocked", "LOCK_TAMPERED": "blocked",
       "BAD_DURATION": "fixable", "OVERLAP": "fixable", "TRAVEL_GAP": "fixable", "CLOSED_FACILITY": "fixable",
       "ACTIVITY_AFTER_CHECKOUT": "fixable", "ROOM_BEFORE_CHECKIN": "fixable", "GUEST_ONLY_FOR_NONSTAY": "fixable", "ACTIVITY_AFTER_LEAVE": "fixable"}

def _t(m): return f"{m // 60:02d}:{m % 60:02d}"

def check(S, decisions, state=None):
    """월드 실행기 검증(CL-1024-12 긴급 보충 · Codex CD-1024-06 반례 8건 포함) → {verdict: pass|fixable|blocked, issues:[{code, severity, msg, i}]}.
    ① 길이 · 겹침 ② 장소가 월드에 있음 ③ 앞 장면에서 이동 가능한 시간 ④ 비결정 장면 영업시간 ⑤ 숙박 상태(체크인 전 · 체크아웃 뒤 · 비투숙의 객실/투숙객 전용 시설)
    ⑥ 엔진 결정: 턴마다 정확히 하나 · 같은 시각 · 같은 장소 · 같은 상품(ID · 이름) · 결정에 없는 엔진 장면 금지.
    엔진 결정 장면이 얽힌 겹침 · 이동 부족은 결정을 움직여야 고칠 수 있으므로 blocked."""
    iss, W = [], world_places()
    def add(code, msg, i=None, sev=None): iss.append({"code": code, "severity": sev or SEV[code], "msg": msg, "i": i})
    for i, sc in enumerate(S):
        eng = sc.get("layer") == "engine"
        if sc["t1"] <= sc["t0"]: add("BAD_DURATION", f"{sc['act']}: 길이 0", i, "blocked" if eng else None)
        if sc["loc"] not in W: add("UNKNOWN_PLACE", f"{sc['act']}@{sc['loc']}: 월드에 없는 장소", i)
        if i:
            pv = S[i - 1]; both = "blocked" if (eng and pv.get("layer") == "engine") else None
            if sc["t0"] < pv["t1"] - 1: add("OVERLAP", f"{sc['act']}: 앞 장면과 겹침 {_t(pv['t1'])}>{_t(sc['t0'])}", i, both)
            elif pv["loc"] != sc["loc"] and pv["loc"] in W and sc["loc"] in W:
                need = travel_min(pv["loc"], sc["loc"])
                if sc["t0"] - pv["t1"] < need - 1: add("TRAVEL_GAP", f"{sc['act']}: 이동 시간 부족 {pv['loc']}→{sc['loc']} 필요 {need}분 · 여유 {sc['t0'] - pv['t1']}분", i, both)
        if not eng and sc["loc"] in W and not open_at(sc["loc"], sc["t0"], min(sc["t1"], sc["t0"] + 30)): add("CLOSED_FACILITY", f"{sc['act']}@{sc['loc']}: 영업시간 밖 {_t(sc['t0'])}", i)
    # ⑤ 숙박 상태
    st = state or {}
    stay = st.get("stay", True) and st.get("phase") != "visit"
    ci = next((sc for sc in S if sc.get("act") == "checkin"), None)
    co = next((sc for sc in S if sc.get("act") == "checkout"), None)
    lv = next((sc for sc in S if sc.get("act") == "leave"), None)
    for i, sc in enumerate(S):
        g = sc["loc"] in GUEST_ONLY; sev = "blocked" if sc.get("layer") == "engine" else None
        if not stay and g: add("GUEST_ONLY_FOR_NONSTAY", f"{sc['act']}@{sc['loc']}: 비투숙 방문인데 객실 · 투숙객 전용 시설", i, sev)
        if ci and g and sc["t0"] < ci["t1"] and sc is not ci and sc.get("act") not in ("wake", "sleep"): add("ROOM_BEFORE_CHECKIN", f"{sc['act']}@{sc['loc']}: 체크인 전 객실 · 투숙객 전용 시설", i, sev)
        if co and g and sc["t0"] >= co["t1"]: add("ACTIVITY_AFTER_CHECKOUT", f"{sc['act']}@{sc['loc']}: 체크아웃 뒤 객실 · 투숙객 전용 시설", i, sev)
        if lv and sc is not lv and sc["t0"] >= lv["t1"]: add("ACTIVITY_AFTER_LEAVE", f"{sc['act']}: 귀가 뒤 활동", i, sev)
    # ⑥ 엔진 결정
    eng = [(i, sc) for i, sc in enumerate(S) if sc.get("layer") == "engine"]
    for d in decisions:
        m = [(i, sc) for i, sc in eng if sc.get("turn") == d["turn"]]
        if len(m) != 1: add("DECISION_MISSING_OR_DUPLICATED", f"엔진 결정 {d['turn']}: 장면 {len(m)}개(정확히 1개여야 함)"); continue
        i, sc = m[0]
        if d.get("time") and sc["t0"] != _hm(d["time"]): add("DECISION_TIME_CHANGED", f"엔진 결정 {d['turn']}: 시각 불일치 {_t(sc['t0'])} ≠ {d['time']}", i)
        if sc["loc"] != d["loc"]: add("DECISION_PLACE_CHANGED", f"엔진 결정 {d['turn']}: 장소 불일치 {sc['loc']} ≠ {d['loc']}", i)
        if d.get("product_label") and sc.get("product") != d["product_label"]: add("DECISION_PRODUCT_CHANGED", f"엔진 결정 {d['turn']}: 상품 불일치 '{sc.get('product')}' ≠ '{d['product_label']}'", i)
        pid_ = d.get("product_id") or d.get("venue_id")
        if pid_ and sc.get("product_id", sc.get("venue_id")) != pid_: add("DECISION_PRODUCT_CHANGED", f"엔진 결정 {d['turn']}: 상품 ID 불일치 {sc.get('product_id', sc.get('venue_id'))} ≠ {pid_}", i)
    extra = [sc.get("turn") for i, sc in eng if sc.get("turn") not in {d["turn"] for d in decisions}]
    if extra: add("DECISION_EXTRA", f"결정에 없는 엔진 장면 {extra}")
    verdict = "blocked" if any(x["severity"] == "blocked" for x in iss) else ("fixable" if iss else "pass")
    return {"verdict": verdict, "issues": iss}

def validate(S, decisions, state=None):
    """호환용 — 오류 문자열 목록(빈 목록 = 통과)."""
    return [x["msg"] for x in check(S, decisions, state)["issues"]]

def fit_travel(S):
    """월드 실행기 조정 — 장면 사이 이동 시간이 모자라면 앞의 비결정 장면을 줄이거나(10분 이상 남을 때) 뒤의 비결정 장면을 늦춘다. 엔진 결정은 움직이지 않는다."""
    for i in range(1, len(S)):
        pv, sc = S[i - 1], S[i]
        if pv["loc"] == sc["loc"]: continue
        need = travel_min(pv["loc"], sc["loc"]); gap = sc["t0"] - pv["t1"]
        if gap >= need: continue
        short = need - gap
        if pv["layer"] != "engine" and pv["t1"] - short - pv["t0"] >= 10: pv["t1"] -= short
        elif sc["layer"] != "engine" and sc["t1"] - (sc["t0"] + short) >= 10: sc["t0"] += short
        sc["travel"] = need
    return S

PROTECTED_ACTS = {"arrive", "checkin", "checkout", "leave", "wake", "room_night", "sleep"}

def autofix(S, decisions, state=None):
    """수정 가능(fixable) 오류만 고친다 — 비결정 장면을 줄이거나 · 늦추거나 · 뺀다. 엔진 결정 장면은 절대 바꾸지 않는다. → (S, 수정 기록)."""
    log = []
    S = [dict(x) for x in S]
    def protected(x):   # 방문 목적 · 일정 뼈대 — 자동 수정으로 빼지 않는다(빼야만 고쳐지면 그대로 두어 재검증에서 차단)
        return x.get("layer") == "engine" or x.get("act") in PROTECTED_ACTS or x.get("meal")
    for _ in range(3):
        r = check(S, decisions, state)
        if r["verdict"] != "fixable": break
        drop = set()
        for x in r["issues"]:
            i = x["i"]
            if i is None or protected(S[i]): continue
            if x["code"] in ("CLOSED_FACILITY", "ACTIVITY_AFTER_CHECKOUT", "ROOM_BEFORE_CHECKIN", "GUEST_ONLY_FOR_NONSTAY", "ACTIVITY_AFTER_LEAVE", "BAD_DURATION"):
                drop.add(i); log.append(f"{x['code']}: {S[i]['act']} 제외")
            elif x["code"] == "OVERLAP":
                pv = S[i - 1]
                if pv.get("layer") != "engine" and S[i]["t0"] - pv["t0"] >= 10: pv["t1"] = S[i]["t0"]; log.append(f"OVERLAP: {pv['act']} 단축")
                else: S[i]["t0"] = pv["t1"]; log.append(f"OVERLAP: {S[i]['act']} 늦춤")
                if S[i]["t1"] - S[i]["t0"] < 10: drop.add(i)
        S = [x for k, x in enumerate(S) if k not in drop]
        before = json.dumps([(x["t0"], x["t1"]) for x in S])
        S = fit_travel(S)
        if json.dumps([(x["t0"], x["t1"]) for x in S]) != before: log.append("TRAVEL_GAP: 이동 시간 확보")
        # fit_travel 로 못 고친 이동 부족 → 뒤 비결정 장면 제외
        r2 = check(S, decisions, state)
        tg = [x["i"] for x in r2["issues"] if x["code"] in ("TRAVEL_GAP", "OVERLAP") and x["i"] is not None and not protected(S[x["i"]])]
        if tg:
            log += [f"TRAVEL_GAP: {S[i]['act']} 제외" for i in tg]
            S = [x for k, x in enumerate(S) if k not in set(tg)]
    return S, log

# ---------------------------------------------------------------- 정량 결정 잠금(불변 객체)
LOCK_FIELDS = ("decision_id", "turn", "time", "loc", "product_id", "product_label", "participation", "alternatives", "source")

def make_lock(decisions):
    """화면이 받은 정량 엔진 결정 → 잠금 객체(정렬된 JSON 의 SHA-256 포함). 계획기는 이 사본을 읽기만 한다."""
    items = []
    for d in decisions:
        items.append({"decision_id": d.get("decision_id") or f"{d.get('turn')}@{d.get('time')}", "turn": d.get("turn"), "time": d.get("time"), "loc": d.get("loc"),
                      "product_id": d.get("product_id") or d.get("venue_id"), "product_label": d.get("product_label"),
                      "participation": d.get("participation") or ("participate" if d.get("venue_id") not in (None, "", "NONE", "SKIP") else "skip"),
                      "alternatives": list(d.get("alternatives") or []), "source": d.get("source") or "quantitative_engine_turn_view"})
    blob = json.dumps(items, ensure_ascii=False, sort_keys=True)
    return {"items": items, "sha256": hashlib.sha256(blob.encode()).hexdigest(), "n": len(items)}

def lock_intact(lock):
    blob = json.dumps(lock["items"], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest() == lock["sha256"]

def scene_sources(S, P):
    """장면별 출처: quantitative_decision(엔진 결정) · observed_reference(그 고객의 후기 사실/일상 관찰 근거) · generated_plan(생성)."""
    for sc in S:
        b = sc.get("basis") or {}
        if sc.get("layer") == "engine": sc["source"] = "quantitative_decision"
        elif b.get("facts") or any(str(x).endswith(":observed") for x in b.get("daily") or []): sc["source"] = "observed_reference"
        else: sc["source"] = "generated_plan"
    return S

def inputs_used(S, P):
    """계획기 입력이 실제 장면에 쓰였는지 — 그 고객 소유 ID(사실 · 일상 슬롯)와 성향 키를 장면 근거에서 모은다."""
    own = {f["id"] for f in P.get("facts") or []}
    facts = sorted({f for sc in S for f in (sc.get("basis") or {}).get("facts") or [] if f in own})
    daily = sorted({x for sc in S for x in (sc.get("basis") or {}).get("daily") or []})
    traits = sorted({t for sc in S for t in (sc.get("basis") or {}).get("traits") or []})
    te = P.get("trait_evidence") or {}
    tfacts = sorted({f for t in traits for f in te.get(t, [])})   # QA: 장면 이유에 쓰인 성향 키를 만든 그 고객의 사실 ID
    return {"fact_ids": facts, "daily_slots": daily, "trait_keys": traits, "trait_fact_ids": tfacts}


# ---------------------------------------------------------------- LLM 백엔드(선택) — 같은 구조를 JSON 으로 제안 · 검증 통과 때만 사용 · 실패 시 규칙
def _key():
    k = os.environ.get("OPENAI_API_KEY")
    if not k:
        f = Path.home() / ".secrets" / "openai_key"
        if f.exists(): k = f.read_text().strip()
    return k

def llm_available():
    return bool(_key())

LAST_LLM_META = {}

def plan_llm(P, decisions, cond, comp, seed=0, rules_plan=None):
    """LLM 에게 프로파일 · 엔진 결정 · 월드(활동 코드 · 영업시간) 를 주고 구조화된 하루를 제안받는다. 응답은 해시로 캐시한다."""
    import requests
    B = cond.get("building") or "VISTA"
    acts = {c: {"label": v[0], "loc": v[1](B), "kind": v[2], "default_min": v[3], "adult_only": v[4], "hours": WIN.get(v[1](B)) or DEFAULT_WIN.get(v[1](B)) or "항상"} for c, v in ACT.items()}
    prof = {"type": P["type"], "party": comp, "traits": {k: round(v, 2) for k, v in {**P["bars"], **P["facets"]}.items() if v}, "experiences": [{"id": f["id"], "gist": f["gist"]} for f in P["facts"]][:30]}
    fixed = [{"turn": d["turn"], "time": d["time"], "loc": d["loc"], "label": d.get("label"), "product": d.get("product_label")} for d in decisions]
    sysmsg = ("당신은 첨부된 고객 프로파일의 성향과 경험을 가진 호텔 방문객입니다. 과거 행동 · 선호 · 동행 구성 · 방문 목적을 토대로 호텔에 머무는 동안의 자연스러운 행동을 정합니다. "
              "월드에 있는 활동 코드 · 장소 · 영업시간만 씁니다. 정량 엔진이 확정한 주요 선택(fixed)은 시각 · 장소 그대로 유지하고 그 전후 활동을 일관된 이유와 함께 구성합니다. "
              "모든 시간에 활동이 필요하지 않습니다(객실 휴식 · 취침도 정상). 같은 장소 · 행동의 기계적 반복을 피하고 앞선 활동 · 피로 · 식사 · 동행자를 고려합니다. "
              "가격 · 점수 · 확률을 만들지 않습니다. 출력은 JSON 만: {\"scenes\":[{\"act\":코드,\"start\":\"HH:MM\",\"min\":길이,\"why\":한 문장,\"traits\":[성향키],\"facts\":[경험id]}]}")
    user = {"profile": prof, "fixed_decisions": fixed, "cond": {k: cond.get(k) for k in ("stay", "building", "party_size", "event", "phase")}, "activities": acts, "seed": seed}
    body = {"model": os.environ.get("OPENAI_MODEL", "gpt-6-luna"), "input": [{"role": "system", "content": sysmsg}, {"role": "user", "content": json.dumps(user, ensure_ascii=False)}], "text": {"format": {"type": "json_object"}}, "reasoning": {"effort": "low"}}
    h = hashlib.sha1(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    CACHE.mkdir(exist_ok=True); cf = CACHE / "stay_plans.jsonl"
    cached = None
    if cf.exists():
        for line in cf.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(line)
                if j.get("h") == h: cached = j["out"]
            except Exception: pass
    meta = {"model": body["model"], "cached": cached is not None, "ms": 0, "usage": None}
    if cached is None:
        t_0 = time.time()
        r = requests.post("https://api.openai.com/v1/responses", json=body, timeout=90, headers={"Authorization": f"Bearer {_key()}"})
        r.raise_for_status()
        j = r.json()
        txt = "".join(c.get("text", "") for o in j.get("output", []) for c in o.get("content", []) if c.get("type") in ("output_text", "text"))
        cached = json.loads(txt)
        meta["ms"] = int((time.time() - t_0) * 1000); meta["usage"] = j.get("usage")
        with cf.open("a", encoding="utf-8") as f: f.write(json.dumps({"h": h, "t": time.time(), "out": cached, "usage": j.get("usage"), "ms": meta["ms"]}, ensure_ascii=False) + "\n")
    LAST_LLM_META.clear(); LAST_LLM_META.update(meta)
    S = []
    for sc in cached.get("scenes", []):
        c = sc.get("act")
        if c not in ACT or c.startswith("turn_"): continue
        hh, mm = str(sc.get("start", "00:00")).split(":")[:2]; t0 = int(hh) * 60 + int(mm); dur = int(sc.get("min") or ACT[c][3])
        S.append({"t0": t0, "t1": t0 + dur, "loc": ACT[c][1](B), "act": c, "label": ACT[c][0], "kind": ACT[c][2], "layer": "review" if P["fact_hits"].get(c) else "generated", "key": False, "consume": ACT[c][5],
                  "why": str(sc.get("why") or ""), "basis": {"traits": [t for t in (sc.get("traits") or []) if t in BAR_LABEL or t in FACET_LABEL][:3], "facts": [f for f in (sc.get("facts") or []) if f in {x["id"] for x in P["facts"]}][:3], "cond": []}, "prev": None, "cond_dep": False, "travel": 0})
    for d in decisions:   # 엔진 결정은 LLM 제안과 무관하게 고정
        hh, mm = d["time"].split(":"); t0 = int(hh) * 60 + int(mm)
        S.append({"t0": t0, "t1": t0 + {"breakfast": 60, "event": 75, "dinner": 90}.get(d["turn"], 60), "loc": d["loc"], "act": f"turn_{d['turn']}", "label": d.get("label") or d["turn"], "kind": "decision", "layer": "engine", "key": True, "consume": True, "why": "", "basis": {"traits": [], "facts": [], "cond": []}, "prev": None, "cond_dep": bool(d.get("changed")), "turn": d["turn"], "product": d.get("product_label"), "product_id": d.get("product_id") or d.get("venue_id"), "venue_id": d.get("venue_id"), "travel": 0})
    S.sort(key=lambda x: x["t0"])
    out = []   # 겹치면 LLM 장면을 깎거나 뺀다(엔진 결정 우선)
    for sc in S:
        if out and sc["t0"] < out[-1]["t1"]:
            if sc["layer"] == "engine": out[-1]["t1"] = sc["t0"]
            else: sc["t0"] = out[-1]["t1"]
            if sc["t1"] - sc["t0"] < 15: continue
        if out: sc["prev"] = out[-1]["act"]; sc["travel"] = travel_min(out[-1]["loc"], sc["loc"])
        out.append(sc)
    return out

def plan(P, decisions, cond, comp, seed=0, backend="rules", base_plan=None):
    """backend: rules | llm | auto(키 있으면 llm · 검증 실패 시 rules).
    흐름: 잠금 생성 → 계획(LLM 또는 규칙) → 월드 검증 → 수정 가능이면 자동 수정(엔진 결정 불변) → 재검증 → 통과만 재생 가능.
    실행 차단(blocked)이면 장면을 내보내지 않는다(status=blocked · 이유 목록). 요청/실제 계획기와 대체 이유를 따로 남긴다."""
    lock = make_lock(decisions)
    used = "rules"; reason = None; llm_meta = None; S = None; first = None; fixlog = []
    state = {"stay": cond.get("stay", True), "phase": cond.get("phase")}
    if backend in ("llm", "auto"):
        if not llm_available():
            reason = "API 키 없음 — 규칙 계획기로 실행(LLM 호출 안 함)"
        else:
            try:
                S0 = plan_llm(P, decisions, cond, comp, seed)
                llm_meta = dict(LAST_LLM_META)
                first = check(S0, decisions, state)
                if first["verdict"] == "blocked":
                    reason = "LLM 계획이 월드 검증에서 실행 차단 — " + " / ".join(x["msg"] for x in first["issues"] if x["severity"] == "blocked")[:300]
                else:
                    S, fixlog = autofix(S0, decisions, state) if first["verdict"] == "fixable" else (S0, [])
                    if check(S, decisions, state)["verdict"] != "pass":
                        reason = "LLM 계획이 자동 수정 뒤에도 월드 검증 실패 — 규칙 계획기로 대체"; S = None; fixlog = []
                    else:
                        used = "llm"
            except Exception as e:
                reason = f"LLM 호출 실패 — {type(e).__name__}: {str(e)[:120]}"; S = None
    if S is None:
        S0 = fit_travel(plan_rules(P, decisions, cond, comp, seed, base_plan))   # 규칙 계획기는 이동 시간 맞춤까지가 생성 단계
        r0 = check(S0, decisions, state)
        if first is None: first = r0
        S, fixlog = autofix(S0, decisions, state) if r0["verdict"] == "fixable" else (S0, [])
    final = check(S, decisions, state)
    if not lock_intact(lock):
        final["issues"].append({"code": "LOCK_TAMPERED", "severity": "blocked", "msg": "잠금 객체가 계획 중 바뀜", "i": None}); final["verdict"] = "blocked"
    for i, sc in enumerate(S):
        sc["i"] = i
        sc.setdefault("travel", travel_min(S[i - 1]["loc"], sc["loc"]) if i else 0)
    scene_sources(S, P)
    status = "ok" if final["verdict"] == "pass" else "blocked"
    out = {"status": status, "scenes": S if status == "ok" else [], "backend": used, "requested": backend, "fallback_reason": reason, "llm": llm_meta,
           "warnings": [x["msg"] for x in final["issues"]], "validation": {"first": {"verdict": first["verdict"], "codes": sorted({x["code"] for x in first["issues"]})},
           "final": {"verdict": final["verdict"], "codes": sorted({x["code"] for x in final["issues"]}), "issues": final["issues"][:12]}, "autofix": fixlog},
           "lock": {"sha256": lock["sha256"], "n": lock["n"], "items": lock["items"], "intact": lock_intact(lock)},
           "inputs_used": inputs_used(S, P), "blocked_scene_count": len(S) if status != "ok" else 0}
    out["decision_context_preserved"] = status == "ok" and not any(c.startswith("DECISION") or c == "LOCK_TAMPERED" for c in out["validation"]["final"]["codes"])
    return out
