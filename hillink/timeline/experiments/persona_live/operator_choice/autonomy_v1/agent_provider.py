"""Responses transport for versioned agents; no credentials or prompts in usage logs.

All participating workers share one locked, durable spend journal. Reservations
survive process failure: an ambiguous request consumes its worst-case allowance.
Replay is labelled and never submitted as evidence of a fresh model decision.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.request
import uuid

POLICY = 'RESPONSES_AGENT_BUDGET_V1'
REQUEST_POLICY = 'RESPONSES_CANONICAL_CONTEXT_V2'
PRICES = {'gpt-6-luna': {'input': .10, 'cached': .01, 'output': .50, 'write': .125}}
PRICE_SOURCE = 'https://developers.openai.com/api/docs/models/gpt-6-luna'
PRICE_CHECKED = '2026-11-04'


class ProviderUnavailable(RuntimeError):
    """Safe diagnostic code only; never propagate HTTP bodies or credentials."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class Budget:
    def __init__(self, path, max_usd, max_calls):
        if not math.isfinite(max_usd) or not 0 < max_usd <= 20 or type(max_calls) is not int or not 0 < max_calls <= 2500:
            raise ValueError('EXPLICIT_APPROVED_BUDGET_REQUIRED')
        self.path = Path(path)
        self.limit, self.calls = max_usd, max_calls

    def _update(self, change):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'r+', encoding='utf-8') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            raw = f.read()
            state = json.loads(raw) if raw else {'policy': POLICY, 'max_usd': self.limit, 'max_calls': self.calls, 'requests': []}
            if self.calls > 400:
                approvals = state.get('limit_amendments', [])
                if not raw or not any(x.get('approved_max_calls', 0) >= self.calls
                                      and x.get('unchanged_max_usd') == 20
                                      and x.get('approval_reference') for x in approvals):
                    raise ValueError('EXISTING_JOURNAL_CALL_EXTENSION_APPROVAL_REQUIRED')
            # Only an explicit journal amendment can set the shared ceiling.
            # A worker's smaller allowance is local; it must not undo approval
            # for other workers. Older binaries may write max_calls downward:
            # recover only the separately recorded, approved ceiling, never an
            # environment variable or a fresh journal's requested allowance.
            approved = state.get('approved_global_max_calls')
            if approved is not None:
                if (type(approved) is not int or not 400 < approved <= 2500
                        or not any(x.get('approved_max_calls') == approved
                                   and x.get('unchanged_max_usd') == 20
                                   and x.get('approval_reference')
                                   for x in state.get('limit_amendments', []))):
                    raise ValueError('GLOBAL_CALL_CEILING_APPROVAL_REQUIRED')
                state['max_calls'] = approved
            else:
                # Unamended legacy journals keep their original lower caps.
                state['max_calls'] = min(state['max_calls'], self.calls)
            state['max_usd'] = min(state['max_usd'], self.limit)
            result = change(state)
            f.seek(0)
            json.dump(state, f, ensure_ascii=False, allow_nan=False)
            f.truncate(); f.flush(); os.fsync(f.fileno())
            return result

    def reserve(self, maximum, metadata):
        if not math.isfinite(maximum) or maximum <= 0:
            raise ValueError('INVALID_COST_RESERVATION')
        def change(s):
            spent = sum(r.get('charged_upper_usd', r['reserved_usd']) for r in s['requests'])
            if len(s['requests']) >= min(s['max_calls'], self.calls):
                raise ProviderUnavailable('CALL_LIMIT')
            if spent + maximum > s['max_usd']:
                raise ProviderUnavailable('USD_LIMIT')
            rid = uuid.uuid4().hex
            s['requests'].append(dict(id=rid, reserved_usd=maximum, state='RESERVED', at=time.time(), **metadata))
            return rid
        return self._update(change)

    def settle(self, rid, *, cost=None, status, **metadata):
        def change(s):
            row = next(r for r in s['requests'] if r['id'] == rid)
            if row['state'] != 'RESERVED':
                raise ValueError('REQUEST_ALREADY_SETTLED')
            if cost is not None and (not math.isfinite(cost) or cost < 0):
                raise ValueError('INVALID_ACTUAL_COST')
            row.update(state=status, charged_upper_usd=row['reserved_usd'] if cost is None else cost, **metadata)
            return dict(row)
        return self._update(change)

    def summary(self):
        return self._update(lambda s: dict(max_usd=s['max_usd'], max_calls=min(s['max_calls'], self.calls), calls=len(s['requests']),
            cost_upper_usd=sum(r.get('charged_upper_usd', r['reserved_usd']) for r in s['requests']),
            unresolved=sum(r['state']=='RESERVED' for r in s['requests'])))


def configured_budget():
    path = os.environ.get('HILLINK_AGENT_BUDGET_FILE')
    if not path:
        raise ProviderUnavailable('SHARED_BUDGET_NOT_CONFIGURED')
    return Budget(path, float(os.environ.get('HILLINK_AGENT_MAX_USD', '0')),
                  int(os.environ.get('HILLINK_AGENT_MAX_CALLS', '0')))


def _write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False)
    os.replace(tmp, path)


def _publish_first(path, value):
    """Atomic first-result index; repeated live calls retain separate archives."""
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.pending')
    _write_private(temporary, value)
    try:
        os.link(temporary, path)
    except FileExistsError:
        pass
    finally:
        temporary.unlink()


