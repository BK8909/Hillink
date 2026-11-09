"""An event admission offered to the AI (e.g. the wine fair's guest free entry) is a single flat contract without
components; building the AI's action list must not fail on it (2026-11-09: LIVE runs with the wine fair stopped)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'experiments/persona_live'))
import population_lab  # noqa: F401,E402  (engine import path)
from operator_choice.autonomy_v1 import autonomous_agent as AA  # noqa: E402


def test_flat_event_admission_contract_is_one_free_item():
    q = AA.fixed_quote(dict(sku_id='C01-WINE-GUEST-FREE-ENTRY', venue_id='FOREST_PARK', billing_quantity=1, unit_price_krw=0))
    assert q['items'] == [dict(sku_id='C01-WINE-GUEST-FREE-ENTRY', quantity=1)] and q['order_total_krw'] == 0


def test_component_contracts_are_unchanged():
    q = AA.fixed_quote(dict(sku_id='P', unit_price_krw=30000, components=[dict(sku_id='A', billing_quantity=2), dict(sku_id='B', billing_quantity=1)]))
    assert q['items'] == [dict(sku_id='A', quantity=2), dict(sku_id='B', quantity=1)] and q['order_total_krw'] == 30000
