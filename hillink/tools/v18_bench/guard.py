"""V18 bench — per-run call guard, checkpoint identity and private-file permissions.

Pure functions (no engine imports) so they can be tested without running a visit.

Checkpoint files per call, in <run_dir>/calls/:
  <key>.inflight.json  written before the call, removed when it ends
  <key>.request.json   the exact request body and its identity digest
  <key>.response.json  answer, provider trace, raw response body, and the identity it answers
  <key>.error.json     a provider error (the call happened; never re-sent automatically)

Before anything is reused or sent, the CURRENT request body and identity are computed by the
caller and compared with what the checkpoint recorded for that key. A finished call is reused
only when request body, identity, policy, purpose, model, reasoning effort and output limit all
match; any difference blocks the call (no reuse, no automatic call). An interrupted or errored
call is never re-sent unless retry is asked for, and even then only when it is the same request.

Files: the run folder and its sub-folders are 0700, every file is 0600. A folder that already
exists is checked before use and refused if any part of it is readable by group or others.
Credentials never reach these files: the API key lives only in the HTTP header built inside the
provider, and nothing here receives headers.
"""
import fcntl
import json
import os
import stat
import time
from contextlib import contextmanager

DIR_MODE = 0o700
FILE_MODE = 0o600
IDENTITY_FIELDS = ('input_sha256', 'policy', 'purpose', 'request_policy', 'model', 'effort', 'max_output_tokens')


class Blocked(Exception):
    pass


# ---------------------------------------------------------------- permissions
def secure_dir(path):
    os.makedirs(path, mode=DIR_MODE, exist_ok=True)
    os.chmod(path, DIR_MODE)
    return path


def loose_entries(root):
    """Paths under root (root included) that group or others can read, write or enter."""
    bad = []
    if not os.path.exists(root): return bad
    for base, dirs, files in os.walk(root):
        for p in [base] + [os.path.join(base, f) for f in files]:
            mode = stat.S_IMODE(os.lstat(p).st_mode)
            if mode & 0o077: bad.append((p, oct(mode)))
        # do not descend through symlinked folders
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
    return bad


def check_private_tree(root):
    bad = loose_entries(root)
    if bad:
        raise Blocked('RUN_DIR_NOT_PRIVATE: %d path(s) readable by group/others, e.g. %s %s — fix with: chmod -R go-rwx %s'
                      % (len(bad), bad[0][0], bad[0][1], root))


def write_private(path, value):
    """Atomic JSON write with 0600 from creation (no window where the file is world-readable)."""
    tmp = str(path) + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=1, default=str)
    except BaseException:
        try: os.remove(tmp)
        except FileNotFoundError: pass
        raise
    os.chmod(tmp, FILE_MODE)
    os.replace(tmp, path)


def write_private_text(path, text):
    tmp = str(path) + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(text)
    os.chmod(tmp, FILE_MODE)
    os.replace(tmp, path)


def assert_no_secret(value):
    """Refuse to record anything that looks like a credential (defence in depth: none should exist)."""
    text = json.dumps(value, ensure_ascii=False, default=str).lower()
    for marker in ('"authorization"', 'bearer sk-', '"api_key"', '"openai_api_key"'):
        if marker in text: raise Blocked('SECRET_LIKE_FIELD_NOT_RECORDED: %s' % marker.strip('"'))
    if os.environ.get('OPENAI_API_KEY') and os.environ['OPENAI_API_KEY'].lower() in text:
        raise Blocked('SECRET_LIKE_FIELD_NOT_RECORDED: api key value')


# ---------------------------------------------------------------- identity
def identity_of(policy, purpose, payload, input_sha256, request_policy):
    return dict(input_sha256=input_sha256, policy=policy, purpose=purpose, request_policy=request_policy,
                model=payload.get('model'), effort=(payload.get('reasoning') or {}).get('effort'),
                max_output_tokens=payload.get('max_output_tokens'))


def mismatches(current, recorded, payload=None, recorded_body=None):
    out = [k for k in IDENTITY_FIELDS if (recorded or {}).get(k) != current.get(k)]
    if payload is not None and recorded_body is not None and recorded_body != payload: out.append('request_body')
    return out