def request(*, policy, system, context, schema, purpose, model=None, effort=None, max_output=6000):
    """One attempt. The caller may replan, but each attempt reserves independently."""
    from openai_credentials import load_openai_api_key
    import jsonschema
    model = model or os.environ.get('HILLINK_AGENT_MODEL', 'gpt-6-luna')
    effort = effort or os.environ.get('HILLINK_AGENT_EFFORT', 'high')
    if model not in PRICES:
        raise ProviderUnavailable('MODEL_PRICE_NOT_VERIFIED')
    if effort not in ('low', 'medium', 'high') or not 256 <= max_output <= 16000:
        raise ValueError('INVALID_INFERENCE_SETTINGS')
    payload = dict(model=model, store=False, reasoning={'effort': effort}, max_output_tokens=max_output,
        input=[{'role':'system', 'content':system}, {'role':'user', 'content':json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)}],
        text={'format':{'type':'json_schema', 'name':'hillink_agent', 'strict':True, 'schema':schema}})
    identity = digest({'request_policy':REQUEST_POLICY, 'policy':policy, 'purpose':purpose, 'request':payload})
    mode = os.environ.get('HILLINK_AGENT_MODE', 'off')
    root = os.environ.get('HILLINK_AGENT_CACHE')
    cache = Path(root) / (identity + '.json') if root else None
    if mode in ('replay', 'cached_live') and cache and cache.is_file():
        saved = json.loads(cache.read_text())
        if saved.get('input_sha256') != identity or saved.get('origin') != 'LIVE_RESPONSES':
            raise ProviderUnavailable('INVALID_REPLAY_ORIGIN')
        jsonschema.validate(saved['answer'], schema)
        return saved['answer'], dict(saved['trace'], execution='CACHE_REPLAY', current_call_cost_usd=0)
    if mode not in ('live', 'cached_live'):
        raise ProviderUnavailable('REPLAY_MISS' if mode == 'replay' else 'PROVIDER_DISABLED')
    if os.environ.get('HILLINK_LLM_EXTERNAL_OPT_IN') != '1':
        raise ProviderUnavailable('EXTERNAL_CALL_NOT_AUTHORIZED')
    # Existing local loader owns credentials. Never persist/print the key.
    try:
        key = load_openai_api_key()
    except Exception:
        raise ProviderUnavailable('CREDENTIALS_UNAVAILABLE') from None
    budget = configured_budget()
    wire = json.dumps(payload, ensure_ascii=False).encode()
    rates = PRICES[model]
    # UTF-8 bytes bound text token count; reserve all input at cache-write rate.
    ceiling = ((len(wire) + 4096) * max(rates['input'], rates['write']) + max_output*rates['output']) / 1e6
    rid = budget.reserve(ceiling, {'purpose':purpose, 'model':model, 'input_sha256':identity})
    begin = time.monotonic(); cost = None; usage = {}; response_id = None
    try:
        req = urllib.request.Request('https://api.openai.com/v1/responses', data=wire, method='POST',
            headers={'Content-Type':'application/json', 'Authorization':'Bearer ' + key})
        # python.org macOS builds may have no system CA link. Use a maintained
        # CA bundle when installed; certificate verification is never disabled.
        try:
            import certifi
            tls = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            tls = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=240, context=tls) as response:
            data = json.loads(response.read())
        usage = data.get('usage') or {}; response_id = data.get('id')
        if 'input_tokens' in usage and 'output_tokens' in usage:
            inp, out = usage['input_tokens'], usage['output_tokens']
            cached = (usage.get('input_tokens_details') or {}).get('cached_tokens', 0)
            # Actual token-based upper estimate; separate from provider invoice.
            cost = ((inp-cached)*rates['write'] + cached*rates['cached'] + out*rates['output']) / 1e6
        if data.get('status') != 'completed':
            raise ProviderUnavailable('RESPONSE_INCOMPLETE')
        answer = json.loads(''.join(c.get('text','') for item in data.get('output',[]) if item.get('type')=='message'
            for c in item.get('content',[]) if c.get('type')=='output_text'))
        jsonschema.validate(answer, schema)
    except Exception as exc:
        code = str(exc) if isinstance(exc, ProviderUnavailable) else 'HTTP_'+str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        trace = budget.settle(rid, cost=cost, status='ERROR', code=code, usage=usage,
                              response_id=response_id, seconds=round(time.monotonic()-begin,3))
        error = ProviderUnavailable(code)
        error.trace = dict(trace, execution='LIVE_ERROR', policy=policy)
        raise error from None
    trace = budget.settle(rid, cost=cost, status='COMPLETED', usage=usage, response_id=response_id,
                         seconds=round(time.monotonic()-begin,3))
    trace.update(execution='LIVE_RESPONSES', input_sha256=identity, policy=policy, request_policy=REQUEST_POLICY,
                 current_call_cost_upper_usd=trace['charged_upper_usd'],
                 model_returned=data.get('model'), price_source=PRICE_SOURCE, price_checked=PRICE_CHECKED,
                 cost_basis='TOKEN_BASED_UPPER_ESTIMATE_NOT_INVOICE')
    if cache:
        saved = dict(origin='LIVE_RESPONSES', input_sha256=identity, answer=answer, trace=trace,
            audit_input=dict(policy=policy,purpose=purpose,system=system,context=context,schema=schema,
                inference_settings=dict(model=model,effort=effort,max_output=max_output,request_policy=REQUEST_POLICY)))
        _publish_first(cache.parent / 'live_history' / (identity + '.' + rid + '.json'), saved)
        _publish_first(cache, saved)
    return answer, trace
