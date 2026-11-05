"""11/02 research options (default off), breakfast mapping, Santa package source/booking hook."""
import unittest
import test_final_four_skus as F
from operator_choice.autonomy_v1 import hotel_catalog as H, candidate_services as C, agent_day as AD
import santa_packages as SPK

class ResearchOptions(unittest.TestCase):
 def test_options_validate_and_default_off(self):
  H.validate({'dinner_plan_lead_min':120,'service_open_overrides':{'GEUMRYONG':'17:00'}},['P'])
  for bad in ({'dinner_plan_lead_min':30},{'dinner_plan_lead_min':200},{'service_open_overrides':{'GEUMRYONG':'19:00'}},{'service_open_overrides':{'PIZZA_HILL':'17:00'}}):
   with self.assertRaises(ValueError):H.validate(bad,['P'])
 def test_open_override_only_moves_dinner_sessions(self):
  base=C.service_check('GEUMRYONG','2026-10-30',17*60,60)
  moved=C.service_check('GEUMRYONG','2026-10-30',17*60,60,open_override=17*60)
  self.assertFalse(base['eligible']);self.assertTrue(moved['eligible'])
  self.assertEqual(moved['service_window']['open_override'],17*60)
  lunch=C.service_check('GEUMRYONG','2026-10-30',12*60,60,open_override=17*60)
  self.assertIsNone(lunch['service_window']['open_override'])
 def test_booked_hook_default_none(self):
  self.assertIsNone(AD.BOOKED_HOOK)

class BreakfastMapping(unittest.TestCase):
 def test_in_room_breakfast_never_offers_lunch_items(self):
  a=F.FinalFour().a();a.sc['catalog_options']={'paid_breakfast_ird_customers':[a.pid]}
  allowed,_=H.orders(a,'ROOM_MEAL',8*60,60,'breakfast')
  self.assertTrue(allowed)
  for c in allowed:
   self.assertTrue(all(p['role']!='MAIN' or 'BREAKFAST' in p['sku_id'] for p in c['components'] if p['role'] not in ('CHILD_COMPONENT','ADDON')),c['label'])
   self.assertNotIn('LUNCH',' '.join(p['sku_id'] for p in c['components']))
 def test_slot_from_native_product_code(self):
  src=open(__import__('operator_choice.autonomy_v1.consumption_orders',fromlist=['']).__file__,encoding='utf-8').read()
  self.assertIn('"breakfast" in code.lower()',src)

class SantaSource(unittest.TestCase):
 def test_2025_package_is_starting_price_not_fixed(self):
  p=SPK.PACKAGES['SANTA_PKG_2025']
  self.assertEqual(p['price_krw'],559000);self.assertIn('부터',p['price_class_ko']);self.assertIn('확정가 아님',p['price_class_ko'])
  self.assertEqual(p['package_sessions'],{'3부':'15:20','4부':'16:30'})
  self.assertIn('2025-12-01',SPK.SOURCE_NOTE)
  # 11/04 official 2026 source contract is now separate and runnable. 2025 assertions above are unchanged.
  newer=SPK.PACKAGES['SANTA_PKG_2026_VISTA_DELUXE']
  self.assertTrue(newer['runnable']);self.assertEqual(newer['package_sessions'],{'3부':'15:20','4부':'16:40'})
  self.assertEqual(newer['source_status'],'OFFICIAL_CAPTURE_AND_PAGE_CHECKED_20261104')

if __name__=='__main__':unittest.main()
