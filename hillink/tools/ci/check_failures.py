"""Strict check of a `pytest -rA` log against a classified list (historical_reference.tsv, or /dev/null for "no failure allowed").

Fails when: the final summary is missing (crash, timeout, interruption), any collection/setup ERROR occurs,
fewer tests passed than the floor, a failing test id is not in the list, a listed id fails a different number
of times, a listed id no longer fails (update the list deliberately), or the summary total disagrees.
Usage: python check_failures.py PYTEST_LOG KNOWN_TSV [--min-passed N]
"""
import argparse, re, sys
from collections import Counter
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument('log'); ap.add_argument('known'); ap.add_argument('--min-passed', type=int, default=820)
a = ap.parse_args()
log = Path(a.log).read_text(errors='replace').splitlines()
known, cause = {}, {}
for line in Path(a.known).read_text().splitlines():
    if not line.strip() or line.startswith('#'): continue
    n, tid, why = line.split('\t', 2); known[tid] = int(n); cause[tid] = why
problems = []
summary = next((l for l in reversed(log) if re.match(r'^=*\s*.*\b(passed|failed|error|no tests ran)\b.* in [\d.]+s', l.strip('= '))), None)
if not summary: problems.append('no pytest final summary (collection crash, interruption or timeout)')
counts = {k: int(v) for v, k in re.findall(r'(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|subtests passed|deselected)', summary or '')}
if 'interrupted' in (summary or '').lower() or any(re.search(r'Interrupted:|!!+ .*(Interrupted|stopping)', l) for l in log):
    problems.append('pytest run was interrupted')
if counts.get('error', 0) or counts.get('errors', 0): problems.append('collection/setup errors: %s' % (counts.get('error') or counts.get('errors')))
failed = Counter()
for l in log:
    m = re.match(r'^(?:SUB)?FAILED(?:\(.*?\))? (\S+?::\S+)', l)
    if m: failed[m.group(1)] += 1
    m = re.match(r'^ERROR (\S+)', l)
    if m: problems.append('ERROR ' + m.group(1))
new = {t: n for t, n in failed.items() if t not in known}
wrong = {t: (known[t], failed[t]) for t in known if failed.get(t) and failed[t] != known[t]}
fixed = [t for t in known if not failed.get(t)]
passed = counts.get('passed', 0)
print('pytest summary:', (summary or '(missing)').strip('= '))
print('passed %d (floor %d) · failed %d · skipped %d' % (passed, a.min_passed, counts.get('failed', 0), counts.get('skipped', 0)))
if passed < a.min_passed: problems.append('passed %d is below the floor %d (tests not collected?)' % (passed, a.min_passed))
if summary and counts.get('failed', 0) != sum(failed.values()): problems.append('summary failed=%d but %d FAILED lines' % (counts.get('failed', 0), sum(failed.values())))
print('\nlisted differences by cause:')
for t, n in known.items():
    print('  %-34s %d/%d  %s' % (cause[t].split(' ')[0], failed.get(t, 0), n, t.split('::', 1)[-1]))
if wrong: problems += ['count changed for %s: expected %d, got %d' % (t, e, g) for t, (e, g) in wrong.items()]
if fixed: problems += ['standing failure now passes, update the list deliberately: ' + t for t in fixed]
print('\nnew failures: %d' % len(new))
for t, n in new.items(): print('  NEW', n, t)
if new or problems:
    for p in problems: print('PROBLEM:', p)
    sys.exit(1)
print('OK: only the classified standing failures, no new regression')
