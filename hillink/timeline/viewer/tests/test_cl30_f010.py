"""CL-1025-30 — 휴관 · 관람 실패(CLOSED/CANCELED_INCOMPLETE) 사실이 그 시설 이용의 직접 근거 · 선택 가중으로 쓰이지 않는지(합성 문장).
python3 -m unittest tests.test_cl30_f010 (timeline/viewer 에서)"""
import sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
from operator_choice.autonomy_v1 import agent_day as AD  # noqa: E402
from operator_choice.operator_world_v1_1 import stay_planner as SP  # noqa: E402


class F010(unittest.TestCase):
    def test_incomplete_semantics(self):
        for t in ("포함된 빛의 시어터 이용권이 있어도 휴관으로 관람 실패", "월요일 휴무를 그날 알았다", "입장 실패 후 돌아감", "운영 중단으로 이용을 못 함"):
            self.assertTrue(AD.INCOMPLETE.search(t), t)
        for t in ("전화 연결에 여러 번 실패하고 다음 날 취소분 접수", "예약을 일정상 취소한 뒤 다시 방문해 이용", "빛의 시어터를 관람했다"):   # 기존 11명 유형의 문장 — 미완료 아님
            self.assertFalse(AD.INCOMPLETE.search(t), t)

    def test_not_in_choice_hits(self):
        facts = [{"id": "X-F1", "gist": "포함된 빛의 시어터 이용권이 있어도 휴관으로 관람 실패", "feat": "", "kind": "comparison"},
                 {"id": "X-F2", "gist": "빛의 시어터를 친구와 관람했다", "feat": "", "kind": "participation"}]
        before = SP.fact_hits(facts, over=AD.EV_OVER).get("theatre", [])
        after = SP.fact_hits(facts, neg_rx=SP.NEG_BASE + "|" + AD.INCOMPLETE.pattern, over=AD.EV_OVER).get("theatre", [])
        self.assertIn("X-F1", before)            # 수정 전 경로 재현(근거로 잡힘)
        self.assertEqual(after, ["X-F2"])        # 수정 후: 실제 관람만


class F011SubstituteObserved(unittest.TestCase):
    """CL-1025-31 — '휴관 뒤 근처 카페로 대체 방문'은 관측(OBSERVED)이며 F010(CANCELED_CLOSED)과 별개. 장소 미특정이라 특정 업장 직접 근거 · 선택 가중은 아님."""
    def test_semantics(self):
        self.assertTrue(AD.incomplete("빛의 시어터 이용권이 있었지만 휴관으로 관람 실패"))
        self.assertFalse(AD.incomplete("전시 휴관 후 근처 카페로 대체 방문"))
        self.assertTrue(AD.VENUE_UNSPEC.search("전시 휴관 후 근처 카페로 대체 방문"))
        self.assertFalse(AD.VENUE_UNSPEC.search("더 파빌리온에서 커피를 마셨다"))

    def test_agent_attribution_synthetic(self):
        import importlib.util, json, subprocess, tempfile
        spec = importlib.util.spec_from_file_location("lp16c31", HERE / "tools" / "lp16_candidate_convert_qa.py"); C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
        rep, conv, traits = C.run(HERE / "tests" / "fixtures" / "lp16_synthetic" / "WH-90001", use_private=True)
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / rep["qa_alias"]; d.mkdir()
            for n, o in (("report.json", rep), ("converted_v42_facts.PRIVATE.json", conv), ("traits_qa.json", traits)):
                (d / n).write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
            code = f"""
import sys, json; sys.path.insert(0, {str(HERE / 'tools')!r})
import lp16_flow_qa as Q
Q.PRIMARY['QA16_90001'] = 'friends'
Q.install(__import__('pathlib').Path({td!r}), 'V2')
AD = Q.AD; inp = AD.load_inputs(); a = AD.Agent('QA16_90001', inp[0], inp[1], inp[2], AD.scenario('base'))
out = dict(cafe_hits=a.P['fact_hits'].get('cafe', []), theatre_hits=a.P['fact_hits'].get('theatre', []), unspec=a.obs_unspec)
for code, loc in (('cafe', 'THE_PAVILION'), ('theatre', 'THEATRE_OF_LIGHT')):
    AD.plan_do(a, code, loc, AD.hm('15:00'), {{}}, []); x = a.log[-1]
    out[code] = dict(layer=x.get('layer'), direct=[f for e in x['evidence'] if e['type'] == '후기에서 확인' for f in e.get('fact_ids') or []],
                     ext=[f for e in x['evidence'] for f in e.get('extended_from') or []])
print(json.dumps(out))"""
            r = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True, timeout=600)
            o = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertNotIn("WH-90001-F006", o["theatre_hits"]); self.assertNotIn("WH-90001-F006", o["theatre"]["direct"] + o["theatre"]["ext"])   # F010 형: 관람 근거 0
        self.assertNotIn("WH-90001-F007", o["cafe_hits"])                     # 장소 미특정 → 선택 가중 없음
        self.assertEqual(o["unspec"].get("cafe"), ["WH-90001-F007"])
        self.assertIn("WH-90001-F007", o["cafe"]["ext"]); self.assertNotIn("WH-90001-F007", o["cafe"]["direct"])   # 같은 종류 활동 관측으로만 표시
