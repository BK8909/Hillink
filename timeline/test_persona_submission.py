import copy
import unittest
from dataclasses import replace
from unittest.mock import patch

import agent_v2
from agent_v0 import TRAITS
import persona_blog05 as P5
import persona_blog06 as P6
from run_persona_submission import run_case, evaluate_partial


class SubmissionTests(unittest.TestCase):
    def test_assumptions_do_not_replace_observed_facts(self):
        for p in (P5, P6):
            self.assertIsNone(p.STAY_FACTS['party_size'])
            self.assertIsNone(p.OBSERVED_PERSONA.party_size)
            self.assertIsNone(p.OBSERVED_PERSONA.included_meals)
            self.assertIsNotNone(p.PERSONA.party_size)
            self.assertEqual(set(p.PERSONA.traits), set(TRAITS))
            self.assertEqual(len(p.PERSONA.unknown_traits()), 5)

    def test_both_cases_execute_without_mutating_persona(self):
        for p in (P5, P6):
            before = copy.deepcopy(p.PERSONA)
            result = run_case(p, 'test')
            self.assertTrue(result['validation_pass'])
            self.assertGreater(result['segment_count'], 0)
            self.assertEqual(before, p.PERSONA)

    def test_unknown_meals_are_not_zero_percent(self):
        result = evaluate_partial([], P6, P6.PERSONA)
        self.assertIsNone(result['meal_results'])
        self.assertIsNone(result['restaurants_exact'])
        self.assertIsNone(result['precision'])

    def test_unreachable_cu_excluded_not_counted_as_model_miss(self):
        result = evaluate_partial([], P6, P6.PERSONA)
        self.assertIn('CU_THEATRE', result['catalog_missing'])
        self.assertNotIn('CU_THEATRE', result['missed_visits'])

    def test_truth_not_used_by_agent(self):
        original, _ = agent_v2.run_agent(P5.PERSONA, P5.START_AT, verbose=False)
        with patch.object(P5, 'TRUTH_VISITED', {'PIZZA_HILL': 'test only'}):
            altered, _ = agent_v2.run_agent(P5.PERSONA, P5.START_AT, verbose=False)
        self.assertEqual(original, altered)

    def test_dates_and_variants_explicit(self):
        self.assertEqual(P5.START_AT.date().isoformat(), '2025-03-09')
        self.assertIsNone(P6.STAY_FACTS['visit_dates'])
        self.assertEqual(P6.START_AT.year, 2000)
        variant = run_case(P6, 'VISTA assumption', {'property': 'VISTA'})
        self.assertTrue(variant['validation_pass'])
        self.assertEqual(P6.PERSONA.property, 'GRAND')
        self.assertIsNone(P6.OBSERVED_PERSONA.property)


if __name__ == '__main__':
    unittest.main()
