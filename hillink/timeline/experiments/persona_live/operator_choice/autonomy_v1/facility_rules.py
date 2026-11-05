"""Facility rules confirmed by already-collected official evidence (operator rule set 2026-11-02 00:56).

Only clear errors are corrected here. No new probability, bonus or forced linkage is added.
- Grand fitness centre (fitness, indoor pool, sauna): regular closure = Grand notice dates (3rd Tuesday list).
- Vista Wellness Club (fitness, indoor pool, sauna): regular closure = Vista notice dates (2nd Wednesday list).
  Closure is applied per facility of the guest's building on the actual visit date.
- Versioned 2026-11-03 sauna contracts use sauna_policy.py facility/building reference tariffs.
  The hidden-HTML unknown-price path below is retained only for unversioned historical contracts.
  Current model tariffs are not confirmation of historical, date-specific selling prices.
- Three states are kept apart: price unknown / free-or-included / unavailable (closure, age, guest-only).
- ALL THAT WELLNESS (sauna type, HC-MENU-028): included sauna = 2 persons x 1 use or 1 person x 2 uses,
  17+ (venue minimum age), before checkout (guest-only rules).
"""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

_TL = Path(__file__).resolve().parents[4]
if str(_TL) not in sys.path:
    sys.path.insert(0, str(_TL))
import walkerhill_timeline_validator as V  # noqa: E402

VISTA_CLOSED = frozenset(d for d, _ in V._VISTA_WELLNESS_CLOSED_2026)
GRAND_CLOSED = frozenset(d for d, _ in V._GRAND_FITNESS_CLOSED_2026)
SAUNA_HOURS = (6 * 60, 22 * 60)          # WELLNESS_SAUNA window in walkerhill_timeline_validator (06:00-22:00)
SOLO_TWICE_SKU = 'HC-MENU-028'
SOLO_SECOND_KEY = 'HC_ROOM_SAUNA_028_SOLO_SECOND'
ROOM_SAUNA_KEY = 'HC_ROOM_SAUNA_ONCE'
VISTA_SAUNA_SKU = 'HC-MENU-232'
VISTA_SAUNA_UNPRICED = 'VISTA_SAUNA_PRICE_UNCONFIRMED_HIDDEN_HTML_ONLY_NOT_CHARGED'


def _day(a):
    return date.fromisoformat(a.sc['date'])


def _room_product(a):
    from . import hotel_catalog as H
    sku = (H.options(a).get('room_products') or {}).get(a.pid) or ''
    return H.BY.get(sku, {})


def _used(a, key):
    return bool((getattr(a, 'visit_history', {}) or {}).get('hotel_entitlement_usage', {}).get(key))


def room_sauna_cover(a):
    """Remaining included sauna uses from the selected room product (None when the room has no sauna benefit)."""
    room = _room_product(a)
    if '사우나' not in (room.get('included_description') or ''):
        return None
    if room.get('sku_id') == SOLO_TWICE_SKU and getattr(a, 'N', 2) == 1:
        return 2 - int(_used(a, ROOM_SAUNA_KEY)) - int(_used(a, SOLO_SECOND_KEY))
    return 0 if _used(a, ROOM_SAUNA_KEY) else 1


def sauna_included_available(a):
    pkg = (getattr(a, 'vs', {}) or {}).get('package_context') or {}
    usage = (((getattr(a, 'visit_history', {}) or {}).get('benefit_usage') or {}).get('package_entitlements') or {})
    for bid, rule in (pkg.get('benefits') or {}).items():
        if rule.get('facility') == 'SAUNA' and usage.get(bid, {}).get('remaining', rule.get('limit', 0)) > 0 \
                and getattr(a, 'N', 1) <= int(rule.get('included_people') or 0):
            return True
    left = room_sauna_cover(a)
    return bool(left and left > 0)


def block(a, code):
    """Reason string when a facility rule blocks this activity on this visit date; otherwise None."""
    code = str(code)
    b = getattr(a, 'B', None)
    try:
        d = _day(a)
    except Exception:
        return None
    if code in ('sauna', 'SAUNA'):
        from . import sauna_policy as SA
        vista=SA.facility(a)=='VISTA_SAUNA'
        if vista and (d in VISTA_CLOSED or d.weekday()==2 and 8<=d.day<=14):
            return 'VISTA_WELLNESS_REGULAR_CLOSURE_2ND_WEDNESDAY'
        if not vista and (d in GRAND_CLOSED or d.weekday()==1 and 15<=d.day<=21):
            return 'GRAND_FITNESS_REGULAR_CLOSURE_3RD_TUESDAY'
    if code == 'fitness' and b != 'VISTA' and d in GRAND_CLOSED:
        return 'GRAND_FITNESS_REGULAR_CLOSURE_3RD_TUESDAY'
    return None


def vista_sauna_unpriced(a, code='SAUNA'):
    """True when a Vista guest's sauna use has no included benefit left: price unknown, not blocked."""
    return False  # 2026-11-03 model tariff supersedes hidden-HTML unknown policy; historical helper retained.


def mark_unpriced(choices):
    """Vista sauna order choices that are not fully included keep the use but carry an unknown price."""
    import copy
    out = []
    for c in choices:
        if c['components'][0].get('source_line') == 232 and not c['components'][0].get('sauna_policy') and not c.get('hc_included'):
            c = copy.deepcopy(c)
            c.update(price_unknown=True, price_status=VISTA_SAUNA_UNPRICED,
                     price_unknown_basis='비스타 웰니스 사우나 — 현재 공식 요금 미확인(숨김 HTML 주석 금액 미사용) · 0원 아님')
        out.append(c)
    return out


def sauna_hours_ok(arrival, duration):
    start = max(arrival, SAUNA_HOURS[0])
    return start == arrival and start + duration <= SAUNA_HOURS[1]
