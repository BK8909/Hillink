"""CL-1025-29 — 격리 실행 하네스(tools/lp16_flow_qa.py) · 시각 자산 원장 검사기(tools/visual_assets_check.py). 합성 · 비식별 고정 자료만.
python3 -m unittest tests.test_cl29_qa_tools (timeline/viewer 에서)"""
import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
FIX = HERE / "tests" / "fixtures" / "lp16_synthetic" / "WH-90001"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE / rel); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class FlowQAIsolated(unittest.TestCase):
    def test_synthetic_alias_runs_in_isolated_process_only(self):
        C = _load("lp16c29", "tools/lp16_candidate_convert_qa.py")
        rep, conv, traits = C.run(FIX, use_private=True)
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / rep["qa_alias"]; d.mkdir()
            for n, o in (("report.json", rep), ("converted_v42_facts.PRIVATE.json", conv), ("traits_qa.json", traits)):
                (d / n).write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
            code = f"""
import sys, json; sys.path.insert(0, {str(HERE / 'tools')!r})
import lp16_flow_qa as Q
Q.PRIMARY['QA16_90001'] = 'couple_anniversary'
ids = Q.install(__import__('pathlib').Path({td!r}))
r = Q.flow({{"personas": ids, "mode": "one", "seed": 0}})
print(json.dumps({{"ids": ids, "err": r.get("error"), "scenes": len(r["plans"]["QA16_90001"]["scenes"]) if "plans" in r else 0}}))"""
            out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=600)
            res = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertEqual(res["ids"], ["QA16_90001"]); self.assertIsNone(res["err"]); self.assertGreater(res["scenes"], 3)
        # 같은 테스트 프로세스의 실행 허용 목록 · 디스크 정본은 그대로(격리)
        AD = _load("flow_run_iso", "flow_run.py").AD
        self.assertEqual(len(AD.DEMO), 11); self.assertNotIn("QA16_90001", AD.DEMO)
        r = subprocess.run([sys.executable, "flow_run.py"], cwd=HERE, input=json.dumps({"personas": ["QA16_90001"], "mode": "one"}), capture_output=True, text=True, timeout=300)
        self.assertEqual(json.loads(r.stdout)["code"], "E_FLOW_PERSONA")


class VisualLedger(unittest.TestCase):
    V = None

    @classmethod
    def setUpClass(cls):
        cls.V = _load("vac29", "tools/visual_assets_check.py")

    def row(self, p, key, rel, path=None, st="AWAITING_LP", ev=("F1",), tid="friends"):
        return {"persona": p, "type_id": tid, "avatar": {"key": key, "rel": rel, "status": "MAPPED" if key else "NO_ASSET"},
                "thumbnail": {"path": path, "sha256": None, "asset_id": None, "status": st, "evidence_ids": list(ev)}}

    def test_ok(self):
        self.assertEqual(self.V.check([self.row("a", "friends_2f", "friends"), self.row("b", "couple_smart", "couple", tid="couple_anniversary"), self.row("c", None, "group")]), [])

    def test_errors(self):
        e = self.V.check([self.row("a", "family_kid1", "friends"),                                                   # 관계 불일치
                          self.row("b", "couple_smart", "friends"),                                                  # 친구에 커플 그림
                          self.row("c", "friends_2f", "friends", path="timeline/viewer/static/persona_thumbs/친구모임_썸네일.jpg"),   # 유형 공용 썸네일 + 준비 전 경로
                          self.row("d", "friends_2f", "friends", path="timeline/viewer/static/avatars/friends_2f_front.png", st="IMAGE_READY"),  # 필드 혼용
                          self.row("e", "custom_e", "friends", ev=())])                                                # 1:1 전용 · 근거 없음
        for s in ("관계 friends 에 맞지 않는 그림 family_kid1", "관계 friends 에 맞지 않는 그림 couple_smart", "유형 공용 썸네일", "필드 혼용", "공용 풀에 없음", "근거 사실 ID 없음"):
            self.assertTrue(any(s in x for x in e), s)

    def test_duplicate_thumbnail(self):
        r1 = self.row("a", "friends_2f", "friends"); r2 = self.row("b", "friends_2f", "friends")
        r1["thumbnail"]["asset_id"] = r2["thumbnail"]["asset_id"] = "T1"
        self.assertTrue(any("중복" in x for x in self.V.check([r1, r2])))
