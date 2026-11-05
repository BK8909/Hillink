"""
식당 선택 기본값 만들기 — 슬기 blog_types.csv (목적 × 실제 간 식당) + 온톨로지 구성비 원장 → dining_pref.csv

  python3 dining_pref.py          # ../docs/blog_types.csv 와 ontology_dining.csv 를 읽어 dining_pref.csv · purpose_mix.csv · type_mix.csv 를 다시 쓴다

왜
  격자에서 뽑은 손님은 식사 때 열에 아홉이 "식당 외 식사" 를 골랐다 (후기 손님과 달리 포함 끼니 · 예약 · 성향이 없어서).
  목적별로 "가고 싶은 식당" 하나를 주면 그 자리가 채워진다. 그 분포가 이 파일이다.

어떻게
  후기 39편(슬기 분류 · 판단 유보 7편 제외)에서 목적별로 "식당=" 에 적힌 업장을 센다. 라운지 · 카페(코드 없음) · 없음은 뺀다.
  후기에 없는 목적(비즈니스 · 골프)과 표본이 적은 칸을 메우려고 온톨로지 "고객 구성비 원장" 에서 역산한 P(업장 | 목적) 을
  후기 3건어치(K=3) 사전으로 섞는다. 비중 = (후기 건수 + 3 × 온톨로지 비중) / 합.
  슬기 분류가 늘면 후기 쪽 무게가 저절로 커진다.
"""

from __future__ import annotations

import csv, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENUES = ["THE_BUFFET", "PIZZA_HILL", "GEUMRYONG", "MYONGWOLGWAN", "ONDAL", "MOEGI", "THE_PAVILION", "LE_PASSAGE", "LUX_BAR"]
PURPOSES = ["커플·기념일", "가족·친족", "비즈니스·접대", "친구·모임", "혼자 휴식", "휴식·산책 동행", "골프·스포츠 모임", "미식 방문"]
K = 3.0


def main(blog_path=None):
    blog_path = Path(blog_path) if blog_path else next(p for p in (HERE.parent / "docs" / "blog_types.csv", HERE / "blog_types.csv") if p.exists())
    blog = defaultdict(Counter)
    n_ok = 0
    for r in csv.DictReader(open(blog_path, encoding="utf-8-sig")):
        if not r["AI유형"]:
            continue
        n_ok += 1
        m = re.match(r"식당=([^;]+)", r["근거"])
        for v in (m.group(1).split(",") if m else []):
            v = re.sub(r"\(.*?\)", "", v).strip()
            if v in VENUES:
                blog[r["목적"]][v] += 1
    onto = defaultdict(dict)
    for r in csv.DictReader(open(HERE / "ontology_dining.csv", encoding="utf-8-sig")):
        onto[r["목적"]][r["업장"]] = float(r["비중"])
    rows = []
    for p in PURPOSES:
        w = {v: blog[p].get(v, 0) + K * onto[p].get(v, 0) for v in VENUES}
        tot = sum(w.values())
        for v in VENUES:
            if w[v] > 0:
                rows.append([p, v, blog[p].get(v, 0), onto[p].get(v, 0), round(w[v] / tot, 3)])
    with open(HERE / "dining_pref.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f); wr.writerow(["목적", "업장", f"후기 건수(슬기 {n_ok}편)", "온톨로지 비중", "비중"]); wr.writerows(rows)
    print(f"blog_types {blog_path} · 유효 {n_ok}편 → dining_pref.csv {len(rows)}줄")

    # ── 목적 분포 · 목적 → AI 유형 분포 (같은 39편에서) ──────────────────────────
    # 목적 분포: 후기 건수 + 10 × 온톨로지 "그랜드 판매 객실박" 목적 배분 (후기에 없는 비즈니스 · 골프를 온톨로지가 메운다)
    ONTO_PURPOSE = {"커플·기념일": .256, "가족·친족": .157, "비즈니스·접대": .177, "친구·모임": .118,
                    "혼자 휴식": .098, "휴식·산책 동행": .110, "골프·스포츠 모임": .044, "미식 방문": .039}
    pc = Counter(); tc = defaultdict(Counter)
    for r in csv.DictReader(open(blog_path, encoding="utf-8-sig")):
        if r["AI유형"]:
            pc[r["목적"]] += 1; tc[r["목적"]][r["AI유형"]] += 1
    KP = 10.0
    tot = sum(pc.get(p, 0) + KP * ONTO_PURPOSE[p] for p in PURPOSES)
    with open(HERE / "purpose_mix.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f); wr.writerow(["목적", f"후기 편수(슬기 {n_ok}편)", "온톨로지 배분", "비중"])
        for p in PURPOSES:
            wr.writerow([p, pc.get(p, 0), ONTO_PURPOSE[p], round((pc.get(p, 0) + KP * ONTO_PURPOSE[p]) / tot, 3)])
    # 유형 분포: 목적별 후기 유형 건수 + 1 × 전체 유형 분포 (표본 적은 목적용). 후기에 없는 목적은 전체 분포
    allt = Counter(); [allt.update(c) for c in tc.values()]
    tot_all = sum(allt.values())
    with open(HERE / "type_mix.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f); wr.writerow(["목적", "AI유형", "후기 건수", "비중"])
        for p in PURPOSES:
            w = {t: tc[p].get(t, 0) + 1.0 * allt[t] / tot_all for t in allt}
            s = sum(w.values())
            for t, v in sorted(w.items(), key=lambda kv: -kv[1]):
                wr.writerow([p, t, tc[p].get(t, 0), round(v / s, 3)])
    print("purpose_mix.csv · type_mix.csv 도 다시 썼다")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
