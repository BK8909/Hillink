"""CL-1025-28 — LP-16 candidate → 엔진 입력 격리 QA 변환기(tools/lp16_candidate_convert_qa.py) 시험. 합성 · 비식별 고정 자료만 씁니다.
python3 -m unittest tests.test_lp16_convert_cl28 (timeline/viewer 에서)"""
import importlib.util, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
FIX = HERE / "tests" / "fixtures" / "lp16_synthetic" / "WH-90001"
spec = importlib.util.spec_from_file_location("lp16c", HERE / "tools" / "lp16_candidate_convert_qa.py"); C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


class LP16Convert(unittest.TestCase):
    def test_schema_not_bypassed_without_private_anchors(self):
        rep, _, _ = C.run(FIX, use_private=False)
        self.assertEqual(rep["convert_status"], "BLOCKED")
        self.assertTrue(all(any("anchors" in e for e in v) for v in rep["schema_errors"].values()))

    def test_convert_ready_and_rules(self):
        rep, conv, traits = C.run(FIX, use_private=True)
        self.assertEqual(rep["convert_status"], "CONVERT_READY", rep["schema_errors"])
        self.assertEqual(rep["qa_alias"], "QA16_90001")
        self.assertEqual([x["fact_id"] for x in rep["excluded"]], ["WH-90001-F004"])          # 대기열 — 범위 밖 주제
        keys = {f["fact_id"]: f["experience_key"] for f in conv["v42_facts"]}
        self.assertEqual(keys["WH-90001-F003"], "LP16_90001_X02")                # 고객 접두 WH- 로 워커힐 판정 안 됨 · 원본 키 낱말 미사용
        self.assertEqual(keys["WH-90001-F001"], "LP16_90001_X01_WH")
        self.assertNotIn("THE_BUFFET", {v for v, xs in traits["venues"].items() if xs})        # 외부 호텔 뷔페 ≠ 더뷔페 이용
        self.assertNotIn("POOL", {v for v, xs in traits["venues"].items() if any(x["kind"] == "used" for x in xs)})   # 취소한 수영장
        self.assertIn("SKYARD", traits["venues"])
        self.assertIn("SAME_BEHAVIOR_OBSERVED", traits["evidence_index"]["WH-90001-F002"]["lp_relation"])
        self.assertIn("CONTEXT_TRANSFER_INFERENCE", traits["evidence_index"]["WH-90001-F003"]["lp_relation"])
        self.assertTrue(rep["checks"]["no_url_email_in_traits"] and rep["checks"]["excluded_not_consumed"])

    def test_scope_patterns_seat_wait(self):   # 좌석 · 대기 · 줄 주제는 소비 입력에서 제외(합성 문장)
        for t in ("창가석 요청 후 안내", "선호 좌석을 확보하지 못함", "약 20분 기다리고 입장", "현장 오픈런", "대기 없는 입장", "대기열이 길어 포기"):
            self.assertTrue(C.OUT_OF_SCOPE.search(t) or C.EXCLUDE_EXTRA.search(t), t)
        for t in ("라운지 조식 이용", "실내 수영 레인 이용", "와인페어 참석"):
            self.assertFalse(C.OUT_OF_SCOPE.search(t) or C.EXCLUDE_EXTRA.search(t), t)
