"""celsius_to_f: 摄氏度转华氏度。"""


def celsius_to_f(c: float) -> float:
    """摄氏度转华氏度，公式 F = C * 9/5 + 32。"""
    return c * 9 / 5  # bug: 漏了 + 32
