"""concat_id 的预期行为。"""
from concat_id import concat_id


def test_basic_concat():
    assert concat_id(prefix='X', n=42) == 'X42'


def test_zero_id():
    assert concat_id(prefix='user_', n=0) == 'user_0'


def test_negative_id():
    assert concat_id(prefix='id_', n=-1) == 'id_-1'