# ---------------------------------------------------------------- batch-wide cap (many runs, parallel workers)
class BatchGuard:
    """One approval's cap shared by every run of a batch, across parallel processes and restarts.

    State lives in <batch_dir>/batch_guard.json and is changed only under an exclusive lock on
    <batch_dir>/batch_guard.lock. A call reserves its worst-case ceiling BEFORE it is sent (global cap and
    the pool of its experiment); the reservation becomes the provider's charged upper bound when the call
    ends (response or error). A call that never reported back (crash, kill) keeps its full ceiling, so a
    restart can only see less room, never more. Nothing here re-sends anything."""
    def __init__(self, batch_dir, pool):
        self.dir = secure_dir(batch_dir); self.pool = pool
        self.state_path = os.path.join(batch_dir, 'batch_guard.json'); self.lock_path = os.path.join(batch_dir, 'batch_guard.lock')
        if not os.path.exists(self.state_path): raise Blocked('BATCH_GUARD_NOT_INITIALISED: %s' % self.state_path)

    @staticmethod
    def init(batch_dir, max_calls, max_usd, pools):
        """pools: {name: max_calls}. Refuses to overwrite an existing state (a restart keeps the counts)."""
        secure_dir(batch_dir); path = os.path.join(batch_dir, 'batch_guard.json')
        if os.path.exists(path): return json.load(open(path, encoding='utf-8'))
        st = dict(max_calls=max_calls, max_usd=max_usd, pools={k: dict(max_calls=v, calls=0) for k, v in pools.items()},
                  calls=0, reserved_usd=0.0, entries={}, created_at=time.time())
        write_private(path, st); return st

    @contextmanager
    def locked(self):
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, FILE_MODE)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            st = json.load(open(self.state_path, encoding='utf-8'))
            yield st
            write_private(self.state_path, st)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)

    def reserve(self, key, ceiling):
        with self.locked() as st:
            if key in st['entries']: raise Blocked('BATCH_KEY_ALREADY_RESERVED: %s' % key)
            pool = st['pools'].get(self.pool)
            if pool is None: raise Blocked('BATCH_POOL_UNKNOWN: %s' % self.pool)
            if st['calls'] + 1 > st['max_calls'] or pool['calls'] + 1 > pool['max_calls'] or st['reserved_usd'] + ceiling > st['max_usd'] + 1e-12:
                raise Blocked('BATCH_CAP: %d/%d calls (pool %s %d/%d), $%.4f + $%.4f > $%.2f'
                              % (st['calls'], st['max_calls'], self.pool, pool['calls'], pool['max_calls'], st['reserved_usd'], ceiling, st['max_usd']))
            st['calls'] += 1; pool['calls'] += 1; st['reserved_usd'] = round(st['reserved_usd'] + ceiling, 6)
            st['entries'][key] = dict(pool=self.pool, ceiling=ceiling, charged=None, state='RESERVED', at=time.time())

    def settle(self, key, charged, state):
        with self.locked() as st:
            e = st['entries'][key]
            charged = e['ceiling'] if charged is None else float(charged)
            st['reserved_usd'] = round(st['reserved_usd'] - e['ceiling'] + charged, 6)
            e.update(charged=charged, state=state)


def batch_guard():
    d = os.environ.get('HL_BATCH_DIR')
    return BatchGuard(d, os.environ.get('HL_BATCH_POOL', '')) if d else None


