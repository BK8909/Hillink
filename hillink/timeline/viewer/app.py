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
# Runtime capabilities must work as the first request in a fresh process.
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
import query as query_mod  # noqa: E402  (10/16 조건으로 묻기 · 캐시만 읽음, 모델을 들여오지 않음)
import wire_json
import visit_execution
ENGINE = [sys.executable, str(HERE / "engine.py")]
LAB = [sys.executable, str(HERE / "lab.py")]
TURN = [sys.executable, str(HERE / "turn_run.py")]   # 10/23 핵심 선택 턴(에이전트 한 명 · 여러 명) — 별도 실행기
STAY = [sys.executable, str(HERE / "stay_run.py")]   # 10/24 체류·행동 계획 계층(엔진 결정 사이의 연속 행동) — 별도 실행기 · 엔진은 부르지 않음
OPX = [sys.executable, str(HERE / "opx_run.py")]
AUTO = [sys.executable, str(HERE / "autonomy_run.py")]   # 10/24 CL-1024-18 자율 행동 시뮬레이션(11명 개별 · 동시) — 별도 실행기 · 기존 턴 · 체류 결과 불변    # 10/24 CL-1024-17 운영 실험 — CD-1024-15 실행 인터페이스 어댑터(별도 실행기 · 기존 턴 · 체류와 섞지 않음)
import http_boundary as boundary
import execution_limits as execution
import ledger_service as receipts
import strategy_agent_service as agent_jobs

FLOW = [sys.executable, str(HERE / "flow_run.py")]   # CL-1024-22R 고객 흐름의 행동 엔진 = autonomy_v1(화면 계약 runs · plans · visits 로 옮기는 어댑터)
VISIT = [sys.executable, str(HERE / "visit_run.py")]  # CL-39 연속 방문: 기존 autonomy_v1 하루 실행을 방문 상태로 연결
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
    r = execution.run(FLOW, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=240)
    if r.returncode != 0:
        sys.stderr.write((r.stderr or "")[-2000:] + "\n")
        raise RuntimeError("고객 흐름 실행 오류")
    return json.loads(r.stdout)


def visit_run(payload):
    try:
        request,env,mode=visit_execution.configure(payload)
    except ValueError as exc:
        return dict(error='선택한 판단 모드로 실행할 수 없습니다: '+str(exc),code=str(exc))
    r = execution.run(VISIT, input=json.dumps(request, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**env, "PYTHONIOENCODING": "utf-8"}, cwd=HERE,
                       timeout=3600 if str(payload.get('hybrid_policy','')).startswith('LLM_AUTONOMOUS_') else 900)
    if r.returncode != 0:
        sys.stderr.write((r.stderr or "")[-2000:] + "\n")
        raise RuntimeError("방문 전체 행동 실행 오류")
    return visit_execution.describe(json.loads(r.stdout),mode,request.get('hybrid_policy'))


def turn_run(payload):
    r = execution.run(TURN, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "turn 오류")
    return json.loads(r.stdout)   # 10/20 개별 페르소나 실험실 — 모델 지문에 들어가지 않는 별도 실행기
