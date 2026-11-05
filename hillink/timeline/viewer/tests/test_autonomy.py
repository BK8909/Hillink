"""CL-1024-18 자율 하루 시험 — python3 -m unittest tests.test_autonomy (timeline/viewer 에서). 로컬 전용 프로필이 없으면 건너뜀."""
import json, re, subprocess, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
LOCAL = HERE.parent / "experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json"


@unittest.skipUnless(LOCAL.exists(), "로컬 전용 프로필 없음")
class Autonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from operator_choice.autonomy_v1 import agent_day as AD
        cls.AD = AD; cls.inp = AD.load_inputs(); cls.base = AD.scenario("base")
        cls.ind = {p: AD.run_one(p, cls.base, cls.inp) for p in AD.DEMO}
        cls.con = AD.run_many(AD.DEMO, cls.base, cls.inp)

    def seq(self, r): return [(x["t"], x["act"], x["loc"]) for x in r["log"]]

    def test_all_eleven_complete_individually_and_concurrently(self):
        for p in self.AD.DEMO:
            self.assertTrue(self.ind[p]["summary"]["completed"], p)
            self.assertTrue(self.con["personas"][p]["summary"]["completed"], p)
            self.assertGreaterEqual(len(self.ind[p]["summary"]["domains"]), 3, p)   # 하루 안에 여러 종류의 행동

    def test_individual_equals_concurrent_and_reproducible(self):
        for p in self.AD.DEMO:
            self.assertEqual(self.seq(self.ind[p]), self.seq(self.con["personas"][p]), p)
            self.assertEqual(self.seq(self.ind[p]), self.seq(self.AD.run_one(p, self.base, self.inp)), p)

    def test_world_rules(self):
        SP = self.AD.SP
        for p, r in self.ind.items():
            L = r["log"]
            for i, x in enumerate(L):
                if i: self.assertGreaterEqual(self.AD.hm(x["t"]), self.AD.hm(L[i - 1]["e"]), f"{p} 겹침 {x['t']}")
                if x["source"] == "planner_rules" and x["act"] in SP.ACT:
                    self.assertTrue(SP.open_at(x["loc"], self.AD.hm(x["t"]), self.AD.hm(x["e"])), f"{p} {x['act']} 영업시간")
                if not r["visit"]["stay"]:
                    self.assertNotIn(x["loc"], SP.GUEST_ONLY, f"{p} 비투숙 투숙객 전용")
            acts = [x["act"] for x in L if x["act"] not in ("move", "wait", "idle", "room_rest", "ROOM_REST", "room_bath", "lunch_skip")]
            self.assertEqual(len(acts), len(set(acts)), f"{p} 같은 활동 반복")

    def test_visit_conditions_not_forced_identical(self):
        vs = {json.dumps(r["visit"], sort_keys=True) for r in self.ind.values()}
        self.assertGreater(len(vs), 3)

    def test_evidence_types_and_review_fact_ownership(self):
        for p, r in self.ind.items():
            own = p.replace("blog", "B")[:3]
            for x in r["log"]:
                for e in x["evidence"]:
                    self.assertIn(e["type"], ("후기에서 확인", "프로파일 기반 추론", "후기 회피 근거", "불확실"))   # CL-1025-24 — 회피(부정) 근거 · 불확실 표시 추가
                    if e["type"] == "후기에서 확인":
                        self.assertTrue(e["fact_ids"])
        # CL-19: 정량 엔진 근거는 그 장소 · 상품에 관한 사실만 '후기에서 확인' — 후기 근거 행동이 없는 고객도 있을 수 있음(성향 추론만)
        # CL-1025-24 — blog41(원저자 매핑 검수 대기) · A01(E08 = 동선 만족, 이용 아님)은 '후기에서 확인'에서 빠짐 → 6명 이상
        self.assertGreaterEqual(sum(1 for r in self.ind.values() if r["summary"]["review_evidence_actions"] > 0), 6)

    def test_cl25_a08_breakfast_and_scope(self):
        x = next(x for x in self.ind["A08"]["log"] if x["act"] == "RS_BREAKFAST_KOREAN")
        self.assertFalse([e for e in x["evidence"] if e["type"] == "후기에서 확인"], "A08S_E28(룸서비스 짬뽕 + 라이트 조식 요약)은 룸서비스 한국식 조식 직접 경험이 아님")
        inf = next(e for e in x["evidence"] if e["type"] == "프로파일 기반 추론")
        self.assertEqual(inf.get("basis_kind"), "CONTEXT_TRANSFER_INFERENCE")
        self.assertIn("A08S_E28", inf["extended_from"])
        shown = [f for p, r in self.ind.items() for y in r["log"] for e in y["evidence"] for f in (e.get("fact_ids") or []) + (e.get("extended_from") or [])]
        shown += [f for p, r in self.ind.items() for y in r["log"] for t in ((y.get("internal") or {}).get("turn_raw") or {}).get("terms", []) for f in t["fact_ids"]]
        for f in ("A08S_E54", "A07-F03", "A02-F13"):   # 남은 음식 포장 · 포장해 객실에서 · 현장 대기 감수 — 행동 근거로 표시하지 않음(원문 보존)
            self.assertNotIn(f, shown)

    def test_cl24_evidence_levels(self):
        I = self.ind
        rv = lambda p: [f for x in I[p]["log"] for e in x["evidence"] if e["type"] == "후기에서 확인" for f in e["fact_ids"]]
        for p in ("blog41", "blog42", "blog43"):
            self.assertEqual(rv(p), [], f"{p} 원저자 매핑 검수 전 — 직접 경험 표시 금지")
        self.assertNotIn("A01S_E08", rv("A01"), "A01S_E08 은 동선 만족(이용 아님)")
        av = [e for x in I["A02"]["log"] for e in x["evidence"] if e["type"] == "후기 회피 근거"]
        self.assertTrue(av and av[0]["venue"] == "PIZZA_HILL" and av[0]["fact_ids"][0].startswith("A02-F18"), "A02 피자힐 회피 근거")
        self.assertFalse(any(x["act"] == "PIZZA_HILL" for x in I["A02"]["log"]))
        actual_charges = [x["charge"] for x in I["A01"]["log"]
                          if (x.get("charge") or {}).get("status") == "유료" and x["charge"].get("per") == "인"]
        self.assertTrue(all(c.get("party_estimate") for c in actual_charges))
        # The seeded day may legitimately contain no paid per-person purchase.
        # Exercise the existing billing seam directly: no selected action is changed.
        from unittest.mock import patch
        actor = self.AD.Agent("A01", *self.inp, self.base)
        amount = 10000 * actor.N
        with patch.object(self.AD.LG, "charge", return_value=dict(status="유료", per="인", krw=amount)):
            row = actor.add("activity", "QA_PAID_HEADCOUNT", "인원 요금 계약 검사", actor.loc,
                            actor.t, 15, "활동", "world_rule", "표시 계약 검사", [])
        self.assertTrue(row["charge"].get("party_estimate"), "아동 구성 미확인 인원 요금은 추정 표시")
        self.assertIn(str(actor.N), row["charge"]["party_note"])
        self.assertEqual(row["charge"]["krw"], amount)
        self.assertEqual(actor.spent_est, amount)
        adult = self.AD.Agent("A04", *self.inp, self.base)
        with patch.object(self.AD.LG, "charge", return_value=dict(status="유료", per="인", krw=10000 * adult.N)):
            control = adult.add("activity", "QA_PAID_HEADCOUNT", "성인 요금 계약 검사", adult.loc,
                                adult.t, 15, "활동", "world_rule", "표시 계약 검사", [])
        self.assertNotIn("party_estimate", control["charge"])
        rs = {p: I[p]["visit"]["review_stay"] for p in I}
        self.assertEqual((rs["A03"]["building"], rs["A03"]["club"], rs["A03"]["same"]), ("GRAND", True, False))
        self.assertTrue(rs["A04"]["same"] and rs["blog43"]["pending"])
        X = self.AD.scenario("club", visit_override={"A03": {"stay": True, "building": "GRAND", "phase": "mid", "party_size": 2, "club": True}})
        a = self.AD.run_one("A03", X, self.inp)
        self.assertTrue(a["visit"]["club"])
        self.assertNotIn("A03_F04", [f for x in a["log"] if x["act"] in ("PIZZA_HILL", "lunch_pizzahill") for e in x["evidence"] if e["type"] == "후기에서 확인" for f in e["fact_ids"]],
                         "라운지 해피아워 피자(A03_F04)는 피자힐 경험이 아님")
        self.assertFalse(any(x["act"] == "lounge" and "클럽 객실 자격" in str(x) for x in a["log"]))

    def test_operator_intervention_changes_some_not_all(self):
        X = self.AD.scenario("wf", changes=[dict(at="13:00", label="와인페어 개최", levers={"WINE_FAIR": {"available": True}})])
        x = self.AD.run_many(self.AD.DEMO, X, self.inp)
        cmp = self.AD.compare(self.con["personas"], x["personas"], "13:00")
        joined = [v["cls"] for v in cmp.values()]
        self.assertTrue(any("행사 참여" in c for c in joined))
        self.assertTrue(any(c.startswith("원래 일정 유지") for c in joined))
        for p in self.AD.DEMO:   # 개입 전(13:00 이전) 행동은 그대로
            b = [y for y in self.con["personas"][p]["log"] if self.AD.hm(y["e"]) <= self.AD.hm("13:00")]
            c = [y for y in x["personas"][p]["log"] if self.AD.hm(y["e"]) <= self.AD.hm("13:00")]
            self.assertEqual([(y["t"], y["act"]) for y in b], [(y["t"], y["act"]) for y in c], p)

    def test_runner_rejects_and_no_private_strings(self):
        run = lambda q: json.loads(subprocess.run([sys.executable, str(HERE / "autonomy_run.py")], input=json.dumps(q), capture_output=True, text=True, timeout=120).stdout)
        self.assertIn("error", run({"op": "run", "personas": ["N08"]}))
        self.assertIn("error", run({"op": "run", "personas": ["A07"], "intervention": "free"}))
        self.assertIn("error", run({"op": "run", "personas": ["A07"], "seed": -1}))
        s = json.dumps(run({"op": "run", "personas": self.AD.DEMO, "mode": "many", "intervention": "wine_fair_1300", "compare": True}), ensure_ascii=False)
        self.assertFalse(re.search(r"/private/|/Users/|/home/|\.local\.json|blog\.naver|\"gist\"", s))


