"""CL-37 L5 소비 원장 — 같은 거래 내역에서 영수증 · 일별 · 체류 전체 · L4~L1 합계가 맞고, 객실은 확정 합계에 들어가지 않는다."""
import csv, json, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


class LedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        r = subprocess.run([sys.executable, str(HERE / "ledger_l5.py"), "--out", str(cls.d)], capture_output=True, text=True, timeout=600, cwd=HERE)
        cls.rc = r.returncode
        cls.chk = json.loads((cls.d / "CHECKS.json").read_text(encoding="utf-8"))
        cls.rows = list(csv.DictReader((cls.d / "L5_LEDGER_11.csv").open(encoding="utf-8-sig")))

    def test_all_sums(self):
        self.assertEqual(self.rc, 0)
        self.assertTrue(self.chk["all_pass"], self.chk["fail"])
        self.assertGreaterEqual(self.chk["checks_total"], 100)

    def test_room_not_confirmed(self):
        rooms = [r for r in self.rows if r["장면"] == "room_night"]
        self.assertTrue(rooms)
        for r in rooms:
            self.assertEqual(r["상태"], "금액 미확인"); self.assertEqual(int(r["확정 결제액"]), 0); self.assertEqual(int(r["결제액"]), 0)

    def test_included_is_zero(self):
        for r in self.rows:
            if r["상태"] in ("포함", "무료", "금액 미확인"):
                self.assertEqual(int(r["확정 결제액"]), 0)

    def test_compat_schema(self):
        h = next(csv.reader((self.d / "L5_COMPAT_ONTOLOGY_FORMAT.csv").open(encoding="utf-8-sig")))
        import importlib.util
        src = (HERE / "engine.py").read_text(encoding="utf-8")
        self.assertIn('L5_COLS = ' + json.dumps(h, ensure_ascii=False).replace('", "', '", "'), src.replace("'", '"'))


if __name__ == "__main__":
    unittest.main()
