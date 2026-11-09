"""Make missing approved inputs explicit; strict release jobs fail, public CI skips."""
import sys
from pathlib import Path
import pytest


def pytest_addoption(parser):
    parser.addoption('--strict-private-inputs', action='store_true', help='Fail when declared approved customer inputs are missing')


def pytest_configure(config):
    root=Path(__file__).resolve().parents[3]
    if (root/'handover/data/bundle.json').exists():
        import os
        sys.path.insert(0,str(root/'tools'))
        from bootstrap_data import bootstrap
        data=bootstrap()
        os.environ.setdefault('HILLINK_QA_PROFILE_ROOT',str(Path(data['path']).parent/'regression/qa'))
    config.addinivalue_line('markers','requires_private_personas(*ids): requires approved turn_personas_ext.local.json / SHA-validated registry')
    config.addinivalue_line('markers','historical_reference: frozen fixture / sealed experiment / stored ledger compared with the current engine (tools/ci/historical_reference.tsv); not a current-product test')


def pytest_collection_modifyitems(config, items):
    tsv=Path(__file__).resolve().parents[3]/'tools/ci/historical_reference.tsv'
    historical={'/'.join(l.split('\t')[1].split('::')[0].split('/')[-1:])+'::'+l.split('\t')[1].split('::',1)[1]
                for l in tsv.read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')}
    for item in items:
        key=item.nodeid.split('/')[-1].split('[')[0]
        if key in historical:item.add_marker(pytest.mark.historical_reference)
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/persona_live'))
    from operator_choice.operator_world_v1_1.turn_view import load_all_personas
    available=set(load_all_personas())
    missing=[]
    for item in items:
        marker=item.get_closest_marker('requires_private_personas')
        if marker:
            absent=set(marker.args)-available
            if absent:
                reason='Approved execution input missing: '+','.join(sorted(absent))+'; provide turn_personas_ext.local.json and approved lineage, never synthesize production data'
                if config.getoption('--strict-private-inputs'):
                    missing.append(item.nodeid)
                else:item.add_marker(pytest.mark.skip(reason=reason))
    if missing:
        raise pytest.UsageError('PRIVATE_INPUT_REQUIRED for '+str(len(missing))+' tests; approved input bundle is not connected')
