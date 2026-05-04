"""
对比重构前后的 metrics 并生成 markdown 报告。

用法：
    python compare.py
"""
from __future__ import annotations

import json
from pathlib import Path

EXP_DIR = Path(__file__).parent
RESULTS = EXP_DIR / 'results'


def pct(before, after):
    if before in (0, None) or after in (None, -1.0):
        return ''
    if before == 0:
        return ''
    delta = (after - before) / before * 100
    arrow = '↓' if delta < 0 else '↑'
    return f"{arrow}{abs(delta):.1f}%"


def main():
    bp = RESULTS / 'before.json'
    ap = RESULTS / 'after.json'
    if not bp.exists() or not ap.exists():
        print(f"需要先跑：python run.py before / after。当前缺失：")
        if not bp.exists():
            print(f"  - {bp}")
        if not ap.exists():
            print(f"  - {ap}")
        return

    before = json.loads(bp.read_text(encoding='utf-8'))
    after = json.loads(ap.read_text(encoding='utf-8'))

    rows = [
        ('java_file_count', '.java 文件数', '↑ 拆分应增加'),
        ('total_loc', '总行数', '可能略减'),
        ('god_service_loc', 'CpPlanService 行数', '↓ 显著'),
        ('avg_method_loc', '平均方法长度', '↓'),
        ('pmd_warnings', 'PMD 警告数（0=未跑）', '↓'),
        ('test_line_coverage', '测试行覆盖率（-1=未跑）', '保持或↑'),
    ]

    out = []
    out.append("# 重构前后量化对照\n\n")
    out.append("| 指标 | 重构前 | 重构后 | Δ | 期望方向 |\n")
    out.append("|------|--------|--------|---|----------|\n")
    for key, label, expect in rows:
        b = before.get(key)
        a = after.get(key)
        out.append(f"| {label} | {b} | {a} | {pct(b, a)} | {expect} |\n")

    out.append("\n## 解读\n\n")
    out.append("（待人工补充：哪几项达到预期？哪几项反而恶化？为什么？）\n")

    md = RESULTS / 'comparison.md'
    md.write_text(''.join(out), encoding='utf-8')
    print(f"写入 {md}\n")
    print(''.join(out))


if __name__ == '__main__':
    main()
