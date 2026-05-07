# 实验一：AGENTS.md 长度效应

## 目的

在 harness-py + DeepSeek 上测量：AGENTS.md（CLAUDE.md）不同长度对 Agent 完成
bug 修复任务的影响。验证或挑战 ETH 论文 arXiv:2602.11988 的结论"过度详细反而
降低成功率、增加成本 20%+"。

## 变量

- **任务**：3 个代表性 bug
  - `cost_tracker_bug` - 补方法
  - `retry_decorator_bug` - 修异常处理逻辑
  - `csv_parser_bug` - 修数据处理边界

- **文档档位**：4 档
  - `L0` 无 CLAUDE.md
  - `L1` 精简（约 300 tokens）
  - `L2` 标准（约 1500 tokens）
  - `L3` 冗长（约 7000 tokens）

- **种子**：5 个（通过 seed 相关的 temperature 扰动获得独立样本）

默认规模 3 × 4 × 5 × 1 = 60 次任务，约 90 分钟（与 `experiments/ch05/README.md` 索引一致）。

## 运行

```bash
# 冒烟（1 次，验证管道）
python run.py --smoke

# 单任务单档位
python run.py --task cost_tracker_bug --variant L2 --seeds 1

# 全量
python run.py
```

结果写入 `results/results.json`，支持中途崩溃后继续（增量写盘）。

## 指标

每次任务记录：
- `success`：pytest 是否通过（独立验证，不依赖 Agent 自述）
- `turns`：总轮数
- `tool_calls`：工具调用次数
- `total_tokens`：总 token 消耗（输入+输出）
- `stop_reason`：Agent 停止原因
- `duration_sec`：wall-clock 秒数

## 实测结果（2026-04，DeepSeek-V3）

| 档位 | 任务成功率 | 平均轮次 | 平均 Token 消耗 |
|------|-----------|---------|----------------|
| L0 无文档 | 100% | 10.9 | 38,234 |
| L1 精简 | 100% | 10.5 | 38,408 |
| L2 标准 | 100% | 11.0 | 39,793 |
| L3 冗长 | 100% | 11.5 | 67,711 |

核心观察：
- 60 次任务全部成功。在简单确定性任务上，文档长度对"能否完成"几乎没有影响（强模型有足够能力从代码补全缺失的上下文）。
- 真正的断层出现在**成本维度**：L0/L1/L2 几乎持平（38K 上下），L3 跃升至 67K，比 L0 多 77%。
- 这比 ETH 论文报告的 20%+ 更激进，原因是 L3 刻意模拟了"文档年久堆积"的真实状态，注入大量历史决策和架构论述等看似有用的背景材料；ETH 的冗长版本写得克制一些。
- 拐点落在 L2 和 L3 之间，与 Anthropic"一眼能读完"经验值建议的 1500-2000 tokens 上限吻合。

数据已回填书稿 5.1.3 节表格。
