"""V2 official facility right: service, non-forced choice, room and L5 contract."""
import copy,unittest
from types import SimpleNamespace
import test_official_contracts
from operator_choice.autonomy_v1 import breakfast_policy as BP,douglas_light_breakfast as DLB,ledger as LG
from operator_choice.operator_world_v1_1 import stay_planner as SP
import ledger_l5 as L5
import room_revenue as RR
import visit_run as VR

class DouglasLightBreakfast(unittest.TestCase):
 def actor(self,n=2,policy=BP.V2):
  return SimpleNamespace(B='DOUGLAS',stay=True,checked_in=True,checked_out=False,N=n,vs={'building':'DOUGLAS','party_size':n},sc={'breakfast_policy':policy})
 def test_facility_right_is_not_buffet_entitlement(self):
  a=self.actor();o=DLB.offer(a,8*60,2)
  self.assertEqual(o['id'],DLB.ID);self.assertEqual(o['venue'],'DOUGLAS_LOUNGE');self.assertTrue(o['in_package'])
  self.assertEqual(BP.covered_adults(a),0);self.assertFalse(BP.whole_party_covered(a))
  self.assertEqual(DLB.charge(a)['krw'],0);self.assertEqual(DLB.charge(a)['sku_contract']['billing_quantity'],2)
  self.assertNotIn('used',a.vs)
 def test_historical_v1_and_non_guests_unchanged(self):
  self.assertIsNone(DLB.offer(self.actor(policy=BP.V1),8*60))
  for key,value in [('B','GRAND'),('stay',False),('checked_in',False),('checked_out',True)]:
   a=self.actor();setattr(a,key,value);self.assertIsNone(DLB.offer(a,8*60))
 def test_time_and_extra_person_not_silently_free_or_charged(self):
  self.assertTrue(DLB.offer(self.actor(),6*60)['available'])
  self.assertFalse(DLB.offer(self.actor(),9*60+45)['available'])
  self.assertFalse(DLB.offer(self.actor(3),8*60)['available'])
  charge=DLB.charge(self.actor(3));self.assertIsNone(charge['krw']);self.assertFalse(charge['auto_charge'])
 def test_light_breakfast_is_meal_and_zero_payment_contract(self):
  a=self.actor();a.meals={};a.meal_log=[];o=DLB.offer(a,8*60)
  self.assertEqual(LG.record_meal(a,DLB.ID,'engine','식사',8*60,o['food']['meal_fraction']),'breakfast')
  self.assertEqual(a.meal_log[0]['size'],'light')
  c=LG.charge(a,DLB.ID,'engine',DLB.VENUE,o,True)
  self.assertEqual((c['status'],c['krw'],c['sku_contract']['sku_id']),('포함',0,DLB.ID))
  self.assertEqual(L5.LOC_L23[DLB.VENUE],('F&B','더글라스 라운지'))
 def test_room_rate_not_upgraded_and_right_metadata_preserved(self):
  for catalog in [False,True]:
   f={'visit_id':'douglas-test','visit':{'start_date':'2026-10-24','breakfast_policy':BP.V2},'visits':{'P':{'building':'DOUGLAS','party_size':2}}}
   if catalog:f['visit']['catalog_policy']='C01_HOTEL_CATALOG_V1'
   q=RR.native_price(f,'P','2026-10-24',0,1)
   self.assertEqual(q['virtual_gross_krw'],259000)
   self.assertEqual(q['breakfast_contract_kind'],DLB.ID);self.assertEqual(q['breakfast_contract_people'],2)
   self.assertFalse(q['room_rate_changed_for_breakfast'])
 def test_room_plan_validation_is_policy_versioned(self):
  self.assertEqual(BP.validate_plan('breakfast_included','DOUGLAS','stay_1',{'breakfast_policy':BP.V2}),'breakfast_included')
  with self.assertRaises(ValueError):BP.validate_plan('breakfast_included','DOUGLAS','stay_1',{'breakfast_policy':BP.V1})
  with self.assertRaises(ValueError):BP.validate_plan('breakfast_included','DOUGLAS','day_visit',{'breakfast_policy':BP.V2})
 def test_daily_facility_right_is_not_consumed_as_one_off_package(self):
  for day in ['2026-10-25','2026-10-26']:
   charge=DLB.charge(self.actor())
   flow={'plans':{'P':{'scenes':[{'act':DLB.ID,'loc':DLB.VENUE,'meal':'breakfast','basis':{'charge':charge}}]}}}
   VR._advance_state({},flow,'P',{'date':day,'phase':'checkout','day_index':2})
   self.assertEqual(charge['status'],'포함');self.assertEqual(charge['krw'],0)
   self.assertNotIn('entitlement_id',charge)
 def test_location_uses_existing_douglas_building(self):
  self.assertEqual(SP.BLDG_OF[DLB.VENUE],'DOUGLAS')

if __name__=='__main__':unittest.main()
