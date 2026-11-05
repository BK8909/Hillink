"""CL-1025-37 P2/P3 — 최종 시연 스토리(v3) · 표시 카드 번호 레지스트리 · 원문 링크 권한 경계(서버 없이 정적 검사)."""
import json, re, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
S = HERE / "static"
ALLOW11 = ["A01", "A02", "A03", "A04", "A05", "A07", "A08", "A10", "blog41", "blog42", "blog43"]


def registry():
    t = (S / "display_registry.js").read_text(encoding="utf-8")
    return json.loads(t[t.index("{"):t.rindex("}") + 1])


class Cl37P3Test(unittest.TestCase):
    def test_story_v3_product_flow(self):
        d = json.loads((S / "demo_story" / "story_v3.json").read_text(encoding="utf-8"))
        ids = [s["id"] for s in d["steps"]]
        self.assertEqual(ids, ["L1", "L2", "P1", "P2", "F1", "F2", "M1", "M2", "M3", "M4", "O1", "O2", "B1", "B2", "B3"])
        self.assertEqual(d["default_step"], "L1")
        self.assertEqual(d["steps"][0]["view"], {"m": "lib"})   # 첫 화면 = 실제 라이브러리(안내 카드 없음)
        self.assertFalse(any(s["view"].get("m") == "card" for s in d["steps"]))
        self.assertEqual(len({s["ch"] for s in d["steps"]}), 6)
        txt = json.dumps(d, ensure_ascii=False)
        self.assertNotIn("WH-", txt); self.assertNotIn("http", txt)
        for s in d["steps"]:   # 화면 문구에 기존 실행 ID 없음(표시 번호만)
            self.assertIsNone(re.search(r"\b(A0[1-9]|A10)\b|blog4[1-3]", s["title"] + s["caption"]), s["id"])
        self.assertEqual(d["fixture"], "/static/demo_story/flow_fixture_v1.json")

    def test_older_stories_preserved(self):
        for v in ("story_v1.json", "story_v2.json"):
            self.assertTrue((S / "demo_story" / v).exists())

    def test_display_registry_fixed_and_not_pid(self):
        r = registry()
        E = r["entries"]
        self.assertEqual(len(r["legacy_entries"]), 76)
        self.assertEqual([E[p]["no"] for p in ALLOW11], [f"{i:04d}" for i in range(1, 12)])
        # Visual aliases and runtime identities share a number only for the same customer.
        identities = {}
        for key, entry in E.items():
            canonical = entry.get("canonical_customer_id", key)
            self.assertIn(canonical, E)
            self.assertEqual(entry["no"], E[canonical]["no"])
            self.assertEqual(identities.setdefault(entry["no"], canonical), canonical)
        for key in r["legacy_entries"]:
            self.assertIn(key, E)
        self.assertTrue(all(e["p_id"] is None for e in E.values()))   # P-ID 계약 미통과 — 정식 번호 발급 0
        self.assertEqual(r["p_id_contract"], "WAITING_FOR_ID_CONTRACT")
        for e in E.values():
            if e["party_origin"] == "UNKNOWN":
                self.assertIsNone(e["party"])
        # Internal customer IDs are allowed in routing data; dno() renders only numbers.
        self.assertTrue(all(re.fullmatch(r"[0-9]{4}", e["no"]) for e in E.values()))

    def test_links_gate_is_server_only(self):
        lib = (S / "library.js").read_text(encoding="utf-8")
        self.assertIn("const libLinksAllowed = () => true;", lib)
        app = (HERE / "app.py").read_text(encoding="utf-8")
        self.assertIn('if not reviewer_ok(self):\n                    return self.send(403', app)
        self.assertIn('return REVIEWER_LOCAL and DEPLOY != "public"', app)

    def test_display_number_not_engine_input(self):
        for f in ("demo_story.js", "agent.js", "behavior.js"):
            t = (S / f).read_text(encoding="utf-8")
            self.assertNotRegex(t, r"personas:\s*\[[^\]]*dno\(")   # 엔진 요청에 표시 번호를 넣지 않음


if __name__ == "__main__":
    unittest.main()
