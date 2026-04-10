# Ch1实验统一任务

## 任务描述（三个Agent使用完全相同的prompt）

```
给harness_py框架的CostTracker模块补充以下功能：

1. 在 src/cost_tracker.py 中给 CostTracker 类添加 summary() 方法，返回一个字典包含：
   - total_calls: 总记录次数
   - total_input_tokens: 输入token总数
   - total_output_tokens: 输出token总数  
   - total_cost_usd: 总成本（美元）
   - by_model: 按模型分组的统计

2. 在 harness_py/agent.py 中集成CostTracker：
   - 每次API调用后记录token消耗
   - 在run()结束时将summary写入RunResult.cost_summary

3. 写单元测试 tests/test_cost_tracker.py，覆盖：
   - record()基本功能
   - summary()汇总计算
   - 空记录时的边界情况

完成后运行 python -m pytest tests/test_cost_tracker.py -v 确认全部通过。
```

## 执行环境

- 项目目录: D:/Working_Tools/Projects/harness-py-book/
- 已有文件: harness_py/ 完整框架（11个模块）
- 需要创建: src/cost_tracker.py（如果不存在）
- Python: 3.13

## 三次运行

### Run 1: Claude Code (Opus 4.6)
```bash
cd D:/Working_Tools/Projects/harness-py-book
claude "给harness_py框架的CostTracker模块补充以下功能：..."
```
运行完后执行捕获脚本。

### Run 2: Codex (GPT-5.4)  
```bash
cd D:/Working_Tools/Projects/harness-py-book
codex "给harness_py框架的CostTracker模块补充以下功能：..."
```
运行完后执行捕获脚本。

### Run 3: harness_py + DeepSeek（自动）
```bash
cd D:/Working_Tools/Projects/harness-py-book
python experiments/ch01_run_deepseek.py
```