@unittest.skipUnless(LOCAL.exists(), "로컬 전용 프로필 없음")
class CL19(unittest.TestCase):
    """CL-19 — 결함 수정 · LLM 계층 폴백 · mock 구분 · 재방문 근거 · 예약 마감 포기 · 문맥 어댑터 비식별."""
    @classmethod
    def setUpClass(cls):
        import os
        for k in ("HILLINK_LLM_ENABLED", "HILLINK_LLM_MOCK", "OPENAI_API_KEY"):
            os.environ.pop(k, None)
        from operator_choice.autonomy_v1 import agent_day as AD, llm_layer as LL, profile_context as PC
        cls.AD, cls.LL, cls.PC = AD, LL, PC
        cls.inp = AD.load_inputs()
        cls.ind = {p: AD.run_one(p, AD.scenario("base"), cls.inp) for p in AD.DEMO}

    def acts(self, r): return [x for x in r["log"] if x["act"] not in ("move", "wait")]

    def test_checkout_deadline_and_end_state(self):
        for p, r in self.ind.items():
            L = self.acts(r)
            co = [x for x in L if x["act"] == "checkout"]
            if co:
                self.assertLessEqual(self.AD.hm(co[0]["e"]), self.AD.hm("11:00"), p)
                self.assertFalse(any(x["loc"] in self.AD.SP.GUEST_ONLY for x in L if self.AD.hm(x["t"]) >= self.AD.hm(co[0]["e"])), p)
            self.assertTrue(any(k in L[-1]["label"] for k in ("귀가", "취침")), f"{p} 하루 끝 상태 {L[-1]['label']}")

    def test_no_same_venue_two_meals_and_no_food_right_after_food(self):
        for p, r in self.ind.items():
            L = self.acts(r)
            v = [self.AD.LUNCH_ENGINE.get(x["act"], x["act"]) for x in L if x["domain"] == "식사" and x["act"] != "lunch_skip" and "BREAKFAST" not in x["act"]]
            self.assertEqual(len(v), len(set(v)), f"{p} 같은 업장 두 끼 {v}")
            food = [x for x in L if x["domain"] in ("식사", "카페") and x["act"] != "lunch_skip"]
            for a, b in zip(food, food[1:]):
                self.assertFalse(a["loc"] == b["loc"] and self.AD.hm(b["t"]) - self.AD.hm(a["e"]) < 240, f"{p} 같은 곳 연속 {a['t']}→{b['t']}")

    def test_no_identical_consecutive_rest_and_time_words(self):
        for p, r in self.ind.items():
            L = self.acts(r)
            for a, b in zip(L, L[1:]):
                self.assertFalse(a["act"] == b["act"] and a["act"] in ("room_rest", "ROOM_REST", "room_bath"), f"{p} 같은 휴식 연속 {b['t']}")
            for x in L:
                if "늦은 오후" in x["why"]:
                    self.assertGreaterEqual(self.AD.hm(x["t"]), self.AD.hm("15:00"), f"{p} {x['t']} 늦은 오후")

    def test_llm_planner_without_key_falls_back_to_rules(self):
        self.LL.USAGE.reset("t")
        for p in ("A07", "blog42"):
            r = self.AD.run_one(p, self.AD.scenario("base", planner="llm"), self.inp)
            self.assertEqual([(x["t"], x["act"]) for x in r["log"]], [(x["t"], x["act"]) for x in self.ind[p]["log"]], p)
            self.assertEqual(r["summary"]["llm_actions"], 0)
        u = self.LL.USAGE.summary()
        self.assertEqual(u["mode"], "rule_only"); self.assertEqual(u["total"]["real_api_calls"], 0); self.assertTrue(u["zero_call_reason"])

    def test_mock_is_labelled_and_not_counted_as_real(self):
        import os
        os.environ.update(HILLINK_LLM_ENABLED="1", HILLINK_LLM_MOCK="1")
        try:
            self.LL.USAGE.reset("mock")
            r = self.AD.run_one("A07", self.AD.scenario("base", planner="llm"), self.inp)
            u = self.LL.USAGE.summary()
            self.assertIn("mock", u["mode"]); self.assertEqual(u["total"]["real_api_calls"], 0); self.assertEqual(u["total"]["cost_usd"], 0)
            self.assertGreater(r["summary"]["llm_actions"], 0)   # 의도가 실제 행동 선택으로 이어짐(장식 아님)
            tr = [x for x in r["trace"] if x["backend"] == "llm"]
            self.assertTrue(tr and all("accepted" in x and "need" in x for x in tr))
        finally:
            os.environ.pop("HILLINK_LLM_ENABLED"); os.environ.pop("HILLINK_LLM_MOCK"); self.LL.USAGE.reset("t")

    def test_budget_includes_prior_runs(self):
        self.LL.USAGE.reset("b"); self.LL.USAGE.prior = dict(calls=30, cost_usd=0.0)
        try:
            self.assertFalse(self.LL.USAGE.can_call(0.001)); self.assertIn("한도", self.LL.USAGE.stopped)
        finally:
            self.LL.USAGE.prior = dict(calls=0, cost_usd=0.0)

    def test_revisit_needs_review_evidence(self):
        a = self.AD.Agent("A07", *self.inp, self.AD.scenario("x"))
        w = self.AD.World(self.AD.scenario("x"))
        a.used.add("PIZZA_HILL"); a.t = self.AD.hm("12:00"); a.loc = a.room; a.meals["breakfast"] = True
        rej = {}
        self.assertIsNone(self.AD.plan_ok(a, "lunch_pizzahill", a.t, w, rej))
        it = dict(option="lunch_pizzahill", why="", fact_ids=[], alternatives=[], keep_or_change="유지", dropped_fact_ids=[])
        ok, why = self.LL.execute(a, w, a.t, it)
        self.assertFalse(ok); self.assertIn("재방문 근거", why)

    def test_reservation_full_leads_to_abandon_and_alternative(self):
        X = self.AD.scenario("pz", changes=[dict(at="15:00", label="피자힐 저녁 마감", closed={"PIZZA_HILL": ["17:30", "20:30"]})])
        base = self.AD.run_many(self.AD.DEMO, self.AD.scenario("base"), self.inp)["personas"]
        x = self.AD.run_many(self.AD.DEMO, X, self.inp)["personas"]
        cmp = self.AD.compare(base, x, "15:00", event=False)
        gave = [p for p, v in cmp.items() if v["cls"] == "이용 포기 · 대안 선택"]
        self.assertTrue(gave)
        for p in gave:
            self.assertTrue(cmp[p]["alternative"]); self.assertNotIn("PIZZA_HILL", [y["act"] for y in x[p]["log"] if self.AD.hm(y["t"]) >= self.AD.hm("17:30")])

    def test_profile_context_is_deidentified_and_owned(self):
        import json as J
        for p in self.AD.DEMO:
            a = self.AD.Agent(p, *self.inp, self.AD.scenario("x"))
            b, cite, cov = self.PC.context(a)
            s = J.dumps(b, ensure_ascii=False)
            self.assertFalse(re.search(r"https?://|blog\.naver|/Users/|/home/", s), p)
            self.assertFalse(a.staff and self.PC.staff_re(a).search(s), p)   # 담당 분석가 이름(라이브러리 owner)이 문맥에 없음
            self.assertTrue(all(a.gist(f) for f in cite), p)
            self.assertGreater(sum(cov["sent"].values()), 10, p)


