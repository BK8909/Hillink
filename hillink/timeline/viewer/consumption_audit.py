"""Read-only scene/order/L5/L1 reconciliation; never reprices a stored run."""
from collections import Counter
VERSION = "consumption-audit-v2-sale-contract"
FOOD = {"PIZZA_HILL","THE_BUFFET","MYONGWOLGWAN","MOEGI","GEUMRYONG","ONDAL","THE_PAVILION","LE_PASSAGE","LUX_BAR","ROOM_MEAL"}

def rows_of(ledger):
    return [row for receipt in ledger.get("receipts", {}).values() for row in receipt.get("rows", [])]

def consuming(scene):
    code = scene.get("act") or ""
    if code in ("lunch_skip", "SKIP_BREAKFAST", "move", "wait", "arrive", "leave"):
        return False
    return scene.get("loc") in FOOD and (code.startswith("lunch_") or code in ("turn_dinner","turn_breakfast","breakfast","bakery","cafe","luxbar") or scene.get("domain") == "식사")

def matches(scene, row):
    return (scene.get("visit_day") or 1) == (row.get("visit_day") or 1) and scene.get("act") == row.get("act", row.get("action_id")) and (not row.get("time") or row["time"] == "%02d:%02d" % divmod(int(scene.get("t0") or 0),60))

