"""Shared local HTTP and cache boundary; independent of customer policy."""
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit
from http.server import ThreadingHTTPServer
import threading

MAX_BODY = 1024 * 1024
READ_TIMEOUT = 10

class RequestError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def cache_key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+\-]{0,219}', value) or '..' in value:
        raise RequestError('INVALID_CACHE_KEY')
    return value


def cache_path(root, key, suffix='.json', prefix=''):
    cache_key(key)
    root = Path(root)
    if root.is_symlink():
        raise RequestError('CACHE_LINK_FORBIDDEN', 403)
    p = root / (prefix + key + suffix)
    if p.is_symlink() or p.resolve().parent != root.resolve():
        raise RequestError('CACHE_LINK_FORBIDDEN', 403)
    return p


def cache_family(root, key):
    # Includes inputs AND outputs opened by the legacy engine/export subprocesses.
    for suffix in ('.json', '.progress.json', '.guests.jsonl', '.guests.jsonl.gz', '.cap.pkl', '.l5.csv'):
        cache_path(root, key, suffix)
    for prefix in ('flow_', 'band_'):
        cache_path(root, key, prefix=prefix)


def authority(value, port):
    try:
        u = urlsplit('http://' + value)
        return (not u.username and not u.password and not u.path and not u.query and not u.fragment
                and u.hostname in ('localhost', '127.0.0.1', '::1') and (u.port or 80) == port)
    except (ValueError, TypeError):
        return False


def guard(handler):
    hosts = handler.headers.get_all('Host', [])
    port = handler.server.server_port
    if len(hosts) != 1 or not authority(hosts[0], port):
        raise RequestError('UNTRUSTED_HOST', 403)
    origins = handler.headers.get_all('Origin', [])
    if len(origins) > 1:
        raise RequestError('UNTRUSTED_ORIGIN', 403)
    if origins:
        u = urlsplit(origins[0])
        if u.scheme != 'http' or u.path or u.query or u.fragment or u.netloc != hosts[0] or not authority(u.netloc, port):
            raise RequestError('UNTRUSTED_ORIGIN', 403)
    if handler.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site'):
        raise RequestError('CROSS_SITE_REQUEST', 403)


def body(handler):
    if handler.headers.get('Transfer-Encoding'):
        raise RequestError('UNSUPPORTED_TRANSFER_ENCODING')
    lengths = handler.headers.get_all('Content-Length', [])
    if len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,10}', lengths[0]):
        raise RequestError('INVALID_CONTENT_LENGTH', 411 if not lengths else 400)
    size = int(lengths[0])
    if size > MAX_BODY:
        raise RequestError('REQUEST_TOO_LARGE', 413)
    if handler.headers.get_content_type() != 'application/json':
        raise RequestError('JSON_CONTENT_TYPE_REQUIRED', 415)
    def expire():
        try:handler.connection.shutdown(socket.SHUT_RDWR)
        except OSError:pass
    timer = threading.Timer(READ_TIMEOUT, expire)
    timer.daemon = True
    timer.start()
    try:
        raw = handler.rfile.read(size)
        if len(raw) != size:
            raise RequestError('INCOMPLETE_BODY')
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise RequestError('INVALID_JSON') from None
    except (socket.timeout, TimeoutError):
        raise RequestError('BODY_TIMEOUT', 408) from None
    finally:
        timer.cancel()
    if not isinstance(value, dict):
        raise RequestError('JSON_OBJECT_REQUIRED')
    for field in ('personas', 'customers'):
        if field in value and (not isinstance(value[field], list) or len(value[field]) > 28
                or any(not isinstance(x, str) or len(x) > 80 for x in value[field])):
            raise RequestError('INVALID_CUSTOMERS')
    if value.get('crowd'):
        cache_key(value['crowd'])
    return value


class LocalHTTPServer(ThreadingHTTPServer):
    """Bound idle connections as well as expensive execution slots."""
    daemon_threads = True
    def __init__(self, *args, **kwargs):
        self.connections = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            request.settimeout(READ_TIMEOUT)
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()
