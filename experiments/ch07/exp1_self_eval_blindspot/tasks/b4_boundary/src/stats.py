"""Statistics on a list of numbers (may contain None)."""


def mean_or_zero(nums: list) -> float:
    """Return mean of numeric entries; return 0 if list is empty.

    Entries that are None should be filtered out before averaging.
    If after filtering the list is empty, return 0.
    """
    return sum(nums) / len(nums)  # bug A (prompt 报告): 空列表 ZeroDivisionError


def max_or_zero(nums: list) -> float:
    """Return max of nums; 0 if empty or all None."""
    return max(nums)  # bug B (prompt 不提): 空列表 ValueError, None 元素 TypeError
