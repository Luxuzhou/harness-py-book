"""
一次性脚本：从 Claude Code session log 提取 context 增长曲线
================================================================
文章发出后可删除。

目标：生成"context 随时间增长 + Chroma 50K rot 门槛"的对比图，
作为公众号文章 hook 的核心配图。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

SESSION_LOG = Path.home() / '.claude' / 'projects' / 'D--Working-Tools------01-----06-Harness-----' / 'ce8fb61d-ac60-44b8-b3bc-b29aa512724a.jsonl'

EXP_DIR = Path(__file__).parent
FIGS = EXP_DIR / 'results' / 'figures'
FIGS.mkdir(parents=True, exist_ok=True)

events = [json.loads(l) for l in SESSION_LOG.read_text(encoding='utf-8').splitlines() if l.strip()]
print(f'总事件数: {len(events)}')

# 提取每个 assistant response 的 timestamp + context 大小
points = []
for e in events:
    if e.get('type') != 'assistant':
        continue
    msg = e.get('message', {})
    usage = msg.get('usage', {})
    if not usage:
        continue
    ctx = usage.get('input_tokens', 0) + usage.get('cache_read_input_tokens', 0) + usage.get('cache_creation_input_tokens', 0)
    cache_read = usage.get('cache_read_input_tokens', 0)
    total = ctx
    ts = e.get('timestamp', '')
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            points.append({
                'dt': dt,
                'ctx': ctx,
                'cache_read': cache_read,
                'cache_hit_rate': cache_read / ctx if ctx else 0,
            })
        except Exception:
            pass

print(f'含 usage 的 assistant response: {len(points)}')
print(f'首次: {points[0]["dt"]}  ctx={points[0]["ctx"]:,}')
print(f'末次: {points[-1]["dt"]}  ctx={points[-1]["ctx"]:,}')
print(f'单次峰值: {max(p["ctx"] for p in points):,}')

# 图 1：context 增长 + Chroma 门槛
fig, ax = plt.subplots(figsize=(11, 5.8))
xs = [p['dt'] for p in points]
ys = [p['ctx'] for p in points]

ax.plot(xs, ys, linewidth=1.2, color='#2E86C1', alpha=0.7)
ax.fill_between(xs, 0, ys, alpha=0.15, color='#2E86C1')

# Chroma 的 rot 门槛
ax.axhline(50_000, linestyle='--', color='#E74C3C', linewidth=1.8,
           label='Chroma 研究：1M 窗口模型在 50K tokens 开始 rot')
ax.axhline(200_000, linestyle=':', color='#F39C12', linewidth=1.5,
           label='Claude Opus 经典 200K 窗口上限（老模型）')

ax.annotate(f'单次请求峰值\n{max(p["ctx"] for p in points):,} tokens',
            xy=(points[-1]['dt'], points[-1]['ctx']),
            xytext=(points[-1]['dt'], points[-1]['ctx'] - 120_000),
            fontsize=11, ha='right',
            arrowprops=dict(arrowstyle='->', color='black'),
            bbox=dict(boxstyle='round', facecolor='#FCF3CF', alpha=0.95))

ax.annotate('Chroma 的 rot 门槛',
            xy=(xs[len(xs) // 4], 50_000),
            xytext=(xs[len(xs) // 4], 150_000),
            fontsize=10.5, color='#C0392B',
            arrowprops=dict(arrowstyle='->', color='#C0392B', alpha=0.6),
            bbox=dict(boxstyle='round', facecolor='#FADBD8', alpha=0.8))

ax.set_ylabel('单次请求 context 大小（tokens）', fontsize=12)
ax.set_title('这篇文章写出时的 Claude Code session context 增长（14.5 小时、517 次请求）',
             fontsize=13, pad=12)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=xs[0].tzinfo))
ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
ax.grid(True, alpha=0.3)
ax.legend(loc='upper left', fontsize=10)
ax.set_ylim(0, max(ys) * 1.1)
plt.tight_layout()
out1 = FIGS / '_article_session_ctx_growth.png'
plt.savefig(out1, dpi=150)
plt.close()
print(f'[1/2] {out1.name}')

# 图 2：cache 命中率演化
fig, ax = plt.subplots(figsize=(11, 4.5))
cache_rates = [p['cache_hit_rate'] * 100 for p in points]

ax.plot(xs, cache_rates, linewidth=1.2, color='#27AE60', alpha=0.85)
ax.axhline(88.6, linestyle='--', color='gray', alpha=0.6,
           label='05 文章里的稳态命中率 88.6%')
overall = sum(p['cache_read'] for p in points) / max(sum(p['ctx'] for p in points), 1) * 100
ax.axhline(overall, linestyle=':', color='#1E8449', linewidth=1.8,
           label=f'本 session 累计命中率 {overall:.1f}%')

ax.set_ylabel('cache 命中率（%）', fontsize=12)
ax.set_title('Prompt cache 命中率：97.5% 的幕后救场', fontsize=13, pad=12)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=xs[0].tzinfo))
ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
ax.grid(True, alpha=0.3)
ax.legend(loc='lower right', fontsize=10)
ax.set_ylim(0, 105)
plt.tight_layout()
out2 = FIGS / '_article_session_cache_hit.png'
plt.savefig(out2, dpi=150)
plt.close()
print(f'[2/2] {out2.name}')

# 额外：终端可打印的核心统计表
print()
print('=== 核心统计（文章用）===')
start_dt = points[0]['dt']
end_dt = points[-1]['dt']
duration_hrs = (end_dt - start_dt).total_seconds() / 3600
total_ctx = sum(p['ctx'] for p in points)
total_cache = sum(p['cache_read'] for p in points)
print(f'持续时间: {duration_hrs:.1f} 小时')
print(f'assistant 响应次数: {len(points)}')
print(f'累计输入（含 cache）: {total_ctx:,} tokens')
print(f'累计 cache 命中: {total_cache:,} tokens')
print(f'整体 cache 命中率: {total_cache/total_ctx*100:.1f}%')
print(f'单次请求峰值: {max(p["ctx"] for p in points):,} tokens')
print(f'穿越 Chroma 50K 门槛的请求数: {sum(1 for p in points if p["ctx"] > 50_000)}/{len(points)}')
print(f'首次穿越 50K 的时刻: {next((p["dt"] for p in points if p["ctx"] > 50_000), None)}')
