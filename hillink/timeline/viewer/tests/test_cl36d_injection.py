"""CL-1025-36d — CD-14C HOLD 결함(호출자 manifest 주입으로 변조 원본 재핀) 재현 · 차단 시험(합성 · 비식별).
python3 -m unittest tests.test_cl36d_injection (timeline/viewer 에서)"""
import inspect, json, shutil, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tools")); sys.path.insert(0, str(HERE / "tests"))
import approval_sidecar_qa as S  # noqa: E402
import _sidecar_test_support as TS  # noqa: E402
from test_cl36_contract import _write, FIXD  # noqa: E402


class ManifestInjection(unittest.TestCase):
    def test_production_api_has_no_manifest_parameter(self):
        for fn in (S.TrustedInputs.__init__, S.consumption, S.install_into_flow, S.build_sidecar, S.load_pinned_manifest):
            self.assertNotIn("manifest", inspect.signature(fn).parameters, fn.__name__)
        self.assertFalse(hasattr(S, "load_manifest"))                                    # 이전(주입 가능) 로더 제거

    def test_cd14c_replay_tampered_source_plus_caller_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            b, a = _write(d); src = Path(d) / "src"; shutil.copytree(FIXD, src)
            fe = src / "WH-90001/candidate/facts_events_evidence.json"
            j = json.loads(fe.read_text(encoding="utf-8")); j["facts"][0]["post_id"] = "WH-90001_P777"; fe.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
            forged_manifest = TS.test_manifest(b, a, src)                               # 변조 원본 SHA 로 갱신한 위조 매니페스트
            with self.assertRaises(TypeError):
                S.TrustedInputs(b, a, src, manifest=forged_manifest)                      # 키워드 주입 불가
            with self.assertRaises(TypeError):
                S.TrustedInputs(b, a, src, forged_manifest)                               # 위치 인자 주입 불가
            with self.assertRaises(S.ContractError):
                S.TrustedInputs(b, a, src)                                                # 운영 경로는 고정 매니페스트만 → 거부

    def test_manifest_file_replaced_or_deleted(self):
        orig = S.PINNED_MANIFEST
        try:
            with tempfile.TemporaryDirectory() as d:
                m = json.loads(orig.read_text(encoding="utf-8")); m["approval_csv"] = "0" * 64
                fake = Path(d) / "approved_inputs_manifest_cl36c.json"; fake.write_text(json.dumps(m), encoding="utf-8")
                S.PINNED_MANIFEST = fake                                                  # 같은 위치의 파일이 교체된 상황 재현
                with self.assertRaises(S.ContractError):
                    S.load_pinned_manifest()
                S.PINNED_MANIFEST = Path(d) / "missing.json"                             # 삭제
                with self.assertRaises(S.ContractError):
                    S.load_pinned_manifest()
        finally:
            S.PINNED_MANIFEST = orig
        self.assertEqual(S.load_pinned_manifest()["approval_csv"], "797b1e99eb1a0a4a9ff0b8f817c0ed9b71eff656e2272c9bc21e6acc273eb670")

    def test_test_subclass_lives_only_in_tests(self):
        self.assertFalse(hasattr(S, "TestOnlyTrustedInputs"))
        self.assertTrue(TS.__file__.startswith(str(HERE / "tests")))


class AnchorAuditSchemas(unittest.TestCase):
    """두 원문 스키마(full_original_text_PRIVATE / body)를 모두 읽는지 · missing_body · true_mismatch 구분(합성 문장)."""
    def test_both_body_fields(self):
        import hashlib
        sys.path.insert(0, str(HERE / "tools")); import anchor_audit_qa as AA
        h = lambda s: hashlib.sha256(s.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            for sid, field in (("WH-90011", "full_original_text_PRIVATE"), ("WH-90012", "body")):
                p = Path(d) / sid / "private"; p.mkdir(parents=True)
                t = "합성 본문 가나다 조식 이용 문장 끝"; q = t[3:10]
                (p / "private_original_fulltext.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in (
                    {"post_id": f"{sid}_P1", field: t}, {"post_id": f"{sid}_P2", field: ""}, {"post_id": f"{sid}_P3", field: "다른 본문"})), encoding="utf-8")
                (p / "fact_evidence_origins_PRIVATE.json").write_text(json.dumps([
                    dict(fact_id=f"{sid}-F001", post_id=f"{sid}_P1", anchor_start=3, anchor_end=10, quote_PRIVATE=q, source_sha256=h(t), anchor_sha256=h(q)),
                    dict(fact_id=f"{sid}-F002", post_id=f"{sid}_P2", anchor_start=0, anchor_end=2, quote_PRIVATE="xx", source_sha256="0", anchor_sha256=h("xx")),
                    dict(fact_id=f"{sid}-F003", post_id=f"{sid}_P3", anchor_start=0, anchor_end=2, quote_PRIVATE="zz", source_sha256="0", anchor_sha256=h("zz"))], ensure_ascii=False), encoding="utf-8")
            res = {r["fact_id"]: r["status"] for r in AA.audit(d)}
        self.assertEqual(res, {"WH-90011-F001": "matching", "WH-90011-F002": "missing_body", "WH-90011-F003": "true_mismatch",
                               "WH-90012-F001": "matching", "WH-90012-F002": "missing_body", "WH-90012-F003": "true_mismatch"})
