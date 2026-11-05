import unittest,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as V

class DouglasVisitGate(unittest.TestCase):
 def resolve(self,children,building='DOUGLAS',duration='stay_1'):
  agent=SimpleNamespace(vs=dict(party_size=2,building='VISTA',stay=True),C={'kids':True})
  conditions=dict(building=building,party_size=2,party_composition=dict(adult_count=1,children=children))
  with patch.object(V.AD,'Agent',return_value=agent):
   return V._resolve_visit('test',duration,17,({}, {}, {}),conditions=conditions,behavior_engine='m4_c01')
 def test_known_child_and_unknown_age_cannot_bypass_room_catalog(self):
  for children in [[{'age_months':84,'school_stage':'elementary'}],[{}]]:
   with self.subTest(children=children),self.assertRaisesRegex(ValueError,'더글라스'):
    self.resolve(children)
 def test_eligible_teen_and_other_building_remain_supported(self):
  self.assertEqual(self.resolve([{'age_months':168,'school_stage':'secondary'}])['building'],'DOUGLAS')
  self.assertEqual(self.resolve([{'age_months':84,'school_stage':'elementary'}],'VISTA')['building'],'VISTA')
 def test_day_visit_does_not_acquire_a_room_restriction(self):
  self.assertFalse(self.resolve([{'age_months':84,'school_stage':'elementary'}],None,'day_visit')['stay'])
if __name__=='__main__':unittest.main()
