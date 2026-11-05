"""Capabilities must work before any profile/registry/visit request primes imports."""
import os
from pathlib import Path
import subprocess
import sys


def test_runtime_capabilities_is_a_valid_first_request_in_fresh_process():
    viewer = Path(__file__).resolve().parents[1]
    program = '''
import json, threading, urllib.request
import app
server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.H)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    url = 'http://127.0.0.1:%d/api/runtime/capabilities' % server.server_port
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.load(response)
        assert response.status == 200
        assert data['autonomous_policy'].startswith('LLM_AUTONOMOUS_CUSTOMER_')
        assert data['agent_mode'] == 'off'
        assert data['llm_strategy'] is False
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
'''
    env = dict(os.environ, HILLINK_AGENT_MODE='off', HILLINK_LLM_EXTERNAL_OPT_IN='0',
               HILLINK_ISOLATED_CUSTOMERS='0', PYTHONPATH=str(viewer))
    result = subprocess.run([sys.executable, '-c', program], cwd=viewer, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
