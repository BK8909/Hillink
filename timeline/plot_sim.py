"""sim_result.json → 그래프 PNG 둘 (docs/). python3 plot_sim.py"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

import glob
for f in glob.glob("/usr/share/fonts/**/NotoSansCJK*-Regular.tt*", recursive=True) + glob.glob("/usr/share/fonts/**/NotoSansCJK*-Medium.tt*", recursive=True):
    fm.fontManager.addfont(f)
_fams = {f.name for f in fm.fontManager.ttflist}
plt.rcParams["font.family"] = next((n for n in ("Noto Sans CJK KR", "Noto Sans CJK JP", "Apple SD Gothic Neo", "AppleGothic") if n in _fams), "sans-serif")
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
S1, S2 = "#2a78d6", "#eb6834"
NAMES = {"PIZZA_HILL": "피자힐", "LE_PASSAGE": "르파사쥬 포장", "DOUGLAS_LOUNGE": "더글라스 라운지",
         "THE_BUFFET": "더뷔페", "MYONGWOLGWAN": "명월관", "GEUMRYONG": "금룡", "ONDAL": "온달",
         "GRAND_CLUB_LOUNGE": "클럽라운지"}

R = json.loads(Path(__file__).with_name("sim_result.json").read_text(encoding="utf-8"))
out = Path(__file__).resolve().parents[1] / "docs"
out.mkdir(exist_ok=True)

def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)

# 1. 피자힐 시간대별 인원
slots, occ = R["slots"], R["pizza_base"]
keep = [i for i, t in enumerate(slots) if "10:00" <= t <= "21:30"]
x = [slots[i] for i in keep]; y = [occ[i] for i in keep]
fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200); fig.patch.set_facecolor(SURF); style(ax)
ax.bar(range(len(x)), y, width=0.8, color=S1, edgecolor=SURF, linewidth=1)
pk = max(range(len(y)), key=lambda i: y[i])
ax.annotate(f"최대 {y[pk]}명 · {x[pk]}", (pk, y[pk]), xytext=(0, 6), textcoords="offset points",
            ha="center", fontsize=9, color=INK)
ax.set_xticks(range(0, len(x), 2)); ax.set_xticklabels(x[::2])
ax.set_ylabel("머무는 인원 (명)", color=INK2, fontsize=9)
ax.set_title(f"피자힐 — 같은 날 {R['teams']}팀({R['people']}명)을 돌렸을 때 30분마다 머무는 인원",
             loc="left", fontsize=10.5, color=INK, pad=10)
fig.text(0.01, 0.01, "손님끼리 줄을 모르는 모델이라 저녁 창이 열리는 17:30 에 한꺼번에 몰린다. 좌석 수가 있어야 대기가 생긴다.",
         fontsize=7.5, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(out / "sim_pizzahill_occupancy.png", facecolor=SURF); plt.close(fig)

# 2. 저녁 장소 — 기본 vs 피자힐 휴장
b, c = R["dinner_base"], R["dinner_closed"]
keys = sorted(set(b) | set(c), key=lambda k: -(b.get(k, 0) + c.get(k, 0)))
labels = [NAMES.get(k, k) for k in keys]
import numpy as np
yy = np.arange(len(keys))[::-1]; h = 0.36
fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200); fig.patch.set_facecolor(SURF); style(ax)
ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID, linewidth=0.8)
ax.spines["bottom"].set_visible(False)
bb = ax.barh(yy + h/2 + 0.02, [b.get(k, 0) for k in keys], height=h, color=S1, label="평소", edgecolor=SURF)
cc = ax.barh(yy - h/2 - 0.02, [c.get(k, 0) for k in keys], height=h, color=S2, label="피자힐 휴장", edgecolor=SURF)
for bars in (bb, cc):
    for r in bars:
        ax.text(r.get_width() + 0.4, r.get_y() + r.get_height()/2, f"{int(r.get_width())}", va="center", fontsize=8.5, color=INK)
ax.set_yticks(yy); ax.set_yticklabels(labels, fontsize=9.5, color=INK)
ax.set_xlabel("저녁을 먹은 팀 수", color=INK2, fontsize=9)
ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=INK)
mv = R["pizza_moved"]
ax.set_title(f"피자힐이 문을 닫으면 — 피자힐 손님 {sum(mv.values())}팀이 간 곳: " +
             " · ".join(f"{NAMES.get(k, k)} {v}" for k, v in sorted(mv.items(), key=lambda kv: -kv[1])),
             loc="left", fontsize=10.5, color=INK, pad=10)
fig.tight_layout(); fig.savefig(out / "sim_pizzahill_closed.png", facecolor=SURF); plt.close(fig)
print("docs/sim_pizzahill_occupancy.png · docs/sim_pizzahill_closed.png")
