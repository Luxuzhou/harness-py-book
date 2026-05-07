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
    
    # 过滤掉空行、注释行和仅包含空白的行
    filtered_lines = []
    for line in lines:
        # 跳过空行
        if not line:
            continue
        # 跳过仅包含空白的行
        if line.strip() == '':
            continue
        # 跳过注释行（以 # 开头，忽略前导空白）
        if line.lstrip().startswith('#'):
            continue
        # 保留原始行
        filtered_lines.append(line)
    
    # BUG: 未过滤空行，空行会被当作一条记录解析
    # 此外对注释行（以 # 开头）也没有处理
    if has_header and filtered_lines:
        header = [h.strip() for h in filtered_lines[0].split(',')]
        rows = []
        for line in filtered_lines[1:]:
            values = [v.strip() for v in line.split(',')]
            rows.append(dict(zip(header, values)))
        return rows
    return [[v.strip() for v in line.split(',')] for line in filtered_lines]
