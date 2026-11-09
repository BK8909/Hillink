"""Explicit operator-approved restoration of the shared journal's USD ceiling to the approved US$20.

agent_provider.Budget keeps the journal's max_usd at the LOWEST limit any process has ever used (it never raises it).
A research run that passed a smaller per-stage USD limit therefore lowered the shared ceiling below the approved US$20.
This tool puts it back to exactly 20 -- never above -- only with a user approval reference, the expected journal digest,
a byte-for-byte private backup and an in-journal record. It never creates a journal, removes or settles a request.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

APPROVED_USD = 20


def restore(path, backup, expected_sha256, approval_reference):
    path, backup = Path(path), Path(backup)
    if not approval_reference.strip():
        raise ValueError('APPROVAL_REFERENCE_REQUIRED')
    with path.open('r+', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        original = stream.read()
        digest = hashlib.sha256(original.encode()).hexdigest()
        if digest != expected_sha256:
            raise ValueError('JOURNAL_CHANGED_REVIEW_BEFORE_RESTORATION')
        state = json.loads(original)
        if not isinstance(state.get('requests'), list):
            raise ValueError('EXISTING_JOURNAL_REQUIRED')
        if any(x.get('state') == 'RESERVED' for x in state['requests']):
            raise ValueError('ACTIVE_OR_UNRESOLVED_REQUEST_REVIEW_REQUIRED')
        previous = state.get('max_usd')
        if not isinstance(previous, (int, float)) or not 0 < previous < APPROVED_USD:
            raise ValueError('NOTHING_TO_RESTORE')
        if not any(x.get('unchanged_max_usd') == APPROVED_USD and x.get('approval_reference') for x in state.get('limit_amendments', [])):
            raise ValueError('NO_RECORDED_USD20_APPROVAL')
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as saved:
            saved.write(original); saved.flush(); os.fsync(saved.fileno())
        history = hashlib.sha256(json.dumps(state['requests'], sort_keys=True).encode()).hexdigest()
        state.setdefault('usd_ceiling_restorations', []).append(dict(at=time.time(), previous_max_usd=previous, restored_max_usd=APPROVED_USD,
            approval_reference=approval_reference, prior_journal_sha256=digest, prior_requests_sha256=history,
            preserved_request_count=len(state['requests'])))
        state['max_usd'] = APPROVED_USD
        stream.seek(0); json.dump(state, stream, ensure_ascii=False, allow_nan=False)
        stream.truncate(); stream.flush(); os.fsync(stream.fileno())
        return dict(previous_max_usd=previous, max_usd=APPROVED_USD, preserved_calls=len(state['requests']), prior_sha256=digest)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal', required=True); p.add_argument('--backup', required=True)
    p.add_argument('--expected-sha256', required=True); p.add_argument('--approval-reference', required=True)
    a = p.parse_args()
    print(json.dumps(restore(a.journal, a.backup, a.expected_sha256, a.approval_reference)))
