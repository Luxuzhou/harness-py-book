"""邮箱去重。依赖 email_normalizer。"""
from src.email_normalizer import normalize


def count_unique_emails(emails: list[str]) -> int:
    """统计唯一邮箱数（按归一化后比较）。"""
    return len(set(normalize(e) for e in emails))
