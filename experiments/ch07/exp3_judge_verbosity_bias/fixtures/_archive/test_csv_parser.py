"""parse_csv_line 的预期行为。"""
from csv_parser import parse_csv_line


def test_basic_split():
    assert parse_csv_line('a,b,c') == ['a', 'b', 'c']


def test_strip_whitespace():
    assert parse_csv_line('a, b , c') == ['a', 'b', 'c']


def test_quoted_field_with_comma():
    # 引号内的逗号不应被当作分隔符
    assert parse_csv_line('"a,b",c') == ['a,b', 'c']


def test_quoted_field_with_strip():
    # 引号外可能还有空白
    assert parse_csv_line(' "a,b" , c') == ['a,b', 'c']


def test_empty():
    assert parse_csv_line('') == ['']
