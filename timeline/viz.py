"""
타임라인 검증 결과를 그림으로 본다.

  cd timeline && python3 viz.py

timeline_viz.html 을 만든다. 브라우저에서 더블클릭해 열면 된다.
설치 필요 없음 — 파이썬 표준 라이브러리만 쓴다.

가로축은 시각, 가로 줄 하나가 장소 하나다.
막대는 그 장소에 머문 구간이고, 색은 어느 상태기계에 속하는지다.
막대 뒤 옅은 띠는 그 업장의 운영 창이다.
빨간 표시가 불변식 위반이다.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timedelta

from walkerhill_timeline_validator import (
    WALKERHILL_VENUE_WINDOWS,
    TimelineSegment,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)

# ── 색 ──────────────────────────────────────────────────────────────────
# dataviz 기준 팔레트. 카테고리 세 칸만 쓴다 (전 쌍 검증 통과).
MACHINE_COLOR = {
    "M2_Stay":           ("--series-1", "투숙"),
    "M7_Outlet":         ("--series-2", "업장 · 시설"),
    "M5_Transport":      ("--series-3", "이동 수단"),
}
DEFAULT_SLOT = ("--series-1", "기타")

LANE_H = 36
BAR_H = 20
GUTTER = 190
RIGHT = 24
TOP = 46
BOTTOM = 34


def machine_slot(m: str):
    return MACHINE_COLOR.get(m, DEFAULT_SLOT)


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def build_chart(segments: list[TimelineSegment], report) -> str:
    if not segments:
        return "<p>구간 없음</p>"

    ordered = sorted(segments, key=lambda s: s.t_in)
    t0 = min(s.t_in for s in ordered)
    t1 = max(s.t_out for s in ordered)
    span = max((t1 - t0).total_seconds() / 60, 60)

    lanes: list[str] = []
    for s in ordered:
        if s.location not in lanes:
            lanes.append(s.location)

    width = 1120
    plot_w = width - GUTTER - RIGHT
    height = TOP + len(lanes) * LANE_H + BOTTOM

    def x(t: datetime) -> float:
        return GUTTER + (t - t0).total_seconds() / 60 / span * plot_w

    def lane_y(loc: str) -> float:
        return TOP + lanes.index(loc) * LANE_H

    out: list[str] = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="타임라인 정합성 검증 결과">'
    ]

    # ── 시각 눈금 ──────────────────────────────────────────────────────
    tick = t0.replace(minute=0, second=0, microsecond=0)
    if tick < t0:
        tick += timedelta(hours=1)
    step = 1 if span <= 14 * 60 else (2 if span <= 28 * 60 else 4)
    while tick <= t1:
        if tick.hour % step == 0:
            tx = x(tick)
            midnight = tick.hour == 0
            out.append(
                f'<line class="grid{" day" if midnight else ""}" x1="{tx:.1f}" y1="{TOP - 10}" '
                f'x2="{tx:.1f}" y2="{height - BOTTOM + 6}"/>'
            )
            label = f"{tick:%m/%d}" if midnight else f"{tick.hour:02d}시"
            out.append(
                f'<text class="tick" x="{tx:.1f}" y="{TOP - 16}" text-anchor="middle">{label}</text>'
            )
        tick += timedelta(hours=1)

    # ── 장소 줄 ────────────────────────────────────────────────────────
    for loc in lanes:
        ly = lane_y(loc)
        out.append(
            f'<line class="lane" x1="{GUTTER}" y1="{ly + LANE_H / 2:.1f}" '
            f'x2="{width - RIGHT}" y2="{ly + LANE_H / 2:.1f}"/>'
        )
        out.append(
            f'<text class="lane-label" x="{GUTTER - 12}" y="{ly + LANE_H / 2 + 4:.1f}" '
            f'text-anchor="end">{esc(loc)}</text>'
        )

    # ── 운영 창 (막대 뒤) ──────────────────────────────────────────────
    venue_by_lane: dict[str, str] = {}
    for s in ordered:
        if s.venue:
            venue_by_lane[s.location] = s.venue

    for loc, venue in venue_by_lane.items():
        ly = lane_y(loc) + (LANE_H - BAR_H) / 2
        for day_off in range(0, (t1.date() - t0.date()).days + 1):
            day = t0.date() + timedelta(days=day_off)
            for w in WALKERHILL_VENUE_WINDOWS.get(venue, ()):  # noqa
                if not w.opens_on(day):      # 10/5 소연 — 그 날 안 여는 창(요일 · 공휴일 · 기간 · 연도)은 안 그린다
                    continue
                a = datetime.combine(day, w.open_at)
                b = datetime.combine(day, w.close_at)
                if b < t0 or a > t1:
                    continue
                a, b = max(a, t0), min(b, t1)
                out.append(
                    f'<rect class="window" x="{x(a):.1f}" y="{ly - 3:.1f}" '
                    f'width="{max(x(b) - x(a), 1):.1f}" height="{BAR_H + 6}" rx="3">'
                    f'<title>{esc(venue)} 운영 {w.open_at:%H:%M}–{w.close_at:%H:%M}</title></rect>'
                )

    # ── 이동 연결선 ────────────────────────────────────────────────────
    for prev, cur in zip(ordered, ordered[1:]):
        if prev.location == cur.location:
            continue
        x1, y1 = x(prev.t_out), lane_y(prev.location) + LANE_H / 2
        x2, y2 = x(cur.t_in), lane_y(cur.location) + LANE_H / 2
        try:
            need = walkerhill_travel_time_min(prev.location, cur.location, prev.t_out)
            tip = f"{prev.location} → {cur.location} · 필요 {need:.0f}분"
        except Exception:
            tip = f"{prev.location} → {cur.location} · 이동 시간 없음"
        out.append(
            f'<path class="move" d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}">'
            f'<title>{esc(tip)}</title></path>'
        )

    # ── 세그먼트 막대 ──────────────────────────────────────────────────
    # 같은 줄에서 다음 막대가 시작하는 지점을 미리 구해 둔다.
    # 라벨이 겹치면 지운다. 지워도 되는 이유는 표 보기가 같이 있기 때문이다.
    next_start: dict[int, float] = {}
    by_lane: dict[str, list[int]] = {}
    for idx, seg in enumerate(ordered):
        by_lane.setdefault(seg.location, []).append(idx)
    for idxs in by_lane.values():
        for a, b in zip(idxs, idxs[1:]):
            next_start[a] = x(ordered[b].t_in)

    for i, s in enumerate(ordered):
        slot, _ = machine_slot(s.machine)
        bx, bw = x(s.t_in), max(x(s.t_out) - x(s.t_in), 3)
        by = lane_y(s.location) + (LANE_H - BAR_H) / 2
        dwell = (s.t_out - s.t_in).total_seconds() / 60
        tip = (f"{s.state}\\n{s.location}"
               f"\\n{s.t_in:%m/%d %H:%M} – {s.t_out:%H:%M} · {dwell:.0f}분"
               + (f"\\n운영 창 검사: {s.venue}" if s.venue else "\\n운영 창 검사 없음"))
        out.append(
            f'<rect class="bar" data-tip="{esc(tip)}" x="{bx:.1f}" y="{by:.1f}" '
            f'width="{bw:.1f}" height="{BAR_H}" rx="4" '
            f'fill="var({slot})"><title>{esc(tip)}</title></rect>'
        )
        # 직접 라벨 — 라이트 모드 대비가 낮은 칸이 있어 색만으로 두지 않는다.
        # 다만 겹칠 자리에는 넣지 않는다. 겹쳐 쓴 글자는 안 쓴 것만 못하다.
        label = s.state
        need = len(label) * 6.4 + 10
        if bw > need + 8:
            out.append(
                f'<text class="bar-label inside" x="{bx + 8:.1f}" y="{by + BAR_H / 2 + 4:.1f}">'
                f'{esc(label)}</text>'
            )
        else:
            room = next_start.get(i, width - RIGHT) - (bx + bw) - 8
            if room >= need:
                out.append(
                    f'<text class="bar-label outside" x="{bx + bw + 6:.1f}" '
                    f'y="{by + BAR_H / 2 + 4:.1f}">{esc(label)}</text>'
                )

    # ── 위반 표시 ──────────────────────────────────────────────────────
    for v in report.violations:
        vx = x(v.at)
        out.append(
            f'<line class="viol-line" x1="{vx:.1f}" y1="{TOP - 6}" '
            f'x2="{vx:.1f}" y2="{height - BOTTOM + 2}"/>'
        )
        out.append(
            f'<path class="viol-mark" d="M{vx - 6:.1f},{TOP - 10} L{vx + 6:.1f},{TOP - 10} '
            f'L{vx:.1f},{TOP - 1} Z"><title>{esc(v.invariant + " " + v.code)}</title></path>'
        )

    out.append("</svg>")
    return "".join(out)


def build_table(segments: list[TimelineSegment]) -> str:
    rows = []
    for s in sorted(segments, key=lambda s: s.t_in):
        dwell = (s.t_out - s.t_in).total_seconds() / 60
        _, group = machine_slot(s.machine)
        rows.append(
            f"<tr><td>{s.t_in:%m/%d %H:%M}</td><td>{s.t_out:%H:%M}</td>"
            f"<td class='num'>{dwell:.0f}</td><td>{esc(s.state)}</td>"
            f"<td>{esc(s.location)}</td><td>{esc(s.venue or '—')}</td>"
            f"<td>{esc(group)}</td></tr>"
        )
    return (
        "<table><thead><tr><th>들어간 시각</th><th>나온 시각</th><th>체류(분)</th>"
        "<th>상태</th><th>위치</th><th>운영 창 검사</th><th>분류</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def build_section(title: str, note: str, segments, nights=1) -> str:
    report = validate_walkerhill_timeline(segments, nights=nights)
    ok = report.ok
    share = (report.total_travel_min / report.stay_day_span_min * 100
             if report.stay_day_span_min else 0)

    viol = ""
    if report.violations:
        items = "".join(
            f"<li><span class='code'>{esc(v.invariant)} {esc(v.code)}</span>"
            f"<span class='when'>{v.at:%m/%d %H:%M}</span>"
            f"<span class='what'>{esc(v.detail)}</span></li>"
            for v in report.violations
        )
        viol = f"<ul class='violations'>{items}</ul>"

    badge = ("<span class='badge pass'>통과</span>" if ok
             else f"<span class='badge fail'>위반 {len(report.violations)}건</span>")

    return f"""
