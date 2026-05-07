"""report_format 的预期行为。"""
from report_format import format_report


def test_basic_format():
    assert format_report(['Alice', 'BOB', 'Carol']) == 'alice, bob, carol'


def test_with_whitespace():
    assert format_report(['  hello ', 'WORLD']) == 'hello, world'


def test_with_none_should_skip():
    # None 应该被跳过而不是崩溃
    assert format_report(['Alice', None, 'Bob']) == 'alice, bob'


def test_empty_list():
    assert format_report([]) == ''