def inspect(flow, ledger=None):
    ledger = ledger or flow.get("ledger") or {}
    rows = rows_of(ledger); records=[]; issues=[]
    def issue(code, **context):
        issues.append(dict(code=code, **context))
    if not ledger.get("run_id"):
        issue("MISSING_LEDGER")
    for pid, plan in flow.get("plans", {}).items():
        customer_rows = [r for r in rows if r.get("customer_id")==pid]
        for index, scene in enumerate(plan.get("scenes", [])):
            charge = (scene.get("basis") or {}).get("charge") or {}
            linked = [r for r in customer_rows if matches(scene,r)]
            status = charge.get("status"); reasons=[]
            if status in ("포함",) or linked and all(r.get("purchase_status")=="PACKAGE_INCLUDED" for r in linked):state="INCLUDED"
            elif status == "무료" or linked and all(r.get("purchase_status")=="FREE_USE" for r in linked):state="FREE"
            elif status in ("가격 미정", "금액 미확인") or any(r.get("amount_status")=="UNKNOWN" for r in linked):
                state="UNRESOLVED";reasons.append("PRICE_UNRESOLVED")
            elif charge.get("krw",0) or any(r.get("paid_krw",0)>0 for r in linked):state="PAID_PRICED"
            elif consuming(scene) and status not in ("포함", "무료"):
                state="UNRESOLVED";reasons.append("PAID_ACTION_WITHOUT_ORDER")
            else:state="NO_PURCHASE"
            if ((scene.get("basis") or {}).get("menu_decision") or {}).get("status")=="UNRESOLVED":
                state="UNRESOLVED";reasons.append("MENU_NOT_ELIGIBLE_AT_ACTION_TIME")
            if status=="유료" and not charge.get("krw"):
                state="UNRESOLVED";reasons.append("PAID_ORDER_ZERO")
            if state=="PAID_PRICED":
                if not linked:reasons.append("ORDER_WITHOUT_L5")
                if charge.get("krw") is not None and sum(r.get("paid_krw",0) for r in linked)!=charge["krw"]:reasons.append("ORDER_L5_AMOUNT_MISMATCH")
                for row in linked:
                    if not row.get("product_id"):reasons.append("ORDER_PRODUCT_MISSING")
                    if row.get("unit_price_krw") is None or not (row.get("billing_quantity") or row.get("quantity")):reasons.append("UNIT_OR_QUANTITY_MISSING")
                    if not row.get("paid_krw") and row.get("purchase_status") not in ("FREE_USE","PACKAGE_INCLUDED"):reasons.append("PAID_ORDER_ZERO")
                contract = charge.get("sku_contract") or {}
                if contract:
                    expanded = contract.get("catalog_policy")=="C01_HOTEL_CATALOG_V1" or any(r.get("parent_order_id") for r in linked)
                    expected = ({p["sku_id"] for p in contract.get("components",[])} if expanded else set()) or {contract.get("sku_id")}
                    actual = {r.get("product_sku_id") or r.get("product_id") for r in linked}
                    if actual != expected:reasons.append("FINAL_SKU_L5_MISMATCH")
            if state in ("FREE","INCLUDED") and any(r.get("paid_krw",0) for r in linked):reasons.append("INCLUDED_OR_FREE_CHARGED")
            for reason in sorted(set(reasons)):issue(reason, customer_id=pid, visit_day=scene.get("visit_day",1), scene_index=index, action_id=scene.get("act"))
            records.append(dict(customer_id=pid,visit_day=scene.get("visit_day",1),scene_index=index,action_id=scene.get("act"),state=state,issues=sorted(set(reasons)),row_ids=[r.get("row_id") for r in linked]))
    ids=[r.get("row_id") for r in rows]
    if len(ids)!=len(set(ids)):issue("DUPLICATE_TRANSACTION_ID")
    amount=sum(r.get("paid_krw",0) for r in rows)
    if amount!=ledger.get("totals",{}).get("paid_krw",0):issue("L5_TOTAL_MISMATCH")
    for level in ("L4","L3","L2","L1"):
        if sum(g.get("paid_krw",0) for g in ledger.get("levels",{}).get(level,[]))!=amount:issue("L5_"+level+"_MISMATCH")
    for row in rows:
        if row.get("amount_status")=="UNKNOWN":issue("L5_PRICE_UNRESOLVED",row_id=row.get("row_id"))
        if row.get("unit_price_krw") is not None:
            quantity=row.get("billing_quantity") or row.get("quantity")
            if quantity is not None and row["unit_price_krw"]*quantity!=row.get("paid_krw",0):issue("L5_UNIT_TOTAL_MISMATCH",row_id=row.get("row_id"))
    warnings=[]
    meal_orders={}
    for row in rows:
        c=row.get('sku_contract') or {};key=(row.get('customer_id'),row.get('visit_date'),row.get('time'),row.get('act'))
        if c.get('party_cohort')=='UNKNOWN_CHILD_FARE' or 'UNKNOWN_CHILD' in c.get('price_status',''):
            warnings.append(dict(code='AGE_FARE_ASSUMPTION_NOT_CONFIRMED',row_id=row.get('row_id')))
        if c.get('venue_id')=='THE_BUFFET' and row.get('act') in ('turn_dinner','turn_lunch','turn_breakfast','lunch_restaurant'):
            meal_orders.setdefault(key,[]).append(row)
        if c.get('included_benefit') and row.get('paid_krw',0)>0:issue('PACKAGE_BENEFIT_DOUBLE_CHARGED',row_id=row.get('row_id'))
        if c.get('set_servings') and c.get('billing_unit')=='set' and c.get('order_quantity_basis')!='EXPLICIT_VIRTUAL_MIXED_ORDER_QUANTITY':
            if (row.get('billing_quantity') or 1)!=1:issue('GROUP_SET_MULTIPLIED_BY_PEOPLE',row_id=row.get('row_id'))
        if c.get('official_source') and not c.get('price_trace') and c.get('price_tier') in ('COMPARABLE_ESTIMATE','SIMULATION_ASSUMPTION') and c.get('party_cohort')!='UNKNOWN_CHILD_FARE':
            warnings.append(dict(code='OFFICIAL_SOURCE_WITH_MODEL_PRICE_REVIEW',row_id=row.get('row_id')))
    for key,group in meal_orders.items():
        n=(flow.get('visits',{}).get(key[0]) or {}).get('party_size')
        if n and sum(r.get('billing_quantity') or r.get('quantity') or 0 for r in group)>n:issue('BUFFET_ADMISSIONS_EXCEED_PARTY',customer_id=key[0],visit_date=key[1],time=key[2])
        identities=[(r.get('parent_order_id'),r.get('product_sku_id'),(r.get('sku_contract') or {}).get('party_cohort')) for r in group]
        if len(identities)!=len(set(identities)):issue('DUPLICATE_MEAL_COMPONENT',customer_id=key[0],visit_date=key[1],time=key[2])
    return dict(version=VERSION,run_id=ledger.get("run_id"),status="FAIL" if issues else "PASS" if flow.get("plans") else "PARTIAL",mode="FULL_SCENES_AND_LEDGER" if flow.get("plans") else "LEDGER_ONLY",scene_count=len(records),counts=dict(Counter(r["state"] for r in records)),l5_rows=len(rows),paid_rows=sum(r.get("paid_krw",0)>0 for r in rows),paid_krw=amount,issue_counts=dict(Counter(x["code"] for x in issues)),issues=issues,scenes=records,stored_run_mutated=False,warnings=warnings)


if __name__ == "__main__":
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path,help="Local saved response or request/response JSON")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args();value=json.loads(args.input.read_text())
    flow=value.get("response",value);ledger=flow.get("ledger") or (flow if "receipts" in flow else None)
    result=inspect(flow,ledger);text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(text);args.output.chmod(0o600)
    else:print(text)
    raise SystemExit(1 if result["status"]=="FAIL" else 0)
