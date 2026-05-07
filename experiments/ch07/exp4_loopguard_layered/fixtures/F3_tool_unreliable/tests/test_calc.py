import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from calc import multiply


def test_basic():
    assert multiply(3, 4) == 12


def test_one():
    assert multiply(1, 5) == 5


def test_zero():
    assert multiply(0, 7) == 0
