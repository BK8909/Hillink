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
        if r.returncode and 'E_FLOW_INPUT_MISSING' in r.stderr:
            raise unittest.SkipTest('Approved turn_personas_ext.local.json required for legacy 11-person ledger')
        if r.returncode and not (cls.d / 'CHECKS.json').exists():
            raise AssertionError('ledger CLI failed before checks: ' + r.stderr[-500:])
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
            self.assertEqual(r["순매출"], "")
            self.assertEqual(r["순매출 상태"], "세금·회계 기준 미확인 · 미계산")

    def test_net_revenue_is_not_inferred_from_unknown_tax_basis(self):
        charged = [r for r in self.rows if r["상태"] == "실결제"]
        self.assertTrue(charged)
        self.assertTrue(all(r["순매출"] == "" for r in charged))
        self.assertTrue(all(r["순매출 상태"] == "세금·회계 기준 미확인 · 미계산" for r in charged))
        p = next(r for r in charged if r["L3 업장"] == "피자힐")
        self.assertEqual(int(p["확정 결제액"]), int(p["결제액"]))  # 장면 총액을 인원수로 다시 곱하지 않는다
        self.assertEqual(p["이용 인원"], "4")
        self.assertEqual(p["판매 수량"], "4")

    def test_included_is_zero(self):
        for r in self.rows:
            if r["상태"] in ("포함", "무료", "금액 미확인"):
                self.assertEqual(int(r["확정 결제액"]), 0)

    def test_hierarchy_export_does_not_mix_units_or_infer_net(self):
        with (self.d / "AGG_L1.csv").open(encoding="utf-8-sig", newline="") as f:
            out = list(csv.DictReader(f))
        self.assertIn("원장 수량(역할·단위별)", out[0])
        self.assertIn("순매출(미계산 · 세금 기준 미확인)", out[0])
        self.assertTrue(all(row["순매출(미계산 · 세금 기준 미확인)"] == "" for row in out))

    def test_compat_schema(self):
        h = next(csv.reader((self.d / "L5_COMPAT_ONTOLOGY_FORMAT.csv").open(encoding="utf-8-sig")))
        import importlib.util
        src = (HERE / "engine.py").read_text(encoding="utf-8")
        self.assertIn('L5_COLS = ' + json.dumps(h, ensure_ascii=False).replace('", "', '", "'), src.replace("'", '"'))


if __name__ == "__main__":
    unittest.main()
