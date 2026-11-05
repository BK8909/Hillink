import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_options import strategy_options
from room_options import hotel_catalog

def test_directory_is_runtime_catalog_projection_without_customer_or_price_data():
    data=strategy_options();h=hotel_catalog()
    assert {p['venue_id'] for p in data['products']} >= {'PIZZA_HILL','GEUMRYONG','MOEGI','ONDAL','MYONGWOLGWAN','THE_BUFFET'}
    assert data['catalog_sha256']==h.SHA
    assert all(set(p)=={'venue_id','category','role'} for p in data['products'])
    assert all(any(all(r.get(k)==v for k,v in p.items()) for r in h.DATA['products']) for p in data['products'])


def test_hypothesis_menu_references_are_public_catalog_fields_not_new_products():
    data = strategy_options()
    source = {p['sku_id']: p for p in hotel_catalog().DATA['products']}
    assert any(p['venue_id'] == 'MYONGWOLGWAN' for p in data['menu_references'])
    allowed = {'sku_id', 'venue_id', 'label', 'category', 'role', 'unit_price_krw',
               'price_status', 'source_unit', 'service_periods', 'source_service_windows',
               'valid_from', 'valid_until', 'minimum_quantity', 'requires_reservation',
               'automatic_choice', 'billing_unit'}
    for p in data['menu_references']:
        assert set(p) <= allowed
        assert p['role'] == 'MAIN'
        assert all(source[p['sku_id']][k] == v for k, v in p.items())
