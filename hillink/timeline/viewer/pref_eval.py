"""목적별 선호 식당의 기여도 (10/16 · 작업배정 1016 항목 19 · 데이터 기여도 1단계에 한 줄 더함)

  python3 pref_eval.py run      # 10/10 · v4.1 · 시드 0 · 1 · 2 × 세 조건 (몇 분) → static/pref_eval.json
  python3 pref_eval.py one A 0  # 한 조건 · 한 시드 (내부용 · 별도 프로세스로 돈다)

무엇을 하나 — 하루 손님(고객 유형표)의 '가고 싶은 식당' 을 정하는 입력만 바꾸고, 업장별 이용 인원이 온톨로지 10/10 과 얼마나 맞는지 본다.
  A  지금 모델 · 목적별 선호 식당 (dining_pref.csv · 목적마다 다른 식당 비중)
  P1 목적 정보 제거 · 선호를 가질 확률은 그대로 두고, 식당 비중을 목적과 무관하게 전체 평균으로
  P0 선호 제거 · '가고 싶은 식당' 을 아무도 갖지 않음
모델 코드 · 입력 표는 바꾸지 않는다(이 스크립트 프로세스 안에서 generate.pick_prefer 만 감쌈). 계산 결과는 화면 캐시가 아니라 임시 폴더에 쓴다.
비교는 같은 날 · 같은 시드 짝. 온톨로지 쪽 값은 ontology_l3_1010_persons.csv 의 '판매 · 사용(인 · 회)' 이고, 정의 차이가 큰 럭스바 · 파빌리온은 뺀다(6개 식당).
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import math
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
OUT = HERE / "static" / "pref_eval.json"
TMP = HERE / "cache" / "pref_eval"
DATE = "2026-10-10"
SEEDS = (0, 1, 2)
CONDS = {"A": "지금 모델 (목적별 선호 식당)", "P1": "목적 정보 제거 (선호 확률은 그대로 · 식당 비중은 목적 무관 평균)", "P0": "선호 식당 제거 (아무도 갖지 않음)"}
VEN = {"금룡": "GEUMRYONG", "온달": "ONDAL", "명월관": "MYONGWOLGWAN", "모에기": "MOEGI", "피자힐": "PIZZA_HILL", "더뷔페": "THE_BUFFET"}


def one(cond, seed):
    sys.path.insert(0, str(HERE)); sys.path.insert(0, str(TL))
    import engine, generate as G
    engine.CACHE = Path(tempfile.mkdtemp(prefix=f"pref_{cond}_{seed}_", dir=TMP))       # 화면 캐시와 섞이지 않게
    if cond == "P0":
        G.pick_prefer = lambda purpose, dining, rng, p: ()
    elif cond == "P1":
        orig = G.pick_prefer

        def flat(purpose, dining, rng, p):
            if purpose not in dining or rng.random() >= p:      # 선호를 가질지 정하는 난수는 지금과 같은 자리에서 뽑는다
                return ()
            pool = {}
            for rows in dining.values():
                for v, w in rows:
                    pool[v] = pool.get(v, 0) + w / len(dining)
            venues, w = zip(*sorted(pool.items()))
            return (rng.choices(venues, weights=w)[0],)
        G.pick_prefer = flat
    theta = dict(engine.V4, seed=seed) if seed else dict(engine.V4)
    with contextlib.redirect_stdout(io.StringIO()):
        engine.day(DATE, "none", 1.0, theta)
    res = None
    for f in engine.CACHE.glob("*.json"):
        if not f.name.endswith(".progress.json"):
            res = json.loads(f.read_text(encoding="utf-8"))
    vd = res.get("venue_detail", {})
    out = dict(cond=cond, seed=seed, persons={k: (vd.get(loc) or {}).get("persons_day", 0) for k, loc in VEN.items()},
               total_krw=res.get("total"), n=res.get("n"), switch_teams=sum(1 for g in res.get("guests", []) if (g.get("n_switch") or 0) > 0))
    print(json.dumps(out, ensure_ascii=False))


def run():
    TMP.mkdir(parents=True, exist_ok=True)
    onto = {r["업장"]: float(r["온톨로지 10/10 판매·사용(인·회 · 한호 채집)"]) for r in csv.DictReader(open(TL / "ontology_l3_1010_persons.csv", encoding="utf-8-sig")) if r["업장"] in VEN}
    jobs = [(c, s) for c in CONDS for s in SEEDS]

    def go(job):
        c, s = job
        r = subprocess.run([sys.executable, __file__, "one", c, str(s)], capture_output=True, text=True, cwd=str(HERE))
        line = [x for x in r.stdout.splitlines() if x.startswith("{")]
        if not line:
            raise RuntimeError(r.stderr[-800:])
        print(c, s, line[-1][:160], flush=True)
        return json.loads(line[-1])
    with ThreadPoolExecutor(max_workers=3) as ex:
        R = list(ex.map(go, jobs))
    by = {(r["cond"], r["seed"]): r for r in R}
    tot_onto = sum(onto.values())

    def fit(p):
        """식당 6곳 · 모델 ÷ 온톨로지 비율의 로그 절대값 평균 (0 이면 모두 같음) · 90~110% 안 개수 · 구성비 차이(절반 합 · %p)"""
        lr = [abs(math.log(max(p[k], 1) / onto[k])) for k in onto]
        tm = sum(p[k] for k in onto) or 1
        comp = 50 * sum(abs(p[k] / tm - onto[k] / tot_onto) for k in onto)
        return dict(mean_abs_log=round(sum(lr) / len(lr), 3), within=sum(1 for k in onto if 0.9 <= p[k] / onto[k] <= 1.1), comp_gap_pp=round(comp, 1))
    rows = []
    for c in CONDS:
        per = [by[(c, s)] for s in SEEDS]
        f = [fit(r["persons"]) for r in per]
        mean_p = {k: round(sum(r["persons"][k] for r in per) / len(per)) for k in VEN}
        row = dict(id=c, name=CONDS[c], persons=mean_p, ratio={k: round(mean_p[k] / onto[k] * 100) for k in VEN},
                   fit=dict(mean_abs_log=round(sum(x["mean_abs_log"] for x in f) / len(f), 3), within=round(sum(x["within"] for x in f) / len(f), 1),
                            comp_gap_pp=round(sum(x["comp_gap_pp"] for x in f) / len(f), 1)),
                   switch_teams=round(sum(r["switch_teams"] for r in per) / len(per)), total_eok=round(sum((r["total_krw"] or 0) for r in per) / len(per) / 1.1 / 1e8, 2))
        if c != "A":       # 시드별 짝 차이 — 구성비 차이(%p)
            d = [fit(by[(c, s)]["persons"])["comp_gap_pp"] - fit(by[("A", s)]["persons"])["comp_gap_pp"] for s in SEEDS]
            row["d_comp_gap_pp"] = dict(mean=round(sum(d) / len(d), 1), min=round(min(d), 1), max=round(max(d), 1), same_sign=sum(1 for x in d if x > 0) if sum(d) > 0 else sum(1 for x in d if x < 0))
        rows.append(row)
    res = dict(built=datetime.now().strftime("%Y-%m-%d %H:%M"), model_ver=__import__("version").model_ver(), date=DATE, seeds=list(SEEDS),
               onto=onto, rows=rows,
               note="하루 손님(고객 유형표)의 '가고 싶은 식당' 입력만 바꾼 짝 비교. 온톨로지 쪽 값은 10/10 판매 · 사용 인원이며 업장마다 정의가 달라 비율 자체보다 조건 사이의 차이를 본다. 럭스바 · 파빌리온 제외.",
               caveat="온톨로지는 참조 모델이지 실측이 아니다. 구성비가 온톨로지에 가까워졌다는 것은 '참조 모델과 맞는다' 는 뜻이지 실제 고객 행동에 더 가깝다는 뜻이 아니다.")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(r["id"], r["fit"], r.get("d_comp_gap_pp"), r["ratio"], r["switch_teams"], r["total_eok"])


if __name__ == "__main__":
    if sys.argv[1] == "one":
        one(sys.argv[2], int(sys.argv[3]))
    else:
        run()
