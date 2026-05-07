"""word_count 的预期行为。"""
from word_count import word_count


def test_english_simple():
    assert word_count('hello world') == 2


def test_english_multiple_spaces():
    assert word_count('a b c d e') == 5


def test_chinese_simple():
    assert word_count('你好世界') == 4


def test_mixed():
    assert word_count('hello 世界') == 3


def test_empty():
    assert word_count('') == 0


def test_chinese_with_punctuation():
    # 标点符号不算词
    assert word_count('你好，世界！') == 4
