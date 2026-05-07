"""货币格式化。多个细微 bug 共存。"""


def format_money(amount, currency='USD'):
    """格式化金额。具体格式约定见 tests/cases.py 中的 EXPECTED 字典。

    实现需要满足所有 cases 的输入→输出。
    """
    # buggy impl: 漏 thousand sep / 漏补零 / 漏负号位置 / 漏 currency 切换
    return f'${amount}'
