"""sum_to_n: 求 1 到 n 的累加和。"""


def sum_to_n(n: int) -> int:
    """返回 1+2+...+n。"""
    total = 0
    for i in range(n):  # bug: 应该是 range(1, n+1)
        total += i
    return total
