"""工具函数测试。"""

from utils import helper_foo, parse_number

def test_helper_foo():
    assert helper_foo("  hi  ") == "hi"


def test_parse_number():
    assert parse_number("42") == 42
