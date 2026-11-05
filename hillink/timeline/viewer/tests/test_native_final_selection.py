"""Boundary contracts. Synthetic responses here are never quality evidence."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import flow_run
from operator_choice.autonomy_v1 import native_hybrid as N,final_selection as F,review_identity as RI

class FinalSelectionTests(unittest.TestCase):
 def actor(self):
  return SimpleNamespace(pid='P',t=100,stay=True,sc={'date':'2026-10-24','seed':17},traits={'evidence_index':{'KNOWN':{}}})
 def offers(self):
  return {k:dict(id=k,label=k,available=True,sku_contract=dict(sku_id=k,unit_price_krw=100,billing_quantity=2)) for k in ('A','B')}
 def entry(self,**kw):
  return dict(rule_choice='A',final='B',time='01:40',date='2026-10-24',outcome='DISAGREE_LLM_ADOPTED',
   call={'fixture':True,'network_attempted':False},llm=dict(verdict='disagree',choice='B',confidence=.8,reasons=[dict(type='상황',text='Synthetic test only',fact_ids=[])]),**kw)
 def test_lock_binds_product_quote_quantity_and_context(self):
  a=self.actor();offers=self.offers();e=F.prepare(a,self.entry(),offers,rule_choice='A',phase='engine',minute=100)
  self.assertEqual(e['review_execution'],'SYNTHETIC_TEST');self.assertFalse(e['review_succeeded'])
  F.verify(a,offers['B'],'B')
  with self.assertRaisesRegex(ValueError,'ALREADY_PENDING'):F.prepare(a,self.entry(),offers,rule_choice='A',phase='engine',minute=100)
  with self.assertRaisesRegex(ValueError,'REPLACED'):F.verify(a,dict(offers['B'],id='A'),'B')
  with self.assertRaisesRegex(ValueError,'REPLACED'):F.verify(a,offers['A'],'A')
  changed=copy.deepcopy(offers['B']);changed['sku_contract']['billing_quantity']=3
  with self.assertRaisesRegex(ValueError,'ORDER_CHANGED'):F.verify(a,changed,'B')
  a.t+=1
  with self.assertRaisesRegex(ValueError,'CONTEXT_CHANGED'):F.pending(a)
 def test_committed_room_rest_skips_planner_and_order_redraw(self):
  from operator_choice.autonomy_v1 import candidate_services as C
  a=self.actor();o=self.offers();o['ROOM_REST']=dict(o['B'],id='ROOM_REST');e=self.entry();e['final']='ROOM_REST'
  F.prepare(a,e,o,rule_choice='A',phase='engine',minute=100)
  with patch.dict(os.environ,{'HILLINK_NATIVE_HYBRID':'1'}),patch.object(C.AD,'plan_choose',side_effect=AssertionError('Planner redraw')),patch.object(C.HR,'choose',side_effect=AssertionError('SKU redraw')),patch.object(C.HR,'offer',return_value=o['ROOM_REST']),N.install(C):
   selected,trace=C.AD.plan_choose(a,100,None,[],None)
   self.assertIsNone(selected)
   offer,trace=C.HR.choose(a,[{'id':'ROOM_REST'}],100,20,None)
   self.assertEqual(offer['id'],'ROOM_REST');self.assertTrue(trace['selection_locked'])
  F.consumed(a,'ROOM_REST');self.assertIsNone(F.pending(a))
 def test_unknown_fact_is_not_silently_filtered_into_success(self):
  a=self.actor();e=self.entry();e['llm']['reasons']=[dict(type='후기 근거',text='not in input',fact_ids=['UNKNOWN'])]
  r=F.prepare(a,e,self.offers(),rule_choice='A',phase='engine',minute=100)
  self.assertEqual(r['final'],'A');self.assertEqual(r['review_proposed_final'],'B');self.assertIsNone(F.pending(a));self.assertFalse(r['review_succeeded'])
 def test_rule_proposal_and_successful_review_are_distinct(self):
  a=self.actor();e=self.entry();e.update(llm=None,outcome='NO_ANSWER_RULE_KEPT',call={'skipped':'replay_miss','cache_hit':False})
  r=F.prepare(a,e,self.offers(),rule_choice='A',phase='engine',minute=100)
  self.assertEqual(r['review_execution'],'CACHE_MISS');self.assertEqual(r['decision_source'],'RULE_ENGINE');self.assertEqual(r['final'],'A')
  self.assertEqual(RI.execution(None)['review_execution'],'NOT_REVIEWED')
  self.assertEqual(RI.execution(dict(llm={},call={'fixture':True}))['review_execution'],'SYNTHETIC_TEST')
  for call,mode in [({'cache_hit':True},'CACHE_REPLAY'),({'provider_response_received':True,'network_attempted':True},'LIVE_REVIEW')]:
   r=RI.execution(dict(llm={'choice':'B'},call=call,outcome='ADOPTED'))
   self.assertEqual(r['review_execution'],mode);self.assertTrue(r['review_succeeded'])
 def test_no_quote_or_disabled_choice_is_never_committed(self):
  for final,disabled in [('MISSING',False),('B',True)]:
   a=self.actor();e=self.entry();e['final']=final;o=self.offers();o['B']['available']=not disabled
   r=F.prepare(a,e,o,rule_choice='A',phase='engine',minute=100)
   self.assertEqual(r['final'],'A');self.assertIsNone(F.pending(a))
 def test_strict_cache_matches_input_model_and_native_policy(self):
  packet=dict(customer={'id':'P'},stay={'date':'2026-10-24'},candidates=[{'id':'A'},{'id':'B'}])
  config=dict(mode='replay',arb='adopt',max_usd=0,model='gpt-6-luna',effort='medium',native_policy='TEST_POLICY')
  with tempfile.TemporaryDirectory() as temp,patch('urllib.request.urlopen',side_effect=AssertionError('No provider')):
   config['cache']=temp;answer,miss=N.R.call(packet,config);self.assertIsNone(answer)
   record=dict(answer={'verdict':'agree','choice':'A','confidence':.8,'reasons':[]},usage={},prompt=copy.deepcopy(packet),identity=miss['identity'])
   (Path(temp)/(miss['cache_key']+'.json')).write_text(json.dumps(record))
   a,r=N.R.call(packet,config);self.assertEqual(a['choice'],'A');self.assertTrue(r['cache_hit']);self.assertFalse(r['network_attempted'])
   for altered in [dict(config,model='different-model'),dict(config,native_policy='different-policy')]:
    a,r=N.R.call(packet,altered);self.assertIsNone(a);self.assertFalse(r['cache_hit'])
   for altered in [dict(packet,stay={'date':'2026-10-25'}),dict(packet,candidates=[{'id':'A'}])]:
    a,r=N.R.call(altered,config);self.assertIsNone(a);self.assertFalse(r['cache_hit'])
   record['prompt']['stay']['date']='2026-10-25';(Path(temp)/(miss['cache_key']+'.json')).write_text(json.dumps(record))
   _,r=N.R.call(packet,config);self.assertEqual(r['skipped'],'cache_content_mismatch')
 def test_no_implicit_budget_or_key_can_enable_live_call(self):
  cfg=dict(mode='live',model='gpt-6-luna',effort='medium',max_usd=1,cache=None)
  with patch.dict(os.environ,{'HILLINK_LLM_EXTERNAL_OPT_IN':'0'},clear=True),patch('urllib.request.urlopen',side_effect=AssertionError('No provider')):
   a,r=N.R.call({'customer':{},'stay':{},'candidates':[]},cfg);self.assertIsNone(a);self.assertEqual(r['skipped'],'authorization')
  with patch.dict(os.environ,{'HILLINK_LLM_EXTERNAL_OPT_IN':'1'},clear=True):self.assertFalse(RI.live_allowed(cfg))
 def test_known_profile_fact_not_transmitted_to_reviewer_is_rejected(self):
  a=self.actor();e=self.entry();e['call']['citable_fact_ids']=[]
  e['llm']['reasons']=[dict(type='후기 근거',text='Was not sent to reviewer',fact_ids=['KNOWN'])]
  r=F.prepare(a,e,self.offers(),rule_choice='A',phase='engine',minute=100)
  self.assertEqual(r['final'],'A');self.assertEqual(r['validation_error'],'REVIEW_FACT_NOT_IN_INPUT')
 def test_live_cache_rejection_can_request_review_only_with_explicit_budget(self):
  import urllib.error
  packet=dict(customer={'id':'P'},stay={},candidates=[{'id':'A'}])
  config=dict(mode='live',arb='adopt',max_usd=.1,model='gpt-6-luna',effort='medium',native_policy='TEST_POLICY')
  with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HILLINK_LLM_EXTERNAL_OPT_IN':'1','HILLINK_HYBRID_MAX_USD':'.1'},clear=True),patch.object(N.R.time,'sleep'):
   config['cache']=temp;_,miss=N.R.call(packet,dict(config,mode='replay'))
   Path(temp,miss['cache_key']+'.json').write_text(json.dumps(dict(prompt={'wrong':'input'},answer={},usage={})))
   with patch('urllib.request.urlopen',side_effect=urllib.error.URLError('Synthetic offline transport failure')) as transport:
    answer,record=N.R.call(packet,config)
   self.assertIsNone(answer);self.assertTrue(transport.called);self.assertTrue(record['network_attempted'])
   self.assertEqual(record['cache_rejection_reason'],'cache_content_mismatch');self.assertFalse(record['cache_hit'])
 def test_memory_contains_only_recorded_past_not_projected_future(self):
  a=self.actor();a.log=[dict(act='room_rest',t='00:40',e='01:00',label='rest',loc='ROOM'),dict(act='sleep',t='02:00',e='03:00',label='future',loc='ROOM')]
  a.visit_history={'m4_history':[dict(date='2026-10-23',start='12:00',end='13:00',action_id='DINNER'),dict(date='2026-10-25',start='12:00',end='13:00',action_id='FUTURE')]}
  before=copy.deepcopy(a.visit_history);memory=N.R.recorded_memory(a,100)
  self.assertEqual([e['action_id'] for e in memory['prior_executed_events']],['DINNER']);self.assertEqual(len(memory['recent_recorded_rest']),1);self.assertEqual(memory['goal_status'],'NOT_RECORDED');self.assertEqual(a.visit_history,before)

if __name__=='__main__':unittest.main()
