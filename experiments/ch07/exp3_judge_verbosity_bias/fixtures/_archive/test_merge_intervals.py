"""merge_intervals 的预期行为。"""
from merge_intervals import merge_intervals


def test_basic_overlap():
    assert merge_intervals([(1, 3), (2, 6)]) == [(1, 6)]


def test_no_overlap():
    assert merge_intervals([(1, 2), (3, 4)]) == [(1, 2), (3, 4)]


def test_unsorted_input():
    assert merge_intervals([(3, 5), (1, 2)]) == [(1, 2), (3, 5)]


def test_touching_intervals():
    # [1,3] 和 [3,5] 首尾相接，应合并
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_empty():
    assert merge_intervals([]) == []


def test_single():
    assert merge_intervals([(1, 5)]) == [(1, 5)]
