"""CL-1025-37 P6 — 하단 시연 챕터 바 삭제 · 고객흐름 수동 시작 · 체류 단계 순서(정적 검사). 브라우저 검증은 별도 스크립트."""
import re
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "static"


class CL37P6UI(unittest.TestCase):
    def test_no_bottom_chapter_bar(self):
        js = (S / "demo_story.js").read_text(encoding="utf-8")
        self.assertNotIn('id="dsNext"', js)
        self.assertNotIn('class="ds-ch', js)
        self.assertNotIn('id="dsTog"', js)
        css = (S / "demo_story.css").read_text(encoding="utf-8")
        self.assertIn("#dsBar { display: none !important; }", css)

    def test_no_auto_run_in_story_or_entry(self):
        js = (S / "demo_story.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"agRun\(\)")
        self.assertNotRegex(js, r"agPlayFrom\(|agPlayManyTime\(")
        ag = (S / "agent.js").read_text(encoding="utf-8")
        self.assertIn('one: null,', ag)
        self.assertNotIn("agEmpty(); agRun(); return;", ag)

    def test_visit_duration_order_replaces_internal_phase_selector(self):
        ag = (S / "agent.js").read_text(encoding="utf-8")
        m = re.search(r'<select id="agDuration".*?</select>', ag)
        self.assertIsNotNone(m)
        order = re.findall(r'<option value="(\w+)"', m.group(0))
        self.assertEqual(order, ["day_visit", "stay_1", "stay_2", "stay_3"])


if __name__ == "__main__":
    unittest.main()
