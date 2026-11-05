"""Read-only launch preflight; never reduces or resets the shared journal."""
import json
import os
from pathlib import Path


def check():
    path=Path(os.environ['HILLINK_AGENT_BUDGET_FILE'])
    with path.open() as stream:
        import fcntl
        fcntl.flock(stream,fcntl.LOCK_SH)
        state=json.load(stream)
    calls=int(os.environ['HILLINK_AGENT_MAX_CALLS'])
    usd=float(os.environ['HILLINK_AGENT_MAX_USD'])
    if calls!=state['max_calls'] or usd!=state['max_usd']:
        raise ValueError('LIMITS_MUST_MATCH_SHARED_JOURNAL; DO_NOT_RESET_OR_SILENTLY_LOWER')
    if not 0<calls<=2500 or not 0<usd<=20 or not isinstance(state.get('requests'),list):
        raise ValueError('APPROVED_CUMULATIVE_LIMITS_REQUIRED')
    if calls>400 and not any(a.get('approved_max_calls',0)>=calls and a.get('unchanged_max_usd')==20
                            and a.get('approval_reference') for a in state.get('limit_amendments',[])):
        raise ValueError('RECORDED_CALL_EXTENSION_APPROVAL_REQUIRED')
    if state.get('approved_global_max_calls', calls) != calls:
        raise ValueError('LIMITS_MUST_MATCH_APPROVED_GLOBAL_CEILING')
    spent=sum(r.get('charged_upper_usd',r['reserved_usd']) for r in state['requests'])
    return dict(max_calls=calls,used_calls=len(state['requests']),max_usd=usd,cost_upper_usd=spent)


if __name__=='__main__':
    print(json.dumps(check()))
