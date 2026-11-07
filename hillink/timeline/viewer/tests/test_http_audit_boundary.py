"""Real HTTP boundary regressions. Synthetic files only; no provider calls."""
import http.client
import json
import socket
import sys
import threading
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import http_boundary as B
import execution_limits as E
from bounded_records import BoundedRecords
from strategy_agent_service import Jobs

@pytest.fixture
def server(tmp_path,monkeypatch):
    cache=tmp_path/'cache';cache.mkdir()
    (cache/'good.json').write_text('{"ok":true,"offsets":[]}')
    (tmp_path/'outside.json').write_text('{"secret":"SENTINEL"}')
    monkeypatch.setattr(app,'CACHE',cache)
    monkeypatch.setattr(app,'DEPLOY','local')
    monkeypatch.setattr(app,'REVIEWER_LOCAL',True)
    srv=B.LocalHTTPServer(('127.0.0.1',0),app.H)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    def call(path,body=None,headers=None,method=None):
        c=http.client.HTTPConnection('127.0.0.1',srv.server_port,timeout=3)
        c.request(method or ('POST' if body is not None else 'GET'),path,body,headers or {})
        r=c.getresponse();result=(r.status,r.read());c.close();return result
    yield call,cache,srv
    srv.shutdown();srv.server_close();thread.join()

@pytest.mark.parametrize('route',['result','status','band','flow','qopts','query','guest','l5.csv'])
def test_all_cache_routes_reject_path_inputs(server,route):
    call,cache,_=server
    keys=['../outside',str(cache.parent/'outside'),'%2e%2e%2foutside','%252e%252e%252foutside','a\\b','a\x00','..','x/y','a'*221]
    for key in keys:
        status,data=call('/api/day/'+route+'?key='+quote(key,safe='%'))
        assert status==400 and b'SENTINEL' not in data
    (cache/'linked.json').symlink_to(cache.parent/'outside.json')
    assert call('/api/day/'+route+'?key=linked')[0]==403


def test_normal_cache_and_public_privacy(server,monkeypatch):
    call,_,_=server
    assert json.loads(call('/api/day/result?key=good')[1])=={'ok':True}
    monkeypatch.setattr(app,'DEPLOY','public')
    for route in ['result','status','band','flow','qopts','query','guest','l5.csv','list']:
        assert call('/api/day/'+route+'?key=good')[0]==403
    for path in ['/api/bands','/api/observed-payments','/local-photo/example.jpg']:
        assert call(path)[0]==403
    assert call('/')[0]==200


def test_host_origin_and_reviewer_get_post(server):
    call,_,srv=server
    for path in ['/api/access','/api/library/links','/api/visit']:
        for headers in [{'Host':'evil.invalid'},{'Origin':'http://evil.invalid'},{'Origin':'null'},{'Sec-Fetch-Site':'cross-site'},{'Host':'localhost:1'}]:
            assert call(path,headers=headers)[0]==403
            assert call(path,b'{}',{**headers,'Content-Type':'application/json'})[0]==403
    assert call('/api/access')[0]==200
    assert call('/api/access',headers={'Host':f'localhost:{srv.server_port}','Origin':f'http://localhost:{srv.server_port}'})[0]==200


def test_saved_evidence_requires_local_review_and_manifest_tag(server,monkeypatch):
    call,_,_=server
    assert call('/api/saved-visits')[0]==200
    assert call('/api/saved-visits/run?tag=../README')[0]==400
    assert call('/api/saved-visits',headers={'Origin':'https://evil.invalid'})[0]==403
    monkeypatch.setattr(app,'DEPLOY','public')
    for path in ('/api/saved-visits','/api/saved-visits/run?tag=A02-v16-baseline','/api/saved-visits/cohort'):
        assert call(path)[0]==403


def test_invalid_bodies_and_no_execution(server):
    call,_,_=server
    with patch.object(app,'completed_visit',side_effect=AssertionError('must not execute')):
        assert call('/api/visit',b'{',{'Content-Type':'application/json'})[0]==400
        assert call('/api/visit',b'[]',{'Content-Type':'application/json'})[0]==400
        assert call('/api/visit',b'{}',{'Content-Type':'text/plain'})[0]==415
        assert call('/api/visit',b'{}',{'Content-Type':'application/json','Content-Length':str(B.MAX_BODY+1)})[0]==413
        assert call('/api/visit',b'{}',{'Content-Type':'application/json','Transfer-Encoding':'chunked'})[0]==400


