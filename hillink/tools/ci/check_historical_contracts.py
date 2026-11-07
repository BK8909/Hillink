"""Historical contract reproduction (separate from current-product checks; never counted as a current-engine fix).

CD-15 (sealed operating experiment): its run manifest records the SHA-256 of the engine files it was computed with.
The current engine differs, so the product refuses to compute it (ENGINE_SHA_MISMATCH, tested elsewhere). Here the
sealed file versions are taken from this repository's own Git history by their SHA-256, placed into a temporary
worktree of the current commit, and the original CD-15 tests are run there unchanged.

  python tools/ci/check_historical_contracts.py      (product directory; needs full Git history and the restored data)
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
OC = 'timeline/experiments/persona_live/operator_choice'
FILES = {'engine.py': f'{OC}/operator_world_v1/engine.py', 'turn_view.py': f'{OC}/operator_world_v1_1/turn_view.py',
         'turn_candidate.py': f'{OC}/operator_world_v1_1/turn_candidate.py'}
LOCAL = f'{OC}/operator_world_v1_1/turn_personas_ext.local.json'


def git(*a, **k): return subprocess.run(['git', *a], cwd=REPO, capture_output=True, check=True, **k).stdout


def sealed_blob(name, want):
    for line in git('rev-list', '--all', '--objects', text=True).splitlines():
        parts = line.split(' ', 1)
        if len(parts) == 2 and parts[1].endswith('/' + name) or (len(parts) == 2 and parts[1] == name):
            data = git('cat-file', '-p', parts[0])
            if hashlib.sha256(data).hexdigest() == want: return parts[0], data
    return None, None


manifest = json.loads((ROOT / OC / 'cd1024_15/run_manifest.json').read_text(encoding='utf-8'))['source_code_sha256']
tmp = Path(tempfile.mkdtemp(prefix='hillink-cd15-')); tree = tmp / 'tree'
subprocess.run(['git', 'worktree', 'add', '--detach', str(tree), 'HEAD'], cwd=REPO, capture_output=True, check=True)
try:
    prod = tree / ROOT.relative_to(REPO)
    for name, rel in FILES.items():
        cur = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        if cur == manifest[name]: print('same as sealed:', name); continue
        blob, data = sealed_blob(name, manifest[name])
        if data is None: print('sealed version not in Git history:', name); sys.exit(1)
        (prod / rel).write_bytes(data); print('sealed version restored from history:', name, blob[:10])
    if not (ROOT / LOCAL).exists(): print('local CD-15 profile not restored; run tools/bootstrap_data.py first'); sys.exit(1)
    shutil.copy2(ROOT / LOCAL, prod / LOCAL)
    env = dict(os.environ, PYTHONPATH=str(prod / 'tools/offline_test_guard'))
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'timeline/viewer/tests/test_opx_adapter.py'], cwd=prod, env=env, capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
    ok = r.returncode == 0
    print('CD-15 historical contract with the sealed engine files:', 'REPRODUCED' if ok else 'NOT REPRODUCED',
          '(historical reproduction only; the current engine still refuses this experiment by design)')
    sys.exit(0 if ok else 1)
finally:
    subprocess.run(['git', 'worktree', 'remove', '--force', str(tree)], cwd=REPO, capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)
