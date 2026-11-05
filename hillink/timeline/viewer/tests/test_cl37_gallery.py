"""CL-1025-37 — 시각 초안 갤러리 자료 · 접근 경계(저장소 안 자료만 · 서버 없이)."""
import hashlib, json, os, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
G = HERE / "static" / "persona_gallery"
ALLOW11 = {"A01", "A02", "A03", "A04", "A05", "A07", "A08", "A10", "blog41", "blog42", "blog43"}


class Cl37GalleryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((G / "gallery.json").read_text(encoding="utf-8"))
        cls.cards = cls.doc["cards"]

    def test_65_unique_cards_and_images(self):
        self.assertEqual(len(self.cards), 65)
        self.assertEqual(len({c["card_id"] for c in self.cards}), 65)
        imgs = [c["image"] for c in self.cards if c["image"]]
        self.assertEqual(len({i["src"] for i in imgs}), len(imgs))
        self.assertEqual(len({i["sha256"] for i in imgs}), len(imgs))
        for i in imgs:   # 파일 실재 + 바이트 SHA
            f = HERE / i["src"].lstrip("/")
            self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), i["sha256"])

    def test_not_approved_not_runnable(self):
        for c in self.cards:
            self.assertFalse(c["engine_eligible"]); self.assertFalse(c["publish_approved"]); self.assertFalse(c["profile_linked"])
            self.assertEqual(c["avatar"]["status"], "AVATAR_REVIEW_PENDING"); self.assertIsNone(c["avatar"]["runtime_key"])
            if c["image"]:
                self.assertFalse(c["image"]["human_approved"])
            self.assertNotIn(c["display_id"], ALLOW11)

    def test_no_source_ids_on_screen_data(self):
        s = json.dumps(self.doc, ensure_ascii=False)
        self.assertNotIn("WH-", s); self.assertNotIn("-F0", s); self.assertNotIn("http", s)
        lib = {p["id"] for p in json.loads((HERE / "static" / "persona_library.json").read_text(encoding="utf-8"))["personas"]}
        for c in self.cards:
            self.assertTrue(c["display_id"] is None or c["display_id"] in lib)

    def test_placeholder_for_external_context(self):
        ph = [c for c in self.cards if c["image"] is None]
        self.assertEqual(len(ph), 2)
        self.assertTrue(all(c["image_withheld"] and c["fact_review"] == "NEEDS_SEMANTIC_REVIEW" for c in ph))

    def test_static_denied_and_public_block(self):
        import app
        self.assertTrue(app.static_denied("gallery.json"))
        from unittest.mock import patch
        handler = object.__new__(app.H)
        handler.path = '/static/persona_gallery/gallery.json'
        handler.send = lambda status, body, *args: (status, body)
        with patch.object(app, 'DEPLOY', 'public'), patch.object(app.boundary, 'guard'):
            self.assertEqual(handler.do_GET()[0], 404)
            handler.path = '/api/library/gallery'
            status, body = handler.do_GET()
            self.assertEqual(status, 200)
            self.assertEqual(body, {'cards': [], 'public_blocked': True})


if __name__ == "__main__":
    unittest.main()
