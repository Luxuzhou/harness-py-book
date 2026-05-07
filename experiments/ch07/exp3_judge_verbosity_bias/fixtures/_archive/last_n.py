"""last_n: 取列表末尾 n 个元素。"""


def last_n(lst: list, n: int) -> list:
    """返回列表的最后 n 个元素，n 大于列表长度时返回整个列表。"""
    return lst[-n - 1:-1]  # bug: 应该是 lst[-n:]
