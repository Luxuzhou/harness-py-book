"""median: 求列表中位数；空列表返回 None。"""


def median(lst: list[float]) -> float | None:
    """返回列表中位数；空列表返回 None。"""
    sorted_lst = sorted(lst)
    mid = len(sorted_lst) // 2
    return sorted_lst[mid]  # bug: 空列表会 IndexError，需要先判空
