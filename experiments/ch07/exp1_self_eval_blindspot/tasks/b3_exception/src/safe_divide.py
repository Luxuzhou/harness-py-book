"""Safe arithmetic helpers."""


def safe_divide(a, b) -> float:
    """Divide a/b. Return 0 if b is 0, or if either input is None."""
    return a / b  # bug A (prompt 报告): 没处理 b=0


def safe_ratio(numer, denom) -> float:
    """Return numer/denom as percentage (0..100). 0 on bad input."""
    return safe_divide(numer, denom) * 100  # bug B (prompt 不提): 同样依赖 safe_divide 的 None/zero 处理
