"""简易 CSV 解析器。存在空行处理相关的bug。"""
from __future__ import annotations


def parse_csv(text: str, has_header: bool = True) -> list[dict] | list[list[str]]:
    """将 CSV 文本解析为 dict 列表（带表头）或 list 列表（无表头）。

    Args:
        text: CSV 原始文本
        has_header: 第一行是否为表头

    Returns:
        has_header=True 时返回 list[dict]，否则返回 list[list[str]]
    """
    lines = text.splitlines()
    
    # 过滤掉空行、注释行和仅含空白的行
    def should_skip(line: str) -> bool:
        return line == '' or line.startswith('#') or line.strip() == ''
    
    if has_header and lines:
        # 确保表头不被过滤
        header_line = lines[0]
        header = [h.strip() for h in header_line.split(',')]
        rows = []
        for line in lines[1:]:
            if should_skip(line):
                continue
            values = [v.strip() for v in line.split(',')]
            rows.append(dict(zip(header, values)))
        return rows
    
    # 无表头的情况：过滤所有行
    filtered_lines = [line for line in lines if not should_skip(line)]
    return [[v.strip() for v in line.split(',')] for line in filtered_lines]
