"""The branch carries its inputs; runtime restore must verify every source byte."""
import json,os,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_bundle_is_complete_and_portable(tmp_path):
 spec=json.loads((ROOT/'handover/data/bundle.json').read_text())
 assert spec['required_external_input_files']==0
 env=dict(os.environ,HILLINK_DATA_HOME=str(tmp_path/'cache'))
 p=subprocess.run([sys.executable,str(ROOT/'tools/bootstrap_data.py'),'--json'],capture_output=True,text=True,env=env)
 assert p.returncode==0,p.stderr
 result=json.loads(p.stdout);registry=json.loads(Path(result['path']).read_text())
 assert len(registry['customers'])==17
 assert all(Path(r[k]['path']).is_file() for r in registry['customers'] for k in ('profile','library','source_import','product_check'))
 manifest=Path(result['path']).parent/'manifest.json';manifest.write_text('{}')
 p=subprocess.run([sys.executable,str(ROOT/'tools/bootstrap_data.py'),'--json'],capture_output=True,text=True,env=env)
 assert p.returncode!=0 and 'MANIFEST_SHA_MISMATCH' in p.stderr
