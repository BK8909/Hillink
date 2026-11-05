"""
힐링크 지도 화면 — 손님을 설정하고, 워커힐 지도 위에서 동선을 보고, 행동마다 근거를 연다 (10/12 경수)

  cd timeline/viewer && python3 app.py          # http://localhost:8765 이 브라우저로 열린다
  python3 app.py --port 9000 --no-browser

설치할 것 없음 (파이썬 표준 라이브러리만). 계산은 engine.py 가 모델(agent_v4 · generate · revenue · scenario_winefair)을 그대로 돌린다.
하루 전체 계산은 cache/ 에 남는다 — 같은 날짜 · 시나리오 · 규모면 다시 안 돌린다 (cache/ 는 저장소에 안 올린다).
"""
from __future__ import annotations

import argparse, json, os, re, subprocess, sys, threading, unicodedata, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
CACHE = HERE / "cache"
sys.path.insert(0, str(HERE))
import query as query_mod  # noqa: E402  (10/16 조건으로 묻기 · 캐시만 읽음, 모델을 들여오지 않음)
ENGINE = [sys.executable, str(HERE / "engine.py")]
LAB = [sys.executable, str(HERE / "lab.py")]
TURN = [sys.executable, str(HERE / "turn_run.py")]   # 10/23 핵심 선택 턴(에이전트 한 명 · 여러 명) — 별도 실행기
STAY = [sys.executable, str(HERE / "stay_run.py")]   # 10/24 체류·행동 계획 계층(엔진 결정 사이의 연속 행동) — 별도 실행기 · 엔진은 부르지 않음
OPX = [sys.executable, str(HERE / "opx_run.py")]
AUTO = [sys.executable, str(HERE / "autonomy_run.py")]   # 10/24 CL-1024-18 자율 행동 시뮬레이션(11명 개별 · 동시) — 별도 실행기 · 기존 턴 · 체류 결과 불변    # 10/24 CL-1024-17 운영 실험 — Codex CD-1024-15 실행 인터페이스 어댑터(별도 실행기 · 기존 턴 · 체류와 섞지 않음)
import ledger_service as receipts

FLOW = [sys.executable, str(HERE / "flow_run.py")]   # CL-1024-22R 고객 흐름의 행동 엔진 = autonomy_v1(화면 계약 runs · plans · visits 로 옮기는 어댑터)
import hashlib as _hl, hmac as _hmac, secrets as _secrets
_DECISION_KEY = _secrets.token_bytes(32)   # CL-1024-22R — 정량 결정 발급 증표(서버 프로세스마다 새 키 · 저장 · 출력 안 함)


def _dec_fields(pid, R, c):
    """화면이 /api/stay 로 넘기는 결정 필드(agent.js agDecisions 와 같은 규칙)를 서버가 같은 엔진 결과에서 다시 만든다."""
    ch = c.get("choice") or {}
    ev = R.get("turn") == "event"
    part = ("participate" if ch.get("venue_id") == "FOREST" else "skip") if ev else ("skip" if ch.get("venue_id") == "ROOM" else "purchase")
    alts = [a.get("product_id") or a.get("venue_id") for a in [x for x in [c.get("runner_up")] + list(c.get("not_chosen") or []) if x][:3]]
    alts = [a for a in alts if a] or ([c["best_other_venue"]["venue_id"]] if c.get("best_other_venue") else [])
    return [f"{pid}|{R.get('turn')}|{R.get('time')}", str(R.get("time")), str(ch.get("map_loc")), str(ch.get("product_id") or ch.get("venue_id")), str(ch.get("venue_id")), part, ",".join(alts)]


def _dec_token(fields):
    return _hmac.new(_DECISION_KEY, "\x1f".join(fields).encode("utf-8"), _hl.sha256).hexdigest()[:40]


def sign_turn(res):
    """/api/turn 결과의 고객 결정마다 발급 증표를 붙인다(view · compare 의 before/after)."""
    for R in ([res] if "customers" in res else [x for x in (res.get("before"), res.get("after")) if isinstance(x, dict)]):
        for c in R.get("customers") or []:
            c["decision_token"] = _dec_token(_dec_fields(c.get("persona_id"), R, c))
    return res


def stay_decisions_ok(cfg):
    """/api/stay plan — 넘어온 결정이 이 서버가 발급한 정량 결정과 필드까지 같은가(재해시 · 상품 바꿔치기 거절)."""
    bad = 0
    for key in ("decisions", "base_decisions"):
        for pid, L in ((cfg.get(key) or {}) or {}).items():
            for d in L or []:
                if not isinstance(d, dict):
                    bad += 1; continue
                f = [str(d.get("decision_id")), str(d.get("time")), str(d.get("loc")), str(d.get("product_id")), str(d.get("venue_id")), str(d.get("participation")), ",".join(map(str, d.get("alternatives") or []))]
                tok = d.get("token")
                if not isinstance(tok, str) or not _hmac.compare_digest(tok, _dec_token(f)) or not str(d.get("decision_id", "")).startswith(f"{pid}|"):
                    bad += 1
    return bad


