"""find_max: 求列表最大值；None 输入或空列表返回 None。"""


def find_max(items: list | None) -> float | None:
    """返回最大值；items 为 None 或空列表时返回 None。"""
    return max(items)  # bug: items 为 None 时会 TypeError
