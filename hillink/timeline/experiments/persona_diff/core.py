"""persona_diff 공통 층 (10/20 · 총괄 C · 격리) — 고객 입력이 판단 계산에 실제로 닿는지 재는 도구

공용 모델(agent_v4) · 고객 파일(persona_blogNN.py · _auto.py)은 import 만 한다. 감싸지도(monkeypatch) 않는다.
점수 · 선택은 agent_v4.run_agent 가 낸 Trace 그대로 읽는다 — 설명을 따로 만들지 않고 계산 항(why)을 해부한다.

  load_persona('blog41')            손 정답본(A 트랙 입력)   · load_persona('blog41', auto=True)  자동 추출본(B 트랙 입력)
  run(persona, start_at, k=12)      같은 손님 · 같은 시작 · 난수 revenue.SEED + i (persona_lab 과 같음)
  parse_term('대기 12분 -0.36')     → ('대기 12분', -0.36)
"""
from __future__ import annotations

import contextlib, importlib.util, io, random, re, sys
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parents[1]
if str(TL) not in sys.path:
    sys.path.insert(0, str(TL))

with contextlib.redirect_stdout(io.StringIO()):
    import agent_v4                     # noqa: E402
    from agent_v0 import Persona         # noqa: E402,F401

SEED_BASE = 20260930                     # revenue.SEED — tests/test_core.py 가 같은지 확인한다(revenue 를 여기서 import 하지 않으려고)
K = 12
TEAMS = ["blog25", "blog41", "blog36", "blog43", "blog26", "blog58", "blog59", "blog57", "blog40", "blog46"]   # 10/20 잠정 10팀(원문 검증 전)
TERM_RE = re.compile(r"^(.*\S)\s+([+-]\d+\.\d+)$")


def load_module(blog: str, auto: bool = False):
    """고객 파일을 모듈로 — 이름이 겹치지 않게 따로 싣는다(손 · 자동을 한 프로세스에서 비교)."""
    name = f"persona_{blog}{'_auto' if auto else ''}"
    path = TL / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_pdiff_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)
    return mod


def load_persona(blog: str, auto: bool = False):
    m = load_module(blog, auto)
    return m.PERSONA, m.START_AT


def parse_term(s: str) -> tuple[str, float | None]:
    """why 한 줄 → (라벨, 값). 값이 없는 줄(예: '빈 시간 채우기 (… 전)')은 None — 점수에 더해지지 않는 표시."""
    m = TERM_RE.match(s)
    return (m.group(1), float(m.group(2))) if m else (s, None)


def decisions(traces) -> list[dict]:
    out = []
    for t in traces:
        meta = t.meta or {}
        alts = [dict(key=a["key"], label=a["label"], pts=a["pts"], wait=a["wait"], terms=[parse_term(w) for w in a["why"]])
                for a in meta.get("alts", [])]
        out.append(dict(turn=t.turn, key=meta.get("key"), label=t.chosen, t_in=t.start, pts=meta.get("pts"),
                        rank=meta.get("rank"), top_gap=meta.get("top_gap"), wait=meta.get("wait"), terms=[parse_term(w) for w in t.why],
                        alts=alts, n_rejected=len(meta.get("rejected", []))))
    return out


def run(persona, start_at: datetime, k: int = K, theta: dict | None = None, capacity_factory=None) -> list[list[dict]]:
    """k 회 — 회마다 결정 목록. 공용 계수 THETA_FIT 이 기본(실험 덮어쓰기는 theta 로만)."""
    th = dict(agent_v4.THETA_FIT, **(theta or {}))
    runs = []
    for i in range(k):
        cap = capacity_factory() if capacity_factory else None
        _, tr = agent_v4.run_agent(persona, start_at, verbose=False, theta=th, rng=random.Random(SEED_BASE + i), capacity=cap)
        runs.append(decisions(tr))
    return runs


PROCEDURE = agent_v4.CHECKIN_KEYS          # 발렛 · 주차 · 도착 · 체크인 절차 — 행동 비교에서 뺀다(도착 수단을 빼면 이 키가 사라질 뿐 선택이 바뀐 게 아님)


def seqs(runs) -> list[tuple[str, ...]]:
    return [tuple(d["key"] for d in r if d["key"] not in PROCEDURE) for r in runs]


def place_p(runs) -> dict[str, float]:
    """행동 키별 '그 체류에서 한 번이라도 고른' 비율(체크인 절차 제외)."""
    c = Counter()
    for r in runs:
        c.update({d["key"] for d in r if d["key"] not in PROCEDURE})
    return {k: round(v / len(runs), 4) for k, v in sorted(c.items())}


def tv_distance(p: dict, q: dict) -> float:
    """두 체류 이용 확률표의 차 — 행동마다 |p − q| 의 최대(가장 크게 바뀐 행동)."""
    keys = set(p) | set(q)
    return round(max((abs(p.get(k, 0) - q.get(k, 0)) for k in keys), default=0.0), 4)


def compare(base_runs, other_runs) -> dict:
    sb, so = seqs(base_runs), seqs(other_runs)
    pb, po = place_p(base_runs), place_p(other_runs)
    delta = {k: round(po.get(k, 0) - pb.get(k, 0), 4) for k in sorted(set(pb) | set(po)) if abs(po.get(k, 0) - pb.get(k, 0)) > 1e-9}
    return dict(identical=sum(x == y for x, y in zip(sb, so)), k=len(sb), max_abs_delta=tv_distance(pb, po), place_p_delta=delta)


def with_fields(persona, **kw):
    return replace(persona, **kw)


def at_common_date(start_at: datetime, day: datetime) -> datetime:
    """공통 가상 날짜 — 각 팀의 도착 시각(시:분)은 그대로, 날짜만 옮긴다(가상 조건)."""
    return day.replace(hour=start_at.hour, minute=start_at.minute)