@unittest.skipUnless(LOCAL.exists(), "로컬 전용 프로필 없음")
class CL19Followup(unittest.TestCase):
    """CL-19 후속 — 공통 장부(끼니 · 지출 · 출입) · 집계 정의 · 재생 전용 · 적대 시험 · 출처 맥락."""
    @classmethod
    def setUpClass(cls):
        import os
        for k in ("HILLINK_LLM_ENABLED", "HILLINK_LLM_MOCK", "HILLINK_LLM_REPLAY", "OPENAI_API_KEY"):
            os.environ.pop(k, None)
        from operator_choice.autonomy_v1 import agent_day as AD, llm_layer as LL, ledger as LG, profile_context as PC
        cls.AD, cls.LL, cls.LG, cls.PC = AD, LL, LG, PC
        cls.inp = AD.load_inputs()
        cls.ind = {p: AD.run_one(p, AD.scenario("base"), cls.inp) for p in AD.DEMO}

    def test_every_meal_event_sets_meal_state_regardless_of_source(self):
        for p, r in self.ind.items():
            for x in r["log"]:
                if x["domain"] == "식사" and x["act"] not in ("lunch_skip",):
                    slot = self.LG.meal_slot(self.AD.hm(x["t"]))
                    if slot:
                        self.assertEqual(x.get("meal_slot"), slot, f"{p} {x['t']} {x['act']}")
                        self.assertTrue(r["summary"]["meals"][slot], f"{p} {slot}")

    def test_spend_equals_sum_of_known_charges_and_unknown_is_not_zero(self):
        for p, r in self.ind.items():
            ch = [x["charge"] for x in r["log"] if x.get("charge")]
            self.assertEqual(r["summary"]["spent_known_krw"], sum(c["krw"] or 0 for c in ch), p)
            for c in ch:
                if c["status"] == "가격 미정":
                    self.assertIsNone(c["krw"], p)
                if c["status"] == "유료":
                    self.assertGreater(c["krw"], 0, p)
            for x in r["log"]:   # 사 먹은 식사는 '구매 없음'이 아님 (외부 배달은 호텔 매출 0 · 외부 지출 금액 미상으로 따로 표시)
                if x["act"] == "EXTERNAL_DELIVERY":
                    self.assertEqual(x["charge"]["status"], "구매 없음"); self.assertIsNone(x["charge"]["external_spend"]["amount_krw"])
                    self.assertEqual(x["charge"]["external_spend"]["hotel_revenue_krw"], 0)
                    continue
                if x["domain"] == "식사" and x["act"] not in ("lunch_skip",) and x.get("charge"):
                    self.assertNotEqual(x["charge"]["status"], "구매 없음", f"{p} {x['act']}")

    def test_non_guest_access_follows_validator_table(self):
        for p, r in self.ind.items():
            for x in r["log"]:
                if x["act"] in ("move", "wait"):
                    continue
                stay_now = r["visit"]["stay"]
                if not stay_now and x["loc"] in ("SKYARD", "FOREST_PARK", "VISTA_POOL", "GRAND_POOL", "TENNEZ_PARK", "GRAND_LIBRARY"):
                    self.fail(f"{p} 비투숙 {x['act']} @ {x['loc']}")

    def test_count_definitions_are_separate(self):
        for p, r in self.ind.items():
            s = r["summary"]
            self.assertEqual(s["timeline_actions"], s["n_actions"])
            self.assertEqual(s["idle_blocks"], sum(1 for x in r["log"] if x["act"] == "idle"))
            self.assertLessEqual(s["llm_accepted"] + s["llm_rejected"], s["llm_intents"] + 0)

    def test_replay_mode_never_calls_network(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        os.environ.update(HILLINK_LLM_ENABLED="1", HILLINK_LLM_REPLAY="1", HILLINK_LLM_CACHE=d)
        real = self.LL.urllib.request.urlopen
        self.LL.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network"))
        try:
            self.LL.USAGE.reset("replay")
            r = self.AD.run_one("A07", self.AD.scenario("base", planner="llm"), self.inp)
            u = self.LL.USAGE.summary()
            self.assertEqual(u["total"]["real_api_calls"], 0); self.assertIn("replay", u["mode"])
            self.assertEqual([(x["t"], x["act"]) for x in r["log"]], [(x["t"], x["act"]) for x in self.ind["A07"]["log"]])   # 캐시 없음 → 규칙과 같음
        finally:
            self.LL.urllib.request.urlopen = real
            for k in ("HILLINK_LLM_ENABLED", "HILLINK_LLM_REPLAY", "HILLINK_LLM_CACHE"):
                os.environ.pop(k, None)
            self.LL.USAGE.reset("t")

    def test_redteam_validator_rejects_violations(self):
        import subprocess, sys, tempfile, json as J
        d = tempfile.mkdtemp()
        subprocess.run([sys.executable, "-m", "operator_choice.autonomy_v1.redteam_cl19", "--out", d], cwd=str(HERE.parent / "experiments" / "persona_live"), check=True, capture_output=True, timeout=600)
        R = J.load(open(d + "/redteam_cl19.json", encoding="utf-8"))
        self.assertTrue(all(r["passed"] for r in R), [r["case"] for r in R if not r["passed"]])

    def test_other_place_experience_is_inference_not_review(self):
        for p, r in self.ind.items():
            a = self.AD.Agent(p, *self.inp, self.AD.scenario("x"))
            for x in r["log"]:
                for e in x["evidence"]:
                    if e["type"] == "후기에서 확인":
                        for f in e["fact_ids"]:
                            self.assertEqual(self.PC.fact_context(a, f), "wh", f"{p} {x['act']} {f}")   # 워커힐 직접 경험만(다른 곳 · 미확정은 추론)

    def test_one_label_each_and_no_review_phrase_without_review(self):
        for p, r in self.ind.items():
            for x in r["log"]:
                types = [e["type"] for e in x["evidence"]]
                self.assertEqual(len(types), len(set(types)), f"{p} {x['t']} 중복 라벨")
                if "후기에서 확인" not in types:
                    self.assertNotIn("후기에서도 같은 경험이 확인됩니다", x["why"], f"{p} {x['t']}")

    def test_unknown_hours_not_opened_and_night_wind_down(self):
        for p, r in self.ind.items():
            self.assertFalse(any(x["act"] == "tennez" for x in r["log"]), p)   # 운영시간 자료 없음
            L = [x for x in r["log"] if x["act"] not in ("move", "wait")]
            if r["visit"]["stay"] and not any(x["act"] == "checkout" for x in L):
                self.assertTrue(any(x["act"] == "sleep" for x in L), p)


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
