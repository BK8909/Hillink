"""A cold process must serve capabilities before another route warms import paths."""
import json,os,socket,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_first_capabilities_request_in_fresh_process(tmp_path):
 with socket.socket() as reserved:
  reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
 env=dict(os.environ,PYTHONPATH=str(ROOT/'tools/offline_test_guard'),HILLINK_ISOLATED_CUSTOMERS='0',HILLINK_AUTONOMOUS_AGENT='0',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_AGENT_MODE='off')
 with (tmp_path/'server.log').open('w') as log:
  server=subprocess.Popen([sys.executable,'-B',str(ROOT/'timeline/viewer/app.py'),'--port',str(port),'--no-browser'],cwd=tmp_path,env=env,stdout=log,stderr=log)
  try:
   deadline=time.monotonic()+10
   while True:
    try:
     with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/runtime/capabilities',timeout=3) as response:result=json.load(response)
     break
    except urllib.error.HTTPError:raise
    except urllib.error.URLError:
     if server.poll() is not None or time.monotonic()>deadline:raise
     time.sleep(.05)
   assert result['isolated_customers']==[]
   assert result['autonomous_agent'] is False
  finally:server.terminate();server.wait(timeout=5)
