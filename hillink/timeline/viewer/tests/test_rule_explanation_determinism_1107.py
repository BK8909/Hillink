"""Rule-mode explanations must not depend on the per-process string hash (PYTHONHASHSEED).

The engine names the factor an alternative trailed the chosen one on most (major_reason -> "... 면에서 덜 맞음").
On equal differences the factor used to come from set iteration order, so the same run could explain itself
differently after a restart (seen for A26 and N23 with the wine event). Scores and choices were never affected.
"""
import json, os, subprocess, sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / 'experiments/persona_live'
CASE = dict(c=dict(feasible=True, terms=[dict(factor=f, value=v) for f, v in
                   [('저녁 끼니 해결', 0.1), ('야경 · 정원 · 공간 경험', 0.1), ('이동 부담', 0.5), ('지불액', 0.3)]]),
            top=dict(feasible=True, terms=[dict(factor=f, value=v) for f, v in
                     [('저녁 끼니 해결', 0.4), ('야경 · 정원 · 공간 경험', 0.4), ('이동 부담', 0.5), ('지불액', 0.3)]]))
CODE = ("import json,sys;sys.path.insert(0,sys.argv[1]);from operator_choice.operator_world_v1.engine import major_reason;"
        "c=json.loads(sys.argv[2]);print(major_reason(c['c'],c['top']))")


def _run(seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    return subprocess.run([sys.executable, '-c', CODE, str(PKG), json.dumps(CASE, ensure_ascii=False)],
                          capture_output=True, text=True, env=env, check=True).stdout.strip()


def test_tied_factor_is_named_the_same_under_every_hash_seed():
    outs = {_run(seed) for seed in range(8)}
    assert len(outs) == 1, outs
    # equal shortfall (-0.30) on two factors: the name order decides, not the hash
    assert outs == {f"{min('저녁 끼니 해결', '야경 · 정원 · 공간 경험')}에서 -0.30"}


def test_a_unique_largest_shortfall_is_unchanged():
    sys.path.insert(0, str(PKG))
    from operator_choice.operator_world_v1.engine import major_reason
    c = dict(feasible=True, terms=[dict(factor='지불액', value=-0.2), dict(factor='이동 부담', value=0.1)])
    top = dict(feasible=True, terms=[dict(factor='지불액', value=0.3), dict(factor='이동 부담', value=0.1)])
    assert major_reason(c, top) == '지불액에서 -0.50'
