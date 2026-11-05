"""Shared clock/world, independent agent memories, and L5 inverse references."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as VR,ledger_service as LS
from operator_choice.autonomy_v1 import m4_runtime as M4

@unittest.skipUnless({'A04','A08'}<=set(VR.AD.load_inputs()[0]),'private approved runtime inputs unavailable')
class SharedWorldTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.q=dict(personas=['A04','A08'],duration='stay_2',event_mode='wine',seed=0,start_date='2026-10-24')
  cls.f=VR.run_visit(cls.q);cls.l=LS.register_visit(cls.f,cls.q)
 def test_real_time_queue_not_ten_finished_runs(self):
  f=self.f;self.assertEqual(f['engine']['simulation_mode'],'shared_world')
  for d in f['shared_world']['days']:
   queue=d['decision_order'];self.assertEqual([x['decision_minute'] for x in queue],sorted(x['decision_minute'] for x in queue))
   self.assertEqual(d['world_instance_count'],1);self.assertEqual(set(d['completed_customer_ids']),{'A04','A08'})
   self.assertGreater(sum(a['customer_id']!=b['customer_id'] for a,b in zip(queue,queue[1:])),3)
   self.assertFalse(d['capacity_and_queues_supported'])
 def test_isolated_history_and_source_appraisals(self):
  for pid,plan in self.f['plans'].items():
   self.assertTrue(all(x['packet']['context_factors']['customer_id']==pid for x in plan['m4']['decisions']))
   other={e['event_id'] for op,p in self.f['plans'].items() if op!=pid for e in p['m4']['activity_history']}
   self.assertFalse(other&{e['event_id'] for e in plan['m4']['activity_history']})
   if pid=='A04':self.assertTrue(all(not x['packet']['source_evidence'] for x in plan['m4']['decisions']))
 def test_all_durations_keep_calendar_and_room_contract(self):
  for duration,n in [('day_visit',0),('stay_1',1),('stay_3',3)]:
   q=dict(self.q,duration=duration);f=VR.run_visit(q);l=LS.register_visit(f,q)
   self.assertEqual(len(f['shared_world']['days']),n+1)
   for receipt in l['receipts'].values():self.assertEqual(sum(r['act']=='room_night' for r in receipt['rows']),n)
   self.assertTrue(l['checks']['day_totals_equal_visit_total'])
 def test_operation_buckets_are_exact_inverse_references(self):
  f,l=self.f,self.l;o=l['operations'];self.assertEqual(o['ledger_run_id'],l['run_id'])
  rows=[x for b in o['buckets'] for x in b['transactions']]
  self.assertEqual(len(rows),len({x['row_id'] for x in rows}))
  self.assertEqual({x['row_id'] for x in rows},{x['row_id'] for r in l['receipts'].values() for x in r['rows']})
  self.assertEqual(sum(b['paid_krw'] for b in o['buckets']),l['totals']['paid_krw'])
  self.assertEqual(sum(b['room_and_other_assumption_krw'] for b in o['buckets']),l['totals']['assumption_addition_krw'])
  for b in o['buckets']:
   for x in b['actions']:self.assertEqual(f['plans'][x['customer_id']]['scenes'][x['visit_scene_index']]['act'],x['action_id'])
   for x in b['transactions']:
    if x['act']=='room_night':self.assertIsNone(b['hour'])
  self.assertEqual(LS.register_visit(f,self.q)['totals'],l['totals'])
 def test_same_world_rule_change_and_order_independence(self):
  inputs=VR.AD.load_inputs();resolution={pid:VR._resolve_visit(pid,'day_visit',0,inputs) for pid in ['A04','A08']}
  sc=VR.AD.scenario('same_world_test',seed=0,visit_resolution=resolution,changes=[{'at':'16:00','label':'control switch','levers':{'WINE_FAIR':{'available':False}}}],levers={'WINE_FAIR':{'available':True}})
  before=VR.AD.World;instances=[]
  class World(before):
   def __init__(self,*args):super().__init__(*args);instances.append(self)
  # Delivery alternatives may construct temporary simulation worlds. Verify the
  # authoritative decisions of both customers share one world, by object identity.
  decide=VR.AD.decide;depth=0;authoritative=[]
  def observe_decide(agent,world):
   nonlocal depth
   if depth==0:authoritative.append((agent.pid,id(world)))
   depth+=1
   try:return decide(agent,world)
   finally:depth-=1
  with patch.object(VR.AD,'World',World),patch.object(VR.AD,'decide',observe_decide):
   r=M4.run_many(['A08','A04'],sc,inputs)
  self.assertEqual({pid for pid,_ in authoritative},{'A04','A08'})
  self.assertEqual({wid for _,wid in authoritative},{id(instances[0])})
  for x in r['shared_world']['decision_order']:
   self.assertEqual(x['world_event_available'],x['decision_minute']<960)
  swapped=M4.run_many(['A04','A08'],sc,inputs)
  for pid in ['A04','A08']:self.assertEqual(r['personas'][pid]['m4']['activity_history'],swapped['personas'][pid]['m4']['activity_history'])
 def test_bad_mode_and_paid_planner_fail_closed(self):
  self.assertIn('error',VR.run_visit(dict(self.q,simulation_mode='unknown')))
  self.assertIn('error',VR.run_visit(dict(self.q,behavior_engine='legacy',simulation_mode='shared_world')))
  with self.assertRaisesRegex(ValueError,'PAID_REASONER_DISABLED'):M4.run_many(['A04','A08'],{'planner':'llm'},None)
 def test_per_step_hooks_restore_on_failure(self):
  inputs=VR.AD.load_inputs();before=(M4.AD.Agent.add,M4.SP.pick,M4.AD.EN.score)
  with patch.object(M4.AD,'decide',side_effect=RuntimeError('deliberate')):
   with self.assertRaisesRegex(RuntimeError,'deliberate'):M4.run_many(['A04','A08'],M4.AD.scenario(),inputs)
  self.assertEqual(before,(M4.AD.Agent.add,M4.SP.pick,M4.AD.EN.score))
