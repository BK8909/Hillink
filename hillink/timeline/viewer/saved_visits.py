"""Manifest-addressed submitted visits. Loading is playback, never a new model call."""
import gzip, hashlib, io, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'handover/data'
MAX_BYTES=192*1024*1024

def manifest():
    return json.loads((DATA/'bundle.json').read_text())

def private_runs():
    """Recorded improved-policy visits kept outside Git (HILLINK_PRIVATE_REPLAY_DIR/index.json, written by
    tools/build_private_replay.py): conditions only. Executing one replays its recorded LIVE answers through the engine."""
    import os
    root=os.environ.get('HILLINK_PRIVATE_REPLAY_DIR')
    if not root or not (Path(root)/'index.json').is_file():return []
    runs=json.loads((Path(root)/'index.json').read_text()).get('runs') or []
    return [r for r in runs if isinstance(r,dict) and r.get('tag') and r.get('customer') and isinstance(r.get('request'),dict)
            and r['request'].get('personas')==[r['customer']]]

def private_run(tag):
    row=next((r for r in private_runs() if r['tag']==tag),None)
    if row is None:raise ValueError('UNKNOWN_SAVED_VISIT')
    return dict(request=row['request'],provenance=dict(tag=tag,display_mode='RECORDED_LIVE_ANSWERS_REPLAY',recorded=row.get('recorded'),current_paid_calls=0))

def index():
    # 2026-11-09 user decision: the product lists improved-policy saved visits only. The V16 records stay in the
    # bundle for research regression (load/payload/cohort below) but are no longer offered or replayed in the product.
    return dict(runs=[dict(tag=r['tag'],customer=r['customer'],duration=r.get('duration'),recorded=r.get('recorded'),private=True) for r in private_runs()],
        retired_v16=len(manifest()['v16_runs']),display_mode='RECORDED_VISIT_PLAYBACK',current_paid_calls=0,human_approval=False)

def _read(relative,spec):
    row=next((r for r in spec['supplemental_files'] if r['path']==relative),None)
    path=(DATA/relative).resolve()
    if not row or DATA.resolve() not in path.parents or path.is_symlink():
        raise ValueError('EVIDENCE_NOT_IN_MANIFEST')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('EVIDENCE_SHA_MISMATCH')
    with gzip.GzipFile(fileobj=io.BytesIO(raw),mode='rb') as stream:
        raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('EVIDENCE_TOO_LARGE')
    return json.loads(raw)

def payload(tag):
    spec=manifest();row=next((r for r in spec['v16_runs'] if r['tag']==tag),None)
    if row is None:raise ValueError('UNKNOWN_SAVED_VISIT')
    data=_read(row['files']['visit'],spec)
    review=_read(row['files']['review'],spec) if 'review' in row['files'] else None
    lineage=_read(row['files']['lineage'],spec) if 'lineage' in row['files'] else []
    if data['head']!=row['source_head'] or data['request']['personas']!=[row['customer']]:
        raise ValueError('EVIDENCE_IDENTITY_MISMATCH')
    return data,row,review,lineage

def load(tag):
    data,row,review,lineage=payload(tag)
    # Presentation metadata is separate from immutable selected plans and receipts.
    flow=data['result'];pid=row['customer']
    flow['plans'][pid]['recorded_review']=dict(tag=tag,display_mode='RECORDED_VISIT_PLAYBACK',
        configuration=data['configuration'],
        source_head=data['head'],model=row['model'],current_paid_calls=0,human_approval=False,
        review=review,lineage=lineage,contract_status=row['contract_status'])
    return dict(result=flow,ledger=flow.get('ledger'),request=data['request'],engine=flow.get('engine'),
        applied=flow.get('levers_applied',[]),skipped=flow.get('levers_not_applied',[]),
        notices=flow.get('notices',[]),stories=flow.get('stories'),intervention=flow.get('intervention'),
        provenance=flow['plans'][pid]['recorded_review'])

def cohort():
    from agent_cohort_evaluation import compare
    tags={r['tag'] for r in manifest()['v16_runs']}
    pairs=[]
    for pid in ('A01','A07','A26'):
        treatment=pid+'-v16-discount20'
        if treatment+'-recovery' in tags:treatment+='-recovery'
        pairs.append((payload(pid+'-v16-baseline')[0],payload(treatment)[0]))
    return compare(pairs,sku_id='HC-MENU-132',discount_percent=20,venue_id='THE_BUFFET')
