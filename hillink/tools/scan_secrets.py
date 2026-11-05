"""Scan candidate files and committed data archives without printing matched values."""
import argparse,gzip,hashlib,io,json,re,subprocess,tarfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RULES={
 'openai_key':rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}',
 'github_token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
 'aws_access_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'slack_token':rb'\bxox[baprs]-[A-Za-z0-9-]{16,}',
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'assigned_credential':rb'''(?i)(?:OPENAI_API_KEY|API_KEY|API_SECRET|CLIENT_SECRET|ACCESS_TOKEN|REFRESH_TOKEN|SECRET_ACCESS_KEY)[\"'\s]*[:=][\s\"']*([A-Za-z0-9_/+=-]{20,})''',
 'bearer_credential':rb'Authorization[\"\s:=]+Bearer [A-Za-z0-9_\-\.]{32,}'
}
FIXTURE_HASHES={'timeline/viewer/tests/test_openai_credentials.py': {'ee7188d0b248344f4f71f32618334279957306d6a2048c740fc0c35181fe9b4e'}}
def scan(paths):
 issues=[];fixture_matches=0;count=0;total=0
 def inspect(name,raw,depth=0):
  nonlocal count,total,fixture_matches
  if depth>4:raise ValueError('ARCHIVE_NESTING_EXCEEDED')
  count+=1;total+=len(raw)
  if raw.startswith(b'PK\x03\x04'):
   with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    for entry in archive.infolist():
     if not entry.is_dir():inspect(name+'!'+entry.filename,archive.read(entry),depth+1)
  elif raw.startswith(b'\x1f\x8b'):
   unpacked=gzip.decompress(raw)
   try:
    with tarfile.open(fileobj=io.BytesIO(unpacked),mode='r:') as archive:
     for entry in archive:
      if entry.isfile():inspect(name+'!'+entry.name,archive.extractfile(entry).read(),depth+1)
   except tarfile.ReadError:inspect(name+'!gunzip',unpacked,depth+1)
  compressed = raw.startswith((b'PK\x03\x04', b'\x1f\x8b'))
  if compressed:return
  for rule,pattern in RULES.items():
   prefixes={'openai_key':(b'sk-',),'github_token':(b'ghp_',b'gho_',b'ghu_',b'ghs_',b'ghr_',b'github_pat_'),'aws_access_key':(b'AKIA',b'ASIA'),'slack_token':(b'xox',),'private_key':(b'PRIVATE KEY',),'bearer_credential':(b'Authorization',)}
   if rule in prefixes and not any(value in raw for value in prefixes[rule]):continue
   if rule=='assigned_credential' and not any(value in raw.upper() for value in (b'API_KEY',b'API_SECRET',b'CLIENT_SECRET',b'ACCESS_TOKEN',b'REFRESH_TOKEN',b'SECRET_ACCESS_KEY')):continue
   for match in re.finditer(pattern,raw):
    value=match.group(1) if rule=='assigned_credential' else match.group()
    if hashlib.sha256(value).hexdigest() in FIXTURE_HASHES.get(name,set()):
     fixture_matches+=1;continue
    issues.append(dict(path=name,rule=rule,match_sha256=hashlib.sha256(value).hexdigest()))

 for relative in paths:
  p=ROOT/relative
  if p.is_file():inspect(relative,p.read_bytes())
 return dict(files_and_archive_entries=count,bytes_scanned=total,findings=issues,known_noncredential_fixture_matches=fixture_matches,matched_values_printed=False)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args()
 paths=subprocess.check_output(['git','-c','core.quotepath=false','ls-files','-z'],cwd=ROOT,text=True).rstrip('\0').split('\0')
 paths+=['handover/data/product-inputs.tar.gz','handover/data/bundle.json']
 result=scan(sorted(set(paths)))
 if a.output:a.output.write_text(json.dumps(result,indent=2))
 print(json.dumps(dict(files_and_archive_entries=result['files_and_archive_entries'],finding_count=len(result['findings']))))
 raise SystemExit(bool(result['findings']))
