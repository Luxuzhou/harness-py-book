"""报告格式化。"""


def _normalize(items: list[str]) -> list[str]:
    """把字符串列表归一化（去空白 + 小写）。"""
    return [item.strip().lower() for item in items]  # bug: items 含 None 时崩


def format_report(items: list) -> str:
    """把字符串列表格式化为逗号分隔的报告。"""
    normalized = _normalize(items)
    return ', '.join(normalized)
