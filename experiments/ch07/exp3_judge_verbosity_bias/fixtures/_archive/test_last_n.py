"""last_n 的预期行为。"""
from last_n import last_n


def test_last_two():
    assert last_n([1, 2, 3, 4, 5], 2) == [4, 5]


def test_last_three():
    assert last_n([10, 20, 30, 40], 3) == [20, 30, 40]


def test_last_one():
    assert last_n([1, 2, 3], 1) == [3]


def test_n_larger_than_list():
    assert last_n([1, 2], 5) == [1, 2]
