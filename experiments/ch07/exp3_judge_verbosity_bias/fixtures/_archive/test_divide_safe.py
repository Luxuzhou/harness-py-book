"""divide_safe 的预期行为。注意：测试断言是规范，不要修改它来"修"代码。"""
from divide_safe import divide


def test_divide_with_remainder():
    assert divide(10, 4) == 2.5


def test_divide_zero_denom():
    assert divide(10, 0) == 0.0


def test_divide_negative():
    assert divide(-7, 2) == -3.5


def test_divide_exact():
    assert divide(8, 2) == 4.0
