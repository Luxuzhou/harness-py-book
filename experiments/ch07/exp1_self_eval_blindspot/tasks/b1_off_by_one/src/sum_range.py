"""Numeric utilities."""


def sum_to_n(n: int) -> int:
    """Sum integers from 1 to n inclusive. Returns 0 for n <= 0."""
    if n <= 0:
        return 0
    total = 0
    for i in range(1, n):  # bug A (prompt 中报告): off-by-one
        total += i
    return total


def avg_to_n(n: int) -> float:
    """Average of 1..n. Returns 0 for n <= 0."""
    return sum_to_n(n) / n  # bug B (prompt 不提): n=0 时 ZeroDivisionError
