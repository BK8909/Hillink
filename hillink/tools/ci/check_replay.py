"""Run the 38 stored V16 replays offline and compare with the recorded expectation (no network, no key)."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
exp = [json.loads(l) for l in open(ROOT / 'tools/ci/replay_expected_v16_38.jsonl', encoding='utf-8')]
out = subprocess.run([sys.executable, str(ROOT / 'tools/ci/replay_check.py'), str(ROOT)] + [e['tag'] for e in exp], capture_output=True, text=True, cwd=ROOT)
got = [json.loads(l) for l in out.stdout.splitlines() if l.startswith('{')]
same = sum(a == b for a, b in zip(exp, got))
print('V16 replay identical: %d / %d' % (same, len(exp)))
if out.returncode or same != len(exp) or len(got) != len(exp):
    print(out.stderr[-2000:]); sys.exit(1)
