import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from price_total import total_price, average_price


def test_total_empty():
    assert total_price([]) == 0


def test_total_single():
    assert total_price(['apple:1.5']) == 1.5


def test_total_multiple():
    assert total_price(['apple:1.5', 'bread:2.5', 'milk:3.0']) == 7.0


def test_total_empty_price():
    """空 price 字段应当 0 处理。"""
    assert total_price(['apple:1.5', 'sample:']) == 1.5


def test_avg_normal():
    assert average_price(['a:2.0', 'b:4.0']) == 3.0


def test_avg_empty():
    """空列表应返回 0，而不是抛 ZeroDivisionError。"""
    assert average_price([]) == 0
