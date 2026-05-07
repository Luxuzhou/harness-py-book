import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from safe_divide import safe_divide, safe_ratio


def test_normal():
    assert safe_divide(10, 2) == 5


def test_zero_denom():
    """b=0 应返回 0，而不是抛 ZeroDivisionError."""
    assert safe_divide(5, 0) == 0


def test_none_a():
    """a=None 应返回 0。"""
    assert safe_divide(None, 3) == 0


def test_none_b():
    """b=None 应返回 0。"""
    assert safe_divide(5, None) == 0


def test_ratio_normal():
    assert safe_ratio(1, 4) == 25.0


def test_ratio_zero_denom():
    """ratio 也要在 denom=0 时安全返回 0。"""
    assert safe_ratio(5, 0) == 0
