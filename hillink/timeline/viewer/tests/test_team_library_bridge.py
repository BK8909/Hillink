import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

VIEWER = Path(__file__).resolve().parents[1]
ROOT = VIEWER.parents[1]
sys.path.insert(0, str(VIEWER))
import build_team_library as bridge


class TeamLibraryBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exact original source bytes travel with the regression suite, without Git history.
        packet = json.loads((VIEWER / 'tests/fixtures/library_source_contract.json').read_text())
        class FixtureSource(bridge.TeamSource):
            def __init__(self, repo, ref=bridge.TEAM_BASE):
                self.repo, self.ref, self.receipts = Path(repo), ref, {}
            def raw(self, path):
                if path.startswith('/') or '..' in Path(path).parts:
                    raise ValueError('unsafe team path')
                entry = packet['sources'][self.ref + ':' + path]
                raw = entry['text'].encode('utf-8')
                if bridge.digest(raw) != entry['sha256']:
                    raise ValueError('pinned source fixture SHA mismatch')
                self.receipts[path] = entry['sha256']
                return raw
        cls.original = packet['original']
        cls.runtime = json.loads(bridge.display.ENGINE.read_text())['personas']
        cls.source = staticmethod(lambda: FixtureSource(ROOT))
        cls.followup = staticmethod(lambda: FixtureSource(ROOT, bridge.REVIEW_BASE))
        cls.supplemental = staticmethod(lambda: FixtureSource(ROOT, bridge.SUPPLEMENTAL_BASE))
        cls.library, cls.review = bridge.build(cls.source(), cls.original, cls.runtime, cls.followup(), cls.supplemental())
        cls.personas = {p['id']: p for p in cls.library['personas']}

    def test_team_pin(self):
        self.assertEqual(self.library['team_data']['commit'], bridge.TEAM_BASE)

    def test_60_candidates_plus_3_development(self):
        self.assertEqual(len(self.personas), 63)
        self.assertEqual(self.library['team_data']['candidate_count'], 60)
        self.assertEqual(self.library['team_data']['base_candidate_count'], 55)
        self.assertEqual(self.library['team_data']['supplemental_commit'], bridge.SUPPLEMENTAL_BASE)

    def test_unique_ids(self):
        self.assertEqual(len(self.library['personas']), len(self.personas))

    def test_new_candidates_are_not_runtime_agents(self):
        for i in range(1, 33):
            p = self.personas[f'N{i:02d}']
            self.assertFalse(p['status']['sim'])
            self.assertFalse(p['status']['reviewed'])
            self.assertEqual(p['status']['profile'], 'none')

    def test_development_profiles_preserved(self):
        for p in self.original['personas']:
            if p['id'].startswith('blog'):
                self.assertEqual(p, self.personas[p['id']])

    def test_runtime_input_not_changed(self):
        before = copy.deepcopy(self.runtime)
        bridge.build(self.source(), self.original, self.runtime, self.followup())
        self.assertEqual(before, self.runtime)
        self.assertFalse(self.library['team_data']['runtime_input_updated'])

    def test_5_shared_profiles_have_separate_status(self):
        active = [p for p in self.personas.values() if 'team_profile' in p]
        self.assertEqual(len(active), 5)
        for p in active:
            self.assertFalse(p['team_profile']['engine_input_replaced'])
            self.assertFalse(p['team_profile']['review_status']['demo_approved'])

    def test_deterministic_rebuild(self):
        again, reviews = bridge.build(self.source(), self.library, self.runtime, self.followup(), self.supplemental())
        self.assertEqual(again, self.library)
        self.assertEqual(reviews, self.review)

    def test_cross_review_scope(self):
        self.assertEqual(len(self.review['cross_review']['items']), 22)
        self.assertFalse(self.review['cross_review']['team_consensus'])

    def test_event_keys_are_author_scoped(self):
        for r in self.review['cross_review']['items']:
            self.assertTrue(all(k.startswith(r['author'] + '-E') for k in r['event_refs']))

    def test_slgi_detail_not_invented(self):
        self.assertEqual(self.review['slgi']['detail_workbook_status'], 'not_received')
        self.assertFalse(self.review['slgi']['latest_detail_comparison_complete'])

    def test_105_is_separate_review_layer(self):
        r = self.review['future_signal_review']
        self.assertEqual(len(r['cases']), 4)
        self.assertEqual(r['common_commit'], bridge.REVIEW_BASE)
        self.assertFalse(r['applied_to_engine'])

    def test_machine_proposals_unapplied(self):
        self.assertEqual(self.review['machine_field_proposals']['status'], 'pending_owner_approval_not_applied')

    def test_exclusion_list_unchanged(self):
        self.assertEqual(self.library['team_data']['evaluation_exclusion_rows'], 155)
        self.assertEqual(self.library['team_data']['evaluation_exclusion_sha256'], '3babb15a491d6347184e43dc04f58dac1da982f1fba454b4016903c47d4eb119')

    def test_original_55_card_file_is_unchanged(self):
        self.assertEqual(bridge.digest(self.source().raw(bridge.CARD_PATH)),
                         '6f42512299711cfb0f64990528952b3945a9df6b0d24e04a54188be9888bc4e8')

    def test_107_additions_are_candidates_not_agents(self):
        self.assertEqual(self.library['team_data']['new_candidate_ids'], [f'N{i:02d}' for i in range(1, 33)])
        self.assertEqual(self.review['pr107_library_followup']['candidate_ids'], ['N28', 'N29', 'N30', 'N31', 'N32'])
        self.assertEqual(self.review['pr107_library_followup']['runtime_agents_added'], 0)
        for i in range(28, 33):
            p = self.personas[f'N{i:02d}']
            self.assertFalse(p['status']['sim'])
            self.assertIn('visit_feature_summary', p)

    def test_107_exposure_records_remain_separate(self):
        self.assertEqual(self.review['pr107_library_followup']['morning_exposure_rows'], 155)
        self.assertEqual(self.review['pr107_library_followup']['afternoon_additional_exposure_rows'], 36)
        self.assertEqual(self.review['pr107_library_followup']['afternoon_overlap_with_morning'], 0)
        self.assertEqual(len(self.library['team_data']['additional_exposure_ids']), 36)

    def test_106_is_review_only_and_a05_ids_are_not_aliased(self):
        r = self.review['pr106_review']
        self.assertEqual(r['hypothesis_reviews'], 20)
        self.assertEqual(r['machine_field_proposals'], 7)
        self.assertEqual(r['mixed_action_stage_opinions'], 5)
        self.assertEqual(r['pr105_followups'], 4)
        self.assertEqual(r['comparison_customer_decisions'], 46)
        self.assertFalse(r['applied_to_profiles_or_engine'])
        self.assertEqual(r['a05_reference_review']['source_fact_id'], 'A05-F08')
        self.assertEqual(r['a05_reference_review']['runtime_fact_id'], 'A05-F08a')
        self.assertEqual(r['a05_reference_review']['relationship'], 'distinct_ids_under_review_not_aliases')

    def test_private_links_not_exported(self):
        self.assertIsNone(bridge.display.IDENT.search(json.dumps([self.library, self.review], ensure_ascii=False)))
        self.assertFalse(self.library['team_data']['private_links_included'])

    def test_moving_ref_rejected(self):
        with self.assertRaises(ValueError): bridge.TeamSource(ROOT, 'origin/merge/validator-0923')

    def test_unsafe_path_rejected(self):
        with self.assertRaises(ValueError): self.source().raw('../private.json')

    def test_existing_data_not_mutated(self):
        original = copy.deepcopy(self.original)
        bridge.build(self.source(), self.original, self.runtime, self.followup())
        self.assertEqual(original, self.original)


if __name__ == '__main__':
    unittest.main()
