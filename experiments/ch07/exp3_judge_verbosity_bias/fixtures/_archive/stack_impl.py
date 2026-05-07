"""简单 Stack 实现。"""


class Stack:
    def __init__(self) -> None:
        self._items: list = []

    def push(self, item) -> None:
        self._items.append(item)

    def pop(self):
        """弹出并返回栈顶；空栈返回 None。"""
        if not self._items:
            return None
        self._items.pop()  # bug: 没 return

    def peek(self):
        """看栈顶但不弹出；空栈返回 None。"""
        if not self._items:
            return None
        return self._items[0]  # bug: 应该是 [-1]

    def is_empty(self) -> bool:
        return False  # bug: 应该是 not self._items
