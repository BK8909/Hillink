import copy,unittest
from test_official_contracts import OfficialContracts
from operator_choice.autonomy_v1 import hotel_catalog as H
from operator_choice.autonomy_v1 import package_benefits as PB
import hotel_ledger,room_revenue
class Closeout(unittest.TestCase):
 def a(self,n=2,day='2026-10-30',weather='clear'):
  a=OfficialContracts().a(n=n,day=day);a.B='DOUGLAS';a.sc.update(catalog_options={'room_products':{'P':'HC-MENU-017'}},scenario_snapshot={'weather':{'condition':weather}});return a
 def test_fire_rain_fair_and_season_window(self):
  for day,weather,variant,t in [('2026-09-01','clear','FIRE',1020),('2026-10-30','rain','RAIN',960),('2026-10-24','rain','FAIR',720)]:
   a=self.a(day=day,weather=weather);p=H.BY['HC-PKG-FIRE-'+variant];period='lunch' if variant=='FAIR' else 'activity'
   self.assertEqual(H.eligible(p,a,t,30,period),[])
   self.assertIn('PACKAGE_REDEMPTION_WINDOW',H.eligible(p,a,t-600,30,period))
   other=H.BY['HC-PKG-FIRE-'+('RAIN' if variant=='FIRE' else 'FIRE')];self.assertIn('PACKAGE_EVENT_WEATHER_VARIANT_MISMATCH',H.eligible(other,a,t,30,'activity'))
   c=H.entitlement(a,H.compose([H.component(p,1,a)],a,period));self.assertTrue(c['hc_included']);self.assertEqual(H.charge(c,included=True)['krw'],0)
   a.visit_history={'hotel_entitlement_usage':{PB.KEY:1}};self.assertIn('PACKAGE_BENEFIT_ALREADY_REDEEMED',H.eligible(p,a,t,30,period))
 def test_fire_native_evening_slot_not_misclassified_as_unavailable(self):
  a=self.a();self.assertEqual(H.eligible(H.BY['HC-PKG-FIRE-FIRE'],a,1020,60,'dinner'),[])
  cs,_=H.orders(a,'FOREST_PARK',1020,60,'dinner');self.assertTrue(any(c['components'][0]['sku_id']=='HC-PKG-FIRE-FIRE' for c in cs))
 def test_fire_entitlement_is_not_a_free_public_product(self):
  a=self.a();a.sc['catalog_options']={};self.assertIn('SELECTED_CURRENT_GUEST_PACKAGE_REQUIRED',H.eligible(H.BY['HC-PKG-FIRE-FIRE'],a,1000,30,'activity'))
 def test_rain_keeps_wine_snack_and_replaces_only_smores(self):
  p=H.BY['HC-PKG-FIRE-RAIN'];text=str(p['included_components']);self.assertIn('wine',text);self.assertIn('snack',text);self.assertIn('noodle',text);self.assertNotIn('smores_experience',[x['item'] for x in p['included_components']])
 def test_fair_no_generic_forest_reentry_or_extra_food_ticket(self):
  a=self.a(day='2026-10-24');self.assertIn('FOREST_GENERAL_USE_REPLACED_BY_WINE_FAIR',H.eligible(H.BY['HC-MENU-236'],a,720,30,'activity'))
  self.assertFalse(PB.state(a)['wine_fair_food_vouchers_included'])
 def order(self,a,venue,items,period='lunch',t=720):
  a.sc['catalog_options']['purchase_orders']={'P':[dict(date=a.sc['date'],venue_id=venue,service_period=period,items=[dict(sku_id=s,quantity=q) for s,q in items])]}
  return H.explicit_order(a,venue,period,t,30)
 def test_wine_bottle_and_platter_do_not_duplicate_included_bottle(self):
  a=self.a();c=self.order(a,'THE_PAVILION',[('HC-MENU-207',1),('HC-PAV-WINE-WHITE',1)])
  self.assertEqual(c['unit_price_krw'],169000);self.assertEqual([x['billing_unit'] for x in c['components']],['set','bottle'])
  self.assertEqual(c['components'][0]['included_components'][0]['quantity'],1)
  self.assertEqual(self.order(a,'THE_PAVILION',[('HC-MENU-207',1)])['unit_price_krw'],99000)
 def test_additional_wine_cannot_take_discount(self):
  with self.assertRaisesRegex(ValueError,'HC_SOURCE_DISCOUNT_NOT_ALLOWED'):H.validate({'discount_percent':{'HC-PAV-WINE-WHITE':10}},['P'])
 def test_explicit_bottle_preserves_age_guard(self):
  a=self.a();a.C['kids']=True;self.assertIn('ALCOHOL_PARTY_QUALIFICATION_UNKNOWN',H.eligible(H.BY['HC-PAV-WINE-WHITE'],a,1000,30,'snack',True))
 def test_wine_expiry_and_last_order(self):
  p=H.BY['HC-MENU-207'];self.assertIn('DATE_OR_SALE_DAY',H.eligible(p,self.a(day='2027-01-01'),1000,30,'lunch'))
  self.assertIn('SOURCE_LAST_ORDER_PASSED',H.eligible(p,self.a(),1201,30,'dinner'))
 def test_set_drink_upgrade_pool(self):
  a=self.a(n=4);c=self.order(a,'PIZZA_HILL',[('HC-MENU-086',1),('HC-MENU-088',2),('HC-MENU-089',2)])
  self.assertEqual(c['unit_price_krw'],336000)
  with self.assertRaisesRegex(ValueError,'HC_UPGRADES_EXCEED_INCLUDED_DRINKS'):self.order(a,'PIZZA_HILL',[('HC-MENU-086',1),('HC-MENU-088',3),('HC-MENU-089',2)])
 def test_topping_requires_pizza_and_cannot_exceed_parent(self):
  a=self.a(n=4);c=self.order(a,'PIZZA_HILL',[('HC-SRC-PIZZA-QUATTRO-HALL',1),('HC-SRC-PIZZA-QUATTRO-CHEESE',1)])
  self.assertEqual(c['unit_price_krw'],143000)
  with self.assertRaisesRegex(ValueError,'HC_ADDON_EXCEEDS_PARENT_UNITS'):self.order(a,'PIZZA_HILL',[('HC-SRC-PIZZA-QUATTRO-HALL',1),('HC-SRC-PIZZA-QUATTRO-CHEESE',2)])
 def test_correct_guest_reference_and_pool_transcription(self):
  self.assertEqual(H.BY['HC-MENU-232']['unit_price_krw'],55000);self.assertFalse(H.BY['HC-MENU-232']['historical_tariff_confirmed']);self.assertTrue(H.BY['HC-MENU-232']['price_confirmed'])  # operator rule 2026-11-02: hidden-HTML amount is a reference, never charged
  self.assertEqual(H.BY['HC-MENU-235']['unit_price_krw'],19000);self.assertEqual(H.BY['HC-MENU-235']['price_tier'],'EXISTING_REFERENCE')
 def test_pasta_portion_is_not_unknown_child_tariff(self):
  a=OfficialContracts().a(n=4,children=[{},{}]);p=H.BY['HC-IRD-RS_LUNCH_PASTA'];self.assertEqual(p['billing_unit'],'portion');self.assertEqual(H.quantity(p,a),4)
 def test_reference_price_is_not_quote_or_unselected_package_benefit(self):
  r=H.OC.room_reference(H.BY['HC-MENU-002'],service_date='2026-07-17',people=4,nights=2,selected=False)
  self.assertFalse(r['actual_date_quote']);self.assertFalse(r['within_source_period']);self.assertFalse(r['benefits_assigned_from_reference']);self.assertEqual(r['scenario_people'],4)
 def test_non_normalized_room_tariff_is_not_promoted_to_official_starting_rate(self):
  f={'visit_id':'x','visit':{'catalog_options':{'room_products':{'P':'HC-MENU-038'}},'start_date':'2026-10-30'},'visits':{'P':{'building':'GRAND','party_size':2}}}
  p=hotel_ledger.room_price(f,'P','2026-10-30',0,1,room_revenue.prices.PRICE,room_revenue.SOURCE_SHA256);self.assertIsNone(p['price_reference_contract'])
 def test_two_night_package_allocates_once_and_starting_rate_label(self):
  f={'visit_id':'x','visit':{'catalog_policy':H.POLICY,'catalog_options':{'room_products':{'P':'HC-MENU-019'}},'start_date':'2026-11-02'},'visits':{'P':{'building':'DOUGLAS','party_size':1}}}
  ps=[hotel_ledger.room_price(f,'P',d,i,2,room_revenue.prices.PRICE,room_revenue.SOURCE_SHA256) for i,d in enumerate(('2026-11-02','2026-11-03'))]
  self.assertEqual(sum(x['virtual_gross_krw'] for x in ps),519000)
  for x in ps:self.assertFalse(x['price_reference_contract']['actual_date_quote'])
if __name__=='__main__':unittest.main()
