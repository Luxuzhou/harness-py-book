"""dedup 的预期行为：依赖 normalize 正确处理 +alias。"""
from src.dedup import count_unique_emails


def test_basic_dedup():
    assert count_unique_emails(['a@x.com', 'A@x.com']) == 1


def test_alias_dedup():
    """Gmail 风格的 +alias 应该被视为同一邮箱。"""
    assert count_unique_emails([
        'user@gmail.com',
        'user+work@gmail.com',
        'user+spam@gmail.com',
    ]) == 1


def test_distinct_emails():
    assert count_unique_emails(['a@x.com', 'b@x.com']) == 2
