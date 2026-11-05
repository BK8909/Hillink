import pytest
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run,ledger_service as LS
from operator_choice.autonomy_v1 import candidate_services as C,menu_connections as M

def actor(n=2,kids=False,day='2026-10-24'):
 return SimpleNamespace(N=n,C={'kids':kids},sc={'date':day},t=780)

class MenuConnections204(unittest.TestCase):
 @pytest.mark.requires_private_personas('A08')
 def test_continuous_service_is_a_real_dinner_candidate(self):
  sc=C.AD.scenario();a=C.AD.Agent('A08',*C.AD.load_inputs(),sc)
  with C.install(sc['date']):
   w=C.AD.engine_world_for(a,C.AD.World(sc),1080)
   o=next(o for o in w['offers'] if o['id']=='PIZZA_HILL')
   self.assertTrue(o['available']);self.assertEqual(o['window'],{'start':'17:30','end':'22:00'})
   self.assertEqual(o['sku_contract']['billing_unit'],'set')
 def test_party_sets_are_one_set_with_exact_total(self):
  with C.install('2026-10-24'):
   base=next(o for o in C.AD.World(C.AD.scenario()).engine_world(1080)['offers'] if o['id']=='PIZZA_HILL')
   for n,amount in [(2,184000),(3,251000),(4,316000),(6,351000)]:
    o=M.attach(base,actor(n),1080);c=o['sku_contract'];bill=M.bill(c,actor(n))
    self.assertEqual(c['billing_quantity'],1);self.assertEqual(bill['krw'],amount)
    self.assertAlmostEqual(o['price_pp_krw']*n,amount)
   self.assertNotIn('sku_contract',M.attach(base,actor(1),1080))
   self.assertIsNone(M.attach(base,actor(1),1080)['price_pp_krw'])
 def test_weekday_season_and_minimum_are_independent_gates(self):
  with C.install('2026-10-24'):
   base=next(o for o in C.AD.World(C.AD.scenario()).engine_world(1080)['offers'] if o['id']=='C01_GEUM_SET1')
   for day,n,kids,yes in [('2026-10-26',2,False,True),('2026-10-24',2,False,False),('2026-10-26',1,False,False),('2026-10-26',4,True,False)]:
    o=M.attach(base,actor(n,kids,day),1080)
    self.assertEqual('sku_contract' in o,yes)
    if not yes:self.assertFalse(o['available'])
   seasonal=next(o for o in C.AD.World(C.AD.scenario()).engine_world(1080)['offers'] if o['id']=='GEUMRYONG')
   self.assertIsNone(M.attach(seasonal,actor(day='2026-11-02'),1080)['price_pp_krw'])
 def test_buffet_adult_calendar_and_child_unknown(self):
  base={'id':'THE_BUFFET'}
  for day,period,price in [('2026-10-26','lunch',176000),('2026-10-24','lunch',198000),('2026-12-24','dinner',205000)]:
   o=M.buffet(base,actor(day=day),period,1080);self.assertEqual(o['sku_contract']['unit_price_krw'],price)
  self.assertIsNone(M.buffet(base,actor(4,True),'dinner',1080)['price_pp_krw'])
  self.assertNotIn('sku_contract',M.buffet(dict(base,in_package=True),actor(),'breakfast',510))
 def test_user_confirms_portion_unit_without_changing_source_menu(self):
  with C.install('2026-10-24'):
   for code,price,sku in [('C01_ONDAL_SURA',195000,'ONDAL-SURA'),('C01_ONDAL_COURT',165000,'ONDAL-GUNGJUNG')]:
    o=next(o for o in C.AD.World(C.AD.scenario()).engine_world(1080)['offers'] if o['id']==code)
    o=M.attach(o,actor(),1080)
    a=actor();a.vs={};a.visit_history={}
    charge=C.AD.LG.charge(a,code,'restaurant',o['venue'],offer=o)
    self.assertEqual(charge['status'],'유료');self.assertEqual(charge['krw'],price*2)
    self.assertEqual(charge['sku_contract']['sku_id'],sku)
    self.assertEqual(charge['sku_contract']['minimum_order_portions'],2)
    self.assertEqual(charge['sku_contract']['user_confirmation']['authority'],'EXPLICIT_USER_INSTRUCTION')
 def test_all_added_products_have_actual_source_and_gates(self):
  with C.install('2026-10-26'):
   w=C.AD.World(C.AD.scenario(date='2026-10-26')).engine_world(1080)
   offers={o['id']:o for o in w['offers']}
   self.assertTrue(set(M.SPECS)<=set(offers))
   for code,(venue,_,_) in M.SPECS.items():
    o=M.attach(offers[code],actor(4 if code=='C01_MYONG_SPECIAL4' else 2,day='2026-10-26'),1080)
    if code in ('C01_GEUM_JAJANG_L','C01_GEUM_XO_L','C01_MYONG_TANG_KR','C01_MYONG_TANG_US'):
     self.assertFalse(o['available']);self.assertEqual(o['status'],'SKU_SERVICE_PERIOD_NOT_AVAILABLE');continue
    if code=='C01_GEUM_KYUNG':
     self.assertFalse(o['available']);self.assertEqual(o['status'],'ADVANCE_RESERVATION_NOT_CONFIRMED');continue
    c=o['sku_contract']
    self.assertEqual(c['venue_id'],venue)
    if code in M.BILLING_PENDING:
     self.assertIsNone(c['billing_quantity']);self.assertIsNone(o['price_pp_krw'])
    else:self.assertEqual(c['billing_quantity'],1 if c['billing_unit']=='set' else 2)
    self.assertEqual(c['source_path'],'timeline/menu.csv');self.assertFalse(c['current_sale_confirmed'])
 @pytest.mark.requires_private_personas('A08')
 def test_controlled_set_ledger_seam_does_not_multiply_team_price(self):
  q=dict(personas=['A08'],duration='stay_2',event_mode='none',seed=0,start_date='2026-10-24',behavior_engine='m4_c01')
  f=visit_run.run_visit(q);self.assertNotIn('error',f)
  f['visit_id']='CONTROLLED_SET_BILLING_ONLY:'+f['visit_id']
  scene=next(s for s in f['visit_days'][0]['flow']['plans']['A08']['scenes'] if s.get('meal'))
  contract=M.planner_contract('lunch_pizzahill',actor(3));scene.update(loc='PIZZA_HILL',act='SET_BILLING_TEST',turn=None)
  scene['basis']['charge']=M.bill(contract,actor(3))
  l=LS.register_visit(f,q,source='CONTROLLED_SET_BILLING_NOT_BEHAVIOR_CHOICE')
  r=next(r for r in l['receipts']['A08']['rows'] if r['act']=='SET_BILLING_TEST')
  self.assertEqual((r['quantity'],r['unit_price_krw'],r['paid_krw']),(1,251000,251000))
  self.assertTrue(l['checks']['receipts_equal_L4_L3_L2_L1'])

if __name__=='__main__':unittest.main()