def test_duplicate_negative_lengths_and_incomplete_body(server):
    _,_,srv=server
    for length in ['Content-Length: -1','Content-Length: 2\r\nContent-Length: 2','Content-Length: x']:
        with socket.create_connection(('127.0.0.1',srv.server_port),timeout=3) as c:
            c.sendall((f'POST /api/visit HTTP/1.0\r\nHost: localhost:{srv.server_port}\r\nContent-Type: application/json\r\n{length}\r\n\r\n'+'{}').encode())
            assert b' 400 ' in c.recv(4096)
    with socket.create_connection(('127.0.0.1',srv.server_port),timeout=3) as c:
        c.sendall(f'POST /api/visit HTTP/1.0\r\nHost: localhost:{srv.server_port}\r\nContent-Type: application/json\r\nContent-Length: 10\r\n\r\n{{}}'.encode());c.shutdown(socket.SHUT_WR)
        assert b' 400 ' in c.recv(4096)


def test_shared_capacity_nested_release_after_failure(monkeypatch):
    monkeypatch.setattr(E,'_LIMIT',threading.BoundedSemaphore(1))
    with E.slot():
        with E.slot():pass
        result=[]
        def compete():
            try:
                with E.slot():result.append('BAD')
            except E.Busy:result.append('BUSY')
        t=threading.Thread(target=compete);t.start();t.join();assert result==['BUSY']
    with pytest.raises(RuntimeError):
        with E.slot():raise RuntimeError()
    with E.slot():pass


def test_queue_cancel_failure_and_capacity():
    jobs=Jobs();started=threading.Event();release=threading.Event();calls=[]
    def first():started.set();release.wait(3);return {'ok':True}
    a=jobs.submit('a',[],first);assert started.wait(2)
    b=jobs.submit('b',[],lambda:calls.append('cancelled'))
    jobs.submit('c',[],lambda:None);jobs.submit('d',[],lambda:None)
    with pytest.raises(ValueError,match='FULL'):jobs.submit('e',[],lambda:None)
    assert jobs.cancel(b['job_id'])['status']=='CANCELLED'
    with pytest.raises(ValueError,match='CANNOT'):jobs.cancel(a['job_id'])
    release.set();jobs.worker.shutdown();assert calls==[]
    assert jobs.get(a['job_id'])['status']=='DONE'


def test_byte_bounds_are_atomic():
    records=BoundedRecords(2,50);records['a']={'v':'a'};records['b']={'v':'b'}
    with pytest.raises(ValueError,match='TOO_LARGE'):records['a']={'v':'x'*100}
    assert records['a']=={'v':'a'}
    records['c']={'v':'c'};assert 'a' not in records and records.bytes<=50
    records.clear();assert records.bytes==0


def test_timeout_kills_child_group_without_late_result(tmp_path):
    import subprocess,time
    marker=tmp_path/'late.txt'
    child=f'import time,pathlib;time.sleep(0.6);pathlib.Path({str(marker)!r}).write_text("late")'
    parent=f'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",{child!r}]);time.sleep(20)'
    with pytest.raises(subprocess.TimeoutExpired):
        E.run([sys.executable,'-c',parent],capture_output=True,text=True,timeout=.2)
    time.sleep(.7)
    assert not marker.exists()
    assert E.run([sys.executable,'-c','print("recovered")'],capture_output=True,text=True).stdout.strip()=='recovered'


def test_job_retention_and_retry_after_failure():
    jobs=Jobs()
    first=None
    for i in range(34):
        done=threading.Event()
        row=jobs.submit(str(i),[],lambda:done.set())
        assert done.wait(2)
        # Wait for serialized terminal state, not only callable completion.
        import time
        for _ in range(100):
            if jobs.get(row['job_id'])['status']=='DONE':break
            time.sleep(.001)
        first=first or row['job_id']
    jobs.worker.shutdown()
    assert len(jobs.rows)<=32 and len(jobs.futures)<=32
    with pytest.raises(ValueError,match='EXPIRED'):jobs.get(first)


