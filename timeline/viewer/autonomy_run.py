"""자율 행동 실행기 (CL-1024-18) — /api/autonomy 가 부르는 별도 프로세스.
입력: {"op":"run", "personas":[...], "mode":"one|many", "intervention":"none|wine_fair_1300|pool_check", "compare": bool, "seed": int}
출력: {"mode", "personas":{pid:{visit, log, summary}}, "compare":{pid:{cls,new,cancelled}}?, "notices", "interaction", "inputs_sha"}
· 운영자 개입은 서버의 정해진 시나리오만(자유 입력 레버 없음). 고객 ID 는 시연 11명만.
· 로그에는 사실 ID 만 싣는다(요지 · 원문 · 경로 없음). 화면은 이미 받은 라이브러리 자료로 요지를 찾는다."""
import hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
from operator_choice.autonomy_v1 import agent_day as AD  # noqa: E402

INTERVENTIONS = {
    "none": dict(label="운영자 개입 없음", changes=[]),
    "wine_fair_1300": dict(label="13:00 포레스트 파크 와인페어 개최 공지(2부 15:30~20:00 · 비투숙 성인 55,000원 · 투숙객 무료 입장)", at="13:00",
                           changes=[dict(at="13:00", label="포레스트 파크 와인페어 개최(2부 15:30~20:00 · 55,000원)", levers={"WINE_FAIR": {"available": True}})]),
    "pool_check": dict(label="실내 수영장 16:00~19:00 점검(가상 운영 변경 · 12:00 공지)", at="12:00",
                       changes=[dict(at="12:00", label="실내 수영장 16:00~19:00 점검", closed={"VISTA_POOL": ["16:00", "19:00"], "GRAND_POOL": ["16:00", "19:00"]})]),
    "pizzahill_full": dict(label="피자힐 저녁 17:30~20:30 예약 마감(가상 운영 변경 · 15:00 공지)", at="15:00",
                           changes=[dict(at="15:00", label="피자힐 저녁 17:30~20:30 예약 마감", closed={"PIZZA_HILL": ["17:30", "20:30"]})]),
}
NOISE_REJ = ("오늘 이미 이용", "뒤 활동", "쉰 지", "시즌", "자격이 필요", "운영시간 자료 없음", "후보가 아님", "아이 동반이 아님", "90분 이내", "영업시간 밖", "방금 객실에서 쉼", "지치지 않음")   # 화면에는 이 고객 · 이 순간에 의미 있는 제외 이유만


def _labels(*runs):
    """행동 코드 → 화면 이름(계획기 활동표 · 엔진 상품 이름 · 이미 실행된 기록)."""
    lab = {k: v[0] for k, v in AD.SP.ACT.items()}
    w = AD.World(AD.scenario("lab", levers={"WINE_FAIR": {"available": True}}))
    lab.update({o["id"]: o["label"] for o in w.engine_world(AD.hm("16:00"))["offers"]})
    for r in runs:
        for p in r.values():
            for x in p["log"]:
                lab.setdefault(x["act"], x["label"])
    return lab


def _rej(r):
    """제외 이유 문장에서 내부 코드 · 수치를 걷어 낸다."""
    if "→" in r and re.search(r"[A-Z]{3,}", r):
        return r.split("→")[0].strip().replace("(또는 퇴실 뒤)", " · 퇴실 뒤") + "에는 이용할 수 없음"
    return re.sub(r"\s*\((적합도|점수)[^)]*\)", "", r)


def _why_not(s):
    m = re.match(r"(.+?)에서 -?\d", s or "")
    return f"{m.group(1)} 면에서 덜 맞음" if m else "종합 판단에서 밀림"


def annotate(personas, lab):
    """각 행동에 '함께 검토한 다른 선택'과 '이 순간 막힌 선택'을 공개용 문장으로 붙인다(점수 · 내부 키 없이). 정량 엔진 · 계획기 결과는 바꾸지 않는다."""
    for p in personas.values():
        stay = p["visit"].get("stay")
        name = lambda c: ("따로 움직이지 않고 쉬기" if c == "ROOM_REST" and not stay else lab.get(c, c))
        for x in p["log"]:
            iv = x.get("internal") or {}
            alts = []
            if iv.get("alternatives"):
                alts = [dict(label=name(a["offer"]), note=_why_not(a.get("why_not"))) for a in iv["alternatives"][:3]]
            elif iv.get("weights"):
                alts = [dict(label=name(c), note="후보였지만 이번에는 덜 끌림") for c, _ in sorted(iv["weights"].items(), key=lambda kv: -kv[1]) if c != x["act"]][:3]
            blocked = [dict(label=name(c), note=_rej(r)) for c, r in (iv.get("rejected") or {}).items() if isinstance(r, str) and not any(n in r for n in NOISE_REJ)][:3]
            if alts or blocked:
                x["choice"] = dict(considered=alts, blocked=blocked)


WINDOW = {"wine_fair_1300": "15:30", "pool_check": "16:00", "pizzahill_full": "17:30"}   # 개입이 실제로 영향을 주는 시작 시각


