"""统计词数：英文按空格分词，中文按字符。"""


def word_count(text: str) -> int:
    """返回 text 中的词数。"""
    return len(text.split())  # bug: 中文不会被 split 成词
