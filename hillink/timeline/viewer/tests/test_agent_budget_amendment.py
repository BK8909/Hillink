import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from test_autonomous_agent import P

@pytest.fixture(autouse=True)
def _credential_present(monkeypatch):
    # budget-journal tests: the server-side API credential is present (its value is never read here)
    import openai_credentials
    monkeypatch.setattr(openai_credentials, 'load_openai_api_key', lambda: 'present')


spec = importlib.util.spec_from_file_location('amend', Path(__file__).resolve().parents[2] / 'tools/amend_agent_call_limit.py')
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


def test_extension_preserves_failed_calls_spend_and_requires_approval(tmp_path):
    p = tmp_path / 'journal'
    old = P.Budget(p, 20, 400)
    rid = old.reserve(.01, {'purpose': 'TEST'})
    old.settle(rid, status='ERROR')
    original = p.read_bytes(); requests = json.loads(original)['requests']
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 1000).summary()
    M.amend(p, tmp_path/'backup', hashlib.sha256(original).hexdigest(), 1000, 'EXPLICIT_TEST_APPROVAL')
    assert (tmp_path/'backup').read_bytes() == original
    assert json.loads(p.read_bytes())['requests'] == requests
    summary = P.Budget(p, 20, 1000).summary()
    assert summary == dict(max_usd=20, max_calls=1000, calls=1, cost_upper_usd=.01, unresolved=0)
    with pytest.raises(ValueError): P.Budget(p, 20, 6301)
    with pytest.raises(ValueError): P.Budget(p, 21, 1000)


def test_extension_cannot_create_reset_or_ignore_concurrent_calls(tmp_path):
    p = tmp_path/'journal'
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'): P.Budget(p, 20, 1000).summary()
    b = P.Budget(p, 20, 400); b.summary()
    before = hashlib.sha256(p.read_bytes()).hexdigest()
    rid = b.reserve(.001, {})
    with pytest.raises(ValueError, match='JOURNAL_CHANGED'):
        M.amend(p, tmp_path/'backup', before, 1000, 'TEST')
    with pytest.raises(ValueError, match='UNRESOLVED'):
        M.amend(p, tmp_path/'backup', hashlib.sha256(p.read_bytes()).hexdigest(), 1000, 'TEST')
    assert b.summary()['unresolved'] == 1
    assert not (tmp_path/'backup').exists()


def test_second_extension_preserves_entire_history_and_worker_local_caps(tmp_path):
    p = tmp_path/'journal'
    b = P.Budget(p, 20, 400)
    rid = b.reserve(.01, {}); b.settle(rid, status='ERROR')
    M.amend(p, tmp_path/'first', hashlib.sha256(p.read_bytes()).hexdigest(), 1000, 'FIRST')
    before = p.read_bytes(); history = json.loads(before)['requests']
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 1500).summary()
    M.amend(p, tmp_path/'second', hashlib.sha256(before).hexdigest(), 1500, 'USER_SECOND')
    assert (tmp_path/'second').read_bytes() == before
    assert P.Budget(p, 20, 1500).summary()['max_calls'] == 1500
    assert P.Budget(p, 20, 1000).summary()['max_calls'] == 1000
    assert json.loads(p.read_bytes())['max_calls'] == 1500
    local = P.Budget(p, 20, 1)
    with pytest.raises(P.ProviderUnavailable, match='CALL_LIMIT'): local.reserve(.01, {})
    state = json.loads(p.read_bytes())
    assert state['requests'] == history
    assert state['max_usd'] == 20
    assert [a['approved_max_calls'] for a in state['limit_amendments']] == [1000, 1500]


def test_legacy_worker_lower_write_cannot_erase_explicit_global_approval(tmp_path):
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'backup', hashlib.sha256(p.read_bytes()).hexdigest(), 1500, 'TEST')
    state = json.loads(p.read_bytes()); state['max_calls'] = 1000
    p.write_text(json.dumps(state))  # Simulate an already-running old binary.
    assert P.Budget(p, 20, 1500).summary()['max_calls'] == 1500
    state = json.loads(p.read_bytes()); state['approved_global_max_calls'] = 1499
    p.write_text(json.dumps(state))
    with pytest.raises(ValueError, match='GLOBAL_CALL_CEILING_APPROVAL_REQUIRED'):
        P.Budget(p, 20, 400).summary()


