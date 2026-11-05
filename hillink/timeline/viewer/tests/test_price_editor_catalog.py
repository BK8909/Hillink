"""The operator selector is a projection of the active catalog, not the old base."""
import json,sys,unittest
from pathlib import Path
VIEWER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(VIEWER))
import visit_run
from operator_choice.autonomy_v1 import hotel_catalog as H
class PriceEditorCatalog(unittest.TestCase):
 def test_selector_matches_active_catalog_identity_price_and_unit(self):
  doc=json.loads((VIEWER/'static/sku_scenario_options.json').read_text())
  products={p['sku_id']:p for p in doc['products']}
  self.assertEqual(set(products),set(H.BY));self.assertEqual(doc['catalog_sha256'],H.SHA)
  for sku,p in products.items():
   for key in ['label','venue_id','role','unit_price_krw','billing_unit','price_tier']:
    self.assertEqual(p[key],H.BY[sku].get(key),(sku,key))
 def test_vista_model_price_replaces_hidden_reference_without_claiming_historical_quote(self):
  doc=json.loads((VIEWER/'static/sku_scenario_options.json').read_text())
  p={x['sku_id']:x for x in doc['products']}['HC-MENU-232']
  self.assertTrue(p['price_confirmed']);self.assertEqual(p['unit_price_krw'],55000)
  self.assertEqual(p['guest_building_rates']['GRAND'],66000)
  self.assertFalse(H.BY['HC-MENU-232']['historical_tariff_confirmed'])
  self.assertEqual(H.validate({'price_overrides':{'HC-MENU-232':44000}},['A01'])['price_overrides']['HC-MENU-232'],44000)
