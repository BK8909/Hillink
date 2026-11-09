"""The USD ceiling of the shared journal can only go back up to the approved US$20, with approval, digest and backup."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'experiments' / 'persona_live'))
import restore_agent_usd_ceiling as R  # noqa: E402
import amend_agent_call_limit as M  # noqa: E402
from operator_choice.autonomy_v1 import agent_provider as P  # noqa: E402


def lowered(tmp_path):
    p = tmp_path / 'journal'
    P.Budget(p, 20, 400).summary()
    M.amend(p, tmp_path / 'b0', hashlib.sha256(p.read_bytes()).hexdigest(), 600, 'USER_APPROVAL_TEST')
    P.Budget(p, 15.5, 600).summary()   # a process with a smaller per-stage limit lowers the shared ceiling
    assert json.loads(p.read_text())['max_usd'] == 15.5
    return p


def test_restores_exactly_twenty_with_record_and_backup(tmp_path):
    p = lowered(tmp_path); before = p.read_bytes()
    out = R.restore(p, tmp_path / 'b1', hashlib.sha256(before).hexdigest(), 'USER_APPROVAL_RESTORE')
    s = json.loads(p.read_text())
    assert out['max_usd'] == 20 and s['max_usd'] == 20 and (tmp_path / 'b1').read_bytes() == before
    assert s['usd_ceiling_restorations'][0]['previous_max_usd'] == 15.5 and s['usd_ceiling_restorations'][0]['approval_reference']
    assert P.Budget(p, 20, 600).summary()['max_usd'] == 20


def test_refuses_without_approval_wrong_digest_or_nothing_to_restore(tmp_path):
    p = lowered(tmp_path); sha = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='APPROVAL_REFERENCE_REQUIRED'): R.restore(p, tmp_path / 'b1', sha, ' ')
    with pytest.raises(ValueError, match='JOURNAL_CHANGED'): R.restore(p, tmp_path / 'b2', '0' * 64, 'A')
    R.restore(p, tmp_path / 'b3', sha, 'A')
    with pytest.raises(ValueError, match='NOTHING_TO_RESTORE'): R.restore(p, tmp_path / 'b4', hashlib.sha256(p.read_bytes()).hexdigest(), 'A')