def test_1500_cannot_start_fresh_journal_or_raise_usd_limit(tmp_path):
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(tmp_path/'new', 20, 1500).summary()
    with pytest.raises(ValueError): P.Budget(tmp_path/'new', 20.01, 1500)


def test_parallel_workers_cannot_overrun_global_1500_ceiling(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'backup', hashlib.sha256(p.read_bytes()).hexdigest(), 1500, 'TEST')
    state = json.loads(p.read_bytes())
    state['requests'] = [dict(id=str(i), state='COMPLETED', reserved_usd=.001,
                              charged_upper_usd=.001) for i in range(1499)]
    p.write_text(json.dumps(state))
    def reserve(_):
        try:
            P.Budget(p, 20, 1500).reserve(.001, {})
            return 'RESERVED'
        except P.ProviderUnavailable as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(4)))
    assert results.count('RESERVED') == 1
    assert results.count('CALL_LIMIT') == 3
    assert len(json.loads(p.read_bytes())['requests']) == 1500


def test_third_approval_preserves_errors_interrupted_cost_and_prior_approvals(tmp_path):
    p = tmp_path/'journal'
    budget = P.Budget(p, 20, 400)
    for status in ('COMPLETED', 'ERROR', 'INTERRUPTED_BILLING_UNKNOWN'):
        rid = budget.reserve(.01, {'purpose': 'TEST'})
        budget.settle(rid, status=status, cost=.004 if status == 'COMPLETED' else None)
    for limit in (1000, 1500):
        M.amend(p, tmp_path/str(limit), hashlib.sha256(p.read_bytes()).hexdigest(), limit, 'PRIOR_APPROVAL')
    before = p.read_bytes(); prior = json.loads(before)
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 2500).summary()
    M.amend(p, tmp_path/'2500', hashlib.sha256(before).hexdigest(), 2500, 'USER_APPROVAL_2026_11_05')
    after = json.loads(p.read_bytes())
    assert (tmp_path/'2500').read_bytes() == before
    assert after['requests'] == prior['requests']
    assert after['limit_amendments'][:-1] == prior['limit_amendments']
    assert after['approved_global_max_calls'] == after['max_calls'] == 2500
    assert after['max_usd'] == 20
    assert P.Budget(p, 20, 2500).summary()['cost_upper_usd'] == pytest.approx(.024)
    assert P.Budget(p, 20, 1500).summary()['max_calls'] == 1500
    assert json.loads(p.read_bytes())['max_calls'] == 2500


def _reserve_in_process(args):
    path, amount = args
    try:
        return P.Budget(path, 20, 2500).reserve(amount, {'purpose': 'PARALLEL_TEST'})
    except P.ProviderUnavailable as error:
        return str(error)


@pytest.mark.parametrize('boundary', ['calls', 'usd'])
def test_parallel_processes_reserve_last_allowance_once_and_keep_settlement(tmp_path, boundary):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'backup', hashlib.sha256(p.read_bytes()).hexdigest(), 2500, 'TEST')
    state = json.loads(p.read_bytes())
    count = 2499 if boundary == 'calls' else 1
    price = .001 if boundary == 'calls' else 19.99
    state['requests'] = [dict(id=str(i), state='COMPLETED', reserved_usd=price,
                              charged_upper_usd=price) for i in range(count)]
    p.write_text(json.dumps(state))
    amount = .01 if boundary == 'usd' else .001
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as pool:
        outcomes = list(pool.map(_reserve_in_process, [(p, amount)] * 4))
    rejection = 'CALL_LIMIT' if boundary == 'calls' else 'USD_LIMIT'
    assert outcomes.count(rejection) == 3
    rid = next(outcome for outcome in outcomes if outcome != rejection)
    current = json.loads(p.read_bytes())
    assert current['requests'][:-1] == state['requests']
    assert len(current['requests']) == count + 1
    assert current['requests'][-1]['state'] == 'RESERVED'
    budget = P.Budget(p, 20, 2500)
    budget.settle(rid, status='ERROR')  # Ambiguous failure consumes reservation.
    with pytest.raises(ValueError, match='ALREADY_SETTLED'):
        budget.settle(rid, status='COMPLETED', cost=0)
    with pytest.raises(P.ProviderUnavailable, match=rejection):
        budget.reserve(.001, {})
    assert budget.summary()['cost_upper_usd'] <= 20