RUNNING: dict[str, subprocess.Popen] = {}
def completed_visit(body,include_ledger=True,*,prepare_response=False):
    res=visit_run(body)
    if len(json.dumps(res,ensure_ascii=False).encode())>execution.MAX_RETAINED_RESULT_BYTES:
        raise boundary.RequestError('RESULT_TOO_LARGE',413)
    if len(wire_json.serialize(res,execution.MAX_VISIT_RESULT_BYTES))>execution.MAX_VISIT_RESULT_BYTES:
        raise boundary.RequestError('RESULT_TOO_LARGE',413)
    if include_ledger and 'error' not in res:
        res['ledger']=receipts.register_visit(res,body)
        try:
            import operating_reference as _OR   # operator aggregate; references never change agent choices
            profile=body.get('reference_profile','external')
            res['operating_summary']=_OR.aggregate(res,profile=profile)
            import population as _POP   # composition weights: estimates for the stated guest mix, never ledger totals
            w=_POP.weights(res,_OR.load(profile=profile)[0],'party_size')
            res['operating_summary']['population']=dict(weights=w,estimates=_POP.estimates(res,w if w.get('status','').startswith('OK') else None))
        except Exception as exc:   # never fail a visit because of the operator aggregate
            res['operating_summary']=dict(error=type(exc).__name__)
        res.pop('profile_sha',None)
        response=wire_json.serialize(res,execution.MAX_VISIT_RESULT_BYTES)
        if len(response)>execution.MAX_VISIT_RESULT_BYTES:
            raise boundary.RequestError('RESULT_TOO_LARGE',413)
        # Preserve the actual HTTP/strategy request contract. The outer ledger
        # flag is not an engine input, but is part of the source request hash.
        agent_jobs.remember(res,dict(body,include_ledger=True))
    res.pop('profile_sha',None)
    if prepare_response:
        # Reuse the final, size-checked bytes on the synchronous HTTP path.
        # Async jobs retain ordinary objects; no process-wide serialization cache.
        if not include_ledger or 'error' in res:
            response=wire_json.serialize(res,execution.MAX_VISIT_RESULT_BYTES)
        status=((409 if res.get('code')=='E_FLOW_INPUT_MISSING' else 400) if 'error' in res else 200)
        return status,response
    return res


def strategy_bundle(pid,handler):
    customer=next((p for p in library_personas()['personas'] if p['id']==pid),None)
    if customer is None and pid in local_trial_ids(handler):
        from private_intake_view import project as intake_project
        customer=intake_project(pid,strategy=True)['customer']
    if customer is None:raise ValueError('CUSTOMER_NOT_AUTHORIZED')
    from strategy_evidence import project
    return project(customer,reviewer=False)


def execute_agent_pair(pair):
    a,b,contract=pair
    left=completed_visit(a);right=completed_visit(b)
    left['request']=a;right['request']=b
    readiness=agent_jobs.pair_readiness(left,right,a,b,contract)
    comparison=receipts.compare(left['ledger']['run_id'],right['ledger']['run_id']) if readiness['comparable'] else None
    return dict(before=left,after=right,comparison=comparison,experiment_contract=contract,readiness=readiness,
        fixed_choice_repricing=agent_jobs.fixed_choice_repricing(left,a,b,contract) if readiness['comparable'] else None,
        target_meal_comparison=agent_jobs.target_meal_comparison(left,right,contract) if readiness['comparable'] else None,
        interpretation='OBSERVED_SIMULATION_DIFFERENCE_NOT_CAUSAL_EFFECT' if readiness['comparable'] else 'INCOMPLETE_PAIR_NO_EFFECT_REPORTED',
        llm_variation='Separate Responses inputs; policy and visit inputs held constant except price. Response variation remains unisolated.')


