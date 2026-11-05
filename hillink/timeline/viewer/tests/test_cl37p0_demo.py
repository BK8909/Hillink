"""CL-1025-37 P0 — 시연 저장 스토리 자료 정합(서버 없이)."""
import hashlib, json, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
D = HERE / "static" / "demo_story"


class Cl37P0DemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads((D / "flow_fixture_v1.json").read_text(encoding="utf-8"))
        cls.story = json.loads((D / "story_v1.json").read_text(encoding="utf-8"))
        cls.gal = {c["card_id"]: c for c in json.loads((HERE / "static" / "persona_gallery" / "gallery.json").read_text(encoding="utf-8"))["cards"]}

    def test_fixture_keys_match_ui_request_shape(self):
        for k, v in self.fx["entries"].items():
            q = json.loads(k)
            self.assertEqual(sorted(q), ["event", "intervention", "mode", "observe", "personas", "product_levers", "seed", "visit_override"])
            self.assertEqual(q["personas"], sorted(q["personas"]))
            self.assertEqual(k, json.dumps(q, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
            self.assertTrue(set(q["personas"]) <= set(self.fx["personas"]))   # 실행 허용 11명만
            self.assertEqual(hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), self.fx["entry_sha"][k])
            self.assertNotIn("error", v)

    def test_story_steps_point_to_real_data(self):
        ids = [s["id"] for s in self.story["steps"]]
        self.assertEqual(len(ids), len(set(ids)))
        for s in self.story["steps"]:
            v = s["view"]
            if v["m"] == "flow":
                k = json.dumps({"event": bool(v["e"]), "intervention": "none", "mode": "one", "observe": "day", "personas": [v["p"]], "product_levers": {}, "seed": 0, "visit_override": None}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                self.assertIn(k, self.fx["entries"])
                if v.get("turn"):
                    self.assertIn(v["turn"], [r["turn"] for r in self.fx["entries"][k]["runs"]])
            if v["m"] == "draft":
                self.assertIn(v["card"], self.gal)
                self.assertIn(v["card"], self.story["observations"])
            for kd in s["kinds"]:
                self.assertIn(kd, self.story["legend"])

    def test_story_observations_not_engine_runnable(self):
        for cid, ob in self.story["observations"].items():
            self.assertFalse(self.gal[cid]["engine_eligible"])
            self.assertIn("NOT_RUN_SECOND_CONTRACT_REQUIRED", ob["engine"])
        s = json.dumps(self.story, ensure_ascii=False)
        self.assertNotIn("http", s)

    def test_public_mode_blocks_demo_story(self):
        src = (HERE / "app.py").read_text(encoding="utf-8")
        self.assertIn('(STATIC / "demo_story") in f.parents', src)


if __name__ == "__main__":
    unittest.main()
