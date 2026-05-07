"""Stack 的预期行为。注意：Stack 有多个 bug，pop / peek / is_empty 都需要修。"""
from stack_impl import Stack


def test_pop_returns_top_item():
    s = Stack()
    s.push(1)
    s.push(2)
    assert s.pop() == 2


def test_pop_from_empty_returns_none():
    s = Stack()
    assert s.pop() is None


def test_peek_returns_top_item():
    s = Stack()
    s.push('a')
    s.push('b')
    assert s.peek() == 'b'


def test_is_empty_when_empty():
    s = Stack()
    assert s.is_empty() is True


def test_is_empty_when_filled():
    s = Stack()
    s.push(1)
    assert s.is_empty() is False
