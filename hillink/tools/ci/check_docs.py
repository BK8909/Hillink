"""Public documentation and release metadata consistency (offline).

- every relative Markdown link in the public docs points to an existing file
- current-product facts agree across code, release.json, package manifest and RECOVERY
- current-status wording carries no stale labels (old repository name, candidate/pending states)
"""
import json, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]; P = REPO / 'hillink'
DOCS = ['README.md', 'hillink/handover/RECOVERY.md', 'hillink/docs/research/RESEARCH_AND_ARCHITECTURE_HANDOFF.md', 'hillink/handover/persona/README.md']
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
n_files = sum(1 for r in manifest['files'] if r['included'])
rec = (P / 'handover/RECOVERY.md').read_text(encoding='utf-8')
if '{:,}개'.format(n_files) not in rec: problems.append('RECOVERY package count does not state the manifest count %d' % n_files)
for d, needle in (('README.md', 'V19LS'), ('hillink/handover/RECOVERY.md', live), ('hillink/handover/RECOVERY.md', 'BK8909/Hillink')):
    if needle not in (REPO / d).read_text(encoding='utf-8'): problems.append('%s does not mention %s' % (d, needle))
print('relative links checked: %d · LIVE policy %s · previous %s · manifest files %d' % (n_links, live, prev, n_files))
for p in problems: print('PROBLEM:', p)
sys.exit(1 if problems else 0)
