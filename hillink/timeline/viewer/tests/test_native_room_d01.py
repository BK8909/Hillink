import copy, importlib.util, sys, unittest
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import room_revenue as R, visit_run as VR, ledger_service as LS

class NativePricingTests(unittest.TestCase):
 def flow(self,building='GRAND',party=2,package=None):
  return dict(visit_id='test-visit',visit=dict(package_context=package),visits={'p':dict(building=building,party_size=party,breakfast_plan='room_only')})
 def test_2026_rates_rooms_not_people(self):
  for building,amount in [('GRAND',247000),('VISTA',307000),('DOUGLAS',259000)]:
   for party in (1,2,4):
    for nights in (1,2,3):
     prices=[R.native_price(self.flow(building,party),'p',f'2026-10-{24+i}',i,nights) for i in range(nights)]
     self.assertEqual(sum(p['virtual_gross_krw'] for p in prices),amount*nights)
     self.assertTrue(all(p['room_count']==1 and p['price_status']=='VIRTUAL_MODEL_UNIT_PRICE' for p in prices))
 def test_priority_allocation_and_expiry(self):
  package=dict(id='p',label='test',building='GRAND',nights=2,party_size=2,effective_from='2026-10-01',effective_to='2026-10-31',price_status='VERIFIED_TOTAL',verified_total_krw=600001,price_source='trusted catalog',tax_status='UNKNOWN')
  f=self.flow(package=package)
  values=[R.native_price(f,'p',f'2026-10-{24+i}',i,2) for i in range(2)]
  self.assertEqual([p['virtual_gross_krw'] for p in values],[300001,300000]);self.assertTrue(all(p['net_ex_vat_krw'] is None for p in values))
  # v4: an expired package no longer prices the night; the ordinary virtual room model rate applies instead (never 0, never the package total)
  expired=R.native_price(f,'p','2026-11-01',0,2);self.assertEqual((expired['virtual_gross_krw'],expired['price_status']),(247000,'VIRTUAL_MODEL_UNIT_PRICE'))
  package.update(price_status='VERIFIED_ROOM_NIGHTLY',verified_room_nightly_krw=270000)
  self.assertEqual(R.native_price(f,'p','2026-10-24',0,2)['virtual_gross_krw'],270000)
  package.update(price_status='UNCONFIRMED')
  self.assertEqual(R.native_price(f,'p','2026-10-24',0,2)['virtual_gross_krw'],247000)
 def test_unknown_is_not_free(self):
  price=R.native_price(self.flow('UNKNOWN'),'p','2026-10-24',0,1);self.assertIsNone(price['virtual_gross_krw']);self.assertEqual(price['price_status'],'UNKNOWN_ROOM_PRICE')
  # v4: other years use the virtual model rate, labelled as a model rate rather than that date's sale price
  other=R.native_price(self.flow(),'p','2027-01-01',0,1);self.assertEqual(other['virtual_gross_krw'],247000);self.assertTrue(other['model_rate_outside_model_year'])

@unittest.skipUnless('A08' in VR.AD.load_inputs()[0],'approved execution input absent')
class NativeIntegrationTests(unittest.TestCase):
 def test_live_durations_and_inverse_ledger(self):
  for nights in range(4):
   q=dict(personas=['A08'],duration='day_visit' if not nights else f'stay_{nights}',event_mode='none',seed=0,start_date='2026-10-24')
   f=VR.run_visit(q);before=copy.deepcopy(f);l=LS.register_visit(f,q);self.assertEqual(f,before)
   rows=l['receipts']['A08']['rows'];rooms=[r for r in rows if r['act']=='room_night']
   self.assertEqual(l['virtual_revenue']['levels']['L1']['virtual_gross_krw'],l['totals']['paid_krw'])
   self.assertEqual(len(rooms),nights);self.assertEqual(sum(r['paid_krw'] for r in rooms),259000*nights)
   self.assertEqual(len({(r['stay_id'],r['room_id'],r['visit_date']) for r in rooms}),nights)
   for level in ('L4','L3','L2','L1'):self.assertEqual(sum(g['paid_krw'] for g in l['levels'][level]),sum(r['paid_krw'] for r in rows))
   for level in ('L4','L3','L2','L1'):
    self.assertEqual(sum(Decimal(str(g['known_net_revenue_krw'])) for g in l['levels'][level]),Decimal(str(l['totals']['known_net_revenue_krw'])))
   self.assertEqual(LS.lookup(l['run_id'])['totals'],l['totals'])
   for r in rooms:
    self.assertEqual(r['run_id'],l['run_id']);self.assertEqual(r['room_count'],1);self.assertEqual(r['purchase_status'],'SIMULATED_CHARGE')
   self.assertIsNone(l['totals']['net_revenue_krw']) # nonroom tax remains unverified
