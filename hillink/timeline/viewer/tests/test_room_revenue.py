import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import room_revenue as R
class RoomRevenueTests(unittest.TestCase):
 def data(self,n=2,package=None):
  rows=[dict(row_id=str(i),visit_date='2026-10-24',department='ROOM',venue='더글라스',product='old',act='room_night',quantity=1,status='금액 미확인',paid_krw=0,visit_day=i+1) for i in range(n)]
  return {'visit_id':'v','visit':{'package_context':package},'visits':{'A08':{'building':'DOUGLAS','party_size':4}}},{'run_id':'l','receipts':{'A08':{'rows':rows}},'totals':{'assumption_addition_krw':774000}}
 def test_nights_and_not_people(self):
  for n in range(4):
   f,l=self.data(n);v=R.build(f,l);self.assertEqual(v['room']['virtual_gross_krw'],259000*n);self.assertEqual(len(v['rows']),n)
 def test_verified_total_once_and_unknown_fallback(self):
  for package,expected in [({'id':'p'},518000),({'id':'p','label':'package','verified_total_krw':600001,'price_status':'VERIFIED_TOTAL','price_source':'trusted catalog'},600001)]:
   f,l=self.data(package=package);v=R.build(f,l);self.assertEqual(v['levels']['L1']['virtual_gross_krw'],expected)
 def test_input_untouched_and_tax_unknown(self):
  f,l=self.data();before=copy.deepcopy(l);v=R.build(f,l);self.assertEqual(l,before);self.assertAlmostEqual(v['room']['net_ex_vat_krw'],470909.1)
  l['receipts']['A08']['rows'].append(dict(l['receipts']['A08']['rows'][0],row_id='food',act='meal',status='실결제',paid_krw=100))
  v=R.build(f,l);self.assertIsNone(v['levels']['L1']['net_ex_vat_krw']);self.assertEqual(v['nonroom']['virtual_gross_krw'],100)
