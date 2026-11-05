import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import profile_display_review as R

def test_private_display_does_not_grant_engine_or_thumbnail_approval(tmp_path,monkeypatch):
 source=tmp_path/'source';source.write_text('synthetic approved display source')
 row=dict(status='SOURCE_RECONCILED_DISPLAY_ONLY',fact_ids=['X-F1'],source_anchors=[dict(customer_id='X',path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())],changes={'fact_summaries':{'X-F1':'source-reconciled display'}})
 file=tmp_path/'review';file.write_text(json.dumps({'customers':{'X':row,'WH-00265':row,'WH-00392':row}}));monkeypatch.setenv('HILLINK_PROFILE_DISPLAY_REVIEW',str(file))
 out=R.load();assert set(out['customers'])=={'X'}
 assert not out['customers']['X']['engine_changed'] and not out['customers']['X']['semantic_approval']
 assert 'source_anchors' not in str(out)
 source.write_text('changed source');assert R.load()['customers']=={}

def test_unsupported_fields_cannot_change_profile_or_engine(tmp_path,monkeypatch):
 source=tmp_path/'source';source.write_text('source')
 row=dict(status='SOURCE_RECONCILED_DISPLAY_ONLY',fact_ids=[],source_anchors=[dict(customer_id='X',path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())],changes={'engine':{'weights':'changed'}})
 file=tmp_path/'review';file.write_text(json.dumps({'customers':{'X':row}}));monkeypatch.setenv('HILLINK_PROFILE_DISPLAY_REVIEW',str(file))
 assert R.load()['customers']=={}

def test_source_bound_customer_is_not_permanently_hidden(tmp_path,monkeypatch):
 source=tmp_path/'source';source.write_text('source-confirmed visit')
 row=dict(status='SOURCE_RECONCILED_DISPLAY_ONLY',fact_ids=[],source_anchors=[dict(customer_id='WH-00265',path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())],changes={'list_line':'observed visit','signature':'observed choice'})
 file=tmp_path/'review';file.write_text(json.dumps({'customers':{'WH-00265':row,'WH-00392':row}}));monkeypatch.setenv('HILLINK_PROFILE_DISPLAY_REVIEW',str(file))
 assert set(R.load()['customers'])=={'WH-00265'}

def test_limited_evidence_cannot_correct_fact_text(tmp_path,monkeypatch):
 source=tmp_path/'source';source.write_text('existing projection only')
 row=dict(status='EVIDENCE_LIMITED_DISPLAY_ONLY',fact_ids=[],source_anchors=[dict(customer_id='X',path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())],changes={'fact_summaries':{'X-F1':'unverified correction'}})
 file=tmp_path/'review';file.write_text(json.dumps({'customers':{'X':row}}));monkeypatch.setenv('HILLINK_PROFILE_DISPLAY_REVIEW',str(file))
 assert R.load()['customers']=={}
 row['changes']={'list_line':'existing summary, original source pending','signature':'choice reason not yet verified'}
 file.write_text(json.dumps({'customers':{'X':row}}))
 assert R.load()['customers']['X']['status']=='EVIDENCE_LIMITED_DISPLAY_ONLY'
