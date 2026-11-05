"""A running visit must never observe partially restored JSON overlays."""
import concurrent.futures,json,sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from connect_private_data import publish

def test_concurrent_restore_readers_only_see_complete_json(tmp_path):
    target=tmp_path/'profile.json';payloads=[json.dumps({'generation':i,'facts':['source']*10000}).encode() for i in range(4)]
    target.write_bytes(payloads[0]);stop=threading.Event();errors=[];reads=[]
    def reader():
        while not stop.is_set():
            try:
                value=json.loads(target.read_bytes());assert len(value['facts'])==10000
                reads.append(value['generation'])
            except Exception as e:errors.append(type(e).__name__)
    thread=threading.Thread(target=reader);thread.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i:publish(target,payloads[i%4]),range(80)))
    finally:stop.set();thread.join()
    assert reads and not errors and not list(tmp_path.glob('.restore-*'))
