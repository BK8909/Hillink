"""Live L5 receipts; source-backed room pricing is delegated to room_revenue."""
from bounded_records import BoundedRecords
import copy
import hashlib
import json
import threading
from decimal import Decimal
from collections import Counter, OrderedDict, defaultdict

import ledger_l5 as L5

VERSION = "live-l5-v2"
_CACHE = BoundedRecords(64,128*1024*1024)
_LOCK = threading.Lock()
_LIMIT = 64


class ReceiptError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _tax_amounts(rows):
    known = [Decimal(str(r['_net_ex_vat_krw'])) if r.get('_net_ex_vat_krw') is not None else Decimal(0) for r in rows if r.get('_net_ex_vat_krw') is not None or (r['확정 결제액'] == 0 and r['상태'] != '금액 미확인')]
    unknown = len(rows)-len(known)
    total = float(sum(known, Decimal(0)))
    return dict(net_revenue_krw=None if unknown else total, known_net_revenue_krw=total, tax_unknown_count=unknown)


def _amounts(rows):
    paid = sum(int(r["확정 결제액"]) for r in rows)
    assumed = sum(int(r["가정 결제액"]) for r in rows)
    return dict(paid_krw=paid, assumption_addition_krw=assumed-paid,
                with_assumptions_krw=assumed,
                unknown_count=sum(r["상태"] == "금액 미확인" for r in rows), **_tax_amounts(rows))


def _dedupe_rows(raw):
    """Deduplicate repeated simulation rows by stable row id; reject collisions."""
    seen, unique = {}, []
    for row in raw:
        key = row["_row_key"]
        value = _digest({k: v for k, v in row.items() if k != "_row_key"})
        if key in seen:
            if seen[key] != value:
                raise ReceiptError("같은 시뮬레이션 행 ID에 서로 다른 소비 내용이 있습니다")
            continue
        seen[key] = value
        unique.append(row)
    return unique, len(raw) - len(unique)


