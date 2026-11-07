"""Compare a pytest -rA log with the classified standing failures. Exit 1 on any new failing test id."""
import re, sys
from pathlib import Path
log, known = Path(sys.argv[1]).read_text(errors='replace'), Path(sys.argv[2]).read_text()
known = {l.strip() for l in known.splitlines() if l.strip() and not l.startswith('#')}
failed = set()
for line in log.splitlines():
    m = re.match(r'^(?:SUB)?FAILED(?:\([^)]*\))? (\S+)', line) or re.match(r'^ERROR (\S+)', line)
    if m: failed.add(m.group(1))
new, fixed = sorted(failed - known), sorted(known - failed)
summary = [l for l in log.splitlines() if re.search(r'\d+ (passed|failed)', l)][-1:]
print('pytest:', summary[0] if summary else '(no summary)')
print('standing failures still failing: %d / %d' % (len(known & failed), len(known)))
if fixed: print('standing failures now passing:', *fixed, sep='\n  ')
if new:
    print('NEW FAILURES:', *new, sep='\n  '); sys.exit(1)
print('new failures: 0')
