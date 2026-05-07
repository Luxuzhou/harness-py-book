"""安全除法。"""


def divide(a: int, b: int) -> float:
    """整数相除返回 float；除数为 0 时返回 0.0。"""
    if b == 0:
        return 0.0
    return a // b  # bug: 应该是 a / b（当前用了整除会丢小数部分）
