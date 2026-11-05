"""Live receipts from the existing L5 converter. No planning or price rules here."""
import copy
import hashlib
import json
import threading
from collections import Counter, OrderedDict, defaultdict

import ledger_l5 as L5

VERSION = "live-l5-v1"
_CACHE = OrderedDict()
_LOCK = threading.Lock()
_LIMIT = 64


class ReceiptError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _amounts(rows):
    paid = sum(int(r["확정 결제액"]) for r in rows)
    assumed = sum(int(r["가정 결제액"]) for r in rows)
    return dict(paid_krw=paid, assumption_addition_krw=assumed-paid,
                with_assumptions_krw=assumed,
                unknown_count=sum(r["상태"] == "금액 미확인" for r in rows))


def _assemble(raw, info, traces):
    """Every amount, including the hotel total, comes from the same L5 rows."""
    agg = L5.aggregate(raw)
    levels = {}
    totals = _amounts(raw)
    for level in ("L4", "L3", "L2", "L1"):
        groups = []
        for key, values in agg[level].items():
            dims = key[2:]
            groups.append(dict(key=list(dims), quantity=values[0], paid_krw=values[1],
                               assumption_addition_krw=values[2]-values[1], with_assumptions_krw=values[2]))
        groups.sort(key=lambda g: (-g["paid_krw"], g["key"]))
        for group in groups:
            dims = group["key"]
            matches = [r for r in raw if (level == "L1" or r["L2 부문"] == dims[0])
                       and (level not in ("L3", "L4") or r["L3 업장"] == dims[1])
                       and (level != "L4" or r["L4 상품"] == dims[2])]
            group["unknown_count"] = sum(r["상태"] == "금액 미확인" for r in matches)
        levels[level] = groups
        if sum(g["paid_krw"] for g in groups) != totals["paid_krw"]:
            raise ReceiptError("영수증 집계 합계가 일치하지 않습니다")
    receipts = {}
    for pid, metadata in info.items():
        rr = [r for r in raw if r["내부 ID"] == pid]
        items = []
        for r in rr:
            trace = traces[r["_row_key"]]
            items.append(dict(row_id=r["_row_key"], customer_id=pid, department=r["L2 부문"], venue=r["L3 업장"],
                              venue_id=trace["loc"], product=r["L4 상품"], product_id=r["상품 ID"] or trace["act"],
                              time=r["시각"], status=r["상태"], quantity=r["수량"], unit_price_krw=r["단가"] if r["단가"] != "" else None,
                              unit_basis=r["과금 단위"], paid_krw=r["확정 결제액"],
                              assumption_addition_krw=r["가정 결제액"]-r["확정 결제액"],
                              price_basis=r["가격 근거"], price_grade=r["가격 등급"],
                              notes=[s for s in r["확인 메모"].split(" | ") if s], **trace))
        receipts[pid] = dict(metadata, **_amounts(rr), rows=items,
                             status_counts=dict(Counter(r["상태"] for r in rr)))
    venues = []
    for group in levels["L3"]:
        department, name = group["key"]
        rr = [r for r in raw if r["L2 부문"] == department and r["L3 업장"] == name]
        by_type = defaultdict(lambda: {"ids": set(), "paid_krw": 0})
        for r in rr:
            by_type[r["라이브러리 유형"]]["ids"].add(r["내부 ID"])
            by_type[r["라이브러리 유형"]]["paid_krw"] += r["확정 결제액"]
        venues.append(dict(group, name=name, department=department, team_count=len({r["내부 ID"] for r in rr}),
                           customer_ids=sorted({r["내부 ID"] for r in rr}),
                           unknown_count=sum(r["상태"] == "금액 미확인" for r in rr),
                           types=[dict(name=t, team_count=len(v["ids"]), paid_krw=v["paid_krw"])
                                  for t, v in sorted(by_type.items(), key=lambda x: (-len(x[1]["ids"]), x[0]))]))
    if sum(r["paid_krw"] for r in receipts.values()) != totals["paid_krw"]:
        raise ReceiptError("고객 영수증과 호텔 합계가 일치하지 않습니다")
    return dict(receipts=receipts, levels=levels, venues=venues, totals=totals,
                team_count=len(info), customer_types=sorted({v["customer_type"] for v in info.values()}),
                checks=dict(receipts_equal_L4_L3_L2_L1=True, duplicate_transactions=0))


