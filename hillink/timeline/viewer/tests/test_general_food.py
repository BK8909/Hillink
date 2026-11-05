import copy,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1 import general_food as G
class GeneralFoodTest(unittest.TestCase):
 def setUp(self):
  self.o={'venue':'X','food':{'meal_fraction':1,'menu_tags':['pizza']},'sku_contract':{'service_period':'dinner'}}
  self.ctx={'date':'2026-10-24','time':1080,'prior_meals':[],'food_observation':{'status':'UNOBSERVED_IN_ACCEPTED_INPUT','indirect_fact_ids':{}}}
  self.terms=[{'factor':'음식 경험','value':2,'facet':'food','fact_ids':['F']}];self.common=[{'factor':'음식 경험','value':1.2}]
 def calc(self,p,**kw):
  with patch.dict(os.environ,HILLINK_GENERAL_FOOD_POLICY=p):return G.adjustment(self.o,self.terms,self.ctx,common_terms=self.common,**kw)
 def test_default_off(self):
  with patch.dict(os.environ,{},clear=True):self.assertEqual(G.policy(),'A');self.assertEqual(G.adjustment(self.o,self.terms,self.ctx)[0],0)
 def test_strong_and_unmapped_protected(self):
  for st in ['LINKED_PREFERENCE','FOOD_EVIDENCE_UNMAPPED','UNVERIFIED']:
   self.ctx['food_observation']['status']=st;self.assertEqual(self.calc('C')[0],0)
 def test_direct_negative_priority(self):
  self.ctx['direct_avoid_venues']={'X':['F-negative']};d,t=self.calc('B');self.assertEqual(d,0);self.assertEqual(t['reason'],'SOURCE_LINKED_NEGATIVE_EVIDENCE_PROTECTED')
  self.ctx.pop('direct_avoid_venues');self.terms.append(dict(factor='negative',value=-1,fact_ids=['F-negative']));self.assertEqual(self.calc('C')[0],0)
 def test_time_only_common_part_not_personal(self):
  self.assertAlmostEqual(self.calc('B')[0],.06);self.terms[0]['value']=100;self.assertAlmostEqual(self.calc('B')[0],.06)
  self.o['sku_contract']['service_period']='lunch';self.assertAlmostEqual(self.calc('B')[0],.03)
  self.o['sku_contract']['service_period']='breakfast';self.assertEqual(self.calc('C')[0],0)
 def test_actual_history_and_no_future(self):
  from datetime import date
  now=date.fromisoformat(self.ctx['date']).toordinal()*1440+1080
  m=dict(venue_id='X',event_id='e',fraction=1,end_absolute=now-100,menu_tags=['pizza']);self.ctx['prior_meals']=[m]
  d,t=self.calc('C');self.assertLess(d,0);self.assertEqual(t['prior_event_ids'],['e'])
  m['end_absolute']=now+1;self.assertEqual(self.calc('C')[0],self.calc('B')[0])
 def test_no_repeat_double_count(self):
  from datetime import date
  self.ctx['prior_meals']=[dict(venue_id='X',event_id='e',fraction=1,end_absolute=date.fromisoformat(self.ctx['date']).toordinal()*1440,menu_tags=['pizza'])]
  self.assertEqual(self.calc('C',existing_repeat=True)[0],self.calc('B')[0])
 def test_read_only_and_provenance(self):
  old=copy.deepcopy((self.o,self.ctx,self.terms));d,t=self.calc('B');self.assertEqual(old,(self.o,self.ctx,self.terms));self.assertEqual(t['stage'],'BEFORE_SELECTION');self.assertIn('ASSUMPTION',t['coefficient_origin']);self.assertEqual(d,sum(c['delta'] for c in t['components']))
if __name__=='__main__':unittest.main()