def flow_run(payload):
    r = subprocess.run(FLOW, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=240)
    if r.returncode != 0:
        sys.stderr.write((r.stderr or "")[-2000:] + "\n")
        raise RuntimeError("고객 흐름 실행 오류")
    return json.loads(r.stdout)


def turn_run(payload):
    r = subprocess.run(TURN, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "turn 오류")
    return json.loads(r.stdout)   # 10/20 개별 페르소나 실험실 — 모델 지문에 들어가지 않는 별도 실행기
RUNNING: dict[str, subprocess.Popen] = {}
LIB: dict = {}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def engine(*args, payload=None, timeout=300):
    r = subprocess.run(ENGINE + list(args), input=json.dumps(payload or {}, ensure_ascii=False), capture_output=True,
                       text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "engine 오류")
    return json.loads(r.stdout)


def _lib_sig():
    tl = HERE.parent
    fs = [HERE / "engine.py", HERE / "links.local.csv", HERE / "photos.local"] + sorted(tl.glob("*.csv")) + sorted(tl.glob("persona_blog*.py")) + [tl / "ontology_oct_daily.json"]
    return [int(f.stat().st_mtime) for f in fs if f.exists()]


# ---------------------------------------------------------------- CL-1024-16 접근 경계(이 서버에는 사용자 인증이 없다)
#   · 원문(작성자) 링크 · 링크 표: 기본은 주지 않는다. 검수자 자료는 '로컬 검수 환경'(서버를 켤 때 HILLINK_REVIEWER_LOCAL=1 · 공개 배포 모드 아님 ·
#     요청이 이 컴퓨터(127.0.0.1)에서 옴)일 때만 준다. URL 매개변수(?reviewer=1)나 화면의 '개발 정보' 버튼은 권한이 아니다.
#   · 라이브러리 자료: 게시 승인(persona_publish.json) + 화면용 프로파일이 있는 고객만 서버가 골라서 준다. 원본 파일은 정적 경로로 주지 않는다.
#   · 공개 배포 모드(HILLINK_DEPLOY=public): 외부 공개 승인(external_publish)만 · 검수자 자료는 항상 차단.
DEPLOY = os.environ.get("HILLINK_DEPLOY", "local").strip().lower()
REVIEWER_LOCAL = os.environ.get("HILLINK_REVIEWER_LOCAL") == "1"
STATIC_DENY = ("persona_library.json", "persona_library.local.json", "persona_links.local.json", "persona_publish.json", "gallery.json", "persona_catalog.json")   # CL-1025-37 — 시각 초안 갤러리 목록도 API 로만
STATIC_REVIEWER_ONLY = ("team_review_index.json", "pref_eval.json")   # CL-1024-20 — 검수 색인(화면이 쓰지 않음)은 로컬 검수 환경에서만
LAB_BLOG = re.compile(r"^blog\d{2}$")


def reviewer_ok(handler) -> bool:
    return REVIEWER_LOCAL and DEPLOY != "public" and handler.client_address[0] in ("127.0.0.1", "::1")


def safe_error(handler, e) -> dict:
    """CL-1024-20 — 공개 · 데모 응답에는 예외 문장 · 경로를 싣지 않는다(상세는 로컬 서버 로그에만). 로컬 검수 환경만 상세 포함."""
    import traceback
    sys.stderr.write("[error] " + "".join(traceback.format_exception_only(type(e), e)))
    return {"error": str(e)} if reviewer_ok(handler) else {"error": "요청을 처리하지 못했습니다", "code": "E_INTERNAL"}


def static_denied(rel_path: str) -> bool:
    name = Path(rel_path).name
    return name in STATIC_DENY or ".local." in name