def execute_agent_analysis(cfg,bundles):
    entry=agent_jobs.source(cfg['run_id']) if cfg.get('run_id') else None
    source_mode=(entry or {}).get('flow',{}).get('judgment',{}).get('actual')
    mode=source_mode if source_mode in ('replay','live') else os.environ.get('HILLINK_AGENT_MODE','replay')
    env=dict(os.environ,HILLINK_AGENT_MODE=mode)
    if mode=='replay':env.update(HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0')
    if mode=='live':
        ok,reason=visit_execution.live_status()
        if not ok:raise ValueError(reason)
    r=execution.run([sys.executable,str(HERE/'strategy_analysis_worker.py')],
        input=json.dumps(dict(request=cfg,bundles=bundles,source=entry),ensure_ascii=False),
        env=env,capture_output=True,text=True,encoding='utf-8',cwd=HERE,timeout=1800)
    if r.returncode:raise ValueError('STRATEGY_ANALYSIS_HOLD')
    return json.loads(r.stdout)
LIB: dict = {}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def engine(*args, payload=None, timeout=300):
    r = execution.run(ENGINE + list(args), input=json.dumps(payload or {}, ensure_ascii=False), capture_output=True,
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


def population_experiment_spec(cfg, allowed):
    """Validated group A/B request: same customers, dates, seed, engine, reference profile and prior on both sides;
    B differs only by a percentage discount on Pizza Hill dine-in mains."""
    import operating_reference as OR
    if not isinstance(cfg, dict) or set(cfg) - {'personas', 'duration', 'reference_profile', 'behaviour_prior', 'pizza_hill_discount_percent', 'seed', 'start_date'}:
        raise ValueError('UNSUPPORTED_FIELDS')
    ids = cfg.get('personas')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 28 or len(set(ids)) != len(ids) or set(ids) - allowed: raise ValueError('CUSTOMER_SCOPE_INVALID')
    if cfg.get('duration', 'stay_1') not in ('stay_1', 'stay_2'): raise ValueError('STAY_DURATION_REQUIRED')
    if cfg.get('reference_profile', 'external') not in OR.PROFILES: raise ValueError('UNKNOWN_REFERENCE_PROFILE')
    if cfg.get('behaviour_prior', 'OFF') not in ('OFF', 'HOTEL_PRIOR_V1'): raise ValueError('UNKNOWN_BEHAVIOUR_PRIOR')
    pct = cfg.get('pizza_hill_discount_percent', 20)
    if type(pct) is not int or not 5 <= pct <= 50: raise ValueError('DISCOUNT_PERCENT_5_TO_50')
    seed = cfg.get('seed', 0)
    if type(seed) is not int or not 0 <= seed <= 9999: raise ValueError('SEED_INVALID')
    return dict(personas=sorted(ids), duration=cfg.get('duration', 'stay_1'), reference_profile=cfg.get('reference_profile', 'external'),
                behaviour_prior=cfg.get('behaviour_prior', 'OFF'), pizza_hill_discount_percent=pct, seed=seed, start_date=cfg.get('start_date', '2026-11-13'))


def local_trial_ids(handler):
    if DEPLOY == 'public' or handler.client_address[0] not in ('127.0.0.1','::1') or os.environ.get('HILLINK_ISOLATED_CUSTOMERS') != '1':
        return set()
    sys.path.insert(0,str(HERE.parent/'experiments/persona_live'))
    from operator_choice.operator_world_v1_1 import isolated_registry as IR
    return set(IR.registrations())

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
    r = execution.run(OPX, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("운영 실험 실행 오류")   # 내부 오류 문구(경로 포함 가능)는 내보내지 않음
    return json.loads(r.stdout)


def auto_run(payload):
    r = execution.run(AUTO, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
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
            body = wire_json.serialize(body,execution.MAX_VISIT_RESULT_BYTES)
            if len(body)>execution.MAX_VISIT_RESULT_BYTES:
                code=413;body=b'{"code":"RESULT_TOO_LARGE"}'
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.connection.settimeout(boundary.READ_TIMEOUT)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        return boundary.body(self)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            boundary.guard(self)
            if DEPLOY == 'public' and (u.path.startswith('/api/day') or u.path in ('/api/bands', '/api/observed-payments') or u.path.startswith('/local-photo/')):
                return self.send(403, {'code': 'PRIVATE_CACHE_DISABLED'})
            if 'key' in q:
                boundary.cache_family(CACHE, q['key'])
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
                r = execution.run([sys.executable, str(HERE.parent / "observed_payments_cli.py"), "--month", period],
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
                if DEPLOY == 'public' and rel.endswith('.json') and rel not in ('avatars/manifest.json','place_img/manifest.json','event_scenario_options.json','situation_options.json','sku_scenario_options.json'):
                    return self.send(404, {'code':'PRIVATE_STATIC_DATA_DISABLED'})
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
                if DEPLOY == "public" and ((STATIC / "a02_assets" / "thumbs") in f.parents or (STATIC / "persona_gallery") in f.parents or (STATIC / "demo_story") in f.parents or (STATIC / "demo_thumbs") in f.parents):   # P5 — 시연용 임시 표시 이미지도 공개 배포 제외   # CL-1025-37 P0 — 시연 저장본도 공개 배포에서 주지 않음   # CL-1025-37 — 고객 고유 썸네일 초안(사람 승인 0)은 공개 배포에서 주지 않음
                    return self.send(404, {"error": "없음"})
                if STATIC in f.parents and f.exists():
                    return self.send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
                return self.send(404, {"error": "없음"})
            if u.path == '/api/build':
                return self.send(200, {'head': os.environ.get('HILLINK_BUILD_SHA'), 'branch': os.environ.get('HILLINK_BUILD_BRANCH'), 'agent_mode': os.environ.get('HILLINK_AGENT_MODE', 'off')})
            if u.path in ('/api/saved-visits','/api/saved-visits/run','/api/saved-visits/cohort'):
                if not reviewer_ok(self):return self.send(403,{'code':'LOCAL_REVIEW_REQUIRED'})
                import saved_visits
                try:
                    if u.path=='/api/saved-visits':return self.send(200,saved_visits.index())
                    with execution.slot():
                        if u.path.endswith('/cohort'):return self.send(200,saved_visits.cohort())
                        saved=saved_visits.load(q.get('tag',''))
                        allowed=set(publish_set()[0])|local_trial_ids(self)
                        if set(saved['result']['plans'])-allowed:return self.send(403,{'code':'CUSTOMER_NOT_AUTHORIZED'})
                        agent_jobs.remember(saved['result'],saved['request'])
                        return self.send(200,saved)
                except ValueError:return self.send(400,{'code':'INVALID_OR_UNVERIFIED_SAVED_VISIT'})
            if u.path == '/api/agent/jobs':
                if not reviewer_ok(self):return self.send(403,{'error':'로컬 검수 환경 전용입니다.'})
                try:
                    job=agent_jobs.JOBS.get(q.get('id',''))
                    allowed=set(publish_set()[0])|local_trial_ids(self)
                    if set(job['customers'])-allowed:return self.send(403,{'error':'고객 접근 권한을 확인해 주세요.'})
                    return self.send(200,job)
                except ValueError as exc:return self.send(409,{'error':str(exc)})
            if u.path == '/api/strategy/evidence':
                pid = q.get('customer', '')
                customer = next((p for p in library_personas()['personas'] if p['id'] == pid), None)
                if customer is None and pid in local_trial_ids(self):
                    from private_intake_view import project as intake_project
                    customer = intake_project(pid, strategy=True)['customer']
                if customer is None:
                    return self.send(403, {'error': '현재 환경에서 열람할 수 없는 고객입니다.'})
                from strategy_evidence import project
                return self.send(200, project(customer, reviewer=reviewer_ok(self), links=library_links([customer]).get('links', {}) if reviewer_ok(self) else None))
            if u.path == '/api/strategy/options':
                from strategy_options import strategy_options
                return self.send(200, strategy_options())
            if u.path == '/api/room/options':
                from room_options import room_options
                return self.send(200, room_options())
            if u.path == '/api/runtime/capabilities':
                from operator_choice.autonomy_v1.autonomous_agent import POLICY as autonomous_policy, LIVE_POLICY as live_policy, POLICIES as autonomous_policies
                local = DEPLOY != 'public' and self.client_address[0] in ('127.0.0.1','::1')
                return self.send(200,dict(common_candidate=local and os.environ.get('HILLINK_V12Z_COMMON')=='1',
                    autonomous_agent=local and os.environ.get('HILLINK_AUTONOMOUS_AGENT')=='1',
                    autonomous_policy=autonomous_policy,live_policy=live_policy,replay_policies=sorted(autonomous_policies),
                    agent_mode=os.environ.get('HILLINK_AGENT_MODE','off') if local else 'off',
                    llm_strategy=local and reviewer_ok(self) and os.environ.get('HILLINK_AGENT_MODE') in ('live','replay') and (os.environ.get('HILLINK_AGENT_MODE')=='replay' or os.environ.get('HILLINK_LLM_EXTERNAL_OPT_IN')=='1'),
                    judgment_modes=dict(rules=True,replay=local and os.environ.get('HILLINK_AUTONOMOUS_AGENT')=='1',live=local and visit_execution.live_status()[0]),
                    native_hybrid=local and os.environ.get('HILLINK_NATIVE_HYBRID')=='1',hybrid_mode=os.environ.get('HILLINK_HYBRID','off') if local else 'off',
                    catalog_policy='C01_HOTEL_CATALOG_V1',hybrid_policy='SELECTIVE_V12Z_NATIVE_V1',isolated_customers=sorted(local_trial_ids(self)) if local else [],
                    supported=['customer','0_to_3_nights','date','five_event_cards','weather_with_explicit_source_rules','arrival_time','explicit_order_quantities','catalog_price_overrides','catalog_discount_percent','catalog_service_open_overrides'],
                    service_open_venues={'GEUMRYONG':'18:00','MOEGI':'18:00','ONDAL':'18:00','MYONGWOLGWAN':'17:30'},
                    limited=['weather_is_advisory_without_explicit_rule','unconfirmed_child_age_requires_declared_model_or_age','no_actual_booking','no_venue_wide_discount'],default_promotion=False))
            if u.path == '/api/runtime/intake':
                pid = q.get('customer', '')
                if pid not in local_trial_ids(self):
                    return self.send(403, {'error':'비공개 격리 검수에서 등록된 고객만 열 수 있습니다','code':'E_PRIVATE_INTAKE_ACCESS'})
                from private_intake_view import project
                return self.send(200, project(pid))
            if u.path == "/api/turn/meta":
                meta = turn_run({"op": "meta", "turn": q.get("turn", "dinner")})
                if not reviewer_ok(self) and isinstance(meta, dict) and isinstance(meta.get("personas"), list):   # CL-1024-20 — 게시 승인 고객만
                    appr = set(publish_set()[0]) | local_trial_ids(self)
                    meta = dict(meta, personas=[p for p in meta["personas"] if p.get("id") in appr])
                if isinstance(meta,dict) and isinstance(meta.get("personas"),list):
                    trial = local_trial_ids(self)
                    meta = dict(meta,personas=[dict(p,isolated_qa=True) if p.get("id") in trial else p for p in meta["personas"]])
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
            if u.path == "/api/library/display-review":
                if not reviewer_ok(self):
                    return self.send(403, {"error": "LOCAL_REVIEWER_REQUIRED"})
                from profile_display_review import load
                return self.send(200, load())
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
                        boundary.cache_path(CACHE, f.stem)
                        m = json.loads(f.read_text(encoding="utf-8"))
                        out.append({"key": m["key"], "date": m["date"], "scenario": m["scenario"], "scale": m["scale"], "n": m["n"], "built": m["built"],
                                    "theta": m.get("theta") or {}, "knobs": m.get("knobs", ""), "model_ver": m.get("model_ver"), "input_ver": m.get("input_ver")})
                    except Exception:
                        pass
                return self.send(200, out)
            if u.path == "/api/day/status":
                key = q["key"]
                with agent_jobs.JOBS.lock:
                    jid=agent_jobs.JOBS.keys.get('legacy-day:'+key)
                    job=agent_jobs.JOBS.rows.get(jid,{})
                    if job.get('status') in ('QUEUED','RUNNING'):
                        return self.send(200,{'status':'running','key':key})
                    if job.get('status') in ('ERROR','CANCELLED'):
                        return self.send(200,{'status':'error','error':job.get('error','DAY_EXECUTION_FAILED')})
                done = (CACHE / f"{key}.json").exists() and key not in RUNNING
                p = RUNNING.get(key)
                if p is not None and p.poll() is not None:
                    RUNNING.pop(key, None)
                    done = (CACHE / f"{key}.json").exists()
                    if not done:
                        err = (p.stderr.read() if p.stderr else "") or "계산 실패"
                        return self.send(200, {"status": "error", "error": "DAY_EXECUTION_FAILED"})
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
                body = boundary.cache_path(CACHE, q["key"], ".l5.csv").read_bytes()
                self.send_response(200); self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="L5_{q["key"]}.csv"'); self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            if u.path == "/api/bands":
                # 비교가 있는 시드 묶음 전부 — 변칙 시나리오 · 가설 예측표 (질문 탭)
                out = []
                for f in sorted(CACHE.glob("band_*.json")):
                    try:
                        boundary.cache_path(CACHE, f.stem)
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
                    execution.run([sys.executable, str(HERE / "check_flow.py"), "--key", key], capture_output=True, text=True)
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
        except boundary.RequestError as e:
            self.close_connection = True
            return self.send(e.status, {'error': e.code, 'code': e.code})
        except execution.Busy:
            return self.send(503, {'code': 'EXECUTION_CAPACITY_FULL'})
        except subprocess.TimeoutExpired:
            return self.send(504, {'code': 'EXECUTION_TIMEOUT'})
        except (ValueError, KeyError, TypeError) as exc:
            if str(exc)=='JOB_QUEUE_FULL':return self.send(429,{'code':'JOB_QUEUE_FULL'})
            return self.send(400, {'code': 'INVALID_REQUEST'})
        except Exception as e:
            return self.send(500, safe_error(self, e))

    def do_POST(self):
        u = urlparse(self.path)
        try:
            boundary.guard(self)
            if DEPLOY == 'public' and u.path in ('/api/day', '/api/guest', '/api/review', '/api/lab', '/api/packages'):
                return self.send(403, {'code': 'PRIVATE_LEGACY_API_DISABLED'})
            cfg = self.body()
            if u.path == '/api/agent/jobs/cancel':
                if not reviewer_ok(self):return self.send(403,{'code':'LOCAL_REVIEWER_REQUIRED'})
                try:return self.send(200,agent_jobs.JOBS.cancel(cfg.get('job_id')))
                except ValueError:return self.send(409,{'code':'JOB_NOT_CANCELLABLE'})
            if cfg.get('crowd'):
                boundary.cache_family(CACHE, cfg['crowd'])
            if u.path.startswith('/api/strategy/agent') or u.path=='/api/visit/jobs':
                origin=self.headers.get('Origin')
                if origin and urlparse(origin).netloc!=self.headers.get('Host'):
                    return self.send(403,{'error':'현재 제품 화면에서 명시적으로 실행해 주세요.'})
            if u.path in ('/api/strategy/agent','/api/strategy/agent/experiment'):
                if not reviewer_ok(self) or os.environ.get('HILLINK_AGENT_MODE') not in ('live','replay') or (os.environ.get('HILLINK_AGENT_MODE')=='live' and os.environ.get('HILLINK_LLM_EXTERNAL_OPT_IN')!='1'):
                    return self.send(403,{'error':'LLM 로컬 실행 설정과 누적 비용 한도를 먼저 확인해 주세요.'})
                if not isinstance(cfg,dict):return self.send(400,{'error':'요청 형식 오류'})
                try:
                    from operator_choice.autonomy_v1.agent_provider import digest
                    allowed=set(publish_set()[0])|local_trial_ids(self)
                    if u.path.endswith('/experiment'):
                        pair=agent_jobs.pair(cfg)
                        ids=pair[0]['personas']
                        if set(ids)-allowed:raise ValueError('CUSTOMER_NOT_AUTHORIZED')
                        job=agent_jobs.JOBS.submit(digest(dict(type='PRICE_PAIR',request=cfg)),ids,lambda:execute_agent_pair(pair))
                    else:
                        if set(cfg)-{'customers','run_id','goal','source_actions'}:raise ValueError('CLIENT_EVIDENCE_NOT_ACCEPTED')
                        ids=cfg.get('customers')
                        if not isinstance(ids,list) or not 1<=len(ids)<=28 or len(set(ids))!=len(ids) or set(ids)-allowed:raise ValueError('CUSTOMER_SCOPE_INVALID')
                        goal=cfg.get('goal',{})
                        if goal.get('basis') not in ('ACTUAL_RUN','PROFILE_HYPOTHESIS','OPERATOR_ASSUMPTION'):raise ValueError('EXPLICIT_ANALYSIS_BASIS_REQUIRED')
                        if goal['basis']=='ACTUAL_RUN':
                            entry=agent_jobs.source(cfg.get('run_id'))
                            if set(ids)-set(entry['flow']['plans']):raise ValueError('SOURCE_CUSTOMER_MISMATCH')
                        bundles={pid:strategy_bundle(pid,self) for pid in ids}
                        job=agent_jobs.JOBS.submit(digest(dict(type='STRATEGY',request=cfg)),ids,lambda:execute_agent_analysis(cfg,bundles))
                    return self.send(202,job)
                except (ValueError,KeyError,TypeError) as exc:
                    if str(exc)=='JOB_QUEUE_FULL':return self.send(429,{'code':'JOB_QUEUE_FULL'})
                    return self.send(400,{'error':'고객·실제 소비 결정·운영 목표 또는 지원 개입을 확인해 주세요.'})
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
                    if "event_only" in cfg and not isinstance(cfg["event_only"], bool):
                        return self.send(400, {"error": "비교 유형을 확인해 주세요"})
                    comparison = receipts.compare(cfg.get("baseline_id"), cfg.get("scenario_id"), cfg.get("customer_type"), cfg.get("stay_status", "all"), cfg.get("event_only", False))
                except receipts.ReceiptError as e:
                    return self.send(409, {"error": str(e), "code": "E_RECEIPT_COMPARE"})
                if any(p not in (set(publish_set()[0]) | local_trial_ids(self)) for p in comparison["customers"]):
                    return self.send(403, {"error": "게시 승인 고객만 확인합니다"})
                return self.send(200, comparison)
            if u.path == "/api/ledger/filter":
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식을 확인해 주세요"})
                try:
                    ledger = receipts.lookup(cfg.get("run_id"), cfg.get("customer_type"), cfg.get("stay_status", "all"))
                except receipts.ReceiptError as e:
                    return self.send(409, {"error": str(e), "code": "E_RECEIPT_RUN"})
                if any(p not in (set(publish_set()[0]) | local_trial_ids(self)) for p in ledger["receipts"]):
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
                if isinstance(res, dict):
                    res.pop("profile_sha", None)  # comparison fingerprint stays inside the server-issued ledger context
                return self.send((409 if res.get("code") == "E_FLOW_INPUT_MISSING" else 400) if "error" in res else 200, res)
            if u.path in ("/api/visit","/api/visit/jobs"):   # one server-owned source for sync/async visits
                if not isinstance(cfg, dict):
                    return self.send(400, {"error": "요청 형식 오류"})
                appr = publish_set()[0]
                ids = cfg.get("personas") or []
                appr = set(appr) | local_trial_ids(self)
                extra = [x for x in ids if x not in appr]
                if extra:
                    return self.send(403, {"error": "게시 승인 고객만 실행합니다", "n": len(extra)})
                if "include_ledger" in cfg and not isinstance(cfg["include_ledger"], bool):
                    return self.send(400, {"error": "영수증 요청 형식을 확인해 주세요"})
                body = {k: cfg[k] for k in ("personas", "duration", "event_mode", "seed", "start_date", "package_id", "visit_conditions", "behavior_engine", "simulation_mode", "scenario", "catalog_policy", "catalog_options", "hybrid_policy", "judgment_mode", "environment", "virtual_room_rates", "breakfast_policy", "behaviour_prior", "reference_profile", "behaviour_prior_coefficient") if k in cfg}
                if u.path.endswith('/jobs'):
                    if not reviewer_ok(self):return self.send(403,{'error':'로컬 검수 환경 전용입니다.'})
                    from operator_choice.autonomy_v1.agent_provider import digest
                    try:return self.send(202,agent_jobs.JOBS.submit(digest(dict(type='VISIT',request=body)),ids,lambda:completed_visit(body)))
                    except ValueError:return self.send(429,{'code':'JOB_QUEUE_FULL'})
                try:
                    status,res = completed_visit(body,cfg.get('include_ledger',False),prepare_response=True)
                except receipts.ReceiptError:
                    return self.send(409, {"error": "날짜별 장면 지출과 방문 영수증을 대조하지 못했습니다", "code": "E_RECEIPT_BALANCE"})
                return self.send(status,res)
            if u.path == "/api/population/experiment":   # research: group A/B on the rules engine (no model call), local review only
                if not reviewer_ok(self):return self.send(403,{'error':'로컬 검수 환경 전용 연구 기능입니다.'})
                try:
                    import population_lab as PL
                    spec=population_experiment_spec(cfg,set(publish_set()[0])|local_trial_ids(self))
                    from operator_choice.autonomy_v1.agent_provider import digest
                    job=agent_jobs.JOBS.submit(digest(dict(type='POPULATION_AB',request=spec)),spec['personas'],lambda:PL.experiment(spec))
                    return self.send(202,job)
                except ValueError as exc:
                    if str(exc)=='JOB_QUEUE_FULL':return self.send(429,{'code':'JOB_QUEUE_FULL'})
                    return self.send(400,{'error':'집단 실험 조건을 확인해 주세요.','reason':str(exc)})
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
                r = execution.run(STAY, input=json.dumps(cfg, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
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
                r = execution.run(LAB, input=json.dumps(cfg, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=HERE, timeout=300)
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "lab 오류")
                return self.send(200, json.loads(r.stdout))
            if u.path == "/api/day":
                scale=cfg.get('scale',1.0)
                if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not 0<scale<=1:
                    raise boundary.RequestError('INVALID_SCALE')
                theta = cfg.get("theta") or {}
                key = day_key(cfg["date"], cfg.get("scenario", "none"), cfg.get("scale", 1.0), theta)
                boundary.cache_family(CACHE, key)
                if (CACHE / f"{key}.json").exists() and not cfg.get("force") and _fresh(CACHE / f"{key}.json"):
                    return self.send(200, {"status": "done", "key": key})
                boundary.cache_family(CACHE, key)
                job = agent_jobs.JOBS.submit('legacy-day:' + key, [], lambda: engine('day', '--date', cfg['date'], '--scenario', cfg.get('scenario', 'none'), '--scale', str(cfg.get('scale', 1.0)), '--theta', json.dumps(theta), timeout=900), reuse_completed=False)
                return self.send(200, {'status': 'done' if job['status']=='DONE' else 'error' if job['status']=='ERROR' else 'running', 'key': key})
            return self.send(404, {"error": "없음"})
        except boundary.RequestError as e:
            self.close_connection = True
            return self.send(e.status, {'error': e.code, 'code': e.code})
        except execution.Busy:
            return self.send(503, {'code': 'EXECUTION_CAPACITY_FULL'})
        except subprocess.TimeoutExpired:
            return self.send(504, {'code': 'EXECUTION_TIMEOUT'})
        except (ValueError, KeyError, TypeError) as exc:
            if str(exc)=='JOB_QUEUE_FULL':return self.send(429,{'code':'JOB_QUEUE_FULL'})
            return self.send(400, {'code': 'INVALID_REQUEST'})
        except Exception as e:
            return self.send(500, safe_error(self, e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    # 10/14 손님 상세 기록은 크기(약 20MB) 때문에 압축본(.guests.jsonl.gz)으로 옮길 때가 있다 — 풀린 파일이 없으면 시작할 때 푼다
    import gzip, shutil
    if CACHE.is_symlink():
        raise boundary.RequestError('CACHE_LINK_FORBIDDEN',403)
    for gz in CACHE.glob("*.guests.jsonl.gz"):
        if gz.is_symlink():
            continue
        plain = gz.with_suffix("")
        if plain.is_symlink():
            continue
        if not plain.exists() or gz.stat().st_mtime > plain.stat().st_mtime:      # 10/16 새로 옮긴 압축본이 있으면 예전 풀린 파일을 바꾼다
            with gzip.open(gz, "rb") as src, plain.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    # 10/26 — 로컬 보관 실행 입력 4개 점검(없으면 해당 고객은 계산 대신 '입력 미연결' 안내 · 서버 오류 아님)
    LOCAL_INPUTS = [STATIC / "persona_library.local.json", STATIC / "persona_links.local.json", HERE / "links.local.csv",
                    HERE.parent / "experiments" / "persona_live" / "operator_choice" / "operator_world_v1_1" / "turn_personas_ext.local.json"]
    miss = [f.name for f in LOCAL_INPUTS if not f.exists()]
    if miss:
        print("⚠ 로컬 보관 입력 없음: " + ", ".join(miss) + " — 해당 자료가 필요한 고객의 프로필 · 원문 링크 · 실행이 빠질 수 있습니다(실행 입력이 없으면 '입력 미연결' 안내)")
    srv = boundary.LocalHTTPServer(("127.0.0.1", a.port), H)
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
