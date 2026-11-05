"""Count and serialized-byte bounds for server-owned snapshots."""
from collections import OrderedDict
import json

class BoundedRecords(OrderedDict):
    def __init__(self, limit, max_bytes):
        super().__init__()
        self.limit, self.max_bytes = limit, max_bytes
        self.sizes = {}
        self.bytes = 0

    def __setitem__(self, key, value):
        size = len(json.dumps(value, ensure_ascii=False, default=str).encode())
        if size > self.max_bytes:
            raise ValueError('RESULT_TOO_LARGE')
        if key in self:
            self.pop(key)
        while self and (len(self) >= self.limit or self.bytes + size > self.max_bytes):
            self.popitem(last=False)
        super().__setitem__(key, value)
        self.sizes[key] = size
        self.bytes += size

    def pop(self, key, *default):
        if key in self:
            self.bytes -= self.sizes.pop(key)
        return super().pop(key, *default)

    def popitem(self, last=True):
        key = next(reversed(self)) if last else next(iter(self))
        return key, self.pop(key)

    def clear(self):
        super().clear()
        self.sizes.clear()
        self.bytes = 0