def stories(base, chg, cmp, at, lab, iv_label, iv_id=None):
    """개입 전후 한 고객의 이야기 — 원래 계획 → 새 조건 → (부딪힘) → 검토한 대안 → 선택 · 이어서. 모두 같은 실행 기록에서 만든다."""
    T = AD.hm(at); out = {}
    for pid, c in cmp.items():
        b = [x for x in base[pid]["log"] if AD.hm(x["t"]) >= T and x["act"] not in ("move", "wait", "idle")]
        n = [x for x in chg[pid]["log"] if AD.hm(x["t"]) >= T and x["act"] not in ("move", "wait", "idle")]
        gone = {tuple(k) for k in c["cancelled"]}; new = {tuple(k) for k in c["new"]}
        before = [dict(t=x["t"], label=x["label"]) for x in b if (x["act"], x["loc"]) in gone][:3]
        mark = lambda x: str(x["act"]).endswith((":full", ":check"))
        seq = [x for x in n if x["source"] != "obligation" and (mark(x) or (x["act"], x["loc"]) in new)][:4]
        chosen = next((x for x in seq if not mark(x)), None)
        if c["cls"].startswith("새 행동 선택(행사"):
            chosen = next((x for x in n if x["act"] == "WINE_FAIR"), chosen)
        steps = []
        for x in seq:
            kind = "마감 확인" if str(x["act"]).endswith(":full") else "안내 확인" if str(x["act"]).endswith(":check") else ("선택" if x is chosen else "이어서")
            steps.append(dict(kind=kind, t=x["t"], label=x["label"], why=x["why"], evidence=x["evidence"] if x is chosen else [], charge=x.get("charge") if x is chosen else None))
            if x is chosen and c["cls"].startswith("새 행동 선택(행사"):
                break
        keep = None
        if c["cls"].startswith("원래"):
            lv = next((x for x in chg[pid]["log"] if x["act"] == "leave"), None)
            w = WINDOW.get(iv_id)
            if lv and w and AD.hm(lv["t"]) < AD.hm(w):
                keep = f"{lv['t']}에 일정을 마치고 귀가해, 개입이 영향을 주는 {w} 이후에는 현장에 없습니다."
            else:
                keep = c["reason"].replace("개입과 관련된 시설을 오늘 계획에서 쓰지 않음", "운영이 바뀐 시설을 오늘 계획에 넣지 않았기 때문에 일정이 그대로입니다.")
        out[pid] = dict(cls=c["cls"], before=before, notice=dict(t=at, text=iv_label), steps=steps,
                        considered=(chosen or {}).get("choice", {}).get("considered", []), blocked=(chosen or {}).get("choice", {}).get("blocked", []),
                        keep_reason=keep)
    return out


FORBIDDEN = re.compile(r"/private/|/Users/|/home/|\.local\.json|blog\.naver|review_text|source_gist")


def main():
    q = json.loads(sys.stdin.read() or "{}")
    if q.get("op") == "meta":
        print(json.dumps(dict(version=AD.VERSION, personas=AD.DEMO, interventions={k: v["label"] for k, v in INTERVENTIONS.items()}), ensure_ascii=False)); return
    ids = [p for p in (q.get("personas") or []) if p in AD.DEMO]
    bad = [p for p in (q.get("personas") or []) if p not in AD.DEMO]
    if bad or not ids:
        print(json.dumps({"error": "시연 고객 11명 안의 ID 만 실행합니다", "n_bad": len(bad)}, ensure_ascii=False)); return
    iv = q.get("intervention") or "none"
    if iv not in INTERVENTIONS:
        print(json.dumps({"error": "정해진 운영자 개입만 선택할 수 있습니다"}, ensure_ascii=False)); return
    seed = q.get("seed", 0)
    if not isinstance(seed, int) or isinstance(seed, bool) or not (0 <= seed <= 9999):
        print(json.dumps({"error": "seed 는 0~9999 정수"}, ensure_ascii=False)); return
    inp = AD.load_inputs()
    base = AD.scenario("base", seed=seed)
    sc = AD.scenario(iv, seed=seed, changes=INTERVENTIONS[iv]["changes"])
    mode = "many" if (q.get("mode") == "many" or len(ids) > 1) else "one"
    if mode == "one":
        r = AD.run_one(ids[0], sc, inp); out = dict(mode="one", personas={ids[0]: r}, notices=r["notices"], interaction=None)
    else:
        r = AD.run_many(ids, sc, inp); out = dict(mode="many", personas=r["personas"], notices=r["notices"], interaction=r["interaction"], copresence=r["copresence"])
    out["inputs_sha"] = hashlib.sha256(json.dumps({p: out["personas"][p]["log"] for p in out["personas"]}, sort_keys=True, ensure_ascii=False, default=list).encode()).hexdigest()   # 화면용 설명(choice · stories)을 붙이기 전 실행 기록 기준
    if q.get("compare") and iv != "none":
        b = AD.run_many(ids, base, inp)["personas"] if mode == "many" else {ids[0]: AD.run_one(ids[0], base, inp)}
        out["compare"] = AD.compare(b, out["personas"], INTERVENTIONS[iv]["at"], event=iv == "wine_fair_1300")
        lab = _labels(b, out["personas"]); annotate(b, lab); annotate(out["personas"], lab)
        out["baseline"] = {p: dict(log=b[p]["log"], summary=b[p]["summary"]) for p in b}
        out["stories"] = stories(b, out["personas"], out["compare"], INTERVENTIONS[iv]["at"], lab, INTERVENTIONS[iv]["label"], iv)
    else:
        annotate(out["personas"], _labels(out["personas"]))
    out["intervention"] = dict(id=iv, label=INTERVENTIONS[iv]["label"])
    out["engine"] = dict(version=AD.VERSION, llm_backend="rules(LLM 호출 0)", seed=seed)
    s = json.dumps(out, ensure_ascii=False, default=list)
    if FORBIDDEN.search(s):
        print(json.dumps({"error": "결과에 비공개 문자열이 있어 내보내지 않음"}, ensure_ascii=False)); return
    print(s)


if __name__ == "__main__":
    main()
