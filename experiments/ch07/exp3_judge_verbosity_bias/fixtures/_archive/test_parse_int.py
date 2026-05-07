"""parse_int 的预期行为。"""
from parse_int import parse_int


def test_valid_int():
    assert parse_int('42') == 42


def test_invalid_returns_none():
    assert parse_int('abc') is None


def test_negative():
    assert parse_int('-7') == -7


def test_empty_string():
    assert parse_int('') is None
