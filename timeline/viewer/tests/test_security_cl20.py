"""CL-1024-20 P0-S2 — 공개 · 비공개 API 경계(원문 링크 · /api/lab 입력 · 오류 문장 · 정적 검수 색인 · /api/turn 게시 승인).
서버를 임시 포트로 띄워(기본 · 공개 모드) 실제 HTTP 로 확인한다. python3 -m unittest tests.test_security_cl20 (timeline/viewer 에서)"""
import json, os, re, socket, subprocess, sys, time, unittest, urllib.request, urllib.error
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
LEAK = re.compile(r"/home/|/Users/|/private/|Traceback|File \"|https?://")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Server:
    def __init__(self, env):
        self.port = free_port()
        self.p = subprocess.Popen([sys.executable, "app.py", "--port", str(self.port), "--no-browser"], cwd=str(HERE), env={**os.environ, **env},
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=2); return
            except Exception:
                time.sleep(0.2)

    def call(self, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def stop(self):
        self.p.terminate(); self.p.wait(timeout=10)


class SecurityBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env0 = {k: "" for k in ("HILLINK_REVIEWER_LOCAL", "HILLINK_PUBLISH_OVERRIDE")}
        cls.local = Server({**env0, "HILLINK_DEPLOY": "local"})
        cls.public = Server({**env0, "HILLINK_DEPLOY": "public", "HILLINK_REVIEWER_LOCAL": "1"})

    @classmethod
    def tearDownClass(cls):
        cls.local.stop(); cls.public.stop()

    def test_review_link_never_without_reviewer(self):
        for s in (self.local, self.public):
            st, b = s.call("/api/review", {"blog": "blog41"})
            self.assertNotIn('"link"', b); self.assertFalse(re.search(r"https?://", b))

    def test_lab_rejects_unregistered_input(self):
        for s in (self.local, self.public):
            for bad in ({"blog": "../../etc", "var": "winefair"}, {"blog": "os.path", "var": "winefair"}, {"blog": "blog41", "var": "__import__"}, ["x"]):
                st, b = s.call("/api/lab", bad)
                self.assertIn(st, (400, 403), bad); self.assertFalse(LEAK.search(b), b)

    def test_errors_do_not_leak_internals(self):
        for s in (self.local, self.public):
            for path, body in (("/api/lab", {"blog": "blog99", "var": "winefair"}), ("/api/stay", {"op": "nope", "personas": ["A07"]})):
                st, b = s.call(path, body)
                self.assertGreaterEqual(st, 400); self.assertFalse(LEAK.search(b), b); self.assertNotIn("RuntimeError", b)

    def test_static_review_indexes_hidden(self):
        for s in (self.local, self.public):
            for f in ("team_review_index.json", "pref_eval.json", "persona_publish.json", "persona_library.json", "persona_links.local.json"):
                st, _ = s.call(f"/static/{f}")
                self.assertEqual(st, 404, f)

    def test_turn_only_published(self):
        st, b = self.local.call("/api/turn", {"op": "view", "turn": "dinner", "personas": ["N08"]})
        self.assertEqual(st, 403)
        st, b = self.public.call("/api/turn/meta?turn=dinner")
        self.assertEqual(json.loads(b).get("personas"), [])   # 공개 모드 외부 공개 승인 0명
        st, b = self.public.call("/api/turn", {"op": "view", "turn": "dinner", "personas": ["A07"]})
        self.assertEqual(st, 403)
        st, b = self.local.call("/api/turn/meta?turn=dinner")
        self.assertEqual(len(json.loads(b)["personas"]), 11)


if __name__ == "__main__":
    unittest.main()
