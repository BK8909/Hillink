import pytest
"""CL-1024-22R — 고객 흐름의 행동 엔진 = autonomy_v1 · /api/stay 결정 위조 거절.
서버를 임시 포트로 띄워 실제 HTTP 로 확인한다. python3 -m unittest tests.test_flow_cl22 (timeline/viewer 에서)

1) /api/flow 의 하루 장면 · 정량 결정이 autonomy_v1 을 같은 조건으로 직접 돌린 기록과 같다(기존 엔진 결과에 설명만 덧칠한 것이 아님).
2) 운영 변경(와인페어 · 피자힐 마감 · 수영장 점검) → 개입 전후 비교 · 고객별 이야기가 있고, 시간 겹침이 없고, 와인페어 입장료가 방문 조건대로다.
3) /api/stay plan — 서버가 발급한 결정만 받는다(상품 바꿔치기 · 재해시 · 증표 없음 · 시각 변경 · 다른 고객 ID → 403 E_DECISION_NOT_ISSUED). 정상 결정은 200.
4) 게시 승인 밖 고객 · 형식 오류 입력은 거절."""
import hashlib, json, os, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tests"))
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
from test_security_cl20 import Server  # noqa: E402

IDS = ["A02", "A04", "A05", "A07", "A10", "blog41", "blog42", "blog43", "A01", "A03", "A08"]
COND = {"turn": "dinner", "event": False, "stay": True, "building": "VISTA", "party_size": 2, "pricing": "historical", "product_levers": {}, "phase": "mid"}
hm = lambda t: int(t[:2]) * 60 + int(t[3:5])


class FlowEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server({"HILLINK_REVIEWER_LOCAL": "", "HILLINK_PUBLISH_OVERRIDE": "", "HILLINK_DEPLOY": "local"})

    @classmethod
    def tearDownClass(cls):
        cls.s.stop()

    def flow(self, body):
        st, b = self.s.call("/api/flow", body)
        self.assertEqual(st, 200, b[:200])
        return json.loads(b)

    def test_flow_uses_autonomy_engine(self):
        from operator_choice.autonomy_v1 import agent_day as AD
        d = self.flow({"personas": ["A07"], "mode": "one"})
        self.assertEqual(d["engine"]["name"], "autonomy_v1")
        r = AD.run_one("A07", AD.scenario("none", seed=0, levers={"WINE_FAIR": {"available": False}}, observe="day"))
        direct = [(hm(x["t"]), hm(x["e"]), x["loc"]) for x in r["log"] if x["act"] != "move" and not (x["act"] == "wait" and hm(x["e"]) - hm(x["t"]) < 10)]
        scenes = [(s["t0"], s["t1"], s["loc"]) for s in d["plans"]["A07"]["scenes"]]
        self.assertEqual(scenes, direct)
        eng = [x for x in r["log"] if (x.get("internal") or {}).get("turn_raw")]
        self.assertTrue(eng)
        turns = {R["turn"]: R["customers"][0] for R in d["runs"]}
        self.assertIn("breakfast", turns)
        bx = next(x for x in eng if x["internal"]["turn_raw"]["world"] == "breakfast")
        self.assertEqual(turns["breakfast"]["choice"]["product_id"], bx["act"])
        self.assertEqual(turns["breakfast"]["decided_at"], bx["t"])
        self.assertEqual(d["plans"]["A07"]["backend"], "autonomy_v1")

    @pytest.mark.requires_private_personas('A01','A03','A08')
    def test_interventions_story_time_fee(self):
        for iv in ("wine_fair_1300", "pizzahill_full", "pool_check"):
            d = self.flow({"personas": IDS, "mode": "many", "intervention": iv})
            self.assertEqual(len(d["stories"]), 11, iv)
            self.assertTrue(any(not s["keep_reason"] for s in d["stories"].values()), iv)
            self.assertTrue(any(s["keep_reason"] for s in d["stories"].values()), iv)
            for pid, p in d["plans"].items():
                for a, b in zip(p["scenes"], p["scenes"][1:]):
                    self.assertLessEqual(a["t1"], b["t0"], f"{iv} {pid} {a['act']}→{b['act']}")
            if iv == "wine_fair_1300":
                ev = next(R for R in d["runs"] if R["turn"] == "event")
                for c in ev["customers"]:
                    v = d["visits"][c["persona_id"]]
                    self.assertEqual(c["choice"]["price"]["paid_krw"], 0 if v["stay"] else 55000, c["persona_id"])
                self.assertIn("compare", ev)
            if iv == "pool_check":
                self.assertTrue(d["stories"]["A01"]["steps"])

    def test_stay_forgery_rejected(self):
        st, b = self.s.call("/api/turn", {"op": "view", "personas": ["A07"], "cond": COND})
        R = json.loads(b); c = R["customers"][0]; ch = c["choice"]
        alts = [(a.get("product_id") or a.get("venue_id")) for a in [x for x in [c.get("runner_up")] + c.get("not_chosen", []) if x][:3]]
        d = dict(decision_id=f"A07|{R['turn']}|{R['time']}", turn=R["turn"], time=R["time"], loc=ch["map_loc"], label="저녁", product_id=ch["product_id"] or ch["venue_id"],
                 product_label=ch["product_label"], venue_id=ch["venue_id"], participation="purchase", alternatives=alts, source="turn_view", changed=False, token=c["decision_token"])
        body = lambda x: {"op": "plan", "personas": ["A07"], "cond": COND, "decisions": {"A07": [x]}, "comp": {"A07": {"n": 2, "rel": "spouse"}}, "seed": 0, "backend": "rules"}
        st, b = self.s.call("/api/stay", body(d)); self.assertEqual(st, 200, b[:200])
        forged = dict(d, product_id="QA_FORGED_PRODUCT", product_label="위조")
        cases = [forged, dict(forged, token=hashlib.sha256(json.dumps(forged, sort_keys=True).encode()).hexdigest()[:40]),
                 {k: v for k, v in d.items() if k != "token"}, dict(d, time="17:00"), dict(d, decision_id="A05|dinner|18:30"), dict(d, alternatives=["QA_FORGED_PRODUCT"])]
        for x in cases:
            st, b = self.s.call("/api/stay", body(x))
            self.assertEqual(st, 403, b[:200]); self.assertIn("E_DECISION_NOT_ISSUED", b)
        st, b = self.s.call("/api/stay", dict(body(d), base_decisions={"A07": [forged]}))
        self.assertEqual(st, 403)

    def test_flow_rejects(self):
        st, b = self.s.call("/api/flow", {"personas": ["N08"], "mode": "one"}); self.assertEqual(st, 403)
        st, b = self.s.call("/api/flow", {"personas": ["A07"], "intervention": "../../x"}); self.assertEqual(st, 400)
        st, b = self.s.call("/api/flow", {"personas": ["A07"], "visit_override": {"A07": {"building": "X"}}}); self.assertEqual(st, 400)
        st, b = self.s.call("/api/flow", {"personas": ["A07"], "seed": "1;rm"}); self.assertEqual(st, 400)
        self.assertNotIn("/home/", b)


