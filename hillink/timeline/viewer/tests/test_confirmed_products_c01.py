import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as V,ledger_service as LS
from operator_choice.autonomy_v1 import candidate_services as C,menu_connections as M,lunch_products as L

class ConfirmedProducts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.inputs=C.AD.load_inputs()
 def actor(self,day,n=4):
  a=C.AD.Agent('A04',*self.inputs,C.AD.scenario(date=day));a.N=n;a.loc='GRAND_LOBBY';a.C=copy.deepcopy(a.C);a.C['kids']=False
  return a
 def test_platter_all_days_but_only_matching_set_and_service(self):
  for day in ('2026-10-24','2026-10-25','2026-10-26','2026-10-03'):
   for n in (1,2,4):
    a=self.actor(day,n)
    with C.install(day):
     w=C.AD.World(a.sc).engine_world(1080);o=next(o for o in w['offers'] if o['id']=='C01_MYONG_SPECIAL4')
     selected=M.attach(o,a,1080)
     self.assertEqual('sku_contract' in selected,n==4)
     if n==4:
      c=selected['sku_contract'];self.assertEqual(M.bill(c,a)['krw'],770000);self.assertEqual(c['billing_quantity'],1)
      self.assertEqual(c['menu_day_rule'],'ALL_DAYS_WITHIN_VENUE_SERVICE_WINDOW')
     allowed,_=L.options(a,'lunch_myongwol',750,{o['id']:o for o in w['offers']},C.service_check,70,0)
     self.assertEqual('C01_MYONG_SPECIAL4' in {o['id'] for o in allowed},n==4)
   self.assertFalse(C.service_check('MYONGWOLGWAN',day,1290,90)['eligible'])
 def test_ondal_minimum_portions_does_not_close_single_guest_venue(self):
  for n in (1,2,3):
   a=self.actor('2026-10-24',n)
   with C.install(a.sc['date']):
    w=C.AD.World(a.sc).engine_world(1080)
    for code,price in [('C01_ONDAL_SURA',195000),('C01_ONDAL_COURT',165000)]:
     o=M.attach(next(o for o in w['offers'] if o['id']==code),a,1080)
     self.assertEqual('sku_contract' in o,n>=2)
     if n>=2:self.assertEqual(C.AD.LG.charge(a,code,'restaurant','ONDAL',offer=o)['krw'],price*n)
 def test_bill_rejects_less_than_two_confirmed_portions(self):
  line,row=M.find('온달','수라상차림')
  c=M.contract(line,row,'ONDAL','dinner',1)
  with self.assertRaisesRegex(ValueError,'MINIMUM_ORDER_PORTIONS'):M.bill(c,self.actor('2026-10-24',1))
 def test_same_ledger_uses_set_once_and_person_portions(self):
  q=dict(personas=['A04'],duration='stay_2',event_mode='none',seed=0,start_date='2026-10-24',behavior_engine='m4_c01',visit_conditions={'A04':{'party_size':4,'building':'GRAND'}})
  f=V.run_visit(q);self.assertNotIn('error',f);f['visit_id']='CONTROLLED_USER_CONTRACT:'+f['visit_id']
  scenes=[s for day in f['visit_days'] for s in day['flow']['plans']['A04']['scenes'] if s.get('meal') in ('lunch','dinner')]
  # Billing seam only; not a claim the behavior engine naturally chose these.
  for scene,(venue,name,code,unit,qty) in zip(scenes,[('MYONGWOLGWAN','명월관 모둠 한상','C01_MYONG_SPECIAL4','set',1),('ONDAL','수라상차림','C01_ONDAL_SURA','person_meal',4)]):
   ko='명월관' if venue=='MYONGWOLGWAN' else '온달';line,row=M.find(ko,name)
   c=M.contract(line,row,venue,'dinner',qty,unit)
   scene.update(loc=venue,act='CONTROLLED_'+code,turn=None);scene['basis']['charge']=M.bill(c,self.actor('2026-10-24',4))
  ledger=LS.register_visit(f,q,source='CONTROLLED_CONTRACT_BILLING_NOT_BEHAVIOR_PROOF')
  rows=[r for r in ledger['receipts']['A04']['rows'] if r['act'].startswith('CONTROLLED_')]
  self.assertEqual(len(rows),2)
  self.assertEqual([(r['quantity'],r['paid_krw']) for r in rows],[(1,770000),(4,780000)])
  self.assertTrue(ledger['checks']['receipts_equal_L4_L3_L2_L1'])
  self.assertTrue(all(r['sku_contract']['user_confirmation']['authority']=='EXPLICIT_USER_INSTRUCTION' for r in rows))

if __name__=='__main__':unittest.main()
