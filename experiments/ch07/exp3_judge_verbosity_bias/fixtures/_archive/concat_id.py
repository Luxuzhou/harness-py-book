"""concat_id: 拼接前缀字符串和数字 ID。"""


def concat_id(prefix: str, n: int) -> str:
    """返回 'prefix-N' 格式的拼接结果。"""
    return prefix + n  # bug: int 不能直接和 str 相加，应该 prefix + str(n)
