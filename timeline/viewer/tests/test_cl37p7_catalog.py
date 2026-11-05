"""CL-37 P7 — 라이브러리 열람 카탈로그: 실행 11명과 분리 · 비공개 정보 없음 · 1:1 조인 · 정적 경로 차단."""
import json, re, unittest
from pathlib import Path

ST = Path(__file__).resolve().parent.parent / "static"


class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads((ST / "persona_catalog.json").read_text(encoding="utf-8"))
        cls.pub = json.loads((ST / "persona_publish.json").read_text(encoding="utf-8"))
        cls.led = {p["id"]: p for p in json.loads((ST / "persona_library.json").read_text(encoding="utf-8"))["personas"]}

    def test_separate_from_runnable(self):
        run = set(self.pub["demo_display"])
        self.assertEqual(len(run), 11)
        for c in self.cat["customers"]:
            self.assertNotIn(c["id"], run)
            self.assertFalse(c["engine_runnable"])
            self.assertTrue(c["catalogue_visible"])

    def test_unique_join(self):
        C = self.cat["customers"]
        self.assertEqual(len({c["id"] for c in C}), len(C))
        self.assertEqual(len({c["scene"] for c in C}), len(C))
        self.assertEqual(len({c["no"] for c in C}), len(C))
        for c in C:
            self.assertIn(c["id"], self.led)
        srcs = [c["image"]["src"] for c in C if c["image"]]
        self.assertEqual(len(srcs), len(set(srcs)))
        self.assertEqual(self.cat["counts"]["catalogue"] + self.cat["counts"]["excluded_ledger"] + self.cat["counts"]["runnable"], self.cat["counts"]["ledger"])

    def test_no_private_fields(self):
        t = json.dumps(self.cat, ensure_ascii=False)
        for pat in (r"WH-\d", r"RV-\d", r"https?://", r"owner", r"슬기|\(안\)", r"블로그", r"_PRIVATE"):
            self.assertIsNone(re.search(pat, t), pat)
        sens = re.compile(r"아이|자녀|딸|아들|유아|첫째|둘째|건강|병원|몸이|몸보신|학생")
        for c in self.cat["customers"]:
            for s in [c.get("summary") or "", c.get("visit") or "", *c.get("notes", [])]:
                self.assertIsNone(sens.search(s), s)

    def test_static_denied(self):
        src = (ST.parent / "app.py").read_text(encoding="utf-8")
        self.assertRegex(src, r'STATIC_DENY = \([^)]*"persona_catalog\.json"')


if __name__ == "__main__":
    unittest.main()
