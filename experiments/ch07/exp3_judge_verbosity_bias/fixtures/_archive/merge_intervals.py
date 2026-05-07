"""合并重叠区间。"""


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """传入 [(start, end), ...]，返回合并重叠后的区间列表。"""
    result = [intervals[0]]                      # bug: 空列表会 IndexError
    for cur in intervals[1:]:                    # bug: 没 sort 前提
        last = result[-1]
        if cur[0] < last[1]:                     # bug: 应该 <= 让 [1,3]+[3,5] 合并
            result[-1] = (last[0], max(last[1], cur[1]))
        else:
            result.append(cur)
    return result
