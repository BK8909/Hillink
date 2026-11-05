"""Selection identity and source preservation across the native/catalog seam."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

VIEWER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIEWER))
import hotel_ledger as L
import intake_team_profile as I
from operator_choice.autonomy_v1 import native_hybrid as N

class NativeCatalogHybridTests(unittest.TestCase):
    def test_private_pilot_requires_both_flags_and_explicit_request(self):
        actor = SimpleNamespace(sc={'hybrid_policy': N.POLICY})
        with patch.dict(os.environ, {'HILLINK_NATIVE_HYBRID':'1','HILLINK_V12Z_COMMON':'0'}):
            self.assertFalse(N.active(actor))
        with patch.dict(os.environ, {'HILLINK_NATIVE_HYBRID':'1','HILLINK_V12Z_COMMON':'1'}):
            self.assertTrue(N.active(actor))
            self.assertFalse(N.active(SimpleNamespace(sc={})))

    def test_catalog_opt_in_preserves_legacy_minimal_actor_contract(self):
        self.assertFalse(L.H.enabled(SimpleNamespace()))
        self.assertFalse(L.H.enabled(SimpleNamespace(sc=None)))
        self.assertFalse(L.H.enabled(SimpleNamespace(sc={})))
        self.assertTrue(L.H.enabled(SimpleNamespace(sc={'catalog_policy':L.H.POLICY})))

    def test_live_provider_is_not_authorized_by_hybrid_flag(self):
        with patch.dict(os.environ, {'HILLINK_HYBRID':'live','HILLINK_LLM_EXTERNAL_OPT_IN':'0'}):
            with self.assertRaisesRegex(ValueError,'PAID_PROVIDER_NOT_AUTHORIZED'):
                N.R.cfg()

    def test_malformed_review_keeps_rule_instead_of_breaking_visit(self):
        valid=dict(verdict='disagree',choice='B',confidence=.8,reasons=[dict(type='상황',text='fixture',fact_ids=[])])
        self.assertTrue(N.valid_answer(valid))
        for field,value in [('choice',None),('confidence',float('nan')),('confidence',True),('reasons',['malformed'])]:
            self.assertFalse(N.valid_answer(dict(valid,**{field:value})))

    def test_component_transactions_keep_final_selection_and_sum_once(self):
        contract = dict(catalog_policy=L.H.POLICY,selection_id='selected-event',final_candidate_id='HC_FINAL',unit_price_krw=250,
            components=[dict(sku_id='sku-1',label='one',unit_price_krw=100,billing_quantity=2,billing_unit='item',price_tier='OFFICIAL'),
                        dict(sku_id='sku-2',label='two',unit_price_krw=50,billing_quantity=1,billing_unit='item',price_tier='SIMULATION_ASSUMPTION')])
        raw=[{'선택 SKU 계약':contract,'상태':'유료','_row_key':'order','확인 메모':'fixture','확정 결제액':250}]
        before=copy.deepcopy(raw);traces={'order':{'scene_index':3}}
        rows=L.expand(raw,traces)
        self.assertEqual(raw,before)
        self.assertEqual(sum(r['확정 결제액'] for r in rows),250)
        self.assertEqual(len({r['_row_key'] for r in rows}),2)
        for row in rows:
            self.assertEqual(row['선택 SKU 계약']['selection_id'],'selected-event')
            self.assertEqual(row['선택 SKU 계약']['final_candidate_id'],'HC_FINAL')
            self.assertEqual(traces[row['_row_key']]['scene_index'],3)

    def test_source_assumption_is_not_reported_as_reference_and_quote_is_immutable(self):
        c=dict(sku_id='HC-MENU-127',catalog_sha256='catalog',price_tier='EXISTING_REFERENCE',source_grade='△',billing_quantity=4)
        row=dict(row_id='tx',paid_krw=792000,unit_price_krw=198000,sku_contract=c)
        ledger=dict(receipts={'P':{'rows':[row]}},totals={'paid_krw':792000});before=copy.deepcopy(c)
        L.annotate(ledger)
        self.assertEqual(row['price_tier'],'SIMULATION_ASSUMPTION');self.assertEqual(c,before)
        self.assertEqual(row['paid_krw'],792000);self.assertEqual(row['unit_price_krw'],198000)
        self.assertEqual(ledger['price_class_aggregates']['estimated_or_assumed_krw'],792000)
    def test_adopted_choice_is_a_feasible_input_candidate(self):
        feasible=[dict(offer='A',total=1),dict(offer='B',total=.9)]
        answer=dict(verdict='disagree',choice='UNKNOWN',confidence=.99,reasons=[dict(type='상황',text='fixture',fact_ids=[])])
        selected,_=N.R.arbitrate(answer,feasible,dict(arb='adopt'),[dict(id='A'),dict(id='B')])
        self.assertIsNone(selected)

    def test_history_projection_preserves_source_and_refuses_observed_hold(self):
        doc=dict(schema_version='team_persona_shared_export_v1',author_group_id='TEST',facts=[dict(fact_id='TEST-F001',feature_key='repeat_visit',experience_key='E1',scope='related',kind='participation',time_scope='source_experience',actor='author',detail='fixture')])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'shared.json';path.write_text(json.dumps(doc));before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'nonobservational_scope'):
                I.check(str(path),history_evidence_hold_ids=['TEST-F001'])
            self.assertEqual(path.read_bytes(),before)

if __name__ == '__main__': unittest.main()
