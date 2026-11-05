import unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[2]/'experiments/persona_live')]
import private_intake_view as P

class PrivateView(unittest.TestCase):
 def test_unregistered_customer_is_rejected(self):
  with patch.object(P.IR,'registrations',return_value={}):
   with self.assertRaises(ValueError):P.project('missing')
 def test_projection_preserves_fact_ids_and_pending_approval_without_source_paths(self):
  profile={'traits':{'facets':{'novelty':{'level':2,'present':True,'evidence':[{'fact_id':'X-F1','gist':'private raw quote','feature':'test','grade':'obs'}]}}}}
  source={'X':{'engine':{'facts':{'X-F1':{'gist':'Observed action','post_id':'private post','url':'https://example.test/private'},'X-F2':{'gist':'https://example.test/private'}}}}}
  with patch.object(P.IR,'registrations',return_value={'X':(profile,{'profile_sha256':'a'*64})}),patch.object(P.IR,'extend_library',return_value=source):d=P.project('X')
  self.assertFalse(d['public_approval']);self.assertFalse(d['human_approval']);self.assertEqual(d['technical_stage'],'RUNNABLE')
  self.assertEqual(set(d['customer']['engine']['facts']),{'X-F1','X-F2'})
  self.assertNotIn('url',d['customer']['engine']['facts']['X-F1']);self.assertNotIn('post_id',d['customer']['engine']['facts']['X-F1'])
  self.assertNotIn('https://',d['customer']['engine']['facts']['X-F2']['gist']);self.assertNotIn('gist',d['facets']['novelty']['evidence'][0])

 def test_strategy_projection_preserves_tags_and_groups_without_private_source_ids(self):
  import copy,json
  profile={'traits':{'facets':{'food_specific':{'present':True,'evidence':[{'fact_id':'F','feature':'pasta_preference','grade':'rep'}]}}}}
  facts={'F':{'gist':'food choice','features':['pasta_preference'],'post_id':'private-account-post','experience_key':'private-trip','actor':'author','time_scope':'historical'},'G':{'gist':'same visit','features':[],'post_id':'private-account-post','experience_key':'private-trip'}}
  source={'C':{'engine':{'facts':facts}}};original=copy.deepcopy(source)
  with patch.object(P.IR,'registrations',return_value={'C':(profile,{})}),patch.object(P.IR,'extend_library',return_value=source):
   view=P.project('C');strategy=P.project('C',strategy=True)
  a=strategy['customer']['engine']['facts'];self.assertEqual(a['F']['features'],['pasta_preference']);self.assertEqual(a['F']['post'],a['G']['post']);self.assertEqual(a['F']['exp'],a['G']['exp'])
  self.assertNotIn('private-account',json.dumps(strategy));self.assertNotIn('private-trip',json.dumps(strategy));self.assertNotIn('features',view['customer']['engine']['facts']['F']);self.assertEqual(source,original)
