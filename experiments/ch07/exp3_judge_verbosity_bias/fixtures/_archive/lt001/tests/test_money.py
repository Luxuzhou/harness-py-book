"""test_money: 通过运行时 case 表驱动，agent 必须读 cases.py 或看 traceback。"""
import pytest

from src.money import format_money
from tests.cases import EXPECTED


@pytest.mark.parametrize('amount,currency', list(EXPECTED.keys()))
def test_format_money(amount, currency):
    expected = EXPECTED[(amount, currency)]
    assert format_money(amount, currency) == expected, (
        f'format_money({amount!r}, {currency!r}) → got incorrect output, '
        f'expected {expected!r}'
    )
