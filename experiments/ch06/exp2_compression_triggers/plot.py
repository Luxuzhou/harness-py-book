"""生成 exp2 的聚合表和图表。"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

EXP_DIR = Path(__file__).parent
RESULTS = EXP_DIR / 'results'
FIGURES = RESULTS / 'figures'
FIGURES.mkdir(exist_ok=True)


def load():
    p = RESULTS / 'raw.jsonl'
    if not p.exists():
        print(f'ERROR: 缺少 {p}，请先跑 run.py')
        sys.exit(1)
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]


def aggregate(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[(r['preserve'], r['threshold'])].append(r)
    out = []
    for (p, th), items in sorted(groups.items()):
        summary_all = [x for r in items for x in r['summary_ratios']]
        out.append({
            'preserve': p, 'threshold': th, 'n': len(items),
            'micro_mean': round(mean(r['micro_count'] for r in items), 2),
            'snip_mean': round(mean(r['snip_count'] for r in items), 2),
            'compact_mean': round(mean(r['compact_count'] for r in items), 2),
            'reactive_mean': round(mean(r['reactive_count'] for r in items), 2),
            'api_errors_mean': round(mean(r['api_errors'] for r in items), 2),
            'llm_calls_mean': round(mean(r['total_llm_calls'] for r in items), 2),
            'tokens_final_mean': int(mean(r['token_curve'][-1] if r['token_curve'] else 0 for r in items)),
            'tokens_peak_mean': int(mean(max(r['token_curve'] or [0]) for r in items)),
            'summary_ratio_mean': round(mean(summary_all), 3) if summary_all else None,
            'summary_ratio_std': round(pstdev(summary_all), 3) if len(summary_all) > 1 else 0.0,
        })
    return out


def write_csv(summary):
    p = RESULTS / 'summary.csv'
    if not summary:
        return
    with p.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(f'已写入 {p}')


def plot_all(rows, summary):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print('未安装 matplotlib，跳过绘图。')
        return

    # Token 曲线（按配置分组，取 seed 均值）
    fig, ax = plt.subplots(figsize=(10, 6))
    by_cfg = defaultdict(list)
    for r in rows:
        by_cfg[(r['preserve'], r['threshold'])].append(r['token_curve'])
    for (p, th), curves in sorted(by_cfg.items()):
        if not curves:
            continue
        max_len = max(len(c) for c in curves)
        avg = []
        for t in range(max_len):
            vals = [c[t] for c in curves if t < len(c)]
            avg.append(mean(vals) if vals else 0)
        ax.plot(range(1, len(avg) + 1), avg,
                label=f'p={p}, th={th}', alpha=0.8)
    ax.set_xlabel('step')
    ax.set_ylabel('total tokens after compression')
    ax.set_title('Chapter 6 Exp2: Token curve by config')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / 'token_curve_by_config.png', dpi=150)
    plt.close(fig)
    print(f'已写入 {FIGURES / "token_curve_by_config.png"}')

    # 触发次数堆叠柱状图
    fig, ax = plt.subplots(figsize=(10, 6))
    labels = [f'p={r["preserve"]}\nth={r["threshold"]}' for r in summary]
    micro = [r['micro_mean'] for r in summary]
    snip = [r['snip_mean'] for r in summary]
    compact = [r['compact_mean'] for r in summary]
    reactive = [r['reactive_mean'] for r in summary]
    x = range(len(labels))
    ax.bar(x, micro, label='microcompact')
    ax.bar(x, snip, bottom=micro, label='snip')
    ax.bar(x, compact, bottom=[a + b for a, b in zip(micro, snip)], label='compact')
    ax.bar(x, reactive,
           bottom=[a + b + c for a, b, c in zip(micro, snip, compact)],
           label='reactive')
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel('trigger count (mean)')
    ax.set_title('Chapter 6 Exp2: Compression trigger breakdown')
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / 'trigger_breakdown.png', dpi=150)
    plt.close(fig)
    print(f'已写入 {FIGURES / "trigger_breakdown.png"}')

    # 摘要比例分布
    ratios = [x for r in rows for x in r['summary_ratios']]
    if ratios:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(ratios, bins=20, edgecolor='black')
        ax.axvline(0.15, linestyle='--', label='15% 下限')
        ax.axvline(0.20, linestyle='--', label='20% 上限')
        ax.set_xlabel('summary / compressed content ratio')
        ax.set_ylabel('occurrences')
        ax.set_title('Chapter 6 Exp2: Compaction summary ratio')
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIGURES / 'summary_ratio.png', dpi=150)
        plt.close(fig)
        print(f'已写入 {FIGURES / "summary_ratio.png"}')


def main():
    rows = load()
    summary = aggregate(rows)
    write_csv(summary)
    plot_all(rows, summary)
    print('\n=== summary ===')
    for r in summary:
        print(r)


if __name__ == '__main__':
    main()
