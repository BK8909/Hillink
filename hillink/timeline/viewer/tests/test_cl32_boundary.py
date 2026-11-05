"""CL-1025-32 — (A) 한 사실 안의 관측 행동 / 범위 밖 맥락 분리(부분 관측) · (B) 일반 /api/flow 요지 최소화. 합성 자료 + 기존 11명 응답.
python3 -m unittest tests.test_cl32_boundary (timeline/viewer 에서)"""
import hashlib, importlib.util, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
FIX = HERE / "tests" / "fixtures" / "lp16_synthetic" / "WH-90001"


def _conv():
    spec = importlib.util.spec_from_file_location("lp16c32", HERE / "tools" / "lp16_candidate_convert_qa.py"); C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C); return C


class PartialObserved(unittest.TestCase):
    def test_split_keeps_observed_clause_only(self):
        C = _conv()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "WH-90001"; shutil.copytree(FIX, d)
            fe = json.loads((d / "candidate/facts_events_evidence.json").read_text(encoding="utf-8")); pv = json.loads((d / "private/fact_evidence_origins_PRIVATE.json").read_text(encoding="utf-8"))
            det = "가족 동행 조식 2부 이용 · 대기 없는 입장"; q = f"[합성 인용 F008] {det}"; h = hashlib.sha256(q.encode()).hexdigest()
            fe["facts"].append({"fact_id": "WH-90001-F008", "post_id": "WH-90001_P001", "event_id": "WH-90001-E008", "experience_key_PROVISIONAL": "WH-90001_VISTA_REST", "detail_intermediate_not_observation_approval": det,
                                "kind_original": "participation", "action_stage_original": "consumption_reported", "actor_original": "author_with_family", "scope_original": "walkerhill_property",
                                "original_polarity": "not_quantified_pending_human_semantic_review", "original_confidence": "medium_contextual_source", "anchors": [{"start": 0, "end": len(q), "anchor_sha256": h}]})
            pv.append({"fact_id": "WH-90001-F008", "post_id": "WH-90001_P001", "anchor_start": 0, "anchor_end": len(q), "quote_PRIVATE": q, "anchor_sha256": h})
            (d / "candidate/facts_events_evidence.json").write_text(json.dumps(fe, ensure_ascii=False), encoding="utf-8"); (d / "private/fact_evidence_origins_PRIVATE.json").write_text(json.dumps(pv, ensure_ascii=False), encoding="utf-8")
            r0, _, t0 = C.run(d, True)                                                   # LP 상태 없음 → 전체 제외(종전)
            self.assertIn("WH-90001-F008", [x["fact_id"] for x in r0["excluded"]])
            r1, c1, t1 = C.run(d, True, {"WH-90001-F008": ("OBSERVED", "YES")})          # LP OBSERVED · 워커힐 직접 → 부분 관측
            self.assertEqual([x["fact_id"] for x in r1["partial_observed"]], ["WH-90001-F008"])
            g = next(x for x in c1["v42_facts"] if x["fact_id"] == "WH-90001-F008")
            self.assertEqual(g["detail"], "가족 동행 조식 2부 이용"); self.assertNotIn("대기", g["detail"])
            self.assertEqual(c1["detail_original_PRIVATE"]["WH-90001-F008"], det)
            self.assertEqual(t1["evidence_index"]["WH-90001-F008"]["layer"], "OBSERVATION_ONLY_PARTIAL")
            e0, e1 = dict(t0), dict(t1); e0.pop("evidence_index"); e1.pop("evidence_index")
            self.assertEqual(e0, e1)                                                      # 성향 · 업장 점수 projection 불변(점수 · 선호 수치 부여 없음)
            r2, _, _ = C.run(d, True, {"WH-90001-F008": ("OTHER_CONTEXT", "NO_EXTERNAL_CONTEXT")})
            self.assertIn("WH-90001-F008", [x["fact_id"] for x in r2["excluded"]])       # OBSERVED 가 아니면 종전대로 제외


class ApiEvidenceMinimal(unittest.TestCase):
    def test_flow_evidence_only_cited_and_masked(self):
        sys.path.insert(0, str(HERE))
        import flow_run as FR
        for q in ({"personas": ["A01", "A02", "A03", "A04", "A05", "A07", "A08", "A10", "blog41", "blog42", "blog43"], "mode": "many", "seed": 0},
                  {"personas": ["A10"], "mode": "one", "seed": 0}):
            r = json.loads(subprocess.run([sys.executable, "flow_run.py"], cwd=HERE, input=json.dumps(q), capture_output=True, text=True, timeout=600).stdout)
            for run in r["runs"]:
                for c in run["customers"]:
                    used = {f for t in c["reasons"] for f in t["fact_ids"]} | {f for e in c["engine_evidence"] for f in (e.get("fact_ids") or [])}
                    self.assertTrue(set(c["evidence"]) <= used, (c["persona_id"], set(c["evidence"]) - used))
                    for v in c["evidence"].values():
                        self.assertTrue(v == FR.MASKED or not FR.DISPLAY_SENSITIVE.search(v), v[:12])
            s = json.dumps(r, ensure_ascii=False)
            for f in ("A10-F30", "A10-F33", "A10-F65"):
                self.assertNotIn(f, s)
