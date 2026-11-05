import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1 import hotel_runtime as H
from operator_choice.operator_world_v1_1.turn_view import _empty_traits
E=H.EN
class PersonalizationContract(unittest.TestCase):
 def actor(self):return SimpleNamespace(N=2,room='GRAND',B='GRAND')
 def contract(self,discount=0):
  p=copy.deepcopy(H.H.BY['HC-MENU-134']);p.update(billing_quantity=2,unit_price_krw=100000)
  return dict(sku_id='TEST',venue_id=p['venue_id'],components=[p],service_period='dinner',unit_price_krw=200000-discount,discount_krw=discount,label=p['label'],price_status='TEST')
 def offer(self,c):return H.offer(self.actor(),c,1080,90,H.AD.WD.default_world())
 def traits(self,facet,tags):
  x=_empty_traits();x['facets'][facet]['evidence']=[dict(fact_id='TEST-F1',tags=tags,grade='rep',mass=1,gist='synthetic contract fixture')];return x
 def score(self,o,tr):return E.score(o,1080,dict(used=set(),hunger=1),dict(checkin='15:00',rest_goal=.5),tr,H.AD.WD.default_world())
 def test_course_menu_not_minimum_diners_and_known_course_evidence(self):
  c=self.contract();o=self.offer(c);self.assertTrue(o['food']['course_menu']);self.assertFalse(o['food']['course_count_known'])
  tr=self.traits('food',['course']);terms=self.score(o,tr)
  self.assertIn('TEST-F1',next(t for t in terms if t['factor']=='음식 경험')['fact_ids'])
  c['components'][0].update(label='2인 세트',tags=['pizza'],minimum_quantity=2)
  q=self.offer(c);self.assertFalse(q['food']['course_menu']);self.assertEqual(q['food']['courses'],1)
  self.assertNotIn('TEST-F1',next(t for t in self.score(q,tr) if t['factor']=='음식 경험')['fact_ids'])
 def test_composed_menu_preserves_all_tags_and_quote(self):
  c=self.contract();c['components'].append(dict(c['components'][0],label='추가 음료',role='DRINK',tags=['tea']));before=copy.deepcopy(c)
  o=self.offer(c);self.assertIn('tea',o['food']['menu_tags']);self.assertEqual(c,before)
 def test_discount_preserves_same_net_without_double_charge(self):
  c=self.contract(40000);o=self.offer(c);self.assertEqual(E.out_of_pocket(o),80000)
  self.assertEqual(o['guest_discount_krw'],20000);self.assertEqual(H.H.charge(c)['krw'],160000)
  from operator_choice.operator_world_v1_1.candidate import candidate_engine
  with candidate_engine(c1=True):
   terms=self.score(o,self.traits('benefit',['discount']))
   self.assertTrue(any(t['factor']=='할인 반응(개인 근거)' and t['value']>0 for t in terms))
 def test_included_retains_reference_not_new_payment(self):
  c=self.contract();c['hc_included']=True;o=self.offer(c)
  self.assertEqual(E.out_of_pocket(o),0);self.assertEqual(H.H.charge(c,included=True)['krw'],0)
  self.assertEqual(o['price_pp_krw'],100000)
 def test_revisit_uses_same_venue_across_sku_ids_only_with_source_policy(self):
  from operator_choice.autonomy_v1.m4_context import repeat_adjustment
  o=dict(id='HC_NEW_ORDER',venue='PIZZA_HILL',food=dict(menu_tags=['pizza'],meal_fraction=1))
  ctx=dict(prior_meals=[dict(venue_id='PIZZA_HILL',fraction=1,menu_tags=['pizza'],event_id='previous-meal')])
  terms=[dict(facet='space',value=.6),dict(facet='food_specific',value=.4)]
  policy={'PIZZA_HILL':dict(food_appraisal='MIXED',explicit_repeat_intention=False,source_fact_ids=['TEST-F1'])}
  self.assertEqual(repeat_adjustment(o,terms,ctx,policy)[0],-1)
  self.assertEqual(repeat_adjustment(o,terms,ctx,{})[0],0)
  self.assertEqual(repeat_adjustment(o,terms,dict(ctx,explicit_repeat_reason=True),policy)[0],0)
  other=dict(o,venue='MOEGI');self.assertEqual(repeat_adjustment(other,terms,ctx,policy)[0],0)
 def test_only_committed_food_order_updates_meal_memory(self):
  from operator_choice.autonomy_v1.m4_meal import catalog_intake_slot,meal_state,absolute_minute
  c=self.contract();o=self.offer(c);r=dict(charge=H.H.charge(c))
  self.assertEqual(catalog_intake_slot(o,r),'dinner')
  self.assertIsNone(catalog_intake_slot(o,{}))
  self.assertIsNone(catalog_intake_slot(o,dict(charge=dict(r['charge'],sku_contract=dict(c,sku_id='other')))))
  drinks=copy.deepcopy(o)
  for part in drinks['sku_contract']['components']:part['role']='DRINK'
  self.assertIsNone(catalog_intake_slot(drinks,r))
  event=dict(event_id='actual-meal',date='2026-10-24',meal_slot=catalog_intake_slot(o,r),fraction=1,end_absolute=absolute_minute('2026-10-24',1041))
  state=meal_state([event],'2026-10-24',1041)
  self.assertEqual(state['last_meal_id'],'actual-meal');self.assertEqual(state['current_meal_target_proxy'],0)
 def test_explicit_dinner_main_is_not_hidden_by_cafe_venue(self):
  self.assertIn('THE_PAVILION',H.dinner_venues())
  self.assertNotIn('LUX_BAR',H.dinner_venues())
  self.assertEqual(H.dinner_duration('THE_PAVILION'),H.SP.ACT['lunch_cafe'][3])
  p=H.H.BY['HC-PDF-THE_PAVILION-BURGER'];self.assertIn('dinner',p['service_periods'])
  self.assertEqual(p['unit_price_krw'],44000)
 def test_legacy_offer_course_rule_unchanged(self):
  o=H.AD.WD.offer('X','fixture','restaurant','X',meal_fraction=1,quality='standard',courses=3)
  self.assertIn('TEST-F1',next(t for t in self.score(o,self.traits('food',['course'])) if t['factor']=='음식 경험')['fact_ids'])
if __name__=='__main__':unittest.main()
