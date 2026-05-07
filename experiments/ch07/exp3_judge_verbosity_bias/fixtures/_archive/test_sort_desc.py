"""sort_desc 的预期行为。"""
from sort_desc import sort_desc


def test_basic_desc():
    assert sort_desc([3, 1, 4, 1, 5]) == [5, 4, 3, 1, 1]


def test_already_desc():
    assert sort_desc([5, 4, 3, 2, 1]) == [5, 4, 3, 2, 1]


def test_empty():
    assert sort_desc([]) == []


def test_single():
    assert sort_desc([42]) == [42]