class Guard:
    def __init__(self, run_dir, max_calls, max_usd, retry=False, mode='offline'):
        self.run_dir = run_dir; self.max_calls = max_calls; self.max_usd = max_usd; self.retry = retry; self.mode = mode
        self.calls = secure_dir(os.path.join(run_dir, 'calls'))
        self.batch = batch_guard()
        self.batch_prefix = os.environ.get('HL_BATCH_JOB', os.path.basename(os.path.normpath(run_dir)))

    # state
    def state_path(self): return os.path.join(self.run_dir, 'run_state.json')

    def state(self):
        try: return json.load(open(self.state_path(), encoding='utf-8'))
        except FileNotFoundError: return dict(calls_started=0, ceiling_usd=0.0, settled_upper_usd=0.0, reused=0, blocked=[])

    def save(self, st): write_private(self.state_path(), st)

    def path(self, key, kind): return os.path.join(self.calls, '%s.%s.json' % (key, kind))

    def _load(self, key, kind):
        p = self.path(key, kind)
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None

    def _block(self, key, reason, **extra):
        st = self.state(); st['blocked'].append(dict(key=key, reason=reason, **extra)); self.save(st)
        raise Blocked(reason)

    def call(self, key, policy, purpose, payload, input_sha256, request_policy, ceiling, send, step=None):
        """send(capture) performs the call and returns (answer, trace). Nothing is sent or reused until the
        current request has been compared with the checkpoint."""
        current = identity_of(policy, purpose, payload, input_sha256, request_policy)
        req, resp, err, inflight = (self._load(key, k) for k in ('request', 'response', 'error', 'inflight'))
        recorded = req and dict(identity_of(req.get('policy'), req.get('purpose'), req.get('request_body') or {}, req.get('input_sha256'), req.get('request_policy')))
        if req is not None:
            diff = mismatches(current, recorded, payload, req.get('request_body'))
            if diff: self._block(key, 'CHECKPOINT_IDENTITY_MISMATCH: ' + ','.join(diff), recorded=recorded, current=current)
        if resp is not None:
            if req is None: self._block(key, 'CHECKPOINT_RESPONSE_WITHOUT_REQUEST')
            diff = mismatches(current, resp.get('identity'))
            if diff: self._block(key, 'CHECKPOINT_RESPONSE_IDENTITY_MISMATCH: ' + ','.join(diff), recorded=resp.get('identity'), current=current)
            st = self.state(); st['reused'] += 1; self.save(st)
            return resp['answer'], dict(resp['trace'], reused_from_checkpoint=True)
        for name, rec in (('error', err), ('inflight', inflight)):
            if rec is not None and (rec.get('input_sha256') or (rec.get('identity') or {}).get('input_sha256')) != input_sha256:
                self._block(key, 'CHECKPOINT_IDENTITY_MISMATCH: %s.input_sha256' % name, recorded=rec.get('input_sha256'), current=input_sha256)
        if err is not None and not self.retry: self._block(key, 'ERROR_RECORDED_NOT_REPEATED')
        if inflight is not None and not self.retry: self._block(key, 'INTERRUPTED_CALL_NOT_REPEATED')
        st = self.state()
        if st['calls_started'] + 1 > self.max_calls or st['ceiling_usd'] + ceiling > self.max_usd + 1e-12:
            st['blocked'].append(dict(key=key, reason='RUN_CAP', calls_started=st['calls_started'], ceiling_usd=st['ceiling_usd'], next_ceiling=ceiling))
            self.save(st)
            raise Blocked('RUN_CAP: %d/%d calls, worst-case $%.4f + $%.4f > $%.4f' % (st['calls_started'], self.max_calls, st['ceiling_usd'], ceiling, self.max_usd))
        record = dict(key=key, policy=policy, purpose=purpose, input_sha256=input_sha256, request_policy=request_policy,
                      request_body=payload, mode=self.mode, recorded_step=step)
        assert_no_secret(record)
        bkey = '%s/%s' % (self.batch_prefix, key)
        if self.batch is not None:
            try: self.batch.reserve(bkey, ceiling)
            except Blocked as exc:
                st['blocked'].append(dict(key=key, reason=str(exc))); self.save(st); raise
        st['calls_started'] += 1; st['ceiling_usd'] = round(st['ceiling_usd'] + ceiling, 6); self.save(st)
        write_private(self.path(key, 'inflight'), dict(key=key, input_sha256=input_sha256, identity=current, ceiling_usd=ceiling, started_at=time.time(), mode=self.mode))
        write_private(self.path(key, 'request'), record)
        if err is not None: os.replace(self.path(key, 'error'), self.path(key, 'error') + '.%d.prev' % int(time.time()))
        captured = {}
        def capture(stage, value):
            captured[stage] = value
            if stage == 'request':
                captured['provider_identity_matches'] = value['input_sha256'] == input_sha256 and value['request_body'] == payload
        try:
            answer, trace = send(capture)
        except Exception as exc:
            trace = getattr(exc, 'trace', None)
            rec = dict(key=key, input_sha256=input_sha256, identity=current, error=str(exc), trace=trace, raw=captured.get('error'),
                       provider_identity_matches=captured.get('provider_identity_matches'))
            assert_no_secret(rec)
            write_private(self.path(key, 'error'), rec)
            os.remove(self.path(key, 'inflight'))
            st = self.state(); st['settled_upper_usd'] = round(st['settled_upper_usd'] + float((trace or {}).get('charged_upper_usd') or 0), 6); self.save(st)
            if self.batch is not None:
                # a provider-side error is charged as the provider recorded it; an error before any reservation
                # in the shared ledger (no trace) keeps the full ceiling (we cannot prove it was not sent)
                self.batch.settle(bkey, (trace or {}).get('charged_upper_usd'), 'ERROR')
            raise
        rec = dict(key=key, identity=current, answer=answer, trace=trace, raw_response=(captured.get('response') or {}).get('response_body'),
                   provider_identity_matches=captured.get('provider_identity_matches'))
        assert_no_secret(rec)
        write_private(self.path(key, 'response'), rec)
        os.remove(self.path(key, 'inflight'))
        st = self.state(); st['settled_upper_usd'] = round(st['settled_upper_usd'] + float(trace.get('charged_upper_usd') or 0), 6); self.save(st)
        if self.batch is not None:
            self.batch.settle(bkey, trace.get('charged_upper_usd') if self.mode == 'live' else 0.0, 'DONE')
        return answer, trace
