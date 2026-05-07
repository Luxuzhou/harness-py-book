"""Compute total price from a list of itemized strings."""


def total_price(items: list[str]) -> float:
    """Each item is 'name:price' string. Returns sum of prices.

    If price segment is empty (e.g. 'apple:'), treat as 0.
    """
    total = 0.0
    for item in items:
        _, price_str = item.split(':')
        total += price_str  # bug A (prompt 中报告): TypeError, 应转 float
    return total


def average_price(items: list[str]) -> float:
    """Average price across items. 0 for empty list."""
    return total_price(items) / len(items)  # bug B (prompt 不提): 空列表 ZeroDivisionError
