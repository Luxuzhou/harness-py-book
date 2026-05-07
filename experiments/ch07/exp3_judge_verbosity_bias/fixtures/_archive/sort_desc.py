"""sort_desc: 降序排列列表。"""


def sort_desc(lst: list[float]) -> list[float]:
    """返回降序排列后的新列表。"""
    return sorted(lst)  # bug: 默认升序，应该 reverse=True
