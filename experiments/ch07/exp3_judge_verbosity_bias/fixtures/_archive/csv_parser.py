"""CSV 行解析。"""


def parse_csv_line(line: str) -> list[str]:
    """把一行 CSV 解析成字段列表。
    要求：
    - 普通逗号分隔："a,b,c" → ["a", "b", "c"]
    - 字段两侧空白要 strip："a, b , c" → ["a", "b", "c"]
    - 引号包围的字段，引号内的逗号不视为分隔符：'"a,b",c' → ["a,b", "c"]
    """
    return line.split(',')  # bug: 既不 strip 也不处理引号