def test_2500_requires_existing_approval_and_rejects_higher_caps(tmp_path):
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(tmp_path/'absent', 20, 2500).summary()
    for usd, calls in ((20.001, 2500), (20, 6301)):
        with pytest.raises(ValueError):
            P.Budget(tmp_path/'unapproved', usd, calls)
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    original = p.read_bytes()
    for calls, approval in ((6301, 'TEST'), (2500, '')):
        with pytest.raises(ValueError, match='APPROVED_CALL_LIMIT_REQUIRED'):
            M.amend(p, tmp_path/'backup', hashlib.sha256(original).hexdigest(), calls, approval)
    assert p.read_bytes() == original


def test_2600_ceiling_needs_its_own_recorded_amendment(tmp_path):
    """2026-11-08 03:20: the approvable ceiling is 2,600 calls (USD20 unchanged); a journal approved for 2,500 stays
    at 2,500 until an amendment for 2,600 is recorded, and nothing above 2,600 can be approved."""
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'b1', hashlib.sha256(p.read_bytes()).hexdigest(), 2500, 'USER_APPROVAL_2026_11_05')
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 2600).summary()
    assert P.Budget(p, 20, 2500).summary()['max_calls'] == 2500
    M.amend(p, tmp_path/'b2', hashlib.sha256(p.read_bytes()).hexdigest(), 2600, 'USER_APPROVAL_2026_11_08_0320')
    s = P.Budget(p, 20, 2600).summary()
    assert s['max_calls'] == 2600 and s['max_usd'] == 20
    with pytest.raises(ValueError, match='APPROVED_CALL_LIMIT_REQUIRED'):
        M.amend(p, tmp_path/'b3', hashlib.sha256(p.read_bytes()).hexdigest(), 6301, 'TEST')


def test_live_preflight_accepts_an_amended_2600_journal_only(tmp_path, monkeypatch):
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import visit_execution as VE
    assert VE.MAX_APPROVABLE_CALLS == P.MAX_APPROVABLE_CALLS
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'b1', hashlib.sha256(p.read_bytes()).hexdigest(), 2500, 'USER_APPROVAL_2026_11_05')
    monkeypatch.setenv('HILLINK_LIVE_APPROVAL_REFERENCE', 'TEST'); monkeypatch.setenv('HILLINK_LLM_EXTERNAL_OPT_IN', '1')
    monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE', str(p)); monkeypatch.setenv('HILLINK_AGENT_MAX_USD', '20')
    monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS', '2600')
    assert VE.live_status() == (False, 'EXISTING_JOURNAL_CALL_EXTENSION_APPROVAL_REQUIRED')
    M.amend(p, tmp_path/'b2', hashlib.sha256(p.read_bytes()).hexdigest(), 2600, 'USER_APPROVAL_2026_11_08_0320')
    assert VE.live_status() == (True, None)
    monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS', '6301')
    assert VE.live_status() == (False, 'APPROVED_LIMIT_REQUIRED')


def test_2620_ceiling_needs_its_own_recorded_amendment(tmp_path, monkeypatch):
    """2026-11-08 12:11: ceiling 2,620 (USD20 unchanged). A journal amended to 2,600 stays at 2,600 until a 2,620
    amendment is recorded; LIVE preflight follows the journal; nothing above 2,620 can be approved."""
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import visit_execution as VE
    assert P.MAX_APPROVABLE_CALLS == VE.MAX_APPROVABLE_CALLS == M.MAX_APPROVABLE_CALLS == 6300
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'b1', hashlib.sha256(p.read_bytes()).hexdigest(), 2600, 'USER_APPROVAL_2026_11_08_0320')
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 2620).summary()
    monkeypatch.setenv('HILLINK_LIVE_APPROVAL_REFERENCE', 'TEST'); monkeypatch.setenv('HILLINK_LLM_EXTERNAL_OPT_IN', '1')
    monkeypatch.setenv('HILLINK_AGENT_BUDGET_FILE', str(p)); monkeypatch.setenv('HILLINK_AGENT_MAX_USD', '20')
    monkeypatch.setenv('HILLINK_AGENT_MAX_CALLS', '2620')
    assert VE.live_status() == (False, 'EXISTING_JOURNAL_CALL_EXTENSION_APPROVAL_REQUIRED')
    M.amend(p, tmp_path/'b2', hashlib.sha256(p.read_bytes()).hexdigest(), 2620, 'USER_APPROVAL_2026_11_08_1211')
    assert P.Budget(p, 20, 2620).summary()['max_calls'] == 2620 and VE.live_status() == (True, None)
    with pytest.raises(ValueError, match='APPROVED_CALL_LIMIT_REQUIRED'):
        M.amend(p, tmp_path/'b3', hashlib.sha256(p.read_bytes()).hexdigest(), 6301, 'TEST')


