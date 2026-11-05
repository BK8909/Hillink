"""CL-1025-36 — 승인 범위 sidecar + 안전 adapter 계약 시험(합성 · 비식별 고정 자료).
python3 -m unittest tests.test_cl36_contract (timeline/viewer 에서)"""
import csv, importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
FIXD = HERE / "tests" / "fixtures" / "lp16_synthetic"
sys.path.insert(0, str(HERE / "tools"))
import approval_sidecar_qa as S  # noqa: E402
sys.path.insert(0, str(HERE / "tests"))
import _sidecar_test_support as TS  # noqa: E402

BCOLS = ["source_profile_id", "fact_id", "event_id", "behavior_occurrence", "direct_walkerhill_experience", "preference_direction", "preference_value", "applicable_activities"]
BOUND = [("F001", "OBSERVED", "YES", "PREFERENCE_SUPPORT", "VISTA_STAY"), ("F002", "OBSERVED", "YES", "PREFERENCE_SUPPORT", "SKYARD"),
         ("F003", "OTHER_CONTEXT", "NO_EXTERNAL_CONTEXT", "DIRECTION_UNKNOWN", "EXTERNAL_BUFFET"), ("F004", "OTHER_CONTEXT", "NO_EXTERNAL_CONTEXT", "DIRECTION_UNKNOWN", "EXTERNAL_SNACK"),
         ("F005", "NOT_DONE", "YES", "DIRECTION_UNKNOWN", "POOL_NOT_USED"), ("F006", "CANCELED_CLOSED", "YES", "DIRECTION_UNKNOWN", "THEATRE_OF_LIGHT"),
         ("F007", "OBSERVED", "YES", "PREFERENCE_SUPPORT", "CAFE|ALTERNATIVE_ACTIVITY")]
ACOLS = ["source_profile_id", "fact_id", "human_disposition", "approval_scope", "strength_status", "engine_input_status"]
APPR = [("F002", "APPROVE_DIRECTION_NO_STRENGTH", "SKYARD_CONTEXTUAL_POSITIVE"), ("F005", "APPROVE_OBSERVATION_ONLY", "POOL_NOT_DONE_CONTEXT"),
        ("F006", "APPROVE_OBSERVATION_ONLY", "CANCELED_CLOSED_NONVISIT"), ("F007", "APPROVE_OBSERVATION_ONLY", "ALTERNATIVE_CAFE_VENUE_UNKNOWN"),
        ("F001", "HOLD_UNKNOWN", "REVIEWED_HOLD")]


def _manifest(b, a, src=FIXD):
    """테스트 전용 매니페스트(합성 입력의 SHA) — 운영 모듈에는 주입 경로가 없고 tests/_sidecar_test_support 하위 클래스로만 사용."""
    return TS.test_manifest(b, a, src)


def _write(d, bound=BOUND, appr=APPR, strength="NOT_ASSIGNED"):
    b, a = Path(d) / "b.csv", Path(d) / "a.csv"
    with open(b, "w", newline="") as f:
        w = csv.writer(f); w.writerow(BCOLS)
        for fid, occ, direct, pdir, act in bound:
            w.writerow(["WH-90001", f"WH-90001-{fid}", f"WH-90001-E{fid[1:]}", occ, direct, pdir, "UNKNOWN_NOT_ASSIGNED", act])
    with open(a, "w", newline="") as f:
        w = csv.writer(f); w.writerow(ACOLS)
        for fid, disp, scope in appr:
            w.writerow(["WH-90001", f"WH-90001-{fid}", disp, scope, strength, "PENDING_CODEX_CONTRACT"])
    return b, a


