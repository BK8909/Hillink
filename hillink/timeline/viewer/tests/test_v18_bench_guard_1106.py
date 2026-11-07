"""V18 bench: checkpoint identity before reuse, no automatic re-send, private files, request field diff.

Pure-function tests of tools/v18_bench/guard.py and request_diff.py (no visit, no network).
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/v18_bench'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guard as G  # noqa: E402
import request_diff as RD  # noqa: E402
import hotel_ledger  # noqa: E402,F401
from operator_choice.autonomy_v1 import agent_provider as P  # noqa: E402


def body(effort='high', system='지시\n응답 작성:\n출력', personal=None, schema=None, extra=None):
    ctx2 = dict(visit=dict(date='2026-11-05'), candidates=[dict(action_id='room_rest')], **(extra or {}))
    return dict(model='gpt-6-luna', store=False, reasoning={'effort': effort}, max_output_tokens=16000,
                input=[dict(role='system', content=system),
                       dict(role='user', content=json.dumps(dict(personal=personal or dict(citable_fact_ids=['F1', 'F2'], evidence_records=[dict(fact_ids=['F1'], summary='a'), dict(fact_ids=['F2'], summary='b')])), ensure_ascii=False)),
                       dict(role='user', content=json.dumps(ctx2, ensure_ascii=False))],
                text={'format': {'type': 'json_schema', 'name': 'hillink_agent', 'strict': True, 'schema': schema or {'type': 'object', 'properties': {'x': {'type': 'string'}}}}})


def call(guard, key, payload, sent, policy='P', fail=None):
    identity = P.request_identity(policy, 'BENCH', payload)
    def send(capture):
        capture('request', dict(request_body=payload, input_sha256=identity))
        sent.append(identity)
        if fail: raise fail
        return dict(x='ok'), dict(execution='TEST', input_sha256=identity, charged_upper_usd=0.001)
    return guard.call(key, policy, 'BENCH', payload, identity, P.REQUEST_POLICY, 0.01, send)


def test_same_request_resumes_from_the_checkpoint_without_a_new_call(tmp_path):
    sent = []
    g = G.Guard(str(tmp_path), max_calls=8, max_usd=0.2)
    a1, _ = call(g, 'A07_k_a1', body(), sent)
    a2, t2 = call(G.Guard(str(tmp_path), max_calls=8, max_usd=0.2), 'A07_k_a1', body(), sent)
    assert a1 == a2 and t2['reused_from_checkpoint'] and len(sent) == 1
    st = g.state(); assert st['calls_started'] == 1 and st['reused'] == 1


@pytest.mark.parametrize('change', ['effort', 'system', 'personal', 'policy'])
def test_a_changed_setting_blocks_reuse_and_does_not_call(tmp_path, change):
    sent = []
    call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent)
    changed = dict(effort=body(effort='medium'), system=body(system='다른 지시\n응답 작성:\n출력'),
                   personal=body(personal=dict(citable_fact_ids=['F1'])), policy=body())[change]
    with pytest.raises(G.Blocked, match='CHECKPOINT_IDENTITY_MISMATCH'):
        call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', changed, sent, policy='Q' if change == 'policy' else 'P')
    assert len(sent) == 1, 'no reuse and no automatic call'
    assert G.Guard(str(tmp_path), 8, 0.2).state()['blocked'][-1]['reason'].startswith('CHECKPOINT_IDENTITY_MISMATCH')


def test_a_response_file_answering_another_request_is_not_reused(tmp_path):
    sent = []
    call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent)
    resp = tmp_path / 'calls' / 'A07_k_a1.response.json'
    rec = json.load(open(resp)); rec['identity']['effort'] = 'low'; G.write_private(str(resp), rec)
    with pytest.raises(G.Blocked, match='CHECKPOINT_RESPONSE_IDENTITY_MISMATCH'):
        call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent)
    assert len(sent) == 1


def test_an_interrupted_call_is_not_resent_automatically_and_retry_sends_it_once(tmp_path):
    sent = []
    with pytest.raises(KeyboardInterrupt):
        call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent, fail=KeyboardInterrupt())
    assert (tmp_path / 'calls' / 'A07_k_a1.inflight.json').exists()
    with pytest.raises(G.Blocked, match='INTERRUPTED_CALL_NOT_REPEATED'):
        call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent)
    assert len(sent) == 1
    # retry with a DIFFERENT request under the same key is still blocked
    with pytest.raises(G.Blocked, match='CHECKPOINT_IDENTITY_MISMATCH'):
        call(G.Guard(str(tmp_path), 8, 0.2, retry=True), 'A07_k_a1', body(effort='medium'), sent)
    call(G.Guard(str(tmp_path), 8, 0.2, retry=True), 'A07_k_a1', body(), sent)
    assert len(sent) == 2 and not (tmp_path / 'calls' / 'A07_k_a1.inflight.json').exists()
    call(G.Guard(str(tmp_path), 8, 0.2, retry=True), 'A07_k_a1', body(), sent)
    assert len(sent) == 2, 'once finished it is reused, not re-sent'


def test_errors_are_not_repeated_and_caps_are_checked_before_the_call(tmp_path):
    sent = []
    with pytest.raises(P.ProviderUnavailable):
        call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent, fail=P.ProviderUnavailable('HTTP_500'))
    with pytest.raises(G.Blocked, match='ERROR_RECORDED_NOT_REPEATED'):
        call(G.Guard(str(tmp_path), 8, 0.2), 'A07_k_a1', body(), sent)
    g = G.Guard(str(tmp_path / 'cap'), max_calls=1, max_usd=0.2)
    call(g, 'k1', body(), sent)
    with pytest.raises(G.Blocked, match='RUN_CAP'):
        call(g, 'k2', body(effort='medium'), sent)
    g = G.Guard(str(tmp_path / 'usd'), max_calls=8, max_usd=0.005)
    with pytest.raises(G.Blocked, match='RUN_CAP'):
        call(g, 'k1', body(), sent)
    assert len(sent) == 2


def test_files_are_private_and_a_loose_existing_folder_is_refused(tmp_path):
    old = os.umask(0o022)
    try:
        run = tmp_path / 'run'
        call(G.Guard(str(G.secure_dir(str(run))), 8, 0.2), 'A07_k_a1', body(), [])
        modes = {p.name: stat.S_IMODE(p.stat().st_mode) for p in [run, run / 'calls', *run.rglob('*')]}
        assert all(m == 0o700 for n, m in modes.items() if (run / n).is_dir() or n in ('run', 'calls')), modes
        assert all(m == 0o600 for p, m in ((p, stat.S_IMODE(p.stat().st_mode)) for p in run.rglob('*') if p.is_file())), modes
        G.check_private_tree(str(run))
        os.chmod(run / 'calls' / 'A07_k_a1.request.json', 0o644)
        with pytest.raises(G.Blocked, match='RUN_DIR_NOT_PRIVATE'):
            G.check_private_tree(str(run))
    finally:
        os.umask(old)


def test_credentials_are_never_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-unit-test-value')
    with pytest.raises(G.Blocked, match='SECRET_LIKE'):
        call(G.Guard(str(tmp_path), 8, 0.2), 'k', body(extra=dict(note='sk-unit-test-value')), [])
    with pytest.raises(G.Blocked, match='SECRET_LIKE'):
        G.assert_no_secret(dict(headers={'Authorization': 'Bearer sk-x'}))
    assert not (tmp_path / 'calls' / 'k.request.json').exists()


def test_request_diff_accepts_only_the_intended_fields():
    a = body(); b = body(personal=dict(citable_fact_ids=['F1'], evidence_records=[dict(fact_ids=['F1'], summary='a')]))
    assert RD.compare(a, b, ('A', 'B'))['verdict'] == 'ONLY_INTENDED_DIFFERENCES'
    assert RD.compare(b, body(effort='medium', personal=json.loads(b['input'][1]['content'])['personal']), ('B', 'C'))['verdict'] == 'ONLY_INTENDED_DIFFERENCES'
    d = body(system='지시\n응답 작성:\n짧게', personal=json.loads(b['input'][1]['content'])['personal'], schema={'type': 'object', 'properties': {'y': {'type': 'string'}}})
    res = RD.compare(b, d, ('B', 'D'))
    assert res['verdict'] == 'ONLY_INTENDED_DIFFERENCES' and 'input[0].output_contract' in [x['path'] for x in res['differences']]
    # unintended differences are caught: another block, the instructions, a dropped key, a message split
    assert RD.compare(a, body(extra=dict(state=1)), ('A', 'B'))['unexpected']
    assert RD.compare(b, body(system='다른 지시\n응답 작성:\n짧게', personal=json.loads(b['input'][1]['content'])['personal']), ('B', 'D'))['unexpected']
    shape = RD.compare(a, body(personal=dict(citable_fact_ids=['F1'])), ('A', 'B'))
    assert shape['verdict'] == 'UNINTENDED_DIFFERENCES' and shape['structure_differences']
    two = dict(a, input=[a['input'][0], dict(role='user', content=json.dumps(dict(json.loads(a['input'][1]['content']), **json.loads(a['input'][2]['content']))))])
    assert RD.compare(two, a, ('A', 'B'))['verdict'] == 'UNINTENDED_DIFFERENCES'


def test_batch_guard_caps_pools_and_keeps_unsettled_reservations(tmp_path):
    import threading
    d = str(tmp_path / 'batch')
    G.BatchGuard.init(d, max_calls=5, max_usd=0.05, pools=dict(A=3, B=3))
    a, b = G.BatchGuard(d, 'A'), G.BatchGuard(d, 'B')
    a.reserve('j1/k1', 0.01); a.reserve('j1/k2', 0.01); a.reserve('j1/k3', 0.01)
    with pytest.raises(G.Blocked, match='BATCH_CAP'): a.reserve('j1/k4', 0.001)      # pool A full
    with pytest.raises(G.Blocked, match='BATCH_KEY_ALREADY_RESERVED'): b.reserve('j1/k1', 0.001)
    b.reserve('j2/k1', 0.015)
    with pytest.raises(G.Blocked, match='BATCH_CAP'): b.reserve('j2/k2', 0.01)       # dollars: 0.045 + 0.01 > 0.05
    a.settle('j1/k1', 0.002, 'DONE'); a.settle('j1/k2', None, 'ERROR')               # unknown charge keeps the ceiling
    st = json.load(open(os.path.join(d, 'batch_guard.json')))
    assert st['calls'] == 4 and abs(st['reserved_usd'] - (0.002 + 0.01 + 0.01 + 0.015)) < 1e-9
    assert G.BatchGuard.init(d, 99, 99, dict(A=99))['max_calls'] == 5, 'a restart never resets the counts'
    # parallel reservations never overshoot the cap
    d2 = str(tmp_path / 'batch2'); G.BatchGuard.init(d2, max_calls=20, max_usd=1.0, pools=dict(A=20))
    ok = []
    def worker(i):
        g = G.BatchGuard(d2, 'A')
        for k in range(10):
            try: g.reserve('w%d/%d' % (i, k), 0.001); ok.append(1)
            except G.Blocked: pass
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(ok) == 20 and json.load(open(os.path.join(d2, 'batch_guard.json')))['calls'] == 20


def test_guard_uses_batch_cap_before_sending(tmp_path, monkeypatch):
    d = str(tmp_path / 'batch'); G.BatchGuard.init(d, max_calls=1, max_usd=1.0, pools=dict(A=1))
    monkeypatch.setenv('HL_BATCH_DIR', d); monkeypatch.setenv('HL_BATCH_POOL', 'A'); monkeypatch.setenv('HL_BATCH_JOB', 'job1')
    g = G.Guard(str(tmp_path / 'run'), 10, 1.0, mode='live'); sent = []
    def send(capture): sent.append(1); return {'x': 1}, dict(charged_upper_usd=0.003)
    g.call('k1', 'P', 'X', {'model': 'm'}, 'sha1', 'R', 0.01, send)
    with pytest.raises(G.Blocked, match='BATCH_CAP'): g.call('k2', 'P', 'X', {'model': 'm'}, 'sha2', 'R', 0.01, send)
    assert sent == [1]
    st = json.load(open(os.path.join(d, 'batch_guard.json')))
    assert st['entries']['job1/k1']['charged'] == 0.003 and st['calls'] == 1
