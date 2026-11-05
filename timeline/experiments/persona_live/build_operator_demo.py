"""운영 실험실 화면 생성 (10/22 · 총괄 C · 격리) — python3 build_operator_demo.py
operator_choice/operator_world_v1_artifacts/{presets,traits,grid}.json 을 demo/operator_world_template.html 에 넣어 demo/operator_world.html 을 만든다.
기존 build_sim.py · persona_sim.html · library.json 은 건드리지 않는다. 서버 없이 파일로 열린다.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "operator_choice" / "operator_world_v1_artifacts"
TPL = HERE / "demo" / "operator_world_template.html"
OUT = HERE / "demo" / "operator_world.html"


def embed(doc) -> str:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def main():
    presets = json.loads((ART / "presets.json").read_text(encoding="utf-8"))
    traits = json.loads((ART / "traits.json").read_text(encoding="utf-8"))
    grid = json.loads((ART / "grid.json").read_text(encoding="utf-8"))
    html = TPL.read_text(encoding="utf-8")
    for tag, doc in (("/*__PRESETS__*/null", presets), ("/*__TRAITS__*/null", traits), ("/*__GRID__*/null", grid)):
        assert html.count(tag) == 1, tag
        html = html.replace(tag, embed(doc))
    OUT.write_text(html, encoding="utf-8")
    print(OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
