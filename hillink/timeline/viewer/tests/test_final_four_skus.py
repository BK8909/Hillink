import copy,unittest
import test_official_contracts as T
from operator_choice.autonomy_v1 import hotel_catalog as H
import hotel_ledger as L,ledger_l5 as LL
class FinalFour(unittest.TestCase):
 def a(self,building='GRAND',n=3,children=None,room=None):
  a=T.OfficialContracts().a(n=n,children=children,day='2026-10-30');a.B=building;a.club=False;a.sc['catalog_policy']=H.POLICY
  if room:a.sc['catalog_options']={'room_products':{'P':room}}
  return a
 def test_burger_channel_not_overwritten_by_dining_menu(self):
  p=H.BY['HC-MENU-083'];self.assertEqual((p['venue_id'],p['unit_price_krw'],p['price_tier']),('ROOM_MEAL',46000,'SIMULATION_ASSUMPTION'))
  self.assertEqual(H.BY['HC-PDF-THE_PAVILION-BURGER']['unit_price_krw'],44000)
 def test_lux_cannot_inherit_pizza_highball_price(self):
  p=H.BY['HC-MENU-217'];self.assertEqual(p['unit_price_krw'],25000);self.assertEqual(p['price_tier'],'SIMULATION_ASSUMPTION');self.assertEqual(p['source_resolution']['source_pages'][0]['venue'],'PIZZA_HILL')
 def test_grand_adult_reference_and_language_conflict(self):
  c=H.orders(self.a(),'POOL',600,60,'activity')[0][0];p=c['components'][-1];self.assertEqual(c['unit_price_krw'],19000);self.assertEqual(p['party_cohort'],'ADULT');self.assertEqual(p['price_tier'],'EXISTING_REFERENCE');self.assertFalse(p['date_specific_tariff_confirmed']);self.assertEqual(p['source_resolution']['language_prices']['cn'],16500)
 def test_unknown_children_are_not_declared_adults(self):
  c=H.orders(self.a(n=4,children=[{},{}]),'POOL',600,60,'activity')[0][0];p=c['components'][-1];self.assertEqual(c['unit_price_krw'],38000);self.assertEqual(p['billing_quantity'],2);self.assertEqual(p['price_tier'],'SIMULATION_ASSUMPTION');self.assertEqual(p['party_cohort'],'CHILD_FARE_UNVERIFIED')
 def test_vista_does_not_take_grand_official_fee(self):
  c=H.orders(self.a('VISTA'),'POOL',600,60,'activity')[0][0];self.assertEqual(c['unit_price_krw'],20000);self.assertEqual(c['components'][-1]['price_tier'],'SIMULATION_ASSUMPTION');self.assertIn('VISTA',c['components'][-1]['sku_id']);self.assertIn('GRAND_POOL_REFERENCE_NOT_VISTA',H.eligible(H.BY['HC-MENU-235'],self.a('VISTA'),600,60,'activity',True))
 def sky(self,a):return H.orders(a,'SKYARD',600,30,'activity')[0]
 def test_vista_guest_included_not_paid(self):
  a=self.a('VISTA');cs=self.sky(a);self.assertTrue(cs);self.assertTrue(all(c['unit_price_krw']==0 for c in cs));c=H.entitlement(a,cs[0]);self.assertTrue(c['hc_included']);self.assertEqual(H.charge(c,included=True)['status'],'포함')
 def test_grand_club_flag_is_not_room_entitlement(self):
  a=self.a();a.club=True;cs=self.sky(a);self.assertTrue(cs);self.assertTrue(all(c['unit_price_krw']==19000 for c in cs))
 def test_grand_club_deluxe_exclusion_and_suite_inclusion(self):
  for room,paid in [('HC-MENU-047',19000),('HC-MENU-049',0)]:
   a=self.a(room=room);a.club=True;cs=self.sky(a);self.assertTrue(cs);self.assertTrue(all(c['unit_price_krw']==paid for c in cs))
 def test_non_guest_not_given_included_skyard(self):
  a=self.a('VISTA');a.checked_out=True;self.assertFalse(H.OC.skyard_included(a,{}));self.assertIn('FREE_SKYARD_COVERAGE_NOT_PRESENT',H.eligible(H.BY['HC-MENU-242'],a,600,30,'activity'))
 def test_repeated_modeled_access_not_double_charge_same_day(self):
  a=self.a();c=H.entitlement(a,self.sky(a)[0]);key=c['hotel_entitlement_key'];a.visit_history={'hotel_entitlement_usage':{key:1}};self.assertTrue(H.entitlement(a,self.sky(a)[0])['hc_included']);a.sc['date']='2026-10-31';self.assertFalse(H.entitlement(a,self.sky(a)[0]).get('hc_included',False))
 def test_order_l5_l1_and_immutability(self):
  a=self.a();cs=[H.compose([H.component(H.BY[k],2 if k.endswith('083') else 1,a)],a,'snack') for k in ('HC-MENU-083','HC-MENU-217')]+[H.orders(a,'POOL',600,60,'activity')[0][0],H.entitlement(a,self.sky(a)[0])]
  for i,c in enumerate(cs):
   before=copy.deepcopy(c);ch=H.charge(c,included=c.get('hc_included',False));raw={'_row_key':str(i),'상태':ch['status'],'선택 SKU 계약':ch['sku_contract'],'확정 결제액':ch['krw'],'확인 메모':'EXPLICIT_DIAGNOSTIC','L2 부문':'F&B','L3 업장':c['venue_id'],'L4 상품':c['label'],'원장 범위':'test','행사':'none','고객':'P','체류 일차':1};rr=L.expand([raw],{str(i):{'act':'test'}});agg=LL.aggregate(rr)
   self.assertEqual(sum(r['확정 결제액'] for r in rr),ch['krw']);self.assertEqual(c,before)
   for level in ('L4','L3','L2','L1'):self.assertEqual(sum(x[1] for x in agg[level].values()),ch['krw'])
if __name__=='__main__':unittest.main()
