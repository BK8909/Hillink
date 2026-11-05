"""
민감도 표 — 조정값을 하나씩 흔들어 어느 가정이 결과를 제일 움직이는지 (10/2)

왜
  하루 손님 생성기 뒤에 근거 없는 조정값이 열 개 가까이 있다 (가동률 · 비투숙 규모 · 선호 비율 · 메뉴 가중치 · 한정 객실 · 사전 예약 …).
  어느 것이 L1 을 크게 흔드는지 알아야 10/7 에 무엇을 먼저 물을지 정해진다. 대표님 온톨로지에도 같은 모양의 민감도 표가 있다.

어떻게
  기준(10/10 · 기본값)을 한 번 돌리고, 조정값을 하나씩 낮춤 / 높임으로 바꿔 다시 돌린다. generate.py 의 --set 과 기존 플래그를 쓴다.
  결과는 순매출(억) — L1 · ROOM · F&B · 레저 와 기준 대비 % . sensitivity.csv 에 쓰고 표로 찍는다.

  python3 sensitivity.py                 # 전부 (한 번에 2분 · 20번 안팎)
  python3 sensitivity.py --only 가동률    # 이름에 그 글자가 든 경우만
"""

from __future__ import annotations

import argparse, csv, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATE = "2026-10-10"

# (이름, 방향, 추가 인자)
CASES = [
    ("기준", "", []),
    ("가동률 OCC_BASE 0.79", "낮춤 0.60", ["--set", "generate.OCC_BASE=0.60"]),
    ("가동률 OCC_BASE 0.79", "높임 0.96", ["--set", "generate.OCC_BASE=0.96"]),
    ("비투숙 규모 311팀", "낮춤 156", ["--day-scenario", "low"]),
    ("비투숙 규모 311팀", "높임 622", ["--day-scenario", "high"]),
    ("좌석 점유율 1.0", "낮춤 0.55", ["--occupancy", "0.55"]),
    ("좌석 상한", "끔", ["--no-cap"]),
    ("식당 선호 비율 0.7", "낮춤 0.35", ["--prefer", "0.35"]),
    ("식당 선호 비율 0.7", "높임 1.0", ["--prefer", "1.0"]),
    ("원장 상품 가중 W_LEDGER 3", "낮춤 1", ["--set", "menu.W_LEDGER=1"]),
    ("원장 상품 가중 W_LEDGER 3", "높임 6", ["--set", "menu.W_LEDGER=6"]),
    ("한정 객실 W_LIMITED 0.1", "낮춤 0", ["--set", "menu.W_LIMITED=0"]),
    ("한정 객실 W_LIMITED 0.1", "높임 1", ["--set", "menu.W_LIMITED=1"]),
    ("사전 예약 W_RESERVE 0.2", "낮춤 0", ["--set", "menu.W_RESERVE=0"]),
    ("사전 예약 W_RESERVE 0.2", "높임 1", ["--set", "menu.W_RESERVE=1"]),
    ("목적 분포 (purpose_mix)", "격자 그대로", ["--grid-purpose"]),
    ("연령 분포 (age_mix 25/50/25)", "격자 그대로", ["--grid-age"]),
    ("메뉴 선택 층", "끔 (업장당 값 하나)", ["--no-menu"]),
]

L2_RE = re.compile(r"L2 (ROOM|F&B|레저)\s+([\d,]+)원\s+\(순매출\s+([\d,]+)\)")
L1_RE = re.compile(r"L1 전체\s+결제액 ([\d,]+)원 · 순매출 ([\d,]+)원")
L3_RE = re.compile(r"^  (더뷔페|그랜드|비스타|피자힐|명월관|금룡|더글라스|온달|모에기|파빌리온)\s+([\d,]+)\s+(\d+)\s+([\d,]+)$")


def run(extra):
    out = subprocess.run([sys.executable, str(HERE / "generate.py"), "--date", DATE, *extra],
                         capture_output=True, text=True, timeout=900).stdout
    r = dict(l1=0.0, ROOM=0.0, **{"F&B": 0.0, "레저": 0.0})
    for line in out.splitlines():
        m = L1_RE.search(line)
        if m:
            r["l1"] = int(m.group(2).replace(",", "")) / 1e8
        m = L2_RE.search(line)
        if m:
            r[m.group(1)] = int(m.group(3).replace(",", "")) / 1e8
        m = L3_RE.match(line)
        if m:
            r["l3:" + m.group(1)] = int(m.group(2).replace(",", "")) / 1.1 / 1e8
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    rows = []
    base = None
    for name, how, extra in CASES:
        if a.only and a.only not in name and name != "기준":
            continue
        r = run(extra)
        if name == "기준":
            base = r
        rows.append((name, how, r))
        d = f"{(r['l1'] / base['l1'] - 1) * 100:+.1f}%" if base and base["l1"] else ""
        print(f"{name:28s} {how:14s} L1 {r['l1']:6.2f}억 ({d:>7s})  ROOM {r['ROOM']:5.2f}  F&B {r['F&B']:5.2f}  레저 {r['레저']:4.2f}", flush=True)

    with (HERE / "sensitivity.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        venues = ["더뷔페", "그랜드", "비스타", "피자힐", "명월관", "금룡", "더글라스", "온달", "모에기", "파빌리온"]
        w.writerow(["조정값", "방향", "L1 순매출(억)", "기준 대비 %", "ROOM", "F&B", "레저"] + venues)
        for name, how, r in rows:
            pct = (r["l1"] / base["l1"] - 1) * 100 if base and base["l1"] else 0
            w.writerow([name, how, f"{r['l1']:.2f}", f"{pct:+.1f}", f"{r['ROOM']:.2f}", f"{r['F&B']:.2f}", f"{r['레저']:.2f}"]
                       + [f"{r.get('l3:' + v, 0):.2f}" for v in venues])
    # 흔든 폭 순위 — 낮춤 · 높임 중 큰 쪽
    span = {}
    for name, how, r in rows:
        if name == "기준":
            continue
        pct = abs(r["l1"] / base["l1"] - 1) * 100
        span[name] = max(span.get(name, 0), pct)
    print("\n흔든 폭 순위 (L1 기준 대비 |%| 최대)")
    for name, v in sorted(span.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5.1f}%  {name}")


if __name__ == "__main__":
    main()
