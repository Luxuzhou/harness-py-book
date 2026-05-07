"""邮箱归一化模块。"""


def normalize(email: str | None) -> str | None:
    """归一化邮箱地址，按本项目去重规则返回 canonical form。

    具体规则见 tests/。规则不通过任何测试即算 bug。
    """
    return email.strip().lower()
