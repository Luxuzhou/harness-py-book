"""celsius_to_f 的预期行为。"""
from celsius_to_f import celsius_to_f


def test_boiling():
    assert celsius_to_f(100) == 212.0


def test_freezing():
    assert celsius_to_f(0) == 32.0


def test_negative():
    assert celsius_to_f(-40) == -40.0
