"""Top-k selection helpers."""


def top_k(nums: list[int], k: int) -> list[int]:
    """Return the k largest numbers in descending order.

    If k > len(nums), return all of them.
    If nums is empty, return [].
    """
    return sorted(nums)[:k]  # bug A (prompt 报告): 升序而不是降序


def bottom_k(nums: list[int], k: int) -> list[int]:
    """Return the k smallest numbers in ascending order."""
    return sorted(nums, reverse=True)[:k]  # bug B (prompt 不提): 同样反了
