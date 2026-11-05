"""One bounded execution budget for synchronous HTTP and background jobs."""
from contextlib import contextmanager
import os
import signal
import subprocess
import threading

_LIMIT = threading.BoundedSemaphore(4)
_LOCAL = threading.local()

class Busy(RuntimeError):
    pass

@contextmanager
def slot():
    nested = getattr(_LOCAL, 'held', False)
    if not nested and not _LIMIT.acquire(blocking=False):
        raise Busy('EXECUTION_CAPACITY_FULL')
    _LOCAL.held = True
    try:
        yield
    finally:
        _LOCAL.held = nested
        if not nested:
            _LIMIT.release()


def run(args, *, input=None, capture_output=False, timeout=300, **kwargs):
    """Kill the owned process group on timeout, including day-engine children."""
    with slot():
        if capture_output:
            kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if input is not None:
            kwargs['stdin'] = subprocess.PIPE
        with subprocess.Popen(args, start_new_session=True, **kwargs) as p:
            try:
                out, err = p.communicate(input, timeout=timeout)
            except BaseException:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.communicate()
                raise
            return subprocess.CompletedProcess(args, p.returncode, out, err)

# Full 28-customer multi-day traces exceed 16 MiB. Serialized payload bounds.
MAX_VISIT_RESULT_BYTES = 192 * 1024 * 1024
MAX_RETAINED_RESULT_BYTES = 384 * 1024 * 1024
