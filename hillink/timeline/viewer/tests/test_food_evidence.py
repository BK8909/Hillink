import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1.food_evidence import observation,neutral_evidence,contribution
class FoodEvidenceTests(unittest.TestCase):
 def test_unknown_is_not_dislike_or_zero_preference(self):
  x=observation(dict(facets={},menu=[],venues={}))
  self.assertEqual(x['status'],'UNOBSERVED_IN_ACCEPTED_INPUT');self.assertEqual(x['menu_links'],[])
  self.assertEqual(x['source_quality']['counterevidence'],'NOT_PROVEN_ABSENT')
 def test_unmapped_food_evidence_is_not_reported_absent(self):
  x=observation(dict(facets={'food_specific':{'evidence':[{'fact_id':'F1','grade':'rep'}]}},menu=[]))
  self.assertEqual(x['status'],'FOOD_EVIDENCE_UNMAPPED');self.assertEqual(x['unmapped_food_fact_ids'],['F1'])
 def test_existing_polarities_not_new_source_approval(self):
  t=dict(facets={},menu=[dict(tags=['pizza'],weight=1,fact_ids=['F1']),dict(tags=['shellfish'],weight=-.5,fact_ids=['F2'])])
  before=copy.deepcopy(t);x=observation(t);self.assertEqual(t,before)
  self.assertEqual([m['polarity'] for m in x['menu_links']],['POSITIVE_LINK','NEGATIVE_LINK'])
  self.assertTrue(all(m['directness']=='NOT_VERIFIED_IN_RUNTIME_INPUT' for m in x['menu_links']))
 def test_indirect_evidence_and_counterexamples_preserved(self):
  t=dict(facets={'space':{'evidence':[{'fact_id':'F1','grade':'rep'},{'fact_id':'F2','grade':'exclude'}],'opposing_count':1}},menu=[])
  x=observation(t);self.assertEqual(x['status'],'UNOBSERVED_IN_ACCEPTED_INPUT');self.assertEqual(x['indirect_fact_ids'],{'space':['F1']})
  self.assertEqual(x['source_quality']['recorded_opposing_counts']['space'],1)
 def test_neutral_does_not_modify_profile_or_context_metadata(self):
  t=dict(facets={'food':{'evidence':[1],'level':.8}},menu=[1],venues={'X':[1]},evidence_index={'F1':{}});a=copy.deepcopy(t);b=neutral_evidence(t)
  self.assertEqual(t,a);self.assertEqual(b['facets']['food']['evidence'],[]);self.assertEqual(b['evidence_index'],t['evidence_index'])
 def test_same_state_split_sums_including_negative_and_disappearing_terms(self):
  terms=[dict(factor='food',value=2,fact_ids=['F1']),dict(factor='cost',value=-1)]
  common=[dict(factor='food',value=1.2),dict(factor='cost',value=-1),dict(factor='other',value=.2)]
  x=contribution(terms,common);self.assertAlmostEqual(x['common']+x['evidence_delta'],x['actual'])
  self.assertAlmostEqual(sum(t['evidence_delta'] for t in x['terms']),x['evidence_delta'])
if __name__=='__main__':unittest.main()
