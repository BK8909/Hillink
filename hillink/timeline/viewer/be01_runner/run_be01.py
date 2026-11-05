"""Product handoff launcher: verify frozen execution/input version, then compute a NEW visit."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--request',required=True);p.add_argument('--policy',required=True,choices=['baseline','active']);p.add_argument('--out',required=True);a=p.parse_args();r=Path(a.bundle)
seal=json.loads((r/'SEAL.json').read_text())
for f in seal['files']:
 path=r/f['path']
 if not path.exists():raise SystemExit('Missing frozen dependency: '+f['path'])
 if hashlib.sha256(path.read_bytes()).hexdigest()!=f['sha256']:raise SystemExit('Frozen version mismatch: '+f['path'])
subprocess.run([sys.executable,str(r/'frozen/research/cohort_entry.py'),'--root',str(r),'--request',a.request,'--policy',a.policy,'--out',a.out],check=True)

subprocess.run([sys.executable,str(Path(__file__).with_name('cohort_export.py')),a.out],check=True)
