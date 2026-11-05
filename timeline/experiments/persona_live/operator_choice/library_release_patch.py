"""Generate/rehearse a pinned historical-runtime patch, never deploy it.

python3 -m operator_choice.library_release_patch --write NEW_DIRECTORY
Reads only tracked code and existing public JSON/HTML, not private reviews.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from . import library_release_policy as policy

SOURCE = "f798373"
BASE = "timeline/experiments/persona_live/"
FILES = ("library.py", "library_ext/build_public.py", "build_sim.py", "serve_demo.py")


def git_file(path):
    return subprocess.check_output(["git", "show", SOURCE + ":" + BASE + path])


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("historical_source_mismatch")
    return text.replace(old, new, 1)


def changed_sources():
    old = {f: git_file(f).decode() for f in FILES}
    new = dict(old)
    new["library_ext/build_public.py"] = replace_once(old["library_ext/build_public.py"],
        "    return meta\n", "    from library_release_policy import public_metadata\n    return public_metadata(meta)\n")
    new["library_ext/build_public.py"] = new["library_ext/build_public.py"].replace(
        "작성자 키(해시) · ", "").replace(
        "넣지 않는 것: URL", "넣지 않는 것: 작성자 키(해시) · 시험용 중복 및 관련 격리 기록 · URL")
    new["library.py"] = replace_once(old["library.py"],
        'm = json.loads(REVIEWS_META.read_text(encoding="utf-8")); items = []; detail = {}',
        'from library_release_policy import public_metadata\n    m = public_metadata(json.loads(REVIEWS_META.read_text(encoding="utf-8"))); items = []; detail = {}')
    new["library.py"] = replace_once(new["library.py"],
        '("acct:" + r["author_key"]) if r["author_key"] else None', 'None')
    # Wrapper catches both legacy account hashes and embedded detail before callers
    # (including build_sim) serialize it. Original tag/stage/model logic is intact.
    new["library.py"] = replace_once(new["library.py"], "def build() -> dict:\n", "def _build_unreleased() -> dict:\n")
    new["library.py"] = replace_once(new["library.py"], "\ndef main():\n", '''
def build() -> dict:
    from library_release_policy import public_library
    metadata = json.loads(REVIEWS_META.read_text(encoding="utf-8")) if REVIEWS_META.exists() else {}
    return public_library(_build_unreleased(), metadata)

def main():
''')
    # build_sim formerly persisted detail inside library.json, unlike library.main.
    new["build_sim.py"] = replace_once(old["build_sim.py"],
        'lib = LIBM.build(); (DEMO / "library.json").write_text',
        'lib = LIBM.build(); detail = lib.pop("detail", {}); (DEMO / "library_detail.json").write_text(json.dumps(detail, ensure_ascii=False), encoding="utf-8"); (DEMO / "library.json").write_text')
    new["serve_demo.py"] = replace_once(old["serve_demo.py"], "    def do_GET(self):\n", '''    def do_GET(self):
        from library_release_policy import json_route, public_html
        def load_json(path, default):
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        # Even stale generated files must pass the same release policy.
        meta = load_json(HERE / "library_ext/data/public/reviews_meta.json", {})
        route = json_route(self.path, load_json(DEMO / "library.json", {}),
                           load_json(DEMO / "library_detail.json", {}), meta)
        if route is not None:
            code, payload = route
            return self._send(code, json.dumps(payload, ensure_ascii=False).encode(), TYPES[".json"])
''')
    new["serve_demo.py"] = replace_once(new["serve_demo.py"],
        '(DEMO / "persona_sim.html").read_bytes()',
        'public_html((DEMO / "persona_sim.html").read_text(encoding="utf-8"), meta).encode()')
    # Remove the obsolete raw detail branch entirely, not merely hide the list.
    start = new["serve_demo.py"].index('        elif self.path == "/library_detail.json":')
    end = new["serve_demo.py"].index('        elif self.path == "/map_base.png":', start)
    new["serve_demo.py"] = new["serve_demo.py"][:start] + new["serve_demo.py"][end:]
    old["library_release_policy.py"] = ""
    new["library_release_policy.py"] = Path(policy.__file__).read_text(encoding="utf-8")
    return old, new


def make_patch():
    old, new = changed_sources()
    diff = "".join("".join(difflib.unified_diff(old[f].splitlines(True), new[f].splitlines(True),
        fromfile="a/" + BASE + f if old[f] else "/dev/null", tofile="b/" + BASE + f)) for f in new)
    # Git accepts empty context lines without a single-space prefix. Avoid
    # trailing-whitespace diagnostics on this patch stored as a new text file.
    return "".join("\n" if line == " \n" else line for line in diff.splitlines(True))


def project_public():
    """In-memory public-only rehearsal; never reopens source Excel/body archives."""
    raw = {f: git_file(f) for f in ("demo/library.json", "demo/library_detail.json",
                                  "library_ext/data/public/reviews_meta.json", "demo/persona_sim.html")}
    lib, detail, meta = (json.loads(raw[f]) for f in list(raw)[:3])
    safe = policy.public_library(lib, meta)
    return raw, safe, policy.public_detail(detail, meta), policy.public_metadata(meta)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path, required=True)
    args = ap.parse_args()
    # Exclusive new output directory: no overwrite or deployment.
    args.write.mkdir(parents=True, exist_ok=False)
    patch = make_patch()
    (args.write / "historical_619_release.patch").write_text(patch, encoding="utf-8")
    raw, lib, detail, meta = project_public()
    report = {"source_commit": subprocess.check_output(["git", "rev-parse", SOURCE], text=True).strip(),
              "policy": policy.VERSION, "mode": "isolated_rehearsal_not_deployed",
              "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
              "source_blob_sha256": {f: hashlib.sha256(b).hexdigest() for f, b in raw.items()},
              "source_records": len(json.loads(raw["demo/library.json"])["items"]),
              "release_records": len(lib["items"]), "release_details": len(detail),
              "release_metadata": len(meta["records"]), "published": False}
    # No 619 data replica or author hash is written to research/GitHub.
    (args.write / "rehearsal.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
