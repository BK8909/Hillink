import pytest
"""Changed age/order paths only; no provider or shared HTTP server."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as V
from operator_choice.autonomy_v1 import candidate_services as C,menu_connections as M,party_orders as P

class ExplicitPartyOrders(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.inputs=C.AD.load_inputs()
 def actor(self,composition=None,orders=None,n=4,day='2026-10-24'):
  a=C.AD.Agent('A01',*self.inputs,C.AD.scenario(date=day));a.N=n;a.vs=copy.deepcopy(a.vs);a.C=dict(a.C,kids=True)
  if composition is not None:a.vs['party_composition']=composition
  a.vs['orders']=orders or [];return a
 def p(self,stage='preschool',age=60):return dict(adult_count=2,children=[dict(age_months=age,school_stage=stage)]*2)
 @pytest.mark.requires_private_personas('A01')
 def test_counts_and_unknown_ages_are_not_inferred(self):
  with self.assertRaisesRegex(ValueError,'COUNTS'):P.validate({'party_composition':self.p()},3)
  with self.assertRaises(ValueError):P.validate({'party_composition':dict(adult_count=True,children=[])},1)
  p=self.p(age=None);P.validate({'party_composition':p},4)
  a=self.actor(p);o=M.buffet({},a,'dinner',1050)
  # 11/03: unknown ages are priced with the same labelled adult-rate proxy as the catalog order (score = order = L5); no age is inferred.
  parts=o['sku_contract']['components'];self.assertTrue(any('연령 미확정' in x['label'] and x['party_cohort']=='UNKNOWN_CHILD_FARE' for x in parts))
  self.assertFalse(any(x.get('age_inputs') and any(c.get('age_months') for c in x['age_inputs']) for x in parts))
 @pytest.mark.requires_private_personas('A01')
 def test_no_input_retains_unknown(self):
  a=self.actor();self.assertIsNone(M.buffet({},a,'dinner',1050)['price_pp_krw'])
  self.assertIsNone(M.attach({'id':'MYONGWOLGWAN','venue':'MYONGWOLGWAN'},a,1050)['price_pp_krw'])
 @pytest.mark.requires_private_personas('A01')
 def test_buffet_age_calendar_and_inclusion(self):
  # Source 2026 Oct: weekday adult176/child88; weekend adult198/child98.
  for day,period,total in [('2026-10-24','breakfast',256000),('2026-10-26','lunch',528000),('2026-10-24','lunch',592000),('2026-10-24','dinner',592000)]:
   a=self.actor(self.p(),day=day);c=M.buffet({},a,period,750)['sku_contract']
   self.assertEqual(M.bill(c,a)['krw'],total)
   self.assertEqual(sum(x['billing_quantity'] for x in c['components']),4)
  a=self.actor(self.p());self.assertEqual(M.buffet({'in_package':True},a,'breakfast',450),{'in_package':True})
  # 11/03: same cohort rules as the catalog order — under 36 months free, secondary school pays the adult tariff.
  infant=M.buffet({},self.actor(self.p(age=24)),'dinner',1050)['sku_contract'];self.assertEqual(sum(x['billing_quantity'] for x in infant['components']),2)
  sec=M.buffet({},self.actor(self.p(stage='secondary',age=156)),'dinner',1050)['sku_contract'];self.assertTrue(any(x.get('party_cohort')=='ADULT_TARIFF_SECONDARY' for x in sec['components']))
 @pytest.mark.requires_private_personas('A01')
 def test_child_menus_match_actual_eligibility_not_generic_kids(self):
  for venue,name,child_price in [('GEUMRYONG','삼선 자장면 · 저녁',68000),('ONDAL','수라상차림',40000),('MOEGI','마코토 코스',70000)]:
   ko={'GEUMRYONG':'금룡','ONDAL':'온달','MOEGI':'모에기'}[venue];i,r=M.find(ko,name)
   a=self.actor(self.p());c=P.mixed_person_contract(M.contract(i,r,venue,'dinner',4),a)
   self.assertEqual(c['components'][-1]['unit_price_krw'],child_price)
   self.assertEqual(M.bill(c,a)['krw'],2*int(r['단가'])+2*child_price)
   elementary=self.actor(self.p(stage='elementary',age=96))
   x=P.mixed_person_contract(M.contract(i,r,venue,'dinner',4),elementary)
   self.assertEqual(x is not None,venue=='MOEGI')
 @pytest.mark.requires_private_personas('A01')
 def test_explicit_portions_not_people_and_cups_not_party(self):
  for venue,line,quantity,total in [('MYONGWOLGWAN',159,2,156000),('THE_PAVILION',204,2,38000)]:
   o=dict(date='2026-10-24',venue_id=venue,service_period='dinner' if line==159 else 'snack',items=[dict(source_line=line,quantity=quantity)])
   P.validate({'orders':[o]},1)
   a=self.actor(orders=[o],n=1);c=P.explicit_order(a,venue,o['service_period'],1080 if line==159 else 600)
   self.assertEqual(M.bill(c,a)['krw'],total);self.assertEqual(c['components'][0]['billing_quantity'],2)
   self.assertFalse(c['quantity_observed'])
 def test_wrong_menu_time_addon_and_minimum_fail_closed(self):
  for venue,line,period,q in [('MYONGWOLGWAN',158,'dinner',2),('THE_PAVILION',200,'snack',1),('THE_PAVILION',204,'lunch',1),('ONDAL',147,'dinner',1)]:
   o=dict(date='2026-10-24',venue_id=venue,service_period=period,items=[dict(source_line=line,quantity=q)])
   with self.assertRaises(ValueError):P.validate({'orders':[o]},1)
 @pytest.mark.requires_private_personas('A01')
 def test_explicit_buffet_diner_quantities_are_separate_from_total_party(self):
  o=dict(date='2026-10-24',venue_id='THE_BUFFET',service_period='dinner',items=[dict(source_line=106,quantity=1),dict(source_line=108,quantity=1)])
  p=self.p();P.validate(dict(party_composition=p,orders=[o]),4)
  a=self.actor(p,orders=[o]);c=M.buffet({},a,'dinner',1050)['sku_contract']
  self.assertEqual(M.bill(c,a)['krw'],296000)
  o['items'][1]['quantity']=3
  with self.assertRaisesRegex(ValueError,'DINER'):P.validate(dict(party_composition=p,orders=[o]),4)
 @pytest.mark.requires_private_personas('A01')
 def test_native_resolution_forwards_without_editing_profile(self):
  original=copy.deepcopy(self.inputs[0]['A01']);x=V._resolve_visit('A01','stay_2',0,self.inputs,conditions={'party_size':4,'party_composition':self.p()},behavior_engine='m4_c01')
  self.assertEqual(x['party_composition'],self.p());self.assertEqual(original,self.inputs[0]['A01'])
  with C.install('2026-10-24'):
   a=C.AD.Agent('A01',*self.inputs,C.AD.scenario(date='2026-10-24',visit_resolution={'A01':x}))
   self.assertEqual(P.party(a),self.p());self.assertTrue(a.C['kids'])
 @pytest.mark.requires_private_personas('A01')
 def test_real_runtime_mixed_party_candidates_and_explicit_order_before_open(self):
  for pid,n,p in [('A01',4,self.p()),('A04',1,dict(adult_count=1,children=[]))]:
   order=dict(date='2026-10-24',venue_id='MYONGWOLGWAN',service_period='dinner',items=[dict(source_line=159,quantity=2)])
   x=V._resolve_visit(pid,'stay_2',0,self.inputs,conditions={'party_size':n,'party_composition':p,'orders':[order] if pid=='A04' else []},behavior_engine='m4_c01')
   day='2026-10-25' if pid=='A01' else '2026-10-24'
   with C.install(day):
    a=C.AD.Agent(pid,*self.inputs,C.AD.scenario(date=day,visit_resolution={pid:x}))
    a.loc='VISTA_ROOM';a.t=1030;a.checked_in=True
    world=C.AD.World(a.sc);w=C.AD.engine_world_for(a,world,1030);by={o['id']:o for o in w['offers']}
    if pid=='A01':
     for key in ['THE_BUFFET','C01_GEUM_JAJANG_D','C01_ONDAL_SURA','MOEGI']:
      self.assertTrue(by[key]['available'],(key,by[key].get('status')))
      c=by[key]['sku_contract'];self.assertEqual(sum(x['billing_quantity'] for x in c['components']),4)
    else:
     c=by['MYONGWOLGWAN']['sku_contract'];self.assertEqual(M.bill(c,a)['krw'],156000)
 @pytest.mark.requires_private_personas('A01')
 def test_actual_charge_to_l5_keeps_composed_quantity(self):
  import flow_run as F,ledger_l5 as L5
  a=self.actor(self.p());a.checked_in=True
  o=M.buffet(dict(id='THE_BUFFET',venue='THE_BUFFET',duration_min=90),a,'dinner',1050)
  with C.install('2026-10-24'):
   a.add('restaurant','test_explicit_buffet',o['label'],'THE_BUFFET',1050,90,'식사','explicit_virtual_order','diagnostic',[],offer=o,fraction=1)
  raw={'log':a.log};plan=F.plan_of('A01',raw,{},set());flow={'plans':{'A01':plan},'visits':{'A01':dict(a.vs,party_size=4)},'runs':[]}
  rows,_,_,_,_=L5.day_rows('A01',False,flow,'isolated quantity diagnostic',1,dict(types={},no={}))
  self.assertEqual(rows[0]['결제액'],592000);self.assertEqual(rows[0]['수량'],1)
  self.assertEqual(rows[0]['판매 단위'],'건');self.assertEqual(rows[0]['확인 메모'],'')
  self.assertEqual(rows[0]['선택 SKU 계약']['components'][1]['billing_quantity'],2)
 @pytest.mark.requires_private_personas('A01')
 def test_fixed_set_stays_one_and_default_rejects_new_fields(self):
  a=self.actor(self.p());c=M.attach({'id':'PIZZA_HILL','venue':'PIZZA_HILL','food':{}},a,1080)['sku_contract']
  self.assertEqual(c['billing_quantity'],1);self.assertEqual(c['billing_unit'],'set')
  a=self.actor();o=dict(id='C01_MYONG_SPECIAL4',venue='MYONGWOLGWAN',window=dict(start='17:30',end='21:00'),duration_min=90)
  c=M.attach(o,a,1080)['sku_contract'];self.assertEqual(c['billing_quantity'],1);self.assertEqual(M.bill(c,a)['krw'],770000)
  with self.assertRaises(ValueError):V._resolve_visit('A01','stay_2',0,self.inputs,conditions={'party_composition':self.p()})
if __name__=='__main__':unittest.main()
