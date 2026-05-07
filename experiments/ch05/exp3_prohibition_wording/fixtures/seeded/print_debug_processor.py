"""批处理工具，处理过程输出调试信息。"""


def process_items(items: list) -> list:
    """处理整数列表，返回绝对值。"""
    results = []
    for item in items:
        print(f"Processing: {item}")
        result = abs(item)
        print(f"Result: {result}")
        results.append(result)
    return results


def process_strings(items: list) -> list:
    """处理字符串列表，返回去空白版本。"""
    results = []
    for item in items:
        print(f"Stripping: {item!r}")
        results.append(item.strip())
    return results
