"""sum_to_n 的预期行为。"""
from sum_to_n import sum_to_n


def test_sum_to_5():
    assert sum_to_n(5) == 15


def test_sum_to_10():
    assert sum_to_n(10) == 55


def test_sum_to_1():
    assert sum_to_n(1) == 1


def test_sum_to_0():
    assert sum_to_n(0) == 0
