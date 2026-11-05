import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import consumption_audit as A
class ConsumptionAuditTests(unittest.TestCase):
 def sample(self):
  row=dict(row_id='tx',customer_id='P',visit_day=2,time='12:00',act='lunch_cafe',product_id='sku',quantity=2,unit_price_krw=100,paid_krw=200)
  scene=dict(visit_day=2,t0=720,act='lunch_cafe',loc='THE_PAVILION',basis={'charge':{'status':'유료','krw':200,'sku_contract':{'sku_id':'sku'}}})
  return dict(plans={'P':{'scenes':[scene]}},ledger=dict(run_id='run',receipts={'P':{'rows':[row]}},totals={'paid_krw':200},levels={l:[{'paid_krw':200}] for l in ('L4','L3','L2','L1')}))
 def test_empty_input_is_not_pass(self):
  self.assertEqual(A.inspect({})["status"],"FAIL")
 def test_valid_input_is_not_modified(self):
  f=self.sample();before=copy.deepcopy(f);self.assertEqual(A.inspect(f)['status'],'PASS');self.assertEqual(f,before)
 def test_missing_order_is_not_free(self):
  f=self.sample();f['plans']['P']['scenes'][0]['basis']['charge']={'status':'구매 없음','krw':0};f['ledger']['receipts']['P']['rows']=[]
  self.assertIn('PAID_ACTION_WITHOUT_ORDER',A.inspect(f)['issue_counts'])
 def test_unit_total_sku_and_hotel_mismatch_are_reported(self):
  for field,value,code in [('product_id','other','FINAL_SKU_L5_MISMATCH'),('unit_price_krw',1,'L5_UNIT_TOTAL_MISMATCH'),('paid_krw',0,'ORDER_L5_AMOUNT_MISMATCH')]:
   f=self.sample();f['ledger']['receipts']['P']['rows'][0][field]=value;self.assertIn(code,A.inspect(f)['issue_counts'])
 def test_native_bundled_sku_does_not_require_catalog_component_expansion(self):
  f=self.sample();f['plans']['P']['scenes'][0]['basis']['charge']['sku_contract']['components']=[{'sku_id':'sub-a'},{'sku_id':'sub-b'}]
  self.assertEqual(A.inspect(f)['status'],'PASS')
 def test_unknown_and_paid_zero_are_detected(self):
  f=self.sample();f['plans']['P']['scenes'][0]['basis']['charge']={'status':'유료','krw':0};self.assertIn('PAID_ORDER_ZERO',A.inspect(f)['issue_counts'])
  f['ledger']['receipts']['P']['rows'][0]['amount_status']='UNKNOWN';self.assertIn('L5_PRICE_UNRESOLVED',A.inspect(f)['issue_counts'])
 def test_included_never_charged(self):
  f=self.sample();f['plans']['P']['scenes'][0]['basis']['charge']={'status':'포함','krw':0};self.assertIn('INCLUDED_OR_FREE_CHARGED',A.inspect(f)['issue_counts'])
 def test_duplicate_transactions_reported(self):
  f=self.sample();f['ledger']['receipts']['P']['rows']*=2;self.assertIn('DUPLICATE_TRANSACTION_ID',A.inspect(f)['issue_counts'])
 def test_same_meal_duplicate_component_detected_but_different_dates_allowed(self):
  f=self.sample();f['visits']={'P':{'party_size':2}};r=f['ledger']['receipts']['P']['rows'][0];r.update(product_sku_id='adult',parent_order_id='o',sku_contract={'venue_id':'THE_BUFFET'},act='turn_dinner',visit_date='2026-07-17')
  r2=copy.deepcopy(r);r2['row_id']='tx2';f['ledger']['receipts']['P']['rows'].append(r2)
  a=A.inspect(f);self.assertIn('DUPLICATE_MEAL_COMPONENT',a['issue_counts']);self.assertIn('BUFFET_ADMISSIONS_EXCEED_PARTY',a['issue_counts'])
  r2['visit_date']='2026-07-18';self.assertNotIn('DUPLICATE_MEAL_COMPONENT',A.inspect(f)['issue_counts'])
 def test_included_component_cannot_be_charged(self):
  f=self.sample();f['ledger']['receipts']['P']['rows'][0]['sku_contract']={'included_benefit':'PACKAGE_PIZZA'}
  self.assertIn('PACKAGE_BENEFIT_DOUBLE_CHARGED',A.inspect(f)['issue_counts'])
if __name__=='__main__':unittest.main()
