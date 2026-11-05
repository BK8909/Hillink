import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as VR
from operator_choice.autonomy_v1 import candidate_services as C

class CandidateServiceTests(unittest.TestCase):
 def test_moegi_current_vs_future_and_closed(self):
  for t,eligible,plan in [(1050,False,'FUTURE_SERVICE_ONLY'),(1110,True,'AVAILABLE_NOW'),(1290,False,'NO_FITTING_SESSION')]:
   r=C.service_check('MOEGI','2026-10-24',t,90)
   self.assertEqual((r['eligible'],r['planning_viability']),(eligible,plan))
  self.assertTrue(C.service_check('MYONGWOLGWAN','2026-10-24',1050,90)['eligible'])
 def test_calendar_is_not_union(self):
  self.assertFalse(C.service_check('GRAND_CLUB_LOUNGE','2026-10-24',1180,10)['eligible'])
  self.assertTrue(C.service_check('GRAND_CLUB_LOUNGE','2025-10-24',1180,10)['eligible'])
  self.assertFalse(C.service_check('THE_BUFFET','2026-10-24',780,20)['eligible'])
  self.assertTrue(C.service_check('THE_BUFFET','2026-10-23',780,20)['eligible'])
  self.assertFalse(C.service_check('RIVERPARK','2026-10-24',720,60)['eligible'])
 def test_unknown_window_not_free_pass(self):
  self.assertFalse(C.service_check('UNKNOWN','2026-10-24',720)['eligible'])
 def test_install_restores_all_runtime_bindings(self):
  before=(C.SP.WIN,C.AD.World.engine_world,C.EN._score,C.EN.out_of_pocket,C.AD.turn_raw)
  with self.assertRaises(RuntimeError):
   with C.install('2026-10-24'):raise RuntimeError('scope failure')
  self.assertEqual(before,(C.SP.WIN,C.AD.World.engine_world,C.EN._score,C.EN.out_of_pocket,C.AD.turn_raw))
  self.assertNotIn('MOEGI',C.AD.ENGINE_DOMAIN)
 def test_offers_have_distinct_service_price_and_reservation(self):
  with C.install('2026-10-24'):
   offers={o['id']:o for o in C.AD.World({'date':'2026-10-24'}).engine_world(1050)['offers']}
   o=offers['MOEGI'];self.assertIsNone(o['price_pp_krw']);self.assertIsNone(C.EN.out_of_pocket(o))
   self.assertEqual(o['service_contract']['planning_viability'],'FUTURE_SERVICE_ONLY')
   self.assertEqual(o['service_contract']['reservation_state'],'UNKNOWN_NOT_BOOKED')
   actor=SimpleNamespace(vs={},visit_history={},N=2)
   charge=C.AD.LG.charge(actor,'MOEGI','restaurant','MOEGI',offer=o)
   self.assertEqual(charge['status'],'가격 미정');self.assertIsNone(charge['krw'])
   self.assertEqual(offers['GEUMRYONG']['window']['start'],'18:00')
   self.assertEqual(offers['MYONGWOLGWAN']['window']['end'],'21:00')
 def test_weekend_party_rule_without_preference_change(self):
  with C.install('2026-10-24'):
   o=next(o for o in C.AD.World({'date':'2026-10-24'}).engine_world(1080)['offers'] if o['id']=='ONDAL')
   for n in (1,2,4):
    reasons=C.EN.feasible(o,1080,{'used':set(),'hunger':1},{'end':'23:00','party_size':n,'alcohol_eligible':True})
    self.assertEqual('WEEKEND_COURSE_MINIMUM_TWO' in reasons,n==1)
 def test_all_dated_windows_respect_source_predicates(self):
  for venue,ws in C.V.WALKERHILL_VENUE_WINDOWS.items():
   for day in ('2026-01-24','2026-07-24','2026-10-24','2026-10-25','2026-12-24'):
    for w in C.windows(venue,day):
     self.assertIn(w,ws);self.assertTrue(w.opens_on(C.date.fromisoformat(day)))
 def test_precheckin_quantitative_guests_are_blocked_with_reason(self):
  inputs=C.AD.load_inputs()
  if 'A08' not in inputs[0]:self.skipTest('private execution profile unavailable')
  sc=C.AD.scenario();a=C.AD.Agent('A08',*inputs,sc);a.B='GRAND';a.stay=True;a.checked_out=False
  with C.install(sc['date']):
   for checked in (False,True):
    a.checked_in=checked
    offers={o['id']:o for o in C.AD.engine_world_for(a,C.AD.World(sc),960)['offers']}
    for key in ('POOL','SAUNA','ROOM_MEAL'):
     if key not in offers:continue
     if not checked:
      self.assertFalse(offers[key]['available'])
      self.assertEqual(offers[key]['service_contract']['blocked_reason'],'CURRENT_CHECKED_IN_GUEST_REQUIRED')
     else:self.assertNotEqual(offers[key].get('status'),'CURRENT_CHECKED_IN_GUEST_REQUIRED')
 def test_douglas_breakfast_party_time_and_entitlement(self):
  inputs=C.AD.load_inputs()
  if 'A08' not in inputs[0]:self.skipTest('private execution profile unavailable')
  for n in (1,2,4):
   for minute in (510,600):
    sc=C.AD.scenario();a=C.AD.Agent('A08',*inputs,sc)
    a.B='DOUGLAS';a.stay=True;a.checked_in=True;a.checked_out=False;a.N=n;a.loc='DOUGLAS_ROOM'
    captured=[];original=C.TC.decide_turn
    def capture(traits,visit,world,turn,state):
     captured.extend(world['offers']);return original(traits,visit,world,turn,state)
    with C.install(sc['date']),C.patch.object(C.TC,'decide_turn',capture):
     C.AD.breakfast_step(a,C.AD.World(sc),minute)
     offer=next((o for o in captured if o['id']=='DOUGLAS_LIGHT_BREAKFAST'),None)
     self.assertEqual(offer is not None,n<=2 and minute==510)
     if offer:
      charge=C.AD.LG.charge(a,offer['id'],'restaurant','DOUGLAS_LOUNGE',offer=offer)
      self.assertEqual(charge['status'],'포함');self.assertEqual(charge['krw'],0)
 def test_legacy_m4_source_configuration_not_replaced(self):
  self.assertNotEqual(C.configuration()['sha256'],C.M4.configuration()['sha256'])
  self.assertEqual(C.M4.configuration()['version'],'m4-live-v2-shared-world')

if __name__=='__main__':unittest.main()