def test_4500_ceiling_needs_its_own_recorded_amendment(tmp_path, monkeypatch):
    """2026-11-08 13:19: ceiling 4,500 (USD20 unchanged). A journal at 2,620 stays there until a 4,500 amendment is
    recorded; nothing above 4,500 can be approved; the dollar ceiling never moves."""
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import visit_execution as VE
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'b1', hashlib.sha256(p.read_bytes()).hexdigest(), 2620, 'USER_APPROVAL_2026_11_08_1211')
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 4500).summary()
    M.amend(p, tmp_path/'b2', hashlib.sha256(p.read_bytes()).hexdigest(), 4500, 'USER_APPROVAL_2026_11_08_1319')
    assert P.Budget(p, 20, 4500).summary()['max_calls'] == 4500
    with pytest.raises(ValueError):
        P.Budget(p, 20.01, 4500)
    with pytest.raises(ValueError, match='APPROVED_CALL_LIMIT_REQUIRED'):
        M.amend(p, tmp_path/'b3', hashlib.sha256(p.read_bytes()).hexdigest(), 6301, 'TEST')


def test_5000_ceiling_needs_its_own_recorded_amendment(tmp_path):
    """2026-11-08 23:44 user approval: ceiling 5,000 (USD20 unchanged). A journal at 4,500 stays there until a 5,000
    amendment is recorded; nothing above 5,000 can be approved."""
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'b1', hashlib.sha256(p.read_bytes()).hexdigest(), 4500, 'USER_APPROVAL_2026_11_08_1319')
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 5000).summary()
    M.amend(p, tmp_path/'b2', hashlib.sha256(p.read_bytes()).hexdigest(), 5000, 'USER_APPROVAL_2026_11_08_2344')
    assert P.Budget(p, 20, 5000).summary()['max_calls'] == 5000
    with pytest.raises(ValueError, match='APPROVED_CALL_LIMIT_REQUIRED'):
        M.amend(p, tmp_path/'b3', hashlib.sha256(p.read_bytes()).hexdigest(), 6301, 'TEST')


def test_6300_ceiling_needs_its_own_recorded_amendment(tmp_path):
    """2026-11-09 17:18 user approval: ceiling 6,300 for the final A/B LIVE study (USD20 unchanged). A journal at 5,000
    stays there until a 6,300 amendment is recorded; nothing above 6,300 can be approved and USD20 cannot be raised."""
    p = tmp_path/'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path/'b1', hashlib.sha256(p.read_bytes()).hexdigest(), 5000, 'USER_APPROVAL_2026_11_08_2344')
    with pytest.raises(ValueError, match='APPROVAL_REQUIRED'):
        P.Budget(p, 20, 6300).summary()
    M.amend(p, tmp_path/'b2', hashlib.sha256(p.read_bytes()).hexdigest(), 6300, 'USER_APPROVAL_2026_11_09_1718')
    assert P.Budget(p, 20, 6300).summary()['max_calls'] == 6300
    with pytest.raises(ValueError):
        P.Budget(p, 20.01, 6300)
    with pytest.raises(ValueError, match='APPROVED_CALL_LIMIT_REQUIRED'):
        M.amend(p, tmp_path/'b3', hashlib.sha256(p.read_bytes()).hexdigest(), 6301, 'TEST')
