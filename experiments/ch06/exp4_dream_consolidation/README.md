# 实验四：Dream 整理的量化效果

对应书稿 **6.4.3 离线 Memory 去重与结构化整理**。

## 研究问题

> 对 10 份不同风格的真实 Memory 文件跑 Dream 的规则式整理（去重 + 相对日期
> 转换 + 裁剪），能把文件压到多小？哪些条目被合并了？哪些相对日期被转换？

章节第 685-705 行展示了一个"47 行压到 22 行"的对比案例。这一案例需要用
可复现的脚本重新跑一遍，并且扩展到多份 Memory 文件，以防止单样例的偏差。

## 外部对标

- Claude Code Dream 机制（v2.1.59+）。触发条件为"24 小时 + 5 次会话"。
- 本实验测量 Dream 的一个简化规则引擎实现，不完全对应 Claude Code 的内部
  实现，但遵循同样的四阶段设计（Orientation / Gather / Consolidate / Prune）。

## 实验设定

**输入**：10 份合成的 Memory 文件，分别覆盖：
- `simple_project.md`：规模小，重复少
- `duplicate_heavy.md`：有大量重复条目
- `relative_dates.md`：大量"今天"/"昨天"相对日期
- `mixed_types.md`：架构决策 + 日常事件 + 一次性操作混合
- `long_stream.md`：超过 200 行的 overflow 情况
- `empty_after_dedup.md`：去重后所剩无几
- `yaml_front_matter.md`：带有 YAML 元数据
- `multilingual.md`：中英文混排
- `chronology.md`：时间顺序混乱的事件流
- `operations_log.md`：运维类条目（重启 / 部署 / 回滚）

**自变量**：无（单组测量）

**因变量**：
- `lines_before` / `lines_after`：整理前后行数
- `reduction_pct`：行数减少百分比
- `duplicates_removed`：去重条目数
- `relative_dates_converted`：相对日期转换数
- `empty_files_pruned`：被删除的空文件数
- `index_entries_after`：MEMORY.md 索引的条目数

**控制变量**：
- 整理时间固定为 `2026-04-19`（避免日期随当前时间变化影响可复现性）
- 规则引擎实现固定（对齐章节代码清单）

**样本量**：10 份输入文件即样本总体。

## 成本估算

无 API 调用。CPU 时间 < 5 秒。可随时跑。

## 实际产出

- `results/raw.jsonl`：每份文件的整理记录（10 行）
- `results/summary.csv`：整体统计
- `results/diffs/<file>.md`：每份文件整理前后的 diff 展示（用于书稿截取）

## 复现命令

```bash
python experiments/ch06/exp4_dream_consolidation/run.py
```

无 `--smoke`，因为总成本已经极低。

## 实测结论（已回填书稿 6.4.3 节）

- **总行数：344 → 290（降 15.7%）**，逐文件平均缩减率 **5.84%**（最高单文件 19.8%，long_stream.md）
- **重复条目去除 4 处，相对日期转换 13 处**
- **YAML front matter 受保护**：当前实现在去重前先剥离 `---\n...\n---`，只对 body 做行级去重，`---` 分隔符不会被当成重复行误删（早期实现未保护时数字更高但不严谨）
- **收益分布不均**：`duplicate_heavy.md` 和 `long_stream.md` 缩减明显；大部分 simple/multilingual/yaml 类文件 0% 缩减，因为它们本身就没有重复行
- **规则引擎的局限**：语义相似但措辞不同的条目（如"API 端点放在 routes/" vs "所有路由定义在 routes/ 中"）不会被合并，这部分要由 LLM 语义合并或 Claude Code 完整 Dream 机制承担，见 6.4.3 节开头的"三层实现"说明

## 限制

- 10 份 Memory 文件都是合成的。真实用户的 Memory 可能有更复杂的模式。
- 不测量 Dream 对 Agent 实际行为的影响（那需要 exp5 或额外实验）。
