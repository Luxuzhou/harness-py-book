"""
综合分析：clean 模式 + seeded 模式
===================================
对比"无诱导"和"有诱导上下文"两种场景下，禁令 vs 指导措辞的实际效力。

读取 results/results.json（clean，原实验）和 results/results_seeded.json（B 阶段新增）
输出：违反率+收敛度的二维对比表。

用法:
    python analyze_combined.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

EXP_DIR = Path(__file__).parent
CLEAN_PATH = EXP_DIR / 'results' / 'results.json'
SEEDED_PATH = EXP_DIR / 'results' / 'results_seeded.json'

# 复用 analyze_convergence.py 的分类器
from analyze_convergence import CLASSIFIERS, classify, convergence_score  # noqa: E402


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


def summarize(records: list[dict], pair_id: str, wording: str) -> dict:
    """返回该 (pair, wording) 组的汇总指标。"""
    group = [r for r in records if r['pair_id'] == pair_id and r['wording'] == wording and not r.get('error')]
    if not group:
        return {}
    n = len(group)
    violations = sum(1 for r in group if r['violated'])
    complied = sum(1 for r in group if r['complied_with_alternative'])
    labels: Counter[str] = Counter()
    for r in group:
        labels[classify(pair_id, r['code_preview'])] += 1
    return {
        'n': n,
        'violation_rate': violations / n * 100,
        'compliance_rate': complied / n * 100,
        'distinct_methods': len(labels),
        'hhi': convergence_score(labels),
        'top_method': labels.most_common(1)[0][0] if labels else '',
        'top_method_share': labels.most_common(1)[0][1] / n if labels else 0,
    }


def print_block(title: str, data: dict) -> None:
    print(f'\n{title}')
    print('-' * len(title))
    if not data:
        print('(无数据)')
        return
    print(
        f'  n={data["n"]:>3} | 违反率={data["violation_rate"]:>5.1f}% | '
        f'采用替代率={data["compliance_rate"]:>5.1f}% | '
        f'独特方案={data["distinct_methods"]} | HHI={data["hhi"]:.2f} | '
        f'主流方案: {data["top_method"]} ({data["top_method_share"]*100:.0f}%)'
    )


def main() -> int:
    clean = load(CLEAN_PATH)
    seeded = load(SEEDED_PATH)

    if not clean and not seeded:
        print('ERROR: 没有找到任何结果数据。')
        return 1

    print('=' * 78)
    print('实验三综合对比：clean（无诱导） vs seeded（诱导上下文）')
    print('=' * 78)
    print(f'clean records:  {len(clean)}')
    print(f'seeded records: {len(seeded)}')

    for pair_id in CLASSIFIERS:
        print(f'\n{"=" * 78}')
        print(f'【{pair_id}】')
        print('=' * 78)
        for wording in ('negative', 'positive'):
            clean_data = summarize(clean, pair_id, wording)
            seeded_data = summarize(seeded, pair_id, wording)
            print_block(f'[{wording}] clean', clean_data)
            print_block(f'[{wording}] seeded', seeded_data)

    # 整体交叉对比表
    print(f'\n{"=" * 78}')
    print('违反率矩阵（行=pair，列=4种组合）')
    print('=' * 78)
    header = f'{"pair":<18}{"clean/neg":>12}{"clean/pos":>12}{"seeded/neg":>12}{"seeded/pos":>12}'
    print(header)
    print('-' * len(header))
    for pair_id in CLASSIFIERS:
        cn = summarize(clean, pair_id, 'negative')
        cp = summarize(clean, pair_id, 'positive')
        sn = summarize(seeded, pair_id, 'negative')
        sp = summarize(seeded, pair_id, 'positive')

        def fmt(d: dict) -> str:
            return f'{d["violation_rate"]:>10.1f}%' if d else f'{"N/A":>11}'

        print(f'{pair_id:<18}{fmt(cn)}{fmt(cp)}{fmt(sn)}{fmt(sp)}')

    # 关键对比：seeded 下 negative vs positive 的违反率差
    print(f'\n{"=" * 78}')
    print('诱导上下文下（seeded）的关键对比')
    print('=' * 78)
    print(f'{"pair":<18}{"neg 违反率":>14}{"pos 违反率":>14}{"差":>10}  结论')
    print('-' * 78)
    for pair_id in CLASSIFIERS:
        sn = summarize(seeded, pair_id, 'negative')
        sp = summarize(seeded, pair_id, 'positive')
        if not (sn and sp):
            continue
        diff = sn['violation_rate'] - sp['violation_rate']
        if abs(diff) < 10:
            verdict = '≈ 措辞差异不显著'
        elif diff > 10:
            verdict = '↓ 正向指导更有效（违反率更低）'
        else:
            verdict = '↑ 负向禁令更有效（违反率更低）'
        print(
            f'{pair_id:<18}{sn["violation_rate"]:>12.1f}%{sp["violation_rate"]:>13.1f}%{diff:>+9.1f}%  {verdict}'
        )

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