def register(flow, request, source="live_engine"):
    """Consume the already-computed flow exactly once; never call the engine."""
    if flow.get("error") or not flow.get("plans"):
        raise ReceiptError("영수증을 만들 실행 결과가 없습니다")
    context = {k: copy.deepcopy(request[k]) for k in ("event", "seed", "intervention", "visit_override", "product_levers") if k in request}
    context.setdefault("seed", 0)
    effective_event = bool(request.get("event") or request.get("intervention") == "wine_fair_1300")
    context["event"] = effective_event
    run_id = _digest(dict(version=VERSION, flow=flow, context=context, source=source))
    with _LOCK:
        if run_id in _CACHE:
            _CACHE.move_to_end(run_id)
            return copy.deepcopy(_CACHE[run_id]["ledger"])
    meta = dict(types=L5.load_types(), no=L5.display_no())
    menu = L5.load_menu()
    raw, info, traces = [], {}, {}
    for pid in flow["plans"]:
        rr, counts, bf, base, visit = L5.day_rows(pid, effective_event, flow, "하루(실행)", 1, meta)
        rm = L5.room_row(base, visit, bf, menu, 0 if visit.get("phase") == "checkout" or not visit.get("stay") else 1)
        charge_scenes = [(i, s) for i, s in enumerate(flow["plans"][pid].get("scenes", []))
                         if ((s.get("basis") or {}).get("charge") or {}).get("status") not in (None, "구매 없음")]
        if len(rr) != len(charge_scenes):
            raise ReceiptError("장면과 거래 행의 연결이 일치하지 않습니다")
        for row, (index, scene) in zip(rr, charge_scenes):
            key = _digest([run_id, pid, index])[:24]
            row["_row_key"] = key
            traces[key] = dict(scene_index=index, loc=scene.get("loc"), act=scene.get("act"), turn=scene.get("turn"),
                               decision_id=f"{pid}|{scene['turn']}|{row['시각']}" if scene.get("turn") else None,
                               fact_ids=list((scene.get("basis") or {}).get("facts") or []),
                               t0=scene["t0"], t1=scene["t1"], meal=scene.get("meal"))
        direct = sum((((s.get("basis") or {}).get("charge") or {}).get("krw") or 0)
                     for s in flow["plans"][pid].get("scenes", [])
                     if ((s.get("basis") or {}).get("charge") or {}).get("status") == "유료")
        if sum(r["확정 결제액"] for r in rr) != direct:
            raise ReceiptError("엔진 장면 지출과 영수증이 일치하지 않습니다")
        if rm:
            key = _digest([run_id, pid, "room_night"])[:24]; rm["_row_key"] = key; rr.append(rm)
            traces[key] = dict(scene_index=None, loc=f"{visit.get('building')}_ROOM", act="room_night", turn=None,
                               decision_id=None, fact_ids=[], t0=None, t1=None, meal=None)
        raw.extend(rr)
        info[pid] = dict(customer_id=pid, display_id=meta["no"].get(pid, pid), customer_type=meta["types"].get(pid) or "유형 확인 중",
                         stay=bool(visit.get("stay")), party_size=visit.get("party_size"), phase=visit.get("phase"),
                         day_window=[min(s["t0"] for s in flow["plans"][pid]["scenes"]), max(s["t1"] for s in flow["plans"][pid]["scenes"])] if flow["plans"][pid]["scenes"] else None,
                         building=visit.get("building"), engine_scene_paid_krw=direct)
    ledger = dict(version=VERSION, run_id=run_id, source=source, context=context,
                  input_missing=list(flow.get("input_missing") or []), **_assemble(raw, info, traces))
    ledger["checks"]["engine_scene_equal_receipt"] = True
    with _LOCK:
        _CACHE[run_id] = dict(ledger=copy.deepcopy(ledger), raw=raw, info=info, traces=traces)
        while len(_CACHE) > _LIMIT: _CACHE.popitem(last=False)
    return ledger


def lookup(run_id, customer_type=None, stay_status="all"):
    if not isinstance(run_id, str) or len(run_id) != 64:
        raise ReceiptError("실행 결과를 다시 계산해 주세요")
    if stay_status not in ("all", "staying", "non_staying"):
        raise ReceiptError("투숙 조건을 확인해 주세요")
    with _LOCK:
        entry = copy.deepcopy(_CACHE.get(run_id))
    if entry is None:
        raise ReceiptError("실행 기록이 만료되었습니다. 같은 조건으로 다시 계산해 주세요")
    info = {p: i for p, i in entry["info"].items() if (not customer_type or i["customer_type"] == customer_type)
            and (stay_status == "all" or i["stay"] == (stay_status == "staying"))}
    if customer_type and customer_type not in entry["ledger"]["customer_types"]:
        raise ReceiptError("고객 유형을 확인해 주세요")
    raw = [r for r in entry["raw"] if r["내부 ID"] in info]
    return dict(version=VERSION, run_id=run_id, source=entry["ledger"]["source"], context=entry["ledger"]["context"],
                input_missing=entry["ledger"]["input_missing"], filters=dict(customer_type=customer_type, stay_status=stay_status),
                **_assemble(raw, info, entry["traces"]))


def _slot_rows(receipt):
    counters = Counter()
    out = {}
    for row in receipt["rows"]:
        # Meals and quantitative decisions retain their decision role even if the venue changes.
        slot = row.get("turn") or row.get("meal") or row["act"]
        counters[slot] += 1
        out[(slot, counters[slot])] = row
    return out


