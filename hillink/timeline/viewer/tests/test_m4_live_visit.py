"""Actual M4 calculation versus accepted research and explicit visit inputs."""
import copy,json,os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
import visit_run as VR
import ledger_service as LS
from operator_choice.autonomy_v1 import m4_runtime as M4,ledger as LG
REF=json.loads((Path(__file__).parent/'fixtures/a08_m4_research_ae37786.json').read_text())
HAS_INPUT='A08' in VR.AD.load_inputs()[0]

def request(pid='A08',event='none',duration='stay_2',**kw):
 return dict(personas=[pid],duration=duration,event_mode=event,seed=0,start_date='2026-10-24',**kw)

def execute(q):
 f=VR.run_visit(q)
 if f.get('error'):raise AssertionError(f)
 return f,LS.register_visit(f,q)

@unittest.skipUnless(HAS_INPUT,'approved private A08 execution inputs unavailable')
class M4LiveVisitTests(unittest.TestCase):
 # The frozen research reference predates the external-delivery default; it is reproduced under the previous policy.
 @classmethod
 def setUpClass(cls):
  cls._delivery=os.environ.get('HILLINK_EXTERNAL_DELIVERY');os.environ['HILLINK_EXTERNAL_DELIVERY']='0'
  cls.runs={e:execute(request(event=e)) for e in ('none','wine')}
 @classmethod
 def tearDownClass(cls):
  if cls._delivery is None:os.environ.pop('HILLINK_EXTERNAL_DELIVERY',None)
  else:os.environ['HILLINK_EXTERNAL_DELIVERY']=cls._delivery
 def test_a08_same_source_profile_and_facts_not_reprofiled_to_match(self):
  for f,l in self.runs.values():
   m=f['plans']['A08']['m4']
   self.assertEqual(m['behavior_profile_sha256'],'5109f6a2f6f6fe6e406d8e3ad8025842c8c212d7c081672007ca10eefe5785ef')
   self.assertEqual(m['facts_traits_sha256'],'2b76e7c54408f5ba7a5dbb6d8a05a8554dcb0ba4416e1ce968df076581402af1')
   self.assertEqual(f['visits']['A08']['building'],'DOUGLAS');self.assertEqual(f['visits']['A08']['party_size'],2)
   self.assertEqual(f['visit']['resolved_conditions']['A08']['club'],f['visits']['A08']['club'])
   self.assertEqual(m['configuration']['execution_mode'],'LIVE_RULES_COMPUTATION_NOT_SNAPSHOT_REPLAY')
 def test_complete_action_sequence_and_l5_transactions_match_research(self):
  keys=('date','start','end','action_id','venue_id','fraction');tk=('visit_day','time','venue_id','product','quantity','unit_price_krw','paid_krw','assumption_addition_krw','amount_status')
  for event,(f,l) in self.runs.items():
   ref=REF['cases'][event];m=f['plans']['A08']['m4']
   self.assertEqual([{k:e[k] for k in keys} for e in m['activity_history']],ref['activities'])
   # D01 intentionally prices native room-night rows; all original nonroom
   # transactions and the frozen behavior fixture remain unchanged.
   rows=[{k:t.get(k) for k in tk} for t in l['receipts']['A08']['rows'] if t['act']!='room_night']
   self.assertEqual(rows,[t for t in ref['transactions'] if not t['product'].startswith('객실 1박')])
   rooms=[t for t in l['receipts']['A08']['rows'] if t['act']=='room_night']
   self.assertEqual(sum(t['paid_krw'] for t in rooms),518000)
   self.assertEqual(l['totals']['paid_krw'],ref['paid_krw']+518000)
   self.assertEqual(l['totals']['assumption_addition_krw'],0)
 def test_all_quantitative_candidate_values_match_research(self):
  keys=('candidate_id','base_score','context_adjustment','final_score','final_with_lookahead','world_allowed')
  for event,(f,l) in self.runs.items():
   current=[{'date':d['packet']['context_factors']['date'],'time':d['packet']['context_factors']['time'],'selected':d['selected_action'],
       'candidates':[{k:c.get(k) for k in keys} for c in d['packet']['candidates']]} for d in f['plans']['A08']['m4']['decisions'] if d['packet']['kind']=='QUANTITATIVE']
   self.assertEqual(current,REF['cases'][event]['quantitative_decisions'])
 def test_reentry_memory_is_soft_and_unconfirmed_meal_credit_removed(self):
  f,l=self.runs['wine'];m=f['plans']['A08']['m4'];day2=next(d for d in m['decisions'] if d['packet']['kind']=='QUANTITATIVE' and d['packet']['context_factors']['date']=='2026-10-25' and d['packet']['context_factors']['time']==950)
  self.assertEqual(day2['selected_action'],'ROOM_REST');self.assertEqual(len(day2['packet']['context_factors']['event_memory']['prior_attendance']),1)
  candidate=next(c for c in day2['packet']['candidates'] if c['candidate_id']=='WINE_FAIR')
  self.assertTrue(candidate['world_allowed']);self.assertEqual(candidate['context_adjustment'],-.45);self.assertEqual(candidate['final_score'],.275)
  self.assertEqual(sum(e['action_id']=='WINE_FAIR' for e in m['activity_history']),1)
  self.assertTrue(all(d['llm_choice'] is None for d in m['decisions']))
 def test_day_ledger_and_trace_hash_invariants(self):
  for f,l in self.runs.values():
   self.assertTrue(l['checks']['day_totals_equal_visit_total']);self.assertTrue(l['checks']['receipts_equal_L4_L3_L2_L1'])
   self.assertEqual(len(l['receipts']['A08']['rows']),len({r['row_id'] for r in l['receipts']['A08']['rows']}))
   for d in f['plans']['A08']['m4']['decisions']:
    p=copy.deepcopy(d['packet']);h=p.pop('packet_sha256');self.assertEqual(M4.digest(p),h)
   for day in f['visit_days']:
    scenes=day['flow']['plans']['A08']['scenes'];self.assertTrue(all(s['t1']<=1380 for s in scenes))
    self.assertTrue(all(a['t1']<=b['t0'] for a,b in zip(scenes,scenes[1:])))
   self.assertTrue(any(s['basis'].get('m4') for s in f['plans']['A08']['scenes']))
 def test_seed_and_duration_are_new_calculations(self):
  base,_=self.runs['none'];q=request();q['seed']=17;other,l=execute(q)
  self.assertNotEqual(base['visit_id'],other['visit_id'])
  for duration,n in [('day_visit',0),('stay_1',1),('stay_3',3)]:
   f,l=execute(request(duration=duration));self.assertEqual(len(f['visit_days']),n+1)
   self.assertEqual(sum(r['act']=='room_night' for r in l['receipts']['A08']['rows']),n)
   if not n:self.assertEqual(l['totals']['assumption_addition_krw'],0)
 def test_multi_customer_history_is_isolated(self):
  q=request();q['personas']=['A04','A08'];f,l=execute(q)
  self.assertEqual(f['plans']['A08']['m4']['activity_history'],self.runs['none'][0]['plans']['A08']['m4']['activity_history'])
  for pid in q['personas']:
   self.assertTrue(all(d['packet']['context_factors']['customer_id']==pid for d in f['plans'][pid]['m4']['decisions']))
 def test_a04_explicit_one_person_vista_and_package_reference_do_not_change_people(self):
  for package,building in [(None,'VISTA'),('GRAND_SUNGSU_V2_2N','GRAND')]:
   q=request('A04',visit_conditions={'A04':{'party_size':1,'building':building,'club':False}})
   if package:q['package_id']=package
   f,l=execute(q)
   self.assertEqual(f['visits']['A04']['building'],building);self.assertEqual(f['visits']['A04']['party_size'],1)
   self.assertTrue(all(d['flow']['visits']['A04']['party_size']==1 for d in f['visit_days']))
   if package:self.assertEqual(f['visit']['resolved_conditions']['A04']['package_reference_party_size'],2)
 def test_invalid_overrides_fail_closed(self):
  for override in ({'party_size':True},{'party_size':0},{'building':'UNKNOWN'},{'club':True,'building':'VISTA'}):
   self.assertIn('error',VR.run_visit(request('A04',visit_conditions={'A04':override})))
  self.assertIn('error',VR.run_visit(request('A04',visit_conditions={'A04':{'party_size':1,'building':'VISTA'}},package_id='GRAND_SUNGSU_V2_2N')))
 def test_m4_planner_and_install_cannot_invoke_paid_provider(self):
  with self.assertRaisesRegex(ValueError,'PAID_REASONER_DISABLED'):
   M4.run_one('A08',{'planner':'llm'},None)
  before=(M4.AD.EN.score,M4.AD.EN.decide_at)
  from operator_choice.autonomy_v1.m4_context import M4Context
  with self.assertRaisesRegex(RuntimeError,'synthetic'):
   with M4Context('M4',meal_state_enabled=True).install():raise RuntimeError('synthetic')
  self.assertEqual(before,(M4.AD.EN.score,M4.AD.EN.decide_at))
 def test_package_extra_people_unknown_is_not_free_or_a_party_override(self):
  import package_entitlements as PE
  pack=PE.get_package('GRAND_SUNGSU_V2_2N');actor=SimpleNamespace(vs={'package_context':pack},N=3,visit_history={'benefit_usage':{'package_entitlements':PE.initial_benefit_usage(pack)}})
  row=LG.charge(actor,'sauna','wellness','GRAND_SAUNA')
  self.assertIsNone(row['krw']);self.assertEqual(row['status'],'가격 미정');self.assertEqual(row['unpriced_extra_people'],1);self.assertTrue(row['entitlement_consumed'])

# 11/02: 유료 룸서비스 조식 자동 구매 중단 이전의 동결 기준을 재현하는 테스트 — 이 모듈에서만 이전 규칙을 켬.
import os as _bf_os
def setUpModule():
    _bf_os.environ["HILLINK_PAID_IRD_BREAKFAST_AUTO"] = "1"
    _bf_os.environ["HILLINK_BREAKFAST_POLICY"] = "LEGACY_STAY_INCLUDED"   # 11/03 조식 계약 정책 이전 기준
def tearDownModule():
    _bf_os.environ.pop("HILLINK_PAID_IRD_BREAKFAST_AUTO", None)
    _bf_os.environ.pop("HILLINK_BREAKFAST_POLICY", None)


if __name__=='__main__':unittest.main()
