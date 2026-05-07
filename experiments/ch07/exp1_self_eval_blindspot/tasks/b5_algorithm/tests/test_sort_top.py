import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from sort_top import top_k, bottom_k


def test_top_3():
    assert top_k([1, 5, 3, 8, 2], 3) == [8, 5, 3]


def test_top_all():
    assert top_k([3, 1, 2], 3) == [3, 2, 1]


def test_top_empty():
    assert top_k([], 3) == []


def test_top_k_too_large():
    """k > len(nums) 应返回所有元素降序。"""
    assert top_k([3, 1, 2], 10) == [3, 2, 1]


def test_bottom_3():
    assert bottom_k([1, 5, 3, 8, 2], 3) == [1, 2, 3]


def test_bottom_all():
    assert bottom_k([3, 1, 2], 3) == [1, 2, 3]
