"""Public restaurant directory from the runtime catalog, independent of a visit quote."""
from room_options import hotel_catalog


def strategy_options():
    h = hotel_catalog()
    products = [dict(venue_id=p['venue_id'], category=p['category'], role=p['role'])
                for p in h.DATA['products']
                if p.get('category') == 'F&B' and p.get('role') in ('MAIN', 'BREAKFAST', 'SNACK')
                and p.get('venue_id') not in ('ROOM_MEAL', 'WINE_FAIR')
                and p.get('automatic_choice') is not False]
    # Public menu references are hypotheses inputs, never executable eligibility claims.
    fields = ('sku_id', 'venue_id', 'label', 'category', 'role', 'unit_price_krw',
              'price_status', 'source_unit', 'service_periods', 'source_service_windows',
              'valid_from', 'valid_until', 'minimum_quantity', 'requires_reservation',
              'automatic_choice', 'billing_unit')
    menus = [{k: p[k] for k in fields if k in p} for p in h.DATA['products']
             if p.get('category') == 'F&B' and p.get('role') == 'MAIN'
             and p.get('automatic_choice') is not False]
    return dict(products=products, menu_references=menus,
                catalog_policy=h.POLICY, catalog_sha256=h.SHA)
