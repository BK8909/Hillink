"""Verify and reconnect a relocated private data bundle to this product checkout."""
import argparse,hashlib,json,os,shlex,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def publish(path,raw):
 path=Path(path)
 if path.exists() and path.read_bytes()==raw:return
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,name=tempfile.mkstemp(prefix='.restore-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as output:output.write(raw)
  os.chmod(name,0o600)
  os.replace(name,path)
 finally:
  Path(name).unlink(missing_ok=True)
def connect(bundle):
 b=Path(bundle).resolve()
 if any((x/'.git').exists() for x in (b,*b.parents)):raise ValueError('private_bundle_must_be_outside_git')
 manifest=json.loads((b/'manifest.json').read_text())
 if sha(b/'registry.private.json')!=manifest['registry_sha256']:raise ValueError('registry_manifest_mismatch')
 for row in manifest['files']:
  path=(b/row['path']).resolve()
  if b not in path.parents or sha(path)!=row['sha256']:raise ValueError('private_manifest_mismatch')
 registry=json.loads((b/'registry.private.json').read_text())
 for row in registry['customers']:
  for key in ('profile','library','source_import','product_check'):
   path=b/'customers'/row['customer_id']/(key+'.json')
   if b not in path.resolve().parents or sha(path)!=row[key]['sha256']:raise ValueError('customer_reference_mismatch')
   row[key]['path']=str(path)
 target=b/'registry.runtime.json';publish(target,json.dumps(registry,ensure_ascii=False,indent=2).encode())
 for row in manifest['files']:
  if row['role']=='local_overlay':
   relative=Path(row['path']).relative_to('overlays');dest=(ROOT/relative).resolve()
   if ROOT not in dest.parents:raise ValueError('invalid_overlay_destination')
   publish(dest,(b/row['path']).read_bytes())
 return target
def main():
 p=argparse.ArgumentParser();p.add_argument('bundle',type=Path);a=p.parse_args();target=connect(a.bundle)
 print('export HILLINK_ISOLATED_REGISTRY='+shlex.quote(str(target)))
 print('export HILLINK_ISOLATED_REGISTRY_SHA256='+sha(target))
if __name__=='__main__':main()
