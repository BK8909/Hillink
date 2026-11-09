"""v20c repeat runner (no key, no cost): a recorded request is rebuilt byte-identically, memory OFF removes only the
earlier-day memory (block + candidate marks) and keeps system text, schema and settings, and the batch cap blocks."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/v18_batch'))
sys.path.insert(0, str(ROOT / 'timeline/experiments/persona_live'))
import repeat_live as R  # noqa: E402
from operator_choice.autonomy_v1 import agent_provider as P  # noqa: E402

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['selected_action_id', 'selected_basket_id', 'reason'],
          'properties': {'selected_action_id': {'type': 'string'}, 'selected_basket_id': {'type': ['string', 'null']}, 'reason': {'type': 'string'}}}


def record(src, rel, context, policy='LLM_AUTONOMOUS_CUSTOMER_V19LS_MEM1', purpose='BREAKFAST_SELECTION'):
    body = P.build_payload(system='시스템 + 기억 지시', context=context, schema=SCHEMA, model='gpt-6-luna', effort='medium', max_output=16000,
                           stable_prefix=True, prefix_message='personal')
    p = src / (rel + '.request.json'); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(key=p.name[:-13], policy=policy, purpose=purpose, input_sha256=P.request_identity(policy, purpose, body),
                                 request_body=body), ensure_ascii=False))
    return body


def make_source(tmp):
    src = tmp / 'src'
    ctx = dict(personal={'records': [{'fact_ids': ['F1']}]}, visit={'date': '2026-11-08'}, state={'time': '08:10'},
               candidates=[dict(action_id='BREAKFAST_BUFFET', items=[{'sku_id': 'S', 'quantity': 2}], conditions={'price_krw': 85000}),
                           dict(action_id='SKIP_BREAKFAST', conditions={'price_krw': 0}, earlier_use={'times': 1})],
               earlier_days={'days': [{'date': '2026-11-07'}]})
    for k, rel in R.SRC.items():
        record(src, rel, ctx if k != 'd1_dinner' else {k2: v for k2, v in ctx.items() if k2 != 'earlier_days'})
    return src, ctx


def test_rebuild_is_byte_identical_and_memory_off_changes_only_memory(tmp_path):
    src, ctx = make_source(tmp_path)
    on = R.build(dict(source='d2_breakfast', memory='on'), str(src), P)
    off = R.build(dict(source='d2_breakfast', memory='off'), str(src), P)
    assert on['byte_identical_to_recorded'] and not off['byte_identical_to_recorded']
    assert off['removed'] == {'keys': ['earlier_days'], 'marks': 1}
    assert off['payload']['input'][0] == on['payload']['input'][0] and off['payload']['text'] == on['payload']['text']   # same system and schema
    assert off['payload']['input'][1] == on['payload']['input'][1]                                                     # same personal prefix
    u_on, u_off = json.loads(on['payload']['input'][2]['content']), json.loads(off['payload']['input'][2]['content'])
    assert 'earlier_days' not in u_off and u_off['visit'] == u_on['visit'] and u_off['state'] == u_on['state']
    assert [c['action_id'] for c in u_off['candidates']] == [c['action_id'] for c in u_on['candidates']]
    assert R.inspect({'selected_action_id': 'BREAKFAST_BUFFET', 'selected_basket_id': None}, on['context'])['valid_action']


def test_offline_run_and_batch_cap(tmp_path):
    src, _ = make_source(tmp_path)
    env = dict(os.environ); env.pop('HILLINK_AGENT_BUDGET_FILE', None)
    run = lambda d, *extra: subprocess.run([sys.executable, str(ROOT / 'tools/v18_batch/repeat_live.py'), 'run', '--source', str(src), '--batch-dir', str(d),
                                            '--shadow', 'offline', *extra], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    r = run(tmp_path / 'ok'); assert r.returncode == 0, r.stderr[-1500:]
    s = json.load(open(tmp_path / 'ok/repeat_status.json'))
    assert len(s['samples']) == 15 and all(x['execution'] == 'OFFLINE_SYNTHETIC' for x in s['samples'])
    assert [x['memory'] for x in s['samples'][5:9]] == ['on', 'off', 'on', 'off']        # ON/OFF interleaved
    r = run(tmp_path / 'cap', '--max-calls', '3'); assert r.returncode == 0
    s = json.load(open(tmp_path / 'cap/repeat_status.json'))
    assert len(s['samples']) == 3 and s['blocked'] and 'BATCH_CAP' in s['blocked'][0]['reason']
    assert run(tmp_path / 'over', '--max-calls', '21').returncode != 0                      # caps above the approval are refused
