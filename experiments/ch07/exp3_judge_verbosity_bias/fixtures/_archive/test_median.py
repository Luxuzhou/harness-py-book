"""median 的预期行为。"""
from median import median


def test_odd_count():
    assert median([3, 1, 2]) == 2


def test_empty_returns_none():
    assert median([]) is None


def test_single_element():
    assert median([42]) == 42
