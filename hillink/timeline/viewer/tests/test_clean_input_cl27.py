"""CL-1025-27 — 제품용 정제 입력 오버레이(비파괴 · 기본 꺼짐). python3 -m unittest tests.test_clean_input_cl27 (timeline/viewer 에서)
1) 동결 입력은 그대로(오버레이는 깊은 복사본만 바꿈) · 기본(HILLINK_CLEAN_INPUT 없음) 실행은 정제 전과 같다.
2) 정제 입력에서 알려진 제외 사실(A08S_E54 · A07-F03 · A02-F13 · A01S_E11 업장 이용 · B43-P02 업장 이용)의 점수 기여가 0이고 출처 충돌이 남지 않는다.
3) A08S_E28 은 룸서비스 업장 이용 기록 · 실용 대안 근거로 유지되고, 한국식 조식 상품 직접 이용은 0."""
import copy, json, os, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
LOCAL = HERE.parent / "experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json"
KNOWN = {"A08": ["A08S_E54"], "A07": ["A07-F03", "A07-F95"], "A02": ["A02-F13"], "A01": ["A01S_E11"], "blog43": ["B43-P02"]}


@unittest.skipUnless(LOCAL.exists(), "로컬 전용 프로필 없음")
class CleanInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from operator_choice.autonomy_v1 import agent_day as AD
        cls.AD = AD
        os.environ.pop("HILLINK_CLEAN_INPUT", None)
        cls.off = AD.load_inputs()
        cls.frozen = copy.deepcopy(cls.off[0])
        os.environ["HILLINK_CLEAN_INPUT"] = "1"
        try:
            cls.on = AD.load_inputs()
        finally:
            os.environ.pop("HILLINK_CLEAN_INPUT", None)
        cls.sc = AD.scenario("base")

    def test_frozen_untouched_and_default_off(self):
        self.assertEqual(json.dumps(self.off[0], sort_keys=True, default=str), json.dumps(self.frozen, sort_keys=True, default=str))
        self.assertIn("A08S_E54", [e["fact_id"] for e in self.off[0]["A08"]["traits"]["facets"]["practical_alt"]["evidence"]])
        self.assertNotIn("A08S_E54", [e["fact_id"] for e in self.on[0]["A08"]["traits"]["facets"]["practical_alt"]["evidence"]])
        self.assertEqual(json.dumps(self.on[0]["A04"], sort_keys=True, default=str), json.dumps(self.off[0]["A04"], sort_keys=True, default=str))   # 영향 없는 고객은 그대로

    def test_excluded_contribution_zero(self):
        for p, fids in KNOWN.items():
            r = self.AD.run_one(p, self.sc, self.on)
            for x in r["log"]:
                tr = (x.get("internal") or {}).get("turn_raw") or {}
                for t in tr.get("terms", []):
                    for fid in fids: self.assertNotIn((t.get("provenance") or {}).get(fid), ("OUT_OF_SCOPE", "NOT_DONE"), f"{p} {fid} 정제 입력에서 제외 사실로 점수에 남음")   # A01S_E11 의 음식 성향 근거는 의도적으로 유지
                    self.assertFalse(t.get("score_provenance_conflict"), f"{p} 출처 충돌 잔존 {t['factor']}")
        a = self.AD.run_one("A08", self.sc, self.on)
        x = next(x for x in a["log"] if x["act"] == "RS_BREAKFAST_KOREAN")
        terms = {t["factor"]: t for t in x["internal"]["turn_raw"]["terms"]}
        self.assertAlmostEqual(terms["실용적 식사 대안(객실에서 먹기)"]["value"], 0.08, places=4)
        self.assertEqual(terms["익숙한 곳 · 실제 이용 경험"]["provenance"], {"A08S_E28": "CONTEXT_TRANSFER_INFERENCE"})
        self.assertEqual(terms["익숙한 곳 · 실제 이용 경험"]["product_direct_visits"], 0)
        b = self.AD.run_one("A01", self.sc, self.on)
        y = next(y for y in b["log"] if (y.get("internal") or {}).get("turn_raw", {}).get("world") == "breakfast")
        self.assertNotIn("익숙한 곳 · 실제 이용 경험", [t["factor"] for t in y["internal"]["turn_raw"]["terms"]])   # 포기한 더뷔페 이용 가산 없음

# 11/02: 유료 룸서비스 조식 자동 구매 중단 이전의 동결 기준을 재현하는 테스트 — 이 모듈에서만 이전 규칙을 켬.
import os as _bf_os
def setUpModule():
    _bf_os.environ["HILLINK_PAID_IRD_BREAKFAST_AUTO"] = "1"
    _bf_os.environ["HILLINK_BREAKFAST_POLICY"] = "LEGACY_STAY_INCLUDED"   # 11/03 조식 계약 정책 이전 기준
def tearDownModule():
    _bf_os.environ.pop("HILLINK_PAID_IRD_BREAKFAST_AUTO", None)
    _bf_os.environ.pop("HILLINK_BREAKFAST_POLICY", None)
