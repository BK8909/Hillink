"""Rule-engine repeat diagnosis (research, no cost). Every switch is OFF unless its environment variable is set, so the
engine, the stored replays and the determinism check are unchanged by default. Each switch changes ONE factor so the
cause of repeated visits (e.g. Pizza Hill twice in a 2-night stay) can be isolated; none is a product change.

  HILLINK_DIAG_SPACE_BASE=off       night-view term without its unconditional base (W.space x 0.3 = 0.45 given to every
                                    customer after sunset); only the personal-evidence part stays
  HILLINK_DIAG_VISIT_MEMORY=on      a full meal at a venue already eaten at earlier in this visit, by a customer with no
                                    personal record about that venue and no stated repeat intention, does not earn the
                                    discovery terms (night view, specific food) a second time (the engine already does this
                                    for customers with a mixed/negative appraisal; this extends it to customers without one)
  HILLINK_DIAG_VISIT_MEMORY=base    the same, but only the parts without personal evidence are not earned twice (the
                                    unconditional night-view base and specific-food terms without Fact ids)
  HILLINK_DIAG_VISIT_MEMORY=base_unless_personal   as base, but a night-view term with personal evidence is kept whole
  HILLINK_DIAG_SKU_CAP=<k>          at most k candidate SKUs per restaurant venue (catalog order) at a decision
  HILLINK_DIAG_WAIT_LEAD_MIN=<min>  a venue that opens within <min> minutes can be planned (engine default 30)
"""
import os

DUP_FACETS = ('food_specific', 'space')
SPACE_BASE = 0.45   # W.space 1.5 x 0.3, the night-view part every customer receives


def active():
    return {k: os.environ.get(v) for k, v in (('space', 'HILLINK_DIAG_SPACE_BASE'), ('memory', 'HILLINK_DIAG_VISIT_MEMORY'),
                                              ('sku_cap', 'HILLINK_DIAG_SKU_CAP'), ('wait', 'HILLINK_DIAG_WAIT_LEAD_MIN')) if os.environ.get(v)}


def space_base_off(terms, W):
    if os.environ.get('HILLINK_DIAG_SPACE_BASE') != 'off':
        return terms
    base = W['space'] * 0.3
    out = []
    for t in terms:
        if t.get('facet') == 'space' and '야경' in str(t.get('factor')) and t.get('value', 0) > 0:
            v = round(t['value'] - base, 6)
            if v <= 1e-9:
                continue
            t = dict(t, value=v, factor=str(t['factor']) + ' (진단: 기본점 제외)')
        out.append(t)
    return out


def visit_memory(offer, terms, ctx, traits, existing_delta, discount):
    """(delta, trace) — only when HILLINK_DIAG_VISIT_MEMORY=on."""
    mode = os.environ.get('HILLINK_DIAG_VISIT_MEMORY')
    if mode not in ('on', 'base', 'base_unless_personal') or existing_delta:
        return 0.0, None
    if (offer.get('food') or {}).get('meal_fraction', 0) < .8:
        return 0.0, None
    previous = [m for m in ctx.get('prior_meals') or [] if m.get('venue_id') == offer.get('venue') and m.get('fraction', 0) >= .8]
    if not previous or (traits.get('venues') or {}).get(offer.get('venue')):
        return 0.0, None
    dup = [t for t in terms if t.get('facet') in DUP_FACETS and t.get('value', 0) > 0]
    if mode in ('base', 'base_unless_personal'):
        # only the parts without personal evidence: the unconditional night-view base, and specific-food terms with no Fact id.
        # base_unless_personal: a night-view term that carries personal evidence is kept whole (the value of returning to a
        # space the customer is recorded to like), only a night-view term without any personal evidence loses its base.
        parts = []
        for t in dup:
            if t.get('facet') == 'space' and '야경' in str(t.get('factor')):
                if mode == 'base_unless_personal' and t.get('fact_ids'):
                    continue
                parts.append(dict(t, value=min(t['value'], SPACE_BASE)))
            elif not t.get('fact_ids'):
                parts.append(t)
        dup = parts
    if not dup:
        return 0.0, None
    delta = round(-sum(t['value'] for t in dup) * discount, 6)
    return delta, dict(factor='DIAG_VISIT_MEMORY_SATURATION', delta=delta, prior_meal_ids=[m.get('event_id') for m in previous],
                       suppressed=[{k: t.get(k) for k in ('factor', 'facet', 'value')} for t in dup],
                       inference='DIAGNOSTIC_SWITCH_NOT_PRODUCT_RULE')


def sku_cap(world):
    k = os.environ.get('HILLINK_DIAG_SKU_CAP')
    if not k:
        return world
    k = int(k); seen = {}; offers = []
    for o in world['offers']:
        if o.get('kind') == 'restaurant' and o.get('venue'):
            seen[o['venue']] = seen.get(o['venue'], 0) + 1
            if seen[o['venue']] > k:
                continue
        offers.append(o)
    return dict(world, offers=offers)


def wait_lead(EN):
    v = os.environ.get('HILLINK_DIAG_WAIT_LEAD_MIN')
    if v:
        EN.WAIT_LEAD_MIN = int(v)
