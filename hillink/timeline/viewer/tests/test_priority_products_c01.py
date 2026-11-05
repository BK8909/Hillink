import pytest
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as V,ledger_service as LS
from operator_choice.autonomy_v1 import candidate_services as C,menu_connections as M,lunch_products as L

class PriorityProducts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.inputs=C.AD.load_inputs()
 def actor(self,day='2026-10-26',n=2,kids=False):
  a=C.AD.Agent('A08',*self.inputs,C.AD.scenario(date=day));a.N=n;a.C=copy.deepcopy(a.C);a.C['kids']=kids;a.loc='VISTA_LOBBY';a.t=750
  return a
 def options(self,a,code,t):
  w=C.AD.World(a.sc).engine_world(t);templates={o['id']:o for o in w['offers']}
  if code in ('cafe','lunch_cafe'):
   templates['THE_PAVILION']=C.AD.WD.offer('THE_PAVILION','카페 상품','simple_meal','THE_PAVILION',duration=C.SP.ACT[code][3],price=None,meal_fraction=0 if code=='cafe' else .5,quality='none' if code=='cafe' else 'standard')
  return L.options(a,code,t,templates,C.service_check,C.SP.ACT[code][3],0)
 @pytest.mark.requires_private_personas('A08')
 def test_lunch_only_and_dinner_day_rules(self):
  for day,yes in [('2026-10-24',False),('2026-10-25',True),('2026-10-26',True),('2026-10-03',False)]:
   a=self.actor(day)
   with C.install(day):
    w=C.AD.World(a.sc).engine_world(1080);by={o['id']:o for o in w['offers']}
    for key in ('C01_GEUM_JAJANG_L','C01_GEUM_XO_L','C01_MYONG_TANG_KR','C01_MYONG_TANG_US'):
     self.assertFalse(M.attach(by[key],a,1080)['available'])
    for key in ('C01_GEUM_JAJANG_D','C01_GEUM_XO_D'):
     self.assertEqual('sku_contract' in M.attach(by[key],a,1080),yes)
 @pytest.mark.requires_private_personas('A08')
 def test_one_main_portion_allocation_does_not_apply_to_shared_pizza(self):
  for n in (1,2,4):
   a=self.actor(n=n)
   with C.install(a.sc['date']):
    for code,sku,unit in [('lunch_geumryong','C01_GEUM_JAJANG_L',29000),('lunch_myongwol','C01_MYONG_TANG_US',39000),('lunch_pizzahill','C01_PIZZA_VONGOLE',49000)]:
     offers,_=self.options(a,code,750);o=next(o for o in offers if o['id']==sku);c=o['sku_contract']
     self.assertEqual(c['billing_unit'],'portion_meal');self.assertEqual(c['billing_quantity'],n)
     self.assertFalse(c['quantity_observed']);self.assertEqual(M.bill(c,a)['krw'],unit*n)
    offers,_=self.options(a,'lunch_pizzahill',750)
    sets=[o['sku_contract'] for o in offers if o['sku_contract']['billing_unit']=='set']
    self.assertEqual(len(sets),0 if n==1 else 1)
    self.assertTrue(all(c['billing_quantity']==1 for c in sets))
 @pytest.mark.requires_private_personas('A08')
 def test_coffee_windows_counts_and_children_not_adult_assumed(self):
  a=self.actor(n=3)
  with C.install(a.sc['date']):
   for t,yes in [(539,False),(540,True),(1200,True),(1201,False),(1220,False),(1290,False)]:
    offers,_=self.options(a,'cafe',t)
    self.assertEqual('C01_PAV_COFFEE_HOT' in {o['id'] for o in offers},yes)
   offers,_=self.options(a,'cafe',600);c=next(o['sku_contract'] for o in offers if o['id']=='C01_PAV_COFFEE_HOT')
   self.assertEqual(c['billing_unit'],'cup');self.assertEqual(M.bill(c,a)['krw'],57000)
   child=self.actor(n=4,kids=True);offers,_=self.options(child,'cafe',600)
   self.assertTrue(all(o.get('c01_lunch_venue_only') for o in offers));self.assertTrue(all(o['price_pp_krw'] is None for o in offers))
   shared,_=self.options(child,'cafe',750)
   self.assertEqual({o['id'] for o in shared},{'C01_PAV_FALL_SET'})
   self.assertEqual(M.bill(shared[0]['sku_contract'],child)['krw'],196000)
 @pytest.mark.requires_private_personas('A08')
 def test_brunch_requires_priced_drink_and_has_no_standalone_28000_choice(self):
  a=self.actor()
  with C.install(a.sc['date']):
   offers,_=self.options(a,'lunch_cafe',750)
   self.assertEqual({o['id'] for o in offers},{'C01_PAV_BRUNCH_HOT','C01_PAV_BRUNCH_ICE'})
   for o in offers:
    c=o['sku_contract'];self.assertEqual(len(c['components']),2);self.assertFalse(c['standalone_main_allowed'])
    self.assertEqual(M.bill(c,a)['krw'],sum(x['unit_price_krw']*x['billing_quantity'] for x in c['components']))
   late,_=self.options(a,'lunch_cafe',810)
   self.assertTrue(all(o.get('c01_lunch_venue_only') for o in late))
 @pytest.mark.requires_private_personas('A08')
 def test_extra_dessert_requires_parent_and_is_not_multiplied_by_party_again(self):
  for n,total in [(2,98000),(3,147000),(4,196000)]:
   a=self.actor(n=n)
   with C.install(a.sc['date']):
    offers,_=self.options(a,'cafe',750)
    c=next(o['sku_contract'] for o in offers if o['id']=='C01_PAV_FALL_SET')
    self.assertEqual(M.bill(c,a)['krw'],total);self.assertEqual(c['billing_quantity'],1)
    if n>2:
     self.assertFalse(c['standalone_addon_allowed']);self.assertEqual(c['components'][1]['billing_quantity'],n-2)
     self.assertEqual(sum(x['unit_price_krw']*x['billing_quantity'] for x in c['components']),total)
    self.assertFalse(any(o['sku_contract'].get('source_line')==200 for o in offers))
 @pytest.mark.requires_private_personas('A08')
 def test_real_plan_do_retains_precharge_menu_decision(self):
  a=self.actor()
  with C.install(a.sc['date']):
   for code in ('cafe','lunch_cafe','lunch_pizzahill'):
    a=self.actor();C.AD.plan_do(a,code,C.SP.ACT[code][1](a.B),750,{}, {})
    row=a.log[-1];r=row['internal']['c01_product_decision'];contract=row['charge']['sku_contract']
    candidate=next(c for c in r['packet']['candidates'] if c['candidate_id']==r['selected_product_id'])
    self.assertEqual(contract['sku_id'],candidate['sku_id']);self.assertEqual(r['selection_phase'],'BEFORE_ACTION_AND_CHARGE')
 def test_product_alias_preserves_existing_review_and_restores_default_scope(self):
  original=C.M4.evidence_policy
  with C.install('2026-10-24'):
   reviews,_=C.M4.evidence_policy({'A08S_E29'})
   self.assertEqual(reviews['PIZZA_HILL'],reviews['C01_PIZZA_VONGOLE'])
   no_reviews,_=C.M4.evidence_policy(set());self.assertEqual(no_reviews,{})
  self.assertIs(C.M4.evidence_policy,original)
 @pytest.mark.requires_private_personas('A08')
 def test_unpriced_venue_container_does_not_compete_with_fitting_products(self):
  for n in (1,2):
   a=self.actor(day='2026-10-25',n=n);a.hunger_e=1
   with C.install(a.sc['date']):
    w=C.AD.engine_world_for(a,C.AD.World(a.sc),1080);by={o['id']:o for o in w['offers']}
    if n==2:
     venue=by['GEUMRYONG'];self.assertFalse(venue['available'])
     self.assertTrue(venue['service_contract']['venue_operating'])
     self.assertIn('C01_GEUM_JAJANG_D',venue['service_contract']['eligible_product_ids'])
    else:
     self.assertTrue(by['MYONGWOLGWAN']['available']);self.assertIsNone(by['MYONGWOLGWAN']['price_pp_krw'])
 @pytest.mark.requires_private_personas('A08')
 def test_solo_saturday_course_order_requires_explicit_quantity_not_unknown_free_meal(self):
  a=self.actor(day='2026-10-24',n=1);a.hunger_e=1
  with C.install(a.sc['date']):
   w=C.AD.engine_world_for(a,C.AD.World(a.sc),1080)
   venue=next(o for o in w['offers'] if o['id']=='GEUMRYONG')
   self.assertFalse(venue['available']);self.assertTrue(venue['service_contract']['venue_operating'])
   self.assertEqual(venue['status'],'COURSE_ONLY_MINIMUM_ORDER_REQUIRES_EXPLICIT_QUANTITY')
 @pytest.mark.requires_private_personas('A08')
 def test_composed_order_l5_total_counts_components_once(self):
  q=dict(personas=['A08'],duration='stay_2',event_mode='none',seed=0,start_date='2026-10-24',behavior_engine='m4_c01')
  f=V.run_visit(q);self.assertNotIn('error',f);f['visit_id']='CONTROLLED_PRIORITY_BILLING:'+f['visit_id']
  scene=next(s for day in f['visit_days'] for s in day['flow']['plans']['A08']['scenes'] if s.get('meal')=='lunch')
  line,row=M.find('파빌리온','더파빌리온 브런치');dl,dr=M.find('파빌리온','아메리카노 HOT')
  c=M.composed_brunch(M.contract(line,row,'THE_PAVILION','lunch',2),dl,dr,2)
  scene.update(loc='THE_PAVILION',act='CONTROLLED_COMPOSED_ORDER',turn=None);scene['basis']['charge']=M.bill(c,self.actor())
  ledger=LS.register_visit(f,q,source='CONTROLLED_BILLING_NOT_NATURAL_CHOICE')
  r=next(r for r in ledger['receipts']['A08']['rows'] if r['act']=='CONTROLLED_COMPOSED_ORDER')
  self.assertEqual(r['paid_krw'],94000);self.assertEqual(r['quantity'],2);self.assertEqual(r['notes'],[])
  self.assertEqual(sum(x['unit_price_krw']*x['billing_quantity'] for x in r['sku_contract']['components']),r['paid_krw'])
  self.assertTrue(ledger['checks']['receipts_equal_L4_L3_L2_L1'])

if __name__=='__main__':unittest.main()
