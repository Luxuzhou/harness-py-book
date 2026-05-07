import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from stats import mean_or_zero, max_or_zero


def test_mean_normal():
    assert mean_or_zero([1, 2, 3, 4, 5]) == 3


def test_mean_empty():
    """空列表应返回 0。"""
    assert mean_or_zero([]) == 0


def test_mean_with_none():
    """含 None 的列表应过滤后平均。"""
    assert mean_or_zero([1, None, 3, None, 5]) == 3


def test_max_normal():
    assert max_or_zero([1, 5, 2]) == 5


def test_max_empty():
    """max 空列表应返回 0。"""
    assert max_or_zero([]) == 0


def test_max_with_none():
    """max 含 None 应过滤再取最大。"""
    assert max_or_zero([1, None, 7, None]) == 7
