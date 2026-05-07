"""
方案收敛度分析（补充分析脚本）
================================
原实验只测"违反率"，在 DeepSeek-V3 上几乎永远为 0%，区分度差。
本脚本换一个视角：对每组 10 次重复，统计模型使用了多少种不同的
实现方案。预期：
- 负向措辞（禁令）→ 方案发散（模型自己找替代，多种合理做法）
- 正向措辞（指导）→ 方案收敛（模型采用你推荐的那一种）

这个指标捕获了 Anthropic 博客"禁令强于指导"断言的更精确表达：
**指导不是降低违反率，而是收敛实现方案。**

用法:
    python analyze_convergence.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

EXP_DIR = Path(__file__).parent
RESULTS_PATH = EXP_DIR / 'results' / 'results.json'

# 每对规则的"方案分类器"：regex → 方案标签
# 分类器按顺序匹配，第一个命中的即为该次的方案。
# 如果都不命中，归入 "other"。
CLASSIFIERS: dict[str, list[tuple[str, str]]] = {
    'os_system': [
        ('subprocess_run', r'subprocess\.run\('),
        ('subprocess_check_output', r'subprocess\.check_output\('),
        ('subprocess_popen', r'subprocess\.Popen\('),
        ('os_listdir', r'os\.listdir\('),
        ('pathlib_iterdir', r'\.iterdir\(\)'),
        ('os_system_VIOLATION', r'os\.system\('),
        ('os_popen', r'os\.popen\('),
    ],
    'eval_usage': [
        ('ast_literal_eval', r'ast\.literal_eval\('),
        ('json_loads', r'json\.loads\('),
        ('eval_VIOLATION', r'\beval\s*\('),
        ('manual_parse', r'(\.strip\(\)\.split|re\.(findall|match))'),
    ],
    'bare_except': [
        ('specific_multi', r'except\s*\(\s*(ValueError|TypeError)'),
        ('specific_value_error', r'except\s+ValueError'),
        ('specific_type_error', r'except\s+TypeError'),
        ('pre_check_no_except', r'(isdigit\(\)|\.lstrip\(.\-.\))'),
        ('bare_except_VIOLATION', r'except\s*:'),
        ('except_exception_VIOLATION', r'except\s+Exception\s*[:\)]'),
    ],
    'print_debug': [
        ('logging_module', r'logging\.(debug|info|warning|error)'),
        ('logger_instance', r'\b(logger|log)\.(debug|info|warning|error)'),
        ('list_accumulator', r'intermediate_results\s*=\s*\[\]|debug_log\s*=\s*\[\]|_trace\s*=\s*\[\]'),
        ('return_debug_info', r'return\s*\{[^}]*result[^}]*,\s*[\'"](debug|trace|log)'),
        ('print_VIOLATION', r'\bprint\s*\('),
    ],
    'sql_injection': [
        ('param_qmark', r"execute\s*\(\s*['\"][^'\"]*\?[^'\"]*['\"]\s*,"),
        ('param_named', r"execute\s*\(\s*['\"][^'\"]*:[a-zA-Z]"),
        ('param_percent', r"execute\s*\(\s*['\"][^'\"]*%s[^'\"]*['\"]\s*,"),
        ('fstring_sql_VIOLATION', r"f['\"]SELECT.*\{"),
        ('concat_sql_VIOLATION', r"['\"]\s*\+\s*username"),
    ],
}


def classify(pair_id: str, code: str) -> str:
    """根据分类器判定方案标签。第一条命中的 rule 作为标签。"""
    rules = CLASSIFIERS.get(pair_id, [])
    for label, pattern in rules:
        if re.search(pattern, code):
            return label
    return 'other'


def convergence_score(method_counts: Counter) -> float:
    """用赫芬达尔指数（HHI）度量收敛度。
    HHI = Σ (p_i)^2，其中 p_i 是方案 i 的占比。
    - HHI=1：完全收敛（10 次都同一方案）
    - HHI=0.1：完全发散（10 次各用一种方案）
    返回值越大越收敛。
    """
    total = sum(method_counts.values())
    if total == 0:
        return 0.0
    return sum((c / total) ** 2 for c in method_counts.values())


def main() -> int:
    raw = json.loads(RESULTS_PATH.read_text(encoding='utf-8'))
    # 按 (pair_id, wording) 分组
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in raw:
        if r.get('error'):
            continue
        # code_preview 只保留前 400 字节，需要改用原始 code 才准确
        # 但 results.json 当前只存了 preview，用它足够分类（代码通常开头就能判定）
        groups[(r['pair_id'], r['wording'])].append(r)

    print('=' * 72)
    print('方案收敛度分析（100 次重复实验）')
    print('=' * 72)
    print()
    print('收敛度 = 赫芬达尔指数 HHI = Σ (方案占比)²')
    print('  1.00: 完全收敛（10次都同一方案）')
    print('  0.10: 完全发散（10次各一种方案）')
    print()

    # 汇总表
    summary_rows: list[dict] = []
    for pair_id in CLASSIFIERS:
        print(f'\n=== {pair_id} ===')
        for wording in ('negative', 'positive'):
            records = groups.get((pair_id, wording), [])
            if not records:
                continue
            counts: Counter[str] = Counter()
            for r in records:
                label = classify(pair_id, r['code_preview'])
                counts[label] += 1
            score = convergence_score(counts)
            n_distinct = len(counts)

            print(f'  [{wording}]  n={len(records)}  独特方案数={n_distinct}  HHI收敛度={score:.2f}')
            for label, c in counts.most_common():
                marker = ' ⚠ VIOLATION' if 'VIOLATION' in label else ''
                pct = c / len(records) * 100
                print(f'    - {label:<30s} {c:>2}次 ({pct:>5.1f}%){marker}')

            summary_rows.append({
                'pair_id': pair_id,
                'wording': wording,
                'n': len(records),
                'distinct_methods': n_distinct,
                'hhi': round(score, 3),
                'top_method': counts.most_common(1)[0][0] if counts else '',
                'top_method_share': counts.most_common(1)[0][1] / len(records) if counts else 0,
            })

    # 汇总对比
    print('\n' + '=' * 72)
    print('汇总：每对规则的 negative vs positive 收敛度对比')
    print('=' * 72)
    print(f'{"pair_id":<18}{"neg独特":>8}{"neg HHI":>10}{"pos独特":>8}{"pos HHI":>10}{"HHI差":>10}')
    for pair_id in CLASSIFIERS:
        neg = next((r for r in summary_rows if r['pair_id'] == pair_id and r['wording'] == 'negative'), None)
        pos = next((r for r in summary_rows if r['pair_id'] == pair_id and r['wording'] == 'positive'), None)
        if not (neg and pos):
            continue
        diff = pos['hhi'] - neg['hhi']
        arrow = '↑正向更收敛' if diff > 0.05 else ('↓负向更收敛' if diff < -0.05 else '≈差异不显著')
        print(
            f'{pair_id:<18}{neg["distinct_methods"]:>8}{neg["hhi"]:>10.2f}'
            f'{pos["distinct_methods"]:>8}{pos["hhi"]:>10.2f}{diff:>+10.2f}  {arrow}'
        )

    # 整体均值
    neg_hhis = [r['hhi'] for r in summary_rows if r['wording'] == 'negative']
    pos_hhis = [r['hhi'] for r in summary_rows if r['wording'] == 'positive']
    if neg_hhis and pos_hhis:
        print()
        print(f'整体 HHI 均值：negative={sum(neg_hhis)/len(neg_hhis):.2f}  '
              f'positive={sum(pos_hhis)/len(pos_hhis):.2f}')

    # 保存到 summary.json
    out = EXP_DIR / 'results' / 'convergence_summary.json'
    out.write_text(
        json.dumps(summary_rows, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'\n详细数据已保存到 {out}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
