"""find_max 的预期行为。"""
from find_max import find_max


def test_normal_list():
    assert find_max([3, 1, 4, 1, 5, 9, 2, 6]) == 9


def test_none_returns_none():
    assert find_max(None) is None


def test_empty_returns_none():
    assert find_max([]) is None


def test_single_element():
    assert find_max([42]) == 42