def test_failed_job_can_retry_without_reusing_failed_result():
    import time
    jobs=Jobs()
    def fail():raise RuntimeError('PRIVATE_PATH')
    old=jobs.submit('retry',[],fail)
    for _ in range(200):
        if jobs.get(old['job_id'])['status']=='ERROR':break
        time.sleep(.001)
    new=jobs.submit('retry',[],lambda:{'ok':True})
    jobs.worker.shutdown()
    assert old['job_id']!=new['job_id']
    assert jobs.get(new['job_id'])['status']=='DONE'
    assert 'PRIVATE_PATH' not in str(jobs.get(old['job_id']))


def test_forced_recompute_reuses_only_active_jobs():
    import time
    jobs=Jobs()
    first=jobs.submit('day',[],lambda:{'generation':1})
    for _ in range(200):
        if jobs.get(first['job_id'])['status']=='DONE':break
        time.sleep(.001)
    second=jobs.submit('day',[],lambda:{'generation':2},reuse_completed=False)
    jobs.worker.shutdown()
    assert first['job_id']!=second['job_id']
    assert jobs.get(second['job_id'])['result']=={'generation':2}


@pytest.mark.parametrize('suffix,prefix',[('.progress.json',''),('.guests.jsonl',''),('.guests.jsonl.gz',''),('.cap.pkl',''),('.l5.csv',''),('.json','flow_'),('.json','band_')])
def test_every_cache_companion_link_rejected_before_reader(server,suffix,prefix):
    call,cache,_=server
    (cache/(prefix+'good'+suffix)).symlink_to(cache.parent/'outside.json')
    assert call('/api/day/result?key=good')[0]==403
    assert call('/api/guest',json.dumps({'crowd':'good'}).encode(),{'Content-Type':'application/json'})[0]==403


def test_public_raw_static_data_blocked(server,monkeypatch):
    call,_,_=server;monkeypatch.setattr(app,'DEPLOY','public')
    for name in ('llm_pilot.json','strategy_santa_ab.json','research_index.json','persona_library.local.json','demo_story/flow_fixture_v1.json'):
        assert call('/static/'+name)[0]==404
    assert call('/static/app.js')[0]==200


def test_completed_visit_size_limit_prevents_registration(monkeypatch):
    monkeypatch.setattr(E, 'MAX_VISIT_RESULT_BYTES', 128)
    monkeypatch.setattr(app, 'visit_run', lambda body: {'plans': {'synthetic': 'x' * 256}})
    with patch.object(app.receipts, 'register_visit', side_effect=AssertionError('oversized result must not be registered')):
        with pytest.raises(B.RequestError, match='RESULT_TOO_LARGE'):
            app.completed_visit({'personas': ['synthetic']})


def test_sync_visit_reuses_checked_response_without_losing_ledger(monkeypatch):
    original = {'plans': {'synthetic': {'decisions': ['original']}}, 'profile_sha': 'private'}
    monkeypatch.setattr(app, 'visit_run', lambda body: original)
    monkeypatch.setattr(app.receipts, 'register_visit', lambda flow, body: {'run_id': 'same-run', 'total': 17})
    with patch.object(app.agent_jobs, 'remember') as remember, patch.object(app.wire_json, 'serialize', wraps=app.wire_json.serialize) as encode:
        status, response = app.completed_visit({'personas': ['synthetic']}, prepare_response=True)
        assert status == 200
        body = json.loads(response)
        # 2026-11-07: the operator aggregate is attached after the ledger (a new field, never replacing it)
        assert body.pop('operating_summary')['schema'] == 'HILLINK_OPERATING_SUMMARY_V1'
        assert body == {'plans': {'synthetic': {'decisions': ['original']}}, 'ledger': {'run_id': 'same-run', 'total': 17}}
        assert encode.call_count == 2  # pre-registration boundary + final HTTP bytes
        remember.assert_called_once()


@pytest.mark.parametrize('code,status', [('E_FLOW_INPUT_MISSING', 409), ('OTHER', 400)])
def test_prepared_visit_keeps_error_status(monkeypatch, code, status):
    monkeypatch.setattr(app, 'visit_run', lambda body: {'error': 'missing', 'code': code})
    with patch.object(app.receipts, 'register_visit', side_effect=AssertionError('errors must not register')):
        actual, response = app.completed_visit({}, prepare_response=True)
    assert actual == status
    assert json.loads(response)['code'] == code