def _assemble(raw, info, traces):
    """Every amount, including the hotel total, comes from the same L5 rows."""
    raw, duplicate_rows = _dedupe_rows(raw)
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
            group.update(_tax_amounts(matches))
            units = defaultdict(int)
            for row in matches:
                unit = row.get("과금 단위") or "단위 미확인"
                units[unit] += int(row.get("수량") or 0)
            group["quantity_by_unit"] = [dict(unit=u, quantity=n) for u, n in sorted(units.items())]
            group["quantity"] = next(iter(units.values())) if len(units) == 1 else None
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
            items.append(dict(row_id=r["_row_key"], simulation_entry_id=r["_row_key"], actual_transaction_id=None,
                              customer_id=pid, department=r["L2 부문"], venue=r["L3 업장"],
                              venue_id=trace["loc"], product=r["L4 상품"], product_id=r["상품 ID"] or None,
                              action_id=trace["act"],
                              time=r["시각"], status=r["상태"], quantity=r["수량"], unit_price_krw=r["단가"] if r["단가"] != "" else None,
                              unit_basis=r["과금 단위"], billing_quantity=int(r["판매 수량"]) if r.get("판매 수량") not in (None, "") else None,
                              billing_unit=r.get("판매 단위") or None, participant_count=int(r["이용 인원"]) if r.get("이용 인원") not in (None, "") else None,
                              paid_krw=r["확정 결제액"],
                              assumption_addition_krw=r["가정 결제액"]-r["확정 결제액"],
                              amount_status=("SIMULATED_CHARGE" if r["상태"] in ("실결제", "가상 결제") else "ASSUMED" if r["가정 결제액"] else "UNKNOWN" if r["상태"] == "금액 미확인" else "NO_CHARGE"),
                              purchase_status=("SIMULATED_CHARGE" if r["상태"] in ("실결제", "가상 결제") else "PACKAGE_INCLUDED" if r["상태"] == "포함" else "FREE_USE" if r["상태"] == "무료" else "UNKNOWN_AMOUNT" if r["상태"] == "금액 미확인" else "UNKNOWN"),
                              tax_status="UNKNOWN", net_revenue_krw=None,
                              price_source_status="ENGINE_CHARGE_BASIS_PRESENT; VERIFIED_CATALOG_NOT_APPLIED" if r["가격 근거"] else "UNMAPPED",
                              quantity_role="BILLING_UNIT_UNVERIFIED" if not r["과금 단위"] else "ENGINE_ROW_QUANTITY",
                              price_basis=r["가격 근거"], price_grade=r["가격 등급"],
                              notes=[s for s in r["확인 메모"].split(" | ") if s], **trace))
            if r.get('선택 SKU 계약'):
                contract=copy.deepcopy(r['선택 SKU 계약'])
                items[-1].update(selection_id=contract.get('selection_id'),sku_contract=contract,product_sku_id=contract['sku_id'],
                    price_source_status=contract['price_status'],price_status=contract['price_status'],
                    current_sale_confirmed=False,reservation_confirmed=False)
                if contract.get("billing_unit")=="portion_person_mapping_pending":
                    items[-1]["quantity_role"]="PARTICIPANTS_ONLY_BILLING_UNIT_UNVERIFIED"
            if r.get('_room_pricing'):
                pricing=copy.deepcopy(r['_room_pricing'])
                items[-1].update(room_pricing=pricing, stay_id=pricing['stay_id'], room_id=pricing['room_id'],
                                 room_count=pricing['room_count'], price_status=pricing['price_status'],
                                 price_source_status=pricing['price_status'], quantity_role='ROOM_NIGHT_NOT_PARTICIPANT_COUNT',
                                 virtual_gross_krw=pricing['virtual_gross_krw'], tax_status=pricing['tax_status'],
                                 net_revenue_krw=pricing['net_ex_vat_krw'], actual_cash_observed=False)
        receipts[pid] = dict(metadata, **_amounts(rr), rows=items,
                             actions=copy.deepcopy(metadata.get("actions", [])),
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
                aggregation_contract=dict(
                    hillink_row_grain="one simulation run × one customer team × one selected action/charge row",
                    ontology_row_grain="service date × pool × product × customer dimensions (already aggregated)",
                    direct_row_mapping=False,
                    comparison_rollup_keys=["service date", "venue_id", "product_id only when explicitly known", "verified customer dimensions only"],
                    quantity_views=["billing_quantity + billing_unit", "participant_count"],
                    quantity_views_are_alternatives=True,
                    excluded_from_paid_sum=["ASSUMED", "UNKNOWN", "PACKAGE_INCLUDED", "FREE_USE", "NO_PURCHASE"],
                    pos_actuals_supplied=False),
                checks=dict(receipts_equal_L4_L3_L2_L1=True, duplicate_transactions=None,
                            duplicate_simulation_rows=duplicate_rows,
                            net_revenue_calculated=False, tax_status="UNKNOWN",
                            actual_pos_transactions=None, actual_pos_data_supplied=False))