# 11/02: 유료 룸서비스 조식 자동 구매 중단 이전의 동결 기준을 재현하는 테스트 — 이 모듈에서만 이전 규칙을 켬.
import os as _bf_os
def setUpModule():
    _bf_os.environ["HILLINK_PAID_IRD_BREAKFAST_AUTO"] = "1"
    _bf_os.environ["HILLINK_BREAKFAST_POLICY"] = "LEGACY_STAY_INCLUDED"   # 11/03 조식 계약 정책 이전 기준
def tearDownModule():
    _bf_os.environ.pop("HILLINK_PAID_IRD_BREAKFAST_AUTO", None)
    _bf_os.environ.pop("HILLINK_BREAKFAST_POLICY", None)


if __name__ == "__main__":
    unittest.main()


class A08BreakfastProvenance(unittest.TestCase):
    """CL-1025-26 — A08 09:10 RS_BREAKFAST_KOREAN: 실제 HTTP /api/flow 응답에서 A08S_E28 이 직접 후기 몫 · 상품 이용 횟수로 귀속되지 않고,
    A08S_E54(범위 밖)는 근거 요지에 없으며 점수에 남은 몫은 SCORE_PROVENANCE_CONFLICT 로 드러난다. 선택 · 점수(엔진)는 그대로."""
    @classmethod
    def setUpClass(cls):
        cls.s = Server({"HILLINK_REVIEWER_LOCAL": "", "HILLINK_PUBLISH_OVERRIDE": "", "HILLINK_DEPLOY": "local"})

    @classmethod
    def tearDownClass(cls):
        cls.s.stop()

    @pytest.mark.requires_private_personas('A01','A03','A08')
    def test_a08_breakfast(self):
        st, b = self.s.call("/api/flow", {"personas": ["A08"], "mode": "one", "seed": 0})
        self.assertEqual(st, 200, b[:200])
        r = json.loads(b)
        c = next(c for R in r["runs"] if R["turn"] == "breakfast" for c in R["customers"])
        self.assertEqual((c["choice"]["product_id"], c["decided_at"], c["choice"]["score"]), ("RS_BREAKFAST_KOREAN", "09:10", 4.42))   # 동결 엔진 선택 · 점수 불변
        self.assertEqual(c["direct_review_fact_ids"], [])
        self.assertEqual(c["product_direct_visits"], 0)
        for t in c["reasons"]:
            if "A08S_E28" in (t.get("provenance") or {}):
                self.assertEqual(t["provenance"]["A08S_E28"], "CONTEXT_TRANSFER_INFERENCE")
                self.assertGreater(t["parts"]["transfer"], 0)
            if t["factor"].startswith("익숙한 곳"):
                self.assertEqual(t["parts"]["review"], 0.0)
                self.assertNotIn("이 업장 실제 이용 1회", t["note"])
                self.assertIn("이 상품 직접 이용 0회", t["note"])
        self.assertNotIn("A08S_E54", c["evidence"])
        conf = [x for x in c["score_provenance_conflicts"] if "A08S_E54" in x["fact_ids"]]
        self.assertTrue(conf and conf[0]["code"] == "SCORE_PROVENANCE_CONFLICT" and conf[0]["amount"] > 0)
        self.assertAlmostEqual(sum(c["reason_totals"].values()), c["choice"]["score"], places=2)
        scene = next(s for s in r["plans"]["A08"]["scenes"] if s["t0"] == 9 * 60 + 10)
        self.assertFalse([e for e in scene["basis"]["evidence"] if e["type"] == "후기에서 확인"])
        self.assertTrue(any(e.get("basis_kind") == "CONTEXT_TRANSFER_INFERENCE" for e in scene["basis"]["evidence"]))
