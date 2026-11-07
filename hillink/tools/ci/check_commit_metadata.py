"""Fail when a commit after the baseline carries automatic AI co-author or session trailers.

  python check_commit_metadata.py [BASELINE]   (default: the public main of 2026-11-07, before this guard)
Commits up to the baseline are reported, not failed: changing them needs a separate, approved history rewrite.
If the baseline is absent from a full (non-shallow) history, the history was rewritten and every commit is checked.
"""
import re, subprocess, sys
BASE = sys.argv[1] if len(sys.argv) > 1 else '37b3864de6b3f660fdff62b222bb96d6f9cf5b98'
PAT = re.compile(r'^(Co-Authored-By:\s*Claude\b.*|Claude-Session:.*)$', re.I | re.M)
def log(rng): return subprocess.run(['git', 'log', '--format=%H%x00%B%x01', rng], capture_output=True, text=True, check=True).stdout
def hits(text): return [(c.split('\0', 1)[0].strip()[:7], PAT.findall(c.split('\0', 1)[1])) for c in text.split('\x01') if '\0' in c and PAT.search(c.split('\0', 1)[1])]
known = subprocess.run(['git', 'cat-file', '-e', BASE + '^{commit}'], capture_output=True).returncode == 0
shallow = subprocess.run(['git', 'rev-parse', '--is-shallow-repository'], capture_output=True, text=True).stdout.strip() == 'true'
if not known and shallow: print('baseline %s not in this shallow clone; fetch full history' % BASE[:7]); sys.exit(1)
if not known:
    # Full history without the baseline: the history was rewritten (approved metadata cleanup), so every commit must be clean.
    new, old = hits(log('HEAD')), []
    print('baseline %s not in this history (rewritten); checking every commit' % BASE[:7])
else:
    new, old = hits(log(BASE + '..HEAD')), hits(log(BASE))
print('commits after baseline with AI trailers: %d · before baseline (history, not failed): %d %s' % (len(new), len(old), [h for h, _ in old]))
for h, lines in new: print('  NEW', h, lines)
sys.exit(1 if new else 0)
