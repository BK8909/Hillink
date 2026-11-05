"""CL-1024-17 운영 실험 어댑터 시험 — python3 -m unittest tests.test_opx_adapter (timeline/viewer 에서)
로컬 전용 프로필(turn_personas_ext.local.json)이 없으면 건너뜀."""
import json, subprocess, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
LOCAL = HERE.parents[1] / "timeline/experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json"


def run(**kw):
    r = subprocess.run([sys.executable, str(HERE / "opx_run.py")], input=json.dumps({"op": "run", "date": "2026-10-27", "start_time": "18:30", **kw}),
                       capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout)


@unittest.skipUnless(LOCAL.exists(), "로컬 전용 프로필 없음")
class OpxAdapter(unittest.TestCase):
    def counts(self, d): return {v["venue_id"]: v["scenario_selected_count"] for v in d["venue_aggregates"]}

    def test_four_baselines(self):
        for amt, want in {0: (11, 0), 10000: (11, 0), 20000: (9, 2), 40000: (8, 3)}.items():
            c = self.counts(run(discount_amount=amt))
            self.assertEqual((c.get("GEUMRYONG", 0), c.get("THE_BUFFET", 0)), want, amt)

    def test_arbitrary_value_recomputed(self):
        d = run(discount_amount=15000)
        self.assertTrue(d["adapter"]["engine_called"])
        self.assertEqual(self.counts(d), {"GEUMRYONG": 10, "THE_BUFFET": 1})

    def test_rejects_injection_and_bad_values(self):
        for kw in ({"selected_persona_ids": ["N08"]}, {"offer_overrides": {}}, {"discount_amount": -1}, {"discount_amount": 250000}, {"target_offer": "PH_COUPLE_SET"}):
            self.assertEqual(run(**kw)["experiment"]["run_status"], "INVALID_REQUEST", kw)

    def test_no_private_strings(self):
        s = json.dumps(run(discount_amount=20000), ensure_ascii=False)
        for bad in ("/private/", "/Users/", "/home/", ".local.json", "blog.naver"):
            self.assertNotIn(bad, s)


if __name__ == "__main__":
    unittest.main()


def test_integrity_failure_never_imports_engine():
    import io
    from contextlib import redirect_stdout
    from unittest.mock import patch
    sys.path.insert(0,str(HERE))
    import opx_run
    for invalid in (False,True):
        request=dict(op='run',date='2026-10-27',start_time='18:30',discount_amount=-1 if invalid else 0)
        output=io.StringIO()
        with patch.object(opx_run,'integrity',return_value={'ok':False,'engine_head':'FIXTURE'}),patch.object(opx_run,'_service',side_effect=AssertionError('sealed engine must not be imported')),patch.object(sys,'stdin',io.StringIO(json.dumps(request))),redirect_stdout(output):
            assert opx_run.main()==0
        assert json.loads(output.getvalue())['experiment']['run_status']==('INVALID_REQUEST' if invalid else 'ENGINE_SHA_MISMATCH')
