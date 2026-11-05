"""CL-1025-36c — CD-14B HOLD 결함(계보 필드 post_id · anchor_sha256 · applicable_activities 변조 수락 · 입력 SHA 미고정) 재현 · 차단 시험.
합성 · 비식별 고정 자료. python3 -m unittest tests.test_cl36c_lineage (timeline/viewer 에서)"""
import json, shutil, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tools")); sys.path.insert(0, str(HERE / "tests"))
import approval_sidecar_qa as S  # noqa: E402
sys.path.insert(0, str(HERE / "tests"))
import _sidecar_test_support as TS  # noqa: E402
from test_cl36_contract import _write, _manifest, FIXD, APPR, BOUND  # noqa: E402


class Lineage(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); d = Path(self.td.name)
        self.b, self.a = _write(d)
        self.src = d / "src"; shutil.copytree(FIXD, self.src)                          # 원본 사실 사본(변조 시험용)
        self.M = _manifest(self.b, self.a, self.src)                                     # 승인된 고정 매니페스트(시험 시점 원본 기준)
        self.sc = S.build_sidecar(self.b, self.a, self.src, _bind=TS.bind_of(self.M))
        self.T = TS.TestOnlyTrustedInputs(self.b, self.a, self.src, self.M)

    def tearDown(self):
        self.td.cleanup()

    def rows(self):
        return json.loads(json.dumps(self.sc["WH-90001"]))

    def consume(self, rows, T=None):
        return S.consumption(rows, "QA16_90001", "친구 모임", "friends", trusted=T or self.T, source_profile_id="WH-90001")

    def test_normal_passes(self):
        p, lib, obs = self.consume(self.rows())
        self.assertEqual(sorted(o["fact_id"][-4:] for o in obs), ["F002", "F005", "F006", "F007"])

    def test_each_lineage_field_mutation_blocked(self):
        for field, val in (("post_id", "WH-90001_P999"), ("anchor_sha256", ["0" * 64]), ("applicable_activities", ["THE_BUFFET"])):
            for i in range(len(self.rows())):
                r = self.rows(); r[i][field] = val
                with self.assertRaises(S.ContractError, msg=f"{field} row{i}"):
                    self.consume(r)

    def test_all_three_at_once_and_cross_swap_blocked(self):
        r = self.rows(); r[0].update(post_id="X", anchor_sha256=["1" * 64], applicable_activities=["POOL"])
        with self.assertRaises(S.ContractError):
            self.consume(r)
        r = self.rows(); r[0]["anchor_sha256"], r[1]["anchor_sha256"] = r[1]["anchor_sha256"], r[0]["anchor_sha256"]
        with self.assertRaises(S.ContractError):
            self.consume(r)                                                              # 앵커 교차 바꾸기
        r = self.rows(); r[0]["fact_id"], r[1]["fact_id"] = r[1]["fact_id"], r[0]["fact_id"]
        with self.assertRaises(S.ContractError):
            self.consume(r)                                                              # ID 교차 바꾸기

    def _tamper_source(self):
        fe = self.src / "WH-90001/candidate/facts_events_evidence.json"
        d = json.loads(fe.read_text(encoding="utf-8")); d["facts"][0]["anchors"][0]["anchor_sha256"] = "2" * 64; d["facts"][0]["post_id"] = "WH-90001_P777"
        fe.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    def test_source_only_tamper_blocked_by_pinned_manifest(self):
        self._tamper_source()
        with self.assertRaises(S.ContractError):
            TS.TestOnlyTrustedInputs(self.b, self.a, self.src, self.M)                    # 원본만 덮어쓰기 → 고정 SHA 불일치

    def test_source_plus_sidecar_tamper_blocked(self):
        self._tamper_source()
        forged = S.build_sidecar(self.b, self.a, self.src, _bind=TS.bind_of(self.M))["WH-90001"]  # 변조 원본으로 sidecar 도 일관되게 재생성
        with self.assertRaises(S.ContractError):
            TS.TestOnlyTrustedInputs(self.b, self.a, self.src, self.M)
        with self.assertRaises(S.ContractError):
            self.consume(forged)                                                         # 기존 신뢰 입력과도 불일치

    def test_approval_or_boundary_swap_blocked(self):
        with tempfile.TemporaryDirectory() as d2:
            b2, a2 = _write(d2, bound=[("F003", "OBSERVED", "YES", "PREFERENCE_SUPPORT", "THE_BUFFET") if x[0] == "F003" else x for x in BOUND], appr=APPR[:-1])
            with self.assertRaises(S.ContractError):
                TS.TestOnlyTrustedInputs(self.b, a2, self.src, self.M)                    # 승인표 교체
            with self.assertRaises(S.ContractError):
                TS.TestOnlyTrustedInputs(b2, self.a, self.src, self.M)                    # 정본 교체(외부 맥락 사실을 워커힐 관측으로 바꾼 정본)
            foreign = S.build_sidecar(b2, a2, self.src, _bind=TS.bind_of(_manifest(b2, a2, self.src)))["WH-90001"]
        with self.assertRaises(S.ContractError):
            self.consume(foreign)                                                        # 다른 매니페스트로 만든 sidecar

    def test_sourceless_and_injection_blocked(self):
        with self.assertRaises(S.ContractError):
            TS.TestOnlyTrustedInputs(self.b, self.a, None, self.M)                         # source 없는 소비
        for mut in (dict(polarity="neutral"), dict(strength=0.4), dict(contract_state="OBSERVATION_ONLY")):
            r = self.rows(); i = next(k for k, x in enumerate(r) if x["contract_state"] == "HOLD_UNKNOWN"); r[i].update(mut)
            with self.assertRaises(S.ContractError, msg=str(mut)):
                self.consume(r)
        with self.assertRaises(S.ContractError):
            self.consume(self.rows()[1:])                                                # 행 누락

    def test_default_manifest_is_repo_pinned(self):
        m = S.load_pinned_manifest()
        self.assertEqual(m["approval_csv"], "797b1e99eb1a0a4a9ff0b8f817c0ed9b71eff656e2272c9bc21e6acc273eb670")
        self.assertEqual(m["boundary_csv"], "5c9bec5b067375fe4f400b8f2c6907e4e8a29bb316d1b38abe32075855f33e71")
        self.assertEqual(len(m["source_facts"]), 5)
        with self.assertRaises(S.ContractError):
            S.TrustedInputs(self.b, self.a, self.src)                                    # 합성 입력은 기본(실데이터) 매니페스트와 불일치 → 중단
