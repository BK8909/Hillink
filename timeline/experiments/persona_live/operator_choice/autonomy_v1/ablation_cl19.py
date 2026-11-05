"""CL-19 보충 — 프로파일 제거 실험: 난수 경로 변화와 실제 성향 기여를 구분.
같은 방문 조건(시드 0의 visit_state)에 결정 난수만 S개 바꿔 실행 → 활동 빈도 분포.
  noise  = 전체 프로파일 시드 절반(0..S/2-1) vs 나머지 절반의 분포 차(TVD) — 난수 경로만으로 생기는 차이
  shift  = 전체 프로파일 S개 vs 프로파일 제거 S개의 분포 차(TVD)
  기여   = shift − noise (양수가 클수록 성향 · 후기 근거가 실제로 행동을 바꿈)
단일 시드 '로그가 달라짐'(CL-18 11/11)은 난수 경로 변화와 섞여 있으므로 이 지표로 대체한다.
  python3 -m operator_choice.autonomy_v1.ablation_cl19 --seeds 20 --out DIR
"""
import argparse, collections, json
from pathlib import Path
from . import agent_day as AD
from ..operator_world_v1_1 import turn_view as TV

SKIP = {"move", "wait", "idle", "arrive", "leave", "wake", "checkin", "checkout", "pack", "unpack", "sleep"}


def run(p, inp, seed, ablate):
    P, bars, lib = inp
    sc = AD.scenario("base", seed=0)
    real = AD.Agent(p, P, bars, lib, sc)
    if ablate:
        P0 = {k: dict(v, traits=TV._empty_traits()) for k, v in P.items()}
        a = AD.Agent(p, P0, {k: [] for k in bars}, {k: dict(v, engine={}) for k, v in lib.items()}, sc)
        a.vs, a.B, a.stay, a.phase, a.N, a.C = real.vs, real.B, real.stay, real.phase, real.N, real.C
        a.room = AD.SP.room(a.B) if a.stay else None; a.loc = a.room if a.phase in ("mid", "checkout") else "HOTEL_GATE"; a.t = real.t; a.checked_in = real.checked_in; a.end = real.end
    else:
        a = real
    a.rng_base = f"autonomy|{p}|{seed}"   # 결정 난수만 바꿈(방문 조건 고정)
    w = AD.World(sc); g = 0
    while AD.decide(a, w) and g < 90:
        g += 1
    r = AD.finish(a)
    return [x for x in r["log"] if x["act"] not in SKIP]


def dist(runs):
    c = collections.Counter(x["act"].split(":")[0] for r in runs for x in r)
    n = len(runs)
    return {k: v / n for k, v in c.items()}


def tvd(a, b):
    ks = set(a) | set(b)
    sa, sb = sum(a.values()) or 1, sum(b.values()) or 1
    return round(0.5 * sum(abs(a.get(k, 0) / sa - b.get(k, 0) / sb) for k in ks), 3)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=20); ap.add_argument("--out", required=True)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    inp = AD.load_inputs(); S = a.seeds; res = {}
    for p in AD.DEMO:
        full = [run(p, inp, s, False) for s in range(S)]
        abl = [run(p, inp, s, True) for s in range(S)]
        df, da = dist(full), dist(abl)
        noise = max(tvd(dist(full[:S // 2]), dist(full[S // 2:])), tvd(dist(abl[:S // 2]), dist(abl[S // 2:])))
        shift = tvd(df, da)
        one_seed_changed = sum(1 for f, b in zip(full, abl) if [x["act"] for x in f] != [x["act"] for x in b])
        seed_pairs_diff = sum(1 for i in range(S) for j in range(i + 1, S) if [x["act"] for x in full[i]] != [x["act"] for x in full[j]]) / max(1, S * (S - 1) / 2)
        delta = sorted(((k, round(df.get(k, 0) - da.get(k, 0), 2)) for k in set(df) | set(da)), key=lambda kv: -abs(kv[1]))[:6]
        why = {}
        for k, _ in delta:
            ev = [e for r in full for x in r if x["act"].split(":")[0] == k for e in x["evidence"]]
            why[k] = dict(review_facts=sorted({f for e in ev if e["type"] == "후기에서 확인" for f in e["fact_ids"]})[:5],
                          traits=sorted({t for e in ev if e["type"] == "프로파일 기반 추론" for t in (e.get("traits") or [])})[:5])
        res[p] = dict(seeds=S, noise_tvd=noise, shift_tvd=shift, contribution=round(shift - noise, 3), single_seed_changed=f"{one_seed_changed}/{S}",
                      full_seed_pairs_differ=round(seed_pairs_diff, 2), top_shift=delta, shift_basis=why,
                      verdict="성향 기여 뚜렷" if shift - noise >= 0.15 else "성향 기여 있음" if shift - noise >= 0.05 else "난수 경로 차이와 구분 어려움")
    (out / "ablation_cl19.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# 프로파일 제거 실험(난수 경로 vs 성향 기여)\n", f"같은 방문 조건 · 결정 난수 {S}개 · 규칙 기반 실행\n",
          "| 고객 | 시드별 로그 변화(단일 시드 기준) | 같은 프로파일 시드끼리 로그 다름 | 난수 잡음 TVD | 제거 시 분포 변화 TVD | 성향 기여 | 판정 | 가장 크게 변한 행동(전체−제거, 하루당 횟수) |", "|---|---|---|---:|---:|---:|---|---|"]
    for p, v in res.items():
        md.append(f"| {p} | {v['single_seed_changed']} | {v['full_seed_pairs_differ']:.0%} | {v['noise_tvd']} | {v['shift_tvd']} | {v['contribution']} | {v['verdict']} | {', '.join(f'{k} {d:+}' for k, d in v['top_shift'][:4])} |")
    (out / "ablation_cl19.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
