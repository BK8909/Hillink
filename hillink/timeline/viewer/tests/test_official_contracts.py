import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run
from operator_choice.autonomy_v1 import hotel_catalog as H
class OfficialContracts(unittest.TestCase):
 def a(self,n=4,children=None,adults=None,day='2026-07-17'):
  party=dict(adult_count=n-len(children),children=children) if children is not None else dict(adult_count=adults or n,children=[])
  return SimpleNamespace(pid='P',sc=dict(date=day,catalog_options={}),N=n,B='VISTA',stay=True,checked_in=True,checked_out=False,vs={'nights':2,'party_composition':party},C={'kids':bool(party['children'])},visit_history={})
 def buffet(self,a):return H.orders(a,'THE_BUFFET',1050,90,'dinner')[0][0]
 def test_buffet_four_adults_two_children_and_infants(self):
  cases=[([],4,792000),([{'age_months':72,'school_stage':'elementary'}]*2,2,592000),([{'age_months':24,'school_stage':'preschool'}]*2,2,396000)]
  for children,adults,total in cases:
   c=self.buffet(self.a(children=children,adults=adults));self.assertEqual(c['unit_price_krw'],total);self.assertEqual(sum(x['billing_quantity'] for x in c['components']),4)
 def test_unknown_age_is_not_reported_as_known_adult(self):
  c=self.buffet(self.a(children=[{},{}]));p=c['components'][1];self.assertEqual(p['party_cohort'],'UNKNOWN_CHILD_FARE');self.assertIn('연령 미확정',p['label']);self.assertEqual(p['price_tier'],'SIMULATION_ASSUMPTION')
 def test_weekday_cannot_use_1730_holiday_session(self):
  self.assertFalse(H.orders(self.a(day='2026-07-16'),'THE_BUFFET',1050,90,'dinner')[0])
 def test_brunch_drink_is_part_of_scored_candidate(self):
  a=self.a(day='2026-10-30');cs,_=H.orders(a,'THE_PAVILION',720,60,'lunch');bundles=[c for c in cs if c.get('required_drink_choice')]
  self.assertGreater(len(bundles),2);self.assertGreater(len({c['unit_price_krw'] for c in bundles}),1)
  for c in bundles:self.assertEqual([p['billing_quantity'] for p in c['components']],[4,4])
 def test_group_set_once_and_moegi_solo_alacarte(self):
  self.assertEqual(H.quantity(H.BY['HC-MENU-086'],self.a()),1)
  cs,_=H.orders(self.a(n=1,day='2026-10-30'),'MOEGI',1080,90,'dinner');self.assertTrue(any(p['sku_id']=='HC-PDF-MOEGI-KAKE-UDON' for c in cs for p in c['components']))
 def test_package_exact_people_and_benefit_once(self):
  a=self.a(n=3);a.B='DOUGLAS';a.sc['catalog_options']={'room_products':{'P':'HC-MENU-021'}}
  room=H.BY['HC-MENU-021'];self.assertFalse(H.eligible(room,a,0,0,'booking'));a.N=4;self.assertIn('PACKAGE_PARTY_OPTION_MISMATCH',H.eligible(room,a,0,0,'booking'));a.N=3
  p=H.BY['HC-SRC-PIZZA-QUATTRO-TAKEOUT'];c=H.compose([H.component(p,1,a)],a,'dinner');covered=H.entitlement(a,c);self.assertEqual(H.charge(covered,included=True)['krw'],0)
  a.visit_history={'hotel_entitlement_usage':{covered['hotel_entitlement_key']:True}};self.assertNotIn('hc_included',H.entitlement(a,c))
 def test_known_infant_does_not_get_an_automatic_adult_main(self):
  a=self.a(children=[{'age_months':24,'school_stage':'preschool'}]*2,day='2026-10-30')
  self.assertEqual(H.quantity(H.BY['HC-MENU-203'],a),2)
  p=H.BY['HC-IRD-RS_CLUB_SANDWICH'];parts=H.OC.child_parts(p,a,1080,45,'dinner',H,H.modeled_party(a));self.assertEqual(parts,[])
 def test_unchanged_original_catalog_and_new_fingerprint(self):
  self.assertEqual(len(H.BASE_DATA['products']),298);self.assertNotEqual(H.BASE_SHA,H.SHA);self.assertEqual(len(H.BY),len(H.DATA['products']))
  base_ids={p['sku_id'] for p in H.BASE_DATA['products']}
  for p in H.DATA['products']:
   if p['sku_id'] not in base_ids:self.assertFalse(p.get('verified_source_aliases'),p['sku_id'])
if __name__=='__main__':unittest.main()
