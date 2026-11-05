"""시연 화면 로컬 서버 — 고객에게 실시간으로 질문 (10/20 · 총괄 C)

  python3 serve_demo.py            # http://127.0.0.1:8765/  (demo/persona_demo.html 을 그대로 서빙)

POST /ask  {"plan": "demo_1", "blog": "blog25", "cond": "D0", "question": "..."}  → 같은 페르소나 시트 · 무대 · 이미 정한 계획을 두고 ask.ask_followup 호출
답은 runs/<plan>/<blog>/<cond>_followup.json 에 덧붙여 저장되고(저장된 질의응답으로 재사용), 화면은 서버가 없으면 저장된 답만 보여 준다.
`claude` CLI 가 있는 로컬에서만 실시간 답이 나온다. 외부 공개용 서버가 아니다(인증 없음 · 로컬 바인딩).
"""
from __future__ import annotations

import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import branching as BR   # noqa: E402  (가지 · 질문 — verify10.py 와 같은 코드)

DEMO = HERE / "demo"
VSTATIC = HERE.parents[1] / "viewer" / "static"          # 기존 힐링크 뷰어의 style.css · 로고 · 시설 그림을 그대로 쓴다(v3)
MAP_PNG = VSTATIC / "map_base.png"
TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml"}


class H(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (DEMO / "persona_sim.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/demo":
            self._send(200, (DEMO / "persona_demo.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/map_base.png":
            self._send(200, MAP_PNG.read_bytes(), "image/png")
        elif self.path.startswith("/viewer/static/"):
            f = (VSTATIC / self.path[len("/viewer/static/"):].split("?")[0]).resolve()
            if VSTATIC.resolve() in f.parents and f.is_file() and f.suffix.lower() in TYPES:
                self._send(200, f.read_bytes(), TYPES[f.suffix.lower()])
            else:
                self._send(404, b"not found", "text/plain")
        elif self.path == "/health":
            self._send(200, b'{"ok":true}', "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); q = json.loads(self.rfile.read(n) or b"{}")
        f = HERE / "runs" / q.get("plan", "") / q.get("blog", "") / f"{q.get('cond', '')}_r0.json"
        if not f.exists():
            return self._send(404, json.dumps({"error": "run not found"}).encode(), "application/json")
        rec = json.loads(f.read_text(encoding="utf-8"))
        if self.path == "/ask":
            try:
                r = BR.followup(f, q["question"])
            except Exception as e:   # noqa: BLE001
                return self._send(500, json.dumps({"error": str(e)[:300]}).encode(), "application/json")
            return self._send(200, json.dumps(r, ensure_ascii=False).encode(), "application/json")
        if self.path == "/event":
            try:
                r = BR.make_branch(f, int(q["slot_index"]), q["text"], "operator")
            except Exception as e:   # noqa: BLE001
                return self._send(500, json.dumps({"error": str(e)[:300]}).encode(), "application/json")
            return self._send(200, json.dumps(dict(key=r["key"], entry=r["entry"], later_plan=r["later_plan"], cost_usd=r["cost_usd"]), ensure_ascii=False, default=str).encode(), "application/json")
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):   # 조용히
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"http://127.0.0.1:{port}/  (Ctrl+C 로 종료)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