def _decompose(before, after):
    parts = {k: 0 for k in ("selection", "price_condition", "time_rule", "interaction")}
    transitions = []
    a, b = _slot_rows(before), _slot_rows(after)
    for key in sorted(set(a) | set(b)):
        left, right = a.get(key), b.get(key)
        delta = (right["paid_krw"] if right else 0) - (left["paid_krw"] if left else 0)
        kind = "interaction"
        if left and right:
            same_product = (left["venue"], left["product_id"]) == (right["venue"], right["product_id"])
            if not same_product and key[0] in ("breakfast", "lunch", "dinner", "event"):
                kind = "selection"
                transitions.append(dict(slot=key[0], before_venue=left["venue"], after_venue=right["venue"],
                                        before_product=left["product"], after_product=right["product"], delta_krw=delta,
                                        before_decision_id=left.get("decision_id"), after_decision_id=right.get("decision_id")))
            elif same_product and left["quantity"] == right["quantity"] and (
                    left["status"] != right["status"] or left["unit_price_krw"] != right["unit_price_krw"]):
                kind = "price_condition"
        elif before.get("phase") != after.get("phase") or before.get("stay") != after.get("stay"):
            row = left or right
            other = after if left else before
            window = other.get("day_window")
            if window and row.get("t0") is not None and (row["t0"] >= window[1] or row["t1"] <= window[0]):
                kind = "time_rule"
        parts[kind] += delta
    expected = after["paid_krw"] - before["paid_krw"]
    if sum(parts.values()) != expected:
        raise ReceiptError("상황 비교 차액이 일치하지 않습니다")
    return parts, transitions


def compare(baseline_id, scenario_id, customer_type=None, stay_status="all"):
    before = lookup(baseline_id, customer_type, stay_status)
    after = lookup(scenario_id, customer_type, stay_status)
    if before["source"] != "live_engine" or after["source"] != "live_engine":
        raise ReceiptError("상황 비교는 실제 엔진 실행 결과끼리만 제공합니다")
    if before["context"].get("seed") != after["context"].get("seed"):
        raise ReceiptError("같은 시드의 실행끼리 비교해 주세요")
    if set(before["receipts"]) != set(after["receipts"]):
        return dict(comparable=False, code="COHORT_CHANGED", baseline_id=baseline_id, scenario_id=scenario_id,
                    message="필터 적용 후 고객 집합이 다릅니다. 전체 고객 조건에서 다시 비교해 주세요",
                    before_team_count=before["team_count"], after_team_count=after["team_count"], customers={}, venues=[])
    customers = {}
    for pid in before["receipts"]:
        a, b = before["receipts"][pid], after["receipts"][pid]
        parts, transitions = _decompose(a, b)
        departments = []
        for name in ("F&B", "ROOM", "레저", "미매핑"):
            x = sum(r["paid_krw"] for r in a["rows"] if r["department"] == name)
            y = sum(r["paid_krw"] for r in b["rows"] if r["department"] == name)
            if x or y: departments.append(dict(name=name, before_krw=x, after_krw=y, delta_krw=y-x))
        if sum(r["delta_krw"] for r in departments) != b["paid_krw"]-a["paid_krw"]:
            raise ReceiptError("부문별 비교 차액이 일치하지 않습니다")
        customers[pid] = dict(before_context=dict(before["context"], stay=a["stay"], phase=a["phase"], building=a["building"], party_size=a["party_size"]),
                              after_context=dict(after["context"], stay=b["stay"], phase=b["phase"], building=b["building"], party_size=b["party_size"]),
                              before_krw=a["paid_krw"], after_krw=b["paid_krw"], delta_krw=b["paid_krw"]-a["paid_krw"],
                              before_assumed_krw=a["with_assumptions_krw"], after_assumed_krw=b["with_assumptions_krw"],
                              departments=departments, decomposition=parts, transitions=transitions)
    a={tuple(v["key"]):v for v in before["venues"]};b={tuple(v["key"]):v for v in after["venues"]}
    venues=[]
    for key in sorted(set(a)|set(b)):
        x,y=a.get(key,{}),b.get(key,{})
        venues.append(dict(key=list(key),name=key[1],department=key[0],before_krw=x.get("paid_krw",0),after_krw=y.get("paid_krw",0),
                           delta_krw=y.get("paid_krw",0)-x.get("paid_krw",0),before_teams=x.get("team_count",0),after_teams=y.get("team_count",0)))
    delta=after["totals"]["paid_krw"]-before["totals"]["paid_krw"]
    if sum(v["delta_krw"] for v in venues)!=delta or sum(c["delta_krw"] for c in customers.values())!=delta:
        raise ReceiptError("고객별·업장별 비교 차액이 일치하지 않습니다")
    return dict(comparable=True,baseline_id=baseline_id,scenario_id=scenario_id,team_count=after["team_count"],
                before_krw=before["totals"]["paid_krw"],after_krw=after["totals"]["paid_krw"],delta_krw=delta,
                before_context=before["context"],after_context=after["context"],customers=customers,venues=venues,
                caveat="같은 행동 단위의 기록을 비교한 분류입니다. 상호작용을 분리할 수 없는 차액은 복합 변화로 남깁니다.")
