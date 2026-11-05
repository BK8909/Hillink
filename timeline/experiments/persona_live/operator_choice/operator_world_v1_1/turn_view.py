"""화면 JSON 계약 — 핵심 선택 턴 결과를 지도 화면이 쓰는 모양으로 꺼낸다(표시 · 전달 구조만, 계산은 turn_candidate 그대로).

turn_view(personas, conditions)   → 에이전트별 선택 · 대안 · 이유(공통 / 후기 근거 / 설계 가정) · 가격 출처 · 지도 위치
turn_compare(before, after)        → 에이전트별 선택 변경 / 점수만 변경 / 유지 · 업장 변경 여부 · 가장 크게 변한 항

계수 · 효용 계산은 바꾸지 않는다. 분류는 표시 규칙이다:
  review     : 근거 사실 ID 가 붙은 항(후기에서 연결된 성향 · 업장 이력)
  assumption : 근거 없이 월드 설계로 들어간 값에서 나온 항 — 지금은 객실 식사의 '휴식 · 회복'(객실 식사 휴식 가치 0.6)
  common     : 그 밖의 항(끼니 · 기본 음식 · 지불액 · 대기 등 — 누구에게나 같은 규칙)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from operator_choice.operator_world_v1 import world as WD
from operator_choice.operator_world_v1.__main__ import PRESETS
from operator_choice.operator_world_v1 import engine as EN
from operator_choice.operator_world_v1 import profile_adapter as PA
from operator_choice.operator_world_v1_1.candidate import candidate_engine
from operator_choice.operator_world_v1_1.turn_candidate import load_catalog, turn_world, decide_turn, TURN_TIME

PERSONA_PATH = Path(__file__).with_name("turn_personas_rbase.json")
PRE = {p["id"]: p["levers"] for p in PRESETS}

VENUE_LABEL = {"PIZZA_HILL": "피자힐", "ROOM_MEAL": "객실(룸서비스)", "MYONGWOLGWAN": "명월관", "ONDAL": "온달", "GEUMRYONG": "금룡",
               "THE_BUFFET": "더뷔페", "LE_PASSAGE": "르 파사쥬", "ROOM": "객실", "FOREST": "포레스트 파크", "SKYARD": "스카이야드"}
MAP_LOC = {"FOREST": "FOREST_PARK"}
BUILDING_LABEL = {"GRAND": "그랜드 워커힐", "VISTA": "비스타 워커힐", "DOUGLAS": "더글라스 하우스"}
MENU_AS_OF = {"PH_PDF_2026_07": "2026-07 메뉴판", "RS_PHOTO_2021": "2021년경 메뉴 사진", "WORLD_V1_IRD": "기존 월드(공식 IRD 주석)", "OPERATOR_INPUT": "운영자 입력(공식 가격 미확인)", "NONE": "지불 없음", "WORLD_V1": "2026 가을 공식 운영 조건(기존 월드)", "PRESET_V1": "연구 프리셋 · 가상 운영안"}
BAR_FACETS = ["food", "space", "value_check", "benefit", "rest_need", "routine"]      # 저녁 턴에서 쓰이는 성향 — 엔진 facet 그대로


def load_personas(path: Path = PERSONA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["personas"]


# 10/23 확장 에이전트 — R-BASE 5명(load_personas)은 그대로 두고 화면 실행기에서만 합친다.
#   turn_personas_ext.json(저장소 · 개발 그룹 blog41~43) · turn_personas_ext.local.json(로컬 전용 · 비공개 보관 프로파일)
EXT_PATHS = (PERSONA_PATH.with_name("turn_personas_ext.json"), PERSONA_PATH.with_name("turn_personas_ext.local.json"))


def load_all_personas() -> dict:
    P = dict(load_personas())
    for f in EXT_PATHS:
        if f.exists():
            for k, v in json.loads(f.read_text(encoding="utf-8"))["personas"].items():
                P.setdefault(k, v)
    return P


def _venue_of(o: dict) -> str:
    cat = o.get("catalog")
    if cat:
        return o["venue"] if o["venue"] in VENUE_LABEL else ("ROOM_MEAL" if o["kind"] == "room_meal" else o["venue"])
    return o["venue"]


def _map_loc(venue: str, building: str) -> str:
    return f"{building}_ROOM" if venue in ("ROOM_MEAL", "ROOM") else MAP_LOC.get(venue, venue)


def _price(o: dict) -> dict:
    cat = o.get("catalog") or {}
    src = cat.get("source") or ("WORLD_V1" if o.get("status") == "official" else o.get("status"))
    note = o["price_source"]["note"]
    paid = 0 if o.get("in_package") else max(0, o["price_pp_krw"] - (o.get("guest_discount_krw") or 0) - (o.get("card_benefit_krw") or 0))
    return dict(pp_krw=o["price_pp_krw"], paid_krw=paid, in_package=bool(o.get("in_package")), guest_discount_krw=o.get("guest_discount_krw") or 0,
                list_krw=cat.get("list_price_krw", o["price_pp_krw"]), basis=cat.get("pricing", "world_v1"),
                source=src, menu_as_of=MENU_AS_OF.get(cat.get("source"), "2026 가을 공식 정보(기존 월드)"),
                is_estimate=cat.get("pricing") == "provisional" and "× 1.10" in note, operator_set="운영자 설정" in note, party_assumed="(인원 추정)" in note, party_basis=cat.get("party_basis"), share_n=cat.get("share_n"), note=note)


def _empty_traits() -> dict:
    f = PA._empty_facets()
    PA._finish(f)
    return dict(facets=f, menu=[], venues={}, evidence_index={}, evidence_granularity="fact")


def common_baseline(offer: dict, visit: dict, world: dict, turn: str) -> dict:
    """같은 선택지를 후기 근거가 하나도 없는 성향으로 같은 시점에 계산한 항별 값 — 항 안의 공통 몫(기존 감사의 '공통 기본선'과 같은 방법)."""
    v = dict(visit, checkin="07:00" if turn == "breakfast" else visit.get("checkin", "15:30"))
    with candidate_engine(c1=True, c2="venue_visits", c3=True):
        terms = EN.score(offer, EN.hm(TURN_TIME[turn]), dict(used=set(), hunger=1.0), v, _empty_traits(), world)
    out = {}
    for x in terms:
        k = x["factor"].replace("저녁 끼니 해결", "아침 끼니 해결").replace("저녁을 미룸", "아침 식사 건너뜀") if turn == "breakfast" else x["factor"]
        out[k] = out.get(k, 0.0) + x["value"]
    return out


def split_reason(reason: dict, offer: dict, base: dict) -> dict:
    """항 하나를 공통 / 후기 근거 / 설계 가정 몫으로 나눈다(표시 규칙 · 계산 변경 없음).
    공통 몫 = 근거 없는 성향으로 계산한 같은 항의 값 · 후기 근거 몫 = 나머지 · 객실 식사 '휴식 · 회복'의 공통 몫은 설계 가정(휴식 가치 0.6)."""
    v = reason["value"]
    c = base.get(reason["factor"], 0.0) if reason["factor"] in base else (0.0 if reason.get("fact_ids") else v)
    if not reason.get("fact_ids"):
        c = v
    r = v - c
    if reason["factor"] == "휴식 · 회복" and offer["kind"] == "room_meal":
        return dict(common=0.0, review=round(r, 4), assumption=round(c, 4))
    return dict(common=round(c, 4), review=round(r, 4), assumption=0.0)


def classify(parts: dict) -> str:
    return max(parts, key=lambda k: abs(parts[k]))


def display_evidence(traits: dict, fact_ids: list[str]) -> tuple[dict, dict]:
    """표시 전용: 제공된 사실 요지만 연결한다. 원문 검증·성향·점수는 변경하지 않는다."""
    facet_entries = {e["fact_id"]: e for f in traits["facets"].values()
                     for e in f.get("evidence", []) if e.get("fact_id")}
    index = traits.get("evidence_index") or {}
    evidence, statuses = {}, {}
    for fid in dict.fromkeys([*facet_entries, *fact_ids]):
        # 업장 이력 등 facet 밖의 사실도 같은 고객의 기존 index에서 찾는다.
        entry = index[fid] if fid in index else facet_entries.get(fid)
        gist = entry.get("gist") if isinstance(entry, dict) and entry.get("fact_id", fid) == fid else None
        found = isinstance(gist, str) and bool(gist.strip())
        evidence[fid] = gist if found else "설명 확인 필요"
        statuses[fid] = "provided_summary" if found else "needs_review"
    return evidence, statuses


def persona_bars(traits: dict) -> list[dict]:
    out = []
    for k in BAR_FACETS:
        f = traits["facets"].get(k)
        if not f:
            continue
        n = len(f.get("evidence", []))
        out.append(dict(key=k, label=f.get("label", k), level=round(f["level"], 3) if f.get("present") else None,
                        evidence_count=n, status="observed" if f.get("present") else "no_evidence"))
    return out


def _option(o: dict, score, building: str, feasible=True, blocked=()) -> dict:
    v = _venue_of(o)
    return dict(product_id=o["id"], product_label=o["label"], venue_id=v, venue_label=VENUE_LABEL.get(v, v), map_loc=_map_loc(v, building),
                score=None if score is None else round(score, 4), feasible=feasible, blocked=list(blocked), price=_price(o))


def conditions_default(turn: str = "dinner") -> dict:
    return dict(turn=turn, pricing="historical", party_size=2, stay=True, building="VISTA", event=False, product_levers={})


def build_world(cond: dict, allow_skip: bool = False):
    base = PRE["base"] if cond.get("event") else PRE["closed"]
    return turn_world(cond.get("turn", "dinner"), cond.get("pricing", "historical"), cond.get("party_size", 2),
                      product_levers=cond.get("product_levers") or None, base_levers=base, allow_skip=allow_skip)


def turn_view(persona_ids: list[str], cond: dict, personas: dict | None = None, states: dict | None = None) -> dict:
    """states: 에이전트별 직전 턴 상태(state_after 의 engine_state) — 하루 흐름에서 행사 턴의 이용 · 허기를 저녁 턴에 잇는다(없으면 독립 턴)."""
    P = personas or load_personas()
    cond = dict(conditions_default(cond.get("turn", "dinner")), **cond)
    states = states or {}
    _, excluded = build_world(cond)
    b = cond.get("building", "VISTA")
    custs = []
    for pid in persona_ids:
        tr = P[pid]["traits"]
        visit = dict(WD.default_visit(pid), party_size=cond.get("party_size", 2))
        st = states.get(pid)
        # Participation history (used) and food consumed (hunger) belong to this
        # customer only. Preserve the existing solo eligibility rule; no weights
        # or meal model changes. Participation without eating is not sufficient.
        ate = (st or {}).get("hunger", 1.0) < 1.0
        world, _ = build_world(cond, allow_skip=cond.get("turn") == "dinner" and ate)
        if not cond.get("stay", True):                              # 비투숙 — 객실 선택지 없음
            world = dict(world, offers=[o for o in world["offers"] if o["kind"] != "room_meal"])
        by = {o["id"]: o for o in world["offers"]}
        d = decide_turn(tr, visit, world, cond.get("turn", "dinner"), state=dict(st, used=set(st.get("used", []))) if st else None)
        ch = by[d["chosen"]["id"]]
        chosen = _option(ch, d["chosen"]["score"], b)
        others = [_option(by[x["id"]], x["score"], b, x["feasible"], x["blocked"]) for x in d["not_chosen"]]
        feas = [x for x in others if x["feasible"] and x["score"] is not None]
        runner = feas[0] if feas else None
        other_venue = next((x for x in feas if x["venue_id"] != chosen["venue_id"]), None)
        base = common_baseline(ch, visit, world, cond.get("turn", "dinner"))
        reasons = []
        for r in d["reasons"]:
            parts = split_reason(r, ch, base)
            reasons.append(dict(factor=r["factor"], value=r["value"], parts=parts, cls=classify(parts), facet=r.get("facet"),
                                fact_ids=r.get("fact_ids", []) if parts["review"] else [], note=r.get("note", "")))
        totals = {k: round(sum(x["parts"][k] for x in reasons), 4) for k in ("common", "review", "assumption")}
        evidence, evidence_status = display_evidence(tr, [fid for r in reasons for fid in r["fact_ids"]])
        custs.append(dict(
            persona_id=pid, persona=dict(label=P[pid]["label"], companion=P[pid].get("companion"), bars=persona_bars(tr)),
            choice=chosen,
            runner_up=None if not runner else dict(runner, margin=round(chosen["score"] - runner["score"], 4)),
            best_other_venue=None if not other_venue else dict(other_venue, margin=round(chosen["score"] - other_venue["score"], 4)),
            not_chosen=others, reasons=reasons, reason_totals=totals,
            evidence=evidence, evidence_status=evidence_status,
            state_after=dict(meal_done=d["state_after"]["hunger"] <= 0.3, used=d["state_after"]["used"],
                             engine_state=dict(hunger=d["state_after"]["hunger"], used=d["state_after"]["used"]), chained=bool(st))))
    return dict(turn=cond.get("turn", "dinner"), time=d["time"] if persona_ids else None, conditions=cond,
                building=dict(id=b, label=BUILDING_LABEL.get(b, b)),
                excluded=[dict(product_id=e["id"], product_label=e["name"], why=e["why"]) for e in excluded], customers=custs)


def turn_compare(before: dict, after: dict) -> dict:
    """같은 에이전트 · 같은 방문 조건에서 운영 조건만 다른 두 결과를 비교."""
    A = {c["persona_id"]: c for c in before["customers"]}
    out, summary = [], dict(changed=0, score_only=0, kept=0)
    for c in after["customers"]:
        b = A.get(c["persona_id"])
        if not b:
            continue
        same = b["choice"]["product_id"] == c["choice"]["product_id"]
        ds = round(c["choice"]["score"] - b["choice"]["score"], 4)
        status = "changed" if not same else ("score_only" if abs(ds) > 1e-6 else "kept")
        summary[status] += 1
        rb = {r["factor"]: r for r in b["reasons"]}
        ra = {r["factor"]: r for r in c["reasons"]}
        if same:
            deltas = [dict(factor=k, delta=round(ra.get(k, {}).get("value", 0) - rb.get(k, {}).get("value", 0), 4), cls=(ra.get(k) or rb.get(k))["cls"])
                      for k in set(ra) | set(rb)]
        else:      # 선택이 바뀐 경우: 새 선택의 항 − 이전 선택의 항(같은 조건의 두 선택지 비교가 아니라 전후 선택 비교)
            deltas = [dict(factor=k, delta=round(ra.get(k, {}).get("value", 0) - rb.get(k, {}).get("value", 0), 4), cls=(ra.get(k) or rb.get(k))["cls"])
                      for k in set(ra) | set(rb)]
        deltas = sorted([x for x in deltas if abs(x["delta"]) > 1e-6], key=lambda x: -abs(x["delta"]))[:2]
        kept_reason = None
        if same:
            alt = c["best_other_venue"] or c["runner_up"]
            kept_reason = None if not alt else dict(product_label=alt["product_label"], venue_label=alt["venue_label"], margin=alt["margin"])
        out.append(dict(persona_id=c["persona_id"], status=status,
                        before=dict(product_id=b["choice"]["product_id"], product_label=b["choice"]["product_label"], venue_id=b["choice"]["venue_id"], map_loc=b["choice"]["map_loc"], score=b["choice"]["score"]),
                        after=dict(product_id=c["choice"]["product_id"], product_label=c["choice"]["product_label"], venue_id=c["choice"]["venue_id"], map_loc=c["choice"]["map_loc"], score=c["choice"]["score"]),
                        venue_changed=b["choice"]["venue_id"] != c["choice"]["venue_id"], score_delta=ds, top_drivers=deltas, kept_reason=kept_reason))
    return dict(summary=summary, customers=out, same_visit=before["conditions"].get("party_size") == after["conditions"].get("party_size")
                and before["conditions"].get("stay") == after["conditions"].get("stay") and before["conditions"].get("building") == after["conditions"].get("building"))


def turn_meta(turn: str = "dinner", personas: dict | None = None) -> dict:
    """왼쪽 패널용 — 고를 수 있는 에이전트와 그 턴의 대표 상품(운영자가 바꿀 수 있는 속성 포함)."""
    P = personas or load_personas()
    cat = load_catalog()
    prods = [dict(product_id=p["id"], label=p["name"], venue_id=p["venue"], kind=p["kind"], price_krw=p["price_krw"], unit=p["unit"],
                  party_basis=p["party_basis"], party_basis_stated=p["party_basis_stated"], provisional_krw=p.get("provisional_sim_price_krw"),
                  source=p["source"], menu_as_of=MENU_AS_OF.get(p["source"]), levers=p["operator_levers"], unverified=p.get("unverified", []))
             for p in cat["products"] if p["turn"] == turn]
    return dict(turn=turn, personas=[dict(id=k, label=v["label"], companion=v.get("companion"), bars=persona_bars(v["traits"]), pipeline=v.get("pipeline", "R-BASE-1022")) for k, v in P.items()],
                products=prods, buildings=BUILDING_LABEL, sources=cat["sources"])
