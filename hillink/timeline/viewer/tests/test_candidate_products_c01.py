import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run,flow_run as F,ledger_service as LS
from operator_choice.autonomy_v1 import candidate_services as C,candidate_products as P

class ProductConnections(unittest.TestCase):
 def test_dated_source_unit_and_menu_agree(self):
  c=P.makoto_contract();self.assertEqual(c['unit_price_krw'],210000)
  self.assertEqual(c['billing_unit'],'person_meal');self.assertEqual(c['service_period'],'dinner')
  self.assertFalse(c['current_sale_confirmed']);self.assertFalse(c['transaction_confirmed'])
 def test_party_eligibility_does_not_make_unknown_free(self):
  with C.install('2026-10-24'):
   offer=next(o for o in C.AD.World({'date':'2026-10-24'}).engine_world(1080)['offers'] if o['id']=='MOEGI')
   for n,kids,priced in [(1,False,False),(2,True,False),(2,False,True),(4,False,True)]:
    a=SimpleNamespace(C={'kids':kids},N=n,vs={},visit_history={});o=P.attach(offer,a)
    ch=C.AD.LG.charge(a,'MOEGI','restaurant','MOEGI',offer=o)
    if priced:
     self.assertEqual(ch['krw'],210000*n);self.assertEqual(ch['sku_contract']['sku_id'],'MOEGI-MAKOTO-DINNER-REFERENCE')
     op=F.option(o,1,'VISTA',True);self.assertEqual(op['price']['price_status'],'DATED_OFFICIAL_MENU_SIMULATION_REFERENCE')
    else:self.assertIsNone(ch['krw']);self.assertEqual(ch['status'],'가격 미정')
 def test_other_existing_dinner_courses_keep_separate_source_and_sku(self):
  with C.install('2026-10-24'):
   offers={o['id']:o for o in C.AD.World({'date':'2026-10-24'}).engine_world(1080)['offers']}
   for code,(name,price,page) in P.VARIANTS.items():
    a=SimpleNamespace(C={'kids':False},N=2,vs={},visit_history={});o=P.attach(offers[code],a)
    self.assertEqual(o['price_pp_krw'],price);self.assertEqual(o['sku_contract']['source_document'],'20260630_moegi.pdf p'+str(page))
    self.assertIn('DINNER',o['sku_contract']['sku_id']);self.assertEqual(o['window']['start'],'18:00')
    self.assertEqual(C.AD.LG.charge(a,code,'restaurant','MOEGI',offer=o)['krw'],price*2)
    self.assertFalse(P.attach(offers[code],SimpleNamespace(C={'kids':False},N=1))['available'])
    self.assertFalse(P.attach(offers[code],SimpleNamespace(C={'kids':True},N=4))['available'])
 def test_selected_sku_metadata_roundtrip_in_controlled_ledger_fixture(self):
  # Billing seam only. This explicitly does not claim a natural engine choice.
  if 'A08' not in C.AD.load_inputs()[0]:self.skipTest('private input unavailable')
  q=dict(personas=['A08'],duration='stay_2',event_mode='none',seed=0,start_date='2026-10-24',behavior_engine='m4_c01')
  flow=visit_run.run_visit(q);self.assertNotIn('error',flow)
  flow['visit_id']='CONTROLLED_SKU_BILLING_FIXTURE:'+flow['visit_id']
  scenes=flow['visit_days'][0]['flow']['plans']['A08']['scenes']
  scene=next(s for s in scenes if s.get('meal') and s['act']!='room_night')
  with C.install('2026-10-24'):
   offer=next(o for o in C.AD.World({'date':'2026-10-24'}).engine_world(1080)['offers'] if o['id']=='MOEGI')
   actor=SimpleNamespace(C={'kids':False},N=2,vs={},visit_history={});o=P.attach(offer,actor)
   charge=C.AD.LG.charge(actor,'MOEGI','restaurant','MOEGI',offer=o)
  scene.update(loc='MOEGI',label='Controlled SKU billing fixture',act='CONTROLLED_SKU_TEST',turn=None)
  scene['basis']['charge']=charge
  ledger=LS.register_visit(flow,q,source='CONTROLLED_BILLING_FIXTURE_NOT_ENGINE_CHOICE')
  row=next(r for r in ledger['receipts']['A08']['rows'] if r['act']=='CONTROLLED_SKU_TEST')
  self.assertEqual(row['product_sku_id'],'MOEGI-MAKOTO-DINNER-REFERENCE')
  self.assertEqual((row['quantity'],row['unit_price_krw'],row['paid_krw']),(2,210000,420000))
  self.assertFalse(row['current_sale_confirmed']);self.assertFalse(row['reservation_confirmed'])
  self.assertTrue(ledger['checks']['receipts_equal_L4_L3_L2_L1'])
 def test_last_order_blocks_product_not_lunch_price_substitution(self):
  inputs=C.AD.load_inputs()
  if 'A08' not in inputs[0]:self.skipTest('private input unavailable')
  sc=C.AD.scenario();a=C.AD.Agent('A08',*inputs,sc);a.N=2;a.C['kids']=False;a.loc='MOEGI';a.food=[]
  with C.install(sc['date']):
   for t,allowed in [(1170,True),(1171,False)]:
    o=next(o for o in C.AD.engine_world_for(a,C.AD.World(sc),t)['offers'] if o['id']=='MOEGI')
    self.assertEqual(o['available'],allowed)
    self.assertEqual(o['price_pp_krw'],210000)
    if not allowed:self.assertIn('LAST_ORDER',o['status'])

if __name__=='__main__':unittest.main()
