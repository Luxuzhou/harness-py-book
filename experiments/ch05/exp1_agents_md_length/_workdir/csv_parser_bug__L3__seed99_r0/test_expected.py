"""parse_csv 的预期行为。修复后所有测试必须通过。"""
from csv_parser import parse_csv


def test_skip_empty_lines_with_header():
    text = 'name,age\nAlice,30\n\nBob,25\n'
    result = parse_csv(text, has_header=True)
    assert len(result) == 2
    assert result[0] == {'name': 'Alice', 'age': '30'}
    assert result[1] == {'name': 'Bob', 'age': '25'}


def test_skip_empty_lines_without_header():
    text = '1,2\n\n3,4\n'
    result = parse_csv(text, has_header=False)
    assert result == [['1', '2'], ['3', '4']]


def test_skip_comment_lines():
    text = 'name,age\n# this is a comment\nAlice,30\n# trailing comment\n'
    result = parse_csv(text, has_header=True)
    assert result == [{'name': 'Alice', 'age': '30'}]


def test_trailing_newline():
    text = 'a,b\n1,2\n'
    result = parse_csv(text, has_header=True)
    assert len(result) == 1
    assert result[0] == {'a': '1', 'b': '2'}


def test_whitespace_only_line_skipped():
    text = 'x,y\n1,2\n   \n3,4\n'
    result = parse_csv(text, has_header=True)
    assert len(result) == 2
