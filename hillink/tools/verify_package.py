"""Verify every included product file against the handover manifest."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
 manifest=json.loads((ROOT/'handover/package_manifest.json').read_text())
 for row in manifest['files']:
  if not row['included']:continue
  target=(ROOT/row['path']).resolve()
  if ROOT not in target.parents or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
   raise ValueError('PACKAGE_FILE_MISMATCH: '+row['path'])
 print('Package files verified:',sum(r['included'] for r in manifest['files']))
if __name__=='__main__':verify()
