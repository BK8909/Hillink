import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import catalog_request_adapter as A
import visit_run as V
from operator_choice.autonomy_v1 import hotel_catalog as H

class CatalogRequestAdapterTests(unittest.TestCase):
 def order(self,line=204,quantity=3):
  return dict(date='2026-10-24',venue_id='THE_PAVILION',service_period='snack',items=[dict(source_line=line,quantity=quantity)])
 def test_quantity_is_preserved_and_real_catalog_candidate_uses_it(self):
  visits={'A04':{'orders':[self.order()]}};before=copy.deepcopy(visits);options=A.connect({},visits,H,{'2026-10-24'})
  self.assertEqual(visits,before)
  order=options['purchase_orders']['A04'][0];self.assertEqual(order['items'],[dict(sku_id='HC-MENU-204',quantity=3)])
  actor=SimpleNamespace(pid='A04',sc=dict(date='2026-10-24',catalog_options=options),N=2,B='GRAND',stay=True,checked_in=True,checked_out=False,C={},vs={},visit_history={})
  quote=H.explicit_order(actor,'THE_PAVILION','snack',900,30)
  self.assertEqual(quote['components'][0]['billing_quantity'],3)
  self.assertEqual(quote['unit_price_krw'],3*H.BY['HC-MENU-204']['unit_price_krw'])
 def test_conflicting_inputs_rejected_identical_inputs_idempotent(self):
  visits={'A04':{'orders':[self.order()]}};options=A.connect({},visits,H,{'2026-10-24'})
  self.assertEqual(A.connect(options,visits,H,{'2026-10-24'}),options)
  options['purchase_orders']['A04'][0]['items'][0]['quantity']=4
  with self.assertRaisesRegex(ValueError,'INPUT_CONFLICT'):A.connect(options,visits,H,{'2026-10-24'})
 def test_unknown_source_or_outside_visit_is_not_silently_ignored(self):
  with self.assertRaisesRegex(ValueError,'MAPPING_UNCONFIRMED'):A.connect({}, {'A04':{'orders':[self.order(99999)]}},H,{'2026-10-24'})
  with self.assertRaisesRegex(ValueError,'DATE_NOT_IN_VISIT'):A.connect({}, {'A04':{'orders':[self.order()]}},H,{'2026-10-25'})
 def test_brunch_beverages_cover_modeled_child_portions_and_explicit_orders(self):
  actor=SimpleNamespace(pid='A01',sc=dict(date='2026-09-12',catalog_options={}),N=4,B='GRAND',stay=True,checked_in=True,checked_out=False,C={'kids':True},vs={},visit_history={})
  orders,_=H.orders(actor,'THE_PAVILION',745,60,'lunch')
  brunch=next(c for c in orders if any(p.get('source_line')==203 for p in c['components']))
  self.assertEqual(sum(p['billing_quantity'] for p in brunch['components'] if p['role']=='DRINK'),4)
  self.assertEqual(brunch['unit_price_krw'],4*(28000+19000))
  actor.sc['catalog_options']={'purchase_orders':{'A01':[dict(date='2026-09-12',venue_id='THE_PAVILION',service_period='lunch',items=[dict(sku_id='HC-MENU-203',quantity=4)])]}}
  with self.assertRaisesRegex(ValueError,'BRUNCH_BEVERAGE_QUANTITY'):H.explicit_order(actor,'THE_PAVILION','lunch',745,60)
 def test_package_checks_each_paid_night_but_not_checkout(self):
  opts={'room_products':{'A04':'HC-MENU-019'}}
  visits={'A04':dict(party_size=1,building='DOUGLAS',stay=True,nights=2,kids=False,party_composition=dict(adult_count=1,children=[]))}
  # Collected weekday model excludes Friday/Saturday. Thursday check-in alone
  # is insufficient for a two-night Thursday+Friday bundle.
  with self.assertRaisesRegex(ValueError,'2026-11-06:DATE_OR_SALE_DAY'):
   A.connect(opts,visits,H,{'2026-11-05','2026-11-06','2026-11-07'})
  self.assertEqual(A.connect(opts,visits,H,{'2026-11-04','2026-11-05','2026-11-06'}),opts)
 def test_no_order_preserves_catalog_and_other_customer_inputs(self):
  options={'price_overrides':{'HC-MENU-204':9000}};original=copy.deepcopy(options)
  self.assertEqual(A.connect(options,{'A04':{}},H,{'2026-10-24'}),original)
  self.assertEqual(options,original)

if __name__=='__main__':unittest.main()
