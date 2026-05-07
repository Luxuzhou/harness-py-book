"""
聚合 exp1 的 results/raw.jsonl，生成 summary.csv 和图表。
"""
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


def load() -> list[dict]:
    p = RESULTS / 'raw.jsonl'
    if not p.exists():
        print(f'ERROR: {p} 不存在，请先跑 run.py')
        sys.exit(1)
    return [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]


def aggregate(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[(r['compression'], r['observation_turn'])].append(r)
    out = []
    for (comp, turn), items in sorted(groups.items()):
        snrs = [x['snr'] for x in items]
        qs = [x['quality_score'] for x in items if x['quality_score'] >= 0]
        recalls = [x['recall_accuracy'] for x in items if x['recall_accuracy'] >= 0]
        toks = [x['total_tokens'] for x in items]
        # 替代度量：noise_ratio = noise_chars / (noise + useful)。比 SNR 更贴近
        # "工具输出占比"这一工程直觉；即便 SNR 因 assistant 总结膨胀而不降，
        # noise_ratio 仍能反映 tool 字符的绝对主导地位。
        noise_ratios = []
        for x in items:
            tot = x['useful_chars'] + x['noise_chars']
            if tot > 0:
                noise_ratios.append(x['noise_chars'] / tot)
        out.append({
            'compression': comp,
            'turn': turn,
            'n': len(items),
            'snr_mean': round(mean(snrs), 4),
            'snr_std': round(pstdev(snrs), 4) if len(snrs) > 1 else 0.0,
            'noise_ratio_mean': round(mean(noise_ratios), 4) if noise_ratios else None,
            'quality_mean': round(mean(qs), 2) if qs else None,
            'quality_std': round(pstdev(qs), 2) if len(qs) > 1 else 0.0,
            'recall_mean': round(mean(recalls), 2) if recalls else None,
            'tokens_mean': int(mean(toks)),
            'tokens_std': int(pstdev(toks)) if len(toks) > 1 else 0,
            'compression_events_mean': round(mean([x['compression_events'] for x in items]), 2),
        })
    return out


def write_csv(summary: list[dict]):
    if not summary:
        return
    p = RESULTS / 'summary.csv'
    with p.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(f'已写入 {p}')


def plot_curves(summary: list[dict]):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print('未安装 matplotlib，跳过绘图。pip install matplotlib 后 rerun plot.py')
        return

    by_comp = defaultdict(list)
    for r in summary:
        by_comp[r['compression']].append(r)

    # SNR 曲线
    fig, ax = plt.subplots(figsize=(8, 5))
    for comp, rows in by_comp.items():
        rows_sorted = sorted(rows, key=lambda x: x['turn'])
        xs = [r['turn'] for r in rows_sorted]
        ys = [r['snr_mean'] for r in rows_sorted]
        es = [r['snr_std'] for r in rows_sorted]
        ax.errorbar(xs, ys, yerr=es, marker='o', capsize=4, label=f'compression={comp}')
    ax.set_xlabel('observation turn')
    ax.set_ylabel('SNR (useful / total)')
    ax.set_title('Chapter 6 Exp1: Context SNR vs turn')
    ax.set_ylim(0, None)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / 'snr_curve.png', dpi=150)
    plt.close(fig)
    print(f'已写入 {FIGURES / "snr_curve.png"}')

    # Token 曲线：压缩收益最直接的信号——off 线性增长、on 在 turn=10+ 应出现压缩拐点
    fig, ax = plt.subplots(figsize=(8, 5))
    for comp, rows in by_comp.items():
        rows_sorted = sorted(rows, key=lambda x: x['turn'])
        xs = [r['turn'] for r in rows_sorted]
        ys = [r['tokens_mean'] for r in rows_sorted]
        es = [r['tokens_std'] for r in rows_sorted]
        ax.errorbar(xs, ys, yerr=es, marker='^', capsize=4, label=f'compression={comp}')
    ax.axhline(int(6000 * 0.70), linestyle='--', alpha=0.4,
               label='compress threshold (4200)')
    ax.set_xlabel('observation turn')
    ax.set_ylabel('total tokens')
    ax.set_title('Chapter 6 Exp1: Total tokens vs turn')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / 'tokens_curve.png', dpi=150)
    plt.close(fig)
    print(f'已写入 {FIGURES / "tokens_curve.png"}')

    # noise_ratio 曲线：替代 SNR 的工程视角度量
    fig, ax = plt.subplots(figsize=(8, 5))
    for comp, rows in by_comp.items():
        rows_sorted = [r for r in sorted(rows, key=lambda x: x['turn'])
                       if r['noise_ratio_mean'] is not None]
        if not rows_sorted:
            continue
        xs = [r['turn'] for r in rows_sorted]
        ys = [r['noise_ratio_mean'] for r in rows_sorted]
        ax.plot(xs, ys, marker='d', label=f'compression={comp}')
    ax.set_xlabel('observation turn')
    ax.set_ylabel('noise ratio (tool chars / total)')
    ax.set_title('Chapter 6 Exp1: Noise ratio vs turn')
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / 'noise_ratio_curve.png', dpi=150)
    plt.close(fig)
    print(f'已写入 {FIGURES / "noise_ratio_curve.png"}')

    # 质量曲线（如有）
    has_quality = any(r['quality_mean'] is not None for r in summary)
    if has_quality:
        fig, ax = plt.subplots(figsize=(8, 5))
        for comp, rows in by_comp.items():
            rows_sorted = [r for r in sorted(rows, key=lambda x: x['turn']) if r['quality_mean'] is not None]
            if not rows_sorted:
                continue
            xs = [r['turn'] for r in rows_sorted]
            ys = [r['quality_mean'] for r in rows_sorted]
            es = [r['quality_std'] for r in rows_sorted]
            ax.errorbar(xs, ys, yerr=es, marker='s', capsize=4, label=f'compression={comp}')
        ax.set_xlabel('observation turn')
        ax.set_ylabel('probe quality score (1-5)')
        ax.set_title('Chapter 6 Exp1: Recall quality vs turn')
        ax.set_ylim(0, 5.2)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIGURES / 'quality_curve.png', dpi=150)
        plt.close(fig)
        print(f'已写入 {FIGURES / "quality_curve.png"}')


def main():
    rows = load()
    summary = aggregate(rows)
    write_csv(summary)
    plot_curves(summary)
    # 打印一份终端摘要
    print('\n=== summary ===')
    for r in summary:
        print(r)


if __name__ == '__main__':
    main()