def register(flow, request, source="live_engine"):
    """Consume the already-computed flow exactly once; never call the engine."""
    if flow.get("visit_days"):
        return register_visit(flow, request, source)
    if flow.get("error") or not flow.get("plans"):
        raise ReceiptError("영수증을 만들 실행 결과가 없습니다")
    context = {k: copy.deepcopy(request[k]) for k in ("personas", "mode", "event", "seed", "intervention", "visit_override", "product_levers", "observe") if k in request}
    context["personas"] = list(request.get("personas") or flow.get("plans", {}).keys())
    context["mode"] = request.get("mode") or ("one" if len(context["personas"]) == 1 else "many")
    context["engine_version"] = (flow.get("engine") or {}).get("version")
    context["profile_sha"] = flow.get("profile_sha")
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
        scene_row_ids = {}
        for row, (index, scene) in zip(rr, charge_scenes):
            key = _digest([run_id, pid, index])[:24]
            row["_row_key"] = key
            scene_row_ids[index] = key
            traces[key] = dict(scene_index=index, loc=scene.get("loc"), act=scene.get("act"), turn=scene.get("turn"),
                               decision_id=f"{pid}|{scene['turn']}|{row['시각']}" if scene.get("turn") else None,
                               fact_ids=list((scene.get("basis") or {}).get("facts") or []),
                               package_entitlement_id=((scene.get("basis") or {}).get("charge") or {}).get("entitlement_id"),
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
        actions, occurrence, = [], Counter()
        for index, scene in enumerate(flow["plans"][pid].get("scenes", [])):
            basis = scene.get("basis") or {}
            charge = basis.get("charge") or {}
            status = charge.get("status")
            choice = basis.get("choice") or {}
            slot = scene.get("turn") or scene.get("meal") or scene.get("act") or "activity"
            occurrence[slot] += 1
            action = dict(action_id=f"{pid}|{index}", slot=slot, occurrence=occurrence[slot],
                          turn=scene.get("turn"), decision_id=f"{pid}|{scene['turn']}|{scene.get('t0')}" if scene.get("turn") else None,
                          time=f"{scene['t0'] // 60:02d}:{scene['t0'] % 60:02d}" if scene.get("t0") is not None else None,
                          venue_id=scene.get("loc"), action=scene.get("act"), label=scene.get("label"),
                          action_status="SIMULATED_SELECTED_ACTION",
                          purchase_status={"유료":"SIMULATED_CHARGE", "포함":"PACKAGE_INCLUDED", "무료":"FREE_USE", "가격 미정":"UNKNOWN_AMOUNT", "구매 없음":"NO_PURCHASE"}.get(status, "NO_PURCHASE"),
                          amount_krw=charge.get("krw") if status == "유료" else 0 if status in ("포함", "무료", "구매 없음") else None,
                          amount_is_in_receipt=bool(index in scene_row_ids), row_id=scene_row_ids.get(index),
                          fact_ids=list(basis.get("facts") or []),
                          considered=[dict(status="NOT_SELECTED", label=x.get("label"), reason=x.get("note")) for x in (choice.get("considered") or [])],
                          blocked=[dict(status="NOT_SELECTED_BLOCKED", label=x.get("label"), reason=x.get("note")) for x in (choice.get("blocked") or [])])
            if charge.get("external_spend"):   # e.g. external delivery: outside the hotel ledger, amount unknown
                action["external_spend"] = dict(charge["external_spend"])
            actions.append(action)
        visit_layer = visit.get("layer") or "unknown"
        visit_note = {
            "review": "방문 조건이 후기 근거에 연결됨",
            "mixed": "후기 정보와 유형·시드 기반 모델 구성이 함께 반영됨",
            "generated": "방문 조건은 유형·성향·시드 기반 모델 가정이며 실제 방문 사실이 아님",
        }.get(visit_layer, "방문 조건 출처 미확인")
        visit_override = (request.get("visit_override") or {}).get(pid) or {}
        if visit_override.get("stay") is False:
            visit_note = "비투숙은 사용자가 선택한 가상 상황이며, 동행 인원은 고객 유형·성향·시드 기반 엔진 구성값입니다"
        info[pid] = dict(customer_id=pid, display_id=meta["no"].get(pid, pid), customer_type=meta["types"].get(pid) or "유형 확인 중",
                         stay=bool(visit.get("stay")), party_size=visit.get("party_size"), phase=visit.get("phase"), nights=visit.get("nights"),
                         visit_profile_layer=visit_layer, visit_profile_note=visit_note,
                         day_window=[min(s["t0"] for s in flow["plans"][pid]["scenes"]), max(s["t1"] for s in flow["plans"][pid]["scenes"])] if flow["plans"][pid]["scenes"] else None,
                         building=visit.get("building"), engine_scene_paid_krw=direct, actions=actions)
    import hotel_ledger
    raw=hotel_ledger.expand(raw,traces)
    ledger = dict(version=VERSION, run_id=run_id, source=source, context=context,
                  input_missing=list(flow.get("input_missing") or []), **_assemble(raw, info, traces))
    ledger["checks"]["engine_scene_equal_receipt"] = True
    hotel_ledger.annotate(ledger)
    ledger["external_spend"] = _external_summary(ledger)
    if source != "stored_demo":
        from consumption_audit import inspect as audit_consumption
        ledger["consumption_audit"] = audit_consumption(flow, ledger)
    with _LOCK:
        _CACHE[run_id] = dict(ledger=copy.deepcopy(ledger), raw=raw, info=info, traces=traces)
        while len(_CACHE) > _LIMIT: _CACHE.popitem(last=False)
    return ledger


def register_visit(flow, request, source="live_engine"):
    """Roll daily L5 rows from one stateful visit into one visit-level ledger."""
    if flow.get("error") or not flow.get("visit_days") or not flow.get("plans"):
        raise ReceiptError("방문 전체 영수증을 만들 실행 결과가 없습니다")
    visit_meta = flow.get("visit") or {}
    personas = list(request.get("personas") or flow["plans"].keys())
    duration = request.get("duration")
    expected_nights = {"day_visit": 0, "stay_1": 1, "stay_2": 2, "stay_3": 3}.get(duration)
    if expected_nights is None:
        raise ReceiptError("지원하지 않는 체류 기간입니다")
    days = flow["visit_days"]
    if len(days) != expected_nights + 1 or len({d.get("date") for d in days}) != len(days):
        raise ReceiptError("방문 일자 수 또는 날짜 중복이 체류 기간과 일치하지 않습니다")
    profile_shas = {d.get("flow", {}).get("profile_sha") for d in days}
    if None in profile_shas or len(profile_shas) != 1:
        raise ReceiptError("체류 날짜 사이 고객 프로필 입력이 달라졌습니다")
    context = dict(personas=personas, mode="one" if len(personas) == 1 else "many", event=request.get("event_mode") == "wine",
                   seed=request.get("seed", 0), duration=duration, start_date=visit_meta.get("start_date"),
                   engine_version=(flow.get("engine") or {}).get("version"), profile_sha=next(iter(profile_shas)),
                   price_version=L5.VERSION if hasattr(L5, "VERSION") else None)
    scenario=visit_meta.get('scenario_snapshot')
    if scenario:
        context.update(scenario_id=scenario['scenario_id'],scenario_snapshot_sha256=scenario['snapshot_sha256'],event_card_id=scenario['event_card_id'],event_label=scenario['sources'][0]['record']['행사 · 상품명'],scenario_enabled=scenario['enabled'])
    import room_revenue
    context["room_valuation_version"] = room_revenue.NATIVE_VERSION if (flow.get("engine") or {}).get("behavior_engine") in ("m4", "m4_c01") else "virtual-room-revenue-v1"
    context["room_price_source_sha256"] = room_revenue.SOURCE_SHA256
    if context["room_valuation_version"] == room_revenue.NATIVE_VERSION:
        context["room_payment_basis"] = "2026_PROJECT_VIRTUAL_MODEL_NOT_OBSERVED_CASH"
    if flow.get("shared_world"):
        context["simulation_mode"] = "shared_world"
    if request.get("package_id"):
        context["package_id"] = request["package_id"]
    run_id = _digest(dict(version=VERSION, visit_id=flow.get("visit_id"), context=context, source=source))
    with _LOCK:
        cached = _CACHE.get(run_id)
        if cached:
            _CACHE.move_to_end(run_id)
            return copy.deepcopy(cached["ledger"])
    raw, traces, info = [], {}, {}
    day_totals = []
    native_keys = set()
    native_rooms = context["room_valuation_version"] == room_revenue.NATIVE_VERSION
    for day in days:
        day_flow = day.get("flow") or {}
        day_request = dict(personas=personas, mode=context["mode"], event=bool(day.get("event")), seed=context["seed"],
                           intervention="none", observe="weekend" if duration != "day_visit" else "day")
        daily = register(day_flow, day_request, source=source)
        with _LOCK:
            cached_day = copy.deepcopy(_CACHE.get(daily["run_id"]))
        if cached_day is None:
            raise ReceiptError("날짜별 실행 원장이 만료되어 방문 합계를 만들 수 없습니다")
        row_start = len(raw)
        daily_paid = daily_assumed = daily_unknown = 0
        for row in cached_day["raw"]:
            row = copy.deepcopy(row)
            if request.get("package_id") and row.get("장면") == "room_night":
                package = visit_meta.get("package_context") or {}
                row["L4 상품"] = f"객실 패키지 · {package.get('label', request['package_id'])} · 박당 거래 미확인"
                row["단가"] = ""
                row["확정 결제액"] = row["결제액"] = row["가정 결제액"] = 0
                row["상태"] = "금액 미확인"
                row["확인 메모"] = "선택 시나리오 패키지 · 예약/결제 미관측 · 가격 자동 반영 안 함"
            if native_rooms and row.get("장면") == "room_night":
                pricing=room_revenue.native_price(flow,row["내부 ID"],day["date"],day["day_index"]-1,expected_nights)
                unique=(pricing['stay_id'],pricing['room_id'],day['date'])
                if unique in native_keys: raise ReceiptError("동일 객실 숙박일 중복 거래")
                native_keys.add(unique)
                room_revenue.apply_native(row,pricing)
            old_key = row["_row_key"]
            new_key = _digest([run_id, day["day_index"], row["내부 ID"], old_key])[:24]
            row["_row_key"] = new_key
            row["거래일"] = day["date"]
            row["체류 일차"] = day["day_index"]
            row["방문 ID"] = flow["visit_id"]
            # one scenario label across dates; actual event availability stays in its own trace field.
            row["행사"] = "와인페어 시나리오" if request.get("event_mode") == "wine" else "행사 없음"
            trace = copy.deepcopy(cached_day["traces"][old_key])
            trace.update(run_id=run_id, visit_id=flow["visit_id"], visit_day=day["day_index"], visit_date=day["date"],
                         day_phase=day["phase"], event_available=bool(day.get("event")))
            if row.get("_room_pricing"): trace["room_pricing"] = copy.deepcopy(row["_room_pricing"])
            traces[new_key] = trace
            raw.append(row)
            daily_paid += int(row.get("확정 결제액") or 0)
            daily_assumed += int(row.get("가정 결제액") or 0)
            daily_unknown += row.get("상태") == "금액 미확인"
        day_totals.append(dict(day_index=day["day_index"], date=day["date"], phase=day["phase"],
                               event_available=bool(day.get("event")), paid_krw=daily_paid,
                               assumption_addition_krw=daily_assumed-daily_paid,
                               with_assumptions_krw=daily_assumed, unknown_count=daily_unknown,
                               transaction_rows=len(raw)-row_start))
        for pid, daily_info in cached_day["info"].items():
            existing = info.get(pid)
            if existing is None:
                existing = copy.deepcopy(daily_info)
                existing["actions"] = []
                existing["day_windows"] = []
                # Day totals are added below for every day, including the first one.
                # Starting from the copied day-1 amount counted day 1 twice (A04: 274,000 vs 182,000).
                existing["engine_scene_paid_krw"] = 0
                info[pid] = existing
            existing["actions"].extend(dict(a, visit_day=day["day_index"], visit_date=day["date"]) for a in daily_info.get("actions", []))
            if daily_info.get("day_window"):
                existing["day_windows"].append(dict(day_index=day["day_index"], date=day["date"], window=daily_info["day_window"]))
            existing["engine_scene_paid_krw"] += daily_info.get("engine_scene_paid_krw", 0)
            existing["stay"] = expected_nights > 0
            existing["nights"] = expected_nights
            existing["duration"] = duration
            existing["visit_id"] = flow.get("visit_id")
            existing["phase"] = "visit" if expected_nights == 0 else "stay"
            existing["visit_profile_note"] = ("패키지 선택은 사용자가 설정한 가상 시나리오이며 실제 예약 사실이 아닙니다." if request.get("package_id") else "사용자가 설정한 가상 체류 기간. 건물·동행은 고객별 프로필 해결값이며 원문 사실과 모델 가정을 구분합니다.")
    import hotel_ledger
    raw=hotel_ledger.expand(raw,traces)
    for day_total in day_totals:day_total['transaction_rows']=sum(r['체류 일차']==day_total['day_index'] for r in raw)
    if set(info) != set(flow["plans"]):
        raise ReceiptError("일별 영수증 고객 집합이 방문 실행 고객과 다릅니다")
    ledger = dict(version=VERSION, run_id=run_id, source=source, context=context,
                  input_missing=list(flow.get("input_missing") or []), **_assemble(raw, info, traces))
    totals = ledger["totals"]
    if sum(d["paid_krw"] for d in day_totals) != totals["paid_krw"]:
        raise ReceiptError("일자별 소비 합계가 체류 전체 소비와 일치하지 않습니다")
    room_rows = [r for r in raw if r.get("장면") == "room_night"]
    if expected_nights == 0 and room_rows or expected_nights > 0 and len(room_rows) != expected_nights * len(personas):
        raise ReceiptError("객실박 거래 행이 선택한 체류 기간과 일치하지 않습니다")
    visit_ledger = dict(visit_id=flow.get("visit_id"), duration=duration, nights=expected_nights,
                        start_date=visit_meta.get("start_date"), day_count=len(days), days=day_totals,
                        event_mode=visit_meta.get("event_mode"), event_dates=[d["date"] for d in days if d.get("event")],
                        visit_inputs_sha=flow.get("visit_inputs_sha"),
                        room_assumption_krw=0 if native_rooms else sum(int(r.get("가정 결제액") or 0) for r in room_rows),
                        room_paid_krw=sum(int(r.get("확정 결제액") or 0) for r in room_rows),
                        historical_menu_room_assumption_krw=sum(int(r.get("_legacy_room_assumption_krw") or 0) for r in room_rows),
                        room_price_policy="NATIVE_ROOM_L5_VIRTUAL_MODEL_OR_VERIFIED_CATALOG_NOT_ACTUAL_CASH" if native_rooms else visit_meta.get("room_price_policy"),
                        total_estimated_payable_krw=totals["with_assumptions_krw"] if not totals["unknown_count"] else None)
    if request.get("package_id"):
        visit_ledger.update(package_context=copy.deepcopy(visit_meta.get("package_context")),
                            benefit_usage={pid: copy.deepcopy((flow.get("visits", {}).get(pid, {}).get("benefit_usage") or {})) for pid in personas})
    ledger["visit"] = visit_ledger
    import room_revenue
    ledger["virtual_revenue"] = room_revenue.build(flow, ledger)
    valuations = {r["row_id"]:r for r in ledger["virtual_revenue"]["rows"]}
    for receipt in ledger["receipts"].values():
        for row in receipt["rows"]:
            row["virtual_valuation"] = copy.deepcopy(valuations[row["row_id"]])
            traces[row["row_id"]]["virtual_valuation"] = copy.deepcopy(valuations[row["row_id"]])
    if flow.get("shared_world"):
        import visit_operations
        ledger["operations"] = visit_operations.build(flow, ledger)
        ledger["shared_world"] = {k:copy.deepcopy(flow["shared_world"][k]) for k in ("mode","customer_ids","capacity_and_queues_supported","customer_interactions_supported")}
    import hotel_ledger
    hotel_ledger.annotate(ledger)
    ledger["external_spend"] = _external_summary(ledger)
    ledger["checks"].update(day_totals_equal_visit_total=True, room_nights_equal_duration=True,
                            date_rows_unique=True, visit_id_attached=True)
    from consumption_audit import inspect as audit_consumption
    ledger["consumption_audit"] = audit_consumption(flow, ledger)
    with _LOCK:
        _CACHE[run_id] = dict(ledger=copy.deepcopy(ledger), raw=raw, info=info, traces=traces)
        while len(_CACHE) > _LIMIT:
            _CACHE.popitem(last=False)
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
    result = dict(version=VERSION, run_id=run_id, source=entry["ledger"]["source"], context=entry["ledger"]["context"],
                input_missing=entry["ledger"]["input_missing"], filters=dict(customer_type=customer_type, stay_status=stay_status),
                **_assemble(raw, info, entry["traces"]))
    import hotel_ledger
    hotel_ledger.annotate(result)
    if set(info) == set(entry["info"]) and entry["ledger"].get("consumption_audit"):
        result["consumption_audit"] = copy.deepcopy(entry["ledger"]["consumption_audit"])
    return result


def _slot_rows(receipt):
    counters = Counter()
    out = {}
    for row in receipt["rows"]:
        # Meals and quantitative decisions retain their decision role even if the venue changes.
        slot = row.get("turn") or row.get("meal") or row["act"]
        counters[slot] += 1
        out[(row.get("visit_day", 1), slot, counters[slot])] = row
    return out


def _decompose(before, after):
    parts = {k: 0 for k in ("selection", "price_condition", "time_rule", "interaction")}
    transitions = []
    a, b = _slot_rows(before), _slot_rows(after)
    row_changes = []
    for key in sorted(set(a) | set(b)):
        left, right = a.get(key), b.get(key)
        delta = (right["paid_krw"] if right else 0) - (left["paid_krw"] if left else 0)
        if left is None or right is None or (left["venue_id"], left["product_id"], left["quantity"], left["status"], left["paid_krw"], left.get("assumption_addition_krw")) != (right["venue_id"], right["product_id"], right["quantity"], right["status"], right["paid_krw"], right.get("assumption_addition_krw")):
            row_changes.append(dict(visit_day=key[0], slot=key[-2], change="ADDED" if left is None else "REMOVED" if right is None else "CHANGED",
                                    before=copy.deepcopy(left), after=copy.deepcopy(right), delta_krw=delta,
                                    before_fact_ids=list((left or {}).get("fact_ids") or []),
                                    after_fact_ids=list((right or {}).get("fact_ids") or [])))
        kind = "interaction"
        if left and right:
            same_product = (left["venue"], left["product_id"]) == (right["venue"], right["product_id"])
            if not same_product and key[-2] in ("breakfast", "lunch", "dinner", "event"):
                kind = "selection"
                transitions.append(dict(visit_day=key[0], slot=key[-2], before_venue=left["venue"], after_venue=right["venue"],
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
    return parts, transitions, row_changes


def _venue_deltas(before, after):
    def totals(receipt):
        out = defaultdict(int)
        for row in receipt.get("rows", []):
            key = (row.get("department") or "미매핑", row.get("venue") or "업장 미확인", row.get("venue_id") or "")
            out[key] += int(row.get("paid_krw") or 0)
        return out
    a, b = totals(before), totals(after)
    result = []
    for key in sorted(set(a) | set(b)):
        x, y = a.get(key, 0), b.get(key, 0)
        if x != y:
            result.append(dict(department=key[0], venue=key[1], venue_id=key[2], before_krw=x,
                               after_krw=y, delta_krw=y-x))
    if sum(x["delta_krw"] for x in result) != after["paid_krw"] - before["paid_krw"]:
        raise ReceiptError("고객별 업장 차액이 영수증 차액과 일치하지 않습니다")
    return result


def compare(baseline_id, scenario_id, customer_type=None, stay_status="all", event_only=False):
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
    a_context, b_context = before["context"], after["context"]
    if event_only:
        if not a_context.get("profile_sha") or not b_context.get("profile_sha") or not a_context.get("engine_version") or not b_context.get("engine_version"):
            raise ReceiptError("프로필·엔진 버전 지문이 없어 동일 입력 비교를 확인할 수 없습니다")
        changed = [k for k in set(a_context) | set(b_context) if k != "event" and a_context.get(k) != b_context.get(k)]
        if changed:
            raise ReceiptError("행사 조건 외 입력이 달라 동일 고객 상황 비교를 할 수 없습니다")
        if baseline_id != scenario_id and bool(a_context.get("event")) == bool(b_context.get("event")):
            raise ReceiptError("행사 없음과 와인페어처럼 행사 조건이 다른 실행을 선택해 주세요")
    customers = {}
    for pid in before["receipts"]:
        a, b = before["receipts"][pid], after["receipts"][pid]
        parts, transitions, row_changes = _decompose(a, b)
        departments = []
        for name in ("F&B", "ROOM", "레저", "미매핑"):
            x = sum(r["paid_krw"] for r in a["rows"] if r["department"] == name)
            y = sum(r["paid_krw"] for r in b["rows"] if r["department"] == name)
            if x or y: departments.append(dict(name=name, before_krw=x, after_krw=y, delta_krw=y-x))
        if sum(r["delta_krw"] for r in departments) != b["paid_krw"]-a["paid_krw"]:
            raise ReceiptError("부문별 비교 차액이 일치하지 않습니다")
        def action_map(receipt):
            return {(x.get("slot"), x.get("occurrence", 1)): x for x in receipt.get("actions", [])}
        aa, bb = action_map(a), action_map(b)
        activity_changes = []
        for action_key in sorted(set(aa) | set(bb)):
            left, right = aa.get(action_key), bb.get(action_key)
            if left is None or right is None or (left.get("venue_id"), left.get("action"), left.get("label"), left.get("purchase_status")) != (right.get("venue_id"), right.get("action"), right.get("label"), right.get("purchase_status")):
                activity_changes.append(dict(slot=action_key[0], before=copy.deepcopy(left), after=copy.deepcopy(right)))
        customers[pid] = dict(before_context=dict(before["context"], stay=a["stay"], phase=a["phase"], building=a["building"], party_size=a["party_size"]),
                              after_context=dict(after["context"], stay=b["stay"], phase=b["phase"], building=b["building"], party_size=b["party_size"]),
                              before_krw=a["paid_krw"], after_krw=b["paid_krw"], delta_krw=b["paid_krw"]-a["paid_krw"],
                              before_assumed_krw=a["with_assumptions_krw"], after_assumed_krw=b["with_assumptions_krw"],
                              departments=departments, venues=_venue_deltas(a, b), decomposition=parts, transitions=transitions,
                              row_changes=row_changes, activity_changes=activity_changes,
                              changed=bool(row_changes or activity_changes))
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
                caveat="같은 행동 단위의 기록을 비교한 분류입니다. 상호작용을 분리할 수 없는 차액은 복합 변화로 남깁니다.",
                comparison_kind="event_ab" if event_only else "operating_condition")

def _external_summary(ledger):
    """Guest spend outside the hotel (external delivery). Never part of L1; the amount stays unknown."""
    rows = [dict(customer_id=pid, visit_date=a.get("visit_date"), time=a.get("time"), action=a.get("action"), label=a.get("label"), **a["external_spend"])
            for pid, r in (ledger.get("receipts") or {}).items() for a in (r.get("actions") or []) if a.get("external_spend")]
    return dict(count=len(rows), customers=sorted({r["customer_id"] for r in rows}), amount_krw=None, hotel_revenue_krw=0,
                note="외부 배달 등 호텔 밖 지출 · 호텔 L1 제외 · 금액 미상", rows=rows)
