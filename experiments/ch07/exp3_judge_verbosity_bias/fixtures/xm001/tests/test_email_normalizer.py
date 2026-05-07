"""email_normalizer 的预期行为。"""
from src.email_normalizer import normalize


def test_basic_lowercase():
    assert normalize('Foo@bar.com') == 'foo@bar.com'


def test_strip_whitespace():
    assert normalize('  foo@bar.com  ') == 'foo@bar.com'


def test_none_returns_none():
    assert normalize(None) is None