<section class="run">
  <div class="run-head">
    <h2>{esc(title)}</h2>
    {badge}
    <span class="stat">총 이동 <b>{report.total_travel_min:.0f}</b>분</span>
    <span class="stat">투숙 기간 <b>{report.stay_day_span_min / 60:.0f}</b>시간</span>
    <span class="stat">이동 비중 <b>{share:.1f}</b>%</span>
  </div>
  <p class="note">{esc(note)}</p>
  {build_chart(segments, report)}
  {viol}
  <details><summary>표로 보기</summary>{build_table(segments)}</details>
</section>"""


CSS = """
:root { color-scheme: light dark; }
.viz-root{
  color-scheme: light;
  --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7;
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a;
  --good:#0ca30c; --critical:#d03b3b;
  --window:#eceae2;
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])) .viz-root{
    color-scheme: dark;
    --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835;
    --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
    --window:#26261f;
  }
}
:root[data-theme="dark"] .viz-root{
  color-scheme: dark;
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835;
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70;
  --window:#26261f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--text-primary);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:32px 16px 72px}
header.top{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:8px}
h1{font-size:22px;margin:0;letter-spacing:-.01em}
.sub{color:var(--text-secondary);font-size:13.5px;margin:0 0 20px}
button.theme{margin-left:auto;background:none;border:1px solid var(--axis);color:var(--text-secondary);
  border-radius:999px;padding:5px 14px;font:inherit;font-size:13px;cursor:pointer}
.legend{display:flex;gap:18px;flex-wrap:wrap;align-items:center;
  background:var(--surface-1);border:1px solid var(--grid);border-radius:10px;padding:12px 16px;margin-bottom:24px}
.legend .item{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--text-secondary)}
.legend .sw{width:14px;height:14px;border-radius:4px;flex:0 0 auto}
.legend .sw.win{background:var(--window);border:1px solid var(--grid)}
.legend .sw.mv{background:none;border-top:2px dashed var(--muted);height:0;border-radius:0}
.legend .sw.vi{background:var(--critical);clip-path:polygon(50% 100%,0 0,100% 0)}
.run{background:var(--surface-1);border:1px solid var(--grid);border-radius:12px;
  padding:20px 20px 16px;margin-bottom:22px}
