"""Explicit operator-approved amendment of an existing cumulative journal.

Never creates/resets a journal, settles calls, or raises the USD20 ceiling.
The expected digest prevents applying approval to a different/concurrently used
journal. A private byte-for-byte backup and in-journal approval trail are required.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time


def amend(path, backup, expected_sha256, max_calls, approval_reference):
    path, backup = Path(path), Path(backup)
    if (not approval_reference.strip() or type(max_calls) is not int
            or not 400 < max_calls <= 2500):
        raise ValueError('APPROVED_CALL_LIMIT_REQUIRED')
    with path.open('r+', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        original = stream.read()
        digest = hashlib.sha256(original.encode()).hexdigest()
        if digest != expected_sha256:
            raise ValueError('JOURNAL_CHANGED_REVIEW_BEFORE_AMENDMENT')
        state = json.loads(original)
        if state.get('max_usd') != 20 or not isinstance(state.get('requests'), list):
            raise ValueError('EXISTING_USD20_JOURNAL_REQUIRED')
        if any(x.get('state') == 'RESERVED' for x in state['requests']):
            raise ValueError('ACTIVE_OR_UNRESOLVED_REQUEST_REVIEW_REQUIRED')
        previous_limit = max(state['max_calls'], state.get('approved_global_max_calls', 0))
        if max_calls <= previous_limit or len(state['requests']) > max_calls:
            raise ValueError('INVALID_CALL_EXTENSION')
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as saved:
            saved.write(original); saved.flush(); os.fsync(saved.fileno())
        history_digest = hashlib.sha256(json.dumps(state['requests'], sort_keys=True).encode()).hexdigest()
        state.setdefault('limit_amendments', []).append(dict(at=time.time(),
            previous_max_calls=previous_limit, approved_max_calls=max_calls,
            unchanged_max_usd=20, approval_reference=approval_reference,
            prior_journal_sha256=digest, prior_requests_sha256=history_digest,
            preserved_request_count=len(state['requests'])))
        state['max_calls'] = max_calls
        state['approved_global_max_calls'] = max_calls
        stream.seek(0); json.dump(state, stream, ensure_ascii=False, allow_nan=False)
        stream.truncate(); stream.flush(); os.fsync(stream.fileno())
        return dict(max_calls=max_calls, max_usd=20, preserved_calls=len(state['requests']),
                    prior_sha256=digest, requests_sha256=history_digest)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal', required=True); p.add_argument('--backup', required=True)
    p.add_argument('--expected-sha256', required=True); p.add_argument('--max-calls', type=int, required=True)
    p.add_argument('--approval-reference', required=True)
    a = p.parse_args()
    print(json.dumps(amend(a.journal, a.backup, a.expected_sha256, a.max_calls, a.approval_reference)))
