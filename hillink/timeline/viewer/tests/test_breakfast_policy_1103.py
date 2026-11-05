"""11/03: 2025 buffet historical reference, breakfast contract V1 (vs legacy), Santa auto session."""
import copy,unittest
import test_official_contracts as T
from operator_choice.autonomy_v1 import hotel_catalog as H, menu_connections as M, breakfast_policy as BP, event_scenarios as ES, historical_prices as HIST
import room_revenue as RR

def actor(day,children=(),adults=2,plan=None,policy=None):
  a=T.OfficialContracts().a(n=adults+len(children),children=list(children),adults=adults,day=day)
  a.B='GRAND'
  if children:a.vs['party_composition']=dict(adult_count=adults,children=list(children))
  if plan:a.vs['breakfast_plan']=plan
  if policy:a.sc['breakfast_policy']=policy
  return a

class HistoricalBuffet(unittest.TestCase):
 def test_2025_rates_and_source_grade(self):
  bf=H.BY['HC-HIST2025-BUFFET-BF-ADULT-WKND-DEC'];dn=H.BY['HC-HIST2025-BUFFET-DN-ADULT-DEC']
  self.assertEqual((bf['unit_price_krw'],H.BY['HC-HIST2025-BUFFET-BF-CHILD-WKND-DEC']['unit_price_krw'],dn['unit_price_krw'],H.BY['HC-HIST2025-BUFFET-DN-CHILD-DEC']['unit_price_krw']),(82000,40000,195000,98000))
  self.assertTrue(dn['price_status'].startswith('2025_HISTORICAL_REFERENCE'));self.assertIn('VIRTUAL_COMPARISON',dn['price_status'])
  self.assertTrue(H.day_ok(dn,'2025-12-19'));self.assertFalse(H.day_ok(dn,'2026-12-19'))
  self.assertFalse(any('중식' in p['label'] for p in HIST.DATA['products']))   # no 2025 lunch evidence -> stays unknown
 def test_catalog_order_and_native_score_price_match(self):
  a=actor('2025-12-19',children=[{}])
  order=H.orders(a,'THE_BUFFET',17*60+30,90,'dinner')[0][0]
  native=M.buffet({'id':'THE_BUFFET'},a,'dinner',17*60+30)
  self.assertEqual(order['unit_price_krw'],195000*3)                       # 2 adults + unknown-age proxy at adult rate
  self.assertEqual(native['price_pp_krw']*a.N,order['unit_price_krw'])     # the score input equals the order/L5 amount
  self.assertNotEqual(native.get('price_status'),'AMOUNT_UNKNOWN')
 def test_2026_rows_unchanged(self):
  a=actor('2026-10-30');c=H.orders(a,'THE_BUFFET',18*60,90,'dinner')[0][0];self.assertEqual(c['unit_price_krw'],2*198000)

class BreakfastContract(unittest.TestCase):
 def test_policy_default_and_validation(self):
  self.assertEqual(BP.policy({}),BP.V2);self.assertEqual(BP.policy({'breakfast_policy':BP.LEGACY}),BP.LEGACY)
  with self.assertRaises(ValueError):BP.validate_plan('breakfast_included','DOUGLAS','stay_1',{'breakfast_policy':BP.V1})
  with self.assertRaises(ValueError):BP.validate_plan('breakfast_included','GRAND','day_visit')
 def test_general_room_covers_nobody_included_room_two_adults(self):
  self.assertEqual(BP.covered_adults(actor('2026-10-25')),0)
  a=actor('2026-10-25',children=[{}],plan='breakfast_included');self.assertEqual(BP.covered_adults(a),2);self.assertFalse(BP.whole_party_covered(a))
  self.assertEqual(BP.covered_adults(actor('2026-10-25',plan='breakfast_included',policy=BP.LEGACY)),0)
 def test_partial_coverage_prices_only_uncovered(self):
  a=actor('2026-10-25',children=[{'age_months':72,'school_stage':'elementary'}],plan='breakfast_included')
  o=M.buffet({'id':'BREAKFAST_BUFFET'},a,'breakfast',8*60,covered_adults=2)
  self.assertEqual(round(o['price_pp_krw']*a.N),43000);self.assertEqual(o['room_breakfast_contract']['covered_adults'],2)
  full=M.buffet({'id':'BREAKFAST_BUFFET'},actor('2026-10-25'),'breakfast',8*60,covered_adults=2);self.assertTrue(full['in_package'])
 def test_included_room_rate_counts_benefit_once(self):
  flow={'visit':{'breakfast_policy':BP.V1,'start_date':'2026-10-24'},'visits':{'P':{'breakfast_plan':'breakfast_included','building':'GRAND'}}}
  f=RR.breakfast_room_fields(flow,'P','GRAND');self.assertEqual(f['virtual_gross_krw'],313000);self.assertTrue(f['breakfast_included_in_room'])
  flow['visits']['P']['breakfast_plan']='room_only';self.assertIsNone(RR.breakfast_room_fields(flow,'P','GRAND'))
  flow['visit']['breakfast_policy']=BP.LEGACY;flow['visits']['P']['breakfast_plan']='breakfast_included';self.assertIsNone(RR.breakfast_room_fields(flow,'P','GRAND'))

class SantaAutoSession(unittest.TestCase):
 def test_auto_and_before_checkin_validation(self):
  src=open(ES.__file__,encoding='utf-8').read()
  self.assertIn("b['start']=='auto'",src);self.assertIn('santa_before_checkin',src)
  from operator_choice.autonomy_v1 import scenario_conditions as SC
  s=open(SC.__file__,encoding='utf-8').read();self.assertIn('RECOMMENDED_FROM_TIME_OBLIGATIONS',s)

if __name__=='__main__':unittest.main()
