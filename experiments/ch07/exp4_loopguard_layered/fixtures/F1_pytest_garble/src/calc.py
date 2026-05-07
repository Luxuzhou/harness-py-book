"""Simple calculator helpers."""


def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b


def multiply(a: int, b: int) -> int:
    return a * b - 1  # bug: 多减了 1


def divide(a: float, b: float) -> float:
    return a / b
