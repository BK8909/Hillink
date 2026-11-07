"""Same request, different per-process string hash: the visit result must be byte-identical (no model call).

  python tools/ci/check_determinism.py      (run from the product directory after the data restore)

Each case runs timeline/viewer/visit_run.py twice with PYTHONHASHSEED 1 and 2 in rules mode with the product
environment of tools/start_product.sh, and compares the whole JSON result (choices, amounts, ledger, explanations).
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = [('A26', 'wine', 'stay_1'), ('N23', 'wine', 'stay_1'), ('A05', 'none', 'stay_2')]
data = json.loads(subprocess.run([sys.executable, '-B', 'tools/bootstrap_data.py', '--json'], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout)
ENV = dict(os.environ, HILLINK_LLM_ENABLED='0', HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_AGENT_MODE='replay',
           HILLINK_V12Z_COMMON='1', HILLINK_NATIVE_HYBRID='1', HILLINK_AUTONOMOUS_AGENT='1', HILLINK_HYBRID='replay',
           HILLINK_GENERAL_FOOD_POLICY='A', HILLINK_BREAKFAST_POLICY='BREAKFAST_INCLUDED_DEFAULT_V2', HILLINK_DEPLOY='local',
           PYTHONPATH=str(ROOT / 'tools/offline_test_guard'), HILLINK_ISOLATED_REGISTRY=data['path'],
           HILLINK_ISOLATED_REGISTRY_SHA256=data['sha256'], HILLINK_PROFILE_DISPLAY_REVIEW=data.get('profile_display_review') or '',
           HILLINK_ISOLATED_CUSTOMERS='1', HILLINK_REVIEWER_LOCAL='1')


def run(pid, event, duration, seed):
    req = dict(personas=[pid], duration=duration, event_mode=event, seed=0, start_date='2026-10-24', include_ledger=True,
               judgment_mode='rules', behavior_engine='m4_c01', catalog_policy='C01_HOTEL_CATALOG_V1')
    out = subprocess.run([sys.executable, '-B', 'timeline/viewer/visit_run.py'], input=json.dumps(req), cwd=ROOT,
                         capture_output=True, text=True, env=dict(ENV, PYTHONHASHSEED=str(seed)), timeout=900)
    if out.returncode: print(out.stderr[-600:]); sys.exit(1)
    return out.stdout


def first_difference(a, b, path=''):
    if type(a) != type(b): return path
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b: return path + '/' + k
            d = first_difference(a[k], b[k], path + '/' + k)
            if d: return d
    elif isinstance(a, list):
        if len(a) != len(b): return path
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, path + '/' + str(i))
            if d: return d
    elif a != b: return path
    return None


bad = 0
for case in CASES:
    a, b = run(*case, 1), run(*case, 2)
    same = a == b
    print(('PASS ' if same else 'FAIL ') + ' '.join(case) + ('' if same else ' · first difference ' + str(first_difference(json.loads(a), json.loads(b)))))
    bad += not same
print('determinism: %d/%d identical under two hash seeds' % (len(CASES) - bad, len(CASES)))
sys.exit(1 if bad else 0)
