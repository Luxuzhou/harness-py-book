"""avg_score: 计算字符串形式分数列表的平均分。"""


def avg_score(scores: list[str]) -> float:
    """传入字符串分数列表，返回平均分。"""
    return sum(scores) / len(scores)  # bug: sum 不能直接对字符串求和
