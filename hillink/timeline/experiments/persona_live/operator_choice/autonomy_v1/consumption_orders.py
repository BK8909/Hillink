"""Post-venue menu fulfillment. Reuse C01 eligibility, quantity and native scoring.

A venue choice is never replayed or replaced. Already selected SKU contracts
(including adopted reviews) and package entitlements remain authoritative.
"""
import copy
from . import hotel_catalog as H
VERSION = "post-venue-order-v1"
FOOD = {"PIZZA_HILL", "MYONGWOLGWAN", "GEUMRYONG", "ONDAL", "MOEGI", "THE_BUFFET", "ROOM_MEAL", "LE_PASSAGE", "THE_PAVILION", "LUX_BAR"}

def complete(a, code, kind, target, time, duration, domain, offer, internal, in_package):
    from . import hotel_runtime as R
    current = offer or {}
    trace = copy.deepcopy(internal or {})
    if current.get("sku_contract") or in_package or current.get("hc_included"):
        return offer, trace, None
    if current.get("id") == "EXTERNAL_DELIVERY" or code == "EXTERNAL_DELIVERY":
        return offer, trace, None   # external delivery: not a hotel menu, no IRD item is chosen or charged
    venue = current.get("venue") or target
    if target == getattr(a, "room", None) and (current.get("kind") == "room_meal" or code == "lunch_room"):
        venue = "ROOM_MEAL"
    if code in ("sauna", "SAUNA") and target in ("WELLNESS_SAUNA", "FITNESS"):
        venue = "SAUNA"
    consuming = code not in ("lunch_skip", "SKIP_BREAKFAST") and (code.startswith("lunch_") or code in ("turn_dinner", "turn_breakfast", "breakfast", "bakery", "cafe", "luxbar") or domain == "식사" or kind in ("restaurant", "simple_meal", "room_meal"))
    if venue == "SAUNA" and code in ("sauna", "SAUNA"):
        consuming = True
    if venue == "SKYARD" and code in ("SKYARD", "SKYARD_NIGHT", "footbath", "night_footbath"):
        consuming = True
    if venue == "THEATRE_OF_LIGHT" and code == "theatre":
        consuming = True
    if venue not in FOOD | {"THEATRE_OF_LIGHT", "SKYARD", "SAUNA"} or not consuming:
        return offer, trace, None
    slot = "breakfast" if "breakfast" in code.lower() else "lunch" if code.startswith("lunch_") else "snack" if code in ("bakery", "cafe", "luxbar") else "dinner" if time >= 960 else "lunch"
    if venue in ("THEATRE_OF_LIGHT", "SKYARD", "SAUNA"):
        slot = "activity"
    choices, excluded = H.orders(a, venue, time, duration, slot)
    if venue == "SAUNA":
        choices = [c for c in choices if c["components"][0].get("facility_id") == ("VISTA_SAUNA" if target=="WELLNESS_SAUNA" else "GRAND_SAUNA")]
    # An already selected solo meal can be valued as an explicitly unspecified
    # meal model. Restricted real courses stay excluded, never relabeled as
    # eligible one-person courses or invented reservations.
    model = False
    if not choices and venue in FOOD and slot in ("lunch", "dinner") and a.N == 1:
        for blocked in excluded:
            ref = H.BY.get(blocked.get("sku_id"))
            if not ref or ref["role"]!="MAIN" or ref["minimum_quantity"]!=2 or set(blocked["reasons"])!={"MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY"}:
                continue
            p=copy.deepcopy(ref)
            p.update(sku_id="MODEL-UNSPECIFIED-MEAL-"+ref["sku_id"],label="가상 식사 주문 · 실제 메뉴 미확인",minimum_quantity=1,source_unit="모델 1인 식사 · 원 코스 구매 아님",price_tier="SIMULATION_ASSUMPTION",price_status="UNSPECIFIED_MEAL_COMPARABLE_UNIT_NOT_RESTRICTED_COURSE",reference_sku_id=ref["sku_id"],reference_label=ref["label"],native_product_id=None)
            part=H.component(p,1,a,assumption="SINGLE_DINER_UNSPECIFIED_MEAL_VALUE; REFERENCED_TWO_PERSON_COURSE_IS_NOT_ORDERED")
            c=H.compose([part],a,slot);c["order_origin"]="SELECTED_VENUE_UNSPECIFIED_MEAL_MODEL";choices.append(c);model=True
    choices = [H.entitlement(a,c) for c in choices]
    if venue == "SAUNA":   # Vista sauna has no confirmed price: not fully included -> unknown price, use kept
        from . import facility_rules as FR
        choices = FR.mark_unpriced(choices)
    # Preserve a specifically selected native menu where it has a dated SKU.
    matching = [c for c in choices if any(p.get("native_product_id") == current.get("id") and current.get("id") for p in c["components"])]
    pool = matching or choices
    world = R.AD.World(a.sc).engine_world(time)
    selected, decision = R.POST_VENUE_RULE_CHOOSE(a, pool, time, duration, world) if pool else (None, None)
    if selected is None:
        trace["hotel_product_decision"] = dict(version=VERSION, status="UNRESOLVED", venue_id=venue, service_period=slot, excluded=excluded, reason="NO_ELIGIBLE_MENU_AT_ACTUAL_ACTION_TIME")
        return offer, trace, None
    contract = copy.deepcopy(selected["sku_contract"])
    selection_id = trace.get("selection_id") or H.digest([VERSION, a.pid, a.sc["date"], time, code, contract["sku_id"]])
    trace.setdefault("selection_id", selection_id)
    contract.update(selection_id=selection_id, final_candidate_id=contract["sku_id"], order_origin="SELECTED_VENUE_UNSPECIFIED_MEAL_MODEL" if model else "NATIVE_POST_VENUE_MENU_DECISION")
    selected.update(sku_contract=contract)
    trace["hotel_product_decision"] = dict(decision, version=VERSION, status="SELECTED", parent_venue_id=venue, original_offer_id=current.get("id"), excluded=excluded, selection_id=selection_id, order_origin=contract["order_origin"], context=dict(time=time, hunger_before=a.hunger_e, fatigue_before=a.fatigue, prior_meals=copy.deepcopy(a.meals), prior_food=copy.deepcopy(a.food), profile_used=True), party_assumption=H.modeled_party(a), unspecified_meal_model=model, saleable_menu_confirmed=False if model else None)
    return selected, trace, selected["label"]
