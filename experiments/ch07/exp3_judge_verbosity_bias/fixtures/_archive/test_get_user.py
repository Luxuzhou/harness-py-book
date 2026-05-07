"""get_user 的预期行为。"""
from get_user import get_user


def test_existing_user():
    users = {1: {'name': 'Alice'}, 2: {'name': 'Bob'}}
    assert get_user(users, 1) == {'name': 'Alice'}


def test_missing_returns_none():
    assert get_user(users={}, uid=1) is None


def test_missing_in_populated_dict():
    users = {1: {'name': 'Alice'}}
    assert get_user(users, 999) is None
