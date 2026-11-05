"""CL-1025-35 — 하루 행동 export 행 분류(합성 기록 · 비공개 자료 없이 실행)."""
import sys, unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "tools"), str(Path(__file__).resolve().parents[1])]
import cl35_daily_export_qa as X  # noqa: E402

OBS = [dict(fact_id="F-OBS", applicable_activities=["ROOM_SERVICE_PRICE"]), dict(fact_id="F-GAP", applicable_activities=["DOUGLAS_LOUNGE"])]


def eng(review=0.0, fids=(), why="휴식 · 회복을 중시하는 성향이라 쉽니다."):
    terms = [dict(factor="휴식", value=0.2, fact_ids=list(fids), parts=dict(common=0.2, review=review, assumption=0.0))]
    tr = dict(world="operator", chosen="ROOM_MEAL", score=0.2 + review, total=1.0, terms=terms,
              rejected=[dict(offer="POOL", feasible=True, score=0.1, total=0.5), dict(offer="WINE_FAIR", feasible=False, score=None, total=None, blocked=["운영하지 않음"])])
    return dict(t="18:00", e="19:00", act="ROOM_MEAL", label="객실 식사", loc="ROOM", domain="식사", source="quantitative_engine", why=why,
                evidence=[dict(type="프로파일 기반 추론", traits=[])], internal=dict(engine="decide_at", turn_raw=tr, event_view=[dict(offer="WINE_FAIR", stage="참여 불가", why=["운영하지 않음"])]))


class Cl35ExportTest(unittest.TestCase):
    def test_generic_default_and_template_flag(self):
        r = X.row_of(eng(), {}, OBS)
        self.assertTrue(r["reason_basis"].startswith("MODEL_SCORE_GENERIC_DEFAULT"))
        self.assertTrue(r["why_text_flag"].startswith("TEMPLATE_SENTENCE_NOT_PERSONAL"))
        self.assertEqual(r["contrib_review"], 0.0)
        self.assertEqual(r["scoring_fact_ids"], "")
        self.assertIn("POOL=0.5", r["not_chosen_feasible"])
        self.assertIn("WINE_FAIR:운영하지 않음", r["not_chosen_blocked"])
        self.assertIn("WINE_FAIR:참여 불가", r["time_event_constraints"])
        self.assertTrue(r["package_eligibility"].startswith("unknown"))

    def test_review_evidence_not_hidden_as_generic(self):
        r = X.row_of(eng(review=0.3, fids=["F-X"]), {}, OBS)
        self.assertEqual(r["reason_basis"], "REVIEW_EVIDENCE")
        self.assertEqual(r["why_text_flag"], "")
        self.assertEqual(r["scoring_fact_ids"], "F-X")

    def test_observation_display_only_literal_map(self):
        r = X.row_of(eng(), {}, OBS)
        self.assertEqual(r["explanatory_observation_ids_display_only"], "F-OBS")   # 장소 표현 없는 DOUGLAS_LOUNGE 는 붙지 않음
        self.assertNotIn("F-OBS", r["scoring_fact_ids"])

    def test_planner_rows_not_model_score(self):
        x = dict(t="21:00", e="22:00", act="luxbar", label="바", loc="BAR", domain="바", source="planner_rules", why="친구와 한잔을 즐깁니다.",
                 evidence=[], internal=dict(weights={"luxbar": 0.6}, rejected={"cafe": "영업시간 밖"}))
        r = X.row_of(x, {}, OBS)
        self.assertTrue(r["reason_basis"].startswith("UNKNOWN/GENERIC_DEFAULT"))
        self.assertIn("cafe:영업시간 밖", r["not_chosen_blocked"])

    def test_not_run_scenario_recorded(self):
        self.assertIn("AUTUMN_CAMCNIC_20261026", X.NOT_RUN)
        self.assertNotIn("AUTUMN_CAMCNIC_20261026", X.SCENARIOS)
        self.assertEqual(X.SCENARIOS["BASE_NO_EVENT"]["programming"], "HYPOTHETICAL_EVENT_PROGRAMMING")


if __name__ == "__main__":
    unittest.main()
