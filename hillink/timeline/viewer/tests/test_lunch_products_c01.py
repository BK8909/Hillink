import pytest
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run
from operator_choice.autonomy_v1 import candidate_services as C,lunch_products as L,menu_connections as M

class LunchProductConnections(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.inputs=C.AD.load_inputs()
 def actor(self,day='2026-10-26',n=2,kids=False):
  sc=C.AD.scenario(date=day);a=C.AD.Agent('A08',*self.inputs,sc)
  a.N=n;a.C=copy.deepcopy(a.C);a.C['kids']=kids;a.loc='VISTA_LOBBY';a.t=750
  return a
 def options(self,a,code,t=750,travel=0):
  w=C.AD.World(a.sc).engine_world(t)
  return L.options(a,code,t,{o['id']:o for o in w['offers']},C.service_check,C.SP.ACT[code][3],travel)
 @pytest.mark.requires_private_personas('A08')
 def test_source_lunch_products_and_reservation_exclusion(self):
  a=self.actor()
  with C.install(a.sc['date']):
   offers,excluded=self.options(a,'lunch_geumryong')
   self.assertEqual(len(offers),10)
   self.assertIn('ADVANCE_RESERVATION_NOT_CONFIRMED',next(r for r in excluded if r['candidate_id']=='C01_GEUM_KYUNG')['reasons'])
   self.assertTrue(all(o['sku_contract']['service_period']=='lunch' for o in offers))
   dinner=next(o for o in C.AD.World(a.sc).engine_world(1080)['offers'] if o['id']=='C01_GEUM_KYUNG')
   self.assertFalse(M.attach(dinner,a,1080)['available'])
 @pytest.mark.requires_private_personas('A08')
 def test_moegi_last_order_differs_from_venue_close(self):
  a=self.actor()
  with C.install(a.sc['date']):
   for t,course,sashimi in [(750,True,True),(810,True,True),(811,False,True),(830,False,True),(841,False,False),(930,False,False)]:
    offers,_=self.options(a,'lunch_moegi',t)
    ids={o['id'] for o in offers}
    self.assertEqual('C01_MOEGI_LUNCH' in ids,course)
    self.assertEqual('C01_MOEGI_SASHIMI' in ids,sashimi)
    self.assertFalse(any(o['sku_contract']['source_line'] in (189,190,191) for o in offers))
 @pytest.mark.requires_private_personas('A08')
 def test_weekday_season_child_and_set_quantity(self):
  for day,n,kids in [('2026-10-26',2,False),('2026-10-24',2,False),('2026-11-02',2,False),('2026-10-26',1,False),('2026-10-26',4,True)]:
   a=self.actor(day,n,kids)
   with C.install(day):
    offers,_=self.options(a,'lunch_myongwol');ids={o['id'] for o in offers}
    self.assertEqual('C01_MYONG_SPECIAL2' in ids,n==2 and not kids)
    self.assertEqual('C01_MYONG_AUTUMN' in ids,day=='2026-10-26' and n>=2 and not kids)
    for o in offers:
     if o.get('c01_lunch_venue_only'):
      self.assertIsNone(o['price_pp_krw'])
      charge=C.AD.LG.charge(a,'lunch_myongwol','activity','MYONGWOLGWAN',offer=o)
      self.assertIsNone(charge['krw']);self.assertEqual(charge['status'],'가격 미정');continue
     c=o['sku_contract'];self.assertEqual(c['billing_quantity'],1 if c['billing_unit']=='set' else n)
 @pytest.mark.requires_private_personas('A08')
 def test_confirmed_ondal_portion_prices_reach_lunch_charge(self):
  a=self.actor()
  with C.install(a.sc['date']):
   offers,_=self.options(a,'lunch_ondal')
   for code,price in [('C01_ONDAL_COURT',165000),('C01_ONDAL_SURA',195000)]:
    o=next(o for o in offers if o['id']==code)
    charge=C.AD.LG.charge(a,'lunch_ondal','activity','ONDAL',offer=o)
    self.assertEqual(charge['krw'],price*2);self.assertEqual(charge['status'],'유료')
    self.assertEqual(charge['sku_contract']['billing_quantity'],2)
 @pytest.mark.requires_private_personas('A08')
 def test_selected_contract_is_scored_before_action_and_charged_once(self):
  a=self.actor()
  with C.install(a.sc['date']):
   C.AD.plan_do(a,'lunch_myongwol','MYONGWOLGWAN',750,{}, {})
   r=a.log[-1];d=r['internal']['c01_product_decision'];c=r['charge']['sku_contract']
   self.assertEqual(d['selection_phase'],'BEFORE_ACTION_AND_CHARGE')
   selected=next(x for x in d['packet']['candidates'] if x['candidate_id']==d['selected_product_id'])
   self.assertEqual(selected['sku_id'],c['sku_id'])
   self.assertAlmostEqual(selected['base_score'],sum(t['value'] for t in selected['terms']))
   self.assertEqual(r['charge']['krw'],c['unit_price_krw']*c['billing_quantity'])
   self.assertEqual(c['resolution_layer'],'PRE_ACTION_CONDITIONAL_LUNCH_MENU_SELECTION')
   self.assertAlmostEqual(sum(d['sampling']['probabilities'].values()),1)
 @pytest.mark.requires_private_personas('A08')
 def test_venue_weights_unchanged_and_context_restored(self):
  a=self.actor();before=C.AD.plan_do
  weights={code:C.SP.lunch_weight(code,a.P,a.C,a.ctx()) for code in L.VENUES}
  with C.install(a.sc['date']):
   self.assertEqual(weights,{code:C.SP.lunch_weight(code,a.P,a.C,a.ctx()) for code in L.VENUES})
  self.assertIs(C.AD.plan_do,before)

if __name__=='__main__':unittest.main()
