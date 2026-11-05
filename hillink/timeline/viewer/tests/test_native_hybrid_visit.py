"""A synthetic reviewer checks wiring only; it is not an LLM quality evaluation."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

VIEWER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(VIEWER))
import visit_run as V
import ledger_service as L

class NativeHybridVisitTests(unittest.TestCase):
    def test_adoption_scene_components_and_distinct_run_cache(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,dict(HILLINK_V12Z_COMMON='1',HILLINK_NATIVE_HYBRID='1',HILLINK_HYBRID='dry',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_ISOLATED_CUSTOMERS='0',PYTHONDONTWRITEBYTECODE='1')):
            script=Path(temp)/'fixture.py'
            script.write_text('''import sys
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import flow_run
from operator_choice.autonomy_v1 import native_hybrid as N
def answer(packet,c):
 return dict(verdict='disagree',choice=packet['candidates'][-1]['id'],confidence=.95,reasons=[dict(type='상황',text='계약 시험 응답',fact_ids=[])],summary='SYNTHETIC_TEST_NOT_MODEL_RESULT'),dict(fixture=True,cost_usd=0,cache_hit=False)
with patch.object(N.R,'call',answer):flow_run.main()
''')
            request=dict(personas=['A02'],duration='stay_1',event_mode='none',start_date='2026-10-24',seed=17,behavior_engine='m4_c01',catalog_policy='C01_HOTEL_CATALOG_V1',hybrid_policy='SELECTIVE_V12Z_NATIVE_V1')
            with patch.object(V,'FLOW',[sys.executable,'-B',str(script),str(VIEWER)]):
                flow=V.run_visit(request)
            self.assertNotIn('error',flow)
            ledger=L.register_visit(flow,request)
            scenes=[s for s in flow['plans']['A02']['scenes'] if ((s.get('basis') or {}).get('review') or {}).get('decided_by')=='SYNTHETIC_REVIEW_ADOPTED']
            self.assertTrue(scenes,'fixture must exercise actual adoption')
            rows=[r for r in ledger['receipts']['A02']['rows'] if r.get('selection_id')]
            self.assertTrue(rows)
            for row in rows:
                matches=[s for s in scenes if s['basis']['selection_id']==row['selection_id']]
                self.assertEqual(len(matches),1)
                self.assertEqual(row['sku_contract']['final_candidate_id'],matches[0]['basis']['review']['final'])
            self.assertTrue(ledger['checks']['receipts_equal_L4_L3_L2_L1'])
            # Same request with no reviewer must not retrieve the fixture's ledger.
            rule=V.run_visit(request)
            self.assertNotIn('error',rule)
            self.assertNotEqual(flow['visit_id'],rule['visit_id'])
            self.assertNotEqual(ledger['run_id'],L.register_visit(rule,request)['run_id'])

if __name__=='__main__':unittest.main()
