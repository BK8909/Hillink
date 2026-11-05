"""Source-reconciled local display corrections; never an engine projection.

Only the local reviewer endpoint calls this loader. The runtime manifest stays outside source control; bundled private review
sources stay outside static serving. A changed source
invalidates its correction instead of silently approving new content.
"""
import hashlib
import json
import os
from pathlib import Path

DISPLAY_STATUSES = {'SOURCE_RECONCILED_DISPLAY_ONLY', 'EVIDENCE_LIMITED_DISPLAY_ONLY'}


def load():
    configured = os.environ.get('HILLINK_PROFILE_DISPLAY_REVIEW')
    if not configured:
        return {'customers': {}, 'status': 'NOT_CONFIGURED'}
    try:
        manifest = json.loads(Path(configured).read_text())
        customers = {}
        for pid, row in manifest['customers'].items():
            if row.get('status') not in DISPLAY_STATUSES:
                continue
            anchors = row.get('source_anchors', [])
            if not anchors or any(a.get('customer_id') != pid or hashlib.sha256(Path(a['path']).read_bytes()).hexdigest() != a['sha256'] for a in anchors):
                continue
            changes = row.get('changes', {})
            allowed = {'list_line', 'signature'}
            if row['status'] == 'SOURCE_RECONCILED_DISPLAY_ONLY':
                allowed.add('fact_summaries')
            if set(changes) - allowed:
                continue
            if any(not isinstance(v, str) or len(v) > 600 for k, v in changes.items() if k != 'fact_summaries'):
                continue
            facts = changes.get('fact_summaries', {})
            if not isinstance(facts, dict) or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 600 for k, v in facts.items()):
                continue
            redundant = row.get('redundant_support_texts', [])
            if not isinstance(redundant, list) or any(not isinstance(t, str) or len(t) > 600 for t in redundant):
                continue
            customers[pid] = dict(changes=changes, status=row['status'], fact_ids=row['fact_ids'],
                redundant_support_texts=redundant, post_ids=row.get('post_ids', []), review_scope=row.get('review_scope', ''), hold_reason=row.get('hold_reason', ''),
                engine_changed=False, semantic_approval=False, thumbnail_approval=False)
        return {'customers': customers, 'status': 'LOCAL_DISPLAY_REVIEW'}
    except (OSError, ValueError, KeyError, TypeError):
        return {'customers': {}, 'status': 'REVIEW_MANIFEST_HOLD'}
