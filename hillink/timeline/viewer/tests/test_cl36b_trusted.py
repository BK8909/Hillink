"""CL-1025-36b — CD-14 HOLD 결함(sidecar 상태만 바꿔 보류/미검토를 관측으로 노출) 재현 · 차단 시험(합성 · 비식별).
python3 -m unittest tests.test_cl36b_trusted (timeline/viewer 에서)"""
import json, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tools")); sys.path.insert(0, str(HERE / "tests"))
import approval_sidecar_qa as S  # noqa: E402
sys.path.insert(0, str(HERE / "tests"))
import _sidecar_test_support as TS  # noqa: E402
from test_cl36_contract import _write, _manifest, FIXD, APPR  # noqa: E402


class TrustedReverify(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.b, self.a = _write(self.td.name)
        self.M = _manifest(self.b, self.a)
        self.sc = S.build_sidecar(self.b, self.a, FIXD, _bind=TS.bind_of(self.M)); self.T = TS.TestOnlyTrustedInputs(self.b, self.a, FIXD, self.M)

    def tearDown(self):
        self.td.cleanup()

    def rows(self):
        return json.loads(json.dumps(self.sc["WH-90001"]))

    def consume(self, rows):
        return S.consumption(rows, "QA16_90001", "친구 모임", "friends", trusted=self.T, source_profile_id="WH-90001")

    def test_cd14_repro_hold_to_observation_blocked(self):
        r = self.rows(); i = next(k for k, x in enumerate(r) if x["contract_state"] == "HOLD_UNKNOWN")
        r[i]["contract_state"] = "OBSERVATION_ONLY"                                   # CD-14 재현: 상태만 위조
        with self.assertRaises(S.ContractError):
            self.consume(r)
        r[i].update(human_disposition="APPROVE_OBSERVATION_ONLY", approval_scope="FORGED")   # 처분 · 범위까지 맞춰 위조해도
        with self.assertRaises(S.ContractError):
            self.consume(r)

    def test_unreviewed_to_observation_or_direction_blocked(self):
        for to in ("OBSERVATION_ONLY", "DIRECTION_CONTEXT_ONLY"):
            r = self.rows(); i = next(k for k, x in enumerate(r) if x["contract_state"] == "UNREVIEWED"); r[i]["contract_state"] = to
            with self.assertRaises(S.ContractError, msg=to):
                self.consume(r)

    def test_scope_drop_add_and_foreign_sidecar_blocked(self):
        r = self.rows(); r[1]["approval_scope"] = "WIDER_SCOPE"
        with self.assertRaises(S.ContractError):
            self.consume(r)
        with self.assertRaises(S.ContractError):
            self.consume(self.rows()[:-1])                                              # 행 누락(묵살)
        r = self.rows(); r.append(dict(r[0], fact_id="WH-90001-F099"))
        with self.assertRaises(S.ContractError):
            self.consume(r)                                                             # 행 추가
        with tempfile.TemporaryDirectory() as d2:                                       # 다른 승인표로 만든 sidecar
            b2, a2 = _write(d2, appr=APPR[:-1]); foreign = S.build_sidecar(b2, a2, FIXD, _bind=TS.bind_of(_manifest(b2, a2)))["WH-90001"]
        with self.assertRaises(S.ContractError):
            self.consume(foreign)

    def test_no_trusted_input_fails_closed(self):
        with self.assertRaises(TypeError):
            S.consumption(self.rows(), "QA16_90001", "친구 모임", "friends")
        with self.assertRaises(S.ContractError):
            S.consumption(self.rows(), "QA16_90001", "친구 모임", "friends", trusted=None, source_profile_id="WH-90001")

    def test_genuine_passes_and_observations_from_trusted(self):
        p, lib, obs = self.consume(self.rows())
        self.assertEqual(sorted(o["fact_id"][-4:] for o in obs), ["F002", "F005", "F006", "F007"])
        self.assertNotIn("WH-90001-F001", [o["fact_id"] for o in obs])                  # HOLD 는 출력 없음
        self.assertEqual(sum(len(f.get("evidence") or []) for f in p["traits"]["facets"].values()), 0)
