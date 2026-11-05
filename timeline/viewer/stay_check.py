"""연박 집계 점검 · 둘째 날 행동 · 좌석 공유 · 집계 단위 (10/16 · 실험 · 분석 전용, 모델 · 입력 · 화면 계산은 바꾸지 않음)

  python3 stay_check.py 2026-10-10 0            # stay_day.py 와 같은 이어 생성(워밍업 3일) + 손님별 기록 → cache/stay_check_<날짜>_<시드>.json

stay_day.py 의 계산을 그대로 따라가면서 두 가지를 더 남긴다.
  ① 손님별 식음 행동 기록(체류 전체) — 둘째 날 행동이 적게 나오는 원인을 '이용 가능한 손님 · 시간'을 맞춰 보기 위해
  ② 좌석 예약마다 '어느 날 생성된 손님인지' 표시 — 먼저 생성된 손님의 자리 차지가 뒤 손님의 선택(전환)에 실제로 영향을 주는지 보기 위해
결과 파일은 저장소 밖 캐시에만 둔다(손님별 기록 · 합성 손님이지만 크기가 커서). 요약은 근거사슬 7-27.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
import stay_day as S  # noqa: E402

E, G, revenue = S.E, S.G, S.revenue
MEALK = set(S.agent_v4.MEAL_KEYS) | {"pavilion", "lounge_t", "room"}


def run(target: str, seed: int, warm: int = 3):
    cap = S.Capacity()
    if "모에기" in cap.cap:
        cap.cap["모에기"] = int(E.V4.get("moegi_seats") or cap.cap["모에기"])
    cur = {"ix": None}
    tags = defaultdict(list)                       # 좌석 업장 → (시작, 끝, 인원, 생성일 ix)
    _book = cap.book

    def book(key, t_in, t_out, party):
        _book(key, t_in, t_out, party)
        v = cap.venue_of(key)
        if v:
            tags[v].append((t_in, t_out, party, cur["ix"]))
    cap.book = book
    catch = E.Catch()
    carry: dict = {}
    t_day = datetime.strptime(target, "%Y-%m-%d").date()
    guests = []
    for ix in range(-warm, 1):
        cur["ix"] = ix
        dt = datetime.strptime(target, "%Y-%m-%d") + timedelta(days=ix)
        day = dt.date().isoformat()
        th, cfg = S.setup_day(day, seed)
        grid, factors = G.load_grid(), G.load_factors()
        pmix = G.load_mix(S.TL / "purpose_mix.csv")
        amix = G.load_mix(S.TL / "age_mix.csv", key="연령")
        tmix = G.load_type_mix()
        cap.prune(dt)
        with contextlib.redirect_stdout(io.StringIO()):
            stays = G.guests_for(day, grid, factors, scale=1.0, purpose_mix=pmix, type_mix=tmix, carry=carry,
                                 day_parties=None, day_scenario="base", day_config=cfg, age_mix=amix)
        if th.get("order_mix"):
            stays = list(stays)
            random.Random(G.SEED + 7).shuffle(stays)
        nxt = Counter()
        for gid, _, m in stays:
            p = m.PERSONA
            lines = revenue.spend_lines(m, k=1, capacity=cap)
            segs, traces = catch.last
            det = E.detail_json(p, m.START_AT, segs, traces, lines)
            if p.is_guest and p.nights >= 2:
                nxt[p.property] += 1
            # 목표일 21:00 에 어디 있었나 (객실 · 업장 · 호텔 밖)
            at21 = None
            t21 = datetime.combine(t_day, datetime.min.time()).replace(hour=21)
            for sg in det["segments"]:
                if datetime.fromisoformat(sg["t_in"]) <= t21 < datetime.fromisoformat(sg["t_out"]):
                    at21 = sg["location"]
                    break
            acts = []
            for s in det["steps"]:
                if s.get("key") not in MEALK:
                    continue
                sw = s.get("switch") or {}
                acts.append(dict(d=s["t_in"][:10], t=s["t_in"][11:16], k=s["key"], v=s.get("venue") or s.get("location"), st=s.get("state"),
                                 sw=({k: sw.get(k) for k in ("원래", "원래_키", "사유", "시각")} if sw.get("원래") else None)))
            guests.append(dict(ix=ix, id=gid, guest=p.is_guest, nights=p.nights, party=p.party_size, kids=bool(p.has_child_under_13),
                               purpose=p.purpose, start=m.START_AT.isoformat(timespec="minutes"), at21=at21, acts=acts))
        carry = dict(nxt)
    booked = {v: [(a.isoformat(timespec="minutes"), b.isoformat(timespec="minutes"), n, g) for a, b, n, g in L if b.date() >= t_day - timedelta(days=1)]
              for v, L in tags.items()}
    return dict(date=target, seed=seed, warm=warm, model_ver=E._version.model_ver(), input_ver=E._version.input_ver(),
                cap=dict(cap.cap), guests=guests, booked=booked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("seed", type=int); ap.add_argument("--warm", type=int, default=3)
    a = ap.parse_args()
    r = run(a.date, a.seed, a.warm)
    out = HERE / "cache" / f"stay_check_{a.date}_{a.seed}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    print(out, len(r["guests"]))


if __name__ == "__main__":
    main()