def _jload(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def publish_set() -> tuple[dict, str]:
    pub = _jload(STATIC / "persona_publish.json", {})
    key = "external_publish" if DEPLOY == "public" else "demo_display"
    appr = {k: True for k in (pub.get(key) or {})}
    ov = os.environ.get("HILLINK_PUBLISH_OVERRIDE")   # 시험 서버 전용(파일은 그대로) — {"A02": false, "A06": true}
    if ov and DEPLOY != "public":
        for k, v in json.loads(ov).items():
            if v: appr[k] = True
            else: appr.pop(k, None)
    return appr, key


def _has_profile(p: dict) -> bool:
    return bool((p.get("audit") and p.get("traits")) or ((p.get("engine") or {}).get("n") or 0) > 0)


def library_personas() -> dict:
    """게시 승인 + 화면용 프로파일이 있는 고객만. 승인 안 된 고객은 요약 · 사실 · 행동 어떤 칸도 내보내지 않는다(ID 와 숨김 사유만)."""
    base = _jload(STATIC / "persona_library.json", {"personas": []})
    local = _jload(STATIC / "persona_library.local.json", {}).get("personas", {})
    appr, key = publish_set()
    pend = (_jload(STATIC / "persona_publish.json", {}).get("pending") or {})
    out, hidden = [], {}
    for p in base.get("personas", []):
        q = dict(p); q.update(local.get(p["id"], {}))
        ok_p, ok_a = _has_profile(q), bool(appr.get(p["id"]))
        if ok_p and ok_a:
            out.append(q)
        else:
            why = pend.get(p["id"]) or ("예비 수집 대상 · 화면 프로파일 연결 전 · 게시 승인 없음" if p.get("group") == "reserve" else ("화면 자료에 프로파일 연결 전" if not ok_p else "") + (" · " if not ok_p and not ok_a else "") + ("게시 승인 없음" if not ok_a else ""))
            hidden[why] = hidden.get(why, 0) + 1
    return {"about": base.get("about"), "sources": base.get("sources"), "status_legend": base.get("status_legend"),
            "publish": {"mode": DEPLOY, "basis": key, "approved": {p["id"]: True for p in out}}, "hidden": hidden, "personas": out}


def library_links(personas: list) -> dict:
    """검수자 전용 — 게시된 고객이 실제로 참조하는 원문 글만(다른 글 · 다른 작성자 링크는 빼고 준다)."""
    L = _jload(STATIC / "persona_links.local.json", {})
    ids = {p["id"] for p in personas}
    posts = set()
    for p in personas:
        for e in (p.get("wh_events") or []) + (p.get("other_events") or []):
            posts.update(e.get("posts") or [])
        for f in ((p.get("engine") or {}).get("facts") or {}).values():
            if f.get("post"): posts.add(f["post"])
        if p.get("start_post"): posts.add(p["start_post"])
    return {"links": {k: v for k, v in (L.get("links") or {}).items() if k in posts},
            "start": {k: v for k, v in (L.get("start") or {}).items() if k in ids}}


_META_IDS: dict = {}


def opx_run(payload):
    r = subprocess.run(OPX, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("운영 실험 실행 오류")   # 내부 오류 문구(경로 포함 가능)는 내보내지 않음
    return json.loads(r.stdout)


def auto_run(payload):
    r = subprocess.run(AUTO, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("자율 행동 실행 오류")
    return json.loads(r.stdout)


def opx_allowed() -> tuple[bool, list]:
    """운영 실험은 시연 고객 11명 전원을 계산한다 — 그중 한 명이라도 현재 배포 기준(로컬 demo_display · 공개 external_publish) 승인 밖이면 막는다."""
    ok = publish_set()[0]
    miss = [x for x in ("A02", "A04", "A05", "A07", "A10", "blog41", "blog42", "blog43", "A01", "A03", "A08") if x not in ok]
    return (not miss), miss


def runnable_ids() -> set:
    if "ids" not in _META_IDS:
        _META_IDS["ids"] = {p["id"] for p in turn_run({"op": "meta", "turn": "dinner"}).get("personas", [])}
    return _META_IDS["ids"]


# 10/16 지도 방문 사진 카드 — 저장소 밖 photos.local/ 만 읽는다 (.gitignore). 사용 권한이 확인된 파일만 이 폴더에 넣는다
#   photos.local/<장소코드>[__n].jpg                 공식 · 현장 사진 (공식 사진)
#   photos.local/review/<blogNN>/<장소코드>[__n].jpg   그 후기 작성자가 찍은 장소 사진 (후기 사진 · 인물 없음 · 작성자 허락 확인된 것만)
#   photos.local/sources.csv  (파일,출처)            선택 · 카드에 작게 보이는 출처 문구
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")


def local_photo_index():
    base = HERE / "photos.local"
    out = {"official": {}, "review": {}, "credit": {}}
    if not base.is_dir():
        return out
    for f in sorted(base.iterdir()):
        if f.is_file() and f.suffix.lower() in PHOTO_EXT:
            out["official"].setdefault(f.stem.split("__")[0], []).append(f.name)
    rv = base / "review"
    if rv.is_dir():
        for d in sorted(rv.iterdir()):
            if d.is_dir() and d.name.startswith("blog"):
                for f in sorted(d.iterdir()):
                    if f.is_file() and f.suffix.lower() in PHOTO_EXT:
                        out["review"].setdefault(d.name, {}).setdefault(f.stem.split("__")[0], []).append(f"review/{d.name}/{f.name}")
    src = base / "sources.csv"
    if src.exists():
        import csv
        for r in csv.reader(open(src, encoding="utf-8-sig")):
            if len(r) >= 2 and r[0].strip() and not r[0].startswith("#") and r[0].strip() != "파일":
                out["credit"][r[0].strip()] = r[1].strip()
    return out


def day_key(date, scenario, scale, theta=None):
    # Share the engine's cache key and holiday rules so new scenario controls cannot collide.
    return _fresh_module("engine").day_key(date, scenario, scale, theta)


_MODS = {}


def _fresh_module(name):
    """10/16 서버를 켠 뒤 engine.py · version.py 가 바뀌면 다시 읽는다. 예전에는 처음 읽은 모듈을 계속 써서,
    코드를 받은 뒤 서버를 다시 켜지 않으면 모든 캐시가 '예전 계산' 으로 보이고 하루 돌리기가 매번 처음부터 다시 돌았다"""
    import importlib
    f = HERE / f"{name}.py"
    mt = f.stat().st_mtime
    mod, seen = _MODS.get(name, (None, None))
    if mod is None or seen != mt:
        mod = importlib.import_module(name) if mod is None else importlib.reload(mod)
        _MODS[name] = (mod, mt)
    return mod


def _fresh(f):
    """결과 파일이 지금 코드 · 입력 버전으로 계산됐는지 (10/14) — 아니면 다시 계산한다"""
    version = _fresh_module("version")
    try:
        m = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return False
    return m.get("model_ver") == version.model_ver() and m.get("input_ver") == version.input_ver()


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        if "/api/day/status" not in (str(a[0]) if a else ""):     # 10/16 QA · 오류 로그는 첫 인자가 문자열이 아닐 수 있음
            sys.stderr.write("  " + fmt % a + "\n")

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=str)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, (STATIC / "index.html").read_bytes(), TYPES[".html"])
            if u.path.startswith("/local-photo/"):
                # 저장소 밖 로컬 사진 (photos.local/ · .gitignore) — 10/7 현장 · 공식 장소 사진만 넣는다. 블로그 사진은 넣지 않는다
                base = (HERE / "photos.local").resolve()
                f = (base / unquote(u.path[len("/local-photo/"):])).resolve()
                if base in f.parents and f.exists():
                    return self.send(200, f.read_bytes(), TYPES.get(f.suffix.lower(), "application/octet-stream"))
                return self.send(404, {"error": "없음"})
            if u.path == "/api/observed-payments":
                # 매 요청마다 새 프로세스로 후기 원장을 읽는다. 일별 시뮬레이션 캐시와 혼합하지 않는다.
                # 10/16 revenue.py(모델 버전 대상) 대신 독립 실행 파일 observed_payments_cli.py 를 부른다.
                period = q.get("month", "all")
                from datetime import date
                import re
                if period != "all":
                    if not re.fullmatch(r"\d{4}-\d{2}", period):
                        return self.send(400, {"error": "월은 YYYY-MM 형식이어야 합니다"})
                    try:
                        date.fromisoformat(period + "-01")
                    except ValueError:
                        return self.send(400, {"error": "유효하지 않은 월입니다"})
                r = subprocess.run([sys.executable, str(HERE.parent / "observed_payments_cli.py"), "--month", period],
                                   capture_output=True, text=True, encoding="utf-8", cwd=HERE.parent, timeout=30,
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                if r.returncode:
                    raise RuntimeError("후기 결제 집계 실패")
                return self.send(200, json.loads(r.stdout))
            if u.path == "/api/photos":
                return self.send(200, local_photo_index())
            if u.path.startswith("/static/"):
                # CL-1024-14 — 한글 파일 이름(유형 썸네일 · 아이콘): 주소의 %인코딩을 풀고, Mac(NFD)/그 밖(NFC) 이름 어느 쪽이든 연다
                rel = unquote(u.path[len("/static/"):])
                if "\x00" in rel or "\\" in rel:   # 널 바이트 · 역슬래시 경로는 열지 않음(CL-1024-15 보안 점검)
                    return self.send(404, {"error": "없음"})
                f = (STATIC / rel).resolve()
                if not f.exists():
                    for form in ("NFC", "NFD"):
                        g = (STATIC / unicodedata.normalize(form, rel)).resolve()
                        if g.exists():
                            f = g
                            break
                if static_denied(f.name) or static_denied(rel):   # 원본 프로파일 · 링크 표 · 게시 목록은 정적 경로로 주지 않음(API 가 걸러서 줌)
                    return self.send(404, {"error": "없음"})
                if (f.name in STATIC_REVIEWER_ONLY or Path(rel).name in STATIC_REVIEWER_ONLY) and not reviewer_ok(self):
                    return self.send(404, {"error": "없음"})
                if DEPLOY == "public" and ((STATIC / "persona_gallery") in f.parents or (STATIC / "demo_story") in f.parents or (STATIC / "demo_thumbs") in f.parents):   # P5 — 시연용 임시 표시 이미지도 공개 배포 제외   # CL-1025-37 P0 — 시연 저장본도 공개 배포에서 주지 않음   # CL-1025-37 — 고객 고유 썸네일 초안(사람 승인 0)은 공개 배포에서 주지 않음
                    return self.send(404, {"error": "없음"})
                if STATIC in f.parents and f.exists():
                    return self.send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
                return self.send(404, {"error": "없음"})
            if u.path == "/api/turn/meta":
                meta = turn_run({"op": "meta", "turn": q.get("turn", "dinner")})
                if not reviewer_ok(self) and isinstance(meta, dict) and isinstance(meta.get("personas"), list):   # CL-1024-20 — 게시 승인 고객만
                    appr = publish_set()[0]
                    meta = dict(meta, personas=[p for p in meta["personas"] if p.get("id") in appr])
                return self.send(200, meta)
            if u.path == "/api/library":
                # 근거 묶음은 처음 한 번 계산해 두되, engine.py · 표(csv) · 후기 페르소나 · 로컬 링크가 바뀌면 다시 읽는다 (10/14 — 서버를 안 껐다 켜도 새 표가 보이게)
                sig = _lib_sig()
                if not LIB or LIB.get("_sig") != sig:
                    LIB.clear(); LIB.update(engine("library")); LIB["_sig"] = sig
                if reviewer_ok(self):   # CL-1024-16 — 로컬 검수 환경일 때만 원문(작성자) 링크 포함(?reviewer=1 은 권한이 아님 · 무시)
                    return self.send(200, LIB)
                out = dict(LIB); out["review_list"] = [{k: v for k, v in r.items() if k != "link"} for r in LIB.get("review_list", [])]
                if DEPLOY == "public":   # CL-1024-16 — 공개 배포: 후기 인용(reviews.why) · 미승인 후보 목록 · 아동 여부를 보내지 않음(외부 공개 승인 고객만)
                    ok = publish_set()[0]   # 외부 공개 승인 0명 → 빈 목록 (승인 생기면 고객 ID ↔ 후기 ID 대응을 다시 확인할 것)
                    out["review_list"] = [{k: v for k, v in r.items() if k not in ("link", "kids", "name")} for r in out["review_list"] if r.get("blog") in ok]
                    out["reviews"] = {}
                    out["public_minimized"] = True
                return self.send(200, out)
            if u.path == "/api/library/personas":
                return self.send(200, library_personas())
            if u.path == "/api/library/gallery":   # CL-1025-37 — 시각 초안 갤러리(내부 시연 · 검수 중). 공개 배포 모드에서는 빈 목록
                if DEPLOY == "public":
                    return self.send(200, {"cards": [], "public_blocked": True})
                return self.send(200, _jload(STATIC / "persona_gallery" / "gallery.json", {"cards": []}))
            if u.path == "/api/library/catalog":   # CL-37 P7 — 열람 전용 고객(원장 · 표시 번호 · 썸네일 1:1 조인). 실행 허용 목록 · 게시 승인과 별개(실행 API 는 그대로 막힘). 공개 배포 모드에서는 빈 목록
                if DEPLOY == "public":
                    return self.send(200, {"customers": [], "public_blocked": True})
                cat = _jload(STATIC / "persona_catalog.json", {"customers": []})
                appr = publish_set()[0]
                return self.send(200, {"about": cat.get("about"), "version": cat.get("version"), "counts": cat.get("counts"),
                                       "customers": [c for c in cat.get("customers", []) if c.get("id") not in appr and not c.get("engine_runnable")]})
            if u.path == "/api/library/links":
                if not reviewer_ok(self):
                    return self.send(403, {"error": "원문 링크는 로컬 검수 환경에서만 열립니다", "reviewer": False})
                return self.send(200, library_links(library_personas()["personas"]))
            if u.path == "/api/autonomy/meta":
                ok, miss = opx_allowed()
                if not ok:
                    return self.send(403, {"error": "현재 배포 기준의 공개 승인 밖 고객이 있어 열지 않습니다", "deploy": DEPLOY})
                return self.send(200, auto_run({"op": "meta"}))
            if u.path == "/api/opx/meta":
                ok, miss = opx_allowed()
                if not ok:
                    return self.send(403, {"error": "운영 실험 고객 중 현재 배포 기준의 공개 승인 밖 고객이 있어 열지 않습니다", "deploy": DEPLOY, "n_missing": len(miss)})
                return self.send(200, opx_run({"op": "meta"}))
            if u.path == "/api/access":
                return self.send(200, {"deploy": DEPLOY, "reviewer": reviewer_ok(self)})
            if u.path == "/api/random":
                return self.send(200, engine("random", "--seed", q.get("seed", "1"), *(("--row", q["row"]) if q.get("row", "").isdigit() else ())))
            if u.path == "/api/day/list":
                out = []
                for f in sorted(CACHE.glob("*.json")):
                    if f.name.endswith(".progress.json") or f.name.startswith("band_"):
                        continue
                    try:
                        m = json.loads(f.read_text(encoding="utf-8"))
                        out.append({"key": m["key"], "date": m["date"], "scenario": m["scenario"], "scale": m["scale"], "n": m["n"], "built": m["built"],
                                    "theta": m.get("theta") or {}, "knobs": m.get("knobs", ""), "model_ver": m.get("model_ver"), "input_ver": m.get("input_ver")})
                    except Exception:
                        pass
                return self.send(200, out)
            if u.path == "/api/day/status":
                key = q["key"]
                done = (CACHE / f"{key}.json").exists() and key not in RUNNING
                p = RUNNING.get(key)
                if p is not None and p.poll() is not None:
                    RUNNING.pop(key, None)
                    done = (CACHE / f"{key}.json").exists()
                    if not done:
                        err = (p.stderr.read() if p.stderr else "") or "계산 실패"
                        return self.send(200, {"status": "error", "error": err.strip().splitlines()[-1]})
                prog = {}
                pf = CACHE / f"{key}.progress.json"
                if pf.exists():
                    try:
                        prog = json.loads(pf.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                st = "done" if done else ("running" if key in RUNNING else "none")
                if st == "none" and prog and prog.get("phase") != "끝":
                    # 10/16 서버가 다시 켜져 그 계산을 놓친 경우. 진행 파일이 아직 바뀌고 있으면(남은 계산이 돌고 있음) 기다리고,
                    # 90초 넘게 그대로면 끊긴 것으로 알려 화면이 계속 기다리지 않게 한다
                    import time as _t
                    st = "running" if _t.time() - pf.stat().st_mtime < 90 else "lost"
                return self.send(200, {"status": st, **prog})
            if u.path == "/api/day/result":
                m = json.loads((CACHE / f"{q['key']}.json").read_text(encoding="utf-8"))
                m.pop("offsets", None)
                return self.send(200, m)
            if u.path == "/api/day/l5.csv":
                r = engine("l5_export", "--key", q["key"])          # 엔진은 늘 따로 띄운다 (app 은 모델을 안 들여온다)
                body = Path(r["out"]).read_bytes()
                self.send_response(200); self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="L5_{q["key"]}.csv"'); self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            if u.path == "/api/bands":
                # 비교가 있는 시드 묶음 전부 — 변칙 시나리오 · 가설 예측표 (질문 탭)
                out = []
                for f in sorted(CACHE.glob("band_*.json")):
                    try:
                        b = json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if b.get("compare") and b.get("effect") and f.name == f"band_{b.get('compare_key')}.json":
                        out.append({k: b.get(k) for k in ("date", "scenario", "seeds", "theta", "compare", "base_key", "compare_key", "effect", "base", "comp", "model_ver", "input_ver")})
                return self.send(200, out)
            if u.path == "/api/day/band":
                f = CACHE / f"band_{q['key']}.json"
                return self.send(200, json.loads(f.read_text(encoding="utf-8")) if f.exists() else {})
            if u.path == "/api/day/flow":
                # 10/14 고객 이동 정산 (check_flow.py) — 없거나 버전이 다르면 그 자리에서 만든다. 손님 상세(guests.jsonl)가 있어야 한다
                key = q["key"]; f = CACHE / f"flow_{key}.json"; day_f = CACHE / f"{key}.json"
                if not (CACHE / f"{key}.guests.jsonl").exists():
                    return self.send(200, {"error": "이 날의 손님 상세 기록이 없습니다 — 하루를 다시 돌리면 생깁니다"})
                dm = json.loads(day_f.read_text(encoding="utf-8")) if day_f.exists() else {}
                old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
                if not old or old.get("model_ver") != dm.get("model_ver") or old.get("input_ver") != dm.get("input_ver") or "events" not in old:
                    subprocess.run([sys.executable, str(HERE / "check_flow.py"), "--key", key], capture_output=True, text=True)
                return self.send(200, json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"error": "정산 실패"})
            if u.path == "/api/day/qopts":
                # 10/16 운영 어시스턴트 2차 · 조건으로 묻기 — 고를 수 있는 업장 · 회차 · 고객군 (query.py · 모델을 들여오지 않는다)
                return self.send(200, query_mod.options(CACHE, q["key"]))
            if u.path == "/api/day/query":
                return self.send(200, query_mod.query(CACHE, q["key"], q["venue"], q.get("window", "*"), q.get("group", "all")))
            if u.path == "/api/day/guest":
                key, idx = q["key"], int(q["idx"])
                m = json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8"))
                with (CACHE / f"{key}.guests.jsonl").open(encoding="utf-8") as fd:
                    fd.seek(m["offsets"][idx])
                    det = json.loads(fd.readline())
                det["crowd_note"] = f"그 날 손님 {m['n']}팀 중 하나 ({key})"
                det["scenario"] = m["scenario"]
                return self.send(200, det)
            return self.send(404, {"error": "없음"})
        except Exception as e:
            return self.send(500, safe_error(self, e))

    def do_POST(self):
        u = urlparse(self.path)
        try:
            cfg = self.body()
            if u.path == "/api/turn":
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식 오류"})
                appr = publish_set()[0]
                extra = [x for x in (cfg.get("personas") or []) if x not in appr]
                if extra and not reviewer_ok(self):   # CL-1024-20 — 게시 승인 밖 고객 실행은 로컬 검수 환경에서만
                    return self.send(403, {"error": "게시 승인 고객만 실행합니다", "n": len(extra)})
                return self.send(200, sign_turn(turn_run(cfg)))
            if u.path == "/api/ledger/demo":
                if DEPLOY == "public" or not isinstance(cfg, dict):
                    return self.send(403, {"error": "저장 시연 영수증은 로컬 시연에서만 확인합니다"})
                key = cfg.get("key")
                fx = _jload(STATIC / "demo_story" / "flow_fixture_v1.json", {})
                entry = (fx.get("entries") or {}).get(key) if isinstance(key, str) else None
                if entry is None:
                    return self.send(404, {"error": "확인할 저장 시연이 없습니다"})
                request = json.loads(key)
                if any(p not in publish_set()[0] for p in request.get("personas", [])):
                    return self.send(403, {"error": "게시 승인 고객만 확인합니다"})
                return self.send(200, receipts.register(entry, request, source="stored_demo"))
            if u.path == "/api/ledger/compare":
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식을 확인해 주세요"})
                try:
                    comparison = receipts.compare(cfg.get("baseline_id"), cfg.get("scenario_id"), cfg.get("customer_type"), cfg.get("stay_status", "all"))
                except receipts.ReceiptError as e:
                    return self.send(409, {"error": str(e), "code": "E_RECEIPT_COMPARE"})
                if any(p not in publish_set()[0] for p in comparison["customers"]):
                    return self.send(403, {"error": "게시 승인 고객만 확인합니다"})
                return self.send(200, comparison)
            if u.path == "/api/ledger/filter":
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식을 확인해 주세요"})
                try:
                    ledger = receipts.lookup(cfg.get("run_id"), cfg.get("customer_type"), cfg.get("stay_status", "all"))
                except receipts.ReceiptError as e:
                    return self.send(409, {"error": str(e), "code": "E_RECEIPT_RUN"})
                if any(p not in publish_set()[0] for p in ledger["receipts"]):
                    return self.send(403, {"error": "게시 승인 고객만 확인합니다"})
                return self.send(200, ledger)
            if u.path == "/api/flow":   # CL-1024-22R — 고객 흐름(한 명 · 여러 명)의 실행 경로
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식 오류"})
                appr = publish_set()[0]
                extra = [x for x in (cfg.get("personas") or []) if x not in appr]
                if extra:
                    return self.send(403, {"error": "게시 승인 고객만 실행합니다", "n": len(extra)})
                body = {k: cfg.get(k) for k in ("personas", "mode", "visit_override", "event", "intervention", "product_levers", "observe", "seed") if k in cfg}
                if "include_ledger" in cfg and not isinstance(cfg["include_ledger"], bool):
                    return self.send(400, {"error": "영수증 요청 형식을 확인해 주세요"})
                res = flow_run(body)
                if cfg.get("include_ledger") and "error" not in res:
                    try:
                        res = dict(res, ledger=receipts.register(res, body))
                    except receipts.ReceiptError:
                        return self.send(409, {"error": "장면 지출과 영수증을 대조하지 못했습니다", "code": "E_RECEIPT_BALANCE"})
                return self.send((409 if res.get("code") == "E_FLOW_INPUT_MISSING" else 400) if "error" in res else 200, res)
            if u.path == "/api/autonomy":
                ok, miss = opx_allowed()
                if not ok:
                    return self.send(403, {"error": "현재 배포 기준의 공개 승인 밖 고객이 있어 계산하지 않습니다", "deploy": DEPLOY})
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식 오류"})
                appr = publish_set()[0]
                extra = [x for x in (cfg.get("personas") or []) if x not in appr]
                if extra:
                    return self.send(403, {"error": "게시 승인 고객만 실행합니다", "n": len(extra)})
                body = {k: cfg.get(k) for k in ("personas", "mode", "intervention", "compare", "seed") if k in cfg}
                res = auto_run({**body, "op": "run"})
                return self.send(400 if "error" in res else 200, res)
            if u.path == "/api/opx/run":
                ok, miss = opx_allowed()
                if not ok:
                    return self.send(403, {"error": "운영 실험 고객 중 현재 배포 기준의 공개 승인 밖 고객이 있어 계산하지 않습니다", "deploy": DEPLOY, "n_missing": len(miss)})
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식 오류"})
                return self.send(200, opx_run({**cfg, "op": "run"}))
            if u.path == "/api/stay":
                extra = [x for x in (cfg.get("personas") or []) if x not in runnable_ids()]
                if extra and not reviewer_ok(self):   # CL-1024-16 — 등록 · 실행 가능 고객 밖(비공개 QA 프로파일 등)은 로컬 검수 환경에서만
                    return self.send(403, {"error": "등록된 실행 가능 고객만 계산합니다", "ids": extra})
                if isinstance(cfg, dict) and cfg.get("op") == "plan":   # CL-1024-22R — 클라이언트가 만든 결정 · 해시를 믿지 않음: 서버 발급 증표가 맞는 결정만
                    nb = stay_decisions_ok(cfg)
                    if nb:
                        return self.send(403, {"error": "서버가 발급하지 않았거나 바뀐 정량 결정은 받지 않습니다", "code": "E_DECISION_NOT_ISSUED", "n": nb})
                r = subprocess.run(STAY, input=json.dumps(cfg, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=180)
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "stay 오류")
                return self.send(200, json.loads(r.stdout))
            if u.path == "/api/packages":
                return self.send(200, engine("packages", payload=cfg))
            if u.path == "/api/guest":
                return self.send(200, engine("guest", payload=cfg))
            if u.path == "/api/review":
                out = engine("review", payload=cfg)
                if not reviewer_ok(self) and isinstance(out, dict) and isinstance(out.get("review"), dict):   # CL-1024-20 — 원문(작성자) 링크는 로컬 검수 환경에서만(CL-16 경계와 같은 기준)
                    out = dict(out, review={k: v for k, v in out["review"].items() if k not in ("link", "url", "links")})
                return self.send(200, out)
            if u.path == "/api/lab":
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식 오류"})
                if not cfg.get("avail"):   # CL-1024-20 — 경로 · 모듈 이름에 쓰이는 값은 등록된 형식 · 변수만
                    if not (isinstance(cfg.get("blog"), str) and LAB_BLOG.match(cfg["blog"])) or cfg.get("var") not in ("winefair", "riverpark", "rain"):
                        return self.send(400, {"error": "허용되지 않는 실험 대상입니다", "code": "E_LAB_INPUT"})
                    cfg = {"blog": cfg["blog"], "var": cfg["var"]}
                else:
                    cfg = {"avail": True}
                r = subprocess.run(LAB, input=json.dumps(cfg, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=300)
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "lab 오류")
                return self.send(200, json.loads(r.stdout))
            if u.path == "/api/day":
                theta = cfg.get("theta") or {}
                key = day_key(cfg["date"], cfg.get("scenario", "none"), cfg.get("scale", 1.0), theta)
                if (CACHE / f"{key}.json").exists() and not cfg.get("force") and _fresh(CACHE / f"{key}.json"):
                    return self.send(200, {"status": "done", "key": key})
                if key not in RUNNING:
                    CACHE.mkdir(exist_ok=True)
                    (CACHE / f"{key}.json").unlink(missing_ok=True)
                    RUNNING[key] = subprocess.Popen(ENGINE + ["day", "--date", cfg["date"], "--scenario", cfg.get("scenario", "none"),
                                                              "--scale", str(cfg.get("scale", 1.0)), "--theta", json.dumps(theta)],
                                                    cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                return self.send(200, {"status": "running", "key": key})
            return self.send(404, {"error": "없음"})
        except Exception as e:
            return self.send(500, safe_error(self, e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    # 10/14 손님 상세 기록은 크기(약 20MB) 때문에 압축본(.guests.jsonl.gz)으로 옮길 때가 있다 — 풀린 파일이 없으면 시작할 때 푼다
    import gzip, shutil
    for gz in CACHE.glob("*.guests.jsonl.gz"):
        plain = gz.with_suffix("")
        if not plain.exists() or gz.stat().st_mtime > plain.stat().st_mtime:      # 10/16 새로 옮긴 압축본이 있으면 예전 풀린 파일을 바꾼다
            with gzip.open(gz, "rb") as src, plain.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    # 10/26 — 로컬 보관 실행 입력 4개 점검(없으면 해당 고객은 계산 대신 '입력 미연결' 안내 · 서버 오류 아님)
    LOCAL_INPUTS = [STATIC / "persona_library.local.json", STATIC / "persona_links.local.json", HERE / "links.local.csv",
                    HERE.parent / "experiments" / "persona_live" / "operator_choice" / "operator_world_v1_1" / "turn_personas_ext.local.json"]
    miss = [f.name for f in LOCAL_INPUTS if not f.exists()]
    if miss:
        print("⚠ 로컬 보관 입력 없음: " + ", ".join(miss) + " — 해당 자료가 필요한 고객의 프로필 · 원문 링크 · 실행이 빠질 수 있습니다(실행 입력이 없으면 '입력 미연결' 안내)")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    url = f"http://localhost:{a.port}"
    print(f"힐링크 지도 화면 → {url}   (끄려면 Ctrl+C)")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n끝")


if __name__ == "__main__":
    main()
