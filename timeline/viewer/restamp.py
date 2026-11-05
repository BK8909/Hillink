"""캐시 버전 다시 찍기 (10/14) — 코드를 고쳤지만 계산 결과는 그대로일 때 쓴다.

화면 · 설명용 코드(예: 손님 한 팀 출력에 성향 값 추가)만 바꿔도 engine.py 해시가 바뀌어 모든 캐시가 '예전 계산' 이 된다.
그때 전부 다시 돌리는 대신, 기준 날 하나를 새 코드로 다시 계산해 이전 결과와 숫자가 같은지 확인하고,
같을 때만 이전 버전 캐시의 model_ver 를 새 버전으로 바꾼다. 다르면 아무것도 바꾸지 않는다 (그때는 다시 돌려야 한다).

  python3 restamp.py --key 2026-10-10_none_s100_kbn0.16-...   # 확인할 기준 날 (지금 캐시에 있는 키)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
sys.path.insert(0, str(HERE))
import version  # noqa: E402

SKIP = {"built", "model_ver", "input_ver", "offsets"}   # offsets = guests.jsonl 안의 위치 (손님 상세 출력 모양이 바뀌면 달라진다 · 결과가 아님)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    a = ap.parse_args()
    f = CACHE / f"{a.key}.json"
    old = json.loads(f.read_text(encoding="utf-8"))
    old_ver, inp = old.get("model_ver"), old.get("input_ver")
    new_ver = version.model_ver()
    if inp != version.input_ver():
        sys.exit("입력 표 버전이 다릅니다 — 다시 찍을 수 없고 다시 계산해야 합니다")
    if old_ver == new_ver:
        sys.exit("이미 지금 버전입니다")
    sides = [f] + [CACHE / f"{a.key}{ext}" for ext in (".guests.jsonl", ".cap.pkl")]
    backups = [(g, g.with_name(g.name + ".restamp_bak")) for g in sides if g.exists()]
    for g, b in backups:
        shutil.copy(g, b)

    def restore():
        for g, b in backups:
            shutil.move(b, g)
    th = old["theta"]
    r = subprocess.run([sys.executable, str(HERE / "engine.py"), "day", "--date", old["date"], "--scenario", old["scenario"],
                        "--scale", str(old["scale"]), "--theta", json.dumps(th, ensure_ascii=False)], capture_output=True, text=True)
    if r.returncode:
        restore()
        sys.exit("다시 계산 실패:\n" + r.stderr[-2000:])
    new = json.loads(f.read_text(encoding="utf-8"))
    diff = sorted(k for k in set(old) | set(new) if k not in SKIP and old.get(k) != new.get(k))
    if diff:
        restore()
        sys.exit(f"결과가 다릅니다 ({', '.join(diff[:10])}) — 다시 찍지 않습니다. 다시 계산하세요")
    for g, b in backups:
        b.unlink()        # 새로 계산한 기준 날(손님 상세 · 좌석 포함)을 그대로 둔다
    n = 0
    for g in CACHE.glob("*.json"):
        if g.name.endswith("progress.json"):
            continue
        try:
            d = json.loads(g.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("model_ver") == old_ver and d.get("input_ver") == inp:
            d["model_ver"] = new_ver
            g.write_text(json.dumps(d, ensure_ascii=False, default=str), encoding="utf-8")
            n += 1
    print(f"기준 날 결과 같음 → {old_ver} → {new_ver} 로 {n}개 다시 찍음")


if __name__ == "__main__":
    main()
