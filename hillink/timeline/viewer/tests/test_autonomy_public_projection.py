"""The legacy autonomy response must not inherit nested scorer source text."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autonomy_run import public_log_projection


class LegacyAutonomyProjection(unittest.TestCase):
    def test_nested_candidate_summaries_removed_without_mutating_engine_result(self):
        raw = {"inputs_sha": "original", "log": [{"act": "meal", "t": "12:00",
            "internal": {"candidates": [{"terms": [{"value": 2, "fact_ids": ["F1"],
                "evidence": [{"fact_id": "F1", "gist": "private source summary"}]}]}]},
            "order": {"sku": "SKU1", "quantity": 2, "total_krw": 100}}]}
        original = copy.deepcopy(raw)
        shown = public_log_projection(raw)
        self.assertEqual(raw, original)
        self.assertEqual(shown["inputs_sha"], raw["inputs_sha"])
        self.assertEqual(shown["log"][0]["order"], raw["log"][0]["order"])
        self.assertEqual(shown["log"][0]["act"], "meal")
        term = shown["log"][0]["internal"]["candidates"][0]["terms"][0]
        self.assertEqual(term, {"value": 2, "fact_ids": ["F1"], "evidence": [{"fact_id": "F1"}]})

    def test_other_private_summary_fields_and_comparison_baseline(self):
        raw = {"baseline": {"A": {"log": [{"source_gist": "private", "review_text": "raw",
            "evidence": [{"fact_ids": ["F2"], "type": "프로파일 기반 추론"}]}]}},
            "stories": [{"why": "derived explanation", "gist": "private"}]}
        self.assertEqual(public_log_projection(raw), {"baseline": {"A": {"log": [{
            "evidence": [{"fact_ids": ["F2"], "type": "프로파일 기반 추론"}]}]}},
            "stories": [{"why": "derived explanation"}]})
