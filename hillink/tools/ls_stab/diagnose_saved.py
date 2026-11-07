"""Offline (no paid call) review of saved LS / V19LS selection calls.

Reads a private run folder (runs/<job>/calls/*.request.json + *.response.json), annotates each LS request
with ls_stability.annotate and runs ls_stability.diagnose on the saved answer. Prints de-identified codes
and fact ids only (no review text) unless --text is given for a private terminal.
Usage: python -I tools/ls_stab/diagnose_saved.py <run_root> [--text]
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'timeline/viewer'))
sys.path.insert(0, str(ROOT / 'timeline/experiments/persona_live'))
from operator_choice.autonomy_v1 import ls_stability as LSS  # noqa: E402


def answer_of(resp):
    a = resp.get('answer')
    if a: return a
    body = resp.get('response_body') or {}
    txt = ''.join(c.get('text', '') for it in body.get('output', []) if it.get('type') == 'message' for c in it.get('content', []) if c.get('type') == 'output_text')
    return json.loads(txt) if txt else None


def lean_of(req):
    msgs = req['request_body']['input']
    out = {}
    for m in msgs[1:]:
        try: out.update(json.loads(m['content']))
        except Exception: pass
    return out


def library_facts():
    lib = json.loads((ROOT / 'timeline/viewer/static/persona_library.json').read_text())
    return {(p.get('pid') or p.get('id')): ((p.get('engine') or {}).get('facts') or {}) for p in lib.get('personas', [])}


def main(root, text=False):
    facts = library_facts()
    rows = []
    for req_path in sorted(Path(root).glob('runs/*/calls/*.request.json')):
        resp_path = Path(str(req_path).replace('.request.json', '.response.json'))
        if not resp_path.exists(): continue
        req = json.loads(req_path.read_text()); resp = json.loads(resp_path.read_text())
        if 'V18LS' not in req_path.name and 'V19LS' not in req_path.name: continue
        raw_lean = lean_of(req); pid = req_path.name.split('_')[0]
        raw = facts.get(pid) or {}
        lean = LSS.annotate(raw_lean, {k: v.get('kind') for k, v in raw.items() if v.get('kind')}, LSS.feature_links(raw, raw_lean.get('candidates')))
        ans = answer_of(resp)
        diag = LSS.diagnose(ans, lean, (lean.get('visit') or {}).get('party_size'))
        recs = [dict(ids=r['fact_ids'], stance=r['stance'], flags=r.get('flags', []), about=r.get('about', []), **({'summary': r['summary']} if text else {}))
                for r in lean['personal'].get('records', []) if r.get('about') or r.get('flags') or r['stance'] in ('혼합', '부정')]
        rows.append(dict(call=req_path.name.replace('.request.json', ''), selected=ans.get('selected_action_id'), basket=ans.get('selected_basket_id'),
                         cited=dict(sup=ans.get('supporting_fact_ids'), counter=ans.get('counterevidence_fact_ids')),
                         diagnostics=diag, marked_records=recs, **({'reason': ans.get('reason')} if text else {})))
    print(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], '--text' in sys.argv)