.run-head{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.run-head h2{font-size:16.5px;margin:0}
.badge{font-size:12.5px;font-weight:600;padding:3px 10px;border-radius:999px}
.badge.pass{color:var(--good);background:color-mix(in srgb,var(--good) 12%,transparent)}
.badge.fail{color:var(--critical);background:color-mix(in srgb,var(--critical) 12%,transparent)}
.stat{font-size:13px;color:var(--text-secondary)}
.stat b{color:var(--text-primary);font-variant-numeric:tabular-nums}
.note{font-size:13px;color:var(--text-secondary);margin:8px 0 6px}
svg.chart{width:100%;height:auto;display:block;margin:6px 0 4px;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.grid.day{stroke:var(--axis);stroke-width:1.5}
.lane{stroke:var(--grid);stroke-width:1}
.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.lane-label{fill:var(--text-secondary);font-size:11.5px}
.window{fill:var(--window)}
.move{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:3 3;fill:none;opacity:.75}
.bar{stroke:var(--surface-1);stroke-width:2}
.bar:hover{stroke:var(--text-primary);stroke-width:2}
.bar-label{font-size:10.5px;pointer-events:none}
.bar-label.inside{fill:#fff}
.bar-label.outside{fill:var(--text-secondary)}
.viol-line{stroke:var(--critical);stroke-width:1.5;stroke-dasharray:2 3;opacity:.8}
.viol-mark{fill:var(--critical)}
ul.violations{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:6px}
ul.violations li{display:grid;grid-template-columns:150px 92px 1fr;gap:10px;
  font-size:12.5px;padding:7px 10px;border-radius:8px;
  background:color-mix(in srgb,var(--critical) 8%,transparent)}
ul.violations .code{color:var(--critical);font-weight:600}
ul.violations .when{color:var(--muted);font-variant-numeric:tabular-nums}
ul.violations .what{color:var(--text-secondary)}
details{margin-top:12px}
summary{cursor:pointer;font-size:13px;color:var(--text-secondary)}
table{border-collapse:collapse;width:100%;margin-top:10px;font-size:12.5px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--grid)}
th{color:var(--muted);font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}
#tip{position:fixed;pointer-events:none;background:var(--text-primary);color:var(--surface-1);
  font-size:12px;line-height:1.5;padding:7px 10px;border-radius:7px;white-space:pre;
  opacity:0;transition:opacity .1s;z-index:9}
@media (max-width:760px){ .wrap{padding:20px 10px 48px} ul.violations li{grid-template-columns:1fr} }
"""

JS = """
const tip=document.getElementById('tip');
document.querySelectorAll('.bar,.move').forEach(el=>{
  el.addEventListener('mouseenter',e=>{
    const t=el.dataset.tip||el.querySelector('title')?.textContent||'';
    tip.textContent=t.replace(/\\\\n/g,'\\n'); tip.style.opacity=1;
  });
  el.addEventListener('mousemove',e=>{
    tip.style.left=Math.min(e.clientX+14,innerWidth-260)+'px';
    tip.style.top=(e.clientY+16)+'px';
  });
  el.addEventListener('mouseleave',()=>tip.style.opacity=0);
});
const btn=document.querySelector('button.theme');
btn.addEventListener('click',()=>{
  const cur=document.documentElement.getAttribute('data-theme');
  const next=cur==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',next);
  btn.textContent=next==='dark'?'밝게':'어둡게';
});
"""


def render(sections: list[str], title: str, subtitle: str) -> str:
    legend = """
<div class="legend">
  <span class="item"><span class="sw" style="background:var(--series-1)"></span>투숙</span>
  <span class="item"><span class="sw" style="background:var(--series-2)"></span>업장 · 시설</span>
  <span class="item"><span class="sw" style="background:var(--series-3)"></span>이동 수단</span>
  <span class="item"><span class="sw win"></span>운영 창</span>
  <span class="item"><span class="sw mv"></span>이동 구간</span>
  <span class="item"><span class="sw vi"></span>불변식 위반</span>
</div>"""
    return f"""<!doctype html>
<html lang="ko" class="viz-root">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body class="viz-root">
<div class="wrap">
  <header class="top"><h1>{esc(title)}</h1>
    <button class="theme">어둡게</button></header>
  <p class="sub">{esc(subtitle)}</p>
  {legend}
  {''.join(sections)}
</div>
<div id="tip"></div>
<script>{JS}</script>
</body></html>"""


# ---------------------------------------------------------------------------
# 무엇을 그릴지
# ---------------------------------------------------------------------------

def main() -> None:
    sections: list[str] = []

    # 1) 후기 한 편
    try:
        import blog01 as blog
        sections.append(build_section(
            "후기 A — 검증기가 아는 지점만",
            "발렛과 수영장처럼 이동 그래프에 없던 지점을 뺀 축약판입니다.",
            blog.RUN_A, nights=2))
        sections.append(build_section(
            "후기 B — 체크인 대기 중 이동 포함",
            "웨이팅 번호를 받고 로비 공연을 보고 비스타 쪽까지 다녀온 구간을 넣었습니다.",
            blog.RUN_B, nights=2))
        sections.append(build_section(
            "후기 C — 원문 그대로",
            "발렛 · 수영장 · 피자힐까지 넣은 2박 3일 전체입니다.",
            blog.RUN_C, nights=2))
    except Exception as e:  # noqa
        sections.append(f"<section class='run'><p class='note'>후기 불러오기 실패 — {esc(e)}</p></section>")

    # 2) 후기 페르소나로 v0 · v1 — 후기 C 바로 아래에 두어 위아래로 겹쳐 본다
    try:
        import persona_blog01 as P
        import agent_v0, agent_v1
        from match import evaluate
        start = datetime.fromisoformat("2025-01-31T14:00")
        for mod, name in ((agent_v0, "v0"), (agent_v1, "v1")):
            timeline, _ = mod.run_agent(P.PERSONA, start, verbose=False)
            r = evaluate(timeline, P, title=name)
            note = (f"후기 1편에서 근거를 붙여 뽑은 페르소나 (미상 {len(P.PERSONA.unknown_traits())}개). "
                    f"일치율 — 방문 집합 재현 {r.recall:.0%} · 정밀 {r.precision:.0%} · "
                    f"식당 집합 {r.restaurants_label} · "
                    f"순서 {r.order_ok}/{r.order_checked} · 끼니 {len(r.meals_hit)}/{len(r.meals_truth)}"
                    + (f" · 후기가 안 갔다고 한 곳 {', '.join(sorted(r.forbidden_hit))}" if r.forbidden_hit else ""))
            sections.append(build_section(
                f"에이전트 {name} — 후기 1편 페르소나", note, timeline, nights=P.PERSONA.nights))
    except Exception as e:  # noqa
        sections.append(f"<section class='run'><p class='note'>후기 페르소나 실행 실패 — {esc(e)}</p></section>")

    # 3) 가상 페르소나 셋 (v1)
    try:
        import agent_v0
        import agent_v1 as agent
        start = datetime.fromisoformat("2025-01-31T14:00")
        for p in agent_v0.PERSONAS:
            timeline, _ = agent.run_agent(p, start, verbose=False)
            unknown = p.unknown_traits()
            note = (f"일행 {p.party_size}명 · {p.nights}박"
                    + (" · 13세 미만 동반" if p.has_child_under_13 else ""))
            if unknown:
                note += (f" · 성향 {len(unknown)}개 미상 ({', '.join(unknown)})"
                         " — 0이 아니라 영향 없음으로 가정하고 계산에서 제외")
            sections.append(build_section(
                f"에이전트 v1 — {p.name}", note, timeline, nights=p.nights))
    except Exception as e:  # noqa
        sections.append(f"<section class='run'><p class='note'>에이전트 불러오기 실패 — {esc(e)}</p></section>")

    out = render(
        sections,
        "타임라인 정합성 검증",
        "가로축은 시각, 가로 줄 하나가 장소 하나입니다. 막대는 그 장소에 머문 구간이고 "
        "색은 어느 상태기계에 속하는지입니다. 막대 뒤 옅은 띠가 그 업장의 운영 창이고, "
        "점선이 이동 구간입니다. 빨간 표시가 불변식 위반입니다. 막대에 마우스를 올리면 상세가 나옵니다.",
    )
    with open("timeline_viz.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"timeline_viz.html 생성 — 섹션 {len(sections)}개")


def render_file(path: str, nights: int | None = None, out: str | None = None) -> str:
    """후기 파일 하나를 그린다 — 팀원용.

      python3 viz.py blog03.py            # 그 파일 안의 타임라인 전부
      python3 viz.py blog01.py --nights 2

    파일 안에서 TimelineSegment 리스트인 모듈 변수(RUN_A, STAY_B, BLOG02_TIMELINE, *_PROBE …)를
    전부 찾아 섹션 하나씩 만든다. 위반이 있으면 빨간 표시와 목록이 그대로 붙는다.
    터미널 글자 대신 이걸 보면서 고치라고 만든 것.
    """
    import importlib, os, re, sys
    name = os.path.splitext(os.path.basename(path))[0]
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)) or ".")
    mod = importlib.import_module(name)

    # nights 추정: 파일이 run(..., nights=2) 처럼 부르면 그 값을 쓴다
    if nights is None:
        src = open(path, encoding="utf-8").read()
        m = re.search(r"nights\s*=\s*(\d+)", src)
        nights = int(m.group(1)) if m else 1

    sections = []
    for attr in dir(mod):
        val = getattr(mod, attr)
        if (isinstance(val, list) and val and all(isinstance(x, TimelineSegment) for x in val)
                and attr.isupper()):
            probe = attr.endswith("PROBE")
            note = ("일부러 깨뜨린 점검용 — 위반이 나와야 정상" if probe
                    else f"{name}.{attr} · {len(val)}구간 · nights={nights}")
            sections.append(build_section(f"{name} · {attr}", note, val, nights=nights))

    html = render(
        sections,
        f"{name} — 타임라인 정합성",
        "가로 줄 하나가 장소 하나, 막대는 그 장소에 머문 구간입니다. 막대 뒤 옅은 띠가 운영 창, "
        "점선이 이동입니다. 빨간 표시가 위반이고, 그 아래 목록에 어느 불변식이 왜 걸렸는지 나옵니다. "
        "막대에 마우스를 올리면 상세가 나옵니다.",
    )
    out = out or f"{name}_viz.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{out} 생성 — 섹션 {len(sections)}개")
    return out


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:]]
    if args and args[0].endswith(".py"):
        n = None
        if "--nights" in args:
            n = int(args[args.index("--nights") + 1])
        render_file(args[0], nights=n)
    else:
        main()
