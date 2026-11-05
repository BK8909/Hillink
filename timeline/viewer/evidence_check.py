"""근거 완전성 검사 (10/16 · 작업배정 1016 항목 5 · 근거사슬 7-25)

  python3 evidence_check.py      # → static/evidence_check.json · 화면 판단 근거 ⑦ '근거 완전성 검사' 가 읽음

지금 기본 모델(v4.1)이 실제로 쓰는 입력(조정값 · 행동 점수 계수 · 손님 생성 상수 · 입력 표)을 목록으로 만들고,
입력 출처표(input_provenance.csv) · 가설표(hypotheses.csv) · 근거 사슬표(docs/evidence_chain_20261010.csv)와 이어지는지 본다.
단순히 번호가 있는지가 아니라 다섯 가지를 나눠 보고한다.
  누락        지금 쓰는 입력인데 출처표에 줄이 없음 (가설표에만 있으면 '부분')
  참조 오류   출처표가 가리키는 파일 · 이름이 없거나, 적힌 값이 지금 코드 값과 다름
  버전 불일치 화면이 읽는 결과 파일 · 하루 계산이 지금 모델 · 입력 버전과 다름
  근거 혼용   등급은 외부 근거(◎ · ○)인데 출처가 '맞춘 값 · 역산 · 가정' — 외부 근거와 모델 가정이 한 줄에 섞임
  표기 차이   화면 문구와 원천 표의 상태가 다름 (예: H4b)
  보류        결정에 따라 다음 입력 버전 갱신 때 고칠 항목 (10/16 · H4b 원천 가설표 — 입력 버전에 들어가 있어 지금 고치면 하루 계산이 모두 예전 기준이 됨)
그리고 입력마다 근거 종류를 외부 근거 · 맞춤값(평가 대상과 같은 자료로 맞춤) · 가정 · 근거 없음으로 나눈다.
10/16 집계를 두 기준으로 나눈다 — 고유 입력 기준(kinds_unique · 합 = 입력 수)과 근거 연결 기준(kinds_links · 혼합 입력은 줄마다).
출처표 비고에 '출처표 보완' 이 있는 줄은 그날 누락을 메운 줄이다 (filled) — 누락 해소이지 외부 검증이 아니다.
모델 코드 · 입력 표는 바꾸지 않는다(읽기만).
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
ROOT = TL.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(TL))
with contextlib.redirect_stdout(io.StringIO()):
    import agent_v4, engine, generate as G, version  # noqa: E402

OUT = HERE / "static" / "evidence_check.json"
FIT_WORDS = re.compile(r"맞춘|맞춤|역산|대조로 맞|교차검증")
ASSUME_WORDS = re.compile(r"임시|가정(?!표)|추정|자리표")


def nums(s):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(s).replace(",", ""))]


def close(v, s):
    """값 v 가 문자열 s 의 숫자 중 하나와 같은가 (비율 ↔ % · 반올림 허용)"""
    if isinstance(v, bool) or v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return None
    for x in nums(s):
        for c in (x, x / 100):
            if abs(c - v) <= max(0.011, abs(v) * 0.011):
                return True
    return False


OFFICIAL = re.compile(r"공식|정부|공개|보도자료|현장|메뉴판|홈페이지")


def kind_of(row):
    """맞춤값 > 참조 모델 값 > 외부 근거 > 가정 순으로 판정 (한 줄에 여러 근거가 있으면 가장 독립성이 낮은 쪽을 앞에)"""
    g, src = row["등급"], row["출처"] + " " + row["표본 · 근거"]
    if FIT_WORDS.search(src):
        return "맞춤값"
    if "온톨로지" in row["출처"]:
        return "참조 모델 값"
    if g.startswith("◎") or OFFICIAL.search(row["출처"]):
        return "외부 근거"
    return "가정"


def main():
    PV = list(csv.DictReader(open(TL / "input_provenance.csv", encoding="utf-8-sig")))
    HY = list(csv.DictReader(open(TL / "hypotheses.csv", encoding="utf-8-sig")))
    CH = list(csv.DictReader(open(ROOT / "docs" / "evidence_chain_20261010.csv", encoding="utf-8-sig")))
    pv_text = lambda r: " ".join(r.values())
    issues = []

    def issue(cat, target, detail, fix):
        issues.append(dict(cat=cat, target=target, detail=detail, fix=fix))

    # ── 지금 쓰는 입력 목록
    inv = []
    for k, v in engine.V4.items():
        inv.append(dict(id=f"조정값 {k}", name=(engine.KNOBS.get(k) or (k,))[0], value=v, keys=[k], group="v4.1 조정값"))
    for k, v in agent_v4.THETA_FIT.items():
        inv.append(dict(id=f"계수 {k}", name=f"행동 점수 계수 {k}", value=round(v, 3) if isinstance(v, float) else v, keys=[k, "THETA_FIT"], group="행동 점수 계수"))
    for k in ("OCC_BASE", "P_PREFER_GUEST", "P_PREFER_DAY", "DAY_ARRIVE", "WAKE_SPREAD", "DAY_SCALE", "BREAKFAST_PKG"):
        v = getattr(G, k)
        inv.append(dict(id=f"generate.{k}", name=k, value=v if isinstance(v, (int, float)) else str(v)[:60], keys=[k], group="손님 생성 상수"))
    inv.append(dict(id="agent_v4.MIN_DWELL", name="붐빌 때 최소 체류", value=str(agent_v4.MIN_DWELL)[:60], keys=["MIN_DWELL", "체류 단축"], group="행동 규칙 상수"))
    for k, nm in (("SEATS", "업장 좌석 · 회차 (prices.SEATS)"), ("ROOMS", "객실 수 (prices.ROOMS)")):
        inv.append(dict(id=f"prices.{k}", name=nm, value=None, keys=[f"prices.{k}"], group="운영 조건 표"))
    for f in ("place_assumptions.csv", "program_capacity.csv"):
        inv.append(dict(id=f, name=f, value=None, keys=[f], group="운영 조건 표"))
    for f in version.INPUT_FILES:
        inv.append(dict(id=f, name=Path(f).name, value=None, keys=[Path(f).name, Path(f).stem], group="입력 표"))

    # ── 연결 찾기
    for it in inv:
        rows = []
        for r in PV:
            place = r["파일 · 자리"] + " " + r["입력"]
            label = it["name"] if it["group"] == "v4.1 조정값" else None
            hit = any(re.search(r"(?<![A-Za-z_])" + re.escape(k) + r"(?![A-Za-z_])", place if not re.fullmatch(r"[A-Z_]{4,}", k) else pv_text(r)) for k in it["keys"] if k != "THETA_FIT")
            if not hit and "THETA_FIT" in it["keys"] and "THETA_FIT" in place:
                hit = "group"
            if not hit and label:
                head = label.split(" (")[0].split(" · ")[0]
                if len(head) > 3 and head in place:
                    hit = "label"
            if hit:
                rows.append((r, hit))
        hy = [h for h in HY if any(re.search(r"(?<![A-Za-z_])" + re.escape(k) + r"(?![A-Za-z_])", pv_text(h)) for k in it["keys"] if k != "THETA_FIT")]
        ch = [c for c in CH if any(k in pv_text(c) for k in it["keys"] if len(k) > 4 and k != "THETA_FIT")]
        it["provenance"] = [r["입력"] for r, _ in rows]
        it["hypotheses"] = [(re.search(r"\((H[0-9a-z]+)\)", h["이름"]) or re.search(r"(.*)", "가설 " + str(h["ID"]))).group(1) for h in hy]
        it["chain"] = [c["근거ID"] for c in ch]
        if rows:
            r, how = rows[0]
            ks = list(dict.fromkeys(kind_of(x) for x, _ in rows)) if it["group"] in ("입력 표", "운영 조건 표") else [kind_of(r)]
            it["grade"] = r["등급"]; it["kind"] = ks[0] if len(ks) == 1 else "혼합 (" + " · ".join(ks) + ")"; it["kinds"] = ks; it["source"] = r["출처"][:120]
            it["link"] = "묶음 줄" if how == "group" else "이름 표기 없이 이름표로" if how == "label" else "있음"
            # 값 확인 — 출처표 '지금 값' 에 지금 코드 값이 보이는가 (묶음 줄은 표기된 계수만)
            switch = it["group"] == "v4.1 조정값" and (engine.KNOBS.get(it["keys"][0]) or (None, None))[1] == 0      # 켬 · 끔 조정값 (값 1 · 2 는 방식 번호)
            ok = None if (switch or isinstance(it["value"], str)) else (close(it["value"], r["지금 값"]) or close(it["value"], r["출처"]))
            if switch:
                it["link"] += " · 켬/끔 조정값"
            if how == "group":
                key = it["keys"][0]
                m = re.search(re.escape(key) + r"\s*([0-9.]+)", r["지금 값"])
                ok = None if not m else abs(float(m.group(1)) - float(it["value"])) <= max(0.011, abs(float(it["value"])) * 0.02)
                if not m:
                    it["link"] = "묶음 줄 (값 미표기)"
            it["value_ok"] = ok
            if ok is False:
                issue("참조 오류", it["id"], f"출처표 '{r['입력']}' 의 지금 값 '{r['지금 값'][:60]}' 에 코드 값 {it['value']} 이 보이지 않음", "출처표의 지금 값을 코드 값으로 고치거나, 다른 값을 가리키는 이유를 비고에")
        else:
            it["grade"] = None; it["kind"] = "근거 없음" if not hy else "가설표에만"; it["link"] = "없음"; it["value_ok"] = None; it["source"] = ""
            if it["id"] in ("조정값 rng_team",):
                it["kind"] = "계산 방식 (근거 대상 아님)"; continue
            if it["group"] == "입력 표" and it["name"] in ("hypotheses.csv", "anomaly_scenarios.csv", "trend_signals.csv"):
                it["kind"] = "장부 · 시나리오 표"; continue
            if it["value"] in (0, None) and it["group"] != "입력 표":
                it["kind"] = "꺼짐 (값 0)"; continue
            issue("누락" if not hy else "누락 (부분)", it["id"],
                  f"지금 기본 모델이 쓰는 {it['group']} '{it['name']}'" + ("" if it["value"] is None else f" = {it['value']}") + " 에 출처표 줄이 없음" + (f" · 가설표 {', '.join(it['hypotheses'])} 에만 근거" if hy else ""),
                  "출처표에 줄 추가 (값 · 등급 · 출처 · 표본)" if not hy else "가설표 근거를 출처표 줄로 옮겨 적기")

    for it in inv:       # 값이 0 인 계수 · 조정값은 꺼진 것
        if it["group"] in ("행동 점수 계수",) and it["value"] in (0, 0.0):
            it["kind"] = "꺼짐 (값 0)"

    # ── 출처표가 가리키는 파일 · 이름이 실제로 있는가
    srcfiles = {p.name: p for p in list(TL.glob("*.py")) + list(TL.glob("*.csv")) + list(TL.glob("*.json")) + list(HERE.glob("*.py"))}
    for r in PV:
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*\.(?:csv|json|py)", r["파일 · 자리"]):
            if tok not in srcfiles:
                issue("참조 오류", r["입력"], f"출처표가 가리키는 파일 '{tok}' 이 없음", "파일 이름 확인")
        for mod, name in re.findall(r"\b(generate|prices|agent_v4|menu|revenue)\.([A-Za-z_][A-Za-z0-9_]*)", r["파일 · 자리"]):
            f = TL / f"{mod}.py"
            if f.exists() and not re.search(r"\b" + re.escape(name) + r"\b", f.read_text(encoding="utf-8")):
                issue("참조 오류", r["입력"], f"'{mod}.{name}' 이 {mod}.py 에 없음", "이름 확인")
        for k in re.findall(r"조정값\s+([a-z_]+)", r["파일 · 자리"]):
            if k not in engine.KNOBS:
                issue("참조 오류", r["입력"], f"조정값 '{k}' 이 엔진 조정값 목록에 없음", "이름 확인")
        # 근거 혼용 — 등급은 외부 근거인데 출처가 맞춘 값 · 역산 · 가정
        g = r["등급"]
        if (g.startswith("◎") or g.startswith("○")) and "/" not in g and "~" not in g and (FIT_WORDS.search(r["출처"] + r["표본 · 근거"]) or ASSUME_WORDS.search(r["출처"])):
            issue("근거 혼용", r["입력"], f"등급 {g} 인데 출처 · 표본에 '{(FIT_WORDS.search(r['출처'] + r['표본 · 근거']) or ASSUME_WORDS.search(r['출처'])).group(0)}' — 외부 근거와 모델에 맞춘 값 · 가정이 한 줄에 섞임",
                  "등급을 '○/△' 처럼 나누거나 '맞춤값' 으로 표기 · 평가 대상과 같은 자료로 맞춘 값이면 독립 근거가 아님을 적기")

    # ── 가설표 · 화면 표기
    for h in HY:
        op, gr = h.get("운영 표시", ""), h.get("등급", "")
        if op == "모델 기본값 반영" and gr.startswith("△"):
            # 10/16 결정 — H4b 는 화면 · 출처표에서 '모델 가정 △' 로 표시하고, 원천 가설표(입력 버전에 들어감)는 다음 입력 표 변경 때 고친다
            held = "H4b" in h["이름"]
            issue("보류 · 다음 입력 버전" if held else "근거 혼용", f"가설 {h['이름'][:30]}", f"운영 표시 '모델 기본값 반영' · 등급 {gr[:30]} — 가정(△)이 기본 모델에 들어가 있음",
                  "화면 · 문서에서 '외부 근거로 유지하는 모델 가정' 처럼 가정임을 함께 표기")
    h4b = next((h for h in HY if "H4b" in h["이름"]), None)
    if h4b:
        issue("보류 · 다음 입력 버전", "가설 H4b (평일 비투숙 0.5) · 표기",
              f"원천 가설표: 상태 '{h4b['상태'][:40]}…' · 운영 표시 '{h4b['운영 표시']}'. 화면(운영 요약 · 10/16 v1.53): '가설 H4b · 외부 근거로 유지하는 모델 가정 · 범위 0.4~0.7'. 화면 문구는 원천의 '10/14 채택 (v4 기본)' 과 등급 '△' 를 함께 읽어 '기본값에 넣은 가정' 으로 해석한 것",
              "가설표 csv 는 입력 버전(input_ver)에 들어가 있어 고치면 하루 계산 캐시를 다시 찍어야 함(restamp · 결과는 같음). 다음 입력 표 변경 때 운영 표시 열을 '모델 가정 (외부 근거로 유지)' 로 함께 바꾸기")

    # ── 버전
    cur = dict(model_ver=version.model_ver(), input_ver=version.input_ver())
    files = []
    for f in sorted((HERE / "static").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if f.name in ("evidence_check.json",) or f.name.startswith("llm_cases"):
            continue
        if isinstance(d, dict) and d.get("model_ver"):
            ok = d["model_ver"] == cur["model_ver"]
            files.append(dict(file=f.name, model_ver=d["model_ver"], ok=ok))
            if not ok:
                issue("버전 불일치", f"static/{f.name}", f"결과 파일의 model_ver {d['model_ver']} ≠ 지금 {cur['model_ver']}", "그 스크립트를 다시 돌리기")
    days = dict(total=0, current=0, old=0)
    for f in (HERE / "cache").glob("*.json"):
        if f.name.endswith(".progress.json") or f.name.startswith("band_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or "model_ver" not in d:
            continue
        days["total"] += 1
        if d.get("model_ver") == cur["model_ver"] and d.get("input_ver") == cur["input_ver"]:
            days["current"] += 1
        else:
            days["old"] += 1
    if days["old"]:
        issue("버전 불일치 (정보)", "하루 계산 캐시", f"하루 계산 {days['total']}개 중 {days['old']}개가 예전 버전 — 화면은 '예전 기준' 으로 표시하고 비교 · 요약 · 어시스턴트는 지금 버전만 읽음", "필요한 날만 다시 계산 (지우지 않음)")

    # ── 요약
    from collections import Counter
    # 10/16 집계 기준 두 가지 — 고유 입력 기준(입력 하나에 종류 하나 · 합 = 입력 수)과 근거 연결 기준(출처표 줄마다 · 한 입력에 여러 줄이면 겹쳐 셈)
    #   kinds_unique: 혼합 · 꺼짐 · 장부 · 계산 방식도 그대로 한 칸 → 합이 입력 수와 같다
    #   kinds (= kinds_links): 혼합 입력은 줄마다, 꺼진 계수(값 0)는 출처표 묶음 줄의 종류로 셈 → 합이 입력 수보다 클 수 있다
    for it in inv:
        prow = next((r for r in PV if r["입력"] in (it.get("provenance") or [])[:1]), None)
        it["filled"] = bool(prow and "출처표 보완" in prow.get("비고", ""))
    kinds = Counter(k for it in inv for k in (it.get("kinds") or [it["kind"]]))
    kinds_unique = Counter(it["kind"] for it in inv)
    cats = Counter(i["cat"] for i in issues)
    filled = [it["id"] for it in inv if it.get("filled")]
    res = dict(built=datetime.now().strftime("%Y-%m-%d %H:%M"), **cur, inventory=inv, issues=issues, kinds=dict(kinds), kinds_links=dict(kinds),
               kinds_unique=dict(kinds_unique), n_inputs=len(inv), n_links=sum(kinds.values()), filled=filled,
               count_rule="고유 입력 기준: 입력 하나에 근거 종류 하나 (출처표 줄이 여럿이면 '혼합', 값이 0 인 계수는 '꺼짐') · 합 = 입력 수. "
                          "근거 연결 기준: 입력과 이어진 출처표 줄의 근거 종류를 모두 셈 (혼합 입력은 두 번, 꺼진 계수는 출처표 묶음 줄의 종류로) · 합이 입력 수보다 클 수 있음. "
                          "'출처표 보완' 은 누락이 해소됐다는 뜻이고 근거 수준이 올라갔다는 뜻이 아님",
               cats=dict(cats),
               days=days, files=files, where="이 검사를 돌린 컴퓨터의 캐시 · 결과 파일 기준",
               rule="근거 종류: 외부 근거(공식 · 공개 자료 · 현장) · 맞춤값(평가하거나 비교하는 대상과 같은 자료 — 온톨로지 · 후기 46편 — 로 맞춘 값, 독립 근거 아님) · 가정(임시 · 추정) · 근거 없음. 출처표 한 줄을 기준으로 나누며, '○/△' 처럼 나뉜 줄은 앞쪽 근거를 따름.")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("입력", len(inv), "고유 입력 기준", dict(kinds_unique)); print("근거 연결 기준", sum(kinds.values()), dict(kinds)); print("출처표 보완", len(filled), filled); print("문제", dict(cats))
    for i in issues:
        print(f"[{i['cat']}] {i['target']} — {i['detail'][:150]}")


if __name__ == "__main__":
    main()
