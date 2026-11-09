"""v20b follow-up (no key, no cost): repeat evidence is split into venue-specific links and general trait Facts, and
the lean need-estimate research switch is OFF by default (product request unchanged) and adds only the engine's
elapsed-time estimate when ON."""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'timeline/experiments/persona_live/operator_choice'))
from autonomy_v1 import visit_memory_llm as VM  # noqa: E402

RUN = ROOT / 'tools/v18_bench/run.py'


def test_repeat_check_does_not_count_general_trait_facts_as_venue_evidence():
    full = dict(candidates=[
        dict(action_id='meal:PIZZA_HILL', type='MEAL', earlier_use=dict(times=1, last=[dict(date='2026-11-07')]),
             m4=dict(evidence_fact_ids=['F10', 'F12'], shown_because='ENGINE_SHORTLIST_FEASIBLE')),
        dict(action_id='activity:footbath:X', type='ACTIVITY', earlier_use=dict(times=1, last=[dict(date='2026-11-07', same_place_other_option=True)]),
             m4=dict(direct_evidence_fact_ids=['F05'], evidence_fact_ids=['F05']))])
    chk = VM.repeat_check(full)
    pz, fb = chk['candidates']
    assert pz['personal_evidence_fact_ids'] == [] and pz['general_trait_fact_ids'] == ['F10', 'F12']
    assert fb['personal_evidence_fact_ids'] == ['F05'] and fb['same_place_other_option'] is True
    r = VM.repeat_choice(chk, dict(action_id='meal:PIZZA_HILL', supporting_fact_ids=['F10'], decision_summary='어제 이용한 곳'))
    assert r['basis'] == 'REASON_CITES_EARLIER_VISIT_OR_SITUATION' and r['general_trait_evidence_cited'] == ['F10'] and r['personal_evidence_cited'] == []
    r = VM.repeat_choice(chk, dict(action_id='activity:footbath:X', supporting_fact_ids=['F05'], decision_summary='하이라이트 기록'))
    assert r['basis'] == 'PERSONAL_EVIDENCE_CITED' and r['same_place_other_option'] is True


def bench(tmp, name, env):
    d = tmp / name
    cmd = [sys.executable, str(RUN), '--case', 'pid:A05', '--e2e-policy', 'LLM_AUTONOMOUS_CUSTOMER_V19LS', '--e2e-max-decisions', '3',
           '--arrival', '16:30', '--request-extra', '{"duration":"stay_2"}', '--run-dir', str(d), '--shadow', 'offline', '--yes']
    r = subprocess.run(cmd, cwd=str(ROOT), env=dict(os.environ, HILLINK_AGENT_BUDGET_FILE=str(tmp / 'usage.json'), HILLINK_LLM_EXTERNAL_OPT_IN='0', **env),
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    return [json.load(open(f))['request_body'] for f in sorted(glob.glob(str(d / 'calls/*_a1.request.json')))]


@pytest.mark.skipif(not RUN.exists(), reason='bench not in this package')
def test_lean_need_estimate_switch(tmp_path):
    off = bench(tmp_path, 'off', {'HILLINK_RESEARCH_LEAN_NEED_ESTIMATE': ''})
    on = bench(tmp_path, 'on', {'HILLINK_RESEARCH_LEAN_NEED_ESTIMATE': '1'})
    assert off and len(off) == len(on)
    for a, b in zip(off, on):
        ua, ub = json.loads(a['input'][2]['content']), json.loads(b['input'][2]['content'])
        assert 'modeled_need' not in ua['state']
        need = ub['state'].pop('modeled_need')
        assert ua == ub and a['input'][:2] == b['input'][:2] and a['text'] == b['text']     # nothing else changes
        assert need['engine_estimate']['modeled_satiety'] and need['engine_estimate']['source'].startswith('ENGINE_RULE') and '관측되지 않았' in need['meaning']
        assert 'next_meal_options' in need
    after = json.loads(on[1]['input'][2]['content'])['state']['modeled_need']
    assert after['last_simulated_meal'] and after['minutes_since_last_meal'] is not None
    assert after['last_simulated_meal']['kind_basis'] == 'MODEL_ASSUMPTION_AT_ORDER_NOT_OBSERVED_INTAKE'
