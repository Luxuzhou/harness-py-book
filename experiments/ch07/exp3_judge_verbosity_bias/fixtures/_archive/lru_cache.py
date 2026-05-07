"""定容量 LRU 缓存。"""
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._d: OrderedDict = OrderedDict()

    def get(self, key):
        if key not in self._d:
            return None
        self._d.move_to_end(key)
        return self._d[key]

    def put(self, key, value):
        if key in self._d:
            self._d[key] = value           # bug: 没 move_to_end，recency 没刷新
            return
        self._d[key] = value
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)
