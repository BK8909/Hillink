"""The situation screen's event-card date label mirrors the engine date gate; the engine stays authoritative."""
import json,sys,unittest
from pathlib import Path
VIEWER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(VIEWER))
import visit_run  # noqa: F401  (path setup)
from operator_choice.autonomy_v1 import event_scenarios as ES
class EventCardDateMirror(unittest.TestCase):
 def test_display_ranges_match_engine_snapshot(self):
  cards=json.loads((VIEWER/'static/event_scenario_options.json').read_text())['events']
  for c in cards:
   if not c.get('event_card_id'):continue
   s=ES.snapshot(dict(event_card_id=c['event_card_id'],**c.get('scenario_defaults',{})),c['start_date'],'stay_1')
   self.assertEqual(c['source_date_range'],s['source_date_range'],c['id']);self.assertEqual(c['weekdays'],s['weekdays'],c['id'])
   self.assertTrue(ES.active(s,c['start_date']),c['id'])
   self.assertFalse(ES.active(s,'2026-11-20'),c['id'])
if __name__=='__main__':unittest.main()
