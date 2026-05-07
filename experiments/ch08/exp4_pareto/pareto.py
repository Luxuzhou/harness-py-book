"""
Pareto 前沿可视化
==================
读取 run.py 输出的 pareto_summary.json，用 matplotlib 绘制
Accuracy × Cost 散点图，标记 Pareto 前沿。

用法：
    python pareto.py                           # 使用最新结果
    python pareto.py results/pareto_summary.json  # 指定文件
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP_DIR = Path(__file__).parent
DEFAULT_SUMMARY = EXP_DIR / 'results' / 'pareto_summary.json'


def load_data(path: Path) -> dict:
    if not path.exists():
        print(f"未找到结果文件: {path}")
        print("请先运行: python run.py --smoke")
        sys.exit(1)
    return json.loads(path.read_text(encoding='utf-8'))


def format_label(pt: dict) -> str:
    name = pt['subject_name']
    ver = pt['subject_version']
    short = {'system_prompt': 'SP', 'tool_description': 'TD'}
    return f"{short.get(name, name)} {ver}"


def render_table(data: dict) -> str:
    """Generate markdown-ready table for the chapter."""
    lines = [
        "| 配置 | n | First-call Acc | Policy Pass | Forbidden Hit | Cost($) | Avg Calls | 前沿 |",
        "|------|---|:-------------:|:----------:|:------------:|:------:|:--------:|:----:|",
    ]
    for pt in data['points']:
        label = format_label(pt)
        frontier = '◆' if pt.get('on_frontier') else ''
        lines.append(
            f"| {label} | {pt['n']} | {pt['first_call_acc']:.1%} "
            f"| {pt['policy_pass_rate']:.1%} "
            f"| {pt['forbidden_call_rate']:.1%} "
            f"| ${pt['avg_cost_usd']:.5f} "
            f"| {pt['avg_tool_calls']:.1f} | {frontier} |"
        )
    return '\n'.join(lines)


def main():
    summary_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SUMMARY
    data = load_data(summary_path)

    print("=" * 70)
    print("Pareto 前沿分析结果")
    print("=" * 70)
    print()
    print(render_table(data))
    print()

    # 生成 matplotlib 图表
    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))

        frontier_names = {f"{p['subject_name']}/{p['subject_version']}"
                          for p in data['frontier']}
        colors = {'system_prompt': '#2196F3', 'tool_description': '#FF9800'}
        markers = {'v1': 'o', 'v2': 's'}

        for pt in data['points']:
            name = pt['subject_name']
            ver = pt['subject_version']
            label = format_label(pt)
            on_frontier = f"{name}/{ver}" in frontier_names

            ax.scatter(
                pt['avg_cost_usd'], pt['first_call_acc'],
                c=colors.get(name, '#666'),
                marker=markers.get(ver, 'o'),
                s=180 if on_frontier else 100,
                edgecolors='black' if on_frontier else 'none',
                linewidths=1.5,
                zorder=5 if on_frontier else 2,
                label=label if pt is data['points'][0] or pt is data['points'][1]
                      or (name == 'tool_description' and ver == 'v1') else "",
            )

            # 标签偏移
            offset = (0.002, 0.02) if name == 'system_prompt' else (-0.002, -0.03)
            ax.annotate(label, (pt['avg_cost_usd'], pt['first_call_acc']),
                        xytext=offset, textcoords='offset fontsize',
                        fontsize=9, fontweight='bold' if on_frontier else 'normal')

        # Pareto 前沿连线
        frontier_pts = sorted(
            [pt for pt in data['points'] if pt.get('on_frontier')],
            key=lambda p: (p['avg_cost_usd'], -p['first_call_acc']),
        )
        if len(frontier_pts) >= 2:
            fx = [p['avg_cost_usd'] for p in frontier_pts]
            fy = [p['first_call_acc'] for p in frontier_pts]
            ax.plot(fx, fy, '--', color='#4CAF50', alpha=0.6, linewidth=1.5,
                    label='Pareto Frontier', zorder=3)

        # 被支配区域填充（前沿以下区域）
        if frontier_pts:
            fx_all = [p['avg_cost_usd'] for p in frontier_pts]
            fy_all = [p['first_call_acc'] for p in frontier_pts]
            ax.fill_between(fx_all, fy_all, 0, alpha=0.04, color='#4CAF50')

        ax.set_xlabel('Average Cost per Task (USD)')
        ax.set_ylabel('First-call Accuracy')
        ax.set_title('Accuracy × Cost Pareto Frontier')
        ax.set_xlim(left=0)
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='lower right', fontsize=8)

        # 标注 Pareto 最优方向
        ax.annotate('Pareto optimal →', xy=(0.7, 0.15), xycoords='axes fraction',
                    fontsize=10, color='#4CAF50', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

        out_path = EXP_DIR / 'results' / 'pareto_frontier.png'
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存: {out_path}")

        # Also save as PDF for print-quality
        pdf_path = EXP_DIR / 'results' / 'pareto_frontier.pdf'
        fig.savefig(pdf_path, bbox_inches='tight')
        print(f"PDF 已保存: {pdf_path}")

    except ImportError:
        print("matplotlib 未安装，跳过图表生成。")
        print("安装: pip install matplotlib")
    except Exception as e:
        print(f"图表生成失败: {e}")


if __name__ == '__main__':
    main()
