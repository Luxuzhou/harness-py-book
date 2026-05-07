"""LRUCache 的预期行为。"""
from lru_cache import LRUCache


def test_basic_get_put():
    c = LRUCache(2)
    c.put('a', 1)
    c.put('b', 2)
    assert c.get('a') == 1
    assert c.get('b') == 2


def test_eviction_when_full():
    c = LRUCache(2)
    c.put('a', 1)
    c.put('b', 2)
    c.put('c', 3)
    assert c.get('a') is None  # a 应被淘汰


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put('a', 1)
    c.put('b', 2)
    c.get('a')                   # a 变成最近使用
    c.put('c', 3)                # 应淘汰 b
    assert c.get('b') is None
    assert c.get('a') == 1


def test_update_refreshes_recency():
    """put 已存在的 key 也应刷新 recency。"""
    c = LRUCache(2)
    c.put('a', 1)
    c.put('b', 2)
    c.put('a', 99)               # 重新 put a，a 应变成最近使用
    c.put('c', 3)                # 应淘汰 b
    assert c.get('b') is None
    assert c.get('a') == 99


def test_get_missing():
    c = LRUCache(2)
    assert c.get('nope') is None
