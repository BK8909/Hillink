"""개별 페르소나 실험실 — 화면용 결과 읽기 (10/20 · U · UX 23차)

R 세션의 실행 결과 파일(experiments/persona_lab/runs/<판>/<blog>/<조건>.json · ④ 형식)만 읽어 화면에 넘긴다.
- 모델을 돌리지 않는다(엔진 · 평가 로직 import 없음). 결과가 없는 변수는 '준비 전'으로 돌려준다.
- 후기 근거(방문 · 미방문 · 지나감 판단 요지)는 페르소나 파일을 읽기만 한다.
- 실험 날짜는 가상 조건이다(후기의 실제 방문 시점이 아님).

  echo '{"blog":"blog41","var":"winefair"}' | python3 lab.py
  echo '{"avail":true}' | python3 lab.py
"""
from __future__ import annotations

import contextlib, importlib, io, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path.insert(0, str(TL))
RUNS = TL / "experiments" / "persona_lab" / "runs"
PLAN = "baseline_0"   # R 이 새 판(interest_1 등)을 내면 여기만 바꾼다

# 화면 변수 → R 조건 파일(변수 없음, 변수 있음). R 결과가 없는 변수는 이유와 함께 비활성.
VARS = {
    "winefair": dict(name="와인페어", files=("V1a_와인페어_미개최", "V1b_와인페어_개최"), focus=["와인페어"],
                     base_txt="와인페어 없음", var_txt="와인페어 개최",
                     env="2026 와인페어 10/10 ~ 10/25 토 · 일 · 11:00 ~ 15:00 · 15:30 ~ 20:00 · 포레스트 파크 · 투숙객 무료(보도자료 ◎)"),
    "riverpark": dict(name="야외 수영장(리버파크)", files=("V3a_리버파크_휴장", "V3b_리버파크_개장"), focus=["리버파크"],
                      base_txt="리버파크 휴장", var_txt="리버파크 개장",
                      env="2026 여름 시즌 리버파크 운영(공식 ◎) · '변수 없음'은 같은 날 휴장으로 가정"),
    "rain": dict(name="비(악천후)", files=None, focus=["포레스트 파크", "스카이야드", "리버파크"],
                 reason="R 실행 결과(V4 비) 파일이 아직 없습니다 — 결과가 나오면 바로 열립니다"),
}
OFF = {"autumn": "계절 효과의 운영 · 행동 근거를 조사 중입니다(모델에 계절 항 없음)",
       "beer": "테라스 운영일 · '골든 나이트' 일정이 확인되지 않았습니다(모델에 행동 없음)"}


def _load(blog, name):
    p = RUNS / PLAN / blog / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def avail() -> dict:
    out = {}
    root = RUNS / PLAN
    for bd in sorted(root.glob("blog*")) if root.exists() else []:
        out[bd.name] = {v: bool(s["files"]) and all((bd / f"{f}.json").exists() for f in s["files"]) for v, s in VARS.items()}
    # 조건 설명(가상 날짜)은 R manifest 의 conditions 에서 그대로 가져온다
    cond = {}
    for bd in sorted(root.glob("blog*")) if root.exists() else []:
        m = _load(bd.name, "manifest") or {}
        for c in m.get("conditions", []):
            cond.setdefault(c["name"], dict(virtual=c.get("virtual"), start=c.get("start"), scenario=c.get("scenario"), closed=c.get("closed")))
    vars_ = {v: dict(name=s["name"], base_txt=s.get("base_txt"), var_txt=s.get("var_txt"),
                     base=cond.get(s["files"][0]) if s["files"] else None, var=cond.get(s["files"][1]) if s["files"] else None) for v, s in VARS.items()}
    return dict(plan=PLAN, blogs=out, vars=vars_, reasons={**{v: s.get("reason") for v, s in VARS.items() if not s["files"]}, **OFF})


def _side(d: dict) -> dict:
    det = d.get("detail") or {}
    return dict(start=d["start"], virtual=d.get("virtual"), action_p=d.get("action_p", {}), place_p=d.get("place_p", {}),
                steps=det.get("steps", []), spend_total=det.get("spend_total"), K=d.get("K"), seeds=d.get("seeds"))


def compare(cfg: dict) -> dict:
    blog, var = cfg.get("blog"), cfg.get("var")
    # CL-1024-20 — 경로 · 모듈 이름을 입력 문자열로 넓히지 않음: 형식(blogNN) + 실제 결과 폴더가 있는 대상 · 등록된 변수만
    if not (isinstance(blog, str) and re.fullmatch(r"blog\d{2}", blog)) or var not in VARS or not (RUNS / PLAN / blog).is_dir():
        raise RuntimeError("허용되지 않는 실험 대상")
    spec = VARS[var]
    if not spec["files"]:
        raise RuntimeError(spec["reason"])
    a, b = (_load(blog, f) for f in spec["files"])
    if a is None or b is None:
        raise RuntimeError(f"{blog} 의 R 결과 파일({PLAN})이 없습니다")
    man = _load(blog, "manifest") or {}
    with contextlib.redirect_stdout(io.StringIO()):
        mod = importlib.import_module("persona_" + blog)
    ev = dict(visited=getattr(mod, "TRUTH_VISITED", {}), not_visited=getattr(mod, "TRUTH_NOT_VISITED", {}), passed=getattr(mod, "TRUTH_PASSED", {}))
    base, chg = _side(a), _side(b)
    acts = sorted(set(base["action_p"]) | set(chg["action_p"]))
    diff = [dict(act=x, base=base["action_p"].get(x, 0.0), var=chg["action_p"].get(x, 0.0)) for x in acts]
    for x in diff:
        x["delta"] = round(x["var"] - x["base"], 4)
    return dict(blog=blog, var=var, var_name=spec["name"], base_txt=spec["base_txt"], var_txt=spec["var_txt"], env=spec["env"], focus=spec["focus"],
                virtual=b.get("virtual"), base=base, changed=chg, diff=diff, evidence=ev, persona_name=mod.PERSONA.name,
                meta=dict(plan=PLAN, files=list(spec["files"]), model_ver=man.get("model_ver"), input_ver=man.get("input_ver"), K=b.get("K"),
                          seed_base=man.get("seed_base"), git_head=man.get("git_head"), created_at=man.get("created_at"),
                          lam_trait=(man.get("theta") or {}).get("lam_trait"), note=man.get("note"),
                          interest="평가자 관심 · 비선호 항 없음(다음 판에서 연결)"))


if __name__ == "__main__":
    cfg = json.loads(sys.stdin.read() or "{}")
    sys.stdout.write(json.dumps(avail() if cfg.get("avail") else compare(cfg), ensure_ascii=False, default=str))
