"""L2 department classification must follow what is sold, not only add up.

Every venue the ledger maps to an L2 department is checked against the categories of the
products the hotel catalog sells there. A drink/food venue booked under ROOM (the old
LUX_BAR mapping) moves F&B spend into ROOM while every total still matches.
"""
import collections, json, sys, unittest
from pathlib import Path
VIEWER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIEWER))
import ledger_l5 as L

CATALOG = VIEWER.parents[0] / 'experiments' / 'persona_live' / 'operator_choice' / 'autonomy_v1' / 'hotel_catalog.json'
EXPECTED = {'F&B': {'F&B'}, '레저': {'ACTIVITY'}}


class LedgerDepartmentClassification(unittest.TestCase):
    def setUp(self):
        self.cat = collections.defaultdict(set)
        for p in json.loads(CATALOG.read_text())['products']:
            if p.get('category'):
                self.cat[p['venue_id']].add(p['category'])

    def test_department_matches_catalog_product_category(self):
        for venue, (l2, _) in L.LOC_L23.items():
            sold = self.cat.get(venue)
            if not sold:
                continue
            self.assertTrue(sold <= EXPECTED.get(l2, set()), f'{venue}: L2 {l2} but catalog sells {sorted(sold)}')

    def test_lux_bar_is_food_and_beverage(self):
        self.assertEqual(L.LOC_L23['LUX_BAR'], ('F&B', '럭스바'))

    def test_no_scene_venue_is_booked_under_room(self):
        # ROOM is assigned separately for room nights (and in-room dining by its own rule); no scene venue maps to it.
        self.assertFalse([v for v, (l2, _) in L.LOC_L23.items() if l2 == 'ROOM'])


if __name__ == '__main__':
    unittest.main()