class Sidecar(unittest.TestCase):
    def test_provenance_lossless_and_states(self):
        with tempfile.TemporaryDirectory() as d:
            b, a = _write(d); sc = S.build_sidecar(b, a, FIXD, _bind=TS.bind_of(_manifest(b, a)))
        rows = {r["fact_id"]: r for r in sc["WH-90001"]}
        self.assertEqual(len(rows), 7)                                                   # 묵살 없이 전부
        st = {k[-4:]: v["contract_state"] for k, v in rows.items()}
        self.assertEqual(st, {"F001": "HOLD_UNKNOWN", "F002": "DIRECTION_CONTEXT_ONLY", "F003": "UNREVIEWED", "F004": "UNREVIEWED",
                              "F005": "OBSERVATION_ONLY", "F006": "OBSERVATION_ONLY", "F007": "OBSERVATION_ONLY"})
        for r in rows.values():
            self.assertNotIn("polarity", r); self.assertEqual((r["strength"], r["score_contribution"]), ("NOT_ASSIGNED", 0))
            self.assertTrue(r["anchor_sha256"] and r["post_id"] and r["event_id"])
        self.assertEqual(rows["WH-90001-F006"]["behavior_occurrence"], "CANCELED_CLOSED")

    def test_fail_closed_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ([("F002", "neutral", "x")], [("F002", "positive", "x")], [("F002", "APPROVE_STRONG", "x")], [("F099", "APPROVE_OBSERVATION_ONLY", "x")],
                        [("F002", "APPROVE_OBSERVATION_ONLY", "x"), ("F002", "APPROVE_OBSERVATION_ONLY", "x")]):
                with self.assertRaises(S.ContractError, msg=str(bad)):
                    b, a = _write(d, appr=bad); S.build_sidecar(b, a, _bind=TS.bind_of(_manifest(b, a)))
            with self.assertRaises(S.ContractError):
                b, a = _write(d, strength="0.5"); S.build_sidecar(b, a, _bind=TS.bind_of(_manifest(b, a)))
            b, a = _write(d); sc = S.build_sidecar(b, a, _bind=TS.bind_of(_manifest(b, a)))
        for mut in (dict(contract_state="neutral"), dict(contract_state="POSITIVE_PREFERENCE"), dict(polarity="neutral"), dict(strength=0.5), dict(score_contribution=0.1)):
            t = json.loads(json.dumps(sc)); t["WH-90001"][0].update(mut)
            with self.assertRaises(S.ContractError, msg=str(mut)):
                S.validate_sidecar(t)

    def test_neutral_leak_reproduced_then_blocked(self):
        spec = importlib.util.spec_from_file_location("lp16c36", HERE / "tools" / "lp16_candidate_convert_qa.py"); C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
        _, _, t0 = C.run(FIXD / "WH-90001", True)                                       # 종전 변환(극성 neutral 합성)
        leaked = {e["fact_id"] for f in t0["facets"].values() for e in f.get("evidence") or []} | {x for xs in t0["venues"].values() for v in xs for x in v["fact_ids"]}
        self.assertIn("WH-90001-F001", leaked)                                           # 보류(HOLD) 사실이 성향/업장 근거로 새는 것을 재현
        with tempfile.TemporaryDirectory() as d:
            b, a = _write(d); M = _manifest(b, a); sc = S.build_sidecar(b, a, FIXD, _bind=TS.bind_of(M)); T = TS.TestOnlyTrustedInputs(b, a, FIXD, M)
        p, lib, obs = S.consumption(sc["WH-90001"], "QA16_90001", "친구 모임", "friends", trusted=T, source_profile_id="WH-90001")
        tr = p["traits"]
        self.assertEqual(sum(len(f.get("evidence") or []) for f in tr["facets"].values()), 0)
        self.assertFalse(any(tr["venues"].values()) if tr.get("venues") else False)
        self.assertEqual((lib["engine"]["facts"], lib["wh_events"], tr.get("evidence_index") or {}), ({}, [], {}))
        self.assertEqual(sorted(o["fact_id"][-4:] for o in obs), ["F002", "F005", "F006", "F007"])   # HOLD · UNREVIEWED 는 출력에도 없음
        self.assertTrue(all(o["score_contribution"] == 0 for o in obs))

    def test_flow_isolated_no_attribution(self):
        with tempfile.TemporaryDirectory() as d:
            b, a = _write(d); M = _manifest(b, a); sc = S.build_sidecar(b, a, FIXD, _bind=TS.bind_of(M))
            mp = Path(d) / "m.json"; mp.write_text(json.dumps(M), encoding="utf-8")
            sp = Path(d) / "sc.json"; sp.write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
            code = f"""
import sys, json, re; sys.path.insert(0, {str(HERE / 'tools')!r})
import approval_sidecar_qa as S, lp16_flow_qa as Q
sys.path.insert(0, {str(HERE / 'tests')!r}); import _sidecar_test_support as TS
ids, OBS = S.install_into_flow(json.load(open({str(sp)!r})), TS.TestOnlyTrustedInputs({str(b)!r}, {str(a)!r}, {str(FIXD)!r}, json.load(open({str(mp)!r}))))
r = Q.flow({{"personas": ids, "mode": "one", "seed": 0}}); s = json.dumps(r, ensure_ascii=False)
cust = [c for run in r.get("runs") or [] for c in run["customers"]]
print(json.dumps(dict(ids=ids, err=r.get("error"), cited=sorted(set(re.findall(r"WH-90001-F\\d+", s))), avoid=[a for c in cust for a in c.get("avoid") or []],
     review=sum(1 for x in r["plans"][ids[0]]["scenes"] if x["layer"] == "review"), obs=[o["fact_id"] for o in OBS[ids[0]]])))"""
            out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=600)
            o = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertIsNone(o["err"]); self.assertEqual(o["ids"], ["QA16_90001"])
        self.assertEqual(o["cited"], []); self.assertEqual(o["avoid"], []); self.assertEqual(o["review"], 0)   # 점수 · 근거 · 회피 귀속 0
        self.assertNotIn("WH-90001-F001", o["obs"])
