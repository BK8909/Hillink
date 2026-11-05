import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as V
from operator_choice.autonomy_v1 import consumption_orders as O,hotel_catalog as H,hotel_runtime as R
class PostVenueTests(unittest.TestCase):
 def actor(self):
  return SimpleNamespace(pid='P',sc=dict(date='2026-10-30',catalog_options={}),N=1,B='GRAND',stay=True,checked_in=True,checked_out=False,C={'kids':False},vs={},visit_history={},room='GRAND_ROOM',hunger_e=1,fatigue=0,meals={},food=[])
 def choose(self,a,choices,t,duration,world):
  c=choices[0];return dict(sku_contract=c,label=c['label']),dict(candidates=[],selected=c['sku_id'])
 def test_adopted_product_and_included_offer_are_untouched(self):
  for included in (False,True):
   o={'id':'locked','sku_contract':{'sku_id':'FINAL','unit_price_krw':100}};before=copy.deepcopy(o)
   result=O.complete(self.actor(),'turn_dinner','restaurant','MOEGI',1080,90,'식사',o,{},included)
   self.assertIs(result[0],o);self.assertEqual(o,before)
 def test_solo_uses_official_alacarte_without_relaxing_course_minimum(self):
  a=self.actor();source=copy.deepcopy(H.BY['HC-MENU-189'])
  with patch.object(R.AD,'World') as world,patch.object(R,'POST_VENUE_RULE_CHOOSE',self.choose):
   offer,trace,_=O.complete(a,'turn_dinner','restaurant','MOEGI',1080,90,'식사',None,{},False)
  c=offer['sku_contract'];self.assertTrue(c['sku_id'].startswith('HC-ORDER-'));self.assertTrue(c['components'][0]['sku_id'].startswith('HC-PDF-MOEGI-'))
  self.assertEqual(c['order_origin'],'NATIVE_POST_VENUE_MENU_DECISION');self.assertFalse(trace['hotel_product_decision']['unspecified_meal_model']);self.assertEqual(H.BY['HC-MENU-189'],source)
  self.assertIn('MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY',H.eligible(source,a,1080,90,'dinner'))
 def test_closed_time_is_not_filled_by_unspecified_model(self):
  a=self.actor()
  with patch.object(R.AD,'World'):
   offer,trace,_=O.complete(a,'turn_dinner','restaurant','MOEGI',1380,60,'식사',None,{},False)
  self.assertIsNone(offer);self.assertEqual(trace['hotel_product_decision']['status'],'UNRESOLVED')
if __name__=='__main__':unittest.main()
