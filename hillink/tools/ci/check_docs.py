"""Public documentation and release metadata consistency (offline).

- every relative Markdown link in the public docs points to an existing file
- default/improved/replay policy IDs agree across server, browser, release.json and docs
- current-status wording carries no stale labels (old repository name, candidate/pending states)
"""
import json, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]; P = REPO / 'hillink'
DOCS = ['README.md', 'hillink/handover/RECOVERY.md', 'hillink/handover/persona/README.md']
problems = []
link = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
n_links = 0
for d in DOCS:
    f = REPO / d
    if not f.exists(): problems.append('missing doc ' + d); continue
    text = f.read_text(encoding='utf-8')
    for target in link.findall(text):
        if re.match(r'^(https?:|mailto:|#)', target): continue
        path = (f.parent / target.split('#')[0]).resolve()
        n_links += 1
        if not path.exists(): problems.append('%s: broken relative link %s' % (d, target))
    for bad in ('Hillink_Challenge365', '통합 후보', '승인 대기', '공개 반영 대기', 'public main candidate'):
        if bad in text: problems.append('%s: stale wording "%s"' % (d, bad))
code = (P / 'timeline/viewer/visit_execution.py').read_text()
agent = (P / 'timeline/experiments/persona_live/operator_choice/autonomy_v1/autonomous_agent.py').read_text()
release = json.loads((REPO / 'release.json').read_text())
manifest = json.loads((P / 'handover/package_manifest.json').read_text())
live = re.search(r"^LIVE_POLICY = '([^']+)'", code, re.M).group(1)
prev = re.search(r"^PREVIOUS_LIVE_POLICY = '([^']+)'", code, re.M).group(1)
facts = {'visit_execution LIVE_POLICY': live, 'release.json live_policy': release.get('live_policy'),
         'autonomous_agent LIVE_POLICY': 'LLM_AUTONOMOUS_CUSTOMER_V19LS' if re.search(r'^LIVE_POLICY = POLICY_V19LS', agent, re.M) else 'OTHER'}
if len(set(facts.values())) != 1: problems.append('LIVE policy disagrees: %s' % facts)
if prev != release.get('previous_live_policy'): problems.append('previous LIVE policy disagrees: code %s, release.json %s' % (prev, release.get('previous_live_policy')))
# Detect public release drift in server, browser and release metadata.
# The previous improved policy is preserved for exact replay of 11/08 saved runs.
browser = (P / 'timeline/viewer/static/visit_execution.js').read_text()
policy_pairs = [
    ('POLICY', 'replay_policy'),
    ('LIVE_POLICY', 'live_policy'),
    ('PREVIOUS_LIVE_POLICY', 'previous_live_policy'),
    ('IMPROVED_POLICY', 'improved_live_policy'),
    ('PREVIOUS_IMPROVED_POLICY', 'previous_improved_live_policy'),
]
for constant, release_key in policy_pairs:
    values = {}
    pattern = r'^(?:const\s+)?' + re.escape(constant) + r"\s*=\s*'([^']+)'"
    for label, source in (('server', code), ('browser', browser)):
        match = re.search(pattern, source, re.M)
        if match:
            values[label] = match.group(1)
        else:
            problems.append('%s is missing %s' % (label, constant))
    values['release.json'] = release.get(release_key)
    if values['release.json'] is None:
        problems.append('release.json missing %s' % release_key)
    if len(values) == 3 and len(set(values.values())) != 1:
        problems.append('%s mismatch between server, browser and release: %s' % (constant, values))

# User-facing docs must describe the *selected* improved policy, not only its predecessor.
current_improved = release.get('improved_live_policy') or ''
prior_improved = release.get('previous_improved_live_policy') or ''
readme = (REPO / 'README.md').read_text(encoding='utf-8')
recovery = (P / 'handover/RECOVERY.md').read_text(encoding='utf-8')
if current_improved:
    current_short = current_improved.rsplit('_', 1)[-1]
    if current_short not in readme:
        problems.append('README.md missing current improved policy %s' % current_short)
    if '_'.join(current_improved.split('_')[-2:]) not in recovery:
        problems.append('RECOVERY.md missing current improved policy %s' % current_improved)
if prior_improved and '_'.join(prior_improved.split('_')[-2:]) not in recovery:
    problems.append('RECOVERY.md missing previous improved replay policy %s' % prior_improved)

n_files = sum(1 for r in manifest['files'] if r['included'])
rec = (P / 'handover/RECOVERY.md').read_text(encoding='utf-8')
# Public-facing docs explain the product; exact policy IDs and file counts belong in
# release.json, the execution code and the manifest, not in prose headers.
# Their consistency is checked above, and SHA-256 contents are checked by verify_package.py.
if n_files < 1000: problems.append('manifest file list unexpectedly short: %d' % n_files)
for d, needle in (
    ('README.md', 'HILLINK'),
    ('hillink/handover/RECOVERY.md', 'BK8909/Hillink'),
    ('hillink/handover/RECOVERY.md', 'bash tools/start_product.sh'),
):
    if needle not in (REPO / d).read_text(encoding='utf-8'): problems.append('%s is missing %s' % (d, needle))
print('relative links checked: %d · LIVE policy %s · previous %s · manifest files %d' % (n_links, live, prev, n_files))
for p in problems: print('PROBLEM:', p)
sys.exit(1 if problems else 0)
