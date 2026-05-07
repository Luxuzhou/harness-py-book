"""
一次性脚本：为公众号文章生成 2 张核心补充图（基于修 bug 后的新数据）
=====================================================================
文章发出后可删除。

产物：
  results/figures/_article_recall_tradeoff.png    recall 曲线对比（off 线性增长 vs on 达峰后下降）
  results/figures/_article_3d_tradeoff_card.png   三维权衡归一对比卡（token/recall/quality）

数据来源：results/raw.jsonl（exp1 修 bug 后的 30 trial 新数据）
"""
from __future__ import annotations

import json
import statistics as stats
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

EXP_DIR = Path(__file__).parent
RAW = EXP_DIR / 'results' / 'raw.jsonl'
FIGS = EXP_DIR / 'results' / 'figures'
FIGS.mkdir(parents=True, exist_ok=True)

rows = [json.loads(l) for l in RAW.read_text(encoding='utf-8').splitlines() if l.strip()]
print(f'已加载 {len(rows)} 条 trial 数据')


# ======== 图 1：recall 曲线对比 ========
# X: turn; Y: recall_mean; 两条线 off/on
by_comp_turn = defaultdict(lambda: defaultdict(list))
for r in rows:
    by_comp_turn[r['compression']][r['observation_turn']].append(r['recall_accuracy'])

fig, ax = plt.subplots(figsize=(9, 5.5))
palette = {'off': '#E74C3C', 'on': '#27AE60'}
for comp in ['off', 'on']:
    turns = sorted(by_comp_turn[comp].keys())
    means = [stats.mean(by_comp_turn[comp][t]) for t in turns]
    stds = [stats.pstdev(by_comp_turn[comp][t]) if len(by_comp_turn[comp][t]) > 1 else 0
            for t in turns]
    ax.errorbar(turns, means, yerr=stds, marker='o', markersize=11,
                linewidth=2.5, capsize=5,
                label=f'compression={comp}', color=palette[comp])

ax.annotate('off 路径线性增长\n3.67 → 16.33（turn=3→20）',
            xy=(20, 16.33), xytext=(12, 14.5),
            fontsize=10.5,
            arrowprops=dict(arrowstyle='->', color='#C0392B', alpha=0.6),
            bbox=dict(boxstyle='round', facecolor='#FADBD8', alpha=0.85))
ax.annotate('on 路径在 turn=15 达峰后回落\n压缩 10 次以上，recall 从 12 跌到 8.33',
            xy=(20, 8.33), xytext=(9, 4),
            fontsize=10.5,
            arrowprops=dict(arrowstyle='->', color='#1E8449', alpha=0.6),
            bbox=dict(boxstyle='round', facecolor='#D5F5E3', alpha=0.85))

ax.set_xlabel('observation turn（读了多少个模块）', fontsize=12)
ax.set_ylabel('recall_accuracy（正确引用的模块数）', fontsize=12)
ax.set_title('综合问答 recall 随 turn 的走势：off 持续吸收、on 被压缩"精简"',
             fontsize=13, pad=12)
ax.set_ylim(0, 19)
ax.set_xticks([3, 6, 10, 15, 20])
ax.grid(True, alpha=0.3)
ax.legend(loc='upper left', fontsize=11)
plt.tight_layout()
out1 = FIGS / '_article_recall_tradeoff.png'
plt.savefig(out1, dpi=150)
plt.close()
print(f'[1/2] {out1.name}')


# ======== 图 2：三维权衡归一化对比卡（turn=20）========
# 三列：tokens / recall / quality
# 以 off 为 100% 基线，on 显示百分比

off20 = {r['compression']: r for r in rows if r['compression'] == 'off' and r['observation_turn'] == 20}
on20 = {r['compression']: r for r in rows if r['compression'] == 'on' and r['observation_turn'] == 20}
off_trials = [r for r in rows if r['compression'] == 'off' and r['observation_turn'] == 20]
on_trials = [r for r in rows if r['compression'] == 'on' and r['observation_turn'] == 20]

off_tokens = stats.mean(r['total_tokens'] for r in off_trials)
on_tokens = stats.mean(r['total_tokens'] for r in on_trials)
off_recall = stats.mean(r['recall_accuracy'] for r in off_trials)
on_recall = stats.mean(r['recall_accuracy'] for r in on_trials)
off_quality = stats.mean(r['quality_score'] for r in off_trials)
on_quality = stats.mean(r['quality_score'] for r in on_trials)

# 归一化（off = 100）
dims = ['total_tokens\n(越低越省)', 'recall\n(越高覆盖面越广)', 'quality\n(越高越精准)']
off_norm = [100, 100, 100]
on_norm = [
    on_tokens / off_tokens * 100,
    on_recall / off_recall * 100,
    on_quality / off_quality * 100,
]

fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(len(dims))
width = 0.38

bars_off = ax.bar(x - width/2, off_norm, width,
                  label='compression=off (基线 100%)',
                  color='#E74C3C', edgecolor='black', linewidth=0.8)
bars_on = ax.bar(x + width/2, on_norm, width,
                 label='compression=on',
                 color='#27AE60', edgecolor='black', linewidth=0.8)

# 真实数值标注
truth_off = [f'{off_tokens:.0f}', f'{off_recall:.2f}', f'{off_quality:.2f}']
truth_on = [f'{on_tokens:.0f}', f'{on_recall:.2f}', f'{on_quality:.2f}']
for i, (b, v) in enumerate(zip(bars_off, truth_off)):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 3,
            v, ha='center', fontsize=10.5, fontweight='bold')
for i, (b, v) in enumerate(zip(bars_on, truth_on)):
    h = b.get_height()
    ax.text(b.get_x() + b.get_width() / 2, h + 3,
            v, ha='center', fontsize=10.5, fontweight='bold')

# 箭头标注（off 到 on 的变化方向）
changes = [on_norm[0] - 100, on_norm[1] - 100, on_norm[2] - 100]
for i, ch in enumerate(changes):
    sign = '+' if ch >= 0 else ''
    color = '#1E8449' if ch >= 0 else '#C0392B'
    ax.text(x[i] + width/2 + 0.15, max(100, on_norm[i]) + 16,
            f'{sign}{ch:.0f}%', ha='left', va='bottom',
            fontsize=11, color=color, fontweight='bold')

ax.set_ylabel('相对 off 基线的百分比（%）', fontsize=12)
ax.set_title('turn=20 时压缩的三维权衡：省 86% token、精准度 +25%、覆盖面 -49%',
             fontsize=13, pad=12)
ax.set_xticks(x)
ax.set_xticklabels(dims, fontsize=11)
ax.axhline(100, linestyle='--', color='gray', alpha=0.5)
ax.set_ylim(0, 180)
ax.grid(axis='y', alpha=0.3)
ax.legend(loc='upper right', fontsize=10.5)
plt.tight_layout()
out2 = FIGS / '_article_3d_tradeoff_card.png'
plt.savefig(out2, dpi=150)
plt.close()
print(f'[2/2] {out2.name}')

print(f'\n完成：2 张新图都写入 {FIGS}')
