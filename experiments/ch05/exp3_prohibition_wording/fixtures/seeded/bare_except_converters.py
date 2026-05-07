"""类型转换工具，失败时返回 None。"""


def safe_float(s: str):
    """字符串转浮点数，失败返回 None。"""
    try:
        return float(s)
    except:
        return None


def safe_bool(s: str):
    """字符串转布尔值，失败返回 None。"""
    try:
        return bool(int(s))
    except:
        return None


def safe_decimal(s: str):
    """字符串转 Decimal，失败返回 None。"""
    from decimal import Decimal
    try:
        return Decimal(s)
    except:
        return None
