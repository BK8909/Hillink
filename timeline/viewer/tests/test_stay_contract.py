"""CL-1024-12 긴급 보충 — 하이브리드 계약 단위 테스트.
① Codex CD-1024-06 월드 반례 8건(통과 / 수정 가능 / 실행 차단 구분) ② 정량 결정 잠금 · 자동 수정 중 보존 · 차단 계획 미출력
③ 규칙/LLM 경로 분리(가짜 LLM — 외부 호출 없음) ④ QA 프로파일 실제 로드 · SHA 검증 · daily 축소 모드 · 미등록 명시 실패
⑤ 고객별 행동 차이 · 데이터 제거 대조(유형 대본 + ID 교체 방식이 아님을 확인) ⑥ 원문 인용 · URL 미출력.
QA 원자료는 저장소에 없다 — HILLINK_QA_PROFILE_ROOT 가 가리키는 비공개 경로에 batch4/5 패키지가 있을 때만 ④⑤⑥ 실데이터 검사(없으면 skip).
실행: 저장소 루트에서  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest timeline.viewer.tests.test_stay_contract -v
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "timeline/experiments/persona_live"))
sys.path.insert(0, str(ROOT / "timeline/viewer"))
from operator_choice.operator_world_v1_1 import stay_planner as SP  # noqa: E402
from operator_choice.operator_world_v1_1 import stay_qa_profiles as QA  # noqa: E402
from operator_choice.operator_world_v1_1.turn_view import load_all_personas  # noqa: E402

STAY = ROOT / "timeline/viewer/stay_run.py"
QROOT = os.environ.get("HILLINK_QA_PROFILE_ROOT", "")
ELEVEN = ["A01", "A02", "A03", "A04", "A05", "A07", "A08", "A10", "blog41", "blog42", "blog43"]
TRACKED8 = ["A02", "A04", "A05", "A07", "A10", "blog41", "blog42", "blog43"]   # 로컬 확장 파일 없이도 등록되는 고객
DEC = [
    {"turn": "event", "time": "16:30", "loc": "SKYARD", "label": "행사", "product_label": "스카이야드", "venue_id": "SKYARD"},
    {"turn": "dinner", "time": "18:30", "loc": "PIZZA_HILL", "label": "저녁", "product_label": "피자힐", "venue_id": "PIZZA_HILL"},
]
COND = {"stay": True, "building": "VISTA", "party_size": 2, "phase": "mid", "event": True}


def run(q, env=None):
    e = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "OPENAI_API_KEY": ""}
    e.update(env or {})
    r = subprocess.run([sys.executable, str(STAY)], input=json.dumps(q, ensure_ascii=False), capture_output=True, text=True, cwd=ROOT, env=e, timeout=90, check=True)
    return r.stdout, json.loads(r.stdout)


def sc(t0, t1, loc, act="activity", layer="generated", **kw):
    return dict(t0=t0, t1=t1, loc=loc, act=act, layer=layer, **kw)


def has_qa(pid):
    if not QROOT:
        return False
    old = os.environ.get(QA.ENV)
    os.environ[QA.ENV] = QROOT
    try:
        return QA._find(pid)[1] is not None
    finally:
        if old is None: os.environ.pop(QA.ENV, None)
        else: os.environ[QA.ENV] = old


# ------------------------------------------------------------------ ① Codex CD-1024-06 반례 8건(hybrid_world_negative_cases.csv 와 같은 입력)
FIXED = [{"turn": "event", "time": "16:30", "loc": "SKYARD", "product_label": "WINE_FAIR"}]
CASES = [
    ("unknown_place", [sc(900, 930, "UNKNOWN_X")], [], "UNKNOWN_PLACE", "blocked"),
    ("short_travel", [sc(900, 930, "VISTA_LOBBY"), sc(930, 960, "GRAND_LOBBY")], [], "TRAVEL_GAP", "fixable"),
    ("decision_time_changed", [sc(700, 760, "SKYARD", "turn_event", "engine", turn="event", product="WINE_FAIR")], FIXED, "DECISION_TIME_CHANGED", "blocked"),
    ("decision_product_changed", [sc(990, 1065, "SKYARD", "turn_event", "engine", turn="event", product="OTHER")], FIXED, "DECISION_PRODUCT_CHANGED", "blocked"),
    ("decision_removed", [sc(900, 930, "VISTA_LOBBY")], FIXED, "DECISION_MISSING_OR_DUPLICATED", "blocked"),
    ("closed_facility", [sc(60, 90, "VISTA_POOL")], [], "CLOSED_FACILITY", "fixable"),
    ("overlap", [sc(900, 930, "VISTA_LOBBY"), sc(920, 950, "VISTA_LOBBY")], [], "OVERLAP", "fixable"),
    ("after_checkout", [sc(660, 680, "GRAND_LOBBY", "checkout"), sc(700, 730, "GRAND_LIBRARY")], [], "ACTIVITY_AFTER_CHECKOUT", "fixable"),
]


class CodexEightCounterexamples(unittest.TestCase):
    def test_all_eight_detected_with_severity(self):
        rows = []
        for name, S, fixed, code, sev in CASES:
            r = SP.check(S, fixed)
            codes = {x["code"]: x["severity"] for x in r["issues"]}
            rows.append((name, code in codes, codes.get(code), r["verdict"]))
            self.assertIn(code, codes, (name, r))
            self.assertEqual(codes[code], sev, (name, r))
            self.assertNotEqual(r["verdict"], "pass", name)
        self.assertEqual(sum(1 for r in rows if r[1]), 8)

    def test_engine_travel_gap_is_blocked(self):
        """엔진 결정 두 개 사이 이동 불가능 → 결정을 움직여야 고칠 수 있음 → 실행 차단."""
        S = [sc(990, 1065, "SKYARD", "turn_event", "engine", turn="event"), sc(1066, 1150, "PIZZA_HILL", "turn_dinner", "engine", turn="dinner")]
        r = SP.check(S, [])
        self.assertEqual(r["verdict"], "blocked", r)

    def test_normal_rules_plan_passes(self):
        P = load_all_personas()
        prof = SP.profile("A10", P["A10"], [], {})
        out = SP.plan(prof, DEC, dict(COND, phase="checkin"), {"n": 2, "rel": "friend"}, 7, "rules")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["validation"]["final"]["verdict"], "pass")
        anchors = [(s["turn"], s["t0"], s["loc"], s.get("product")) for s in out["scenes"] if s["layer"] == "engine"]
        self.assertEqual(anchors, [("event", 990, "SKYARD", "스카이야드"), ("dinner", 1110, "PIZZA_HILL", "피자힐")])


# ------------------------------------------------------------------ ② 잠금 · 자동 수정 · 차단
class DecisionLock(unittest.TestCase):
    def setUp(self):
        P = load_all_personas()
        self.prof = SP.profile("A10", P["A10"], [], {})

    def test_lock_object(self):
        lk = SP.make_lock(DEC)
        self.assertEqual(lk["n"], 2)
        self.assertEqual([x["product_id"] for x in lk["items"]], ["SKYARD", "PIZZA_HILL"])
        self.assertTrue(SP.lock_intact(lk))
        bad = copy.deepcopy(lk); bad["items"][0]["time"] = "10:00"
        self.assertFalse(SP.lock_intact(bad))

    def test_autofix_preserves_decisions(self):
        """수정 가능 오류(영업시간 밖 · 이동 부족 · 체크아웃 뒤)를 고쳐도 엔진 결정 장면은 그대로."""
        S = [sc(60, 90, "VISTA_POOL", "pool"), sc(900, 960, "VISTA_LOBBY", "x"), sc(962, 985, "FOREST_PARK", "forest_walk"),
             sc(990, 1065, "SKYARD", "turn_event", "engine", turn="event", product="스카이야드", venue_id="SKYARD"),
             sc(1110, 1200, "PIZZA_HILL", "turn_dinner", "engine", turn="dinner", product="피자힐", venue_id="PIZZA_HILL")]
        self.assertEqual(SP.check(S, DEC)["verdict"], "fixable")
        F, log = SP.autofix(S, DEC)
        self.assertEqual(SP.check(F, DEC)["verdict"], "pass", (F, log))
        self.assertEqual([(x["t0"], x["t1"], x["loc"], x["product"]) for x in F if x["layer"] == "engine"],
                         [(990, 1065, "SKYARD", "스카이야드"), (1110, 1200, "PIZZA_HILL", "피자힐")])
        self.assertTrue(log)

    def test_rules_preserve(self):
        out = SP.plan(self.prof, DEC, dict(COND, phase="checkin"), {"n": 2, "rel": "friend"}, 7, "rules")
        self.assertTrue(out["decision_context_preserved"])
        self.assertTrue(out["lock"]["intact"])

    def test_llm_cannot_override(self):
        """가짜 LLM 이 결정을 다른 시각 · 상품으로 바꾸면 → 실행 차단 판정 · 규칙 계획기로 대체 · 대체 이유 · 결정 보존."""
        bad = [{"t0": 600, "t1": 660, "loc": "SKYARD", "act": "turn_event", "layer": "engine", "turn": "event", "product": "다른 상품", "key": True},
               {"t0": 1110, "t1": 1200, "loc": "PIZZA_HILL", "act": "turn_dinner", "layer": "engine", "turn": "dinner", "product": "피자힐", "venue_id": "PIZZA_HILL", "key": True}]
        orig_av, orig_llm = SP.llm_available, SP.plan_llm
        SP.llm_available = lambda: True
        SP.plan_llm = lambda *a, **k: [dict(x) for x in bad]
        try:
            out = SP.plan(self.prof, DEC, dict(COND, phase="checkin"), {"n": 2}, 7, "llm")
        finally:
            SP.llm_available, SP.plan_llm = orig_av, orig_llm
        self.assertEqual(out["requested"], "llm")
        self.assertEqual(out["backend"], "rules", "검증 실패한 LLM 계획을 실제 사용으로 표시하면 안 됨")
        self.assertIn("실행 차단", out["fallback_reason"])
        self.assertEqual(out["validation"]["first"]["verdict"], "blocked")
        anchors = [(s["turn"], s["t0"], s.get("product")) for s in out["scenes"] if s["layer"] == "engine"]
        self.assertEqual(anchors, [("event", 990, "스카이야드"), ("dinner", 1110, "피자힐")])

    def test_no_key_is_reported_as_rules(self):
        orig = SP.llm_available
        SP.llm_available = lambda: False
        try:
            out = SP.plan(self.prof, DEC, dict(COND, phase="checkin"), {"n": 2}, 7, "auto")
        finally:
            SP.llm_available = orig
        self.assertEqual(out["backend"], "rules")
        self.assertIn("키", out["fallback_reason"])
        self.assertIsNone(out["llm"])

    def test_product_id_lock_with_ui_fields(self):
        """화면이 보내는 잠금 필드(결정 ID · 상품 ID ≠ 장소 ID · 참여 · 대안 · 출처)로도 정상 계획은 통과, 상품 ID 를 바꾸면 차단."""
        dec = [{"decision_id": "A10|event|16:30", "turn": "event", "time": "16:30", "loc": "FOREST_PARK", "product_id": "WINE_FAIR", "product_label": "와인페어", "venue_id": "FOREST",
                "participation": "participate", "alternatives": ["FOOTBATH"], "source": "turn_view"}]
        out = SP.plan(self.prof, dec, dict(COND, phase="checkin"), {"n": 2}, 7, "rules")
        self.assertEqual(out["status"], "ok", out["validation"])
        self.assertEqual(out["lock"]["items"][0]["product_id"], "WINE_FAIR")
        S = [dict(x) for x in out["scenes"]]
        next(x for x in S if x["layer"] == "engine")["product_id"] = "FOOTBATH"
        self.assertIn("DECISION_PRODUCT_CHANGED", {x["code"] for x in SP.check(S, dec)["issues"]})

    def test_impossible_decisions_blocked_not_played(self):
        """정량 결정끼리 겹쳐 월드에서 불가능 → 장면을 내보내지 않음(status=blocked)."""
        dec = [dict(DEC[0]), dict(DEC[1], time="16:45")]
        out = SP.plan(self.prof, dec, dict(COND, phase="checkin"), {"n": 2}, 7, "rules")
        self.assertEqual(out["status"], "blocked", out["validation"])
        self.assertEqual(out["scenes"], [])
        self.assertFalse(out["decision_context_preserved"])


# ------------------------------------------------------------------ ④ QA 프로파일 로드 · 미등록
class Registration(unittest.TestCase):
    def test_unregistered_without_root_is_generic_fallback(self):
        _, d = run({"op": "plan", "personas": ["A14"], "cond": dict(COND, phase="checkin"), "decisions": {"A14": DEC}, "seed": 1, "backend": "rules"}, {QA.ENV: ""})
        t = d["plans"]["A14"]["trace"]
        self.assertFalse(d["plans"]["A14"]["registered"])
        self.assertEqual(t["profile_source"], "generic_demo_fallback")
        self.assertEqual(t["profile_fallback_used"], "generic_demo_fallback")
        self.assertFalse(t["profile_loaded"])
        self.assertFalse(t["planner_inputs_verified"])

    def test_unregistered_strict_fails(self):
        _, d = run({"op": "plan", "personas": ["A14"], "cond": COND, "decisions": {"A14": DEC}, "seed": 1, "strict_profiles": True}, {QA.ENV: ""})
        self.assertEqual(d["plans"]["A14"]["status"], "error")
        self.assertEqual(d["plans"]["A14"]["scenes"], [])

    def test_registered_eleven_present(self):
        """본제품 11명 = 저장소 추적 8명 + 로컬 확장(turn_personas_ext.local.json · 비공개 · 저장소 밖) 3명(A01 · A03 · A08)."""
        P = load_all_personas()
        for pid in TRACKED8:
            self.assertIn(pid, P)
        ext = ROOT / "timeline/experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json"
        if ext.exists():
            for pid in ("A01", "A03", "A08"):
                self.assertIn(pid, P)
        for pid in ["A14", "A23", "A26", "N08"]:
            self.assertNotIn(pid, P, "QA 후보가 본제품 등록부에 편입되면 안 됨")

    def test_registered_trace_fields(self):
        _, d = run({"op": "plan", "personas": ["A07"], "cond": COND, "decisions": {"A07": DEC}, "seed": 1, "backend": "auto"}, {QA.ENV: ""})
        t = d["plans"]["A07"]["trace"]
        for k in ("profile_loaded", "daily_behavior_loaded", "decision_context_preserved", "planner_inputs_verified", "profile_fallback_used",
                  "backend_requested", "backend_used", "planner_backend_fallback_used", "fallback_reason", "structured_sha256", "daily_sha256", "scene_sources"):
            self.assertIn(k, t)
        self.assertEqual(t["profile_source"], "registry")
        self.assertTrue(t["daily_missing_reason"])
        self.assertEqual(t["backend_requested"], "auto"); self.assertEqual(t["backend_used"], "rules"); self.assertTrue(t["planner_backend_fallback_used"])


def _pkg_copy(pid, tmp, with_daily=True, tamper=False):
    """batch 패키지에서 한 고객만 임시 패키지로 복사(체크섬 포함) — daily 누락 · SHA 불일치 상황 재현."""
    os.environ[QA.ENV] = QROOT
    pkg, d = QA._find(pid)
    dst = Path(tmp) / "PKG" / "profiles" / pid
    dst.mkdir(parents=True)
    shutil.copy(d / "structured_profile.json", dst / "structured_profile.json")
    lines = [l for l in (pkg / "checksums.sha256").read_text(encoding="utf-8").splitlines() if f"profiles/{pid}/structured_profile.json" in l]
    if with_daily:
        shutil.copy(d / "daily_behavior_profile.json", dst / "daily_behavior_profile.json")
        lines += [l for l in (pkg / "checksums.sha256").read_text(encoding="utf-8").splitlines() if f"profiles/{pid}/daily_behavior_profile.json" in l]
    (Path(tmp) / "PKG" / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if tamper:
        with open(dst / "structured_profile.json", "a", encoding="utf-8") as f: f.write(" ")
    return str(Path(tmp) / "PKG")


@unittest.skipUnless(has_qa("A23") and has_qa("A26"), "비공개 QA 패키지(batch4/5) 없음 — HILLINK_QA_PROFILE_ROOT")
class QAProfileIntegration(unittest.TestCase):
    PIDS = ["A23", "N08", "N32", "N23", "A26", "A28", "N03", "N20"]

    def plan_of(self, pid, seed=3, env=None):
        raw, d = run({"op": "plan", "personas": [pid], "cond": COND, "decisions": {pid: DEC}, "seed": seed, "backend": "rules"}, env or {QA.ENV: QROOT})
        return raw, d["plans"][pid]

    def test_eight_loaded_and_verified(self):
        for pid in self.PIDS:
            _, p = self.plan_of(pid)
            t = p["trace"]
            self.assertEqual(t["profile_source"], "qa_profile", pid)
            self.assertTrue(t["profile_loaded"] and t["daily_behavior_loaded"] and t["sha_verified"], (pid, t))
            self.assertTrue(t["planner_inputs_verified"], (pid, p["inputs_used"]))
            self.assertTrue(t["decision_context_preserved"], pid)
            self.assertFalse(p["registered"])
            self.assertEqual(p["status"], "ok")

    def test_blocked_import_facts_excluded(self):
        for pid, fid in (("N20", "N20-F009"), ("N03", "N03-F001")):
            raw, p = self.plan_of(pid)
            self.assertIn(fid, p["trace"]["qa_inputs"]["blocked_facts"])
            self.assertNotIn(fid, json.dumps(p["scenes"], ensure_ascii=False))

    def test_customers_differ_under_same_world(self):
        """같은 월드 · 같은 결정 · 같은 시드에서 고객별 활동과 이유가 다르고, 이유의 근거 ID 가 각자 자기 것."""
        A = {pid: self.plan_of(pid)[1] for pid in ("A23", "A26", "N23")}
        acts = {pid: [s["act"] for s in p["scenes"] if s["layer"] != "engine"] for pid, p in A.items()}
        self.assertNotEqual(acts["A23"], acts["A26"]); self.assertNotEqual(acts["A26"], acts["N23"]); self.assertNotEqual(acts["A23"], acts["N23"])
        for pid, p in A.items():
            ids = set(p["inputs_used"]["fact_ids"]) | set(p["inputs_used"]["trait_fact_ids"])
            self.assertTrue(ids and all(i.startswith(pid + "-") for i in ids), (pid, ids))

    def test_ablation_data_drives_plan(self):
        """같은 ID · 같은 시드에서 프로파일 자료(사실 · 일상 · 성향)를 비우면 계획이 달라진다 — 유형 대본 + ID 교체가 아님."""
        os.environ[QA.ENV] = QROOT
        raw, st = QA.load("A26")
        P, _ = SP.qa_profile("A26", raw, st)
        full = SP.plan(P, DEC, COND, {"n": 2, "rel": "friends"}, 3, "rules")
        E = copy.deepcopy(P)
        E["facts"], E["fact_hits"], E["daily_hits"], E["trait_evidence"] = [], {}, {}, {}
        E["bars"] = {k: 0.0 for k in E["bars"]}; E["facets"] = {k: 0.0 for k in E["facets"]}
        empty = SP.plan(E, DEC, COND, {"n": 2, "rel": "friends"}, 3, "rules")
        self.assertNotEqual([s["act"] for s in full["scenes"]], [s["act"] for s in empty["scenes"]])
        self.assertEqual([(s["turn"], s["t0"]) for s in full["scenes"] if s["layer"] == "engine"], [(s["turn"], s["t0"]) for s in empty["scenes"] if s["layer"] == "engine"])

    def test_no_quotes_or_urls_in_output(self):
        os.environ[QA.ENV] = QROOT
        for pid in ("A23", "N08"):
            raw_out, _ = self.plan_of(pid)
            _, vis = run({"op": "visit", "personas": [pid], "cond": {"event": True}, "seed": 1}, {QA.ENV: QROOT})
            sp = QA.load(pid)[0]["sp"]
            anchors = [a.get("quote") if isinstance(a, dict) else str(a) for f in sp["STRUCTURED_PROFILE"]["facts"] for a in (f.get("anchors") or [])]
            blob = raw_out + json.dumps(vis, ensure_ascii=False)
            for q in anchors:
                if q and len(q) >= 12:
                    self.assertNotIn(q[:40], blob, pid)
            self.assertNotIn("http", blob)
            self.assertNotIn("source_location_private", blob)
            self.assertNotIn(QROOT, blob)

    def test_daily_missing_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _pkg_copy("A26", tmp, with_daily=False)
            _, p = self.plan_of("A26", env={QA.ENV: root})
            t = p["trace"]
            self.assertTrue(t["profile_loaded"]); self.assertFalse(t["daily_behavior_loaded"])
            self.assertIn("daily", t["daily_missing_reason"]); self.assertEqual(p["inputs_used"]["daily_slots"], [])

    def test_sha_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _pkg_copy("A26", tmp, tamper=True)
            _, p = self.plan_of("A26", env={QA.ENV: root})
            self.assertEqual(p["trace"]["profile_source"], "generic_demo_fallback")
            self.assertIn("SHA", p["trace"]["load_error"])


if __name__ == "__main__":
    unittest.main()
