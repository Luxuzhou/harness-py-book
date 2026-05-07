"""有序列表的二分搜索。"""


def binary_search(arr: list[int], target: int) -> int:
    """返回 target 在 arr 中的索引；未找到返回 -1。"""
    lo, hi = 0, len(arr) - 1
    while lo < hi:                # bug: 应该 lo <= hi（否则单元素列表必漏）
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return 0                      # bug: 应该 -1（找不到错把 0 当结果）
