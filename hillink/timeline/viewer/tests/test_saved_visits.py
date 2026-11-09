"""Submitted evidence stays immutable and cannot grant semantic approval."""
import copy,hashlib,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import saved_visits as S
import strategy_agent_service as J

def test_product_index_lists_improved_records_only():
    idx=S.index();assert idx['retired_v16']==38 and not any('-v16-' in r['tag'] for r in idx['runs'])


def test_submitted_v16_coverage_and_immutable_decisions():
    rows=[{k:v for k,v in r.items() if k not in ('files','replay_entries')} for r in S.manifest()['v16_runs']];assert len(rows)==38
    completed=[r for r in rows if r['contract_status']!='EXECUTION_INCOMPLETE_HOLD']
    assert len(completed)==36 and len({r['customer'] for r in completed})==28
    decisions=0
    for row in completed:
        data,_,review,lineage=S.payload(row['tag']);pid=row['customer']
        before=copy.deepcopy(data['result']['plans'][pid]['autonomous_decisions'])
        opened=S.load(row['tag'])
        assert opened['result']['plans'][pid]['autonomous_decisions']==before
        assert not opened['provenance']['human_approval'] and opened['provenance']['current_paid_calls']==0
        for key in ('receipts_equal_L4_L3_L2_L1','day_totals_equal_visit_total','room_nights_equal_duration','date_rows_unique'):
            assert opened['ledger']['checks'][key] is True
        assert review['review']['human_approval'] is False
        decisions+=len(before)
    assert decisions==312

def test_unknown_tags_are_not_file_paths():
    for tag in ('../README','/etc/passwd','A02-v16-baseline.private.json.gz',''):
        with pytest.raises(ValueError,match='UNKNOWN_SAVED_VISIT'):S.load(tag)

def test_saved_cohort_preserves_exploratory_scope_and_trace_holds():
    result=S.cohort()
    assert result['paired_customers']==3 and result['status']=='EXPLORATORY_PAIRED_SIMULATION'
    assert result['aggregate_delta']['hotel_paid_krw']==290000
    assert result['aggregate_delta']['target_sku_selected']==0
    assert not result['human_semantic_approval'] and result['causal_effect']=='NOT_ESTABLISHED'
    wrapped=S.load('A02-v16-booked-event')
    review=J.evidence_review(wrapped['result'],'A02')
    assert review['trace_holds'] and not review['automatic_strategy_approval']

def test_original_receipts_match_accepted_model_plans():
    spec=S.manifest()
    for row in spec['v16_runs']:
        data,_,_,_=S.payload(row['tag'])
        entries=row['replay_entries'];by_hash={}
        for e in entries:
            receipt=S._read(e['path'],spec)
            assert receipt['origin']=='LIVE_RESPONSES' and receipt['input_sha256']==e['input_sha256']
            by_hash.setdefault(e['input_sha256'],[]).append(receipt)
        for plan in data['result'].get('plans',{}).values():
            for d in plan.get('autonomous_decisions',[]):
                for a in d.get('attempts',[]):
                    t=a.get('provider',{})
                    if t.get('execution') not in ('LIVE_RESPONSES','CACHE_REPLAY'):continue
                    assert any(r['answer']==a['answer'] and r['trace']['response_id']==t['response_id'] for r in by_hash[t['input_sha256']])

def test_independent_review_preserves_original_context_and_provider_answer():
    spec=S.manifest()
    for row in spec['v16_runs']:
        if 'review' not in row['files']:continue
        review=S._read(row['files']['review'],spec)['review']
        context=S._read(row['files']['review_context'],spec)
        receipt=S._read(row['files']['review_receipt'],spec)
        assert receipt['origin']=='LIVE_RESPONSES'
        assert context==receipt['audit_input']['context']['context']
        assert all(review[k]==v for k,v in receipt['answer'].items())
        assert not review['human_approval']
