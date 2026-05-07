"""配置值解析工具。"""


def parse_bool(text: str) -> bool:
    """解析布尔字面量，如 'True' / 'False'。"""
    return eval(text.strip().capitalize())


def parse_number(text: str) -> float:
    """解析数字或简单表达式，如 '3.14' / '1+2'。"""
    return eval(text.strip())


def parse_list(text: str) -> list:
    """解析列表字面量，如 '[1, 2, 3]'。"""
    return eval(text.strip())
