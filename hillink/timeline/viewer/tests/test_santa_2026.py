"""2026 source contract boundaries; no change to the 2025 price/session contract."""
import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run
import santa_packages as P
from operator_choice.autonomy_v1 import event_scenarios as E,santa_2026 as S,sauna_policy as SA

def config(package='SANTA_PKG_2026_GRAND_HYVAA_JOULUA'):
 return {'event_card_id':S.ID,'entitlements':{'A02':dict(selected_package=True,included_people=3,package_id=package)},'assumptions':{'booked_sessions':{'A02':{'date':'2026-12-18','start':'16:40'}}}}
class Contract(unittest.TestCase):
 def test_four_distinct_starting_prices_and_benefits(self):
  self.assertEqual([p['price_krw'] for p in S.PACKAGES.values()],[549000,829000,597000,757000]);self.assertEqual(sum(p['sauna'] for p in S.PACKAGES.values()),1)
 def test_2026_source_sessions(self):
  s=E.snapshot(config(),'2026-12-18','stay_1');self.assertEqual(s['sessions'],[['15:20','16:30'],['16:40','17:50']]);self.assertEqual(s['meal_fraction'],0)
 def test_dates_outside_rejected(self):
  for day in ['2025-12-19','2026-12-17','2026-12-26']:
   with self.subTest(day=day),self.assertRaisesRegex(ValueError,'OUTSIDE'):E.snapshot(config(),day,'stay_1')
 def test_old_clock_and_auto_not_2026(self):
  for start in ['16:30','auto','14:10']:
   c=config();c['assumptions']['booked_sessions']['A02']['start']=start
   with self.assertRaisesRegex(ValueError,'EXPLICIT_SESSION'):E.snapshot(c,'2026-12-18','stay_1')
 def test_cannot_turn_event_drinks_into_meal(self):
  c=config();c['assumptions']['meal_fraction']=1
  with self.assertRaisesRegex(ValueError,'NOT_A_MEAL'):E.snapshot(c,'2026-12-18','stay_1')
 def test_no_package_no_2025_ticket_price(self):
  s=E.snapshot({'event_card_id':S.ID},'2026-12-18','day_visit');a=SimpleNamespace(pid='A02',sc={'date':'2026-12-18'},N=3)
  q=E.contract(a,s);self.assertIsNone(q['unit_price_krw']);self.assertNotEqual(q['unit_price_krw'],200000)
 def test_earlybird_requires_date_and_opt_in(self):
  c=config();c['entitlements']['A02']['earlybird']=True
  with self.assertRaisesRegex(ValueError,'ELIGIBLE_BOOKING_DATE'):E.snapshot(c,'2026-12-18','stay_1')
  c['entitlements']['A02']['booking_date']='2026-11-04';s=E.snapshot(c,'2026-12-18','stay_1')
  f={'visit':{'scenario_snapshot':s},'visits':{'A02':{'building':'GRAND','party_size':3}}};q=P.room_night(f,'A02','2026-12-18',0);self.assertEqual(q['unit_price_krw'],505080);self.assertEqual(q['price_trace']['scenario_unit_price_before_discount_krw'],549000);self.assertEqual(q['price_trace']['discount_percent'],8)
  c['entitlements']['A02']['earlybird']=False;f['visit']['scenario_snapshot']=E.snapshot(c,'2026-12-18','stay_1');self.assertEqual(P.room_night(f,'A02','2026-12-18',0)['unit_price_krw'],549000);self.assertIsNone(P.room_night(f,'A02','2026-12-19',1))
 def test_package_building_and_occupancy(self):
  s=E.snapshot(config(),'2026-12-18','stay_1');v={'A02':{'building':'GRAND','party_size':3,'party_composition':{'adult_count':2,'children':[{}]}}};S.validate_visits(s,v,{})
  v['A02']['party_size']=4
  with self.assertRaisesRegex(ValueError,'EXTRA_ROOM'):S.validate_visits(s,v,{})
  v['A02']['building']='VISTA'
  with self.assertRaisesRegex(ValueError,'BUILDING'):S.validate_visits(s,v,{})
 def test_day_visit_package_rejected(self):
  with self.assertRaisesRegex(ValueError,'ROOM_NIGHT'):E.snapshot(config(),'2026-12-18','day_visit')
 def test_2025_contract_retains_four_sessions_and_price(self):
  c={'event_card_id':'SANTA_KIDS_VILLAGE_2025','assumptions':{'sessions':[['11:00','12:00'],['14:10','15:10'],['15:20','16:20'],['16:30','17:30']],'duration_min':60,'historical_model_prices_acknowledged':True},'entitlements':{'A02':{'selected_package':True,'included_people':3}}}
  s=E.snapshot(c,'2025-12-19','stay_1');self.assertEqual(len(s['sessions']),4);self.assertEqual(P.selected({'visit':{'scenario_snapshot':s}},'A02')['price_krw'],559000)
 def test_duplicate_package_and_unknown_fields_rejected(self):
  c=config();c['entitlements']['A02']['invented']=1
  with self.assertRaisesRegex(ValueError,'FIELDS_INVALID'):E.snapshot(c,'2026-12-18','stay_1')
  s=E.snapshot(config(),'2026-12-18','stay_1')
  with self.assertRaisesRegex(ValueError,'SECOND_ROOM'):S.validate_visits(s,{},dict(catalog_options={'room_products':{'A02':'HC-MENU-003'}}))

 def test_lounge_family_age_gate_and_signature_scope(self):
  a=SimpleNamespace(pid='A02',sc={'date':'2026-12-18','scenario_snapshot':E.snapshot(config('SANTA_PKG_2026_VISTA_SIGNATURE'),'2026-12-18','stay_1')},vs={'party_composition':{'adult_count':2,'children':[{}]}},visit_history={})
  self.assertIn('SANTA_PACKAGE_17H_CHILD_RESTRICTION_PARTY_SPLIT_NOT_MODELED',S.lounge_reasons(a,{'sku_id':'HC-GRAND-LOUNGE-278'},1050,50))
  self.assertIn('SIGNATURE_HAPPY_HOUR_ONLY_NO_CLUB_TEA_BREAKFAST',S.lounge_reasons(a,{'sku_id':'HC-GRAND-LOUNGE-277'},840,50))
  self.assertEqual(SA.contract(a)['facility_id'],'VISTA_SAUNA')
  a.sc['date']='2026-12-20';self.assertIsNone(S.actor_package(a))
 def test_malformed_booking_is_validation_error(self):
  c=config();c['assumptions']['booked_sessions']=['bad']
  with self.assertRaises(ValueError):E.snapshot(c,'2026-12-18','stay_1')

 def test_package_rights_do_not_invent_a_session_reservation(self):
  c=config();c['assumptions']={};s=E.snapshot(c,'2026-12-18','stay_1')
  a=SimpleNamespace(pid='A02',sc={'date':'2026-12-18'},phase='checkin',checked_in=True,visit_history={})
  self.assertIn('SANTA_2026_SESSION_RESERVATION_NOT_DECLARED',E.eligibility(a,s)[0])
  c=config();c['assumptions']['santa_before_checkin']='not_allowed';s=E.snapshot(c,'2026-12-18','stay_1');a.checked_in=False
  self.assertIn('SANTA_2026_CHECKIN_REQUIRED_BEFORE_ADMISSION',E.eligibility(a,s)[0])
