"""binary_search 的预期行为。"""
from binary_search import binary_search


def test_found_middle():
    assert binary_search([1, 3, 5, 7, 9], 5) == 2


def test_found_first():
    assert binary_search([1, 3, 5], 1) == 0


def test_found_last():
    assert binary_search([1, 3, 5], 5) == 2


def test_not_found_returns_minus_one():
    assert binary_search([1, 3, 5], 4) == -1


def test_not_found_below_range():
    assert binary_search([1, 3, 5], 0) == -1


def test_not_found_above_range():
    assert binary_search([1, 3, 5], 99) == -1


def test_single_element_found():
    assert binary_search([42], 42) == 0


def test_single_element_not_found():
    assert binary_search([42], 1) == -1


def test_empty_list():
    assert binary_search([], 42) == -1
