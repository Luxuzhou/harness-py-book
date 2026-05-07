import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from sum_range import sum_to_n, avg_to_n


def test_sum_zero():
    assert sum_to_n(0) == 0


def test_sum_one():
    assert sum_to_n(1) == 1


def test_sum_small():
    assert sum_to_n(5) == 15


def test_sum_ten():
    assert sum_to_n(10) == 55


def test_avg_normal():
    assert avg_to_n(5) == 3.0


def test_avg_zero():
    """avg_to_n(0) 应该返回 0，但当前实现会 ZeroDivisionError。"""
    assert avg_to_n(0) == 0
