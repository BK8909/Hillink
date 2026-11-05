"""Pre-choice basket alternatives; quantities and fullness are model assumptions.

Never invent products, change persona weights, or append a charge after choice.
Admission/course contracts and explicit operator orders retain their quantities.
"""
import copy
import re

POLICY = 'MEAL_BASKET_V1'
VENUES = {'PIZZA_HILL', 'GEUMRYONG', 'MOEGI', 'MYONGWOLGWAN', 'ONDAL', 'THE_BUFFET'}


def servings(p):
    unit = p.get('billing_unit')
    if p.get('role') not in ('MAIN', 'BREAKFAST', 'CHILD_COMPONENT'):
        return 0
    if unit in ('person', 'portion'):
        return 1  # meal-equivalent assumption, not nutritional or observed intake
    if unit == 'pizza':
        label = p['label']
        return 6 if '세이스' in label else 4 if '콰트로' in label else 3 if re.search(r'\bL\b', label) else 2
    if unit == 'set':
        match = re.search(r'세트.*?(\d+)인', p.get('source_unit', ''))
        return int(match[1]) if match else None
    return None


def metadata(c, a, kind='EXISTING_ORDER'):
    parts = c['components']
    food = [p for p in parts if p.get('role') in ('MAIN', 'BREAKFAST', 'CHILD_COMPONENT')]
    if not food:
        return c
    capacities = [servings(p) for p in food]
    known = all(x is not None for x in capacities)
    capacity = sum(x * p['billing_quantity'] for x, p in zip(capacities, food)) if known else None
    # Preserve historical full-meal assumption when source units cannot be mapped;
    # explicitly record that limitation instead of claiming a measured portion.
    fraction = min(1., capacity / max(1, a.N)) if known else 1.
    tags = set(tag for p in food for tag in p.get('tags', []))
    for p in food:
        included = p.get('included_components') or {}
        if isinstance(included, dict):
            tags.update(k for k in ('pizza', 'pasta', 'salad') if included.get(k))
    c['meal_basket'] = dict(
        policy=POLICY, kind=kind, portion_basis='GENERAL_MEAL_EQUIVALENT_ASSUMPTION_NOT_OBSERVED_INTAKE',
        capacity_basis='CATALOG_SALE_UNITS_AND_EXISTING_PIZZA_SHARING_MODEL',
        party_size=a.N, meal_equivalents=capacity, meal_fraction=fraction,
        excess_capacity=max(0, capacity-a.N) if known else None,
        excess_note='Capacity is not measured consumption; fullness capped at one modeled meal. No leftover fact inferred.',
        source_composition_tags=sorted(tags),
        menu_diversity=len({p['sku_id'] for p in food}) >= 2 or len(tags & {'pizza', 'pasta', 'salad'}) >= 2,
        hunger_before=getattr(a, 'hunger_e', None),
        prior_meals=copy.deepcopy(getattr(a, 'meal_log', [])),
        limitation=None if known else 'PORTION_UNKNOWN_LEGACY_FULL_MEAL_ASSUMPTION',
        selection_stage='BEFORE_SCORING', session_rule='ONE_SELECTED_BASKET_ONE_MEAL_SESSION')
    return c


def expandable(p):
    # No buffet admissions, multi-person minimum courses, child components,
    # upgrades or reservation-dependent products are split into mixed dishes.
    return (p.get('role') == 'MAIN' and p.get('minimum_quantity', 1) == 1
            and p.get('billing_unit') in ('portion', 'pizza', 'person')
            and not set(p.get('tags', [])) & {'course', 'buffet'}
            and not re.search(r'코스|오마카세|뷔페|세트|정식|course|omakase', p.get('label', ''), re.I)
            and not p.get('required_parent_sku_ids') and not p.get('requires_reservation'))


def alternatives(orders, a, period, H):
    if not orders or orders[0]['venue_id'] not in VENUES or period not in ('lunch', 'dinner'):
        return orders
    result = [metadata(c, a) for c in orders]
    if orders[0]['venue_id'] == 'THE_BUFFET' or a.N < 2 or (H.modeled_party(a) or {}).get('children'):
        # Existing child pricing/age uncertainty is not replaced by adult portions.
        return result
    mains = {p['sku_id']: p for c in orders for p in c['components'] if expandable(p)}
    seen = {tuple(sorted((p['sku_id'], p['billing_quantity']) for p in c['components'])) for c in result}

    def add(parts, kind):
        key = tuple(sorted((p['sku_id'], p['billing_quantity']) for p in parts))
        if key not in seen:
            seen.add(key)
            result.append(metadata(H.compose(parts, a, period), a, kind))

    for p in mains.values():
        # Bounded, reproducible search: each eligible main plus the lowest-priced
        # different dish. No personalized coefficients changed.
        peers = [q for q in mains.values() if q['sku_id'] != p['sku_id']
                 and q.get('billing_unit') in ('portion', 'person')]
        if peers:
            q = min(peers, key=lambda x: (x['unit_price_krw'], x['sku_id']))
            units = max(1, a.N - 1) if p['billing_unit'] in ('portion', 'person') else max(1, H.quantity(p, a))
            parts = [dict(copy.deepcopy(p), billing_quantity=units), dict(copy.deepcopy(q), billing_quantity=1)]
            for part in parts:
                part['order_quantity_basis'] = 'PRE_CHOICE_MIXED_MEAL_MODEL_NOT_OBSERVED'
            add(parts, 'MIXED_REGISTERED_MENUS')
        # A smaller order is an option only after recorded food and low hunger;
        # full orders remain available. Never fractional SKU or mandatory snack.
        if getattr(a, 'meal_log', []) and 0 < getattr(a, 'hunger_e', 1) < .8 and p['billing_quantity'] > 1:
            add([dict(copy.deepcopy(p), billing_quantity=1, order_quantity_basis='LIGHT_ORDER_AFTER_RECORDED_MEAL_MODEL')], 'LIGHT_AFTER_PRIOR_MEAL')
    return result
