"""Private display corrections must survive relocation and reject wrong sources."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[3] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('display_bootstrap', TOOLS / 'bootstrap_data.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


@pytest.mark.parametrize('defect', [None, 'customer', 'post', 'source'])
def test_relocated_review_is_bound_to_customer_post_and_source(tmp_path, monkeypatch, defect):
    root = tmp_path / 'clone'
    data = root / 'handover/data'
    data.mkdir(parents=True)
    cache = tmp_path / 'empty-cache'
    source = cache / 'customers/X/corpus.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps([{'post_id': 'X_P001', 'text': 'verified visit'}]))
    anchor = {'customer_id': 'Y' if defect == 'customer' else 'X',
              'bundle_path': 'customers/X/corpus.json', 'sha256': B.sha(source)}
    row = {'status': 'SOURCE_RECONCILED_DISPLAY_ONLY', 'source_anchors': [anchor],
           'post_ids': ['Y_P001' if defect == 'post' else 'X_P001'], 'fact_ids': [],
           'changes': {'list_line': 'verified visit'}}
    manifest = data / 'review.json'
    manifest.write_text(json.dumps({'customers': {'X': row}}))
    config = {'profile_display_review': {'path': 'review.json', 'sha256': B.sha(manifest)}}
    if defect == 'source':
        source.write_text('changed')
    monkeypatch.setattr(B, 'ROOT', root)
    original = manifest.read_bytes()
    if defect:
        with pytest.raises(ValueError, match='DISPLAY_REVIEW_'):
            B.restore_display_review(config, cache)
    else:
        runtime = Path(B.restore_display_review(config, cache))
        assert runtime.parent == cache
        assert json.loads(runtime.read_text())['customers']['X']['source_anchors'][0]['path'] == str(source)
        monkeypatch.setenv('HILLINK_PROFILE_DISPLAY_REVIEW', str(runtime))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from profile_display_review import load
        result = load()['customers']['X']
        assert result['changes']['list_line'] == 'verified visit'
        assert not any(result[k] for k in ['engine_changed', 'semantic_approval', 'thumbnail_approval'])
    assert manifest.read_bytes() == original
