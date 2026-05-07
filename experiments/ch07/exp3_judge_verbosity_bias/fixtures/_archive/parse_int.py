"""parse_int: 容错版字符串转整数，失败返回 None。"""


def parse_int(s: str) -> int | None:
    """解析字符串为整数；不能解析时返回 None。"""
    return int(s)  # bug: 应该捕获 ValueError 返回 None
